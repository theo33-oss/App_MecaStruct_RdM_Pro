# E26 — Page « Poutres » 1/2 (saisie, calcul, diagrammes, rapports)

**Modèle** : Haiku · **Durée** : 90 min · **Prérequis** : E25.

## Objectif
Le cœur de l'application : la page Poutres avec la saisie de base, le calcul, les graphiques et tous
les tableaux de résultats. Les fonctions avancées (combinaisons, EC3, fatigue, profilé le plus léger,
charge mobile, actions imposées, annuler/rétablir) viennent en E27.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 3255–3458 | `buildBeamTab` (ordre des champs, sections pliables, libellés, infobulles `tips`, colonnes des tableaux) |
| `MecaStruct_App.m` | 283–404 | `computeBeam` (ce qui est affiché après le calcul) |
| `MecaStruct_App.m` | 3716–3804, 4813–4873 | `selectedComps`, `beamSectionProps`, `beamCheck`, `equationTable`, `plotEquations`, `plotRatios` |
| `docs/img/03_poutre_sollicitations.png`, `04_poutre_deformee.png` | — | rendus MATLAB |

## Contenu
Colonne de gauche (expanders dans l'ordre MATLAB) :
- Exemples (`example_picker("Beam")`).
- Poutre et matériau : L (m), matériau (selectbox de `dm.listMaterials()`, remplit E, G, Re), E, G, Re.
- Section : S, Iz, Iy, Ix, Iyz (mm², mm⁴), ky, kz, |y|max, |z|max (mm) ; ligne d'info de la section
  utilisée ; bouton « Importer depuis Sections » (si `result("Sec")` existe).
- Appuis : tableau éditable `sup` (Position (m), Type ∈ 5 types, Nom) + rappel de ce que bloque chaque type.
- Forces ponctuelles `pl`, couples `pm`, charges réparties `dl` (colonnes et cas G/Q/W/S comme le MATLAB).
- Options : plan de la flèche (xy/xz), cisaillement inclus, coefficient de sécurité s, Kt, composantes à tracer.
- Bouton **Calculer** → `beam_services.computeBeam`.
Les infobulles (`help=`) reprennent `B.tips`.

Colonne de droite :
- Ligne d'état (`widgets.status`) avec l'avertissement « résultats non fiables » si `unreliable`.
- Onglets graphiques : **Schéma** (`beamSchematic`, aussi affiché **avant** calcul avec `sol=None` comme
  aperçu), **Diagrammes** (`internalForces`), **Déformée α(s), v(s)** (`deflection`), **Équations par tronçon**.
- Onglets de résultats : **Rapport**, **Réactions** (tableau kN, kN·m), **Équations** (texte SI et LaTeX),
  **Flèche : 4 méthodes** (`d["comparison"]`), **Énergie**, **Contraintes** (`beamCheck`).

## Tests : `web/tests/test_page_poutres.py`
`AppTest` : page sans exception ; charger l'exemple « Appui-appui : charge uniforme », cliquer
« Calculer », vérifier qu'aucune exception n'est levée et que `result("Beam")["sol"]["extrema"]["Mfz"]["max"] > 0` ;
cas du README saisi dans les widgets → texte d'état contenant `20` (kN·m) ou flèche `9,029`/`9.029` mm.

## Commit
`E26 : page Poutres (saisie, calcul, diagrammes, rapports)`
