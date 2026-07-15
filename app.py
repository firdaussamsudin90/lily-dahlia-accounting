import re

import streamlit as st

from modules.auth import require_login
from modules.db import get_connection, init_db
from modules.icons import icon
from modules.theme import TEXT_MUTED, TEXT_SECONDARY, html, inject_theme

st.set_page_config(page_title="Lily Dahlia Enterprise — Accounting", page_icon="🧾", layout="wide")
inject_theme()
init_db()
require_login()

# Material Symbols names (Streamlit's built-in outline icon set) — used only for
# the sidebar nav, since it must render inside a real, reliably-clickable
# st.button rather than the custom SVG overlay used everywhere else on the page.
PAGES = {
    "OVERVIEW": [
        ("pages/0_Dashboard.py", "Dashboard", "grid_view", True),
    ],
    "DATA ENTRY": [
        ("pages/1_Upload_Statement.py", "Upload Statement", "upload", False),
        ("pages/8_Upload_Documents.py", "Upload Documents", "note_add", False),
    ],
    "RECONCILIATION": [
        ("pages/2_Review_Queue.py", "Review Queue", "search", False),
        ("pages/4_Outstanding_Documents.py", "Outstanding Documents", "attach_file", False),
    ],
    "RECORDS": [
        ("pages/3_Transactions.py", "Transactions", "receipt_long", False),
        ("pages/5_Vouchers.py", "Vouchers", "description", False),
        ("pages/6_Payroll_Register.py", "Payroll Register", "group", False),
    ],
    "SETTINGS": [
        ("pages/7_Categorization_Rules.py", "Categorization Rules", "settings", False),
    ],
}

st_pages = {
    section: [st.Page(path, title=title, default=is_default) for path, title, _icon, is_default in items]
    for section, items in PAGES.items()
}
nav = st.navigation(st_pages, position="hidden")

# --------------------------------------------------------- pending badges --
conn = get_connection()
review_count = conn.execute(
    "SELECT COUNT(*) AS count FROM transactions WHERE category IS NULL OR flag_color = 'red'"
).fetchone()["count"]
outstanding_count = conn.execute(
    "SELECT COUNT(*) AS count FROM transactions WHERE needs_document = TRUE AND document_id IS NULL"
).fetchone()["count"]
conn.close()
BADGES = {"Review Queue": review_count, "Outstanding Documents": outstanding_count}


def slug(text):
    return re.sub(r"[^a-zA-Z0-9]", "_", text)


def nav_row(page, material_icon, badge_count, active):
    label = f"{page.title}   ·  {badge_count}" if badge_count else page.title
    key_prefix = "navactive" if active else "navrow"
    row_key = f"{key_prefix}_{slug(page.title)}"
    with st.container(key=row_key):
        if st.button(label, icon=f":material/{material_icon}:", key=f"btn_{row_key}", use_container_width=True):
            st.switch_page(page)


with st.sidebar:
    st.markdown(
        html(f"""
        <div class="dg-sidebar-logo">
            <span class="dg-icon-square" style="background:#1F4D3C;">{icon("sparkle", size=18, color="#fff")}</span>
            <div>
                <div style="font-weight:800;font-size:1.05rem;color:#15171A;line-height:1.1;">Demiglow</div>
                <div style="font-size:0.72rem;color:{TEXT_MUTED};">Lily Dahlia Enterprise</div>
            </div>
        </div>
        """),
        unsafe_allow_html=True,
    )

    for section, items in PAGES.items():
        st.markdown(f'<div class="dg-sidebar-section">{section}</div>', unsafe_allow_html=True)
        for page_obj, (path, title, material_icon, _default) in zip(st_pages[section], items):
            nav_row(page_obj, material_icon, BADGES.get(title), active=(nav.title == title))

    st.markdown('<div class="dg-sidebar-section">GENERAL</div>', unsafe_allow_html=True)
    settings_page = st_pages["SETTINGS"][0]
    with st.container(key="navrow_general_settings"):
        if st.button("Settings", icon=":material/settings:", key="btn_general_settings", use_container_width=True):
            st.switch_page(settings_page)
    with st.container(key="navrow_general_help"):
        if st.button("Help", icon=":material/help:", key="btn_general_help", use_container_width=True):
            st.toast("Need a hand? Ping Firdaus, or check Getting_Started_Guide.md in the repo.", icon="💬")
    with st.container(key="navrow_general_logout"):
        if st.button("Logout", icon=":material/logout:", key="btn_general_logout", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

# --------------------------------------------------------------- top bar ---
st.markdown(
    html(f"""
    <div class="dg-topbar">
        <div class="dg-search">
            {icon("search", size=16, color=TEXT_MUTED)}
            <span>Search…</span>
            <span class="dg-kbd">⌘F</span>
        </div>
        <div class="dg-topbar-icons">
            {icon("mail", size=19, color=TEXT_SECONDARY)}
            {icon("bell", size=19, color=TEXT_SECONDARY)}
            <div class="dg-avatar">
                <div class="dg-avatar-circle">FD</div>
                <div>
                    <div style="font-weight:700;font-size:0.85rem;color:#15171A;">Firdaus</div>
                    <div style="font-size:0.74rem;color:{TEXT_MUTED};">m.firdaussamsudin@gmail.com</div>
                </div>
            </div>
        </div>
    </div>
    """),
    unsafe_allow_html=True,
)

nav.run()
