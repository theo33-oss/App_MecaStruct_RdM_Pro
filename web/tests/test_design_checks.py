"""Tests de design_checks (étape E17) : portage de tests/test_DesignChecks.m (IPE 300 de référence, Eurocode 3
simplifié et fatigue de Goodman) et cas golden de golden_design.json.

Tolérance des cas golden (fiche E17) : rel = 1e-9 (assert_matches, abs_ par défaut de golden_tools).
"""

import math

import pytest

from mecastruct.core.data_manager import DataManager
from mecastruct.core.design_checks import (
    classify,
    ec3AxialBending,
    ec3Bending,
    ec3FlexuralBuckling,
    ec3Interaction,
    ec3LateralTorsional,
    ec3WebShear,
    goodman,
    ibeamDims,
)
from mecastruct.core.errors import MecaStructError
from mecastruct.core.geometry import fromProfile
from tests.golden_tools import assert_matches, get_case

GOLDEN = "golden_design.json"
PREFIXE = "MecaStruct:Design:"


def ipe300():
    """Dimensions de l'IPE 300 du catalogue (DataManager → GeometryEngine.fromProfile → ibeamDims)."""
    return ibeamDims(fromProfile(DataManager().getProfile("IPE", "IPE 300")))


def verifier_erreur(identifiant, appel):
    """Vérifie que l'appel lève une MecaStructError d'identifiant 'MecaStruct:Design:<identifiant>'."""
    with pytest.raises(MecaStructError) as info:
        appel()
    assert info.value.identifier == PREFIXE + identifiant


# -------------------------------------------------------------------------------------------------
# Tests portés de tests/test_DesignChecks.m
# -------------------------------------------------------------------------------------------------


def test_ipe300_catalogue():
    d = ipe300()
    assert d["h"] == pytest.approx(0.3, abs=1e-9)
    r = ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 50e3)
    assert r["class"]["class"] == 1
    assert r["Wpl"] == pytest.approx(628.4e-6, rel=5e-3)
    assert r["Av"] == pytest.approx(2568e-6, rel=1e-2)
    assert r["Mc"] == pytest.approx(147.7e3, rel=5e-3)
    assert r["reduced"] is False
    assert r["ok"] is True
    assert r["ratioM"] == pytest.approx(100e3 / r["Mc"], rel=1e-12)


def test_interaction_tranchant():
    d = ipe300()
    r0 = ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 0)
    r = ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 0.8 * r0["Vpl"])
    assert r["reduced"] is True
    assert r["rho"] == pytest.approx((2 * 0.8 - 1) ** 2, abs=1e-12)
    assert r["MRd"] < r0["Mc"]
    r2 = ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.1, 100e3, 0)
    assert r2["Mc"] == pytest.approx(r0["Mc"] / 1.1, rel=1e-12)


def test_classes():
    # classe 3 : aile c/tf = 12 (entre 10ε et 14ε) → module élastique
    d3 = {"h": 0.4, "b": 0.25, "tw": 0.01, "tf": 0.01, "r": 0}
    r = ec3Bending(d3, 2 * 0.25 * 0.01 + 0.38 * 0.01, 1e-4, 235e6, 1.0, 50e3, 10e3)
    assert r["class"]["class"] == 3
    assert r["W"] == r["Wel"]
    # classe 4 refusée
    d4 = {"h": 0.5, "b": 0.3, "tw": 0.01, "tf": 0.01, "r": 0}
    verifier_erreur("class4", lambda: ec3Bending(d4, 0.01, 1e-4, 235e6, 1.0, 1e3, 1e3))
    # un acier plus résistant durcit les limites (ε plus petit)
    c = classify(ipe300(), 460e6, 0, 0, 5381e-6, 8356e-8)
    assert c["eps"] < 1


def test_section_non_supportee():
    verifier_erreur("unsupportedSection", lambda: ibeamDims({"type": "rectangle"}))
    dm = DataManager()
    upn = dm.listProfiles("UPN")[0]
    verifier_erreur("unsupportedSection", lambda: ibeamDims(fromProfile(dm.getProfile("UPN", upn))))


def test_deversement_ipe300():
    # Calcul à la main (IPE 300, S235, E = 210 GPa, G = 81 GPa, Iz = 603,8 cm⁴, It = 20,1 cm⁴, Lcr = 4 m, C1 = 1) :
    # Iw ≈ 126·10³ cm⁶, Mcr ≈ 159,8 kN·m, λ̄LT ≈ 0,96, courbe b (h/b = 2), χLT ≈ 0,72, Mb,Rd ≈ 107 kN·m.
    d = ipe300()
    b = ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 50e3, 10e3)
    r = ec3LateralTorsional(d, True, b["W"], 235e6, 1.0, 210e9, 81e9, 603.8e-8, 20.1e-8, 4, 1, 50e3)
    assert r["Mcr"] == pytest.approx(159.8e3, rel=3e-2)
    assert r["lambda"] == pytest.approx(0.96, rel=3e-2)
    assert r["curve"] == "b"
    assert r["chi"] == pytest.approx(0.72, rel=3e-2)
    assert r["MbRd"] == pytest.approx(107e3, rel=3e-2)
    assert r["MbRd"] < b["Mc"]
    # maintien latéral serré : plus de réduction
    r2 = ec3LateralTorsional(d, True, b["W"], 235e6, 1.0, 210e9, 81e9, 603.8e-8, 20.1e-8, 1, 1, 50e3)
    assert r2["chi"] == pytest.approx(1, abs=0.1)
    assert r2["MbRd"] > r["MbRd"]
    # un moment non uniforme (C1 > 1) augmente Mcr
    r3 = ec3LateralTorsional(d, True, b["W"], 235e6, 1.0, 210e9, 81e9, 603.8e-8, 20.1e-8, 4, 1.77, 50e3)
    assert r3["Mcr"] == pytest.approx(1.77 * r["Mcr"], rel=1e-12)
    # choix de courbe : laminé élancé → c ; soudé → c / d
    dt = {"h": 0.6, "b": 0.2, "tw": 0.01, "tf": 0.015, "r": 0}
    assert ec3LateralTorsional(dt, True, 2e-3, 235e6, 1, 210e9, 81e9, 1e-5, 1e-7, 3, 1, 1e3)["curve"] == "c"
    assert ec3LateralTorsional(dt, False, 2e-3, 235e6, 1, 210e9, 81e9, 1e-5, 1e-7, 3, 1, 1e3)["curve"] == "d"
    assert ec3LateralTorsional(d, False, b["W"], 235e6, 1, 210e9, 81e9, 603.8e-8, 20.1e-8, 4, 1, 1e3)["curve"] == "c"
    verifier_erreur(
        "invalidInput",
        lambda: ec3LateralTorsional(d, True, b["W"], 235e6, 1, 210e9, 81e9, 603.8e-8, 20.1e-8, 0, 1, 1e3),
    )


def test_flambement_ipe300():
    # À la main (IPE 300, S235, Lcr = 3 m, E = 210 GPa) : axe faible Ncr = 1390 kN, λ̄ = 0,954, courbe b (h/b = 2,
    # tf ≤ 40 mm), Φ = 1,083, χ = 0,627, Nb,Rd = 792 kN ; axe fort λ̄ = 0,256, courbe a, χ = 0,988.
    d = ipe300()
    r = ec3FlexuralBuckling(d, True, 5381e-6, 8356e-8, 603.8e-8, 3, 235e6, 210e9, 1.0, 500e3)
    assert r["governing"] == 2, "L'axe faible gouverne."
    z = r["axes"][1]
    assert z["Ncr"] == pytest.approx(1390e3, rel=1e-2)
    assert z["lambda"] == pytest.approx(0.954, rel=1e-2)
    assert z["curve"] == "b"
    assert z["chi"] == pytest.approx(0.627, rel=1e-2)
    assert r["NbRd"] == pytest.approx(792e3, rel=1e-2)
    assert r["axes"][0]["curve"] == "a"
    assert r["axes"][0]["needed"] is False, "NEd/Ncr = 0,026 ≤ 0,04 : pas de vérification sur l'axe fort (6.3.1.2(4))."
    r1000 = ec3FlexuralBuckling(d, True, 5381e-6, 8356e-8, 603.8e-8, 3, 235e6, 210e9, 1.0, 1000e3)
    assert r1000["axes"][0]["needed"] is True
    assert r1000["axes"][0]["chi"] == pytest.approx(0.988, rel=1e-2)
    assert r["ratio"] == pytest.approx(500e3 / r["NbRd"], rel=1e-12)
    # barre trapue : pas de vérification (λ̄ ≤ 0,2)
    rs = ec3FlexuralBuckling(d, True, 5381e-6, 8356e-8, 603.8e-8, 0.3, 235e6, 210e9, 1.0, 500e3)
    assert rs["axes"][1]["chi"] == 1
    assert rs["axes"][1]["needed"] is False
    verifier_erreur(
        "unsupportedSteel",
        lambda: ec3FlexuralBuckling(d, True, 5381e-6, 8356e-8, 603.8e-8, 3, 460e6, 210e9, 1.0, 1e3),
    )
    # soudé : une courbe plus défavorable
    rw = ec3FlexuralBuckling(d, False, 5381e-6, 8356e-8, 603.8e-8, 3, 235e6, 210e9, 1.0, 500e3)
    assert rw["axes"][1]["curve"] == "c"
    assert rw["NbRd"] < r["NbRd"]


def test_flexion_effort_normal():
    d = ipe300()
    b = ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 0)
    # N faible : aucune réduction (6.33 et 6.34 vérifiées)
    r1 = ec3AxialBending(d, b, 5381e-6, 235e6, 1.0, 200e3, 100e3)
    assert r1["free"] is True
    assert r1["MNRd"] == pytest.approx(b["Mc"], rel=1e-12)
    # N = 400 kN : n = 0,316 ; a = 0,4035 ; MN = Mpl·(1 − n)/(1 − 0,5·a) = 0,857·Mpl
    r2 = ec3AxialBending(d, b, 5381e-6, 235e6, 1.0, 400e3, 100e3)
    assert r2["free"] is False
    assert r2["n"] == pytest.approx(0.3163, rel=1e-3)
    assert r2["a"] == pytest.approx(0.4035, rel=1e-3)
    assert r2["MNRd"] / b["Mc"] == pytest.approx(0.8565, rel=2e-3)
    # N = Npl : plus de capacité en flexion
    r3 = ec3AxialBending(d, b, 5381e-6, 235e6, 1.0, 5381e-6 * 235e6, 1e3)
    assert r3["ok"] is False
    # classe 3 : contrainte élastique N/A + M/Wel
    d3 = {"h": 0.4, "b": 0.25, "tw": 0.01, "tf": 0.01, "r": 0}
    A3 = 2 * 0.25 * 0.01 + 0.38 * 0.01
    b3 = ec3Bending(d3, A3, 1e-4, 235e6, 1.0, 50e3, 10e3)
    r4 = ec3AxialBending(d3, b3, A3, 235e6, 1.0, 100e3, 50e3)
    assert r4["class12"] is False
    assert r4["sigma"] == pytest.approx(100e3 / A3 + 50e3 / b3["Wel"], rel=1e-12)


def test_goodman():
    r = goodman(100e6, -1, 1, 400e6, 1, 1)
    assert r["Se"] == pytest.approx(200e6, rel=1e-12)
    assert r["n"] == pytest.approx(2, rel=1e-12), "Alterné : n = Se / σa."
    r = goodman(100e6, 0, 1, 400e6, 1, 1)
    assert r["n"] == pytest.approx(1 / (50 / 200 + 50 / 400), rel=1e-12)
    r = goodman(100e6, -1, 2, 400e6, 0.8, 1)
    assert r["n"] == pytest.approx(0.8 * 200e6 / (2 * 100e6), rel=1e-12), "Kf et ka agissent comme attendu."
    verifier_erreur("invalidInput", lambda: goodman(100e6, 1, 1, 400e6, 1, 1))
    assert goodman(0, 0, 1, 400e6, 1, 1)["n"] == math.inf


def test_interaction_annexe_b():
    # Valeurs recalculées à la main : A = 1e-2 m², W = 1e-3 m³, fy = 235 MPa, N = 500 kN, M = 100 kN·m, Cmy = CmLT = 0,9
    buck = {"axes": [{"chi": 0.8, "lambda": 0.8}, {"chi": 0.5, "lambda": 1.2}]}
    ltb = {"chi": 0.7}
    r = ec3Interaction(1, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 500e3, 100e3, 0.9, 0.9)
    assert r["nY"] == pytest.approx(0.265957, rel=1e-5)
    assert r["nZ"] == pytest.approx(0.425532, rel=1e-5)
    assert r["kyy"] == pytest.approx(1.043617, rel=1e-5), (
        "kyy = min(0,9(1+0,6·nY) ; 0,9(1+0,8·nY)) en classe 1 avec λ̄y = 0,8."
    )
    assert r["kzy"] == pytest.approx(0.934534, rel=1e-5)
    assert r["ratio61"] == pytest.approx(0.9004, rel=1e-3)
    assert r["ratio62"] == pytest.approx(0.9936, rel=1e-3)
    assert r["ok"] is True
    r2 = ec3Interaction(1, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 600e3, 100e3, 0.9, 0.9)
    assert r2["ok"] is False, "Plus de compression : l'interaction dépasse 1."
    verifier_erreur("invalidInput", lambda: ec3Interaction(1, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 5e5, 1e5, 1.2, 0.9))
    verifier_erreur("class4", lambda: ec3Interaction(4, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 5e5, 1e5, 0.9, 0.9))


def test_voilement_ame():
    # Âme élancée soudée : hw = 0,96 m, tw = 6 mm (hw/tw = 160 > 72ε/η = 60) ; λ̄w = 1,852 ; χw = 1,37/(0,7 + λ̄w)
    d = {"h": 1.0, "b": 0.3, "tw": 0.006, "tf": 0.02, "r": 0}
    w = ec3WebShear(d, 235e6, 1.0, 300e3)
    assert w["needed"] is True
    assert w["lambda"] == pytest.approx(0.96 / (86.4 * 0.006), rel=1e-12)
    assert w["chi"] == pytest.approx(1.37 / (0.7 + w["lambda"]), rel=1e-12)
    assert w["VbRd"] == pytest.approx(419.5e3, rel=1e-3)
    assert w["ratio"] == pytest.approx(300e3 / w["VbRd"], rel=1e-12)
    # profilé laminé : sans objet (IPE 300 : hw/tw = 35)
    w2 = ec3WebShear({"h": 0.3, "b": 0.15, "tw": 0.0071, "tf": 0.0107, "r": 0.015}, 235e6, 1.0, 100e3)
    assert w2["needed"] is False
    assert w2["ok"] is True


def test_classe_sous_compression():
    # IPE 300 : âme c/tw = 248,6 / 7,1 = 35,0. Flexion seule : classe 1 (72ε).
    # Compression pure (ψ = 1, α = 1) : classe 2.
    d = ipe300()
    A = 5381e-6
    Iz = 8356e-8
    c0 = classify(d, 235e6, 0, 1e3, A, Iz)
    assert c0["psi"] == pytest.approx(-1, abs=1e-12)
    assert c0["classWeb"] == 1
    c1 = classify(d, 235e6, 0.5 * A * 235e6, 0, A, Iz)
    assert c1["alpha"] == pytest.approx(1, abs=1e-12)
    assert c1["classWeb"] == 2
    # compression et flexion avec ψ = −0,2 (α = 0,833) : limite 396ε/(13α − 1) ≈ 40,3ε, donc encore classe 1
    sC = 1e6 / A
    sM = 1.5 * sC
    c2 = classify(d, 235e6, 1e6, sM * Iz / ((d["h"] - 2 * d["tf"]) / 2), A, Iz)
    assert c2["psi"] == pytest.approx(-0.2, rel=1e-9)
    assert c2["alpha"] == pytest.approx(1 / 1.2, rel=1e-9)
    assert c2["classWeb"] == 1


def test_longueur_fort_separee():
    # Lcr,y (axe fort) et Lcr,z (axe faible) distincts : Ncr = π²·E·I/L² pour chaque axe.
    d = ipe300()
    r = ec3FlexuralBuckling(d, True, 5381e-6, 8356e-8, 603.8e-8, [6, 3], 235e6, 210e9, 1.0, 100e3)
    assert r["axes"][0]["Ncr"] == pytest.approx(math.pi**2 * 210e9 * 8356e-8 / 6**2, rel=1e-12)
    assert r["axes"][1]["Ncr"] == pytest.approx(math.pi**2 * 210e9 * 603.8e-8 / 3**2, rel=1e-12)


def test_courbe_tres_epaisse():
    # Laminé, h/b = 2,4 et tf = 120 mm : non tabulé, courbe d sur les deux axes (α = 0,76).
    d = {"h": 0.6, "b": 0.25, "tw": 0.02, "tf": 0.12, "r": 0}
    r = ec3FlexuralBuckling(d, True, 0.05, 1e-3, 1e-2, 3, 235e6, 210e9, 1.0, 0)
    assert r["axes"][0]["curve"] == "d"
    assert r["axes"][1]["curve"] == "d"
    assert r["axes"][1]["alpha"] == pytest.approx(0.76, abs=1e-12)


# -------------------------------------------------------------------------------------------------
# Cas golden (golden_design.json)
# -------------------------------------------------------------------------------------------------


def _entrees(identifiant):
    return get_case(GOLDEN, identifiant)["entrees"]


def _d_golden():
    return ibeamDims(_entrees("ibeamDims_IPE300"))


def test_golden_ibeamDims_IPE300():
    assert_matches(ibeamDims(_entrees("ibeamDims_IPE300")), get_case(GOLDEN, "ibeamDims_IPE300")["sortie"], rel=1e-9)


@pytest.mark.parametrize("identifiant", ["classify_flexion", "classify_compression"])
def test_golden_classify(identifiant):
    e = _entrees(identifiant)
    obtenu = classify(e["d"], e["fy"], e["Nc"], e["Mz"], e["A"], e["Iz"])
    assert_matches(obtenu, get_case(GOLDEN, identifiant)["sortie"], rel=1e-9)


@pytest.mark.parametrize("identifiant", ["ec3Bending", "ec3Bending_VEd_fort"])
def test_golden_ec3Bending(identifiant):
    e = _entrees(identifiant)
    obtenu = ec3Bending(e["d"], e["S"], e["Iz"], e["fy"], e["gM0"], e["MEd"], e["VEd"], e["Nc"])
    assert_matches(obtenu, get_case(GOLDEN, identifiant)["sortie"], rel=1e-9)


def test_golden_ec3LateralTorsional():
    e = _entrees("ec3LateralTorsional")
    obtenu = ec3LateralTorsional(
        e["d"],
        e["rolled"],
        e["W"],
        e["fy"],
        e["gM1"],
        e["E"],
        e["G"],
        e["Iweak"],
        e["It"],
        e["Lcr"],
        e["C1"],
        e["MEd"],
    )
    assert_matches(obtenu, get_case(GOLDEN, "ec3LateralTorsional")["sortie"], rel=1e-9)


def test_golden_ec3FlexuralBuckling():
    e = _entrees("ec3FlexuralBuckling")
    obtenu = ec3FlexuralBuckling(
        e["d"], e["rolled"], e["A"], e["Iy"], e["Iz"], e["Lcr"], e["fy"], e["E"], e["gM1"], e["NEd"]
    )
    assert_matches(obtenu, get_case(GOLDEN, "ec3FlexuralBuckling")["sortie"], rel=1e-9)


def test_golden_ec3AxialBending():
    # d et b recalculés comme dans export_golden_json.m (section « Eurocode 3 et fatigue »)
    e = _entrees("ec3AxialBending")
    eb = _entrees("ec3Bending")
    b = ec3Bending(eb["d"], eb["S"], eb["Iz"], eb["fy"], eb["gM0"], eb["MEd"], eb["VEd"], eb["Nc"])
    obtenu = ec3AxialBending(_d_golden(), b, e["A"], e["fy"], e["gM0"], e["NEd"], e["MEd"])
    assert_matches(obtenu, get_case(GOLDEN, "ec3AxialBending")["sortie"], rel=1e-9)


def test_golden_ec3Interaction():
    # buck et ltb recalculés comme dans export_golden_json.m
    e = _entrees("ec3Interaction")
    ef = _entrees("ec3FlexuralBuckling")
    buck = ec3FlexuralBuckling(
        ef["d"], ef["rolled"], ef["A"], ef["Iy"], ef["Iz"], ef["Lcr"], ef["fy"], ef["E"], ef["gM1"], ef["NEd"]
    )
    el = _entrees("ec3LateralTorsional")
    ltb = ec3LateralTorsional(
        el["d"],
        el["rolled"],
        el["W"],
        el["fy"],
        el["gM1"],
        el["E"],
        el["G"],
        el["Iweak"],
        el["It"],
        el["Lcr"],
        el["C1"],
        el["MEd"],
    )
    obtenu = ec3Interaction(
        e["cls"], buck, ltb, e["A"], e["W"], e["fy"], e["gM1"], e["NEd"], e["MEd"], e["Cmy"], e["CmLT"]
    )
    assert_matches(obtenu, get_case(GOLDEN, "ec3Interaction")["sortie"], rel=1e-9)


def test_golden_ec3WebShear():
    e = _entrees("ec3WebShear")
    obtenu = ec3WebShear(e["d"], e["fy"], e["gM1"], e["VEd"])
    assert_matches(obtenu, get_case(GOLDEN, "ec3WebShear")["sortie"], rel=1e-9)


@pytest.mark.parametrize("identifiant", ["goodman_R0", "goodman_alterne"])
def test_golden_goodman(identifiant):
    sigMax, R, Kf, Rm, ka, kb = _entrees(identifiant)
    assert_matches(goodman(sigMax, R, Kf, Rm, ka, kb), get_case(GOLDEN, identifiant)["sortie"], rel=1e-9)
