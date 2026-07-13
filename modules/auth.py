"""
Simple password gate. This app used to be reachable only from localhost; now
that it's hosted on a public URL, anyone with the link could otherwise see
real bank transactions, receipts, and vouchers. There's no user-management
need (single user), so a shared password compared against a secret is enough
— call require_login() at the top of every page, before rendering anything.

If APP_PASSWORD isn't configured, the gate is skipped (with a visible
warning) so local development without secrets set up still works.
"""
import streamlit as st

from modules.config import get_secret


def require_login():
    password = get_secret("APP_PASSWORD")
    if not password:
        st.warning(
            "APP_PASSWORD is not set — this app is running with NO password protection. "
            "Set it in .streamlit/secrets.toml (local) or the app's Secrets settings "
            "(Streamlit Community Cloud) before sharing the URL. See Getting_Started_Guide.md.",
            icon="⚠️",
        )
        return

    if st.session_state.get("authenticated"):
        return

    st.title("🧾 Lily Dahlia Enterprise — Accounting")
    entered = st.text_input("Password", type="password")
    if st.button("Log in") or entered:
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        elif entered:
            st.error("Incorrect password.")
    st.stop()
