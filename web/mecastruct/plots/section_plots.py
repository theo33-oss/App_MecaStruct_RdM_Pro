"""Graphiques de section en Plotly, port de PlotEngine.m : géométrie (section) et contraintes (sectionStress).

Aucun calcul mécanique ici : on trace les sorties de geometry.analytical, geometry.outline et des solicitations
(SI strict ; affichage en mm et MPa, comme MATLAB).
"""

import math

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mecastruct.core import geometry
from mecastruct.plots._common import COULEUR, arrow, legende, num, polyShape, rgb, teinte

_VERT = (0.10, 0.55, 0.20)
_CONTOUR = (0.55, 0.70, 0.90)
_AXES = (0.85, 0.15, 0.15)


def _cote(fig: go.Figure, p1, p2, texte: str, ou: str) -> None:
    """Cote entre p1 et p2 (mm) : double flèche et texte au milieu, décalé côté ou (below, above, left ou right)."""
    milieu = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    arrow(fig, milieu, p1, COULEUR["trait"], 1)
    arrow(fig, milieu, p2, COULEUR["trait"], 1)
    ancrage = {
        "below": dict(xanchor="center", yanchor="top", yshift=-4),
        "above": dict(xanchor="center", yanchor="bottom", yshift=4),
        "left": dict(xanchor="right", yanchor="middle", xshift=-4),
        "right": dict(xanchor="left", yanchor="middle", xshift=4),
    }[ou]
    fig.add_annotation(x=milieu[0], y=milieu[1], text=texte, showarrow=False, font=dict(size=10), **ancrage)


def section(sec: dict, P: dict | None = None) -> go.Figure:
    """Géométrie de la section : contour, G, axes (G, y, z), axes principaux, cotes (mm), axes égaux.

    Entrées : `sec` (section, dimensions en m) ; `P` (propriétés SI de geometry.analytical ; calculées si absent).
    Sortie : figure Plotly, z horizontal et y vertical, repère O1 (coin bas-gauche de la section).
    """
    if P is None:
        P = geometry.analytical(sec)
    out = geometry.outline(sec)
    k = 1e3
    fig = go.Figure()
    fond = rgb(_CONTOUR, 0.6)
    for contour in out["outer"]:
        polyShape(fig, np.asarray(contour) * k, COULEUR["trait"], 1.5, fond, True)
    for trou in out["holes"]:
        polyShape(fig, np.asarray(trou) * k, COULEUR["trait"], 1.5, "white", True)

    bb = np.asarray(out["bbox"], dtype=float) * k  # [zmin zmax ymin ymax]
    W, H = bb[1] - bb[0], bb[3] - bb[2]
    D = max(W, H)
    zG, yG = P["zG"] * k, P["yG"] * k
    cAx = rgb(_AXES)
    arrow(fig, (bb[0] - 0.12 * D, yG), (bb[1] + 0.18 * D, yG), cAx, 1.2)
    arrow(fig, (zG, bb[2] - 0.12 * D), (zG, bb[3] + 0.18 * D), cAx, 1.2)
    fig.add_annotation(
        x=bb[1] + 0.19 * D,
        y=yG,
        text="<i>z</i>",
        showarrow=False,
        font=dict(color=cAx, size=13),
        xanchor="left",
        yanchor="middle",
    )
    fig.add_annotation(
        x=zG, y=bb[3] + 0.19 * D, text="<i>y</i>", showarrow=False, font=dict(color=cAx, size=13), yanchor="bottom"
    )
    fig.add_trace(
        go.Scatter(
            x=[zG],
            y=[yG],
            mode="markers",
            marker=dict(color=cAx, size=8, line=dict(color=COULEUR["trait"], width=1)),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_annotation(
        x=zG + 0.02 * D,
        y=yG + 0.02 * D,
        text="<i>G</i>",
        showarrow=False,
        font=dict(size=13),
        xanchor="left",
        yanchor="bottom",
    )
    legende(fig, "Section", fond)
    legende(fig, "Axes (G, y, z)", cAx)

    # axes principaux, seulement si la section n'est pas symétrique (Iyz non nul)
    Iyz = float(P.get("Iyz", 0.0))
    if abs(Iyz) > 1e-9 * max(P["Iz"], P["Iy"]):
        a = P["alphaP"]
        cP = rgb(_VERT)
        Lp = 0.75 * D
        u1 = (math.cos(a), math.sin(a))
        u2 = (-math.sin(a), math.cos(a))
        for u in (u1, u2):
            fig.add_shape(
                type="line",
                x0=zG - Lp * u[0],
                y0=yG - Lp * u[1],
                x1=zG + Lp * u[0],
                y1=yG + Lp * u[1],
                line=dict(color=cP, width=1.4, dash="dash"),
            )
        for u, nom in ((u1, "1"), (u2, "2")):
            fig.add_annotation(
                x=zG + 1.02 * Lp * u[0],
                y=yG + 1.02 * Lp * u[1],
                text=f"<i>{nom}</i>",
                showarrow=False,
                font=dict(color=cP, size=12),
            )
        th = np.linspace(0, a, 30)
        polyShape(fig, np.column_stack([zG + 0.3 * D * np.cos(th), yG + 0.3 * D * np.sin(th)]), cP, 1)
        fig.add_annotation(
            x=zG + 0.32 * D * math.cos(a / 2),
            y=yG + 0.32 * D * math.sin(a / 2),
            text=f"α<sub>P</sub> = {num(math.degrees(a))}°",
            showarrow=False,
            font=dict(color=cP, size=10),
        )
        legende(
            fig,
            f"Axes principaux (I<sub>1</sub> = {num(P['I1'] * 1e12)}, I<sub>2</sub> = {num(P['I2'] * 1e12)} mm⁴)",
            cP,
            "dash",
        )

    # cotes : largeur, hauteur, positions de G
    _cote(fig, (bb[0], bb[2] - 0.25 * D), (bb[1], bb[2] - 0.25 * D), f"{num(W)} mm", "below")
    _cote(fig, (bb[0] - 0.25 * D, bb[2]), (bb[0] - 0.25 * D, bb[3]), f"{num(H)} mm", "left")
    _cote(fig, (bb[1] + 0.08 * D, bb[2]), (bb[1] + 0.08 * D, yG), f"y<sub>G</sub> = {num(yG - bb[2])}", "right")
    _cote(fig, (bb[0], bb[3] + 0.08 * D), (zG, bb[3] + 0.08 * D), f"z<sub>G</sub> = {num(zG - bb[0])}", "above")

    fig.update_xaxes(range=[bb[0] - 0.45 * D, bb[1] + 0.45 * D], title_text="z (mm)")
    fig.update_yaxes(range=[bb[2] - 0.40 * D, bb[3] + 0.30 * D], title_text="y (mm)", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title_text=(
            f"Section : S = {num(P['S'] * 1e6)} mm<sup>2</sup><br>"
            f"I<sub>Gz</sub> = {num(P['Iz'] * 1e12)} mm<sup>4</sup>, "
            f"I<sub>Gy</sub> = {num(P['Iy'] * 1e12)} mm<sup>4</sup>, "
            f"I<sub>yz</sub> = {num(Iyz * 1e12)} mm<sup>4</sup>"
        ),
        height=560,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5),
    )
    return fig


def sectionStress(sec: dict, P: dict | None, bend: dict | None, jour: dict | None) -> go.Figure:
    """Profils de contraintes dans la section : σxx(y) avec axe neutre, et τ(y) de Jourawski avec parabole et τmoy.

    Entrées : `sec` et `P` (section et propriétés, P calculé si absent) ; `bend` (solicitations.bendingStress) et
    `jour` (solicitations.jourawski) ; un résultat absent (None) n'est pas tracé.
    Sortie : figure Plotly à deux sous-graphes, y depuis G en mm, contraintes en MPa.
    """
    if P is None:
        P = geometry.analytical(sec)
    yTop, yBot = P["vyTop"] * 1e3, -P["vyBot"] * 1e3
    dy = yTop - yBot
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Contrainte normale σ<sub>xx</sub>(y)", "Contrainte de cisaillement τ(y)"),
        horizontal_spacing=0.14,
    )
    sMax = 1.0
    if bend is not None:
        y = np.asarray(bend["yProfile"], dtype=float).ravel() * 1e3
        sg = np.asarray(bend["sigmaProfile"], dtype=float).ravel() / 1e6
        sMax = float(np.max(np.abs(sg))) or 1.0
        for vals, nom, couleur in (
            (np.maximum(sg, 0.0), "Traction", "negatif"),
            (np.minimum(sg, 0.0), "Compression", "positif"),
        ):
            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([vals, np.zeros_like(vals)[::-1]]),
                    y=np.concatenate([y, y[::-1]]),
                    fill="toself",
                    fillcolor=teinte(couleur, 0.3),
                    line=dict(width=0),
                    name=nom,
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )
        fig.add_trace(
            go.Scatter(
                x=[0.0, 0.0],
                y=[yBot, yTop],
                mode="lines",
                line=dict(color=COULEUR["trait"], width=2.5),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=sg,
                y=y,
                mode="lines",
                line=dict(color=COULEUR["trait"], width=1.8),
                name="σ<sub>xx</sub>(y) à z = 0",
            ),
            row=1,
            col=1,
        )
        # axe neutre : a + b·y = 0 (z = 0), tracé s'il est dans la section
        na = bend.get("neutralAxis")
        if isinstance(na, dict) and float(na.get("b", 0.0)) != 0.0:
            yn = -float(na["a"]) / float(na["b"]) * 1e3
            if yBot - 1e-9 <= yn <= yTop + 1e-9:
                fig.add_trace(
                    go.Scatter(
                        x=[-1.3 * sMax, 1.3 * sMax],
                        y=[yn, yn],
                        mode="lines",
                        line=dict(color=rgb(_VERT), width=1.5, dash="dash"),
                        name=f"Axe neutre (y = {num(yn)} mm)",
                    ),
                    row=1,
                    col=1,
                )
        for i, ancrage in ((int(np.argmax(y)), "bottom"), (int(np.argmin(y)), "top")):
            fig.add_annotation(
                x=sg[i],
                y=y[i],
                row=1,
                col=1,
                text=f"{num(sg[i])} MPa",
                showarrow=False,
                font=dict(color=COULEUR["trait"], size=10),
                xanchor="right" if sg[i] < 0 else "left",
                yanchor=ancrage,
            )
        fig.update_xaxes(range=[-1.5 * sMax, 1.5 * sMax], title_text="σ<sub>xx</sub> (MPa)", row=1, col=1)

    if jour is not None:
        y = np.asarray(jour["y"], dtype=float).ravel() * 1e3
        t = np.asarray(jour["tau"], dtype=float).ravel() / 1e6
        tM, yM = float(jour["tauMax"]) / 1e6, float(jour["yAtMax"]) * 1e3
        tAbs = float(np.max(np.abs(np.concatenate([t, [tM]])))) or 1.0
        fig.add_trace(
            go.Scatter(
                x=np.concatenate([t, np.zeros_like(t)[::-1]]),
                y=np.concatenate([y, y[::-1]]),
                fill="toself",
                fillcolor=teinte("castigliano_tranchant", 0.25),
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=2,
        )
        fig.add_trace(
            go.Scatter(
                x=[0.0, 0.0],
                y=[yBot, yTop],
                mode="lines",
                line=dict(color=COULEUR["trait"], width=2.5),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=2,
        )
        fig.add_trace(
            go.Scatter(
                x=t,
                y=y,
                mode="lines",
                line=dict(color=COULEUR["castigliano_tranchant"], width=1.8),
                name="Jourawski τ(y) = T·Q(y)/(I<sub>z</sub>·b(y))",
            ),
            row=1,
            col=2,
        )
        # parabole de référence : seulement pour une section où elle est définie (sinon NaN)
        tp = np.asarray(jour.get("tauParabola", np.nan), dtype=float).ravel()
        if tp.size == y.size and np.any(np.isfinite(tp)):
            fig.add_trace(
                go.Scatter(
                    x=tp / 1e6,
                    y=y,
                    mode="lines",
                    line=dict(color=COULEUR["trait"], width=1.8, dash="dot"),
                    name="Parabole 3T/(2S)·(1 − 4y²/h²)",
                ),
                row=1,
                col=2,
            )
        if "tauMoy" in jour:
            tm = float(jour["tauMoy"]) / 1e6
            fig.add_trace(
                go.Scatter(
                    x=[tm, tm],
                    y=[yBot, yTop],
                    mode="lines",
                    line=dict(color=rgb(_VERT), width=1.2, dash="dash"),
                    name=f"τ<sub>moy</sub> = T/S = {num(tm)} MPa",
                ),
                row=1,
                col=2,
            )
        fig.add_trace(
            go.Scatter(
                x=[tM],
                y=[yM],
                mode="markers",
                marker=dict(color=COULEUR["castigliano_tranchant"], size=7),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1,
            col=2,
        )
        fig.add_annotation(
            x=tM,
            y=yM + 0.05 * dy,
            row=1,
            col=2,
            text=f"τ<sub>max</sub> = {num(tM)} MPa",
            showarrow=False,
            font=dict(color=COULEUR["trait"], size=10),
            xanchor="center",
            yanchor="bottom",
            bgcolor="white",
        )
        xr = [-0.15 * tAbs, 1.6 * tAbs] if tM >= 0 else [-1.6 * tAbs, 0.15 * tAbs]
        fig.update_xaxes(range=xr, title_text="τ<sub>xy</sub> (MPa)", row=1, col=2)

    fig.update_yaxes(range=[yBot - 0.15 * dy, yTop + 0.15 * dy], title_text="y (mm)")
    fig.update_layout(
        title_text="Contraintes dans la section",
        height=480,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
    )
    return fig
