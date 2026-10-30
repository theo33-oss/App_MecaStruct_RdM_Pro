"""Enregistrer / ouvrir un problème ou un projet (JSON) et exporter les tableaux de résultats (xlsx, csv).

Port de saveProblem, loadProblem, saveProject, loadProject, exportResults, resultSheets et beamEffortSheets de
MecaStruct_App.m. Écart assumé : les fichiers sont des JSON (lisibles, sans pickle) et non des .mat ; les champs
sont repérés par leur nom (comme matchInputs). Aucun import de streamlit.
"""

import io
import json
import re
import zipfile

import numpy as np
import pandas as pd

from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import ppEval

APP = "MecaStruct RdM Pro"
FORMAT_VERSION = 1
PROJECT_KEYS = ("Sec", "Beam", "Tr", "Tra", "Cis", "Tor", "Fle", "Fla", "Ten", "Hoo", "Jau")  # projectKeys

_ID = "MecaStruct:App:badProblemFile"
_CARACTERES_INTERDITS = re.compile(r"[\[\]:*?/\\]")


def _json(obj) -> str:
    """JSON lisible : tableaux NumPy et DataFrame convertis en listes."""

    def defaut(o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, pd.DataFrame):
            return o.to_dict("records")
        raise TypeError(f"{type(o).__name__} n'est pas enregistrable")

    return json.dumps(obj, ensure_ascii=False, indent=2, default=defaut)


def _lit(text: str, nature: str) -> dict:
    """Décode un fichier JSON MecaStruct : dict de l'application, version comprise, sinon badProblemFile."""
    try:
        d = json.loads(text)
    except ValueError as err:
        raise MecaStructError(_ID, f"Ce fichier n'est pas {nature} MecaStruct (JSON illisible : {err}).") from err
    if not isinstance(d, dict) or d.get("app") != APP:
        raise MecaStructError(_ID, f"Ce fichier n'est pas {nature} enregistré par {APP}.")
    if not isinstance(d.get("version"), int) or d["version"] > FORMAT_VERSION:
        raise MecaStructError(_ID, "Ce fichier date d'une autre version de l'application (format non reconnu).")
    return d


def problemToJson(tab: str, saisie: dict) -> str:
    """JSON d'un problème : la saisie de l'onglet `tab` (unités d'affichage), avec l'application et la version."""
    return _json({"app": APP, "version": FORMAT_VERSION, "onglet": tab, "saisie": saisie})


def problemFromJson(text: str, tab: str | None = None) -> tuple[str, dict]:
    """Relit un problème : renvoie (onglet, saisie). Si `tab` est donné, le fichier doit venir de cet onglet.

    Erreur : MecaStruct:App:badProblemFile (fichier étranger, version inconnue ou onglet différent).
    """
    d = _lit(text, "un problème")
    if d.get("onglet") not in PROJECT_KEYS or not isinstance(d.get("saisie"), dict):
        raise MecaStructError(_ID, "Ce fichier n'est pas un problème enregistré depuis un onglet de calcul.")
    if tab is not None and d["onglet"] != tab:
        raise MecaStructError(
            _ID,
            f"Ce fichier n'est pas un problème enregistré depuis cet onglet (il vient de l'onglet « {d['onglet']} »).",
        )
    return d["onglet"], d["saisie"]


def projectToJson(saisies: dict[str, dict]) -> str:
    """JSON d'un projet : la saisie de chaque onglet de PROJECT_KEYS (clés absentes de `saisies` : erreur)."""
    return _json({"app": APP, "version": FORMAT_VERSION, "projet": {k: saisies[k] for k in PROJECT_KEYS}})


def projectFromJson(text: str) -> tuple[dict[str, dict], list[str]]:
    """Relit un projet : renvoie (saisies des onglets relus, onglets non relus car absents ou illisibles)."""
    d = _lit(text, "un projet")
    projet = d.get("projet")
    if not isinstance(projet, dict):
        raise MecaStructError(_ID, "Ce fichier n'est pas un projet MecaStruct.")
    saisies = {k: projet[k] for k in PROJECT_KEYS if isinstance(projet.get(k), dict)}
    return saisies, [k for k in PROJECT_KEYS if k not in saisies]


def beamEffortSheets(sol: dict) -> dict[str, pd.DataFrame]:
    """Feuilles « Enveloppe » (max / min de chaque effort) et « Efforts » (valeurs le long de la poutre), kN et kN·m.

    Entrée : `sol` (solveBeam, SI). Sortie : dict nom → DataFrame, mêmes colonnes que MATLAB.
    """
    comps = ("N", "Ty", "Tz", "Mt", "Mfy", "Mfz")
    unites = ("kN", "kN", "kN", "kN·m", "kN·m", "kN·m")
    ext = [sol["extrema"][c] for c in comps]
    env = pd.DataFrame(
        {
            "Effort": comps,
            "Unité": unites,
            "Max": [e["max"] / 1e3 for e in ext],
            "s du max (m)": [e["sMax"] for e in ext],
            "Min": [e["min"] / 1e3 for e in ext],
            "s du min (m)": [e["sMin"] for e in ext],
        }
    )
    breaks = np.asarray(sol["N"].breaks, dtype=float)
    s = np.unique(np.concatenate([np.linspace(0.0, breaks[-1], 201), breaks]))
    eff = pd.DataFrame({"s (m)": s})
    for c, u in zip(comps, unites, strict=True):
        eff[f"{c} ({u})"] = ppEval(sol[c], s) / 1e3
    return {"Enveloppe": env, "Efforts": eff}


def resultSheets(tab: str, res: dict) -> dict[str, pd.DataFrame]:
    """Tableaux exportables d'un résultat (tables non vides) ; pour Beam, plus « Enveloppe » et « Efforts ».

    Entrées : `tab` (onglet) ; `res` (dernier résultat de l'onglet, avec la clé "tables").
    Sortie : dict nom → DataFrame, noms de feuille de 31 caractères au plus, sans [ ] : * ? / \\ et distincts.
    """
    brut = {nom: t for nom, t in res.get("tables", {}).items() if len(t) > 0}
    if tab == "Beam" and "sol" in res:
        brut.update(beamEffortSheets(res["sol"]))
    sheets: dict[str, pd.DataFrame] = {}
    for nom, t in brut.items():
        court = _CARACTERES_INTERDITS.sub(" ", nom).strip()[:31].strip()
        base, k = court, 1
        while court in sheets:  # deux titres qui ne diffèrent qu'après le 31e caractère
            k += 1
            court = f"{base[: 31 - len(str(k)) - 1]}_{k}"
        sheets[court] = t
    return sheets


def toXlsx(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Classeur Excel (.xlsx) : une feuille par tableau. Erreur : MecaStruct:App:noResults si `sheets` est vide."""
    _nonVide(sheets)
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as writer:
        for nom, t in sheets.items():
            t.to_excel(writer, sheet_name=nom, index=False)
    return tampon.getvalue()


def toCsvZip(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Archive .zip d'un CSV par tableau (séparateur « ; », décimale « , », UTF-8 avec BOM pour Excel)."""
    _nonVide(sheets)
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, t in sheets.items():
            z.writestr(f"{nom}.csv", t.to_csv(sep=";", decimal=",", index=False, encoding="utf-8-sig"))
    return tampon.getvalue()


def _nonVide(sheets: dict) -> None:
    if not sheets:
        raise MecaStructError(
            "MecaStruct:App:noResults", "Aucun résultat à exporter : cliquez d'abord sur « Calculer »."
        )
