import calendar
from datetime import date

import pandas as pd
import streamlit as st

from modules.db import get_connection, init_db
from modules.auth import require_login
from modules.payroll_register import generate_and_save, get_saved_register

init_db()
require_login()
st.title("👥 Monthly Payroll Register")
st.caption(
    "Every person paid this month — staff wages, live host wages, owner drawings — as line items. "
    "No statutory deduction columns (EPF/SOCSO/EIS); all staff are informal/casual per the owner."
)

conn = get_connection()
months = [r["month"] for r in conn.execute("SELECT DISTINCT month FROM transactions ORDER BY month").fetchall()]
conn.close()

if not months:
    st.info("No transactions yet — upload a statement first.")
    st.stop()

month = st.selectbox("Month", options=months, index=len(months) - 1)

if st.button("Generate / Regenerate register for this month", type="primary"):
    generate_and_save(month)
    st.success("Payroll register generated.")

lines = get_saved_register(month)

if not lines:
    st.info("No payroll register generated for this month yet — click the button above.")
    st.stop()

df = pd.DataFrame(lines)[["person_name", "role", "amount", "notes"]]
df.columns = ["Person", "Role", "Amount (RM)", "Notes"]

st.dataframe(df, width="stretch")

total = df["Amount (RM)"].sum()
st.metric("Total payroll this month (RM)", f"{total:,.2f}")

by_role = df.groupby("Role")["Amount (RM)"].sum()
cols = st.columns(len(by_role) or 1)
for col, (role, amt) in zip(cols, by_role.items()):
    col.metric(role.replace("_", " ").title(), f"RM {amt:,.2f}")

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Download as CSV", csv, file_name=f"payroll_register_{month}.csv", mime="text/csv")
