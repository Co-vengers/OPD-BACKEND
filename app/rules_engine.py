from datetime import datetime

# --- POLICY CONFIGURATION ---
POLICY_TERMS = {
    "policy_id": "PLUM_OPD_2024",
    "effective_date": "2024-01-01",
    "coverage_details": {
        "annual_limit": 50000,
        "per_claim_limit": 5000,
        "consultation_fees": {
            "sub_limit": 2000,
            "copay_percentage": 10
        },
        "diagnostic_tests": {
            "sub_limit": 10000,
            "pre_auth_required_tests": ["MRI", "CT Scan"]
        },
        "pharmacy": {
            "sub_limit": 15000,
            "branded_drugs_copay": 30
        },
        "dental": {
            "sub_limit": 10000,
            "procedures_covered": ["Filling", "Extraction", "Root canal", "Cleaning"],
            "cosmetic_procedures": False
        }
    },
    "waiting_periods": {
        "initial_waiting": 30,
        "specific_ailments": {
            "diabetes": 90,
            "hypertension": 90,
            "joint_replacement": 730
        }
    },
    "exclusions": [
        "cosmetic", "weight loss", "infertility", "experimental", 
        "self-inflicted", "adventure sports", "alcoholism", "drug abuse",
        "whitening", "hair transplant"
    ],
    "claim_requirements": {
        "submission_timeline_days": 30,
        "minimum_claim_amount": 500
    }
}

def calculate_days_since_policy_start(treatment_date_str):
    try:
        treat_date = datetime.strptime(treatment_date_str, "%Y-%m-%d")
        policy_start = datetime.strptime(POLICY_TERMS["effective_date"], "%Y-%m-%d")
        return (treat_date - policy_start).days, treat_date
    except (ValueError, TypeError):
        return -1, None

def check_waiting_periods(diagnosis, days_active):
    diagnosis = diagnosis.lower() if diagnosis else ""
    
    # 1. Initial Waiting Period
    if days_active < POLICY_TERMS["waiting_periods"]["initial_waiting"]:
        return False, f"General Waiting Period not met (Policy age: {days_active} days)"

    # 2. Specific Ailments
    specific_waits = POLICY_TERMS["waiting_periods"]["specific_ailments"]
    for ailment, days in specific_waits.items():
        if ailment in diagnosis and days_active < days:
            return False, f"Waiting Period for {ailment.title()} not met ({days} days required)"
            
    return True, ""

def classify_claim_category(diagnosis, line_items):
    text_blob = (diagnosis + " " + " ".join([i.get('item', '') for i in line_items])).lower()
    
    if "root canal" in text_blob or "tooth" in text_blob or "filling" in text_blob:
        return "dental"
    if "consultation" in text_blob:
        return "consultation_fees"
    if "mri" in text_blob or "scan" in text_blob or "x-ray" in text_blob or "blood" in text_blob:
        return "diagnostic_tests"
    if "pharmacy" in text_blob or "tablet" in text_blob or "mg" in text_blob:
        return "pharmacy"
    return "general"

# --- CRITICAL FIX IS HERE ---
# We added 'current_year_total' to the function arguments
def adjudicate(data: dict, current_year_total: float = 0.0) -> dict:
    reasons = []
    status = "APPROVED"
    raw_amount = data.get("total_claimed_amount") or 0.0
    approved_amount = raw_amount
    
    # Helper for safe access
    extracted_items = data.get("line_items") or []
    valid_items = [item for item in extracted_items if isinstance(item, dict)]

    # --- STEP 1: SANITY & FRAUD CHECKS ---
    if data.get("confidence_score", 0) < 0.70:
        return {"status": "MANUAL_REVIEW", "approved_amount": 0, "reasons": ["Low AI Confidence Score"]}
    
    if not data.get("doctor_reg_no"):
        status = "REJECTED"
        reasons.append("DOCTOR_REG_INVALID: Missing Registration Number")
        
    if raw_amount < POLICY_TERMS["claim_requirements"]["minimum_claim_amount"]:
        status = "REJECTED"
        reasons.append(f"BELOW_MIN_AMOUNT: Claim is below ₹{POLICY_TERMS['claim_requirements']['minimum_claim_amount']}")

    # --- STEP 1.5: MEDICAL NECESSITY (AI CHECK) ---
    if data.get("medical_necessity_check") == "FAIL":
        status = "REJECTED"
        reason = data.get("medical_necessity_reason", "Treatment does not match diagnosis")
        reasons.append(f"NOT_MEDICALLY_NECESSARY: {reason}")

    # --- STEP 2: ELIGIBILITY & WAITING PERIODS ---
    days_active, treat_date = calculate_days_since_policy_start(data.get("date_of_service"))
    
    if treat_date:
        days_since_treatment = (datetime.now() - treat_date).days
        if days_since_treatment > POLICY_TERMS["claim_requirements"]["submission_timeline_days"]:
             status = "REJECTED"
             reasons.append(f"LATE_SUBMISSION: Submitted {days_since_treatment} days after treatment")

        is_eligible, wait_msg = check_waiting_periods(data.get("diagnosis"), days_active)
        if not is_eligible:
            status = "REJECTED"
            reasons.append(f"WAITING_PERIOD: {wait_msg}")
    else:
        reasons.append("DATE_INVALID: Could not parse Date of Service")
        status = "MANUAL_REVIEW"

    # --- STEP 3: EXCLUSIONS ---
    diagnosis_lower = (data.get("diagnosis") or "").lower()
    for excl in POLICY_TERMS["exclusions"]:
        if excl in diagnosis_lower:
            status = "REJECTED"
            reasons.append(f"EXCLUDED_CONDITION: {excl.upper()}")
            break
            
    if "dental" in classify_claim_category(diagnosis_lower, valid_items):
        if "whitening" in diagnosis_lower or "cosmetic" in diagnosis_lower:
             status = "REJECTED"
             reasons.append("EXCLUDED_CONDITION: Cosmetic Dental Procedure")

    # --- STEP 4: LIMITS & CALCULATIONS ---
    if status != "REJECTED":
        category = classify_claim_category(diagnosis_lower, valid_items)
        cat_rules = POLICY_TERMS["coverage_details"].get(category, {})
        
        # 4a. Annual Limit Check (Cumulative)
        remaining_annual_limit = POLICY_TERMS["coverage_details"]["annual_limit"] - current_year_total
        if remaining_annual_limit <= 0:
            status = "REJECTED"
            reasons.append(f"ANNUAL_LIMIT_EXCEEDED: History: ₹{current_year_total}, Limit: ₹{POLICY_TERMS['coverage_details']['annual_limit']}")
            approved_amount = 0
        elif approved_amount > remaining_annual_limit:
            reasons.append(f"ANNUAL_LIMIT_EXCEEDED: Capped at remaining ₹{remaining_annual_limit}")
            approved_amount = remaining_annual_limit
            if status == "APPROVED": status = "PARTIAL"

        # 4b. Sub-limits
        if "sub_limit" in cat_rules and approved_amount > cat_rules["sub_limit"]:
            reasons.append(f"SUB_LIMIT_EXCEEDED: {category.title()} limit is ₹{cat_rules['sub_limit']}")
            approved_amount = min(approved_amount, cat_rules["sub_limit"])
            if status == "APPROVED": status = "PARTIAL"

        # 4c. Co-pay
        if "copay_percentage" in cat_rules:
            copay_amt = approved_amount * (cat_rules["copay_percentage"] / 100)
            approved_amount -= copay_amt
            reasons.append(f"CO_PAY_DEDUCTION: {cat_rules['copay_percentage']}% co-pay applied")
            if status == "APPROVED": status = "PARTIAL"

        # 4d. Per-Claim Limit
        if approved_amount > POLICY_TERMS["coverage_details"]["per_claim_limit"]:
            reasons.append(f"PER_CLAIM_EXCEEDED: Capped at ₹{POLICY_TERMS['coverage_details']['per_claim_limit']}")
            approved_amount = POLICY_TERMS["coverage_details"]["per_claim_limit"]
            if status == "APPROVED": status = "PARTIAL"

    if approved_amount <= 0 and status != "MANUAL_REVIEW":
        status = "REJECTED"
        approved_amount = 0

    return {
        "status": status,
        "approved_amount": round(approved_amount, 2),
        "reasons": reasons
    }