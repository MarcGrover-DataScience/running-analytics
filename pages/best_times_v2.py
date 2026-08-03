"""
Running Analytics - Best Times Page
======================================

Two tabs:
  - Overall Bests: 4 tables (PB all-time / since 2020, Favourite Runs
    all-time / since 2020), each with a Run Quality data-bar column.
  - Annual Progression: 2 pivot tables (Year x Distance / Year x
    Favourite Run) showing the best time per year, with the overall
    best time per distance highlighted.

No filters or interactivity on this page, per the visuals specification.
"""

from datetime import datetime

import streamlit as st

from data_helpers import (
    calculate_annual_progression_favourite_runs,
    calculate_annual_progression_pb,
    calculate_favourite_runs,
    calculate_personal_bests,
    highlight_column_minimum,
    load_reference_data,
    load_runs_data,
)

st.title("Best Times")

df = load_runs_data()
reference = load_reference_data()

SINCE_2020 = datetime(2020, 1, 1)


def prepare_quality_display(table):
    """Scale Run Quality to a percentage value for display/data-bar use -
    printf/progress column formats don't auto-multiply by 100."""
    display_table = table.copy()
    display_table["Run Quality"] = display_table["Run Quality"] * 100
    return display_table


def render_best_times_table(table):
    st.dataframe(
        prepare_quality_display(table),
        column_config={
            "Run Quality": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=110
            ),
        },
        hide_index=True,
        width="stretch",
    )


tab_overall, tab_annual = st.tabs(["Overall Bests", "Annual Progression"])


# ==============================================================
# TAB 1: OVERALL BESTS
# ==============================================================
with tab_overall:
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.markdown("**Personal Bests (All Time)**")
        render_best_times_table(calculate_personal_bests(df, reference["personal_bests"]))
    with row1_col2:
        st.markdown("**Personal Bests (Since 2020)**")
        render_best_times_table(
            calculate_personal_bests(df, reference["personal_bests"], since_date=SINCE_2020)
        )

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.markdown("**Favourite Runs (All Time)**")
        render_best_times_table(calculate_favourite_runs(df, reference["favourite_runs"]))
    with row2_col2:
        st.markdown("**Favourite Runs (Since 2020)**")
        render_best_times_table(
            calculate_favourite_runs(df, reference["favourite_runs"], since_date=SINCE_2020)
        )


# ==============================================================
# TAB 2: ANNUAL PROGRESSION
# ==============================================================
with tab_annual:
    st.markdown("**Annual Best (Personal Bests)**")
    pb_display, pb_seconds = calculate_annual_progression_pb(df, reference["personal_bests"])
    st.dataframe(
        pb_display.style.apply(highlight_column_minimum(pb_seconds), axis=None),
        width="stretch",
    )

    st.markdown("**Annual Best (Favourite Runs)**")
    fav_display, fav_seconds = calculate_annual_progression_favourite_runs(
        df, reference["favourite_runs"], earliest_year=2017
    )
    st.dataframe(
        fav_display.style.apply(highlight_column_minimum(fav_seconds), axis=None),
        width="stretch",
    )
