"""
Running Analytics - Best Times Page
======================================

Three tabs:
  - Overall Bests: 4 tables (PB all-time / since 2020, Favourite Runs
    all-time / since 2020), each with a Run Quality data-bar column.
  - Annual Progression: 2 pivot tables (Year x Distance / Year x
    Favourite Run) showing the best time per year, with the overall
    best time per distance highlighted.
  - Favourite Runs: KPIs, tables and a chart for a single Favourite Run
    at a time, selected via this tab's own filter (the first filter in
    the dashboard - scoped to this tab only, no other tab/page is
    affected).
"""

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_annual_progression_favourite_runs,
    calculate_annual_progression_pb,
    calculate_favourite_run_all_time_series,
    calculate_favourite_run_recent_n,
    calculate_favourite_run_top_n,
    calculate_favourite_runs,
    calculate_personal_bests,
    filter_runs_for_favourite_run,
    format_seconds_to_hhmmss,
    format_seconds_to_mmss,
    get_best_time_row,
    get_favourite_run_reference_row,
    highlight_column_minimum,
    kpi_average_pace_seconds,
    kpi_average_time_seconds,
    load_reference_data,
    load_runs_data,
)

PRIMARY_GREEN = "#4CAF7D"

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


tab_overall, tab_annual, tab_favourite_runs = st.tabs(
    ["Overall Bests", "Annual Progression", "Favourite Runs"]
)


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


# ==============================================================
# TAB 3: FAVOURITE RUNS
# ==============================================================
with tab_favourite_runs:

    # The tab's own filter - a single Favourite Run at a time, defaulting
    # to Hampshire 12.8km. Every visual below is filtered by this
    # selection; it's a plain local variable (not shared session_state),
    # so it has no effect outside this tab.
    favourite_run_names = reference["favourite_runs"]["Favourite Run Name"].tolist()
    DEFAULT_FAVOURITE_RUN = "Hampshire 12.8km"
    selected_favourite_run = st.selectbox(
        "Favourite Run",
        options=favourite_run_names,
        index=favourite_run_names.index(DEFAULT_FAVOURITE_RUN),
    )

    favourite_run_row = get_favourite_run_reference_row(
        reference["favourite_runs"], selected_favourite_run
    )
    filtered_df = filter_runs_for_favourite_run(df, favourite_run_row)

    # --- Row 1 & 2: KPIs (KPI32-39) ---
    # Best Time/Best Pace/Best Time (Month) all come from the same
    # fastest row (ties broken by most recent date); Runs/Last Run/Runs
    # (Rolling Year) don't exclude Family Runs, consistent with how the
    # existing Favourite Runs Overall Bests tables treat this data.
    # Average Time/Average Pace DO exclude Family Runs, consistent with
    # the project's Average Pace convention (kpi_average_pace_seconds).
    best_row = get_best_time_row(filtered_df)

    row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
    row1_col1.metric("Runs", f"{len(filtered_df):,}")
    row1_col2.metric("Best Time", best_row["Run Time (hh:mm:ss)"] if best_row is not None else "-")
    row1_col3.metric("Best Pace", best_row["Running Pace (min/km)"] if best_row is not None else "-")
    row1_col4.metric(
        "Best Time (Month)", best_row["Date"].strftime("%b-%y") if best_row is not None else "-"
    )

    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
    row2_col1.metric("Average Time", format_seconds_to_hhmmss(kpi_average_time_seconds(filtered_df)))
    row2_col2.metric("Average Pace", format_seconds_to_mmss(kpi_average_pace_seconds(filtered_df)))
    row2_col3.metric(
        "Last Run",
        filtered_df["Date"].max().strftime("%b-%y") if not filtered_df.empty else "-",
    )
    row2_col4.metric("Runs (Rolling Year)", f"{(filtered_df['In Last Year'] == 1).sum():,}")

    # --- Row 3: Top 10 Runs (Table40) ---
    st.subheader("Top 10 Runs")
    top_10_df = calculate_favourite_run_top_n(filtered_df, 10)
    display_top_10_df = top_10_df.copy()
    display_top_10_df["Quality"] = display_top_10_df["Quality"] * 100
    st.dataframe(
        display_top_10_df,
        column_config={
            "Rank": st.column_config.NumberColumn(alignment="left"),
            "Quality": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=110
            ),
        },
        hide_index=True,
        width="stretch",
    )

    # --- Row 4: All Time (Line41) ---
    # X-axis is run sequence (oldest to newest, equally spaced) with no
    # date/month labels shown - the point is the shape of the trend, not
    # reading off a specific date. Month and Time appear on hover instead.
    all_time_df = calculate_favourite_run_all_time_series(filtered_df)

    line41_fig = go.Figure()
    line41_fig.add_trace(
        go.Scatter(
            x=list(range(1, len(all_time_df) + 1)),
            y=all_time_df["Time Seconds"] / 60,
            mode="lines+markers",
            line=dict(color=PRIMARY_GREEN, width=2),
            marker=dict(size=5),
            customdata=all_time_df[["Time", "Month"]].values,
            hovertemplate="%{customdata[1]}: %{customdata[0]}<extra></extra>",
            name="Run Time",
        )
    )
    line41_fig.update_layout(
        title="All Time",
        xaxis=dict(showticklabels=False, title=None),
        yaxis=dict(title="Run Time (minutes)"),
        showlegend=False,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(line41_fig, width="stretch", theme="streamlit")

    # --- Row 5: Recent 5 Runs (Table42) ---
    st.subheader("Recent 5 Runs")
    recent_5_df = calculate_favourite_run_recent_n(filtered_df, 5)
    display_recent_5_df = recent_5_df.copy()
    display_recent_5_df["Quality"] = display_recent_5_df["Quality"] * 100
    st.dataframe(
        display_recent_5_df,
        column_config={
            "Quality": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=110
            ),
        },
        hide_index=True,
        width="stretch",
    )