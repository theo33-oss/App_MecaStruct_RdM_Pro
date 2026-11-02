"""Dimensionnement d'une motorisation : couple équivalent thermique, vérification du moteur, inertie ramenée.

Cours « Description et étude des chaînes de transmission de puissance » (IUT de Bordeaux). Couple quadratique moyen
(couple équivalent thermique) sur les phases du cycle : C_th = √(Σ Ci²·ti / Σ ti). Le moteur doit avoir un couple
nominal ≥ C_th, un couple maxi ≥ couple de pointe et une vitesse maxi ≥ vitesse requise. Inertie ramenée à l'arbre
moteur : J = Jm + Σ Ji / ri², avec ri le rapport de réduction entre l'arbre moteur et l'arbre i.
"""

import math

from mecastruct.core.errors import MecaStructError

_ID = "MecaStruct:Transmission:invalidInput"


def thermalTorque(phases: list[tuple[float, float]]) -> float:
    """Couple équivalent thermique (N·m) : √(Σ C²·t / Σ t), phases = [(C N·m, t s), ...], durées positives."""
    if not phases or any(t < 0 for _, t in phases) or sum(t for _, t in phases) <= 0:
        raise MecaStructError(_ID, "Il faut des phases de durée positive (total strictement positif).")
    total = sum(t for _, t in phases)
    return math.sqrt(sum(C**2 * t for C, t in phases) / total)


def motorChecks(Cth: float, Cpointe: float, Nreq: float, moteur: dict) -> list[tuple[str, float, float, bool]]:
    """Vérifications du moteur : (nom, valeur calculée, limite moteur, ok) pour le couple nominal, le couple maxi et
    la vitesse maxi.

    Entrées : Cth et Cpointe (N·m), Nreq (tr/min), moteur = {« Cn » (N·m), « Cmax » (N·m), « Nmax » (tr/min)}.
    """
    return [
        ("Couple nominal ≥ couple équivalent thermique (N·m)", Cth, moteur["Cn"], moteur["Cn"] >= Cth),
        ("Couple maxi ≥ couple de pointe (N·m)", Cpointe, moteur["Cmax"], moteur["Cmax"] >= Cpointe),
        ("Vitesse maxi ≥ vitesse requise (tr/min)", Nreq, moteur["Nmax"], moteur["Nmax"] >= Nreq),
    ]


def reducedInertia(Jm: float, sorties: list[tuple[float, float]]) -> float:
    """Inertie ramenée à l'arbre moteur (kg·m²) : Jm + Σ J/r², sorties = [(J kg·m², rapport r), ...]."""
    if any(r == 0 for _, r in sorties):
        raise MecaStructError(_ID, "Un rapport de réduction ne peut pas être nul.")
    return Jm + sum(J / r**2 for J, r in sorties)
