# E11 — Treillis (`truss_solver.py`)

**Modèle** : Haiku · **Durée** : 45 min · **Prérequis** : E02.

## Objectif
Porter la résolution des treillis 2D et 3D : méthode des nœuds (isostatique) et méthode des rigidités.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §3 « Treillis » | structure `truss` et champs de `tsol` |
| `BeamAndTrussSolver.m` | 258–278 | `solveTruss` (doc) |
| `BeamAndTrussSolver.m` | 2452–2759 | `btsSolveTruss`, `btsTrussProp`, `btsTrussNames`, `btsTrussReport` |
| `tests/test_BeamAndTrussSolver.m` | 739–890 | tests treillis |

## Convention d'indices (IMPORTANT)
`truss["bars"]` contient des **numéros de nœuds à partir de 1**, comme en MATLAB et comme l'utilisateur
les voit. Le solveur convertit en interne (`bars0 = np.asarray(bars, int) - 1`). Les tableaux de sortie
par nœud ou par barre sont indexés à partir de 0 en Python, mais les **noms** et le **tableau**
(`table`, colonne `Barre`, `Noeuds`) affichent des numéros à partir de 1.

## Fichier à créer : `web/mecastruct/core/truss_solver.py`
```python
def solveTruss(truss: dict) -> dict
    """Treillis articulé 2D ou 3D. Entrées SI : nodes (n×dim, m), bars (m×2, numéros à partir de 1),
    E, S (scalaires ou m valeurs), supports (n×dim booléens, True = ddl bloqué), loads (n×dim, N), names (optionnel).
    Sortie : dim, h, isostatic, mechanism, L0, N, nature, sigma, dL, reactions, displacements, Njoints,
    Nstiffness, A, methodUsed, table (DataFrame : Barre, Noeuds, L_m, N_N, Nature, Sigma_Pa, dL_m), report, latex."""
```
- `supports` du JSON peut arriver en liste de listes de booléens ou de 0/1 → `np.asarray(..., dtype=bool)`.
- `nature` : `'Traction'`, `'Compression'`, `'Nul'` avec le **seuil relatif 1e-9** du MATLAB.
- Mécanisme : reproduire exactement le comportement MATLAB (erreur `MecaStruct:...` ou drapeau
  `mechanism = True` : regarder le code et le cas golden `truss_mecanisme`).
- `Njoints` vide (`[]` → `np.empty(0)` ou `None`, comme le MATLAB renvoie `[]`) si hyperstatique.

## Tests à écrire : `web/tests/test_truss_solver.py`
1. Porter tous les tests des lignes 739–890 (`testTrussTriangleIsostatic`, `testTrussHyperstaticThreeBars`,
   `testTrussHyperstaticBraced`, `testTruss3DTripod`, `testTrussMechanism`, `testTrussInvalidInputs`).
2. Golden `golden_truss.json` (4 cas) : `assert_matches(solveTruss(c["entrees"]), c["sortie"], rel=1e-9, abs_=1e-6)`.
   Si `erreur` est non vide : vérifier que Python lève `MecaStructError` avec le même identifiant.
3. Méthode des nœuds ≡ méthode des rigidités sur le triangle (`Njoints` ≈ `Nstiffness`).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E11 : treillis 2D/3D (nœuds et rigidités)`
