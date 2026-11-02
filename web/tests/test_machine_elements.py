"""Éléments de machines : ajustements ISO 286, frettage, paliers lisses, clavette normalisée, goupille sous couple.

Références : valeurs de l'ISO 286-2 et valeurs enregistrées dans les classeurs Excel de l'auteur (frettage,
paliers lisses), dont les modules de calcul étaient illisibles et ont été reconstruits.
"""

import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mecastruct.core import fits, key_pin, plain_bearing, shrink_fit
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError

PAGES = Path(__file__).resolve().parents[1] / "app_pages"


@pytest.mark.parametrize(
    ("lettre", "q", "ES", "EI"),
    [("K", 7, 6, -15), ("N", 7, -7, -28), ("P", 7, -14, -35), ("M", 7, 0, -21), ("JS", 7, 10, -10),
     ("J", 7, 12, -9), ("H", 7, 21, 0), ("G", 7, 28, 7)],
)  # fmt: skip
def test_alesages_iso286_a_30_mm(lettre, q, ES, EI):
    h = fits.holeDeviations(30, lettre, q)
    assert (h["ES"], h["EI"]) == (ES, EI)


@pytest.mark.parametrize(
    ("lettre", "q", "es", "ei"),
    [("js", 6, 6.5, -6.5), ("k", 6, 15, 2), ("h", 8, 0, -33), ("j", 6, 9, -4), ("f", 7, -20, -41),
     ("r", 6, 41, 28), ("p", 6, 35, 22), ("s", 6, 48, 35), ("g", 6, -7, -20)],
)  # fmt: skip
def test_arbres_iso286_a_30_mm(lettre, q, es, ei):
    s = fits.shaftDeviations(30, lettre, q)
    assert (s["es"], s["ei"]) == (es, ei)


def test_ajustement_h7_r6_et_classeur_ecarts():
    r = fits.fit(100, "H", 7, "r", 6)
    assert (r["serrageMin"], r["serrageMax"], r["type"]) == (16, 73, "serré")
    # feuille ANALYSE du classeur : Ø5, arbre h8 (0 / −18), alésage H7 (12 / 0), jeu 0 à 30 µm
    r = fits.fit(5, "H", 7, "h", 8)
    assert (r["jeuMin"], r["jeuMax"], r["type"]) == (0, 30, "avec jeu")


def test_ecart_inexistant_et_hors_table():
    with pytest.raises(MecaStructError):
        fits.shaftDeviations(5000, "h", 7)
    with pytest.raises(MecaStructError):
        fits.shaftDeviations(30, "j", 9)


def test_frettage_retrouve_le_classeur():
    """Exemple enregistré dans « Calculs de frettage normalises.xlsm » (Ø100 × 100, moyeu Ø280, E = 205 GPa)."""
    r = shrink_fit.shrinkFit(
        {
            "Fa": 0,
            "C": 750 / (12 * math.pi / 30),
            "f": 0.1,
            "s": 1.5,
            "d": 100,
            "di": 0,
            "D": 280,
            "L": 100,
            "Ea": 205e9,
            "nua": 0.3,
            "Rea": 300e6,
            "Em": 205e9,
            "num": 0.3,
            "Rem": 300e6,
            "alpham": 1.1e-5,
            "qa": 6,
            "qm": 7,
            "lissage": 5,
            "jeu": 0.2,
        }  # fmt: skip
    )
    assert r["pMin"] == pytest.approx(5.6993165798815006, rel=1e-12)
    assert r["K"] == pytest.approx(1.1182427613749821e-5, rel=1e-12)
    assert r["serrageUtile"] == pytest.approx(6.3732195102369085, rel=1e-12)
    assert r["eiRequis"] == pytest.approx(46.373219510236908, rel=1e-12)
    assert r["arbre"] == "r"
    assert r["pMax"] == pytest.approx(65.280994897959189, rel=1e-12)
    assert r["sigmaArbre"] == pytest.approx(130.56198979591838, rel=1e-12)
    assert r["sigmaMoyeu"] == pytest.approx(129.95164450051331, rel=1e-12)
    assert r["sArbre"] == pytest.approx(2.2977590987157166, rel=1e-12)
    assert r["sMoyeu"] == pytest.approx(2.3085510087470653, rel=1e-12)
    assert r["deltaT"] == pytest.approx(248.18181818181819, rel=1e-12)


def test_frettage_geometrie_invalide():
    with pytest.raises(MecaStructError):
        shrink_fit.shrinkFit({"d": 100, "D": 90, "L": 50, "f": 0.1, "s": 1})


def test_palier_lisse_retrouve_le_classeur():
    """Valeurs enregistrées dans « CALCULS PALIERS LISSES.xlsm » (bronze roulé, 403 N, 350 tr/min)."""
    m = plain_bearing.material("Bronze roulé")
    V = 0.15707963267948966
    assert plain_bearing.pLimit(m, V) * V == pytest.approx(0.69191376159182461, rel=1e-12)
    r = plain_bearing.plainBearing({"Fr": 403, "Fa": 100, "n": 350, "d": 12, "L": 15, "materiau": "Bronze roulé"})
    assert r["P"] == pytest.approx(2.2388888888888889, rel=1e-12)
    r = plain_bearing.plainBearing(
        {"Fr": 403, "Fa": 100, "n": 350, "d": 20, "L": 16, "Dfl": 30, "materiau": "Bronze roulé"}
    )
    assert r["V"] == pytest.approx(0.36651914291880916, rel=1e-12)
    assert r["collerette"]["Pa"] == pytest.approx(0.25464790894703254, rel=1e-12)
    assert r["collerette"]["Va"] == pytest.approx(0.54977871437821368, rel=1e-12)


def test_palier_oscillation_et_limites():
    m = plain_bearing.material("Bronze massif")
    assert plain_bearing.pLimit(m, 0.0005) == m["Pmax"]
    assert plain_bearing.pLimit(m, 0.01) == pytest.approx(m["Pdyn"])
    assert plain_bearing.pLimit(m, m["Vmax"]) == pytest.approx(1.0)
    r = plain_bearing.plainBearing({"Fr": 1000, "osc": 30, "beta": 45, "d": 20, "L": 20, "materiau": "POM"})
    assert r["oscillation"] and r["V"] == pytest.approx(4 * 45 / 360 * 30 / 60 * math.pi * 20 / 1000)


def test_clavette_normalisee_formules():
    r = key_pin.keyStandard({"C": 500, "d": 30, "L": 40, "forme": "A", "Padm": 100, "tauAdm": 100})
    assert (r["dims"]["b"], r["dims"]["h"], r["dims"]["t1"], r["Lp"]) == (8, 7, 4, 32)
    C = 500e3
    assert r["pArbre"] == pytest.approx(2 * C / (30 - 4) / (32 * 4))
    assert r["pMoyeu"] == pytest.approx(2 * C / (30 - 4 + 7) / (32 * 3))
    assert r["tau"] == pytest.approx(2 * C / 30 / (32 * 8))


def test_goupille_sous_couple_formules():
    r = key_pin.pinTorque({"montage": "transversale", "T": 50, "D": 30, "D1": 50, "d": 8, "Padm": 60, "tauAdm": 100})
    T, A = 50e3, math.pi * 64 / 4
    assert r["tau"] == pytest.approx(T / (30 * A))
    assert r["pMoyeu"] == pytest.approx(4 * T / (8 * (50**2 - 30**2)))
    r = key_pin.pinTorque({"montage": "longitudinale", "T": 50, "D": 30, "d": 8, "l": 30, "Padm": 60, "tauAdm": 100})
    assert r["tau"] == pytest.approx(2 * T / (30 * 8 * 30))


def test_nuances_du_classeur_dans_la_base():
    dm = DataManager()
    for nom in ("C45E (XC48) trempé-revenu", "100Cr6 (100C6) trempé-revenu", "EN-GJL-300 (FGL 300)"):
        assert dm.getMaterial(nom)["Re"] > 0
    assert dm.getMaterial("C45E (XC48) normalisé")["E"] == 210e9


@pytest.mark.parametrize("page", ["ajustements", "frettage", "paliers_lisses"])
def test_pages_calculent(page):
    at = AppTest.from_file(str(PAGES / f"{page}.py"), default_timeout=60).run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    assert not at.exception and not at.error
    assert any(t.label == "Explications du calcul" for t in at.tabs)
    assert len(at.latex) > 0
