import streamlit as st

from modules.db import init_db
from modules.auth import require_login
from modules.outstanding_documents import attach_document, get_outstanding
from modules.storage import download_bytes

st.set_page_config(page_title="Outstanding Documents", page_icon="📎", layout="wide")
init_db()
require_login()
st.title("📎 Outstanding Documents")
st.caption(
    "Every transaction in COGS, Marketing, Operating Expenses, or Logistics needs a supporting "
    "document. This list persists across months until resolved. Attaching a document clears the "
    "item and auto-generates its Payment/Claim Voucher."
)

outstanding = get_outstanding()

if not outstanding:
    st.success("Nothing outstanding — every document-requiring transaction has a document attached.")
    st.stop()

st.write(f"**{len(outstanding)}** transaction(s) outstanding.")

DOCUMENT_TYPES = ["invoice", "receipt", "ad_confirmation", "other"]

for txn in outstanding:
    amount = txn["debit"] if txn["debit"] else txn["credit"]
    label = (
        f"{txn['date']} — {txn['counterparty'] or '(no counterparty)'} — RM{amount:,.2f} — "
        f"{txn['category']}/{txn['subcategory']} — expects: {txn['expected_document_type']}"
    )
    with st.expander(label):
        st.write(f"**Note:** {txn['note'] or '—'}")
        if txn["flag_color"]:
            st.warning(f"Flag: {txn['flag_color']} — {txn['flag_note'] or ''}")

        with st.form(key=f"doc_form_{txn['id']}"):
            document_type = st.selectbox("Document type", options=DOCUMENT_TYPES, key=f"doctype_{txn['id']}")
            mode = st.radio(
                "Evidence", options=["Upload file", "Manual reference (no file exists)"],
                key=f"mode_{txn['id']}", horizontal=True,
            )
            uploaded_file = None
            manual_reference = None
            if mode == "Upload file":
                uploaded_file = st.file_uploader(
                    "Receipt/invoice photo or PDF", type=["pdf", "png", "jpg", "jpeg"], key=f"file_{txn['id']}"
                )
            else:
                manual_reference = st.text_input(
                    "Manual reference (e.g. 'verbal confirmation from supplier, no receipt issued')",
                    key=f"manualref_{txn['id']}",
                )
            notes = st.text_area("Notes (optional)", key=f"notes_{txn['id']}")

            voucher_type = st.radio(
                "Voucher type", options=["payment", "claim"],
                index=0 if "claim" not in (txn["subcategory"] or "").lower() else 1,
                format_func=lambda v: "Payment Voucher" if v == "payment" else "Claim Voucher",
                key=f"vtype_{txn['id']}", horizontal=True,
            )
            c1, c2 = st.columns(2)
            prepared_by = c1.text_input("Prepared by", value="Firdaus", key=f"prep_{txn['id']}")
            approved_by = c2.text_input("Approved by", value="Diyanna", key=f"appr_{txn['id']}")

            submitted = st.form_submit_button("Attach document & generate voucher")
            if submitted:
                if mode == "Upload file" and uploaded_file is None:
                    st.error("Please upload a file, or switch to manual reference.")
                elif mode != "Upload file" and not manual_reference:
                    st.error("Please enter a manual reference.")
                else:
                    doc_id, voucher_number, voucher_storage_path = attach_document(
                        transaction_id=txn["id"],
                        document_type=document_type,
                        uploaded_file=uploaded_file,
                        manual_reference=manual_reference,
                        notes=notes,
                        voucher_type=voucher_type,
                        prepared_by=prepared_by,
                        approved_by=approved_by,
                    )
                    st.success(
                        f"Document attached. Generated **{voucher_number}**. This item will disappear "
                        f"from the list above next time you open this page — download the voucher below first."
                    )
                    st.download_button(
                        "Download voucher PDF", download_bytes(voucher_storage_path),
                        file_name=f"{voucher_number}.pdf", mime="application/pdf", key=f"dl_{txn['id']}",
                    )
