"""Tests de geometry (étape E07) : portage de tests/test_GeometryEngine.m, lignes 110–375 (formes fermées, intégrales,
Huygens) et 488–733 (cisaillement, profilés, tabulée, comparaison, composites), plus testReportFormat et l'erreur de
integral reportées par E06. Golden : analytical, integral, shearFactors, compare, tabulated et erreurs.
"""

import copy
import math

import numpy as np
import pandas as pd
import pytest

from mecastruct.core import geometry as geo
from tests.golden_tools import assert_matches, case_ids, get_case
from tests.test_geometry_base import ID, IPE200, SECTIONS, UPN200, _erreur, _verifRel

SYM = pytest.mark.skipif(not geo.hasSymbolic(), reason="SymPy indisponible")
INTERDITS = [
    "\\iint",
    "\\iiint",
    "\\implies",
    "\\text{",
    "\\dfrac",
    "\\tfrac",
    "\\boldsymbol",
    "\\geqslant",
    "\\leqslant",
    "pmatrix",
    "bmatrix",
    "{align",
    "{cases",
]


def _propDiff(A: dict, B: dict) -> float:
    """Écart relatif maximal entre deux jeux de propriétés (Iyz rapporté à max(Iz, Iy)), comme propDiff de MATLAB."""
    flds = [
        "S",
        "yG",
        "zG",
        "MO1z",
        "MO1y",
        "Iz",
        "Iy",
        "Iyz",
        "Ix",
        "I1",
        "I2",
        "rz",
        "ry",
        "vyTop",
        "vyBot",
        "vzRight",
    ]
    flds += ["vzLeft", "Wz", "Wy"]
    Lref = max(A["bbox"][1] - A["bbox"][0], A["bbox"][3] - A["bbox"][2])
    d = 0.0
    for nom in flds:
        a, b = A[nom], B[nom]
        if nom == "Iyz":
            den = max(abs(a), abs(A["Iz"]), abs(A["Iy"]))
        elif nom in ("yG", "zG", "vyTop", "vyBot", "vzRight", "vzLeft"):
            den = max(abs(a), Lref)
        elif nom in ("MO1z", "MO1y"):
            den = max(abs(a), A["S"] * Lref)
        else:
            den = abs(a)
        d = max(d, abs(a - b) / den if den > 0 else (0.0 if a == b else math.inf))
    if A["Iyz"] != 0 or B["Iyz"] != 0:
        d = max(d, abs(A["alphaP"] - B["alphaP"]))
    return d


# -------------------------------------------------------------------------------------
#  Formules fermées (MATLAB 110–151, 153–205, 207–269)
# -------------------------------------------------------------------------------------


def test_rectangle_forme_fermee():
    b, h = 0.1, 0.2
    P = geo.analytical({"type": "rectangle", "b": b, "h": h})
    _verifRel(P["S"], b * h, 1e-12)
    _verifRel(P["Iz"], b * h**3 / 12, 1e-12)
    _verifRel(P["Iy"], h * b**3 / 12, 1e-12)
    assert P["Iyz"] == 0
    _verifRel(P["Ix"], b * h**3 / 12 + h * b**3 / 12, 1e-12)
    _verifRel([P["yG"], P["zG"]], [h / 2, b / 2], 1e-12)
    _verifRel([P["MO1z"], P["MO1y"]], [b * h * h / 2, b * h * b / 2], 1e-12)
    _verifRel([P["I1"], P["I2"]], [b * h**3 / 12, h * b**3 / 12], 1e-12)
    assert P["alphaP"] == 0
    _verifRel([P["rz"], P["ry"]], [h / math.sqrt(12), b / math.sqrt(12)], 1e-12)
    _verifRel([P["vyTop"], P["vyBot"], P["vzRight"], P["vzLeft"]], [h / 2, h / 2, b / 2, b / 2], 1e-12)
    _verifRel([P["Wz"], P["Wy"]], [b * h**2 / 6, h * b**2 / 6], 1e-12)
    assert P["method"] == "analytique"
    assert P["kSource"] == "cours"
    _verifRel([P["k"], P["ky"]], [3 / 2, 5 / 6], 1e-12)


def test_rectangle_plus_large_que_haut():
    # b > h : l'axe principal 1 (inertie max) est l'axe y, alphaP = pi/2
    P = geo.analytical({"type": "rectangle", "b": 0.3, "h": 0.1})
    _verifRel(P["I1"], P["Iy"], 1e-12)
    _verifRel(P["I2"], P["Iz"], 1e-12)
    _verifRel(P["alphaP"], math.pi / 2, 1e-12)


def test_rectangle_saint_venant():
    # beta = J/(a c³) : valeurs de référence (Timoshenko) 1 -> 0.1406, 2 -> 0.2287, 10 -> 0.3123
    c = 0.02
    for ratio, beta_ref in zip([1, 2, 10], [0.1406, 0.2287, 0.3123]):
        P = geo.analytical({"type": "rectangle", "b": c, "h": ratio * c})
        assert abs(P["J"] / (ratio * c * c**3) - beta_ref) <= 2e-4
    # grand allongement : J -> a c³/3 (1 − 0,630 c/a)
    P = geo.analytical({"type": "rectangle", "b": 0.001, "h": 1})
    n = np.arange(1, 200, 2)
    _verifRel(P["J"], 0.001**3 / 3 * (1 - 192 / math.pi**5 * 0.001 * np.sum(1 / n**5)), 1e-9)


def test_disque():
    D = 0.1
    P = geo.analytical({"type": "disque", "D": D})
    _verifRel(P["S"], math.pi * D**2 / 4, 1e-12)
    _verifRel([P["Iz"], P["Iy"]], [math.pi * D**4 / 64] * 2, 1e-12)
    _verifRel(P["Ix"], math.pi * D**4 / 32, 1e-12)
    _verifRel(P["J"], math.pi * D**4 / 32, 1e-12)
    _verifRel([P["yG"], P["zG"]], [D / 2, D / 2], 1e-12)
    _verifRel(P["Wz"], math.pi * D**3 / 32, 1e-12)
    _verifRel(P["rz"], D / 4, 1e-12)
    assert P["alphaP"] == 0


def test_couronne():
    D, d = 0.1, 0.06
    m = d / D
    P = geo.analytical({"type": "couronne", "D": D, "d": d})
    _verifRel(P["S"], math.pi * D**2 / 4 * (1 - m**2), 1e-12)
    _verifRel([P["Iz"], P["Iy"]], [math.pi * D**4 / 64 * (1 - m**4)] * 2, 1e-12)
    _verifRel(P["Ix"], math.pi * D**4 / 32 * (1 - m**4), 1e-12)
    _verifRel(P["J"], math.pi * (D**4 - d**4) / 32, 1e-12)
    _verifRel(P["Wz"], math.pi * D**3 / 32 * (1 - m**4), 1e-12)
    # couronne d = 0 : identique au disque
    P0 = geo.analytical({"type": "couronne", "D": D, "d": 0})
    Pd = geo.analytical({"type": "disque", "D": D})
    _verifRel([P0["S"], P0["Iz"], P0["Ix"]], [Pd["S"], Pd["Iz"], Pd["Ix"]], 1e-12)


def test_rectangle_creux():
    B, H, t = 0.1, 0.2, 0.01
    P = geo.analytical({"type": "rectangle_creux", "B": B, "H": H, "t": t})
    _verifRel(P["S"], B * H - (B - 2 * t) * (H - 2 * t), 1e-12)
    _verifRel(P["Iz"], (B * H**3 - (B - 2 * t) * (H - 2 * t) ** 3) / 12, 1e-12)
    _verifRel(P["Iy"], (H * B**3 - (H - 2 * t) * (B - 2 * t) ** 3) / 12, 1e-12)
    Am = (B - t) * (H - t)
    pm = 2 * ((B - t) + (H - t))
    _verifRel(P["J"], 4 * Am**2 * t / pm, 1e-12)
    assert len(P["huygens"]) == 2
    assert P["huygens"]["S_i"].iloc[1] < 0


def test_section_i():
    h, b, tw, tf = 0.2, 0.1, 0.0056, 0.0085
    P = geo.analytical({"type": "I", "h": h, "b": b, "tw": tw, "tf": tf})
    _verifRel(P["S"], 2 * b * tf + (h - 2 * tf) * tw, 1e-12)
    _verifRel(P["Iz"], (b * h**3 - (b - tw) * (h - 2 * tf) ** 3) / 12, 1e-12)
    _verifRel(P["Iy"], (2 * tf * b**3 + (h - 2 * tf) * tw**3) / 12, 1e-12)
    _verifRel([P["yG"], P["zG"]], [h / 2, b / 2], 1e-12)
    assert P["Iyz"] == 0
    _verifRel(P["J"], (2 * b * tf**3 + (h - 2 * tf) * tw**3) / 3, 1e-12)
    Sw = tw * (h - 2 * tf)
    _verifRel([P["k"], P["ky"]], [P["S"] / Sw, Sw / P["S"]], 1e-12)
    assert list(P["huygens"]["Label"]) == ["Aile inférieure", "Âme", "Aile supérieure"]


def test_section_t():
    h, b, tw, tf = 0.1, 0.08, 0.008, 0.01
    P = geo.analytical({"type": "T", "h": h, "b": b, "tw": tw, "tf": tf})
    S = tw * (h - tf) + b * tf
    yG = (tw * (h - tf) ** 2 / 2 + b * tf * (h - tf / 2)) / S
    IO1z = tw * (h - tf) ** 3 / 3 + b * (h**3 - (h - tf) ** 3) / 3
    _verifRel(P["S"], S, 1e-12)
    _verifRel(P["yG"], yG, 1e-12)
    _verifRel(P["zG"], b / 2, 1e-12)
    _verifRel(P["Iz"], IO1z - S * yG**2, 1e-12)
    _verifRel(P["Iy"], (h - tf) * tw**3 / 12 + tf * b**3 / 12, 1e-12)
    assert P["Iyz"] == 0
    _verifRel([P["vyTop"], P["vyBot"]], [h - yG, yG], 1e-12)
    _verifRel(P["Wz"], P["Iz"] / yG, 1e-12)
    assert P["kSource"] == "numérique"


def test_section_u():
    h, b, tw, tf = 0.2, 0.075, 0.0085, 0.0115
    P = geo.analytical({"type": "U", "h": h, "b": b, "tw": tw, "tf": tf})
    S = h * tw + 2 * (b - tw) * tf
    zG = (h * tw**2 / 2 + 2 * tf * (b**2 - tw**2) / 2) / S
    IO1y = h * tw**3 / 3 + 2 * tf * (b**3 - tw**3) / 3
    _verifRel(P["S"], S, 1e-12)
    _verifRel(P["zG"], zG, 1e-12)
    _verifRel(P["yG"], h / 2, 1e-12)
    _verifRel(P["Iz"], (b * h**3 - (b - tw) * (h - 2 * tf) ** 3) / 12, 1e-12)
    _verifRel(P["Iy"], IO1y - S * zG**2, 1e-12)
    _verifRel([P["vzLeft"], P["vzRight"]], [zG, b - zG], 1e-12)
    _verifRel(P["Wy"], P["Iy"] / (b - zG), 1e-12)
    _verifRel(P["J"], (h * tw**3 + 2 * (b - tw) * tf**3) / 3, 1e-12)


@pytest.mark.parametrize("h, b, t", [(0.1, 0.1, 0.01), (0.12, 0.08, 0.012)], ids=["egale", "inegale"])
def test_cornieres_l(h, b, t):
    P = geo.analytical({"type": "L", "h": h, "b": b, "t": t})
    S = t * h + (b - t) * t
    yG = (t * h**2 / 2 + (b - t) * t**2 / 2) / S
    zG = (h * t**2 / 2 + t * (b**2 - t**2) / 2) / S
    Iz = t * h**3 / 3 + (b - t) * t**3 / 3 - S * yG**2
    Iy = h * t**3 / 3 + t * (b**3 - t**3) / 3 - S * zG**2
    Iyz = t**2 * h**2 / 4 + (b**2 - t**2) * t**2 / 4 - S * yG * zG
    _verifRel([P["S"], P["yG"], P["zG"]], [S, yG, zG], 1e-12)
    _verifRel([P["Iz"], P["Iy"]], [Iz, Iy], 1e-12)
    _verifRel(P["Iyz"], Iyz, 1e-11)
    assert P["Iyz"] < 0, "Iyz < 0 pour une cornière à angle en bas à gauche"
    # invariants des axes principaux
    _verifRel(P["I1"] + P["I2"], Iz + Iy, 1e-12)
    _verifRel(P["I1"] * P["I2"], Iz * Iy - Iyz**2, 1e-10)
    assert P["I1"] >= P["I2"]

    # I(alpha) = Iz cos² + Iy sin² − 2 Iyz sin cos : maximum en alphaP
    def Ia(a):
        return Iz * np.cos(a) ** 2 + Iy * np.sin(a) ** 2 - 2 * Iyz * np.sin(a) * np.cos(a)

    _verifRel(Ia(P["alphaP"]), P["I1"], 1e-11)
    _verifRel(Ia(P["alphaP"] + math.pi / 2), P["I2"], 1e-10)
    assert Ia(np.linspace(-math.pi / 2, math.pi / 2, 2001)).max() <= P["I1"] * (1 + 1e-12)
    _verifRel(P["J"], (h * t**3 + (b - t) * t**3) / 3, 1e-12)


def test_corniere_l_angle_45():
    P = geo.analytical({"type": "L", "h": 0.1, "b": 0.1, "t": 0.01})
    _verifRel(P["alphaP"], math.pi / 4, 1e-12)


# -------------------------------------------------------------------------------------
#  Analytique ≡ intégrale (MATLAB 275–339)
# -------------------------------------------------------------------------------------


@SYM
@pytest.mark.parametrize("nom, sec", SECTIONS, ids=[n for n, _ in SECTIONS])
def test_analytique_egale_integrale_symbolique(nom, sec):
    A = geo.analytical(sec)
    B = geo.integral(sec, "symbolique")
    assert B["methodUsed"] == "symbolique"
    assert B["method"] == "intégrale symbolique"
    assert _propDiff(A, B) <= 1e-9
    _verifRel(B["IxDirect"], B["Iz"] + B["Iy"], 1e-12)
    if math.isnan(A["J"]):
        assert math.isnan(B["J"])
    else:
        _verifRel(B["J"], A["J"], 1e-9)


@pytest.mark.parametrize("nom, sec", SECTIONS, ids=[n for n, _ in SECTIONS])
def test_analytique_egale_integrale_numerique(nom, sec):
    A = geo.analytical(sec)
    N = geo.integral(sec, "numerique")
    assert N["methodUsed"] == "numérique"
    assert N["method"] == "intégrale numérique"
    assert _propDiff(A, N) <= 1e-9
    _verifRel(N["IxDirect"], N["Iz"] + N["Iy"], 1e-10)


def test_integral_champs_et_mode_par_defaut():
    sec = {"type": "I", "h": 0.2, "b": 0.1, "tw": 0.0056, "tf": 0.0085}
    P = geo.integral(sec)
    assert P["methodUsed"] == ("symbolique" if geo.hasSymbolic() else "numérique")
    assert all(isinstance(s, str) for s in P["integrals"])
    assert len(P["integrals"]) == 7 * 3
    assert all(s.startswith("$") and s.endswith("$") for s in P["integrals"])
    assert r"\int_{0}^{0.1}\!\!\int_{0}^{0.0085}" in P["integrals"][0]
    champs = [
        "S",
        "zG",
        "yG",
        "Iz",
        "Iy",
        "Iyz",
        "Ix",
        "J",
        "I1",
        "I2",
        "alphaP",
        "rz",
        "ry",
        "vyTop",
        "vyBot",
        "vzRight",
        "vzLeft",
        "Wz",
        "Wy",
        "MO1z",
        "MO1y",
        "k",
        "ky",
        "kSource",
        "method",
        "report",
        "latex",
        "integrals",
        "methodUsed",
    ]
    assert all(k in P for k in champs)
    assert "huygens" not in P
    # disque : intégrale en coordonnées polaires
    Pd = geo.integral({"type": "disque", "D": 0.1}, "numerique")
    assert r"r\,dr\,d\theta" in Pd["integrals"][0]
    # alias de mode
    assert geo.integral(sec, "numérique")["methodUsed"] == "numérique"


def test_integral_mode_inconnu():
    _erreur(ID + "unknownMode", geo.integral, {"type": "rectangle", "b": 0.1, "h": 0.2}, "monte-carlo")


def test_analytical_champs():
    P = geo.analytical({"type": "T", "h": 0.1, "b": 0.08, "tw": 0.008, "tf": 0.01})
    champs = [
        "S",
        "zG",
        "yG",
        "Iz",
        "Iy",
        "Iyz",
        "Ix",
        "J",
        "I1",
        "I2",
        "alphaP",
        "rz",
        "ry",
        "vyTop",
        "vyBot",
        "vzRight",
        "vzLeft",
        "Wz",
        "Wy",
        "MO1z",
        "MO1y",
        "k",
        "ky",
        "kSource",
        "method",
        "report",
        "latex",
        "huygens",
    ]
    assert all(k in P for k in champs)
    _verifRel(P["Ix"], P["Iz"] + P["Iy"], 1e-15)
    _verifRel(P["yG"], P["MO1z"] / P["S"], 1e-15)
    _verifRel(P["zG"], P["MO1y"] / P["S"], 1e-15)


def test_alias_types_analytical():
    P1 = geo.analytical({"type": "Rectangle", "b": 0.1, "h": 0.2})
    P2 = geo.analytical({"type": "rectangle", "b": 0.1, "h": 0.2})
    assert P1["Iz"] == P2["Iz"]
    P3 = geo.analytical({"type": "i", "h": 0.2, "b": 0.1, "tw": 0.0056, "tf": 0.0085})
    assert P3["type"] == "I"


# -------------------------------------------------------------------------------------
#  Huygens (MATLAB 345–370)
# -------------------------------------------------------------------------------------


@pytest.mark.parametrize("nom, sec", SECTIONS, ids=[n for n, _ in SECTIONS])
def test_huygens_table(nom, sec):
    P = geo.analytical(sec)
    T = P["huygens"]
    assert isinstance(T, pd.DataFrame)
    cols = ["Label", "S_i", "zG_i", "yG_i", "IGz_i", "IGy_i", "dy_i", "dz_i", "SDy2", "SDz2", "Iz_i", "Iy_i"]
    assert all(c in T.columns for c in cols)
    _verifRel(T["S_i"].sum(), P["S"], 1e-12)
    _verifRel(T["Iz_i"].sum(), P["Iz"], 1e-12)
    _verifRel(T["Iy_i"].sum(), P["Iy"], 1e-12)
    _verifRel((T["S_i"] * T["yG_i"]).sum() / T["S_i"].sum(), P["yG"], 1e-12)
    _verifRel(T["SDy2"], T["S_i"] * T["dy_i"] ** 2, 1e-12)
    _verifRel(T["SDz2"], T["S_i"] * T["dz_i"] ** 2, 1e-12)
    _verifRel(T["Iz_i"], T["IGz_i"] + T["SDy2"], 1e-12)
    _verifRel(T["Iy_i"], T["IGy_i"] + T["SDz2"], 1e-12)
    assert abs(T["SDyDz"].sum() - P["Iyz"]) <= 1e-12 * max(P["Iz"], P["Iy"])


def test_huygens_section_i_explicite():
    h, b, tw, tf = 0.2, 0.1, 0.0056, 0.0085
    T = geo.analytical({"type": "I", "h": h, "b": b, "tw": tw, "tf": tf})["huygens"]
    _verifRel(T["dy_i"].iloc[0], -(h / 2 - tf / 2), 1e-12)
    _verifRel(T["SDy2"].iloc[2], b * tf * (h / 2 - tf / 2) ** 2, 1e-12)
    _verifRel(T["IGz_i"].iloc[1], tw * (h - 2 * tf) ** 3 / 12, 1e-12)


# -------------------------------------------------------------------------------------
#  Facteurs de cisaillement (MATLAB 488–575)
# -------------------------------------------------------------------------------------


def test_shear_factors_rectangle():
    f = geo.shearFactors({"type": "rectangle", "b": 0.1, "h": 0.2})
    assert f["kCours"] == 3 / 2
    assert f["kyCours"] == 5 / 6
    _verifRel(f["kNum"], 3 / 2, 1e-9)
    _verifRel(f["kyNum"], 5 / 6, 1e-9)
    assert abs(f["yAtMax"]) <= 1e-12
    assert f["connected"]
    assert all(isinstance(s, str) for s in f["report"] + f["latex"])


def test_jourawski_rectangle_max():
    # tau(y) = T·Q(y)/(Iz·b(y)) : maximum 1,5 T/S en G, parabole 3/2 T/S (1 − (2y/h)²)
    b, h, T = 0.1, 0.2, 1e4
    sec = {"type": "rectangle", "b": b, "h": h}
    P = geo.analytical(sec)
    y = np.linspace(-h / 2, h / 2, 101)
    tau = T * geo.firstMomentAbove(sec, y) / (P["Iz"] * geo.widthAt(sec, y))
    assert np.max(np.abs(tau - 1.5 * T / (b * h) * (1 - (2 * y / h) ** 2))) <= 1e-9 * T / (b * h)
    _verifRel(tau.max(), 1.5 * T / P["S"], 1e-12)
    _verifRel(P["shear"]["kNum"] * T / P["S"], 1.5 * T / P["S"], 1e-9)


def test_shear_factors_disque():
    f = geo.shearFactors({"type": "disque", "D": 0.08})
    _verifRel(f["kNum"], 4 / 3, 1e-9)
    _verifRel(f["kyNum"], 9 / 10, 1e-9)  # intégration exacte : 9/10 (cours : 6/7, élasticité)
    assert f["kCours"] == 4 / 3
    assert f["kyCours"] == 6 / 7
    assert any("9/10" in s for s in f["report"])


def test_shear_factors_couronne():
    D, d = 0.1, 0.08
    R, r = D / 2, d / 2
    f = geo.shearFactors({"type": "couronne", "D": D, "d": d})
    _verifRel(f["kCours"], 4 / 3 * (1 + r * R / (r**2 + R**2)), 1e-12)
    _verifRel(f["kNum"], 4 / 3 * (1 + r * R / (r**2 + R**2)), 1e-9)
    assert f["kyCours"] == 1 / 2
    # tube mince : Jourawski (coupes horizontales) -> ky = 2/3 ; k -> 2
    ft = geo.shearFactors({"type": "couronne", "D": 0.1, "d": 0.0998})
    _verifRel(ft["kNum"], 2, 1e-5)
    _verifRel(ft["kyNum"], 2 / 3, 2e-2)


def test_shear_factors_i():
    h, b, tw, tf = 0.2, 0.1, 0.0056, 0.0085
    sec = {"type": "I", "h": h, "b": b, "tw": tw, "tf": tf}
    f = geo.shearFactors(sec)
    P = geo.analytical(sec)
    Sw = tw * (h - 2 * tf)
    _verifRel(f["Sweb"], Sw, 1e-12)
    _verifRel(f["kCours"], P["S"] / Sw, 1e-12)
    _verifRel(f["kyCours"], Sw / P["S"], 1e-12)
    Q0 = b * tf * (h / 2 - tf / 2) + tw * (h / 2 - tf) ** 2 / 2
    _verifRel(f["kNum"], P["S"] * Q0 / (P["Iz"] * tw), 1e-9)
    assert 0 < f["kyNum"] < 1


def test_shear_factors_composite_rectangle_et_t():
    # composite d'un seul rectangle : valeurs exactes 3/2 et 5/6 retrouvées numériquement
    f = geo.shearFactors({"type": "composite", "rects": [[1, 1.1, 2, 2.3]]})
    assert math.isnan(f["kCours"])
    _verifRel(f["kNum"], 3 / 2, 1e-9)
    _verifRel(f["kyNum"], 5 / 6, 1e-9)
    # T : maximum de tau en G (dans l'âme)
    sec = {"type": "T", "h": 0.1, "b": 0.08, "tw": 0.008, "tf": 0.01}
    P = geo.analytical(sec)
    fT = geo.shearFactors(sec)
    _verifRel(fT["kNum"], P["S"] * geo.firstMomentAbove(sec, 0.0) / (P["Iz"] * 0.008), 1e-9)
    assert P["k"] == fT["kNum"]
    assert P["ky"] == fT["kyNum"]


def test_shear_factors_disconnected():
    sec = {"type": "composite", "rects": [[0, 0.1, 0, 0.02], [0, 0.1, 0.08, 0.1]]}
    f = geo.shearFactors(sec)
    assert not f["connected"]
    assert math.isnan(f["kNum"]) and math.isnan(f["kyNum"])
    P = geo.analytical(sec)
    _verifRel(P["Iz"], 2 * (0.1 * 0.02**3 / 12 + 0.1 * 0.02 * 0.04**2), 1e-12)
    assert math.isnan(P["k"]) and math.isnan(P["ky"])
    # disque posé sur un rectangle (contact ponctuel) : étranglement détecté
    fc = geo.shearFactors({"type": "composite", "rects": [[-0.05, 0.05, -0.1, 0]], "disks": [[0, 0.03, 0.03]]})
    assert not fc["connected"]
    assert math.isnan(fc["kNum"])


# -------------------------------------------------------------------------------------
#  Profilés, valeurs tabulées, comparaison (MATLAB 581–676)
# -------------------------------------------------------------------------------------


def test_profile_ipe_analytical():
    P = geo.analytical(IPE200)
    PI = geo.analytical({"type": "I", "h": 0.2, "b": 0.1, "tw": 0.0056, "tf": 0.0085})
    assert _propDiff(PI, P) <= 1e-14
    assert any("géométrie simplifiée" in s for s in P["report"])
    _verifRel(P["S"], 27.248e-4, 1e-12)


def test_tabulated_ipe():
    T = geo.tabulated(IPE200)
    assert T["method"] == "tabulée"
    assert [T["S"], T["Iz"], T["Iy"], T["Wz"], T["Wy"], T["rz"], T["ry"]] == [
        28.5e-4,
        1943e-8,
        142.4e-8,
        194.3e-6,
        28.47e-6,
        0.0826,
        0.0224,
    ]
    assert [T["yG"], T["zG"], T["Iyz"]] == [0.1, 0.05, 0]
    _verifRel(T["Ix"], 1943e-8 + 142.4e-8, 1e-15)
    _verifRel([T["I1"], T["I2"]], [1943e-8, 142.4e-8], 1e-12)
    assert T["alphaP"] == 0
    Sw = 0.0056 * (0.2 - 2 * 0.0085)
    _verifRel([T["k"], T["ky"]], [28.5e-4 / Sw, Sw / 28.5e-4], 1e-12)
    assert math.isnan(T["J"])
    assert all(isinstance(s, str) for s in T["report"])
    # valeurs absentes : déduites
    s2 = {k: v for k, v in IPE200.items() if k not in ("rz", "ry", "Wz", "Wy")}
    T2 = geo.tabulated(s2)
    _verifRel(
        [T2["rz"], T2["ry"], T2["Wz"], T2["Wy"]],
        [math.sqrt(1943e-8 / 28.5e-4), math.sqrt(142.4e-8 / 28.5e-4), 1943e-8 / 0.1, 142.4e-8 / 0.05],
        1e-12,
    )


def test_tabulated_upn():
    T = geo.tabulated(UPN200)
    assert T["zG"] == 0.0201
    _verifRel([T["vzLeft"], T["vzRight"]], [0.0201, 0.075 - 0.0201], 1e-12)
    assert T["kSource"] == "numérique"
    P = geo.analytical(UPN200)
    h, b, tw, tf = 0.2, 0.075, 0.0085, 0.0115
    S = h * tw + 2 * (b - tw) * tf
    _verifRel(P["S"], S, 1e-12)
    _verifRel(P["zG"], (h * tw**2 / 2 + 2 * tf * (b**2 - tw**2) / 2) / S, 1e-12)
    # famille déduite du nom ou de c
    s2 = {k: v for k, v in UPN200.items() if k != "family"}
    assert geo.validateSection(s2)["profileShape"] == "U"
    s3 = {k: v for k, v in UPN200.items() if k not in ("family", "name")}
    assert geo.validateSection(s3)["profileShape"] == "U"


def test_tabulated_erreurs():
    _erreur(ID + "notProfile", geo.tabulated, {"type": "rectangle", "b": 0.1, "h": 0.2})
    s = {k: v for k, v in IPE200.items() if k != "Iz"}
    _erreur(ID + "missingField", geo.tabulated, s)


def test_compare_profile():
    C = geo.compare(IPE200)
    assert isinstance(C, pd.DataFrame)
    assert list(C.index) == ["S", "yG", "zG", "Iz", "Iy", "Iyz", "Ix", "rz", "ry", "Wz", "Wy"]
    assert list(C.columns) == ["Analytique", "Integrale", "Tabulee", "EcartMax_pct"]
    _verifRel(C["Analytique"], C["Integrale"], 1e-9)
    assert C.loc["Iz", "Tabulee"] == 1943e-8
    # écart attendu de quelques % (congés) : rapporté, pas caché
    assert 1 < C.loc["Iz", "EcartMax_pct"] < 10
    _verifRel(C.loc["S", "EcartMax_pct"], 100 * (28.5e-4 - 27.248e-4) / 28.5e-4, 1e-9)
    assert C.loc["yG", "EcartMax_pct"] < 1e-9
    assert C.loc["Iyz", "EcartMax_pct"] == 0
    assert any("congés" in s for s in C.attrs["report"])
    assert isinstance(C.attrs["tabulated"], dict)


SECTIONS_HORS_PROFILE = [(n, s) for n, s in SECTIONS if s["type"] != "profile"]


@pytest.mark.parametrize("nom, sec", SECTIONS_HORS_PROFILE, ids=[n for n, _ in SECTIONS_HORS_PROFILE])
def test_compare_non_profile(nom, sec):
    C = geo.compare(sec)
    assert C["Tabulee"].isna().all()
    assert C["EcartMax_pct"].max() < 1e-7


def test_from_profile():
    p = {
        "Family": "IPE",
        "Name": "IPE 200",
        "h": 0.2,
        "b": 0.1,
        "a": 0.0056,
        "e": 0.0085,
        "r": 0.012,
        "S": 28.5e-4,
        "Iz": 1943e-8,
        "Iy": 142.4e-8,
        "Wz": 194.3e-6,
        "Wy": 28.47e-6,
        "rz": 0.0826,
        "ry": 0.0224,
        "mass": 22.4,
        "c": math.nan,
    }
    sec = geo.fromProfile(p)
    assert sec["type"] == "profile"
    assert sec["family"] == "IPE"
    assert sec["name"] == "IPE 200"
    assert sec["profileShape"] == "I"
    assert geo.tabulated(sec)["Iz"] == 1943e-8


# -------------------------------------------------------------------------------------
#  Composites (MATLAB 682–728)
# -------------------------------------------------------------------------------------


def test_composite_egal_i():
    h, b, tw, tf = 0.2, 0.1, 0.0056, 0.0085
    rects = [[0, b, 0, tf], [(b - tw) / 2, (b + tw) / 2, tf, h - tf], [0, b, h - tf, h]]
    PC = geo.analytical({"type": "composite", "rects": rects})
    PI = geo.analytical({"type": "I", "h": h, "b": b, "tw": tw, "tf": tf})
    assert _propDiff(PI, PC) <= 1e-13
    _verifRel(PC["J"], PI["J"], 1e-12)
    # translation du repère utilisateur : G translaté, inerties inchangées
    shifted = [[z1 + 1, z2 + 1, y1 - 2, y2 - 2] for z1, z2, y1, y2 in rects]
    PT = geo.analytical({"type": "composite", "rects": shifted})
    _verifRel([PT["zG"], PT["yG"]], [PI["zG"] + 1, PI["yG"] - 2], 1e-12)
    _verifRel([PT["Iz"], PT["Iy"]], [PI["Iz"], PI["Iy"]], 1e-9)
    # caisson soudé (contour fermé) et carré plein coupé en deux : Σ l·t³/3 ne s'applique pas
    box = [[0, 0.1, 0, 0.005], [0, 0.1, 0.095, 0.1], [0, 0.005, 0.005, 0.095], [0.095, 0.1, 0.005, 0.095]]
    assert math.isnan(geo.analytical({"type": "composite", "rects": box})["J"])
    coupe = [[0, 0.05, 0, 0.1], [0.05, 0.1, 0, 0.1]]
    assert math.isnan(geo.analytical({"type": "composite", "rects": coupe})["J"])
    # kz (tranchant Tz) : rectangle plat -> 5/6 aussi ; profil en I -> les ailes travaillent, kz > ky
    Pr = geo.analytical({"type": "composite", "rects": [[0, 0.3, 0, 0.1]]})
    _verifRel(Pr["kz"], 5 / 6, 1e-6)
    Sf = 2 * b * tf / PI["S"]  # part d'aire des ailes : borne haute de kz
    assert PI["kz"] > 0.85 * Sf
    assert PI["kz"] < Sf
    assert PI["kz"] > PI["ky"]
    # couronne d = 0 : même ky que le disque
    Pc = geo.analytical({"type": "couronne", "D": 0.1, "d": 0})
    _verifRel(Pc["ky"], 6 / 7, 1e-12)


def test_composite_trous():
    # plaque percée d'un trou circulaire centré
    sec = {"type": "composite", "rects": [[0, 0.2, 0, 0.1]], "diskHoles": [[0.1, 0.05, 0.03]]}
    P = geo.analytical(sec)
    R = 0.03
    _verifRel(P["S"], 0.02 - math.pi * R**2, 1e-12)
    _verifRel(P["Iz"], 0.2 * 0.1**3 / 12 - math.pi * R**4 / 4, 1e-12)
    _verifRel(P["Iy"], 0.1 * 0.2**3 / 12 - math.pi * R**4 / 4, 1e-12)
    assert math.isnan(P["J"])
    _verifRel(geo.widthAt(sec, 0), 0.2 - 2 * R, 1e-12)
    # trou rectangulaire excentré : Huygens avec aire négative
    sec2 = {"type": "composite", "rects": [[0, 0.1, 0, 0.2]], "holes": [[0.02, 0.04, 0.02, 0.06]]}
    P2 = geo.analytical(sec2)
    S = 0.02 - 0.0008
    yG = (0.02 * 0.1 - 0.0008 * 0.04) / S
    Iz = 0.1 * 0.2**3 / 12 + 0.02 * (0.1 - yG) ** 2 - (0.02 * 0.04**3 / 12 + 0.0008 * (0.04 - yG) ** 2)
    _verifRel([P2["S"], P2["yG"], P2["Iz"]], [S, yG, Iz], 1e-12)
    assert P2["huygens"]["S_i"].iloc[1] < 0
    assert P2["Iyz"] != 0


# -------------------------------------------------------------------------------------
#  Rapport, LaTeX (MATLAB 804–859, partie sans rendu) : reporté par E06
# -------------------------------------------------------------------------------------


@pytest.mark.parametrize("nom, sec", SECTIONS, ids=[n for n, _ in SECTIONS])
def test_format_rapport(nom, sec):
    for P in (geo.analytical(sec), geo.integral(sec, "numerique"), geo.shearFactors(sec)):
        assert isinstance(P["report"], list) and P["report"]
        assert all(isinstance(s, str) for s in P["report"])
        assert all(isinstance(s, str) for s in P["latex"])


def test_latex_valide():
    strs = []
    for _, sec in SECTIONS:
        N = geo.integral(sec, "numerique")
        strs += geo.analytical(sec)["latex"] + N["latex"] + N["integrals"]
        if sec["type"] == "profile":
            strs += geo.tabulated(sec)["latex"]
    if geo.hasSymbolic():
        B = geo.integral(SECTIONS[4][1], "symbolique")
        strs += B["latex"] + B["integrals"]
    for s in strs:
        assert s.isascii(), s
        assert len(s) < 1000
        assert s.startswith("$") and s.endswith("$"), s
        assert not any(f in s for f in INTERDITS), s


# -------------------------------------------------------------------------------------
#  Golden files (MATLAB) et erreurs attendues
# -------------------------------------------------------------------------------------


# Le maximum de Q/b est plat en y = 0 pour une section symétrique : sa position (yAtMax) n'est connue qu'au bruit
# d'arrondi près, donc le golden ne se reproduit qu'à quelques 1e-10 m (−1,74e-10 m pour couronne_60_40 en intégrale
# numérique, où MATLAB donne 0). Décision de Théo (option a) : tolérance absolue de 1e-9 m sur yAtMax seulement.
YATMAX_ABS = 1e-9  # m


def _verifie_golden(resultat: dict, sortie: dict, rel: float, abs_: float = 1e-12) -> None:
    """Compare un résultat à sa sortie golden ; yAtMax (shear.yAtMax ou yAtMax) est comparé avec abs = YATMAX_ABS."""
    autres = copy.deepcopy(sortie)
    autres.pop("yAtMax", None)
    if isinstance(autres.get("shear"), dict):
        autres["shear"].pop("yAtMax", None)
    assert_matches(resultat, autres, rel=rel, abs_=abs_)
    if "yAtMax" in sortie:
        assert_matches(resultat["yAtMax"], sortie["yAtMax"], rel=0.0, abs_=YATMAX_ABS)
    elif "yAtMax" in sortie.get("shear", {}):
        assert_matches(resultat["shear"]["yAtMax"], sortie["shear"]["yAtMax"], rel=0.0, abs_=YATMAX_ABS)


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_analytical"))
def test_golden_analytical(cid):
    c = get_case("golden_geometry.json", cid)
    _verifie_golden(geo.analytical(c["entrees"]), c["sortie"], rel=1e-9)


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_integral_num"))
def test_golden_integral_num(cid):
    c = get_case("golden_geometry.json", cid)
    _verifie_golden(geo.integral(c["entrees"]["sec"], "numerique"), c["sortie"], rel=1e-6, abs_=1e-15)


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_shearFactors"))
def test_golden_shear_factors(cid):
    c = get_case("golden_geometry.json", cid)
    _verifie_golden(geo.shearFactors(c["entrees"]), c["sortie"], rel=1e-6)


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_compare"))
def test_golden_compare(cid):
    c = get_case("golden_geometry.json", cid)
    assert_matches(geo.compare(c["entrees"]), c["sortie"], rel=1e-6)


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_tabulated"))
def test_golden_tabulated(cid):
    c = get_case("golden_geometry.json", cid)
    assert_matches(geo.tabulated(c["entrees"]), c["sortie"], rel=1e-9)


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", prefix="erreur_"))
def test_golden_erreurs(cid):
    c = get_case("golden_geometry.json", cid)
    identifiant = c["erreur"].split(" | ")[0]
    _erreur(identifiant, getattr(geo, c["fonction"].split(".")[-1]), c["entrees"])
