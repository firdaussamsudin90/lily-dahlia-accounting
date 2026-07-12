"""
Outstanding Documents list: transactions where needs_document=true and no
document has been linked yet. Persists across months until resolved by
attaching a document, which in turn auto-generates a Payment or Claim
Voucher PDF.
"""
from datetime import date

from modules.db import get_connection
from modules.storage import upload_bytes
from modules.voucher_generator import generate_voucher

EXPECTED_DOCUMENT_TYPE = {
    "COGS": "Purchase Invoice / Receipt",
    "Marketing": "Ad Spend Confirmation / Receipt",
    "Operating Expenses": "Invoice / Receipt",
    "Logistics": "Shipping Receipt / Invoice",
}


def get_outstanding(conn=None):
    own_conn = conn is None
    conn = conn or get_connection()
    rows = conn.execute(
        """SELECT * FROM transactions
           WHERE needs_document = TRUE AND document_id IS NULL
           ORDER BY date ASC"""
    ).fetchall()
    if own_conn:
        conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d["expected_document_type"] = EXPECTED_DOCUMENT_TYPE.get(d["category"], "Receipt")
        out.append(d)
    return out


def _default_voucher_type(transaction):
    subcat = (transaction.get("subcategory") or "").lower()
    note = (transaction.get("note") or "").lower()
    if "claim" in subcat or "claim" in note:
        return "claim"
    return "payment"


def attach_document(
    transaction_id,
    document_type,
    uploaded_file=None,
    manual_reference=None,
    notes=None,
    voucher_type=None,
    prepared_by=None,
    approved_by=None,
):
    """Links a document (uploaded file or manual reference text) to a
    transaction, clears it from the Outstanding Documents list, and
    auto-generates the matching voucher PDF.

    uploaded_file: a Streamlit UploadedFile, or None if using manual_reference.
    Returns (document_id, voucher_number, voucher_storage_path).
    """
    conn = get_connection()
    txn = conn.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,)).fetchone()
    if txn is None:
        conn.close()
        raise ValueError(f"No transaction with id {transaction_id}")

    storage_path = None
    filename = None
    if uploaded_file is not None:
        filename = uploaded_file.name
        storage_path = f"documents/{txn['month']}/txn{transaction_id}_{filename}"
        upload_bytes(storage_path, uploaded_file.getvalue(),
                     content_type=uploaded_file.type or "application/octet-stream")

    combined_notes = notes or ""
    if manual_reference:
        combined_notes = f"Manual reference: {manual_reference}. {combined_notes}".strip()

    cur = conn.execute(
        """INSERT INTO documents (filename, storage_path, uploaded_date, document_type,
                                   linked_transaction_id, notes)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (filename, storage_path, date.today().isoformat(), document_type, transaction_id, combined_notes),
    )
    document_id = cur.fetchone()["id"]

    conn.execute("UPDATE transactions SET document_id = %s WHERE id = %s", (document_id, transaction_id))
    conn.commit()

    v_type = voucher_type or _default_voucher_type(dict(txn))
    voucher_number, voucher_storage_path = generate_voucher(
        transaction_id=transaction_id,
        voucher_type=v_type,
        document_id=document_id,
        prepared_by=prepared_by,
        approved_by=approved_by,
        conn=conn,
    )

    conn.close()
    return document_id, voucher_number, voucher_storage_path
