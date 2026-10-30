"""Graphiques de la page Sollicitations en Plotly (tracés inline de computeTraction, computeShear, computeTorsion).

Aucun calcul mécanique ici : on trace les profils fournis par services/compute.py (SI strict, affichage en MPa, mm).
"""

import numpy as np
import plotly.graph_objects as go

from mecastruct.plots._common import COULEUR


def tractionStress(x, N: float, Sx, Kt: float, sigmaAdm: float) -> go.Figure:
    """σxx(x) = N/S(x), Kt·σxx(x) et limite ± Re/s le long de la barre.

    Entrées : `x` (m), `Sx` (m², même longueur), `N` (N, > 0 traction), `Kt` (-), `sigmaAdm` (Pa).
    Sortie : figure Plotly, contraintes en MPa.
    """
    x, Sx = np.asarray(x, dtype=float), np.asarray(Sx, dtype=float)
    sigma = N / Sx / 1e6
    limite = (1.0 if N >= 0 else -1.0) * sigmaAdm / 1e6
    fig = go.Figure()
    fig.add_scatter(x=x, y=sigma, mode="lines", name="σ<sub>xx</sub>(x) = N/S(x)", line={"width": 3})
    fig.add_scatter(x=x, y=Kt * sigma, mode="lines", name="K<sub>t</sub> σ<sub>xx</sub>(x)", line={"dash": "dash"})
    fig.add_scatter(x=[x[0], x[-1]], y=[limite, limite], mode="lines", name="± R<sub>e</sub>/s", line={"dash": "dot"})
    fig.update_layout(
        title="Contrainte normale le long de la barre", xaxis_title="x (m)", yaxis_title="σ<sub>xx</sub> (MPa)"
    )
    return fig


def elongations(dL: dict) -> go.Figure:
    """Allongement ΔL par les 3 méthodes (analytique, intégrale, énergétique), en mm.

    Entrée : `dL` (dict analytique, integrale, energetique, en m).
    """
    vals = [dL["analytique"] * 1e3, dL["integrale"] * 1e3, dL["energetique"] * 1e3]
    fig = go.Figure(go.Bar(x=["Analytique", "Intégrale", "Énergétique"], y=vals, text=[f"{v:.5g}" for v in vals]))
    fig.update_layout(title="Allongement : 3 méthodes", yaxis_title="ΔL (mm)")
    return fig


def ratios(labels: list[str], vals: list[float], titre: str, utilisation: bool = True) -> go.Figure:
    """Barres de taux (rouge au-delà de 1) avec la ligne de limite à 1 si `utilisation` (plotRatios de MATLAB)."""
    couleurs = [COULEUR["negatif"] if utilisation and v > 1 else COULEUR["positif"] for v in vals]
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=couleurs, text=[f"{v:.4g}" for v in vals]))
    if utilisation:
        fig.add_hline(y=1.0, line_dash="dash", line_color="red")
    fig.update_layout(title=titre)
    return fig


def torsionStress(r: dict, D: float) -> go.Figure:
    """Répartition de τ(r) sur un diamètre, valeur maximale Kt·τmax et τadm.

    Entrées : `r` (sortie de solicitations.torsion : rProfile en m, tauProfile, tauMax, tauAdm en Pa) ; `D` (m).
    """
    rr, tt = np.asarray(r["rProfile"]) * 1e3, np.asarray(r["tauProfile"]) / 1e6
    fig = go.Figure()
    fig.add_scatter(x=rr, y=tt, mode="lines", name="τ(r) = M<sub>t</sub> r/I<sub>x</sub>", line={"width": 3})
    fig.add_scatter(x=-rr, y=-tt, mode="lines", line={"width": 3}, showlegend=False)
    bord = D / 2 * 1e3
    fig.add_scatter(
        x=[-bord, bord], y=[-r["tauMax"] / 1e6, r["tauMax"] / 1e6], mode="markers", name="K<sub>t</sub> τ<sub>max</sub>"
    )
    fig.add_scatter(
        x=[-bord, bord], y=[r["tauAdm"] / 1e6] * 2, mode="lines", name="τ<sub>adm</sub>", line={"dash": "dot"}
    )
    fig.update_layout(
        title="Répartition de la contrainte de torsion sur un diamètre", xaxis_title="r (mm)", yaxis_title="τ (MPa)"
    )
    return fig


def torsionAngle(L: float, theta: float, phi: float) -> go.Figure:
    """Rotation des sections φ(s) = θ s ; titre avec φ(L) en mrad et en degrés.

    Entrées : `L` (m), `theta` (rad/m), `phi` (rad, φ(L) analytique).
    """
    s = np.linspace(0.0, L, 101)
    fig = go.Figure(go.Scatter(x=s, y=theta * s * 1e3, mode="lines", line={"width": 3}))
    fig.update_layout(
        title=f"Rotation des sections : φ(L) = {phi * 1e3:.4g} mrad = {np.degrees(phi):.4g}°",
        xaxis_title="s (m)",
        yaxis_title="φ (mrad)",
    )
    return fig


def bendingMarks(fig: go.Figure, P: dict, bend: dict) -> go.Figure:
    """Ajoute à la figure de la section l'axe neutre et les points de σ max en traction et en compression.

    Entrées : `fig` (section_plots.section) ; `P` (propriétés : zG, yG en m) ; `bend` (bendingStress). Sortie : `fig`.
    """
    pts = np.asarray(bend["neutralAxis"]["points"], dtype=float)
    if np.all(np.isfinite(pts)):
        fig.add_scatter(
            x=(P["zG"] + pts[:, 1]) * 1e3,
            y=(P["yG"] + pts[:, 0]) * 1e3,
            mode="lines",
            name="Axe neutre",
            line={"dash": "dash", "color": "rgb(217,26,26)", "width": 2},
        )
    for cle, nom, symbole, couleur in (
        ("locMaxTraction", "σ max traction", "triangle-up", "rgb(217,26,26)"),
        ("locMaxCompression", "σ max compression", "triangle-down", "rgb(0,115,189)"),
    ):
        loc = bend[cle]
        fig.add_scatter(
            x=[(P["zG"] + loc[1]) * 1e3],
            y=[(P["yG"] + loc[0]) * 1e3],
            mode="markers",
            name=nom,
            marker={"symbol": symbole, "size": 11, "color": couleur},
        )
    return fig
