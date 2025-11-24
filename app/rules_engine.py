from datetime import datetime

# Mock Policy Configuration
POLICY = {
    "active_since": "2024-01-01",
    "waiting_period_days": 30,
    "limits": {
        "per_claim": 5000,
        "annual": 50000,
        "consultation_sublimit": 1000
    },
    "exclusions": [
        "cosmetic", "weight loss", "whitening", "hair transplant", 
        "supplement", "vitamin"
    ]
}

def adjudicate(data: dict) -> dict:
    reasons = []
    status = "APPROVED"
    claimed_amount = data.get("total_claimed_amount", 0) or 0
    approved_amount = claimed_amount

    # 1. Sanity & Fraud Checks
    if data.get("confidence_score", 0) < 0.70:
        return {
            "status": "MANUAL_REVIEW",
            "approved_amount": 0,
            "reasons": ["AI Confidence Low - Document might be blurry or incomplete"]
        }
        
    if not data.get("doctor_reg_no"):
        reasons.append("Missing or Invalid Doctor Registration Number")
        status = "REJECTED"

    # 2. Waiting Period Check
    service_date_str = data.get("date_of_service")
    if service_date_str:
        try:
            svc_date = datetime.strptime(service_date_str, "%Y-%m-%d")
            policy_start = datetime.strptime(POLICY["active_since"], "%Y-%m-%d")
            days_active = (svc_date - policy_start).days
            
            if days_active < POLICY["waiting_period_days"]:
                status = "REJECTED"
                reasons.append(f"Waiting Period Violation (Policy age: {days_active} days)")
                approved_amount = 0
        except ValueError:
            reasons.append("Invalid Date Format in Document")
            status = "MANUAL_REVIEW"

    # 3. Exclusions Check
    diagnosis = (data.get("diagnosis") or "").lower()
    raw_items = data.get("line_items") or [] 
    line_items = [item.get('item', '').lower() for item in raw_items if isinstance(item, dict)]
    
    # Check diagnosis against exclusions
    for exclusion in POLICY["exclusions"]:
        if exclusion in diagnosis:
            status = "REJECTED"
            reasons.append(f"Excluded Treatment: {exclusion.title()}")
            approved_amount = 0
            break
            
    # Check specific line items (Partial Approval Logic)
    if status != "REJECTED":
        new_total = 0
        items_to_process = data.get("line_items") or []
        
        for item in items_to_process:
            # We also ensure 'item' is a dictionary to prevent crashes
            if not isinstance(item, dict): 
                continue
                
            is_excluded = any(ex in item.get('item', '').lower() for ex in POLICY["exclusions"])
            if is_excluded:
                reasons.append(f"Line Item Rejected: {item.get('item')}")
                status = "PARTIAL"
            else:
                new_total += item.get('cost', 0)
        approved_amount = new_total

    # 4. Limit Checks
    if approved_amount > POLICY["limits"]["per_claim"]:
        reasons.append(f"Per-claim limit of ₹{POLICY['limits']['per_claim']} exceeded")
        approved_amount = POLICY["limits"]["per_claim"]
        if status == "APPROVED":
            status = "PARTIAL"

    # Final logic for complete rejections
    if approved_amount == 0 and status != "MANUAL_REVIEW":
        status = "REJECTED"

    return {
        "status": status,
        "approved_amount": approved_amount,
        "reasons": reasons
    }