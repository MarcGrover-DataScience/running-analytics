"""
Running Analytics - Races Page
====================================

Built one tab at a time, per the project's visuals-spec process. Only
the parkruns tab is built so far - wrapped in st.tabs() now so further
tabs can be added later without restructuring this page.
"""

import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_parkrun_locations_summary,
    calculate_parkruns_per_year_summary,
    calculate_race_summary,
    calculate_races_per_year,
    load_runs_data,
)

# ==============================================================
# THEME COLOURS (matching the portfolio/app palette)
# ==============================================================
PRIMARY_GREEN = "#4CAF7D"

st.title("Races")

runs_df = load_runs_data()

parkruns_tab, races_tab = st.tabs(["parkruns", "Races"])


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

# ==============================================================
# RACES TAB
# ==============================================================
with races_tab:

    # --- Row 1: Races per Year ---
    # Column chart, full width. X-axis is Year as a category (not a
    # numeric axis) so it can be forced into descending order (most
    # recent year on the left) via categoryarray, the same technique
    # used for the Month axes elsewhere in the app.
    races_per_year_df = calculate_races_per_year(runs_df)

    races_per_year_fig = go.Figure()
    races_per_year_fig.add_trace(
        go.Bar(
            x=races_per_year_df["Year"].astype(str),
            y=races_per_year_df["Races"],
            marker=dict(color=PRIMARY_GREEN),
            hovertemplate="%{x}: %{y} races<extra></extra>",
            name="Races",
        )
    )
    races_per_year_fig.update_layout(
        title="Races per Year",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=races_per_year_df["Year"].astype(str).tolist(),
            title=None,
        ),
        yaxis=dict(title="Count of Races"),
        showlegend=False,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(races_per_year_fig, width="stretch", theme="streamlit")

    # --- Row 2: Race Summary ---
    # Full-width, unaggregated listing of every non-parkrun race, most
    # recent first. Quality gets the data-bar treatment; every other
    # field is explicitly left-aligned, per the project's alignment
    # standard (a data-bar column is the only exception to left-align).
    race_summary_df = calculate_race_summary(runs_df)
    race_summary_display_df = race_summary_df.copy()
    race_summary_display_df["Quality"] = race_summary_display_df["Quality"] * 100

    st.subheader("Race Summary")
    st.dataframe(
        race_summary_display_df,
        column_config={
            "Month": st.column_config.TextColumn(alignment="left"),
            "Location": st.column_config.TextColumn(alignment="left"),
            "Distance": st.column_config.NumberColumn(format="%.2f km", alignment="left"),
            "Time": st.column_config.TextColumn(alignment="left"),
            "Pace": st.column_config.TextColumn(alignment="left"),
            "Quality": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=110
            ),
        },
        hide_index=True,
        width="stretch",
    )