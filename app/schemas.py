from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any, Dict
from datetime import datetime

# Base Schema
class ClaimBase(BaseModel):
    claim_id: str
    patient_name: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_date: Optional[str] = None
    
    # Financials
    total_amount: float
    approved_amount: float
    
    # Decisions
    status: str
    confidence_score: float
    rejection_reasons: Optional[List[str]] = []
    
    # Full extraction data
    extracted_data: Optional[Dict[str, Any]] = None

# Response Schema (includes DB ID and timestamps)
class ClaimResponse(ClaimBase):
    id: int
    created_at: datetime

    # Pydantic v2 Config to read from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)