"""Prévisualisation des graphiques : écrit les figures Plotly en HTML dans tools/out/ (outil de Théo).

Usage (depuis le dossier web/) : python tools/preview_plots.py
Poutres (E21) : schéma, sollicitations, déformée, enveloppe mobile.
Sections et autres (E22) : section, contraintes, flambage, Mohr 2D et 3D, plasticité, treillis, abaques Kt.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from mecastruct.core import kt_mohr  # noqa: E402
from mecastruct.core.data_manager import DataManager  # noqa: E402
from mecastruct.plots.beam_plots import beamSchematic, deflection, internalForces, movingEnvelope  # noqa: E402
from mecastruct.plots.other_plots import bucklingCurve, ktChart, mohr2D, mohr3D, truss, yieldLocus  # noqa: E402
from mecastruct.plots.section_plots import section, sectionStress  # noqa: E402
from mecastruct.services import compute  # noqa: E402
from mecastruct.services.beam_design import computeMovingLoad  # noqa: E402
from mecastruct.services.beam_services import computeBeam  # noqa: E402
from mecastruct.services.examples import loadExample  # noqa: E402

SORTIE = Path(__file__).resolve().parent / "out"
EXEMPLES = {"appui_appui": "isostatique", "console": "console", "deux_travees": "deuxtravees"}


def _ecrit(figures: dict[str, object]) -> None:
    """Écrit chaque figure en HTML autonome dans SORTIE, en affichant son chemin."""
    for nom, fig in figures.items():
        chemin = SORTIE / f"{nom}.html"
        fig.write_html(chemin, include_plotlyjs=True, full_html=True)
        print(chemin)


def poutres(dm: DataManager) -> None:
    """Figures de l'E21 : schéma, efforts intérieurs, déformée (et enveloppe pour l'appui-appui)."""
    for nom, variante in EXEMPLES.items():
        saisie = loadExample("Beam", variante)
        r = computeBeam(saisie, dm)
        figures = {
            f"{nom}_schema": beamSchematic(r["model"], r["sol"]),
            f"{nom}_sollicitations": internalForces(r["sol"]),
            f"{nom}_deformee": deflection(r["model"], r["defl"]),
        }
        if nom == "appui_appui":
            _, env = computeMovingLoad(saisie, dm)
            figures[f"{nom}_enveloppe"] = movingEnvelope(env)
        _ecrit(figures)


def autres(dm: DataManager) -> None:
    """Figures de l'E22 : section, contraintes, flambage, Mohr, plasticité, treillis, abaques Kt."""
    section_calcul = compute.computeSection(loadExample("Sec"), dm)["result"]
    _ecrit(
        {
            "section_geometrie": section(section_calcul["sec"], section_calcul["P"]),
            "section_contraintes": sectionStress(
                section_calcul["sec"], section_calcul["P"], section_calcul["bend"], section_calcul["jour"]
            ),
        }
    )
    flambage = compute.computeBuckling(compute.defaultBucklingInput(), dm)["result"]
    tenseurs = compute.computeTensor(compute.defaultTensorInput(), dm)["result"]
    treillis = compute.computeTruss(compute.defaultTrussInput(), dm)["result"]
    _ecrit(
        {
            "flambage_courbe": bucklingCurve(flambage["curve"], flambage["analysis"]),
            "mohr_2D": mohr2D(tenseurs["plane2D"]),
            "mohr_3D": mohr3D(tenseurs["mohr3D"]),
            "plasticite": yieldLocus(tenseurs["loci"]),
            "treillis": truss(treillis["truss"], treillis["tsol"]),
        }
    )
    _ecrit({f"kt_{c['id']}": ktChart(c["id"]) for c in kt_mohr.ktCharts()})


def main() -> None:
    """Calcule les exemples et écrit toutes les figures en HTML autonome."""
    SORTIE.mkdir(exist_ok=True)
    dm = DataManager()
    poutres(dm)
    autres(dm)


if __name__ == "__main__":
    main()
