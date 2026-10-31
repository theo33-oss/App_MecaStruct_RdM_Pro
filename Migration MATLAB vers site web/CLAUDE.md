# CLAUDE.md — MecaStruct RdM Pro (migration web en cours)

> Ce fichier est dans le dossier « Migration MATLAB vers site web ». Les chemins ci-dessous sont
> relatifs à la **racine du dépôt** (dossier `5_MecaStruct_RdM_Pro`). Les noms de chemin contiennent des
> espaces : toujours les mettre entre guillemets dans les commandes (`ls "Migration MATLAB vers site web"`).

Ce dépôt contient l'application MATLAB **MecaStruct RdM Pro** (racine) et sa **migration en application web
Python/Streamlit** (dossier `web/`). Le plan complet est dans `Migration MATLAB vers site web/PLAN.md`.

## Avant toute action

1. Lire `Migration MATLAB vers site web/PLAN.md` (sections 3 et 4 au minimum).
2. Lire `Migration MATLAB vers site web/PROGRESSION.md` pour savoir quelle étape est en cours.
3. Lire la fiche de l'étape demandée : `Migration MATLAB vers site web/etapes/Exx_*.md`. Suivre ses instructions
   **dans l'ordre**, sans en sauter, sans faire l'étape suivante.

## Règles absolues

- **Ne jamais modifier** les fichiers MATLAB (`*.m` à la racine, `tests/*.m`) ni `docs/ARCHITECTURE.md`.
  Ils sont la référence. Seuls `web/`, `.streamlit/` (thème, à la racine : seul endroit lu par Streamlit Community Cloud), `.github/workflows/`,
  `Migration MATLAB vers site web/PROGRESSION.md` et `Migration MATLAB vers site web/BLOCAGES.md` sont modifiables (et `CLAUDE.md` si une fiche le demande).
- **Ne jamais recopier à la main** une valeur numérique de la base (matériaux, profilés…) : elle vient
  de `web/data/*.json`.
- **Ne jamais modifier un fichier golden** (`web/tests/golden/*.json`) ni affaiblir une tolérance de test
  pour qu'un test passe. Si un test échoue, c'est le code Python qu'il faut corriger.
- Les moteurs (`web/mecastruct/core/`) n'importent **jamais** `streamlit` ni `plotly`.
- Code, commentaires, messages d'erreur et textes d'interface **en français** ; noms des fonctions
  publiques et des clés de dictionnaires **identiques à MATLAB / ARCHITECTURE.md** (camelCase).
- Chaque fonction publique a une docstring : une phrase, puis entrées / sorties avec unités.
- Pas de code incomplet : aucun `TODO`, aucun `pass` provisoire, aucun `...` à la place d'un calcul,
  sauf exception écrite noir sur blanc dans la fiche d'étape (ex. E08), à supprimer à l'étape indiquée.

## Lire les gros fichiers MATLAB

Les fichiers `.m` sont longs (jusqu'à 5 000 lignes). Ne jamais les lire en entier : utiliser les plages de
lignes données dans la fiche d'étape (outil Read avec `offset` et `limit`, 300 lignes maximum par lecture),
ou chercher une fonction avec `grep -n "function nom" Fichier.m`. Si les numéros de lignes ne
correspondent plus (fichier modifié), relancer `grep -n "^\s*function " Fichier.m`.

## Commandes (depuis le dossier `web/`)

Windows PowerShell (machine de Théo) :
```
.\.venv\Scripts\Activate.ps1
python -m pytest -q                      # tous les tests
python -m pytest tests/test_geometry.py -q   # un seul fichier
python -m ruff check .                   # qualité
python -m ruff format .                  # mise en forme
cd ..; streamlit run web/streamlit_app.py  # lancer l'application depuis la racine (thème de .streamlit/) : http://localhost:8501
```
Linux / macOS / Claude Code web : remplacer la première ligne par `source .venv/bin/activate`.

## Fin d'étape (obligatoire)

1. `python -m pytest -q` entièrement vert et `python -m ruff check .` sans erreur.
2. Cocher l'étape dans `Migration MATLAB vers site web/PROGRESSION.md` et y écrire 1 à 3 lignes de notes.
3. `git add -A` puis `git commit -m "<message donné dans la fiche>"`. Ne pas faire `git push` sauf si
   la fiche le demande.
4. Afficher un résumé court : fichiers créés, nombre de tests, points d'attention.

## Si tu bloques

Après **3 tentatives** infructueuses sur le même problème : arrête, décris le problème dans
`Migration MATLAB vers site web/BLOCAGES.md` (étape, fichier, test en échec, message d'erreur, ce qui a été essayé),
committe, et demande de l'aide. Ne contourne pas le problème en supprimant ou en modifiant un test.
