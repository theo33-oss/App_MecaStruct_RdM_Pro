"""Palier lisse (coussinet) : pression P, vitesse de glissement V, produit PV et diagramme P-V du matériau.

Port du classeur « CALCULS PALIERS LISSES.xlsm » de l'auteur, sans le catalogue du fabricant : le palier est
vérifié pour les dimensions saisies. Le module de calcul du classeur était illisible ; le modèle P-V est celui de
sa feuille MATIERE, vérifié sur les valeurs enregistrées (tests/test_plain_bearing.py).
"""

import math

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import load_json

_ID = "MecaStruct:PlainBearing:invalidInput"


def materials() -> list[dict]:
    """Matériaux de coussinet : Name, Pmax, Pdyn (MPa), Vmax (m/s), f (frottement)."""
    return load_json("plain_bearing_materials.json")["Materiaux"]


def material(nom: str) -> dict:
    """Matériau de coussinet `nom` (voir materials). Erreur : MecaStruct:PlainBearing:invalidInput."""
    for m in materials():
        if m["Name"] == nom:
            return m
    raise MecaStructError(_ID, f"Matériau de coussinet inconnu : {nom!r}.")


def pLimit(m: dict, V: float) -> float:
    """Pression limite (MPa) du matériau `m` à la vitesse V (m/s) : courbe log-log de la feuille MATIERE.

    Entre 0,001 et 0,01 m/s, de Pmax à Pdyn ; au-delà de 0,01 m/s, de Pdyn à 1 MPa en Vmax ; 0 au-delà de Vmax.
    """
    if V <= 0.001:
        return m["Pmax"]
    if V < 0.01:
        x = (math.log(V) - math.log(0.001)) / (math.log(0.01) - math.log(0.001))
        return math.exp(math.log(m["Pmax"]) - (math.log(m["Pmax"]) - math.log(m["Pdyn"])) * x)
    if V > m["Vmax"]:
        return 0.0
    return math.exp(math.log(m["Pdyn"]) * (1 - (math.log(V) - math.log(0.01)) / (math.log(m["Vmax"]) - math.log(0.01))))


def plainBearing(p: dict) -> dict:
    """Vérification d'un coussinet cylindrique (et de sa collerette) en rotation continue ou en oscillation.

    Entrées (dict) : Fr, Fa (N) ; n (tr/min) ; osc (oscillations/min), beta (°, demi-amplitude) : s'ils sont
    renseignés, ils remplacent n ; d, L (mm, alésage et longueur du coussinet) ; materiau (nom) ; Dfl (mm, diamètre
    de collerette, 0 = sans collerette).
    Sortie : dict P, V, PV, Plim, PVadm, oscillation (bool), checks (liste de (nom, valeur, limite, ok)), ok,
    collerette (dict Pa, Va, PVa, Plim, ok ou None), puissance (W perdue par frottement), report, latex.
    Erreur : MecaStruct:PlainBearing:invalidInput.
    """
    m = material(p["materiau"])
    d, L = float(p.get("d") or 0), float(p.get("L") or 0)
    if d <= 0 or L <= 0:
        raise MecaStructError(
            _ID, f"Diamètre et longueur du coussinet doivent être positifs (d = {d:g}, L = {L:g} mm)."
        )
    Fr, Fa = abs(float(p.get("Fr") or 0)), abs(float(p.get("Fa") or 0))
    osc, beta = float(p.get("osc") or 0), float(p.get("beta") or 0)
    oscillation = osc > 0 and beta > 0
    if oscillation:
        V = 4 * beta / 360 * osc / 60 * math.pi * d / 1000  # chemin 4β par oscillation
        vTxt = f"V = π·d·(4β/360)·f/60 = π×{d:g}×(4×{beta:g}/360)×{osc:g}/60 mm/s"
    else:
        V = math.pi * d * float(p.get("n") or 0) / 60000
        vTxt = f"V = π·d·n/60000 = π×{d:g}×{float(p.get('n') or 0):g}/60000"
    P = Fr / (d * L)
    Plim = pLimit(m, V)
    PV, PVadm = P * V, Plim * V
    checks = [
        ("P (MPa)", P, m["Pdyn"] if V > 0 else m["Pmax"], P <= (m["Pdyn"] if V > 0 else m["Pmax"])),
        ("V (m/s)", V, m["Vmax"], V <= m["Vmax"]),
        ("P sous la courbe P-V (MPa)", P, Plim, P <= Plim),
    ]
    colle = None
    Dfl = float(p.get("Dfl") or 0)
    if Dfl > 0:
        if Dfl <= d:
            raise MecaStructError(_ID, f"Le diamètre de collerette ({Dfl:g} mm) doit dépasser l'alésage ({d:g} mm).")
        Pa = Fa / (math.pi / 4 * (Dfl**2 - d**2))
        Va = V * Dfl / d  # vitesse au bord extérieur de la collerette
        PlimA = pLimit(m, Va)
        colle = {"Pa": Pa, "Va": Va, "PVa": Pa * Va, "Plim": PlimA, "ok": Pa <= PlimA and Va <= m["Vmax"]}
    ok = all(c[3] for c in checks) and (colle is None or colle["ok"])
    puissance = m["f"] * Fr * V
    report = [
        f"Matériau {m['Name']} : Pmax = {m['Pmax']:g} MPa, Pdyn = {m['Pdyn']:g} MPa, Vmax = {m['Vmax']:g} m/s, "
        f"f = {m['f']:g}",
        f"P = Fr/(d·L) = {Fr:g}/({d:g}×{L:g}) = {P:.4g} MPa",
        f"{vTxt} = {V:.4g} m/s" + (" (oscillation)" if oscillation else ""),
        f"P limite à cette vitesse = {Plim:.4g} MPa ; PV = {PV:.4g} MPa·m/s ; PV admissible = {PVadm:.4g} MPa·m/s",
        f"Puissance perdue par frottement f·Fr·V = {puissance:.4g} W",
    ]
    if colle:
        report.append(
            f"Collerette : Pa = Fa/(π/4·(Dfl² − d²)) = {colle['Pa']:.4g} MPa, Va = {colle['Va']:.4g} m/s, "
            f"P limite = {colle['Plim']:.4g} MPa → {'vérifiée' if colle['ok'] else 'NON vérifiée'}"
        )
    report.append("Palier vérifié." if ok else "Palier NON vérifié.")
    latex = [
        rf"P = \frac{{F_r}}{{d\,L}} = \frac{{{Fr:g}}}{{{d:g}\times{L:g}}} = {P:.4g}\ \mathrm{{MPa}}",
        rf"V = {V:.4g}\ \mathrm{{m/s}},\quad P_{{lim}}(V) = {Plim:.4g}\ \mathrm{{MPa}},\quad PV"
        rf" = {PV:.4g} \le PV_{{adm}} = {PVadm:.4g}",
    ]
    return {"P": P, "V": V, "PV": PV, "Plim": Plim, "PVadm": PVadm, "oscillation": oscillation, "checks": checks,
            "ok": ok, "collerette": colle, "puissance": puissance, "materiau": m,
            "report": report, "latex": latex}  # fmt: skip
