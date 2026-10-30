"""Treillis articulé 2D ou 3D : méthode des nœuds (isostatique) et méthode des rigidités (port de btsSolveTruss,
ARCHITECTURE §3 « Treillis »).

Les numéros de nœuds et de barres montrés à l'utilisateur (`bars`, colonne `Barre`, noms) partent de 1 comme en MATLAB ;
les tableaux par nœud ou par barre sont indexés à partir de 0.
"""

import numpy as np
import pandas as pd

from mecastruct.core.beam_solver import _joinNums, _linEq
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import _num, _texNum

_ID_MODEL = "MecaStruct:Truss:invalidModel"
_ID_MECANISME = "MecaStruct:Truss:mechanism"
_AX = "xyz"


def _absent(v) -> bool:
    """Vrai si une entrée est absente ou vide (isempty de MATLAB) : None, liste vide, tableau vide.

    Entrée : `v` (valeur quelconque du modèle). Sortie : bool.
    """
    return v is None or np.size(v) == 0


def _prop(truss: dict, f: str, m: int, defaut: float) -> np.ndarray:
    """Propriété par barre `f` (E en Pa ou S en m²) : scalaire ou m valeurs > 0, `defaut` si absente.

    Entrées : `truss` (dict), `f` (nom du champ), `m` (nombre de barres), `defaut` (SI).
    Sortie : tableau de m réels.
    Erreur : MecaStruct:Truss:invalidModel si la taille ou une valeur est incorrecte.
    """
    if _absent(truss.get(f)):
        return np.full(m, defaut)
    v = np.asarray(truss[f], dtype=float).reshape(-1)
    if v.size == 1:
        v = np.full(m, v[0])
    if v.size != m or not np.all(np.isfinite(v)) or np.any(v <= 0):
        raise MecaStructError(_ID_MODEL, f"truss.{f} doit être un scalaire ou un vecteur {m}×1 strictement positif.")
    return v


def _noms(truss: dict, n: int) -> list[str]:
    """Noms des nœuds `truss.names` (n textes non vides), sinon A, B, C… (N1, N2… au-delà de 26 nœuds).

    Entrées : `truss` (dict), `n` (nombre de nœuds). Sortie : list[str] de longueur n.
    """
    nm = truss.get("names")
    if isinstance(nm, list | tuple) and len(nm) == n and all(isinstance(x, str) and x for x in nm):
        return list(nm)
    return [chr(ord("A") + i) if n <= 26 else f"N{i + 1}" for i in range(n)]


def solveTruss(truss: dict) -> dict:
    """Résout un treillis articulé 2D ou 3D : méthode des nœuds si isostatique, sinon méthode des rigidités.

    Entrées SI : `truss` avec `nodes` (n×dim, m), `bars` (m×2, numéros de nœuds à partir de 1), `E` et `S`
    (scalaires ou m valeurs, Pa et m²), `supports` (n×dim, True = ddl bloqué), `loads` (n×dim, N, facultatif) et
    `names` (n textes, facultatif).
    Sorties : dict avec dim, h, isostatic, mechanism, L0 (m), N (N), nature, sigma (Pa), dL (m), reactions (N),
    displacements (m), Njoints, Nstiffness, A, methodUsed, table (DataFrame), rank, ecartMethodes, names, report, latex.
    Erreurs : MecaStruct:Truss:invalidModel si le modèle est incorrect ; MecaStruct:Truss:mechanism si le treillis
    est un mécanisme incompatible avec le chargement.
    """
    if not isinstance(truss, dict):
        raise MecaStructError(_ID_MODEL, "Le treillis doit être une structure scalaire.")
    for f in ("nodes", "bars", "supports"):
        if _absent(truss.get(f)):
            raise MecaStructError(_ID_MODEL, f"Champ truss.{f} manquant ou vide.")
    nodes = np.asarray(truss["nodes"], dtype=float)
    if nodes.ndim != 2 or nodes.shape[1] not in (2, 3) or not np.all(np.isfinite(nodes)):
        raise MecaStructError(_ID_MODEL, "truss.nodes doit être une matrice n×2 ou n×3 de coordonnées finies (m).")
    n, dim = nodes.shape
    bars = np.asarray(truss["bars"], dtype=float)
    if (
        bars.ndim != 2
        or bars.shape[1] != 2
        or np.any(bars != np.round(bars))
        or np.any(bars < 1)
        or np.any(bars > n)
        or np.any(bars[:, 0] == bars[:, 1])
    ):
        raise MecaStructError(_ID_MODEL, f"truss.bars doit être une matrice m×2 d'indices de nœuds distincts (1..{n}).")
    b0 = bars.astype(int) - 1
    m = len(b0)
    E = _prop(truss, "E", m, 210e9)
    S = _prop(truss, "S", m, 1e-4)
    notes = []
    if _absent(truss.get("E")):
        notes.append("E non fourni : 210 GPa par défaut (sans effet sur N si isostatique).")
    if _absent(truss.get("S")):
        notes.append("S non fourni : 1e-4 m² par défaut (sans effet sur N si isostatique).")
    sups = np.asarray(truss["supports"])
    if sups.shape != (n, dim) or sups.dtype.kind not in "biuf":
        raise MecaStructError(_ID_MODEL, f"truss.supports doit être une matrice logique {n}×{dim}.")
    sups = sups.astype(bool)
    if _absent(truss.get("loads")):
        loads = np.zeros((n, dim))
    else:
        loads = np.asarray(truss["loads"], dtype=float)
        if loads.shape != (n, dim) or not np.all(np.isfinite(loads)):
            raise MecaStructError(_ID_MODEL, f"truss.loads doit être une matrice {n}×{dim} de forces finies (N).")
    names = _noms(truss, n)

    # géométrie
    dX = nodes[b0[:, 1]] - nodes[b0[:, 0]]
    L0 = np.sqrt(np.sum(dX**2, axis=1))
    if np.any(L0 <= 1e-12 * max(1.0, np.abs(nodes).max())):
        raise MecaStructError(_ID_MODEL, "Barre de longueur nulle (nœuds confondus).")
    e = dX / L0[:, None]

    # méthode des nœuds : [A]{N, R} = {-F}
    r = int(sups.sum())
    h = m + r - dim * n
    nd = dim * n
    A = np.zeros((nd, m + r))
    for b, (i, j) in enumerate(b0):
        A[i * dim : (i + 1) * dim, b] += e[b]
        A[j * dim : (j + 1) * dim, b] -= e[b]
    blocked = np.flatnonzero(sups)
    for k, idx in enumerate(blocked):
        A[idx, m + k] = 1.0
    Fv = loads.reshape(-1)
    rankA = int(np.linalg.matrix_rank(A))
    mechanism = rankA < nd
    scaleF = float(np.max(np.abs(Fv)))
    if mechanism:
        z = np.linalg.lstsq(A, -Fv, rcond=None)[0]
        if np.max(np.abs(A @ z + Fv)) > 1e-9 * scaleF:
            raise MecaStructError(
                _ID_MECANISME,
                f"Mécanisme : rang([A]) = {rankA} < {nd} équations (h = m + r - {dim}·n = {h}) ; le treillis ne "
                "peut pas équilibrer le chargement appliqué.",
            )
    isostatic = h == 0 and not mechanism
    Njoints = np.zeros(0)
    if isostatic:
        z = np.linalg.solve(A, -Fv)
        Njoints, Rj = z[:m], z[m:]

    # méthode des rigidités
    kb = E * S / L0
    K = np.zeros((nd, nd))
    for b, (i, j) in enumerate(b0):
        ke = kb[b] * np.outer(e[b], e[b])
        di = slice(i * dim, (i + 1) * dim)
        dj = slice(j * dim, (j + 1) * dim)
        K[di, di] += ke
        K[dj, dj] += ke
        K[di, dj] -= ke
        K[dj, di] -= ke
    free = np.ones(nd, dtype=bool)
    free[blocked] = False
    u = np.zeros(nd)
    if np.any(free):
        Kff = K[np.ix_(free, free)]
        if mechanism or np.linalg.cond(Kff) > 1e14:  # équivalent de rcond(Kff) < 1e-14
            u[free] = np.linalg.lstsq(Kff, Fv[free], rcond=None)[0]
        else:
            u[free] = np.linalg.solve(Kff, Fv[free])
    U = u.reshape(n, dim)
    Nst = kb * np.sum(e * (U[b0[:, 1]] - U[b0[:, 0]]), axis=1)
    Rfull = K @ u - Fv
    Rfull[free] = 0.0
    reactions = Rfull.reshape(n, dim)

    if isostatic:
        N = Njoints
        reacJ = np.zeros(nd)
        reacJ[blocked] = Rj
        reactions = reacJ.reshape(n, dim)
        methodUsed = "méthode des nœuds (vérifiée par la méthode des rigidités)"
    else:
        N = Nst
        methodUsed = "méthode des rigidités"
    scaleN = max(float(np.max(np.abs(N))), scaleF)
    N = np.where(np.abs(N) <= 1e-13 * scaleN, 0.0, N)
    reactions = np.where(np.abs(reactions) <= 1e-13 * max(scaleN, 1e-300), 0.0, reactions)
    thr = 1e-9 * np.max(np.abs(N))
    nature = ["Traction" if x > thr else "Compression" if x < -thr else "Nul" for x in N]
    sigma = N / S
    dL = N * L0 / (E * S)

    ecart = np.nan
    if isostatic:
        ecart = np.max(np.abs(Njoints - Nst)) / max(np.max(np.abs(Njoints)), scaleF, 1e-300)

    tbl = pd.DataFrame(
        {
            "Barre": np.arange(1, m + 1),
            "Noeuds": [f"{names[i]}-{names[j]}" for i, j in b0],
            "L_m": L0,
            "N_N": N,
            "Nature": nature,
            "Sigma_Pa": sigma,
            "dL_m": dL,
        }
    )
    res = {
        "dim": dim,
        "h": h,
        "isostatic": isostatic,
        "mechanism": mechanism,
        "L0": L0,
        "N": N,
        "nature": nature,
        "sigma": sigma,
        "dL": dL,
        "reactions": reactions,
        "displacements": U,
        "Njoints": Njoints,
        "Nstiffness": Nst,
        "A": A,
        "methodUsed": methodUsed,
        "table": tbl,
        "rank": rankA,
        "ecartMethodes": ecart,
        "names": names,
    }
    res["report"], res["latex"] = _rapport(res, nodes, b0, E, S, sups, loads, names, notes, blocked, r)
    return res


def _rapport(t, nodes, bars, E, S, sups, loads, names, notes, blocked, r) -> tuple[list[str], list[str]]:
    """Rapport texte et formules LaTeX du treillis (port de btsTrussReport), à partir des résultats `t` déjà calculés.

    Entrées : `nodes` (n×dim, m), `bars` (m×2, indices à partir de 0), `E` et `S` (m), `sups` (n×dim booléen),
    `loads` (n×dim, N), `names`, `notes` (remarques), `blocked` (ddl bloqués, indices à partir de 0), `r` (nombre
    de ddl bloqués).
    Sorties : (rapport, latex), deux listes de textes.
    """
    dim, n, m = t["dim"], len(names), len(bars)
    rep = [f"=== Treillis articulé {dim}D : {n} nœuds, {m} barres (BeamAndTrussSolver.solveTruss) ==="]
    rep += [f"  Remarque : {x}" for x in notes]
    rep.append("Nœuds (m), ddl bloqués et charges (N) :")
    for i in range(n):
        bl = "".join(_AX[d] for d in range(dim) if sups[i, d]) or "-"
        rep.append(f"  {names[i]} : ({_joinNums(nodes[i])}) ; bloqué : {bl} ; F = ({_joinNums(loads[i])})")
    rep.append("Barres :")
    for b, (i, j) in enumerate(bars):
        rep.append(
            f"  Barre {b + 1} : {names[i]}-{names[j]}, L = {_num(t['L0'][b])} m, E = {_num(E[b])} Pa, "
            f"S = {_num(S[b])} m²"
        )
    h, rang = t["h"], t["rank"]
    rep.append(
        f"Degré d'hyperstatisme : h = m + r - {dim}·n = {m} + {r} - {dim}·{n} = {h} ; rang([A]) = {rang} / {dim * n}"
    )
    tex = [rf"$h = m + r - {dim}\,n = {m} + {r} - {dim} \cdot {n} = {h}$"]
    if t["mechanism"]:
        rep.append("  ATTENTION : mécanisme (rang insuffisant) ; chargement compatible, solution de norme minimale.")
    elif t["isostatic"]:
        rep.append("  Treillis isostatique (strictement indéformable).")
    else:
        rep.append(f"  Treillis hyperstatique d'ordre {h} : méthode des rigidités nécessaire.")

    # méthode des nœuds
    rep.append("--- Méthode des nœuds : équilibre de chaque nœud, Σ F = 0, sous forme [A]{N, R} = {-F} ---")
    rep.append(
        "  Convention : N > 0 traction ; une barre tendue tire le nœud vers l'autre extrémité (vecteur unitaire e_ij)."
    )
    tex.append(
        r"$\sum_{barres} N_{b}\,\vec{e}_{b} + \vec{R}_{i} + \vec{F}_{i} = \vec{0}\ "
        r"\Rightarrow\ [A]\,\{N;R\} = \{-F\}$"
    )
    noms_col = [f"N{b + 1}" for b in range(m)]
    for idx in blocked:
        noeud, d = divmod(int(idx), dim)
        noms_col.append(f"R{_AX[d]}{names[noeud]}")
    if n <= 40:
        for i in range(n):
            for d in range(dim):
                eq = _linEq(t["A"][i * dim + d], noms_col, loads[i, d], False)
                rep.append(f"  Nœud {names[i]}, direction {_AX[d]} : {eq}")
    if t["isostatic"]:
        rep.append("  Système carré inversible : résolution directe (méthode des nœuds).")
        rep.append(f"  Écart relatif méthode des nœuds / méthode des rigidités : {t['ecartMethodes']:.3g}")
    else:
        rep.append("  Système non carré (ou singulier) : la méthode des nœuds seule ne suffit pas.")

    # méthode des rigidités
    rep.append("--- Méthode des rigidités : [K]{u} = {F}, k_b = E·S/L, N_b = k_b·e_b·(u_j - u_i) ---")
    tex.append(
        r"$[K_{b}] = \frac{E_b\,S_b}{L_b} \left[ \begin{array}{cc} \vec{e}\,\vec{e}^{T} & -\vec{e}\,\vec{e}^{T} \\ "
        r"-\vec{e}\,\vec{e}^{T} & \vec{e}\,\vec{e}^{T} \end{array} \right]$"
    )
    tex.append(r"$N_{b} = \frac{E_b\,S_b}{L_b}\,\vec{e}_{b} \cdot \left( \vec{u}_{j} - \vec{u}_{i} \right)$")
    for i in range(n):
        rep.append(f"  Déplacement de {names[i]} : ({_joinNums(t['displacements'][i])}) m")

    # résultats
    rep.append(f"--- Efforts normaux ({t['methodUsed']}) ---")
    N, nature = t["N"], t["nature"]
    for b, (i, j) in enumerate(bars):
        rep.append(
            f"  Barre {b + 1} ({names[i]}-{names[j]}) : N = {_num(N[b])} N ({nature[b]}) ; "
            f"σ = N/S = {_num(t['sigma'][b])} Pa ; ΔL = N·L/(E·S) = {_num(t['dL'][b])} m"
        )
        if b < 40:
            tex.append(
                rf"$N_{{{b + 1}}} = {_texNum(N[b])}\ \mathrm{{N}}\ (\mathrm{{{nature[b]}}}),\ \ "
                rf"\sigma_{{{b + 1}}} = \frac{{N}}{{S}} = {_texNum(t['sigma'][b])}\ \mathrm{{Pa}},\ \ "
                rf"\Delta L_{{{b + 1}}} = \frac{{N\,L}}{{E\,S}} = {_texNum(t['dL'][b])}\ \mathrm{{m}}$"
            )
    rep.append("--- Réactions d'appui (N) ---")
    for i in range(n):
        if sups[i].any():
            rep.append(f"  {names[i]} : R = ({_joinNums(t['reactions'][i])})")
    return rep, tex
