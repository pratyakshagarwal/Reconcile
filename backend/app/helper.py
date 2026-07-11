#helper.py
from backend.app.db import get_connection

def unwrap_confident_fields(data: dict) -> dict:
    """Strips ConfidentField wrappers back to plain values, recursively.
    Call this once right after extraction — everything downstream stays
    exactly as it was before confidence scoring existed."""
    result = {}
    for key, val in data.items():
        if isinstance(val, dict) and "value" in val and "confidence" in val:
            result[key] = val["value"]
        elif isinstance(val, list):
            result[key] = [unwrap_confident_fields(item) if isinstance(item, dict) else item for item in val]
        elif isinstance(val, dict):
            result[key] = unwrap_confident_fields(val)
        else:
            result[key] = val
    return result


def extract_confidences(data: dict) -> dict:
    """Pulls out just the confidence scores, separately, before unwrapping."""
    return {
        key: val["confidence"]
        for key, val in data.items()
        if isinstance(val, dict) and "confidence" in val
    }

def get_vendor_history(vendor_name: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT AVG(total_amount), COUNT(*) FROM invoices
           WHERE vendor_name = %s""",
        (vendor_name.strip().lower(),)
    )
    avg_amount, count = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "is_new_vendor": count == 0,
        "avg_invoice_amount": float(avg_amount) if avg_amount else None,
        "invoice_count": count,
    }

def process_context(report: dict) -> dict:
    """
    Convert full pipeline report into a compact,
    LLM-friendly explanation context.
    """

    stages = report.get("stages", {})

    validation = stages.get("validation", {})
    matching = stages.get("matching", {})
    risk = stages.get("risk", {})
    warnings = stages.get("warnings", [])

    signals = []

    # Validation errors
    for err in validation.get("errors", []):
        signals.append(f"Validation error: {err}")

    # Matching issues
    for issue in matching.get("issues", []):

        field = issue.get("field", "")
        severity = issue.get("severity", "medium")

        # Missing line items
        if field.startswith("line_item:"):

            item_name = field.replace("line_item:", "").strip()
            item_name = item_name[:80]

            signals.append(
                f"Critical line item missing from goods receipt: {item_name}"
            )

        # Total mismatch
        elif field == "total_amount":

            signals.append(
                f"Invoice total differs significantly from expected value "
                f"(expected {issue.get('expected')}, found {issue.get('actual')})"
            )

        else:

            signals.append(
                f"{field} mismatch detected with {severity} severity"
            )

    # Pipeline warnings
    for warning in warnings:

        # warnings are like:
        # {"DuplicatePurchaseOrder": "purchase order with same no exists in database"}

        if isinstance(warning, dict):

            for key, value in warning.items():

                readable_key = (
                    key.replace("_", " ")
                    .replace("-", " ")
                )

                signals.append(
                    f"{readable_key}: {value}"
                )

        else:
            signals.append(str(warning))

    return {
        "invoice_number": report.get("invoice_number"),
        "vendor_name": report.get("vendor_name"),
        "risk_level": risk.get("tier"),
        "risk_score": risk.get("score"),
        "signals": signals
    }

import numpy as np

def jsonable(value):
    if value is None:
        return None
    if isinstance(value, (np.bool_, np.integer, np.floating)):
        return value.item()  # converts numpy scalar to native Python type
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(i) for i in value]
    return value


if __name__ == '__main__':pass