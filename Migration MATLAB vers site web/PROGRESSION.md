# Progression de la migration web

Cocher `[x]` à la fin de chaque étape (tests verts + commit) et ajouter 1 à 3 lignes de notes dessous.

## Phase 0 — Préparation (Théo)
- [x] E00 — Dépôt GitHub, Python, exports JSON depuis MATLAB
  Dépôt privé `App_MecaStruct_RdM_Pro` sur GitHub. Python 3.12.10 installé. 8 JSON de base et 9 fichiers golden (209 cas) exportés. Erreurs attendues seulement : erreur_tabulated_rectangle, truss_mecanisme.

## Phase 1 — Squelette
- [x] E01 — Dossier web/, dépendances, pytest, ruff, CI, page « Bonjour »
  Modèles copiés sans modification (dont tests.yml à la racine, non testé sur GitHub : pas de push). venv Python 3.12.10 : pytest 10 passed (0 skip), ruff « All checks passed! », Streamlit health ok et page « MecaStruct RdM Pro » vue. Étape E00 vérifiée : 8 JSON et 9 golden présents.

## Phase 2 — Moteurs de calcul
- [x] E02 — errors.py, utils.py, units.py (+ convertisseur)
  Ports de buildUnitMap / normalizeUnit (table recopiée, contrôlée contre units.json par les tests), toSI / fromSI rejettent les textes (invalidValue) comme MATLAB.
  pytest : 167 passed (10 anciens + 157 nouveaux) ; ruff check et ruff format --check verts.
- [x] E03 — data_manager.py
  Port de DataManager.m sans abaques Kt ni table de Mohr (E04). Sauvegarde .mat remplacée par exportUserData / importUserData (JSON) ; getMaterial et getProfile renvoient aussi IsUser et Author (ARCHITECTURE §1).
  pytest 201 passed (34 nouveaux) ; ruff check et ruff format --check verts. Tests d'unités déjà dans test_units.py (E02), testDefaultUserFilePath sans objet en Python.
- [x] E04 — kt_mohr.py
  Port de ktCharts, evalKt, evalKtInfo, mohrTable ; abaques et table lus dans kt_charts.json et mohr_table.json. Les 10 couples inversés de Mohr reprennent la forme directe, a et b échangés.
  pytest 217 passed (16 nouveaux, dont 4 cas golden) ; ruff check et ruff format --check verts. Test LaTeX de MATLAB porté pour Kt et Mohr seulement (chaînes $…$, commandes interdites).
- [x] E05 — pp.py
  Port de ppEval, ppSample, ppIntegrate, ppDerivative, ppAdd, ppScale, ppMultiply, ppRefine, ppIntegral, ppZero, ppConst, poly2latex, poly2str ; PP en dataclass, asPP accepte le dict JSON. hasSymbolic réexporté de data_manager.
  Aides privées _tol, _segIndex, _mergeBreaks, _polyAdd, _pad, _shiftPoly, _polyStr, _num, _texNum prêtes pour E08 à E13.
  pytest 225 passed (8 nouveaux : testPp*, testPoly2*, testHasSymbolic portés + aides) ; ruff check et ruff format --check verts.
- [x] E06 — geometry.py 1/2
  Port de validateSection, primitives, widthAt, firstMomentAbove, outline, fromProfile, sectionTypes, hasSymbolic et des aides privées (Huygens, formules fermées, J, b(y), Q(y), contours, textes). _assembleP absente (E07). Écarts : widthAt prend side = 'max' par défaut (valeur MATLAB, pas « both » de la fiche) ; un profilé donné seulement par famille et nom est complété depuis le catalogue (demandé par la fiche, absent de MATLAB).
  pytest 304 passed (79 nouveaux : tests portés, golden widthAt et firstMomentAbove, cohérence Huygens) ; ruff check et ruff format --check verts. Reportés à E07 : testReportFormat et erreurs de integral.
- [ ] E07 — geometry.py 2/2
- [ ] E08 — beam_solver.py 1/3 (modèle, sous-problèmes, coupures)
- [ ] E09 — beam_solver.py 2/3 (hyperstatique)
- [ ] E10 — beam_solver.py 3/3 (méthode intégrale, extrema, équations, rapport)
- [ ] E11 — truss_solver.py
- [ ] E12 — solicitations.py
- [ ] E13 — deflection.py
- [ ] E14 — buckling.py
- [ ] E15 — tensors.py
- [ ] E16 — hooke_gauges.py
- [ ] E17 — design_checks.py

## Phase 3 — Services
- [ ] E18 — beam_services.py
- [ ] E19 — beam_design.py
- [ ] E20 — compute.py + examples.py

## Phase 4 — Graphiques
- [ ] E21 — beam_plots.py
- [ ] E22 — section_plots.py + other_plots.py

## Phase 5 — Interface
- [ ] E23 — Coquille Streamlit, Accueil, Formulaire rapide
- [ ] E24 — Base de données + Convertisseur
- [ ] E25 — Sections
- [ ] E26 — Poutres 1/2
- [ ] E27 — Poutres 2/2
- [ ] E28 — Treillis + Sollicitations
- [ ] E29 — Flambage, Tenseurs & critères, Hooke & jauges
- [ ] E30 — Enregistrer / ouvrir + exports

## Phase 6 — Dossier de validation
- [ ] E31 — validation_report.py

## Phase 7 — Mise en ligne
- [ ] E32 — Déploiement Streamlit Community Cloud + recette
- [ ] E33 — (option) Version GitHub Pages sans serveur

## Notes
