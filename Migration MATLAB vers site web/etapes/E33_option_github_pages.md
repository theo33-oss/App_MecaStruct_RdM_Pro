# E33 — (Option) Version sans serveur sur GitHub Pages avec stlite

**Modèle** : Sonnet · **Durée** : 90 min · **Prérequis** : E32.

## Pourquoi
Streamlit Community Cloud s'endort après 12 h sans visite. **stlite** exécute la même application
Streamlit **dans le navigateur** (Python compilé en WebAssembly par Pyodide) : on peut alors l'héberger
comme un simple site statique sur GitHub Pages, sans serveur et sans mise en veille.
Contreparties : premier chargement plus long (10 à 30 s, téléchargement de Python et des bibliothèques),
calculs un peu plus lents ; SymPy est lourd (le chemin numérique suffit).

## À faire
1. Lire la documentation de stlite (https://github.com/whitphx/stlite) : version « browser » avec un
   fichier `index.html` qui charge `@stlite/browser` depuis jsdelivr et monte l'application.
2. Créer `web/static/index.html` qui monte `streamlit_app.py`, les dossiers `mecastruct/`, `app_pages/`,
   `data/` et la liste des paquets (`numpy`, `scipy`, `pandas`, `plotly`, `openpyxl`, `jinja2`, `shapely`).
3. Script `web/tools/build_static.py` qui copie les fichiers nécessaires dans `web/static/`.
4. Workflow GitHub Actions `.github/workflows/pages.yml` qui publie `web/static/` sur GitHub Pages.
5. Tester localement (`python -m http.server` dans `web/static/`) puis activer GitHub Pages
   (Settings → Pages → Source : GitHub Actions).

## Commit
`E33 : version statique GitHub Pages (stlite)`
