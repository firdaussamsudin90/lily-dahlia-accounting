import streamlit as st

st.set_page_config(page_title="Lily Dahlia Enterprise — Accounting", page_icon="🧾", layout="wide")

# Section headers render via Streamlit's own st.navigation grouping (below); this
# just enforces the small/muted/letter-spaced look on top of the default style.
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(250, 250, 250, 0.45);
        margin-top: 1.1rem;
        margin-bottom: 0.15rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

pages = {
    "OVERVIEW": [
        st.Page("pages/00_Home.py", title="Home", icon="🏠", default=True),
        st.Page("pages/0_Dashboard.py", title="Dashboard", icon="📊"),
    ],
    "DATA ENTRY": [
        st.Page("pages/1_Upload_Statement.py", title="Upload Statement", icon="📤"),
        st.Page("pages/8_Upload_Documents.py", title="Upload Documents", icon="📥"),
    ],
    "RECONCILIATION": [
        st.Page("pages/2_Review_Queue.py", title="Review Queue", icon="🔎"),
        st.Page("pages/4_Outstanding_Documents.py", title="Outstanding Documents", icon="📎"),
    ],
    "RECORDS": [
        st.Page("pages/3_Transactions.py", title="Transactions", icon="📒"),
        st.Page("pages/5_Vouchers.py", title="Vouchers", icon="🧾"),
        st.Page("pages/6_Payroll_Register.py", title="Payroll Register", icon="👥"),
    ],
    "SETTINGS": [
        st.Page("pages/7_Categorization_Rules.py", title="Categorization Rules", icon="⚙️"),
    ],
}

st.navigation(pages).run()
