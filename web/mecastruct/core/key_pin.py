"""Clavette parallèle normalisée et goupille transmettant un couple (compléments des volets de Sollicitations).

Port des classeurs « calculs_clavetage.xlsm » (clavette : formes A, B, C, matage arbre et moyeu séparés) et
« GOUPILLES_MECANINDUS.xlsm » (goupilles transversale et longitudinale, goupille élastique creuse), sans le
catalogue du fabricant. Les pressions admissibles sont celles déjà choisies dans le volet (table de matage).
"""

import math

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import load_json

_ID = "MecaStruct:KeyPin:invalidInput"
FORMES = {"A": 1.0, "B": 0.0, "C": 0.5}  # longueur portante = L − k·b


def keyDimensions(d: float) -> dict:
    """Clavette parallèle normalisée pour un arbre de diamètre d (mm) : b, h, t1, t2 (mm) et plage."""
    for li in load_json("keys_iso773.json")["Lignes"]:
        if li["dMin"] < d <= li["dMax"]:
            return li
    raise MecaStructError(_ID, f"Pas de clavette normalisée pour d = {d:g} mm (tableau de 6 à 230 mm).")


def keyStandard(p: dict) -> dict:
    """Clavette parallèle normalisée : matage arbre et moyeu, cisaillement, torsion de l'arbre.

    Entrées (dict) : C (N·m), d (mm, arbre), L (mm, longueur totale de la clavette ; 0 = dimensionner : L prend la
    longueur minimale imposée par le matage et le cisaillement), forme (« A », « B », « C »), Padm (MPa), tauAdm (MPa,
    cisaillement admissible de la clavette et de l'arbre).
    Sortie : dict dims (b, h, t1, t2), L (mm, longueur totale retenue), dimensionne (bool), Lp (mm, longueur
    portante), pArbre, pMoyeu, tau, tauArbre (MPa), checks (liste de (nom, valeur, limite, ok)), LminMatage, LminCis
    (mm, longueur portante minimale), report, latex.
    """
    d, L = float(p["d"]), float(p["L"])
    forme = p.get("forme", "A")
    if forme not in FORMES:
        raise MecaStructError(_ID, f"Forme de clavette inconnue : {forme!r} (A, B ou C).")
    Padm, tauAdm = float(p["Padm"]), float(p["tauAdm"])
    if Padm <= 0 or tauAdm <= 0:
        raise MecaStructError(_ID, f"Padm et τadm doivent être positifs (Padm = {Padm:g}, τadm = {tauAdm:g} MPa).")
    k = keyDimensions(d)
    b, h, t1 = k["b"], k["h"], k["t1"]
    C = abs(float(p["C"])) * 1e3  # N·mm
    Farbre = 2 * C / (d - t1)  # effort au rayon moyen de la partie dans l'arbre
    Fmoyeu = 2 * C / (d - t1 + h)
    LminMatage = max(Farbre / (t1 * Padm), Fmoyeu / ((h - t1) * Padm))
    LminCis = 2 * C / d / (b * tauAdm)
    dimensionne = L <= 0
    if dimensionne:
        # Lp arrondie au 1/100 mm strictement supérieur : à Lp = Lmin exacte, l'arrondi flottant donnerait p > Padm.
        L = math.floor(max(LminMatage, LminCis) * 100) / 100 + 0.01 + FORMES[forme] * b
    Lp = L - FORMES[forme] * b
    if Lp <= 0:
        raise MecaStructError(
            _ID, f"Longueur de clavette trop courte : L = {L:g} mm pour b = {b:g} mm (forme {forme})."
        )
    pArbre = Farbre / (Lp * t1)
    pMoyeu = Fmoyeu / (Lp * (h - t1))
    tau = 2 * C / d / (Lp * b)
    tauArbre = 16 * C / (math.pi * d**3)
    checks = [
        ("Matage arbre (MPa)", pArbre, Padm, pArbre <= Padm),
        ("Matage moyeu (MPa)", pMoyeu, Padm, pMoyeu <= Padm),
        ("Cisaillement clavette (MPa)", tau, tauAdm, tau <= tauAdm),
        ("Torsion arbre plein (MPa)", tauArbre, tauAdm, tauArbre <= tauAdm),
    ]
    report = [
        f"Clavette {b:g} × {h:g} (arbre d {k['dMin']:g} < d ≤ {k['dMax']:g} mm), rainure arbre t1 = {t1:g} mm, "
        f"moyeu t2 = {k['t2']:g} mm ; forme {forme} : longueur portante Lp = {Lp:g} mm",
        f"Matage arbre : F = 2C/(d − t1) = {Farbre:.5g} N ; p = F/(Lp·t1) = {pArbre:.4g} MPa (Padm {Padm:g})",
        f"Matage moyeu : F = 2C/(d − t1 + h) = {Fmoyeu:.5g} N ; p = F/(Lp·(h − t1)) = {pMoyeu:.4g} MPa",
        f"Cisaillement : τ = (2C/d)/(Lp·b) = {tau:.4g} MPa (τadm {tauAdm:.4g}) ; torsion arbre 16C/(πd³) = "
        f"{tauArbre:.4g} MPa",
        f"Longueur portante minimale : matage {LminMatage:.4g} mm, cisaillement {LminCis:.4g} mm",
    ]
    if dimensionne:
        report.append(
            f"Dimensionnement (L = 0) : Lp = {Lp:.4g} mm (minimum arrondi au 1/100 mm supérieur), "
            f"longueur totale L = Lp + {FORMES[forme]:g}·b = {L:.4g} mm"
        )
    latex = [
        rf"p_{{arbre}} = \frac{{2C}}{{(d-t_1)\,L_p\,t_1}}"
        rf" = \frac{{2\times{C:g}}}{{({d:g}-{t1:g})\times{Lp:g}\times{t1:g}}} = {pArbre:.4g}\ \mathrm{{MPa}}",
        rf"p_{{moyeu}} = \frac{{2C}}{{(d-t_1+h)\,L_p\,(h-t_1)}} = {pMoyeu:.4g}\ \mathrm{{MPa}}",
        rf"\tau = \frac{{2C}}{{d\,L_p\,b}} = \frac{{2\times{C:g}}}{{{d:g}\times{Lp:g}\times{b:g}}}"
        rf" = {tau:.4g}\ \mathrm{{MPa}}",
    ]
    return {"dims": k, "L": L, "dimensionne": dimensionne, "Lp": Lp, "pArbre": pArbre, "pMoyeu": pMoyeu,
            "tau": tau, "tauArbre": tauArbre,
            "checks": checks, "LminMatage": LminMatage, "LminCis": LminCis,
            "report": report, "latex": latex}  # fmt: skip


def pinTorque(p: dict) -> dict:
    """Goupille transmettant un couple entre un arbre et un moyeu.

    Entrées (dict) : montage (« transversale » : goupille radiale traversant arbre et moyeu ; « longitudinale » :
    goupille axiale dans le plan de joint), T (N·m), D (mm, arbre), D1 (mm, extérieur du moyeu, transversale),
    d (mm, goupille), dint (mm, alésage d'une goupille élastique, 0 = pleine), l (mm, longueur engagée,
    longitudinale), Padm, tauAdm (MPa).
    Sortie : dict pArbre, pMoyeu, tau, tauArbre (MPa), checks, report, latex.
    Formules classiques (Roloff/Matek) ; transversale : 2 sections cisaillées.
    """
    T = abs(float(p["T"])) * 1e3  # N·mm
    D, d = float(p["D"]), float(p["d"])
    dint = float(p.get("dint") or 0.0)
    if not 0 <= dint < d < D:
        raise MecaStructError(_ID, f"Il faut 0 ≤ dint < d < D (dint = {dint:g}, d = {d:g}, D = {D:g} mm).")
    A = math.pi * (d**2 - dint**2) / 4
    Padm, tauAdm = float(p["Padm"]), float(p["tauAdm"])
    if p.get("montage", "transversale") == "transversale":
        D1 = float(p["D1"])
        if D1 <= D:
            raise MecaStructError(_ID, f"Le moyeu ({D1:g} mm) doit être plus grand que l'arbre ({D:g} mm).")
        tau = T / (D * A)
        pArbre = 6 * T / (d * D**2)
        pMoyeu = 4 * T / (d * (D1**2 - D**2))
        latex = [
            rf"\tau = \frac{{T}}{{D\,A}} = \frac{{{T:g}}}{{{D:g}\times{A:.5g}}} = {tau:.4g}\ \mathrm{{MPa}}",
            rf"p_{{arbre}} = \frac{{6T}}{{d\,D^2}} = {pArbre:.4g},\quad p_{{moyeu}}"
            rf" = \frac{{4T}}{{d\,(D_1^2 - D^2)}} = {pMoyeu:.4g}\ \mathrm{{MPa}}",
        ]
        rep = (
            f"Goupille transversale : τ = T/(D·A) = {tau:.4g} MPa (2 sections) ; matage arbre 6T/(d·D²) = {pArbre:.4g} "
            f"MPa ; matage moyeu 4T/(d·(D1² − D²)) = {pMoyeu:.4g} MPa"
        )
    else:
        lg = float(p["l"])
        if lg <= 0:
            raise MecaStructError(_ID, f"Longueur engagée de la goupille longitudinale invalide : {lg:g} mm.")
        tau = 2 * T / (D * d * lg)
        pArbre = pMoyeu = 4 * T / (D * d * lg)
        latex = [
            rf"\tau = \frac{{2T}}{{D\,d\,l}} = {tau:.4g},\quad p = \frac{{4T}}{{D\,d\,l}}"
            rf" = {pArbre:.4g}\ \mathrm{{MPa}}"
        ]
        rep = f"Goupille longitudinale : τ = 2T/(D·d·l) = {tau:.4g} MPa ; matage 4T/(D·d·l) = {pArbre:.4g} MPa"
    tauArbre = 16 * T / (math.pi * D**3)
    checks = [
        ("Cisaillement goupille (MPa)", tau, tauAdm, tau <= tauAdm),
        ("Matage arbre (MPa)", pArbre, Padm, pArbre <= Padm),
        ("Matage moyeu (MPa)", pMoyeu, Padm, pMoyeu <= Padm),
        ("Torsion arbre plein (MPa)", tauArbre, tauAdm, tauArbre <= tauAdm),
    ]
    report = [rep, f"Torsion de l'arbre 16T/(πD³) = {tauArbre:.4g} MPa (trou de goupille non déduit)"]
    return {"pArbre": pArbre, "pMoyeu": pMoyeu, "tau": tau, "tauArbre": tauArbre, "checks": checks,
            "report": report, "latex": latex}  # fmt: skip
