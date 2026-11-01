"""Contraste élevé des graphiques : traits épaissis, aires plus opaques, bord d'aire (largeur 0) inchangé."""

from pathlib import Path

import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest

from mecastruct.ui import widgets

PAGE = str(Path(__file__).resolve().parents[1] / "app_pages" / "poutres.py")


def test_renforce():
    fig = go.Figure(
        [
            go.Scatter(y=[0, 1], line={"width": 1.8}),
            go.Scatter(y=[0, 1], fill="tozeroy", line={"width": 0}, fillcolor="rgba(0,115,189,0.3)"),
        ]
    )
    widgets._renforce(fig)
    assert fig.data[0].line.width == 3.24
    assert fig.data[1].line.width == 0 and fig.data[1].fillcolor == "rgba(0,115,189,0.6)"


def test_page_poutres_en_contraste_eleve():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.session_state["vue"] = "pc"
    at.session_state["contraste"] = True
    at.run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    assert not at.exception
