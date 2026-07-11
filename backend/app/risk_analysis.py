from backend.app.schemas import MatchResult
from backend.app.helper import get_vendor_history
from backend.app.dbs.risk_db import get_vendor_decisions


def assess_risk(invoice: dict, match_result: MatchResult,invoice_confidences: dict, anomaly_result) -> dict:
    score = 0
    reasons = []
    vendor_history = get_vendor_history(vendor_name=invoice['vendor_name'])

    if any(i.severity == "critical" for i in match_result.issues):
        score += 40
        reasons.append("Critical matching mismatch")

    avg_amount = vendor_history.get("avg_invoice_amount")
    if avg_amount and invoice["total_amount"] > avg_amount * 1.5:
        score += 15
        reasons.append("Amount 50%+ above vendor average")

    low_confidence_fields = [f for f, c in invoice_confidences.items() if c < 0.6]
    if low_confidence_fields:
        score += 15
        reasons.append(f"Low extraction confidence on: {', '.join(low_confidence_fields)}")

    if vendor_history.get("is_new_vendor"):
        score += 10
        reasons.append("New/unseen vendor")

    # ML anomaly signal
    if anomaly_result and anomaly_result.get("is_anomaly"):
        score += 25
        model = anomaly_result.get("model_used", "unknown")
        reasons.append(
            f"ML anomaly detected (score {anomaly_result.get('anomaly_score', 0):.3f}, "
            f"model: {model})"
        )
    
    vendor_name = invoice.get("vendor_name", "")
    past_decisions = get_vendor_decisions(vendor_name)
    if past_decisions:
        approved = sum(1 for d in past_decisions if d["decision"] == "approved")
        total = len(past_decisions)
        approval_rate = approved / total

        if approval_rate >= 0.8 and total >= 3:
            score = max(0, score - 15)
            reasons.append(f"Vendor historically approved by reviewers ({approved}/{total} times)")
        elif approval_rate <= 0.2 and total >= 3:
            score += 20
            reasons.append(f"Vendor historically rejected by reviewers ({total - approved}/{total} times)")


    tier = "high" if score >= 50 else "medium" if score >= 20 else "low"
    return {"score": score, "tier": tier, "reasons": reasons}
