"""Polynômes par morceaux (structure `pp`), port des utilitaires pp de BeamAndTrussSolver.m (ARCHITECTURE §0.5).

`breaks` : n+1 abscisses croissantes (m) ; `coefs` : n tableaux de coefficients (ordre polyval) en variable
globale s, valables sur [breaks[k], breaks[k+1]].
"""

import math
from dataclasses import dataclass

import numpy as np

from mecastruct.core.data_manager import hasSymbolic  # noqa: F401 (API de pp, comme BeamAndTrussSolver.hasSymbolic)
from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import is_num

_ID_ARG = "MecaStruct:BeamAndTrussSolver:invalidArgument"
_ID_PP = "MecaStruct:BeamAndTrussSolver:invalidPP"


@dataclass
class PP:
    """Polynôme par morceaux : breaks (n+1,), coefs = liste de n tableaux 1-D (ordre polyval, variable globale s)."""

    breaks: np.ndarray
    coefs: list[np.ndarray]


def asPP(x) -> PP:
    """Structure pp valide depuis un PP ou un dict {"breaks", "coefs"} (JSON MATLAB).

    Entrée : `x` (PP ou dict). Sortie : PP en tableaux float ; un coefficient vide devient [0].
    Erreur : MecaStruct:BeamAndTrussSolver:invalidPP si la structure est incohérente.
    """
    if isinstance(x, PP):
        br, c = x.breaks, x.coefs
    elif isinstance(x, dict) and "breaks" in x and "coefs" in x:
        br, c = x["breaks"], x["coefs"]
    else:
        raise MecaStructError(_ID_PP, "Structure pp invalide : champs « breaks » et « coefs » requis.")
    br = np.asarray(br, dtype=float).ravel()
    if not isinstance(c, list | tuple | np.ndarray) or br.size < 2 or len(c) != br.size - 1 or np.any(np.diff(br) <= 0):
        raise MecaStructError(
            _ID_PP, "Structure pp invalide : il faut un tronçon de moins que de points de rupture, croissants."
        )
    coefs = [np.asarray(ck, dtype=float).ravel() for ck in c]
    return PP(br, [ck if ck.size else np.zeros(1) for ck in coefs])


def ppEval(pp, s, side: str = "right") -> float | np.ndarray:
    """Évaluation d'un pp aux abscisses s (m), polynômes extrêmes prolongés hors du domaine.

    Entrées : `pp` (PP ou dict) ; `s` (nombre ou tableau) ; `side` = "right" (défaut) ou "left" : limite retenue
    aux points de rupture intérieurs (en s = L la limite à gauche, en s = 0 la limite à droite).
    Sortie : float si s est un nombre, sinon tableau de la forme de s.
    Erreurs : invalidPP (pp), invalidArgument (side).
    """
    pp = asPP(pp)
    v = _eval(pp, s, _sideIsLeft(side))
    return float(v) if v.ndim == 0 else v


def ppSample(pp, nPerSeg: int = 60) -> tuple[np.ndarray, np.ndarray]:
    """Échantillonnage d'un pp pour le tracé : nPerSeg points par tronçon, points de rupture dupliqués.

    Entrées : `pp` ; `nPerSeg` (entier ≥ 2, défaut 60).
    Sorties : `s` (m) et `v` (valeurs), tableaux 1-D de n × nPerSeg points.
    Erreur : invalidArgument si nPerSeg < 2.
    """
    if not is_num(nPerSeg) or not math.isfinite(nPerSeg) or nPerSeg < 2:
        raise MecaStructError(_ID_ARG, "nPerSeg doit être un entier supérieur ou égal à 2.")
    pp = asPP(pp)
    nP = int(nPerSeg + 0.5)  # arrondi comme round() de MATLAB (demi vers le haut)
    ts = [np.linspace(a, b, nP) for a, b in zip(pp.breaks[:-1], pp.breaks[1:], strict=True)]
    vs = [np.polyval(ck, t) for ck, t in zip(pp.coefs, ts, strict=True)]
    return np.concatenate(ts), np.concatenate(vs)


def ppIntegrate(pp, C0: float = 0.0) -> PP:
    """Primitive continue d'un pp, valant C0 en breaks[0] ; le degré de chaque tronçon augmente de 1.

    Entrées : `pp` ; `C0` (scalaire, défaut 0). Sortie : PP de mêmes points de rupture.
    Erreur : invalidArgument si C0 n'est pas un scalaire.
    """
    if not is_num(C0):
        raise MecaStructError(_ID_ARG, "C0 doit être un scalaire.")
    pp = asPP(pp)
    coefs, val = [], float(C0)
    for k, ck in enumerate(pp.coefs):
        q = np.polyint(ck)
        q[-1] += val - np.polyval(q, pp.breaks[k])
        coefs.append(q)
        val = np.polyval(q, pp.breaks[k + 1])
    return PP(pp.breaks, coefs)


def ppDerivative(pp) -> PP:
    """Dérivée d'un pp, tronçon par tronçon (les sauts aux points de rupture ne donnent pas de Dirac).

    Entrée : `pp`. Sortie : PP de mêmes points de rupture ; la dérivée d'une constante vaut 0.
    """
    pp = asPP(pp)
    coefs = [np.polyder(ck) for ck in pp.coefs]
    return PP(pp.breaks, [d if d.size else np.zeros(1) for d in coefs])


def ppAdd(ppA, ppB) -> PP:
    """Somme de deux pp, points de rupture fusionnés ; ppB peut être un scalaire (constante ajoutée).

    Entrées : `ppA`, `ppB` (pp ou nombre). Sortie : PP.
    """
    ppA = asPP(ppA)
    if is_num(ppB):
        ppB = PP(ppA.breaks[[0, -1]], [np.array([float(ppB)])])
    ppB = asPP(ppB)
    br = _mergeBreaks(np.concatenate([ppA.breaks, ppB.breaks]))
    cA = _refineCoefs(ppA, br)
    cB = _refineCoefs(ppB, br)
    return PP(br, [_polyAdd(a, b) for a, b in zip(cA, cB, strict=True)])


def ppScale(pp, k: float) -> PP:
    """Produit d'un pp par un scalaire k.

    Entrées : `pp`, `k` (scalaire). Sortie : PP. Erreur : invalidArgument si k n'est pas un scalaire.
    """
    if not is_num(k):
        raise MecaStructError(_ID_ARG, "k doit être un scalaire.")
    pp = asPP(pp)
    return PP(pp.breaks, [float(k) * ck for ck in pp.coefs])


def ppMultiply(ppA, ppB) -> PP:
    """Produit de deux pp : fusion des points de rupture, puis produit des polynômes tronçon par tronçon.

    Entrées : `ppA`, `ppB` (pp). Sortie : PP.
    """
    ppA, ppB = asPP(ppA), asPP(ppB)
    br = _mergeBreaks(np.concatenate([ppA.breaks, ppB.breaks]))
    cA = _refineCoefs(ppA, br)
    cB = _refineCoefs(ppB, br)
    return PP(br, [np.convolve(a, b) for a, b in zip(cA, cB, strict=True)])


def ppRefine(pp, newBreaks) -> PP:
    """Ajoute des points de rupture à un pp ; ceux situés hors de [breaks[0], breaks[-1]] sont ignorés.

    Entrées : `pp`, `newBreaks` (abscisses, m). Sortie : PP représentant la même fonction.
    """
    pp = asPP(pp)
    nb = np.asarray(newBreaks, dtype=float).ravel()
    tol = _tol(pp.breaks)
    nb = nb[np.isfinite(nb) & (nb >= pp.breaks[0] - tol) & (nb <= pp.breaks[-1] + tol)]
    br = _mergeBreaks(np.concatenate([pp.breaks, nb]))
    br[0], br[-1] = pp.breaks[0], pp.breaks[-1]
    return PP(br, _refineCoefs(pp, br))


def ppIntegral(pp, a=None, b=None) -> float | np.ndarray:
    """Intégrale exacte d'un pp de a à b (défauts : breaks[0] et breaks[-1]) ; négative si b < a.

    Entrées : `pp` ; `a`, `b` (nombres, ou tableaux de même taille). Sortie : float, ou tableau si a ou b en est un.
    """
    pp = asPP(pp)
    a = pp.breaks[0] if a is None else a
    b = pp.breaks[-1] if b is None else b
    P = ppIntegrate(pp, 0.0)
    return ppEval(P, b) - ppEval(P, a)


def ppZero(breaks) -> PP:
    """pp identiquement nul sur les tronçons de breaks (mêmes contraintes que ppConst).

    Entrée : `breaks` (m). Sortie : PP.
    """
    return ppConst(breaks, 0.0)


def ppConst(breaks, c: float = 0.0) -> PP:
    """pp constant égal à c sur chaque tronçon ; breaks finis et strictement croissants (au moins 2 valeurs).

    Entrées : `breaks` (m), `c` (scalaire, défaut 0). Sortie : PP.
    Erreurs : invalidPP (breaks), invalidArgument (c).
    """
    br = np.asarray(breaks, dtype=float).ravel()
    if br.size < 2 or not np.all(np.isfinite(br)) or np.any(np.diff(br) <= 0):
        raise MecaStructError(
            _ID_PP, "Les points de rupture doivent être finis, strictement croissants (au moins 2 valeurs)."
        )
    if not is_num(c):
        raise MecaStructError(_ID_ARG, "La constante doit être un scalaire.")
    return PP(br, [np.array([float(c)]) for _ in range(br.size - 1)])


def poly2latex(c, var: str = "s") -> str:
    """Écriture LaTeX, sans les $, d'un polynôme (coefficients en ordre polyval) ; signes propres.

    Entrées : `c` (coefficients), `var` (nom de la variable, défaut "s"). Format %.4g (%.8g dès deux termes).
    Sortie : texte, "0" si le polynôme est nul.
    """
    return _polyStr(c, var, tex=True)


def poly2str(c, var: str = "s") -> str:
    """Écriture texte d'un polynôme, même format que poly2latex (ex. "-1500*s^2 + 3000*s - 250").

    Entrées : `c` (coefficients), `var` (défaut "s"). Sortie : texte, "0" si le polynôme est nul.
    """
    return _polyStr(c, var, tex=False)


def _sideIsLeft(side: str) -> bool:
    """Vrai pour side = "left", faux pour "right" ; toute autre valeur lève invalidArgument."""
    if isinstance(side, str) and side.lower() in ("left", "right"):
        return side.lower() == "left"
    raise MecaStructError(_ID_ARG, "side doit valoir 'right' ou 'left'.")


def _tol(br) -> float:
    """Tolérance de reconnaissance des points de rupture : 1e-12 × max|breaks| (1e-12 si nul ou non fini)."""
    m = np.nanmax(np.abs(br), initial=0.0)
    return 1e-12 * m if np.isfinite(m) and m > 0 else 1e-12


def _segIndex(br: np.ndarray, s: np.ndarray, leftSide: bool) -> np.ndarray:
    """Indice (0 à n-1) du tronçon contenant chaque abscisse de s (tableau 1-D) ; points de rupture à _tol près."""
    n = len(br) - 1
    tol = _tol(br)
    st = br[:n]
    if leftSide:
        cnt = np.sum(st < s[:, None] - tol, axis=1)
    else:
        cnt = np.sum(st <= s[:, None] + tol, axis=1)
    return np.clip(cnt, 1, n) - 1


def _eval(pp: PP, s, leftSide: bool) -> np.ndarray:
    """Évaluation de pp aux abscisses s, de la forme de s."""
    s = np.asarray(s, dtype=float)
    flat = s.ravel()
    idx = _segIndex(pp.breaks, flat, leftSide)
    v = np.zeros(flat.shape)
    for k, ck in enumerate(pp.coefs):
        m = idx == k
        v[m] = np.polyval(ck, flat[m])
    return v.reshape(s.shape)


def _mergeBreaks(x) -> np.ndarray:
    """Points de rupture triés et fusionnés (écart ≤ _tol supprimé) ; les valeurs non finies sont retirées."""
    x = np.sort(np.asarray(x, dtype=float).ravel())
    x = x[np.isfinite(x)]
    if x.size == 0:
        return x
    return x[np.concatenate([[True], np.diff(x) > _tol(x)])]


def _refineCoefs(pp: PP, br: np.ndarray) -> list[np.ndarray]:
    """Coefficients de pp sur la subdivision br : chaque tronçon reprend le polynôme qui le couvre."""
    n = len(br) - 1
    mid = (br[:n] + br[1:]) / 2
    idx = _segIndex(pp.breaks, mid, False)
    return [pp.coefs[k] for k in idx]


def _pad(v, n: int) -> np.ndarray:
    """Coefficients v complétés à gauche par des zéros jusqu'à n (tronqués à gauche s'ils sont plus longs)."""
    v = np.asarray(v, dtype=float).ravel()
    if v.size < n:
        return np.concatenate([np.zeros(n - v.size), v])
    return v[v.size - n :]


def _polyAdd(a, b) -> np.ndarray:
    """Somme de deux polynômes (coefficients en ordre polyval) de longueurs différentes."""
    n = max(np.size(a), np.size(b))
    return _pad(a, n) + _pad(b, n)


def _shiftPoly(c, a: float) -> np.ndarray:
    """Coefficients en s de p(s) = Σ c_i (s − a)^(n−i), par le schéma de Horner."""
    c = np.asarray(c, dtype=float).ravel()
    g = c[:1]
    for ci in c[1:]:
        g = _polyAdd(np.convolve(g, [1.0, -a]), [ci])
    return g


def _g(x: float, spec: str) -> str:
    """Format C %g (spec ex. ".4g") ; NaN, Inf et -Inf écrits comme MATLAB."""
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Inf" if x > 0 else "-Inf"
    return format(x, spec)


def _num(v: float) -> str:
    """Nombre pour les textes de rapport (%.6g, -0 écrit 0)."""
    return _g(v + 0.0, ".6g")


def _texNum(v: float, spec: str = ".4g") -> str:
    """Nombre LaTeX : exposant écrit sous la forme \\cdot 10^{n}, Inf et NaN en symboles, -0 écrit 0."""
    s = _g(v + 0.0, spec)
    symboles = {"Inf": r"\infty", "-Inf": r"-\infty", "NaN": r"\mathrm{NaN}"}
    if s in symboles:
        return symboles[s]
    if "e" not in s:
        return s
    mant, ex = s.split("e")
    puissance = f"10^{{{int(ex)}}}"
    if mant in ("1", "-1"):
        return ("-" if mant == "-1" else "") + puissance
    return f"{mant} \\cdot {puissance}"


def _polyStr(c, var: str, tex: bool) -> str:
    """Écriture d'un polynôme (texte ou LaTeX), termes nuls omis."""
    c = np.asarray(c, dtype=float).ravel()
    if c.size == 0:
        return "0"
    finis = np.abs(c[np.isfinite(c)])
    mx = finis.max() if finis.size else 0.0
    # les termes se compensent loin de s = 0 : 4 chiffres ne suffisent plus dès qu'il y a plusieurs termes
    fmt = ".8g" if np.count_nonzero(c != 0) > 1 else ".4g"
    n = c.size
    texte = ""
    for i, a in enumerate(c):
        if a == 0 or (np.isfinite(a) and abs(a) <= 1e-12 * mx):
            continue
        p = n - 1 - i
        mag = _texNum(abs(a), fmt) if tex else _g(abs(a), fmt)
        if p == 0:
            terme = mag
        else:
            vp = var if p == 1 else (f"{var}^{{{p}}}" if tex else f"{var}^{p}")
            if mag == "1":
                terme = vp
            else:
                terme = f"{mag}\\,{vp}" if tex else f"{mag}*{vp}"
        if not texte:
            texte = "-" + terme if a < 0 else terme
        else:
            texte += (" - " if a < 0 else " + ") + terme
    return texte or "0"
