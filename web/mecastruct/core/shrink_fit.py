"""Frettage (assemblage serré arbre / moyeu) : pression de Lamé, serrage normalisé et température de chauffe.

Port du classeur « Calculs de frettage normalises.xlsm » de l'auteur (NF E22-620). Son module de calcul était
illisible : la méthode a été reconstruite et retombe sur toutes les valeurs enregistrées dans le classeur
(K, p mini, p maxi, contraintes équivalentes, ΔT : voir tests/test_shrink_fit.py).
"""

import math

from mecastruct.core import fits
from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import load_json

_ID = "MecaStruct:ShrinkFit:invalidInput"
# arbres possibles pour un serrage avec alésage normal H, du moins au plus serré
LETTRES_SERRAGE = ("k", "m", "n", "p", "r", "s", "t", "u", "v", "x", "y", "z", "za", "zb", "zc")


def normValues(d: float) -> dict | None:
    """Valeurs conseillées par la norme pour le diamètre d (mm) : qualités, Ra, lissage (µm), jeu de montage (mm).

    Renvoie None au-delà de la dernière ligne de la table (630 mm) : la norme ne donne alors aucune valeur.
    """
    for li in load_json("shrink_fit_norm.json")["Lignes"]:
        if d <= li["d"]:
            return li
    return None


def _pos(p: dict, k: str, quoi: str) -> float:
    v = p.get(k)
    if v is None or not math.isfinite(v) or v <= 0:
        raise MecaStructError(_ID, f"{quoi} doit être strictement positif (reçu : {v}).")
    return float(v)


def shrinkFit(p: dict) -> dict:
    """Liaison frettée arbre / moyeu à alésage normal H : serrage nécessaire, ajustement normalisé, vérifications.

    Entrées (dict) : Fa (N), C (N·m), f (coefficient d'adhérence), s (coefficient de sécurité sur l'effort),
    d, di, D, L (mm : diamètre de frettage, intérieur de l'arbre, extérieur du moyeu, longueur frettée) ;
    Ea, nua, Rea (arbre : Pa, 1, Pa) ; Em, num, Rem, alpham (moyeu : Pa, 1, Pa, 1/K) ; qa, qm (qualités IT de
    l'arbre et du moyeu) ; lissage (µm) ; jeu (mm, jeu de montage à chaud).
    Sortie : dict R (N), pMin, K, serrageUtile (µm), eiRequis (µm), arbre (lettre retenue), fit (sortie de
    fits.fit), pMinNorm, pMax (MPa), sigmaArbre, sigmaMoyeu (MPa), sArbre, sMoyeu, couple (N·m transmissible au
    serrage mini), deltaT (K), report, latex.
    Erreur : MecaStruct:ShrinkFit:invalidInput.
    """
    d, D, L = _pos(p, "d", "d"), _pos(p, "D", "D"), _pos(p, "L", "L")
    di = float(p.get("di") or 0.0)
    if not 0 <= di < d < D:
        raise MecaStructError(_ID, f"Il faut 0 ≤ di < d < D (di = {di:g}, d = {d:g}, D = {D:g} mm).")
    f, s = _pos(p, "f", "Le coefficient d'adhérence"), _pos(p, "s", "Le coefficient de sécurité")
    Fa, C = abs(float(p.get("Fa") or 0.0)), abs(float(p.get("C") or 0.0))
    Ea, Em = _pos(p, "Ea", "E arbre") / 1e6, _pos(p, "Em", "E moyeu") / 1e6  # MPa
    nua, num = float(p["nua"]), float(p["num"])
    lissage, jeu = float(p.get("lissage") or 0.0), float(p.get("jeu") or 0.0)
    qa, qm = int(p["qa"]), int(p["qm"])

    Ft = 2 * C * 1e3 / d  # N (C en N·mm sur le rayon d/2)
    R = s * math.hypot(Ft, Fa)
    pMin = R / (f * math.pi * d * L)  # MPa
    ka, km = di / d, d / D
    K = (1 / Ea) * ((1 + ka**2) / (1 - ka**2) - nua) + (1 / Em) * ((1 + km**2) / (1 - km**2) + num)  # 1/MPa
    serrageUtile = pMin * K * d * 1e3  # µm
    hole = fits.holeDeviations(d, "H", qm)
    eiRequis = hole["ES"] + serrageUtile + lissage
    arbre = None
    for lettre in LETTRES_SERRAGE:
        try:
            if fits.shaftDeviations(d, lettre, qa)["ei"] >= eiRequis:
                arbre = lettre
                break
        except MecaStructError:  # écart inexistant pour ce diamètre : lettre suivante
            continue
    if arbre is None:
        raise MecaStructError(
            _ID,
            f"Aucun arbre normalisé de qualité {qa} ne donne ei ≥ {eiRequis:.4g} µm : augmentez la longueur frettée, "
            "le diamètre ou le coefficient d'adhérence.",
        )
    ft = fits.fit(d, "H", qm, arbre, qa)
    pMinNorm = (ft["serrageMin"] - lissage) / (K * d * 1e3)
    pMax = ft["serrageMax"] / (K * d * 1e3)  # sans retrancher le lissage : pression maxi majorée
    sigmaArbre = 2 * pMax / (1 - ka**2)
    sigmaMoyeu = pMax * math.sqrt(3 + km**4) / (1 - km**2)
    Rea, Rem = p.get("Rea"), p.get("Rem")
    sArbre = Rea / 1e6 / sigmaArbre if Rea else None
    sMoyeu = Rem / 1e6 / sigmaMoyeu if Rem else None
    couple = f * pMinNorm * math.pi * d * L * d / 2 / 1e3  # N·m
    alpham = _pos(p, "alpham", "Le coefficient de dilatation du moyeu")
    deltaT = (ft["serrageMax"] / 1e3 + jeu) / (d * alpham)
    nom = f"H{qm}/{arbre}{qa}"
    report = [
        f"Effort à transmettre : R = s·√((2C/d)² + Fa²) = {s:g}·√({Ft:.5g}² + {Fa:.5g}²) = {R:.5g} N",
        f"Pression mini : p = R/(f·π·d·L) = {pMin:.5g} MPa",
        f"Coefficient de Lamé : K = {K:.5g} 1/MPa ; serrage utile = p·K·d = {serrageUtile:.4g} µm",
        f"Écart inférieur requis de l'arbre : ei ≥ ES + serrage utile + lissage = {hole['ES']:g} + {serrageUtile:.4g} "
        f"+ {lissage:g} = {eiRequis:.4g} µm → ajustement normalisé {nom} (ei = {ft['shaft']['ei']:g} µm)",
        f"Serrages normalisés : {ft['serrageMin']:g} à {ft['serrageMax']:g} µm ; p mini normalisée = "
        f"{pMinNorm:.4g} MPa "
        f"(couple transmissible {couple:.4g} N·m) ; p maxi = {pMax:.4g} MPa",
        f"Contrainte équivalente arbre 2p/(1 − (di/d)²) = {sigmaArbre:.4g} MPa"
        + (f", coefficient de sécurité Re/σ = {sArbre:.3g}" if sArbre else ""),
        f"Contrainte équivalente moyeu (Von Mises à l'alésage) = {sigmaMoyeu:.4g} MPa"
        + (f", coefficient de sécurité Re/σ = {sMoyeu:.3g}" if sMoyeu else ""),
        f"Température de chauffe du moyeu : ΔT = (serrage maxi + jeu)/(d·α) = {deltaT:.4g} K",
    ]
    latex = [
        rf"R = s\sqrt{{\left(\frac{{2C}}{{d}}\right)^2 + F_a^2}} = {s:g}\sqrt{{{Ft:.5g}^2 + {Fa:.5g}^2}}"
        rf" = {R:.5g}\ \mathrm{{N}}",
        rf"p_{{min}} = \frac{{R}}{{f\,\pi\,d\,L}} = \frac{{{R:.5g}}}{{{f:g}\times\pi\times{d:g}\times{L:g}}}"
        rf" = {pMin:.5g}\ \mathrm{{MPa}}",
        rf"K = \frac{{1}}{{E_a}}\left(\frac{{1+q_a^2}}{{1-q_a^2}} - \nu_a\right) "
        rf"+ \frac{{1}}{{E_m}}\left(\frac{{1+q_m^2}}"
        rf"{{1-q_m^2}} + \nu_m\right) = {K:.5g}\ \mathrm{{MPa^{{-1}}}},\ q_a = {ka:.4g},\ q_m = {km:.4g}",
        rf"\delta_{{utile}} = p_{{min}}\,K\,d = {pMin:.5g}\times{K:.5g}\times{d:g}"
        rf" = {serrageUtile / 1e3:.5g}\ \mathrm{{mm}}",
        rf"ei \ge ES + \delta_{{utile}} + \text{{lissage}}"
        rf" = {hole['ES']:g} + {serrageUtile:.4g} + {lissage:g} = {eiRequis:.4g}\ \mu m",
        rf"p_{{max}} = \frac{{\delta_{{max}}}}{{K\,d}}"
        rf" = \frac{{{ft['serrageMax'] / 1e3:g}}}{{{K:.5g}\times{d:g}}} = {pMax:.5g}\ \mathrm{{MPa}}",
        rf"\sigma_{{eq,moyeu}} = p_{{max}}\frac{{\sqrt{{3 + q_m^4}}}}{{1 - q_m^2}} = {sigmaMoyeu:.5g}\ \mathrm{{MPa}}",
        rf"\Delta T = \frac{{\delta_{{max}} + j}}{{d\,\alpha_m}}"
        rf" = \frac{{{ft['serrageMax'] / 1e3:g} + {jeu:g}}}{{{d:g}\times{alpham:g}}} = {deltaT:.5g}\ \mathrm{{K}}",
    ]
    return {
        "R": R,
        "pMin": pMin,
        "K": K,
        "serrageUtile": serrageUtile,
        "eiRequis": eiRequis,
        "arbre": arbre,
        "fit": ft,
        "pMinNorm": pMinNorm,
        "pMax": pMax,
        "sigmaArbre": sigmaArbre,
        "sigmaMoyeu": sigmaMoyeu,
        "sArbre": sArbre,
        "sMoyeu": sMoyeu,
        "couple": couple,
        "deltaT": deltaT,
        "report": report,
        "latex": latex,
    }
