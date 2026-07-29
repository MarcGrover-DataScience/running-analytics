"""
Running Analytics - App Entry Point
======================================

Defines the multipage navigation. Pages are added here as they're built;
the local_mode flag (set in .streamlit/secrets.toml, never committed)
will later control which additional local-only pages appear (Data Entry,
Detailed Data) once those are built.
"""

import streamlit as st

st.set_page_config(page_title="Running Analytics", layout="wide")

# Style every st.metric as a bordered, tinted "card" using the theme
# palette - Streamlit doesn't have a built-in option for this, but
# data-testid="stMetric" is the selector Streamlit itself documents for
# targeted metric styling (more stable across versions than internal
# class names).
st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: rgba(76, 175, 125, 0.08);
        border: 1px solid rgba(76, 175, 125, 0.35);
        border-left: 4px solid #4CAF7D;
        border-radius: 8px;
        padding: 12px 16px 8px 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

pages = [
    st.Page("pages/overview.py", title="Overview"),
    st.Page("pages/best_times.py", title="Best Times"),
]

# Local-only pages will be appended here once built, e.g.:
# if st.secrets.get("local_mode", False):
#     pages += [st.Page("pages/log_new_run.py", title="Log New Run")]

nav = st.navigation(pages)
nav.run()
