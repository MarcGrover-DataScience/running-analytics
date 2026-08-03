"""
Running Analytics - Quality Page
====================================

Single page, no tabs (per the visuals spec) - four visuals, each on its
own full-width row:
  - Monthly Quality (Line29): Average Quality and Maximum Quality, per
    month, as two lines.
  - Rolling Average Monthly Quality (Line30): 4-month moving average of
    Average Quality, per month.
  - Monthly Quality (Table31): Month / Average Quality / Maximum Quality
    (same three fields/row order as the Distance page's Monthly Summary
    table), plus Consistency, Form and Form Difference.
  - Consistency by Month: the Coefficient of Variation the Consistency
    category is derived from, plotted directly (a category doesn't plot
    naturally as a line) - lower is more consistent.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_monthly_consistency_trend,
    calculate_monthly_moving_average_quality,
    calculate_monthly_quality_table,
    calculate_monthly_quality_trend,
    load_runs_data,
)

# ==============================================================
# THEME COLOURS (matching the portfolio/app palette)
# ==============================================================
PRIMARY_GREEN = "#4CAF7D"
SECONDARY_BLUE = "#4C90AF"

st.title("Quality")

runs_df = load_runs_data()


# ==============================================================
# ROW 1: MONTHLY QUALITY (Line29) - Average and Maximum Quality lines
# ==============================================================
monthly_quality_df = calculate_monthly_quality_trend(runs_df)

line29_fig = go.Figure()
line29_fig.add_trace(
    go.Scatter(
        x=monthly_quality_df["Month"],
        y=monthly_quality_df["Average Quality"] * 100,
        mode="lines+markers",
        line=dict(color=PRIMARY_GREEN, width=2),
        marker=dict(size=5),
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        name="Average Quality",
    )
)
line29_fig.add_trace(
    go.Scatter(
        x=monthly_quality_df["Month"],
        y=monthly_quality_df["Maximum Quality"] * 100,
        mode="lines+markers",
        line=dict(color=SECONDARY_BLUE, width=2),
        marker=dict(size=5),
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        name="Maximum Quality",
    )
)
line29_fig.update_layout(
    title="Monthly Quality",
    xaxis=dict(
        type="category",
        categoryorder="array",
        categoryarray=monthly_quality_df["Month"].tolist(),
        title=None,
    ),
    yaxis=dict(title="Run Quality (%)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(t=60, b=20, l=10, r=10),
)
st.plotly_chart(line29_fig, width="stretch", theme="streamlit")


# ==============================================================
# ROW 2: ROLLING AVERAGE MONTHLY QUALITY (Line30)
# ==============================================================
moving_average_quality_df = calculate_monthly_moving_average_quality(monthly_quality_df)

line30_fig = go.Figure()
line30_fig.add_trace(
    go.Scatter(
        x=moving_average_quality_df["Month"],
        y=moving_average_quality_df["Moving Average Quality"] * 100,
        mode="lines+markers",
        line=dict(color=PRIMARY_GREEN, width=2),
        marker=dict(size=5),
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        name="4-Month Moving Average",
    )
)
line30_fig.update_layout(
    title="Rolling Average Monthly Quality (4-month average)",
    xaxis=dict(
        type="category",
        categoryorder="array",
        categoryarray=moving_average_quality_df["Month"].tolist(),
        title=None,
    ),
    yaxis=dict(title="Run Quality (%)"),
    showlegend=False,
    margin=dict(t=60, b=20, l=10, r=10),
)
st.plotly_chart(line30_fig, width="stretch", theme="streamlit")


# ==============================================================
# ROW 3: MONTHLY QUALITY TABLE (Table31)
# ==============================================================
# Month / Average Quality / Maximum Quality are the same three fields
# (and same row order) as the Distance page's Monthly Summary table.
# Consistency and Form are per the new metric definitions; Form
# Difference is {Form this month} - {Form last month}, shown with a
# green up arrow / red down arrow (Streamlit's st.dataframe supports
# solid background-color from a pandas Styler, just not the
# linear-gradient .bar() used elsewhere - see render_summary_table on
# the Distance page for that distinction).
monthly_quality_table_df = calculate_monthly_quality_table(runs_df)

display_df = monthly_quality_table_df.copy()
display_df["Average Quality"] = display_df["Average Quality"] * 100
display_df["Maximum Quality"] = display_df["Maximum Quality"] * 100


def format_form_difference(value: float) -> str:
    """Formats a Form Difference value with a directional arrow - blank
    for the first month in the data (no prior month to compare to)."""
    if pd.isna(value):
        return ""
    if value > 0:
        return f"▲ +{value:.1f}"
    if value < 0:
        return f"▼ {value:.1f}"
    return f"→ {value:.1f}"


def color_form_difference(value: str) -> str:
    """Green background for an improving month, red for a declining
    month - identified from the arrow added by format_form_difference,
    so a 0.0/blank cell is left uncoloured."""
    if value.startswith("▲"):
        return "background-color: #4CAF7D; color: #0E1117; font-weight: bold;"
    if value.startswith("▼"):
        return "background-color: #D9534F; color: #FFFFFF; font-weight: bold;"
    return ""


display_df["Form Difference"] = display_df["Form Difference"].apply(format_form_difference)
styled_table = display_df.style.map(color_form_difference, subset=["Form Difference"])

st.subheader("Monthly Quality")
st.dataframe(
    styled_table,
    column_config={
        "Average Quality": st.column_config.ProgressColumn(
            format="%.1f%%", min_value=0, max_value=110
        ),
        "Maximum Quality": st.column_config.NumberColumn(format="%.1f%%", alignment="left"),
        "Form": st.column_config.NumberColumn(format="%.1f", alignment="left"),
    },
    hide_index=True,
    width="stretch",
    height=630,
)


# ==============================================================
# ROW 4: CONSISTENCY BY MONTH
# ==============================================================
# Plots the Coefficient of Variation directly, rather than the
# Consistency category it's mapped to - a category (Very Low...Very
# High) doesn't plot naturally as a line. Lower CV means more
# consistent.
monthly_consistency_df = calculate_monthly_consistency_trend(runs_df)

# Chart only shows January 2012 onwards - the CV calculation itself is
# unaffected (still based on each month's own runs), this just trims
# which months are plotted.
monthly_consistency_df = monthly_consistency_df[
    pd.to_datetime(monthly_consistency_df["Month"], format="%b-%y")
    >= pd.Timestamp("2012-01-01")
].reset_index(drop=True)

consistency_fig = go.Figure()
consistency_fig.add_trace(
    go.Scatter(
        x=monthly_consistency_df["Month"],
        y=monthly_consistency_df["Coefficient of Variation"],
        mode="lines+markers",
        line=dict(color=PRIMARY_GREEN, width=2),
        marker=dict(size=5),
        hovertemplate="%{x}: %{y:.3f}<extra></extra>",
        name="Coefficient of Variation",
    )
)
consistency_fig.update_layout(
    title="Consistency by Month (Coefficient of Variation - lower is more consistent)",
    xaxis=dict(
        type="category",
        categoryorder="array",
        categoryarray=monthly_consistency_df["Month"].tolist(),
        title=None,
    ),
    yaxis=dict(title="Coefficient of Variation (CV)"),
    showlegend=False,
    margin=dict(t=60, b=20, l=10, r=10),
)
st.plotly_chart(consistency_fig, width="stretch", theme="streamlit")