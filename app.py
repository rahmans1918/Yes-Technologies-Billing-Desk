from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "yestech_billing.db"
DOCUMENT_TYPES = {"invoice": "GST Invoice", "quotation": "Quotation", "proforma": "Proforma Invoice", "purchase_order": "Purchase Order"}
STATUS_OPTIONS = ("Draft", "Sent", "Paid", "Cancelled")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "yestech-local-development-key")
app.config["DATABASE"] = str(DATABASE)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            business_name TEXT NOT NULL,
            gstin TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            state TEXT NOT NULL,
            state_code TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_type TEXT NOT NULL CHECK (document_type IN ('invoice', 'quotation', 'proforma', 'purchase_order')),
            document_number TEXT NOT NULL UNIQUE,
            document_date TEXT NOT NULL,
            due_date TEXT,
            customer_name TEXT NOT NULL,
            customer_gstin TEXT,
            customer_address TEXT NOT NULL,
            customer_state TEXT NOT NULL,
            customer_state_code TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'Draft',
            subtotal REAL NOT NULL DEFAULT 0,
            cgst REAL NOT NULL DEFAULT 0,
            sgst REAL NOT NULL DEFAULT 0,
            igst REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS document_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            hsn_sac TEXT,
            quantity REAL NOT NULL,
            rate REAL NOT NULL,
            gst_rate REAL NOT NULL DEFAULT 18,
            amount REAL NOT NULL
        );
        INSERT OR IGNORE INTO settings (id, business_name, gstin, address, phone, email, state, state_code)
        VALUES (1, 'Yes Technologies', '36AZWPA0162E2ZJ', '5-6-371, Nehru Nagar, Gajularamaram, Quthbullapur, Medchal - Malkajgiri, Hyderabad, Telangana - 500055', '+91 - 9700511523 / +91 - 9493920930', 'accounts@yestechnologies.in', 'Telangana', '36');
        """)
    document_schema = db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'documents'").fetchone()[0]
    if "purchase_order" not in document_schema:
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("ALTER TABLE documents RENAME TO documents_legacy")
        db.execute("""CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_type TEXT NOT NULL CHECK (document_type IN ('invoice', 'quotation', 'proforma', 'purchase_order')),
            document_number TEXT NOT NULL UNIQUE,
            document_date TEXT NOT NULL,
            due_date TEXT,
            customer_name TEXT NOT NULL,
            customer_gstin TEXT,
            customer_address TEXT NOT NULL,
            customer_state TEXT NOT NULL,
            customer_state_code TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'Draft',
            subtotal REAL NOT NULL DEFAULT 0,
            cgst REAL NOT NULL DEFAULT 0,
            sgst REAL NOT NULL DEFAULT 0,
            igst REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        db.execute("INSERT INTO documents SELECT * FROM documents_legacy")
        db.execute("DROP TABLE documents_legacy")
        db.execute("PRAGMA foreign_keys = ON")
    item_foreign_key = db.execute("PRAGMA foreign_key_list(document_items)").fetchone()
    if item_foreign_key is not None and item_foreign_key[2] != "documents":
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("ALTER TABLE document_items RENAME TO document_items_legacy")
        db.execute("""CREATE TABLE document_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            hsn_sac TEXT,
            quantity REAL NOT NULL,
            rate REAL NOT NULL,
            gst_rate REAL NOT NULL DEFAULT 18,
            amount REAL NOT NULL
        )""")
        db.execute("INSERT INTO document_items SELECT * FROM document_items_legacy")
        db.execute("DROP TABLE document_items_legacy")
        db.execute("PRAGMA foreign_keys = ON")
    db.commit()


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def next_number(document_type: str) -> str:
    prefix = {"invoice": "INV", "quotation": "QUO", "proforma": "PI", "purchase_order": "PO"}[document_type]
    year = datetime.now().year
    row = get_db().execute(
        "SELECT COUNT(*) AS count FROM documents WHERE document_type = ? AND strftime('%Y', created_at) = ?",
        (document_type, str(year)),
    ).fetchone()
    return f"{prefix}-{year}-{int(row['count']) + 1:04d}"


def calculate_totals(items: list[dict[str, Any]], seller_state_code: str, customer_state_code: str) -> dict[str, Decimal]:
    subtotal = sum((item["amount"] for item in items), Decimal("0.00"))
    tax_total = sum((item["tax"] for item in items), Decimal("0.00"))
    if seller_state_code == customer_state_code:
        cgst = (tax_total / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = tax_total - cgst
        igst = Decimal("0.00")
    else:
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = tax_total
    return {"subtotal": subtotal, "cgst": cgst, "sgst": sgst, "igst": igst, "total": subtotal + tax_total}


def settings() -> sqlite3.Row:
    return get_db().execute("SELECT * FROM settings WHERE id = 1").fetchone()


@app.template_filter("inr")
def format_inr(value: Any) -> str:
    return f"₹{money(value):,.2f}"


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {"document_types": DOCUMENT_TYPES, "today": date.today().isoformat(), "business": settings()}


@app.route("/")
def dashboard():
    db = get_db()
    stats = db.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(total), 0) AS value FROM documents WHERE document_type = 'invoice' AND status != 'Cancelled'"
    ).fetchone()
    outstanding = db.execute(
        "SELECT COALESCE(SUM(total), 0) AS value FROM documents WHERE document_type = 'invoice' AND status IN ('Draft', 'Sent')"
    ).fetchone()
    recent = db.execute("SELECT * FROM documents ORDER BY id DESC LIMIT 6").fetchall()
    counts = {key: db.execute("SELECT COUNT(*) AS count FROM documents WHERE document_type = ?", (key,)).fetchone()["count"] for key in DOCUMENT_TYPES}
    return render_template("dashboard.html", stats=stats, outstanding=outstanding, recent=recent, counts=counts)


@app.route("/documents")
def documents():
    document_type = request.args.get("type", "")
    query = "SELECT * FROM documents"
    params: list[Any] = []
    if document_type in DOCUMENT_TYPES:
        query += " WHERE document_type = ?"
        params.append(document_type)
    query += " ORDER BY id DESC"
    rows = get_db().execute(query, params).fetchall()
    return render_template("documents.html", documents=rows, selected_type=document_type)


@app.route("/documents/new/<document_type>", methods=["GET", "POST"])
def new_document(document_type: str):
    if document_type not in DOCUMENT_TYPES:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        form = request.form
        descriptions = form.getlist("description[]")
        quantities = form.getlist("quantity[]")
        rates = form.getlist("rate[]")
        gst_rates = form.getlist("gst_rate[]")
        hsn_codes = form.getlist("hsn_sac[]")
        items: list[dict[str, Any]] = []
        for index, description in enumerate(descriptions):
            if not description.strip():
                continue
            quantity = money(quantities[index] if index < len(quantities) else 0)
            rate = money(rates[index] if index < len(rates) else 0)
            gst_rate = money(gst_rates[index] if index < len(gst_rates) else 18)
            amount = (quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax = (amount * gst_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            items.append({"description": description.strip(), "hsn_sac": hsn_codes[index] if index < len(hsn_codes) else "", "quantity": quantity, "rate": rate, "gst_rate": gst_rate, "amount": amount, "tax": tax})
        if not items:
            flash("Add at least one line item before saving.", "error")
            return render_template("document_form.html", document_type=document_type, form=form)
        db = get_db()
        totals = calculate_totals(items, settings()["state_code"], form.get("customer_state_code", ""))
        number = form.get("document_number", "").strip() or next_number(document_type)
        try:
            cursor = db.execute(
                """INSERT INTO documents (document_type, document_number, document_date, due_date, customer_name, customer_gstin, customer_address, customer_state, customer_state_code, notes, status, subtotal, cgst, sgst, igst, total, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document_type, number, form.get("document_date") or date.today().isoformat(), form.get("due_date"), form.get("customer_name", "").strip(), form.get("customer_gstin", "").strip().upper(), form.get("customer_address", "").strip(), form.get("customer_state", "").strip(), form.get("customer_state_code", "").strip(), form.get("notes", "").strip(), form.get("status", "Draft"), float(totals["subtotal"]), float(totals["cgst"]), float(totals["sgst"]), float(totals["igst"]), float(totals["total"]), datetime.now().isoformat(timespec="seconds")),
            )
        except sqlite3.IntegrityError:
            flash("That document number already exists. Use a unique number.", "error")
            return render_template("document_form.html", document_type=document_type, form=form)
        document_id = cursor.lastrowid
        db.executemany(
            "INSERT INTO document_items (document_id, description, hsn_sac, quantity, rate, gst_rate, amount) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(document_id, item["description"], item["hsn_sac"], float(item["quantity"]), float(item["rate"]), float(item["gst_rate"]), float(item["amount"])) for item in items],
        )
        db.commit()
        flash(f"{DOCUMENT_TYPES[document_type]} {number} created.", "success")
        return redirect(url_for("view_document", document_id=document_id))
    return render_template("document_form.html", document_type=document_type, form={"document_date": date.today().isoformat(), "document_number": next_number(document_type)})


@app.route("/documents/<int:document_id>")
def view_document(document_id: int):
    db = get_db()
    document = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if document is None:
        return redirect(url_for("documents"))
    items = db.execute("SELECT * FROM document_items WHERE document_id = ? ORDER BY id", (document_id,)).fetchall()
    return render_template("document_view.html", document=document, items=items)


@app.post("/documents/<int:document_id>/status")
def update_status(document_id: int):
    status = request.form.get("status", "Draft")
    if status in STATUS_OPTIONS:
        get_db().execute("UPDATE documents SET status = ? WHERE id = ?", (status, document_id))
        get_db().commit()
        flash("Document status updated.", "success")
    return redirect(url_for("view_document", document_id=document_id))


@app.route("/settings", methods=["GET", "POST"])
def edit_settings():
    if request.method == "POST":
        form = request.form
        get_db().execute(
            "UPDATE settings SET business_name = ?, gstin = ?, address = ?, phone = ?, email = ?, state = ?, state_code = ? WHERE id = 1",
            (form.get("business_name", "").strip(), form.get("gstin", "").strip().upper(), form.get("address", "").strip(), form.get("phone", "").strip(), form.get("email", "").strip(), form.get("state", "").strip(), form.get("state_code", "").strip()),
        )
        get_db().commit()
        flash("Business profile saved.", "success")
        return redirect(url_for("edit_settings"))
    return render_template("settings.html", profile=settings())


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
