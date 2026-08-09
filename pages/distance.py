"""
Running Analytics - Distance Page
====================================

Built one tab at a time, per the project's visuals-spec process. Trends,
Annual Cumulative and Ranges are built.
"""

from datetime import datetime
import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_annual_cumulative_distance,
    calculate_annual_summary,
    calculate_distance_heat_map,
    calculate_monthly_distance_distribution,
    calculate_monthly_distance_trend,
    calculate_monthly_moving_average_distance,
    calculate_monthly_summary,
    calculate_run_distance_histogram,
    load_runs_data,
)

# ==============================================================
# THEME COLOURS (matching the portfolio/app palette)
# ==============================================================
PRIMARY_GREEN = "#4CAF7D"
SECONDARY_BLUE = "#4C90AF"

st.title("Distance")

runs_df = load_runs_data()

trends_tab, annual_cumulative_tab, ranges_tab = st.tabs(
    ["Trends", "Annual Cumulative", "Ranges"]
)


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
        pixel integer instead for a fixed, scrollable height. Longest
        Run (Annual Summary only - Monthly Summary has no such column)
        also gets a data-bar, scaled to its own column maximum like
        Distance. Year (Annual Summary only) is explicitly left-aligned,
        since Streamlit right-aligns numeric columns by default and
        Year isn't given its own ProgressColumn/NumberColumn treatment
        otherwise."""
        display_df = prepare_summary_display(summary_df)
        column_config = {
            "Distance": st.column_config.ProgressColumn(
                format="%,.2f km",
                min_value=0,
                max_value=display_df["Distance"].max(),
            ),
            "Average Quality": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=110
            ),
            "Average Distance": st.column_config.NumberColumn(
                format="%.2f km", alignment="left"
            ),
            "Maximum Quality": st.column_config.NumberColumn(
                format="%.1f%%", alignment="left"
            ),
            "Runs": st.column_config.NumberColumn(format="%d", alignment="left"),
        }
        if "Longest Run" in display_df.columns:
            column_config["Longest Run"] = st.column_config.ProgressColumn(
                format="%,.2f km",
                min_value=0,
                max_value=display_df["Longest Run"].max(),
            )
        if "Year" in display_df.columns:
            column_config["Year"] = st.column_config.NumberColumn(
                format="%d", alignment="left"
            )
        st.dataframe(
            display_df,
            column_config=column_config,
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


# ==============================================================
# ANNUAL CUMULATIVE TAB
# ==============================================================
with annual_cumulative_tab:

    # The one parameter for this tab - all three visuals below are based
    # from January of this year onwards. Change this single value to
    # move the start point in future (e.g. to 2022) without touching any
    # of the calculation or chart code below.
    ANNUAL_CUMULATIVE_START_YEAR = 2021

    # Used only by the Monthly Distance Distribution bar chart (Bar34),
    # to identify and exclude the current, still-in-progress calendar
    # month - taken live at render time, not from the dataset's most
    # recent date, so the app self-corrects at the start of every new
    # month even if the underlying data hasn't been refreshed yet.
    CALCULATION_DATE = datetime.today()

    cumulative_distance_df = calculate_annual_cumulative_distance(
        runs_df, ANNUAL_CUMULATIVE_START_YEAR
    )

    # --- Row 1: Annual Distance Progression (Line32) ---
    # One line per year, x-axis is month-of-year (Jan-Dec) rather than
    # 'Mon-yy' - the point of this chart is comparing years against each
    # other on the same month positions, which only works if the year
    # isn't baked into the x-axis label. The most recent year is drawn
    # in the primary green and slightly thicker, to draw the eye to
    # current-year progress against the greyed-back prior years.
    years = sorted(cumulative_distance_df["Year"].unique())
    month_order = cumulative_distance_df.sort_values("Month Number")["Month"].unique().tolist()
    # A muted grey-blue for earlier years, stepping up to the primary
    # green for the most recent year.
    EARLIER_YEAR_COLORS = ["#8FA6B3", "#7A98A8", "#6B8C9C", "#5C8091", "#4C90AF"]

    line32_fig = go.Figure()
    for i, year in enumerate(years):
        is_latest_year = year == years[-1]
        year_df = cumulative_distance_df[cumulative_distance_df["Year"] == year]
        line32_fig.add_trace(
            go.Scatter(
                x=year_df["Month"],
                y=year_df["Cumulative Distance"],
                mode="lines+markers",
                line=dict(
                    color=PRIMARY_GREEN if is_latest_year else EARLIER_YEAR_COLORS[i % len(EARLIER_YEAR_COLORS)],
                    width=3 if is_latest_year else 1.5,
                ),
                marker=dict(size=5),
                hovertemplate="%{x} " + str(year) + ": %{y:,.2f} km<extra></extra>",
                name=str(year),
            )
        )
    line32_fig.update_layout(
        title=f"Annual Distance Progression ({ANNUAL_CUMULATIVE_START_YEAR} onwards)",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=month_order,
            title=None,
        ),
        yaxis=dict(title="Cumulative Run Distance (km)"),
        legend=dict(title="Year"),
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(line32_fig, width="stretch", theme="streamlit")

    # --- Row 2: Annual Distance Comparison (Table33) ---
    # Pivot: Month on rows, Year on columns - blank cells are months the
    # current year hasn't reached yet.
    comparison_pivot_df = cumulative_distance_df.pivot(
        index="Month Number", columns="Year", values="Cumulative Distance"
    )
    comparison_pivot_df.index = [
        calendar.month_name[m] for m in comparison_pivot_df.index
    ]
    comparison_pivot_df.index.name = "Month"
    comparison_pivot_df.columns = [str(year) for year in comparison_pivot_df.columns]

    st.subheader("Annual Distance Comparison")
    st.dataframe(
        comparison_pivot_df,
        column_config={
            str(year): st.column_config.NumberColumn(format="%,.2f km", alignment="left")
            for year in years
        },
        width="stretch",
    )

    # --- Row 3: Monthly Distance Distribution (Bar34) ---
    monthly_distribution_df = calculate_monthly_distance_distribution(
        runs_df, ANNUAL_CUMULATIVE_START_YEAR, CALCULATION_DATE
    )

    bar34_fig = go.Figure()
    bar34_fig.add_trace(
        go.Bar(
            x=monthly_distribution_df["Month"],
            y=monthly_distribution_df["Average Distance"],
            marker=dict(color=PRIMARY_GREEN),
            hovertemplate="%{x}: %{y:,.2f} km<extra></extra>",
            name="Average Distance",
        )
    )
    bar34_fig.update_layout(
        title=(
            f"Monthly Distance Distribution "
            f"({ANNUAL_CUMULATIVE_START_YEAR} onwards, complete months only)"
        ),
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=monthly_distribution_df["Month"].tolist(),
            title=None,
        ),
        yaxis=dict(title="Average Run Distance (km)"),
        showlegend=False,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(bar34_fig, width="stretch", theme="streamlit")


# ==============================================================
# RANGES TAB
# ==============================================================
with ranges_tab:

    # --- Row 1: Run Distribution (Ran1) ---
    # Year filter scoped to this one chart only (a plain local variable,
    # not shared session_state) - multi-select, defaulting to 2026.
    HISTOGRAM_BIN_WIDTH_KM = 2.0

    years_available = sorted(runs_df["Date"].dt.year.unique().tolist(), reverse=True)
    selected_years = st.multiselect(
        "Year",
        options=years_available,
        default=[2026] if 2026 in years_available else years_available[:1],
    )

    if selected_years:
        histogram_df, kde_x, kde_y = calculate_run_distance_histogram(
            runs_df, selected_years, bin_width=HISTOGRAM_BIN_WIDTH_KM
        )

        ran1_fig = go.Figure()
        ran1_fig.add_trace(
            go.Bar(
                x=histogram_df["Bin Midpoint"],
                y=histogram_df["Count"],
                width=HISTOGRAM_BIN_WIDTH_KM * 0.9,
                marker=dict(color=PRIMARY_GREEN),
                customdata=histogram_df["Bin Label"],
                hovertemplate="%{customdata}: %{y} runs<extra></extra>",
                name="Runs",
            )
        )
        if len(kde_x):
            # Rescaled to the same count scale as the bars above
            # (density * n * bin width), rather than a separate density
            # axis, so both traces read naturally off one y-axis.
            ran1_fig.add_trace(
                go.Scatter(
                    x=kde_x,
                    y=kde_y,
                    mode="lines",
                    line=dict(color=SECONDARY_BLUE, width=2),
                    hoverinfo="skip",
                    name="KDE",
                )
            )
        ran1_fig.update_layout(
            title="Run Distribution",
            xaxis=dict(
                title="Run Distance (km)",
                tickmode="array",
                tickvals=histogram_df["Bin Midpoint"].tolist(),
                ticktext=histogram_df["Bin Label"].tolist(),
            ),
            yaxis=dict(title="Count of Runs"),
            bargap=0.1,
            margin=dict(t=40, b=20, l=10, r=10),
        )
        st.plotly_chart(ran1_fig, width="stretch", theme="streamlit")
    else:
        st.info("Select at least one year to show the Run Distribution chart.")

    # --- Row 2: Distance Heat Map (Ran2) ---
    # Count per cell, colour-coded with a green gradient (lighter =
    # fewer runs, darker = more) via a pandas Styler - the same solid
    # per-cell background-color mechanism used for Form Difference on
    # the Quality page, just driven by a colour map (background_gradient)
    # instead of a manual sign check. This isn't given the alignment
    # standard's usual left-align treatment, since - like a data bar -
    # the colour itself is already the primary visual encoding here.
    heat_map_df = calculate_distance_heat_map(runs_df, datetime(2012, 1, 1))
    styled_heat_map = heat_map_df.style.background_gradient(cmap="Greens", axis=None)

    st.subheader("Distance Heat Map")
    st.dataframe(styled_heat_map, width="stretch")