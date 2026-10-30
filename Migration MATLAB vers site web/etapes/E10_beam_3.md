# E10 — Poutres 3/3 (méthode intégrale, équations par tronçon, rapport)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E09.

## Objectif
Terminer `beam_solver.py` : calcul des efforts par la méthode **intégrale** (contrôle des coupures,
`methodCheck`), **équations par tronçon** (texte et LaTeX), **rapport** complet en français.
Supprimer la fonction `_provisoire_E10` créée en E08.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `BeamAndTrussSolver.m` | 1675–1759 | `btsIntegralMethod`, `btsSym2Poly` |
| `BeamAndTrussSolver.m` | 1880–2015 | fin de `btsSolveBeam` : `methodCheck`, équations, extrema, contexte du rapport |
| `BeamAndTrussSolver.m` | 2046–2451 | `btsLinEq`, `btsAppendTerm`, `btsDofText`, `btsJoinNums`, `btsBeamReport` |
| `BeamAndTrussSolver.m` | 442–553 | `btsPolyStr`, `btsNum`, `btsTexNum` (déjà portés en E05 dans `pp.py` : les réutiliser) |
| `tests/test_BeamAndTrussSolver.m` | 456–482, 645–738, 891–899 | `testCutsEqualIntegral`, `testOptions`, `testReportAndLatexFormat`, `testLatexRendersWithoutWarning`, `testReportHyperstaticSignMy` |

## À faire
1. `_integralMethod(br, tol, act, dl, D, useSym)` : intégration de `dTy/ds = −py`, `dMfz/ds = −Ty`,
   `dMfy/ds = Tz`, `dN/ds = −px` depuis s = L avec sauts aux charges ponctuelles. Chemin numérique
   avec `np.polyint` ; chemin symbolique (SymPy) seulement si `useSymbolic` est vrai ; le résultat doit
   être identique. Par défaut `useSymbolic = False` en Python (plus rapide) : écrire ce choix dans la
   docstring de `solveBeam`.
2. `internalIntegral` (6 `PP`), `methodCheck` (écart relatif max), `equations` : liste de dicts par tronçon
   `{s1, s2, N, N_txt, Ty, Ty_txt, ..., Mfz, Mfz_txt}` (LaTeX complet `'$M_{fz}(s) = ...$'` et texte).
3. `_beamReport(ctx) -> (report, latex)` : port **ligne à ligne** de `btsBeamReport` ; mêmes phrases,
   mêmes formats numériques (`%.5g`, etc.), mêmes unités.
4. Supprimer `_provisoire_E10`.

## Tests à ajouter dans `web/tests/test_beam_solver.py`
1. Porter `testCutsEqualIntegral`, `testOptions`, `testReportAndLatexFormat`, `testReportHyperstaticSignMy`.
2. Remplacer `testLatexRendersWithoutWarning` (spécifique à MATLAB) par : chaque chaîne de `sol["latex"]`
   et de `sol["equations"]` commence et finit par `$`, a autant de `{` que de `}`, et ne contient aucun
   des motifs interdits d'ARCHITECTURE.md §0.4 (`\iint`, `\text{`, `\dfrac`, `pmatrix`…).
3. Golden : enlever `"equations", "internalIntegral", "methodCheck"` de la liste `ignore` du test golden
   de E09 (`internalIntegral` est maintenant comparé ; `methodCheck` < 1e-9).
4. Cas README (`readme_IPE200_solveBeam`) : `extrema["Mfz"]["max"] == approx(20e3, rel=1e-9)`.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.
Afficher dans le terminal le rapport du cas `appui_appui_uniforme` (`print("\n".join(sol["report"]))`)
et vérifier qu'il est lisible et en français.

## Commit
`E10 : poutres, méthode intégrale, équations par tronçon, rapport`
