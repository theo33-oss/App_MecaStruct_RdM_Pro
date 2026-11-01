"""Garde-fous du site public : expressions, taille des saisies, fichiers importés, exports, configuration."""

import io
import time
import zipfile
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import beam_services, compute, project_io
from mecastruct.services.examples import loadExample
from mecastruct.services.limits import MAX_LIGNES, MAX_TEXTE

RACINE = Path(__file__).resolve().parents[2]


def _identifiant(appel, *args) -> str:
    with pytest.raises(MecaStructError) as err:
        appel(*args)
    return err.value.identifier


# ---------------------------------------------------------------------------------------------- expressions S(x)


@pytest.mark.parametrize("expr", ["9^9^9", "9^9^9^9", "10^400", "1/0"])
def test_expression_qui_deborde_est_refusee_sans_bloquer(expr):
    debut = time.perf_counter()
    assert _identifiant(compute.parseFunction, expr) == "MecaStruct:App:invalidExpression"
    assert time.perf_counter() - debut < 2


def test_expression_normale_inchangee():
    assert list(compute.parseFunction("2^10")([0.0, 1.0])) == [1024.0, 1024.0]


# ------------------------------------------------------------------------------------------------ taille des saisies


def test_trop_de_lignes_refuse_au_calcul():
    s = loadExample("Beam")
    s["pl"] = s["pl"] * (MAX_LIGNES + 1)
    assert _identifiant(beam_services.buildBeamModel, s, DataManager()) == "MecaStruct:App:invalidInput"
    t = loadExample("Tr")
    t["nodes"] = t["nodes"] * (MAX_LIGNES + 1)
    assert _identifiant(compute.computeTruss, t, DataManager()) == "MecaStruct:App:invalidInput"


def test_texte_trop_long_refuse():
    s = loadExample("Beam")
    s["mvP"] = "1 " * MAX_TEXTE
    assert _identifiant(beam_services.buildBeamModel, s, DataManager()) == "MecaStruct:App:invalidInput"


# ------------------------------------------------------------------------------------------------ fichiers importés


def test_import_refuse_un_champ_de_mauvais_genre():
    s = loadExample("Beam")
    s["L"] = "six mètres"
    texte = project_io.problemToJson("Beam", s)
    assert _identifiant(project_io.problemFromJson, texte, "Beam") == "MecaStruct:App:badProblemFile"


def test_import_refuse_un_tableau_trop_long():
    s = loadExample("Beam")
    s["pl"] = s["pl"] * (MAX_LIGNES + 1)
    texte = project_io.problemToJson("Beam", s)
    assert _identifiant(project_io.problemFromJson, texte, "Beam") == "MecaStruct:App:invalidInput"


def test_projet_un_onglet_invalide_est_signale_les_autres_sont_ouverts():
    saisies = {k: loadExample(k) for k in project_io.PROJECT_KEYS}
    saisies["Beam"]["L"] = "six mètres"
    lus, echecs = project_io.projectFromJson(project_io.projectToJson(saisies))
    assert echecs == ["Beam"]
    assert set(lus) == set(project_io.PROJECT_KEYS) - {"Beam"}


# --------------------------------------------------------------------------------------------- exports sans formule

TEXTES = ["=1+1", "@SUM(1)", "+cmd", "-2+3", "-12,5", "-", "texte sûr"]


def test_xlsx_aucun_texte_ne_devient_une_formule():
    x = project_io.toXlsx({"T": pd.DataFrame({"Nom": TEXTES, "=A1": range(len(TEXTES))})})
    ws = openpyxl.load_workbook(io.BytesIO(x)).active
    assert ws.cell(1, 2).value == "'=A1"
    cellules = [ws.cell(r, 1) for r in range(2, 2 + len(TEXTES))]
    assert all(c.data_type != "f" for c in cellules)
    assert [c.value for c in cellules] == ["'=1+1", "'@SUM(1)", "'+cmd", "'-2+3", "-12,5", "-", "texte sûr"]


def test_csv_aucun_texte_ne_commence_par_un_signe_de_formule():
    z = project_io.toCsvZip({"T": pd.DataFrame({"Nom": TEXTES})})
    lignes = zipfile.ZipFile(io.BytesIO(z)).read("T.csv").decode("utf-8-sig").splitlines()[1:]
    assert [ligne.strip('"') for ligne in lignes] == ["'=1+1", "'@SUM(1)", "'+cmd", "'-2+3", "-12,5", "-", "texte sûr"]


def test_export_des_resultats_reels_inchange_pour_les_nombres():
    res = compute.computeTruss(loadExample("Tr"), DataManager())
    feuilles = project_io.resultSheets("Tr", res)
    relu = pd.read_excel(io.BytesIO(project_io.toXlsx(feuilles)), sheet_name=None)
    assert set(relu) == set(feuilles)


# ----------------------------------------------------------------------------------------------- configuration


def test_limite_de_televersement_et_secrets_ignores():
    assert "maxUploadSize = 5" in (RACINE / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    ignores = (RACINE / ".gitignore").read_text(encoding="utf-8").split()
    for motif in (".env", ".streamlit/secrets.toml", "*.pem", "*.key"):
        assert motif in ignores
