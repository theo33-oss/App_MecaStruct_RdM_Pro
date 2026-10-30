# E05 — Polynômes par morceaux (`pp.py`)

**Modèle** : Haiku · **Durée** : 45 min · **Prérequis** : E02.

## Objectif
Porter les utilitaires de polynômes par morceaux de `BeamAndTrussSolver.m`. Ils servent à **tous** les
efforts intérieurs, déformées et tracés : ils doivent être parfaits.

Rappel (ARCHITECTURE.md §0.5) : `pp.breaks` = abscisses croissantes (m), `pp.coefs[k]` = coefficients
(ordre `polyval`, puissances décroissantes) **en variable GLOBALE s**, valables sur `[breaks[k], breaks[k+1]]`.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §0.5 | contrat des `pp` |
| `BeamAndTrussSolver.m` | 27–232 | méthodes publiques `ppEval` … `hasSymbolic` |
| `BeamAndTrussSolver.m` | 279–560 | aides : `btsTol`, `btsCheckPP`, `btsSideIsLeft`, `btsSegIndex`, `btsEval`, `btsSample`, `btsIntegratePP`, `btsMergeBreaks`, `btsRefineCoefs`, `btsPolyAdd`, `btsPad`, `btsShiftPoly`, `btsPolyStr`, `btsNum`, `btsTexNum`, `btsHasSymbolic` |
| `tests/test_BeamAndTrussSolver.m` | 19–156 | tests `testPp*`, `testPoly2*`, `testHasSymbolic` |

## Fichier à créer : `web/mecastruct/core/pp.py`

```python
@dataclass
class PP:
    """Polynôme par morceaux : breaks (n+1,), coefs = liste de n tableaux 1-D (ordre polyval, variable globale s)."""
    breaks: np.ndarray
    coefs: list[np.ndarray]

def asPP(x) -> PP                       # accepte PP ou dict {"breaks", "coefs"} (JSON) ; valide (btsCheckPP)
def ppEval(pp, s, side: str = "right")   # même forme de sortie que s ; scalaire → float
def ppSample(pp, nPerSeg: int = 60) -> tuple[np.ndarray, np.ndarray]
def ppIntegrate(pp, C0: float = 0.0) -> PP
def ppDerivative(pp) -> PP
def ppAdd(ppA, ppB) -> PP
def ppScale(pp, k: float) -> PP
def ppMultiply(ppA, ppB) -> PP
def ppRefine(pp, newBreaks) -> PP
def ppIntegral(pp, a: float, b: float) -> float
def ppZero(breaks) -> PP
def ppConst(breaks, c: float) -> PP
def poly2latex(c, var: str = "s") -> str
def poly2str(c, var: str = "s") -> str
def hasSymbolic() -> bool               # réutiliser data_manager.hasSymbolic
```
Garder aussi en fonctions privées (préfixe `_`) les aides MATLAB utiles aux étapes suivantes :
`_tol`, `_segIndex`, `_mergeBreaks`, `_polyAdd`, `_pad`, `_shiftPoly`, `_polyStr`, `_num`, `_texNum`.
Les étapes E08 à E13 les importeront (`from mecastruct.core.pp import _polyAdd` est autorisé).

Points d'attention (tous testés dans le MATLAB) :
- **Tolérance aux points de rupture** : `1e-12 * L` (voir `btsTol`). Avec `side="right"` (défaut) un point
  de rupture prend la valeur du tronçon de droite ; `side="left"` celle du tronçon de gauche ;
  en `s = L` toujours la limite à gauche ; en `s = 0` toujours la limite à droite.
- **Hors du domaine** : prolongement du premier / dernier polynôme (ex. `ppEval(pp, -1) == -2` dans le test).
- `ppEval(pp, [])` → tableau vide ; une matrice d'entrée donne une matrice de sortie de même forme.
- `ppSample` duplique les points de rupture (sauts visibles) ; `nPerSeg < 2` → erreur.
- `ppIntegrate` donne une primitive **continue** valant `C0` en `breaks[0]`.
- `side` invalide → `MecaStructError("MecaStruct:BeamAndTrussSolver:invalidArgument", ...)` ;
  pp invalide → `"MecaStruct:BeamAndTrussSolver:invalidPP"`.
- `poly2latex` : format `%.4g`, signes propres, `'0'` si nul, pas de `$` autour. Reproduire **à
  l'identique** les chaînes attendues par les tests MATLAB.

## Tests à écrire : `web/tests/test_pp.py`
Porter **un par un** tous les tests des lignes 19–156 de `tests/test_BeamAndTrussSolver.m`
(`testPpEvalSides`, `testPpSample`, `testPpIntegrateDerivative`, `testPpAddScaleMultiplyRefine`,
`testPpIntegralZeroConst`, `testPoly2latexPoly2str`, `testHasSymbolic`), en gardant les mêmes valeurs.
Correspondances : `tc.verifyEqual(a, b)` → `assert a == b` (ou `np.testing.assert_allclose`),
`'AbsTol', t` → `atol=t`, `'RelTol', t` → `rtol=t`, `tc.verifyError(@() f, id)` →
`with pytest.raises(MecaStructError) as e: ...; assert e.value.identifier == id`.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E05 : polynômes par morceaux (pp)`
