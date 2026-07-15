"""
Shared document-saving logic for the Upload Documents page (both the
one-by-one and WhatsApp import modes) — handles the Supabase Storage upload,
the `documents` row, and (when linked to a transaction that still needs a
document) generating the matching voucher, mirroring what Outstanding
Documents' attach_document does for the existing flow.
"""
import re
import uuid
from datetime import date

from modules.db import get_connection
from modules.storage import upload_bytes
from modules.voucher_generator import generate_voucher


def _default_voucher_type(transaction):
    subcat = (transaction.get("subcategory") or "").lower()
    note = (transaction.get("note") or "").lower()
    if "claim" in subcat or "claim" in note:
        return "claim"
    return "payment"


def _link_and_maybe_generate_voucher(conn, document_id, transaction_id, prepared_by, approved_by):
    txn = conn.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,)).fetchone()
    if txn is None:
        return None, None
    txn = dict(txn)
    if not (txn["needs_document"] and txn["document_id"] is None):
        return None, None  # already has a document, or this category doesn't need one — just link, no voucher

    conn.execute("UPDATE transactions SET document_id = %s WHERE id = %s", (document_id, transaction_id))
    conn.commit()
    return generate_voucher(
        transaction_id=transaction_id,
        voucher_type=_default_voucher_type(txn),
        document_id=document_id,
        prepared_by=prepared_by,
        approved_by=approved_by,
        conn=conn,
    )


def save_document(
    file_bytes,
    filename,
    content_type=None,
    caption=None,
    month=None,
    document_type="receipt",
    linked_transaction_id=None,
    flag_color=None,
    flag_note=None,
    source="manual_upload",
    message_date=None,
    notes=None,
    prepared_by=None,
    approved_by=None,
    conn=None,
):
    """Uploads the file (if any) and records a `documents` row. If
    linked_transaction_id is given and that transaction still needs a
    document, also links it and generates the Payment/Claim Voucher.
    Returns {document_id, voucher_number, voucher_storage_path}."""
    own_conn = conn is None
    conn = conn or get_connection()

    storage_path = None
    if file_bytes is not None:
        safe_month = month or "unfiled"
        unique = uuid.uuid4().hex[:8]
        safe_name = re.sub(r"[^\w.\-]", "_", filename or "file")
        storage_path = f"documents/{safe_month}/{unique}_{safe_name}"
        upload_bytes(storage_path, file_bytes, content_type=content_type or "application/octet-stream")

    cur = conn.execute(
        """INSERT INTO documents (filename, storage_path, uploaded_date, document_type,
                                   linked_transaction_id, caption, flag_color, flag_note,
                                   source, message_date, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (filename, storage_path, date.today().isoformat(), document_type,
         linked_transaction_id, caption, flag_color, flag_note, source, message_date, notes),
    )
    document_id = cur.fetchone()["id"]
    conn.commit()

    voucher_number, voucher_storage_path = (None, None)
    if linked_transaction_id is not None:
        voucher_number, voucher_storage_path = _link_and_maybe_generate_voucher(
            conn, document_id, linked_transaction_id, prepared_by, approved_by
        )

    if own_conn:
        conn.close()

    return {
        "document_id": document_id,
        "voucher_number": voucher_number,
        "voucher_storage_path": voucher_storage_path,
    }


def rematch_document(document_id, transaction_id, prepared_by=None, approved_by=None, conn=None):
    """Links an already-saved (unmatched/flagged) document to a transaction
    from the Pending Review list, clearing its flag. Returns
    (voucher_number, voucher_storage_path) — both None if no voucher was
    generated (transaction didn't need a document, or already had one)."""
    own_conn = conn is None
    conn = conn or get_connection()

    conn.execute(
        "UPDATE documents SET linked_transaction_id = %s, flag_color = NULL, flag_note = NULL WHERE id = %s",
        (transaction_id, document_id),
    )
    conn.commit()

    voucher_number, voucher_storage_path = _link_and_maybe_generate_voucher(
        conn, document_id, transaction_id, prepared_by, approved_by
    )

    if own_conn:
        conn.close()
    return voucher_number, voucher_storage_path
