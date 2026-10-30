# Plan de migration web de MecaStruct RdM Pro

> Document maître. À lire en entier au début de chaque session Claude Code, avec `CLAUDE.md` (dans ce dossier)
> et la fiche de l'étape en cours (`Migration MATLAB vers site web/etapes/Exx_*.md`).

## 1. Objectif

Transformer l'application MATLAB `MecaStruct_App` (≈ 21 000 lignes, 9 modules) en une **application web**
utilisable depuis n'importe quel navigateur, sans MATLAB, hébergée gratuitement à partir de GitHub,
**sans perdre aucun calcul** et avec **exactement les mêmes résultats numériques**.

Le code MATLAB reste dans le dépôt comme **référence** : on ne le modifie pas. La version web est créée
dans un nouveau dossier `web/`.

## 2. Choix technique (décidé, ne pas remettre en cause)

| Besoin | Choix | Pourquoi |
| --- | --- | --- |
| Langage | **Python 3.12** | NumPy reproduit presque ligne à ligne la syntaxe matricielle MATLAB ; SciPy remplace `integral2`, `fzero`, `eig` ; SymPy remplace la Symbolic Math Toolbox. |
| Interface web | **Streamlit** (≥ 1.40) | Une page web se décrit en Python pur (pas de HTML/JavaScript à écrire) ; champs, tableaux éditables (`st.data_editor`), onglets, formules (`st.latex`, rendu KaTeX), boutons de téléchargement. |
| Graphiques | **Plotly** | Graphiques interactifs (zoom, survol des valeurs) dans le navigateur. |
| Tableaux / export | **pandas** + **openpyxl** | `DataFrame` ≈ `table` MATLAB ; export `.xlsx` et `.csv`. |
| Dossier de validation | **Jinja2** + MathJax | Génère le même dossier HTML autonome que `ValidationReport.m`. |
| Géométrie 2D | **shapely** | Remplace `polyshape` (union et différence de contours de sections). |
| Tests | **pytest** | Port des tests `matlab.unittest` + comparaison aux résultats MATLAB exportés en JSON. |
| Qualité | **ruff** | Vérifie le style et les erreurs courantes. |
| Hébergement | **Streamlit Community Cloud** (gratuit, connecté à GitHub) | Déploiement en 3 clics depuis le dépôt GitHub ; chaque `git push` met le site à jour. |

Limites connues de l'hébergement gratuit : l'application s'endort après 12 h sans visite (réveil ≈ 30 s),
environ 1 Go de mémoire, une seule application privée (les autres doivent être publiques).

## 3. Architecture cible

```
5_MecaStruct_RdM_Pro/                 ← dépôt GitHub (racine)
├── *.m, tests/*.m, docs/             ← code MATLAB de référence (NE PAS MODIFIER)
├── Migration MATLAB vers site web/  ← ce plan, CLAUDE.md (règles), fiches d'étapes, scripts d'export MATLAB
└── web/                              ← NOUVELLE application
    ├── streamlit_app.py              ← point d'entrée (navigation entre pages)
    ├── requirements.txt              ← dépendances (lu par Streamlit Cloud)
    ├── pyproject.toml                ← configuration pytest + ruff
    ├── .streamlit/config.toml        ← thème
    ├── data/                         ← JSON exportés de MATLAB (matériaux, profilés, formules, unités…)
    ├── mecastruct/
    │   ├── core/                     ← MOTEURS DE CALCUL (aucun import de streamlit, aucun tracé)
    │   │   ├── errors.py             ← MecaStructError
    │   │   ├── utils.py              ← as_list, formatage des nombres, petits outils
    │   │   ├── units.py              ← toSI, fromSI, unitFactor, convertUnits
    │   │   ├── data_manager.py       ← DataManager.m
    │   │   ├── kt_mohr.py            ← abaques Kt + table des intégrales de Mohr
    │   │   ├── pp.py                 ← polynômes par morceaux (utilitaires pp de BeamAndTrussSolver.m)
    │   │   ├── geometry.py           ← GeometryEngine.m
    │   │   ├── beam_solver.py        ← BeamAndTrussSolver.m (poutres)
    │   │   ├── truss_solver.py       ← BeamAndTrussSolver.m (treillis)
    │   │   ├── solicitations.py      ← SolicitationsEngine.m (sauf flèches)
    │   │   ├── deflection.py         ← SolicitationsEngine.m (flèches, énergie, intégrales de Mohr)
    │   │   ├── buckling.py           ← BucklingEngine.m
    │   │   ├── tensors.py            ← TensorAndCriteriaEngine.m (tenseurs, Mohr, critères)
    │   │   ├── hooke_gauges.py       ← TensorAndCriteriaEngine.m (Hooke, Voigt, jauges, rosettes)
    │   │   └── design_checks.py      ← DesignChecks.m
    │   ├── services/                 ← logique de l'application sans interface (port des computeXxx de MecaStruct_App.m)
    │   │   ├── compute.py            ← une fonction par onglet : saisie (unités d'affichage) → SI → moteur → résultat
    │   │   ├── beam_services.py      ← modèle de poutre depuis la saisie, combinaisons, charge rapide
    │   │   ├── beam_design.py        ← Eurocode 3, fatigue, profilé le plus léger, charge mobile
    │   │   ├── examples.py           ← exemples d'école (loadExample)
    │   │   ├── project_io.py         ← enregistrer / ouvrir un problème ou un projet (JSON), export xlsx/csv
    │   │   └── validation_report.py  ← dossier de validation HTML
    │   ├── plots/                    ← port de PlotEngine.m avec Plotly (aucun calcul mécanique)
    │   │   ├── beam_plots.py
    │   │   ├── section_plots.py
    │   │   └── other_plots.py        ← flambage, Mohr 2D/3D, lieux de plasticité, treillis, abaques Kt
    │   └── ui/                       ← briques d'interface Streamlit réutilisables
    │       ├── widgets.py            ← champ numérique avec unité, bloc rapport, bloc LaTeX, boutons d'export
    │       ├── state.py              ← accès à st.session_state
    │       └── formula_panel.py      ← « Formulaire rapide »
    ├── app_pages/                    ← une page Streamlit par onglet de l'application MATLAB
    │   ├── accueil.py  base_de_donnees.py  sections.py  poutres.py  treillis.py
    │   ├── sollicitations.py  flambage.py  tenseurs.py  hooke_jauges.py  convertisseur.py
    └── tests/
        ├── conftest.py               ← chargement des fichiers golden, comparaisons tolérantes
        ├── golden/                   ← JSON exportés de MATLAB (cas de référence)
        └── test_*.py                 ← un fichier par module
```

Règle de dépendances (identique à ARCHITECTURE.md §0.1) :

```
app_pages → ui, services, plots, core
services  → core
plots     → core.pp, core.geometry (outline, widthAt), core.tensors (lieux) — jamais de calcul mécanique
core      → numpy, scipy, sympy (optionnel), pandas — JAMAIS streamlit ni plotly
```

## 4. Conventions de traduction MATLAB → Python (OBLIGATOIRES)

`docs/ARCHITECTURE.md` reste **la source de vérité** : mêmes noms, mêmes champs, mêmes unités, mêmes
conventions de signe. On change seulement la syntaxe.

### 4.1 Correspondance des objets

| MATLAB | Python |
| --- | --- |
| classe statique `GeometryEngine` | module `mecastruct/core/geometry.py` |
| méthode publique `GeometryEngine.analytical(sec)` | fonction `analytical(sec)` — **même nom en camelCase** |
| méthode privée / fonction locale `btsPolyAdd` | fonction privée `_polyAdd` (préfixe `_`, on peut retirer le préfixe du module `bts`, `se`, `pe`) |
| structure `p.E` | `dict` : `p["E"]` |
| champ optionnel `isfield(p,'s')` | `p.get("s", 1.0)` |
| tableau de structures `model.supports(i).pos` | `list[dict]` : `model["supports"][i]["pos"]` |
| `cell` colonne de `char` (`report`, `latex`) | `list[str]` |
| `table` MATLAB | `pandas.DataFrame` avec **les mêmes noms de colonnes** |
| polynôme par morceaux `pp.breaks`, `pp.coefs{k}` | `PP(breaks: np.ndarray, coefs: list[np.ndarray])` (dataclass de `pp.py`) |
| handle `@(y,z) ...` | fonction Python / `lambda` |
| `NaN`, `Inf` | `math.nan`, `math.inf` (ou `np.nan`, `np.inf`) |
| `true` / `false` | `True` / `False` |
| `error('MecaStruct:Beam:mechanism', msg)` | `raise MecaStructError("MecaStruct:Beam:mechanism", msg)` |
| `class DataManager < handle` | classe Python `DataManager` (seule vraie classe) |
| Symbolic Math Toolbox | SymPy, **optionnel** ; par défaut chemin numérique ; champ `methodUsed` conservé |

### 4.2 Pièges classiques (à relire avant chaque étape de moteur)

1. **Indices** : MATLAB commence à 1, Python à 0. `x(end)` → `x[-1]`, `x(2:end)` → `x[1:]`,
   `x(1:n)` → `x[:n]`. Les numéros montrés à l'utilisateur (nœuds, barres, tronçons) restent à partir de 1.
2. **Bornes de `range`** : `for k = 1:n` → `for k in range(n)` (k de 0 à n−1).
3. **Polynômes** : même ordre que MATLAB (`np.polyval`, `np.polyint`, `np.polyder`, `np.polymul`,
   `np.roots` utilisent l'ordre décroissant des puissances comme `polyval`). `np.polyint(c)` ajoute une
   constante nulle à la fin, comme `polyint`.
4. **Division matricielle** : `A\b` → `np.linalg.solve(A, b)` si A carrée inversible, sinon
   `np.linalg.lstsq(A, b, rcond=None)[0]`. `pinv` → `np.linalg.pinv`.
5. **Valeurs propres** : `eig` (symétrique) → `np.linalg.eigh` (ordre CROISSANT : retrier comme MATLAB).
6. **Intégrales** : `integral` → `scipy.integrate.quad` ; `integral2` → `scipy.integrate.dblquad`
   (attention, `dblquad(f, a, b, gfun, hfun)` intègre `f(y, x)` : ordre des variables inversé) ;
   `fzero` → `scipy.optimize.brentq` (intervalle) ou `fsolve` ; `fminbnd` →
   `scipy.optimize.minimize_scalar(..., bounds=(lo, hi), method="bounded", options={"xatol": ...})` ;
   `interp1(x, y, xi, 'linear')` → `np.interp(xi, x, y)` (**attention** : `np.interp` prolonge par la
   valeur de bord alors que `interp1` renvoie NaN hors de l'intervalle) ; `polyshape`, `union`,
   `subtract` → `shapely` (`Polygon`, `unary_union`, `.difference`) ; `dsolve`/`vpasolve` → SymPy
   (optionnel, toujours avec un repli numérique).
7. **Produits** : `A*B` (matriciel) → `A @ B` ; `A.*B` → `A * B` ; `A'` → `A.T` ; `A.^2` → `A**2`.
8. **Vecteurs ligne/colonne** : NumPy n'a pas de différence 1×n / n×1 pour un tableau 1-D.
   Utiliser des tableaux 1-D partout sauf pour les vraies matrices.
9. **Comparaisons de flottants** : garder les mêmes tolérances que MATLAB (ex. `tol = 1e-12 * L`).
10. **`sprintf('%g')`** → `f"{x:g}"` ; `'%.4g'` → `f"{x:.4g}"`. Les nombres affichés gardent la
    **virgule décimale française** quand le MATLAB l'utilise (voir `utils.fmt_fr`).
11. **Copie** : en MATLAB une structure modifiée dans une fonction est une copie ; en Python un `dict`
    est partagé. **Toujours** faire `p = copy.deepcopy(p)` en début de fonction si on modifie l'entrée.
12. **`isempty(x)`** : pour une liste → `len(x) == 0` ; pour un tableau → `x.size == 0`.
13. **`max` avec indice** : `[v, i] = max(x)` → `i = int(np.argmax(x)); v = x[i]`.
14. **`linspace`, `zeros`, `ones`** : `np.linspace`, `np.zeros`, `np.ones` (attention : `zeros(n)` MATLAB
    est n×n, `np.zeros(n)` est un vecteur).
15. **Chaînes LaTeX** : utiliser des chaînes brutes `r"..."`. MathJax/KaTeX acceptent ce que MATLAB
    accepte ; `st.latex` attend la formule **sans** les `$` qui l'entourent.

### 4.2 bis Entrées venant du JSON MATLAB

`jsonencode` écrit un tableau de structures **d'un seul élément** comme un objet seul, et un vecteur d'un
seul élément comme un nombre. Toute fonction publique d'un moteur doit donc accepter, là où une liste est
attendue, aussi un `dict` seul (`utils.as_list`) et, là où un vecteur est attendu, aussi un nombre
(`utils.as_array`). NaN et Inf sont écrits `NaN` / `Infinity` dans les JSON : `json.load` les lit directement.

### 4.3 Résultats

Chaque fonction de calcul renvoie un `dict` qui contient **au minimum** `report` (`list[str]`, en
français) et `latex` (`list[str]`), comme en MATLAB. Les autres clés ont les noms d'ARCHITECTURE.md.

### 4.4 Unités

Moteurs en **SI strict** (N, m, Pa, rad…). Les conversions se font dans `services/compute.py` avec
`units.toSI` / `units.fromSI`. Unités de saisie et d'affichage identiques à MATLAB
(ARCHITECTURE.md §8) : mm, m, kN, kN·m, kN/m, GPa, MPa, 10⁻⁶/°C, µdéf ; résultats en kN, kN·m, MPa, mm, mrad.

## 5. Stratégie de vérification (« golden files »)

Avant toute traduction, Théo lance dans MATLAB deux scripts fournis (`Migration MATLAB vers site web/matlab/`) :

- `export_database_json.m` → `web/data/*.json` : toute la base de données (matériaux, profilés,
  formulaires LaTeX, unités, abaques…). **On ne recopie jamais une valeur à la main.**
- `export_golden_json.m` → `web/tests/golden/golden_*.json` : ≈ 200 cas calculés par les moteurs
  MATLAB (sections, 18 poutres dont hyperstatiques, treillis, sollicitations, flambage, tenseurs,
  Eurocode 3, convertisseur), avec entrées et sorties.

Chaque module Python doit :
1. passer les **tests portés** depuis `tests/test_<Module>.m` (valeurs théoriques du cours) ;
2. reproduire les **golden files** à `rel=1e-9` (calculs exacts) ou `rel=1e-6` (intégrations numériques).

Un module n'est « terminé » que si `pytest` est entièrement vert.

## 6. Découpage en étapes

Chaque étape = **une session Claude Code** (commencer par `/clear`). Une étape produit au plus
≈ 600 lignes de Python. Les fiches détaillées sont dans `Migration MATLAB vers site web/etapes/`.
Le suivi se fait dans `Migration MATLAB vers site web/PROGRESSION.md`.

| Phase | Étape | Contenu | Modèle conseillé |
| --- | --- | --- | --- |
| 0. Préparation | E00 | (Théo, à la main) dépôt GitHub, Python, exports JSON depuis MATLAB | — |
| 1. Squelette | E01 | Dossier `web/`, dépendances, pytest, ruff, CI GitHub, page « Bonjour » | Haiku |
| 2. Moteurs | E02 | `errors.py`, `utils.py`, `units.py` (+ convertisseur) | Haiku |
| | E03 | `data_manager.py` (matériaux, profilés, matage, formulaires) | Haiku |
| | E04 | `kt_mohr.py` (abaques Kt, table des intégrales de Mohr) | Haiku |
| | E05 | `pp.py` (polynômes par morceaux, poly2latex) | Haiku |
| | E06 | `geometry.py` 1/2 (validation, primitives, analytique/Huygens, b(y), Q(y), contour) | Haiku |
| | E07 | `geometry.py` 2/2 (intégrale, tabulée, comparaison, facteurs de cisaillement, J) | Haiku |
| | E08 | `beam_solver.py` 1/3 (normalisation du modèle, sous-problèmes, coupures) | **Sonnet** conseillé |
| | E09 | `beam_solver.py` 2/3 (hyperstatique : Ménabréa, intégration, ressorts, tassements, rotules, thermique) | **Sonnet** conseillé |
| | E10 | `beam_solver.py` 3/3 (méthode intégrale, extrema, équations par tronçon, rapport) | Haiku |
| | E11 | `truss_solver.py` (nœuds + rigidités, 2D/3D) | Haiku |
| | E12 | `solicitations.py` (traction, cisaillement, Jourawski, matage, clavette, goupille, torsion, flexion) | Haiku |
| | E13 | `deflection.py` (4 méthodes de flèche, énergie, intégrales de Mohr) | **Sonnet** conseillé |
| | E14 | `buckling.py` | Haiku |
| | E15 | `tensors.py` (principales, facette, Mohr 2D/3D, critères, lieux) | Haiku |
| | E16 | `hooke_gauges.py` (Hooke, orthotrope, Voigt, jauges, ponts, rosettes) | Haiku |
| | E17 | `design_checks.py` (Eurocode 3 + Goodman) | Haiku |
| 3. Services | E18 | `beam_services.py` (modèle depuis la saisie, combinaisons, charge rapide) | Haiku |
| | E19 | `beam_design.py` (EC3 complet, fatigue, profilé le plus léger, charge mobile) | Haiku |
| | E20 | `compute.py` + `examples.py` (tous les autres onglets, exemples d'école) | Haiku |
| 4. Graphiques | E21 | `beam_plots.py` (schéma, diagrammes, déformée, enveloppe charge mobile) | Haiku |
| | E22 | `section_plots.py` + `other_plots.py` | Haiku |
| 5. Interface | E23 | Coquille Streamlit : navigation, briques `ui/`, Accueil, Formulaire rapide | Haiku |
| | E24 | Pages Base de données + Convertisseur | Haiku |
| | E25 | Page Sections | Haiku |
| | E26 | Page Poutres 1/2 (saisie, calcul, diagrammes, rapports) | Haiku |
| | E27 | Page Poutres 2/2 (combinaisons, EC3, fatigue, profilé, charge mobile, actions imposées) | Haiku |
| | E28 | Pages Treillis + Sollicitations | Haiku |
| | E29 | Pages Flambage, Tenseurs & critères, Hooke & jauges | Haiku |
| | E30 | Enregistrer / ouvrir (problème, projet) + export xlsx/csv sur toutes les pages | Haiku |
| 6. Dossier | E31 | Dossier de validation HTML (port de ValidationReport.m) | **Sonnet** conseillé |
| 7. Mise en ligne | E32 | Déploiement Streamlit Community Cloud, README, recette finale | Haiku |
| (option) | E33 | Version sans serveur sur GitHub Pages (stlite) | Sonnet |

## 7. Ce qui change par rapport à MATLAB (assumé)

| Fonction MATLAB | Version web |
| --- | --- |
| Clic sur le schéma pour ajouter un appui/une force | Remplacé par des tableaux éditables + boutons « Ajouter » (plus fiable dans un navigateur) |
| Annuler / Rétablir de la saisie Poutres | Historique simple dans `st.session_state` (10 états), étape E27 |
| Export PNG/PDF d'un graphique | Bouton appareil photo de Plotly (PNG) ; PDF par impression du navigateur |
| Dossier de validation en PDF (Edge sans fenêtre) | HTML téléchargeable ; PDF par « Imprimer → Enregistrer en PDF » du navigateur |
| Sauvegarde `.mat` des données utilisateur | Fichier JSON téléchargé puis rechargé (pas de stockage serveur) |
| Visite guidée en 5 étapes | Encadré « Comment faire » sur l'Accueil |
| Méthodes symboliques | SymPy si installé (il l'est), sinon numérique ; résultats identiques |

## 8. Critères de réussite finaux

- `pytest` : 100 % vert (tests portés + golden).
- Cas de bout en bout du README : IPE 200, S235, L = 4 m, q = 10 kN/m → Mmax = 20 kN·m,
  σmax = 102,9 MPa, flèche 9,029 mm par les 4 méthodes.
- Chaque onglet MATLAB a sa page web avec les mêmes saisies, résultats, graphiques et exports.
- L'application est en ligne sur `https://<nom>.streamlit.app` et se met à jour à chaque `git push`.
