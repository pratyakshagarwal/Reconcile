/* ============================================================
   REPORT VIEW — renders a finished pipeline run, plus the
   human review Approve/Reject buttons.
   Depends on: authFetch (auth.js), showView/els (main.js), loadHistory (history.js)
   ============================================================ */

let currentRunId = null; // tracks which run is currently shown in the report view
let currentThreadId = null; // Tracks the Thread Id for the run

function renderReport(report, status) {
  if (!report) {
    els.pipelineTitle.textContent = `Stopped — ${status || "unknown reason"}`;
    return;
  }

  document.getElementById("reportVendor").textContent = report.vendor_name || "Unknown vendor";
  document.getElementById("reportMeta").textContent = `Invoice ${report.invoice_number || "—"} · processed ${formatTimestamp(report.generated_at)}`;

  const decision = report.stages?.approval?.decision;
  const decisionEl = document.getElementById("reportDecision");
  if (decision === "auto_approved") {
    decisionEl.textContent = "Auto-approved";
    decisionEl.className = "report-decision approved";
  } else {
    decisionEl.textContent = `Needs review — ${report.stages?.approval?.approver || ""}`;
    decisionEl.className = "report-decision review";
  }

  document.getElementById("reportAmount").textContent = formatCurrency(report.total_amount, report.currency);
  document.getElementById("reportAmountSub").textContent = report.invoice_number || "—";

  const v = report.stages?.validation || {};
  setStatus("reportValidation", v.passed ? "Passed" : "Failed", v.passed ? "ok" : "flagged");
  fillList("reportValidationErrors", v.errors || []);

  const m = report.stages?.matching || {};
  setStatus("reportMatching", m.matched ? "Reconciled" : "Discrepancy found", m.matched ? "ok" : "flagged");
  fillList("reportMatchingIssues", (m.issues || []).map(i => `${i.field}: expected ${i.expected}, got ${i.actual}`));

  const c = report.stages?.classification || {};
  setStatus("reportClassification", c.primary_category || "Uncategorized", "ok");
  const tagsEl = document.getElementById("reportClassBreakdown");
  tagsEl.innerHTML = "";
  Object.entries(c.category_breakdown || {}).forEach(([cat, count]) => {
    const tag = document.createElement("span");
    tag.className = "tag-cat";
    tag.textContent = `${cat} × ${count}`;
    tagsEl.appendChild(tag);
  });

  const r = report.stages?.risk || {};
  setStatus("reportRisk", `${capitalize(r.tier || "—")} (score ${r.score ?? "—"})`, r.tier === "high" ? "flagged" : r.tier === "medium" ? "warn" : "ok");
  fillList("reportRiskReasons", r.reasons || []);

  // explanation
  const explanationSection = document.getElementById("reportExplanationSection");
  const explanationText = document.getElementById("reportExplanation");

  if (report.explanation) {
    explanationSection.hidden = false;
    explanationText.textContent = report.explanation;
  } else {
    explanationSection.hidden = true;
  }

  const a = report.stages?.approval || {};
  setStatus("reportApproval", a.decision === "auto_approved" ? "Auto-approved" : `Sent to ${a.approver || "review"}`, a.decision === "auto_approved" ? "ok" : "warn");

  setupDecisionButtons(report, currentRunId);

  showView("report");
  loadHistory(); // refresh sidebar so the just-completed run appears
}

function setStatus(id, text, cls) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = `report-status ${cls}`;
}

function fillList(id, items) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  if (!items.length) {
    el.innerHTML = `<li style="color: var(--ink-faint);">None</li>`;
    return;
  }
  items.forEach(item => {
    const li = document.createElement("li");
    li.textContent = item;
    el.appendChild(li);
  });
}

/* ============================================================
   HUMAN REVIEW — Approve / Reject buttons
   Only shown when the pipeline routed this run to "needs review".
   ============================================================ */
function setupDecisionButtons(report, runId) {
  const actions = document.getElementById("decisionActions");
  const resultText = document.getElementById("decisionResult");
  const approveBtn = document.getElementById("approveBtn");
  const rejectBtn = document.getElementById("rejectBtn");

   if (!runId || !currentThreadId) {
      resultEl.textContent = `Error: missing run_id (${runId}) or thread_id (${currentThreadId})`;
      return;
    }
  resultText.textContent = "";
  document.getElementById("reviewerNote").value = ""; 

  const needsReview = report?.stages?.approval?.decision !== "auto_approved";
  actions.hidden = !needsReview || !runId;

  approveBtn.onclick = () => submitDecision(runId, "approved", actions, resultText);
  rejectBtn.onclick = () => submitDecision(runId, "rejected", actions, resultText);
}

async function submitDecision(runId, decision, actionsEl, resultEl) {
  const noteEl = document.getElementById("reviewerNote");
  const note = noteEl.value.trim() || null;

  try {
    const params = new URLSearchParams({
      decision: decision,
      thread_id: currentThreadId,
    });

    if (note) {
      params.set("note", note);
    }

    const res = await authFetch(
      `/api/runs/${runId}/resume?${params.toString()}`,
      { method: "POST" }
    );

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Could not resume pipeline.");
    }

    const data = await res.json();

    actionsEl.hidden = true;
    resultEl.textContent = `Decision recorded: ${decision}`;

    currentRunId = data.run_id;

    renderReport(data.report, data.status);
    loadHistory();

  } catch (err) {
    resultEl.textContent = `Error: ${err.message}`;
  }
}