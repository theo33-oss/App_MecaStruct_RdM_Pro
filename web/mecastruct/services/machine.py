"""Éléments de machines : ajustements ISO 286, frettage, paliers lisses, clavette normalisée, goupille sous couple.

Chaque compute* renvoie, comme les services de compute.py : result (sortie du moteur + rapport), tables
(« Synthèse » et tableaux propres), status (ligne d'état) et ok (verdict global, None si sans objet).
"""

import pandas as pd

from mecastruct.core import fits, key_pin, plain_bearing, shrink_fit
from mecastruct.core.data_manager import DataManager


def _verdict(ok: bool) -> str:
    return "vérifié" if ok else "NON vérifié"


def _checks(checks: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Contrôle": n, "Valeur": v, "Limite": lim, "Résultat": "OK" if ok else "NON"} for n, v, lim, ok in checks]
    )


# ------------------------------------------------------------------------------------------- ajustements


def defaultFitInput() -> dict:
    """Ajustement de l'exemple : Ø100 H7/r6 (frettage du classeur de l'auteur)."""
    return {"d": 100.0, "alesage": "H", "qa": 7, "arbre": "r", "qb": 6}


def computeFit(s: dict) -> dict:
    """Écarts, cotes limites et jeux d'un ajustement (saisie : d mm, alesage, qa, arbre, qb)."""
    r = fits.fit(s["d"], s["alesage"], int(s["qa"]), s["arbre"], int(s["qb"]))
    h, a, c = r["hole"], r["shaft"], r["cotes"]
    t = pd.DataFrame(
        [
            {"Pièce": f"Alésage {s['alesage']}{s['qa']}", "Écart sup (µm)": h["ES"], "Écart inf (µm)": h["EI"],
             "IT (µm)": h["IT"], "Cote maxi (mm)": c["alesageMax"], "Cote mini (mm)": c["alesageMin"]},
            {"Pièce": f"Arbre {s['arbre']}{s['qb']}", "Écart sup (µm)": a["es"], "Écart inf (µm)": a["ei"],
             "IT (µm)": a["IT"], "Cote maxi (mm)": c["arbreMax"], "Cote mini (mm)": c["arbreMin"]},
        ]
    )  # fmt: skip
    head = (
        f"Ajustement {s['d']:g} {s['alesage']}{s['qa']}/{s['arbre']}{s['qb']} {r['type']} : jeu de {r['jeuMin']:+g} "
        f"à {r['jeuMax']:+g} µm"
    )
    return {"result": {**r, "rapport": [head, *r["report"]]}, "tables": {"Synthèse": t}, "status": head, "ok": True}


# ----------------------------------------------------------------------------------------------- frettage


def defaultShrinkInput() -> dict:
    """Exemple du classeur de l'auteur : Ø100 × 100, moyeu Ø280, 750 W à 12 tr/min, adhérence 0,1, s = 1,5."""
    return {"Fa": 0.0, "C": 596.83103659460755, "f": 0.1, "s": 1.5, "d": 100.0, "di": 0.0, "D": 280.0, "L": 100.0,
            "matArbre": "S235", "matMoyeu": "S235", "qa": 6, "qm": 7, "lissage": 5.0, "jeu": 0.2}  # fmt: skip


def computeShrinkFit(s: dict, dm: DataManager) -> dict:
    """Frettage (saisie : Fa N, C N·m, f, s, d, di, D, L mm, matArbre, matMoyeu, qa, qm, lissage µm, jeu mm)."""
    ma, mm = dm.getMaterial(s["matArbre"]), dm.getMaterial(s["matMoyeu"])
    p = {**s, "Ea": ma["E"], "nua": ma["nu"], "Rea": ma["Re"], "Em": mm["E"], "num": mm["nu"], "Rem": mm["Re"],
         "alpham": mm["alpha"]}  # fmt: skip
    r = shrink_fit.shrinkFit(p)
    ok = all(x is None or x >= 1 for x in (r["sArbre"], r["sMoyeu"]))
    ft = r["fit"]
    rows = [
        ("Pression mini nécessaire (MPa)", r["pMin"]),
        ("Serrage utile (µm)", r["serrageUtile"]),
        ("Ajustement normalisé", f"H{s['qm']}/{r['arbre']}{s['qa']}"),
        ("Serrage normalisé mini / maxi (µm)", f"{ft['serrageMin']:g} / {ft['serrageMax']:g}"),
        ("Pression maxi (MPa)", r["pMax"]),
        ("Couple transmissible au serrage mini (N·m)", r["couple"]),
        ("σ équivalente arbre / moyeu (MPa)", f"{r['sigmaArbre']:.4g} / {r['sigmaMoyeu']:.4g}"),
        ("Coefficient de sécurité arbre / moyeu", f"{r['sArbre']:.3g} / {r['sMoyeu']:.3g}"),
        ("Température de chauffe ΔT (K)", r["deltaT"]),
    ]
    t = pd.DataFrame([{"Grandeur": n, "Valeur": v if isinstance(v, str) else f"{v:.5g}"} for n, v in rows])
    head = (
        f"Frettage H{s['qm']}/{r['arbre']}{s['qa']} : p = {r['pMinNorm']:.3g} à {r['pMax']:.3g} MPa, "
        f"chauffe ΔT = {r['deltaT']:.0f} K — résistance {_verdict(ok)}e"
    )
    return {"result": {**r, "rapport": [head, *r["report"]]}, "tables": {"Synthèse": t}, "status": head, "ok": ok}


# ------------------------------------------------------------------------------------------ paliers lisses


def defaultBearingInput() -> dict:
    """Exemple du classeur de l'auteur : 403 N radial, 100 N axial, 350 tr/min, coussinet Ø20 × 16 à collerette Ø30."""
    return {"Fr": 403.0, "Fa": 100.0, "n": 350.0, "osc": 0.0, "beta": 0.0, "d": 20.0, "L": 16.0, "Dfl": 30.0,
            "materiau": "Bronze roulé"}  # fmt: skip


def computeBearing(s: dict) -> dict:
    """Palier lisse (saisie : Fr, Fa N ; n tr/min ; osc /min, beta ° ; d, L, Dfl mm ; materiau)."""
    r = plain_bearing.plainBearing(s)
    checks = list(r["checks"])
    if r["collerette"]:
        c = r["collerette"]
        checks.append(("Collerette : P sous la courbe P-V (MPa)", c["Pa"], c["Plim"], c["Pa"] <= c["Plim"]))
    head = (
        f"Palier lisse {r['materiau']['Name']} : P = {r['P']:.3g} MPa, V = {r['V']:.3g} m/s, PV = {r['PV']:.3g} "
        f"MPa·m/s ({_verdict(r['ok'])})"
    )
    return {"result": {**r, "rapport": [head, *r["report"]]}, "tables": {"Synthèse": _checks(checks)},
            "status": head, "ok": r["ok"]}  # fmt: skip


# ---------------------------------------------------------------------- compléments clavette et goupille


def computeKeyStandard(saisie: dict, forme: str, tauAdm: float) -> dict:
    """Clavette normalisée à partir de la saisie Cisaillement (C kN·m, Dk mm, Lk mm, 0 = dimensionner, Padm MPa).

    tauAdm en MPa ; si Lk = 0, la longueur retenue est la longueur minimale (matage et cisaillement).
    """
    r = key_pin.keyStandard(
        {
            "C": saisie["C"] * 1e3,
            "d": saisie["Dk"],
            "L": saisie["Lk"],
            "forme": forme,
            "Padm": saisie["Padm"],
            "tauAdm": tauAdm,
        }  # fmt: skip
    )
    ok = all(c[3] for c in r["checks"])
    k = r["dims"]
    if r["dimensionne"]:
        head = (
            f"Clavette normalisée {k['b']:g} × {k['h']:g} forme {forme} : longueur minimale L = {r['L']:.4g} mm "
            f"(Lp = {r['Lp']:.4g} mm), {_verdict(ok)}"
        )
    else:
        head = f"Clavette normalisée {k['b']:g} × {k['h']:g} forme {forme}, Lp = {r['Lp']:g} mm : {_verdict(ok)}"
    return {"result": {**r, "rapport": [head, *r["report"]]}, "tables": {"Synthèse": _checks(r["checks"])},
            "status": head, "ok": ok}  # fmt: skip


def computePinTorque(p: dict) -> dict:
    """Goupille sous couple (voir key_pin.pinTorque ; T en N·m, longueurs en mm, Padm et tauAdm en MPa)."""
    r = key_pin.pinTorque(p)
    ok = all(c[3] for c in r["checks"])
    head = f"Goupille {p['montage']} sous {p['T']:g} N·m : {_verdict(ok)}"
    return {"result": {**r, "rapport": [head, *r["report"]]}, "tables": {"Synthèse": _checks(r["checks"])},
            "status": head, "ok": ok}  # fmt: skip
