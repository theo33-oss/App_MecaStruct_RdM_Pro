# MecaStruct RdM Pro

Application MATLAB de Résistance des Matériaux et de dimensionnement des structures.
L'interface est entièrement programmatique : `uifigure`, `uigridlayout`, `uitabgroup`, sans `.mlapp`.

## Lancer l'application

Dans MATLAB (R2025b testé), ouvrir `Lancer.m` et cliquer sur « Exécuter » (ou taper `Lancer`) : le dossier courant est réglé tout seul. À la main, depuis ce dossier :

```matlab
app = MecaStruct_App();
```

Pour la lancer sans fenêtre (scripts, tests) : `app = MecaStruct_App('Visible','off'); app.runAllExamples();`

Symbolic Math Toolbox est recommandée. Elle sert aux méthodes intégrales symboliques. Sans elle, l'application bascule automatiquement sur des méthodes numériques.

## Onglets

- **Accueil** (onglet d'ouverture) : raccourcis vers les calculs courants, unités de saisie, conventions de signe et lien vers le guide. Le bouton « Guide » reste visible dans tous les onglets. La « Visite guidée » déroule une poutre en 5 étapes. Dans **Poutres** et **Treillis**, « Enregistrer mon problème » et « Ouvrir un problème » sauvegardent et rechargent toute la saisie (sans interface : `app.saveProblem('Beam', fichier)`, `app.loadProblem('Beam', fichier)`). Sur l'Accueil, « Enregistrer tout le projet » et « Ouvrir un projet » couvrent tous les onglets de calcul (`app.saveProject(fichier)`, `app.loadProject(fichier)`). Chaque onglet a un bouton « Exporter en tableau (.xlsx / .csv) » : Excel (une feuille par tableau) ou CSV (un fichier par tableau) ; pour Poutres, deux feuilles en plus : « Enveloppe » (max et min de N, Ty, Tz, Mt, Mfy, Mfz avec leur abscisse) et « Efforts » (valeurs le long de la poutre, en kN et kN·m). Sans interface : `app.exportResults('Beam', 'poutre.xlsx')`. Dans **Poutres** : chaque charge porte un **cas** (G permanentes, Q exploitation, W vent, S neige), la case « Poids propre » ajoute ρ·S·g au cas G, et « Calculer les combinaisons » résout chaque ligne du tableau (coefficients γG, γQ, γW, γS) puis donne l'enveloppe (onglet Combinaisons : Mfz, Ty, N, flèche, Kt·σ). « Calculer » seul additionne tous les cas avec le coefficient 1. « Chercher le profilé le plus léger » essaie une famille du catalogue avec le chargement saisi (critère Kt·σ ≤ Re/s, et flèche ≤ L/n si demandé), sans modifier la section saisie. « Vérifier selon l'Eurocode 3 » (moteur `DesignChecks.m`, clauses citées dans le tableau de résultats et dans [docs/NORMES.md](docs/NORMES.md)) contrôle la flexion autour de l'axe fort, l'effort tranchant et le déversement d'un profilé IPE, HEA, HEB, IPN ou d'une section en I : classe de section 1 à 3 (la classe 4 est refusée), Mc,Rd avec Wpl ou Wel (EN 1993-1-1 §6.2.5), Vpl,Rd (§6.2.6), réduction du moment si VEd > 0,5 Vpl,Rd (§6.2.8), déversement des laminés (§6.3.2.3, Mcr selon NCCI SN003), γM0 et γM1 réglables, fy = Re. Les efforts viennent du dernier « Calculer » ou de l'enveloppe des combinaisons (à utiliser avec une combinaison ELU). L'interaction N + M (§6.3.3, annexe B, axe fort) et le voilement de l'âme par cisaillement sont vérifiés. **Non vérifiés** : voilement sous charges concentrées, flexion déviée, ELS, classe 4 ; annexe nationale : seules γM0 et γM1 sont paramétrables. L'effort normal est traité (§6.2.4, §6.2.9, flambement §6.3.1) et le tableau de résultats avertit quand la compression et le moment coexistent. « Vérifier la fatigue » applique la droite de Goodman (vie infinie, acier) : Se = ka·kb·0,5·Rm, Kf = Kt appliqué à l'amplitude, rapport R = σmin/σmax. Sans interface : `app.computeCombinations()`, `app.findLightestProfile('IPE', 300)`, `app.checkEurocode()`, `app.checkFatigue()`. Dans **Poutres**, « Charge rapide » ajoute une charge répartie (uniforme, triangulaire, trapèze) sans écrire les valeurs à la main.
- **Base de données** : matériaux du cours, profilés IPN, IPE, HEA, HEB, UPN et UAP, pressions de matage, abaques Kt. Les données utilisateur peuvent être sauvegardées et rechargées.
- **Panneau de saisie (à gauche)** : chaque titre bleu est une section que l'on plie ou déplie d'un clic (▾ ouverte, ▸ fermée). Dans **Poutres**, les sections peu utilisées sont fermées au départ : charge rapide, combinaisons, profilé le plus léger, Eurocode 3, fatigue. Les champs masqués gardent leur valeur et les calculs les utilisent.
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

  Pour la poutre, le dossier recalcule aussi, si vous les avez lancés dans la session : les combinaisons (équilibre de chaque ligne, superposition des cas, tableau, enveloppe), l'Eurocode 3 (classes, Mc,Rd, Vpl,Rd, déversement, flambement, N + M, refaits à la main sans `DesignChecks`), la fatigue de Goodman et la cohérence du tableau « profilé le plus léger ». Ces résultats sont relancés avant l'écriture du dossier pour suivre la saisie actuelle. Les contrôles des combinaisons utilisent le solveur : ils vérifient la cohérence, pas le solveur.

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

- **Poutre hyperstatique avec Iyz ≠ 0** (section sans axes principaux, par exemple une cornière) : les réactions sont calculées plan par plan, le couplage y–z des inconnues hyperstatiques est ignoré. Réactions, moments et contraintes ne sont pas fiables. Saisir la section dans ses axes principaux (Iyz = 0). Le bouton « Calculer » demande si l'on affiche le résultat quand même ; les autres calculs (combinaisons, charge mobile, efforts lus, Eurocode 3) préfixent leur message d'état d'un avertissement. En isostatique, Iyz ≠ 0 est traité exactement (flèches et contraintes).
- **Dossier de validation, contrainte au point le plus sollicité** : non recalculée à la main pour une section dissymétrique (T, U, L, composée) ni pour Iyz ≠ 0 ; le dossier le dit.
- **Normes** : seules les vérifications Eurocode 3 de `docs/NORMES.md` sont normatives ; l'interaction N + M (annexe B) est à vérifier dans le texte de l'EN 1993-1-1.
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

## Actions imposées, charge mobile, saisie et dossier

Dans **Poutres**, la section repliée « Ressorts, tassements, rotules, température » ajoute : des **appuis élastiques** (ressort de raideur k, déplacement = −R/k), des **tassements d'appui** imposés (x, y, z, en mm), des **rotules intermédiaires** (poutre Gerber : moment de flexion nul au point choisi, pente discontinue) et des **actions thermiques** (ΔT uniforme et gradients selon y et z, α pris dans le matériau). Ces effets entrent dans la résolution des réactions (Ménabréa et intégration, qui doivent concorder) et dans les quatre méthodes de flèche. La section « Charge mobile » fait passer un convoi d'essieux sur la poutre et trace l'enveloppe de Mfz, Ty et des réactions (onglet graphique « Charge mobile »). Les positions du convoi sont une grille plus les positions critiques (essieu sur un appui, une rotule ou un point du tableau, et symétrie essieu–résultante). Sans appuis élastiques, les valeurs du tableau sont exactes en chaque point, et le moment maximal sous un essieu est exact sur poutre à deux appuis simples ; avec appuis élastiques, l'enveloppe est approchée.

Limites : tassements et température sont rangés dans le cas G (pondérés par γG dans une combinaison, comme les charges permanentes) ; pas de tassement en rotation ; ressort de translation seulement ; le dossier de validation ne recalcule pas à la main les réactions de ces cas (il contrôle l'équilibre, le déplacement des appuis et le moment nul aux rotules).

La saisie de Poutres a un **historique** (boutons Annuler / Rétablir), un **aperçu du schéma** mis à jour à chaque modification et un **clic sur le schéma** qui ajoute un appui, une force ou une rotule. L'onglet **Sections** propose des **tubes et cornières courants** (dimensions nominales, congés ignorés : écart de quelques % avec les tables) ; la base contient aussi du **bois** (C24, GL24h) et du **béton** (C25/30, C30/37) en matériau homogène élastique, sans dimensionnement du béton armé. Le **dossier de validation** s'exporte en **HTML** ou en **PDF** (Edge ou Chrome sans fenêtre ; les formules demandent Internet).

## Matériaux issus d'Euralliage

La base contient une quarantaine de matériaux tirés des fiches du site [Euralliage](https://www.euralliage.com) (métaux non ferreux) : aluminium (1050A, 3003, 5052, 5754, 5083, 6060, 6061, 6082, 2017A, 2024, 7075), cuivre, laitons (CuZn33, CuZn36Pb3, CuZn37, CuZn38Sn1, CuZn39Pb2, CuZn40Pb3, CuZn23Al4), bronzes (CuSn6, CuSn8, CuSn9P), cupro-aluminiums (CuAl9Ni3Fe2, CuAl10Ni5Fe4), CuCrZr et CuBe2. Re et Rm sont les valeurs **minimales** de la fiche (état et produit cités dans la colonne « Remarques »). Pour l'aluminium, E, G, ν, α et ρ viennent de la fiche ; pour le cuivre et ses alliages la fiche ne les donne pas : **E, ν et α sont des valeurs usuelles**, signalées comme telles. Les valeurs de Rp0,2 entre parenthèses dans la fiche (indicatives) sont reprises et signalées. L'Aluminium 2017 du cours est remplacé par l'alliage 2017A (T4). Les tableaux de ces fiches sont parfois mal alignés à la lecture : à confirmer dans la norme (EN 485-2, EN 755-2, EN 12163…) avant tout dimensionnement. Le cupro-nickel CuNi25 n'est pas repris : la fiche ne donne que des valeurs maximales.

## Données du cours corrigées

Trois valeurs du support de cours étaient incohérentes ; elles sont corrigées dans la base (la valeur d'origine est citée dans la colonne « Remarques » de chaque matériau) :

- **Aluminium 2017 et 5356** : E = 70 GPa et G = 27 GPa (le cours donnait 90 et 32 GPa) ; ν = 0,3 et α = 23e-6 /°C (EN 1999-1-1).
- **Titane TA6V** : Re = 830 MPa et Rm = 900 MPa (le cours donnait Re = 100 à 120 et Rm = 300 à 350 MPa, valeurs d'un titane non allié).
- **Plexiglas** : G = 1,1 GPa (le cours donnait 11 GPa).

Restent à vérifier :
- **Profilés UPN et UAP** : la géométrie analytique simplifiée ne tient pas compte des congés ni de la pente des ailes. L'écart avec le catalogue peut dépasser 10 %, et l'application l'affiche.
