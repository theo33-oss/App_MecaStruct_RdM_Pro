"""Tests de la page « Poutres » (AppTest) : exécution, exemple isostatique, cas du README."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PAGE = str(Path(__file__).resolve().parents[1] / "app_pages" / "poutres.py")


def _bouton(at: AppTest, libelle: str):
    """Bouton de la page dont le libellé est `libelle`."""
    return next(b for b in at.button if b.label == libelle)


def test_page_p_execute():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception


def test_exemple_isostatique_puis_calcul():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Charger l'exemple").click().run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    res = at.session_state["res"]["Beam"]
    assert res["sol"]["extrema"]["Mfz"]["max"] > 0
    assert not res["unreliable"]


def test_cas_readme_en_widgets():
    """IPE 200, L = 4 m, 10 kN/m, sans tranchant : flèche 9,029 mm et Mfz max 20 kN·m."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.number_input(key="Beam.L").set_value(4.0)
    at.number_input(key="Beam.S").set_value(2848.0)
    at.number_input(key="Beam.Iz").set_value(19430000.0)
    at.number_input(key="Beam.Iy").set_value(1424000.0)
    at.number_input(key="Beam.E").set_value(190.0)
    at.checkbox(key="Beam.shear").set_value(False)
    s = at.session_state["saisie"]["Beam"]
    s["sup"] = [{"pos": 0.0, "type": "pivot", "name": "A"}, {"pos": 4.0, "type": "appui_simple", "name": "B"}]
    s["pl"] = []
    s["dl"] = [{"a": 0.0, "b": 4.0, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}]
    for tableau in ("sup", "pl", "dl"):  # le tableau affiché repart de la saisie modifiée
        del at.session_state[f"Beam.{tableau}.src"]
        del at.session_state[f"Beam.{tableau}"]
    at.run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception and not at.error
    res = at.session_state["res"]["Beam"]
    assert res["sol"]["extrema"]["Mfz"]["max"] / 1e3 == pytest.approx(20.0, rel=1e-6)
    assert res["defl"]["integration"]["fmax"] * 1e3 == pytest.approx(9.029, abs=5e-4)
    assert "9.029" in res["status"]
