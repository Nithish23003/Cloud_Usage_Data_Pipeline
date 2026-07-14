import pandas as pd

from data.synthetic_cost_generator import (
    generate_cost_data,
    get_spike_multiplier
)


def test_generate_cost_data_returns_dataframe():
    df = generate_cost_data(days=10)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_expected_columns_exist():
    df = generate_cost_data(days=1)

    expected_columns = {
        "date",
        "team",
        "resource_category",
        "resource_name",
        "cost",
        "utilization",
        "is_weekend",
        "month",
        "quarter",
    }

    assert expected_columns.issubset(set(df.columns))


def test_record_count_for_one_day():
    df = generate_cost_data(days=1)

    # 8 teams × 3 categories
    expected_rows = 8 * 3

    assert len(df) == expected_rows


def test_record_count_for_ten_days():
    df = generate_cost_data(days=10)

    expected_rows = 10 * 8 * 3

    assert len(df) == expected_rows


def test_cost_never_negative():
    df = generate_cost_data(days=30)

    assert (df["cost"] > 0).all()


def test_utilization_within_range():
    df = generate_cost_data(days=30)

    assert (df["utilization"] >= 0).all()
    assert (df["utilization"] <= 100).all()


def test_month_values_valid():
    df = generate_cost_data(days=365)

    assert df["month"].between(1, 12).all()


def test_quarter_values_valid():
    df = generate_cost_data(days=365)

    valid_quarters = {"Q1", "Q2", "Q3", "Q4"}

    assert set(df["quarter"].unique()).issubset(valid_quarters)


def test_spike_multiplier_normal_day():
    from datetime import date

    multiplier = get_spike_multiplier(
        date(2024, 1, 15),
        "Finance",
        "Database"
    )

    assert multiplier == 1.0


def test_finance_quarter_end_spike():
    from datetime import date

    multiplier = get_spike_multiplier(
        date(2024, 3, 29),
        "Finance",
        "Database"
    )

    assert multiplier == 3.5


def test_mac2_incident_spike():
    from datetime import date

    multiplier = get_spike_multiplier(
        date(2024, 7, 22),
        "MAC2",
        "Compute"
    )

    assert multiplier == 8.0


def test_weekend_flag_exists():
    df = generate_cost_data(days=30)

    assert df["is_weekend"].dtype == bool


def test_no_null_values_in_key_columns():
    df = generate_cost_data(days=30)

    critical_columns = [
        "date",
        "team",
        "resource_category",
        "resource_name",
        "cost",
    ]

    assert not df[critical_columns].isnull().any().any()