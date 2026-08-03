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

pages = [
    st.Page("pages/overview.py", title="Overview"),
    # st.Page("pages/best_times.py", title="Best Times"),
]

# Local-only pages will be appended here once built, e.g.:
# if st.secrets.get("local_mode", False):
#     pages += [st.Page("pages/log_new_run.py", title="Log New Run")]

nav = st.navigation(pages)
nav.run()
