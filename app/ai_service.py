import google.generativeai as genai
import os
import json
import typing_extensions as typing

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-flash")

def extract_claim_data(image_bytes: bytes, mime_type: str) -> dict:
    """
    Sends the image to Gemini Flash and returns structured JSON.
    """
    prompt = """
    Analyze this medical document (Bill, Prescription, or Report).
    Extract the data strictly into the following JSON format.
    If a field is not visible, use null.
    
    schema = {
        "document_type": "BILL" | "PRESCRIPTION" | "REPORT" | "UNKNOWN",
        "patient_name": str,
        "date_of_service": "YYYY-MM-DD",
        "doctor_name": str,
        "doctor_reg_no": str, # Format: STATE/NUM/YEAR
        "diagnosis": str,
        "medicines": [str],
        "total_claimed_amount": float,
        "line_items": [{"item": str, "cost": float}],
        "hospital_name": str,
        "is_handwritten": bool,
        "confidence_score": float # 0.0 to 1.0 based on clarity/legibility
    }
    CRITICAL: Evaluate "medical_necessity_check". 
    If the medicines/tests do not match the diagnosis (e.g., "Cast" for "Fever", or "Whitening" for "Cavity"), set to "FAIL".
    """
    
    try:
        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": image_bytes}
        ])
        
        # Strip markdown code blocks if Gemini adds them
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3]
            
        return json.loads(text)
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        return {
            "error": "Failed to process document", 
            "confidence_score": 0.0
        }