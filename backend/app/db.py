import psycopg2, os

def get_connection():
    return psycopg2.connect(os.getenv("DB_URL"))


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Invoices
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            vendor_name TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            po_number TEXT,
            total_amount NUMERIC,
            tax_amount NUMERIC,
            currency TEXT,
            invoice_date DATE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(vendor_name, invoice_number)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoice_line_items (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
            description TEXT,
            quantity NUMERIC,
            unit_price NUMERIC
        )
    """)

    # Purchase Orders
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id SERIAL PRIMARY KEY,
            po_number TEXT NOT NULL UNIQUE,
            vendor_name TEXT NOT NULL,
            currency TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS po_line_items (
            id SERIAL PRIMARY KEY,
            po_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
            description TEXT,
            quantity NUMERIC,
            unit_price NUMERIC
        )
    """)

    # Goods Receipts
    cur.execute("""
        CREATE TABLE IF NOT EXISTS goods_receipts (
            id SERIAL PRIMARY KEY,
            po_number TEXT NOT NULL,
            received_date DATE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gr_line_items (
            id SERIAL PRIMARY KEY,
            gr_id INTEGER REFERENCES goods_receipts(id) ON DELETE CASCADE,
            description TEXT,
            quantity_received NUMERIC
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


# ---------- Duplicate check (unchanged logic) ----------

def check_duplicate(invoice: dict) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    vendor = invoice["vendor_name"].strip().lower()
    inv_num = invoice["invoice_number"].strip().lower()

    cur.execute(
        "SELECT id FROM invoices WHERE vendor_name = %s AND invoice_number = %s",
        (vendor, inv_num)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None  # True = duplicate exists


# ---------- Insert invoice + its line items ----------

def insert_invoice(invoice: dict, user_id:int) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO invoices (vendor_name, invoice_number, po_number, total_amount, tax_amount, currency, invoice_date, user_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (
            invoice["vendor_name"].strip().lower(),
            invoice["invoice_number"].strip().lower(),
            invoice.get("po_number"),
            invoice.get("total_amount"),
            invoice.get("tax_amount"),
            invoice.get("currency"),
            invoice.get("invoice_date"),
            user_id,
        )
    )
    invoice_id = cur.fetchone()[0]

    for item in invoice.get("line_items", []):
        cur.execute(
            """INSERT INTO invoice_line_items (invoice_id, description, quantity, unit_price)
               VALUES (%s, %s, %s, %s)""",
            (invoice_id, item.get("description"), item.get("quantity"), item.get("unit_price"))
        )

    conn.commit()
    cur.close()
    conn.close()
    return invoice_id


# ---------- Insert PO + its line items ----------

def check_duplicate_po(po: dict) -> bool:
    conn = get_connection()
    cur = conn.cursor()

    po_number = (po.get("po_number") or "").strip().lower()

    cur.execute(
        "SELECT id FROM purchase_orders WHERE LOWER(po_number) = %s",
        (po_number,)
    )

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result is not None

def insert_po(po: dict) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO purchase_orders (po_number, vendor_name, currency)
           VALUES (%s, %s, %s)
           RETURNING id""",
        (po.get("po_number"), po.get("vendor_name"), po.get("currency"))
    )
    po_id = cur.fetchone()[0]

    for item in po.get("line_items", []):
        cur.execute(
            """INSERT INTO po_line_items (po_id, description, quantity, unit_price)
               VALUES (%s, %s, %s, %s)""",
            (po_id, item.get("description"), item.get("quantity"), item.get("unit_price"))
        )

    conn.commit()
    cur.close()
    conn.close()
    return po_id


# ---------- Insert GR + its line items ----------

def check_duplicate_gr(gr: dict) -> bool:
    conn = get_connection()
    cur = conn.cursor()

    po_number = (gr.get("po_number") or "").strip().lower()
    received_date = gr.get("received_date")

    cur.execute(
        """
        SELECT id
        FROM goods_receipts
        WHERE LOWER(po_number) = %s
        AND received_date = %s
        """,
        (po_number, received_date)
    )

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result is not None

def insert_gr(gr: dict) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO goods_receipts (po_number, received_date)
           VALUES (%s, %s)
           RETURNING id""",
        (gr.get("po_number"), gr.get("received_date"))
    )
    gr_id = cur.fetchone()[0]

    for item in gr.get("line_items", []):
        cur.execute(
            """INSERT INTO gr_line_items (gr_id, description, quantity_received)
               VALUES (%s, %s, %s)""",
            (gr_id, item.get("description"), item.get("quantity_received"))
        )

    conn.commit()
    cur.close()
    conn.close()
    return gr_id

def migrate_invoices_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS po_number TEXT")
    cur.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS tax_amount NUMERIC")
    cur.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS currency TEXT")
    conn.commit()
    cur.close()
    conn.close()


def migrate_purchase_ordertable():
    conn = get_connection()
    curr = conn.cursor()

    curr.execute("ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS invoice_id TEXT ")
    conn.commit()
    curr.close()
    conn.close()
    