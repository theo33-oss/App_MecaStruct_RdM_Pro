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
- Statut : ouvert. Reste de E07 fait (`geometry.py` complet : `analytical`, `integral`, `tabulated`, `compare`, `shearFactors`, `_assembleP`, `_shearCore`, `_integrateSymbolic`, `_integrateNumeric`). Case E07 non cochée dans PROGRESSION.md.
