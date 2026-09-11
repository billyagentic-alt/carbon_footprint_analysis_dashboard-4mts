import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Tuple, List, Optional

# Import the data‑layer functions. They must be implemented in ``src/data_layer.py``.
# Expected signatures (examples):
#   get_global_kpis(year_range: Tuple[int, int]) -> dict[str, float]
#   get_emissions_timeseries(year_range: Tuple[int, int]) -> pd.DataFrame
#   get_country_emissions_geojson(year: int) -> Tuple[pd.DataFrame, dict]
#   get_available_years() -> List[int]
#   refresh_cache() -> None
from src.data_layer import (
    get_global_kpis,
    get_emissions_timeseries,
    get_country_emissions_geojson,
    get_available_years,
    refresh_cache,
)


def _load_year_options() -> List[int]:
    """Return the list of years available in the dataset.

    The function is cached because the list does not change often.
    """
    try:
        years = get_available_years()
        if not years:
            raise ValueError("Aucune année disponible dans les données.")
        return sorted(years)
    except Exception as exc:  # pragma: no cover
        st.error(f"Erreur lors du chargement des années : {exc}")
        return []


def _draw_global_emissions_chart(df: pd.DataFrame) -> None:
    """Render a line chart showing the evolution of global CO₂ emissions.

    Parameters
    ----------
    df: pd.DataFrame
        Must contain columns ``year`` (int) and ``co2_mt`` (float).
    """
    if df.empty:
        st.warning("Aucune donnée d'émissions disponible pour la période sélectionnée.")
        return

    fig = px.line(
        df,
        x="year",
        y="co2_mt",
        title="Évolution annuelle des émissions mondiales de CO₂",
        labels={"year": "Année", "co2_mt": "Émissions (MtCO₂)"},
        markers=True,
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)


def _draw_choropleth_map(df: pd.DataFrame, geojson: dict) -> None:
    """Render a choropleth map of CO₂ emissions per country for a given year.

    Parameters
    ----------
    df: pd.DataFrame
        Must contain columns ``iso_code`` (str) and ``co2_mt`` (float).
    geojson: dict
        GeoJSON feature collection compatible with Plotly Express.
    """
    if df.empty:
        st.warning("Aucune donnée géographique disponible pour l'année sélectionnée.")
        return

    fig = px.choropleth(
        df,
        geojson=geojson,
        locations="iso_code",
        color="co2_mt",
        hover_name="country",
        color_continuous_scale="YlOrRd",
        title=f"Émissions de CO₂ par pays en {df['year'].iloc[0]} (MtCO₂)",
        labels={"co2_mt": "Émissions (MtCO₂)"},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)


def _display_kpis(kpis: dict) -> None:
    """Display the main KPI metrics in a responsive 4‑column layout.

    Parameters
    ----------
    kpis: dict
        Mapping KPI name → numeric value.
    """
    col1, col2, col3, col4 = st.columns(4)

    # Helper to format numbers with appropriate units
    def _fmt(value: Optional[float], unit: str = "") -> str:
        if value is None:
            return "N/A"
        if isinstance(value, (int, float)):
            return f"{value:,.2f}{unit}"
        return str(value)

    col1.metric(
        label="Émissions totales de CO₂ (MtCO₂)",
        value=_fmt(kpis.get("total_co2")),
    )
    col2.metric(
        label="Émissions par habitant (tCO₂/hab)",
        value=_fmt(kpis.get("co2_per_capita")),
    )
    col3.metric(
        label="Intensité carbone du PIB (kgCO₂/USD)",
        value=_fmt(kpis.get("carbon_intensity_gdp")),
    )
    col4.metric(
        label="Variation annuelle moyenne (%)",
        value=_fmt(kpis.get("annual_change_pct"), "%"),
    )


def render_home() -> None:
    """Render the **Accueil** page of the Carbon Footprint Analysis Dashboard.

    The page includes:
    - Global filters (year range, refresh button) in the sidebar.
    - KPI cards summarising the selected period.
    - A choropleth map for the most recent year in the range.
    - A line chart showing the evolution of global emissions.
    """
    st.set_page_config(
        page_title="Carbon Footprint – Accueil",
        page_icon="🌍",
        layout="wide",
    )

    # ----------------------------------------------------------------------
    # Sidebar – global filters
    # ----------------------------------------------------------------------
    st.sidebar.header("Filtres globaux")
    years = _load_year_options()
    if not years:
        st.stop()

    min_year, max_year = min(years), max(years)
    selected_range = st.sidebar.slider(
        "Période",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
        step=1,
        format="%d",
    )
    if st.sidebar.button("🔄 Rafraîchir le cache"):
        try:
            refresh_cache()
            st.sidebar.success("Cache rafraîchi avec succès.")
        except Exception as exc:  # pragma: no cover
            st.sidebar.error(f"Erreur lors du rafraîchissement du cache : {exc}")

    # ----------------------------------------------------------------------
    # Main content
    # ----------------------------------------------------------------------
    st.title("🌱 Tableau de bord – Vue d’ensemble")
    st.markdown(
        """
        Cette page présente les indicateurs clés (KPIs) globaux ainsi que les
        visualisations principales de l’empreinte carbone mondiale.
        Utilisez le panneau latéral pour ajuster la période d’analyse.
        """
    )

    # ----------------------------------------------------------------------
    # Load data & compute KPIs
    # ----------------------------------------------------------------------
    try:
        kpis = get_global_kpis(year_range=selected_range)
        emissions_ts = get_emissions_timeseries(year_range=selected_range)
        # For the choropleth we pick the most recent year of the interval
        latest_year = selected_range[1]
        country_df, geojson = get_country_emissions_geojson(year=latest_year)
    except Exception as exc:  # pragma: no cover
        st.error(f"Erreur lors du chargement des données : {exc}")
        st.stop()

    # ----------------------------------------------------------------------
    # Display KPIs
    # ----------------------------------------------------------------------
    _display_kpis(kpis)

    st.markdown("---")

    # ----------------------------------------------------------------------
    # Visualisations
    # ----------------------------------------------------------------------
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Émissions mondiales au fil du temps")
        _draw_global_emissions_chart(emissions_ts)

    with chart_col2:
        st.subheader(f"Répartition des émissions par pays en {latest_year}")
        _draw_choropleth_map(country_df, geojson)

    st.markdown(
        """
        <small>
        *Les données proviennent de **Our World in Data** (émissions CO₂) et de la **World Bank**
        (population, PIB). Les valeurs sont actualisées mensuellement.
        </small>
        """,
        unsafe_allow_html=True,
    )
