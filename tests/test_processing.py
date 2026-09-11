import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest
import requests
from plotly.graph_objs import Figure

# Assuming the project structure:
# - data_layer.py contains: download_owid_data, download_world_bank_data, transform_data, calculate_kpis
# - visuals/charts.py contains: line_chart, stacked_area_chart, bar_chart, donut_chart

from data_layer import (
    download_owid_data,
    download_world_bank_data,
    transform_data,
    calculate_kpis,
)
from visuals.charts import (
    line_chart,
    stacked_area_chart,
    bar_chart,
    donut_chart,
)


@pytest.fixture
def mock_owid_csv(tmp_path: Path) -> Path:
    """Create a temporary CSV file mimicking the OWID CO₂ dataset."""
    data = {
        "country": ["CountryA", "CountryA", "CountryB", "CountryB"],
        "year": [2020, 2021, 2020, 2021],
        "sector": ["Energy", "Energy", "Transport", "Transport"],
        "co2": [100.0, 110.0, 50.0, 55.0],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "owid_co2.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def mock_world_bank_json() -> Dict[str, Any]:
    """Mock response payload from the World Bank API."""
    return {
        "country": [
            {"id": "CTA", "name": "CountryA"},
            {"id": "CTB", "name": "CountryB"},
        ],
        "indicator": [
            {
                "id": "SP.POP.TOTL",
                "value": "Population",
                "country": {"id": "CTA"},
                "date": "2020",
                "value": 10_000_000,
            },
            {
                "id": "SP.POP.TOTL",
                "value": "Population",
                "country": {"id": "CTA"},
                "date": "2021",
                "value": 10_100_000,
            },
            {
                "id": "SP.POP.TOTL",
                "value": "Population",
                "country": {"id": "CTB"},
                "date": "2020",
                "value": 5_000_000,
            },
            {
                "id": "SP.POP.TOTL",
                "value": "Population",
                "country": {"id": "CTB"},
                "date": "2021",
                "value": 5_050_000,
            },
        ],
    }


def test_download_owid_data_success(monkeypatch: pytest.MonkeyPatch, mock_owid_csv: Path) -> None:
    """Verify that download_owid_data returns a DataFrame when the request succeeds."""

    class MockResponse:
        status_code = 200

        def __init__(self, path: Path) -> None:
            self._path = path

        def raise_for_status(self) -> None:
            pass

        @property
        def content(self) -> bytes:
            return self._path.read_bytes()

    def mock_get(url: str, timeout: int = 10) -> MockResponse:  # noqa: D401
        """Return a mock response containing the temporary CSV."""
        return MockResponse(mock_owid_csv)

    monkeypatch.setattr(requests, "get", mock_get)

    df = download_owid_data("https://example.com/owid_co2.csv")
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {"country", "year", "sector", "co2"}
    assert len(df) == 4
    assert df["co2"].sum() == 315.0


def test_download_owid_data_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure that download_owid_data raises a RuntimeError on HTTP errors."""

    class MockResponse:
        status_code = 404

        def raise_for_status(self) -> None:
            raise requests.HTTPError("Not Found")

    monkeypatch.setattr(requests, "get", lambda *_, **__: MockResponse())

    with pytest.raises(RuntimeError, match="Failed to download OWID data"):
        download_owid_data("https://example.com/missing.csv")


def test_transform_data_basic() -> None:
    """Test that transform_data correctly merges CO₂, population, and GDP data."""
    co2_df = pd.DataFrame(
        {
            "country": ["CountryA", "CountryA", "CountryB"],
            "year": [2020, 2021, 2020],
            "sector": ["Energy", "Energy", "Transport"],
            "co2": [100.0, 110.0, 50.0],
        }
    )
    pop_df = pd.DataFrame(
        {
            "country": ["CountryA", "CountryA", "CountryB"],
            "year": [2020, 2021, 2020],
            "population": [10_000_000, 10_100_000, 5_000_000],
        }
    )
    gdp_df = pd.DataFrame(
        {
            "country": ["CountryA", "CountryB"],
            "year": [2020, 2020],
            "gdp": [500_000_000_000, 200_000_000_000],
        }
    )

    merged = transform_data(co2_df, pop_df, gdp_df)

    # Expected columns after transformation
    expected_cols = {
        "country",
        "year",
        "sector",
        "co2",
        "population",
        "gdp",
        "co2_per_capita",
        "co2_intensity_gdp",
    }
    assert set(merged.columns) == expected_cols

    # Verify calculations for a known row
    row = merged.query("country == 'CountryA' and year == 2020 and sector == 'Energy'").iloc[0]
    assert row["co2"] == 100.0
    assert row["population"] == 10_000_000
    assert row["gdp"] == 500_000_000_000
    assert pytest.approx(row["co2_per_capita"], rel=1e-6) == 0.01  # 100 t / 10M = 0.01 t per person
    assert pytest.approx(row["co2_intensity_gdp"], rel=1e-6) == 2e-7  # 100 t / 5e11 USD


def test_calculate_kpis_basic() -> None:
    """Validate KPI calculations on a small synthetic dataset."""
    data = pd.DataFrame(
        {
            "country": ["CountryA", "CountryA", "CountryB", "CountryB"],
            "year": [2020, 2021, 2020, 2021],
            "sector": ["Energy", "Energy", "Transport", "Transport"],
            "co2": [100.0, 110.0, 50.0, 55.0],
            "population": [10_000_000, 10_100_000, 5_000_000, 5_050_000],
            "gdp": [500_000_000_000, 505_000_000_000, 200_000_000_000, 202_000_000_000],
        }
    )
    filters = {"countries": ["CountryA", "CountryB"], "years": [2020, 2021]}

    kpis = calculate_kpis(data, filters)

    # Expected KPI keys
    expected_keys = {
        "total_co2",
        "co2_per_capita",
        "co2_intensity_gdp",
        "average_annual_change_pct",
        "energy_sector_share_pct",
    }
    assert set(kpis.keys()) == expected_keys

    # Verify numeric values
    assert pytest.approx(kpis["total_co2"], rel=1e-6) == 315.0
    # total population = 10M+10.1M+5M+5.05M = 30.15M
    assert pytest.approx(kpis["co2_per_capita"], rel=1e-6) == 315.0 / 30_150_000
    # total gdp = 500B+505B+200B+202B = 1.407T
    assert pytest.approx(kpis["co2_intensity_gdp"], rel=1e-6) == 315.0 / 1_407_000_000_000
    # average annual change: ((110-100)+(55-50))/2 / previous year total = (10+5)/2 / 265 = 0.028301... => 2.83%
    assert pytest.approx(kpis["average_annual_change_pct"], rel=1e-4) == 2.8301
    # Energy sector share: only CountryA Energy rows = 210 / 315 = 66.666...
    assert pytest.approx(kpis["energy_sector_share_pct"], rel=1e-4) == 66.6667


@pytest.mark.parametrize(
    "chart_func, args, expected_trace_type",
    [
        (line_chart, [{"country": "CountryA", "year": [2020, 2021], "co2": [100, 110]}], "scatter"),
        (
            stacked_area_chart,
            [{"country": "CountryA", "year": [2020, 2021], "sector": ["Energy", "Energy"], "co2": [100, 110]}],
            "scatter",
        ),
        (
            bar_chart,
            [{"countries": ["CountryA", "CountryB"], "co2_per_capita": [0.01, 0.011]}],
            "bar",
        ),
        (
            donut_chart,
            [{"country": "CountryA", "sectors": ["Energy", "Transport"], "co2": [100, 20]}],
            "pie",
        ),
    ],
)
def test_chart_functions_return_figure(
    chart_func,
    args: List[Dict[str, Any]],
    expected_trace_type: str,
) -> None:
    """All chart helpers must return a Plotly Figure with at least one trace of the expected type."""
    fig: Figure = chart_func(**args[0])  # type: ignore[arg-type]
    assert isinstance(fig, Figure)
    assert len(fig.data) > 0
    # The first trace type should match the expectation (scatter for line/area, bar for bar, pie for donut)
    assert fig.data[0].type == expected_trace_type


def test_line_chart_invalid_input() -> None:
    """Line chart should raise a ValueError when required columns are missing."""
    incomplete_data = pd.DataFrame({"country": ["A"], "year": [2020]})  # missing 'co2'
    with pytest.raises(ValueError, match="DataFrame must contain columns"):
        line_chart(incomplete_data)  # type: ignore[arg-type]


def test_donut_chart_zero_total(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the total CO₂ for a country is zero, donut_chart should handle gracefully."""
    zero_data = pd.DataFrame(
        {
            "country": ["CountryZero"],
            "sector": ["Energy", "Transport"],
            "co2": [0, 0],
        }
    )
    # Monkeypatch the internal Plotly call to capture the figure creation without raising
    monkeypatch.setattr("visuals.charts.go.Figure", Figure)

    fig = donut_chart(zero_data)  # type: ignore[arg-type]
    assert isinstance(fig, Figure)
    # All values are zero, so the figure should still contain a trace with zero values
    assert all(v == 0 for v in fig.data[0].values)  # type: ignore[attr-defined]
