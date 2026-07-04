"""
Stores reviewer decisions for vendor-level risk adjustment.
Each row is one human decision on one invoice run — over time,
this table becomes the basis for adaptive risk scoring per vendor.
"""

from datetime import datetime, timezone
from backend.app.db import get_connection


def create_reviewer_decisions_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviewer_decisions (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER,
            reviewer_id INTEGER REFERENCES users(id),
            vendor_name TEXT,
            decision TEXT NOT NULL,
            risk_score_at_decision INTEGER,
            risk_factors JSONB,
            reviewer_note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def insert_reviewer_decision(
    invoice_id: int | None,
    reviewer_id: int,
    vendor_name: str | None,
    decision: str,
    risk_score_at_decision: int | None,
    risk_factors: list,
    reviewer_note: str = "",
):
    conn = get_connection()
    cur = conn.cursor()
    import json
    cur.execute(
        """INSERT INTO reviewer_decisions
           (invoice_id, reviewer_id, vendor_name, decision, risk_score_at_decision, risk_factors, reviewer_note)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            invoice_id,
            reviewer_id,
            vendor_name.strip().lower(),
            decision,
            risk_score_at_decision,
            json.dumps(risk_factors),
            reviewer_note,
        )
    )
    conn.commit()
    cur.close()
    conn.close()


def get_vendor_decisions(vendor_name: str) -> list[dict]:
    """
    Returns all past reviewer decisions for a given vendor.
    Used by the risk agent to check: did reviewers historically
    approve this vendor even when it was flagged?
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT decision, risk_score_at_decision, risk_factors, created_at
           FROM reviewer_decisions
           WHERE vendor_name = %s
           ORDER BY created_at DESC""",
        (vendor_name.strip().lower(),)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "decision": r[0],
            "risk_score_at_decision": r[1],
            "risk_factors": r[2],
            "created_at": r[3].isoformat(),
        }
        for r in rows
    ]