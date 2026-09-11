import pandas as pd
import requests
import streamlit as st
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DATA_URL: str = (
    "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
)
DATA_VERSION: str = "v1.0.0"


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
def _download_csv(url: str) -> pd.DataFrame:
    """Download a CSV file from *url* and return it as a DataFrame.

    Args:
        url: The HTTP URL pointing to a CSV file.

    Returns:
        A pandas DataFrame containing the raw CSV data.

    Raises:
        RuntimeError: If the request fails or the content cannot be parsed.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return pd.read_csv(pd.compat.StringIO(response.text))
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to download data from {url!r}: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Unable to parse CSV data from {url!r}: {exc}") from exc


_COUNTRY_NORMALISATION_MAP: Dict[str, str] = {
    "United States": "United States of America",
    "USA": "United States of America",
    "UK": "United Kingdom",
    "Korea, Rep.": "South Korea",
    "Russian Federation": "Russia",
    # Add more mappings as required
}


def _normalize_country(name: str) -> str:
    """Return a canonical country name.

    The function first strips surrounding whitespace, then applies a
    predefined mapping. If the name is not present in the mapping, the
    original (trimmed) name is returned.

    Args:
        name: Raw country name.

    Returns:
        Normalised country name.
    """
    name_clean = name.strip()
    return _COUNTRY_NORMALISATION_MAP.get(name_clean, name_clean)


def _convert_numeric(series: pd.Series) -> pd.Series:
    """Convert a pandas Series to numeric, coercing errors to NaN."""
    return pd.to_numeric(series, errors="coerce")


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
@dataclass
class KPIFilters:
    """Container for KPI filtering criteria.

    Attributes:
        year_range: Inclusive start and end year (e.g. (2000, 2022)).
        countries: List of country names to include. ``None`` means all.
        sectors: List of sector names to include. ``None`` means all.
    """

    year_range: Tuple[int, int] = (2000, 2022)
    countries: Optional[List[str]] = field(default_factory=list)
    sectors: Optional[List[str]] = field(default_factory=list)


@st.cache_data(ttl=86_400, show_spinner=False)
def load_raw_data(version: str = DATA_VERSION) -> pd.DataFrame:
    """Load the raw carbon‑footprint dataset.

    The function is cached; changing the ``DATA_VERSION`` constant forces a
    refresh of the cached data.

    Args:
        version: Internal cache‑busting parameter. Defaults to ``DATA_VERSION``.

    Returns:
        A DataFrame containing the raw, unprocessed data.

    Raises:
        RuntimeError: If the data cannot be downloaded.
    """
    # The ``version`` argument is not used directly but participates in the
    # cache key, ensuring that a bump of ``DATA_VERSION`` invalidates the cache.
    _ = version  # noqa: F841
    return _download_csv(DATA_URL)


@st.cache_data(ttl=86_400, show_spinner=False)
def get_clean_data(version: str = DATA_VERSION) -> pd.DataFrame:
    """Return a cleaned version of the raw dataset.

    Cleaning steps include:
        * Normalising country names.
        * Converting numeric columns to proper dtypes.
        * Parsing the ``year`` column as ``int``.
        * Dropping rows that lack essential information.

    Args:
        version: Cache‑busting version identifier.

    Returns:
        A cleaned pandas DataFrame ready for KPI computation.
    """
    raw = load_raw_data(version=version)

    df = raw.copy()

    # Normalise country names
    if "country" in df.columns:
        df["country"] = df["country"].astype(str).apply(_normalize_country)

    # Ensure a numeric year column
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    # Identify numeric columns (excluding identifiers)
    numeric_cols = [
        col
        for col in df.select_dtypes(include=["object", "float", "int"]).columns
        if col not in {"country", "year", "sector"}
    ]
    for col in numeric_cols:
        df[col] = _convert_numeric(df[col])

    # Drop rows where year is missing – they cannot be filtered sensibly
    df = df.dropna(subset=["year"])

    # Optional: drop rows where country is missing
    df = df.dropna(subset=["country"])

    return df


def get_kpis(filters: KPIFilters) -> Dict[str, pd.Series]:
    """Compute KPI series based on the supplied *filters*.

    The function extracts the cleaned dataset, applies the filter criteria,
    and returns a dictionary of KPI series. Current KPIs include:

        * ``total_emissions`` – total CO₂ emissions per country.
        * ``emissions_per_capita`` – CO₂ emissions per capita per country.
        * ``sector_emissions`` – emissions aggregated by sector.

    Args:
        filters: An instance of :class:`KPIFilters` describing the desired
            subset of the data.

    Returns:
        A dictionary where keys are KPI names and values are pandas Series
        indexed by the appropriate dimension (e.g., country or sector).
    """
    df = get_clean_data()

    # Apply year filter
    start_year, end_year = filters.year_range
    mask = df["year"].between(start_year, end_year, inclusive="both")
    df = df.loc[mask]

    # Apply country filter if provided
    if filters.countries:
        selected_countries = { _normalize_country(c) for c in filters.countries }
        df = df[df["country"].isin(selected_countries)]

    # Apply sector filter if provided and the column exists
    if filters.sectors and "sector" in df.columns:
        df = df[df["sector"].isin(filters.sectors)]

    # Compute KPIs
    kpis: Dict[str, pd.Series] = {}

    # Total emissions per country (assuming column name 'co2')
    if "co2" in df.columns:
        total_emissions = (
            df.groupby("country")["co2"]
            .sum()
            .sort_values(ascending=False)
        )
        kpis["total_emissions"] = total_emissions

    # Emissions per capita (assuming columns 'co2' and 'population')
    if {"co2", "population"}.issubset(df.columns):
        emissions_per_capita = (
            df.groupby("country")
            .apply(lambda g: (g["co2"].sum() / g["population"].sum()))
            .rename("emissions_per_capita")
            .sort_values(ascending=False)
        )
        kpis["emissions_per_capita"] = emissions_per_capita

    # Sector emissions (if sector column exists)
    if "sector" in df.columns and "co2" in df.columns:
        sector_emissions = (
            df.groupby("sector")["co2"]
            .sum()
            .sort_values(ascending=False)
        )
        kpis["sector_emissions"] = sector_emissions

    return kpis


__all__ = [
    "load_raw_data",
    "get_clean_data",
    "get_kpis",
    "KPIFilters",
]