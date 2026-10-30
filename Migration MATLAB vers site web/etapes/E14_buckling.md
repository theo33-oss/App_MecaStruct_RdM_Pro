# E14 — Flambage (`buckling.py`)

**Modèle** : Haiku · **Durée** : 45 min · **Prérequis** : E02.

## Objectif
Porter `BucklingEngine.m` : Euler, Rankine, compression simple, arbre de décision, courbe de stabilité,
modes propres et démonstration (équation `v'' + k²v = 0`).

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §5 | entrées / sorties |
| `BucklingEngine.m` | 1–351 | `analyze`, `stabilityCurve`, `listConditions`, `effectiveLengthCoefficient`, `hasSymbolic` |
| `BucklingEngine.m` | 352–729 | aides : contrôles, `normalizeCondition`, `conditionInfo`, `kLClampedPinned`, `modeFunctions`, `checkMode`, `bcDeterminant`, `firstRoot`, `characteristicEquation`, `symbolicSolve` |
| `BucklingEngine.m` | 730–1051 | `buildDerivation`, `buildReport`, `buildLatex`, formats |
| `tests/test_BucklingEngine.m` | `grep -n "^function test" tests/test_BucklingEngine.m` | tests à porter |

## Fichier à créer : `web/mecastruct/core/buckling.py`
```python
def analyze(p: dict) -> dict
def stabilityCurve(E: float, Re: float, lambdaVec=None, lambdaCompression: float = 20) -> dict
def listConditions() -> list[dict]
def effectiveLengthCoefficient(condition: str) -> float
def hasSymbolic() -> bool
```
- `modeShape` : fonction Python `modeShape(s)` vectorisée (max = 1).
- `fzero(f, [a, b])` → `scipy.optimize.brentq(f, a, b, xtol=1e-14)`. `kL` encastré-articulé = 4,4934…
  (racine de `tan(x) = x` dans [4 ; 4,7]).
- Chemin symbolique (`symbolicSolve` : `dsolve`, `det`, `vpasolve`) : le porter avec SymPy **seulement**
  si c'est simple ; sinon garder le chemin numérique et mettre `methodUsed = "numérique"`. Les valeurs
  numériques (Pcrit, PE, PR…) doivent être identiques dans tous les cas.

## Tests à écrire : `web/tests/test_buckling.py`
1. Porter tous les tests de `tests/test_BucklingEngine.m` (régimes, PE, PR, courbe, modes).
2. Golden `golden_buckling.json` : cas `buckling_*` → `analyze(e)` (`rel=1e-9`) ; `stabilityCurve` →
   `stabilityCurve(e["E"], e["Re"], e["lambdaVec"])` (`rel=1e-9`).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E14 : flambage (Euler, Rankine, compression, courbe de stabilité)`
