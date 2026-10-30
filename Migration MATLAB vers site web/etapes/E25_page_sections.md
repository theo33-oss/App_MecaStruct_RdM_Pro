# E25 — Page « Sections »

**Modèle** : Haiku · **Durée** : 45 min · **Prérequis** : E24.

## Objectif
Page web équivalente à l'onglet MATLAB « Sections ».

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 120–177 | `computeSection` |
| `MecaStruct_App.m` | 270–282 | `applySectionPreset` |
| `MecaStruct_App.m` | 2504–2587 | `makeWork`, `newAxes`, `finishWork` (organisation zone de saisie / graphiques / résultats commune à tous les onglets) |
| `MecaStruct_App.m` | 3159–3254 | `buildSectionsTab`, `onSectionType`, `onFamilyChange`, `buildSection` |
| `MecaStruct_App.m` | 4705–4812 | `relevantDims`, `sectionLabel`, `compareDisplay`, `huygensDisplay` |
| `docs/img/02_sections.png` | — | rendu MATLAB |

## Disposition commune à toutes les pages de calcul (à respecter aussi en E26–E29)
```python
state.init(); formula_panel("geometrie")
st.title("Sections droites")
gauche, droite = st.columns([1, 2], gap="large")
with gauche:
    example_picker("Sec")
    with st.expander("Type de section", expanded=True): ...
    with st.expander("Dimensions", expanded=True): ...
    calc = st.button("Calculer", type="primary", use_container_width=True)
with droite:
    if calc: try: set_result("Sec", compute.computeSection(saisie("Sec"), dm)) except Exception as e: error_box(e)
    r = result("Sec")
    if r: status(...); onglets graphiques (st.tabs) puis onglets de résultats (st.tabs)
```
Les sections MATLAB pliables (titres bleus ▾/▸) deviennent des `st.expander` (ouvert/fermé comme dans le MATLAB).

## Contenu de la page
- Saisie : type (`geometry.sectionTypes()`), dimensions **pertinentes seulement** (`relevantDims`, en mm),
  profilé du catalogue (famille + désignation), préréglages tubes/cornières (`sectionPresets`),
  section composée (tableau éditable de rectangles `z1 z2 y1 y2` et de trous, en mm), mode d'intégration.
- Graphiques : `section_plots.section` ; `section_plots.sectionStress` si une contrainte est demandée.
- Résultats : tableau de comparaison des 3 méthodes (`compareDisplay`), tableau de Huygens
  (`huygensDisplay`), facteurs de cisaillement, rapport (`widgets.report`), formules (`widgets.formulas`).
- Bouton « Utiliser cette section pour une poutre » → `beam_design.sectionToBeamInput` sur
  `saisie("Beam")`, `reset_widgets("Beam")`, message de confirmation avec `st.page_link` vers Poutres.

## Tests : `web/tests/test_page_sections.py`
`AppTest` : la page s'exécute ; cliquer sur « Calculer » avec le rectangle par défaut ne lève pas
d'exception et `result("Sec")` contient `Iz` ≈ b·h³/12 ; charger l'exemple IPE puis calculer.

## Commit
`E25 : page Sections`
