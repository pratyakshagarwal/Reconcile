from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import csv
import json
import io
from datetime import datetime
from backend.app.db import get_connection

router = APIRouter()

# ============================================================================
# Get Invoice Details (with PO and GR)
# ============================================================================

@router.get("/api/invoices/{invoice_id}")
def get_invoice_details(invoice_id: int):
    """Get invoice, PO, GR, and review decisions"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Get invoice
        cur.execute("""
            SELECT id, vendor_name, invoice_number, po_number, total_amount, 
                   tax_amount, currency, invoice_date, created_at
            FROM invoices WHERE id = %s
        """, (invoice_id,))
        
        invoice = cur.fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        invoice_data = {
            "id": invoice[0],
            "vendor_name": invoice[1],
            "invoice_number": invoice[2],
            "po_number": invoice[3],
            "total_amount": float(invoice[4]) if invoice[4] else 0,
            "tax_amount": float(invoice[5]) if invoice[5] else 0,
            "currency": invoice[6],
            "invoice_date": invoice[7],
            "created_at": invoice[8].isoformat() if invoice[8] else None
        }
        
        # Get invoice line items
        cur.execute("""
            SELECT description, quantity, unit_price
            FROM invoice_line_items WHERE invoice_id = %s
        """, (invoice_id,))
        
        invoice_data["line_items"] = [
            {"description": row[0], "quantity": float(row[1]) if row[1] else 0, "unit_price": float(row[2]) if row[2] else 0}
            for row in cur.fetchall()
        ]
        
        # Get PO
        if invoice_data["po_number"]:
            cur.execute("""
                SELECT id, po_number, vendor_name, currency
                FROM purchase_orders WHERE po_number = %s
            """, (invoice_data["po_number"],))
            
            po = cur.fetchone()
            if po:
                po_data = {
                    "po_number": po[1],
                    "vendor_name": po[2],
                    "currency": po[3]
                }
                
                cur.execute("""
                    SELECT description, quantity, unit_price
                    FROM po_line_items WHERE po_id = %s
                """, (po[0],))
                
                po_data["line_items"] = [
                    {"description": row[0], "quantity": float(row[1]) if row[1] else 0, "unit_price": float(row[2]) if row[2] else 0}
                    for row in cur.fetchall()
                ]
                
                invoice_data["po"] = po_data
        
        # Get GR
        if invoice_data["po_number"]:
            cur.execute("""
                SELECT id, po_number, received_date
                FROM goods_receipts WHERE po_number = %s
            """, (invoice_data["po_number"],))
            
            gr = cur.fetchone()
            if gr:
                gr_data = {
                    "po_number": gr[1],
                    "received_date": gr[2]
                }
                
                cur.execute("""
                    SELECT description, quantity_received
                    FROM gr_line_items WHERE gr_id = %s
                """, (gr[0],))
                
                gr_data["line_items"] = [
                    {"description": row[0], "quantity_received": float(row[1]) if row[1] else 0}
                    for row in cur.fetchall()
                ]
                
                invoice_data["gr"] = gr_data
        
        # Get review decisions
        cur.execute("""
            SELECT decision, risk_score_at_decision, reviewer_note, created_at
            FROM reviewer_decisions WHERE invoice_id = %s
            ORDER BY created_at DESC
        """, (invoice_id,))
        
        invoice_data["reviews"] = [
            {
                "decision": row[0],
                "risk_score": float(row[1]) if row[1] else 0,
                "note": row[2],
                "reviewed_at": row[3].isoformat() if row[3] else None
            }
            for row in cur.fetchall()
        ]
        
        return invoice_data
    
    finally:
        cur.close()
        conn.close()

# ============================================================================
# Export Invoice as JSON
# ============================================================================

@router.get("/api/invoices/{invoice_id}/export/json")
def export_invoice_json(invoice_id: int):
    """Export invoice as JSON"""
    invoice = get_invoice_details(invoice_id)
    
    json_str = json.dumps(invoice, indent=2, default=str)
    
    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice_id}.json"}
    )

# ============================================================================
# Export Invoice as CSV
# ============================================================================

@router.get("/api/invoices/{invoice_id}/export/csv")
def export_invoice_csv(invoice_id: int):
    """Export invoice as CSV"""
    invoice = get_invoice_details(invoice_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Invoice Details"])
    writer.writerow([])
    writer.writerow(["Field", "Value"])
    writer.writerow(["Invoice Number", invoice.get("invoice_number")])
    writer.writerow(["Vendor", invoice.get("vendor_name")])
    writer.writerow(["PO Number", invoice.get("po_number")])
    writer.writerow(["Total Amount", invoice.get("total_amount")])
    writer.writerow(["Tax", invoice.get("tax_amount")])
    writer.writerow(["Currency", invoice.get("currency")])
    writer.writerow(["Invoice Date", invoice.get("invoice_date")])
    writer.writerow([])
    
    # Line items
    writer.writerow(["Invoice Line Items"])
    writer.writerow(["Description", "Quantity", "Unit Price", "Total"])
    for item in invoice.get("line_items", []):
        total = (item.get("quantity") or 0) * (item.get("unit_price") or 0)
        writer.writerow([
            item.get("description"),
            item.get("quantity"),
            item.get("unit_price"),
            total
        ])
    
    writer.writerow([])
    
    # PO info
    if invoice.get("po"):
        po = invoice["po"]
        writer.writerow(["Purchase Order"])
        writer.writerow(["PO Number", po.get("po_number")])
        writer.writerow(["Vendor", po.get("vendor_name")])
        writer.writerow([])
        writer.writerow(["PO Line Items"])
        writer.writerow(["Description", "Quantity", "Unit Price", "Total"])
        for item in po.get("line_items", []):
            total = (item.get("quantity") or 0) * (item.get("unit_price") or 0)
            writer.writerow([
                item.get("description"),
                item.get("quantity"),
                item.get("unit_price"),
                total
            ])
        writer.writerow([])
    
    # GR info
    if invoice.get("gr"):
        gr = invoice["gr"]
        writer.writerow(["Goods Receipt"])
        writer.writerow(["PO Number", gr.get("po_number")])
        writer.writerow(["Received Date", gr.get("received_date")])
        writer.writerow([])
        writer.writerow(["GR Line Items"])
        writer.writerow(["Description", "Quantity Received"])
        for item in gr.get("line_items", []):
            writer.writerow([
                item.get("description"),
                item.get("quantity_received")
            ])
        writer.writerow([])
    
    # Reviews
    if invoice.get("reviews"):
        writer.writerow(["Review Decisions"])
        writer.writerow(["Decision", "Risk Score", "Note", "Date"])
        for review in invoice["reviews"]:
            writer.writerow([
                review.get("decision"),
                review.get("risk_score"),
                review.get("note"),
                review.get("reviewed_at")
            ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice_id}.csv"}
    )

# ============================================================================
# List all invoices (for dashboard)
# ============================================================================

@router.get("/api/invoices")
def list_invoices(skip: int = 0, limit: int = 50):
    """Get all invoices for dashboard"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, vendor_name, invoice_number, po_number, total_amount, created_at
            FROM invoices
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, skip))
        
        invoices = [
            {
                "id": row[0],
                "vendor_name": row[1],
                "invoice_number": row[2],
                "po_number": row[3],
                "total_amount": float(row[4]) if row[4] else 0,
                "created_at": row[5].isoformat() if row[5] else None
            }
            for row in cur.fetchall()
        ]
        
        # Get review status for each invoice
        for invoice in invoices:
            cur.execute("""
                SELECT COUNT(*), 
                       SUM(CASE WHEN decision = 'approved' THEN 1 ELSE 0 END)
                FROM reviewer_decisions WHERE invoice_id = %s
            """, (invoice["id"],))
            
            result = cur.fetchone()
            invoice["total_reviews"] = result[0] or 0
            invoice["approved_count"] = result[1] or 0
        
        return invoices
    
    finally:
        cur.close()
        conn.close()
