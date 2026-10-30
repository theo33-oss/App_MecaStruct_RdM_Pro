# E22 — Autres graphiques (`section_plots.py`, `other_plots.py`)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E21.

## Objectif
Porter le reste de `PlotEngine.m` avec Plotly, selon les mêmes règles qu'en E21 (une fonction renvoie un
`go.Figure`, étiquettes HTML `<sub>`, aucun calcul mécanique).

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `PlotEngine.m` | 653–847 | `section`, `sectionStress` |
| `PlotEngine.m` | 848–1195 | `bucklingCurve`, `mohr2D`, `mohr3D`, `yieldLocus` |
| `PlotEngine.m` | 1196–1509 | `truss`, `formulaSheet` (ne pas porter : remplacé par `st.latex` en E23), `ktChart`, `exportAxes` (ne pas porter) |
| `docs/img/02_sections.png`, `05_treillis.png`, `10_flambage.png`, `11_tenseurs_mohr.png` | — | rendus attendus |

## Fichiers à créer
### `web/mecastruct/plots/section_plots.py`
```python
def section(sec: dict, P: dict) -> go.Figure            # contour (geometry.outline), trous, G, axes y z, axes principaux si Iyz ≠ 0, cotes ; axes égaux
def sectionStress(sec: dict, P: dict, bend: dict, jour: dict) -> go.Figure   # 2 sous-graphes : σxx(y) et τ(y) (+ parabole de référence)
```
Contour : `fill="toself"` pour l'extérieur, trous remplis de la couleur du fond.

### `web/mecastruct/plots/other_plots.py`
```python
def bucklingCurve(curve: dict, b: dict | None = None) -> go.Figure   # palier σe, Euler, Rankine, courbe de dimensionnement, λ = 20 et λlim, point de fonctionnement
def mohr2D(r2D: dict, theta: float | None = None) -> go.Figure       # cercle, A, B, centre, rayon, σ1, σ2, angle 2θ, point de la facette ; axes égaux
def mohr3D(m3: dict, point=None) -> go.Figure                        # tricercle, zone admissible ombrée
def yieldLocus(loci: dict, point=None) -> go.Figure                  # hexagone de Tresca, ellipse de Von Mises, carré de Rankine, point
def truss(truss: dict, tsol: dict | None = None, scale: float | None = None) -> go.Figure   # traction rouge, compression bleue, nulle grise, efforts, appuis, charges, déformée amplifiée ; 3D → go.Scatter3d
def ktChart(id: str) -> go.Figure                                    # courbes Kt de kt_mohr.evalKt
```
Axes égaux : `fig.update_yaxes(scaleanchor="x", scaleratio=1)`.

## Outil de prévisualisation
Compléter `web/tools/preview_plots.py` pour écrire aussi une figure de chaque fonction (exemples de
`services.examples`).

## Tests à écrire : `web/tests/test_other_plots.py`
Pour chaque fonction, avec des sorties réelles des moteurs (exemples d'école) : pas d'erreur, renvoie un
`go.Figure`, `to_json()` fonctionne, et un contrôle numérique simple (ex. `mohr2D` : la trace du cercle a
un rayon égal à `r2D["rho"]` ; `section` : les sommets du contour correspondent à `geometry.outline`).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur. Demander à Théo d'ouvrir
`web/tools/out/*.html` et de comparer avec `docs/img/`.

## Commit
`E22 : graphiques sections, flambage, Mohr, plasticité, treillis, Kt`
