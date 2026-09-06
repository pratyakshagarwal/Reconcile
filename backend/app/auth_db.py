"""
Schema additions for auth + per-user pipeline run history.

Run init_auth_db() once after your existing init_db() to add these tables
and back-fill user_id columns onto invoices/purchase_orders/goods_receipts.
"""

import json
from datetime import datetime, timezone
from backend.app.db import get_connection
from backend.app.dbs.risk_db import insert_reviewer_decision, create_reviewer_decisions_table

def init_auth_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # One row per full pipeline execution — this is the actual "session history."
    # report is stored as JSONB since it's read as a whole object, not queried field-by-field.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
            status TEXT NOT NULL,
            report JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Back-fill ownership columns onto existing tables.
    # Nullable for now since pre-existing rows have no associated user.
    cur.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)")
    cur.execute("ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)")
    cur.execute("ALTER TABLE goods_receipts ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)")
    # one-time additions — safe to re-run, ALTER...IF NOT EXISTS skips if already applied
    cur.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS human_decision TEXT")
    cur.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS decided_by INTEGER REFERENCES users(id)")
    cur.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS decided_at TIMESTAMP")
    cur.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS reviewer_note TEXT")
    cur.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS thread_id TEXT")
    create_reviewer_decisions_table()

    conn.commit()
    cur.close()
    conn.close()


def create_user(email: str, password_hash: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
        (email.strip().lower(), password_hash)
    )
    user_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return user_id


def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email.strip().lower(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "password_hash": row[2]}


def insert_pipeline_run(user_id: int, invoice_id: int | None, status: str, report: dict | None, thread_id: str=None) -> int:

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO pipeline_runs (user_id, invoice_id, status, report, thread_id)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (user_id, invoice_id, status, json.dumps(report) if report else None, thread_id)
    )
    run_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return run_id


def list_pipeline_runs(user_id: int, limit: int = 50) -> list[dict]:
    """Returns this user's run history only — never another user's data."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, invoice_id, status, report, human_decision, decided_at, created_at
           FROM pipeline_runs
           WHERE user_id = %s
           ORDER BY created_at DESC
           LIMIT %s""",
        (user_id, limit)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": r[0], "invoice_id": r[1], "status": r[2], "report": r[3],
            "human_decision": r[4],
            "decided_at": r[5].isoformat() if r[5] else None,
            "created_at": r[6].isoformat(),
        }
        for r in rows
    ]


def get_pipeline_run(user_id: int, run_id: int) -> dict | None:
    """Fetches one run, scoped to the requesting user — returns None if it belongs to someone else."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, invoice_id, status, report, human_decision, decided_at, created_at
           FROM pipeline_runs
           WHERE id = %s AND user_id = %s""",
        (run_id, user_id)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return None
    return {
        "id": row[0], "invoice_id": row[1], "status": row[2], "report": row[3],
        "human_decision": row[4],
        "decided_at": row[5].isoformat() if row[5] else None,
        "created_at": row[6].isoformat(),
    }

VALID_DECISIONS = {"approved", "rejected"}


def update_run_decision(
    run_id: int,
    user_id: int,
    decision: str,
    note: str = ""
) -> bool:
    """
    Records the human decision on a pipeline run AND logs it
    to reviewer_decisions for future vendor risk adjustment —
    both happen in the same call, so they're always in sync.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 1. Update the pipeline run's decision fields
    cur.execute(
        """UPDATE pipeline_runs
           SET human_decision = %s,
               decided_by = %s,
               decided_at = %s,
               reviewer_note = %s
           WHERE id = %s AND user_id = %s
           RETURNING invoice_id, report""",
        (decision, user_id, datetime.now(timezone.utc), note, run_id, user_id)
    )
    row = cur.fetchone()
    updated = row is not None
    conn.commit()
    cur.close()
    conn.close()

    # 2. If update succeeded, log to reviewer_decisions for risk learning
    if updated:
        invoice_id, report = row
        report = report or {}
        risk = report.get("stages", {}).get("risk", {})

        insert_reviewer_decision(
            invoice_id=invoice_id,
            reviewer_id=user_id,
            vendor_name=report.get("vendor_name"),
            decision=decision,
            risk_score_at_decision=risk.get("score"),
            risk_factors=risk.get("reasons", []),
            reviewer_note=note,
        )

    return updated


def update_run_report(run_id: int, report: dict, status: str):
    conn = get_connection()
    cur = conn.cursor()
    import json
    cur.execute(
        """UPDATE pipeline_runs
           SET report = %s, status = %s
           WHERE id = %s""",
        (json.dumps(report) if report else None, status, run_id)
    )
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':init_auth_db()