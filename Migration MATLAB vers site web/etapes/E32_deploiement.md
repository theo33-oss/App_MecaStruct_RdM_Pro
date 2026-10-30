# E32 — Mise en ligne sur Streamlit Community Cloud et recette finale

**Modèle** : Haiku pour la partie code ; **Théo** pour la partie en ligne · **Durée** : 45 min ·
**Prérequis** : E31 (ou E26 pour une première mise en ligne partielle).

## Partie Claude Code
1. Vérifier que `web/requirements.txt` contient toutes les bibliothèques importées par `web/mecastruct`
   et `web/app_pages` (`grep -rh "^import\|^from" web/mecastruct web/app_pages | sort -u`), **sans**
   pytest ni ruff.
2. Créer `web/runtime.txt` ? **Non** : sur Streamlit Community Cloud, la version de Python se choisit
   dans « Advanced settings » au déploiement (3.12).
3. Vérifier que l'application ne lit **aucun** fichier en dehors du dépôt et n'écrit nulle part (le
   serveur est en lecture seule à part `/tmp`).
4. Mettre à jour `web/README.md` : adresse du site (à compléter par Théo), mode d'emploi rapide,
   différences avec la version MATLAB (PLAN.md §7), comment lancer les tests.
5. Recette automatique : `python -m pytest -q` (tout vert), puis `streamlit run streamlit_app.py` et
   parcours de **chaque** page avec son exemple d'école ; noter le résultat dans `PROGRESSION.md`.
6. Commit `E32 : préparation du déploiement` puis `git push`.

## Partie Théo (dans le navigateur, ≈ 10 min)
1. Aller sur https://share.streamlit.io , se connecter avec GitHub, autoriser l'accès au dépôt.
2. « Create app » → « Deploy a public app from GitHub » (ou privée) :
   - Repository : `<ton-identifiant>/mecastruct-rdm-pro`, Branch : `main`
   - Main file path : `web/streamlit_app.py`
   - App URL : par ex. `mecastruct-rdm` → `https://mecastruct-rdm.streamlit.app`
   - Advanced settings → Python version : 3.12
3. « Deploy ». Le premier démarrage prend quelques minutes (installation des bibliothèques).
4. Recette en ligne : cas du README (IPE 200, S235, L = 4 m, q = 10 kN/m) → Mmax = 20 kN·m,
   σmax = 102,9 MPa, flèche 9,029 mm par les 4 méthodes ; un dossier de validation téléchargé s'ouvre
   correctement.
5. Ensuite, chaque `git push` sur `main` met le site à jour automatiquement.

Limites de l'offre gratuite : mise en veille après 12 h sans visite (réveil en ≈ 30 s), ≈ 1 Go de mémoire.
