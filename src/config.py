from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Literal

from pydantic import BaseSettings, Field, validator, root_validator


class DashboardConfig(BaseSettings):
    """
    Configuration settings for the Carbon Footprint Analysis Dashboard.

    The class inherits from :class:`pydantic.BaseSettings`, allowing values to be
    populated from environment variables, a ``.env`` file or the defaults
    defined below. All paths are resolved to absolute :class:`pathlib.Path`
    objects for safety.

    Environment variables (case‑insensitive) that can override defaults:

    - ``CARBON_DATA_DIR`` – Directory where raw and processed data files are stored.
    - ``CARBON_CACHE_DIR`` – Directory used by Streamlit's cache mechanisms.
    - ``CARBON_OWID_CO2_URL`` – URL of the OWID CO₂ emissions CSV.
    - ``CARBON_WORLD_BANK_API_URL`` – Base URL of the World Bank API.
    - ``CARBON_TITLE`` – Title displayed in the Streamlit sidebar/header.
    - ``CARBON_LOGO_URL`` – Optional URL to a logo image.
    - ``CARBON_THEME`` – Name of the colour theme (``light`` or ``dark``).
    - ``CARBON_REFRESH_INTERVAL`` – Minimum seconds between automatic data refreshes.
    """

    # --------------------------------------------------------------------- #
    # Paths
    # --------------------------------------------------------------------- #
    data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("CARBON_DATA_DIR", "data")).expanduser().resolve(),
        description="Root directory for all data files (raw and processed).",
    )
    cache_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("CARBON_CACHE_DIR", ".cache")).expanduser().resolve(),
        description="Directory used for Streamlit's caching of DataFrames and assets.",
    )

    # --------------------------------------------------------------------- #
    # External data sources
    # --------------------------------------------------------------------- #
    owid_co2_url: str = Field(
        default="https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv",
        description="Direct URL to the OWID CO₂ emissions CSV file.",
    )
    world_bank_api_url: str = Field(
        default="https://api.worldbank.org/v2",
        description="Base URL for the World Bank REST API.",
    )

    # --------------------------------------------------------------------- #
    # UI / branding
    # --------------------------------------------------------------------- #
    title: str = Field(default="Carbon Footprint Analysis Dashboard", description="Dashboard title shown in the UI.")
    logo_url: str | None = Field(
        default=None,
        description="Optional URL to a logo image displayed in the sidebar/header.",
    )
    theme: Literal["light", "dark"] = Field(
        default="light",
        description="Colour theme used throughout the dashboard.",
    )

    # --------------------------------------------------------------------- #
    # Visualisation palette
    # --------------------------------------------------------------------- #
    colors: Dict[str, str] = Field(
        default_factory=lambda: {
            "background": "#FFFFFF",
            "text": "#212529",
            "primary": "#0d6efd",
            "secondary": "#6c757d",
            "success": "#198754",
            "danger": "#dc3545",
            "warning": "#ffc107",
            "info": "#0dcaf0",
            "light": "#f8f9fa",
            "dark": "#212529",
        },
        description="Mapping of semantic colour names to HEX values used by Plotly charts.",
    )

    # --------------------------------------------------------------------- #
    # Runtime behaviour
    # --------------------------------------------------------------------- #
    refresh_interval: int = Field(
        default=86400,
        ge=0,
        description="Minimum number of seconds between automatic data refreshes (default: 24 h).",
    )

    class Config:
        """Pydantic configuration."""

        case_sensitive = False
        env_prefix = "CARBON_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    # --------------------------------------------------------------------- #
    # Validators
    # --------------------------------------------------------------------- #
    @validator("data_dir", "cache_dir", pre=True)
    def _ensure_path(cls, v: str | Path) -> Path:
        """Convert incoming strings to absolute :class:`Path` objects."""
        path = Path(v).expanduser().resolve()
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except PermissionError as exc:
                raise PermissionError(f"Unable to create directory '{path}': {exc}") from exc
        return path

    @validator("theme")
    def _validate_theme(cls, v: str) -> str:
        """Ensure the theme is one of the supported values."""
        if v not in {"light", "dark"}:
            raise ValueError("theme must be either 'light' or 'dark'")
        return v

    @root_validator
    def _adjust_palette_for_theme(cls, values: dict) -> dict:
        """
        Adjust the colour palette according to the selected theme.

        For a dark theme we invert background / text colours while keeping the
        semantic colours unchanged.
        """
        theme = values.get("theme", "light")
        colors = values.get("colors", {})

        if theme == "dark":
            colors.setdefault("background", "#212529")
            colors.setdefault("text", "#f8f9fa")
        else:
            colors.setdefault("background", "#FFFFFF")
            colors.setdefault("text", "#212529")

        values["colors"] = colors
        return values

    # --------------------------------------------------------------------- #
    # Helper properties
    # --------------------------------------------------------------------- #
    @property
    def raw_data_path(self) -> Path:
        """Path to the directory containing raw source files."""
        return self.data_dir / "raw"

    @property
    def processed_data_path(self) -> Path:
        """Path to the directory where transformed CSV/Parquet files are stored."""
        return self.data_dir / "processed"

    @property
    def logo(self) -> str | None:
        """Return the logo URL if defined, otherwise ``None``."""
        return self.logo_url


# Instantiate a singleton configuration object that can be imported throughout the project.
config: DashboardConfig = DashboardConfig()
