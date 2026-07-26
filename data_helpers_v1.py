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
