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

from mecastruct.core import data_manager, geometry
from mecastruct.core.errors import MecaStructError
from mecastruct.core.pp import asPP
from mecastruct.services import beam_design, beam_services, compute

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


def _result(key: str, res: dict) -> dict:
    """Résultat du moteur : res lui-même pour Poutres (sol, defl, check…), res["result"] ailleurs."""
    return res if key == "Beam" else res["result"]


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
    from scipy.integrate import quad

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


def _handRows(key: str, saisie: dict, res: dict, dm) -> list[dict]:
    """Lignes de contrôle à la main de l'onglet (sans appeler les moteurs). Sous-étape A : Tra et Sec seulement."""
    if key == "Sec":
        return _handSec(saisie, res)
    if key == "Tra":
        return _handTra(saisie, res)
    return []


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
    rows = _handRows(key, saisie, res, dm)
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
        bilan=_bilan(nOK, nTot, nWarn, nKo),
        erreurs=res.get("erreursRecalcul", []),
        sections=sections,
    )


def _hypSafe(key: str, saisie: dict, res: dict, dm) -> tuple[str, int, int]:
    try:
        return _hypothesesHTML(key, saisie, res, dm)
    except Exception as err:
        return f'<p class="warnbox">Section indisponible : {_esc(err)}</p>', 0, 0


def _handSafe(key: str, saisie: dict, res: dict, dm) -> tuple[str, int, int]:
    try:
        return _handHTML(key, saisie, res, dm)
    except Exception as err:
        return f'<p class="warnbox">Section indisponible : {_esc(err)}</p>', 0, 0


def _bilan(nOK: int, nTot: int, nWarn: int, nKo: int) -> str:
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
