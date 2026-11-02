"""Éléments de machines d'après les cours (IUT de Bordeaux) : roulements, engrenages, trains épicycloïdaux, freins et
embrayages, dimensionnement moteur.

Les exemples numériques sont ceux des cours quand ils sont cohérents. Deux écarts du cours sont fixés par les tests
(commentés aux endroits concernés) : l'interpolation de Y et la durée de l'exemple de roulement.
"""

import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mecastruct.core import bearings, brake_clutch, gears, planetary, transmission
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import machine_courses as mc

PAGES = Path(__file__).resolve().parents[1] / "app_pages"


# ------------------------------------------------------------------------------------------------- roulements


def test_ensembles_de_roulements_du_cours():
    # cours : 15 000 h et 25 000 h en série -> 11 630 h ; guidage de 15 000 h à deux roulements -> 23 811 h chacun
    assert bearings.lifeSet([15000, 25000]) == pytest.approx(11630, rel=1e-4)
    assert bearings.isoReliableLife(15000, 2) == pytest.approx(23811, rel=1e-4)


def test_fiabilite_du_cours():
    assert bearings.reliabilityFactor(0.96) == pytest.approx(0.53, abs=0.005)
    assert bearings.reliabilityFactor(0.9) == pytest.approx(1.0)
    with pytest.raises(MecaStructError):
        bearings.reliabilityFactor(1.0)


def test_interpolation_de_e_et_Y():
    # cours, Fa/C0 = 0,064 : e = 0,2657 (le cours écrit 0,0265) et Y = 1,664 (le cours écrit 1,59 : sens de la
    # pente inversé, Y doit décroître de 1,71 à 1,55 quand Fa/C0 augmente)
    e, Y = bearings.eYInterpolated(0.064)
    assert e == pytest.approx(0.26 + 0.02 * (0.008 / 0.028))
    assert Y == pytest.approx(1.55 + 0.16 * (0.02 / 0.028))
    with pytest.raises(MecaStructError):
        bearings.eYInterpolated(0.6)


def test_charge_equivalente_et_duree():
    assert bearings.dynamicLoad(10000, 2000, 0.3535, 0.56, 1.2558) == 10000  # Fa/Fr ≤ e : P = Fr
    assert bearings.dynamicLoad(10000, 4000, 0.3535, 0.56, 1.31) == pytest.approx(0.56 * 10000 + 1.31 * 4000)
    assert bearings.dynamicLoad(0, 5000, 0.3, 0.56, 1.2) == 5000  # butée : P = Fa
    # cours : C = 35,8 kN, P = 1084 daN (Y = 1,31). Le cours annonce L10 = 185,3 M tours (10 294 h), or (C/P)³ ≈ 36 M
    # tours, soit 2 001 h à 300 tr/min : l'écart est dans le cours, le calcul ci-dessous suit la formule.
    L10 = bearings.lifeMTours(35800, 10840, 3)
    assert L10 == pytest.approx(36.0, abs=0.1)
    assert bearings.lifeHours(L10, 300) == pytest.approx(2001, abs=2)
    assert bearings.dynamicRating(10840, 36.0, 3) == pytest.approx(35800, rel=1e-3)


def test_regles_de_montage_du_cours():
    # cours : bague tournante par rapport à la charge -> montée serrée ; bague fixe -> montée glissante
    assert bearings.mountingRule("intérieure", "tournante") == "serrée"
    assert bearings.mountingRule("extérieure", "fixe") == "glissante"
    # exemples du cours : Ø60 H7 / Ø40 k6 (bague intérieure tournante, charge normale) et Ø60 N7 / Ø40 g6
    assert bearings.fitRule("intérieure", "tournante", "normale") == ("arbre", "k5 à k6")
    assert bearings.fitRule("extérieure", "fixe", "normale") == ("alésage", "H7")
    assert bearings.fitRule("extérieure", "tournante", "normale") == ("alésage", "N7")
    assert bearings.fitRule("intérieure", "fixe", "constante") == ("arbre", "g6")
    with pytest.raises(MecaStructError):
        bearings.fitRule("intérieure", "fixe", "importante")


# ------------------------------------------------------------------------------------------------- engrenages


def test_geometrie_et_entraxe():
    g = gears.geometry(2, 20)
    assert g["d"] == 40
    assert g["p"] == pytest.approx(2 * math.pi)
    assert g["h"] == pytest.approx(4.5)  # 2,25·m
    assert gears.centerDistance(2, 20, 40) == pytest.approx(60)
    assert gears.ratio(20, 40) == pytest.approx(-0.5)


def test_efforts_sur_la_denture():
    f = gears.toothForces(10, 40)  # C = 10 N·m au diamètre 40 mm : Ft = 500 N
    assert f["Ft"] == pytest.approx(500)
    assert f["Fr"] == pytest.approx(500 * math.tan(math.radians(20)))
    assert f["Fn"] == pytest.approx(500 / math.cos(math.radians(20)))


def test_contrainte_de_pied_et_module_minimal():
    # le cours écrit la forme approchée 5,47·Ft/(k·m²) : la formule exacte 54/π² en est l'équivalent à 0,3 % près
    assert gears.rootStress(500, 2, 8) == pytest.approx(5.47 * 500 / (8 * 4), rel=3e-3)
    m = gears.moduleMini(500, 8, 150)
    assert gears.rootStress(500, m, 8) == pytest.approx(150)
    assert gears.normalizedModule(1.44) == 1.5
    with pytest.raises(MecaStructError):
        gears.normalizedModule(60)


def test_train_d_engrenages():
    # cours : rendement 0,98 par engrènement, 1000 W à 500 tr/min en entrée
    lignes = gears.gearTrain([(15, 45), (20, 40), (10, 50)], 1000, 500, 0.98)
    assert lignes[0]["C"] == pytest.approx(19.1, abs=0.01)
    assert lignes[-1]["P"] == pytest.approx(1000 * 0.98**3)
    assert lignes[-1]["N"] == pytest.approx(-500 / 30)  # trois engrènements : sens inversé, rapport 1/30
    assert lignes[-1]["C"] == pytest.approx(lignes[0]["C"] * 30 * 0.98**3)


# ------------------------------------------------------------------------------------ trains épicycloïdaux


def test_willis_exemple_du_cours():
    # cours : Z1 = 15, Z2 = 9, Z4 = 33 ; couronne bloquée, entrée 157 rad/s -> porte-satellites 49 rad/s
    rb = planetary.basicRatio(15, 9, 9, 33)
    assert rb == pytest.approx(-15 / 33)
    v = planetary.speeds(rb, "couronne", "planétaire", 157.0)  # vitesses en rad/s, comme dans le cours
    assert v["couronne"] == 0
    assert v["porte-satellites"] == pytest.approx(49.07, abs=0.01)
    assert v["couronne"] - v["porte-satellites"] == pytest.approx(rb * (v["planétaire"] - v["porte-satellites"]))


def test_willis_autre_configuration():
    rb = -15 / 33
    v = planetary.speeds(rb, "porte-satellites", "planétaire", 1500)  # porte-satellites bloqué : couronne = rb·entrée
    assert v["couronne"] == pytest.approx(rb * 1500)
    with pytest.raises(MecaStructError):
        planetary.speeds(rb, "couronne", "couronne", 1500)


def test_montage_du_train_du_cours():
    assert all(ok for _, _, ok in planetary.assemblyChecks(15, 9, 9, 33, 3))  # Z4 = Z1 + 2·Z2 et 48 / 3 entier
    assert not planetary.assemblyChecks(15, 9, 9, 34, 3)[0][2]


# ------------------------------------------------------------------------------------ freins et embrayages


def test_frein_pression_et_usure_constantes():
    # Re = 100 mm, Ri = 50 mm, F = 1000 N par surface, f = 0,3, n = 2
    C = brake_clutch.brakeTorque(1000, 0.3, 2, 100, 50, "pression")
    assert C == pytest.approx(2 * 0.3 * 1000 * (2 / 3) * (100**3 - 50**3) / (100**2 - 50**2) / 1000)
    assert brake_clutch.brakeTorque(1000, 0.3, 2, 100, 50, "usure") == pytest.approx(2 * 0.3 * 1000 * 75 / 1000)
    assert brake_clutch.maxPressure(1000, 100, 50, "pression") == pytest.approx(1000 / (math.pi * 7500))
    assert brake_clutch.maxPressure(1000, 100, 50, "usure") == pytest.approx(1000 / (2 * math.pi * 50 * 50))
    with pytest.raises(MecaStructError):
        brake_clutch.brakeTorque(1000, 0.3, 2, 50, 100, "pression")


def test_embrayage_exemple_du_cours():
    # cours : CM = 130 N·m, 1500 tr/min, JR = 1,2 kg·m², CR = −55 N·m ; couple d'accélération 18,8 N·m pour 10 s
    w = 2 * math.pi * 1500 / 60
    CT = brake_clutch.clutchTorqueFor(1.2, w, -55, 10)
    assert CT - 55 == pytest.approx(18.8, abs=0.1)
    assert brake_clutch.syncTime(1.2, w, CT, -55) == pytest.approx(10)
    assert brake_clutch.slipEnergy(CT, w, 10) == pytest.approx(CT * w * 5)
    with pytest.raises(MecaStructError):
        brake_clutch.syncTime(1.2, w, 50, -55)


# ---------------------------------------------------------------------------------- dimensionnement moteur


def test_couple_equivalent_thermique_et_choix_moteur():
    assert transmission.thermalTorque([(120, 1), (54, 1)]) == pytest.approx(math.sqrt((120**2 + 54**2) / 2))
    assert transmission.thermalTorque([(120, 1), (54, 13.3), (0, 0)]) == pytest.approx(61, abs=0.05)
    checks = transmission.motorChecks(61, 120, 1000, {"Cn": 63, "Cmax": 126, "Nmax": 1470})  # cours : moteur retenu
    assert all(ok for *_, ok in checks)
    assert not transmission.motorChecks(70, 120, 1000, {"Cn": 63, "Cmax": 126, "Nmax": 1470})[0][3]


def test_inertie_ramenee():
    assert transmission.reducedInertia(0.6, [(1.2, 1.0)]) == pytest.approx(1.8)
    assert transmission.reducedInertia(0.6, [(1.2, 2.0)]) == pytest.approx(0.9)
    with pytest.raises(MecaStructError):
        transmission.reducedInertia(0.6, [(1.2, 0.0)])


# ------------------------------------------------------------------------------------------- services et pages


def test_services_calculent_les_exemples():
    dm = DataManager()
    assert mc.computeBearingLife(mc.defaultBearingInput())["ok"] is True
    assert mc.computeBearingSet(mc.defaultBearingSetInput())["ok"] is None
    assert mc.computeGearMesh(mc.defaultGearInput(), dm)["ok"] is True
    assert mc.computePlanetary(mc.defaultPlanetaryInput())["result"]["r"] == pytest.approx(0.3125, rel=1e-3)
    assert mc.computeClutch(mc.defaultClutchInput())["ok"] is True
    assert mc.computeMotor(mc.defaultMotorInput())["result"]["Cth"] == pytest.approx(61, abs=0.1)


def test_service_signale_les_entrees_incoherentes():
    s = {**mc.defaultBearingInput(), "type": "rouleaux"}
    with pytest.raises(MecaStructError):
        mc.computeBearingLife(s)
    s = {**mc.defaultPlanetaryInput(), "entree": "couronne"}
    with pytest.raises(MecaStructError):
        mc.computePlanetary(s)
    with pytest.raises(MecaStructError):
        mc.computeGearMesh({**mc.defaultGearInput(), "N": 0.0}, DataManager())


def test_butee_et_charge_radiale_nulle():
    r = mc.computeBearingLife({**mc.defaultBearingInput(), "Fr": 0.0, "tableau": False, "e": 0.3, "X": 0.56, "Y": 1.2})
    assert r["result"]["P"] == pytest.approx(4000)  # butée : P = Fa
    assert r["result"]["L10"] == pytest.approx((35800 / 4000) ** 3)


@pytest.mark.parametrize(
    "page", ["roulements", "engrenages", "epicycloidaux", "freins_embrayages", "dimensionnement_moteur"]
)
def test_pages_calculent(page):
    at = AppTest.from_file(str(PAGES / f"{page}.py"), default_timeout=60).run()
    assert not at.exception and not at.error
    next(b for b in at.button if b.label == "Calculer").click().run()
    assert not at.exception and not at.error
    assert any(t.label == "Explications du calcul" for t in at.tabs)
    assert len(at.latex) > 0
