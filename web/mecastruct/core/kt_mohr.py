"""Abaques Kt (ajustements de Peterson) et table des intégrales de Mohr, en SI sans unité.

Port de DataManager.ktCharts, evalKt, petersonTable, ktPlateParam, ktShaftParams, mohrTable et mohrRecord.
Les abaques et les formes de diagrammes sont lus dans web/data/kt_charts.json et mohr_table.json.
"""

import numpy as np

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import as_list, load_json

_PLAQUE = "plaque_trou_traction"
_ARBRES = ("arbre_epaulement_flexion", "arbre_epaulement_torsion", "arbre_epaulement_traction")


def ktCharts() -> list[dict]:
    """Abaques Kt disponibles : id, title, params, ranges, description, paramFields, curves, table, latex.

    Sortie : list[dict] lu dans web/data/kt_charts.json ; table contient les lignes [D/d, A, b] de Peterson.
    """
    return as_list(load_json("kt_charts.json"))


def evalKt(id: str, prm) -> float | np.ndarray:
    """Kt de l'abaque `id`, toujours supérieur ou égal à 1 (paramètres : voir evalKtInfo).

    Sortie : nombre si prm est un nombre ou un couple, tableau sinon.
    Erreurs : MecaStruct:DataManager:unknownKt, MecaStruct:DataManager:ktParams.
    """
    return evalKtInfo(id, prm)[0]


def evalKtInfo(id: str, prm) -> tuple[float | np.ndarray, dict]:
    """Kt de l'abaque `id`, avec son détail.

    Entrées : `id` (plaque_trou_traction, arbre_epaulement_flexion, _torsion ou _traction) ; `prm` : d/W pour
    la plaque (nombre, tableau, ou dict dW ou d et W) ; [r/d, D/d], matrice n×2, ou dict (rd, Dd) ou
    (r, d, D) pour un arbre, avec r/d > 0 et D/d > 1.
    Sorties : Kt (≥ 1) et info dict : id, A, b (NaN pour la plaque), inRange (domaine de validité respecté),
    params, report (list[str], en français), latex (list[str]).
    Erreurs : MecaStruct:DataManager:unknownKt, MecaStruct:DataManager:ktParams.
    """
    idc = str(id).strip().lower()
    info = {"id": idc, "A": np.nan, "b": np.nan, "inRange": True, "params": {}, "report": [], "latex": []}
    if idc == _PLAQUE:
        x = _ktPlateParam(prm)
        Kt = np.maximum(3 - 3.13 * x + 3.66 * x**2 - 1.53 * x**3, 1)
        info["params"] = {"dW": x}
        info["report"] = [
            "Plaque percée d'un trou central en traction (section nette).",
            "Kt = 3 − 3,13·(d/W) + 3,66·(d/W)² − 1,53·(d/W)³",
        ]
        if x.size == 1:
            dw, kt = x.item(), Kt.item()
            info["report"].append(f"d/W = {dw:.4g}  →  Kt = {kt:.4g}")
            info["latex"] = [
                f"$K_t = 3 - 3{{,}}13 \\times {dw:.4g} + 3{{,}}66 \\times {dw:.4g}^2 - "
                f"1{{,}}53 \\times {dw:.4g}^3 = {kt:.4g}$"
            ]
        else:
            info["latex"] = [
                r"$K_t = 3 - 3{,}13\,\frac{d}{W} + 3{,}66\left(\frac{d}{W}\right)^2 "
                r"- 1{,}53\left(\frac{d}{W}\right)^3$"
            ]
    elif idc in _ARBRES:
        rd, Dd = _ktShaftParams(prm)
        tab = _petersonTable(idc)
        Ddc = np.clip(Dd, tab[0, 0], tab[-1, 0])
        A = np.interp(Ddc, tab[:, 0], tab[:, 1])
        b = np.interp(Ddc, tab[:, 0], tab[:, 2])
        Kt = np.maximum(A * rd**b, 1)
        rdOk = (rd >= 0.01 - 1e-12) & (rd <= 0.30 + 1e-12)
        DdOk = (Dd >= tab[0, 0] - 1e-12) & (Dd <= tab[-1, 0] + 1e-12)
        info.update(A=A, b=b, inRange=bool(np.all(rdOk) and np.all(DdOk)), params={"rd": rd, "Dd": Dd})
        mode = idc.removeprefix("arbre_epaulement_")
        info["report"] = [f"Arbre épaulé en {mode} : ajustement de Peterson Kt = A·(r/d)^b."]
        if rd.size == 1 and Dd.size == 1:
            rv, Dv, Av, bv, Ktv = rd.item(), Dd.item(), A.item(), b.item(), Kt.item()
            info["report"] += [
                f"r/d = {rv:.4g} ; D/d = {Dv:.4g}  →  A = {Av:.5g} ; b = {bv:.5g} (interpolation linéaire en D/d)",
                f"Kt = {Av:.5g} × {rv:.4g}^({bv:.5g}) = {Ktv:.4g}",
            ]
            info["latex"] = [
                f"$K_t = A\\left(\\frac{{r}}{{d}}\\right)^{{b}} = {Av:.5g} \\times {rv:.4g}^{{{bv:.5g}}} = {Ktv:.4g}$"
            ]
        else:
            info["latex"] = [r"$K_t = A\left(\frac{D}{d}\right)\,\left(\frac{r}{d}\right)^{b(D/d)}$"]
        if np.any(Dd != Ddc):
            info["report"].append(
                f"Attention : D/d hors de la table [{tab[0, 0]:.4g} ; {tab[-1, 0]:.4g}], "
                "coefficients de la borne la plus proche utilisés."
            )
    else:
        names = ", ".join(c["id"] for c in ktCharts())
        raise MecaStructError(
            "MecaStruct:DataManager:unknownKt",
            f"Abaque Kt inconnu : « {idc} ». Abaques disponibles : {names}.",
        )
    if not info["inRange"]:
        info["report"].append("Attention : paramètres hors du domaine de validité de l'abaque (extrapolation).")
    return Kt, info


def mohrTable() -> list[dict]:
    """Table des intégrales de Mohr ∫₀ˡ Mi·Mj ds pour les 25 couples ordonnés de 5 formes de diagrammes.

    Sortie : list[dict] avec id, shape1, shape2, latex, description (lus dans web/data/mohr_table.json) et fun,
    fonction (l, a, b) → intégrale. l : longueur (m) ; a, b : valeurs caractéristiques de chaque diagramme
    (rectangle et triangle [M], trapèze [M_gauche, M_droite], parabole [f]).
    """
    return [{**e, "fun": _mohrFun(e["id"])} for e in as_list(load_json("mohr_table.json"))]


# -------------------------------------------------------------------------------------------------
# Aides privées
# -------------------------------------------------------------------------------------------------


def _firstField(s: dict, names: tuple[str, ...]) -> np.ndarray:
    """Premier champ non vide de s parmi names, en tableau de réels ; tableau vide si aucun n'existe."""
    for name in names:
        if s.get(name) is not None and np.size(s[name]) > 0:
            return np.asarray(s[name], dtype=float)
    return np.zeros(0)


def _ktPlateParam(prm) -> np.ndarray:
    """Paramètre d/W de la plaque : nombre, tableau, ou dict (dW, ou d et W) ; erreur si hors de [0 ; 1[."""
    if isinstance(prm, dict):
        x = _firstField(prm, ("dW", "d_W", "dsurW", "d_sur_W", "dOverW", "ratio"))
        if x.size == 0 and "d" in prm and "W" in prm:
            x = np.asarray(prm["d"], dtype=float) / np.asarray(prm["W"], dtype=float)
    else:
        x = np.asarray(prm, dtype=float)
    if x.size == 0 or not np.isfinite(x).all() or ((x < 0) | (x >= 1)).any():
        raise MecaStructError(
            "MecaStruct:DataManager:ktParams",
            "Plaque trouée : le paramètre d/W doit être réel, avec 0 ≤ d/W < 1.",
        )
    return x


def _ktShaftParams(prm) -> tuple[np.ndarray, np.ndarray]:
    """Paramètres r/d et D/d de l'arbre épaulé : [r/d, D/d] ou matrice n×2, dict (rd, Dd) ou (r, d, D)."""
    rd = Dd = np.zeros(0)
    if isinstance(prm, dict):
        rd = _firstField(prm, ("rd", "r_d", "rsurd", "r_sur_d", "rOverd"))
        Dd = _firstField(prm, ("Dd", "D_d", "Dsurd", "D_sur_d", "DOverd"))
        if rd.size == 0 and "r" in prm and "d" in prm:
            rd = np.asarray(prm["r"], dtype=float) / np.asarray(prm["d"], dtype=float)
        if Dd.size == 0 and "D" in prm and "d" in prm:
            Dd = np.asarray(prm["D"], dtype=float) / np.asarray(prm["d"], dtype=float)
    else:
        arr = np.asarray(prm, dtype=float)
        if arr.size == 2:
            rd, Dd = arr.flat[0], arr.flat[1]
        elif arr.ndim == 2 and arr.shape[1] == 2:
            rd, Dd = arr[:, 0], arr[:, 1]
    if rd.size == 0 or Dd.size == 0 or not (np.isfinite(rd).all() and np.isfinite(Dd).all()):
        raise MecaStructError(
            "MecaStruct:DataManager:ktParams",
            "Arbre épaulé : paramètres attendus [r/d, D/d] ou structure (rd, Dd) ou (r, d, D).",
        )
    if not ((rd > 0).all() and (Dd > 1).all()):
        raise MecaStructError("MecaStruct:DataManager:ktParams", "Arbre épaulé : il faut r/d > 0 et D/d > 1.")
    return rd, Dd


def _petersonTable(idc: str) -> np.ndarray:
    """Lignes [D/d, A, b] de Peterson de l'abaque arbre `idc`, lues dans ktCharts."""
    chart = next(c for c in ktCharts() if c["id"] == idc)
    return np.asarray(chart["table"], dtype=float)


# Intégrale ∫₀ˡ M1·M2 ds pour les 15 couples directs ; les 10 couples inversés s'en déduisent (voir _mohrFun).
_MOHR_FUNS = {
    "rectangle_x_rectangle": lambda l, a, b: l * a[0] * b[0],
    "rectangle_x_triangle": lambda l, a, b: l * a[0] * b[0] / 2,
    "rectangle_x_triangle_inverse": lambda l, a, b: l * a[0] * b[0] / 2,
    "rectangle_x_trapeze": lambda l, a, b: l * a[0] * (b[0] + b[1]) / 2,
    "rectangle_x_parabole": lambda l, a, b: 2 * l * a[0] * b[0] / 3,
    "triangle_x_triangle": lambda l, a, b: l * a[0] * b[0] / 3,
    "triangle_x_triangle_inverse": lambda l, a, b: l * a[0] * b[0] / 6,
    "triangle_x_trapeze": lambda l, a, b: l * a[0] * (b[0] + 2 * b[1]) / 6,
    "triangle_x_parabole": lambda l, a, b: l * a[0] * b[0] / 3,
    "triangle_inverse_x_triangle_inverse": lambda l, a, b: l * a[0] * b[0] / 3,
    "triangle_inverse_x_trapeze": lambda l, a, b: l * a[0] * (2 * b[0] + b[1]) / 6,
    "triangle_inverse_x_parabole": lambda l, a, b: l * a[0] * b[0] / 3,
    "trapeze_x_trapeze": lambda l, a, b: l * (a[0] * (2 * b[0] + b[1]) + a[1] * (b[0] + 2 * b[1])) / 6,
    "trapeze_x_parabole": lambda l, a, b: l * (a[0] + a[1]) * b[0] / 3,
    "parabole_x_parabole": lambda l, a, b: 8 * l * a[0] * b[0] / 15,
}


def _mohrFun(ident: str):
    """Intégrale de Mohr de l'entrée `ident` ; une paire inversée réutilise la paire directe, a et b échangés."""
    if ident in _MOHR_FUNS:
        return _MOHR_FUNS[ident]
    s1, s2 = ident.split("_x_")
    f = _MOHR_FUNS[f"{s2}_x_{s1}"]
    return lambda l, a, b: f(l, b, a)
