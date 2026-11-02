"""Pages légales (mentions, confidentialité, cookies, conditions) et légende textuelle des graphiques."""

from pathlib import Path

import plotly.graph_objects as go
import pytest
from streamlit.testing.v1 import AppTest

from mecastruct.ui.widgets import resume_graphique

PAGES = Path(__file__).resolve().parents[1] / "app_pages"


@pytest.mark.parametrize(
    ("fichier", "titre"),
    [
        ("mentions_legales.py", "Mentions légales"),
        ("confidentialite.py", "Politique de confidentialité"),
        ("cookies.py", "Cookies et traceurs"),
        ("conditions.py", "Conditions d'utilisation"),
    ],
)
def test_page_legale_affiche_son_titre(fichier, titre):
    at = AppTest.from_file(str(PAGES / fichier), default_timeout=60).run()
    assert not at.exception
    assert [t.value for t in at.title] == [titre]
    assert any("Dernière mise à jour" in c.value for c in at.caption)


def test_resume_graphique_donne_titre_axes_et_extrema():
    fig = go.Figure(go.Scatter(x=[0, 1, 2, 3], y=[0, 5, -2, 1], name="v(s)"))
    fig.update_layout(title="Flèche<br><sup>poutre</sup>", xaxis_title="s (m)", yaxis_title="v (mm)")
    texte = resume_graphique(fig)
    assert "Flèche poutre" in texte
    assert "x = s (m), y = v (mm)" in texte
    assert "v(s) : maximum 5 en x = 1, minimum -2 en x = 2." in texte


def test_resume_graphique_d_un_dessin_a_l_echelle_se_limite_au_titre():
    fig = go.Figure(go.Scatter(x=[0, 1, 2], y=[0, 1, 0], name="contour"))
    fig.update_layout(title="Schéma", yaxis_scaleanchor="x")
    assert resume_graphique(fig) == "Schéma"
