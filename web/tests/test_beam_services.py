"""Tests des services Poutres (saisie → modèle, calcul complet, combinaisons, charge rapide)."""

import logging
import math

import numpy as np
import pytest

from mecastruct.core import geometry
from mecastruct.core.beam_solver import solveBeam
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import ppEval
from mecastruct.services import beam_services
from mecastruct.services.beam_services import (
    addQuickLoad,
    beamCheck,
    beamThermal,
    buildBeamModel,
    caseFactor,
    computeBeam,
    computeCombinations,
    defaultBeamInput,
    distCoeffs,
    effortSheets,
)


@pytest.fixture(scope="module")
def dm():
    return DataManager()


def _ipe200_readme(dm):
    """Saisie du cas de référence du README : IPE 200, S235, E = 190 GPa, L = 4 m, q = −10 kN/m."""
    s = defaultBeamInput()
    p = dm.getProfile("IPE", "IPE 200")
    P = geometry.analytical(geometry.fromProfile(p))
    Pt = geometry.tabulated(geometry.fromProfile(p))
    s.update(
        {
            "L": 4.0,
            "E": 190.0,
            "G": 190.0 / 2.6,
            "S": p["S"] * 1e6,
            "Iz": p["Iz"] * 1e12,
            "Iy": p["Iy"] * 1e12,
            "Ix": P["J"] * 1e12,
            "ky": Pt["ky"],
            "kz": Pt["kz"],
            "vy": p["h"] / 2 * 1e3,
            "vz": p["b"] / 2 * 1e3,
            "sup": [{"pos": 0.0, "type": "pivot", "name": "A"}, {"pos": 4.0, "type": "appui_simple", "name": "B"}],
            "pl": [],
            "dl": [{"a": 0.0, "b": 4.0, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}],
            "Kt": 1.0,
            # sans tranchant dans Castigliano : les 4 méthodes concordent à 9,029 mm (avec tranchant : 9,296 mm)
            "shear": False,
        }
    )
    return s


# ---------------------------------------------------------------------------------------------
# Cas README
# ---------------------------------------------------------------------------------------------


def test_cas_readme_moment_contrainte_fleche(dm):
    s = _ipe200_readme(dm)
    r = computeBeam(s, dm)
    e = r["sol"]["extrema"]["Mfz"]
    assert max(abs(e["max"]), abs(e["min"])) == pytest.approx(20e3, rel=1e-9)
    assert r["check"]["bend"]["sigmaMaxKt"] / 1e6 == pytest.approx(102.9, rel=1e-3)
    d = r["defl"]
    for methode in ("integration", "aires", "castigliano", "mohr"):
        assert d[methode]["fmax"] * 1e3 == pytest.approx(9.029, rel=1e-3), methode
    assert r["unreliable"] is False
    assert "isostatique" in r["status"]


def test_computeBeam_renvoie_les_cles_du_contrat(dm):
    r = computeBeam(defaultBeamInput(), dm)
    assert set(r) == {"model", "sol", "defl", "energy", "check", "status", "unreliable"}
    assert r["status"].startswith("h = 0 (isostatique) — f max = ")


# ---------------------------------------------------------------------------------------------
# buildBeamModel
# ---------------------------------------------------------------------------------------------


def test_conversions_unites(dm):
    s = defaultBeamInput()
    m = buildBeamModel(s, dm)
    assert m["E"] == pytest.approx(s["E"] * 1e9)
    assert m["S"] == pytest.approx(s["S"] * 1e-6)
    assert m["Iz"] == pytest.approx(s["Iz"] * 1e-12)
    assert m["pointLoads"][0]["Fy"] == pytest.approx(-20e3)
    assert m["distLoads"][0]["coeffs"] == pytest.approx(np.array([-10e3]))


def test_cas_omis_si_coefficient_nul(dm):
    s = defaultBeamInput()
    m = buildBeamModel(s, dm, {"G": 1.0, "Q": 0.0, "W": 0.0, "S": 0.0})
    assert m["pointLoads"] == []
    assert len(m["distLoads"]) == 1


def test_poids_propre_et_tassements(dm):
    s = defaultBeamInput()
    s["selfw"] = True
    s["supx"] = [{"name": "B", "k": 0.0, "dx": 0.0, "dy": -10.0, "dz": 0.0}]
    m = buildBeamModel(s, dm, {"G": 1.5, "Q": 1.0, "W": 0.0, "S": 0.0})
    rho = dm.getMaterial("S235")["rho"]
    poids = [c for c in m["distLoads"] if c["name"] == "poids propre"][0]
    assert poids["coeffs"] == pytest.approx(-1.5 * rho * 9.80665 * m["S"])
    appuiB = [a for a in m["supports"] if a["name"] == "B"][0]
    assert appuiB["dy"] == pytest.approx(-10e-3 * 1.5)


def test_ressort_et_gradient_thermique(dm):
    s = defaultBeamInput()
    s["supx"] = [{"name": "B", "k": 5000.0, "dx": 0.0, "dy": 0.0, "dz": 0.0}]
    s["thGy"] = 20.0
    m = buildBeamModel(s, dm)
    assert [a for a in m["supports"] if a["name"] == "B"][0]["spring"] == pytest.approx(5e6, rel=1e-12)
    alpha = dm.getMaterial("S235")["alpha"]
    assert m["thermal"]["kv"] == pytest.approx(-alpha * 20 / (2 * s["vy"] * 1e-3), rel=1e-12)


def test_thermique_sans_fibre_extreme(dm):
    s = defaultBeamInput()
    s["thDT"] = 10.0
    th = beamThermal(s, dm)
    assert th["epsX"] == pytest.approx(dm.getMaterial("S235")["alpha"] * 10.0)
    s["vy"] = 0.0
    s["thGy"] = 5.0
    with pytest.raises(MecaStructError) as err:
        beamThermal(s, dm)
    assert err.value.identifier == "MecaStruct:App:invalidInput"


def test_iyz_trop_grand_refuse(dm):
    s = defaultBeamInput()
    s["Iyz"] = 2 * s["Iz"]
    with pytest.raises(MecaStructError):
        buildBeamModel(s, dm)


def test_cas_inconnu_refuse():
    with pytest.raises(MecaStructError) as err:
        caseFactor({"G": 1.0}, {"case": "X"})
    assert err.value.identifier == "MecaStruct:App:invalidInput"
    assert caseFactor({"G": 0.5, "Q": 1.5}, {}) == 0.5


# ---------------------------------------------------------------------------------------------
# distCoeffs
# ---------------------------------------------------------------------------------------------


def test_distCoeffs_uniforme_lineaire_polynomiale():
    assert distCoeffs("uniforme", "-10", 0.0, 4.0) == pytest.approx(np.array([-10.0]))
    assert distCoeffs("linéaire", "0 -10", 1.0, 3.0) == pytest.approx(np.array([-5.0, 0.0]))
    assert distCoeffs("polynomiale", "1; -2,5 3", 0.0, 2.0) == pytest.approx(np.array([1.0, -2.5, 3.0]))


def test_distCoeffs_erreurs():
    with pytest.raises(MecaStructError):
        distCoeffs("linéaire", "5", 0.0, 1.0)
    with pytest.raises(MecaStructError):
        distCoeffs("uniforme", "abc", 0.0, 1.0)
    with pytest.raises(MecaStructError):
        distCoeffs("inconnue", "1", 0.0, 1.0)


# ---------------------------------------------------------------------------------------------
# Combinaisons
# ---------------------------------------------------------------------------------------------


def _saisie_G_Q(dm):
    """Poutre IPE 300 : charge permanente uniforme (G) et force d'exploitation (Q) à 2 m."""
    s = defaultBeamInput()
    s["combo"] = [
        {"name": "ELS", "gG": 1.0, "gQ": 1.0, "gW": 0.0, "gS": 0.0},
        {"name": "ELU", "gG": 1.35, "gQ": 1.5, "gW": 0.0, "gS": 0.0},
    ]
    return s


def test_combinaisons_superposition_et_enveloppe(dm):
    s = _saisie_G_Q(dm)
    T = computeCombinations(s, dm)
    assert list(T["Combinaison"]) == ["ELS", "ELU", "Enveloppe"]

    grille = np.linspace(0.0, s["L"], 301)
    solG = solveBeam(buildBeamModel(s, dm, {"G": 1.0, "Q": 0.0, "W": 0.0, "S": 0.0}))
    solQ = solveBeam(buildBeamModel(s, dm, {"G": 0.0, "Q": 1.0, "W": 0.0, "S": 0.0}))
    ELU = solveBeam(buildBeamModel(s, dm, {"G": 1.35, "Q": 1.5, "W": 0.0, "S": 0.0}))
    attendu = 1.35 * ppEval(solG["Mfz"], grille) + 1.5 * ppEval(solQ["Mfz"], grille)
    assert ppEval(ELU["Mfz"], grille) == pytest.approx(attendu, abs=1e-6)
    assert T["Mfz max (kN·m)"].iloc[1] == pytest.approx(ELU["extrema"]["Mfz"]["max"] / 1e3, rel=1e-9)

    enveloppe = T.iloc[-1]
    assert enveloppe["f max (mm)"] == pytest.approx(T["f max (mm)"].iloc[:-1].max())
    assert enveloppe["Mfz max (kN·m)"] == pytest.approx(T["Mfz max (kN·m)"].iloc[:-1].max())


def test_combinaisons_vide_refuse(dm):
    s = defaultBeamInput()
    s["combo"] = []
    with pytest.raises(MecaStructError) as err:
        computeCombinations(s, dm)
    assert err.value.identifier == "MecaStruct:App:invalidInput"


def test_poids_propre_augmente_la_fleche(dm):
    s = defaultBeamInput()
    f0 = computeBeam(s, dm)["defl"]["integration"]["fmax"]
    s["selfw"] = True
    f1 = computeBeam(s, dm)["defl"]["integration"]["fmax"]
    assert f1 > f0


# ---------------------------------------------------------------------------------------------
# Charge rapide
# ---------------------------------------------------------------------------------------------


def test_charge_rapide_trapeze_et_erreur(dm):
    s = defaultBeamInput()
    n0 = len(s["dl"])
    s2 = addQuickLoad(s, "trapeze", 0.0, 6.0, -10.0, -20.0)
    assert len(s2["dl"]) == n0 + 1
    assert len(s["dl"]) == n0  # la saisie d'origine n'est pas modifiée
    ligne = s2["dl"][-1]
    assert ligne["type"] == "linéaire" and ligne["vals"] == "-10 -20"
    with pytest.raises(MecaStructError) as err:
        addQuickLoad(s, "uniforme", 3.0, 3.0, -10.0)
    assert err.value.identifier == "MecaStruct:App:invalidLoad"


def test_charge_rapide_uniforme_puis_calcul(dm):
    s = addQuickLoad(defaultBeamInput(), "uniforme", 0.0, 6.0, -10.0, case="G")
    r = computeBeam(s, dm)
    assert r["check"]["bend"]["ok"] in (True, False)


# ---------------------------------------------------------------------------------------------
# Vérification et feuilles d'efforts
# ---------------------------------------------------------------------------------------------


def test_beamCheck_point_et_rapport(dm):
    r = computeBeam(defaultBeamInput(), dm)
    chk = beamCheck(defaultBeamInput(), r["sol"], dm)
    assert chk["report"][0].startswith("Point le plus sollicité : s = ")
    assert 0.0 <= chk["s"] <= defaultBeamInput()["L"]
    assert math.isfinite(chk["bend"]["sigmaMaxKt"])


def test_effortSheets(dm):
    s = defaultBeamInput()
    sol = computeBeam(s, dm)["sol"]
    feuilles = effortSheets(sol)
    assert list(feuilles["Enveloppe"]["Effort"]) == ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]
    assert feuilles["Efforts"]["s (m)"].iloc[-1] == pytest.approx(s["L"])
    assert "Mfz (kN·m)" in feuilles["Efforts"].columns


def _trois_appuis(dm):
    """Poutre de 8 m sur trois appuis (A pivot, B et C simples), charge uniforme permanente de −10 kN/m."""
    s = defaultBeamInput()
    s.update(
        {
            "L": 8.0,
            "sup": [
                {"pos": 0.0, "type": "pivot", "name": "A"},
                {"pos": 4.0, "type": "appui_simple", "name": "B"},
                {"pos": 8.0, "type": "appui_simple", "name": "C"},
            ],
            "pl": [],
            "dl": [{"a": 0.0, "b": 8.0, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}],
        }
    )
    return s


def test_poutre_gerber_reactions(dm):
    s = _trois_appuis(dm)
    s["hg"] = [{"pos": 2.0, "name": "R1"}]
    ry = [r["Ry"] for r in computeBeam(s, dm)["sol"]["reactions"]]
    assert ry == pytest.approx([10e3, 60e3, 10e3], rel=1e-9)


def test_tassement_decharge_l_appui(dm):
    s = _trois_appuis(dm)
    ry0 = computeBeam(s, dm)["sol"]["reactions"][1]["Ry"]
    s["supx"] = [{"name": "B", "k": 0.0, "dx": 0.0, "dy": -10.0, "dz": 0.0}]
    ry1 = computeBeam(s, dm)["sol"]["reactions"][1]["Ry"]
    assert ry1 < ry0


def test_tranchant_castigliano_ecart_de_3_pour_cent(dm):
    s = _ipe200_readme(dm)
    s["shear"] = False
    f0 = computeBeam(s, dm)["defl"]
    s["shear"] = True
    f1 = computeBeam(s, dm)["defl"]
    assert f1["castigliano"]["fmax"] * 1e3 == pytest.approx(9.296, rel=1e-3)
    for methode in ("integration", "aires", "mohr"):
        assert f1[methode]["fmax"] == pytest.approx(f0[methode]["fmax"], rel=1e-12), methode
    assert defaultBeamInput()["shear"] is False


def test_combinaison_en_erreur_numerique_n_arrete_pas_les_autres(dm, monkeypatch, caplog):
    real_solve = beam_services.solveBeam

    def solve_defaillant(model, opts=None):
        # simule une erreur numérique inattendue pour la seule combinaison ELU (charge de −13,5 kN/m)
        if model["distLoads"] and model["distLoads"][0]["coeffs"][0] < -12e3:
            raise ValueError("matrice singulière simulée")
        return real_solve(model, opts)

    monkeypatch.setattr(beam_services, "solveBeam", solve_defaillant)
    s = defaultBeamInput()
    s["combo"] = [
        {"name": "ELS", "gG": 1.0, "gQ": 0.0, "gW": 0.0, "gS": 0.0},
        {"name": "ELU", "gG": 1.35, "gQ": 0.0, "gW": 0.0, "gS": 0.0},
        {"name": "ELS2", "gG": 1.0, "gQ": 0.0, "gW": 0.0, "gS": 0.0},
    ]
    with caplog.at_level(logging.ERROR, logger="mecastruct.services.beam_services"):
        T = computeCombinations(s, dm)
    assert T["Résistance"].iloc[1] == "Erreur de calcul (ValueError) : matrice singulière simulée"
    assert np.isnan(T["f max (mm)"].iloc[1])
    assert T["f max (mm)"].iloc[0] > 0 and T["f max (mm)"].iloc[2] > 0
    assert T["Résistance"].iloc[0] == "vérifié"
    assert T["f max (mm)"].iloc[3] == pytest.approx(T["f max (mm)"].iloc[[0, 2]].max())
    assert any("ELU" in r.getMessage() for r in caplog.records if r.exc_info)
