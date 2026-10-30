# E03 — Base de données (`data_manager.py`)

**Modèle** : Haiku · **Durée** : 45 min · **Prérequis** : E02.

## Objectif
Porter `DataManager.m` (sauf abaques Kt et table de Mohr, faits en E04). Les **valeurs** viennent des
fichiers `web/data/*.json` exportés de MATLAB : on porte la **logique** (recherche par nom, ajout,
complétion E/G/ν, matage), jamais les tableaux de valeurs.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §1 | contrat de `DataManager` |
| `DataManager.m` | 1–455 | propriétés, constructeur, méthodes d'instance (matériaux, profilés, matage, sauvegarde) |
| `DataManager.m` | 471–527 | `completeIsotropic` |
| `DataManager.m` | 583–641 | `hasSymbolic`, `formulaKeys`, `formulaSheet` |
| `DataManager.m` | 1224–1321 | `buildProfileRow`, `materialRow`, `authorOf`, `prepareMaterial` |
| `DataManager.m` | 2164–2395 | aides privées : `checkFamily`, `profileIndex`, `matchName`, `matchLiaison`, `matchCondition`, `normKey`, `stripAccents`, `checkNu`… |
| `tests/test_DataManager.m` | `grep -n "^function test" tests/test_DataManager.m` | tests à porter |

**Ne pas lire** les lignes 901–1223 (`defaultMaterialsTable`, `defaultProfiles`…) : ces valeurs sont
déjà dans `web/data/materials.json` et `web/data/profiles.json`.

Données disponibles (`core.utils.load_json`) :
- `materials.json` : liste d'objets `Name, Category, E, G, nu, Re, Rm, alpha, rho, Note, IsUser, Author` (SI).
- `profiles.json` : `{"IPN": [...], "IPE": [...], ...}`, chaque profilé `Name, h, b, a, e, r, S, Iz, Iy, Wz, Wy, rz, ry, mass, c, IsUser, Author` (SI).
- `bearing_pressures.json` : liste `Liaison, Conditions, Pmin, Pmax, Note` (Pa).
- `formula_sheets.json` : `{"keys": [...], "sheets": {clé: [ {title, latex, vars}, ... ]}}`.
- `section_presets.json` : liste `{name, type, dims}` (mm).

## Fichier à créer : `web/mecastruct/core/data_manager.py`

```python
class DataManager:
    """Base de données de MecaStruct : matériaux, profilés, pressions de matage (valeurs SI)."""
    def __init__(self) -> None: ...          # charge les JSON ; Materials, Profiles, BearingPressures
    Materials: pd.DataFrame                    # mêmes colonnes que MATLAB
    Profiles: dict[str, pd.DataFrame]          # clés "IPN","IPE","HEA","HEB","UPN","UAP"
    BearingPressures: pd.DataFrame
    # matériaux
    def listMaterials(self) -> list[str]
    def getMaterial(self, name: str) -> dict   # Name, Category, E, G, nu, Re, Rm, alpha, rho, Note
    def addMaterial(self, m: dict) -> None     # complète via completeIsotropic, IsUser=True
    def removeMaterial(self, name: str) -> None
    # profilés
    def listProfileFamilies(self) -> list[str]
    def listProfiles(self, family: str) -> list[str]
    def getProfile(self, family: str, name: str) -> dict  # Family, Name, h, b, a, e, r, S, Iz, Iy, Wz, Wy, rz, ry, mass, c
    def addProfile(self, family: str, p: dict) -> None
    def removeProfile(self, family: str, name: str) -> None
    # matage
    def getBearingPressure(self, liaison: str, conditions: str) -> tuple[float, float]
    def setBearingPressure(self, liaison, conditions, pmin, pmax, note="") -> None
    def resetBearingPressures(self) -> None
    # données utilisateur (remplace saveUserData / loadUserData .mat)
    def exportUserData(self) -> dict           # {"materials": [...], "profiles": {fam: [...]}, "bearing": [...]} : seuls les ajouts (IsUser)
    def importUserData(self, data: dict) -> int  # fusionne ; renvoie le nombre d'éléments ajoutés

# fonctions de module (méthodes statiques MATLAB)
def completeIsotropic(m: dict) -> dict
def formulaKeys() -> list[str]
def formulaSheet(key: str) -> list[dict]       # [{"title", "latex", "vars"}]
def sectionPresets() -> list[dict]
def hasSymbolic() -> bool                      # True si `import sympy` réussit (mis en cache)
```

Règles :
- Reproduire **exactement** la recherche tolérante des noms (`matchName`, `normKey`, `stripAccents` :
  « s235 », « S 235 », « Acier S235 »… selon ce que fait le MATLAB) et les messages/identifiants
  d'erreur (`MecaStruct:DataManager:unknownMaterial`, `unknownProfile`, `unknownFamily`,
  `bearingNotFound`, `bearingAmbiguous`, `notUserMaterial`, `invalidNu`…).
- `getMaterial` / `getProfile` renvoient des `dict` de types Python simples (`float`, `str`), NaN conservés.
- Une colonne JSON manquante (NaN écrit `NaN`) reste `math.nan`.
- Toujours passer les listes lues dans le JSON par `as_list(...)` : MATLAB écrit une liste d'un seul
  élément comme un objet seul.
- `completeIsotropic` : port ligne à ligne (G = E/(2(1+ν)), etc., contrôle −1 < ν < 0,5, note si écart > 5 %).

## Tests à écrire : `web/tests/test_data_manager.py`
1. Porter **tous** les tests de `tests/test_DataManager.m` **sauf** : ceux de LaTeX rendu par MATLAB
   (`lastwarn`), Kt et table de Mohr (E04), et la sauvegarde `.mat` (remplacée par un test
   `exportUserData` → `importUserData` sur un nouveau `DataManager`).
2. Golden `golden_datamanager.json` :
   - cas `complete_E_nu`, `complete_E_G`, `complete_G_nu` → `completeIsotropic(entrees)` ;
   - `get_material_S235` → `DataManager().getMaterial("S235")` (comparer avec `ignore={"Note"}`) ;
   - `get_profile_IPE200` → `getProfile("IPE", "IPE 200")` ;
   - tous les cas `bearing_*` → `{"pmin", "pmax"}` de `getBearingPressure(liaison, conditions)`.
   Utiliser `assert_matches(..., rel=1e-12)`.
3. Cohérence des profilés (comme MATLAB) : pour toutes les familles, `rz ≈ sqrt(Iz/S)` et
   `ry ≈ sqrt(Iy/S)` à 2 %, `Wz ≈ Iz/(h/2)` à 2 % (sauf UPN/UAP pour `Wy`).
4. `formulaKeys()` contient les 19 clés d'ARCHITECTURE.md ; chaque `formulaSheet(k)` est une liste non vide
   de dicts ayant `title`, `latex`, `vars`.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E03 : DataManager (matériaux, profilés, matage, formulaires)`
