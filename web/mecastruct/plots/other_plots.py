"""Autres graphiques en Plotly, port de PlotEngine.m : flambage, Mohr 2D et 3D, lieux de plasticité, treillis, Kt.

Aucun calcul mécanique ici : on trace les sorties des moteurs (SI strict ; affichage en MPa, mm, kN).
"""

import math

import numpy as np
import plotly.graph_objects as go

from mecastruct.core import kt_mohr
from mecastruct.core.errors import MecaStructError
from mecastruct.plots._common import COULEUR, arrow, legende, num, polyShape, rgb, support, teinte

_ID_KT = "MecaStruct:PlotEngine:unknownKt"
_GRIS = (0.75, 0.75, 0.75)
_GRIS_NUL = (0.60, 0.60, 0.60)
_JAUNE = (0.93, 0.69, 0.13)
_VERT = (0.10, 0.55, 0.20)
_VIOLET = (0.49, 0.18, 0.56)
_ROUGE = (0.85, 0.15, 0.15)
_BLEU_CLAIR = (0.30, 0.60, 0.90)


def _ancrageH(x: float, L: float) -> str:
    """Ancrage horizontal d'une étiquette placée au point d'abscisse x (à droite si x > 0,6 L)."""
    return "right" if x > 0.6 * L else "left"


def _trace(pts, dim3: bool, **kw):
    """Trace d'une polyligne N×3 (x, y, z) : go.Scatter en 2D (z ignoré), go.Scatter3d en 3D."""
    pts = np.asarray(pts, dtype=float)
    if dim3:
        return go.Scatter3d(x=pts[:, 0], y=pts[:, 1], z=pts[:, 2], **kw)
    return go.Scatter(x=pts[:, 0], y=pts[:, 1], **kw)


def bucklingCurve(curve: dict, b: dict | None = None) -> go.Figure:
    """Courbe de stabilité σcr(λ) : palier, Euler, Rankine, dimensionnement, point critique et de fonctionnement.

    Entrées : `curve` (buckling.stabilityCurve) ; `b` (buckling.analyze, optionnel) pour le point critique
    (λ, Pcrit/S) et le point de fonctionnement (λ, P/S). Affichage en MPa.
    Sortie : figure Plotly, zones de régime ombrées, droites λ = λ_compression et λ = λ_lim.
    """
    lam = np.asarray(curve["lambda"], dtype=float).ravel()
    Re = float(curve["Re"]) / 1e6
    lc, ll = float(curve["lambdaCompression"]), float(curve["lambdaLim"])
    lMax = float(lam.max())
    yMax = 1.35 * Re
    fig = go.Figure()

    # zones de régime : trapue (compression), moyenne (Rankine), élancée (Euler)
    zc = [_GRIS, _JAUNE, _BLEU_CLAIR]
    zx = [(0.0, min(lc, ll)), (min(lc, ll), ll), (ll, max(ll, lMax))]
    zl = [
        f"Poutre trapue (courte)<br>λ &lt; {num(lc)} : compression simple",
        f"Poutre moyenne<br>{num(lc)} ≤ λ &lt; λ<sub>lim</sub><br>Rankine",
        "Poutre élancée (longue)<br>λ ≥ λ<sub>lim</sub> : Euler",
    ]
    zn = [f"Poutre trapue (courte) : λ &lt; {num(lc)}", "Poutre moyenne : Rankine", "Poutre élancée (longue) : Euler"]
    actif = None
    if b is not None and "regime" in b:
        actif = {"compression": 0, "rankine": 1, "euler": 2}.get(str(b["regime"]))
    for k, (x0, x1) in enumerate(zx):
        if x1 <= x0:
            continue
        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=0,
            y1=yMax,
            fillcolor=rgb(zc[k], 0.16 + 0.10 * (k == actif)),
            line=dict(width=0),
            layer="below",
        )
        couleur, txt = COULEUR["trait"], zl[k]
        if k == actif:
            couleur, txt = rgb(_ROUGE), f"{zl[k]}<br>(votre poutre)"
        milieu = (x0 + x1) / 2
        if x1 - x0 < 0.15 * lMax:
            # zone étroite : étiquette verticale, sous le palier (zone vide)
            t1 = zn[k] + ("  (votre poutre)" if k == actif else "")
            fig.add_annotation(
                x=milieu,
                y=0.45 * yMax,
                text=f"<b>{t1}</b>",
                textangle=-90,
                showarrow=False,
                font=dict(color=couleur, size=10),
            )
        else:
            fig.add_annotation(
                x=milieu,
                y=0.985 * yMax,
                text=f"<b>{txt}</b>",
                showarrow=False,
                yanchor="top",
                font=dict(color=couleur, size=10),
            )

    fig.add_trace(
        go.Scatter(
            x=lam,
            y=np.asarray(curve["sigmaPalier"], dtype=float) / 1e6,
            mode="lines",
            line=dict(color="#666666", width=1.2, dash="dash"),
            name="Palier σ = R<sub>e</sub>",
        )
    )
    sE = np.asarray(curve["sigmaEuler"], dtype=float) / 1e6
    fig.add_trace(
        go.Scatter(
            x=lam,
            y=np.where(sE > yMax, np.nan, sE),
            mode="lines",
            line=dict(color=COULEUR["positif"], width=1.6, dash="dot"),
            name="Euler π²E/λ²",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=lam,
            y=np.asarray(curve["sigmaRankine"], dtype=float) / 1e6,
            mode="lines",
            line=dict(color=COULEUR["aires"], width=1.4, dash="dashdot"),
            name="Rankine Re/(1+(λ/λ<sub>lim</sub>)²)",
        )
    )
    # la courbe de dimensionnement est coupée là où le régime change (comme MATLAB)
    zone = curve.get("zone")
    jmp = np.nonzero(np.diff(np.asarray(zone).ravel()))[0] if zone is not None else np.array([], dtype=int)
    fig.add_trace(
        go.Scatter(
            x=np.insert(lam, jmp + 1, np.nan),
            y=np.insert(np.asarray(curve["sigmaDesign"], dtype=float) / 1e6, jmp + 1, np.nan),
            mode="lines",
            line=dict(color=COULEUR["trait"], width=2.5),
            name="Dimensionnement",
        )
    )
    for seuil, texte in ((lc, f"λ = {num(lc)}"), (ll, f"λ<sub>lim</sub> = {num(ll)}")):
        fig.add_shape(type="line", x0=seuil, x1=seuil, y0=0, y1=yMax, line=dict(color=COULEUR["trait"], width=1))
        fig.add_annotation(
            x=seuil,
            y=0.02 * yMax,
            text=texte,
            textangle=-90,
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=10),
        )

    if b is not None and "lambda" in b:
        lb = float(b["lambda"])
        sc = float(b["Pcrit"]) / float(b["S"]) / 1e6
        rg = str(b["regime"])
        fig.add_trace(
            go.Scatter(
                x=[lb],
                y=[sc],
                mode="markers",
                marker=dict(symbol="pentagon", size=13, color=rgb(_ROUGE)),
                name=f"Point critique ({rg[:1].upper()}{rg[1:]})",
            )
        )
        fig.add_annotation(
            x=lb,
            y=sc + 0.05 * yMax,
            text=f"λ = {num(lb)}, σ<sub>cr</sub> = {num(sc)} MPa",
            showarrow=False,
            xanchor=_ancrageH(lb, lMax),
            yanchor="bottom",
            bgcolor="white",
            font=dict(size=10),
        )
        if b.get("sigmaApplied") is not None and math.isfinite(float(b["sigmaApplied"])):
            sa = float(b["sigmaApplied"]) / 1e6
            fig.add_shape(type="line", x0=lb, x1=lb, y0=sa, y1=sc, line=dict(color=rgb(_VERT), width=1.2, dash="dot"))
            fig.add_trace(
                go.Scatter(
                    x=[lb],
                    y=[sa],
                    mode="markers",
                    marker=dict(symbol="circle", size=9, color=rgb(_VERT)),
                    name="Point de fonctionnement",
                )
            )
            fig.add_annotation(
                x=lb,
                y=sa - 0.05 * yMax,
                text=f"σ = P/S = {num(sa)} MPa",
                showarrow=False,
                xanchor=_ancrageH(lb, lMax),
                yanchor="top",
                bgcolor="white",
                font=dict(color=rgb(_VERT), size=10),
            )

    fig.update_xaxes(range=[0, lMax], title_text="λ = L'/r<sub>min</sub>")
    fig.update_yaxes(range=[0, yMax], title_text="σ<sub>cr</sub> (MPa)")
    fig.update_layout(
        title_text=f"Courbe de flambage (E = {num(float(curve['E']) / 1e9)} GPa, R<sub>e</sub> = {num(Re)} MPa)",
        height=520,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
    )
    return fig


def mohr2D(r2D: dict, theta: float | None = None) -> go.Figure:
    """Cercle de Mohr plan : centre δ, rayon ρ, points A et B, σ1 et σ2, facette θ (point obtenu par rotation de 2θ).

    Entrées : `r2D` (tensors.plane2D en Pa, ou tensors.plane2DStrain) ; `theta` (rad, optionnel : par défaut
    r2D["theta"] s'il est non nul). Affichage en MPa (µdéf pour les déformations).
    Sortie : figure Plotly à axes égaux ; la trace « Cercle de Mohr » a pour rayon r2D["rho"] dans l'unité affichée.
    """
    if theta is None:
        th = np.asarray(r2D.get("theta", 0.0), dtype=float).ravel()
        if th.size == 1 and th[0] != 0:
            theta = float(th[0])
    deformation = str(r2D.get("kind", "")).lower() == "strain"
    if deformation:
        k, un, s, t = 1e6, "µdéf", "ε", "γ/2"
    else:
        k, un, s, t = 1e-6, "MPa", "σ", "τ"
    n1, n2 = f"{s}<sub>1</sub>", f"{s}<sub>2</sub>"
    c = float(r2D["delta"]) * k
    R = float(r2D["rho"]) * k
    A = np.asarray(r2D["pointA"], dtype=float).ravel() * k
    B = np.asarray(r2D["pointB"], dtype=float).ravel() * k
    ext = max(abs(c) + R, R, 1e-12)
    hmax = max(R, 0.2 * ext)
    fg = COULEUR["trait"]
    fig = go.Figure()

    arrow(fig, (min(0, c - R) - 0.15 * ext, 0), (max(0, c + R) + 0.2 * ext, 0), fg, 1)
    arrow(fig, (0, -1.25 * hmax), (0, 1.3 * hmax), fg, 1)
    fig.add_annotation(
        x=max(0, c + R) + 0.21 * ext,
        y=0,
        text=f"<i>{s}</i>",
        showarrow=False,
        font=dict(size=13),
        xanchor="left",
        yanchor="middle",
    )
    fig.add_annotation(
        x=0.02 * ext,
        y=1.3 * hmax,
        text=f"<i>{t}</i>",
        showarrow=False,
        font=dict(size=13),
        xanchor="left",
        yanchor="top",
    )

    phi = np.linspace(0, 2 * math.pi, 361)
    fig.add_trace(
        go.Scatter(
            x=c + R * np.cos(phi),
            y=R * np.sin(phi),
            mode="lines",
            line=dict(color=COULEUR["positif"], width=2),
            name=f"Cercle de Mohr ({un})",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[A[0], B[0]],
            y=[A[1], B[1]],
            mode="lines",
            line=dict(color=fg, width=1),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[A[0]],
            y=[A[1]],
            mode="markers",
            marker=dict(symbol="circle", size=8, color=rgb(_ROUGE)),
            name="A",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[B[0]],
            y=[B[1]],
            mode="markers",
            marker=dict(symbol="square", size=8, color=rgb(_VERT)),
            name="B",
        )
    )
    # étiquettes de A et B à l'extérieur du cercle, dans le sens radial
    for q, texte, couleur in (
        (A, f"A({s}<sub>xx</sub>, {s}<sub>xy</sub>)", rgb(_ROUGE)),
        (B, f"B({s}<sub>yy</sub>, −{s}<sub>xy</sub>)", rgb(_VERT)),
    ):
        u = (q - np.array([c, 0.0])) / max(R, np.finfo(float).eps)
        fig.add_annotation(
            x=q[0] + 0.05 * ext * u[0],
            y=q[1] + 0.05 * ext * u[1],
            text=texte,
            showarrow=False,
            font=dict(color=couleur, size=10),
            xanchor="right" if u[0] < 0 else "left",
            yanchor="top" if -u[1] > 0 else "bottom",
        )
    fig.add_trace(
        go.Scatter(
            x=[c],
            y=[0],
            mode="markers",
            marker=dict(symbol="cross", size=10, color=fg),
            name="δ",
        )
    )
    fig.add_annotation(
        x=c,
        y=-0.06 * ext,
        text=f"δ = {num(c)}",
        showarrow=False,
        font=dict(color=fg, size=10),
        xanchor="center",
        yanchor="top",
        bgcolor="white",
    )
    d45 = (math.cos(math.pi / 4), math.sin(math.pi / 4))
    fig.add_shape(type="line", x0=c, y0=0, x1=c + R * d45[0], y1=R * d45[1], line=dict(color=fg, width=0.8))
    fig.add_annotation(
        x=c + 0.55 * R * d45[0],
        y=0.55 * R * d45[1],
        text=f"ρ = {num(R)}",
        showarrow=False,
        font=dict(color=fg, size=10),
        xanchor="right",
        yanchor="bottom",
        bgcolor="white",
    )
    fig.add_trace(
        go.Scatter(
            x=[c + R, c - R],
            y=[0, 0],
            mode="markers",
            marker=dict(symbol="diamond", size=8, color=rgb(_JAUNE)),
            name=f"{n1}, {n2}",
        )
    )
    fig.add_annotation(
        x=c + R + 0.03 * ext,
        y=0.05 * ext,
        text=f"{n1} = {num(c + R)}",
        showarrow=False,
        font=dict(color=fg, size=10),
        xanchor="left",
        yanchor="bottom",
    )
    fig.add_annotation(
        x=c - R - 0.03 * ext,
        y=0.05 * ext,
        text=f"{n2} = {num(c - R)}",
        showarrow=False,
        font=dict(color=fg, size=10),
        xanchor="right",
        yanchor="bottom",
    )

    # facette θ : point de la facette par rotation de -2θ depuis A autour du centre
    if theta is not None and R > 0:
        violet = rgb(_VIOLET)
        d0 = A - np.array([c, 0.0])
        a0 = math.atan2(d0[1], d0[0])
        a1 = a0 - 2 * theta
        Pf = np.array([c + R * math.cos(a1), R * math.sin(a1)])
        ang = np.linspace(a0, a1, 60)
        polyShape(fig, np.column_stack([c + 0.35 * R * np.cos(ang), 0.35 * R * np.sin(ang)]), violet, 1.5)
        arrow(
            fig,
            (c + 0.35 * R * math.cos(ang[-2]), 0.35 * R * math.sin(ang[-2])),
            (c + 0.35 * R * math.cos(ang[-1]), 0.35 * R * math.sin(ang[-1])),
            violet,
            1.5,
        )
        fig.add_shape(type="line", x0=c, y0=0, x1=Pf[0], y1=Pf[1], line=dict(color=violet, width=1, dash="dash"))
        fig.add_shape(type="line", x0=c, y0=0, x1=A[0], y1=A[1], line=dict(color=rgb(_ROUGE), width=1, dash="dash"))
        am = (a0 + a1) / 2
        fig.add_annotation(
            x=c + 0.42 * R * math.cos(am),
            y=0.42 * R * math.sin(am),
            text=f"2θ = {num(2 * theta * 180 / math.pi)}°",
            showarrow=False,
            font=dict(color=violet, size=10),
            bgcolor="white",
        )
        up = 1 if Pf[1] >= 0 else -1
        fig.add_trace(
            go.Scatter(
                x=[Pf[0]],
                y=[Pf[1]],
                mode="markers",
                marker=dict(symbol="pentagon", size=13, color=violet),
                name=f"Facette θ = {num(theta * 180 / math.pi)}°",
            )
        )
        fig.add_annotation(
            x=Pf[0],
            y=Pf[1] + up * 0.09 * ext,
            text=f"{s} = {num(Pf[0])}, {t} = {num(Pf[1])}",
            showarrow=False,
            font=dict(color=violet, size=10),
            xanchor="right" if Pf[0] >= c else "left",
            yanchor="bottom" if up > 0 else "top",
            bgcolor="white",
        )

    fig.update_xaxes(range=[min(0, c - R) - 0.65 * ext, max(0, c + R) + 0.65 * ext], title_text=f"{s} ({un})")
    fig.update_yaxes(range=[-1.45 * hmax, 1.45 * hmax], title_text=f"{t} ({un})", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title_text="Cercle de Mohr",
        height=560,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
    )
    return fig


def mohr3D(m3: dict, point=None) -> go.Figure:
    """Tricercle de Mohr et zone admissible ombrée (grand cercle moins les deux petits), point de facette optionnel.

    Entrées : `m3` (tensors.mohr3D) ; `point` : [σn, τ] en Pa d'une facette (optionnel). Affichage en MPa.
    Sortie : figure Plotly à axes égaux.
    """
    k = 1e-6
    p = np.asarray(m3["pr"], dtype=float).ravel() * k
    ce = np.asarray(m3["centers"], dtype=float).ravel() * k
    ra = np.asarray(m3["radii"], dtype=float).ravel() * k
    ext = max(float(np.max(np.abs(p))), float(ra[2]), 1e-12)
    phi = np.linspace(0, 2 * math.pi, 361)
    fg = COULEUR["trait"]

    def cercle(c, r):
        return np.column_stack([c + r * np.cos(phi), r * np.sin(phi)])

    fig = go.Figure()
    # zone admissible : le grand cercle, évidé par les deux petits (remplis de blanc, fond du graphique)
    if ra[2] > 1e-12 * ext and max(ra[0], ra[1]) < (1 - 1e-9) * ra[2]:
        zone = cercle(ce[2], ra[2])
        fig.add_trace(
            go.Scatter(
                x=zone[:, 0],
                y=zone[:, 1],
                fill="toself",
                fillcolor=rgb(_BLEU_CLAIR, 0.25),
                line=dict(width=0),
                name="Zone admissible (σn, τ)",
                hoverinfo="skip",
            )
        )
        for j in range(2):
            if ra[j] > 1e-9 * ext:
                trou = cercle(ce[j], ra[j])
                fig.add_trace(
                    go.Scatter(
                        x=trou[:, 0],
                        y=trou[:, 1],
                        fill="toself",
                        fillcolor="white",
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )

    couleurs = [COULEUR["aires"], rgb(_VERT), COULEUR["positif"]]
    noms = ["(σ<sub>I</sub>, σ<sub>II</sub>)", "(σ<sub>II</sub>, σ<sub>III</sub>)", "(σ<sub>I</sub>, σ<sub>III</sub>)"]
    for j in range(3):
        pts = cercle(ce[j], ra[j])
        fig.add_trace(
            go.Scatter(
                x=pts[:, 0],
                y=pts[:, 1],
                mode="lines",
                line=dict(color=couleurs[j], width=1.8),
                name=f"Cercle {noms[j]}",
            )
        )
    fig.add_shape(
        type="line",
        x0=min(0, p[2]) - 0.15 * ext,
        x1=max(0, p[0]) + 0.15 * ext,
        y0=0,
        y1=0,
        line=dict(color=fg, width=0.8),
    )
    hAxe = 1.2 * max(ra[2], 0.2 * ext)
    fig.add_shape(type="line", x0=0, x1=0, y0=-hAxe, y1=hAxe, line=dict(color=fg, width=0.8))
    fig.add_trace(
        go.Scatter(
            x=p, y=np.zeros(3), mode="markers", marker=dict(color=fg, size=6), showlegend=False, hoverinfo="skip"
        )
    )
    tn = ["σ<sub>I</sub>", "σ<sub>II</sub>", "σ<sub>III</sub>"]
    for j in range(3):
        if j == 1:
            # contrainte médiane, au point de tangence : sur fond d'axe
            fig.add_annotation(
                x=p[j],
                y=0.06 * ext,
                text=f"{tn[j]} = {num(p[j])}",
                showarrow=False,
                font=dict(color=fg, size=10),
                xanchor="center",
                yanchor="bottom",
                bgcolor="white",
            )
        else:
            fig.add_annotation(
                x=p[j] + (2 - j) * 0.03 * ext,
                y=0.05 * ext,
                text=f"{tn[j]} = {num(p[j])}",
                showarrow=False,
                font=dict(color=fg, size=10),
                xanchor="left",
                yanchor="bottom",
            )
    if ra[2] > 0:
        fig.add_shape(type="line", x0=ce[2], x1=ce[2], y0=0, y1=ra[2], line=dict(color=fg, width=1, dash="dot"))
        fig.add_annotation(
            x=ce[2],
            y=ra[2],
            text=f"τ<sub>max</sub> = {num(ra[2])} MPa",
            showarrow=False,
            font=dict(color=fg, size=10),
            xanchor="center",
            yanchor="bottom",
            bgcolor="white",
        )
    if point is not None:
        q = np.asarray(point, dtype=float).ravel() * k
        fig.add_trace(
            go.Scatter(
                x=[q[0]],
                y=[q[1]],
                mode="markers",
                marker=dict(symbol="pentagon", size=13, color=rgb(_ROUGE)),
                name="Facette",
            )
        )
        fig.add_annotation(
            x=q[0],
            y=q[1] + 0.06 * ext,
            text=f"({num(q[0])}, {num(q[1])})",
            showarrow=False,
            font=dict(color=rgb(_ROUGE), size=10),
            xanchor="center",
            yanchor="bottom",
            bgcolor="white",
        )
    fig.update_xaxes(range=[min(0, p[2]) - 0.6 * ext, max(0, p[0]) + 0.6 * ext], title_text="σ<sub>n</sub> (MPa)")
    fig.update_yaxes(range=[-1.3 * hAxe, 1.3 * hAxe], title_text="τ (MPa)", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title_text="Tricercle de Mohr",
        height=560,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
    )
    return fig


def yieldLocus(loci: dict, point=None) -> go.Figure:
    """Lieux de plasticité en contraintes planes : hexagone de Tresca, ellipse de Von Mises, carré de Rankine.

    Entrées : `loci` (tensors.yieldLoci, en Pa) ; `point` : [σ1, σ2] en Pa de l'état de contrainte (optionnel).
    Sortie : figure Plotly à axes égaux, affichage en MPa.
    """
    k = 1e-6
    T = np.asarray(loci["tresca"], dtype=float) * k
    V = np.asarray(loci["vonMises"], dtype=float) * k
    Rk = np.asarray(loci["rankine"], dtype=float) * k
    a = float(loci["sigmaAdm"]) * k
    ext = max(float(np.max(np.abs(Rk))), float(np.max(np.abs(V))), float(np.max(np.abs(T))))
    q = None
    if point is not None:
        q = np.asarray(point, dtype=float).ravel() * k
        ext = max(ext, float(np.max(np.abs(q))))
    e = 1.2 * ext
    fg = COULEUR["trait"]
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=T[:, 0],
            y=T[:, 1],
            fill="toself",
            fillcolor=teinte("aires", 0.10),
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_shape(type="line", x0=-e, x1=e, y0=0, y1=0, line=dict(color=fg, width=0.8))
    fig.add_shape(type="line", x0=0, x1=0, y0=-e, y1=e, line=dict(color=fg, width=0.8))
    fig.add_shape(type="line", x0=-e, x1=e, y0=-e, y1=e, line=dict(color=rgb(_GRIS_NUL), width=1, dash="dot"))
    fig.add_shape(type="line", x0=-e, x1=e, y0=e, y1=-e, line=dict(color=rgb(_GRIS_NUL), width=1, dash="dot"))
    fig.add_trace(
        go.Scatter(
            x=Rk[:, 0],
            y=Rk[:, 1],
            mode="lines",
            line=dict(color=rgb(_VERT), width=1.5, dash="dashdot"),
            name="Contrainte normale max (carré)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=V[:, 0],
            y=V[:, 1],
            mode="lines",
            line=dict(color=COULEUR["positif"], width=2),
            name="Von Mises (ellipse)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=T[:, 0],
            y=T[:, 1],
            mode="lines",
            line=dict(color=COULEUR["aires"], width=2),
            name="Tresca (hexagone)",
        )
    )
    fig.add_annotation(
        x=a, y=0, text=num(a), showarrow=False, font=dict(color=fg, size=10), xanchor="left", yanchor="top"
    )
    fig.add_annotation(
        x=0, y=a, text=num(a), showarrow=False, font=dict(color=fg, size=10), xanchor="left", yanchor="bottom"
    )
    if q is not None:
        violet = rgb(_VIOLET)
        fig.add_shape(type="line", x0=0, x1=q[0], y0=0, y1=q[1], line=dict(color=violet, width=1, dash="dash"))
        fig.add_trace(
            go.Scatter(
                x=[q[0]],
                y=[q[1]],
                mode="markers",
                marker=dict(symbol="pentagon", size=14, color=violet),
                name="État de contrainte (σ<sub>1</sub>, σ<sub>2</sub>)",
            )
        )
        fig.add_annotation(
            x=q[0],
            y=q[1] - 0.07 * ext,
            text=f"({num(q[0])}, {num(q[1])})",
            showarrow=False,
            font=dict(color=violet, size=10),
            xanchor="center",
            yanchor="top",
            bgcolor="white",
        )
    fig.update_xaxes(range=[-1.25 * ext, 1.25 * ext], title_text="σ<sub>1</sub> (MPa)")
    fig.update_yaxes(range=[-1.25 * ext, 1.25 * ext], title_text="σ<sub>2</sub> (MPa)", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title_text=f"Lieux de plasticité (σ<sub>adm</sub> = {num(a)} MPa)",
        height=560,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
    )
    return fig


def truss(truss: dict, tsol: dict | None = None, scale: float | None = None) -> go.Figure:
    """Treillis : barres colorées (traction rouge, compression bleue, nulle grise), N, appuis, charges, réactions et
    déformée amplifiée en pointillé ; en 2D (go.Figure) ou en 3D (go.Scatter3d).

    Entrées : `truss` (modèle §3 : nodes en m, bars numérotées à partir de 1, supports booléens, loads en N, names
    optionnel) ; `tsol` (truss_solver.solveTruss, optionnel) ; `scale` (facteur de la déformée ; défaut : 10 % de
    l'encombrement pour le plus grand déplacement ; 0 : pas de déformée).
    Sortie : figure Plotly, efforts en kN. En 3D, les vecteurs sont tracés sans pointe de flèche.
    """
    X = np.asarray(truss["nodes"], dtype=float)
    n, dim = X.shape
    dim3 = dim == 3
    X3 = X if dim3 else np.column_stack([X, np.zeros(n)])
    bars = np.asarray(truss["bars"]).astype(int) - 1
    span = float(np.max(X3.max(axis=0) - X3.min(axis=0))) or 1.0
    nomsModele = truss.get("names")
    noms = (
        [str(x) for x in nomsModele]
        if nomsModele is not None and len(nomsModele) == n
        else [str(i + 1) for i in range(n)]
    )
    fg = COULEUR["trait"]
    hasN = tsol is not None and "N" in tsol
    fig = go.Figure()

    # déformée amplifiée
    if tsol is not None and "displacements" in tsol and scale != 0:
        U = np.asarray(tsol["displacements"], dtype=float)
        if not dim3:
            U = np.column_stack([U, np.zeros(n)])
        umax = float(np.max(np.linalg.norm(U, axis=1)))
        if umax > 0:
            if scale is None:
                scale = 0.1 * span / umax
            Xd = X3 + scale * U
            for b in range(len(bars)):
                fig.add_trace(
                    _trace(
                        Xd[bars[b]],
                        dim3,
                        mode="lines",
                        line=dict(color=rgb(_VIOLET), width=1.5, dash="dot"),
                        name=f"Déformée (×{num(scale)})",
                        showlegend=b == 0,
                        hoverinfo="skip",
                    )
                )

    # barres : couleur selon la nature de l'effort
    couleurs = {"Traction": rgb(_ROUGE), "Compression": COULEUR["positif"], "Nul": rgb(_GRIS_NUL)}
    vus = set()
    for b in range(len(bars)):
        if hasN:
            nature = str(tsol["nature"][b])
            col = couleurs.get(nature, couleurs["Nul"])
            nomBarre = nature if nature in couleurs and nature != "Nul" else "Barre nulle"
        else:
            col, nomBarre = fg, "Barre"
        fig.add_trace(
            _trace(
                X3[bars[b]],
                dim3,
                mode="lines",
                line=dict(color=col, width=3),
                name=nomBarre,
                showlegend=nomBarre not in vus,
                hoverinfo="skip",
            )
        )
        vus.add(nomBarre)
        if hasN:
            milieu = X3[bars[b]].mean(axis=0)
            fig.add_trace(
                _trace(
                    milieu[None, :],
                    dim3,
                    mode="text",
                    text=[f"N<sub>{b + 1}</sub> = {num(float(tsol['N'][b]) / 1e3)}"],
                    textfont=dict(color=col, size=9),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    # nœuds et noms
    fig.add_trace(
        _trace(
            X3,
            dim3,
            mode="markers",
            marker=dict(color="white", size=6, line=dict(color=fg, width=1)),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        _trace(
            X3,
            dim3,
            mode="text",
            text=[f"  {nm}" for nm in noms],
            textposition="top right",
            textfont=dict(color=fg, size=11),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # appuis
    if truss.get("supports") is not None:
        S = np.asarray(truss["supports"], dtype=bool)
        for i in range(n):
            if not S[i].any():
                continue
            if dim3:
                fig.add_trace(
                    _trace(
                        X3[i : i + 1],
                        True,
                        mode="markers",
                        marker=dict(symbol="square", size=10, color=COULEUR["appui"], line=dict(color=fg, width=1)),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
            elif S[i, :2].all():
                support(fig, X[i], "pivot", 0.05 * span, 0.0, fg)
            elif S[i, 1]:
                support(fig, X[i], "pivot_glissant", 0.05 * span, 0.0, fg)
            else:
                support(fig, X[i], "pivot_glissant", 0.05 * span, -math.pi / 2, fg)

    # charges (pointe sur le nœud) et réactions (décalées sous l'appui)
    La = 0.15 * span
    vecteurs = []
    if truss.get("loads") is not None and np.any(np.asarray(truss["loads"]) != 0):
        vecteurs.append((np.asarray(truss["loads"], dtype=float), COULEUR["charge"], "Charges", 1))
    if tsol is not None and "reactions" in tsol:
        vecteurs.append((np.asarray(tsol["reactions"], dtype=float), COULEUR["reaction"], "Réactions", -1))
    for F, col, nom, sens in vecteurs:
        F3 = F if dim3 else np.column_stack([F, np.zeros(n)])
        Fmax = float(np.max(np.linalg.norm(F3, axis=1)))
        dessine = False
        for i in range(n):
            f = F3[i]
            nf = float(np.linalg.norm(f))
            if nf <= 1e-12 * max(Fmax, np.finfo(float).tiny):
                continue
            u = f / nf
            if sens > 0:
                p1, p2 = X3[i] - La * u, X3[i]
            else:
                p1, p2 = X3[i] - 1.6 * La * u, X3[i] - 0.6 * La * u
            dessine = True
            txt = f"({', '.join(num(v / 1e3) for v in f[:dim])}) kN"
            if dim3:
                fig.add_trace(
                    _trace(
                        np.array([p1, p2]),
                        True,
                        mode="lines",
                        line=dict(color=col, width=6),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
                fig.add_trace(
                    _trace(
                        p1[None, :],
                        True,
                        mode="text",
                        text=[txt],
                        textfont=dict(color=col, size=9),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
            else:
                arrow(fig, p1[:2], p2[:2], col, 2)
                fig.add_annotation(
                    x=p1[0],
                    y=p1[1],
                    text=txt,
                    showarrow=False,
                    font=dict(color=col, size=9),
                    xanchor="center",
                    yanchor="top" if u[1] > 0 else "bottom",
                )
        if dessine:
            legende(fig, nom, col)

    mn = X3.min(axis=0) - np.array([0.12, 0.3, 0.3]) * span
    mx = X3.max(axis=0) + np.array([0.12, 0.3, 0.3]) * span
    titre = "Treillis : efforts normaux N (kN)" if hasN else "Treillis"
    if dim3:
        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[mn[0], mx[0]], title="x (m)"),
                yaxis=dict(range=[mn[1], mx[1]], title="y (m)"),
                zaxis=dict(range=[mn[2], mx[2]], title="z (m)"),
                aspectmode="data",
            )
        )
    else:
        fig.update_xaxes(range=[mn[0], mx[0]], title_text="x (m)")
        fig.update_yaxes(range=[mn[1], mx[1]], title_text="y (m)", scaleanchor="x", scaleratio=1)
    fig.update_layout(
        title_text=titre,
        height=600 if dim3 else 480,
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
    )
    return fig


def ktChart(id: str) -> go.Figure:
    """Abaque de concentration de contrainte Kt : Kt(d/W) pour la plaque, une courbe Kt(r/d) par D/d pour un arbre.

    Entrée : `id` (identifiant de kt_mohr.ktCharts : plaque_trou_traction, arbre_epaulement_flexion, …).
    Sortie : figure Plotly. Erreur : MecaStruct:PlotEngine:unknownKt si l'identifiant est inconnu.
    """
    idc = str(id).strip().lower()
    ch = next((c for c in kt_mohr.ktCharts() if c["id"] == idc), None)
    if ch is None:
        raise MecaStructError(_ID_KT, f"Abaque Kt inconnu : « {idc} ».")
    r = np.asarray(ch["ranges"], dtype=float)
    fig = go.Figure()
    if not ch["curves"]:
        x = np.linspace(r[0], min(r[1], 0.95), 200)
        fig.add_trace(
            go.Scatter(
                x=x,
                y=kt_mohr.evalKt(idc, x),
                mode="lines",
                line=dict(color=COULEUR["positif"], width=2),
                name="K<sub>t</sub>(d/W)",
            )
        )
        xTitre = "d/W"
    else:
        x = np.linspace(r[0][0], r[0][1], 200)
        for Dd in ch["curves"]:
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=kt_mohr.evalKt(idc, np.column_stack([x, np.full_like(x, float(Dd))])),
                    mode="lines",
                    line=dict(width=1.8),
                    name=f"D/d = {num(float(Dd))}",
                )
            )
        xTitre = "r/d"
    ymax = max(float(np.max(t.y)) for t in fig.data)
    fig.update_xaxes(title_text=xTitre)
    fig.update_yaxes(range=[1, max(ymax, 1.5)], title_text="K<sub>t</sub>")
    fig.update_layout(
        title_text=ch["title"],
        height=480,
        plot_bgcolor="white",
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
    )
    return fig


def bucklingMode(b: dict) -> go.Figure:
    """Mode propre de flambement v(s)/v_max sur [0, L].

    Entrée : `b` (buckling.analyze : modeShape, conditionText, Lp en m, L en m). Sortie : figure Plotly.
    """
    s = np.linspace(0.0, float(b["L"]), 201)
    fig = go.Figure(go.Scatter(x=s, y=np.asarray(b["modeShape"](s), dtype=float), mode="lines", line={"width": 3}))
    fig.update_layout(
        title=f"Mode propre ({b['conditionText']}, L' = {float(b['Lp']):.4g} m)",
        xaxis_title="s (m)",
        yaxis_title="v(s)/v<sub>max</sub>",
    )
    return fig
