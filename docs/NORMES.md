# Normes et sources de MecaStruct RdM Pro

Ce document dit sur quelles normes et quels ouvrages reposent les vérifications de l'application, clause par clause.
Les textes des normes sont payants et ne sont pas dans le dépôt : les numéros de clauses et les valeurs ci-dessous
viennent des textes publiés et ont été recoupés avec les sources en ligne citées en fin de document.
**Avant tout usage professionnel, vérifier chaque valeur dans le texte officiel et dans l'annexe nationale du pays.**

## 1. Eurocode 3 : NF EN 1993-1-1 (calcul des structures en acier, règles générales)

Texte : NF EN 1993-1-1:2005 + A1:2014 et son annexe nationale NF EN 1993-1-1/NA (AFNOR). L'application applique
les **valeurs recommandées du texte européen**, sans l'annexe nationale.

| Sujet | Clause | Utilisé dans | Valeur / formule retenue |
|---|---|---|---|
| Coefficients partiels | §6.1(1) | `DesignChecks.ec3Bending`, `ec3LateralTorsional` | γM0 = γM1 = 1,0 (réglables) |
| Propriétés de l'acier | §3.2, tableau 3.1 | champ Re | fy = Re de la base de données ; la baisse de fy avec l'épaisseur n'est **pas** appliquée ; E = 210 GPa et G = 81 GPa (§3.2.6) sont les valeurs de l'Eurocode, la base de données du cours utilise E = 190 GPa |
| Classification des sections | §5.5, tableau 5.2 | `DesignChecks.classify` | ε = √(235/fy) ; aile en console c/tf ≤ 9ε, 10ε, 14ε ; âme comprimée et fléchie : ψ = σ2/σ1 et α = 1/(1 − ψ) aux bords de l'âme (compression comprise) ; sans compression : 72ε, 83ε, 124ε ; traction ignorée (côté sécurité) ; classe 4 refusée |
| Résistance en flexion | §6.2.5(2), éq. 6.12 à 6.14 | `ec3Bending` | Mc,Rd = Wpl·fy/γM0 (classes 1, 2) ou Wel·fy/γM0 (classe 3) |
| Résistance au cisaillement | §6.2.6(2), (3), éq. 6.17, 6.18 | `ec3Bending` | Vpl,Rd = Av·(fy/√3)/γM0 ; Av = A − 2·b·tf + (tw + 2r)·tf, au moins η·hw·tw avec η = 1,2 (1,0 au-delà de S460) |
| Flexion et effort tranchant | §6.2.8 | `ec3Bending` | si VEd > 0,5·Vpl,Rd : ρ = (2·VEd/Vpl,Rd − 1)², moment réduit |
| Résistance à la compression | §6.2.4, éq. 6.9, 6.10 | `ec3AxialBending` | Npl,Rd = A·fy/γM0 |
| Flexion + effort normal, classes 1 et 2 | §6.2.9.1(4), (5), éq. 6.33, 6.34, 6.36 | `ec3AxialBending` | n = NEd/Npl,Rd ; a = (A − 2b·tf)/A ≤ 0,5 ; MN,y,Rd = Mpl,y,Rd·(1 − n)/(1 − 0,5a) ≤ Mpl,y,Rd ; aucune réduction si NEd ≤ 0,25·Npl,Rd et NEd ≤ 0,5·hw·tw·fy/γM0 ; plafonné par le moment réduit par le tranchant |
| Flexion + effort normal, classe 3 | §6.2.9.2, éq. 6.42 | `ec3AxialBending` | σx,Ed = NEd/A + MEd/Wel ≤ fy/γM0 |
| Flambement par flexion | §6.3.1.2, éq. 6.46, 6.47, 6.49, 6.50 ; tableaux 6.1, 6.2 | `ec3FlexuralBuckling` | Ncr = π²EI/Lcr² ; λ̄ = √(A·fy/Ncr) ; Φ = 0,5·[1 + α(λ̄ − 0,2) + λ̄²] ; χ = 1/(Φ + √(Φ² − λ̄²)) ≤ 1 ; Nb,Rd = χ·A·fy/γM1 ; pas de vérification si λ̄ ≤ 0,2 ou NEd/Ncr ≤ 0,04 (§6.3.1.2(4)) ; courbes du tableau 6.2 pour S235 à S420 : laminé h/b > 1,2 : tf ≤ 40 mm a (y-y) / b (z-z), 40 < tf ≤ 100 mm b / c ; laminé h/b ≤ 1,2 : b / c (tf ≤ 100 mm) ; soudé : tf ≤ 40 mm b / c, sinon c / d ; α : a0 0,13 ; a 0,21 ; b 0,34 ; c 0,49 ; d 0,76 ; S460 refusé |
| Déversement des profils laminés | §6.3.2.2, §6.3.2.3, éq. 6.54, 6.55, 6.57 | `ec3LateralTorsional` | λ̄LT,0 = 0,4 ; β = 0,75 ; ΦLT = 0,5·[1 + αLT·(λ̄LT − λ̄LT,0) + β·λ̄LT²] ; χLT = 1/(ΦLT + √(ΦLT² − β·λ̄LT²)) borné à 1 et 1/λ̄LT² ; Mb,Rd = χLT·Wy·fy/γM1 |
| Courbes de déversement | tableaux 6.3 et 6.5 | `ec3LateralTorsional` | laminé : h/b ≤ 2 → courbe b, h/b > 2 → c ; soudé : h/b ≤ 2 → c, h/b > 2 → d ; α : a 0,21 ; b 0,34 ; c 0,49 ; d 0,76 |
| Combinaisons ELU | EN 1990, §6.4.3.2, éq. 6.10 | tableau Combinaisons (valeurs par défaut) | 1,35·G + 1,5·Q (STR/GEO, coefficients de l'annexe A1 de l'EN 1990, tableau A1.2(B)) |

Limites assumées par l'application, **écrites aussi dans le tableau de résultats** :
- interaction N + M (§6.3.3) : annexe B (méthode 2, tableau B.2, barres sensibles à la torsion, profils en I), flexion autour de l'axe fort seulement, Cmy et CmLT saisis (1 = prudent). Les expressions de kyy et kzy sont transcrites de mémoire et recoupées en partie seulement avec des sources en ligne (le tableau imprimé contient des coquilles connues) : **à vérifier dans l'EN 1993-1-1 avant usage** ; pas de flexion déviée ;
- tableau 6.2 : seule sa première ligne (laminés h/b > 1,2, tf ≤ 40 mm) a pu être recoupée avec une source en ligne ; les autres lignes viennent des textes publiés et sont à vérifier dans l'EN 1993-1-1 avant usage ;
- voilement de l'âme par cisaillement (EN 1993-1-5 §5) : contrôle de hw/tw > 72ε/η, sinon Vb,Rd = χw·fy·hw·tw/(√3·γM1) avec λ̄w = hw/(86,4·tw·ε) et le tableau 5.1 (poteau d'extrémité rigide, semelles négligées) ; pas de voilement sous charges concentrées (§6), pas de section efficace (classe 4), pas d'assemblages (EN 1993-1-8) ;
- pas d'ELS : les limites de flèche sont fixées par l'annexe nationale (valeurs usuelles L/200 à L/300), l'utilisateur les fixe lui-même dans « Chercher le profilé le plus léger » ;
- flambement : longueur Lcr,y pour l'axe fort y-y (la longueur de la poutre par défaut) et Lcr pour l'axe faible z-z (entretoises) ; laminé h/b > 1,2 avec tf > 100 mm non tabulé, courbe d retenue par prudence ;
- déversement : poutre à fourches, charge appliquée au centre de torsion, pas de coefficient f de répartition du moment (§6.3.2.3, éq. 6.58, favorable), Iw estimé par Iz·(h − tf)²/4 (parois minces) ;
- annexe nationale : seules γM0 et γM1 sont paramétrables. La France retient γM0 = 1,0, γM1 = 1,0 et γM2 = 1,25 (source : documentation de logiciels de calcul, pas le texte de l'annexe), soit les valeurs de l'EN ; les autres paramètres (courbes, λLT,0, β) restent les valeurs recommandées, non comparées au texte de l'annexe française. Les valeurs d'autres pays ne sont pas fournies : choisir « Autre » et les saisir ;
- l'Eurocode 3 ne remplace pas la note de calcul d'un bureau d'études.

## 2. Moment critique élastique de déversement

NCCI SN003a-EN-EU et SN003b-EN-EU « Elastic critical moment for lateral torsional buckling » (Access Steel, CTICM / SCI).
Poutre doublement symétrique, appuis à fourches (k = kw = 1) :
Mcr = C1·π²·E·Iz/Lcr² · √(Iw/Iz + Lcr²·G·It/(π²·E·Iz)).
C1 = 1,00 pour un moment uniforme, 1,77 pour des moments d'extrémité ψ = 0, environ 1,13 pour une charge uniforme et
1,35 pour une charge centrée sur appuis simples. La valeur par défaut de l'application est C1 = 1 (prudent).

## 3. Fatigue

Droite de Goodman modifiée et facteurs de Marin (ka état de surface, kb effet de taille) :
R. G. Budynas, J. K. Nisbett, *Shigley's Mechanical Engineering Design*, McGraw-Hill, chap. 6.
Se = ka·kb·0,5·Rm (acier, Rm ≤ 1400 MPa, plafonné à 700 MPa) ; Kf = Kt appliqué à l'amplitude ; n = 1/(σa/Se + σm/Rm).
Ce n'est **pas** la vérification de fatigue des constructions métalliques (catégories de détail ΔσC, EN 1993-1-9), non traitée.

## 4. Autres sources déjà utilisées par l'application

| Sujet | Source |
|---|---|
| Dimensions et caractéristiques des profilés IPE, HEA, HEB, IPN, UPN, UAP | NF EN 10365 (dimensions) ; catalogues ArcelorMittal et fabricants ; tolérances EN 10034 |
| Nuances d'acier et limites élastiques | NF EN 10025-2 (aciers de construction laminés à chaud) |
| Alliages d'aluminium et de cuivre (Rm, Rp0,2 minimaux ; E, G, ν, α, ρ de l'aluminium) | Euralliage, https://www.euralliage.com, fiches par nuance (EN 485-2, EN 755-2, EN 754-2, EN 12163, EN 12164, EN 1652) ; E, ν, α du cuivre et de ses alliages : valeurs usuelles, absentes des fiches |
| Bois (C24, GL24h) | EN 338, EN 14080, EN 1995-1-1 |
| Béton (C25/30, C30/37) | EN 1992-1-1, tableau 3.1 |
| Tubes, cornières (dimensions nominales) | EN 10219, EN 10210, EN 10056-1 |
| Théorie de la RDM (Navier, Jourawski, Euler, Castigliano, Ménabréa, Mohr, Tresca, Von Mises, Hooke, Bredt, Saint-Venant) | voir README, section « Auteur et sources » |
| Coefficients de concentration de contrainte Kt | W. D. Pilkey, *Peterson's Stress Concentration Factors*, Wiley |

## 5. Sources en ligne consultées pour recouper les valeurs (consultées le 29 octobre 2026)

- Tableau 5.2 (limites de classes) et facteurs d'imperfection : SkyCiv, « Guide to Eurocode 3 steel design » (https://skyciv.com/docs/tech-notes/other/guide-to-eurocode-3-steel-design/), annexe nationale de Chypre à l'EN 1993-1-1 (tableaux 6.1 et 6.3), SDC Verifier « EC3 buckling curves a, b, c, d » (https://sdcverifier.com/structural-engineering-101/ec3-buckling-curves-a-b-c-d/).
- §6.3.2.3 (λ̄LT,0 = 0,4, β = 0,75, courbes du tableau 6.5) : documentation STAAD.Pro de Bentley, « Clause 6.3.2.3(1) – LTB for rolled sections or equivalent welded section » (https://docs.bentley.com/LiveContent/web/STAAD.Pro%20Help-v21/en/GUID-3B18C54A-0B6C-4553-8E1B-717E63834082.html) ; l'annexe nationale finlandaise retient la courbe b pour h/b ≤ 2 et c au-delà.
- Moment critique : NCCI SN003b, SteelConstruction.info (https://www.SteelConstruction.info/images/0/0f/SN003b.pdf) et SN003a (https://dan.ct.upt.ro/fire/files/NCCI_SN003a-EN-EU.pdf).
- Les annexes nationales peuvent modifier λ̄LT,0, β et le choix des courbes : l'annexe belge, par exemple, prévoit 0,2 et 1,0 lorsque Mcr tient compte des maintiens latéraux. Vérifier l'annexe du pays d'utilisation.
- §6.2.9.1 (flexion + effort normal, éq. 6.36) : Blueprints, documentation de l'EN 1993-1-1:2005 (https://blueprints.readthedocs.io/en/stable/API%20reference/codes/eurocode/en_1993_1_1_2005/chapter_6_ultimate_limit_state/formula_6_36/) et exemple de vérification SOFiSTiK (https://docs.sofistik.com/2026/en/verification/_static/verification/pdf/dce-en20.pdf). Pour n, ces sources utilisent NEd/Npl,Rd (NV,Rd quand le tranchant réduit la résistance) ; l'application emploie NEd/Npl,Rd puis plafonne par le moment réduit par le tranchant.
- Tableau 6.2 (courbes de flambement) : recoupé seulement pour la première ligne, via la documentation STAAD.Pro de Bentley ; les autres lignes sont à vérifier dans le texte de l'EN.

## 6. Contrôle de ces vérifications

Le dossier de validation de la poutre (`ValidationReport`) refait à la main le calcul Eurocode 3 et la fatigue avec d'autres écritures que `DesignChecks.m` : il détecte une erreur de programmation, pas un choix de formule ou de coefficient discutable. Les valeurs de normes ci-dessus restent à vérifier dans les textes officiels.
