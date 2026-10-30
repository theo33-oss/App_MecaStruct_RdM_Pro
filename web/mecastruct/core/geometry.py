"""Propriétés des sections droites : port de GeometryEngine.m, première moitié (étape E06).

Repère O1 : z horizontal vers la droite, y vertical vers le haut, origine au coin bas-gauche de la section.
Les fonctions qui reçoivent une cote y la mesurent depuis le centre de gravité G (ARCHITECTURE §2).
Les aires sont en m², les moments statiques en m³, les moments quadratiques en m⁴.
"""

import copy
import math
import re

import numpy as np
import pandas as pd
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
