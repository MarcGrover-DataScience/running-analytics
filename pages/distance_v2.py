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

    # --- Row 3: Annual Summary (Table27) | Monthly Summary (Table28) ---
    # Year/Month is set as the index (rather than left as a column) so it
    # displays as the table's row label without a redundant numeric index
    # alongside it.
    annual_summary_df = calculate_annual_summary(runs_df).set_index("Year")
    monthly_summary_df = calculate_monthly_summary(runs_df).set_index("Month")

    NUMBER_FORMATS = {
        "Distance": "{:,.2f}",
        "Runs": "{:,.0f}",
        "Average Distance": "{:,.2f}",
        "Average Quality": "{:.1%}",
        "Maximum Quality": "{:.1%}",
    }

    def style_summary_table(summary_df: pd.DataFrame):
        """Shared styling for the Annual/Monthly Summary tables: number
        formatting, plus data bars on Distance and Average Quality, per
        the spec. Rendered with st.table (not st.dataframe) below -
        Streamlit's interactive st.dataframe grid does not render pandas
        Styler .bar() gradients, only st.table's static HTML output
        does."""
        return (
            summary_df.style.format(NUMBER_FORMATS)
            .bar(subset=["Distance"], color=PRIMARY_GREEN)
            .bar(subset=["Average Quality"], color=PRIMARY_GREEN, vmin=0, vmax=1)
        )

    annual_col, monthly_col = st.columns(2)

    with annual_col:
        st.subheader("Annual Summary")
        st.table(style_summary_table(annual_summary_df))

    with monthly_col:
        st.subheader("Monthly Summary")
        st.table(style_summary_table(monthly_summary_df))
