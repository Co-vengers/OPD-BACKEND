from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uuid

from .database import engine, Base, get_db
from . import models, ai_service, rules_engine

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Plum Adjudicator")

# CORS Setup (Allow Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/submit-claim")
async def submit_claim(file: UploadFile = File(...), db: Session = Depends(get_db)):
    
    # 1. Process Image
    content = await file.read()
    extracted_data = ai_service.extract_claim_data(content, file.content_type)
    
    if "error" in extracted_data:
        raise HTTPException(status_code=400, detail="AI Processing Failed")

    # 2. Run Adjudication Rules
    decision = rules_engine.adjudicate(extracted_data)

    # 3. Save to DB
    claim_id = f"CLM-{str(uuid.uuid4())[:8].upper()}"
    
    db_claim = models.Claim(
        claim_id=claim_id,
        patient_name=extracted_data.get("patient_name"),
        diagnosis=extracted_data.get("diagnosis"),
        treatment_date=extracted_data.get("date_of_service"),
        total_amount=extracted_data.get("total_claimed_amount"),
        approved_amount=decision["approved_amount"],
        status=decision["status"],
        confidence_score=extracted_data.get("confidence_score"),
        rejection_reasons=decision["reasons"],
        extracted_data=extracted_data
    )
    
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)

    return db_claim