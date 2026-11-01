"""Tests du moteur d'ossatures 3D (frame3d) : cas d'école analytiques, équilibre, mécanisme, entrées invalides."""

import math

import numpy as np
import pytest

from mecastruct.core import beam_solver, deflection, frame3d
from mecastruct.core.pp import ppEval

E, G = 210e9, 80e9
PROPS = {"E": E, "G": G, "A": 2e-3, "Iy": 8e-6, "Iz": 3e-6, "J": 1e-6, "rho": 7850.0}
REL = 1e-6


def noeud(i, x, y=0.0, z=0.0, appui="libre", **kw):
    return {"id": i, "x": x, "y": y, "z": z, "appui": appui, **kw}


def element(i, ni, nj, **kw):
    return {"id": i, "ni": ni, "nj": nj, **PROPS, **kw}


def console(L=2.0, direction=(1.0, 0.0, 0.0), n=1, **props):
    """Console de longueur L selon `direction`, encastrée au nœud 0, découpée en n éléments."""
    d = np.asarray(direction) / np.linalg.norm(direction)
    nds = [noeud(k, *(d * L * k / n), appui="encastrement" if k == 0 else "libre") for k in range(n + 1)]
    return {"noeuds": nds, "elements": [element(k + 1, k, k + 1, **props) for k in range(n)]}


# ------------------------------------------------------------------ 1 à 3 : console


def test_console_force_bout_deux_plans():
    L, P = 2.0, 1e3
    d = console(L)
    d["charges_nodales"] = [{"noeud": 1, "Fz": -P}]
    u = frame3d.solveFrame3D(d)["deplacements"][1]
    assert u[2] == pytest.approx(-P * L**3 / (3 * E * PROPS["Iy"]), rel=REL)
    assert u[4] == pytest.approx(P * L**2 / (2 * E * PROPS["Iy"]), rel=REL)  # θy = -w' > 0
    d["charges_nodales"] = [{"noeud": 1, "Fy": -P}]
    u = frame3d.solveFrame3D(d)["deplacements"][1]
    assert u[1] == pytest.approx(-P * L**3 / (3 * E * PROPS["Iz"]), rel=REL)
    assert u[5] == pytest.approx(-P * L**2 / (2 * E * PROPS["Iz"]), rel=REL)  # θz = v'


def test_traction_et_torsion():
    L, P, T = 2.0, 1e4, 300.0
    d = console(L)
    d["charges_nodales"] = [{"noeud": 1, "Fx": P, "Mx": T}]
    r = frame3d.solveFrame3D(d)
    u = r["deplacements"][1]
    assert u[0] == pytest.approx(P * L / (E * PROPS["A"]), rel=REL)
    assert u[3] == pytest.approx(T * L / (G * PROPS["J"]), rel=REL)
    ef = r["efforts"][1]
    assert np.allclose(ef["N"], P, rtol=REL) and np.allclose(ef["T"], T, rtol=REL)


def test_console_charge_repartie_deux_plans():
    L, q = 3.0, 2e3
    for comp, I, k in (("qz", PROPS["Iy"], 2), ("qy", PROPS["Iz"], 1)):
        d = console(L)
        d["charges_reparties"] = [{"element": 1, comp: -q}]
        r = frame3d.solveFrame3D(d)
        assert r["deplacements"][1][k] == pytest.approx(-q * L**4 / (8 * E * I), rel=REL)
        M = r["efforts"][1]["My" if k == 2 else "Mz"]
        assert abs(M[0]) == pytest.approx(q * L**2 / 2, rel=REL) and abs(M[-1]) < 1e-9 * q * L**2


# ------------------------------------------------------------------ 4 : poutre sur deux appuis


def test_deux_appuis_quatre_elements():
    L, q = 4.0, 5e3
    nds = [noeud(k, L * k / 4) for k in range(5)]
    nds[0]["appui"] = "rotule"
    nds[4].update(appui="perso", ddl=[False, True, True, True, False, False])
    d = {
        "noeuds": nds,
        "elements": [element(k + 1, k, k + 1) for k in range(4)],
        "charges_reparties": [{"element": k + 1, "qz": -q} for k in range(4)],
    }
    r = frame3d.solveFrame3D(d)
    assert r["deplacements"][2][2] == pytest.approx(-5 * q * L**4 / (384 * E * PROPS["Iy"]), rel=REL)
    Mmax = max(max(abs(m) for m in r["efforts"][k]["My"]) for k in range(1, 5))
    assert Mmax == pytest.approx(q * L**2 / 8, rel=REL)
    assert r["reactions"][0][2] == pytest.approx(q * L / 2, rel=REL)
    assert r["deplacement_max"]["noeud"] == 2


# ------------------------------------------------------------------ 5 : invariance par rotation


def test_invariance_orientation():
    L, P = 2.0, 1e3
    rond = {"Iy": 5e-6, "Iz": 5e-6, "J": 1e-5}
    ref = P * L**3 / (3 * E * 5e-6)
    s3 = 1 / math.sqrt(3)
    cas = [((1, 0, 0), (0, 0, -1)), ((0, 1, 0), (0, 0, -1)), ((0, 0, 1), (1, 0, 0)), ((s3, s3, s3), (1, -1, 0))]
    for direction, f in cas:
        d = console(L, direction, **rond)
        f = P * np.asarray(f, dtype=float) / np.linalg.norm(f)
        d["charges_nodales"] = [{"noeud": 1, "Fx": f[0], "Fy": f[1], "Fz": f[2]}]
        u = np.array(frame3d.solveFrame3D(d)["deplacements"][1][:3])
        assert np.linalg.norm(u) == pytest.approx(ref, rel=REL)
        assert u @ f / P == pytest.approx(ref, rel=REL)


# ------------------------------------------------------------------ 6 : potence en L


def test_potence_en_L():
    a, b, P = 1.5, 1.0, 500.0
    s = frame3d.sectionRond(0.05)
    d = {
        "noeuds": [noeud(1, 0, appui="encastrement"), noeud(2, a), noeud(3, a, b)],
        "elements": [{"id": k, "ni": k, "nj": k + 1, "E": E, "G": G, **s} for k in (1, 2)],
        "charges_nodales": [{"noeud": 3, "Fz": -P}],
    }
    I, J = s["Iy"], s["J"]
    attendu = P * a**3 / (3 * E * I) + P * b**3 / (3 * E * I) + P * a * b**2 / (G * J)
    assert frame3d.solveFrame3D(d)["deplacements"][3][2] == pytest.approx(-attendu, rel=REL)


# ------------------------------------------------------------------ 7 : rotule


def test_rotule_noeud_central():
    L, P = 2.0, 1e3
    d = {
        "noeuds": [noeud(1, 0, appui="encastrement"), noeud(2, L), noeud(3, 2 * L, appui="encastrement")],
        "elements": [element(1, 1, 2), element(2, 2, 3)],
        "charges_nodales": [{"noeud": 2, "Fz": -P}],
    }
    EI = E * PROPS["Iy"]
    assert frame3d.solveFrame3D(d)["deplacements"][2][2] == pytest.approx(-P * L**3 / (24 * EI), rel=REL)
    d["elements"][0]["liaison_j"] = "articulee"
    r = frame3d.solveFrame3D(d)
    assert r["deplacements"][2][2] == pytest.approx(-P * L**3 / (6 * EI), rel=REL)
    ef = r["efforts"][1]
    assert abs(ef["My"][-1]) < 1e-9 and abs(ef["Mz"][-1]) < 1e-9
    assert abs(ef["My"][0]) == pytest.approx(P * L / 2, rel=REL)  # chaque moitié porte P/2


def test_blocage_automatique_rotations():
    # deux barres articulées au nœud central : ses rotations n'ont aucune raideur hors torsion
    L, P = 2.0, 1e3
    d = {
        "noeuds": [noeud(1, 0, appui="encastrement"), noeud(2, L), noeud(3, 2 * L, appui="encastrement")],
        "elements": [element(1, 1, 2, liaison_j="articulee"), element(2, 2, 3, liaison_i="articulee")],
        "charges_nodales": [{"noeud": 2, "Fz": -P}],
    }
    r = frame3d.solveFrame3D(d)
    assert r["deplacements"][2][2] == pytest.approx(-P * L**3 / (6 * E * PROPS["Iy"]), rel=REL)
    assert len(r["blocages_auto"]) == 2 and all(b["noeud"] == 2 for b in r["blocages_auto"])
    assert any("Blocage automatique" in ligne for ligne in r["rapport"])
    assert r["equilibre"]["ok"]


# ------------------------------------------------------------------ 8 : exemples


@pytest.mark.parametrize("nom", ["Console", "Potence en L", "Portique 3D", "Table 4 pieds"])
def test_exemples_equilibre_et_symetrie(nom):
    r = frame3d.solveFrame3D(frame3d.exemples()[nom])
    assert r["equilibre"]["ok"]
    K = r["K"]
    assert np.allclose(K, K.T, rtol=0, atol=1e-12 * np.abs(K).max())
    assert all(c["sigma_max"] is not None for c in r["contraintes"].values())
    for ligne in r["latex"]:
        assert ligne.isascii() and ligne.count("{") == ligne.count("}")


# ------------------------------------------------------------------ 9, 10 : erreurs


def test_mecanisme():
    d = {
        "noeuds": [noeud(1, 0, appui="appui_z"), noeud(2, 3, appui="appui_z")],
        "elements": [element(1, 1, 2)],
        "charges_nodales": [{"noeud": 2, "Fz": -1e3}],
    }
    with pytest.raises(frame3d.FrameMechanismError, match="mécanisme.*ux"):
        frame3d.solveFrame3D(d)


def test_entrees_invalides():
    base = {"noeuds": [noeud(1, 0, appui="encastrement"), noeud(2, 1)], "elements": [element(1, 1, 2)]}
    with pytest.raises(ValueError, match="n'existe pas"):
        frame3d.solveFrame3D({**base, "elements": [element(1, 1, 9)]})
    with pytest.raises(ValueError, match="longueur nulle"):
        frame3d.solveFrame3D({**base, "noeuds": [noeud(1, 0, appui="encastrement"), noeud(2, 0)]})
    with pytest.raises(ValueError, match="strictement positif"):
        frame3d.solveFrame3D({**base, "elements": [element(1, 1, 2, A=0)]})
    with pytest.raises(ValueError, match="double"):
        frame3d.solveFrame3D({**base, "noeuds": base["noeuds"] + [noeud(2, 5)]})


# ------------------------------------------------------------------ sections


def test_sections():
    s = frame3d.sectionRectangle(0.1, 0.1)
    assert s["J"] == pytest.approx(0.1406 * 0.1**4, rel=2e-3)  # carré : J ≈ 0,1406·a⁴ (Roark)
    assert s["Wt"] == pytest.approx(0.208 * 0.1**3, rel=2e-3)
    r = frame3d.sectionRectangle(0.02, 0.2)  # a/c = 10 : J = 0,312·a·c³ (table de Timoshenko)
    assert r["J"] == pytest.approx(0.312 * 0.2 * 0.02**3, rel=2e-3)  # table à 3 chiffres
    assert r["Iy"] == pytest.approx(0.02 * 0.2**3 / 12)
    t = frame3d.sectionTube(0.1, 0.05)
    assert t == pytest.approx(frame3d.sectionRond(0.1))


# ------------------------------------------------------------------ 11 : comparaison au solveur 2D


def test_comparaison_solveBeam():
    L, a, P = 4.0, 1.5, 1e4
    m2d = {
        "L": L,
        "E": E,
        "G": G,
        "S": PROPS["A"],
        "Iz": PROPS["Iz"],
        "Iy": PROPS["Iy"],
        "Ix": PROPS["J"],
        "supports": [{"pos": 0, "type": "pivot", "name": "A"}, {"pos": L, "type": "appui_simple", "name": "B"}],
        "pointLoads": [{"pos": a, "Fx": 0, "Fy": 0, "Fz": -P, "name": "F"}],
        "pointMoments": [],
        "distLoads": [],
    }
    sol = beam_solver.solveBeam(m2d)
    w2d = ppEval(deflection.deflection(m2d, sol, {"plane": "xz", "includeShear": False})["integration"]["vPP"], a)
    d = {
        "noeuds": [
            noeud("A", 0, appui="rotule"),
            noeud("F", a),
            noeud("B", L, appui="perso", ddl=[False, True, True, True, False, False]),
        ],
        "elements": [element(1, "A", "F"), element(2, "F", "B")],
        "charges_nodales": [{"noeud": "F", "Fz": -P}],
    }
    r = frame3d.solveFrame3D(d)
    assert r["deplacements"]["F"][2] == pytest.approx(w2d, rel=REL)
    assert r["reactions"]["A"][2] == pytest.approx(sol["reactions"][0]["Rz"], rel=REL)
    assert r["reactions"]["B"][2] == pytest.approx(sol["reactions"][1]["Rz"], rel=REL)
