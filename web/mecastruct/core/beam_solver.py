"""Solveur de poutres, port de la partie poutres de BeamAndTrussSolver.m (ARCHITECTURE §3).

Ce fichier contient pour l'instant les aides de base : options, normalisation du modèle, charges réparties,
quadrature de Gauss sur des matrices de coefficients (une ligne par tronçon, ordre polyval) et méthode des coupures.
"""

import copy
import math
import re

import numpy as np

from mecastruct.core.data_manager import hasSymbolic
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import PP, _pad, _segIndex, _shiftPoly
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
    Sortie : dict avec les 4 clés (useSymbolic vaut False si SymPy est absent).
    Erreur : MecaStruct:Beam:invalidOption si une option est inconnue ou mal typée.
    """
    o = {"internalMethod": "both", "hyperMethod": "both", "useSymbolic": None, "includeShearEnergy": False}
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
    o["useSymbolic"] = hasSymbolic() if o["useSymbolic"] is None else (o["useSymbolic"] and hasSymbolic())
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
