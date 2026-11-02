"""Engrenages droits à denture cylindrique : géométrie, rapport, couple et puissance, efforts, résistance de la dent.

Formules du cours « Les engrenages » (IUT de Bordeaux) : d = m·Z, p = π·m, a = m·(Z1 + Z2)/2, hauteur de dent 2,25·m,
largeur b = k·m (k entre 6 et 10). Efforts : Ft = 2C/d, Fr = Ft·tan α, Fn = Ft/cos α. Dent modélisée par une poutre
encastrée de section (π·m/2)·b, moment maxi Ft·2,25·m : σ = 54·Ft/(π²·k·m²) (≈ 5,47·Ft/(k·m²)) ≤ Rpe = Re/s, donc
m ≥ √(54·Ft/(π²·k·Rpe)) (≈ 2,34·√(Ft/(k·Rpe))).
"""

import math

from mecastruct.core.errors import MecaStructError

_ID = "MecaStruct:Gears:invalidInput"
MODULES = (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 32, 40, 50)  # série principale ISO 54 (mm)
ALPHA = 20.0  # angle de pression normalisé (°)


def geometry(m: float, Z: int, alpha: float = ALPHA) -> dict:
    """Géométrie d'une roue à denture droite standard : d, db (diamètres primitif et de base, mm), p (pas, mm),
    ha (saillie, mm), hf (creux, mm) et h = ha + hf (hauteur de dent, mm).

    Entrées : m (module, mm), Z (nombre de dents), alpha (angle de pression, °).
    """
    if m <= 0 or Z < 1:
        raise MecaStructError(_ID, "Module et nombre de dents strictement positifs.")
    d = m * Z
    return {
        "d": d,
        "db": d * math.cos(math.radians(alpha)),
        "p": math.pi * m,
        "ha": m,
        "hf": 1.25 * m,
        "h": 2.25 * m,
    }


def centerDistance(m: float, Z1: int, Z2: int) -> float:
    """Entraxe (mm) d'un engrènement extérieur sans déport : a = m·(Z1 + Z2)/2."""
    return m * (Z1 + Z2) / 2


def ratio(Z1: int, Z2: int) -> float:
    """Rapport de transmission ω_menée / ω_menante d'un engrènement extérieur : −Z1/Z2 (signe : sens inversé)."""
    return -Z1 / Z2


def toothForces(C: float, d: float, alpha: float = ALPHA) -> dict:
    """Efforts de la denture (N) : Ft tangentiel, Fr radial, Fn normal, pour un couple C (N·m) au diamètre d (mm)."""
    if d <= 0:
        raise MecaStructError(_ID, "Le diamètre primitif doit être strictement positif.")
    a = math.radians(alpha)
    Ft = 2000 * abs(C) / d
    return {"Ft": Ft, "Fr": Ft * math.tan(a), "Fn": Ft / math.cos(a)}


def rootStress(Ft: float, m: float, k: float) -> float:
    """Contrainte maxi en pied de dent (MPa) : 54·Ft/(π²·k·m²), Ft en N, m en mm, k = b/m sans dimension."""
    return 54 * Ft / (math.pi**2 * k * m**2)


def moduleMini(Ft: float, k: float, Rpe: float) -> float:
    """Module minimal (mm) pour une résistance pratique Rpe (MPa) : √(54·Ft/(π²·k·Rpe)), Ft en N."""
    if k <= 0 or Rpe <= 0:
        raise MecaStructError(_ID, "Le coefficient k et la résistance Rpe doivent être strictement positifs.")
    return math.sqrt(54 * Ft / (math.pi**2 * k * Rpe))


def normalizedModule(mMini: float) -> float:
    """Premier module normalisé (série ISO 54) supérieur ou égal à `mMini` (mm). Erreur au-delà de 50 mm."""
    for m in MODULES:
        if m >= mMini:
            return m
    raise MecaStructError(_ID, f"Aucun module normalisé ≥ {mMini:.3g} mm dans la série (jusqu'à 50 mm).")


def gearTrain(Z: list[tuple[int, int]], P: float, N: float, eta: float) -> list[dict]:
    """Train d'engrenages en série : puissance, fréquence de rotation et couple de chaque arbre.

    Entrées : Z = [(Z menant, Z mené), ...] pour chaque engrènement, P (W) et N (tr/min) à l'entrée, eta rendement
    d'un engrènement. Sorties : une ligne par arbre (arbre, N tr/min signé, P W, C N·m) : N = N·Π(−Z menant/Z mené),
    P = P·eta^k, C = P/ω. Un nombre impair d'engrènements inverse le sens de rotation.
    """
    if not Z or N == 0:
        raise MecaStructError(_ID, "Il faut au moins un engrènement et une fréquence de rotation non nulle.")
    lignes = [{"arbre": "Entrée", "N": N, "P": P}]
    for i, (zm, zc) in enumerate(Z, start=1):
        amont = lignes[-1]
        lignes.append({"arbre": f"Arbre {i}", "N": amont["N"] * ratio(zm, zc), "P": amont["P"] * eta})
    for ligne in lignes:
        ligne["C"] = 30 * ligne["P"] / (math.pi * abs(ligne["N"]))  # N·m, avec P en W et N en tr/min
    return lignes
