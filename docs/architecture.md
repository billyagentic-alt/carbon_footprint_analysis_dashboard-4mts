# Architecture du Dashboard : Carbon Footprint Analysis

## 1. Vue d’ensemble
Le tableau de bord **Carbon Footprint Analysis** est organisé selon une architecture en couches clairement séparées :

```
┌─────────────────────┐
│   Interface Streamlit│   ← Pages & Visualisations
└─────────▲───────────┘
          │
┌─────────┴───────────┐
│   Couche Visualisation│   ← Plotly, Altair, st.plotly_chart
└─────────▲───────────┘
          │
┌─────────┴───────────┐
│   Couche Data Layer   │   ← data_layer.py (download, transformation, KPI)
└─────────▲───────────┘
          │
┌─────────┴───────────┐
│   Sources de données │   ← OWID CSV, World Bank API, UNFCCC API (optionnel)
└─────────────────────┘
```

Chaque couche possède une responsabilité unique :  
* **Sources** : récupération brute des jeux de données.  
* **Data Layer** : nettoyage, normalisation, jointures, calcul des KPI, mise en cache.  
* **Visualisation** : transformation des DataFrames en objets Plotly prêts à être affichés.  
* **Pages Streamlit** : orchestration de l’interface utilisateur, gestion des filtres et de la navigation.

---

## 2. Stack technique

| Niveau | Technologie | Raison du choix |
|--------|--------------|-----------------|
| **Langage** | Python ≥ 3.10 | Typage statique (`typing`), f‑strings, performance suffisante. |
| **Web UI** | Streamlit ≥ 1.30 | Déploiement rapide, support multi‑pages, cache intégré. |
| **Visualisation** | Plotly Express & Graph Objects | Graphiques interactifs, export PNG/SVG, callbacks. |
| **Data ingestion** | `pandas`, `requests`, `httpx` (async) | Manipulation tabulaire, gestion d’erreurs HTTP. |
| **Cache** | `st.cache_data` (ou `st.experimental_memo`) | Mémoire partagée, invalidation via clé de version. |
| **Tests** | pytest, pytest‑cov | Couverture unitaires et intégration. |
| **CI/CD** | GitHub Actions | Linting (ruff), tests, build headless. |
| **Déploiement** | Streamlit Community Cloud / Docker | Isolation, scalabilité, configuration via `Dockerfile`. |
| **Documentation** | Markdown, docstrings (Google style) | Lisibilité, génération possible avec Sphinx. |

---

## 3. Couche Data Layer (`data_layer.py`)

### 3.1 Responsabilités
1. **Téléchargement** des sources :
   - OWID : `pd.read_csv(url, ...)` avec `requests` fallback.
   - World Bank : appel API via `httpx` (gestion du token et pagination).
   - UNFCCC : optionnel, appel REST avec authentification si nécessaire.
2. **Nettoyage & Normalisation** :
   - Uniformisation des noms de pays (ISO‑3, ISO‑2, alias).
   - Conversion des années en `int`, des valeurs en `float`.
   - Gestion des valeurs manquantes (`NaN` → `0` ou interpolation selon KPI).
3. **Jointures** :
   - `CO2` ↔ `Population` ↔ `GDP` ↔ `Energy consumption`.
   - Table fact principale : `country_code | year | sector | co2_mt | population | gdp_usd | energy_twh`.
4. **Calcul des KPI** :
   - `total_co2`, `co2_per_capita`, `carbon_intensity_gdp`, `annual_avg_change`, `energy_sector_share`.
   - Chaque KPI exposé via une fonction `get_kpis(filters: KPIFilters) -> dict`.
5. **Caching** :
   - Décorateur `@st.cache_data` sur les fonctions de téléchargement et de transformation.
   - Clé de version (`DATA_VERSION`) pour forcer le rafraîchissement.

### 3.2 API publique du module
```python
class KPIFilters(TypedDict, total=False):
    countries: Sequence[str]
    years: Sequence[int]
    sectors: Sequence[str]

def load_raw_data() -> dict[str, pd.DataFrame]:
    """Télécharge et retourne les DataFrames brutes (co2, population, gdp, energy)."""

def get_clean_data() -> pd.DataFrame:
    """Renvoie la table fact normalisée, prête à être filtrée."""

def get_kpis(filters: KPIFilters) -> dict[str, pd.Series]:
    """Calcule les KPI demandés selon les filtres et retourne un dict de séries."""
```

---

## 4. Couche Visualisation

| Visualisation | Fonction | Entrées | Sortie |
|---------------|----------|---------|--------|
| **Line chart** | `plot_total_co2_line(df, countries, years)` | DataFrame filtrée | `go.Figure` |
| **Stacked area** | `plot_sectoral_area(df, country, years)` | DataFrame filtrée | `go.Figure` |
| **Bar chart** | `plot_intensity_bar(df, countries, year)` | DataFrame filtrée | `go.Figure` |
| **Donut chart** | `plot_sector_donut(df, country, year)` | DataFrame filtrée | `go.Figure` |
| **Choropleth** | `plot_world_map(df, year)` | DataFrame agrégée | `go.Figure` |

- Chaque fonction accepte uniquement des DataFrames déjà filtrées (responsabilité du caller).  
- Les graphiques sont configurés avec un thème sombre clair, légendes interactives, et `hovertemplate` détaillé.  
- Les callbacks Plotly (zoom, sélection) sont exposés via `st.plotly_chart(..., use_container_width=True)`.

---

## 5. Pages Streamlit

| Page | Description | Principaux widgets |
|------|-------------|--------------------|
| **Accueil** | Vue d’ensemble globale, KPI agrégés, carte choroplèthe, texte de synthèse. | `st.metric`, `st.selectbox` (année globale), `st.button` (refresh cache). |
| **Analyse par pays** | Sélection multi‑pays, période, secteur → graphiques détaillés. | `st.multiselect` (pays), `st.slider` (année), `st.checkbox` (secteurs). |
| **Comparaison multi‑pays** | Tableau éditable, bar chart comparatif, export CSV. | `st.data_editor`, `st.download_button`. |
| **Paramètres** | Gestion du cache, affichage de la version des données, documentation. | `st.button` (clear cache), `st.expander` (README). |

### Sidebar commun
- **Filtres globaux** : pays, période, secteur (appliqués par défaut à toutes les pages).  
- **Bouton “Refresh data”** : `st.experimental_rerun()` après `st.cache_data.clear()`.  
- **Info version** : `st.caption(f"Data version: {DATA_VERSION}")`.

---

## 6. Flux de données

1. **Démarrage** : Streamlit charge `main.py`, exécute `st.set_page_config`.  
2. **Cache** : `data_layer.load_raw_data()` est appelé une fois, les DataFrames sont mis en cache.  
3. **Filtrage** : Les sélections du sidebar sont transmises aux fonctions `get_clean_data()` → `df_filtered`.  
4. **KPI** : `get_kpis(filters)` calcule les métriques affichées via `st.metric`.  
5. **Visualisation** : Les fonctions du module `visuals.py` reçoivent `df_filtered` et retournent des `go.Figure`.  
6. **Rendu** : `st.plotly_chart` injecte les figures dans la page.  
7. **Interaction** : Les callbacks Plotly (zoom, hover) sont gérés côté client; aucune requête serveur supplémentaire n’est nécessaire.  

---

## 7. Gestion des erreurs

| Niveau | Technique |
|--------|-----------|
| **Téléchargement** | `try/except` autour de `requests.get` ; retries avec `httpx.Retry`. Retour d’un DataFrame vide + log `st.error`. |
| **Transformation** | Validation des colonnes (`assert set(required) <= set(df.columns)`). Utilisation de `pandas.api.types.is_numeric_dtype`. |
| **KPI** | Protection contre division par zéro (`np.where(population > 0, ...)`). |
| **UI** | `st.warning` si aucun pays sélectionné, `st.info` pour messages de chargement. |
| **Logging** | Module `logging` configuré en `INFO` (console) + `ERROR` (fichier `logs/app.log`). |

---

## 8. Stratégie de cache & rafraîchissement

- **Clé de version** : `DATA_VERSION = "2024-09"` (mise à jour manuelle ou via checksum du CSV).  
- **Invalidation** : Bouton “Refresh data” appelle `st.cache_data.clear()` puis `st.experimental_rerun()`.  
- **TTL** : Optionnel `ttl=86400` (24 h) pour les appels API World Bank afin de limiter le trafic.  

---

## 9. Déploiement

### Dockerfile (exemple)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.headless=true"]
```

- **Variables d’environnement** : `DATA_VERSION`, `WORLD_BANK_API_KEY` (si nécessaire).  
- **Healthcheck** : `curl -f http://localhost:8501/_stcore/health`  

### Streamlit Community Cloud
- Branch `main` déclenchée automatiquement.  
- Paramètre `secrets.toml` pour stocker les clés API en toute sécurité.  

---

## 10. CI / CD (GitHub Actions)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Lint with ruff
        run: ruff check .
      - name: Run tests
        run: pytest --cov=data_layer tests/
      - name: Build (headless)
        run: streamlit run main.py --server.headless true &
```

- **Artifacts** : couverture (`coverage.xml`) et logs (`app.log`).  

---

## 11. Extensibilité & Maintenance

| Axe | Possibilité d’évolution |
|-----|--------------------------|
| **Nouvelles sources** | Ajouter un connecteur `UNFCCC` dans `data_layer.download_unfccc()`. |
| **Nouveaux KPI** | Créer une fonction `compute_custom_kpi(df, **kwargs)` et l’exposer via `get_kpis`. |
| **Thèmes UI** | Utiliser `st.theme` ou injecter du CSS via `st.markdown(..., unsafe_allow_html=True)`. |
| **Export** | Ajouter `st.download_button` pour CSV/Excel des DataFrames filtrés. |
| **Internationalisation** | Wrapper les textes avec `gettext` ou `streamlit-i18n`. |

---

## 12. Sécurité

- **Secrets** : stockés dans `secrets.toml` (Streamlit) ou variables d’environnement Docker.  
- **CORS** : non applicable (Streamlit s’exécute en mode serveur).  
- **Rate limiting** : `httpx` avec `limits` pour les appels API World Bank.  
- **Audit** : logs d’accès (`st.experimental_get_query_params`) pour traçabilité.  

---

## 13. Documentation

- **README.md** : description du projet, instructions d’installation, usage, contribution.  
- **docs/architecture.md** : (ce fichier).  
- **docstrings** : format Google, générés avec `pydocstyle`.  
- **Sphinx** (optionnel) : `make html` pour un site de documentation complet.  

---  

*Fin de l’architecture.*
