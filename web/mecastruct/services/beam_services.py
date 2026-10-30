"""Onglet Poutres sans interface : saisie → modèle SI, calcul complet, combinaisons, charge rapide.

Port de MecaStruct_App.m (readBeamModel, beamThermal, beamCheck, computeBeam, computeCombinations,
addQuickLoad, caseFactor, distCoeffs, beamEffortSheets). Les unités de saisie sont celles de l'interface.
"""

import copy
import logging
import math
import re

import numpy as np
import pandas as pd

from mecastruct.core import geometry
from mecastruct.core.beam_solver import solveBeam
from mecastruct.core.data_manager import DataManager
from mecastruct.core.deflection import deflection, strainEnergy
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import ppEval
from mecastruct.core.solicitations import bendingStress
from mecastruct.core.units import toSI

_ID = "MecaStruct:App:invalidInput"
logger = logging.getLogger(__name__)

BEAM_INPUT_DOC = """Saisie de l'onglet Poutres : un dict dont les clés sont les noms des champs MATLAB (app.H.Beam).

Valeurs dans les unités affichées : L (m), E, G, Re (GPa, GPa, MPa), S (mm²), Iz, Iy, Ix, Iyz (mm⁴), ky, kz (-),
vy, vz (fibre extrême, mm), s, Kt (-), thDT (°C), thGy, thGz (°C), selfw (bool), plane ('xy' ou 'xz'), mat (nom du
matériau), section (dict « sec » de la section Sections ou None).
shear (bool) : « Tranchant dans Castigliano ». Par défaut décochée, comme la case MATLAB. Coché, il ajoute le
tranchant à la flèche de Castigliano : une IPE 200 de 4 m sous 10 kN/m passe de 9,029 mm à 9,296 mm (+3 %).
Les trois autres méthodes (intégration, aires, Mohr) ne tiennent pas compte du tranchant et ne changent pas.
secTabulated (bool) : vrai si la section vient d'un profilé du catalogue (valeurs de la saisie, pas le contour).
Champs E19 : na (« EN », « FR » ou « autre »), gM0, gM1, Cmy, CmLT (-), Lcr, LcrF (m, 0 = L), C1 (-),
ecsrc (« courant » ou « enveloppe »), fR (-), fka, fkb (-), mvP (texte, kN), mvE (texte, m), mvN (positions),
mvFixed (bool : garder les charges fixes avec le convoi), pfam (famille de profilés), pdef (flèche L/n, 0 = ignorée).
Tableaux (listes de dicts) :
  sup    : {pos (m), type, name}
  supx   : {name, k (kN/m), dx, dy, dz (mm)}
  hg     : {pos (m), name}
  pl     : {pos (m), Fx, Fy, Fz (kN), name, case}
  pm     : {pos (m), Mx, My, Mz (kN·m), name, case}
  dl     : {a, b (m), dir ('x', 'y' ou 'z'), type ('uniforme', 'linéaire', 'polynomiale'),
            vals (texte, kN/m), name, case}
  combo  : {name, gG, gQ, gW, gS}
case : 'G' (permanent), 'Q' (exploitation), 'W' (vent) ou 'S' (neige).
"""


def defaultBeamInput() -> dict:
    """Saisie par défaut de l'onglet Poutres : IPE 300, S235, L = 6 m, case tranchant décochée.

    Sortie : dict au format de BEAM_INPUT_DOC, valeurs prises dans la base (aucune valeur recopiée à la main).
    Le cas de l'exemple « isostatique » du menu coche la case tranchant ; ici elle reste décochée (valeur MATLAB).
    """
    dm = DataManager()
    mat = dm.getMaterial("S235")
    p = dm.getProfile("IPE", "IPE 300")
    sec = geometry.fromProfile(p)
    P = geometry.analytical(sec)
    Pt = geometry.tabulated(sec)
    return {
        "L": 6.0,
        "mat": mat["Name"],
        "E": mat["E"] / 1e9,
        "G": mat["G"] / 1e9,
        "Re": mat["Re"] / 1e6,
        "S": p["S"] * 1e6,
        "Iz": p["Iz"] * 1e12,
        "Iy": p["Iy"] * 1e12,
        "Ix": P["J"] * 1e12,
        "Iyz": 0.0,
        "ky": Pt["ky"],
        "kz": Pt["kz"],
        "vy": p["h"] / 2 * 1e3,
        "vz": p["b"] / 2 * 1e3,
        "s": 1.5,
        "Kt": 1.0,
        "sup": [{"pos": 0.0, "type": "pivot", "name": "A"}, {"pos": 6.0, "type": "appui_simple", "name": "B"}],
        "supx": [],
        "hg": [],
        "pl": [{"pos": 2.0, "Fx": 0.0, "Fy": -20.0, "Fz": 0.0, "name": "F", "case": "Q"}],
        "pm": [],
        "dl": [{"a": 0.0, "b": 6.0, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}],
        "thDT": 0.0,
        "thGy": 0.0,
        "thGz": 0.0,
        "selfw": False,
        "plane": "xy",
        "shear": False,
        "na": "EN",
        "gM0": 1.0,
        "gM1": 1.0,
        "Cmy": 1.0,
        "CmLT": 1.0,
        "Lcr": 0.0,
        "LcrF": 0.0,
        "C1": 1.0,
        "ecsrc": "courant",
        "fR": 0.0,
        "fka": 1.0,
        "fkb": 1.0,
        "mvP": "-100",
        "mvE": "1.5",
        "mvN": 61,
        "mvFixed": False,
        "pfam": "IPE",
        "pdef": 0.0,
        "secTabulated": False,
        "combo": [
            {"name": "ELS", "gG": 1.0, "gQ": 1.0, "gW": 0.0, "gS": 0.0},
            {"name": "ELU", "gG": 1.35, "gQ": 1.5, "gW": 0.0, "gS": 0.0},
        ],
        "section": None,
    }


def _num(x, what: str) -> float:
    """Nombre fini lu dans une case de tableau (virgule décimale admise)."""
    try:
        v = float(x) if isinstance(x, (int, float)) else float(str(x).replace(",", "."))
    except ValueError:
        v = math.nan
    if not math.isfinite(v):
        raise MecaStructError(_ID, f"{what} : valeur numérique invalide.")
    return v


def _okText(ok: bool) -> str:
    """Verdict en français (« vérifié » ou « NON vérifié »)."""
    return "vérifié" if ok else "NON vérifié"


def caseFactor(fac: dict, row: dict) -> float:
    """Coefficient du cas de charge d'une ligne (clé « case » ; sans cas : G).

    Entrées : `fac` (dict G, Q, W, S → coefficient) ; `row` (ligne de tableau). Sortie : float.
    Erreur : MecaStruct:App:invalidInput si le cas n'est ni G, Q, W ni S.
    """
    c = str(row.get("case") or "G")
    if c not in fac:
        raise MecaStructError(_ID, f"Cas de charge inconnu « {c} » (attendu : G, Q, W ou S).")
    return fac[c]


def distCoeffs(type_: str, vals: str, a: float, b: float) -> np.ndarray:
    """Coefficients (ordre polyval, variable locale ξ = s − a) d'une charge répartie, en kN/m.

    Entrées : `type_` ('uniforme', 'linéaire' ou 'polynomiale', sans accent accepté) ; `vals` (texte, nombres
    séparés par espaces, virgules ou points-virgules) ; `a`, `b` (m). Sortie : np.ndarray (kN/m, kN/m², …).
    Erreur : MecaStruct:App:invalidInput si une valeur est invalide ou le type inconnu.
    """
    s = re.sub(r"[;]", " ", str(vals)).strip()
    v = np.array([float(t) for t in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", s.replace(",", "."))])
    if v.size == 0:
        raise MecaStructError(_ID, f"Charge répartie : valeurs « {s} » invalides.")
    t = str(type_).lower().replace("é", "e").replace("è", "e")
    if t == "uniforme":
        return v[:1]
    if t == "lineaire":
        if v.size < 2:
            raise MecaStructError(_ID, "Charge linéaire : deux valeurs « p1 p2 » attendues.")
        return np.array([(v[1] - v[0]) / (b - a), v[0]])
    if t == "polynomiale":
        return v
    raise MecaStructError(_ID, f"Type de charge répartie inconnu : {t}.")


def beamThermal(saisie: dict, dm: DataManager) -> dict:
    """Action thermique de la poutre : epsX = α·ΔT, courbures kv = −α·Δgy/hy et kw = −α·Δgz/hz (1/m).

    Entrées : `saisie` (thDT, thGy, thGz en °C ; vy, vz en mm ; mat) ; `dm` (base de matériaux).
    Sortie : dict epsX (-), kv, kw (1/m). Erreur : MecaStruct:App:invalidInput si α ou une fibre extrême manque.
    """
    th = {"epsX": 0.0, "kv": 0.0, "kw": 0.0}
    if saisie["thDT"] == 0 and saisie["thGy"] == 0 and saisie["thGz"] == 0:
        return th
    alpha = dm.getMaterial(saisie["mat"])["alpha"]
    if not (math.isfinite(alpha) and alpha > 0):
        raise MecaStructError(_ID, f"Température : coefficient de dilatation inconnu pour « {saisie['mat']} ».")
    th["epsX"] = alpha * saisie["thDT"]
    if saisie["thGy"] != 0:
        if not saisie["vy"] > 0:
            raise MecaStructError(
                _ID, "Gradient thermique selon y : renseignez la fibre extrême |y|max (hauteur = 2·|y|max)."
            )
        th["kv"] = -alpha * saisie["thGy"] / (2 * saisie["vy"] * 1e-3)
    if saisie["thGz"] != 0:
        if not saisie["vz"] > 0:
            raise MecaStructError(
                _ID, "Gradient thermique selon z : renseignez la fibre extrême |z|max (hauteur = 2·|z|max)."
            )
        th["kw"] = -alpha * saisie["thGz"] / (2 * saisie["vz"] * 1e-3)
    return th


def buildBeamModel(saisie: dict, dm: DataManager, fac: dict | None = None) -> dict:
    """Modèle de poutre SI (readBeamModel) à partir de la saisie ; un cas dont le coefficient vaut 0 est omis.

    Entrées : `saisie` (BEAM_INPUT_DOC) ; `dm` (base de matériaux) ; `fac` (dict G, Q, W, S ; défaut 1 partout).
    Sortie : dict model (L en m, E, G, S, Iz, Iy, Ix en Pa ou m², m⁴ ; supports, hinges, thermal, pointLoads,
    pointMoments, distLoads en N, N·m, N/m).
    Erreur : MecaStruct:App:invalidInput (longueur, Iyz, valeurs, masse volumique, cas inconnu).
    """
    if fac is None:
        fac = {"G": 1.0, "Q": 1.0, "W": 1.0, "S": 1.0}
    L = float(saisie["L"])
    if not L > 0:
        raise MecaStructError(_ID, "La longueur L doit être strictement positive.")
    model = {
        "L": L,
        "E": toSI(saisie["E"], "GPa"),
        "G": toSI(saisie["G"], "GPa"),
        "S": toSI(saisie["S"], "mm^2"),
        "Iz": toSI(saisie["Iz"], "mm^4"),
        "Iy": toSI(saisie["Iy"], "mm^4"),
        "Ix": toSI(saisie["Ix"], "mm^4"),
        "ky": float(saisie["ky"]),
        "kz": float(saisie["kz"]),
        "Iyz": toSI(saisie["Iyz"], "mm^4"),
    }
    if model["Iyz"] ** 2 >= model["Iz"] * model["Iy"]:
        raise MecaStructError(_ID, "Il faut Iyz² < Iz·Iy (matrice d'inertie définie positive).")

    sup = []
    for row in saisie["sup"]:
        sup.append(
            {
                "pos": _num(row["pos"], "Appui : position"),
                "type": str(row["type"]),
                "name": str(row["name"]),
                "spring": 0.0,
                "dx": 0.0,
                "dy": 0.0,
                "dz": 0.0,
            }
        )
    for row in saisie["supx"]:
        match = [s for s in sup if s["name"] == str(row["name"])]
        if not match:
            raise MecaStructError(_ID, f"Ressorts et tassements : aucun appui ne s'appelle « {row['name']} ».")
        j = match[0]
        j["spring"] = toSI(_num(row["k"], "Ressort k"), "kN/m")
        # tassements et température : actions permanentes, rangées dans le cas G (pondérées par γG dans une combinaison)
        j["dx"] = fac["G"] * _num(row["dx"], "Tassement x") * 1e-3
        j["dy"] = fac["G"] * _num(row["dy"], "Tassement y") * 1e-3
        j["dz"] = fac["G"] * _num(row["dz"], "Tassement z") * 1e-3
    model["supports"] = sup
    model["hinges"] = [{"pos": _num(r["pos"], "Rotule : position"), "name": str(r["name"])} for r in saisie["hg"]]

    th = beamThermal(saisie, dm)
    model["thermal"] = {"epsX": fac["G"] * th["epsX"], "kv": fac["G"] * th["kv"], "kw": fac["G"] * th["kw"]}

    pl = []
    for row in saisie["pl"]:
        k = caseFactor(fac, row)
        if k == 0:
            continue
        pl.append(
            {
                "pos": _num(row["pos"], "Force : position"),
                "Fx": k * toSI(_num(row["Fx"], "Fx"), "kN"),
                "Fy": k * toSI(_num(row["Fy"], "Fy"), "kN"),
                "Fz": k * toSI(_num(row["Fz"], "Fz"), "kN"),
                "name": str(row["name"]),
            }
        )
    model["pointLoads"] = pl

    pm = []
    for row in saisie["pm"]:
        k = caseFactor(fac, row)
        if k == 0:
            continue
        pm.append(
            {
                "pos": _num(row["pos"], "Couple : position"),
                "Mx": k * toSI(_num(row["Mx"], "Mx"), "kN.m"),
                "My": k * toSI(_num(row["My"], "My"), "kN.m"),
                "Mz": k * toSI(_num(row["Mz"], "Mz"), "kN.m"),
                "name": str(row["name"]),
            }
        )
    model["pointMoments"] = pm

    dl = []
    for row in saisie["dl"]:
        k = caseFactor(fac, row)
        if k == 0:
            continue
        a = _num(row["a"], "Charge répartie : a")
        b = _num(row["b"], "Charge répartie : b")
        dl.append(
            {
                "a": a,
                "b": b,
                "dir": str(row["dir"]),
                "coeffs": k * toSI(distCoeffs(row["type"], row["vals"], a, b), "kN/m"),
                "name": str(row["name"]),
            }
        )
    if saisie["selfw"] and fac["G"] != 0:
        rho = dm.getMaterial(saisie["mat"])["rho"]
        if not (math.isfinite(rho) and rho > 0):
            raise MecaStructError(_ID, f"Poids propre : masse volumique inconnue pour « {saisie['mat']} ».")
        dl.append(
            {
                "a": 0.0,
                "b": L,
                "dir": "y",
                "coeffs": -fac["G"] * rho * 9.80665 * model["S"],
                "name": "poids propre",
            }
        )
    model["distLoads"] = dl
    return model


def _sectionProps(saisie: dict) -> dict:
    """Propriétés de section saisies à la main (SI), pour la vérification de résistance.

    Erreur : MecaStruct:App:invalidInput si une fibre extrême |y|max ou |z|max n'est pas > 0.
    """
    vy = toSI(saisie["vy"], "mm")
    vz = toSI(saisie["vz"], "mm")
    if not (vy > 0 and vz > 0):
        raise MecaStructError(_ID, "Les distances aux fibres extrêmes |y|max et |z|max doivent être > 0.")
    return {
        "S": toSI(saisie["S"], "mm^2"),
        "Iz": toSI(saisie["Iz"], "mm^4"),
        "Iy": toSI(saisie["Iy"], "mm^4"),
        "Iyz": toSI(saisie["Iyz"], "mm^4"),
        "vyTop": vy,
        "vyBot": vy,
        "vzRight": vz,
        "vzLeft": vz,
    }


def beamCheck(saisie: dict, sol: dict, dm: DataManager) -> dict:
    """Vérification de résistance au point le plus sollicité (flexion composée et déviée).

    Entrées : `saisie` (Kt, Re, s, vy, vz, S…, section) ; `sol` (sortie de solveBeam) ; `dm` (non utilisé, gardé
    pour la signature commune des services).
    Sortie : dict s (m), N, Ty, Tz, Mfz, Mfy (SI au point), bend (bendingStress), sigma, loc, ok, report (list[str]).
    """
    L = sol["model"]["L"]
    s = np.unique(np.concatenate([np.linspace(0.0, L, 1201), np.asarray(sol["breaks"], dtype=float).ravel()]))
    ss = np.concatenate([s, s])

    def ev(pp):
        return np.concatenate([ppEval(pp, s, "left"), ppEval(pp, s, "right")])

    N, Ty, Tz, Mfz, Mfy = (ev(sol[k]) for k in ("N", "Ty", "Tz", "Mfz", "Mfy"))
    useSec = saisie.get("section") is not None and not saisie.get("secTabulated", False)
    if useSec:
        sec = saisie["section"]
        P = geometry.analytical(sec)
        srcTxt = "section de l'onglet Sections (contour exact)"
    else:
        P = _sectionProps(saisie)
        srcTxt = "section saisie (fibres extrêmes symétriques |y|max, |z|max)"

    score = (
        np.abs(N) / P["S"]
        + np.abs(Mfz) * max(P["vyTop"], P["vyBot"]) / P["Iz"]
        + np.abs(Mfy) * max(P["vzRight"], P["vzLeft"]) / P["Iy"]
    )
    # le score (somme linéaire des termes) est exact pour un rectangle mais pas pour un disque ni pour Iyz ≠ 0 :
    # on retient les meilleurs candidats et on garde celui dont σ exact est maximal
    order = np.argsort(-score, kind="stable")
    iMz = int(np.argmax(np.abs(Mfz)))
    iMy = int(np.argmax(np.abs(Mfy)))
    cand = list(dict.fromkeys([*order[:10].tolist(), iMz, iMy]))

    best = -math.inf
    for c in cand:
        pc = {
            "N": float(N[c]),
            "Mfz": float(Mfz[c]),
            "Mfy": float(Mfy[c]),
            "Kt": saisie["Kt"],
            "Re": toSI(saisie["Re"], "MPa"),
            "s": saisie["s"],
        }
        if useSec:
            pc["sec"] = sec
            pc["Pcore"] = P
        else:
            pc["P"] = P
        bc = bendingStress(pc)
        if bc["sigmaMaxAbs"] > best * (1 + 1e-12):
            best = bc["sigmaMaxAbs"]
            i = c
            bend = bc

    if abs(bend["sigmaMaxTraction"]) >= abs(bend["sigmaMaxCompression"]):
        sig, loc = bend["sigmaMaxTraction"], bend["locMaxTraction"]
    else:
        sig, loc = bend["sigmaMaxCompression"], bend["locMaxCompression"]
    text = (
        f"Point le plus sollicité : s = {ss[i]:.4g} m (N = {N[i] / 1e3:.5g} kN, Mfz = {Mfz[i] / 1e3:.5g} kN·m, "
        f"Mfy = {Mfy[i] / 1e3:.5g} kN·m) ; {srcTxt}."
    )
    return {
        "s": float(ss[i]),
        "N": float(N[i]),
        "Ty": float(Ty[i]),
        "Tz": float(Tz[i]),
        "Mfz": float(Mfz[i]),
        "Mfy": float(Mfy[i]),
        "bend": bend,
        "sigma": sig,
        "loc": loc,
        "ok": bend["ok"],
        "report": [text, *bend["report"]],
    }


def computeBeam(saisie: dict, dm: DataManager) -> dict:
    """Calcul complet de l'onglet Poutres : statique, déformée (4 méthodes), énergie et résistance.

    Entrées : `saisie` (BEAM_INPUT_DOC) ; `dm` (base de matériaux).
    Sortie : dict model, sol (solveBeam), defl (deflection), energy (strainEnergy), check (beamCheck),
    status (ligne d'état), unreliable (bool : hyperstatique avec Iyz ≠ 0, réactions non fiables).
    Erreur : MecaStruct:App:invalidInput (saisie), erreurs des moteurs (mécanisme, appui invalide…).
    """
    model = buildBeamModel(saisie, dm)
    sol = solveBeam(model)
    d = deflection(sol["model"], sol, {"plane": saisie["plane"], "includeShear": bool(saisie["shear"])})
    U = strainEnergy(sol["model"], sol)
    chk = beamCheck(saisie, sol, dm)
    h = sol["h"]
    hTxt = "isostatique" if sol["isostatic"] else "hyperstatique"
    bd = chk["bend"]
    status = (
        f"h = {h['total']} ({hTxt}) — f max = {d['integration']['fmax'] * 1e3:.4g} mm — "
        f"Kt·|σ|max = {bd['sigmaMaxKt'] / 1e6:.4g} MPa ({_okText(bd['ok'])})"
    )
    unreliable = (not sol["isostatic"]) and sol["model"]["Iyz"] != 0
    if unreliable:
        status = "⚠ LIMITE : hyperstatique avec Iyz ≠ 0, résultats NON fiables — " + status
    return {
        "model": sol["model"],
        "sol": sol,
        "defl": d,
        "energy": U,
        "check": chk,
        "status": status,
        "unreliable": unreliable,
    }


def _colMax(v: np.ndarray) -> float:
    """Maximum des valeurs non NaN (NaN s'il n'y en a pas)."""
    v = v[~np.isnan(v)]
    return float(v.max()) if v.size else math.nan


def _colMin(v: np.ndarray) -> float:
    """Minimum des valeurs non NaN (NaN s'il n'y en a pas)."""
    v = v[~np.isnan(v)]
    return float(v.min()) if v.size else math.nan


def computeCombinations(saisie: dict, dm: DataManager) -> pd.DataFrame:
    """Résout chaque combinaison de cas du tableau combo, puis donne l'enveloppe (ligne « Enveloppe »).

    Superposition de cas : exacte pour une poutre linéaire. Une combinaison dont le calcul échoue garde ses
    valeurs vides ; le verdict est « erreur : … » (MecaStructError) ou « Erreur de calcul (type) : … »
    (autre exception, tracée dans le log du module).
    Entrées : `saisie` (BEAM_INPUT_DOC) ; `dm` (base de matériaux).
    Sortie : DataFrame, colonnes Combinaison, Mfz max/min (kN·m), Ty max/min (kN), N max/min (kN), f max (mm),
    Kt·σ max (MPa), σadm (MPa), Résistance.
    Erreur : MecaStruct:App:invalidInput si aucune combinaison.
    """
    combo = saisie["combo"]
    if not combo:
        raise MecaStructError(_ID, "Aucune combinaison : ajoutez une ligne au tableau Combinaisons.")
    n = len(combo)
    v = np.full((n, 9), math.nan)
    verdict = []
    ok = np.ones(n, dtype=bool)
    for i, row in enumerate(combo):
        fac = {
            "G": _num(row["gG"], "γG"),
            "Q": _num(row["gQ"], "γQ"),
            "W": _num(row["gW"], "γW"),
            "S": _num(row["gS"], "γS"),
        }
        try:
            sol = solveBeam(buildBeamModel(saisie, dm, fac))
            d = deflection(sol["model"], sol, {"plane": saisie["plane"], "includeShear": bool(saisie["shear"])})
            chk = beamCheck(saisie, sol, dm)
        except MecaStructError as err:
            ok[i] = False
            verdict.append(f"erreur : {err}")
            continue
        except Exception as err:  # comme MATLAB : une combinaison en erreur ne bloque pas les autres
            logger.exception("Combinaison « %s » non calculée", row["name"])
            ok[i] = False
            verdict.append(f"Erreur de calcul ({type(err).__name__}) : {err}")
            continue
        e = sol["extrema"]
        v[i, :6] = [e["Mfz"]["max"], e["Mfz"]["min"], e["Ty"]["max"], e["Ty"]["min"], e["N"]["max"], e["N"]["min"]]
        v[i, :6] /= 1e3
        v[i, 6:9] = [d["integration"]["fmax"] * 1e3, chk["bend"]["sigmaMaxKt"] / 1e6, chk["bend"]["sigmaAdm"] / 1e6]
        ok[i] = bool(chk["bend"]["ok"])
        verdict.append(_okText(ok[i]))

    ok &= ~np.isnan(v[:, 0])
    row = np.full(9, math.nan)
    for k in (0, 2, 4, 6, 7):
        row[k] = _colMax(v[:, k])
    for k in (1, 3, 5):
        row[k] = _colMin(v[:, k])
    sigAdm = v[~np.isnan(v[:, 8]), 8]  # σadm est la même pour toutes les combinaisons : la première valeur suffit
    row[8] = float(sigAdm[0]) if sigAdm.size else math.nan

    allOk = bool(np.all(ok))
    columns = {
        "Combinaison": [str(r["name"]) for r in combo] + ["Enveloppe"],
        "Mfz max (kN·m)": [*v[:, 0], row[0]],
        "Mfz min (kN·m)": [*v[:, 1], row[1]],
        "Ty max (kN)": [*v[:, 2], row[2]],
        "Ty min (kN)": [*v[:, 3], row[3]],
        "N max (kN)": [*v[:, 4], row[4]],
        "N min (kN)": [*v[:, 5], row[5]],
        "f max (mm)": [*v[:, 6], row[6]],
        "Kt·σ max (MPa)": [*v[:, 7], row[7]],
        "σadm (MPa)": [*v[:, 8], row[8]],
        "Résistance": [*verdict, _okText(allOk)],
    }
    return pd.DataFrame(columns)


def addQuickLoad(
    saisie: dict, kind: str, a: float, b: float, p1: float, p2: float = 0.0, direction: str = "y", case: str = "G"
) -> dict:
    """Copie de la saisie à laquelle est ajoutée une charge répartie (« Charge rapide »).

    Entrées : `kind` = 'uniforme', 'triangle_croissant' (0 → p1), 'triangle_decroissant' (p1 → 0) ou
    'trapeze' (p1 → p2) ; `a`, `b` (m) ; `p1`, `p2` (kN/m, < 0 : vers le bas) ; `direction` ('x', 'y' ou 'z') ;
    `case` (G, Q, W, S).
    Sortie : dict, copie de `saisie` avec une ligne ajoutée à dl.
    Erreur : MecaStruct:App:invalidLoad si b ≤ a ; MecaStruct:App:invalidInput si kind est inconnu.
    """
    if b <= a:
        raise MecaStructError("MecaStruct:App:invalidLoad", "La charge doit finir après son début (b > a).")
    vals = {
        "uniforme": ("uniforme", f"{p1:.10g}"),
        "triangle_croissant": ("linéaire", f"0 {p1:.10g}"),
        "triangle_decroissant": ("linéaire", f"{p1:.10g} 0"),
        "trapeze": ("linéaire", f"{p1:.10g} {p2:.10g}"),
    }
    if kind not in vals:
        raise MecaStructError(_ID, f"Forme de charge inconnue : {kind}.")
    type_, text = vals[kind]
    new = copy.deepcopy(saisie)
    new["dl"].append({"a": a, "b": b, "dir": direction, "type": type_, "vals": text, "name": "", "case": case})
    return new


def effortSheets(sol: dict) -> dict[str, pd.DataFrame]:
    """Feuilles « Enveloppe » (max et min de chaque effort) et « Efforts » (valeurs le long de la poutre).

    Entrée : `sol` (sortie de solveBeam). Sortie : dict nom → DataFrame, en kN et kN·m.
    """
    comps = ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]
    unit = ["kN", "kN", "kN", "kN·m", "kN·m", "kN·m"]
    rows = []
    for c, u in zip(comps, unit, strict=True):
        e = sol["extrema"][c]
        rows.append(
            {
                "Effort": c,
                "Unité": u,
                "Max": e["max"] / 1e3,
                "s du max (m)": e["sMax"],
                "Min": e["min"] / 1e3,
                "s du min (m)": e["sMin"],
            }
        )
    env = pd.DataFrame(rows)
    L = float(sol["N"].breaks[-1])
    s = np.unique(np.concatenate([np.linspace(0.0, L, 201), np.asarray(sol["N"].breaks, dtype=float)]))
    eff = pd.DataFrame({"s (m)": s})
    for c, u in zip(comps, unit, strict=True):
        eff[f"{c} ({u})"] = ppEval(sol[c], s) / 1e3
    return {"Enveloppe": env, "Efforts": eff}
