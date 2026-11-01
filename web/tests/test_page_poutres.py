"""Tests de la page « Poutres » (AppTest) : exécution, exemple isostatique, cas du README."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PAGE = str(Path(__file__).resolve().parents[1] / "app_pages" / "poutres.py")


def _bouton(at: AppTest, libelle: str):
    """Bouton de la page dont le libellé est `libelle`."""
    return next(b for b in at.button if b.label == libelle)


def test_page_p_execute():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception


def test_exemple_isostatique_puis_calcul():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Charger l'exemple").click().run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    res = at.session_state["res"]["Beam"]
    assert res["sol"]["extrema"]["Mfz"]["max"] > 0
    assert not res["unreliable"]


def test_cas_readme_en_widgets():
    """IPE 200, L = 4 m, 10 kN/m, sans tranchant : flèche 9,029 mm et Mfz max 20 kN·m."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.number_input(key="Beam.L").set_value(4.0)
    at.number_input(key="Beam.S").set_value(2848.0)
    at.number_input(key="Beam.Iz").set_value(19430000.0)
    at.number_input(key="Beam.Iy").set_value(1424000.0)
    at.number_input(key="Beam.E").set_value(190.0)
    at.checkbox(key="Beam.shear").set_value(False)
    s = at.session_state["saisie"]["Beam"]
    s["sup"] = [{"pos": 0.0, "type": "pivot", "name": "A"}, {"pos": 4.0, "type": "appui_simple", "name": "B"}]
    s["pl"] = []
    s["dl"] = [{"a": 0.0, "b": 4.0, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}]
    for tableau in ("sup", "pl", "dl"):  # le tableau affiché repart de la saisie modifiée
        del at.session_state[f"Beam.{tableau}.src"]
        del at.session_state[f"Beam.{tableau}"]
    at.run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception and not at.error
    res = at.session_state["res"]["Beam"]
    assert res["sol"]["extrema"]["Mfz"]["max"] / 1e3 == pytest.approx(20.0, rel=1e-6)
    assert res["defl"]["integration"]["fmax"] * 1e3 == pytest.approx(9.029, abs=5e-4)
    assert "9.029" in res["status"]


def _charge(at: AppTest, variante: str) -> None:
    at.selectbox(key="Beam.exemple").set_value(variante).run()
    _bouton(at, "Charger l'exemple").click().run()


def test_combinaisons_avec_enveloppe():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Calculer les combinaisons").click().run()
    assert not at.exception  # la ligne d'état est rouge : l'ELU de l'exemple ne passe pas
    T = at.session_state["res"]["BeamCombo"]
    assert T["Combinaison"].iloc[-1] == "Enveloppe"
    labels = [t.label for t in at.tabs]
    assert "Combinaisons" in labels
    at.number_input(key="Beam.L").set_value(9.0).run()  # saisie modifiée : l'onglet le signale
    assert "Combinaisons (saisie modifiée depuis)" in [t.label for t in at.tabs]


def test_eurocode_fatigue_et_profile_sur_exemple_ipe():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Vérifier selon l'Eurocode 3").click().run()
    _bouton(at, "Vérifier la fatigue").click().run()
    _bouton(at, "Chercher le profilé le plus léger").click().run()
    assert not at.exception and not at.error
    res = at.session_state["res"]
    assert {"BeamEC3", "BeamFat", "BeamProf"} <= set(res)
    assert res["BeamProf"][1] is not None


def test_eurocode_refuse_une_section_saisie_a_la_main():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.number_input(key="Beam.S").set_value(5000.0).run()  # valeur à la main : plus de forme associée
    _bouton(at, "Vérifier selon l'Eurocode 3").click().run()
    assert not at.exception
    assert len(at.error) == 1 and "BeamEC3" not in at.session_state["res"]


def test_charge_mobile():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Calculer l'enveloppe de la charge mobile").click().run()
    assert not at.exception and not at.error
    assert "BeamMov" in at.session_state["res"]


def test_annexe_nationale_remet_gamma_a_1():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.selectbox(key="Beam.na").set_value("autre").run()
    at.number_input(key="Beam.gM0").set_value(1.1).run()
    assert at.session_state["saisie"]["Beam"]["gM0"] == pytest.approx(1.1)
    at.selectbox(key="Beam.na").set_value("FR").run()
    s = at.session_state["saisie"]["Beam"]
    assert s["gM0"] == 1.0 and s["gM1"] == 1.0


def test_charge_rapide_ajoute_une_ligne():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    avant = len(at.session_state["saisie"]["Beam"]["dl"])
    at.selectbox(key="Beam_qforme").set_value("Triangulaire croissante (0 → p)").run()
    _bouton(at, "Ajouter cette charge").click().run()
    assert not at.exception and not at.error
    dl = at.session_state["saisie"]["Beam"]["dl"]
    assert len(dl) == avant + 1 and dl[-1]["type"] == "linéaire" and dl[-1]["vals"].startswith("0 ")


def test_tassement_ressort_rotule_et_poids_propre_editables():
    """Exemples « tassement » et « gerber » : tableaux supx et hg, température et poids propre éditables."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _charge(at, "tassement")
    assert at.session_state["saisie"]["Beam"]["supx"][0]["dy"] == -10.0
    at.number_input(key="Beam.thDT").set_value(20.0).run()
    at.checkbox(key="Beam.selfw").set_value(True).run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception and not at.error
    s = at.session_state["saisie"]["Beam"]
    assert s["thDT"] == 20.0 and s["selfw"] is True and "Beam" in at.session_state["res"]
    _charge(at, "gerber")
    _bouton(at, "Calculer").click().run()
    assert not at.exception and not at.error
    assert len(at.session_state["saisie"]["Beam"]["hg"]) == 1


def test_annuler_retablit_le_premier_exemple():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _charge(at, "console")
    L1 = at.session_state["saisie"]["Beam"]["L"]
    _charge(at, "deuxtravees")
    L2 = at.session_state["saisie"]["Beam"]["L"]
    assert L1 != L2
    _bouton(at, "↶ Annuler").click().run()
    assert at.session_state["saisie"]["Beam"]["L"] == L1
    assert at.number_input(key="Beam.L").value == L1
    _bouton(at, "↷ Rétablir").click().run()
    assert at.session_state["saisie"]["Beam"]["L"] == L2


def test_envoyer_au_tenseur():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Envoyer au tenseur (point le plus sollicité)").click().run()
    assert not at.exception and not at.error
    ten = at.session_state["saisie"]["Ten"]
    sigma = at.session_state["res"]["Beam"]["check"]["sigma"] / 1e6
    assert ten["sig"][0][0] == pytest.approx(sigma) and ten["mat"] == "S235"


def test_graphiques_empiles_puis_en_onglets():
    """Après « Calculer » : graphiques sous des titres, équations en onglets ; l'interrupteur rétablit les onglets."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Charger l'exemple").click().run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    assert {"Schéma", "Diagrammes", "Déformée α(s), v(s)"} <= {s.value for s in at.subheader}
    assert "Équations par tronçon" in [t.label for t in at.tabs]
    at.toggle(key="Beam_graphes_onglets").set_value(True).run()
    assert not at.exception and "Diagrammes" not in {s.value for s in at.subheader}
    assert "Diagrammes" in [t.label for t in at.tabs]


def _ordre(at: AppTest) -> list[str]:
    """Libellés des boutons, volets et titres de la page, dans l'ordre d'affichage (parcours en profondeur)."""
    sortie = []

    def parcours(bloc):
        for el in bloc.children.values():
            if el.type in ("button", "expander"):
                sortie.append(el.label)
            elif el.type == "subheader":
                sortie.append(el.value)
            if hasattr(el, "children"):
                parcours(el)

    parcours(at.main)
    return sortie


ESSENTIELS = ["Poutre et matériau", "Section", "Appuis et charges", "Calcul et affichage"]
AVANCES = [
    "Fatigue (Goodman)",
    "Eurocode 3 simplifié (flexion + tranchant)",
    "Charge mobile (convoi d'essieux, enveloppe)",
]


def test_volets_avances_sous_le_bouton_calculer():
    """Par défaut : Calculer, volets essentiels, « Fonctions avancées », volets avancés, « Mise en page »."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    ordre = _ordre(at)
    calcul, avance, mise = ordre.index("Calculer"), ordre.index("Fonctions avancées"), ordre.index("Mise en page")
    assert all(calcul < ordre.index(t) < avance for t in ESSENTIELS)
    assert all(avance < ordre.index(t) < mise for t in AVANCES)


def test_mise_en_page_deplace_un_volet_puis_reinitialise():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.radio(key="mise_en_page.Beam.fatigue").set_value("Haut").run()
    ordre = _ordre(at)
    assert ordre.index("Fatigue (Goodman)") < ordre.index("Fonctions avancées")
    at.radio(key="mise_en_page.Beam.section").set_value("Bas").run()
    ordre = _ordre(at)
    assert ordre.index("Section") > ordre.index("Fonctions avancées")
    _bouton(at, "Réinitialiser la mise en page").click().run()
    ordre = _ordre(at)
    assert ordre.index("Section") < ordre.index("Fonctions avancées") < ordre.index("Fatigue (Goodman)")


def test_mise_en_page_survit_au_chargement_d_un_exemple():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.radio(key="mise_en_page.Beam.fatigue").set_value("Haut").run()
    _bouton(at, "Charger l'exemple").click().run()
    assert at.radio(key="mise_en_page.Beam.fatigue").value == "Haut"


def test_synthese_sous_le_bouton_calculer():
    """Avant le calcul : aucune valeur ; après : 5 valeurs clés, la flèche est celle du calcul."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.metric
    _bouton(at, "Charger l'exemple").click().run()
    _bouton(at, "Calculer").click().run()
    assert not at.exception
    assert [m.label for m in at.metric] == ["Réaction max", "|T| max", "|Mf| max", "Flèche max", "Kt·σ max"]
    res = at.session_state["res"]["Beam"]
    fleche = res["defl"]["integration"]["fmax"] * 1e3
    assert at.metric[3].value == f"{fleche:.4g} mm"
    assert at.metric[4].delta.startswith(("vérifié", "NON vérifié"))


def test_mode_compact_formulaire_derriere_un_bouton():
    """Mode compact : un bouton « Formulaire » (tiroir). PC : panneau repliable « Formulaire rapide » à droite."""
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.session_state["vue"] = "telephone"
    at.run()
    assert not at.exception
    assert "Formulaire" in [b.label for b in at.button]
    assert "Formulaire rapide" not in [e.label for e in at.expander]
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert "Formulaire rapide" in [e.label for e in at.expander]
    assert "Formulaire rapide" not in [s.value for s in at.sidebar.subheader]


def test_schema_suit_la_saisie_apres_un_calcul():
    """Après « Calculer », changer L met le schéma à jour (aperçu) et signale que les résultats datent du calcul."""
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    _bouton(at, "Charger l'exemple").click().run()
    _bouton(at, "Calculer").click().run()
    textes = [c.value for c in at.caption]
    assert not any("Le schéma suit la saisie" in t for t in textes)
    at.number_input(key="Beam.L").set_value(8.0).run()
    assert not at.exception
    assert any("Le schéma suit la saisie" in c.value for c in at.caption)
    _bouton(at, "Calculer").click().run()
    assert not any("Le schéma suit la saisie" in c.value for c in at.caption)


def test_telephone_schema_au_dessus_de_la_saisie_pc_a_cote():
    """Téléphone : la visualisation (schéma) précède le bouton Calculer ; PC : le bouton précède le schéma."""
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.session_state["vue"] = "telephone"
    at.run()
    assert not at.exception
    ordre = _ordre(at)
    assert ordre.index("Schéma") < ordre.index("Calculer")
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.session_state["vue"] = "pc"
    at.run()
    assert not at.exception
    ordre = _ordre(at)
    assert ordre.index("Calculer") < ordre.index("Schéma")
