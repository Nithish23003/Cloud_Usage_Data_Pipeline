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


def test_database_exists():
    assert os.path.exists(DB_PATH)


def test_database_connection():
    conn = duckdb.connect(DB_PATH, read_only=True)

    result = conn.execute("SELECT 1").fetchone()[0]

    conn.close()

    assert result == 1


def test_all_views_exist():

    conn = duckdb.connect(DB_PATH, read_only=True)

    tables = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
    """).fetchall()

    conn.close()

    available = {row[0] for row in tables}

    for view in EXPECTED_VIEWS:
        assert view in available


def test_views_return_dataframe():

    conn = duckdb.connect(DB_PATH, read_only=True)

    for view in EXPECTED_VIEWS:

        df = conn.execute(
            f"SELECT * FROM {view}"
        ).df()

        assert isinstance(df, pd.DataFrame)

    conn.close()


def test_views_not_empty():

    conn = duckdb.connect(DB_PATH, read_only=True)

    for view in EXPECTED_VIEWS:

        count = conn.execute(
            f"SELECT COUNT(*) FROM {view}"
        ).fetchone()[0]

        assert count >= 0

    conn.close()


def test_exports_folder_exists():
    assert os.path.exists("exports")


def test_exported_csv_files_exist():

    for view in EXPECTED_VIEWS:

        file_path = f"exports/{view}.csv"

        assert os.path.exists(file_path)


def test_exported_csv_not_empty():

    for view in EXPECTED_VIEWS:

        file_path = f"exports/{view}.csv"

        df = pd.read_csv(file_path)

        assert isinstance(df, pd.DataFrame)


def test_monthly_trend_has_expected_columns():

    file_path = "exports/VW_MONTHLY_COST_TREND.csv"

    df = pd.read_csv(file_path)

    expected_columns = {
        "team",
        "resource_category",
        "total_cost",
    }

    assert expected_columns.issubset(df.columns)


def test_team_share_percentages_valid():

    conn = duckdb.connect(DB_PATH, read_only=True)

    df = conn.execute("""
        SELECT pct_of_quarter_spend
        FROM VW_TEAM_COST_SHARE
    """).df()

    conn.close()

    assert (df["pct_of_quarter_spend"] >= 0).all()


def test_anomaly_severity_values():

    conn = duckdb.connect(DB_PATH, read_only=True)

    df = conn.execute("""
        SELECT DISTINCT severity
        FROM VW_COST_ANOMALIES
    """).df()

    conn.close()

    allowed = {"WARNING", "CRITICAL"}

    if not df.empty:
        assert set(df["severity"]).issubset(allowed)