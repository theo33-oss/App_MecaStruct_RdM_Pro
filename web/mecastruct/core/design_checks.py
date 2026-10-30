"""Vérifications de dimensionnement : port de DesignChecks.m (étape E17).

Eurocode 3 simplifié (flexion + effort tranchant, déversement, flambement, N + M, interaction, voilement de
l'âme) pour les profilés en I, et fatigue de Goodman modifiée. Unités SI strictes (m, N, Pa, N·m) ; aucun
accès à l'interface. Les clauses de norme sont conservées dans les docstrings (détail dans docs/NORMES.md).

Application de Théo Brun, basée sur son cours de Résistance des Matériaux.
"""

import math

import numpy as np

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import fmt_fr

EPS = np.finfo(float).eps  # précision machine (eps de MATLAB), utilisée par goodman et ec3AxialBending
_ALPHA = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}  # tableaux 6.1 et 6.3


def _alphaOf(curve: str) -> float:
    """Facteur d'imperfection α de la courbe a0, a, b, c ou d (tableaux 6.1 et 6.3)."""
    return _ALPHA[curve]


def _pick(x: float, lims: list[float]) -> int:
    """Numéro (1 à 3) de la première limite lims[k] ≥ x ; 4 si aucune (find de MATLAB)."""
    for k, lim in enumerate(lims, start=1):
        if x <= lim:
            return k
    return 4


def _rapport(a: float, b: float) -> float:
    """a / b avec la convention MATLAB : x / 0 = Inf, 0 / 0 = NaN."""
    if b == 0:
        return math.nan if a == 0 else math.inf
    return a / b


def ibeamDims(sec: dict) -> dict:
    """Dimensions h, b, tw, tf, r (m) d'une section 'profile' (IPE, HEA, HEB, IPN) ou 'I'.

    Entrée : sec (dict de geometry.fromProfile, ou section de type 'I'). Sortie : dict h, b, tw, tf, r (m).
    Erreur : MecaStruct:Design:unsupportedSection pour tout autre type ou famille.
    """
    if sec["type"] == "profile":
        if sec["family"] not in ("IPE", "HEA", "HEB", "IPN"):
            raise MecaStructError(
                "MecaStruct:Design:unsupportedSection",
                "Eurocode 3 : seuls les profilés IPE, HEA, HEB, IPN et les sections en I sont traités "
                f"(section : {sec['family']}).",
            )
        r = sec.get("r")
        r = r if r is not None and math.isfinite(r) else 0.0
        return {"h": sec["h"], "b": sec["b"], "tw": sec["a"], "tf": sec["e"], "r": r}
    if sec["type"] == "I":
        return {"h": sec["h"], "b": sec["b"], "tw": sec["tw"], "tf": sec["tf"], "r": 0.0}
    raise MecaStructError(
        "MecaStruct:Design:unsupportedSection",
        f"Eurocode 3 : la section doit être un profilé IPE, HEA, HEB, IPN ou un profil en I (section : {sec['type']}).",
    )


def classify(d: dict, fy: float, Nc: float, Mz: float, A: float, Iz: float) -> dict:
    """Classe de section (EN 1993-1-1, tableau 5.2) sous compression Nc (N, ≥ 0) et moment fort Mz (N·m).

    Entrées : d (ibeamDims), fy (Pa), Nc (N), Mz (N·m), A (m²), Iz (m⁴).
    Sortie : dict eps, cf, cw, ratioFlange, ratioWeb, psi, alpha, classFlange, classWeb, class.
    Aile en console : c/tf ≤ 9ε, 10ε, 14ε. Âme (feuille 2) : σ = Nc/A ± |Mz|·(hw/2)/Iz aux bords de l'âme, ψ = σ2/σ1,
    α = dc/d = 1/(1 − ψ) ≤ 1. Classes 1 et 2 : 396ε/(13α − 1) et 456ε/(13α − 1) si α > 0,5, sinon 36ε/α et 41,5ε/α.
    Classe 3 : 42ε/(0,67 + 0,33ψ), ou 62ε(1 − ψ)√(−ψ) si ψ ≤ −1. Flexion seule : ψ = −1, soit 72ε, 83ε, 124ε.
    La traction est ignorée : elle donnerait des limites plus larges, donc c'est du côté de la sécurité.
    """
    epsilon = math.sqrt(235e6 / fy)
    hw = d["h"] - 2 * d["tf"]
    cf = (d["b"] - d["tw"] - 2 * d["r"]) / 2
    cw = hw - 2 * d["r"]
    sC = max(Nc, 0) / A
    sM = abs(Mz) * (hw / 2) / Iz
    psi = -1.0
    if sC + sM > 0:
        psi = (sC - sM) / (sC + sM)
    alpha = 1.0 if psi >= 1 else min(1.0, 1 / (1 - psi))
    if alpha > 0.5:
        lim = [396 / (13 * alpha - 1), 456 / (13 * alpha - 1)]
    else:
        lim = [36 / alpha, 41.5 / alpha]
    if psi > -1:
        lim.append(42 / (0.67 + 0.33 * psi))
    else:
        lim.append(62 * (1 - psi) * math.sqrt(-psi))
    rf = cf / d["tf"]
    rw = cw / d["tw"]
    c = {
        "eps": epsilon,
        "cf": cf,
        "cw": cw,
        "ratioFlange": rf,
        "ratioWeb": rw,
        "psi": psi,
        "alpha": alpha,
        "classFlange": _pick(rf, [k * epsilon for k in (9, 10, 14)]),
        "classWeb": _pick(rw, [k * epsilon for k in lim]),
    }
    c["class"] = max(c["classFlange"], c["classWeb"])
    return c


def ec3Bending(d: dict, S: float, Iz: float, fy: float, gM0: float, MEd: float, VEd: float, Nc: float = 0.0) -> dict:
    """Résistance en flexion (axe fort) et en effort tranchant d'un profil en I.

    Entrées : d (ibeamDims) ; S (m²), Iz (m⁴) ; fy (Pa) ; gM0 (-) ; MEd (N·m), VEd (N) : valeurs de calcul ;
    Nc : compression de calcul (N, défaut 0), qui abaisse les limites de classe de l'âme (voir classify).
    Réduction du moment si VEd > 0,5·Vpl,Rd (6.2.8). Erreur 'MecaStruct:Design:class4' en classe 4.
    """
    if not (fy > 0 and gM0 > 0):
        raise MecaStructError("MecaStruct:Design:invalidInput", "fy et γM0 doivent être strictement positifs.")
    cl = classify(d, fy, Nc, MEd, S, Iz)
    if cl["class"] == 4:
        raise MecaStructError(
            "MecaStruct:Design:class4",
            f"Section de classe 4 (aile {fmt_fr(cl['ratioFlange'], '.1f')}, âme {fmt_fr(cl['ratioWeb'], '.1f')}) : "
            "la section efficace n'est pas traitée. Choisir un profilé plus trapu.",
        )
    hw = d["h"] - 2 * d["tf"]
    Wpl = (
        d["b"] * d["tf"] * (d["h"] - d["tf"])
        + d["tw"] * hw**2 / 4
        + 4 * (1 - math.pi / 4) * d["r"] ** 2 * (hw / 2 - 0.2234 * d["r"])
    )
    Wel = Iz / (d["h"] / 2)
    W = Wpl if cl["class"] <= 2 else Wel
    Mc = W * fy / gM0
    eta = 1.0 if fy > 460e6 else 1.2
    Av = max(S - 2 * d["b"] * d["tf"] + (d["tw"] + 2 * d["r"]) * d["tf"], eta * hw * d["tw"])
    Vpl = Av * (fy / math.sqrt(3)) / gM0
    reduced = abs(VEd) > 0.5 * Vpl
    rho = 0.0
    MRd = Mc
    if reduced:
        rho = (2 * abs(VEd) / Vpl - 1) ** 2
        Aw = hw * d["tw"]
        MRd = max(0.0, min(Mc, (W - rho * Aw**2 / (4 * d["tw"])) * fy / gM0))
    r = {
        "class": cl,
        "Wpl": Wpl,
        "Wel": Wel,
        "W": W,
        "Mc": Mc,
        "Av": Av,
        "Vpl": Vpl,
        "reduced": reduced,
        "rho": rho,
        "MRd": MRd,
        "MEd": abs(MEd),
        "VEd": abs(VEd),
        "ratioM": _rapport(abs(MEd), MRd),
        "ratioV": abs(VEd) / Vpl,
    }
    r["ok"] = r["ratioM"] <= 1 and r["ratioV"] <= 1
    return r


def ec3LateralTorsional(
    d: dict,
    rolled: bool,
    W: float,
    fy: float,
    gM1: float,
    E: float,
    G: float,
    Iweak: float,
    It: float,
    Lcr: float,
    C1: float,
    MEd: float,
) -> dict:
    """Résistance au déversement d'un profil en I (EN 1993-1-1, 6.3.2.3, cas des laminés).

    Entrées : d (ibeamDims) ; rolled : True (laminé) ou False (soudé) ; W : module de flexion de la classe (Wpl ou
    Wel, m³) ; fy (Pa) ; gM1 (-) ; E, G (Pa) ; Iweak : moment quadratique de l'axe faible (m⁴) ; It : constante de
    torsion (m⁴) ; Lcr : longueur entre maintiens latéraux (m) ;
    C1 : facteur de forme du moment (1 = uniforme, prudent).
    Mcr (poutre à fourches, charge au centre de torsion, doublement symétrique) : NCCI SN003a/b,
      Mcr = C1·π²·E·Iz/Lcr²·√(Iw/Iz + Lcr²·G·It/(π²·E·Iz)), avec Iw ≈ Iz·(h − tf)²/4 (parois minces).
    λ̄LT = √(W·fy/Mcr) ; ΦLT = 0,5·[1 + αLT·(λ̄LT − 0,4) + 0,75·λ̄LT²] ;
    χLT = 1/(ΦLT + √(ΦLT² − 0,75·λ̄LT²)), borné par 1 et 1/λ̄LT² (6.57) ; Mb,Rd = χLT·W·fy/γM1 (6.55).
    Courbe (tableau 6.5, valeurs recommandées) : laminé h/b ≤ 2 → b, > 2 → c ; soudé h/b ≤ 2 → c, > 2 → d ;
    α (tableau 6.3) : a 0,21 ; b 0,34 ; c 0,49 ; d 0,76. L'annexe nationale peut modifier ces choix.
    Non pris en compte : coefficient f de répartition du moment (6.58, favorable) et le niveau
    d'application de la charge.
    """
    if not (Lcr > 0 and C1 > 0 and gM1 > 0 and Iweak > 0 and It > 0):
        raise MecaStructError(
            "MecaStruct:Design:invalidInput",
            "Déversement : Lcr, C1, γM1, Iz et It doivent être strictement positifs.",
        )
    Iw = Iweak * (d["h"] - d["tf"]) ** 2 / 4
    Mcr = C1 * math.pi**2 * E * Iweak / Lcr**2 * math.sqrt(Iw / Iweak + Lcr**2 * G * It / (math.pi**2 * E * Iweak))
    lam = math.sqrt(W * fy / Mcr)
    tall = d["h"] / d["b"] > 2 + 1e-9
    curve = ("bc" if rolled else "cd")[int(tall)]
    alpha = _alphaOf(curve)
    beta = 0.75
    lam0 = 0.4
    Phi = 0.5 * (1 + alpha * (lam - lam0) + beta * lam**2)
    # 6.3.2.3(1) : pas de réduction pour λ̄LT ≤ λ̄LT,0 (6.56)
    chi = 1.0 if lam <= lam0 else min(1.0, 1 / lam**2, 1 / (Phi + math.sqrt(max(Phi**2 - beta * lam**2, 0))))
    Mb = chi * W * fy / gM1
    r = {
        "Iw": Iw,
        "Mcr": Mcr,
        "lambda": lam,
        "curve": curve,
        "alpha": alpha,
        "Phi": Phi,
        "chi": chi,
        "MbRd": Mb,
        "MEd": abs(MEd),
        "ratio": abs(MEd) / Mb,
    }
    r["ok"] = r["ratio"] <= 1
    return r


def ec3FlexuralBuckling(
    d: dict,
    rolled: bool,
    A: float,
    Iy: float,
    Iz: float,
    Lcr: float | list[float],
    fy: float,
    E: float,
    gM1: float,
    NEd: float,
) -> dict:
    """Flambement par flexion d'une barre comprimée en I (EN 1993-1-1, 6.3.1).

    Entrées : d (ibeamDims) ; rolled : laminé (True) ou soudé ; A (m²) ; Iy (axe fort), Iz (axe faible) en m⁴ ;
    Lcr (m) : scalaire, ou [Lcr,y Lcr,z] pour l'axe fort y-y et l'axe faible z-z (le plan fort n'est pas
    contreventé par les entretoises : sa longueur est celle de la poutre) ; fy, E (Pa) ; gM1 (-) ; NEd (N, compression).
    Ncr = π²·E·I/Lcr² ; λ̄ = √(A·fy/Ncr) ; Φ = 0,5·[1 + α·(λ̄ − 0,2) + λ̄²] ; χ = 1/(Φ + √(Φ² − λ̄²)) ≤ 1 (6.49) ;
    Nb,Rd = χ·A·fy/γM1 (6.47). Pas de vérification si λ̄ ≤ 0,2 ou NEd/Ncr ≤ 0,04 (6.3.1.2(4)).
    Courbes (tableau 6.2, aciers S235 à S420) : laminé h/b > 1,2 : tf ≤ 40 mm → a (y-y), b (z-z) ;
    40 < tf ≤ 100 mm → b, c ; laminé h/b ≤ 1,2 : tf ≤ 100 mm → b, c ; soudé : tf ≤ 40 mm → b, c ; tf > 40 mm → c, d.
    Laminé h/b > 1,2 avec tf > 100 mm : non tabulé, courbe d par prudence.
    α (tableau 6.1) : a0 0,13 ; a 0,21 ; b 0,34 ; c 0,49 ; d 0,76. Aciers S460 : courbes différentes, refusés.
    Sortie : dict axes (liste de 2 dicts y-y puis z-z), governing (1 ou 2), NbRd, NEd, ratio, ok.
    """
    if fy > 420e6:
        raise MecaStructError(
            "MecaStruct:Design:unsupportedSteel",
            "Flambement : le tableau 6.2 retenu vaut pour les aciers jusqu'à S420 "
            f"(fy = {fmt_fr(fy / 1e6, '.0f')} MPa).",
        )
    lcr = [Lcr, Lcr] if np.ndim(Lcr) == 0 else list(Lcr)
    if not (all(x > 0 for x in lcr) and gM1 > 0 and A > 0 and Iy > 0 and Iz > 0):
        raise MecaStructError(
            "MecaStruct:Design:invalidInput",
            "Flambement : Lcr, γM1, A, Iy et Iz doivent être strictement positifs.",
        )
    tf = d["tf"] * 1e3
    hb = d["h"] / d["b"]
    if rolled:
        if hb > 1.2:
            curves = ("d", "d") if tf > 100 else ("b", "c") if tf > 40 else ("a", "b")
        else:
            curves = ("d", "d") if tf > 100 else ("b", "c")
    else:
        curves = ("c", "d") if tf > 40 else ("b", "c")
    I = [Iy, Iz]
    axisName = ["y-y", "z-z"]
    ax = []
    for k in range(2):
        Ncr = math.pi**2 * E * I[k] / lcr[k] ** 2
        lam = math.sqrt(A * fy / Ncr)
        al = _alphaOf(curves[k])
        Phi = 0.5 * (1 + al * (lam - 0.2) + lam**2)
        chi = min(1.0, 1 / (Phi + math.sqrt(max(Phi**2 - lam**2, 0))))
        needed = not (lam <= 0.2 or abs(NEd) / Ncr <= 0.04)
        if not needed:
            chi = 1.0
        ax.append(
            {
                "axis": axisName[k],
                "Ncr": Ncr,
                "lambda": lam,
                "curve": curves[k],
                "alpha": al,
                "Phi": Phi,
                "chi": chi,
                "NbRd": chi * A * fy / gM1,
                "needed": needed,
            }
        )
    g = int(np.argmin([a["NbRd"] for a in ax])) + 1  # numéro de 1 à 2, comme MATLAB
    r = {"axes": ax, "governing": g, "NbRd": ax[g - 1]["NbRd"], "NEd": abs(NEd)}
    r["ratio"] = abs(NEd) / r["NbRd"]
    r["ok"] = r["ratio"] <= 1
    return r


def ec3AxialBending(d: dict, b: dict, A: float, fy: float, gM0: float, NEd: float, MEd: float) -> dict:
    """Flexion + effort normal, section de classe 1 à 3, flexion autour de l'axe fort (EN 1993-1-1, 6.2.9).

    Entrées : d (ibeamDims) ; b : résultat de ec3Bending ; NEd (N, signe ignoré) ; MEd (N·m).
    Classes 1 et 2 (6.2.9.1) : MN,y,Rd = Mpl,y,Rd·(1 − n)/(1 − 0,5·a) ≤ Mpl,y,Rd (6.36), n = NEd/Npl,Rd,
    a = (A − 2·b·tf)/A ≤ 0,5 ; sans réduction si NEd ≤ 0,25·Npl,Rd et NEd ≤ 0,5·hw·tw·fy/γM0 (6.33, 6.34) ;
    plafonné par le moment réduit par le tranchant. Classe 3 (6.2.9.2) : σx,Ed = N/A + M/Wel ≤ fy/γM0 (6.42).
    """
    NEd = abs(NEd)
    Npl = A * fy / gM0
    n = NEd / Npl
    hw = d["h"] - 2 * d["tf"]
    if b["class"]["class"] <= 2:
        a = min((A - 2 * d["b"] * d["tf"]) / A, 0.5)
        free = n <= 0.25 and NEd <= 0.5 * hw * d["tw"] * fy / gM0
        if free:
            MN = b["Mc"]
        elif n >= 1:
            MN = 0.0
        else:
            MN = min(b["Mc"], b["Mc"] * (1 - n) / (1 - 0.5 * a))
        MN = min(MN, b["MRd"])
        ratio = math.inf if MN <= 0 else abs(MEd) / max(MN, EPS)
        r = {"class12": True, "n": n, "a": a, "free": free, "Npl": Npl, "MNRd": MN, "ratio": ratio}
    else:
        sig = NEd / A + abs(MEd) / b["Wel"]
        r = {
            "class12": False,
            "n": n,
            "a": math.nan,
            "free": False,
            "Npl": Npl,
            "MNRd": math.nan,
            "sigma": sig,
            "ratio": sig / (fy / gM0),
        }
    r["ok"] = r["ratio"] <= 1
    return r


def ec3Interaction(
    cls: int,
    buck: dict,
    ltb: dict,
    A: float,
    W: float,
    fy: float,
    gM1: float,
    NEd: float,
    MEd: float,
    Cmy: float,
    CmLT: float,
) -> dict:
    """Interaction compression + flexion autour de l'axe fort d'un profil en I (EN 1993-1-1, 6.3.3, éq. 6.61 et 6.62).

    Entrées : cls : classe de section (1 à 3) ; buck : ec3FlexuralBuckling (χy, χz, λ̄y, λ̄z) ; ltb : ec3LateralTorsional
    (χLT) ; A (m²) ; W (m³, Wpl en classe 1-2, Wel en classe 3) ; fy (Pa) ; gM1 ; NEd (N, compression) ; MEd (N·m, axe
    fort) ; Cmy, CmLT : facteurs de moment uniforme équivalent (tableau B.3 ; 1 = prudent, valeurs admises de 0,4 à 1).
    NEd/(χy·NRk/γM1) + kyy·MEd/(χLT·My,Rk/γM1) ≤ 1 (6.61) ; NEd/(χz·NRk/γM1) + kzy·MEd/(χLT·My,Rk/γM1) ≤ 1 (6.62).
    Facteurs kyy et kzy : annexe B (méthode 2), tableau B.2 (barres sensibles aux déformations de torsion,
    profils en I) :
      classes 1-2 : kyy = Cmy·[1 + (λ̄y − 0,2)·nY] ≤ Cmy·(1 + 0,8·nY) ;
        kzy = 1 − 0,1·λ̄z·nZ/(CmLT − 0,25) ≥ 1 − 0,1·nZ/(CmLT − 0,25) si λ̄z ≥ 0,4 ;
        kzy = 0,6 + λ̄z ≤ 1 − 0,1·λ̄z·nZ/(CmLT − 0,25) si λ̄z < 0,4 ;
      classe 3 : kyy = Cmy·(1 + 0,6·λ̄y·nY) ≤ Cmy·(1 + 0,6·nY) ;
        kzy = 1 − 0,05·λ̄z·nZ/(CmLT − 0,25) ≥ 1 − 0,05·nZ/(CmLT − 0,25).
    nY = NEd/(χy·NRk/γM1), nZ = NEd/(χz·NRk/γM1). Flexion autour de l'axe fort seulement (pas de My,z).
    """
    if not (0.4 <= Cmy <= 1 and 0.4 <= CmLT <= 1):
        raise MecaStructError(
            "MecaStruct:Design:invalidInput", "Cmy et CmLT doivent être compris entre 0,4 et 1 (tableau B.3)."
        )
    if not (1 <= cls <= 3):
        raise MecaStructError("MecaStruct:Design:class4", "Interaction 6.3.3 : classes 1 à 3 seulement.")
    NRk = A * fy
    MyRk = W * fy
    ay, az = buck["axes"]
    nY = abs(NEd) / (ay["chi"] * NRk / gM1)
    nZ = abs(NEd) / (az["chi"] * NRk / gM1)
    if cls <= 2:
        kyy = min(Cmy * (1 + (ay["lambda"] - 0.2) * nY), Cmy * (1 + 0.8 * nY))
        if az["lambda"] >= 0.4:
            kzy = max(1 - 0.1 * az["lambda"] * nZ / (CmLT - 0.25), 1 - 0.1 * nZ / (CmLT - 0.25))
        else:
            kzy = min(0.6 + az["lambda"], 1 - 0.1 * az["lambda"] * nZ / (CmLT - 0.25))
    else:
        kyy = min(Cmy * (1 + 0.6 * ay["lambda"] * nY), Cmy * (1 + 0.6 * nY))
        kzy = max(1 - 0.05 * az["lambda"] * nZ / (CmLT - 0.25), 1 - 0.05 * nZ / (CmLT - 0.25))
    den = ltb["chi"] * MyRk / gM1
    r61 = nY + kyy * abs(MEd) / den
    r62 = nZ + kzy * abs(MEd) / den
    r = {
        "nY": nY,
        "nZ": nZ,
        "kyy": kyy,
        "kzy": kzy,
        "ratio61": r61,
        "ratio62": r62,
        "ratio": max(r61, r62),
        "Cmy": Cmy,
        "CmLT": CmLT,
    }
    r["ok"] = r["ratio"] <= 1
    return r


def ec3WebShear(d: dict, fy: float, gM1: float, VEd: float) -> dict:
    """Voilement de l'âme par cisaillement, âme non raidie sauf aux appuis (EN 1993-1-1 6.2.6(6), EN 1993-1-5 §5).

    Vérification nécessaire si hw/tw > 72·ε/η (η = 1,2 jusqu'à S460, 1,0 au-delà). Sinon : sans objet.
    λ̄w = hw/(86,4·tw·ε) (raidisseurs aux appuis seulement, éq. 5.6) ; poteau d'extrémité rigide (tableau 5.1) :
    χw = η si λ̄w < 0,83/η ; 0,83/λ̄w si λ̄w < 1,08 ; 1,37/(0,7 + λ̄w) au-delà ; Vb,Rd = χw·fy·hw·tw/(√3·γM1)
    (la contribution des semelles est négligée : côté sécurité). Les charges concentrées (voilement local,
    §6) ne sont pas vérifiées.
    """
    epsilon = math.sqrt(235e6 / fy)
    eta = 1.0 if fy > 460e6 else 1.2
    hw = d["h"] - 2 * d["tf"]
    lim = 72 * epsilon / eta
    r = {"hwTw": hw / d["tw"], "limit": lim, "needed": hw / d["tw"] > lim, "VEd": abs(VEd)}
    if not r["needed"]:
        r.update({"lambda": math.nan, "chi": math.nan, "VbRd": math.inf, "ratio": 0.0, "ok": True})
        return r
    lam = hw / (86.4 * d["tw"] * epsilon)
    if lam < 0.83 / eta:
        chi = eta
    elif lam < 1.08:
        chi = 0.83 / lam
    else:
        chi = 1.37 / (0.7 + lam)
    r["lambda"] = lam
    r["chi"] = chi
    r["VbRd"] = chi * fy * hw * d["tw"] / (math.sqrt(3) * gM1)
    r["ratio"] = abs(VEd) / r["VbRd"]
    r["ok"] = r["ratio"] <= 1
    return r


def goodman(sigMax: float, R: float, Kf: float, Rm: float, ka: float, kb: float) -> dict:
    """Coefficient de sécurité en fatigue (droite de Goodman modifiée), contrainte nominale sigMax (Pa).

    Entrées : sigMax (Pa, ≥ 0) ; R = σmin/σmax dans [-1, 1[ (-1 : alterné, 0 : répété) ; Kf ≥ 1 (s'applique à
    l'amplitude seulement) ; Rm (Pa) ; ka, kb (-) : facteurs de Marin.
    Sortie : dict sigmaA, sigmaM (Pa), Se (Pa), n (-).
    """
    if not (-1 <= R < 1):
        raise MecaStructError("MecaStruct:Design:invalidInput", "Le rapport R = σmin/σmax doit vérifier -1 ≤ R < 1.")
    if not (sigMax >= 0 and Rm > 0 and ka > 0 and kb > 0 and Kf >= 1):
        raise MecaStructError(
            "MecaStruct:Design:invalidInput",
            "Fatigue : σmax ≥ 0, Rm > 0, ka > 0, kb > 0 et Kf ≥ 1 sont requis.",
        )
    Sep = min(0.5 * Rm, 700e6)
    Se = ka * kb * Sep
    sigA = Kf * sigMax * (1 - R) / 2
    sigM = sigMax * (1 + R) / 2
    den = sigA / Se + max(sigM, 0) / Rm
    n = math.inf if den == 0 else 1 / max(den, EPS)
    return {"sigmaA": sigA, "sigmaM": sigM, "Se": Se, "n": n}
