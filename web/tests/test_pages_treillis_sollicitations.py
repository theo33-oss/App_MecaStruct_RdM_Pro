"""Tests des pages Treillis et Sollicitations (AppTest) : exécution, exemples calculés, efforts de la poutre."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app_pages"


def _page(nom: str) -> AppTest:
    return AppTest.from_file(str(APP / f"{nom}.py"), default_timeout=60).run()


@pytest.mark.parametrize("nom", ["treillis", "sollicitations"])
def test_la_page_s_execute(nom):
    assert not _page(nom).exception


def test_treillis_exemple_se_calcule():
    at = _page("treillis")
    next(b for b in at.button if b.label == "Calculer").click().run()
    assert not at.exception and not at.error
    res = at.session_state["res"]["Tr"]
    assert res["result"]["tsol"]["isostatic"] and set(res["tables"]) == {"Barres", "Réactions", "Déplacements"}


def test_treillis_barre_inconnue_donne_un_message():
    at = _page("treillis")
    at.session_state["saisie"]["Tr"]["bars"][0]["j"] = 99
    for cle in ("Tr.bars", "Tr.bars.src"):
        del at.session_state[cle]
    at.run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    assert not at.exception  # message d'erreur ou trace dans la page, pas d'exception non gérée de la page


@pytest.mark.parametrize(
    ("cle", "resultat"),
    [
        ("Tra.calc", "Tra"),
        ("Cis.calc", "Cis"),
        ("Cis.key", "CisKey"),
        ("Cis.pin", "CisPin"),
        ("Tor.calc", "Tor"),
        ("Fle.calc", "Fle"),
    ],
)
def test_sollicitations_chaque_exemple_se_calcule(cle, resultat):
    at = _page("sollicitations")
    at.button(key=cle).click().run()
    assert not at.exception and not at.error
    assert resultat in at.session_state["res"]


def test_traction_section_variable_et_expression_interdite():
    at = _page("sollicitations")
    at.button(key="Tra.charger").click().run()
    at.selectbox(key="Tra.exemple").set_value("variable").run()
    at.button(key="Tra.charger").click().run()
    at.button(key="Tra.calc").click().run()
    assert not at.exception and not at.error
    at.text_input(key="Tra.Sexpr").set_value("__import__('os').getcwd()").run()
    at.button(key="Tra.calc").click().run()
    assert not at.exception and len(at.error) == 1  # refusée par la liste blanche, jamais exécutée


def test_flexion_efforts_de_la_poutre():
    """« Charger depuis la poutre » : efforts en s puis au point critique, abscisse hors poutre refusée."""
    from mecastruct.core.pp import ppEval

    at = _page("sollicitations")
    at.number_input(key="Fle.s0").set_value(2.0).run()
    at.button(key="Fle.efforts_s").click().run()
    assert not at.exception and not at.error
    sol = at.session_state["res"]["Beam"]["sol"]
    fle = at.session_state["saisie"]["Fle"]
    assert fle["Mfz"] == pytest.approx(ppEval(sol["Mfz"], 2.0) / 1e3)
    at.button(key="Fle.efforts_max").click().run()
    chk = at.session_state["res"]["Beam"]["check"]
    assert at.session_state["saisie"]["Fle"]["s0"] == pytest.approx(chk["s"])
    assert at.session_state["saisie"]["Fle"]["Mfz"] == pytest.approx(chk["Mfz"] / 1e3)
    at.number_input(key="Fle.s0").set_value(99.0).run()
    at.button(key="Fle.efforts_s").click().run()
    assert len(at.error) == 1


def test_sections_envoie_la_section_a_flambage():
    """Report de E25 : « Utiliser cette section » remplit aussi la saisie Flambage (S, Iz, Iy, matériau)."""
    at = AppTest.from_file(str(APP / "sections.py"), default_timeout=60).run()
    next(b for b in at.button if b.label == "Charger l'exemple").click().run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    next(b for b in at.button if b.label == "Utiliser cette section pour une poutre").click().run()
    assert not at.exception and not at.error
    fla, beam = at.session_state["saisie"]["Fla"], at.session_state["saisie"]["Beam"]
    assert fla["S"] == pytest.approx(beam["S"]) and fla["Iz"] == pytest.approx(beam["Iz"])
    assert fla["Iy"] == pytest.approx(beam["Iy"]) and fla["mat"] == "S235"
    assert fla["E"] == pytest.approx(190.0)


def test_sections_cornière_envoie_les_moments_principaux():
    from mecastruct.core import geometry

    at = AppTest.from_file(str(APP / "sections.py"), default_timeout=60).run()
    at.selectbox(key="Sec.type").set_value("L").run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    next(b for b in at.button if b.label == "Utiliser cette section pour une poutre").click().run()
    assert not at.exception and not at.error
    P = geometry.analytical(at.session_state["res"]["Sec"]["result"]["sec"])
    fla = at.session_state["saisie"]["Fla"]
    assert abs(P["Iyz"]) > 0
    assert fla["Iz"] == pytest.approx(P["I1"] * 1e12) and fla["Iy"] == pytest.approx(P["I2"] * 1e12)
