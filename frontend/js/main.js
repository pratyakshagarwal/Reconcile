/* ============================================================
   MAIN — shared element references, view switching, app init.
   This must load AFTER index.html's elements exist, but its
   `els` object is referenced by pipeline.js, report.js, history.js —
   so keep this loaded early (right after auth.js) in index.html.
   ============================================================ */

const els = {
  viewUpload: document.getElementById("viewUpload"),
  viewPipeline: document.getElementById("viewPipeline"),
  viewReport: document.getElementById("viewReport"),
  uploadForm: document.getElementById("uploadForm"),
  submitBtn: document.getElementById("submitBtn"),
  formNote: document.getElementById("formNote"),
  stageList: document.getElementById("stageList"),
  pipelineTitle: document.getElementById("pipelineTitle"),
  ledgerList: document.getElementById("ledgerList"),
  ledgerEmpty: document.getElementById("ledgerEmpty"),
  statTotal: document.getElementById("statTotal"),
  statFlagged: document.getElementById("statFlagged"),
  statApproved: document.getElementById("statApproved"),
  newInvoiceBtn: document.getElementById("newInvoiceBtn"),
  backToUploadBtn: document.getElementById("backToUploadBtn"),
  searchInput: document.getElementById("searchInput"),
  viewInvoices: document.getElementById("viewInvoices"),
};

/* ============================================================
   VIEW SWITCHING
   ============================================================ */
function showView(name) {
  els.viewUpload.hidden = name !== "upload";
  els.viewPipeline.hidden = name !== "pipeline";
  els.viewReport.hidden = name !== "report";
  if (els.viewInvoices) {
    els.viewInvoices.hidden = name !== "invoices";
  }
}

els.newInvoiceBtn.addEventListener("click", () => {
  els.uploadForm.reset();
  document.querySelectorAll(".dropzone").forEach(dz => {
    dz.classList.remove("filled");
    dz.querySelector(".dz-filename").textContent = "";
  });
  showView("upload");
});

els.backToUploadBtn.addEventListener("click", () => showView("upload"));

/* ============================================================
   INIT — runs last, after every other file has defined what it needs
   ============================================================ */
if (getToken()) {
  enterApp();
} else {
  showAuthScreen(); 
}
