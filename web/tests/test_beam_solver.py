"""Tests de beam_solver, sous-étapes E08a, E08b et E08c.

E08a : options, normalisation du modèle, Gauss, matrices de coefficients, coupures. Portage de testInvalidInputs et de
la partie normalisation de testNormalizationAndDefaults (tests/test_BeamAndTrussSolver.m) ; les erreurs passent ici par
_normalizeModel et _beamOpts.
E08b : sous-problèmes, Ménabréa, extrema, solveBeam (structure du résultat, mécanisme, E09).
E08c : cas d'école de MATLAB (isostatiques et hyperstatiques par Ménabréa) et golden_beam.json hors ressort, tassement,
rotule et thermique (E09). Non portés : methodCheck, hyperCheck, equations, reactionsIntegration (E09 et E10).
"""

import copy
import math
import time

import numpy as np
import pytest
from scipy.integrate import quad

from mecastruct.core.beam_solver import (
    _actions,
    _baseOrder,
    _beamOpts,
    _bendDisp,
    _buildSubs,
    _cleanMat,
    _condText,
    _cutBend,
    _extrema,
    _gauss,
    _gaussData,
    _gaussVals,
    _jumps,
    _matEval,
    _matIntegrate,
    _matMaxAbs,
    _matToPP,
    _normalizeModel,
    _normType,
    _prepDist,
    _provisoire_E10,
    _reactionDiff,
    solveBeam,
)
from mecastruct.core.data_manager import hasSymbolic
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import PP, ppDerivative, ppEval, ppIntegrate, ppScale
from tests.golden_tools import assert_matches, case_ids, get_case

COUPURES_MENABREA = {"hyperMethod": "menabrea", "internalMethod": "coupures"}
MECANISME = "MecaStruct:Beam:mechanism"

MODELE = "MecaStruct:Beam:invalidModel"
APPUI = "MecaStruct:Beam:invalidSupport"
OPTION = "MecaStruct:Beam:invalidOption"


def verifier_erreur(identifiant, appel, *args):
    """Vérifie que l'appel lève une MecaStructError portant l'identifiant MATLAB attendu."""
    with pytest.raises(MecaStructError) as info:
        appel(*args)
    assert info.value.identifier == identifiant


def baseModel(L):
    """Modèle de poutre sans appui ni charge (aide de tests/test_BeamAndTrussSolver.m)."""
    return {
        "L": L,
        "E": 210e9,
        "G": 80e9,
        "S": 2e-3,
        "Iz": 8e-6,
        "Iy": 3e-6,
        "Ix": 1e-6,
        "ky": 1,
        "kz": 1,
        "supports": [],
        "pointLoads": [],
        "pointMoments": [],
        "distLoads": [],
    }


def addSup(m, pos, typ, name):
    m["supports"].append({"pos": pos, "type": typ, "name": name})
    return m


def addQ(m, a, b, dir_, coeffs):
    m["distLoads"].append({"a": a, "b": b, "dir": dir_, "coeffs": coeffs, "name": f"q{len(m['distLoads']) + 1}"})
    return m


def test_invalid_inputs():
    verifier_erreur(MODELE, _normalizeModel, {"L": 0})
    verifier_erreur(MODELE, _normalizeModel, {"E": 1})
    verifier_erreur(MODELE, _normalizeModel, 42)
    verifier_erreur(APPUI, _normalizeModel, addSup(baseModel(4), 0, "glissiere_bizarre", "A"))
    verifier_erreur(MODELE, _normalizeModel, addSup(baseModel(4), 5, "pivot", "A"))
    m = addQ(addSup(baseModel(4), 0, "encastrement", "A"), 2, 2, "y", -1)
    verifier_erreur(MODELE, _normalizeModel, m)
    m = addQ(addSup(baseModel(4), 0, "encastrement", "A"), 0, 2, "w", -1)
    verifier_erreur(MODELE, _normalizeModel, m)
    verifier_erreur(OPTION, _beamOpts, {"internalMethod": "foo"})
    verifier_erreur(OPTION, _beamOpts, {"hyperMethod": "bar"})
    mE = baseModel(4)
    mE["E"] = -1
    verifier_erreur(MODELE, _normalizeModel, mE)


def test_normalization_and_defaults():
    m = {
        "L": 2,
        "supports": [{"pos": 0, "type": "Pivot"}, {"pos": 2, "type": "appui simple"}],
        "pointLoads": {"pos": 1, "Fy": -100},  # dict seul : JSON MATLAB d'une structure à un élément
        "pointMoments": None,
        "distLoads": [],
    }
    avant = copy.deepcopy(m)
    mdl, notes = _normalizeModel(m)
    assert m == avant  # le modèle d'entrée n'est pas modifié
    for f in ("E", "G", "S", "Iz", "Iy", "Ix", "ky", "kz"):
        assert isinstance(mdl[f], float) and mdl[f] > 0, f
    assert [s["name"] for s in mdl["supports"]] == ["A", "B"]
    assert [s["type"] for s in mdl["supports"]] == ["pivot", "appui_simple"]
    assert [mdl["pointLoads"][0][f] for f in ("Fx", "Fz")] == [0, 0]
    assert mdl["pointLoads"][0]["name"] == "F1"
    assert mdl["pointMoments"] == [] and mdl["distLoads"] == [] and mdl["hinges"] == []
    assert any("non fourni" in n for n in notes)
    assert mdl["G"] == pytest.approx(mdl["E"] / 2.6, rel=1e-15)
    assert mdl["Ix"] == mdl["Iz"] + mdl["Iy"]
    assert mdl["thermal"] == {"epsX": 0.0, "kv": 0.0, "kw": 0.0}
    assert {s["spring"] for s in mdl["supports"]} == {0.0}
    # modèle sans aucune liaison ni charge : accepté
    m0, _ = _normalizeModel({"L": 1})
    assert m0["supports"] == [] and m0["pointLoads"] == []


def test_normalization_json_forms_and_fields():
    m = baseModel(5)
    m["supports"] = {"pos": 0, "type": "encastré", "name": "  Enc  ", "spring": 1e6, "dz": -0.002}
    m["pointMoments"] = {"pos": 2, "Mz": 300}
    m["distLoads"] = {"a": 1, "b": 4, "dir": "Y", "coeffs": -1000}  # coeffs : nombre seul
    m["hinges"] = {"pos": 3}
    m["thermal"] = {"epsX": 1e-4, "kv": 2e-5}
    m["Iyz"] = 1e-7  # champ hors normalisation : conservé
    mdl, notes = _normalizeModel(m)
    assert notes == []
    s = mdl["supports"][0]
    assert (s["type"], s["name"], s["spring"], s["dz"], s["dx"]) == ("encastrement", "Enc", 1e6, -0.002, 0.0)
    assert mdl["pointMoments"][0] == {"pos": 2.0, "Mx": 0.0, "My": 0.0, "Mz": 300.0, "name": "C1"}
    q = mdl["distLoads"][0]
    assert q["dir"] == "y" and q["name"] == "q1" and np.array_equal(q["coeffs"], [-1000.0])
    assert mdl["hinges"] == [{"pos": 3.0, "name": "R1"}]
    assert mdl["thermal"] == {"epsX": 1e-4, "kv": 2e-5, "kw": 0.0}
    assert mdl["Iyz"] == 1e-7


def test_normalization_positions_and_names():
    m = baseModel(4)
    m["supports"] = [{"pos": 4 + 1e-13, "type": "pivot"}]
    assert _normalizeModel(m)[0]["supports"][0]["pos"] == 4.0  # ramenée sur la poutre à 1e-12·L près
    m["supports"] = [{"pos": i, "type": "pivot"} for i in range(0, 28)]
    m["L"] = 30
    noms = [s["name"] for s in _normalizeModel(m)[0]["supports"]]
    assert noms[0] == "A" and noms[25] == "Z" and noms[26] == "A27"


def test_normalization_errors_details():
    m = baseModel(4)
    m["supports"] = [{"pos": 0}]
    verifier_erreur(APPUI, _normalizeModel, m)
    m["supports"] = [{"pos": 0, "type": "pivot", "spring": -1}]
    verifier_erreur(APPUI, _normalizeModel, m)
    m["supports"] = [{"pos": 0, "type": 3}]
    verifier_erreur(APPUI, _normalizeModel, m)
    m["supports"] = [{"pos": 0, "type": "pivot", "dy": "x"}]
    verifier_erreur(MODELE, _normalizeModel, m)
    for champ in ("supports", "pointLoads"):
        mm = baseModel(4)
        mm[champ] = [1, 2]
        verifier_erreur(MODELE, _normalizeModel, mm)
    for coeffs in (None, [], "a", [1, float("nan")], [[1, 2]], [True]):
        mm = addQ(baseModel(4), 0, 2, "y", coeffs)
        verifier_erreur(MODELE, _normalizeModel, mm)
    for E in (0, "x", float("inf")):
        verifier_erreur(MODELE, _normalizeModel, {**baseModel(4), "E": E})
    verifier_erreur(MODELE, _normalizeModel, {**baseModel(4), "L": float("nan")})


def test_hinges():
    m = addSup(baseModel(6), 3, "appui_simple", "B")
    for pos in (0, 6):
        m["hinges"] = [{"pos": pos}]
        verifier_erreur(MODELE, _normalizeModel, m)  # pas aux extrémités
    m["hinges"] = [{"pos": 3}]
    verifier_erreur(MODELE, _normalizeModel, m)  # pas sur un appui
    m["hinges"] = [{"pos": 2}]
    m["pointMoments"] = [{"pos": 2, "Mz": 10}]
    verifier_erreur(MODELE, _normalizeModel, m)  # couple de flexion au même point
    m["pointMoments"] = [{"pos": 2, "Mx": 10}]
    assert _normalizeModel(m)[0]["hinges"][0]["name"] == "R1"  # un couple de torsion est permis


def test_options():
    o = _beamOpts(None)
    assert (o["internalMethod"], o["hyperMethod"], o["includeShearEnergy"]) == ("both", "both", False)
    assert o["useSymbolic"] is hasSymbolic()
    assert _beamOpts({}) == o
    o = _beamOpts({"internalMethod": "Intégrale", "hyperMethod": "MENABREA", "includeShearEnergy": 1})
    assert (o["internalMethod"], o["hyperMethod"], o["includeShearEnergy"]) == ("integrale", "menabrea", True)
    assert _beamOpts({"useSymbolic": False})["useSymbolic"] is False
    assert _beamOpts({"useSymbolic": True})["useSymbolic"] is hasSymbolic()
    assert _beamOpts({"internalMethod": None, "hyperMethod": ""})["hyperMethod"] == "both"
    verifier_erreur(OPTION, _beamOpts, [1])
    verifier_erreur(OPTION, _beamOpts, {"useSymbolic": "oui"})
    verifier_erreur(OPTION, _beamOpts, {"includeShearEnergy": [True, False]})
    verifier_erreur(OPTION, _beamOpts, {"internalMethod": 3})


def test_norm_type_aliases():
    attendu = {
        "appui_simple": ["Appui simple", "appui", "APPUI-PONCTUEL", " simple ", "appui_plan"],
        "rotule": ["rotule", "Articulation", "rotule sphérique"],
        "pivot": ["pivot", "Pivot"],
        "pivot_glissant": ["pivot-glissant", "glissière", "Glissiere"],
        "encastrement": ["encastrement", "encastré", "ENCASTRÉE"],
    }
    for canonique, noms in attendu.items():
        assert [_normType(t, 1) for t in noms] == [canonique] * len(noms)


def test_prepDist():
    m, _ = _normalizeModel(addQ(baseModel(6), 1, 4, "y", [-300.0, -600.0]))  # p(ξ) = −300 ξ − 600, ξ = s − 1
    d = _prepDist(m["distLoads"])[0]
    p = lambda s: -300.0 * (s - 1) - 600.0  # noqa: E731
    assert np.polyval(d["pg"], 2.5) == pytest.approx(p(2.5), rel=1e-12)
    assert d["I0"] == pytest.approx(-300 * 9 / 2 - 600 * 3, rel=1e-12)  # ∫ p ds
    # ∫ s·p ds sur [1, 4] avec p = −300 s − 300
    assert d["I1"] == pytest.approx(-300 * (64 - 1) / 3 - 300 * (16 - 1) / 2, rel=1e-12)
    assert d["deg"] == 1 and d["dir"] == "y" and d["name"] == "q1"
    assert d["absInt"] == pytest.approx(3 * 1500.0, rel=1e-12)
    zero, _ = _normalizeModel(addQ(baseModel(6), 1, 4, "x", 0.0))
    dz = _prepDist(zero["distLoads"])[0]
    assert np.array_equal(dz["pg"], [0.0]) and dz["I0"] == 0.0 and dz["deg"] == 0


def test_gauss():
    x, w = _gauss(3)
    assert x.shape == w.shape == (3,) and np.all(np.diff(x) > 0)
    # x⁵ sur [0, 1] exactement avec 3 points (degré 2·3 − 1 = 5)
    assert np.sum(0.5 * w * (0.5 + 0.5 * x) ** 5) == pytest.approx(1 / 6, rel=1e-14)
    x1, w1 = _gauss(1)
    assert (x1[0], w1[0]) == (0.0, 2.0)
    assert _gauss(3)[0] is x  # mémorisé
    for ng in (3, 5, 12):
        xg, wg = _gauss(ng)
        assert wg.sum() == pytest.approx(2.0, rel=1e-13)
        assert np.sum(wg * xg**4) == pytest.approx(2 / 5, rel=1e-13)


def test_gauss_data_and_vals():
    br = [0.0, 0.4, 1.0]
    G = _gaussData(br, 3, 5)
    assert G["V"].shape == (6, 6) and list(G["seg"]) == [0, 0, 0, 1, 1, 1]
    C = np.array([[1.0, 0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0, 0]])  # s⁵ sur les deux tronçons
    assert np.sum(G["w"] * _gaussVals(G, C)) == pytest.approx(1 / 6, rel=1e-14)
    C2 = np.array([[0, 0, 0, 0, 2.0, 0], [0, 0, 0, 0, 0, 3.0]])  # 2 s sur [0 ; 0,4] puis 3 sur [0,4 ; 1]
    assert np.sum(G["w"] * _gaussVals(G, C2)) == pytest.approx(0.16 + 1.8, rel=1e-14)


def test_matrix_representation():
    br = np.array([0.0, 1.0, 3.0])
    C = np.array([[2.0, 0.0], [0.0, 3.0]])  # 2 s puis 3
    P = _matIntegrate(C, br)
    assert P.shape == (2, 3)
    assert np.allclose(P, [[1.0, 0.0, 0.0], [0.0, 3.0, -2.0]])  # s² puis 3 s − 2 : primitive continue, nulle en 0
    assert np.allclose(_matEval(P, br, [0.0, 0.5, 1.0, 2.0, 3.0]), [0.0, 0.25, 1.0, 4.0, 7.0])  # limite à droite en 1
    assert _matEval(C, br, []).shape == (0,)
    assert _matEval(C, br, 2.0)[0] == 3.0
    # nettoyage : le terme 1e-20·s sur [0, 1] est négligeable, pas le terme constant
    Cn = _cleanMat(np.array([[1e-20, 1.0]]), [0.0, 1.0], 1e-12)
    assert np.array_equal(Cn, [[0.0, 1.0]])
    Cin = np.array([[1e-20, 1.0]])
    assert np.array_equal(_cleanMat(Cin, [0.0, 1.0], 0.0), Cin) and _cleanMat(Cin, [0.0, 1.0], 0.0) is not Cin
    pp = _matToPP(np.array([[0.0, 0.0, 5.0], [0.0, 0.0, 0.0], [1.0, -2.0, 0.0]]), [0.0, 1.0, 2.0, 3.0])
    assert [list(c) for c in pp.coefs] == [[5.0], [0.0], [1.0, -2.0, 0.0]]
    assert ppEval(pp, 2.5) == pytest.approx(2.5**2 - 2 * 2.5)
    assert _matMaxAbs(np.array([[1.0, 0.0, -1.0]]), [-2.0, 2.0]) == pytest.approx(3.0)


def test_cut_bend_tip_load():
    # console de longueur 4 m, force −1000 N à l'extrémité : T = −1000, M = 1000 s − 4000
    T, M = _cutBend([0.0, 4.0], 1e-12 * 4, [4.0], [-1000.0], [], [], [], 1)
    assert np.allclose(T, [[0.0, -1000.0]]) and np.allclose(M, [[1000.0, -4000.0]])


def test_cut_bend_couple_and_uniform_load():
    q = 1000.0
    m, _ = _normalizeModel(addQ(baseModel(4), 1, 3, "y", q))
    dl = _prepDist(m["distLoads"])
    br = [0.0, 1.0, 3.0, 3.5, 4.0]  # charge sur [1, 3], couple de 200 N·m en 3,5
    T, M = _cutBend(br, 4e-12, [], [], [3.5], [200.0], dl, 2)
    # [0, 1] : toute la charge est à droite ; [1, 3] : charge en cours ; au-delà de 3, plus de charge à droite
    assert np.allclose(T, [[0, 0, 2 * q], [0, -q, 3 * q], [0, 0, 0], [0, 0, 0]])
    assert np.allclose(M[0], [0, -2 * q, 4 * q + 200])  # ∫_1^3 (x − s) q dx = 4q − 2q s, plus le couple
    assert np.allclose(M[1], [q / 2, -3 * q, 4.5 * q + 200])  # q (3 − s)² / 2, plus le couple
    assert np.allclose(M[2], [0, 0, 200.0])  # le couple est à droite du tronçon [3 ; 3,5]
    assert np.allclose(M[3], 0.0)  # et à gauche du dernier


def chargeY(m, pos, fy):
    """Ajoute une force verticale fy (N) en s = pos (m) ; la normalisation complète les autres composantes à 0."""
    m["pointLoads"].append({"pos": pos, "Fy": fy})
    return m


def sur_deux_appuis():
    """Poutre de 4 m sur pivot A et appui simple B, force de −1000 N en s = 1."""
    return chargeY(addSup(addSup(baseModel(4), 0, "pivot", "A"), 4, "appui_simple", "B"), 1, -1000)


def console_appuyee():
    """Poutre de 4 m encastrée en A et sur appui simple B (hyperstatique de degré 1 par plan)."""
    return addSup(addSup(baseModel(4), 0, "encastrement", "A"), 4, "appui_simple", "B")


def test_solveBeam_isostatique_structure():
    sol = solveBeam(sur_deux_appuis(), COUPURES_MENABREA)
    assert sol["isostatic"] and sol["h"] == dict.fromkeys(("axial", "xy", "xz", "torsion", "total", "plan2D"), 0)
    assert [(r["name"], r["pos"], r["type"]) for r in sol["reactions"]] == [("A", 0, "pivot"), ("B", 4, "appui_simple")]
    assert [r["Ry"] for r in sol["reactions"]] == pytest.approx([750.0, 250.0], rel=1e-12)
    assert set(sol["reactions"][0]) == {"name", "pos", "type", "Rx", "Ry", "Rz", "Mx", "My", "Mz"}
    assert list(sol["breaks"]) == [0.0, 1.0, 4.0]
    assert all(isinstance(sol[c], PP) for c in ("N", "Ty", "Tz", "Mt", "Mfy", "Mfz"))
    # Ty(s) = Σ_droite Fy ; Mfz(s) = Σ_droite (xi − s)·Fyi
    assert ppEval(sol["Ty"], [0.5, 2.0]) == pytest.approx([-750.0, 250.0], rel=1e-12)
    assert ppEval(sol["Mfz"], [0.5, 2.0]) == pytest.approx([375.0, 500.0], rel=1e-12)
    ext = sol["extrema"]["Mfz"]
    assert (ext["max"], ext["sMax"]) == (pytest.approx(750.0), pytest.approx(1.0))
    assert set(sol["extrema"]) == {"N", "Ty", "Tz", "Mt", "Mfy", "Mfz"}
    assert sol["menabrea"] == {} and sol["integration"] == {} and sol["reactionsMenabrea"] == []
    assert math.isnan(sol["hyperCheck"]) and sol["methodUsed"] == "coupures"
    assert sol["model"]["supports"][0]["name"] == "A"


def test_solveBeam_options_par_defaut_sur_isostatique():
    sol = solveBeam(sur_deux_appuis())  # both / both : aucun appel à l'intégration sur un isostatique
    assert sol["reactions"][0]["Ry"] == pytest.approx(750.0, rel=1e-12)


def test_provisoire_E10():
    assert _provisoire_E10() == ({}, pytest.approx(math.nan, nan_ok=True), [], [], [])
    sol = solveBeam(sur_deux_appuis(), COUPURES_MENABREA)
    assert sol["internalIntegral"] == {} and math.isnan(sol["methodCheck"])
    assert sol["equations"] == [] and sol["report"] == [] and sol["latex"] == []


def test_menabrea_console_appuyee_force_au_milieu():
    m = chargeY(console_appuyee(), 2, -1000)
    sol = solveBeam(m, COUPURES_MENABREA)
    assert not sol["isostatic"] and (sol["h"]["xy"], sol["h"]["xz"], sol["h"]["total"], sol["h"]["plan2D"]) == (
        1,
        1,
        2,
        1,
    )
    A, B = sol["reactions"]
    # console appuyée, force P au milieu : R_B = 5P/16, R_A = 11P/16, M_A = 3PL/16
    assert (A["Ry"], B["Ry"], A["Mz"]) == pytest.approx((687.5, 312.5, 750.0), rel=1e-9)
    men = sol["menabrea"]["xy"]
    assert (men["unknowns"], men["base"], men["includeShear"]) == (["Y_B"], ["Y_A", "Mz_A"], False)
    assert men["X"] == pytest.approx([312.5], rel=1e-9)
    assert list(sol["menabrea"]) == ["xy"]  # le plan (x,z) non chargé n'a pas de système de Ménabréa
    assert sol["reactionsMenabrea"] == sol["reactions"] and sol["reactionsIntegration"] == []
    assert math.isnan(sol["hyperCheck"])


def test_menabrea_cisaillement_et_tassement():
    m = chargeY(console_appuyee(), 2, -1000)
    avec = solveBeam(m, {**COUPURES_MENABREA, "includeShearEnergy": True})
    sans = solveBeam(m, COUPURES_MENABREA)
    assert avec["menabrea"]["xy"]["includeShear"] is True
    EI, kGS, P, L = 210e9 * 8e-6, 80e9 * 2e-3, 1000.0, 4.0  # flèche de B de la console libre / flexibilité de B
    RB = (5 * P * L**3 / (48 * EI) + P * (L / 2) / kGS) / (L**3 / (3 * EI) + L / kGS)
    assert avec["reactions"][1]["Ry"] == pytest.approx(RB, rel=1e-9) and RB > sans["reactions"][1]["Ry"]
    t = console_appuyee()  # sans charge : le tassement dy du seul appui B charge l'hyperstatique, R_B = 3·E·Iz·dy/L³
    t["supports"][1]["dy"] = -0.002
    assert solveBeam(t, COUPURES_MENABREA)["reactions"][1]["Ry"] == pytest.approx(
        3 * 210e9 * 8e-6 * -0.002 / 4**3, rel=1e-9
    )


def test_integration_pas_encore_portee():
    m = chargeY(console_appuyee(), 2, -1000)
    for opts in ({"hyperMethod": "integration"}, {"hyperMethod": "both"}, None):
        with pytest.raises(NotImplementedError, match="E09"):
            solveBeam(m, opts)


def test_mecanisme():
    m = chargeY(addSup(baseModel(4), 0, "appui_simple", "A"), 2, -1000)  # un seul appui simple, force excentrée
    verifier_erreur(MECANISME, solveBeam, m)
    m = addSup(addSup(baseModel(4), 0, "pivot", "A"), 4, "appui_simple", "B")  # torsion sans encastrement
    m["pointMoments"].append({"pos": 2, "Mx": 500})
    verifier_erreur(MECANISME, solveBeam, m)
    verifier_erreur(MECANISME, solveBeam, chargeY(baseModel(4), 2, -1000))  # aucune liaison
    sol = solveBeam(chargeY(addSup(baseModel(4), 2, "appui_simple", "A"), 2, -1000))  # appui sous la force : compatible
    assert sol["reactions"][0]["Ry"] == pytest.approx(1000.0, rel=1e-12) and sol["h"]["total"] == 0


def test_buildSubs_inconnues_et_ordre_de_base():
    mdl, _ = _normalizeModel(console_appuyee())
    sps = _buildSubs(mdl, [], "A")
    assert [s["name"] for s in sps] == ["axial", "xy", "xz", "torsion"]
    assert [[u["name"] for u in s["unk"]] for s in sps] == [
        ["X_A"],
        ["Y_A", "Y_B", "Mz_A"],
        ["Z_A", "Z_B", "My_A"],
        ["Mx_A"],
    ]
    assert [u["sgn"] for u in sps[2]["unk"]] == [1, 1, -1]
    assert sps[1]["unk"][2]["tex"] == "M_{zA}" and sps[2]["rowSign"] == [1, -1]
    assert _baseOrder(sps[1]["unk"], True) == [0, 2, 1]  # force et moment de l'encastrement, puis l'autre appui
    assert _baseOrder([], True) == []


def test_extrema():
    pp = PP(np.array([0.0, 3.0, 5.0]), [np.array([-1.0, 4.0, 0.0]), np.array([2.0, -9.0])])
    assert _extrema(pp) == {"max": 4.0, "sMax": 2.0, "min": -3.0, "sMin": 3.0}  # racine de la dérivée, puis bornes
    sans_racine_reelle = PP(
        np.array([0.0, 1.0]), [np.array([1.0, 0.0, 1.0, 0.0])]
    )  # s³ + s : dérivée sans racine réelle
    assert _extrema(sans_racine_reelle) == {"max": 2.0, "sMax": 1.0, "min": 0.0, "sMin": 0.0}


def test_actions_et_sauts():
    sol = solveBeam(sur_deux_appuis(), COUPURES_MENABREA)
    act = _actions(sol["model"], sol["reactions"])
    assert np.allclose(act["Fy"], [[1, -1000], [0, 750], [4, 250]])  # charges puis réactions
    assert act["Mz"].shape == (2, 2) and act["Fx"].shape == (3, 2)
    noms = ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]
    assert np.allclose(_jumps(act, noms, 1.0, 1e-9), [0, -1000, 0, 0, 0, 0])
    assert np.allclose(_jumps(act, noms, 2.0, 1e-9), 0.0)


def test_bendDisp_condText_reactionDiff():
    # moment constant M0 = 1000 N·m sur 2 m : θ(L) = M0·L/EI et v(L) = M0·L²/(2·EI) ; le cisaillement ajoute T·L/kGS
    M, T = np.array([[1000.0]]), np.array([[100.0]])
    v, th = _bendDisp(M, T, [0.0, 2.0], [2.0], 1e6, 1e5, False)
    assert (v[0], th[0]) == pytest.approx((1000 * 4 / 2 / 1e6, 1000 * 2 / 1e6), rel=1e-14)
    assert _bendDisp(M, T, [0.0, 2.0], [2.0], 1e6, 1e5, True)[0][0] == pytest.approx(v[0] + 100 * 2 / 1e5, rel=1e-14)
    assert _condText("v", "B", 0.0, 0.0) == "v(B) = 0"
    assert _condText("v", "B", -0.002, 0.0) == "v(B) = -0.002 m"
    assert _condText("w", "C", 0.0, 1e6) == "w(C) = 0 - R/k (k = 1e+06 N/m)"
    unk = [{"kind": "F"}, {"kind": "C"}]
    assert _reactionDiff(
        np.array([10.0, 0.0]), np.array([10.1, 0.0]), unk, True, np.array([100.0, 400.0])
    ) == pytest.approx(1e-3)


# ---------------------------------------------------------------------------------------------------------------------
# E08c : cas d'école de tests/test_BeamAndTrussSolver.m (OPTS : Ménabréa et coupures seulement)
# ---------------------------------------------------------------------------------------------------------------------

OPTS = COUPURES_MENABREA
EI = 210e9 * 8e-6


def addF(m, pos, Fx, Fy, Fz):
    m["pointLoads"].append({"pos": pos, "Fx": Fx, "Fy": Fy, "Fz": Fz, "name": f"F{len(m['pointLoads']) + 1}"})
    return m


def addC(m, pos, Mx, My, Mz):
    m["pointMoments"].append({"pos": pos, "Mx": Mx, "My": My, "Mz": Mz, "name": f"C{len(m['pointMoments']) + 1}"})
    return m


def col(sol, champ):
    """Valeurs d'un champ des réactions, dans l'ordre des appuis ([sol.reactions.Ry] de MATLAB)."""
    return [r[champ] for r in sol["reactions"]]


def deflectionAt(sol, EI, conds, sEval):
    """Flèche par double intégration (ppIntegrate) : E I v'' = Mfz, v = I2 + C1 + C2 s ; renvoie (v, résidu).

    conds : lignes (s, type), type 0 : v(s) = 0, type 1 : v'(s) = 0.
    """
    I1 = ppIntegrate(ppScale(sol["Mfz"], 1 / EI), 0.0)
    I2 = ppIntegrate(I1, 0.0)
    A = np.zeros((len(conds), 2))
    b = np.zeros(len(conds))
    for k, (s, typ) in enumerate(conds):
        if typ == 0:
            A[k] = [1.0, s]
            b[k] = -ppEval(I2, s)
        else:
            A[k] = [0.0, 1.0]
            b[k] = -ppEval(I1, s)
    C = np.linalg.solve(A, b) if len(conds) == 2 else np.linalg.lstsq(A, b, rcond=None)[0]
    v = ppEval(I2, sEval) + C[0] + C[1] * sEval
    scale = np.max(np.abs(ppEval(I2, np.linspace(0, sol["model"]["L"], 21))))
    return v, np.max(np.abs(A @ C - b)) / max(scale, np.finfo(float).tiny)


def test_SimplySupportedCentralLoad():
    L, P = 4.0, 1e4
    m = addF(addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B"), L / 2, 0, -P, 0)
    sol = solveBeam(m, OPTS)
    assert sol["isostatic"]
    assert [sol["h"][k] for k in ("axial", "xy", "xz", "torsion", "total", "plan2D")] == [0] * 6
    assert col(sol, "Ry") == pytest.approx([P / 2, P / 2], rel=1e-12)
    assert [r[c] for r in sol["reactions"] for c in ("Rx", "Rz", "Mz")] == [0] * 6
    assert sol["extrema"]["Mfz"]["max"] == pytest.approx(P * L / 4, rel=1e-12)
    assert sol["extrema"]["Mfz"]["sMax"] == pytest.approx(L / 2, abs=1e-12)
    assert ppEval(sol["Mfz"], L / 2) == pytest.approx(P * L / 4, rel=1e-12)
    # saut de Ty : Ty(a-) = Ty(a+) + Fy
    assert ppEval(sol["Ty"], L / 2, "left") == pytest.approx(ppEval(sol["Ty"], L / 2, "right") - P, rel=1e-12)
    assert ppEval(sol["Ty"], 1.0) == pytest.approx(-P / 2, rel=1e-12)
    v, _ = deflectionAt(sol, EI, [(0, 0), (L, 0)], L / 2)  # flèche : PL³/(48EI)
    assert v == pytest.approx(-P * L**3 / (48 * EI), rel=1e-10)
    assert sol["menabrea"] == {} and sol["reactionsMenabrea"] == [] and sol["reactionsIntegration"] == []
    assert list(sol["breaks"]) == [0.0, L / 2, L]


def test_CantileverTipLoad():
    L, P = 3.0, 2e3
    sol = solveBeam(addF(addSup(baseModel(L), 0, "encastrement", "A"), L, 0, -P, 0), OPTS)
    assert sol["isostatic"] and sol["h"]["total"] == 0
    assert ppEval(sol["Mfz"], 0.0) == pytest.approx(-P * L, rel=1e-12)
    assert sol["reactions"][0]["Ry"] == pytest.approx(P, rel=1e-12)
    assert sol["reactions"][0]["Mz"] == pytest.approx(P * L, rel=1e-12)
    assert sol["extrema"]["Mfz"]["min"] == pytest.approx(-P * L, rel=1e-12)
    assert sol["extrema"]["Mfz"]["sMin"] == 0
    v, _ = deflectionAt(sol, EI, [(0, 0), (0, 1)], L)
    assert v == pytest.approx(-P * L**3 / (3 * EI), rel=1e-10)


def test_SimplySupportedUniform():
    L, q = 6.0, 5e3
    m = addQ(addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B"), 0, L, "y", -q)
    sol = solveBeam(m, OPTS)
    assert col(sol, "Ry") == pytest.approx([q * L / 2, q * L / 2], rel=1e-12)
    assert sol["extrema"]["Mfz"]["max"] == pytest.approx(q * L**2 / 8, rel=1e-12)
    assert sol["extrema"]["Mfz"]["sMax"] == pytest.approx(L / 2, rel=1e-10)
    v, _ = deflectionAt(sol, EI, [(0, 0), (L, 0)], L / 2)
    assert v == pytest.approx(-5 * q * L**4 / (384 * EI), rel=1e-10)
    # relations différentielles : dTy/ds = -py et Ty = -dMfz/ds
    t = np.array([0.4, 2.2, 5.1])
    assert ppEval(ppDerivative(sol["Ty"]), t) == pytest.approx(q * np.ones(3), rel=1e-12)
    assert ppEval(ppDerivative(sol["Mfz"]), t) == pytest.approx(-ppEval(sol["Ty"], t), rel=1e-12)


def test_ProppedCantileverUniform():
    L, q = 5.0, 1e3
    m = addQ(addSup(addSup(baseModel(L), 0, "encastrement", "A"), L, "appui_simple", "B"), 0, L, "y", -q)
    sol = solveBeam(m, OPTS)
    assert not sol["isostatic"] and sol["h"]["xy"] == 1 and sol["h"]["plan2D"] == 1
    A, B = sol["reactions"]
    assert B["Ry"] == pytest.approx(3 * q * L / 8, rel=1e-12)
    assert A["Ry"] == pytest.approx(5 * q * L / 8, rel=1e-12)
    assert A["Mz"] == pytest.approx(q * L**2 / 8, rel=1e-12)
    assert ppEval(sol["Mfz"], 0.0) == pytest.approx(-q * L**2 / 8, rel=1e-12)
    assert sol["extrema"]["Mfz"]["max"] == pytest.approx(9 * q * L**2 / 128, rel=1e-12)
    assert sol["extrema"]["Mfz"]["sMax"] == pytest.approx(5 * L / 8, rel=1e-10)
    # Ménabréa : système de base console, X = Y_B
    men = sol["menabrea"]["xy"]
    assert men["unknowns"] == ["Y_B"]
    assert men["X"] == pytest.approx(3 * q * L / 8, rel=1e-12)
    assert men["delta"] == pytest.approx(L**3 / (3 * EI), rel=1e-12)
    assert men["rhs"] == pytest.approx(q * L**4 / (8 * EI), rel=1e-12)
    assert sol["reactionsMenabrea"][0]["Mz"] == pytest.approx(q * L**2 / 8, rel=1e-12)
    # compatibilité cinématique : v(0) = v'(0) = v(L) = 0 vérifiées ensemble
    _, res = deflectionAt(sol, EI, [(0, 0), (0, 1), (L, 0)], L / 2)
    assert res < 1e-12


def test_TwoEqualSpansUniform():
    L, q = 4.0, 2e3
    m = addSup(addSup(addSup(baseModel(2 * L), 0, "pivot", "A"), L, "appui_simple", "B"), 2 * L, "appui_simple", "C")
    sol = solveBeam(addQ(m, 0, 2 * L, "y", -q), OPTS)
    assert sol["h"]["xy"] == 1
    assert col(sol, "Ry") == pytest.approx([3 * q * L / 8, 5 * q * L / 4, 3 * q * L / 8], rel=1e-12)
    assert ppEval(sol["Mfz"], L) == pytest.approx(-q * L**2 / 8, rel=1e-12)
    assert sol["menabrea"]["xy"]["unknowns"] == ["Y_B"]
    _, res = deflectionAt(sol, EI, [(0, 0), (L, 0), (2 * L, 0)], L / 2)
    assert res < 1e-12


def test_FixedFixedUniform():
    L, q = 4.0, 3e3
    m = addQ(addSup(addSup(baseModel(L), 0, "encastrement", "A"), L, "encastrement", "B"), 0, L, "y", -q)
    sol = solveBeam(m, OPTS)
    assert [sol["h"][k] for k in ("axial", "xy", "xz", "torsion", "total")] == [1, 2, 2, 1, 6]
    assert ppEval(sol["Mfz"], np.array([0.0, L / 2, L])) == pytest.approx(
        [-q * L**2 / 12, q * L**2 / 24, -q * L**2 / 12], rel=1e-11
    )
    assert col(sol, "Ry") == pytest.approx([q * L / 2, q * L / 2], rel=1e-12)
    assert col(sol, "Mz") == pytest.approx([q * L**2 / 12, -q * L**2 / 12], rel=1e-11)
    v, _ = deflectionAt(sol, EI, [(0, 0), (0, 1)], L / 2)
    assert v == pytest.approx(-q * L**4 / (384 * EI), rel=1e-10)
    _, res = deflectionAt(sol, EI, [(0, 0), (0, 1), (L, 0), (L, 1)], L / 2)
    assert res < 1e-12
    men = sol["menabrea"]["xy"]
    assert sorted(men["unknowns"]) == ["Mz_B", "Y_B"] and np.shape(men["delta"]) == (2, 2)


def test_AxialBarFixedFixed():
    L, F = 4.0, 6e3
    m = addF(addSup(addSup(baseModel(L), 0, "encastrement", "A"), L, "encastrement", "B"), L / 2, F, 0, 0)
    sol = solveBeam(m, OPTS)
    assert sol["h"]["axial"] == 1
    assert col(sol, "Rx") == pytest.approx([-F / 2, -F / 2], rel=1e-12)
    assert ppEval(sol["N"], np.array([1.0, 3.0])) == pytest.approx([F / 2, -F / 2], rel=1e-12)
    men = sol["menabrea"]["axial"]
    assert men["unknowns"] == ["X_B"] and men["X"] == pytest.approx(-F / 2, rel=1e-12)
    # position quelconque : répartition selon les raideurs
    a = 1.0
    m2 = addF(addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "rotule", "B"), a, F, 0, 0)
    sol2 = solveBeam(m2, OPTS)
    assert col(sol2, "Rx") == pytest.approx([-F * (L - a) / L, -F * a / L], rel=1e-12)
    assert sol2["h"]["axial"] == 1 and sol2["h"]["xy"] == 0


def test_LoadsInPlaneXZ():
    L, P, q, C0, a = 4.0, 8e3, 2e3, 5e3, 1.0
    # (a) force Fz centrée sur poutre sur deux appuis
    m = addF(addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B"), L / 2, 0, 0, -P)
    sol = solveBeam(m, OPTS)
    assert col(sol, "Rz") == pytest.approx([P / 2, P / 2], rel=1e-12)
    assert ppEval(sol["Mfy"], L / 2) == pytest.approx(-P * L / 4, rel=1e-12)
    assert ppEval(sol["Tz"], 1.0) == pytest.approx(-P / 2, rel=1e-12)
    t = np.array([0.5, 1.7, 2.6, 3.9])
    assert ppEval(ppDerivative(sol["Mfy"]), t) == pytest.approx(ppEval(sol["Tz"], t), rel=1e-12)
    assert sol["extrema"]["Mfz"]["max"] == 0
    # (b) encastrée-appuyée dans le plan xz, charge pz uniforme
    m = addQ(addSup(addSup(baseModel(L), 0, "encastrement", "A"), L, "appui_simple", "B"), 0, L, "z", -q)
    sol = solveBeam(m, OPTS)
    assert sol["h"]["xz"] == 1
    assert sol["reactions"][1]["Rz"] == pytest.approx(3 * q * L / 8, rel=1e-12)
    assert sol["reactions"][0]["My"] == pytest.approx(-q * L**2 / 8, rel=1e-12)
    assert ppEval(sol["Mfy"], 0.0) == pytest.approx(q * L**2 / 8, rel=1e-12)
    # flèche w : E Iy w'' = -Mfy, w(L) = 0 pour la console équivalente
    EIy = 210e9 * 3e-6
    I2 = ppIntegrate(ppIntegrate(ppScale(sol["Mfy"], -1 / EIy)))
    wmax = np.max(np.abs(ppEval(I2, np.linspace(0, L, 41))))
    assert wmax > 0
    assert ppEval(I2, L) == pytest.approx(0.0, abs=1e-12 * wmax)
    # (c) couple My sur poutre sur deux appuis
    m = addC(addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B"), a, 0, C0, 0)
    sol = solveBeam(m, OPTS)
    assert col(sol, "Rz") == pytest.approx([-C0 / L, C0 / L], rel=1e-12)
    assert ppEval(sol["Mfy"], a, "left") - ppEval(sol["Mfy"], a, "right") == pytest.approx(C0, rel=1e-12)


def test_Torsion():
    L, C, a = 4.0, 900.0, 1.0
    sol = solveBeam(addC(addSup(baseModel(L), 0, "encastrement", "A"), L, C, 0, 0), OPTS)
    assert sol["reactions"][0]["Mx"] == pytest.approx(-C, rel=1e-12)
    assert ppEval(sol["Mt"], np.array([0.0, 2.0, L])) == pytest.approx([C, C, C], rel=1e-12)
    assert sol["h"]["torsion"] == 0
    # arbre bi-encastré : couple en a
    m = addC(addSup(addSup(baseModel(L), 0, "encastrement", "A"), L, "encastrement", "B"), a, C, 0, 0)
    sol = solveBeam(m, OPTS)
    assert sol["h"]["torsion"] == 1
    assert col(sol, "Mx") == pytest.approx([-C * (L - a) / L, -C * a / L], rel=1e-12)
    assert ppEval(sol["Mt"], np.array([0.5, 2.0])) == pytest.approx([C * (L - a) / L, -C * a / L], rel=1e-12)
    assert sol["menabrea"]["torsion"]["unknowns"] == ["Mx_B"]


def test_PointCouple():
    L, C0, a = 4.0, 4e3, 1.0
    m = addC(addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B"), a, 0, 0, C0)
    sol = solveBeam(m, OPTS)
    assert col(sol, "Ry") == pytest.approx([C0 / L, -C0 / L], rel=1e-12)
    Ml, Mr = ppEval(sol["Mfz"], a, "left"), ppEval(sol["Mfz"], a, "right")
    assert Ml == pytest.approx(C0 * a / L, rel=1e-12)
    assert Mr == pytest.approx(-C0 * (L - a) / L, rel=1e-12)
    assert Ml - Mr == pytest.approx(C0, rel=1e-12)
    assert sol["extrema"]["Mfz"]["max"] == pytest.approx(C0 * a / L, rel=1e-12)
    assert sol["extrema"]["Mfz"]["min"] == pytest.approx(-C0 * (L - a) / L, rel=1e-12)


def test_TriangularLinearLoad():
    L, q0 = 6.0, 3e3
    m = addQ(addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B"), 0, L, "y", [-q0 / L, 0.0])
    sol = solveBeam(m, OPTS)
    assert col(sol, "Ry") == pytest.approx([q0 * L / 6, q0 * L / 3], rel=1e-12)
    assert sol["extrema"]["Mfz"]["max"] == pytest.approx(q0 * L**2 / (9 * math.sqrt(3)), rel=1e-12)
    assert sol["extrema"]["Mfz"]["sMax"] == pytest.approx(L / math.sqrt(3), rel=1e-9)


def test_PartialTrapezoidLoadLocalXi():
    # charge linéaire de p1 = -2000 (s = 1) à p2 = -6000 (s = 3), ξ = s - a
    L, a, b, p1, p2 = 4.0, 1.0, 3.0, -2000.0, -6000.0
    m = addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B")
    sol = solveBeam(addQ(m, a, b, "y", [(p2 - p1) / (b - a), p1]), OPTS)
    W = (b - a) * (p1 + p2) / 2
    xbar = a + (b - a) * (p1 + 2 * p2) / (3 * (p1 + p2))
    RB = -W * xbar / L
    RA = -W - RB
    assert col(sol, "Ry") == pytest.approx([RA, RB], rel=1e-12)
    assert list(sol["breaks"]) == [0.0, 1.0, 3.0, 4.0]

    def p(x):
        return p1 + (p2 - p1) / (b - a) * (x - a)

    def integrale(f, s):
        """∫_s^L f(x)·1[a ≤ x ≤ b] dx, par quad sur la partie chargée [max(s, a), b]."""
        return quad(f, max(s, a), b, epsabs=1e-12, epsrel=1e-13)[0] if s < b else 0.0

    for s in (0.5, 1.5, 2.0, 2.7, 3.5):
        Ty = RB + integrale(p, s)
        Mz = (L - s) * RB + integrale(lambda x, s=s: (x - s) * p(x), s)
        assert ppEval(sol["Ty"], s) == pytest.approx(Ty, rel=1e-9)
        assert ppEval(sol["Mfz"], s) == pytest.approx(Mz, rel=1e-9)
    assert ppEval(sol["Mfz"], 2.0) == pytest.approx(6000.0, rel=1e-12)
    assert list(sol["model"]["distLoads"][0]["coeffs"]) == [(p2 - p1) / (b - a), p1]


def test_MechanismDetection():
    L = 4.0
    # un seul appui simple, force excentrée : mécanisme
    verifier_erreur(MECANISME, solveBeam, addF(addSup(baseModel(L), 0, "appui_simple", "A"), 2, 0, -1e3, 0), OPTS)
    # deux appuis simples et effort axial : mécanisme axial
    m = addSup(addSup(baseModel(L), 0, "appui_simple", "A"), L, "appui_simple", "B")
    verifier_erreur(MECANISME, solveBeam, addF(m, 2, 1e3, 0, 0), OPTS)
    # aucune liaison et force : mécanisme
    verifier_erreur(MECANISME, solveBeam, addF(baseModel(L), 2, 0, -1e3, 0), OPTS)
    # torsion sans encastrement : mécanisme
    m = addSup(addSup(baseModel(L), 0, "pivot", "A"), L, "appui_simple", "B")
    verifier_erreur(MECANISME, solveBeam, addC(m, 2, 500, 0, 0), OPTS)
    # deux appuis au même point, force ailleurs : mécanisme
    m = addSup(addSup(baseModel(L), 1, "pivot", "A"), 1, "appui_simple", "B")
    verifier_erreur(MECANISME, solveBeam, addF(m, 3, 0, -1e3, 0), OPTS)
    # sous-problèmes non chargés ou chargements équilibrés : pas d'erreur
    m = addSup(addSup(baseModel(L), 0, "appui_simple", "A"), L, "appui_simple", "B")
    m = addC(addC(addF(m, 2, 0, -1e3, 0), 1, 300, 0, 0), 3, -300, 0, 0)
    sol = solveBeam(m, OPTS)
    assert col(sol, "Ry") == pytest.approx([500, 500], rel=1e-12)
    assert sol["h"]["axial"] == 0 and sol["h"]["torsion"] == 0 and sol["h"]["plan2D"] == -1
    # Mt(s) = Σ_droite Mx : entre les deux couples, seul -300 (en s = 3) est à droite
    assert ppEval(sol["Mt"], np.array([0.5, 2.0, 3.5])) == pytest.approx([0, -300, 0], abs=1e-12)
    # appui unique sous la force : chargement compatible
    sol = solveBeam(addF(addSup(baseModel(L), 2, "appui_simple", "A"), 2, 0, -1e3, 0), OPTS)
    assert sol["reactions"][0]["Ry"] == pytest.approx(1e3, rel=1e-12) and sol["h"]["total"] == 0


def test_FastPathPerformance():
    m = addSup(addSup(addSup(baseModel(6), 0, "pivot", "A"), 3, "appui_simple", "B"), 6, "appui_simple", "C")
    for pos, fy in ((1, -1000), (2, -2000), (4, -1500), (5, -500)):
        addF(m, pos, 0, fy, 0)
    solveBeam(m, OPTS)  # échauffement
    t0 = time.perf_counter()
    for _ in range(50):
        sol = solveBeam(m, OPTS)
    duree = time.perf_counter() - t0
    assert duree < 1.0, f"chemin rapide trop lent : {1000 * duree / 50:.1f} ms par appel"
    assert sum(col(sol, "Ry")) == pytest.approx(5000, rel=1e-12)


# ---------------------------------------------------------------------------------------------------------------------
# E08c : golden_beam.json, cas solveBeam sans ressort, tassement, rotule ni thermique (ceux-là sont en E09)
# ---------------------------------------------------------------------------------------------------------------------

HORS_E08 = ("gerber_", "appui_elastique_", "tassement_", "thermique_")
IDS_GOLDEN = [i for i in case_ids("golden_beam.json", suffix="_solveBeam") if not i.startswith(HORS_E08)]
# Ignorés par assert_matches : E09 / E10, et les abscisses sMin / sMax, comparées à part par verifie_abscisses_extrema.
IGNORE_GOLDEN = {
    "equations",
    "internalIntegral",
    "methodCheck",
    "hyperCheck",
    "reactionsIntegration",
    "integration",
    "sMin",
    "sMax",
}


def verifie_abscisses_extrema(sol, extrema):
    """Compare les abscisses sMin et sMax de Python à celles du golden, avec le repli autorisé par Théo (E08c).

    Quand deux abscisses donnent exactement le même extremum (bi_encastree_uniforme : Mfz(0) = Mfz(L) = −12 000 N·m),
    MATLAB et Python les départagent par le bruit d'arrondi (1e-15 relatif) et retiennent deux abscisses différentes.
    Si l'abscisse de Python diffère de celle du golden (rel 1e-9, abs 1e-6 m), on vérifie alors que la valeur de la
    fonction à l'abscisse de Python égale l'extremum du golden à rel 1e-9. Cela ne concerne que les champs sMin et
    sMax ; le golden et les autres tolérances sont inchangés.
    """
    for nom, e in extrema.items():
        for champ_s, champ_v in (("sMax", "max"), ("sMin", "min")):
            s = sol["extrema"][nom][champ_s]
            if math.isclose(s, e[champ_s], rel_tol=1e-9, abs_tol=1e-6):
                continue
            v = ppEval(sol[nom], s)
            assert math.isclose(v, e[champ_v], rel_tol=1e-9), (
                f"extrema.{nom}.{champ_s} : {e[champ_s]!r} attendu, obtenu {s!r} ; "
                f"valeur à cette abscisse {v!r} au lieu de l'extremum {e[champ_v]!r}"
            )


@pytest.mark.parametrize("cid", IDS_GOLDEN)
def test_golden_solveBeam(cid):
    c = get_case("golden_beam.json", cid)
    sol = solveBeam(c["entrees"], OPTS)
    assert_matches(sol, c["sortie"], rel=1e-9, abs_=1e-6, ignore=IGNORE_GOLDEN)
    verifie_abscisses_extrema(sol, c["sortie"]["extrema"])
