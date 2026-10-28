# MecaStruct RdM Pro

Application MATLAB de Résistance des Matériaux et de dimensionnement des structures.
L'interface est entièrement programmatique : `uifigure`, `uigridlayout`, `uitabgroup`, sans `.mlapp`.

## Lancer l'application

Dans MATLAB (R2025b testé), depuis ce dossier :

```matlab
app = MecaStruct_App();
```

Pour la lancer sans fenêtre (scripts, tests) : `app = MecaStruct_App('Visible','off'); app.runAllExamples();`

Symbolic Math Toolbox est recommandée. Elle sert aux méthodes intégrales symboliques. Sans elle, l'application bascule automatiquement sur des méthodes numériques.

## Onglets

- **Base de données** : matériaux du cours, profilés IPN, IPE, HEA, HEB, UPN et UAP, pressions de matage, abaques Kt. Les données utilisateur peuvent être sauvegardées et rechargées.
- **Sections** : calcul analytique (Huygens), calcul intégral (symbolique ou numérique) et valeurs du catalogue, avec un tableau qui compare les trois. Affiche aussi les profils σ(y) et τ(y).
- **Poutres** : réactions (PFS, et pour l'hyperstatique Ménabréa et intégration), torseur de cohésion, équations par tronçon et énergie de déformation. La déformée est calculée par 4 méthodes : intégration, aires, Castigliano et Mohr tabulé.
- **Treillis** 2D et 3D : méthode des nœuds et méthode des rigidités.
- **Sollicitations** : traction et compression, cisaillement (Jourawski), matage (clavette, goupille), torsion, flexion déviée et flexion composée.
- **Flambage** : Euler, Rankine et compression simple, avec courbe de stabilité et modes propres.
- **Tenseurs et critères** : contraintes principales, cercles de Mohr 2D et 3D, critères de Tresca et de Von Mises, lieux de plasticité.
- **Hooke et jauges** : loi de Hooke (isotrope, contraintes planes, déformations planes, orthotrope), pont de Wheatstone, rosettes à 45° et à 60°.
- **Convertisseur** : conversion entre unités (longueur, aire, moment quadratique, force, moment, charge linéique, contrainte, module, angle, dilatation, masse volumique, déformation, température) avec les unités SI, usuelles et anglo-saxonnes (in, ft, lbf, kip, kgf, psi, ksi, bar). Il affiche la valeur dans toutes les unités, rappelle l'unité attendue dans chaque champ de saisie et peut copier le résultat. Utilisable sans interface : `MecaStruct_App.convertUnits(1, 'Longueur', 'in', 'mm')`. Les champs de saisie restent en mm, m, kN et MPa ; les résultats aussi.
- **Formulaire rapide** (panneau latéral) : fiche de formules en LaTeX pour l'onglet actif.

## Documents et validation par un tiers

- **Base de données** : boutons « Note de calcul » (`docs/NOTE_DE_CALCUL.html` : hypothèses, équations, conditions aux limites, démonstrations) et « Guide d'utilisation » (`docs/GUIDE_UTILISATEUR.html`).
- **Chaque onglet de calcul** : bouton « Dossier de validation de ce problème ». Il recalcule l'onglet puis écrit dans `validation/` un fichier HTML autonome, à envoyer à un relecteur. Un sommaire cliquable ouvre le document. Il contient :
  1. les données saisies ;
  2. les hypothèses, avec un contrôle d'applicabilité chiffré ;
  3. les équations avec les valeurs du problème, recalculées à la main (sans le solveur) puis comparées au solveur ;
  4. les tableaux de résultats ;
  5. les diagrammes ;
  6. le rapport détaillé du solveur ;
  7. les seules formules utilisées pour ce calcul ;
  8. une grille d'avis pour le relecteur.

  Sans interface : `ValidationReport.generate(app, 'Beam')`. Les clés valent `Sec`, `Beam`, `Tr`, `Tra`, `Cis`, `Tor`, `Fle`, `Fla`, `Ten`, `Hoo` et `Jau`. Les formules s'affichent avec MathJax, qui demande une connexion Internet.

## Architecture

| Fichier | Rôle |
|---|---|
| `DataManager.m` | Base de données, conversions d'unités, fiches de formules, table de Mohr, abaques Kt |
| `GeometryEngine.m` | Caractéristiques de section |
| `BeamAndTrussSolver.m` | Poutres (iso et hyperstatiques) et treillis |
| `SolicitationsEngine.m` | Contraintes, déformations, flèches |
| `BucklingEngine.m` | Flambage |
| `TensorAndCriteriaEngine.m` | Tenseurs, critères, Hooke, extensométrie |
| `PlotEngine.m` | Tous les tracés (aucun calcul mécanique) |
| `ValidationReport.m` | Dossier de validation HTML par problème (données, hypothèses, vérification à la main, diagrammes) |
| `MecaStruct_App.m` | Interface graphique |

Le contrat d'interfaces et les conventions de signe sont décrits dans `docs/ARCHITECTURE.md`.

## Tests

```matlab
run('tests/run_all_tests.m')
```

Tous les tests doivent réussir : la dernière ligne affichée par `run_all_tests` donne le bilan.
La suite complète dure environ 12 minutes, dont 10 pour l'interface et les tracés. Pour un contrôle rapide des moteurs (environ 1 à 2 minutes) : `setenv('MECASTRUCT_FAST_TESTS','1'); run('tests/run_all_tests.m')`.

## Limites connues de l'application

Elles sont aussi affichées dans l'application (ligne d'état et rapport) et dans le §2 du dossier de validation.

- **Poutre hyperstatique avec Iyz ≠ 0** (section sans axes principaux, par exemple une cornière) : les réactions sont calculées plan par plan, le couplage y–z des inconnues hyperstatiques est ignoré. Réactions, moments et contraintes ne sont pas fiables. Saisir la section dans ses axes principaux (Iyz = 0). En isostatique, Iyz ≠ 0 est traité exactement (flèches et contraintes).
- **Dossier de validation, contrainte au point le plus sollicité** : non recalculée à la main pour une section dissymétrique (T, U, L, composée) ni pour Iyz ≠ 0 ; le dossier le dit.
- **Normes** : aucune norme de dimensionnement (Eurocode…) : voir `docs/NOTE_DE_CALCUL.html`, §16.
- **Formules du dossier** : MathJax demande Internet ; hors connexion, un bandeau le signale et les équations restent en LaTeX brut.

Cas de contrôle de bout en bout :
- **Données** : poutre IPE 200 en acier S235, sur deux appuis, L = 4 m, charge uniforme q = 10 kN/m.
- **Résultats** : Mmax = 20 kN·m et σmax = 102,9 MPa. La flèche vaut 9,029 mm par les 4 méthodes, soit exactement 5qL⁴/(384·E·Iz) avec E = 190 GPa.

## Auteur et sources

Application de **Théo Brun**, basée sur son cours de Résistance des Matériaux.

| Source | Ce qui en vient |
|---|---|
| Cours de RDM de l'auteur (texte de la demande recopié dans `docs/CAHIER_DES_CHARGES.md`) | Formules, conventions de signe (torseur de cohésion = actions à droite), arbre de décision du flambage (compression simple, Rankine, Euler), valeurs des matériaux, pressions de matage, formule de la goupille |
| Théorie classique de la RDM : *Guide du calcul en mécanique* (J.-L. Fanchon, Nathan), *Mémotech*, cours de RDM des IUT GMP | Navier, Huygens, Jourawski, Euler, Castigliano, Ménabréa, intégrales de Mohr, cercles de Mohr, Tresca, Von Mises, Hooke, Bredt, Saint-Venant |
| Wikipédia : « Résistance des matériaux », « Flambage », « Cercle de Mohr », « Critère de von Mises » | Rappels et contrôles des formules standard |
| W. D. Pilkey, *Peterson's Stress Concentration Factors* (Wiley) | Ajustements des abaques Kt (plaque trouée, arbre épaulé) |
| Tables de profilés Eurocode 3 / fabricants | Dimensions et caractéristiques des IPE, IPN, HEA, HEB, UPN, UAP (Iz de l'application = Iy du catalogue) |
| MathJax (cdnjs) | Affichage des formules dans les documents HTML |

## Données issues du cours à vérifier

- **TA6V** : les valeurs de Re et Rm sont celles du cours. Les valeurs usuelles sont plutôt Re ≈ 830–880 MPa et Rm ≈ 900–950 MPa.
- **Aluminium** : le cours donne E = 90 GPa. La valeur usuelle est 72–74 GPa.
- **Plexiglas** : le cours donne G = 11 GPa. La valeur cohérente est environ 1,1 GPa.
- **Profilés UPN et UAP** : la géométrie analytique simplifiée ne tient pas compte des congés ni de la pente des ailes. L'écart avec le catalogue peut dépasser 10 %, et l'application l'affiche.
