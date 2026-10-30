"""Tests de solicitations (étape E12).

Portage des tests de traction, cisaillement, Jourawski, matage, clavette, goupille, torsion et flexion de
tests/test_SolicitationsEngine.m, et comparaison aux golden_solicitations.json. Les tests de flèche, d'énergie et
d'intégrales de Mohr sont à l'étape E13.
"""

import math

import numpy as np
import pytest
from scipy.interpolate import CubicSpline

from mecastruct.core import geometry
from mecastruct.core import solicitations as se
from mecastruct.core.errors import MecaStructError
from tests.golden_tools import assert_matches, case_ids, get_case

GOLDEN = "golden_solicitations.json"
MANQUANT = "MecaStruct:SolicitationsEngine:missingField"
INVALIDE = "MecaStruct:SolicitationsEngine:invalidInput"


def verifier_erreur(identifiant, appel, *args):
    """Vérifie que l'appel lève une MecaStructError portant l'identifiant MATLAB attendu."""
    with pytest.raises(MecaStructError) as info:
        appel(*args)
    assert info.value.identifier == identifiant


def verifier_latex(lignes):
    """Chaînes LaTeX en ASCII et accolades équilibrées (le rendu MathJax n'est pas testé ici)."""
    for ligne in lignes:
        assert ligne.isascii(), ligne
        assert ligne.count("{") == ligne.count("}"), ligne


# ------------------------------------------------------------------ traction


def test_traction_trois_methodes():
    p = {"N": 5e4, "S0": 2e-4, "L0": 1.5, "E": 2e11, "nu": 0.3, "Re": 355e6, "s": 2}
    r = se.traction(p)
    ref = 5e4 * 1.5 / (2e11 * 2e-4)
    assert r["dL"]["analytique"] == pytest.approx(ref, rel=1e-12)
    assert r["dL"]["integrale"] == pytest.approx(ref, rel=1e-9)
    assert r["dL"]["energetique"] == pytest.approx(ref, rel=1e-9)
    assert r["sigmaNom"] == pytest.approx(2.5e8, rel=1e-12)
    assert r["sigmaAdm"] == pytest.approx(177.5e6, rel=1e-12)
    assert not r["okResistance"]
    assert r["K"] == pytest.approx(2e11 * 2e-4 / 1.5, rel=1e-12)
    assert r["U"] == pytest.approx(0.5 * 5e4 * ref, rel=1e-9)  # Clapeyron
    assert r["epsyy"] == pytest.approx(-0.3 * r["epsxx"], rel=1e-12)
    assert r["dVsurV"] == pytest.approx(0.4 * r["sigmaNom"] / 2e11, rel=1e-12)
    assert r["dVsurV"] == pytest.approx(r["epsxx"] + r["epsyy"] + r["epszz"], rel=1e-12)
    verifier_latex(r["latex"])
    assert isinstance(r["report"], list)


def test_traction_section_variable_verdict():
    # barre conique S(x) = 100 − 50x mm² sous 10 kN : la section la plus chargée (200 MPa) décide
    p = {"N": 10e3, "S0": 100e-6, "L0": 1, "E": 210e9, "Re": 235e6, "s": 1.5, "Sfun": lambda x: (100 - 50 * x) * 1e-6}
    r = se.traction(p)
    assert r["sigmaMax"] == pytest.approx(200e6, rel=1e-9)
    assert not r["okResistance"]
    assert r["sigmaNom"] == pytest.approx(100e6, rel=1e-12)


def test_traction_barre_conique():
    F, L, E, d1, d2 = 1e4, 0.8, 2e11, 0.02, 0.04
    p = {
        "N": F,
        "S0": math.pi * d1**2 / 4,
        "L0": L,
        "E": E,
        "Re": 235e6,
        "Sfun": lambda x: math.pi / 4 * (d1 + (d2 - d1) * x / L) ** 2,
    }
    r = se.traction(p)
    ref = 4 * F * L / (math.pi * E * d1 * d2)
    assert r["dL"]["integrale"] == pytest.approx(ref, rel=1e-9)
    assert r["dL"]["energetique"] == pytest.approx(ref, rel=1e-9)
    assert r["dL"]["analytique"] == pytest.approx(F * L / (E * math.pi * d1**2 / 4), rel=1e-12)


def test_traction_repli_numerique():
    # section donnée par un spline (pas de forme symbolique) : chemin numérique, même résultat
    F, L, E, d1, d2 = 1e4, 0.8, 2e11, 0.02, 0.04
    xs = np.linspace(0, L, 2001)
    spline = CubicSpline(xs, math.pi / 4 * (d1 + (d2 - d1) * xs / L) ** 2)
    p = {"N": F, "S0": math.pi * d1**2 / 4, "L0": L, "E": E, "Re": 235e6, "Sfun": spline}
    r = se.traction(p)
    assert r["methodUsed"] == "numérique"
    ref = 4 * F * L / (math.pi * E * d1 * d2)
    assert r["dL"]["integrale"] == pytest.approx(ref, rel=1e-7)
    assert r["dL"]["energetique"] == pytest.approx(r["dL"]["integrale"], rel=1e-9)


def test_traction_thermique():
    p = {"N": 0, "S0": 1e-4, "L0": 2, "E": 2e11, "nu": 0.3, "alpha": 12e-6, "dT": 50, "Re": 235e6, "dLmax": 2e-3}
    r = se.traction(p)
    ref = 12e-6 * 50 * 2
    assert r["dL"]["analytique"] == pytest.approx(ref, rel=1e-12)
    assert r["dL"]["integrale"] == pytest.approx(ref, rel=1e-9)
    assert r["dL"]["energetique"] == pytest.approx(ref, rel=1e-9)
    assert r["epsxx"] == pytest.approx(6e-4, rel=1e-12)
    assert r["epsyy"] == pytest.approx(6e-4, rel=1e-12)
    assert r["dVsurV"] == pytest.approx(18e-4, rel=1e-12)
    assert r["okRigidite"]
    # thermique variable : ΔT(x) = 100 x/L → ΔL = α·50·L
    p["dTfun"] = lambda x: 100 * x / 2
    r = se.traction(p)
    assert r["dL"]["integrale"] == pytest.approx(ref, rel=1e-9)
    assert r["dL"]["energetique"] == pytest.approx(ref, rel=1e-9)


def test_traction_kt_et_erreurs():
    p = {"N": -1e4, "S0": 1e-4, "L0": 1, "E": 2e11, "Kt": 2.5, "Re": 300e6}
    r = se.traction(p)
    assert r["sigmaMax"] == pytest.approx(-2.5e8, rel=1e-12)
    assert r["okResistance"]
    assert r["dL"]["analytique"] < 0
    verifier_erreur(MANQUANT, se.traction, {k: v for k, v in p.items() if k != "S0"})
    verifier_erreur(INVALIDE, se.traction, {**p, "E": -1})


# ------------------------------------------------------------------ cisaillement, Jourawski, matage


def test_cisaillement():
    p = {"T": 1e4, "S": 1e-4, "k": 1.5, "Re": 240e6, "s": 2, "G": 80e9}
    r = se.shear(p)
    assert r["tauMoy"] == pytest.approx(1e8, rel=1e-12)
    assert r["tauMax"] == pytest.approx(1.5e8, rel=1e-12)
    assert r["tauE"] == pytest.approx(120e6, rel=1e-12)
    assert r["tauAdm"] == pytest.approx(60e6, rel=1e-12)
    assert not r["ok"]
    assert r["gamma"] == pytest.approx(1e8 / 80e9, rel=1e-12)
    r = se.shear({**p, "criterion": "VonMises"})
    assert r["tauE"] == pytest.approx(240e6 / math.sqrt(3), rel=1e-12)
    r = se.shear({**p, "tauE": 200e6})
    assert r["tauE"] == 200e6
    verifier_latex(r["latex"])
    verifier_erreur(INVALIDE, se.shear, {**p, "criterion": "Rankine"})


def test_jourawski_rectangle():
    sec = {"type": "rectangle", "b": 0.1, "h": 0.2}
    T = 3e4
    prof = se.jourawski(sec, T, 201)
    S = 0.02
    assert prof["tauMax"] == pytest.approx(1.5 * T / S, rel=1e-9)
    assert prof["yAtMax"] == pytest.approx(0, abs=1e-12)
    assert prof["tauMoy"] == pytest.approx(T / S, rel=1e-12)
    assert prof["kNum"] == pytest.approx(1.5, rel=1e-9)
    np.testing.assert_allclose(prof["tau"], prof["tauParabola"], atol=1e-9 * prof["tauMax"])
    assert prof["Iz"] == pytest.approx(0.1 * 0.2**3 / 12, rel=1e-12)
    np.testing.assert_allclose([prof["tau"][0], prof["tau"][-1]], [0, 0], atol=1e-6)
    assert len(prof["y"]) == 201
    verifier_latex(prof["latex"])


def test_jourawski_i():
    h, b, tw, tf = 0.3, 0.15, 0.008, 0.012
    sec = {"type": "I", "h": h, "b": b, "tw": tw, "tf": tf}
    T = 5e4
    prof = se.jourawski(sec, T, 301)
    Iz = b * h**3 / 12 - (b - tw) * (h - 2 * tf) ** 3 / 12
    Q0 = b * tf * (h / 2 - tf / 2) + tw * (h / 2 - tf) ** 2 / 2
    assert prof["Iz"] == pytest.approx(Iz, rel=1e-10)
    assert prof["tauMax"] == pytest.approx(T * Q0 / (Iz * tw), rel=1e-9)
    assert prof["yAtMax"] == pytest.approx(0, abs=1e-12)
    assert np.all(np.isnan(prof["tauParabola"]))
    # âme : τ ≈ T/S_âme à quelques % près (formule approchée du cours)
    assert prof["tauMax"] == pytest.approx(T / (tw * (h - 2 * tf)), rel=0.15)


def test_matage():
    r = se.bearing({"F": 2e4, "Smatee": 4e-4, "Padm": 40e6})
    assert r["P"] == pytest.approx(5e7, rel=1e-12)
    assert not r["ok"]
    assert r["SminRequired"] == pytest.approx(5e-4, rel=1e-12)
    verifier_latex(r["latex"])


def test_clavette():
    C, D, a, b, Padm, Re = 300, 0.04, 0.012, 0.008, 60e6, 300e6
    p = {"C": C, "D": D, "a": a, "b": b, "Padm": Padm, "Re": Re, "s": 1.5, "L": 0.05}
    r = se.keyDesign(p)
    tadm = Re / 2 / 1.5
    assert r["F"] == pytest.approx(2 * C / D, rel=1e-12)
    assert r["LminMatage"] == pytest.approx(4 * C / (D * b * Padm), rel=1e-12)
    assert r["LminCis"] == pytest.approx(2 * C / (a * D * tadm), rel=1e-12)
    assert r["Lmin"] == pytest.approx(max(r["LminMatage"], r["LminCis"]), rel=1e-12)
    assert r["P"] == pytest.approx(4 * C / (D * b * 0.05), rel=1e-12)
    assert r["tau"] == pytest.approx(2 * C / (a * 0.05 * D), rel=1e-12)
    assert not r["okP"]  # P = 75 MPa > 60 MPa
    assert r["okTau"]
    # au minimum de matage, P = Padm exactement
    r2 = se.keyDesign({**p, "L": r["LminMatage"]})
    assert r2["P"] == pytest.approx(Padm, rel=1e-12)
    verifier_latex(r2["latex"])
    assert "P" not in se.keyDesign({k: v for k, v in p.items() if k != "L"})


def test_goupille():
    F, d, e, Padm = 5e3, 0.008, 0.01, 100e6
    p = {"F": F, "d": d, "e": e, "Padm": Padm, "Re": 400e6, "nShear": 2}
    r = se.pinDesign(p)
    assert r["P"] == pytest.approx(2 * F / (d * e), rel=1e-12)
    assert r["tau"] == pytest.approx(4 * F / (2 * math.pi * d**2), rel=1e-12)
    assert r["eMin"] == pytest.approx(2 * F / (d * Padm), rel=1e-12)
    expected = max(math.sqrt(4 * F / (2 * math.pi * 200e6)), 2 * F / (e * Padm))
    assert r["dMin"] == pytest.approx(expected, rel=1e-12)
    assert r["okTau"]
    assert not r["okP"]
    verifier_latex(r["latex"])


# ------------------------------------------------------------------ torsion


def test_torsion_pleine():
    Mt, D, G, L = 500, 0.04, 80e9, 1.2
    p = {"Mt": Mt, "D": D, "G": G, "L": L, "Re": 300e6, "thetaAdm": 0.01}
    r = se.torsion(p)
    Ix = math.pi * D**4 / 32
    assert r["Ix"] == pytest.approx(Ix, rel=1e-12)
    assert r["tauMax"] == pytest.approx(16 * Mt / (math.pi * D**3), rel=1e-12)
    assert r["theta"] == pytest.approx(Mt / (G * Ix), rel=1e-12)
    ref = Mt * L / (G * Ix)
    assert r["phi"]["analytique"] == pytest.approx(ref, rel=1e-12)
    assert r["phi"]["integrale"] == pytest.approx(ref, rel=1e-9)
    assert r["phi"]["energetique"] == pytest.approx(ref, rel=1e-9)
    assert r["U"] == pytest.approx(0.5 * Mt * ref, rel=1e-9)
    assert r["Ktorsion"] == pytest.approx(G * Ix / L, rel=1e-12)
    assert r["tauProfile"][-1] == pytest.approx(r["tauMaxNom"], rel=1e-12)
    assert r["tauProfile"][0] == pytest.approx(0, abs=1e-6)
    assert r["okResistance"]
    assert not r["okRigidite"]
    verifier_latex(r["latex"])


def test_torsion_creuse_et_variable():
    Mt, D, d, G, L = 800, 0.05, 0.04, 80e9, 2
    p = {"Mt": Mt, "D": D, "d": d, "G": G, "L": L, "Re": 300e6, "Kt": 1.4, "criterion": "VonMises"}
    r = se.torsion(p)
    Ix = math.pi * (D**4 - d**4) / 32
    assert r["Ix"] == pytest.approx(Ix, rel=1e-12)
    assert r["m"] == pytest.approx(0.8, rel=1e-12)
    assert r["tauMaxNom"] == pytest.approx(Mt * D / (2 * Ix), rel=1e-12)
    assert r["tauMax"] == pytest.approx(1.4 * Mt * D / (2 * Ix), rel=1e-12)
    assert r["tauAdm"] == pytest.approx(300e6 / math.sqrt(3), rel=1e-12)
    np.testing.assert_allclose(r["rProfile"][[0, -1]], [d / 2, D / 2], rtol=1e-12)
    assert r["phi"]["integrale"] == pytest.approx(Mt * L / (G * Ix), rel=1e-9)
    # moment variable Mt(s) = Mt·s/L → φ = Mt L/(2 G Ix)
    r = se.torsion({**p, "MtFun": lambda s: Mt * s / L})
    assert r["phi"]["integrale"] == pytest.approx(Mt * L / (2 * G * Ix), rel=1e-9)
    assert r["phi"]["energetique"] == pytest.approx(Mt * L / (2 * G * Ix), rel=1e-9)
    verifier_erreur(INVALIDE, se.torsion, {**p, "d": D})


# ------------------------------------------------------------------ contraintes de flexion


def test_flexion_composee_rectangle():
    b, h = 0.1, 0.2
    sec = {"type": "rectangle", "b": b, "h": h}
    Mfz, Mfy, N = 2e4, 5e3, 1e5
    r = se.bendingStress({"sec": sec, "N": N, "Mfz": Mfz, "Mfy": Mfy, "Re": 235e6, "Kt": 1.2})
    S, Wz, Wy = b * h, b * h**2 / 6, h * b**2 / 6
    assert not r["usedGeneralFormula"]
    assert r["sigmaMaxTraction"] == pytest.approx(N / S + Mfz / Wz + Mfy / Wy, rel=1e-12)
    assert r["sigmaMaxCompression"] == pytest.approx(N / S - Mfz / Wz - Mfy / Wy, rel=1e-12)
    np.testing.assert_allclose(r["locMaxTraction"], [-h / 2, b / 2], atol=1e-12)  # σ = −Mfz y/Iz + Mfy z/Iy
    assert r["sigmaMaxKt"] == pytest.approx(1.2 * r["sigmaMaxAbs"], rel=1e-12)
    assert r["sigmaFun"](0, 0) == pytest.approx(N / S, rel=1e-12)
    na = r["neutralAxis"]
    np.testing.assert_allclose(na["a"] + na["b"] * na["points"][:, 0] + na["c"] * na["points"][:, 1], [0, 0], atol=1e-6)
    np.testing.assert_allclose(r["sigmaProfile"], N / S - Mfz * r["yProfile"] / (b * h**3 / 12), rtol=1e-12)
    verifier_latex(r["latex"])


def test_flexion_proprietes_seules():
    P = {
        "S": 0.02,
        "Iz": 0.1 * 0.2**3 / 12,
        "Iy": 0.2 * 0.1**3 / 12,
        "vyTop": 0.1,
        "vyBot": 0.1,
        "vzRight": 0.05,
        "vzLeft": 0.05,
    }
    r = se.bendingStress({"P": P, "N": -2e5, "Mfz": -1e4, "Re": 235e6, "s": 1.5})
    assert r["sigmaMaxCompression"] == pytest.approx(-2e5 / 0.02 - 1e4 / (0.1 * 0.2**2 / 6), rel=1e-12)
    assert r["sigmaAdm"] == pytest.approx(235e6 / 1.5, rel=1e-12)
    assert r["locMaxCompression"][0] == pytest.approx(-0.1, abs=1e-12)
    verifier_erreur(MANQUANT, se.bendingStress, {"Re": 1e8})


def test_flexion_formule_generale_en_L():
    sec = {"type": "L", "h": 0.1, "b": 0.06, "t": 0.008}
    P = geometry.analytical(sec)
    Mfz, Mfy = 3e3, -1e3
    r = se.bendingStress({"sec": sec, "Mfz": Mfz, "Mfy": Mfy, "Re": 235e6})
    assert r["usedGeneralFormula"]
    b, c = r["coefs"][1], r["coefs"][2]
    assert b * P["Iz"] + c * P["Iyz"] == pytest.approx(-Mfz, rel=1e-10)
    assert b * P["Iyz"] + c * P["Iy"] == pytest.approx(Mfy, rel=1e-10)
    # extrema = sommets du contour
    V = geometry.outline(sec)["outer"][0]
    s = r["sigmaFun"](V[:, 1] - P["yG"], V[:, 0] - P["zG"])
    assert r["sigmaMaxTraction"] == pytest.approx(max(s), rel=1e-12)
    assert r["sigmaMaxCompression"] == pytest.approx(min(s), rel=1e-12)
    verifier_latex(r["latex"])


def test_flexion_disque():
    D = 0.05
    r = se.bendingStress({"sec": {"type": "disque", "D": D}, "Mfz": 300, "Mfy": 400, "Re": 235e6})
    assert r["sigmaMaxAbs"] == pytest.approx(32 * 500 / (math.pi * D**3), rel=1e-9)


# ------------------------------------------------------------------ golden files


@pytest.mark.parametrize("cas", case_ids(GOLDEN, prefix="traction"))
def test_golden_traction(cas):
    c = get_case(GOLDEN, cas)
    assert_matches(se.traction(c["entrees"]), c["sortie"], rel=1e-9)


@pytest.mark.parametrize("cas", case_ids(GOLDEN, prefix="shear"))
def test_golden_shear(cas):
    c = get_case(GOLDEN, cas)
    assert_matches(se.shear(c["entrees"]), c["sortie"], rel=1e-12)


@pytest.mark.parametrize("cas", case_ids(GOLDEN, prefix="jourawski_"))
def test_golden_jourawski(cas):
    c = get_case(GOLDEN, cas)
    e = c["entrees"]
    assert_matches(se.jourawski(e["sec"], e["T"], e["n"]), c["sortie"], rel=1e-9, abs_=1e-6)


@pytest.mark.parametrize("cas", ["bearing", "keyDesign", "pinDesign"])
def test_golden_matage_clavette_goupille(cas):
    c = get_case(GOLDEN, cas)
    appel = {"bearing": se.bearing, "keyDesign": se.keyDesign, "pinDesign": se.pinDesign}[cas]
    assert_matches(appel(c["entrees"]), c["sortie"], rel=1e-12)


@pytest.mark.parametrize("cas", case_ids(GOLDEN, prefix="torsion_"))
def test_golden_torsion(cas):
    c = get_case(GOLDEN, cas)
    assert_matches(se.torsion(c["entrees"]), c["sortie"], rel=1e-9)


@pytest.mark.parametrize("cas", case_ids(GOLDEN, prefix="bending_"))
def test_golden_flexion(cas):
    c = get_case(GOLDEN, cas)
    assert_matches(se.bendingStress(c["entrees"]), c["sortie"], rel=1e-9, abs_=1e-6)
