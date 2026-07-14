import os
import duckdb
import pandas as pd

DB_PATH = "database/db/finops_export.duckdb"

EXPECTED_VIEWS = [
    "VW_DAILY_COST_SUMMARY",
    "VW_MONTHLY_COST_TREND",
    "VW_TEAM_COST_SHARE",
    "VW_COST_ANOMALIES",
    "VW_UTILIZATION_EFFICIENCY",
    "VW_WEEKEND_VS_WEEKDAY",
    "VW_TOP_EXPENSIVE_DAYS",
]


def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


# --------------------------------------------------
# Database Tests
# --------------------------------------------------

def test_database_exists():
    assert os.path.exists(DB_PATH)


def test_raw_table_exists():

    conn = get_connection()

    tables = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
    """).fetchall()

    conn.close()

    table_names = [t[0] for t in tables]

    assert "AZURE_COST_DATA" in table_names


def test_raw_data_loaded():

    conn = get_connection()

    count = conn.execute("""
        SELECT COUNT(*)
        FROM AZURE_COST_DATA
    """).fetchone()[0]

    conn.close()

    assert count > 0


# --------------------------------------------------
# View Creation Tests
# --------------------------------------------------

def test_all_views_exist():

    conn = get_connection()

    objects = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
    """).fetchall()

    conn.close()

    names = {row[0] for row in objects}

    for view in EXPECTED_VIEWS:
        assert view in names


def test_views_return_data():

    conn = get_connection()

    for view in EXPECTED_VIEWS:

        count = conn.execute(
            f"SELECT COUNT(*) FROM {view}"
        ).fetchone()[0]

        assert count >= 0

    conn.close()


# --------------------------------------------------
# Daily Cost Summary
# --------------------------------------------------

def test_daily_summary_columns():

    conn = get_connection()

    df = conn.execute("""
        SELECT *
        FROM VW_DAILY_COST_SUMMARY
        LIMIT 1
    """).df()

    conn.close()

    expected = {
        "date",
        "team",
        "resource_category",
        "quarter",
        "total_cost",
        "avg_utilization",
        "running_total_cost",
    }

    assert expected.issubset(df.columns)


# --------------------------------------------------
# Monthly Trend
# --------------------------------------------------

def test_monthly_trend_contains_mom():

    conn = get_connection()

    df = conn.execute("""
        SELECT *
        FROM VW_MONTHLY_COST_TREND
        LIMIT 5
    """).df()

    conn.close()

    assert "mom_pct_change" in df.columns


# --------------------------------------------------
# Team Cost Share
# --------------------------------------------------

def test_team_cost_share_percentage_valid():

    conn = get_connection()

    df = conn.execute("""
        SELECT pct_of_quarter_spend
        FROM VW_TEAM_COST_SHARE
    """).df()

    conn.close()

    assert (df["pct_of_quarter_spend"] >= 0).all()
    assert (df["pct_of_quarter_spend"] <= 100).all()


# --------------------------------------------------
# Anomaly Detection
# --------------------------------------------------

def test_anomaly_view_exists():

    conn = get_connection()

    count = conn.execute("""
        SELECT COUNT(*)
        FROM VW_COST_ANOMALIES
    """).fetchone()[0]

    conn.close()

    assert count >= 0


def test_anomaly_severity_values():

    conn = get_connection()

    df = conn.execute("""
        SELECT DISTINCT severity
        FROM VW_COST_ANOMALIES
    """).df()

    conn.close()

    allowed = {"WARNING", "CRITICAL"}

    if not df.empty:
        assert set(df["severity"]).issubset(allowed)


# --------------------------------------------------
# Utilization Efficiency
# --------------------------------------------------

def test_efficiency_labels_valid():

    conn = get_connection()

    df = conn.execute("""
        SELECT DISTINCT efficiency_label
        FROM VW_UTILIZATION_EFFICIENCY
    """).df()

    conn.close()

    allowed = {
        "Overprovisioned",
        "Optimized-HighLoad",
        "Efficient",
        "Normal"
    }

    assert set(df["efficiency_label"]).issubset(allowed)


# --------------------------------------------------
# Weekend Analysis
# --------------------------------------------------

def test_weekend_flag_values():

    conn = get_connection()

    df = conn.execute("""
        SELECT DISTINCT is_weekend
        FROM VW_WEEKEND_VS_WEEKDAY
    """).df()

    conn.close()

    values = set(df["is_weekend"])

    assert values.issubset({True, False})


# --------------------------------------------------
# Top Expensive Days
# --------------------------------------------------

def test_top_expensive_days_limit():

    conn = get_connection()

    count = conn.execute("""
        SELECT COUNT(*)
        FROM VW_TOP_EXPENSIVE_DAYS
    """).fetchone()[0]

    conn.close()

    assert count <= 10


def test_top_expensive_days_sorted():

    conn = get_connection()

    df = conn.execute("""
        SELECT total_daily_spend
        FROM VW_TOP_EXPENSIVE_DAYS
    """).df()

    conn.close()

    values = df["total_daily_spend"].tolist()

    assert values == sorted(values, reverse=True)


# --------------------------------------------------
# Export Database
# --------------------------------------------------

def test_export_database_created():

    assert os.path.exists(
        "database/db/finops_export.duckdb"
    )