"""Éléments de machines d'après les cours (IUT de Bordeaux) : roulements, engrenages, trains épicycloïdaux, freins et
embrayages, dimensionnement moteur.

Chaque compute* renvoie, comme les services de machine.py : result (sortie du moteur, rapport et formules), tables
(« Synthèse » et tableaux), status (ligne d'état) et ok (verdict global, None si sans objet).
"""

import math

import pandas as pd

from mecastruct.core import bearings, brake_clutch, gears, planetary, transmission
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services.machine import _checks, _verdict


def _synthese(lignes: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame([{"Grandeur": n, "Valeur": v} for n, v in lignes])


# ------------------------------------------------------------------------------------------------- roulements


def defaultBearingInput() -> dict:
    """Exemple du cours : roulement à billes à contact radial, Fr = 1000 daN, Fa = 400 daN, 300 tr/min, C = 35,8 kN."""
    return {"Fr": 10000.0, "Fa": 4000.0, "C": 35800.0, "C0": 19300.0, "N": 300.0, "type": "billes", "F": 90.0,
            "tableau": True, "e": 0.38, "X": 0.56, "Y": 1.31, "Lh": 1500.0}  # fmt: skip


def computeBearingLife(s: dict) -> dict:
    """Durée de vie d'un roulement : charge équivalente P, L10, L10h, Lnh (fiabilité F) et charge de base requise.

    Entrées : Fr, Fa (N), C, C0 (N), N (tr/min), type (« billes » ou « rouleaux »), F (fiabilité en %), tableau (True :
    e et Y interpolés dans la table du cours, billes à contact radial ; False : e, X, Y saisis), Lh (durée visée, h).
    """
    if s["tableau"] and s["type"] != "billes":
        raise MecaStructError(
            "MecaStruct:Bearing:invalidInput", "La table du cours vaut pour les billes : saisir e, X, Y."
        )
    if s["C0"] <= 0:
        raise MecaStructError(
            "MecaStruct:Bearing:invalidInput", "La charge statique C0 doit être strictement positive."
        )
    faC0 = s["Fa"] / s["C0"]
    fafr = s["Fa"] / s["Fr"] if s["Fr"] > 0 else math.inf
    if s["tableau"]:
        e, Y = bearings.eYInterpolated(faC0)
        X = bearings.xyTable()["X"]
    else:
        e, X, Y = s["e"], s["X"], s["Y"]
    P = bearings.dynamicLoad(s["Fr"], s["Fa"], e, X, Y)
    n = bearings.EXPOSANT[s["type"]]
    L10 = bearings.lifeMTours(s["C"], P, n)
    L10h = bearings.lifeHours(L10, s["N"])
    a1 = bearings.reliabilityFactor(s["F"] / 100)
    Lnh = a1 * L10h
    Creq = bearings.dynamicRating(P, s["Lh"] * 60 * s["N"] / 1e6 / a1, n)
    ok = Lnh >= s["Lh"]
    head = (
        f"Roulement : P = {P:.0f} N, L10h = {L10h:.0f} h, Lnh = {Lnh:.0f} h à {s['F']:g} % de fiabilité "
        f"({_verdict(ok)} pour {s['Lh']:g} h)"
    )
    if s["Fr"] == 0:
        equivalente = rf"P = F_a = {P:.5g}\ \mathrm{{N}}"
    elif fafr <= e:
        equivalente = rf"P = F_r = {P:.5g}\ \mathrm{{N}}"
    else:
        equivalente = (
            rf"P = X F_r + Y F_a = {X:g} \times {s['Fr']:g} + {Y:.4g} \times {s['Fa']:g} = {P:.5g}\ \mathrm{{N}}"
        )
    latex = [
        rf"Fa/C_0 = {faC0:.4g} \quad e = {e:.4g} \quad Y = {Y:.4g}",
        equivalente,
        rf"L_{{10}} = \left(\frac{{C}}{{P}}\right)^{{{n:.4g}}} = {L10:.4g}\ \mathrm{{millions\ de\ tours}}",
        rf"L_{{10h}} = \frac{{10^6\, L_{{10}}}}{{60\, N}} = {L10h:.5g}\ \mathrm{{h}}",
        rf"L_{{nh}} = a_1\, L_{{10h}} = {a1:.4g} \times {L10h:.5g} = {Lnh:.5g}\ \mathrm{{h}}",
    ]
    rapport = [
        "Charge équivalente : butée, P = Fa"
        if s["Fr"] == 0
        else f"Charge équivalente : Fa/Fr = {fafr:.4g} comparé à e = {e:.4g}",
        f"Durée L10 : (C/P)^{n:.4g} = ({s['C']:g}/{P:.5g})^{n:.4g} = {L10:.4g} millions de tours",
        f"Fiabilité {s['F']:g} % : a1 = (ln(1/F)/ln(1/0,9))^(1/1,5) = {a1:.4g}",
        f"Charge de base minimale pour {s['Lh']:g} h à la fiabilité {s['F']:g} % : C = {Creq:.5g} N "
        f"(C saisi : {s['C']:g} N)",
    ]
    tab = _synthese(
        [
            ("Charge équivalente P (N)", f"{P:.5g}"),
            ("L10 (millions de tours)", f"{L10:.4g}"),
            ("L10h (heures)", f"{L10h:.0f}"),
            (f"a1 (fiabilité {s['F']:g} %)", f"{a1:.4g}"),
            ("Lnh (heures)", f"{Lnh:.0f}"),
            (f"Charge de base C requise pour {s['Lh']:g} h (N)", f"{Creq:.5g}"),
        ]
    )
    res = {"P": P, "e": e, "X": X, "Y": Y, "L10": L10, "L10h": L10h, "a1": a1, "Lnh": Lnh, "Creq": Creq,
           "rapport": [head, *rapport], "latex": latex}  # fmt: skip
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": ok}


def defaultBearingSetInput() -> dict:
    """Exemple du cours : deux durées de 15 000 h et 25 000 h, puis un guidage de 15 000 h avec deux roulements."""
    return {"L1": 15000.0, "L2": 25000.0, "L3": 0.0, "LG": 15000.0, "nG": 2}


def computeBearingSet(s: dict) -> dict:
    """Ensemble de roulements en série (durée L_E) et durée de chaque roulement iso-fiable pour un guidage donné.

    Entrées : L1, L2, L3 (h, 0 = absent), LG (h, durée du guidage), nG (nombre de roulements iso-fiables).
    """
    durees = [x for x in (s["L1"], s["L2"], s["L3"]) if x > 0]
    LE = bearings.lifeSet(durees)
    nG = int(s["nG"])
    Liso = bearings.isoReliableLife(s["LG"], nG)
    head = (
        f"Ensemble de {len(durees)} roulement(s) : L_E = {LE:.0f} h ; guidage de {s['LG']:g} h avec "
        f"{nG} roulements iso-fiables : {Liso:.0f} h chacun"
    )
    rapport = [
        "Durée d'un ensemble : (Σ Lj^(−1,5))^(−1/1,5) avec les durées de chaque roulement",
        f"Durées saisies : {', '.join(f'{x:g} h' for x in durees)} ; L_E = {LE:.5g} h",
        f"Roulements iso-fiables : L = LG · nG^(2/3) = {s['LG']:g} × {nG}^(2/3) = {Liso:.5g} h",
    ]
    latex = [
        rf"L_E = \left(\sum_j L_j^{{-1{{,}}5}}\right)^{{-1/1{{,}}5}} = {LE:.5g}\ \mathrm{{h}}",
        rf"L = L_G \cdot n_G^{{2/3}} = {s['LG']:g} \times {nG}^{{2/3}} = {Liso:.5g}\ \mathrm{{h}}",
    ]
    tab = _synthese(
        [("Durée de l'ensemble L_E (h)", f"{LE:.0f}"), ("Durée de chaque roulement iso-fiable (h)", f"{Liso:.0f}")]
    )
    res = {"LE": LE, "Liso": Liso, "rapport": [head, *rapport], "latex": latex}
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": None}


# ------------------------------------------------------------------------------------------------- engrenages


def defaultGearInput() -> dict:
    """Pignon Z = 20, module 2 mm, roue Z = 40, 500 W à 500 tr/min, acier S235, k = 8, sécurité 1,5."""
    return {"m": 2.0, "Z1": 20, "Z2": 40, "P": 500.0, "N": 500.0, "k": 8.0, "materiau": "S235", "s": 1.5}


def computeGearMesh(s: dict, dm: DataManager) -> dict:
    """Engrènement droit : géométrie, rapport, efforts sur la denture, contrainte en pied de dent et module minimal.

    Entrées : m (mm), Z1, Z2, P (W) et N (tr/min) sur le pignon, k = b/m, materiau (base de données), s (sécurité).
    Le pignon est vérifié avec Rpe = Re/s (Re lu dans la base de matériaux, converti en MPa).
    """
    Z1, Z2 = int(s["Z1"]), int(s["Z2"])
    if s["N"] <= 0:
        raise MecaStructError("MecaStruct:Gears:invalidInput", "La fréquence de rotation du pignon doit être positive.")
    C1 = 30 * s["P"] / (math.pi * s["N"])
    geo = gears.geometry(s["m"], Z1)
    r = gears.ratio(Z1, Z2)
    a = gears.centerDistance(s["m"], Z1, Z2)
    f = gears.toothForces(C1, geo["d"])
    Rpe = dm.getMaterial(s["materiau"])["Re"] / 1e6 / s["s"]
    sigma = gears.rootStress(f["Ft"], s["m"], s["k"])
    mMini = gears.moduleMini(f["Ft"], s["k"], Rpe)
    mNorm = gears.normalizedModule(mMini)
    ok = sigma <= Rpe
    head = (
        f"Engrènement m = {s['m']:g} mm, Z = {Z1}/{Z2} : r = {r:.4g}, σ pied = {sigma:.4g} MPa "
        f"≤ Rpe = {Rpe:.4g} MPa ({_verdict(ok)})"
    )
    latex = [
        rf"C_1 = \frac{{P}}{{\omega}} = {C1:.4g}\ \mathrm{{N{{\cdot}}m}}",
        rf"F_t = \frac{{2C_1}}{{d_1}} = {f['Ft']:.5g}\ \mathrm{{N}}, \quad F_r = F_t \tan\alpha = {f['Fr']:.5g}\ "
        rf"\mathrm{{N}}, \quad F_n = \frac{{F_t}}{{\cos\alpha}} = {f['Fn']:.5g}\ \mathrm{{N}}",
        rf"\sigma = \frac{{54\, F_t}}{{\pi^2\, k\, m^2}} = {sigma:.4g}\ \mathrm{{MPa}}",
        rf"m \geq \sqrt{{\frac{{54\, F_t}}{{\pi^2\, k\, R_{{pe}}}}}} = {mMini:.4g}\ \mathrm{{mm}}",
    ]
    rapport = [
        f"Géométrie du pignon : d1 = m·Z1 = {geo['d']:g} mm ; roue d2 = {s['m'] * Z2:g} mm ; entraxe "
        f"a = {a:g} mm ; pas p = π·m = {geo['p']:.4g} mm",
        f"Couple au pignon : C1 = 30·P/(π·N) = {C1:.4g} N·m",
        f"Largeur de denture b = k·m = {s['k'] * s['m']:g} mm (k = {s['k']:g}, plage usuelle 6 à 10)",
        f"Rpe = Re/s = {Rpe * s['s']:g}/{s['s']:g} = {Rpe:.4g} MPa (Re du matériau {s['materiau']})",
        f"Module minimal {mMini:.4g} mm, module normalisé retenu {mNorm:g} mm",
    ]
    tab = _synthese(
        [
            ("Rapport de transmission", f"{r:.4g}"),
            ("Entraxe (mm)", f"{a:g}"),
            ("Diamètre primitif pignon (mm)", f"{geo['d']:g}"),
            ("Couple pignon C1 (N·m)", f"{C1:.4g}"),
            ("Effort tangentiel Ft (N)", f"{f['Ft']:.5g}"),
            ("Effort radial Fr (N)", f"{f['Fr']:.5g}"),
            ("Effort normal Fn (N)", f"{f['Fn']:.5g}"),
            ("Contrainte en pied de dent σ (MPa)", f"{sigma:.4g}"),
            ("Rpe admissible (MPa)", f"{Rpe:.4g}"),
            ("Module minimal (mm)", f"{mMini:.4g}"),
            ("Module normalisé retenu (mm)", f"{mNorm:g}"),
        ]
    )
    res = {"r": r, "a": a, "d": geo["d"], "C1": C1, "Ft": f["Ft"], "Fr": f["Fr"], "Fn": f["Fn"], "sigma": sigma,
           "Rpe": Rpe, "mMini": mMini, "mNorm": mNorm, "rapport": [head, *rapport], "latex": latex}  # fmt: skip
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": ok}


def defaultGearTrainInput() -> dict:
    """Train de trois engrènements en série : 1000 W à 500 tr/min en entrée, rendement 0,98 par engrènement."""
    return {"P": 1000.0, "N": 500.0, "eta": 0.98, "Z1": 15, "Z2": 45, "Z3": 20, "Z4": 40, "Z5": 10, "Z6": 50}


def computeGearTrain(s: dict) -> dict:
    """Train d'engrenages en série : fréquence de rotation, puissance et couple de chaque arbre.

    Entrées : P (W) et N (tr/min) à l'entrée, eta (rendement d'un engrènement), Z1 à Z6 (paires menante / menée).
    """
    paires = [(int(s[f"Z{i}"]), int(s[f"Z{i + 1}"])) for i in (1, 3, 5)]
    lignes = gears.gearTrain(paires, s["P"], s["N"], s["eta"])
    entree, sortie = lignes[0], lignes[-1]
    r = sortie["N"] / entree["N"]
    tab = pd.DataFrame(
        [
            {"Arbre": ligne["arbre"], "Fréquence (tr/min)": round(ligne["N"], 3),
             "Puissance (W)": round(ligne["P"], 2), "Couple (N·m)": round(ligne["C"], 3)}
            for ligne in lignes
        ]
    )  # fmt: skip
    head = (
        f"Train de {len(paires)} engrènements : r = {r:.4g}, sortie {sortie['N']:.4g} tr/min, "
        f"{sortie['P']:.0f} W, {sortie['C']:.4g} N·m"
    )
    rapport = [
        "Rapport de chaque engrènement : −Z menant / Z mené ; le rapport total est le produit des rapports",
        f"Puissance : P × η par engrènement, soit {s['eta']:g}^{len(paires)} = {sortie['P'] / entree['P']:.4g}",
        f"Couple de sortie : C = P/ω = {sortie['C']:.4g} N·m",
    ]
    res = {"lignes": lignes, "r": r, "rapport": [head, *rapport], "latex": []}
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": None}


# ------------------------------------------------------------------------------------------- trains épicycloïdaux


def defaultPlanetaryInput() -> dict:
    """Exemple du cours : planétaire Z1 = 15, satellite Z2 = 9, couronne Z4 = 33, couronne bloquée."""
    return {"Z1": 15, "Z21": 9, "Z22": 9, "Z4": 33, "nSat": 3, "bloque": "couronne", "entree": "planétaire",
            "Ne": 1500.0}  # fmt: skip


def computePlanetary(s: dict) -> dict:
    """Train épicycloïdal plan : raison basique (formule de Willis), vitesse de sortie et conditions de montage.

    Entrées : Z1 (planétaire), Z21 et Z22 (satellites engrenant le planétaire et la couronne), Z4 (couronne), nSat,
    bloque et entree (« planétaire », « couronne » ou « porte-satellites »), Ne (vitesse d'entrée, tr/min).
    """
    Z1, Z21, Z22, Z4, nSat = (int(s[k]) for k in ("Z1", "Z21", "Z22", "Z4", "nSat"))
    rb = planetary.basicRatio(Z1, Z21, Z22, Z4)
    v = planetary.speeds(rb, s["bloque"], s["entree"], s["Ne"])
    sortie = next(e for e in planetary.ELEMENTS if e not in (s["bloque"], s["entree"]))
    r = v[sortie] / s["Ne"]
    checks = planetary.assemblyChecks(Z1, Z21, Z22, Z4, nSat)
    ok = all(c[2] for c in checks)
    head = f"Train épicycloïdal : rb = {rb:.4g}, {sortie} à {v[sortie]:.4g} tr/min, r = {r:.4g}"
    rapport = [
        f"Raison basique : rb = −Z1·Z22/(Z21·Z4) = −{Z1}·{Z22}/({Z21}·{Z4}) = {rb:.4g}",
        f"Willis : ω_couronne − ω_PS = rb·(ω_planétaire − ω_PS) ; {s['bloque']} bloquée, "
        f"{s['entree']} à {s['Ne']:g} tr/min",
        f"Rapport de réduction r = ω_sortie/ω_entrée = {r:.4g}",
    ]
    rapport += [f"Montage, {nom} = {val:g} : {'OK' if ok_ else 'NON'}" for nom, val, ok_ in checks]
    latex = [
        rf"r_b = \frac{{\omega_{{couronne}} - \omega_{{PS}}}}{{\omega_{{planétaire}} - \omega_{{PS}}}} = "
        rf"\frac{{-Z_1 Z_{{22}}}}{{Z_{{21}} Z_4}} = {rb:.4g}",
        r"\omega_{couronne} - \omega_{PS} = r_b\,(\omega_{planétaire} - \omega_{PS})",
    ]
    tab = pd.DataFrame(
        [
            {"Élément": e, "Vitesse (tr/min)": round(v[e], 4),
             "Rôle": "bloqué" if e == s["bloque"] else ("entrée" if e == s["entree"] else "sortie")}
            for e in planetary.ELEMENTS
        ]
    )  # fmt: skip
    res = {"rb": rb, "vitesses": v, "r": r, "rapport": [head, *rapport], "latex": latex}
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": ok}


# --------------------------------------------------------------------------------------- freins et embrayages


def defaultBrakeInput() -> dict:
    """Frein à disque : effort 5000 N, f = 0,35, 2 surfaces, rayons 70 à 120 mm, disque à 1000 tr/min."""
    return {"F": 5000.0, "f": 0.35, "n": 2, "Re": 120.0, "Ri": 70.0, "N": 1000.0}


def computeBrake(s: dict) -> dict:
    """Frein à disque : couple de freinage, pression maxi et puissance spécifique pour les deux lois d'usure.

    Entrées : F (N, effort presseur par surface), f (coefficient de frottement), n (surfaces frottantes), Re et Ri
    (mm), N (tr/min, vitesse du disque au freinage).
    """
    omega = 2 * math.pi * s["N"] / 60
    lois = {"pression constante": "pression", "usure constante": "usure"}
    lignes = []
    for nom, loi in lois.items():
        Cf = brake_clutch.brakeTorque(s["F"], s["f"], s["n"], s["Re"], s["Ri"], loi)
        p = brake_clutch.maxPressure(s["F"], s["Re"], s["Ri"], loi)
        ps = brake_clutch.specificPower(Cf, omega, s["n"], s["Re"], s["Ri"])
        lignes.append({"Loi": nom, "Couple Cf (N·m)": round(Cf, 4), "Pression maxi (MPa)": round(p, 4),
                       "Puissance spécifique (W/mm²)": round(ps, 6)})  # fmt: skip
    Cp, Cu = (brake_clutch.brakeTorque(s["F"], s["f"], s["n"], s["Re"], s["Ri"], loi) for loi in lois.values())
    head = f"Frein à disque : Cf = {Cp:.4g} N·m (pression constante), {Cu:.4g} N·m (usure constante)"
    rapport = [
        "Pression constante : Cf = n·f·F·(2/3)·(Re³ − Ri³)/(Re² − Ri²)",
        "Usure constante : Cf = n·f·F·(Re + Ri)/2",
        f"Puissance dissipée à {s['N']:g} tr/min : Cf·ω = {Cp * omega:.5g} W (pression constante)",
    ]
    latex = [
        rf"C_f = \frac{{2}}{{3}}\, n f F \frac{{R_e^3 - R_i^3}}{{R_e^2 - R_i^2}} = {Cp:.5g}\ \mathrm{{N{{\cdot}}m}}",
        rf"C_f = n f F \frac{{R_e + R_i}}{{2}} = {Cu:.5g}\ \mathrm{{N{{\cdot}}m}}",
    ]
    tab = pd.DataFrame(lignes)
    res = {"Cp": Cp, "Cu": Cu, "rapport": [head, *rapport], "latex": latex}
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": None}


def defaultClutchInput() -> dict:
    """Exemple du cours : moteur 130 N·m à 1500 tr/min, récepteur JR = 1,2 kg·m², couple résistant CR = −55 N·m."""
    return {"CM": 130.0, "NM": 1500.0, "JR": 1.2, "CR": -55.0, "ts": 10.0, "cadence": 10.0}


def computeClutch(s: dict) -> dict:
    """Embrayage : couple à transmettre pour synchroniser en ts, durée réelle, énergie dissipée et puissance moyenne.

    Entrées : CM (N·m, couple moteur), NM (tr/min, vitesse du moteur, supposée constante pendant la synchronisation),
    JR (kg·m²), CR (N·m, couple résistant, négatif), ts (s, durée visée), cadence (manœuvres par heure).
    """
    omega = 2 * math.pi * s["NM"] / 60
    Cacc = s["JR"] * omega / s["ts"]
    CT = brake_clutch.clutchTorqueFor(s["JR"], omega, s["CR"], s["ts"])
    t = brake_clutch.syncTime(s["JR"], omega, CT, s["CR"])
    E = brake_clutch.slipEnergy(CT, omega, t)
    Pmoy = E * s["cadence"] / 3600
    ok = CT <= s["CM"]
    head = (
        f"Embrayage : CT = {CT:.4g} N·m pour synchroniser en {t:.4g} s ({_verdict(ok)} face au couple moteur "
        f"{s['CM']:g} N·m)"
    )
    rapport = [
        f"Couple d'accélération du récepteur : JR·ω/ts = {Cacc:.4g} N·m ; couple résistant : {abs(s['CR']):g} N·m",
        f"Couple d'embrayage : CT = |CR| + JR·ω/ts = {CT:.4g} N·m",
        f"Énergie dissipée par glissement : CT·ω·t/2 = {E:.5g} J ; puissance moyenne à {s['cadence']:g} manœuvres/h "
        f"= {Pmoy:.4g} W",
        "Hypothèse du cours : vitesse du moteur constante pendant la synchronisation (JM n'intervient donc pas)",
    ]
    latex = [
        rf"J_R \dot\omega_R = C_R + C_T \quad \Rightarrow \quad C_T = |C_R| + \frac{{J_R\, \omega_M}}{{t_s}} = "
        rf"{CT:.5g}\ \mathrm{{N{{\cdot}}m}}",
        rf"E = \frac{{C_T\, \omega_M\, t_s}}{{2}} = {E:.5g}\ \mathrm{{J}}",
    ]
    tab = _synthese(
        [
            ("Couple d'accélération (N·m)", f"{Cacc:.4g}"),
            ("Couple d'embrayage CT (N·m)", f"{CT:.4g}"),
            ("Durée de synchronisation (s)", f"{t:.4g}"),
            ("Énergie par manœuvre (J)", f"{E:.5g}"),
            ("Puissance moyenne dissipée (W)", f"{Pmoy:.4g}"),
        ]
    )
    res = {"Cacc": Cacc, "CT": CT, "t": t, "E": E, "Pmoy": Pmoy, "rapport": [head, *rapport], "latex": latex}
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": ok}


# ------------------------------------------------------------------------------------- dimensionnement moteur


def defaultMotorInput() -> dict:
    """Exemple du cours (ascenseur) : 120 N·m en accélération, 54 N·m en régime établi.
    Moteur retenu dans le cours : 63 N·m nominal, 126 N·m maxi, 1470 tr/min.
    Les durées des phases ne sont pas données dans le cours : valeurs choisies pour retrouver C_th = 61 N·m.
    """
    return {"Ca": 120.0, "ta": 1.0, "Cc": 54.0, "tc": 13.3, "Cfr": 0.0, "tfr": 0.0, "Cn": 63.0, "Cmax": 126.0,
            "Nmax": 1470.0, "Nreq": 1000.0, "Jm": 0.6, "Js": 1.2, "rs": 1.0}  # fmt: skip


def computeMotor(s: dict) -> dict:
    """Choix du moteur : couple équivalent thermique du cycle, vérifications nominal / maxi / vitesse, inertie ramenée.

    Entrées : phases (Ca, ta ; Cc, tc ; Cfr, tfr : couple en N·m et durée en s), moteur (Cn, Cmax en N·m ; Nmax en
    tr/min), Nreq (tr/min, vitesse requise), Jm (kg·m², moteur), Js (kg·m²) et rs (rapport de réduction) de la sortie.
    """
    phases = [(s["Ca"], s["ta"]), (s["Cc"], s["tc"]), (s["Cfr"], s["tfr"])]
    phases = [p for p in phases if p[1] > 0]
    Cth = transmission.thermalTorque(phases)
    Cpointe = max(abs(C) for C, _ in phases)
    checks = transmission.motorChecks(Cth, Cpointe, s["Nreq"], {"Cn": s["Cn"], "Cmax": s["Cmax"], "Nmax": s["Nmax"]})
    J = transmission.reducedInertia(s["Jm"], [(s["Js"], s["rs"])])
    ok = all(c[3] for c in checks)
    head = f"Moteur : C_th = {Cth:.4g} N·m, couple de pointe {Cpointe:g} N·m ({_verdict(ok)})"
    rapport = [
        f"Couple équivalent thermique : √(Σ C²·t / Σ t) = {Cth:.4g} N·m sur {sum(t for _, t in phases):g} s de cycle",
        f"Inertie ramenée à l'arbre moteur : Jm + Js/rs² = {J:.4g} kg·m²",
    ]
    latex = [
        rf"C_{{th}} = \sqrt{{\frac{{\sum C_i^2\, t_i}}{{\sum t_i}}}} = {Cth:.4g}\ \mathrm{{N{{\cdot}}m}}",
        rf"J = J_m + \frac{{J_s}}{{r_s^2}} = {J:.4g}\ \mathrm{{kg{{\cdot}}m^2}}",
    ]
    tab = _checks(checks)
    res = {"Cth": Cth, "Cpointe": Cpointe, "J": J, "rapport": [head, *rapport], "latex": latex}
    return {"result": res, "tables": {"Synthèse": tab}, "status": head, "ok": ok}
