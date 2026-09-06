/* ============================================================
   PIPELINE — upload form, SSE stream consumption, live stage list
   Depends on: authFetch (auth.js), showView/els (main.js), renderReport (report.js)
   ============================================================ */

let extractionCompletedCount = 0;
const NODE_SEQUENCE = [
  { key: "extraction", label: "Extracting document fields" },
  { key: "validation", label: "Validating extracted data" },
  { key: "duplicate_detect", label: "Checking for duplicates" },
  { key: "3_way_matching", label: "Matching invoice against PO/GR" },
  { key: "classify", label: "Classifying expense category" },
  {key: "anomaly_detect",  label: "Detecting Invoice Based on History"},
  { key: "risk_analysis", label: "Assessing risk" },
  { key: "approval", label: "Routing for approval" },
  { key: "report_gen", label: "Generating report" },
];

/* ============================================================
   DROPZONE FILE LABELS
   ============================================================ */
document.querySelectorAll(".dropzone input[type=file]").forEach(input => {
  input.addEventListener("change", () => {
    const dz = input.closest(".dropzone");
    const nameEl = dz.querySelector(".dz-filename");
    if (input.files.length) {
      dz.classList.add("filled");
      nameEl.textContent = input.files[0].name;
    } else {
      dz.classList.remove("filled");
      nameEl.textContent = "";
    }
  });
});

/* ============================================================
   UPLOAD + STREAM PIPELINE
   ============================================================ */
els.uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const invoiceFile = document.getElementById("invoiceFile").files[0];
  const poFile = document.getElementById("poFile").files[0];
  const grFile = document.getElementById("grFile").files[0];

  if (!invoiceFile) {
    els.formNote.textContent = "An invoice file is required.";
    return;
  }

  els.formNote.textContent = "";
  els.submitBtn.disabled = true;
  els.submitBtn.textContent = "Starting…";

  const formData = new FormData();
  formData.append("invoice", invoiceFile);
  if (poFile) formData.append("po", poFile);
  if (grFile) formData.append("gr", grFile);

  buildStageList();
  els.pipelineTitle.textContent = `Processing ${invoiceFile.name}`;
  showView("pipeline");

  try {
    const response = await authFetch("/api/process", {
      method: "POST",
      body: formData,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Server responded ${response.status}`);
    }

    await consumeStream(response.body);

  } catch (err) {
    markPipelineError(err.message);
  } finally {
    els.submitBtn.disabled = false;
    els.submitBtn.textContent = "Run pipeline";
  }
});

function buildStageList() {
  els.stageList.innerHTML = "";
  NODE_SEQUENCE.forEach((node, i) => {
    const row = document.createElement("div");
    row.className = "stage-row";
    row.id = `stage-${node.key}`;
    row.innerHTML = `
      <div class="stage-row-main">
        <span class="stage-num">${String(i + 1).padStart(2, "0")}</span>
        <span class="stage-stamp">✓</span>
        <span class="stage-body">
          <span class="stage-label">${node.label}</span>
          <span class="stage-detail"></span>
        </span>
      </div>
      <div class="stage-logs" hidden></div>
    `;
    els.stageList.appendChild(row);
  });
}

function markPipelineError(message) {
  els.pipelineTitle.textContent = "Pipeline stopped";
  const note = document.createElement("p");
  note.className = "view-sub";
  note.style.color = "var(--rust)";
  note.textContent = message;
  els.stageList.before(note);
}

/* Parses a fetch ReadableStream as Server-Sent Events and dispatches each. */
async function consumeStream(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop(); // last chunk may be incomplete — keep for next read

    for (const raw of events) {
      if (!raw.trim()) continue;
      const eventMatch = raw.match(/^event: (.+)$/m);
      const dataMatch = raw.match(/^data: (.+)$/m);
      if (!eventMatch || !dataMatch) continue;

      const eventName = eventMatch[1].trim();
      const data = JSON.parse(dataMatch[1]);
      handleStreamEvent(eventName, data);
    }
  }
}

function handleStreamEvent(eventName, data) {
  // Remap the three fan-out extraction nodes to the single "extraction" UI row
  const EXTRACTION_NODES = ["extract_Invoice", "extract_PurchaseOrder", "extract_GoodReceipt"];

  if (EXTRACTION_NODES.includes(data.node)) {
    if (eventName === "node_start") {
      // Only activate the row on the first one to fire
      const row = document.getElementById("stage-extraction");
      if (row) row.classList.add("active");
    }
    if (eventName === "node_complete") {
      extractionCompletedCount++;
      if (extractionCompletedCount >= 3) {
        // All three done — mark the row complete
        const row = document.getElementById("stage-extraction");
        if (row) {
          row.classList.remove("active");
          row.classList.add("complete");
          const detail = row.querySelector(".stage-detail");
          if (detail) detail.textContent = "invoice, PO and GR extracted";
        }
        extractionCompletedCount = 0; // reset for next run
      }
    }
    return; // don't fall through to the normal handler
  }
  if (eventName === "node_start") {
    const row = document.getElementById(`stage-${data.node}`);
    if (row) row.classList.add("active");
  }

  if (eventName === "node_complete") {
    const row = document.getElementById(`stage-${data.node}`);
    if (!row) return;
    row.classList.remove("active");
    row.classList.add("complete");

    const detail = row.querySelector(".stage-detail");
    const summary = summarizeStageDelta(data.node, data.state_delta);
    if (summary.flagged) {
      row.classList.add("flagged");
      detail.classList.add("flagged-text");
    }
    detail.textContent = summary.text;

    // Attach expandable logs if this node produced any
    const logs = extractStageLogs(data.node, data.state_delta);
    if (logs.length) {
      attachStageLogs(row, logs);
    }
  }
  if (eventName === "interrupted") {
    currentRunId    = data.run_id;
    currentThreadId = data.thread_id;

    // Mark approval row as "waiting"
    const approvalRow = document.getElementById("stage-approval");
    if (approvalRow) {
      approvalRow.classList.remove("active");
      approvalRow.classList.add("interrupted");
      const detail = approvalRow.querySelector(".stage-detail");
      if (detail) detail.textContent = "waiting for your decision";
    }

    // Update header so it doesn't look frozen
    els.pipelineTitle.textContent = "Review required";
    document.getElementById("pipelineSub").textContent =
      "The pipeline has paused for human review. Approve or reject to continue.";

    // Show buttons
    const actions  = document.getElementById("decisionActions");
    const resultEl = document.getElementById("decisionResult");
    const approveBtn = document.getElementById("approveBtn");
    const rejectBtn  = document.getElementById("rejectBtn");

    actions.hidden = false;

    approveBtn.onclick = () => submitDecision(currentRunId, "approved", actions, resultEl);
    rejectBtn.onclick  = () => submitDecision(currentRunId, "rejected", actions, resultEl);

    return;
  }
  if (eventName === "done") {
    currentRunId = data.run_id;
    setTimeout(() => renderReport(data.report, data.status), 500);
  }

  if (eventName === "error") {
    markPipelineError(`Error: ${data.message}`);
  }
}

function extractStageLogs(node, delta) {
  if (!delta) return [];
  // Pull logs from wherever this node stores them in state
  if (node === "anomaly_detect") {
    return delta.anomaly_result?.logs || [];
  }
  if (node === "risk_analysis") {
    return delta.risk?.reasons || [];
  }
  if (node === "3_way_matching") {
    return (delta.match_result?.issues || []).map(
      i => `${i.field}: expected ${i.expected}, got ${i.actual} [${i.severity}]`
    );
  }
  return [];
}

function attachStageLogs(row, logs) {
  const logsDiv = row.querySelector(".stage-logs");
  if (!logsDiv) return;

  logs.forEach(log => {
    const p = document.createElement("p");
    p.className = "stage-log-line";
    p.textContent = log;
    logsDiv.appendChild(p);
  });

  logsDiv.hidden = false; // show once logs exist
  row.classList.add("has-logs");

  // Click the main row area to toggle logs open/closed
  row.querySelector(".stage-row-main").addEventListener("click", () => {
    logsDiv.hidden = !logsDiv.hidden;
    row.classList.toggle("logs-open", !logsDiv.hidden);
  });
}

/* Produces a one-line human summary for each node's result, shown under the stage label. */
function summarizeStageDelta(node, delta) {
  if (!delta) return { text: "", flagged: false };

  switch (node) {
    case "extraction":
      return { text: delta.invoice ? `${delta.invoice.invoice_number || "unknown"} — ${delta.invoice.vendor_name || "unknown vendor"}` : "extracted", flagged: false };
    case "validation":
      return delta.is_valid
        ? { text: "all required fields present", flagged: false }
        : { text: `${(delta.validation_errors || []).length} issue(s) found`, flagged: true };
    case "duplicate_detect":
      return delta.is_duplicate
        ? { text: "already exists in the ledger", flagged: true }
        : { text: "no prior record found", flagged: false };
    case "3_way_matching":
      return delta.match_result?.matched
        ? { text: "invoice reconciles with PO/GR", flagged: false }
        : { text: `${(delta.match_result?.issues || []).length} mismatch(es)`, flagged: true };
    case "classify":
      return { text: delta.classification?.primary_category || "uncategorized", flagged: false };
    case "risk_analysis":
      return { text: `${delta.risk?.tier || "—"} risk (score ${delta.risk?.score ?? "—"})`, flagged: delta.risk?.tier === "high" };
    case "approval":
      return { text: delta.approval?.decision === "auto_approved" ? "auto-approved" : `routed to ${delta.approval?.approver || "review"}`, flagged: delta.approval?.decision !== "auto_approved" };
    case "report_gen":
      return { text: "report compiled", flagged: false };
    default:
      return { text: "", flagged: false };
  }
}
