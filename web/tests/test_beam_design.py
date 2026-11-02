"""Tests des services Poutres 2/2 : Eurocode 3, fatigue, profilé le plus léger, charge mobile (E19).

Tests portés de tests/test_MecaStruct_App.m (testProfileLePlusLeger, testChargeMobile, testEurocodeEtFatigue).
"""

import copy

import numpy as np
import pytest

from mecastruct.core import design_checks, geometry
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import ppEval
from mecastruct.services.beam_design import (
    _parseNumbers,
    checkEurocode,
    checkFatigue,
    computeMovingLoad,
    findLightestProfile,
    loadFromBeam,
    sectionToBeamInput,
    sendToTensor,
)
from mecastruct.services.beam_services import computeBeam, defaultBeamInput

_ID = "MecaStruct:App:invalidInput"


@pytest.fixture(scope="module")
def dm():
    return DataManager()


def _beam(dm, profile="IPE 300", L=6.0):
    """Saisie par défaut de l'onglet Poutres, section importée du catalogue (profilé tabulé), longueur L."""
    sec = geometry.fromProfile(dm.getProfile("IPE", profile))
    s = sectionToBeamInput(defaultBeamInput(), sec, geometry.analytical(sec), dm.getMaterial("S235"))
    s["L"] = L
    s["sup"][1]["pos"] = L
    return s


def _readme(dm):
    """Cas de référence du README : IPE 200, S235, L = 4 m, q = −10 kN/m (uniforme), sans force ponctuelle."""
    s = _beam(dm, "IPE 200", 4.0)
    s["pl"] = []
    s["dl"] = [{"a": 0.0, "b": 4.0, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}]
    return s


def test_ec3_coherent_avec_les_appels_directs(dm):
    s = _beam(dm)
    s["pl"] = []
    s["dl"] = [{"a": 0.0, "b": 6.0, "dir": "y", "type": "uniforme", "vals": "-20", "name": "q", "case": "G"}]
    r, _ = checkEurocode(s, dm, "poutre")
    mat = dm.getMaterial("S235")
    Pt = geometry.tabulated(s["section"])  # valeurs du catalogue, comme celles que lit checkEurocode
    d = design_checks.ibeamDims(s["section"])
    assert r["MEd"] == pytest.approx(20e3 * 6.0**2 / 8, rel=1e-6)  # qL²/8, les efforts sortent du solveur
    ref = design_checks.ec3Bending(d, Pt["S"], Pt["Iz"], mat["Re"], 1.0, r["MEd"], r["VEd"], 0.0)
    assert r["class"]["class"] == ref["class"]["class"]
    assert r["MRd"] == pytest.approx(ref["MRd"], rel=1e-9)
    assert r["ratioV"] == pytest.approx(ref["ratioV"], rel=1e-9)
    ltb = design_checks.ec3LateralTorsional(
        d, True, ref["W"], mat["Re"], 1.0, mat["E"], mat["G"], Pt["Iy"], s["Ix"] * 1e-12, 6.0, 1.0, r["MEd"]
    )
    assert r["ltb"]["Mcr"] == pytest.approx(ltb["Mcr"], rel=1e-9)
    assert r["ltb"]["chi"] == pytest.approx(ltb["chi"], rel=1e-9)


def test_fatigue_egale_goodman(dm):
    s = _beam(dm)
    s.update({"Kt": 1.5, "fR": 0.0, "fka": 0.8, "fkb": 0.9})
    r, T = checkFatigue(s, dm)
    sigMax = computeBeam(s, dm)["check"]["bend"]["sigmaMaxKt"] / 1.5
    ref = design_checks.goodman(sigMax, 0.0, 1.5, dm.getMaterial("S235")["Rm"], 0.8, 0.9)
    assert r["n"] == pytest.approx(ref["n"], rel=1e-12)
    assert r["Se"] == pytest.approx(ref["Se"], rel=1e-12)
    assert list(T.columns) == ["Grandeur", "Valeur", "Unité"]


def test_profile_le_plus_leger_readme(dm):
    s = _readme(dm)
    T, best = findLightestProfile(s, dm, "IPE", None)
    assert best is not None
    assert T["S (mm²)"].is_monotonic_increasing
    i = int(np.flatnonzero(T["Profilé"].to_numpy() == best["Name"])[0])
    assert T.iloc[i]["Kt·σ max (MPa)"] <= T.iloc[i]["σadm (MPa)"]
    assert T.iloc[i]["σadm (MPa)"] == pytest.approx(dm.getMaterial("S235")["Re"] / 1e6 / s["s"], rel=1e-9)
    assert i > 0
    assert T.iloc[i - 1]["Kt·σ max (MPa)"] > T.iloc[i - 1]["σadm (MPa)"], "Le profilé précédent ne vérifie pas."


def test_profile_le_plus_leger_verifie_le_tranchant(dm):
    """F = 400 kN près d'un appui sur 1 m : la flexion seule retiendrait l'IPE 220, le tranchant l'écarte."""
    s = _beam(dm, "IPE 220", 1.0)
    s.update(dl=[], pl=[{"pos": 0.1, "Fx": 0.0, "Fy": -400.0, "Fz": 0.0, "name": "F", "case": "Q"}])
    T, best = findLightestProfile(s, dm, "IPE", None)
    ligne = T[T["Profilé"] == "IPE 220"].iloc[0]
    assert ligne["Kt·σ max (MPa)"] <= ligne["σadm (MPa)"]
    assert ligne["Résistance"] == "NON vérifié (tranchant : VEd/Vpl,Rd = 1.67)"
    assert best["S"] > dm.getProfile("IPE", "IPE 220")["S"]
    T, _ = findLightestProfile(_readme(dm), dm, "UPN", None)
    assert T["Résistance"].str.contains("flexion seule, tranchant non vérifié").all()


def test_eurocode_par_defaut_enveloppe_et_non_pondere_indicatif(dm):
    s = _beam(dm)
    _, T = checkEurocode(s, dm)
    assert T.set_index("Grandeur").loc["Efforts utilisés", "Valeur"] == "enveloppe des combinaisons"
    s["Lcr"] = 1.0  # tout passe avec les efforts non pondérés
    r, T = checkEurocode(s, dm, "poutre")
    assert r["okAll"] and not r["pondere"]
    final = T.set_index("Grandeur").loc["Eurocode 3 (sections, voilement, déversement, N + M, flambement)", "Valeur"]
    assert final.startswith("indicatif")
    s["combo"] = []
    r, _ = checkEurocode(s, dm)
    assert not r["pondere"], "Sans combinaison : efforts de la poutre."


def test_fleche_limitee_impose_un_profil_plus_gros(dm):
    s = _readme(dm)
    before = copy.deepcopy(s)
    _, best = findLightestProfile(s, dm, "IPE", None)
    _, bestF = findLightestProfile(s, dm, "IPE", 1000)
    assert bestF is not None
    assert bestF["Name"] != best["Name"], "Une flèche L/1000 impose un profilé plus gros."
    assert s == before, "La saisie ne doit pas être modifiée."


def test_charge_mobile_essieu_unique_pl_sur_4(dm):
    s = _beam(dm)
    s["pl"] = []
    s["dl"] = []
    s.update({"mvP": "-100", "mvE": "1.5", "mvN": 61})
    T, env = computeMovingLoad(s, dm)
    assert env["extrema"]["Mmax"] == pytest.approx(100e3 * 6.0 / 4, rel=1e-6)
    assert len(T) == 101


def test_charge_mobile_deux_essieux(dm):
    s = _beam(dm)
    s["pl"] = []
    s["dl"] = []
    s.update({"mvP": "-100 -100", "mvE": "1.5", "mvN": 241})
    T, env = computeMovingLoad(s, dm)
    # référence statique : moment maximal sous un essieu
    P, e, L = 100e3, 1.5, 6.0
    x = np.linspace(0, L - e, 20001)
    RB = P * (2 * x + e) / L
    RA = 2 * P - RB
    best = max(0.0, float(np.max(RA * x)), float(np.max(RA * (x + e) - P * e)))
    assert env["extrema"]["Mmax"] == pytest.approx(best, rel=1e-6)
    assert env["Rmax"] == pytest.approx([175e3, 175e3], rel=1e-9)
    assert max(T["Mfz max (kN·m)"]) == pytest.approx(best / 1e3, rel=5e-3)
    s["mvN"] = 2  # grille grossière : les positions critiques donnent le même maximum
    _, env2 = computeMovingLoad(s, dm)
    assert env2["extrema"]["Mmax"] == pytest.approx(best, rel=1e-6)
    s.update({"mvN": 241, "mvE": "1 2"})
    with pytest.raises(MecaStructError) as err:
        computeMovingLoad(s, dm)
    assert err.value.identifier == _ID


def test_charge_mobile_virgule_decimale_comme_un_point(dm):
    """« -10,5 » est une charge de 10,5 kN, pas deux essieux : même convoi qu'avec un point."""
    resultats = []
    for charges, ecart in (("-10,5 -10", "4,5"), ("-10.5 -10", "4.5")):
        s = _beam(dm)
        s["pl"] = []
        s["dl"] = []
        s.update({"mvP": charges, "mvE": ecart, "mvN": 61})
        _, env = computeMovingLoad(s, dm)
        resultats.append(env)
    virgule, point = resultats
    assert virgule["extrema"]["Mmax"] == pytest.approx(point["extrema"]["Mmax"], rel=1e-12)
    assert virgule["extrema"]["Mmin"] == pytest.approx(point["extrema"]["Mmin"], rel=1e-12)
    assert virgule["Rmax"] == pytest.approx(point["Rmax"], rel=1e-12)


def test_parse_nombres_virgule_decimale():
    assert _parseNumbers("10,5", "x").tolist() == [10.5]
    assert _parseNumbers("10,5 10; 4.5", "x").tolist() == [10.5, 10.0, 4.5]
    assert _parseNumbers("", "x").size == 0
    with pytest.raises(MecaStructError) as err:
        _parseNumbers("10,5,3", "x")
    assert err.value.identifier == _ID


def test_eurocode_et_fatigue(dm):
    s = _beam(dm)
    r, _ = checkEurocode(s, dm, "poutre")
    e = computeBeam(s, dm)["sol"]["extrema"]
    assert r["MEd"] == pytest.approx(max(abs(e["Mfz"]["max"]), abs(e["Mfz"]["min"])), rel=1e-12)
    assert r["class"]["class"] == 1
    assert 0.3 < r["ratioM"] < 0.7
    assert r["ok"]
    assert r["ltb"]["Mcr"] > 0
    assert r["okAll"] == (r["ok"] and r["ltb"]["ok"])
    s["Lcr"] = 1.0
    rShort, _ = checkEurocode(s, dm, "poutre")
    assert rShort["ltb"]["ratio"] < r["ltb"]["ratio"], "Un maintien latéral rapproché réduit le déversement."
    s["Lcr"] = 0.0
    assert r["buck"] is None and not r["partial"], "Sans effort normal : pas de flambement."
    s["pl"] = [
        {"pos": 2.0, "Fx": 0.0, "Fy": -20.0, "Fz": 0.0, "name": "F", "case": "Q"},
        {"pos": 6.0, "Fx": -100.0, "Fy": 0.0, "Fz": 0.0, "name": "N", "case": "Q"},
    ]
    rN, _ = checkEurocode(s, dm, "poutre")
    assert rN["buck"] is not None
    assert rN["inter"] is not None, "Compression + moment : l'interaction 6.3.3 est vérifiée."
    assert rN["inter"]["ratio"] == pytest.approx(max(rN["inter"]["ratio61"], rN["inter"]["ratio62"]), rel=1e-12)
    assert rN["inter"]["ratio"] > rN["buck"]["ratio"], "Le moment s'ajoute à la compression."
    assert rN["buck"]["NEd"] == pytest.approx(100e3, rel=1e-6)
    assert rN["axial"]["n"] == pytest.approx(100e3 / rN["axial"]["Npl"], rel=1e-12)

    rEnv, _ = checkEurocode(_beam(dm), dm, "enveloppe")
    assert rEnv["ratioM"] > r["ratioM"], "L'ELU est plus défavorable que le cas courant."

    s = _beam(dm)
    s["fR"] = -1.0
    f1, _ = checkFatigue(s, dm)
    s["fR"] = 0.0
    f0, _ = checkFatigue(s, dm)
    assert f0["n"] > f1["n"], "Un chargement répété (R = 0) est moins sévère que l'alterné."
    assert f1["n"] > 0

    s["section"] = None
    with pytest.raises(MecaStructError) as err:
        checkEurocode(s, dm)
    assert err.value.identifier == _ID


def test_loadFromBeam_et_sendToTensor(dm):
    s = _beam(dm)
    res = computeBeam(s, dm)
    cible = {"N": 0.0, "Mfz": 0.0, "Mfy": 0.0, "Ty": 0.0, "s0": 3.0}
    out = loadFromBeam(cible, res, "Fle", "abscisse")
    assert out["Mfz"] == pytest.approx(ppEval(res["sol"]["Mfz"], 3.0) / 1e3)
    assert cible["Mfz"] == 0.0, "La saisie cible d'origine ne doit pas être modifiée."
    assert loadFromBeam(cible, res, "Sec", "max")["s0"] == res["check"]["s"]
    with pytest.raises(MecaStructError) as err:
        loadFromBeam({**cible, "s0": 7.0}, res, "Fle", "abscisse")
    assert err.value.identifier == _ID
    tens = sendToTensor(res)
    assert tens["sig"][0, 0] == pytest.approx(res["check"]["sigma"] / 1e6)
    assert np.count_nonzero(tens["sig"]) == 1
