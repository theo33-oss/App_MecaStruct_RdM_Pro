"""Base de données de MecaStruct : matériaux, profilés et pressions de matage (valeurs SI).

Port de DataManager.m, sauf les abaques Kt et la table des intégrales de Mohr (étape E04).
Les valeurs viennent de web/data/*.json (exportés de MATLAB) : seule la logique est portée ici.
"""

import functools
import math
import re

import numpy as np
import pandas as pd

from mecastruct.core.errors import MecaStructError
from mecastruct.core.utils import as_list, load_json

FAMILIES = ("IPN", "IPE", "HEA", "HEB", "UPN", "UAP")
MATERIAL_VARS = ["Name", "Category", "E", "G", "nu", "Re", "Rm", "alpha", "rho", "Note", "IsUser", "Author"]
PROFILE_VARS = [
    "Name",
    "h",
    "b",
    "a",
    "e",
    "r",
    "S",
    "Iz",
    "Iy",
    "Wz",
    "Wy",
    "rz",
    "ry",
    "mass",
    "c",
    "IsUser",
    "Author",
]
BEARING_VARS = ["Liaison", "Conditions", "Pmin", "Pmax", "Note"]
RHO_STEEL = 7850.0  # kg/m³ : masse linéique d'un profilé = ρ · S

_ACCENTS = str.maketrans(
    "àáâãäåçèéêëìíîïñòóôõöùúûüýÿÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝ",
    "aaaaaaceeeeiiiinooooouuuuyyAAAAAACEEEEIIIINOOOOOUUUUY",
)


class DataManager:
    """Base de données de MecaStruct : matériaux, profilés, pressions de matage (valeurs SI).

    Les ajouts de l'utilisateur restent en mémoire ; ils se sauvegardent avec exportUserData
    et se rechargent avec importUserData.
    """

    def __init__(self) -> None:
        """Charge la base par défaut depuis web/data : matériaux, profilés par famille, pressions de matage.

        Les matériaux viennent de materials.json, suivi de materials_extra.json (même format).
        """
        materiaux = as_list(load_json("materials.json")) + as_list(load_json("materials_extra.json"))
        self._defaultMaterials = pd.DataFrame(materiaux, columns=MATERIAL_VARS)
        profiles = load_json("profiles.json")
        self._defaultProfiles = {fam: pd.DataFrame(as_list(profiles[fam]), columns=PROFILE_VARS) for fam in FAMILIES}
        self.Materials = self._defaultMaterials.copy()
        self.Profiles = {fam: T.copy() for fam, T in self._defaultProfiles.items()}
        self.BearingPressures = _bearingTableDefault()

    # ---------------------------------------------------------------------------------------------
    # Matériaux
    # ---------------------------------------------------------------------------------------------

    def listMaterials(self) -> list[str]:
        """Noms des matériaux disponibles, dans l'ordre de la base.

        Sortie : list[str].
        """
        return list(self.Materials["Name"])

    def getMaterial(self, name: str) -> dict:
        """Caractéristiques d'un matériau (recherche tolérante : casse, accents, espaces, préfixe unique).

        Entrée : `name`, ex. « S235 », « s 235 », « xc38 ».
        Sortie : dict Name, Category, E, G, nu, Re, Rm (Pa), alpha (1/°C), rho (kg/m³), Note, IsUser, Author.
        Erreur : MecaStruct:DataManager:unknownMaterial.
        """
        idx = _matchName(self.Materials["Name"], name)
        if idx is None:
            raise MecaStructError("MecaStruct:DataManager:unknownMaterial", f"Matériau inconnu : « {name} ».")
        return _rowToDict(self.Materials.iloc[idx])

    def addMaterial(self, m: dict) -> None:
        """Ajoute ou remplace un matériau utilisateur (même nom, casse et espaces ignorés).

        Entrée : `m` dict avec Name (requis) et, en SI, E, G, nu, Re, Rm (Pa), alpha (1/°C), rho (kg/m³),
        Category, Note, Author. Les champs absents valent NaN ; la constante élastique manquante est
        complétée par completeIsotropic. Le matériau est marqué IsUser = True.
        Bornes de plausibilité (SI) : E dans [1e10 ; 5e11] Pa, Re et Rm dans [1e6 ; 3e9] Pa, Re ≤ Rm.
        Erreurs : MecaStruct:DataManager:invalidMaterial, invalidNu, invalidModulus.
        """
        if not isinstance(m, dict) or _isBlank(m.get("Name")):
            raise MecaStructError(
                "MecaStruct:DataManager:invalidMaterial",
                "Le matériau doit être un dictionnaire avec un champ Name non vide.",
            )
        m = completeIsotropic(_prepareMaterial(m, "Utilisateur", "Matériau utilisateur."))
        _checkUserBounds(m)
        row = {**m, "IsUser": True, "Author": _authorOf(m, True)}
        T = self.Materials
        self.Materials = _replaceOrAppend(T, _exactIndex(T["Name"], m["Name"]), row, MATERIAL_VARS)

    def removeMaterial(self, name: str) -> None:
        """Supprime un matériau utilisateur ; si celui-ci remplaçait un matériau par défaut, ce dernier est restauré.

        Entrée : `name` (nom exact, casse et espaces ignorés).
        Erreurs : MecaStruct:DataManager:unknownMaterial, notUserMaterial (matériau de la base par défaut).
        """
        T = self.Materials
        idx = _exactIndex(T["Name"], name)
        if idx is None:
            raise MecaStructError("MecaStruct:DataManager:unknownMaterial", f"Matériau inconnu : « {name} ».")
        if not T["IsUser"].iloc[idx]:
            raise MecaStructError(
                "MecaStruct:DataManager:notUserMaterial",
                f"Seuls les matériaux utilisateur peuvent être supprimés "
                f"(« {T['Name'].iloc[idx]} » appartient à la base par défaut).",
            )
        iDef = _exactIndex(self._defaultMaterials["Name"], T["Name"].iloc[idx])
        self.Materials = _retirerLigne(T, idx, self._defaultMaterials, iDef, MATERIAL_VARS)

    # ---------------------------------------------------------------------------------------------
    # Profilés
    # ---------------------------------------------------------------------------------------------

    def listProfileFamilies(self) -> list[str]:
        """Familles de profilés disponibles.

        Sortie : ["IPN", "IPE", "HEA", "HEB", "UPN", "UAP"].
        """
        return list(FAMILIES)

    def listProfiles(self, family: str) -> list[str]:
        """Désignations des profilés d'une famille, ex. « IPE 200 ».

        Entrée : `family` (IPN, IPE, HEA, HEB, UPN ou UAP ; casse ignorée).
        Erreur : MecaStruct:DataManager:unknownFamily.
        """
        return list(self.Profiles[_checkFamily(family)]["Name"])

    def getProfile(self, family: str, name) -> dict:
        """Caractéristiques d'un profilé du catalogue, valeurs SI (m, m², m⁴, m³).

        Entrée : `family` et `name` (« IPE 200 », « IPE200 », « 200 » ou 200).
        Sortie : dict Family, Name, h, b, a (âme), e (aile), r, S, Iz (axe fort), Iy (axe faible), Wz, Wy,
        rz, ry, mass (kg/m), c (U : dos d'âme → G ; NaN sinon), IsUser, Author.
        Erreurs : MecaStruct:DataManager:unknownFamily, unknownProfile.
        """
        fam = _checkFamily(family)
        T = self.Profiles[fam]
        idx = _profileIndex(T["Name"], fam, name)
        if idx is None:
            raise MecaStructError(
                "MecaStruct:DataManager:unknownProfile",
                f"Profilé inconnu dans la famille {fam} : « {name} ».",
            )
        return {"Family": fam, **_rowToDict(T.iloc[idx])}

    def addProfile(self, family: str, p: dict) -> None:
        """Ajoute ou remplace un profilé utilisateur ; les champs géométriques manquants sont calculés.

        Entrée : `family` ; `p` dict avec Name, h, b, a, e (m, requis) et, optionnels, r, S, Iz, Iy, c,
        Wz, Wy, rz, ry, mass (SI). Sortie : None. Le profilé est marqué IsUser = True.
        Erreurs : MecaStruct:DataManager:unknownFamily, invalidProfile.
        """
        fam = _checkFamily(family)
        if not isinstance(p, dict) or _isBlank(p.get("Name")):
            raise MecaStructError(
                "MecaStruct:DataManager:invalidProfile",
                "Le profilé doit être un dictionnaire avec un champ Name non vide.",
            )
        row = _buildProfileRow(fam, p)
        T = self.Profiles[fam]
        self.Profiles[fam] = _replaceOrAppend(T, _profileIndex(T["Name"], fam, row["Name"]), row, PROFILE_VARS)

    def removeProfile(self, family: str, name) -> None:
        """Supprime un profilé utilisateur ; s'il remplaçait un profilé du catalogue, ce dernier est restauré.

        Erreurs : MecaStruct:DataManager:unknownFamily, unknownProfile, notUserProfile.
        """
        fam = _checkFamily(family)
        T = self.Profiles[fam]
        idx = _profileIndex(T["Name"], fam, name)
        if idx is None:
            raise MecaStructError(
                "MecaStruct:DataManager:unknownProfile",
                f"Profilé inconnu dans la famille {fam} : « {name} ».",
            )
        if not T["IsUser"].iloc[idx]:
            raise MecaStructError(
                "MecaStruct:DataManager:notUserProfile",
                f"Seuls les profilés utilisateur peuvent être supprimés "
                f"(« {T['Name'].iloc[idx]} » appartient au catalogue).",
            )
        D = self._defaultProfiles[fam]
        iDef = _profileIndex(D["Name"], fam, T["Name"].iloc[idx])
        self.Profiles[fam] = _retirerLigne(T, idx, D, iDef, PROFILE_VARS)

    # ---------------------------------------------------------------------------------------------
    # Pressions de matage
    # ---------------------------------------------------------------------------------------------

    def getBearingPressure(self, liaison: str, conditions: str) -> tuple[float, float]:
        """Pression admissible de matage, en Pa.

        Entrée : `liaison` (libellé de la table ou mots-clés non ambigus, ex. « fixe ») ;
        `conditions` (« médiocres », « moyennes », « très bonnes » ; accents, casse et préfixe ignorés).
        Sortie : (pmin, pmax) en Pa.
        Erreurs : MecaStruct:DataManager:bearingNotFound, bearingAmbiguous.
        """
        T = self.BearingPressures
        idx = _matchCondition(T["Conditions"], _matchLiaison(T["Liaison"], liaison), conditions)
        return float(T["Pmin"].iloc[idx]), float(T["Pmax"].iloc[idx])

    def setBearingPressure(self, liaison: str, conditions: str, pmin: float, pmax: float, note: str = "") -> None:
        """Modifie ou ajoute une ligne de la table de matage ; la ligne de même liaison et conditions est remplacée.

        Entrée : `liaison`, `conditions`, `pmin` et `pmax` (Pa, 0 < pmin ≤ pmax), `note` (texte libre).
        Erreur : MecaStruct:DataManager:invalidBearing.
        """
        if _isBlank(note):
            note = "Valeur utilisateur"
        if not (
            _isNumber(pmin)
            and _isNumber(pmax)
            and math.isfinite(pmin)
            and math.isfinite(pmax)
            and pmin > 0
            and pmax >= pmin
        ):
            raise MecaStructError(
                "MecaStruct:DataManager:invalidBearing",
                "Les pressions doivent vérifier 0 < Pmin ≤ Pmax (Pa).",
            )
        if _isBlank(liaison) or _isBlank(conditions):
            raise MecaStructError(
                "MecaStruct:DataManager:invalidBearing",
                "La liaison et les conditions doivent être renseignées.",
            )
        T = self.BearingPressures
        kL = _keys(T["Liaison"])
        kC = _keys(T["Conditions"])
        idx = next(
            (i for i in range(len(T)) if kL[i] == _normKey(liaison) and kC[i] == _normKey(conditions)),
            None,
        )
        row = {
            "Liaison": str(liaison),
            "Conditions": str(conditions),
            "Pmin": float(pmin),
            "Pmax": float(pmax),
            "Note": str(note),
        }
        self.BearingPressures = _replaceOrAppend(T, idx, row, BEARING_VARS)

    def resetBearingPressures(self) -> None:
        """Restaure la table de matage par défaut (valeurs de web/data/bearing_pressures.json)."""
        self.BearingPressures = _bearingTableDefault()

    # ---------------------------------------------------------------------------------------------
    # Données utilisateur (remplace saveUserData / loadUserData du fichier .mat)
    # ---------------------------------------------------------------------------------------------

    def exportUserData(self) -> dict:
        """Ajouts utilisateur (matériaux et profilés IsUser) et table de matage complète.

        Sortie : dict {"materials": [dict], "profiles": {famille: [dict]}, "bearing": [dict]}, en types
        Python simples (sérialisable en JSON).
        """
        return {
            "materials": [_rowToDict(r) for _, r in self.Materials.iterrows() if r["IsUser"]],
            "profiles": {
                fam: [_rowToDict(r) for _, r in T.iterrows() if r["IsUser"]] for fam, T in self.Profiles.items()
            },
            "bearing": [_rowToDict(r) for _, r in self.BearingPressures.iterrows()],
        }

    def importUserData(self, data: dict) -> int:
        """Fusionne des données utilisateur (sortie de exportUserData) dans la base.

        Entrée : `data` dict. Les matériaux et profilés sont ajoutés (ou remplacent ceux de même nom) ;
        la table de matage du fichier, si elle est non vide, remplace la table courante.
        Sortie : nombre de matériaux et de profilés importés (int).
        Erreurs : MecaStruct:DataManager:invalidUserFile, plus les erreurs d'ajout.
        """
        if not isinstance(data, dict):
            raise MecaStructError(
                "MecaStruct:DataManager:invalidUserFile",
                "Les données utilisateur doivent être un dictionnaire.",
            )
        n = 0
        for mat in as_list(data.get("materials")):
            self.addMaterial(mat)
            n += 1
        for fam, rows in (data.get("profiles") or {}).items():
            if fam.upper() not in FAMILIES:
                continue
            for row in as_list(rows):
                self.addProfile(fam, row)
                n += 1
        if data.get("bearing"):
            self.BearingPressures = _validerTableMatage(data["bearing"])
        return n


# -------------------------------------------------------------------------------------------------
# Fonctions de module
# -------------------------------------------------------------------------------------------------


def completeIsotropic(m: dict) -> dict:
    """Complète la constante élastique manquante d'un matériau isotrope.

    Entrée : `m` dict avec E, G (Pa) et nu, éventuellement absents ou NaN ; Note optionnelle.
    Sortie : copie de `m` avec E, G, nu et Note complétés. Si E, G et ν sont connus, un écart relatif
    supérieur à 5 % entre G et E/(2(1+ν)) est signalé dans Note.
    Erreurs : MecaStruct:DataManager:invalidMaterial, invalidNu (ν hors de ]−1 ; 0,5[), invalidModulus (E ou G ≤ 0,
    ou E et G tous deux absents).
    """
    if not isinstance(m, dict):
        raise MecaStructError(
            "MecaStruct:DataManager:invalidMaterial",
            "completeIsotropic attend un dictionnaire.",
        )
    m = dict(m)
    E, G, nu = _numField(m, "E"), _numField(m, "G"), _numField(m, "nu")
    note = "" if _isBlank(m.get("Note")) else str(m["Note"])
    if (math.isfinite(E) and E <= 0) or (math.isfinite(G) and G <= 0):
        raise MecaStructError(
            "MecaStruct:DataManager:invalidModulus",
            "Les modules E et G doivent être strictement positifs.",
        )
    if not (math.isfinite(E) or math.isfinite(G)):
        raise MecaStructError(
            "MecaStruct:DataManager:invalidModulus",
            "Au moins un des modules E ou G (Pa) doit être renseigné.",
        )
    if math.isfinite(nu):
        _checkNu(nu)
    known = [math.isfinite(E), math.isfinite(G), math.isfinite(nu)]
    if all(known):
        _checkNu(nu)
        Gth = E / (2 * (1 + nu))
        gap = abs(G - Gth) / Gth
        if gap > 0.05 and "Écart de cohérence" not in note:
            note = _appendNote(
                note,
                f"Écart de cohérence : G = {G / 1e9:.4g} GPa alors que E/(2(1+ν)) = {Gth / 1e9:.4g} GPa "
                f"(écart {100 * gap:.1f} %).",
            )
    elif known[0] and known[2]:
        _checkNu(nu)
        G = E / (2 * (1 + nu))
        note = _appendNote(note, "G calculé par G = E/(2(1+ν)).")
    elif known[0] and known[1]:
        nu = E / (2 * G) - 1
        _checkNu(nu)
        note = _appendNote(note, "ν déduit de E et G : ν = E/(2G) − 1.")
    elif known[1] and known[2]:
        _checkNu(nu)
        E = 2 * G * (1 + nu)
        note = _appendNote(note, "E calculé par E = 2G(1+ν).")
    else:
        note = _appendNote(
            note,
            "Constantes élastiques incomplètes (au moins deux de E, G, ν sont nécessaires).",
        )
    m.update(E=E, G=G, nu=nu, Note=note)
    return m


def formulaKeys() -> list[str]:
    """Clés des fiches du formulaire rapide (19 thèmes).

    Sortie : list[str].
    """
    return as_list(load_json("formula_sheets.json")["keys"])


def formulaSheet(key: str) -> list[dict]:
    """Fiche de formules d'un thème du formulaire rapide.

    Entrée : `key`, une clé de formulaireKeys (casse et accents ignorés).
    Sortie : list[dict] avec title (texte français), latex (entre $...$, sans commande interdite) et vars
    (définitions des variables avec unités SI).
    Erreur : MecaStruct:DataManager:unknownFormulaKey.
    """
    k = _stripAccents(str(key).strip()).lower()
    sheets = load_json("formula_sheets.json")["sheets"]
    if k not in sheets:
        raise MecaStructError(
            "MecaStruct:DataManager:unknownFormulaKey",
            f"Clé de formulaire inconnue : « {k} ». Clés valides : {', '.join(formulaKeys())}.",
        )
    return as_list(sheets[k])


def sectionPresets() -> list[dict]:
    """Sections prédéfinies (formes creuses et pleines normalisées) du module Sections.

    Sortie : list[dict] avec name, type, dims (dimensions en mm).
    """
    return as_list(load_json("section_presets.json"))


@functools.cache
def hasSymbolic() -> bool:
    """Vrai si SymPy est importable : les moteurs l'utilisent avec un repli numérique.

    Sortie : bool, mis en cache.
    """
    try:
        import sympy  # noqa: F401
    except ImportError:
        return False
    return True


# -------------------------------------------------------------------------------------------------
# Aides privées (fonctions de module MATLAB privées, préfixe « _ »)
# -------------------------------------------------------------------------------------------------


def _bearingTableDefault() -> pd.DataFrame:
    """Table de matage par défaut (web/data/bearing_pressures.json)."""
    return pd.DataFrame(as_list(load_json("bearing_pressures.json")), columns=BEARING_VARS)


def _validerTableMatage(rows) -> pd.DataFrame:
    """Table de matage lue dans un fichier utilisateur ; erreur si une colonne manque ou si 0 < Pmin ≤ Pmax échoue."""
    T = pd.DataFrame(as_list(rows))
    manquantes = [c for c in BEARING_VARS if c not in T.columns]
    if manquantes:
        raise MecaStructError(
            "MecaStruct:DataManager:invalidUserFile",
            f"bearingPressures : variables manquantes : {', '.join(manquantes)}.",
        )
    T = T[BEARING_VARS].copy()
    for c in ("Liaison", "Conditions", "Note"):
        T[c] = T[c].astype(str)
    pmin = pd.to_numeric(T["Pmin"], errors="coerce").to_numpy(dtype=float)
    pmax = pd.to_numeric(T["Pmax"], errors="coerce").to_numpy(dtype=float)
    if not (np.isfinite(pmin).all() and np.isfinite(pmax).all() and (pmin > 0).all() and (pmax >= pmin).all()):
        raise MecaStructError(
            "MecaStruct:DataManager:invalidUserFile",
            "Table de matage invalide : il faut 0 < Pmin ≤ Pmax.",
        )
    T["Pmin"], T["Pmax"] = pmin, pmax
    return T.reset_index(drop=True)


def _stripAccents(s: str) -> str:
    """Remplace les lettres accentuées usuelles par leur lettre de base (« œ » → « oe »)."""
    return s.translate(_ACCENTS).replace("œ", "oe").replace("Œ", "OE")


def _normKey(s) -> str:
    """Clé de recherche : minuscules, sans accents, sans espaces ni ponctuation (« S 235 » → « s235 »)."""
    if isinstance(s, (int, float)):
        s = f"{s:g}"
    return re.sub(r"[^a-z0-9]", "", _stripAccents(str(s)).lower())


def _normWords(s) -> list[str]:
    """Mots de recherche (minuscules, sans accents) : « Clavette / cannelures - fixe » → clavette, cannelures, fixe."""
    return re.findall(r"[a-z0-9]+", _stripAccents(str(s)).lower())


def _keys(names) -> list[str]:
    """Clés de recherche d'une suite de noms."""
    return [_normKey(n) for n in names]


def _exactIndex(names, name) -> int | None:
    """Indice du premier nom égal à `name` (casse, accents, espaces et ponctuation ignorés), None si absent."""
    key = _normKey(name)
    return next((i for i, k in enumerate(_keys(names)) if k == key), None)


def _matchName(names, name) -> int | None:
    """Indice de `name` : correspondance exacte normalisée, sinon préfixe unique ; None si absent ou ambigu."""
    idx = _exactIndex(names, name)
    if idx is not None:
        return idx
    q = _normKey(name)
    hits = [i for i, k in enumerate(_keys(names)) if q and k.startswith(q)]
    return hits[0] if len(hits) == 1 else None


def _matchLiaison(liaisons, q: str) -> list[bool]:
    """Lignes de la table de matage correspondant à la liaison q (exacte, sinon tous les mots de q présents)."""
    keysL = _keys(liaisons)
    qk = _normKey(q)
    mask = [k == qk for k in keysL]
    if any(mask):
        return mask
    qw = _normWords(q)
    if not qw:
        raise MecaStructError("MecaStruct:DataManager:bearingNotFound", "Liaison non précisée.")
    ok = [all(any(w.startswith(m) for w in _normWords(lab)) for m in qw) for lab in liaisons]
    u = {k for k, o in zip(keysL, ok, strict=True) if o}
    if not u:
        raise MecaStructError(
            "MecaStruct:DataManager:bearingNotFound",
            f"Liaison inconnue dans la table de matage : « {q} ».",
        )
    if len(u) > 1:
        raise MecaStructError(
            "MecaStruct:DataManager:bearingAmbiguous",
            f"Liaison ambiguë : « {q} » ({len(u)} liaisons correspondent).",
        )
    target = u.pop()
    return [k == target for k in keysL]


def _matchCondition(conds, mask: list[bool], q: str) -> int:
    """Indice de la ligne (parmi mask) dont les conditions correspondent à q (exactes, sinon préfixe)."""
    keysC = _keys(conds)
    qk = _normKey(q)
    hit = [i for i, (k, m) in enumerate(zip(keysC, mask, strict=True)) if m and k == qk]
    if not hit and qk:
        hit = [i for i, (k, m) in enumerate(zip(keysC, mask, strict=True)) if m and k.startswith(qk)]
    if not hit:
        raise MecaStructError(
            "MecaStruct:DataManager:bearingNotFound",
            f"Conditions inconnues pour cette liaison : « {q} » (attendu : médiocres, moyennes, très bonnes).",
        )
    if len(hit) > 1:
        raise MecaStructError("MecaStruct:DataManager:bearingAmbiguous", f"Conditions ambiguës : « {q} ».")
    return hit[0]


def _profileIndex(names, fam: str, name) -> int | None:
    """Indice d'un profilé dans sa famille (« 200 », « IPE200 » ou « IPE 200 » acceptés) ; None si absent."""
    q = _normKey(name)
    if not q.startswith(fam.lower()):
        q = fam.lower() + q
    return next((i for i, k in enumerate(_keys(names)) if k == q), None)


def _checkFamily(family) -> str:
    """Famille de profilés normalisée en majuscules ; erreur si elle est inconnue."""
    if not isinstance(family, str):
        raise MecaStructError("MecaStruct:DataManager:unknownFamily", "La famille de profilés doit être un texte.")
    fam = family.strip().upper()
    if fam not in FAMILIES:
        raise MecaStructError(
            "MecaStruct:DataManager:unknownFamily",
            f"Famille de profilés inconnue : « {fam} » (familles : {', '.join(FAMILIES)}).",
        )
    return fam


def _isBlank(v) -> bool:
    """Vrai si la valeur est absente ou ne contient que des espaces."""
    if v is None:
        return True
    return isinstance(v, str) and not v.strip()


def _isNumber(x) -> bool:
    """Vrai pour un nombre réel (booléen exclu)."""
    return isinstance(x, (int, float, np.number)) and not isinstance(x, bool)


def _numField(s: dict, f: str) -> float:
    """Valeur numérique du champ f de s ; NaN si absent, vide ou non numérique."""
    x = s.get(f)
    return float(x) if _isNumber(x) else math.nan


def _posField(s: dict, f: str, required: bool, default: float = math.nan) -> float:
    """Champ numérique strictement positif (SI) ; default si absent ou NaN, erreur si required et absent."""
    v = _numField(s, f)
    if not math.isfinite(v):
        if required:
            raise MecaStructError(
                "MecaStruct:DataManager:invalidProfile",
                f"Le champ {f} (SI) est requis et doit être un réel strictement positif.",
            )
        v = default
    if not (math.isfinite(v) and v > 0):
        raise MecaStructError(
            "MecaStruct:DataManager:invalidProfile",
            f"Le champ {f} doit être un réel strictement positif (valeur : {v:g}).",
        )
    return v


def _checkNu(nu: float) -> None:
    """Vérifie −1 < ν < 0,5 ; erreur sinon."""
    if not (-1 < nu < 0.5):
        raise MecaStructError(
            "MecaStruct:DataManager:invalidNu",
            f"Coefficient de Poisson hors de l'intervalle ]−1 ; 0,5[ : ν = {nu:g}.",
        )


def _checkUserBounds(m: dict) -> None:
    """Bornes de plausibilité d'un matériau utilisateur (SI) ; NaN = non renseigné, 0 et ±inf refusés."""
    for k, lo, hi in (("E", 1e10, 5e11), ("Re", 1e6, 3e9), ("Rm", 1e6, 3e9)):
        v = m[k]
        if not math.isnan(v) and not (lo <= v <= hi):
            raise MecaStructError(
                "MecaStruct:DataManager:invalidMaterial",
                f"{k} = {v:g} Pa est hors de la plage plausible [{lo:g} ; {hi:g}] Pa : "
                f"la valeur doit être saisie en Pa (SI).",
            )


def _appendNote(note: str, txt: str) -> str:
    """Ajoute une phrase à une note, sans doublon."""
    if txt in note:
        return note
    return txt if not note.strip() else f"{note.strip()} {txt}"


def _authorOf(s: dict, is_user: bool) -> str:
    """« Ajouté par » : nom saisi, « Utilisateur » à défaut ; la base par défaut n'a pas d'auteur."""
    if not is_user:
        return "Base fournie"
    if not _isBlank(s.get("Author")):
        return str(s["Author"]).strip()
    return "Utilisateur"


def _prepareMaterial(m: dict, def_category: str, def_note: str) -> dict:
    """Normalise un matériau saisi : texte nettoyé, champs numériques (SI) ou NaN, contrôles de signe."""
    out = {"Name": str(m["Name"]).strip(), "Category": def_category}
    if not _isBlank(m.get("Category")):
        out["Category"] = str(m["Category"])
    for k in ("E", "G", "nu", "Re", "Rm", "alpha", "rho"):
        v = m.get(k)
        if v is None:
            v = math.nan
        elif not _isNumber(v):
            raise MecaStructError(
                "MecaStruct:DataManager:invalidMaterial",
                f"Le champ {k} doit être un scalaire réel (SI).",
            )
        out[k] = float(v)
    if out["Re"] < 0 or out["Rm"] < 0:
        raise MecaStructError("MecaStruct:DataManager:invalidMaterial", "Re et Rm doivent être positifs (Pa).")
    if out["Re"] > out["Rm"]:
        raise MecaStructError(
            "MecaStruct:DataManager:invalidMaterial",
            f"Re ({out['Re']:g} Pa) ne peut pas dépasser Rm ({out['Rm']:g} Pa).",
        )
    if out["rho"] <= 0:
        raise MecaStructError(
            "MecaStruct:DataManager:invalidMaterial",
            "La masse volumique doit être strictement positive.",
        )
    out["Note"] = def_note if _isBlank(m.get("Note")) else str(m["Note"])
    if "Author" in m:
        out["Author"] = m["Author"]
    return out


def _buildProfileRow(fam: str, p: dict) -> dict:
    """Ligne d'un profilé utilisateur ; les champs géométriques manquants sont calculés (géométrie simplifiée)."""
    name = str(p["Name"]).strip()
    if not _normKey(name).startswith(fam.lower()):
        name = f"{fam} {name}"
    is_u = fam in ("UPN", "UAP")
    h = _posField(p, "h", True)
    b = _posField(p, "b", True)
    a = _posField(p, "a", True)
    e = _posField(p, "e", True)
    if 2 * e >= h or a >= b:
        raise MecaStructError(
            "MecaStruct:DataManager:invalidProfile",
            "Géométrie incohérente : il faut 2e < h et a < b.",
        )
    r = _numField(p, "r")
    if not math.isfinite(r):
        r = 0.0
    if r < 0:
        raise MecaStructError("MecaStruct:DataManager:invalidProfile", "Le rayon de congé r doit être positif.")
    hw = h - 2 * e  # hauteur de l'âme entre ailes
    Sgeo = 2 * b * e + hw * a
    S = _posField(p, "S", False, Sgeo)
    Iz = _posField(p, "Iz", False, (b * h**3 - (b - a) * hw**3) / 12)
    if is_u:
        cGeo = (e * b**2 + hw * a**2 / 2) / Sgeo  # dos d'âme → G
        c = _posField(p, "c", False, cGeo)
        IyGeo = 2 * (e * b**3 / 12 + e * b * (b / 2 - c) ** 2) + hw * a**3 / 12 + hw * a * (a / 2 - c) ** 2
        Iy = _posField(p, "Iy", False, IyGeo)
        vz = max(c, b - c)
    else:
        c = math.nan
        Iy = _posField(p, "Iy", False, (2 * e * b**3 + hw * a**3) / 12)
        vz = b / 2
    Wz = _posField(p, "Wz", False, Iz / (h / 2))
    Wy = _posField(p, "Wy", False, Iy / vz)
    rz = _posField(p, "rz", False, math.sqrt(Iz / S))
    ry = _posField(p, "ry", False, math.sqrt(Iy / S))
    mass = _posField(p, "mass", False, RHO_STEEL * S)
    return {
        "Name": name,
        "h": h,
        "b": b,
        "a": a,
        "e": e,
        "r": r,
        "S": S,
        "Iz": Iz,
        "Iy": Iy,
        "Wz": Wz,
        "Wy": Wy,
        "rz": rz,
        "ry": ry,
        "mass": mass,
        "c": c,
        "IsUser": True,
        "Author": _authorOf(p, True),
    }


def _rowToDict(row: pd.Series) -> dict:
    """Ligne de table en dictionnaire Python simple : texte en str, booléen en bool, nombre en float."""
    out = {}
    for k, v in row.items():
        if isinstance(v, (bool, np.bool_)):
            out[k] = bool(v)
        elif v is None or isinstance(v, str):
            out[k] = v
        else:
            out[k] = float(v)
    return out


def _replaceOrAppend(T: pd.DataFrame, idx: int | None, row: dict, columns: list[str]) -> pd.DataFrame:
    """Table T où la ligne idx est remplacée par row (row est ajoutée en fin si idx vaut None)."""
    new = pd.DataFrame([row], columns=columns)
    if idx is None:
        return pd.concat([T, new], ignore_index=True)
    return pd.concat([T.iloc[:idx], new, T.iloc[idx + 1 :]], ignore_index=True)


def _retirerLigne(T: pd.DataFrame, idx: int, D: pd.DataFrame, iDef: int | None, columns: list[str]) -> pd.DataFrame:
    """Table T sans la ligne idx ; si la base par défaut D a une ligne iDef de même nom, elle la remplace."""
    if iDef is None:
        return T.drop(T.index[idx]).reset_index(drop=True)
    return _replaceOrAppend(T, idx, _rowToDict(D.iloc[iDef]), columns)
