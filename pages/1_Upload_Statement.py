import calendar
import tempfile
from datetime import date, datetime

import pandas as pd
import streamlit as st

from modules.balance_verifier import verify
from modules.bank_statement_parser import parse_statement
from modules.categorizer import categorize_transactions
from modules.db import get_connection, init_db
from modules.auth import require_login
from modules.storage import upload_bytes

st.set_page_config(page_title="Upload Statement", page_icon="📤", layout="wide")
init_db()
require_login()
st.title("📤 Upload Bank Statement")

st.markdown(
    "Upload the month's Maybank statement PDF. The app extracts every transaction, verifies the "
    "balance chain against the printed opening/closing balance, and auto-categorizes using the "
    "rules ported from the Category Reference tab. **The balance chain must reconcile with zero "
    "discrepancy before anything can be saved** — this mirrors the manual process being replaced."
)

col_a, col_b = st.columns(2)
this_year = date.today().year
year = col_a.selectbox("Statement year", options=list(range(this_year - 2, this_year + 2)), index=2)
month_num = col_b.selectbox(
    "Statement month", options=list(range(1, 13)),
    format_func=lambda m: calendar.month_name[m], index=date.today().month - 1
)
month_str = f"{year:04d}-{month_num:02d}"

uploaded_pdf = st.file_uploader("Bank statement PDF", type=["pdf"])

if uploaded_pdf is not None:
    conn = get_connection()
    existing = conn.execute("SELECT * FROM bank_statements WHERE month = %s", (month_str,)).fetchone()
    conn.close()

    if existing and not st.session_state.get("confirm_replace_" + month_str):
        st.warning(
            f"A statement for {month_str} was already uploaded and verified "
            f"(closing balance RM{existing['closing_balance']:,.2f}). Uploading again will delete "
            f"that month's transactions, documents, and vouchers and replace them."
        )
        if st.button(f"Replace existing data for {month_str}"):
            st.session_state["confirm_replace_" + month_str] = True
            st.rerun()
        st.stop()

    pdf_bytes = uploaded_pdf.getvalue()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        with st.spinner("Parsing PDF..."):
            parsed = parse_statement(tmp.name, year_hint=year, month_hint=month_num)

    st.caption(f"Extraction method used: **{parsed['method']}**")

    oc1, oc2 = st.columns(2)
    opening_balance = oc1.number_input(
        "Opening balance (RM) — edit if not detected correctly",
        value=float(parsed["opening_balance"]) if parsed["opening_balance"] is not None else 0.0,
        format="%.2f",
    )
    closing_balance = oc2.number_input(
        "Closing balance (RM) — edit if not detected correctly",
        value=float(parsed["closing_balance"]) if parsed["closing_balance"] is not None else 0.0,
        format="%.2f",
    )

    if not parsed["transactions"]:
        st.error("No transactions could be parsed from this PDF. Try a different export/format.")
        st.stop()

    st.subheader(f"Parsed transactions ({len(parsed['transactions'])}) — review and fix before saving")
    st.caption(
        "Edit any cell that looks wrong (especially Counterparty/Note if the extraction method was "
        "'text' — those aren't split from a real column in that fallback path)."
    )

    df = pd.DataFrame(parsed["transactions"])
    for col in ["date", "counterparty", "note", "debit", "credit", "running_balance"]:
        if col not in df.columns:
            df[col] = None
    df = df[["date", "counterparty", "note", "debit", "credit", "running_balance"]]

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "date": st.column_config.TextColumn("Date"),
            "counterparty": st.column_config.TextColumn("Counterparty"),
            "note": st.column_config.TextColumn("Transaction Note"),
            "debit": st.column_config.NumberColumn("Debit (RM)", format="%.2f"),
            "credit": st.column_config.NumberColumn("Credit (RM)", format="%.2f"),
            "running_balance": st.column_config.NumberColumn("Balance (RM)", format="%.2f"),
        },
        key="txn_editor",
    )

    transactions = edited_df.to_dict("records")
    for t in transactions:
        t["debit"] = float(t["debit"]) if t.get("debit") not in (None, "") else None
        t["credit"] = float(t["credit"]) if t.get("credit") not in (None, "") else None
        t["running_balance"] = float(t["running_balance"]) if t.get("running_balance") not in (None, "") else None

    st.subheader("Balance chain verification")
    result = verify(opening_balance, closing_balance, transactions)

    if not result["ok"]:
        st.error("❌ Balance chain does NOT reconcile — fix the transactions above before saving.")
        for e in result["errors"]:
            st.write("- " + e)
        if result["row_errors"]:
            st.dataframe(pd.DataFrame(result["row_errors"]), use_container_width=True)
        st.stop()

    st.success("✅ Balance chain reconciles: opening balance → every transaction → closing balance, exactly.")

    st.subheader("Auto-categorization preview")
    categorized = categorize_transactions([dict(t) for t in transactions])
    preview_df = pd.DataFrame(categorized)[
        ["date", "counterparty", "note", "debit", "credit", "category", "subcategory", "flag_color"]
    ]
    st.dataframe(preview_df, use_container_width=True)

    n_uncategorized = sum(1 for t in categorized if t["category"] is None)
    n_red = sum(1 for t in categorized if t["flag_color"] == "red")
    st.caption(
        f"{n_uncategorized} transaction(s) matched no rule (will land in Review Queue), "
        f"{n_red} flagged red for confirmation."
    )

    if st.button("💾 Save this statement", type="primary"):
        conn = get_connection()
        if existing:
            old_ids = [r["id"] for r in conn.execute(
                "SELECT id FROM transactions WHERE month = %s", (month_str,)
            ).fetchall()]
            if old_ids:
                q = ",".join("%s" for _ in old_ids)
                # Order matters: vouchers/transactions reference documents, so both must be
                # cleared before documents are deleted, or the FK constraint on
                # transactions.document_id rejects the delete.
                conn.execute(f"DELETE FROM vouchers WHERE transaction_id IN ({q})", old_ids)
                conn.execute(f"DELETE FROM transactions WHERE id IN ({q})", old_ids)
                conn.execute(f"DELETE FROM documents WHERE linked_transaction_id IN ({q})", old_ids)
            conn.execute("DELETE FROM bank_statements WHERE month = %s", (month_str,))

        storage_path = f"statements/{month_str}/{uploaded_pdf.name}"
        upload_bytes(storage_path, pdf_bytes, content_type="application/pdf")

        cur = conn.execute(
            """INSERT INTO bank_statements (month, filename, storage_path, opening_balance, closing_balance,
                                             verified, upload_date)
               VALUES (%s, %s, %s, %s, %s, TRUE, %s) RETURNING id""",
            (month_str, uploaded_pdf.name, storage_path, opening_balance, closing_balance,
             datetime.now().isoformat()),
        )
        statement_id = cur.fetchone()["id"]

        for t in categorized:
            conn.execute(
                """INSERT INTO transactions
                   (month, date, counterparty, note, debit, credit, running_balance,
                    category, subcategory, flag_color, flag_note, needs_document, source, bank_statement_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'bank_statement', %s)""",
                (month_str, t["date"], t.get("counterparty"), t.get("note"), t.get("debit"), t.get("credit"),
                 t.get("running_balance"), t.get("category"), t.get("subcategory"), t.get("flag_color"),
                 t.get("flag_note"), bool(t.get("needs_document", False)), statement_id),
            )
        conn.commit()
        conn.close()
        st.session_state.pop("confirm_replace_" + month_str, None)
        st.success(f"Saved {len(categorized)} transactions for {month_str}.")
        st.balloons()
