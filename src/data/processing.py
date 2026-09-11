import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Literal, Mapping, Optional, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #

Country = str
Sector = str
Year = int
Metric = Literal[
    "total_emissions",
    "emissions_per_capita",
    "carbon_intensity",
    "average_annual_change",
    "sector_share",
]

# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class KPIResult:
    """Container for KPI values computed on a filtered dataset."""

    total_emissions: float
    emissions_per_capita: float
    carbon_intensity: float
    average_annual_change: float
    sector_share: Dict[Sector, float]


# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #


def _validate_year_range(years: Tuple[int, int]) -> Tuple[int, int]:
    """Validate that a year range is well‑formed.

    Args:
        years: Tuple ``(start_year, end_year)``.

    Returns:
        The same tuple if validation succeeds.

    Raises:
        ValueError: If ``start_year`` > ``end_year`` or any year is negative.
    """
    start, end = years
    if start > end:
        raise ValueError(f"Start year ({start}) cannot be greater than end year ({end}).")
    if start < 0 or end < 0:
        raise ValueError("Years must be non‑negative integers.")
    return start, end


def _safe_divide(numerator: Union[int, float, pd.Series], denominator: Union[int, float, pd.Series]) -> Union[float, pd.Series]:
    """Perform division protecting against division by zero.

    Returns ``float('nan')`` or ``pd.NA`` where the denominator is zero.
    """
    with pd.option_context("mode.use_inf_as_na", True):
        result = numerator / denominator.replace({0: pd.NA})
    return result


# --------------------------------------------------------------------------- #
# Core processing functions
# --------------------------------------------------------------------------- #


def download_csv(url: str, *, timeout: int = 30) -> pd.DataFrame:
    """Download a CSV file from a URL and return it as a DataFrame.

    The function uses ``pandas.read_csv`` with a small set of defaults that
    work for the OWID and World Bank CSV sources.

    Args:
        url: Direct link to the CSV file.
        timeout: HTTP timeout in seconds.

    Returns:
        DataFrame containing the raw CSV data.

    Raises:
        RuntimeError: If the request fails or the CSV cannot be parsed.
    """
    try:
        df = pd.read_csv(url, low_memory=False)
        logger.debug("CSV downloaded successfully from %s – shape=%s", url, df.shape)
        return df
    except Exception as exc:  # pragma: no cover – defensive
        logger.exception("Failed to download or parse CSV from %s", url)
        raise RuntimeError(f"Unable to download CSV from {url}") from exc


def clean_owid_co2(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the OWID CO₂ emissions dataset.

    The function:
    * Renames columns to snake_case.
    * Parses the ``year`` column as ``int``.
    * Ensures the ``country`` column is of type ``str``.
    * Filters out rows with missing emission values.

    Args:
        df: Raw OWID CO₂ DataFrame.

    Returns:
        Cleaned DataFrame with columns ``country``, ``year``, ``co2`` and
        sector‑specific columns (e.g. ``co2_energy``).

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"Country", "Year", "CO2"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"OWID CO₂ data is missing required columns: {missing}")

    df = df.rename(columns=lambda c: c.strip().lower().replace(" ", "_"))
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["country"] = df["country"].astype(str).str.strip()

    # Keep only rows with a valid year and CO₂ value
    df = df.dropna(subset=["year", "co2"])
    logger.debug("OWID CO₂ cleaned – rows after dropna: %d", len(df))
    return df


def clean_world_bank(df: pd.DataFrame, value_column: str) -> pd.DataFrame:
    """Standardise a World Bank indicator DataFrame.

    The World Bank API returns a wide format where each year is a column.
    This function melts the DataFrame into a tidy long format.

    Args:
        df: Raw World Bank DataFrame.
        value_column: Name to assign to the indicator values (e.g. ``population``).

    Returns:
        Tidy DataFrame with columns ``country``, ``year`` and the supplied
        ``value_column``.

    Raises:
        ValueError: If the DataFrame does not contain a ``Country Name`` column.
    """
    if "Country Name" not in df.columns:
        raise ValueError("World Bank data must contain a 'Country Name' column.")

    id_vars = ["Country Name", "Country Code"]
    year_cols = [c for c in df.columns if c.isdigit()]

    tidy = df.melt(
        id_vars=id_vars,
        value_vars=year_cols,
        var_name="year",
        value_name=value_column,
    )
    tidy = tidy.rename(columns={"Country Name": "country", "Country Code": "country_code"})
    tidy["year"] = pd.to_numeric(tidy["year"], errors="coerce").astype("Int64")
    tidy[value_column] = pd.to_numeric(tidy[value_column], errors="coerce")
    logger.debug(
        "World Bank %s cleaned – rows: %d, years: %d",
        value_column,
        tidy.shape[0],
        tidy["year"].nunique(),
    )
    return tidy


def normalize_country_names(df: pd.DataFrame, country_col: str = "country") -> pd.DataFrame:
    """Standardise country names to a canonical representation.

    The function strips whitespace, title‑cases the names and replaces known
    aliases (e.g. ``United States`` → ``United States of America``).

    Args:
        df: DataFrame containing a country column.
        country_col: Name of the column holding country names.

    Returns:
        DataFrame with a normalized ``country`` column.
    """
    alias_map = {
        "United States": "United States of America",
        "Russia": "Russian Federation",
        "South Korea": "Korea, Rep.",
        "North Korea": "Korea, Dem. People's Rep.",
        "Iran": "Iran, Islamic Rep.",
        "Venezuela": "Venezuela, RB",
    }

    def _norm(name: Any) -> str:
        if not isinstance(name, str):
            return ""
        name = name.strip()
        name = alias_map.get(name, name)
        return name.title()

    df = df.copy()
    df[country_col] = df[country_col].apply(_norm)
    logger.debug("Country names normalized in column '%s'.", country_col)
    return df


def merge_datasets(
    co2_df: pd.DataFrame,
    pop_df: pd.DataFrame,
    gdp_df: pd.DataFrame,
    *,
    on: Tuple[str, str] = ("country", "year"),
) -> pd.DataFrame:
    """Merge CO₂, population and GDP datasets into a single analytical table.

    The merge is performed as an inner join to keep only rows where all three
    indicators are available.

    Args:
        co2_df: Cleaned CO₂ emissions DataFrame.
        pop_df: Population DataFrame (column ``population``).
        gdp_df: GDP DataFrame (column ``gdp``).
        on: Columns to join on.

    Returns:
        DataFrame with columns ``country``, ``year``, ``co2``, ``population``,
        ``gdp`` and any sector‑specific CO₂ columns present in ``co2_df``.
    """
    merged = (
        co2_df.merge(pop_df, on=on, how="inner")
        .merge(gdp_df, on=on, how="inner")
        .astype({"year": "Int64"})
    )
    logger.debug(
        "Datasets merged – resulting shape: %s (countries: %d, years: %d)",
        merged.shape,
        merged["country"].nunique(),
        merged["year"].nunique(),
    )
    return merged


def filter_data(
    df: pd.DataFrame,
    *,
    countries: Optional[Iterable[Country]] = None,
    years: Optional[Tuple[int, int]] = None,
    sectors: Optional[Iterable[Sector]] = None,
) -> pd.DataFrame:
    """Apply multi‑dimensional filters to the analytical DataFrame.

    Args:
        df: The merged analytical DataFrame.
        countries: Iterable of country names to keep. If ``None`` keep all.
        years: Tuple ``(start, end)`` inclusive. If ``None`` keep all.
        sectors: Iterable of sector column suffixes (e.g. ``energy``). If
            ``None`` keep all sector columns.

    Returns:
        Filtered DataFrame.
    """
    filtered = df.copy()

    if countries is not None:
        country_set = {c.strip() for c in countries}
        filtered = filtered[filtered["country"].isin(country_set)]

    if years is not None:
        start, end = _validate_year_range(years)
        filtered = filtered[(filtered["year"] >= start) & (filtered["year"] <= end)]

    if sectors is not None:
        sector_cols = [col for col in filtered.columns if any(s in col for s in sectors)]
        # Keep core columns plus selected sector columns
        core = ["country", "year", "co2", "population", "gdp"]
        filtered = filtered[core + sector_cols]

    logger.debug(
        "Data filtered – rows: %d, countries: %d, years: %d",
        filtered.shape[0],
        filtered["country"].nunique(),
        filtered["year"].nunique(),
    )
    return filtered


def calculate_total_emissions(df: pd.DataFrame) -> float:
    """Compute the total CO₂ emissions (MtCO₂) for the supplied rows.

    Args:
        df: DataFrame containing a ``co2`` column.

    Returns:
        Sum of emissions as a float. Returns ``0.0`` if the DataFrame is empty.
    """
    total = float(df["co2"].sum(skipna=True))
    logger.debug("Total emissions calculated: %f MtCO₂", total)
    return total


def calculate_emissions_per_capita(df: pd.DataFrame) -> pd.Series:
    """Calculate emissions per capita (tCO₂ / person) for each row.

    The result is a ``pandas.Series`` indexed like the input DataFrame.

    Args:
        df: DataFrame with ``co2`` (MtCO₂) and ``population`` columns.

    Returns:
        Series of emissions per capita in tonnes.
    """
    # Convert MtCO₂ to tonnes (1 Mt = 1e6 tonnes)
    emissions_tonnes = df["co2"] * 1_000_000
    per_capita = _safe_divide(emissions_tonnes, df["population"])
    logger.debug("Emissions per capita calculated for %d rows.", len(per_capita))
    return per_capita


def calculate_carbon_intensity(df: pd.DataFrame) -> pd.Series:
    """Calculate carbon intensity of GDP (kgCO₂ per USD).

    Args:
        df: DataFrame with ``co2`` (MtCO₂) and ``gdp`` (USD) columns.

    Returns:
        Series of carbon intensity values.
    """
    # Convert MtCO₂ to kg (1 Mt = 1e9 kg)
    emissions_kg = df["co2"] * 1_000_000_000
    intensity = _safe_divide(emissions_kg, df["gdp"])
