# E21 — Graphiques Poutres (`beam_plots.py`, Plotly)

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E20.

## Objectif
Porter de `PlotEngine.m` les tracés de poutre avec **Plotly** : schéma (appuis, charges, réactions),
diagrammes des efforts intérieurs, déformée et rotation (4 méthodes), enveloppe de charge mobile.
Aucun calcul mécanique ici : on trace les sorties des moteurs.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | §7 | rôle de chaque tracé |
| `PlotEngine.m` | 1–652 | `beamSchematic`, `movingEnvelope`, `internalForces`, `deflection` |
| `PlotEngine.m` | 1510–1777 | aides (`peTx`, `peNum`, `peTexName`, `peArrow`, `peArcArrow`, `peSupport`, `peExtremum`, `peDim`, `peWrap`, `peMk`…) |
| `docs/img/03_poutre_sollicitations.png`, `04_poutre_deformee.png` | — | rendu attendu (ouvrir les images) |

## Règles Plotly
- Chaque fonction **renvoie** un `plotly.graph_objects.Figure` (pas d'axe en entrée) :
  ```python
  def beamSchematic(model: dict, sol: dict | None = None) -> go.Figure
  def internalForces(sol: dict, comps: list[str]) -> go.Figure          # un sous-graphe par composante, axes x partagés (make_subplots(shared_xaxes=True))
  def deflection(model: dict, d: dict) -> go.Figure                    # 2 sous-graphes : α(s) (mrad) et v(s) (mm)
  def movingEnvelope(env: dict) -> go.Figure
  ```
- Échantillonnage : `pp.ppSample(sol["Ty"], 60)` (points de rupture dupliqués → sauts visibles).
- Diagrammes : aire remplie bleue pour > 0 et rouge pour < 0 (`fill="tozeroy"`, deux traces), courbe
  blanche ou noire, extrema annotés (`fig.add_annotation`) avec valeur et abscisse, comme le MATLAB.
- Unités affichées : kN, kN·m, mm, mrad, m.
- **LaTeX** : Plotly dans Streamlit n'affiche pas `$...$` de façon fiable. Écrire les noms avec le HTML
  simple accepté par Plotly : `M<sub>fz</sub>(s)`, `T<sub>y</sub>`, `α(s)`. Créer dans
  `web/mecastruct/plots/_common.py` une fonction `label(name: str) -> str` (`"Mfz"` → `"M<sub>fz</sub>"`)
  et les constantes de couleurs.
- Schéma : poutre = trait épais ; appuis dessinés par des formes (`fig.add_shape`, triangles en
  `path`, hachures de l'encastrement par petits segments) ; forces = flèches (`add_annotation` avec
  `showarrow=True, ax, ay`) ; charges réparties = suite de flèches + contour ; couples = arc + flèche ;
  réactions en vert avec valeurs (si `sol` fourni). Axe y masqué, `scaleanchor` pour garder les proportions.

## Outil de prévisualisation (pour Théo)
Créer `web/tools/preview_plots.py` : calcule 3 exemples (appui-appui uniforme, console, deux travées)
avec `services.examples` / `beam_services.computeBeam`, et écrit chaque figure en HTML dans
`web/tools/out/` (`fig.write_html(...)`). Ajouter `tools/out/` à `web/.gitignore`.

## Tests à écrire : `web/tests/test_beam_plots.py`
Pour chaque fonction, sur 3 poutres (isostatique, hyperstatique, plan xz) :
- s'exécute sans erreur et renvoie un `go.Figure` ;
- le nombre de sous-graphes de `internalForces` = nombre de composantes demandées ;
- les données y tracées de `Mfz` (en kN·m) ont pour maximum `sol["extrema"]["Mfz"]["max"] / 1e3` (rel 1e-9) ;
- `fig.to_json()` fonctionne (figure sérialisable).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur, `python tools/preview_plots.py`
produit les fichiers HTML. **Demander à Théo d'ouvrir `web/tools/out/*.html`** et de comparer avec les
captures `docs/img/03_*.png` et `04_*.png` avant de continuer.

## Commit
`E21 : graphiques Poutres (schéma, diagrammes, déformée, charge mobile)`
