# E31 — Dossier de validation HTML (`validation_report.py`)

**Modèle** : **Sonnet conseillé** · **Durée** : 2 × 90 min (deux sous-étapes, deux commits) ·
**Prérequis** : E30.

## Objectif
Porter `ValidationReport.m` : pour chaque page de calcul, un bouton « Dossier de validation de ce
problème » qui recalcule la page puis produit un **fichier HTML autonome** à envoyer à un relecteur, avec
les 8 parties du MATLAB :
1. données saisies ; 2. hypothèses avec contrôle d'applicabilité chiffré ; 3. équations avec les valeurs du
problème **recalculées à la main (sans le solveur)** puis comparées au solveur ; 4. tableaux de résultats ;
5. diagrammes ; 6. rapport détaillé du solveur ; 7. formules utilisées ; 8. grille d'avis du relecteur.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `README.md` | 33–48 | description du dossier |
| `ValidationReport.m` | 1–212 | `generate`, `handCheck`, `meta` (ignorer `findBrowser` et `toPDF`) |
| `ValidationReport.m` | 213–917 | construction HTML (`headHTML`, `section`, `inputsHTML`, `hypothesesHTML`, `handHTML`, `latexBlocks`, `resultsHTML`, `plotsHTML`, `reportHTML`, `formulasHTML`, `reviewHTML`, `extraStatements`, `hypStatements`, `autoChecks`, `extraChecks`, `addChk`, `lvl`) |
| `ValidationReport.m` | 918–1985 | contrôles à la main par onglet (`hc`, `grp`, `handRows`, `handSec`, `handTra`, `handCis`, `handTor`, `handFle`, `handFla`, `handTen`, `handHoo`, `handJau`, `handTruss`, `handBeam`, `handImposed`, `handExtras`, `handCombos`, `handEC3`, `handFatigue`, `handProfiles`, `beamPlaneRows`) |
| `ValidationReport.m` | 1986–2150 | aides (`esc`, `num`, `mj`, `mjRaw`, `b64`, `safe*`, `tableHTML`, `css`) |
| `validation/Validation_Poutre_*.html` | — | exemples de dossiers produits par MATLAB (ouvrir l'un d'eux pour voir le rendu attendu) |

## Principe Python
- Le MATLAB lit l'état de l'application (`app`). En Python, chaque fonction reçoit
  `(tab, saisie, res, dm)` : la saisie de la page, le résultat de `services` et la base.
- HTML produit avec **Jinja2** : un gabarit `web/mecastruct/services/templates/validation.html.j2`
  (CSS de `css()` recopié, sommaire cliquable, MathJax 3 depuis cdnjs comme le MATLAB, bandeau si
  hors ligne). Les graphiques Plotly sont insérés avec `fig.to_html(full_html=False, include_plotlyjs="cdn")`.
- Le fichier est proposé par `st.download_button` (nom `Validation_<Onglet>_AAAAMMJJ_HHMMSS.html`).
  Pas de PDF côté serveur : indiquer « Imprimer → Enregistrer en PDF » dans le navigateur.

## Sous-étape A — structure du dossier (commit `E31a`)
`web/mecastruct/services/validation_report.py` :
```python
def meta(key: str) -> dict
def generate(key: str, saisie: dict, res: dict, dm) -> str          # HTML complet
def handCheck(key: str, saisie: dict, res: dict, dm) -> tuple[int, int]   # (nOK, nTot) des contrôles du §3
```
Parties 1, 2, 4, 5, 6, 7, 8 complètes pour les 11 clés ; partie 3 : appel de `_handRows(key, ...)`
qui, pour cette sous-étape, ne gère que `Tra` et `Sec`.
Tests : `generate` produit un HTML qui contient les 8 titres de partie pour chaque clé (exemples d'école).

## Sous-étape B — contrôles à la main (commit `E31b`)
Porter tous les `hand*` (918–1985) : chaque contrôle recalcule la grandeur **avec la formule du cours**
(sans appeler le moteur), la compare au résultat du solveur avec la tolérance du MATLAB, et produit une
ligne `{label, latex, hand, solver, unit, ok}`.
Tests : pour chaque exemple d'école, `handCheck` renvoie `nOK == nTot` ; pour la poutre, avec
combinaisons, EC3 et fatigue calculés, idem.

## Interface
Dans `widgets.py`, `validation_button(tab)` (bouton dans la colonne de droite de chaque page de calcul,
actif seulement s'il y a un résultat) ; l'appeler sur les 9 pages de calcul.

## Commits
`E31a : dossier de validation (structure, 7 parties)` · `E31b : dossier de validation (contrôles à la main)`
