"""Panneau « Explications du calcul » : lignes avec équations (validation_report) et affichage sur la page Poutres."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mecastruct.core.data_manager import DataManager
from mecastruct.services import validation_report as vr
from mecastruct.services.examples import loadExample

PAGE = str(Path(__file__).resolve().parents[1] / "app_pages" / "poutres.py")
MESSAGE_AVANT_CALCUL = "Cliquez sur « Calculer » pour voir les équations appliquées à vos données."


@pytest.fixture(scope="module")
def dm():
    return DataManager()


@pytest.mark.parametrize("key", vr.KEYS)
def test_lignes_avec_equation_latex(dm, key):
    """Chaque contrôle à la main de l'exemple par défaut a une équation LaTeX non vide."""
    saisie = loadExample(key)
    res = vr.recompute(key, saisie, dm)
    rows = vr.explanationRows(key, saisie, res, dm)
    assert rows
    for r in rows:
        if r["hand"] is not None:
            assert isinstance(r["latex"], str) and r["latex"].strip(), (key, r["label"])


def test_message_avant_calcul():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.session_state["vue"] = "pc"
    at.run()
    at.toggle(key="explication.Beam.visible").set_value(True).run()
    assert not at.exception
    assert MESSAGE_AVANT_CALCUL in [i.value for i in at.info]


def test_equations_affichees_apres_calcul():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.session_state["vue"] = "pc"
    at.run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    at.toggle(key="explication.Beam.visible").set_value(True).run()
    assert not at.exception
    assert len(at.latex) > 0
