import os
import joblib
import pandas as pd
import numpy as np

from backend.app.anomaly_detection.data_handling import build_features, FEATURES

MODELS_DIR = "models"


def load_models(models_dir: str = MODELS_DIR) -> dict:
    """Load all .pkl model files from disk into a dict keyed by model name."""
    models = {}
    if not os.path.exists(models_dir):
        return models

    for filename in os.listdir(models_dir):
        if not filename.endswith(".pkl"):
            continue
        key = filename[:-4]  # strip .pkl
        path = os.path.join(models_dir, filename)
        models[key] = joblib.load(path)  # joblib.load, not open().read()

    return models


# anomaly_detection/detect.py — update detect_anomaly to return logs
def detect_anomaly(models: dict, invoice: dict, user_id: int) -> dict:
    from backend.app.anomaly_detection.train import model_key

    vendor = invoice.get("vendor_name", "")
    currency = invoice.get("currency", "USD")
    key = model_key(user_id, vendor, currency)

    logs = []  # human-readable trace of what happened

    row = pd.DataFrame([{
        "user_id": user_id,
        "vendor_name": vendor,
        "currency": currency,
        "total_amount": invoice.get("total_amount", 0),
        "tax_amount": invoice.get("tax_amount", 0),
        "invoice_date": invoice.get("invoice_date"),
        "line_items": invoice.get("line_items", []),
    }])
    row = build_features(row)

    if key in models:
        model = models[key]
        model_used = key
        logs.append(f"Vendor model found for '{vendor}' ({currency}).")
    elif "global" in models:
        model = models["global"]
        model_used = "global"
        logs.append(f"No vendor model for '{vendor}' — not enough historical data.")
        logs.append("Falling back to global model. Prediction may be less accurate.")
    else:
        logs.append("No models available. Anomaly detection skipped.")
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "model_used": "none",
            "logs": logs,
        }

    X = row[FEATURES].fillna(0)
    prediction = model.predict(X)[0]
    score = model.score_samples(X)[0]
    is_anomaly = prediction == -1

    logs.append(f"Anomaly score: {score:.4f} (lower = more anomalous).")
    if is_anomaly:
        logs.append(f"⚠ Flagged as anomalous by {model_used} model.")
    else:
        logs.append(f"✓ Invoice appears normal based on vendor history.")

    return {
    "is_anomaly": bool(is_anomaly),        # ← explicit cast
    "anomaly_score": round(float(score), 4),  # ← already float
    "model_used": model_used,
    "logs": logs,
    }