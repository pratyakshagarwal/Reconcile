
import numpy as np
import pandas as pd
import os
import psycopg2


FEATURES = [
    "invoice_total",
    "tax_percent",
    "line_item_count",
    "avg_unit_price",
    "vendor_avg_invoice_total",
    "vendor_std_invoice_total",
    "vendor_avg_line_items",
    "vendor_invoice_frequency",
    "days_since_last_vendor_invoice",
    "invoice_total_ratio",       # most important — relative deviation
    "line_item_count_ratio",     # most important — relative deviation
]

def get_connection():
    return psycopg2.connect(os.getenv("DB_URL"))


def get_invoice_sample() -> pd.DataFrame:
    """
    Pulls all invoices + line items from Supabase and returns
    a flat DataFrame ready to pass into build_features().
    No sampling — train on everything available.
    """
    conn = get_connection()

    invoices = pd.read_sql("""
        SELECT
            id,
            user_id,
            vendor_name,
            invoice_number,
            invoice_date,
            total_amount,
            tax_amount,
            currency
        FROM invoices
        WHERE user_id IS NOT NULL
          AND total_amount IS NOT NULL
          AND vendor_name IS NOT NULL
    """, conn)

    line_items = pd.read_sql("""
        SELECT
            invoice_id,
            description,
            quantity,
            unit_price
        FROM invoice_line_items
    """, conn)

    conn.close()

    if invoices.empty:
        return pd.DataFrame()

    # Aggregate line items per invoice into a list of dicts
    grouped = (
        line_items
        .groupby("invoice_id")
        .apply(lambda x: x[["description", "quantity", "unit_price"]].to_dict("records"))
        .rename("line_items")
        .reset_index()
    )

    # Merge line items onto invoices — invoices with no line items get empty list
    df = invoices.merge(
        grouped,
        left_on="id",
        right_on="invoice_id",
        how="left"
    ).drop(columns=["invoice_id"])

    df["line_items"] = df["line_items"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    return df

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["invoice_total"] = df["total_amount"].fillna(0)

    # Tax as a percentage of pre-tax subtotal
    subtotal = df["total_amount"] - df["tax_amount"]
    df["tax_percent"] = (df["tax_amount"] / subtotal.replace(0, np.nan)).fillna(0)

    df["line_item_count"] = df["line_items"].apply(
        lambda items: len(items) if isinstance(items, list) else 0
    )
    df["avg_unit_price"] = df["line_items"].apply(
        lambda items: np.mean([x["unit_price"] for x in items])
        if isinstance(items, list) and len(items) > 0 else 0
    )

    # Vendor-level historical statistics (per user + vendor pair)
    vendor_stats = (
        df.groupby(["user_id", "vendor_name"])
          .agg(
              vendor_avg_invoice_total=("invoice_total", "mean"),
              vendor_std_invoice_total=("invoice_total", "std"),
              vendor_avg_line_items=("line_item_count", "mean"),
              vendor_invoice_frequency=("invoice_total", "count"),
          )
          .reset_index()
    )

    df = df.merge(vendor_stats, on=["user_id", "vendor_name"], how="left")
    df["vendor_std_invoice_total"] = df["vendor_std_invoice_total"].fillna(0)

    # Days since last invoice from same vendor — cap at 365 instead of 999
    # so the scaler doesn't blow up on first-invoice rows
    df = df.sort_values(["user_id", "vendor_name", "invoice_date"])
    df["days_since_last_vendor_invoice"] = (
        df.groupby(["user_id", "vendor_name"])["invoice_date"]
          .diff()
          .dt.days
          .clip(upper=365)       # cap outliers
          .fillna(180)           # neutral midpoint for first invoice, not 999
    )

    # Relative features — how much does this invoice deviate from vendor norm?
    df["invoice_total_ratio"] = (
        df["invoice_total"] /
        df["vendor_avg_invoice_total"].replace(0, np.nan)
    ).fillna(1.0)  # 1.0 = "normal" when no history

    df["line_item_count_ratio"] = (
        df["line_item_count"] /
        df["vendor_avg_line_items"].replace(0, np.nan)
    ).fillna(1.0)

    return df