"""Tests du dossier de validation HTML (E31) : structure en 8 parties, contrôles à la main, méta et nom de fichier."""

import re
from datetime import datetime

import pytest

from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import validation_report as vr
from mecastruct.services.examples import loadExample

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


@pytest.mark.parametrize("key", ["Sec", "Tra"])
def test_controles_a_la_main_A(dossiers, dm, key):
    """Sous-étape A : Sec et Tra ont des contrôles à la main qui concordent tous."""
    saisie, res, _ = dossiers[key]
    nOK, nTot = vr.handCheck(key, saisie, res, dm)
    assert nTot >= 5
    assert nOK == nTot


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
