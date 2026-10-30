# E07 — Sections droites 2/2 (`geometry.py` : méthodes A, B, tabulée, cisaillement)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E06.

## Objectif
Terminer `geometry.py` : `analytical` (méthode A), `integral` (méthode B, symbolique et numérique),
`tabulated`, `compare`, `shearFactors` (k, ky, kz du cours et numériques).

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §2 « Champs de P » | liste exacte des champs de sortie |
| `GeometryEngine.m` | 162–537 | `analytical`, `integral`, `tabulated`, `compare` |
| `GeometryEngine.m` | 629–656 | `shearFactors` |
| `GeometryEngine.m` | 1288–1329 | `assembleP` (relire) |
| `GeometryEngine.m` | 1436–1627 | `shearCore`, `shearZ`, `courseShear` |
| `GeometryEngine.m` | 1737–1902 | `integrateSymbolic`, `integrateNumeric`, `innerRadius`, `integralStrings` |
| `tests/test_GeometryEngine.m` | 110–375 | formes fermées, analytique ≡ intégrale, champs, table de Huygens |
| `tests/test_GeometryEngine.m` | 488–733 | facteurs de cisaillement, profilés, tabulée, comparaison, sections composées |

## À ajouter dans `web/mecastruct/core/geometry.py`
```python
def analytical(sec: dict) -> dict      # méthode A ; champs de P + "huygens" (DataFrame : Label, S_i, zG_i, yG_i, IGz_i, IGy_i, dy_i, dz_i, SDy2, SDz2, Iz_i, Iy_i)
def integral(sec: dict, mode: str | None = None) -> dict   # méthode B ; + "integrals" (list[str] LaTeX), "methodUsed"
def tabulated(sec: dict) -> dict       # profilés du catalogue seulement, sinon MecaStructError
def compare(sec: dict) -> pd.DataFrame # index = ["S","yG","zG","Iz","Iy","Iyz","Ix","rz","ry","Wz","Wy"], colonnes Analytique, Integrale, Tabulee, EcartMax_pct
def shearFactors(sec: dict) -> dict    # kCours, kyCours, kNum, kyNum
```
Pour `compare`, regarder dans le MATLAB si la grandeur est en nom de ligne ou dans une colonne : la
reproduire de la même façon (si le MATLAB a une colonne `Grandeur`, faire une colonne `Grandeur`).

Traductions :
- `integral2(f, z1, z2, y1, y2, 'RelTol', 1e-13)` → `scipy.integrate.dblquad(lambda y, z: f(z, y), z1, z2, y1, y2, epsrel=1e-13, epsabs=0)`
  (**dblquad intègre f(y, x)** : l'ordre des arguments de la fonction est inversé). Si scipy prévient
  que la tolérance est inatteignable, passer à `epsrel=1e-12`.
- Mode symbolique : SymPy (`sympy.integrate` sur rectangles en (z, y) et disques en (r, θ)), résultats
  convertis en `float`. Si `import sympy` échoue → repli numérique, `methodUsed = "numérique"`.
- `fminbnd(g, lo, hi, optimset('TolX', t))` → `minimize_scalar(g, bounds=(lo, hi), method="bounded", options={"xatol": t})`.
- `mode` : accepter les mêmes alias que `normalizeMode` (`'numerique'`, `'numérique'`, `'num'`, `'sym'`…).

## Tests à écrire : `web/tests/test_geometry.py`
1. Porter tous les tests MATLAB des lignes 110–375 et 488–733.
   - « analytique ≡ intégrale symbolique » : `rel=1e-9` ; « ≡ intégrale numérique » : `rel=1e-6`.
2. Golden `golden_geometry.json` (paramétrer avec `case_ids`) :
   | Suffixe du cas | Appel Python | Tolérance |
   | --- | --- | --- |
   | `_analytical` | `analytical(c["entrees"])` | `rel=1e-9` |
   | `_integral_num` | `integral(e["sec"], "numerique")` | `rel=1e-6, abs_=1e-15` |
   | `_shearFactors` | `shearFactors(c["entrees"])` | `rel=1e-6` |
   | `_compare` | `compare(c["entrees"])` | `rel=1e-6` |
   | `_tabulated` | `tabulated(c["entrees"])` | `rel=1e-9` |
   - Si le cas golden contient `erreur` non vide : vérifier que Python lève `MecaStructError` avec le même
     identifiant (partie avant `" | "`). Ex. `erreur_tabulated_rectangle`.
   - Passer `ignore={"huygens"}` si l'ordre des lignes de la table de Huygens diffère, et ajouter alors un
     test séparé qui compare les **sommes** des colonnes.

## Vérifications
`python -m pytest -q` vert (les intégrations numériques peuvent prendre quelques secondes),
`python -m ruff check .` sans erreur.

## Commit
`E07 : sections 2/2 (analytique, intégrale, tabulée, comparaison, cisaillement)`
