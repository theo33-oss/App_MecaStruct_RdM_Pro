"""Vérification à la main de l'Ossature 3D : bilan des actions nul et contrainte refaite égale à celle du solveur."""

import numpy as np
import pytest

from mecastruct.core import frame3d

NOMS = list(frame3d.exemples())


@pytest.mark.parametrize("nom", NOMS)
def test_bilan_nul_et_contrainte_refaite(nom):
    data = frame3d.exemples()[nom]
    res = frame3d.solveFrame3D(data)
    v = frame3d.verificationAMain(data, res)
    cats = v["bilan"]
    echelle = max(np.abs(cats["réactions"]["F"]).max(), np.abs(cats["réactions"]["M"]).max(), 1.0)
    assert np.abs(cats["somme"]["F"]).max() <= 1e-6 * echelle
    assert np.abs(cats["somme"]["M"]).max() <= 1e-6 * echelle
    for c in v["contraintes"]:
        if c["sigma"] is not None:
            assert c["sigma"] == pytest.approx(c["solveur"], rel=1e-9)
