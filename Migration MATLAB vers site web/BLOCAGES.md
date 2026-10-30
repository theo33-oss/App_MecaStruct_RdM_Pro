# Blocages

Format d'une entrée (la plus récente en haut) :

```
## AAAA-MM-JJ — Exx — titre court
- Fichier / fonction :
- Test en échec et message :
- Ce qui a été essayé (3 tentatives) :
- Hypothèse :
- Statut : ouvert | résolu (comment)
```

## 2026-10-30 — E13 — flèche : égalités de maxima et valeurs nulles au bruit dans les golden
- Fichier / fonction : `web/tests/test_deflection.py`, `test_golden_deflection` (18 cas `*_deflection` de golden_beam.json) et helpers `verifier_egalites_maxima`, `verifier_blocs_symetriques`, `verifier_valeurs_nulles`.
- Test en échec et message : 10 cas en échec avec la tolérance initiale. `appui_elastique_deflection` : `castigliano.sAtFmax` et `castigliano.s0` (abscisses 3,341 et 4,659, symétriques autour de L/2 = 4 m, |v| égal). `thermique_bi_encastree_deflection` : `castigliano.sAtFmax` (4,05 contre 5,55), flèche nulle en exact. Les autres : `integration.constants.C1/C2` et `aires.Aire` attendus à 0 ou au niveau du bruit (1e-11 à 1e-27), donc hors de l'atol 1e-12 fixe.
- Ce qui a été essayé :
  1. Tolérance initiale abs 1e-12, rel 1e-7 : 10 échecs.
  2. abs = 1e-12 × max|attendu du même champ| : 3 régressions (`appui_appui_uniforme`, `charge_triangulaire`, `readme_IPE200`, C2 attendu exactement 0) et 4 cas encore en échec (constantes au bruit).
  3. Règles de Théo (décision ci-dessous) : 18 cas passent.
- Hypothèse : MATLAB et numpy ne donnent pas les mêmes bits ; les valeurs nulles en exact et les maxima à égalité en exact sont départagés par le bruit d'arrondi.
- Décision demandée à Théo : les trois exceptions ci-dessous, dans le code de test seul ; golden JSON et autres tolérances inchangés.
- Statut : résolu. Décision de Théo, appliquée dans `test_deflection.py` :
  1. Constantes C1, C2 et `aires.Aire` : abs = max(1e-12, 1e-12 × plus grande valeur absolue de toute la sortie golden du cas, abscisses comprises). Ecart_pct : abs 1e-9. Le plancher 1e-12 garde les cas déjà verts.
  2. `appui_elastique` seul : les blocs `castigliano` et `mohr` ne sont plus comparés terme à terme mais par trois contrôles : max|vTotal|, max|vBending| et max|v| égaux au golden à rel 1e-7 ; à chaque s0, la flèche de Python égale celle du golden au même point ou à son symétrique L − s ; `mohr.s0` élément par élément égal à l'abscisse golden ou à son symétrique (1e-9 × L). Le reste (intégration, aires, comparaison) reste comparé en entier.
  3. Maxima : l'abscisse diffère seulement si la flèche de la méthode à l'abscisse de Python égale l'extremum golden (rel 1e-7, ou 1e-9 × échelle si les flèches sont nulles).
  Interprétations validées par mesure (lecture seule) :
  - Flèches nulles : plus grande flèche golden ≤ 1e-9 × échelle du cas. appui_elastique : 4,3e-2 contre seuil 4,6e-4, non nulle. thermique : 1,8e-18 contre seuil 1e-7, nulle.
  - Référence des maxima : la méthode elle-même. Thermique : castigliano 2,9e-33 contre golden 2,4e-33 ; le pp d'intégration donne 5,1e-19 au même point, du bruit. Appui_elastique : castigliano 0,043456410911857 et pp 0,043456410911857 contre golden 0,043456410911857535.
  - Appariement à 1e-9 × L : écarts mesurés de 9e-16 (41 points directs) et 3e-15 (symétrique), soit environ 1e6 fois sous la tolérance.
  - Non comparés pour appui_elastique : `castigliano.alpha`, `castigliano.vShear`, `mohr.details`.
  Suite : 629 passed, ruff check et format verts.

## 2026-10-30 — E07 — yAtMax : maximum plat de Q/b, golden couronne_60_40_integral_num
- Fichier / fonction : `web/mecastruct/core/geometry.py`, `_shearCore` (cote `yBest` du maximum de τ) ; test `web/tests/test_geometry.py::test_golden_integral_num[couronne_60_40_integral_num]`.
- Test en échec et message : `sortie.shear.yAtMax : 0 attendu, obtenu -1.740054017121826e-10` (rel 1e-6, abs 1e-15). Les 451 autres tests de la suite passent, ruff check et ruff format sont verts.
- Ce qui a été essayé :
  1. Seuil MATLAB `|yBest| <= 1e-9·L` (code actuel) : seul le cas couronne échoue.
  2. Seuil relevé à `1e-7·L` : casse `T_100` (analytique, intégrale, cisaillement, attendu −6.144e-10) et `caisson` analytique (attendu 7.97e-10).
  3. Cisaillement calculé sur le cœur de Huygens pour toutes les méthodes : casse `caisson` analytique (attendu 7.97e-10, obtenu 0).
  4. Retour au flux MATLAB (formule fermée en analytique, cœur numérique en intégrale) : seul le cas couronne reste en échec.
- Hypothèse : le maximum de Q/b est plat en y = 0 (section symétrique). Sa cote calculée par `minimize_scalar` n'est connue qu'à ~√ε·L près, donc elle dépend de l'arrondi du cœur (yG, S, Iz). MATLAB donne `yG = 0.029999999999998868` pour ce cas (erreur 1,1e-15 de integral2), Python `0.030000000000000002`. Côté MATLAB, le bruit tombe sous le seuil 1e-9·L et est ramené à 0 ; côté Python il reste −1,74e-10 (soit 2,9e-9·L). Les goldens `T_100` et `caisson` attendent au contraire des bruits non nuls (−6,144e-10 soit 6,1e-9·L, 7,97e-10) que le chemin actuel reproduit à ~1e-17 près. Aucun seuil ni choix de cœur ne satisfait les trois cas sans ajuster une constante au bruit observé.
- Décision demandée à Théo :
  - (a) accepter une tolérance absolue plus large sur `shear.yAtMax` dans les tests golden (par exemple 1e-9·L). C'est une modification de tolérance de test, donc à valider ;
  - (b) un seuil de mise à zéro entre 2,9e-9·L et 6,1e-9·L passerait les 452 tests, mais il serait calé sur ce bruit ;
  - (c) autre approche de la cote du maximum que tu préfères.
- Statut : résolu. Décision de Théo : option (a), tolérance absolue de 1e-9 m sur `yAtMax` dans les tests golden (`_verifie_golden` dans `web/tests/test_geometry.py`), seul ce champ ; aucun fichier golden JSON ni autre tolérance modifiés. Suite : 452 passed, ruff check et format verts. E07 cochée dans PROGRESSION.md.
