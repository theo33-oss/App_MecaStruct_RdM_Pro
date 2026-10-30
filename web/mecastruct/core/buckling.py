"""Flambage des poutres droites comprimées : port de BucklingEngine.m (étape E14).

analyze : Euler, Rankine et compression simple selon l'arbre de décision du cours, avec mode propre et
démonstration (v'' + k² v = 0) ; stabilityCurve : courbes de stabilité σcr(λ) ; listConditions et
effectiveLengthCoefficient : conditions aux limites et coefficients L'/L ; hasSymbolic : SymPy disponible.
Le chemin symbolique de MATLAB (dsolve, vpasolve) n'est pas porté : la racine kL est toujours numérique
(methodUsed = 'numérique'). Unités SI strictes ; chaque résultat contient `report` et `latex`.
"""

import functools
import math
import re

import numpy as np
from scipy.optimize import brentq

from mecastruct.core.data_manager import hasSymbolic  # noqa: F401 (API de BucklingEngine.hasSymbolic)
from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import is_num

_ID = "MecaStruct:BucklingEngine:"
_CHAMPS = ("E", "Re", "S", "Iz", "Iy", "L", "condition")
_IDENTIFIANTS = ("encastre-libre", "articule-articule", "encastre-articule", "encastre-encastre")
_ALIAS = {
    "encastre-libre": "encastre-libre",
    "libre-encastre": "encastre-libre",
    "console": "encastre-libre",
    "articule-articule": "articule-articule",
    "rotule-rotule": "articule-articule",
    "bi-articule": "articule-articule",
    "biarticule": "articule-articule",
    "encastre-articule": "encastre-articule",
    "articule-encastre": "encastre-articule",
    "encastre-rotule": "encastre-articule",
    "rotule-encastre": "encastre-articule",
    "encastre-encastre": "encastre-encastre",
    "bi-encastre": "encastre-encastre",
    "biencastre": "encastre-encastre",
}
# identifiant : (libellé, coefficient L'/L, texte du coefficient, coefficient en LaTeX)
_COEFFICIENTS = {
    "encastre-libre": ("encastré-libre", 2.0, "2", "2"),
    "articule-articule": ("articulé-articulé", 1.0, "1", "1"),
    "encastre-articule": ("encastré-articulé", 1 / math.sqrt(2), "1/√2", r"\frac{1}{\sqrt{2}}"),
    "encastre-encastre": ("encastré-encastré", 0.5, "1/2", r"\frac{1}{2}"),
}
_KL_REF = {"encastre-libre": math.pi / 2, "articule-articule": math.pi, "encastre-encastre": 2 * math.pi}
# identifiant : (équation caractéristique en LaTeX, texte)
_EQUATION_CARACT = {
    "articule-articule": (r"$\sin(k\,L) = 0$", "sin(kL) = 0"),
    "encastre-libre": (r"$\cos(k\,L) = 0$", "cos(kL) = 0"),
    "encastre-articule": (r"$\tan(k\,L) = k\,L$", "tan(kL) = kL"),
    "encastre-encastre": (r"$2 - 2\cos(k\,L) - k\,L\,\sin(k\,L) = 0$", "2 − 2 cos(kL) − kL sin(kL) = 0"),
}
_DETERMINANT = "det[M(kL)] évalué numériquement (solution A sin ks + B cos ks + C s + D)"
_EQUATION_MODE = "v'''' + k² v'' = 0 (dérivée seconde de E·Imin·v'' + P·v = M_0 + R·(L − s))"
_SYMBOLE_REGIME = {"compression": "PC (compression simple)", "rankine": "PR (Rankine)", "euler": "PE (Euler)"}
_REF_ARTICULE = r"$\textrm{Reference (articule-articule) : } \sin(k\,L) = 0 \Rightarrow k = \frac{\pi}{L}$"


# ----------------------------------------------------------------- validation et utilitaires


def _positif(x, nom: str) -> float:
    """Scalaire réel fini strictement positif, renvoyé en float ; sinon MecaStructError.

    Entrées : `x` (valeur à tester), `nom` (nom de la grandeur, pour le message).
    Sortie : float.
    """
    if not is_num(x) or not math.isfinite(x) or x <= 0:
        raise MecaStructError(
            _ID + "invalidInput", f"La grandeur {nom} doit être un scalaire réel fini strictement positif."
        )
    return float(x)


def _positifOuNul(x, nom: str) -> float:
    """Scalaire réel fini positif ou nul, renvoyé en float ; sinon MecaStructError.

    Entrées : `x` (valeur à tester), `nom` (nom de la grandeur, pour le message).
    Sortie : float.
    """
    if not is_num(x) or not math.isfinite(x) or x < 0:
        raise MecaStructError(
            _ID + "invalidInput", f"La grandeur {nom} doit être un scalaire réel fini positif ou nul."
        )
    return float(x)


def _absent(x) -> bool:
    """Vrai pour un champ optionnel absent : None ou vide (équivalent du [] de MATLAB)."""
    return x is None or np.size(x) == 0


def _condition(c) -> str:
    """Identifiant canonique d'une condition aux limites (accents, majuscules, '_' et espaces tolérés).

    Entrée : `c` (texte). Sortie : 'encastre-libre', 'articule-articule', 'encastre-articule' ou 'encastre-encastre'.
    Erreur : MecaStruct:BucklingEngine:condition si `c` n'est pas un texte ou est inconnu.
    """
    if not isinstance(c, str) or not c:
        raise MecaStructError(
            _ID + "condition", "La condition aux limites doit être un texte (ex. 'articule-articule')."
        )
    t = c.strip().lower()
    t = re.sub(r"[éèêë]", "e", t)
    t = re.sub(r"[\s_–—/]+", "-", t)
    t = re.sub(r"-+", "-", t)
    if t not in _ALIAS:
        raise MecaStructError(
            _ID + "condition",
            f"Condition aux limites inconnue : '{c}'. Valeurs admises : 'encastre-libre', 'articule-articule', "
            "'encastre-articule', 'encastre-encastre'.",
        )
    return _ALIAS[t]


@functools.cache
def _kLClampedPinned() -> float:
    """Première racine non nulle de tan(x) = x (encastré-articulé), 4,4934…, par brentq."""
    return brentq(lambda t: math.sin(t) - t * math.cos(t), 4.0, 4.7, xtol=1e-14)


def _conditionInfo(cond: str) -> dict:
    """Libellé, coefficient L'/L (texte et LaTeX) et racine kL de référence d'une condition normalisée."""
    libelle, coef, texte, tex = _COEFFICIENTS[cond]
    kLRef = _kLClampedPinned() if cond == "encastre-articule" else _KL_REF[cond]
    return {"id": cond, "label": libelle, "coef": coef, "coefText": texte, "coefTex": tex, "kLRef": kLRef}


def _texNum(x: float) -> str:
    """Nombre au format LaTeX : 4 chiffres significatifs, puissance de 10 si besoin (texNum de MATLAB)."""
    if math.isnan(x):
        return r"\mathrm{NaN}"
    if math.isinf(x):
        return r"\infty" if x > 0 else r"-\infty"
    if x == 0:
        return "0"
    # mantisse et exposant après arrondi à 4 chiffres significatifs (évite 1e+04 pour 9999,5)
    mant, ex = f"{x:.3e}".split("e")
    e = int(ex)
    if -3 <= e <= 3:
        return f"{x:.4g}"
    if e == 4:
        return f"{x:.0f}"
    return f"{float(mant):.4g} \\times 10^{{{e}}}"


def _ltx(*morceaux) -> str:
    """Concatène des fragments LaTeX (chaînes) et des nombres, écrits par _texNum."""
    return "".join(m if isinstance(m, str) else _texNum(m) for m in morceaux)


# ----------------------------------------------------------------- modes propres


def _modeFunctions(cond: str, L: float) -> dict:
    """Mode propre normalisé (max = 1) : fonction v, dérivées analytiques d1 à d4, abscisse du maximum.

    Entrées : `cond` (condition normalisée), `L` (longueur, m).
    Sortie : dict v, d1, d2, d3, d4 (fonctions de s), k (rad/m), kL, sMax (m), text.
    """
    if cond == "articule-articule":
        k = math.pi / L
        derivees = [
            lambda s: np.sin(k * s),
            lambda s: k * np.cos(k * s),
            lambda s: -(k**2) * np.sin(k * s),
            lambda s: -(k**3) * np.cos(k * s),
            lambda s: k**4 * np.sin(k * s),
        ]
        sMax = L / 2
        texte = "v(s) = sin(π s/L) (maximum en s = L/2)"
    elif cond == "encastre-libre":
        k = math.pi / (2 * L)
        derivees = [
            lambda s: 1 - np.cos(k * s),
            lambda s: k * np.sin(k * s),
            lambda s: k**2 * np.cos(k * s),
            lambda s: -(k**3) * np.sin(k * s),
            lambda s: -(k**4) * np.cos(k * s),
        ]
        sMax = L
        texte = "v(s) = 1 − cos(π s/(2L)) (encastrement en s = 0, extrémité libre en s = L, maximum en s = L)"
    elif cond == "encastre-encastre":
        k = 2 * math.pi / L
        derivees = [
            lambda s: (1 - np.cos(k * s)) / 2,
            lambda s: k * np.sin(k * s) / 2,
            lambda s: k**2 * np.cos(k * s) / 2,
            lambda s: -(k**3) * np.sin(k * s) / 2,
            lambda s: -(k**4) * np.cos(k * s) / 2,
        ]
        sMax = L / 2
        texte = "v(s) = (1 − cos(2π s/L))/2 (maximum en s = L/2)"
    else:  # encastre-articule
        kL = _kLClampedPinned()
        k = kL / L
        # maximum : v'(s) = 0 ⇔ tan(ks/2) = kL ⇒ ks* = 2·atan(kL)
        uMax = 2 * math.atan(kL)
        fmax = math.sin(uMax) - uMax + kL * (1 - math.cos(uMax))
        derivees = [
            lambda s: (np.sin(k * s) - k * s + kL * (1 - np.cos(k * s))) / fmax,
            lambda s: (k * np.cos(k * s) - k + kL * k * np.sin(k * s)) / fmax,
            lambda s: (-(k**2) * np.sin(k * s) + kL * k**2 * np.cos(k * s)) / fmax,
            lambda s: (-(k**3) * np.cos(k * s) - kL * k**3 * np.sin(k * s)) / fmax,
            lambda s: (k**4 * np.sin(k * s) - kL * k**4 * np.cos(k * s)) / fmax,
        ]
        sMax = uMax / k
        texte = (
            f"v(s) = [sin(ks) − ks + kL(1 − cos ks)]/{fmax:.6g} avec kL = {kL:.6g} "
            f"(encastrement en s = 0, articulation en s = L, maximum en s = {uMax / kL:.4f} L)"
        )
    v, d1, d2, d3, d4 = derivees
    return {"v": v, "d1": d1, "d2": d2, "d3": d3, "d4": d4, "k": k, "kL": k * L, "sMax": sMax, "text": texte}


def _checkMode(m: dict, cond: str, L: float) -> dict:
    """Vérifie numériquement les conditions aux limites, l'équation et la normalisation du mode.

    Entrées : `m` (sortie de _modeFunctions), `cond`, `L`. Sortie : dict k, kL, equation, bcLabels, bcResiduals,
    odeResidual, fdResidual (différences finies), normResidual, tolerance, ok.
    """
    k, v, d1, d2, d3 = m["k"], m["v"], m["d1"], m["d2"], m["d3"]
    if cond == "articule-articule":
        labels = ["v(0) = 0", "v''(0) = 0 (moment nul)", "v(L) = 0", "v''(L) = 0 (moment nul)"]
        res = [v(0), d2(0) / k**2, v(L), d2(L) / k**2]
    elif cond == "encastre-libre":
        labels = [
            "v(0) = 0",
            "v'(0) = 0",
            "v''(L) = 0 (moment nul)",
            "v'''(L) + k² v'(L) = 0 (effort tranchant nul)",
        ]
        res = [v(0), d1(0) / k, d2(L) / k**2, (d3(L) + k**2 * d1(L)) / k**3]
    elif cond == "encastre-articule":
        labels = ["v(0) = 0", "v'(0) = 0", "v(L) = 0", "v''(L) = 0 (moment nul)"]
        res = [v(0), d1(0) / k, v(L), d2(L) / k**2]
    else:  # encastre-encastre
        labels = ["v(0) = 0", "v'(0) = 0", "v(L) = 0", "v'(L) = 0"]
        res = [v(0), d1(0) / k, v(L), d1(L) / k]
    sg = np.linspace(0, L, 801)
    odeRes = np.max(np.abs(m["d4"](sg) + k**2 * d2(sg))) / k**4
    # contrôle indépendant : dérivées par différences finies centrées
    h = 1e-4 * L
    si = np.linspace(0.02 * L, 0.98 * L, 97)
    fd2 = (v(si + h) - 2 * v(si) + v(si - h)) / h**2
    fdRes = np.max(np.abs(fd2 - d2(si))) / k**2
    fd1 = (v(si + h) - v(si - h)) / (2 * h)
    fd1Res = np.max(np.abs(fd1 - d1(si))) / k
    normRes = max(abs(v(m["sMax"]) - 1), max(np.max(np.abs(v(sg))) - 1, 0.0))
    tol = 1e-9
    fdResidual = max(fdRes, fd1Res)
    return {
        "k": k,
        "kL": k * L,
        "equation": _EQUATION_MODE,
        "bcLabels": labels,
        "bcResiduals": [float(x) for x in res],
        "odeResidual": float(odeRes),
        "fdResidual": float(fdResidual),
        "normResidual": float(normRes),
        "tolerance": tol,
        "ok": bool(all(abs(x) < tol for x in res) and odeRes < tol and fdResidual < 1e-5 and normRes < 1e-12),
    }


# ----------------------------------------------------------------- équation caractéristique


def _bcDeterminant(cond: str, x: float) -> float:
    """Déterminant des conditions aux limites (L = 1, k = x) ; v = A sin(ks) + B cos(ks) + C s + D."""

    def phi0(t):
        return np.array([math.sin(x * t), math.cos(x * t), t, 1.0])

    def phi1(t):
        return np.array([x * math.cos(x * t), -x * math.sin(x * t), 1.0, 0.0])

    def phi2(t):
        return np.array([-(x**2) * math.sin(x * t), -(x**2) * math.cos(x * t), 0.0, 0.0])

    def phi3(t):
        return np.array([-(x**3) * math.cos(x * t), x**3 * math.sin(x * t), 0.0, 0.0])

    if cond == "articule-articule":
        rows = [phi0(0), phi2(0), phi0(1), phi2(1)]
    elif cond == "encastre-libre":
        rows = [phi0(0), phi1(0), phi2(1), phi3(1) + x**2 * phi1(1)]
    elif cond == "encastre-articule":
        rows = [phi0(0), phi1(0), phi0(1), phi2(1)]
    else:  # encastre-encastre
        rows = [phi0(0), phi1(0), phi0(1), phi1(1)]
    return float(np.linalg.det(np.array(rows)))


def _firstRoot(f) -> float:
    """Première racine de `f` sur ]0,5 ; 20] : balayage au pas 0,01 puis brentq sur le premier changement de signe.

    Entrée : `f` (fonction scalaire). Sortie : float. Erreur : MecaStruct:BucklingEngine:noRoot si aucune racine.
    """
    xs = np.linspace(0.5, 20.0, 1951)
    ys = np.array([f(x) for x in xs])
    j = np.flatnonzero((np.sign(ys[:-1]) != np.sign(ys[1:])) | (ys[:-1] == 0))
    if j.size == 0:
        raise MecaStructError(_ID + "noRoot", "Aucune racine de l'équation caractéristique trouvée sur ]0,5 ; 20].")
    i = int(j[0])
    if ys[i] == 0:
        return float(xs[i])
    return brentq(f, xs[i], xs[i + 1], xtol=1e-14)


def _characteristicEquation(cond: str) -> dict:
    """Équation caractéristique, première racine kL (numérique) et vérification contre la référence du cours."""
    kLRef = _conditionInfo(cond)["kLRef"]
    latex, texte = _EQUATION_CARACT[cond]
    kL = _firstRoot(lambda x: _bcDeterminant(cond, x))
    return {
        "latex": latex,
        "text": texte,
        "kLReference": kLRef,
        "kLNumeric": kL,
        "kL": kL,
        "method": "numérique",
        "determinant": _DETERMINANT,
        "verified": abs(kL - kLRef) <= 1e-9 * kLRef,
    }


# ----------------------------------------------------------------- textes : dérivation, rapport, LaTeX


def _buildDerivation(cond: str, E: float, Imin: float, L: float, Lp: float, PE: float, ce: dict) -> list[str]:
    """Étapes LaTeX de la résolution de l'équation de flambage (v'' + k² v = 0)."""
    d = [r"$E\,I_{min}\,v''(s) = M_f(s),\ \ k^2 = \frac{P}{E\,I_{min}}$"]
    if cond == "articule-articule":
        d += [
            r"$M_f(s) = -P\,v(s) \Rightarrow v''(s) + k^2\,v(s) = 0$",
            r"$v(s) = A\cos(k\,s) + B\sin(k\,s)$",
            r"$v(0) = 0 \Rightarrow A = 0$",
            r"$v(L) = 0 \Rightarrow B\sin(k\,L) = 0$",
            r"$B \neq 0 \Rightarrow \sin(k\,L) = 0 \Rightarrow k\,L = n\,\pi$",
            r"$n = 1 : P_E = k^2\,E\,I_{min} = \frac{\pi^2\,E\,I_{min}}{L^2},\ \ L' = L$",
            r"$v(s) = B\sin\left(\frac{\pi\,s}{L}\right)$",
        ]
    elif cond == "encastre-libre":
        d += [
            r"$M_f(s) = P\,(\delta - v(s)),\ \ \delta = v(L)$",
            r"$v''(s) + k^2\,v(s) = k^2\,\delta$",
            r"$v(s) = A\cos(k\,s) + B\sin(k\,s) + \delta$",
            r"$v(0) = 0 \Rightarrow A = -\delta,\ \ v'(0) = 0 \Rightarrow B = 0$",
            r"$v(L) = \delta \Rightarrow \delta\cos(k\,L) = 0 \Rightarrow \cos(k\,L) = 0$",
            r"$k\,L = \frac{\pi}{2} \Rightarrow P_E = \frac{\pi^2\,E\,I_{min}}{(2\,L)^2},\ \ L' = 2\,L$",
            r"$v(s) = \delta\left(1 - \cos\frac{\pi\,s}{2\,L}\right)$",
        ]
    elif cond == "encastre-encastre":
        d += [
            r"$M_f(s) = M_0 - P\,v(s)\ \ \textrm{(mode symetrique)}$",
            r"$v''(s) + k^2\,v(s) = \frac{M_0}{E\,I_{min}}$",
            r"$v(s) = A\cos(k\,s) + B\sin(k\,s) + \frac{M_0}{P}$",
            r"$v(0) = 0,\ v'(0) = 0 \Rightarrow A = -\frac{M_0}{P},\ \ B = 0$",
            r"$v(L) = 0,\ v'(L) = 0 \Rightarrow \cos(k\,L) = 1,\ \ \sin(k\,L) = 0$",
            r"$\det = 2 - 2\cos(k\,L) - k\,L\,\sin(k\,L) = 0 \Rightarrow k\,L = 2\,\pi$",
            r"$P_E = \frac{4\,\pi^2\,E\,I_{min}}{L^2} = \frac{\pi^2\,E\,I_{min}}{(L/2)^2},\ \ L' = \frac{L}{2}$",
            r"$v(s) = \frac{1}{2}\left(1 - \cos\frac{2\,\pi\,s}{L}\right)$",
        ]
    else:  # encastre-articule
        kLx = ce["kLReference"]
        d += [
            r"$M_f(s) = R\,(L - s) - P\,v(s)\ \ \textrm{(R : reaction de l'articulation)}$",
            r"$v''(s) + k^2\,v(s) = \frac{R}{E\,I_{min}}\,(L - s)$",
            r"$v(s) = A\cos(k\,s) + B\sin(k\,s) + \frac{R}{P}\,(L - s)$",
            r"$v(0) = 0 \Rightarrow A = -\frac{R\,L}{P},\ \ v'(0) = 0 \Rightarrow B = \frac{R}{k\,P}$",
            r"$v(L) = 0 \Rightarrow \tan(k\,L) = k\,L$",
            f"$k\\,L = {kLx:.4f} \\Rightarrow P = \\frac{{{kLx**2:.4g}\\,E\\,I_{{min}}}}{{L^2}} = "
            f"\\frac{{\\pi^2\\,E\\,I_{{min}}}}{{({math.pi / kLx:.4f}\\,L)^2}}$",
            r"$\textrm{Cours : } L' = \frac{L}{\sqrt{2}} \Rightarrow P_E = \frac{2\,\pi^2\,E\,I_{min}}{L^2}$",
            r"$v(s) \propto \sin(k\,s) - k\,s + k\,L\,(1 - \cos(k\,s))$",
        ]
    if cond != "articule-articule":
        d.append(_REF_ARTICULE)
    d += [
        _ltx(
            r"$\textrm{Equation caracteristique : } ",
            ce["latex"][1:-1],
            r" \Rightarrow k\,L = ",
            f"{ce['kL']:.6g}",
            "$",
        ),
        _ltx(
            r"$P_E = \frac{\pi^2\,E\,I_{min}}{L'^2} = \frac{\pi^2 \times ",
            E,
            r" \times ",
            Imin,
            r"}{\left(",
            Lp,
            r"\right)^2} = ",
            PE,
            r"\ \mathrm{N}$",
        ),
        _ltx(
            r"$k = \sqrt{\frac{P_E}{E\,I_{min}}} = \frac{\pi}{L'} = ",
            math.pi / Lp,
            r"\ \mathrm{m^{-1}},\ \ L = ",
            L,
            r"\ \mathrm{m}$",
        ),
    ]
    return d


def _buildReport(r: dict, info: dict, hasP: bool, pNegative: bool) -> list[str]:
    """Rapport texte en français : démarche, régime, comparaison des trois modèles, vérification."""
    lc = r["lambdaCompression"]
    rep = [
        "=== Flambage — analyse selon l'arbre de décision du cours ===",
        f"Données : E = {r['E']:.5g} Pa ({r['E'] / 1e9:.4g} GPa), Re = {r['Re']:.5g} Pa ({r['Re'] / 1e6:.4g} MPa), "
        f"S = {r['S']:.5g} m² ({r['S'] * 1e6:.5g} mm²)",
        f"          Iz = {r['Iz']:.5g} m⁴, Iy = {r['Iy']:.5g} m⁴, L = {r['L']:.5g} m, "
        f"coefficient de sécurité s = {r['s']:.4g}",
        f"Conditions aux limites : {info['label']} → L' = {info['coefText']} × L = {r['Lp']:.5g} m",
        "1) Plan de flambage (la poutre flambe suivant l'inertie la plus faible) :",
        f"   Imin = min(Iz, Iy) = I{r['axis']} = {r['Imin']:.5g} m⁴ ; Imax = {r['Imax']:.5g} m⁴",
        "   " + r["planeText"],
        "2) Rayon de giration minimal :",
        f"   rmin = √(Imin/S) = √({r['Imin']:.5g}/{r['S']:.5g}) = {r['rmin']:.5g} m ({r['rmin'] * 1e3:.4g} mm)",
        "3) Élancement :",
        f"   λ = L'/rmin = {r['Lp']:.5g}/{r['rmin']:.5g} = {r['lambda']:.5g}",
        "4) Élancement limite (σE = Re) :",
        f"   λlim = π·√(E/Re) = π·√({r['E']:.5g}/{r['Re']:.5g}) = {r['lambdaLim']:.5g}",
        "5) Arbre de décision :",
        f"   λ < {lc:.4g} → compression simple ; {lc:.4g} ≤ λ < λlim → Rankine ; λ ≥ λlim → Euler",
    ]
    sE = r["sigmaE"] / 1e6
    reMPa = r["Re"] / 1e6
    if r["regime"] == "compression":
        rep += [
            f"   λ = {r['lambda']:.4g} < {lc:.4g} → régime retenu : COMPRESSION SIMPLE.",
            "   Poutre courte (trapue) : la ruine survient par écrasement/plastification de la section",
            "   avant toute instabilité ; la charge critique est la charge de plastification Pcrit = PC = Re·S.",
            f"   Euler n'est pas pertinent : σE = π²E/λ² = {sE:.5g} MPa > Re = {reMPa:.4g} MPa "
            "(la poutre plastifierait avant de flamber élastiquement).",
        ]
    elif r["regime"] == "rankine":
        rep += [
            f"   {lc:.4g} ≤ λ = {r['lambda']:.4g} < λlim = {r['lambdaLim']:.4g} → régime retenu : RANKINE.",
            "   Élancement intermédiaire : plastification et instabilité interagissent ; la formule de Rankine",
            "   1/PR = 1/PE + 1/PC combine les deux modes de ruine : Pcrit = PR = Re·S/(1 + (λ/λlim)²).",
            f"   Euler surestimerait la charge (σE = {sE:.5g} MPa > Re = {reMPa:.4g} MPa) et la compression "
            "simple ignorerait l'instabilité.",
        ]
    else:
        rep += [
            f"   λ = {r['lambda']:.4g} ≥ λlim = {r['lambdaLim']:.4g} → régime retenu : EULER.",
            f"   Poutre élancée : σE = π²E/λ² = {sE:.5g} MPa ≤ Re = {reMPa:.4g} MPa, l'instabilité "
            "élastique survient avant la plastification : Pcrit = PE = π²·E·Imin/L'².",
            "   La compression simple surestimerait la résistance (PC > PE) ; Rankine reste plus prudent (PR < PE).",
        ]
        if r["lambdaLim"] <= lc and r["lambda"] < lc:
            rep.append(
                f"   Cas particulier : λlim = {r['lambdaLim']:.4g} ≤ {lc:.4g} (zone de Rankine vide) ; "
                "Euler est retenu en priorité sur la compression simple car σE ≤ Re (choix sécuritaire)."
            )
    # comparaison des trois modèles, calculés quel que soit le régime
    names = [
        "Compression  PC = Re·S",
        "Euler        PE = π²E·Imin/L'²",
        "Rankine      PR = Re·S/(1+(λ/λlim)²)",
    ]
    vals = [r["PC"], r["PE"], r["PR"]]
    ids = ["compression", "euler", "rankine"]
    rep += [
        "6) Comparaison des trois modèles (calculés quel que soit le régime) :",
        f"   {'Modèle':<40} {'Charge critique':<28} {'σ = P/S':<14} P/Pcrit retenu",
    ]
    for nom, val, ident in zip(names, vals, ids, strict=True):
        marque = "  ← retenu" if ident == r["regime"] else ""
        rep.append(
            f"   {nom:<40} {val:>12.5g} N ({val / 1e3:>9.4g} kN)  {val / r['S'] / 1e6:>9.4g} MPa  "
            f"{val / r['Pcrit']:>8.4f}{marque}"
        )
    invSum = 1 / r["PE"] + 1 / r["PC"]
    imin = int(np.argmin(vals))
    rep += [
        f"   Contrôle de Rankine : 1/PR = {1 / r['PR']:.6g} N⁻¹ ; 1/PE + 1/PC = {invSum:.6g} N⁻¹ "
        f"(écart relatif {abs(1 / r['PR'] - invSum) / invSum:.1e})",
        f"   Contrainte critique d'Euler : σE = π²E/λ² = {r['sigmaE']:.5g} Pa ({sE:.5g} MPa)",
        f"   Modèle le plus défavorable : {names[imin].split()[0]} ({vals[imin]:.5g} N) ; "
        f"par construction PR ≤ min(PE, PC) (PR/min = {r['PR'] / min(r['PE'], r['PC']):.4f}).",
        "7) Charge critique et charge admissible :",
        f"   Pcrit = {_SYMBOLE_REGIME[r['regime']]} = {r['Pcrit']:.5g} N ({r['Pcrit'] / 1e3:.4g} kN) ; "
        f"σcrit = Pcrit/S = {r['sigmaCrit'] / 1e6:.5g} MPa",
        f"   Padm = Pcrit/s = {r['Pcrit']:.5g}/{r['s']:.4g} = {r['Padm']:.5g} N ({r['Padm'] / 1e3:.4g} kN) ; "
        f"σadm = {r['sigmaAdm'] / 1e6:.5g} MPa",
        "8) Vérification :",
    ]
    if hasP:
        if pNegative:
            rep.append("   P < 0 interprété comme un effort normal N < 0 (compression) : |P| retenu.")
        verdict, cmp = ("VÉRIFIÉ", "≤") if r["ok"] else ("NON VÉRIFIÉ (risque de flambage)", ">")
        rep += [
            f"   P = {r['P']:.5g} N ({r['P'] / 1e3:.4g} kN) ; σ = P/S = {r['sigmaApplied'] / 1e6:.5g} MPa",
            f"   P {cmp} Padm = {r['Padm']:.5g} N → {verdict}",
            f"   Coefficient de sécurité obtenu Pcrit/P = {r['safetyObtained']:.4g} (requis s = {r['s']:.4g}) ; "
            f"taux d'utilisation P/Padm = {100 * r['utilization']:.1f} %",
        ]
    else:
        rep.append("   Aucun effort P fourni : seule la charge admissible Padm est calculée.")
    mc = r["modeCheck"]
    ce = r["charEquation"]
    mcTxt = "conforme" if mc["ok"] else "NON conforme"
    rep += [
        "9) Mode propre de flambage (normalisé, max = 1) :",
        "   " + r["modeText"],
        f"   Vérification numérique : conditions aux limites "
        f"(résidu max {max(abs(x) for x in mc['bcResiduals']):.1e}), "
        f"équation v⁽⁴⁾ + k²v'' = 0 (résidu {mc['odeResidual']:.1e}), "
        f"différences finies (écart {mc['fdResidual']:.1e}) → {mcTxt}.",
        "   Conditions vérifiées : " + " ; ".join(mc["bcLabels"]),
        f"10) Résolution de l'équation différentielle (méthode {ce['method']}) :",
        "   E·Imin·v'' = Mf(s) avec Mf = −P·v (+ moment d'encastrement / réaction) ⇒ "
        "v'' + k²·v = second membre, k² = P/(E·Imin).",
        f"   Équation caractéristique : {ce['text']} ⇒ première racine kL = {ce['kL']:.10g} "
        f"(référence {ce['kLReference']:.10g}) → {'vérifiée' if ce['verified'] else 'NON vérifiée'}.",
        "   Solution générale v = A sin(ks) + B cos(ks) + C s + D ; les 4 conditions aux limites donnent",
        "   un système homogène M(kL)·{A B C D} = 0 dont le déterminant s'annule pour la charge critique.",
        f"   k = π/L' = {math.pi / r['Lp']:.5g} m⁻¹ ; P = k²·E·Imin = {r['PE']:.5g} N",
        "Remarques :",
    ]
    if r["condition"] == "encastre-articule":
        rep.append(
            f"   L' = L/√2 = 0,7071 L (valeur du cours). La résolution exacte (tan kL = kL, kL = {ce['kL']:.4f}) "
            f"donne L'exact = {ce['coefLpExact']:.4f} L, soit PE exact = {ce['PEexact']:.5g} N "
            f"({100 * (ce['PEexact'] / r['PE'] - 1):+.2f} % par rapport au cours) : "
            "la valeur du cours est légèrement sécuritaire."
        )
    if r["lambdaLim"] > lc:
        sigmaR = r["Re"] / (1 + (lc / r["lambdaLim"]) ** 2) / 1e6
        rep.append(
            "   La courbe de dimensionnement du cours est discontinue : en λ = "
            f"{lc:.4g}, Re → σR = {sigmaR:.4g} MPa ; en λ = λlim, σR = Re/2 alors que σE = Re."
        )
    if r["s"] < 1:
        rep.append("   Attention : coefficient de sécurité s < 1 (non sécuritaire).")
    rep.append(f"   Méthode de résolution : {r['methodUsed']}.")
    return rep


def _buildLatex(r: dict, info: dict, hasP: bool) -> list[str]:
    """Formules clés avec valeurs numériques, au format LaTeX (chaînes entre $)."""
    iName = "I_y" if r["axis"] == "y" else "I_z"
    lam, lc, lamLim = r["lambda"], r["lambdaCompression"], r["lambdaLim"]
    if r["regime"] == "compression":
        regLine = _ltx(r"$\lambda = ", lam, r" < \lambda_C = ", lc, r" \Rightarrow \textrm{compression simple}$")
        pName = "P_C"
    elif r["regime"] == "rankine":
        regLine = _ltx(
            r"$\lambda_C = ",
            lc,
            r" \le \lambda = ",
            lam,
            r" < \lambda_{lim} = ",
            lamLim,
            r" \Rightarrow \textrm{Rankine}$",
        )
        pName = "P_R"
    else:
        regLine = _ltx(r"$\lambda = ", lam, r" \ge \lambda_{lim} = ", lamLim, r" \Rightarrow \textrm{Euler}$")
        pName = "P_E"
    lat = [
        _ltx(r"$I_{min} = \min(I_z, I_y) = ", iName, " = ", r["Imin"], r"\ \mathrm{m^4}$"),
        _ltx(
            r"$r_{min} = \sqrt{\frac{I_{min}}{S}} = \sqrt{\frac{",
            r["Imin"],
            "}{",
            r["S"],
            "}} = ",
            r["rmin"],
            r"\ \mathrm{m}$",
        ),
        _ltx("$L' = ", info["coefTex"], r"\,L = ", r["Lp"], r"\ \mathrm{m}$"),
        _ltx(r"$\lambda = \frac{L'}{r_{min}} = \frac{", r["Lp"], "}{", r["rmin"], "} = ", lam, "$"),
        _ltx(
            r"$\lambda_{lim} = \pi\sqrt{\frac{E}{R_e}} = \pi\sqrt{\frac{", r["E"], "}{", r["Re"], "}} = ", lamLim, "$"
        ),
        regLine,
        _ltx(r"$P_C = R_e\,S = ", r["Re"], r" \times ", r["S"], " = ", r["PC"], r"\ \mathrm{N}$"),
        _ltx(
            r"$P_E = \frac{\pi^2\,E\,I_{min}}{L'^2} = \frac{\pi^2 \times ",
            r["E"],
            r" \times ",
            r["Imin"],
            r"}{\left(",
            r["Lp"],
            r"\right)^2} = ",
            r["PE"],
            r"\ \mathrm{N}$",
        ),
        _ltx(
            r"$P_R = \frac{R_e\,S}{1+\left(\frac{\lambda}{\lambda_{lim}}\right)^2} = \frac{",
            r["PC"],
            r"}{1+\left(\frac{",
            lam,
            "}{",
            lamLim,
            r"}\right)^2} = ",
            r["PR"],
            r"\ \mathrm{N}$",
        ),
        _ltx(r"$\frac{1}{P_R} = \frac{1}{P_E} + \frac{1}{P_C} = ", 1 / r["PR"], r"\ \mathrm{N^{-1}}$"),
        _ltx(r"$\sigma_E = \frac{\pi^2\,E}{\lambda^2} = ", r["sigmaE"], r"\ \mathrm{Pa}$"),
        _ltx(
            r"$P_{crit} = " + pName + " = ",
            r["Pcrit"],
            r"\ \mathrm{N} \Rightarrow P_{adm} = \frac{P_{crit}}{s} = \frac{",
            r["Pcrit"],
            "}{",
            r["s"],
            "} = ",
            r["Padm"],
            r"\ \mathrm{N}$",
        ),
    ]
    if hasP:
        cmp = r"\le" if r["ok"] else ">"
        lat += [
            _ltx(r"$P = ", r["P"], r"\ \mathrm{N} " + cmp + r" P_{adm} = ", r["Padm"], r"\ \mathrm{N}$"),
            _ltx(
                r"$\sigma = \frac{P}{S} = ",
                r["sigmaApplied"],
                r"\ \mathrm{Pa},\ \ \frac{P_{crit}}{P} = ",
                r["safetyObtained"],
                "$",
            ),
        ]
    return lat


# ----------------------------------------------------------------- API publique


def analyze(p: dict) -> dict:
    """Analyse au flambage d'une poutre droite comprimée, selon l'arbre de décision du cours.

    Entrées (dict, SI) : E (Pa), Re (Pa), S (m²), Iz et Iy (m⁴), L (m), condition (texte), s (coefficient de
    sécurité, défaut 1), P (N de compression, optionnel ; None, vide ou NaN = absent ; un P négatif est lu comme
    N < 0, on retient |P|), lambdaCompression (défaut 20), useSymbolic (accepté, le chemin symbolique n'est pas
    porté : methodUsed vaut toujours 'numérique').
    Sortie : dict des charges (PC, PE, PR, Pcrit, Padm, ok…), du mode propre (modeShape, modeK, modeSMax…),
    charEquation, derivation, methodUsed, report et latex.
    Erreur : MecaStruct:BucklingEngine:* si une donnée est absente ou invalide.
    """
    if not isinstance(p, dict):
        raise MecaStructError(_ID + "invalidInput", "Les données du flambage doivent être une structure scalaire p.")
    for champ in _CHAMPS:
        if champ not in p:
            raise MecaStructError(_ID + "missingField", f"Champ obligatoire manquant pour le flambage : p.{champ}.")
    E = _positif(p["E"], "E (module d'Young)")
    Re = _positif(p["Re"], "Re (limite élastique)")
    S = _positif(p["S"], "S (aire de la section)")
    Iz = _positif(p["Iz"], "Iz (moment quadratique)")
    Iy = _positif(p["Iy"], "Iy (moment quadratique)")
    L = _positif(p["L"], "L (longueur)")
    cond = _condition(p["condition"])
    sf = 1.0 if _absent(p.get("s")) else _positif(p["s"], "s (coefficient de sécurité)")
    lc = (
        20.0
        if _absent(p.get("lambdaCompression"))
        else _positifOuNul(p["lambdaCompression"], "lambdaCompression (élancement de fin de compression simple)")
    )
    hasP, Pval, pNegative = False, math.nan, False
    P = p.get("P")
    if not _absent(P):
        if not is_num(P) or math.isinf(P):
            raise MecaStructError(
                _ID + "invalidInput", "L'effort de compression P doit être un scalaire réel fini (N)."
            )
        if not math.isnan(P):
            hasP, pNegative, Pval = True, P < 0, abs(float(P))
    info = _conditionInfo(cond)

    # plan de flambage : inertie la plus faible
    tolI = 1e-12 * max(Iz, Iy)
    if Iy < Iz - tolI:
        Imin, Imax, ax = Iy, Iz, "y"
        planeText = (
            "Flambage dans le plan (x, z) : flexion autour de l'axe (G, y), déplacement w selon z "
            f"(Imin = Iy = {Iy:.5g} m⁴ < Iz = {Iz:.5g} m⁴)."
        )
    elif Iz < Iy - tolI:
        Imin, Imax, ax = Iz, Iy, "z"
        planeText = (
            "Flambage dans le plan (x, y) : flexion autour de l'axe (G, z), déplacement v selon y "
            f"(Imin = Iz = {Iz:.5g} m⁴ < Iy = {Iy:.5g} m⁴)."
        )
    else:
        Imin, Imax, ax = min(Iz, Iy), max(Iz, Iy), "z"
        planeText = (
            f"Iz = Iy = {Imin:.5g} m⁴ : toutes les directions transversales sont équivalentes ; "
            "plan (x, y) retenu par convention (flexion autour de (G, z))."
        )

    # rayon de giration, longueur de flambage, élancements
    rmin = math.sqrt(Imin / S)
    coefLp = info["coef"]
    Lp = coefLp * L
    lam = Lp / rmin
    lambdaLim = math.pi * math.sqrt(E / Re)

    # les trois modèles, calculés quel que soit le régime
    PC = Re * S
    PE = math.pi**2 * E * Imin / Lp**2
    PR = Re * S / (1 + (lam / lambdaLim) ** 2)
    sigmaE = math.pi**2 * E / lam**2

    # arbre de décision
    if lam >= lambdaLim:
        regime, Pcrit = "euler", PE
    elif lam < lc:
        regime, Pcrit = "compression", PC
    else:
        regime, Pcrit = "rankine", PR
    Padm = Pcrit / sf
    sigmaCrit = Pcrit / S
    sigmaAdm = Padm / S

    if hasP:
        ok = Pval <= Padm
        sigmaApplied = Pval / S
        safetyObtained = Pcrit / Pval if Pval > 0 else math.inf
        utilization = Pval / Padm
    else:
        ok, sigmaApplied, safetyObtained, utilization = None, math.nan, math.nan, math.nan

    md = _modeFunctions(cond, L)
    modeCheck = _checkMode(md, cond, L)
    ce = _characteristicEquation(cond)
    ce["kLCourse"] = math.pi / coefLp
    ce["coefLpExact"] = math.pi / ce["kL"]
    ce["PEexact"] = ce["kL"] ** 2 * E * Imin / L**2
    derivation = _buildDerivation(cond, E, Imin, L, Lp, PE, ce)

    r = {
        "condition": cond,
        "conditionText": info["label"],
        "E": E,
        "Re": Re,
        "S": S,
        "Iz": Iz,
        "Iy": Iy,
        "L": L,
        "s": sf,
        "Imin": Imin,
        "Imax": Imax,
        "axis": ax,
        "planeText": planeText,
        "rmin": rmin,
        "coefLp": coefLp,
        "Lp": Lp,
        "lambda": lam,
        "lambdaLim": lambdaLim,
        "lambdaCompression": lc,
        "regime": regime,
        "PC": PC,
        "PE": PE,
        "PR": PR,
        "sigmaE": sigmaE,
        "Pcrit": Pcrit,
        "Padm": Padm,
        "sigmaCrit": sigmaCrit,
        "sigmaAdm": sigmaAdm,
        "P": Pval,
        "ok": ok,
        "sigmaApplied": sigmaApplied,
        "safetyObtained": safetyObtained,
        "utilization": utilization,
        "modeShape": md["v"],
        "modeDerivatives": {"d1": md["d1"], "d2": md["d2"], "d3": md["d3"], "d4": md["d4"]},
        "modeK": md["k"],
        "modeSMax": md["sMax"],
        "modeText": md["text"],
        "modeCheck": modeCheck,
        "charEquation": ce,
        "derivation": derivation,
        "methodUsed": ce["method"],
    }
    r["report"] = _buildReport(r, info, hasP, pNegative)
    r["latex"] = _buildLatex(r, info, hasP)
    return r


def stabilityCurve(E: float, Re: float | None = None, lambdaVec=None, lambdaCompression: float | None = None) -> dict:
    """Courbes de stabilité σcr(λ) : palier, Euler, Rankine et courbe de dimensionnement (arbre de décision).

    Entrées : E (Pa), Re (Pa), lambdaVec (élancements ≥ 0, vecteur ou nombre ; défaut 0 à 300 pas 0,5),
    lambdaCompression (défaut 20).
    Sortie : dict lambda, sigmaEuler (NaN en λ = 0), sigmaRankine, sigmaPalier, sigmaDesign (Pa), zone (1, 2, 3),
    lambdaLim, lambdaCompression, E, Re, report et latex.
    Erreur : MecaStruct:BucklingEngine:invalidInput si E, Re ou lambdaVec sont invalides.
    """
    if Re is None:
        raise MecaStructError(_ID + "invalidInput", "stabilityCurve attend au moins E et Re.")
    E = _positif(E, "E (module d'Young)")
    Re = _positif(Re, "Re (limite élastique)")
    lc = (
        20.0
        if _absent(lambdaCompression)
        else _positifOuNul(lambdaCompression, "lambdaCompression (élancement de fin de compression simple)")
    )
    if _absent(lambdaVec):
        lam = np.arange(0.0, 300.5, 0.5)
    else:
        try:
            arr = np.asarray(lambdaVec, dtype=float)
        except (TypeError, ValueError) as err:
            raise MecaStructError(_ID + "invalidInput", "lambdaVec doit être un vecteur réel.") from err
        if arr.ndim > 2 or (arr.ndim == 2 and 1 not in arr.shape) or not np.all(np.isfinite(arr)) or np.any(arr < 0):
            raise MecaStructError(
                _ID + "invalidInput",
                "lambdaVec doit être un vecteur réel d'élancements finis et positifs ou nuls.",
            )
        lam = arr.reshape(-1)
    lambdaLim = math.pi * math.sqrt(E / Re)

    with np.errstate(divide="ignore"):
        sigmaEuler = math.pi**2 * E / lam**2
    sigmaEuler[lam == 0] = math.nan
    sigmaRankine = Re / (1 + (lam / lambdaLim) ** 2)
    sigmaPalier = np.full(lam.shape, Re)

    isEuler = lam >= lambdaLim
    isComp = ~isEuler & (lam < lc)
    isRank = ~isEuler & ~isComp
    zone = np.zeros(lam.shape)
    zone[isComp] = 1
    zone[isRank] = 2
    zone[isEuler] = 3
    sigmaDesign = sigmaPalier.copy()
    sigmaDesign[isRank] = sigmaRankine[isRank]
    sigmaDesign[isEuler] = sigmaEuler[isEuler]

    rep = [
        "=== Courbe de stabilité σcr(λ) ===",
        f"E = {E:.5g} Pa ({E / 1e9:.4g} GPa), Re = {Re:.5g} Pa ({Re / 1e6:.4g} MPa)",
        f"Élancement limite : λlim = π·√(E/Re) = {lambdaLim:.5g} (σE(λlim) = Re)",
        f"Domaine tracé : λ ∈ [{lam.min():.4g} ; {lam.max():.4g}] ({lam.size} points)",
        f"Palier de compression simple : σ = Re = {Re / 1e6:.4g} MPa pour λ < {lc:.4g}",
        f"Rankine : σR = Re/(1 + (λ/λlim)²) pour {lc:.4g} ≤ λ < {lambdaLim:.4g}",
        f"Euler : σE = π²E/λ² pour λ ≥ {lambdaLim:.4g} (non défini en λ = 0 : valeur NaN)",
    ]
    if lambdaLim > lc:
        sigmaR = Re / (1 + (lc / lambdaLim) ** 2) / 1e6
        rep.append(
            "Remarque : la courbe de dimensionnement du cours est discontinue : "
            f"en λ = {lc:.4g}, Re → σR = {sigmaR:.4g} MPa ; en λ = λlim, σR = Re/2 = {Re / 2e6:.4g} MPa "
            f"→ σE = Re = {Re / 1e6:.4g} MPa."
        )
    else:
        rep.append(
            f"Remarque : λlim = {lambdaLim:.4g} ≤ {lc:.4g} : zone de Rankine vide ; "
            "Euler est retenu dès λ ≥ λlim (choix sécuritaire)."
        )
    latex = [
        _ltx(r"$\lambda_{lim} = \pi\sqrt{\frac{E}{R_e}} = \pi\sqrt{\frac{", E, "}{", Re, "}} = ", lambdaLim, "$"),
        r"$\sigma_E = \frac{\pi^2\,E}{\lambda^2}\ \ (\lambda \ge \lambda_{lim})$",
        _ltx(
            r"$\sigma_R = \frac{R_e}{1+\left(\frac{\lambda}{\lambda_{lim}}\right)^2}\ \ (",
            lc,
            r" \le \lambda < \lambda_{lim})$",
        ),
        _ltx(r"$\sigma = R_e = ", Re, r"\ \mathrm{Pa}\ \ (\lambda < ", lc, ")$"),
    ]
    return {
        "lambda": lam,
        "sigmaEuler": sigmaEuler,
        "sigmaRankine": sigmaRankine,
        "sigmaPalier": sigmaPalier,
        "sigmaDesign": sigmaDesign,
        "zone": zone,
        "lambdaLim": lambdaLim,
        "lambdaCompression": lc,
        "E": E,
        "Re": Re,
        "report": rep,
        "latex": latex,
    }


def listConditions() -> list[dict]:
    """Conditions aux limites reconnues, avec leur libellé et leur coefficient de longueur de flambage.

    Sortie : liste de dicts Condition (identifiant à passer dans p['condition']), Libelle, Coefficient (L'/L),
    CoefficientTexte.
    """
    lignes = []
    for cond in _IDENTIFIANTS:
        info = _conditionInfo(cond)
        lignes.append(
            {
                "Condition": cond,
                "Libelle": info["label"],
                "Coefficient": info["coef"],
                "CoefficientTexte": info["coefText"],
            }
        )
    return lignes


def effectiveLengthCoefficient(condition: str) -> float:
    """Coefficient L'/L de la longueur de flambage, valeurs du cours.

    Entrée : `condition` (texte, voir analyze). Sortie : 2 (encastré-libre), 1 (articulé-articulé),
    1/√2 (encastré-articulé) ou 1/2 (encastré-encastré).
    """
    return _conditionInfo(_condition(condition))["coef"]
