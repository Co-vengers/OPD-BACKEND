from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # <--- Import this
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
import shutil
import os

from .database import engine, Base, get_db
from . import models, ai_service, rules_engine
from .schemas import ClaimResponse 

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Plum Adjudicator")

# 1. Setup Uploads Directory
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 2. Mount Static Files (So frontend can view images)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Plum Adjudicator Backend"}

@app.get("/api/claims")
def get_claims_history(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Claim).order_by(models.Claim.created_at.desc()).offset(skip).limit(limit).all()

@app.get("/api/dashboard-stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_claims = db.query(models.Claim).count()
    approved = db.query(models.Claim).filter(models.Claim.status == "APPROVED").count()
    rejected = db.query(models.Claim).filter(models.Claim.status == "REJECTED").count()
    partial = db.query(models.Claim).filter(models.Claim.status == "PARTIAL").count()
    manual = db.query(models.Claim).filter(models.Claim.status == "MANUAL_REVIEW").count()
    total_disbursed = db.query(func.sum(models.Claim.approved_amount)).scalar() or 0.0
    total_claimed = db.query(func.sum(models.Claim.total_amount)).scalar() or 0.0
    
    auto_rate = 0
    if total_claims > 0:
        auto_rate = ((total_claims - manual) / total_claims) * 100

    return {
        "total_claims": total_claims,
        "approved": approved,
        "rejected": rejected,
        "partial": partial,
        "manual_review": manual,
        "total_disbursed": total_disbursed,
        "total_claimed": total_claimed,
        "auto_adjudication_rate": round(auto_rate, 1)
    }

@app.post("/api/submit-claim")
async def submit_claim(file: UploadFile = File(...), db: Session = Depends(get_db)):
    
    # 1. Read Content for AI
    content = await file.read()
    
    # 2. Save File to Disk
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"{UPLOAD_DIR}/{unique_filename}"
    
    with open(file_path, "wb") as f:
        f.write(content)

    # 3. AI Processing
    extracted_data = ai_service.extract_claim_data(content, file.content_type)
    
    if "error" in extracted_data:
        raise HTTPException(status_code=400, detail="AI Processing Failed")

    # 4. Fetch History
    patient_name = extracted_data.get("patient_name")
    current_year_total = 0.0
    if patient_name:
        total_spent = db.query(func.sum(models.Claim.approved_amount))\
            .filter(models.Claim.patient_name == patient_name)\
            .filter(models.Claim.status.in_(["APPROVED", "PARTIAL"]))\
            .scalar()
        current_year_total = total_spent or 0.0

    # 5. Adjudicate
    decision = rules_engine.adjudicate(extracted_data, current_year_total)

    # 6. Save to DB
    claim_id = f"CLM-{str(uuid.uuid4())[:8].upper()}"
    
    db_claim = models.Claim(
        claim_id=claim_id,
        patient_name=patient_name,
        diagnosis=extracted_data.get("diagnosis"),
        treatment_date=extracted_data.get("date_of_service"),
        total_amount=extracted_data.get("total_claimed_amount"),
        approved_amount=decision["approved_amount"],
        status=decision["status"],
        confidence_score=extracted_data.get("confidence_score"),
        rejection_reasons=decision["reasons"],
        extracted_data=extracted_data,
        file_path=file_path # <--- Saving the path
    )
    
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)

    return db_claim