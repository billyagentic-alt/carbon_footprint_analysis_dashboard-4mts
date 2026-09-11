import streamlit as st
from pathlib import Path
from typing import Callable, Dict

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
    Dynamically import page modules.

    Returns
    -------
    dict[str, Callable[[], None]]
        Mapping between page titles and callables that render the page.
    """
    try:
        from pages import home, country_analysis, comparison, settings
    except ImportError as exc:
        st.error(f"❌ Impossible de charger les modules de page : {exc}")
        raise

    return {
        "Accueil": home.render,
        "Analyse par pays": country_analysis.render,
        "Comparaison multi‑pays": comparison.render,
        "Paramètres": settings.render,
    }


def _clear_cache() -> None:
    """
    Clear Streamlit's data cache.

    This function is bound to a button in the sidebar to allow users
    to force a refresh of the underlying datasets.
    """
    st.experimental_memo.clear()
    st.experimental_singleton.clear()
    st.success("✅ Cache vidé ! Les données seront rechargées au prochain rafraîchissement.")


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
if st.sidebar.button("🔄 Rafraîchir le cache", help="Vider le cache et recharger les données"):
    _clear_cache()

st.sidebar.markdown(
    """
    ---
    **Version**: 1.0.0  
    **Auteur**: Équipe Data‑Science  
    **Licence**: MIT  
    """
)

# ----------------------------------------------------------------------
# Main content – render selected page
# ----------------------------------------------------------------------
def _render_page(page_callable: Callable[[], None]) -> None:
    """
    Execute the rendering function of the selected page.

    Parameters
    ----------
    page_callable : Callable[[], None]
        Function that builds the Streamlit UI for the page.
    """
    try:
        page_callable()
    except Exception as exc:  # pragma: no cover
        # In production we log the error; here we simply display it.
        st.error(f"❗ Une erreur est survenue lors du rendu de la page : {exc}")
        raise


if __name__ == "__main__":
    # The entry‑point guard allows the module to be imported without side‑effects.
    _render_page(page_modules[selected_page])
