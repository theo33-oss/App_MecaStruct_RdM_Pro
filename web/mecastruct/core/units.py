"""Conversions d'unités vers le SI : ports de DataManager.toSI, fromSI, unitFactor et de App.convertUnits."""

import math

import numpy as np

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import load_json

# Facteurs vers le SI, code d'unité normalisé → facteur (port de DataManager.buildUnitMap)
_UNIT_MAP: dict[str, float] = {
    "m": 1,
    "cm": 1e-2,
    "mm": 1e-3,
    "µm": 1e-6,
    "um": 1e-6,
    "km": 1e3,
    "m^2": 1,
    "cm^2": 1e-4,
    "mm^2": 1e-6,
    "m^3": 1,
    "cm^3": 1e-6,
    "mm^3": 1e-9,
    "m^4": 1,
    "cm^4": 1e-8,
    "mm^4": 1e-12,
    "N": 1,
    "kN": 1e3,
    "MN": 1e6,
    "daN": 10,
    "N.m": 1,
    "kN.m": 1e3,
    "N.mm": 1e-3,
    "daN.m": 10,
    "MN.m": 1e6,
    "kN.mm": 1,
    "Nm": 1,
    "kNm": 1e3,
    "Nmm": 1e-3,
    "daNm": 10,
    "N/m": 1,
    "kN/m": 1e3,
    "N/mm": 1e3,
    "daN/m": 10,
    "MN/m": 1e6,
    "Pa": 1,
    "kPa": 1e3,
    "MPa": 1e6,
    "GPa": 1e9,
    "N/m^2": 1,
    "N/mm^2": 1e6,
    "bar": 1e5,
    "rad": 1,
    "mrad": 1e-3,
    "deg": math.pi / 180,
    "°": math.pi / 180,
    "rad/m": 1,
    "mrad/m": 1e-3,
    "deg/m": math.pi / 180,
    "°/m": math.pi / 180,
    "1/°C": 1,
    "1e-6/°C": 1e-6,
    "/°C": 1,
    "1/K": 1,
    "1e-6/K": 1e-6,
    "1/C": 1,
    "1e-6/C": 1e-6,
    "°C": 1,
    "K": 1,
    "kg/m^3": 1,
    "g/cm^3": 1e3,
    "kg/m": 1,
    "-": 1,
    "%": 1e-2,
    "µdef": 1e-6,
    "µdéf": 1e-6,
    "udef": 1e-6,
    "mm/m": 1e-3,
    "W": 1,
    "kW": 1e3,
    "tr/min": 2 * math.pi / 60,
    "rad/s": 1,
    "J": 1,
    "kJ": 1e3,
    # unités anglo-saxonnes et anciennes (convertisseur)
    "in": 0.0254,
    "ft": 0.3048,
    "in^2": 0.0254**2,
    "ft^2": 0.3048**2,
    "in^4": 0.0254**4,
    "ft^4": 0.3048**4,
    "lbf": 4.4482216152605,
    "kip": 4448.2216152605,
    "kgf": 9.80665,
    "tf": 9806.65,
    "lbf.in": 4.4482216152605 * 0.0254,
    "lbf.ft": 4.4482216152605 * 0.3048,
    "kip.in": 4448.2216152605 * 0.0254,
    "kip.ft": 4448.2216152605 * 0.3048,
    "kgf.m": 9.80665,
    "kgf.cm": 9.80665e-2,
    "lbf/in": 4.4482216152605 / 0.0254,
    "lbf/ft": 4.4482216152605 / 0.3048,
    "kip/ft": 4448.2216152605 / 0.3048,
    "kgf/m": 9.80665,
    "psi": 6894.757293168,
    "ksi": 6894757.293168,
    "kgf/cm^2": 98066.5,
    "kgf/mm^2": 9806650,
    "Mpsi": 6894757293.168,
    "lb/ft^3": 16.01846337,
    "lb/in^3": 27679.9047,
    "°F": 5 / 9,
    "1/°F": 9 / 5,
    "1e-6/°F": 1.8e-6,
    "turn": 2 * math.pi,
    "arcmin": math.pi / 10800,
    "arcsec": math.pi / 648000,
}

# Symboles remplacés avant la recherche (port de DataManager.normalizeUnit)
_SYMBOLES = {
    " ": "",
    " ": "",
    "·": ".",
    "⋅": ".",
    "×": ".",
    "*": ".",
    "²": "^2",
    "³": "^3",
    "⁴": "^4",
    "μ": "µ",
    "º": "°",
    "−": "-",
}


def _normalizeUnit(unit: str) -> str:
    """Normalise une chaîne d'unité : sans espaces, symboles de produit et exposants en ASCII.

    Entrée : `unit` (texte, ex. « kN · m² »).
    Sortie : texte normalisé (« - » si vide).
    """
    u = unit.strip()
    for source, cible in _SYMBOLES.items():
        u = u.replace(source, cible)
    return u or "-"


def _asNumeric(val) -> np.ndarray:
    """Convertit une valeur en tableau de réels ; texte, None ou valeur non convertible → MecaStructError."""
    try:
        if val is None or isinstance(val, str):
            raise TypeError(val)
        return np.asarray(val, dtype=float)
    except (TypeError, ValueError) as err:
        raise MecaStructError(
            "MecaStruct:DataManager:invalidValue", "La valeur à convertir doit être numérique."
        ) from err


def _unwrap(v: np.ndarray):
    """Renvoie un float pour un scalaire, sinon le tableau."""
    return float(v) if v.ndim == 0 else v


def unitFactor(unit: str) -> float:
    """Facteur multiplicatif vers le SI (valeur_SI = valeur · facteur).

    Entrée : `unit` (code d'unité, ex. « kN.m », « MPa », « in »).
    Sortie : float. Unité inconnue → MecaStructError « MecaStruct:DataManager:unknownUnit ».
    """
    if not isinstance(unit, str):
        raise MecaStructError("MecaStruct:DataManager:unknownUnit", "L'unité doit être un texte.")
    u = _normalizeUnit(unit)
    if u in _UNIT_MAP:
        return _UNIT_MAP[u]
    # sans tenir compte de la casse, seulement si la correspondance est unique (comme strcmpi),
    # mais jamais en confondant les préfixes m (milli) et M (méga) : « mN » n'est pas « MN »
    hits = [k for k in _UNIT_MAP if k.lower() == u.lower() and not (k[0] in "mM" and k[0] != u[0])]
    if len(hits) == 1:
        return _UNIT_MAP[hits[0]]
    raise MecaStructError("MecaStruct:DataManager:unknownUnit", f"Unité inconnue : « {unit} ».")


def toSI(val, unit: str):
    """Convertit une valeur de l'unité `unit` vers le SI.

    Entrées : `val` (nombre, liste ou tableau, en `unit`), `unit` (code d'unité).
    Sortie : float pour un scalaire, np.ndarray sinon, en unités SI.
    """
    return _unwrap(_asNumeric(val) * unitFactor(unit))


def fromSI(val, unit: str):
    """Convertit une valeur SI vers l'unité `unit`.

    Entrées : `val` (nombre, liste ou tableau, en SI), `unit` (code d'unité).
    Sortie : float pour un scalaire, np.ndarray sinon, dans `unit`.
    """
    return _unwrap(_asNumeric(val) / unitFactor(unit))


def unitCatalog() -> list[dict]:
    """Grandeurs et unités du convertisseur, lues dans `units.json`.

    Sortie : liste de {name, units: [{label, code}…], defFrom, defTo} (indices à partir de 1, comme MATLAB).
    """
    return load_json("units.json")["catalog"]


def convertUnits(val, quantity: str, frm: str, to: str):
    """Convertit une valeur entre deux unités d'une même grandeur du convertisseur.

    Entrées : `val` (nombre ou tableau, dans `frm`), `quantity` (nom de grandeur, ex. « Longueur »),
    `frm` et `to` (libellés d'unité, ex. « in » et « mm »).
    Sortie : float pour un scalaire, np.ndarray sinon, dans l'unité `to`.
    """
    grandeurs = [g for g in unitCatalog() if g["name"] == quantity]
    if not grandeurs:
        raise MecaStructError("MecaStruct:App:unknownQuantity", f"Grandeur inconnue : « {quantity} ».")
    unites = grandeurs[0]["units"]
    libelles = [u["label"] for u in unites]
    if frm not in libelles or to not in libelles:
        raise MecaStructError(
            "MecaStruct:App:unknownUnit", f"Unité inconnue pour « {quantity} » : « {frm} » ou « {to} »."
        )
    code_from = unites[libelles.index(frm)]["code"]
    code_to = unites[libelles.index(to)]["code"]
    v = _asNumeric(val)
    if quantity == "Température absolue":
        # passage par le kelvin (décalage d'origine)
        if code_from == "K":
            kelvin = v
        elif code_from == "C":
            kelvin = v + 273.15
        else:
            kelvin = (v + 459.67) * 5 / 9
        if code_to == "K":
            return _unwrap(kelvin)
        if code_to == "C":
            return _unwrap(kelvin - 273.15)
        return _unwrap(kelvin * 9 / 5 - 459.67)
    return _unwrap(v * unitFactor(code_from) / unitFactor(code_to))
