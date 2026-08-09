"""
Running Analytics - Overview Page
====================================

Two tabs:
  - Summary: three rows of 6 KPIs (Current Month / Rolling Year / All
    Time), plus a row with two summary tables (Personal Bests /
    Favourite Runs). This tab is unchanged from the page's original,
    single-tab layout.
  - Recent Running Profile: a 'Past Month' row of 6 KPIs, then two
    'Past Year' rows - one of two charts, one of two tables.

No filters or interactivity on this page, per the visuals specification.
"""

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from data_helpers import (
    calculate_distance_range_distribution,
    calculate_favourite_runs,
    calculate_form_score,
    calculate_long_run_tracker,
    calculate_parkrun_summary,
    calculate_personal_bests,
    calculate_races_table,
    calculate_recent_runs,
    calculate_consistency_category,
    format_seconds_to_dhms,
    format_seconds_to_hhmmss,
    format_seconds_to_mmss,
    kpi_average_distance,
    kpi_average_pace_seconds,
    kpi_distance_sum,
    kpi_quality_average,
    kpi_quality_coefficient_of_variation,
    kpi_quality_maximum,
    kpi_run_count,
    kpi_total_time_seconds,
    load_reference_data,
    load_runs_data,
    months_since_records_began,
)

# ==============================================================
# THEME COLOURS (matching the portfolio/app palette)
# ==============================================================
PRIMARY_GREEN = "#4CAF7D"
CHART_PALETTE = ["#4CAF7D", "#4C90AF", "#8FA6B3", "#6B8C9C", "#2E7D5B", "#7A98A8", "#5C8091", "#A8C3B5", "#3C6E5E"]

st.title("Overview")

df = load_runs_data()
reference = load_reference_data()

# The date the page is considered "as of" - matches the ingestion
# pipeline's CALCULATION_DATE convention (today's date).
CALCULATION_DATE = datetime.today()

tab_summary, tab_recent_profile = st.tabs(["Summary", "Recent Running Profile"])


# ==============================================================
# TAB 1: SUMMARY
# ==============================================================
with tab_summary:

    # --- Row 1: Current Month ---
    st.subheader("Current Month")
    current_month_df = df[df["Current Month"] == 1]

    cols = st.columns(6)
    with cols[0]:
        st.metric("Distance", f"{kpi_distance_sum(current_month_df):,.2f} km")
    with cols[1]:
        quality_avg = kpi_quality_average(current_month_df)
        st.metric("Average Quality", f"{quality_avg:.1%}" if quality_avg == quality_avg else "-")
    with cols[2]:
        quality_max = kpi_quality_maximum(current_month_df)
        st.metric("Maximum Quality", f"{quality_max:.1%}" if quality_max == quality_max else "-")
    with cols[3]:
        st.metric("Runs", f"{kpi_run_count(current_month_df):,}")
    with cols[4]:
        st.metric(
            "Average Pace",
            format_seconds_to_mmss(kpi_average_pace_seconds(current_month_df)) + " /km",
        )
    with cols[5]:
        st.metric("Total Time", format_seconds_to_hhmmss(kpi_total_time_seconds(current_month_df)))

    # --- Row 2: Rolling Year ---
    st.subheader("Rolling Year")
    rolling_year_df = df[df["In Last Year"] == 1]

    cols = st.columns(6)
    with cols[0]:
        st.metric("Distance", f"{kpi_distance_sum(rolling_year_df):,.2f} km")
    with cols[1]:
        quality_avg = kpi_quality_average(rolling_year_df)
        st.metric("Average Quality", f"{quality_avg:.1%}" if quality_avg == quality_avg else "-")
    with cols[2]:
        quality_max = kpi_quality_maximum(rolling_year_df)
        st.metric("Maximum Quality", f"{quality_max:.1%}" if quality_max == quality_max else "-")
    with cols[3]:
        st.metric("Runs", f"{kpi_run_count(rolling_year_df):,}")
    with cols[4]:
        st.metric(
            "Average Pace",
            format_seconds_to_mmss(kpi_average_pace_seconds(rolling_year_df)) + " /km",
        )
    with cols[5]:
        # Days:hours:minutes:seconds here, rather than plain hh:mm:ss - a
        # rolling year's total running time is large enough (100+ hours)
        # that a day count gives more useful context than hours alone.
        st.metric("Total Time (day:hr:min:sec)", format_seconds_to_dhms(kpi_total_time_seconds(rolling_year_df)))

    # --- Row 3: All Time ---
    st.subheader("All Time")

    months_elapsed = months_since_records_began(CALCULATION_DATE)
    runs_per_month = kpi_run_count(df) / months_elapsed
    distance_per_month = kpi_distance_sum(df) / months_elapsed

    cols = st.columns(6)
    with cols[0]:
        st.metric("Distance", f"{kpi_distance_sum(df):,.0f} km")
    with cols[1]:
        quality_avg = kpi_quality_average(df)
        st.metric("Average Quality", f"{quality_avg:.1%}" if quality_avg == quality_avg else "-")
    with cols[2]:
        st.metric("Runs", f"{kpi_run_count(df):,}")
    with cols[3]:
        # Same days:hours:minutes:seconds formatting as Rolling Year,
        # above - all-time total is large enough (thousands of hours)
        # that a plain hour count loses context entirely without the day
        # breakdown.
        st.metric("Total Time (day:hr:min:sec)", format_seconds_to_dhms(kpi_total_time_seconds(df)))
    with cols[4]:
        st.metric("Runs per Month", f"{runs_per_month:,.1f}")
    with cols[5]:
        st.metric("Distance per Month", f"{distance_per_month:,.2f} km")

    # --- Row 4: Best Times ---
    st.subheader("Best Times")

    personal_bests_table = calculate_personal_bests(df, reference["personal_bests"])
    favourite_runs_table = calculate_favourite_runs(df, reference["favourite_runs"])

    # Run Quality is stored as a decimal (e.g. 0.8017); printf-style
    # column formats don't auto-multiply for percentages, so scale to a
    # percentage value here before applying the "%.1f%%" display format.
    personal_bests_display = personal_bests_table.copy()
    personal_bests_display["Run Quality"] = personal_bests_display["Run Quality"] * 100

    favourite_runs_display = favourite_runs_table.copy()
    favourite_runs_display["Run Quality"] = favourite_runs_display["Run Quality"] * 100

    table_col1, table_col2 = st.columns(2)
    with table_col1:
        st.markdown("**Personal Bests**")
        st.dataframe(
            personal_bests_display,
            column_config={
                "Run Quality": st.column_config.NumberColumn(format="%.1f%%", alignment="left"),
            },
            hide_index=True,
            width="stretch",
        )
    with table_col2:
        st.markdown("**Favourite Runs**")
        st.dataframe(
            favourite_runs_display,
            column_config={
                "Run Quality": st.column_config.NumberColumn(format="%.1f%%", alignment="left"),
            },
            hide_index=True,
            width="stretch",
        )


# ==============================================================
# TAB 2: RECENT RUNNING PROFILE
# ==============================================================
with tab_recent_profile:

    # --- Row 1: Past Month (Vis44-49) ---
    st.subheader("Past Month")
    last_month_df = df[df["Last Month"] == 1]

    cols = st.columns(6)
    with cols[0]:
        st.metric("Runs", f"{kpi_run_count(last_month_df):,}")
    with cols[1]:
        st.metric("Distance", f"{kpi_distance_sum(last_month_df):,.2f} km")
    with cols[2]:
        form_score = calculate_form_score(kpi_quality_average(last_month_df))
        st.metric("Form", f"{form_score:.1f}" if form_score == form_score else "-")
    with cols[3]:
        quality_max = kpi_quality_maximum(last_month_df)
        st.metric("Maximum Quality", f"{quality_max:.1%}" if quality_max == quality_max else "-")
    with cols[4]:
        average_distance = kpi_average_distance(last_month_df)
        st.metric(
            "Average Distance", f"{average_distance:,.2f} km" if average_distance == average_distance else "-"
        )
    with cols[5]:
        consistency = calculate_consistency_category(
            kpi_quality_coefficient_of_variation(last_month_df)
        )
        st.metric("Consistency", consistency if consistency else "-")

    # --- Row 2 & 3: Past Year (Vis50-53) ---
    st.subheader("Past Year")

    # Row 2: Distance Profile (Vis50) | Long Run Tracker (Vis51)
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        distance_profile_df = calculate_distance_range_distribution(df)
        pie_fig = go.Figure()
        pie_fig.add_trace(
            go.Pie(
                labels=distance_profile_df["Distance Range"],
                values=distance_profile_df["Count"],
                marker=dict(colors=CHART_PALETTE),
                hovertemplate="%{label}: %{value} runs<extra></extra>",
            )
        )
        pie_fig.update_layout(
            title="Distance Profile",
            margin=dict(t=40, b=20, l=10, r=10),
        )
        st.plotly_chart(pie_fig, width="stretch", theme="streamlit")

    with chart_col2:
        long_run_df = calculate_long_run_tracker(df)
        bar_fig = go.Figure()
        bar_fig.add_trace(
            go.Bar(
                x=long_run_df["Threshold"],
                y=long_run_df["Count"],
                marker=dict(color=PRIMARY_GREEN),
                hovertemplate="%{x}: %{y} runs<extra></extra>",
                name="Runs",
            )
        )
        bar_fig.update_layout(
            title="Long Run Tracker",
            xaxis=dict(type="category", title=None),
            yaxis=dict(title="Count of Runs"),
            showlegend=False,
            margin=dict(t=40, b=20, l=10, r=10),
        )
        st.plotly_chart(bar_fig, width="stretch", theme="streamlit")

    # Row 3: Parkruns (Vis52) | Races (Vis53)
    table_col1, table_col2 = st.columns(2)

    with table_col1:
        st.markdown("**Parkruns**")
        st.dataframe(
            calculate_parkrun_summary(df),
            column_config={
                "Runs": st.column_config.NumberColumn(alignment="left"),
                "Best Time": st.column_config.TextColumn(alignment="left"),
                "Best Pace": st.column_config.TextColumn(alignment="left"),
                "Sub-20": st.column_config.NumberColumn(alignment="left"),
            },
            hide_index=True,
            width="stretch",
        )

    with table_col2:
        st.markdown("**Races**")
        races_display_df = calculate_races_table(df)
        races_display_df["Quality"] = races_display_df["Quality"] * 100
        st.dataframe(
            races_display_df,
            column_config={
                "Distance": st.column_config.NumberColumn(format="%.2f km", alignment="left"),
                "Quality": st.column_config.ProgressColumn(
                    format="%.1f%%", min_value=0, max_value=110
                ),
            },
            hide_index=True,
            width="stretch",
        )

    # Row 4: Recent Runs (new) - every run from the past calendar month,
    # most recent first. Half-width, via the same two-column pattern as
    # the rows above, with the second column left empty.
    st.subheader("Recent Runs (Last Month)")
    recent_runs_col, _ = st.columns(2)

    with recent_runs_col:
        recent_runs_display_df = calculate_recent_runs(df)
        recent_runs_display_df["Run Quality"] = recent_runs_display_df["Run Quality"] * 100
        st.dataframe(
            recent_runs_display_df,
            column_config={
                "Run Distance": st.column_config.NumberColumn(format="%.2f km", alignment="left"),
                "Run Time": st.column_config.TextColumn(alignment="left"),
                "Run Pace": st.column_config.TextColumn(alignment="left"),
                "Run Quality": st.column_config.ProgressColumn(
                    format="%.1f%%", min_value=0, max_value=110
                ),
            },
            hide_index=True,
            width="stretch",
        )
