import streamlit as st

from modules.auth import require_login
from modules.db import get_connection, init_db

init_db()
require_login()

st.title("🧾 Lily Dahlia Enterprise / Demiglow — Accounting")
st.caption("Phase 1: bank statement processing, categorization, outstanding documents, vouchers, payroll register.")

conn = get_connection()
months = [r["month"] for r in conn.execute("SELECT DISTINCT month FROM transactions ORDER BY month").fetchall()]
txn_count = conn.execute("SELECT COUNT(*) AS count FROM transactions").fetchone()["count"]
outstanding_count = conn.execute(
    "SELECT COUNT(*) AS count FROM transactions WHERE needs_document = TRUE AND document_id IS NULL"
).fetchone()["count"]
review_count = conn.execute(
    "SELECT COUNT(*) AS count FROM transactions WHERE category IS NULL OR flag_color = 'red'"
).fetchone()["count"]
voucher_count = conn.execute("SELECT COUNT(*) AS count FROM vouchers").fetchone()["count"]
conn.close()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Months loaded", len(months))
col2.metric("Transactions", txn_count)
col3.metric("Outstanding documents", outstanding_count)
col4.metric("Review queue", review_count)
col5.metric("Vouchers generated", voucher_count)

st.divider()
st.markdown(
    """
    Use the sidebar to navigate:
    - **Upload Statement** — upload a bank statement PDF, verify the balance chain, auto-categorize
    - **Review Queue** — transactions that didn't match a rule, or are flagged red for confirmation
    - **Transactions** — browse/filter/edit every transaction
    - **Outstanding Documents** — attach a document to clear an item and auto-generate its voucher
    - **Vouchers** — download generated Payment/Claim Voucher PDFs
    - **Payroll Register** — monthly register of everyone paid
    - **Categorization Rules** — view/edit the auto-categorization rules
    """
)

if months:
    st.info(f"Months currently loaded: {', '.join(months)}")
else:
    st.warning("No bank statements uploaded yet — start with **Upload Statement** in the sidebar.")
