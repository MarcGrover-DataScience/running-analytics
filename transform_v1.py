"""
Running Analytics - Shared Transformation Logic
==================================================

Every calculation formula used to build the clean data model, in one
place, so it's defined exactly once regardless of which script needs it:

    - ingest_transform.py   (raw Excel Master sheet -> clean model)
    - reingest_edits.py     (edited backup Excel -> refreshed clean model)
    - the future Streamlit data entry form (one new run -> clean model)

None of these functions perform any file I/O - purely calculation, so
they're easy to test in isolation and safe to import anywhere.
"""

import math
from datetime import datetime, time, timedelta

import pandas as pd

# ==============================================================
# TIME CONVERSION
# ==============================================================
def excel_time_to_seconds(value) -> float:
    """Convert a datetime.time, timedelta, or Excel day-fraction float
    (or None) to total seconds as a float. Handles every form a 'time of
    day' or duration value can take once round-tripped through Excel via
    openpyxl - covers both the original raw Master sheet's Run Time
    column, and a re-ingested backup file's Run Time column (which
    round-trips as datetime.time after being written as a duration with
    a custom number_format)."""
    if value is None:
        return math.nan
    if isinstance(value, time):
        return (
            value.hour * 3600
            + value.minute * 60
            + value.second
            + value.microsecond / 1_000_000
        )
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, (int, float)):
        return value * 86400
    raise TypeError(f"Unexpected time value type: {type(value)}")


def seconds_to_mmss(total_seconds: float) -> str:
    """Format a pace duration (in seconds) as mm:ss."""
    if pd.isna(total_seconds):
        return None
    total_seconds = round(total_seconds)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def seconds_to_hhmmss(total_seconds: float) -> str:
    """Format a run duration (in seconds) as hh:mm:ss."""
    if pd.isna(total_seconds):
        return None
    total_seconds = round(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# ==============================================================
# CORE PER-RUN CALCULATIONS
# ==============================================================
def calculate_pace_seconds(distance_km: float, time_seconds: float) -> float:
    """Pace in seconds per kilometre."""
    return time_seconds / distance_km


def calculate_speed_kmh(distance_km: float, time_seconds: float) -> float:
    """Speed in kilometres per hour."""
    return distance_km / (time_seconds / 3600)


def calculate_quality(distance_km: float, speed_kmh: float) -> float:
    """Run Quality: speed expressed as a proportion of the 'expected'
    speed for that distance, per the log-distance-normalised model:
        Quality = Speed / (-1.407 x LN(Distance) + 17.771)
    """
    return speed_kmh / (-1.407 * math.log(distance_km) + 17.771)


def calculate_calories(distance_km: float) -> float:
    """Run Calories: a flat 76 calories per kilometre."""
    return round(76 * distance_km, 2)


def calculate_5k_sub20(distance_km: float, time_seconds: float) -> int:
    """1 if this is a 5.00km run completed in 20 minutes or less, else 0."""
    return int(distance_km == 5.0 and time_seconds <= 20 * 60)


def calculate_distance_range(distance_km: float) -> str:
    """Bucket a distance into the standard Distance Range categories.
    Boundaries belong to the *next* range up (e.g. exactly 6.00km falls
    into '6 -> 8', not '4 -> 6')."""
    boundaries = [4, 6, 8, 10, 12, 14, 16, 20]
    labels = [
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
    for boundary, label in zip(boundaries, labels):
        if distance_km < boundary:
            return label
    return labels[-1]  # "> 20"


# ==============================================================
# DATE-DERIVED FIELDS
# ==============================================================
def calculate_weekday(run_date) -> str:
    """Day-of-week name for a run date."""
    return pd.to_datetime(run_date).day_name()


def calculate_rolling_flags(run_date, calculation_date: datetime) -> dict:
    """Current Year / Current Month / Last Month / In Last Year flags,
    all relative to `calculation_date` (the date the pipeline or entry
    form is being run/submitted on). Current Year/Current Month are
    calendar-based; Last Month/In Last Year are rolling windows ending on
    the calculation date (not fixed calendar periods)."""
    run_date = pd.to_datetime(run_date)

    current_year = int(run_date.year == calculation_date.year)
    current_month = int(
        run_date.year == calculation_date.year
        and run_date.month == calculation_date.month
    )

    one_month_ago = calculation_date - pd.DateOffset(months=1)
    last_month = int(one_month_ago < run_date <= calculation_date)

    one_year_ago = calculation_date - pd.DateOffset(years=1)
    in_last_year = int(one_year_ago < run_date <= calculation_date)

    return {
        "Current Year": current_year,
        "Current Month": current_month,
        "Last Month": last_month,
        "In Last Year": in_last_year,
    }


# ==============================================================
# FULL PER-RUN CALCULATION (convenience wrapper)
# ==============================================================
def calculate_all_derived_fields(
    distance_km: float, time_seconds: float, run_date, calculation_date: datetime
) -> dict:
    """Given the raw inputs for a single run, return every calculated
    field this project derives. Used by any script/form that needs the
    complete set for one run, rather than calling each function
    individually."""
    pace_seconds = calculate_pace_seconds(distance_km, time_seconds)
    speed_kmh = calculate_speed_kmh(distance_km, time_seconds)
    quality = calculate_quality(distance_km, speed_kmh)
    calories = calculate_calories(distance_km)

    fields = {
        "Run Time (hh:mm:ss)": seconds_to_hhmmss(time_seconds),
        "Running Pace (min/km)": seconds_to_mmss(pace_seconds),
        "Running Speed (km/hr)": speed_kmh,
        "Run Quality": quality,
        "Run Calories": calories,
        "Weekday": calculate_weekday(run_date),
        "5k_Sub20": calculate_5k_sub20(distance_km, time_seconds),
        "Distance Range": calculate_distance_range(distance_km),
    }
    fields.update(calculate_rolling_flags(run_date, calculation_date))
    return fields
