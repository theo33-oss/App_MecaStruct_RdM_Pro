"""Tests de truss_solver (étape E11).

Portage des tests treillis de tests/test_BeamAndTrussSolver.m (lignes 739–890), golden_truss.json (4 cas, dont
l'erreur de mécanisme) et égalité méthode des nœuds / méthode des rigidités sur le triangle.
"""

import numpy as np
import pytest

from mecastruct.core.errors import MecaStructError
from mecastruct.core.truss_solver import solveTruss
from tests.golden_tools import assert_matches, case_ids, get_case

MODELE = "MecaStruct:Truss:invalidModel"
MECANISME = "MecaStruct:Truss:mechanism"


def verifier_erreur(identifiant, appel, *args):
    """Vérifie que l'appel lève une MecaStructError portant l'identifiant MATLAB attendu."""
    with pytest.raises(MecaStructError) as info:
        appel(*args)
    assert info.value.identifier == identifiant


def triangle(P):
    """Triangle isostatique 2D de tests/test_BeamAndTrussSolver.m (triangleTruss), charge P vers le bas en C."""
    return {
        "nodes": [[0, 0], [4, 0], [2, 3]],
        "bars": [[1, 2], [1, 3], [2, 3]],
        "E": 210e9,
        "S": 1e-4,
        "supports": [[True, True], [False, True], [False, False]],
        "loads": [[0, 0], [0, 0], [0, -P]],
    }


def residu_noeuds(t, tr):
    """Résidu max de [A]{N, R} + F = 0 (méthode des nœuds), R = réactions aux ddl bloqués."""
    sups = np.asarray(tr["supports"], dtype=bool)
    rb = t["reactions"].reshape(-1)[sups.reshape(-1)]
    F = np.asarray(tr["loads"], dtype=float).reshape(-1)
    return np.max(np.abs(t["A"] @ np.concatenate([t["N"], rb]) + F))


def test_triangle_isostatique():
    P = 1000
    t = solveTruss(triangle(P))
    assert t["dim"] == 2 and t["h"] == 0
    assert t["isostatic"] and not t["mechanism"]
    # résolution à la main : N_AC = N_BC = -P√13/6, N_AB = P/3
    nhand = np.array([P / 3, -P * np.sqrt(13) / 6, -P * np.sqrt(13) / 6])
    np.testing.assert_allclose(t["N"], nhand, rtol=1e-12)
    np.testing.assert_allclose(t["Njoints"], nhand, rtol=1e-12)
    np.testing.assert_allclose(t["Nstiffness"], nhand, rtol=1e-10)
    # méthode des nœuds ≡ méthode des rigidités
    np.testing.assert_allclose(t["Njoints"], t["Nstiffness"], rtol=1e-10)
    np.testing.assert_allclose(t["reactions"], [[0, P / 2], [0, P / 2], [0, 0]], rtol=0, atol=1e-9)
    assert t["nature"] == ["Traction", "Compression", "Compression"]
    np.testing.assert_allclose(t["L0"], [4, np.sqrt(13), np.sqrt(13)], rtol=1e-14)
    np.testing.assert_allclose(t["sigma"], nhand / 1e-4, rtol=1e-12)
    np.testing.assert_allclose(t["dL"], nhand * t["L0"] / (210e9 * 1e-4), rtol=1e-12)
    assert t["A"].shape == (6, 6)
    # Clapeyron : travail de P = énergie de déformation
    U = np.sum(t["N"] ** 2 * t["L0"] / (210e9 * 1e-4)) / 2
    np.testing.assert_allclose(0.5 * P * -t["displacements"][2, 1], U, rtol=1e-10)
    np.testing.assert_array_equal(t["displacements"][0], [0, 0])
    assert t["displacements"][1, 1] == 0
    T = t["table"]
    assert list(T.columns) == ["Barre", "Noeuds", "L_m", "N_N", "Nature", "Sigma_Pa", "dL_m"]
    assert len(T) == 3 and T["Noeuds"][1] == "A-C"
    assert all(isinstance(x, str) for x in t["report"])
    assert "nœuds" in t["methodUsed"]


def test_3barres_hyperstatique():
    P, a, H = 2e4, 1.5, 2
    tr = {
        "nodes": [[-a, H], [0, H], [a, H], [0, 0]],
        "bars": [[1, 4], [2, 4], [3, 4]],
        "E": 200e9,
        "S": 3e-4,
        "supports": [[1, 1], [1, 1], [1, 1], [0, 0]],
        "loads": [[0, 0], [0, 0], [0, 0], [0, -P]],
        "names": ["A", "B", "C", "D"],
    }
    t = solveTruss(tr)
    assert t["h"] == 1 and not t["isostatic"] and not t["mechanism"]
    assert len(t["Njoints"]) == 0
    ca = H / np.sqrt(a**2 + H**2)
    N2 = P / (1 + 2 * ca**3)
    N1 = P * ca**2 / (1 + 2 * ca**3)
    np.testing.assert_allclose(t["N"], [N1, N2, N1], rtol=1e-10)
    np.testing.assert_array_equal(t["Nstiffness"], t["N"])
    np.testing.assert_allclose(np.sum(t["reactions"][:, 1]), P, rtol=1e-12)
    assert t["nature"] == ["Traction"] * 3
    assert residu_noeuds(t, tr) < 1e-8 * P
    assert t["methodUsed"] == "méthode des rigidités"


def test_hyperstatique_contreventement():
    # carré à deux diagonales (h = 1) : équilibre et Clapeyron
    P = 5e3
    tr = {
        "nodes": [[0, 0], [2, 0], [2, 2], [0, 2]],
        "bars": [[1, 2], [2, 3], [3, 4], [4, 1], [1, 3], [2, 4]],
        "E": 210e9,
        "S": [2e-4, 2e-4, 2e-4, 2e-4, 1e-4, 1e-4],
        "supports": [[1, 1], [0, 1], [0, 0], [0, 0]],
        "loads": [[0, 0], [0, 0], [P, 0], [0, -P]],
    }
    t = solveTruss(tr)
    assert t["h"] == 1
    U = np.sum(t["N"] ** 2 * t["L0"] / (tr["E"] * np.array(tr["S"]))) / 2
    W = 0.5 * np.sum(np.asarray(tr["loads"], dtype=float) * t["displacements"])
    np.testing.assert_allclose(W, U, rtol=1e-10)
    assert residu_noeuds(t, tr) < 1e-8 * P
    np.testing.assert_allclose(t["dL"], t["N"] * t["L0"] / (tr["E"] * np.array(tr["S"])), rtol=1e-12)


def test_tripode_3d():
    P, R, H = 9e3, 1, 2
    tr = {
        "nodes": [[R, 0, 0], [-R / 2, R * np.sqrt(3) / 2, 0], [-R / 2, -R * np.sqrt(3) / 2, 0], [0, 0, H]],
        "bars": [[1, 4], [2, 4], [3, 4]],
        "E": 210e9,
        "S": 1e-4,
        "supports": [[1, 1, 1], [1, 1, 1], [1, 1, 1], [0, 0, 0]],
        "loads": [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, -P]],
    }
    t = solveTruss(tr)
    assert t["dim"] == 3 and t["h"] == 0 and t["isostatic"]
    cb = H / np.sqrt(R**2 + H**2)
    np.testing.assert_allclose(t["N"], -P / (3 * cb) * np.ones(3), rtol=1e-12)
    np.testing.assert_allclose(t["reactions"][:3, 2], P / 3 * np.ones(3), rtol=1e-12)
    np.testing.assert_allclose(t["Nstiffness"], t["Njoints"], rtol=1e-10)
    # charge dissymétrique : nœuds ≡ rigidités
    tr["loads"][3] = [1e3, -2e3, -P]
    t2 = solveTruss(tr)
    np.testing.assert_allclose(t2["Nstiffness"], t2["Njoints"], rtol=1e-9)
    np.testing.assert_allclose(t2["reactions"].sum(axis=0), -np.array(tr["loads"][3]), rtol=1e-10)
    assert t2["displacements"].shape == (4, 3)


def test_mecanisme():
    tr = {
        "nodes": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "bars": [[1, 2], [2, 3], [3, 4], [4, 1]],
        "E": 210e9,
        "S": 1e-4,
        "supports": [[1, 1], [0, 1], [0, 0], [0, 0]],
        "loads": [[0, 0], [0, 0], [1000, 0], [0, 0]],
    }
    verifier_erreur(MECANISME, solveTruss, tr)
    tr["loads"] = [[0, 0]] * 4
    t = solveTruss(tr)
    assert t["mechanism"] and not t["isostatic"]
    np.testing.assert_allclose(t["N"], np.zeros(4), atol=1e-12)
    assert t["nature"] == ["Nul"] * 4


def test_entrees_invalides():
    bad = triangle(1000)
    bad["bars"] = [[1, 2], [2, 5]]
    verifier_erreur(MODELE, solveTruss, bad)
    bad = triangle(1000)
    bad["supports"] = np.ones((2, 2), dtype=bool).tolist()
    verifier_erreur(MODELE, solveTruss, bad)
    bad = triangle(1000)
    bad["nodes"][2] = bad["nodes"][0]
    verifier_erreur(MODELE, solveTruss, bad)
    bad = triangle(1000)
    bad["S"] = [1, 2]
    verifier_erreur(MODELE, solveTruss, bad)
    verifier_erreur(MODELE, solveTruss, 42)
    # noms par défaut et charges absentes
    ok = triangle(1000)
    del ok["loads"]
    t = solveTruss(ok)
    np.testing.assert_allclose(t["N"], np.zeros(3), atol=1e-12)
    assert t["names"] == ["A", "B", "C"]


@pytest.mark.parametrize("cid", case_ids("golden_truss.json"))
def test_golden_truss(cid):
    c = get_case("golden_truss.json", cid)
    if c["erreur"]:
        verifier_erreur(c["erreur"].split(" | ")[0], solveTruss, c["entrees"])
    else:
        assert_matches(solveTruss(c["entrees"]), c["sortie"], rel=1e-9, abs_=1e-6)
