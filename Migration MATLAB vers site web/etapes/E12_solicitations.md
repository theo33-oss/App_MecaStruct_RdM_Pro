# E12 — Sollicitations simples (`solicitations.py`)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E07 (sections), E05 (pp).

## Objectif
Porter de `SolicitationsEngine.m` : traction/compression, cisaillement, Jourawski, matage, clavette,
goupille, torsion, contraintes de flexion. (Flèches, énergie et intégrales de Mohr : E13. Flambage : E14.)

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §4 (tableau) | entrées / sorties de chaque fonction, τe et coefficient s |
| `SolicitationsEngine.m` | 1–479 | `traction`, `shear`, `jourawski`, `bearing`, `keyDesign`, `pinDesign`, `torsion`, `bendingStress` |
| `SolicitationsEngine.m` | 781–887 | `seStruct`, `seReq`, `seReqPos`, `seOpt`, `seFun`, `seTauE`, `seCastigliano` |
| `SolicitationsEngine.m` | 1257–1332 | formats (`seRx`, `seF`, `seSgn`, `seT`, `seTp`, `seTs`, `seOk`, `seIf`) |
| `tests/test_SolicitationsEngine.m` | `grep -n "^function test" tests/test_SolicitationsEngine.m` | tests à porter (ceux de ces 8 fonctions) |

## Fichier à créer : `web/mecastruct/core/solicitations.py`
```python
def traction(p: dict) -> dict
def shear(p: dict) -> dict
def jourawski(sec: dict, T: float, n: int = 201) -> dict
def bearing(p: dict) -> dict
def keyDesign(p: dict) -> dict
def pinDesign(p: dict) -> dict
def torsion(p: dict) -> dict
def bendingStress(p: dict) -> dict
```
Entrées, valeurs par défaut et sorties : **exactement** le tableau d'ARCHITECTURE.md §4.
- `traction` : `dL.analytique`, `dL.integrale`, `dL.energetique` → sous-dict `r["dL"] = {"analytique": ..., ...}`.
  Les handles optionnels `Sfun(x)`, `Nfun(x)`, `dTfun(x)` deviennent des fonctions Python vectorisées
  (`np.ndarray -> np.ndarray`). Intégrales numériques : `scipy.integrate.quad` (epsrel 1e-12).
- `torsion` : `phi = {"analytique", "integrale", "energetique"}`, `rProfile`, `tauProfile` en `np.ndarray`.
- `bendingStress` : `sigmaFun` est une fonction Python `sigmaFun(y, z)` (y, z depuis G, vectorisée) ;
  `neutralAxis = {"a", "b", "c", "points"}` (reprendre les noms exacts du MATLAB).
- Utiliser `geometry.analytical`, `geometry.widthAt`, `geometry.firstMomentAbove` pour Jourawski.

## Tests à écrire : `web/tests/test_solicitations.py`
1. Porter les tests MATLAB de ces 8 fonctions (ΔL = NL/(ES) par 3 méthodes, barre conique
   `ΔL = 4FL/(πE d1 d2)`, φ = ML/(G Ix), arbre creux, clavette, goupille, contraintes de flexion,
   Jourawski max rectangle = 1,5 T/S…).
2. Golden `golden_solicitations.json` :
   | Cas | Appel | Tolérance |
   | --- | --- | --- |
   | `traction`, `traction_thermique_Kt` | `traction(e)` | `rel=1e-9` |
   | `shear`, `shear_vonmises` | `shear(e)` | `rel=1e-12` |
   | `jourawski_*` | `jourawski(e["sec"], e["T"], e["n"])` | `rel=1e-9, abs_=1e-6` |
   | `bearing`, `keyDesign`, `pinDesign` | fonction du même nom | `rel=1e-12` |
   | `torsion_*` | `torsion(e)` | `rel=1e-9` |
   | `bending_*` | `bendingStress(e)` | `rel=1e-9, abs_=1e-6` |
   (`e = c["entrees"]`.) Les cas `mohrIntegral_*` sont pour E13.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E12 : sollicitations (traction, cisaillement, Jourawski, matage, clavette, goupille, torsion, flexion)`
