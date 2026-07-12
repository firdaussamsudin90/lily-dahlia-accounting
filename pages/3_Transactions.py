import pandas as pd
import streamlit as st

from modules.db import get_connection, init_db
from modules.auth import require_login

st.set_page_config(page_title="Transactions", page_icon="📒", layout="wide")
init_db()
require_login()
st.title("📒 Transactions")

conn = get_connection()
months = [r["month"] for r in conn.execute("SELECT DISTINCT month FROM transactions ORDER BY month").fetchall()]
categories = [r["category"] for r in conn.execute(
    "SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category"
).fetchall()]
conn.close()

if not months:
    st.info("No transactions yet — upload a statement first.")
    st.stop()

c1, c2, c3 = st.columns(3)
month_filter = c1.multiselect("Month", options=months, default=months)
category_filter = c2.multiselect("Category", options=categories, default=[])
flag_filter = c3.selectbox("Flag", options=["(all)", "none", "yellow", "red"], index=0)

conn = get_connection()
query = "SELECT * FROM transactions WHERE 1=1"
params = []
if month_filter:
    query += f" AND month IN ({','.join('%s' for _ in month_filter)})"
    params += month_filter
if category_filter:
    query += f" AND category IN ({','.join('%s' for _ in category_filter)})"
    params += category_filter
if flag_filter == "none":
    query += " AND flag_color IS NULL"
elif flag_filter in ("yellow", "red"):
    query += " AND flag_color = %s"
    params.append(flag_filter)
query += " ORDER BY date ASC"

rows = conn.execute(query, params).fetchall()
conn.close()

df = pd.DataFrame([dict(r) for r in rows])
if df.empty:
    st.info("No transactions match this filter.")
    st.stop()

total_debit = df["debit"].fillna(0).sum()
total_credit = df["credit"].fillna(0).sum()
m1, m2, m3 = st.columns(3)
m1.metric("Transactions", len(df))
m2.metric("Total debit (RM)", f"{total_debit:,.2f}")
m3.metric("Total credit (RM)", f"{total_credit:,.2f}")

display_cols = [
    "id", "date", "counterparty", "note", "debit", "credit", "running_balance",
    "category", "subcategory", "flag_color", "needs_document", "document_id",
]
st.dataframe(df[display_cols], use_container_width=True, height=600)

st.divider()
st.subheader("Edit a transaction")
edit_id = st.number_input("Transaction ID", min_value=0, step=1)
if edit_id:
    conn = get_connection()
    row = conn.execute("SELECT * FROM transactions WHERE id = %s", (edit_id,)).fetchone()
    conn.close()
    if row is None:
        st.warning("No transaction with that ID.")
    else:
        row = dict(row)
        with st.form("edit_txn"):
            c1, c2 = st.columns(2)
            category = c1.text_input("Category", value=row["category"] or "")
            subcategory = c1.text_input("Subcategory", value=row["subcategory"] or "")
            flag_color = c2.selectbox(
                "Flag", options=["", "yellow", "red"],
                index=["", "yellow", "red"].index(row["flag_color"] or ""),
            )
            needs_document = c2.checkbox("Needs document", value=bool(row["needs_document"]))
            flag_note = st.text_area("Flag note", value=row["flag_note"] or "")
            if st.form_submit_button("Save changes"):
                conn = get_connection()
                conn.execute(
                    """UPDATE transactions SET category=%s, subcategory=%s, flag_color=%s, flag_note=%s,
                       needs_document=%s WHERE id=%s""",
                    (category or None, subcategory or None, flag_color or None, flag_note or None,
                     bool(needs_document), edit_id),
                )
                conn.commit()
                conn.close()
                st.success("Updated.")
                st.rerun()
