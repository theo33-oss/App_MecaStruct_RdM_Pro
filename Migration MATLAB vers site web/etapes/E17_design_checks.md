# E17 — Eurocode 3 et fatigue (`design_checks.py`)

**Modèle** : Haiku · **Durée** : 40 min · **Prérequis** : E07.

## Objectif
Porter `DesignChecks.m` (372 lignes) : classes de section, flexion + tranchant, déversement, flambement,
N + M, interaction, voilement de l'âme, fatigue de Goodman. Les clauses de norme citées dans les
commentaires et messages MATLAB (EN 1993-1-1 §…) sont **conservées mot pour mot** dans les docstrings
et les rapports.

## À lire
| Fichier | Lignes | Contenu |
| --- | --- | --- |
| `DesignChecks.m` | 1–372 | tout le fichier (en 2 lectures : 1–200 puis 200–372) |
| `docs/NORMES.md` | tout | clauses, hypothèses, limites |
| `tests/test_DesignChecks.m` | tout (≈ 300 lignes) | tests à porter |

## Fichier à créer : `web/mecastruct/core/design_checks.py`
```python
def ibeamDims(sec: dict) -> dict                    # h, b, tw, tf, r (m)
def classify(d, fy, Nc, Mz, A, Iz) -> dict
def ec3Bending(d, S, Iz, fy, gM0, MEd, VEd, Nc=0.0) -> dict
def ec3LateralTorsional(d, rolled, W, fy, gM1, E, G, Iweak, It, Lcr, C1, MEd) -> dict
def ec3FlexuralBuckling(d, rolled, A, Iy, Iz, Lcr, fy, E, gM1, NEd) -> dict   # Lcr scalaire ou [Lcr_y, Lcr_z]
def ec3AxialBending(d, b, A, fy, gM0, NEd, MEd) -> dict
def ec3Interaction(cls, buck, ltb, A, W, fy, gM1, NEd, MEd, Cmy, CmLT) -> dict
def ec3WebShear(d, fy, gM1, VEd) -> dict
def goodman(sigMax, R, Kf, Rm, ka, kb) -> dict      # sigmaA, sigmaM, Se, n
```
- Attention : dans `classify` et `ec3WebShear`, le MATLAB nomme une variable `eps` (= √(235/fy)) : en
  Python l'appeler `epsilon` pour ne pas confondre avec la précision machine. Dans `goodman`, `eps`
  désigne au contraire la **précision machine** MATLAB → `np.finfo(float).eps`.
- Erreurs : `MecaStruct:Design:class4`, `MecaStruct:Design:unsupportedSection`, `MecaStruct:Design:invalidInput`.

## Tests à écrire : `web/tests/test_design_checks.py`
1. Porter tous les tests de `tests/test_DesignChecks.m`.
2. Golden `golden_design.json` : chaque cas appelle la fonction indiquée par `fonction` avec les
   arguments de `entrees` (pour `ec3LateralTorsional`, `ec3FlexuralBuckling` et `ec3Interaction`,
   recalculer d'abord `d`, `b`, `buck`, `ltb` comme dans le script `Migration MATLAB vers site web/matlab/export_golden_json.m`,
   section « Eurocode 3 et fatigue », lignes à lire dans ce script). `rel=1e-9`.

## Vérifications
`python -m pytest -q` vert, `python -m ruff check .` sans erreur.

## Commit
`E17 : Eurocode 3 (classes, flexion, tranchant, déversement, flambement, N+M) et Goodman`
