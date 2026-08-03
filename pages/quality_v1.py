"""
Running Analytics - Quality Page
====================================

Single page, no tabs (per the visuals spec) - three visuals, each on its
own full-width row:
  - Monthly Quality (Line29): Average Quality and Maximum Quality, per
    month, as two lines.
  - Rolling Average Monthly Quality (Line30): 4-month moving average of
    Average Quality, per month.
  - Monthly Quality (Table31): Month / Average Quality / Maximum Quality
    - the same three columns (and same row order/formatting) as the
    Distance page's Monthly Summary table.
"""

import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_monthly_moving_average_quality,
    calculate_monthly_quality_trend,
    calculate_monthly_summary,
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
# Same three columns (Month, Average Quality, Maximum Quality), same
# most-recent-first row order, and same ProgressColumn/NumberColumn
# formatting as the Distance page's Monthly Summary table - reusing
# calculate_monthly_summary rather than recalculating, since the Notes
# column of the spec describes this as the same underlying figures.
monthly_quality_table_df = calculate_monthly_summary(runs_df)[
    ["Month", "Average Quality", "Maximum Quality"]
]

display_df = monthly_quality_table_df.copy()
display_df["Average Quality"] = display_df["Average Quality"] * 100
display_df["Maximum Quality"] = display_df["Maximum Quality"] * 100

st.subheader("Monthly Quality")
st.dataframe(
    display_df,
    column_config={
        "Average Quality": st.column_config.ProgressColumn(
            format="%.1f%%", min_value=0, max_value=110
        ),
        "Maximum Quality": st.column_config.NumberColumn(format="%.1f%%"),
    },
    hide_index=True,
    width="stretch",
    height=630,
)
