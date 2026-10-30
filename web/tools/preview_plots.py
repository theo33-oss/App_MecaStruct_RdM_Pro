"""Prévisualisation des graphiques Poutres : écrit les figures Plotly en HTML dans tools/out/ (outil de Théo).

Usage (depuis le dossier web/) : python tools/preview_plots.py
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from mecastruct.core.data_manager import DataManager  # noqa: E402
from mecastruct.plots.beam_plots import beamSchematic, deflection, internalForces, movingEnvelope  # noqa: E402
from mecastruct.services.beam_design import computeMovingLoad  # noqa: E402
from mecastruct.services.beam_services import computeBeam  # noqa: E402
from mecastruct.services.examples import loadExample  # noqa: E402

SORTIE = Path(__file__).resolve().parent / "out"
EXEMPLES = {"appui_appui": "isostatique", "console": "console", "deux_travees": "deuxtravees"}


def main() -> None:
    """Calcule les trois exemples et écrit leurs figures en HTML autonome."""
    SORTIE.mkdir(exist_ok=True)
    dm = DataManager()
    for nom, variante in EXEMPLES.items():
        saisie = loadExample("Beam", variante)
        r = computeBeam(saisie, dm)
        figures = {
            "schema": beamSchematic(r["model"], r["sol"]),
            "sollicitations": internalForces(r["sol"]),
            "deformee": deflection(r["model"], r["defl"]),
        }
        if nom == "appui_appui":
            _, env = computeMovingLoad(saisie, dm)
            figures["enveloppe"] = movingEnvelope(env)
        for suffixe, fig in figures.items():
            chemin = SORTIE / f"{nom}_{suffixe}.html"
            fig.write_html(chemin, include_plotlyjs=True, full_html=True)
            print(chemin)


if __name__ == "__main__":
    main()
