> ## ⚠️ VERSION WEB NON MAINTENUE : archivée
> Cette version web (Python / Streamlit) est **abandonnée** et conservée uniquement pour archive. Elle ne reçoit plus
> de corrections ni d'évolutions et peut être en retard sur l'application PC. Pour un outil à jour, utiliser
> l'application MATLAB : voir [desktop/](../desktop/README.md) et le [README racine](../README.md).
> Raison de l'abandon : [À COMPLÉTER PAR THÉO].

# MecaStruct RdM Pro — version web

Version web (Python, Streamlit) de l'application MATLAB MecaStruct RdM Pro, par Théo Brun.
Les calculs sont ceux de l'application MATLAB, sans MATLAB. Le plan de migration est dans
[PLAN.md](../Migration%20MATLAB%20vers%20site%20web/PLAN.md).

**Site en ligne** : arrêté. L'ancienne adresse (appmecastructurerdm.streamlit.app) ne répond plus ; l'application ne se lance plus qu'en local (voir plus bas).

## Mode d'emploi rapide

1. Choisir une page dans le menu de gauche : Sections, Poutres, Treillis, Sollicitations, Flambage,
   Tenseurs & critères, Hooke & jauges (calculs), Base de données et Convertisseur (données).
2. Chaque page de calcul s'ouvre sur un exemple d'école : modifier la saisie, puis cliquer sur **Calculer**.
3. Les barres « Enregistrer / ouvrir » téléchargent et rechargent le problème en JSON ; les résultats
   s'exportent en .xlsx ou en .csv.
4. Le bouton **Dossier de validation** (actif après « Calculer ») télécharge un fichier HTML qui refait les
   calculs à la main ; pour un PDF, utiliser « Imprimer → Enregistrer en PDF » du navigateur.
5. Cas de contrôle (page Poutres) : IPE 200, S235, L = 4 m, q = 10 kN/m → Mmax = 20 kN·m,
   σmax = 102,9 MPa, flèche 9,029 mm par les 4 méthodes (avec le tranchant décoché).

Le serveur ne garde rien : aucune donnée n'est stockée, tout fichier utile se télécharge.

## Différences avec la version MATLAB

Détail dans [PLAN.md §7](../Migration%20MATLAB%20vers%20site%20web/PLAN.md) :

- le clic sur le schéma est remplacé par des tableaux éditables et des boutons « Ajouter » ;
- Annuler / Rétablir : historique de 10 états de la saisie Poutres ;
- export d'un graphique : bouton appareil photo de Plotly (PNG) ;
- dossier de validation : HTML téléchargeable (diagrammes interactifs), pas de PDF direct ;
- données utilisateur et problèmes : fichiers JSON téléchargés puis rechargés, pas de `.mat` ni de stockage serveur ;
- la visite guidée est un encadré « Comment faire » sur l'Accueil ;
- treillis : 2D seulement (comme l'interface MATLAB).

## Limites connues

- **Flexion avec un profilé du catalogue** : le dossier de validation (§3) relève 3 écarts de 2,9 % entre le
  solveur (valeurs tabulées du profilé) et le contrôle à la main (géométrie analytique simplifiée, sans congés).
  MATLAB lit la même géométrie dans son contrôle ; l'écart n'est pas corrigé, la décision est à prendre.
- **Module d'Young des aciers de la base** : E = 190 GPa pour S185, S235, S275 et S355 (valeur du cours), alors
  que les XC et la pratique courante (EN 1993-1-1) prennent 210 GPa. Les flèches des aciers de construction
  sont donc environ 10 % plus grandes qu'avec 210 GPa. Pour changer, modifier E dans la saisie ou ajouter un
  matériau dans la base (page Base de données).
- **Profilés UPN et UAP** : la géométrie analytique ne tient pas compte des congés ni de la pente des ailes ;
  l'écart avec le catalogue peut dépasser 10 % (l'application l'affiche).
- **Dossier de validation** : les formules sont rendues par MathJax chargé depuis Internet ; hors ligne, un
  bandeau le signale.
- **Téléversement et téléchargement** (enregistrer / ouvrir) : non pilotés par les tests automatiques.
- **Hébergement gratuit** (Streamlit Community Cloud) : mise en veille après 12 h sans visite (réveil en
  environ 30 s), environ 1 Go de mémoire. Le thème est dans `.streamlit/config.toml`, à la racine du dépôt
  (Streamlit Community Cloud ne lit que ce dossier).

Autres limites de calcul (aluminium, titane, cuivre, bois, béton, ressorts, tassements…) : voir le
[README MATLAB](../README.md).

## Lancer l'application en local

Dans Windows PowerShell, `python -m pytest` et `ruff` se lancent depuis `web/`, mais l'application se lance depuis la
racine du dépôt, pour que le thème de `.streamlit/config.toml` s'applique :

```
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
cd ..
streamlit run web/streamlit_app.py
```

L'application s'ouvre sur http://localhost:8501. Arrêter le serveur avec Ctrl+C.

## Tests

```
python -m pytest -q
python -m ruff check .
```

## Mise en ligne (Streamlit Community Cloud)

- Dépôt : `theo33-oss/App_MecaStruct_RdM_Pro`, branche `main`
- Fichier principal : `web/streamlit_app.py`
- Python : 3.12 (« Advanced settings » au déploiement)
- Dépendances : `web/requirements.txt` (pytest et ruff sont dans `requirements-dev.txt`, non installés en ligne)

Historique : réglages utilisés quand le site était publié. Le site a été arrêté ; un `git push` ne met plus rien en ligne.
