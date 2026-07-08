"""
FastAPI app exposing the LangGraph invoice pipeline, with per-user auth.

Auth routes:
  POST /api/auth/signup   — create account (email + password, password is hashed)
  POST /api/auth/login    — verify credentials, issue a JWT

Protected routes (require Authorization: Bearer <token>):
  POST /api/process        — upload invoice (+ optional PO/GR), stream node-by-node results via SSE
  GET  /api/runs            — list THIS user's past pipeline runs (session history)
  GET  /api/runs/{run_id}   — full report for one of THIS user's past runs
  POST /api/runs/{run_id}/decide  -- Approved or Decline for that process
  GET /api/invoices/          - List the invoices with user_id in stored 
  GET /api/invoices/{invoice_id} extract a particular invoice based on invoice id return invoice data 
  j
Run with: uvicorn app.main:app --reload
"""

import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

# These import from your existing pipeline module — adjust the import path
# to wherever create_graph/nodes/paths actually live in your project.
from backend.app.agent import create_graph, nodes, paths
from backend.app.db import get_connection
from backend.app.auth import hash_password, verify_password, create_access_token, get_current_user_id
from backend.app.auth_db import (
    init_auth_db, create_user, get_user_by_email,
    insert_pipeline_run, list_pipeline_runs, get_pipeline_run,
    VALID_DECISIONS, update_run_decision
)

app = FastAPI(title="Invoice Automation Pipeline")
init_auth_db()  # ensures users/pipeline_runs tables + user_id columns exist on startup

# Allow the frontend dev server to call this API during local development.
# Tighten allow_origins to your actual deployed frontend URL before shipping.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = create_graph(nodes, paths)

# ============================================================
# AUTH ROUTES
# ============================================================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(payload: SignupRequest):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    existing = get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    password_hash = hash_password(payload.password)
    user_id = create_user(payload.email, password_hash)

    token = create_access_token(user_id, payload.email)
    return TokenResponse(access_token=token)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm expects 'username' + 'password' fields —
    # we treat 'username' as the email address here.
    user = get_user_by_email(form_data.username)
    if user is None or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=token)

# Human-readable labels for each node — shown in the frontend's live progress UI
NODE_LABELS = {
    "extraction": "Extracting document fields",
    "validation": "Validating extracted data",
    "duplicate_detect": "Checking for duplicates",
    "3_way_matching": "Matching invoice against PO/GR",
    "classify": "Classifying expense category",
    "risk_analysis": "Assessing risk",
    "approval": "Routing for approval",
    "report_gen": "Generating report",
}


def save_upload(file: Optional[UploadFile], dest_dir: Path) -> Optional[str]:
    """Save an uploaded file to a temp dir, return its path (or None if no file given)."""
    if file is None:
        return None
    dest_path = dest_dir / file.filename
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return str(dest_path)


def sse_event(event: str, data: dict) -> str:
    """Format a single Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/process")
async def process_invoice(
    invoice: UploadFile = File(...),
    po: Optional[UploadFile] = File(None),
    gr: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
):
    """
    Upload invoice (+ optional PO/GR), stream each pipeline node's result as it completes.
    Requires a valid Bearer token — the resulting run is recorded under the calling user.

    Event stream shape:
      event: node_start   data: {"node": "...", "label": "..."}
      event: node_complete data: {"node": "...", "label": "...", "state_delta": {...}}
      event: done          data: {"status": "...", "report": {...} | null, "run_id": int}
      event: error         data: {"node": "...", "message": "..."}
    """
    run_id_str = str(uuid.uuid4())
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"invoice_{run_id_str}_"))

    try:
        invoice_path = save_upload(invoice, tmp_dir)
        po_path = save_upload(po, tmp_dir)
        gr_path = save_upload(gr, tmp_dir)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save uploaded files: {e}")

    initial_state = {
        "invoice_path": invoice_path,
        "po_path": po_path,
        "gr_path": gr_path,
        "user_id": user_id ,
    }

    async def event_generator():
        final_state = {}
        try:
            # .stream() yields {node_name: state_after_that_node} after each step
            for step in pipeline.stream(initial_state):
                for node_name, state_delta in step.items():
                    label = NODE_LABELS.get(node_name, node_name)
                    yield sse_event("node_start", {"node": node_name, "label": label})

                    final_state.update(state_delta)

                    yield sse_event("node_complete", {
                        "node": node_name,
                        "label": label,
                        "state_delta": jsonable(state_delta),
                    })

            final_status = final_state.get("status", "processed")
            final_report = jsonable(final_state.get("report"))

            # Persist this run under the calling user — this is the actual session history.
            db_run_id = insert_pipeline_run(
                user_id=user_id,
                invoice_id=final_state.get("invoice_id"),  # set this once insert_invoice() runs inside your graph and you thread its id back into state
                status=final_status,
                report=final_report,
            )

            yield sse_event("done", {
                "status": final_status,
                "report": final_report,
                "run_id": db_run_id,
            })

        except Exception as e:
            yield sse_event("error", {"message": str(e)})

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/runs/{run_id}/decide")
def decide_run(
    run_id: int,
    decision: str,
    note: str | None = None,
    user_id: int = Depends(get_current_user_id),
):
    if decision not in VALID_DECISIONS:
        raise HTTPException(status_code=400, detail=f"decision must be one of {VALID_DECISIONS}")

    updated = update_run_decision(run_id, user_id, decision, note or "")
    if not updated:
        raise HTTPException(status_code=404, detail="Run not found.")

    return {"run_id": run_id, "decision": decision, "note": note}

def jsonable(value):
    """Best-effort conversion of pipeline state values into JSON-safe primitives."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value



@app.get("/api/runs")
def get_my_runs(user_id: int = Depends(get_current_user_id), limit: int = 50):
    """Return THIS user's past pipeline runs only — the dashboard's session history."""
    return list_pipeline_runs(user_id, limit=limit)


@app.get("/api/runs/{run_id}")
def get_my_run(run_id: int, user_id: int = Depends(get_current_user_id)):
    """
    Return one past run's full report — scoped to the calling user.
    Returns 404 (not 403) if the run belongs to someone else, so we don'tp
    leak whether a given run_id exists at all to users who don't own it.
    """
    run = get_pipeline_run(user_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/invoices")
def list_invoices(user_id: int = Depends(get_current_user_id), limit: int = 50):
    """Returns all invoices belonging to this user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, invoice_number, vendor_name, invoice_date,
                  total_amount, tax_amount, currency, created_at
           FROM invoices
           WHERE user_id = %s
           ORDER BY created_at DESC
           LIMIT %s""",
        (user_id, limit)
    )
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, user_id: int = Depends(get_current_user_id)):
    """Returns one invoice with its line items, scoped to the requesting user."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM invoices WHERE id = %s AND user_id = %s",
        (invoice_id, user_id)
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found.")

    cols = [d[0] for d in cur.description]
    invoice = dict(zip(cols, row))

    cur.execute(
        "SELECT description, quantity, unit_price FROM invoice_line_items WHERE invoice_id = %s",
        (invoice_id,)
    )
    items = cur.fetchall()
    invoice["line_items"] = [
        {"description": d, "quantity": q, "unit_price": p}
        for d, q, p in items
    ]

    cur.close()
    conn.close()
    return invoice