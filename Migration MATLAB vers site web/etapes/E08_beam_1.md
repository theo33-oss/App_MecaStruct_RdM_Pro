# E08 — Poutres 1/3 (`beam_solver.py` : modèle, sous-problèmes, coupures, Ménabréa)

**Modèle** : **Sonnet conseillé** (Haiku possible en suivant strictement les sous-étapes) ·
**Durée** : 90 min · **Prérequis** : E05.

## Objectif
Porter le cœur du solveur de poutres : normalisation du modèle, découpage en 4 sous-problèmes (axial,
flexion xy, flexion xz, torsion), méthode des **coupures**, résolution isostatique et hyperstatique par
**Ménabréa**, extrema. La méthode d'**intégration** (hyperstatique) est faite en E09, la méthode
**intégrale** des efforts et le rapport en E10.

Cette étape se fait en **trois sous-étapes avec un commit chacune**.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §0.3, §3 | conventions de signe, modèle `model`, types d'appuis, champs de `sol` |
| `docs/ARCHITECTURE.md` | §1 « Actions imposées » | ressorts, tassements, rotules, thermique |
| `BeamAndTrussSolver.m` | 233–257 | `solveBeam` (doc des options) |
| `BeamAndTrussSolver.m` | 565–674 | Gauss et représentation matricielle des coefficients (`btsGauss`, `btsGaussData`, `btsGaussVals`, `btsMatIntegrate`, `btsMatEval`, `btsCleanMat`, `btsMatToPP`, `btsMatMaxAbs`) |
| `BeamAndTrussSolver.m` | 675–864 | `btsCutBend`, `btsBeamOpts`, petites aides (`btsIsNum`, `btsVec`, `btsReqPos`, `btsOptNum`, `btsOptName`, `btsGetArr`, `btsNormType`) |
| `BeamAndTrussSolver.m` | 865–1094 | `btsNormalizeModel`, `btsPrepDist`, `btsTexId`, `btsMakeUnk` |
| `BeamAndTrussSolver.m` | 1095–1480 | `btsBuildSubs`, `btsAddCompat`, `btsBaseOrder`, `btsSolveSub`, `btsCleanReactions`, `btsLoadMoments`, `btsReactionDiff` |
| `BeamAndTrussSolver.m` | 1481–1581 | `btsMenabrea`, `btsBendDisp`, `btsCondText` |
| `BeamAndTrussSolver.m` | 1760–2045 | `btsJumps`, `btsExtrema`, `btsSolveBeam` (programme principal), `btsReactionStruct`, `btsActions` |
| `tests/test_BeamAndTrussSolver.m` | 157–455, 527–695, 903–1040 | cas d'école, mécanismes, entrées invalides, normalisation, options, aides des tests |

## Sous-étape A — aides et normalisation (commit `E08a`)
Dans `web/mecastruct/core/beam_solver.py` :
- porter `btsBeamOpts` → `_beamOpts(opts)`, les petites aides (`_reqPos`, `_optNum`, `_optName`,
  `_getArr`, `_normType`), `btsNormalizeModel` → `_normalizeModel(model) -> (m, notes)`, `btsPrepDist` → `_prepDist`.
- Le modèle d'entrée est un `dict` ; `supports`, `pointLoads`, `pointMoments`, `distLoads`, `hinges`
  peuvent être absents, `None`, une liste ou **un dict seul** (JSON MATLAB) → `as_list`.
  `coeffs` peut être un nombre ou une liste → `as_array`.
- Porter la représentation « matrice de coefficients + quadrature de Gauss » (`_gauss`, `_gaussData`,
  `_matIntegrate`, `_matEval`, `_cleanMat`, `_matToPP`, `_matMaxAbs`) et `_cutBend`.
- Tests (`web/tests/test_beam_solver.py`) : porter `testInvalidInputs`, `testNormalizationAndDefaults`
  (partie normalisation), et un test de `_gauss` (intègre exactement x⁵ sur [0, 1] avec 3 points).

## Sous-étape B — sous-problèmes, coupures, Ménabréa, solveBeam (commit `E08b`)
- Porter `btsBuildSubs`, `btsAddCompat`, `btsBaseOrder`, `btsSolveSub`, `btsCleanReactions`,
  `btsLoadMoments`, `btsReactionDiff`, `btsMenabrea`, `btsBendDisp`, `btsCondText`, `btsJumps`,
  `btsExtrema`, `btsReactionStruct`, `btsActions` et le programme principal `btsSolveBeam`.
- Fonction publique :
  ```python
  def solveBeam(model: dict, opts: dict | None = None) -> dict
  ```
  Champs de `sol` : ceux d'ARCHITECTURE.md §3 (`model, h, isostatic, reactions, breaks, N, Ty, Tz, Mt,
  Mfy, Mfz, internalIntegral, methodCheck, equations, extrema, menabrea, reactionsMenabrea,
  reactionsIntegration, report, latex, hyperCheck…`). `N…Mfz` sont des `PP`. `reactions` est une
  **liste de dicts** (`name, pos, type, Rx, Ry, Rz, Mx, My, Mz`).
- **Pour cette étape seulement** : dans `btsSolveSub`, les appels à `btsIntegration` lèvent
  `NotImplementedError("E09")` **uniquement** si `hyperMethod` vaut `'integration'` ou `'both'` ;
  les tests de cette étape appellent `solveBeam(m, {"hyperMethod": "menabrea", "internalMethod": "coupures"})`.
  Le calcul de l'intégrale des efforts (`btsIntegralMethod`) et `btsBeamReport` sont remplacés
  provisoirement par : `internalIntegral = {}`, `methodCheck = nan`, `equations = []`, `report = []`,
  `latex = []`. Écrire ces 3 remplacements dans **une seule** fonction `_provisoire_E10(...)` clairement
  nommée, que E10 supprimera.
- Mécanisme réel → `MecaStructError("MecaStruct:Beam:mechanism", ...)`.

## Sous-étape C — tests (commit `E08c`)
Dans `web/tests/test_beam_solver.py`, avec `OPTS = {"hyperMethod": "menabrea", "internalMethod": "coupures"}` :
1. Porter les tests MATLAB : `testSimplySupportedCentralLoad`, `testCantileverTipLoad`,
   `testSimplySupportedUniform`, `testProppedCantileverUniform`, `testTwoEqualSpansUniform`,
   `testFixedFixedUniform`, `testAxialBarFixedFixed`, `testLoadsInPlaneXZ`, `testTorsion`,
   `testPointCouple`, `testTriangularLinearLoad`, `testPartialTrapezoidLoadLocalXi`,
   `testMechanismDetection`, `testFastPathPerformance` (temps < 1 s pour 50 appels rapides).
   Recopier les aides `baseModel`, `addSup`, `addF`, `addC`, `addQ`, `deflectionAt` (lignes 903–1040)
   en Python. La partie flèche de ces tests (`deflectionAt`) utilise `pp.ppIntegrate` : la garder.
2. Golden `golden_beam.json`, tous les cas `*_solveBeam` **sans** ressort, tassement, rotule ni
   thermique (exclure les ids `gerber_*`, `appui_elastique_*`, `tassement_*`, `thermique_*` : E09) :
   ```python
   sol = beam_solver.solveBeam(c["entrees"], OPTS)
   assert_matches(sol, c["sortie"], rel=1e-9, abs_=1e-6,
                  ignore={"equations", "internalIntegral", "methodCheck", "hyperCheck",
                          "reactionsIntegration", "integration"})
   ```
   `abs_=1e-6` (N ou N·m) absorbe les zéros numériques de l'ordre de 1e-10.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commits
`E08a : poutres, normalisation du modèle` · `E08b : poutres, sous-problèmes, coupures, Ménabréa` ·
`E08c : poutres, tests isostatiques et hyperstatiques (Ménabréa)`
