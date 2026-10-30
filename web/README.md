# MecaStruct RdM Pro — version web

Version web (Python, Streamlit) de l'application MATLAB MecaStruct RdM Pro, par Théo Brun.
Les calculs sont ceux de l'application MATLAB, sans MATLAB. Le plan de migration est dans
[PLAN.md](../Migration%20MATLAB%20vers%20site%20web/PLAN.md).

## Lancer l'application en local

Depuis le dossier `web/`, dans Windows PowerShell :

```
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
streamlit run streamlit_app.py
```

L'application s'ouvre sur http://localhost:8501. Arrêter le serveur avec Ctrl+C.

## Tests

```
python -m pytest -q
python -m ruff check .
```
