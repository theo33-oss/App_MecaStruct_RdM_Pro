# Audit « le concepteur calcule et vérifie sans générer le dossier » (1er novembre 2026)

Objectif de l'application : le concepteur calcule et VÉRIFIE à plusieurs niveaux (résultat, explications à côté,
dossier de validation) sans devoir générer le dossier pour savoir si le calcul est bon.

Audit en lecture seule : 6 volets, 36 constats, tous confirmés par un second relecteur, aucun réfuté.
Ce fichier dit ce qui est corrigé, ce qui ne l'est pas, et ce qui n'a pas pu être vérifié.

## Corrigé

- **Section de Cisaillement et Flexion** : l'explication et le dossier relisaient la section courante de la page
  Sections, pas celle du calcul affiché. Ils utilisent maintenant la section enregistrée au clic sur « Calculer ».
- **Dossier de validation** : bouton grisé si la saisie a changé depuis le dernier calcul ; un ancien dossier est
  effacé à chaque nouveau calcul.
- **Bilan du dossier** (`validation_report.py`) : un sous-contrôle impossible (combinaisons, Eurocode 3, fatigue,
  profilé) compte comme un écart ; des hypothèses non contrôlées ou un calcul annexe non refait figurent dans le
  bilan au lieu de laisser « tout concorde ». Tests : `tests/test_validation_report.py`.
- **Résultats périmés** : avertissement commun à toutes les pages de calcul (via le bouton du dossier).
- **Poutres 2D, explications** : onglet « Explications du calcul » à côté des graphiques ; équilibres écrits avec leurs
  valeurs (kN, kN·m) ; coupes M(s) et T(s) avec les termes remplis, aux extrémités, à 10-25-50-75-90 % de L et aux
  extrema (étiquette « juste après la charge » quand la coupe est décalée) ; Kt·|σ|max, σadm et verdict ;
  flèche maximale avec son abscisse ; écarts exprimés dans l'unité affichée.
- **Ossature 3D** : onglet « Vérification à la main » (bilan ΣF et ΣM avec valeurs, contraintes comparées à Re) ;
  rapport avec charges nodales, Wy, Wz et β ; le texte de σmax décrit enfin ce que fait le code.
  Tests : `tests/test_verification_3d.py`.
- **Dossier de validation en HTML, PDF ou Word** (3 novembre, choix du format sous le bouton du dossier, toutes les
  pages) : le PDF et le Word reprennent les parties, les tableaux et les formules, dessinées en images (lisibles hors
  connexion). Les diagrammes Plotly n'y sont pas (version HTML seulement) ; les formules en matrice (array) restent en
  LaTeX brut. Code : `services/dossier_export.py` ; tests : `tests/test_dossier_export.py`.

## Non corrigé (à faire)

- Charge mobile : absente du panneau et du dossier ; la position du convoi qui donne chaque extrême n'est pas gardée
  (`beam_design.py`, `computeMovingLoad`).
- Combinaisons, Eurocode 3, fatigue, profilé : absents du panneau (le calcul principal seul est refait, voir le
  commit « explications sans recalcul des annexes ») ; ils restent dans le dossier.
- Poutres 2D : pas de ligne N(s), Mt(s) ni ΣMx ; ΣFx sans termes ; unités mélangées dans les lignes de ressorts et
  de tassements.
- « Concorde avec le solveur » n'est pas indépendant pour Eurocode 3, fatigue et Navier (valeurs reprises du
  solveur) ; poutres hyperstatiques : les réactions surabondantes ne sont pas contrôlées.
- Dossier : diagrammes et formules chargés depuis un CDN (Plotly, MathJax) : sans Internet ils disparaissent, le
  mot « autonome » est inexact ; charges réparties saisies peu lisibles.
- Eurocode 3 : le symbole I_z des formules désigne l'inertie faible (champ `Iy`).
- Clavette, goupille, Sections, Flexion : contrôles à la main absents ou partiels ; hypothèses et verdicts visibles
  seulement dans le dossier.
- Ossature 3D : maxima des efforts sans signe ni position, CSV sans efforts internes, exemples « expliqués » qui ne
  sont qu'une description, équilibre global qui ne contrôle pas le modèle lui-même ; σ refaite reprend les efforts
  du solveur (non indépendante).
- Parcours : retours des boutons avancés loin du bouton, guide de l'Accueil à mettre à jour, explications repliées
  en vue Téléphone.

## Non vérifié

- Justesse physique des solveurs contre une référence indépendante : « concorde » prouve la cohérence avec le même
  solveur, pas l'exactitude. Un seul cas contrôlé à la main : poutre sur deux appuis de l'exemple Poutres
  (flèche 15,47 mm = 10,62 + 4,85 mm par superposition).
- Pages Sections, Flambage, Tenseurs, Hooke et jauges, Treillis, Torsion : lues seulement, jamais recalculées.
- Persistance : un projet enregistré puis rechargé redonne-t-il les mêmes résultats, explications et dossier ?
- Rendu hors ligne du dossier et vue Téléphone : non testés dans un navigateur.
- Acier S185 à S355 : E passé de 190 GPa (cours) à 210 GPa (Eurocode 3), G = E/(2(1+ν)) = 80,77 GPa, à la demande
  du développeur. L'application MATLAB de référence reste à 190 GPa : la référence golden S235
  (`tests/golden/golden_datamanager.json`) et 4 tests ont été alignés à la main. Les résultats d'acier diffèrent donc
  de ceux de MATLAB d'environ 10 % sur les flèches.

# Éléments de machines (2 novembre 2026), d'après les classeurs Excel de l'auteur

Sources : clé USB D: (« MOI », FAT32). **Les six fichiers y sont abîmés** (octets altérés sur le disque, lecture
répétée identique) : les contenus ont été récupérés morceau par morceau. Faire une copie saine de la clé.

## Fait

- **Ajustements ISO 286** (page) : tables du classeur « ecarts-normalises » (`data/iso286.json`), règles ISO
  appliquées correctement (colonnes j et k selon la qualité, Δ pour K, M, N ≤ 8 et P à ZC ≤ 7 : les macros du classeur
  se trompaient). Vérifié sur des valeurs ISO 286-2 connues (K7, N7, P7, M7, JS7, J7, js6, k6, h8, j6, f7, r6, p6, s6).
- **Frettage** (page) : méthode reconstruite (le module de calcul du classeur était illisible) ; retrouve toutes les
  valeurs enregistrées du classeur (K, p mini, p maxi, σ équivalentes, coefficients de sécurité, ΔT) à 1e-12 près.
- **Paliers lisses** (page) : P, V, PV, courbe P-V du matériau, rotation ou oscillation, collerette ; retrouve les
  valeurs enregistrées du classeur. Pas de catalogue de fabricant (choix du développeur).
- **Clavette normalisée** et **goupille sous couple** : ajoutées aux volets Clavette et Goupille de Sollicitations,
  avec la pression de matage déjà choisie dans le volet.
- **17 nuances** du classeur matériaux ajoutées à `data/materials_extra.json` (E = 210 GPa pour les aciers).
- Chaque calcul a son onglet « Explications du calcul » (formules remplies avec les valeurs, démarche).
  Tests : `tests/test_machine_elements.py`.
- **Cours IUT de Bordeaux** (2 novembre, pages « Roulements », « Engrenages », « Trains épicycloïdaux », « Freins et
  embrayages », « Dimensionnement moteur ») : formules et exemples des six PDF, avec « Explications du calcul ».
  Roulements : L10, L10h, Lnh (a1), charge équivalente P (table e, X, Y du cours), charge requise, ensembles iso-fiables,
  règles de montage (bague serrée ou glissante, ajustements du tableau). Engrenages : géométrie, efforts, pied de dent
  (module minimal avec Re de la base), train en série. Épicycloïdal : Willis, montage. Freins : pression ou usure
  constante ; embrayage : couple de synchronisation. Moteur : couple équivalent thermique, inertie ramenée.
  Tests : `tests/test_machine_courses.py`.
- **Schémas qui suivent la saisie** (mêmes pages, redessinés à chaque valeur modifiée, avant « Calculer ») : pignon et
  roue à denture en développante (α = 20°, cercles primitifs, entraxe, ligne d'action), train d'engrenages en schéma
  cinématique, train épicycloïdal vu de face (élément bloqué hachuré, vitesses, montage vérifié ou non), roulement
  chargé, durées d'un ensemble, disque de frein et rayons équivalents, synchronisation de l'embrayage, cycle de couple
  du moteur ; après « Calculer » : courbe Lnh(P) et pression p(r) du frein. Tests : `tests/test_machine_schemas.py`
  (dentures qui engrènent sans se chevaucher dès 17 dents). Sous 17 dents, le dégagement de pied n'est pas dessiné :
  un avertissement le signale.

## Corrections de données (notées dans `data/iso286.json`)

- r / R : 26 → 28 µm (18 à 30 mm) et 66 → 68 µm (160 à 180 mm) ; c / C : ±670 → ∓70 µm (3 à 6 mm).

## Non fait ou non vérifié

- **Tableau des clavettes ressaisi à la main** (`data/keys_iso773.json`) d'après NF E22-177 / ISO 773 : le tableau
  du classeur était illisible. À VÉRIFIER sur la norme.
- **Cannelures** (flancs parallèles et en développante) : tableaux récupérés mais module de calcul illisible ; non
  porté.
- **Goupilles** : les configurations 1 et 2 du classeur (chape avec excentrement, goupille radiale dans un tube)
  ont des formules incohérentes (longueur d'appui du moyeu prise égale à son diamètre, torsion calculée avec le
  diamètre de la goupille) : non portées. Transversale et longitudinale sous couple : formules classiques
  (Roloff/Matek), pas celles du classeur pour le matage du moyeu. Catalogue Mécanindus non publié (choix).
- **Paliers lisses** : la vitesse en oscillation (V = π·d·4β·f/360/60) est une formule usuelle, le module du classeur
  étant perdu ; les limites P-V par famille de matériau viennent du classeur, à confirmer chez le fabricant.
  Une feuille de catalogue (PTFE) était illisible ; catalogues SKF non publiés (choix).
- **Frettage** : contrainte de l'arbre plein prise à 2p (formule du classeur, prudente : Von Mises donne p).
  Pression maxi calculée sans retrancher le lissage (prudent, comme le classeur).
- **ISO 286** : colonnes a, b, cd, d, ef, fg, t, u, v, x, y, z, za, zb, zc et leurs alésages non recoupées avec la
  norme (valeurs du classeur, deux coquilles déjà trouvées dans les autres colonnes).
- **Dossier de validation** : les cinq pages de cours (Roulements, Engrenages, Trains épicycloïdaux, Freins et
  embrayages, Dimensionnement moteur) ont un dossier par page, qui réunit les calculs à jour de la page
  (`services/machine_validation.py`, bouton `ui/machine_dossier.py`, tests `tests/test_machine_validation.py`). Ses
  contrôles à la main réécrivent les formules du cours : ils prouvent que le solveur les applique, pas qu'elles
  conviennent au cas. Pas de diagramme dans ces dossiers. Ajustements, Frettage et Paliers lisses n'ont toujours pas
  de dossier (explications à côté seulement).
- **Cours : écarts relevés dans les PDF** (à signaler à l'auteur du cours) : pour Fa/C0 = 0,064 le cours écrit
  Y = 1,59, alors que l'interpolation donne 1,66 (pente inversée dans la formule). Exemple du roulement : le cours
  annonce L10 = 185,3 M tours (10 294 h), or (C/P)³ avec C = 35,8 kN et P = 10,84 kN vaut 36 M tours (2 001 h à
  300 tr/min). Y = 1,31 y est lu au bord de la table (Fa/C0 = 0,170), l'interpolation à 0,207 donne 1,256.
- **Chaîne de transmission** : le cours ne donne ni les durées des phases de l'exemple ni la vitesse requise ; les
  valeurs par défaut de la page (1 s, 13,3 s) retrouvent seulement le couple de 61 N·m.
- **Engrenages, roulements** : pas de tableaux de catalogue (C, C0, e, X, Y par référence), pas de denture hélicoïdale
  ni déportée. La table e, X, Y est celle des billes à contact radial, saisie à la main pour les autres roulements.
- **Freins** : pas de limite de puissance spécifique du fabricant (la page affiche la valeur à comparer).
- **Embrayage** : modèle du cours (moteur à vitesse constante pendant la synchronisation), pas de modèle à vitesse
  variable.
