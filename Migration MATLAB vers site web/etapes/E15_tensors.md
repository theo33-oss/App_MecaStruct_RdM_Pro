# E15 — Tenseurs, Mohr, critères (`tensors.py`)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E02.

## Objectif
Porter la première moitié de `TensorAndCriteriaEngine.m` : contraintes principales, facette,
Mohr 2D (contraintes et déformations), tricercle de Mohr 3D, critères (Tresca, Von Mises, Rankine),
lieux de plasticité.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §6 | entrées / sorties |
| `TensorAndCriteriaEngine.m` | 1–716 | `principal`, `facet`, `plane2D`, `plane2DStrain`, `mohr3D`, `criteria`, `yieldLoci` |
| `TensorAndCriteriaEngine.m` | 1206–1227 | `mohrCore` |
| `TensorAndCriteriaEngine.m` | 1417–1787 | `principalTriplet`, contrôles (`asTensor`, `asVector3`, `asVoigt6`, `scalarIn`…), `kindFactor`, `symbolicAvailable`, `safeRatio`, `clean`, formats (`fmt`, `tex`, `vecTxt`, `vecTex`, `matTex`, `joinRaw`, `polyTex`, `polyTxt`), `err` |
| `tests/test_TensorAndCriteriaEngine.m` | `grep -n "^function test" tests/test_TensorAndCriteriaEngine.m` | tests à porter (ceux de ces 7 fonctions) |

## Fichier à créer : `web/mecastruct/core/tensors.py`
```python
def principal(sig, useSymbolic: bool | None = None) -> dict
def facet(sig, n, t=None) -> dict
def plane2D(sxx, syy, sxy, theta) -> dict
def plane2DStrain(exx, eyy, exy, theta) -> dict
def mohr3D(pr, nPts: int = <valeur MATLAB>) -> dict
def criteria(pr, Re: float, s: float = 1, sigmaR: float | None = None) -> dict
def yieldLoci(Re: float, s: float = 1, sigmaR: float | None = None, nPts: int = <valeur MATLAB>) -> dict
```
Toutes les aides privées (contrôles, formats LaTeX) vont aussi dans ce fichier avec le préfixe `_` :
`hooke_gauges.py` (E16) les importera.

Points d'attention :
- `eig` → `np.linalg.eigh` (valeurs **croissantes**) ; trier en **décroissant** comme MATLAB
  (`sigmaI ≥ sigmaII ≥ sigmaIII`).
- **Signe des vecteurs propres** : NumPy et MATLAB peuvent renvoyer `−v` au lieu de `v`. Reproduire la
  règle de normalisation du MATLAB (trièdre direct, éventuel choix de signe) ; si le golden diffère
  encore seulement par le signe d'une colonne, comparer `directions` en valeur absolue et l'écrire en
  commentaire dans le test.
- `rootsCharPoly` peut être complexe avec une partie imaginaire infime : renvoyer `np.real_if_close`.
  Dans le golden, un tableau complexe est écrit `{"re": [...], "im": [...]}` : comparer `re` à la partie
  réelle et `im` à la partie imaginaire (abs 1e-6).
- `plane2D` est vectorisé en `theta`.

## Tests à écrire : `web/tests/test_tensors.py`
1. Porter les tests MATLAB de ces fonctions : traction simple, cisaillement pur (Tresca 2τ, VM √3·τ),
   exemple 3D, cohérence Mohr 2D avec la rotation `R σ Rᵀ`.
2. Golden `golden_tensors.json` : `principal` (`principal(np.array(e), False)`), `facet`, `plane2D`
   (`plane2D(*e)`), `plane2DStrain`, `mohr3D`, `criteria`, `yieldLoci`, à `rel=1e-9, abs_=1e-6`
   (contraintes en Pa : 1e-6 Pa est négligeable).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E15 : tenseurs, Mohr 2D/3D, critères, lieux de plasticité`
