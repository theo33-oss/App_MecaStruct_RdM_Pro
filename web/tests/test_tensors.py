"""Tests de tensors (étape E15) : portage des tests de tests/test_TensorAndCriteriaEngine.m pour principal, facet,
plane2D, plane2DStrain, mohr3D, criteria et yieldLoci, puis cas golden (golden_tensors.json).

Le générateur aléatoire de MATLAB (mt19937ar, graine 17) n'est pas reproduit : les tests aléatoires gardent les mêmes
propriétés avec numpy default_rng. Le rendu LaTeX n'est pas testé : délimiteurs $, ASCII et commandes interdites.
"""

import math

import numpy as np
import pytest

from mecastruct.core import tensors
from mecastruct.core.data_manager import hasSymbolic
from mecastruct.core.errors import MecaStructError
from tests.golden_tools import assert_matches, get_case
from tests.test_data_manager import FORBIDDEN_LATEX

GOLDEN = "golden_tensors.json"
PREFIXE = "MecaStruct:TensorAndCriteriaEngine:"


def proche(actual, expected, rel=0.0, abs_=0.0):
    """Égalité à la tolérance près (verifyEqual avec RelTol / AbsTol de MATLAB ; rel = abs = 0 : égalité exacte).

    abs_ peut être un tableau (une tolérance par composante).
    """
    a = np.asarray(actual, dtype=float)
    e = np.asarray(expected, dtype=float)
    ecart = np.abs(a - e)
    assert np.all((ecart <= abs_ + rel * np.abs(e)) | (a == e)), f"{a} attendu {e} (écart {ecart})"


def erreur(identifiant, appel):
    """Vérifie que l'appel lève une MecaStructError d'identifiant 'MecaStruct:TensorAndCriteriaEngine:<id>'."""
    with pytest.raises(MecaStructError) as info:
        appel()
    assert info.value.identifier == PREFIXE + identifiant


def verifier_latex(chaines):
    """Chaînes LaTeX entre $, ASCII, sans commande interdite."""
    for s in chaines:
        assert s.startswith("$") and s.endswith("$"), s
        assert s.isascii(), s
        assert not any(cmd in s for cmd in FORBIDDEN_LATEX), s


def _contrainteTresca(P):
    """max(|σ1|, |σ2|, |σ1 − σ2|) pour chaque point [σ1 σ2] de P."""
    return np.max(np.column_stack([np.abs(P[:, 0]), np.abs(P[:, 1]), np.abs(P[:, 0] - P[:, 1])]), axis=1)


def _rotation(theta):
    """Matrice R = [cos θ sin θ ; −sin θ cos θ] de la convention de TensorAndCriteriaEngine."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, s], [-s, c]])


# -------------------------------------------------------------------------------------------------
# Contraintes principales
# -------------------------------------------------------------------------------------------------
def test_traction_simple():
    s0 = 150e6
    sig = np.diag([s0, 0.0, 0.0])
    r = tensors.principal(sig, False)
    proche([r["sigmaI"], r["sigmaII"], r["sigmaIII"]], [s0, 0, 0], abs_=1e-12 * s0)
    proche(r["I1"], s0, rel=1e-14)
    proche(r["I2"], 0, abs_=1e-12 * s0**2)
    proche(r["I3"], 0, abs_=1e-12 * s0**3)
    proche(r["charPoly"], [1, -s0, 0, 0], abs_=1e-12 * np.array([1, s0, s0**2, s0**3]))
    proche(r["rootsCharPoly"], [s0, 0, 0], abs_=1e-9 * s0)
    proche(r["eigVals"], [s0, 0, 0], abs_=1e-12 * s0)
    proche(r["tauMax"], s0 / 2, rel=1e-12)
    proche(np.abs(r["directions"][:, 0]), [1, 0, 0], abs_=1e-12)
    proche(np.linalg.det(r["directions"]), 1, abs_=1e-12)
    proche(r["sigmaOct"], s0 / 3, rel=1e-12)
    proche(r["tauOct"], math.sqrt(2) * s0 / 3, rel=1e-12)
    assert r["methodUsed"] == "numérique"

    c = tensors.criteria([r["sigmaI"], r["sigmaII"], r["sigmaIII"]], 235e6, 1.5)
    proche(c["sigmaEqTresca"], s0, rel=1e-12)
    proche(c["sigmaEqVM"], s0, rel=1e-12)
    proche(c["sigmaMaxNormal"], s0, rel=1e-12)
    proche(c["sigmaAdm"], 235e6 / 1.5, rel=1e-14)
    assert c["okTresca"] and c["okVM"] and c["okRankine"]
    proche(c["sfTresca"], 235 / 150, rel=1e-12)
    proche(c["sfVM"], 235 / 150, rel=1e-12)

    # Facette inclinée à 45° : σn = τ = σ/2 ; formules du cours en 2D : σ = σ0 cos²θ, τ = −σ0 sinθ cosθ
    f = tensors.facet(sig, [1, 1, 0])
    proche(f["sigmaN"], s0 / 2, rel=1e-12)
    proche(f["tauNorm"], s0 / 2, rel=1e-12)
    th = np.linspace(0, np.pi, 13)
    p = tensors.plane2D(s0, 0, 0, th)
    proche(p["sigma"], s0 * np.cos(th) ** 2, abs_=1e-12 * s0)
    proche(p["tau"], -s0 * np.sin(th) * np.cos(th), abs_=1e-12 * s0)


def test_cisaillement_pur():
    tau = 80e6
    sig = np.array([[0, tau, 0], [tau, 0, 0], [0, 0, 0]], dtype=float)
    r = tensors.principal(sig, False)
    proche([r["sigmaI"], r["sigmaII"], r["sigmaIII"]], [tau, 0, -tau], abs_=1e-12 * tau)
    proche(r["tauMax"], tau, rel=1e-12)
    d = r["directions"]
    proche(abs(d[:, 0] @ np.array([1, 1, 0]) / math.sqrt(2)), 1, abs_=1e-12)
    proche(abs(d[:, 2] @ np.array([1, -1, 0]) / math.sqrt(2)), 1, abs_=1e-12)
    proche(abs(d[:, 1] @ np.array([0, 0, 1])), 1, abs_=1e-12)
    proche(np.linalg.det(d), 1, abs_=1e-12)
    proche(r["I2"], -(tau**2), rel=1e-14)

    c = tensors.criteria(sig, 300e6)
    proche(c["sigmaEqTresca"], 2 * tau, rel=1e-12)
    proche(c["sigmaEqVM"], math.sqrt(3) * tau, rel=1e-12)
    proche(c["sigmaMaxNormal"], tau, rel=1e-12)
    proche(c["tauMax"], tau, rel=1e-12)
    proche(c["sigmaR"], 300e6, rel=0)  # défaut sigmaR = Re
    assert c["okTresca"] and c["okVM"] and c["okRankine"]

    p = tensors.plane2D(0, 0, tau, math.pi / 4)
    proche(p["sigma"], tau, rel=1e-12)
    proche(p["tau"], 0, abs_=1e-12 * tau)
    proche(p["thetaP"], math.pi / 4, abs_=1e-14)
    proche(p["delta"], 0, abs_=1e-20)
    proche(p["rho"], tau, rel=1e-14)
    proche([p["sigma1"], p["sigma2"]], [tau, -tau], rel=1e-14)
    proche(p["tauMax2D"], tau, rel=1e-14)


def test_exemple_3d_valeurs_connues():
    # σ = [5 2 0 ; 2 2 0 ; 0 0 −3] MPa : σI = 6, σII = 1, σIII = −3 MPa (bloc 2x2 : (7 ± 5)/2)
    sig = np.array([[5, 2, 0], [2, 2, 0], [0, 0, -3]], dtype=float) * 1e6
    r = tensors.principal(sig)
    proche(r["I1"], 4e6, rel=1e-14)
    proche(r["I2"], -15e12, rel=1e-14)
    proche(r["I3"], -18e18, rel=1e-12)
    proche(r["charPoly"], [1, -4e6, -15e12, 18e18], rel=1e-12)
    proche(r["eigVals"], np.array([6, 1, -3]) * 1e6, rel=1e-12)
    proche(r["rootsCharPoly"], np.array([6, 1, -3]) * 1e6, rel=1e-12)
    assert r["rootsEigDiff"] < 1e-12
    proche(r["sigmaI"], 6e6, rel=1e-12)
    # Directions : nI = (2, 1, 0)/√5, nII = (−1, 2, 0)/√5, nIII = nI ∧ nII = (0, 0, 1)
    d = r["directions"]
    proche(d[:, 0], np.array([2, 1, 0]) / math.sqrt(5), abs_=1e-12)
    proche(d[:, 1], np.array([-1, 2, 0]) / math.sqrt(5), abs_=1e-12)
    proche(d[:, 2], [0, 0, 1], abs_=1e-12)
    proche(np.cross(d[:, 0], d[:, 1]), d[:, 2], abs_=1e-12)
    assert r["residual"] < 1e-13
    proche(r["tauMax"], 4.5e6, rel=1e-12)
    proche(r["sigmaOct"], 4e6 / 3, rel=1e-12)
    proche(r["tauOct"], math.sqrt(122) / 3 * 1e6, rel=1e-12)
    # Liens avec le déviateur : τoct = √(2 J2/3), σVM = √(3 J2)
    proche(r["tauOct"], math.sqrt(2 * r["J2"] / 3), rel=1e-12)
    c = tensors.criteria(sig, 235e6)
    proche(c["sigmaEqVM"], math.sqrt(3 * r["J2"]), rel=1e-12)
    proche(c["sigmaEqTresca"], 9e6, rel=1e-12)
    # Polynôme caractéristique nul aux valeurs propres
    proche(np.polyval(r["charPoly"], r["eigVals"]) / 1e18, np.zeros(3), abs_=1e-9)
    # Entrée équivalente : vecteur de Voigt [xx yy zz yz xz xy]
    rv = tensors.principal(np.array([5, 2, -3, 0, 0, 2]) * 1e6, False)
    proche(rv["eigVals"], r["eigVals"], rel=1e-12)


def test_tenseur_tourne_quelconque():
    lam = np.array([250, -40, -120]) * 1e6
    Rz = _rot3(0.7, "z")
    Rx = _rot3(-0.4, "x")
    Rz2 = _rot3(1.9, "z")
    Q = Rz @ Rx @ Rz2
    sig = Q @ np.diag(lam) @ Q.T
    sig = (sig + sig.T) / 2
    r = tensors.principal(sig, False)
    proche(r["eigVals"], lam, rel=1e-12)
    proche(r["rootsCharPoly"], lam, rel=1e-10)
    proche(np.abs(Q.T @ r["directions"]), np.eye(3), abs_=1e-10)
    proche(r["directions"].T @ r["directions"], np.eye(3), abs_=1e-13)
    proche(np.linalg.det(r["directions"]), 1, abs_=1e-13)
    proche(r["I1"], lam.sum(), rel=1e-12)
    proche(r["I2"], lam[0] * lam[1] + lam[1] * lam[2] + lam[0] * lam[2], rel=1e-12)
    proche(r["I3"], lam.prod(), rel=1e-12)

    # Trièdre direct et résidu sur une série de tenseurs aléatoires (graine fixée)
    rng = np.random.default_rng(17)
    for _ in range(25):
        A = (rng.random((3, 3)) - 0.5) * 400e6
        A = (A + A.T) / 2
        rk = tensors.principal(A, False)
        proche(np.linalg.det(rk["directions"]), 1, abs_=1e-12)
        proche(rk["directions"].T @ rk["directions"], np.eye(3), abs_=1e-12)
        assert rk["residual"] < 1e-12
        assert np.all(np.diff(rk["eigVals"]) <= 0)
        proche(rk["rootsCharPoly"], rk["eigVals"], abs_=1e-8 * np.max(np.abs(A)))


def _rot3(angle, axe):
    """Rotation de `angle` (rad) autour de l'axe 'x' ou 'z'."""
    c, s = math.cos(angle), math.sin(angle)
    if axe == "z":
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def test_etat_hydrostatique():
    p = -50e6
    r = tensors.principal(p * np.eye(3), False)
    proche(r["eigVals"], [p] * 3, rel=1e-14)
    proche(r["rootsCharPoly"], [p] * 3, rel=1e-4)  # racine triple : précision ~ eps^(1/3)
    proche(r["tauMax"], 0, abs_=1e-20)
    proche(r["tauOct"], 0, abs_=1e-20)
    proche(r["directions"], np.eye(3), abs_=1e-14)
    c = tensors.criteria(p * np.eye(3), 235e6)
    proche(c["sigmaEqTresca"], 0, abs_=1e-20)
    proche(c["sigmaEqVM"], 0, abs_=1e-20)
    assert c["sfTresca"] == math.inf
    assert c["sfVM"] == math.inf
    proche(c["sigmaMaxNormal"], 50e6, rel=1e-14)
    r0 = tensors.principal(np.zeros((3, 3)), False)
    proche(r0["eigVals"], np.zeros(3), abs_=0)
    proche(np.linalg.det(r0["directions"]), 1, abs_=1e-14)


def test_polynome_symbolique():
    sig = np.array([[120, 30, 0], [30, -40, 10], [0, 10, 25]], dtype=float) * 1e6
    rn = tensors.principal(sig, False)
    assert rn["methodUsed"] == "numérique"
    assert rn["charPolySym"] == []
    # Valeurs de référence (calcul symbolique exact en MPa) : −λ³ + 105 λ² + 3800 λ − 154500
    proche(rn["charPoly"], [1, -105e6, -3800e12, 154500e18], rel=1e-12)
    if hasSymbolic():
        rs = tensors.principal(sig, True)
        assert rs["methodUsed"] == "symbolique"
        proche(rs["charPolySym"], rn["charPoly"], rel=1e-12)
        assert any(r"\mathrm{det}(\sigma - \lambda I)" in s for s in rs["latex"])
        proche(rs["eigVals"], rn["eigVals"], rel=1e-14)
    else:
        rs = tensors.principal(sig, True)
        assert rs["methodUsed"] == "numérique"


# -------------------------------------------------------------------------------------------------
# Facette, Mohr 2D et 3D
# -------------------------------------------------------------------------------------------------
def test_facette():
    sig = np.array([[120, 30, -20], [30, -40, 10], [-20, 10, 25]], dtype=float) * 1e6
    r = tensors.facet(sig, [1, 2, 2])
    n = np.array([1, 2, 2]) / 3
    Cn = sig @ n
    proche(r["n"], n, abs_=1e-15)
    proche(r["Cn"], Cn, rel=1e-14)
    proche(r["sigmaN"], Cn @ n, rel=1e-14)
    proche(r["tauVec"] @ n, 0, abs_=1e-8)
    proche(r["tauNorm"], math.sqrt(Cn @ Cn - (Cn @ n) ** 2), rel=1e-12)
    proche(r["normalVec"] + r["tauVec"], Cn, rel=1e-14)
    assert math.isnan(r["tauT"])
    # Tangente fournie orthogonale
    t = np.array([2, -1, 0]) / math.sqrt(5)
    r2 = tensors.facet(sig, n, t)
    assert r2["tProjected"] is False
    proche(r2["tauT"], Cn @ t, rel=1e-13)
    # Tangente non orthogonale : projetée sur le plan de la facette
    r3 = tensors.facet(sig, n, [1, 0, 0])
    assert r3["tProjected"] is True
    proche(r3["t"] @ n, 0, abs_=1e-15)
    proche(np.linalg.norm(r3["t"]), 1, abs_=1e-15)
    proche(r3["tauT"], Cn @ r3["t"], rel=1e-12)
    # Erreurs
    erreur("zeroVector", lambda: tensors.facet(sig, [0, 0, 0]))
    erreur("badInput", lambda: tensors.facet(sig, n, 2 * n))
    erreur("badInput", lambda: tensors.facet(sig, [1, 2, 3, 4]))


def test_plane2d_coherence_rotation():
    # Convention : n = (cos θ, sin θ), t = (−sin θ, cos θ) ; σ = Cn·n, τ = Cn·t, identiques aux composantes σ'11 et
    # σ'12 de σ' = R σ Rᵀ avec R = [cos θ sin θ ; −sin θ cos θ].
    sxx, syy, sxy = 120e6, -40e6, 30e6
    S = np.array([[sxx, sxy], [sxy, syy]])
    th = np.linspace(-np.pi, np.pi, 37)
    r = tensors.plane2D(sxx, syy, sxy, th)
    assert r["sigma"].shape == th.shape
    assert r["tau"].shape == th.shape
    tol = 1e-12 * 120e6
    for k, theta in enumerate(th):
        Sp = _rotation(theta) @ S @ _rotation(theta).T
        proche(r["sigma"][k], Sp[0, 0], abs_=tol)
        proche(r["tau"][k], Sp[0, 1], abs_=tol)
        n = np.array([math.cos(theta), math.sin(theta)])
        t = np.array([-math.sin(theta), math.cos(theta)])
        proche(r["tau"][k], (S @ n) @ t, abs_=tol)
        f = tensors.facet(S, n, t)
        proche(f["sigmaN"], r["sigma"][k], abs_=tol)
        proche(f["tauT"], r["tau"][k], abs_=tol)
    rho = math.hypot(80, 30) * 1e6
    proche(r["delta"], 40e6, rel=1e-14)
    proche(r["rho"], rho, rel=1e-14)
    proche([r["sigma1"], r["sigma2"]], np.sort(np.linalg.eigvalsh(S))[::-1], rel=1e-12)
    proche(r["thetaP"], 0.5 * math.atan2(60, 160), abs_=1e-15)
    proche(r["pointA"], [sxx, sxy])
    proche(r["pointB"], [syy, -sxy])
    proche(r["tauMax2D"], rho, rel=1e-14)
    # Facettes principales et de cisaillement maximal
    p1 = tensors.plane2D(sxx, syy, sxy, r["thetaP"])
    proche(p1["sigma"], r["sigma1"], rel=1e-12)
    proche(p1["tau"], 0, abs_=1e-12 * rho)
    p2 = tensors.plane2D(sxx, syy, sxy, r["thetaP"] + math.pi / 2)
    proche(p2["sigma"], r["sigma2"], rel=1e-12)
    p3 = tensors.plane2D(sxx, syy, sxy, r["thetaTauMax"])
    proche(p3["tau"], rho, rel=1e-12)
    proche(p3["sigma"], r["delta"], rel=1e-12)
    # Cercle : fermé, points à distance ρ du centre ; points des facettes sur le cercle
    assert r["circle"].shape[1] == 2
    proche(r["circle"][0], r["circle"][-1])
    proche(np.hypot(r["circle"][:, 0] - r["delta"], r["circle"][:, 1]), rho, rel=1e-12)
    proche(np.hypot(r["sigma"] - r["delta"], r["tau"]), rho, rel=1e-12)
    # Sens de parcours : le point de la facette θ se déduit de A par une rotation de −2θ (horaire)
    angA = math.atan2(sxy, sxx - r["delta"])
    angT = np.arctan2(r["tau"], r["sigma"] - r["delta"])
    proche(np.angle(np.exp(1j * (angT - (angA - 2 * th)))), np.zeros(th.size), abs_=1e-12)
    # État 3D associé (σzz = 0)
    proche(r["principal3D"], np.sort([r["sigma1"], r["sigma2"], 0.0])[::-1])
    proche(r["tauMax3D"], (max(r["sigma1"], 0) - min(r["sigma2"], 0)) / 2, rel=1e-14)
    # Valeur par défaut θ = 0 et tableau 2D de θ
    r0 = tensors.plane2D(sxx, syy, sxy)
    proche([r0["sigma"], r0["tau"]], [sxx, sxy], rel=1e-14)
    rm = tensors.plane2D(sxx, syy, sxy, np.linspace(0, np.pi, 6).reshape(2, 3))
    assert rm["sigma"].shape == (2, 3)


def test_plane2d_strain():
    exx, eyy, exy = 500e-6, -200e-6, 150e-6
    Ee = np.array([[exx, exy], [exy, eyy]])
    th = np.linspace(0, np.pi, 19)
    r = tensors.plane2DStrain(exx, eyy, exy, th)
    for k, theta in enumerate(th):
        Ep = _rotation(theta) @ Ee @ _rotation(theta).T
        proche(r["eps"][k], Ep[0, 0], abs_=1e-12 * 500e-6)
        proche(r["gammaHalf"][k], Ep[0, 1], abs_=1e-12 * 500e-6)
    proche(r["gamma"], 2 * r["gammaHalf"], rel=1e-15)
    proche([r["eps1"], r["eps2"]], np.sort(np.linalg.eigvalsh(Ee))[::-1], rel=1e-12)
    proche(r["gammaMax2D"], r["eps1"] - r["eps2"], rel=1e-12)
    proche(r["gxy"], 300e-6, rel=1e-15)
    proche(r["pointA"], [exx, exy])
    proche(r["pointB"], [eyy, -exy])
    assert r["kind"] == "strain"
    proche(r["delta"], 150e-6, rel=1e-14)
    proche(r["rho"], math.sqrt(350**2 + 150**2) * 1e-6, rel=1e-14)


def test_mohr3d():
    m = tensors.mohr3D([50e6, -100e6, 200e6])
    proche(m["pr"], [200e6, 50e6, -100e6])
    proche(m["centers"], [125e6, -25e6, 50e6], rel=1e-14)
    proche(m["radii"], [75e6, 75e6, 150e6], rel=1e-14)
    proche(m["tauMax"], 150e6, rel=1e-14)
    assert len(m["circles"]) == 3
    for k in range(3):
        C = m["circles"][k]
        assert C.shape[1] == 2
        proche(np.hypot(C[:, 0] - m["centers"][k], C[:, 1]), m["radii"][k] * np.ones(C.shape[0]), rel=1e-12)
    # État plan [σ1 σ2] : σ3 = 0 ajouté ; tenseur 3x3 accepté
    mp = tensors.mohr3D([80e6, -30e6])
    proche(mp["pr"], [80e6, 0, -30e6])
    sig = np.array([[5, 2, 0], [2, 2, 0], [0, 0, -3]], dtype=float) * 1e6
    mt = tensors.mohr3D(sig)
    proche(mt["pr"], [6e6, 1e6, -3e6], rel=1e-12)
    # Tout point (σn, τ) d'une facette est dans le grand cercle et hors des deux petits
    rng = np.random.default_rng(3)
    for _ in range(50):
        f = tensors.facet(sig, rng.standard_normal(3))
        dBig = math.hypot(f["sigmaN"] - mt["centers"][2], f["tauNorm"]) - mt["radii"][2]
        d1 = math.hypot(f["sigmaN"] - mt["centers"][0], f["tauNorm"]) - mt["radii"][0]
        d2 = math.hypot(f["sigmaN"] - mt["centers"][1], f["tauNorm"]) - mt["radii"][1]
        assert dBig <= 1e-6
        assert d1 >= -1e-6
        assert d2 >= -1e-6


# -------------------------------------------------------------------------------------------------
# Critères et lieux de plasticité
# -------------------------------------------------------------------------------------------------
def test_criteres():
    c = tensors.criteria([50e6, -100e6, 200e6], 355e6, 1.2, 490e6)
    proche(c["pr"], [200e6, 50e6, -100e6])
    proche(c["sigmaEqTresca"], 300e6, rel=1e-14)
    proche(c["sigmaEqVM"], math.sqrt(67500) * 1e6, rel=1e-14)
    proche(c["sigmaMaxNormal"], 200e6, rel=1e-14)
    proche(c["sigmaAdm"], 355e6 / 1.2, rel=1e-14)
    assert not c["okTresca"]  # 300 > 295,8 MPa
    assert c["okVM"]  # 259,8 ≤ 295,8 MPa
    assert c["okRankine"]  # 200 ≤ 490/1,2 MPa
    proche(c["sfTresca"], 355 / 300, rel=1e-14)
    proche(c["sfVM"], 355 / math.sqrt(67500), rel=1e-14)
    proche(c["sfRankine"], 490 / 200, rel=1e-14)
    proche(c["sigmaRAdm"], 490e6 / 1.2, rel=1e-14)
    # Rapport Tresca / Von Mises compris entre 1 et 2/√3
    assert c["sigmaEqTresca"] / c["sigmaEqVM"] >= 1
    assert c["sigmaEqTresca"] / c["sigmaEqVM"] <= 2 / math.sqrt(3) + 1e-12
    # Contraintes planes : σVM = √(σ1² − σ1σ2 + σ2²)
    cp = tensors.criteria([120e6, -70e6], 235e6)
    proche(cp["sigmaEqVM"], math.sqrt(120**2 + 120 * 70 + 70**2) * 1e6, rel=1e-14)
    proche(cp["sigmaEqTresca"], 190e6, rel=1e-14)
    # Matériau fragile : contrainte normale maximale non vérifiée
    cf = tensors.criteria([-250e6, 0, 0], 300e6, 1, 200e6)
    assert not cf["okRankine"]
    proche(cf["sigmaMaxNormal"], 250e6)
    # Entrées : vecteur de Voigt et valeur NaN de sigmaR (→ Re)
    cv = tensors.criteria(np.array([5, 2, -3, 0, 0, 2]) * 1e6, 235e6, 1, math.nan)
    proche(cv["sigmaEqTresca"], 9e6, rel=1e-12)
    proche(cv["sigmaR"], 235e6)
    # Erreurs
    erreur("badInput", lambda: tensors.criteria([1, 2, 3], -1))
    erreur("badInput", lambda: tensors.criteria([1, 2, 3], 235e6, 0))
    erreur("badInput", lambda: tensors.criteria([1, 2, 3, 4], 235e6))


def test_lieux_plasticite():
    Re, s, sR = 235e6, 1.5, 340e6
    L = tensors.yieldLoci(Re, s, sR)
    a = Re / s
    proche(L["sigmaAdm"], a, rel=1e-15)
    # Ellipse exacte de Von Mises : σ1² − σ1σ2 + σ2² = σadm²
    V = L["vonMises"]
    assert V.shape[1] == 2
    assert V.shape[0] > 100
    proche(V[0], V[-1])
    proche(V[:, 0] ** 2 - V[:, 0] * V[:, 1] + V[:, 1] ** 2, np.full(V.shape[0], a**2), rel=1e-12)
    # Hexagone de Tresca : fermé, max(|σ1|, |σ2|, |σ1 − σ2|) = σadm aux sommets et sur les côtés
    H = L["tresca"]
    assert H.shape == (7, 2)
    proche(H[0], H[-1])
    proche(_contrainteTresca(H), np.full(7, a), rel=1e-14)
    mid = (H[:-1] + H[1:]) / 2
    proche(_contrainteTresca(mid), np.full(6, a), rel=1e-14)
    # Hexagone inscrit dans l'ellipse (sommets sur l'ellipse)
    proche(H[:, 0] ** 2 - H[:, 0] * H[:, 1] + H[:, 1] ** 2, np.full(7, a**2), rel=1e-14)
    # Carré de Rankine
    Q = L["rankine"]
    assert Q.shape == (5, 2)
    proche(Q[0], Q[-1])
    proche(np.max(np.abs(Q), axis=1), np.full(5, sR / s), rel=1e-14)
    # Cohérence avec criteria sur quelques points de l'ellipse
    for k in range(0, V.shape[0], 30):
        c = tensors.criteria(V[k], Re, s)
        proche(c["sigmaEqVM"], a, rel=1e-12)
    # Valeurs par défaut (s = 1, sigmaR = Re)
    L1 = tensors.yieldLoci(Re)
    proche(L1["sigmaAdm"], Re)
    proche(np.max(np.abs(L1["rankine"])), Re)


# -------------------------------------------------------------------------------------------------
# Cas golden (sorties MATLAB exportées)
# -------------------------------------------------------------------------------------------------
def test_golden_principal():
    cas = get_case(GOLDEN, "principal")
    r = tensors.principal(np.array(cas["entrees"], dtype=float), False)
    assert_matches(r, cas["sortie"], rel=1e-9, abs_=1e-6)


def test_golden_facet():
    cas = get_case(GOLDEN, "facet")
    e = cas["entrees"]
    r = tensors.facet(np.array(e["sig"], dtype=float), e["n"])
    assert_matches(r, cas["sortie"], rel=1e-9, abs_=1e-6)


def test_golden_plane2d():
    cas = get_case(GOLDEN, "plane2D")
    assert_matches(tensors.plane2D(*cas["entrees"]), cas["sortie"], rel=1e-9, abs_=1e-6)


def test_golden_plane2d_strain():
    cas = get_case(GOLDEN, "plane2DStrain")
    assert_matches(tensors.plane2DStrain(*cas["entrees"]), cas["sortie"], rel=1e-9, abs_=1e-6)


def test_golden_mohr3d():
    cas = get_case(GOLDEN, "mohr3D")
    assert_matches(tensors.mohr3D(cas["entrees"]), cas["sortie"], rel=1e-9, abs_=1e-6)


def test_golden_criteria():
    cas = get_case(GOLDEN, "criteria")
    e = cas["entrees"]
    assert_matches(tensors.criteria(e["pr"], e["Re"], e["s"]), cas["sortie"], rel=1e-9, abs_=1e-6)


def test_golden_yield_loci():
    cas = get_case(GOLDEN, "yieldLoci")
    e = cas["entrees"]
    assert_matches(tensors.yieldLoci(e["Re"], e["s"]), cas["sortie"], rel=1e-9, abs_=1e-6)


def test_rapports_et_latex():
    sig = np.array([[120, 30, -20], [30, -40, 10], [-20, 10, 25]], dtype=float) * 1e6
    resultats = [
        tensors.principal(sig, True),
        tensors.facet(sig, [1, 2, 2], [2, -1, 0]),
        tensors.plane2D(120e6, -40e6, 30e6, 0.4),
        tensors.plane2DStrain(500e-6, -200e-6, 150e-6, 0.4),
        tensors.mohr3D(sig),
        tensors.criteria(sig, 235e6),
        tensors.yieldLoci(235e6),
    ]
    for r in resultats:
        assert r["report"] and all(isinstance(s, str) for s in r["report"])
        verifier_latex(r["latex"])
