"""Services Poutres 2/2 : Eurocode 3, fatigue, profilé le plus léger, charge mobile (étape E19).

Port de MecaStruct_App.m (useSectionForBeam, checkEurocode, checkFatigue, findLightestProfile, computeMovingLoad,
loadFromBeam, sendToTensor). Les fonctions prennent la saisie de l'onglet Poutres (unités d'affichage) et ne
modifient jamais leur entrée. Le dossier de validation et l'interface sont hors de ce module.
"""

import copy
import math
import re

import numpy as np
import pandas as pd

from mecastruct.core import design_checks, geometry
from mecastruct.core.beam_solver import solveBeam
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import ppEval
from mecastruct.core.units import fromSI, toSI
from mecastruct.services.beam_services import _okText, buildBeamModel, computeBeam, computeCombinations

_ID = "MecaStruct:App:invalidInput"
_EPS = np.finfo(float).eps  # eps de MATLAB, utilisé pour éviter une division par zéro sur la flèche


def _maxAbs(*vals: float) -> float:
    """Maximum des valeurs absolues hors NaN (NaN si aucune), comme max de MATLAB."""
    v = [abs(x) for x in vals if not math.isnan(x)]
    return max(v) if v else math.nan


def _kvTable(rows: list[tuple]) -> pd.DataFrame:
    """Tableau Grandeur / Valeur / Unité ; valeurs mises en forme comme kvTable (%.6g, verdicts en français)."""
    data = []
    for label, value, unit in rows:
        if isinstance(value, (bool, np.bool_)):
            text = _okText(bool(value))
        elif isinstance(value, (int, float, np.integer, np.floating)):
            text = "NaN" if math.isnan(value) else ("Inf" if math.isinf(value) else f"{value:.6g}")
        else:
            text = str(value)
        data.append((label, text, unit))
    return pd.DataFrame(data, columns=["Grandeur", "Valeur", "Unité"])


def _parseNumbers(txt: str, what: str) -> np.ndarray:
    """Liste de nombres séparés par des espaces, virgules ou points-virgules (« 100 100, 50 »).

    Erreur : MecaStruct:App:invalidInput si un élément n'est pas un nombre fini (la virgule décimale n'est pas admise).
    """
    parts = re.sub(r"[;,]+", " ", str(txt)).split()
    try:
        v = np.array([float(p) for p in parts])
    except ValueError:
        v = np.array([math.nan])
    if not np.all(np.isfinite(v)):
        raise MecaStructError(_ID, f"{what} : liste de nombres invalide (« {txt} »).")
    return v


def sectionToBeamInput(saisie: dict, sec: dict, P: dict, material: dict | None) -> dict:
    """= useSectionForBeam : copie S, Iz, Iy, Ix (J), Iyz, ky, kz, vy, vz (unités d'affichage) et sec.

    Entrées : `saisie` (BEAM_INPUT_DOC) ; `sec` (section de l'onglet Sections, geometry.fromProfile) ; `P` (propriétés
    analytiques de sec, geometry.analytical) ; `material` (dict de DataManager.getMaterial, ou None pour garder le
    matériau de la saisie). Profilé du catalogue : S, Iz, Iy, ky, kz et fibres extrêmes sont tabulés
    (geometry.tabulated), car la géométrie simplifiée ignore les congés ; la section n'est alors pas redessinée
    (secTabulated = vrai).
    Sortie : nouvelle saisie (copie) ; `section` reçoit sec.
    """
    out = copy.deepcopy(saisie)
    tabulated = sec["type"] == "profile"
    if tabulated:
        Pt = geometry.tabulated(sec)
        P = {**P, **{f: Pt[f] for f in ("S", "Iz", "Iy", "ky", "kz", "vyTop", "vyBot", "vzRight", "vzLeft")}}
    J = P["J"] if math.isfinite(P["J"]) and P["J"] > 0 else P["Ix"]
    ky = P["ky"] if math.isfinite(P["ky"]) and P["ky"] > 0 else 1.0
    kz = P["kz"] if math.isfinite(P["kz"]) and P["kz"] > 0 else ky
    out.update(
        {
            "S": fromSI(P["S"], "mm^2"),
            "Iz": fromSI(P["Iz"], "mm^4"),
            "Iy": fromSI(P["Iy"], "mm^4"),
            "Ix": fromSI(J, "mm^4"),
            "Iyz": fromSI(P["Iyz"], "mm^4"),
            "ky": ky,
            "kz": kz,
            "vy": fromSI(max(P["vyTop"], P["vyBot"]), "mm"),
            "vz": fromSI(max(P["vzRight"], P["vzLeft"]), "mm"),
            "section": sec,
            "secTabulated": tabulated,
        }
    )
    if material is not None:
        out.update(
            {
                "mat": material["Name"],
                "E": fromSI(material["E"], "GPa"),
                "G": fromSI(material["G"], "GPa"),
                "Re": fromSI(material["Re"], "MPa"),
            }
        )
    return out


def checkEurocode(saisie: dict, dm: DataManager, source: str = "poutre") -> tuple[dict, pd.DataFrame]:
    """Vérification Eurocode 3 simplifiée (ec3Bending) de la poutre, avec efforts « poutre » ou « enveloppe ».

    Entrées : `saisie` (BEAM_INPUT_DOC, section importée obligatoire) ; `dm` ; `source` : 'poutre' (tous les cas à 1)
    ou 'enveloppe' (enveloppe des combinaisons, ligne Enveloppe de computeCombinations).
    Sortie : (r, T) : r dict des vérifications (class, W, ltb, axial, buck, inter, web, okAll, MEd, VEd, ratioM…),
    T tableau Grandeur / Valeur / Unité.
    Erreur : MecaStruct:App:invalidInput si la section n'est pas un profilé ou un profil en I, ou source inconnue.
    """
    sec = saisie.get("section")
    if sec is None:
        raise MecaStructError(
            _ID,
            "Eurocode 3 : la section doit venir d'un profilé ou d'un profil en I (importée depuis Sections ou "
            "exemple), pas de valeurs saisies à la main.",
        )
    d = design_checks.ibeamDims(sec)
    if source == "enveloppe":
        c = computeCombinations(saisie, dm).iloc[-1]
        MEd = _maxAbs(c["Mfz max (kN·m)"], c["Mfz min (kN·m)"]) * 1e3
        VEd = _maxAbs(c["Ty max (kN)"], c["Ty min (kN)"]) * 1e3
        Nmax, Nmin = c["N max (kN)"] * 1e3, c["N min (kN)"] * 1e3
        src = "enveloppe des combinaisons"
        ignored = ""
    elif source == "poutre":
        e = computeBeam(saisie, dm)["sol"]["extrema"]
        MEd = _maxAbs(e["Mfz"]["max"], e["Mfz"]["min"])
        VEd = _maxAbs(e["Ty"]["max"], e["Ty"]["min"])
        Nmax, Nmin = e["N"]["max"], e["N"]["min"]
        src = "poutre recalculée avec la saisie actuelle (tous les cas à 1)"
        My = _maxAbs(e["Mfy"]["max"], e["Mfy"]["min"]) / 1e3
        ignored = f"Mfy max = {My:.4g} kN·m (flexion déviée non prise en compte)" if My > 1e-6 else ""
    else:
        raise MecaStructError(_ID, f"Eurocode 3 : source « {source} » inconnue (attendu : poutre ou enveloppe).")

    NEd = _maxAbs(Nmax, Nmin)  # N > 0 : traction ; on associe le N maximal au M maximal (prudent)
    Ncomp = max(0.0, -Nmin)
    fy = toSI(saisie["Re"], "MPa")
    gM0, gM1 = saisie["gM0"], saisie["gM1"]
    A = toSI(saisie["S"], "mm^2")
    Iz = toSI(saisie["Iz"], "mm^4")
    Iy = toSI(saisie["Iy"], "mm^4")
    Ix = toSI(saisie["Ix"], "mm^4")
    E = toSI(saisie["E"], "GPa")
    G = toSI(saisie["G"], "GPa")
    rolled = sec["type"] == "profile"

    r = design_checks.ec3Bending(d, A, Iz, fy, gM0, MEd, VEd, Ncomp)
    Lcr = saisie["Lcr"] if saisie["Lcr"] > 0 else saisie["L"]
    LcrF = saisie["LcrF"] if saisie["LcrF"] > 0 else saisie["L"]  # plan fort : les entretoises ne le réduisent pas
    ltb = design_checks.ec3LateralTorsional(d, rolled, r["W"], fy, gM1, E, G, Iy, Ix, Lcr, saisie["C1"], MEd)
    r["ltb"] = ltb
    r["axial"] = design_checks.ec3AxialBending(d, r, A, fy, gM0, NEd, MEd)
    r["buck"] = None
    if Ncomp > 0:
        r["buck"] = design_checks.ec3FlexuralBuckling(d, rolled, A, Iz, Iy, [LcrF, Lcr], fy, E, gM1, Ncomp)
    r["inter"] = None
    if Ncomp > 0 and MEd > 0 and r["class"]["class"] <= 3:
        r["inter"] = design_checks.ec3Interaction(
            r["class"]["class"], r["buck"], ltb, A, r["W"], fy, gM1, Ncomp, MEd, saisie["Cmy"], saisie["CmLT"]
        )
    r["web"] = design_checks.ec3WebShear(d, fy, gM1, VEd)
    r["partial"] = False
    r["Ncomp"] = Ncomp  # compression retenue pour la classe (le dossier la refait à la main)
    r["okAll"] = bool(
        r["ok"]
        and ltb["ok"]
        and r["axial"]["ok"]
        and (r["buck"] is None or r["buck"]["ok"])
        and (r["inter"] is None or r["inter"]["ok"])
        and r["web"]["ok"]
    )
    rows = _ec3Rows(r, d, src, fy, saisie, Lcr, LcrF, NEd)
    sol = solveBeam(buildBeamModel(saisie, dm))
    if not sol["isostatic"] and sol["model"]["Iyz"] != 0:
        rows.append(
            ("Résultats non fiables", "poutre hyperstatique avec Iyz ≠ 0 : réactions et efforts plan par plan", "")
        )
    if ignored:
        rows.append(("Efforts ignorés", ignored, ""))
    return r, _kvTable(rows)


def _ec3Rows(r: dict, d: dict, src: str, fy: float, saisie: dict, Lcr: float, LcrF: float, NEd: float) -> list[tuple]:
    """Lignes du tableau Eurocode 3 (libellés et clauses de MecaStruct_App.m, checkEurocode)."""
    cl, ltb, ax = r["class"], r["ltb"], r["axial"]
    rows = [
        ("Efforts utilisés", src, ""),
        ("fy = Re (EN 1993-1-1 tab. 3.1 : fy dépend de l'épaisseur, non pris en compte)", fy / 1e6, "MPa"),
        ("γM0 [EN 1993-1-1 §6.1(1), valeur recommandée 1,0]", saisie["gM0"], "-"),
        ("Classe de l'aile (c/tf) [tab. 5.2 : 9ε, 10ε, 14ε]", f"{cl['classFlange']} ({cl['ratioFlange']:.2f})", ""),
        ("Classe de l'âme (c/tw) [tab. 5.2 : 72ε, 83ε, 124ε]", f"{cl['classWeb']} ({cl['ratioWeb']:.2f})", ""),
        ("Classe de la section [§5.5]", cl["class"], "-"),
        ("Wpl,y", r["Wpl"] * 1e6, "cm³"),
        ("Wel,y", r["Wel"] * 1e6, "cm³"),
        ("Mc,Rd = W·fy/γM0 [§6.2.5(2), éq. 6.13 / 6.14]", r["Mc"] / 1e3, "kN·m"),
        ("Av [§6.2.6(3)]", r["Av"] * 1e6, "mm²"),
        ("Vpl,Rd = Av·(fy/√3)/γM0 [§6.2.6(2), éq. 6.18]", r["Vpl"] / 1e3, "kN"),
        ("MEd", r["MEd"] / 1e3, "kN·m"),
        ("VEd", r["VEd"] / 1e3, "kN"),
        ("Moment réduit par le tranchant, VEd > 0,5 Vpl,Rd [§6.2.8]", "oui" if r["reduced"] else "non", ""),
        ("MEd / MRd [éq. 6.12]", r["ratioM"], "-"),
        ("VEd / Vpl,Rd [éq. 6.17]", r["ratioV"], "-"),
        ("Résistance des sections", r["ok"], ""),
        ("Lcr (entretoises : flambement faible et déversement)", Lcr, "m"),
        ("Lcr,y (flambement dans le plan fort ; 0 = L)", LcrF, "m"),
        ("Mcr [NCCI SN003, appuis à fourches]", ltb["Mcr"] / 1e3, "kN·m"),
        ("λ̄LT = √(W·fy/Mcr) [§6.3.2.2]", ltb["lambda"], "-"),
        (f"Courbe {ltb['curve']}, αLT [tab. 6.5 puis tab. 6.3]", ltb["alpha"], "-"),
        ("χLT [§6.3.2.3, éq. 6.57, λ̄LT,0 = 0,4, β = 0,75]", ltb["chi"], "-"),
        ("Mb,Rd = χLT·W·fy/γM1 [éq. 6.55]", ltb["MbRd"] / 1e3, "kN·m"),
        ("MEd / Mb,Rd [éq. 6.54]", ltb["ratio"], "-"),
        ("Déversement", ltb["ok"], ""),
        ("NEd (traction ou compression, au maximum)", NEd / 1e3, "kN"),
        ("Npl,Rd = A·fy/γM0 [§6.2.4, éq. 6.6]", ax["Npl"] / 1e3, "kN"),
    ]
    if ax["class12"]:
        rows += [
            ("n = NEd/Npl,Rd ; a = (A − 2b·tf)/A ≤ 0,5 [§6.2.9.1(5)]", f"n = {ax['n']:.3f} ; a = {ax['a']:.3f}", ""),
            (
                "MN,y,Rd = Mpl,y,Rd·(1 − n)/(1 − 0,5a) [éq. 6.36, sans réduction si 6.33 et 6.34]",
                ax["MNRd"] / 1e3,
                "kN·m",
            ),
            ("MEd / MN,y,Rd", ax["ratio"], "-"),
        ]
    else:
        rows += [
            ("σx,Ed = NEd/A + MEd/Wel [§6.2.9.2, éq. 6.42]", ax["sigma"] / 1e6, "MPa"),
            ("σx,Ed / (fy/γM0)", ax["ratio"], "-"),
        ]
    rows.append(("Flexion + effort normal", ax["ok"], ""))
    if r["buck"] is not None:
        for a in r["buck"]["axes"]:
            rows += [
                (f"Flambement {a['axis']} : Ncr = π²EI/Lcr² [§6.3.1.2, éq. 6.50]", a["Ncr"] / 1e3, "kN"),
                (
                    f"Flambement {a['axis']} : λ̄, courbe {a['curve']}, α = {a['alpha']:.2f} [tab. 6.2, tab. 6.1]",
                    a["lambda"],
                    "-",
                ),
                (f"Flambement {a['axis']} : χ [éq. 6.49]", a["chi"], "-"),
                (f"Flambement {a['axis']} : Nb,Rd = χ·A·fy/γM1 [éq. 6.47]", a["NbRd"] / 1e3, "kN"),
            ]
        rows += [
            ("NEd,compression / Nb,Rd [éq. 6.46]", r["buck"]["ratio"], "-"),
            ("Flambement", r["buck"]["ok"], ""),
        ]
    if r["inter"] is not None:
        it = r["inter"]
        rows += [
            (
                "Interaction N + M, nY = NEd/(χy·NRk/γM1) ; nZ [§6.3.3, annexe B]",
                f"nY = {it['nY']:.3f} ; nZ = {it['nZ']:.3f}",
                "",
            ),
            (
                "kyy, kzy [annexe B, méthode 2, tableau B.2 ; Cmy, CmLT]",
                f"kyy = {it['kyy']:.3f} ; kzy = {it['kzy']:.3f} (Cmy = {it['Cmy']:.2f}, CmLT = {it['CmLT']:.2f})",
                "",
            ),
            ("NEd/(χy·NRk/γM1) + kyy·MEd/(χLT·My,Rk/γM1) [éq. 6.61]", it["ratio61"], "-"),
            ("NEd/(χz·NRk/γM1) + kzy·MEd/(χLT·My,Rk/γM1) [éq. 6.62]", it["ratio62"], "-"),
            ("Interaction N + M", it["ok"], ""),
        ]
    elif r["Ncomp"] > 0 and r["MEd"] > 0:
        rows.append(
            ("ATTENTION", "N de compression et M présents mais section de classe 4 : interaction non vérifiée", "")
        )
    w = r["web"]
    if w["needed"]:
        rows += [
            (
                "Voilement de l'âme par cisaillement : hw/tw > 72ε/η, vérification requise [EN 1993-1-5 §5]",
                f"hw/tw = {w['hwTw']:.1f} > {w['limit']:.1f}",
                "",
            ),
            (
                "λ̄w = hw/(86,4·tw·ε) ; χw [tab. 5.1, poteau d'extrémité rigide]",
                f"λ̄w = {w['lambda']:.3f} ; χw = {w['chi']:.3f}",
                "",
            ),
            ("Vb,Rd = χw·fy·hw·tw/(√3·γM1) (semelles négligées)", w["VbRd"] / 1e3, "kN"),
            ("VEd / Vb,Rd", w["ratio"], "-"),
            ("Voilement de l'âme", w["ok"], ""),
        ]
    else:
        rows.append(
            (
                "Voilement de l'âme par cisaillement",
                f"sans objet : hw/tw = {w['hwTw']:.1f} ≤ 72ε/η = {w['limit']:.1f} [EN 1993-1-1 §6.2.6(6)]",
                "",
            )
        )
    na = saisie["na"]
    if na == "FR":
        naTxt = (
            "France : γM0 = 1,0 ; γM1 = 1,0 ; γM2 = 1,25 (mêmes valeurs que l'EN) ; courbes de flambement et de "
            "déversement : valeurs recommandées de l'EN (non comparées au texte de l'annexe française)"
        )
    elif na == "autre":
        naTxt = (
            f"autre pays : γM0 = {saisie['gM0']:.3g} et γM1 = {saisie['gM1']:.3g} saisis ; autres paramètres : "
            "valeurs recommandées de l'EN"
        )
    else:
        naTxt = "valeurs recommandées de l'EN (γM0 = γM1 = 1,0)"
    rows += [
        ("Eurocode 3 (sections, voilement, déversement, N + M, flambement)", r["okAll"], ""),
        (
            "Non vérifié",
            "voilement local sous charges concentrées (EN 1993-1-5 §6), flexion déviée, ELS, assemblages, classe 4",
            "",
        ),
        ("Annexe nationale", naTxt, ""),
        ("Sources", "docs/NORMES.md", ""),
    ]
    return rows


def checkFatigue(saisie: dict, dm: DataManager) -> tuple[dict, pd.DataFrame]:
    """Coefficient de sécurité en fatigue (Goodman modifié) au point le plus sollicité de la poutre.

    Entrées : `saisie` (Kt, R = fR, ka = fka, kb = fkb, s, mat) ; `dm` (Rm du matériau).
    σmax nominale = Kt·σ / Kt (σ du calcul « tous les cas à 1 ») ; Kf = Kt.
    Sortie : (r, T) : r dict de design_checks.goodman (sigmaA, sigmaM, Se, n), T tableau Grandeur / Valeur / Unité.
    Erreur : MecaStruct:App:invalidInput si Kt < 1 ou Rm inconnu.
    """
    Kt = saisie["Kt"]
    if not Kt >= 1:
        raise MecaStructError(_ID, "Fatigue : Kt doit être ≥ 1.")
    sigMax = computeBeam(saisie, dm)["check"]["bend"]["sigmaMaxKt"] / Kt
    Rm = dm.getMaterial(saisie["mat"])["Rm"]
    if not (math.isfinite(Rm) and Rm > 0):
        raise MecaStructError(_ID, f"Fatigue : Rm inconnu pour « {saisie['mat']} ».")
    r = design_checks.goodman(sigMax, saisie["fR"], Kt, Rm, saisie["fka"], saisie["fkb"])
    ok = r["n"] >= saisie["s"]
    rows = [
        ("Contrainte nominale max σmax", sigMax / 1e6, "MPa"),
        ("R = σmin / σmax", saisie["fR"], "-"),
        ("Kf (= Kt)", Kt, "-"),
        ("Amplitude σa = Kf·σmax·(1−R)/2", r["sigmaA"] / 1e6, "MPa"),
        ("Contrainte moyenne σm", r["sigmaM"] / 1e6, "MPa"),
        ("Rm", Rm / 1e6, "MPa"),
        ("Limite d'endurance Se = ka·kb·0,5·Rm", r["Se"] / 1e6, "MPa"),
        ("Coefficient de sécurité n = 1 / (σa/Se + σm/Rm)", r["n"], "-"),
        ("Coefficient exigé s", saisie["s"], "-"),
        ("Fatigue (Goodman)", ok, ""),
        ("Hypothèses", "acier, vie infinie, Kf = Kt, chargement uniaxial d'amplitude constante", ""),
    ]
    return r, _kvTable(rows)


def findLightestProfile(
    saisie: dict, dm: DataManager, family: str, deflRatio: float | None
) -> tuple[pd.DataFrame, dict | None]:
    """Essaie chaque profilé d'une famille avec le chargement de la poutre ; renvoie le plus léger qui vérifie.

    Entrées : `saisie` (non modifiée : chaque profilé est essayé sur une copie) ; `family` (IPE, HEA, HEB, IPN, UPN,
    UAP) ; `deflRatio` : flèche limitée à L/deflRatio (None ou 0 = ignorée).
    Sortie : (T, best) : T trié par aire croissante (colonnes Profilé, S (mm²), Masse (kg/m), Kt·σ max (MPa),
    σadm (MPa), f max (mm), L/f (-), Résistance) ; best = profilé du catalogue (getProfile) qui vérifie
    (résistance et, si demandé, flèche), None sinon.
    """
    if deflRatio is None:
        deflRatio = 0.0
    names = dm.listProfiles(family)
    rho = dm.getMaterial(saisie["mat"])["rho"]
    rows = []
    for name in names:
        p = dm.getProfile(family, name)
        sec = geometry.fromProfile(p)
        P = geometry.analytical(sec)
        Pt = geometry.tabulated(sec)
        trial = copy.deepcopy(saisie)
        trial.update(
            {
                "S": p["S"] * 1e6,
                "Iz": p["Iz"] * 1e12,
                "Iy": p["Iy"] * 1e12,
                "Ix": P["J"] * 1e12,
                "ky": Pt["ky"],
                "kz": Pt["kz"],
                "Iyz": 0.0,
                "vy": p["h"] / 2 * 1e3,
                "vz": p["b"] / 2 * 1e3,
                "section": None,
                "secTabulated": False,
            }
        )
        try:
            beam = computeBeam(trial, dm)
            L = beam["sol"]["model"]["L"]
            f = beam["defl"]["integration"]["fmax"] * 1e3
            chk = beam["check"]["bend"]
            okF = deflRatio <= 0 or f <= L * 1e3 / deflRatio
            ok = bool(chk["ok"]) and okF
            vals = [
                p["S"] * 1e6,
                rho * p["S"],
                chk["sigmaMaxKt"] / 1e6,
                chk["sigmaAdm"] / 1e6,
                f,
                L * 1e3 / max(f, _EPS),
            ]
            verdict = _okText(ok)
        except Exception as err:  # comme MATLAB : un profilé en erreur ne bloque pas les autres
            ok = False
            vals = [math.nan] * 6
            verdict = f"erreur : {err}"
        rows.append([name, *vals, ok, verdict])
    rows.sort(key=lambda row: row[1])  # tri stable par aire croissante
    T = pd.DataFrame(
        [row[:7] + [row[8]] for row in rows],
        columns=[
            "Profilé",
            "S (mm²)",
            "Masse (kg/m)",
            "Kt·σ max (MPa)",
            "σadm (MPa)",
            "f max (mm)",
            "L/f (-)",
            "Résistance",
        ],
    )
    best = next((row[0] for row in rows if row[7]), None)
    return T, (dm.getProfile(family, best) if best is not None else None)


def computeMovingLoad(saisie: dict, dm: DataManager) -> tuple[pd.DataFrame, dict]:
    """Enveloppe d'un convoi de charges mobiles (1 à 20 essieux) sur la poutre.

    La poutre est résolue pour chaque position du convoi : grille de `mvN` positions, plus les positions critiques
    (essieu sur un appui, une rotule ou un point de la grille, symétrie « essieu et résultante de part et d'autre du
    milieu »). Sans `mvFixed`, seul le convoi est appliqué (ni charges saisies, ni tassement, ni température).
    Entrées : `saisie` (mvP en kN, mvE en m, mvN, mvFixed) ; `dm`.
    Sortie : (T, env) : T enveloppe le long de la poutre (101 points, kN·m et kN) ; env dict s, Mmax, Mmin, Tmax, Tmin
    (tableaux), extrema (Mmax, Mmin, Tmax, Tmin exacts), Rmax, Rmin (réactions Ry par appui), names, positions,
    fixedLoads.
    Erreur : MecaStruct:App:invalidInput (essieux, écartements, nombre de positions, aucun essieu sur la poutre).
    """
    P = _parseNumbers(saisie["mvP"], "Essieux") * 1e3
    if P.size == 0:
        raise MecaStructError(_ID, "Charge mobile : saisissez au moins une charge d'essieu (kN).")
    gaps = _parseNumbers(saisie["mvE"], "Écartements")
    if gaps.size == 1:
        gaps = np.full(P.size - 1, gaps[0])  # un seul écartement pour tous (aucun pour un essieu seul)
    if gaps.size != P.size - 1 or np.any(gaps <= 0):
        raise MecaStructError(
            _ID,
            f"Charge mobile : {P.size} essieu(x) demandent {P.size - 1} écartement(s) positif(s) "
            "(ou un seul pour tous).",
        )
    if P.size > 20:
        raise MecaStructError(_ID, "Charge mobile : 20 essieux au plus.")
    nPos = math.floor(saisie["mvN"] + 0.5)  # arrondi comme round de MATLAB
    if not 2 <= nPos <= 500:
        raise MecaStructError(_ID, "Charge mobile : 2 à 500 positions de base.")

    offs = np.concatenate([[0.0], np.cumsum(gaps)])
    model = buildBeamModel(saisie, dm)
    if not saisie["mvFixed"]:
        model["pointLoads"] = []
        model["pointMoments"] = []
        model["distLoads"] = []
        model["thermal"] = {"epsX": 0.0, "kv": 0.0, "kw": 0.0}
        for sup in model["supports"]:
            sup["dx"] = sup["dy"] = sup["dz"] = 0.0
    nF = len(model["pointLoads"])
    L = model["L"]
    s = np.linspace(0.0, L, 101)
    hi = np.full(s.size, -math.inf)
    lo = np.full(s.size, math.inf)
    thi = np.full(s.size, -math.inf)
    tlo = np.full(s.size, math.inf)
    ext = {"Mmax": -math.inf, "Mmin": math.inf, "Tmax": -math.inf, "Tmin": math.inf}
    ns = len(model["supports"])
    Rmax = np.full(ns, -math.inf)
    Rmin = np.full(ns, math.inf)
    pts = np.concatenate([[sup["pos"] for sup in model["supports"]], [h["pos"] for h in model["hinges"]], s])
    cand = np.concatenate([np.linspace(-offs[-1], L, nPos), (pts[:, None] - offs[None, :]).ravel()])
    if abs(P.sum()) > 0:
        offR = np.sum(P * offs) / np.sum(P)
        cand = np.append(cand, (L - offs - offR) / 2)

    used = 0
    for x0 in np.unique(cand):
        xs = x0 + offs
        on = (xs >= -1e-9) & (xs <= L + 1e-9)  # tolérance : un essieu posé sur un appui reste compté
        if not on.any():
            continue
        m = copy.deepcopy(model)
        for k in np.flatnonzero(on):
            m["pointLoads"].append(
                {"pos": min(max(xs[k], 0.0), L), "Fx": 0.0, "Fy": P[k], "Fz": 0.0, "name": f"E{k + 1}"}
            )
        sol = solveBeam(m, {"internalMethod": "coupures", "hyperMethod": "menabrea", "useSymbolic": False})
        M = ppEval(sol["Mfz"], s, "left")
        M2 = ppEval(sol["Mfz"], s, "right")
        Ty = ppEval(sol["Ty"], s, "left")
        Ty2 = ppEval(sol["Ty"], s, "right")
        hi = np.maximum(hi, np.maximum(M, M2))
        lo = np.minimum(lo, np.minimum(M, M2))
        thi = np.maximum(thi, np.maximum(Ty, Ty2))
        tlo = np.minimum(tlo, np.minimum(Ty, Ty2))
        e = sol["extrema"]
        ext["Mmax"] = max(ext["Mmax"], e["Mfz"]["max"])
        ext["Mmin"] = min(ext["Mmin"], e["Mfz"]["min"])
        ext["Tmax"] = max(ext["Tmax"], e["Ty"]["max"])
        ext["Tmin"] = min(ext["Tmin"], e["Ty"]["min"])
        R = np.array([react["Ry"] for react in sol["reactions"]])
        Rmax = np.maximum(Rmax, R)
        Rmin = np.minimum(Rmin, R)
        used += 1
    if used == 0:
        raise MecaStructError(_ID, "Charge mobile : aucun essieu sur la poutre.")

    env = {
        "s": s,
        "Mmax": hi,
        "Mmin": lo,
        "Tmax": thi,
        "Tmin": tlo,
        "extrema": ext,
        "Rmax": Rmax,
        "Rmin": Rmin,
        "names": [sup["name"] for sup in model["supports"]],
        "positions": used,
        "fixedLoads": nF,
    }
    T = pd.DataFrame(
        {
            "s (m)": s,
            "Mfz max (kN·m)": hi / 1e3,
            "Mfz min (kN·m)": lo / 1e3,
            "Ty max (kN)": thi / 1e3,
            "Ty min (kN)": tlo / 1e3,
        }
    )
    return T, env


def loadFromBeam(saisie_cible: dict, beam_result: dict, key: str, mode: str) -> dict:
    """Copie de la saisie cible (Sections ou Flexion) remplie avec N, Mfz, Mfy (et Ty) lus sur la poutre.

    Entrées : `saisie_cible` (N, Mfz, Mfy, Ty si présent, s0 en kN, kN·m, m) ; `beam_result` (sortie de computeBeam) ;
    `key` : 'Sec' ou 'Fle' ; `mode` : 'abscisse' (efforts en s0) ou 'max' (point le plus sollicité, comme beamCheck).
    Les efforts sont ceux du torseur de cohésion (actions à droite de la coupure).
    Sortie : nouvelle saisie cible. Erreur : MecaStruct:App:invalidInput si key est inconnu ou si s0 est hors de [0, L].
    """
    if key not in ("Sec", "Fle"):
        raise MecaStructError(_ID, "key doit valoir 'Sec' ou 'Fle'.")
    out = copy.deepcopy(saisie_cible)
    sol = beam_result["sol"]
    if mode == "max":
        c = beam_result["check"]
        s = c["s"]
        N, Mfz, Mfy, Ty = c["N"], c["Mfz"], c["Mfy"], c["Ty"]  # côté de la discontinuité retenu par beamCheck
    else:
        s = saisie_cible["s0"]
        L = sol["model"]["L"]
        if not 0 <= s <= L:
            raise MecaStructError(_ID, f"L'abscisse s doit être comprise entre 0 et L = {L:.4g} m.")
        N, Mfz, Mfy = (ppEval(sol[k], s) for k in ("N", "Mfz", "Mfy"))
        Ty = ppEval(sol["Ty"], s)
    out.update({"N": N / 1e3, "Mfz": Mfz / 1e3, "Mfy": Mfy / 1e3, "s0": s})
    if "Ty" in saisie_cible:
        out["Ty"] = Ty / 1e3
    return out


def sendToTensor(beam_result: dict) -> dict:
    """État de contrainte du point le plus sollicité de la poutre, pour l'onglet Tenseurs & Critères.

    Entrée : `beam_result` (sortie de computeBeam). Sortie : dict sig (tenseur σ en MPa, σxx seul non nul), s (m),
    loc (position (y, z) de la fibre, m). Le matériau, Re et s viennent de la saisie de la poutre.
    """
    chk = beam_result["check"]
    sig = np.zeros((3, 3))
    sig[0, 0] = chk["sigma"] / 1e6
    return {"sig": sig, "s": chk["s"], "loc": chk["loc"]}
