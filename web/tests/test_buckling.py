"""Tests de buckling (étape E14) : flambage d'Euler, Rankine et compression, courbe de stabilité, modes propres.

Portage de tests/test_BucklingEngine.m, sauf les tests du chemin symbolique (dsolve, vpasolve) non portés : methodUsed
vaut toujours 'numérique'. Portage aussi de testBucklingDelegation (tests/test_SolicitationsEngine.m) et des golden
files (golden_buckling.json). Le rendu LaTeX n'est pas testé : délimiteurs $, ASCII, longueur et commandes interdites.
"""

import math

import numpy as np
import pytest
from scipy.optimize import brentq, minimize_scalar

from mecastruct.core import buckling
from mecastruct.core import solicitations as se
from mecastruct.core.errors import MecaStructError
from tests.golden_tools import assert_matches, case_ids, get_case

GOLDEN = "golden_buckling.json"
# sorties propres au chemin symbolique de MATLAB (dsolve, vpasolve), non portées : voir la fiche E14
SYMBOLIQUE = {"symbolic", "determinant"}
CONDITIONS = ["encastre-libre", "articule-articule", "encastre-articule", "encastre-encastre"]
PREFIXE = "MecaStruct:BucklingEngine:"
BASE = {"E": 210e9, "Re": 235e6, "S": 1e-3, "Iz": 2e-6, "Iy": 5e-7, "L": 3.0, "s": 1}


def base(condition="articule-articule", **modif):
    """Section rectangulaire fictive : S = 1e-3 m², Iz = 2e-6 m⁴, Iy = 5e-7 m⁴ (baseParams de MATLAB)."""
    return {**BASE, "condition": condition, **modif}


def erreur(identifiant, appel):
    """Vérifie que l'appel lève une MecaStructError d'identifiant donné."""
    with pytest.raises(MecaStructError) as info:
        appel()
    assert info.value.identifier == identifiant


def verifier_latex(chaines):
    """Chaînes LaTeX entre $, ASCII, moins de 1000 caractères, sans commande interdite (le rendu n'est pas testé)."""
    interdit = [
        "\\iint", "\\iiint", "\\implies", "\\text{", "\\dfrac", "\\tfrac", "\\boldsymbol",
        "\\geqslant", "\\leqslant", "pmatrix", "bmatrix", "{align", "{cases",
    ]  # fmt: skip
    for s in chaines:
        assert s.startswith("$") and s.endswith("$"), s
        assert len(s) < 1000, s
        assert s.isascii(), s
        for commande in interdit:
            assert commande not in s, s


# ----------------------------------------------------------------- régimes


def test_euler_barre_ronde():
    # barre ronde pleine D = 20 mm, L = 2 m, articulée-articulée : PE = π³ E D⁴/(64 L²) ≈ 4069,57 N
    D, L, E, Re = 0.02, 2.0, 210e9, 235e6
    S = math.pi * D**2 / 4
    I = math.pi * D**4 / 64
    r = buckling.analyze({"E": E, "Re": Re, "S": S, "Iz": I, "Iy": I, "L": L, "condition": "articule-articule"})
    assert r["regime"] == "euler"
    assert r["rmin"] == pytest.approx(D / 4, rel=1e-12)
    assert r["Lp"] == pytest.approx(L, rel=1e-15)
    assert r["lambda"] == pytest.approx(400, rel=1e-12)
    assert r["lambdaLim"] == pytest.approx(math.pi * math.sqrt(E / Re), rel=1e-14)
    assert r["lambdaLim"] == pytest.approx(93.913, rel=1e-5)
    assert r["PE"] == pytest.approx(math.pi**3 * E * D**4 / (64 * L**2), rel=1e-12)
    assert r["PE"] == pytest.approx(4069.5738, rel=1e-6)
    assert r["sigmaE"] == pytest.approx(math.pi**2 * E / 400**2, rel=1e-12)
    assert r["sigmaE"] == pytest.approx(12.95386e6, rel=1e-6)
    assert r["sigmaE"] * S == pytest.approx(r["PE"], rel=1e-12)
    assert r["Pcrit"] == r["PE"]
    assert r["Padm"] == pytest.approx(r["PE"], rel=1e-15)
    assert r["s"] == 1
    assert r["PC"] == pytest.approx(Re * S, rel=1e-15)
    assert r["PE"] < r["PC"]
    assert r["sigmaCrit"] == pytest.approx(r["Pcrit"] / S, rel=1e-15)
    assert r["ok"] is None
    assert math.isnan(r["sigmaApplied"])


def test_euler_ipe200():
    # IPE 200 : flambage autour de l'axe faible (G, y), articulée-articulée L = 5 m, s = 3
    p = {
        "E": 210e9,
        "Re": 235e6,
        "S": 28.48e-4,
        "Iz": 1943e-8,
        "Iy": 142.4e-8,
        "L": 5,
        "condition": "articule-articule",
    }
    r = buckling.analyze({**p, "s": 3})
    assert r["axis"] == "y"
    assert r["Imin"] == 142.4e-8
    assert r["Imax"] == 1943e-8
    assert r["rmin"] == pytest.approx(math.sqrt(142.4e-8 / 28.48e-4), rel=1e-14)
    assert r["lambda"] == pytest.approx(5 / math.sqrt(142.4e-8 / 28.48e-4), rel=1e-12)
    assert r["regime"] == "euler"
    PE = math.pi**2 * 210e9 * 142.4e-8 / 5**2
    assert r["PE"] == pytest.approx(PE, rel=1e-12)
    assert r["PE"] == pytest.approx(118056.26, rel=1e-6)
    assert r["Padm"] == pytest.approx(PE / 3, rel=1e-12)


def test_rankine():
    # encastrée-encastrée L = 3 m : L' = 1,5 m, λ ≈ 67,08 ∈ [20 ; 93,91[ ⇒ Rankine
    r = buckling.analyze(base("encastre-encastre", s=2))
    lam = 1.5 / math.sqrt(5e-4)
    lamLim = math.pi * math.sqrt(210e9 / 235e6)
    PR = 235e6 * 1e-3 / (1 + (lam / lamLim) ** 2)
    assert r["regime"] == "rankine"
    assert r["Lp"] == pytest.approx(1.5, rel=1e-15)
    assert r["lambda"] == pytest.approx(lam, rel=1e-12)
    assert r["PR"] == pytest.approx(PR, rel=1e-12)
    assert r["PR"] == pytest.approx(155606, rel=1e-5)
    assert r["Pcrit"] == r["PR"]
    assert r["Padm"] == pytest.approx(PR / 2, rel=1e-12)
    assert r["sigmaAdm"] == pytest.approx(PR / 2 / 1e-3, rel=1e-12)
    assert r["PE"] == pytest.approx(math.pi**2 * 210e9 * 5e-7 / 1.5**2, rel=1e-12)
    assert r["PC"] == pytest.approx(235e3, rel=1e-15)
    assert r["PR"] < r["PC"]
    assert r["sigmaE"] > 235e6


def test_compression_simple():
    # poutre courte articulée L = 0,2 m : λ ≈ 8,94 < 20 ⇒ compression simple PC = Re S
    r = buckling.analyze(base(L=0.2))
    assert r["regime"] == "compression"
    assert r["lambda"] == pytest.approx(0.2 / math.sqrt(5e-4), rel=1e-12)
    assert r["lambda"] < 20
    assert r["Pcrit"] == pytest.approx(235e6 * 1e-3, rel=1e-15)
    assert r["Pcrit"] == r["PC"]
    assert r["sigmaCrit"] == pytest.approx(235e6, rel=1e-15)
    assert r["sigmaE"] > r["Re"]
    assert r["PE"] == pytest.approx(math.pi**2 * 210e9 * 5e-7 / 0.2**2, rel=1e-12)
    assert r["PR"] == pytest.approx(r["PC"] / (1 + (r["lambda"] / r["lambdaLim"]) ** 2), rel=1e-12)


def test_frontieres_de_l_arbre_de_decision():
    # λ = λC → Rankine (inégalité large) ; λ juste sous λC → compression ; λ = λlim (1 ± 1e-9) → Euler / Rankine
    p = base(L=1.5)
    r0 = buckling.analyze(p)
    assert r0["regime"] == "rankine"
    assert buckling.analyze({**p, "lambdaCompression": r0["lambda"]})["regime"] == "rankine"
    assert buckling.analyze({**p, "lambdaCompression": r0["lambda"] * (1 + 1e-12)})["regime"] == "compression"
    lamLim = r0["lambdaLim"]
    assert buckling.analyze({**p, "L": lamLim * (1 + 1e-9) * r0["rmin"]})["regime"] == "euler"
    r3 = buckling.analyze({**p, "L": lamLim * (1 - 1e-9) * r0["rmin"]})
    assert r3["regime"] == "rankine"
    # à λ = λlim : PE = PC et PR = PC/2 (discontinuité de la courbe du cours)
    assert r3["PE"] == pytest.approx(r3["PC"], rel=1e-8)
    assert r3["PR"] == pytest.approx(r3["PC"] / 2, rel=1e-8)
    assert r0["lambdaCompression"] == 20


def test_lambda_lim_sous_la_limite_de_compression():
    # E/Re = 30 ⇒ λlim = π√30 ≈ 17,2 < 20 : Euler est retenu pour λ = 18 (zone de Rankine vide)
    E, Re = 3e9, 100e6
    p = {"E": E, "Re": Re, "S": 1e-4, "Iz": 1e-8, "Iy": 1e-8, "L": 18 * 1e-2, "condition": "articule-articule"}
    r = buckling.analyze(p)
    assert r["lambdaLim"] == pytest.approx(math.pi * math.sqrt(30), rel=1e-14)
    assert r["lambda"] == pytest.approx(18, rel=1e-12)
    assert r["regime"] == "euler"
    assert r["sigmaE"] <= Re
    assert any("Cas particulier" in ligne for ligne in r["report"])
    c = buckling.stabilityCurve(E, Re)
    assert not np.any(c["zone"] == 2)
    assert np.all(c["zone"][c["lambda"] >= c["lambdaLim"]] == 3)


@pytest.mark.parametrize("cond", CONDITIONS)
def test_identite_de_rankine(cond):
    # 1/PR = 1/PE + 1/PC quel que soit le cas (quatre conditions, six longueurs)
    for L in [0.05, 0.3, 1, 2.5, 6, 15]:
        r = buckling.analyze(base(cond, L=L))
        assert 1 / r["PR"] == pytest.approx(1 / r["PE"] + 1 / r["PC"], rel=1e-12)
        assert r["PR"] < min(r["PE"], r["PC"])
        assert r["PE"] == pytest.approx(r["sigmaE"] * r["S"], rel=1e-12)
        assert r["PE"] == pytest.approx(r["PC"] * (r["lambdaLim"] / r["lambda"]) ** 2, rel=1e-12)
        if r["lambda"] >= r["lambdaLim"]:
            assert r["regime"] == "euler"
            assert r["Pcrit"] == r["PE"]
        elif r["lambda"] < 20:
            assert r["regime"] == "compression"
            assert r["Pcrit"] == r["PC"]
        else:
            assert r["regime"] == "rankine"
            assert r["Pcrit"] == r["PR"]


# ----------------------------------------------------------------- longueur de flambage, plan, alias


def test_coefficients_de_longueur_de_flambage():
    expected = [2, 1, 1 / math.sqrt(2), 0.5]
    for cond, coef in zip(CONDITIONS, expected, strict=True):
        assert buckling.effectiveLengthCoefficient(cond) == pytest.approx(coef, rel=1e-15)
        r = buckling.analyze(base(cond, L=2.7))
        assert r["coefLp"] == pytest.approx(coef, rel=1e-15)
        assert r["Lp"] == pytest.approx(coef * 2.7, rel=1e-15)
        assert r["lambda"] == pytest.approx(coef * 2.7 / math.sqrt(5e-4), rel=1e-12)
        assert r["PE"] == pytest.approx(math.pi**2 * 210e9 * 5e-7 / (coef * 2.7) ** 2, rel=1e-12)
        assert r["condition"] == cond
    # rapports de charges critiques d'Euler : 1/4, 1, 2, 4 fois le cas articulé
    PEref = buckling.analyze(base("articule-articule", L=10))["PE"]
    for cond, ratio in zip(CONDITIONS, [0.25, 1, 2, 4], strict=True):
        assert buckling.analyze(base(cond, L=10))["PE"] / PEref == pytest.approx(ratio, rel=1e-12)
    table = buckling.listConditions()
    assert [ligne["Condition"] for ligne in table] == CONDITIONS
    assert [ligne["Coefficient"] for ligne in table] == pytest.approx(expected, rel=1e-15)


def test_alias_des_conditions():
    assert buckling.analyze(base("Encastré-Libre"))["condition"] == "encastre-libre"
    assert buckling.analyze(base("articule_articule"))["condition"] == "articule-articule"
    assert buckling.analyze(base("Encastré articulé"))["condition"] == "encastre-articule"
    assert buckling.analyze(base("bi-encastre"))["condition"] == "encastre-encastre"
    assert buckling.effectiveLengthCoefficient("ENCASTRE-ENCASTRE") == 0.5


def test_choix_de_l_axe_faible():
    # Iy < Iz : flambage autour de (G, y), plan (x, z)
    r = buckling.analyze(base())
    assert r["axis"] == "y"
    assert r["Imin"] == 5e-7
    assert r["Imax"] == 2e-6
    assert "(x, z)" in r["planeText"]
    assert r["rmin"] == pytest.approx(math.sqrt(5e-7 / 1e-3), rel=1e-15)
    # Iz < Iy : flambage autour de (G, z), plan (x, y)
    r = buckling.analyze(base(Iz=3e-7, Iy=8e-7))
    assert r["axis"] == "z"
    assert r["Imin"] == 3e-7
    assert r["Imax"] == 8e-7
    assert "(x, y)" in r["planeText"]
    assert r["PE"] == pytest.approx(math.pi**2 * 210e9 * 3e-7 / 3**2, rel=1e-12)
    # Iz = Iy : convention axe z, Imin = Imax
    r = buckling.analyze(base(Iz=4e-7, Iy=4e-7))
    assert r["axis"] == "z"
    assert r["Imin"] == r["Imax"]
    assert "équivalentes" in r["planeText"]


# ----------------------------------------------------------------- effort appliqué, coefficient de sécurité


def test_verification_d_un_effort_applique():
    Padm = buckling.analyze(base(s=2))["PE"] / 2
    r = buckling.analyze(base(s=2, P=0.9 * Padm))
    assert r["ok"] is True
    assert r["P"] == 0.9 * Padm
    assert r["sigmaApplied"] == pytest.approx(0.9 * Padm / 1e-3, rel=1e-15)
    assert r["safetyObtained"] == pytest.approx(r["Pcrit"] / (0.9 * Padm), rel=1e-14)
    assert r["utilization"] == pytest.approx(0.9, rel=1e-12)
    assert any("VÉRIFIÉ" in ligne for ligne in r["report"])
    r = buckling.analyze(base(s=2, P=1.1 * Padm))
    assert r["ok"] is False
    assert any("NON VÉRIFIÉ" in ligne for ligne in r["report"])
    # effort négatif (convention N < 0 en compression) : |P| retenu
    r = buckling.analyze(base(s=2, P=-0.5 * Padm))
    assert r["ok"] is True
    assert r["P"] == pytest.approx(0.5 * Padm, rel=1e-15)
    assert any("|P| retenu" in ligne for ligne in r["report"])
    # égalité : P = Padm vérifié
    assert buckling.analyze(base(s=2, P=Padm))["ok"] is True


def test_alerte_pres_du_seuil_lambda_lim():
    """Autour de λlim (±10 %), Pcrit saute de Re·S/2 à Re·S : alerte dans le rapport, valeurs inchangées."""
    lambdaLim = math.pi * math.sqrt(210e9 / 235e6)
    rmin = math.sqrt(5e-7 / 1e-3)
    juste_avant = buckling.analyze(base(L=0.999 * lambdaLim * rmin))
    au_seuil = buckling.analyze(base(L=lambdaLim * rmin))
    assert juste_avant["regime"] == "rankine" and au_seuil["regime"] == "euler"
    assert au_seuil["Pcrit"] / juste_avant["Pcrit"] == pytest.approx(2, rel=1e-2)
    for r in (juste_avant, au_seuil):
        assert any("ATTENTION" in ligne and "λlim" in ligne for ligne in r["report"])
    loin = buckling.analyze(base(L=1.5 * lambdaLim * rmin))
    assert not any("ATTENTION" in ligne for ligne in loin["report"])
    assert buckling.alerteSeuilLambdaLim(1.09 * lambdaLim, lambdaLim)
    assert not buckling.alerteSeuilLambdaLim(1.11 * lambdaLim, lambdaLim)


def test_effort_absent_nul_ou_vide():
    for P in [math.nan, []]:
        r = buckling.analyze(base(P=P))
        assert r["ok"] is None
        assert math.isnan(r["P"])
    r = buckling.analyze(base(P=0))
    assert r["ok"] is True
    assert r["safetyObtained"] == math.inf


def test_coefficient_de_securite():
    for cond in CONDITIONS:
        r1 = buckling.analyze(base(cond))
        r2 = buckling.analyze(base(cond, s=2.5))
        assert r2["Pcrit"] == r1["Pcrit"]
        assert r2["Padm"] == pytest.approx(r1["Pcrit"] / 2.5, rel=1e-15)
        assert r2["s"] == 2.5


# ----------------------------------------------------------------- modes propres


def test_formes_de_mode_conformes_au_contrat():
    L = 2.4
    s = np.linspace(0, L, 2001)
    kLca = brentq(lambda x: math.tan(x) - x, 4.4, 4.6)
    contrat = [
        lambda x: 1 - np.cos(math.pi * x / (2 * L)),
        lambda x: np.sin(math.pi * x / L),
        lambda x: np.sin(kLca * x / L) - kLca * x / L + kLca * (1 - np.cos(kLca * x / L)),
        lambda x: (1 - np.cos(2 * math.pi * x / L)) / 2,
    ]
    for i, cond in enumerate(CONDITIONS):
        r = buckling.analyze(base(cond, L=L))
        v = r["modeShape"](s)
        assert v.shape == s.shape
        ve = contrat[i](s)
        if cond == "encastre-articule":
            # normalisation au maximum de la forme du contrat (non normalisée), abscisse du maximum
            f = contrat[2]
            im = int(np.argmax(ve))
            res = minimize_scalar(
                lambda x: -f(x),
                bounds=(s[max(im - 1, 0)], s[min(im + 1, s.size - 1)]),
                method="bounded",
                options={"xatol": 1e-14},
            )
            ve = ve / f(res.x)
            assert r["modeSMax"] == pytest.approx(res.x, rel=1e-6)
            assert r["modeK"] * L == pytest.approx(4.493409457909064, rel=1e-12)
        np.testing.assert_allclose(v, ve, rtol=0, atol=1e-9)
        assert max(v) == pytest.approx(1, abs=1e-5)
        assert max(v) <= 1 + 1e-12
        assert r["modeShape"](r["modeSMax"]) == pytest.approx(1, abs=1e-12)
        assert min(v) >= -1e-12


@pytest.mark.parametrize("cond", CONDITIONS)
def test_conditions_limites_et_equation_du_mode(cond):
    # contrôle indépendant par différences finies, puis modeCheck
    L = 3.0
    r = buckling.analyze(base(cond, L=L))
    v, k, d = r["modeShape"], r["modeK"], r["modeDerivatives"]
    h = 1e-5 * L
    d1_0 = (-3 * v(0) + 4 * v(h) - v(2 * h)) / (2 * h)
    d1_L = (3 * v(L) - 4 * v(L - h) + v(L - 2 * h)) / (2 * h)
    assert v(0) == pytest.approx(0, abs=1e-12)
    if cond == "encastre-libre":
        assert d1_0 / k == pytest.approx(0, abs=1e-8)
        assert d["d2"](L) / k**2 == pytest.approx(0, abs=1e-12)
        assert (d["d3"](L) + k**2 * d["d1"](L)) / k**3 == pytest.approx(0, abs=1e-12)
        assert k * L == pytest.approx(math.pi / 2, rel=1e-14)
    elif cond == "articule-articule":
        assert v(L) == pytest.approx(0, abs=1e-12)
        assert d["d2"](0) / k**2 == pytest.approx(0, abs=1e-12)
        assert d["d2"](L) / k**2 == pytest.approx(0, abs=1e-12)
        assert k * L == pytest.approx(math.pi, rel=1e-14)
    elif cond == "encastre-articule":
        assert d1_0 / k == pytest.approx(0, abs=1e-8)
        assert v(L) == pytest.approx(0, abs=1e-12)
        assert d["d2"](L) / k**2 == pytest.approx(0, abs=1e-12)
    else:
        assert d1_0 / k == pytest.approx(0, abs=1e-8)
        assert v(L) == pytest.approx(0, abs=1e-12)
        assert d1_L / k == pytest.approx(0, abs=1e-8)
        assert k * L == pytest.approx(2 * math.pi, rel=1e-14)
    # équation v'''' + k² v'' = 0 par différences finies (points intérieurs)
    hh = 3e-3 * L
    si = np.linspace(0.1 * L, 0.9 * L, 41)
    fd2 = (v(si + hh) - 2 * v(si) + v(si - hh)) / hh**2
    fd4 = (v(si + 2 * hh) - 4 * v(si + hh) + 6 * v(si) - 4 * v(si - hh) + v(si - 2 * hh)) / hh**4
    assert np.max(np.abs(fd4 + k**2 * fd2)) / k**4 < 1e-3
    np.testing.assert_allclose(d["d2"](si), fd2, rtol=0, atol=1e-4 * k**2)
    mc = r["modeCheck"]
    assert mc["ok"] is True
    assert max(abs(x) for x in mc["bcResiduals"]) < 1e-12
    assert mc["odeResidual"] < 1e-12
    assert len(mc["bcLabels"]) == 4


# ----------------------------------------------------------------- équation caractéristique et dérivation


def test_equation_caracteristique_numerique():
    kLref = [math.pi / 2, math.pi, 4.493409457909064, 2 * math.pi]
    for cond, kl in zip(CONDITIONS, kLref, strict=True):
        r = buckling.analyze(base(cond, useSymbolic=False))
        assert r["methodUsed"] == "numérique"
        ce = r["charEquation"]
        assert ce["kL"] == pytest.approx(kl, rel=1e-12)
        assert ce["kLNumeric"] == pytest.approx(kl, rel=1e-12)
        assert ce["verified"] is True
        assert ce["coefLpExact"] == pytest.approx(math.pi / kl, rel=1e-12)
        assert ce["PEexact"] == pytest.approx(kl**2 * 210e9 * 5e-7 / 3**2, rel=1e-12)
        assert isinstance(r["derivation"], list)
        assert len(r["derivation"]) >= 8
        assert any("k^2" in ligne for ligne in r["derivation"])
    # encastré-articulé : le L' = L/√2 du cours est légèrement sécuritaire (PE cours < PE exact)
    r = buckling.analyze(base("encastre-articule", useSymbolic=False))
    assert r["charEquation"]["coefLpExact"] == pytest.approx(0.6991556596, rel=1e-8)
    assert r["PE"] < r["charEquation"]["PEexact"]
    assert r["charEquation"]["PEexact"] / r["PE"] == pytest.approx(4.493409457909064**2 / (2 * math.pi**2), rel=1e-12)
    # articulé : sin(kL) = 0 apparaît dans la dérivation
    r = buckling.analyze(base("articule-articule", useSymbolic=False))
    assert r["charEquation"]["text"] == "sin(kL) = 0"
    assert any(r"\sin(k\,L) = 0" in ligne for ligne in r["derivation"])
    assert any(r"v''(s) + k^2\,v(s) = 0" in ligne for ligne in r["derivation"])


# ----------------------------------------------------------------- courbe de stabilité


def test_courbe_de_stabilite_par_defaut():
    E, Re = 210e9, 235e6
    c = buckling.stabilityCurve(E, Re)
    lam = np.arange(0, 300.5, 0.5)
    np.testing.assert_array_equal(c["lambda"], lam)
    assert c["lambdaLim"] == pytest.approx(math.pi * math.sqrt(E / Re), rel=1e-14)
    assert c["lambdaCompression"] == 20
    for cle in ("sigmaEuler", "sigmaRankine", "sigmaPalier", "sigmaDesign"):
        assert c[cle].shape == lam.shape
    # Euler : NaN en λ = 0 (pas d'Inf), hyperbole ailleurs
    assert math.isnan(c["sigmaEuler"][0])
    assert not np.any(np.isinf(c["sigmaEuler"]))
    assert not np.any(np.isinf(c["sigmaDesign"])) and not np.any(np.isnan(c["sigmaDesign"]))
    np.testing.assert_allclose(c["sigmaEuler"][1:], math.pi**2 * E / lam[1:] ** 2, rtol=1e-14)
    np.testing.assert_allclose(c["sigmaRankine"], Re / (1 + (lam / c["lambdaLim"]) ** 2), rtol=1e-14)
    assert c["sigmaRankine"][0] == pytest.approx(Re, rel=1e-15)
    np.testing.assert_array_equal(c["sigmaPalier"], Re * np.ones(lam.shape))
    # courbe de dimensionnement (arbre de décision)
    iC = lam < 20
    iE = lam >= c["lambdaLim"]
    iR = ~iC & ~iE
    np.testing.assert_array_equal(c["sigmaDesign"][iC], Re * np.ones(np.count_nonzero(iC)))
    np.testing.assert_array_equal(c["sigmaDesign"][iR], c["sigmaRankine"][iR])
    np.testing.assert_array_equal(c["sigmaDesign"][iE], c["sigmaEuler"][iE])
    np.testing.assert_array_equal(c["zone"][iC], 1)
    np.testing.assert_array_equal(c["zone"][iR], 2)
    np.testing.assert_array_equal(c["zone"][iE], 3)
    assert np.all(c["sigmaDesign"] <= Re)
    # points remarquables : σE(λlim) = Re, σR(λlim) = Re/2
    cL = buckling.stabilityCurve(E, Re, [c["lambdaLim"], 20])
    assert cL["sigmaEuler"][0] == pytest.approx(Re, rel=1e-12)
    assert cL["sigmaRankine"][0] == pytest.approx(Re / 2, rel=1e-12)
    assert cL["sigmaDesign"][0] == pytest.approx(Re, rel=1e-12)
    assert cL["sigmaDesign"][1] == pytest.approx(Re / (1 + (20 / c["lambdaLim"]) ** 2), rel=1e-12)
    assert all(isinstance(x, str) for x in c["report"])
    verifier_latex(c["latex"])


def test_courbe_personnalisee_et_coherence_avec_analyze():
    c = buckling.stabilityCurve(70e9, 200e6, np.arange(0, 201, 10).reshape(-1, 1), 10)
    np.testing.assert_array_equal(c["lambda"], np.arange(0, 201, 10))
    assert c["lambdaCompression"] == 10
    np.testing.assert_array_equal(c["sigmaDesign"][c["lambda"] < 10], [200e6])
    for cond in CONDITIONS:
        for L in [0.2, 1, 3, 8]:
            p = base(cond, L=L)
            r = buckling.analyze(p)
            cc = buckling.stabilityCurve(p["E"], p["Re"], r["lambda"])
            np.testing.assert_allclose(cc["sigmaDesign"], r["Pcrit"] / r["S"], rtol=1e-12)
            np.testing.assert_allclose(cc["sigmaEuler"], r["sigmaE"], rtol=1e-12)


# ----------------------------------------------------------------- rapport, LaTeX, erreurs, contrat


def test_contenu_du_rapport():
    cas = [
        ("articule-articule", 0.2, "COMPRESSION SIMPLE"),
        ("encastre-encastre", 3, "RANKINE"),
        ("articule-articule", 3, "EULER"),
    ]
    for cond, L, regime in cas:
        r = buckling.analyze(base(cond, L=L, P=1e4))
        rep = r["report"]
        assert all(isinstance(ligne, str) for ligne in rep)
        assert any(regime in ligne for ligne in rep), regime
        assert any("Comparaison des trois modèles" in ligne for ligne in rep)
        assert any(ligne.strip().startswith("Compression  PC") for ligne in rep)
        assert any(ligne.strip().startswith("Euler        PE") for ligne in rep)
        assert any(ligne.strip().startswith("Rankine      PR") for ligne in rep)
        assert any("← retenu" in ligne for ligne in rep)
        assert any("λlim" in ligne for ligne in rep)
        assert any("Padm" in ligne for ligne in rep)
        assert any("Mode propre" in ligne for ligne in rep)
        assert r["planeText"]
        assert r["methodUsed"] == "numérique"
    r = buckling.analyze(base("encastre-articule"))
    assert any("L/√2" in ligne for ligne in r["report"])


def test_chaines_latex():
    chaines = []
    for cond in CONDITIONS:
        for L in [0.2, 3, 12]:
            r = buckling.analyze(base(cond, L=L, P=2e4))
            chaines += r["latex"] + r["derivation"]
    chaines += buckling.analyze(base(P=1e9, s=3))["latex"]
    chaines += buckling.analyze(base(P=0))["latex"]
    chaines += buckling.stabilityCurve(210e9, 235e6)["latex"]
    verifier_latex(chaines)


def test_erreurs():
    p = base()
    sans_Iy = {cle: val for cle, val in p.items() if cle != "Iy"}
    sans_condition = {cle: val for cle, val in p.items() if cle != "condition"}
    erreur(PREFIXE + "missingField", lambda: buckling.analyze(sans_Iy))
    erreur(PREFIXE + "missingField", lambda: buckling.analyze(sans_condition))
    erreur(PREFIXE + "invalidInput", lambda: buckling.analyze(42))
    erreur(PREFIXE + "invalidInput", lambda: buckling.analyze([p, p]))
    for champ, valeur in [("E", -1), ("S", 0), ("L", math.nan), ("Iz", "abc"), ("s", 0), ("P", math.inf),
                          ("P", [1, 2]), ("lambdaCompression", -5)]:  # fmt: skip
        erreur(PREFIXE + "invalidInput", lambda champ=champ, valeur=valeur: buckling.analyze({**p, champ: valeur}))
    erreur(PREFIXE + "condition", lambda: buckling.analyze(base("libre-libre")))
    erreur(PREFIXE + "condition", lambda: buckling.analyze(base(3)))
    erreur(PREFIXE + "condition", lambda: buckling.effectiveLengthCoefficient("glissiere"))
    erreur(PREFIXE + "invalidInput", lambda: buckling.stabilityCurve(210e9))
    erreur(PREFIXE + "invalidInput", lambda: buckling.stabilityCurve(210e9, -1))
    erreur(PREFIXE + "invalidInput", lambda: buckling.stabilityCurve(210e9, 235e6, [-1, 2]))
    erreur(PREFIXE + "invalidInput", lambda: buckling.stabilityCurve(210e9, 235e6, [1, math.inf]))
    erreur(PREFIXE + "invalidInput", lambda: buckling.stabilityCurve(210e9, 235e6, np.ones((2, 2))))


def test_contrat_de_la_structure_de_resultat():
    r = buckling.analyze(base("encastre-libre", P=1e3))
    champs = [
        "Imin", "Imax", "axis", "planeText", "rmin", "coefLp", "Lp", "lambda", "lambdaLim", "regime", "PC", "PE",
        "PR", "sigmaE", "Pcrit", "Padm", "ok", "sigmaApplied", "modeShape", "derivation", "methodUsed", "report",
        "latex",
    ]  # fmt: skip
    for champ in champs:
        assert champ in r, champ
    assert callable(r["modeShape"])
    assert r["axis"] in ("y", "z")
    assert r["regime"] in ("compression", "rankine", "euler")
    c = buckling.stabilityCurve(210e9, 235e6)
    for champ in [
        "lambda",
        "sigmaEuler",
        "sigmaRankine",
        "sigmaPalier",
        "sigmaDesign",
        "lambdaLim",
        "lambdaCompression",
    ]:
        assert champ in c, champ


def test_delegation_depuis_solicitations():
    p = {"E": 210e9, "Re": 235e6, "S": 1e-3, "Iz": 2e-6, "Iy": 5e-7, "L": 3, "condition": "articule-articule", "P": 1e4}
    b = se.buckling(p)
    assert b["PE"] == pytest.approx(math.pi**2 * 210e9 * 5e-7 / 9, rel=1e-9)
    assert b["regime"] == buckling.analyze(p)["regime"]


# ----------------------------------------------------------------- golden files


@pytest.mark.parametrize("cas", case_ids(GOLDEN, prefix="buckling_"))
def test_golden_analyze(cas):
    attendu = get_case(GOLDEN, cas)
    assert_matches(buckling.analyze(attendu["entrees"]), attendu["sortie"], rel=1e-9, ignore=SYMBOLIQUE)


def test_golden_stability_curve():
    attendu = get_case(GOLDEN, "stabilityCurve")
    e = attendu["entrees"]
    assert_matches(buckling.stabilityCurve(e["E"], e["Re"], e["lambdaVec"]), attendu["sortie"], rel=1e-9)
