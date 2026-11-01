"""Cas d'école du mode Ossature 3D : chacun se calcule sans mécanisme, s'équilibre et a son explication."""

import pytest

from app_pages import exemples_3d
from mecastruct.core import frame3d
from mecastruct.core.data_manager import DataManager

DM = DataManager()
EXEMPLES = exemples_3d.exemples(DM)


@pytest.mark.parametrize("nom", list(EXEMPLES))
def test_exemple_resolu_et_equilibre(nom):
    r = frame3d.solveFrame3D(EXEMPLES[nom])
    assert r["equilibre"]["ok"]
    assert 0 < r["deplacement_max"]["valeur"] < 0.1  # moins de 10 cm : structure raisonnable, pas un mécanisme caché
    assert nom in exemples_3d.EXPLICATIONS


def test_poutre_triangulaire_diagonales_articulees():
    """Diagonales articulées : moments nuls aux deux bouts et pas de torsion (seul le poids propre les fléchit)."""
    d = EXEMPLES["Poutre treillis triangulaire"]
    r = frame3d.solveFrame3D(d)
    for e in d["elements"]:
        if e.get("liaison_i") == "articulee":
            ef = r["efforts"][e["id"]]
            bouts = [ef[c][k] for c in ("My", "Mz") for k in (0, -1)] + ef["T"]
            assert max(map(abs, bouts)) < 1e-6
