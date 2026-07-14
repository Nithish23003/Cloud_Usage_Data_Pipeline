import os
import pandas as pd
from unittest.mock import Mock, patch

from ai_engine.spend_narrative import (
    get_cost_metrics,
    build_prompt,
    generate_narrative,
    save_report
)


# --------------------------------------------------
# DuckDB Metrics Extraction
# --------------------------------------------------

def test_get_cost_metrics_returns_dataframes():

    mom_df, anomalies_df, team_df, waste_df = get_cost_metrics(
        "database/db/finops_export.duckdb"
    )

    assert isinstance(mom_df, pd.DataFrame)
    assert isinstance(anomalies_df, pd.DataFrame)
    assert isinstance(team_df, pd.DataFrame)
    assert isinstance(waste_df, pd.DataFrame)


def test_team_dataframe_not_empty():

    _, _, team_df, _ = get_cost_metrics(
        "database/db/finops_export.duckdb"
    )

    assert len(team_df) > 0


# --------------------------------------------------
# Prompt Building
# --------------------------------------------------

def test_build_prompt_returns_string():

    mom_df, anomalies_df, team_df, waste_df = get_cost_metrics(
        "database/db/finops_export.duckdb"
    )

    prompt = build_prompt(
        mom_df,
        anomalies_df,
        team_df,
        waste_df
    )

    assert isinstance(prompt, str)


def test_prompt_contains_required_sections():

    mom_df, anomalies_df, team_df, waste_df = get_cost_metrics(
        "database/db/finops_export.duckdb"
    )

    prompt = build_prompt(
        mom_df,
        anomalies_df,
        team_df,
        waste_df
    )

    assert "Overall Spend Summary" in prompt
    assert "Key Cost Drivers" in prompt
    assert "Anomalies & Alerts" in prompt
    assert "Executive One-liner" in prompt


def test_prompt_contains_team_data():

    mom_df, anomalies_df, team_df, waste_df = get_cost_metrics(
        "database/db/finops_export.duckdb"
    )

    prompt = build_prompt(
        mom_df,
        anomalies_df,
        team_df,
        waste_df
    )

    first_team = team_df.iloc[0]["team"]

    assert first_team in prompt


# --------------------------------------------------
# Gemini Mock Test
# --------------------------------------------------

@patch("ai_engine.spend_narrative.model.generate_content")
def test_generate_narrative(mock_generate_content):

    mock_response = Mock()
    mock_response.text = "Mock FinOps Narrative"

    mock_generate_content.return_value = mock_response

    result = generate_narrative("dummy prompt")

    assert result == "Mock FinOps Narrative"


# --------------------------------------------------
# Report Save Tests
# --------------------------------------------------

def test_save_report_creates_file():

    narrative = "Test narrative content"

    file_path = save_report(narrative)

    assert os.path.exists(file_path)


def test_saved_report_contains_content():

    narrative = "FinOps cost reduction opportunity"

    file_path = save_report(narrative)

    with open(file_path, "r") as f:
        content = f.read()

    assert narrative in content


def test_report_has_header():

    narrative = "Sample narrative"

    file_path = save_report(narrative)

    with open(file_path, "r") as f:
        content = f.read()

    assert "# FinOps AI Report" in content


# --------------------------------------------------
# Empty Data Handling
# --------------------------------------------------

def test_build_prompt_with_empty_dataframes():

    empty_df = pd.DataFrame()

    prompt = build_prompt(
        empty_df,
        empty_df,
        empty_df,
        empty_df
    )

    assert isinstance(prompt, str)
    assert len(prompt) > 0