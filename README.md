# Running Performance Analytics Dashboard

An interactive Streamlit dashboard analysing 17 years of personal running data (3,500+ logged runs since 2009) — built as a portfolio project demonstrating data modelling, pipeline engineering, custom metric design, and public dashboard deployment.

**Live application:** https://running-analytics.streamlit.app/
**Full write-up:** https://marcgrover-datascience.github.io/running-analytics/

## What it does

- Tracks distance, pace, and a custom-designed Run Quality metric across seven analytical pages (Overview, Best Times, Distance, Quality, Races, Geography)
- Normalises performance across runs of very different distances using a log-distance-normalised expected-pace model
- Derives medium-term Form and Consistency measures from Run Quality, to answer "how is training going this month" rather than just "how good was this run"
- Maintains a repeatable ingestion pipeline for correcting historical records and logging new runs

## Tech stack

Python, pandas, Streamlit, Plotly. Deployed on Streamlit Community Cloud.

## Project structure

| Path | Purpose |
|---|---|
| `app.py` | Streamlit entry point and page navigation |
| `pages/` | One file per analytical page |
| `transform.py` | Shared calculation logic (used by ingestion and the app) |
| `data_helpers.py` | Data loading and page-level calculation helpers |
| `ingest_transform.py` | Rebuilds the dataset from the raw source workbook |
| `reingest_edits.py` | Re-applies manual corrections from the backup Excel file |
| `data/runs.parquet` | The cleaned dataset (the app's source of truth) |
| `reference/reference_data.xlsx` | Lookup lists (locations, personal-best distances, etc.) |

## Running it locally

```bash
git clone https://github.com/MarcGrover-DataScience/running-analytics.git
cd running-analytics
pip install -r requirements.txt
streamlit run app.py
```

## Data

The underlying running data is personal but already public via Strava; this project presents it in aggregate rather than exposing exact routes or precise locations.
