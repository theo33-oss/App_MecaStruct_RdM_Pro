"""Propriétés des sections droites : port de GeometryEngine.m (étapes E06 et E07).

Repère O1 : z horizontal vers la droite, y vertical vers le haut, origine au coin bas-gauche de la section.
Les fonctions qui reçoivent une cote y la mesurent depuis le centre de gravité G (ARCHITECTURE §2).
Les aires sont en m², les moments statiques en m³, les moments quadratiques en m⁴.
"""

import copy
import math
import re

import numpy as np
import pandas as pd
from scipy.integrate import dblquad, quad
from scipy.optimize import minimize_scalar
from shapely.geometry import Polygon
from shapely.ops import unary_union

from mecastruct.core import data_manager
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import _num
from mecastruct.core.utils import is_num

_ID = "MecaStruct:GeometryEngine:"
_NC = 240  # segments des cercles (au moins 120 points, comme GeometryEngine.m)

_ALIAS = {
    "rectangle": "rectangle",
    "rect": "rectangle",
    "rectangulaire": "rectangle",
    "disque": "disque",
    "disk": "disque",
    "cercle": "disque",
    "circle": "disque",
    "rond": "disque",
    "circulaire": "disque",
    "couronne": "couronne",
    "tube": "couronne",
    "annulus": "couronne",
    "anneau": "couronne",
    "tube_circulaire": "couronne",
    "rectangle_creux": "rectangle_creux",
    "caisson": "rectangle_creux",
    "tube_rectangulaire": "rectangle_creux",
    "creux": "rectangle_creux",
    "i": "I",
    "t": "T",
    "u": "U",
    "l": "L",
    "corniere": "L",
    "cornière": "L",
    "profile": "profile",
    "profil": "profile",
    "profilé": "profile",
    "profile_catalogue": "profile",
    "composite": "composite",
    "composee": "composite",
    "composée": "composite",
    "quelconque": "composite",
}

_SECTION_TYPES = [
    ("rectangle", "Rectangle plein", ["b", "h"], "coin bas-gauche"),
    ("disque", "Disque plein", ["D"], "coin bas-gauche du carré englobant"),
    ("couronne", "Couronne (tube circulaire)", ["D", "d"], "coin bas-gauche du carré englobant"),
    ("rectangle_creux", "Rectangle creux (caisson)", ["B", "H", "t"], "coin bas-gauche"),
    ("I", "Profil en I symétrique", ["h", "b", "tw", "tf"], "coin bas-gauche"),
    ("T", "Profil en T", ["h", "b", "tw", "tf"], "coin bas-gauche (aile en haut)"),
    ("U", "Profil en U", ["h", "b", "tw", "tf"], "coin bas-gauche (âme à gauche)"),
    ("L", "Cornière L", ["h", "b", "t"], "angle en bas à gauche"),
    ("profile", "Profilé du catalogue", ["family", "name", "h", "b", "a", "e", "S", "Iz", "Iy"], "coin bas-gauche"),
    ("composite", "Section composée de rectangles", ["rects", "holes"], "repère utilisateur"),
]


# =====================================================================================
#  Fonctions publiques
# =====================================================================================


def validateSection(sec: dict) -> dict:
    """Contrôle et normalise une section : type canonique, dimensions réelles en m, profilé et composite complétés.

    Entrée : `sec` (dict, champ `type` obligatoire, dimensions en m). Sortie : copie validée du dict.
    Erreurs : MecaStruct:GeometryEngine:invalidInput, missingField, unknownType, invalidDimensions, overlap,
    holeOutside.
    """
    if not isinstance(sec, dict):
        raise MecaStructError(
            _ID + "invalidInput", "La section doit être une structure scalaire (champ sec.type obligatoire)."
        )
    texte = sec.get("type")
    if not isinstance(texte, str) or texte == "":
        raise MecaStructError(_ID + "missingField", "Champ obligatoire manquant : sec.type (texte).")
    t = _ALIAS.get(texte.strip().lower().replace(" ", "_").replace("-", "_"))
    if t is None:
        raise MecaStructError(
            _ID + "unknownType",
            f"Type de section inconnu : '{texte}'. Types reconnus : rectangle, disque, couronne, "
            "rectangle_creux, I, T, U, L, profile, composite.",
        )
    sec = copy.deepcopy(sec)
    sec["type"] = t
    if t == "rectangle":
        sec["b"] = _dimField(sec, "b", "largeur selon z")
        sec["h"] = _dimField(sec, "h", "hauteur selon y")
    elif t == "disque":
        sec["D"] = _dimField(sec, "D", "diamètre")
    elif t == "couronne":
        sec["D"] = _dimField(sec, "D", "diamètre extérieur")
        sec["d"] = _dimField(sec, "d", "diamètre intérieur", True)
        if sec["d"] >= sec["D"]:
            raise MecaStructError(
                _ID + "invalidDimensions",
                f"Couronne : le diamètre intérieur d ({_num(sec['d'])} m) doit être inférieur "
                f"à D ({_num(sec['D'])} m).",
            )
    elif t == "rectangle_creux":
        sec["B"] = _dimField(sec, "B", "largeur extérieure selon z")
        sec["H"] = _dimField(sec, "H", "hauteur extérieure selon y")
        sec["t"] = _dimField(sec, "t", "épaisseur de paroi")
        if 2 * sec["t"] >= min(sec["B"], sec["H"]):
            raise MecaStructError(
                _ID + "invalidDimensions",
                f"Rectangle creux : il faut 2t < min(B, H) (t = {_num(sec['t'])} m, B = {_num(sec['B'])} m, "
                f"H = {_num(sec['H'])} m).",
            )
    elif t in ("I", "T", "U"):
        sec["h"] = _dimField(sec, "h", "hauteur totale")
        sec["b"] = _dimField(sec, "b", "largeur des ailes")
        sec["tw"] = _dimField(sec, "tw", "épaisseur d'âme a")
        sec["tf"] = _dimField(sec, "tf", "épaisseur d'aile e")
        _checkThinWalls(t, sec["h"], sec["b"], sec["tw"], sec["tf"])
    elif t == "L":
        sec["h"] = _dimField(sec, "h", "longueur de l'aile verticale")
        sec["b"] = _dimField(sec, "b", "longueur de l'aile horizontale")
        sec["t"] = _dimField(sec, "t", "épaisseur")
        if sec["t"] >= min(sec["h"], sec["b"]):
            raise MecaStructError(
                _ID + "invalidDimensions",
                f"Cornière L : il faut t < min(h, b) (t = {_num(sec['t'])} m, h = {_num(sec['h'])} m, "
                f"b = {_num(sec['b'])} m).",
            )
    elif t == "profile":
        return _resolveProfile(sec)
    elif t == "composite":
        return _validateComposite(sec)
    return sec


def primitives(sec: dict) -> list[dict]:
    """Décomposition d'une section en primitives signées (rectangles, disques, couronnes), repère O1.

    Entrée : `sec` (dict de section). Sortie : liste de dicts `kind` ('rect', 'disk', 'annulus'), `sign` (+1 matière,
    -1 trou), `z1, z2, y1, y2`, `zc, yc, R, Ri` (NaN pour un rectangle), `label`.
    """
    return _buildPrims(validateSection(sec))


def widthAt(sec: dict, y, side: str = "max"):
    """Largeur b(y) de la section à la cote y mesurée depuis G (exacte, vectorisée).

    Entrées : `sec` ; `y` (m, depuis G, nombre ou tableau) ; `side` = 'max' (défaut : plus grande limite),
    'dessus'/'above' (limite par au-dessus), 'dessous'/'below' (limite par en dessous). Hors section : 0.
    Sortie : float si y est un nombre, sinon tableau de même forme (m).
    """
    side = _normalizeSide(side)
    sec = validateSection(sec)
    prims = _buildPrims(sec)
    core = _huygensCore(prims)
    _checkNumeric(y, "y")
    return _out(_widthCore(prims, core["yG"], np.asarray(y, dtype=float), side))


def firstMomentAbove(sec: dict, y):
    """Moment statique Q(y) = ∫_{η > y} η dS de la partie de section située au-dessus de y (η depuis G).

    Entrées : `sec` ; `y` (m, depuis G, nombre ou tableau). Sortie : float ou tableau (m³), 0 hors de la section.
    """
    sec = validateSection(sec)
    prims = _buildPrims(sec)
    core = _huygensCore(prims)
    _checkNumeric(y, "y")
    return _out(_firstMomentCore(prims, core["yG"], np.asarray(y, dtype=float)))


def outline(sec: dict) -> dict:
    """Contours fermés de la section dans le repère O1, pour le tracé.

    Entrée : `sec`. Sortie : dict `outer` (liste de tableaux N×2 [z y] fermés, sens trigonométrique), `holes`
    (liste de contours de trous, sens horaire), `bbox` ([zmin zmax ymin ymax], m). Cercles à 240 segments.
    """
    sec = validateSection(sec)
    prims = _buildPrims(sec)
    out = {"outer": [], "holes": [], "bbox": _bboxPrims(prims)}
    t = sec["type"]
    if t == "rectangle":
        out["outer"] = [_rectPoly(0, sec["b"], 0, sec["h"])]
    elif t in ("disque", "couronne"):
        R = sec["D"] / 2
        out["outer"] = [_circlePoly(R, R, R, _NC)]
        if t == "couronne" and sec["d"] > 0:
            out["holes"] = [_circlePoly(R, R, sec["d"] / 2, _NC)[::-1]]
    elif t == "rectangle_creux":
        ep = sec["t"]
        out["outer"] = [_rectPoly(0, sec["B"], 0, sec["H"])]
        out["holes"] = [_rectPoly(ep, sec["B"] - ep, ep, sec["H"] - ep)[::-1]]
    elif t in ("I", "T", "U", "L", "profile"):
        out["outer"] = [_shapePoly(sec)]
    elif t == "composite":
        geom = unary_union([_primPolyshape(p, _NC) for p in prims if p["sign"] > 0])
        neg = [_primPolyshape(p, _NC) for p in prims if p["sign"] < 0]
        if neg:
            geom = geom.difference(unary_union(neg))
        for poly in _parts(geom):
            out["outer"].append(_orientPoly(_closePoly(np.asarray(poly.exterior.coords)), True))
            for ring in poly.interiors:
                out["holes"].append(_orientPoly(_closePoly(np.asarray(ring.coords)), False))
    return out


def fromProfile(p: dict) -> dict:
    """Section 'profile' à partir d'un profilé du catalogue (DataManager.getProfile), validée.

    Entrée : `p` (dict contenant h, b, a, e, ou family et name). Sortie : dict validé de type 'profile'.
    Erreur : MecaStruct:GeometryEngine:invalidInput si `p` n'est pas un dict.
    """
    if not isinstance(p, dict):
        raise MecaStructError(
            _ID + "invalidInput", "Le profilé doit être une structure scalaire (cf. DataManager.getProfile)."
        )
    sec = dict(p, type="profile")
    if "family" not in sec and "Family" in sec:
        sec["family"] = str(sec["Family"])
    if "name" not in sec and "Name" in sec:
        sec["name"] = str(sec["Name"])
    return validateSection(sec)


def sectionTypes() -> list[dict]:
    """Description des types de section reconnus.

    Sortie : liste de dicts `type`, `label` (texte français), `fields` (noms des dimensions), `origin` (repère O1).
    """
    return [{"type": t, "label": lbl, "fields": f, "origin": o} for t, lbl, f, o in _SECTION_TYPES]


def hasSymbolic() -> bool:
    """Indique si le calcul symbolique (SymPy, à la place de la Symbolic Math Toolbox) est disponible.

    Sortie : bool.
    """
    return data_manager.hasSymbolic()


def analytical(sec: dict) -> dict:
    """Méthode A : formules fermées des éléments et théorème de Huygens, propriétés de la section en G.

    Entrée : `sec` (dict de section, dimensions en m). Sortie : dict P en SI (S en m², moments statiques en m³,
    moments quadratiques en m⁴) : champs de ARCHITECTURE §2, `shear` (shearFactors), `huygens` (DataFrame de la
    décomposition), `report` (list[str]) et `latex` (list[str]).
    """
    sec = validateSection(sec)
    prims = _buildPrims(sec)
    core = _huygensCore(prims)
    core, repClosed, texClosed = _closedForm(sec, core)
    P = _assembleP(sec, prims, core, "analytique")
    P["huygens"] = core["table"]

    rep = [f"Méthode A — formules fermées et théorème de Huygens ({_typeLabel(sec)})", _describeSection(sec)]
    if repClosed:
        rep += repClosed
        tex = texClosed
    else:
        repH, tex = _huygensText(core)
        rep += repH
    if sec["type"] == "profile":
        rep.append(
            "Remarque : géométrie simplifiée (âme et ailes d'épaisseurs constantes a et e, congés de raccordement et "
            "inclinaison des ailes ignorés) : un écart de quelques % avec les valeurs du catalogue est attendu "
            "(voir compare)."
        )
    repC, texC = _commonText(P)
    P["report"] = rep + repC
    P["latex"] = tex + texC
    return P


def integral(sec: dict, mode: str | None = None) -> dict:
    """Méthode B : intégration surfacique exacte (SymPy) ou numérique (dblquad), primitive par primitive.

    Entrées : `sec` ; `mode` = 'symbolique' ou 'numerique' (alias acceptés) ; None = symbolique si SymPy est disponible.
    Sortie : dict P comme analytical (sans huygens), plus IxDirect (m⁴, ∬ r² dS), methodUsed, method et
    integrals (list[str], intégrales posées en LaTeX). Erreur : MecaStruct:GeometryEngine:unknownMode.
    """
    sec = validateSection(sec)
    if mode is None or mode == "":
        mode = "symbolique" if hasSymbolic() else "numerique"
    mode = _normalizeMode(mode)
    prims = _buildPrims(sec)
    notes = []
    R = None
    if mode == "symbolique" and not hasSymbolic():
        notes.append("SymPy indisponible : repli sur l'intégration numérique (dblquad).")
        mode = "numerique"
    if mode == "symbolique":
        try:
            R = _integrateSymbolic(prims)
        except Exception as err:  # repli numérique sur toute erreur SymPy, comme GeometryEngine.m
            notes.append(f"Échec du calcul symbolique ({err}) : repli sur l'intégration numérique (dblquad).")
            mode = "numerique"
    if R is None:
        R = _integrateNumeric(prims)

    symbolique = mode == "symbolique"
    core = _cleanIyz({k: R[k] for k in ("S", "MO1z", "MO1y", "yG", "zG", "Iz", "Iy", "Iyz")})
    P = _assembleP(sec, prims, core, "intégrale symbolique" if symbolique else "intégrale numérique")
    P["IxDirect"] = R["IxDirect"]
    P["methodUsed"] = "symbolique" if symbolique else "numérique"
    P["integrals"] = _integralStrings(prims, R)

    fs = _num
    if symbolique:
        rep = ["Méthode B — intégration surfacique exacte (calcul symbolique SymPy, intégrales imbriquées)"]
    else:
        rep = ["Méthode B — intégration surfacique numérique (dblquad, tolérance relative 1e-13)"]
    rep += [_describeSection(sec)] + notes
    rep.append(
        "Coordonnées (y, z) dans le repère O1 ; rectangles : dS = dy·dz ; disques et couronnes : dS = r·dr·dθ "
        "avec y = yc + r·sin θ, z = zc + r·cos θ."
    )
    for k, p in enumerate(prims):
        sgTxt = "+" if p["sign"] > 0 else "−"
        if p["kind"] == "rect":
            rep.append(
                f"  {k + 1}. {p['label']} ({sgTxt}) : z ∈ [{fs(p['z1'])} ; {fs(p['z2'])}] m, "
                f"y ∈ [{fs(p['y1'])} ; {fs(p['y2'])}] m"
            )
        else:
            rep.append(
                f"  {k + 1}. {p['label']} ({sgTxt}) : centre (zc = {fs(p['zc'])} m, yc = {fs(p['yc'])} m), "
                f"r ∈ [{fs(p['Ri'])} ; {fs(p['R'])}] m, θ ∈ [0 ; 2π]"
            )
        rep.append(
            f"     S_{k + 1} = {fs(R['Si'][k])} m², M_O1z,{k + 1} = {fs(R['MO1zi'][k])} m³, "
            f"M_O1y,{k + 1} = {fs(R['MO1yi'][k])} m³ ; contributions en G : I_Gz = {fs(R['Izi'][k])} m⁴, "
            f"I_Gy = {fs(R['Iyi'][k])} m⁴, I_Gyz = {fs(R['Iyzi'][k])} m⁴"
        )
    rep.append(f"Aire : S = ∬ dS = {fs(P['S'])} m² ({fs(P['S'] * 1e4)} cm²)")
    rep.append(f"Moments statiques : M_O1z = ∬ y1 dS = {fs(P['MO1z'])} m³ ; M_O1y = ∬ z1 dS = {fs(P['MO1y'])} m³")
    rep.append(f"Barycentre : yG = M_O1z/S = {fs(P['yG'])} m ; zG = M_O1y/S = {fs(P['zG'])} m")
    rep.append(
        f"I_Gz = ∬ y² dS = {fs(P['Iz'])} m⁴ ({fs(P['Iz'] * 1e8)} cm⁴) ; "
        f"I_Gy = ∬ z² dS = {fs(P['Iy'])} m⁴ ({fs(P['Iy'] * 1e8)} cm⁴)"
    )
    rep.append(f"Produit d'inertie : I_Gyz = ∬ y·z dS = {fs(P['Iyz'])} m⁴")
    ecIx = abs(P["IxDirect"] - (P["Iz"] + P["Iy"])) / max(abs(P["IxDirect"]), np.finfo(float).tiny)
    rep.append(
        f"Contrôle : Ix = ∬ r² dS = {fs(P['IxDirect'])} m⁴ ; I_Gz + I_Gy = {fs(P['Iz'] + P['Iy'])} m⁴ "
        f"(écart relatif {ecIx:.2g})"
    )
    tex = [
        r"$S = \int\!\!\int_S dS = " + _texNum(P["S"]) + r"\ \mathrm{m^2}$",
        r"$y_G = \frac{1}{S}\int\!\!\int_S y_1\,dS = \frac{"
        + _texNum(P["MO1z"])
        + "}{"
        + _texNum(P["S"])
        + "} = "
        + _texNum(P["yG"])
        + r"\ \mathrm{m}$",
        r"$z_G = \frac{1}{S}\int\!\!\int_S z_1\,dS = \frac{"
        + _texNum(P["MO1y"])
        + "}{"
        + _texNum(P["S"])
        + "} = "
        + _texNum(P["zG"])
        + r"\ \mathrm{m}$",
        r"$I_{Gz} = \int\!\!\int_S y^2\,dS = " + _texNum(P["Iz"]) + r"\ \mathrm{m^4}$",
        r"$I_{Gy} = \int\!\!\int_S z^2\,dS = " + _texNum(P["Iy"]) + r"\ \mathrm{m^4}$",
        r"$I_{Gyz} = \int\!\!\int_S y\,z\,dS = " + _texNum(P["Iyz"]) + r"\ \mathrm{m^4}$",
        r"$I_x = \int\!\!\int_S r^2\,dS = " + _texNum(P["IxDirect"]) + r"\ \mathrm{m^4}$",
    ]
    repC, texC = _commonText(P)
    P["report"] = rep + repC
    P["latex"] = tex + texC
    return P


def tabulated(sec: dict) -> dict:
    """Caractéristiques d'un profilé lues dans le catalogue ; les valeurs absentes sont déduites.

    Entrée : `sec` (profilé du catalogue : h, b, a, e, S, Iz, Iy et, s'ils existent, Wz, Wy, rz, ry, c, J ou It ; m).
    Sortie : dict P comme analytical (sans huygens), method 'tabulée'.
    Erreur : MecaStruct:GeometryEngine:notProfile si sec.type n'est pas 'profile'.
    """
    sec = validateSection(sec)
    if sec["type"] != "profile":
        raise MecaStructError(
            _ID + "notProfile",
            "Les valeurs tabulées n'existent que pour un profilé du catalogue "
            f"(sec.type = 'profile') ; type fourni : '{sec['type']}'.",
        )
    S = _catField(sec, "S", "aire")
    Iz = _catField(sec, "Iz", "moment quadratique axe fort")
    Iy = _catField(sec, "Iy", "moment quadratique axe faible")
    h, b, a, e = sec["h"], sec["b"], sec["tw"], sec["tf"]
    fs = _num
    notes = []
    yG = h / 2
    if sec["profileShape"] == "U":
        c = _optField(sec, "c")
        if math.isfinite(c) and c > 0:
            zG = c
        else:
            zG = _huygensCore(_buildPrims(sec))["zG"]
            notes.append("Distance c (dos d'âme → G) absente du catalogue : zG calculé sur la géométrie simplifiée.")
    else:
        zG = b / 2

    P = {
        "type": "profile",
        "method": "tabulée",
        "S": S,
        "zG": zG,
        "yG": yG,
        "MO1z": S * yG,
        "MO1y": S * zG,
        "Iz": Iz,
        "Iy": Iy,
        "Iyz": 0.0,
        "Ix": Iz + Iy,
    }
    P["I1"], P["I2"], P["alphaP"] = _principal(Iz, Iy, 0.0)
    rz = _optField(sec, "rz")
    ry = _optField(sec, "ry")
    P["rz"] = rz if math.isfinite(rz) and rz > 0 else math.sqrt(Iz / S)
    P["ry"] = ry if math.isfinite(ry) and ry > 0 else math.sqrt(Iy / S)
    P["vyTop"], P["vyBot"], P["vzRight"], P["vzLeft"] = h - yG, yG, b - zG, zG
    Wz = _optField(sec, "Wz")
    Wy = _optField(sec, "Wy")
    P["Wz"] = Wz if math.isfinite(Wz) and Wz > 0 else Iz / max(P["vyTop"], P["vyBot"])
    P["Wy"] = Wy if math.isfinite(Wy) and Wy > 0 else Iy / max(P["vzRight"], P["vzLeft"])
    J = _optField(sec, "J")
    if not math.isfinite(J):
        J = _optField(sec, "It")
    if math.isfinite(J) and J > 0:
        P["J"], P["Jmethod"] = J, "valeur du catalogue"
    else:
        P["J"], P["Jmethod"] = math.nan, "non tabulée (voir la méthode analytique : Σ l·t³/3)"

    P["bbox"] = [0.0, b, 0.0, h]
    P["shear"] = {"kCours": math.nan, "kyCours": math.nan, "kNum": math.nan, "kyNum": math.nan}
    if sec["profileShape"] == "I":
        Sw = (h - 2 * e) * a
        P["k"], P["ky"], P["kSource"] = S / Sw, Sw / S, "cours"
        P["shear"]["kCours"], P["shear"]["kyCours"] = P["k"], P["ky"]
        kTxt = (
            f"k = S/S_âme = {fs(P['k'])}, ky = S_âme/S = {fs(P['ky'])} "
            f"(S_âme = (h − 2e)·a = {fs(Sw)} m², S du catalogue)"
        )
    else:
        f = shearFactors(sec)
        P["k"], P["ky"], P["kSource"] = f["kNum"], f["kyNum"], "numérique"
        P["shear"]["kNum"], P["shear"]["kyNum"] = P["k"], P["ky"]
        kTxt = f"k = {fs(P['k'])} (Jourawski), ky = {fs(P['ky'])} (énergie), calculés sur la géométrie simplifiée"
    P["kz"] = _shearZ(sec, _buildPrims(sec), P["ky"])
    kTxt += f" ; kz = {fs(P['kz'])} (énergie, effort tranchant Tz, géométrie simplifiée)"

    rep = [
        f"Valeurs tabulées du catalogue — {_describeSection(sec)}",
        "Convention : Iz (application) = axe fort = Iy (Eurocode) ; Iy (application) = axe faible = Iz (Eurocode).",
    ] + notes
    rep += [
        f"S = {fs(S)} m² ({fs(S * 1e4)} cm²)",
        f"G : yG = h/2 = {fs(yG)} m ; zG = {fs(zG)} m (repère O1)",
        f"Iz = {fs(Iz)} m⁴ ({fs(Iz * 1e8)} cm⁴) ; Iy = {fs(Iy)} m⁴ ({fs(Iy * 1e8)} cm⁴) ; Iyz = 0 (symétrie)",
        f"Ix = Iz + Iy = {fs(P['Ix'])} m⁴",
        f"rz = {fs(P['rz'])} m ; ry = {fs(P['ry'])} m",
        f"Wz = {fs(P['Wz'])} m³ ({fs(P['Wz'] * 1e6)} cm³) ; Wy = {fs(P['Wy'])} m³ ({fs(P['Wy'] * 1e6)} cm³)",
        f"J : {P['Jmethod']}",
        "Cisaillement : " + kTxt,
    ]
    P["report"] = rep
    P["latex"] = [
        r"$S = "
        + _texNum(S)
        + r"\ \mathrm{m^2},\ I_{Gz} = "
        + _texNum(Iz)
        + r"\ \mathrm{m^4},\ I_{Gy} = "
        + _texNum(Iy)
        + r"\ \mathrm{m^4}$",
        r"$r_z = \sqrt{\frac{I_{Gz}}{S}} = "
        + _texNum(P["rz"])
        + r"\ \mathrm{m},\ r_y = "
        + _texNum(P["ry"])
        + r"\ \mathrm{m}$",
        r"$W_z = " + _texNum(P["Wz"]) + r"\ \mathrm{m^3},\ W_y = " + _texNum(P["Wy"]) + r"\ \mathrm{m^3}$",
        r"$k = " + _texNum(P["k"]) + r",\ k_y = " + _texNum(P["ky"]) + "$",
    ]
    return P


def compare(sec: dict) -> pd.DataFrame:
    """Tableau comparatif des méthodes analytique, intégrale et tabulée.

    Entrée : `sec`. Sortie : DataFrame, index S, yG, zG, Iz, Iy, Iyz, Ix, rz, ry, Wz, Wy ; colonnes Analytique,
    Integrale, Tabulee (NaN si la section n'est pas un profilé) et EcartMax_pct (écart relatif maximal entre les
    colonnes disponibles, en %). `attrs` : units, analytical, integral, tabulated (None hors profilé), report
    (list[str], écarts commentés) et ecartAB_pct (écart analytique / intégrale, en %).
    """
    sec = validateSection(sec)
    A = analytical(sec)
    B = integral(sec)
    names = ["S", "yG", "zG", "Iz", "Iy", "Iyz", "Ix", "rz", "ry", "Wz", "Wy"]
    units = ["m^2", "m", "m", "m^4", "m^4", "m^4", "m^4", "m", "m", "m^3", "m^3"]
    isProfile = sec["type"] == "profile"
    T = tabulated(sec) if isProfile else None
    n = len(names)
    va, vb, vt = np.zeros(n), np.zeros(n), np.full(n, math.nan)
    ec, ecAB, ecT = np.zeros(n), np.zeros(n), np.zeros(n)
    Lref = max(A["bbox"][1] - A["bbox"][0], A["bbox"][3] - A["bbox"][2])
    for k, nom in enumerate(names):
        va[k] = A[nom]
        vb[k] = B[nom]
        if isProfile:
            vt[k] = T[nom]
        vals = np.array([va[k], vb[k], vt[k]])
        vals = vals[~np.isnan(vals)]
        if nom == "Iyz":
            den = max(*np.abs(vals), abs(A["Iz"]), abs(A["Iy"]))
        elif nom in ("yG", "zG"):
            den = max(*np.abs(vals), 1e-6 * Lref)
        else:
            den = np.abs(vals).max()
        if den > 0:
            ec[k] = 100 * (vals.max() - vals.min()) / den
            ecAB[k] = 100 * abs(va[k] - vb[k]) / den
        if isProfile and vt[k] != 0:
            ecT[k] = 100 * abs(va[k] - vt[k]) / abs(vt[k])

    C = pd.DataFrame({"Analytique": va, "Integrale": vb, "Tabulee": vt, "EcartMax_pct": ec}, index=names)
    fs = _num
    rep = [f"Comparaison des méthodes — {_describeSection(sec)}", f"Méthode B : {B['method']}."]
    iAB = int(np.argmax(ecAB))
    rep.append(
        f"Analytique / intégrale : écart relatif maximal {ecAB[iAB]:.3g} % ({names[iAB]}) — "
        "les deux méthodes sont exactes et doivent coïncider."
    )
    if isProfile:
        iT = int(np.argmax(ecT))
        rep.append(
            f"Catalogue / géométrie simplifiée : écart maximal {ecT[iT]:.3g} % ({names[iT]}, relatif au catalogue). "
            "Écart attendu de quelques % : les congés de raccordement (r) et l'inclinaison éventuelle des ailes ne "
            "sont pas modélisés par la géométrie simplifiée."
        )
        if ecT[iT] > 10:
            rep.append(
                "Écart supérieur à 10 % : typique des profilés à ailes inclinées (UPN, IPN), dont l'épaisseur d'aile e "
                "du catalogue est une valeur moyenne ; les grandeurs relatives à l'axe faible (zG, Iy, Wy) sont "
                "les plus affectées. Utiliser les valeurs tabulées pour le dimensionnement."
            )
        for k, nom in enumerate(names):
            if nom != "Iyz" and vt[k] != 0:
                rep.append(
                    f"  {nom} : analytique {fs(va[k])}, catalogue {fs(vt[k])} {units[k]} "
                    f"(écart {100 * (va[k] - vt[k]) / vt[k]:+.2f} %)"
                )
    C.attrs = {
        "units": units,
        "analytical": A,
        "integral": B,
        "tabulated": T,
        "report": rep,
        "ecartAB_pct": float(ecAB.max()),
    }
    return C


def shearFactors(sec: dict) -> dict:
    """Facteurs de cisaillement : k (τmax = k·T/S) et ky (section réduite ky·S), valeurs du cours et numériques.

    Entrée : `sec`. Sortie : dict kCours, kyCours (NaN si le type n'a pas de valeur du cours), kNum, kyNum (-),
    yAtMax (m, depuis G, cote du maximum de τ), Sweb (m², aire d'âme des I, NaN sinon), connected (bool, False si
    la section n'est pas connexe selon y), report (list[str]) et latex (list[str]).
    """
    sec = validateSection(sec)
    prims = _buildPrims(sec)
    return _shearCore(sec, prims, _huygensCore(prims))


# =====================================================================================
#  Validation
# =====================================================================================


def _present(sec: dict, name: str) -> bool:
    """Champ présent, non None et non vide (équivalent de isfield && ~isempty)."""
    return name in sec and sec[name] is not None and np.size(sec[name]) > 0


def _dimField(sec: dict, name: str, label: str, allowZero: bool = False) -> float:
    """Dimension obligatoire réelle finie, strictement positive (positive ou nulle si allowZero)."""
    if not _present(sec, name):
        raise MecaStructError(_ID + "missingField", f"Champ obligatoire manquant : sec.{name} ({label}, en m).")
    v = sec[name]
    if not is_num(v) or not math.isfinite(v) or v < 0 or (v == 0 and not allowZero):
        raise MecaStructError(
            _ID + "invalidDimensions",
            f"La dimension sec.{name} ({label}) doit être un réel strictement positif (m).",
        )
    return float(v)


def _optField(sec: dict, name: str) -> float:
    """Valeur numérique scalaire optionnelle ; NaN si absente ou non numérique."""
    x = sec.get(name)
    return float(x) if is_num(x) else math.nan


def _catField(sec: dict, name: str, label: str) -> float:
    """Valeur obligatoire du catalogue (profilé), finie et strictement positive."""
    v = _optField(sec, name)
    if not (math.isfinite(v) and v > 0):
        raise MecaStructError(
            _ID + "missingField", f"Valeur du catalogue manquante ou invalide : sec.{name} ({label}, SI)."
        )
    return v


def _checkThinWalls(t: str, h: float, b: float, tw: float, tf: float) -> None:
    """Cohérence des épaisseurs des profils I, T et U."""
    if t == "I":
        ok, msg = tw <= b and 2 * tf < h, "Profil I : il faut tw ≤ b et 2·tf < h"
    elif t == "T":
        ok, msg = tw <= b and tf < h, "Profil T : il faut tw ≤ b et tf < h"
    else:
        ok, msg = tw < b and 2 * tf < h, "Profil U : il faut tw < b et 2·tf < h"
    if not ok:
        raise MecaStructError(
            _ID + "invalidDimensions",
            f"{msg} (h = {_num(h)} m, b = {_num(b)} m, tw = {_num(tw)} m, tf = {_num(tf)} m).",
        )


def _resolveProfile(sec: dict) -> dict:
    """Profilé : forme simplifiée en I ou U (famille), épaisseurs a et e ; dimensions lues au catalogue si absentes."""
    fam = str(sec.get("family") or sec.get("Family") or "").strip().upper()
    nm = str(sec.get("name") or sec.get("Name") or "")
    if not fam and nm:
        m = re.match(r"\s*([A-Z]+)", nm.upper())
        if m:
            fam = m.group(1)
    if not _present(sec, "h") and fam and nm:
        # profilé désigné seulement par sa famille et son nom : les dimensions viennent du catalogue
        sec = {**data_manager.DataManager().getProfile(fam, nm), **sec}
    shape = str(sec.get("profileShape") or sec.get("shape") or "").upper()
    if shape not in ("I", "U"):
        if fam:
            shape = "U" if fam.startswith("U") else "I"
        else:
            shape = "U" if math.isfinite(_optField(sec, "c")) else "I"
    h = _dimField(sec, "h", "hauteur du profilé")
    b = _dimField(sec, "b", "largeur des ailes")
    a = _dimField(sec, "a", "épaisseur d'âme") if _present(sec, "a") else _dimField(sec, "tw", "épaisseur d'âme a")
    e = _dimField(sec, "e", "épaisseur d'aile") if _present(sec, "e") else _dimField(sec, "tf", "épaisseur d'aile e")
    _checkThinWalls(shape, h, b, a, e)
    return {**sec, "h": h, "b": b, "a": a, "e": e, "tw": a, "tf": e, "profileShape": shape, "family": fam, "name": nm}


def _matField(sec: dict, name: str, nc: int) -> np.ndarray:
    """Matrice optionnelle à nc colonnes réelles finies (vide si absente)."""
    if not _present(sec, name):
        return np.zeros((0, nc))
    try:
        M = np.atleast_2d(np.asarray(sec[name], dtype=float))
    except (TypeError, ValueError):
        M = None
    if M is None or M.ndim != 2 or M.shape[1] != nc or not np.all(np.isfinite(M)):
        raise MecaStructError(
            _ID + "invalidDimensions",
            f"Section composite : sec.{name} doit être une matrice réelle finie à {nc} colonnes (m).",
        )
    return M


def _validateComposite(sec: dict) -> dict:
    """Section composite : rectangles, trous rectangulaires, disques et trous circulaires, sans chevauchement."""
    rects = _matField(sec, "rects", 4)
    holes = _matField(sec, "holes", 4)
    disks = _matField(sec, "disks", 3)
    dholes = _matField(sec, "diskHoles", 3)
    if rects.size == 0 and disks.size == 0:
        raise MecaStructError(
            _ID + "missingField",
            "Section composite : sec.rects (N×4 [z1 z2 y1 y2], m) doit contenir au moins un rectangle.",
        )
    allR = np.vstack([rects, holes])
    if np.any(allR[:, 1] <= allR[:, 0]) or np.any(allR[:, 3] <= allR[:, 2]):
        raise MecaStructError(
            _ID + "invalidDimensions",
            "Section composite : chaque rectangle [z1 z2 y1 y2] doit vérifier z2 > z1 et y2 > y1.",
        )
    allD = np.vstack([disks, dholes])
    if np.any(allD[:, 2] <= 0):
        raise MecaStructError(
            _ID + "invalidDimensions", "Section composite : chaque disque [zc yc R] doit avoir un rayon R > 0."
        )
    bb = [math.inf, -math.inf, math.inf, -math.inf]
    if rects.size:
        bb = [rects[:, 0].min(), rects[:, 1].max(), rects[:, 2].min(), rects[:, 3].max()]
    if disks.size:
        bb = [
            min(bb[0], (disks[:, 0] - disks[:, 2]).min()),
            max(bb[1], (disks[:, 0] + disks[:, 2]).max()),
            min(bb[2], (disks[:, 1] - disks[:, 2]).min()),
            max(bb[3], (disks[:, 1] + disks[:, 2]).max()),
        ]
    Lref = max(bb[1] - bb[0], bb[3] - bb[2])
    tolA = 1e-10 * Lref**2
    tolL = 1e-9 * Lref
    # matière : pas de chevauchement
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if _rectOverlap(rects[i], rects[j]) > tolA:
                raise MecaStructError(
                    _ID + "overlap", f"Section composite : les rectangles {i + 1} et {j + 1} se chevauchent."
                )
        for j in range(len(disks)):
            if _rectDiskDistance(rects[i], disks[j, :2]) < disks[j, 2] - tolL:
                raise MecaStructError(
                    _ID + "overlap", f"Section composite : le rectangle {i + 1} et le disque {j + 1} se chevauchent."
                )
    for i in range(len(disks)):
        for j in range(i + 1, len(disks)):
            if math.hypot(disks[i, 0] - disks[j, 0], disks[i, 1] - disks[j, 1]) < disks[i, 2] + disks[j, 2] - tolL:
                raise MecaStructError(
                    _ID + "overlap", f"Section composite : les disques {i + 1} et {j + 1} se chevauchent."
                )
    # trous : contenus dans la matière, sans chevauchement mutuel
    for i in range(len(holes)):
        hA = (holes[i, 1] - holes[i, 0]) * (holes[i, 3] - holes[i, 2])
        cov = sum(_rectOverlap(holes[i], r) for r in rects)
        if cov < hA - tolA:
            raise MecaStructError(
                _ID + "holeOutside",
                f"Section composite : le trou rectangulaire {i + 1} n'est pas entièrement contenu dans les rectangles.",
            )
        for j in range(i + 1, len(holes)):
            if _rectOverlap(holes[i], holes[j]) > tolA:
                raise MecaStructError(
                    _ID + "overlap",
                    f"Section composite : les trous rectangulaires {i + 1} et {j + 1} se chevauchent.",
                )
        for j in range(len(dholes)):
            if _rectDiskDistance(holes[i], dholes[j, :2]) < dholes[j, 2] - tolL:
                raise MecaStructError(
                    _ID + "overlap",
                    f"Section composite : le trou rectangulaire {i + 1} et le trou circulaire {j + 1} se chevauchent.",
                )
    for i in range(len(dholes)):
        zc, yc, Rh = dholes[i]
        inDisk = any(math.hypot(zc - d[0], yc - d[1]) + Rh <= d[2] + tolL for d in disks)
        inRects = False
        if not inDisk and rects.size:
            rr, tt = np.meshgrid(np.array([0, 0.25, 0.5, 0.75, 0.9, 1]) * Rh, np.linspace(0, 2 * np.pi, 361))
            zs = (zc + rr * np.cos(tt)).ravel()
            ys = (yc + rr * np.sin(tt)).ravel()
            inside = np.zeros(zs.shape, dtype=bool)
            for r in rects:
                inside |= (zs >= r[0] - tolL) & (zs <= r[1] + tolL) & (ys >= r[2] - tolL) & (ys <= r[3] + tolL)
            inRects = bool(inside.all())
        if not inDisk and not inRects:
            raise MecaStructError(
                _ID + "holeOutside",
                f"Section composite : le trou circulaire {i + 1} n'est pas entièrement contenu dans la matière.",
            )
        for j in range(i + 1, len(dholes)):
            if math.hypot(zc - dholes[j, 0], yc - dholes[j, 1]) < Rh + dholes[j, 2] - tolL:
                raise MecaStructError(
                    _ID + "overlap",
                    f"Section composite : les trous circulaires {i + 1} et {j + 1} se chevauchent.",
                )
    return {**sec, "rects": rects, "holes": holes, "disks": disks, "diskHoles": dholes}


def _rectOverlap(r1, r2) -> float:
    """Aire de l'intersection de deux rectangles [z1 z2 y1 y2]."""
    return max(0.0, min(r1[1], r2[1]) - max(r1[0], r2[0])) * max(0.0, min(r1[3], r2[3]) - max(r1[2], r2[2]))


def _rectDiskDistance(r, c) -> float:
    """Distance du centre c = [zc yc] au rectangle r (0 si le centre est dans le rectangle)."""
    dz = max(r[0] - c[0], 0.0, c[0] - r[1])
    dy = max(r[2] - c[1], 0.0, c[1] - r[3])
    return math.hypot(dz, dy)


def _checkNumeric(y, name: str) -> None:
    """Vérifie que y est un tableau numérique réel (booléens et textes refusés)."""
    if np.asarray(y).dtype.kind not in "iuf":
        raise MecaStructError(
            _ID + "invalidInput", f"L'argument {name} doit être un tableau numérique réel (m, depuis G)."
        )


def _normalizeSide(side) -> str:
    """Côté de la limite pour widthAt : 'max', 'above' ou 'below'."""
    if not isinstance(side, str):
        raise MecaStructError(_ID + "invalidInput", "L'option side doit être 'max', 'dessus' ou 'dessous'.")
    key = side.strip().lower()
    if key in ("max", "ferme", "fermé", "closure"):
        return "max"
    if key in ("dessus", "above", "haut", "plus", "+"):
        return "above"
    if key in ("dessous", "below", "bas", "moins", "-"):
        return "below"
    raise MecaStructError(_ID + "invalidInput", f"Option side inconnue : '{side}' ('max', 'dessus' ou 'dessous').")


def _normalizeMode(mode) -> str:
    """Mode d'intégration : 'symbolique' ou 'numerique'."""
    if not isinstance(mode, str):
        raise MecaStructError(_ID + "unknownMode", "Le mode d'intégration doit être 'symbolique' ou 'numerique'.")
    key = mode.strip().lower()
    if key in ("symbolique", "symbolic", "sym", "exacte", "exact", "int"):
        return "symbolique"
    if key in ("numerique", "numérique", "numeric", "num", "integral2"):
        return "numerique"
    raise MecaStructError(_ID + "unknownMode", f"Mode d'intégration inconnu : '{key}' ('symbolique' ou 'numerique').")


# =====================================================================================
#  Primitives
# =====================================================================================


def _buildPrims(sec: dict) -> list[dict]:
    """Décomposition de la section (sec déjà validée) en primitives signées."""
    prims: list[dict] = []
    t = sec["type"]
    if t == "rectangle":
        _addRect(prims, 0, sec["b"], 0, sec["h"], 1, "Rectangle")
    elif t == "disque":
        R = sec["D"] / 2
        _addDisk(prims, "disk", R, R, R, 0, 1, "Disque")
    elif t == "couronne":
        R = sec["D"] / 2
        _addDisk(prims, "annulus", R, R, R, sec["d"] / 2, 1, "Couronne")
    elif t == "rectangle_creux":
        ep = sec["t"]
        _addRect(prims, 0, sec["B"], 0, sec["H"], 1, "Rectangle extérieur")
        _addRect(prims, ep, sec["B"] - ep, ep, sec["H"] - ep, -1, "Évidement intérieur")
    elif t == "I":
        _primsI(prims, sec["h"], sec["b"], sec["tw"], sec["tf"])
    elif t == "T":
        h, b, tw, tf = sec["h"], sec["b"], sec["tw"], sec["tf"]
        _addRect(prims, (b - tw) / 2, (b + tw) / 2, 0, h - tf, 1, "Âme")
        _addRect(prims, 0, b, h - tf, h, 1, "Aile")
    elif t == "U":
        _primsU(prims, sec["h"], sec["b"], sec["tw"], sec["tf"])
    elif t == "L":
        h, b, ep = sec["h"], sec["b"], sec["t"]
        _addRect(prims, 0, ep, 0, h, 1, "Aile verticale")
        _addRect(prims, ep, b, 0, ep, 1, "Aile horizontale")
    elif t == "profile":
        if sec["profileShape"] == "U":
            _primsU(prims, sec["h"], sec["b"], sec["tw"], sec["tf"])
        else:
            _primsI(prims, sec["h"], sec["b"], sec["tw"], sec["tf"])
    elif t == "composite":
        for k, r in enumerate(sec["rects"], 1):
            _addRect(prims, *r, 1, f"Rectangle {k}")
        for k, d in enumerate(sec["disks"], 1):
            _addDisk(prims, "disk", d[0], d[1], d[2], 0, 1, f"Disque {k}")
        for k, r in enumerate(sec["holes"], 1):
            _addRect(prims, *r, -1, f"Trou {k}")
        for k, d in enumerate(sec["diskHoles"], 1):
            _addDisk(prims, "disk", d[0], d[1], d[2], 0, -1, f"Trou circulaire {k}")
    return prims


def _primsI(prims: list[dict], h: float, b: float, tw: float, tf: float) -> None:
    """Profil I symétrique : aile inférieure, âme, aile supérieure."""
    _addRect(prims, 0, b, 0, tf, 1, "Aile inférieure")
    _addRect(prims, (b - tw) / 2, (b + tw) / 2, tf, h - tf, 1, "Âme")
    _addRect(prims, 0, b, h - tf, h, 1, "Aile supérieure")


def _primsU(prims: list[dict], h: float, b: float, tw: float, tf: float) -> None:
    """Profil U : âme à gauche, pleine hauteur, ailes vers la droite."""
    _addRect(prims, 0, tw, 0, h, 1, "Âme")
    _addRect(prims, tw, b, 0, tf, 1, "Aile inférieure")
    _addRect(prims, tw, b, h - tf, h, 1, "Aile supérieure")


def _addRect(prims: list[dict], z1, z2, y1, y2, sg, label: str) -> None:
    """Ajoute le rectangle [z1 z2] × [y1 y2] (repère O1)."""
    prims.append(
        {
            "kind": "rect",
            "sign": sg,
            "z1": z1,
            "z2": z2,
            "y1": y1,
            "y2": y2,
            "zc": (z1 + z2) / 2,
            "yc": (y1 + y2) / 2,
            "R": math.nan,
            "Ri": math.nan,
            "label": label,
        }
    )


def _addDisk(prims: list[dict], kind: str, zc, yc, R, Ri, sg, label: str) -> None:
    """Ajoute un disque ou une couronne de centre (zc, yc) (repère O1)."""
    prims.append(
        {
            "kind": kind,
            "sign": sg,
            "z1": zc - R,
            "z2": zc + R,
            "y1": yc - R,
            "y2": yc + R,
            "zc": zc,
            "yc": yc,
            "R": R,
            "Ri": Ri,
            "label": label,
        }
    )


def _primProps(p: dict) -> tuple[float, float, float, float, float]:
    """Aire, centre et moments quadratiques propres (non signés) d'une primitive : (A, zc, yc, IGz, IGy)."""
    if p["kind"] == "rect":
        w = p["z2"] - p["z1"]
        hh = p["y2"] - p["y1"]
        A, Igz, Igy = w * hh, w * hh**3 / 12, hh * w**3 / 12
    elif p["kind"] == "disk":
        A = math.pi * p["R"] ** 2
        Igz = math.pi * p["R"] ** 4 / 4
        Igy = Igz
    else:
        A = math.pi * (p["R"] ** 2 - p["Ri"] ** 2)
        Igz = math.pi * (p["R"] ** 4 - p["Ri"] ** 4) / 4
        Igy = Igz
    return A, p["zc"], p["yc"], Igz, Igy


def _bboxPrims(prims: list[dict]) -> list[float]:
    """Boîte englobante [zmin zmax ymin ymax] de la matière (m)."""
    pos = [p for p in prims if p["sign"] > 0]
    return [min(p["z1"] for p in pos), max(p["z2"] for p in pos), min(p["y1"] for p in pos), max(p["y2"] for p in pos)]


def _refLength(prims: list[dict]) -> float:
    """Dimension caractéristique : plus grand côté de la boîte englobante."""
    bb = _bboxPrims(prims)
    return max(bb[1] - bb[0], bb[3] - bb[2])


def _levels(prims: list[dict]) -> np.ndarray:
    """Cotes y (repère O1) où la largeur b(y) change de loi, sans doublon."""
    lev = []
    for p in prims:
        if p["kind"] == "rect":
            lev += [p["y1"], p["y2"]]
        else:
            lev += [p["yc"] - p["R"], p["yc"] + p["R"]]
            if p["Ri"] > 0:
                lev += [p["yc"] - p["Ri"], p["yc"] + p["Ri"]]
    lev = np.sort(np.array(lev, dtype=float))
    keep = np.concatenate(([True], np.diff(lev) > 1e-12 * _refLength(prims)))
    return lev[keep]


# =====================================================================================
#  Calculs : Huygens, formules fermées, axes principaux, torsion
# =====================================================================================


def _huygensCore(prims: list[dict]) -> dict:
    """Moments statiques, barycentre et théorème de Huygens (valeurs signées, trous négatifs) ; table détaillée."""
    n = len(prims)
    Si, zc, yc, IGz, IGy = (np.zeros(n) for _ in range(5))
    for k, p in enumerate(prims):
        Si[k], zc[k], yc[k], IGz[k], IGy[k] = _primProps(p)
    sg = np.array([p["sign"] for p in prims], dtype=float)
    Ss = sg * Si
    S = Ss.sum()
    if not S > 0:
        raise MecaStructError(
            _ID + "invalidDimensions", f"L'aire nette de la section est nulle ou négative (S = {_num(S)} m²)."
        )
    MO1z = np.sum(Ss * yc)
    MO1y = np.sum(Ss * zc)
    yG = MO1z / S
    zG = MO1y / S
    dy = yc - yG
    dz = zc - zG
    Lref = _refLength(prims)
    dy[np.abs(dy) <= 1e-12 * Lref] = 0  # résidus d'arrondi (éléments centrés sur G)
    dz[np.abs(dz) <= 1e-12 * Lref] = 0
    IGzs = sg * IGz
    IGys = sg * IGy
    SDy2 = Ss * dy**2
    SDz2 = Ss * dz**2
    SDyDz = Ss * dy * dz
    Izi = IGzs + SDy2
    Iyi = IGys + SDz2
    core = {
        "S": S,
        "MO1z": MO1z,
        "MO1y": MO1y,
        "yG": yG,
        "zG": zG,
        "Iz": Izi.sum(),
        "Iy": Iyi.sum(),
        "Iyz": SDyDz.sum(),
    }
    core = _cleanIyz(core)
    core["table"] = pd.DataFrame(
        {
            "Label": [p["label"] for p in prims],
            "S_i": Ss,
            "zG_i": zc,
            "yG_i": yc,
            "IGz_i": IGzs,
            "IGy_i": IGys,
            "dy_i": dy,
            "dz_i": dz,
            "SDy2": SDy2,
            "SDz2": SDz2,
            "Iz_i": Izi,
            "Iy_i": Iyi,
            "SDyDz": SDyDz,
        }
    )
    return core


def _cleanIyz(core: dict) -> dict:
    """Annule un produit d'inertie résiduel (arrondi) pour une section symétrique."""
    if abs(core["Iyz"]) <= 1e-12 * max(abs(core["Iz"]), abs(core["Iy"])):
        core["Iyz"] = 0.0
    return core


def _closedForm(sec: dict, core: dict) -> tuple[dict, list[str], list[str]]:
    """Formules fermées des sections élémentaires : (core complété, rapport, LaTeX) ; vides pour les autres types."""
    core = dict(core)
    t = sec["type"]
    if t == "rectangle":
        b, h = sec["b"], sec["h"]
        S, Iz, Iy = b * h, b * h**3 / 12, h * b**3 / 12
        rep = [
            f"S = b·h = {_num(b)} × {_num(h)} = {_num(S)} m² ({_num(S * 1e4)} cm²)",
            f"G au centre : zG = b/2 = {_num(b / 2)} m ; yG = h/2 = {_num(h / 2)} m",
            f"I_Gz = b·h³/12 = {_num(Iz)} m⁴ ({_num(Iz * 1e8)} cm⁴)",
            f"I_Gy = h·b³/12 = {_num(Iy)} m⁴ ({_num(Iy * 1e8)} cm⁴)",
            "I_Gyz = 0 (deux axes de symétrie)",
        ]
        tex = [
            r"$S = b\,h = " + _texNum(b) + r" \times " + _texNum(h) + " = " + _texNum(S) + r"\ \mathrm{m^2}$",
            r"$z_G = \frac{b}{2} = "
            + _texNum(b / 2)
            + r"\ \mathrm{m},\ y_G = \frac{h}{2} = "
            + _texNum(h / 2)
            + r"\ \mathrm{m}$",
            r"$I_{Gz} = \frac{b\,h^3}{12} = " + _texNum(Iz) + r"\ \mathrm{m^4}$",
            r"$I_{Gy} = \frac{h\,b^3}{12} = " + _texNum(Iy) + r"\ \mathrm{m^4}$",
        ]
        zG, yG = b / 2, h / 2
    elif t == "disque":
        D = sec["D"]
        S, Iz = math.pi * D**2 / 4, math.pi * D**4 / 64
        Iy = Iz
        rep = [
            f"S = π·D²/4 = {_num(S)} m² ({_num(S * 1e4)} cm²)",
            f"G au centre : zG = yG = D/2 = {_num(D / 2)} m",
            f"I_Gz = I_Gy = π·D⁴/64 = {_num(Iz)} m⁴ ({_num(Iz * 1e8)} cm⁴)",
            f"Ix = π·D⁴/32 = {_num(2 * Iz)} m⁴",
        ]
        tex = [
            r"$S = \frac{\pi D^2}{4} = " + _texNum(S) + r"\ \mathrm{m^2}$",
            r"$I_{Gz} = I_{Gy} = \frac{\pi D^4}{64} = " + _texNum(Iz) + r"\ \mathrm{m^4}$",
            r"$I_x = \frac{\pi D^4}{32} = " + _texNum(2 * Iz) + r"\ \mathrm{m^4}$",
        ]
        zG, yG = D / 2, D / 2
    elif t == "couronne":
        D, d = sec["D"], sec["d"]
        m = d / D
        S = math.pi * D**2 / 4 * (1 - m**2)
        Iz = math.pi * D**4 / 64 * (1 - m**4)
        Iy = Iz
        rep = [
            f"m = d/D = {_num(m)}",
            f"S = π·D²/4·(1 − m²) = {_num(S)} m² ({_num(S * 1e4)} cm²)",
            f"G au centre : zG = yG = D/2 = {_num(D / 2)} m",
            f"I_Gz = I_Gy = π·D⁴/64·(1 − m⁴) = {_num(Iz)} m⁴ ({_num(Iz * 1e8)} cm⁴)",
            f"Ix = π·D⁴/32·(1 − m⁴) = {_num(2 * Iz)} m⁴",
        ]
        tex = [
            r"$m = \frac{d}{D} = " + _texNum(m) + "$",
            r"$S = \frac{\pi D^2}{4}\left(1 - m^2\right) = " + _texNum(S) + r"\ \mathrm{m^2}$",
            r"$I_{Gz} = I_{Gy} = \frac{\pi D^4}{64}\left(1 - m^4\right) = " + _texNum(Iz) + r"\ \mathrm{m^4}$",
            r"$I_x = \frac{\pi D^4}{32}\left(1 - m^4\right) = " + _texNum(2 * Iz) + r"\ \mathrm{m^4}$",
        ]
        zG, yG = D / 2, D / 2
    elif t == "rectangle_creux":
        B, H, ep = sec["B"], sec["H"], sec["t"]
        bi, hi = B - 2 * ep, H - 2 * ep
        S = B * H - bi * hi
        Iz = (B * H**3 - bi * hi**3) / 12
        Iy = (H * B**3 - hi * bi**3) / 12
        rep = [
            f"Rectangle extérieur B×H moins évidement (B − 2t)×(H − 2t) = {_num(bi)} × {_num(hi)} m",
            f"S = B·H − (B − 2t)(H − 2t) = {_num(S)} m² ({_num(S * 1e4)} cm²)",
            f"G au centre : zG = B/2 = {_num(B / 2)} m ; yG = H/2 = {_num(H / 2)} m",
            f"I_Gz = [B·H³ − (B − 2t)(H − 2t)³]/12 = {_num(Iz)} m⁴ ({_num(Iz * 1e8)} cm⁴)",
            f"I_Gy = [H·B³ − (H − 2t)(B − 2t)³]/12 = {_num(Iy)} m⁴ ({_num(Iy * 1e8)} cm⁴)",
            "I_Gyz = 0 (deux axes de symétrie)",
        ]
        tex = [
            r"$S = B\,H - (B-2t)(H-2t) = " + _texNum(S) + r"\ \mathrm{m^2}$",
            r"$I_{Gz} = \frac{B\,H^3 - (B-2t)(H-2t)^3}{12} = " + _texNum(Iz) + r"\ \mathrm{m^4}$",
            r"$I_{Gy} = \frac{H\,B^3 - (H-2t)(B-2t)^3}{12} = " + _texNum(Iy) + r"\ \mathrm{m^4}$",
        ]
        zG, yG = B / 2, H / 2
    else:
        return core, [], []
    core.update(S=S, zG=zG, yG=yG, MO1z=S * yG, MO1y=S * zG, Iz=Iz, Iy=Iy, Iyz=0.0)
    return core, rep, tex


def _principal(Iz: float, Iy: float, Iyz: float) -> tuple[float, float, float]:
    """Moments principaux (I1 ≥ I2) et angle de l'axe 1 depuis z, tan 2α = −2 Iyz/(Iz − Iy)."""
    m = (Iz + Iy) / 2
    R = math.hypot((Iz - Iy) / 2, Iyz)
    if R <= 1e-12 * abs(m):
        alphaP = 0.0
    elif Iyz == 0:
        alphaP = 0.0 if Iz >= Iy else math.pi / 2
    else:
        alphaP = 0.5 * math.atan2(-2 * Iyz, Iz - Iy)
    return m + R, m - R, alphaP


def _torsionConstant(sec: dict, prims: list[dict]) -> tuple[float, str, str]:
    """Constante de torsion J (m⁴) selon le type de section : (J, texte du rapport, LaTeX)."""
    t = sec["type"]
    if t == "rectangle":
        return _saintVenant(sec["b"], sec["h"])
    if t == "disque":
        J = math.pi * sec["D"] ** 4 / 32
        return (
            J,
            "exacte : J = Ix = π·D⁴/32",
            r"$J = I_x = \frac{\pi D^4}{32} = " + _texNum(J) + r"\ \mathrm{m^4}$",
        )
    if t == "couronne":
        J = math.pi * (sec["D"] ** 4 - sec["d"] ** 4) / 32
        return (
            J,
            "exacte : J = Ix = π·(D⁴ − d⁴)/32",
            r"$J = I_x = \frac{\pi \left(D^4 - d^4\right)}{32} = " + _texNum(J) + r"\ \mathrm{m^4}$",
        )
    if t == "rectangle_creux":
        ep = sec["t"]
        Am = (sec["B"] - ep) * (sec["H"] - ep)
        pm = 2 * ((sec["B"] - ep) + (sec["H"] - ep))
        J = 4 * Am**2 * ep / pm
        txt = (
            f"Bredt (caisson mince) : J = 4·Am²·t/pm avec Am = (B − t)(H − t) = {_num(Am)} m², "
            f"pm = 2[(B − t) + (H − t)] = {_num(pm)} m"
        )
        tex = (
            r"$J = \frac{4\,A_m^2\,t}{p_m} = \frac{4 \times "
            + _texNum(Am)
            + r"^2 \times "
            + _texNum(ep)
            + r"}{"
            + _texNum(pm)
            + r"} = "
            + _texNum(J)
            + r"\ \mathrm{m^4}$"
        )
        return J, txt, tex
    if t in ("I", "T", "U", "L", "profile"):
        return _openThinWalled(prims)
    # section composite
    if any(p["sign"] < 0 for p in prims) or any(p["kind"] != "rect" for p in prims):
        return (
            math.nan,
            "non calculée (section composite avec trou(s) ou disque(s) : section fermée ou massive, "
            "aucune formule simple)",
            r"$J : \mathrm{non\ calculee}$",
        )
    if len(prims) == 1:
        p = prims[0]
        return _saintVenant(p["z2"] - p["z1"], p["y2"] - p["y1"])
    w = np.array([p["z2"] - p["z1"] for p in prims])
    hh = np.array([p["y2"] - p["y1"] for p in prims])
    ps = unary_union([_primPolyshape(p, _NC) for p in prims])
    if np.any(np.minimum(w, hh) / np.maximum(w, hh) > 0.2) or _nHoles(ps) > 0:
        return (
            math.nan,
            "non calculée (rectangles épais ou formant un contour fermé : la formule des parois minces ouvertes "
            "ne s'applique pas)",
            r"$J : \mathrm{non\ calculee}$",
        )
    return _openThinWalled(prims)


def _saintVenant(b: float, h: float) -> tuple[float, str, str]:
    """Rectangle plein (Saint-Venant, série de 100 termes) : a = grand côté, c = petit côté."""
    a, c = max(b, h), min(b, h)
    n = np.arange(1, 200, 2)
    s = np.sum(np.tanh(n * math.pi * a / (2 * c)) / n**5)
    J = a * c**3 / 3 * (1 - 192 * c / (math.pi**5 * a) * s)
    beta = J / (a * c**3)
    txt = (
        f"Saint-Venant (rectangle plein, a = {_num(a)} m, c = {_num(c)} m, série de 100 termes) : "
        f"J = β·a·c³ avec β = {beta:.5f}"
    )
    tex = (
        r"$J = \frac{a\,c^3}{3}\left[1 - \frac{192\,c}{\pi^5 a}\sum_{n\ impair} \frac{1}{n^5}"
        r"\tanh\frac{n \pi a}{2 c}\right] = "
        + _texNum(beta, 4)
        + r" \times a\,c^3 = "
        + _texNum(J)
        + r"\ \mathrm{m^4}$"
    )
    return J, txt, tex


def _openThinWalled(prims: list[dict]) -> tuple[float, str, str]:
    """Section ouverte à parois minces : J ≈ Σ l·t³/3 sur les rectangles (l = grand côté, t = épaisseur)."""
    J = 0.0
    for p in prims:
        w = p["z2"] - p["z1"]
        hh = p["y2"] - p["y1"]
        J += max(w, hh) * min(w, hh) ** 3 / 3
    txt = f"parois minces ouvertes : J ≈ Σ l_i·t_i³/3 sur les {len(prims)} rectangles (l = grand côté, t = épaisseur)"
    return J, txt, r"$J \approx \sum \frac{l_i\,t_i^3}{3} = " + _texNum(J) + r"\ \mathrm{m^4}$"


# =====================================================================================
#  Largeurs, moments statiques
# =====================================================================================


def _out(x):
    """Résultat vectorisé : float si l'entrée était un nombre, sinon tableau."""
    return float(x) if np.ndim(x) == 0 else x


def _q2b(prims: list[dict], yG: float, x: np.ndarray, tolW: float) -> np.ndarray:
    """Intégrande Q(y)²/b(y), nul où la largeur est nulle (extrémités des disques)."""
    Q = _firstMomentCore(prims, yG, x)
    b = _widthCore(prims, yG, x, "above")
    ok = b > tolW
    return np.where(ok, Q**2 / np.where(ok, b, 1.0), 0.0)


def _widthCore(prims: list[dict], yG: float, yrel: np.ndarray, side: str) -> np.ndarray:
    """Largeur b(y) (y depuis G), cotes proches d'une discontinuité recalées sur elle."""
    yrel = np.asarray(yrel, dtype=float)
    yy = yrel + yG
    L = _refLength(prims)
    for lv in _levels(prims):
        yy = np.where(np.abs(yy - lv) <= 1e-10 * L, lv, yy)
    if side == "above":
        b = _widthSide(prims, yy, True)
    elif side == "below":
        b = _widthSide(prims, yy, False)
    else:
        b = np.maximum(_widthSide(prims, yy, True), _widthSide(prims, yy, False))
    b = np.where(np.abs(b) <= 1e-12 * L, 0.0, b)
    return np.where(np.isnan(yrel), np.nan, b)


def _widthSide(prims: list[dict], yy: np.ndarray, above: bool) -> np.ndarray:
    """Somme signée des largeurs des primitives, limite par au-dessus (above) ou par en dessous."""
    b = np.zeros(np.shape(yy))
    for p in prims:
        if p["kind"] == "rect":
            if above:
                inside = (yy >= p["y1"]) & (yy < p["y2"])
            else:
                inside = (yy > p["y1"]) & (yy <= p["y2"])
            w = (p["z2"] - p["z1"]) * inside
        elif p["kind"] == "disk":
            w = 2 * np.sqrt(np.fmax(p["R"] ** 2 - (yy - p["yc"]) ** 2, 0))
        else:
            w = 2 * np.sqrt(np.fmax(p["R"] ** 2 - (yy - p["yc"]) ** 2, 0)) - 2 * np.sqrt(
                np.fmax(p["Ri"] ** 2 - (yy - p["yc"]) ** 2, 0)
            )
        b = b + p["sign"] * w
    return b


def _firstMomentCore(prims: list[dict], yG: float, yrel: np.ndarray) -> np.ndarray:
    """Moment statique par rapport à (G, z) de la partie au-dessus de y (y depuis G).

    Pour y < 0, Q est pris comme l'opposé du moment de la partie inférieure (meilleure précision relative).
    """
    yrel = np.asarray(yrel, dtype=float)
    yy = yrel + yG
    Qa = np.zeros(yy.shape)
    Qb = np.zeros(yy.shape)
    for p in prims:
        if p["kind"] == "rect":
            w = p["z2"] - p["z1"]
            lo = np.maximum(yy, p["y1"])
            qa = np.where(yy >= p["y2"], 0.0, w * ((p["y2"] - yG) ** 2 - (lo - yG) ** 2) / 2)
            hi = np.minimum(yy, p["y2"])
            qb = np.where(yy <= p["y1"], 0.0, w * ((hi - yG) ** 2 - (p["y1"] - yG) ** 2) / 2)
        else:
            qa, qb = _diskQ(yy, p["yc"], p["R"], yG)
            if p["Ri"] > 0:
                qai, qbi = _diskQ(yy, p["yc"], p["Ri"], yG)
                qa, qb = qa - qai, qb - qbi
        Qa = Qa + p["sign"] * qa
        Qb = Qb + p["sign"] * qb
    Q = np.where(yrel < 0, -Qb, Qa)
    bb = _bboxPrims(prims)
    tol = 1e-12 * max(bb[1] - bb[0], bb[3] - bb[2])
    Q = np.where((yy <= bb[2] + tol) | (yy >= bb[3] - tol), 0.0, Q)
    return np.where(np.isnan(yrel), np.nan, Q)


def _diskQ(yy: np.ndarray, yc: float, R: float, yG: float) -> tuple[np.ndarray, np.ndarray]:
    """Moments statiques des segments de disque au-dessus (qa) et au-dessous (qb) de la cote yy."""
    u = np.fmin(np.fmax(yy - yc, -R), R)
    s = np.sqrt(np.fmax(R**2 - u**2, 0))
    Aa = R**2 * np.arccos(u / R) - u * s
    Ab = R**2 * np.arccos(-u / R) + u * s
    qa = (2 / 3) * s**3 + (yc - yG) * Aa
    qb = -(2 / 3) * s**3 + (yc - yG) * Ab
    return qa, qb


# =====================================================================================
#  Contours et polygones
# =====================================================================================


def _rectPoly(z1, z2, y1, y2) -> np.ndarray:
    """Rectangle fermé [z y], sens trigonométrique."""
    return np.array([[z1, y1], [z2, y1], [z2, y2], [z1, y2], [z1, y1]], dtype=float)


def _circlePoly(zc, yc, R, n: int) -> np.ndarray:
    """Cercle fermé à n segments [z y], sens trigonométrique."""
    t = np.linspace(0, 2 * np.pi, n + 1)
    P = np.column_stack([zc + R * np.cos(t), yc + R * np.sin(t)])
    P[-1] = P[0]
    return P


def _shapePoly(sec: dict) -> np.ndarray:
    """Contour extérieur des profils I, T, U, L (sens trigonométrique), sans sommets consécutifs identiques."""
    shape = sec["profileShape"] if sec["type"] == "profile" else sec["type"]
    h, b = sec["h"], sec["b"]
    if shape == "I":
        tw, tf = sec["tw"], sec["tf"]
        zl, zr = (b - tw) / 2, (b + tw) / 2
        pts = [
            (0, 0),
            (b, 0),
            (b, tf),
            (zr, tf),
            (zr, h - tf),
            (b, h - tf),
            (b, h),
            (0, h),
            (0, h - tf),
            (zl, h - tf),
            (zl, tf),
            (0, tf),
            (0, 0),
        ]
    elif shape == "T":
        tw, tf = sec["tw"], sec["tf"]
        zl, zr = (b - tw) / 2, (b + tw) / 2
        pts = [(zl, 0), (zr, 0), (zr, h - tf), (b, h - tf), (b, h), (0, h), (0, h - tf), (zl, h - tf), (zl, 0)]
    elif shape == "U":
        tw, tf = sec["tw"], sec["tf"]
        pts = [(0, 0), (b, 0), (b, tf), (tw, tf), (tw, h - tf), (b, h - tf), (b, h), (0, h), (0, 0)]
    else:
        t = sec["t"]
        pts = [(0, 0), (b, 0), (b, t), (t, t), (t, h), (0, h), (0, 0)]
    P = np.array(pts, dtype=float)
    keep = np.concatenate(([True], np.any(np.diff(P, axis=0) != 0, axis=1)))
    return P[keep]


def _primPolyshape(p: dict, n: int) -> Polygon:
    """Polygone shapely d'une primitive (rectangle, ou cercle à n segments)."""
    if p["kind"] == "rect":
        return Polygon([(p["z1"], p["y1"]), (p["z2"], p["y1"]), (p["z2"], p["y2"]), (p["z1"], p["y2"])])
    c = _circlePoly(p["zc"], p["yc"], p["R"], n)
    return Polygon(c[:-1])


def _parts(geom) -> list:
    """Polygones d'une géométrie shapely (un seul ou plusieurs)."""
    return list(getattr(geom, "geoms", [geom]))


def _nHoles(geom) -> int:
    """Nombre de trous d'une géométrie shapely."""
    return sum(len(g.interiors) for g in _parts(geom))


def _closePoly(P: np.ndarray) -> np.ndarray:
    """Contour fermé : points non finis retirés, dernier point égal au premier."""
    P = P[np.all(np.isfinite(P), axis=1)]
    if P.size and np.any(P[0] != P[-1]):
        P = np.vstack([P, P[0]])
    return P


def _orientPoly(P: np.ndarray, ccw: bool) -> np.ndarray:
    """Impose le sens de parcours d'un contour fermé (ccw = True : trigonométrique)."""
    a = 0.5 * np.sum(P[:-1, 0] * P[1:, 1] - P[1:, 0] * P[:-1, 1])
    return P[::-1] if (a < 0) == ccw else P


# =====================================================================================
#  Textes du rapport et LaTeX
# =====================================================================================


def _typeLabel(sec: dict) -> str:
    """Nom lisible du type de section."""
    return {
        "rectangle": "rectangle plein",
        "disque": "disque plein",
        "couronne": "couronne",
        "rectangle_creux": "rectangle creux",
        "I": "profil en I",
        "T": "profil en T",
        "U": "profil en U",
        "L": "cornière L",
        "profile": "profilé du catalogue",
    }.get(sec["type"], "section composite")


def _describeSection(sec: dict) -> str:
    """Description de la section avec ses dimensions (mm)."""

    def mm(x: float) -> str:
        return _num(1000 * x) + " mm"

    t = sec["type"]
    if t == "rectangle":
        return f"Rectangle : b = {mm(sec['b'])} (selon z), h = {mm(sec['h'])} (selon y)"
    if t == "disque":
        return f"Disque : D = {mm(sec['D'])}"
    if t == "couronne":
        return f"Couronne : D = {mm(sec['D'])}, d = {mm(sec['d'])}"
    if t == "rectangle_creux":
        return f"Rectangle creux : B = {mm(sec['B'])}, H = {mm(sec['H'])}, t = {mm(sec['t'])}"
    if t in ("I", "T", "U"):
        return f"Profil {t} : h = {mm(sec['h'])}, b = {mm(sec['b'])}, tw = {mm(sec['tw'])}, tf = {mm(sec['tf'])}"
    if t == "L":
        return f"Cornière L : h = {mm(sec['h'])}, b = {mm(sec['b'])}, t = {mm(sec['t'])}"
    if t == "profile":
        nm = sec["name"].strip() or sec["family"] or "profilé"
        return (
            f"Profilé {nm} (géométrie simplifiée en {sec['profileShape']}) : h = {mm(sec['h'])}, "
            f"b = {mm(sec['b'])}, a = {mm(sec['tw'])}, e = {mm(sec['tf'])}"
        )
    return (
        f"Section composite : {len(sec['rects'])} rectangle(s), {len(sec['holes'])} trou(s) rectangulaire(s), "
        f"{len(sec['disks'])} disque(s), {len(sec['diskHoles'])} trou(s) circulaire(s) (repère utilisateur)"
    )


def _huygensText(core: dict) -> tuple[list[str], list[str]]:
    """Démarche de Huygens : (rapport, LaTeX)."""
    rows = core["table"].to_dict("records")
    n = len(rows)
    rep = [f"Décomposition en {n} élément(s) (repère O1 ; valeurs signées, trous négatifs) :"]
    for k, r in enumerate(rows, 1):
        rep.append(
            f"  {k}. {r['Label']} : S_i = {_num(r['S_i'])} m², zG_i = {_num(r['zG_i'])} m, "
            f"yG_i = {_num(r['yG_i'])} m, IGz_i = {_num(r['IGz_i'])} m⁴, IGy_i = {_num(r['IGy_i'])} m⁴"
        )
    rep.append(f"Aire : S = Σ S_i = {_num(core['S'])} m² ({_num(core['S'] * 1e4)} cm²)")
    rep.append(
        f"Moments statiques : M_O1z = Σ S_i·yG_i = {_num(core['MO1z'])} m³ ; "
        f"M_O1y = Σ S_i·zG_i = {_num(core['MO1y'])} m³"
    )
    rep.append(f"Barycentre : yG = M_O1z/S = {_num(core['yG'])} m ; zG = M_O1y/S = {_num(core['zG'])} m")
    rep.append("Théorème de Huygens (dy_i = yG_i − yG, dz_i = zG_i − zG) :")
    for k, r in enumerate(rows, 1):
        rep.append(
            f"  {k}. dy = {_num(r['dy_i'])} m, dz = {_num(r['dz_i'])} m : Iz_i = IGz_i + S_i·dy² = "
            f"{_num(r['IGz_i'])}{_plusTxt(r['SDy2'])} = {_num(r['Iz_i'])} m⁴ ; Iy_i = IGy_i + S_i·dz² = "
            f"{_num(r['IGy_i'])}{_plusTxt(r['SDz2'])} = {_num(r['Iy_i'])} m⁴"
        )
    rep.append(f"I_Gz = Σ (IGz_i + S_i·dy_i²) = {_num(core['Iz'])} m⁴ ({_num(core['Iz'] * 1e8)} cm⁴)")
    rep.append(f"I_Gy = Σ (IGy_i + S_i·dz_i²) = {_num(core['Iy'])} m⁴ ({_num(core['Iy'] * 1e8)} cm⁴)")
    rep.append(f"I_Gyz = Σ S_i·dy_i·dz_i = {_num(core['Iyz'])} m⁴")
    tex = [
        r"$S = \sum S_i = " + _texNum(core["S"]) + r"\ \mathrm{m^2}$",
        r"$y_G = \frac{M_{O_1z_1}}{S} = \frac{\sum S_i\,y_{Gi}}{\sum S_i} = \frac{"
        + _texNum(core["MO1z"])
        + "}{"
        + _texNum(core["S"])
        + "} = "
        + _texNum(core["yG"])
        + r"\ \mathrm{m}$",
        r"$z_G = \frac{M_{O_1y_1}}{S} = \frac{\sum S_i\,z_{Gi}}{\sum S_i} = \frac{"
        + _texNum(core["MO1y"])
        + "}{"
        + _texNum(core["S"])
        + "} = "
        + _texNum(core["zG"])
        + r"\ \mathrm{m}$",
    ]
    for k, r in enumerate(rows[:12], 1):
        ks = str(k)
        term = " + 0" if r["SDy2"] == 0 else _offStr(r["SDy2"])
        tex.append(
            r"$("
            + ks
            + r"):\ S_{"
            + ks
            + r"} = "
            + _texNum(r["S_i"])
            + r",\ I_{Gz_{"
            + ks
            + r"}} + S_{"
            + ks
            + r"}\,d_{y"
            + ks
            + r"}^2 = "
            + _texNum(r["IGz_i"])
            + term
            + " = "
            + _texNum(r["Iz_i"])
            + "$"
        )
    tex += [
        r"$I_{Gz} = \sum \left(I_{Gz_i} + S_i\,d_{y_i}^2\right) = " + _texNum(core["Iz"]) + r"\ \mathrm{m^4}$",
        r"$I_{Gy} = \sum \left(I_{Gy_i} + S_i\,d_{z_i}^2\right) = " + _texNum(core["Iy"]) + r"\ \mathrm{m^4}$",
        r"$I_{Gyz} = \sum S_i\,d_{y_i}\,d_{z_i} = " + _texNum(core["Iyz"]) + r"\ \mathrm{m^4}$",
    ]
    return rep, tex


def _commonText(P: dict) -> tuple[list[str], list[str]]:
    """Grandeurs dérivées communes à toutes les méthodes : (rapport, LaTeX)."""
    sh = P["shear"]
    deg = P["alphaP"] * 180 / math.pi
    rep = [f"Moment polaire : Ix = I_Gz + I_Gy = {_num(P['Ix'])} m⁴ ({_num(P['Ix'] * 1e8)} cm⁴)"]
    if P["Iyz"] != 0:
        rep.append(
            "Axes principaux : I1,2 = (Iz + Iy)/2 ± √[((Iz − Iy)/2)² + Iyz²] ⇒ "
            f"I1 = {_num(P['I1'])} m⁴, I2 = {_num(P['I2'])} m⁴ ; tan 2α = −2·Iyz/(Iz − Iy) ⇒ "
            f"αP = {_num(P['alphaP'])} rad ({_num(deg)}°) depuis z"
        )
    else:
        rep.append(
            "Axes principaux : Iyz = 0, les axes (G, z) et (G, y) sont principaux ; "
            f"I1 = {_num(P['I1'])} m⁴, I2 = {_num(P['I2'])} m⁴, αP = {_num(deg)}°"
        )
    rep.append(
        f"Rayons de giration : rz = √(Iz/S) = {_num(P['rz'])} m ({_num(P['rz'] * 1e3)} mm) ; "
        f"ry = √(Iy/S) = {_num(P['ry'])} m ({_num(P['ry'] * 1e3)} mm)"
    )
    rep.append(
        f"Fibres extrêmes : vy,haut = {_num(P['vyTop'])} m, vy,bas = {_num(P['vyBot'])} m, "
        f"vz,droite = {_num(P['vzRight'])} m, vz,gauche = {_num(P['vzLeft'])} m"
    )
    rep.append(
        f"Modules de flexion : Wz = Iz/vy,max = {_num(P['Wz'])} m³ ({_num(P['Wz'] * 1e6)} cm³) ; "
        f"Wy = Iy/vz,max = {_num(P['Wy'])} m³ ({_num(P['Wy'] * 1e6)} cm³)"
    )
    rep.append(f"Constante de torsion : J = {_num(P['J'])} m⁴ — {P['Jmethod']}")
    rep.append(
        f"Cisaillement : k = {_num(P['k'])}, ky = {_num(P['ky'])} (source : {P['kSource']}) ; "
        f"Jourawski kNum = {_num(sh['kNum'])}, énergie kyNum = {_num(sh['kyNum'])} ; kz = {_num(P['kz'])} (Tz)"
    )
    rep += sh["report"][1:]
    tex = [r"$I_x = I_{Gz} + I_{Gy} = " + _texNum(P["Ix"]) + r"\ \mathrm{m^4}$"]
    if P["Iyz"] != 0:
        tex.append(
            r"$I_{1,2} = \frac{I_{Gz}+I_{Gy}}{2} \pm \sqrt{\left(\frac{I_{Gz}-I_{Gy}}{2}\right)^2 "
            r"+ I_{Gyz}^2} \Rightarrow I_1 = " + _texNum(P["I1"]) + r",\ I_2 = " + _texNum(P["I2"]) + r"\ \mathrm{m^4}$"
        )
        tex.append(
            r"$\tan 2\alpha_P = \frac{-2\,I_{Gyz}}{I_{Gz}-I_{Gy}} \Rightarrow \alpha_P = "
            + _texNum(deg, 4)
            + r"^{\circ}$"
        )
    else:
        tex.append(
            r"$I_{Gyz} = 0 \Rightarrow I_1 = "
            + _texNum(P["I1"])
            + r",\ I_2 = "
            + _texNum(P["I2"])
            + r"\ \mathrm{m^4},\ \alpha_P = "
            + _texNum(deg, 4)
            + r"^{\circ}$"
        )
    tex += [
        r"$r_z = \sqrt{\frac{I_{Gz}}{S}} = "
        + _texNum(P["rz"])
        + r"\ \mathrm{m},\ r_y = \sqrt{\frac{I_{Gy}}{S}} = "
        + _texNum(P["ry"])
        + r"\ \mathrm{m}$",
        r"$W_z = \frac{I_{Gz}}{v_{y,max}} = \frac{"
        + _texNum(P["Iz"])
        + "}{"
        + _texNum(max(P["vyTop"], P["vyBot"]))
        + "} = "
        + _texNum(P["Wz"])
        + r"\ \mathrm{m^3}$",
        r"$W_y = \frac{I_{Gy}}{v_{z,max}} = \frac{"
        + _texNum(P["Iy"])
        + "}{"
        + _texNum(max(P["vzRight"], P["vzLeft"]))
        + "} = "
        + _texNum(P["Wy"])
        + r"\ \mathrm{m^3}$",
        P["Jlatex"],
    ]
    tex += sh["latex"]
    return rep, tex


def _plusTxt(x: float) -> str:
    """Terme additif signé pour les rapports : « + x » ou « − |x| »."""
    return f" − {_num(-x)}" if x < 0 else f" + {_num(x)}"


def _offStr(v: float) -> str:
    """Terme additif signé pour le LaTeX : « + v » ou « - |v| » (vide si v = 0)."""
    if v == 0:
        return ""
    return " + " + _texNum(v) if v > 0 else " - " + _texNum(-v)


def _texNum(x: float, nd: int = 5) -> str:
    """Nombre au format LaTeX, puissances de 10 explicites (\\times 10^{n})."""
    if math.isnan(x):
        return r"\mathrm{NaN}"
    if math.isinf(x):
        return r"\infty" if x > 0 else r"-\infty"
    if x == 0:
        return "0"
    s = f"{x:.{nd}g}"
    if "e" in s:
        mant, ex = s.split("e")
        ex_n = int(ex)
        if mant == "1":
            s = f"10^{{{ex_n}}}"
        elif mant == "-1":
            s = f"-10^{{{ex_n}}}"
        else:
            s = f"{mant} \\times 10^{{{ex_n}}}"
    return s


# =====================================================================================
#  Assemblage, cisaillement, intégrales (étape E07)
# =====================================================================================


def _assembleP(sec: dict, prims: list[dict], core: dict, method: str) -> dict:
    """Champs communs des méthodes analytique et intégrale (GeometryEngine.assembleP)."""
    S, Iz, Iy = core["S"], core["Iz"], core["Iy"]
    P = {
        "type": sec["type"],
        "method": method,
        "S": S,
        "zG": core["zG"],
        "yG": core["yG"],
        "MO1z": core["MO1z"],
        "MO1y": core["MO1y"],
        "Iz": Iz,
        "Iy": Iy,
        "Iyz": core["Iyz"],
        "Ix": Iz + Iy,
    }
    P["I1"], P["I2"], P["alphaP"] = _principal(Iz, Iy, core["Iyz"])
    P["rz"] = math.sqrt(Iz / S)
    P["ry"] = math.sqrt(Iy / S)
    bb = _bboxPrims(prims)
    P["vyTop"] = bb[3] - core["yG"]
    P["vyBot"] = core["yG"] - bb[2]
    P["vzRight"] = bb[1] - core["zG"]
    P["vzLeft"] = core["zG"] - bb[0]
    P["Wz"] = Iz / max(P["vyTop"], P["vyBot"])
    P["Wy"] = Iy / max(P["vzRight"], P["vzLeft"])
    P["J"], P["Jmethod"], P["Jlatex"] = _torsionConstant(sec, prims)
    f = _shearCore(sec, prims, core)
    if not math.isnan(f["kCours"]):
        P["k"], P["ky"], P["kSource"] = f["kCours"], f["kyCours"], "cours"
    else:
        P["k"], P["ky"], P["kSource"] = f["kNum"], f["kyNum"], "numérique"
    P["kz"] = _shearZ(sec, prims, P["ky"])
    P["shear"] = f
    P["bbox"] = bb
    P["report"] = []
    P["latex"] = []
    return P


def _innerRadius(p: dict) -> float:
    """Rayon intérieur d'une primitive circulaire (0 pour un disque plein)."""
    return p["Ri"] if p["kind"] == "annulus" and p["Ri"] > 0 else 0.0


def _primIntegral(p: dict, L: float, g) -> float:
    """∬ g(y, z) dS sur la primitive p, en coordonnées adimensionnées (x/L) ; signe non appliqué."""
    # tolérance absolue 1e-15 comme AbsTol de MATLAB : évite de chercher une précision relative sur les zéros
    if p["kind"] == "rect":
        return dblquad(
            lambda yy, zz: g(yy, zz), p["z1"] / L, p["z2"] / L, p["y1"] / L, p["y2"] / L, epsabs=1e-15, epsrel=1e-13
        )[0]
    ycs, zcs = p["yc"] / L, p["zc"] / L
    return dblquad(
        lambda rr, tt: g(ycs + rr * np.sin(tt), zcs + rr * np.cos(tt)) * rr,
        0.0,
        2 * np.pi,
        _innerRadius(p) / L,
        p["R"] / L,
        epsabs=1e-15,
        epsrel=1e-13,
    )[0]


def _integrateNumeric(prims: list[dict]) -> dict:
    """Intégrales doubles numériques en coordonnées adimensionnées (x/L), primitive par primitive."""
    L = _refLength(prims)
    Si = np.array([p["sign"] * L**2 * _primIntegral(p, L, lambda y, z: 1.0) for p in prims])
    MO1zi = np.array([p["sign"] * L**3 * _primIntegral(p, L, lambda y, z: y) for p in prims])
    MO1yi = np.array([p["sign"] * L**3 * _primIntegral(p, L, lambda y, z: z) for p in prims])
    S = Si.sum()
    yG = MO1zi.sum() / S
    zG = MO1yi.sum() / S
    yGs, zGs = yG / L, zG / L
    Izi = np.array([p["sign"] * L**4 * _primIntegral(p, L, lambda y, z: (y - yGs) ** 2) for p in prims])
    Iyi = np.array([p["sign"] * L**4 * _primIntegral(p, L, lambda y, z: (z - zGs) ** 2) for p in prims])
    Iyzi = np.array([p["sign"] * L**4 * _primIntegral(p, L, lambda y, z: (y - yGs) * (z - zGs)) for p in prims])
    Ixi = np.array(
        [p["sign"] * L**4 * _primIntegral(p, L, lambda y, z: (y - yGs) ** 2 + (z - zGs) ** 2) for p in prims]
    )
    return {
        "Si": Si,
        "MO1zi": MO1zi,
        "MO1yi": MO1yi,
        "Izi": Izi,
        "Iyi": Iyi,
        "Iyzi": Iyzi,
        "Ixi": Ixi,
        "S": S,
        "MO1z": MO1zi.sum(),
        "MO1y": MO1yi.sum(),
        "yG": yG,
        "zG": zG,
        "Iz": Izi.sum(),
        "Iy": Iyi.sum(),
        "Iyz": Iyzi.sum(),
        "IxDirect": Ixi.sum(),
    }


def _integrateSymbolic(prims: list[dict]) -> dict:
    """Intégrales doubles exactes par SymPy, primitive par primitive ; résultats convertis en float."""
    import sympy as sp  # import tardif : SymPy est optionnel

    y, z = sp.symbols("y z", real=True)
    r = sp.symbols("r", positive=True)
    th = sp.symbols("theta", real=True)

    def exact(v: float):
        return sp.Rational(float(v))  # rationnel exact du flottant, comme sym(x) de MATLAB

    def integ(p: dict, g):
        """∬ g(y, z) dS sur la primitive p, exacte ; signe non appliqué."""
        if p["kind"] == "rect":
            inner = sp.integrate(g(y, z), (y, exact(p["y1"]), exact(p["y2"])))
            return sp.integrate(inner, (z, exact(p["z1"]), exact(p["z2"])))
        yy = exact(p["yc"]) + r * sp.sin(th)
        zz = exact(p["zc"]) + r * sp.cos(th)
        inner = sp.integrate(g(yy, zz) * r, (r, exact(_innerRadius(p)), exact(p["R"])))
        return sp.integrate(inner, (th, 0, 2 * sp.pi))

    def sums(g):
        """Termes signés ∬ g dS de chaque primitive, et leur somme."""
        terms = [p["sign"] * integ(p, g) for p in prims]
        return terms, sum(terms)

    Si_t, S = sums(lambda a, b: 1)
    MO1zi_t, MO1z = sums(lambda a, b: a)
    MO1yi_t, MO1y = sums(lambda a, b: b)
    yG = MO1z / S
    zG = MO1y / S
    Izi_t, Iz = sums(lambda a, b: (a - yG) ** 2)
    Iyi_t, Iy = sums(lambda a, b: (b - zG) ** 2)
    Iyzi_t, Iyz = sums(lambda a, b: (a - yG) * (b - zG))
    Ixi_t, Ix = sums(lambda a, b: (a - yG) ** 2 + (b - zG) ** 2)

    def arr(terms):
        return np.array([float(t) for t in terms])

    return {
        "Si": arr(Si_t),
        "MO1zi": arr(MO1zi_t),
        "MO1yi": arr(MO1yi_t),
        "Izi": arr(Izi_t),
        "Iyi": arr(Iyi_t),
        "Iyzi": arr(Iyzi_t),
        "Ixi": arr(Ixi_t),
        "S": float(S),
        "MO1z": float(MO1z),
        "MO1y": float(MO1y),
        "yG": float(yG),
        "zG": float(zG),
        "Iz": float(Iz),
        "Iy": float(Iy),
        "Iyz": float(Iyz),
        "IxDirect": float(Ix),
    }


def _integralStrings(prims: list[dict], R: dict) -> list[str]:
    """Intégrales posées en LaTeX avec leurs bornes numériques : sept lignes par primitive."""
    tn = _texNum
    c = []
    yG, zG = R["yG"], R["zG"]
    for k, p in enumerate(prims):
        sg = "" if p["sign"] > 0 else "-"
        ks = str(k + 1)
        if p["kind"] == "rect":
            dbl = (
                r"\int_{"
                + tn(p["z1"])
                + "}^{"
                + tn(p["z2"])
                + r"}\!\!\int_{"
                + tn(p["y1"])
                + "}^{"
                + tn(p["y2"])
                + "} "
            )
            dS = r"dy\,dz"
            ey = r"\left(y" + _offStr(-yG) + r"\right)"
            ez = r"\left(z" + _offStr(-zG) + r"\right)"
            my = r"y\,"
            mz = r"z\,"
        else:
            dbl = r"\int_{0}^{2\pi}\!\!\int_{" + tn(_innerRadius(p)) + "}^{" + tn(p["R"]) + "} "
            dS = r"r\,dr\,d\theta"
            ey = r"\left(r\sin\theta" + _offStr(p["yc"] - yG) + r"\right)"
            ez = r"\left(r\cos\theta" + _offStr(p["zc"] - zG) + r"\right)"
            my = r"\left(" + tn(p["yc"]) + r" + r\sin\theta\right) "
            mz = r"\left(" + tn(p["zc"]) + r" + r\cos\theta\right) "
        c.append("$S^{(" + ks + ")} = " + sg + dbl + dS + " = " + tn(R["Si"][k]) + r"\ \mathrm{m^2}$")
        c.append("$M_{O_1z}^{(" + ks + ")} = " + sg + dbl + my + dS + " = " + tn(R["MO1zi"][k]) + r"\ \mathrm{m^3}$")
        c.append("$M_{O_1y}^{(" + ks + ")} = " + sg + dbl + mz + dS + " = " + tn(R["MO1yi"][k]) + r"\ \mathrm{m^3}$")
        c.append(
            "$I_{Gz}^{(" + ks + ")} = " + sg + dbl + ey + r"^2\," + dS + " = " + tn(R["Izi"][k]) + r"\ \mathrm{m^4}$"
        )
        c.append(
            "$I_{Gy}^{(" + ks + ")} = " + sg + dbl + ez + r"^2\," + dS + " = " + tn(R["Iyi"][k]) + r"\ \mathrm{m^4}$"
        )
        c.append(
            "$I_{Gyz}^{("
            + ks
            + ")} = "
            + sg
            + dbl
            + ey
            + ez
            + r"\,"
            + dS
            + " = "
            + tn(R["Iyzi"][k])
            + r"\ \mathrm{m^4}$"
        )
        c.append(
            "$I_{x}^{("
            + ks
            + ")} = "
            + sg
            + dbl
            + r"\left["
            + ey
            + "^2 + "
            + ez
            + r"^2\right] "
            + dS
            + " = "
            + tn(R["Ixi"][k])
            + r"\ \mathrm{m^4}$"
        )
    return c


def _shearZ(sec: dict, prims: list[dict], ky: float) -> float:
    """Coefficient kz (effort tranchant Tz) : calcul énergétique de ky sur la section aux axes y et z échangés."""
    if sec["type"] in ("rectangle", "disque", "couronne"):
        return ky  # valeur du cours, indépendante de la direction
    pr = [dict(p, z1=p["y1"], y1=p["z1"], z2=p["y2"], y2=p["z2"], zc=p["yc"], yc=p["zc"]) for p in prims]
    kz = _shearCore({"type": "composite"}, pr, _huygensCore(pr))["kyNum"]
    return kz if math.isfinite(kz) and kz > 0 else ky  # section non connexe selon z : pas de valeur énergétique


def _courseShear(sec: dict, core: dict) -> tuple[float, float, float, str]:
    """Valeurs tabulées du cours pour k et ky : (kCours, kyCours, Sweb, texte) ; NaN si le type n'en a pas."""
    t = sec["type"]
    nan = math.nan
    if t == "rectangle":
        return 3 / 2, 5 / 6, nan, "rectangle : k = 3/2, ky = 5/6"
    if t == "disque":
        return 4 / 3, 6 / 7, nan, "disque : k = 4/3, ky = 6/7"
    if t == "couronne":
        R, r = sec["D"] / 2, sec["d"] / 2
        kC = 4 / 3 * (1 + r * R / (r**2 + R**2))
        if r == 0:
            return kC, 6 / 7, nan, f"couronne avec d = 0 (disque plein) : k = {_num(kC)}, ky = 6/7"
        return kC, 1 / 2, nan, f"tube : k = 4/3·(1 + rR/(r² + R²)) = {_num(kC)}, ky = 1/2 (tube mince)"
    if t == "I" or (t == "profile" and sec["profileShape"] == "I"):
        Sweb = sec["tw"] * (sec["h"] - 2 * sec["tf"])
        kC, kyC = core["S"] / Sweb, Sweb / core["S"]
        if t == "I":
            txt = (
                f"poutre en I : k = S/S_âme = {_num(kC)}, ky = S_âme/S = {_num(kyC)} "
                f"(S_âme = tw·(h − 2tf) = {_num(Sweb)} m²)"
            )
        else:
            txt = (
                f"profilé en I : k = S/S_âme = {_num(kC)}, ky = S_âme/S = {_num(kyC)} "
                f"(S_âme = a·(h − 2e) = {_num(Sweb)} m², S de la géométrie simplifiée)"
            )
        return kC, kyC, Sweb, txt
    if t == "profile":
        return nan, nan, nan, "aucune valeur du cours pour un profilé en U (valeurs numériques retenues)"
    return nan, nan, nan, "aucune valeur du cours pour ce type (valeurs numériques retenues)"


def _shearCore(sec: dict, prims: list[dict], core: dict) -> dict:
    """Facteurs de cisaillement (cours, Jourawski, énergie) : kCours, kyCours, kNum, kyNum, yAtMax, Sweb, connected."""
    S, Iz, yG = core["S"], core["Iz"], core["yG"]
    fs = _num
    kC, kyC, Sweb, courseTxt = _courseShear(sec, core)
    Lref = _refLength(prims)
    tolW = 1e-12 * Lref
    lev = _levels(prims)
    yb = lev - yG
    connected = True
    # étranglement : largeur nulle (d'un côté) à une cote intérieure où Q ≠ 0
    # (parties disjointes ou contact ponctuel, ex. disque posé sur un rectangle)
    bb = _bboxPrims(prims)
    for k in range(len(lev)):
        if bb[2] + tolW < lev[k] < bb[3] - tolW:
            bA = float(_widthCore(prims, yG, yb[k], "above"))
            bB = float(_widthCore(prims, yG, yb[k], "below"))
            if min(bA, bB) <= tolW and abs(float(_firstMomentCore(prims, yG, yb[k]))) > 1e-9 * S * Lref:
                connected = False
    bestR = -math.inf
    yBest = math.nan
    intQ2b = 0.0
    absTol = 1e-15 * Iz**2 / S
    for k in range(len(yb) - 1):
        a, c = yb[k], yb[k + 1]
        if c - a <= tolW:
            continue
        if float(_widthCore(prims, yG, (a + c) / 2, "above")) <= tolW:
            connected = False
            continue
        t = np.linspace(a, c, 201)
        if a < 0 < c:
            t = np.unique(np.append(t, 0.0))
        bt = _widthCore(prims, yG, t, "above")
        bt[-1] = float(_widthCore(prims, yG, c, "below"))
        Qt = _firstMomentCore(prims, yG, t)
        rt = np.zeros(t.shape)
        ok = bt > tolW
        rt[ok] = Qt[ok] / bt[ok]
        im = int(np.argmax(rt))
        rmax = rt[im]
        ym = t[im]
        lo = t[max(im - 1, 0)]
        hi = t[min(im + 1, len(t) - 1)]
        if hi > lo:

            def g(x):
                return -float(_firstMomentCore(prims, yG, x)) / max(float(_widthCore(prims, yG, x, "above")), tolW)

            res = minimize_scalar(g, bounds=(lo, hi), method="bounded", options={"xatol": 1e-12 * Lref})
            if -res.fun > rmax:
                rmax = -res.fun
                ym = res.x
        if rmax > bestR:
            bestR = rmax
            yBest = ym
        intQ2b += quad(lambda x: float(_q2b(prims, yG, x, tolW)), a, c, epsabs=absTol, epsrel=1e-12)[0]
    if connected and math.isfinite(bestR) and intQ2b > 0:
        kNum = S * bestR / Iz
        kyNum = Iz**2 / (S * intQ2b)
        if abs(yBest) <= 1e-9 * Lref:
            yBest = 0.0
    else:
        kNum = kyNum = yBest = math.nan

    f = {
        "kCours": kC,
        "kyCours": kyC,
        "kNum": kNum,
        "kyNum": kyNum,
        "yAtMax": yBest,
        "Sweb": Sweb,
        "connected": connected,
    }
    rep = ["Facteurs de cisaillement (effort tranchant Ty, flexion autour de z)", f"Valeurs du cours : {courseTxt}"]
    if connected:
        rep.append(
            "Jourawski : τ(y) = T·Q(y)/(Iz·b(y)) ; maximum de Q/b en y = "
            f"{fs(yBest)} m (depuis G) : kNum = S·Q/(Iz·b) = {fs(kNum)}"
        )
        rep.append(
            "Énergie : 1/(ky·S) = ∫ Q(y)²/(Iz²·b(y)) dy ⇒ kyNum = Iz²/(S·∫ Q²/b dy) "
            f"= {fs(kyNum)} (∫ Q²/b dy = {fs(intQ2b)} m⁶)"
        )
    else:
        rep.append(
            "Section non connexe ou à contact ponctuel selon y (b(y) nulle entre deux parties alors que Q ≠ 0) : "
            "Jourawski non applicable, kNum = kyNum = NaN."
        )
    if sec["type"] == "disque":
        rep.append(
            f"Disque : l'intégration exacte donne kyNum = 9/10 = {fs(kyNum)} (1/ky = 10/9) ; valeur du cours 6/7 = "
            f"{fs(6 / 7)} (écart {100 * (kyNum - 6 / 7) / (6 / 7):.2f} %) : 6/7 résulte de la théorie de l'élasticité "
            "(Cowper, ν = 0), alors que la répartition de Jourawski ne retient que τxy moyen sur la largeur "
            "et néglige τxz."
        )
    elif sec["type"] == "rectangle":
        rep.append("Rectangle : kNum = 3/2 et kyNum = 5/6 exactement (valeurs du cours).")
    elif sec["type"] == "couronne":
        rep.append(
            "Couronne : kNum coïncide exactement avec 4/3·(1 + rR/(r² + R²)) ; "
            f"kyNum = {fs(kyNum)} tend vers 2/3 pour un tube mince : la formule énergétique ne retient que τxy moyen "
            "sur la largeur horizontale b(y), alors que la valeur 1/2 du cours suppose un flux de cisaillement tangent "
            "à la paroi (τxz pris en compte en haut et en bas)."
        )
    elif sec["type"] in ("I", "profile") and not math.isnan(kC):
        rep.append(
            "Profil en I : la formule du cours (S/S_âme) suppose τ uniforme dans l'âme ; Jourawski donne τmax en G : "
            f"écart kNum/kCours = {100 * (kNum - kC) / kC:+.2f} %."
        )
    tex = [
        r"$k = \frac{\tau_{max}\,S}{T} = \frac{S\,Q(y)}{I_{Gz}\,b(y)} = " + _texNum(kNum) + "$",
        r"$k_y = \frac{I_{Gz}^2}{S \int Q(y)^2/b(y)\,dy} = " + _texNum(kyNum) + "$",
    ]
    if not math.isnan(kC):
        tex.append(r"$k_{cours} = " + _texNum(kC) + r",\ k_{y,cours} = " + _texNum(kyC) + "$")
    f["report"] = rep
    f["latex"] = tex
    return f
