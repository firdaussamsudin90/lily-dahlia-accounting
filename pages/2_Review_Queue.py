import calendar
from collections import defaultdict

import streamlit as st

from modules.auth import require_login
from modules.db import get_connection, init_db

st.set_page_config(page_title="Review Queue", page_icon="🔎", layout="wide")
init_db()
require_login()
st.title("🔎 Review Queue")
st.caption(
    "Transactions that matched no categorization rule, or are flagged red per a standing rule "
    "(e.g. Shopee Mobile Malaysia, SPayLater) that always needs owner confirmation."
)

CATEGORIES = [
    "Revenue", "COGS", "Marketing", "Staff Cost", "Owner Transactions", "Operating Expenses",
    "Logistics", "Financing", "Personal/Non-business", "Admin & Bank", "Uncategorized",
]
FLAGS = [None, "yellow", "red"]


def month_label(month_str):
    year, month_num = month_str.split("-")
    return f"{calendar.month_name[int(month_num)]} {year}"


def render_review_row(r):
    label = (
        f"{r['date']} — {r['counterparty'] or '(no counterparty)'} — "
        f"RM{(r['debit'] or r['credit'] or 0):,.2f}"
    )
    with st.expander(label):
        c1, c2 = st.columns(2)
        c1.write(f"**Note:** {r['note'] or '—'}")
        c1.write(f"**Debit:** {r['debit']}  **Credit:** {r['credit']}  **Balance:** {r['running_balance']}")
        c1.write(f"**Current flag note:** {r['flag_note'] or '—'}")

        with c2.form(key=f"form_{r['id']}"):
            category = st.selectbox(
                "Category", options=CATEGORIES,
                index=CATEGORIES.index(r["category"]) if r["category"] in CATEGORIES else 0,
                key=f"cat_{r['id']}",
            )
            subcategory = st.text_input("Subcategory", value=r["subcategory"] or "", key=f"sub_{r['id']}")
            flag = st.selectbox(
                "Flag", options=FLAGS,
                index=FLAGS.index(r["flag_color"]) if r["flag_color"] in FLAGS else 0,
                format_func=lambda f: f or "none", key=f"flag_{r['id']}",
            )
            flag_note = st.text_input("Flag note", value=r["flag_note"] or "", key=f"flagnote_{r['id']}")
            needs_document = st.checkbox(
                "Needs supporting document", value=bool(r["needs_document"]), key=f"needsdoc_{r['id']}"
            )
            submitted = st.form_submit_button("Save")
            if submitted:
                conn = get_connection()
                conn.execute(
                    """UPDATE transactions
                       SET category=%s, subcategory=%s, flag_color=%s, flag_note=%s, needs_document=%s
                       WHERE id=%s""",
                    (category, subcategory or None, flag, flag_note or None,
                     bool(needs_document), r["id"]),
                )
                conn.commit()
                conn.close()
                st.success("Saved.")
                st.rerun()


conn = get_connection()
rows = conn.execute(
    """SELECT * FROM transactions
       WHERE category IS NULL OR flag_color = 'red'
       ORDER BY month DESC, date ASC"""
).fetchall()
conn.close()

if not rows:
    st.success("Nothing to review — every transaction is categorized and no red flags are outstanding.")
    st.stop()

st.write(f"**{len(rows)}** transaction(s) need attention.")

by_month = defaultdict(list)
for r in rows:
    by_month[r["month"]].append(dict(r))

months = sorted(by_month.keys(), reverse=True)
tabs = st.tabs([f"{month_label(m)} ({len(by_month[m])})" for m in months])
for tab, month in zip(tabs, months):
    with tab:
        for r in by_month[month]:
            render_review_row(r)
