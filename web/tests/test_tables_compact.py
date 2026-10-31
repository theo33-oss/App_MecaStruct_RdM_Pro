"""Tableaux en mode compact : une liste de volets (champs empilés) au lieu de la grille, même saisie dessous."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app_pages"


def _page(nom: str, compact: bool = True) -> AppTest:
    at = AppTest.from_file(str(APP / f"{nom}.py"), default_timeout=60)
    at.session_state["vue"] = "telephone" if compact else "pc"
    return at.run()


def _bouton(at: AppTest, cle: str):
    return next(b for b in at.button if b.key == cle)


def test_treillis_liste_a_la_place_de_la_grille():
    at = _page("treillis")
    assert not at.exception
    assert any(e.label.startswith("1. ") for e in at.expander)
    assert _bouton(at, "Tr.nodes.l.ajout")


def test_ajouter_puis_supprimer_une_ligne_modifie_la_saisie():
    at = _page("treillis")
    n = len(at.session_state["saisie"]["Tr"]["nodes"])
    _bouton(at, "Tr.nodes.l.ajout").click().run()
    assert not at.exception
    assert len(at.session_state["saisie"]["Tr"]["nodes"]) == n + 1
    _bouton(at, f"Tr.nodes.l.{n}.sup").click().run()
    assert not at.exception
    assert len(at.session_state["saisie"]["Tr"]["nodes"]) == n


def test_une_valeur_saisie_dans_la_liste_est_recopiee_puis_retrouvee_dans_la_grille():
    at = _page("treillis")
    at.number_input(key="Tr.nodes.l.1.x").set_value(7.5).run()
    assert at.session_state["saisie"]["Tr"]["nodes"][1]["x"] == 7.5
    at.session_state["vue"] = "pc"
    at.run()
    assert not at.exception
    assert at.session_state["saisie"]["Tr"]["nodes"][1]["x"] == 7.5
    assert at.session_state["Tr.nodes.src"].iloc[1]["x"] == 7.5


def test_poutres_en_mode_compact_calcule_avec_les_lignes_de_la_liste():
    at = _page("poutres")
    assert not at.exception
    next(b for b in at.button if b.label == "Charger l'exemple").click().run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    assert not at.exception and not at.error
    assert at.session_state["res"]["Beam"]["sol"]["extrema"]["Mfz"]["max"] > 0
