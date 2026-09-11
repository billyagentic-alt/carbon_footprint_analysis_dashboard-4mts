import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Optional, Sequence, Tuple, Union

__all__ = [
    "line_chart",
    "stacked_area_chart",
    "bar_chart",
    "donut_chart",
    "heatmap_chart",
    "total_co2_line",
    "per_capita_co2_line",
    "gdp_intensity_bar",
    "annual_emission_change_line",
    "energy_sector_share_donut",
]


def _validate_columns(df: pd.DataFrame, required: Sequence[str]) -> None:
    """Validate that *required* columns exist in *df*.

    Args:
        df: DataFrame to validate.
        required: Iterable of column names that must be present.

    Raises:
        ValueError: If any required column is missing.
    """
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in DataFrame: {missing}")


def _base_layout(title: str) -> dict:
    """Return a base layout dictionary with a professional style.

    Args:
        title: Title displayed on the chart.

    Returns:
        A dictionary suitable for ``fig.update_layout``.
    """
    return {
        "title": {"text": title, "x": 0.5, "xanchor": "center"},
        "paper_bgcolor": "#fafafa",
        "plot_bgcolor": "#ffffff",
        "font": {"family": "Arial, sans-serif", "size": 12, "color": "#333333"},
        "margin": {"l": 60, "r": 20, "t": 60, "b": 60},
        "hovermode": "x unified",
    }


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
    width: int = 800,
    height: int = 500,
) -> go.Figure:
    """Create a generic line chart.

    Args:
        df: Source data.
        x: Column name for the x‑axis (typically a year).
        y: Column name for the y‑axis (metric to plot).
        color: Optional column used to split lines (e.g., country).
        title: Chart title.
        width: Figure width in pixels.
        height: Figure height in pixels.

    Returns:
        A Plotly ``go.Figure`` instance.
    """
    _validate_columns(df, [x, y] + ([color] if color else []))

    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        markers=True,
        width=width,
        height=height,
    )
    fig.update_layout(_base_layout(title))
    fig.update_traces(hovertemplate="%{x}<br>%{y:.2f}<extra></extra>")
    return fig


def stacked_area_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    stackgroup: str,
    title: str = "",
    width: int = 800,
    height: int = 500,
) -> go.Figure:
    """Create a stacked area chart.

    Args:
        df: Source data.
        x: Column for the x‑axis.
        y: Column for the y‑axis (value to stack).
        stackgroup: Column that defines the stacking groups (e.g., sector).
        title: Chart title.
        width: Figure width.
        height: Figure height.

    Returns:
        A Plotly ``go.Figure`` with stacked areas.
    """
    _validate_columns(df, [x, y, stackgroup])

    fig = go.Figure()
    for sector, sub_df in df.groupby(stackgroup):
        fig.add_trace(
            go.Scatter(
                x=sub_df[x],
                y=sub_df[y],
                mode="lines",
                stackgroup="one",
                name=str(sector),
                hovertemplate=f"{stackgroup}: {sector}<br>%{{x}}: %{{y:.2f}}<extra></extra>",
            )
        )
    fig.update_layout(_base_layout(title), width=width, height=height)
    return fig


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
    width: int = 800,
    height: int = 500,
) -> go.Figure:
    """Create a bar chart.

    Args:
        df: Source data.
        x: Column for the x‑axis (categorical).
        y: Column for the y‑axis (numeric).
        color: Optional column to color bars.
        title: Chart title.
        width: Figure width.
        height: Figure height.

    Returns:
        A Plotly ``go.Figure`` with bars.
    """
    _validate_columns(df, [x, y] + ([color] if color else []))

    fig = px.bar(
        df,
        x=x,
        y=y,
        color=color,
        text=y,
        width=width,
        height=height,
    )
    fig.update_layout(_base_layout(title))
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_yaxes(automargin=True)
    return fig


def donut_chart(
    df: pd.DataFrame,
    names: str,
    values: str,
    title: str = "",
    width: int = 600,
    height: int = 600,
) -> go.Figure:
    """Create a donut (pie with hole) chart.

    Args:
        df: Source data.
        names: Column containing category names.
        values: Column containing numeric values.
        title: Chart title.
        width: Figure width.
        height: Figure height.

    Returns:
        A Plotly ``go.Figure`` representing a donut chart.
    """
    _validate_columns(df, [names, values])

    fig = go.Figure(
        data=[
            go.Pie(
                labels=df[names],
                values=df[values],
                hole=0.4,
                hoverinfo="label+percent+value",
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(_base_layout(title), width=width, height=height)
    return fig


def heatmap_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    z: str,
    title: str = "",
    colorscale: str = "Viridis",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    """Create a heatmap chart.

    Args:
        df: Source data.
        x: Column for the x‑axis.
        y: Column for the y‑axis.
        z: Column containing the value to colour.
        title: Chart title.
        colorscale: Plotly colorscale name.
        width: Figure width.
        height: Figure height.

    Returns:
        A Plotly ``go.Figure`` with a heatmap.
    """
    _validate_columns(df, [x, y, z])

    fig = go.Figure(
        data=go.Heatmap(
            x=df[x],
            y=df[y],
            z=df[z],
            colorscale=colorscale,
            hovertemplate=f"%{{x}} – %{{y}}: %{{z:.2f}}<extra></extra>",
        )
    )
    fig.update_layout(_base_layout(title), width=width, height=height)
    return fig


# --------------------------------------------------------------------------- #
# Specific chart factories for the KPI set
# --------------------------------------------------------------------------- #


def total_co2_line(
    df: pd.DataFrame,
    country_col: str = "country",
    year_col: str = "year",
    emission_col: str = "co2_mt",
    selected_countries: Optional[List[str]] = None,
    title: str = "Émissions totales de CO₂ (MtCO₂)",
) -> go.Figure:
    """Line chart of total CO₂ emissions for one or several countries.

    Args:
        df: DataFrame containing at least ``country_col``, ``year_col`` and ``emission_col``.
        country_col: Column name for country identifiers.
        year_col: Column name for the year.
        emission_col: Column name for total CO₂ emissions in megatonnes.
        selected_countries: List of countries to keep; if ``None`` all are shown.
        title: Chart title.

    Returns:
        Plotly ``go.Figure``.
    """
    _validate_columns(df, [country_col, year_col, emission_col])

    data = df.copy()
    if selected_countries:
        data = data[data[country_col].isin(selected_countries)]

    return line_chart(
        data,
        x=year_col,
        y=emission_col,
        color=country_col,
        title=title,
    )


def per_capita_co2_line(
    df: pd.DataFrame,
    country_col: str = "country",
    year_col: str = "year",
    per_capita_col: str = "co2_per_capita_t",
    selected_countries: Optional[List[str]] = None,
    title: str = "Émissions de CO₂ par habitant (tCO₂ / habitant)",
) -> go.Figure:
    """Line chart of CO₂ emissions per capita.

    Args:
        df: DataFrame with country, year and per‑capita emission columns.
        country_col: Column name for country.
        year_col: Column name for year.
        per_capita_col: Column name for emissions per capita (tonnes).
        selected_countries: Optional filter on countries.
        title: Chart title.

    Returns:
        Plotly ``go.Figure``.
    """
    _validate_columns(df, [country_col, year_col, per_capita_col])

    data = df.copy()
    if selected_countries:
        data = data[data[country_col].isin(selected_countries)]

    return line_chart(
        data,
        x=year_col,
        y=per_capita_col,
        color=country_col,
        title=title,
    )


def gdp_intensity_bar(
    df: pd.DataFrame,
    country_col: str = "country",
    year_col: str = "year",
    intensity_col: str = "co2_intensity_kg_per_usd",
    year: int = 2022,
    title: str = "Intensité carbone du PIB (kgCO₂ / USD)",
) -> go.Figure:
    """Bar chart comparing carbon intensity of GDP across countries for a given year.

    Args:
        df: DataFrame containing country, year and intensity columns.
        country_col: Column name for country.
        year_col: Column name for year.
        intensity_col: Column name for carbon intensity (kg CO₂ per USD of GDP).
        year: Year to filter on.
        title: Chart title.

    Returns:
        Plotly ``go.Figure``.
    """
    _validate_columns(df, [country_col, year_col, intensity_col])

    filtered = df[df[year_col] == year].dropna(subset=[intensity_col])
    if filtered.empty:
        raise ValueError(f"No data available for year {year} to compute GDP intensity.")

    # Sort for a nicer visual ordering
    filtered = filtered.sort_values(intensity_col, ascending=False)

    return bar_chart(
        filtered,
        x=country_col,
        y=intensity_col,
        title=title,
    )


def annual_emission_change_line(
    df: pd.DataFrame,
    country_col: str = "country",
    year_col: str = "year",
    emission_col: str = "co2_mt",
    selected_countries: Optional[List[str]] = None,
    title: str = "Variation annuelle moyenne des émissions (%)",
) -> go.Figure:
    """Line chart of year‑over‑year percentage change of CO₂ emissions.

    The function computes the percentage change per country and then
    aggregates (mean) across the selected countries.
