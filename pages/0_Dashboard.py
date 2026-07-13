import pandas as pd
import streamlit as st

from modules.db import get_connection, init_db
from modules.auth import require_login

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
init_db()
require_login()
st.title("📊 Dashboard")

EXPENSE_CATEGORIES = ["COGS", "Operating Expenses", "Staff Cost", "Logistics", "Marketing"]

conn = get_connection()
months = [r["month"] for r in conn.execute("SELECT DISTINCT month FROM transactions ORDER BY month").fetchall()]
conn.close()

if not months:
    st.info("No transactions yet — upload a statement first.")
    st.stop()

month_filter = st.multiselect("Month", options=months, default=months)
if not month_filter:
    st.info("Select at least one month.")
    st.stop()

conn = get_connection()
rows = conn.execute(
    f"""SELECT month, category, subcategory, debit, credit FROM transactions
        WHERE month IN ({','.join('%s' for _ in month_filter)})""",
    month_filter,
).fetchall()
conn.close()

df = pd.DataFrame([dict(r) for r in rows])
if df.empty:
    st.info("No transactions match this filter.")
    st.stop()

# Postgres NUMERIC columns come back as decimal.Decimal via psycopg2 — convert to
# float before this DataFrame goes anywhere near st.dataframe()/Arrow/charts, since
# mixing Decimal into a pyarrow-backed pandas DataFrame can crash the process outright.
for col in ["debit", "credit"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

revenue_rows = df.loc[df["category"] == "Revenue"]
sales = revenue_rows["credit"].sum() - revenue_rows["debit"].sum()  # nets out refunds, also filed under Revenue
expenses = df.loc[df["category"].isin(EXPENSE_CATEGORIES), "debit"].sum()
ads_spend = df.loc[df["category"] == "Marketing", "debit"].sum()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Sales (RM)", f"{sales:,.2f}")
m2.metric("Expenses (RM)", f"{expenses:,.2f}")
m3.metric("Ad Spend (RM)", f"{ads_spend:,.2f}")
m4.metric("Net (RM)", f"{sales - expenses:,.2f}")

st.divider()
st.subheader("Sales vs Expenses vs Ad Spend by month")

revenue_by_month = revenue_rows.groupby("month")[["credit", "debit"]].sum()
monthly = pd.DataFrame({
    "Sales": revenue_by_month["credit"] - revenue_by_month["debit"],
    "Expenses": df.loc[df["category"].isin(EXPENSE_CATEGORIES)].groupby("month")["debit"].sum(),
    "Ad Spend": df.loc[df["category"] == "Marketing"].groupby("month")["debit"].sum(),
}).fillna(0).sort_index()
st.bar_chart(monthly)

st.divider()
c1, c2 = st.columns(2)
with c1:
    st.subheader("Expenses by category")
    by_category = (
        df.loc[df["category"].isin(EXPENSE_CATEGORIES)]
        .groupby("category")["debit"].sum()
        .sort_values(ascending=False)
    )
    st.bar_chart(by_category)
with c2:
    st.subheader("Ad spend by channel")
    ads_by_channel = (
        df.loc[df["category"] == "Marketing"]
        .groupby("subcategory")["debit"].sum()
        .sort_values(ascending=False)
    )
    if ads_by_channel.empty:
        st.info("No ad spend in this period.")
    else:
        st.bar_chart(ads_by_channel)

st.divider()
st.subheader("Category breakdown")
breakdown = df.groupby("category").agg(sales=("credit", "sum"), expenses=("debit", "sum")).reset_index()
breakdown = breakdown.sort_values("expenses", ascending=False)
st.dataframe(breakdown, width="stretch", hide_index=True)
