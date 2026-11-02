"""Dossier de validation HTML d'un problème (port de ValidationReport.m, sans findBrowser ni toPDF).

Pour chaque page de calcul, `recompute` refait le calcul, puis `generate` écrit un fichier HTML autonome en 8 parties :
1. données saisies ; 2. hypothèses et contrôles d'applicabilité chiffrés ; 3. équations avec valeurs recalculées à la
main (sans le solveur) puis comparées au solveur ; 4. tableaux de résultats ; 5. diagrammes ; 6. rapport détaillé du
solveur ; 7. formules utilisées ; 8. grille d'avis du relecteur.

Clés : 'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau' (celles de project_io.PROJECT_KEYS).
`res` est le résultat de l'onglet (sortie de computeXxx) ; `res["extras"]` porte les résultats facultatifs :
Poutres : combos (DataFrame), ec3 et fatigue (tuples (r, T) de beam_design), profiles ((T, best)) ;
Cisaillement : key et pin (sorties de computeKey et computePin). Aucun import de streamlit.
"""

import html
import math
import platform
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from scipy.integrate import quad

from mecastruct.core import data_manager, geometry
from mecastruct.core.beam_solver import solveBeam
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import asPP, ppEval
from mecastruct.services import beam_design, beam_services, compute
from mecastruct.services.beam_services import buildBeamModel

KEYS = ("Sec", "Beam", "Tr", "Tra", "Cis", "Tor", "Fle", "Fla", "Ten", "Hoo", "Jau")

_TEMPLATES = Path(__file__).parent / "templates"
_NAN = float("nan")

# Tolérance par défaut d'un contrôle à la main : relative 1e-6, plus un plancher absolu (handHTML de MATLAB)
_TOL_REL = 1e-6
_TOL_ABS = 1e-12

_SECTIONS = (
    ("donnees", "1. Données du problème"),
    ("hypotheses", "2. Hypothèses du modèle et applicabilité"),
    ("verif", "3. Équations et vérification indépendante"),
    ("resultats", "4. Résultats du solveur"),
    ("diagrammes", "5. Diagrammes"),
    ("rapport", "6. Rapport détaillé du solveur (étapes de calcul)"),
    ("formules", "7. Formules utilisées pour ce calcul"),
    ("avis", "8. Avis du relecteur"),
)


# ---------------------------------------------------------------------------------------------------- Méta


def meta(key: str) -> dict:
    """Titre, onglet, calculs à relancer et fiches de formules de la zone de travail `key`.

    Entrée : `key` (KEYS). Sortie : dict title, sel (page), calls (fonctions de compute relancées), forms (fiches de
    formules), keep (titres des formules retenues au §7). Erreur : MecaStruct:Validation:unknownKey.
    """
    d = {
        "Sec": ("Section droite", "Sections", ["computeSection"], ["geometrie"]),
        "Beam": (
            "Poutre",
            "Poutres",
            ["computeBeam"],
            ["equilibre", "cohesion", "deformee", "energie", "mohr_integrales"],
        ),
        "Tr": ("Treillis", "Treillis", ["computeTruss"], ["treillis"]),
        "Tra": ("Traction-compression", "Traction", ["computeTraction"], ["traction"]),
        "Cis": (
            "Cisaillement et matage",
            "Cisaillement",
            ["computeShear", "computeKey", "computePin"],
            ["cisaillement", "matage"],
        ),
        "Tor": ("Torsion", "Torsion", ["computeTorsion"], ["torsion"]),
        "Fle": ("Flexion", "Flexion", ["computeBending"], ["flexion"]),
        "Fla": ("Flambage", "Flambage", ["computeBuckling"], ["flambage"]),
        "Ten": ("Tenseurs et criteres", "Tenseurs", ["computeTensor"], ["tenseurs", "mohr_cercle", "criteres"]),
        "Hoo": ("Loi de Hooke", "Hooke", ["computeHooke"], ["hooke"]),
        "Jau": ("Jauges et rosettes", "Jauges", ["computeGauges"], ["extensometrie"]),
    }
    if key not in d:
        raise MecaStructError("MecaStruct:Validation:unknownKey", f"Zone de travail inconnue : {key}")
    title, sel, calls, forms = d[key]
    keep = {
        "Sec": [
            "Aire de la section",
            "Centre de surface G",
            "Moments quadratiques en G",
            "Théorème de Huygens",
            "Modules de flexion",
        ],
        "Beam": [
            "Principe fondamental de la statique",
            "Degré d'hyperstatisme",
            "Composantes du torseur de cohésion",
            "Relations différentielles",
            "Équation de la déformée",
            "Conditions aux limites",
            "Théorème de Ménabréa",
        ],
        "Tr": [
            "Équilibre du nœud i (méthode des nœuds)",
            "Degré d'hyperstatisme",
            "Contrainte normale",
            "Allongement d'une barre",
        ],
        "Tra": [
            "Contrainte normale",
            "Concentration de contrainte et condition de résistance",
            "Allongement : méthode analytique",
            "Condition de rigidité",
        ],
        "Cis": [
            "Contrainte tangentielle moyenne",
            "Contrainte maximale et condition de résistance",
            "Pression de matage",
            "Clavette : matage",
            "Clavette : cisaillement",
            "Rivet ou goupille : cisaillement",
        ],
        "Tor": [
            "Contrainte tangentielle",
            "Condition de résistance",
            "Rotation : méthode analytique",
            "Moment quadratique polaire",
            "Puissance transmise",
        ],
        "Fle": ["Flexion simple", "Condition de résistance", "Axe neutre", "Flexion composée"],
        "Fla": [
            "Longueurs de flambement",
            "Élancement",
            "Élancement limite",
            "Charge critique d'Euler (λ ≥ λlim)",
            "Formule de Rankine (20 ≤ λ < λlim)",
            "Charge admissible",
        ],
        "Ten": [
            "Contraintes principales planes",
            "Rayon du cercle de Mohr",
            "Critère de Tresca",
            "Critère de Von Mises",
            "Coefficient de sécurité obtenu",
        ],
        "Hoo": ["Loi de Hooke 3D isotrope", "Contraintes planes", "Variation de volume", "Relations entre constantes"],
        "Jau": [
            "Loi de la jauge (Bridgman)",
            "Quart de pont",
            "Rosette à 45°",
            "Rosette à 60° (delta)",
            "Déformations principales",
            "Contraintes (état plan de contrainte)",
        ],
    }[key]
    return {"title": title, "sel": sel, "calls": calls, "forms": forms, "keep": keep}


# --------------------------------------------------------------------------------------------------- Outils


def _esc(x) -> str:
    """Échappe &, < et > pour le HTML."""
    return html.escape(str(x), quote=False)


def _num(x) -> str:
    """Nombre en %.6g (formule avec valeurs)."""
    return f"{x:.6g}"


def _mj(latex: str) -> str:
    """Formule en ligne pour MathJax (le LaTeX est échappé pour le HTML)."""
    return "$" + _esc(latex) + "$"


def _oui(v) -> str:
    return "oui" if v else "non"


def _cell(v) -> str:
    """Texte d'une cellule de tableau (comme tableHTML de MATLAB : %.6g pour un nombre, oui / non pour un booléen)."""
    if isinstance(v, (bool, np.bool_)):
        return _oui(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        if isinstance(v, (float, np.floating)):
            if math.isnan(v):
                return "NaN"
            if math.isinf(v):
                return "Inf" if v > 0 else "-Inf"
        return f"{v:.6g}"
    return str(v)


def _tableHTML(t: pd.DataFrame, lignes: bool = False) -> str:
    """Tableau HTML d'un DataFrame (titres de colonnes, cellules formatées)."""
    if t is None or len(t) == 0:
        return '<p class="muted">(tableau vide)</p>'
    h = '<table class="data"><tr>'
    if lignes:
        h += "<th></th>"
    h += "".join(f"<th>{_esc(c)}</th>" for c in t.columns) + "</tr>"
    for idx, row in zip(t.index, t.itertuples(index=False), strict=True):
        h += "<tr>" + (f"<th>{_esc(idx)}</th>" if lignes else "")
        h += "".join(f"<td>{_esc(_cell(v))}</td>" for v in row) + "</tr>"
    return h + "</table>"


def _chemin(res: dict, chemin: str):
    """Valeur d'un chemin « a.b.c » dans des dict imbriqués, None s'il manque un maillon."""
    s = res
    for p in chemin.split("."):
        if isinstance(s, dict) and p in s:
            s = s[p]
        else:
            return None
    return s


def _sure(fn, *args) -> str:
    """Un bloc qui échoue ne doit pas empêcher la génération du dossier (safe de MATLAB)."""
    try:
        return fn(*args)
    except Exception as err:
        return f'<p class="warnbox">Section indisponible : {_esc(err)}</p>'


def _extras(res: dict) -> dict:
    return res.get("extras") or {}


def _sec(saisie: dict) -> dict | None:
    return saisie.get("section")


# ------------------------------------------------------------------------------------ 1. Données du problème


def _kv(titre: str | None, lignes: list[tuple[str, str]]) -> str:
    h = f"<h3>{_esc(titre)}</h3>" if titre else ""
    h += '<table class="kv">'
    for lib, val in lignes:
        h += f'<tr><td>{_esc(lib)}</td><td class="v">{_esc(val)}</td></tr>'
    return h + "</table>"


def _val(v, choix: dict | None = None) -> str:
    """Valeur d'un champ de saisie : oui / non, libellé du choix, %.6g, ou texte."""
    if isinstance(v, (bool, np.bool_)):
        return _oui(v)
    if choix and v in choix:
        return str(choix[v])
    if isinstance(v, (int, float, np.integer, np.floating)):
        return f"{v:.6g}"
    return str(v)


def _champs(saisie: dict, champs: list[tuple]) -> list[tuple[str, str]]:
    """Lignes (libellé, valeur unité) des champs (champ, libellé, unité[, choix[, condition]])."""
    out = []
    for c in champs:
        champ, lib, unite = c[0], c[1], c[2]
        choix = c[3] if len(c) > 3 else None
        if len(c) > 4 and not c[4](saisie):
            continue  # champ inactif dans l'interface : non reporté (comme Enable = 'off' de MATLAB)
        if champ not in saisie:
            continue
        v = _val(saisie[champ], choix)
        out.append((lib, f"{v} {unite}".strip() if unite and unite != "-" else v))
    return out


def _tableSaisie(titre: str, lignes: list[dict], colonnes: dict) -> str:
    """Tableau de saisie (liste de dict) avec des titres de colonnes lisibles."""
    if not lignes:
        return f'<h3>{_esc(titre)}</h3><p class="muted">(tableau vide)</p>'
    t = pd.DataFrame([{h: ligne.get(c, "") for c, h in colonnes.items()} for ligne in lignes])
    return f"<h3>{_esc(titre)}</h3>" + _tableHTML(t)


_CRITERES = {"Tresca": "Tresca (τe = Re/2)", "VonMises": "Von Mises (τe = Re/√3)"}
_TYPES_SECTION = {
    "rectangle": "Rectangle",
    "disque": "Disque",
    "couronne": "Couronne",
    "rectangle_creux": "Rectangle creux",
    "I": "Profil en I",
    "T": "Profil en T",
    "U": "Profil en U",
    "L": "Cornière en L",
    "profile": "Profilé du catalogue",
    "composite": "Section composée",
}
_APPUIS = {
    "appui_simple": "appui simple",
    "rotule": "rotule",
    "pivot": "pivot",
    "pivot_glissant": "pivot glissant",
    "encastrement": "encastrement",
}


def _sectionUtilisee(saisie: dict) -> str:
    sec = _sec(saisie)
    if sec is None:
        return ""
    lignes = [("Section", compute._sectionLabel(sec))]
    P = geometry.analytical(sec)
    lignes += [
        ("Aire S", f"{P['S'] * 1e6:.6g} mm²"),
        ("Iz", f"{P['Iz'] * 1e12:.6g} mm⁴"),
        ("Iy", f"{P['Iy'] * 1e12:.6g} mm⁴"),
    ]
    return _kv("Section utilisée (onglet Sections)", lignes)


def _inputsHTML(key: str, saisie: dict) -> str:
    """Partie 1 : champs de saisie de l'onglet, groupés comme dans l'interface."""
    s = saisie
    sig = "Coefficient de sécurité s"
    if key == "Sec":
        t = s["type"]
        g = [("type", "Type de section", "", _TYPES_SECTION)]
        if t == "profile":
            g += [("fam", "Famille de profilé", ""), ("prof", "Profilé du catalogue", "")]
        else:
            g += [(c, c, "mm") for c in compute._DIMS_SECTION.get(t, ())]
        h = _kv("Section", _champs(s, g))
        if t == "composite":
            col = {"z1": "z1 (mm)", "z2": "z2 (mm)", "y1": "y1 (mm)", "y2": "y2 (mm)"}
            h += _tableSaisie("Rectangles additifs", s["rects"], col)
            h += _tableSaisie("Rectangles soustractifs (trous)", s["holes"], col)
        h += _kv(
            "Efforts et matériau",
            _champs(
                s,
                [
                    ("mat", "Matériau", ""),
                    ("N", "N (traction > 0)", "kN"),
                    ("Mfz", "Mfz", "kN·m"),
                    ("Mfy", "Mfy", "kN·m"),
                    ("Ty", "Ty", "kN"),
                    ("s0", "Abscisse s des efforts", "m"),
                    ("Kt", "Kt", "-"),
                    ("mode", "Méthode d'intégration", ""),
                ],
            ),
        )
        return h
    if key == "Beam":
        return _inputsBeam(s)
    if key == "Tr":
        h = _kv(
            "Matériau et barres",
            _champs(
                s,
                [
                    ("mat", "Matériau", ""),
                    ("E", "E", "GPa"),
                    ("S", "S (section des barres)", "mm²"),
                    ("scale", "Amplification de la déformée (0 = auto)", ""),
                ],
            ),
        )
        h += _tableSaisie("Nœuds", s["nodes"], {"name": "Nom", "x": "x (m)", "y": "y (m)"})
        h += _tableSaisie("Barres", s["bars"], {"i": "Nœud i", "j": "Nœud j"})
        h += _tableSaisie("Appuis", s["sup"], {"node": "Nœud", "bx": "Bloque x", "by": "Bloque y"})
        h += _tableSaisie("Charges", s["loads"], {"node": "Nœud", "Fx": "Fx (kN)", "Fy": "Fy (kN)"})
        return h
    if key == "Tra":
        return _kv(
            "Barre et chargement",
            _champs(
                s,
                [
                    ("N", "N (> 0 traction)", "kN"),
                    ("S0", "S0", "mm²"),
                    ("L0", "L0", "m"),
                    ("mat", "Matériau", ""),
                    ("E", "E", "GPa"),
                    ("nu", "ν", "-"),
                    ("alpha", "α", "10⁻⁶/°C"),
                    ("Re", "Re", "MPa"),
                    ("dT", "ΔT", "°C"),
                    ("Kt", "Kt", "-"),
                    ("s", sig, "-"),
                    ("dLmax", "ΔL max (0 = sans limite)", "mm"),
                    ("varS", "Section variable S(x)", ""),
                    ("Sexpr", "S(x) (mm², x en m)", "", None, lambda d: d["varS"]),
                ],
            ),
        )
    if key == "Cis":
        h = _kv(
            "Matériau",
            _champs(
                s,
                [
                    ("mat", "Matériau", ""),
                    ("Re", "Re", "MPa"),
                    ("G", "G", "GPa"),
                    ("crit", "Critère (τe)", "", _CRITERES),
                    ("s", sig, "-"),
                ],
            ),
        )
        h += _kv(
            "Cisaillement simple et matage",
            _champs(
                s,
                [
                    ("T", "T", "kN"),
                    ("S", "S cisaillée", "mm²"),
                    ("k", "k = τmax/τmoy", "-"),
                    ("Fm", "F (matage)", "kN"),
                    ("Sm", "S matée", "mm²"),
                    ("Padm", "P_adm", "MPa"),
                ],
            ),
        )
        h += _kv(
            "Clavette parallèle",
            _champs(
                s,
                [
                    ("C", "Couple C", "kN·m"),
                    ("Dk", "Diamètre d'arbre D", "mm"),
                    ("ak", "Largeur a", "mm"),
                    ("bk", "Hauteur b", "mm"),
                    ("Lk", "Longueur L (0 = dimensionner)", "mm"),
                ],
            ),
        )
        h += _kv(
            "Goupille / rivet",
            _champs(
                s,
                [
                    ("Fp", "F", "kN"),
                    ("dp", "d", "mm"),
                    ("ep", "e — épaisseur matée", "mm"),
                    ("np", "Sections cisaillées n", "-"),
                ],
            ),
        )
        return h + _sectionUtilisee(s)
    if key == "Tor":
        return _kv(
            "Arbre circulaire",
            _champs(
                s,
                [
                    ("Mt", "Mt", "kN·m"),
                    ("D", "D", "mm"),
                    ("d", "d — alésage (0 = plein)", "mm"),
                    ("L", "L", "m"),
                    ("mat", "Matériau", ""),
                    ("G", "G", "GPa"),
                    ("Re", "Re", "MPa"),
                    ("crit", "Critère (τe)", "", _CRITERES),
                    ("s", sig, "-"),
                    ("Kt", "Kt", "-"),
                    ("thetaAdm", "θ admissible (0 = sans)", "°/m"),
                ],
            ),
        )
    if key == "Fle":
        h = _kv(
            "Efforts et matériau",
            _champs(
                s,
                [
                    ("N", "N (traction > 0)", "kN"),
                    ("Mfz", "Mfz", "kN·m"),
                    ("Mfy", "Mfy", "kN·m"),
                    ("s0", "Abscisse s des efforts", "m"),
                    ("Kt", "Kt", "-"),
                    ("mat", "Matériau", ""),
                    ("Re", "Re", "MPa"),
                    ("s", sig, "-"),
                ],
            ),
        )
        return h + _sectionUtilisee(s)
    if key == "Fla":
        cond = {
            "encastre-libre": "encastré-libre",
            "articule-articule": "articulé-articulé",
            "encastre-articule": "encastré-articulé",
            "encastre-encastre": "encastré-encastré",
        }
        return _kv(
            "Poutre comprimée",
            _champs(
                s,
                [
                    ("fam", "Famille de profilé", ""),
                    ("prof", "Profilé", ""),
                    ("S", "S", "mm²"),
                    ("Iz", "Iz", "mm⁴"),
                    ("Iy", "Iy", "mm⁴"),
                    ("mat", "Matériau", ""),
                    ("E", "E", "GPa"),
                    ("Re", "Re", "MPa"),
                    ("L", "Longueur L", "m"),
                    ("cond", "Conditions aux limites", "", cond),
                    ("P", "P appliquée (0 = aucune)", "kN"),
                    ("s", sig, "-"),
                ],
            ),
        )
    if key == "Ten":
        ax = ["x", "y", "z"]
        t = pd.DataFrame(s["sig"], index=ax, columns=ax)
        h = "<h3>Tenseur des contraintes σ (MPa)</h3>" + _tableHTML(t, lignes=True)
        fm = {"theta": "Angle θ dans le plan (x, y)", "n": "Normale n (nx, ny, nz)"}
        h += _kv(
            "Facette et critères",
            _champs(
                s,
                [
                    ("fmode", "Définition de la facette", "", fm),
                    ("theta", "θ", "°", None, lambda d: d["fmode"] == "theta"),
                    ("nx", "nx", "-", None, lambda d: d["fmode"] == "n"),
                    ("ny", "ny", "-", None, lambda d: d["fmode"] == "n"),
                    ("nz", "nz", "-", None, lambda d: d["fmode"] == "n"),
                    ("mat", "Matériau", ""),
                    ("Re", "Re = σe", "MPa"),
                    ("Rm", "σR (fragiles : Rm)", "MPa"),
                    ("s", sig, "-"),
                ],
            ),
        )
        return h
    if key == "Hoo":
        mode = {
            "iso3D": "Isotrope 3D",
            "planeStress": "Contraintes planes",
            "planeStrain": "Déformations planes",
            "ortho": "Orthotrope",
        }
        iso = s["mode"] in ("iso3D", "planeStress", "planeStrain")
        sg = s["mode"] in ("iso3D", "ortho")
        champs = [
            ("mode", "Loi", "", mode),
            ("mat", "Matériau", "", None, lambda d: iso),
            ("E", "E", "GPa", None, lambda d: iso),
            ("nu", "ν", "-", None, lambda d: iso),
            ("alpha", "α", "10⁻⁶/°C", None, lambda d: d["mode"] == "iso3D"),
            ("dT", "ΔT", "°C", None, lambda d: d["mode"] == "iso3D"),
            ("sxx", "σxx", "MPa", None, lambda d: d["mode"] != "planeStrain"),
            ("syy", "σyy", "MPa", None, lambda d: d["mode"] != "planeStrain"),
            ("sxy", "σxy", "MPa", None, lambda d: d["mode"] != "planeStrain"),
            ("szz", "σzz", "MPa", None, lambda d: sg),
            ("syz", "σyz", "MPa", None, lambda d: sg),
            ("sxz", "σxz", "MPa", None, lambda d: sg),
            ("exx", "εxx", "µdéf", None, lambda d: d["mode"] == "planeStrain"),
            ("eyy", "εyy", "µdéf", None, lambda d: d["mode"] == "planeStrain"),
            ("gxy", "γxy", "µdéf", None, lambda d: d["mode"] == "planeStrain"),
        ]
        champs += [
            (c, c, u, None, lambda d: d["mode"] == "ortho")
            for c, u in [
                ("E1", "GPa"),
                ("E2", "GPa"),
                ("E3", "GPa"),
                ("nu12", "-"),
                ("nu13", "-"),
                ("nu23", "-"),
                ("G12", "GPa"),
                ("G13", "GPa"),
                ("G23", "GPa"),
            ]
        ]
        return _kv("Loi de Hooke", _champs(s, champs))
    if key == "Jau":
        mont = {"quart": "Quart de pont", "demi": "Demi-pont", "complet": "Pont complet"}
        ros = {"45": "Rectangulaire 0°/45°/90°", "60": "Delta 0°/60°/120°"}
        h = _kv(
            "Jauge et pont de Wheatstone",
            _champs(
                s,
                [
                    ("K", "Facteur de jauge K", "-"),
                    ("eps", "ε", "µdéf"),
                    ("R0", "R0", "Ω"),
                    ("cfg", "Montage", "", mont),
                    ("Vin", "Alimentation Vin", "V"),
                    ("e1", "ε1", "µdéf"),
                    ("e2", "ε2", "µdéf", None, lambda d: d["cfg"] != "quart"),
                    ("e3", "ε3", "µdéf", None, lambda d: d["cfg"] == "complet"),
                    ("e4", "ε4", "µdéf", None, lambda d: d["cfg"] == "complet"),
                    ("Vout", "Vout mesurée", "mV"),
                ],
            ),
        )
        h += _kv(
            "Rosette",
            _champs(
                s,
                [
                    ("rtype", "Type", "", ros),
                    ("ra", "ε à 0°", "µdéf"),
                    ("rb", "ε à 90° (rect.) / 60° (delta)", "µdéf"),
                    ("rc", "ε à 45° (rect.) / 120° (delta)", "µdéf"),
                    ("mat", "Matériau", ""),
                    ("E", "E", "GPa"),
                    ("nu", "ν", "-"),
                ],
            ),
        )
        return h
    return ""


def _inputsBeam(s: dict) -> str:
    h = _kv(
        "Poutre et matériau",
        _champs(
            s,
            [
                ("L", "Longueur L", "m"),
                ("mat", "Matériau", ""),
                ("E", "E", "GPa"),
                ("G", "G", "GPa"),
                ("Re", "Re", "MPa"),
                ("s", "Coefficient de sécurité s", "-"),
                ("Kt", "Kt", "-"),
                ("plane", "Plan de la déformée", "", {"xy": "(x, y)", "xz": "(x, z)"}),
                ("selfw", "Poids propre", ""),
                ("shear", "Tranchant dans Castigliano", ""),
            ],
        ),
    )
    h += _kv(
        "Section",
        _champs(
            s,
            [
                ("S", "S", "mm²"),
                ("Iz", "Iz", "mm⁴"),
                ("Iy", "Iy", "mm⁴"),
                ("Ix", "Ix (torsion)", "mm⁴"),
                ("Iyz", "Iyz", "mm⁴"),
                ("ky", "ky", "-"),
                ("kz", "kz", "-"),
                ("vy", "|y|max", "mm"),
                ("vz", "|z|max", "mm"),
            ],
        ),
    )
    if _sec(s) is not None:
        h += _kv(None, [("Section importée", compute._sectionLabel(_sec(s)))])
    h += _kv(
        "Température",
        _champs(s, [("thDT", "ΔT uniforme", "°C"), ("thGy", "Gradient ΔTy", "°C"), ("thGz", "Gradient ΔTz", "°C")]),
    )
    h += _tableSaisie("Appuis", s["sup"], {"name": "Nom", "pos": "s (m)", "type": "Type"})
    h += _tableSaisie(
        "Ressorts et tassements",
        s["supx"],
        {"name": "Appui", "k": "k (kN/m)", "dx": "dx (mm)", "dy": "dy (mm)", "dz": "dz (mm)"},
    )
    h += _tableSaisie("Rotules intermédiaires", s["hg"], {"name": "Nom", "pos": "s (m)"})
    h += _tableSaisie(
        "Forces ponctuelles",
        s["pl"],
        {"name": "Nom", "pos": "s (m)", "Fx": "Fx (kN)", "Fy": "Fy (kN)", "Fz": "Fz (kN)", "case": "Cas"},
    )
    h += _tableSaisie(
        "Couples ponctuels",
        s["pm"],
        {"name": "Nom", "pos": "s (m)", "Mx": "Mx (kN·m)", "My": "My (kN·m)", "Mz": "Mz (kN·m)", "case": "Cas"},
    )
    h += _tableSaisie(
        "Charges réparties",
        s["dl"],
        {
            "name": "Nom",
            "a": "a (m)",
            "b": "b (m)",
            "dir": "Direction",
            "type": "Type",
            "vals": "p (kN/m)",
            "case": "Cas",
        },
    )
    h += _tableSaisie("Combinaisons", s["combo"], {"name": "Nom", "gG": "γG", "gQ": "γQ", "gW": "γW", "gS": "γS"})
    h += _kv(
        "Eurocode 3, fatigue et profilé le plus léger",
        _champs(
            s,
            [
                ("na", "Annexe nationale", "", {"EN": "EN", "FR": "France", "autre": "autre"}),
                ("gM0", "γM0", "-"),
                ("gM1", "γM1", "-"),
                ("Cmy", "Cmy", "-"),
                ("CmLT", "CmLT", "-"),
                ("Lcr", "Lcr (0 = L)", "m"),
                ("LcrF", "Lcr plan fort (0 = L)", "m"),
                ("C1", "C1", "-"),
                ("ecsrc", "Efforts de calcul", "", {"courant": "dernier calcul", "enveloppe": "enveloppe"}),
                ("fR", "Fatigue : R = σmin/σmax", "-"),
                ("fka", "Fatigue : ka", "-"),
                ("fkb", "Fatigue : kb", "-"),
                ("pfam", "Famille de profilés", ""),
                ("pdef", "Flèche L/n (0 = ignorée)", ""),
            ],
        ),
    )
    return h


# ------------------------------------------------------------------- 2. Hypothèses et contrôles d'applicabilité


def _hypStatements(key: str) -> list[str]:
    commun = [
        "Matériau homogène, isotrope, élastique linéaire (σ = E ε jusqu'à Re).",
        "Petits déplacements et petites déformations : équilibre écrit sur la géométrie non déformée.",
    ]
    d = {
        "Sec": [
            "Section constituée de rectangles, disques et couronnes (additifs ou soustractifs).",
            "Les profilés du catalogue sont modélisés par une géométrie simplifiée (congés ignorés).",
            "Contrainte de cisaillement de Jourawski uniforme sur la largeur b(y) de la section.",
        ],
        "Beam": commun
        + [
            "Poutre droite à section et matériau constants, longueur très supérieure à la hauteur.",
            "Sections planes qui restent planes et perpendiculaires à la ligne moyenne (Bernoulli).",
            "Effet de l'effort tranchant sur la flèche négligé, sauf option Castigliano avec tranchant.",
            "Liaisons parfaites (sans frottement), appuis rigides (aucun tassement).",
            "Charges dans le plan de symétrie, sans déversement ni instabilité.",
        ],
        "Tr": commun
        + [
            "Barres articulées sans frottement aux nœuds.",
            "Charges et appuis uniquement aux nœuds ; poids propre négligé.",
            "Chaque barre ne subit qu'un effort normal constant.",
            "Le flambage des barres comprimées n'est pas vérifié ici.",
        ],
        "Tra": commun
        + [
            "Barre droite, effort normal centré, contrainte uniforme dans la section (Saint-Venant).",
            "Concentration de contrainte représentée par un coefficient Kt appliqué à la contrainte nominale.",
            "Si la section est variable : variation lente de S(x) (pas de changement brusque).",
        ],
        "Cis": commun
        + [
            "Cisaillement simple : τ uniforme sur la section cisaillée (premier ordre).",
            "Matage : pression uniforme sur la surface projetée.",
            "Critère de résistance au glissement : τe = Re/2 (Tresca) ou Re/√3 (Von Mises).",
            "Pressions admissibles de matage prises dans la table du cours.",
        ],
        "Tor": commun
        + [
            "Arbre de section circulaire (pleine ou creuse), constante.",
            "Sections planes qui restent planes et circulaires ; rayons qui restent droits.",
            "Moment de torsion constant le long de l'arbre ; zones d'appui et de variation de section écartées "
            "(Saint-Venant).",
        ],
        "Fle": commun
        + [
            "Sections planes qui restent planes (Navier-Bernoulli) ; flexion composée déviée par superposition.",
            "Axes principaux, ou formule générale si le produit d'inertie n'est pas nul.",
            "Contrainte maximale cherchée aux points du contour de la section.",
        ],
        "Fla": [
            "Poutre droite, section constante, compression centrée, imperfections négligées.",
            "Flambage dans le plan de plus faible inertie.",
            "Arbre de décision du cours : compression simple (λ < 20), Rankine, Euler (λ ≥ λlim).",
            "Conditions aux limites idéalisées (longueur de flambement L' = c·L).",
        ],
        "Ten": commun
        + [
            "Tenseur des contraintes symétrique en un point.",
            "Matériau ductile pour Tresca et Von Mises ; contrainte normale maximale pour un matériau fragile.",
        ],
        "Hoo": commun
        + [
            "Matériau isotrope (2 constantes E, ν) ou orthotrope aux axes d'orthotropie alignés sur x, y, z.",
            "Cisaillements en notation d'ingénieur dans Voigt (γ = 2ε).",
        ],
        "Jau": [
            "Loi de la jauge ΔR/R = K ε (K constant, pas d'effet de température).",
            "Pont de Wheatstone linéarisé ; l'erreur de linéarité est affichée.",
            "Rosette : état de déformation plan, contraintes planes pour passer aux contraintes.",
        ],
    }
    return d[key]


def _extraStatements(key: str, res: dict) -> list[str]:
    """Hypothèses des résultats ajoutés à l'onglet Poutres, seulement s'ils ont été calculés."""
    if key != "Beam":
        return []
    ex = _extras(res)
    s = []
    if ex.get("combos") is not None:
        s.append(
            "Combinaisons : superposition linéaire des cas G, Q, W, S avec les coefficients saisis (non imposés par "
            "une norme) ; l'enveloppe associe des maxima non simultanés."
        )
    if ex.get("ec3") is not None:
        s.append(
            "Eurocode 3 (EN 1993-1-1) : valeurs recommandées, annexe nationale non appliquée ; fy = Re sans "
            "réduction avec l'épaisseur ; profilés IPE, HEA, HEB, IPN ou sections en I, classes 1 à 3 ; flexion "
            "autour de l'axe fort."
        )
        s.append(
            "Déversement : poutre à fourches, charge au centre de torsion, Iw estimé par Iz(h − tf)²/4, C1 et Lcr "
            "saisis, pas de coefficient f de répartition du moment."
        )
        s.append(
            "Efforts de calcul : N et M maximaux associés sans être simultanés (prudent) ; interaction N + M "
            "(§6.3.3) par l'annexe B, tableau B.2, avec Cmy et CmLT saisis ; voilement de l'âme par cisaillement "
            "(EN 1993-1-5 §5) sans la contribution des semelles."
        )
    if ex.get("fatigue") is not None:
        s.append(
            "Fatigue : droite de Goodman modifiée, acier, vie infinie, Se = ka·kb·0,5·Rm, Kf = Kt, amplitude "
            "constante (Shigley, chap. 6)."
        )
    if ex.get("profiles") is not None:
        s.append(
            "Profilé le plus léger : critère Kt·σ ≤ Re/s (et flèche si demandée), sans Eurocode 3, avec le "
            "chargement saisi ; section supposée sans produit d'inertie."
        )
    return s


def _chk(titre: str, detail: str, etat) -> tuple[str, str, str]:
    """Ligne de contrôle : état 'ok', 'warn' ou 'ko' (un booléen vaut ok / ko)."""
    if isinstance(etat, (bool, np.bool_)):
        etat = "ok" if etat else "ko"
    return (titre, detail, etat)


def _lvl(cond, mauvais: str) -> str:
    """'ok' si la condition est vraie, sinon le niveau `mauvais` ('warn' ou 'ko')."""
    return "ok" if cond else mauvais


def _autoChecks(key: str, saisie: dict, res: dict, dm) -> list[tuple[str, str, str]]:
    """Contrôles d'applicabilité chiffrés de chaque onglet (autoChecks de MATLAB)."""
    chk: list[tuple[str, str, str]] = []
    add = chk.append
    S = saisie
    R = None if key == "Beam" else res["result"]
    if key == "Sec":
        ec = R["compare"].attrs["ecartAB_pct"]
        add(_chk("Méthodes analytique et intégrale concordantes", f"écart maximal {ec:.3g} %", ec < 1e-6))
        if R["sec"]["type"] == "profile":
            add(
                _chk(
                    "Profilé du catalogue : géométrie simplifiée",
                    "congés ignorés : voir l'écart avec les valeurs tabulées au §4",
                    "warn",
                )
            )
    elif key == "Beam":
        B = res
        L = B["model"]["L"]
        vy = max(S["vy"], 1e-9) * 1e-3
        add(_chk("Poutre élancée : L/h ≥ 10 (h ≈ 2·vy)", f"L/h = {L / (2 * vy):.3g}", _lvl(L / (2 * vy) >= 10, "warn")))
        f = abs(B["defl"]["integration"]["fmax"])
        add(
            _chk(
                "Petits déplacements : f max / L ≤ 1/50",
                f"f max/L = 1/{L / max(f, np.finfo(float).eps):.3g}",
                _lvl(f / L <= 1 / 50, "warn"),
            )
        )
        bd = B["check"]["bend"]
        sAdm = bd["sigmaAdm"] * S["s"]
        add(
            _chk(
                "Domaine élastique : σ max ≤ Re",
                f"σ max = {bd['sigmaMaxAbs'] / 1e6:.4g} MPa ; Re = {sAdm / 1e6:.4g} MPa",
                _lvl(bd["sigmaMaxAbs"] <= sAdm, "ko"),
            )
        )
        add(
            _chk(
                "Résistance avec coefficient de sécurité : Kt·σ max ≤ Re/s",
                f"{bd['sigmaMaxKt'] / 1e6:.4g} MPa ≤ {bd['sigmaAdm'] / 1e6:.4g} MPa",
                _lvl(bool(bd["ok"]), "ko"),
            )
        )
        nmin = B["sol"]["extrema"]["N"]["min"]
        if nmin < -1e-6:
            add(
                _chk(
                    "Effort normal de compression présent",
                    f"N min = {nmin / 1e3:.4g} kN : vérifier le flambage (onglet Flambage)",
                    "warn",
                )
            )
        sol = B["sol"]
        if not sol["isostatic"]:
            add(
                _chk(
                    "Poutre hyperstatique : réactions par Ménabréa et par intégration",
                    f"écart coupures/intégrale = {sol['methodCheck']:.2g}",
                    _lvl(sol["methodCheck"] < 1e-6, "warn"),
                )
            )
        if not sol["isostatic"] and S["Iyz"] != 0:
            add(
                _chk(
                    "LIMITE DU LOGICIEL : poutre hyperstatique avec Iyz ≠ 0",
                    "réactions calculées plan par plan : le couplage y–z des inconnues hyperstatiques est ignoré, "
                    "réactions, moments et contraintes NON fiables ; saisir la section dans ses axes principaux "
                    "(Iyz = 0)",
                    "ko",
                )
            )
        mo = sol["model"]
        th = mo["thermal"]
        if (
            any(sp["spring"] > 0 for sp in mo["supports"])
            or any(abs(sp[c]) > 0 for sp in mo["supports"] for c in ("dx", "dy", "dz"))
            or len(mo["hinges"]) > 0
            or any(abs(th[c]) > 0 for c in ("epsX", "kv", "kw"))
        ):
            add(
                _chk(
                    "Ressorts, tassements, rotules ou température présents",
                    "les réactions ne sont pas recalculées à la main (le dossier contrôle l'équilibre, les "
                    "conditions aux appuis et le moment nul aux rotules) ; elles sont obtenues par deux méthodes "
                    "indépendantes (Ménabréa et intégration) et la flèche par quatre",
                    "warn",
                )
            )
        add(
            _chk(
                "Effet de l'effort tranchant sur la flèche",
                f"inclus dans Castigliano : {_oui(S['shear'])}",
                _lvl(S["shear"] or L / (2 * vy) >= 10, "warn"),
            )
        )
        chk += _extraChecks(S, res)
    elif key == "Tr":
        ts = R["tsol"]
        add(_chk("Treillis non mécanisme (h ≥ 0)", f"h = {ts['h']}", _lvl(ts["h"] >= 0 and not ts["mechanism"], "ko")))
        Re = dm.getMaterial(S["mat"])["Re"]
        sm = float(np.max(np.abs(ts["sigma"])))
        add(
            _chk(
                "Domaine élastique : |σ| max ≤ Re",
                f"|σ| max = {sm / 1e6:.4g} MPa ; Re = {Re / 1e6:.4g} MPa",
                _lvl(sm <= Re, "ko"),
            )
        )
        N = np.asarray(ts["N"], dtype=float)
        nc = int(np.sum(np.asarray(ts["nature"]) == "Compression"))
        if nc > 0:
            add(
                _chk(
                    "Barres comprimées : flambage à vérifier",
                    f"{nc} barre(s) en compression, |N| max = {np.max(np.abs(N[N < 0])) / 1e3:.4g} kN",
                    "warn",
                )
            )
        Lmin = float(np.min(ts["L0"]))
        umax = float(np.max(np.linalg.norm(ts["displacements"], axis=1)))
        add(
            _chk(
                "Petits déplacements : u max / L min ≤ 1 %",
                f"u max = {umax * 1e3:.4g} mm ; L min = {Lmin:.4g} m",
                _lvl(umax / Lmin <= 0.01, "warn"),
            )
        )
    elif key == "Tra":
        sMax = abs(R["sigmaMax"]) / 1e6
        add(
            _chk(
                "Domaine élastique : σ max ≤ Re",
                f"σ max = {sMax:.4g} MPa ; Re = {S['Re']:.4g} MPa",
                _lvl(sMax <= S["Re"], "ko"),
            )
        )
        add(
            _chk(
                "Résistance : Kt·σ ≤ Re/s",
                f"{sMax:.4g} MPa ≤ {R['sigmaAdm'] / 1e6:.4g} MPa",
                _lvl(bool(R["okResistance"]), "ko"),
            )
        )
        eps = abs(R["dL"]["integrale"]) / S["L0"]
        add(_chk("Petites déformations : |ΔL|/L0 ≤ 1 %", f"{100 * eps:.3g} %", _lvl(eps <= 0.01, "warn")))
        if S["N"] < 0:
            add(_chk("Effort de compression : flambage à vérifier", "voir l'onglet Flambage", "warn"))
        if S["varS"]:
            add(
                _chk(
                    "Section variable",
                    "hypothèse : variation lente de S(x) ; ΔL analytique à S constante non représentatif",
                    "warn",
                )
            )
    elif key == "Cis":
        r, b = R["shear"], R["bearing"]
        add(
            _chk(
                "Cisaillement : k·T/S ≤ τe/s",
                f"{r['tauMax'] / 1e6:.4g} MPa ≤ {r['tauAdm'] / 1e6:.4g} MPa",
                _lvl(bool(r["ok"]), "ko"),
            )
        )
        add(_chk("Matage : P ≤ Padm", f"{b['P'] / 1e6:.4g} MPa ≤ {S['Padm']:.4g} MPa", _lvl(bool(b["ok"]), "ko")))
        add(
            _chk(
                "Pression admissible dans la plage du cours (0,5 à 150 MPa)",
                f"Padm = {S['Padm']:.4g} MPa",
                _lvl(0.5 <= S["Padm"] <= 150, "warn"),
            )
        )
        if _extras(res).get("pin") is not None:
            add(
                _chk(
                    "Matage de la goupille : formule du cours P = 2F/(d e)",
                    "beaucoup de manuels écrivent F/(d e) : à confirmer avec le montage",
                    "warn",
                )
            )
    elif key == "Tor":
        add(
            _chk(
                "Résistance : Kt·τ max ≤ τe/s",
                f"{R['tauMax'] / 1e6:.4g} MPa ≤ {R['tauAdm'] / 1e6:.4g} MPa",
                _lvl(bool(R["okResistance"]), "ko"),
            )
        )
        add(
            _chk(
                "Rigidité : θ ≤ θ admissible",
                f"θ = {math.degrees(R['theta']):.4g} °/m ; θ adm = {S['thetaAdm']:.4g} °/m",
                _lvl(bool(R["okRigidite"]), "ko"),
            )
        )
        ld = S["L"] * 1e3 / S["D"]
        add(_chk("Arbre long devant son diamètre (Saint-Venant) : L/D ≥ 3", f"L/D = {ld:.3g}", _lvl(ld >= 3, "warn")))
    elif key == "Fle":
        bd = R["bend"]
        add(
            _chk(
                "Domaine élastique : |σ| max ≤ Re",
                f"{bd['sigmaMaxAbs'] / 1e6:.4g} MPa ≤ {S['Re']:.4g} MPa",
                _lvl(bd["sigmaMaxAbs"] / 1e6 <= S["Re"], "ko"),
            )
        )
        add(
            _chk(
                "Résistance : Kt·|σ| max ≤ Re/s",
                f"{bd['sigmaMaxKt'] / 1e6:.4g} MPa ≤ {bd['sigmaAdm'] / 1e6:.4g} MPa",
                _lvl(bool(bd["ok"]), "ko"),
            )
        )
        add(
            _chk(
                "Axes principaux (Iyz = 0) ou formule générale utilisée",
                f"formule générale : {_oui(bd['usedGeneralFormula'])}",
                "ok",
            )
        )
    elif key == "Fla":
        b = R["analysis"]
        add(
            _chk(
                "Régime de flambage",
                f"λ = {b['lambda']:.4g} ; λlim = {b['lambdaLim']:.4g} ; régime {b['regime']}",
                "ok",
            )
        )
        add(_chk("Élancement raisonnable : λ ≤ 200", f"λ = {b['lambda']:.4g}", _lvl(b["lambda"] <= 200, "warn")))
        if b["lambda"] < 20:
            add(_chk("Poutre trapue (λ < 20) : compression simple", "le flambage est négligeable", "ok"))
        if math.isfinite(b["P"]):
            add(
                _chk(
                    "Stabilité : P ≤ Padm",
                    f"{b['P'] / 1e3:.4g} kN ≤ {b['Padm'] / 1e3:.4g} kN",
                    _lvl(bool(b["ok"]), "ko"),
                )
            )
        if S["cond"] == "encastre-articule":
            add(
                _chk(
                    "Encastré-articulé : L' = L/√2 (valeur exacte 0,6992 L)",
                    "écart de 1 % sur L', du côté sécuritaire",
                    "warn",
                )
            )
    elif key == "Ten":
        cr = R["criteria"]
        add(_chk("Tenseur symétrique (symétrisé automatiquement)", "σij = σji", "ok"))
        add(
            _chk(
                "Critère de Von Mises respecté",
                f"σVM = {cr['sigmaEqVM'] / 1e6:.4g} MPa ≤ {cr['sigmaAdm'] / 1e6:.4g} MPa",
                _lvl(bool(cr["okVM"]), "ko"),
            )
        )
        add(
            _chk(
                "Critère de Tresca respecté",
                f"{cr['sigmaEqTresca'] / 1e6:.4g} MPa ≤ {cr['sigmaAdm'] / 1e6:.4g} MPa",
                _lvl(bool(cr["okTresca"]), "ko"),
            )
        )
    elif key == "Hoo":
        nu = S["nu"]
        if S["mode"] == "ortho":
            add(
                _chk(
                    "Matériau orthotrope : [S] symétrique, [C] définie positive",
                    "vérifié par le solveur (erreur sinon)",
                    "ok",
                )
            )
        else:
            add(_chk("Coefficient de Poisson dans ]−1 ; 0,5[", f"ν = {nu:.4g}", _lvl(-1 < nu < 0.5, "ko")))
            add(_chk("Module de Young positif", f"E = {S['E']:.4g} GPa", _lvl(S["E"] > 0, "ko")))
        if S["mode"] == "planeStress":
            add(
                _chk(
                    "Contraintes planes : σzz = σxz = σyz = 0 par hypothèse",
                    "les valeurs de σzz, σxz, σyz saisies sont ignorées",
                    "warn",
                )
            )
    elif key == "Jau":
        add(
            _chk(
                "Facteur de jauge usuel (1,8 à 2,2 pour une jauge métallique)",
                f"K = {S['K']:.4g}",
                _lvl(1.8 <= S["K"] <= 2.2, "warn"),
            )
        )
        le = R["bridge"]["linearityError"]
        add(
            _chk("Linéarisation du pont : erreur ≤ 1 %", f"{le * 100:.3g} %", _lvl(abs(le) <= 0.01, "warn")),
        )
    return chk


def _extraChecks(S: dict, res: dict) -> list[tuple[str, str, str]]:
    """Contrôles d'applicabilité des résultats ajoutés à l'onglet Poutres (si calculés)."""
    chk: list[tuple[str, str, str]] = []
    ex = _extras(res)
    T = ex.get("combos")
    if T is not None:
        nErr = int(T["Résistance"].astype(str).str.contains("erreur").sum())
        add = chk.append
        add(
            _chk(
                "Combinaisons : toutes résolues sans erreur",
                f"{len(T) - 1} combinaison(s), {nErr} en erreur",
                _lvl(nErr == 0, "ko"),
            )
        )
        env = T.iloc[-1]
        add(
            _chk(
                "Combinaisons : résistance sur l'enveloppe (Kt·σ ≤ Re/s)",
                f"{env['Kt·σ max (MPa)']:.4g} MPa ≤ {env['σadm (MPa)']:.4g} MPa",
                _lvl(env["Kt·σ max (MPa)"] <= env["σadm (MPa)"], "ko"),
            )
        )
    if ex.get("ec3") is not None:
        r = ex["ec3"][0]
        add = chk.append
        add(
            _chk(
                "Eurocode 3 : classe de section 1 à 3",
                f"classe {r['class']['class']}",
                _lvl(r["class"]["class"] <= 3, "ko"),
            )
        )
        add(
            _chk(
                "Eurocode 3 : résistance des sections (flexion, tranchant)",
                f"MEd/MRd = {r['ratioM']:.3f} ; VEd/Vpl,Rd = {r['ratioV']:.3f}",
                _lvl(bool(r["ok"]), "ko"),
            )
        )
        lcr = S["Lcr"] if S["Lcr"] > 0 else S["L"]
        add(
            _chk(
                "Eurocode 3 : déversement",
                f"MEd/Mb,Rd = {r['ltb']['ratio']:.3f} (Lcr = {lcr:.4g} m, C1 = {S['C1']:.3g})",
                _lvl(bool(r["ltb"]["ok"]), "ko"),
            )
        )
        add(
            _chk(
                "Eurocode 3 : flexion + effort normal",
                f"rapport = {r['axial']['ratio']:.3f}",
                _lvl(bool(r["axial"]["ok"]), "ko"),
            )
        )
        if r["buck"] is not None:
            add(
                _chk(
                    "Eurocode 3 : flambement",
                    f"NEd/Nb,Rd = {r['buck']['ratio']:.3f}",
                    _lvl(bool(r["buck"]["ok"]), "ko"),
                )
            )
        if r["inter"] is not None:
            it = r["inter"]
            add(
                _chk(
                    "Eurocode 3 : interaction N + M (6.61 et 6.62, annexe B)",
                    f"rapport = {it['ratio']:.3f} (Cmy = {it['Cmy']:.2f}, CmLT = {it['CmLT']:.2f})",
                    _lvl(bool(it["ok"]), "ko"),
                )
            )
        w = r["web"]
        if w["needed"]:
            txt = f"hw/tw = {w['hwTw']:.1f} > {w['limit']:.1f} : VEd/Vb,Rd = {w['ratio']:.3f}"
        else:
            txt = f"sans objet : hw/tw = {w['hwTw']:.1f} ≤ {w['limit']:.1f}"
        add(_chk("Eurocode 3 : voilement de l'âme par cisaillement", txt, _lvl(bool(w["ok"]), "ko")))
        add(
            _chk(
                "Eurocode 3 : annexe nationale",
                "seules γM0 et γM1 sont paramétrables (France : mêmes valeurs que l'EN) ; vérifier les autres "
                "paramètres dans l'annexe du pays",
                "warn",
            )
        )
        add(
            _chk(
                "Eurocode 3 : fy = Re",
                f"fy = {S['Re']:.4g} MPa, sans réduction avec l'épaisseur (EN 1993-1-1 tableau 3.1)",
                "warn",
            )
        )
    if ex.get("fatigue") is not None:
        f = ex["fatigue"][0]
        chk.append(
            _chk("Fatigue (Goodman) : n ≥ s", f"n = {f['n']:.3g} ; s = {S['s']:.3g}", _lvl(f["n"] >= S["s"], "ko"))
        )
        chk.append(
            _chk("Fatigue : limite d'endurance estimée (ka, kb saisis)", f"Se = {f['Se'] / 1e6:.4g} MPa", "warn")
        )
    if ex.get("profiles") is not None:
        T = ex["profiles"][0]
        r = T["Résistance"].astype(str)
        ok = ~r.str.contains("NON") & ~r.str.contains("erreur")
        chk.append(
            _chk(
                "Profilé le plus léger : au moins un profilé de la famille vérifie",
                f"{int(ok.sum())} profilé(s) sur {len(T)}",
                _lvl(bool(ok.any()), "warn"),
            )
        )
    return chk


_CHOIX = "&#9744; valide &nbsp; &#9744; à revoir &nbsp; &#9744; non applicable"


def _hypothesesHTML(key: str, saisie: dict, res: dict, dm) -> tuple[str, int, int]:
    """Partie 2 : hypothèses (avis du relecteur) et contrôles d'applicabilité ; renvoie (html, nWarn, nKo)."""
    stat = _hypStatements(key) + _extraStatements(key, res)
    h = "<h3>Hypothèses du modèle (à valider)</h3><table><tr><th>Hypothèse</th><th>Avis du relecteur</th></tr>"
    h += "".join(f'<tr><td>{_esc(s)}</td><td class="rv">{_CHOIX}</td></tr>' for s in stat) + "</table>"
    h += (
        "<h3>Contrôles d'applicabilité faits par le logiciel</h3>"
        "<table><tr><th>Contrôle</th><th>Valeurs</th><th>Résultat</th></tr>"
    )
    nWarn = nKo = 0
    for titre, detail, etat in _autoChecks(key, saisie, res, dm):
        if etat == "ok":
            st = '<span class="ok">satisfait</span>'
        elif etat == "warn":
            st = '<span class="warn">point d\'attention</span>'
            nWarn += 1
        else:
            st = '<span class="ko">NON satisfait</span>'
            nKo += 1
        h += f"<tr><td>{_esc(titre)}</td><td>{_esc(detail)}</td><td>{st}</td></tr>"
    return h + "</table>", nWarn, nKo


# --------------------------------------------------------------------------- 3. Vérification indépendante


def _hc(label: str, latex: str, hand: float, solver: float, unit: str = "", tol: float = _NAN) -> dict:
    """Ligne de contrôle à la main : grandeur recalculée (hand), valeur du solveur et tolérance (NaN : défaut)."""
    return {"label": label, "latex": latex, "hand": hand, "solver": solver, "unit": unit, "tol": tol}


def _grp(label: str) -> dict:
    """Ligne de titre de groupe (pas de contrôle)."""
    return {"label": label, "latex": "", "hand": None, "solver": None, "unit": "", "tol": _NAN}


def _handTra(saisie: dict, res: dict) -> list[dict]:
    n = _num
    T, r = saisie, res["result"]
    N = T["N"] * 1e3
    S0, L0 = T["S0"], T["L0"]
    E = T["E"] * 1e3
    nu, al, dT, Kt, Re, s = T["nu"], T["alpha"] * 1e-6, T["dT"], T["Kt"], T["Re"], T["s"]
    sig = N / S0
    dLa = N * L0 * 1e3 / (E * S0) + al * dT * L0 * 1e3
    rows = [
        _grp("Contraintes (N en N, S en mm², contraintes en MPa)"),
        _hc(
            "Contrainte nominale",
            r"\sigma=\frac{N}{S_0}=\frac{%s\,\mathrm{N}}{%s\,\mathrm{mm^2}}=%s\,\mathrm{MPa}" % (n(N), n(S0), n(sig)),
            sig,
            r["sigmaNom"] / 1e6,
            "MPa",
        ),
        _hc(
            "Contrainte maximale",
            r"\sigma_{max}=K_t\,\sigma=%s\times%s=%s\,\mathrm{MPa}" % (n(Kt), n(sig), n(Kt * sig)),
            Kt * sig,
            r["sigmaMax"] / 1e6,
            "MPa",
        ),
        _hc(
            "Contrainte admissible",
            r"\sigma_{adm}=\frac{R_e}{s}=\frac{%s}{%s}=%s\,\mathrm{MPa}" % (n(Re), n(s), n(Re / s)),
            Re / s,
            r["sigmaAdm"] / 1e6,
            "MPa",
        ),
        _grp("Déformations et allongement"),
        _hc(
            "Déformation longitudinale",
            r"\varepsilon_{xx}=\frac{\sigma}{E}+\alpha\Delta T=\frac{%s}{%s}+%s\times%s" % (n(sig), n(E), n(al), n(dT)),
            sig / E + al * dT,
            r["epsxx"],
        ),
        _hc(
            "Déformation transversale",
            r"\varepsilon_{yy}=-\nu\frac{\sigma}{E}+\alpha\Delta T=-%s\times\frac{%s}{%s}+\alpha\Delta T"
            % (n(nu), n(sig), n(E)),
            -nu * sig / E + al * dT,
            r["epsyy"],
        ),
        _hc(
            "Variation relative de volume",
            r"\frac{\Delta V}{V}=(1-2\nu)\frac{\sigma}{E}+3\alpha\Delta T=(1-2\times%s)\frac{%s}{%s}+3\alpha\Delta T"
            % (n(nu), n(sig), n(E)),
            (1 - 2 * nu) * sig / E + 3 * al * dT,
            r["dVsurV"],
        ),
        _hc(
            "Allongement (section constante)",
            r"\Delta L=\frac{N\,L_0}{E\,S_0}+\alpha\Delta T L_0=\frac{%s\times%s}{%s\times%s}"
            % (n(N), n(L0 * 1e3), n(E), n(S0)),
            dLa,
            r["dL"]["analytique"] * 1e3,
            "mm",
        ),
    ]
    if T["varS"]:
        fS = compute.parseFunction(T["Sexpr"])

        def Sx(x):
            return float(fS(x)) * 1e-6  # mm² → m²

        dLi = quad(lambda x: N / (E * 1e6 * Sx(x)), 0, L0, epsabs=0, epsrel=1e-12)[0] * 1e3 + al * dT * L0 * 1e3
        rows.append(
            _hc(
                "Allongement (section variable S(x))",
                r"\Delta L=\int_0^{%s}\frac{N}{E\,S(x)}dx+\alpha\Delta T L_0\ \text{avec}\ S(x)=%s"
                % (n(L0), T["Sexpr"].replace("*", r"\cdot ")),
                dLi,
                r["dL"]["integrale"] * 1e3,
                "mm",
            )
        )
    else:
        rows.append(
            _hc(
                "Allongement (intégrale)",
                r"\Delta L=\int_0^{L_0}\left(\frac{N}{E S}+\alpha\Delta T\right)dx",
                dLa,
                r["dL"]["integrale"] * 1e3,
                "mm",
            )
        )
    rows.append(
        _hc(
            "Raideur K",
            r"K=\frac{E\,S_0}{L_0}=\frac{%s\times%s}{%s}" % (n(E), n(S0), n(L0 * 1e3)),
            E * S0 / (L0 * 1e3),
            r["K"] / 1e3,
            "N/mm",
        )
    )
    return rows


def _handSec(saisie: dict, res: dict) -> list[dict]:
    n = _num
    R = res["result"]
    sec, P = R["sec"], R["P"]
    t = sec["type"]

    def mm(k):
        return sec[k] * 1e3

    if t == "rectangle":
        b, h = mm("b"), mm("h")
        S, Iz, Iy = b * h, b * h**3 / 12, h * b**3 / 12
        fS = r"S=b\,h=%s\times%s" % (n(b), n(h))
        fIz = r"I_z=\frac{b\,h^3}{12}=\frac{%s\times%s^3}{12}" % (n(b), n(h))
        fIy = r"I_y=\frac{h\,b^3}{12}=\frac{%s\times%s^3}{12}" % (n(h), n(b))
    elif t == "disque":
        D = mm("D")
        S, Iz = math.pi * D**2 / 4, math.pi * D**4 / 64
        Iy = Iz
        fS = r"S=\frac{\pi D^2}{4}=\frac{\pi\times%s^2}{4}" % n(D)
        fIz = r"I_z=\frac{\pi D^4}{64}=\frac{\pi\times%s^4}{64}" % n(D)
        fIy = "I_y=I_z"
    elif t == "couronne":
        D, d = mm("D"), mm("d")
        S, Iz = math.pi * (D**2 - d**2) / 4, math.pi * (D**4 - d**4) / 64
        Iy = Iz
        fS = r"S=\frac{\pi(D^2-d^2)}{4}=\frac{\pi(%s^2-%s^2)}{4}" % (n(D), n(d))
        fIz = r"I_z=\frac{\pi(D^4-d^4)}{64}=\frac{\pi(%s^4-%s^4)}{64}" % (n(D), n(d))
        fIy = "I_y=I_z"
    elif t == "rectangle_creux":
        B, H, e = mm("B"), mm("H"), mm("t")
        S = B * H - (B - 2 * e) * (H - 2 * e)
        Iz = (B * H**3 - (B - 2 * e) * (H - 2 * e) ** 3) / 12
        Iy = (H * B**3 - (H - 2 * e) * (B - 2 * e) ** 3) / 12
        fS = r"S=BH-(B-2t)(H-2t)=%s\times%s-%s\times%s" % (n(B), n(H), n(B - 2 * e), n(H - 2 * e))
        fIz = r"I_z=\frac{BH^3-(B-2t)(H-2t)^3}{12}"
        fIy = r"I_y=\frac{HB^3-(H-2t)(B-2t)^3}{12}"
    elif t == "I":
        h, b, tw, tf = mm("h"), mm("b"), mm("tw"), mm("tf")
        S = 2 * b * tf + tw * (h - 2 * tf)
        Iz = (b * h**3 - (b - tw) * (h - 2 * tf) ** 3) / 12
        Iy = (2 * tf * b**3 + (h - 2 * tf) * tw**3) / 12
        fS = r"S=2\,b\,t_f+t_w(h-2t_f)=2\times%s\times%s+%s\times%s" % (n(b), n(tf), n(tw), n(h - 2 * tf))
        fIz = r"I_z=\frac{b\,h^3-(b-t_w)(h-2t_f)^3}{12}=\frac{%s\times%s^3-%s\times%s^3}{12}" % (
            n(b),
            n(h),
            n(b - tw),
            n(h - 2 * tf),
        )
        fIy = r"I_y=\frac{2\,t_f\,b^3+(h-2t_f)\,t_w^3}{12}"
    else:
        return [
            _grp(
                f"Section de type « {t} » : formules fermées non recalculées ici ; la comparaison analytique / "
                "intégrale / tabulée est au §4."
            )
        ]
    vmax = max(P["vyTop"], P["vyBot"]) * 1e3
    return [
        _grp("Caractéristiques géométriques (mm, mm², mm⁴)"),
        _hc("Aire S", fS + "=" + n(S) + r"\,\mathrm{mm^2}", S, P["S"] * 1e6, "mm²"),
        _hc("Moment quadratique Iz", fIz + "=" + n(Iz) + r"\,\mathrm{mm^4}", Iz, P["Iz"] * 1e12, "mm⁴"),
        _hc("Moment quadratique Iy", fIy + "=" + n(Iy) + r"\,\mathrm{mm^4}", Iy, P["Iy"] * 1e12, "mm⁴"),
        _hc(
            "Rayon de giration rz",
            r"r_z=\sqrt{I_z/S}=\sqrt{%s/%s}" % (n(Iz), n(S)),
            math.sqrt(Iz / S),
            P["rz"] * 1e3,
            "mm",
        ),
        _hc(
            "Module de flexion Wz",
            r"W_z=\frac{I_z}{v_{max}}=\frac{%s}{%s}" % (n(Iz), n(vmax)),
            Iz / vmax,
            P["Wz"] * 1e9,
            "mm³",
        ),
    ]


def _handCis(saisie: dict, res: dict) -> list[dict]:
    n = _num
    C, R = saisie, res["result"]
    Re, s = C["Re"], C["s"]
    if "tresca" in C["crit"].lower():
        tauE = Re / 2
        fte = r"\tau_e=\frac{R_e}{2}=\frac{%s}{2}" % n(Re)
    else:
        tauE = Re / math.sqrt(3)
        fte = r"\tau_e=\frac{R_e}{\sqrt3}=\frac{%s}{\sqrt3}" % n(Re)
    r, b = R["shear"], R["bearing"]
    T, S, k = C["T"] * 1e3, C["S"], C["k"]
    rows = [
        _grp("Cisaillement simple (T en N, S en mm², contraintes en MPa)"),
        _hc(
            "Contrainte moyenne",
            r"\tau_{moy}=\frac{T}{S}=\frac{%s}{%s}" % (n(T), n(S)),
            T / S,
            r["tauMoy"] / 1e6,
            "MPa",
        ),
        _hc(
            "Contrainte maximale",
            r"\tau_{max}=k\frac{T}{S}=%s\times\frac{%s}{%s}" % (n(k), n(T), n(S)),
            k * T / S,
            r["tauMax"] / 1e6,
            "MPa",
        ),
        _hc("Limite élastique au cisaillement", fte, tauE, r["tauE"] / 1e6, "MPa"),
        _hc(
            "Contrainte admissible",
            r"\tau_{adm}=\frac{\tau_e}{s}=\frac{%s}{%s}" % (n(tauE), n(s)),
            tauE / s,
            r["tauAdm"] / 1e6,
            "MPa",
        ),
        _grp("Matage"),
        _hc(
            "Pression de matage",
            r"P=\frac{F}{S_{mat}}=\frac{%s}{%s}" % (n(C["Fm"] * 1e3), n(C["Sm"])),
            C["Fm"] * 1e3 / C["Sm"],
            b["P"] / 1e6,
            "MPa",
        ),
    ]
    ex = _extras(res)
    if ex.get("key") is not None and "F" in ex["key"]["result"]:
        k2 = ex["key"]["result"]
        Cc, D, a, bh, Lk = C["C"] * 1e6, C["Dk"], C["ak"], C["bk"], C["Lk"]
        rows += [
            _grp("Clavette parallèle (C en N·mm, dimensions en mm)"),
            _hc("Effort tangentiel", r"F=\frac{2C}{D}=\frac{2\times%s}{%s}" % (n(Cc), n(D)), 2 * Cc / D, k2["F"], "N"),
        ]
        if "P" in k2:
            rows += [
                _hc(
                    "Pression de matage",
                    r"P=\frac{4C}{D\,b\,L}=\frac{4\times%s}{%s\times%s\times%s}" % (n(Cc), n(D), n(bh), n(Lk)),
                    4 * Cc / (D * bh * Lk),
                    k2["P"] / 1e6,
                    "MPa",
                ),
                _hc(
                    "Contrainte de cisaillement",
                    r"\tau=\frac{2C}{a\,L\,D}=\frac{2\times%s}{%s\times%s\times%s}" % (n(Cc), n(a), n(Lk), n(D)),
                    2 * Cc / (a * Lk * D),
                    k2["tau"] / 1e6,
                    "MPa",
                ),
            ]
    if ex.get("pin") is not None:
        p = ex["pin"]["result"]
        F, d, e2, ns = C["Fp"] * 1e3, C["dp"], C["ep"], C["np"]
        rows += [
            _grp("Goupille / rivet (F en N, d et e en mm)"),
            _hc(
                "Pression de matage (formule du cours)",
                r"P=\frac{2F}{d\,e}=\frac{2\times%s}{%s\times%s}" % (n(F), n(d), n(e2)),
                2 * F / (d * e2),
                p["P"] / 1e6,
                "MPa",
            ),
            _hc(
                "Contrainte de cisaillement",
                r"\tau=\frac{4F}{n\pi d^2}=\frac{4\times%s}{%s\times\pi\times%s^2}" % (n(F), n(ns), n(d)),
                4 * F / (ns * math.pi * d**2),
                p["tau"] / 1e6,
                "MPa",
            ),
        ]
    return rows


def _handTor(saisie: dict, res: dict) -> list[dict]:
    n = _num
    T, r = saisie, res["result"]
    Mt, D, d, G, L = T["Mt"] * 1e6, T["D"], T["d"], T["G"] * 1e3, T["L"] * 1e3
    Kt, Re, s = T["Kt"], T["Re"], T["s"]
    Ix = math.pi * (D**4 - d**4) / 32
    tau = Mt * (D / 2) / Ix
    if "tresca" in T["crit"].lower():
        tauE = Re / 2
        fte = r"\tau_e=\frac{R_e}{2}=\frac{%s}{2}" % n(Re)
    else:
        tauE = Re / math.sqrt(3)
        fte = r"\tau_e=\frac{R_e}{\sqrt3}=\frac{%s}{\sqrt3}" % n(Re)
    th = Mt / (G * Ix)
    return [
        _grp("Arbre circulaire (Mt en N·mm, D et d en mm, G en MPa)"),
        _hc(
            "Moment quadratique polaire",
            r"I_x=\frac{\pi(D^4-d^4)}{32}=\frac{\pi(%s^4-%s^4)}{32}" % (n(D), n(d)),
            Ix,
            r["Ix"] * 1e12,
            "mm⁴",
        ),
        _hc(
            "Contrainte de torsion nominale",
            r"\tau=\frac{M_t\,D/2}{I_x}=\frac{%s\times%s}{%s}" % (n(Mt), n(D / 2), n(Ix)),
            tau,
            r["tauMaxNom"] / 1e6,
            "MPa",
        ),
        _hc(
            "Contrainte maximale",
            r"\tau_{max}=K_t\,\tau=%s\times%s" % (n(Kt), n(tau)),
            Kt * tau,
            r["tauMax"] / 1e6,
            "MPa",
        ),
        _hc("Limite élastique au cisaillement", fte, tauE, (r["tauAdm"] * s) / 1e6, "MPa"),
        _hc(
            "Contrainte admissible",
            r"\tau_{adm}=\frac{\tau_e}{s}=\frac{%s}{%s}" % (n(tauE), n(s)),
            tauE / s,
            r["tauAdm"] / 1e6,
            "MPa",
        ),
        _hc(
            "Angle unitaire de torsion",
            r"\theta=\frac{M_t}{G\,I_x}=\frac{%s}{%s\times%s}\ \mathrm{rad/mm}\ \times\frac{180}{\pi}\times1000"
            % (n(Mt), n(G), n(Ix)),
            math.degrees(th) * 1e3,
            math.degrees(r["theta"]),
            "°/m",
        ),
        _hc(
            "Rotation totale",
            r"\varphi=\theta\,L=%s\times%s" % (n(th), n(L)),
            th * L * 1e3,
            r["phi"]["analytique"] * 1e3,
            "mrad",
        ),
        _hc(
            "Raideur de torsion",
            r"K=\frac{G\,I_x}{L}=\frac{%s\times%s}{%s}" % (n(G), n(Ix), n(L)),
            G * Ix / L,
            r["Ktorsion"] * 1e3,
            "N·mm/rad",
        ),
    ]


def _handFle(saisie: dict, res: dict) -> list[dict]:
    n = _num
    R = res["result"]
    bd, P, F = R["bend"], R["P"], saisie
    N, Mfz, Mfy = F["N"] * 1e3, F["Mfz"] * 1e6, F["Mfy"] * 1e6
    S, Iz, Iy = P["S"] * 1e6, P["Iz"] * 1e12, P["Iy"] * 1e12
    rows = [_grp("Contrainte normale σ = N/S − Mfz·y/Iz + Mfy·z/Iy (N, N·mm, mm)")]
    if abs(P["Iyz"]) > 1e-9 * max(P["Iz"], P["Iy"]):
        rows.append(_grp("Produit d'inertie non nul : formule générale utilisée par le solveur (non recalculée ici)."))
        return rows
    lt = np.asarray(bd["locMaxTraction"]) * 1e3
    lc = np.asarray(bd["locMaxCompression"]) * 1e3
    s1 = N / S - Mfz / Iz * lt[0] + Mfy / Iy * lt[1]
    s2 = N / S - Mfz / Iz * lc[0] + Mfy / Iy * lc[1]

    def fm(p):
        return r"\sigma=\frac{%s}{%s}-\frac{%s}{%s}\times(%s)+\frac{%s}{%s}\times(%s)" % (
            n(N),
            n(S),
            n(Mfz),
            n(Iz),
            n(p[0]),
            n(Mfy),
            n(Iy),
            n(p[1]),
        )

    return rows + [
        _hc("σ au point de traction maximale", fm(lt), s1, bd["sigmaMaxTraction"] / 1e6, "MPa"),
        _hc("σ au point de compression maximale", fm(lc), s2, bd["sigmaMaxCompression"] / 1e6, "MPa"),
        _hc(
            "Contrainte amplifiée Kt·|σ|max",
            r"K_t|\sigma|_{max}=%s\times%s" % (n(F["Kt"]), n(max(abs(s1), abs(s2)))),
            F["Kt"] * max(abs(s1), abs(s2)),
            bd["sigmaMaxKt"] / 1e6,
            "MPa",
        ),
        _hc(
            "Contrainte admissible",
            r"\sigma_{adm}=\frac{R_e}{s}=\frac{%s}{%s}" % (n(F["Re"]), n(F["s"])),
            F["Re"] / F["s"],
            bd["sigmaAdm"] / 1e6,
            "MPa",
        ),
    ]


_COEF_COND = {
    "encastre-libre": 2.0,
    "articule-articule": 1.0,
    "encastre-articule": 1 / math.sqrt(2),
    "encastre-encastre": 0.5,
}


def _handFla(saisie: dict, res: dict) -> list[dict]:
    n = _num
    F, b = saisie, res["result"]["analysis"]
    E, Re, S, Iz, Iy = F["E"] * 1e3, F["Re"], F["S"], F["Iz"], F["Iy"]
    L, s = F["L"] * 1e3, F["s"]
    c = _COEF_COND.get(F["cond"], _NAN)
    Imin = min(Iz, Iy)
    rmin = math.sqrt(Imin / S)
    Lp = c * L
    lam = Lp / rmin
    lim = math.pi * math.sqrt(E / Re)
    PE = math.pi**2 * E * Imin / Lp**2
    PC = Re * S
    PR = PC / (1 + (lam / lim) ** 2)
    if lam < 20:
        Pc, reg = PC, "compression simple (λ < 20)"
    elif lam < lim:
        Pc, reg = PR, "Rankine (20 ≤ λ < λlim)"
    else:
        Pc, reg = PE, "Euler (λ ≥ λlim)"
    return [
        _grp("Flambage (E, Re en MPa ; S en mm² ; I en mm⁴ ; L en mm ; charges en kN)"),
        _hc("Inertie minimale", r"I_{min}=\min(I_z,I_y)=\min(%s;%s)" % (n(Iz), n(Iy)), Imin, b["Imin"] * 1e12, "mm⁴"),
        _hc(
            "Rayon de giration minimal",
            r"r_{min}=\sqrt{I_{min}/S}=\sqrt{%s/%s}" % (n(Imin), n(S)),
            rmin,
            b["rmin"] * 1e3,
            "mm",
        ),
        _hc("Longueur de flambement", r"L'=c\,L=%s\times%s" % (n(c), n(L)), Lp * 1e-3, b["Lp"], "m"),
        _hc("Élancement", r"\lambda=\frac{L'}{r_{min}}=\frac{%s}{%s}" % (n(Lp), n(rmin)), lam, b["lambda"]),
        _hc(
            "Élancement limite",
            r"\lambda_{lim}=\pi\sqrt{E/R_e}=\pi\sqrt{%s/%s}" % (n(E), n(Re)),
            lim,
            b["lambdaLim"],
        ),
        _hc(
            "Charge d'Euler",
            r"P_E=\frac{\pi^2E\,I_{min}}{L'^2}=\frac{\pi^2\times%s\times%s}{%s^2}" % (n(E), n(Imin), n(Lp)),
            PE / 1e3,
            b["PE"] / 1e3,
            "kN",
        ),
        _hc("Charge de compression simple", r"P_C=R_e\,S=%s\times%s" % (n(Re), n(S)), PC / 1e3, b["PC"] / 1e3, "kN"),
        _hc(
            "Charge de Rankine",
            r"P_R=\frac{R_eS}{1+(\lambda/\lambda_{lim})^2}=\frac{%s}{1+(%s/%s)^2}" % (n(PC), n(lam), n(lim)),
            PR / 1e3,
            b["PR"] / 1e3,
            "kN",
        ),
        _grp("Régime retenu par l'arbre de décision : " + reg),
        _hc("Charge critique retenue", r"P_{crit}=%s\,\mathrm{kN}" % n(Pc / 1e3), Pc / 1e3, b["Pcrit"] / 1e3, "kN"),
        _hc(
            "Charge admissible",
            r"P_{adm}=\frac{P_{crit}}{s}=\frac{%s}{%s}" % (n(Pc / 1e3), n(s)),
            Pc / s / 1e3,
            b["Padm"] / 1e3,
            "kN",
        ),
    ]


def _handTen(saisie: dict, res: dict) -> list[dict]:
    n = _num
    T, r = saisie, res["result"]
    sg = np.array(T["sig"], dtype=float)
    sg = (sg + sg.T) / 2
    ev = np.sort(np.linalg.eigvalsh(sg))[::-1]
    I1 = np.trace(sg)
    I2 = (np.trace(sg) ** 2 - np.trace(sg @ sg)) / 2
    I3 = np.linalg.det(sg)
    pr, cr, fa = r["principal"], r["criteria"], r["facet"]
    Re, s = T["Re"], T["s"]
    tre = ev[0] - ev[2]
    vm = math.sqrt(0.5 * ((ev[0] - ev[1]) ** 2 + (ev[1] - ev[2]) ** 2 + (ev[0] - ev[2]) ** 2))
    nv = np.asarray(fa["n"], dtype=float).ravel()
    Cn = sg @ nv
    sn = float(Cn @ nv)
    tn = float(np.linalg.norm(Cn - sn * nv))  # même définition que le solveur ; √(|C|² − σn²) donne du bruit près de 0
    return [
        _grp("Invariants et contraintes principales (MPa)"),
        _hc(
            "Premier invariant",
            r"I_1=\mathrm{tr}\,\sigma=%s+%s+%s" % (n(sg[0, 0]), n(sg[1, 1]), n(sg[2, 2])),
            I1,
            pr["I1"] / 1e6,
            "MPa",
        ),
        _hc(
            "Deuxième invariant",
            r"I_2=\tfrac12[(\mathrm{tr}\,\sigma)^2-\mathrm{tr}(\sigma^2)]",
            I2,
            pr["I2"] / 1e12,
            "MPa²",
        ),
        _hc("Troisième invariant", r"I_3=\det\sigma", I3, pr["I3"] / 1e18, "MPa³"),
        _hc("Contrainte principale σI", r"\sigma_I=\max\ \mathrm{eig}(\sigma)", ev[0], pr["sigmaI"] / 1e6, "MPa"),
        _hc("Contrainte principale σII", r"\sigma_{II}", ev[1], pr["sigmaII"] / 1e6, "MPa"),
        _hc(
            "Contrainte principale σIII", r"\sigma_{III}=\min\ \mathrm{eig}(\sigma)", ev[2], pr["sigmaIII"] / 1e6, "MPa"
        ),
        _grp("Critères de résistance"),
        _hc("Tresca", r"\sigma_I-\sigma_{III}=%s-(%s)" % (n(ev[0]), n(ev[2])), tre, cr["sigmaEqTresca"] / 1e6, "MPa"),
        _hc(
            "Von Mises",
            r"\sigma_{VM}=\sqrt{\tfrac12[(\sigma_I-\sigma_{II})^2+(\sigma_{II}-\sigma_{III})^2+(\sigma_I-\sigma_{III})^2]}",
            vm,
            cr["sigmaEqVM"] / 1e6,
            "MPa",
        ),
        _hc(
            "Contrainte admissible", r"\frac{R_e}{s}=\frac{%s}{%s}" % (n(Re), n(s)), Re / s, cr["sigmaAdm"] / 1e6, "MPa"
        ),
        _grp("Facette de normale n"),
        _hc("Contrainte normale", r"\sigma_n=\vec n^T[\sigma]\vec n", sn, fa["sigmaN"] / 1e6, "MPa"),
        _hc("Contrainte tangentielle", r"\tau=\sqrt{|\vec C|^2-\sigma_n^2}", tn, fa["tauNorm"] / 1e6, "MPa"),
    ]


def _handHoo(saisie: dict, res: dict) -> list[dict]:
    n = _num
    K, R = saisie, res["result"]
    E, nu = K["E"] * 1e3, K["nu"]
    G = E / (2 * (1 + nu))
    al, dT = K["alpha"] * 1e-6, K["dT"]
    sx, sy, sz, syz, sxz, sxy = (K[c] for c in ("sxx", "syy", "szz", "syz", "sxz", "sxy"))
    v = res["tables"]["Résultats"].iloc[:, 1].to_numpy(dtype=float)
    rows: list[dict] = []
    if K["mode"] == "iso3D":
        exx = (sx - nu * (sy + sz)) / E + al * dT
        eyy = (sy - nu * (sx + sz)) / E + al * dT
        ezz = (sz - nu * (sx + sy)) / E + al * dT
        rows = [
            _grp("Hooke isotrope 3D (contraintes en MPa, E en MPa) ; déformations en µdéf"),
            _hc(
                "εxx",
                r"\varepsilon_{xx}=\frac{\sigma_{xx}-\nu(\sigma_{yy}+\sigma_{zz})}{E}+\alpha\Delta T="
                r"\frac{%s-%s(%s+%s)}{%s}" % (n(sx), n(nu), n(sy), n(sz), n(E)),
                exx * 1e6,
                v[0],
                "µdéf",
            ),
            _hc(
                "εyy",
                r"\varepsilon_{yy}=\frac{\sigma_{yy}-\nu(\sigma_{xx}+\sigma_{zz})}{E}+\alpha\Delta T",
                eyy * 1e6,
                v[1],
                "µdéf",
            ),
            _hc(
                "εzz",
                r"\varepsilon_{zz}=\frac{\sigma_{zz}-\nu(\sigma_{xx}+\sigma_{yy})}{E}+\alpha\Delta T",
                ezz * 1e6,
                v[2],
                "µdéf",
            ),
            _hc("γyz", r"\gamma_{yz}=\frac{\tau_{yz}}{G}=\frac{%s}{%s}" % (n(syz), n(G)), syz / G * 1e6, v[3], "µdéf"),
            _hc("γxz", r"\gamma_{xz}=\frac{\tau_{xz}}{G}", sxz / G * 1e6, v[4], "µdéf"),
            _hc("γxy", r"\gamma_{xy}=\frac{\tau_{xy}}{G}=\frac{%s}{%s}" % (n(sxy), n(G)), sxy / G * 1e6, v[5], "µdéf"),
        ]
    elif K["mode"] == "planeStress":
        exx = (sx - nu * sy) / E
        eyy = (sy - nu * sx) / E
        ezz = -nu * (sx + sy) / E
        rows = [
            _grp("Contraintes planes (σzz = τxz = τyz = 0) ; déformations en µdéf"),
            _hc(
                "εxx",
                r"\varepsilon_{xx}=\frac{\sigma_{xx}-\nu\sigma_{yy}}{E}=\frac{%s-%s\times%s}{%s}"
                % (n(sx), n(nu), n(sy), n(E)),
                exx * 1e6,
                v[0],
                "µdéf",
            ),
            _hc("εyy", r"\varepsilon_{yy}=\frac{\sigma_{yy}-\nu\sigma_{xx}}{E}", eyy * 1e6, v[1], "µdéf"),
            _hc("εzz", r"\varepsilon_{zz}=-\frac{\nu(\sigma_{xx}+\sigma_{yy})}{E}", ezz * 1e6, v[2], "µdéf"),
            _hc("γxy", r"\gamma_{xy}=\frac{\tau_{xy}}{G}=\frac{%s}{%s}" % (n(sxy), n(G)), sxy / G * 1e6, v[3], "µdéf"),
        ]
    elif K["mode"] == "planeStrain":
        ex, ey, gx = K["exx"] * 1e-6, K["eyy"] * 1e-6, K["gxy"] * 1e-6
        c = E / ((1 + nu) * (1 - 2 * nu))
        sxx = c * ((1 - nu) * ex + nu * ey)
        syy = c * ((1 - nu) * ey + nu * ex)
        sxy2 = G * gx
        szz = nu * (sxx + syy)
        rows = [
            _grp("Déformations planes (εzz = γxz = γyz = 0) ; contraintes en MPa"),
            _hc(
                "σxx",
                r"\sigma_{xx}=\frac{E}{(1+\nu)(1-2\nu)}[(1-\nu)\varepsilon_{xx}+\nu\varepsilon_{yy}]",
                sxx,
                v[0],
                "MPa",
            ),
            _hc(
                "σyy",
                r"\sigma_{yy}=\frac{E}{(1+\nu)(1-2\nu)}[(1-\nu)\varepsilon_{yy}+\nu\varepsilon_{xx}]",
                syy,
                v[1],
                "MPa",
            ),
            _hc("σxy", r"\tau_{xy}=G\,\gamma_{xy}=%s\times%s" % (n(G), n(gx)), sxy2, v[2], "MPa"),
            _hc("σzz", r"\sigma_{zz}=\nu(\sigma_{xx}+\sigma_{yy})", szz, v[3], "MPa"),
        ]
    elif K["mode"] == "ortho":
        E1, E2, E3 = K["E1"] * 1e3, K["E2"] * 1e3, K["E3"] * 1e3
        n12, n13, n23 = K["nu12"], K["nu13"], K["nu23"]
        G12, G13, G23 = K["G12"] * 1e3, K["G13"] * 1e3, K["G23"] * 1e3
        n21, n31, n32 = n12 * E2 / E1, n13 * E3 / E1, n23 * E3 / E2
        e11 = sx / E1 - n21 * sy / E2 - n31 * sz / E3
        e22 = -n12 * sx / E1 + sy / E2 - n32 * sz / E3
        e33 = -n13 * sx / E1 - n23 * sy / E2 + sz / E3
        rows = [
            _grp(
                "Orthotrope : [S] symétrique, ν21 = ν12·E2/E1, ν31 = ν13·E3/E1, ν32 = ν23·E3/E2 ; déformations en µdéf"
            ),
            _hc(
                "ε11",
                r"\varepsilon_{11}=\frac{\sigma_{11}}{E_1}-\frac{\nu_{21}\sigma_{22}}{E_2}-\frac{\nu_{31}\sigma_{33}}{E_3}",
                e11 * 1e6,
                v[0],
                "µdéf",
            ),
            _hc(
                "ε22",
                r"\varepsilon_{22}=-\frac{\nu_{12}\sigma_{11}}{E_1}+\frac{\sigma_{22}}{E_2}-\frac{\nu_{32}\sigma_{33}}{E_3}",
                e22 * 1e6,
                v[1],
                "µdéf",
            ),
            _hc(
                "ε33",
                r"\varepsilon_{33}=-\frac{\nu_{13}\sigma_{11}}{E_1}-\frac{\nu_{23}\sigma_{22}}{E_2}+\frac{\sigma_{33}}{E_3}",
                e33 * 1e6,
                v[2],
                "µdéf",
            ),
            _hc("γ23", r"\gamma_{23}=\frac{\tau_{23}}{G_{23}}", syz / G23 * 1e6, v[3], "µdéf"),
            _hc("γ13", r"\gamma_{13}=\frac{\tau_{13}}{G_{13}}", sxz / G13 * 1e6, v[4], "µdéf"),
            _hc("γ12", r"\gamma_{12}=\frac{\tau_{12}}{G_{12}}", sxy / G12 * 1e6, v[5], "µdéf"),
        ]
    ex, ey, exy = R["exx"], R["eyy"], R["exy"]
    cen = (ex + ey) / 2
    rad = math.sqrt(((ex - ey) / 2) ** 2 + exy**2)
    m = R["mohr"]
    return rows + [
        _grp("Cercle de Mohr des déformations dans le plan (x, y), en µdéf"),
        _hc(
            "Centre",
            r"\delta=\frac{\varepsilon_{xx}+\varepsilon_{yy}}{2}",
            cen * 1e6,
            (m["sigma1"] + m["sigma2"]) / 2 * 1e6,
            "µdéf",
        ),
        _hc(
            "Déformation principale ε1",
            r"\varepsilon_1=\delta+\rho,\ "
            r"\rho=\sqrt{\left(\frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\right)^2+\varepsilon_{xy}^2}",
            (cen + rad) * 1e6,
            m["sigma1"] * 1e6,
            "µdéf",
        ),
        _hc("Déformation principale ε2", r"\varepsilon_2=\delta-\rho", (cen - rad) * 1e6, m["sigma2"] * 1e6, "µdéf"),
    ]


def _handJau(saisie: dict, res: dict) -> list[dict]:
    n = _num
    J, R = saisie, res["result"]
    K, eps, R0, Vin = J["K"], J["eps"] * 1e-6, J["R0"], J["Vin"]
    e4 = np.array([J["e1"], J["e2"], J["e3"], J["e4"]]) * 1e-6
    if J["cfg"] == "quart":
        ev, fac = np.array([e4[0], 0, 0, 0]), 1
    elif J["cfg"] == "demi":
        ev, fac = np.array([e4[0], e4[1], 0, 0]), 2
    else:
        ev, fac = e4, 4
    Vout = Vin * K / 4 * (ev[0] - ev[1] + ev[2] - ev[3])
    Vm = J["Vout"] * 1e-3
    ebr = 4 * Vm / (K * Vin) / fac
    ra, rb, rc = J["ra"] * 1e-6, J["rb"] * 1e-6, J["rc"] * 1e-6
    E, nu = J["E"] * 1e3, J["nu"]
    if J["rtype"] == "60":
        exx, eyy, exy = ra, (2 * (rb + rc) - ra) / 3, (rb - rc) / math.sqrt(3)
        fr = (
            r"\varepsilon_{xx}=\varepsilon_0,\ \varepsilon_{yy}=\frac{2(\varepsilon_{60}+\varepsilon_{120})"
            r"-\varepsilon_0}{3},\ \varepsilon_{xy}=\frac{\varepsilon_{60}-\varepsilon_{120}}{\sqrt3}"
        )
    else:
        exx, eyy, exy = ra, rb, rc - (ra + rb) / 2
        fr = (
            r"\varepsilon_{xx}=\varepsilon_0,\ \varepsilon_{yy}=\varepsilon_{90},\ "
            r"\varepsilon_{xy}=\varepsilon_{45}-\frac{\varepsilon_0+\varepsilon_{90}}{2}"
        )
    cen = (exx + eyy) / 2
    rad = math.sqrt(((exx - eyy) / 2) ** 2 + exy**2)
    sxx = E / (1 - nu**2) * (exx + nu * eyy)
    syy = E / (1 - nu**2) * (eyy + nu * exx)
    sxy = E / (1 + nu) * exy
    cs = (sxx + syy) / 2
    rs = math.sqrt(((sxx - syy) / 2) ** 2 + sxy**2)
    g, br, ro = R["gauge"], R["bridge"], R["rosette"]
    return [
        _grp("Jauge (loi de Bridgman)"),
        _hc(
            "Variation relative de résistance",
            r"\frac{\Delta R}{R}=K\,\varepsilon=%s\times%s" % (n(K), n(eps)),
            K * eps,
            g["dRsurR"],
        ),
        _hc(
            "Variation de résistance",
            r"\Delta R=R_0\,K\,\varepsilon=%s\times%s\times%s" % (n(R0), n(K), n(eps)),
            R0 * K * eps,
            g["dR"],
            "Ω",
        ),
        _grp("Pont de Wheatstone"),
        _hc(
            "Tension de sortie linéarisée",
            r"V_{out}=\frac{V_{in}K}{4}(\varepsilon_1-\varepsilon_2+\varepsilon_3-\varepsilon_4)=\frac{%s\times%s}{4}(\ldots)"
            % (n(Vin), n(K)),
            Vout * 1e3,
            br["Vout"] * 1e3,
            "mV",
        ),
        _hc(
            "Déformation déduite de Vout mesurée",
            r"\varepsilon=\frac{4V_{out}}{K\,V_{in}}\Big/\text{facteur de pont}=\frac{4\times%s}{%s\times%s}\Big/%d"
            % (n(Vm), n(K), n(Vin), fac),
            ebr * 1e6,
            float(np.ravel(R["bridgeStrain"])[0]) * 1e6,
            "µdéf",
        ),
        _grp("Rosette (déformations en µdéf, contraintes en MPa)"),
        _hc("Déformation εxx", fr, exx * 1e6, ro["exx"] * 1e6, "µdéf"),
        _hc("Déformation εyy", r"\varepsilon_{yy}", eyy * 1e6, ro["eyy"] * 1e6, "µdéf"),
        _hc("Déformation εxy", r"\varepsilon_{xy}", exy * 1e6, ro["exy"] * 1e6, "µdéf"),
        _hc(
            "Déformation principale εI",
            r"\varepsilon_I=\delta+\rho=%s+%s" % (n(cen * 1e6), n(rad * 1e6)),
            (cen + rad) * 1e6,
            ro["epsI"] * 1e6,
            "µdéf",
        ),
        _hc(
            "Déformation principale εII", r"\varepsilon_{II}=\delta-\rho", (cen - rad) * 1e6, ro["epsII"] * 1e6, "µdéf"
        ),
        _hc(
            "Contrainte σxx (contraintes planes)",
            r"\sigma_{xx}=\frac{E}{1-\nu^2}(\varepsilon_{xx}+\nu\varepsilon_{yy})=\frac{%s}{1-%s^2}(\ldots)"
            % (n(E), n(nu)),
            sxx,
            ro["sxx"] / 1e6,
            "MPa",
        ),
        _hc(
            "Contrainte σyy",
            r"\sigma_{yy}=\frac{E}{1-\nu^2}(\varepsilon_{yy}+\nu\varepsilon_{xx})",
            syy,
            ro["syy"] / 1e6,
            "MPa",
        ),
        _hc("Contrainte σxy", r"\tau_{xy}=\frac{E}{1+\nu}\varepsilon_{xy}", sxy, ro["sxy"] / 1e6, "MPa"),
        _hc(
            "Contrainte principale σI",
            r"\sigma_I=\frac{\sigma_{xx}+\sigma_{yy}}{2}+\sqrt{\left(\frac{\sigma_{xx}-\sigma_{yy}}{2}\right)^2+\tau_{xy}^2}",
            cs + rs,
            ro["sigmaI"] / 1e6,
            "MPa",
        ),
    ]


def _handTruss(saisie: dict, res: dict) -> list[dict]:
    n = _num
    R = res["result"]
    tr, ts = R["truss"], R["tsol"]
    X = np.asarray(tr["nodes"], dtype=float)
    B = np.asarray(tr["bars"], dtype=int)  # numéros de nœuds à partir de 1
    m, dim, nn = len(B), X.shape[1], len(X)
    E = np.broadcast_to(np.atleast_1d(np.asarray(tr["E"], dtype=float)), (m,))
    S = np.broadcast_to(np.atleast_1d(np.asarray(tr["S"], dtype=float)), (m,))
    N = np.asarray(ts["N"], dtype=float)
    disp = np.asarray(ts["displacements"], dtype=float)
    Lh = np.zeros(m)
    U = np.zeros((m, dim))
    for k in range(m):
        dv = X[B[k, 1] - 1] - X[B[k, 0] - 1]
        Lh[k] = np.linalg.norm(dv)
        U[k] = dv / Lh[k]
    sigH = N / S
    dLH = N * Lh / (E * S)
    # compatibilité : allongement déduit des déplacements nodaux
    dLc = np.array([U[k] @ (disp[B[k, 1] - 1] - disp[B[k, 0] - 1]) for k in range(m)])
    # équilibre nodal : Σ N u + F + R = 0
    loads = np.asarray(tr["loads"], dtype=float)
    reac = np.asarray(ts["reactions"], dtype=float)
    resid = loads + reac
    for k in range(m):
        resid[B[k, 0] - 1] += N[k] * U[k]
        resid[B[k, 1] - 1] -= N[k] * U[k]
    fscale = max(1.0, float(np.max(np.abs(loads))), float(np.max(np.abs(reac))))
    rows = [
        _grp("Équilibre et compatibilité (vérifiés indépendamment du solveur)"),
        _hc(
            "Résidu d'équilibre de tous les nœuds (N)",
            r"\max_i\left\|\sum_j N_{ij}\vec u_{ij}+\vec F_i+\vec R_i\right\|\ \text{(attendu 0)}",
            float(np.max(np.linalg.norm(resid, axis=1))),
            0.0,
            "N",
            1e-6 * fscale,
        ),
        _hc(
            "Somme des forces extérieures + réactions (N)",
            r"\left\|\sum_i(\vec F_i+\vec R_i)\right\|\ \text{(attendu 0)}",
            float(np.linalg.norm(np.sum(loads + reac, axis=0))),
            0.0,
            "N",
            1e-6 * fscale,
        ),
        _hc(
            "Compatibilité : allongement des barres (max d'écart)",
            r"\Delta L_{barre}=\vec u_{ij}\cdot(\vec u_j-\vec u_i)\ \text{contre}\ \frac{N\,L}{E\,S}",
            float(np.max(np.abs(dLc - dLH))) * 1e3,
            0.0,
            "mm",
            1e-6 * max(1e-3, float(np.max(np.abs(dLH))) * 1e3),
        ),
        _hc(
            "Longueurs des barres (écart max)",
            r"L=\sqrt{(x_j-x_i)^2+(y_j-y_i)^2}",
            float(np.max(np.abs(Lh - np.asarray(ts["L0"], dtype=float)))),
            0.0,
            "m",
            1e-9,
        ),
        _hc(
            "Contraintes σ = N/S (écart max)",
            r"\sigma=\frac{N}{S}",
            float(np.max(np.abs(sigH - np.asarray(ts["sigma"], dtype=float)))) / 1e6,
            0.0,
            "MPa",
            1e-6 * max(1.0, float(np.max(np.abs(sigH))) / 1e6),
        ),
        _hc(
            "Hyperstatisme",
            r"h=m+r-d\,n=%d+%d-%d\times%d" % (m, int(np.count_nonzero(tr["supports"])), dim, nn),
            m + int(np.count_nonzero(tr["supports"])) - dim * nn,
            ts["h"],
        ),
        _grp("Détail par barre : N (solveur), σ = N/S et ΔL = N·L/(E·S) recalculés"),
    ]
    sg = np.asarray(ts["sigma"], dtype=float)
    dl = np.asarray(ts["dL"], dtype=float)
    for k in range(m):
        nm = f"Barre {k + 1} (nœuds {B[k, 0]}–{B[k, 1]})"
        rows.append(
            _hc(
                f"{nm} : σ",
                r"\sigma=\frac{%s\,\mathrm{N}}{%s\,\mathrm{m^2}}" % (n(N[k]), n(S[k])),
                sigH[k] / 1e6,
                sg[k] / 1e6,
                "MPa",
            )
        )
        rows.append(
            _hc(
                f"{nm} : ΔL",
                r"\Delta L=\frac{N\,L}{E\,S}=\frac{%s\times%s}{%s\times%s}" % (n(N[k]), n(Lh[k]), n(E[k]), n(S[k])),
                dLH[k] * 1e3,
                dl[k] * 1e3,
                "mm",
            )
        )
    return rows


def _qint(c, a: float, b: float, f) -> float:
    """∫ p(x)·f(x) dx sur [a, b], avec p(x) = polyval(c, x − a) (charge répartie polynomiale)."""
    return float(quad(lambda x: np.polyval(c, x - a) * f(x), a, b, epsabs=0, epsrel=1e-12)[0])


def _t(v: float) -> str:
    """Nombre LaTeX d'un terme de somme : entre parenthèses s'il est négatif."""
    return f"({_num(v)})" if v < 0 else _num(v)


def _termes(groupes: list[tuple[str, list[str]]]) -> str:
    """Somme LaTeX de termes déjà formatés, chaque groupe légendé sous une accolade ; « 0 » si tout est vide."""
    return " + ".join(r"\underbrace{%s}_{\text{%s}}" % (" + ".join(t), leg) for leg, t in groupes if t) or "0"


def _beamPlaneRows(sol: dict, plane: str) -> list[dict]:
    """Équilibre global et torseur de cohésion (par la gauche) d'un plan de flexion.

    Plan 'y' : plan (x, y), Mfz et Ty ; plan 'z' : plan (x, z) équivalent (F' = Fz, C' = −My, p' = pz), avec
    Mfy = −M' et Tz = T'. Chaque formule porte les valeurs de la saisie (kN, kN·m) pour être refaite à la main.
    """
    n = _num
    mo = sol["model"]
    L = mo["L"]
    rea, pl, pm, dl = sol["reactions"], mo["pointLoads"], mo["pointMoments"], mo["distLoads"]
    if plane == "y":
        fF, fC, fR, sC, sM, Mpp, Tpp = "Fy", "Mz", "Ry", 1, 1, sol["Mfz"], sol["Ty"]
        lab, nM, nT, nF = "(x, y)", "Mfz", "Ty", "y"
    else:
        fF, fC, fR, sC, sM, Mpp, Tpp = "Fz", "My", "Rz", -1, -1, sol["Mfy"], sol["Tz"]
        lab, nM, nT, nF = "(x, z)", "Mfy", "Tz", "z"
    px = [p["pos"] for p in pl]
    F = [p[fF] for p in pl]
    cx = [p["pos"] for p in pm]
    C = [sC * p[fC] for p in pm]
    rp = [r["pos"] for r in rea]
    rR = [r[fR] for r in rea]
    rM = [sC * r[fC] for r in rea]
    dist = [(d["a"], d["b"], np.asarray(d["coeffs"], dtype=float)) for d in dl if d["dir"] == nF]
    qF = [_qint(c, a, b, lambda x: 1.0) for a, b, c in dist]  # résultantes des charges réparties
    qM = [_qint(c, a, b, lambda x: x) for a, b, c in dist]  # leurs moments par rapport à s = 0
    sumF = sum(F) + sum(rR) + sum(qF)
    sumM = sum(x * f for x, f in zip(px, F, strict=True)) + sum(C) + sum(x * r for x, r in zip(rp, rR, strict=True))
    sumM += sum(rM) + sum(qM)
    fsc = max([1.0, *map(abs, F), *map(abs, rR)])
    tolE = 1e-6 * fsc * max(1.0, L)

    def kN(v: float) -> str:
        return _t(v / 1e3)

    termesF = _termes(
        [
            ("forces", [kN(f) for f in F if f]),
            (r"r\'eparties", [kN(q) for q in qF if q]),
            (r"r\'eactions", [kN(r) for r in rR if r]),
        ]
    )
    termesM = _termes(
        [
            ("forces", [f"{n(x)}\\times{kN(f)}" for x, f in zip(px, F, strict=True) if x and f]),
            (r"r\'eparties", [kN(q) for q in qM if q]),
            ("couples", [kN(c) for c in C if c]),
            (
                r"r\'eactions",
                [f"{n(x)}\\times{kN(r)}" for x, r in zip(rp, rR, strict=True) if x and r] + [kN(m) for m in rM if m],
            ),
        ]
    )
    rows = [
        _grp(
            f"Équilibre global de la poutre, plan {lab} : la somme des forces et des moments (charges + réactions du "
            "solveur) doit être nulle"
        ),
        _hc(
            f"Équilibre des forces en {nF}",
            r"\sum F_%s=%s=%s\ \mathrm{kN}" % (nF, termesF, n(sumF / 1e3)),
            sumF / 1e3,
            0.0,
            "kN",
            tolE / 1e3,
        ),
        _hc(
            f"Équilibre des moments du plan {lab}, pris en s = 0",
            r"\sum M(0)=%s=%s\ \mathrm{kN\cdot m}" % (termesM, n(sumM / 1e3)),
            sumM / 1e3,
            0.0,
            "kN·m",
            tolE * max(1.0, L) / 1e3,
        ),
    ]
    # coupes : extrémités, abscisses types, extrema de M et de T ; décalées si elles tombent sur une charge ou un appui
    ex, exT = sol["extrema"][nM], sol["extrema"][nT]
    s0 = [0.0, *(L * x for x in (0.1, 0.25, 0.5, 0.75, 0.9)), L]
    s0 += [float(ex["sMax"]), float(ex["sMin"]), float(exT["sMax"]), float(exT["sMin"])]
    s0 = sorted({round(s, 9) for s in s0})
    posAll = px + cx + rp
    apres: dict[float, str] = {}  # coupe décalée : « juste après / avant » la charge, dit dans l'étiquette
    for k, s in enumerate(s0):
        if any(abs(p - s) < 1e-9 for p in posAll):
            # charge en s = L : couper juste avant, sinon la somme à gauche l'inclut
            avant = s + 1e-6 * L > L
            s0[k] = s - 1e-6 * L if avant else s + 1e-6 * L
            apres[s0[k]] = " (juste avant la charge ou l'appui)" if avant else " (juste après la charge ou l'appui)"
    rows.append(
        _grp(
            f"Plan {lab} : {nM} et {nT} recalculés en sommant les actions à GAUCHE de la coupure "
            "(le solveur somme à droite) : M(s) = Σ[(s − xᵢ)·Fᵢ − Cᵢ] + ∫(s − x)·p dx ; T(s) = −ΣF − ∫p dx. "
            "Coupes aux extrémités, à 10-25-50-75-90 % de L et aux extrema"
        )
    )
    for s in s0:
        Mh = Th = 0.0
        tM: list[str] = []  # termes de M(s) et de T(s), en kN et kN·m, pour les refaire à la main
        tT: list[str] = []
        for x, f in zip(px, F, strict=True):
            if x < s:
                Mh += (s - x) * f
                Th -= f
                if f:
                    tM.append(f"{kN(f)}\\times({n(s)}-{n(x)})")
                    tT.append(kN(-f))
        for x, c in zip(cx, C, strict=True):
            if x < s:
                Mh -= c
                if c:
                    tM.append(kN(-c))
        for x, r, m in zip(rp, rR, rM, strict=True):
            if x < s:
                Mh += (s - x) * r - m
                Th -= r
                if r:
                    tM.append(f"{kN(r)}\\times({n(s)}-{n(x)})")
                    tT.append(kN(-r))
                if m:
                    tM.append(kN(-m))
        for a, b, c in dist:
            if s > a:
                bb = min(b, s)
                dM, dT = _qint(c, a, bb, lambda x, s=s: s - x), -_qint(c, a, bb, lambda x: 1.0)
                Mh += dM
                Th += dT
                tM.append(kN(dM))
                tT.append(kN(dT))
        Mh *= sM
        enM = " + ".join(tM) or "0"
        enT = " + ".join(tT) or "0"
        if sM < 0:  # plan (x, z) : Mfy = −M' (convention du solveur)
            enM = r"-\left(%s\right)" % enM
        Ms = ppEval(Mpp, s)
        Ts = ppEval(Tpp, s)
        tolM = 1e-6 * max(1.0, abs(Ms)) + 1e-6
        tolT = 1e-6 * max(1.0, abs(Ts)) + 1e-6
        rows.append(
            _hc(
                f"{nM} en s = {s:.4g} m{apres.get(s, '')}",
                r"M(s)=%s=%s\,\mathrm{kN\cdot m}" % (enM, n(Mh / 1e3)),
                Mh / 1e3,
                Ms / 1e3,
                "kN·m",
                tolM / 1e3,
            )
        )
        rows.append(
            _hc(
                f"{nT} en s = {s:.4g} m{apres.get(s, '')}",
                r"T(s)=%s=%s\,\mathrm{kN}" % (enT, n(Th / 1e3)),
                Th / 1e3,
                Ts / 1e3,
                "kN",
                tolT / 1e3,
            )
        )
    return rows


def _handImposed(B: dict) -> list[dict]:
    """Appuis élastiques, tassements et rotules : conditions que le résultat doit vérifier, lues sur la solution
    (flèche aux appuis, moment aux rotules), sans refaire le calcul des réactions."""
    n = _num
    mo = B["sol"]["model"]
    sup = mo["supports"]
    rows: list[dict] = []
    if sup and (any(s["spring"] > 0 for s in sup) or any(abs(s[c]) > 0 for s in sup for c in ("dx", "dy", "dz"))):
        rows.append(
            _grp(
                "Appuis élastiques et tassements : déplacement de chaque appui = tassement − R/k "
                "(flèche de la déformée, plan affiché)"
            )
        )
        rf, df = ("Ry", "dy") if B["defl"]["plane"] == "xy" else ("Rz", "dz")
        for i, s in enumerate(sup):
            d = s[df]
            R = B["sol"]["reactions"][i][rf]
            if s["spring"] > 0:
                d = d - R / s["spring"]
            v = ppEval(B["defl"]["integration"]["vPP"], s["pos"], "left")
            rows.append(
                _hc(
                    f"Déplacement de l'appui {s['name']} (mm)",
                    r"v(s_%d)=d-\frac{R}{k}=%s-\frac{%s}{%s}"
                    % (i + 1, n(s[df] * 1e3), n(R), n(max(s["spring"], np.finfo(float).eps))),
                    d * 1e3,
                    v * 1e3,
                    "mm",
                    1e-6 * max(1.0, abs(d * 1e3)),
                )
            )
    hg = mo["hinges"]
    if hg:
        rows.append(_grp("Rotules intermédiaires : moment de flexion nul"))
        mscale = float(np.max(np.abs(ppEval(B["sol"]["Mfz"], np.linspace(0, mo["L"], 41)))))
        for h in hg:
            m = ppEval(B["sol"]["Mfz"], h["pos"], "left")
            rows.append(
                _hc(
                    f"M_fz à la rotule {h['name']} (N·m)",
                    r"M_{fz}(%s)=%s\ \text{(attendu 0)}" % (n(h["pos"]), n(m)),
                    0.0,
                    m,
                    "N·m",
                    1e-6 * max(1.0, mscale),
                )
            )
    return rows


def _handBeam(saisie: dict, res: dict) -> list[dict]:
    n = _num
    B = res
    sol = B["sol"]
    mo = sol["model"]
    L = mo["L"]
    rea, pl, pm, dl = sol["reactions"], mo["pointLoads"], mo["pointMoments"], mo["distLoads"]
    Fx = [p["Fx"] for p in pl]
    rRx = [r["Rx"] for r in rea]
    distX = [(d["a"], d["b"], np.asarray(d["coeffs"], dtype=float)) for d in dl if d["dir"] == "x"]
    sumFx = sum(Fx) + sum(rRx) + sum(_qint(c, a, b, lambda x: 1.0) for a, b, c in distX)
    rows = [
        _grp("Équilibre axial, recalculé à partir du modèle et des réactions du solveur"),
        _hc(
            "Équilibre des forces en x (N)",
            r"\sum F_x=%s\ \text{(attendu 0)}" % n(sumFx),
            sumFx,
            0.0,
            "N",
            1e-6 * max([1.0, *map(abs, Fx), *map(abs, rRx)]) * max(1.0, L),
        ),
    ]
    # plan (x, y) toujours ; plan (x, z) seulement s'il y a des charges ou des réactions en z
    rows += _beamPlaneRows(sol, "y")
    hasZ = (
        any(p["Fz"] != 0 for p in pl)
        or any(p["My"] != 0 for p in pm)
        or any(d["dir"] == "z" for d in dl)
        or any(r["Rz"] != 0 or r["My"] != 0 for r in rea)
    )
    if hasZ:
        rows += _beamPlaneRows(sol, "z")
    rows += _handImposed(B)
    # contrainte au point le plus sollicité
    chk = B["check"]
    bd = chk["bend"]
    S, Iz, Iy = saisie["S"], saisie["Iz"], saisie["Iy"]
    sec = _sec(saisie)
    secT = sec["type"] if sec is not None else ""
    if saisie["Iyz"] != 0:
        rows.append(
            _grp(
                "Contrainte au point le plus sollicité : Iyz ≠ 0, flexion déviée : NON recalculée à la main "
                "(la loi de Navier à axes principaux ne s'applique pas). "
                f"Valeur du solveur : |σ|max = {bd['sigmaMaxAbs'] / 1e6:.6g} MPa"
            )
        )
    elif secT in ("T", "U", "L", "composite"):
        rows.append(
            _grp(
                f"Contrainte au point le plus sollicité : section dissymétrique ({secT}), contour exact utilisé par "
                "le solveur : NON recalculée à la main. "
                f"Valeur du solveur : |σ|max = {bd['sigmaMaxAbs'] / 1e6:.6g} MPa"
            )
        )
    else:
        # maximum de |σ| de la loi de Navier, trouvé sans le solveur : sur les 4 coins des fibres extrêmes saisies,
        # ou sur le cercle (module du moment résultant) pour un disque ou une couronne
        if secT in ("disque", "couronne"):
            Rr = sec["D"] / 2 * 1e3
            mres = math.hypot(chk["Mfz"], chk["Mfy"]) * 1e3
            sh = abs(chk["N"]) / S + mres * Rr / Iz
            ftxt = (
                r"|\sigma|_{max}=\frac{|N|}{S}+\frac{\sqrt{M_{fz}^2+M_{fy}^2}\,R}{I}=\frac{%s}{%s}+\frac{%s\times%s}{%s}"
                % (
                    n(abs(chk["N"])),
                    n(S),
                    n(mres),
                    n(Rr),
                    n(Iz),
                )
            )
        else:
            vy, vz = saisie["vy"], saisie["vz"]
            sh = max(
                abs(chk["N"] / S - chk["Mfz"] * 1e3 * y / Iz + chk["Mfy"] * 1e3 * z / Iy)
                for y in (-vy, vy)
                for z in (-vz, vz)
            )
            ftxt = (
                r"|\sigma|_{max}=\max_{\pm v_y,\pm v_z}\left|\frac{%s}{%s}-\frac{%s\,y}{%s}+\frac{%s\,z}{%s}\right|"
                % (
                    n(chk["N"]),
                    n(S),
                    n(chk["Mfz"] * 1e3),
                    n(Iz),
                    n(chk["Mfy"] * 1e3),
                    n(Iy),
                )
            )
        rows += [
            _grp("Contrainte maximale au point le plus sollicité (N en N, M en N·mm)"),
            _hc("|σ| max (loi de Navier, sans le solveur)", ftxt, sh, bd["sigmaMaxAbs"] / 1e6, "MPa"),
            _hc(
                "Kt·|σ| max (concentration de contraintes)",
                r"K_t|\sigma|_{max}=%s\times%s" % (n(saisie["Kt"]), n(sh)),
                saisie["Kt"] * sh,
                bd["sigmaMaxKt"] / 1e6,
                "MPa",
            ),
        ]
    adm = saisie["Re"] / saisie["s"]
    rows.append(
        _hc(
            "σadm (limite élastique / coefficient de sécurité)",
            r"\sigma_{adm}=\frac{R_e}{s}=\frac{%s}{%s}" % (n(saisie["Re"]), n(saisie["s"])),
            adm,
            bd["sigmaAdm"] / 1e6,
            "MPa",
        )
    )
    okTxt = "vérifié" if bd["ok"] else "NON VÉRIFIÉ"
    rows.append(
        _grp(
            f"Verdict de résistance : Kt·|σ|max = {bd['sigmaMaxKt'] / 1e6:.6g} MPa "
            f"{'≤' if bd['ok'] else '>'} σadm = {bd['sigmaAdm'] / 1e6:.6g} MPa → {okTxt}"
        )
    )
    cmp = B["defl"]["comparison"]
    flexion = ~cmp["Methode"].astype(str).str.contains("tranchant")  # la ligne « flexion + tranchant » est à part
    ecart = float(np.max(np.abs(cmp["Ecart_pct"].to_numpy(dtype=float)[flexion.to_numpy()])))
    rows.append(
        _grp(
            f"Flèche maximale {B['defl']['integration']['fmax'] * 1e3:.5g} mm en s = "
            f"{B['defl']['integration']['sAtFmax']:.4g} m (E·I = E·Iz ou E·Iy selon le plan, double intégration de "
            f"M/(E·I)) ; écart maximal entre les 4 méthodes = {ecart:.3g} % "
            "(la ligne « flexion + tranchant » de Castigliano est à part ; voir §4)"
        )
    )
    return rows


def _handCombos(saisie: dict, res: dict, dm) -> list[dict]:
    """Combinaisons : équilibre et torseur de chaque combinaison, superposition des cas, tableau = recalcul.

    Ces contrôles font appel au solveur de poutre : ils vérifient la cohérence des combinaisons, pas le solveur.
    """
    T = _extras(res)["combos"]
    noms = ("G", "Q", "W", "S")
    used = [False] * 4
    for tb in (saisie["pl"], saisie["pm"], saisie["dl"]):
        for ligne in tb:
            if str(ligne.get("case")) in noms:
                used[noms.index(str(ligne["case"]))] = True
    if saisie["selfw"]:
        used[0] = True
    s = np.linspace(0, saisie["L"], 21)
    sols = {}
    for k in (i for i in range(4) if used[i]):
        fac = dict.fromkeys(noms, 0.0)
        fac[noms[k]] = 1.0
        sols[noms[k]] = solveBeam(buildBeamModel(saisie, dm, fac))
    rows = [
        _grp(
            "Combinaisons : chaque ligne est résolue séparément, puis comparée (équilibre, superposition des cas, "
            "tableau). Ces contrôles utilisent le solveur : ils vérifient la cohérence des combinaisons."
        )
    ]
    gov = {"Mfz": ("", -math.inf), "Ty": ("", -math.inf)}
    for i, ligne in enumerate(saisie["combo"]):
        g = [beam_services._num(ligne[c], "γ") for c in ("gG", "gQ", "gW", "gS")]
        sol = solveBeam(buildBeamModel(saisie, dm, dict(zip(noms, g, strict=True))))
        nm = str(ligne["name"])
        rows.append(_grp(f"Combinaison « {nm} » : γG = {g[0]:g}, γQ = {g[1]:g}, γW = {g[2]:g}, γS = {g[3]:g}"))
        rows += _beamPlaneRows(sol, "y")
        # superposition : Mfz(combinaison) = somme des γ·Mfz(cas), en 21 abscisses
        sup = np.zeros_like(s)
        for k in (i2 for i2 in range(4) if used[i2]):
            sup = sup + g[k] * ppEval(sols[noms[k]]["Mfz"], s)
        direct = ppEval(sol["Mfz"], s)
        rows.append(
            _hc(
                "Moment fléchissant : superposition des cas (somme sur 21 abscisses de |Mfz|)",
                r"\sum_s \left|\sum_c \gamma_c\,M_{fz,c}(s)\right|",
                float(np.sum(np.abs(sup))) / 1e3,
                float(np.sum(np.abs(direct))) / 1e3,
                "kN·m",
            )
        )
        e = sol["extrema"]
        rows.append(
            _hc(
                "Tableau Combinaisons : Mfz max = recalcul de la combinaison",
                "M_{fz,max}",
                e["Mfz"]["max"] / 1e3,
                T["Mfz max (kN·m)"].iloc[i],
                "kN·m",
            )
        )
        rows.append(
            _hc(
                "Tableau Combinaisons : Mfz min = recalcul de la combinaison",
                "M_{fz,min}",
                e["Mfz"]["min"] / 1e3,
                T["Mfz min (kN·m)"].iloc[i],
                "kN·m",
            )
        )
        rows.append(
            _hc(
                "Tableau Combinaisons : Ty max = recalcul de la combinaison",
                "T_{y,max}",
                e["Ty"]["max"] / 1e3,
                T["Ty max (kN)"].iloc[i],
                "kN",
            )
        )
        if e["Mfz"]["max"] > gov["Mfz"][1]:
            gov["Mfz"] = (nm, e["Mfz"]["max"])
        if e["Ty"]["max"] > gov["Ty"][1]:
            gov["Ty"] = (nm, e["Ty"]["max"])
    nT = len(T)
    rows.append(
        _hc(
            "Enveloppe : Mfz max = plus grand Mfz max des combinaisons",
            r"M_{fz,max}^{env}=\max_i M_{fz,max,i}",
            float(np.max(T["Mfz max (kN·m)"].to_numpy(dtype=float)[: nT - 1])),
            T["Mfz max (kN·m)"].iloc[nT - 1],
            "kN·m",
        )
    )
    rows.append(
        _grp(
            f"Combinaison dimensionnante : « {gov['Mfz'][0]} » pour Mfz max, « {gov['Ty'][0]} » pour Ty max. "
            "L'enveloppe associe des maxima qui ne sont pas simultanés : elle est prudente."
        )
    )
    return rows


def _classe(x: float, lims) -> int:
    """Première classe (1 à 3) dont la limite est respectée, sinon 4."""
    return next((i for i, lim in enumerate(lims, 1) if x <= lim), 4)


def _handEC3(saisie: dict, res: dict) -> list[dict]:  # noqa: C901
    """Eurocode 3 : recalcul avec d'autres écritures (Wpl = 2·Sy, formules explicites) sans appeler design_checks."""
    n = _num
    B = saisie
    r = _extras(res)["ec3"][0]
    sec = B["section"]
    rolled = sec["type"] == "profile"
    if rolled:
        h, b, tw, tf = sec["h"], sec["b"], sec["a"], sec["e"]
        rr = sec["r"] if math.isfinite(sec.get("r", math.nan)) else 0.0
    else:
        h, b, tw, tf, rr = sec["h"], sec["b"], sec["tw"], sec["tf"], 0.0
    fy, g0, g1 = B["Re"] * 1e6, B["gM0"], B["gM1"]
    E, G = B["E"] * 1e9, B["G"] * 1e9
    A, Iy, Iw_, It = B["S"] * 1e-6, B["Iz"] * 1e-12, B["Iy"] * 1e-12, B["Ix"] * 1e-12
    Lcr = B["Lcr"] if B["Lcr"] > 0 else B["L"]
    LcrF = B["LcrF"] if B["LcrF"] > 0 else B["L"]
    C1 = B["C1"]
    MEd, VEd = r["MEd"], r["VEd"]
    Npl = A * fy / g0
    NEd = r["axial"]["n"] * Npl
    rows = [
        _grp(
            "Eurocode 3 : classes, résistances, déversement, N + M (EN 1993-1-1) ; efforts de calcul pris dans les "
            "résultats de la poutre"
        )
    ]
    # classes (tableau 5.2)
    eps = math.sqrt(235e6 / fy)
    hw = h - 2 * tf
    cf = (b - tw - 2 * rr) / 2
    cw = hw - 2 * rr
    # âme (tableau 5.2, feuille 2) : ψ et α aux bords de l'âme, compression seule (r.Ncomp) avec la flexion MEd
    sCw = r["Ncomp"] / A
    sMw = abs(MEd) * (hw / 2) / Iy
    psiW = -1.0
    if sCw + sMw > 0:
        psiW = (sCw - sMw) / (sCw + sMw)
    alW = min(1.0, 1 / (1 - psiW))
    if alW > 0.5:
        limW = [396 / (13 * alW - 1), 456 / (13 * alW - 1)]
    else:
        limW = [36 / alW, 41.5 / alW]
    limW.append(42 / (0.67 + 0.33 * psiW) if psiW > -1 else 62 * (1 - psiW) * math.sqrt(-psiW))
    kf = _classe(cf / tf, [9 * eps, 10 * eps, 14 * eps])
    kw = _classe(cw / tw, [x * eps for x in limW])
    cls = max(kf, kw)
    c = r["class"]
    rows += [
        _hc("ε = √(235/fy)", r"\varepsilon=\sqrt{235/%s}" % n(fy / 1e6), eps, c["eps"]),
        _hc(
            "Aile : c/tf",
            r"c/t_f=\frac{(b-t_w-2r)/2}{t_f}=\frac{%s}{%s}" % (n(cf * 1e3), n(tf * 1e3)),
            cf / tf,
            c["ratioFlange"],
        ),
        _hc(
            "Âme : c/tw",
            r"c/t_w=\frac{h-2t_f-2r}{t_w}=\frac{%s}{%s}" % (n(cw * 1e3), n(tw * 1e3)),
            cw / tw,
            c["ratioWeb"],
        ),
        _hc(
            "Classe de la section (tableau 5.2 : aile 9ε, 10ε, 14ε ; âme selon ψ et α)",
            r"\text{classe}=\max(%d,%d)" % (kf, kw),
            cls,
            c["class"],
            "",
            0.0,
        ),
    ]
    if cls > 3:
        return rows
    # flexion et tranchant (6.2.5, 6.2.6, 6.2.8)
    hfil = (1 - math.pi / 4) * rr**2
    Sy = b * tf * (h - tf) / 2 + tw * (hw / 2) * (hw / 4) + 2 * hfil * (hw / 2 - 0.2234 * rr)
    Wpl = 2 * Sy
    Wel = Iy / (h / 2)
    W = Wel if cls == 3 else Wpl
    Mc = W * fy / g0
    eta = 1.0 if fy > 460e6 else 1.2
    Av = max(A - 2 * b * tf + (tw + 2 * rr) * tf, eta * hw * tw)
    Vpl = Av * (fy / math.sqrt(3)) / g0
    red = abs(VEd) > 0.5 * Vpl
    MRd = Mc
    if red:
        rho = (2 * abs(VEd) / Vpl - 1) ** 2
        MRd = max(0.0, min(Mc, (W - rho * (hw * tw) ** 2 / (4 * tw)) * fy / g0))
    rows += [
        _hc(
            "Wpl = 2·Sy (moment statique d'une demi-section)",
            r"W_{pl}=2\left[b t_f\frac{h-t_f}{2}+t_w\frac{h_w}{2}\frac{h_w}{4}+2A_f(\tfrac{h_w}{2}-0{,}2234r)\right]=%s"
            % n(Wpl * 1e6),
            Wpl * 1e6,
            r["Wpl"] * 1e6,
            "cm³",
        ),
        _hc(
            "Wel = Iy/(h/2)",
            r"W_{el}=\frac{I_y}{h/2}=\frac{%s}{%s}" % (n(Iy * 1e8), n(h * 50)),
            Wel * 1e6,
            r["Wel"] * 1e6,
            "cm³",
        ),
        _hc(
            "Mc,Rd = W·fy/γM0 (§6.2.5, éq. 6.13/6.14)",
            r"M_{c,Rd}=\frac{%s\times%s}{%s}" % (n(W * 1e6), n(fy / 1e6), n(g0)),
            Mc / 1e3,
            r["Mc"] / 1e3,
            "kN·m",
        ),
        _hc(
            "Av (§6.2.6(3))",
            r"A_v=\max(A-2bt_f+(t_w+2r)t_f,\ \eta h_w t_w)=%s" % n(Av * 1e6),
            Av * 1e6,
            r["Av"] * 1e6,
            "mm²",
        ),
        _hc(
            "Vpl,Rd = Av·(fy/√3)/γM0 (§6.2.6(2))",
            r"V_{pl,Rd}=\frac{%s\,(%s/\sqrt3)}{%s}" % (n(Av * 1e6), n(fy / 1e6), n(g0)),
            Vpl / 1e3,
            r["Vpl"] / 1e3,
            "kN",
        ),
        _hc(
            "MRd après réduction par le tranchant (§6.2.8)",
            r"V_{Ed}=%s\ \text{kN}\ \ \text{; réduction : }%d" % (n(VEd / 1e3), int(red)),
            MRd / 1e3,
            r["MRd"] / 1e3,
            "kN·m",
        ),
        _hc("MEd / MRd (éq. 6.12)", r"\frac{%s}{%s}" % (n(MEd / 1e3), n(MRd / 1e3)), MEd / MRd, r["ratioM"]),
        _hc("VEd / Vpl,Rd (éq. 6.17)", r"\frac{%s}{%s}" % (n(VEd / 1e3), n(Vpl / 1e3)), VEd / Vpl, r["ratioV"]),
    ]
    # déversement (6.3.2.3 ; Mcr : NCCI SN003)
    Iw = Iw_ * (h - tf) ** 2 / 4
    Mcr = C1 * math.pi**2 * E * Iw_ / Lcr**2 * math.sqrt(Iw / Iw_ + Lcr**2 * G * It / (math.pi**2 * E * Iw_))
    lam = math.sqrt(W * fy / Mcr)
    tall = h / b > 2 + 1e-9
    cv = "bc" if rolled else "cd"
    alt = [0.21, 0.34, 0.49, 0.76]
    curve = cv[int(tall)]
    al = alt[ord(curve) - ord("a")]
    Phi = 0.5 * (1 + al * (lam - 0.4) + 0.75 * lam**2)
    chi = min(1.0, 1 / lam**2, 1 / (Phi + math.sqrt(max(Phi**2 - 0.75 * lam**2, 0))))
    if lam <= 0.4:
        chi = 1.0
    Mb = chi * W * fy / g1
    lt = r["ltb"]
    rows += [
        _hc(
            "Mcr (poutre à fourches, charge au centre de torsion)",
            r"M_{cr}=C_1\frac{\pi^2EI_z}{L_{cr}^2}\sqrt{\frac{I_w}{I_z}+\frac{L_{cr}^2GI_t}{\pi^2EI_z}}"
            r"\ ;\ C_1=%s,\ L_{cr}=%s\ \text{m}" % (n(C1), n(Lcr)),
            Mcr / 1e3,
            lt["Mcr"] / 1e3,
            "kN·m",
        ),
        _hc(
            "λ̄LT = √(W·fy/Mcr)",
            r"\bar\lambda_{LT}=\sqrt{\frac{%s\times%s}{%s}}" % (n(W * 1e6), n(fy / 1e6), n(Mcr / 1e3)),
            lam,
            lt["lambda"],
        ),
        _hc(f"αLT (courbe {curve}, tableaux 6.5 puis 6.3)", r"\alpha_{LT}=%s" % n(al), al, lt["alpha"]),
        _hc(
            "χLT (éq. 6.57, λ̄LT,0 = 0,4, β = 0,75)",
            r"\chi_{LT}=\frac{1}{\Phi_{LT}+\sqrt{\Phi_{LT}^2-0{,}75\bar\lambda_{LT}^2}},\ \Phi_{LT}=%s" % n(Phi),
            chi,
            lt["chi"],
        ),
        _hc(
            "Mb,Rd = χLT·W·fy/γM1 (éq. 6.55)",
            r"M_{b,Rd}=%s\times%s\times%s/%s" % (n(chi), n(W * 1e6), n(fy / 1e6), n(g1)),
            Mb / 1e3,
            lt["MbRd"] / 1e3,
            "kN·m",
        ),
        _hc("MEd / Mb,Rd (éq. 6.54)", r"\frac{%s}{%s}" % (n(MEd / 1e3), n(Mb / 1e3)), MEd / Mb, lt["ratio"]),
    ]
    # flexion + effort normal (6.2.9)
    n_ = NEd / Npl
    ax = r["axial"]
    if cls <= 2:
        a_ = min((A - 2 * b * tf) / A, 0.5)
        free = n_ <= 0.25 and NEd <= 0.5 * hw * tw * fy / g0
        if free:
            MN = Mc
        elif n_ >= 1:
            MN = 0.0
        else:
            MN = min(Mc, Mc * (1 - n_) / (1 - 0.5 * a_))
        MN = min(MN, MRd)
        rows += [
            _hc("n = NEd/Npl,Rd", r"n=\frac{%s}{%s}" % (n(NEd / 1e3), n(Npl / 1e3)), n_, ax["n"]),
            _hc(
                "MN,y,Rd (§6.2.9.1, éq. 6.36 ; sans réduction si 6.33 et 6.34)",
                r"M_{N,y,Rd}=M_{pl,y,Rd}\frac{1-n}{1-0{,}5a},\ a=%s" % n(a_),
                MN / 1e3,
                ax["MNRd"] / 1e3,
                "kN·m",
            ),
        ]
    else:
        sig = NEd / A + MEd / Wel
        rows.append(
            _hc(
                "σx,Ed = NEd/A + MEd/Wel (§6.2.9.2, éq. 6.42)",
                r"\sigma_{x,Ed}=\frac{%s}{%s}+\frac{%s}{%s}" % (n(NEd / 1e3), n(A * 1e6), n(MEd / 1e3), n(Wel * 1e6)),
                sig / 1e6,
                ax["sigma"] / 1e6,
                "MPa",
            )
        )
    # flambement par flexion (6.3.1), axe faible z-z
    if r["buck"] is not None:
        bk = r["buck"]
        Nc = bk["NEd"]
        hb = h / b
        if rolled:
            if hb > 1.2:
                cz = "d" if tf * 1e3 > 100 else ("c" if tf * 1e3 > 40 else "b")
            else:
                cz = "d" if tf * 1e3 > 100 else "c"
        else:
            cz = "d" if tf * 1e3 > 40 else "c"
        alz = alt[ord(cz) - ord("a")]
        Ncr = math.pi**2 * E * Iw_ / Lcr**2
        lz = math.sqrt(A * fy / Ncr)
        Pz = 0.5 * (1 + alz * (lz - 0.2) + lz**2)
        chz = min(1.0, 1 / (Pz + math.sqrt(max(Pz**2 - lz**2, 0))))
        if lz <= 0.2 or Nc / Ncr <= 0.04:
            chz = 1.0
        az = bk["axes"][1]
        rows += [
            _hc(
                "Flambement z-z : Ncr = π²·E·Iz/Lcr²",
                r"N_{cr}=\frac{\pi^2EI_z}{L_{cr}^2}=%s\ \text{kN}" % n(Ncr / 1e3),
                Ncr / 1e3,
                az["Ncr"] / 1e3,
                "kN",
            ),
            _hc(
                f"Flambement z-z : λ̄ (courbe {cz}, tableaux 6.2 et 6.1)",
                r"\bar\lambda=\sqrt{\frac{Af_y}{N_{cr}}}=%s" % n(lz),
                lz,
                az["lambda"],
            ),
            _hc(
                "Flambement z-z : χ (éq. 6.49)",
                r"\chi=\frac{1}{\Phi+\sqrt{\Phi^2-\bar\lambda^2}},\ \Phi=%s" % n(Pz),
                chz,
                az["chi"],
            ),
            _hc(
                "Flambement z-z : Nb,Rd = χ·A·fy/γM1 (éq. 6.47)",
                r"N_{b,Rd}=%s\times%s\times%s/%s" % (n(chz), n(A * 1e6), n(fy / 1e6), n(g1)),
                chz * A * fy / g1 / 1e3,
                az["NbRd"] / 1e3,
                "kN",
            ),
        ]
        # interaction N + M (6.3.3, annexe B, tableau B.2) : refait avec le χ de l'axe fort recalculé ici
        if r["inter"] is not None:
            it = r["inter"]
            if rolled:
                if hb > 1.2:
                    cy = "d" if tf * 1e3 > 100 else ("b" if tf * 1e3 > 40 else "a")
                else:
                    cy = "d" if tf * 1e3 > 100 else "b"
            else:
                cy = "c" if tf * 1e3 > 40 else "b"
            aly = [0.21, 0.34, 0.49, 0.76][ord(cy) - ord("a")]
            Ncry = math.pi**2 * E * Iy / LcrF**2  # axe fort : longueur du plan fort, pas la longueur entre entretoises
            ly = math.sqrt(A * fy / Ncry)
            Py = 0.5 * (1 + aly * (ly - 0.2) + ly**2)
            chy = min(1.0, 1 / (Py + math.sqrt(max(Py**2 - ly**2, 0))))
            if ly <= 0.2 or Nc / Ncry <= 0.04:
                chy = 1.0
            nY_ = Nc / (chy * A * fy / g1)
            nZ_ = Nc / (chz * A * fy / g1)
            Cmy, CmL = B["Cmy"], B["CmLT"]
            if cls <= 2:
                kyy = min(Cmy * (1 + (ly - 0.2) * nY_), Cmy * (1 + 0.8 * nY_))
                if lz >= 0.4:
                    kzy = max(1 - 0.1 * lz * nZ_ / (CmL - 0.25), 1 - 0.1 * nZ_ / (CmL - 0.25))
                else:
                    kzy = min(0.6 + lz, 1 - 0.1 * lz * nZ_ / (CmL - 0.25))
            else:
                kyy = min(Cmy * (1 + 0.6 * ly * nY_), Cmy * (1 + 0.6 * nY_))
                kzy = max(1 - 0.05 * lz * nZ_ / (CmL - 0.25), 1 - 0.05 * nZ_ / (CmL - 0.25))
            dn = chi * W * fy / g1
            rows += [
                _hc(
                    f"Flambement y-y : χy (courbe {cy})",
                    r"\chi_y=\frac{1}{\Phi+\sqrt{\Phi^2-\bar\lambda_y^2}},\ \bar\lambda_y=%s" % n(ly),
                    chy,
                    bk["axes"][0]["chi"],
                ),
                _hc(
                    "kyy (annexe B, tableau B.2)",
                    r"k_{yy}=C_{my}\left[1+(\bar\lambda_y-0{,}2)n_Y\right]\le C_{my}(1+0{,}8\,n_Y)\ ;\ n_Y=%s" % n(nY_),
                    kyy,
                    it["kyy"],
                ),
                _hc(
                    "kzy (annexe B, tableau B.2)",
                    r"k_{zy}=1-\frac{0{,}1\bar\lambda_z n_Z}{C_{mLT}-0{,}25}\ ;\ n_Z=%s" % n(nZ_),
                    kzy,
                    it["kzy"],
                ),
                _hc(
                    "Éq. 6.61 : N/(χy·NRk/γM1) + kyy·M/(χLT·My,Rk/γM1)",
                    r"%s+%s\frac{%s}{%s}" % (n(nY_), n(kyy), n(MEd / 1e3), n(dn / 1e3)),
                    nY_ + kyy * MEd / dn,
                    it["ratio61"],
                ),
                _hc(
                    "Éq. 6.62 : N/(χz·NRk/γM1) + kzy·M/(χLT·My,Rk/γM1)",
                    r"%s+%s\frac{%s}{%s}" % (n(nZ_), n(kzy), n(MEd / 1e3), n(dn / 1e3)),
                    nZ_ + kzy * MEd / dn,
                    it["ratio62"],
                ),
            ]
    # voilement de l'âme par cisaillement (EN 1993-1-5 §5, âme non raidie)
    et = 1.0 if fy > 460e6 else 1.2
    w = r["web"]
    if hw / tw > 72 * eps / et:
        lw = hw / (86.4 * tw * eps)
        if lw < 0.83 / et:
            chw = et
        elif lw < 1.08:
            chw = 0.83 / lw
        else:
            chw = 1.37 / (0.7 + lw)
        Vb = chw * fy * hw * tw / (math.sqrt(3) * g1)
        rows += [
            _hc(
                "Voilement de l'âme : χw (tableau 5.1, poteau d'extrémité rigide)",
                r"\bar\lambda_w=\frac{h_w}{86{,}4\,t_w\varepsilon}=%s" % n(lw),
                chw,
                w["chi"],
            ),
            _hc(
                "Vb,Rd = χw·fy·hw·tw/(√3·γM1)",
                r"V_{b,Rd}=\frac{%s\times%s\times%s}{\sqrt3\times%s}" % (n(chw), n(fy / 1e6), n(hw * tw * 1e6), n(g1)),
                Vb / 1e3,
                w["VbRd"] / 1e3,
                "kN",
            ),
        ]
    else:
        rows.append(
            _grp(
                f"Voilement de l'âme par cisaillement : hw/tw = {hw / tw:.1f} ≤ 72ε/η = {72 * eps / et:.1f}, "
                "sans objet."
            )
        )
    rows.append(
        _grp(
            "Non recalculé : voilement local sous charges concentrées, flexion déviée, ELS, classe 4 ; annexe "
            "nationale : seules γM0 et γM1 sont paramétrables. Le recalcul reprend les mêmes formules écrites "
            "autrement (Wpl par le moment statique d'une demi-section) : il détecte les erreurs de programmation, "
            "pas un choix de formule discutable."
        )
    )
    return rows


def _handFatigue(saisie: dict, res: dict, dm) -> list[dict]:
    """Fatigue : Goodman recalculé à partir des champs de saisie et de la contrainte de la poutre."""
    n = _num
    B = saisie
    f = _extras(res)["fatigue"][0]
    bd = res["check"]["bend"]
    Kt, R = B["Kt"], B["fR"]
    Rm = dm.getMaterial(B["mat"])["Rm"]
    smax = bd["sigmaMaxAbs"]
    Se = B["fka"] * B["fkb"] * min(0.5 * Rm, 700e6)
    sa = Kt * smax * (1 - R) / 2
    sm = smax * (1 + R) / 2
    nn = 1 / (sa / Se + max(sm, 0) / Rm)
    return [
        _grp("Fatigue (Goodman modifié, Shigley chap. 6) : recalcul à partir des champs de saisie"),
        _hc(
            "σmax nominale = Kt·σmax / Kt (la contrainte nominale n'est pas reconstruite à tort)",
            r"\sigma_{max}=\frac{K_t\sigma_{max}}{K_t}=\frac{%s}{%s}" % (n(bd["sigmaMaxKt"] / 1e6), n(Kt)),
            bd["sigmaMaxKt"] / Kt / 1e6,
            smax / 1e6,
            "MPa",
        ),
        _hc(
            "Se = ka·kb·min(0,5·Rm ; 700 MPa)",
            r"S_e=%s\times%s\times\min(0{,}5\times%s,\,700)" % (n(B["fka"]), n(B["fkb"]), n(Rm / 1e6)),
            Se / 1e6,
            f["Se"] / 1e6,
            "MPa",
        ),
        _hc(
            "σa = Kf·σmax·(1−R)/2",
            r"\sigma_a=%s\times%s\times\frac{1-(%s)}{2}" % (n(Kt), n(smax / 1e6), n(R)),
            sa / 1e6,
            f["sigmaA"] / 1e6,
            "MPa",
        ),
        _hc(
            "σm = σmax·(1+R)/2",
            r"\sigma_m=%s\times\frac{1+(%s)}{2}" % (n(smax / 1e6), n(R)),
            sm / 1e6,
            f["sigmaM"] / 1e6,
            "MPa",
        ),
        _hc(
            "n = 1/(σa/Se + σm/Rm)",
            r"n=\frac{1}{%s/%s+%s/%s}" % (n(sa / 1e6), n(Se / 1e6), n(max(sm, 0) / 1e6), n(Rm / 1e6)),
            nn,
            f["n"],
        ),
        _grp(
            "Hypothèses non recalculables : acier, vie infinie, Kf = Kt (sensibilité à l'entaille q = 1), chargement "
            "uniaxial d'amplitude constante. Autre vérification de fatigue des constructions métalliques : "
            "EN 1993-1-9, non traitée."
        ),
    ]


def _handProfiles(saisie: dict, res: dict, dm) -> list[dict]:
    """Profilé le plus léger : cohérence du tableau (tri, σadm, masse, L/f, choix du premier qui vérifie)."""
    n = _num
    B = saisie
    T = _extras(res)["profiles"][0]
    L = B["L"]
    rho = dm.getMaterial(B["mat"])["rho"]
    S = T["S (mm²)"].to_numpy(dtype=float)
    inv = int(np.sum(np.diff(S[~np.isnan(S)]) < 0))
    sadm = T["σadm (MPa)"].to_numpy(dtype=float)
    sadm = sadm[~np.isnan(sadm)]
    r = T["Résistance"].astype(str)
    ok = (~r.str.contains("NON") & ~r.str.contains("erreur")).to_numpy()
    rows = [
        _grp(f"Profilé le plus léger, famille {B['pfam']} : {len(T)} profilés essayés avec le chargement de l'onglet"),
        _hc("Tri par aire croissante : nombre d'inversions", r"\#\{i:\ S_{i+1}<S_i\}", inv, 0, "", 0.0),
        _hc(
            "σadm = Re/s (tous les profilés)",
            r"\sigma_{adm}=\frac{%s}{%s}" % (n(B["Re"]), n(B["s"])),
            B["Re"] / B["s"],
            sadm[0],
            "MPa",
        ),
    ]
    if not ok.any():
        rows.append(_grp("Aucun profilé de cette famille ne vérifie le chargement : pas de profilé retenu."))
        return rows
    i1 = int(np.argmax(ok))
    m_ = T["Masse (kg/m)"].iloc[i1]
    Sb = S[i1]
    f1 = T["f max (mm)"].iloc[i1]
    rows += [
        _hc(
            f"Masse linéique du profilé retenu ({T['Profilé'].iloc[i1]}) = ρ·S",
            r"m=\rho S=%s\times%s\times10^{-6}" % (n(rho), n(Sb)),
            rho * Sb * 1e-6,
            m_,
            "kg/m",
        ),
        _hc(
            "Le profilé retenu est le plus léger qui vérifie",
            r"\min\{S_i:\ \text{vérifié}\}",
            float(np.min(S[ok])),
            Sb,
            "mm²",
        ),
        _hc(
            "L/f du profilé retenu = L / f max",
            r"\frac{L}{f}=\frac{%s}{%s}" % (n(L * 1e3), n(f1)),
            L * 1e3 / f1,
            T["L/f (-)"].iloc[i1],
        ),
    ]
    if B["pdef"] > 0:
        rows.append(
            _hc(
                f"Critère de flèche L/{B['pdef']:g} respecté par le profilé retenu (0 = oui)",
                r"\frac{L}{f}\ge %s" % n(B["pdef"]),
                float(T["L/f (-)"].iloc[i1] < B["pdef"]),
                0.0,
                "",
                0.0,
            )
        )
    rows.append(
        _grp(
            "Non recalculé ici : la contrainte de chaque profilé (poids propre et moments dépendent du profilé). "
            "Pour la contrôler, importer le profilé retenu dans l'onglet Poutres et consulter son dossier de "
            "validation."
        )
    )
    return rows


def _safeRows(fn, nom: str) -> list[dict]:
    try:
        return fn()
    except Exception as err:  # un contrôle impossible est un contrôle raté : NaN ne concorde jamais (voir _verdict)
        return [_hc(f"{nom} : contrôle impossible ({getattr(err, 'message', err)})", "", _NAN, _NAN)]


def _handExtras(saisie: dict, res: dict, dm) -> list[dict]:
    """Contrôles des résultats ajoutés à l'onglet Poutres (présents seulement s'ils ont été calculés)."""
    ex = _extras(res)
    rows: list[dict] = []
    if ex.get("combos") is not None:
        rows += _safeRows(lambda: _handCombos(saisie, res, dm), "Combinaisons")
    if ex.get("ec3") is not None:
        rows += _safeRows(lambda: _handEC3(saisie, res), "Eurocode 3")
    if ex.get("fatigue") is not None:
        rows += _safeRows(lambda: _handFatigue(saisie, res, dm), "Fatigue")
    if ex.get("profiles") is not None:
        rows += _safeRows(lambda: _handProfiles(saisie, res, dm), "Profilé le plus léger")
    return rows


def _handRows(key: str, saisie: dict, res: dict, dm, withExtras: bool = True) -> list[dict]:
    """Lignes de contrôle à la main de l'onglet (formules du cours, sans appeler les moteurs de calcul)."""
    f = {
        "Sec": _handSec,
        "Beam": _handBeam,
        "Tr": _handTruss,
        "Tra": _handTra,
        "Cis": _handCis,
        "Tor": _handTor,
        "Fle": _handFle,
        "Fla": _handFla,
        "Ten": _handTen,
        "Hoo": _handHoo,
        "Jau": _handJau,
    }[key]
    rows = f(saisie, res)
    if key == "Beam" and withExtras:
        rows = rows + _handExtras(saisie, res, dm)
    return rows


def _verdict(r: dict) -> tuple[float, bool]:
    """(écart absolu, concordance) d'une ligne : tolérance par défaut 1e-6 relatif + 1e-12 (handHTML de MATLAB)."""
    d = abs(r["hand"] - r["solver"])
    tol = r["tol"]
    if math.isnan(tol):
        tol = _TOL_REL * max(abs(r["solver"]), abs(r["hand"])) + _TOL_ABS
    return d, bool(d <= tol)


def _latexBlocks(key: str, res: dict) -> list[tuple[str, list[str]]]:
    """Équations avec valeurs « telles qu'écrites par le solveur » (champ latex des résultats)."""
    chemins = {
        "Sec": ["result.P", "result.bend", "result.jour"],
        "Beam": ["sol", "defl"],
        "Tr": ["result.tsol"],
        "Tra": ["result"],
        "Cis": ["result.shear", "result.jour", "result.bearing", "extras.key", "extras.pin"],
        "Tor": ["result"],
        "Fle": ["result.bend"],
        "Fla": ["result.analysis"],
        "Ten": ["result.principal", "result.facet", "result.plane2D", "result.criteria"],
        "Hoo": ["result.mohr"],
        "Jau": ["result.gauge", "result.bridge", "result.rosette"],
    }
    noms = {
        "P": "Section : analytique",
        "bend": "Flexion",
        "jour": "Cisaillement (Jourawski)",
        "sol": "Poutre : statique",
        "defl": "Poutre : déformée",
        "tsol": "Treillis",
        "shear": "Cisaillement",
        "bearing": "Matage",
        "key": "Clavette",
        "pin": "Goupille",
        "analysis": "Flambage",
        "principal": "Contraintes principales",
        "facet": "Facette",
        "plane2D": "Mohr plan",
        "criteria": "Critères",
        "mohr": "Cercle de Mohr",
        "gauge": "Jauge",
        "bridge": "Pont",
        "rosette": "Rosette",
        "result": {"Tra": "Traction", "Tor": "Torsion"}.get(key, "Résultat"),
    }
    out = []
    for c in chemins[key]:
        s = _chemin(res, c)
        lat = s.get("latex") if isinstance(s, dict) else None
        if lat is None or len(lat) == 0:
            continue
        lat = [lat] if isinstance(lat, str) else list(lat)
        out.append((noms[c.split(".")[-1]], lat))
    return out


def _handHTML(key: str, saisie: dict, res: dict, dm, withExtras: bool = True) -> tuple[str, int, int]:
    """Partie 3 : tableau des contrôles à la main, puis équations du solveur ; renvoie (html, nOK, nTot)."""
    rows = _handRows(key, saisie, res, dm, withExtras)
    h = (
        "<p>Pour chaque grandeur, la formule est écrite avec les valeurs de ce problème, calculée à la main "
        "(sans appeler le solveur) puis comparée à la valeur du solveur.</p>"
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
    h += "</table>"
    blocs = _latexBlocks(key, res)
    if blocs:
        h += "<h3>Équations avec valeurs, telles qu'écrites par le solveur</h3>"
        for titre, lat in blocs:
            h += f'<div class="eqblock"><div class="eqtitle">{_esc(titre)}</div>'
            h += "".join(f'<div class="eq">{_esc(x)}</div>' for x in lat) + "</div>"
    return h, nOK, nTot


def handCheck(key: str, saisie: dict, res: dict, dm, withExtras: bool = True) -> tuple[int, int]:
    """Compte les contrôles à la main du §3 qui concordent, sans écrire de dossier.

    Entrées : `key` (KEYS) ; `saisie` de la page ; `res` (résultat de la page, avec `extras` éventuel) ; `dm` (base) ;
    `withExtras` : inclure combinaisons, Eurocode 3, fatigue et profilé de la poutre s'ils sont dans res["extras"].
    Sortie : (nOK, nTot).
    """
    _, nOK, nTot = _handHTML(key, saisie, res, dm, withExtras)
    return nOK, nTot


# ---------------------------------------------------------------------------------------- 4. Résultats


def _resultsHTML(key: str, res: dict) -> str:
    tables = list(res.get("tables", {}).items())
    ex = _extras(res)
    if key == "Beam":
        if ex.get("combos") is not None:
            tables.append(("Combinaisons", ex["combos"]))
        if ex.get("profiles") is not None:
            tables.append(("Profilé le plus léger", ex["profiles"][0]))
        if ex.get("ec3") is not None:
            tables.append(("Eurocode 3", ex["ec3"][1]))
        if ex.get("fatigue") is not None:
            tables.append(("Fatigue", ex["fatigue"][1]))
    if key == "Cis":
        tables = [("Cisaillement et matage", res["tables"]["Synthèse"])]
        for cle, titre in (("key", "Clavette"), ("pin", "Goupille")):
            if ex.get(cle) is not None:
                tables.append((titre, ex[cle]["tables"]["Synthèse"]))
    h = "".join(f"<h3>{_esc(t)}</h3>{_tableHTML(df)}" for t, df in tables)
    return h or "<p>Aucun tableau.</p>"


# ---------------------------------------------------------------------------------------- 5. Diagrammes


def _figures(key: str, saisie: dict, res: dict) -> list[tuple[str, object]]:
    """Figures Plotly de l'onglet (les mêmes que la page), sous forme (titre, figure)."""
    from mecastruct.plots import beam_plots, other_plots, section_plots, sollicitation_plots

    R = None if key == "Beam" else res["result"]
    f: list[tuple[str, object]] = []
    if key == "Sec":
        f = [
            ("Section", section_plots.section(R["sec"], R["P"])),
            ("Contraintes σ(y) et τ(y)", section_plots.sectionStress(R["sec"], R["P"], R["bend"], R["jour"])),
        ]
    elif key == "Beam":
        sol = res["sol"]
        comps = [c for c in ("N", "Ty", "Tz", "Mt", "Mfy", "Mfz") if any(np.any(k != 0) for k in asPP(sol[c]).coefs)]
        f = [
            ("Schéma", beam_plots.beamSchematic(res["model"], sol)),
            ("Diagrammes", beam_plots.internalForces(sol, comps or ["Ty", "Mfz"])),
            ("Déformée α(s), v(s)", beam_plots.deflection(res["model"], res["defl"])),
        ]
        if _extras(res).get("combos") is not None:
            f.append(("Combinaisons", beam_plots.combinations(_extras(res)["combos"])))
    elif key == "Tr":
        f = [("Treillis déformé", other_plots.truss(R["truss"], R["tsol"], saisie["scale"] or None))]
    elif key == "Tra":
        f = [
            (
                "Contrainte σ(x)",
                sollicitation_plots.tractionStress(R["x"], saisie["N"] * 1e3, R["Sx"], saisie["Kt"], R["sigmaAdm"]),
            ),
            ("Allongements", sollicitation_plots.elongations(R["dL"])),
        ]
    elif key == "Cis":
        sec = saisie["section"]
        P = geometry.analytical(sec)
        shear, jour, bearing = R["shear"], R["jour"], R["bearing"]
        taux = [
            abs(shear["tauMax"]) / shear["tauAdm"],
            abs(jour["tauMax"]) / shear["tauAdm"],
            abs(bearing["P"]) / (saisie["Padm"] * 1e6),
        ]
        f = [
            ("Section", section_plots.section(sec, P)),
            ("Contraintes de cisaillement", section_plots.sectionStress(sec, P, None, jour)),
            (
                "Taux d'utilisation",
                sollicitation_plots.ratios(
                    ["τmax/τadm", "τJourawski/τadm", "P/Padm"], taux, "Taux d'utilisation (cisaillement et matage)"
                ),
            ),
        ]
    elif key == "Tor":
        f = [
            ("Contrainte de torsion", sollicitation_plots.torsionStress(R, saisie["D"] * 1e-3)),
            ("Angle de torsion", sollicitation_plots.torsionAngle(saisie["L"], R["theta"], R["phi"]["analytique"])),
        ]
    elif key == "Fle":
        f = [
            (
                "Section et axe neutre",
                sollicitation_plots.bendingMarks(section_plots.section(R["sec"], R["P"]), R["P"], R["bend"]),
            ),
            ("Contraintes σ", section_plots.sectionStress(R["sec"], R["P"], R["bend"], None)),
        ]
    elif key == "Fla":
        f = [
            ("Courbe de stabilité", other_plots.bucklingCurve(R["curve"], R["analysis"])),
            ("Mode propre", other_plots.bucklingMode(R["analysis"])),
        ]
    elif key == "Ten":
        fa = R["facet"]
        sig = np.array(saisie["sig"], dtype=float)
        if np.all(np.abs(sig[2, :]) <= 1e-12 * max(1.0, np.max(np.abs(sig)))):
            pt = [R["plane2D"]["sigma1"], R["plane2D"]["sigma2"]]
        else:
            pr = R["principal"]
            pt = [pr["sigmaI"] - pr["sigmaII"], pr["sigmaIII"] - pr["sigmaII"]]
        f = [
            ("Tricercle de Mohr", other_plots.mohr3D(R["mohr3D"], [fa["sigmaN"], fa["tauNorm"]])),
            ("Mohr 2D (plan x, y)", other_plots.mohr2D(R["plane2D"], R["plane2D"]["theta"])),
            ("Lieu de plasticité", other_plots.yieldLocus(R["loci"], pt)),
        ]
    elif key == "Hoo":
        f = [("Cercle de Mohr des déformations", other_plots.mohr2D(R["mohr"]))]
    elif key == "Jau":
        f = [
            ("Cercle de Mohr des déformations", other_plots.mohr2D(R["mohrDeformations"])),
            ("Cercle de Mohr des contraintes", other_plots.mohr2D(R["mohrContraintes"])),
        ]
    return f


def _plotsHTML(key: str, saisie: dict, res: dict) -> str:
    h = ""
    premiere = True
    for titre, fig in _figures(key, saisie, res):
        fig.update_layout(template="plotly_white")  # fond clair, comme le thème clair forcé de MATLAB
        h += f'<h3>{_esc(titre)}</h3><div class="fig">'
        h += fig.to_html(full_html=False, include_plotlyjs="cdn" if premiere else False) + "</div>"
        premiere = False
    return h or "<p>Aucun diagramme disponible.</p>"


# ------------------------------------------------------------------- 6. Rapport, 7. Formules, 8. Avis


def _rapportLignes(key: str, res: dict) -> list[str]:
    if key == "Beam":
        return list(res["rapport"])
    if key == "Cis":
        lignes = list(res["result"]["rapport"])
        for cle in ("key", "pin"):
            if _extras(res).get(cle) is not None:
                lignes += _extras(res)[cle]["result"]["rapport"]
        return lignes
    return list(res["result"]["rapport"])


def _reportHTML(lines: list[str]) -> str:
    h = '<details open><summary>Afficher / masquer</summary><div class="rep">'
    for s in lines:
        s = str(s)
        if s.strip().startswith("==="):
            h += f'<div class="rsec">{_esc(s.strip().strip("=").strip())}</div>'
        else:
            h += f'<div class="rln">{_esc(s)}</div>'
    return h + "</div></details>"


def _formulasHTML(m: dict) -> str:
    h = ""
    vus: set[str] = set()
    for forme in m["forms"]:
        for fiche in data_manager.formulaSheet(forme):
            t = fiche["title"]
            if t not in m["keep"] or t in vus:
                continue
            vus.add(t)
            h += (
                f'<div class="eqblock"><div class="eqtitle">{_esc(t)}</div>'
                f'<div class="eq">{_esc(fiche["latex"])}</div>'
                f'<div class="var">{_esc(fiche.get("vars", ""))}</div></div>'
            )
    return h + '<p class="muted">Fiches complètes : page Base de données, documents Note de calcul.</p>'


def _reviewHTML() -> str:
    q = [
        "Le modèle physique est adapté à ce problème (hypothèses du §2).",
        "Les équations du §3 sont justes.",
        "Les valeurs du solveur sont cohérentes avec ma vérification.",
        "Les diagrammes (§5) sont cohérents (signes, allures, extrema).",
        "Les données d'entrée (§1) sont correctes.",
    ]
    h = "<table><tr><th>Question</th><th>Avis</th></tr>"
    h += "".join(f'<tr><td>{_esc(x)}</td><td class="rv">{_CHOIX}</td></tr>' for x in q) + "</table>"
    return (
        h + '<p>Commentaires :</p><div class="comment"></div>'
        "<p>Relecteur : ______________________ &nbsp; Date : ____________ &nbsp; Conclusion : &#9744; validé &nbsp; "
        "&#9744; validé avec réserves &nbsp; &#9744; refusé</p>"
    )


# ------------------------------------------------------------------------------------------ Assemblage


def recompute(key: str, saisie: dict, dm, previous: dict | None = None) -> dict:
    """Refait le calcul de la page `key` (et les résultats facultatifs déjà calculés) avec la saisie actuelle.

    Entrées : `key` ; `saisie` (unités d'affichage) ; `dm` (base) ; `previous` : résultats facultatifs déjà calculés
    dans la session, dict dont les clés combos, ec3, fatigue, profiles (Poutres) indiquent ce qu'il faut refaire.
    Sortie : `res` (sortie de computeXxx) avec `extras` et `erreursRecalcul` (list[str]). Cisaillement refait aussi la
    clavette et la goupille, comme MATLAB. Erreur du calcul principal : relevée telle quelle.
    """
    meta(key)  # clé inconnue : erreur
    f = {
        "Sec": compute.computeSection,
        "Beam": beam_services.computeBeam,
        "Tr": compute.computeTruss,
        "Tra": compute.computeTraction,
        "Cis": compute.computeShear,
        "Tor": compute.computeTorsion,
        "Fle": compute.computeBending,
        "Fla": compute.computeBuckling,
        "Ten": compute.computeTensor,
        "Hoo": compute.computeHooke,
        "Jau": compute.computeGauges,
    }[key]
    res = f(saisie, dm)
    extras: dict = {}
    errs: list[str] = []
    steps: list[tuple[str, str, object]] = []
    if key == "Cis":
        steps = [
            ("key", "computeKey", lambda: compute.computeKey(saisie, dm)),
            ("pin", "computePin", lambda: compute.computePin(saisie, dm)),
        ]
    elif key == "Beam":
        src = "enveloppe" if saisie["ecsrc"] == "enveloppe" else "poutre"
        steps = [
            ("combos", "computeCombinations", lambda: beam_services.computeCombinations(saisie, dm)),
            ("ec3", "checkEurocode", lambda: beam_design.checkEurocode(saisie, dm, src)),
            ("fatigue", "checkFatigue", lambda: beam_design.checkFatigue(saisie, dm)),
            (
                "profiles",
                "findLightestProfile",
                lambda: beam_design.findLightestProfile(saisie, dm, saisie["pfam"], saisie["pdef"]),
            ),
        ]
    for cle, nom, fn in steps:
        if key == "Beam" and (previous is None or previous.get(cle) is None):
            continue  # seulement ce qui a déjà été calculé dans la session
        try:
            extras[cle] = fn()
        except Exception as err:
            errs.append(f"{nom} : {getattr(err, 'message', err)}")
    res = dict(res)
    res["extras"] = extras
    res["erreursRecalcul"] = errs
    return res


def generate(key: str, saisie: dict, res: dict, dm) -> str:
    """Dossier de validation complet (HTML autonome) de l'onglet `key`.

    Entrées : `key` (KEYS) ; `saisie` ; `res` (sortie de `recompute`) ; `dm` (base). Sortie : texte HTML.
    Les formules demandent MathJax (Internet) ; les diagrammes Plotly sont chargés depuis un CDN.
    """
    m = meta(key)
    hyp, nWarn, nKo = _hypSafe(key, saisie, res, dm)
    hand, nOK, nTot = _handSafe(key, saisie, res, dm)
    contenus = {
        "donnees": _sure(_inputsHTML, key, saisie),
        "hypotheses": hyp,
        "verif": hand,
        "resultats": _sure(_resultsHTML, key, res),
        "diagrammes": _sure(_plotsHTML, key, saisie, res),
        "rapport": _sure(lambda: _reportHTML(_rapportLignes(key, res))),
        "formules": _sure(_formulasHTML, m),
        "avis": _reviewHTML(),
    }
    sections = [
        {
            "id": i,
            "titre": t,
            "titre_court": t.split(". ", 1)[1],
            "html": contenus[i],
        }
        for i, t in _SECTIONS
    ]
    return _template().render(
        titre=m["title"],
        date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        python=platform.python_version(),
        statut=res.get("status", ""),
        bilan=_bilan(nOK, nTot, nWarn, nKo, len(res.get("erreursRecalcul", []))),
        erreurs=res.get("erreursRecalcul", []),
        sections=sections,
    )


def _hypSafe(key: str, saisie: dict, res: dict, dm) -> tuple[str, int, int]:
    try:
        return _hypothesesHTML(key, saisie, res, dm)
    except Exception as err:  # hypothèses non contrôlées : compte comme une hypothèse non satisfaite dans le bilan
        return f'<p class="warnbox">Section indisponible : {_esc(err)}</p>', 0, 1


def _handSafe(key: str, saisie: dict, res: dict, dm) -> tuple[str, int, int]:
    try:
        return _handHTML(key, saisie, res, dm)
    except Exception as err:
        return f'<p class="warnbox">Section indisponible : {_esc(err)}</p>', 0, 0


def _bilan(nOK: int, nTot: int, nWarn: int, nKo: int, nErr: int = 0) -> str:
    if nTot == 0:
        h = (
            '<span class="ko">vérification indépendante non exécutée (voir §3) : aucun contrôle de calcul n\'a pu '
            "être fait</span>"
        )
    else:
        h = f'<span class="ok">{nOK} / {nTot} contrôles de calcul concordent</span>'
    if nTot > nOK:
        h += f' ; <span class="ko">{nTot - nOK} écart(s) à examiner</span>'
    if nKo > 0:
        h += f' ; <span class="ko">{nKo} hypothèse(s) NON satisfaite(s)</span>'
    if nErr > 0:
        h += f" ; <span class=\"ko\">{nErr} calcul(s) annexe(s) non refait(s) (voir l'encadré d'erreurs)</span>"
    if nWarn > 0:
        h += f' ; <span class="warn">{nWarn} point(s) d\'attention sur les hypothèses</span>'
    return h + "."


def _template():
    return Environment(loader=FileSystemLoader(_TEMPLATES), autoescape=True).get_template("validation.html.j2")


def fileName(key: str, now: datetime | None = None) -> str:
    """Nom du fichier proposé au téléchargement : Validation_<Titre>_AAAAMMJJ_HHMMSS.html."""
    import re

    now = now or datetime.now()
    titre = re.sub(r"[^A-Za-z0-9]+", "_", meta(key)["title"])
    return f"Validation_{titre}_{now:%Y%m%d_%H%M%S}.html"


def explanationRows(key: str, saisie: dict, res: dict, dm) -> list[dict]:
    """Lignes « équation avec valeurs » de l'onglet `key`, avec contrôle à la main (titres de groupe sans contrôle)."""
    return _handRows(key, saisie, res, dm, withExtras=True)


def explanationVerdict(row: dict) -> tuple[float, bool]:
    """(écart absolu, concordance) d'une ligne renvoyée par explanationRows."""
    return _verdict(row)


def solverEquations(key: str, res: dict) -> list[tuple[str, list[str]]]:
    """Équations écrites par le solveur pour l'onglet `key` : liste de (nom, formules LaTeX)."""
    return _latexBlocks(key, res)
