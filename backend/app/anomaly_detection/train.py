# ============================================================
# anomaly_detection/train.py
# ============================================================
import os
import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from backend.app.anomaly_detection.data_handling import build_features, FEATURES

MODELS_DIR = "models"
MIN_SAMPLES = 5   # don't train on fewer than 5 invoices — model would be meaningless


def train_pipeline(X: pd.DataFrame) -> Pipeline:
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model", IsolationForest(
            n_estimators=200,
            contamination=0.05,   # expect ~5% of invoices to be anomalous
            random_state=42,
        ))
    ])
    pipe.fit(X)
    return pipe


def model_key(user_id, vendor_name: str, currency: str) -> str:
    """Consistent key used for both saving and loading models."""
    safe_vendor = vendor_name.strip().lower().replace(" ", "_")
    return f"{user_id}__{safe_vendor}__{currency.lower()}"


def train_all(df: pd.DataFrame) -> dict:
    """
    Train one IsolationForest per (user_id, vendor_name, currency) group
    with enough history, plus one global fallback model for vendors with
    insufficient history.

    Returns a dict of {model_key: fitted_pipeline}.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    df = build_features(df)
    models = {}

    # Per-vendor models
    for (user_id, vendor, currency), group in df.groupby(
        ["user_id", "vendor_name", "currency"]
    ):
        if len(group) < MIN_SAMPLES:
            continue

        X = group[FEATURES].fillna(0)
        pipe = train_pipeline(X)
        key = model_key(user_id, vendor, currency)
        models[key] = pipe
        joblib.dump(pipe, os.path.join(MODELS_DIR, f"{key}.pkl"))

    # Global fallback model — trained on all invoices
    # used when a vendor has no dedicated model yet
    X_global = df[FEATURES].fillna(0)
    if len(X_global) >= MIN_SAMPLES:
        global_pipe = train_pipeline(X_global)
        models["global"] = global_pipe
        joblib.dump(global_pipe, os.path.join(MODELS_DIR, "global.pkl"))

    print(f"Trained {len(models) - 1} vendor models + 1 global fallback.")
    return models