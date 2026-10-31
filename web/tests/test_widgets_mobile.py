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
