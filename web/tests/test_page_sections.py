"""Tests de la page « Sections » (AppTest) : exécution, rectangle par défaut, exemple IPE, section composée."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PAGE = str(Path(__file__).resolve().parents[1] / "app_pages" / "sections.py")


def _bouton(at: AppTest, libelle: str):
    """Bouton de la page dont le libellé est `libelle`."""
    return next(b for b in at.button if b.label == libelle)


def test_page_s_execute():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception


def test_rectangle_par_defaut_iz():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.selectbox(key="Sec.type").set_value("rectangle").run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    res = at.session_state["res"]["Sec"]["result"]
    b, h = 0.100, 0.200  # dimensions par défaut en m (100 mm × 200 mm)
    assert res["P"]["Iz"] == pytest.approx(b * h**3 / 12, rel=1e-9)


def test_exemple_ipe_puis_calcul():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Charger l'exemple").click().run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    assert "Sec" in at.session_state["res"]
    assert at.session_state["saisie"]["Sec"]["prof"] == "IPE 200"


def test_section_composee_calcule():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.selectbox(key="Sec.type").set_value("composite").run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    assert at.session_state["res"]["Sec"]["result"]["sec"]["type"] == "composite"
