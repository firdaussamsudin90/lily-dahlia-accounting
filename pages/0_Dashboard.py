import altair as alt
import pandas as pd
import streamlit as st

from modules.db import get_connection, init_db
from modules.auth import require_login

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
init_db()
require_login()

EXPENSE_CATEGORIES = ["COGS", "Operating Expenses", "Staff Cost", "Logistics", "Marketing"]

# Categorical slots from the shared dark-mode palette — kept fixed per metric
# (not cycled) so Sales/Expenses/Ad Spend always read the same color everywhere.
COLOR_SALES = "#3987e5"     # blue
COLOR_EXPENSES = "#e66767"  # red
COLOR_ADS = "#9085e9"       # violet
COLOR_GOOD = "#0ca30c"
COLOR_BAD = "#e34948"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRIDLINE = "#333331"

st.markdown(
    """
    <style>
    .stat-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 18px 20px;
        position: relative;
        overflow: hidden;
    }
    .stat-card::before {
        content: "";
        position: absolute;
        left: 0; top: 0; bottom: 0;
        width: 4px;
        background: var(--accent);
    }
    .stat-icon { font-size: 20px; margin-bottom: 6px; }
    .stat-label {
        font-size: 12px; font-weight: 600; text-transform: uppercase;
        letter-spacing: .05em; color: #a3a2a0; margin-bottom: 4px;
    }
    .stat-value { font-size: 26px; font-weight: 700; color: #ffffff; line-height: 1.2; }
    .stat-delta { font-size: 13px; margin-top: 4px; }
    .stat-delta.up { color: #0ca30c; }
    .stat-delta.down { color: #e34948; }
    .stat-delta.flat { color: #898781; }
    </style>
    """,
    unsafe_allow_html=True,
)


def stat_card(icon, label, value_str, accent, delta_str=None, delta_dir="flat"):
    delta_html = f'<div class="stat-delta {delta_dir}">{delta_str}</div>' if delta_str else ""
    st.markdown(
        f"""
        <div class="stat-card" style="--accent: {accent}">
            <div class="stat-icon">{icon}</div>
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value_str}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def themed(chart):
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=GRIDLINE, domainColor=GRIDLINE, tickColor=GRIDLINE,
            labelColor=INK_SECONDARY, titleColor=INK_MUTED, labelFontSize=11, titleFontSize=12,
        )
        .configure_legend(labelColor=INK_SECONDARY, titleColor=INK_MUTED, symbolSize=80)
        .properties(background="transparent")
    )


st.title("📊 Dashboard")

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
net = sales - expenses

# Month-over-month delta: only meaningful when the two most recent selected
# months are actually adjacent in the data, so compare against the prior
# selected month's totals rather than implying a trend from a single point.
revenue_by_month = revenue_rows.groupby("month")[["credit", "debit"]].sum()
monthly = pd.DataFrame({
    "Sales": revenue_by_month["credit"] - revenue_by_month["debit"],
    "Expenses": df.loc[df["category"].isin(EXPENSE_CATEGORIES)].groupby("month")["debit"].sum(),
    "Ad Spend": df.loc[df["category"] == "Marketing"].groupby("month")["debit"].sum(),
}).fillna(0).sort_index()


def month_delta(series):
    if len(series) < 2:
        return None, "flat"
    prev, latest = series.iloc[-2], series.iloc[-1]
    if prev == 0:
        return None, "flat"
    pct = (latest - prev) / abs(prev) * 100
    direction = "up" if pct > 0 else ("down" if pct < 0 else "flat")
    return f"{'▲' if pct > 0 else '▼' if pct < 0 else '—'} {abs(pct):,.1f}% vs {series.index[-2]}", direction


sales_delta, sales_dir = month_delta(monthly["Sales"])
expenses_delta, expenses_dir = month_delta(monthly["Expenses"])
# Rising expenses is bad, not good — flip the color semantics vs the raw direction.
expenses_dir = {"up": "down", "down": "up", "flat": "flat"}[expenses_dir]
ads_delta, ads_dir = month_delta(monthly["Ad Spend"])

c1, c2, c3, c4 = st.columns(4)
with c1:
    stat_card("💰", "Sales", f"RM {sales:,.2f}", COLOR_SALES, sales_delta, sales_dir)
with c2:
    stat_card("💸", "Expenses", f"RM {expenses:,.2f}", COLOR_EXPENSES, expenses_delta, expenses_dir)
with c3:
    stat_card("📣", "Ad Spend", f"RM {ads_spend:,.2f}", COLOR_ADS, ads_delta, ads_dir)
with c4:
    stat_card("📈" if net >= 0 else "📉", "Net", f"RM {net:,.2f}", COLOR_GOOD if net >= 0 else COLOR_BAD)

st.divider()
st.subheader("Sales vs Expenses vs Ad Spend by month")

monthly_long = monthly.reset_index().melt("month", var_name="Metric", value_name="Amount")
color_scale = alt.Scale(domain=["Sales", "Expenses", "Ad Spend"], range=[COLOR_SALES, COLOR_EXPENSES, COLOR_ADS])
trend_chart = (
    alt.Chart(monthly_long)
    .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=16)
    .encode(
        x=alt.X("month:N", title=None, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("Metric:N", sort=["Sales", "Expenses", "Ad Spend"]),
        y=alt.Y("Amount:Q", title="RM"),
        color=alt.Color("Metric:N", scale=color_scale, sort=["Sales", "Expenses", "Ad Spend"],
                         legend=alt.Legend(title=None, orient="top")),
        tooltip=["month", "Metric", alt.Tooltip("Amount:Q", format=",.2f")],
    )
    .properties(height=320)
)
st.altair_chart(themed(trend_chart), use_container_width=True)

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Expenses by category")
    by_category = (
        df.loc[df["category"].isin(EXPENSE_CATEGORIES)]
        .groupby("category")["debit"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    by_category.columns = ["Category", "Amount"]
    cat_chart = (
        alt.Chart(by_category)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3, size=16, color=COLOR_EXPENSES)
        .encode(
            y=alt.Y("Category:N", sort="-x", title=None),
            x=alt.X("Amount:Q", title="RM"),
            tooltip=["Category", alt.Tooltip("Amount:Q", format=",.2f")],
        )
        .properties(height=max(28 * len(by_category) + 40, 120))
    )
    st.altair_chart(themed(cat_chart), use_container_width=True)
with col2:
    st.subheader("Ad spend by channel")
    ads_by_channel = (
        df.loc[df["category"] == "Marketing"]
        .groupby("subcategory")["debit"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    ads_by_channel.columns = ["Channel", "Amount"]
    if ads_by_channel.empty:
        st.info("No ad spend in this period.")
    else:
        ads_chart = (
            alt.Chart(ads_by_channel)
            .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3, size=16, color=COLOR_ADS)
            .encode(
                y=alt.Y("Channel:N", sort="-x", title=None),
                x=alt.X("Amount:Q", title="RM"),
                tooltip=["Channel", alt.Tooltip("Amount:Q", format=",.2f")],
            )
            .properties(height=max(28 * len(ads_by_channel) + 40, 120))
        )
        st.altair_chart(themed(ads_chart), use_container_width=True)

st.divider()
st.subheader("Category breakdown")
breakdown = df.groupby("category").agg(sales=("credit", "sum"), expenses=("debit", "sum")).reset_index()
breakdown = breakdown.sort_values("expenses", ascending=False)
st.dataframe(
    breakdown,
    width="stretch",
    hide_index=True,
    column_config={
        "category": st.column_config.TextColumn("Category"),
        "sales": st.column_config.NumberColumn("Sales (RM)", format="%.2f"),
        "expenses": st.column_config.NumberColumn("Expenses (RM)", format="%.2f"),
    },
)
