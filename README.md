# carbon_footprint_analysis_dashboard-4mts

Dashboard Streamlit interactif pour analyser l'empreinte carbone des pays et les émissions par secteur (OWID / World Bank) avec filtres temporels et sectoriels, KPIs calculés, visualisations Plotly et architecture data layer séparée.

## Fonctionnalités

- Dashboard interactif Streamlit multi-pages :
- Accueil – vue d’ensemble avec KPIs globaux et carte choroplèthe
- Analyse par pays – filtres pays, période, secteur + visualisations détaillées
- Comparaison multi‑pays – tableau comparatif et graphiques de comparaison
- Paramètres – gestion du cache, rafraîchissement des données, documentation
- KPIs : Émissions totales de CO₂ (MtCO₂) – sélectionnées, Émissions par habitant (tCO₂ / habitant), Intensité carbone du PIB (kgCO₂ / USD), Variation annuelle moyenne des émissions (%), Part du secteur énergie dans les émissions totales (%)
- Visualisations Plotly professionnelles (zoom, hover, responsive)
- Cache des données (Streamlit `@st.cache_data`)
- Tests unitaires et CI GitHub Actions

## Installation

```bash
pip install -r requirements.txt
```

## Lancer l'application

```bash
streamlit run app.py
```

## Structure

```
app.py
src/
  data/       # fetch + processing
  visuals/    # charts Plotly
  pages/      # pages Streamlit
  utils/      # helpers
tests/        # tests unitaires
docs/         # documentation
```

## Données

- Our World in Data – CO₂ emissions by country and sector (CSV via GitHub)
- World Bank – Population, GDP, Energy consumption (API)
- UNFCCC – National greenhouse gas inventories (optional supplemental API)
