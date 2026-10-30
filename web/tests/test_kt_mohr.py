"""Tests de kt_mohr (étape E04) : portage des tests Kt et Mohr de tests/test_DataManager.m et cas golden."""

import numpy as np
import pytest
from scipy.integrate import quad

from mecastruct.core.errors import MecaStructError
from mecastruct.core.kt_mohr import evalKt, evalKtInfo, ktCharts, mohrTable
from tests.golden_tools import assert_matches, case_ids, get_case
from tests.test_data_manager import FORBIDDEN_LATEX

GOLDEN = "golden_datamanager.json"
ARBRES = ["arbre_epaulement_flexion", "arbre_epaulement_torsion", "arbre_epaulement_traction"]


def verifier_erreur(identifiant, appel, *args):
    """Vérifie que l'appel lève une MecaStructError portant l'identifiant MATLAB attendu."""
    with pytest.raises(MecaStructError) as info:
        appel(*args)
    assert info.value.identifier == identifiant


def _diagramme(forme: str, l: float, v: list[float]):
    """Diagramme élémentaire sur [0, l], valeurs caractéristiques v (même convention que mohrTable)."""
    formes = {
        "rectangle": lambda s: v[0] + 0 * s,
        "triangle": lambda s: v[0] * s / l,
        "triangle_inverse": lambda s: v[0] * (1 - s / l),
        "trapeze": lambda s: v[0] * (1 - s / l) + v[1] * s / l,
        "parabole": lambda s: 4 * v[0] * s * (l - s) / l**2,
    }
    return formes[forme]


# -------------------------------------------------------------------------------------------------
# Abaques Kt
# -------------------------------------------------------------------------------------------------


def test_golden_kt_plaque():
    cas = get_case(GOLDEN, "kt_plaque")
    assert_matches(evalKt(cas["entrees"]["id"], cas["entrees"]["prm"]), cas["sortie"], rel=1e-12)


@pytest.mark.parametrize("case_id", case_ids(GOLDEN, prefix="kt_arbre"))
def test_golden_kt_arbres(case_id):
    cas = get_case(GOLDEN, case_id)
    for prm, attendu in zip(cas["entrees"]["prm"], cas["sortie"], strict=True):
        assert_matches(evalKt(cas["entrees"]["id"], prm), attendu, rel=1e-12)


def test_abaques_kt_structure():
    C = ktCharts()
    assert sorted(c["id"] for c in C) == sorted(["plaque_trou_traction", *ARBRES])
    for c in C:
        assert {"id", "title", "params", "ranges", "description"} <= set(c)
        assert all(isinstance(p, str) for p in c["params"])
        ranges = np.asarray(c["ranges"], dtype=float).reshape(-1, 2)
        assert ranges.shape == (len(c["params"]), 2)
        assert (ranges[:, 1] > ranges[:, 0]).all()


def test_plaque_trouee():
    assert evalKt("plaque_trou_traction", 0) == 3
    x = 0.3
    assert evalKt("plaque_trou_traction", x) == pytest.approx(3 - 3.13 * x + 3.66 * x**2 - 1.53 * x**3, rel=1e-12)
    assert evalKt("plaque_trou_traction", {"d": 0.01, "W": 0.05}) == pytest.approx(
        evalKt("plaque_trou_traction", 0.2), rel=1e-12
    )
    xs = np.linspace(0, 0.99, 50)
    K = evalKt("plaque_trou_traction", xs)
    assert K.shape == xs.shape
    assert (K >= 1).all() and (np.diff(K) <= 0).all()
    verifier_erreur("MecaStruct:DataManager:ktParams", evalKt, "plaque_trou_traction", 1.2)
    verifier_erreur("MecaStruct:DataManager:unknownKt", evalKt, "inconnu", 0.1)


@pytest.mark.parametrize("arbre", ARBRES)
def test_arbre_epaulement_aux_points_de_la_table(arbre):
    tab = next(c for c in ktCharts() if c["id"] == arbre)["table"]
    for dd, A, b in tab:
        Kt, info = evalKtInfo(arbre, [0.1, dd])
        assert Kt == pytest.approx(max(A * 0.1**b, 1), rel=1e-12)
        assert info["inRange"]
        assert isinstance(info["report"], list) and isinstance(info["latex"], list)


@pytest.mark.parametrize("arbre", ARBRES)
def test_arbre_epaulement_interpolation_et_domaine(arbre):
    tab = np.asarray(next(c for c in ktCharts() if c["id"] == arbre)["table"], dtype=float)
    dm = (tab[0, 0] + tab[1, 0]) / 2
    _, info = evalKtInfo(arbre, {"rd": 0.05, "Dd": dm})
    assert info["A"] == pytest.approx((tab[0, 1] + tab[1, 1]) / 2, rel=1e-12)
    assert info["b"] == pytest.approx((tab[0, 2] + tab[1, 2]) / 2, rel=1e-12)
    rd = np.linspace(0.01, 0.3, 30)
    K = evalKt(arbre, np.column_stack([rd, np.full(30, 1.5)]))
    assert (K >= 1).all() and (np.diff(K) <= 1e-12).all()
    assert evalKt(arbre, [0.02, 2]) > evalKt(arbre, [0.02, 1.1])
    assert evalKt(arbre, {"r": 2, "d": 20, "D": 30}) == pytest.approx(evalKt(arbre, [0.1, 1.5]), rel=1e-12)
    _, info = evalKtInfo(arbre, [0.5, 1.5])
    assert not info["inRange"]
    verifier_erreur("MecaStruct:DataManager:ktParams", evalKt, arbre, [0.1, 0.9])
    verifier_erreur("MecaStruct:DataManager:ktParams", evalKt, arbre, {"x": 1})


def test_arbre_epaulement_ordre_de_grandeur():
    # Flexion, r/d = 0,1 et D/d = 2 : Kt ≈ 1,7
    assert evalKt("arbre_epaulement_flexion", [0.1, 2]) == pytest.approx(1.7, rel=0.06)


# -------------------------------------------------------------------------------------------------
# Table des intégrales de Mohr
# -------------------------------------------------------------------------------------------------


def test_mohr_contre_integration_numerique():
    l = 2.7
    vals = {
        "rectangle": [3.2],
        "triangle": [-1.7],
        "triangle_inverse": [2.3],
        "trapeze": [1.9, -0.8],
        "parabole": [4.1],
    }
    valsB = {
        "rectangle": [-0.6],
        "triangle": [2.9],
        "triangle_inverse": [1.1],
        "trapeze": [-2.2, 3.4],
        "parabole": [-1.3],
    }
    T = mohrTable()
    assert len(T) == 25
    for e in T:
        assert e["id"] == f"{e['shape1']}_x_{e['shape2']}"
        f1 = _diagramme(e["shape1"], l, vals[e["shape1"]])
        f2 = _diagramme(e["shape2"], l, valsB[e["shape2"]])
        ref, _ = quad(lambda s: f1(s) * f2(s), 0, l, epsabs=1e-14, epsrel=1e-13)
        assert e["fun"](l, vals[e["shape1"]], valsB[e["shape2"]]) == pytest.approx(ref, rel=1e-9), e["id"]


def test_mohr_ids_et_valeurs_de_cours():
    T = {e["id"]: e["fun"] for e in mohrTable()}
    for need in [
        "rectangle_x_rectangle",
        "rectangle_x_triangle",
        "rectangle_x_trapeze",
        "rectangle_x_parabole",
        "triangle_x_triangle",
        "triangle_x_triangle_inverse",
        "triangle_x_trapeze",
        "trapeze_x_trapeze",
        "parabole_x_triangle",
        "parabole_x_trapeze",
        "parabole_x_parabole",
    ]:
        assert need in T, need
    assert T["triangle_x_triangle"](6, [2], [5]) == pytest.approx(6 / 3 * 2 * 5, rel=1e-12)
    assert T["triangle_x_triangle_inverse"](6, [2], [5]) == pytest.approx(6 / 6 * 2 * 5, rel=1e-12)
    assert T["triangle_inverse_x_trapeze"](6, [3], [1, 2]) == pytest.approx(6 / 6 * 3 * (2 * 1 + 2), rel=1e-12)
    assert T["parabole_x_parabole"](1, [1], [1]) == pytest.approx(8 / 15, rel=1e-12)


# -------------------------------------------------------------------------------------------------
# LaTeX des abaques et de la table de Mohr
# -------------------------------------------------------------------------------------------------


def test_latex_sans_commande_interdite():
    chaines = [e["latex"] for e in mohrTable()] + [c["latex"] for c in ktCharts()]
    chaines.append(evalKtInfo("arbre_epaulement_flexion", [0.1, 1.5])[1]["latex"][0])
    chaines.append(evalKtInfo("plaque_trou_traction", 0.3)[1]["latex"][0])
    for s in chaines:
        assert s.startswith("$") and s.endswith("$"), s
        assert not any(cmd in s for cmd in FORBIDDEN_LATEX), s
