# E16 — Hooke, orthotropie, extensométrie (`hooke_gauges.py`)

**Modèle** : Haiku · **Durée** : 45 min · **Prérequis** : E15.

## Objectif
Porter la seconde moitié de `TensorAndCriteriaEngine.m` : lois de Hooke (isotrope 3D, contraintes
planes, déformations planes, orthotrope), notation de Voigt, jauges, ponts de Wheatstone, rosettes.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §6 (fin du tableau) | entrées / sorties |
| `TensorAndCriteriaEngine.m` | 717–1205 | `complianceIsotropic` … `rosette60` |
| `TensorAndCriteriaEngine.m` | 1228–1416 | `rosetteCore`, `orthoCheck`, `bridgeConfig` |
| `tests/test_TensorAndCriteriaEngine.m` | `grep -n "^function test" tests/test_TensorAndCriteriaEngine.m` | tests Hooke, Voigt, jauges, rosettes |

## Fichier à créer : `web/mecastruct/core/hooke_gauges.py`
```python
def complianceIsotropic(E, nu) -> np.ndarray      # 6×6 Voigt [xx yy zz yz xz xy], γ ingénieur
def stiffnessIsotropic(E, nu) -> np.ndarray
def hooke3D(sigV, E, nu, alpha=0, dT=0) -> np.ndarray
def hooke3DInverse(epsV, E, nu, alpha=0, dT=0) -> np.ndarray
def planeStress(sxx, syy, sxy, E, nu) -> dict
def planeStrain(exx, eyy, gxy, E, nu) -> dict
def complianceOrthotropic(c: dict) -> np.ndarray
def stiffnessOrthotropic(c: dict) -> np.ndarray
def tensorToVoigt(T, kind: str) -> np.ndarray
def voigtToTensor(v, kind: str) -> np.ndarray
def gauge(K, eps, R0=<valeur MATLAB>) -> dict
def gaugeStrain(K, dRsurR)
def wheatstone(config: str, K, Vin, eps) -> dict
def bridgeStrain(config: str, K, Vin, Vout, factor=None)
def rosette45(e1, e2, e3, E, nu) -> dict
def rosette60(e0, e60, e120, E, nu) -> dict
```
Réutiliser les aides privées de `tensors.py` (`from mecastruct.core.tensors import _fmt, _tex, ...`).
Vecteurs de Voigt : tableaux 1-D de 6 valeurs (le MATLAB utilise 6×1).

## Tests à écrire : `web/tests/test_hooke_gauges.py`
1. Porter les tests MATLAB correspondants (`S·C = I`, rosette, ponts…).
2. Golden `golden_tensors.json` : tous les cas restants (`complianceIsotropic`, `stiffnessIsotropic`,
   `hooke3D`, `hooke3DInverse`, `planeStress`, `planeStrain`, `complianceOrthotropic`,
   `stiffnessOrthotropic`, `gauge`, `wheatstone_*`, `bridgeStrain_quart`, `rosette45`, `rosette60`),
   `rel=1e-9` et `abs_ = 1e-12 × (plus grande valeur absolue attendue du cas)` : les termes nuls d'une
   matrice inversée ne valent pas exactement 0 (bruit numérique), et les déformations sont de l'ordre de
   1e-6. Écrire une petite aide `scale = np.nanmax(np.abs(np.asarray(sortie, dtype=float)))` quand la
   sortie est une matrice.
   Les entrées sous forme de liste `[a, b, c, ...]` se passent avec `f(*e)` ; les entrées sous forme
   d'objet se passent par nom (`hooke3D(e["sigV"], e["E"], e["nu"], e["alpha"], e["dT"])`).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E16 : Hooke, orthotropie, Voigt, jauges, ponts, rosettes`
