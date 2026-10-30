"""Tests des pages « Base de données » et « Convertisseur » (AppTest) : exécution sans exception, conversion,
ajout d'un matériau par le formulaire."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGES = Path(__file__).resolve().parents[1] / "app_pages"


def test_base_de_donnees_s_execute():
    at = AppTest.from_file(str(PAGES / "base_de_donnees.py"), default_timeout=60).run()
    assert not at.exception


def test_convertisseur_s_execute():
    at = AppTest.from_file(str(PAGES / "convertisseur.py"), default_timeout=60).run()
    assert not at.exception


def test_convertisseur_pouces_en_millimetres():
    at = AppTest.from_file(str(PAGES / "convertisseur.py"), default_timeout=60).run()
    at.selectbox(key="conv.grandeur").set_value("Longueur").run()
    at.selectbox(key="conv.de").set_value("in").run()
    at.selectbox(key="conv.vers").set_value("mm").run()
    assert not at.exception
    assert "25.4" in at.metric[0].value


def test_base_ajoute_un_materiau():
    at = AppTest.from_file(str(PAGES / "base_de_donnees.py"), default_timeout=60).run()
    bouton = next(b for b in at.button if b.label == "Ajouter / remplacer")
    bouton.click().run()
    assert not at.exception
    assert "Acier utilisateur" in at.session_state["dm"].listMaterials()
