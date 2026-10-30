"""Tests des graphiques de section et des autres graphiques : figures valides, sérialisables, données tracées conformes
aux moteurs (contour, rayon du cercle de Mohr, courbes de plasticité, treillis 2D et 3D, abaques Kt)."""

import re

import numpy as np
import plotly.graph_objects as go
import pytest

from mecastruct.core import geometry, kt_mohr
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.plots.other_plots import bucklingCurve, ktChart, mohr2D, mohr3D, truss, yieldLocus
from mecastruct.plots.section_plots import section, sectionStress
from mecastruct.services import compute
from mecastruct.services.examples import loadExample


@pytest.fixture(scope="module")
def dm():
    return DataManager()


@pytest.fixture(scope="module")
def section_calcul(dm):
    """Calcul de section d'exemple (computeSection) : sec, P, bend, jour."""
    return compute.computeSection(loadExample("Sec"), dm)["result"]


@pytest.fixture(scope="module")
def flambage(dm):
    return compute.computeBuckling(compute.defaultBucklingInput(), dm)["result"]


@pytest.fixture(scope="module")
def contraintes(dm):
    return compute.computeTensor(compute.defaultTensorInput(), dm)["result"]


@pytest.fixture(scope="module")
def treillis(dm):
    return compute.computeTruss(compute.defaultTrussInput(), dm)["result"]


def _trace(fig: go.Figure, nom: str) -> go.Scatter:
    """Premier tracé dont le nom commence par `nom` (erreur explicite si absent)."""
    for t in fig.data:
        if t.name and t.name.startswith(nom):
            return t
    raise AssertionError(f"aucun tracé nommé « {nom} »")


def _premier_sommet(chemin: str) -> tuple[float, float]:
    """Premier couple (x, y) d'un chemin SVG « M x,y L … » tracé par polyShape."""
    x, y = re.findall(r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?", chemin)[:2]
    return float(x), float(y)


# ---------- section_plots ----------


def test_section_contour_matches_outline(section_calcul):
    sec, P = section_calcul["sec"], section_calcul["P"]
    fig = section(sec, P)
    assert isinstance(fig, go.Figure)
    contour = geometry.outline(sec)["outer"][0]
    z, y = _premier_sommet(fig.layout.shapes[0].path)
    assert z == pytest.approx(contour[0, 0] * 1e3, rel=1e-8, abs=1e-9)
    assert y == pytest.approx(contour[0, 1] * 1e3, rel=1e-8, abs=1e-9)
    fig.to_json()


def test_section_sans_proprietes_calcule_analytical(section_calcul):
    fig = section(section_calcul["sec"])
    assert isinstance(fig, go.Figure)
    assert fig.layout.yaxis.scaleanchor == "x"
    fig.to_json()


def test_section_stress_deux_sous_graphes(section_calcul):
    fig = sectionStress(section_calcul["sec"], section_calcul["P"], section_calcul["bend"], section_calcul["jour"])
    assert isinstance(fig, go.Figure)
    assert "xaxis2" in fig.layout
    # le tracé de τ(y) reprend le profil de Jourawski (en MPa)
    tau = _trace(fig, "Jourawski")
    assert np.allclose(tau.x, np.asarray(section_calcul["jour"]["tau"]).ravel() / 1e6)
    fig.to_json()


def test_section_stress_sans_resultat(section_calcul):
    fig = sectionStress(section_calcul["sec"], section_calcul["P"], None, None)
    assert isinstance(fig, go.Figure)
    fig.to_json()


# ---------- other_plots : flambage ----------


@pytest.mark.parametrize("avec_analyse", [True, False])
def test_buckling_curve(flambage, avec_analyse):
    fig = bucklingCurve(flambage["curve"], flambage["analysis"] if avec_analyse else None)
    assert isinstance(fig, go.Figure)
    design = _trace(fig, "Dimensionnement")
    assert np.isfinite(np.asarray(design.y, dtype=float)).any()
    fig.to_json()


def test_buckling_curve_point_critique(flambage):
    fig = bucklingCurve(flambage["curve"], flambage["analysis"])
    point = _trace(fig, "Point critique")
    b = flambage["analysis"]
    assert point.x[0] == pytest.approx(b["lambda"])
    assert point.y[0] == pytest.approx(b["Pcrit"] / b["S"] / 1e6)


# ---------- other_plots : Mohr ----------


def test_mohr2D_rayon_du_cercle(contraintes):
    r2D = contraintes["plane2D"]
    fig = mohr2D(r2D)
    cercle = _trace(fig, "Cercle de Mohr")
    x, y = np.asarray(cercle.x), np.asarray(cercle.y)
    centre = r2D["delta"] * 1e-6
    assert np.hypot(x - centre, y).max() == pytest.approx(r2D["rho"] * 1e-6, rel=1e-9)
    fig.to_json()


def test_mohr2D_facette_et_deformations(contraintes):
    fig = mohr2D(contraintes["plane2D"], 0.4)
    assert any(t.name and t.name.startswith("Facette") for t in fig.data)
    fig.to_json()
    deformations = dict(contraintes["plane2D"])
    deformations["kind"] = "strain"
    fig_eps = mohr2D(deformations)
    assert "µdéf" in fig_eps.layout.xaxis.title.text
    fig_eps.to_json()


def test_mohr3D_cercles_et_zone(contraintes):
    m3 = contraintes["mohr3D"]
    fig = mohr3D(m3, [1e6, 2e6])
    assert isinstance(fig, go.Figure)
    for j, nom in enumerate(["(σ<sub>I</sub>, σ<sub>II</sub>)", "(σ<sub>II</sub>, σ<sub>III</sub>)"]):
        cercle = _trace(fig, f"Cercle {nom}")
        rayon = np.hypot(np.asarray(cercle.x) - m3["centers"][j] * 1e-6, np.asarray(cercle.y)).max()
        assert rayon == pytest.approx(m3["radii"][j] * 1e-6, rel=1e-9)
    fig.to_json()


def test_yield_locus_polygones(contraintes):
    loci = contraintes["loci"]
    fig = yieldLocus(loci, [1e6, 2e6])
    tresca = _trace(fig, "Tresca")
    assert np.allclose(np.column_stack([tresca.x, tresca.y]), np.asarray(loci["tresca"]) * 1e-6)
    assert any(t.name and t.name.startswith("État de contrainte") for t in fig.data)
    fig.to_json()


# ---------- other_plots : treillis ----------


def test_truss_2d(treillis):
    fig = truss(treillis["truss"], treillis["tsol"])
    assert isinstance(fig, go.Figure)
    assert any(t.name == "Traction" or t.name == "Compression" for t in fig.data)
    fig.to_json()


def test_truss_sans_resultat(treillis):
    fig = truss(treillis["truss"])
    assert isinstance(fig, go.Figure)
    fig.to_json()


def test_truss_3d_tetraedre():
    modele = {
        "nodes": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
        "bars": [[1, 2], [1, 3], [1, 4], [2, 3], [2, 4], [3, 4]],
        "supports": [[1, 1, 1], [0, 0, 1], [0, 0, 0], [0, 0, 0]],
        "loads": [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, -1000]],
    }
    fig = truss(modele)
    assert sum(isinstance(t, go.Scatter3d) for t in fig.data) >= 6
    fig.to_json()


# ---------- other_plots : abaques Kt ----------


@pytest.mark.parametrize("identifiant", [c["id"] for c in kt_mohr.ktCharts()])
def test_kt_chart_tous_les_abaques(identifiant):
    chart = next(c for c in kt_mohr.ktCharts() if c["id"] == identifiant)
    fig = ktChart(identifiant)
    attendu = 1 if not chart["curves"] else len(chart["curves"])
    assert len(fig.data) == attendu
    fig.to_json()


def test_kt_chart_courbe_plaque_egale_evalKt():
    fig = ktChart("plaque_trou_traction")
    x = np.asarray(fig.data[0].x)
    assert np.allclose(fig.data[0].y, kt_mohr.evalKt("plaque_trou_traction", x))


def test_kt_chart_identifiant_inconnu():
    with pytest.raises(MecaStructError) as info:
        ktChart("inconnu")
    assert info.value.identifier == "MecaStruct:PlotEngine:unknownKt"
