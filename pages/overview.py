"""
Running Analytics - Overview Page
====================================

Three rows of 6 KPIs (Current Month / Rolling Year / All Time), plus a
fourth row with two summary tables (Personal Bests / Favourite Runs).
No filters or interactivity on this page, per the visuals specification.
"""

from datetime import datetime

import streamlit as st

from data_helpers import (
    format_seconds_to_dhms,
    format_seconds_to_hhmmss,
    format_seconds_to_mmss,
    kpi_average_pace_seconds,
    kpi_distance_sum,
    kpi_quality_average,
    kpi_quality_maximum,
    kpi_run_count,
    kpi_total_time_seconds,
    load_reference_data,
    load_runs_data,
    months_since_records_began,
    calculate_personal_bests,
    calculate_favourite_runs,
)

st.title("Overview")

df = load_runs_data()
reference = load_reference_data()

# The date the page is considered "as of" - matches the ingestion
# pipeline's CALCULATION_DATE convention (today's date).
CALCULATION_DATE = datetime.today()


# ==============================================================
# ROW 1: CURRENT MONTH
# ==============================================================
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
    st.metric("Average Pace", format_seconds_to_mmss(kpi_average_pace_seconds(current_month_df)) + " /km")
with cols[5]:
    st.metric("Total Time", format_seconds_to_hhmmss(kpi_total_time_seconds(current_month_df)))


# ==============================================================
# ROW 2: ROLLING YEAR
# ==============================================================
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
    st.metric("Average Pace", format_seconds_to_mmss(kpi_average_pace_seconds(rolling_year_df)) + " /km")
with cols[5]:
    # Days:hours:minutes:seconds here, rather than plain hh:mm:ss - a
    # rolling year's total running time is large enough (100+ hours) that
    # a day count gives more useful context than hours alone.
    st.metric("Total Time", format_seconds_to_dhms(kpi_total_time_seconds(rolling_year_df)))


# ==============================================================
# ROW 3: ALL TIME
# ==============================================================
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
    # Same days:hours:minutes:seconds formatting as Rolling Year, above -
    # all-time total is large enough (thousands of hours) that a plain
    # hour count loses context entirely without the day breakdown.
    st.metric("Total Time", format_seconds_to_dhms(kpi_total_time_seconds(df)))
with cols[4]:
    st.metric("Runs per Month", f"{runs_per_month:,.1f}")
with cols[5]:
    st.metric("Distance per Month", f"{distance_per_month:,.2f} km")


# ==============================================================
# ROW 4: BEST TIMES
# ==============================================================
st.subheader("Best Times")

personal_bests_table = calculate_personal_bests(df, reference["personal_bests"])
favourite_runs_table = calculate_favourite_runs(df, reference["favourite_runs"])

# Run Quality is stored as a decimal (e.g. 0.8017); printf-style column
# formats don't auto-multiply for percentages, so scale to a percentage
# value here before applying the "%.1f%%" display format.
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
            "Run Quality": st.column_config.NumberColumn(format="%.1f%%"),
        },
        hide_index=True,
        width="stretch",
    )
with table_col2:
    st.markdown("**Favourite Runs**")
    st.dataframe(
        favourite_runs_display,
        column_config={
            "Run Quality": st.column_config.NumberColumn(format="%.1f%%"),
        },
        hide_index=True,
        width="stretch",
    )
