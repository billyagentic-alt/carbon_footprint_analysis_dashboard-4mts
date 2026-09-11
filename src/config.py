from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Literal, TypedDict

from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Environment handling
# --------------------------------------------------------------------------- #
def load_env() -> None:
    """Load environment variables from a ``.env`` file.

    This function uses :pypi:`python-dotenv` to read a ``.env`` file located
    at the project root (if present) and populates ``os.environ``.  It is
    idempotent and safe to call multiple times.
    """
    env_path = Path(".env")
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path, encoding="utf-8")


# Load environment variables as soon as the module is imported.
load_env()


# --------------------------------------------------------------------------- #
# Global constants
# --------------------------------------------------------------------------- #
APP_VERSION: str = "1.0.0"
"""Application semantic version (``MAJOR.MINOR.PATCH``)."""

DATA_VERSION: str = os.getenv("DATA_VERSION", "2024-01")
"""Version identifier for the underlying dataset; defaults to ``2024-01``."""

CACHE_TTL: int = 86_400
"""Time‑to‑live for cached objects, expressed in seconds (default: 24 h)."""

OWID_CO2_URL: str = os.getenv(
    "CARBON_OWID_CO2_URL",
    "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv",
)
"""Direct URL to the OWID CO₂ emissions CSV file."""

WORLD_BANK_API_BASE: str = os.getenv(
    "CARBON_WORLD_BANK_API_URL", "https://api.worldbank.org/v2"
)
"""Base URL for the World Bank REST API."""


# --------------------------------------------------------------------------- #
# Typed structures for connection parameters
# --------------------------------------------------------------------------- #
class ApiConnectionParams(TypedDict, total=False):
    """TypedDict describing generic API connection parameters.

    Attributes:
        base_url: Base endpoint of the API.
        timeout: Request timeout in seconds.
        headers: Optional HTTP headers to include with each request.
    """

    base_url: str
    timeout: int
    headers: Dict[str, str]


# --------------------------------------------------------------------------- #
# Dashboard configuration dataclass
# --------------------------------------------------------------------------- #
@dataclass
class DashboardConfig:
    """Configuration settings for the Carbon Footprint Analysis Dashboard.

    Values are primarily sourced from environment variables (prefixed with
    ``CARBON_``) with sensible fall‑backs.  Paths are resolved to absolute
    :class:`pathlib.Path` objects and created on‑demand.

    Attributes:
        data_dir: Root directory for all data files (raw and processed).
        cache_dir: Directory used for Streamlit's caching of DataFrames and assets.
        owid_co2_url: URL of the OWID CO₂ emissions CSV.
        world_bank_api_url: Base URL of the World Bank API.
        title: Dashboard title shown in the UI.
        logo_url: Optional URL to a logo image displayed in the sidebar/header.
        theme: Colour theme used throughout the dashboard (``light`` or ``dark``).
        colors: Mapping of semantic colour names to HEX values used by Plotly charts.
        refresh_interval: Minimum number of seconds between automatic data refreshes.
    """

    # --------------------------------------------------------------------- #
    # Paths
    # --------------------------------------------------------------------- #
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("CARBON_DATA_DIR", "data")
        ).expanduser().resolve()
    )
    """Root directory for all data files (raw and processed)."""

    cache_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("CARBON_CACHE_DIR", ".cache")
        ).expanduser().resolve()
    )
    """Directory used for Streamlit's caching of DataFrames and assets."""

    # --------------------------------------------------------------------- #
    # External data sources
    # --------------------------------------------------------------------- #
    owid_co2_url: str = field(default=OWID_CO2_URL)
    """Direct URL to the OWID CO₂ emissions CSV file."""

    world_bank_api_url: str = field(default=WORLD_BANK_API_BASE)
    """Base URL for the World Bank REST API."""

    # --------------------------------------------------------------------- #
    # UI / branding
    # --------------------------------------------------------------------- #
    title: str = field(
        default=os.getenv(
            "CARBON_TITLE", "Carbon Footprint Analysis Dashboard"
        )
    )
    """Dashboard title shown in the UI."""

    logo_url: str | None = field(
        default=os.getenv("CARBON_LOGO_URL")
    )
    """Optional URL to a logo image displayed in the sidebar/header."""

    theme: Literal["light", "dark"] = field(
        default=os.getenv("CARBON_THEME", "light")
    )
    """Colour theme used throughout the dashboard."""

    # --------------------------------------------------------------------- #
    # Visualisation palette
    # --------------------------------------------------------------------- #
    colors: Dict[str, str] = field(
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
        }
    )
    """Mapping of semantic colour names to HEX values used by Plotly charts."""

    # --------------------------------------------------------------------- #
    # Runtime behaviour
    # --------------------------------------------------------------------- #
    refresh_interval: int = field(
        default=int(os.getenv("CARBON_REFRESH_INTERVAL", "86400"))
    )
    """Minimum number of seconds between automatic data refreshes."""

    def __post_init__(self) -> None:
        """Validate and normalise configuration after dataclass initialisation."""
        self._ensure_path(self.data_dir, "data_dir")
        self._ensure_path(self.cache_dir, "cache_dir")
        self._validate_theme()
        self._adjust_palette_for_theme()

    # --------------------------------------------------------------------- #
    # Private helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _ensure_path(path: Path, name: str) -> None:
        """Create ``path`` if it does not exist and raise a clear error on failure."""
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except PermissionError as exc:
                raise PermissionError(
                    f"Unable to create directory for {name} ('{path}'): {exc}"
                ) from exc

    def _validate_theme(self) -> None:
        """Ensure ``theme`` is either ``light`` or ``dark``."""
        if self.theme not in {"light", "dark"}:
            raise ValueError("theme must be either 'light' or 'dark'")

    def _adjust_palette_for_theme(self) -> None:
        """Adjust background / text colours according to the selected theme."""
        if self.theme == "dark":
            self.colors.setdefault("background", "#212529")
            self.colors.setdefault("text", "#f8f9fa")
        else:
            self.colors.setdefault("background", "#FFFFFF")
            self.colors.setdefault("text", "#212529")

    # --------------------------------------------------------------------- #
    # Convenience properties
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


# --------------------------------------------------------------------------- #
# Singleton instance for easy import throughout the project
# --------------------------------------------------------------------------- #
config: DashboardConfig = DashboardConfig()