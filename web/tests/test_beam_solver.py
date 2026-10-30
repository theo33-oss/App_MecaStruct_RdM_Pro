"""Tests de beam_solver, sous-étapes E08a et E08b.

E08a : options, normalisation du modèle, Gauss, matrices de coefficients, coupures. Portage de testInvalidInputs et de
la partie normalisation de testNormalizationAndDefaults (tests/test_BeamAndTrussSolver.m) ; les erreurs passent ici par
_normalizeModel et _beamOpts.
E08b : sous-problèmes, Ménabréa, extrema, solveBeam (structure du résultat, mécanisme, E09). Les cas d'école de MATLAB
et les golden viennent en E08c.
"""

import copy
import math

import numpy as np
import pytest

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
from mecastruct.core.pp import PP, ppEval

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
