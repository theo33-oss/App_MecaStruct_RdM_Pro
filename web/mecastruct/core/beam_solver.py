"""Solveur de poutres, port de la partie poutres de BeamAndTrussSolver.m (ARCHITECTURE §3).

Ce fichier contient les aides de base (options, normalisation du modèle, charges réparties, quadrature de Gauss
sur des matrices de coefficients, une ligne par tronçon, ordre polyval), la méthode des coupures, la méthode intégrale,
les 4 sous-problèmes (axial, flexion xy, flexion xz, torsion), la résolution isostatique et hyperstatique (Ménabréa et
intégration, avec ressorts, tassements, dilatation thermique et rotules), les équations par tronçon, le rapport et
solveBeam.
"""

import copy
import math
import re

import numpy as np

from mecastruct.core.data_manager import hasSymbolic
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import (
    PP,
    _mergeBreaks,
    _num,
    _pad,
    _polyAdd,
    _segIndex,
    _shiftPoly,
    _texNum,
    _tol,
    poly2latex,
    poly2str,
)
from mecastruct.core.utils import as_array, as_list, is_num

_ID_MODEL = "MecaStruct:Beam:invalidModel"
_ID_SUPPORT = "MecaStruct:Beam:invalidSupport"
_ID_OPTION = "MecaStruct:Beam:invalidOption"

_GAUSS_CACHE: dict[int, tuple[np.ndarray, np.ndarray]] = {}
_GAUSS_CACHE_MAX = 60  # comme MATLAB : on ne mémorise que les ordres de 1 à 60


def _g(x: float) -> str:
    """Nombre au format %g de MATLAB (pour les messages)."""
    return format(x, "g")


def _isNum(v) -> bool:
    """Vrai pour un réel fini (scalaire) ; faux pour un booléen, un texte, None, NaN ou Inf."""
    return is_num(v) and math.isfinite(v)


def _isEmpty(v) -> bool:
    """Équivalent de isempty : None, texte, liste, tuple, dict ou tableau sans élément."""
    if v is None:
        return True
    if isinstance(v, np.ndarray):
        return v.size == 0
    return isinstance(v, str | list | tuple | dict) and len(v) == 0


def _ascii(s: str) -> str:
    """Texte (déjà en minuscules) sans les accents usuels, pour comparer les options et les types d'appuis."""
    return s.translate(str.maketrans("éèêàâîôûç", "eeeaaiouc"))


def _beamOpts(opts) -> dict:
    """Options de solveBeam complétées par leurs valeurs par défaut.

    Entrée : `opts` (dict ou None) : internalMethod, hyperMethod, useSymbolic, includeShearEnergy.
    Sortie : dict avec les 4 clés (useSymbolic vaut False par défaut, et aussi si SymPy est absent).
    Erreur : MecaStruct:Beam:invalidOption si une option est inconnue ou mal typée.
    """
    o = {"internalMethod": "both", "hyperMethod": "both", "useSymbolic": False, "includeShearEnergy": False}
    if not _isEmpty(opts):
        if not isinstance(opts, dict):
            raise MecaStructError(_ID_OPTION, "Les options doivent être une structure scalaire.")
        for cle, permis in (
            ("internalMethod", ("both", "coupures", "integrale")),
            ("hyperMethod", ("both", "menabrea", "integration")),
        ):
            v = opts.get(cle)
            if not _isEmpty(v):
                v = _ascii(v.lower()) if isinstance(v, str) else None
                if v not in permis:
                    raise MecaStructError(
                        _ID_OPTION, f"{cle} doit valoir '{permis[0]}', '{permis[1]}' ou '{permis[2]}'."
                    )
                o[cle] = v
        for cle in ("useSymbolic", "includeShearEnergy"):
            v = opts.get(cle)
            if not _isEmpty(v):
                if not (isinstance(v, bool | np.bool_) or is_num(v)):
                    raise MecaStructError(_ID_OPTION, f"{cle} doit être un booléen.")
                o[cle] = bool(v)
    o["useSymbolic"] = o["useSymbolic"] and hasSymbolic()
    return o


def _reqPos(s: dict, f: str, what: str, i: int, L: float, tol: float) -> float:
    """Abscisse obligatoire s[f] (m), ramenée dans [0, L] à `tol` près.

    Entrées : `s` (dict de l'élément), `f` (nom du champ), `what` (nom de l'élément pour le message),
    `i` (numéro à partir de 1), `L` (m), `tol` (m).
    Erreur : MecaStruct:Beam:invalidModel si le champ manque, n'est pas un réel fini ou sort de la poutre.
    """
    if not _isNum(s.get(f)):
        raise MecaStructError(_ID_MODEL, f"{what} n°{i} : champ '{f}' (m) manquant ou invalide.")
    v = float(s[f])
    if v < -tol or v > L + tol:
        raise MecaStructError(_ID_MODEL, f"{what} n°{i} : {f} = {_g(v)} m hors de la poutre [0, {_g(L)}] m.")
    return min(max(v, 0.0), L)


def _optNum(s: dict, f: str, what: str, i: int) -> float:
    """Réel facultatif s[f] (défaut 0).

    Entrées : `s` (dict), `f` (champ), `what`, `i` (numéro à partir de 1, pour le message).
    Erreur : MecaStruct:Beam:invalidModel si le champ est présent mais n'est pas un réel fini.
    """
    v = s.get(f)
    if _isEmpty(v):
        return 0.0
    if not _isNum(v):
        raise MecaStructError(_ID_MODEL, f"{what} n°{i} : champ '{f}' invalide (réel fini attendu).")
    return float(v)


def _optName(s: dict, default: str) -> str:
    """Nom s["name"] sans espaces de bord, ou `default` s'il est absent, vide ou n'est pas un texte."""
    nom = s.get("name")
    if isinstance(nom, str) and nom.strip():
        return nom.strip()
    return default


def _getArr(model: dict, f: str) -> list[dict]:
    """Liste de dicts model[f] ; absent, None ou vide donne [], un dict seul (JSON MATLAB) donne [dict].

    Erreur : MecaStruct:Beam:invalidModel si la valeur n'est pas un tableau de structures.
    """
    arr = model.get(f)
    if _isEmpty(arr):
        return []
    if not isinstance(arr, dict | list | tuple) or not all(isinstance(x, dict) for x in as_list(arr)):
        raise MecaStructError(_ID_MODEL, f"model.{f} doit être un tableau de structures (ou vide).")
    return as_list(arr)


def _normType(t, i: int) -> str:
    """Type d'appui canonique (appui_simple, rotule, pivot, pivot_glissant, encastrement) depuis un alias.

    Entrées : `t` (texte, casse, accents, espaces et tirets tolérés), `i` (numéro de l'appui, à partir de 1).
    Erreur : MecaStruct:Beam:invalidSupport si le type n'est pas un texte ou est inconnu.
    """
    if not isinstance(t, str):
        raise MecaStructError(_ID_SUPPORT, f"Appui n°{i} : type invalide.")
    cle = re.sub(r"[\s\-]+", "_", _ascii(t.strip().lower()))
    alias = {
        "appui_simple": ("appui_simple", "appui", "appui_ponctuel", "simple", "appui_plan"),
        "rotule": ("rotule", "articulation", "rotule_spherique"),
        "pivot": ("pivot",),
        "pivot_glissant": ("pivot_glissant", "glissiere"),
        "encastrement": ("encastrement", "encastre", "encastree"),
    }
    for canonique, noms in alias.items():
        if cle in noms:
            return canonique
    raise MecaStructError(
        _ID_SUPPORT,
        f"Appui n°{i} : type '{t}' inconnu (attendu : appui_simple, rotule, pivot, pivot_glissant, encastrement).",
    )


def _normalizeModel(model: dict) -> tuple[dict, list[str]]:
    """Modèle de poutre normalisé : valeurs par défaut, listes typées, positions ramenées dans [0, L].

    Entrée : `model` (dict, ARCHITECTURE §3, SI : m, Pa, m², m⁴, N, N·m ; non modifié). Les listes
    supports, pointLoads, pointMoments, distLoads, hinges peuvent être absentes, None, vides ou un dict seul ;
    coeffs peut être un nombre ou une liste.
    Sorties : `(m, notes)` ; m est une copie complète du modèle (E, S, Iz, Iy, G, Ix, ky, kz, supports avec
    spring/dx/dy/dz, hinges, thermal, pointLoads, pointMoments, distLoads) ; notes = textes « non fourni ».
    Erreurs : MecaStruct:Beam:invalidModel, MecaStruct:Beam:invalidSupport.
    """
    if not isinstance(model, dict):
        raise MecaStructError(_ID_MODEL, "Le modèle de poutre doit être une structure scalaire.")
    if not _isNum(model.get("L")) or model["L"] <= 0:
        raise MecaStructError(_ID_MODEL, "model.L (longueur, m) doit être un réel strictement positif.")
    notes: list[str] = []
    m = copy.deepcopy(model)
    L = m["L"] = float(model["L"])
    tol = 1e-12 * L

    def absent(f: str) -> bool:
        return _isEmpty(model.get(f))

    def positif(f: str) -> float:
        if not _isNum(model[f]) or model[f] <= 0:
            raise MecaStructError(_ID_MODEL, f"model.{f} doit être un réel strictement positif.")
        return float(model[f])

    for f, defaut, unite in (("E", 210e9, "Pa"), ("S", 1e-3, "m²"), ("Iz", 1e-5, "m⁴"), ("Iy", 1e-5, "m⁴")):
        if absent(f):
            m[f] = defaut
            notes.append(
                f"{f} non fourni : valeur par défaut {_g(defaut)} {unite} "
                "(sans effet sur les réactions d'un sous-problème homogène)."
            )
        else:
            m[f] = positif(f)
    if absent("G"):
        m["G"] = m["E"] / 2.6
        notes.append(f"G non fourni : G = E/(2(1+0,3)) = {_g(m['G'])} Pa.")
    else:
        m["G"] = positif("G")
    if absent("Ix"):
        m["Ix"] = m["Iz"] + m["Iy"]
        notes.append(f"Ix non fourni : Ix = Iz + Iy = {_g(m['Ix'])} m⁴.")
    else:
        m["Ix"] = positif("Ix")
    for f in ("ky", "kz"):
        m[f] = 1.0 if absent(f) else positif(f)

    # --- appuis
    sup = []
    for i, si in enumerate(_getArr(model, "supports"), start=1):
        defaut = chr(ord("A") + i - 1) if i <= 26 else f"A{i}"
        if "type" not in si:
            raise MecaStructError(_ID_SUPPORT, f"Appui n°{i} : champ 'type' manquant.")
        s = {
            "pos": _reqPos(si, "pos", "Appui", i, L, tol),
            "type": _normType(si["type"], i),
            "name": _optName(si, defaut),
            # ressort (N/m, 0 = appui rigide) et tassements imposés (m, positifs dans le sens de l'axe)
            "spring": _optNum(si, "spring", "Appui", i),
        }
        if s["spring"] < 0:
            raise MecaStructError(
                _ID_SUPPORT, f"Appui n°{i} : la raideur du ressort doit être positive ou nulle (N/m)."
            )
        for d in ("dx", "dy", "dz"):
            s[d] = _optNum(si, d, "Appui", i)
        sup.append(s)
    m["supports"] = sup

    # --- rotules intermédiaires (moments de flexion nuls en s = pos)
    hg = []
    for i, hi in enumerate(_getArr(model, "hinges"), start=1):
        h = {"pos": _reqPos(hi, "pos", "Rotule intermédiaire", i, L, tol), "name": _optName(hi, f"R{i}")}
        if h["pos"] <= tol or h["pos"] >= L - tol:
            raise MecaStructError(
                _ID_MODEL,
                f"Rotule intermédiaire n°{i} : elle doit être à l'intérieur de la poutre (0 < s < {_g(L)} m).",
            )
        if any(abs(s["pos"] - h["pos"]) <= 1e-9 * L for s in sup):
            raise MecaStructError(
                _ID_MODEL,
                f"Rotule intermédiaire n°{i} (s = {_g(h['pos'])} m) : pas sur un appui ; "
                "décalez-la ou changez le type de l'appui.",
            )
        hg.append(h)
    m["hinges"] = hg

    # --- actions thermiques : epsX = α·ΔT (allongement relatif), kv = v'' et kw = w'' d'origine thermique (1/m)
    th = {"epsX": 0.0, "kv": 0.0, "kw": 0.0}
    if isinstance(model.get("thermal"), dict) and model["thermal"]:
        for f in th:
            th[f] = _optNum(model["thermal"], f, "Action thermique", 1)
    m["thermal"] = th

    # --- forces et couples ponctuels
    pl = []
    for i, si in enumerate(_getArr(model, "pointLoads"), start=1):
        p = {"pos": _reqPos(si, "pos", "Force ponctuelle", i, L, tol)}
        for f in ("Fx", "Fy", "Fz"):
            p[f] = _optNum(si, f, "Force ponctuelle", i)
        p["name"] = _optName(si, f"F{i}")
        pl.append(p)
    m["pointLoads"] = pl
    pm = []
    for i, si in enumerate(_getArr(model, "pointMoments"), start=1):
        p = {"pos": _reqPos(si, "pos", "Couple ponctuel", i, L, tol)}
        for f in ("Mx", "My", "Mz"):
            p[f] = _optNum(si, f, "Couple ponctuel", i)
        p["name"] = _optName(si, f"C{i}")
        pm.append(p)
    m["pointMoments"] = pm
    for i, h in enumerate(hg, start=1):
        if any(abs(p["pos"] - h["pos"]) <= 1e-9 * L and (p["My"] != 0 or p["Mz"] != 0) for p in pm):
            raise MecaStructError(
                _ID_MODEL,
                f"Rotule intermédiaire n°{i} : un couple de flexion appliqué au même point est ambigu ; décalez-le.",
            )

    # --- charges réparties
    dl = []
    for i, si in enumerate(_getArr(model, "distLoads"), start=1):
        a = _reqPos(si, "a", "Charge répartie", i, L, tol)
        b = _reqPos(si, "b", "Charge répartie", i, L, tol)
        if b - a <= tol:
            raise MecaStructError(_ID_MODEL, f"Charge répartie n°{i} : il faut a < b (a = {_g(a)} m, b = {_g(b)} m).")
        d = si.get("dir")
        if not isinstance(d, str) or d.lower() not in ("x", "y", "z"):
            raise MecaStructError(_ID_MODEL, f"Charge répartie n°{i} : dir doit valoir 'x', 'y' ou 'z'.")
        c = si.get("coeffs")
        c = c.tolist() if isinstance(c, np.ndarray) else c
        seq = c if isinstance(c, list | tuple) else [c]
        if not seq or not all(_isNum(v) for v in seq):
            raise MecaStructError(
                _ID_MODEL,
                f"Charge répartie n°{i} : coeffs (N/m, ordre polyval en ξ = s - a) manquants ou invalides.",
            )
        dl.append({"a": a, "b": b, "dir": d.lower(), "coeffs": as_array(seq), "name": _optName(si, f"q{i}")})
    m["distLoads"] = dl
    return m, notes


def _prepDist(dlm: list[dict]) -> list[dict]:
    """Pré-calculs des charges réparties : polynôme global en s, primitives, résultantes.

    Entrée : `dlm` (distLoads normalisées : a, b en m, dir, coeffs en N/m en ξ = s − a, name).
    Sortie : liste de dicts a, b, dir, pg (N/m, en s), P (∫p), Q (∫s·p), Pa, Pb, Qa, Qb, I0 = ∫p (N),
    I1 = ∫s·p (N·m), deg, absInt (N, majorant de ∫|p|), name, coeffs.
    """
    d = []
    for dk in dlm:
        a, b = dk["a"], dk["b"]
        pg = _shiftPoly(dk["coeffs"], a)
        nz = np.flatnonzero(pg)
        pg = pg[nz[0] :] if nz.size else np.zeros(1)
        P = np.polyint(pg)
        Q = np.polyint(np.append(pg, 0.0))
        Pa, Pb, Qa, Qb = (float(np.polyval(R, x)) for R, x in ((P, a), (P, b), (Q, a), (Q, b)))
        d.append(
            {
                "a": a,
                "b": b,
                "dir": dk["dir"],
                "pg": pg,
                "P": P,
                "Q": Q,
                "Pa": Pa,
                "Pb": Pb,
                "Qa": Qa,
                "Qb": Qb,
                "I0": Pb - Pa,
                "I1": Qb - Qa,
                "deg": pg.size - 1,
                "absInt": (b - a) * float(np.max(np.abs(np.polyval(pg, np.linspace(a, b, 9))))),
                "name": dk["name"],
                "coeffs": dk["coeffs"],
            }
        )
    return d


def _gauss(ng: int) -> tuple[np.ndarray, np.ndarray]:
    """Points et poids de Gauss-Legendre à ng points sur [-1, 1] (Golub-Welsch), mémorisés.

    Entrée : `ng` (entier ≥ 1). Sorties : `(x, w)`, deux tableaux 1-D croissants en x, en lecture seule.
    """
    if ng in _GAUSS_CACHE:
        return _GAUSS_CACHE[ng]
    if ng == 1:
        x, w = np.zeros(1), np.array([2.0])
    else:
        k = np.arange(1, ng)
        beta = k / np.sqrt(4.0 * k**2 - 1)
        vals, V = np.linalg.eigh(np.diag(beta, 1) + np.diag(beta, -1))
        ix = np.argsort(vals)  # eigh trie déjà par ordre croissant, comme MATLAB : on le garantit
        x, w = vals[ix], 2.0 * V[0, ix] ** 2
    x.setflags(write=False)
    w.setflags(write=False)
    if ng <= _GAUSS_CACHE_MAX:
        _GAUSS_CACHE[ng] = (x, w)
    return x, w


def _gaussData(br, ng: int, D: int) -> dict:
    """Points de Gauss de chaque tronçon (intégration exacte jusqu'au degré 2·ng − 1).

    Entrées : `br` (points de rupture, m), `ng` (points par tronçon), `D` (degré maximal des polynômes évalués).
    Sortie : dict `pts` (abscisses, m), `w` (poids, m), `seg` (indice 0 du tronçon de chaque point),
    `V` (matrice de Vandermonde pts^D … pts^0), tous classés tronçon par tronçon.
    """
    br = np.asarray(br, dtype=float).ravel()
    xg, wg = _gauss(ng)
    n = br.size - 1
    half = (br[1:] - br[:n]) / 2
    mid = (br[:n] + br[1:]) / 2
    pts = (mid[:, None] + half[:, None] * xg[None, :]).ravel()
    return {
        "pts": pts,
        "w": (half[:, None] * wg[None, :]).ravel(),
        "seg": np.repeat(np.arange(n), ng),
        "V": pts[:, None] ** np.arange(D, -1, -1),
    }


def _gaussVals(G: dict, C: np.ndarray) -> np.ndarray:
    """Valeurs aux points de Gauss G de la représentation matricielle C (une ligne de coefficients par tronçon)."""
    return np.sum(G["V"] * C[G["seg"]], axis=1)


def _matIntegrate(C: np.ndarray, br) -> np.ndarray:
    """Primitive continue, nulle en br[0], d'une représentation matricielle ; une colonne de plus que C.

    Entrées : `C` (n × w, ordre polyval), `br` (n+1 points de rupture, m). Sortie : tableau n × (w+1).
    """
    br = np.asarray(br, dtype=float).ravel()
    n, w = C.shape
    P = np.hstack([C / np.arange(w, 0, -1), np.zeros((n, 1))])
    val = 0.0
    for k in range(n):
        P[k, -1] = val - np.polyval(P[k], br[k])
        val = np.polyval(P[k], br[k + 1])
    return P


def _matEval(C: np.ndarray, br, p) -> np.ndarray:
    """Évaluation (limite à droite aux points de rupture) d'une représentation matricielle aux abscisses p.

    Entrées : `C` (n × w), `br` (m), `p` (nombre ou tableau, m). Sortie : tableau 1-D de la taille de p.
    """
    p = np.asarray(p, dtype=float).ravel()
    if p.size == 0:
        return np.zeros(0)
    idx = _segIndex(np.asarray(br, dtype=float).ravel(), p, False)
    return np.sum(C[idx] * p[:, None] ** np.arange(C.shape[1] - 1, -1, -1), axis=1)


def _cleanMat(C: np.ndarray, br, absTol: float) -> np.ndarray:
    """Copie de C où les termes dont la contribution maximale sur le tronçon est < absTol sont annulés."""
    C = np.array(C, dtype=float)
    if absTol <= 0:
        return C
    br = np.asarray(br, dtype=float).ravel()
    n, w = C.shape
    smax = np.maximum(np.abs(br[:n]), np.abs(br[1 : n + 1]))
    bound = np.abs(C) * np.maximum(smax, 1e-300)[:, None] ** np.arange(w - 1, -1, -1)
    C[bound < absTol] = 0.0
    return C


def _matToPP(C: np.ndarray, br) -> PP:
    """pp d'une représentation matricielle : zéros de tête supprimés, tronçon nul = [0]."""
    coefs = []
    for row in C:
        nz = np.flatnonzero(row)
        coefs.append(np.array(row[nz[0] :], dtype=float) if nz.size else np.zeros(1))
    return PP(np.array(br, dtype=float).ravel(), coefs)


def _matMaxAbs(C: np.ndarray, br) -> float:
    """Maximum de |C| estimé aux bornes et en 7 points intérieurs de chaque tronçon."""
    br = np.asarray(br, dtype=float).ravel()
    mx = 0.0
    for k in range(C.shape[0]):
        mx = max(mx, float(np.max(np.abs(np.polyval(C[k], np.linspace(br[k], br[k + 1], 9))))))
    return mx


def _cutBend(br, tol: float, fx, fv, cx, cv, dl: list[dict], D: int) -> tuple[np.ndarray, np.ndarray]:
    """Efforts tranchant et moment fléchissant d'un problème plan par la méthode des coupures (actions à droite).

    T(s) = Σ_droite F + ∫_s^L p dx ; M(s) = Σ_droite [(x − s)·F + C] + ∫_s^L (x − s)·p dx.
    Entrées : `br` (points de rupture, m), `tol` (m), `fx`, `fv` (abscisses en m et valeurs en N des forces),
    `cx`, `cv` (abscisses en m et valeurs en N·m des couples), `dl` (sortie de _prepDist, charges du plan),
    `D` (degré maximal des polynômes, ≥ 1 ; les matrices ont D+1 colonnes).
    Sorties : `(T, M)`, tableaux n × (D+1) (ordre polyval en s), n = nombre de tronçons.
    """
    br = np.asarray(br, dtype=float).ravel()
    n = br.size - 1
    T = np.zeros((n, D + 1))
    M = np.zeros((n, D + 1))
    sR, sL = br[1:], br[:n]
    fx, fv, cx, cv = (np.asarray(v, dtype=float).ravel() for v in (fx, fv, cx, cv))
    if fx.size:
        msk = (fx[None, :] >= sR[:, None] - tol).astype(float)
        Fs = msk @ fv
        T[:, D] = Fs
        M[:, D - 1] = -Fs
        M[:, D] = msk @ (fv * fx)
    if cx.size:
        M[:, D] += (cx[None, :] >= sR[:, None] - tol).astype(float) @ cv
    for d in dl:
        right = d["a"] >= sR - tol
        if right.any():
            T[right, D] += d["I0"]
            M[right, D - 1] -= d["I0"]
            M[right, D] += d["I1"]
        inside = (d["a"] <= sL + tol) & (d["b"] >= sR - tol)
        if inside.any():
            # T(s) = P(b) - P(s) ; M(s) = Q(b) - Q(s) - s·P(b) + s·P(s)
            Tin = _pad(-d["P"], D + 1)
            Tin[D] += d["Pb"]
            Min = _pad(-d["Q"], D + 1) + _pad(np.append(d["P"], 0.0), D + 1)
            Min[D - 1] -= d["Pb"]
            Min[D] += d["Qb"]
            T[inside] += Tin
            M[inside] += Min
    return T, M


def _vec(sa: list[dict], f: str) -> np.ndarray:
    """Champ f d'une liste de dicts sous forme de tableau 1-D de réels (vide si la liste est vide)."""
    return np.array([s[f] for s in sa], dtype=float)


def _texId(name, i: int) -> str:
    """Identifiant LaTeX d'un appui : son nom réduit aux caractères alphanumériques, sinon le numéro i."""
    return re.sub(r"[^A-Za-z0-9]", "", str(name)) or str(i)


def _solve(A: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Équivalent de A\\b : solution exacte si A est carrée inversible, sinon moindres carrés de norme minimale."""
    try:
        return np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(A, b, rcond=None)[0]


def _rcond(M: np.ndarray) -> float:
    """Inverse du conditionnement en norme 1 (0 si la matrice est singulière)."""
    try:
        c = np.linalg.cond(M, 1)
    except np.linalg.LinAlgError:
        return 0.0
    return 1.0 / c if np.isfinite(c) and c > 0 else 0.0


def _makeUnk(sup, iF, fTxt, fTex, fField, fUnit, fTexUnit, iC, cTxt, cTex, cField, cSgn) -> list[dict]:
    """Inconnues de liaison d'un sous-problème : réactions de force aux appuis iF, puis moments aux appuis iC.

    Entrées : `sup` (appuis normalisés), `iF` et `iC` (indices à partir de 0), modèles de nom `fTxt`/`cTxt` et
    `fTex`/`cTex` (un %s pour le nom de l'appui), `fField`/`cField` (champ de réaction), unités, `cSgn` (signe qui
    ramène le moment du plan équivalent à la réaction physique).
    Sortie : liste de dicts kind ('F' ou 'C'), sup, pos (m), name, tex, field, sgn, unit, texUnit.
    """
    unk = []
    for i in iF:
        nom, ident = sup[i]["name"], _texId(sup[i]["name"], i + 1)
        unk.append(
            {
                "kind": "F",
                "sup": i,
                "pos": sup[i]["pos"],
                "name": fTxt % nom,
                "tex": fTex % ident,
                "field": fField,
                "sgn": 1,
                "unit": fUnit,
                "texUnit": fTexUnit,
            }
        )
    for i in iC:
        nom, ident = sup[i]["name"], _texId(sup[i]["name"], i + 1)
        unk.append(
            {
                "kind": "C",
                "sup": i,
                "pos": sup[i]["pos"],
                "name": cTxt % nom,
                "tex": cTex % ident,
                "field": cField,
                "sgn": cSgn,
                "unit": "N·m",
                "texUnit": r"N\,m",
            }
        )
    return unk


def _addCompat(sp: dict, sup: list[dict], dfield: str) -> dict:
    """Ajoute à sp la raideur de ressort (N/m) et le tassement imposé (m) de chaque réaction de force.

    Entrées : `sp` (sous-problème), `sup` (appuis normalisés), `dfield` ('dx', 'dy', 'dz' ; '' en torsion).
    Sortie : sp avec les tableaux `spring` et `delta` (un élément par inconnue).
    """
    nu = len(sp["unk"])
    sp["spring"] = np.zeros(nu)
    sp["delta"] = np.zeros(nu)
    for j, u in enumerate(sp["unk"]):
        if u["kind"] == "F" and dfield:
            sp["spring"][j] = sup[u["sup"]]["spring"]
            sp["delta"][j] = sup[u["sup"]][dfield]
    return sp


def _buildSubs(mdl: dict, dl: list[dict], nameA: str) -> list[dict]:
    """Les 4 sous-problèmes indépendants : axial, flexion (x,y), flexion (x,z) et torsion.

    Le plan (x,z) est traité comme un plan équivalent : F' = Fz, C' = −Cy, p' = pz, alors Tz = T' et Mfy = −M'.
    Entrées : `mdl` (modèle normalisé), `dl` (sortie de _prepDist), `nameA` (appui où l'on écrit les moments).
    Sortie : liste de 4 dicts (name, label, kind 'bar'/'bend', charges fx/fv/cx/cv/dl, inconnues unk, raideurs,
    textes du rapport, kappa, hinges, spring, delta).
    """
    sup = mdl["supports"]
    types = [s["type"] for s in sup]
    bu = [i for i, t in enumerate(types) if t in ("rotule", "pivot", "encastrement")]
    enc = [i for i, t in enumerate(types) if t == "encastrement"]
    allIdx = list(range(len(sup)))
    PL, PM = mdl["pointLoads"], mdl["pointMoments"]
    plPos, pmPos = _vec(PL, "pos"), _vec(PM, "pos")
    none = np.zeros(0)

    def deDir(d: str) -> list[dict]:
        return [x for x in dl if x["dir"] == d]

    s1 = {
        "name": "axial",
        "label": "Axial (u)",
        "kind": "bar",
        "fx": plPos,
        "fv": _vec(PL, "Fx"),
        "cx": none,
        "cv": none,
        "dl": deDir("x"),
        "unk": _makeUnk(sup, bu, "X_%s", "X_{%s}", "Rx", "N", "N", [], "", "", "", 1),
        "stiff": mdl["E"] * mdl["S"],
        "stiffTxt": "E·S",
        "stiffTex": r"E\,S",
        "shear": math.inf,
        "shearTxt": "",
        "shearTex": "",
        "eqTxt": ["Σ Fx = 0"],
        "eqTex": [r"\sum F_{x} = 0"],
        "rowSign": [1],
        "intTxt": "E·S·u'(s) = N(s)  ->  u(s) = C1 + (1/ES)·∫_0^s N dx",
        "intTex": r"$E\,S\,u'(s) = N(s) \Rightarrow u(s) = C_1 + \frac{1}{E\,S}\int_0^s N\,dx$",
        "dispTxt": "u",
        "constNames": ["C1 = u(0)"],
        "energyTxt": "U = ∫ N²/(2·E·S) ds",
        "energyTex": (
            r"$\delta_{ij} = \int_0^L \frac{n_i\,n_j}{E\,S}\,ds,\ \ "
            r"\delta_{i0} = \int_0^L \frac{n_i\,N_0}{E\,S}\,ds$"
        ),
        "compT": "N",
        "compM": "",
    }
    s2 = {
        "name": "xy",
        "label": "Flexion (x,y)",
        "kind": "bend",
        "fx": plPos,
        "fv": _vec(PL, "Fy"),
        "cx": pmPos,
        "cv": _vec(PM, "Mz"),
        "dl": deDir("y"),
        "unk": _makeUnk(sup, allIdx, "Y_%s", "Y_{%s}", "Ry", "N", "N", enc, "Mz_%s", "M_{z%s}", "Mz", 1),
        "stiff": mdl["E"] * mdl["Iz"],
        "stiffTxt": "E·Iz",
        "stiffTex": r"E\,I_z",
        "shear": mdl["ky"] * mdl["G"] * mdl["S"],
        "shearTxt": "ky·G·S",
        "shearTex": r"k_y\,G\,S",
        "eqTxt": ["Σ Fy = 0", f"Σ Mz({nameA}) = 0"],
        "eqTex": [r"\sum F_{y} = 0", r"\sum M_{z}(" + _texId(nameA, 0) + r") = 0"],
        "rowSign": [1, 1],
        "intTxt": "E·Iz·v''(s) = Mfz(s)  ->  v(s) = C1 + C2·s + (1/EIz)·∫∫ Mfz",
        "intTex": (
            r"$E\,I_z\,v''(s) = M_{fz}(s) \Rightarrow "
            r"v(s) = C_1 + C_2\,s + \frac{1}{E\,I_z}\int_0^s\!\!\int_0^t M_{fz}\,dx\,dt$"
        ),
        "dispTxt": "v",
        "constNames": ["C1 = v(0)", "C2 = v'(0)"],
        "energyTxt": "U = ∫ Mfz²/(2·E·Iz) ds",
        "energyTex": (
            r"$\delta_{ij} = \int_0^L \frac{m_i\,m_j}{E\,I_z}\,ds,\ \ "
            r"\delta_{i0} = \int_0^L \frac{m_i\,M_0}{E\,I_z}\,ds$"
        ),
        "compT": "Ty",
        "compM": "Mfz",
    }
    s3 = {
        "name": "xz",
        "label": "Flexion (x,z)",
        "kind": "bend",
        "fx": plPos,
        "fv": _vec(PL, "Fz"),
        "cx": pmPos,
        "cv": -_vec(PM, "My"),
        "dl": deDir("z"),
        "unk": _makeUnk(sup, allIdx, "Z_%s", "Z_{%s}", "Rz", "N", "N", enc, "My_%s", "M_{y%s}", "My", -1),
        "stiff": mdl["E"] * mdl["Iy"],
        "stiffTxt": "E·Iy",
        "stiffTex": r"E\,I_y",
        "shear": mdl["kz"] * mdl["G"] * mdl["S"],
        "shearTxt": "kz·G·S",
        "shearTex": r"k_z\,G\,S",
        "eqTxt": ["Σ Fz = 0", f"Σ My({nameA}) = 0"],
        "eqTex": [r"\sum F_{z} = 0", r"\sum M_{y}(" + _texId(nameA, 0) + r") = 0"],
        "rowSign": [1, -1],
        "intTxt": "E·Iy·w''(s) = -Mfy(s)  ->  w(s) = C1 + C2·s - (1/EIy)·∫∫ Mfy",
        "intTex": (
            r"$E\,I_y\,w''(s) = -M_{fy}(s) \Rightarrow "
            r"w(s) = C_1 + C_2\,s - \frac{1}{E\,I_y}\int_0^s\!\!\int_0^t M_{fy}\,dx\,dt$"
        ),
        "dispTxt": "w",
        "constNames": ["C1 = w(0)", "C2 = w'(0)"],
        "energyTxt": "U = ∫ Mfy²/(2·E·Iy) ds",
        "energyTex": (
            r"$\delta_{ij} = \int_0^L \frac{m_i\,m_j}{E\,I_y}\,ds,\ \ "
            r"\delta_{i0} = \int_0^L \frac{m_i\,M_0}{E\,I_y}\,ds$"
        ),
        "compT": "Tz",
        "compM": "Mfy",
    }
    s4 = {
        "name": "torsion",
        "label": "Torsion (θx)",
        "kind": "bar",
        "fx": pmPos,
        "fv": _vec(PM, "Mx"),
        "cx": none,
        "cv": none,
        "dl": [],
        "unk": _makeUnk(sup, enc, "Mx_%s", "M_{x%s}", "Mx", "N·m", r"N\,m", [], "", "", "", 1),
        "stiff": mdl["G"] * mdl["Ix"],
        "stiffTxt": "G·Ix",
        "stiffTex": r"G\,I_x",
        "shear": math.inf,
        "shearTxt": "",
        "shearTex": "",
        "eqTxt": ["Σ Mx = 0"],
        "eqTex": [r"\sum M_{x} = 0"],
        "rowSign": [1],
        "intTxt": "G·Ix·φ'(s) = Mt(s)  ->  φ(s) = C1 + (1/GIx)·∫_0^s Mt dx",
        "intTex": r"$G\,I_x\,\varphi'(s) = M_t(s) \Rightarrow \varphi(s) = C_1 + \frac{1}{G\,I_x}\int_0^s M_t\,dx$",
        "dispTxt": "φ",
        "constNames": ["C1 = φ(0)"],
        "energyTxt": "U = ∫ Mt²/(2·G·Ix) ds",
        "energyTex": (
            r"$\delta_{ij} = \int_0^L \frac{t_i\,t_j}{G\,I_x}\,ds,\ \ "
            r"\delta_{i0} = \int_0^L \frac{t_i\,M_{t0}}{G\,I_x}\,ds$"
        ),
        "compT": "Mt",
        "compM": "",
    }
    # actions de compatibilité : ressorts, tassements imposés, dilatation thermique, rotules intermédiaires
    th = mdl["thermal"]
    s1["kappa"], s2["kappa"], s3["kappa"], s4["kappa"] = th["epsX"], th["kv"], th["kw"], 0.0
    hp = _vec(mdl["hinges"], "pos")
    s1["hinges"], s2["hinges"], s3["hinges"], s4["hinges"] = none, hp, hp, none
    return [
        _addCompat(s1, sup, "dx"),
        _addCompat(s2, sup, "dy"),
        _addCompat(s3, sup, "dz"),
        _addCompat(s4, sup, ""),
    ]


def _baseOrder(unk: list[dict], isBend: bool) -> list[int]:
    """Ordre de préférence des réactions conservées dans le système de base (indices à partir de 0).

    L'encastrement (console) d'abord, sinon les appuis extrêmes (poutre sur 2 appuis), puis les autres.
    """
    if not unk:
        return []
    pos = _vec(unk, "pos")
    isC = np.array([u["kind"] == "C" for u in unk])
    supIdx = _vec(unk, "sup")
    iF = np.flatnonzero(~isC)
    iF = iF[np.argsort(pos[iF], kind="stable")]
    order: list[int] = []
    if isBend and isC.any():
        c1 = int(np.flatnonzero(isC)[0])
        order = [*iF[supIdx[iF] == supIdx[c1]].tolist(), c1]
    if iF.size:
        order += [int(iF[0]), int(iF[-1]), *iF[1:-1].tolist()]
    order += np.flatnonzero(isC).tolist()
    return list(dict.fromkeys(order))


def _integration(sp, A, bv, TL, ML, TU, MU, br, o, forceLsq) -> tuple[np.ndarray, dict]:
    """Méthode d'intégration : réactions et constantes d'intégration résolues ensemble (btsIntegration).

    Le système réunit l'équilibre A·R + b = 0 et une condition cinématique par inconnue de liaison (déplacement nul,
    imposé, ou lié à la réaction par un ressort), avec les inconnues R, les constantes C1 (et C2 en flexion) et un
    saut de rotation par rotule.
    Entrées : `sp` (sous-problème), `A`, `bv`, `TL`, `ML`, `TU`, `MU` (comme _menabrea), `br` (m), `o` (options),
    `forceLsq` (moindres carrés de norme minimale même si le système est bien conditionné).
    Sorties : `(R, info)` ; R = réactions (nu), info = dict subproblem, label, unknowns, K, f, solution, constants,
    conditions, includeShear.
    """
    isBend = sp["kind"] == "bend"
    neq, nu = A.shape
    nc = 1 + int(isBend)  # constantes d'intégration (C1, C2) ; neq = nc + nombre de rotules
    hp = np.asarray(sp["hinges"], dtype=float).ravel()
    nh = hp.size
    P = _vec(sp["unk"], "pos")
    invk = np.zeros(nu)
    iK = sp["spring"] > 0
    invk[iK] = 1.0 / sp["spring"][iK]
    useShear = bool(isBend and o["includeShearEnergy"] and math.isfinite(sp["shear"]))
    Vp = np.zeros((nu, nu))
    THp = np.zeros((nu, nu))
    if isBend:
        vL, thL = _bendDisp(ML, TL, br, P, sp["stiff"], sp["shear"], useShear)
        for j in range(nu):
            Vp[:, j], THp[:, j] = _bendDisp(MU[:, :, j], TU[:, :, j], br, P, sp["stiff"], sp["shear"], useShear)
    else:
        vL = _matEval(_matIntegrate(TL, br), br, P) / sp["stiff"]
        for j in range(nu):
            Vp[:, j] = _matEval(_matIntegrate(TU[:, :, j], br), br, P) / sp["stiff"]
    n = nu + nc + nh  # inconnues : réactions, constantes, sauts de rotation aux rotules
    K = np.zeros((n, n))
    f = np.zeros(n)
    K[:neq, :nu] = A
    f[:neq] = -bv
    cond = []
    for k in range(nu):
        r = neq + k
        supName = sp["unk"][k]["name"]
        if "_" in supName:
            supName = supName.split("_", 1)[1]
        if isBend and sp["unk"][k]["kind"] == "C":
            K[r, :nu] = THp[k]
            K[r, nu + 1] = 1
            K[r, nu + nc :] = P[k] > hp + 1e-12  # sauts de rotation des rotules à gauche de l'appui
            f[r] = -thL[k] - sp["kappa"] * P[k]
            # avec le tranchant, v' = θ + T/kGS : l'encastrement impose la rotation de section θ = 0
            cond.append(f"θ({supName}) = 0" if useShear else f"{sp['dispTxt']}'({supName}) = 0")
        elif isBend:
            K[r, :nu] = Vp[k]
            K[r, k] += invk[k]
            K[r, nu] = 1
            K[r, nu + 1] = P[k]
            K[r, nu + nc :] = np.maximum(P[k] - hp, 0.0)
            f[r] = sp["delta"][k] - vL[k] - sp["kappa"] * P[k] ** 2 / 2
            cond.append(_condText(sp["dispTxt"], supName, sp["delta"][k], sp["spring"][k]))
        else:
            K[r, :nu] = Vp[k]
            K[r, k] += invk[k]
            K[r, nu] = 1
            f[r] = sp["delta"][k] - vL[k] - sp["kappa"] * P[k]
            cond.append(_condText(sp["dispTxt"], supName, sp["delta"][k], sp["spring"][k]))
    # équilibrage des lignes et colonnes (unités hétérogènes)
    rs = np.max(np.abs(K), axis=1)
    rs[rs == 0] = 1.0
    Ks = K / rs[:, None]
    fs = f / rs
    cs = np.max(np.abs(Ks), axis=0)
    cs[cs == 0] = 1.0
    Ks = Ks / cs
    if forceLsq or _rcond(Ks) < 1e-12:
        zs = np.linalg.lstsq(Ks, fs, rcond=None)[0]
    else:
        zs = np.linalg.solve(Ks, fs)
    z = zs / cs
    constNames = list(sp["constNames"])
    if useShear:
        constNames[1] = f"C2 = θ(0) (rotation de section ; {sp['dispTxt']}'(0) = C2 + T(0)/(k·G·S))"
    for hh in range(nh):
        constNames.append(f"Δθ_R{hh + 1} = saut de rotation à la rotule s = {_num(hp[hh])} m")
    info = {
        "subproblem": sp["name"],
        "label": sp["label"],
        "unknowns": [u["name"] for u in sp["unk"]] + constNames,
        "K": K,
        "f": f,
        "solution": z,
        "constants": z[nu:],
        "conditions": cond,
        "includeShear": useShear,
    }
    return z[:nu], info


def _cleanReactions(R: np.ndarray, unk: list[dict], isBend: bool, scaleEq: np.ndarray) -> np.ndarray:
    """Annule les réactions de l'ordre du bruit numérique (relatif à l'échelle des charges)."""
    R = np.array(R, dtype=float)
    for j, u in enumerate(unk):
        sc = scaleEq[-1] if isBend and u["kind"] == "C" else scaleEq[0]
        if abs(R[j]) <= 1e-13 * sc:
            R[j] = 0.0
    return R + 0.0


def _reactionDiff(R1: np.ndarray, R2: np.ndarray, unk: list[dict], isBend: bool, scaleEq: np.ndarray) -> float:
    """Écart relatif maximal entre deux jeux de réactions."""
    e = 0.0
    for j, u in enumerate(unk):
        sc = scaleEq[-1] if isBend and u["kind"] == "C" else scaleEq[0]
        den = max(abs(R1[j]), sc) or 1.0
        e = max(e, abs(R1[j] - R2[j]) / den)
    return float(e)


def _loadMoments(sp: dict, xA: float) -> list[dict]:
    """Moments au point A des charges d'un sous-problème en flexion (affichage du transport), sinon [].

    Sortie : liste de dicts label (texte) et value (N·m, dans le sens du plan équivalent signé par rowSign).
    """
    lm: list[dict] = []
    if sp["kind"] != "bend":
        return lm
    sg = sp["rowSign"][-1]
    pre = "-" if sg < 0 else ""
    for x, f in zip(sp["fx"], sp["fv"], strict=True):
        if f != 0:
            lm.append(
                {
                    "label": f"force en s = {_num(x)} : {pre}({_num(x)} - {_num(xA)})·({_num(f)})",
                    "value": float(sg * (x - xA) * f),
                }
            )
    for x, c in zip(sp["cx"], sp["cv"], strict=True):
        if c != 0:
            lm.append({"label": f"couple en s = {_num(x)}", "value": float(sg * c)})
    for d in sp["dl"]:
        if np.any(d["pg"] != 0):
            lm.append(
                {
                    "label": (
                        f"charge répartie {d['name']} : ∫(x - {_num(xA)})·p dx sur [{_num(d['a'])} ; {_num(d['b'])}]"
                    ),
                    "value": float(sg * (d["I1"] - xA * d["I0"])),
                }
            )
    return lm


def _menabrea(sp, A, bv, TL, ML, TU, MU, Gq, o, isBend) -> tuple[np.ndarray, dict]:
    """Théorème de Ménabréa (dU/dXi = 0) sur un système de base isostatique.

    Entrées : `sp` (sous-problème), `A`, `bv` (équilibre A·R + bv = 0), `TL`, `ML` (efforts des charges seules),
    `TU`, `MU` (efforts unitaires de chaque inconnue, n × (D+1) × nu), `Gq` (quadrature de _gaussData), `o` (options),
    `isBend` (flexion).
    Sorties : `(R, men)` ; R = réactions (nu), men = dict subproblem, label, unknowns, unknownsTex, base, delta,
    delta0, rhs, X, includeShear, sgn.
    """
    neq, nu = A.shape
    base: list[int] = []
    for j in _baseOrder(sp["unk"], isBend):
        cand = [*base, j]
        if np.linalg.matrix_rank(A[:, cand]) == len(cand):
            base = cand
        if len(base) == neq:
            break
    Xi = [j for j in range(nu) if j not in base]
    Ab = A[:, base]
    R0 = -_solve(Ab, bv)
    rb = -_solve(Ab, A[:, Xi])
    h = len(Xi)
    U, P0 = (MU, ML) if isBend else (TU, TL)
    Ub = U[:, :, base]
    w = Gq["w"]
    v0 = _gaussVals(Gq, P0 + Ub @ R0)
    V = np.column_stack([_gaussVals(Gq, U[:, :, Xi[i]] + Ub @ rb[:, i]) for i in range(h)])
    delta = (V.T @ (w[:, None] * V)) / sp["stiff"]
    d0 = (V.T @ (w * v0)) / sp["stiff"]
    withShear = bool(isBend and o["includeShearEnergy"] and math.isfinite(sp["shear"]))
    if withShear:
        TUb = TU[:, :, base]
        q0 = _gaussVals(Gq, TL + TUb @ R0)
        W = np.column_stack([_gaussVals(Gq, TU[:, :, Xi[i]] + TUb @ rb[:, i]) for i in range(h)])
        delta = delta + (W.T @ (w[:, None] * W)) / sp["shear"]
        d0 = d0 + (W.T @ (w * q0)) / sp["shear"]
    # Actions imposées (travail virtuel des réactions R = c + S·X sur les déplacements d'appui
    # d_j = tassement_j − R_j/k_j, et des déformations thermiques κ) :
    #   Σj δij·Xj + δi0 + ∫ mi·κ ds = Σj Sji·d_j
    S = np.zeros((nu, h))
    S[base, :] = rb
    S[Xi, :] = np.eye(h)
    c0 = np.zeros(nu)
    c0[base] = R0
    invk = np.zeros(nu)
    iK = sp["spring"] > 0
    invk[iK] = 1.0 / sp["spring"][iK]
    thTerm = sp["kappa"] * (V.T @ w)
    delta = delta + S.T @ (invk[:, None] * S)
    rhs = S.T @ sp["delta"] - S.T @ (invk * c0) - d0 - thTerm
    d0 = -rhs
    X = np.linalg.lstsq(delta, rhs, rcond=None)[0] if _rcond(delta) < 1e-14 else np.linalg.solve(delta, rhs)
    R = np.zeros(nu)
    R[Xi] = X
    R[base] = R0 + rb @ X
    names, texs = [u["name"] for u in sp["unk"]], [u["tex"] for u in sp["unk"]]
    men = {
        "subproblem": sp["name"],
        "label": sp["label"],
        "unknowns": [names[i] for i in Xi],
        "unknownsTex": [texs[i] for i in Xi],
        "base": [names[i] for i in base],
        "delta": delta,
        "delta0": d0,
        "rhs": rhs,
        "X": X,
        "includeShear": withShear,
        "sgn": _vec([sp["unk"][i] for i in Xi], "sgn"),  # plan équivalent -> réaction physique
    }
    return R, men


def _bendDisp(M, T, br, P, EI: float, kGS: float, useShear: bool) -> tuple[np.ndarray, np.ndarray]:
    """Flèche et rotation (intégrations depuis s = 0, constantes nulles) aux abscisses P.

    Entrées : `M`, `T` (moment et tranchant, matrices n × w), `br` (m), `P` (abscisses, m), `EI` (N·m²),
    `kGS` (N, raideur de cisaillement), `useShear` (ajoute la flèche de cisaillement).
    Sorties : `(v, th)` en m et rad.
    """
    I1 = _matIntegrate(M, br)
    I2 = _matIntegrate(I1, br)
    th = _matEval(I1, br, P) / EI
    v = _matEval(I2, br, P) / EI
    if useShear:
        v = v + _matEval(_matIntegrate(T, br), br, P) / kGS
    return v, th


def _condText(disp: str, supName: str, delta: float, spring: float) -> str:
    """Condition cinématique d'un appui : déplacement nul, imposé (tassement) ou lié à la réaction (ressort)."""
    if spring > 0:
        return f"{disp}({supName}) = {_num(delta)} - R/k (k = {_num(spring)} N/m)"
    if delta != 0:
        return f"{disp}({supName}) = {_num(delta)} m"
    return f"{disp}({supName}) = 0"


def _solveSub(sp: dict, br, tol: float, D: int, Gq: dict, o: dict, L: float, xA: float) -> dict:
    """Résout un sous-problème : réactions (isostatique, Ménabréa ou intégration) puis efforts par coupures.

    Entrées : `sp` (sous-problème de _buildSubs), `br` (points de rupture, m), `tol` (m), `D` (degré maximal),
    `Gq` (quadrature), `o` (options), `L` (m), `xA` (abscisse du point A des moments, m).
    Sortie : sp complété de A, b, scaleEq, loaded, nunk, neq, rank, h, R, T, M, men, int, Rmen, Rint,
    hyperCheck, status, degenerate, loadMoments (R, Rmen, Rint : None si non calculés).
    Erreur : MecaStruct:Beam:mechanism si les liaisons sont insuffisantes pour le chargement.
    """
    n = len(br) - 1
    isBend = sp["kind"] == "bend"
    unk = sp["unk"]
    nu = len(unk)
    fv, cv = sp["fv"], sp["cv"]
    TL, ML = _cutBend(br, tol, sp["fx"], fv, sp["cx"], cv, sp["dl"], D)
    TU = np.zeros((n, D + 1, nu))
    MU = np.zeros((n, D + 1, nu))
    sR = br[1:]
    for j, u in enumerate(unk):
        msk = (u["pos"] >= sR - tol).astype(float)
        if isBend and u["kind"] == "C":
            MU[:, D, j] = msk
        else:
            TU[:, D, j] = msk
            if isBend:
                MU[:, D - 1, j] = -msk
                MU[:, D, j] = msk * u["pos"]

    # --- équations d'équilibre A·R + b = 0 (moments au point A d'abscisse xA)
    I0 = sum(d["I0"] for d in sp["dl"])
    I1 = sum(d["I1"] for d in sp["dl"])
    absP = sum(d["absInt"] for d in sp["dl"])
    loadedDist = any(np.any(d["pg"] != 0) for d in sp["dl"])
    rows = [np.array([1.0 if not isBend or u["kind"] == "F" else 0.0 for u in unk])]
    rhsEq = [float(np.sum(fv) + I0)]
    sc0 = float(np.sum(np.abs(fv)) + absP)
    scaleEq = [sc0]
    if isBend:
        rows.append(np.array([u["pos"] - xA if u["kind"] == "F" else 1.0 for u in unk]))
        rhsEq.append(float(np.sum((sp["fx"] - xA) * fv) + np.sum(cv) + I1 - xA * I0))
        scaleEq.append(sc0 * L + float(np.sum(np.abs(cv))))
    # rotules intermédiaires : un moment de flexion nul de plus par rotule (équation d'équilibre en plus)
    for hp in sp["hinges"]:
        rows.append(np.array([_matEval(MU[:, :, j], br, hp)[0] for j in range(nu)]))
        rhsEq.append(float(_matEval(ML, br, hp)[0]))
        scaleEq.append(scaleEq[1])
        sp["eqTxt"].append(f"M({_num(hp)}) = 0 (rotule)")
        sp["eqTex"].append(f"M({_texNum(hp)}) = 0")
        sp["rowSign"].append(sp["rowSign"][1])
    A = np.array(rows).reshape(len(rows), nu)
    bv = np.array(rhsEq)
    scaleEq = np.array(scaleEq)
    neq = A.shape[0]
    # une action imposée (tassement, dilatation) charge aussi un hyperstatique sans charge
    loaded = bool(np.any(fv != 0) or np.any(cv != 0) or loadedDist or np.any(sp["delta"] != 0) or sp["kappa"] != 0)

    rA = int(np.linalg.matrix_rank(A)) if nu > 0 else 0
    R = np.zeros(nu)
    men = intg = Rmen = Rint = None
    hyperCheck = math.nan
    degenerate = False
    if rA < neq:
        # liaisons insuffisantes : chargement compatible ou mécanisme
        if nu > 0:
            R = np.linalg.pinv(A) @ (-bv)
        res = np.abs(A @ R + bv)
        if np.any(res > 1e-9 * scaleEq):
            raise MecaStructError(
                "MecaStruct:Beam:mechanism",
                f"Mécanisme : sous-problème {sp['label']}, liaisons insuffisantes ou mal disposées pour le "
                f"chargement appliqué ({nu} inconnue(s) de liaison, rang {rA} < {neq} équation(s)).",
            )
        h = nu - rA
        if h > 0:
            degenerate = True
            R, intg = _integration(sp, A, bv, TL, ML, TU, MU, br, o, True)
            Rint = Rmen = R
        status = "liaisons insuffisantes, chargement compatible"
    else:
        h = nu - neq
        if h == 0:
            R = -_solve(A, bv)
            status = "isostatique"
        elif not loaded:
            status = "hyperstatique non chargé"
            Rmen = Rint = R.copy()
        else:
            status = "hyperstatique"
            doMen = o["hyperMethod"] in ("both", "menabrea")
            doInt = o["hyperMethod"] in ("both", "integration")
            if doMen:
                Rmen, men = _menabrea(sp, A, bv, TL, ML, TU, MU, Gq, o, isBend)
            if doInt:
                Rint, intg = _integration(sp, A, bv, TL, ML, TU, MU, br, o, False)
            R = Rmen if doMen else Rint
            if doMen and doInt:
                hyperCheck = _reactionDiff(Rmen, Rint, unk, isBend, scaleEq)

    # --- nettoyage des réactions (bruit numérique)
    R = _cleanReactions(R, unk, isBend, scaleEq)
    if Rmen is not None:
        Rmen = _cleanReactions(Rmen, unk, isBend, scaleEq)
    if Rint is not None:
        Rint = _cleanReactions(Rint, unk, isBend, scaleEq)

    T, M = TL, ML
    if nu > 0:
        T, M = TL + TU @ R, ML + MU @ R
    sp.update(
        A=A,
        b=bv,
        scaleEq=scaleEq,
        loaded=loaded,
        nunk=nu,
        neq=neq,
        rank=rA,
        h=int(h),
        R=R,
        T=T,
        M=M,
        men=men,
        int=intg,
        Rmen=Rmen,
        Rint=Rint,
        hyperCheck=hyperCheck,
        status=status,
        degenerate=degenerate,
    )
    sp["loadMoments"] = _loadMoments(sp, xA)
    return sp


def _jumps(act: dict, fl: list[str], a: float, tol: float) -> np.ndarray:
    """Sauts des 6 composantes en s = a : somme des actions ponctuelles (charges et réactions) situées en a ± tol.

    Entrées : `act` (sortie de _actions : tableaux m × 2 [abscisse, valeur]), `fl` (6 noms de composantes),
    `a` (m), `tol` (m). Sortie : tableau de 6 sauts (N ou N·m).
    """
    j = np.zeros(6)
    for c in range(6):
        lst = act[fl[c]]
        if lst.size:
            j[c] = np.sum(lst[np.abs(lst[:, 0] - a) <= tol, 1])
    return j


def _extrema(pp: PP) -> dict:
    """Extrema d'un pp : bornes de chaque tronçon (limites) et racines réelles de la dérivée.

    Sortie : dict max, sMax (abscisse du maximum, m), min, sMin.
    """
    br = pp.breaks
    cs: list[float] = []
    cv: list[float] = []
    for k, ck in enumerate(pp.coefs):
        a, b = br[k], br[k + 1]
        ss = [a, b]
        if len(ck) > 2:
            r = np.roots(np.polyder(ck))
            r = r[np.abs(r.imag) <= 1e-9 * np.maximum(1.0, np.abs(r.real))].real
            ss += r[(r > a) & (r < b)].tolist()
        cs += ss
        cv += np.polyval(ck, ss).tolist()
    i1, i2 = int(np.argmax(cv)), int(np.argmin(cv))
    return {"max": cv[i1], "sMax": cs[i1], "min": cv[i2], "sMin": cs[i2]}


def _reactionStruct(sup: list[dict]) -> list[dict]:
    """Réactions nulles (name, pos, type, Rx, Ry, Rz, Mx, My, Mz) pour chaque appui."""
    return [
        {
            "name": s["name"],
            "pos": s["pos"],
            "type": s["type"],
            "Rx": 0.0,
            "Ry": 0.0,
            "Rz": 0.0,
            "Mx": 0.0,
            "My": 0.0,
            "Mz": 0.0,
        }
        for s in sup
    ]


def _actions(mdl: dict, reac: list[dict]) -> dict:
    """Actions ponctuelles (charges puis réactions) par composante Fx, Fy, Fz, Mx, My, Mz.

    Entrées : `mdl` (modèle normalisé), `reac` (réactions de solveBeam).
    Sortie : dict de tableaux m × 2 [abscisse en m, valeur en N ou N·m].
    """

    def col(sa: list[dict], f: str) -> np.ndarray:
        return np.array([[s["pos"], s[f]] for s in sa], dtype=float).reshape(-1, 2)

    act = {}
    for f in ("Fx", "Fy", "Fz"):
        act[f] = np.vstack([col(mdl["pointLoads"], f), col(reac, "R" + f[1])])
    for f in ("Mx", "My", "Mz"):
        act[f] = np.vstack([col(mdl["pointMoments"], f), col(reac, f)])
    return act


_COMPOSANTES = ("N", "Ty", "Tz", "Mt", "Mfy", "Mfz")
_TEX_COMPOSANTES = ("N", "T_{y}", "T_{z}", "M_{t}", "M_{fy}", "M_{fz}")
_FL_ACTIONS = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")


def _symPoly(c, x):
    """Polynôme numérique (ordre polyval) en expression SymPy exacte de x (flottants convertis en rationnels).

    Entrées : `c` (coefficients), `x` (symbole SymPy). Sortie : expression SymPy.
    """
    import sympy as sp  # import tardif : SymPy est optionnel

    c = np.atleast_1d(np.asarray(c, dtype=float))
    return sp.Add(*[sp.Rational(float(ck)) * x ** (c.size - 1 - k) for k, ck in enumerate(c)])


def _symCoefs(e, s) -> np.ndarray:
    """Coefficients (ordre polyval, flottants) d'une expression SymPy polynomiale en s ; une constante : 1 élément.

    Entrées : `e` (expression SymPy), `s` (symbole). Sortie : tableau 1-D.
    """
    import sympy as sp  # import tardif : SymPy est optionnel

    e = sp.expand(e)
    if not e.free_symbols:
        return np.array([float(e)])
    return np.array([float(ck) for ck in sp.Poly(e, s).all_coeffs()])


def _integralRowsNum(endv: np.ndarray, px, py, pz, sR: float) -> list[np.ndarray]:
    """Coefficients (N, Ty, Tz, Mt, Mfy, Mfz) d'un tronçon par np.polyint, à partir des valeurs en sR.

    Entrées : `endv` (6 valeurs en s = sR : N, N·m), `px`, `py`, `pz` (charges réparties en s, N/m), `sR` (m).
    Sortie : liste de 6 tableaux de coefficients (ordre polyval).
    """
    Px, Py, Pz = np.polyint(px), np.polyint(py), np.polyint(pz)
    cN = -Px
    cN[-1] += endv[0] + np.polyval(Px, sR)
    cTy = -Py
    cTy[-1] += endv[1] + np.polyval(Py, sR)
    cTz = -Pz
    cTz[-1] += endv[2] + np.polyval(Pz, sR)
    ITy = np.polyint(cTy)
    cMfz = -ITy
    cMfz[-1] += endv[5] + np.polyval(ITy, sR)
    ITz = np.polyint(cTz)
    cMfy = ITz.copy()
    cMfy[-1] += endv[4] - np.polyval(ITz, sR)
    return [cN, cTy, cTz, np.array([endv[3]]), cMfy, cMfz]


def _integralRowsSym(endv: np.ndarray, px, py, pz, sR: float) -> list[np.ndarray]:
    """Même résultat que _integralRowsNum, par intégrales SymPy exactes (flottants convertis en rationnels).

    Entrées et sortie : comme _integralRowsNum.
    """
    import sympy as sp  # import tardif : SymPy est optionnel

    x, s = sp.symbols("x s")
    bor = sp.Rational(float(sR))
    I = [sp.integrate(_symPoly(p, x), (x, s, bor)) for p in (px, py, pz)]
    NS = sp.Rational(float(endv[0])) + I[0]
    TyS = sp.Rational(float(endv[1])) + I[1]
    TzS = sp.Rational(float(endv[2])) + I[2]
    I2 = [sp.integrate(T.subs(s, x), (x, s, bor)) for T in (TyS, TzS)]
    MfzS = sp.Rational(float(endv[5])) + I2[0]
    MfyS = sp.Rational(float(endv[4])) - I2[1]
    return [
        _symCoefs(NS, s),
        _symCoefs(TyS, s),
        _symCoefs(TzS, s),
        np.array([endv[3]]),
        _symCoefs(MfyS, s),
        _symCoefs(MfzS, s),
    ]


def _integralMethod(br, tol: float, act: dict, dl: list[dict], D: int, useSym: bool) -> tuple:
    """Méthode intégrale : efforts intégrés depuis s = L (valeurs nulles en L+), sauts aux actions ponctuelles.

    Entrées : `br` (points de rupture, m), `tol` (m), `act` (sortie de _actions), `dl` (sortie de _prepDist), `D`
    (degré maximal), `useSym` (vrai : chemin SymPy, donne le même résultat ; faux : chemin numérique).
    Sorties : `(C6, closure, methodUsed)` ; C6 = liste des 6 matrices n × (D+3) (N, Ty, Tz, Mt, Mfy, Mfz) ;
    closure = 6 valeurs de fermeture en s = 0- (N, N·m) ; methodUsed = 'symbolique' ou 'numérique'.
    """
    n = len(br) - 1
    W = D + 3
    C6 = [np.zeros((n, W)) for _ in range(6)]
    endv = np.zeros(6)
    for k in range(n - 1, -1, -1):
        sR, sL = br[k + 1], br[k]
        endv = endv + _jumps(act, _FL_ACTIONS, sR, tol)
        acc = {"x": np.zeros(1), "y": np.zeros(1), "z": np.zeros(1)}
        for d in dl:
            if d["a"] <= sL + tol and d["b"] >= sR - tol:
                acc[d["dir"]] = _polyAdd(acc[d["dir"]], d["pg"])
        if useSym:
            rows = _integralRowsSym(endv, acc["x"], acc["y"], acc["z"], sR)
        else:
            rows = _integralRowsNum(endv, acc["x"], acc["y"], acc["z"], sR)
        for c in range(6):
            C6[c][k] = _pad(rows[c], W)
        endv = np.array([np.polyval(r, sL) for r in rows])
    closure = endv + _jumps(act, _FL_ACTIONS, br[0], tol)
    return C6, closure, "symbolique" if useSym else "numérique"


def _methodCheck(Cc: list, Ci: list, br, compScale: list) -> float:
    """Écart relatif maximal entre les efforts par coupures (Cc) et par la méthode intégrale (Ci), 7 points par tronçon.

    Entrées : `Cc`, `Ci` (6 matrices n × w chacune), `br` (m), `compScale` (6 échelles, N ou N·m).
    Sortie : écart (sans dimension, ou absolu si l'échelle est nulle).
    """
    err = 0.0
    for c in range(6):
        dmax = 0.0
        for k in range(len(br) - 1):
            t = np.linspace(br[k], br[k + 1], 7)
            dmax = max(dmax, float(np.max(np.abs(np.polyval(Cc[c][k], t) - np.polyval(Ci[c][k], t)))))
        if compScale[c] > 0:
            err = max(err, dmax / compScale[c])
        elif dmax > 0:
            err = max(err, dmax)
    return err


def _equations(sol: dict, br) -> list[dict]:
    """Équations par tronçon : pour chaque composante, la formule LaTeX (entre $) et le texte.

    Entrées : `sol` (dict dont les 6 composantes sont des PP), `br` (points de rupture, m).
    Sortie : liste de dicts s1, s2 (m), puis par composante C (LaTeX) et C_txt (texte).
    """
    eqs = []
    for k in range(len(br) - 1):
        eq = {"s1": float(br[k]), "s2": float(br[k + 1])}
        for nom, tex in zip(_COMPOSANTES, _TEX_COMPOSANTES, strict=True):
            ck = sol[nom].coefs[k]
            eq[nom] = f"${tex}(s) = {poly2latex(ck)}$"
            eq[nom + "_txt"] = f"{nom}(s) = {poly2str(ck)}"
        eqs.append(eq)
    return eqs


def _appendTerm(s: str, terme: str, neg: bool) -> str:
    """Ajoute un terme signé à une combinaison linéaire en texte (vide au départ).

    Entrées : `s` (combinaison déjà écrite, éventuellement vide), `terme` (texte), `neg` (vrai si le signe est moins).
    """
    if not s:
        return "-" + terme if neg else terme
    return f"{s} - {terme}" if neg else f"{s} + {terme}"


def _linEq(coefs, names: list[str], cst: float, isTex: bool, withZero: bool = True) -> str:
    """Combinaison linéaire « a·X + b·Y + c » en texte ou LaTeX (suivie de « = 0 » si withZero).

    Entrées : `coefs` (tableau), `names` (noms des inconnues, même longueur), `cst` (constante), `isTex`, `withZero`.
    Les termes négligeables (≤ 1e-13 du maximum) sont omis ; sortie "0" si tous le sont.
    """
    coefs = np.asarray(coefs, dtype=float).ravel()
    mx = float(np.max(np.abs(np.append(coefs, cst)), initial=0.0))
    s = ""
    for c, nom in zip(coefs, names, strict=True):
        if c == 0 or abs(c) <= 1e-13 * mx:
            continue
        mag = _texNum(abs(c)) if isTex else _num(abs(c))
        if mag == "1":
            terme = nom
        elif isTex:
            terme = mag + r"\," + nom
        else:
            terme = mag + "·" + nom
        s = _appendTerm(s, terme, c < 0)
    if cst != 0 and abs(cst) > 1e-13 * mx:
        s = _appendTerm(s, _texNum(abs(cst)) if isTex else _num(abs(cst)), cst < 0)
    if not s:
        s = "0"
    return s + " = 0" if withZero else s


def _dofText(type_: str) -> str:
    """Degrés de liberté bloqués d'un type d'appui, en texte du rapport."""
    if type_ in ("appui_simple", "pivot_glissant"):
        return "v, w"
    if type_ in ("rotule", "pivot"):
        return "u, v, w"
    return "u, v, w, θx, θy, θz"


def _joinNums(v) -> str:
    """Nombres séparés par « , » au format du rapport (%.6g)."""
    return ", ".join(_num(float(x)) for x in v)


def _repDonnees(c: dict, rep: list[str], tex: list[str]) -> None:
    """Rapport : données, liaisons, rotules, actions thermiques, charges et points de rupture (ajoutés à rep, tex).

    Entrée : `c` (contexte de _beamReport). Sorties : aucune, rep et tex sont complétés.
    """
    mdl = c["mdl"]
    rep.append(
        f"Données (SI) : L = {_num(mdl['L'])} m ; E = {_num(mdl['E'])} Pa ; G = {_num(mdl['G'])} Pa ; "
        f"S = {_num(mdl['S'])} m² ; Iz = {_num(mdl['Iz'])} m⁴ ; Iy = {_num(mdl['Iy'])} m⁴ ; "
        f"Ix = {_num(mdl['Ix'])} m⁴ ; ky = {_num(mdl['ky'])} ; kz = {_num(mdl['kz'])}"
    )
    rep.extend(f"  Remarque : {note}" for note in c["notes"])
    rep.append(
        "Convention : torseur de cohésion = actions extérieures à DROITE de la section, réduit au centre G(s) ; "
        "réactions = efforts exercés par les appuis sur la poutre (repère global)."
    )
    sup = mdl["supports"]
    if not sup:
        rep.append("Liaisons : aucune.")
    else:
        rep.append("Liaisons :")
        for s in sup:
            rep.append(
                f"  {s['name']} : {s['type'].replace('_', ' ')} en s = {_num(s['pos'])} m "
                f"(ddl bloqués : {_dofText(s['type'])})"
            )
            if s["spring"] > 0:
                rep.append(f"    appui élastique : ressort de raideur k = {_num(s['spring'])} N/m (déplacement = −R/k)")
            if s["dx"] != 0 or s["dy"] != 0 or s["dz"] != 0:
                rep.append(
                    f"    tassement imposé : dx = {_num(s['dx'])} m ; dy = {_num(s['dy'])} m ; dz = {_num(s['dz'])} m"
                )
    for hi in mdl["hinges"]:
        rep.append(
            f"Rotule intermédiaire {hi['name']} en s = {_num(hi['pos'])} m : "
            "Mfy = Mfz = 0 (la rotation y est discontinue)."
        )
    th = mdl["thermal"]
    if th["epsX"] != 0 or th["kv"] != 0 or th["kw"] != 0:
        rep.append(
            f"Action thermique : α·ΔT = {_num(th['epsX'])} (allongement relatif), courbure thermique "
            f"v'' = {_num(th['kv'])} 1/m (plan xy), w'' = {_num(th['kw'])} 1/m (plan xz). "
            "Une dilatation ou une courbure empêchée par les appuis crée des efforts."
        )
    if mdl["pointLoads"]:
        rep.append("Forces ponctuelles :")
        for p in mdl["pointLoads"]:
            rep.append(
                f"  {p['name']} en s = {_num(p['pos'])} m : Fx = {_num(p['Fx'])} N ; "
                f"Fy = {_num(p['Fy'])} N ; Fz = {_num(p['Fz'])} N"
            )
    if mdl["pointMoments"]:
        rep.append("Couples ponctuels :")
        for p in mdl["pointMoments"]:
            rep.append(
                f"  {p['name']} en s = {_num(p['pos'])} m : Mx = {_num(p['Mx'])} N·m ; "
                f"My = {_num(p['My'])} N·m ; Mz = {_num(p['Mz'])} N·m"
            )
    if c["dl"]:
        rep.append("Charges réparties (ξ = s - a, variable locale) :")
        for d in c["dl"]:
            if d["I0"] != 0:
                xr = f" ; résultante {_num(d['I0'])} N appliquée en s = {_num(d['I1'] / d['I0'])} m"
            else:
                xr = f" ; résultante nulle, moment {_num(d['I1'])} N·m"
            dr = d["dir"]
            rep.append(
                f"  {d['name']} : p_{dr}(ξ) = {poly2str(d['coeffs'], 'ξ')} N/m sur "
                f"[{_num(d['a'])} ; {_num(d['b'])}] m, soit p_{dr}(s) = {poly2str(d['pg'])}{xr}"
            )
            xiTex = r"\xi = s" if d["a"] == 0 else r"\xi = s - " + _texNum(d["a"])
            tex.append(
                "$p_{"
                + dr
                + r"}(\xi) = "
                + poly2latex(d["coeffs"], r"\xi")
                + r",\ \ "
                + xiTex
                + r",\ \ \int_{"
                + _texNum(d["a"])
                + "}^{"
                + _texNum(d["b"])
                + "} p_{"
                + dr
                + r"}\,ds = "
                + _texNum(d["I0"])
                + "$"
            )
    rep.append(f"Points de rupture (tronçons) : s = [{_joinNums(c['br'])}] m")


def _repHyper(c: dict, rep: list[str], tex: list[str]) -> None:
    """Rapport : degré d'hyperstatisme des 4 sous-problèmes et total (ajouté à rep et tex)."""
    sps = c["subs"]
    rep.append("--- Degré d'hyperstatisme (4 sous-problèmes indépendants) ---")
    for s in sps:
        nm = ", ".join(u["name"] for u in s["unk"]) if s["nunk"] > 0 else "-"
        extra = ""
        if s["rank"] < s["neq"]:
            if s["nunk"] == 0 and not s["loaded"]:
                extra = " (aucune liaison ni charge : sans objet)"
            else:
                extra = " (liaisons insuffisantes mais chargement équilibré : pas de mécanisme effectif)"
        elif s["h"] > 0 and not s["loaded"]:
            extra = " (non chargé : réactions nulles)"
        rep.append(f"  {s['label']} : {s['nunk']} inconnue(s) [{nm}], {s['neq']} équation(s) -> h = {s['h']}{extra}")
    H = c["h"]
    st = "isostatique" if c["isostatic"] else "hyperstatique"
    rep.append(
        f"  h total = {H['axial']} + {H['xy']} + {H['xz']} + {H['torsion']} = {H['total']} ; "
        f"h plan (x,y) = {sps[0]['nunk']} + {sps[1]['nunk']} - 3 = {H['plan2D']} -> poutre {st}"
    )
    tex.append(
        f"$h = h_{{N}} + h_{{xy}} + h_{{xz}} + h_{{t}} = {H['axial']} + {H['xy']} + {H['xz']} + {H['torsion']} "
        f"= {H['total']}$"
    )
    tex.append(f"$h_{{plan}} = r_{{N}} + r_{{xy}} - 3 = {sps[0]['nunk']} + {sps[1]['nunk']} - 3 = {H['plan2D']}$")


def _repPFS(c: dict, rep: list[str], tex: list[str]) -> None:
    """Rapport : principe fondamental de la statique par sous-problème (équations et réactions, ajoutés à rep, tex)."""
    nameA = c["nameA"]
    texA = _texId(nameA, 0)
    rep.append(
        f"--- Principe fondamental de la statique : résultantes et moments au point {nameA} (s = {_num(c['xA'])} m) ---"
    )
    rep.append(
        f"  Transport des moments : M_{nameA}(F) = M_P(F) + {nameA}P ∧ F avec {nameA}P = (x_P - x_{nameA})·x, "
        f"soit (x_P - x_{nameA})·Fy selon z et -(x_P - x_{nameA})·Fz selon y."
    )
    tex.append(
        r"$\overrightarrow{M}_{"
        + texA
        + r"}(\vec{F}) = \overrightarrow{M}_{P}(\vec{F}) + \overrightarrow{"
        + texA
        + r"P} \wedge \vec{F}$"
    )
    for s in c["subs"]:
        if s["nunk"] == 0 and not s["loaded"]:
            continue
        rep.append(f"  [{s['label']}]")
        if s["loadMoments"]:
            parts = [f"{lm['label']} = {_num(lm['value'])} N·m" for lm in s["loadMoments"]]
            ax = "z" if s["name"] == "xy" else "y"
            rep.append(f"    Moments des charges en {nameA} (selon {ax}) : {' ; '.join(parts)}")
        sg = np.array([u["sgn"] for u in s["unk"]], dtype=float)
        nmT = [u["name"] for u in s["unk"]]
        nmX = [u["tex"] for u in s["unk"]]
        for r in range(s["neq"]):
            coefs = s["rowSign"][r] * s["A"][r] * sg
            cst = s["rowSign"][r] * s["b"][r]
            rep.append(f"    {s['eqTxt'][r]} : {_linEq(coefs, nmT, cst, False)}")
            tex.append("$" + s["eqTex"][r] + r" :\ " + _linEq(coefs, nmX, cst, True) + "$")
        if s["rank"] == s["neq"] and s["h"] == 0:
            parts = []
            for j, u in enumerate(s["unk"]):
                val = u["sgn"] * s["R"][j]
                parts.append(f"{u['name']} = {_num(val)} {u['unit']}")
                tex.append("$" + u["tex"] + " = " + _texNum(val) + r"\ \mathrm{" + u["texUnit"] + "}$")
            rep.append("    => " + " ; ".join(parts))
        elif s["h"] > 0 and s["rank"] == s["neq"]:
            if s["loaded"]:
                rep.append(
                    f"    => {s['neq']} équation(s) pour {s['nunk']} inconnue(s) : hyperstatique d'ordre {s['h']}, "
                    "résolution par Ménabréa / intégration ci-dessous."
                )
            else:
                rep.append(f"    => hyperstatique d'ordre {s['h']} non chargé : toutes les réactions sont nulles.")
        else:
            rep.append(
                "    => liaisons insuffisantes mais chargement compatible (aucun mouvement de mécanisme sollicité)."
            )
            if s["degenerate"]:
                rep.append(
                    "    => liaisons à la fois redondantes et insuffisantes : réactions de norme minimale "
                    "(méthode d'intégration)."
                )


def _repHypRes(c: dict, rep: list[str], tex: list[str]) -> None:
    """Rapport : Ménabréa, méthode d'intégration et écart entre les deux, par sous-problème hyperstatique."""
    for s in c["subs"]:
        men = s["men"]
        if men is not None:
            rep.append(f"--- Théorème de Ménabréa : {s['label']} (h = {s['h']}) ---")
            rep.append(
                f"  Système de base isostatique : réactions conservées [{', '.join(men['base'])}] ; inconnues "
                f"hyperstatiques X = [{', '.join(men['unknowns'])}] (déplacements correspondants nuls)."
            )
            if s["kind"] == "bend":
                msg = (
                    f"  M(s) = M0(s) + Σ Xi·mi(s) ; {s['energyTxt']} ; ∂U/∂Xi = 0 -> Σj δij·Xj = -δi0, "
                    f"δij = ∫ mi·mj/({s['stiffTxt']}) ds"
                )
                if men["includeShear"]:
                    msg += f" + ∫ ti·tj/({s['shearTxt']}) ds"
            else:
                msg = (
                    f"  N(s) = N0(s) + Σ Xi·ni(s) ; {s['energyTxt']} ; ∂U/∂Xi = 0 -> Σj δij·Xj = -δi0, "
                    f"δij = ∫ ni·nj/({s['stiffTxt']}) ds"
                )
            rep.append(msg)
            tex.append(
                r"$\frac{\partial U}{\partial X_{i}} = 0 \Rightarrow \sum_{j} \delta_{ij}\,X_{j} = -\delta_{i0}$"
            )
            tex.append(s["energyTex"])
            hX = len(men["X"])
            xn = [f"X_{{{i}}}" for i in range(1, hX + 1)]
            for i in range(hX):
                rep.append(f"  Ligne {i + 1} : δ = [{_joinNums(men['delta'][i])}] ; -δ{i + 1}0 = {_num(men['rhs'][i])}")
                tex.append("$" + _linEq(men["delta"][i], xn, 0.0, True, False) + " = " + _texNum(men["rhs"][i]) + "$")
            parts = []
            for i in range(hX):
                xi = men["sgn"][i] * men["X"][i]
                parts.append(f"X{i + 1} = {men['unknowns'][i]} = {_num(xi)}")
                tex.append(f"$X_{{{i + 1}}} = " + men["unknownsTex"][i] + " = " + _texNum(xi) + "$")
            rep.append("  Solution : " + " ; ".join(parts))
        it = s["int"]
        if it is not None:
            rep.append(f"--- Méthode d'intégration : {s['label']} ---")
            rep.append("  " + s["intTxt"])
            tex.append(s["intTex"])
            rep.append(f"  Inconnues ({len(it['unknowns'])}) : {', '.join(it['unknowns'])}")
            rep.append(f"  Équations : {s['neq']} d'équilibre + conditions cinématiques {', '.join(it['conditions'])}")
            parts = []
            for i, valeur in enumerate(it["solution"]):
                nmi = it["unknowns"][i]
                if " =" in nmi:
                    nmi = nmi[: nmi.index(" =")]
                sg = s["unk"][i]["sgn"] if i < len(s["unk"]) else 1
                parts.append(f"{nmi} = {_num(sg * valeur)}")
            rep.append("  Solution : " + " ; ".join(parts))
        if not math.isnan(s["hyperCheck"]):
            rep.append(f"  Écart relatif maximal Ménabréa / intégration ({s['label']}) : {s['hyperCheck']:.3g}")


def _repReactions(c: dict, rep: list[str]) -> None:
    """Rapport : réactions des appuis (efforts exercés par les appuis sur la poutre, repère global)."""
    rep.append("--- Réactions (efforts exercés par les appuis sur la poutre, repère global) ---")
    if not c["reactions"]:
        rep.append("  aucune liaison.")
    for r in c["reactions"]:
        rep.append(
            f"  {r['name']} ({r['type'].replace('_', ' ')}, s = {_num(r['pos'])} m) : Rx = {_num(r['Rx'])} N ; "
            f"Ry = {_num(r['Ry'])} N ; Rz = {_num(r['Rz'])} N ; Mx = {_num(r['Mx'])} N·m ; "
            f"My = {_num(r['My'])} N·m ; Mz = {_num(r['Mz'])} N·m"
        )


def _repCohesion(c: dict, rep: list[str], tex: list[str]) -> None:
    """Rapport : torseur de cohésion (coupures et intégrale), équations par tronçon et contrôle des deux méthodes."""
    if c["doCut"]:
        rep.append("--- Torseur de cohésion : méthode des coupures (somme des actions à droite) ---")
        rep.append(
            "  N(s) = Σdroite Fx + ∫_s^L px dx ; Ty(s) = Σdroite Fy + ∫_s^L py dx ; "
            "Tz(s) = Σdroite Fz + ∫_s^L pz dx ; Mt(s) = Σdroite Mx"
        )
        rep.append(
            "  Mfz(s) = Σdroite [(xi - s)·Fyi + Czi] + ∫_s^L (x - s)·py dx ; "
            "Mfy(s) = Σdroite [-(xi - s)·Fzi + Cyi] - ∫_s^L (x - s)·pz dx"
        )
        tex.append(
            r"$N(s) = \sum_{droite} F_{xi} + \int_{s}^{L} p_x\,dx,\ \ "
            r"T_y(s) = \sum_{droite} F_{yi} + \int_{s}^{L} p_y\,dx$"
        )
        tex.append(
            r"$M_{fz}(s) = \sum_{droite} \left[ (x_i - s)\,F_{yi} + C_{zi} \right] + \int_{s}^{L} (x - s)\,p_y\,dx$"
        )
        tex.append(
            r"$M_{fy}(s) = \sum_{droite} \left[ -(x_i - s)\,F_{zi} + C_{yi} \right] - \int_{s}^{L} (x - s)\,p_z\,dx$"
        )
    else:
        rep.append("--- Torseur de cohésion (méthode intégrale uniquement) ---")
    for k, e in enumerate(c["eqs"], start=1):
        rep.append(f"  Tronçon {k} : s ∈ [{_num(e['s1'])} ; {_num(e['s2'])}] m")
        nz = 0
        for nom in _COMPOSANTES:
            txt = e[nom + "_txt"]
            if not txt.endswith("= 0"):
                rep.append("    " + txt)
                nz += 1
        if nz == 0:
            rep.append("    toutes les composantes sont nulles")
    if c["doIntg"]:
        rep.append(
            f"--- Méthode intégrale ({c['methodUsed']}) : intégration depuis s = L (valeurs nulles en L+), "
            "sauts aux actions ponctuelles ---"
        )
        rep.append(
            "  dN/ds = -px ; dTy/ds = -py (= q) ; dTz/ds = -pz ; dMfz/ds = -Ty ; dMfy/ds = Tz ; "
            "Ty(a-) = Ty(a+) + Fy ; Mfz(a-) = Mfz(a+) + Cz ; Mfy(a-) = Mfy(a+) + Cy"
        )
        tex.append(
            r"$\frac{dN}{ds} = -p_x,\ \ \frac{dT_y}{ds} = -p_y,\ \ T_y = -\frac{dM_{fz}}{ds},\ \ "
            r"T_z = \frac{dM_{fy}}{ds}$"
        )
        tex.append(r"$T_y(s) = T_y(b^{-}) + \int_{s}^{b} p_y\,dx,\ \ M_{fz}(s) = M_{fz}(b^{-}) + \int_{s}^{b} T_y\,dx$")
        cl = c["closure"]
        rep.append(
            "  Fermeture en s = 0- (équilibre global, doit être nulle) : "
            f"N = {_num(cl[0])} ; Ty = {_num(cl[1])} ; Tz = {_num(cl[2])} ; "
            f"Mt = {_num(cl[3])} ; Mfy = {_num(cl[4])} ; Mfz = {_num(cl[5])}"
        )
        if not math.isnan(c["methodCheck"]):
            rep.append(f"  Écart relatif maximal coupures / intégrale : {c['methodCheck']:.3g}")


def _repExtrema(c: dict, rep: list[str], tex: list[str]) -> None:
    """Rapport : extrema des 6 composantes d'efforts (texte et LaTeX)."""
    rep.append("--- Extrema des efforts intérieurs ---")
    unites = ("N", "N", "N", "N·m", "N·m", "N·m")
    unitesTex = ("N", "N", "N", r"N\,m", r"N\,m", r"N\,m")
    base = ("N_{", "T_{y,", "T_{z,", "M_{t,", "M_{fy,", "M_{fz,")
    for nom, u, ut, b in zip(_COMPOSANTES, unites, unitesTex, base, strict=True):
        e = c["extrema"][nom]
        rep.append(
            f"  {nom} : max = {_num(e['max'])} {u} en s = {_num(e['sMax'])} m ; "
            f"min = {_num(e['min'])} {u} en s = {_num(e['sMin'])} m"
        )
        if e["max"] != 0 or e["min"] != 0:
            tex.append(
                "$"
                + b
                + r"max} = "
                + _texNum(e["max"])
                + r"\ \mathrm{"
                + ut
                + r"}\ (s = "
                + _texNum(e["sMax"])
                + r"\ \mathrm{m}),\ \ "
                + b
                + "min} = "
                + _texNum(e["min"])
                + r"\ \mathrm{"
                + ut
                + r"}\ (s = "
                + _texNum(e["sMin"])
                + r"\ \mathrm{m})$"
            )


def _beamReport(c: dict) -> tuple[list[str], list[str]]:
    """Rapport détaillé (texte, en français) et formules clés (LaTeX) de solveBeam ; port de btsBeamReport.

    Entrée : `c` (contexte de solveBeam : mdl, notes, br, subs, h, xA, nameA, isostatic, reactions, dl, doCut, doIntg,
    methodUsed, methodCheck, closure, eqs, extrema).
    Sorties : `(report, latex)`, deux listes de chaînes ; les chaînes LaTeX sont entre $ et sans caractère non ASCII.
    """
    rep = ["=== Poutre droite : résolution statique (BeamAndTrussSolver.solveBeam) ==="]
    tex = [r"$\{T_{coh}\}_{G} = \{T_{ext,\,droite}\}_{G} = -\{T_{ext,\,gauche}\}_{G}$"]
    _repDonnees(c, rep, tex)
    _repHyper(c, rep, tex)
    _repPFS(c, rep, tex)
    _repHypRes(c, rep, tex)
    _repReactions(c, rep)
    _repCohesion(c, rep, tex)
    _repExtrema(c, rep, tex)
    return rep, tex


def solveBeam(model: dict, opts: dict | None = None) -> dict:
    """Résout une poutre : réactions, degré d'hyperstatisme et efforts intérieurs (ARCHITECTURE §3).

    Entrées : `model` (dict, SI : m, Pa, m², m⁴, N, N·m) ; `opts` (dict facultatif) : internalMethod
    ('both', 'coupures', 'integrale'), hyperMethod ('both', 'menabrea', 'integration'), useSymbolic, includeShearEnergy.
    useSymbolic vaut faux par défaut : la méthode intégrale est alors numérique (np.polyint), plus rapide, avec le même
    résultat que le chemin SymPy, qui n'est utilisé que si useSymbolic est vrai et que SymPy est installé.
    Sortie : dict `sol` : model, h, isostatic, reactions (liste de dicts name, pos, type, Rx, Ry, Rz, Mx, My, Mz,
    en N et N·m), breaks, N, Ty, Tz, Mt, Mfy, Mfz (PP : coupures, ou méthode intégrale si internalMethod = 'integrale'),
    internalIntegral (6 PP, methodUsed, closure ; {} si non calculée), methodCheck (écart des deux méthodes, NaN si
    une seule), equations (une entrée par tronçon), extrema, menabrea, reactionsMenabrea, reactionsIntegration,
    hyperCheck, integration, methodUsed, report, latex.
    Erreurs : MecaStruct:Beam:invalidModel, invalidSupport, invalidOption, mechanism.
    """
    o = _beamOpts(opts)
    mdl, notes = _normalizeModel(model)
    L = mdl["L"]
    sup = mdl["supports"]
    dl = _prepDist(mdl["distLoads"])
    D = max(d["deg"] for d in dl) + 2 if dl else 1
    br = _mergeBreaks(
        np.concatenate(
            [
                [0.0, L],
                _vec(sup, "pos"),
                _vec(mdl["pointLoads"], "pos"),
                _vec(mdl["pointMoments"], "pos"),
                _vec(dl, "a"),
                _vec(dl, "b"),
                _vec(mdl["hinges"], "pos"),
            ]
        )
    )
    br[0], br[-1] = 0.0, L
    tol = _tol(br)
    Gq = _gaussData(br, D + 1, D)
    xA, nameA = (sup[0]["pos"], sup[0]["name"]) if sup else (0.0, "O")

    # --- 4 sous-problèmes indépendants
    sps = [_solveSub(sp, br, tol, D, Gq, o, L, xA) for sp in _buildSubs(mdl, dl, nameA)]

    # --- degré d'hyperstatisme
    h = {"axial": sps[0]["h"], "xy": sps[1]["h"], "xz": sps[2]["h"], "torsion": sps[3]["h"]}
    h["total"] = sum(h.values())
    h["plan2D"] = sps[0]["nunk"] + sps[1]["nunk"] - 3
    isostatic = h["total"] == 0

    # --- réactions
    reactions = _reactionStruct(sup)
    reacMen = copy.deepcopy(reactions)
    reacInt = copy.deepcopy(reactions)
    for s in sps:
        for j, u in enumerate(s["unk"]):
            reactions[u["sup"]][u["field"]] = float(u["sgn"] * s["R"][j] + 0.0)
            if not isostatic:
                vm = s["R"][j] if s["Rmen"] is None else s["Rmen"][j]
                vi = s["R"][j] if s["Rint"] is None else s["Rint"][j]
                reacMen[u["sup"]][u["field"]] = float(u["sgn"] * vm + 0.0)
                reacInt[u["sup"]][u["field"]] = float(u["sgn"] * vi + 0.0)
    reacMen = reacMen if o["hyperMethod"] in ("both", "menabrea") else []
    reacInt = reacInt if o["hyperMethod"] in ("both", "integration") else []

    # --- échelles (nettoyage et comparaison)
    scaleF = max(s["scaleEq"][0] for s in sps)
    scaleC = max([s["scaleEq"][1] for s in sps if len(s["scaleEq"]) > 1] + [0.0, float(np.sum(np.abs(sps[3]["fv"])))])

    # --- torseur de cohésion par coupures (superposition des actions à droite)
    Cc = [sps[0]["T"], sps[1]["T"], sps[2]["T"], sps[3]["T"], -sps[2]["M"], sps[1]["M"]]
    maxF = max([_matMaxAbs(C, br) for C in Cc[:3]] + [scaleF])
    maxM = max([_matMaxAbs(C, br) for C in Cc[3:]] + [maxF * L, scaleC])
    compScale = [maxF] * 3 + [maxM] * 3
    doCut = o["internalMethod"] in ("both", "coupures")
    doIntg = o["internalMethod"] in ("both", "integrale")

    # --- méthode intégrale (internalIntegral, contrôle des coupures)
    methodCheck = math.nan
    internalIntegral: dict = {}
    closure = None
    methodUsed = "numérique"
    if doIntg:
        act = _actions(mdl, reactions)
        Ci, closure, methodUsed = _integralMethod(br, tol, act, dl, D, o["useSymbolic"])
        if doCut:
            methodCheck = _methodCheck(Cc, Ci, br, compScale)
        for c, nom in enumerate(_COMPOSANTES):
            internalIntegral[nom] = _matToPP(_cleanMat(Ci[c], br, 1e-12 * compScale[c]), br)
        internalIntegral["methodUsed"] = methodUsed
        internalIntegral["closure"] = closure

    # --- pp principaux : coupures, ou méthode intégrale seule (internalMethod = 'integrale')
    sol = {"model": mdl, "h": h, "isostatic": isostatic, "reactions": reactions, "breaks": br}
    for c, nom in enumerate(_COMPOSANTES):
        sol[nom] = _matToPP(_cleanMat(Cc[c], br, 1e-12 * compScale[c]), br) if doCut else internalIntegral[nom]
    sol["internalIntegral"] = internalIntegral
    sol["methodCheck"] = methodCheck
    sol["equations"] = _equations(sol, br)
    sol["extrema"] = {nom: _extrema(sol[nom]) for nom in _COMPOSANTES}

    # --- Ménabréa / intégration
    sol["menabrea"] = {s["name"]: s["men"] for s in sps if s["men"] is not None}
    sol["integration"] = {s["name"]: s["int"] for s in sps if s["int"] is not None}
    checks = [s["hyperCheck"] for s in sps if not math.isnan(s["hyperCheck"])]
    sol["hyperCheck"] = max(checks) if checks else math.nan
    sol["reactionsMenabrea"] = [] if isostatic else reacMen
    sol["reactionsIntegration"] = [] if isostatic else reacInt
    sol["methodUsed"] = methodUsed if doIntg else "coupures"

    # --- rapport
    ctx = {
        "mdl": mdl,
        "notes": notes,
        "br": br,
        "subs": sps,
        "h": h,
        "xA": xA,
        "nameA": nameA,
        "isostatic": isostatic,
        "reactions": reactions,
        "dl": dl,
        "doCut": doCut,
        "doIntg": doIntg,
        "methodUsed": methodUsed,
        "methodCheck": methodCheck,
        "closure": closure,
        "eqs": sol["equations"],
        "extrema": sol["extrema"],
    }
    sol["report"], sol["latex"] = _beamReport(ctx)
    return sol
