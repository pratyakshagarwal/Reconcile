title	Ledger
emoji	🚀
colorFrom	blue
colorTo	indigo
sdk	docker
app_port	7860
pinned	false

# Reconcile
Agentic Accounts Payable automation for validating, reconciling, and reviewing invoices before payment.

Reconcile goes beyond invoice extraction. It combines multimodal document understanding, 3-way matching, anomaly detection, risk analysis, and human approval into a single workflow orchestrated with LangGraph.

Live Demo: https://reconcile-kqsc.vercel.app/

---

## What's New in Reconcile 1.4

Reconcile 1.4 is a structural upgrade focused on performance, state persistence, and proper human-in-the-loop execution.

**Parallel Document Extraction**
The single sequential extraction node has been replaced with a LangGraph fan-out pattern. Invoice, Purchase Order, and Goods Receipt now extract concurrently as independent nodes, merging back into shared state before validation. Extraction wall time dropped ~45% on average across test sets — the run is now gated by the slowest document, not the sum of all three.

**Persistent Checkpointing**
Integrated LangGraph's PostgresSaver against Supabase PostgreSQL. Every node transition is checkpointed — full graph state is serialized after each step. Server restarts no longer lose in-progress runs. Every run has a persistent `thread_id` tied to its checkpoint history and can be resumed from any prior state.

**Human-in-the-Loop via Interrupt**
The approval node now uses LangGraph's `interrupt()` primitive. When an invoice is flagged for review, the graph suspends at that node, persists state to the checkpoint store, and waits. The reviewer approves or rejects via the UI, and the graph resumes from the exact checkpoint — continuing into report generation with the human decision baked into state. This is a proper resumable workflow, not a re-run.

---

## The Problem
Extracting an invoice is only the first step.

Before an invoice can be paid, an AP team may need to verify it against a Purchase Order and Goods Receipt, identify discrepancies, assess vendor risk, and decide whether it should be approved.

Reconcile is built around that complete review process.

---

## What It Does
Given an invoice and its supporting documents, Reconcile:

- Extracts structured data from invoices, POs, and GRs — in parallel
- Validates extracted fields
- Detects duplicate invoices
- Performs 3-way matching
- Classifies expenses
- Detects vendor anomalies
- Scores invoice risk
- Routes invoices through an approval workflow with human-in-the-loop gates
- Generates explanations for review decisions
- Maintains a persistent audit trail across server restarts

The workflow streams execution progress to the frontend in real time, so users can see what the system is doing rather than waiting on a black-box response.

---

## Evaluation
Reconcile currently includes a manually curated benchmark of 15 invoices covering extraction, 3-way matching, and mismatch detection.

| Metric | Result |
|---|---|
| Overall evaluation score | 0.964 |
| Extraction accuracy | 1.000 |
| 3-way matching precision | 1.000 |
| 3-way matching recall | 1.000 |
| 3-way matching F1 | 1.000 |
| Mismatch detection (LLM judge) | 0.933 |

The evaluation combines deterministic comparisons against ground truth with an LLM judge for mismatch detection.

The benchmark is intentionally small at the moment. Expanding it requires manually creating invoice, PO, GR, and mismatch ground truth, while each processed invoice also requires multiple model calls. The benchmark will be expanded incrementally as more evaluation data is collected.

---

## Adaptive Vendor Anomaly Detection
Reconcile does not force every vendor through the same anomaly detector.

The system selects a strategy based on the available historical data:

- Vendor-specific Isolation Forest when sufficient history exists
- Statistical profiling for vendors with limited history
- Global fallback rules for new vendors

This allows anomaly detection to become more specific as vendor history accumulates.

---

## 3-Way Reconciliation
Invoices, Purchase Orders, and Goods Receipts can be inspected side-by-side.

Reconcile highlights discrepancies across:

- Quantity
- Unit price
- Totals
- Ordered vs received quantities
- Other document-level inconsistencies

This turns reconciliation from a manual document hunt into an explicit comparison.

---

## Human-in-the-Loop Review
Not every decision should be automated.

In Reconcile 1.4, the human review gate is implemented using LangGraph's `interrupt()` primitive. When the approval node determines an invoice needs review:

1. The graph suspends execution at that node
2. Full pipeline state is persisted to PostgreSQL via `PostgresSaver`
3. The frontend receives an `interrupted` SSE event with the `run_id` and `thread_id`
4. The reviewer sees the pipeline paused mid-run with Approve / Reject controls
5. On decision, `POST /api/runs/{run_id}/resume` is called with the decision and thread_id
6. LangGraph resumes the graph from the checkpoint — report generation runs with the human decision in state

Reviewer decisions are stored and can be used as historical context for future risk assessment. The system treats automation as a decision-support layer rather than blindly approving invoices.

---

## Architecture

```
             Invoice / PO / GR
                    │
                    ▼
         ┌──────────┴──────────┐
         ▼          ▼          ▼
   Extract       Extract     Extract
   Invoice        PO           GR
         └──────────┬──────────┘
                    │ (parallel fan-out, merge on completion)
                    ▼
                Validation
                    │
                    ▼
          Duplicate Detection
                    │
                    ▼
            3-Way Matching
                    │
                    ▼
        ┌───────────┴───────────┐
        ▼                       ▼
Expense Classification    Anomaly Detection
                                │
                                ▼
                          Risk Analysis
                                │
                                ▼
                    Approval Flow ── ⏸ interrupt (needs review)
                                │        │
                                │    Human Decision
                                │        │
                                └────────┘
                                │
                                ▼
                          Audit Report
```

The workflow is orchestrated with LangGraph and exposed through FastAPI. Execution events are streamed to the frontend using Server-Sent Events. Graph state is checkpointed to PostgreSQL after every node transition.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph |
| State Persistence | LangGraph PostgresSaver + Supabase |
| LLM | Gemini 2.5 Flash |
| Backend | FastAPI |
| Database | Supabase PostgreSQL |
| ML | Scikit-learn |
| Streaming | Server-Sent Events |
| Authentication | JWT + bcrypt |
| Frontend | HTML / CSS / JavaScript |
| Deployment | Vercel + Hugging Face Spaces |

---

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Configure environment variables:
```
API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.5-flash
DB_URL=your_supabase_postgres_url
JWT_SECRET=your_secret
```

### Frontend
```bash
cd frontend
python -m http.server 5500
```

Then open: http://localhost:5500

---

## Current Limitations
Reconcile is a working prototype rather than a production AP platform.

Current limitations include:

- No ERP integrations
- Limited historical data for vendor anomaly models
- Rules-based expense classification
- Basic collaboration capabilities
- Limited policy configuration
- Small evaluation benchmark

---

## Roadmap

- ERP integrations
- Async workflow execution
- Parallel classification and anomaly detection
- Expanded evaluation benchmarks
- Policy engine
- Analytics dashboards
- Multi-user collaboration
- Reviewer learning models
- Vendor relationship graphs

---

## Why Reconcile?
Most invoice automation stops at extraction.

Reconcile focuses on the part that comes after extraction: figuring out whether an invoice should actually be paid.

It combines document understanding, deterministic reconciliation, machine learning, LLM-based reasoning, and human review into one stateful, resumable workflow.

Demo: https://reconcile-kqsc.vercel.app/
