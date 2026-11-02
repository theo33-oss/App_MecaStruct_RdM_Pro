"""Roulements à éléments roulants : durée de vie L10, charge dynamique équivalente P, ensembles et règles de montage.

Formules du cours « Calcul sur les roulements » (IUT de Bordeaux) : L10 = (C/P)^n, L10h, coefficient de fiabilité a1,
durée d'un ensemble iso-fiable (exposant 1,5) ; coefficients e et Y interpolés dans web/data/bearing_xy.json
(roulements à billes à contact radial). Règles de montage d'après « Liaison pivot par roulements » (même cours).
"""

import math

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import load_json

_ID = "MecaStruct:Bearing:invalidInput"
EXPOSANT = {"billes": 3.0, "rouleaux": 10 / 3}  # n de L10 = (C/P)^n

# (bague, rotation par rapport à la charge, charge) -> (portée, ajustement conseillé), tableau du cours
AJUSTEMENTS = [
    (("intérieure", "fixe", "constante"), ("arbre", "g6")),
    (("intérieure", "fixe", "variable"), ("arbre", "h6")),
    (("intérieure", "tournante", "faible"), ("arbre", "h5 à j6")),
    (("intérieure", "tournante", "variable"), ("arbre", "h5 à j6")),
    (("intérieure", "tournante", "normale"), ("arbre", "k5 à k6")),
    (("intérieure", "tournante", "importante"), ("arbre", "m5 à m6")),
    (("intérieure", "tournante", "importante avec chocs"), ("arbre", "n6 à p6")),
    (("extérieure", "tournante", "faible"), ("alésage", "M7")),
    (("extérieure", "tournante", "variable"), ("alésage", "M7")),
    (("extérieure", "tournante", "normale"), ("alésage", "N7")),
    (("extérieure", "tournante", "importante"), ("alésage", "N7")),
    (("extérieure", "tournante", "importante avec chocs"), ("alésage", "P7")),
    (("extérieure", "fixe", "importante avec chocs"), ("alésage", "J7")),
    (("extérieure", "fixe", "normale"), ("alésage", "H7")),
    (("extérieure", "fixe", "normale mécanique ordinaire"), ("alésage", "H8")),
    (("extérieure", "indéfinie", "importante"), ("alésage", "K7")),
    (("extérieure", "indéfinie", "normale"), ("alésage", "K7")),
]


def xyTable() -> dict:
    """Table du cours des roulements à billes à contact radial : Fa/C0, e, Y et X (web/data/bearing_xy.json)."""
    return load_json("bearing_xy.json")


def eYInterpolated(faC0: float) -> tuple[float, float]:
    """Coefficients (e, Y) interpolés linéairement dans la table, pour rapport Fa/C0 (sans dimension).

    Erreur hors de la plage du tableau : on ne prolonge pas la courbe, il faut alors saisir e et Y du constructeur.
    """
    t = xyTable()
    x = t["FaC0"]
    if not x[0] <= faC0 <= x[-1]:
        raise MecaStructError(
            _ID, f"Fa/C0 = {faC0:g} hors du tableau ({x[0]:g} à {x[-1]:g}) : saisir e et Y du constructeur."
        )
    i = next(k for k in range(len(x) - 1) if faC0 <= x[k + 1])
    u = (faC0 - x[i]) / (x[i + 1] - x[i])
    e = t["e"][i] + u * (t["e"][i + 1] - t["e"][i])
    Y = t["Y"][i] + u * (t["Y"][i + 1] - t["Y"][i])
    return e, Y


def dynamicLoad(Fr: float, Fa: float, e: float, X: float, Y: float) -> float:
    """Charge dynamique équivalente P (N) : Fr si Fa/Fr ≤ e, sinon X·Fr + Y·Fa ; Fa seule pour une butée (Fr = 0).

    Entrées : Fr, Fa (N, positifs), e, X, Y (sans dimension, constructeur).
    """
    if Fr < 0 or Fa < 0:
        raise MecaStructError(_ID, "Les charges Fr et Fa sont des intensités positives (leur sens n'entre pas ici).")
    if Fr == 0:
        return Fa
    return Fr if Fa / Fr <= e else X * Fr + Y * Fa


def lifeMTours(C: float, P: float, n: float) -> float:
    """Durée de vie L10 en millions de tours : (C/P)^n ; C charge dynamique de base (N), P charge équivalente (N)."""
    if C <= 0 or P <= 0:
        raise MecaStructError(_ID, "La charge de base C et la charge équivalente P doivent être strictement positives.")
    return (C / P) ** n


def lifeHours(L10: float, N: float) -> float:
    """Durée de vie L10h en heures, pour L10 en millions de tours et N en tr/min : 10⁶·L10 / (60·N)."""
    if N <= 0:
        raise MecaStructError(_ID, "La fréquence de rotation N doit être strictement positive.")
    return 1e6 * L10 / (60 * N)


def reliabilityFactor(F: float) -> float:
    """Coefficient a1 pour une fiabilité F (0 < F < 1) : (ln(1/F) / ln(1/0,9))^(1/1,5). Vaut 1 à 90 %, 0,53 à 96 %."""
    if not 0 < F < 1:
        raise MecaStructError(_ID, f"Fiabilité F = {F:g} hors de l'intervalle ouvert 0 à 1.")
    return (math.log(1 / F) / math.log(1 / 0.9)) ** (1 / 1.5)


def dynamicRating(P: float, L10req: float, n: float) -> float:
    """Charge dynamique de base minimale C (N) pour une durée L10 requise (millions de tours) : P·L10^(1/n)."""
    return P * L10req ** (1 / n)


def lifeSet(lives: list[float]) -> float:
    """Durée d'un ensemble de roulements en série de même unité que `lives` : (Σ Lj^(−1,5))^(−1/1,5)."""
    if not lives or any(x <= 0 for x in lives):
        raise MecaStructError(_ID, "Il faut au moins une durée, toutes strictement positives.")
    return sum(x**-1.5 for x in lives) ** (-1 / 1.5)


def isoReliableLife(setLife: float, count: int) -> float:
    """Durée de chacun des `count` roulements iso-fiables donnant la durée `setLife` : setLife·count^(2/3)."""
    if count < 1:
        raise MecaStructError(_ID, "Il faut au moins un roulement.")
    return setLife * count ** (2 / 3)


def mountingRule(bague: str, rotation: str) -> str:
    """Montage conseillé : « serrée » si la bague tourne par rapport à la charge, « glissante » si elle est fixe.

    Entrées : bague (« intérieure » ou « extérieure »), rotation (« tournante », « fixe »).
    """
    if rotation not in ("tournante", "fixe"):
        raise MecaStructError(_ID, f"Rotation inconnue : {rotation!r} (« tournante » ou « fixe »).")
    return "serrée" if rotation == "tournante" else "glissante"


def fitRule(bague: str, rotation: str, charge: str) -> tuple[str, str]:
    """Portée et ajustement conseillés (tableau du cours) : ("arbre" | "alésage", « g6 », « N7 », ...).

    Entrées : bague (« intérieure » ou « extérieure »), rotation (« tournante », « fixe » ou « indéfinie » pour
    l'extérieure), charge (« constante », « variable », « faible », « normale », « importante »,
    « importante avec chocs » ou « normale mécanique ordinaire »). Erreur si la combinaison n'est pas au tableau.
    """
    for cle, valeur in AJUSTEMENTS:
        if cle == (bague, rotation, charge):
            return valeur
    raise MecaStructError(_ID, f"Pas d'ajustement au tableau pour {bague}, {rotation}, charge {charge!r}.")
