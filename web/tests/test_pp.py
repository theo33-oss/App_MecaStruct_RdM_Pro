"""Tests de pp (étape E05) : portage des tests testPp*, testPoly2* et testHasSymbolic de BeamAndTrussSolver."""

import importlib.util

import numpy as np
import pytest

from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import (
    _mergeBreaks,
    _num,
    _shiftPoly,
    _texNum,
    hasSymbolic,
    poly2latex,
    poly2str,
    ppAdd,
    ppConst,
    ppDerivative,
    ppEval,
    ppIntegral,
    ppIntegrate,
    ppMultiply,
    ppRefine,
    ppSample,
    ppScale,
    ppZero,
)

ARG = "MecaStruct:BeamAndTrussSolver:invalidArgument"
PP_INVALIDE = "MecaStruct:BeamAndTrussSolver:invalidPP"


def verifier_erreur(identifiant, appel, *args):
    """Vérifie que l'appel lève une MecaStructError portant l'identifiant MATLAB attendu."""
    with pytest.raises(MecaStructError) as info:
        appel(*args)
    assert info.value.identifier == identifiant


def _fA(s):
    """Polynôme par morceaux A de l'essai : s sur [0, 2], 4 - s sur [2, 4]."""
    return np.where(s < 2, s, 4 - s)


def _fB(s):
    """Polynôme par morceaux B de l'essai : 3 sur [0, 1], s + 1 sur [1, 4]."""
    return np.where(s < 1, 3.0, s + 1)


def test_pp_eval_sides():
    pp = {"breaks": [0, 1, 3], "coefs": [[2, 0], 5]}
    assert ppEval(pp, 1) == 5
    assert ppEval(pp, 1, "right") == 5
    assert ppEval(pp, 1, "left") == 2
    assert ppEval(pp, 0, "left") == 0
    assert ppEval(pp, 3) == 5
    assert ppEval(pp, 3, "left") == 5
    np.testing.assert_array_equal(ppEval(pp, [[0.5, 2], [1, 3]]), [[1, 5], [5, 5]])
    np.testing.assert_array_equal(ppEval(pp, [[0.25], [0.5]]), [[0.5], [1]])
    # tolérance relative 1e-12·L aux points de rupture
    assert ppEval(pp, 1 - 1e-14) == 5
    assert ppEval(pp, 1 + 1e-14, "left") == pytest.approx(2, abs=1e-12)
    # prolongement hors du domaine
    assert ppEval(pp, -1) == -2
    assert ppEval(pp, 4) == 5
    assert ppEval(pp, []).size == 0
    verifier_erreur(ARG, ppEval, pp, 1, "milieu")
    verifier_erreur(PP_INVALIDE, ppEval, {"a": 1}, 1)
    verifier_erreur(PP_INVALIDE, ppEval, {"breaks": [0, 1, 2], "coefs": [1]}, 1)


def test_pp_sample():
    pp = {"breaks": [0, 1, 3], "coefs": [[2, 0], 5]}
    s, v = ppSample(pp, 5)
    assert s.shape == (10,)
    assert v.shape == (10,)
    np.testing.assert_array_equal(s[4:6], [1, 1])
    np.testing.assert_array_equal(v[4:6], [2, 5])
    np.testing.assert_array_equal([s[0], s[-1]], [0, 3])
    idx = [0, 1, 2, 3, 6, 7, 8, 9]
    np.testing.assert_allclose(v[idx], ppEval(pp, s[idx]), atol=1e-14)
    s60, _ = ppSample(pp)
    assert s60.size == 120
    verifier_erreur(ARG, ppSample, pp, 1)


def test_pp_integrate_derivative():
    pp = {"breaks": [0, 1, 3], "coefs": [[2, 0], 5]}
    P = ppIntegrate(pp, 2)
    # primitive : s² + 2 sur [0, 1], 5s - 2 sur [1, 3]
    np.testing.assert_allclose(ppEval(P, [0, 0.5, 1, 2, 3]), [2, 2.25, 3, 8, 13], atol=1e-13)
    assert ppEval(P, 1, "left") == pytest.approx(ppEval(P, 1, "right"), abs=1e-13)
    P0 = ppIntegrate(pp)
    assert ppEval(P0, 0) == pytest.approx(0, abs=1e-15)
    Dp = ppDerivative(P)
    t = [0.1, 0.7, 1.3, 2.9]
    np.testing.assert_allclose(ppEval(Dp, t), ppEval(pp, t), atol=1e-12)
    Dc = ppDerivative(ppConst([0, 2], 7))
    assert ppEval(Dc, 1) == 0
    # intégration double d'une constante : s² / 2
    P2 = ppIntegrate(ppIntegrate(ppConst([0, 1, 2, 4], 1)))
    s = np.array([0.5, 1.5, 3, 4])
    np.testing.assert_allclose(ppEval(P2, s), s**2 / 2, rtol=1e-13)


def test_pp_add_scale_multiply_refine():
    A = {"breaks": [0, 2, 4], "coefs": [[1, 0], [-1, 4]]}
    B = {"breaks": [0, 1, 4], "coefs": [3, [1, 1]]}
    t = np.array([0.3, 0.9, 1.4, 1.99, 2.5, 3.7])
    C = ppAdd(A, B)
    assert C.breaks.tolist() == [0, 1, 2, 4]
    np.testing.assert_allclose(ppEval(C, t), _fA(t) + _fB(t), atol=1e-13)
    C2 = ppAdd(A, 10)
    np.testing.assert_allclose(ppEval(C2, t), _fA(t) + 10, atol=1e-13)
    M = ppMultiply(A, B)
    assert M.breaks.tolist() == [0, 1, 2, 4]
    np.testing.assert_allclose(ppEval(M, t), _fA(t) * _fB(t), atol=1e-12)
    S = ppScale(A, -2)
    np.testing.assert_allclose(ppEval(S, t), -2 * _fA(t), atol=1e-13)
    R = ppRefine(A, [0.5, 3, 5, -1])
    assert R.breaks.tolist() == [0, 0.5, 2, 3, 4]
    np.testing.assert_allclose(ppEval(R, t), _fA(t), atol=1e-13)
    # fusion des points de rupture avec tolérance relative 1e-12·L
    Bn = {"breaks": [0, 2 + 1e-13, 4], "coefs": [1, 2]}
    assert len(ppAdd(A, Bn).breaks) == 3
    assert len(C.coefs) == len(C.breaks) - 1


def test_pp_integral_zero_const():
    A = {"breaks": [0, 2, 4], "coefs": [[1, 0], [-1, 4]]}
    assert ppIntegral(A, 0, 4) == pytest.approx(4, rel=1e-13)
    assert ppIntegral(A) == pytest.approx(4, rel=1e-13)
    assert ppIntegral(A, 1, 3) == pytest.approx(3, rel=1e-13)
    assert ppIntegral(A, 3, 1) == pytest.approx(-3, rel=1e-13)
    np.testing.assert_allclose(ppIntegral(A, [0, 1], [4, 3]), [4, 3], rtol=1e-13)
    Z = ppZero([0, 1, 2])
    assert [c.tolist() for c in Z.coefs] == [[0], [0]]
    np.testing.assert_array_equal(ppEval(Z, [0, 1.5, 2]), [0, 0, 0])
    K = ppConst([0, 1, 2], 3)
    assert ppIntegral(K, 0, 2) == pytest.approx(6, rel=1e-14)
    verifier_erreur(PP_INVALIDE, ppConst, [0, 0, 1], 1)
    verifier_erreur(PP_INVALIDE, ppZero, 1)


def test_poly2latex_poly2str():
    assert poly2latex([-3, 2, -1]) == r"-3\,s^{2} + 2\,s - 1"
    assert poly2latex([1, 0, 0]) == r"s^{2}"
    assert poly2latex([-1, 0, 4]) == r"-s^{2} + 4"
    assert poly2latex([0, 0]) == "0"
    assert poly2latex([]) == "0"
    assert poly2latex([2.5e-5, 0]) == r"2.5 \cdot 10^{-5}\,s"
    assert poly2latex([1, -1], "x") == "x - 1"
    assert poly2latex(12345.678) == r"1.235 \cdot 10^{4}"
    assert poly2latex([1e-20, 1]) == "1"
    assert poly2latex([0, -5000, 0]) == r"-5000\,s"
    assert poly2latex([2, 3], r"\xi") == r"2\,\xi + 3"
    assert poly2str([-1500, 3000, -250]) == "-1500*s^2 + 3000*s - 250"
    # tronçon [9, 10] d'une console : l'équation imprimée doit redonner M(10) = 0 (termes qui se compensent)
    c = [-617.3, 12346, -61730]
    assert eval(poly2str(c).replace("^", "**"), {"s": 10.0}) == pytest.approx(0, abs=1e-6)
    assert poly2str([0.5, -2, 0]) == "0.5*s^2 - 2*s"
    assert poly2str([1, 0], "x") == "x"
    assert poly2str(0) == "0"
    assert poly2str(-0.25) == "-0.25"
    for cas in ([1, -2, 3, -4], [-1, -1, -1], [3, 0, -2, 0, 1], [-7.5, 1e-3]):
        assert "+ -" not in poly2latex(cas)
        assert "+ -" not in poly2str(cas)


def test_has_symbolic():
    tf = hasSymbolic()
    assert isinstance(tf, bool)
    assert tf == (importlib.util.find_spec("sympy") is not None)


def test_aides_privees():
    # (s - 2)² = s² - 4s + 4
    np.testing.assert_allclose(_shiftPoly([1, 0, 0], 2), [1, -4, 4])
    assert _mergeBreaks([3, 0, 1, 1 + 1e-14]).tolist() == [0, 1, 3]
    assert _texNum(2.5e-5) == r"2.5 \cdot 10^{-5}"
    assert _texNum(np.inf) == r"\infty"
    assert _num(-0.0) == "0"
