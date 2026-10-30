"""Outils communs aux graphiques Plotly : libellés HTML, nombres, couleurs, flèches, tracés en coordonnées."""

import math
import re

import numpy as np
import plotly.graph_objects as go

# Couleurs MATLAB de PlotEngine.m (triplets RVB entre 0 et 1)
_TRIPLETS = {
    "trait": (0.00, 0.00, 0.00),
    "charge": (0.80, 0.10, 0.10),
    "charge_repartie": (0.90, 0.45, 0.00),
    "reaction": (0.10, 0.60, 0.20),
    "positif": (0.00, 0.45, 0.74),
    "negatif": (0.85, 0.15, 0.15),
    "aires": (0.85, 0.33, 0.10),
    "castigliano": (0.47, 0.67, 0.19),
    "castigliano_tranchant": (0.49, 0.18, 0.56),
    "mohr": (0.93, 0.69, 0.13),
    "non_deforme": (0.60, 0.60, 0.60),
    "appui": (0.82, 0.82, 0.82),
}


def rgb(c: tuple[float, float, float], alpha: float = 1.0) -> str:
    """Couleur CSS rgba() d'un triplet MATLAB (composantes entre 0 et 1) ; alpha entre 0 et 1."""
    r, g, b = (round(255 * x) for x in c)
    return f"rgba({r},{g},{b},{alpha:g})"


COULEUR = {nom: rgb(c) for nom, c in _TRIPLETS.items()}


def teinte(nom: str, alpha: float) -> str:
    """Couleur CSS de la teinte nommée (clé de COULEUR) avec une transparence alpha entre 0 et 1."""
    return rgb(_TRIPLETS[nom], alpha)


def label(name: str) -> str:
    """Libellé HTML d'une grandeur : « Mfz » → « M<sub>fz</sub> », « F1 » → « F<sub>1</sub> » ; autre nom inchangé."""
    m = re.fullmatch(r"([A-Za-z])([a-z]{1,2}|\d+)", name)
    return name if m is None else f"{m.group(1)}<sub>{m.group(2)}</sub>"


def comp(name: str, c: str) -> str:
    """Libellé HTML d'une composante : « Mfz » + « y » → « M<sub>fz,y</sub> » ; « F1 » + « x » → « F<sub>1,x</sub> »."""
    base = label(name)
    if base.endswith("</sub>"):
        return f"{base[:-6]},{c}</sub>"
    return f"{base}<sub>{c}</sub>"


def num(v: float) -> str:
    """Nombre à 4 chiffres significatifs, sans -0 ni exposant « e+0 » (comme peNum de PlotEngine.m)."""
    if abs(v) < 1e-12:
        v = 0.0
    s = f"{v:.4g}"
    return s.replace("e+0", "e").replace("e-0", "e-").replace("e+", "e")


def arrow(fig: go.Figure, p1, p2, couleur: str, largeur: float = 2.0) -> None:
    """Flèche de p1 vers p2 (coordonnées de données, p1 ≠ p2) : trait et pointe triangulaire pleine."""
    fig.add_annotation(
        x=p2[0],
        y=p2[1],
        ax=p1[0],
        ay=p1[1],
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.2,
        arrowwidth=largeur,
        arrowcolor=couleur,
    )


def polyShape(
    fig: go.Figure, pts, couleur: str, largeur: float = 1.5, remplissage: str | None = None, ferme=False
) -> None:
    """Trait brisé ou polygone en coordonnées de données ; pts : suite de couples (x, y) ; remplissage : couleur CSS."""
    chemin = "M " + " L ".join(f"{x:.9g},{y:.9g}" for x, y in pts)
    if ferme:
        chemin += " Z"
    fig.add_shape(
        type="path",
        path=chemin,
        line=dict(color=couleur, width=largeur),
        fillcolor=remplissage or "rgba(0,0,0,0)",
    )


def arcArrow(fig: go.Figure, centre, r: float, M: float, couleur: str, largeur: float = 1.8) -> None:
    """Couple : arc fléché de rayon r autour de centre (x, y), sens trigonométrique si M > 0 (unités de données)."""
    th = np.linspace(-math.pi / 3, 4 * math.pi / 3, 60)
    if M <= 0:
        th = th[::-1]
    pts = np.column_stack([centre[0] + r * np.cos(th), centre[1] + r * np.sin(th)])
    polyShape(fig, pts[:-2], couleur, largeur)
    arrow(fig, pts[-4], pts[-1], couleur, largeur)
