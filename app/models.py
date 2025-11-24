from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, Text
from datetime import datetime
from .database import Base

class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String, unique=True, index=True)
    patient_name = Column(String)
    diagnosis = Column(String)
    treatment_date = Column(String)
    
    # Financials
    total_amount = Column(Float)
    approved_amount = Column(Float)
    
    # Decisions
    status = Column(String)  # APPROVED, REJECTED, PARTIAL, MANUAL_REVIEW
    confidence_score = Column(Float)
    rejection_reasons = Column(JSON) # Store list of strings
    
    # Meta
    extracted_data = Column(JSON) # Full raw extraction
    created_at = Column(DateTime, default=datetime.utcnow)