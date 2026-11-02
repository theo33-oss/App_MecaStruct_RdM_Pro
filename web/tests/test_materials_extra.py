"""Matériaux complémentaires (web/data/materials_extra.json) : contenu, cohérence SI et branchement dans DataManager."""

import pytest

from mecastruct.core.data_manager import DataManager
from mecastruct.core.utils import load_json


def _extra() -> list[dict]:
    return load_json("materials_extra.json")


def test_materials_extra_contient_44_materiaux():
    assert len(_extra()) == 44


def test_aucun_nom_en_double_avec_materials_json():
    noms_base = {m["Name"] for m in load_json("materials.json")}
    noms_extra = [m["Name"] for m in _extra()]
    assert not noms_base & set(noms_extra)


def test_g_egale_e_sur_2_un_plus_nu():
    for m in _extra():
        assert m["G"] == pytest.approx(m["E"] / (2 * (1 + m["nu"])), rel=1e-12), m["Name"]


def test_bornes_si_et_provenance():
    for m in _extra():
        nom = m["Name"]
        assert 1e9 <= m["E"] <= 3e11, nom
        assert 0 < m["nu"] < 0.5, nom
        assert 0 < m["Re"] <= m["Rm"], nom
        assert 1e-7 < m["alpha"] < 2e-4, nom
        assert 1000 <= m["rho"] <= 9000, nom
        assert m["IsUser"] is False, nom
        assert m["Author"] == "Base complémentaire", nom


def test_listMaterials_ajoute_les_44_apres_les_51_de_base():
    noms = DataManager().listMaterials()
    base = [m["Name"] for m in load_json("materials.json")]
    assert len(noms) == 51 + 44
    assert noms[:51] == base


def test_getMaterial_acier_inoxydable_316L():
    m = DataManager().getMaterial("Inox 316L (X2CrNiMo17-12-2)")
    assert m["E"] == pytest.approx(195e9, rel=1e-12)
    assert m["Re"] == pytest.approx(170e6, rel=1e-12)
    assert m["Rm"] == pytest.approx(458e6, rel=1e-12)
    assert m["rho"] == pytest.approx(7900, rel=1e-12)


def test_s235_inchange_dans_la_base_matlab():
    assert DataManager().getMaterial("S235")["E"] == 210e9
