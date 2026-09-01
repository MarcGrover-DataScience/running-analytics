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
import calendar
import math

import pandas as pd
import numpy as np
import streamlit as st
from scipy.stats import gaussian_kde

from transform import calculate_rolling_flags

# ==============================================================
# CONFIGURATION
# ==============================================================
RUNS_PARQUET_PATH = "data/runs.parquet"
REFERENCE_DATA_PATH = "reference/reference_data.xlsx"

# How long a cached load_runs_data() result is trusted before Streamlit
# re-reads the Parquet file and recomputes the rolling flags below. Not
# needed for the Parquet content itself (that only changes when a new
# run is logged/committed, which invalidates the cache on redeploy
# anyway) - it exists purely so the four rolling flags don't go stale if
# a single app process stays alive and idle across a day boundary
# (e.g. a browser tab left open overnight on Streamlit Cloud).
ROLLING_FLAGS_CACHE_TTL = "1h"

# The date running records are considered to begin, used for the
# "per month" KPIs (Runs per Month, Distance per Month).
RECORDS_START_DATE = datetime(2009, 9, 1)

# Average month length in days (365.25 / 12), used to convert a total
# number of days into a decimal number of months.
AVERAGE_DAYS_PER_MONTH = 365.25 / 12


# ==============================================================
# DATA LOADING (cached so the file is only read once per session)
# ==============================================================
@st.cache_data(ttl=ROLLING_FLAGS_CACHE_TTL)
def load_runs_data() -> pd.DataFrame:
    """Load the clean runs dataset from Parquet, then overwrite Current
    Year / Current Month / Last Month / In Last Year with values freshly
    computed against today's date.

    These four flags are rolling/relative properties of *today*, not
    fixed properties of a run - a run's Date never changes, but whether
    it falls in "the last month" does, every single day, regardless of
    whether that run's row has been touched since. The values stored in
    runs.parquet are only ever as fresh as the last ingest_transform.py
    or reingest_edits.py run, and the normal logging workflow (the
    Streamlit entry form, which auto-commits) never re-runs either
    pipeline script - so relying on the stored values meant every
    previously-logged run's flags silently aged out of date. Recomputing
    them here, every load, makes them self-correcting: whatever's in the
    Parquet file for these four columns is superseded before any page
    sees it, so no page file needs to know this happened.

    The other 15 fields are genuine per-run values (calculated once, at
    ingestion/logging time, from that run's own data) and are left
    exactly as stored."""
    df = pd.read_parquet(RUNS_PARQUET_PATH)

    calculation_date = datetime.today()
    rolling_flags = pd.DataFrame(
        df["Date"].apply(lambda d: calculate_rolling_flags(d, calculation_date)).tolist(),
        index=df.index,
    )
    for column in rolling_flags.columns:
        df[column] = rolling_flags[column]

    return df


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
    """Average pace (in seconds/km), excluding Family Runs. Pace is
    fundamentally a run-quality measure - Family Runs are runs where I'm
    deliberately running slower, so (per the project's metric-notes
    convention) they're excluded here, the same as Average/Maximum
    Quality. NaN if there are no non-Family-Run rows (e.g. a group made
    up entirely of Family Runs) - pandas can't take the mean of an empty
    string-typed column, so this is checked explicitly rather than
    relying on .mean() to handle it."""
    non_family = df[df["Family Run"] == "No"]
    if non_family.empty:
        return math.nan
    pace_seconds = non_family["Running Pace (min/km)"].apply(parse_mmss_to_seconds)
    return pace_seconds.mean()


def kpi_total_time_seconds(df: pd.DataFrame) -> float:
    """Total running time (in seconds) across the given rows. Returns 0.0
    for an empty DataFrame (e.g. the current calendar month before any
    run has been logged) rather than relying on Series.sum() to handle
    it - an empty 'Run Time (hh:mm:ss)' column never gets its .apply()
    call actually invoked (pandas skips it when there's nothing to
    iterate), so it stays string-typed rather than numeric, and summing
    an empty string-typed Series returns '' instead of 0."""
    if df.empty:
        return 0.0
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
# ==============================================================
# FAVOURITE RUNS TAB (Best Times page) CALCULATION HELPERS
# ==============================================================
def calculate_best_runs_past_year(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Best Runs in Past Year (Best Times page, Overall Bests tab): top n
    runs by Run Quality (highest first) among runs where In Last Year =
    1. Family Runs are excluded, consistent with the project's Run
    Quality convention (a Family Run is a deliberately slower run, so a
    quality-based ranking excludes it). Returns columns: Month,
    Location, Run Distance, Run Time, Run Pace, Run Quality."""
    working_df = df[(df["In Last Year"] == 1) & (df["Family Run"] == "No")].copy()
    working_df = working_df.sort_values("Run Quality", ascending=False).head(n).reset_index(
        drop=True
    )
    working_df["Month"] = working_df["Date"].dt.strftime("%b-%y")
    working_df = working_df.rename(
        columns={
            "Run Location": "Location",
            "Run Time (hh:mm:ss)": "Run Time",
            "Running Pace (min/km)": "Run Pace",
        }
    )
    return working_df[
        ["Month", "Location", "Run Distance", "Run Time", "Run Pace", "Run Quality"]
    ]


def kpi_average_distance(df: pd.DataFrame) -> float:
    """Average Run Distance (km) across the given rows - Sum of Run
    Distance divided by count of runs. No Family Run exclusion (Run
    Distance is not a quality metric)."""
    return df["Run Distance"].mean()


# The project's Distance Range bucket order (matches
# calculate_distance_range in transform.py) - shorter runs first, not
# alphabetical. Shared by any function that needs to present Distance
# Range categories in their natural order.
DISTANCE_RANGE_ORDER = [
    "< 4",
    "4 -> 6",
    "6 -> 8",
    "8 -> 10",
    "10 -> 12",
    "12 -> 14",
    "14 -> 16",
    "16 -> 20",
    "> 20",
]


def calculate_distance_range_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Count of runs within each Distance Range, for runs where In Last
    Year = 1 - basis for the Recent Running Profile tab's Distance
    Profile pie chart (Vis50). Distance Ranges with zero runs in the
    period are dropped (a zero-size pie slice isn't meaningful). Returns
    columns: Distance Range, Count, in DISTANCE_RANGE_ORDER (not
    alphabetical)."""
    rolling_year_df = df[df["In Last Year"] == 1]
    counts = rolling_year_df["Distance Range"].value_counts()
    result = pd.DataFrame(
        {
            "Distance Range": DISTANCE_RANGE_ORDER,
            "Count": [int(counts.get(label, 0)) for label in DISTANCE_RANGE_ORDER],
        }
    )
    return result[result["Count"] > 0].reset_index(drop=True)


def calculate_long_run_tracker(df: pd.DataFrame) -> pd.DataFrame:
    """Count of runs (In Last Year = 1) meeting each of four distance
    thresholds - basis for the Recent Running Profile tab's Long Run
    Tracker bar chart (Vis51). Thresholds are cumulative, not exclusive
    bins - e.g. a 15km run counts toward >=10km, >=12km AND >=14km (but
    not >=16km). Returns columns: Threshold, Count."""
    rolling_year_df = df[df["In Last Year"] == 1]
    THRESHOLDS_KM = [10, 12, 14, 16]
    rows = [
        {
            "Threshold": f">= {threshold}km",
            "Count": int((rolling_year_df["Run Distance"] >= threshold).sum()),
        }
        for threshold in THRESHOLDS_KM
    ]
    return pd.DataFrame(rows)


def calculate_parkrun_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Parkruns table (Recent Running Profile tab, Vis52): one row per
    parkrun Location, plus a final 'Total' row across all of them.
    Considers only Race-type runs at a Location containing 'parkrun'
    (case-insensitive - this also catches variants like 'parkrun buggy -
    ...' and '... - kids' as their own rows, since each is a distinct
    Location string), where In Last Year = 1. Best Time/Best Pace are
    read from the single fastest run in each group (ties broken by most
    recent date, via get_best_time_row); Sub-20 is a count of runs with
    a Run Time of 20 minutes or less. Returns columns: Location, Runs,
    Best Time, Best Pace, Sub-20."""
    parkrun_df = df[
        (df["Run Type"] == "Race")
        & (df["Run Location"].str.contains("parkrun", case=False))
        & (df["In Last Year"] == 1)
    ]

    def summarise_group(group_df: pd.DataFrame, location_label: str) -> dict:
        best_row = get_best_time_row(group_df)
        time_seconds = group_df["Run Time (hh:mm:ss)"].apply(parse_hhmmss_to_seconds)
        return {
            "Location": location_label,
            "Runs": len(group_df),
            "Best Time": best_row["Run Time (hh:mm:ss)"] if best_row is not None else "-",
            "Best Pace": best_row["Running Pace (min/km)"] if best_row is not None else "-",
            "Sub-20": int((time_seconds <= 20 * 60).sum()),
        }

    rows = [
        summarise_group(location_df, location)
        for location, location_df in parkrun_df.groupby("Run Location")
    ]
    rows.append(summarise_group(parkrun_df, "Total"))
    return pd.DataFrame(rows)


def calculate_races_table(df: pd.DataFrame) -> pd.DataFrame:
    """Races table (Recent Running Profile tab, Vis53): every individual
    non-parkrun race in the past year, most recent first. Considers
    Race-type runs where In Last Year = 1 and the Location does NOT
    contain 'parkrun' (case-insensitive). Returns columns: Location,
    Month, Distance, Time, Pace, Quality."""
    races_df = df[
        (df["Run Type"] == "Race")
        & (~df["Run Location"].str.contains("parkrun", case=False))
        & (df["In Last Year"] == 1)
    ].copy()
    races_df = races_df.sort_values("Date", ascending=False).reset_index(drop=True)
    races_df["Month"] = races_df["Date"].dt.strftime("%b-%y")
    races_df = races_df.rename(
        columns={
            "Run Location": "Location",
            "Run Distance": "Distance",
            "Run Time (hh:mm:ss)": "Time",
            "Running Pace (min/km)": "Pace",
            "Run Quality": "Quality",
        }
    )
    return races_df[["Location", "Month", "Distance", "Time", "Pace", "Quality"]]


def calculate_races_per_year(df: pd.DataFrame) -> pd.DataFrame:
    """Races per Year chart data (Races page, new Races tab, Row 1):
    count of non-parkrun races per calendar year, across all time. Same
    Race-type + Location-does-not-contain-'parkrun' filter as
    calculate_race_summary below. Most recent year first. Returns
    columns: Year, Races."""
    races_df = df[
        (df["Run Type"] == "Race")
        & (~df["Run Location"].str.contains("parkrun", case=False))
    ].copy()
    races_df["Year"] = races_df["Date"].dt.year

    result = (
        races_df.groupby("Year")
        .size()
        .reset_index(name="Races")
        .sort_values("Year", ascending=False)
        .reset_index(drop=True)
    )
    return result


def calculate_race_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Race Summary table (Races page, new Races tab, Row 2): every
    individual non-parkrun race across all time (unlike
    calculate_races_table, which is Rolling-Year-only), most recent
    first. Same Race-type + Location-does-not-contain-'parkrun' filter,
    with no In Last Year restriction. A plain listing of individual
    races rather than a Quality-based aggregate, so Family Runs are not
    excluded (races are never Family Runs in practice, but this keeps
    the convention explicit and consistent with calculate_races_table).
    Returns columns: Month, Location, Distance, Time, Pace, Quality."""
    races_df = df[
        (df["Run Type"] == "Race")
        & (~df["Run Location"].str.contains("parkrun", case=False))
    ].copy()
    races_df = races_df.sort_values("Date", ascending=False).reset_index(drop=True)
    races_df["Month"] = races_df["Date"].dt.strftime("%b-%y")
    races_df = races_df.rename(
        columns={
            "Run Location": "Location",
            "Run Distance": "Distance",
            "Run Time (hh:mm:ss)": "Time",
            "Running Pace (min/km)": "Pace",
            "Run Quality": "Quality",
        }
    )
    return races_df[["Month", "Location", "Distance", "Time", "Pace", "Quality"]]


def calculate_recent_runs(df: pd.DataFrame) -> pd.DataFrame:
    """Recent Runs table (Overview page, Recent Running Profile tab):
    every run where Last Month = 1, most recent first. A plain listing
    of individual runs rather than a Quality-based aggregate, so - like
    calculate_best_runs_past_year/calculate_races_table - Family Runs
    are not excluded. Returns columns: Run Distance, Run Time, Run Pace,
    Run Quality."""
    working_df = df[df["Last Month"] == 1].copy()
    working_df = working_df.sort_values("Date", ascending=False).reset_index(drop=True)
    working_df = working_df.rename(
        columns={
            "Run Time (hh:mm:ss)": "Run Time",
            "Running Pace (min/km)": "Run Pace",
        }
    )
    return working_df[["Run Distance", "Run Time", "Run Pace", "Run Quality"]]


def _summarise_parkrun_group(group_df: pd.DataFrame) -> dict:
    """Shared per-group calculation for the Races page's parkruns tab
    (Vis54/Vis55): Runs, Best Time/Best Pace/Month (all read from the
    single fastest run in the group, ties broken by most recent date,
    via get_best_time_row), Quality (the group's own Maximum Quality -
    not necessarily from the same run as Best Time), and Sub-20 (count
    of runs of 20 minutes or less)."""
    best_row = get_best_time_row(group_df)
    time_seconds = group_df["Run Time (hh:mm:ss)"].apply(parse_hhmmss_to_seconds)
    return {
        "Runs": len(group_df),
        "Best Time": best_row["Run Time (hh:mm:ss)"] if best_row is not None else "-",
        "Best Pace": best_row["Running Pace (min/km)"] if best_row is not None else "-",
        "Month": best_row["Date"].strftime("%b-%y") if best_row is not None else "-",
        "Quality": kpi_quality_maximum(group_df),
        "Sub-20": int((time_seconds <= 20 * 60).sum()),
    }


def calculate_parkrun_locations_summary(df: pd.DataFrame) -> pd.DataFrame:
    """parkrun locations table (Races page, parkruns tab, Vis54): one
    row per parkrun Location, across all time (no year restriction),
    plus a final 'Total' row across all of them. Considers only
    Race-type runs at a Location containing 'parkrun' (case-insensitive
    - this also catches variants like 'parkrun buggy - ...' and '... -
    kids' as their own rows, since each is a distinct Location string).
    Sorted by Runs descending (Total always last, regardless of its own
    Runs value). Returns columns: parkrun, Runs, Best Time, Best Pace,
    Month, Quality, Sub-20."""
    parkrun_df = df[
        (df["Run Type"] == "Race") & (df["Run Location"].str.contains("parkrun", case=False))
    ]

    rows = [
        {"parkrun": location, **_summarise_parkrun_group(location_df)}
        for location, location_df in parkrun_df.groupby("Run Location")
    ]
    result = pd.DataFrame(rows).sort_values("Runs", ascending=False).reset_index(drop=True)

    total_row = pd.DataFrame([{"parkrun": "Total", **_summarise_parkrun_group(parkrun_df)}])
    result = pd.concat([result, total_row], ignore_index=True)
    return result[["parkrun", "Runs", "Best Time", "Best Pace", "Month", "Quality", "Sub-20"]]


def calculate_parkruns_per_year_summary(df: pd.DataFrame) -> pd.DataFrame:
    """parkruns per year table (Races page, parkruns tab, Vis55): one
    row per calendar year (from Run Date), most recent year first. Same
    Race-type + 'parkrun' Location filter as
    calculate_parkrun_locations_summary, across all time. Returns
    columns: Year, Runs, Best Time, Best Pace, Month, Quality, Sub-20."""
    parkrun_df = df[
        (df["Run Type"] == "Race") & (df["Run Location"].str.contains("parkrun", case=False))
    ].copy()
    parkrun_df["Year"] = parkrun_df["Date"].dt.year

    rows = [
        {"Year": year, **_summarise_parkrun_group(year_df)}
        for year, year_df in parkrun_df.groupby("Year")
    ]
    result = pd.DataFrame(rows).sort_values("Year", ascending=False).reset_index(drop=True)
    return result[["Year", "Runs", "Best Time", "Best Pace", "Month", "Quality", "Sub-20"]]


def calculate_run_distance_histogram(
    df: pd.DataFrame, selected_years: list, bin_width: float = 2.0
):
    """Run Distance histogram + KDE curve data (Distance page, Ranges
    tab, Ran1), for the given selected year(s). Bins are bin_width km
    wide, starting at 0km, sized to the selected years' own maximum
    distance (not the full dataset's) - the bin range and x-axis resize
    to whichever year(s) are picked. The KDE curve is rescaled to the
    same count scale as the histogram bars (density * n * bin_width) -
    the standard way to overlay a KDE on a count histogram on a single
    y-axis, rather than needing its own separate density axis. Returns a
    tuple: (histogram_df, kde_x, kde_y) - histogram_df has columns Bin
    Midpoint / Bin Label / Count, for the bar chart; kde_x/kde_y (numpy
    arrays, both empty if there are fewer than 2 distinct distance
    values) are the KDE line's coordinates, on the same km x-axis."""
    year_df = df[df["Date"].dt.year.isin(selected_years)]
    distances = year_df["Run Distance"].dropna()

    if distances.empty:
        return pd.DataFrame(columns=["Bin Midpoint", "Bin Label", "Count"]), np.array([]), np.array([])

    max_distance = distances.max()
    num_bins = math.ceil(max_distance / bin_width)
    bin_edges = np.array([i * bin_width for i in range(num_bins + 1)])

    bin_counts, _ = np.histogram(distances, bins=bin_edges)
    bin_midpoints = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_labels = [
        f"{bin_edges[i]:.0f}-{bin_edges[i + 1]:.0f}km" for i in range(len(bin_edges) - 1)
    ]
    histogram_df = pd.DataFrame(
        {"Bin Midpoint": bin_midpoints, "Bin Label": bin_labels, "Count": bin_counts}
    )

    kde_x, kde_y = np.array([]), np.array([])
    if len(distances) >= 2 and distances.nunique() > 1:
        kde = gaussian_kde(distances)
        kde_x = np.linspace(0, max_distance, 200)
        kde_y = kde(kde_x) * len(distances) * bin_width

    return histogram_df, kde_x, kde_y


def calculate_distance_heat_map(df: pd.DataFrame, start_date: datetime) -> pd.DataFrame:
    """Year x Distance Range pivot (Distance page, Ranges tab, Ran2):
    count of runs per Distance Range per calendar year, for runs from
    start_date onwards. Rows (Year) are most recent first; columns
    (Distance Range) follow DISTANCE_RANGE_ORDER (shorter runs on the
    left). A Distance Range with no runs in a given year shows as 0, not
    blank, since colour-coding a heat map needs a real (low) value in
    every cell rather than a gap."""
    working_df = df[df["Date"] >= start_date].copy()
    working_df["Year"] = working_df["Date"].dt.year

    pivot = pd.crosstab(working_df["Year"], working_df["Distance Range"])
    pivot = pivot.reindex(columns=DISTANCE_RANGE_ORDER, fill_value=0)
    pivot = pivot.sort_index(ascending=False)
    pivot.index.name = "Year"
    return pivot


def calculate_annual_long_run_thresholds(df: pd.DataFrame) -> pd.DataFrame:
    """Year x Distance Threshold pivot (Distance page, Ranges tab, new
    Row 3): count of runs meeting each of four distance thresholds, per
    calendar year. Rows (Year) are most recent first. Thresholds are
    cumulative, not exclusive bins - e.g. a 15km run counts toward
    >=10km, >=12km AND >=14km (but not >=16km) - the same convention and
    thresholds as calculate_long_run_tracker (Overview page), applied
    here across all years rather than just the rolling year. Returns
    columns: >=10km, >=12km, >=14km, >=16km."""
    working_df = df.copy()
    working_df["Year"] = working_df["Date"].dt.year

    THRESHOLDS_KM = [10, 12, 14, 16]
    years = sorted(working_df["Year"].unique(), reverse=True)
    rows = []
    for year in years:
        year_df = working_df[working_df["Year"] == year]
        rows.append(
            {
                f">={threshold}km": int((year_df["Run Distance"] >= threshold).sum())
                for threshold in THRESHOLDS_KM
            }
        )
    result_df = pd.DataFrame(rows, index=years)
    result_df.index.name = "Year"
    return result_df


def calculate_country_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Countries table (Geography page, Geo1): one row per Country,
    sorted by Runs descending. Runs/Distance/Average Distance use all
    runs; Average Quality/Average Pace exclude Family Runs, consistent
    with the project's quality-metric convention (kpi_quality_average /
    kpi_average_pace_seconds). Returns columns: Country, Runs, Distance,
    Average Quality, Average Pace, Average Distance (the last formatted
    as 'mm:ss')."""
    rows = [
        {
            "Country": country,
            "Runs": len(group_df),
            "Distance": group_df["Run Distance"].sum(),
            "Average Quality": kpi_quality_average(group_df),
            "Average Pace": format_seconds_to_mmss(kpi_average_pace_seconds(group_df)),
            "Average Distance": group_df["Run Distance"].mean(),
        }
        for country, group_df in df.groupby("Country")
    ]
    return pd.DataFrame(rows).sort_values("Runs", ascending=False).reset_index(drop=True)


def calculate_location_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Locations table (Geography page, Geo2): one row per Run Location,
    sorted by Runs descending - every location is returned (not just the
    top 10), since the table is meant to scroll to lower rows rather
    than truncate the data. Same field-calculation rules as
    calculate_country_summary - see that function for details. Returns
    columns: Location, Runs, Distance, Average Quality, Average Pace,
    Average Distance (the last formatted as 'mm:ss')."""
    rows = [
        {
            "Location": location,
            "Runs": len(group_df),
            "Distance": group_df["Run Distance"].sum(),
            "Average Quality": kpi_quality_average(group_df),
            "Average Pace": format_seconds_to_mmss(kpi_average_pace_seconds(group_df)),
            "Average Distance": group_df["Run Distance"].mean(),
        }
        for location, group_df in df.groupby("Run Location")
    ]
    return pd.DataFrame(rows).sort_values("Distance", ascending=False).reset_index(drop=True)


def calculate_ireland_runs_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Ireland runs by year (Geography page, Geo3): Runs (count) and
    Distance (sum) per calendar year, for Country = 'Ireland' only, most
    recent year first - this chart is ordered with the most recent year
    on the left, unlike the rest of the app's charts (which run oldest
    to newest, left to right). Returns columns: Year, Runs, Distance."""
    ireland_df = df[df["Country"] == "Ireland"].copy()
    ireland_df["Year"] = ireland_df["Date"].dt.year
    result = ireland_df.groupby("Year", as_index=False).agg(
        Runs=("Run Distance", "count"), Distance=("Run Distance", "sum")
    )
    return result.sort_values("Year", ascending=False).reset_index(drop=True)


def get_favourite_run_reference_row(
    favourite_runs_reference: pd.DataFrame, favourite_run_name: str
) -> pd.Series:
    """Look up a single row from the Favourite Runs reference list by its
    display name (e.g. 'Hampshire 12.8km') - used to resolve the Favourite
    Runs tab's filter selection into a Distance + Location to match runs
    against."""
    matches = favourite_runs_reference[
        favourite_runs_reference["Favourite Run Name"] == favourite_run_name
    ]
    return matches.iloc[0]


def filter_runs_for_favourite_run(df: pd.DataFrame, favourite_run_row: pd.Series) -> pd.DataFrame:
    """Filter the full runs dataset down to just the runs matching a
    single Favourite Run (Distance rounded to 2dp AND Location) - the
    same matching rule used by calculate_favourite_runs."""
    target_distance = round(favourite_run_row["Distance"], 2)
    return df[
        (df["Run Distance"].round(2) == target_distance)
        & (df["Run Location"] == favourite_run_row["Location"])
    ]


def get_personal_best_reference_row(
    personal_bests_reference: pd.DataFrame, distance_name: str
) -> pd.Series:
    """Look up a single row from the Personal Bests reference list by its
    Distance Name (e.g. '5 km') - used to resolve the Personal Bests
    tab's filter selection into a target Distance to match runs
    against."""
    matches = personal_bests_reference[
        personal_bests_reference["Distance Name"] == distance_name
    ]
    return matches.iloc[0]


def filter_runs_for_personal_best(df: pd.DataFrame, personal_best_row: pd.Series) -> pd.DataFrame:
    """Filter the full runs dataset down to just the runs matching a
    single Personal Best distance (Run Distance rounded to 2dp) - the
    same matching rule used by calculate_personal_bests. Family Runs are
    excluded here (unlike filter_runs_for_favourite_run), since every
    visual on the Personal Bests tab is meant to exclude them; this
    means every downstream function that's reused from the Favourite
    Runs tab (get_best_time_row, kpi_average_time_seconds,
    kpi_average_pace_seconds, etc.) naturally excludes Family Runs too,
    without needing its own copy."""
    target_distance = round(personal_best_row["Distance"], 2)
    return df[(df["Run Distance"].round(2) == target_distance) & (df["Family Run"] == "No")]


def get_best_time_row(filtered_df: pd.DataFrame):
    """The row with the minimum Run Time - ties broken by the most
    recent Date. Returns None if filtered_df is empty. Basis for the
    Favourite Runs tab's Best Time / Best Pace / Best Time (Month) KPIs,
    which all read off this same row. Family Runs are NOT excluded here,
    consistent with how the existing Favourite Runs Overall Bests tables
    (calculate_favourite_runs) determine best times."""
    if filtered_df.empty:
        return None
    working_df = filtered_df.copy()
    working_df["_time_seconds"] = working_df["Run Time (hh:mm:ss)"].apply(
        parse_hhmmss_to_seconds
    )
    min_time_seconds = working_df["_time_seconds"].min()
    candidates = working_df[working_df["_time_seconds"] == min_time_seconds]
    return candidates.loc[candidates["Date"].idxmax()]


def kpi_average_time_seconds(df: pd.DataFrame) -> float:
    """Average Run Time (in seconds), excluding Family Runs - consistent
    with the project's Average Pace convention (kpi_average_pace_seconds),
    since Average Time and Average Pace carry the same information for a
    fixed-distance Favourite Run. NaN if there are no non-Family-Run rows
    - same empty-check kpi_average_pace_seconds already uses, since an
    empty string-typed column can't have .mean() called on it at all
    (raises TypeError) once .apply() leaves it unconverted."""
    non_family = df[df["Family Run"] == "No"]
    if non_family.empty:
        return math.nan
    time_seconds = non_family["Run Time (hh:mm:ss)"].apply(parse_hhmmss_to_seconds)
    return time_seconds.mean()


def calculate_favourite_run_top_n(
    filtered_df: pd.DataFrame, n: int, include_location: bool = False
) -> pd.DataFrame:
    """Top n fastest runs for a Favourite Run (Table40 - Top 10 Runs),
    fastest first. Returns columns: Rank, Month, [Location], Time, Pace,
    Quality. Location is omitted by default (every row shares the same
    location on the Favourite Runs tab, since a Favourite Run is a fixed
    distance+location combination) - pass include_location=True for the
    Personal Bests tab, where a distance alone doesn't fix the location
    and so it varies row to row."""
    working_df = filtered_df.copy()
    working_df["_time_seconds"] = working_df["Run Time (hh:mm:ss)"].apply(
        parse_hhmmss_to_seconds
    )
    working_df = working_df.sort_values("_time_seconds").head(n).reset_index(drop=True)
    working_df["Rank"] = working_df.index + 1
    working_df["Month"] = working_df["Date"].dt.strftime("%b-%y")
    working_df = working_df.rename(
        columns={
            "Run Time (hh:mm:ss)": "Time",
            "Running Pace (min/km)": "Pace",
            "Run Quality": "Quality",
            "Run Location": "Location",
        }
    )
    columns = ["Rank", "Month"]
    if include_location:
        columns.append("Location")
    columns += ["Time", "Pace", "Quality"]
    return working_df[columns]


def calculate_favourite_run_recent_n(
    filtered_df: pd.DataFrame, n: int, include_location: bool = False
) -> pd.DataFrame:
    """Most recent n runs for a Favourite Run (Table42 - Recent 5 Runs),
    most recent first. Returns columns: Month, [Location], Time, Pace,
    Quality. Location is omitted by default (every row shares the same
    location on the Favourite Runs tab, since a Favourite Run is a fixed
    distance+location combination) - pass include_location=True for the
    Personal Bests tab, where a distance alone doesn't fix the location
    and so it varies row to row."""
    working_df = filtered_df.sort_values("Date", ascending=False).head(n).reset_index(drop=True)
    working_df["Month"] = working_df["Date"].dt.strftime("%b-%y")
    working_df = working_df.rename(
        columns={
            "Run Time (hh:mm:ss)": "Time",
            "Running Pace (min/km)": "Pace",
            "Run Quality": "Quality",
            "Run Location": "Location",
        }
    )
    columns = ["Month"]
    if include_location:
        columns.append("Location")
    columns += ["Time", "Pace", "Quality"]
    return working_df[columns]


def calculate_favourite_run_all_time_series(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """All runs for a Favourite Run, oldest to newest - basis for the
    'All Time' line chart (Line41). Time Seconds is the plotted value;
    Time/Month are the formatted hover-text fields. Returns columns:
    Month, Time, Time Seconds."""
    working_df = filtered_df.sort_values("Date").reset_index(drop=True).copy()
    working_df["Time Seconds"] = working_df["Run Time (hh:mm:ss)"].apply(
        parse_hhmmss_to_seconds
    )
    working_df["Month"] = working_df["Date"].dt.strftime("%b-%y")
    working_df = working_df.rename(columns={"Run Time (hh:mm:ss)": "Time"})
    return working_df[["Month", "Time", "Time Seconds"]]


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


def calculate_annual_cumulative_distance(df: pd.DataFrame, start_year: int) -> pd.DataFrame:
    """Cumulative Run Distance per month, within each calendar year, for
    years >= start_year - the basis for both the Annual Cumulative tab's
    line chart (Line32) and pivot table (Table33). E.g. the value for
    June 2026 is the total distance run from January to June 2026
    inclusive. A year stops at whatever its most recent month with data
    is (no projection into months not yet reached) - a month with zero
    runs part-way through a year still gets a row, with the cumulative
    total simply carried forward flat, so the line doesn't drop to zero.
    Returns columns: Year, Month Number (1-12), Month (month name),
    Cumulative Distance."""
    working_df = df[df["Date"].dt.year >= start_year].copy()
    working_df["Year"] = working_df["Date"].dt.year
    working_df["Month Number"] = working_df["Date"].dt.month

    monthly_totals = working_df.groupby(["Year", "Month Number"], as_index=False)[
        "Run Distance"
    ].sum()

    year_frames = []
    for year, year_group in monthly_totals.groupby("Year"):
        max_month = year_group["Month Number"].max()
        full_months = pd.DataFrame({"Month Number": range(1, max_month + 1)})
        year_full = full_months.merge(
            year_group[["Month Number", "Run Distance"]], on="Month Number", how="left"
        )
        year_full["Run Distance"] = year_full["Run Distance"].fillna(0.0)
        year_full["Year"] = year
        year_full["Cumulative Distance"] = year_full["Run Distance"].cumsum()
        year_frames.append(year_full)

    result = pd.concat(year_frames, ignore_index=True)
    result["Month"] = result["Month Number"].apply(lambda m: calendar.month_name[m])
    return result[["Year", "Month Number", "Month", "Cumulative Distance"]]


def calculate_monthly_distance_distribution(
    df: pd.DataFrame, start_year: int, as_of: datetime
) -> pd.DataFrame:
    """Average total Run Distance per calendar month (Jan-Dec), across
    all years from start_year to the current year - the basis for the
    Annual Cumulative tab's Monthly Distance Distribution bar chart
    (Bar34). The current, still-in-progress calendar month (as_of.year /
    as_of.month - normally datetime.today() at the time the page is
    rendered) is excluded, so a partial month doesn't skew that month's
    average low; prior years' occurrences of the same month number are
    unaffected. Returns columns: Month Number (1-12), Month (month
    name), Average Distance."""
    working_df = df[df["Date"].dt.year >= start_year].copy()
    working_df["Year"] = working_df["Date"].dt.year
    working_df["Month Number"] = working_df["Date"].dt.month

    is_current_month = (working_df["Year"] == as_of.year) & (
        working_df["Month Number"] == as_of.month
    )
    working_df = working_df[~is_current_month]

    monthly_totals = working_df.groupby(["Year", "Month Number"], as_index=False)[
        "Run Distance"
    ].sum()
    average_by_month = (
        monthly_totals.groupby("Month Number", as_index=False)["Run Distance"]
        .mean()
        .rename(columns={"Run Distance": "Average Distance"})
    )

    # Every month 1-12 is included even if it has no complete occurrence
    # yet in the range (e.g. start_year's first partial calendar year).
    all_months = pd.DataFrame({"Month Number": range(1, 13)})
    result = all_months.merge(average_by_month, on="Month Number", how="left")
    result["Month"] = result["Month Number"].apply(lambda m: calendar.month_name[m])
    return result[["Month Number", "Month", "Average Distance"]]


def calculate_annual_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Annual Summary table (Distance page, Trends tab): one row per
    calendar year that has at least one run, most recent year first.
    Distance/Runs/Average Distance/Longest Run are calculated across all
    runs; Average Quality/Maximum Quality/Average Pace exclude Family
    Runs, per the project's metric-notes convention (Average Pace is
    fundamentally a quality measure, and Family Runs are
    deliberately-slower runs).
    Returns columns: Year, Distance, Runs, Average Distance, Longest
    Run, Average Quality, Maximum Quality, Average Pace (the last
    formatted as 'mm:ss')."""
    working_df = df.copy()
    working_df["_year"] = working_df["Date"].dt.year

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
                "Longest Run": year_df["Run Distance"].max(),
                "Average Quality": kpi_quality_average(year_df),
                "Maximum Quality": kpi_quality_maximum(year_df),
                "Average Pace": format_seconds_to_mmss(kpi_average_pace_seconds(year_df)),
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
                "Average Pace": format_seconds_to_mmss(kpi_average_pace_seconds(month_df)),
            }
        )
    return pd.DataFrame(rows)


def calculate_monthly_quality_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Average Quality and Maximum Quality per calendar month, ascending
    (oldest first, so the most recent month plots on the right of the
    line chart) - both are quality metrics, so (per the project's
    metric-notes convention) Family Runs are excluded. Returns columns:
    Month, Average Quality, Maximum Quality."""
    working_df = add_month_label(df)
    month_periods = sorted(working_df["_month_period"].unique())
    rows = []
    for period in month_periods:
        month_df = working_df[working_df["_month_period"] == period]
        rows.append(
            {
                "Month": month_df["Month"].iloc[0],
                "Average Quality": kpi_quality_average(month_df),
                "Maximum Quality": kpi_quality_maximum(month_df),
            }
        )
    return pd.DataFrame(rows)


def calculate_monthly_moving_average_quality(
    monthly_quality_df: pd.DataFrame, window: int = 4
) -> pd.DataFrame:
    """4-month moving average of Average Quality per month - e.g. the
    value shown for April 2026 is the average of the Average Quality
    values for January/February/March/April 2026. Expects
    calculate_monthly_quality_trend's output (already in ascending month
    order) as input. The first (window - 1) months have no moving-average
    value yet (not enough prior months), and are left as NaN rather than
    a partial average, so the line chart correctly shows no point for
    them."""
    result = monthly_quality_df.copy()
    result["Moving Average Quality"] = (
        result["Average Quality"].rolling(window=window, min_periods=window).mean()
    )
    return result[["Month", "Moving Average Quality"]]


def kpi_quality_coefficient_of_variation(df: pd.DataFrame) -> float:
    """Coefficient of variation (standard deviation / mean) of Run
    Quality, excluding Family Runs - the basis for the Consistency
    metric. NaN if there are fewer than 2 non-Family-Run rows (standard
    deviation is undefined for a single value)."""
    non_family_quality = df[df["Family Run"] == "No"]["Run Quality"]
    if len(non_family_quality) < 2:
        return math.nan
    return non_family_quality.std() / non_family_quality.mean()


# Consistency category thresholds, per the Consistency Definition
# (derived from analysis of 17 years of data) - checked in descending
# order, first match wins; CV <= 0.025 falls through to "Very High". A
# larger coefficient of variation means less consistent.
CONSISTENCY_THRESHOLDS = [
    (0.05, "Very Low"),
    (0.04, "Low"),
    (0.033, "Medium"),
    (0.025, "High"),
]


def calculate_consistency_category(coefficient_of_variation: float) -> str:
    """Maps a coefficient of variation (see
    kpi_quality_coefficient_of_variation) to a Consistency category:
    Very Low / Low / Medium / High / Very High. Returns None if the
    coefficient of variation is undefined (fewer than 2 non-Family-Run
    runs in the period)."""
    if pd.isna(coefficient_of_variation):
        return None
    for threshold, category in CONSISTENCY_THRESHOLDS:
        if coefficient_of_variation > threshold:
            return category
    return "Very High"


def calculate_form_score(average_quality: float) -> float:
    """Form Score, per the Form Definition: converts a mean Run Quality
    value (0-1 scale, from non-Family-Run rows) into a more spread-out
    0-10 scale, since most Average Quality values cluster tightly
    between roughly 0.87 and 0.92. Subtracts 0.82 from the mean, clips
    the result to [0, 0.1], then multiplies by 100. Always rounded to 1
    decimal place. NaN if average_quality is NaN (e.g. no non-Family-Run
    runs in the period)."""
    if pd.isna(average_quality):
        return math.nan
    shifted_value = average_quality - 0.82
    clipped_value = min(max(shifted_value, 0.0), 0.1)
    return round(clipped_value * 100, 1)


def calculate_monthly_consistency_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Coefficient of variation of Run Quality (see
    kpi_quality_coefficient_of_variation) per calendar month, ascending
    (oldest first, so the most recent month plots on the right of the
    line chart) - the continuous value the Consistency category is
    derived from; a lower value means more consistent. Returns columns:
    Month, Coefficient of Variation."""
    working_df = add_month_label(df)
    month_periods = sorted(working_df["_month_period"].unique())
    rows = []
    for period in month_periods:
        month_df = working_df[working_df["_month_period"] == period]
        rows.append(
            {
                "Month": month_df["Month"].iloc[0],
                "Coefficient of Variation": kpi_quality_coefficient_of_variation(month_df),
            }
        )
    return pd.DataFrame(rows)


def calculate_monthly_quality_table(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly Quality table (Quality page): one row per calendar month
    that has at least one run, most recent month first. Month / Average
    Quality / Maximum Quality are the same three fields (and same row
    order) as the Distance page's Monthly Summary table - see
    calculate_monthly_summary. Consistency and Form are calculated per
    the new metric definitions; Form Difference is {Form this month} -
    {Form last calendar month} (using the already-rounded Form values),
    and is NaN for a month with no immediately preceding month in the
    data."""
    working_df = add_month_label(df)
    month_periods = sorted(working_df["_month_period"].unique())  # ascending, for the diff()

    rows = []
    for period in month_periods:
        month_df = working_df[working_df["_month_period"] == period]
        average_quality = kpi_quality_average(month_df)
        coefficient_of_variation = kpi_quality_coefficient_of_variation(month_df)
        rows.append(
            {
                "_month_period": period,
                "Month": month_df["Month"].iloc[0],
                "Average Quality": average_quality,
                "Maximum Quality": kpi_quality_maximum(month_df),
                "Consistency": calculate_consistency_category(coefficient_of_variation),
                "Form": calculate_form_score(average_quality),
            }
        )
    result = pd.DataFrame(rows)
    result["Form Difference"] = result["Form"].diff()
    result = result.sort_values("_month_period", ascending=False).reset_index(drop=True)
    return result.drop(columns="_month_period")


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
