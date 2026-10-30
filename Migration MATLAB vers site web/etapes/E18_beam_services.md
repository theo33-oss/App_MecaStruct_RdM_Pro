# E18 — Services Poutres 1/2 (`beam_services.py` : saisie → modèle, calcul, combinaisons)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E13 (tous les moteurs de poutre).

## Objectif
Porter la logique de l'onglet **Poutres** de `MecaStruct_App.m` qui **ne dépend pas de l'interface** :
construire le modèle SI à partir de la saisie (unités d'affichage), lancer le calcul complet, vérifier
la résistance, résoudre les combinaisons de cas de charge, ajouter une charge rapide.
Ces fonctions seront appelées par la page Streamlit (E26-E27) et testées sans navigateur.

## La « saisie » (contrat entre la page web et les services)
Un `dict` dont les **clés sont les noms des champs MATLAB** `app.H.Beam.<nom>` (voir `buildBeamTab`,
`MecaStruct_App.m` 3255–3458) et dont les valeurs sont **dans les unités affichées** (m, GPa, MPa, mm², mm⁴,
kN, kN·m, kN/m, mm). Les tableaux sont des **listes de dicts** dont les clés sont les en-têtes de
colonnes MATLAB simplifiés. Écrire ce contrat en tête de `beam_services.py` dans une constante
documentée `BEAM_INPUT_DOC` et une fonction `defaultBeamInput() -> dict` (valeurs par défaut de l'onglet).

Exemple (à compléter avec **tous** les champs trouvés dans `buildBeamTab`) :
```python
{
  "L": 6.0, "mat": "S235", "E": 190.0, "G": 73.0769, "Re": 235.0,
  "S": 5381.0, "Iz": 8.356e7, "Iy": 6.038e6, "Ix": 155742.0, "Iyz": 0.0,
  "ky": 1.0, "kz": 1.0, "vy": 150.0, "vz": 75.0, "s": 1.5, "Kt": 1.0,
  "sup":   [{"pos": 0.0, "type": "pivot", "name": "A"}, {"pos": 6.0, "type": "appui_simple", "name": "B"}],
  "supx":  [],   # {"name", "k" (kN/m), "dx", "dy", "dz" (mm)}
  "hg":    [],   # {"pos" (m), "name"}
  "pl":    [],   # {"pos", "Fx", "Fy", "Fz" (kN), "name", "case" ('G'|'Q'|'W'|'S')}
  "pm":    [],   # {"pos", "Mx", "My", "Mz" (kN·m), "name", "case"}
  "dl":    [{"a": 0, "b": 6, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q1", "case": "G"}],
  "selfw": False, "thDT": 0.0, "thGy": 0.0, "thGz": 0.0,
  "plane": "xy", "shear": True,
  "combo": [{"name": "ELU", "gG": 1.35, "gQ": 1.5, "gW": 0.0, "gS": 0.0}],
  "section": None   # dict `sec` (GeometryEngine) si la section vient de Sections ou d'un exemple
}
```

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 3255–3482 | `buildBeamTab`, `hookBeamHistory`, `markBeamManual` (noms des champs, colonnes, valeurs par défaut) |
| `MecaStruct_App.m` | 283–404 | `computeBeam` (garder le calcul, ignorer l'affichage) |
| `MecaStruct_App.m` | 706–757 | `computeCombinations` |
| `MecaStruct_App.m` | 1907–1929 | `addQuickLoad` |
| `MecaStruct_App.m` | 3577–3804 | `readBeamModel`, `beamThermal`, `selectedComps`, `beamSectionProps`, `beamCheck` |
| `MecaStruct_App.m` | 4435–4471, 4502–4570, 4882–4934 | `caseFactor`, `beamEffortSheets`, `unreliableNote`, `plainVerdict`, `errorHint`, `effortReading`, `effortHelp`, `cellNum`, `parseNumbers`, `distCoeffs` |
| `MecaStruct_App.m` | 2236–2288 | `stressGeometry`, `parseFunction` |

## Fichier à créer : `web/mecastruct/services/beam_services.py`
```python
BEAM_INPUT_DOC: str
def defaultBeamInput() -> dict
def caseFactor(fac: dict, row: dict) -> float
def distCoeffs(type_: str, vals: str, a: float, b: float) -> np.ndarray         # kN/m, variable locale
def beamThermal(saisie: dict, dm: DataManager) -> dict                            # epsX, kv, kw
def buildBeamModel(saisie: dict, dm: DataManager, fac: dict | None = None) -> dict  # = readBeamModel, SI
def beamCheck(saisie: dict, sol: dict, dm: DataManager) -> dict                   # = beamCheck (bend, ...)
def computeBeam(saisie: dict, dm: DataManager) -> dict
    """Calcul complet de l'onglet Poutres : {"model", "sol", "defl", "energy", "check", "status", "unreliable"}."""
def computeCombinations(saisie: dict, dm: DataManager) -> pd.DataFrame          # colonnes identiques au MATLAB, ligne « Enveloppe »
def addQuickLoad(saisie: dict, kind: str, ...) -> dict                            # renvoie une copie de la saisie avec la charge ajoutée
def effortSheets(sol: dict) -> dict[str, pd.DataFrame]                            # « Enveloppe » et « Efforts » (kN, kN·m)
```
- Erreurs de saisie : `MecaStructError("MecaStruct:App:invalidInput", "<message MATLAB>")`.
- `computeBeam` renvoie aussi le texte de la ligne d'état (`status`) construit comme dans le MATLAB
  (« h = 0 (isostatique) — f max = … mm — Kt·σ … »).

## Tests à écrire : `web/tests/test_beam_services.py`
1. **Cas README** : saisie IPE 200 (prendre S, Iz, Iy dans `DataManager().getProfile("IPE", "IPE 200")`
   convertis en mm² / mm⁴), E = 190 GPa, L = 4 m, appuis pivot en 0 et appui simple en 4, charge
   uniforme −10 kN/m → `Mmax = 20 kN·m` (rel 1e-9), `σmax = 102,9 MPa` (rel 1e-3),
   flèche = 9,029 mm par les 4 méthodes (rel 1e-3).
2. `buildBeamModel` : conversions d'unités (kN → N, kN·m → N·m, mm⁴ → m⁴), cas de charge omis quand
   le coefficient vaut 0, poids propre = ρ·g·S dans le cas G, tassements en mm → m multipliés par γG.
3. `distCoeffs` : uniforme, linéaire `[(p2−p1)/(b−a), p1]`, polynomiale, erreurs.
4. `computeCombinations` : deux lignes (ELU 1,35G+1,5Q et ELS G+Q) ; vérifier la superposition
   (résultat ELU = 1,35×cas G seul + 1,5×cas Q seul pour Mfz max quand les deux ont le même signe) et la
   ligne « Enveloppe ».
5. Porter les tests numériques de `tests/test_MecaStruct_App.m` qui concernent `computeBeam` et
   `computeCombinations` (`grep -n "computeBeam\|computeCombinations\|readBeamModel" tests/test_MecaStruct_App.m`).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E18 : services Poutres (saisie → modèle, calcul complet, combinaisons, charge rapide)`
