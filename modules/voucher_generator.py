"""
Generates Payment/Claim Voucher PDFs and records them in the `vouchers` table.
Numbering is sequential per calendar year per voucher type, never reused
(gaps allowed e.g. if a voucher is voided) — PV-2026-001, CV-2026-001, etc.

PDFs are rendered in memory and uploaded straight to Supabase Storage (no
local disk involved) since the app server's filesystem isn't persistent.
"""
import io
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from modules.db import get_connection
from modules.storage import upload_bytes

PREFIX_BY_TYPE = {"payment": "PV", "claim": "CV"}
TITLE_BY_TYPE = {"payment": "PAYMENT VOUCHER", "claim": "CLAIM VOUCHER"}


def next_voucher_number(voucher_type, year, conn):
    prefix = PREFIX_BY_TYPE[voucher_type]
    like_pattern = f"{prefix}-{year}-%"
    rows = conn.execute(
        "SELECT voucher_number FROM vouchers WHERE voucher_number LIKE %s", (like_pattern,)
    ).fetchall()
    max_seq = 0
    for r in rows:
        try:
            seq = int(r["voucher_number"].rsplit("-", 1)[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            pass
    return f"{prefix}-{year}-{max_seq + 1:03d}"


def _render_pdf(voucher_number, voucher_type, txn, document, prepared_by, approved_by) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    left = 20 * mm
    y = height - 25 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, "Lily Dahlia Enterprise (Demiglow)")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, y, TITLE_BY_TYPE[voucher_type])
    y -= 12 * mm

    c.setFont("Helvetica", 10)

    def row(label, value):
        nonlocal y
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(left + 45 * mm, y, str(value) if value is not None else "")
        y -= 7 * mm

    row("Voucher No.:", voucher_number)
    row("Date Generated:", date.today().isoformat())
    row("Transaction Date:", txn["date"])
    row("Counterparty:", txn["counterparty"])
    row("Transaction Note:", txn["note"])
    row("Category:", f"{txn['category']} / {txn['subcategory']}" if txn["subcategory"] else txn["category"])
    amount = txn["debit"] if txn["debit"] else txn["credit"]
    row("Amount (RM):", f"{amount:,.2f}" if amount is not None else "")

    if document is not None:
        row("Supporting Document:", document["filename"] or "(manual reference)")
        if document["notes"]:
            row("Document Notes:", document["notes"])

    y -= 8 * mm
    row("Prepared By:", prepared_by or "")
    row("Approved By:", approved_by or "")

    y -= 15 * mm
    c.line(left, y, left + 70 * mm, y)
    c.drawString(left, y - 5 * mm, "Signature (Prepared By)")
    c.line(left + 90 * mm, y, left + 160 * mm, y)
    c.drawString(left + 90 * mm, y - 5 * mm, "Signature (Approved By)")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_voucher(transaction_id, voucher_type, document_id=None, prepared_by=None, approved_by=None, conn=None):
    own_conn = conn is None
    conn = conn or get_connection()

    txn = conn.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,)).fetchone()
    if txn is None:
        raise ValueError(f"No transaction with id {transaction_id}")

    document = None
    if document_id is not None:
        document = conn.execute("SELECT * FROM documents WHERE id = %s", (document_id,)).fetchone()

    year = txn["date"][:4]
    voucher_number = next_voucher_number(voucher_type, year, conn)

    pdf_bytes = _render_pdf(voucher_number, voucher_type, txn, document, prepared_by, approved_by)
    storage_path = f"vouchers/{year}/{voucher_number}.pdf"
    upload_bytes(storage_path, pdf_bytes, content_type="application/pdf")

    conn.execute(
        """INSERT INTO vouchers (voucher_number, voucher_type, transaction_id, document_id,
                                  prepared_by, approved_by, date_generated, storage_path)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (voucher_number, voucher_type, transaction_id, document_id, prepared_by, approved_by,
         date.today().isoformat(), storage_path),
    )
    conn.commit()

    if own_conn:
        conn.close()

    return voucher_number, storage_path
