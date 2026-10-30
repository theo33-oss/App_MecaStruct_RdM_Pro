"""Graphiques Poutres en Plotly, port de PlotEngine.m : schéma, efforts intérieurs, déformée, enveloppe mobile.

Aucun calcul mécanique ici : on trace les sorties des moteurs (SI strict, affichage en kN, kN·m, mm, mrad).
"""

import math

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import asPP, ppEval, ppSample
from mecastruct.plots._common import COULEUR, arcArrow, arrow, comp, label, num, polyShape, support, teinte

_ID = "MecaStruct:PlotEngine:invalidInput"
_TOUTES = ("N", "Ty", "Tz", "Mt", "Mfy", "Mfz")
_INFO = {
    "N": ("Effort normal N(s)", "N (kN)"),
    "Ty": ("Effort tranchant T<sub>y</sub>(s)", "T<sub>y</sub> (kN)"),
    "Tz": ("Effort tranchant T<sub>z</sub>(s)", "T<sub>z</sub> (kN)"),
    "Mt": ("Moment de torsion M<sub>t</sub>(s)", "M<sub>t</sub> (kN·m)"),
    "Mfy": ("Moment fléchissant M<sub>fy</sub>(s)", "M<sub>fy</sub> (kN·m)"),
    "Mfz": ("Moment fléchissant M<sub>fz</sub>(s)", "M<sub>fz</sub> (kN·m)"),
}
_NOIR = "#000000"


def _arrondi(x: float) -> int:
    """Arrondi comme round() de MATLAB (demi vers le haut)."""
    return math.floor(x + 0.5)


def _txt(
    fig: go.Figure, x: float, y: float, texte: str, couleur: str, ancrage_x="center", ancrage_y="bottom", taille=10
):
    """Texte HTML ancré en coordonnées de données (ancrage_x : left/center/right ; ancrage_y : top/middle/bottom)."""
    fig.add_annotation(
        x=x,
        y=y,
        text=texte,
        showarrow=False,
        font=dict(color=couleur, size=taille),
        xanchor=ancrage_x,
        yanchor=ancrage_y,
    )


def beamSchematic(model: dict, sol: dict | None = None) -> go.Figure:
    """Schéma de la poutre : appuis, forces, couples, charges réparties et réactions (avec valeurs si sol est fourni).

    Entrées : `model` (modèle de poutre, SI : m, N, N·m) ; `sol` (résultat de solveBeam, optionnel).
    Sortie : figure Plotly, axes en mètres, proportions conservées.
    Erreur : MecaStruct:PlotEngine:invalidInput si model["L"] n'est pas un réel strictement positif.
    """
    L = model.get("L")
    if not isinstance(L, (int, float)) or not L > 0:
        raise MecaStructError(_ID, "model.L (longueur, m) doit être un réel strictement positif.")
    L = float(L)
    fig = go.Figure()
    fg = COULEUR["trait"]
    cLoad, cDist, cReac = COULEUR["charge"], COULEUR["charge_repartie"], COULEUR["reaction"]
    h, Ha, Hq, Hr = 0.05 * L, 0.20 * L, 0.10 * L, 0.12 * L
    yTop, yBot = 0.05 * L, -0.05 * L
    cles = [0.0, L]
    avecDist = avecForces = avecReac = False
    fig.add_shape(type="line", x0=0.0, y0=0.0, x1=L, y1=0.0, line=dict(color=fg, width=4))

    # ---- appuis
    for i, sup in enumerate(model.get("supports") or [], start=1):
        x = float(sup["pos"])
        cles.append(x)
        typ = str(sup["type"]).lower()
        nm = sup.get("name") or chr(ord("A") + i - 1)
        phi = 0.0
        if typ == "encastrement":
            phi = -math.pi / 2 if x < L / 2 else math.pi / 2
        support(fig, (x, 0.0), typ, h, phi, fg)
        if typ == "encastrement":
            _txt(fig, x + math.copysign(1.8 * h, phi), -1.6 * h, label(nm), fg, "center", "top", 11)
        else:
            _txt(fig, x - 0.9 * h, -0.5 * h, label(nm), fg, "right", "middle", 11)
        yBot = min(yBot, -1.6 * h)
        note = ""
        if (sup.get("spring") or 0) > 0:
            zy = np.linspace(-1.1 * h, -3.1 * h, 9)
            zx = x + 0.5 * h * np.array([0, 1, -1, 1, -1, 1, -1, 1, 0])
            polyShape(fig, np.column_stack([zx, zy]), fg, 1.2)
            polyShape(fig, [(x - h, zy[-1] - 0.1 * h), (x + h, zy[-1] - 0.1 * h)], fg, 2)
            note = f"k = {num(sup['spring'] / 1e3)} kN/m"
            yBot = min(yBot, -3.6 * h)
        dd = [float(sup.get(k) or 0.0) for k in ("dx", "dy", "dz")]
        if any(dd):
            note = f"{note} tassement (mm) : {' '.join(num(v * 1e3) for v in dd)}".strip()
        if note:
            _txt(fig, x, yBot - 0.4 * h, note, fg, "center", "top", 8)
            yBot -= 1.6 * h

    # ---- rotules intermédiaires
    for hg in model.get("hinges") or []:
        cles.append(float(hg["pos"]))
        fig.add_trace(
            go.Scatter(
                x=[hg["pos"]],
                y=[0.0],
                mode="markers",
                marker=dict(size=10, color="white", line=dict(color=fg, width=1.8)),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # ---- charges réparties (empilées si elles se recouvrent)
    dl = model.get("distLoads") or []
    pmaxAll = max(
        (float(np.max(np.abs(np.polyval(d["coeffs"], np.linspace(0, d["b"] - d["a"], 50))))) for d in dl), default=0.0
    )
    placed = []  # [a, b, sommet] des charges déjà tracées
    for i, d in enumerate(dl, start=1):
        a, b = float(d["a"]), float(d["b"])
        cles += [a, b]
        c = np.asarray(d["coeffs"], dtype=float).ravel()
        nm = d.get("name") or f"q{i}"
        avecDist = True
        xs = np.linspace(a, b, 120)
        ps = np.polyval(c, xs - a)
        dirc = str(d["dir"]).lower()
        if dirc == "y":
            base = 0.0
            dessus = [p[2] for p in placed if p[0] < b and p[1] > a]
            if dessus:
                base = max(dessus)
                fig.add_shape(type="line", x0=a, x1=b, y0=base, y1=base, line=dict(color=cDist, width=1, dash="dot"))
            env = base + Hq * np.abs(ps) / pmaxAll if pmaxAll > 0 else np.full(xs.shape, base)
            polyShape(fig, np.column_stack([xs, env]), cDist, 1.5)
            polyShape(fig, [(a, base), (a, env[0])], cDist, 1)
            polyShape(fig, [(b, base), (b, env[-1])], cDist, 1)
            nArr = max(5, _arrondi(14 * (b - a) / L))
            xa = np.linspace(a, b, nArr)
            for xk, pk in zip(xa, np.polyval(c, xa - a), strict=True):
                hk = Hq * abs(pk) / max(pmaxAll, np.finfo(float).tiny)
                if hk < 0.15 * Hq:
                    continue
                if pk < 0:
                    arrow(fig, (xk, base + hk), (xk, base), cDist, 1)
                else:
                    arrow(fig, (xk, base), (xk, base + hk), cDist, 1)
            if c.size == 1:
                _txt(fig, (a + b) / 2, env.max() + 0.02 * L, f"{label(nm)} = {num(c[0] / 1e3)} kN/m", cDist)
            else:
                _txt(
                    fig,
                    a,
                    env[0] + 0.02 * L,
                    f"{label(nm)}({num(a)}) = {num(ps[0] / 1e3)} kN/m",
                    cDist,
                    "left",
                    "bottom",
                    9,
                )
                _txt(
                    fig,
                    b,
                    env[-1] + 0.02 * L,
                    f"{label(nm)}({num(b)}) = {num(ps[-1] / 1e3)} kN/m",
                    cDist,
                    "right",
                    "bottom",
                    9,
                )
            yTop = max(yTop, env.max() + 0.08 * L)
            placed.append((a, b, env.max() + 0.07 * L))
        elif dirc == "x":
            fig.add_shape(
                type="line", x0=a, x1=b, y0=0.03 * L, y1=0.03 * L, line=dict(color=cDist, width=1.2, dash="dot")
            )
            nArr = max(3, _arrondi(8 * (b - a) / L))
            xa = np.linspace(a, b, nArr + 1)
            pa = np.polyval(c, (xa[:-1] + xa[1:]) / 2 - a)
            for k in range(nArr):
                p0, p1 = (xa[k], 0.03 * L), (xa[k + 1], 0.03 * L)
                if pa[k] >= 0:
                    arrow(fig, p0, p1, cDist, 1)
                else:
                    arrow(fig, p1, p0, cDist, 1)
            _txt(fig, (a + b) / 2, 0.05 * L, f"p<sub>x</sub> : {label(nm)}", cDist, taille=9)
            yTop = max(yTop, 0.1 * L)
        else:
            nArr = max(3, _arrondi(10 * (b - a) / L))
            xa = np.linspace(a, b, nArr)
            pa = np.polyval(c, xa - a)
            fig.add_shape(
                type="line", x0=a, x1=b, y0=0.03 * L, y1=0.03 * L, line=dict(color=cDist, width=1.2, dash="dot")
            )
            fig.add_trace(
                go.Scatter(
                    x=xa,
                    y=np.full(nArr, 0.03 * L),
                    mode="markers",
                    marker=dict(
                        symbol=["x" if p < 0 else "circle-open" for p in pa],
                        size=7,
                        color=cDist,
                        line=dict(color=cDist, width=1.2),
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            _txt(fig, (a + b) / 2, 0.05 * L, f"p<sub>z</sub> : {label(nm)}", cDist, taille=9)
            yTop = max(yTop, 0.1 * L)

    # ---- forces ponctuelles
    for i, p in enumerate(model.get("pointLoads") or [], start=1):
        x = float(p["pos"])
        cles.append(x)
        nm = p.get("name") or f"F{i}"
        Fx, Fy, Fz = (float(p.get(k) or 0.0) for k in ("Fx", "Fy", "Fz"))
        if Fy != 0:
            if Fy < 0:
                arrow(fig, (x, Ha), (x, 0.0), cLoad, 2)
            else:
                arrow(fig, (x, 0.0), (x, Ha), cLoad, 2)
            _txt(fig, x, Ha + 0.015 * L, f"{comp(nm, 'y')} = {num(Fy / 1e3)} kN", cLoad)
            yTop = max(yTop, Ha + 0.09 * L)
            avecForces = True
        if Fx != 0:
            yx = 0.012 * L
            if x > L / 2:
                p1, p2 = (x, yx), (x + math.copysign(0.6 * Ha, Fx), yx)
                if Fx < 0:
                    p1, p2 = (x + 0.6 * Ha, yx), (x, yx)
            else:
                p2, p1 = (x, yx), (x - math.copysign(0.6 * Ha, Fx), yx)
                if Fx < 0:
                    p1, p2 = (x, yx), (x - 0.6 * Ha, yx)
            arrow(fig, p1, p2, cLoad, 2)
            _txt(fig, (p1[0] + p2[0]) / 2, yx + 0.02 * L, f"{comp(nm, 'x')} = {num(Fx / 1e3)} kN", cLoad)
            avecForces = True
        if Fz != 0:
            fig.add_trace(
                go.Scatter(
                    x=[x],
                    y=[0.0],
                    mode="markers",
                    marker=dict(
                        symbol="circle-open" if Fz > 0 else "x", size=12, color=cLoad, line=dict(color=cLoad, width=2)
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[x], y=[0.0], mode="markers", marker=dict(size=4, color=cLoad), showlegend=False, hoverinfo="skip"
                )
            )
            _txt(fig, x, -0.03 * L, f"{comp(nm, 'z')} = {num(Fz / 1e3)} kN", cLoad, ancrage_y="top")
            avecForces = True

    # ---- couples ponctuels
    for i, m in enumerate(model.get("pointMoments") or [], start=1):
        x = float(m["pos"])
        cles.append(x)
        nm = m.get("name") or f"C{i}"
        Mx, My, Mz = (float(m.get(k) or 0.0) for k in ("Mx", "My", "Mz"))
        parts = []
        if Mz != 0:
            arcArrow(fig, (x, 0.0), 1.6 * h, Mz, cLoad)
            parts.append(f"{comp(nm, 'z')} = {num(Mz / 1e3)} kN·m")
            avecForces = True
        for axe, v in (("x", Mx), ("y", My)):
            if v != 0:
                parts.append(f"{comp(nm, axe)} = {num(v / 1e3)} kN·m")
                fig.add_trace(
                    go.Scatter(
                        x=[x],
                        y=[0.0],
                        mode="markers",
                        marker=dict(symbol="diamond", size=7, color=cLoad),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
        if parts:
            _txt(fig, x, -1.8 * h, ", ".join(parts), cLoad, ancrage_y="top")
            yBot = min(yBot, -1.8 * h - 0.07 * L)

    # ---- réactions (valeurs si sol est fourni)
    for i, R in enumerate((sol or {}).get("reactions") or [], start=1):
        x = float(R["pos"])
        nm = R.get("name") or chr(ord("A") + i - 1)
        isEnc = str(R["type"]).lower() == "encastrement"
        Rx, Ry, Rz, Mx, My, Mz = (float(R.get(k) or 0.0) for k in ("Rx", "Ry", "Rz", "Mx", "My", "Mz"))
        y0 = -1.3 * h if isEnc else -1.75 * h
        if Ry != 0:
            if Ry > 0:
                arrow(fig, (x, y0 - Hr), (x, y0), cReac, 2)
            else:
                arrow(fig, (x, y0), (x, y0 - Hr), cReac, 2)
            avecReac = True
        lignes = []
        if Rx != 0:
            yx = y0 - 0.35 * Hr
            sd = -1 if x > L / 2 else 1  # côté extérieur : gauche si x <= L/2, droite sinon
            xo = x - sd * 0.8 * Hr
            if math.copysign(1, Rx) == sd:
                arrow(fig, (xo, yx), (x, yx), cReac, 2)
            else:
                arrow(fig, (x, yx), (xo, yx), cReac, 2)
            lignes.append(f"X<sub>{nm}</sub> = {num(Rx / 1e3)} kN")
            avecReac = True
        if Ry != 0 or not isEnc:
            lignes.append(f"Y<sub>{nm}</sub> = {num(Ry / 1e3)} kN")
        if Mz != 0:
            arcArrow(fig, (x, 0.0), 1.6 * h, Mz, cReac)
            lignes.append(f"M<sub>{nm}</sub> = {num(Mz / 1e3)} kN·m")
            avecReac = True
        if Rz != 0:
            lignes.append(f"Z<sub>{nm}</sub> = {num(Rz / 1e3)} kN")
        if My != 0:
            lignes.append(f"M<sub>y{nm}</sub> = {num(My / 1e3)} kN·m")
        if Mx != 0:
            lignes.append(f"M<sub>x{nm}</sub> = {num(Mx / 1e3)} kN·m")
        if lignes:
            yl = y0 - Hr - 0.015 * L
            _txt(fig, x, yl, "<br>".join(lignes), cReac, ancrage_y="top")
            yBot = min(yBot, yl - 0.06 * L * len(lignes))

    # ---- axes : proportions conservées, pas d'axe vertical, graduations aux points clés
    kx = sorted({round(x / L, 9): x for x in cles}.values())
    fig.update_xaxes(range=[-0.15 * L, 1.15 * L], title_text="s (m)")
    if len(kx) <= 12:
        fig.update_xaxes(tickmode="array", tickvals=kx)
    fig.update_yaxes(
        range=[yBot - 0.02 * L, yTop + 0.02 * L],
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    legende = [("Poutre", fg)]
    if avecDist:
        legende.append(("Charges réparties", cDist))
    if avecForces:
        legende.append(("Forces", cLoad))
    if avecReac:
        legende.append(("Réactions", cReac))
    for nom, couleur in legende:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=nom, line=dict(color=couleur, width=3)))
    fig.update_layout(
        title_text="Schéma de la poutre",
        height=420,
        showlegend=True,
        # légende à droite de la poutre : elle ne touche pas le titre de l'axe x, sous le tracé
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
        margin=dict(r=170),
        plot_bgcolor="white",
    )
    return fig


def _extremum(fig: go.Figure, s: float, v: float, L: float, sorte: str, c: str, unite: str, k: int) -> None:
    """Marque un extremum d'un diagramme et l'annote (valeur et abscisse), hors de la courbe (comme peExtremum)."""
    couleur = COULEUR["positif"] if sorte == "max" else COULEUR["negatif"]
    fig.add_trace(
        go.Scatter(
            x=[s], y=[v], mode="markers", marker=dict(color=couleur, size=6), showlegend=False, hoverinfo="skip"
        ),
        row=k,
        col=1,
    )
    fig.add_annotation(
        x=s,
        y=v,
        row=k,
        col=1,
        text=f"{comp(c, sorte)} = {num(v)} {unite} en s = {num(s)} m",
        showarrow=False,
        font=dict(color=couleur, size=9),
        xanchor="right" if s > 0.6 * L else "left",
        yanchor="bottom" if sorte == "max" else "top",
        yshift=6 if sorte == "max" else -6,
        bgcolor="white",
    )


def internalForces(sol: dict, comps: list[str] | None = None) -> go.Figure:
    """Diagrammes des efforts intérieurs alignés sur s ∈ [0, L], un sous-graphe par composante.

    Entrées : `sol` (résultat de solveBeam) ; `comps` (sous-ensemble de N, Ty, Tz, Mt, Mfy, Mfz ; défaut : composantes
    non nulles, ou Ty et Mfz si toutes sont nulles).
    Sortie : figure Plotly, aires bleues (> 0) et rouges (< 0), extrema annotés, axes x liés (kN, kN·m).
    Erreur : MecaStruct:PlotEngine:invalidInput si sol n'est pas un résultat de solveBeam ou si comps est inconnu.
    """
    if not isinstance(sol, dict) or "Mfz" not in sol:
        raise MecaStructError(_ID, "sol doit être un résultat de solveBeam.")
    if not comps:
        comps = [c for c in _TOUTES if any(np.any(np.asarray(k) != 0) for k in asPP(sol[c]).coefs)] or ["Ty", "Mfz"]
    comps = list(comps)
    if not set(comps) <= set(_TOUTES):
        raise MecaStructError(_ID, "comps doit être inclus dans {N, Ty, Tz, Mt, Mfy, Mfz}.")
    n = len(comps)
    L = float(sol["model"]["L"])
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        subplot_titles=[_INFO[c][0] for c in comps],
        vertical_spacing=0.12 if n > 1 else 0.0,
    )
    for k, c in enumerate(comps, start=1):
        s, v = ppSample(sol[c], 200)
        v = v / 1e3
        span = max(float(v.max() - v.min()), float(np.max(np.abs(v))))
        span = span or 1.0
        e = (sol.get("extrema") or {}).get(c)
        if e:
            # les extrema exacts entrent dans le tracé : la courbe atteint la valeur annotée
            s = np.concatenate([s, [e["sMax"], e["sMin"]]])
            v = np.concatenate([v, [e["max"] / 1e3, e["min"] / 1e3]])
            ordre = np.argsort(s, kind="stable")
            s, v = s[ordre], v[ordre]
            vMax, sMax, vMin, sMin = e["max"] / 1e3, e["sMax"], e["min"] / 1e3, e["sMin"]
        else:
            iM, im = int(np.argmax(v)), int(np.argmin(v))
            vMax, sMax, vMin, sMin = v[iM], s[iM], v[im], s[im]
        lo, hi = min(float(v.min()), 0.0), max(float(v.max()), 0.0)
        if hi - lo == 0:
            hi, lo = 1.0, -1.0
        fig.add_trace(
            go.Scatter(
                x=s,
                y=np.maximum(v, 0.0),
                fill="tozeroy",
                mode="lines",
                line=dict(width=0),
                fillcolor=teinte("positif", 0.3),
                name="> 0",
                showlegend=k == 1,
                hoverinfo="skip",
            ),
            row=k,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=s,
                y=np.minimum(v, 0.0),
                fill="tozeroy",
                mode="lines",
                line=dict(width=0),
                fillcolor=teinte("negatif", 0.3),
                name="< 0",
                showlegend=k == 1,
                hoverinfo="skip",
            ),
            row=k,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=s, y=v, mode="lines", line=dict(color=_NOIR, width=1.8), name="Diagramme", showlegend=k == 1),
            row=k,
            col=1,
        )
        fig.add_hline(y=0.0, line=dict(color=_NOIR, width=0.8), row=k, col=1)
        fig.update_yaxes(range=[lo - 0.3 * (hi - lo), hi + 0.3 * (hi - lo)], title_text=_INFO[c][1], row=k, col=1)
        unite = "kN" if c in ("N", "Ty", "Tz") else "kN·m"
        tol = 1e-9 * span
        if abs(vMax) > tol:
            _extremum(fig, sMax, vMax, L, "max", c, unite, k)
        if abs(vMin) > tol and abs(vMin - vMax) > tol:
            _extremum(fig, sMin, vMin, L, "min", c, unite, k)
    fig.update_xaxes(range=[0.0, L], title_text="s (m)", row=n, col=1)
    fig.update_layout(title_text="Efforts intérieurs", height=max(300, 230 * n), showlegend=True)
    return fig


def _has(d: dict, f: str, g: str) -> bool:
    """Vrai si d[f][g] existe et contient au moins une valeur finie (comme peHas de PlotEngine.m)."""
    bloc = d.get(f)
    if not isinstance(bloc, dict) or bloc.get(g) is None:
        return False
    return bool(np.any(np.isfinite(np.asarray(bloc[g], dtype=float))))


def _indicesMarqueurs(n: int) -> np.ndarray:
    """Indices (0-based) de au plus 15 marqueurs répartis, pour ne pas surcharger les courbes denses (peMk)."""
    return np.unique(np.round(np.linspace(0, n - 1, min(n, 15))).astype(int))


def deflection(model: dict, d: dict) -> go.Figure:
    """Rotation α(s) (ou β(s) dans le plan xz) et déformée v(s) (ou w(s)) par les méthodes de SolicitationsEngine.

    Entrées : `model` (modèle de poutre, SI) ; `d` (résultat de deflection, plane 'xy' ou 'xz', SI).
    Sortie : figure Plotly à 2 sous-graphes : rotation en mrad, flèche en mm, poutre non déformée et appuis tracés.
    Erreur : MecaStruct:PlotEngine:invalidInput si d n'est pas un résultat de deflection.
    """
    if not isinstance(d, dict) or "s" not in d:
        raise MecaStructError(_ID, "d doit être un résultat de deflection.")
    L = float(model["L"])
    s = np.asarray(d["s"], dtype=float).ravel()
    isXZ = str(d.get("plane", "xy")).lower() == "xz"
    aNom, vNom = ("β", "w") if isXZ else ("α", "v")
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=(f"Rotation {aNom}(s) = d{vNom}/ds", f"Déformée {vNom}(s)"),
        vertical_spacing=0.12,
    )
    cI, cA, cC = COULEUR["positif"], COULEUR["aires"], COULEUR["castigliano"]
    cS, cM = COULEUR["castigliano_tranchant"], COULEUR["mohr"]
    fig.add_hline(y=0.0, line=dict(color=_NOIR, width=0.8), row=1, col=1)

    def ajoute(row: int, x, y, nom: str, **kw) -> None:
        # la légende n'est affichée que pour la déformée (les méthodes sont les mêmes sur les deux sous-graphes)
        fig.add_trace(go.Scatter(x=x, y=y, name=nom, showlegend=row == 2, hoverinfo="skip", **kw), row=row, col=1)

    # courbes d'intégration évaluées sur une grille fine à partir de leurs polynômes par morceaux (lisses) ;
    # les autres méthodes gardent leurs points de calcul
    sFin = np.unique(np.concatenate([s, np.linspace(0.0, L, 401)]))
    if _has(d, "integration", "alpha"):
        ajoute(
            1,
            sFin,
            1e3 * ppEval(d["integration"]["alphaPP"], sFin),
            "Intégration (exacte)",
            mode="lines",
            line=dict(color=cI, width=2),
        )
    if _has(d, "aires", "alpha"):
        ajoute(
            1,
            s,
            1e3 * np.asarray(d["aires"]["alpha"]).ravel(),
            "Aires",
            mode="lines",
            line=dict(color=cA, width=1.5, dash="dash"),
        )
    if _has(d, "castigliano", "alpha") and _has(d, "castigliano", "s0"):
        idx = _indicesMarqueurs(len(d["castigliano"]["s0"]))
        s0 = np.asarray(d["castigliano"]["s0"], dtype=float)[idx]
        al = 1e3 * np.asarray(d["castigliano"]["alpha"], dtype=float)[idx]
        ajoute(1, s0, al, "Castigliano", mode="markers", marker=dict(symbol="circle", size=7, color=cC))

    # ---- déformée
    vAll = [0.0]
    ajoute(
        2, [0.0, L], [0.0, 0.0], "Poutre non déformée", mode="lines", line=dict(color=COULEUR["non_deforme"], width=4)
    )
    if model.get("supports"):
        supX = [float(q["pos"]) for q in model["supports"]]
        fig.add_trace(
            go.Scatter(
                x=supX,
                y=np.zeros(len(supX)),
                mode="markers",
                marker=dict(symbol="triangle-up", size=9, color=COULEUR["appui"], line=dict(color=_NOIR, width=1)),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=2,
            col=1,
        )
    if _has(d, "integration", "v"):
        vI = 1e3 * ppEval(d["integration"]["vPP"], sFin)
        vAll += list(vI)
        ajoute(2, sFin, vI, "Intégration (exacte)", mode="lines", line=dict(color=cI, width=2))
    if _has(d, "aires", "v"):
        ajoute(
            2,
            s,
            1e3 * np.asarray(d["aires"]["v"]).ravel(),
            "Aires",
            mode="lines",
            line=dict(color=cA, width=1.5, dash="dash"),
        )
    if _has(d, "castigliano", "s0"):
        cas = d["castigliano"]
        c0 = np.asarray(cas["s0"], dtype=float).ravel()
        idx = _indicesMarqueurs(len(c0))
        if _has(d, "castigliano", "vBending"):
            ajoute(
                2,
                c0[idx],
                1e3 * np.asarray(cas["vBending"]).ravel()[idx],
                "Castigliano (flexion)",
                mode="markers",
                marker=dict(symbol="circle", size=7, color=cC),
            )
        if _has(d, "castigliano", "vTotal") and (cas.get("vShear") is None or np.any(np.asarray(cas["vShear"]) != 0)):
            vT = 1e3 * np.asarray(cas["vTotal"]).ravel()
            vAll += list(vT)
            ajoute(
                2,
                c0[idx],
                vT[idx],
                "Castigliano (+ tranchant)",
                mode="markers",
                marker=dict(symbol="square-open", size=10, color=cS, line=dict(color=cS, width=1.5)),
            )
    if _has(d, "mohr", "s0") and _has(d, "mohr", "v"):
        ajoute(
            2,
            np.asarray(d["mohr"]["s0"], dtype=float).ravel(),
            1e3 * np.asarray(d["mohr"]["v"]).ravel(),
            "Intégrales de Mohr",
            mode="markers",
            marker=dict(symbol="x", size=11, color=cM, line=dict(width=2)),
        )
    if _has(d, "integration", "sAtFmax") and _has(d, "integration", "v"):
        sf = float(d["integration"]["sAtFmax"])
        vf = float(1e3 * ppEval(d["integration"]["vPP"], sf))
        fig.add_trace(
            go.Scatter(
                x=[sf],
                y=[vf],
                mode="markers",
                marker=dict(symbol="pentagon", size=12, color=cS),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=2,
            col=1,
        )
        fig.add_shape(
            type="line", x0=sf, x1=sf, y0=0.0, y1=vf, line=dict(color=cS, width=1.2, dash="dot"), row=2, col=1
        )
        fig.add_annotation(
            x=sf,
            y=vf,
            row=2,
            col=1,
            text=f"f<sub>max</sub> = {num(abs(vf))} mm en s = {num(sf)} m",
            showarrow=False,
            font=dict(color=cS, size=11),
            xanchor="center",
            yanchor="top",
            yshift=-8,
            bgcolor="white",
        )
    lo, hi = min(vAll), max(vAll)
    if hi - lo == 0:
        hi, lo = 1.0, -1.0
    fig.update_yaxes(range=[lo - 0.3 * (hi - lo), hi + 0.3 * (hi - lo)], title_text=f"{vNom} (mm)", row=2, col=1)
    fig.update_yaxes(title_text=f"{aNom} (mrad)", row=1, col=1)
    fig.update_xaxes(range=[0.0, L], title_text="s (m)", row=2, col=1)
    fig.update_layout(
        title_text="Rotation et déformée",
        height=640,
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5),
    )
    return fig


def movingEnvelope(env: dict) -> go.Figure:
    """Enveloppe d'une charge mobile : moment Mfz (haut) et tranchant Ty (bas), maximum et minimum.

    Entrées : `env` (sortie de computeMovingLoad : s en m ; Mmax, Mmin en N·m ; Tmax, Tmin en N, mêmes longueurs).
    Sortie : figure Plotly, efforts en kN et kN·m.
    """
    s = np.asarray(env["s"], dtype=float).ravel()
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Enveloppe du moment M<sub>fz</sub>(s)", "Enveloppe du tranchant T<sub>y</sub>(s)"),
        vertical_spacing=0.12,
    )
    for k, (cHi, cLo, yl) in enumerate(
        [("Mmax", "Mmin", "M<sub>fz</sub> (kN·m)"), ("Tmax", "Tmin", "T<sub>y</sub> (kN)")], start=1
    ):
        hi = np.asarray(env[cHi], dtype=float).ravel() / 1e3
        lo = np.asarray(env[cLo], dtype=float).ravel() / 1e3
        span = max(float(hi.max() - lo.min()), float(np.finfo(float).eps))
        fig.add_trace(
            go.Scatter(
                x=np.concatenate([s, s[::-1]]),
                y=np.concatenate([hi, lo[::-1]]),
                fill="toself",
                fillcolor=teinte("positif", 0.25),
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=k,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=s,
                y=hi,
                mode="lines",
                line=dict(color=COULEUR["positif"], width=1.8),
                name="maximum",
                showlegend=k == 1,
            ),
            row=k,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=s,
                y=lo,
                mode="lines",
                line=dict(color=COULEUR["negatif"], width=1.8),
                name="minimum",
                showlegend=k == 1,
            ),
            row=k,
            col=1,
        )
        fig.add_hline(y=0.0, line=dict(color=_NOIR, width=0.8), row=k, col=1)
        fig.update_yaxes(range=[lo.min() - 0.1 * span, hi.max() + 0.1 * span], title_text=yl, row=k, col=1)
    fig.update_xaxes(range=[s[0], s[-1]], title_text="s (m)", row=2, col=1)
    fig.update_layout(title_text="Enveloppe de charge mobile", height=560, showlegend=True)
    return fig


def combinations(T) -> go.Figure:
    """Moment Mfz maximal et minimal de chaque combinaison (barres), ligne « Enveloppe » comprise.

    Entrée : `T` (DataFrame de computeCombinations : colonnes Combinaison, Mfz max (kN·m), Mfz min (kN·m)).
    Sortie : figure Plotly, en kN·m.
    """
    fig = go.Figure()
    fig.add_bar(x=T["Combinaison"], y=T["Mfz max (kN·m)"], name="Mfz max", marker_color=COULEUR["positif"])
    fig.add_bar(x=T["Combinaison"], y=T["Mfz min (kN·m)"], name="Mfz min", marker_color=COULEUR["negatif"])
    fig.update_layout(
        barmode="group", title="Moment M<sub>fz</sub> par combinaison", yaxis_title="M<sub>fz</sub> (kN·m)"
    )
    return fig
