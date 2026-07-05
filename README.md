---

title: Ledger
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Ledger Backend

AI-powered finance backend.

-------------

# Reconcile

Agentic accounts-payable automation for invoice extraction, validation, 3-way matching, anomaly detection, adaptive risk scoring, and approval orchestration.

Built with LangGraph, FastAPI, Gemini, Supabase, and a live streaming frontend.

---

# Live Demo

Frontend: https://reconcile-kqsc.vercel.app/

### Demo Video

[Watch the demo](https://github.com/user-attachments/assets/1da1f596-7577-42e4-a270-081f3ea4aa21)

---

# What Reconcile Does

Reconcile simulates how real AP teams verify invoices before payment.

The system processes invoices through a multi-agent workflow that:

1. Extracts structured data from invoices, purchase orders, and goods receipts
2. Validates invoice integrity
3. Detects duplicates
4. Performs 3-way matching
5. Classifies expenses
6. Scores invoice risk
7. Detects vendor-level anomalies
8. Routes invoices through approval workflows
9. Generates human-readable audit explanations
10. Learns from reviewer decisions over time
11. Maintains a complete audit trail

Every stage runs inside a LangGraph workflow and streams live updates to the frontend via Server-Sent Events (SSE).

The system is designed around operational auditability rather than a single opaque AI response.

---

# v1.2 Improvements

Reconcile v1.2 focuses on adaptive review workflows and human feedback loops.

### Reviewer Feedback Learning Loop

Reviewer decisions now persist vendor-level approval history.

When flagged invoices are approved or rejected, the system stores that decision and incorporates it into future risk evaluations.

This allows the risk engine to adapt over time:

* Vendors with strong approval histories receive lower downstream risk weighting
* Vendors with repeated rejections are escalated more aggressively
* Human review decisions compound instead of disappearing after each workflow run

This is a lightweight implementation of the kind of reviewer-feedback systems used in production AP platforms.

---

### Redesigned Review Workflow UI

The review dashboard now supports:

* Reviewer notes alongside approve/reject decisions
* Dedicated invoice review pages
* Clear workflow segmentation with:

  * Pending
  * Approved
  * Declined

instead of a single flat review queue.

---

### Invoice Management View

Users can now:

* Browse all processed invoices
* Inspect completed workflow outputs
* Download invoice results as:

  * JSON
  * CSV

---

### Reliability Improvements

Several backend endpoint and database edge-case bugs were fixed to reduce silent workflow failures and improve pipeline stability.

---

# Pipeline

```text
Upload Invoice (+ optional PO / GR)
        │
        ▼
1. Extraction
        │
        ▼
2. Validation
        │
        ▼
3. Duplicate Detection
        │
        ▼
4. 3-Way Matching
        │
        ▼
5. Classification
        │
        ▼
6. Adaptive Risk Scoring
   ├── Extraction Confidence
   ├── Validation Errors
   ├── Matching Failures
   ├── Duplicate Signals
   ├── Vendor Anomalies
   └── Reviewer Feedback History
        │
        ▼
7. Approval Routing
        │
        ▼
8. Audit Report + AI Explanation
        │
        ▼
   ───────────────────────────────
   Human Review Dashboard
   Approve / Reject / Add Notes
   Decisions persist into future
   vendor risk evaluations
```

---

# Core Features

## Structured Multimodal Extraction

Uses Gemini multimodal extraction with schema-constrained outputs for:

* Invoices
* Purchase Orders
* Goods Receipts

---

## 3-Way Matching

Compares:

* Invoice
* Purchase Order
* Goods Receipt

line-by-line with configurable tolerances and severity-tagged discrepancies.

---

## Adaptive Risk Analysis

Risk scoring incorporates:

* Extraction confidence
* Matching failures
* Duplicate signals
* Vendor anomalies
* Validation errors
* Historical reviewer decisions

---

## Vendor-Aware Anomaly Detection

Detects abnormal vendor behavior using:

* Historical invoice patterns
* Amount deviations
* Vendor review history
* Repeated rejection patterns

---

## Human Review Workflow

Flagged invoices route into a review dashboard where reviewers can:

* Approve invoices
* Reject invoices
* Leave reviewer notes
* Inspect prior decisions

---

## AI Audit Explanations

Transforms raw risk signals into concise audit-readable explanations for AP reviewers.

Example:

> "Flagged because the invoice amount is significantly higher than historical vendor averages and multiple billed items are missing from the goods receipt."

---

## Live Streaming Pipeline

Each workflow node streams results in real time to the frontend using SSE.

---

## Auditability

Every pipeline stage produces inspectable structured outputs instead of opaque model responses.

---

# Tech Stack

| Layer            | Tech                         |
| ---------------- | ---------------------------- |
| Orchestration    | LangGraph                    |
| LLM / Extraction | Gemini + LangChain           |
| Backend          | FastAPI                      |
| Streaming        | Server-Sent Events           |
| Database         | Supabase (PostgreSQL)        |
| Auth             | JWT + bcrypt                 |
| Frontend         | HTML / CSS / JavaScript      |
| Deployment       | Hugging Face Spaces + Vercel |

---

# Architecture

```text
Frontend (Vercel)
        │
        ▼
FastAPI Backend (HF Spaces)
        │
        ├── LangGraph Workflow
        ├── Gemini Extraction
        ├── Matching Engine
        ├── Adaptive Risk Engine
        ├── Vendor Feedback History
        ├── AI Explanation Layer
        └── SSE Streaming
                │
                ▼
        Supabase PostgreSQL
```

---

# Project Structure

```text
backend/
  app/
    main.py
    agent.py
    auth.py
    auth_db.py
    db.py
    extracter.py
    validator.py
    matching.py
    classify.py
    risk_analysis.py
    approval.py
    report.py
    anomaly_exp.py

frontend/
  index.html
  style.css
  js/
```

---

# Running Locally

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create a `.env` file:

```env
API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.5-flash
DB_URL=your_supabase_postgres_url
JWT_SECRET=your_secret
```

---

## Frontend

```bash
cd frontend
python -m http.server 8080
```

Open:

```text
http://localhost:8080
```

---

# Current Limitations

Reconcile is still a portfolio/research-style system rather than a production AP platform.

Current limitations include:

* Rules-based expense classification
* Limited historical anomaly baselines
* No ERP integrations
* Synchronous workflow execution
* Limited reviewer collaboration tooling
* Matching optimized for relatively structured invoices
* Reviewer feedback learning is heuristic rather than model-trained
* Limited policy configurability

---

# Why This Project Exists

Most invoice AI demos stop at OCR extraction.

The harder operational problem is determining whether an invoice should actually be paid.

Reconcile focuses on the workflow layer:

* validation
* reconciliation
* anomaly detection
* auditability
* escalation
* approval orchestration
* reviewer feedback loops

instead of treating invoice processing as a single extraction problem.

---

# Future Improvements

* Async/concurrent workflow execution
* Model-trained reviewer feedback learning
* Adaptive approval policies
* ERP integrations
* Multi-user review collaboration
* Better anomaly baselines
* Evaluation + observability tooling
* Advanced handling for noisy enterprise scans
* Analytics dashboards
* Policy-based workflow configuration
* Vendor graph analysis
* Continuous reviewer calibration

