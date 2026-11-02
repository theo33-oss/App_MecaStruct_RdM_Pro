"""Tests de project_io : aller-retour problème et projet, refus d'un autre onglet, exports xlsx et csv."""

import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import compute, project_io
from mecastruct.services.beam_services import computeBeam
from mecastruct.services.examples import loadExample
from tests.test_beam_services import _ipe200_readme


@pytest.fixture(scope="module")
def dm():
    return DataManager()


@pytest.fixture(scope="module")
def readme_beam(dm):
    return computeBeam(_ipe200_readme(dm), dm)


@pytest.mark.parametrize("tab", project_io.PROJECT_KEYS)
def test_aller_retour_probleme(tab):
    saisie = loadExample(tab)
    onglet, relu = project_io.problemFromJson(project_io.problemToJson(tab, saisie), tab)
    assert onglet == tab
    assert relu == json.loads(json.dumps(saisie))


def test_numpy_et_dataframe_convertis():
    saisie = {"v": np.array([1.0, 2.0]), "x": np.float64(3.5), "tableau": pd.DataFrame({"a": [1, 2]})}
    _, relu = project_io.problemFromJson(project_io.problemToJson("Sec", saisie))
    assert relu == {"v": [1.0, 2.0], "x": 3.5, "tableau": [{"a": 1}, {"a": 2}]}


def test_aller_retour_projet():
    saisies = {k: loadExample(k) for k in project_io.PROJECT_KEYS}
    relus, echecs = project_io.projectFromJson(project_io.projectToJson(saisies))
    assert echecs == []
    assert relus == json.loads(json.dumps(saisies))


def test_projet_onglet_absent_signale():
    d = json.loads(project_io.projectToJson({k: loadExample(k) for k in project_io.PROJECT_KEYS}))
    del d["projet"]["Fla"]
    d["projet"]["Ten"] = "abîmé"
    relus, echecs = project_io.projectFromJson(json.dumps(d))
    assert echecs == ["Fla", "Ten"] and "Beam" in relus


def test_materiau_absent_de_la_base_signale(dm):
    saisies = {k: loadExample(k) for k in project_io.PROJECT_KEYS}
    saisies["Fla"]["mat"] = saisies["Tra"]["mat"] = "Acier utilisateur"  # ajouté dans une autre session
    relus, _ = project_io.projectFromJson(project_io.projectToJson(saisies))
    assert project_io.missingMaterials(relus, dm.listMaterials() + ["Acier utilisateur"]) == {}
    assert project_io.missingMaterials(relus, dm.listMaterials()) == {"Acier utilisateur": ["Tra", "Fla"]}


def test_autre_onglet_refuse():
    texte = project_io.problemToJson("Fla", loadExample("Fla"))
    with pytest.raises(MecaStructError, match="cet onglet") as e:
        project_io.problemFromJson(texte, "Beam")
    assert e.value.identifier == "MecaStruct:App:badProblemFile"


@pytest.mark.parametrize("texte", ["pas du json", "[1, 2]", '{"app": "autre"}', '{"app": "MecaStruct RdM Pro"}'])
def test_fichier_etranger_refuse(texte):
    with pytest.raises(MecaStructError):
        project_io.problemFromJson(texte)
    with pytest.raises(MecaStructError):
        project_io.projectFromJson(texte)


def test_version_plus_recente_refusee():
    d = json.loads(project_io.problemToJson("Sec", loadExample("Sec")))
    d["version"] = project_io.FORMAT_VERSION + 1
    with pytest.raises(MecaStructError, match="autre version"):
        project_io.problemFromJson(json.dumps(d))


def test_enveloppe_du_readme(readme_beam):
    feuilles = project_io.resultSheets("Beam", readme_beam)
    assert {"Enveloppe", "Efforts", "Réactions"} <= set(feuilles)
    mfz = feuilles["Enveloppe"].set_index("Effort").loc["Mfz"]
    assert mfz["Max"] == pytest.approx(20.0, rel=1e-6) and mfz["s du max (m)"] == pytest.approx(2.0)
    assert list(feuilles["Efforts"].columns) == [
        "s (m)", "N (kN)", "Ty (kN)", "Tz (kN)", "Mt (kN·m)", "Mfy (kN·m)", "Mfz (kN·m)"
    ]  # fmt: skip


def test_xlsx_relu_identique(readme_beam):
    feuilles = project_io.resultSheets("Beam", readme_beam)
    relues = pd.read_excel(io.BytesIO(project_io.toXlsx(feuilles)), sheet_name=None)
    assert list(relues) == list(feuilles)
    for nom, t in feuilles.items():
        # une cellule texte vide devient une cellule Excel vide, relue NaN : on compare les deux en texte vide
        pd.testing.assert_frame_equal(relues[nom].fillna(""), t.reset_index(drop=True).fillna(""), check_dtype=False)


def test_csv_zip(readme_beam):
    feuilles = project_io.resultSheets("Beam", readme_beam)
    with zipfile.ZipFile(io.BytesIO(project_io.toCsvZip(feuilles))) as z:
        assert sorted(z.namelist()) == sorted(f"{n}.csv" for n in feuilles)
        texte = z.read("Enveloppe.csv").decode("utf-8-sig")
    assert texte.splitlines()[0] == "Effort;Unité;Max;s du max (m);Min;s du min (m)"
    assert "20,0" in texte  # décimale française


def test_noms_de_feuilles():
    t = pd.DataFrame({"a": [1]})
    feuilles = project_io.resultSheets(
        "Sec", {"tables": {"A[1]:b/c": t, "x" * 40 + "1": t, "x" * 40 + "2": t, "vide": t.iloc[0:0]}}
    )
    assert list(feuilles) == ["A 1  b c", "x" * 31, "x" * 29 + "_2"]


def test_export_sans_resultat():
    assert project_io.resultSheets("Sec", {"tables": {}}) == {}
    with pytest.raises(MecaStructError, match="Calculer"):
        project_io.toXlsx({})


def test_export_autres_onglets(dm):
    res = compute.computeTorsion(loadExample("Tor"), dm)
    feuilles = project_io.resultSheets("Tor", res)
    assert "Synthèse" in feuilles
    pd.read_excel(io.BytesIO(project_io.toXlsx(feuilles)), sheet_name="Synthèse")
