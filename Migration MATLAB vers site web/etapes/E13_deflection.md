# E13 — Déformée : 4 méthodes, énergie, intégrales de Mohr (`deflection.py`)

**Modèle** : **Sonnet conseillé** · **Durée** : 90 min · **Prérequis** : E10, E12.

## Objectif
Porter de `SolicitationsEngine.m` : `deflection` (intégration, aires, Castigliano, Mohr),
`strainEnergy`, `mohrIntegral`. Les 4 méthodes doivent donner la **même** flèche.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §4 « `d = deflection(...)` » | options, 4 méthodes, champs de sortie |
| `SolicitationsEngine.m` | 480–780 | `deflection`, `strainEnergy`, `mohrIntegral`, `buckling` |
| `SolicitationsEngine.m` | 888–1256 | `seFastOpts`, `seDeflOpts`, `seImposed`, `seSeg`, `sePolyAdd`, `seIntegration`, `sePPMaxAbs`, `seAires`, `seAiresKnown`, `seUnitSolve`, `seIntProd`, `seIyz`, `seBendMoments`, `seDefaultS0`, `seCoefAt`, `seShift`, `seDecompose`, `seShapeName`, `seMohrTex` |
| `SolicitationsEngine.m` | 1262–1269 | `seGauss` |
| `tests/test_SolicitationsEngine.m` | `grep -n "^function test" tests/test_SolicitationsEngine.m` | tests de flèche, énergie, Mohr |
| `tests/test_BeamAndTrussSolver.m` | 1041–1131 | parties « flèche » laissées en `# E13` à l'étape E09 |

## Fichier à créer : `web/mecastruct/core/deflection.py`
```python
def deflection(model: dict, sol: dict, opts: dict | None = None) -> dict
def strainEnergy(model: dict, sol: dict) -> dict      # UN, UTy, UTz, UMt, UMfy, UMfz, total
def mohrIntegral(ppA, ppB, a: float, b: float) -> dict  # value, valueTable, segments (DataFrame), allTabulated
```
Puis, dans `solicitations.py`, ajouter `buckling(p)` qui délègue à `buckling.analyze(p)` (module créé en
E14 : import **dans** la fonction pour éviter un import circulaire).

Points d'attention :
- `opts` : `plane` (`'xy'` | `'xz'`), `nPoints` (201), `nCastigliano` (41), `includeShear` (True),
  `methods` (les 4), `s0`. Valeurs par défaut identiques au MATLAB.
- **Castigliano** appelle `beam_solver.solveBeam` en chemin rapide
  (`{"internalMethod": "coupures", "hyperMethod": "menabrea", "useSymbolic": False}`) sous charge unité.
- `d["comparison"]` : `DataFrame` colonnes `Methode, fmax_m, s_m, Ecart_pct`.
- `d["integration"]["constants"]` : `DataFrame` `Troncon, s1, s2, C1, C2` ; `d["aires"]["areas"]` :
  `DataFrame` `Troncon, s1, s2, Aire, sBar`.
- Rotules : saut de pente ; ressorts et tassements : `v(appui) = tassement − R/k` (voir `seImposed`).
- `mohrIntegral` : décomposition trapèze + parabole par tronçon, utilise `kt_mohr.mohrTable()` ;
  hors table → quadrature de Gauss.

## Tests à écrire : `web/tests/test_deflection.py`
1. Porter les tests MATLAB de `deflection`, `strainEnergy`, `mohrIntegral`.
2. Réactiver les parties `# E13` de `web/tests/test_beam_solver.py`.
3. Golden `golden_beam.json` :
   - cas `*_deflection` :
     ```python
     e = c["entrees"]; m = e["modele"]
     sol = beam_solver.solveBeam(m)
     d = deflection.deflection(m, sol, e["opts"])
     assert_matches(d, c["sortie"], rel=1e-7, abs_=1e-12)
     ```
   - cas `*_strainEnergy` : `strainEnergy(m, sol)`, `rel=1e-9`.
4. Golden `golden_solicitations.json`, cas `mohrIntegral_triangle_parabole` :
   `mohrIntegral(e["ppA"], e["ppB"], e["a"], e["b"])` (les `pp` du JSON passent par `pp.asPP`).
5. Cas README : flèche max = 9,029 mm (`abs(fmax) == approx(9.029e-3, rel=1e-3)`) par les 4 méthodes
   et égale à `5qL⁴/(384 E Iz)` à `rel=1e-9`.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E13 : déformée (4 méthodes), énergie de déformation, intégrales de Mohr`
