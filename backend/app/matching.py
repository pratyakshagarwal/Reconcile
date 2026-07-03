from backend.app.schemas import MatchIssue, MatchResult
def match_invoice(invoice: dict, po: dict, gr: dict, price_tolerance_pct: float = 2.0) -> MatchResult:
    issues = []

    if not po.get("po_number"):
        return MatchResult(
            matched=False,
            issues=[MatchIssue(field="po_number", expected="present", actual="missing", severity="warning")]
        )

    # Map by description instead of item_id (normalize to lowercase, strip whitespace)
    po_items = {i.get("description", "").lower().strip(): i for i in po.get("line_items", []) if i.get("description")}
    gr_items = {i.get("description", "").lower().strip(): i for i in gr.get("line_items", []) if i.get("description")}
    inv_items = invoice.get("line_items", [])

    # STEP 1: Match GR against PO
    for desc, po_item in po_items.items():
        gr_item = gr_items.get(desc)
        if not gr_item:
            issues.append(MatchIssue(field=f"GR:{desc}", expected="present", actual="missing", severity="critical"))
            continue
            
        po_qty = po_item.get("quantity") or 0
        gr_qty = gr_item.get("quantity_received") or 0
        
        if po_qty != gr_qty:
            issues.append(MatchIssue(field=f"GR:qty:{desc}", expected=str(po_qty), actual=str(gr_qty), severity="critical"))

    # STEP 2 & 3: Match Invoice against PO and GR
    expected_subtotal = 0.0

    for inv_item in inv_items:
        inv_desc = inv_item.get("description", "").lower().strip()
        inv_qty = inv_item.get("quantity") or 0
        inv_price = inv_item.get("unit_price") or 0
        
        po_item = po_items.get(inv_desc)
        gr_item = gr_items.get(inv_desc)

        if not po_item:
            issues.append(MatchIssue(field=f"Invoice:{inv_desc}", expected="on PO", actual="not ordered", severity="critical"))
            continue

        po_price = po_item.get("unit_price") or 0
        gr_qty = gr_item.get("quantity_received") or 0 if gr_item else 0

        # Price check
        price_diff_pct = ((inv_price - po_price) / po_price * 100) if po_price else 0
        if price_diff_pct > price_tolerance_pct:
            issues.append(MatchIssue(field=f"Invoice:price:{inv_desc}", expected=str(po_price), actual=str(inv_price), severity="critical"))

        # Quantity check
        if inv_qty > gr_qty:
            issues.append(MatchIssue(field=f"Invoice:qty:{inv_desc}", expected=f"<= {gr_qty}", actual=str(inv_qty), severity="critical"))

        expected_subtotal += po_price * min(inv_qty, gr_qty)

    # Final header-level check
    inv_total = invoice.get("total_amount") or 0
    inv_subtotal = inv_total - (invoice.get("tax_amount") or 0)
    tolerance = expected_subtotal * (price_tolerance_pct / 100)

    if abs(inv_subtotal - expected_subtotal) > tolerance:
        issues.append(MatchIssue(field="total_amount", expected=f"~{expected_subtotal:.2f}", actual=str(inv_subtotal), severity="critical"))

    matched = not any(i.severity == "critical" for i in issues)
    return MatchResult(matched=matched, issues=issues)