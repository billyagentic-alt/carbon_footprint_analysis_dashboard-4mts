import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Configuration constants
# --------------------------------------------------------------------------- #

OWID_CO2_URL: str = (
    "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
)
WORLD_BANK_API_ROOT: str = "http://api.worldbank.org/v2"
DEFAULT_PER_PAGE: int = 10_000
UNFCCC_API_ROOT: str = "https://unfccc.int/api/v1"  # Placeholder; actual endpoint may differ


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class DataFetchError(RuntimeError):
    """Raised when a data source cannot be retrieved or parsed."""


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #


def _request_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Any:
    """Perform a GET request and return the JSON payload.

    Args:
        url: Target URL.
        params: Optional query parameters.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        DataFetchError: If the request fails or the response cannot be decoded.
    """
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("Request to %s failed: %s", url, exc)
        raise DataFetchError(f"Failed to fetch JSON data from {url}") from exc
    except ValueError as exc:
        logger.error("Invalid JSON from %s: %s", url, exc)
        raise DataFetchError(f"Invalid JSON response from {url}") from exc


def _request_csv(url: str, timeout: int = 30) -> pd.DataFrame:
    """Download a CSV file and load it into a pandas DataFrame.

    Args:
        url: Direct link to the CSV file.
        timeout: Request timeout in seconds.

    Returns:
        DataFrame containing the CSV data.

    Raises:
        DataFetchError: If the request fails or the CSV cannot be parsed.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return pd.read_csv(pd.compat.StringIO(response.text))
    except requests.RequestException as exc:
        logger.error("CSV request to %s failed: %s", url, exc)
        raise DataFetchError(f"Failed to download CSV from {url}") from exc
    except Exception as exc:  # pandas errors, UnicodeDecodeError, etc.
        logger.error("Parsing CSV from %s failed: %s", url, exc)
        raise DataFetchError(f"Failed to parse CSV from {url}") from exc


# --------------------------------------------------------------------------- #
# Public data‑fetching API
# --------------------------------------------------------------------------- #


@st.cache_data(show_spinner="Downloading OWID CO₂ emissions data…", ttl=86400)
def fetch_owid_co2(csv_url: str = OWID_CO2_URL) -> pd.DataFrame:
    """Fetch the OWID CO₂ emissions dataset.

    The dataset contains country‑level CO₂ emissions by sector and year.

    Args:
        csv_url: URL of the CSV file (defaults to the official OWID repository).

    Returns:
        DataFrame with the raw OWID CO₂ data.

    Raises:
        DataFetchError: If the download or parsing fails.
    """
    logger.info("Fetching OWID CO₂ data from %s", csv_url)
    df = _request_csv(csv_url)
    # Basic sanity check
    required_columns = {"country", "year", "co2", "co2_per_capita", "co2_per_gdp"}
    missing = required_columns - set(df.columns.str.lower())
    if missing:
        logger.warning("OWID dataset missing expected columns: %s", missing)
    return df


@st.cache_data(show_spinner="Downloading World Bank indicator data…", ttl=86400)
def fetch_world_bank_indicator(
    indicator: str,
    country_codes: Optional[List[str]] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> pd.DataFrame:
    """Retrieve a World Bank indicator for a set of countries and years.

    Args:
        indicator: World Bank indicator code (e.g. ``SP.POP.TOTL`` for population).
        country_codes: ISO‑2/ISO‑3 country codes. If ``None``, data for all countries
            is requested.
        start_year: First year of the period (inclusive). If ``None`` the API default
            is used.
        end_year: Last year of the period (inclusive). If ``None`` the API default
            is used.

    Returns:
        DataFrame with columns ``country``, ``countryiso3code``, ``date`` and ``value``.

    Raises:
        DataFetchError: If the request fails or the response cannot be interpreted.
    """
    logger.info(
        "Fetching World Bank indicator %s for countries=%s, years=%s-%s",
        indicator,
        country_codes or "all",
        start_year or "default",
        end_year or "default",
    )

    # Build request URL
    countries_part = ";".join(country_codes) if country_codes else "all"
    url = f"{WORLD_BANK_API_ROOT}/country/{countries_part}/indicator/{indicator}"

    # Build query parameters
    params: Dict[str, Any] = {
        "format": "json",
        "per_page": DEFAULT_PER_PAGE,
    }
    if start_year or end_year:
        date_range = f"{start_year or ''}:{end_year or ''}"
        params["date"] = date_range

    # Retrieve JSON payload (first page contains metadata)
    payload = _request_json(url, params=params)

    if not isinstance(payload, list) or len(payload) < 2:
        raise DataFetchError(f"Unexpected World Bank response structure for {indicator}")

    records: List[Dict[str, Any]] = payload[1]

    # Convert to DataFrame
    df = pd.DataFrame.from_records(records)
    # Rename columns for consistency
    df = df.rename(
        columns={
            "country": "country_name",
            "countryiso3code": "country_iso3",
            "date": "year",
            "value": "value",
        }
    )
    # Ensure correct dtypes
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


@st.cache_data(show_spinner="Downloading UNFCCC inventory data…", ttl=86400)
def fetch_unfccc_inventory(
    api_key: Optional[str] = None,
    country_codes: Optional[List[str]] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> pd.DataFrame:
    """Fetch national greenhouse‑gas inventory data from the UNFCCC API.

    The UNFCCC API is optional and may require authentication. If ``api_key`` is not
    provided, the function returns an empty DataFrame and logs a warning.

    Args:
        api_key: Authentication token for the UNFCCC API.
        country_codes: List of ISO‑3 country codes to filter on.
        start_year: First year of interest.
        end_year: Last year of interest.

    Returns:
        DataFrame with inventory data. Columns depend on the UNFCCC endpoint but
        typically include ``country``, ``year``, ``gas``, ``value`` and ``unit``.

    Raises:
        DataFetchError: If the request fails and an API key was supplied.
    """
    if not api_key:
        logger.warning(
            "UNFCCC API key not provided – returning empty inventory DataFrame."
        )
        return pd.DataFrame()

    logger.info(
        "Fetching UNFCCC inventory for countries=%s, years=%s-%s",
        country_codes or "all",
        start_year or "default",
        end_year or "default",
    )

    endpoint = f"{UNFCCC_API_ROOT}/inventories"
    params: Dict[str, Any] = {"api_key": api_key, "format": "json"}

    if country_codes:
        params["country"] = ",".join(country_codes)
    if start_year:
        params["start_year"] = start_year
    if end_year:
        params["end_year"] = end_year

    payload = _request_json(endpoint, params=params)

    # The exact structure varies; attempt a best‑effort conversion.
    if not isinstance(payload, dict) or "data" not in payload:
        raise DataFetchError("UNFCCC response does not contain expected 'data' field")

    records = payload["data"]
    df = pd.DataFrame.from_records(records)

    # Normalise column names if possible
    rename_map = {
        "country": "country_name",
        "iso3": "country_iso3",
        "year": "year",
        "gas": "gas",
        "value": "value",
        "unit": "unit",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Type conversion
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

    return df


# --------------------------------------------------------------------------- #
# Exported symbols
# --------------------------------------------------------------------------- #

__all__: Tuple[str, ...] = (
    "fetch_owid_co2",
    "fetch_world_bank_indicator",
    "fetch_unfccc_inventory",
    "DataFetchError",
)
