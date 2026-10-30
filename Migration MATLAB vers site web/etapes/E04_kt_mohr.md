# E04 — Abaques Kt et table des intégrales de Mohr (`kt_mohr.py`)

**Modèle** : Haiku · **Durée** : 30 min · **Prérequis** : E03.

## Objectif
Porter `DataManager.ktCharts`, `DataManager.evalKt` et `DataManager.mohrTable`.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `DataManager.m` | 674–724 | `mohrTable` (avec les fonctions `fun`) |
| `DataManager.m` | 725–851 | `ktCharts`, `evalKt` |
| `DataManager.m` | 1322–1447 | `petersonTable`, `ktPlateParam`, `ktShaftParams`, `mohrRecord`, `mohrShapeText` |
| `DataManager.m` | 2364–2374 | `firstField` |
| `tests/test_DataManager.m` | `grep -n "Kt\|kt\|mohr\|Mohr" tests/test_DataManager.m` | tests à porter |

Données : `web/data/kt_charts.json` (le champ `table` contient déjà les lignes `[D/d, A, b]` de Peterson :
**les lire là**, ne pas recopier les nombres) et `web/data/mohr_table.json` (id, formes, LaTeX, sans `fun`).

## Fichier à créer : `web/mecastruct/core/kt_mohr.py`
```python
def ktCharts() -> list[dict]
    """Abaques Kt : id, title, params, ranges, description, paramFields, curves, table, latex (lus dans kt_charts.json)."""
def evalKt(id: str, prm) -> float | np.ndarray
    """Kt de l'abaque `id`. prm : nombre ou tableau (plaque : d/W), [r/d, D/d] ou matrice n×2 (arbres),
    ou dict (dW | d,W ; rd,Dd | r,d,D). Résultat ≥ 1. Port exact de DataManager.evalKt."""
def evalKtInfo(id: str, prm) -> tuple[float | np.ndarray, dict]
    """Comme evalKt, renvoie aussi info : id, A, b, inRange, params, report, latex."""
def mohrTable() -> list[dict]
    """Intégrales de Mohr ∫ Mi·Mj ds : id, shape1, shape2, latex (du JSON) + fun(l, a, b) (porté du MATLAB)."""
```
- `evalKt` : plaque `Kt = 3 − 3,13x + 3,66x² − 1,53x³` ; arbres : `Kt = A·(r/d)^b`, A et b interpolés
  linéairement en D/d (`np.interp`, qui prend déjà la borne la plus proche hors table, comme MATLAB —
  vérifier dans le code), puis `max(Kt, 1)`.
- Erreurs : `MecaStruct:DataManager:unknownKt`, `MecaStruct:DataManager:ktParams` (mêmes messages).
- `mohrTable` : chaque entrée du JSON reçoit sa fonction `fun` portée depuis le MATLAB (associer par `id`).
  `a`, `b` = valeurs caractéristiques des deux diagrammes (rectangle `[M]`, triangle `[M]`, trapèze
  `[Mg, Md]`, parabole `[f]`) : voir ARCHITECTURE.md §1 `mohrTable`.

## Tests à écrire : `web/tests/test_kt_mohr.py`
1. Golden `golden_datamanager.json` : `kt_plaque` → `evalKt(entrees["id"], entrees["prm"])` ≈ `sortie` ;
   `kt_arbre_epaulement_*` → pour chaque ligne `prm[k]` de `entrees["prm"]`, `evalKt(id, prm[k])` ≈
   `sortie[k]` (rel=1e-12).
2. `evalKt("plaque_trou_traction", 0) == 3`, résultat toujours ≥ 1, erreurs pour d/W = 1 et id inconnu.
3. Table de Mohr ≡ intégration numérique : pour chaque entrée, construire les deux diagrammes sur
   [0, l] avec l = 2 et des valeurs a, b quelconques, intégrer leur produit avec
   `scipy.integrate.quad` et comparer à `fun(l, a, b)` (rel=1e-9). Porter ce test depuis le MATLAB.
4. Porter les autres tests Kt / Mohr de `tests/test_DataManager.m`.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E04 : abaques Kt et table des intégrales de Mohr`
