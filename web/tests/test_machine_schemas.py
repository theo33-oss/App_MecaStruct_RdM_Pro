"""Schémas des pages de cours : dentures qui engrènent sans se chevaucher, montage du train épicycloïdal, dessins qui
suivent la saisie dans les pages (avant « Calculer »).
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from mecastruct.core.errors import MecaStructError
from mecastruct.plots import machine_schemas as ms
from mecastruct.services import machine_courses as mc

PAGES = Path(__file__).resolve().parents[1] / "app_pages"


def _dedans(points: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Points strictement intérieurs au polygone fermé `poly` (lancer de rayon, règle pair-impair)."""
    # rayon légèrement décalé : sinon un rayon qui passe par un sommet compte deux traversées
    x, y = points[:, 0][:, None], points[:, 1][:, None] + 1e-7
    x1, y1, x2, y2 = poly[:-1, 0], poly[:-1, 1], poly[1:, 0], poly[1:, 1]
    croise = ((y1 > y) != (y2 > y)) & (x < x1 + (y - y1) * (x2 - x1) / np.where(y2 == y1, 1e-300, y2 - y1))
    return croise.sum(axis=1) % 2 == 1


def _distance(points: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Distance de chaque point au contour `poly` (plus petite distance aux segments)."""
    a, ab = poly[:-1], np.diff(poly, axis=0)
    t = np.clip(((points[:, None, :] - a) * ab).sum(-1) / np.maximum((ab**2).sum(-1), 1e-300), 0, 1)
    return np.min(np.linalg.norm(points[:, None, :] - (a + t[..., None] * ab), axis=-1), axis=1)


def _trace(fig, debut: str):
    return next(t for t in fig.data if t.name and t.name.startswith(debut))


def _xy(trace) -> np.ndarray:
    return np.column_stack([trace.x, trace.y])


@pytest.mark.parametrize("Z1, Z2, m", [(20, 40, 2.0), (18, 65, 3.0), (17, 17, 1.0), (31, 50, 2.5), (40, 200, 1.0)])
def test_pignon_et_roue_engrenent_sans_se_chevaucher(Z1, Z2, m):
    fig = ms.gearMesh({**mc.defaultGearInput(), "Z1": Z1, "Z2": Z2, "m": m})
    pignon, roue = _xy(_trace(fig, "Pignon")), _xy(_trace(fig, "Roue"))
    r1, r2 = m * Z1 / 2, m * Z2 / 2
    rayons = np.hypot(*pignon.T)
    assert rayons.max() == pytest.approx(r1 + m) and rayons.min() == pytest.approx(r1 - 1.25 * m)
    # dents dans les creux : aucun point de l'une dans l'autre, mais les deux roues se touchent presque au primitif
    assert not _dedans(roue, pignon).any() and not _dedans(pignon, roue).any()
    ecart = np.min(np.hypot(*(pignon[:, None, :] - roue[None, :, :]).transpose(2, 0, 1)))
    assert ecart < 0.15 * m
    assert np.hypot(*(roue - [r1 + r2, 0]).T).max() == pytest.approx(r2 + m)
    assert "interférence" not in fig.layout.title.text


def test_moins_de_17_dents_interference_signalee():
    fig = ms.gearMesh({**mc.defaultGearInput(), "Z1": 12, "Z2": 65, "m": 3.0})
    assert "interférence" in fig.layout.title.text  # Zmin = 2/sin²α ≈ 17 sans déport : les dents se chevauchent
    pignon, roue = _xy(_trace(fig, "Pignon")), _xy(_trace(fig, "Roue"))
    assert _dedans(roue, pignon).any()


def test_train_epicycloidal_monte_sans_chevauchement():
    s = mc.defaultPlanetaryInput()  # Z1 = 15, Z2 = 9, Z4 = 33, 3 satellites : montage possible
    fig = ms.planetaryTrain(s)
    assert "Conditions de montage vérifiées" in fig.layout.title.text
    soleil = _xy(_trace(fig, "Planétaire"))
    trou = _xy(next(t for t in fig.data if t.fillcolor == "white"))
    satellites = [_xy(t) for t in fig.data if t.name and t.name.startswith("Satellites")]
    assert len(satellites) == 3
    for sat in satellites:
        assert not _dedans(sat, soleil).any() and not _dedans(soleil, sat).any()
        # le satellite reste dans le creux de la couronne, aux cordes des développantes près (dessin en modules)
        dehors = sat[~_dedans(sat, trou)]
        assert len(dehors) == 0 or _distance(dehors, trou).max() < 0.01
    noms = " | ".join(t.name for t in fig.data if t.name)
    assert "Couronne Z4 = 33 : bloquée" in noms
    assert "Planétaire Z1 = 15 : entrée, 1500 tr/min" in noms
    assert "Porte-satellites : sortie, 468.8 tr/min" in noms


def test_train_epicycloidal_signale_un_montage_impossible():
    fig = ms.planetaryTrain({**mc.defaultPlanetaryInput(), "nSat": 5})  # (15 + 33)/5 non entier
    assert "Montage NON vérifié" in fig.layout.title.text
    fig = ms.planetaryTrain({**mc.defaultPlanetaryInput(), "entree": "couronne"})  # bloqué = entrée
    assert "Couronne Z4 = 33 : bloquée" in " ".join(t.name for t in fig.data if t.name)


def test_autres_schemas_avec_les_exemples():
    r = mc.computeBearingLife(mc.defaultBearingInput())["result"]
    figs = [
        ms.gearTrain(mc.defaultGearTrainInput()),
        ms.bearingSection(mc.defaultBearingInput()),
        ms.bearingSection({**mc.defaultBearingInput(), "Fr": 0.0, "type": "rouleaux"}),
        ms.bearingLife(r, mc.defaultBearingInput()),
        ms.bearingSet(mc.defaultBearingSetInput()),
        ms.brakeDisc(mc.defaultBrakeInput()),
        ms.brakePressure(mc.defaultBrakeInput()),
        ms.clutchSync(mc.defaultClutchInput()),
        ms.motorCycle(mc.defaultMotorInput()),
    ]
    assert all(len(f.data) > 0 for f in figs)
    # rayons équivalents du frein : (2/3)(Re³ − Ri³)/(Re² − Ri²) et (Re + Ri)/2
    noms = [t.name for t in figs[5].data if t.name and t.name.startswith("Rayon")]
    assert "97.19 mm" in noms[0] and "95 mm" in noms[1]
    assert "60.98 N·m" in " ".join(t.name for t in figs[8].data if t.name)  # C_th ≈ 61 N·m du cours
    assert "rapport total -0.03333" in figs[0].layout.title.text  # (−15/45)(−20/40)(−10/50) = −1/30


@pytest.mark.parametrize(
    "dessin, s",
    [
        (ms.gearMesh, {**mc.defaultGearInput(), "Z1": 3}),
        (ms.planetaryTrain, {**mc.defaultPlanetaryInput(), "nSat": 0}),
        (ms.brakeDisc, {**mc.defaultBrakeInput(), "Ri": 130.0}),
        (ms.clutchSync, {**mc.defaultClutchInput(), "ts": 0.0}),
        (ms.motorCycle, {**mc.defaultMotorInput(), "ta": 0.0, "tc": 0.0, "tfr": 0.0}),
    ],
)
def test_saisie_non_dessinable(dessin, s):
    with pytest.raises(MecaStructError):
        dessin(s)


def _titres(at) -> list[str]:
    return [json.loads(e.proto.spec)["layout"]["title"]["text"] for e in at.get("plotly_chart")]


def test_le_schema_des_engrenages_suit_la_saisie_avant_calculer():
    at = AppTest.from_file(str(PAGES / "engrenages.py"), default_timeout=60).run()
    assert not at.exception
    assert any("Z1 = 20" in t for t in _titres(at))
    at.number_input(key="eng.Z1").set_value(30.0).run()
    assert any("Z1 = 30" in t for t in _titres(at))  # redessiné sans cliquer sur « Calculer »


@pytest.mark.parametrize(
    "page", ["roulements", "engrenages", "epicycloidaux", "freins_embrayages", "dimensionnement_moteur"]
)
def test_chaque_page_affiche_ses_schemas(page):
    at = AppTest.from_file(str(PAGES / f"{page}.py"), default_timeout=60).run()
    assert not at.exception and not at.error
    attendus = {"roulements": 2, "engrenages": 2, "freins_embrayages": 2}.get(page, 1)  # un par onglet de calcul
    assert len(at.get("plotly_chart")) == attendus
    assert not any("Schéma indisponible" in c.value for c in at.caption)


def test_courbe_de_duree_apres_calcul():
    at = AppTest.from_file(str(PAGES / "roulements.py"), default_timeout=60).run()
    next(b for b in at.button if b.label == "Calculer").click().run()
    assert not at.exception
    assert any("Durée de vie" in t for t in _titres(at))
    assert math.isfinite(len(at.get("plotly_chart")))
