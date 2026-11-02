"""Trains épicycloïdaux plans à trois éléments (planétaire, couronne, porte-satellites) : formule de Willis.

Cours « Trains épicycloïdaux » (IUT de Bordeaux, ICM S4). Raison basique rb, porte-satellites bloqué :
rb = (ω_couronne − ω_PS) / (ω_planétaire − ω_PS) = (−1)^p · Z1·Z22 / (Z21·Z4), avec Z1 le planétaire, Z21 le satellite
engrenant le planétaire, Z22 le satellite engrenant la couronne Z4, p le nombre d'engrènements extérieurs (1 ici).
Quelle que soit la configuration : ω_couronne − ω_PS = rb·(ω_planétaire − ω_PS).
Conditions de montage : Z4 = Z1 + Z21 + Z22 (entraxes) et (Z1 + Z4)/n_sat entier (« règle du haricot »).
"""

from mecastruct.core.errors import MecaStructError

_ID = "MecaStruct:Planetary:invalidInput"
ELEMENTS = ("planétaire", "couronne", "porte-satellites")


def basicRatio(Z1: int, Z21: int, Z22: int, Z4: int, p: int = 1) -> float:
    """Raison basique rb (sans dimension) : (−1)^p · Z1·Z22 / (Z21·Z4). Satellite simple : Z21 = Z22."""
    if min(Z1, Z21, Z22, Z4) < 1:
        raise MecaStructError(_ID, "Les nombres de dents doivent être strictement positifs.")
    return (-1) ** p * Z1 * Z22 / (Z21 * Z4)


def speeds(rb: float, bloque: str, entree: str, valeur: float) -> dict[str, float]:
    """Vitesses (même unité que `valeur`) des trois éléments, pour un élément bloqué et une vitesse d'entrée connue.

    Entrées : rb (raison basique), bloque et entree (noms dans ELEMENTS, différents), valeur (vitesse de l'entrée).
    Sortie : dict {élément: vitesse}, l'élément restant (la sortie) étant calculé par la relation de Willis.
    """
    if bloque not in ELEMENTS or entree not in ELEMENTS or bloque == entree:
        raise MecaStructError(_ID, "Élément bloqué et élément d'entrée : deux éléments différents parmi trois.")
    sortie = next(e for e in ELEMENTS if e not in (bloque, entree))
    vitesses = {bloque: 0.0, entree: valeur, sortie: 0.0}

    def ecart(v: dict[str, float]) -> float:
        return (v["couronne"] - v["porte-satellites"]) - rb * (v["planétaire"] - v["porte-satellites"])

    f0 = ecart(vitesses)  # f est linéaire en la vitesse inconnue : une évaluation à 0 et une à 1 suffisent
    vitesses[sortie] = 1.0
    pente = ecart(vitesses) - f0
    if abs(pente) < 1e-12:
        raise MecaStructError(_ID, "Pas de vitesse de sortie unique : rb = 1 (train sans raison de réduction).")
    vitesses[sortie] = -f0 / pente
    return vitesses


def assemblyChecks(Z1: int, Z21: int, Z22: int, Z4: int, nSat: int) -> list[tuple[str, float, bool]]:
    """Conditions de montage : (nom, valeur, ok). Entraxes : Z4 − (Z1 + Z21 + Z22) = 0 ; haricot : (Z1 + Z4)/nSat entier."""
    if nSat < 1:
        raise MecaStructError(_ID, "Il faut au moins un satellite.")
    ecart = Z4 - (Z1 + Z21 + Z22)
    haricot = (Z1 + Z4) / nSat
    return [
        ("Entraxes : Z4 − (Z1 + Z21 + Z22)", ecart, ecart == 0),
        ("Règle du haricot : (Z1 + Z4) / n_sat", haricot, abs(haricot - round(haricot)) < 1e-9),
    ]
