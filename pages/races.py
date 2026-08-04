"""
Running Analytics - Races Page
====================================

Built one tab at a time, per the project's visuals-spec process. Only
the parkruns tab is built so far - wrapped in st.tabs() now so further
tabs can be added later without restructuring this page.
"""

import streamlit as st

from data_helpers import (
    calculate_parkrun_locations_summary,
    calculate_parkruns_per_year_summary,
    load_runs_data,
)

st.title("Races")

runs_df = load_runs_data()

(parkruns_tab,) = st.tabs(["parkruns"])


# ==============================================================
# PARKRUNS TAB
# ==============================================================
with parkruns_tab:

    # --- Row 1: parkrun locations (Vis54) ---
    # Runs has a data bar, scaled to the busiest individual location
    # (not the Total row) so the individual bars stay visually
    # differentiated - Total's own bar simply shows full/maxed-out.
    # Quality has no data bar (not requested), so it's left-aligned per
    # the project's alignment standard; Best Time/Best Pace/Month are
    # already left-aligned by default as text columns.
    locations_df = calculate_parkrun_locations_summary(runs_df)
    locations_display_df = locations_df.copy()
    locations_display_df["Quality"] = locations_display_df["Quality"] * 100

    individual_locations_max_runs = int(
        locations_df.loc[locations_df["parkrun"] != "Total", "Runs"].max()
    )

    st.subheader("parkrun locations")
    st.dataframe(
        locations_display_df,
        column_config={
            "Runs": st.column_config.ProgressColumn(
                format="%d", min_value=0, max_value=individual_locations_max_runs
            ),
            "Quality": st.column_config.NumberColumn(format="%.1f%%", alignment="left"),
        },
        hide_index=True,
        width="stretch",
    )

    # --- Row 2: parkruns per year (Vis55) ---
    # Runs has a data bar (per the spec); Best Time has no data bar (per
    # your choice - shown as plain formatted text instead), so it's
    # left-aligned along with Quality and Year.
    per_year_df = calculate_parkruns_per_year_summary(runs_df)
    per_year_display_df = per_year_df.copy()
    per_year_display_df["Quality"] = per_year_display_df["Quality"] * 100

    st.subheader("parkruns per year")
    st.dataframe(
        per_year_display_df,
        column_config={
            "Year": st.column_config.NumberColumn(alignment="left"),
            "Runs": st.column_config.ProgressColumn(
                format="%d", min_value=0, max_value=int(per_year_df["Runs"].max())
            ),
            "Best Time": st.column_config.TextColumn(alignment="left"),
            "Best Pace": st.column_config.TextColumn(alignment="left"),
            "Quality": st.column_config.NumberColumn(format="%.1f%%", alignment="left"),
        },
        hide_index=True,
        width="stretch",
    )
