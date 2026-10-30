"""Tests de geometry (étape E06, première moitié) : portage des tests testFirstMoment*, testWidthAt, testPrimitives,
testOutline, testTypeAliases et testErrors de tests/test_GeometryEngine.m, et golden widthAt / firstMomentAbove.

Les tests qui passent par analytical, integral ou shearFactors (testReportFormat, testErrors pour integral) sont
portés à l'étape E07, quand ces fonctions existent.
"""

import math

import numpy as np
import pytest
from scipy.integrate import quad

from mecastruct.core import geometry as geo
from mecastruct.core.errors import MecaStructError
from tests.golden_tools import assert_matches, case_ids, get_case

ID = "MecaStruct:GeometryEngine:"

IPE200 = {
    "type": "profile",
    "family": "IPE",
    "name": "IPE 200",
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
UPN200 = {
    "type": "profile",
    "family": "UPN",
    "name": "UPN 200",
    "h": 0.2,
    "b": 0.075,
    "a": 0.0085,
    "e": 0.0115,
    "r": 0.0115,
    "S": 32.2e-4,
    "Iz": 1910e-8,
    "Iy": 148e-8,
    "Wz": 191e-6,
    "Wy": 27e-6,
    "rz": 0.077,
    "ry": 0.0214,
    "mass": 25.3,
    "c": 0.0201,
}

# Jeu de sections couvrant tous les types (dimensions en m), comme allSections de MATLAB
SECTIONS = [
    ("rectangle", {"type": "rectangle", "b": 0.1, "h": 0.2}),
    ("disque", {"type": "disque", "D": 0.1}),
    ("couronne", {"type": "couronne", "D": 0.1, "d": 0.08}),
    ("rectangle_creux", {"type": "rectangle_creux", "B": 0.1, "H": 0.2, "t": 0.01}),
    ("I", {"type": "I", "h": 0.2, "b": 0.1, "tw": 0.0056, "tf": 0.0085}),
    ("T", {"type": "T", "h": 0.1, "b": 0.08, "tw": 0.008, "tf": 0.01}),
    ("U", {"type": "U", "h": 0.2, "b": 0.075, "tw": 0.0085, "tf": 0.0115}),
    ("L_egal", {"type": "L", "h": 0.1, "b": 0.1, "t": 0.01}),
    ("L_inegal", {"type": "L", "h": 0.12, "b": 0.08, "t": 0.012}),
    ("profile_IPE200", IPE200),
    ("profile_UPN200", UPN200),
    (
        "composite_trou",
        {
            "type": "composite",
            "rects": [[0, 0.2, 0, 0.02], [0.09, 0.11, 0.02, 0.2]],
            "holes": [[0.02, 0.05, 0.005, 0.015]],
        },
    ),
    (
        "composite_trou_circulaire",
        {"type": "composite", "rects": [[0, 0.2, 0, 0.1]], "diskHoles": [[0.13, 0.04, 0.025]]},
    ),
    ("composite_disque", {"type": "composite", "rects": [[-0.05, 0.05, -0.1, 0]], "disks": [[0, 0.03, 0.03]]}),
]


def _verifRel(actual, expected, tol: float) -> None:
    """Écart relatif maximal, absolu si la valeur attendue est nulle (comme verifyRel de MATLAB)."""
    a, e = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    err = np.abs(a - e) / np.maximum(np.abs(e), np.finfo(float).tiny)
    err = np.where(e == 0, np.abs(a), err)
    assert err.max() <= tol


def _erreur(identifiant: str, appel, *args) -> None:
    """Vérifie que l'appel lève une MecaStructError portant l'identifiant attendu."""
    with pytest.raises(MecaStructError) as info:
        appel(*args)
    assert info.value.identifier == identifiant


# -------------------------------------------------------------------------------------
#  Moments statiques Q(y)
# -------------------------------------------------------------------------------------


def test_first_moment_rectangle():
    b, h = 0.1, 0.2
    sec = {"type": "rectangle", "b": b, "h": h}
    _verifRel(geo.firstMomentAbove(sec, 0), b * h**2 / 8, 1e-12)
    y = np.linspace(-h / 2, h / 2, 41)
    Q = geo.firstMomentAbove(sec, y)
    assert Q.shape == y.shape
    assert np.max(np.abs(Q - b / 2 * (h**2 / 4 - y**2))) <= 1e-12 * b * h**2 / 8
    np.testing.assert_array_equal(geo.firstMomentAbove(sec, np.array([-0.3, 0.3])), [0, 0])
    Ym = np.array([[0, 0.05], [-0.05, 0.02]])
    Qm = geo.firstMomentAbove(sec, Ym)
    assert Qm.shape == (2, 2)
    _verifRel(Qm, b / 2 * (h**2 / 4 - Ym**2), 1e-12)


def test_first_moment_disque():
    D = 0.1
    R = D / 2
    sec = {"type": "disque", "D": D}
    y = np.linspace(-R, R, 51)
    Q = geo.firstMomentAbove(sec, y)
    assert np.max(np.abs(Q - 2 / 3 * (R**2 - y**2) ** 1.5)) <= 1e-12 * R**3
    _verifRel(geo.firstMomentAbove(sec, 0), 2 / 3 * R**3, 1e-12)


def test_first_moment_couronne():
    D, d = 0.1, 0.06
    R, r = D / 2, d / 2
    sec = {"type": "couronne", "D": D, "d": d}
    _verifRel(geo.firstMomentAbove(sec, 0), 2 / 3 * (R**3 - r**3), 1e-12)
    _verifRel(geo.firstMomentAbove(sec, 0.04), 2 / 3 * (R**2 - 0.04**2) ** 1.5, 1e-12)
    _verifRel(geo.firstMomentAbove(sec, 0.01), 2 / 3 * ((R**2 - 0.01**2) ** 1.5 - (r**2 - 0.01**2) ** 1.5), 1e-12)


def test_first_moment_i_symmetric():
    h, b, tw, tf = 0.2, 0.1, 0.0056, 0.0085
    sec = {"type": "I", "h": h, "b": b, "tw": tw, "tf": tf}
    Q0 = b * tf * (h / 2 - tf / 2) + tw * (h / 2 - tf) ** 2 / 2
    _verifRel(geo.firstMomentAbove(sec, 0), Q0, 1e-12)
    yf = h / 2 - tf / 3  # dans l'aile supérieure
    _verifRel(geo.firstMomentAbove(sec, yf), b / 2 * (h**2 / 4 - yf**2), 1e-12)
    yw = 0.05  # dans l'âme
    _verifRel(geo.firstMomentAbove(sec, yw), b * tf * (h / 2 - tf / 2) + tw / 2 * ((h / 2 - tf) ** 2 - yw**2), 1e-12)
    y = np.linspace(-h / 2, h / 2, 37)
    dsym = geo.firstMomentAbove(sec, -y) - geo.firstMomentAbove(sec, y)
    assert np.max(np.abs(dsym)) <= 1e-12 * Q0
    np.testing.assert_array_equal(geo.firstMomentAbove(sec, np.array([-h / 2, h / 2])), [0, 0])


@pytest.mark.parametrize("nom, sec", SECTIONS, ids=[n for n, _ in SECTIONS])
def test_first_moment_derivative_consistency(nom, sec):
    # dQ/dy = -y b(y) (où b est continue), Q nul aux fibres extrêmes, Q(0) = intégrale de b(t)·t sur [0, vyTop]
    prims = geo.primitives(sec)
    yG = geo._huygensCore(prims)["yG"]
    bb = geo._bboxPrims(prims)
    vyTop, vyBot = bb[3] - yG, yG - bb[2]
    yv = np.linspace(-vyBot, vyTop, 157)
    yv = yv[1:-1] + 1e-4 * (vyTop + vyBot) * 0.37
    yv = yv[yv < vyTop]
    hstep = 1e-7 * (vyTop + vyBot)
    dQ = (geo.firstMomentAbove(sec, yv + hstep) - geo.firstMomentAbove(sec, yv - hstep)) / (2 * hstep)
    bL = geo.widthAt(sec, yv - hstep, "dessous")
    bR = geo.widthAt(sec, yv + hstep, "dessus")
    smooth = np.abs(bL - bR) <= 1e-9 * np.max(bL + bR)
    ref = -yv * geo.widthAt(sec, yv)
    scale = np.max(np.abs(ref)) + np.finfo(float).eps
    assert np.max(np.abs(dQ[smooth] - ref[smooth])) / scale <= 1e-5
    assert abs(geo.firstMomentAbove(sec, -vyBot)) <= 1e-15
    assert abs(geo.firstMomentAbove(sec, vyTop)) <= 1e-15
    Qint, _ = quad(
        lambda t: geo.widthAt(sec, t) * t,
        0,
        vyTop,
        points=[0.25 * vyTop, 0.5 * vyTop, 0.75 * vyTop],
        epsabs=0,
        epsrel=1e-10,
        limit=500,
    )
    _verifRel(geo.firstMomentAbove(sec, 0), Qint, 1e-6)


# -------------------------------------------------------------------------------------
#  Largeurs b(y)
# -------------------------------------------------------------------------------------


def test_width_at():
    b, h = 0.1, 0.2
    rect = {"type": "rectangle", "b": b, "h": h}
    np.testing.assert_array_equal(geo.widthAt(rect, np.array([-0.05, 0, 0.05])), [b, b, b])
    np.testing.assert_array_equal(geo.widthAt(rect, np.array([-0.2, 0.2])), [0, 0])
    assert geo.widthAt(rect, h / 2) == b
    assert geo.widthAt(rect, h / 2, "dessus") == 0
    assert geo.widthAt(rect, h / 2, "dessous") == b
    D = 0.1
    R = D / 2
    y = np.linspace(-R, R, 21)
    bw = geo.widthAt({"type": "disque", "D": D}, y)
    assert bw.shape == y.shape
    assert np.max(np.abs(bw - 2 * np.sqrt(R**2 - y**2))) <= 1e-12 * D
    _verifRel(geo.widthAt({"type": "couronne", "D": 0.1, "d": 0.06}, 0), 0.04, 1e-12)
    creux = {"type": "rectangle_creux", "B": 0.1, "H": 0.2, "t": 0.01}
    _verifRel(geo.widthAt(creux, np.array([0, 0.095])), [0.02, 0.1], 1e-12)
    hI, bI, tw, tf = 0.2, 0.1, 0.0056, 0.0085
    sI = {"type": "I", "h": hI, "b": bI, "tw": tw, "tf": tf}
    _verifRel(geo.widthAt(sI, np.array([0, 0.05, -0.05])), [tw, tw, tw], 1e-12)
    _verifRel(geo.widthAt(sI, np.array([hI / 2 - tf / 2, -hI / 2 + tf / 2])), [bI, bI], 1e-12)
    yj = hI / 2 - tf  # jonction âme / aile supérieure
    _verifRel(geo.widthAt(sI, yj), bI, 1e-12)
    _verifRel(geo.widthAt(sI, yj, "below"), tw, 1e-12)
    _verifRel(geo.widthAt(sI, yj, "above"), bI, 1e-12)
    _verifRel(geo.widthAt(sI, -yj, "dessous"), bI, 1e-12)
    _verifRel(geo.widthAt(sI, -yj, "dessus"), tw, 1e-12)
    _verifRel(geo.widthAt(sI, yj * (1 + 1e-14), "dessous"), tw, 1e-12)  # recalage des erreurs d'arrondi
    assert math.isnan(geo.widthAt(sI, math.nan))


# -------------------------------------------------------------------------------------
#  Primitives, contours, types, erreurs
# -------------------------------------------------------------------------------------


def test_primitives():
    pr = geo.primitives({"type": "I", "h": 0.2, "b": 0.1, "tw": 0.0056, "tf": 0.0085})
    assert len(pr) == 3
    cles = {"kind", "sign", "z1", "z2", "y1", "y2", "zc", "yc", "R", "Ri", "label"}
    assert all(cles <= p.keys() for p in pr)
    assert [p["kind"] for p in pr] == ["rect", "rect", "rect"]
    assert pr[2]["label"] == "Aile supérieure"
    np.testing.assert_allclose(
        [pr[1][k] for k in ("z1", "z2", "y1", "y2")], [0.0472, 0.0528, 0.0085, 0.1915], atol=1e-15
    )
    pc = geo.primitives({"type": "couronne", "D": 0.1, "d": 0.06})
    assert len(pc) == 1 and pc[0]["kind"] == "annulus"
    np.testing.assert_allclose([pc[0][k] for k in ("zc", "yc", "R", "Ri", "sign")], [0.05, 0.05, 0.05, 0.03, 1])
    ph = geo.primitives({"type": "rectangle_creux", "B": 0.1, "H": 0.2, "t": 0.01})
    assert [p["sign"] for p in ph] == [1, -1]


@pytest.mark.parametrize("nom, sec", SECTIONS, ids=[n for n, _ in SECTIONS])
def test_outline(nom, sec):
    out = geo.outline(sec)
    prims = geo._buildPrims(geo.validateSection(sec))
    S = geo._huygensCore(prims)["S"]
    assert out["outer"] and isinstance(out["holes"], list)
    courbe = sec["type"] in ("disque", "couronne") or (
        sec["type"] == "composite" and ("disks" in sec or "diskHoles" in sec)
    )
    A = 0.0
    for p in out["outer"] + out["holes"]:
        assert p.shape[1] == 2
        np.testing.assert_array_equal(p[0], p[-1])
    for p in out["outer"]:
        a = 0.5 * np.sum(p[:-1, 0] * p[1:, 1] - p[1:, 0] * p[:-1, 1])
        assert a > 0  # contour extérieur en sens trigonométrique
        A += a
    for p in out["holes"]:
        a = 0.5 * np.sum(p[:-1, 0] * p[1:, 1] - p[1:, 0] * p[:-1, 1])
        assert a < 0  # trou en sens horaire
        A += a
    _verifRel(A, S, 1e-3 if courbe else 1e-12)
    np.testing.assert_allclose(out["bbox"], geo._bboxPrims(prims), atol=1e-15)


def test_outline_details():
    outD = geo.outline({"type": "disque", "D": 0.1})
    assert len(outD["outer"][0]) >= 121
    outC = geo.outline({"type": "couronne", "D": 0.1, "d": 0.06})
    assert len(outC["holes"]) == 1 and len(outC["holes"][0]) >= 121
    r = np.hypot(outC["holes"][0][:, 0] - 0.05, outC["holes"][0][:, 1] - 0.05)
    np.testing.assert_allclose(r, 0.03, atol=1e-15)
    outI = geo.outline({"type": "I", "h": 0.2, "b": 0.1, "tw": 0.0056, "tf": 0.0085})
    assert len(outI["outer"][0]) == 13 and outI["holes"] == []
    outCo = geo.outline({"type": "composite", "rects": [[0, 0.1, 0, 0.2]], "holes": [[0.02, 0.04, 0.02, 0.06]]})
    assert len(outCo["outer"]) == 1 and len(outCo["holes"]) == 1


def test_type_aliases():
    s1 = geo.validateSection({"type": "Rectangle", "b": 0.1, "h": 0.2})
    s2 = geo.validateSection({"type": "rectangle", "b": 0.1, "h": 0.2})
    assert s1["type"] == s2["type"] == "rectangle"
    assert geo.validateSection({"type": "i", "h": 0.2, "b": 0.1, "tw": 0.0056, "tf": 0.0085})["type"] == "I"
    types = geo.sectionTypes()
    assert len(types) == 10
    assert all({"type", "label", "fields", "origin"} <= t.keys() for t in types)


def test_erreurs_validation():
    _erreur(ID + "unknownType", geo.validateSection, {"type": "hexagone"})
    _erreur(ID + "missingField", geo.validateSection, {"b": 0.1})
    _erreur(ID + "invalidInput", geo.validateSection, 42)
    _erreur(ID + "missingField", geo.validateSection, {"type": "rectangle", "b": 0.1})
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "rectangle", "b": -0.1, "h": 0.2})
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "couronne", "D": 0.1, "d": 0.1})
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "I", "h": 0.2, "b": 0.1, "tw": 0.005, "tf": 0.1})
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "U", "h": 0.2, "b": 0.01, "tw": 0.01, "tf": 0.01})
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "L", "h": 0.1, "b": 0.05, "t": 0.05})
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "rectangle_creux", "B": 0.1, "H": 0.2, "t": 0.05})
    _erreur(ID + "overlap", geo.validateSection, {"type": "composite", "rects": [[0, 1, 0, 1], [0.5, 2, 0.5, 2]]})
    _erreur(
        ID + "holeOutside",
        geo.validateSection,
        {"type": "composite", "rects": [[0, 1, 0, 1]], "holes": [[0.5, 1.5, 0.2, 0.4]]},
    )
    _erreur(
        ID + "overlap",
        geo.validateSection,
        {"type": "composite", "rects": [[0, 1, 0, 1]], "holes": [[0.1, 0.5, 0.1, 0.5], [0.3, 0.6, 0.3, 0.6]]},
    )
    _erreur(
        ID + "holeOutside",
        geo.validateSection,
        {"type": "composite", "rects": [[0, 1, 0, 1]], "diskHoles": [[0.9, 0.5, 0.2]]},
    )
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "composite", "rects": [[0, 1, 1, 0]]})
    _erreur(ID + "invalidDimensions", geo.validateSection, {"type": "composite", "rects": [[0, 1, 0]]})
    _erreur(
        ID + "overlap", geo.validateSection, {"type": "composite", "rects": [[0, 1, 0, 1]], "disks": [[1.2, 0.5, 0.3]]}
    )
    _erreur(ID + "invalidInput", geo.widthAt, {"type": "rectangle", "b": 0.1, "h": 0.2}, 0, "gauche")
    _erreur(ID + "invalidInput", geo.firstMomentAbove, {"type": "rectangle", "b": 0.1, "h": 0.2}, "a")


def test_huygens_rectangle():
    b, h = 0.1, 0.2
    core = geo._huygensCore(geo.primitives({"type": "rectangle", "b": b, "h": h}))
    assert core["S"] == pytest.approx(0.02)
    assert core["yG"] == pytest.approx(0.1)
    assert core["Iz"] == pytest.approx(b * h**3 / 12)
    assert core["Iy"] == pytest.approx(h * b**3 / 12)
    assert core["Iyz"] == 0


@pytest.mark.parametrize("nom, sec", SECTIONS[:4], ids=[n for n, _ in SECTIONS[:4]])
def test_formules_fermees_concordent_avec_huygens(nom, sec):
    # formules fermées des sections élémentaires = décomposition de Huygens (même S, Iz, Iy)
    sec = geo.validateSection(sec)
    core = geo._huygensCore(geo._buildPrims(sec))
    fermee, rep, tex = geo._closedForm(sec, core)
    assert rep and tex
    for cle in ("S", "Iz", "Iy"):
        _verifRel(fermee[cle], core[cle], 1e-12)


@pytest.mark.parametrize("nom, sec", SECTIONS, ids=[n for n, _ in SECTIONS])
def test_rapports_et_torsion_sans_erreur(nom, sec):
    # textes du rapport et constante de torsion : valeurs et formes sans erreur pour tous les types
    sec = geo.validateSection(sec)
    prims = geo._buildPrims(sec)
    core = geo._huygensCore(prims)
    rep, tex = geo._huygensText(core)
    assert rep and tex and all(isinstance(t, str) for t in rep + tex)
    J, txt, latex = geo._torsionConstant(sec, prims)
    assert isinstance(txt, str) and isinstance(latex, str)


def test_saint_venant_carre_et_texnum():
    # rectangle carré : J = β·a⁴ avec β ≈ 0,1406 (valeur classique)
    J, _, _ = geo._saintVenant(0.1, 0.1)
    assert J / 0.1**4 == pytest.approx(0.1406, rel=1e-3)
    assert geo._texNum(1e5) == "10^{5}"
    assert geo._texNum(1.5e-7) == r"1.5 \times 10^{-7}"
    assert geo._texNum(-1e-7) == "-10^{-7}"


# -------------------------------------------------------------------------------------
#  Golden files (MATLAB) : widthAt et firstMomentAbove
# -------------------------------------------------------------------------------------


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_widthAt"))
def test_golden_width_at(cid):
    c = get_case("golden_geometry.json", cid)
    e = c["entrees"]
    assert_matches(geo.widthAt(e["sec"], e["y"]), c["sortie"], rel=1e-9)


@pytest.mark.parametrize("cid", case_ids("golden_geometry.json", suffix="_firstMomentAbove"))
def test_golden_first_moment_above(cid):
    c = get_case("golden_geometry.json", cid)
    e = c["entrees"]
    assert_matches(geo.firstMomentAbove(e["sec"], e["y"]), c["sortie"], rel=1e-9)
