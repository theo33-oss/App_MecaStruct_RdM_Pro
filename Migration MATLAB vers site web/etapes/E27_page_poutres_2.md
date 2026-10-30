# E27 — Page « Poutres » 2/2 (fonctions avancées)

**Modèle** : Haiku · **Durée** : 90 min · **Prérequis** : E26.

## Objectif
Ajouter à la page Poutres les sections MATLAB fermées par défaut : charge rapide, actions imposées
(ressorts, tassements, rotules, température), combinaisons, profilé le plus léger, Eurocode 3, fatigue,
charge mobile, ainsi que l'historique Annuler / Rétablir et les passerelles vers les autres pages.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `MecaStruct_App.m` | 3255–3458 | `buildBeamTab` : sections « Charge rapide », « Ressorts, tassements, rotules, température », « Combinaisons », « Profilé le plus léger », « Eurocode 3 », « Fatigue », « Charge mobile » (champs, colonnes, textes d'aide) |
| `MecaStruct_App.m` | 405–924 | logique (déjà portée en E18–E19 : ne relire que pour l'affichage) |
| `MecaStruct_App.m` | 1907–2031 | `addQuickLoad`, `pushBeamHistory`, `resetBeamHistory`, `undoBeam`, `chainEdit`, `previewBeam` |
| `README.md` | 20, 101–107 | description fonctionnelle de ces sections |

## Contenu (expanders **fermés** par défaut, comme le MATLAB)
1. **Charge rapide** : type (uniforme / triangulaire / trapèze), a, b, valeurs, cas → bouton « Ajouter »
   (`beam_services.addQuickLoad`, puis `reset_widgets("Beam")` et `st.rerun()`).
2. **Ressorts, tassements, rotules, température** : tableaux `supx` (Appui, k kN/m, dx dy dz mm) et `hg`
   (Position, Nom), ΔT, gradients selon y et z (°C), case « Poids propre ».
3. **Combinaisons** : tableau `combo` (Nom, γG, γQ, γW, γS), bouton « Calculer les combinaisons » →
   tableau résultat + onglet graphique « Combinaisons » (barres Mfz max/min par combinaison).
4. **Profilé le plus léger** : famille, flèche limite L/n (optionnelle) → tableau des essais, profilé retenu,
   bouton « Utiliser ce profilé ».
5. **Eurocode 3** : γM0, γM1 (annexe nationale), Lcr, Lcr fort, C1, source des efforts → tableau des
   vérifications avec les clauses ; rappel des points **non vérifiés** (README ligne 20).
6. **Fatigue** : R, Kf, Rm, ka, kb → résultat Goodman.
7. **Charge mobile** : tableau du convoi (position relative, charge), pas → enveloppe (`movingEnvelope`)
   dans un onglet graphique « Charge mobile ».
8. **Annuler / Rétablir** : deux boutons en haut de la colonne de gauche. Historique dans
   `st.session_state["beam_history"]` (liste de copies de la saisie, 10 au plus) et un index ; un état est
   empilé à chaque calcul et à chaque chargement d'exemple. Annuler = restaurer la saisie précédente,
   `reset_widgets("Beam")`, `st.rerun()`.
9. Passerelles : « Envoyer vers Tenseurs » (`beam_design.sendToTensor`) et « Charger depuis la poutre » dans
   Sollicitations (`beam_design.loadFromBeam`), avec `st.page_link`.

## Tests : compléter `web/tests/test_page_poutres.py`
`AppTest` : exemple chargé → « Calculer les combinaisons » → pas d'exception, tableau avec une ligne
« Enveloppe » ; Eurocode 3 sur l'exemple IPE → pas d'exception ; Annuler après chargement d'un second
exemple rétablit L du premier.

## Commit
`E27 : page Poutres (combinaisons, EC3, fatigue, profilé, charge mobile, actions imposées, historique)`
