"""Tests de fumée de l'interface Streamlit : l'application et chaque page démarrent sans exception."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

WEB = Path(__file__).resolve().parents[1]
# L'Accueil lance des liens st.page_link, qui n'existent que dans l'application complète : il est testé
# par test_app_starts (page par défaut de la navigation).
PAGES = [
    "base_de_donnees",
    "convertisseur",
    "sections",
    "poutres",
    "treillis",
    "sollicitations",
    "flambage",
    "tenseurs",
    "hooke_jauges",
]


def test_app_starts():
    at = AppTest.from_file(str(WEB / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_alone(page):
    at = AppTest.from_file(str(WEB / "app_pages" / f"{page}.py"), default_timeout=60).run()
    assert not at.exception
