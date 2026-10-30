# E09 — Poutres 2/3 (méthode d'intégration, actions imposées)

**Modèle** : **Sonnet conseillé** · **Durée** : 60 min · **Prérequis** : E08.

## Objectif
Ajouter la résolution hyperstatique par **intégration** (réactions + constantes d'intégration
résolues ensemble), le contrôle Ménabréa ≡ intégration (`hyperCheck`), et valider les actions imposées :
appuis élastiques (ressorts), tassements d'appui, rotules intermédiaires (poutre Gerber), actions thermiques.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §1 « Actions imposées », §3 « Hyperstatique, intégration » | équations de compatibilité |
| `BeamAndTrussSolver.m` | 1247–1416 | `btsSolveSub` (relire : chemins `menabrea`, `integration`, `both`, `forceLsq`) |
| `BeamAndTrussSolver.m` | 1560–1674 | `btsBendDisp`, `btsCondText`, `btsIntegration` |
| `BeamAndTrussSolver.m` | 1960–2005 | agrégation de `hyperCheck` dans `btsSolveBeam` |
| `tests/test_BeamAndTrussSolver.m` | 483–526 | `testMenabreaEqualsIntegration`, `testShearEnergyMenabrea` |
| `tests/test_BeamAndTrussSolver.m` | 1041–1131 | tassements, ressort, thermique, rotule |

## À faire
1. Porter `btsIntegration` → `_integration(sp, A, bv, TL, ML, TU, MU, br, o, forceLsq)`.
   Système surdéterminé → `np.linalg.lstsq(A, b, rcond=None)` ; carré → `np.linalg.solve`.
2. Supprimer le `NotImplementedError("E09")` de l'étape E08 : les chemins `'integration'` et `'both'`
   (valeur par défaut) fonctionnent ; `hyperCheck` et `reactionsIntegration` sont renseignés.
3. Vérifier que ressorts (`supports[i]["spring"]`), tassements (`dx`, `dy`, `dz`), rotules (`hinges`) et
   `thermal` (`epsX`, `kv`, `kw`) sont bien pris en compte dans **les deux** méthodes (ils ont été portés
   en E08 dans la normalisation et les sous-problèmes : relire et corriger si besoin).
4. `includeShearEnergy` (option) : terme `∫ ti tj/(k G S) ds` dans Ménabréa.

## Tests à ajouter dans `web/tests/test_beam_solver.py`
1. Porter `testMenabreaEqualsIntegration`, `testShearEnergyMenabrea`, `testSupportSettlementPropped`,
   `testSupportSettlementTwoSpans`, `testSpringSupport`, `testThermalActions`, `testIntermediateHinge`
   (sans la partie `SolicitationsEngine.deflection`, faite en E13 : la commenter **en indiquant** `# E13`).
2. Tous les tests de E08 passent maintenant **aussi** avec les options par défaut (`solveBeam(m)`).
   Paramétrer : `@pytest.mark.parametrize("opts", [None, OPTS])`.
3. Golden `golden_beam.json` : **tous** les cas `*_solveBeam`, options par défaut :
   `assert_matches(sol, c["sortie"], rel=1e-9, abs_=1e-6, ignore={"equations", "internalIntegral", "methodCheck"})`.
   `hyperCheck` doit être < 1e-9 quand il n'est pas NaN.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E09 : poutres, méthode d'intégration, ressorts, tassements, rotules, thermique`
