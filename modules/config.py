"""Reads config/secrets from Streamlit secrets (Streamlit Community Cloud) or
environment variables (local dev), in that order. Centralized so every module
that needs a credential goes through the same lookup."""
import os


def get_secret(name, default=None):
    try:
        import streamlit as st
        if hasattr(st, "secrets") and name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)
