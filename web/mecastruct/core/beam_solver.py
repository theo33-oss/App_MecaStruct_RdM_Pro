"""Solveur de poutres, port de la partie poutres de BeamAndTrussSolver.m (ARCHITECTURE §3).

Ce fichier contient les aides de base (options, normalisation du modèle, charges réparties, quadrature de Gauss
sur des matrices de coefficients, une ligne par tronçon, ordre polyval), la méthode des coupures, les 4 sous-problèmes
(axial, flexion xy, flexion xz, torsion), la résolution isostatique et hyperstatique par Ménabréa, et solveBeam.
"""

import copy
import math
import re

import numpy as np

from mecastruct.core.data_manager import hasSymbolic
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import PP, _mergeBreaks, _num, _pad, _segIndex, _shiftPoly, _texNum, _tol
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


def _integration(sp, A, bv, TL, ML, TU, MU, br, o, forceLsq):
    """Méthode d'intégration (btsIntegration) : portée en E09 ; lève NotImplementedError("E09") d'ici là."""
    raise NotImplementedError("E09")


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


def _provisoire_E10() -> tuple[dict, float, list, list, list]:
    """Remplace provisoirement la méthode intégrale des efforts et le rapport (portés en E10, qui supprime ceci).

    Sortie : `(internalIntegral, methodCheck, equations, report, latex)` = `({}, nan, [], [], [])`.
    """
    return {}, math.nan, [], [], []


def solveBeam(model: dict, opts: dict | None = None) -> dict:
    """Résout une poutre : réactions, degré d'hyperstatisme et efforts intérieurs (ARCHITECTURE §3).

    Entrées : `model` (dict, SI : m, Pa, m², m⁴, N, N·m) ; `opts` (dict facultatif) : internalMethod
    ('both', 'coupures', 'integrale'), hyperMethod ('both', 'menabrea', 'integration'), useSymbolic,
    includeShearEnergy.
    Sortie : dict `sol` : model, h, isostatic, reactions (liste de dicts name, pos, type, Rx, Ry, Rz, Mx, My, Mz,
    en N et N·m), breaks, N, Ty, Tz, Mt, Mfy, Mfz (PP), internalIntegral, methodCheck, equations, extrema,
    menabrea, reactionsMenabrea, reactionsIntegration, hyperCheck, integration, methodUsed, report, latex.
    Erreurs : MecaStruct:Beam:invalidModel, invalidSupport, invalidOption, mechanism.
    Limite (E08) : la méthode intégrale, les équations et le rapport ne sont pas encore calculés (E10) ;
    hyperMethod 'integration' ou 'both' lève NotImplementedError("E09") sur une poutre hyperstatique chargée.
    """
    o = _beamOpts(opts)
    mdl, _ = _normalizeModel(model)  # notes « non fourni » : rapport (E10)
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
    compNames = ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]

    internalIntegral, methodCheck, equations, report, latex = _provisoire_E10()
    doIntg = o["internalMethod"] in ("both", "integrale")

    # --- pp principaux (en E08, toujours issus des coupures)
    sol = {"model": mdl, "h": h, "isostatic": isostatic, "reactions": reactions, "breaks": br}
    for name, C, sc in zip(compNames, Cc, compScale, strict=True):
        sol[name] = _matToPP(_cleanMat(C, br, 1e-12 * sc), br)
    sol["internalIntegral"] = internalIntegral
    sol["methodCheck"] = methodCheck
    sol["equations"] = equations
    sol["extrema"] = {name: _extrema(sol[name]) for name in compNames}

    # --- Ménabréa / intégration
    sol["menabrea"] = {s["name"]: s["men"] for s in sps if s["men"] is not None}
    sol["integration"] = {s["name"]: s["int"] for s in sps if s["int"] is not None}
    checks = [s["hyperCheck"] for s in sps if not math.isnan(s["hyperCheck"])]
    sol["hyperCheck"] = max(checks) if checks else math.nan
    sol["reactionsMenabrea"] = [] if isostatic else reacMen
    sol["reactionsIntegration"] = [] if isostatic else reacInt
    sol["methodUsed"] = "numérique" if doIntg else "coupures"
    sol["report"], sol["latex"] = report, latex
    return sol
