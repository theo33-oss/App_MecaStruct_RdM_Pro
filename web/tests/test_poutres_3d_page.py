"""Tests de la page « Poutres », mode « Ossature 3D » (AppTest) : ouverture, calcul d'un exemple, mécanisme."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGE = str(Path(__file__).resolve().parents[1] / "app_pages" / "poutres.py")


def _bouton(at: AppTest, libelle: str):
    return next(b for b in at.button if b.label == libelle)


def _mode_3d(at: AppTest, exemple: str) -> AppTest:
    """Passe en mode Ossature 3D et choisit l'exemple."""
    at.button_group(key="poutres.mode").set_value("Ossature 3D").run()
    at.selectbox(key="p3d.exemple").set_value(exemple).run()
    return at


def test_mode_2d_par_defaut():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    assert at.button_group(key="poutres.mode").value == "Poutre 2D"
    assert any(n.key == "Beam.L" for n in at.number_input)


def test_potence_en_L_calcul():
    at = _mode_3d(AppTest.from_file(PAGE, default_timeout=60).run(), "Potence en L")
    assert not at.exception
    _bouton(at, "Calculer").click().run()
    assert not at.exception and not at.error
    assert len(at.metric) >= 1
    assert at.session_state["p3d.res"]["res"]["equilibre"]["ok"]


def test_mecanisme_affiche_une_erreur():
    at = _mode_3d(AppTest.from_file(PAGE, default_timeout=60).run(), "Potence en L")
    noeuds = at.session_state["p3d.src.noeuds"].copy()
    noeuds["appui"] = "libre"  # plus aucun appui : mécanisme
    at.session_state["p3d.src.noeuds"] = noeuds
    del at.session_state["p3d.noeuds"]
    at.run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    assert any("mécanisme" in e.value for e in at.error)
