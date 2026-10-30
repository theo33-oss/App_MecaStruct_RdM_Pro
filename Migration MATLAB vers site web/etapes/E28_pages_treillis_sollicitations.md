# E28 — Pages « Treillis » et « Sollicitations »

**Modèle** : Haiku · **Durée** : 75 min · **Prérequis** : E26.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 3805–3879 | `buildTrussTab`, `readTruss` |
| `MecaStruct_App.m` | 3880–4014 | `buildSolicitationsTab` (4 sous-onglets), `shearBase` |
| `MecaStruct_App.m` | 925–1253 | affichage après `computeTruss`, `computeTraction`, `computeShear`, `computeKey`, `computePin`, `computeTorsion`, `computeBending` |
| `docs/img/05_treillis.png` … `09_flexion.png` | — | rendus MATLAB |

## `web/app_pages/treillis.py`
Disposition commune (voir E25). Saisie : dimension 2D/3D, tableau des nœuds (x, y[, z] en m, nom),
tableau des barres (nœud i, nœud j — **numéros à partir de 1**), E (GPa), S (mm²) global ou par barre,
tableau des appuis (nœud, blocage x/y/z cochés), tableau des charges (nœud, Fx, Fy, Fz en kN), échelle de
la déformée. Résultats : graphique `other_plots.truss`, tableau des barres (kN, MPa, mm), réactions,
déplacements, rapport, formules. `formula_panel("treillis")`.

## `web/app_pages/sollicitations.py`
`st.tabs(["Traction", "Cisaillement & matage", "Torsion", "Flexion"])`, chacun avec sa disposition
gauche/droite, sa clé de saisie (`Tra`, `Cis`, `Tor`, `Fle`) et son bouton « Calculer ».
- Traction : N, S0, L0, E, ν, α, ΔT, Kt, Re, s, ΔLmax, + fonctions optionnelles S(x), N(x), ΔT(x) écrites
  en texte (port de `parseFunction` : n'autoriser que les noms `x`, `pi`, `sqrt`, `sin`, `cos`, `exp`… —
  **pas d'`eval` libre**, utiliser `sympy.sympify` + `lambdify` avec une liste blanche).
- Cisaillement & matage : cisaillement simple (`computeShear`, Jourawski et graphique `sectionStress` si la
  section vient de Sections), clavette (`computeKey`), goupille (`computePin`), pressions de matage de la base.
- Torsion : arbre plein/creux, Kt, θadm, profil τ(r).
- Flexion : section, N, Mfz, Mfy, Kt, Re, s ; graphique de σ et axe neutre ; bouton « Charger depuis la poutre ».
`formula_panel` change selon le sous-onglet (`traction`, `cisaillement`/`matage`, `torsion`, `flexion`).

## Tests : `web/tests/test_pages_treillis_sollicitations.py`
`AppTest` : chaque page s'exécute ; l'exemple par défaut de chaque sous-onglet se calcule sans exception.

## Commit
`E28 : pages Treillis et Sollicitations`
