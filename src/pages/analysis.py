import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from pathlib import Path

# Import the data layer – assumed to be implemented elsewhere in the project.
# The data_layer module must expose the following callables:
#   - load_emissions_data() -> pd.DataFrame
#   - load_population_data() -> pd.DataFrame
#   - load_gdp_data() -> pd.DataFrame
#   - get_available_countries() -> List[str]
#   - get_available_years() -> List[int]
#   - get_available_sectors() -> List[str]
#   - compute_kpis(filters: Dict) -> Dict[str, float]
# If any of these functions are missing, an ImportError will be raised at import time.
try:
    from src.data_layer import (
        load_emissions_data,
        load_population_data,
        load_gdp_data,
        get_available_countries,
        get_available_years,
        get_available_sectors,
        compute_kpis,
    )
except ImportError as exc:
    raise ImportError(
        "The data_layer module could not be imported. Ensure it exists under src/ and "
        "exposes the required functions."
    ) from exc


def _filter_emissions(
    df: pd.DataFrame,
    countries: List[str],
    years: Tuple[int, int],
    sectors: List[str],
) -> pd.DataFrame:
    """Return a filtered view of the emissions DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Raw emissions data with at least the columns ``country``, ``year`` and ``sector``.
    countries : List[str]
        List of ISO‑3 country codes or names to keep.
    years : Tuple[int, int]
        Inclusive start and end year.
    sectors : List[str]
        List of sector names to keep.

    Returns
    -------
    pd.DataFrame
        Filtered DataFrame.
    """
    start, end = years
    mask = (
        df["country"].isin(countries)
        & df["year"].between(start, end, inclusive="both")
        & df["sector"].isin(sectors)
    )
    return df.loc[mask].copy()


def _prepare_stacked_area_data(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot emissions data for a stacked area chart.

    The resulting DataFrame has ``year`` as index and one column per sector
    containing the sum of emissions for the selected countries.

    Parameters
    ----------
    df : pd.DataFrame
        Filtered emissions data.

    Returns
    -------
    pd.DataFrame
        Pivoted DataFrame ready for ``px.area``.
    """
    pivot = (
        df.groupby(["year", "sector"])["co2_mt"]
        .sum()
        .reset_index()
        .pivot(index="year", columns="sector", values="co2_mt")
        .fillna(0)
        .astype(float)
    )
    pivot = pivot.sort_index()
    return pivot


def _prepare_donut_data(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Aggregate sector emissions for a single year to build a donut chart.

    Parameters
    ----------
    df : pd.DataFrame
        Filtered emissions data.
    year : int
        Year for which the aggregation is performed.

    Returns
    -------
    pd.DataFrame
        Two‑column DataFrame with ``sector`` and ``value`` (MtCO₂).
    """
    year_df = df[df["year"] == year]
    if year_df.empty:
        return pd.DataFrame(columns=["sector", "value"])
    agg = (
        year_df.groupby("sector")["co2_mt"]
        .sum()
        .reset_index()
        .rename(columns={"co2_mt": "value"})
    )
    return agg


def _display_kpis(filters: Dict) -> None:
    """Render KPI metrics in a three‑column layout.

    Parameters
    ----------
    filters : dict
        Dictionary passed to ``compute_kpis``.
    """
    try:
        kpis = compute_kpis(filters)
    except Exception as exc:  # pragma: no cover – defensive programming
        st.error(f"❗️ Impossible de calculer les KPI : {exc}")
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(
        "Émissions totales (MtCO₂)",
        f"{kpis.get('total_emissions', 0):,.2f}",
        delta=f"{kpis.get('annual_change_pct', 0):+.2f} %",
    )
    col2.metric(
        "Émissions / habitant (tCO₂)",
        f"{kpis.get('per_capita', 0):,.2f}",
    )
    col3.metric(
        "Intensité carbone du PIB (kgCO₂/USD)",
        f"{kpis.get('intensity_gdp', 0):,.2f}",
    )
    col4.metric(
        "Variation annuelle moyenne (%)",
        f"{kpis.get('avg_annual_variation', 0):,.2f}",
    )
    col5.metric(
        "Part énergie (%)",
        f"{kpis.get('energy_sector_share', 0):,.2f}",
    )


def render_analysis_page() -> None:
    """Render the **Analyse avancée** page.

    This page provides multi‑dimensional filters (pays, période, secteur) and
    interactive Plotly visualisations:
        * Line chart – évolution des émissions totales par pays.
        * Stacked area chart – répartition sectorielle dans le temps.
        * Donut chart – part de chaque secteur pour un pays et une année choisis.
    """
    st.title("🔎 Analyse avancée")

    # ----------------------------------------------------------------------
    # Sidebar – global filters (shared across the application)
    # ----------------------------------------------------------------------
    with st.sidebar:
        st.header("Filtres globaux")
        countries = st.multiselect(
            "Pays",
            options=get_available_countries(),
            default=get_available_countries()[:5],
            help="Sélectionnez un ou plusieurs pays à analyser.",
        )
        years = st.slider(
            "Période",
            min_value=min(get_available_years()),
            max_value=max(get_available_years()),
            value=(
                min(get_available_years()),
                max(get_available_years()),
            ),
            step=1,
        )
        sectors = st.multiselect(
            "Secteurs",
            options=get_available_sectors(),
            default=get_available_sectors(),
            help="Sélectionnez les secteurs d’émission à inclure.",
        )
        refresh = st.button("🔄 Rafraîchir le cache", type="primary")
        if refresh:
            # Invalidate all cached data – Streamlit will recompute on next run.
            st.experimental_rerun()

    if not countries:
        st.warning("Veuillez sélectionner au moins un pays.")
        st.stop()

    # ----------------------------------------------------------------------
    # Load data – cached at the session level
    # ----------------------------------------------------------------------
    @st.cache_data(show_spinner=False)
    def _load_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        emissions = load_emissions_data()
        population = load_population_data()
        gdp = load_gdp_data()
        return emissions, population, gdp

    try:
        emissions_df, population_df, gdp_df = _load_data()
    except Exception as exc:  # pragma: no cover
        st.error(f"❗️ Erreur lors du chargement des données : {exc}")
        st.stop()

    # ----------------------------------------------------------------------
    # Filter data according to user selections
    # ----------------------------------------------------------------------
    filtered_emissions = _filter_emissions(
        emissions_df,
        countries=countries,
        years=years,
        sectors=sectors,
    )
    if filtered_emissions.empty:
        st.info("Aucune donnée disponible pour la combinaison de filtres sélectionnée.")
        st.stop()

    # ----------------------------------------------------------------------
    # KPI section
    # ----------------------------------------------------------------------
    st.subheader("📊 Indicateurs clés")
    kpi_filters = {
        "countries": countries,
        "years": years,
        "sectors": sectors,
    }
    _display_kpis(kpi_filters)

    # ----------------------------------------------------------------------
    # Visualisations
    # ----------------------------------------------------------------------
    st.subheader("📈 Évolution des émissions totales")
    line_df = (
        filtered_emissions.groupby(["year", "country"])["co2_mt"]
        .sum()
        .reset_index()
    )
    fig_line = px.line(
        line_df,
        x="year",
        y="co2_mt",
        color="country",
        labels={"co2_mt": "Émissions (MtCO₂)", "year": "Année"},
        title="Émissions totales de CO₂ par pays",
    )
    fig_line.update_layout(hovermode="x unified")
    st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("🗺️ Répartition sectorielle dans le temps")
    area_df = _prepare_stacked_area_data(filtered_emissions)
    fig_area = px.area(
        area_df,
        x=area_df.index,
        y=area_df.columns,
        labels={"value": "Émissions (MtCO₂)", "year": "Année"},
        title="Part des secteurs dans les émissions totales",
    )
    fig_area.update_layout(legend_title_text="Secteur")
    st.plotly_chart(fig_area, use_container_width=True)

    st.subheader("🥧 Répartition sectorielle pour un pays et une année")
    col_country, col_year = st.columns(2)
    with col_country:
        selected_country = st.selectbox(
            "Pays",
            options=countries,
            index=0,
            help="Pays pour lequel la part sectorielle sera affichée.",
        )
    with col_year:
        selected_year = st.selectbox(
            "Année",
            options=sorted(set(filtered_emissions["year"])),
            index=0,
            help="Année pour laquelle la part sectorielle sera affichée.",
        )
    # Filter for the selected country
    country_df = filtered_emissions[filtered_emissions["country"] == selected_country]
    donut_df = _prepare_donut_data(country_df, selected_year)

    if donut_df.empty:
        st.info("Aucune donnée sectorielle disponible pour ce pays/année.")
    else:
        fig_donut = px.pie(
            donut_df,
            names="sector",
            values="value",
            hole=0.4,
            title=f"Part sectorielle des émissions en {selected_year} – {selected_country}",
        )
        fig_donut.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_donut, use_container_width=True)

    # ----------------------------------------------------------------------
    # Optional: Export filtered data
    # ----------------------------------------------------------------------
    with st.expander("💾 Exporter les données filtrées"):
        csv = filtered_emissions.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Télécharger le CSV",
            data=csv,
            file_name=f"emissions_{datetime.now():%Y%m%d_%H%M%S}.csv",
            mime="text/csv",
        )
        st.dataframe(
            filtered_emissions.head(10),
            use_container_width=True,
            hide_index=True,
        )
