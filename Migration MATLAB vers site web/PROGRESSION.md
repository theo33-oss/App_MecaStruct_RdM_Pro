# Progression de la migration web

Cocher `[x]` à la fin de chaque étape (tests verts + commit) et ajouter 1 à 3 lignes de notes dessous.

## Phase 0 — Préparation (Théo)
- [x] E00 — Dépôt GitHub, Python, exports JSON depuis MATLAB
  Dépôt privé `App_MecaStruct_RdM_Pro` sur GitHub. Python 3.12.10 installé. 8 JSON de base et 9 fichiers golden (209 cas) exportés. Erreurs attendues seulement : erreur_tabulated_rectangle, truss_mecanisme.

## Phase 1 — Squelette
- [x] E01 — Dossier web/, dépendances, pytest, ruff, CI, page « Bonjour »
  Modèles copiés sans modification (dont tests.yml à la racine, non testé sur GitHub : pas de push). venv Python 3.12.10 : pytest 10 passed (0 skip), ruff « All checks passed! », Streamlit health ok et page « MecaStruct RdM Pro » vue. Étape E00 vérifiée : 8 JSON et 9 golden présents.

## Phase 2 — Moteurs de calcul
- [x] E02 — errors.py, utils.py, units.py (+ convertisseur)
  Ports de buildUnitMap / normalizeUnit (table recopiée, contrôlée contre units.json par les tests), toSI / fromSI rejettent les textes (invalidValue) comme MATLAB.
  pytest : 167 passed (10 anciens + 157 nouveaux) ; ruff check et ruff format --check verts.
- [x] E03 — data_manager.py
  Port de DataManager.m sans abaques Kt ni table de Mohr (E04). Sauvegarde .mat remplacée par exportUserData / importUserData (JSON) ; getMaterial et getProfile renvoient aussi IsUser et Author (ARCHITECTURE §1).
  pytest 201 passed (34 nouveaux) ; ruff check et ruff format --check verts. Tests d'unités déjà dans test_units.py (E02), testDefaultUserFilePath sans objet en Python.
- [x] E04 — kt_mohr.py
  Port de ktCharts, evalKt, evalKtInfo, mohrTable ; abaques et table lus dans kt_charts.json et mohr_table.json. Les 10 couples inversés de Mohr reprennent la forme directe, a et b échangés.
  pytest 217 passed (16 nouveaux, dont 4 cas golden) ; ruff check et ruff format --check verts. Test LaTeX de MATLAB porté pour Kt et Mohr seulement (chaînes $…$, commandes interdites).
- [x] E05 — pp.py
  Port de ppEval, ppSample, ppIntegrate, ppDerivative, ppAdd, ppScale, ppMultiply, ppRefine, ppIntegral, ppZero, ppConst, poly2latex, poly2str ; PP en dataclass, asPP accepte le dict JSON. hasSymbolic réexporté de data_manager.
  Aides privées _tol, _segIndex, _mergeBreaks, _polyAdd, _pad, _shiftPoly, _polyStr, _num, _texNum prêtes pour E08 à E13.
  pytest 225 passed (8 nouveaux : testPp*, testPoly2*, testHasSymbolic portés + aides) ; ruff check et ruff format --check verts.
- [x] E06 — geometry.py 1/2
  Port de validateSection, primitives, widthAt, firstMomentAbove, outline, fromProfile, sectionTypes, hasSymbolic et des aides privées (Huygens, formules fermées, J, b(y), Q(y), contours, textes). _assembleP absente (E07). Écarts : widthAt prend side = 'max' par défaut (valeur MATLAB, pas « both » de la fiche) ; un profilé donné seulement par famille et nom est complété depuis le catalogue (demandé par la fiche, absent de MATLAB).
  pytest 304 passed (79 nouveaux : tests portés, golden widthAt et firstMomentAbove, cohérence Huygens) ; ruff check et ruff format --check verts. Reportés à E07 : testReportFormat et erreurs de integral.
- [x] E07 — geometry.py 2/2
  Port de analytical, integral (SymPy, repli dblquad), tabulated, compare, shearFactors, _assembleP, cisaillement et intégrales LaTeX. Écarts : seuil de mise à zéro de yAtMax 1e-9·L (MATLAB) ; intégrales numériques en coordonnées x/L avec epsabs 1e-15 ; rendu LaTeX de testLatexValid non porté.
  pytest 452 passed (148 nouveaux dans test_geometry.py) ; ruff check et ruff format --check verts. Golden shear.yAtMax comparé avec abs 1e-9 m (maximum de Q/b plat en y = 0, cote connue au bruit d'arrondi près), décision de Théo (option a).
- [x] E08 — beam_solver.py 1/3 (modèle, sous-problèmes, coupures)
  Sous-étape A faite (commit E08a) : _beamOpts, _reqPos, _optNum, _optName, _getArr, _normType, _normalizeModel, _prepDist, _gauss, _gaussData, _matIntegrate, _matEval, _cleanMat, _matToPP, _matMaxAbs, _cutBend dans beam_solver.py ; 14 tests dans test_beam_solver.py (pytest 466 passed, ruff verts). Ajout hors liste de la fiche : _gaussVals (même bloc MATLAB, utile à B) ; les erreurs de testInvalidInputs passent par _normalizeModel et _beamOpts (solveBeam arrive en B).
  Sous-étape B faite (commit E08b) : _buildSubs, _addCompat, _makeUnk, _baseOrder, _solveSub, _cleanReactions, _loadMoments, _reactionDiff, _menabrea, _bendDisp, _condText, _jumps, _extrema, _reactionStruct, _actions et solveBeam ; stubs `_integration` (lève NotImplementedError("E09"), à porter en E09) et `_provisoire_E10` (à supprimer en E10). pytest 477 passed (11 nouveaux), ruff verts. Écarts : le cas dégénéré de _solveSub (liaisons insuffisantes avec h > 0) lève toujours E09, car MATLAB y appelle btsIntegration sans condition sur hyperMethod ; menabrea et integration valent {} quand vides.
  Pour C : le golden bi_encastree_uniforme donne extrema.Mfz.sMin = 6 (MATLAB) contre 0 (Python) : Mfz(0) = Mfz(L) = −12 000 N·m exactement, départagé par le bruit d'arrondi (1e-15 relatif) ; même phénomène sur gerber_hyperstatique (E09). Non corrigeable dans le code sans trahir MATLAB : à trancher avec Théo (ne pas affaiblir les tolérances).
  Sous-étape C faite (commit E08c) : 14 tests d'école de MATLAB portés (hors methodCheck, hyperCheck, equations, reactionsIntegration : E09 et E10) et 13 cas golden `*_solveBeam` hors gerber, appui_elastique, tassement, thermique (E09), avec rel 1e-9 et abs 1e-6. Cas sMin/sMax tranché par Théo : si l'abscisse de Python diffère du golden, on vérifie que la valeur de la fonction à cette abscisse égale l'extremum du golden à rel 1e-9 (test seulement, golden et autres tolérances inchangés) ; un seul cas concerné, bi_encastree_uniforme (Mfz.sMin : 6 en MATLAB, 0 en Python). gerber_hyperstatique reste à traiter en E09.
- [x] E09 — beam_solver.py 2/3 (hyperstatique)
  Port de _integration (btsIntegration) : le stub E09 est supprimé, 'integration' et 'both' fonctionnent, hyperCheck et reactionsIntegration renseignés ; ressorts, tassements, rotules et thermique étaient déjà pris en compte dans les deux méthodes (E08), seuls des tests ont été ajoutés. Tests de E08c paramétrés (None, OPTS) ; 7 tests MATLAB portés (flèches de SolicitationsEngine en commentaire `# E13`) ; les 18 cas golden `*_solveBeam` passent avec les options par défaut (gerber_hyperstatique : repli sMin/sMax décidé par Théo, comme bi_encastree_uniforme). pytest 532 passed ; ruff verts.
  Écart à la fiche : le golden thermique_bi_encastree donne lui-même hyperCheck = 1,936 (sans charge, btsReactionDiff compare du bruit d'arrondi à une échelle nulle ; réactions identiques). Python reproduit cette valeur ; pour ce seul cas le test remplace « hyperCheck < 1e-9 » par l'accord des deux méthodes à 1e-9 de la plus grande réaction (HYPERCHECK_BRUIT, code du test). Golden et tolérances inchangés.
- [x] E10 — beam_solver.py 3/3 (méthode intégrale, extrema, équations, rapport)
  Port de btsIntegralMethod (numérique par np.polyint ; symbolique par SymPy exact, même résultat), methodCheck, internalIntegral (6 pp + methodUsed, closure), equations, btsBeamReport découpé en aides `_rep*`. `_provisoire_E10` supprimé ; useSymbolic vaut faux par défaut (fiche), test_options adapté.
  pytest 537 passed ; ruff check et ruff format --check verts. Golden et tolérances inchangés (seules sMin/sMax restent ignorés dans le test golden) ; golden_beam.json ne contient ni internalIntegral ni equations : coupures ≡ intégrale est testé par test_coupures_egales_integrale.
  Rapports de appui_appui_uniforme et bi_encastree_uniforme relus : en français ; Ménabréa ≡ intégration à 5e-17 sur le second.
- [x] E11 — truss_solver.py
  Port de solveTruss (btsSolveTruss, btsTrussProp, btsTrussNames, btsTrussReport) : nœuds et rigidités, 2D/3D, mécanisme. _linEq et _joinNums repris de beam_solver, _num et _texNum de pp. Écarts : lsqminnorm → np.linalg.lstsq ; rcond(Kff) < 1e-14 approché par cond2(Kff) > 1e14.
  pytest 547 passed (10 nouveaux : 4 cas golden truss dont l'erreur de mécanisme, portage des tests 739–890) ; ruff check et ruff format --check verts. Golden et tolérances inchangés.
- [x] E12 — solicitations.py
  Port de traction, shear, jourawski, bearing, keyDesign, pinDesign, torsion, bendingStress et seCastigliano (quad epsrel 1e-12, ∂U/∂F par différence centrée). Écarts : methodUsed = 'numérique' (MATLAB écrit 'symbolique' quand SymPy est là ; golden ignore ce champ) ; checkLatex (rendu) remplacé par ASCII + accolades équilibrées ; seTp, seIf, seRx, seGauss reportés à E13.
  pytest 579 passed (32 nouveaux : tests portés des 8 fonctions MATLAB + 14 cas golden) ; ruff check verts. Golden et tolérances inchangés.
- [x] E13 — deflection.py
  Port de deflection (4 méthodes), strainEnergy et mohrIntegral dans deflection.py ; buckling(p) délègue à buckling.analyze (E14, testBucklingDelegation reporté). 50 tests dans test_deflection.py, # E13 de test_beam_solver.py réactivés ; pytest 629 passed, ruff verts. Écarts : sol optionnel, a et b optionnels pour mohrIntegral, Gauss par numpy leggauss.
  Golden de flèche : 3 exceptions de test décidées par Théo (BLOCAGES.md, E13), limitées à test_golden_deflection ; appui_elastique : castigliano et mohr vérifiés par 3 contrôles au lieu d'une comparaison terme à terme.
- [x] E14 — buckling.py
  Port de BucklingEngine : analyze, stabilityCurve, listConditions, effectiveLengthCoefficient, hasSymbolic (réexporté de data_manager), modes propres, équation caractéristique, dérivation, rapport et LaTeX ; testBucklingDelegation porté. Chemin symbolique (dsolve, vpasolve) non porté : methodUsed = 'numérique' (fiche E14).
  Golden : 'symbolic' et 'determinant' (sorties du chemin symbolique) exclus de la comparaison (SYMBOLIQUE dans test_buckling.py). fdResidual de encastre-encastre : écart 8,5e-13 avec MATLAB (bruit d'arrondi), passe sous le plancher abs 1e-12, tolérances inchangées.
  pytest 665 passed (36 nouveaux, dont 7 golden) ; ruff check et ruff format --check verts. Rendu LaTeX non testé (contrôles de texte seulement, comme E04).
- [x] E15 — tensors.py
  Port de principal, facet, plane2D, plane2DStrain, mohr3D, criteria, yieldLoci et des aides de formats (_g et _texNum réutilisés de pp, comme truss_solver). Écarts : useSymbolic=None vaut numérique (PLAN §4.1) et le chemin SymPy n'est pris que si True ; _voigtToTensor ne traite que les contraintes (voigtToTensor complet en E16) ; « Symbolic Math Toolbox » devient « SymPy » dans les textes.
  pytest 685 passed (20 nouveaux : 12 tests MATLAB portés, 7 cas golden, rapports et LaTeX) ; ruff check et ruff format --check verts. Tests aléatoires en default_rng(17) (pas mt19937ar). Golden et tolérances inchangés.
- [x] E16 — hooke_gauges.py
  Port de complianceIsotropic à rosette60 (Hooke isotrope et 3D, états plans, orthotropie, Voigt, jauges, Wheatstone, rosettes), avec les aides de tensors.py. Écarts : testRenduLatex non porté (rendu MATLAB) ; testErreursEntrees réduit aux lignes E16 ; voigtToTensor complète le _voigtToTensor de E15 (kind, 3 composantes).
  pytest 712 passed (27 nouveaux : 12 tests MATLAB portés, 15 cas golden) ; ruff check et ruff format --check verts. Golden : rel = 1e-9 et abs_ par champ (code de test seulement, autorisation de Théo) : champ non nul = 1e-12 × son propre max ; champ nul en théorie (max < 1e-9 × l'échelle de sa famille dans le cas) ou exactement nul = 1e-12 × l'échelle de la famille (déformation, contrainte, souplesse, raideur) ; angle = 1e-12 × son échelle propre ; checkResidual = 1e-9. Classement : angle par nom, puis strain2D (déformation) ou stress2D (contrainte), puis nom seul.
  Champs reclassés nuls en théorie ou exactement nuls : stress2D.tau des deux rosettes (bruit d'arrondi, ±3,7e-9 et ±1,9e-9), strain2D.tau, strain2D.gammaHalf, strain2D.gamma (exactement 0), planeStrain.ezz (exactement 0). Tolérances proches de 1e-15 pour les déformations, 1,3e-4 à 1,4e-4 pour les stress2D.tau (échelle des contraintes, 1e8 Pa).
  Les règles par cas (Qred 2,3e11 rendait exx et ezz vides) et par bloc (le dictionnaire mêlait contraintes et déformations) étaient trop larges ; la règle par champ est en place.
- [x] E17 — design_checks.py
  Port de ibeamDims, classify, ec3Bending, ec3LateralTorsional, ec3FlexuralBuckling, ec3AxialBending, ec3Interaction, ec3WebShear et goodman. Écarts : messages class4 et unsupportedSteel avec virgule décimale (fmt_fr) ; governing reste 1 ou 2 comme MATLAB (golden) ; pas de report ni latex (MATLAB n'en a pas) ; d de ec3AxialBending pris du cas ibeamDims (absent des entrées golden).
  pytest 737 passed (25 nouveaux : 13 tests MATLAB portés, 12 cas golden à rel 1e-9, aucune tolérance changée) ; ruff check et ruff format --check verts.

## Phase 3 — Services
- [x] E18 — beam_services.py
  Port de readBeamModel, beamThermal, beamCheck, computeBeam, computeCombinations, addQuickLoad, caseFactor, distCoeffs, beamEffortSheets. Écarts : defaultBeamInput() a IPE 300, S235, L = 6 m, avec la case tranchant décochée (uicheckbox MATLAB par défaut ; l'exemple du menu la coche) ; computeCombinations attrape toute exception (MecaStructError : « erreur : … » ; autre : « Erreur de calcul (type) : … » et trace dans le log) ; beamCheck garde dm (signature de la fiche) sans l'utiliser ; BEAM_INPUT_DOC ne couvre que les champs de E18 (EC3, fatigue, charge mobile : E19-E20).
  Décision de Théo : le tranchant suit MATLAB. Castigliano avec shear = True donne 9,296 mm (+3 %) ; intégration, aires et Mohr ne changent pas (9,029 mm). Le cas README garde shear = False explicite pour retrouver 9,029 mm par les 4 méthodes.
  pytest 759 passed (22 nouveaux dans test_beam_services.py : cas README, conversions, distCoeffs, combinaisons, Gerber, tassement, charge rapide, poids propre, tranchant, erreur numérique isolée) ; ruff check et ruff format --check verts.
- [x] E19 — beam_design.py
  Port de useSectionForBeam, checkEurocode (poutre ou enveloppe), checkFatigue, findLightestProfile, computeMovingLoad, loadFromBeam, sendToTensor ; champs E19 ajoutés à defaultBeamInput (noms MATLAB). Écarts : clé secTabulated ajoutée à la saisie (la section d'un profilé reste dans section pour l'Eurocode, sans que beamCheck utilise le contour) ; findLightestProfile renvoie le dict du profilé (getProfile) ; loadFromBeam renvoie une copie de la saisie cible, sans message d'état ni avertissement de section ; applyNationalAnnex (UI) non porté, à faire en E27.
  pytest 767 passed (8 nouveaux dans test_beam_design.py : EC3 cohérent, Goodman, profilé le plus léger, flèche L/1000, charge mobile, Eurocode et fatigue portés de MATLAB) ; ruff check et ruff format --check verts.
- [x] E20 — compute.py + examples.py
  Port des computeXxx (sections, treillis, traction, cisaillement, clavette, goupille, torsion, flexion, flambage, tenseurs, Hooke, jauges, Kt), de loadExample et de runAllExamples (30 étapes, toutes OK). Écarts : Cisaillement et Flexion lisent la section de l'onglet Sections dans saisie["section"] ; défauts = exemples chargés au démarrage par MATLAB ; l'exemple Poutres garde la section IPE 300 (secTabulated) pour l'Eurocode ; tableaux titrés comme les onglets ; texte du rapport dans result["rapport"].
  pytest 805 passed (38 nouveaux dans test_compute.py) ; ruff check et ruff format --check verts. Tests portés de testSectionRectangle, testTruss, testTractionValues, testTorsionAndBuckling, testHookeAndGauges, testParseFunction. Golden et tolérances inchangés.

## Phase 4 — Graphiques
- [x] E21 — beam_plots.py
  Port de PlotEngine (beamSchematic, internalForces, deflection, movingEnvelope) en Plotly, helpers dans _common.py. Écarts : une seule légende par figure (MATLAB en a une par axe) ; flèches de taille fixe ; libellés en HTML (sous-indices) et point décimal ; extrema exacts ajoutés aux points tracés (200 par tronçon en efforts, grille fine pour l'intégration de la déformée) ; légende du schéma à droite.
  pytest 820 passed (15 nouveaux dans test_beam_plots.py) ; ruff check et ruff format --check verts. Aperçus : python tools/preview_plots.py, validés par Théo contre docs/img/03 et 04.
- [x] E22 — section_plots.py + other_plots.py
  Port de section, sectionStress, bucklingCurve, mohr2D, mohr3D, yieldLocus, truss (2D et 3D), ktChart ; _support déplacé de beam_plots vers _common (support). Écarts : sectionStress ne trace pas le contour (le MATLAB non plus) ; vecteurs 3D sans pointe ; zone admissible 3D = disque moins disques blancs. formulaSheet et exportAxes non portés (fiche).
  pytest 840 passed (20 nouveaux) ; ruff check verts. Aperçus : python tools/preview_plots.py (21 HTML dans web/tools/out/), rendu à valider par Théo contre docs/img/02, 05, 10, 11.

## Phase 5 — Interface
- [x] E23 — Coquille Streamlit, Accueil, Formulaire rapide
  streamlit_app.py (10 pages par st.navigation), ui/state.py (init = loadExample de chaque onglet, comme au démarrage MATLAB), ui/widgets.py, ui/formula_panel.py, page Accueil (textes de buildHomeTab, visite en encadré), 9 pages vides. Écarts : formula_panel(None) ne dessine rien (Accueil, Convertisseur) ; test de l'Accueil par test_app_starts (st.page_link exige la navigation) ; applyNationalAnnex non porté (fiche E27).
  pytest 850 passed (10 nouveaux, test_ui_smoke.py) ; ruff check verts ; navigation vérifiée par AppTest (pages Poutres, Sections, Flambage).
- [x] E24 — Base de données + Convertisseur
  Page Base de données : matériaux (filtre, formulaire, suppression des ajouts), profilés (cm², cm⁴, cm³ comme refreshProfileTable), matage, abaques Kt (valeurs initiales de loadExample : arbre de flexion, r/d 0,1, D/d 1,5), données utilisateur en JSON, documents docs/. Convertisseur : catalogue units.json, unités par défaut (defFrom/defTo), Inverser, tableaux MATLAB. Écarts : données utilisateur en JSON et non .mat ; les abaques gardent leurs paramètres par abaque.
  pytest 854 passed (4 nouveaux, test_pages_db_convert.py) ; ruff check verts. Vérification visuelle avec streamlit run non faite.
- [x] E25 — Sections
  Page Sections (disposition commune, exemple IPE, préréglages, dimensions pertinentes, transfert vers Poutres) ; section composée : tableaux rects et holes, pris en charge dans compute._sectionFromSaisie. Écarts : MATLAB exclut le composite de sa liste de types (buildSectionsTab), la fiche le demande : implémenté d'après la fiche. Chargement des efforts depuis la poutre reporté à E26 (dépend des résultats Poutres) ; le transfert n'alimente pas Flambage (page non encore portée).
  pytest 858 passed (4 nouveaux, test_page_sections.py) ; ruff check verts. Rendu visuel avec streamlit run non vérifié.
- [x] E26 — Poutres 1/2
  Page Poutres (exemples, matériau → E, G, Re, section avec import depuis Sections, tableaux appuis / forces / couples / charges réparties, options, Calculer, schéma d'aperçu avant calcul, diagrammes, déformée, équations par tronçon, 6 onglets de résultats). computeBeam renvoie aussi rapport et tables (beamReport, beamTables). Écarts : confirmation « résultat non fiable » remplacée par un avertissement dans l'état ; ressorts, tassements, rotules, température et poids propre laissés à E27 (non éditables ici, mais pris en compte par les exemples). Report de E25 fait ici (hors fiche) : « Efforts en s » et « Efforts au point critique » dans la page Sections, avec le champ s0.
  pytest 862 passed (4 nouveaux : 3 test_page_poutres.py, 1 test_page_sections.py) ; ruff check verts. Rendu visuel avec streamlit run non vérifié.
- [x] E27 — Poutres 2/2
  Page Poutres complétée : charge rapide, ressorts / tassements / rotules / température / poids propre (éditables, déjà pris en compte par le calcul), combinaisons (+ graphique Mfz max/min), charge mobile, profilé le plus léger (+ « Utiliser ce profilé »), Eurocode 3 avec annexe nationale (applyNationalAnnex : γM0 = γM1 = 1 pour EN et FR), fatigue, Annuler / Rétablir (10 états, session_state), envoi vers Tenseurs. Écarts : charge mobile et fatigue suivent les champs MATLAB (mvP, mvE, mvN, mvFixed ; R, ka, kb, Kf = Kt, Rm du matériau), pas le tableau « position relative / charge » ni les champs Kf / Rm de la fiche ; « Charger depuis la poutre » dans Sollicitations reste à E28 (page non portée), lien remplacé par une légende ; la page Tenseurs ne calcule pas encore (E29) : la saisie est remplie et un lien s'affiche ; pas de note « non fiable » dans le statut Eurocode 3.
  pytest 871 passed (9 nouveaux dans test_page_poutres.py) ; ruff check verts. Rendu visuel avec streamlit run non vérifié.
- [ ] E28 — Treillis + Sollicitations
- [ ] E29 — Flambage, Tenseurs & critères, Hooke & jauges
- [ ] E30 — Enregistrer / ouvrir + exports

## Phase 6 — Dossier de validation
- [ ] E31 — validation_report.py

## Phase 7 — Mise en ligne
- [ ] E32 — Déploiement Streamlit Community Cloud + recette
- [ ] E33 — (option) Version GitHub Pages sans serveur

## Notes
