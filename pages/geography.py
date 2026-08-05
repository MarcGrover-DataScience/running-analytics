"""
Running Analytics - Geography Page
====================================

No tabs (per the visuals spec) - three visuals:
  - Row 1: Countries (Geo1) | Locations (Geo2), equal width.
  - Row 2: Ireland runs (Geo3), full width - a dual-axis clustered
    column chart (Runs on the left axis, Distance on the right), most
    recent year on the left.

No filters or interactivity on this page, per the visuals specification.
"""

import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_country_summary,
    calculate_ireland_runs_by_year,
    calculate_location_summary,
    load_runs_data,
)

# ==============================================================
# THEME COLOURS (matching the portfolio/app palette)
# ==============================================================
PRIMARY_GREEN = "#4CAF7D"
SECONDARY_BLUE = "#4C90AF"

st.title("Geography")

runs_df = load_runs_data()


def render_geography_summary_table(summary_df, height=None):
    """Shared rendering for the Countries/Locations tables: Distance and
    Average Quality get the same data-bar (ProgressColumn) treatment as
    the Distance page's summary tables, for a consistent look across the
    app - Average Quality on the fixed 0-110% scale used everywhere else
    Run Quality appears; Distance scaled to that table's own maximum.
    Runs/Average Pace/Average Distance have no data bar, so they're
    left-aligned per the project's alignment standard."""
    display_df = summary_df.copy()
    display_df["Average Quality"] = display_df["Average Quality"] * 100

    st.dataframe(
        display_df,
        column_config={
            "Runs": st.column_config.NumberColumn(format="%d", alignment="left"),
            "Distance": st.column_config.ProgressColumn(
                format="%,.2f km", min_value=0, max_value=display_df["Distance"].max()
            ),
            "Average Quality": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=110
            ),
            "Average Pace": st.column_config.TextColumn(alignment="left"),
            "Average Distance": st.column_config.NumberColumn(
                format="%.2f km", alignment="left"
            ),
        },
        hide_index=True,
        width="stretch",
        height=height if height is not None else "content",
    )


# ==============================================================
# ROW 1: COUNTRIES (Geo1) | LOCATIONS (Geo2)
# ==============================================================
country_col, location_col = st.columns(2)

with country_col:
    st.subheader("Countries")
    render_geography_summary_table(calculate_country_summary(runs_df))

with location_col:
    st.subheader("Locations")
    # Every location is included (not just the top 10) - scrollable to
    # lower-ranked rows rather than truncated, with a fixed height that
    # shows roughly the top 10 before scrolling.
    render_geography_summary_table(calculate_location_summary(runs_df), height=400)


# ==============================================================
# ROW 2: IRELAND RUNS (Geo3)
# ==============================================================
st.subheader("Ireland Runs")

ireland_df = calculate_ireland_runs_by_year(runs_df)
# Already sorted most-recent-first by calculate_ireland_runs_by_year -
# reused directly as the category order below, rather than resorting,
# so the chart's left-to-right order matches the data's own order.
year_labels = [str(year) for year in ireland_df["Year"]]

geo3_fig = go.Figure()
geo3_fig.add_trace(
    go.Bar(
        x=year_labels,
        y=ireland_df["Runs"],
        marker=dict(color=PRIMARY_GREEN),
        hovertemplate="%{x}: %{y} runs<extra></extra>",
        name="Runs",
        yaxis="y",
        offsetgroup="runs",
    )
)
geo3_fig.add_trace(
    go.Bar(
        x=year_labels,
        y=ireland_df["Distance"],
        marker=dict(color=SECONDARY_BLUE),
        hovertemplate="%{x}: %{y:,.2f} km<extra></extra>",
        name="Distance",
        yaxis="y2",
        offsetgroup="distance",
    )
)
geo3_fig.update_layout(
    title="Ireland Runs",
    barmode="group",
    bargap=0.25,
    bargroupgap=0.1,
    xaxis=dict(
        type="category",
        categoryorder="array",
        categoryarray=year_labels,
        title=None,
    ),
    yaxis=dict(title="Runs", side="left"),
    yaxis2=dict(title="Distance (km)", side="right", overlaying="y", showgrid=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(t=60, b=20, l=10, r=10),
)
st.plotly_chart(geo3_fig, width="stretch", theme="streamlit")
