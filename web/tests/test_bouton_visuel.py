"""Bouton « Calculer » du visuel : il lance le même calcul que celui de la saisie, sans défiler jusqu'en bas."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mecastruct.ui.widgets import SAISIE_MODIFIEE

PAGES = Path(__file__).resolve().parents[1] / "app_pages"


@pytest.mark.parametrize(
    ("page", "nom"),
    [
        ("frettage.py", "fre"),
        ("ajustements.py", "aju"),
        ("paliers_lisses.py", "pal"),
        ("dimensionnement_moteur.py", "mot"),
        ("epicycloidaux.py", "epi"),
    ],
)
def test_bouton_du_visuel_calcule_comme_la_saisie(page, nom):
    at = AppTest.from_file(PAGES / page, default_timeout=60).run()
    assert f"{nom}.res" not in at.session_state
    at.button(key=f"zones.{nom}.calc").click().run()
    assert not at.exception
    assert f"{nom}.res" in at.session_state


@pytest.mark.parametrize(
    ("page", "nom"),
    [
        ("flambage.py", "Fla"),
        ("sections.py", "Sec"),
        ("tenseurs.py", "Ten"),
        ("treillis.py", "Tr"),
    ],
)
def test_bouton_du_visuel_sur_les_autres_pages(page, nom):
    at = AppTest.from_file(PAGES / page, default_timeout=60).run()
    at.button(key=f"zones.{nom}.calc").click().run()
    assert not at.exception


def _textes_neutres(at) -> list[str]:
    return [c.value for c in at.caption if SAISIE_MODIFIEE in c.value]


def test_machine_saisie_modifiee_sans_verdict_colore():
    at = AppTest.from_file(PAGES / "frettage.py", default_timeout=60).run()
    at.button(key="zones.fre.calc").click().run()
    assert at.success or at.error  # verdict coloré tant que la saisie est celle du calcul
    assert not _textes_neutres(at)
    at.number_input(key="fre.C").set_value(at.number_input(key="fre.C").value + 1).run()
    assert not at.exception
    assert not at.success and not at.error and _textes_neutres(at)


def test_synthese_sous_calculer_suit_la_saisie():
    at = AppTest.from_file(PAGES / "flambage.py", default_timeout=60).run()
    at.button(key="zones.Fla.calc").click().run()
    assert at.metric and not _textes_neutres(at)
    at.number_input(key="Fla.L").set_value(at.number_input(key="Fla.L").value + 1).run()
    assert not at.exception
    assert not at.metric and _textes_neutres(at)


def test_bouton_du_visuel_en_mode_ossature_3d():
    """Le mode Ossature 3D vit dans la page « Poutres » : son bouton du visuel lance le calcul « p3d.calc »."""
    at = AppTest.from_file(PAGES / "poutres.py", default_timeout=60).run()
    at.button_group(key="poutres.mode").set_value("Ossature 3D").run()
    at.button(key="zones.p3d.calc").click().run()
    assert not at.exception
    assert "p3d.res" in at.session_state


def test_telephone_sans_bouton_du_visuel():
    at = AppTest.from_file(PAGES / "frettage.py", default_timeout=60)
    at.session_state["vue"] = "telephone"
    at.run()
    assert not at.exception
    assert "zones.fre.calc" not in [b.key for b in at.button]
