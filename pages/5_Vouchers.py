import pandas as pd
import streamlit as st

from modules.db import get_connection, init_db
from modules.auth import require_login
from modules.storage import download_bytes

init_db()
require_login()
st.title("🧾 Vouchers")

conn = get_connection()
rows = conn.execute(
    """SELECT v.*, t.date as txn_date, t.counterparty, t.note, t.debit, t.credit, t.category, t.subcategory
       FROM vouchers v JOIN transactions t ON v.transaction_id = t.id
       ORDER BY v.voucher_number DESC"""
).fetchall()
conn.close()

if not rows:
    st.info("No vouchers generated yet — attach a document to an item in Outstanding Documents to create one.")
    st.stop()

df = pd.DataFrame([dict(r) for r in rows])
# Postgres NUMERIC columns come back as decimal.Decimal via psycopg2 — convert to
# float before this DataFrame goes anywhere near st.dataframe()/Arrow, since mixing
# Decimal into a pyarrow-backed pandas DataFrame can crash the process outright.
for col in ["debit", "credit"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
type_filter = st.multiselect("Voucher type", options=["payment", "claim"], default=["payment", "claim"])
df = df[df["voucher_type"].isin(type_filter)]

st.dataframe(
    df[["voucher_number", "voucher_type", "txn_date", "counterparty", "note", "debit", "credit",
        "category", "subcategory", "prepared_by", "approved_by", "date_generated"]],
    width="stretch", height=500,
)

st.divider()
st.subheader("Download a voucher PDF")
choice = st.selectbox("Voucher", options=df["voucher_number"].tolist())
if choice:
    row = df[df["voucher_number"] == choice].iloc[0]
    if row["storage_path"]:
        try:
            pdf_bytes = download_bytes(row["storage_path"])
            st.download_button(
                f"Download {choice}.pdf", pdf_bytes, file_name=f"{choice}.pdf", mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Could not fetch the PDF from storage: {e}")
    else:
        st.error("No storage path recorded for this voucher.")
