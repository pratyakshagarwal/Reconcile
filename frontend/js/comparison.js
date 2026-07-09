/* ============================================================
   DOCUMENT COMPARISON
   ============================================================ */

let comparisonState = {
    invoice: null,
    purchaseOrder: null,
    goodsReceipt: null,
    mismatches: null
};

/* ============================================================
   LOAD COMPARISON DATA
   ============================================================ */

async function loadComparison(invoice) {

    // Reset state every time a new comparison is opened
    comparisonState = {
        invoice,
        purchaseOrder: null,
        goodsReceipt: null,
        mismatches: null
    };

    try {
        const [poRes, grRes, mismatchRes] = await Promise.all([
            authFetch(`/api/purchase_orders/${invoice.po_number}`),
            authFetch(`/api/goods_receipts/${invoice.po_number}`),
            authFetch(`/api/runs/${invoice.run_id}/mismatches`)
        ]);

        comparisonState.purchaseOrder =
            poRes.ok ? await poRes.json() : null;

        comparisonState.goodsReceipt =
            grRes.ok ? await grRes.json() : null;

        comparisonState.mismatches =
            mismatchRes.ok ? await mismatchRes.json() : null;

        console.log("Comparison State:", comparisonState);

    } catch (err) {
        console.error("Comparison load failed:", err);
    }
}

/* ============================================================
   RENDER
   ============================================================ */

function renderLineItemComparison() {

    const invoice = comparisonState.invoice;
    const po = comparisonState.purchaseOrder;
    const gr = comparisonState.goodsReceipt;

        // Build lookup for mismatches
    const mismatchLookup = new Set();

    (comparisonState.mismatches?.issues || []).forEach(issue => {
        mismatchLookup.add(issue.field.toLowerCase());
    });

    const invoiceMap = Object.fromEntries(
        (invoice.line_items || []).map(item => [
            item.description.toLowerCase(),
            item
        ])
    );

    const poMap = Object.fromEntries(
        (po.line_items || []).map(item => [
            item.description.toLowerCase(),
            item
        ])
    );

    const grMap = Object.fromEntries(
        (gr.line_items || []).map(item => [
            item.description.toLowerCase(),
            item
        ])
    );

    const descriptions = new Set([
        ...Object.keys(invoiceMap),
        ...Object.keys(poMap),
        ...Object.keys(grMap)
    ]);

    let html = `
        <h3>Line Item Comparison</h3>

        <table class="comparison-table">
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Invoice Qty</th>
                    <th>PO Qty</th>
                    <th>GR Qty</th>
                    <th>Invoice Price</th>
                    <th>PO Price</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
    `;
    descriptions.forEach(desc => {

        const inv = invoiceMap[desc];
        const poItem = poMap[desc];
        const grItem = grMap[desc];

    // ---------- Highlight logic ----------
        const qtyMismatch = mismatchLookup.has(
        `quantity:${desc}`
        );

        const priceMismatch = mismatchLookup.has(
            `invoice:price:${desc}`
        );

        const status =
            qtyMismatch || priceMismatch
                ? "⚠ Mismatch"
                : "✅ Match";


    const invoicePriceClass = priceMismatch ? "mismatch-cell" : "";
    const poPriceClass = priceMismatch ? "mismatch-cell" : "";

    const invoiceQtyClass = qtyMismatch ? "mismatch-cell" : "";
    const poQtyClass = qtyMismatch ? "mismatch-cell" : "";
    const grQtyClass = qtyMismatch ? "mismatch-cell" : "";

    html += `
        <tr>

            <td>${inv?.description || poItem?.description || grItem?.description}</td>

            <td class="${invoiceQtyClass}">
                ${inv?.quantity ?? "—"}
            </td>

            <td class="${poQtyClass}">
                ${poItem?.quantity ?? "—"}
            </td>

            <td class="${grQtyClass}">
                ${grItem?.quantity ?? "—"}
            </td>

            <td class="${invoicePriceClass}">
                ${priceMismatch ? "⚠ " : ""}
                ${inv?.unit_price ?? "—"}
            </td>

            <td class="${poPriceClass}">
                ${priceMismatch ? "⚠ " : ""}
                ${poItem?.unit_price ?? "—"}
            </td>

            <td>${status}</td>

        </tr>
    `;
});

    html += `
            </tbody>
        </table>
    `;

    document.getElementById("comparisonLineItems").innerHTML = html;
}

function renderComparison() {

    if (
        !comparisonState.invoice ||
        !comparisonState.purchaseOrder ||
        !comparisonState.goodsReceipt ||
        !comparisonState.mismatches
    ) {
        alert("Unable to load comparison data.");
        return;
    }

    document.getElementById("comparisonPanel").hidden = false;
    const invoice = comparisonState.invoice;
    const po = comparisonState.purchaseOrder;
    const gr = comparisonState.goodsReceipt;
    const totalMismatch =
    comparisonState.mismatches.issues.some(
        issue => issue.field.toLowerCase() === "total_amount"
    );

    const totalClass = totalMismatch ? "mismatch-cell" : "";

    document.getElementById("comparisonSummary").innerHTML = `
        <table class="comparison-table">
            <thead>
                <tr>
                    <th>Field</th>
                    <th>Invoice</th>
                    <th>Purchase Order</th>
                    <th>Goods Receipt</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Vendor</td>
                    <td>${invoice.vendor_name ?? "—"}</td>
                    <td>${po.vendor_name ?? "—"}</td>
                    <td>—</td>
                </tr>

                <tr>
                    <td>PO Number</td>
                    <td>${invoice.po_number ?? "—"}</td>
                    <td>${po.po_number ?? "—"}</td>
                    <td>${gr.po_number ?? "—"}</td>
                </tr>

                <tr>
                    <td>Currency</td>
                    <td>${invoice.currency ?? "—"}</td>
                    <td>${po.currency ?? "—"}</td>
                    <td>—</td>
                </tr>

                <tr>
                    <td>Total Amount</td>

                    <td class="${totalClass}">
                        ${totalMismatch ? "⚠ " : ""}
                        ${formatCurrency(invoice.total_amount, invoice.currency)}
                    </td>

                    <td class="${totalClass}">
                        ${totalMismatch ? "⚠ " : ""}
                        ${formatCurrency(
                            po.line_items.reduce(
                                (sum, item) => sum + item.quantity * item.unit_price,
                                0
                            ),
                            po.currency
                        )}
                    </td>

                    <td>—</td>
                </tr>

                <tr>
                    <td>Invoice Date</td>
                    <td>${formatDate(invoice.invoice_date)}</td>
                    <td>—</td>
                    <td>—</td>
                </tr>

                <tr>
                    <td>Received Date</td>
                    <td>—</td>
                    <td>—</td>
                    <td>${formatDate(gr.received_date)}</td>
                </tr>
            </tbody>
        </table>
    `;
    renderLineItemComparison();
}

/* ============================================================
   EVENTS
   ============================================================ */

const compareBtn = document.getElementById("compareDocumentsBtn");
if (compareBtn) {
    compareBtn.addEventListener("click", async () => {
        if (!currentInvoice) return;
        await loadComparison(currentInvoice);
        renderComparison();
    });

}

const closeBtn = document.getElementById("closeComparisonBtn");
if (closeBtn) {
    closeBtn.addEventListener("click", () => {
        document.getElementById("comparisonPanel").hidden = true;
    });
}