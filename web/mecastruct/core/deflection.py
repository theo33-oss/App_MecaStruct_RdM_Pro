"""Déformée des poutres, énergie de déformation et intégrales de Mohr : port de SolicitationsEngine.m (étape E13).

deflection : flèche par 4 méthodes (intégration, aires, Castigliano, Mohr) ; strainEnergy : énergie exacte sur les pp ;
mohrIntegral : intégrale de Mohr par la table des formes élémentaires (hors table : Gauss). Unités SI strictes ;
chaque résultat contient `report` et `latex`.
"""

import copy
import math
import re

import numpy as np
import pandas as pd

from mecastruct.core import beam_solver
from mecastruct.core.errors import MecaStructError
from mecastruct.core.kt_mohr import mohrTable
from mecastruct.core.pp import (
    PP,
    _mergeBreaks,
    _polyAdd,
    _shiftPoly,
    asPP,
    poly2latex,
    ppAdd,
    ppConst,
    ppDerivative,
    ppEval,
    ppIntegral,
    ppMultiply,
    ppRefine,
    ppScale,
)
from mecastruct.core.solicitations import _seF, _seT
from mecastruct.core.utils import is_num

_ID = "MecaStruct:SolicitationsEngine:"
_OPTS_RAPIDES = {"internalMethod": "coupures", "hyperMethod": "menabrea", "useSymbolic": False}
_METHODES = ("integration", "aires", "castigliano", "mohr")
_PROPS_ENERGIE = ("E", "G", "S", "Iz", "Iy", "Ix", "ky", "kz", "Iyz")


# ----------------------------------------------------------------- options et utilitaires


def _deflOpts(opts: dict | None) -> dict:
    """Options de deflection complétées par leurs valeurs par défaut (seDeflOpts).

    Entrée : `opts` (dict ou None). Sortie : dict plane, nPoints, nCastigliano, includeShear, methods, s0.
    Erreur : MecaStruct:SolicitationsEngine:invalidInput si plane ou une méthode est inconnue.
    """
    o = {
        "plane": "xy",
        "nPoints": 201,
        "nCastigliano": 41,
        "includeShear": True,
        "methods": list(_METHODES),
        "s0": None,
    }
    if not opts:
        return o
    if not isinstance(opts, dict):
        raise MecaStructError(_ID + "invalidInput", "opts doit être une structure scalaire.")
    for f in o:
        if opts.get(f) is not None and np.size(opts[f]) > 0:
            o[f] = opts[f]
    o["plane"] = str(o["plane"]).lower()
    if o["plane"] not in ("xy", "xz"):
        raise MecaStructError(_ID + "invalidInput", "opts.plane doit valoir 'xy' ou 'xz'.")
    o["methods"] = [o["methods"]] if isinstance(o["methods"], str) else list(o["methods"])
    bad = sorted(set(o["methods"]) - set(_METHODES))
    if bad:
        raise MecaStructError(_ID + "invalidInput", f"Méthode de déformée inconnue : {bad[0]}.")
    o["nPoints"] = max(2, int(o["nPoints"] + 0.5))
    o["nCastigliano"] = max(2, int(o["nCastigliano"] + 0.5))
    o["includeShear"] = bool(o["includeShear"])
    return o


def _seg(br: np.ndarray, s: float) -> int:
    """Indice (0 à n-1) du tronçon contenant s ; le premier tronçon pour s < breaks[0] (seSeg)."""
    k = int(np.count_nonzero(br[:-1] <= s)) - 1
    return min(max(k, 0), len(br) - 2)


def _seTp(v: float) -> str:
    """Nombre LaTeX entre parenthèses s'il est négatif."""
    s = _seT(v)
    return rf"\left({s}\right)" if v < 0 else s


def _intProd(a: PP, b: PP) -> float:
    """∫₀ᴸ a·b ds, exacte sur les polynômes par morceaux (seIntProd)."""
    return ppIntegral(ppMultiply(a, b))


def _iyz(m: dict) -> float:
    """Produit d'inertie du modèle, 0 s'il est absent ou non fini (seIyz)."""
    v = m.get("Iyz")
    return float(v) if is_num(v) and math.isfinite(v) else 0.0


def _bendMoments(sol: dict, m: dict) -> tuple[PP, PP]:
    """Moments équivalents (Mz, My) de la flexion déviée : E·Iz·v'' = Mz, E·Iy·w'' = −My (seBendMoments)."""
    iyz = _iyz(m)
    if iyz == 0:
        return sol["Mfz"], sol["Mfy"]
    dt = m["Iz"] * m["Iy"] - iyz**2
    if dt <= 0:
        raise MecaStructError(_ID + "invalidInput", "Il faut Iyz² < Iz·Iy.")

    def lin(a, b):
        return ppAdd(ppScale(sol["Mfz"], a), ppScale(sol["Mfy"], b))

    return lin(m["Iz"] * m["Iy"] / dt, m["Iz"] * iyz / dt), lin(m["Iy"] * iyz / dt, m["Iy"] * m["Iz"] / dt)


def _imposed(sol: dict, m: dict, plane: str) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    """Conditions cinématiques, déplacements d'appui, courbure thermique du plan et abscisses des rotules (seImposed).

    Sorties : conds (n × 3 : pos, type 0 = déplacement imposé / 1 = rotation nulle, valeur), dSup (m), kap (1/m),
    hingePos (m). Un appui à ressort se déplace de tassement − R/k.
    """
    rf, df, kap = ("Ry", "dy", m["thermal"]["kv"]) if plane == "xy" else ("Rz", "dz", m["thermal"]["kw"])
    conds = []
    dSup = np.zeros(len(m["supports"]))
    for i, s in enumerate(m["supports"]):
        d = s[df]
        if s["spring"] > 0:
            d = d - sol["reactions"][i][rf] / s["spring"]
        dSup[i] = d
        conds.append([s["pos"], 0, d])
        if s["type"] == "encastrement":
            conds.append([s["pos"], 1, 0.0])
    hingePos = np.array([h["pos"] for h in m["hinges"]], dtype=float)
    return np.array(conds, dtype=float).reshape(-1, 3), dSup, kap, hingePos


def _unitSolve(m: dict, s0: float, kind: str, plane: str) -> tuple[PP, PP, np.ndarray]:
    """Diagrammes m̄ et t̄ sous charge unité (force ou couple) en s0, et réactions r̄ des appuis (seUnitSolve).

    L'état virtuel n'a ni tassement, ni dilatation, ni charge réelle.
    """
    mu = copy.deepcopy(m)
    mu["thermal"] = {"epsX": 0.0, "kv": 0.0, "kw": 0.0}
    for s in mu["supports"]:
        s["dx"] = s["dy"] = s["dz"] = 0.0
    mu["distLoads"], mu["pointLoads"], mu["pointMoments"] = [], [], []
    xy = plane == "xy"
    if kind == "force":
        mu["pointLoads"] = [{"pos": s0, "Fx": 0.0, "Fy": float(xy), "Fz": float(not xy), "name": "F1"}]
    else:
        # couple conjugué de dv/ds (xy : Mz = +1) ou de dw/ds (xz : My = −1) ; à une rotule, la section à droite
        if any(abs(h["pos"] - s0) <= 1e-9 * mu["L"] for h in mu["hinges"]):
            s0 = s0 + 2e-9 * mu["L"]
        mu["pointMoments"] = [{"pos": s0, "Mx": 0.0, "My": -float(not xy), "Mz": float(xy), "name": "C1"}]
    su = beam_solver.solveBeam(mu, _OPTS_RAPIDES)
    if xy:
        return su["Mfz"], su["Ty"], np.array([r["Ry"] for r in su["reactions"]])
    return ppScale(su["Mfy"], -1), su["Tz"], np.array([r["Rz"] for r in su["reactions"]])


def _defaultS0(sup: list[dict], L: float, sMax: float) -> np.ndarray:
    """Points d'intérêt par défaut : flèche max, milieux des travées, extrémités libres (seDefaultS0)."""
    ps = np.unique([s["pos"] for s in sup])
    s0 = [sMax] + list((ps[:-1] + ps[1:]) / 2)
    tol = 1e-9 * L
    if len(ps) == 0 or ps[0] > tol:
        s0.append(0.0)
    if len(ps) == 0 or ps[-1] < L - tol:
        s0.append(L)
    return _mergeBreaks(s0)


# ----------------------------------------------------------------- méthodes de la déformée


def _integration(M: PP, EI: float, conds: np.ndarray, hingePos: np.ndarray) -> dict:
    """Double intégration tronçon par tronçon : E·I·v_k = P_k(s) + C1k·s + C2k (2n constantes, moindres carrés).

    Raccords de v et v' (v' discontinue aux rotules) et conditions aux appuis ; résidu rapporté à max|M|·L².
    """
    br = M.breaks
    n = len(br) - 1
    P1 = [np.polyint(c) for c in M.coefs]
    P2 = [np.polyint(p) for p in P1]
    lignes, rhs = [], []
    for j in range(n - 1):
        sb = br[j + 1]
        ligne = np.zeros(2 * n)
        ligne[2 * j : 2 * j + 2] = [sb, 1]
        ligne[2 * j + 2 : 2 * j + 4] = [-sb, -1]
        lignes.append(ligne)
        rhs.append(np.polyval(P2[j + 1], sb) - np.polyval(P2[j], sb))
        if np.any(np.abs(hingePos - sb) <= 1e-9 * (br[-1] - br[0])):
            continue  # rotule : la pente est discontinue
        ligne = np.zeros(2 * n)
        ligne[2 * j], ligne[2 * j + 2] = 1, -1
        lignes.append(ligne)
        rhs.append(np.polyval(P1[j + 1], sb) - np.polyval(P1[j], sb))
    for sp, typ, val in conds:
        k = _seg(br, sp)
        ligne = np.zeros(2 * n)
        if typ == 0:
            ligne[2 * k : 2 * k + 2] = [sp, 1]
            rhs.append(EI * val - np.polyval(P2[k], sp))
        else:
            ligne[2 * k] = 1
            rhs.append(-np.polyval(P1[k], sp))
        lignes.append(ligne)
    A = np.array(lignes).reshape(-1, 2 * n)
    b = np.array(rhs, dtype=float)
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    Ls = br[-1] - br[0]
    echelle = np.max(np.abs(ppEval(M, np.linspace(br[0], br[-1], 201)))) * Ls**2
    residual = np.linalg.norm(A @ x - b) / max(echelle, np.finfo(float).tiny)
    cv, eq = [], []
    for k in range(n):
        pk = _polyAdd(P2[k], [x[2 * k], x[2 * k + 1]])
        cv.append(pk / EI)
        eq.append(f"$E\\,@I\\,@V_{{{k + 1}}}(s) = {poly2latex(pk)}, \\ {_seT(br[k])} \\le s \\le {_seT(br[k + 1])}$")
    vPP = PP(br, cv)
    constants = pd.DataFrame(
        {"Troncon": np.arange(1, n + 1), "s1": br[:-1], "s2": br[1:], "C1": x[0::2], "C2": x[1::2]}
    )
    return {
        "vPP": vPP,
        "alphaPP": ppDerivative(vPP),
        "constants": constants,
        "equations": eq,
        "residual": residual,
    }


def _ppMaxAbs(vPP: PP, aPP: PP) -> tuple[float, float]:
    """Maximum de |v| et abscisse : points de rupture et racines de v' dans chaque tronçon (sePPMaxAbs)."""
    br = vPP.breaks
    cand = list(br)
    for k in range(len(br) - 1):
        rt = np.roots(aPP.coefs[k])
        rt = rt[np.abs(rt.imag) < 1e-9 * np.maximum(1, np.abs(rt))].real
        cand += rt[(rt > br[k]) & (rt < br[k + 1])].tolist()
    cand = np.array(cand)
    v = np.maximum(np.abs(ppEval(vPP, cand, "left")), np.abs(ppEval(vPP, cand, "right")))
    i = int(np.argmax(v))
    return float(v[i]), float(cand[i])


def _airesConnu(s, br: np.ndarray, IA: list, IS: list, cumA: np.ndarray, cumS: np.ndarray):
    """Contribution des aires sans α0 ni v0, multipliée par EI : Fv = ∫₀ˢ (s − t)·M dt et Fa = ∫₀ˢ M dt.

    Sorties : (Fv, Fa), de la forme de s (seAiresKnown).
    """
    s = np.asarray(s, dtype=float)
    fv, fa = np.zeros(s.shape), np.zeros(s.shape)
    for idx, si in np.ndenumerate(s):
        k = _seg(br, si)
        a = cumA[k] + np.polyval(IA[k], si) - np.polyval(IA[k], br[k])
        m1 = cumS[k] + np.polyval(IS[k], si) - np.polyval(IS[k], br[k])
        fv[idx] = si * a - m1
        fa[idx] = a
    return fv, fa


def _aires(M: PP, EI: float, conds: np.ndarray, sEval: np.ndarray, hingePos: np.ndarray) -> dict:
    """Méthode des aires et des moments des aires (seAires).

    α(s) = α0 + (1/EI)·∫₀ˢ M ; v(s) = v0 + α0·s + (1/EI)·Σ Ak·(s − s̄k) : les constantes v0, α0 et les sauts aux
    rotules sont ajustés aux appuis par moindres carrés de norme minimale.
    """
    br = M.breaks
    n = len(br) - 1
    IA = [np.polyint(c) for c in M.coefs]
    IS = [np.polyint(np.convolve([1.0, 0.0], c)) for c in M.coefs]
    Ak, Sk = np.zeros(n), np.zeros(n)
    for k in range(n):
        Ak[k] = np.polyval(IA[k], br[k + 1]) - np.polyval(IA[k], br[k])
        Sk[k] = np.polyval(IS[k], br[k + 1]) - np.polyval(IS[k], br[k])
    cumA = np.concatenate([[0.0], np.cumsum(Ak)])
    cumS = np.concatenate([[0.0], np.cumsum(Sk)])

    def connu(s):
        return _airesConnu(s, br, IA, IS, cumA, cumS)

    nh = len(hingePos)  # sauts de rotation aux rotules : v += Δθ·(s − sh)+, α += Δθ·[s ≥ sh]
    Q = np.zeros((len(conds), 2 + nh))
    r = np.zeros(len(conds))
    for i, (sp, typ, val) in enumerate(conds):
        fv, fa = connu(sp)
        if typ == 0:
            Q[i] = np.concatenate([[1.0, sp], np.maximum(sp - hingePos, 0.0)])
            r[i] = val - fv / EI
        else:
            Q[i] = np.concatenate([[0.0, 1.0], (sp > hingePos + 1e-12).astype(float)])
            r[i] = -fa / EI
    x = np.linalg.lstsq(Q, r, rcond=None)[0]
    v0, alpha0, sauts = x[0], x[1], x[2:]
    fv, fa = connu(sEval)
    v = v0 + alpha0 * sEval + fv / EI
    alpha = alpha0 + fa / EI
    for h in range(nh):
        v = v + sauts[h] * np.maximum(sEval - hingePos[h], 0.0)
        alpha = alpha + sauts[h] * (sEval >= hingePos[h])
    with np.errstate(divide="ignore", invalid="ignore"):
        sBar = Sk / Ak
    sBar[np.abs(Ak) <= 1e-14 * np.max(np.abs(Ak))] = np.nan
    areas = pd.DataFrame({"Troncon": np.arange(1, n + 1), "s1": br[:-1], "s2": br[1:], "Aire": Ak, "sBar": sBar})
    # flèche maximale : extrémités et zéros de α(s) dans chaque tronçon
    cand = list(br)
    for k in range(n):
        saut = np.sum(sauts[hingePos <= br[k] + 1e-12])
        constante = EI * (alpha0 + saut) + cumA[k] - np.polyval(IA[k], br[k])
        rt = np.roots(_polyAdd(IA[k], [constante]))
        rt = rt[np.abs(rt.imag) < 1e-9 * np.maximum(1, np.abs(rt))].real
        cand += rt[(rt > br[k]) & (rt < br[k + 1])].tolist()
    cand = np.array(cand)
    fvc, _ = connu(cand)
    vc = v0 + alpha0 * cand + fvc / EI
    for h in range(nh):
        vc = vc + sauts[h] * np.maximum(cand - hingePos[h], 0.0)
    vc = np.abs(vc)
    i = int(np.argmax(vc))
    return {
        "v": v,
        "alpha": alpha,
        "areas": areas,
        "v0": v0,
        "alpha0": alpha0,
        "hingeJumps": sauts,
        "residual": np.linalg.norm(Q @ x - r),
        "fmax": float(vc[i]),
        "sAtFmax": float(cand[i]),
    }


# ----------------------------------------------------------------- intégrales de Mohr


def _decompose(c: np.ndarray, s1: float, s2: float) -> tuple[list[dict], bool, int]:
    """Décomposition d'un tronçon en forme linéaire (rectangle, triangle, triangle inversé, trapèze) et parabole.

    La parabole a une flèche f au milieu ; la décomposition existe si le degré est ≤ 2 (seDecompose).
    Sorties : (parties, ok, degré) ; chaque partie est {"shape", "vals"} avec vals un tableau.
    """
    lo = s2 - s1
    q = _shiftPoly(c, -s1)  # coefficients en ξ = s − s1
    pw = np.arange(len(q) - 1, -1, -1)
    mag = np.abs(q) * lo**pw
    sc = float(np.max(mag))
    deg = int(pw[mag > 1e-11 * sc].max()) if sc > 0 else 0
    parts: list[dict] = []
    ok = deg <= 2
    if not ok:
        return parts, ok, deg
    M1, M2 = np.polyval(c, s1), np.polyval(c, s2)
    f = np.polyval(c, (s1 + s2) / 2) - (M1 + M2) / 2
    tol = 1e-11 * max(sc, np.finfo(float).tiny)
    if abs(M1) > tol or abs(M2) > tol:  # sinon : pas de partie linéaire
        if abs(M1 - M2) <= tol:
            parts.append({"shape": "rectangle", "vals": np.array([(M1 + M2) / 2])})
        elif abs(M1) <= tol:
            parts.append({"shape": "triangle", "vals": np.array([M2])})
        elif abs(M2) <= tol:
            parts.append({"shape": "triangle_inverse", "vals": np.array([M1])})
        else:
            parts.append({"shape": "trapeze", "vals": np.array([M1, M2])})
    if abs(f) > tol:
        parts.append({"shape": "parabole", "vals": np.array([f])})
    return parts, ok, deg


def _shapeName(parts: list[dict], ok: bool) -> str:
    """Libellé de la décomposition d'un tronçon (seShapeName)."""
    if not ok:
        return "hors table"
    if not parts:
        return "nul"
    return " + ".join(p["shape"] for p in parts)


def _remplace(s: str, symbole: str, texte: str) -> str:
    """Remplace chaque symbole isolé (ni précédé ni suivi d'une lettre, d'un _ ou d'une barre) par texte."""
    return re.sub(rf"(?<![\\a-zA-Z_]){re.escape(symbole)}(?![a-zA-Z_])", lambda _: texte, s)


def _mohrTex(tex: str, lo: float, a: np.ndarray, b: np.ndarray) -> str:
    """Formule de la table avec les valeurs numériques substituées, sans les $ (seMohrTex)."""
    s = tex[tex.index("= ") + 2 : -1]
    for symbole, v, i in (("a_1", a, 0), ("a_2", a, 1), ("b_1", b, 0), ("b_2", b, 1), ("a", a, 0), ("b", b, 0)):
        if len(v) > i:
            s = _remplace(s, symbole, _seTp(v[i]))
    return _remplace(s, "l", _seTp(lo))


def mohrIntegral(ppA, ppB, a: float | None = None, b: float | None = None) -> dict:
    """Intégrale de Mohr ∫ₐᵇ MA·MB ds, exacte et par la table des formes élémentaires (mohrIntegral).

    Entrées : `ppA`, `ppB` (pp ou dict breaks/coefs) ; `a`, `b` (m, défaut : bornes de ppA). Chaque tronçon est
    décomposé en trapèze (rectangle, triangle, triangle inversé, trapèze) + parabole (degré ≤ 2), lu dans la table
    de mohrTable ; au-delà du degré 2, quadrature de Gauss.
    Sortie : dict value (exacte), valueTable (somme des tronçons), segments (DataFrame s1, s2, shapeA, shapeB,
    formulaLatex, value, tabulated), allTabulated, report, latex.
    Erreur : invalidInput si a ≥ b.
    """
    ppA, ppB = asPP(ppA), asPP(ppB)
    a = ppA.breaks[0] if a is None else a
    b = ppA.breaks[-1] if b is None else b
    if not b > a:
        raise MecaStructError(_ID + "invalidInput", "mohrIntegral : il faut a < b.")
    prod = ppMultiply(ppA, ppB)
    M = {"value": ppIntegral(prod, a, b)}
    tolB = 1e-12 * np.max(np.abs(np.concatenate([[a, b], prod.breaks])))
    br = np.unique(np.concatenate([[a], prod.breaks[(prod.breaks > a + tolB) & (prod.breaks < b - tolB)], [b]]))
    Ra, Rb = ppRefine(ppA, br), ppRefine(ppB, br)
    tab = {e["id"]: e for e in mohrTable()}
    n = len(br) - 1
    s1, s2 = br[:-1], br[1:]
    shA, shB, fl = [], [], []
    val = np.zeros(n)
    tb = np.zeros(n, dtype=bool)
    for k in range(n):
        mid = (s1[k] + s2[k]) / 2
        ca, cb = Ra.coefs[_seg(Ra.breaks, mid)], Rb.coefs[_seg(Rb.breaks, mid)]
        pa, okA, dA = _decompose(ca, s1[k], s2[k])
        pb, okB, dB = _decompose(cb, s1[k], s2[k])
        shA.append(_shapeName(pa, okA))
        shB.append(_shapeName(pb, okB))
        lo = s2[k] - s1[k]
        if okA and okB:
            tb[k] = True
            termes = []
            for xa in pa:
                for xb in pb:
                    e = tab[f"{xa['shape']}_x_{xb['shape']}"]
                    val[k] += e["fun"](lo, xa["vals"], xb["vals"])
                    termes.append(_mohrTex(e["latex"], lo, xa["vals"], xb["vals"]))
            fl.append(f"${' + '.join(termes)} = {_seT(val[k])}$" if termes else "$0$")
        else:
            ng = math.ceil((dA + dB + 1) / 2) + 1
            nodes, poids = np.polynomial.legendre.leggauss(ng)
            sg = mid + lo / 2 * nodes
            val[k] = lo / 2 * np.sum(poids * np.polyval(ca, sg) * np.polyval(cb, sg))
            fl.append(
                f"$\\int_{{{_seT(s1[k])}}}^{{{_seT(s2[k])}}} M_A\\,M_B\\,ds = "
                f"\\frac{{l}}{{2}}\\sum_{{i=1}}^{{{ng}}} w_i\\,M_A\\,M_B = {_seT(val[k])}$"
            )
    M["valueTable"] = float(np.sum(val))
    M["segments"] = pd.DataFrame(
        {"s1": s1, "s2": s2, "shapeA": shA, "shapeB": shB, "formulaLatex": fl, "value": val, "tabulated": tb}
    )
    M["allTabulated"] = bool(tb.all())
    M["report"] = [
        f"Intégrale de Mohr sur [{_seF(a)}, {_seF(b)}] m : {n} tronçon(s)",
        f"Valeur par la table : {_seF(M['valueTable'])} ; valeur exacte : {_seF(M['value'])}",
        "Tous les tronçons sont tabulés."
        if M["allTabulated"]
        else "Certains tronçons (degré > 2) sont calculés par Gauss (hors table).",
    ]
    M["latex"] = [f"$\\int_{{{_seT(a)}}}^{{{_seT(b)}}} M_A\\,M_B\\,ds = {_seT(M['value'])}$"]
    return M


# ----------------------------------------------------------------- fonctions publiques


def deflection(model: dict, sol: dict | None = None, opts: dict | None = None) -> dict:
    """Déformée d'une poutre par 4 méthodes (intégration, aires, Castigliano, Mohr), plan xy ou xz.

    Entrées : `model` (modèle de poutre, ARCHITECTURE §3) ; `sol` (sortie de solveBeam, calculée si None) ; `opts`
    (dict facultatif) : plane ('xy' | 'xz', défaut 'xy'), nPoints (201), nCastigliano (41), includeShear (True),
    methods (défaut les 4), s0 (m, défaut : flèche max, milieux des travées, extrémités libres).
    Sortie : dict s, plane, integration (v, alpha, vPP, alphaPP, constants, equations, fmax, sAtFmax, residual),
    aires (v, alpha, areas, v0, alpha0, hingeJumps, fmax, sAtFmax, residual), castigliano (s0, vBending, vShear,
    vTotal, alpha, fmax, sAtFmax, fmaxBending, sAtFmaxBending), mohr (s0, v, details, fmax, sAtFmax), comparison
    (DataFrame Methode, fmax_m, s_m, Ecart_pct), report, latex. fmax = |v| maximal (m), positif.
    Erreur : invalidInput si plane ou une méthode est inconnue.
    """
    if sol is None:
        sol = beam_solver.solveBeam(model, _OPTS_RAPIDES)
    o = _deflOpts(opts)
    m = sol["model"]
    L = m["L"]
    Mz, My = _bendMoments(sol, m)
    xy = o["plane"] == "xy"
    if xy:
        M, T, EI, kGS = Mz, sol["Ty"], m["E"] * m["Iz"], m["ky"] * m["G"] * m["S"]
        vn, It = "v", "I_z"
    else:
        M, T, EI, kGS = ppScale(My, -1), sol["Tz"], m["E"] * m["Iy"], m["kz"] * m["G"] * m["S"]
        vn, It = "w", "I_y"
    # actions imposées : tassements et ressorts, courbure thermique (moment équivalent M + EI·κ), rotules
    conds, dSup, kap, hingePos = _imposed(sol, m, o["plane"])
    if kap != 0:
        M = ppAdd(M, ppConst(M.breaks, EI * kap))
    d = {"s": np.unique(np.concatenate([np.linspace(0, L, o["nPoints"]), M.breaks])), "plane": o["plane"]}
    sAll = d["s"]

    # 1. intégration (toujours calculée : sert aux points s0)
    integ = _integration(M, EI, conds, hingePos)
    integ["v"] = ppEval(integ["vPP"], sAll)
    integ["alpha"] = ppEval(integ["alphaPP"], sAll)
    integ["fmax"], integ["sAtFmax"] = _ppMaxAbs(integ["vPP"], integ["alphaPP"])
    integ["equations"] = [e.replace("@V", vn).replace("@I", It) for e in integ["equations"]]
    if o["s0"] is None:
        s0 = _defaultS0(m["supports"], L, integ["sAtFmax"])
    else:
        s0 = np.unique(np.minimum(np.maximum(np.ravel(o["s0"]).astype(float), 0.0), L))
    rows = []  # (méthode, fmax, s) pour le tableau de comparaison
    if "integration" in o["methods"]:
        d["integration"] = integ
        rows.append(("Intégration", integ["fmax"], integ["sAtFmax"]))

    # 2. aires et moments des aires
    if "aires" in o["methods"]:
        d["aires"] = _aires(M, EI, conds, sAll, hingePos)
        rows.append(("Aires", d["aires"]["fmax"], d["aires"]["sAtFmax"]))

    # 3. Castigliano : forces unité (solveBeam rapide), travail virtuel des réactions sur les tassements
    cache = []  # (s, m̄, t̄, r̄) des états unité déjà résolus, repris par la méthode de Mohr
    if "castigliano" in o["methods"]:
        sC = np.unique(np.concatenate([np.linspace(0, L, o["nCastigliano"]), s0]))
        vB, vS, al = np.zeros(len(sC)), np.zeros(len(sC)), np.zeros(len(sC))
        for i, s in enumerate(sC):
            mb, tb, rb = _unitSolve(m, s, "force", o["plane"])
            mc, _, rc = _unitSolve(m, s, "couple", o["plane"])
            cache.append((s, mb, tb, rb))
            vB[i] = _intProd(M, mb) / EI - rb @ dSup
            if o["includeShear"]:
                vS[i] = _intProd(T, tb) / kGS
            al[i] = _intProd(M, mc) / EI - rc @ dSup
        Cg = {"s0": sC, "vBending": vB, "vShear": vS, "vTotal": vB + vS, "alpha": al}
        iT = int(np.argmax(np.abs(Cg["vTotal"])))
        iB = int(np.argmax(np.abs(vB)))
        Cg.update(
            fmax=abs(Cg["vTotal"][iT]),
            sAtFmax=sC[iT],
            fmaxBending=abs(vB[iB]),
            sAtFmaxBending=sC[iB],
        )
        d["castigliano"] = Cg
        rows.append(("Castigliano (flexion)", Cg["fmaxBending"], Cg["sAtFmaxBending"]))
        if o["includeShear"]:
            rows.append(("Castigliano (flexion + tranchant)", Cg["fmax"], Cg["sAtFmax"]))

    # 4. intégrales de Mohr tabulées avec le diagramme unité
    if "mohr" in o["methods"]:
        vM = np.zeros(len(s0))
        details = []
        for i, s in enumerate(s0):
            hit = next((c for c in cache if c[0] == s), None)
            if hit is None:
                mb, _, rb = _unitSolve(m, s, "force", o["plane"])
            else:
                _, mb, _, rb = hit
            mi = mohrIntegral(M, mb, 0, L)
            vM[i] = mi["valueTable"] / EI - rb @ dSup
            details.append(mi["segments"])
        Mo = {"s0": s0, "v": vM, "details": details}
        iM = int(np.argmax(np.abs(vM)))
        Mo.update(fmax=abs(vM[iM]), sAtFmax=s0[iM])
        d["mohr"] = Mo
        rows.append(("Mohr (tabulé)", Mo["fmax"], Mo["sAtFmax"]))

    fref = integ["fmax"]
    ecarts = [100 * (f - fref) / fref if fref > 0 else 0.0 for _, f, _ in rows]
    d["comparison"] = pd.DataFrame(
        {
            "Methode": [r[0] for r in rows],
            "fmax_m": [r[1] for r in rows],
            "s_m": [r[2] for r in rows],
            "Ecart_pct": ecarts,
        }
    )

    # rapport et LaTeX (textes du MATLAB)
    nomI = It.replace("_", "")
    rep = [f"Plan ({o['plane']}) : E·{nomI}·{vn}'' = {'Mfz' if xy else '−Mfy'}, E·{nomI} = {_seF(EI)} N·m²"]
    iyz = _iyz(m)
    if iyz != 0:
        rep.append(
            f"Flexion déviée (Iyz = {_seF(iyz)} m⁴) : courbures couplées, "
            "[v''; −w''] = [Iz −Iyz; −Iyz Iy]⁻¹·[Mfz; Mfy]/E ; "
            f"le moment ci-dessus est le moment équivalent {'Mz,eq' if xy else '−My,eq'} = {nomI}·E·{vn}''."
        )
        if not sol["isostatic"]:
            rep.append(
                "Attention : poutre hyperstatique avec Iyz ≠ 0. Les réactions sont calculées plan par plan "
                "(couplage y–z des inconnues hyperstatiques négligé) : saisir la section dans ses axes principaux "
                "pour un calcul exact."
            )
    rep.append(
        f"Intégration : {len(M.breaks) - 1} tronçons, {2 * (len(M.breaks) - 1)} constantes, "
        f"résidu relatif {_seF(integ['residual'])} ; flèche max {_seF(integ['fmax'])} m "
        f"en s = {_seF(integ['sAtFmax'])} m"
    )
    if "aires" in d:
        A = d["aires"]
        rep.append(
            f"Aires : α0 = {_seF(A['alpha0'])} rad, {vn}0 = {_seF(A['v0'])} m ; "
            f"flèche max {_seF(A['fmax'])} m en s = {_seF(A['sAtFmax'])} m"
        )
    if "castigliano" in d:
        Cg = d["castigliano"]
        rep.append(
            f"Castigliano (forces unités, {len(Cg['s0'])} points) : flexion {_seF(Cg['fmaxBending'])} m, "
            f"avec tranchant {_seF(Cg['fmax'])} m"
        )
    if "mohr" in d:
        rep += [f"Mohr : {vn}({_seF(s)} m) = {_seF(v)} m" for s, v in zip(s0, d["mohr"]["v"], strict=True)]
    rep += [
        f"{meth} : f = {_seF(f)} m en s = {_seF(s)} m (écart {_seF(e)} %)"
        for (meth, f, s), e in zip(rows, ecarts, strict=True)
    ]
    d["report"] = rep
    Mt = "M_{fz}" if xy else "-M_{fy}"
    d["latex"] = [
        f"$E\\,{It}\\,{vn}''(s) = {Mt}(s)$",
        f"$\\alpha(s) = \\alpha_0 + \\frac{{1}}{{E\\,{It}}} \\int_0^s M\\,ds, \\ {vn}(s) = {vn}_0 + \\alpha_0\\,s"
        f" + \\frac{{1}}{{E\\,{It}}} \\sum_k A_k\\,(s - \\overline{{s}}_k)$",
        f"${vn}(s_0) = \\int_0^L \\frac{{M\\,\\overline{{m}}}}{{E\\,{It}}}\\,ds"
        f" + \\int_0^L \\frac{{T\\,\\overline{{t}}}}{{k\\,G\\,S}}\\,ds$",
        f"$f = |{vn}|_{{max}} = {_seT(integ['fmax'])}\\,\\mathrm{{m}}"
        f" \\ (s = {_seT(integ['sAtFmax'])}\\,\\mathrm{{m}})$",
        *integ["equations"],
    ]
    return d


def strainEnergy(model: dict, sol: dict | None = None) -> dict:
    """Énergie de déformation élastique : 6 termes intégrés exactement sur les pp (strainEnergy).

    Entrées : `model` (propriétés E, G, S, Iz, Iy, Ix, ky, kz, Iyz, prioritaires sur sol["model"] si fournies) ;
    `sol` (sortie de solveBeam, calculée si None).
    Sortie : dict UN, UTy, UTz, UMt, UMfy, UMfz, total (J), report, latex.
    """
    if sol is None:
        sol = beam_solver.solveBeam(model, _OPTS_RAPIDES)
    m = dict(sol["model"])
    if isinstance(model, dict):
        for f in _PROPS_ENERGIE:
            if model.get(f) is not None and np.size(model[f]) > 0:
                m[f] = model[f]
    Mz, My = _bendMoments(sol, m)  # moments équivalents, égaux à Mfz, Mfy si Iyz = 0

    def energie(f, k):
        return _intProd(f, f) / (2 * k)

    U = {
        "UN": energie(sol["N"], m["E"] * m["S"]),
        "UTy": energie(sol["Ty"], m["ky"] * m["G"] * m["S"]),
        "UTz": energie(sol["Tz"], m["kz"] * m["G"] * m["S"]),
        "UMt": energie(sol["Mt"], m["G"] * m["Ix"]),
        "UMfy": _intProd(sol["Mfy"], My) / (2 * m["E"] * m["Iy"]),
        "UMfz": _intProd(sol["Mfz"], Mz) / (2 * m["E"] * m["Iz"]),
    }
    U["total"] = sum(U.values())
    U["report"] = [
        f"Effort normal : UN = {_seF(U['UN'])} J",
        f"Tranchant : UTy = {_seF(U['UTy'])} J ; UTz = {_seF(U['UTz'])} J",
        f"Torsion : UMt = {_seF(U['UMt'])} J",
        f"Flexion : UMfy = {_seF(U['UMfy'])} J ; UMfz = {_seF(U['UMfz'])} J",
        f"Énergie totale : U = {_seF(U['total'])} J",
    ]
    U["latex"] = [
        r"$U = \int_0^L \left( \frac{N^2}{2ES} + \frac{T_y^2}{2k_yGS} + \frac{T_z^2}{2k_zGS} + \frac{M_t^2}{2GI_x}"
        r" + \frac{M_{fy}^2}{2EI_y} + \frac{M_{fz}^2}{2EI_z} \right) ds$",
        f"$U = {_seT(U['total'])}\\,\\mathrm{{J}}$",
    ]
    return U
