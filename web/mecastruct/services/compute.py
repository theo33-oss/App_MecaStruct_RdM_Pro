"""Onglets hors Poutres sans interface : saisie → SI → moteur → tableaux (port des computeXxx de MecaStruct_App.m).

Chaque fonction lit une saisie dont les clés sont les noms des champs MATLAB (app.H.<Onglet>.<champ>), dans les
unités d'affichage, convertit en SI, appelle le moteur et renvoie
{"result": dict du moteur, "tables": {titre: DataFrame}, "status": str}.
result["rapport"] reprend le texte de la zone de résultats MATLAB (synthèse, puis démarche du moteur).

Les sections de l'onglet Sections (géométrie SI, clé "section") sont passées dans les saisies de Cisaillement et de
Flexion, comme buildSection() les lit dans l'interface.
Les valeurs par défaut sont celles que MATLAB charge au démarrage (loadExample sur chaque onglet).
"""

import ast
import math
import operator

import numpy as np
import pandas as pd

from mecastruct.core import buckling, geometry, hooke_gauges, kt_mohr, solicitations, tensors, truss_solver
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.core.units import fromSI, toSI
from mecastruct.services.beam_design import _kvTable
from mecastruct.services.beam_services import _okText

_ID = "MecaStruct:App:invalidInput"
_ID_EXPR = "MecaStruct:App:invalidExpression"

# Champs de dimensions utiles par type de section (relevantDims de MecaStruct_App.m)
_DIMS_SECTION = {
    "rectangle": ("b", "h"),
    "disque": ("D",),
    "couronne": ("D", "d"),
    "rectangle_creux": ("B", "H", "t"),
    "I": ("h", "b", "tw", "tf"),
    "T": ("h", "b", "tw", "tf"),
    "U": ("h", "b", "tw", "tf"),
    "L": ("h", "b", "t"),
}

# Unités d'affichage des caractéristiques d'un matériau (applyMaterial)
_MAT_UNITS = {"E": "GPa", "G": "GPa", "nu": "-", "Re": "MPa", "Rm": "MPa", "alpha": "1e-6/°C"}


def _materiau(dm: DataManager, nom: str, champs: list[str]) -> dict:
    """applyMaterial : valeurs du matériau dans les unités d'affichage (NaN si la base ne donne pas la valeur)."""
    m = dm.getMaterial(nom)
    return {c: fromSI(m[c], _MAT_UNITS[c]) for c in champs}


def _rapport(entete: list[str], blocs: list[tuple[str, list[str]]]) -> list[str]:
    """setReport : synthèse, puis un bloc par titre « === … === » (texte de la zone de résultats)."""
    lignes = list(entete)
    for titre, texte in blocs:
        lignes += [titre, *texte]
    return lignes


def _sectionLabel(sec: dict) -> str:
    """Libellé d'une section en mm (sectionLabel de MecaStruct_App.m)."""
    t = sec["type"]
    if t == "profile":
        return f"profilé {sec['name']}"
    if t == "rectangle":
        return f"rectangle b = {sec['b'] * 1e3:.4g} mm × h = {sec['h'] * 1e3:.4g} mm"
    if t == "disque":
        return f"disque D = {sec['D'] * 1e3:.4g} mm"
    if t == "couronne":
        return f"couronne D = {sec['D'] * 1e3:.4g} mm, d = {sec['d'] * 1e3:.4g} mm"
    if t == "rectangle_creux":
        return f"rectangle creux B = {sec['B'] * 1e3:.4g} × H = {sec['H'] * 1e3:.4g} mm, t = {sec['t'] * 1e3:.4g} mm"
    if t in ("I", "T", "U"):
        return (
            f"profil en {t} : h = {sec['h'] * 1e3:.4g}, b = {sec['b'] * 1e3:.4g}, "
            f"tw = {sec['tw'] * 1e3:.4g}, tf = {sec['tf'] * 1e3:.4g} mm"
        )
    if t == "L":
        return f"cornière L : h = {sec['h'] * 1e3:.4g}, b = {sec['b'] * 1e3:.4g}, t = {sec['t'] * 1e3:.4g} mm"
    return t


def _effortReading(N: float, Mfz: float, Mfy: float) -> str:
    """Lecture en français des efforts saisis (où la section est tendue ou comprimée)."""
    if N > 0:
        a = f"N = {N:.4g} kN : traction"
    elif N < 0:
        a = f"N = {N:.4g} kN : compression"
    else:
        a = "N = 0"
    if Mfz > 0:
        b = f"Mfz = {Mfz:.4g} kN·m : fibres du haut (y > 0) comprimées, du bas tendues"
    elif Mfz < 0:
        b = f"Mfz = {Mfz:.4g} kN·m : fibres du haut (y > 0) tendues, du bas comprimées"
    else:
        b = "Mfz = 0"
    if Mfy > 0:
        c = f"Mfy = {Mfy:.4g} kN·m : fibres z > 0 tendues, z < 0 comprimées"
    elif Mfy < 0:
        c = f"Mfy = {Mfy:.4g} kN·m : fibres z > 0 comprimées, z < 0 tendues"
    else:
        c = "Mfy = 0"
    return f"Lecture des efforts : {a} ; {b} ; {c}."


def _rectangles(lignes: list[dict]) -> list[list[float]]:
    """Rectangles [z1 z2 y1 y2] en m, depuis un tableau saisi en mm ; les lignes incomplètes sont ignorées."""
    cles = ("z1", "z2", "y1", "y2")

    def complete(ligne: dict) -> bool:
        return all(isinstance(ligne.get(k), (int, float)) and math.isfinite(ligne[k]) for k in cles)

    return [[toSI(ligne[k], "mm") for k in cles] for ligne in lignes if complete(ligne)]


def _sectionFromSaisie(S: dict, dm: DataManager) -> dict:
    """buildSection : section de l'onglet Sections en SI (profilé du catalogue si le type est « profile »)."""
    if S["type"] == "profile":
        return geometry.fromProfile(dm.getProfile(S["fam"], S["prof"]))
    if S["type"] == "composite":
        return geometry.validateSection(
            {"type": "composite", "rects": _rectangles(S["rects"]), "holes": _rectangles(S["holes"])}
        )
    sec = {"type": S["type"], **{k: toSI(S[k], "mm") for k in _DIMS_SECTION.get(S["type"], ())}}
    return geometry.validateSection(sec)


def _stressGeometry(sec: dict, p: dict) -> dict:
    """stressGeometry : profilé du catalogue → valeurs tabulées (les congés comptent), sinon contour exact."""
    if sec["type"] == "profile":
        p["P"] = geometry.tabulated(sec)
    else:
        p["sec"] = sec
    return p


def _compareDisplay(C: pd.DataFrame, extra: dict | None) -> pd.DataFrame:
    """Comparaison des méthodes en mm, mm², mm³, mm⁴ (compareDisplay de MecaStruct_App.m)."""
    facteurs = {"m^2": (1e6, "mm²"), "m": (1e3, "mm"), "m^3": (1e9, "mm³"), "m^4": (1e12, "mm⁴")}
    fu = [facteurs.get(u, (1.0, u)) for u in C.attrs["units"]]
    f = np.array([x[0] for x in fu])
    T = pd.DataFrame(
        {
            "Grandeur": list(C.index),
            "Unité": [x[1] for x in fu],
            "Analytique": C["Analytique"].to_numpy() * f,
            "Intégrale": C["Integrale"].to_numpy() * f,
            "Tabulée": C["Tabulee"].to_numpy() * f,
            "Écart max (%)": C["EcartMax_pct"].to_numpy(),
        }
    )
    if extra is not None:
        T["Intégrale numérique"] = [extra[n] * fi for n, fi in zip(C.index, f, strict=True)]
    return T


def _huygensDisplay(Hy: pd.DataFrame) -> pd.DataFrame:
    """Tableau de Huygens en mm, mm², mm⁴ (huygensDisplay de MecaStruct_App.m)."""
    T = pd.DataFrame()
    for v in Hy.columns:
        x = Hy[v].to_numpy()
        if v == "Label":
            T["Élément"] = [str(s) for s in x]
        elif v == "S_i":
            T["S_i (mm²)"] = x * 1e6
        elif v in ("zG_i", "yG_i", "dy_i", "dz_i"):
            T[f"{v} (mm)"] = x * 1e3
        else:
            T[f"{v} (mm⁴)"] = x * 1e12
    return T


# ----------------------------------------------------------------------------------------------- Sections


def defaultSectionInput() -> dict:
    """Saisie de l'onglet Sections au démarrage : IPE 200 (type I) en S235, efforts de l'exemple d'école."""
    return {
        "type": "I",
        "b": 100.0,
        "h": 200.0,
        "D": 100.0,
        "d": 80.0,
        "B": 100.0,
        "H": 200.0,
        "t": 10.0,
        "tw": 8.0,
        "tf": 12.0,
        "rects": [{"z1": 0.0, "z2": 100.0, "y1": 0.0, "y2": 200.0}],
        "holes": [],
        "fam": "IPE",
        "prof": "IPE 200",
        "mode": "symbolique" if geometry.hasSymbolic() else "numerique",
        "mat": "S235",
        "N": 50.0,
        "Mfz": 20.0,
        "Mfy": 0.0,
        "Ty": 60.0,
        "s0": 3.0,
        "Kt": 1.0,
    }


def computeSection(saisie: dict, dm: DataManager) -> dict:
    """Caractéristiques de la section (analytique, intégrale, tabulée) et contraintes σ(y), τ(y).

    Entrées : `saisie` (defaultSectionInput) ; `dm` (base). Sortie : result (sec, P, Pint, compare, bend, jour,
    rapport), tables « Comparaison des méthodes » et « Tableau de Huygens », status (S, Iz, Iy).
    """
    sec = _sectionFromSaisie(saisie, dm)
    mode = saisie["mode"]
    if mode == "symbolique" and not geometry.hasSymbolic():
        mode = "numerique"
    P = geometry.analytical(sec)
    C = geometry.compare(sec)
    Bdef = C.attrs["integral"]
    extra = None
    Bn = Bdef
    if mode == "numerique" and "symbolique" in Bdef["method"]:
        Bn = geometry.integral(sec, "numerique")
        extra = Bn
    mat = dm.getMaterial(saisie["mat"])
    bend = solicitations.bendingStress(
        _stressGeometry(
            sec,
            {
                "N": toSI(saisie["N"], "kN"),
                "Mfz": toSI(saisie["Mfz"], "kN.m"),
                "Mfy": toSI(saisie["Mfy"], "kN.m"),
                "Kt": saisie["Kt"],
                "Re": mat["Re"],
            },
        )
    )
    jour = solicitations.jourawski(sec, toSI(saisie["Ty"], "kN"))

    S, yG, zG = fromSI(P["S"], "mm^2"), fromSI(P["yG"], "mm"), fromSI(P["zG"], "mm")
    Iz, Iy = fromSI(P["Iz"], "mm^4"), fromSI(P["Iy"], "mm^4")
    entete = [
        f"Section : {_sectionLabel(sec)}",
        f"S = {S:.6g} mm² ; yG = {yG:.5g} mm ; zG = {zG:.5g} mm (repère O1, coin bas-gauche)",
        f"Iz = {Iz:.6g} mm⁴ ; Iy = {Iy:.6g} mm⁴ ; Iyz = {fromSI(P['Iyz'], 'mm^4'):.4g} mm⁴ ; "
        f"Ix = Iz + Iy = {fromSI(P['Ix'], 'mm^4'):.6g} mm⁴",
        f"Moments principaux : I1 = {fromSI(P['I1'], 'mm^4'):.6g} mm⁴, I2 = {fromSI(P['I2'], 'mm^4'):.6g} mm⁴, "
        f"angle = {math.degrees(P['alphaP']):.4g}°",
        f"Constante de torsion J = {fromSI(P['J'], 'mm^4'):.6g} mm⁴",
        f"rz = {fromSI(P['rz'], 'mm'):.5g} mm ; ry = {fromSI(P['ry'], 'mm'):.5g} mm ; "
        f"Wz = {fromSI(P['Wz'], 'mm^3'):.6g} mm³ ; Wy = {fromSI(P['Wy'], 'mm^3'):.6g} mm³",
        f"Facteurs de cisaillement : k = {P['k']:.4g} ; ky = {P['ky']:.4g} ({P['kSource']}) ; kz = {P['kz']:.4g}",
        f"Flexion : σ traction max = {fromSI(bend['sigmaMaxTraction'], 'MPa'):.5g} MPa ; "
        f"σ compression max = {fromSI(bend['sigmaMaxCompression'], 'MPa'):.5g} MPa ; "
        f"Kt·|σ|max = {fromSI(bend['sigmaMaxKt'], 'MPa'):.5g} MPa ({_okText(bend['ok'])})",
        f"Jourawski : τmax = {fromSI(jour['tauMax'], 'MPa'):.5g} MPa en y = {fromSI(jour['yAtMax'], 'mm'):.4g} mm ; "
        f"τmoy = {fromSI(jour['tauMoy'], 'MPa'):.5g} MPa",
    ]
    rapport = _rapport(
        entete,
        [
            ("=== Méthode A : analytique et Huygens ===", P["report"]),
            (f"=== Méthode B : {Bn['method']} ===", Bn["report"]),
            ("=== Comparaison des méthodes ===", C.attrs["report"]),
            ("=== Contraintes normales (flexion composée) ===", bend["report"]),
            ("=== Cisaillement (Jourawski) ===", jour["report"]),
        ],
    )
    tables = {"Comparaison des méthodes": _compareDisplay(C, extra)}
    if "huygens" in P:
        tables["Tableau de Huygens"] = _huygensDisplay(P["huygens"])
    result = {"sec": sec, "P": P, "Pint": Bn, "compare": C, "bend": bend, "jour": jour, "rapport": rapport}
    return {
        "result": result,
        "tables": tables,
        "status": f"S = {S:.5g} mm², Iz = {Iz:.5g} mm⁴, Iy = {Iy:.5g} mm⁴",
    }


# ------------------------------------------------------------------------------------------- Treillis


def defaultTrussInput() -> dict:
    """Saisie de l'onglet Treillis au démarrage : 5 nœuds, 7 barres, S235, S = 500 mm²."""
    dm = DataManager()
    return {
        "mat": "S235",
        "E": _materiau(dm, "S235", ["E"])["E"],
        "S": 500.0,
        "scale": 0.0,
        "nodes": [
            {"name": "A", "x": 0.0, "y": 0.0},
            {"name": "B", "x": 3.0, "y": 0.0},
            {"name": "C", "x": 6.0, "y": 0.0},
            {"name": "D", "x": 1.5, "y": 2.0},
            {"name": "E", "x": 4.5, "y": 2.0},
        ],
        "bars": [{"i": i, "j": j} for i, j in [(1, 2), (2, 3), (1, 4), (4, 2), (4, 5), (2, 5), (5, 3)]],
        "sup": [{"node": 1, "bx": True, "by": True}, {"node": 3, "bx": False, "by": True}],
        "loads": [
            {"node": 2, "Fx": 0.0, "Fy": -20.0},
            {"node": 4, "Fx": 0.0, "Fy": -10.0},
            {"node": 5, "Fx": 5.0, "Fy": -10.0},
        ],
    }


def _readTruss(T: dict) -> dict:
    """readTruss : saisie du treillis → modèle SI (numéros de nœuds à partir de 1, noms de nœuds)."""
    nd = T["nodes"]
    n = len(nd)
    if n < 2:
        raise MecaStructError(_ID, "Le treillis doit comporter au moins 2 nœuds.")
    names = [str(d["name"]).strip() or f"N{i + 1}" for i, d in enumerate(nd)]
    sup = np.zeros((n, 2), dtype=bool)
    for s in T["sup"]:
        j = int(s["node"]) - 1
        sup[j, 0] |= bool(s["bx"])
        sup[j, 1] |= bool(s["by"])
    loads = np.zeros((n, 2))
    for ld in T["loads"]:
        j = int(ld["node"]) - 1
        loads[j] += toSI([ld["Fx"], ld["Fy"]], "kN")
    return {
        "nodes": np.array([[d["x"], d["y"]] for d in nd], dtype=float),
        "bars": np.array([[b["i"], b["j"]] for b in T["bars"]], dtype=float),
        "E": toSI(T["E"], "GPa"),
        "S": toSI(T["S"], "mm^2"),
        "supports": sup,
        "loads": loads,
        "names": names,
    }


def computeTruss(saisie: dict, dm: DataManager) -> dict:
    """Treillis articulé plan : efforts dans les barres, réactions, déplacements (solveTruss).

    Entrées : `saisie` (defaultTrussInput) ; `dm` (non utilisé : le matériau est déjà dans E). Sortie : result (truss,
    tsol, rapport), tables « Barres », « Réactions », « Déplacements », status (h, nature, |N|max).
    """
    truss = _readTruss(saisie)
    tsol = truss_solver.solveTruss(truss)
    m = len(truss["bars"])
    nm = truss["names"]
    noeuds = [f"{nm[int(i) - 1]}–{nm[int(j) - 1]}" for i, j in truss["bars"]]
    sup = truss["supports"].any(axis=1)
    tables = {
        "Barres": pd.DataFrame(
            {
                "Barre": range(1, m + 1),
                "Nœuds": noeuds,
                "L (m)": tsol["L0"],
                "N (kN)": np.asarray(tsol["N"]) / 1e3,
                "Nature": tsol["nature"],
                "σ (MPa)": np.asarray(tsol["sigma"]) / 1e6,
                "ΔL (mm)": np.asarray(tsol["dL"]) * 1e3,
            }
        ),
        "Réactions": pd.DataFrame(
            {
                "Nœud": [nm[i] for i in np.flatnonzero(sup)],
                "Rx (kN)": tsol["reactions"][sup, 0] / 1e3,
                "Ry (kN)": tsol["reactions"][sup, 1] / 1e3,
            }
        ),
        "Déplacements": pd.DataFrame(
            {
                "Nœud": nm,
                "ux (mm)": tsol["displacements"][:, 0] * 1e3,
                "uy (mm)": tsol["displacements"][:, 1] * 1e3,
            }
        ),
    }
    if tsol["mechanism"]:
        hTxt = "mécanisme, chargement compatible : déplacements non uniques (norme minimale)"
    elif tsol["isostatic"]:
        hTxt = "isostatique"
    elif tsol["h"] > 0:
        hTxt = "hyperstatique"
    else:
        hTxt = "hypostatique"
    iMax = int(np.argmax(np.abs(tsol["N"])))
    nMax = abs(float(tsol["N"][iMax]))
    entete = [
        f"Treillis plan : {len(truss['nodes'])} nœuds, {m} barres ; h = m + r − 2n = {tsol['h']} ({hTxt}) ; "
        f"méthode : {tsol['methodUsed']}",
        f"Effort maximal : |N| = {nMax / 1e3:.5g} kN dans la barre {iMax + 1} ({noeuds[iMax]}) ; "
        f"σ = {tsol['sigma'][iMax] / 1e6:.5g} MPa",
    ]
    result = {
        "truss": truss,
        "tsol": tsol,
        "rapport": _rapport(entete, [("=== Démarche (moteur, SI) ===", tsol["report"])]),
    }
    return {"result": result, "tables": tables, "status": f"h = {tsol['h']} ({hTxt}) — |N|max = {nMax / 1e3:.4g} kN"}


# ------------------------------------------------------------------------------------------ Expression S(x)

_FONCTIONS = {
    "sqrt": np.sqrt,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "abs": np.abs,
}
_OPERATIONS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


def _evalExpr(noeud, x):
    """Évalue l'arbre d'une expression autorisée (nombres, x, pi, + - * / ^, fonctions usuelles) sur x."""
    if isinstance(noeud, ast.Expression):
        return _evalExpr(noeud.body, x)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)) and not isinstance(noeud.value, bool):
        return noeud.value
    if isinstance(noeud, ast.Name) and noeud.id == "x":
        return x
    if isinstance(noeud, ast.Name) and noeud.id == "pi":
        return math.pi
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.UAdd, ast.USub)):
        v = _evalExpr(noeud.operand, x)
        return -v if isinstance(noeud.op, ast.USub) else v
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPERATIONS:
        return _OPERATIONS[type(noeud.op)](_evalExpr(noeud.left, x), _evalExpr(noeud.right, x))
    if (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id in _FONCTIONS
        and len(noeud.args) == 1
        and not noeud.keywords
    ):
        return _FONCTIONS[noeud.func.id](_evalExpr(noeud.args[0], x))
    raise MecaStructError(_ID_EXPR, "Construction non autorisée dans l'expression.")


def parseFunction(expr: str):
    """Expression texte en fonction vectorisée f(x), sans exécuter de code (analyse de l'arbre syntaxique).

    Entrée : `expr` (300 caractères au plus) : nombres, x, pi, sqrt, exp, log, log10, sin, cos, tan, abs, + - * / ^
    et parenthèses. Sortie : f(x) de la taille de x. Erreur : MecaStruct:App:invalidExpression.
    """
    e = str(expr).strip()
    if not e:
        raise MecaStructError(_ID_EXPR, "Expression vide.")
    if len(e) > 300:
        raise MecaStructError(_ID_EXPR, "Expression trop longue (300 caractères au plus).")
    try:
        arbre = ast.parse(e.replace("^", "**"), mode="eval")  # ^ = puissance, comme en MATLAB
    except SyntaxError as err:
        raise MecaStructError(_ID_EXPR, f"Expression invalide « {e} ».") from err
    noms = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
    interdits = noms - {"x", "pi", *_FONCTIONS}
    if interdits:
        raise MecaStructError(_ID_EXPR, f"Identificateur non autorisé : « {', '.join(sorted(interdits))} ».")
    with np.errstate(all="ignore"):
        _evalExpr(arbre, np.linspace(0.0, 1.0, 3))  # rejette ici les constructions interdites
    return lambda x: _evalExpr(arbre, np.asarray(x, dtype=float)) + np.zeros(np.shape(x))


# ------------------------------------------------------------------------------------------ Traction


def defaultTractionInput() -> dict:
    """Saisie de l'onglet Traction au démarrage : N = 50 kN, barre droite de 1 m en S235, section constante."""
    dm = DataManager()
    return {
        "N": 50.0,
        "S0": 314.159,
        "L0": 1.0,
        "mat": "S235",
        **_materiau(dm, "S235", ["E", "nu", "alpha", "Re"]),
        "dT": 0.0,
        "Kt": 1.0,
        "s": 1.5,
        "dLmax": 0.0,
        "varS": False,
        "Sexpr": "pi/4*(20 + 10*x)^2",
    }


def computeTraction(saisie: dict, dm: DataManager) -> dict:
    """Traction/compression : σ(x), ΔL par 3 méthodes, rigidité ; section variable S(x) si demandée.

    Entrées : `saisie` (defaultTractionInput) ; `dm` (non utilisé, le matériau est déjà dans E, nu, alpha, Re).
    Sortie : result (moteur + rapport), tables « Synthèse », status (σmax, ΔL intégrale).
    """
    T = saisie
    p = {
        "N": toSI(T["N"], "kN"),
        "S0": toSI(T["S0"], "mm^2"),
        "L0": T["L0"],
        "E": toSI(T["E"], "GPa"),
        "nu": T["nu"],
        "alpha": toSI(T["alpha"], "1e-6/°C"),
        "dT": T["dT"],
        "Kt": T["Kt"],
        "Re": toSI(T["Re"], "MPa"),
        "s": T["s"],
    }
    if T["dLmax"] > 0:
        p["dLmax"] = toSI(T["dLmax"], "mm")
    if T["varS"]:
        fS = parseFunction(T["Sexpr"])
        x = np.linspace(0.0, p["L0"], 201)
        Sx = toSI(fS(x), "mm^2")
        if not np.all(np.isfinite(Sx)) or np.any(Sx <= 0):
            raise MecaStructError(_ID_EXPR, "S(x) doit être réelle, finie et strictement positive sur [0, L0].")
        p["Sfun"] = lambda xx: toSI(fS(xx), "mm^2")
    r = solicitations.traction(p)
    vals = [r["dL"]["analytique"], r["dL"]["integrale"], r["dL"]["energetique"]]
    tables = {
        "Synthèse": _kvTable(
            [
                ("σ nominale = N/S0", fromSI(r["sigmaNom"], "MPa"), "MPa"),
                ("σ max = Kt·σ", fromSI(r["sigmaMax"], "MPa"), "MPa"),
                ("σadm = Re/s", fromSI(r["sigmaAdm"], "MPa"), "MPa"),
                ("Résistance", r["okResistance"], ""),
                ("εxx", r["epsxx"] * 1e6, "µdéf"),
                ("εyy = εzz", r["epsyy"] * 1e6, "µdéf"),
                ("ΔV/V0", r["dVsurV"], "-"),
                ("ΔL analytique", vals[0] * 1e3, "mm"),
                ("ΔL intégrale", vals[1] * 1e3, "mm"),
                ("ΔL énergétique (Castigliano)", vals[2] * 1e3, "mm"),
                ("Raideur K = E S0/L0", r["K"] / 1e6, "kN/mm"),
                ("Énergie U", r["U"], "J"),
                ("Rigidité (ΔL ≤ ΔLmax)", r["okRigidite"], ""),
            ]
        )
    }
    entete = [
        f"σmax = {fromSI(r['sigmaMax'], 'MPa'):.5g} MPa ({_okText(r['okResistance'])}) ; "
        f"ΔL = {vals[0] * 1e3:.5g} mm (analytique) / {vals[1] * 1e3:.5g} mm (intégrale) / "
        f"{vals[2] * 1e3:.5g} mm (énergétique)"
    ]
    result = {**r, "rapport": _rapport(entete, [("=== Démarche (moteur, SI) ===", r["report"])])}
    return {
        "result": result,
        "tables": tables,
        "status": f"σmax = {fromSI(r['sigmaMax'], 'MPa'):.4g} MPa ({_okText(r['okResistance'])}) — "
        f"ΔL = {vals[1] * 1e3:.4g} mm",
    }


# ------------------------------------------------------------------------------- Cisaillement & matage


def defaultShearInput() -> dict:
    """Saisie de l'onglet Cisaillement au démarrage : T = 10 kN en S235, clavette et goupille de l'exemple d'école.

    Le matage prend la 2e ligne de la table de matage (comme l'exemple MATLAB) ; la section est celle de Sections.
    """
    dm = DataManager()
    return {
        "mat": "S235",
        **_materiau(dm, "S235", ["Re", "G"]),
        "crit": "Tresca",
        "s": 1.5,
        "T": 10.0,
        "S": 100.0,
        "k": 1.5,
        "Fm": 10.0,
        "Sm": 200.0,
        "Padm": dm.BearingPressures["Pmin"].iloc[1] / 1e6,
        "C": 0.2,
        "Dk": 30.0,
        "ak": 10.0,
        "bk": 8.0,
        "Lk": 40.0,
        "Fp": 2.0,
        "dp": 8.0,
        "ep": 12.0,
        "np": 2,
        "section": _sectionFromSaisie(defaultSectionInput(), dm),
    }


def computeShear(saisie: dict, dm: DataManager) -> dict:
    """Cisaillement simple, répartition de Jourawski (section de Sections) et matage P = F/S.

    Sortie : result (shear, jour, bearing, rapport), tables « Synthèse », status (τmax, P).
    """
    C = saisie
    p = {"Re": toSI(C["Re"], "MPa"), "criterion": C["crit"], "s": C["s"]}
    p.update(T=toSI(C["T"], "kN"), S=toSI(C["S"], "mm^2"), k=C["k"], G=toSI(C["G"], "GPa"))
    r = solicitations.shear(p)
    sec = C["section"]
    jour = solicitations.jourawski(sec, p["T"])
    b = solicitations.bearing(
        {"F": toSI(C["Fm"], "kN"), "Smatee": toSI(C["Sm"], "mm^2"), "Padm": toSI(C["Padm"], "MPa")}
    )
    tables = {
        "Synthèse": _kvTable(
            [
                ("τmoy = T/S", r["tauMoy"] / 1e6, "MPa"),
                ("τmax = k·T/S", r["tauMax"] / 1e6, "MPa"),
                ("τe", r["tauE"] / 1e6, "MPa"),
                ("τadm = τe/s", r["tauAdm"] / 1e6, "MPa"),
                ("Cisaillement", r["ok"], ""),
                ("Glissement γ", r["gamma"] * 1e3, "mrad"),
                ("Jourawski : τmax (section de l'onglet Sections)", jour["tauMax"] / 1e6, "MPa"),
                ("Jourawski : k = τmax·S/T", jour["kNum"], "-"),
                ("Matage : P = F/S", b["P"] / 1e6, "MPa"),
                ("Matage", b["ok"], ""),
                ("Surface matée minimale", b["SminRequired"] * 1e6, "mm²"),
            ]
        )
    }
    entete = [
        f"τmax = {r['tauMax'] / 1e6:.5g} MPa ≤ τadm = {r['tauAdm'] / 1e6:.5g} MPa : {_okText(r['ok'])} ; "
        f"matage P = {b['P'] / 1e6:.5g} MPa : {_okText(b['ok'])}"
    ]
    rapport = _rapport(
        entete,
        [
            ("=== Cisaillement simple ===", r["report"]),
            ("=== Jourawski ===", jour["report"]),
            ("=== Matage ===", b["report"]),
        ],
    )
    result = {"shear": r, "jour": jour, "bearing": b, "rapport": rapport}
    return {
        "result": result,
        "tables": tables,
        "status": f"τmax = {r['tauMax'] / 1e6:.4g} MPa ({_okText(r['ok'])}) — P = {b['P'] / 1e6:.4g} MPa "
        f"({_okText(b['ok'])})",
    }


def computeKey(saisie: dict, dm: DataManager) -> dict:
    """Clavette parallèle : matage P = 4C/(D b L) et cisaillement τ = 2C/(a L D), ou longueur minimale si L = 0."""
    C = saisie
    p = {"Re": toSI(C["Re"], "MPa"), "criterion": C["crit"], "s": C["s"]}
    p.update(
        C=toSI(C["C"], "kN.m"),
        D=toSI(C["Dk"], "mm"),
        a=toSI(C["ak"], "mm"),
        b=toSI(C["bk"], "mm"),
        Padm=toSI(C["Padm"], "MPa"),
    )
    if C["Lk"] > 0:
        p["L"] = toSI(C["Lk"], "mm")
    r = solicitations.keyDesign(p)
    rows = [
        ("Effort tangentiel F = 2C/D", r["F"] / 1e3, "kN"),
        ("L min (matage)", r["LminMatage"] * 1e3, "mm"),
        ("L min (cisaillement)", r["LminCis"] * 1e3, "mm"),
        ("L min retenue", r["Lmin"] * 1e3, "mm"),
        ("τadm", r["tauAdm"] / 1e6, "MPa"),
    ]
    if "P" in r:
        rows += [
            ("P = 4C/(D b L)", r["P"] / 1e6, "MPa"),
            ("Matage", r["okP"], ""),
            ("τ = 2C/(a L D)", r["tau"] / 1e6, "MPa"),
            ("Cisaillement", r["okTau"], ""),
        ]
        head = (
            f"Clavette L = {p['L'] * 1e3:.4g} mm : P = {r['P'] / 1e6:.5g} MPa ({_okText(r['okP'])}), "
            f"τ = {r['tau'] / 1e6:.5g} MPa ({_okText(r['okTau'])}) ; Lmin = {r['Lmin'] * 1e3:.4g} mm"
        )
    else:
        head = f"Clavette : longueur minimale Lmin = {r['Lmin'] * 1e3:.4g} mm"
    return {
        "result": {**r, "rapport": _rapport([head], [("=== Clavette parallèle (moteur, SI) ===", r["report"])])},
        "tables": {"Synthèse": _kvTable(rows)},
        "status": head,
    }


def computePin(saisie: dict, dm: DataManager) -> dict:
    """Goupille / rivet : P = 2F/(d e) ≤ Padm et τ = 4F/(n π d²) ≤ τadm."""
    C = saisie
    p = {"Re": toSI(C["Re"], "MPa"), "criterion": C["crit"], "s": C["s"]}
    p.update(
        F=toSI(C["Fp"], "kN"),
        d=toSI(C["dp"], "mm"),
        e=toSI(C["ep"], "mm"),
        Padm=toSI(C["Padm"], "MPa"),
        nShear=C["np"],
    )
    r = solicitations.pinDesign(p)
    head = (
        f"Goupille : P = {r['P'] / 1e6:.5g} MPa ({_okText(r['okP'])}), "
        f"τ = {r['tau'] / 1e6:.5g} MPa ({_okText(r['okTau'])})"
    )
    rows = [
        ("P = 2F/(d e)", r["P"] / 1e6, "MPa"),
        ("Matage", r["okP"], ""),
        ("τ = 4F/(n π d²)", r["tau"] / 1e6, "MPa"),
        ("τadm", r["tauAdm"] / 1e6, "MPa"),
        ("Cisaillement", r["okTau"], ""),
        ("d minimal", r["dMin"] * 1e3, "mm"),
        ("e minimale", r["eMin"] * 1e3, "mm"),
    ]
    return {
        "result": {**r, "rapport": _rapport([head], [("=== Goupille / rivet (moteur, SI) ===", r["report"])])},
        "tables": {"Synthèse": _kvTable(rows)},
        "status": head,
    }


# ---------------------------------------------------------------------------------------------- Torsion


def defaultTorsionInput() -> dict:
    """Saisie de l'onglet Torsion au démarrage : arbre plein Ø40 mm, L = 1 m, Mt = 0,5 kN·m, S235."""
    dm = DataManager()
    return {
        "Mt": 0.5,
        "D": 40.0,
        "d": 0.0,
        "L": 1.0,
        "mat": "S235",
        **_materiau(dm, "S235", ["G", "Re"]),
        "crit": "Tresca",
        "s": 1.5,
        "Kt": 1.0,
        "thetaAdm": 0.25,
    }


def computeTorsion(saisie: dict, dm: DataManager) -> dict:
    """Torsion d'un arbre circulaire plein ou creux : τmax, θ, φ par 3 méthodes, raideur.

    Sortie : result (moteur + rapport), tables « Synthèse », status (τmax, θ, φ).
    """
    T = saisie
    p = {
        "Mt": toSI(T["Mt"], "kN.m"),
        "D": toSI(T["D"], "mm"),
        "d": toSI(T["d"], "mm"),
        "G": toSI(T["G"], "GPa"),
        "L": T["L"],
        "Kt": T["Kt"],
        "Re": toSI(T["Re"], "MPa"),
        "criterion": T["crit"],
        "s": T["s"],
    }
    if T["thetaAdm"] > 0:
        p["thetaAdm"] = toSI(T["thetaAdm"], "deg/m")
    r = solicitations.torsion(p)
    head = (
        f"τmax = {r['tauMax'] / 1e6:.5g} MPa ({_okText(r['okResistance'])}) ; "
        f"θ = {math.degrees(r['theta']):.4g} °/m ({_okText(r['okRigidite'])}) ; "
        f"φ = {r['phi']['analytique'] * 1e3:.5g} mrad"
    )
    rows = [
        ("Ix = π(D⁴ − d⁴)/32", r["Ix"] * 1e12, "mm⁴"),
        ("τmax nominale", r["tauMaxNom"] / 1e6, "MPa"),
        ("τmax = Kt·τ", r["tauMax"] / 1e6, "MPa"),
        ("τadm", r["tauAdm"] / 1e6, "MPa"),
        ("Résistance", r["okResistance"], ""),
        ("θ = Mt/(G Ix)", math.degrees(r["theta"]), "°/m"),
        ("Rigidité", r["okRigidite"], ""),
        ("φ analytique", r["phi"]["analytique"] * 1e3, "mrad"),
        ("φ intégrale", r["phi"]["integrale"] * 1e3, "mrad"),
        ("φ énergétique", r["phi"]["energetique"] * 1e3, "mrad"),
        ("Raideur K = G Ix/L", r["Ktorsion"] / 1e3, "kN·m/rad"),
        ("Énergie U", r["U"], "J"),
    ]
    return {
        "result": {**r, "rapport": _rapport([head], [("=== Démarche (moteur, SI) ===", r["report"])])},
        "tables": {"Synthèse": _kvTable(rows)},
        "status": head,
    }


# ----------------------------------------------------------------------------------------------- Flexion


def defaultBendingInput() -> dict:
    """Saisie de l'onglet Flexion au démarrage : N = 10 kN, Mfz = 15 kN·m, Mfy = 2 kN·m, S235, section de Sections."""
    dm = DataManager()
    return {
        "N": 10.0,
        "Mfz": 15.0,
        "Mfy": 2.0,
        "Kt": 1.0,
        "s0": 3.0,
        "s": 1.5,
        "mat": "S235",
        **_materiau(dm, "S235", ["Re"]),
        "section": _sectionFromSaisie(defaultSectionInput(), dm),
    }


def computeBending(saisie: dict, dm: DataManager) -> dict:
    """Contraintes normales de flexion composée dans la section de Sections : σmax, axe neutre (rapport)."""
    F = saisie
    sec = F["section"]
    P = geometry.analytical(sec)
    bend = solicitations.bendingStress(
        _stressGeometry(
            sec,
            {
                "N": toSI(F["N"], "kN"),
                "Mfz": toSI(F["Mfz"], "kN.m"),
                "Mfy": toSI(F["Mfy"], "kN.m"),
                "Kt": F["Kt"],
                "Re": toSI(F["Re"], "MPa"),
                "s": F["s"],
            },
        )
    )
    head = (
        f"σ = {bend['sigmaMaxTraction'] / 1e6:.5g} / {bend['sigmaMaxCompression'] / 1e6:.5g} MPa ; "
        f"Kt·|σ|max = {bend['sigmaMaxKt'] / 1e6:.5g} MPa ≤ {bend['sigmaAdm'] / 1e6:.5g} MPa : "
        f"{_okText(bend['ok'])}"
    )
    rows = [
        ("σ traction max", bend["sigmaMaxTraction"] / 1e6, "MPa"),
        ("σ compression max", bend["sigmaMaxCompression"] / 1e6, "MPa"),
        ("|σ|max", bend["sigmaMaxAbs"] / 1e6, "MPa"),
        ("Kt·|σ|max", bend["sigmaMaxKt"] / 1e6, "MPa"),
        ("σadm = Re/s", bend["sigmaAdm"] / 1e6, "MPa"),
        ("Résistance", bend["ok"], ""),
        ("Formule générale (Iyz ≠ 0)", bend["usedGeneralFormula"], ""),
    ]
    entete = [
        head,
        f"Section : {_sectionLabel(sec)}",
        _effortReading(F["N"], F["Mfz"], F["Mfy"]),
    ]
    return {
        "result": {
            "sec": sec,
            "P": P,
            "bend": bend,
            "rapport": _rapport(entete, [("=== Démarche (moteur, SI) ===", bend["report"])]),
        },
        "tables": {"Synthèse": _kvTable(rows)},
        "status": head,
    }


# -------------------------------------------------------------------------------------------- Flambage


def defaultBucklingInput() -> dict:
    """Saisie de l'onglet Flambage au démarrage : HEA 200 articulée (L = 4 m, P = 300 kN) en S235."""
    dm = DataManager()
    p = dm.getProfile("HEA", "HEA 200")
    return {
        "fam": "HEA",
        "prof": "HEA 200",
        "S": p["S"] * 1e6,
        "Iz": p["Iz"] * 1e12,
        "Iy": p["Iy"] * 1e12,
        "mat": "S235",
        **_materiau(dm, "S235", ["E", "Re"]),
        "L": 4.0,
        "cond": "articule-articule",
        "P": 300.0,
        "s": 2.0,
    }


def computeBuckling(saisie: dict, dm: DataManager) -> dict:
    """Flambage : arbre de décision (compression, Rankine, Euler), courbe de stabilité et mode propre.

    P = 0 : aucune charge appliquée ; P < 0 (compression) : le moteur retient |P|.
    Sortie : result (analysis, curve, rapport), tables « Synthèse », status (λ, régime, Pcrit, Padm).
    """
    F = saisie
    p = {
        "E": toSI(F["E"], "GPa"),
        "Re": toSI(F["Re"], "MPa"),
        "S": toSI(F["S"], "mm^2"),
        "Iz": toSI(F["Iz"], "mm^4"),
        "Iy": toSI(F["Iy"], "mm^4"),
        "L": F["L"],
        "condition": F["cond"],
        "s": F["s"],
    }
    if F["P"] != 0:
        p["P"] = toSI(F["P"], "kN")
    b = buckling.analyze(p)
    c = buckling.stabilityCurve(p["E"], p["Re"], np.arange(0.0, max(300, math.ceil(1.2 * b["lambda"])) + 0.5, 0.5))
    rows = [
        ("Imin", b["Imin"] * 1e12, "mm⁴"),
        ("Axe de flambement", b["axis"], ""),
        ("rmin", b["rmin"] * 1e3, "mm"),
        ("Longueur de flambage L'", b["Lp"], "m"),
        ("Élancement λ", b["lambda"], "-"),
        ("λlim = π√(E/Re)", b["lambdaLim"], "-"),
        ("Régime", b["regime"], ""),
        ("PC = Re·S", b["PC"] / 1e3, "kN"),
        ("PE (Euler)", b["PE"] / 1e3, "kN"),
        ("PR (Rankine)", b["PR"] / 1e3, "kN"),
        ("Pcrit retenue", b["Pcrit"] / 1e3, "kN"),
        ("Padm = Pcrit/s", b["Padm"] / 1e3, "kN"),
    ]
    head = (
        f"λ = {b['lambda']:.4g} (λlim = {b['lambdaLim']:.4g}) : régime {b['regime']} — "
        f"Pcrit = {b['Pcrit'] / 1e3:.5g} kN, Padm = {b['Padm'] / 1e3:.5g} kN"
    )
    if math.isfinite(b["P"]):
        rows += [
            ("P appliquée", b["P"] / 1e3, "kN"),
            ("σ appliquée", b["sigmaApplied"] / 1e6, "MPa"),
            ("Stabilité (P ≤ Padm)", bool(b["ok"]), ""),
        ]
        head += f" — P = {b['P'] / 1e3:.5g} kN : {_okText(bool(b['ok']))}"
    result = {
        "analysis": b,
        "curve": c,
        "rapport": _rapport(
            [head],
            [("=== Démarche (moteur, SI) ===", b["report"]), ("=== Courbe de stabilité ===", c["report"])],
        ),
    }
    return {"result": result, "tables": {"Synthèse": _kvTable(rows)}, "status": head}


# --------------------------------------------------------------------------------------------- Tenseurs


def defaultTensorInput() -> dict:
    """Saisie de l'onglet Tenseurs au démarrage : tenseur de l'exemple, facette θ = 30°, S235 avec s = 1,5."""
    dm = DataManager()
    return {
        "sig": [[80.0, 30.0, 0.0], [30.0, -40.0, 0.0], [0.0, 0.0, 20.0]],
        "fmode": "theta",
        "theta": 30.0,
        "nx": 1.0,
        "ny": 1.0,
        "nz": 0.0,
        "mat": "S235",
        **_materiau(dm, "S235", ["Re", "Rm"]),
        "s": 1.5,
    }


def computeTensor(saisie: dict, dm: DataManager) -> dict:
    """Tenseur des contraintes : principales, facette, Mohr 2D et 3D, critères (Tresca, Von Mises, Rankine).

    Entrée : `sig` (3×3, MPa) ; `fmode` = 'theta' (angle dans le plan x, y) ou 'n' (normale nx, ny, nz).
    Rm nul ou absent : le moteur prend Re. Erreurs : MecaStruct:App:invalidTensor, MecaStruct:App:invalidNormal.
    """
    T = saisie
    sig = np.array(T["sig"], dtype=float)
    if sig.shape != (3, 3) or not np.all(np.isfinite(sig)):
        raise MecaStructError(
            "MecaStruct:App:invalidTensor", "Le tenseur doit être une matrice 3×3 de réels finis (MPa)."
        )
    sig = toSI((sig + sig.T) / 2, "MPa")
    if T["fmode"] == "theta":
        th = math.radians(T["theta"])
        n = np.array([math.cos(th), math.sin(th), 0.0])
    else:
        n = np.array([T["nx"], T["ny"], T["nz"]], dtype=float)
        if np.linalg.norm(n) == 0:
            raise MecaStructError("MecaStruct:App:invalidNormal", "La normale n ne doit pas être nulle.")
        th = math.atan2(n[1], n[0])
    Re = toSI(T["Re"], "MPa")
    Rm = toSI(T["Rm"], "MPa") if T["Rm"] > 0 else math.nan
    pr = tensors.principal(sig)
    fa = tensors.facet(sig, n)
    r2 = tensors.plane2D(sig[0, 0], sig[1, 1], sig[0, 1], th)
    p3 = np.array([pr["sigmaI"], pr["sigmaII"], pr["sigmaIII"]])
    m3 = tensors.mohr3D(p3)
    cr = tensors.criteria(p3, Re, T["s"], Rm)
    lo = tensors.yieldLoci(Re, T["s"], Rm)
    if np.all(np.abs(sig[2, :]) <= 1e-12 * max(1.0, np.abs(sig).max())):
        ptTxt = "état plan : (σ1, σ2) du plan (x, y)"
    else:
        ptTxt = "état triaxial : point (σI − σII, σIII − σII), même σeq Tresca et Von Mises (pas Rankine)"
    dirs = np.asarray(pr["directions"])
    tables = {
        "Principales": pd.DataFrame(
            {
                "Contrainte": ["σI", "σII", "σIII"],
                "Valeur (MPa)": p3 / 1e6,
                "nx": dirs[0, :],
                "ny": dirs[1, :],
                "nz": dirs[2, :],
            }
        ),
        "Critères": pd.DataFrame(
            {
                "Critère": ["Tresca", "Von Mises", "Contrainte normale max"],
                "σ équivalente (MPa)": np.array([cr["sigmaEqTresca"], cr["sigmaEqVM"], cr["sigmaMaxNormal"]]) / 1e6,
                "σ admissible (MPa)": np.array([cr["sigmaAdm"], cr["sigmaAdm"], cr["sigmaRAdm"]]) / 1e6,
                "Coefficient obtenu": [cr["sfTresca"], cr["sfVM"], cr["sfRankine"]],
                "Vérification": [_okText(cr["okTresca"]), _okText(cr["okVM"]), _okText(cr["okRankine"])],
            }
        ),
        "Facette": _kvTable(
            [
                ("Normale n", f"({n[0]:.4g} ; {n[1]:.4g} ; {n[2]:.4g})", ""),
                ("Cn = σ·n", f"({fa['Cn'][0] / 1e6:.5g} ; {fa['Cn'][1] / 1e6:.5g} ; {fa['Cn'][2] / 1e6:.5g})", "MPa"),
                ("σn = Cn·n", fa["sigmaN"] / 1e6, "MPa"),
                ("|τ|", fa["tauNorm"] / 1e6, "MPa"),
                ("σ(θ) plan (x,y)", r2["sigma"] / 1e6, "MPa"),
                ("τ(θ) plan (x,y)", r2["tau"] / 1e6, "MPa"),
                ("θ", math.degrees(th), "°"),
            ]
        ),
    }
    head = (
        f"σI = {p3[0] / 1e6:.5g}, σII = {p3[1] / 1e6:.5g}, σIII = {p3[2] / 1e6:.5g} MPa ; "
        f"Tresca {cr['sigmaEqTresca'] / 1e6:.5g} MPa, Von Mises {cr['sigmaEqVM'] / 1e6:.5g} MPa "
        f"(σadm = {cr['sigmaAdm'] / 1e6:.5g} MPa) : {_okText(cr['okTresca'])} / {_okText(cr['okVM'])}"
    )
    entete = [head, f"Lieu de plasticité : {ptTxt}"]
    result = {
        "principal": pr,
        "facet": fa,
        "plane2D": r2,
        "mohr3D": m3,
        "criteria": cr,
        "loci": lo,
        "rapport": _rapport(
            entete,
            [
                ("=== Contraintes principales ===", pr["report"]),
                ("=== Facette ===", fa["report"]),
                ("=== Mohr plan (x, y) ===", r2["report"]),
                ("=== Critères ===", cr["report"]),
            ],
        ),
    }
    status = (
        f"σI = {p3[0] / 1e6:.4g} MPa, σIII = {p3[2] / 1e6:.4g} MPa — VM = {cr['sigmaEqVM'] / 1e6:.4g} MPa "
        f"({_okText(cr['okVM'])})"
    )
    return {"result": result, "tables": tables, "status": status}


# ------------------------------------------------------------------------------------- Hooke & jauges


def defaultHookeInput() -> dict:
    """Saisie de l'onglet Hooke au démarrage : loi 3D isotrope, S235, contraintes et déformations de l'exemple."""
    dm = DataManager()
    return {
        "mode": "iso3D",
        "mat": "S235",
        **_materiau(dm, "S235", ["E", "nu", "alpha"]),
        "dT": 0.0,
        "sxx": 100.0,
        "syy": 50.0,
        "szz": 0.0,
        "syz": 0.0,
        "sxz": 0.0,
        "sxy": 30.0,
        "exx": 500.0,
        "eyy": -150.0,
        "gxy": 200.0,
        "E1": 140.0,
        "E2": 10.0,
        "E3": 10.0,
        "nu12": 0.3,
        "nu13": 0.3,
        "nu23": 0.4,
        "G12": 5.0,
        "G13": 5.0,
        "G23": 3.6,
    }


def computeHooke(saisie: dict, dm: DataManager) -> dict:
    """Loi de Hooke : 3D isotrope, contraintes planes, déformations planes ou orthotrope ; Mohr des déformations.

    Sortie : result (mode, exx, eyy, exy, mohr, rapport), tables « Résultats » et « Matrice » (rigidité ou
    souplesse réduite en GPa), status (ε1, ε2 en µdéf).
    """
    K = saisie
    E = toSI(K["E"], "GPa")
    nu = K["nu"]
    voigt = ["xx", "yy", "zz", "yz", "xz", "xy"]
    sigV = toSI([K["sxx"], K["syy"], K["szz"], K["syz"], K["sxz"], K["sxy"]], "MPa")
    if K["mode"] == "iso3D":
        e = hooke_gauges.hooke3D(sigV, E, nu, toSI(K["alpha"], "1e-6/°C"), K["dT"])
        Cm = hooke_gauges.stiffnessIsotropic(E, nu)
        res = pd.DataFrame({"Déformation": ["εxx", "εyy", "εzz", "γyz", "γxz", "γxy"], "Valeur (µdéf)": e * 1e6})
        mat = pd.DataFrame(Cm / 1e9, index=voigt, columns=voigt)
        exx, eyy, exy = e[0], e[1], e[5] / 2
        rep = [
            "Loi de Hooke 3D isotrope : {ε} = [S]{σ} + αΔT{1 1 1 0 0 0} (glissements ingénieur).",
            f"εxx = {e[0] * 1e6:.5g}, εyy = {e[1] * 1e6:.5g}, εzz = {e[2] * 1e6:.5g} µdéf ; "
            f"γyz = {e[3] * 1e6:.5g}, γxz = {e[4] * 1e6:.5g}, γxy = {e[5] * 1e6:.5g} µdéf",
            "Table « Matrice » : rigidité [C] en GPa (notation de Voigt).",
        ]
    elif K["mode"] == "planeStress":
        r = hooke_gauges.planeStress(sigV[0], sigV[1], sigV[5], E, nu)
        res = pd.DataFrame(
            {
                "Déformation": ["εxx", "εyy", "εzz", "γxy"],
                "Valeur (µdéf)": np.array([r["exx"], r["eyy"], r["ezz"], r["gxy"]]) * 1e6,
            }
        )
        mat = pd.DataFrame(r["Qred"] / 1e9, index=["xx", "yy", "xy"], columns=["xx", "yy", "xy"])
        exx, eyy, exy = r["exx"], r["eyy"], r["gxy"] / 2
        rep = ["Contraintes planes (σzz = σxz = σyz = 0) ; table « Matrice » : [Q] réduite en GPa.", *r["report"]]
    elif K["mode"] == "planeStrain":
        exx, eyy, gxy = K["exx"] * 1e-6, K["eyy"] * 1e-6, K["gxy"] * 1e-6
        r = hooke_gauges.planeStrain(exx, eyy, gxy, E, nu)
        res = pd.DataFrame(
            {
                "Contrainte": ["σxx", "σyy", "σxy", "σzz"],
                "Valeur (MPa)": np.array([r["sxx"], r["syy"], r["sxy"], r["szz"]]) / 1e6,
            }
        )
        mat = pd.DataFrame(r["Cred"] / 1e9, index=["xx", "yy", "xy"], columns=["xx", "yy", "xy"])
        exy = gxy / 2
        rep = [
            "Déformations planes (εzz = 0 ⇒ σzz = ν(σxx + σyy)) ; table « Matrice » : [C] réduite en GPa.",
            *r["report"],
        ]
    elif K["mode"] == "ortho":
        c = {
            "E1": toSI(K["E1"], "GPa"),
            "E2": toSI(K["E2"], "GPa"),
            "E3": toSI(K["E3"], "GPa"),
            "nu12": K["nu12"],
            "nu13": K["nu13"],
            "nu23": K["nu23"],
            "G12": toSI(K["G12"], "GPa"),
            "G13": toSI(K["G13"], "GPa"),
            "G23": toSI(K["G23"], "GPa"),
        }
        e = hooke_gauges.complianceOrthotropic(c) @ sigV
        Cm = hooke_gauges.stiffnessOrthotropic(c)
        res = pd.DataFrame({"Déformation": ["ε11", "ε22", "ε33", "γ23", "γ13", "γ12"], "Valeur (µdéf)": e * 1e6})
        mat = pd.DataFrame(Cm / 1e9, index=voigt, columns=voigt)
        exx, eyy, exy = e[0], e[1], e[5] / 2
        rep = [
            "Matériau orthotrope (9 constantes) : {ε} = [S]{σ}, axes d'orthotropie 1, 2, 3 = x, y, z.",
            f"ε11 = {e[0] * 1e6:.5g}, ε22 = {e[1] * 1e6:.5g}, ε33 = {e[2] * 1e6:.5g} µdéf ; "
            f"γ23 = {e[3] * 1e6:.5g}, γ13 = {e[4] * 1e6:.5g}, γ12 = {e[5] * 1e6:.5g} µdéf",
            "Table « Matrice » : rigidité [C] en GPa (symétrique, définie positive).",
        ]
    else:
        raise MecaStructError("MecaStruct:App:invalidMode", "Mode de loi de Hooke inconnu.")
    r2 = tensors.plane2DStrain(exx, eyy, exy, 0)
    result = {
        "mode": K["mode"],
        "exx": exx,
        "eyy": eyy,
        "exy": exy,
        "mohr": r2,
        "rapport": _rapport(rep, [("=== Mohr des déformations (plan x, y) ===", r2["report"])]),
    }
    return {
        "result": result,
        "tables": {"Résultats": res, "Matrice": mat},
        "status": f"ε1 = {r2['sigma1'] * 1e6:.5g} µdéf, ε2 = {r2['sigma2'] * 1e6:.5g} µdéf",
    }


def defaultGaugesInput() -> dict:
    """Saisie de l'onglet Jauges au démarrage : jauge K = 2,1, demi-pont, rosette rectangulaire, S235."""
    dm = DataManager()
    return {
        "K": 2.1,
        "eps": 500.0,
        "R0": 120.0,
        "cfg": "demi",
        "Vin": 5.0,
        "e1": 500.0,
        "e2": -150.0,
        "e3": 0.0,
        "e4": 0.0,
        "Vout": 1.2,
        "rtype": "45",
        "ra": 400.0,
        "rb": -120.0,
        "rc": 250.0,
        "mat": "S235",
        **_materiau(dm, "S235", ["E", "nu"]),
    }


def computeGauges(saisie: dict, dm: DataManager) -> dict:
    """Extensométrie : jauge (Bridgman), pont de Wheatstone et rosette 45° ou 60°, avec tensions et déformations.

    cfg : 'quart' (une voie), 'demi' (deux voies) ou 'complet' (quatre voies). Sortie : result, tables « Rosette »
    et « Jauge et pont », status (εI, εII, σI, σII, Vout).
    """
    J = saisie
    g = hooke_gauges.gauge(J["K"], J["eps"] * 1e-6, J["R0"])
    e4 = np.array([J["e1"], J["e2"], J["e3"], J["e4"]]) * 1e-6
    ev = e4[0] if J["cfg"] == "quart" else e4[:2] if J["cfg"] == "demi" else e4
    w = hooke_gauges.wheatstone(J["cfg"], J["K"], J["Vin"], ev)
    eb = hooke_gauges.bridgeStrain(J["cfg"], J["K"], J["Vin"], J["Vout"] * 1e-3)
    rd = np.array([J["ra"], J["rb"], J["rc"]]) * 1e-6
    E = toSI(J["E"], "GPa")
    if J["rtype"] == "60":
        ro = hooke_gauges.rosette60(rd[0], rd[1], rd[2], E, J["nu"])
    else:
        ro = hooke_gauges.rosette45(rd[0], rd[1], rd[2], E, J["nu"])
    r2e = tensors.plane2DStrain(ro["exx"], ro["eyy"], ro["exy"], 0)
    r2s = tensors.plane2D(ro["sxx"], ro["syy"], ro["sxy"], 0)
    tables = {
        "Rosette": _kvTable(
            [
                ("εxx", ro["exx"] * 1e6, "µdéf"),
                ("εyy", ro["eyy"] * 1e6, "µdéf"),
                ("γxy", ro["gxy"] * 1e6, "µdéf"),
                ("εI", ro["epsI"] * 1e6, "µdéf"),
                ("εII", ro["epsII"] * 1e6, "µdéf"),
                ("θP (direction de εI)", math.degrees(ro["thetaP"]), "°"),
                ("σxx", ro["sxx"] / 1e6, "MPa"),
                ("σyy", ro["syy"] / 1e6, "MPa"),
                ("σxy", ro["sxy"] / 1e6, "MPa"),
                ("σI", ro["sigmaI"] / 1e6, "MPa"),
                ("σII", ro["sigmaII"] / 1e6, "MPa"),
                ("σ Von Mises", ro["sigmaVM"] / 1e6, "MPa"),
                ("σ Tresca", ro["sigmaTresca"] / 1e6, "MPa"),
            ]
        ),
        "Jauge et pont": _kvTable(
            [
                ("Jauge : ΔR/R = K·ε", g["dRsurR"], "-"),
                ("Jauge : ΔR", g["dR"], "Ω"),
                ("Pont : Vout linéarisée", w["Vout"] * 1e3, "mV"),
                ("Pont : Vout exacte", w["VoutExact"] * 1e3, "mV"),
                ("Pont : erreur de linéarité", w["linearityError"] * 100, "%"),
                ("Pont : ε déduite de Vout mesurée", float(np.ravel(eb)[0]) * 1e6, "µdéf"),
            ]
        ),
    }
    head = (
        f"Rosette : εI = {ro['epsI'] * 1e6:.5g}, εII = {ro['epsII'] * 1e6:.5g} µdéf ; "
        f"σI = {ro['sigmaI'] / 1e6:.5g}, σII = {ro['sigmaII'] / 1e6:.5g} MPa ; pont : Vout = {w['Vout'] * 1e3:.5g} mV"
    )
    entete = [head, f"Déformation déduite de Vout = {J['Vout']:.4g} mV : ε = {float(np.ravel(eb)[0]) * 1e6:.5g} µdéf"]
    result = {
        "gauge": g,
        "bridge": w,
        "bridgeStrain": eb,
        "rosette": ro,
        "mohrDeformations": r2e,
        "mohrContraintes": r2s,
        "rapport": _rapport(
            entete,
            [
                ("=== Jauge ===", g["report"]),
                ("=== Pont de Wheatstone ===", w["report"]),
                ("=== Rosette ===", ro["report"]),
            ],
        ),
    }
    return {"result": result, "tables": tables, "status": head}


# ------------------------------------------------------------------------------------- Abaques Kt (base)


def computeKt(id: str, prm) -> dict:
    """Kt de l'abaque `id` pour les paramètres `prm` (formes acceptées par kt_mohr.evalKtInfo).

    Sortie : result (Kt, info, rapport), tables vides, status « Kt = … ».
    """
    Kt, info = kt_mohr.evalKtInfo(id, prm)
    head = f"Kt = {Kt:.4g}"
    return {"result": {"Kt": Kt, "info": info, "rapport": [head, *info["report"]]}, "tables": {}, "status": head}
