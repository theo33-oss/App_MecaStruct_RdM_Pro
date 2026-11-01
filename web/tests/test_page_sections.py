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


def test_efforts_de_la_poutre_section_composee_envoyee():
    """Section composée envoyée à la poutre puis recalculée : « Efforts en s » ne plante pas (tableaux NumPy)."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.selectbox(key="Sec.type").set_value("composite").run()
    _bouton(at, "Calculer").click().run()
    _bouton(at, "Utiliser cette section pour une poutre").click().run()
    _bouton(at, "Calculer").click().run()
    _bouton(at, "Efforts en s").click().run()
    assert not at.exception


def test_efforts_de_la_poutre():
    """« Efforts en s » et « Efforts au point critique » reprennent les efforts de la poutre (IPE 300, 6 m)."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.number_input(key="Sec.s0").set_value(2.0).run()
    _bouton(at, "Efforts en s").click().run()
    assert not at.exception and not at.error
    sec = at.session_state["saisie"]["Sec"]
    sol = at.session_state["res"]["Beam"]["sol"]
    from mecastruct.core.pp import ppEval

    assert sec["Mfz"] == pytest.approx(ppEval(sol["Mfz"], 2.0) / 1e3)
    assert sec["Ty"] == pytest.approx(ppEval(sol["Ty"], 2.0) / 1e3)
    _bouton(at, "Efforts au point critique").click().run()
    assert not at.exception and not at.error
    chk = at.session_state["res"]["Beam"]["check"]
    assert at.session_state["saisie"]["Sec"]["s0"] == pytest.approx(chk["s"])
    assert at.session_state["saisie"]["Sec"]["Mfz"] == pytest.approx(chk["Mfz"] / 1e3)
    at.number_input(key="Sec.s0").set_value(99.0).run()
    _bouton(at, "Efforts en s").click().run()
    assert len(at.error) == 1  # abscisse hors de la poutre : message, pas d'exception


def test_apercu_de_la_section_avant_le_calcul_puis_dessin_a_jour():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert "Section" in [s.value for s in at.subheader]
    assert any("Aperçu mis à jour" in c.value for c in at.caption)
