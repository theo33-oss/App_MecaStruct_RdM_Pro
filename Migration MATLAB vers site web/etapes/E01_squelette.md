# E01 — Squelette du projet web

**Modèle** : Haiku · **Durée** : 20 min · **Prérequis** : E00 cochée (fichiers `web/data/*.json` et
`web/tests/golden/*.json` présents).

## Objectif
Créer le dossier `web/` avec l'environnement Python, les outils de test, l'intégration continue GitHub et
une page Streamlit minimale. **Aucun calcul** dans cette étape.

## À lire
- `Migration MATLAB vers site web/PLAN.md` sections 3 et 4.
- Les fichiers modèles de `Migration MATLAB vers site web/fichiers_modeles/` (ils sont déjà prêts : on les copie).

## À faire, dans l'ordre

1. Vérifier les prérequis :
   `ls web/data` doit lister 8 fichiers `.json` ; `ls web/tests/golden` doit lister des `golden_*.json`.
   S'ils manquent : **arrêter** et dire à Théo de faire l'étape E00.
2. Créer l'arborescence (fichiers vides `__init__.py` compris) :
   ```
   web/mecastruct/__init__.py            (contenu : docstring d'une ligne + __version__ = "0.1.0")
   web/mecastruct/core/__init__.py       (docstring d'une ligne)
   web/mecastruct/services/__init__.py   (docstring d'une ligne)
   web/mecastruct/plots/__init__.py      (docstring d'une ligne)
   web/mecastruct/ui/__init__.py         (docstring d'une ligne)
   web/app_pages/                        (dossier vide avec un fichier .gitkeep)
   web/tests/__init__.py                 (vide)
   ```
3. Copier les fichiers modèles **sans les modifier** :
   | Modèle (`Migration MATLAB vers site web/fichiers_modeles/`) | Destination |
   | --- | --- |
   | `requirements.txt` | `web/requirements.txt` |
   | `requirements-dev.txt` | `web/requirements-dev.txt` |
   | `pyproject.toml` | `web/pyproject.toml` |
   | `streamlit_app.py` | `web/streamlit_app.py` |
   | `config.toml` | `web/.streamlit/config.toml` |
   | `golden_tools.py` | `web/tests/golden_tools.py` |
   | `test_smoke.py` | `web/tests/test_smoke.py` |
   | `tests.yml` | `.github/workflows/tests.yml` (**racine du dépôt**) |
4. Créer `web/.gitignore` :
   ```
   .venv/
   __pycache__/
   .pytest_cache/
   .ruff_cache/
   *.pyc
   ```
5. Créer l'environnement virtuel et installer (depuis `web/`) :
   - Windows : `py -3.12 -m venv .venv` puis `.\.venv\Scripts\Activate.ps1`
   - Linux/macOS : `python3.12 -m venv .venv` puis `source .venv/bin/activate`
   - puis : `python -m pip install --upgrade pip` et `python -m pip install -r requirements-dev.txt`
6. Créer `web/README.md` (≈ 20 lignes, en français) : but, lancement local (`streamlit run streamlit_app.py`),
   tests (`python -m pytest -q`), lien vers `Migration MATLAB vers site web/PLAN.md`, auteur Théo Brun.

## Vérifications
- `python -m pytest -q` → `test_package_importable` passe, les 8 `test_data_files_readable` passent
  (pas « skipped »), `test_golden_files_readable` passe.
- `python -m ruff check .` → « All checks passed! ».
- `streamlit run streamlit_app.py` → la page « MecaStruct RdM Pro » s'ouvre (arrêter avec Ctrl+C).

## Critère de fin
Les trois vérifications ci-dessus sont bonnes.

## Commit
`E01 : squelette web (Python, Streamlit, pytest, ruff, CI)`
