# E24 — Pages « Base de données » et « Convertisseur »

**Modèle** : Haiku · **Durée** : 60 min · **Prérequis** : E23.

## Objectif
Pages web équivalentes aux onglets MATLAB « Base de données » et « Convertisseur ».

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 2835–3158 | `buildDatabaseTab`, `refresh*`, `onBearingSelect`, `onMaterialEdit`, `autoG`, `removeSelectedMaterial`, `onKtChartChange`, `saveDialog`, `loadDialog` |
| `MecaStruct_App.m` | 2118–2182 | `saveUserData`, `loadUserData`, `addMaterialFromForm`, `addProfileFromForm` |
| `MecaStruct_App.m` | 2365–2468 | `buildConverterTab`, `onConvQuantity`, `swapConverter`, `copyConverter`, `refreshConverter` |
| `docs/img/01_base_de_donnees.png`, `docs/img/14_convertisseur.png` | — | rendus MATLAB à imiter |

## `web/app_pages/base_de_donnees.py`
Onglets (`st.tabs`) :
1. **Matériaux** : `st.dataframe` de `dm.Materials` (E, G en GPa ; Re, Rm en MPa ; α en 10⁻⁶/°C ;
   colonnes renommées avec l'unité), filtre par catégorie (`st.multiselect`) et recherche texte.
   Formulaire `st.form` « Ajouter un matériau » (Nom, Catégorie, E, G, ν, Re, Rm, α, ρ, Note, Ajouté par) →
   `dm.addMaterial(...)` (G complété automatiquement si vide) ; bouton « Supprimer un matériau
   utilisateur » (selectbox des seuls `IsUser`).
2. **Profilés** : choix de la famille, `st.dataframe` (dimensions en mm, S en cm², I en cm⁴, W en cm³,
   comme le MATLAB l'affiche — vérifier dans `refreshProfileTable`), formulaire d'ajout.
3. **Matage** : tableau des pressions (MPa) et sélecteur liaison + conditions → Pmin, Pmax.
4. **Abaques Kt** : choix de l'abaque, champs des paramètres, `computeKt`, graphique `other_plots.ktChart`,
   description et formule (`st.latex`).
5. **Mes données** : `st.download_button` « Enregistrer mes ajouts (.json) » (`dm.exportUserData()`),
   `st.file_uploader` « Recharger mes ajouts » (`dm.importUserData`) ; message clair : les ajouts ne sont
   **pas** conservés sur le serveur, il faut télécharger le fichier.
6. **Documents** : liens de téléchargement de `docs/NOTE_DE_CALCUL.html` et `docs/GUIDE_UTILISATEUR.html`
   (lire les fichiers depuis la racine du dépôt : `Path(__file__).resolve().parents[2] / "docs"`).

## `web/app_pages/convertisseur.py`
Port de `buildConverterTab` : grandeur (`unitCatalog()`), valeur, unité de départ, unité d'arrivée,
bouton « Inverser », résultat en grand (`st.metric`), tableau de la valeur dans **toutes** les unités de
la grandeur, rappel « Les champs de saisie de l'application sont en mm, m, kN et MPa ». Copie du
résultat : `st.code(valeur)` (bouton copier intégré).

## Tests : `web/tests/test_pages_db_convert.py`
Avec `AppTest` : les deux pages s'exécutent sans exception ; sur le convertisseur, choisir
« Longueur », 1, `in` → `mm` et vérifier que le texte affiché contient `25,4` ou `25.4` ; sur la base,
ajouter un matériau via le formulaire et vérifier qu'il apparaît dans `dm.listMaterials()`.

## Vérifications
`python -m pytest -q` vert, `ruff check .` sans erreur, vérification visuelle avec `streamlit run`.

## Commit
`E24 : pages Base de données et Convertisseur`
