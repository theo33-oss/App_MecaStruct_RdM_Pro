"""Ossatures de poutres 3D : méthode des déplacements, éléments d'Euler-Bernoulli à 12 DDL (2 nœuds × 6 DDL).

Moteur sans équivalent MATLAB (aucune interface ici). Unités SI : m, N, Pa, kg/m³. Ordre des DDL d'un nœud :
[ux, uy, uz, θx, θy, θz]. Repère local : x_l de ni vers nj ; pour une poutre horizontale, z_l est vertical et Iy
porte la flexion sous charge verticale (axe fort au sens Eurocode). Attention : le catalogue de profilés
(DataManager.getProfile) suit la convention MATLAB (Iz = axe fort) ; il faut donc y échanger Iy et Iz.
Convention des efforts internes : efforts exercés par la partie s+ sur la partie s- (face de normale +x_l) ;
N > 0 en traction, dMy/ds = Vz, dMz/ds = -Vy, σ = N/A + My·z/Iy - Mz·y/Iz.
"""

import math

import numpy as np

from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import _num, _texNum
from mecastruct.core.utils import is_num

G_PESANTEUR = 9.81  # m/s²
MAX_NOEUDS = 200
MAX_ELEMENTS = 300
DDL = ("ux", "uy", "uz", "θx", "θy", "θz")
_APPUIS = {
    "libre": [False] * 6,
    "encastrement": [True] * 6,
    "rotule": [True] * 3 + [False] * 3,
    "appui_z": [False, False, True, False, False, False],
}
_NPTS = 21
_RCOND_MIN = 1e-12  # conditionnement minimal de la matrice réduite (mise à l'échelle par sa diagonale)
_NUL_ROT = 1e-9  # raideur de rotation nulle, relativement à la plus grande raideur de rotation


class FrameMechanismError(MecaStructError):
    """Structure 3D mobile (matrice de rigidité réduite singulière) : le message dit quels DDL semblent libres."""

    def __init__(self, message: str):
        super().__init__("MecaStruct:Frame3D:mechanism", message)


# ------------------------------------------------------------------ sections


def sectionRond(d: float) -> dict:
    """Caractéristiques d'un rond plein de diamètre `d` (m).

    Sortie : dict A (m²), Iy, Iz (m⁴), J (m⁴, J = 2I), Wy, Wz (m³), Wt (m³, τ = T/Wt).
    """
    d = _reel(d, "Rond plein : d")
    I = math.pi * d**4 / 64
    return {
        "A": math.pi * d**2 / 4,
        "Iy": I,
        "Iz": I,
        "J": 2 * I,
        "Wy": I / (d / 2),
        "Wz": I / (d / 2),
        "Wt": 2 * I / (d / 2),
    }


def sectionTube(D: float, t: float) -> dict:
    """Caractéristiques d'un tube rond de diamètre extérieur `D` et d'épaisseur `t` (m, 0 < t < D/2 ou t = D/2).

    Sortie : dict A (m²), Iy, Iz, J (m⁴), Wy, Wz, Wt (m³).
    """
    D, t = _reel(D, "Tube : D"), _reel(t, "Tube : t")
    if t > D / 2:
        raise ValueError("Tube : l'épaisseur t doit être au plus égale à D/2.")
    d = D - 2 * t
    I = math.pi * (D**4 - d**4) / 64
    return {
        "A": math.pi * (D**2 - d**2) / 4,
        "Iy": I,
        "Iz": I,
        "J": 2 * I,
        "Wy": I / (D / 2),
        "Wz": I / (D / 2),
        "Wt": 2 * I / (D / 2),
    }


def sectionRectangle(b: float, h: float) -> dict:
    """Caractéristiques d'un rectangle plein de largeur `b` (selon y_l) et de hauteur `h` (selon z_l), en m.

    J et Wt suivent Roark (côtés complets, a = grand côté, c = petit côté, r = c/a) :
    J = a·c³·[1/3 − 0,21·r·(1 − r⁴/12)] et τmax = T/Wt avec Wt = a·c²/(3·[1 + 0,6095 r + 0,8865 r² − 1,8023 r³
    + 0,9100 r⁴]). Sortie : dict A (m²), Iy = b·h³/12, Iz = h·b³/12, J (m⁴), Wy = b·h²/6, Wz = h·b²/6, Wt (m³).
    """
    b, h = _reel(b, "Rectangle : b"), _reel(h, "Rectangle : h")
    a, c = max(b, h), min(b, h)
    r = c / a
    J = a * c**3 * (1 / 3 - 0.21 * r * (1 - r**4 / 12))
    Wt = a * c**2 / (3 * (1 + 0.6095 * r + 0.8865 * r**2 - 1.8023 * r**3 + 0.9100 * r**4))
    return {
        "A": b * h,
        "Iy": b * h**3 / 12,
        "Iz": h * b**3 / 12,
        "J": J,
        "Wy": b * h**2 / 6,
        "Wz": h * b**2 / 6,
        "Wt": Wt,
    }


def _section(sec, quoi: str) -> dict:
    """Caractéristiques d'une section décrite par un dict {type: rond|tube|rectangle, d | D, t | b, h}."""
    if not isinstance(sec, dict):
        raise ValueError(f"{quoi} : la section doit être un dictionnaire.")
    t = sec.get("type")
    if t == "rond":
        return sectionRond(sec.get("d"))
    if t == "tube":
        return sectionTube(sec.get("D"), sec.get("t"))
    if t == "rectangle":
        return sectionRectangle(sec.get("b"), sec.get("h"))
    raise ValueError(f"{quoi} : type de section « {t} » inconnu (attendu : rond, tube, rectangle).")


# ------------------------------------------------------------------ contrôle des entrées


def _reel(v, quoi: str, nul_ok: bool = False, signe: bool = True) -> float:
    """Réel fini ; strictement positif (ou positif ou nul si `nul_ok`) quand `signe` est vrai. Sinon ValueError."""
    if not is_num(v) or not math.isfinite(v):
        raise ValueError(f"{quoi} : nombre réel fini attendu (reçu : {v!r}).")
    v = float(v)
    if signe and (v < 0 or (v == 0 and not nul_ok)):
        raise ValueError(f"{quoi} doit être {'positif ou nul' if nul_ok else 'strictement positif'} (reçu : {v:g}).")
    return v


def _liste(data: dict, cle: str) -> list:
    """Liste data[cle] (absente ou None donne [])."""
    v = data.get(cle)
    if v is None:
        return []
    if not isinstance(v, list | tuple):
        raise ValueError(f"« {cle} » doit être une liste.")
    return list(v)


def _appui(a, quoi: str) -> list[bool]:
    """6 booléens [ux, uy, uz, θx, θy, θz] (vrai = bloqué) à partir du type d'appui ou d'une liste « perso »."""
    if isinstance(a, str) and a in _APPUIS:
        return list(_APPUIS[a])
    if isinstance(a, list | tuple) and len(a) == 6 and all(isinstance(x, bool | np.bool_) for x in a):
        return [bool(x) for x in a]
    if isinstance(a, dict) and a.get("type") == "perso":
        return _appui(a.get("ddl"), quoi)
    raise ValueError(
        f"{quoi} : appui invalide (attendu : libre, encastrement, rotule, appui_z, ou « perso » donné par "
        "6 booléens [ux, uy, uz, rx, ry, rz])."
    )


def _lire(data: dict) -> dict:
    """Modèle contrôlé et normalisé (positions, appuis, propriétés, charges), ou ValueError en français."""
    if not isinstance(data, dict):
        raise ValueError("Les données de l'ossature doivent être un dictionnaire.")
    noeuds, elements = _liste(data, "noeuds"), _liste(data, "elements")
    if not noeuds or not elements:
        raise ValueError("Il faut au moins un nœud et un élément.")
    if len(noeuds) > MAX_NOEUDS:
        raise ValueError(f"Trop de nœuds : {len(noeuds)} (au plus {MAX_NOEUDS}).")
    if len(elements) > MAX_ELEMENTS:
        raise ValueError(f"Trop d'éléments : {len(elements)} (au plus {MAX_ELEMENTS}).")

    ids, xyz, bloque = [], [], []
    for k, n in enumerate(noeuds, start=1):
        if not isinstance(n, dict) or "id" not in n:
            raise ValueError(f"Nœud n°{k} : dictionnaire avec un champ « id » attendu.")
        if n["id"] in ids:
            raise ValueError(f"Identifiant de nœud en double : {n['id']!r}.")
        ids.append(n["id"])
        xyz.append([_reel(n.get(c), f"Nœud {n['id']!r} : {c}", signe=False) for c in "xyz"])
        a = n.get("appui", "libre")
        bloque.append(_appui(n.get("ddl") if a == "perso" else a, f"Nœud {n['id']!r}"))
    index = {i: k for k, i in enumerate(ids)}
    xyz = np.array(xyz)

    els, eids = [], []
    for k, e in enumerate(elements, start=1):
        if not isinstance(e, dict) or "id" not in e:
            raise ValueError(f"Élément n°{k} : dictionnaire avec un champ « id » attendu.")
        nom = f"Élément {e['id']!r}"
        if e["id"] in eids:
            raise ValueError(f"Identifiant d'élément en double : {e['id']!r}.")
        eids.append(e["id"])
        for c in ("ni", "nj"):
            if e.get(c) not in index:
                raise ValueError(f"{nom} : le nœud {c} = {e.get(c)!r} n'existe pas.")
        i, j = index[e["ni"]], index[e["nj"]]
        L = float(np.linalg.norm(xyz[j] - xyz[i]))
        if L <= 1e-12 * max(1.0, float(np.abs(xyz).max())):
            raise ValueError(f"{nom} : longueur nulle (les nœuds {e['ni']!r} et {e['nj']!r} sont confondus).")
        p = {"id": e["id"], "i": i, "j": j, "L": L}
        calc = _section(e["section"], nom) if e.get("section") is not None else {}
        for c in ("E", "G", "A", "Iy", "Iz", "J"):
            p[c] = _reel(e.get(c) if e.get(c) is not None else calc.get(c), f"{nom} : {c}")
        p["rho"] = _reel(e.get("rho", 0.0) if e.get("rho") is not None else 0.0, f"{nom} : rho", nul_ok=True)
        for c in ("Wy", "Wz", "Wt"):
            v = e.get(c) if e.get(c) is not None else calc.get(c)
            p[c] = None if v is None else _reel(v, f"{nom} : {c}")
        p["beta"] = math.radians(_reel(e.get("beta_deg", 0.0) or 0.0, f"{nom} : beta_deg", signe=False))
        for c in ("liaison_i", "liaison_j"):
            v = e.get(c, "rigide") or "rigide"
            if v not in ("rigide", "articulee"):
                raise ValueError(f"{nom} : {c} doit valoir « rigide » ou « articulee » (reçu : {v!r}).")
            p[c] = v
        p["L"], p["R"] = _repere(xyz[i], xyz[j], p["beta"])
        p["q"] = np.zeros(3)  # charge répartie globale (N/m), poids propre compris
        els.append(p)
    eindex = {e["id"]: k for k, e in enumerate(els)}

    F = np.zeros(6 * len(ids))
    for k, c in enumerate(_liste(data, "charges_nodales"), start=1):
        if not isinstance(c, dict) or c.get("noeud") not in index:
            raise ValueError(
                f"Charge nodale n°{k} : le nœud {c.get('noeud') if isinstance(c, dict) else c!r} n'existe pas."
            )
        n = index[c["noeud"]]
        for d, f in enumerate(("Fx", "Fy", "Fz", "Mx", "My", "Mz")):
            F[6 * n + d] += _reel(c.get(f, 0.0) or 0.0, f"Charge nodale n°{k} : {f}", signe=False)
    for k, c in enumerate(_liste(data, "charges_reparties"), start=1):
        if not isinstance(c, dict) or c.get("element") not in eindex:
            raise ValueError(
                f"Charge répartie n°{k} : l'élément {c.get('element') if isinstance(c, dict) else c!r} n'existe pas."
            )
        els[eindex[c["element"]]]["q"] += [
            _reel(c.get(f, 0.0) or 0.0, f"Charge répartie n°{k} : {f}", signe=False) for f in ("qx", "qy", "qz")
        ]
    pp = bool(data.get("poids_propre", False))
    if pp:
        for e in els:
            e["q"][2] -= e["rho"] * G_PESANTEUR * e["A"]
    return {"ids": ids, "xyz": xyz, "bloque": np.array(bloque).reshape(-1), "elements": els, "F": F, "pp": pp}


# ------------------------------------------------------------------ élément


def _repere(xi: np.ndarray, xj: np.ndarray, beta: float) -> tuple[float, np.ndarray]:
    """Longueur (m) et matrice 3×3 de rotation (lignes x_l, y_l, z_l dans le repère global) d'un élément.

    v = Z global (X global si |x_l·Z| > 0,999), y_l = v × x_l normé, z_l = x_l × y_l, puis rotation β autour de x_l.
    """
    d = xj - xi
    L = float(np.linalg.norm(d))
    x = d / L
    v = np.array([0.0, 0.0, 1.0]) if abs(x[2]) <= 0.999 else np.array([1.0, 0.0, 0.0])
    y = np.cross(v, x)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    c, s = math.cos(beta), math.sin(beta)
    return L, np.array([x, c * y + s * z, -s * y + c * z])


def _kLocal(e: dict) -> np.ndarray:
    """Matrice de rigidité locale 12×12 d'Euler-Bernoulli (sans déformation d'effort tranchant)."""
    E, G, L = e["E"], e["G"], e["L"]
    k = np.zeros((12, 12))
    k[np.ix_([0, 6], [0, 6])] = E * e["A"] / L * np.array([[1, -1], [-1, 1]])
    k[np.ix_([3, 9], [3, 9])] = G * e["J"] / L * np.array([[1, -1], [-1, 1]])
    B = (
        np.array(
            [
                [12, 6 * L, -12, 6 * L],
                [6 * L, 4 * L**2, -6 * L, 2 * L**2],
                [-12, -6 * L, 12, -6 * L],
                [6 * L, 2 * L**2, -6 * L, 4 * L**2],
            ]
        )
        / L**3
    )
    k[np.ix_([1, 5, 7, 11], [1, 5, 7, 11])] = E * e["Iz"] * B  # plan (x, y) : v et θz = v'
    S = np.diag([1.0, -1.0, 1.0, -1.0])  # plan (x, z) : θy = -w'
    k[np.ix_([2, 4, 8, 10], [2, 4, 8, 10])] = E * e["Iy"] * S @ B @ S
    return k


def _fLocal(q: np.ndarray, L: float) -> np.ndarray:
    """Charges nodales équivalentes locales (12) d'une charge uniforme locale `q` (N/m) : qL/2 et ±qL²/12."""
    qx, qy, qz = q
    f = np.zeros(12)
    f[[0, 6]] = qx * L / 2
    f[[1, 7]] = qy * L / 2
    f[5], f[11] = qy * L**2 / 12, -qy * L**2 / 12
    f[[2, 8]] = qz * L / 2
    f[4], f[10] = -qz * L**2 / 12, qz * L**2 / 12
    return f


def _condense(k: np.ndarray, f: np.ndarray, rel: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Condensation statique des DDL locaux `rel` (rotations θy, θz relâchées) : matrice et charges équivalentes.

    Les lignes et colonnes relâchées sont mises à zéro ; l'effort d'extrémité correspondant est alors nul.
    """
    if not rel:
        return k, f
    c = [d for d in range(12) if d not in rel]
    Krr, Krc = k[np.ix_(rel, rel)], k[np.ix_(rel, c)]
    kc, fc = np.zeros((12, 12)), np.zeros(12)
    kc[np.ix_(c, c)] = k[np.ix_(c, c)] - Krc.T @ np.linalg.solve(Krr, Krc)
    fc[c] = f[c] - Krc.T @ np.linalg.solve(Krr, f[rel])
    return kc, fc


def _preparer(e: dict) -> None:
    """Ajoute à l'élément : T (12×12), qloc (N/m), klc et flc (locales, condensées), kg et fg (globales)."""
    R = e["R"]
    T = np.kron(np.eye(4), R)
    e["qloc"] = R @ e["q"]
    rel = ([4, 5] if e["liaison_i"] == "articulee" else []) + ([10, 11] if e["liaison_j"] == "articulee" else [])
    if len(rel) == 4:  # articulée aux deux bouts : sinon la barre tourne librement sur son axe (mécanisme)
        rel.append(9)
    e["klc"], e["flc"] = _condense(_kLocal(e), _fLocal(e["qloc"], e["L"]), rel)
    e["T"], e["kg"], e["fg"] = T, T.T @ e["klc"] @ T, T.T @ e["flc"]
    e["dofs"] = np.r_[6 * e["i"] : 6 * e["i"] + 6, 6 * e["j"] : 6 * e["j"] + 6]


# ------------------------------------------------------------------ résolution


def _nomDdl(ids: list, d: int) -> str:
    """Nom lisible d'un DDL global : « nœud 'A' : uz »."""
    return f"nœud {ids[d // 6]!r} : {DDL[d % 6]}"


def _blocagesAuto(
    K: np.ndarray, bloque: np.ndarray, n: int
) -> tuple[np.ndarray, list[tuple[int, np.ndarray, np.ndarray]]]:
    """Bloque les rotations de nœud sans aucune raideur (toutes les pièces y sont articulées).

    Une direction de rotation e d'un nœud telle que eᵀ·K·e = 0 est découplée du reste (K est positive), on lui
    ajoute donc une raideur fictive, puis la rotation correspondante est remise à zéro après la résolution.
    Sorties : matrice augmentée et liste (nœud, indices des DDL de rotation libres, direction e).
    """
    rot = [6 * k + d for k in range(n) for d in (3, 4, 5)]
    kref = float(np.max(np.diag(K)[rot])) or 1.0
    Ka, auto = K.copy(), []
    for k in range(n):
        idx = np.array([6 * k + d for d in (3, 4, 5) if not bloque[6 * k + d]], dtype=int)
        if idx.size == 0:
            continue
        w, V = np.linalg.eigh(K[np.ix_(idx, idx)])
        for lam, vec in zip(w, V.T, strict=True):
            if lam <= _NUL_ROT * kref:
                Ka[np.ix_(idx, idx)] += kref * np.outer(vec, vec)
                auto.append((k, idx, vec))
    return Ka, auto


def _resoudre(Kff: np.ndarray, Ff: np.ndarray, libres: np.ndarray, ids: list) -> tuple[np.ndarray, float]:
    """Déplacements libres et conditionnement réciproque (matrice mise à l'échelle par sa diagonale).

    Erreur : FrameMechanismError si la structure est un mécanisme, avec les DDL qui semblent libres.
    """
    if Kff.size == 0:
        return np.zeros(0), 1.0
    diag = np.diag(Kff)
    nuls = np.flatnonzero(diag <= 0)
    if nuls.size == 0:
        s = 1 / np.sqrt(diag)
        w, V = np.linalg.eigh(s[:, None] * Kff * s[None, :])
        rcond = float(w[0] / w[-1]) if w[-1] > 0 else 0.0
        if rcond >= _RCOND_MIN:
            try:
                return np.linalg.solve(Kff, Ff), rcond
            except np.linalg.LinAlgError:
                pass
        modes = V[:, w <= _RCOND_MIN * max(w[-1], 0.0)]
        poids = np.sum(modes**2, axis=1) if modes.size else np.ones(len(diag))
        nuls = np.flatnonzero(poids >= 0.1 * poids.max())
    noms = [_nomDdl(ids, int(libres[d])) for d in nuls]
    suite = f" (et {len(noms) - 12} autres)" if len(noms) > 12 else ""
    raise FrameMechanismError(
        "La structure est un mécanisme (matrice de rigidité singulière) : ajoutez des appuis ou des liaisons. "
        f"DDL qui semblent libres : {', '.join(noms[:12])}{suite}."
    )


def _efforts(e: dict, u: np.ndarray) -> tuple[dict, np.ndarray]:
    """Efforts internes locaux en 21 points (s, N, Vy, Vz, T, My, Mz) et efforts d'extrémité locaux (12)."""
    f = e["klc"] @ (e["T"] @ u[e["dofs"]]) - e["flc"]  # efforts des nœuds sur l'élément
    qx, qy, qz = e["qloc"]
    s = np.linspace(0.0, e["L"], _NPTS)
    ef = {
        "s": s,
        "N": -f[0] - qx * s,
        "Vy": -f[1] - qy * s,
        "Vz": -f[2] - qz * s,
        "T": np.full(_NPTS, -f[3]),
        "My": -f[4] - f[2] * s - qz * s**2 / 2,
        "Mz": -f[5] + f[1] * s + qy * s**2 / 2,
    }
    return ef, f


def _contraintes(e: dict, ef: dict) -> dict:
    """σmax = max(|N|/A + |My|/Wy + |Mz|/Wz) et τ = max |T|/Wt (Pa), None si un module manque."""
    sig = None
    if e["Wy"] is not None and e["Wz"] is not None:
        sig = float(np.max(np.abs(ef["N"]) / e["A"] + np.abs(ef["My"]) / e["Wy"] + np.abs(ef["Mz"]) / e["Wz"]))
    tau = None if e["Wt"] is None else float(np.max(np.abs(ef["T"])) / e["Wt"])
    return {"sigma_max": sig, "tau_torsion": tau}


def _equilibre(m: dict, R: np.ndarray) -> dict:
    """Somme des réactions et des charges appliquées : forces (N) et moments par rapport à l'origine (N·m)."""
    xyz, els = m["xyz"], m["elements"]
    nod = np.vstack([m["F"].reshape(-1, 6), R.reshape(-1, 6)])  # charges nodales puis réactions
    P = np.vstack([xyz, xyz] + [(xyz[e["i"]] + xyz[e["j"]])[None, :] / 2 for e in els])
    Fo = np.vstack([nod[:, :3]] + [(e["q"] * e["L"])[None, :] for e in els])  # résultantes au milieu des éléments
    sF = Fo.sum(axis=0)
    sM = np.cross(P, Fo).sum(axis=0) + nod[:, 3:].sum(axis=0)
    # échelle : somme des normes des actions, bras de levier compris
    nF, nP = np.linalg.norm(Fo, axis=1), np.linalg.norm(P, axis=1)
    eF = float(nF.sum())
    eM = float((nF * nP).sum() + np.linalg.norm(nod[:, 3:], axis=1).sum() + eF * max(e["L"] for e in els))
    ok = bool(np.linalg.norm(sF) <= 1e-6 * eF and np.linalg.norm(sM) <= 1e-6 * eM)
    return {"forces": sF.tolist(), "moments": sM.tolist(), "ok": ok}


def solveFrame3D(data: dict) -> dict:
    """Résout une ossature de poutres 3D par la méthode des déplacements (Euler-Bernoulli, tranchant négligé).

    Entrée : `data` (dict, SI) : noeuds [{id, x, y, z (m), appui}], appui parmi libre, encastrement, rotule, appui_z
    ou perso (alors « ddl » = 6 booléens [ux, uy, uz, rx, ry, rz], vrai = bloqué) ; elements [{id, ni, nj, E, G (Pa),
    A (m²), Iy, Iz, J (m⁴), rho (kg/m³), beta_deg (°), liaison_i, liaison_j (rigide | articulee), Wy, Wz, Wt (m³,
    facultatifs), section (facultative : {type: rond|tube|rectangle, ...}, complète les valeurs absentes)}] ;
    charges_nodales [{noeud, Fx, Fy, Fz (N), Mx, My, Mz (N·m)}] et charges_reparties [{element, qx, qy, qz (N/m)}],
    repère global ; poids_propre (bool, ρ·g·A selon -Z).
    Sortie : dict deplacements et reactions ({id nœud: 6 valeurs, m et rad / N et N·m}), efforts ({id élément: s,
    N, Vy, Vz, T, My, Mz en 21 points, repère local}), contraintes ({id: sigma_max, tau_torsion en Pa ou None}),
    deplacement_max ({valeur (m), noeud}), equilibre ({forces, moments, ok}), blocages_auto, rcond, K (matrice
    assemblée avant conditions d'appui), rapport et latex (listes de textes).
    Erreurs : ValueError (entrées invalides), FrameMechanismError (mécanisme).
    """
    m = _lire(data)
    ids, n = m["ids"], len(m["ids"])
    K, Feq = np.zeros((6 * n, 6 * n)), np.zeros(6 * n)
    for e in m["elements"]:
        _preparer(e)
        K[np.ix_(e["dofs"], e["dofs"])] += e["kg"]
        Feq[e["dofs"]] += e["fg"]
    F = m["F"] + Feq
    bloque = m["bloque"]
    Ka, auto = _blocagesAuto(K, bloque, n)
    libres = np.flatnonzero(~bloque)
    u = np.zeros(6 * n)
    u[libres], rcond = _resoudre(Ka[np.ix_(libres, libres)], F[libres], libres, ids)
    for _, idx, vec in auto:
        u[idx] -= vec * (vec @ u[idx])
    R = K @ u - F
    echelle = max(float(np.abs(F).max()), 1.0)
    for k, idx, vec in auto:  # un blocage automatique ne doit rien reprendre : sinon c'est un faux appui
        if abs(vec @ R[idx]) > 1e-9 * echelle:
            raise FrameMechanismError(
                f"Moment appliqué sur une rotule au nœud {ids[k]!r} ({_direction(idx, vec)}) : aucune pièce ne peut "
                "le reprendre (toutes y sont articulées). Rendez une liaison rigide ou déplacez le moment."
            )
    R[~bloque] = 0.0

    depl = {ids[k]: u[6 * k : 6 * k + 6].tolist() for k in range(n)}
    appuis = [k for k in range(n) if bloque[6 * k : 6 * k + 6].any()]
    reac = {ids[k]: R[6 * k : 6 * k + 6].tolist() for k in appuis}
    efforts, contr, fext = {}, {}, {}
    for e in m["elements"]:
        ef, fext[e["id"]] = _efforts(e, u)
        efforts[e["id"]] = {c: v.tolist() for c, v in ef.items()}
        contr[e["id"]] = _contraintes(e, ef)
    tr = np.linalg.norm(u.reshape(-1, 6)[:, :3], axis=1)
    kmax = int(np.argmax(tr))
    res = {
        "deplacements": depl,
        "reactions": reac,
        "efforts": efforts,
        "contraintes": contr,
        "deplacement_max": {"valeur": float(tr[kmax]), "noeud": ids[kmax]},
        "equilibre": _equilibre(m, R),
        "blocages_auto": [{"noeud": ids[k], "direction": vec.tolist()} for k, idx, vec in auto],
        "rcond": rcond,
        "K": K,
    }
    res["rapport"], res["latex"] = _rapport(m, res, auto)
    return res


# ------------------------------------------------------------------ rapport


def _vec(v) -> str:
    """Vecteur au format (a ; b ; c) pour le rapport."""
    return "(" + " ; ".join(_num(x) for x in v) + ")"


def _direction(idx: np.ndarray, vec: np.ndarray) -> str:
    """Nom d'une direction de rotation bloquée : θx, θy, θz si elle suit un axe global, sinon ses composantes."""
    full = np.zeros(3)
    full[idx % 6 - 3] = vec
    a = int(np.argmax(np.abs(full)))
    return DDL[3 + a] if abs(abs(full[a]) - 1) < 1e-9 else f"rotation autour de {_vec(full)}"


def _rapport(m: dict, res: dict, auto: list) -> tuple[list[str], list[str]]:
    """Rapport texte (français) et formules LaTeX (ASCII) de l'ossature 3D."""
    ids, els = m["ids"], m["elements"]
    rep = [f"=== Ossature de poutres 3D : {len(ids)} nœuds, {len(els)} éléments (méthode des déplacements) ==="]
    rep.append(
        "Hypothèses : poutres d'Euler-Bernoulli, petits déplacements, matériau élastique linéaire ; la déformation "
        "d'effort tranchant est négligée (flèches un peu sous-estimées pour les poutres courtes)."
    )
    rep.append(
        "Repère local : x_l de ni vers nj ; y_l = Z × x_l normé (X global si l'élément est vertical), z_l = x_l × y_l, "
        "puis rotation beta autour de x_l. DDL d'un nœud : [ux, uy, uz, θx, θy, θz]."
    )
    rep.append(
        "Efforts internes : action de la partie s+ sur la partie s- ; N > 0 en traction ; dMy/ds = Vz, dMz/ds = -Vy."
    )
    if m["pp"]:
        rep.append(f"Poids propre inclus : q = ρ·g·A selon -Z, g = {G_PESANTEUR} m/s².")
    rep.append("Nœuds (m) :")
    for k, i in enumerate(ids):
        bl = "".join("1" if b else "0" for b in m["bloque"][6 * k : 6 * k + 6])
        rep.append(f"  {i!r} : {_vec(m['xyz'][k])}, DDL bloqués [ux uy uz θx θy θz] = {bl}")
    rep.append("Éléments :")
    for e in els:
        lib = [c for c in ("liaison_i", "liaison_j") if e[c] == "articulee"]
        rep.append(
            f"  {e['id']!r} : {ids[e['i']]!r} → {ids[e['j']]!r}, L = {_num(e['L'])} m, E = {_num(e['E'])} Pa, "
            f"G = {_num(e['G'])} Pa, A = {_num(e['A'])} m², Iy = {_num(e['Iy'])} m⁴, Iz = {_num(e['Iz'])} m⁴, "
            f"J = {_num(e['J'])} m⁴, q global = {_vec(e['q'])} N/m"
            + (f", articulé ({', '.join(lib)}) : θy et θz relâchés, torsion transmise" if len(lib) == 1 else "")
            + (
                ", articulé aux deux bouts : θy, θz relâchés et torsion non transmise (barre de treillis)"
                if len(lib) == 2
                else ""
            )
        )
    for k, idx, vec in auto:
        rep.append(
            f"  Blocage automatique : nœud {ids[k]!r}, {_direction(idx, vec)} (aucune raideur : toutes les pièces y "
            "sont articulées)."
        )
    rep.append(f"Conditionnement réciproque de la matrice réduite (mise à l'échelle) : {res['rcond']:.3g}")
    rep.append("Déplacements (m) et rotations (rad) :")
    for i, v in res["deplacements"].items():
        rep.append(f"  {i!r} : u = {_vec(v[:3])}, θ = {_vec(v[3:])}")
    dm = res["deplacement_max"]
    rep.append(f"Déplacement maximal : {_num(dm['valeur'])} m au nœud {dm['noeud']!r}.")
    rep.append("Réactions (N et N·m) :")
    for i, v in res["reactions"].items():
        rep.append(f"  {i!r} : R = {_vec(v[:3])}, M = {_vec(v[3:])}")
    rep.append("Efforts maximaux par élément (valeurs absolues) et contraintes :")
    for e in els:
        ef, c = res["efforts"][e["id"]], res["contraintes"][e["id"]]
        mx = {k: max(abs(x) for x in ef[k]) for k in ("N", "Vy", "Vz", "T", "My", "Mz")}
        txt = ", ".join(f"{k} = {_num(v)}" for k, v in mx.items())
        sig = "non calculée (Wy ou Wz absent)" if c["sigma_max"] is None else f"{_num(c['sigma_max'])} Pa"
        tau = "non calculée (Wt absent)" if c["tau_torsion"] is None else f"{_num(c['tau_torsion'])} Pa"
        rep.append(f"  {e['id']!r} : {txt} ; σmax = {sig} ; τ torsion = {tau}")
    eq = res["equilibre"]
    rep.append(
        f"Équilibre global (réactions + charges) : ΣF = {_vec(eq['forces'])} N, ΣM/O = {_vec(eq['moments'])} N·m "
        f"→ {'vérifié' if eq['ok'] else 'NON VÉRIFIÉ'} (tolérance 1e-6 de l'échelle)."
    )
    rep.append("σmax est une borne conservative (les trois maximums sont supposés au même point de la section).")

    tex = [
        r"$[K]\,\{u\} = \{F\},\quad [K] = \sum_{e} [T_e]^{T}\,[k_e]\,[T_e],\quad "
        r"\{F\} = \{F_{nod}\} + \sum_{e} [T_e]^{T} \{f_e^{eq}\}$",
        r"$[k_e]:\ \frac{EA}{L},\ \frac{GJ}{L},\ \frac{12EI}{L^{3}},\ \frac{6EI}{L^{2}},\ \frac{4EI}{L},\ "
        r"\frac{2EI}{L}$",
        r"$[k_{xz}] = \frac{E I_y}{L^{3}} \left[ \begin{array}{cccc} 12 & -6L & -12 & -6L \\ -6L & 4L^{2} & 6L & "
        r"2L^{2} \\ -12 & 6L & 12 & 6L \\ -6L & 2L^{2} & 6L & 4L^{2} \end{array} \right]\ "
        r"(w_i,\ \theta_{y,i},\ w_j,\ \theta_{y,j})$",
        r"$[k_{xy}] = \frac{E I_z}{L^{3}} \left[ \begin{array}{cccc} 12 & 6L & -12 & 6L \\ 6L & 4L^{2} & -6L & "
        r"2L^{2} \\ -12 & -6L & 12 & -6L \\ 6L & 2L^{2} & -6L & 4L^{2} \end{array} \right]\ "
        r"(v_i,\ \theta_{z,i},\ v_j,\ \theta_{z,j})$",
        r"$\{f^{eq}\}:\ \frac{qL}{2},\ \pm\frac{qL^{2}}{12}$",
        r"$\sigma_{max} = \frac{|N|}{A} + \frac{|M_y|}{W_y} + \frac{|M_z|}{W_z},\quad \tau = \frac{|T|}{W_t}$",
        rf"$u_{{max}} = {_texNum(dm['valeur'])}\ \mathrm{{m}}$",
    ]
    return rep, tex


# ------------------------------------------------------------------ exemples


def _profil(dm, famille: str, nom) -> dict:
    """Propriétés 3D d'un profilé du catalogue : axe fort du catalogue (Iz) → Iy local ; J estimé (parois minces).

    J ≈ (2·b·e³ + (h − 2e)·a³)/3, sans les congés ; Wt = J/max(e, a).
    """
    p = dm.getProfile(famille, nom)
    J = (2 * p["b"] * p["e"] ** 3 + (p["h"] - 2 * p["e"]) * p["a"] ** 3) / 3
    return {
        "A": p["S"],
        "Iy": p["Iz"],
        "Iz": p["Iy"],
        "J": J,
        "Wy": p["Wz"],
        "Wz": p["Wy"],
        "Wt": J / max(p["e"], p["a"]),
    }


def exemples() -> dict:
    """Quatre ossatures prêtes à résoudre : « Console », « Potence en L », « Portique 3D », « Table 4 pieds ».

    Matériau S235 et profilés lus dans la base (DataManager). Sortie : dict nom → données de solveFrame3D.
    """
    from mecastruct.core.data_manager import DataManager

    dm = DataManager()
    acier = dm.getMaterial("S235")
    mat = {"E": acier["E"], "G": acier["G"], "rho": acier["rho"]}

    def el(i, ni, nj, sec, **kw):
        return {"id": i, "ni": ni, "nj": nj, **mat, **sec, **kw}

    ipe200, heb200 = _profil(dm, "IPE", 200), _profil(dm, "HEB", 200)
    tube = sectionTube(0.1, 0.005)
    console = {
        "noeuds": [{"id": 1, "x": 0, "y": 0, "z": 0, "appui": "encastrement"}, {"id": 2, "x": 2, "y": 0, "z": 0}],
        "elements": [el(1, 1, 2, ipe200)],
        "charges_nodales": [{"noeud": 2, "Fz": -10e3}],
        "poids_propre": True,
    }
    potence = {
        "noeuds": [
            {"id": 1, "x": 0, "y": 0, "z": 0, "appui": "encastrement"},
            {"id": 2, "x": 0, "y": 0, "z": 3},
            {"id": 3, "x": 1.5, "y": 0, "z": 3},
        ],
        "elements": [el(1, 1, 2, tube), el(2, 2, 3, tube)],
        "charges_nodales": [{"noeud": 3, "Fz": -1.5e3, "Fy": 200}],
        "poids_propre": True,
    }
    coins = [(0, 0), (5, 0), (5, 4), (0, 4)]
    portique = {
        "noeuds": [{"id": k + 1, "x": x, "y": y, "z": 0, "appui": "encastrement"} for k, (x, y) in enumerate(coins)]
        + [{"id": k + 5, "x": x, "y": y, "z": 3} for k, (x, y) in enumerate(coins)],
        "elements": [el(k + 1, k + 1, k + 5, heb200) for k in range(4)]
        + [el(k + 5, k + 5, (k + 1) % 4 + 5, ipe200) for k in range(4)],
        "charges_reparties": [{"element": k + 5, "qz": -10e3} for k in range(4)],
        "charges_nodales": [{"noeud": 5, "Fx": 5e3}, {"noeud": 8, "Fy": -3e3}],
        "poids_propre": True,
    }
    plateau = [(0, 0), (1.2, 0), (1.2, 0.8), (0, 0.8)]
    pied, cadre = sectionRond(0.04), sectionRectangle(0.03, 0.06)
    table = {
        "noeuds": [{"id": k + 1, "x": x, "y": y, "z": 0, "appui": "rotule"} for k, (x, y) in enumerate(plateau)]
        + [{"id": k + 5, "x": x, "y": y, "z": 0.75} for k, (x, y) in enumerate(plateau)],
        "elements": [el(k + 1, k + 1, k + 5, pied) for k in range(4)]
        + [el(k + 5, k + 5, (k + 1) % 4 + 5, cadre) for k in range(4)],
        "charges_nodales": [{"noeud": k + 5, "Fz": -500} for k in range(4)] + [{"noeud": 6, "Fx": 100}],
        "charges_reparties": [{"element": 5, "qz": -300}],
        "poids_propre": True,
    }
    return {"Console": console, "Potence en L": potence, "Portique 3D": portique, "Table 4 pieds": table}
