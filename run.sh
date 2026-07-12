#!/bin/bash
# One-command launcher: activates the venv and starts the app.
cd "$(dirname "$0")"
source venv/bin/activate
streamlit run app.py
