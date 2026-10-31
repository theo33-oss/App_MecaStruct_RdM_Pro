"""Réglages Plotly selon le terminal : mobile (sans barre d'outils ni zoom, moins haut) et ordinateur."""

import plotly.graph_objects as go
import pytest

from mecastruct.ui import widgets


@pytest.fixture
def appels(monkeypatch):
    liste = []
    monkeypatch.setattr(widgets.st, "plotly_chart", lambda fig, **kw: liste.append((fig, kw)))
    return liste


def _figure() -> go.Figure:
    fig = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))
    fig.update_layout(height=600)
    return fig


def test_plot_mobile(monkeypatch, appels):
    monkeypatch.setattr(widgets, "is_compact", lambda: True)
    fig = _figure()
    widgets.plot(fig)
    config = appels[0][1]["config"]
    assert config["displayModeBar"] is False and config["scrollZoom"] is False
    assert fig.layout.height == 450 and fig.layout.dragmode is False and fig.layout.xaxis.fixedrange


def test_plot_ordinateur(monkeypatch, appels):
    monkeypatch.setattr(widgets, "is_compact", lambda: False)
    fig = _figure()
    widgets.plot(fig)
    assert appels[0][1]["config"]["displaylogo"] is False
    assert fig.layout.height == 600 and fig.layout.dragmode is None


def test_is_compact_hors_session_est_faux():
    assert widgets.is_compact() is False


@pytest.fixture
def metriques(monkeypatch):
    liste = []
    monkeypatch.setattr(widgets, "synthese", liste.extend)
    return liste


def test_synthese_statut_valeurs_et_verdict(metriques):
    widgets.synthese_statut("σI = 87.08 MPa, σIII = -47.08 MPa — VM = 116.2 MPa (vérifié)")
    assert [(v["label"], v["value"]) for v in metriques] == [
        ("σI", "87.08 MPa"),
        ("σIII", "-47.08 MPa"),
        ("VM", "116.2 MPa"),
    ]
    assert metriques[2]["delta"] == "vérifié" and metriques[2]["delta_color"] == "green"
    assert "delta" not in metriques[0]


def test_synthese_statut_verdict_apres_deux_points_et_note_neutre(metriques):
    widgets.synthese_statut("h = 0 (isostatique) — P = 12.5 kN : NON vérifié")
    assert metriques[0]["delta"] == "isostatique" and metriques[0]["delta_color"] == "off"
    assert metriques[1]["value"] == "12.5 kN" and metriques[1]["delta_color"] == "red"


def test_synthese_statut_texte_libre_sans_metrique(metriques):
    widgets.synthese_statut("Clavette : longueur minimale Lmin = 41.2 mm")
    assert [v["label"] for v in metriques] == []


def test_interrupteur_mode_compact_prime_sur_le_user_agent(monkeypatch):
    monkeypatch.setattr(widgets, "agent_mobile", lambda: True)
    monkeypatch.setattr(widgets.st, "session_state", {"mode_compact": False})
    assert widgets.is_compact() is False
    monkeypatch.setattr(widgets.st, "session_state", {})
    assert widgets.is_compact() is True


def test_plot_theme_sombre_garde_une_carte_claire(monkeypatch, appels):
    monkeypatch.setattr(widgets, "is_compact", lambda: False)
    monkeypatch.setattr(widgets, "_theme_sombre", lambda: True)
    fig = _figure()
    widgets.plot(fig)
    assert fig.layout.paper_bgcolor == "white" and appels[0][1]["theme"] is None
