"""
Central design system for the app: color palette + one global CSS injection
(inject_theme(), called once from app.py) so every page picks up the same
look without repeating CSS. Component-specific markup (KPI cards, the
weekly-activity chart, the progress ring, etc.) lives on the pages that use
them, but always through the class names/colors defined here.
"""
import streamlit as st

BG = "#F0F1F0"
CARD_BG = "#FFFFFF"
FOREST = "#1F4D3C"
FOREST_DARK = "#163829"
MINT = "#8FCDB0"
MINT_LIGHT = "#E3F3EA"
TEXT_PRIMARY = "#15171A"
TEXT_SECONDARY = "#6B7280"
TEXT_MUTED = "#9CA3AF"
BORDER = "rgba(15,23,42,0.06)"
SHADOW = "0 2px 12px rgba(0,0,0,0.06)"
AMBER_BG = "#FDECC8"
AMBER_TEXT = "#93650B"
GRAY_BG = "#EEF0F1"
GRAY_TEXT = "#6B7280"
GREEN_BG = "#DFF3E8"
GREEN_TEXT = "#1F4D3C"


def html(s):
    """Flattens a (Python-indented) multi-line HTML string before it goes to
    st.markdown(unsafe_allow_html=True). Two Markdown quirks otherwise bite
    hand-written HTML blocks like these: a line indented 4+ spaces is read as
    a code block instead of HTML, and a line that's blank (e.g. an
    interpolated value that happened to be an empty string) ends the HTML
    block early, dumping everything after it into a stray code block. Both
    are avoided by stripping every line and dropping any that end up empty."""
    return "\n".join(line.strip() for line in s.strip().splitlines() if line.strip())


def inject_theme():
    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background: {BG};
        }}
        [data-testid="stHeader"] {{ display: none; }}
        [data-testid="stMainBlockContainer"], .block-container {{
            padding-top: 1.2rem;
            max-width: 1200px;
        }}
        [data-testid="stSidebar"] {{
            background: {CARD_BG};
            border-right: 1px solid {BORDER};
        }}
        [data-testid="stSidebarNav"] {{ display: none; }}

        h1, h2, h3, h4, .dg-heading {{
            color: {TEXT_PRIMARY} !important;
            font-weight: 700 !important;
        }}
        [data-testid="stCaptionContainer"], .dg-secondary {{ color: {TEXT_SECONDARY}; }}

        /* ---- Cards ---- */
        .dg-card {{
            background: {CARD_BG};
            border-radius: 18px;
            box-shadow: {SHADOW};
            padding: 22px 24px;
            border: 1px solid {BORDER};
        }}
        .dg-card-primary {{
            background: {FOREST};
            color: #FFFFFF;
            border-radius: 18px;
            box-shadow: {SHADOW};
            padding: 22px 24px;
            border: none;
        }}
        .dg-card-primary * {{ color: #FFFFFF !important; }}

        /* ---- Buttons (native Streamlit buttons, restyled as pills) ---- */
        div[data-testid="stButton"] > button, div[data-testid="stFormSubmitButton"] > button {{
            border-radius: 999px !important;
            background: {FOREST} !important;
            color: #FFFFFF !important;
            border: none !important;
            padding: 0.5rem 1.3rem !important;
            font-weight: 600 !important;
            box-shadow: none !important;
        }}
        div[data-testid="stButton"] > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {{
            background: {FOREST_DARK} !important;
            color: #FFFFFF !important;
        }}
        div[data-testid="stButton"] > button[kind="secondary"] {{
            background: #FFFFFF !important;
            color: {TEXT_PRIMARY} !important;
            border: 1px solid {BORDER} !important;
        }}

        /* ---- Inputs ---- */
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
        [data-testid="stTextArea"] textarea, div[data-baseweb="select"] > div {{
            border-radius: 12px !important;
            border-color: {BORDER} !important;
        }}

        /* ---- Cards around dataframes / expanders / metrics ---- */
        [data-testid="stDataFrame"], [data-testid="stExpander"] {{
            border-radius: 16px !important;
            overflow: hidden;
            box-shadow: {SHADOW};
            border: 1px solid {BORDER} !important;
        }}
        [data-testid="stMetric"] {{
            background: {CARD_BG};
            border-radius: 16px;
            padding: 14px 16px;
            box-shadow: {SHADOW};
            border: 1px solid {BORDER};
        }}

        /* ---- Pills / badges / tags ---- */
        .dg-pill-btn {{
            display: inline-flex; align-items: center; gap: 6px;
            border-radius: 999px; padding: 9px 18px; font-weight: 600; font-size: 0.88rem;
            text-decoration: none !important; border: 1px solid transparent;
        }}
        .dg-pill-btn-primary {{ background: {FOREST}; color: #fff !important; }}
        .dg-pill-btn-outline {{ background: #fff; color: {TEXT_PRIMARY} !important; border-color: {BORDER}; }}

        .dg-badge {{
            display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
            min-width: 20px; height: 20px; padding: 0 6px; border-radius: 999px;
            background: {FOREST}; color: #fff; font-size: 0.7rem; font-weight: 700;
        }}
        .dg-tag {{
            display: inline-flex; align-items: center; gap: 4px; border-radius: 999px;
            padding: 4px 10px; font-size: 0.76rem; font-weight: 600;
        }}
        .dg-tag-mint {{ background: {MINT_LIGHT}; color: {FOREST}; }}
        .dg-tag-mint-solid {{ background: rgba(255,255,255,0.22); color: #fff; }}

        .dg-status {{
            display: inline-flex; align-items: center; border-radius: 999px;
            padding: 4px 12px; font-size: 0.76rem; font-weight: 600;
        }}
        .dg-status-completed {{ background: {GREEN_BG}; color: {GREEN_TEXT}; }}
        .dg-status-progress {{ background: {AMBER_BG}; color: {AMBER_TEXT}; }}
        .dg-status-pending {{ background: {GRAY_BG}; color: {GRAY_TEXT}; }}

        /* ---- Icon containers ---- */
        .dg-icon-square {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 38px; height: 38px; border-radius: 12px; flex-shrink: 0;
        }}
        .dg-icon-circle {{
            display: inline-flex; align-items: center; justify-content: center;
            border-radius: 999px; flex-shrink: 0;
        }}

        /* ---- Custom sidebar nav ---- */
        .dg-sidebar-logo {{
            display: flex; align-items: center; gap: 10px; padding: 4px 6px 18px 6px;
        }}
        .dg-sidebar-section {{
            font-size: 0.68rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
            color: {TEXT_MUTED}; margin: 14px 10px 6px 10px;
        }}
        /* Sidebar nav rows are real st.button elements (reliable click targets,
           native Material icon rendering) restyled to look like plain rows —
           transparent/left-aligned by default, tinted + bold + a green left
           edge for whichever one is the current page. */
        div[class*="st-key-navrow_"], div[class*="st-key-navactive_"] {{ margin-bottom: 2px; }}
        div[class*="st-key-navrow_"] div[data-testid="stButton"] > button,
        div[class*="st-key-navactive_"] div[data-testid="stButton"] > button {{
            width: 100% !important; justify-content: flex-start !important; text-align: left !important;
            background: transparent !important; color: {TEXT_PRIMARY} !important; font-weight: 500 !important;
            border: none !important; border-left: 4px solid transparent !important; border-radius: 10px !important;
            padding: 8px 12px !important; box-shadow: none !important;
        }}
        div[class*="st-key-navrow_"] div[data-testid="stButton"] > button:hover {{
            background: {GRAY_BG} !important; color: {TEXT_PRIMARY} !important;
        }}
        div[class*="st-key-navactive_"] div[data-testid="stButton"] > button {{
            background: {MINT_LIGHT} !important; font-weight: 700 !important;
            border-left: 4px solid {FOREST} !important; color: {FOREST} !important;
        }}

        /* ---- Top bar ---- */
        .dg-topbar {{
            display: flex; flex-wrap: nowrap; align-items: center; justify-content: space-between;
            gap: 16px; margin-bottom: 20px; width: 100%;
        }}
        .dg-search {{
            flex: 1 1 auto; min-width: 0; max-width: 380px; display: flex; align-items: center; gap: 8px;
            background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 999px;
            padding: 9px 16px; color: {TEXT_MUTED}; box-shadow: {SHADOW}; overflow: hidden;
        }}
        .dg-search span:first-of-type {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .dg-kbd {{
            margin-left: auto; flex-shrink: 0; font-size: 0.7rem; background: {GRAY_BG}; color: {TEXT_SECONDARY};
            border-radius: 6px; padding: 2px 6px; font-family: monospace;
        }}
        .dg-topbar-icons {{
            display: flex; flex-wrap: nowrap; flex-shrink: 0; align-items: center; gap: 14px; color: {TEXT_SECONDARY};
        }}
        .dg-avatar {{
            display: flex; align-items: center; gap: 10px;
        }}
        .dg-avatar-circle {{
            width: 36px; height: 36px; border-radius: 999px; background: {FOREST};
            color: #fff; display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.85rem;
        }}

        /* ---- Page header ---- */
        .dg-page-title {{ font-size: 1.7rem; font-weight: 800; color: {TEXT_PRIMARY}; margin-bottom: 2px; }}
        .dg-page-subtitle {{ color: {TEXT_SECONDARY}; font-size: 0.92rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
