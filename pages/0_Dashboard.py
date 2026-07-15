import calendar
from datetime import datetime, timedelta

import streamlit as st

from modules.auth import require_login
from modules.db import get_connection, init_db
from modules.icons import icon
from modules.theme import AMBER_BG, AMBER_TEXT, FOREST, GRAY_BG, MINT, MINT_LIGHT, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY

init_db()
require_login()

EXPENSE_CATEGORIES = ["COGS", "Operating Expenses", "Staff Cost", "Logistics", "Marketing"]


def month_label(month_str):
    year, month_num = month_str.split("-")
    return f"{calendar.month_name[int(month_num)]} {year}"


def net_revenue(conn, month):
    row = conn.execute(
        "SELECT COALESCE(SUM(credit),0) AS c, COALESCE(SUM(debit),0) AS d "
        "FROM transactions WHERE category = 'Revenue' AND month = %s", (month,),
    ).fetchone()
    return float(row["c"]) - float(row["d"])


def sum_where(conn, month, category):
    row = conn.execute(
        "SELECT COALESCE(SUM(debit),0) AS d FROM transactions WHERE category = %s AND month = %s",
        (category, month),
    ).fetchone()
    return float(row["d"])


def delta_tag(current, previous, solid=False):
    if previous in (None, 0):
        return ""
    pct = (current - previous) / abs(previous) * 100
    arrow = "↑" if pct >= 0 else "↓"
    word = "increased" if pct >= 0 else "decreased"
    cls = "dg-tag-mint-solid" if solid else "dg-tag-mint"
    return f'<span class="dg-tag {cls}">{arrow} {word} {abs(pct):,.0f}% from last month</span>'


def kpi_card(label, value, icon_name, primary=False, tag_html="", note=""):
    card_class = "dg-card-primary" if primary else "dg-card"
    arrow_bg = "rgba(255,255,255,0.18)" if primary else "#fff"
    arrow_border = "none" if primary else f"1px solid {TEXT_PRIMARY}"
    arrow_color = "#fff" if primary else TEXT_PRIMARY
    label_color = "rgba(255,255,255,0.85)" if primary else TEXT_SECONDARY
    note_html = f'<div style="font-size:0.78rem;color:{label_color};margin-top:8px;">{note}</div>' if note else ""
    st.markdown(
        f"""
        <div class="{card_class}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div style="font-size:0.85rem;color:{label_color};font-weight:600;">{label}</div>
                <span class="dg-icon-circle" style="width:34px;height:34px;background:{arrow_bg};
                    border:{arrow_border};">{icon(icon_name, size=15, color=arrow_color)}</span>
            </div>
            <div style="font-size:1.9rem;font-weight:800;margin-top:10px;color:{'#fff' if primary else TEXT_PRIMARY};">
                {value}
            </div>
            {note_html}
            <div style="margin-top:10px;">{tag_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def progress_ring(pct, size=150, stroke=14):
    r = (size - stroke) / 2
    circumference = 2 * 3.14159265 * r
    filled = circumference * (pct / 100)
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="{GRAY_BG}" stroke-width="{stroke}"/>
        <circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="{FOREST}" stroke-width="{stroke}"
            stroke-linecap="round" stroke-dasharray="{filled} {circumference}"
            transform="rotate(-90 {size/2} {size/2})"/>
        <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central"
            font-size="26" font-weight="800" fill="{TEXT_PRIMARY}" font-family="inherit">{pct:.0f}%</text>
    </svg>
    """


def status_pill(txn):
    if txn["document_id"] is not None:
        return f'<span class="dg-status dg-status-completed">Completed</span>'
    if txn["flag_color"] == "red":
        return f'<span class="dg-status dg-status-progress">In Progress</span>'
    if txn["needs_document"]:
        return f'<span class="dg-status dg-status-pending">Pending</span>'
    return f'<span class="dg-status dg-status-completed">Completed</span>'


def initials(name):
    if not name:
        return "—"
    parts = [p for p in name.split() if p]
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()


conn = get_connection()
months = [r["month"] for r in conn.execute("SELECT DISTINCT month FROM transactions ORDER BY month").fetchall()]

if not months:
    conn.close()
    st.markdown('<div class="dg-page-title">Dashboard</div>', unsafe_allow_html=True)
    st.info("No transactions yet — upload a statement first.")
    st.stop()

latest_month = months[-1]
prev_month = months[-2] if len(months) > 1 else None

sales_now = net_revenue(conn, latest_month)
sales_prev = net_revenue(conn, prev_month) if prev_month else None
ads_now = sum_where(conn, latest_month, "Marketing")
ads_prev = sum_where(conn, prev_month, "Marketing") if prev_month else None

statement = conn.execute(
    "SELECT closing_balance FROM bank_statements WHERE month = %s ORDER BY id DESC LIMIT 1", (latest_month,)
).fetchone()
cash_balance = float(statement["closing_balance"]) if statement else None
prev_statement = (
    conn.execute(
        "SELECT closing_balance FROM bank_statements WHERE month = %s ORDER BY id DESC LIMIT 1", (prev_month,)
    ).fetchone()
    if prev_month else None
)
cash_prev = float(prev_statement["closing_balance"]) if prev_statement else None

outstanding_count = conn.execute(
    "SELECT COUNT(*) AS c FROM transactions WHERE needs_document = TRUE AND document_id IS NULL"
).fetchone()["c"]
flagged_count = conn.execute(
    "SELECT COUNT(*) AS c FROM transactions WHERE flag_color = 'red'"
).fetchone()["c"]

needing_docs = conn.execute("SELECT COUNT(*) AS c FROM transactions WHERE needs_document = TRUE").fetchone()["c"]
resolved_docs = conn.execute(
    "SELECT COUNT(*) AS c FROM transactions WHERE needs_document = TRUE AND document_id IS NOT NULL"
).fetchone()["c"]
reconciliation_pct = (resolved_docs / needing_docs * 100) if needing_docs else 100.0

latest_txn_date = conn.execute("SELECT MAX(date) AS d FROM transactions").fetchone()["d"]
week_start = datetime.strptime(latest_txn_date, "%Y-%m-%d").date()
week_start -= timedelta(days=week_start.weekday())  # Monday of that week
week_days = [week_start + timedelta(days=i) for i in range(7)]
daily_sales = {}
for d in week_days:
    row = conn.execute(
        "SELECT COALESCE(SUM(credit),0) - COALESCE(SUM(debit),0) AS net "
        "FROM transactions WHERE category = 'Revenue' AND date = %s", (d.isoformat(),),
    ).fetchone()
    daily_sales[d] = max(float(row["net"]), 0.0)

recent = conn.execute(
    "SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT 6"
).fetchall()
recent = [dict(r) for r in recent]
conn.close()

# --------------------------------------------------------------- header ----
h1, h2 = st.columns([3, 1.3])
with h1:
    st.markdown('<div class="dg-page-title">Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="dg-page-subtitle">Overview for {month_label(latest_month)} — '
        f'{len(months)} month(s) of data loaded.</div>',
        unsafe_allow_html=True,
    )
with h2:
    b1, b2 = st.columns(2)
    with b1:
        if st.button("＋ Add Entry", key="dash_add_entry", use_container_width=True):
            st.switch_page("pages/8_Upload_Documents.py")
    with b2:
        if st.button("Import Data", key="dash_import", use_container_width=True):
            st.switch_page("pages/1_Upload_Statement.py")

st.write("")

# --------------------------------------------------------------- KPI row ---
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card(
        "Net Sales", f"RM {sales_now:,.0f}", "arrow-up-right", primary=True,
        tag_html=delta_tag(sales_now, sales_prev, solid=True),
    )
with k2:
    kpi_card(
        "Cash Balance", f"RM {cash_balance:,.0f}" if cash_balance is not None else "—", "arrow-up-right",
        tag_html=delta_tag(cash_balance, cash_prev) if cash_balance is not None else "",
    )
with k3:
    kpi_card(
        "Ad Spend", f"RM {ads_now:,.0f}", "arrow-up-right",
        tag_html=delta_tag(ads_now, ads_prev),
    )
with k4:
    kpi_card(
        "Pending Reconciliation", f"{outstanding_count}", "arrow-up-right",
        note=f"{outstanding_count} document(s) awaiting attachment",
    )

st.write("")

# ------------------------------------------------------------ middle row ---
m1, m2 = st.columns([2, 1])
with m1:
    peak_day = max(daily_sales, key=daily_sales.get)
    peak_val = daily_sales[peak_day]
    week_total = sum(daily_sales.values()) or 1
    bars_html = ""
    for d in week_days:
        val = daily_sales[d]
        is_peak = d == peak_day and val > 0
        if val <= 0:
            bar_style = (
                f"background:repeating-linear-gradient(45deg,{GRAY_BG},{GRAY_BG} 4px,#e4e5e4 4px,#e4e5e4 8px);"
            )
            height = 26
        else:
            ratio = val / max(daily_sales.values())
            height = 26 + ratio * 74
            if ratio > 0.66:
                fill = FOREST
            elif ratio > 0.33:
                fill = MINT
            else:
                fill = MINT_LIGHT
            bar_style = f"background:{fill};"
        bubble = ""
        if is_peak:
            pct_share = val / week_total * 100
            bubble = (
                f'<div style="position:absolute;top:-26px;left:50%;transform:translateX(-50%);'
                f'background:{TEXT_PRIMARY};color:#fff;font-size:0.68rem;font-weight:700;'
                f'padding:2px 7px;border-radius:999px;white-space:nowrap;">{pct_share:.0f}%</div>'
            )
        bars_html += f"""
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px;flex:1;">
            <div style="position:relative;height:100px;display:flex;align-items:flex-end;">
                {bubble}
                <div style="width:22px;height:{height}px;border-radius:11px;{bar_style}"></div>
            </div>
            <div style="font-size:0.74rem;color:{TEXT_MUTED};font-weight:600;">{d.strftime('%a')}</div>
        </div>
        """
    st.markdown(
        f"""
        <div class="dg-card">
            <div style="font-weight:700;font-size:1.02rem;color:{TEXT_PRIMARY};">Weekly Sales Activity</div>
            <div style="font-size:0.8rem;color:{TEXT_SECONDARY};margin-bottom:18px;">
                Net sales by day, week of {week_start.strftime('%d %b')}
            </div>
            <div style="display:flex;gap:10px;">{bars_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"""
        <div class="dg-card" style="height:100%;">
            <span class="dg-icon-square" style="background:{AMBER_BG};">{icon("bell", size=17, color=AMBER_TEXT)}</span>
            <div style="font-weight:700;font-size:1.02rem;margin-top:12px;color:{TEXT_PRIMARY};">
                Flagged Items
            </div>
            <div style="font-size:0.83rem;color:{TEXT_SECONDARY};margin:6px 0 16px 0;">
                {flagged_count} transaction(s) are flagged red and waiting on your confirmation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Review Flagged Items", key="dash_review_flagged", use_container_width=True):
        st.switch_page("pages/2_Review_Queue.py")

st.write("")

# ------------------------------------------------------------ bottom row ---
b1, b2 = st.columns([1, 2])
with b1:
    st.markdown(
        f"""
        <div class="dg-card" style="text-align:center;">
            <div style="font-weight:700;font-size:1.02rem;color:{TEXT_PRIMARY};margin-bottom:10px;">
                Reconciliation Progress
            </div>
            <div style="display:flex;justify-content:center;">{progress_ring(reconciliation_pct)}</div>
            <div style="font-size:0.8rem;color:{TEXT_SECONDARY};margin-top:10px;">
                {resolved_docs} of {needing_docs} documents attached
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with b2:
    rows_html = ""
    for t in recent:
        amount = t["debit"] if t["debit"] else t["credit"]
        rows_html += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid {GRAY_BG};">
            <div class="dg-avatar-circle" style="width:34px;height:34px;font-size:0.72rem;">
                {initials(t['counterparty'])}
            </div>
            <div style="flex-grow:1;">
                <div style="font-weight:600;font-size:0.87rem;color:{TEXT_PRIMARY};">
                    {t['counterparty'] or '(no counterparty)'}
                </div>
                <div style="font-size:0.76rem;color:{TEXT_MUTED};">
                    {t['category'] or 'Uncategorized'} · RM {float(amount or 0):,.2f}
                </div>
            </div>
            {status_pill(t)}
        </div>
        """
    st.markdown(
        f"""
        <div class="dg-card">
            <div style="font-weight:700;font-size:1.02rem;color:{TEXT_PRIMARY};margin-bottom:6px;">
                Recent Ledger Entries
            </div>
            {rows_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
