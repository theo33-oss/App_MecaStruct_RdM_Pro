# E23 — Coquille Streamlit : navigation, briques d'interface, Accueil, Formulaire rapide

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E20, E22.

## Objectif
Mettre en place la structure de l'application web : navigation entre 10 pages, état de session,
briques réutilisables (champ numérique avec unité, tableau éditable, bloc rapport, formules), page
d'Accueil et panneau « Formulaire rapide ». Les pages de calcul sont créées vides (titre seulement).

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `README.md` | 18–31 | description des onglets |
| `MecaStruct_App.m` | 2291–2364 | `buildUI`, `buildHomeTab` (textes de l'accueil, conventions, unités) |
| `MecaStruct_App.m` | 2469–2503, 4341–4406 | `buildFormulaPanel`, `updateFormula`, `activeWorkKey`, `currentFormulaKey` (clé de formulaire par onglet) |
| `MecaStruct_App.m` | 4571–4622 | `unitTable`, `expectedUnits` |
| `MecaStruct_App.m` | 4623–4704 | `reportToHTML`, `resolveName`, `formulaLabel` |
| `docs/img/01_base_de_donnees.png` | — | aspect général |

## Fichiers à créer

### `web/streamlit_app.py` (remplace la version « Bonjour »)
```python
import streamlit as st
from mecastruct.ui import state

st.set_page_config(page_title="MecaStruct RdM Pro", page_icon="🏗️", layout="wide")
state.init()   # crée st.session_state["dm"], ["saisie"], ["res"] si absents

pages = {
    "": [st.Page("app_pages/accueil.py", title="Accueil", icon="🏠", default=True)],
    "Données": [
        st.Page("app_pages/base_de_donnees.py", title="Base de données", icon="📚"),
        st.Page("app_pages/convertisseur.py", title="Convertisseur", icon="🔁"),
    ],
    "Calculs": [
        st.Page("app_pages/sections.py", title="Sections", icon="⬛"),
        st.Page("app_pages/poutres.py", title="Poutres", icon="📏"),
        st.Page("app_pages/treillis.py", title="Treillis", icon="🔺"),
        st.Page("app_pages/sollicitations.py", title="Sollicitations", icon="🔩"),
        st.Page("app_pages/flambage.py", title="Flambage", icon="📐"),
        st.Page("app_pages/tenseurs.py", title="Tenseurs & critères", icon="⭕"),
        st.Page("app_pages/hooke_jauges.py", title="Hooke & jauges", icon="📊"),
    ],
}
pg = st.navigation(pages)
pg.run()
```

### `web/mecastruct/ui/state.py`
- `init()` : `dm` = `DataManager()` (un par session : les ajouts de l'utilisateur ne se mélangent pas
  entre visiteurs) ; `saisie` = `{tab: defaultXxxInput()}` pour les 11 clés (`Sec, Beam, Tr, Tra, Cis,
  Tor, Fle, Fla, Ten, Hoo, Jau`) ; `res` = `{}`.
- `saisie(tab) -> dict`, `set_result(tab, res)`, `result(tab)`, `reset_widgets(tab)` (supprime de
  `st.session_state` toutes les clés qui commencent par `f"{tab}."`).

### `web/mecastruct/ui/widgets.py`
```python
def num(tab, field, label, unit="", help=None, **kw) -> float
    """st.number_input lié à saisie[tab][field] ; clé de widget f"{tab}.{field}" ; libellé « label (unit) »."""
def choice(tab, field, label, options, help=None) -> str          # st.selectbox lié à la saisie
def check(tab, field, label, help=None) -> bool                     # st.checkbox lié à la saisie
def table(tab, field, columns: dict, help=None) -> list[dict]
    """st.data_editor(num_rows="dynamic") sur saisie[tab][field] (liste de dicts) ; columns = column_config
    (st.column_config.NumberColumn / SelectboxColumn / TextColumn) ; réécrit la liste de dicts dans la saisie."""
def report(lines: list[str]) -> None    # rapport MATLAB : lignes commençant par « Résultats », « Réaction »… en encadrés (st.info) ; le reste en texte
def formulas(latex: list[str]) -> None  # st.latex pour chaque formule, en retirant les $ de début et de fin
def status(text: str, ok: bool | None = None) -> None   # ligne d'état : st.success / st.warning / st.error
def error_box(err: Exception) -> None   # MecaStructError → st.error(message) + conseil (errorHint) ; autre → st.exception
def example_picker(tab) -> None         # selectbox des exemples (services.examples) + bouton « Charger l'exemple » : remplace la saisie, reset_widgets(tab), st.rerun()
```
**Piège Streamlit** : un widget avec une `key` garde sa valeur dans `st.session_state` ; quand on change
la saisie par programme (exemple, ouverture de fichier), il faut appeler `reset_widgets(tab)` **puis**
`st.rerun()`, sinon les anciennes valeurs restent affichées.

### `web/mecastruct/ui/formula_panel.py`
`formula_panel(key: str)` : dans `st.sidebar`, un `st.selectbox` des clés de `data_manager.formulaKeys()`
(libellés de `formulaLabel`) présélectionné sur la clé de la page, puis pour chaque entrée de
`formulaSheet(key)` : titre en gras, `st.latex(formule sans $)`, variables en petit (`st.caption`).

### `web/app_pages/accueil.py`
Port de `buildHomeTab` : présentation, raccourcis vers les pages (`st.page_link`), **unités de saisie**,
**conventions de signe** (repère, torseur de cohésion = actions à droite, `py < 0` = charge descendante),
encadré « Comment faire » (remplace la visite guidée : les 5 étapes d'une poutre en texte), limites
connues (README §« Limites connues »), auteur et sources (README §« Auteur et sources »).

### Pages vides
`web/app_pages/{base_de_donnees,convertisseur,sections,poutres,treillis,sollicitations,flambage,tenseurs,hooke_jauges}.py` :
chacune `st.title(...)`, `formula_panel(<clé>)` et `st.info("Page en construction (étape Exx).")`.

## Tests à écrire : `web/tests/test_ui_smoke.py`
Utiliser le testeur officiel de Streamlit :
```python
from streamlit.testing.v1 import AppTest
def test_app_starts():
    at = AppTest.from_file("streamlit_app.py", default_timeout=30).run()
    assert not at.exception
```
et un test par page : `AppTest.from_file("app_pages/accueil.py")` après avoir initialisé l'état
(`at.session_state[...]` ou appel de `state.init()` en tête de chaque page : **chaque page appelle
`state.init()`** pour pouvoir être testée seule).

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur. `streamlit run streamlit_app.py` :
la navigation fonctionne, l'Accueil est complet, le formulaire rapide s'affiche dans la barre latérale.

## Commit
`E23 : coquille Streamlit (navigation, briques d'interface, accueil, formulaire rapide)`
