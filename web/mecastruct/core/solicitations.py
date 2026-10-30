"""Sollicitations simples : traction, cisaillement, Jourawski, matage, clavette, goupille, torsion, flexion.

Port de SolicitationsEngine.m, sauf les flèches, l'énergie et les intégrales de Mohr (deflection.py, étape E13)
et le flambage (buckling.py). Unités SI strictes (N, m, Pa, rad) ; chaque résultat contient `report` et `latex`.
"""

import math
import re

import numpy as np
from scipy.integrate import quad

from mecastruct.core import geometry
from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import is_num

_ID = "MecaStruct:SolicitationsEngine:"


# ----------------------------------------------------------------- contrôle des entrées


def _struct(p):
    """Vérifie que les paramètres forment un dict (structure scalaire MATLAB)."""
    if not isinstance(p, dict):
        raise MecaStructError(_ID + "invalidInput", "Les paramètres doivent être une structure scalaire.")
    return p


def _req(p: dict, f: str) -> float:
    """Champ numérique scalaire obligatoire ; NaN refusé, Inf accepté."""
    if p.get(f) is None:
        raise MecaStructError(_ID + "missingField", f"Champ obligatoire manquant : {f}.")
    v = p[f]
    if not is_num(v) or math.isnan(v):
        raise MecaStructError(_ID + "invalidInput", f"Le champ {f} doit être un réel scalaire.")
    return float(v)


def _reqPos(p: dict, f: str) -> float:
    """Champ numérique obligatoire strictement positif."""
    v = _req(p, f)
    if not v > 0:
        raise MecaStructError(_ID + "invalidInput", f"Le champ {f} doit être strictement positif.")
    return v


def _opt(p: dict, f: str, defaut: float) -> float:
    """Champ numérique optionnel, `defaut` s'il est absent ou vide."""
    return _req(p, f) if p.get(f) is not None else defaut


def _fun(p: dict, f: str, constante: float):
    """Handle optionnel p[f](x) vectorisé ; à défaut la fonction constante `constante`."""
    if p.get(f) is None:
        return lambda x: constante + 0 * x
    if not callable(p[f]):
        raise MecaStructError(_ID + "invalidInput", f"{f} doit être une fonction (handle).")
    return p[f]


def _tauE(p: dict) -> tuple[float, str]:
    """Résistance élastique au glissement τe : `tauE` si fourni, sinon Re/2 (Tresca) ou Re/√3 (von Mises).

    Entrée : `p` (tauE ou Re, criterion). Sortie : (τe en Pa, texte du rapport).
    """
    if p.get("tauE") is not None:
        tauE = _reqPos(p, "tauE")
        return tauE, f"τe fourni = {_seF(tauE)} Pa"
    Re = _reqPos(p, "Re")
    crit = "tresca"
    if p.get("criterion") is not None:
        crit = str(p["criterion"]).lower().replace(" ", "")
    if crit == "tresca":
        tauE = Re / 2
        return tauE, f"τe = Re/2 = {_seF(tauE)} Pa (Tresca)"
    if crit in ("vonmises", "von_mises"):
        tauE = Re / math.sqrt(3)
        return tauE, f"τe = Re/√3 = {_seF(tauE)} Pa (Von Mises)"
    raise MecaStructError(_ID + "invalidInput", "criterion doit valoir 'Tresca' ou 'VonMises'.")


# ----------------------------------------------------------------- formats des rapports


def _seF(v: float) -> str:
    """Nombre pour les textes de rapport, 4 chiffres significatifs (NaN, Inf et -0 écrits comme MATLAB)."""
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Inf" if v > 0 else "-Inf"
    return f"{v + 0.0:.4g}"


def _seT(v: float) -> str:
    """Nombre en LaTeX : exposant écrit en puissance de 10 (NaN écrit en mode mathématique)."""
    if math.isnan(v):
        return r"\mathrm{NaN}"
    s = _seF(v)
    m = re.fullmatch(r"(-?[\d.]+)e([+-]\d+)", s)
    if m is None:
        return s
    return f"{m[1]} \\cdot 10^{{{int(m[2])}}}"


def _seSgn(v: float) -> str:
    """Terme signé pour une expression linéaire du rapport."""
    return f"− {_seF(-v)}" if v < 0 else f"+ {_seF(v)}"


def _seTs(v: float) -> str:
    """Terme LaTeX signé."""
    return f"- {_seT(-v)}" if v < 0 else f"+ {_seT(v)}"


def _seOk(ok) -> str:
    """Verdict en texte."""
    return "vérifiée" if ok else "NON vérifiée"


# ----------------------------------------------------------------- intégrales de Castigliano


def _castigliano(fMain, fTh, fU, L: float, F0: float):
    """Intégrales de Castigliano : ∫ fMain, ∫ fTh, U(F0) = ∫ fU(x, F0) et ∂U/∂F en F0.

    Entrées : fMain(x), fTh(x) (None si absente), fU(x, F), L (m), F0 (effort en extrémité).
    Sortie : (Imain, Ith, dUdF, U). Intégrales par scipy.integrate.quad (epsrel 1e-12) ; ∂U/∂F par différence
    centrée, exacte car U est quadratique en F.
    """

    def q(f):
        return quad(f, 0, L, epsrel=1e-12, epsabs=0)[0]

    Imain = q(fMain)
    Ith = q(fTh) if fTh is not None else 0.0
    h = max(abs(F0), 1.0)
    U = q(lambda x: fU(x, F0))
    dUdF = (q(lambda x: fU(x, F0 + h)) - q(lambda x: fU(x, F0 - h))) / (2 * h)
    return Imain, Ith, dUdF, U


# ----------------------------------------------------------------- traction


def traction(p: dict) -> dict:
    """Traction/compression simple avec dilatation thermique : ΔL par 3 méthodes, contraintes, rigidité.

    Entrées : N (N, > 0 en traction), S0 (m²), L0 (m), E (Pa), nu (0,3), alpha (1/°C, 0), dT (°C, 0), Kt (1),
    Re (Pa), s (1), dLmax (m, Inf) ; optionnels Nfun(x), Sfun(x), dTfun(x) (fonctions vectorisées, x dans [0, L0]).
    Sortie : dict sigmaNom, sigmaMax, sigmaAdm (Pa), okResistance, epsxx, epsyy, epszz, dVsurV, dL (analytique,
    integrale, energetique en m), K (N/m), U (J), okRigidite, methodUsed, report, latex.
    """
    p = _struct(p)
    N = _req(p, "N")
    S0 = _reqPos(p, "S0")
    L0 = _reqPos(p, "L0")
    E = _reqPos(p, "E")
    nu = _opt(p, "nu", 0.3)
    alpha = _opt(p, "alpha", 0.0)
    dT = _opt(p, "dT", 0.0)
    Kt = _opt(p, "Kt", 1.0)
    Re = _reqPos(p, "Re")
    s = _opt(p, "s", 1.0)
    dLmax = _opt(p, "dLmax", math.inf)
    Nfun = _fun(p, "Nfun", N)
    Sfun = _fun(p, "Sfun", S0)
    dTfun = _fun(p, "dTfun", dT)
    variable = any(p.get(k) is not None for k in ("Nfun", "Sfun", "dTfun"))
    methode = "numérique"

    sigmaNom = N / S0
    sigWorst = sigmaNom
    if p.get("Nfun") is not None or p.get("Sfun") is not None:  # la section la plus chargée décide
        xs = np.linspace(0.0, L0, 201)
        sx = Nfun(xs) / Sfun(xs)
        sigWorst = float(sx[np.argmax(np.abs(sx))])
    sigmaMax = Kt * sigWorst
    sigmaAdm = Re / s
    okResistance = abs(sigmaMax) <= sigmaAdm
    epsxx = sigmaNom / E + alpha * dT
    epsyy = -nu * sigmaNom / E + alpha * dT
    dVsurV = (1 - 2 * nu) * sigmaNom / E + 3 * alpha * dT

    # Méthode 1 : analytique (section S0 et effort N constants)
    dLana = N * L0 / (E * S0) + alpha * dT * L0

    # Méthodes 2 et 3 : intégrale et énergétique (Castigliano, F = effort en extrémité)
    def fMech(x):
        return Nfun(x) / (E * Sfun(x))

    def fTh(x):
        return alpha * dTfun(x)

    def fU(x, F):
        return (Nfun(x) + F - N) ** 2 / (2 * E * Sfun(x))

    Imech, Ith, dUdF, U = _castigliano(fMech, fTh, fU, L0, N)
    dL = {"analytique": dLana, "integrale": Imech + Ith, "energetique": dUdF + Ith}
    if variable:  # l'analytique (S0, N constants) n'est pas représentative
        okRigidite = max(abs(dL["integrale"]), abs(dL["energetique"])) <= dLmax
    else:
        okRigidite = max(abs(dLana), abs(dL["integrale"]), abs(dL["energetique"])) <= dLmax
    K = E * S0 / L0

    report = [
        f"Contrainte nominale : σ = N/S0 = {_seF(N)} / {_seF(S0)} = {_seF(sigmaNom)} Pa",
        f"Contrainte maximale : σmax = Kt·σ = {_seF(Kt)} × {_seF(sigWorst)} = {_seF(sigmaMax)} Pa",
        f"Contrainte admissible : σadm = Re/s = {_seF(sigmaAdm)} Pa → résistance {_seOk(okResistance)}",
        f"Déformations : εxx = {_seF(epsxx)} ; εyy = εzz = {_seF(epsyy)} ; ΔV/V0 = {_seF(dVsurV)}",
        f"ΔL analytique (N L0/(E S0) + αΔT L0) = {_seF(dLana)} m",
        f"ΔL intégrale (∫ N/(E S) + αΔT dx, {methode}) = {_seF(dL['integrale'])} m",
        f"ΔL énergétique (Castigliano ∂U/∂F + thermique, {methode}) = {_seF(dL['energetique'])} m",
        f"Raideur K = E S0/L0 = {_seF(K)} N/m ; énergie U = {_seF(U)} J",
        f"Rigidité (|ΔL| ≤ ΔLmax = {_seF(dLmax)} m) : {_seOk(okRigidite)}",
    ]
    if variable:
        report.append("Section, effort ou température variables : la méthode analytique utilise S0, N et ΔT constants.")
    latex = [
        rf"$\sigma_{{xx}} = \frac{{N}}{{S_0}} = \frac{{{_seT(N)}}}{{{_seT(S0)}}} = {_seT(sigmaNom)}\,\mathrm{{Pa}}$",
        rf"$\sigma_{{max}} = K_t\,\sigma_{{nom}} = {_seT(sigmaMax)} \le \frac{{R_e}}{{s}} = {_seT(sigmaAdm)}$",
        rf"$\varepsilon_{{xx}} = \frac{{\sigma_{{xx}}}}{{E}} + \alpha\,\Delta T = {_seT(epsxx)}$",
        rf"$\varepsilon_{{yy}} = \varepsilon_{{zz}} = -\nu\,\frac{{\sigma_{{xx}}}}{{E}} + \alpha\,\Delta T"
        rf" = {_seT(epsyy)}$",
        rf"$\frac{{\Delta V}}{{V_0}} = (1-2\nu)\,\frac{{\sigma_{{xx}}}}{{E}} + 3\,\alpha\,\Delta T = {_seT(dVsurV)}$",
        rf"$\Delta L = \frac{{N\,L_0}}{{E\,S_0}} + \alpha\,\Delta T\,L_0 = {_seT(dLana)}\,\mathrm{{m}}$",
        rf"$\Delta L = \int_0^{{L_0}} \left( \frac{{N(x)}}{{E\,S(x)}} + \alpha\,\Delta T(x) \right) dx"
        rf" = {_seT(dL['integrale'])}\,\mathrm{{m}}$",
        rf"$U = \int_0^{{L_0}} \frac{{N^2}}{{2\,E\,S}}\,dx = {_seT(U)}\,\mathrm{{J}}, \ "
        rf"\Delta L = \frac{{\partial U}}{{\partial F}} + \alpha\,\Delta T\,L_0"
        rf" = {_seT(dL['energetique'])}\,\mathrm{{m}}$",
        rf"$K = \frac{{E\,S_0}}{{L_0}} = {_seT(K)}\,\mathrm{{N/m}}$",
    ]
    return {
        "sigmaNom": sigmaNom,
        "sigmaMax": sigmaMax,
        "sigmaAdm": sigmaAdm,
        "okResistance": okResistance,
        "epsxx": epsxx,
        "epsyy": epsyy,
        "epszz": epsyy,
        "dVsurV": dVsurV,
        "dL": dL,
        "K": K,
        "U": U,
        "okRigidite": okRigidite,
        "methodUsed": methode,
        "report": report,
        "latex": latex,
    }


# ----------------------------------------------------------------- cisaillement


def shear(p: dict) -> dict:
    """Cisaillement simple : τmoy = T/S, τmax = k·T/S ≤ τe/s, glissement γ = τmoy/G.

    Entrées : T (N), S (m²), k (1), Re (Pa) ou tauE (Pa), criterion ('Tresca' | 'VonMises'), s (1), G (Pa, optionnel).
    Sortie : dict tauMoy, tauMax, tauE, tauAdm (Pa), ok, gamma (rad, NaN sans G), report, latex.
    """
    p = _struct(p)
    T = _req(p, "T")
    S = _reqPos(p, "S")
    k = _opt(p, "k", 1.0)
    s = _opt(p, "s", 1.0)
    G = _opt(p, "G", math.nan)
    tauE, tauTxt = _tauE(p)
    tauMoy = T / S
    tauMax = k * T / S
    tauAdm = tauE / s
    ok = abs(tauMax) <= tauAdm
    gamma = float(np.divide(tauMoy, G))
    report = [
        f"Contrainte moyenne : τmoy = T/S = {_seF(T)} / {_seF(S)} = {_seF(tauMoy)} Pa",
        f"Contrainte maximale : τmax = k·T/S = {_seF(tauMax)} Pa (k = {_seF(k)})",
        f"{tauTxt} ; τadm = τe/s = {_seF(tauAdm)} Pa → {_seOk(ok)}",
        f"Glissement : γ = τmoy/G = {_seF(gamma)} rad",
    ]
    latex = [
        rf"$\tau_{{moy}} = \frac{{T}}{{S}} = {_seT(tauMoy)}\,\mathrm{{Pa}}$",
        rf"$\tau_{{max}} = k\,\frac{{T}}{{S}} = {_seT(tauMax)} \le \frac{{\tau_e}}{{s}} = {_seT(tauAdm)}$",
        rf"$\gamma = \frac{{\tau}}{{G}} = {_seT(gamma)}\,\mathrm{{rad}}$",
    ]
    return {
        "tauMoy": tauMoy,
        "tauMax": tauMax,
        "tauE": tauE,
        "tauAdm": tauAdm,
        "ok": ok,
        "gamma": gamma,
        "report": report,
        "latex": latex,
    }


def jourawski(sec: dict, T: float, n: int = 201) -> dict:
    """Répartition de Jourawski τ(y) = T·Q(y)/(Iz·b(y)) sur la hauteur de la section.

    Entrées : sec (section, voir geometry), T (N, effort tranchant Ty), n (nombre de points, 201).
    Sortie : dict y (m, depuis G, bas → haut), b (m), Q (m³), tau (Pa), tauMax (Pa), yAtMax (m), tauMoy (Pa),
    kNum (τmax·S/T), tauParabola (Pa, rectangle : 1,5 T/S (1 − (2y/h)²), NaN sinon), Iz (m⁴), report, latex.
    """
    if not is_num(T) or not math.isfinite(T):
        raise MecaStructError(_ID + "invalidInput", "T doit être un réel fini.")
    P = geometry.analytical(sec)
    sec = geometry.validateSection(sec)
    y = np.linspace(-P["vyBot"], P["vyTop"], max(3, math.floor(n + 0.5)))
    b = geometry.widthAt(sec, y)
    Q = geometry.firstMomentAbove(sec, y)
    ratio = np.zeros(y.shape)
    inside = b > 0
    ratio[inside] = Q[inside] / b[inside]
    tau = T * ratio / P["Iz"]
    iMax = int(np.argmax(ratio))
    rmax = ratio[iMax]
    tauMax = T * rmax / P["Iz"]
    tauMoy = T / P["S"]
    kNum = rmax * P["S"] / P["Iz"]
    if sec["type"] == "rectangle":
        tauParabola = 1.5 * T / P["S"] * (1 - (2 * y / sec["h"]) ** 2)
    else:
        tauParabola = np.full(y.shape, math.nan)
    report = [
        f"Jourawski : τ(y) = T·Q(y)/(Iz·b(y)), T = {_seF(T)} N, Iz = {_seF(P['Iz'])} m⁴",
        f"τmax = {_seF(tauMax)} Pa en y = {_seF(y[iMax])} m (depuis G) ; τmoy = T/S = {_seF(tauMoy)} Pa",
        f"Facteur de forme k = τmax·S/T = {_seF(kNum)}",
    ]
    latex = [
        r"$\tau_{yx}(y) = \frac{T_y}{I_z\,b(y)} \int\!\!\int_{S(y)} \eta\,dS$",
        rf"$\tau_{{max}} = {_seT(tauMax)}\,\mathrm{{Pa}}, \ k = \frac{{\tau_{{max}}\,S}}{{T}} = {_seT(kNum)}$",
    ]
    if sec["type"] == "rectangle":
        latex.append(r"$\tau(y) = \frac{3}{2}\,\frac{T}{S}\left[1 - \left(\frac{2y}{h}\right)^2\right]$")
    return {
        "y": y,
        "b": b,
        "Q": Q,
        "tau": tau,
        "tauMax": tauMax,
        "yAtMax": y[iMax],
        "tauMoy": tauMoy,
        "kNum": kNum,
        "tauParabola": tauParabola,
        "Iz": P["Iz"],
        "report": report,
        "latex": latex,
    }


# ----------------------------------------------------------------- matage, clavette, goupille


def bearing(p: dict) -> dict:
    """Matage : pression P = F/S_matée ≤ Padm.

    Entrées : F (N), Smatee (m²), Padm (Pa). Sortie : dict P (Pa), ok, SminRequired (m², = |F|/Padm), report, latex.
    """
    p = _struct(p)
    F = _req(p, "F")
    Sm = _reqPos(p, "Smatee")
    Padm = _reqPos(p, "Padm")
    P = F / Sm
    ok = abs(P) <= Padm
    SminRequired = abs(F) / Padm
    report = [
        f"Pression de matage : P = F/S = {_seF(F)} / {_seF(Sm)} = {_seF(P)} Pa",
        f"Padm = {_seF(Padm)} Pa → {_seOk(ok)} ; surface minimale F/Padm = {_seF(SminRequired)} m²",
    ]
    latex = [rf"$P = \frac{{F}}{{S}} = {_seT(P)} \le P_{{adm}} = {_seT(Padm)}\,\mathrm{{Pa}}$"]
    return {"P": P, "ok": ok, "SminRequired": SminRequired, "report": report, "latex": latex}


def keyDesign(p: dict) -> dict:
    """Clavette parallèle : matage P = 4C/(D b L) et cisaillement τ = 2C/(a L D).

    Entrées : C (N·m), D (m, diamètre de l'arbre), a (m, largeur), b (m, hauteur), Padm (Pa), Re ou tauE,
    criterion, s (1), L (m, optionnel). Sortie : dict F (N), tauAdm (Pa), LminMatage, LminCis, Lmin (m) ; si L :
    P (Pa), tau (Pa), okP, okTau ; report, latex.
    """
    p = _struct(p)
    C = abs(_req(p, "C"))
    D = _reqPos(p, "D")
    a = _reqPos(p, "a")
    b = _reqPos(p, "b")
    Padm = _reqPos(p, "Padm")
    s = _opt(p, "s", 1.0)
    tauE, tauTxt = _tauE(p)
    F = 2 * C / D
    tauAdm = tauE / s
    LminMatage = 4 * C / (D * b * Padm)
    LminCis = 2 * C / (a * D * tauAdm)
    r = {"F": F, "tauAdm": tauAdm, "LminMatage": LminMatage, "LminCis": LminCis, "Lmin": max(LminMatage, LminCis)}
    report = [
        f"Effort tangentiel sur la clavette : F = 2C/D = {_seF(F)} N",
        f"Matage (hauteur b/2 en contact) : L ≥ 4C/(D b Padm) = {_seF(LminMatage)} m",
        f"{tauTxt} ; cisaillement : L ≥ 2C/(a D τadm) = {_seF(LminCis)} m",
        f"Longueur minimale : Lmin = {_seF(r['Lmin'])} m",
    ]
    latex = [
        rf"$F = \frac{{2\,C}}{{D}} = {_seT(F)}\,\mathrm{{N}}$",
        rf"$L_{{min}} = \frac{{4\,C}}{{D\,b\,P_{{adm}}}} = {_seT(LminMatage)}\,\mathrm{{m}}$",
        rf"$L_{{min}} = \frac{{2\,C}}{{a\,D\,\tau_{{adm}}}} = {_seT(LminCis)}\,\mathrm{{m}}$",
    ]
    if p.get("L") is not None:
        L = _reqPos(p, "L")
        r["P"] = 4 * C / (D * b * L)
        r["tau"] = 2 * C / (a * L * D)
        r["okP"] = r["P"] <= Padm
        r["okTau"] = r["tau"] <= tauAdm
        report.append(
            f"Avec L = {_seF(L)} m : P = {_seF(r['P'])} Pa ({_seOk(r['okP'])}), "
            f"τ = {_seF(r['tau'])} Pa ({_seOk(r['okTau'])})"
        )
        latex.append(
            rf"$P = \frac{{4\,C}}{{D\,b\,L}} = {_seT(r['P'])}, \ \tau = \frac{{2\,C}}{{a\,L\,D}} = {_seT(r['tau'])}$"
        )
    r["report"] = report
    r["latex"] = latex
    return r


def pinDesign(p: dict) -> dict:
    """Goupille / rivet : P = 2F/(d e) ≤ Padm et τ = 4F/(nShear π d²) ≤ τadm.

    Entrées : F (N), d (m), e (m, épaisseur matée), Padm (Pa), Re ou tauE, criterion, s (1), nShear (nombre de
    sections cisaillées, 1). Sortie : dict P (Pa), tau (Pa), tauAdm (Pa), dMin (max des conditions de cisaillement
    et de matage à e donné, m), eMin (m), okP, okTau ; report, latex.
    """
    p = _struct(p)
    F = abs(_req(p, "F"))
    d = _reqPos(p, "d")
    e = _reqPos(p, "e")
    Padm = _reqPos(p, "Padm")
    s = _opt(p, "s", 1.0)
    ns = _opt(p, "nShear", 1.0)
    tauE, tauTxt = _tauE(p)
    P = 2 * F / (d * e)
    tau = 4 * F / (ns * math.pi * d**2)
    tauAdm = tauE / s
    dMin = max(math.sqrt(4 * F / (ns * math.pi * tauAdm)), 2 * F / (e * Padm))
    eMin = 2 * F / (d * Padm)
    okP = P <= Padm
    okTau = tau <= tauAdm
    report = [
        f"Matage (formule du cours) : P = 2F/(d e) = {_seF(P)} Pa ≤ {_seF(Padm)} → {_seOk(okP)}",
        f"Cisaillement : τ = 4F/(n π d²) = {_seF(tau)} Pa (n = {round(ns)}) ; {tauTxt} ; "
        f"τadm = {_seF(tauAdm)} → {_seOk(okTau)}",
        f"Dimensions minimales : d ≥ {_seF(dMin)} m ; e ≥ {_seF(eMin)} m",
    ]
    latex = [
        rf"$P = \frac{{2\,F}}{{d\,e}} = {_seT(P)} \le P_{{adm}} = {_seT(Padm)}$",
        rf"$\tau = \frac{{4\,F}}{{n\,\pi\,d^2}} = {_seT(tau)} \le \tau_{{adm}} = {_seT(tauAdm)}$",
    ]
    return {
        "P": P,
        "tau": tau,
        "tauAdm": tauAdm,
        "dMin": dMin,
        "eMin": eMin,
        "okP": okP,
        "okTau": okTau,
        "report": report,
        "latex": latex,
    }


# ----------------------------------------------------------------- torsion


def torsion(p: dict) -> dict:
    """Torsion d'un arbre circulaire plein ou creux : φ par 3 méthodes, contraintes, rigidité.

    Entrées : Mt (N·m), D (m), d (m, 0), G (Pa), L (m), Kt (1), Re ou tauE, criterion, s (1), thetaAdm (rad/m, Inf) ;
    optionnels MtFun(s), IxFun(s) (fonctions vectorisées).
    Sortie : dict Ix (m⁴), m (= d/D), tauMaxNom, tauMax, tauAdm (Pa), okResistance, theta (rad/m), okRigidite,
    phi (analytique, integrale, energetique en rad), Ktorsion (N·m/rad), U (J), rProfile (m), tauProfile (Pa),
    methodUsed, report, latex.
    """
    p = _struct(p)
    Mt = _req(p, "Mt")
    D = _reqPos(p, "D")
    d = _opt(p, "d", 0.0)
    if d < 0 or d >= D:
        raise MecaStructError(_ID + "invalidInput", "Il faut 0 ≤ d < D.")
    G = _reqPos(p, "G")
    L = _reqPos(p, "L")
    Kt = _opt(p, "Kt", 1.0)
    s = _opt(p, "s", 1.0)
    thetaAdm = _opt(p, "thetaAdm", math.inf)
    tauE, tauTxt = _tauE(p)
    methode = "numérique"
    Ix = math.pi * (D**4 - d**4) / 32
    MtFun = _fun(p, "MtFun", Mt)
    IxFun = _fun(p, "IxFun", Ix)

    tauMaxNom = Mt * D / (2 * Ix)
    tauMax = Kt * tauMaxNom
    tauAdm = tauE / s
    okResistance = abs(tauMax) <= tauAdm
    theta = Mt / (G * Ix)
    okRigidite = abs(theta) <= thetaAdm
    phiAnalytique = Mt * L / (G * Ix)

    def fInt(x):
        return MtFun(x) / (G * IxFun(x))

    def fU(x, C):
        return (MtFun(x) + C - Mt) ** 2 / (2 * G * IxFun(x))

    phiInt, _, dUdC, U = _castigliano(fInt, None, fU, L, Mt)
    phi = {"analytique": phiAnalytique, "integrale": phiInt, "energetique": dUdC}
    m = d / D
    Ktorsion = G * Ix / L
    rProfile = np.linspace(d / 2, D / 2, 101)
    report = [
        f"Moment quadratique polaire : Ix = π(D⁴ − d⁴)/32 = {_seF(Ix)} m⁴ (m = d/D = {_seF(m)})",
        f"τmax nominale = Mt·(D/2)/Ix = {_seF(tauMaxNom)} Pa ; avec Kt = {_seF(Kt)} : {_seF(tauMax)} Pa",
        f"{tauTxt} ; τadm = {_seF(tauAdm)} Pa → résistance {_seOk(okResistance)}",
        f"Angle unitaire θ = Mt/(G Ix) = {_seF(theta)} rad/m → rigidité {_seOk(okRigidite)}",
        f"φ analytique (Mt L/(G Ix)) = {_seF(phiAnalytique)} rad",
        f"φ intégrale (∫ Mt/(G Ix) ds, {methode}) = {_seF(phiInt)} rad",
        f"φ énergétique (∂U/∂C, {methode}) = {_seF(dUdC)} rad",
        f"Raideur K = G Ix/L = {_seF(Ktorsion)} N·m/rad ; U = {_seF(U)} J",
    ]
    latex = [
        rf"$I_x = \frac{{\pi\,(D^4 - d^4)}}{{32}} = {_seT(Ix)}\,\mathrm{{m^4}}$",
        rf"$\tau(r) = \frac{{M_t\,r}}{{I_x}}, \ \tau_{{max}} = K_t\,\frac{{M_t}}{{I_x}}\,\frac{{D}}{{2}}"
        rf" = {_seT(tauMax)}\,\mathrm{{Pa}}$",
        rf"$\theta = \frac{{d\varphi}}{{ds}} = \frac{{M_t}}{{G\,I_x}} = {_seT(theta)}\,\mathrm{{rad/m}}$",
        rf"$\varphi = \frac{{M_t\,L}}{{G\,I_x}} = {_seT(phiAnalytique)}\,\mathrm{{rad}}$",
        rf"$\varphi = \int_0^L \frac{{M_t}}{{G\,I_x}}\,ds = {_seT(phiInt)}\,\mathrm{{rad}}$",
        rf"$U = \int_0^L \frac{{M_t^2}}{{2\,G\,I_x}}\,ds = {_seT(U)}\,\mathrm{{J}}, \ "
        rf"\varphi = \frac{{\partial U}}{{\partial C}} = {_seT(dUdC)}$",
    ]
    return {
        "Ix": Ix,
        "m": m,
        "tauMaxNom": tauMaxNom,
        "tauMax": tauMax,
        "tauAdm": tauAdm,
        "okResistance": okResistance,
        "theta": theta,
        "okRigidite": okRigidite,
        "phi": phi,
        "Ktorsion": Ktorsion,
        "U": U,
        "rProfile": rProfile,
        "tauProfile": Mt * rProfile / Ix,
        "methodUsed": methode,
        "report": report,
        "latex": latex,
    }


# ----------------------------------------------------------------- flexion : contraintes


def bendingStress(p: dict) -> dict:
    """Contraintes normales de flexion composée / déviée dans une section.

    Entrées : sec (section, voir geometry) ou P (propriétés : S, Iz, Iy, Iyz, vyTop, vyBot, vzRight, vzLeft),
    N (0), Mfz (0), Mfy (0) (N, N·m), Kt (1), Re (Pa), s (1).
    σ(y, z) = N/S − Mfz·y/Iz + Mfy·z/Iy (axes principaux) ; si |Iyz| n'est pas négligeable,
    σ = N/S + b·y + c·z avec [Iz Iyz; Iyz Iy]·[b; c] = [−Mfz; Mfy].
    Sortie : dict sigmaFun (fonction sigmaFun(y, z), y et z depuis G), coefs [a, b, c], sigmaMaxTraction,
    sigmaMaxCompression (Pa), locMaxTraction, locMaxCompression ([y, z] en m), sigmaMaxAbs, sigmaMaxKt, sigmaAdm (Pa),
    ok, neutralAxis (a, b, c et points 2×2 [y z] de l'axe neutre), usedGeneralFormula, yProfile (m),
    sigmaProfile (Pa, z = 0), report, latex.
    Extrema : sommets du contour (geometry.outline) ; sans sec, coins du rectangle englobant.
    """
    p = _struct(p)
    N = _opt(p, "N", 0.0)
    Mfz = _opt(p, "Mfz", 0.0)
    Mfy = _opt(p, "Mfy", 0.0)
    Kt = _opt(p, "Kt", 1.0)
    Re = _reqPos(p, "Re")
    s = _opt(p, "s", 1.0)
    hasSec = p.get("sec") is not None
    if hasSec:
        # propriétés déjà calculées par l'appelant (évite de refaire l'intégration du cisaillement)
        P = p["Pcore"] if p.get("Pcore") is not None else geometry.analytical(p["sec"])
    elif p.get("P") is not None:
        P = p["P"]
    else:
        raise MecaStructError(_ID + "missingField", "Il faut fournir p.sec ou p.P.")
    Iyz = P["Iyz"] if P.get("Iyz") is not None else 0.0
    general = abs(Iyz) > 1e-9 * math.sqrt(P["Iz"] * P["Iy"])
    a = N / P["S"]
    if general:
        b, c = np.linalg.solve([[P["Iz"], Iyz], [Iyz, P["Iy"]]], [-Mfz, Mfy])
    else:
        b = -Mfz / P["Iz"]
        c = Mfy / P["Iy"]

    def sig(y, z):
        return a + b * y + c * z

    # Points candidats [y z] depuis G
    if hasSec:
        sec = geometry.validateSection(p["sec"])
        out = geometry.outline(sec)
        V = np.vstack(out["outer"] + out["holes"])  # colonnes [z y]
        pts = np.column_stack([V[:, 1] - P["yG"], V[:, 0] - P["zG"]])
        if sec["type"] in ("disque", "couronne") and math.hypot(b, c) > 0:
            u = np.array([b, c]) / math.hypot(b, c)
            pts = np.vstack([pts, sec["D"] / 2 * u, -sec["D"] / 2 * u])
    else:
        pts = np.array([[y, z] for z in (P["vzRight"], -P["vzLeft"]) for y in (P["vyTop"], -P["vyBot"])])
    sv = sig(pts[:, 0], pts[:, 1])
    iMax = int(np.argmax(sv))
    iMin = int(np.argmin(sv))
    smax = float(sv[iMax])
    smin = float(sv[iMin])
    sigmaMaxAbs = max(abs(smax), abs(smin))
    sigmaMaxKt = Kt * sigmaMaxAbs
    sigmaAdm = Re / s
    ok = sigmaMaxKt <= sigmaAdm

    # Axe neutre a + b y + c z = 0
    na = {"a": a, "b": b, "c": c, "points": np.full((2, 2), math.nan)}
    yE = max(P["vyTop"], P["vyBot"])
    zE = max(P["vzRight"], P["vzLeft"])
    if abs(b) * yE >= abs(c) * zE and b != 0:
        zz = np.array([-zE, zE])
        na["points"] = np.column_stack([-(a + c * zz) / b, zz])
    elif c != 0:
        yy = np.array([-yE, yE])
        na["points"] = np.column_stack([yy, -(a + b * yy) / c])

    yProfile = np.linspace(-P["vyBot"], P["vyTop"], 101)
    if general:
        ftxt = "Formule générale (Iyz non négligeable) : σ = N/S + b·y + c·z, [Iz Iyz; Iyz Iy]·[b; c] = [−Mfz; Mfy]"
        f1 = (
            r"$\sigma_{xx} = \frac{N}{S} + b\,y + c\,z, \ \left[\begin{array}{cc} I_z & I_{yz} \\ I_{yz} & I_y "
            r"\end{array}\right] \left[\begin{array}{c} b \\ c \end{array}\right] = "
            r"\left[\begin{array}{c} -M_{fz} \\ M_{fy} \end{array}\right]$"
        )
    else:
        ftxt = "Axes principaux : σ = N/S − Mfz·y/Iz + Mfy·z/Iy"
        f1 = r"$\sigma_{xx} = \frac{N}{S} - \frac{M_{fz}}{I_z}\,y + \frac{M_{fy}}{I_y}\,z$"
    report = [
        ftxt,
        f"σ(y, z) = {_seF(a)} {_seSgn(b)}·y {_seSgn(c)}·z (Pa, y et z en m depuis G)",
        f"Traction maximale : {_seF(smax)} Pa en (y, z) = ({_seF(pts[iMax, 0])}, {_seF(pts[iMax, 1])}) m",
        f"Compression maximale : {_seF(smin)} Pa en (y, z) = ({_seF(pts[iMin, 0])}, {_seF(pts[iMin, 1])}) m",
        f"|σ|max = {_seF(sigmaMaxAbs)} Pa ; Kt·|σ|max = {_seF(sigmaMaxKt)} Pa ; "
        f"σadm = Re/s = {_seF(sigmaAdm)} Pa → {_seOk(ok)}",
        f"Axe neutre : {_seF(a)} {_seSgn(b)}·y {_seSgn(c)}·z = 0",
    ]
    latex = [
        f1,
        rf"$\sigma_{{xx}}(y,z) = {_seT(a)} {_seTs(b)}\,y {_seTs(c)}\,z$",
        rf"$\sigma_{{max}} = {_seT(smax)}, \ \sigma_{{min}} = {_seT(smin)}\,\mathrm{{Pa}}$",
        rf"$K_t\,|\sigma|_{{max}} = {_seT(sigmaMaxKt)} \le \frac{{R_e}}{{s}} = {_seT(sigmaAdm)}$",
    ]
    return {
        "sigmaFun": sig,
        "coefs": [a, b, c],
        "sigmaMaxTraction": smax,
        "sigmaMaxCompression": smin,
        "locMaxTraction": pts[iMax],
        "locMaxCompression": pts[iMin],
        "sigmaMaxAbs": sigmaMaxAbs,
        "sigmaMaxKt": sigmaMaxKt,
        "sigmaAdm": sigmaAdm,
        "ok": ok,
        "neutralAxis": na,
        "usedGeneralFormula": general,
        "yProfile": yProfile,
        "sigmaProfile": sig(yProfile, 0.0),
        "report": report,
        "latex": latex,
    }


def buckling(p: dict) -> dict:
    """Flambage : délégation à buckling.analyze(p) (module créé en E14).

    Entrée : `p` (paramètres de flambage, voir buckling.analyze). Sortie : dict de buckling.analyze.
    """
    from mecastruct.core.buckling import analyze  # import tardif : évite l'import circulaire avec buckling.py

    return analyze(p)
