# E06 — Sections droites 1/2 (`geometry.py` : géométrie de base)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E03, E05.

## Objectif
Porter la première moitié de `GeometryEngine.m` : validation des sections, primitives (rectangles,
disques, couronnes), noyau de Huygens, formules fermées, axes principaux, constante de torsion J,
largeur b(y), moment statique Q(y), contour. La fonction publique `analytical` sera **terminée en E07**
(elle a besoin des facteurs de cisaillement).

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §2 | contrat : types de section, champs, repère O1, y depuis G |
| `GeometryEngine.m` | 1–161 | en-tête, `validateSection`, `primitives` |
| `GeometryEngine.m` | 538–628 | `widthAt`, `firstMomentAbove`, `outline` |
| `GeometryEngine.m` | 657–704 | `fromProfile`, `sectionTypes`, `hasSymbolic` |
| `GeometryEngine.m` | 705–1018 | aides de validation (`dimField`, `checkThinWalls`, `resolveProfile`, `validateComposite`, `normalizeMode`, `normalizeSide`…) |
| `GeometryEngine.m` | 1019–1216 | `buildPrims`, `primsI`, `primsU`, `addRect`, `addDisk`, `primProps`, `bboxPrims`, `refLength`, `levels`, `huygensCore`, `cleanIyz` |
| `GeometryEngine.m` | 1217–1435 | `closedForm`, `assembleP`, `principal`, `torsionConstant`, `saintVenant`, `openThinWalled` |
| `GeometryEngine.m` | 1628–1736 | `q2b`, `widthCore`, `widthSide`, `firstMomentCore`, `diskQ` |
| `GeometryEngine.m` | 1903–2167 | polygones (`rectPoly`, `circlePoly`, `shapePoly`, `primPolyshape`, `closePoly`, `orientPoly`) et textes (`typeLabel`, `describeSection`, `huygensText`, `commonText`, `fs`, `plusTxt`, `texNum`, `offStr`) |
| `tests/test_GeometryEngine.m` | 1–109 | aides des tests (sections types) |
| `tests/test_GeometryEngine.m` | 376–487, 734–818, 865–898 | tests `FirstMoment*`, `WidthAt`, `Primitives`, `Outline`, `ReportFormat`, `TypeAliases`, `Errors` |

Lire par blocs de 300 lignes au plus. Commencer par ARCHITECTURE.md §2.

## Fichier à créer : `web/mecastruct/core/geometry.py` (première partie)
Fonctions publiques de cette étape (noms identiques au MATLAB) :
```python
def validateSection(sec: dict) -> dict        # copie validée (alias de types, profilé résolu, unités SI)
def primitives(sec: dict) -> list[dict]       # kind 'rect'|'disk'|'annulus', sign ±1, z1,z2,y1,y2 | zc,yc,R,Ri, label
def widthAt(sec: dict, y, side: str = "both") -> np.ndarray | float   # y mesuré depuis G ; reprendre la valeur par défaut de side du MATLAB
def firstMomentAbove(sec: dict, y) -> np.ndarray | float
def outline(sec: dict) -> dict                # {"outer": [N×2 ndarray [z y] fermés], "holes": [...]}, repère O1
def fromProfile(p: dict) -> dict
def sectionTypes() -> list[dict]
def hasSymbolic() -> bool
```
Fonctions privées à porter maintenant (préfixe `_`, mêmes noms sans `GeometryEngine.`) : toutes les aides
listées dans le tableau, en particulier `_huygensCore(prims)`, `_closedForm(sec, core)`,
`_principal(Iz, Iy, Iyz)`, `_torsionConstant(sec, prims)`, `_huygensText(core)`, `_commonText(P)`.
`_assembleP` sera complétée en E07 (laisser la fonction **absente** pour l'instant, pas de version partielle).

Points d'attention :
- **Repères** : primitives et contours dans le repère O1 (coin bas-gauche) ; `widthAt`/`firstMomentAbove`
  prennent y **depuis G**.
- `polyshape`/`union` (contours, J des parois minces) → `shapely.geometry.Polygon` + `shapely.ops.unary_union`.
  Les cercles sont discrétisés avec **au moins 120 points** comme dans le MATLAB.
- Les profilés (`type == "profile"`) sont résolus avec `DataManager().getProfile(...)` si seuls
  `family`/`name` sont fournis (voir `resolveProfile`).
- Erreurs : mêmes identifiants (`MecaStruct:GeometryEngine:...`) et messages.

## Tests à écrire : `web/tests/test_geometry_base.py`
1. Porter les tests MATLAB listés plus haut (lignes 376–487, 734–818, 865–898), en recopiant les aides
   des lignes 1–109 en fonctions Python du fichier de test.
2. Test interne Huygens : pour le rectangle 100×200 mm, `_huygensCore(primitives(sec))` donne
   S = 0,02 m², yG = 0,1 m, Iz = b·h³/12, Iy = h·b³/12, Iyz = 0 (vérifier les noms de champs du core dans le MATLAB).
3. Golden `golden_geometry.json`, tous les cas finissant par `_widthAt` et `_firstMomentAbove` :
   ```python
   @pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_widthAt"))
   def test_golden_widthAt(cid):
       c = get_case("golden_geometry.json", cid)
       e = c["entrees"]
       assert_matches(geometry.widthAt(e["sec"], e["y"]), c["sortie"], rel=1e-9)
   ```
   (idem pour `firstMomentAbove`). Les entrées `sec` du JSON sont déjà en SI.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.
Ajouter `shapely>=2.0` à `web/requirements.txt` s'il n'y est pas, puis `pip install -r requirements-dev.txt`.

## Commit
`E06 : sections 1/2 (validation, primitives, Huygens, b(y), Q(y), contour)`
