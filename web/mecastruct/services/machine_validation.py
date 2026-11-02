"""Dossier de validation HTML des pages de cours « Éléments de machines » : roulements, engrenages, trains
épicycloïdaux, freins et embrayages, dimensionnement moteur.

Même gabarit et mêmes 8 parties que validation_report. Une page regroupe plusieurs calculs : chaque partie donne un
bloc par calcul, « non inclus » quand le calcul n'a pas de résultat à jour. Les contrôles à la main refont les
formules du cours depuis la saisie, sans appeler les moteurs de mecastruct.core : ils prouvent que le solveur applique
bien ces formules, pas que les formules conviennent au cas (c'est l'objet des hypothèses du §2). Aucun import de
streamlit.
"""

import math
import platform
import re
import unicodedata
from datetime import datetime

import numpy as np

from mecastruct.core.utils import load_json
from mecastruct.services.validation_report import (
    _CHOIX,
    _SECTIONS,
    _bilan,
    _champs,
    _chk,
    _esc,
    _grp,
    _hc,
    _kv,
    _lvl,
    _mj,
    _reportHTML,
    _reviewHTML,
    _tableHTML,
    _template,
    _verdict,
)

_NON_INCLUS = (
    '<p class="warnbox">Non inclus : pas de résultat à jour pour ce calcul (cliquez sur « Calculer » dans son '
    "onglet, puis régénérez le dossier).</p>"
)

# ------------------------------------------------------------------------------------------------- roulements


def _bearing(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    Fr, Fa, C, N = s["Fr"], s["Fa"], s["C"], s["N"]
    faC0 = Fa / s["C0"]
    rows, chk = [_grp("Charge dynamique équivalente")], []
    if s["tableau"]:
        t = load_json("bearing_xy.json")
        x = t["FaC0"]
        e, Y, X = float(np.interp(faC0, x, t["e"])), float(np.interp(faC0, x, t["Y"])), t["X"]
        lat = rf"F_a/C_0 = {Fa:g}/{s['C0']:g} = {faC0:.4g}\ \text{{(interpolation linéaire dans la table)}}"
        rows += [
            _hc("Coefficient e", lat, e, R["e"]),
            _hc("Coefficient Y", lat, Y, R["Y"]),
            _hc("Coefficient X", rf"X = {X:g}\ \text{{(table)}}", X, R["X"]),
        ]
        chk.append(
            _chk(
                "Fa/C0 dans la table du cours",
                f"Fa/C0 = {faC0:.4g} (table de {x[0]:g} à {x[-1]:g})",
                x[0] <= faC0 <= x[-1],
            )
        )
    else:
        e, X, Y = s["e"], s["X"], s["Y"]
        chk.append(_chk("e, X et Y saisis : à relire dans le catalogue", f"e = {e:g}, X = {X:g}, Y = {Y:g}", "warn"))
    if Fr == 0:
        P, lat = Fa, rf"F_r = 0\ \text{{(butée)}} \Rightarrow P = F_a = {Fa:g}"
    else:
        fafr = Fa / Fr
        if fafr <= e:
            P, lat = Fr, rf"F_a/F_r = {fafr:.4g} \leq e = {e:.4g} \Rightarrow P = F_r = {Fr:g}"
        else:
            P = X * Fr + Y * Fa
            lat = rf"F_a/F_r = {fafr:.4g} > e = {e:.4g} \Rightarrow P = {X:g} \times {Fr:g} + {Y:.6g} \times {Fa:g}"
        # près de e, une lecture de e un peu différente change de formule (cas de l'exemple du cours)
        chk.append(
            _chk(
                "Branche de la charge équivalente nette : Fa/Fr à plus de 5 % de e",
                f"Fa/Fr = {fafr:.4g}, e = {e:.4g}",
                _lvl(abs(fafr - e) > 0.05 * e, "warn"),
            )
        )
    rows.append(_hc("Charge équivalente P", lat, P, R["P"], "N"))
    n = 3.0 if s["type"] == "billes" else 10 / 3
    F = s["F"] / 100
    L10 = (C / P) ** n
    L10h = 1e6 * L10 / (60 * N)
    a1 = (math.log(1 / F) / math.log(1 / 0.9)) ** (1 / 1.5)
    Lnh = a1 * L10h
    Lreq = s["Lh"] * 60 * N / 1e6 / a1
    Creq = P * Lreq ** (1 / n)
    rows += [
        _grp("Durée de vie"),
        _hc("Durée L10", rf"L_{{10}} = (C/P)^n = ({C:g}/{P:.6g})^{{{n:.4g}}}", L10, R["L10"], "millions de tours"),
        _hc("Durée L10h", rf"L_{{10h}} = 10^6 \times {L10:.6g}/(60 \times {N:g})", L10h, R["L10h"], "h"),
        _hc("Coefficient de fiabilité a1", rf"a_1 = (\ln(1/{F:g})/\ln(1/0{{,}}9))^{{1/1{{,}}5}}", a1, R["a1"]),
        _hc("Durée Lnh", rf"L_{{nh}} = a_1 L_{{10h}} = {a1:.6g} \times {L10h:.6g}", Lnh, R["Lnh"], "h"),
        _hc(
            "Charge de base requise",
            rf"C = P\,(60 N L_h / 10^6 / a_1)^{{1/n}} = {P:.6g} \times {Lreq:.6g}^{{1/{n:.4g}}}",
            Creq,
            R["Creq"],
            "N",
        ),
    ]
    chk += [
        _chk("Durée visée atteinte : Lnh ≥ Lh", f"Lnh = {R['Lnh']:.5g} h, Lh = {s['Lh']:g} h", R["Lnh"] >= s["Lh"]),
        _chk("Fiabilité dans le domaine usuel (90 à 99 %)", f"F = {s['F']:g} %", _lvl(90 <= s["F"] <= 99, "warn")),
    ]
    return rows, chk


def _bearingSet(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    L = [x for x in (s["L1"], s["L2"], s["L3"]) if x > 0]
    LE = sum(x**-1.5 for x in L) ** (-1 / 1.5)
    nG = int(s["nG"])
    Liso = s["LG"] * nG ** (2 / 3)
    somme = " + ".join(f"{x:g}^{{-1{{,}}5}}" for x in L)
    rows = [
        _hc("Durée de l'ensemble L_E", rf"L_E = ({somme})^{{-1/1{{,}}5}}", LE, R["LE"], "h"),
        _hc(
            "Durée de chaque roulement iso-fiable",
            rf"L = L_G\, n_G^{{2/3}} = {s['LG']:g} \times {nG}^{{2/3}}",
            Liso,
            R["Liso"],
            "h",
        ),  # fmt: skip
    ]
    chk = [
        _chk(
            "L'ensemble dure moins que son roulement le moins durable",
            f"L_E = {R['LE']:.5g} h, plus courte durée {min(L):g} h",
            R["LE"] <= min(L) * (1 + 1e-12),
        )
    ]
    return rows, chk


# ------------------------------------------------------------------------------------------------- engrenages


def _gearMesh(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    m, Z1, Z2, k = s["m"], int(s["Z1"]), int(s["Z2"]), s["k"]
    C1 = 30 * s["P"] / (math.pi * s["N"])
    d1 = m * Z1
    Ft = 2000 * C1 / d1  # C1 en N·m, d1 en mm
    Re = dm.getMaterial(s["materiau"])["Re"] / 1e6
    Rpe = Re / s["s"]
    sigma = 54 * Ft / (math.pi**2 * k * m**2)
    mMini = math.sqrt(54 * Ft / (math.pi**2 * k * Rpe))
    al = math.radians(20)
    rows = [
        _grp("Géométrie"),
        _hc("Rapport de transmission", rf"r = -Z_1/Z_2 = -{Z1}/{Z2}", -Z1 / Z2, R["r"]),
        _hc("Diamètre primitif du pignon", rf"d_1 = m Z_1 = {m:g} \times {Z1}", d1, R["d"], "mm"),
        _hc("Entraxe", rf"a = m (Z_1 + Z_2)/2 = {m:g} \times ({Z1} + {Z2})/2", m * (Z1 + Z2) / 2, R["a"], "mm"),
        _grp("Efforts sur la denture"),
        _hc(
            "Couple au pignon",
            rf"C_1 = 30 P/(\pi N) = 30 \times {s['P']:g}/(\pi \times {s['N']:g})",
            C1,
            R["C1"],
            "N·m",
        ),  # fmt: skip
        _hc("Effort tangentiel", rf"F_t = 2 C_1/d_1 = 2000 \times {C1:.6g}/{d1:g}", Ft, R["Ft"], "N"),
        _hc("Effort radial", rf"F_r = F_t \tan 20^\circ = {Ft:.6g} \tan 20^\circ", Ft * math.tan(al), R["Fr"], "N"),
        _hc("Effort normal", rf"F_n = F_t/\cos 20^\circ = {Ft:.6g}/\cos 20^\circ", Ft / math.cos(al), R["Fn"], "N"),
        _grp("Résistance en pied de dent"),
        _hc(
            "Contrainte en pied de dent",
            rf"\sigma = 54 F_t/(\pi^2 k m^2) = 54 \times {Ft:.6g}/(\pi^2 \times {k:g} \times {m:g}^2)",
            sigma,
            R["sigma"],
            "MPa",
        ),
        _hc("Résistance pratique", rf"R_{{pe}} = R_e/s = {Re:g}/{s['s']:g}", Rpe, R["Rpe"], "MPa"),
        _hc(
            "Module minimal",
            rf"m_{{min}} = \sqrt{{54 F_t/(\pi^2 k R_{{pe}})}} = \sqrt{{54 \times {Ft:.6g}/(\pi^2 \times {k:g} "
            rf"\times {Rpe:.6g})}}",
            mMini,
            R["mMini"],
            "mm",
        ),
    ]
    chk = [
        _chk(
            "Résistance du pied de dent : σ ≤ Rpe",
            f"σ = {R['sigma']:.4g} MPa, Rpe = {R['Rpe']:.4g} MPa",
            R["sigma"] <= R["Rpe"],
        ),  # fmt: skip
        _chk("Module saisi ≥ module minimal", f"m = {m:g} mm, m_min = {R['mMini']:.4g} mm", m >= R["mMini"]),
        _chk(
            "Module normalisé retenu ≥ module minimal",
            f"{R['mNorm']:g} mm pour {R['mMini']:.4g} mm",
            R["mNorm"] >= R["mMini"],
        ),  # fmt: skip
        _chk("Largeur de denture usuelle : 6 ≤ k ≤ 10", f"k = {k:g}", _lvl(6 <= k <= 10, "warn")),
        _chk("Pas d'interférence de taillage : Z1 ≥ 17 (α = 20°, sans déport)", f"Z1 = {Z1}", _lvl(Z1 >= 17, "warn")),
    ]
    return rows, chk


def _gearTrain(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    lignes = R["lignes"]
    paires = [(int(s[f"Z{i}"]), int(s[f"Z{i + 1}"])) for i in (1, 3, 5)]
    N0, P0, eta = s["N"], s["P"], s["eta"]
    C0 = 30 * P0 / (math.pi * abs(N0))
    rows = [
        _hc("Couple d'entrée", rf"C = 30 P/(\pi N) = 30 \times {P0:g}/(\pi \times {N0:g})", C0, lignes[0]["C"], "N·m")
    ]
    N = N0
    for k, (zm, zc) in enumerate(paires, start=1):
        Nk, Pk = N * (-zm / zc), P0 * eta**k
        Ck = 30 * Pk / (math.pi * abs(Nk))
        rows += [
            _grp(f"Arbre {k} (engrènement {zm}/{zc})"),
            _hc("Fréquence de rotation", rf"N_{k} = {N:.6g} \times (-{zm}/{zc})", Nk, lignes[k]["N"], "tr/min"),
            _hc("Puissance", rf"P_{k} = P\,\eta^{k} = {P0:g} \times {eta:g}^{k}", Pk, lignes[k]["P"], "W"),
            _hc(
                "Couple",
                rf"C_{k} = 30 P_{k}/(\pi |N_{k}|) = 30 \times {Pk:.6g}/(\pi \times {abs(Nk):.6g})",
                Ck,
                lignes[k]["C"],
                "N·m",
            ),  # fmt: skip
        ]
        N = Nk
    rows += [_grp("Train complet"), _hc("Rapport total", rf"r = N_{len(paires)}/N = {N:.6g}/{N0:g}", N / N0, R["r"])]
    impair = len(paires) % 2 == 1
    chk = [
        _chk("Rendement d'un engrènement dans ]0 ; 1]", f"η = {eta:g}", 0 < eta <= 1),
        _chk(
            "Sens de rotation de la sortie cohérent avec le nombre d'engrènements extérieurs",
            f"{len(paires)} engrènements, r = {R['r']:.4g} : sens {'inversé' if R['r'] < 0 else 'conservé'}",
            (R["r"] < 0) == impair,
        ),
        _chk(
            "Pignons sans interférence de taillage : Z menant ≥ 17 (α = 20°, sans déport)",
            ", ".join(f"Z{2 * i + 1} = {zm}" for i, (zm, _) in enumerate(paires)),
            _lvl(min(zm for zm, _ in paires) >= 17, "warn"),
        ),
    ]
    return rows, chk


# ------------------------------------------------------------------------------------------- trains épicycloïdaux


def _planetary(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    Z1, Z21, Z22, Z4, nSat = (int(s[k]) for k in ("Z1", "Z21", "Z22", "Z4", "nSat"))
    rb = -Z1 * Z22 / (Z21 * Z4)
    Ne = s["Ne"]
    # Willis ω_c − ω_PS = rb·(ω_p − ω_PS) résolue à la main pour chaque couple (bloqué, entrée)
    formes = {
        ("porte-satellites", "planétaire"): (rb * Ne, rf"\omega_c = r_b\,\omega_p = {rb:.6g} \times {Ne:g}"),
        ("porte-satellites", "couronne"): (Ne / rb, rf"\omega_p = \omega_c/r_b = {Ne:g}/({rb:.6g})"),
        ("planétaire", "couronne"): (Ne / (1 - rb), rf"\omega_{{PS}} = \omega_c/(1 - r_b) = {Ne:g}/(1 - ({rb:.6g}))"),
        ("planétaire", "porte-satellites"): (
            Ne * (1 - rb),
            rf"\omega_c = \omega_{{PS}}(1 - r_b) = {Ne:g} \times (1 - ({rb:.6g}))",
        ),
        ("couronne", "planétaire"): (
            rb * Ne / (rb - 1),
            rf"\omega_{{PS}} = r_b\,\omega_p/(r_b - 1) = ({rb:.6g}) \times {Ne:g}/({rb:.6g} - 1)",
        ),
        ("couronne", "porte-satellites"): (
            Ne * (rb - 1) / rb,
            rf"\omega_p = \omega_{{PS}}(r_b - 1)/r_b = {Ne:g} \times ({rb:.6g} - 1)/({rb:.6g})",
        ),
    }
    ws, lat = formes[(s["bloque"], s["entree"])]
    sortie = next(x for x in ("planétaire", "couronne", "porte-satellites") if x not in (s["bloque"], s["entree"]))
    v = R["vitesses"]
    rows = [
        _hc(
            "Raison basique",
            rf"r_b = -Z_1 Z_{{22}}/(Z_{{21}} Z_4) = -{Z1} \times {Z22}/({Z21} \times {Z4})",
            rb,
            R["rb"],
        ),  # fmt: skip
        _hc(f"Vitesse de sortie ({sortie})", lat, ws, v[sortie], "tr/min"),
        _hc("Rapport de réduction", rf"r = \omega_{{sortie}}/\omega_{{entrée}} = {ws:.6g}/{Ne:g}", ws / Ne, R["r"]),
    ]
    residu = (v["couronne"] - v["porte-satellites"]) - R["rb"] * (v["planétaire"] - v["porte-satellites"])
    haricot = (Z1 + Z4) / nSat
    chk = [
        _chk(
            "Relation de Willis vérifiée par les vitesses du solveur",
            f"résidu {residu:.3g} tr/min",
            abs(residu) <= 1e-9 * max(1.0, abs(Ne)),
        ),  # fmt: skip
        _chk("Entraxes : Z4 = Z1 + Z21 + Z22", f"Z4 = {Z4}, Z1 + Z21 + Z22 = {Z1 + Z21 + Z22}", Z4 == Z1 + Z21 + Z22),
        _chk(
            "Règle du haricot : (Z1 + Z4)/n_sat entier",
            f"({Z1} + {Z4})/{nSat} = {haricot:.4g}",
            abs(haricot - round(haricot)) < 1e-9,
        ),  # fmt: skip
    ]
    return rows, chk


# --------------------------------------------------------------------------------------- freins et embrayages


def _brake(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    T = res["tables"]["Synthèse"].set_index("Loi")
    F, f, n, Re, Ri = s["F"], s["f"], s["n"], s["Re"], s["Ri"]
    w = 2 * math.pi * s["N"] / 60
    A = math.pi * (Re**2 - Ri**2)
    lois = [
        (
            "pression constante",
            n * f * F * (2 / 3) * (Re**3 - Ri**3) / (Re**2 - Ri**2) / 1000,
            rf"C_f = \tfrac{{2}}{{3}} n f F \tfrac{{R_e^3 - R_i^3}}{{R_e^2 - R_i^2}} = \tfrac{{2}}{{3}} \times {n:g} "
            rf"\times {f:g} \times {F:g} \times \tfrac{{{Re:g}^3 - {Ri:g}^3}}{{{Re:g}^2 - {Ri:g}^2}} \times 10^{{-3}}",
            R["Cp"],
            F / A,
            rf"p = F/(\pi (R_e^2 - R_i^2)) = {F:g}/(\pi ({Re:g}^2 - {Ri:g}^2))",
        ),
        (
            "usure constante",
            n * f * F * (Re + Ri) / 2 / 1000,
            rf"C_f = n f F (R_e + R_i)/2 = {n:g} \times {f:g} \times {F:g} \times ({Re:g} + {Ri:g})/2 \times 10^{{-3}}",
            R["Cu"],
            F / (2 * math.pi * Ri * (Re - Ri)),
            rf"p_{{max}} = F/(2\pi R_i (R_e - R_i)) = {F:g}/(2\pi \times {Ri:g} \times ({Re:g} - {Ri:g}))",
        ),
    ]
    rows = []
    for loi, Cf, latC, solC, p, latP in lois:
        ps = abs(Cf) * w / (n * A)
        rows += [
            _grp(f"Loi : {loi}"),
            _hc("Couple de freinage", latC, Cf, solC, "N·m"),
            # le tableau du solveur arrondit p à 4 décimales et la puissance spécifique à 6
            _hc("Pression de contact maxi", latP, p, T.loc[loi, "Pression maxi (MPa)"], "MPa", 6e-5),
            _hc(
                "Puissance spécifique moyenne",
                rf"C_f \omega/(n \pi (R_e^2 - R_i^2)) = {Cf:.6g} \times {w:.6g}/({n:g} \times {A:.6g})",
                ps,
                T.loc[loi, "Puissance spécifique (W/mm²)"],
                "W/mm²",
                6e-7,
            ),
        ]
    chk = [
        _chk("Rayons cohérents : 0 < Ri < Re", f"Ri = {Ri:g} mm, Re = {Re:g} mm", 0 < Ri < Re),
        _chk(
            "Usure constante plus prudente : Cf(usure) ≤ Cf(pression)",
            f"{R['Cu']:.5g} N·m pour {R['Cp']:.5g} N·m",
            R["Cu"] <= R["Cp"],
        ),  # fmt: skip
        _chk(
            "Puissance spécifique à comparer à la limite du fabricant de la garniture",
            f"{abs(R['Cp']) * w / (n * A):.4g} W/mm² en pression constante (limite non fournie)",
            "warn",
        ),
    ]
    return rows, chk


def _clutch(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    JR, ts = s["JR"], s["ts"]
    w = 2 * math.pi * s["NM"] / 60
    CR = abs(s["CR"])
    Cacc = JR * w / ts
    CT = CR + Cacc
    t = JR * w / (CT - CR)
    E = CT * w * t / 2
    rows = [
        _hc(
            "Couple d'accélération du récepteur",
            rf"J_R \omega_M/t_s = {JR:g} \times {w:.6g}/{ts:g}",
            Cacc,
            R["Cacc"],
            "N·m",
        ),  # fmt: skip
        _hc("Couple d'embrayage", rf"C_T = |C_R| + J_R \omega_M/t_s = {CR:g} + {Cacc:.6g}", CT, R["CT"], "N·m"),
        _hc(
            "Durée de synchronisation",
            rf"t = J_R \omega_M/(C_T - |C_R|) = {JR:g} \times {w:.6g}/({CT:.6g} - {CR:g})",
            t,
            R["t"],
            "s",
        ),  # fmt: skip
        _hc(
            "Énergie dissipée par manœuvre",
            rf"E = C_T \omega_M t/2 = {CT:.6g} \times {w:.6g} \times {t:.6g}/2",
            E,
            R["E"],
            "J",
        ),  # fmt: skip
        _hc(
            "Puissance moyenne dissipée",
            rf"P = E \times {s['cadence']:g}/3600",
            E * s["cadence"] / 3600,
            R["Pmoy"],
            "W",
        ),  # fmt: skip
    ]
    chk = [
        _chk(
            "Couple d'embrayage fourni par le moteur : CT ≤ CM",
            f"CT = {R['CT']:.4g} N·m, CM = {s['CM']:g} N·m",
            R["CT"] <= s["CM"],
        ),  # fmt: skip
        _chk("Couple résistant opposé au mouvement : CR ≤ 0", f"CR = {s['CR']:g} N·m", _lvl(s["CR"] <= 0, "warn")),
    ]
    return rows, chk


# ------------------------------------------------------------------------------------- dimensionnement moteur


def _motor(s: dict, res: dict, dm) -> tuple[list[dict], list[tuple]]:
    R = res["result"]
    ph = [(C, t) for C, t in ((s["Ca"], s["ta"]), (s["Cc"], s["tc"]), (s["Cfr"], s["tfr"])) if t > 0]
    duree = sum(t for _, t in ph)
    Cth = math.sqrt(sum(C**2 * t for C, t in ph) / duree)
    somme = " + ".join(f"{C:g}^2 \\times {t:g}" for C, t in ph)
    rows = [
        _hc("Couple équivalent thermique", rf"C_{{th}} = \sqrt{{({somme})/{duree:g}}}", Cth, R["Cth"], "N·m"),
        _hc("Couple de pointe", r"C_{pointe} = \max |C_i|", max(abs(C) for C, _ in ph), R["Cpointe"], "N·m"),
        _hc(
            "Inertie ramenée à l'arbre moteur",
            rf"J = J_m + J_s/r_s^2 = {s['Jm']:g} + {s['Js']:g}/{s['rs']:g}^2",
            s["Jm"] + s["Js"] / s["rs"] ** 2,
            R["J"],
            "kg·m²",
        ),  # fmt: skip
    ]
    chk = [
        _chk(
            "Couple nominal ≥ couple équivalent thermique",
            f"Cn = {s['Cn']:g} N·m, C_th = {R['Cth']:.4g} N·m",
            s["Cn"] >= R["Cth"],
        ),  # fmt: skip
        _chk(
            "Couple maxi ≥ couple de pointe",
            f"Cmax = {s['Cmax']:g} N·m, pointe {R['Cpointe']:g} N·m",
            s["Cmax"] >= R["Cpointe"],
        ),  # fmt: skip
        _chk(
            "Vitesse maxi ≥ vitesse requise",
            f"Nmax = {s['Nmax']:g} tr/min, requise {s['Nreq']:g} tr/min",
            s["Nmax"] >= s["Nreq"],
        ),  # fmt: skip
    ]
    return rows, chk


# ---------------------------------------------------------------------------------------------- catalogue


def _sansTable(s: dict) -> bool:
    return not s["tableau"]


TYPES = {
    "bearing": {
        "calc": _bearing,
        "champs": [
            ("Fr", "Charge radiale Fr", "N"),
            ("Fa", "Charge axiale Fa", "N"),
            ("N", "Fréquence de rotation", "tr/min"),
            ("type", "Éléments roulants", ""),
            ("C", "Charge dynamique de base C", "N"),
            ("C0", "Charge statique de base C0", "N"),
            ("tableau", "e et Y dans la table du cours (billes à contact radial)", ""),
            ("e", "e", "", None, _sansTable),
            ("X", "X", "", None, _sansTable),
            ("Y", "Y", "", None, _sansTable),
            ("F", "Fiabilité F", "%"),
            ("Lh", "Durée visée Lh", "h"),
        ],
        "hyp": [
            "Charges Fr et Fa constantes en intensité et en direction (sinon charge moyenne équivalente du cycle).",
            "Fréquence de rotation N constante.",
            "Lubrification, étanchéité et température normales : la durée de base L10 (fiabilité 90 %) n'est "
            "corrigée que par a1.",
            "C, C0 (et e, X, Y s'ils sont saisis) lus dans le catalogue du constructeur pour le roulement choisi.",
            "Table du cours : roulements à billes à contact radial, interpolée linéairement en Fa/C0.",
        ],
    },
    "bearingSet": {
        "calc": _bearingSet,
        "champs": [
            ("L1", "Durée du roulement 1", "h"),
            ("L2", "Durée du roulement 2", "h"),
            ("L3", "Durée du roulement 3 (0 = absent)", "h"),
            ("LG", "Durée du guidage LG", "h"),
            ("nG", "Nombre de roulements iso-fiables", ""),
        ],
        "hyp": [
            "Roulements en série : la défaillance d'un seul met l'ensemble hors service.",
            "Durées de chaque roulement données à la même fiabilité (90 %).",
            "Loi de Weibull d'exposant 1,5 (cours) pour combiner les durées.",
        ],
    },
    "gearMesh": {
        "calc": _gearMesh,
        "champs": [
            ("m", "Module m", "mm"),
            ("Z1", "Dents du pignon Z1", ""),
            ("Z2", "Dents de la roue Z2", ""),
            ("P", "Puissance au pignon P", "W"),
            ("N", "Fréquence de rotation du pignon", "tr/min"),
            ("k", "Largeur de denture k = b/m", ""),
            ("materiau", "Matériau du pignon", ""),
            ("s", "Coefficient de sécurité sur l'effort s", ""),
        ],
        "hyp": [
            "Denture droite, profil en développante normalisé, angle de pression α = 20°, sans déport.",
            "Effort transmis par une seule dent ; dent assimilée à une poutre encastrée au pied (formule du cours).",
            "Couple constant : ni choc, ni coefficient de service, ni rendement dans les efforts.",
            "Re du matériau de la base : valeur moyenne, à minorer selon l'état de livraison.",
        ],
    },
    "gearTrain": {
        "calc": _gearTrain,
        "champs": [
            ("P", "Puissance d'entrée P", "W"),
            ("N", "Fréquence de rotation d'entrée", "tr/min"),
            ("eta", "Rendement d'un engrènement η", ""),
            *((f"Z{i}", f"Dents {'menant' if i % 2 else 'mené'} Z{i}", "") for i in range(1, 7)),
        ],
        "hyp": [
            "Trois engrènements extérieurs en série ; chaque arbre intermédiaire porte la roue menée et le pignon "
            "menant suivant.",
            "Même rendement η pour chaque engrènement (pertes des paliers comprises ou négligées).",
            "Régime permanent : pas de couple d'inertie.",
        ],
    },
    "planetary": {
        "calc": _planetary,
        "champs": [
            ("Z1", "Planétaire Z1", ""),
            ("Z21", "Satellite engrenant le planétaire Z21", ""),
            ("Z22", "Satellite engrenant la couronne Z22", ""),
            ("Z4", "Couronne Z4", ""),
            ("nSat", "Nombre de satellites", ""),
            ("bloque", "Élément bloqué", ""),
            ("entree", "Élément d'entrée", ""),
            ("Ne", "Fréquence de rotation de l'entrée", "tr/min"),
        ],
        "hyp": [
            "Train plan à un étage : planétaire, satellites et couronne à denture intérieure (un engrènement "
            "extérieur, d'où le signe de rb).",
            "Même module pour toutes les dentures, sans déport (condition des entraxes).",
            "Satellites identiques et également répartis (règle du haricot).",
            "Vitesses en régime permanent ; rendement non pris en compte.",
        ],
    },
    "brake": {
        "calc": _brake,
        "champs": [
            ("F", "Effort presseur F par surface", "N"),
            ("f", "Coefficient de frottement f", ""),
            ("n", "Nombre de surfaces frottantes n", ""),
            ("Ri", "Rayon intérieur Ri", "mm"),
            ("Re", "Rayon extérieur Re", "mm"),
            ("N", "Fréquence de rotation du disque au freinage", "tr/min"),
        ],
        "hyp": [
            "Contact plan sur une couronne de rayons Ri et Re ; même effort presseur F sur chacune des n surfaces.",
            "Coefficient de frottement f constant (indépendant de la vitesse et de la température).",
            "Pression constante : garniture neuve ; usure constante : garniture rodée (couple le plus faible).",
            "Puissance dissipée calculée à la vitesse du début du freinage (valeur maxi).",
        ],
    },
    "clutch": {
        "calc": _clutch,
        "champs": [
            ("CM", "Couple moteur CM", "N·m"),
            ("NM", "Fréquence de rotation du moteur", "tr/min"),
            ("JR", "Inertie du récepteur JR", "kg·m²"),
            ("CR", "Couple résistant CR (négatif)", "N·m"),
            ("ts", "Durée de synchronisation visée", "s"),
            ("cadence", "Cadence", "manœuvres/h"),
        ],
        "hyp": [
            "Vitesse du moteur constante pendant la synchronisation (modèle du cours) : l'inertie du moteur "
            "n'intervient pas.",
            "Couple d'embrayage CT et couple résistant CR constants pendant le glissement.",
            "Énergie de glissement entièrement dissipée dans l'embrayage.",
        ],
    },
    "motor": {
        "calc": _motor,
        "champs": [
            ("Ca", "Couple en accélération Ca", "N·m"),
            ("ta", "Durée de l'accélération", "s"),
            ("Cc", "Couple en régime établi Cc", "N·m"),
            ("tc", "Durée du régime établi", "s"),
            ("Cfr", "Couple au freinage", "N·m"),
            ("tfr", "Durée du freinage", "s"),
            ("Cn", "Couple nominal", "N·m"),
            ("Cmax", "Couple maxi", "N·m"),
            ("Nmax", "Vitesse maxi", "tr/min"),
            ("Nreq", "Vitesse requise par le cahier des charges", "tr/min"),
            ("Jm", "Inertie du moteur Jm", "kg·m²"),
            ("Js", "Inertie de la charge ramenée à sa sortie Js", "kg·m²"),
            ("rs", "Rapport de réduction vers la sortie", ""),
        ],
        "hyp": [
            "Cycle répétitif, durées des phases représentatives du fonctionnement réel (le cours ne les donne pas).",
            "Échauffement du moteur proportionnel au couple quadratique moyen (pertes Joule en C²).",
            "Pas de phase d'arrêt dans le cycle (sinon l'ajouter avec un couple nul).",
            "Rapport de réduction rs = vitesse du moteur / vitesse de la sortie.",
        ],
    },
}


# ------------------------------------------------------------------------------------------------ assemblage


def _hypHTML(hyp: list[str], chk: list[tuple]) -> tuple[str, int, int]:
    """Hypothèses (avis du relecteur) et contrôles d'applicabilité d'un calcul ; renvoie (html, nWarn, nKo)."""
    h = "<p><strong>Hypothèses du modèle (à valider)</strong></p>"
    h += "<table><tr><th>Hypothèse</th><th>Avis du relecteur</th></tr>"
    h += "".join(f'<tr><td>{_esc(x)}</td><td class="rv">{_CHOIX}</td></tr>' for x in hyp) + "</table>"
    h += "<p><strong>Contrôles d'applicabilité faits par le logiciel</strong></p>"
    h += "<table><tr><th>Contrôle</th><th>Valeurs</th><th>Résultat</th></tr>"
    etats = {
        "ok": '<span class="ok">satisfait</span>',
        "warn": '<span class="warn">point d\'attention</span>',
        "ko": '<span class="ko">NON satisfait</span>',
    }
    h += "".join(f"<tr><td>{_esc(t)}</td><td>{_esc(d)}</td><td>{etats[e]}</td></tr>" for t, d, e in chk)
    return h + "</table>", sum(e == "warn" for *_, e in chk), sum(e == "ko" for *_, e in chk)


def _handTable(rows: list[dict]) -> tuple[str, int, int]:
    """Tableau des contrôles à la main (même présentation que validation_report) ; renvoie (html, nOK, nTot)."""
    h = (
        '<table class="hand"><tr><th>Grandeur</th><th>Formule avec valeurs</th><th>Valeur à la main</th>'
        "<th>Valeur solveur</th><th>Écart</th><th>Verdict</th></tr>"
    )
    nOK = nTot = 0
    for r in rows:
        if r["hand"] is None:
            h += f'<tr><td colspan="6" class="grp">{_esc(r["label"])}</td></tr>'
            continue
        nTot += 1
        d, ok = _verdict(r)
        nOK += ok
        v = '<span class="ok">concordent</span>' if ok else '<span class="ko">ÉCART</span>'
        un = f" {_esc(r['unit'])}" if r["unit"] else ""
        h += (
            f'<tr><td>{_esc(r["label"])}</td><td class="fm">{_mj(r["latex"])}</td>'
            f'<td class="n">{r["hand"]:.8g}{un}</td><td class="n">{r["solver"]:.8g}{un}</td>'
            f'<td class="n">{d:.2g}</td><td>{v}</td></tr>'
        )
    return h + "</table>", nOK, nTot


def generate(titre: str, calculs: list[tuple[str, str, dict, dict | None]], dm) -> str:
    """Dossier de validation (HTML autonome) d'une page de cours, ses calculs à jour réunis en un seul fichier.

    Entrées : titre de la page ; calculs = [(titre du calcul, type (clé de TYPES), saisie, résultat de compute* ou
    None s'il n'est pas à jour)] ; dm (base de matériaux, Re des engrenages). Sortie : texte HTML.
    Les formules demandent MathJax (Internet).
    """
    parts = {i: "" for i, _ in _SECTIONS}
    parts["verif"] = (
        "<p>Pour chaque grandeur, la formule du cours est écrite avec les valeurs de ce problème, calculée à la main "
        "(sans appeler le solveur) puis comparée à la valeur du solveur.</p>"
    )
    parts["diagrammes"] = '<p class="muted">Les schémas sont sur la page de calcul ; ce dossier ne les reprend pas.</p>'
    parts["avis"] = _reviewHTML()
    nOK = nTot = nWarn = nKo = 0
    statuts = []
    for nom, typ, s, res in calculs:
        T = TYPES[typ]
        tete = f"<h3>{_esc(nom)}</h3>"
        if res is None:
            for i in ("donnees", "hypotheses", "verif", "resultats", "rapport", "formules"):
                parts[i] += tete + _NON_INCLUS
            continue
        statuts.append(res["status"])
        try:
            rows, chk = T["calc"](s, res, dm)
        except Exception as err:  # un contrôle impossible ne doit pas empêcher le dossier ; il compte comme échec
            rows, chk = [], [_chk("Contrôles à la main exécutés", str(getattr(err, "message", err)), "ko")]
        hyp, w, k = _hypHTML(T["hyp"], chk)
        hand, ok, tot = _handTable(rows)
        nOK, nTot, nWarn, nKo = nOK + ok, nTot + tot, nWarn + w, nKo + k
        formules = "".join(f'<div class="eq">{_mj(x)}</div>' for x in res["result"]["latex"])
        parts["donnees"] += _kv(nom, _champs(s, T["champs"]))
        parts["hypotheses"] += tete + hyp
        parts["verif"] += tete + hand
        parts["resultats"] += tete + "".join(
            f"<p><strong>{_esc(t)}</strong></p>{_tableHTML(df)}" for t, df in res["tables"].items()
        )
        parts["rapport"] += tete + _reportHTML(res["result"]["rapport"])
        parts["formules"] += tete + (
            f'<div class="eqblock">{formules}</div>'
            if formules
            else '<p class="muted">Pas de formule écrite par le solveur pour ce calcul : voir le §3.</p>'
        )
    sections = [{"id": i, "titre": t, "titre_court": t.split(". ", 1)[1], "html": parts[i]} for i, t in _SECTIONS]
    return _template().render(
        titre=titre,
        date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        python=platform.python_version(),
        statut=" ; ".join(statuts),
        bilan=_bilan(nOK, nTot, nWarn, nKo),
        erreurs=[],
        sections=sections,
    )


def fileName(titre: str, now: datetime | None = None) -> str:
    """Nom du fichier proposé au téléchargement : Validation_<titre sans accents>_AAAAMMJJ_HHMMSS.html."""
    now = now or datetime.now()
    ascii_ = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode()
    return f"Validation_{re.sub(r'[^A-Za-z0-9]+', '_', ascii_).strip('_')}_{now:%Y%m%d_%H%M%S}.html"
