"""
Running Analytics - Distance Page
====================================

Built one tab at a time, per the project's visuals-spec process. Only
the Trends tab is built so far (Ranges and Annual Cumulative to follow) -
wrapped in st.tabs() now so those can be added as further tab entries
without restructuring this page later.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_annual_summary,
    calculate_monthly_distance_trend,
    calculate_monthly_moving_average_distance,
    calculate_monthly_summary,
    load_runs_data,
)

# ==============================================================
# THEME COLOURS (matching the portfolio/app palette)
# ==============================================================
PRIMARY_GREEN = "#4CAF7D"
SECONDARY_BLUE = "#4C90AF"

st.title("Distance")

runs_df = load_runs_data()

(trends_tab,) = st.tabs(["Trends"])


# ==============================================================
# TRENDS TAB
# ==============================================================
with trends_tab:

    # --- Row 1: Distance per month (Line1) ---
    monthly_distance_df = calculate_monthly_distance_trend(runs_df)

    line1_fig = go.Figure()
    line1_fig.add_trace(
        go.Scatter(
            x=monthly_distance_df["Month"],
            y=monthly_distance_df["Run Distance"],
            mode="lines+markers",
            line=dict(color=PRIMARY_GREEN, width=2),
            marker=dict(size=5),
            hovertemplate="%{x}: %{y:,.2f} km<extra></extra>",
            name="Distance",
        )
    )
    line1_fig.update_layout(
        title="Distance (per month)",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=monthly_distance_df["Month"].tolist(),
            title=None,
        ),
        yaxis=dict(title="Run Distance (km)"),
        showlegend=False,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(line1_fig, width="stretch", theme="streamlit")

    # --- Row 2: Moving Average Distance per month (Line2) ---
    moving_average_df = calculate_monthly_moving_average_distance(monthly_distance_df)

    line2_fig = go.Figure()
    line2_fig.add_trace(
        go.Scatter(
            x=moving_average_df["Month"],
            y=moving_average_df["Moving Average Distance"],
            mode="lines+markers",
            line=dict(color=SECONDARY_BLUE, width=2),
            marker=dict(size=5),
            hovertemplate="%{x}: %{y:,.2f} km<extra></extra>",
            name="4-Month Moving Average",
        )
    )
    line2_fig.update_layout(
        title="Moving Average Distance (per month, 4-month average)",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=moving_average_df["Month"].tolist(),
            title=None,
        ),
        yaxis=dict(title="Run Distance (km)"),
        showlegend=False,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(line2_fig, width="stretch", theme="streamlit")

    # --- Row 3: Annual Summary (Table27) ---
    # --- Row 4: Monthly Summary (Table28) ---
    # Each table gets its own full-width row (more column width than the
    # earlier side-by-side layout), and both use the same
    # column_config.ProgressColumn approach as the Best Times page's
    # Overall Bests tables, for a consistent look across the app.
    annual_summary_df = calculate_annual_summary(runs_df)
    monthly_summary_df = calculate_monthly_summary(runs_df)

    def prepare_summary_display(summary_df: pd.DataFrame) -> pd.DataFrame:
        """Scale Average Quality / Maximum Quality to percentage values
        for display/data-bar use, matching prepare_quality_display on the
        Best Times page - progress/number column formats don't
        auto-multiply by 100."""
        display_df = summary_df.copy()
        display_df["Average Quality"] = display_df["Average Quality"] * 100
        display_df["Maximum Quality"] = display_df["Maximum Quality"] * 100
        return display_df

    def render_summary_table(summary_df: pd.DataFrame, height: int | str = "content"):
        """Shared rendering for the Annual/Monthly Summary tables:
        Distance and Average Quality get data-bar (ProgressColumn)
        treatment, per the spec - Average Quality uses the same fixed
        0-110% scale as the Best Times page's quality bars, for
        consistency; Distance is scaled to that table's own maximum,
        since (unlike quality) it has no natural fixed ceiling. height
        defaults to 'content' (fits all rows, no scrolling) - pass a
        pixel integer instead for a fixed, scrollable height."""
        display_df = prepare_summary_display(summary_df)
        st.dataframe(
            display_df,
            column_config={
                "Distance": st.column_config.ProgressColumn(
                    format="%,.2f km",
                    min_value=0,
                    max_value=display_df["Distance"].max(),
                ),
                "Average Quality": st.column_config.ProgressColumn(
                    format="%.1f%%", min_value=0, max_value=110
                ),
                "Average Distance": st.column_config.NumberColumn(format="%.2f km"),
                "Maximum Quality": st.column_config.NumberColumn(format="%.1f%%"),
                "Runs": st.column_config.NumberColumn(format="%d"),
            },
            hide_index=True,
            width="stretch",
            height=height,
        )

    st.subheader("Annual Summary")
    render_summary_table(annual_summary_df)

    # Monthly Summary is scrollable, showing roughly the top 15-20 rows
    # (most recent months first) rather than every month at once.
    st.subheader("Monthly Summary")
    render_summary_table(monthly_summary_df, height=630)