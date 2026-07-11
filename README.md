---
title: Ledger
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Reconcile

Agentic Accounts Payable automation that goes beyond invoice extraction by validating documents, performing 3-way matching, detecting anomalies, assessing risk, and orchestrating approval workflows.

Built with **LangGraph, FastAPI, Gemini, Supabase, and a real-time streaming frontend.**

---

## Live Demo

Frontend:
https://reconcile-kqsc.vercel.app/

Demo Video:
https://github.com/user-attachments/assets/1da1f596-7577-42e4-a270-081f3ea4aa21

---

# What Reconcile Does

Reconcile simulates how AP teams review invoices before payment.

The workflow:

1. Extract document data
2. Validate invoice fields
3. Detect duplicates
4. Perform 3-way matching
5. Classify expenses
6. Detect vendor anomalies
7. Assess invoice risk
8. Route approvals
9. Generate audit explanations

Every stage runs inside a LangGraph workflow and streams live progress to the frontend using Server-Sent Events (SSE).

---

# What's New (v1.3)

### ML-based Vendor Anomaly Detection

Static anomaly rules have been replaced with adaptive anomaly detection.

The engine automatically chooses the best strategy:

- Vendor-specific Isolation Forest models when sufficient history exists
- Statistical profiling for vendors with limited history
- Global fallback rules for new vendors

This avoids applying a single detector to every vendor.

---

### Interactive 3-Way Comparison

Added a comparison interface that displays:

- Invoice
- Purchase Order
- Goods Receipt

side-by-side with highlighted mismatches for:

- Quantities
- Prices
- Totals

---

### Live Pipeline Logs

Each workflow node now streams its execution status to the UI, allowing users to monitor the pipeline in real time.

---

### Authentication Improvements

- Email validation using real email verification
- JWT authentication
- bcrypt password hashing

---

# Core Features

- Multimodal invoice, PO and GR extraction using Gemini
- Invoice validation
- Duplicate detection
- 3-way matching
- ML-based anomaly detection
- Adaptive risk scoring
- AI-generated audit explanations
- Human approval workflow
- Live streaming execution
- Complete audit trail

---

# Pipeline

```text
Invoice
   │
   ▼
Extraction
   │
Validation
   │
Duplicate Detection
   │
3-Way Matching
   │
Expense Classification
   │
Vendor Anomaly Detection
   │
Adaptive Risk Analysis
   │
Approval Routing
   │
Audit Report
```

---

# Tech Stack

| Layer | Tech |
|-------|------|
| Orchestration | LangGraph |
| LLM | Gemini |
| Backend | FastAPI |
| Database | Supabase PostgreSQL |
| Streaming | SSE |
| ML | Scikit-learn |
| Auth | JWT + bcrypt |
| Frontend | HTML / CSS / JavaScript |
| Deployment | Hugging Face Spaces + Vercel |

---

# Architecture

```text
Frontend (Vercel)
        │
        ▼
FastAPI
        │
        ├── LangGraph
        ├── Gemini
        ├── Matching Engine
        ├── Isolation Forest
        ├── Risk Engine
        ├── Approval Workflow
        └── SSE Streaming
                │
                ▼
        Supabase PostgreSQL
```

---

# Running Locally

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create a `.env`

```env
API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.5-flash
DB_URL=your_supabase_postgres_url
JWT_SECRET=your_secret
```

## Frontend

```bash
cd frontend
python -m http.server 8080
```

Open:

```
http://localhost:8080
```

---

# Current Limitations

- No ERP integrations
- Rules-based expense classification
- Limited historical data for anomaly models
- Synchronous workflow execution
- Basic collaboration workflow
- Limited policy configuration

---

# Future Roadmap

- ERP integrations
- Async workflow execution
- Better anomaly models
- Multi-user collaboration
- Analytics dashboards
- Policy engine
- Reviewer learning models
- Vendor relationship graphs

---

# Why This Project

Most invoice AI demos stop after OCR.

Reconcile focuses on what happens next:

- validation
- reconciliation
- anomaly detection
- risk assessment
- approval workflows
- auditability

The goal is to simulate how modern Accounts Payable teams actually review invoices before payment.
