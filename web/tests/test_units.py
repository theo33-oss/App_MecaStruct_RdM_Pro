"""Tests des erreurs, des utilitaires, des unités et du convertisseur (étape E02)."""

import math

import numpy as np
import pytest

from mecastruct.core.errors import MecaStructError
from mecastruct.core.units import convertUnits, fromSI, toSI, unitFactor
from mecastruct.core.utils import as_list, fmt_fr, load_json
from tests.golden_tools import load_cases

FACTEURS = load_json("units.json")["factors"]
CAS_CONVERTISSEUR = load_cases("golden_units.json")

# Table de test_DataManager.m (testUnitsAllContractUnits)
UNITES_CONTRAT = {
    "m": 1,
    "cm": 1e-2,
    "mm": 1e-3,
    "µm": 1e-6,
    "um": 1e-6,
    "m^2": 1,
    "cm^2": 1e-4,
    "mm^2": 1e-6,
    "m^3": 1,
    "cm^3": 1e-6,
    "mm^3": 1e-9,
    "m^4": 1,
    "cm^4": 1e-8,
    "mm^4": 1e-12,
    "N": 1,
    "kN": 1e3,
    "MN": 1e6,
    "daN": 10,
    "N.m": 1,
    "kN.m": 1e3,
    "N.mm": 1e-3,
    "daN.m": 10,
    "N/m": 1,
    "kN/m": 1e3,
    "N/mm": 1e3,
    "Pa": 1,
    "kPa": 1e3,
    "MPa": 1e6,
    "GPa": 1e9,
    "rad": 1,
    "mrad": 1e-3,
    "deg": math.pi / 180,
    "°": math.pi / 180,
    "rad/m": 1,
    "deg/m": math.pi / 180,
    "°/m": math.pi / 180,
    "1/°C": 1,
    "1e-6/°C": 1e-6,
    "kg/m^3": 1,
    "kg/m": 1,
    "-": 1,
}


@pytest.mark.parametrize("entree", FACTEURS, ids=[e["code"] for e in FACTEURS])
def test_facteurs_units_json(entree):
    if entree.get("erreur"):
        with pytest.raises(MecaStructError):
            unitFactor(entree["code"])
    else:
        assert unitFactor(entree["code"]) == pytest.approx(entree["factor"], rel=1e-12)


@pytest.mark.parametrize("unite", ["mm", "kN.m", "MPa", "GPa", "deg", "mm^4", "kN/m"])
def test_aller_retour(unite):
    assert fromSI(toSI(3.7, unite), unite) == pytest.approx(3.7)


def test_vectorisation():
    resultat = toSI([1, 2], "mm")
    assert isinstance(resultat, np.ndarray)
    np.testing.assert_allclose(resultat, [0.001, 0.002])


@pytest.mark.parametrize("cas", CAS_CONVERTISSEUR, ids=[c["id"] for c in CAS_CONVERTISSEUR])
def test_convertisseur_golden(cas):
    entrees = {("frm" if k == "from" else k): v for k, v in cas["entrees"].items()}
    if cas["erreur"]:
        assert "Unité inconnue" in cas["erreur"]
        with pytest.raises(MecaStructError):
            convertUnits(**entrees)
    else:
        assert convertUnits(**entrees) == pytest.approx(cas["sortie"], rel=1e-12)


def test_convertisseur_valeur_fixe():
    assert convertUnits(1, "Longueur", "in", "mm") == pytest.approx(25.4)


@pytest.mark.parametrize("unite, facteur", list(UNITES_CONTRAT.items()))
def test_contrat_unites(unite, facteur):
    x = np.array([[0.0, 1.5, -3.0], [2.0, 7.0, 1e3]])
    assert unitFactor(unite) == pytest.approx(facteur, rel=1e-15)
    np.testing.assert_allclose(toSI(x, unite), x * facteur, rtol=1e-15)
    np.testing.assert_allclose(fromSI(toSI(x, unite), unite), x, rtol=0, atol=1e-12 * np.max(np.abs(x)))


def test_exemples_unites():
    assert toSI(200, "MPa") == 2e8
    assert fromSI(2e8, "MPa") == 200
    assert toSI(180, "deg") == pytest.approx(math.pi, rel=1e-15)
    assert toSI(5, "kN.m") == 5000
    assert toSI(1, "cm²") == pytest.approx(1e-4, rel=1e-15)
    assert toSI(1, "N·m") == 1
    assert toSI(1, " kN / m ") == 1e3


@pytest.mark.parametrize(
    "appel, identifiant",
    [
        (lambda: unitFactor("furlong"), "MecaStruct:DataManager:unknownUnit"),
        (lambda: toSI(1, "parsec"), "MecaStruct:DataManager:unknownUnit"),
        (lambda: unitFactor(12), "MecaStruct:DataManager:unknownUnit"),
        (lambda: unitFactor("mN"), "MecaStruct:DataManager:unknownUnit"),
        (lambda: unitFactor("mPa"), "MecaStruct:DataManager:unknownUnit"),
        (lambda: toSI(1, "mN.m"), "MecaStruct:DataManager:unknownUnit"),
        (lambda: toSI("a", "m"), "MecaStruct:DataManager:invalidValue"),
    ],
)
def test_erreurs_unites(appel, identifiant):
    with pytest.raises(MecaStructError) as err:
        appel()
    assert err.value.identifier == identifiant


def test_repli_casse_sans_confondre_milli_et_mega():
    assert unitFactor("KN") == 1e3
    assert unitFactor("Mpa") == 1e6
    assert unitFactor("KPA") == 1e3
    for unite in ("mN", "mPa", "mpa", "MM"):
        with pytest.raises(MecaStructError):
            unitFactor(unite)


def test_mecastruct_error():
    err = MecaStructError("A:B", "msg")
    assert err.identifier == "A:B"
    assert str(err) == "msg"


def test_utilitaires_listes_et_formats():
    assert as_list(None) == []
    assert as_list({"a": 1}) == [{"a": 1}]
    assert fmt_fr(1.5) == "1,5"
