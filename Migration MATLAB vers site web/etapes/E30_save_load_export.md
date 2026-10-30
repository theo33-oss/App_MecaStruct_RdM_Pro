# E30 — Enregistrer / ouvrir un problème ou un projet, exports Excel et CSV

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E27, E28, E29.

## Objectif
Reproduire « Enregistrer mon problème », « Ouvrir un problème », « Enregistrer tout le projet »,
« Ouvrir un projet » et « Exporter en tableau (.xlsx / .csv) » sur toutes les pages.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 1762–1877 | `saveProblem`, `loadProblem`, `saveProject`, `loadProject`, `exportResults`, `openProjectDialog`, `exportResultsDialog` |
| `MecaStruct_App.m` | 2588–2681 | `captureInputs`, `restoreInputs`, `resultSheets`, `confirmOverwrite` |
| `MecaStruct_App.m` | 4447–4501 | `projectKeys`, `beamEffortSheets`, `inputKey`, `matchInputs`, `inputWidgets` |
| `README.md` | 20 | comportement attendu (feuilles Excel, enveloppe, efforts) |

## Fichier à créer : `web/mecastruct/services/project_io.py`
```python
FORMAT_VERSION = 1
def problemToJson(tab: str, saisie: dict) -> str          # {"app": "MecaStruct RdM Pro", "version": 1, "onglet": tab, "saisie": ...}
def problemFromJson(text: str, tab: str | None = None) -> tuple[str, dict]   # contrôle app / onglet ; MecaStructError sinon
def projectToJson(saisies: dict[str, dict]) -> str        # toutes les clés de projectKeys
def projectFromJson(text: str) -> tuple[dict[str, dict], list[str]]   # saisies + liste des onglets non relus
def resultSheets(tab: str, res: dict) -> dict[str, pd.DataFrame]       # tableaux exportés (+ « Enveloppe » et « Efforts » pour Beam)
def toXlsx(sheets: dict[str, pd.DataFrame]) -> bytes      # une feuille par tableau (noms ≤ 31 caractères, sans []:*?/\)
def toCsvZip(sheets: dict[str, pd.DataFrame]) -> bytes    # un CSV par tableau (séparateur ;, décimale ,) dans un .zip
```
La saisie contient des `np.ndarray` ou des `DataFrame` ? Les convertir en listes (`tolist`, `to_dict("records")`)
avant `json.dumps(..., ensure_ascii=False, indent=2)`.

## Interface
Dans `web/mecastruct/ui/widgets.py`, ajouter `file_bar(tab)` : une ligne de 3 éléments en haut de la
colonne de gauche — `st.download_button` « Enregistrer mon problème (.json) », `st.file_uploader`
« Ouvrir un problème » (après lecture : remplacer la saisie, `reset_widgets(tab)`, `st.rerun()`),
`st.download_button` « Exporter en tableau » avec un choix xlsx / csv (désactivé tant qu'il n'y a pas de
résultat). L'appeler sur toutes les pages de calcul. Sur l'Accueil : « Enregistrer tout le projet » et
« Ouvrir un projet ».

## Tests : `web/tests/test_project_io.py`
Aller-retour problème et projet (saisie identique après relecture) ; fichier d'un autre onglet refusé
avec un message clair ; `toXlsx` relu par `pandas.read_excel` donne les mêmes tableaux ; la feuille
« Enveloppe » de la poutre du README contient Mfz max = 20 kN·m.

## Commit
`E30 : enregistrer / ouvrir (problème, projet) et exports xlsx / csv`
