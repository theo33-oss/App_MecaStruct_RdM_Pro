"""Graphiques des éléments de machines : zones de tolérance d'un ajustement et diagramme P-V d'un palier lisse.

Aucun calcul mécanique ici : on trace les sorties de mecastruct/services/machine.py.
"""

import numpy as np
import plotly.graph_objects as go

from mecastruct.core import plain_bearing
from mecastruct.plots._common import COULEUR


def fitZones(r: dict, alesage: str, arbre: str) -> go.Figure:
    """Zones de tolérance de l'alésage et de l'arbre autour de la ligne zéro (cote nominale), en µm.

    Entrées : `r` (sortie de fits.fit), `alesage`, `arbre` (désignations, ex. « H7 », « r6 »).
    """
    h, s = r["hole"], r["shaft"]
    fig = go.Figure()
    for (bas, haut), nom, coul in (
        ((h["EI"], h["ES"]), f"Alésage {alesage}", COULEUR["positif"]),
        ((s["ei"], s["es"]), f"Arbre {arbre}", COULEUR["negatif"]),
    ):
        fig.add_bar(x=[nom], y=[haut - bas], base=[bas], marker_color=coul, name=nom, width=0.5,
                    text=[f"{haut:+g} / {bas:+g} µm"], textposition="outside")  # fmt: skip
    fig.add_hline(y=0, line_color="black", annotation_text="ligne zéro (cote nominale)")
    fig.update_layout(title=f"Ajustement : {r['type']}", yaxis_title="Écart (µm)", showlegend=False)
    return fig


def pvDiagram(r: dict) -> go.Figure:
    """Courbe P limite(V) du matériau, en log-log, et point de fonctionnement (et celui de la collerette).

    Entrée : `r` (sortie de plain_bearing.plainBearing).
    """
    m = r["materiau"]
    V = np.logspace(-3, np.log10(m["Vmax"]), 200)
    P = [plain_bearing.pLimit(m, v) for v in V]
    fig = go.Figure()
    fig.add_scatter(x=V, y=P, mode="lines", name=f"Limite {m['Name']}", line={"width": 3}, fill="tozeroy")
    fig.add_scatter(x=[max(r["V"], 1e-3)], y=[r["P"]], mode="markers", name="Point de fonctionnement",
                    marker={"size": 12, "color": "red"})  # fmt: skip
    if r["collerette"]:
        c = r["collerette"]
        fig.add_scatter(x=[max(c["Va"], 1e-3)], y=[c["Pa"]], mode="markers", name="Collerette",
                        marker={"size": 11, "symbol": "diamond", "color": "orange"})  # fmt: skip
    fig.update_layout(title="Diagramme P-V : le point doit être sous la courbe", xaxis_type="log", yaxis_type="log",
                      xaxis_title="V (m/s)", yaxis_title="P (MPa)")  # fmt: skip
    return fig
