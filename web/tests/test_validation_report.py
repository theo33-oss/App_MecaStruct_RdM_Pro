"""Tests du dossier de validation HTML (E31) : structure en 8 parties, contrôles à la main, méta et nom de fichier."""

import copy
import re
from datetime import datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import validation_report as vr
from mecastruct.services.examples import exampleNames, loadExample

TITRES = [t for _, t in vr._SECTIONS]


@pytest.fixture(scope="module")
def dm():
    return DataManager()


@pytest.fixture(scope="module")
def dossiers(dm):
    """Pour chaque clé : (saisie, résultat recalculé, HTML) sur l'exemple d'école."""
    out = {}
    for key in vr.KEYS:
        saisie = loadExample(key)
        res = vr.recompute(key, saisie, dm)
        out[key] = (saisie, res, vr.generate(key, saisie, res, dm))
    return out


@pytest.mark.parametrize("key", vr.KEYS)
def test_huit_parties(dossiers, key):
    """Le dossier contient les 8 titres de partie, le sommaire cliquable, et aucune section en erreur."""
    html = dossiers[key][2]
    assert html.startswith("<!doctype html>")
    for titre in TITRES:
        assert f"{titre}<a" in html
    for ident, _ in vr._SECTIONS:
        assert f'href="#{ident}"' in html
        assert f'<h2 id="{ident}">' in html
    assert "Section indisponible" not in html
    assert dossiers[key][1]["erreursRecalcul"] == []


@pytest.mark.parametrize("key", vr.KEYS)
def test_formules_et_rapport_non_vides(dossiers, key):
    """§6 et §7 ne sont pas vides : au moins une formule retenue, des lignes de rapport."""
    html = dossiers[key][2]
    formules = html.split('<h2 id="formules">')[1].split('<h2 id="avis">')[0]
    assert 'class="eqblock"' in formules
    rapport = html.split('<h2 id="rapport">')[1].split('<h2 id="formules">')[0]
    assert 'class="rln"' in rapport


@pytest.mark.parametrize("key", vr.KEYS)
def test_formules_retenues_existent(key):
    """Chaque titre de `keep` (§7) existe dans les fiches de formules : aucun titre perdu en route."""
    from mecastruct.core import data_manager

    m = vr.meta(key)
    titres = {f["title"] for forme in m["forms"] for f in data_manager.formulaSheet(forme)}
    assert [t for t in m["keep"] if t not in titres] == []


EXTRAS = {"combos": 1, "ec3": 1, "fatigue": 1, "profiles": 1}
CAS_EXEMPLES = [(k, nom) for k in vr.KEYS for nom in (exampleNames(k) or [None])]


def _controles(dm, key, nom=None, previous=None, modif=None):
    saisie = loadExample(key, nom)
    if modif:
        modif(saisie)
    res = vr.recompute(key, saisie, dm, previous)
    return saisie, res, vr._handRows(key, saisie, res, dm)


@pytest.mark.parametrize(("key", "nom"), CAS_EXEMPLES)
def test_controles_a_la_main_exemples(dm, key, nom):
    """Chaque exemple d'école : tous les contrôles à la main concordent avec le solveur (nOK == nTot)."""
    saisie, res, rows = _controles(dm, key, nom)
    nOK, nTot = vr.handCheck(key, saisie, res, dm)
    assert nOK == nTot
    # seules les sections en formules fermées (rectangle, disque, couronne, rectangle creux, I) sont recalculées
    assert nTot >= 4 or key == "Sec"
    assert [r["label"] for r in rows if r["hand"] is not None and not vr._verdict(r)[1]] == []


@pytest.mark.parametrize("nom", exampleNames("Beam"))
def test_poutre_avec_combinaisons_ec3_fatigue_profile(dm, nom):
    """Poutre avec combinaisons, Eurocode 3, fatigue et profilé calculés : tout concorde, extras compris."""
    saisie, res, _ = _controles(dm, "Beam", nom, EXTRAS)
    assert set(res["extras"]) == set(EXTRAS) and res["erreursRecalcul"] == []
    nOK, nTot = vr.handCheck("Beam", saisie, res, dm)
    assert nOK == nTot and nTot > 60
    sans = vr.handCheck("Beam", saisie, res, dm, withExtras=False)
    assert sans[0] == sans[1] and sans[1] < nTot


def test_poutre_plan_xz_et_charges_axiales(dm):
    """Charges en z, couples, charges réparties x, y et z : les équilibres des deux plans et de l'axe concordent."""

    def modif(s):
        s["plane"] = "xz"
        s["pl"] = [{"pos": 2.0, "Fx": 5.0, "Fy": -10.0, "Fz": -15.0, "name": "F", "case": "Q"}]
        s["pm"] = [{"pos": 3.0, "Mx": 0.0, "My": 4.0, "Mz": 6.0, "name": "C", "case": "G"}]
        s["dl"] = [
            {"a": 0.0, "b": 6.0, "dir": "z", "type": "uniforme", "vals": "-5", "name": "q", "case": "G"},
            {"a": 1.0, "b": 4.0, "dir": "x", "type": "uniforme", "vals": "2", "name": "qx", "case": "Q"},
            {"a": 1.0, "b": 5.0, "dir": "y", "type": "linéaire", "vals": "0 -8", "name": "qy", "case": "W"},
        ]

    saisie, res, rows = _controles(dm, "Beam", None, EXTRAS, modif)
    assert any("plan (x, z)" in r["label"] for r in rows)
    assert vr.handCheck("Beam", saisie, res, dm)[0] == vr.handCheck("Beam", saisie, res, dm)[1]


def test_poutre_interaction_normal_moment(dm):
    """Compression + flexion : flambement et interaction N + M (6.61, 6.62) refaits à la main concordent."""

    def modif(s):
        s["pl"] = [{"pos": 6.0, "Fx": -300.0, "Fy": -20.0, "Fz": 0.0, "name": "F", "case": "Q"}]
        s["sup"] = [{"pos": 0.0, "type": "pivot", "name": "A"}, {"pos": 6.0, "type": "pivot_glissant", "name": "B"}]
        s.update(Cmy=0.9, CmLT=0.9, C1=1.13, Lcr=3.0, LcrF=6.0)

    saisie, res, rows = _controles(dm, "Beam", None, EXTRAS, modif)
    assert res["extras"]["ec3"][0]["inter"] is not None
    assert any("Éq. 6.61" in r["label"] for r in rows)
    assert vr.handCheck("Beam", saisie, res, dm)[0] == vr.handCheck("Beam", saisie, res, dm)[1]


@pytest.mark.parametrize("cfg", ["quart", "demi", "complet"])
@pytest.mark.parametrize("rtype", ["45", "60"])
def test_jauges_montages_et_rosettes(dm, cfg, rtype):
    saisie, res, _ = _controles(dm, "Jau", None, None, lambda s: s.update(cfg=cfg, rtype=rtype))
    nOK, nTot = vr.handCheck("Jau", saisie, res, dm)
    assert nOK == nTot == 13


@pytest.mark.parametrize("cond", ["encastre-libre", "articule-articule", "encastre-articule", "encastre-encastre"])
@pytest.mark.parametrize("L", [0.5, 2.0, 20.0])
def test_flambage_les_trois_regimes(dm, cond, L):
    saisie, res, _ = _controles(dm, "Fla", None, None, lambda s: s.update(cond=cond, L=L))
    nOK, nTot = vr.handCheck("Fla", saisie, res, dm)
    assert nOK == nTot == 10


@pytest.mark.parametrize("section", ["rectangle", "disque", "I"])
def test_cisaillement_et_flexion_sections(dm, section):
    from mecastruct.services import compute

    S = loadExample("Sec")
    S["type"] = section
    sec = compute._sectionFromSaisie(S, dm)
    for key in ("Cis", "Fle"):
        saisie, res, _ = _controles(dm, key, None, None, lambda s, sec=sec: s.update(section=sec))
        nOK, nTot = vr.handCheck(key, saisie, res, dm)
        assert nOK == nTot > 0


def test_un_ecart_est_detecte(dm):
    """Le contrôle n'est pas complaisant : une valeur du solveur faussée de 1 % est signalée (ÉCART, bilan rouge)."""
    saisie = loadExample("Tra")
    res = copy.deepcopy(vr.recompute("Tra", saisie, dm))
    res["result"]["sigmaMax"] *= 1.01
    nOK, nTot = vr.handCheck("Tra", saisie, res, dm)
    assert nTot - nOK == 1
    html = vr.generate("Tra", saisie, res, dm)
    assert "ÉCART" in html and "1 écart(s) à examiner" in html


def test_bilan_vert_sur_un_exemple(dossiers):
    html = dossiers["Beam"][2]
    assert "contrôles de calcul concordent" in html and "écart(s) à examiner" not in html


def test_diagrammes_plotly_integres(dossiers):
    """§5 : figures Plotly insérées (un seul chargement de plotly.js depuis le CDN) ; MathJax 3 depuis cdnjs."""
    html = dossiers["Beam"][2]
    assert html.count('class="plotly-graph-div"') >= 3
    assert html.count("cdn.plot.ly") == 1
    assert "cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2" in html
    assert 'id="mjwarn"' in html


def test_texte_saisi_echappe(dm):
    """Un nom contenant du HTML ne s'insère pas tel quel dans le dossier."""
    saisie = loadExample("Tr")
    saisie["nodes"][0]["name"] = "<b>X</b>"
    res = vr.recompute("Tr", saisie, dm)
    html = vr.generate("Tr", saisie, res, dm)
    assert "&lt;b&gt;X&lt;/b&gt;" in html
    assert "<b>X</b>" not in html


def test_cle_inconnue():
    with pytest.raises(MecaStructError) as err:
        vr.meta("Zzz")
    assert err.value.identifier == "MecaStruct:Validation:unknownKey"


def test_nom_de_fichier():
    n = vr.fileName("Beam", datetime(2026, 10, 31, 14, 5, 9))
    assert n == "Validation_Poutre_20261031_140509.html"
    assert re.fullmatch(r"Validation_Tenseurs_et_criteres_\d{8}_\d{6}\.html", vr.fileName("Ten"))


APP = Path(__file__).resolve().parents[1] / "app_pages"


def test_bouton_dossier_de_validation():
    """Page Traction : bouton inactif sans résultat, puis dossier téléchargeable après « Calculer »."""
    at = AppTest.from_file(str(APP / "sollicitations.py"), default_timeout=120).run()
    bouton = next(b for b in at.button if b.key == "validation.Tra.bouton")
    assert bouton.disabled
    next(b for b in at.button if b.key == "Tra.calc").click().run()
    bouton = next(b for b in at.button if b.key == "validation.Tra.bouton")
    assert not bouton.disabled
    bouton.click().run()
    assert not at.exception and not at.error
    nom, html, _ = at.session_state["validation.Tra"]
    assert re.fullmatch(r"Validation_Traction_compression_\d{8}_\d{6}\.html", nom)
    assert all(t in html for t in TITRES)


def test_controle_impossible_compte_comme_ecart():
    """Un sous-contrôle qui plante n'est plus une simple ligne de titre : il entre dans le total et ne concorde pas."""
    ligne = vr._safeRows(lambda: 1 / 0, "Fatigue")[0]
    assert ligne["hand"] is not None and not vr._verdict(ligne)[1]


def test_hypotheses_indisponibles_et_calculs_annexes_non_refaits_dans_le_bilan(monkeypatch):
    def plante(*_):
        raise ValueError("boum")

    monkeypatch.setattr(vr, "_hypothesesHTML", plante)
    assert vr._hypSafe("Beam", {}, {}, None)[2] == 1
    assert "2 calcul(s) annexe(s) non refait(s)" in vr._bilan(5, 5, 0, 0, 2)
