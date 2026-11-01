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
- **Résultats périmés** : avertissement commun à toutes les pages de calcul (via le bouton du dossier).
- **Poutres 2D, explications** : onglet « Explications du calcul » à côté des graphiques ; équilibres écrits avec leurs
  valeurs (kN, kN·m) ; coupes M(s) et T(s) avec les termes remplis, aux extrémités, à 10-25-50-75-90 % de L et aux
  extrema (étiquette « juste après la charge » quand la coupe est décalée) ; Kt·|σ|max, σadm et verdict ;
  flèche maximale avec son abscisse ; écarts exprimés dans l'unité affichée.
- **Ossature 3D** : onglet « Vérification à la main » (bilan ΣF et ΣM avec valeurs, contraintes comparées à Re) ;
  rapport avec charges nodales, Wy, Wz et β ; le texte de σmax décrit enfin ce que fait le code.
  Tests : `tests/test_verification_3d.py`.

## Non corrigé (à faire)

- Charge mobile : absente du panneau et du dossier ; la position du convoi qui donne chaque extrême n'est pas gardée
  (`beam_design.py`, `computeMovingLoad`).
- Combinaisons, Eurocode 3, fatigue, profilé : absents du panneau (le calcul principal seul est refait, voir le
  commit « explications sans recalcul des annexes ») ; ils restent dans le dossier.
- Poutres 2D : pas de ligne N(s), Mt(s) ni ΣMx ; ΣFx sans termes ; unités mélangées dans les lignes de ressorts et
  de tassements.
- « Concorde avec le solveur » n'est pas indépendant pour Eurocode 3, fatigue et Navier (valeurs reprises du
  solveur) ; poutres hyperstatiques : les réactions surabondantes ne sont pas contrôlées.
- Dossier : bilan « tout concorde » alors qu'un contrôle a pu échouer (`validation_report.py`, division par zéro
  et échecs isolés hors total) ; diagrammes et formules chargés depuis un CDN (Plotly, MathJax) : sans Internet ils
  disparaissent, le mot « autonome » est inexact ; charges réparties saisies peu lisibles.
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
