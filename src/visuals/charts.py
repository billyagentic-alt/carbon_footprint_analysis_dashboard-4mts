import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from typing import List, Optional, Sequence

# Apply a global Plotly theme
pio.templates.default = "plotly_dark"

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


def _validate_dataframe(df: pd.DataFrame) -> None:
    """Validate that the DataFrame is not empty.

    Args:
        df: DataFrame to validate.

    Raises:
        ValueError: If the DataFrame is empty.
    """
    if df.empty:
        raise ValueError("The provided DataFrame is empty.")


def apply_common_layout(fig: go.Figure, title: str = "", responsive: bool = True) -> go.Figure:
    """Apply a common layout to a Plotly figure.

    This function adds a centered title, a unified hover mode, a light
    background, and a horizontal legend. It also respects the *responsive*
    flag by toggling ``autosize``.

    Args:
        fig: The Plotly ``go.Figure`` to modify.
        title: Title displayed on the chart.
        responsive: If ``True`` the figure will autosize.

    Returns:
        The modified ``go.Figure`` instance.
    """
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        legend=dict(
            orientation="h",
            y=-0.2,
            x=0.5,
            xanchor="center",
        ),
        hovermode="x unified",
        paper_bgcolor="#fafafa",
        plot_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=12, color="#333333"),
        margin=dict(l=60, r=20, t=60, b=60),
        autosize=responsive,
    )
    # ``use_container_width`` is a Streamlit argument; we expose it as a
    # custom attribute so callers can retrieve it if needed.
    fig.layout["use_container_width"] = True
    return fig


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
    width: int = 800,
    height: int = 500,
    responsive: bool = True,
) -> go.Figure:
    """Create a generic line chart.

    Args:
        df: Source data (already filtered if needed).
        x: Column name for the x‑axis (typically a year).
        y: Column name for the y‑axis (metric to plot).
        color: Optional column used to split lines (e.g., country).
        title: Chart title.
        width: Figure width in pixels.
        height: Figure height in pixels.
        responsive: If ``True`` the figure will autosize.

    Returns:
        A Plotly ``go.Figure`` instance.

    Raises:
        ValueError: If the DataFrame is empty or required columns are missing.
    """
    _validate_dataframe(df)
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
    fig = apply_common_layout(fig, title=title, responsive=responsive)
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
    responsive: bool = True,
) -> go.Figure:
    """Create a stacked area chart.

    Args:
        df: Source data (already filtered if needed).
        x: Column for the x‑axis.
        y: Column for the y‑axis (value to stack).
        stackgroup: Column that defines the stacking groups (e.g., sector).
        title: Chart title.
        width: Figure width.
        height: Figure height.
        responsive: If ``True`` the figure will autosize.

    Returns:
        A Plotly ``go.Figure`` with stacked areas.

    Raises:
        ValueError: If the DataFrame is empty or required columns are missing.
    """
    _validate_dataframe(df)
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
    fig = apply_common_layout(fig, title=title, responsive=responsive)
    fig.update_layout(width=width, height=height)
    return fig


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
    width: int = 800,
    height: int = 500,
    responsive: bool = True,
) -> go.Figure:
    """Create a bar chart.

    Args:
        df: Source data (already filtered if needed).
        x: Column for the x‑axis (categorical).
        y: Column for the y‑axis (numeric).
        color: Optional column to color bars.
        title: Chart title.
        width: Figure width.
        height: Figure height.
        responsive: If ``True`` the figure will autosize.

    Returns:
        A Plotly ``go.Figure`` with bars.

    Raises:
        ValueError: If the DataFrame is empty or required columns are missing.
    """
    _validate_dataframe(df)
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
    fig = apply_common_layout(fig, title=title, responsive=responsive)
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
    responsive: bool = True,
) -> go.Figure:
    """Create a donut (pie with hole) chart.

    Args:
        df: Source data (already filtered if needed).
        names: Column containing category names.
        values: Column containing numeric values.
        title: Chart title.
        width: Figure width.
        height: Figure height.
        responsive: If ``True`` the figure will autosize.

    Returns:
        A Plotly ``go.Figure`` representing a donut chart.

    Raises:
        ValueError: If the DataFrame is empty or required columns are missing.
    """
    _validate_dataframe(df)
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
    fig = apply_common_layout(fig, title=title, responsive=responsive)
    fig.update_layout(width=width, height=height)
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
    responsive: bool = True,
) -> go.Figure:
    """Create a heatmap chart.

    Args:
        df: Source data (already filtered if needed).
        x: Column for the x‑axis.
        y: Column for the y‑axis.
        z: Column containing the value to colour.
        title: Chart title.
        colorscale: Plotly colorscale name.
        width: Figure width.
        height: Figure height.
        responsive: If ``True`` the figure will autosize.

    Returns:
        A Plotly ``go.Figure`` with a heatmap.

    Raises:
        ValueError: If the DataFrame is empty or required columns are missing.
    """
    _validate_dataframe(df)
    _validate_columns(df, [x, y, z])

    fig = go.Figure(
        data=go.Heatmap(
            x=df[x],
            y=df[y],
            z=df[z],
            colorscale=colorscale,
            hovertemplate="%{x} – %{y}: %{z:.2f}<extra></extra>",
        )
    )
    fig = apply_common_layout(fig, title=title, responsive=responsive)
    fig.update_layout(width=width, height=height)
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
    responsive: bool = True,
) -> go.Figure:
    """Line chart of total CO₂ emissions for one or several countries.

    Args:
        df: DataFrame containing at least ``country_col``, ``year_col`` and
            ``emission_col``.
        country_col: Column name for country identifiers.
        year_col: Column name for the year.
        emission_col: Column name for total CO₂ emissions in megatonnes.
        selected_countries: List of countries to keep; if ``None`` all are shown.
        title: Chart title.
        responsive: If ``True`` the figure will autosize.

    Returns:
        Plotly ``go.Figure``.

    Raises:
        ValueError: If the DataFrame is empty or required columns are missing.
    """
    _validate_dataframe(df)
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
        responsive=responsive,
    )


def per_capita_co2_line(
    df: pd.DataFrame,
    country_col: str = "country",
    year_col: str = "year",
    per_capita_col: str = "co2_per_capita_t",
    selected_countries: Optional[List