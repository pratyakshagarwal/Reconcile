from typing import TypedDict, Optional, List, Dict, Annotated
from langgraph.graph import StateGraph, END, START
from langgraph.types import Send
from langgraph.types import interrupt

from backend.app.extracter import extract, extract_invoice, extract_po, extract_gr
from backend.app.validator import validate_invoice
from backend.app.db import (
    check_duplicate,check_duplicate_gr, check_duplicate_po, 
    insert_invoice, insert_gr, insert_po
)
from backend.app.matching import match_invoice, MatchResult
from backend.app.classify import classify_invoice
from backend.app.risk_analysis import assess_risk
from backend.app.approval import route_approval
from backend.app.report import generate_report
from backend.app.helper import extract_confidences, unwrap_confident_fields
from backend.app.anomaly_detection.train import train_all
from backend.app.anomaly_detection.predict import load_models, detect_anomaly
from backend.app.anomaly_detection.data_handling import build_features
import pandas as pd

def startup_train():
    try:
        from backend.app.anomaly_detection.data_handling import get_invoice_sample
        df = get_invoice_sample()
        if len(df) >= 5:
            train_all(df)
            print(f"Anomaly models trained on {len(df)} invoices.")
        else:
            print("Not enough invoice data to train anomaly models yet.")
    except Exception as e:
        print(f"Anomaly model training skipped: {e}")

startup_train()
_anomaly_models = load_models()  # load once into memory, reused per request

def merge_optional(a, b):
    """Keep whichever value is not None."""
    return b if b is not None else a
class PipelineState(TypedDict):
    invoice_path: str
    po_path: Optional[str]
    gr_path: Optional[str]
    invoice: Annotated[Optional[dict], merge_optional]
    invoice_id: Optional[int]
    po: Annotated[Optional[dict], merge_optional]
    gr: Annotated[Optional[dict], merge_optional]
    user_id: Optional[int]
    invoice_confidences: Annotated[Optional[dict], merge_optional]
    is_valid: Optional[bool]
    validation_errors: Optional[list]
    is_duplicate: Optional[bool]
    match_result: Optional[dict]
    classification: Optional[dict]
    anomaly_result: Optional[dict] 
    risk: Optional[dict]
    approval: Optional[dict]
    report: Optional[dict]
    status: Optional[str]  # used to short-circuit on duplicate/invalid
    warnings: List[Dict]
    thread_id: Optional[str]         # stored so fr

def extract_Invoice(state: PipelineState) -> PipelineState:
    invoice = extract_invoice(state["invoice_path"])
    return {
        "invoice": unwrap_confident_fields(invoice.model_dump()) if invoice else None,
        "invoice_confidences": extract_confidences(invoice.model_dump()) if invoice else {},
    }

def extract_PurchaseOrder(state: PipelineState) -> PipelineState:
    if not state.get("po_path"):
        return {"po": None}
    po = extract_po(state["po_path"])
    return {"po": po.model_dump() if po else None}

def extract_GoodReceipt(state: PipelineState) -> PipelineState:
    if not state.get("gr_path"):
        return {"gr": None}
    gr = extract_gr(state["gr_path"])
    return {"gr": gr.model_dump() if gr else None}

def dispatch_extraction(state: PipelineState) -> list:
    """Fan out to parallel extraction nodes."""
    tasks = [Send("extract_Invoice", state)]  # pass full state so nodes can read their paths

    if state.get("po_path"):
        tasks.append(Send("extract_PurchaseOrder", state))

    if state.get("gr_path"):
        tasks.append(Send("extract_GoodReceipt", state))

    return tasks

def validation_node(state: PipelineState) -> PipelineState:
    is_valid, errors = validate_invoice(state["invoice"])
    if not is_valid:
        return {**state, "is_valid": is_valid, "validation_errors": errors, "status": "rejected_invalid"}
    return {**state, "is_valid": is_valid, "validation_errors": errors}


def duplicate_node(state: PipelineState) -> PipelineState:
    if check_duplicate(state["invoice"]):
        return {
            **state,
            "is_duplicate": True,
            "status": "rejected_duplicate"
        }
    
    warnings = []
    checks = [
        (
            check_duplicate_po,
            insert_po,
            state["po"],
            "DuplicatePurchaseOrder",
            "purchase order with same no exists in database"
        ),
        (
            check_duplicate_gr,
            insert_gr,
            state["gr"],
            "DuplicateGoodsReceipt",
            "receipt with same no exists in database"
        ),
    ]

    for check_fn, insert_fn, data, key, msg in checks:
        if check_fn(data):
            warnings.append({key: msg})
        else:
            insert_fn(data)

    invoice_id = insert_invoice(state["invoice"], state['user_id'])

    return {
        **state,
        "is_duplicate": False,
        "warnings":warnings,
        "invoice_id": invoice_id
    }


def matching_node(state: PipelineState) -> PipelineState:
    if not state.get("po") or not state.get("gr"):
        return {**state, "match_result": {"matched": False, "issues": [{"field": "po/gr", "expected": "present", "actual": "missing", "severity": "warning"}]}}
    result = match_invoice(state["invoice"], state["po"], state["gr"])
    return {**state, "match_result": result.model_dump()}


def classification_node(state: PipelineState) -> PipelineState:
    return {**state, "classification": classify_invoice(state["invoice"])}

def anomaly_node(state: PipelineState) -> PipelineState:
    if not state.get("invoice"):
        return {**state, "anomaly_result": None}

    result = detect_anomaly(
        models=_anomaly_models,
        invoice=state["invoice"],
        user_id=state.get("user_id"),
    )
    return {**state, "anomaly_result": result}

def risk_node(state: PipelineState) -> PipelineState:
    match_result = MatchResult(**state["match_result"])
    anomaly = state.get("anomaly_result") or {}
    risk = assess_risk(state["invoice"], match_result, state['invoice_confidences'], anomaly)
    return {**state, "risk": risk}

def approval_node(state: PipelineState) -> PipelineState:
    match_result = MatchResult(**state["match_result"])
    risk = state.get("risk", {})

    approval = route_approval(
        state["invoice"],
        risk,
        match_result
    )

    approval["source"] = "automated"

    print("APPROVAL:", approval)

    if approval["decision"] == "needs_review":

        human_input = interrupt({
            "message": "Rejected by Reconcile — Pending Human Review",
            "approval": approval
        })

        decision = (
            human_input.get("decision")
            if isinstance(human_input, dict)
            else human_input
        )

        note = (
            human_input.get("note", "")
            if isinstance(human_input, dict)
            else ""
        )

        return {
            **state,
            "approval": {
                "decision": decision,
                "approver": "human_reviewer",
                "note": note,
                "source": "human",
            }
        }

    return {
        **state,
        "approval": approval
    }

def report_node(state: PipelineState) -> PipelineState:
    report = generate_report(
        invoice=state["invoice"],
        validation=(state["is_valid"], state["validation_errors"]),
        match_result=MatchResult(**state["match_result"]),
        classification=state["classification"],
        risk=state["risk"],
        approval=state["approval"],
        warnings=state['warnings']
    )
    return {**state, "report": report, "status": state.get("status", "processed")}

# Conditional routing: stop early if invalid or duplicate
def route_after_validation(state: PipelineState) -> str:
    return "duplicate_detect" if state["is_valid"] else END


def route_after_duplicate(state: PipelineState) -> str:
    return "3_way_matching" if not state["is_duplicate"] else END


nodes = [
    ("extract_Invoice", extract_Invoice),
    ("extract_PurchaseOrder", extract_PurchaseOrder),
    ("extract_GoodReceipt", extract_GoodReceipt),
    ("validation", validation_node),
    ("duplicate_detect", duplicate_node),
    ("3_way_matching", matching_node),
    ("classify", classification_node),
    ("anomaly_detect", anomaly_node),
    ("risk_analysis", risk_node),
    ("approval", approval_node),
    ("report_gen", report_node),
]

paths = [
    (START, dispatch_extraction, "fan_out"),

    ("extract_Invoice", "validation"),
    ("extract_PurchaseOrder", "validation"),
    ("extract_GoodReceipt", "validation"),

    ("validation", route_after_validation, "conditional_routing"),
    ("duplicate_detect", route_after_duplicate, "conditional_routing"),
    ("3_way_matching", "classify"),
    ("classify", "anomaly_detect"),
    ("anomaly_detect", "risk_analysis"),
    ("risk_analysis", "approval"),
    ("approval", "report_gen"),
    ("report_gen", END),
]

def create_graph(nodes, paths, checkpointer=None):
    graph = StateGraph(PipelineState)

    for name, fn in nodes:
        graph.add_node(name, fn)

    for path in paths:
        if len(path) == 2:
            strt, dstn = path
            graph.add_edge(strt, dstn)
        else:
            strt, route_fn, label = path
            if label == "fan_out":
                # Parallel fan-out — dispatch_extraction returns list of Send objects
                graph.add_conditional_edges(
                    strt,
                    route_fn,
                    ["extract_Invoice", "extract_PurchaseOrder", "extract_GoodReceipt"]
                )
            else:
                # Normal conditional routing
                graph.add_conditional_edges(strt, route_fn)

    pipeline = graph.compile(
        checkpointer=checkpointer)
    return pipeline


if __name__ == '__main__':
    pipeline = create_graph(nodes, paths)
    result = pipeline.invoke({
        "invoice_path": "data\invoices\invoice-sample.pdf",
        "po_path": "data\po\purchase-order-PO-4872-25.pdf",
        "gr_path": "data\gud_recipt\goods-receipt-note-GRN-4872-25.pdf",
    })

    if "report" in result:
        print(result["report"])
    else:
        print(f"Pipeline stopped early — status: {result.get('status')}")
        if result.get("status") == "rejected_invalid":
            print("Validation errors:", result.get("validation_errors"))
        elif result.get("status") == "rejected_duplicate":
            print("This invoice already exists in the database.")
    print(result)