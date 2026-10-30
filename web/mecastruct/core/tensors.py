"""Tenseurs, cercles de Mohr, critères de résistance et lieux de plasticité : port de TensorAndCriteriaEngine.m (E15).

principal : contraintes principales, invariants, directions et grandeurs octaédriques ; facet : contrainte sur une
facette ; plane2D et plane2DStrain : cercles de Mohr 2D (contraintes et déformations) ; mohr3D : tricercle ;
criteria : Tresca, Von Mises et Rankine ; yieldLoci : lieux de plasticité en contraintes planes.
Unités SI strictes (Pa, déformations sans dimension, angles en rad). Chaque résultat contient `report` et `latex`.
Le polynôme caractéristique exact passe par SymPy si `useSymbolic=True` ; sinon methodUsed = 'numérique'.
"""

import math
import re

import numpy as np

from mecastruct.core.data_manager import hasSymbolic
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import _g, _texNum
from mecastruct.core.utils import is_num

_ID = "MecaStruct:TensorAndCriteriaEngine:"
_SUPERSCRITS = ["", "", "²", "³", "⁴", "⁵", "⁶"]  # indexé par la puissance p


# -------------------------------------------------------------------------------------------------
# Contrôles et conversions d'entrées
# -------------------------------------------------------------------------------------------------
def _erreur(identifiant: str, message: str) -> MecaStructError:
    """Erreur 'MecaStruct:TensorAndCriteriaEngine:<identifiant>' avec son message."""
    return MecaStructError(_ID + identifiant, message)


def _reelFini(x) -> bool:
    """Vrai pour un tableau numérique réel, non vide, dont toutes les valeurs sont finies."""
    a = np.asarray(x)
    return a.size > 0 and a.dtype.kind in "iuf" and bool(np.all(np.isfinite(a)))


def _scalaire(x, nom: str) -> float:
    """Scalaire réel fini (scalarIn)."""
    if not is_num(x) or not math.isfinite(x):
        raise _erreur("badInput", f"{nom} doit être un scalaire réel fini.")
    return float(x)


def _positif(x, nom: str) -> float:
    """Scalaire réel fini strictement positif (posScalar)."""
    x = _scalaire(x, nom)
    if x <= 0:
        raise _erreur("badInput", f"{nom} doit être strictement positif.")
    return x


def _tableau(x, nom: str) -> np.ndarray:
    """Tableau réel fini non vide, forme conservée (arrayIn)."""
    if not _reelFini(x):
        raise _erreur("badInput", f"{nom} doit être un tableau numérique réel, fini et non vide.")
    return np.asarray(x, dtype=float)


def _voigtToTensor(v) -> np.ndarray:
    """Tenseur 3x3 de contraintes d'un vecteur de Voigt 6 composantes [xx yy zz yz xz xy] (Pa)."""
    v = np.asarray(v, dtype=float).ravel()
    return np.array([[v[0], v[5], v[4]], [v[5], v[1], v[3]], [v[4], v[3], v[2]]])


def _tenseur(T, nom: str) -> np.ndarray:
    """Tenseur symétrique 3x3 validé : 2x2 complété par des zéros, vecteur de Voigt à 6 composantes accepté."""
    if not _reelFini(T):
        raise _erreur("badInput", f"Le tenseur {nom} doit être numérique, réel et fini.")
    A = np.asarray(T, dtype=float)
    if A.shape == (2, 2):
        A = np.block([[A, np.zeros((2, 1))], [np.zeros((1, 3))]])
    elif A.ndim == 1 and A.size == 6:
        A = _voigtToTensor(A)
    elif A.shape != (3, 3):
        raise _erreur("badInput", f"{nom} doit être un tenseur 3x3 (ou 2x2, ou un vecteur de Voigt à 6 composantes).")
    sc = np.max(np.abs(A))
    asym = np.max(np.abs(A - A.T))
    if sc > 0 and asym > 1e-10 * sc:
        raise _erreur("notSymmetric", f"Le tenseur {nom} n'est pas symétrique (écart max {asym:g}).")
    return (A + A.T) / 2


def _vecteur3(v, nom: str) -> np.ndarray:
    """Vecteur à 3 composantes réelles finies (2 composantes complétées par 0 en plan)."""
    if not _reelFini(v) or np.ndim(v) > 2:
        raise _erreur("badInput", f"Le vecteur {nom} doit être numérique, réel et fini.")
    A = np.asarray(v, dtype=float).ravel()
    if A.size == 2:
        return np.append(A, 0.0)
    if A.size != 3:
        raise _erreur("badInput", f"Le vecteur {nom} doit avoir 3 composantes (ou 2 en plan).")
    return A


def _principalTriplet(pr) -> np.ndarray:
    """Contraintes principales décroissantes [σI σII σIII] depuis [σI σII σIII], [σ1 σ2], un tenseur ou Voigt."""
    if not _reelFini(pr):
        raise _erreur("badInput", "Les contraintes principales doivent être numériques, réelles et finies.")
    A = np.asarray(pr, dtype=float)
    if A.shape in ((3, 3), (2, 2)):
        return np.sort(np.linalg.eigvalsh(_tenseur(A, "pr")))[::-1]
    if A.ndim == 1 and A.size == 3:
        return np.sort(A)[::-1]
    if A.ndim == 1 and A.size == 2:
        return np.sort(np.append(A, 0.0))[::-1]
    if A.ndim == 1 and A.size == 6:
        return np.sort(np.linalg.eigvalsh(_voigtToTensor(A)))[::-1]
    raise _erreur("badInput", "pr doit être [σI σII σIII], [σ1 σ2] (état plan) ou un tenseur 3x3.")


def _echelle(*valeurs) -> float:
    """Ordre de grandeur des valeurs (max des |x|, 1 si toutes nulles) : tolérances et affichage."""
    m = max(float(np.max(np.abs(v))) for v in valeurs)
    return m if m > 0 else 1.0


def _rapport(a: float, b: float) -> float:
    """a / b, valant +Inf si b est nul (safeRatio)."""
    return math.inf if b == 0 else a / b


def _clean(x, ref: float):
    """Annule les résidus d'arrondi (|x| ≤ 1e-12·ref) pour l'affichage ; -0 écrit 0."""
    x = np.asarray(x, dtype=float)
    return np.where(np.abs(x) <= 1e-12 * ref, 0.0, x) + 0.0


def _mpa(x, ref: float):
    """Valeur en Pa ramenée en MPa pour l'affichage, résidus annulés."""
    return _clean(x, ref) / 1e6


# -------------------------------------------------------------------------------------------------
# Formats de texte et LaTeX (mêmes règles que MATLAB : %g, exposants en \cdot 10^{n})
# -------------------------------------------------------------------------------------------------
def _fmt(x, prec: int = 6) -> str:
    """Texte d'un nombre à prec chiffres significatifs (NaN, Inf et -Inf écrits comme MATLAB)."""
    return _g(float(x) + 0.0, f".{prec}g")


def _tex(x, prec: int = 5) -> str:
    """Nombre LaTeX à prec chiffres significatifs (puissances de 10 sous la forme \\cdot 10^{n})."""
    return _texNum(float(x), f".{prec}g")


def _vecTxt(v, prec: int = 6) -> str:
    """Vecteur en texte : (a ; b ; c)."""
    return "(" + " ; ".join(_fmt(x, prec) for x in np.ravel(v)) + ")"


def _vecTex(v, prec: int = 5) -> str:
    """Vecteur en LaTeX : (a,\\ b,\\ c)."""
    return "(" + ",\\ ".join(_tex(x, prec) for x in np.ravel(v)) + ")"


def _matTex(M) -> str:
    """Matrice en LaTeX, environnement array entre crochets."""
    lignes = [" & ".join(_tex(x) for x in ligne) for ligne in M]
    return r"\left[ \begin{array}{" + "c" * M.shape[1] + "} " + " \\\\ ".join(lignes) + r" \end{array} \right]"


def _polyTex(c, var: str) -> str:
    """Polynôme en LaTeX, coefficients décroissants (ordre polyval), termes nuls omis."""
    n = len(c) - 1
    s = ""
    for k, ak in enumerate(c):
        p = n - k
        a = float(ak) + 0.0
        if a == 0:
            continue
        mag = abs(a)
        cs = _tex(mag, 6) if (p == 0 or mag != 1) else ""
        if p == 0:
            terme = cs
        elif p == 1:
            terme = f"{cs}\\,{var}".strip()
        else:
            terme = f"{cs}\\,{var}^{{{p}}}"
        if cs == "" and p > 0:
            terme = re.sub(r"^\\,", "", terme)
        if s == "":
            s = ("-" + terme) if a < 0 else terme
        else:
            s += (" - " if a < 0 else " + ") + terme
    return s or "0"


def _polyTxt(c, var: str) -> str:
    """Polynôme en texte, coefficients décroissants (ex. 3·λ² − 2·λ + 1)."""
    n = len(c) - 1
    s = ""
    for k, ak in enumerate(c):
        p = n - k
        a = float(ak) + 0.0
        if a == 0:
            continue
        mag = abs(a)
        cs = _fmt(mag, 6) if (p == 0 or mag != 1) else ""
        if p == 0:
            terme = cs
        else:
            pw = _SUPERSCRITS[p] if 2 <= p <= 6 else ("" if p == 1 else f"^{p}")
            terme = var + pw if cs == "" else f"{cs}·{var}{pw}"
        if s == "":
            s = ("−" + terme) if a < 0 else terme
        else:
            s += (" − " if a < 0 else " + ") + terme
    return s or "0"


def _polynomeSymbolique(T: np.ndarray) -> list[float]:
    """Coefficients décroissants de det(T − λI) calculés exactement par SymPy (T en MPa, floats convertis)."""
    import sympy

    lam = sympy.Symbol("lambda")
    M = sympy.Matrix(3, 3, lambda i, j: sympy.Rational(T[i, j]))
    pl = sympy.expand((M - lam * sympy.eye(3)).det())
    cs = [float(c) for c in sympy.Poly(pl, lam).all_coeffs()]
    return [0.0] * (4 - len(cs)) + cs


def _mohrCore(a: float, b: float, c: float, theta) -> dict:
    """Cercle de Mohr 2D commun aux contraintes et aux déformations tensorielles (a, b, c = σxx, σyy, σxy)."""
    phi = np.linspace(0, 2 * np.pi, 361)
    delta = (a + b) / 2
    rho = math.hypot((a - b) / 2, c)
    circle = np.column_stack([delta + rho * np.cos(phi), rho * np.sin(phi)])
    circle[-1] = circle[0]
    thetaP = 0.5 * math.atan2(2 * c, a - b)
    return {
        "theta": theta,
        "sigma": (a + b) / 2 + (a - b) / 2 * np.cos(2 * theta) + c * np.sin(2 * theta),
        "tau": -(a - b) / 2 * np.sin(2 * theta) + c * np.cos(2 * theta),
        "delta": delta,
        "rho": rho,
        "sigma1": delta + rho,
        "sigma2": delta - rho,
        "thetaP": thetaP,
        "thetaTauMax": thetaP - math.pi / 4,
        "tauMax2D": rho,
        "pointA": np.array([a, c]),
        "pointB": np.array([b, -c]),
        "circle": circle,
    }


# -------------------------------------------------------------------------------------------------
# Fonctions publiques
# -------------------------------------------------------------------------------------------------
def principal(sig, useSymbolic: bool | None = None) -> dict:
    """Contraintes principales, invariants, directions principales et grandeurs octaédriques d'un tenseur.

    Entrées : `sig` (tenseur 3x3 symétrique en Pa ; 2x2 complété par des zéros ; vecteur de Voigt à 6 composantes),
    `useSymbolic` (None ou False : numérique ; True : polynôme caractéristique exact par SymPy si installé).
    Sortie : dict avec sigmaI ≥ sigmaII ≥ sigmaIII (Pa), directions (colonnes unitaires, trièdre direct), I1, I2 (Pa²),
    I3 (Pa³), charPoly, rootsCharPoly, eigVals, tauMax, sigmaOct, tauOct, J2, J3, methodUsed, report, latex.
    """
    T = _tenseur(sig, "sig")
    symbolique = bool(useSymbolic) and hasSymbolic()
    sc = _echelle(T)

    I1 = float(np.trace(T))
    I2 = (T[0, 0] * T[1, 1] - T[0, 1] ** 2) + (T[0, 0] * T[2, 2] - T[0, 2] ** 2) + (T[2, 2] * T[1, 1] - T[1, 2] ** 2)
    I3 = float(np.linalg.det(T))
    charPoly = np.array([1.0, -I1, I2, -I3])

    # Méthode 1 : racines du polynôme caractéristique, mis à l'échelle pour le conditionnement
    rr = np.sort(np.real(np.roots([1.0, -I1 / sc, I2 / sc**2, -I3 / sc**3])) * sc)[::-1]

    # Méthode 2 : valeurs et vecteurs propres, signes fixés comme dans TensorAndCriteriaEngine.m
    ev, V = np.linalg.eigh(T)
    ordre = np.argsort(-ev, kind="stable")
    ev, V = ev[ordre], V[:, ordre]
    V[:, 0] /= np.linalg.norm(V[:, 0])
    V[:, 1] -= (V[:, 0] @ V[:, 1]) * V[:, 0]
    V[:, 1] /= np.linalg.norm(V[:, 1])
    for k in range(2):
        if V[np.argmax(np.abs(V[:, k])), k] < 0:
            V[:, k] = -V[:, k]
    V[:, 2] = np.cross(V[:, 0], V[:, 1])
    V[:, 2] /= np.linalg.norm(V[:, 2])
    res = np.array([np.linalg.norm(T @ V[:, k] - ev[k] * V[:, k]) / sc for k in range(3)])
    rootsEigDiff = np.max(np.abs(rr - ev)) / sc

    tauMax = (ev[0] - ev[2]) / 2
    sigmaOct = I1 / 3
    tauOct = math.sqrt((ev[0] - ev[1]) ** 2 + (ev[1] - ev[2]) ** 2 + (ev[2] - ev[0]) ** 2) / 3
    Sdev = T - sigmaOct * np.eye(3)
    J2 = 0.5 * float(np.sum(Sdev**2))
    J3 = float(np.linalg.det(Sdev))

    # Polynôme caractéristique symbolique (optionnel)
    charPolySym = []
    symTex = symTxt = symNote = ""
    symErr = math.nan
    methodUsed = "numérique"
    if symbolique:
        try:
            cs = _polynomeSymbolique(T / 1e6)
            csym = -np.array(cs) * np.array([1.0, 1e6, 1e12, 1e18])
            charPolySym = csym.tolist()
            symErr = float(np.max(np.abs((csym - charPoly) / np.array([1.0, sc, sc**2, sc**3]))))
            symTex = _polyTex(cs, r"\lambda")
            symTxt = _polyTxt(cs, "λ")
            methodUsed = "symbolique"
        except Exception as exc:  # repli numérique, message conservé pour le rapport
            symNote = str(exc)

    # Valeurs nettoyées pour l'affichage (MPa)
    Tc = _mpa(T, sc)
    evc = _mpa(ev, sc)
    rrc = _clean(rr, sc * 1e3) / 1e6
    I1c = _mpa(I1, sc)
    I2c = _clean(I2, sc**2) / 1e12
    I3c = _clean(I3, sc**3) / 1e18
    Vc = _clean(V, 1.0)
    pMPa = [1.0, -I1c, I2c, -I3c]
    tmc = _mpa(tauMax, sc)
    toc = _mpa(tauOct, sc)
    soc = _mpa(sigmaOct, sc)

    rep = ["Analyse du tenseur des contraintes σ (valeurs en MPa) :"]
    rep += [f"   | {_fmt(a):>12} {_fmt(b):>12} {_fmt(c):>12} |" for a, b, c in Tc]
    rep += [
        "Invariants :",
        f"   I1 = tr σ = {_fmt(I1c)} MPa",
        "   I2 = (σxx·σyy − σxy²) + (σxx·σzz − σxz²) + (σzz·σyy − σyz²) = " + _fmt(I2c) + " MPa²",
        f"   I3 = det σ = {_fmt(I3c)} MPa³",
        "Équation caractéristique det(σ − σi·I) = 0 ⇔ σi³ − I1·σi² + I2·σi − I3 = 0 : "
        + _polyTxt(pMPa, "λ")
        + " = 0 (λ en MPa)",
    ]
    if methodUsed == "symbolique":
        rep += [
            f"Calcul symbolique (SymPy) : det(σ − λ·I) = {symTxt}",
            f"   écart relatif avec les invariants calculés numériquement : {symErr:.2e}",
        ]
    elif symbolique:
        rep.append("Calcul symbolique indisponible (repli numérique) : " + symNote)
    rep += [
        f"Méthode 1 — racines du polynôme caractéristique (roots) : {_vecTxt(rrc, 6)} MPa",
        f"Méthode 2 — valeurs propres du tenseur (eig) : {_vecTxt(evc, 6)} MPa",
        f"   écart relatif maximal roots / eig : {rootsEigDiff:.2e}",
        f"Contraintes principales (σI ≥ σII ≥ σIII) : σI = {_fmt(evc[0])} MPa ; σII = {_fmt(evc[1])} MPa ; "
        f"σIII = {_fmt(evc[2])} MPa",
        "Directions principales, solutions de (σ − σi·I)·ni = 0 (unitaires, trièdre direct) :",
    ]
    rep += [f"   n{nom} = {_vecTxt(Vc[:, k], 5)}" for k, nom in enumerate(["I", "II", "III"])]
    rep += [
        f"   det[nI nII nIII] = {np.linalg.det(V):.6f} ; résidu max ||(σ − σi·I)·ni|| / max|σij| = {max(res):.2e}",
        f"Cisaillement maximal : τmax = (σI − σIII)/2 = {_fmt(tmc)} MPa",
        f"Facette octaédrique : σoct = I1/3 = {_fmt(soc)} MPa ; τoct = (1/3)·√((σI−σII)² + (σII−σIII)² + "
        f"(σIII−σI)²) = {_fmt(toc)} MPa",
        f"Déviateur : J2 = {_fmt(J2 / 1e12)} MPa² ; J3 = {_fmt(_clean(J3, sc**3) / 1e18)} MPa³ ; "
        f"√(3·J2) = {_fmt(math.sqrt(3 * J2) / 1e6)} MPa (contrainte de Von Mises)",
        f"Méthode du polynôme caractéristique : {methodUsed}",
    ]

    lat = [
        r"$\sigma = " + _matTex(Tc) + r"\ \mathrm{MPa}$",
        r"$I_1 = \mathrm{tr}\,\sigma = " + _tex(I1c) + r"\ \mathrm{MPa}$",
        r"$I_2 = (\sigma_{xx}\sigma_{yy} - \sigma_{xy}^2) + (\sigma_{xx}\sigma_{zz} - \sigma_{xz}^2) + "
        r"(\sigma_{zz}\sigma_{yy} - \sigma_{yz}^2) = " + _tex(I2c) + r"\ \mathrm{MPa}^2$",
        r"$I_3 = \mathrm{det}\,\sigma = " + _tex(I3c) + r"\ \mathrm{MPa}^3$",
        r"$\sigma_i^3 - I_1\,\sigma_i^2 + I_2\,\sigma_i - I_3 = 0\ \ \Rightarrow\ \ "
        + _polyTex(pMPa, r"\lambda")
        + " = 0$",
    ]
    if methodUsed == "symbolique":
        lat.append(r"$\mathrm{det}(\sigma - \lambda I) = " + symTex + r" = 0\ \ (\lambda\ \mathrm{en\ MPa})$")
    lat += [
        r"$\sigma_I = "
        + _tex(evc[0])
        + r",\ \ \sigma_{II} = "
        + _tex(evc[1])
        + r",\ \ \sigma_{III} = "
        + _tex(evc[2])
        + r"\ \mathrm{MPa}$",
        r"$\vec{n}_I = "
        + _vecTex(Vc[:, 0], 4)
        + r",\ \ \vec{n}_{II} = "
        + _vecTex(Vc[:, 1], 4)
        + r",\ \ \vec{n}_{III} = "
        + _vecTex(Vc[:, 2], 4)
        + r"$",
        r"$\tau_{max} = \frac{\sigma_I - \sigma_{III}}{2} = " + _tex(tmc) + r"\ \mathrm{MPa}$",
        r"$\sigma_{oct} = \frac{I_1}{3} = " + _tex(soc) + r"\ \mathrm{MPa}$",
        r"$\tau_{oct} = \frac{1}{3}\sqrt{(\sigma_I-\sigma_{II})^2 + (\sigma_{II}-\sigma_{III})^2 + "
        r"(\sigma_{III}-\sigma_I)^2} = " + _tex(toc) + r"\ \mathrm{MPa}$",
    ]

    return {
        "sigma": T,
        "I1": I1,
        "I2": I2,
        "I3": I3,
        "charPoly": charPoly,
        "rootsCharPoly": rr,
        "eigVals": ev,
        "rootsEigDiff": rootsEigDiff,
        "sigmaI": ev[0],
        "sigmaII": ev[1],
        "sigmaIII": ev[2],
        "directions": V,
        "residual": max(res),
        "tauMax": tauMax,
        "sigmaOct": sigmaOct,
        "tauOct": tauOct,
        "deviator": Sdev,
        "J2": J2,
        "J3": J3,
        "charPolySym": charPolySym,
        "methodUsed": methodUsed,
        "report": rep,
        "latex": lat,
    }


def facet(sig, n, t=None) -> dict:
    """Vecteur contrainte Cn = σ·n sur une facette, avec ses composantes normale et tangentielle.

    Entrées : `sig` (tenseur 3x3 en Pa, 2x2 ou Voigt), `n` (normale, normalisée ; 2 ou 3 composantes),
    `t` (direction tangentielle optionnelle, normalisée et projetée sur la facette si nécessaire).
    Sortie : dict avec n (unitaire), Cn, sigmaN, normalVec, tauVec, tauNorm (Pa), tauDir, t (None si absent), tauT
    (NaN si t absent), tProjected, report, latex.
    """
    T = _tenseur(sig, "sig")
    n = _vecteur3(n, "n")
    nn = np.linalg.norm(n)
    if nn == 0:
        raise _erreur("zeroVector", "La normale n de la facette ne doit pas être nulle.")
    n = n / nn
    sc = _echelle(T)
    Cn = T @ n
    sigmaN = float(Cn @ n)
    tauVec = Cn - sigmaN * n
    tauNorm = float(np.linalg.norm(tauVec))
    tauDir = tauVec / tauNorm if tauNorm > 1e-12 * sc else np.zeros(3)

    tOut = None
    tauT = math.nan
    projected = False
    if t is not None:
        t = _vecteur3(t, "t")
        nt = np.linalg.norm(t)
        if nt == 0:
            raise _erreur("zeroVector", "La direction tangentielle t ne doit pas être nulle.")
        t = t / nt
        proj = float(t @ n)
        if abs(proj) > 1e-9:
            t = t - proj * n
            nt = np.linalg.norm(t)
            if nt < 1e-9:
                raise _erreur("badInput", "La direction t est colinéaire à n : direction tangentielle indéfinie.")
            t = t / nt
            projected = True
        tOut = t
        tauT = float(Cn @ t)

    nc = _clean(n, 1.0)
    Cnc = _mpa(Cn, sc)
    snc = _mpa(sigmaN, sc)
    tvc = _mpa(tauVec, sc)
    tnc = _mpa(tauNorm, sc)

    rep = [
        "Vecteur contrainte sur la facette de normale n (contraintes en MPa) :",
        f"   n (normalisée) = {_vecTxt(nc, 5)}",
        f"   Cn = σ·n = {_vecTxt(Cnc, 6)} MPa",
        f"   Contrainte normale σn = Cn·n = {_fmt(snc)} MPa ({'traction' if sigmaN >= 0 else 'compression'})",
        f"   Vecteur cisaillement τ = Cn − σn·n = {_vecTxt(tvc, 6)} MPa",
        f"   Cisaillement ||τ|| = √(||Cn||² − σn²) = {_fmt(tnc)} MPa",
    ]
    if tOut is not None:
        if projected:
            rep.append("   t non orthogonale à n : projetée sur le plan de la facette puis normalisée.")
        rep.append(f"   t = {_vecTxt(_clean(tOut, 1.0), 5)} ; τt = Cn·t = {_fmt(_mpa(tauT, sc))} MPa")

    lat = [
        r"$\vec{n} = " + _vecTex(nc, 4) + "$",
        r"$\vec{C}_n = \sigma \cdot \vec{n} = " + _vecTex(Cnc, 5) + r"\ \mathrm{MPa}$",
        r"$\sigma_n = \vec{C}_n \cdot \vec{n} = " + _tex(snc) + r"\ \mathrm{MPa}$",
        r"$\vec{\tau} = \vec{C}_n - \sigma_n\,\vec{n} = " + _vecTex(tvc, 5) + r"\ \mathrm{MPa}$",
        r"$\left|\vec{\tau}\right| = \sqrt{\left|\vec{C}_n\right|^2 - \sigma_n^2} = " + _tex(tnc) + r"\ \mathrm{MPa}$",
    ]
    if tOut is not None:
        lat.append(r"$\tau_t = \vec{C}_n \cdot \vec{t} = " + _tex(_mpa(tauT, sc)) + r"\ \mathrm{MPa}$")

    return {
        "n": n,
        "Cn": Cn,
        "sigmaN": sigmaN,
        "normalVec": sigmaN * n,
        "tauVec": tauVec,
        "tauNorm": tauNorm,
        "tauDir": tauDir,
        "t": tOut,
        "tauT": tauT,
        "tProjected": projected,
        "report": rep,
        "latex": lat,
    }


def plane2D(sxx, syy, sxy, theta=0.0) -> dict:
    """État de contraintes plan : contraintes sur une ou plusieurs facettes θ, cercle de Mohr, directions principales.

    Entrées : sxx, syy, sxy (Pa, scalaires) ; theta (rad, scalaire ou tableau, défaut 0) : angle de la normale
    n = (cos θ, sin θ) depuis x. Sortie : dict avec sigma, tau (Pa, même forme que theta), delta, rho, sigma1,
    sigma2, thetaP, thetaTauMax (rad), tauMax2D, pointA, pointB, circle (N×2 fermé), principal3D, tauMax3D, kind,
    report, latex.
    """
    sxx = _scalaire(sxx, "sxx")
    syy = _scalaire(syy, "syy")
    sxy = _scalaire(sxy, "sxy")
    theta = _tableau(0.0 if theta is None else theta, "theta")

    r = _mohrCore(sxx, syy, sxy, theta)
    r["kind"] = "stress"
    r["sxx"] = sxx
    r["syy"] = syy
    r["sxy"] = sxy
    p3 = np.sort([r["sigma1"], r["sigma2"], 0.0])[::-1]
    r["principal3D"] = p3
    r["tauMax3D"] = (p3[0] - p3[2]) / 2

    sc = _echelle(sxx, syy, sxy)
    deg = 180 / math.pi
    rep = [
        f"État plan de contraintes : σxx = {_fmt(_mpa(sxx, sc))} MPa ; σyy = {_fmt(_mpa(syy, sc))} MPa ; "
        f"σxy = {_fmt(_mpa(sxy, sc))} MPa",
        "Convention : n = (cos θ, sin θ), t = (−sin θ, cos θ) = z ∧ n, σ = Cn·n, τ = Cn·t "
        "(θ > 0 sens trigonométrique).",
        "   σ(θ) = (σxx+σyy)/2 + (σxx−σyy)/2·cos 2θ + σxy·sin 2θ",
        "   τ(θ) = −(σxx−σyy)/2·sin 2θ + σxy·cos 2θ",
    ]
    if np.ndim(theta) == 0:
        rep.append(
            f"Facette θ = {_fmt(float(theta) * deg)}° : σ = {_fmt(_mpa(r['sigma'], sc))} MPa ; "
            f"τ = {_fmt(_mpa(r['tau'], sc))} MPa"
        )
    else:
        rep.append(
            f"Facettes : {theta.size} valeurs de θ entre {_fmt(theta.min() * deg)}° et {_fmt(theta.max() * deg)}° "
            "(champs sigma et tau)."
        )
    rep += [
        f"Cercle de Mohr : centre δ = (σxx+σyy)/2 = {_fmt(_mpa(r['delta'], sc))} MPa ; "
        f"rayon ρ = √(((σxx−σyy)/2)² + σxy²) = {_fmt(_mpa(r['rho'], sc))} MPa",
        f"   A(σxx, σxy) = ({_fmt(_mpa(sxx, sc))} ; {_fmt(_mpa(sxy, sc))}) MPa ; "
        f"B(σyy, −σxy) = ({_fmt(_mpa(syy, sc))} ; {_fmt(_mpa(-sxy, sc))}) MPa",
        f"Contraintes principales planes : σ1 = δ + ρ = {_fmt(_mpa(r['sigma1'], sc))} MPa ; "
        f"σ2 = δ − ρ = {_fmt(_mpa(r['sigma2'], sc))} MPa",
        f"Direction principale : θP = ½·atan2(2σxy, σxx − σyy) = {_fmt(r['thetaP'] * deg)}° (σ1), θP + 90° (σ2)",
        f"Cisaillement maximal dans le plan : τmax = ρ = {_fmt(_mpa(r['rho'], sc))} MPa "
        f"(facette θ = θP − 45° = {_fmt(r['thetaTauMax'] * deg)}°)",
        f"Avec σzz = 0 : contraintes principales 3D = {_vecTxt(_mpa(p3, sc), 6)} MPa ; "
        f"τmax 3D = {_fmt(_mpa(r['tauMax3D'], sc))} MPa",
        "Sur le cercle de Mohr, le point de la facette θ se déduit de A par une rotation de 2θ (sens horaire).",
    ]

    lat = [
        r"$\sigma(\theta) = \frac{\sigma_{xx}+\sigma_{yy}}{2} + \frac{\sigma_{xx}-\sigma_{yy}}{2}\cos 2\theta "
        r"+ \sigma_{xy}\sin 2\theta$",
        r"$\tau(\theta) = -\frac{\sigma_{xx}-\sigma_{yy}}{2}\sin 2\theta + \sigma_{xy}\cos 2\theta$",
    ]
    if np.ndim(theta) == 0:
        lat.append(
            r"$\theta = "
            + _tex(float(theta) * deg)
            + r"^\circ :\ \ \sigma = "
            + _tex(_mpa(r["sigma"], sc))
            + r"\ \mathrm{MPa},\ \ \tau = "
            + _tex(_mpa(r["tau"], sc))
            + r"\ \mathrm{MPa}$"
        )
    lat += [
        r"$\delta = \frac{\sigma_{xx}+\sigma_{yy}}{2} = " + _tex(_mpa(r["delta"], sc)) + r"\ \mathrm{MPa}$",
        r"$\rho = \sqrt{\left(\frac{\sigma_{xx}-\sigma_{yy}}{2}\right)^2 + \sigma_{xy}^2} = "
        + _tex(_mpa(r["rho"], sc))
        + r"\ \mathrm{MPa}$",
        r"$\sigma_1 = \delta + \rho = "
        + _tex(_mpa(r["sigma1"], sc))
        + r"\ \mathrm{MPa},\ \ \sigma_2 = \delta - \rho = "
        + _tex(_mpa(r["sigma2"], sc))
        + r"\ \mathrm{MPa}$",
        r"$\theta_P = \frac{1}{2}\mathrm{atan2}(2\sigma_{xy},\ \sigma_{xx}-\sigma_{yy}) = "
        + _tex(r["thetaP"] * deg)
        + r"^\circ$",
        r"$\tau_{max} = \rho = " + _tex(_mpa(r["rho"], sc)) + r"\ \mathrm{MPa}$",
        r"$A(\sigma_{xx},\ \sigma_{xy}) = ("
        + _tex(_mpa(sxx, sc))
        + r",\ "
        + _tex(_mpa(sxy, sc))
        + r"),\ \ B(\sigma_{yy},\ -\sigma_{xy}) = ("
        + _tex(_mpa(syy, sc))
        + r",\ "
        + _tex(_mpa(-sxy, sc))
        + r")\ \mathrm{MPa}$",
    ]
    r["report"] = rep
    r["latex"] = lat
    return r


def plane2DStrain(exx, eyy, exy, theta=0.0) -> dict:
    """État plan de déformations : ε(θ), γ(θ)/2 et cercle de Mohr des déformations.

    Entrées : exx, eyy (sans dimension), exy = γxy/2 (composante tensorielle), theta (rad, scalaire ou tableau,
    défaut 0). Sortie : dict des mêmes champs que plane2D (sigma et tau désignent ε et γ/2), plus eps, gammaHalf,
    gamma = γ(θ) (sans dimension), eps1, eps2, gxy = γxy, gammaMax2D, kind = 'strain', report, latex.
    """
    exx = _scalaire(exx, "exx")
    eyy = _scalaire(eyy, "eyy")
    exy = _scalaire(exy, "exy")
    theta = _tableau(0.0 if theta is None else theta, "theta")

    r = _mohrCore(exx, eyy, exy, theta)
    r["kind"] = "strain"
    r["exx"] = exx
    r["eyy"] = eyy
    r["exy"] = exy
    r["gxy"] = 2 * exy
    r["eps"] = r["sigma"]
    r["gammaHalf"] = r["tau"]
    r["gamma"] = 2 * r["tau"]
    r["eps1"] = r["sigma1"]
    r["eps2"] = r["sigma2"]
    r["gammaMax2D"] = 2 * r["rho"]

    sc = _echelle(exx, eyy, exy)
    deg = 180 / math.pi
    rep = [
        f"État plan de déformations : εxx = {_fmt(_umdef(exx, sc))} µdéf ; εyy = {_fmt(_umdef(eyy, sc))} µdéf ; "
        f"εxy = γxy/2 = {_fmt(_umdef(exy, sc))} µdéf (γxy = {_fmt(_umdef(2 * exy, sc))} µdéf)",
        "   ε(θ) = (εxx+εyy)/2 + (εxx−εyy)/2·cos 2θ + εxy·sin 2θ ; γ(θ)/2 = −(εxx−εyy)/2·sin 2θ + εxy·cos 2θ",
    ]
    if np.ndim(theta) == 0:
        rep.append(
            f"Direction θ = {_fmt(float(theta) * deg)}° : ε = {_fmt(_umdef(r['eps'], sc))} µdéf ; "
            f"γ/2 = {_fmt(_umdef(r['gammaHalf'], sc))} µdéf"
        )
    else:
        rep.append(f"Directions : {theta.size} valeurs de θ (champs eps et gammaHalf).")
    rep += [
        f"Cercle de Mohr des déformations : centre = {_fmt(_umdef(r['delta'], sc))} µdéf ; "
        f"rayon = {_fmt(_umdef(r['rho'], sc))} µdéf",
        f"Déformations principales : ε1 = {_fmt(_umdef(r['eps1'], sc))} µdéf ; "
        f"ε2 = {_fmt(_umdef(r['eps2'], sc))} µdéf ; θP = {_fmt(r['thetaP'] * deg)}°",
        f"Glissement maximal dans le plan : γmax = ε1 − ε2 = {_fmt(_umdef(r['gammaMax2D'], sc))} µdéf",
    ]

    lat = [
        r"$\varepsilon(\theta) = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} + \frac{\varepsilon_{xx}-\varepsilon_{yy}}"
        r"{2}\cos 2\theta + \varepsilon_{xy}\sin 2\theta$",
        r"$\frac{\gamma(\theta)}{2} = -\frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\sin 2\theta + \varepsilon_{xy}\cos "
        r"2\theta$",
    ]
    if np.ndim(theta) == 0:
        lat.append(
            r"$\theta = "
            + _tex(float(theta) * deg)
            + r"^\circ :\ \ \varepsilon = "
            + _tex(_umdef(r["eps"], sc))
            + r"\ \mu\mathrm{def},\ \ \frac{\gamma}{2} = "
            + _tex(_umdef(r["gammaHalf"], sc))
            + r"\ \mu\mathrm{def}$"
        )
    lat += [
        r"$\varepsilon_{1,2} = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} \pm \sqrt{\left(\frac{\varepsilon_{xx}-"
        r"\varepsilon_{yy}}{2}\right)^2 + \varepsilon_{xy}^2} = "
        + _tex(_umdef(r["delta"], sc))
        + " \\pm "
        + _tex(_umdef(r["rho"], sc))
        + r"\ \mu\mathrm{def}$",
        r"$\varepsilon_1 = "
        + _tex(_umdef(r["eps1"], sc))
        + r"\ \mu\mathrm{def},\ \ \varepsilon_2 = "
        + _tex(_umdef(r["eps2"], sc))
        + r"\ \mu\mathrm{def}$",
        r"$\theta_P = \frac{1}{2}\mathrm{atan2}(2\varepsilon_{xy},\ \varepsilon_{xx}-\varepsilon_{yy}) = "
        + _tex(r["thetaP"] * deg)
        + r"^\circ$",
        r"$\gamma_{max} = \varepsilon_1 - \varepsilon_2 = " + _tex(_umdef(r["gammaMax2D"], sc)) + r"\ \mu\mathrm{def}$",
    ]
    r["report"] = rep
    r["latex"] = lat
    return r


def _umdef(x, ref: float):
    """Déformation adimensionnelle ramenée en µdéf pour l'affichage, résidus annulés."""
    return _clean(x, ref) * 1e6


def mohr3D(pr, nPts: int | None = None) -> dict:
    """Tricercle de Mohr à partir des contraintes principales.

    Entrées : `pr` ([σI σII σIII] en Pa, [σ1 σ2] en état plan, ou tenseur 3x3 / 2x2 dont les valeurs propres sont
    prises), `nPts` (points par cercle, défaut 361).
    Sortie : dict avec pr (Pa, décroissant), pairs (indices 1-based des contraintes délimitant chaque cercle),
    centers et radii (Pa, 3 valeurs : (σI,σII), (σII,σIII), (σI,σIII)), circles (liste de N×2 [σ τ]), tauMax, sigmaMin,
    sigmaMax, report, latex.
    """
    p = _principalTriplet(pr)
    nPts = 361 if nPts is None else max(5, round(_scalaire(nPts, "nPts")))
    centers = np.array([(p[0] + p[1]) / 2, (p[1] + p[2]) / 2, (p[0] + p[2]) / 2])
    radii = np.array([(p[0] - p[1]) / 2, (p[1] - p[2]) / 2, (p[0] - p[2]) / 2])
    phi = np.linspace(0, 2 * np.pi, nPts)
    circles = [np.column_stack([c + r * np.cos(phi), r * np.sin(phi)]) for c, r in zip(centers, radii, strict=True)]

    sc = _echelle(p)
    rep = [
        f"Tricercle de Mohr : σI = {_fmt(_mpa(p[0], sc))} MPa ≥ σII = {_fmt(_mpa(p[1], sc))} MPa ≥ "
        f"σIII = {_fmt(_mpa(p[2], sc))} MPa",
        f"   cercle (σI, σII)   : centre = {_fmt(_mpa(centers[0], sc))} MPa ; rayon = {_fmt(_mpa(radii[0], sc))} MPa",
        f"   cercle (σII, σIII) : centre = {_fmt(_mpa(centers[1], sc))} MPa ; rayon = {_fmt(_mpa(radii[1], sc))} MPa",
        f"   cercle (σI, σIII)  : centre = {_fmt(_mpa(centers[2], sc))} MPa ; rayon = {_fmt(_mpa(radii[2], sc))} MPa "
        "= τmax",
        "Les points (σn, τ) de toutes les facettes sont dans le grand cercle et hors des deux petits.",
    ]
    lat = [
        r"$C_{I,II} = \frac{\sigma_I+\sigma_{II}}{2} = " + _tex(_mpa(centers[0], sc)) + r",\ \ R_{I,II} = "
        r"\frac{\sigma_I-\sigma_{II}}{2} = " + _tex(_mpa(radii[0], sc)) + r"\ \mathrm{MPa}$",
        r"$C_{II,III} = \frac{\sigma_{II}+\sigma_{III}}{2} = " + _tex(_mpa(centers[1], sc)) + r",\ \ R_{II,III} = "
        r"\frac{\sigma_{II}-\sigma_{III}}{2} = " + _tex(_mpa(radii[1], sc)) + r"\ \mathrm{MPa}$",
        r"$C_{I,III} = \frac{\sigma_I+\sigma_{III}}{2} = " + _tex(_mpa(centers[2], sc)) + r",\ \ R_{I,III} = "
        r"\frac{\sigma_I-\sigma_{III}}{2} = " + _tex(_mpa(radii[2], sc)) + r"\ \mathrm{MPa}$",
        r"$\tau_{max} = R_{I,III} = " + _tex(_mpa(radii[2], sc)) + r"\ \mathrm{MPa}$",
    ]
    return {
        "pr": p,
        "pairs": [[1, 2], [2, 3], [1, 3]],
        "centers": centers,
        "radii": radii,
        "circles": circles,
        "tauMax": radii[2],
        "sigmaMin": p[2],
        "sigmaMax": p[0],
        "report": rep,
        "latex": lat,
    }


def criteria(pr, Re, s=1.0, sigmaR=None) -> dict:
    """Critères de Tresca, de Von Mises et de la contrainte normale maximale (Rankine).

    Entrées : `pr` (contraintes principales en Pa, [σ1 σ2] ou tenseur), `Re` (limite élastique en Pa, > 0),
    `s` (coefficient de sécurité, défaut 1), `sigmaR` (contrainte de rupture en Pa, défaut Re).
    Sortie : dict avec sigmaEqTresca, sigmaEqVM, sigmaMaxNormal, tauMax (Pa), sigmaAdm et sigmaRAdm (Pa),
    okTresca, okVM, okRankine (bool), sfTresca, sfVM, sfRankine (coefficients de sécurité obtenus), report, latex.
    """
    p = _principalTriplet(pr)
    Re = _positif(Re, "Re")
    s = 1.0 if s is None else _positif(s, "s")
    if sigmaR is None or (is_num(sigmaR) and math.isnan(sigmaR)):
        sigmaR = Re
    sigmaR = _positif(sigmaR, "sigmaR")

    eqTresca = p[0] - p[2]
    eqVM = math.sqrt(((p[0] - p[1]) ** 2 + (p[1] - p[2]) ** 2 + (p[2] - p[0]) ** 2) / 2)
    maxN = float(np.max(np.abs(p)))
    tauMax = (p[0] - p[2]) / 2
    sigAdm = Re / s
    sigRAdm = sigmaR / s
    tol = 1e-12
    okT = bool(eqTresca <= sigAdm * (1 + tol))
    okVM = bool(eqVM <= sigAdm * (1 + tol))
    okR = bool(maxN <= sigRAdm * (1 + tol))
    sfT = _rapport(Re, eqTresca)
    sfVM = _rapport(Re, eqVM)
    sfR = _rapport(sigmaR, maxN)

    sc = _echelle(p, Re)
    V = {True: "vérifié", False: "NON vérifié"}
    K = {True: r"\le", False: ">"}
    rep = [
        f"Contraintes principales : σI = {_fmt(_mpa(p[0], sc))} MPa ; σII = {_fmt(_mpa(p[1], sc))} MPa ; "
        f"σIII = {_fmt(_mpa(p[2], sc))} MPa",
        f"Contrainte admissible : σadm = Re/s = {_fmt(Re / 1e6)} / {_fmt(s)} = {_fmt(sigAdm / 1e6)} MPa",
        f"Tresca : σeq = σI − σIII = {_fmt(_mpa(eqTresca, sc))} MPa (τmax = {_fmt(_mpa(tauMax, sc))} MPa) → "
        f"critère {V[okT]} ; coefficient obtenu Re/σeq = {_fmt(sfT)}",
        f"Von Mises : σeq = (1/√2)·√((σI−σII)² + (σII−σIII)² + (σIII−σI)²) = {_fmt(_mpa(eqVM, sc))} MPa → "
        f"critère {V[okVM]} ; coefficient obtenu = {_fmt(sfVM)}",
        f"Contrainte normale maximale (matériaux fragiles) : max|σi| = {_fmt(_mpa(maxN, sc))} MPa ≤ "
        f"σR/s = {_fmt(sigRAdm / 1e6)} MPa ? → {V[okR]} ; coefficient obtenu = {_fmt(sfR)}",
    ]
    if eqVM > 0:
        rep.append(f"Rapport σeq Tresca / σeq Von Mises = {_fmt(eqTresca / eqVM)} (compris entre 1 et 2/√3 ≈ 1,1547)")

    lat = [
        r"$\sigma_{adm} = \frac{R_e}{s} = \frac{"
        + _tex(Re / 1e6)
        + "}{"
        + _tex(s)
        + "} = "
        + _tex(sigAdm / 1e6)
        + r"\ \mathrm{MPa}$",
        r"$\sigma_{eq}^{\mathrm{Tresca}} = \sigma_I - \sigma_{III} = "
        + _tex(_mpa(eqTresca, sc))
        + r"\ \mathrm{MPa}\ "
        + K[okT]
        + r"\ \sigma_{adm}$",
        r"$\sigma_{eq}^{\mathrm{VM}} = \frac{1}{\sqrt{2}}\sqrt{(\sigma_I-\sigma_{II})^2 + "
        r"(\sigma_{II}-\sigma_{III})^2 + (\sigma_{III}-\sigma_I)^2} = "
        + _tex(_mpa(eqVM, sc))
        + r"\ \mathrm{MPa}\ "
        + K[okVM]
        + r"\ \sigma_{adm}$",
        r"$\mathrm{max}\left|\sigma_i\right| = "
        + _tex(_mpa(maxN, sc))
        + r"\ \mathrm{MPa}\ "
        + K[okR]
        + r"\ \frac{\sigma_R}{s} = "
        + _tex(sigRAdm / 1e6)
        + r"\ \mathrm{MPa}$",
        r"$s_{\mathrm{Tresca}} = \frac{R_e}{\sigma_{eq}^{\mathrm{Tresca}}} = "
        + _tex(sfT)
        + r",\ \ s_{\mathrm{VM}} = \frac{R_e}{\sigma_{eq}^{\mathrm{VM}}} = "
        + _tex(sfVM)
        + "$",
    ]
    return {
        "pr": p,
        "Re": Re,
        "s": s,
        "sigmaR": sigmaR,
        "sigmaEqTresca": eqTresca,
        "sigmaEqVM": eqVM,
        "sigmaMaxNormal": maxN,
        "tauMax": tauMax,
        "sigmaAdm": sigAdm,
        "sigmaRAdm": sigRAdm,
        "okTresca": okT,
        "okVM": okVM,
        "okRankine": okR,
        "sfTresca": sfT,
        "sfVM": sfVM,
        "sfRankine": sfR,
        "report": rep,
        "latex": lat,
    }


def yieldLoci(Re, s=1.0, sigmaR=None, nPts: int | None = None) -> dict:
    """Lieux de plasticité en contraintes planes (σ1, σ2) : Tresca, Von Mises et Rankine.

    Entrées : Re (Pa, > 0), s (défaut 1), sigmaR (Pa, défaut Re), nPts (points de l'ellipse, défaut 361).
    Sortie : dict avec tresca (hexagone fermé, 7×2), vonMises (ellipse fermée, N×2), rankine (carré fermé, 5×2),
    toutes en Pa et de colonnes [σ1 σ2], puis sigmaAdm et sigmaRAdm (Pa), report, latex.
    """
    Re = _positif(Re, "Re")
    s = 1.0 if s is None else _positif(s, "s")
    if sigmaR is None or (is_num(sigmaR) and math.isnan(sigmaR)):
        sigmaR = Re
    sigmaR = _positif(sigmaR, "sigmaR")
    nPts = 361 if nPts is None else max(9, round(_scalaire(nPts, "nPts")))

    a = Re / s
    b = sigmaR / s
    phi = np.linspace(0, 2 * np.pi, nPts)
    vonMises = a * np.column_stack([np.cos(phi) + np.sin(phi) / np.sqrt(3), np.cos(phi) - np.sin(phi) / np.sqrt(3)])
    vonMises[-1] = vonMises[0]

    rep = [
        f"Lieux de plasticité en contraintes planes (σ3 = 0) ; σadm = Re/s = {_fmt(a / 1e6)} MPa :",
        "   Tresca : max(|σ1|, |σ2|, |σ1 − σ2|) = σadm → hexagone de sommets (±σadm, 0), (0, ±σadm), ±(σadm, σadm)",
        f"   Von Mises : σ1² − σ1·σ2 + σ2² = σadm² → ellipse de demi-axes √2·σadm = {_fmt(math.sqrt(2) * a / 1e6)} MPa "
        f"(bissectrice σ1 = σ2) et √(2/3)·σadm = {_fmt(math.sqrt(2 / 3) * a / 1e6)} MPa (σ1 = −σ2)",
        f"   Contrainte normale maximale : max(|σ1|, |σ2|) = σR/s = {_fmt(b / 1e6)} MPa → carré",
        "L'hexagone de Tresca est inscrit dans l'ellipse de Von Mises (Tresca plus sécuritaire).",
    ]
    lat = [
        r"$\mathrm{max}(|\sigma_1|,\ |\sigma_2|,\ |\sigma_1-\sigma_2|) = \sigma_{adm} = \frac{R_e}{s} = "
        + _tex(a / 1e6)
        + r"\ \mathrm{MPa}$",
        r"$\sigma_1^2 - \sigma_1\sigma_2 + \sigma_2^2 = \sigma_{adm}^2 = "
        + _tex((a / 1e6) ** 2)
        + r"\ \mathrm{MPa}^2$",
        r"$\mathrm{max}(|\sigma_1|,\ |\sigma_2|) = \frac{\sigma_R}{s} = " + _tex(b / 1e6) + r"\ \mathrm{MPa}$",
    ]
    return {
        "tresca": a * np.array([[1, 0], [1, 1], [0, 1], [-1, 0], [-1, -1], [0, -1], [1, 0]], dtype=float),
        "vonMises": vonMises,
        "rankine": b * np.array([[1, 1], [-1, 1], [-1, -1], [1, -1], [1, 1]], dtype=float),
        "sigmaAdm": a,
        "sigmaRAdm": b,
        "report": rep,
        "latex": lat,
    }
