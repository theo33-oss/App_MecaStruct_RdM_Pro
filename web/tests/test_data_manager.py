"""Tests de DataManager (étape E03) : portage de tests/test_DataManager.m et cas de golden_datamanager.json.

Les tests des unités, des abaques Kt, de la table de Mohr et du rendu LaTeX ne sont pas ici :
ils sont dans test_units.py (E02) et dans les étapes E04 et suivantes.
"""

import importlib.util
import json
import math

import numpy as np
import pandas as pd
import pytest

from mecastruct.core.data_manager import (
    FAMILIES,
    DataManager,
    completeIsotropic,
    formulaKeys,
    formulaSheet,
    hasSymbolic,
)
from mecastruct.core.errors import MecaStructError
from tests.golden_tools import assert_matches, case_ids, get_case

GOLDEN = "golden_datamanager.json"
FORBIDDEN_LATEX = [
    r"\iint",
    r"\iiint",
    r"\implies",
    r"\text{",
    r"\dfrac",
    r"\tfrac",
    r"\boldsymbol",
    r"\geqslant",
    r"\leqslant",
    "pmatrix",
    "bmatrix",
    "{align",
    "{cases",
]


def verifier_erreur(identifiant, appel, *args):
    """Vérifie que l'appel lève une MecaStructError portant l'identifiant MATLAB attendu."""
    with pytest.raises(MecaStructError) as info:
        appel(*args)
    assert info.value.identifier == identifiant


# -------------------------------------------------------------------------------------------------
# Construction et propriétés
# -------------------------------------------------------------------------------------------------


def test_construction_par_defaut():
    dm = DataManager()
    assert {"Name", "Category", "E", "G", "nu", "Re", "Rm", "alpha", "rho", "Note", "IsUser"} <= set(dm.Materials)
    assert not dm.Materials["IsUser"].any()
    assert set(dm.Profiles) == set(FAMILIES)
    assert isinstance(dm.BearingPressures, pd.DataFrame)


def test_has_symbolic():
    assert isinstance(hasSymbolic(), bool)
    assert hasSymbolic() == (importlib.util.find_spec("sympy") is not None)


# -------------------------------------------------------------------------------------------------
# Matériaux
# -------------------------------------------------------------------------------------------------


def test_materiaux_valeurs_du_cours():
    dm = DataManager()
    assert all(isinstance(n, str) for n in dm.listMaterials())
    # Aciers d'usage général
    for nom, re_mpa, rm_mpa in [("S185", 185, 290), ("S235", 235, 340), ("S275", 275, 410), ("S355", 355, 490)]:
        m = dm.getMaterial(nom)
        assert m["E"] == 210e9
        assert m["nu"] == 0.3
        assert m["Re"] == re_mpa * 1e6
        assert m["Rm"] == rm_mpa * 1e6
        assert m["alpha"] == pytest.approx(12e-6, rel=1e-12)
        assert m["G"] == pytest.approx(210e9 / 2.6, rel=1e-12)
    # Aciers de construction mécanique
    for nom in ("XC 38", "XC 42", "XC 48"):
        m = dm.getMaterial(nom)
        assert m["E"] == 210e9
        assert m["G"] == 80e9
        assert m["nu"] == 0.3
        assert m["alpha"] == pytest.approx(11e-6, rel=1e-12)
        assert "12,5" in m["Note"]
        assert "usuelle" in m["Note"]
        assert m["Rm"] > m["Re"]
    # Aluminium
    m = dm.getMaterial("Aluminium 5356")
    assert [m["E"], m["G"], m["Re"], m["Rm"]] == [70e9, 27e9, 200e6, 300e6]
    assert "90 GPa" in m["Note"]
    assert 22.5e-6 <= m["alpha"] <= 24e-6
    m = dm.getMaterial("Aluminium 2017")
    assert [m["E"], m["G"], m["Re"], m["Rm"], m["rho"]] == [72.5e9, 27.2e9, 260e6, 380e6, 2790]
    assert "Euralliage" in m["Note"]
    assert 22.5e-6 <= m["alpha"] <= 24e-6
    m = dm.getMaterial("Aluminium 6061-T6")
    assert [m["E"], m["G"], m["Re"], m["Rm"], m["rho"]] == [70e9, 26.3e9, 240e6, 290e6, 2700]
    m = dm.getMaterial("Aluminium 7075-T6")
    assert [m["Re"], m["Rm"], m["rho"]] == [460e6, 520e6, 2810]
    m = dm.getMaterial("Bronze CuSn8 R450 (CW453K)")
    assert [m["Re"], m["Rm"], m["rho"]] == [280e6, 450e6, 8800]
    assert "valeurs usuelles" in m["Note"]
    assert sum("Euralliage" in n for n in dm.Materials["Note"]) > 25
    # Titane TA6V
    m = dm.getMaterial("Titane TA6V")
    assert [m["E"], m["Re"], m["Rm"]] == [116e9, 830e6, 900e6]
    assert "100 à 120" in m["Note"]
    assert "950" in m["Note"]
    assert 8.5e-6 <= m["alpha"] <= 9.5e-6
    # Fontes, laiton, Plexiglas
    assert dm.getMaterial("FGL 250")["G"] == 40e9
    assert dm.getMaterial("FGS 400-15")["G"] == 40e9
    assert dm.getMaterial("Laiton CuZn39Pb3")["G"] == 34e9
    pm = dm.getMaterial("Plexiglas")
    assert pm["G"] == 1.1e9
    assert "11 GPa" in pm["Note"]


def test_materiaux_coherence_globale():
    T = DataManager().Materials
    assert np.isfinite(T[["E", "G", "nu", "Re", "Rm", "alpha", "rho"]].to_numpy(dtype=float)).all()
    assert ((T["nu"] > -1) & (T["nu"] < 0.5)).all()
    assert (T["Rm"] >= T["Re"]).all()
    assert ((T["E"] > 1e9) & (T["E"] < 300e9)).all()  # SI strict (Pa)
    for _, r in T.iterrows():
        gth = r["E"] / (2 * (1 + r["nu"]))
        gap = abs(r["G"] - gth) / gth
        if "G calculé" in r["Note"] or "déduit" in r["Note"]:
            assert r["G"] == pytest.approx(gth, rel=1e-12), r["Name"]
        if gap > 0.05:
            assert "cohérence" in r["Note"], r["Name"]


def test_get_material_structure_et_erreurs():
    dm = DataManager()
    m = dm.getMaterial("xc38")
    assert m["Name"] == "XC 38"
    assert {"Name", "Category", "E", "G", "nu", "Re", "Rm", "alpha", "rho", "Note"} <= set(m)
    verifier_erreur("MecaStruct:DataManager:unknownMaterial", dm.getMaterial, "Unobtainium")


def test_complete_isotropic():
    m = completeIsotropic({"E": 200e9, "nu": 0.25})
    assert m["G"] == pytest.approx(80e9, rel=1e-12)
    m = completeIsotropic({"E": 210e9, "G": 80e9, "nu": math.nan})
    assert m["nu"] == pytest.approx(210 / 160 - 1, rel=1e-12)
    m = completeIsotropic({"G": 80e9, "nu": 0.3})
    assert m["E"] == pytest.approx(208e9, rel=1e-12)
    m = completeIsotropic({"E": 200e9, "G": 50e9, "nu": 0.3})
    assert "cohérence" in m["Note"]
    m = completeIsotropic({"E": 200e9})
    assert math.isnan(m["G"]) and math.isnan(m["nu"])
    verifier_erreur("MecaStruct:DataManager:invalidNu", completeIsotropic, {"E": 200e9, "nu": 0.6})
    verifier_erreur("MecaStruct:DataManager:invalidNu", completeIsotropic, {"E": 100e9, "G": 20e9})
    verifier_erreur("MecaStruct:DataManager:invalidModulus", completeIsotropic, {"E": -1, "nu": 0.3})


def test_complete_isotropic_nu_et_modules_absents():
    """ν contrôlé dans tous les cas ; E et G tous deux absents refusés."""
    verifier_erreur("MecaStruct:DataManager:invalidNu", completeIsotropic, {"E": 200e9, "G": 80e9, "nu": 0.7})
    verifier_erreur("MecaStruct:DataManager:invalidModulus", completeIsotropic, {"nu": 0.3})
    verifier_erreur("MecaStruct:DataManager:invalidModulus", completeIsotropic, {})


def test_ajout_materiau_bornes_plausibilite():
    """Matériau utilisateur : E, Re, Rm en Pa dans des plages plausibles, 0 < Re ≤ Rm."""
    dm = DataManager()
    base = {"Name": "Essai", "E": 200e9, "nu": 0.3, "Re": 300e6, "Rm": 450e6}
    for champ, valeur in [("E", 200.0), ("E", 1e12), ("Re", 300.0), ("Re", 0.0), ("Rm", 4e9), ("Re", math.inf)]:
        verifier_erreur("MecaStruct:DataManager:invalidMaterial", dm.addMaterial, {**base, champ: valeur})
    verifier_erreur("MecaStruct:DataManager:invalidMaterial", dm.addMaterial, {**base, "Re": 500e6})
    verifier_erreur("MecaStruct:DataManager:invalidMaterial", dm.addMaterial, {"Name": "x", "G": 1e9, "nu": 0.3})
    with pytest.raises(MecaStructError, match="en Pa"):
        dm.addMaterial({**base, "E": 200.0})
    dm.addMaterial(base)
    assert dm.getMaterial("Essai")["Re"] == 300e6


def test_ajout_suppression_materiau():
    dm = DataManager()
    n0 = len(dm.Materials)
    dm.addMaterial({"Name": "Mon acier", "E": 200e9, "nu": 0.3, "Re": 300e6, "Rm": 450e6})
    assert len(dm.Materials) == n0 + 1
    m = dm.getMaterial("Mon acier")
    assert m["G"] == pytest.approx(200e9 / 2.6, rel=1e-12)
    assert m["IsUser"] is True
    assert m["Author"] == "Utilisateur"
    assert dm.getMaterial("S235")["Author"] == "Base fournie"
    dm.addMaterial({"Name": "Acier de Théo", "E": 200e9, "nu": 0.3, "Author": " Théo "})
    assert dm.getMaterial("Acier de Théo")["Author"] == "Théo"
    dm.removeMaterial("Acier de Théo")
    # Remplacement d'un matériau utilisateur de même nom
    dm.addMaterial({"Name": "mon  ACIER", "E": 210e9, "nu": 0.3})
    assert len(dm.Materials) == n0 + 1
    assert dm.getMaterial("Mon acier")["E"] == 210e9
    # Surcharge d'un matériau par défaut, puis restauration
    dm.addMaterial({"Name": "S235", "E": 200e9, "nu": 0.3, "Re": 240e6, "Rm": 360e6})
    assert dm.getMaterial("S235")["E"] == 200e9
    dm.removeMaterial("S235")
    assert dm.getMaterial("S235")["E"] == 210e9
    assert dm.getMaterial("S235")["IsUser"] is False
    dm.removeMaterial("Mon acier")
    assert len(dm.Materials) == n0
    verifier_erreur("MecaStruct:DataManager:notUserMaterial", dm.removeMaterial, "S355")
    verifier_erreur("MecaStruct:DataManager:unknownMaterial", dm.removeMaterial, "Inconnu")
    verifier_erreur("MecaStruct:DataManager:invalidMaterial", dm.addMaterial, {"E": 1e9})


# -------------------------------------------------------------------------------------------------
# Profilés
# -------------------------------------------------------------------------------------------------


def test_catalogue_profils_contenu():
    dm = DataManager()
    assert dm.listProfileFamilies() == ["IPN", "IPE", "HEA", "HEB", "UPN", "UAP"]
    attendu = {
        "IPN": list(range(80, 301, 20)),
        "IPE": [80, 100, 120, 140, 160, 180, 200, 220, 240, 270, 300, 330, 360, 400, 450, 500, 550, 600],
        "HEA": list(range(100, 361, 20)) + list(range(400, 601, 50)),
        "HEB": list(range(100, 361, 20)) + list(range(400, 601, 50)),
        "UPN": list(range(80, 301, 20)),
        "UAP": [80, 100, 130, 150, 175, 200, 220, 250, 300],
    }
    for fam, tailles in attendu.items():
        assert dm.listProfiles(fam) == [f"{fam} {t}" for t in tailles]


def test_profils_coherence_du_catalogue():
    for fam, T in DataManager().Profiles.items():
        is_u = fam in ("UPN", "UAP")
        for r in T.to_dict("records"):
            lab = r["Name"]
            # SI strict
            assert 0.05 < r["h"] < 0.7 and 0.03 < r["b"] < 0.31 and r["S"] < 0.05, lab
            assert r["Iz"] > r["Iy"], lab
            assert r["rz"] == pytest.approx(math.sqrt(r["Iz"] / r["S"]), rel=0.02), lab
            assert r["ry"] == pytest.approx(math.sqrt(r["Iy"] / r["S"]), rel=0.02), lab
            assert r["Wz"] == pytest.approx(r["Iz"] / (r["h"] / 2), rel=0.02), lab
            sgeo = 2 * r["b"] * r["e"] + (r["h"] - 2 * r["e"]) * r["a"]
            assert r["S"] == pytest.approx(sgeo, rel=0.15), lab
            assert r["mass"] == pytest.approx(7850 * r["S"], rel=0.03), lab
            if is_u:
                assert math.isfinite(r["c"]) and 0 < r["c"] < r["b"] / 2, lab
                assert r["Wy"] == pytest.approx(r["Iy"] / (r["b"] - r["c"]), rel=0.02), lab
            else:
                assert math.isnan(r["c"]), lab
                assert r["Wy"] == pytest.approx(r["Iy"] / (r["b"] / 2), rel=0.02), lab
            assert not r["IsUser"], lab


def test_profils_valeurs_de_reference():
    dm = DataManager()
    p = dm.getProfile("IPE", "IPE 200")
    assert p["Family"] == "IPE"
    assert [p["h"], p["b"], p["a"], p["e"]] == pytest.approx([0.200, 0.100, 0.0056, 0.0085], rel=1e-12)
    assert p["S"] == pytest.approx(28.48e-4, rel=1e-12)
    assert p["Iz"] == pytest.approx(1943e-8, rel=1e-12)
    assert p["Iy"] == pytest.approx(142.4e-8, rel=1e-12)
    assert dm.getProfile("heb", 300)["Iz"] == pytest.approx(25170e-8, rel=1e-12)
    assert dm.getProfile("HEA", "HEA200")["h"] == pytest.approx(0.190, rel=1e-12)
    p = dm.getProfile("UPN", "100")
    assert p["c"] == pytest.approx(0.0155, rel=1e-12)
    assert {"Family", "Name", "h", "b", "a", "e", "r", "S", "Iz", "Iy", "Wz", "Wy", "rz", "ry", "mass", "c"} <= set(p)
    verifier_erreur("MecaStruct:DataManager:unknownProfile", dm.getProfile, "IPE", "IPE 210")
    verifier_erreur("MecaStruct:DataManager:unknownFamily", dm.getProfile, "XYZ", "IPE 200")


def test_ajout_profil_calcule_les_manquants():
    dm = DataManager()
    h, b, a, e = 0.2, 0.1, 0.006, 0.01
    dm.addProfile("IPE", {"Name": "200 perso", "h": h, "b": b, "a": a, "e": e})
    p = dm.getProfile("IPE", "IPE 200 perso")
    hw = h - 2 * e
    S = 2 * b * e + hw * a
    Iz = (b * h**3 - (b - a) * hw**3) / 12
    Iy = (2 * e * b**3 + hw * a**3) / 12
    assert p["S"] == pytest.approx(S, rel=1e-12)
    assert p["Iz"] == pytest.approx(Iz, rel=1e-12)
    assert p["Iy"] == pytest.approx(Iy, rel=1e-12)
    assert p["Wz"] == pytest.approx(Iz / (h / 2), rel=1e-12)
    assert p["Wy"] == pytest.approx(Iy / (b / 2), rel=1e-12)
    assert p["rz"] == pytest.approx(math.sqrt(Iz / S), rel=1e-12)
    assert p["ry"] == pytest.approx(math.sqrt(Iy / S), rel=1e-12)
    assert math.isnan(p["c"])
    assert p["IsUser"] is True
    # Profilé en U : c et Iy calculés autour du centre de gravité
    dm.addProfile("UPN", {"Name": "UPN X", "h": h, "b": b, "a": a, "e": e})
    q = dm.getProfile("UPN", "UPN X")
    c_ref = (e * b**2 + hw * a**2 / 2) / S
    iy_ref = 2 * (e * b**3 / 12 + e * b * (b / 2 - c_ref) ** 2) + hw * a**3 / 12 + hw * a * (a / 2 - c_ref) ** 2
    assert q["c"] == pytest.approx(c_ref, rel=1e-12)
    assert q["Iy"] == pytest.approx(iy_ref, rel=1e-12)
    assert q["Wy"] == pytest.approx(iy_ref / max(c_ref, b - c_ref), rel=1e-12)
    # Valeurs fournies conservées
    dm.addProfile("HEB", {"Name": "HEB 999", "h": 1, "b": 0.3, "a": 0.02, "e": 0.04, "Iz": 1e-2})
    assert dm.getProfile("HEB", 999)["Iz"] == 1e-2
    dm.removeProfile("HEB", 999)
    verifier_erreur("MecaStruct:DataManager:unknownProfile", dm.getProfile, "HEB", 999)
    verifier_erreur("MecaStruct:DataManager:notUserProfile", dm.removeProfile, "HEB", 300)
    verifier_erreur(
        "MecaStruct:DataManager:invalidProfile",
        dm.addProfile,
        "IPE",
        {"Name": "bad", "h": 0.1, "b": 0.1, "a": 0.01},
    )
    verifier_erreur(
        "MecaStruct:DataManager:invalidProfile",
        dm.addProfile,
        "IPE",
        {"Name": "bad", "h": 0.02, "b": 0.1, "a": 0.01, "e": 0.01},
    )


# -------------------------------------------------------------------------------------------------
# Formulaires
# -------------------------------------------------------------------------------------------------


def test_formules_cles():
    assert formulaKeys() == [
        "materiaux",
        "geometrie",
        "equilibre",
        "cohesion",
        "treillis",
        "traction",
        "cisaillement",
        "matage",
        "torsion",
        "flexion",
        "deformee",
        "energie",
        "mohr_integrales",
        "flambage",
        "tenseurs",
        "mohr_cercle",
        "criteres",
        "hooke",
        "extensometrie",
    ]
    verifier_erreur("MecaStruct:DataManager:unknownFormulaKey", formulaSheet, "inexistant")


def test_fiches_de_formules_structure():
    for key in formulaKeys():
        sheet = formulaSheet(key)
        assert len(sheet) >= 6, key
        for j, f in enumerate(sheet):
            lab = f"{key} #{j + 1}"
            assert set(f) == {"title", "latex", "vars"}, lab
            assert f["title"].strip() and f["vars"].strip(), lab
            assert f["latex"].startswith("$") and f["latex"].endswith("$"), lab
            assert all(ord(ch) < 128 for ch in f["latex"]), f"{lab} : caractère non ASCII"
            assert len(f["latex"]) < 1000, lab
            assert not any(cmd in f["latex"] for cmd in FORBIDDEN_LATEX), f"{lab} : commande interdite"


# -------------------------------------------------------------------------------------------------
# Pressions de matage
# -------------------------------------------------------------------------------------------------


def test_pressions_matage_table_par_defaut():
    dm = DataManager()
    T = dm.BearingPressures
    assert list(T.columns) == ["Liaison", "Conditions", "Pmin", "Pmax", "Note"]
    assert T["Pmin"].min() == 0.5e6
    assert T["Pmax"].max() == 150e6
    assert (T["Pmax"] >= T["Pmin"]).all()
    assert T["Conditions"].isin(["médiocres", "moyennes", "très bonnes"]).all()
    assert T["Note"].str.contains("usuelle").all()
    conditions = ["médiocres", "moyennes", "très bonnes"]
    ref = {
        "fixe": [(35, 50), (60, 100), (80, 150)],
        "glissant sans charge": [(15, 20), (20, 30), (25, 40)],
        "glissant sous charge": [(3, 10), (5, 15), (10, 20)],
    }
    for liaison, valeurs in ref.items():
        for cond, (lo, hi) in zip(conditions, valeurs):
            assert dm.getBearingPressure(liaison, cond) == (lo * 1e6, hi * 1e6), f"{liaison} {cond}"
    assert dm.getBearingPressure("Clavette / cannelures - fixe", "tres bonnes") == (80e6, 150e6)
    verifier_erreur("MecaStruct:DataManager:bearingNotFound", dm.getBearingPressure, "soudure", "moyennes")
    verifier_erreur("MecaStruct:DataManager:bearingAmbiguous", dm.getBearingPressure, "glissant", "moyennes")
    verifier_erreur("MecaStruct:DataManager:bearingNotFound", dm.getBearingPressure, "fixe", "excellentes")


def test_pressions_matage_modification():
    dm = DataManager()
    n0 = len(dm.BearingPressures)
    dm.setBearingPressure("Clavette / cannelures - fixe", "moyennes", 70e6, 90e6, "essai")
    assert dm.getBearingPressure("fixe", "moyennes") == (70e6, 90e6)
    assert len(dm.BearingPressures) == n0
    dm.setBearingPressure("Goupille", "moyennes", 20e6, 30e6)
    assert len(dm.BearingPressures) == n0 + 1
    verifier_erreur("MecaStruct:DataManager:invalidBearing", dm.setBearingPressure, "X", "moyennes", 30e6, 20e6)
    dm.resetBearingPressures()
    pd.testing.assert_frame_equal(dm.BearingPressures, DataManager().BearingPressures)


# -------------------------------------------------------------------------------------------------
# Données utilisateur (export / import à la place du fichier .mat)
# -------------------------------------------------------------------------------------------------


def test_export_import_donnees_utilisateur():
    dm = DataManager()
    dm.addMaterial(
        {
            "Name": "Alliage X",
            "Category": "Essai",
            "E": 70e9,
            "G": 26e9,
            "Re": 250e6,
            "Rm": 310e6,
            "alpha": 23e-6,
            "rho": 2700,
            "Note": "note",
        }
    )
    dm.addProfile("UAP", {"Name": "123", "h": 0.123, "b": 0.05, "a": 0.006, "e": 0.009})
    dm.setBearingPressure("Clavette / cannelures - fixe", "moyennes", 61e6, 99e6, "modifiée")
    donnees = json.loads(json.dumps(dm.exportUserData()))
    assert len(donnees["materials"]) == 1
    assert len(donnees["profiles"]["UAP"]) == 1
    assert len(donnees["profiles"]["IPE"]) == 0
    # Rechargement dans une base neuve
    dm2 = DataManager()
    assert dm2.importUserData(donnees) == 2
    assert dm2.getMaterial("Alliage X") == dm.getMaterial("Alliage X")
    assert dm2.getProfile("UAP", "UAP 123") == dm.getProfile("UAP", "UAP 123")
    assert dm2.getBearingPressure("fixe", "moyennes") == (61e6, 99e6)
    assert len(dm2.Materials) == len(dm.Materials)


def test_import_erreurs():
    dm = DataManager()
    verifier_erreur("MecaStruct:DataManager:invalidUserFile", dm.importUserData, "pas un dictionnaire")
    table_incomplete = {"bearing": [{"Liaison": "x", "Conditions": "moyennes", "Pmin": 30e6, "Pmax": 20e6}]}
    verifier_erreur("MecaStruct:DataManager:invalidUserFile", dm.importUserData, table_incomplete)
    table_inversee = {
        "bearing": [{"Liaison": "x", "Conditions": "moyennes", "Pmin": 30e6, "Pmax": 20e6, "Note": ""}],
    }
    verifier_erreur("MecaStruct:DataManager:invalidUserFile", dm.importUserData, table_inversee)


# -------------------------------------------------------------------------------------------------
# Golden : cas calculés par les fonctions MATLAB (golden_datamanager.json)
# -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", case_ids(GOLDEN, prefix="complete_"))
def test_golden_complete_isotropic(case_id):
    cas = get_case(GOLDEN, case_id)
    assert_matches(completeIsotropic(cas["entrees"]), cas["sortie"], rel=1e-12)


def test_golden_materiau_S235():
    cas = get_case(GOLDEN, "get_material_S235")
    assert_matches(DataManager().getMaterial(cas["entrees"]), cas["sortie"], rel=1e-12, ignore={"Note"})


def test_golden_profil_IPE200():
    cas = get_case(GOLDEN, "get_profile_IPE200")
    entrees = cas["entrees"]
    assert_matches(DataManager().getProfile(entrees["family"], entrees["name"]), cas["sortie"], rel=1e-12)


@pytest.mark.parametrize("case_id", case_ids(GOLDEN, prefix="bearing_"))
def test_golden_pressions_matage(case_id):
    cas = get_case(GOLDEN, case_id)
    pmin, pmax = DataManager().getBearingPressure(cas["entrees"]["liaison"], cas["entrees"]["conditions"])
    assert_matches({"pmin": pmin, "pmax": pmax}, cas["sortie"], rel=1e-12)
