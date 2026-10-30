"""Tests de deflection (étape E13) : déformée par 4 méthodes, énergie de déformation, intégrales de Mohr.

Portage des tests de flèche, d'énergie et de Mohr de tests/test_SolicitationsEngine.m, du cas README (IPE 200) et des
golden files (golden_beam.json : cas *_deflection et *_strainEnergy ; golden_solicitations.json : mohrIntegral).
testBucklingDelegation est porté dans test_buckling.py (E14).
"""

import copy
import math

import numpy as np
import pytest
from scipy.integrate import quad

from mecastruct.core import beam_solver, deflection, geometry
from mecastruct.core import solicitations as se
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import ppEval
from tests.golden_tools import assert_matches, case_ids, get_case

GOLDEN_BEAM = "golden_beam.json"
GOLDEN_SOL = "golden_solicitations.json"
INVALIDE = "MecaStruct:SolicitationsEngine:invalidInput"
EI_REF = 210e9 * 8e-6  # poutre de référence des tests : E = 210 GPa, Iz = 8e-6 m⁴


def modele(L, positions, types):
    """Poutre acier E = 210 GPa, Iz = 8e-6, Iy = 3e-6, S = 2e-3, ky = kz = 5/6, sans charge (beamModel de MATLAB)."""
    return {
        "L": L,
        "E": 210e9,
        "G": 80e9,
        "S": 2e-3,
        "Iz": 8e-6,
        "Iy": 3e-6,
        "Ix": 1e-6,
        "ky": 5 / 6,
        "kz": 5 / 6,
        "supports": [{"pos": p, "type": t, "name": n} for p, t, n in zip(positions, types, "ABC", strict=False)],
        "pointLoads": [],
        "pointMoments": [],
        "distLoads": [],
    }


def verifier_latex(lignes):
    """Chaînes LaTeX en ASCII et accolades équilibrées (le rendu MathJax n'est pas testé ici)."""
    for ligne in lignes:
        assert ligne.isascii(), ligne
        assert ligne.count("{") == ligne.count("}"), ligne


def verifier_accord(d, fref, tol):
    """Les 4 méthodes donnent la même flèche (flexion seule) que la référence, résidu d'intégration petit."""
    assert d["integration"]["fmax"] == pytest.approx(fref, rel=tol)
    assert d["aires"]["fmax"] == pytest.approx(fref, rel=tol)
    assert d["castigliano"]["fmaxBending"] == pytest.approx(fref, rel=tol)
    assert d["mohr"]["fmax"] == pytest.approx(fref, rel=tol)
    assert d["integration"]["residual"] < 1e-8


def indice_s(d_cast, s):
    """Indice de la première abscisse s0 égale à s (exacte), dans une sortie castigliano."""
    return int(np.flatnonzero(d_cast["s0"] == s)[0])


# ------------------------------------------------------------------ flexion déviée (Iyz ≠ 0)


def test_deflection_iyz():
    # cornière 100×100×10 sur deux appuis, charge selon y : la flèche a une composante w
    L, q, E = 4, 1e4, 210e9
    sec = {"type": "L", "h": 0.1, "b": 0.1, "t": 0.01}
    P = geometry.analytical(sec)
    m = modele(L, [0, L], ["pivot", "appui_simple"])
    m.update(Iz=P["Iz"], Iy=P["Iy"], Iyz=P["Iyz"], S=P["S"])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": -q, "name": "q"}]
    sol = beam_solver.solveBeam(m)
    dv = deflection.deflection(m, sol, {"includeShear": False, "plane": "xy"})
    dw = deflection.deflection(m, sol, {"includeShear": False, "plane": "xz"})
    dt = P["Iz"] * P["Iy"] - P["Iyz"] ** 2
    f0 = 5 * q * L**4 / (384 * E)
    verifier_accord(dv, f0 * P["Iy"] / dt, 1e-6)
    verifier_accord(dw, f0 * abs(P["Iyz"]) / dt, 1e-6)
    b = se.bendingStress({"sec": sec, "Mfz": q * L**2 / 8, "Re": 235e6})
    assert dw["integration"]["fmax"] / dv["integration"]["fmax"] == pytest.approx(
        abs(b["coefs"][2] / b["coefs"][1]), rel=1e-9
    )
    # énergie de flexion : ∫ Mfz²·Iy/(2E·det) ds
    U = deflection.strainEnergy(m, sol)
    assert U["UMfz"] + U["UMfy"] == pytest.approx(q**2 * L**5 / 120 * P["Iy"] / (2 * E * dt), rel=1e-9)


# ------------------------------------------------------------------ flèches de poutres d'école


def test_deflection_simply_supported_point_load():
    L, P = 4, 1e4
    m = modele(L, [0, L], ["appui_simple", "appui_simple"])
    m["pointLoads"] = [{"pos": L / 2, "Fx": 0, "Fy": -P, "Fz": 0, "name": "F"}]
    d = deflection.deflection(m, None)
    fref = P * L**3 / (48 * EI_REF)
    verifier_accord(d, fref, 1e-6)
    assert d["integration"]["sAtFmax"] == pytest.approx(L / 2, abs=1e-9)
    assert d["aires"]["sAtFmax"] == pytest.approx(L / 2, abs=1e-9)
    assert ppEval(d["integration"]["vPP"], L / 2) == pytest.approx(-fref, rel=1e-9)
    assert d["integration"]["alpha"][0] == pytest.approx(-P * L**2 / (16 * EI_REF), rel=1e-9)
    assert d["aires"]["alpha"][0] == pytest.approx(-P * L**2 / (16 * EI_REF), rel=1e-9)
    np.testing.assert_allclose(d["aires"]["v"], d["integration"]["v"], atol=1e-9 * fref)
    assert len(d["integration"]["constants"]) == 2
    assert len(d["comparison"]) == 5
    assert d["plane"] == "xy"
    verifier_latex(d["latex"])
    verifier_latex(d["mohr"]["details"][0]["formulaLatex"].tolist())


def test_deflection_cantilever():
    L, P = 2, 1e3
    m = modele(L, [0], ["encastrement"])
    m["pointLoads"] = [{"pos": L, "Fx": 0, "Fy": -P, "Fz": 0, "name": "F"}]
    d = deflection.deflection(m, None)
    verifier_accord(d, P * L**3 / (3 * EI_REF), 1e-6)
    assert d["integration"]["sAtFmax"] == pytest.approx(L, abs=1e-12)
    # contribution du tranchant : P·L/(ky·G·S)
    c = d["castigliano"]
    iL = indice_s(c, L)
    assert c["vShear"][iL] == pytest.approx(-P * L / (5 / 6 * 80e9 * 2e-3), rel=1e-9)
    assert c["vTotal"][iL] == pytest.approx(c["vBending"][iL] + c["vShear"][iL], rel=1e-12)
    assert c["alpha"][iL] == pytest.approx(-P * L**2 / (2 * EI_REF), rel=1e-9)
    assert c["fmax"] == pytest.approx(P * L**3 / (3 * EI_REF) + P * L / (5 / 6 * 80e9 * 2e-3), rel=1e-9)
    # E I v = P/6 (s³ − 3 L s²) : constantes nulles
    np.testing.assert_allclose(d["integration"]["constants"][["C1", "C2"]].to_numpy(), 0, atol=1e-9)
    # sans tranchant
    d2 = deflection.deflection(m, None, {"includeShear": False, "methods": ["castigliano"]})
    assert np.all(d2["castigliano"]["vShear"] == 0)
    assert "mohr" not in d2


def test_deflection_uniform_simply_supported():
    L, q = 5, 2e4
    m = modele(L, [0, L], ["rotule", "appui_simple"])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": -q, "name": "q"}]
    d = deflection.deflection(m, None)
    verifier_accord(d, 5 * q * L**4 / (384 * EI_REF), 1e-6)
    assert d["mohr"]["details"][0]["tabulated"].all()
    assert d["mohr"]["details"][0]["shapeA"].str.contains("parabole").any()


def test_deflection_clamped_clamped_uniform():
    L, q = 6, 1e4
    m = modele(L, [0, L], ["encastrement", "encastrement"])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": -q, "name": "q"}]
    d = deflection.deflection(m, None)
    verifier_accord(d, q * L**4 / (384 * EI_REF), 1e-6)


def test_deflection_clamped_pinned_uniform():
    L, q = 4, 1.5e4
    m = modele(L, [0, L], ["encastrement", "appui_simple"])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": -q, "name": "q"}]
    d = deflection.deflection(m, None)
    fref = q * L**4 / EI_REF * (39 + 55 * np.sqrt(33)) / 65536
    verifier_accord(d, fref, 1e-6)
    assert d["integration"]["sAtFmax"] == pytest.approx(L * (15 - np.sqrt(33)) / 16, rel=1e-9)


def test_deflection_plane_xz():
    L, P = 3, 2e3
    m = modele(L, [0, L], ["appui_simple", "appui_simple"])
    m["pointLoads"] = [{"pos": L / 2, "Fx": 0, "Fy": 0, "Fz": -P, "name": "F"}]
    d = deflection.deflection(m, None, {"plane": "xz"})
    fref = P * L**3 / (48 * 210e9 * 3e-6)
    verifier_accord(d, fref, 1e-6)
    assert ppEval(d["integration"]["vPP"], L / 2) == pytest.approx(-fref, rel=1e-9)  # w < 0
    v_mi = d["mohr"]["v"][np.abs(d["mohr"]["s0"] - L / 2) < 1e-9]
    np.testing.assert_allclose(v_mi, -fref, rtol=1e-9)
    c = d["castigliano"]
    assert c["alpha"][indice_s(c, 0)] == pytest.approx(d["integration"]["alpha"][0], rel=1e-9)  # dw/ds
    assert d["plane"] == "xz"
    verifier_latex(d["latex"])
    with pytest.raises(MecaStructError) as info:
        deflection.deflection(m, None, {"plane": "yz"})
    assert info.value.identifier == INVALIDE


def test_deflection_linear_load_gauss():
    # charge triangulaire : M cubique, hors table de Mohr (Gauss), mais exact
    L, q0 = 3, 1e4
    m = modele(L, [0, L], ["appui_simple", "appui_simple"])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": [-q0 / L, 0], "name": "q"}]
    d = deflection.deflection(m, None, {"s0": L / 2})
    assert d["mohr"]["v"][0] == pytest.approx(-5 * q0 * L**4 / (768 * EI_REF), rel=1e-9)
    assert not d["mohr"]["details"][0]["tabulated"].all()
    assert d["integration"]["fmax"] == pytest.approx(d["aires"]["fmax"], rel=1e-9)
    assert d["integration"]["fmax"] == pytest.approx(0.00652 * q0 * L**4 / EI_REF, rel=1e-3)


def test_maxwell_betti():
    L, a, b = 5, 1.2, 3.7
    m = modele(L, [0, 3.5], ["rotule", "appui_simple"])
    mA = {**m, "pointLoads": [{"pos": a, "Fx": 0, "Fy": 1, "Fz": 0, "name": "F"}]}
    mB = {**m, "pointLoads": [{"pos": b, "Fx": 0, "Fy": 1, "Fz": 0, "name": "F"}]}
    dA = deflection.deflection(mA, None, {"methods": ["castigliano"], "nCastigliano": 2, "s0": b})
    dB = deflection.deflection(mB, None, {"methods": ["castigliano"], "nCastigliano": 2, "s0": a})
    sBA = dA["castigliano"]["vTotal"][dA["castigliano"]["s0"] == b][0]
    sAB = dB["castigliano"]["vTotal"][dB["castigliano"]["s0"] == a][0]
    assert sBA == pytest.approx(sAB, rel=1e-9)
    assert sBA != 0


# ------------------------------------------------------------------ énergie de déformation


def test_clapeyron_energy():
    L, P = 2, 1e3
    m = modele(L, [0], ["encastrement"])
    m["pointLoads"] = [{"pos": L, "Fx": 0, "Fy": -P, "Fz": 0, "name": "F"}]
    sol = beam_solver.solveBeam(m)
    U = deflection.strainEnergy(m, sol)
    d = deflection.deflection(m, sol, {"methods": ["castigliano"], "s0": L})
    c = d["castigliano"]
    iL = indice_s(c, L)
    assert U["UMfz"] == pytest.approx(0.5 * P * abs(c["vBending"][iL]), rel=1e-9)
    assert U["total"] == pytest.approx(0.5 * P * abs(c["vTotal"][iL]), rel=1e-9)
    assert U["UTy"] == pytest.approx(P**2 * L / (2 * 5 / 6 * 80e9 * 2e-3), rel=1e-12)
    assert [U["UN"], U["UTz"], U["UMt"], U["UMfy"]] == pytest.approx([0, 0, 0, 0], abs=1e-15)
    verifier_latex(U["latex"])


def test_strain_energy_all_terms():
    L, F, C, Pz = 1.5, 2e4, 300, 500
    m = modele(L, [0], ["encastrement"])
    m["pointLoads"] = [{"pos": L, "Fx": F, "Fy": 0, "Fz": Pz, "name": "F"}]
    m["pointMoments"] = [{"pos": L, "Mx": C, "My": 0, "Mz": 0, "name": "C"}]
    sol = beam_solver.solveBeam(m)
    U = deflection.strainEnergy(m, sol)
    assert U["UN"] == pytest.approx(F**2 * L / (2 * 210e9 * 2e-3), rel=1e-12)
    assert U["UMt"] == pytest.approx(C**2 * L / (2 * 80e9 * 1e-6), rel=1e-12)
    assert U["UTz"] == pytest.approx(Pz**2 * L / (2 * 5 / 6 * 80e9 * 2e-3), rel=1e-12)
    assert U["UMfy"] == pytest.approx(Pz**2 * L**3 / (6 * 210e9 * 3e-6), rel=1e-12)
    # propriétés du modèle prioritaires
    U2 = deflection.strainEnergy({**m, "E": 105e9}, sol)
    assert U2["UN"] == pytest.approx(2 * U["UN"], rel=1e-12)


# ------------------------------------------------------------------ intégrales de Mohr


def test_mohr_integral_table():
    # trapèze × parabole + triangles sur deux tronçons
    A = {"breaks": [0, 1, 3], "coefs": [[2, 1], [-1, 5, -2]]}
    B = {"breaks": [0, 2, 3], "coefs": [[1, 0], [-2, 6]]}
    M = deflection.mohrIntegral(A, B, 0, 3)
    ex = sum(
        quad(lambda s: ppEval(A, s) * ppEval(B, s), lo, hi, epsabs=0, epsrel=1e-13)[0]
        for lo, hi in ((0, 1), (1, 2), (2, 3))
    )
    assert M["value"] == pytest.approx(ex, rel=1e-10)
    assert M["valueTable"] == pytest.approx(M["value"], rel=1e-12)
    assert M["allTabulated"]
    assert len(M["segments"]) == 3
    assert M["segments"]["value"].sum() == pytest.approx(M["valueTable"], rel=1e-14)
    verifier_latex(M["segments"]["formulaLatex"].tolist())
    verifier_latex(M["latex"])
    # formes élémentaires : triangle × triangle de même sens = l·a·b/3
    T1 = {"breaks": [0, 2], "coefs": [[3, 0]]}
    M2 = deflection.mohrIntegral(T1, T1)  # bornes par défaut
    assert M2["valueTable"] == pytest.approx(2 * 6 * 6 / 3, rel=1e-12)
    assert M2["segments"]["shapeA"][0] == "triangle"
    # hors table : degré 3 → Gauss exact
    C3 = {"breaks": [0, 1], "coefs": [[1, 0, 0, 1]]}
    M3 = deflection.mohrIntegral(C3, T1, 0, 1)
    assert not M3["allTabulated"]
    assert M3["valueTable"] == pytest.approx(M3["value"], rel=1e-12)
    assert M3["value"] == pytest.approx(3 * (1 / 5 + 1 / 2), rel=1e-12)
    with pytest.raises(MecaStructError) as info:
        deflection.mohrIntegral(T1, T1, 1, 1)
    assert info.value.identifier == INVALIDE


# ------------------------------------------------------------------ cas README et golden files


def test_readme_ipe200():
    # flèche max 9,029 mm par les 4 méthodes, égale à 5qL⁴/(384 E Iz)
    m = get_case(GOLDEN_BEAM, "readme_IPE200_deflection")["entrees"]["modele"]
    q, L = 1e4, m["L"]
    fref = 5 * q * L**4 / (384 * m["E"] * m["Iz"])
    d = deflection.deflection(m, None, {"includeShear": False})
    assert len(d["comparison"]) == 4
    assert np.abs(d["comparison"]["fmax_m"].to_numpy()) == pytest.approx(9.029e-3, rel=1e-3)
    assert d["integration"]["fmax"] == pytest.approx(fref, rel=1e-9)


# Exceptions des cas golden de flèche, accordées par Théo et limitées à ce test (golden et autres tolérances inchangés).
# 1. Égalités de maxima : appui_elastique (|v| égal en s et en L − s : le maximum choisi par numpy diffère de celui de
#    MATLAB) et thermique_bi_encastree (flèche nulle en exact : le maximum est décidé par le bruit d'arrondi).
#    Pour ces deux cas, l'abscisse diffère seulement si la flèche de Python à cette abscisse égale l'extremum golden.
# 2. Valeurs nulles en exact : C1, C2 et aires.Aire sont comparés à abs max(1e-12, 1e-12 × échelle de la sortie) ;
#    Ecart_pct à abs 1e-9 (verifier_valeurs_nulles).
# 3. appui_elastique seul : castigliano et mohr sont vérifiés par verifier_blocs_symetriques, pas terme à terme.
CAS_EGALITES_MAXIMA = ("appui_elastique_deflection", "thermique_bi_encastree_deflection")
CAS_BLOCS_SYMETRIQUES = ("appui_elastique_deflection",)


def _valeurs_numeriques(x) -> list[float]:
    """Valeurs absolues finies de toutes les valeurs numériques d'une sortie golden (échelle du cas)."""
    if isinstance(x, dict):
        return [v for y in x.values() for v in _valeurs_numeriques(y)]
    if isinstance(x, list):
        return [v for y in x for v in _valeurs_numeriques(y)]
    if isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x):
        return [abs(x)]
    return []


def verifier_egalites_maxima(cas, d, g, L):
    """Égalités de maxima (cas listés) : si l'abscisse de Python diffère de celle du golden, la flèche de Python à cette
    abscisse, lue dans la méthode elle-même, doit égaler l'extremum du golden à rel 1e-7 ; si toutes les flèches sont
    nulles, à 1e-9 × l'échelle du cas. Les abscisses acceptées sont recopiées dans g pour la comparaison qui suit."""
    echelle = max(_valeurs_numeriques(g))
    # toutes les flèches sont nulles si leur plus grande valeur est au niveau du bruit (1e-9 × l'échelle du cas)
    champs_fleche = (("integration", "v"), ("castigliano", "vTotal"), ("mohr", "v"))
    fleche_max = max(max(_valeurs_numeriques(g[b][c])) for b, c in champs_fleche)
    nulle = fleche_max <= 1e-9 * echelle
    vPP = d["integration"]["vPP"]
    methodes = {  # libellé de comparison -> (bloc, champ de la flèche)
        "Intégration": ("integration", None),
        "Aires": ("aires", None),
        "Castigliano (flexion)": ("castigliano", "vBending"),
        "Castigliano (flexion + tranchant)": ("castigliano", "vTotal"),
        "Mohr (tabulé)": ("mohr", None),
    }

    def valeur(bloc, champ, s):
        """|flèche| de la méthode `bloc` à l'abscisse s de Python, lue dans cette méthode."""
        if bloc in ("integration", "aires"):
            return abs(ppEval(vPP, s))
        if bloc == "mohr":
            return abs(d["mohr"]["v"][np.argmin(np.abs(d["mohr"]["s0"] - s))])
        return abs(d["castigliano"][champ][np.argmin(np.abs(d["castigliano"]["s0"] - s))])

    def controle(s_py, s_g, f_g, valeur_py):
        if abs(s_py - s_g) <= 1e-7 * abs(s_g) + 1e-12:  # même abscisse : comparaison habituelle
            return s_py
        tol = 1e-9 * echelle if nulle else 1e-7 * abs(f_g)
        ecart = abs(valeur_py - abs(f_g))
        assert ecart <= tol, f"abscisse {s_py} : écart {ecart:.3e} à l'extremum golden {f_g:.3e} (tolérance {tol:.3e})"
        return s_py

    for bloc, champ_s, champ_f, champ_v in (
        ("integration", "sAtFmax", "fmax", None),
        ("aires", "sAtFmax", "fmax", None),
        ("castigliano", "sAtFmax", "fmax", "vTotal"),
        ("castigliano", "sAtFmaxBending", "fmaxBending", "vBending"),
        ("mohr", "sAtFmax", "fmax", None),
    ):
        s = d[bloc][champ_s]
        g[bloc][champ_s] = controle(s, g[bloc][champ_s], g[bloc][champ_f], valeur(bloc, champ_v, s))
    for k, ligne in enumerate(g["comparison"]):
        s = float(d["comparison"]["s_m"].iloc[k])
        bloc, champ_v = methodes[ligne["Methode"]]
        ligne["s_m"] = controle(s, ligne["s_m"], ligne["fmax_m"], valeur(bloc, champ_v, s))


def _apparier(s_py, s_g, L):
    """Indice golden de chaque abscisse de Python : même abscisse, sinon symétrique L − s (tolérance 1e-9 × L).

    Les abscisses de MATLAB et de numpy diffèrent d'un ulp ; le symétrique sert pour le point du maximum choisi dans
    appui_elastique. Erreur : AssertionError si un point n'a pas de partenaire ou si l'appariement n'est pas bijectif.
    """
    tol = 1e-9 * L
    indices = []
    for s in s_py:
        direct = np.flatnonzero(np.abs(s_g - s) <= tol)
        if direct.size:
            indices.append(int(direct[0]))
            continue
        miroir = np.flatnonzero(np.abs(s_g - (L - s)) <= tol)
        assert miroir.size == 1, f"abscisse {s} de Python sans partenaire dans le golden (ni direct, ni symétrique)"
        indices.append(int(miroir[0]))
    assert len(set(indices)) == len(indices) == len(s_g), "appariement des abscisses non bijectif"
    return indices


def verifier_blocs_symetriques(d, g, L):
    """appui_elastique : castigliano et mohr sont échantillonnés autour de s0, donc le point symétrique du maximum
    décale leurs tableaux. Au lieu de la comparaison terme à terme de ces deux blocs, trois vérifications :
    1. max|vTotal| et max|vBending| (castigliano), max|v| (mohr) égalent ceux du golden à rel 1e-7 ;
    2. à chacun de ses s0, la flèche de Python égale celle du golden au même point, ou à son symétrique L − s ;
    3. mohr.s0 est, élément par élément, l'abscisse du golden ou son symétrique par rapport à L/2 (1e-9 × L).
    Les autres champs de castigliano (alpha, vShear) et le détail de Mohr ne sont pas comparés dans ce cas.
    """

    def max_abs(valeurs):
        return float(np.max(np.abs(np.asarray(valeurs, dtype=float))))

    for champ in ("vTotal", "vBending"):
        assert max_abs(d["castigliano"][champ]) == pytest.approx(
            max_abs(g["castigliano"][champ]), rel=1e-7, abs=1e-12
        ), f"castigliano.{champ} : max|.| différent"
    assert max_abs(d["mohr"]["v"]) == pytest.approx(max_abs(g["mohr"]["v"]), rel=1e-7, abs=1e-12), "mohr.v : max|.|"
    for bloc, champs in (("castigliano", ("vTotal", "vBending")), ("mohr", ("v",))):
        ind = _apparier(np.asarray(d[bloc]["s0"]), np.asarray(g[bloc]["s0"]), L)
        for champ in champs:
            np.testing.assert_allclose(
                np.asarray(d[bloc][champ]),
                np.asarray(g[bloc][champ], dtype=float)[ind],
                rtol=1e-7,
                atol=1e-12,
                err_msg=f"{bloc}.{champ} (aux s0 de Python)",
            )
    s_py, s_g = np.asarray(d["mohr"]["s0"]), np.asarray(g["mohr"]["s0"], dtype=float)
    assert s_py.shape == s_g.shape, "mohr.s0 : longueur différente"
    tol = 1e-9 * L
    directes = np.abs(s_py - s_g) <= tol
    symetriques = np.abs(s_py - (L - s_g)) <= tol
    assert np.all(directes | symetriques), "mohr.s0 : abscisses non symétriques"


def verifier_valeurs_nulles(d, g):
    """Valeurs nulles en exact, comparées au bruit d'arrondi : C1, C2 et aires.Aire à rel 1e-7 et
    abs max(1e-12, 1e-12 × la plus grande valeur absolue de toute la sortie golden du cas, abscisses comprises) ;
    Ecart_pct (en %) à rel 1e-7 et abs 1e-9. Le plancher 1e-12 garde les cas qui passaient déjà."""
    echelle = max(_valeurs_numeriques(g))
    attendu = np.array([[r["C1"], r["C2"]] for r in g["integration"]["constants"]], dtype=float)
    obtenu = d["integration"]["constants"][["C1", "C2"]].to_numpy(dtype=float)
    for k, nom in enumerate(("C1", "C2")):
        np.testing.assert_allclose(
            obtenu[:, k],
            attendu[:, k],
            rtol=1e-7,
            atol=max(1e-12, 1e-12 * echelle),
            err_msg=f"integration.constants.{nom}",
        )
    aire = np.array([r["Aire"] for r in g["aires"]["areas"]], dtype=float)
    np.testing.assert_allclose(
        d["aires"]["areas"]["Aire"].to_numpy(),
        aire,
        rtol=1e-7,
        atol=max(1e-12, 1e-12 * echelle),
        err_msg="aires.Aire",
    )
    ecart = np.array([r["Ecart_pct"] for r in g["comparison"]], dtype=float)
    np.testing.assert_allclose(
        d["comparison"]["Ecart_pct"].to_numpy(), ecart, rtol=1e-7, atol=1e-9, err_msg="comparison.Ecart_pct"
    )


@pytest.mark.parametrize("cas", case_ids(GOLDEN_BEAM, suffix="_deflection"))
def test_golden_deflection(cas):
    c = get_case(GOLDEN_BEAM, cas)
    e = c["entrees"]
    m = e["modele"]
    sol = beam_solver.solveBeam(m)
    d = deflection.deflection(m, sol, e["opts"])
    g = copy.deepcopy(c["sortie"])
    if cas in CAS_EGALITES_MAXIMA:
        verifier_egalites_maxima(cas, d, g, m["L"])
    verifier_valeurs_nulles(d, g)
    if cas in CAS_BLOCS_SYMETRIQUES:
        verifier_blocs_symetriques(d, g, m["L"])
        blocs = ("castigliano", "mohr")  # remplacés par verifier_blocs_symetriques
        d = {k: v for k, v in d.items() if k not in blocs}
        g = {k: v for k, v in g.items() if k not in blocs}
    ignore = {"constants", "Aire", "Ecart_pct"}  # contrôlées par verifier_valeurs_nulles
    if cas == "thermique_bi_encastree_deflection":
        ignore.add("formulaLatex")  # segment Mohr dont la formule contient du bruit d'arrondi (~1e-13)
    assert_matches(d, g, rel=1e-7, abs_=1e-12, ignore=ignore)


@pytest.mark.parametrize("cas", case_ids(GOLDEN_BEAM, suffix="_strainEnergy"))
def test_golden_strain_energy(cas):
    c = get_case(GOLDEN_BEAM, cas)
    m = c["entrees"]
    sol = beam_solver.solveBeam(m)
    assert_matches(deflection.strainEnergy(m, sol), c["sortie"], rel=1e-9)


def test_golden_mohr_integral():
    c = get_case(GOLDEN_SOL, "mohrIntegral_triangle_parabole")
    e = c["entrees"]
    assert_matches(deflection.mohrIntegral(e["ppA"], e["ppB"], e["a"], e["b"]), c["sortie"], rel=1e-9)
