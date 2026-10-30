"""Tests des graphiques Poutres : figures valides, sérialisables, données tracées conformes aux moteurs."""

import plotly.graph_objects as go
import pytest

from mecastruct.core.data_manager import DataManager
from mecastruct.plots.beam_plots import beamSchematic, deflection, internalForces, movingEnvelope
from mecastruct.services.beam_design import computeMovingLoad
from mecastruct.services.beam_services import computeBeam, defaultBeamInput
from mecastruct.services.examples import loadExample

# isostatique, hyperstatique, et isostatique tracé dans le plan xz (flèche et rotation en w et β)
CAS = [("isostatique", "xy"), ("hyperstatique", "xy"), ("isostatique", "xz")]


@pytest.fixture(scope="module")
def dm():
    return DataManager()


@pytest.fixture(scope="module")
def calcul(dm):
    """Calcul complet (computeBeam) de chaque cas, indexé par (variante, plan)."""
    resultats = {}
    for variante, plane in CAS:
        saisie = loadExample("Beam", variante)
        saisie["plane"] = plane
        resultats[(variante, plane)] = computeBeam(saisie, dm)
    return resultats


@pytest.mark.parametrize("cas", CAS)
def test_schema_renvoie_une_figure(calcul, cas):
    r = calcul[cas]
    fig = beamSchematic(r["model"], r["sol"])
    assert isinstance(fig, go.Figure)
    assert fig.to_json()


def test_schema_sans_resultat(calcul):
    fig = beamSchematic(calcul[CAS[0]]["model"])
    assert isinstance(fig, go.Figure)


def test_schema_refuse_longueur_nulle():
    with pytest.raises(Exception, match="model.L"):
        beamSchematic({"L": 0.0, "supports": []})


@pytest.mark.parametrize("cas", CAS)
def test_efforts_un_sous_graphe_par_composante(calcul, cas):
    fig = internalForces(calcul[cas]["sol"], ["Ty", "Mfz"])
    assert isinstance(fig, go.Figure)
    assert len([k for k in fig.layout if k.startswith("yaxis")]) == 2
    assert fig.to_json()


@pytest.mark.parametrize("cas", CAS)
def test_efforts_maximum_du_moment(calcul, cas):
    sol = calcul[cas]["sol"]
    fig = internalForces(sol, ["Mfz"])
    courbe = next(t for t in fig.data if t.name == "Diagramme")
    assert max(courbe.y) == pytest.approx(sol["extrema"]["Mfz"]["max"] / 1e3, rel=1e-9)


@pytest.mark.parametrize("cas", CAS)
def test_deflexion_serialisable(calcul, cas):
    r = calcul[cas]
    fig = deflection(r["model"], r["defl"])
    assert isinstance(fig, go.Figure)
    assert fig.to_json()


def test_enveloppe_charge_mobile(dm):
    T, env = computeMovingLoad(defaultBeamInput(), dm)
    fig = movingEnvelope(env)
    assert isinstance(fig, go.Figure)
    assert len(T) > 0
    assert fig.to_json()
