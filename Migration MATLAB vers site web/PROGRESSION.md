# Progression de la migration web

Cocher `[x]` à la fin de chaque étape (tests verts + commit) et ajouter 1 à 3 lignes de notes dessous.

## Phase 0 — Préparation (Théo)
- [ ] E00 — Dépôt GitHub, Python, exports JSON depuis MATLAB

## Phase 1 — Squelette
- [ ] E01 — Dossier web/, dépendances, pytest, ruff, CI, page « Bonjour »

## Phase 2 — Moteurs de calcul
- [ ] E02 — errors.py, utils.py, units.py (+ convertisseur)
- [ ] E03 — data_manager.py
- [ ] E04 — kt_mohr.py
- [ ] E05 — pp.py
- [ ] E06 — geometry.py 1/2
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
