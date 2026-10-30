# E20 — Services des autres onglets et exemples (`compute.py`, `examples.py`)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E11 à E19.

## Objectif
Pour chaque onglet hors Poutres, une fonction `computeXxx(saisie, dm)` qui lit la saisie (unités
d'affichage), convertit en SI, appelle le moteur et renvoie le résultat **et** les tableaux affichés.
Porter aussi les exemples d'école (`loadExample`) et `runAllExamples`.

## Convention de saisie
Comme en E18 : clés = noms des champs MATLAB `app.H.<Onglet>.<champ>` (ex. `app.H.Tra.N` → `saisie["N"]`),
valeurs dans les unités affichées. Pour chaque onglet, une fonction `defaultXxxInput() -> dict`.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 120–177 | `computeSection` |
| `MecaStruct_App.m` | 925–1516 | `computeTruss`, `computeTraction`, `computeShear`, `computeKey`, `computePin`, `computeTorsion`, `computeBending`, `computeBuckling`, `computeTensor`, `computeHooke`, `computeGauges`, `computeKt` |
| `MecaStruct_App.m` | 1517–1696 | `loadExample`, `runAllExamples` |
| `MecaStruct_App.m` | 3483–3576 | `loadBeamExample` |
| `MecaStruct_App.m` | 3159–3254 | `buildSectionsTab`, `onSectionType`, `onFamilyChange`, `buildSection` (champs de Sections) |
| `MecaStruct_App.m` | 3805–4202 | onglets Treillis, Sollicitations, Flambage, Tenseurs, Hooke (champs, valeurs par défaut), `readTruss`, `shearBase`, `loadProfileForBuckling`, `onHookeMode`, `applyMaterial` |
| `MecaStruct_App.m` | 4705–4812 | `relevantDims`, `sectionLabel`, `compareDisplay`, `huygensDisplay` |

## Fichiers à créer
### `web/mecastruct/services/compute.py`
```python
def defaultSectionInput() -> dict;   def computeSection(saisie, dm) -> dict
def defaultTrussInput() -> dict;     def computeTruss(saisie, dm) -> dict
def defaultTractionInput() -> dict;  def computeTraction(saisie, dm) -> dict
def defaultShearInput() -> dict;     def computeShear(saisie, dm) -> dict
def computeKey(saisie, dm) -> dict;  def computePin(saisie, dm) -> dict
def defaultTorsionInput() -> dict;   def computeTorsion(saisie, dm) -> dict
def defaultBendingInput() -> dict;   def computeBending(saisie, dm) -> dict
def defaultBucklingInput() -> dict;  def computeBuckling(saisie, dm) -> dict
def defaultTensorInput() -> dict;    def computeTensor(saisie, dm) -> dict
def defaultHookeInput() -> dict;     def computeHooke(saisie, dm) -> dict
def defaultGaugesInput() -> dict;    def computeGauges(saisie, dm) -> dict
def computeKt(id: str, prm: dict) -> dict
```
Chaque `computeXxx` renvoie `{"result": <dict du moteur>, "tables": {nom: DataFrame}, "status": str}`.
Les tableaux portent les **mêmes titres et colonnes** que l'interface MATLAB (ex. `compareDisplay`,
`huygensDisplay`, tableau des barres du treillis).

### `web/mecastruct/services/examples.py`
```python
def exampleNames(tab: str) -> list[str]                  # variantes disponibles par onglet
def loadExample(tab: str, variant: str | None = None) -> dict   # renvoie la saisie de l'exemple
def runAllExamples(dm) -> dict                            # {onglet: {"ok": bool, "message": str}}
```
`tab` ∈ `"Sec", "Beam", "Tr", "Tra", "Cis", "Tor", "Fle", "Fla", "Ten", "Hoo", "Jau"` (mêmes clés que
`ValidationReport`).

## Tests à écrire : `web/tests/test_compute.py`
1. `runAllExamples(DataManager())` : tous les onglets `ok == True`.
2. Pour chaque onglet, l'exemple par défaut donne le même résultat que l'appel direct du moteur avec les
   valeurs SI (ex. traction : `computeTraction(ex)["result"]["sigmaNom"] == solicitations.traction(p_SI)["sigmaNom"]`).
3. Porter les tests numériques de `tests/test_MecaStruct_App.m` concernant ces `computeXxx`
   et `loadExample` (`grep -n "compute\|loadExample\|runAllExamples" tests/test_MecaStruct_App.m`).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E20 : services de tous les onglets et exemples d'école`
