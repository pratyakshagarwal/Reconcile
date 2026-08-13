---
title: Ledger
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

---

title: Reconcile
emoji: 🧾
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
-------------

# Reconcile

**Agentic Accounts Payable automation for validating, reconciling, and reviewing invoices before payment.**

Reconcile goes beyond invoice extraction. It combines multimodal document understanding, 3-way matching, anomaly detection, risk analysis, and human approval into a single workflow orchestrated with LangGraph.

**Live Demo:** https://reconcile-kqsc.vercel.app/

---

## The Problem

Extracting an invoice is only the first step.

Before an invoice can be paid, an AP team may need to verify it against a Purchase Order and Goods Receipt, identify discrepancies, assess vendor risk, and decide whether it should be approved.

Reconcile is built around that complete review process.

---

## What It Does

Given an invoice and its supporting documents, Reconcile:

1. Extracts structured data from invoices, POs, and GRs
2. Validates extracted fields
3. Detects duplicate invoices
4. Performs 3-way matching
5. Classifies expenses
6. Detects vendor anomalies
7. Scores invoice risk
8. Routes invoices through an approval workflow
9. Generates explanations for review decisions
10. Maintains an audit trail

The workflow streams execution progress to the frontend in real time, so users can see what the system is doing rather than waiting on a black-box response.

---

## Evaluation

Reconcile currently includes a manually curated benchmark of **15 invoices** covering extraction, 3-way matching, and mismatch detection.

| Metric                         |    Result |
| ------------------------------ | --------: |
| Overall evaluation score       | **0.964** |
| Extraction accuracy            | **1.000** |
| 3-way matching precision       | **1.000** |
| 3-way matching recall          | **1.000** |
| 3-way matching F1              | **1.000** |
| Mismatch detection (LLM judge) | **0.933** |

The evaluation combines deterministic comparisons against ground truth with an LLM judge for mismatch detection.

The benchmark is intentionally small at the moment. Expanding it requires manually creating invoice, PO, GR, and mismatch ground truth, while each processed invoice also requires multiple model calls. The benchmark will be expanded incrementally as more evaluation data is collected.

---

## Adaptive Vendor Anomaly Detection

Reconcile does not force every vendor through the same anomaly detector.

The system selects a strategy based on the available historical data:

* **Vendor-specific Isolation Forest** when sufficient history exists
* **Statistical profiling** for vendors with limited history
* **Global fallback rules** for new vendors

This allows anomaly detection to become more specific as vendor history accumulates.

---

## 3-Way Reconciliation

Invoices, Purchase Orders, and Goods Receipts can be inspected side-by-side.

Reconcile highlights discrepancies across:

* Quantity
* Unit price
* Totals
* Ordered vs received quantities
* Other document-level inconsistencies

This turns reconciliation from a manual document hunt into an explicit comparison.

---

## Human-in-the-Loop Review

Not every decision should be automated.

Flagged invoices can be reviewed and approved or rejected by a human. Reviewer decisions are stored and can be used as historical context for future risk assessment.

The system therefore treats automation as a decision-support layer rather than blindly approving invoices.

---

## Architecture

```text
                    Invoice / PO / GR
                           │
                           ▼
                    Document Extraction
                           │
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
              ┌────────────┴────────────┐
              ▼                         ▼
      Expense Classification     Anomaly Detection
                                        │
                                        ▼
                                  Risk Analysis
                                        │
                                        ▼
                                  Approval Flow
                                        │
                                        ▼
                                  Audit Report
```

The workflow is orchestrated with LangGraph and exposed through FastAPI. Execution events are streamed to the frontend using Server-Sent Events.

---

## Tech Stack

| Layer          | Technology                   |
| -------------- | ---------------------------- |
| Orchestration  | LangGraph                    |
| LLM            | Gemini                       |
| Backend        | FastAPI                      |
| Database       | Supabase PostgreSQL          |
| ML             | Scikit-learn                 |
| Streaming      | Server-Sent Events           |
| Authentication | JWT + bcrypt                 |
| Frontend       | HTML / CSS / JavaScript      |
| Deployment     | Vercel + Hugging Face Spaces |

---

## Local Development

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Configure environment variables:

```env
API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.5-flash
DB_URL=your_supabase_postgres_url
JWT_SECRET=your_secret
```

### Frontend

```bash
cd frontend
python -m http.server 8080
```

Then open:

```text
http://localhost:8080
```

---

## Current Limitations

Reconcile is a working prototype rather than a production AP platform.

Current limitations include:

* No ERP integrations
* Limited historical data for vendor anomaly models
* Rules-based expense classification
* Basic collaboration capabilities
* Limited policy configuration
* Small evaluation benchmark

---

## Roadmap

* ERP integrations
* Async workflow execution
* Expanded evaluation benchmarks
* Policy engine
* Analytics dashboards
* Multi-user collaboration
* Reviewer learning models
* Vendor relationship graphs

---

## Why Reconcile?

Most invoice automation stops at extraction.

Reconcile focuses on the part that comes after extraction: **figuring out whether an invoice should actually be paid.**

It combines document understanding, deterministic reconciliation, machine learning, LLM-based reasoning, and human review into one workflow.

**Demo:** https://reconcile-kqsc.vercel.app/
