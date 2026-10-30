# E29 — Pages « Flambage », « Tenseurs & critères », « Hooke & jauges »

**Modèle** : Haiku · **Durée** : 75 min · **Prérequis** : E26.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 4015–4057 | `buildBucklingTab`, `loadProfileForBuckling` |
| `MecaStruct_App.m` | 4058–4089 | `buildTensorTab` |
| `MecaStruct_App.m` | 4090–4202 | `buildHookeTab`, `onHookeMode`, `applyMaterial` |
| `MecaStruct_App.m` | 1254–1495 | affichage après `computeBuckling`, `computeTensor`, `computeHooke`, `computeGauges` |
| `docs/img/10_flambage.png` … `13_jauges.png` | — | rendus MATLAB |

## `web/app_pages/flambage.py`
Saisie : matériau, E, Re, S, Iz, Iy (ou « Charger un profilé »), L, conditions aux limites (4, avec
schéma texte et coefficient L'/L), s, P appliquée. Résultats : régime (compression / Rankine / Euler) mis
en évidence, PE, PR, PC, Pcrit, Padm, verdict ; graphique `bucklingCurve` ; mode propre (tracé de
`modeShape` sur [0, L]) ; démonstration (`derivation` en `st.latex`) ; rapport.

## `web/app_pages/tenseurs.py`
Saisie : tenseur 3×3 symétrique (`st.data_editor` 3×3 en MPa, symétrisation automatique comme
`symmetrize`), Re, s, σR, facette n (et t), angle θ pour Mohr 2D. Résultats : principales, invariants,
directions, cercles de Mohr 2D (`mohr2D`) et 3D (`mohr3D`), critères (tableau Tresca / Von Mises /
Rankine), lieux de plasticité (`yieldLocus`), rapport, formules.

## `web/app_pages/hooke_jauges.py`
`st.tabs(["Loi de Hooke", "Jauges et rosettes"])` :
- Hooke : mode (isotrope 3D, contraintes planes, déformations planes, orthotrope) — les champs affichés
  changent avec le mode comme `onHookeMode` ; matériau de la base ; matrices [S] et [C] affichées
  (`st.dataframe` formaté).
- Jauges : facteur K, pont (quart, demi, complet), Vin, ε ou Vout ; rosettes 45° et 60° (3 lectures en µdéf)
  → déformations et contraintes principales, cercle de Mohr.

## Tests : `web/tests/test_pages_flambage_tenseurs_hooke.py`
`AppTest` : chaque page et chaque sous-onglet s'exécute et calcule son exemple sans exception.

## Commit
`E29 : pages Flambage, Tenseurs & critères, Hooke & jauges`
