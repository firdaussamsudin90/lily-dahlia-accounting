import pandas as pd
import streamlit as st

from modules.db import get_connection, init_db
from modules.auth import require_login

st.set_page_config(page_title="Categorization Rules", page_icon="⚙️", layout="wide")
init_db()
require_login()
st.title("⚙️ Categorization Rules")
st.caption(
    "Seeded from the Category Reference and Reconciliation Notes tabs. Rules are tried in order "
    "(top to bottom, by ID) and the first match wins — keep specific rules above generic ones. "
    "match_field is 'counterparty', 'note', 'both' (pattern format 'COUNTERPARTY_TEXT::NOTE_TEXT'), or "
    "'either' (same pattern checked against both fields). A pattern ending in '*' is a prefix match "
    "(e.g. 'ttads*' matches any note starting with 'ttads')."
)

conn = get_connection()
rows = conn.execute("SELECT * FROM categorization_rules ORDER BY id ASC").fetchall()
conn.close()

df = pd.DataFrame([dict(r) for r in rows])
st.dataframe(df, use_container_width=True, height=600)

st.divider()
st.subheader("Add a new rule")
with st.form("add_rule"):
    c1, c2, c3 = st.columns(3)
    match_pattern = c1.text_input("Match pattern")
    match_field = c2.selectbox("Match field", options=["counterparty", "note", "both", "either"])
    category = c3.text_input("Category")
    c4, c5, c6 = st.columns(3)
    subcategory = c4.text_input("Subcategory")
    default_flag = c5.selectbox("Default flag", options=["", "yellow", "red"])
    needs_document = c6.checkbox("Needs document")
    notes = st.text_area("Notes")
    if st.form_submit_button("Add rule"):
        if not match_pattern or not category:
            st.error("Match pattern and category are required.")
        else:
            conn = get_connection()
            conn.execute(
                """INSERT INTO categorization_rules
                   (match_pattern, match_field, category, subcategory, default_flag, needs_document, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (match_pattern, match_field, category, subcategory or None, default_flag or None,
                 bool(needs_document), notes or None),
            )
            conn.commit()
            conn.close()
            st.success("Rule added — new rules are appended at the end (lowest priority). Re-run "
                       "categorization on affected transactions from the Review Queue if needed.")
            st.rerun()

st.divider()
st.subheader("Delete a rule")
rule_id = st.number_input("Rule ID to delete", min_value=0, step=1)
if rule_id and st.button("Delete rule"):
    conn = get_connection()
    conn.execute("DELETE FROM categorization_rules WHERE id = %s", (rule_id,))
    conn.commit()
    conn.close()
    st.success(f"Deleted rule {rule_id}.")
    st.rerun()
