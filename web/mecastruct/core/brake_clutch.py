"""Freins à disque et embrayages : couple de freinage, pression et puissance spécifique, synchronisation.

Cours « Frein – Embrayage » (IUT de Bordeaux, ICM S5). Pour un effort presseur F (N) par surface, n surfaces frottantes,
coefficient f, rayons Ri et Re (mm) :
- pression de contact constante : Cf = n·f·F·(2/3)·(Re³ − Ri³)/(Re² − Ri²) ;
- usure constante (pression en 1/rayon) : Cf = n·f·F·(Re + Ri)/2.
Embrayage, avec J_M·ω̇_M = C_M − C_T et J_R·ω̇_R = C_R + C_T (C_R < 0 en général) : pendant la synchronisation le
moteur est supposé à vitesse constante, donc le récepteur accélère avec le couple C_T + C_R.
"""

import math

from mecastruct.core.errors import MecaStructError

_ID = "MecaStruct:BrakeClutch:invalidInput"


def _rayons(Ri: float, Re: float) -> None:
    if not 0 <= Ri < Re:
        raise MecaStructError(_ID, f"Rayons incohérents : Ri = {Ri:g} mm, Re = {Re:g} mm (il faut 0 ≤ Ri < Re).")


def brakeTorque(F: float, f: float, n: int, Re: float, Ri: float, loi: str = "pression") -> float:
    """Couple de freinage Cf (N·m) : F (N) par surface, f, n surfaces, Re et Ri (mm).

    `loi` : « pression » (pression de contact constante) ou « usure » (usure constante, pression en 1/rayon).
    """
    _rayons(Ri, Re)
    if loi == "pression":
        cf = n * f * F * (2 / 3) * (Re**3 - Ri**3) / (Re**2 - Ri**2)
    elif loi == "usure":
        cf = n * f * F * (Re + Ri) / 2
    else:
        raise MecaStructError(_ID, f"Loi d'usure inconnue : {loi!r} (« pression » ou « usure »).")
    return cf / 1000  # N·mm -> N·m


def maxPressure(F: float, Re: float, Ri: float, loi: str = "pression") -> float:
    """Pression de contact maxi (MPa) sur une surface : F/(π·(Re² − Ri²)), ou F/(2π·Ri·(Re − Ri)) à usure constante."""
    _rayons(Ri, Re)
    if loi == "pression":
        return F / (math.pi * (Re**2 - Ri**2))
    if loi == "usure":
        if Ri == 0:
            raise MecaStructError(_ID, "Usure constante : la pression tend vers l'infini au centre (Ri = 0).")
        return F / (2 * math.pi * Ri * (Re - Ri))
    raise MecaStructError(_ID, f"Loi d'usure inconnue : {loi!r} (« pression » ou « usure »).")


def specificPower(Cf: float, omega: float, n: int, Re: float, Ri: float) -> float:
    """Puissance spécifique moyenne (W/mm²) : Cf·ω / (n·π·(Re² − Ri²)), Cf en N·m, ω en rad/s, rayons en mm."""
    _rayons(Ri, Re)
    return abs(Cf) * omega / (n * math.pi * (Re**2 - Ri**2))


def clutchTorqueFor(JR: float, omegaM: float, CR: float, tsync: float) -> float:
    """Couple d'embrayage CT (N·m) pour synchroniser le récepteur en `tsync` s : |CR| + JR·ωM / tsync.

    Entrées : JR (kg·m²), omegaM (rad/s, vitesse du moteur pendant la synchronisation), CR (N·m, couple résistant).
    """
    if tsync <= 0:
        raise MecaStructError(_ID, "La durée de synchronisation doit être strictement positive.")
    return abs(CR) + JR * omegaM / tsync


def syncTime(JR: float, omegaM: float, CT: float, CR: float) -> float:
    """Durée de synchronisation (s) avec le couple CT : JR·ωM / (CT − |CR|). Erreur si CT ≤ |CR| (pas de synchronisation)."""
    if CT <= abs(CR):
        raise MecaStructError(_ID, f"Couple d'embrayage {CT:g} N·m insuffisant contre le couple résistant {abs(CR):g} N·m.")
    return JR * omegaM / (CT - abs(CR))


def slipEnergy(CT: float, omegaM: float, tsync: float) -> float:
    """Énergie dissipée par glissement (J) pendant une synchronisation à couple CT constant : CT·ωM·t / 2."""
    return CT * omegaM * tsync / 2
