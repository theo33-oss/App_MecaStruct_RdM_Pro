# MecaStruct RdM Pro

**MecaStruct RdM Pro** est un outil de calcul de structures (résistance des matériaux) : poutres, treillis, sections, sollicitations simples, flambage, tenseurs et critères de plasticité, loi de Hooke et jauges. Il vérifie aussi des poutres acier selon l'Eurocode 3 et produit un dossier de validation HTML par calcul.
C'est une application de bureau écrite en MATLAB (interface `uifigure`). *English summary at the bottom.*

> ⚠️ **Outil pédagogique, fourni sans aucune garantie.** Les résultats doivent être vérifiés (calcul à la main, autre logiciel, norme officielle) avant tout usage réel, notamment le dimensionnement d'une vraie pièce ou structure. Il ne remplace ni une note de calcul d'un bureau d'études, ni les normes.

## Organisation

| Dossier | Contenu |
|---|---|
| [`desktop/`](desktop/README.md) | Application MATLAB |
| [`docs/`](docs/) | Documentation, guides, normes, captures d'écran |

## État du projet

- Projet jeune, développé **seul** par Théo Brun, étudiant en Master de génie mécanique. Pas d'autre contributeur ni d'utilisateurs connus à ce jour.

## Fonctionnalités

Décrites dans [desktop/README.md](desktop/README.md) (section « Onglets ») : base de données (matériaux, profilés IPN/IPE/HEA/HEB/UPN/UAP, pressions de matage, abaques Kt), sections (analytique, intégrale, catalogue), poutres (isostatiques et hyperstatiques, déformée par 4 méthodes), treillis 2D/3D, sollicitations (traction, cisaillement, matage, torsion, flexion), flambage, tenseurs et critères (Mohr, Tresca, Von Mises), Hooke et jauges, convertisseur d'unités, formulaire rapide, vérifications Eurocode 3 et fatigue ([docs/NORMES.md](docs/NORMES.md)).

## Prérequis

- **MATLAB R2025b** (version indiquée comme testée dans le README de `desktop/` ; le code de `ValidationReport.m` exige au moins R2025a pour les diagrammes). Le lancement sans fenêtre a été vérifié en R2025b après la réorganisation.
- **Symbolic Math Toolbox** : recommandée mais facultative. Sans elle, l'application bascule sur des méthodes numériques.
- Aucune autre toolbox détectée dans le code (recherche dans les sources, pas test sur une installation sans toolbox).

## Installation et lancement

1. Cloner ou télécharger le dépôt (bouton *Code* sur GitHub, puis *Download ZIP*).
2. Ouvrir MATLAB.
3. Ouvrir le fichier `desktop/Lancer.m` et cliquer sur **Exécuter** (ou, dans la fenêtre de commande : `cd desktop` puis `Lancer`).
4. L'application s'ouvre sur l'onglet « Accueil ».

## Exemple d'utilisation

Cas de contrôle (voir [desktop/README.md](desktop/README.md)) : poutre IPE 200 en acier S235 sur deux appuis, L = 4 m, charge uniforme q = 10 kN/m. Résultats annoncés : Mmax = 20 kN·m, σmax = 102,9 MPa, flèche 9,029 mm (= 5qL⁴/(384·E·Iz) avec E = 190 GPa, valeur de la base de données). Dans l'onglet « Poutres », charger l'exemple isostatique et cliquer sur « Calculer ». Captures d'écran : [docs/img/](docs/img/) ; [guide utilisateur](docs/GUIDE_UTILISATEUR.html).

## Limites connues et niveau de validation

- Une suite de tests MATLAB existe (`desktop/tests/`, lancement : `run('desktop/tests/run_all_tests.m')`). Chaque calcul peut produire un dossier de validation qui refait les équations à la main : cela détecte des erreurs de programmation, **pas** un choix de formule ou de coefficient discutable.
- Pas de validation externe indépendante connue à ce jour [À COMPLÉTER PAR THÉO si une relecture a eu lieu].
- Limites détaillées dans [desktop/README.md](desktop/README.md) (section « Limites connues ») et [docs/NORMES.md](docs/NORMES.md). Exemples : poutre hyperstatique avec Iyz ≠ 0 non fiable ; interaction N+M de l'Eurocode 3 à vérifier dans la norme ; pas de section de classe 4.
- Les valeurs tirées de normes et de catalogues sont à vérifier sur les textes officiels avant usage.

## Feuille de route

Aucune feuille de route formelle. [À COMPLÉTER PAR THÉO]

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) et le [code de conduite](CODE_OF_CONDUCT.md). Références théoriques : [REFERENCES.md](REFERENCES.md).

## Licence

[Licence MIT](LICENSE), © 2026 Théo Brun. Les données issues de normes ou d'ouvrages tiers restent soumises à leurs propres droits (voir [REFERENCES.md](REFERENCES.md)).

---

## English summary

**MecaStruct RdM Pro** is a structural mechanics (strength of materials) tool written in MATLAB: beams, trusses, cross-sections, buckling, stress tensors and failure criteria, plus some Eurocode 3 steel checks.
The project is young and developed alone by a Master's student. The app is in `desktop/` (MATLAB R2025b; Symbolic Math Toolbox optional).
To run it: open `desktop/Lancer.m` in MATLAB and click *Run*.
**Educational use only, no warranty**: always verify results before any real-world design. Documentation is mostly in French. See [CONTRIBUTING.md](CONTRIBUTING.md). License: MIT.
