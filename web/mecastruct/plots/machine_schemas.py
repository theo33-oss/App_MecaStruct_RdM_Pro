"""Schémas des pages de cours dessinés d'après la saisie : ils suivent chaque valeur modifiée, avant « Calculer ».

Engrenages à denture en développante de cercle, train d'engrenages (schéma cinématique), roulement chargé, durées
d'un ensemble de roulements, train épicycloïdal vu de face, disque de frein, synchronisation d'un embrayage et cycle
de couple d'un moteur. Les grandeurs mécaniques affichées viennent de mecastruct/core ; ici, seulement du dessin.
"""

import math

import numpy as np
import plotly.graph_objects as go

from mecastruct.core import bearings, brake_clutch, gears, planetary, transmission
from mecastruct.core.errors import MecaStructError
from mecastruct.plots._common import COULEUR, arrow, num, teinte
from mecastruct.plots.section_plots import _cote

_ID = "MecaStruct:Schema:invalidInput"
_ALPHA = math.radians(gears.ALPHA)
_ZMIN = 5  # en dessous, le dessin d'une denture n'a plus de sens
_ZINTERF = 17  # 2/sin²α = 17,1 : nombre de dents usuel sous lequel il y a interférence de taillage sans déport


def _inv(a: float) -> float:
    """Fonction développante inv(a) = tan(a) − a (a en rad)."""
    return math.tan(a) - a


def _profil(Z: int, m: float, saillie: float, creux: float, phase: float = 0.0, centre=(0.0, 0.0)) -> np.ndarray:
    """Contour fermé (points x, y en mm) d'une roue à denture droite en développante de cercle, α = 20°.

    Entrées : Z, m (mm), saillie et creux (mm) autour du cercle primitif (m et 1,25·m pour une roue extérieure ;
    1,25·m et m pour le creux d'une couronne intérieure), phase (rad, axe d'une dent), centre (mm).
    """
    # shortcut: pas de dégagement de pied dessiné (interférence sous 17 dents), suffisant pour un schéma
    r = m * Z / 2
    rb, ra, rf = r * math.cos(_ALPHA), r + saillie, max(r - creux, 0.05 * r)
    rho = np.linspace(max(rb, rf), ra, 8)
    # demi-épaisseur angulaire de la dent au rayon rho : π/(2Z) au primitif, développante au-delà du cercle de base
    beta = np.maximum(math.pi / (2 * Z) + _inv(_ALPHA) - np.array([_inv(math.acos(rb / x)) for x in rho]), 0.0)
    pas = 2 * math.pi / Z
    polaire: list[tuple[float, float]] = []
    for k in range(Z):
        c = phase + k * pas
        polaire += [(rf, a) for a in np.linspace(c - pas / 2, c - beta[0], 3)]
        polaire += [(x, c - b) for x, b in zip(rho, beta, strict=True)]
        polaire += [(ra, a) for a in np.linspace(c - beta[-1], c + beta[-1], 3)[1:-1]]
        polaire += [(x, c + b) for x, b in zip(rho[::-1], beta[::-1], strict=True)]
        polaire += [(rf, a) for a in np.linspace(c + beta[0], c + pas / 2, 3)]
    p = np.array(polaire)
    return np.column_stack([centre[0] + p[:, 0] * np.cos(p[:, 1]), centre[1] + p[:, 0] * np.sin(p[:, 1])])


def _cercle(r: float, centre=(0.0, 0.0), n: int = 120) -> np.ndarray:
    t = np.linspace(0, 2 * math.pi, n)
    return np.column_stack([centre[0] + r * np.cos(t), centre[1] + r * np.sin(t)])


def _surface(fig: go.Figure, pts, couleur: str, nom: str, alpha: float = 0.35, **kw) -> None:
    """Surface fermée remplie (roue, bague, disque) ; kw : options de go.Scatter (fillpattern, showlegend…)."""
    kw.setdefault("showlegend", False)
    fig.add_scatter(
        x=pts[:, 0],
        y=pts[:, 1],
        mode="lines",
        fill="toself",
        fillcolor=teinte(couleur, alpha),
        line={"color": COULEUR[couleur], "width": 1.2},
        name=nom,
        hoverinfo="name",
        **kw,
    )


def _trait(fig: go.Figure, pts, couleur: str, dash: str | None = None, largeur: float = 1.0, nom: str = "") -> None:
    fig.add_scatter(
        x=pts[:, 0],
        y=pts[:, 1],
        mode="lines",
        line={"color": couleur, "width": largeur, "dash": dash},
        name=nom,
        showlegend=bool(nom),
        hoverinfo="skip",
    )


def _texte(fig: go.Figure, x: float, y: float, texte: str, **kw) -> None:
    fig.add_annotation(x=x, y=y, text=texte, showarrow=False, font={"size": 12}, **kw)


def _vue(fig: go.Figure, titre: str, hauteur: int = 460, egal: bool = True) -> go.Figure:
    """Mise en page commune : axes masqués, repère orthonormé pour une vue de pièce, légende sous le dessin."""
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x" if egal else None, scaleratio=1)
    fig.update_layout(
        title_text=titre,
        height=hauteur,
        plot_bgcolor="white",
        margin={"l": 10, "r": 10, "t": 70},
        legend={"orientation": "h", "yanchor": "top", "y": -0.02, "xanchor": "center", "x": 0.5},
    )
    return fig


def _dents(*Z: int) -> None:
    if min(Z) < _ZMIN:
        raise MecaStructError(_ID, f"Dessin des dentures à partir de {_ZMIN} dents.")


# ------------------------------------------------------------------------------------------------- engrenages


def gearMesh(s: dict) -> go.Figure:
    """Pignon et roue en prise, vue de face : dentures, cercles primitifs, entraxe et ligne d'action (α = 20°).

    Entrée : saisie de la page Engrenages (m en mm, Z1, Z2 ; N pour le sens de rotation du pignon).
    """
    m, Z1, Z2 = float(s["m"]), int(s["Z1"]), int(s["Z2"])
    if m <= 0:
        raise MecaStructError(_ID, "Module strictement positif.")
    _dents(Z1, Z2)
    r1, r2 = m * Z1 / 2, m * Z2 / 2
    a = gears.centerDistance(m, Z1, Z2)
    fig = go.Figure()
    # une dent du pignon face à la roue (angle 0) tombe dans un creux de la roue (angle π)
    _surface(fig, _profil(Z1, m, m, 1.25 * m), "positif", f"Pignon Z1 = {Z1}")
    _surface(fig, _profil(Z2, m, m, 1.25 * m, math.pi + math.pi / Z2, (a, 0.0)), "aires", f"Roue Z2 = {Z2}")
    for r, c in ((r1, 0.0), (r2, a)):
        _trait(fig, _cercle(r, (c, 0.0)), COULEUR["trait"], "dash")
        alesage = max(min(0.3 * r, r - 2.5 * m), 0.1 * r)
        _surface(fig, _cercle(alesage, (c, 0.0), 60), "appui", "Alésage", alpha=1.0)
        _trait(fig, np.array([[c - 0.15 * r, 0], [c + 0.15 * r, 0]]), COULEUR["trait"])
        _trait(fig, np.array([[c, -0.15 * r], [c, 0.15 * r]]), COULEUR["trait"])
    # ligne d'action : tangente aux deux cercles de base, inclinée de α sur la tangente commune en I
    T1 = r1 * math.cos(_ALPHA) * np.array([math.cos(_ALPHA), -math.sin(_ALPHA)])
    T2 = np.array([a, 0.0]) + r2 * math.cos(_ALPHA) * np.array([-math.cos(_ALPHA), math.sin(_ALPHA)])
    _trait(fig, np.array([T1, T2]), COULEUR["charge"], "dot", 1.6, "Ligne d'action (α = 20°)")
    u = np.array([math.sin(_ALPHA), math.cos(_ALPHA)]) * (1 if s.get("N", 1) >= 0 else -1)
    longueur = 0.45 * min(r1, r2) + 2 * m
    arrow(fig, (r1, 0.0), (r1 + longueur * u[0], longueur * u[1]), COULEUR["charge"], 2.5)
    _texte(fig, r1 + longueur * u[0], longueur * u[1], "F<sub>n</sub> sur la roue", xanchor="left", xshift=6)
    y = -max(r1, r2) - 3 * m
    _cote(fig, (0.0, y), (a, y), f"entraxe a = {num(a)} mm", "below")
    _texte(fig, 0, r1 + 1.8 * m, f"d<sub>1</sub> = {num(m * Z1)} mm", yanchor="bottom")
    _texte(fig, a, r2 + 1.8 * m, f"d<sub>2</sub> = {num(m * Z2)} mm", yanchor="bottom")
    titre = (
        f"Pignon Z1 = {Z1} et roue Z2 = {Z2}, module {num(m)} mm<br>"
        f"<sup>rapport ω2/ω1 = {num(gears.ratio(Z1, Z2))} ; cercles primitifs en tirets ; hauteur de dent 2,25·m</sup>"
        + _interference(Z1, Z2)
    )
    return _vue(fig, titre)


def _interference(*Z: int) -> str:
    """Avertissement sous Zmin = 2/sin²α ≈ 17 dents : sans déport, la dent est dégagée au taillage (non dessiné)."""
    if min(Z) >= _ZINTERF:
        return ""
    return (
        f"<br><sup><span style='color:#b3261e'>moins de {_ZINTERF} dents : déport de denture nécessaire contre "
        "l'interférence de taillage (non dessiné)</span></sup>"
    )


def gearTrain(s: dict) -> go.Figure:
    """Schéma cinématique du train en série (vue de côté) : roues à l'échelle de leur nombre de dents, arbres.

    Entrée : saisie de la page Engrenages, onglet train (P, N, eta, Z1 à Z6 ; paires menant / mené).
    """
    paires = [(int(s[f"Z{i}"]), int(s[f"Z{i + 1}"])) for i in (1, 3, 5)]
    if min(min(p) for p in paires) < 1:
        raise MecaStructError(_ID, "Nombres de dents strictement positifs.")
    lignes = gears.gearTrain(paires, s["P"], s["N"], s["eta"])
    pas = 0.9 * max(max(p) for p in paires)  # écart horizontal entre deux engrènements
    largeur = 0.18 * pas
    fig = go.Figure()
    y = [0.0]
    for zm, zn in paires:
        y.append(y[-1] + (zm + zn) / 2)  # entraxe en « modules »
    for k, (zm, zn) in enumerate(paires):
        x = k * pas
        # libellé sous la roue menante et au-dessus de la roue menée : loin des arbres
        for Z, yc, couleur, i, sg in ((zm, y[k], "positif", 2 * k + 1, -1), (zn, y[k + 1], "aires", 2 * k + 2, 1)):
            g, d = x - largeur / 2, x + largeur / 2
            rect = np.array([[g, yc - Z / 2], [d, yc - Z / 2], [d, yc + Z / 2], [g, yc + Z / 2], [g, yc - Z / 2]])
            _surface(fig, rect, couleur, f"Z{i} = {Z}", alpha=0.45)
            _texte(fig, x, yc + sg * Z / 2, f"Z{i} = {Z}", yanchor="top" if sg < 0 else "bottom")
    for k, ligne in enumerate(lignes):
        debut = (k - 1) * pas - 0.5 * largeur if k > 0 else -0.8 * pas
        fin = k * pas + 0.5 * largeur if k < len(paires) else (k - 1) * pas + 0.8 * pas
        _trait(fig, np.array([[debut, y[k]], [fin, y[k]]]), COULEUR["trait"], largeur=3)
        nom = "Entrée" if k == 0 else ("Sortie" if k == len(paires) else ligne["arbre"])
        cote = {"xanchor": "right", "xshift": -4} if k == 0 else {"xanchor": "left", "xshift": 4}
        texte = f"{nom}<br>{num(ligne['N'])} tr/min<br>{num(ligne['C'])} N·m"
        _texte(fig, debut if k == 0 else fin, y[k], texte, yanchor="bottom", **cote)  # au-dessus : Z est dessous
    titre = (
        f"Train de {len(paires)} engrènements : rapport total {num(lignes[-1]['N'] / lignes[0]['N'])}<br>"
        "<sup>bleu : roue menante, orange : roue menée ; hauteur des roues proportionnelle à Z</sup>"
    )
    return _vue(fig, titre, egal=False)


# ------------------------------------------------------------------------------------------------- roulements


def bearingSection(s: dict) -> go.Figure:
    """Coupe d'un roulement monté sur son arbre, avec Fr et Fa à l'échelle l'une de l'autre.

    Entrée : saisie de la page Roulements (Fr, Fa en N, type « billes » ou « rouleaux », C0 en N).
    """
    Fr, Fa = float(s["Fr"]), float(s["Fa"])
    if Fr < 0 or Fa < 0:
        raise MecaStructError(_ID, "Charges Fr et Fa positives.")
    fig = go.Figure()
    arbre = np.array([[-30, -16], [30, -16], [30, 16], [-30, 16], [-30, -16]], dtype=float)
    _surface(fig, arbre, "appui", "Arbre", alpha=0.6)
    _trait(fig, np.array([[-36, 0], [36, 0]]), COULEUR["trait"], "dashdot")
    for sg in (1, -1):
        for bas, haut, nom in ((16, 25, "Bague intérieure"), (33, 42, "Bague extérieure")):
            pts = np.array([[-12, bas], [12, bas], [12, haut], [-12, haut], [-12, bas]], dtype=float) * [1, sg]
            _surface(fig, pts, "positif", nom, alpha=0.45)
        if s["type"] == "rouleaux":
            corps = np.array([[-8, 24], [8, 24], [8, 34], [-8, 34], [-8, 24]], dtype=float) * [1, sg]
        else:
            corps = _cercle(5.8, (0, 29 * sg), 60)  # dépasse dans les bagues : chemins de roulement
        _surface(fig, corps, "mohr", "Élément roulant", alpha=0.9)
    Fmax = max(Fr, Fa)
    if Fmax > 0:
        echelle = 30 / Fmax
        if Fr > 0:
            arrow(fig, (0, 43 + echelle * Fr), (0, 43), COULEUR["charge"], 3)
            _texte(fig, 0, 43 + echelle * Fr, f"F<sub>r</sub> = {Fr:.6g} N", yanchor="bottom")
        if Fa > 0:
            arrow(fig, (-31 - echelle * Fa, 0), (-31, 0), COULEUR["charge"], 3)
            _texte(fig, -31 - echelle * Fa, 0, f"F<sub>a</sub> = {Fa:.6g} N", xanchor="right", xshift=-4)
    rapport = f"F<sub>a</sub>/F<sub>r</sub> = {num(Fa / Fr)}" if Fr > 0 else "butée : F<sub>r</sub> = 0"
    if s.get("C0", 0) > 0:
        rapport += f", F<sub>a</sub>/C<sub>0</sub> = {num(Fa / s['C0'])}"
    titre = f"Roulement à {s['type']} chargé<br><sup>{rapport} ; flèches à la même échelle, dessin non coté</sup>"
    return _vue(fig, titre, 420)


def bearingLife(r: dict, s: dict) -> go.Figure:
    """Durée Lnh en fonction de la charge équivalente P, point de fonctionnement et durée visée (après Calculer).

    Entrées : r (résultat de computeBearingLife : P, a1, Lnh) ; s (saisie : C en N, N en tr/min, type, Lh en h).
    """
    n = bearings.EXPOSANT[s["type"]]
    P = np.linspace(0.3 * r["P"], 3 * r["P"], 200)
    L = r["a1"] * 1e6 * (s["C"] / P) ** n / (60 * s["N"])
    fig = go.Figure()
    fig.add_scatter(x=P, y=L, mode="lines", name="L<sub>nh</sub>(P)", line={"width": 3, "color": COULEUR["positif"]})
    fig.add_scatter(
        x=[r["P"]],
        y=[r["Lnh"]],
        mode="markers",
        name="Point de fonctionnement",
        marker={"size": 12, "color": COULEUR["charge"]},
    )
    fig.add_hline(y=s["Lh"], line_dash="dash", line_color=COULEUR["reaction"], annotation_text="durée visée")
    fig.update_layout(
        title_text=f"Durée de vie : exposant n = {num(n)}, la durée chute vite quand P augmente",
        xaxis_title="Charge équivalente P (N)",
        yaxis_title="L<sub>nh</sub> (h)",
        yaxis_type="log",
        height=420,
        plot_bgcolor="white",
    )
    return fig


def bearingSet(s: dict) -> go.Figure:
    """Durées des roulements en série et durée de l'ensemble L_E, plus courte que la plus courte d'entre elles.

    Entrée : saisie de l'onglet Ensemble (L1, L2, L3 en h, 0 = absent).
    """
    durees = [(f"Roulement {i}", s[f"L{i}"]) for i in (1, 2, 3) if s[f"L{i}"] > 0]
    LE = bearings.lifeSet([d for _, d in durees])
    fig = go.Figure()
    fig.add_bar(
        x=[n for n, _ in durees],
        y=[d for _, d in durees],
        marker_color=COULEUR["positif"],
        text=[f"{d:.0f} h" for _, d in durees],
        textposition="outside",
        name="Roulements",
    )
    fig.add_bar(
        x=["Ensemble L<sub>E</sub>"],
        y=[LE],
        marker_color=COULEUR["charge"],
        text=[f"{LE:.0f} h"],
        textposition="outside",
        name="Ensemble",
    )
    fig.update_layout(
        title_text="Ensemble en série : il s'arrête dès qu'un roulement est usé",
        showlegend=False,
        yaxis_title="Durée (h)",
        height=380,
        plot_bgcolor="white",
    )
    return fig


# ----------------------------------------------------------------------------------------- train épicycloïdal


def planetaryTrain(s: dict) -> go.Figure:
    """Train épicycloïdal vu de face : planétaire, satellites, couronne et porte-satellites, rôles et vitesses.

    Entrée : saisie de la page Trains épicycloïdaux (Z1, Z21, Z22, Z4, nSat, bloque, entree, Ne en tr/min).
    L'élément bloqué est hachuré. Si les conditions de montage ne sont pas remplies, le dessin le montre.
    """
    Z1, Z21, Z22, Z4, nSat = (int(s[k]) for k in ("Z1", "Z21", "Z22", "Z4", "nSat"))
    _dents(Z1, Z21, Z22, Z4)
    if nSat < 1:
        raise MecaStructError(_ID, "Au moins un satellite.")
    m = 1.0  # dessin en « modules »
    Rc = (Z1 + Z21) / 2  # rayon du porte-satellites
    try:
        v = planetary.speeds(planetary.basicRatio(Z1, Z21, Z22, Z4), s["bloque"], s["entree"], s["Ne"])
    except MecaStructError:
        v = {}  # bloqué = entrée : on dessine quand même les roues

    def legende(e: str, base: str) -> str:
        if e == s["bloque"]:
            return f"{base} : {'bloquée' if e == 'couronne' else 'bloqué'}"
        role = "entrée" if e == s["entree"] else "sortie"
        return f"{base} : {role}, {num(v[e])} tr/min" if e in v else base

    def motif(e: str) -> dict:
        return {"fillpattern": {"shape": "/", "fgcolor": COULEUR["trait"], "size": 6}} if e == s["bloque"] else {}

    fig = go.Figure()
    Rext = Z4 / 2 + 1.25 * m + 2.5 * m
    _surface(
        fig,
        _cercle(Rext, n=240),
        "non_deforme",
        legende("couronne", f"Couronne Z4 = {Z4}"),
        0.55,
        showlegend=True,
        **motif("couronne"),
    )
    # phase de la couronne : un creux de couronne face à une dent du satellite 0 (θ = 0)
    phi0 = math.pi + math.pi / Z21  # dent du satellite 0 face au creux du planétaire (dent de planétaire à 0)
    delta = (phi0 + math.pi / Z21) % (2 * math.pi / Z21) - math.pi / Z21
    phase_c = delta * Z21 / Z4 if Z21 == Z22 else 0.0
    trou = _profil(Z4, m, 1.25 * m, m, phase_c)
    fig.add_scatter(
        x=trou[:, 0],
        y=trou[:, 1],
        mode="lines",
        fill="toself",
        fillcolor="white",
        line={"color": COULEUR["trait"], "width": 1.2},
        showlegend=False,
        hoverinfo="skip",
    )
    _surface(
        fig,
        _profil(Z1, m, m, 1.25 * m),
        "positif",
        legende("planétaire", f"Planétaire Z1 = {Z1}"),
        showlegend=True,
        **motif("planétaire"),
    )
    centres = []
    for k in range(nSat):
        th = 2 * math.pi * k / nSat
        c = (Rc * math.cos(th), Rc * math.sin(th))
        centres.append(c)
        j = round(th * Z1 / (2 * math.pi))
        frac = (2 * math.pi * j / Z1 - th) * Z1 / (2 * math.pi)  # décalage de la dent de planétaire, en pas
        phi = th + math.pi - frac * 2 * math.pi / Z21 + math.pi / Z21
        nom = f"Satellites Z21 = {Z21}" + (f", Z22 = {Z22}" if Z22 != Z21 else "")
        _surface(fig, _profil(Z21, m, m, 1.25 * m, phi, c), "aires", nom, showlegend=k == 0, legendgroup="sat")
        if Z22 != Z21:
            _trait(fig, _cercle(Z22 / 2, c), COULEUR["aires"], "dash")
    bras = []
    for c in centres:
        bras += [(0.0, 0.0), c, (None, None)]
    bras = np.array(bras, dtype=float)
    fig.add_scatter(
        x=bras[:, 0],
        y=bras[:, 1],
        mode="lines",
        name=legende("porte-satellites", "Porte-satellites"),
        line={"color": COULEUR["reaction"], "width": 7, "dash": "dot" if s["bloque"] == "porte-satellites" else None},
        opacity=0.75,
        hoverinfo="name",
    )
    cx, cy = zip(*centres, strict=True)
    fig.add_scatter(
        x=[0, *cx],
        y=[0, *cy],
        mode="markers",
        marker={"size": 9, "color": COULEUR["reaction"]},
        showlegend=False,
        hoverinfo="skip",
    )
    defauts = [f"{n} = {num(x)}" for n, x, ok in planetary.assemblyChecks(Z1, Z21, Z22, Z4, nSat) if not ok]
    note = "Montage NON vérifié : " + " ; ".join(defauts) if defauts else "Conditions de montage vérifiées"
    couleur = "#b3261e" if defauts else "#1d7a3a"
    titre = (
        f"Train épicycloïdal, {nSat} satellite(s)<br><sup><span style='color:{couleur}'>{note}</span> ; "
        "élément bloqué hachuré ; vitesse > 0 : sens trigonométrique</sup>" + _interference(Z1, Z21, Z22)
    )
    return _vue(fig, titre, 540)


# --------------------------------------------------------------------------------------- freins et embrayages


def brakeDisc(s: dict) -> go.Figure:
    """Disque de frein vu de face : surface frottante Ri à Re, garniture, rayons équivalents des deux lois.

    Entrée : saisie de l'onglet Frein à disque (Ri, Re en mm, F en N, n). Cf = n·f·F·R_eq avec R_eq de chaque loi.
    """
    Ri, Re = float(s["Ri"]), float(s["Re"])
    if not 0 < Ri < Re:
        raise MecaStructError(_ID, "Rayons : 0 < Ri < Re.")
    fig = go.Figure()
    _surface(fig, _cercle(Re, n=200), "non_deforme", "Disque", 0.25)
    t = np.linspace(0, 2 * math.pi, 200)
    couronne = np.column_stack(
        [np.r_[Re * np.cos(t), Ri * np.cos(t[::-1])], np.r_[Re * np.sin(t), Ri * np.sin(t[::-1])]]
    )
    _surface(fig, couronne, "non_deforme", "Surface frottante", 0.6)
    _surface(fig, _cercle(0.45 * Ri, n=80), "appui", "Moyeu", alpha=1.0)
    a = np.linspace(-math.radians(28), math.radians(28), 40)
    garniture = np.column_stack(
        [np.r_[Re * np.cos(a), Ri * np.cos(a[::-1])], np.r_[Re * np.sin(a), Ri * np.sin(a[::-1])]]
    )
    _surface(fig, garniture, "aires", "Garniture (plaquette)", 0.8, showlegend=True)
    for loi, nom, couleur in (("pression", "pression constante", "positif"), ("usure", "usure constante", "charge")):
        Req = brake_clutch.brakeTorque(1.0, 1.0, 1, Re, Ri, loi) * 1000  # Cf/(n·f·F), en mm
        _trait(fig, _cercle(Req), COULEUR[couleur], "dash", 2, f"Rayon équivalent, {nom} : {num(Req)} mm")
    _cote(fig, (0.0, 0.0), (Ri * math.cos(2.4), Ri * math.sin(2.4)), f"R<sub>i</sub> = {num(Ri)}", "left")
    _cote(fig, (0.0, 0.0), (Re * math.cos(3.6), Re * math.sin(3.6)), f"R<sub>e</sub> = {num(Re)}", "left")
    titre = (
        f"Disque de frein : {int(s['n'])} surface(s) frottante(s), F = {num(s['F'])} N par surface<br>"
        "<sup>C<sub>f</sub> = n·f·F·R<sub>eq</sub> ; cotes en mm</sup>"
    )
    return _vue(fig, titre, 480)


def brakePressure(s: dict) -> go.Figure:
    """Pression de contact p(r) entre Ri et Re pour les deux lois : uniforme, ou p·r constant (usure constante).

    Entrée : saisie de l'onglet Frein à disque (F en N, Ri et Re en mm).
    """
    Ri, Re = float(s["Ri"]), float(s["Re"])
    r = np.linspace(Ri, Re, 100)
    p_unif = brake_clutch.maxPressure(s["F"], Re, Ri, "pression")
    p_usure = brake_clutch.maxPressure(s["F"], Re, Ri, "usure") * Ri / r
    fig = go.Figure()
    fig.add_scatter(
        x=r,
        y=np.full_like(r, p_unif),
        mode="lines",
        name="Pression constante",
        line={"width": 3, "color": COULEUR["positif"]},
    )
    fig.add_scatter(
        x=r, y=p_usure, mode="lines", name="Usure constante (p·r = cte)", line={"width": 3, "color": COULEUR["charge"]}
    )
    fig.update_layout(
        title_text="Pression de contact sur la garniture : maximale au rayon intérieur en usure constante",
        xaxis_title="Rayon r (mm)",
        yaxis_title="p (MPa)",
        height=400,
        plot_bgcolor="white",
    )
    return fig


def clutchSync(s: dict) -> go.Figure:
    """Vitesses du moteur (constante) et du récepteur pendant la synchronisation ; l'aire entre elles = glissement.

    Entrée : saisie de l'onglet Embrayage (NM en tr/min, ts en s, JR, CR).
    """
    NM, ts = float(s["NM"]), float(s["ts"])
    if ts <= 0:
        raise MecaStructError(_ID, "Durée de synchronisation strictement positive.")
    CT = brake_clutch.clutchTorqueFor(s["JR"], 2 * math.pi * NM / 60, s["CR"], ts)
    fig = go.Figure()
    fig.add_scatter(
        x=[0, ts, 0, 0],
        y=[0, NM, NM, 0],
        fill="toself",
        mode="none",
        fillcolor=teinte("charge", 0.2),
        name="Glissement (énergie dissipée)",
    )
    fig.add_scatter(
        x=[0, 1.4 * ts], y=[NM, NM], mode="lines", name="Moteur", line={"width": 3, "color": COULEUR["positif"]}
    )
    fig.add_scatter(
        x=[0, ts, 1.4 * ts], y=[0, NM, NM], mode="lines", name="Récepteur", line={"width": 3, "color": COULEUR["aires"]}
    )
    fig.add_vline(x=ts, line_dash="dash", line_color=COULEUR["trait"], annotation_text=f"t<sub>s</sub> = {num(ts)} s")
    fig.update_layout(
        title_text=f"Synchronisation : couple d'embrayage C<sub>T</sub> = {num(CT)} N·m pendant {num(ts)} s",
        xaxis_title="Temps (s)",
        yaxis_title="Fréquence de rotation (tr/min)",
        height=400,
        plot_bgcolor="white",
    )
    return fig


# ------------------------------------------------------------------------------------- dimensionnement moteur


def motorCycle(s: dict) -> go.Figure:
    """Cycle de couple (accélération, régime établi, freinage), couple équivalent thermique et couples du moteur.

    Entrée : saisie de la page Dimensionnement moteur (Ca, ta, Cc, tc, Cfr, tfr ; Cn, Cmax en N·m).
    """
    phases = [
        (n, s[c], s[t])
        for n, c, t in (("accélération", "Ca", "ta"), ("régime établi", "Cc", "tc"), ("freinage", "Cfr", "tfr"))
        if s[t] > 0
    ]
    if not phases:
        raise MecaStructError(_ID, "Au moins une phase de durée non nulle.")
    Cth = transmission.thermalTorque([(C, t) for _, C, t in phases])
    x, y, debut = [], [], 0.0
    fig = go.Figure()
    for nom, C, t in phases:
        x += [debut, debut + t]
        y += [C, C]
        _texte(fig, debut + t / 2, 0, nom, yanchor="bottom", yshift=4)  # en pied : loin des lignes Cth, Cn, Cmax
        debut += t
    fig.add_scatter(
        x=x,
        y=y,
        mode="lines",
        fill="tozeroy",
        fillcolor=teinte("positif", 0.2),
        name="Couple du cycle",
        line={"width": 3, "color": COULEUR["positif"]},
    )
    for val, nom, couleur, dash in (
        (Cth, "C<sub>th</sub> équivalent", "charge", None),
        (s["Cn"], "C<sub>n</sub> nominal du moteur", "reaction", "dash"),
        (s["Cmax"], "C<sub>max</sub> du moteur", "trait", "dot"),
    ):
        fig.add_scatter(
            x=[0, debut],
            y=[val, val],
            mode="lines",
            name=f"{nom} : {num(val)} N·m",
            line={"width": 2, "color": COULEUR[couleur], "dash": dash},
        )
    fig.update_layout(
        title_text="Cycle de couple : C<sub>th</sub> ≤ C<sub>n</sub> et pointe ≤ C<sub>max</sub>",
        xaxis_title="Temps (s)",
        yaxis_title="Couple (N·m)",
        height=420,
        plot_bgcolor="white",
        legend={"orientation": "h", "yanchor": "top", "y": -0.2, "xanchor": "center", "x": 0.5},
    )
    return fig
