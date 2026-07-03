from backend.app.schemas import MatchIssue, MatchResult

def match_invoice(invoice: dict, po: dict, gr: dict, price_tolerance_pct: float = 2.0) -> MatchResult:
    issues = []

    if not po.get("po_number"):
        return MatchResult(
            matched=False,
            issues=[MatchIssue(field="po_number", expected="present", actual="missing", severity="warning")]
        )

    # 1. Map PO and GR items (Using 'item_id' or SKU is much safer than description text)
    po_items = {i["item_id"]: i for i in po.get("line_items", []) if i.get("item_id")}
    gr_items = {i["item_id"]: i for i in gr.get("line_items", []) if i.get("item_id")}
    inv_items = invoice.get("line_items", [])

    # 2. STEP 1: Match Goods Receipt against PO
    for item_id, po_item in po_items.items():
        gr_item = gr_items.get(item_id)
        if not gr_item:
            issues.append(MatchIssue(field=f"GR:item:{item_id}", expected="present", actual="missing", severity="critical"))
            continue
            
        po_qty = po_item.get("quantity") or 0
        gr_qty = gr_item.get("quantity_received") or 0
        
        if po_qty != gr_qty:
            issues.append(MatchIssue(field=f"GR:quantity:{item_id}", expected=str(po_qty), actual=str(gr_qty), severity="critical"))

    # 3. STEP 2 & 3: Match Invoice against PO (Price) and GR (Quantity)
    expected_subtotal = 0.0

    for inv_item in inv_items:
        item_id = inv_item.get("item_id")
        inv_qty = inv_item.get("quantity") or 0
        inv_price = inv_item.get("unit_price") or 0
        
        po_item = po_items.get(item_id)
        gr_item = gr_items.get(item_id)

        # Check if vendor invoiced an item we never ordered
        if not po_item:
            issues.append(MatchIssue(field=f"Invoice:item:{item_id}", expected="ordered on PO", actual="unordered item", severity="critical"))
            continue

        po_price = po_item.get("unit_price") or 0
        gr_qty = gr_item.get("quantity_received") or 0 if gr_item else 0

        # Check: Did they overcharge us on unit price compared to PO?
        price_diff_pct = ((inv_price - po_price) / po_price * 100) if po_price else 0
        if price_diff_pct > price_tolerance_pct:
            issues.append(MatchIssue(field=f"Invoice:price:{item_id}", expected=str(po_price), actual=str(inv_price), severity="critical"))

        # Check: Are they billing us for more than we actually received?
        if inv_qty > gr_qty:
            issues.append(MatchIssue(field=f"Invoice:quantity:{item_id}", expected=f"<= {gr_qty} (received)", actual=str(inv_qty), severity="critical"))

        # Keep track of what the subtotal should be based on valid PO prices and received amounts
        expected_subtotal += po_price * min(inv_qty, gr_qty)

    # 4. Final Header-Level Check
    inv_total = invoice.get("total_amount") or 0
    inv_subtotal = inv_total - (invoice.get("tax_amount") or 0)
    tolerance = expected_subtotal * (price_tolerance_pct / 100)

    if abs(inv_subtotal - expected_subtotal) > tolerance:
        issues.append(MatchIssue(field="total_amount", expected=f"~{expected_subtotal:.2f}", actual=str(inv_subtotal), severity="critical"))

    matched = not any(i.severity == "critical" for i in issues)
    return MatchResult(matched=matched, issues=issues)
