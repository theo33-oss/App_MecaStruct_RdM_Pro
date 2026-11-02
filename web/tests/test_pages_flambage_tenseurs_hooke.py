"""Tests des pages Flambage, Tenseurs & critères et Hooke & jauges (AppTest) : exécution, exemples, transferts."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app_pages"


def _page(nom: str) -> AppTest:
    return AppTest.from_file(str(APP / f"{nom}.py"), default_timeout=60).run()


def _bouton(at: AppTest, libelle: str):
    return next(b for b in at.button if b.label == libelle)


@pytest.mark.parametrize("nom", ["flambage", "tenseurs", "hooke_jauges"])
def test_la_page_s_execute(nom):
    assert not _page(nom).exception


@pytest.mark.parametrize(
    ("cle", "resultat"),
    [("Fla.calc", "Fla"), ("Ten.calc", "Ten"), ("Hoo.calc", "Hoo"), ("Jau.calc", "Jau")],
)
def test_chaque_exemple_se_calcule(cle, resultat):
    nom = {"Fla": "flambage", "Ten": "tenseurs", "Hoo": "hooke_jauges", "Jau": "hooke_jauges"}[resultat]
    at = _page(nom)
    at.button(key=cle).click().run()
    assert not at.exception and not at.error
    assert resultat in at.session_state["res"]


@pytest.mark.parametrize("mode", ["iso3D", "planeStress", "planeStrain", "ortho"])
def test_hooke_chaque_mode_se_calcule(mode):
    at = _page("hooke_jauges")
    at.selectbox(key="Hoo.mode").set_value(mode).run()
    _bouton(at, "Recharger l'exemple").click().run()
    at.button(key="Hoo.calc").click().run()
    assert not at.exception and not at.error
    assert at.session_state["res"]["Hoo"]["result"]["mode"] == mode


def test_hooke_champs_inactifs_selon_le_mode():
    at = _page("hooke_jauges")
    at.selectbox(key="Hoo.mode").set_value("planeStrain").run()
    assert at.number_input(key="Hoo.sxx").disabled and not at.number_input(key="Hoo.exx").disabled
    at.selectbox(key="Hoo.mode").set_value("ortho").run()
    assert at.number_input(key="Hoo.E").disabled and not at.number_input(key="Hoo.E1").disabled


def test_flambage_regime_et_verdict_lisibles():
    """Le régime est mis en évidence (Rankine pour l'exemple) et le verdict suit P ; P = 0 : pas de verdict."""
    at = _page("flambage")
    at.button(key="Fla.calc").click().run()
    textes = [e.value for e in at.info]
    assert any("Régime : Poutre moyenne" in t for t in textes)
    assert any("vérifié" in e.value for e in at.success)
    at.number_input(key="Fla.P").set_value(0.0).run()
    at.button(key="Fla.calc").click().run()
    assert not at.exception and not at.success


def test_flambage_alerte_pres_du_seuil_et_libelle_de_p():
    """λ à ±10 % de λlim : avertissement visible ; le libellé de P précise le signe (compression > 0)."""
    at = _page("flambage")
    assert "compression > 0" in at.number_input(key="Fla.P").label
    at.button(key="Fla.calc").click().run()
    assert not any("λlim" in e.value for e in at.warning)
    b = at.session_state["res"]["Fla"]["result"]["analysis"]
    at.number_input(key="Fla.L").set_value(at.number_input(key="Fla.L").value * b["lambdaLim"] / b["lambda"]).run()
    at.button(key="Fla.calc").click().run()
    assert not at.exception
    assert any("λlim" in e.value for e in at.warning)


@pytest.mark.parametrize("cond", ["encastre-libre", "encastre-articule", "encastre-encastre"])
def test_flambage_conditions_aux_limites(cond):
    at = _page("flambage")
    at.selectbox(key="Fla.cond").set_value(cond).run()
    at.button(key="Fla.calc").click().run()
    assert not at.exception  # la ligne d'état peut être rouge : P = 300 kN dépasse Padm pour encastré-libre
    assert at.session_state["res"]["Fla"]["result"]["analysis"]["condition"] == cond


def test_flambage_charger_un_profile():
    at = _page("flambage")
    at.selectbox(key="Fla.fam").set_value("IPE").run()
    at.selectbox(key="Fla.prof").set_value("IPE 300").run()
    at.button(key="Fla.charger_profil").click().run()
    assert at.number_input(key="Fla.S").value == pytest.approx(5381.0)
    assert "IPE 300" in at.session_state["Fla_info"]


def test_flambage_importer_sans_section_calculee():
    at = _page("flambage")
    at.button(key="Fla.importer").click().run()
    assert not at.exception and len(at.warning) == 1


def test_section_envoyee_depuis_sections_se_lit_dans_flambage():
    """Report de E28 : la section calculée dans Sections arrive dans Flambage (valeurs, texte, matériau, calcul)."""
    sec = AppTest.from_file(str(APP / "sections.py"), default_timeout=60).run()
    _bouton(sec, "Charger l'exemple").click().run()
    _bouton(sec, "Calculer").click().run()
    _bouton(sec, "Utiliser cette section pour une poutre").click().run()
    assert not sec.exception and not sec.error
    fla = AppTest.from_file(str(APP / "flambage.py"), default_timeout=60)
    fla.session_state["saisie"] = sec.session_state["saisie"]
    fla.session_state["Fla_info"] = sec.session_state["Fla_info"]
    fla.run()
    assert not fla.exception
    saisie = sec.session_state["saisie"]["Fla"]
    assert fla.number_input(key="Fla.S").value == pytest.approx(saisie["S"])
    assert fla.number_input(key="Fla.Iz").value == pytest.approx(saisie["Iz"])
    assert any("profil en I" in m.value for m in fla.markdown)
    fla.button(key="Fla.calc").click().run()
    assert not fla.exception
    assert not fla.session_state["res"]["Fla"]["result"]["analysis"]["ok"]  # IPE 200 de 4 m sous 300 kN : NON vérifié
    assert len(fla.error) == 1 and "NON vérifié" in fla.error[0].value


def test_flambage_importer_depuis_sections_met_a_jour_poutres_et_flambage():
    """Le bouton « Importer depuis Sections » de Flambage fait le même transfert que celui de Sections."""
    sec = AppTest.from_file(str(APP / "sections.py"), default_timeout=60).run()
    _bouton(sec, "Calculer").click().run()
    sec.selectbox(key="Sec.type").set_value("disque").run()
    _bouton(sec, "Calculer").click().run()
    fla = AppTest.from_file(str(APP / "flambage.py"), default_timeout=60)
    fla.session_state["saisie"] = sec.session_state["saisie"]
    fla.session_state["res"] = {"Sec": sec.session_state["res"]["Sec"]}
    fla.run()
    fla.button(key="Fla.importer").click().run()
    assert not fla.exception and not fla.warning
    P = sec.session_state["res"]["Sec"]["result"]["P"]
    assert fla.number_input(key="Fla.Iz").value == pytest.approx(P["Iz"] * 1e12)
    assert fla.session_state["saisie"]["Beam"]["Iz"] == pytest.approx(P["Iz"] * 1e12)
    assert any("disque" in m.value for m in fla.markdown)


def test_poutre_vers_tenseurs_se_lit_dans_la_page_tenseurs():
    """Report de E27 : le σxx du point le plus sollicité de la poutre arrive dans Tenseurs et se calcule."""
    poutre = _page("poutres")
    _bouton(poutre, "Envoyer au tenseur (point le plus sollicité)").click().run()
    assert not poutre.exception and not poutre.error
    sigma = poutre.session_state["res"]["Beam"]["check"]["sigma"] / 1e6
    ten = AppTest.from_file(str(APP / "tenseurs.py"), default_timeout=60)
    ten.session_state["saisie"] = poutre.session_state["saisie"]
    ten.run()
    assert not ten.exception
    assert ten.number_input(key="Ten.Re").value == pytest.approx(poutre.session_state["saisie"]["Beam"]["Re"])
    ten.button(key="Ten.calc").click().run()
    assert not ten.exception and not ten.error
    pr = ten.session_state["res"]["Ten"]["result"]["principal"]
    assert pr["sigmaI"] / 1e6 == pytest.approx(sigma, rel=1e-9)  # σxx seul : la contrainte principale est σxx
    assert pr["sigmaII"] == pytest.approx(0.0, abs=1e-6) and pr["sigmaIII"] == pytest.approx(0.0, abs=1e-6)


def test_tenseurs_facette_par_normale():
    at = _page("tenseurs")
    at.selectbox(key="Ten.fmode").set_value("n").run()
    assert at.number_input(key="Ten.theta").disabled and not at.number_input(key="Ten.nx").disabled
    at.button(key="Ten.calc").click().run()
    assert not at.exception and not at.error


def test_symmetrize_garde_le_tenseur_symetrique():
    from mecastruct.services.compute import symmetrize

    sig = [[80.0, 30.0, 0.0], [30.0, -40.0, 0.0], [0.0, 0.0, 20.0]]
    out = symmetrize(sig, {0: {"y": 12.0}, 2: {"x": None}, 1: {"y": -5.0}})
    assert out == [[80.0, 12.0, 0.0], [12.0, -5.0, 0.0], [0.0, 0.0, 20.0]]
    assert sig[0][1] == 30.0  # entrée inchangée
