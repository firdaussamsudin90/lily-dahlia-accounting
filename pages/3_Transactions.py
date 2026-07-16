import pandas as pd
import streamlit as st

from modules.balance_verifier import recalculate_running_balances
from modules.db import get_connection, init_db
from modules.auth import require_login
from modules.storage import download_bytes

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}

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

# Postgres NUMERIC columns come back as decimal.Decimal via psycopg2 — convert to
# float before this DataFrame goes anywhere near st.dataframe()/Arrow, since mixing
# Decimal into a pyarrow-backed pandas DataFrame can crash the process outright.
for col in ["debit", "credit", "running_balance"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

total_debit = df["debit"].fillna(0).sum()
total_credit = df["credit"].fillna(0).sum()
m1, m2, m3 = st.columns(3)
m1.metric("Transactions", len(df))
m2.metric("Total debit (RM)", f"{total_debit:,.2f}")
m3.metric("Total credit (RM)", f"{total_credit:,.2f}")

conn = get_connection()
statements = conn.execute(
    f"""SELECT month, opening_balance, closing_balance FROM bank_statements
        WHERE month IN ({','.join('%s' for _ in month_filter)}) ORDER BY month""",
    month_filter,
).fetchall() if month_filter else []
conn.close()
if statements:
    st.caption("Opening → closing balance per statement, for reference against your bank account:")
    for s in statements:
        st.caption(f"**{s['month']}**: RM{s['opening_balance']:,.2f} → RM{s['closing_balance']:,.2f}")

display_cols = [
    "id", "date", "counterparty", "note", "debit", "credit", "running_balance",
    "category", "subcategory", "flag_color", "needs_document", "document_id",
]
st.dataframe(df[display_cols], width="stretch", height=600)

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

        if row["document_id"]:
            doc_conn = get_connection()
            doc = doc_conn.execute("SELECT * FROM documents WHERE id = %s", (row["document_id"],)).fetchone()
            doc_conn.close()
            if doc:
                doc = dict(doc)
                st.markdown(
                    f"**Attached document:** {doc['filename'] or '(manual reference)'}"
                    + (f" — _{doc['caption']}_" if doc["caption"] else "")
                )
                if doc["storage_path"]:
                    doc_bytes = download_bytes(doc["storage_path"])
                    ext = (doc["filename"] or "").rsplit(".", 1)[-1].lower()
                    if ext in IMAGE_EXTS:
                        st.image(doc_bytes, width=460)
                    st.download_button(
                        "Download attached document", doc_bytes,
                        file_name=doc["filename"] or f"document_{doc['id']}", key=f"dl_doc_{doc['id']}",
                    )
                else:
                    st.caption(f"Manual reference: {doc['notes'] or '(no notes)'}")

        st.caption(
            "Correcting the date/counterparty/note/debit/credit here is for fixing a bank statement "
            "parsing mistake (wrong text or amount pulled from the PDF) — after saving, the running "
            "balance for every transaction in this month is recalculated from the statement's opening "
            "balance, so the chain stays consistent."
        )
        with st.form("edit_txn"):
            d1, d2 = st.columns(2)
            txn_date = d1.text_input("Date (YYYY-MM-DD)", value=row["date"] or "")
            counterparty = d2.text_input("Counterparty", value=row["counterparty"] or "")
            note = st.text_input("Note", value=row["note"] or "")
            a1, a2 = st.columns(2)
            debit = a1.number_input(
                "Debit (RM) — 0 if this is a credit", min_value=0.0, format="%.2f",
                value=float(row["debit"]) if row["debit"] else 0.0,
            )
            credit = a2.number_input(
                "Credit (RM) — 0 if this is a debit", min_value=0.0, format="%.2f",
                value=float(row["credit"]) if row["credit"] else 0.0,
            )

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
                if debit > 0 and credit > 0:
                    st.error("A transaction can't be both a debit and a credit — set one of them to 0.")
                else:
                    conn = get_connection()
                    conn.execute(
                        """UPDATE transactions SET date=%s, counterparty=%s, note=%s, debit=%s, credit=%s,
                           category=%s, subcategory=%s, flag_color=%s, flag_note=%s, needs_document=%s
                           WHERE id=%s""",
                        (txn_date, counterparty or None, note or None, debit or None, credit or None,
                         category or None, subcategory or None, flag_color or None, flag_note or None,
                         bool(needs_document), edit_id),
                    )
                    conn.commit()
                    final_balance, closing_balance = recalculate_running_balances(conn, row["month"])
                    conn.close()
                    st.success("Updated — running balances for this month recalculated.")
                    if final_balance is not None and abs(final_balance - closing_balance) > 0.01:
                        st.warning(
                            f"Heads up: after recalculating, the month now ends at RM{final_balance:,.2f}, "
                            f"but the statement's printed closing balance is RM{closing_balance:,.2f} "
                            f"(diff RM{final_balance - closing_balance:,.2f}). That usually means another "
                            "transaction in this month also has a wrong amount — check the Upload Statement "
                            "page's original PDF against this month's transactions for the difference."
                        )
                    st.rerun()
