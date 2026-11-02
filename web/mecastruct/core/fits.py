"""Écarts normalisés ISO 286 et ajustements arbre / alésage (tables de web/data/iso286.json).

Port du classeur « ecarts-normalises.xlsm » de l'auteur, avec les règles de l'ISO 286-1 que ses macros
appliquaient mal : colonne j ou k selon la qualité, correction Δ pour K, M, N (qualités ≤ 8) et P à ZC (≤ 7).
"""

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import load_json

LETTRES_ARBRE = ("a", "b", "c", "cd", "d", "e", "ef", "f", "fg", "g", "h", "js", "j", "k", "m", "n", "p", "r", "s",
                 "t", "u", "v", "x", "y", "z", "za", "zb", "zc")  # fmt: skip
LETTRES_ALESAGE = tuple(x.upper() for x in LETTRES_ARBRE)
QUALITES = tuple(range(1, 19))
_ID = "MecaStruct:Fits:invalidInput"


def _table() -> dict:
    return load_json("iso286.json")


def _ligne(t: dict, d: float) -> int:
    """Indice de la plage de diamètre contenant d (mm) : première borne supérieure ≥ d."""
    if not 0 < d <= t["bornes"][-1]:
        raise MecaStructError(_ID, f"Diamètre nominal hors des tables ISO 286 : {d:g} mm (0 < d ≤ 3150 mm).")
    return next(i for i, b in enumerate(t["bornes"]) if d <= b)


def _it(t: dict, i: int, q: int) -> float:
    if q not in QUALITES:
        raise MecaStructError(_ID, f"Qualité IT{q} hors des tables (1 à 18).")
    return t["it"][str(q)][i]


def _val(v, quoi: str) -> float:
    if v is None:
        raise MecaStructError(_ID, f"{quoi} n'existe pas dans l'ISO 286 pour ce diamètre.")
    return v


def _js(it: float, q: int) -> float:
    """Demi-intervalle de js/JS : IT/2, IT ramené au pair inférieur s'il est impair pour les qualités 7 à 11."""
    if 7 <= q <= 11 and it % 2 == 1:
        it -= 1
    return it / 2


def shaftDeviations(d: float, lettre: str, q: int) -> dict:
    """Écarts d'un arbre ISO 286 (ex. « r », 6) pour le diamètre nominal d.

    Entrées : d (mm), lettre (a à zc, js), q (qualité 1 à 18).
    Sortie : dict es, ei, IT (µm), plage (texte), fondamental (« es » ou « ei », écart lu dans la table).
    Erreur : MecaStruct:Fits:invalidInput (diamètre, lettre ou qualité hors table, écart inexistant).
    """
    t = _table()
    if lettre not in LETTRES_ARBRE:
        raise MecaStructError(_ID, f"Position d'arbre inconnue : {lettre!r}.")
    i = _ligne(t, d)
    it = _it(t, i, q)
    nom = f"{lettre}{q}"
    if lettre == "js":
        es, ei, fond = _js(it, q), -_js(it, q), "es"
    elif LETTRES_ARBRE.index(lettre) <= LETTRES_ARBRE.index("h"):
        es = _val(t["arbre"][lettre][i], nom)
        ei, fond = es - it, "es"
    else:
        if lettre == "j":
            col = {5: "j5-6", 6: "j5-6", 7: "j7", 8: "j8"}.get(q)
            if col is None:
                raise MecaStructError(_ID, f"{nom} n'existe pas : j est défini pour les qualités 5 à 8.")
        elif lettre == "k":
            col = "k4-7" if 4 <= q <= 7 else "k"
        else:
            col = lettre
        ei = _val(t["arbre"][col][i], nom)
        es, fond = ei + it, "ei"
    return {"es": es, "ei": ei, "IT": it, "plage": _plage(t, i), "fondamental": fond}


def holeDeviations(d: float, lettre: str, q: int) -> dict:
    """Écarts d'un alésage ISO 286 (ex. « H », 7) pour le diamètre nominal d.

    Entrées : d (mm), lettre (A à ZC, JS), q (qualité 1 à 18).
    Sortie : dict ES, EI, IT, delta (µm, correction Δ ajoutée à ES, 0 sinon), plage, fondamental (« EI » ou « ES »).
    Erreur : MecaStruct:Fits:invalidInput.
    """
    t = _table()
    if lettre not in LETTRES_ALESAGE:
        raise MecaStructError(_ID, f"Position d'alésage inconnue : {lettre!r}.")
    i = _ligne(t, d)
    it = _it(t, i, q)
    nom = f"{lettre}{q}"
    delta = 0.0
    if lettre == "JS":
        ES, EI, fond = _js(it, q), -_js(it, q), "EI"
    elif LETTRES_ALESAGE.index(lettre) <= LETTRES_ALESAGE.index("H"):
        EI = _val(t["alesage"][lettre][i], nom)
        ES, fond = EI + it, "EI"
    else:
        if lettre == "J":
            if q not in (6, 7, 8):
                raise MecaStructError(_ID, f"{nom} n'existe pas : J est défini pour les qualités 6 à 8.")
            col = f"J{q}"
        elif lettre in ("K", "M", "N"):
            col = f"{lettre}<=8" if q <= 8 else lettre
        else:
            col = lettre
        ES = _val(t["alesage"][col][i], nom)
        avec_delta = (lettre in ("K", "M", "N") and 3 <= q <= 8) or (
            LETTRES_ALESAGE.index(lettre) >= LETTRES_ALESAGE.index("P") and 3 <= q <= 7
        )
        if avec_delta:
            delta = _val(t["delta"][str(q)][i], f"Δ pour {nom}")
            ES += delta
        EI, fond = ES - it, "ES"
    return {"ES": ES, "EI": EI, "IT": it, "delta": delta, "plage": _plage(t, i), "fondamental": fond}


def _plage(t: dict, i: int) -> str:
    bas = 0 if i == 0 else t["bornes"][i - 1]
    return f"au-delà de {bas:g} jusqu'à {t['bornes'][i]:g} mm"


def fit(d: float, alesage: str, qa: int, arbre: str, qb: int) -> dict:
    """Ajustement alésage / arbre (ex. H7/r6) : écarts, cotes limites, jeux et serrages, type.

    Entrées : d (mm) ; alesage, qa (position et qualité de l'alésage) ; arbre, qb (de l'arbre).
    Sortie : dict hole, shaft (sorties de holeDeviations / shaftDeviations), jeuMax, jeuMin (µm, négatif = serrage),
    serrageMax, serrageMin (µm), type (« avec jeu », « serré », « incertain »), cotes (mm : alésage min/max, arbre
    min/max), moyennes (mm), report, latex.
    """
    h, s = holeDeviations(d, alesage, qa), shaftDeviations(d, arbre, qb)
    jmax, jmin = h["ES"] - s["ei"], h["EI"] - s["es"]
    if jmin >= 0:
        typ = "avec jeu"
    elif jmax <= 0:
        typ = "serré"
    else:
        typ = "incertain"
    cotes = {
        "alesageMin": d + h["EI"] / 1000,
        "alesageMax": d + h["ES"] / 1000,
        "arbreMin": d + s["ei"] / 1000,
        "arbreMax": d + s["es"] / 1000,
    }
    nom = f"{d:g} {alesage}{qa}/{arbre}{qb}"
    report = [
        f"Ajustement {nom} ({h['plage']}).",
        f"Alésage {alesage}{qa} : IT{qa} = {h['IT']:g} µm ; ES = {h['ES']:+g} µm ; EI = {h['EI']:+g} µm"
        + (f" (Δ = {h['delta']:g} µm ajouté à ES)" if h["delta"] else ""),
        f"Arbre {arbre}{qb} : IT{qb} = {s['IT']:g} µm ; es = {s['es']:+g} µm ; ei = {s['ei']:+g} µm",
        f"Jeu maxi = ES − ei = {jmax:+g} µm ; jeu mini = EI − es = {jmin:+g} µm → ajustement {typ}",
    ]
    latex = [
        rf"J_{{max}} = ES - ei = {h['ES']:g} - ({s['ei']:g}) = {jmax:g}\ \mu m",
        rf"J_{{min}} = EI - es = {h['EI']:g} - ({s['es']:g}) = {jmin:g}\ \mu m",
    ]
    return {
        "hole": h,
        "shaft": s,
        "jeuMax": jmax,
        "jeuMin": jmin,
        "serrageMax": -jmin,
        "serrageMin": -jmax,
        "type": typ,
        "cotes": cotes,
        "moyennes": {
            "alesage": (cotes["alesageMin"] + cotes["alesageMax"]) / 2,
            "arbre": (cotes["arbreMin"] + cotes["arbreMax"]) / 2,
        },  # fmt: skip
        "report": report,
        "latex": latex,
    }
