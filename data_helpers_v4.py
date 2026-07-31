"""
Running Analytics - Shared Data Helpers
=========================================

Purpose
-------
Loading, formatting, and calculation functions shared across every
analytics page in the Streamlit app. Kept separate from the ingestion
pipeline (ingest_transform.py) - this module is concerned with reading
the already-clean data and preparing it for display, not with building
the clean dataset in the first place.

A later refactor will introduce transform.py to share the *calculation*
logic (pace/quality/calories formulas) between the ingestion pipeline and
the data entry form. This module's time-parsing helpers below duplicate a
small amount of that logic for now (parsing the formatted strings back to
seconds) - deliberately left as-is until that refactor, since this
module's parsing need (string -> seconds, for aggregation) is the mirror
image of the ingestion side's need (seconds -> string, for storage), not
a straightforward shared function.
"""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# ==============================================================
# CONFIGURATION
# ==============================================================
RUNS_PARQUET_PATH = "data/runs.parquet"
REFERENCE_DATA_PATH = "reference/reference_data.xlsx"

# The date running records are considered to begin, used for the
# "per month" KPIs (Runs per Month, Distance per Month).
RECORDS_START_DATE = datetime(2009, 9, 1)

# Average month length in days (365.25 / 12), used to convert a total
# number of days into a decimal number of months.
AVERAGE_DAYS_PER_MONTH = 365.25 / 12


# ==============================================================
# DATA LOADING (cached so the file is only read once per session)
# ==============================================================
@st.cache_data
def load_runs_data() -> pd.DataFrame:
    """Load the clean runs dataset from Parquet."""
    return pd.read_parquet(RUNS_PARQUET_PATH)


@st.cache_data
def load_reference_data() -> dict:
    """Load all reference lookup tables from the reference workbook."""
    return {
        "personal_bests": pd.read_excel(REFERENCE_DATA_PATH, sheet_name="Personal Bests"),
        "favourite_runs": pd.read_excel(REFERENCE_DATA_PATH, sheet_name="Favourite Runs"),
        "run_locations": pd.read_excel(REFERENCE_DATA_PATH, sheet_name="Run Locations"),
        "countries": pd.read_excel(REFERENCE_DATA_PATH, sheet_name="Countries"),
        "run_types": pd.read_excel(REFERENCE_DATA_PATH, sheet_name="Run Types"),
    }


# ==============================================================
# TIME PARSING / FORMATTING HELPERS
# ==============================================================
def parse_hhmmss_to_seconds(value: str) -> float:
    """Convert an 'hh:mm:ss' string to total seconds."""
    if value is None or pd.isna(value):
        return float("nan")
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def parse_mmss_to_seconds(value: str) -> float:
    """Convert a 'mm:ss' string to total seconds."""
    if value is None or pd.isna(value):
        return float("nan")
    minutes, seconds = map(int, value.split(":"))
    return minutes * 60 + seconds


def format_seconds_to_hhmmss(total_seconds: float) -> str:
    """Format total seconds as H:MM:SS. Hours are NOT capped at 24, since
    this is used for durations (e.g. total time run in a year), which can
    exceed a single day."""
    if pd.isna(total_seconds):
        return "-"
    total_seconds = round(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def format_seconds_to_mmss(total_seconds: float) -> str:
    """Format total seconds as MM:SS (for pace values, always under an hour)."""
    if pd.isna(total_seconds):
        return "-"
    total_seconds = round(total_seconds)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def format_seconds_to_dhms(total_seconds: float) -> str:
    """Format total seconds as D:HH:MM:SS - used for durations large enough
    that a plain hour count loses context (e.g. total time run over a
    rolling year or all-time), so the day count is shown explicitly."""
    if pd.isna(total_seconds):
        return "-"
    total_seconds = round(total_seconds)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}:{hours:02d}:{minutes:02d}:{seconds:02d}"


# ==============================================================
# KPI CALCULATION HELPERS
# ==============================================================
def kpi_distance_sum(df: pd.DataFrame) -> float:
    """Total Run Distance across the given (already-filtered) rows."""
    return df["Run Distance"].sum()


def kpi_quality_average(df: pd.DataFrame) -> float:
    """Average Run Quality, excluding Family Runs, per the project's
    metric-notes convention."""
    non_family = df[df["Family Run"] == "No"]
    return non_family["Run Quality"].mean()


def kpi_quality_maximum(df: pd.DataFrame) -> float:
    """Maximum Run Quality, excluding Family Runs."""
    non_family = df[df["Family Run"] == "No"]
    return non_family["Run Quality"].max()


def kpi_run_count(df: pd.DataFrame) -> int:
    """Count of runs (Family Runs included - the exclusion rule applies
    only to quality metrics, not run counts)."""
    return len(df)


def kpi_average_pace_seconds(df: pd.DataFrame) -> float:
    """Average pace (in seconds/km) across the given rows."""
    pace_seconds = df["Running Pace (min/km)"].apply(parse_mmss_to_seconds)
    return pace_seconds.mean()


def kpi_total_time_seconds(df: pd.DataFrame) -> float:
    """Total running time (in seconds) across the given rows."""
    time_seconds = df["Run Time (hh:mm:ss)"].apply(parse_hhmmss_to_seconds)
    return time_seconds.sum()


def months_since_records_began(calculation_date: datetime) -> float:
    """Decimal number of months between RECORDS_START_DATE and the given
    calculation date, using an average month length (365.25 / 12 days)."""
    total_days = (calculation_date - RECORDS_START_DATE).days
    return total_days / AVERAGE_DAYS_PER_MONTH


# ==============================================================
# PERSONAL BESTS / FAVOURITE RUNS CALCULATION HELPERS
# ==============================================================
def calculate_personal_bests(
    df: pd.DataFrame, personal_bests_reference: pd.DataFrame, since_date=None
) -> pd.DataFrame:
    """For each standard distance in the Personal Bests reference list,
    find the run with the minimum time at that distance (matching on
    Run Distance rounded to 2 decimal places, to avoid floating-point
    mismatch). Optionally restricted to runs on/after `since_date`.

    Returns a DataFrame with one row per distance (in the same order as
    the reference list), sorted by distance descending, with columns:
    Distance Name, Distance, Time, Month, Running Pace, Run Quality.
    Distances with no matching runs are still included, with blank
    result columns.
    """
    working_df = df.copy()
    if since_date is not None:
        working_df = working_df[working_df["Date"] >= since_date]

    working_df["_distance_rounded"] = working_df["Run Distance"].round(2)
    working_df["_time_seconds"] = working_df["Run Time (hh:mm:ss)"].apply(
        parse_hhmmss_to_seconds
    )

    results = []
    for _, pb_row in personal_bests_reference.iterrows():
        target_distance = round(pb_row["Distance"], 2)
        matches = working_df[working_df["_distance_rounded"] == target_distance]

        if len(matches) == 0:
            results.append(
                {
                    "Distance Name": pb_row["Distance Name"],
                    "Distance": pb_row["Distance"],
                    "Time": "-",
                    "Month": "-",
                    "Running Pace": "-",
                    "Run Quality": None,
                }
            )
            continue

        best_row = matches.loc[matches["_time_seconds"].idxmin()]
        results.append(
            {
                "Distance Name": pb_row["Distance Name"],
                "Distance": pb_row["Distance"],
                "Time": best_row["Run Time (hh:mm:ss)"],
                "Month": best_row["Date"].strftime("%b-%y"),
                "Running Pace": best_row["Running Pace (min/km)"],
                "Run Quality": best_row["Run Quality"],
            }
        )

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("Distance", ascending=False).reset_index(drop=True)
    return result_df.drop(columns=["Distance"])


def calculate_favourite_runs(
    df: pd.DataFrame, favourite_runs_reference: pd.DataFrame, since_date=None
) -> pd.DataFrame:
    """Equivalent to calculate_personal_bests, but matching on both
    Run Distance AND Run Location (a Favourite Run is a specific distance
    at a specific place, not just a distance)."""
    working_df = df.copy()
    if since_date is not None:
        working_df = working_df[working_df["Date"] >= since_date]

    working_df["_distance_rounded"] = working_df["Run Distance"].round(2)
    working_df["_time_seconds"] = working_df["Run Time (hh:mm:ss)"].apply(
        parse_hhmmss_to_seconds
    )

    results = []
    for _, fav_row in favourite_runs_reference.iterrows():
        target_distance = round(fav_row["Distance"], 2)
        matches = working_df[
            (working_df["_distance_rounded"] == target_distance)
            & (working_df["Run Location"] == fav_row["Location"])
        ]

        if len(matches) == 0:
            results.append(
                {
                    "Favourite Run Name": fav_row["Favourite Run Name"],
                    "Distance": fav_row["Distance"],
                    "Time": "-",
                    "Month": "-",
                    "Running Pace": "-",
                    "Run Quality": None,
                }
            )
            continue

        best_row = matches.loc[matches["_time_seconds"].idxmin()]
        results.append(
            {
                "Favourite Run Name": fav_row["Favourite Run Name"],
                "Distance": fav_row["Distance"],
                "Time": best_row["Run Time (hh:mm:ss)"],
                "Month": best_row["Date"].strftime("%b-%y"),
                "Running Pace": best_row["Running Pace (min/km)"],
                "Run Quality": best_row["Run Quality"],
            }
        )

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("Distance", ascending=False).reset_index(drop=True)
    return result_df.drop(columns=["Distance"])


# ==============================================================
# ANNUAL PROGRESSION CALCULATION HELPERS (Best Times page)
# ==============================================================
def calculate_annual_progression_pb(df: pd.DataFrame, personal_bests_reference: pd.DataFrame):
    """Build a Year x Distance pivot of the best (minimum) time per year,
    for each Personal Best distance. Returns two same-shaped DataFrames
    (indexed by Year descending, columns = Distance Name descending by
    distance): one with formatted hh:mm:ss strings for display, one with
    raw seconds (used to identify the overall-best cell per distance for
    highlighting - string comparison of hh:mm:ss text would sort
    incorrectly, e.g. '10:00:00' vs '2:00:00')."""
    working_df = df.copy()
    working_df["_distance_rounded"] = working_df["Run Distance"].round(2)
    working_df["_time_seconds"] = working_df["Run Time (hh:mm:ss)"].apply(
        parse_hhmmss_to_seconds
    )
    working_df["_year"] = working_df["Date"].dt.year

    years = sorted(working_df["_year"].unique(), reverse=True)
    ordered_reference = personal_bests_reference.sort_values("Distance", ascending=False)
    distance_names = ordered_reference["Distance Name"].tolist()
    distance_lookup = dict(
        zip(ordered_reference["Distance Name"], ordered_reference["Distance"].round(2))
    )

    display_data = {}
    seconds_data = {}
    for distance_name in distance_names:
        target_distance = distance_lookup[distance_name]
        display_col = []
        seconds_col = []
        for year in years:
            matches = working_df[
                (working_df["_distance_rounded"] == target_distance)
                & (working_df["_year"] == year)
            ]
            if len(matches) == 0:
                display_col.append(None)
                seconds_col.append(float("nan"))
            else:
                best_seconds = matches["_time_seconds"].min()
                display_col.append(format_seconds_to_hhmmss(best_seconds))
                seconds_col.append(best_seconds)
        display_data[distance_name] = display_col
        seconds_data[distance_name] = seconds_col

    display_df = pd.DataFrame(display_data, index=pd.Index(years, name="Year"))
    seconds_df = pd.DataFrame(seconds_data, index=pd.Index(years, name="Year"))
    return display_df, seconds_df


def calculate_annual_progression_favourite_runs(
    df: pd.DataFrame, favourite_runs_reference: pd.DataFrame, earliest_year: int = 2017
):
    """Equivalent to calculate_annual_progression_pb, but matching on
    Distance + Location (a Favourite Run), and restricted to years from
    `earliest_year` onward."""
    working_df = df.copy()
    working_df["_distance_rounded"] = working_df["Run Distance"].round(2)
    working_df["_time_seconds"] = working_df["Run Time (hh:mm:ss)"].apply(
        parse_hhmmss_to_seconds
    )
    working_df["_year"] = working_df["Date"].dt.year
    working_df = working_df[working_df["_year"] >= earliest_year]

    all_years = working_df["_year"].unique().tolist()
    years = sorted(set(all_years) | {earliest_year}, reverse=True)

    ordered_reference = favourite_runs_reference.sort_values("Distance", ascending=False)

    display_data = {}
    seconds_data = {}
    for _, fav_row in ordered_reference.iterrows():
        run_name = fav_row["Favourite Run Name"]
        target_distance = round(fav_row["Distance"], 2)
        target_location = fav_row["Location"]
        display_col = []
        seconds_col = []
        for year in years:
            matches = working_df[
                (working_df["_distance_rounded"] == target_distance)
                & (working_df["Run Location"] == target_location)
                & (working_df["_year"] == year)
            ]
            if len(matches) == 0:
                display_col.append(None)
                seconds_col.append(float("nan"))
            else:
                best_seconds = matches["_time_seconds"].min()
                display_col.append(format_seconds_to_hhmmss(best_seconds))
                seconds_col.append(best_seconds)
        display_data[run_name] = display_col
        seconds_data[run_name] = seconds_col

    display_df = pd.DataFrame(display_data, index=pd.Index(years, name="Year"))
    seconds_df = pd.DataFrame(seconds_data, index=pd.Index(years, name="Year"))
    return display_df, seconds_df


# ==============================================================
# DISTANCE PAGE - TRENDS TAB CALCULATION HELPERS
# ==============================================================
def add_month_label(df: pd.DataFrame) -> pd.DataFrame:
    """Add a '_month_period' column (a sortable pandas Period, for correct
    chronological grouping/ordering) and a 'Month' display column (in
    'Mon-yy' format, e.g. 'Apr-26') derived from Date."""
    working_df = df.copy()
    working_df["_month_period"] = working_df["Date"].dt.to_period("M")
    working_df["Month"] = working_df["Date"].dt.strftime("%b-%y")
    return working_df


def calculate_monthly_distance_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Total Run Distance per calendar month, ascending (oldest first, so
    the most recent month plots on the right of the line chart) - every
    month with at least one run is included. Distance is not a quality
    metric, so Family Runs are included, per the project's metric-notes
    convention. Returns columns: Month, Run Distance."""
    working_df = add_month_label(df)
    monthly = (
        working_df.groupby(["_month_period", "Month"], as_index=False)["Run Distance"]
        .sum()
        .sort_values("_month_period")
        .reset_index(drop=True)
    )
    return monthly[["Month", "Run Distance"]]


def calculate_monthly_moving_average_distance(
    monthly_distance_df: pd.DataFrame, window: int = 4
) -> pd.DataFrame:
    """4-month moving average of monthly distance totals - e.g. the value
    shown for April 2026 is the average of January/February/March/April
    2026's monthly totals. Expects calculate_monthly_distance_trend's
    output (already in ascending month order) as input. The first
    (window - 1) months have no moving-average value yet (not enough
    prior months), and are left as NaN rather than a partial average, so
    the line chart correctly shows no point for them rather than an
    understated early value."""
    result = monthly_distance_df.copy()
    result["Moving Average Distance"] = (
        result["Run Distance"].rolling(window=window, min_periods=window).mean()
    )
    return result[["Month", "Moving Average Distance"]]


def calculate_annual_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Annual Summary table (Distance page, Trends tab): one row per
    calendar year that has at least one run, most recent year first.
    Distance/Runs/Average Distance/Average Pace are calculated across all
    runs (not quality metrics); Average Quality/Maximum Quality exclude
    Family Runs, per the project's metric-notes convention. Returns
    columns: Year, Distance, Runs, Average Distance, Average Quality,
    Maximum Quality, Average Pace (the last formatted as 'mm:ss')."""
    working_df = df.copy()
    working_df["_year"] = working_df["Date"].dt.year
    working_df["_pace_seconds"] = working_df["Running Pace (min/km)"].apply(
        parse_mmss_to_seconds
    )

    years = sorted(working_df["_year"].unique(), reverse=True)
    rows = []
    for year in years:
        year_df = working_df[working_df["_year"] == year]
        rows.append(
            {
                "Year": year,
                "Distance": year_df["Run Distance"].sum(),
                "Runs": len(year_df),
                "Average Distance": year_df["Run Distance"].mean(),
                "Average Quality": kpi_quality_average(year_df),
                "Maximum Quality": kpi_quality_maximum(year_df),
                "Average Pace": format_seconds_to_mmss(year_df["_pace_seconds"].mean()),
            }
        )
    return pd.DataFrame(rows)


def calculate_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly Summary table (Distance page, Trends tab): one row per
    calendar month that has at least one run, most recent month first,
    labelled 'Mon-yy'. Same field-calculation rules as
    calculate_annual_summary - see that function for details. Returns
    columns: Month, Distance, Runs, Average Distance, Average Quality,
    Maximum Quality, Average Pace (the last formatted as 'mm:ss')."""
    working_df = add_month_label(df)
    working_df["_pace_seconds"] = working_df["Running Pace (min/km)"].apply(
        parse_mmss_to_seconds
    )

    month_periods = sorted(working_df["_month_period"].unique(), reverse=True)
    rows = []
    for period in month_periods:
        month_df = working_df[working_df["_month_period"] == period]
        rows.append(
            {
                "Month": month_df["Month"].iloc[0],
                "Distance": month_df["Run Distance"].sum(),
                "Runs": len(month_df),
                "Average Distance": month_df["Run Distance"].mean(),
                "Average Quality": kpi_quality_average(month_df),
                "Maximum Quality": kpi_quality_maximum(month_df),
                "Average Pace": format_seconds_to_mmss(month_df["_pace_seconds"].mean()),
            }
        )
    return pd.DataFrame(rows)


def highlight_column_minimum(seconds_df: pd.DataFrame):
    """Returns a Styler-compatible function that highlights, in each
    column, the cell(s) matching that column's minimum value - used to
    flag the overall Personal Best / Favourite Run time within an annual
    progression table."""

    def style_func(_):
        styles = pd.DataFrame("", index=seconds_df.index, columns=seconds_df.columns)
        for col in seconds_df.columns:
            col_min = seconds_df[col].min()
            if pd.notna(col_min):
                mask = seconds_df[col] == col_min
                styles.loc[mask, col] = "background-color: #4CAF7D; color: #0E1117; font-weight: bold;"
        return styles

    return style_func