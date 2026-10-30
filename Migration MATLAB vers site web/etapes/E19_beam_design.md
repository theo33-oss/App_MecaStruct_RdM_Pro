# E19 — Services Poutres 2/2 (`beam_design.py` : EC3, fatigue, profilé le plus léger, charge mobile)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E17, E18.

## Objectif
Porter les vérifications avancées de l'onglet Poutres, sans interface.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 178–282 | `useSectionForBeam`, `showBeamSection`, `applySectionPreset` (seulement la logique de recopie des propriétés) |
| `MecaStruct_App.m` | 405–705 | `applyNationalAnnex`, `checkEurocode`, `checkFatigue`, `findLightestProfile`, `restoreBeamSection` |
| `MecaStruct_App.m` | 758–924 | `computeMovingLoad`, `loadFromBeam`, `sendToTensor` |
| `docs/NORMES.md` | tout | clauses à citer |

## Fichier à créer : `web/mecastruct/services/beam_design.py`
```python
def sectionToBeamInput(saisie: dict, sec: dict, P: dict, material: dict | None) -> dict
    """= useSectionForBeam : copie S, Iz, Iy, Ix (J), Iyz, ky, kz, vy, vz (unités d'affichage) et sec."""
def checkEurocode(saisie: dict, dm: DataManager, source: str = "poutre") -> tuple[dict, pd.DataFrame]
    """source : 'poutre' (dernier calcul, tous cas à 1) ou 'enveloppe' (combinaisons). Renvoie r et le tableau de résultats."""
def checkFatigue(saisie: dict, dm: DataManager) -> tuple[dict, pd.DataFrame]
def findLightestProfile(saisie: dict, dm: DataManager, family: str, deflRatio: float | None) -> tuple[pd.DataFrame, dict | None]
def computeMovingLoad(saisie: dict, dm: DataManager) -> tuple[pd.DataFrame, dict]
def loadFromBeam(saisie_cible: dict, beam_result: dict, key: str, mode: str) -> dict
def sendToTensor(beam_result: dict) -> dict
```
- Les champs de saisie supplémentaires (γM0, γM1, Lcr, LcrF, C1, source des efforts, R, ka, kb, Rm,
  famille, rapport de flèche L/n, convoi d'essieux…) prennent **les noms des champs MATLAB**
  (`B.gM0`, `B.Lcr`, `B.C1`, `B.ecsrc`…) : les ajouter à `defaultBeamInput()` et à `BEAM_INPUT_DOC` de E18.
- `findLightestProfile` **ne modifie pas** la saisie (le MATLAB restaure la section : ici on travaille sur
  une copie `copy.deepcopy`).
- Tableaux de résultats : mêmes colonnes et mêmes libellés de lignes que le MATLAB (avec les clauses EN 1993-1-1 citées).

## Tests à écrire : `web/tests/test_beam_design.py`
1. EC3 sur IPE 300 S235, L = 6 m, appui-appui, q = −20 kN/m : comparer `r` aux appels directs de
   `design_checks.ec3Bending` / `ec3LateralTorsional` avec les mêmes efforts (cohérence).
2. Fatigue : `checkFatigue` ≈ `design_checks.goodman` avec σmax de la poutre.
3. Profilé le plus léger : pour la poutre du README (q = 10 kN/m, L = 4 m, S235, s = 1,5), la famille IPE
   donne un profilé dont `Kt·σ ≤ Re/s` et dont le profilé précédent de la famille ne passe pas.
4. Charge mobile : un essieu unique P sur appui-appui → Mfz max de l'enveloppe = P·L/4 (rel 1e-6).
5. Porter les tests de `tests/test_MecaStruct_App.m` portant sur `checkEurocode`, `checkFatigue`,
   `findLightestProfile`, `computeMovingLoad` (`grep -n "checkEurocode\|checkFatigue\|findLightest\|MovingLoad" tests/test_MecaStruct_App.m`).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E19 : services Poutres (Eurocode 3, fatigue, profilé le plus léger, charge mobile)`
