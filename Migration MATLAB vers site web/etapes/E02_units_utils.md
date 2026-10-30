# E02 — Erreurs, utilitaires, unités et convertisseur

**Modèle** : Haiku · **Durée** : 30 min · **Prérequis** : E01.

## Objectif
Créer les briques de base utilisées par tous les moteurs : l'exception `MecaStructError`, de petits
utilitaires, et les conversions d'unités (`toSI`, `fromSI`, `unitFactor`, `convertUnits`).

## À lire (MATLAB, par plages de lignes)
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `DataManager.m` | 528–582 | `toSI`, `fromSI`, `unitFactor` |
| `DataManager.m` | 1448–1508 | `buildUnitMap`, `normalizeUnit` (table des codes d'unité) |
| `MecaStruct_App.m` | 2192–2235 | `unitCatalog`, `convertUnits` |
| `MecaStruct_App.m` | 4571–4622 | `unitTable` (catalogue du convertisseur), `expectedUnits` |
| `docs/ARCHITECTURE.md` | §1 « Méthodes statiques » | liste des codes d'unité |
| `tests/test_DataManager.m` | `grep -n "unit\|toSI\|fromSI" tests/test_DataManager.m` | tests à porter |

Données : `web/data/units.json` = `{"catalog": [...], "factors": [{"code", "factor"}...]}` (exporté de MATLAB).

## Fichiers à créer

### `web/mecastruct/core/errors.py`
```python
class MecaStructError(Exception):
    """Erreur de calcul MecaStruct, avec un identifiant identique à MATLAB (ex. 'MecaStruct:Beam:mechanism')."""
    def __init__(self, identifier: str, message: str):
        super().__init__(message)
        self.identifier = identifier
        self.message = message
    def __str__(self) -> str:
        return self.message
```

### `web/mecastruct/core/utils.py`
Fonctions (avec docstrings et annotations de type) :
- `data_path(name: str) -> Path` : chemin de `web/data/<name>` (calculé depuis `__file__`).
- `load_json(name: str)` : lit `web/data/<name>` en UTF-8 avec `json.load` ; résultat mis en cache
  (`functools.lru_cache`). Renvoyer une **copie profonde** (`copy.deepcopy`) à chaque appel pour que
  l'appelant ne modifie pas le cache.
- `as_list(x) -> list` : `None` → `[]` ; `dict` → `[x]` ; `list`/`tuple` → `list(x)`. (Le JSON MATLAB
  écrit un tableau de structures d'un seul élément comme un objet, pas une liste.)
- `as_array(x) -> np.ndarray` : `np.atleast_1d(np.asarray(x, dtype=float))` ; `None` ou `[]` → tableau vide.
- `fmt_fr(x: float, spec: str = ".4g") -> str` : `format(x, spec)` avec le point remplacé par une
  virgule ; `NaN` → `"NaN"`, `inf` → `"Inf"`, `-inf` → `"-Inf"`.
- `is_num(x) -> bool` : vrai pour un réel fini ou non (int/float/numpy), faux pour bool et None.

### `web/mecastruct/core/units.py`
- Porter `buildUnitMap` et `normalizeUnit` en un dictionnaire module `_UNIT_MAP: dict[str, float]`
  (code normalisé → facteur vers le SI) et une fonction `_normalizeUnit(unit: str) -> str`.
  Recopier la logique de normalisation exactement (espaces, `²`, `³`, `⁴`, `·`, `µ`/`u`, `°`…).
- `unitFactor(unit: str) -> float` : facteur multiplicatif vers le SI. Unité inconnue →
  `MecaStructError("MecaStruct:DataManager:unknownUnit", "Unité inconnue : « ... ».")` (reprendre
  l'identifiant et le message exacts du MATLAB).
- `toSI(val, unit)` et `fromSI(val, unit)` : vectorisés (scalaire → float, liste/tableau → `np.ndarray`).
- `unitCatalog() -> list[dict]` : lit `units.json["catalog"]` ; chaque grandeur :
  `{"name", "units": [{"label", "code"}...], "defFrom", "defTo"}`.
- `convertUnits(val, quantity: str, frm: str, to: str)` : port exact de `MecaStruct_App.convertUnits`
  (cas spécial « Température absolue » par le kelvin ; sinon `val * unitFactor(code_from) / unitFactor(code_to)`).
  Identifiants d'erreur : `MecaStruct:App:unknownQuantity`, `MecaStruct:App:unknownUnit`.
  (Le paramètre s'appelle `frm` car `from` est un mot réservé en Python.)

## Tests à écrire : `web/tests/test_units.py`
1. **Facteurs** (paramétré) : pour chaque entrée de `units.json["factors"]` dont `factor` est fini,
   `unitFactor(code) == pytest.approx(factor, rel=1e-12)`. Les entrées avec un champ `erreur` doivent
   lever `MecaStructError`.
2. **Aller-retour** : `fromSI(toSI(3.7, u), u) == approx(3.7)` pour u ∈ {mm, kN.m, MPa, GPa, deg, mm^4, kN/m}.
3. **Vectorisation** : `toSI([1, 2], "mm")` → `np.array([0.001, 0.002])`.
4. **Convertisseur** : pour chaque cas de `golden_units.json` sans erreur :
   `convertUnits(**entrees)` ≈ `sortie` à `rel=1e-12` (attention : clé `from` → argument `frm`).
   Si un cas a une erreur « Unité inconnue », le test doit vérifier que Python lève aussi `MecaStructError`.
5. Valeurs fixes : `convertUnits(1, "Longueur", "in", "mm") == approx(25.4)`.
6. Porter les autres tests d'unités trouvés dans `tests/test_DataManager.m` (voir la commande grep plus haut).
7. `MecaStructError("A:B", "msg").identifier == "A:B"` et `str(...) == "msg"`.
8. `as_list(None) == []`, `as_list({"a": 1}) == [{"a": 1}]`, `fmt_fr(1.5) == "1,5"`.

Pour lire un golden : `from tests.golden_tools import load_cases`.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E02 : erreurs, utilitaires, unités et convertisseur`
