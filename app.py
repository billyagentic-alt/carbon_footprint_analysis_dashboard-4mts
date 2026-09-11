import streamlit as st
from pathlib import Path
from typing import Callable, Dict
import importlib
import logging

from src.config import APP_VERSION

# ----------------------------------------------------------------------
# Logging configuration
# ----------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Page configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Analyse de l'empreinte carbone",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
def _load_page_modules() -> Dict[str, Callable[[], None]]:
    """
    Dynamically import page modules using ``importlib``.

    Returns
    -------
    Dict[str, Callable[[], None]]
        Mapping between page titles and the callable that renders the page.
    """
    page_definitions: Dict[str, str] = {
        "Accueil": "pages.home",
        "Analyse par pays": "pages.country_analysis",
        "Comparaison multi‑pays": "pages.comparison",
        "Paramètres": "pages.settings",
    }

    loaded_pages: Dict[str, Callable[[], None]] = {}

    for title, module_path in page_definitions.items():
        try:
            module = importlib.import_module(module_path)
            render_func = getattr(module, "render")
            if not callable(render_func):
                raise AttributeError(
                    f"Le module '{module_path}' n'expose pas de fonction callable 'render'."
                )
            loaded_pages[title] = render_func
        except Exception as exc:  # pragma: no cover
            logger.exception("Impossible de charger le module de page %s", module_path)
            st.sidebar.error(
                f"⚠️ Impossible de charger la page « {title} » : {exc}"
            )
    return loaded_pages


def clear_all_cache() -> None:
    """
    Clear Streamlit's data and resource caches.
    """
    st.cache_data.clear()
    st.cache_resource.clear()
    st.success(
        "✅ Cache vidé ! Les données seront rechargées au prochain rafraîchissement."
    )


# ----------------------------------------------------------------------
# Sidebar – navigation & global controls
# ----------------------------------------------------------------------
st.sidebar.title("🧭 Navigation")
page_modules = _load_page_modules()
selected_page = st.sidebar.radio(
    label="Sélectionnez une page",
    options=list(page_modules.keys()),
    index=0,
    key="navigation_radio",
)

st.sidebar.divider()
st.sidebar.subheader("⚙️ Actions globales")
if st.sidebar.button(
    "🔄 Rafraîchir le cache",
    help="Vider le cache et recharger les données",
):
    clear_all_cache()

st.sidebar.markdown(
    f"""
    ---
    **Version**: {APP_VERSION}  
    **Auteur**: Équipe Data‑Science  
    **Licence**: MIT  
    """
)

# ----------------------------------------------------------------------
# Main content – render selected page
# ----------------------------------------------------------------------
def _render_page(page_callable: Callable[[], None]) -> None:
    """
    Execute the rendering function of the selected page inside a spinner.

    Parameters
    ----------
    page_callable : Callable[[], None]
        Function that builds the Streamlit UI for the page.
    """
    try:
        with st.spinner("Chargement…"):
            page_callable()
    except Exception as exc:  # pragma: no cover
        logger.exception("Erreur lors du rendu de la page")
        st.error(f"❗ Une erreur est survenue lors du rendu de la page : {exc}")


if __name__ == "__main__":
    # Guard to avoid side‑effects on import.
    _render_page(page_modules[selected_page])