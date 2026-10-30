"""Tests de hooke_gauges (étape E16) : portage des tests de tests/test_TensorAndCriteriaEngine.m pour la loi de Hooke,
les états plans, l'orthotropie, Voigt, les jauges, les ponts de Wheatstone et les rosettes ; cas golden restants
de golden_tensors.json.

Tolérance des cas golden (fiche E16) : rel = 1e-9 et abs = 1e-12 × la plus grande valeur absolue attendue du cas.
Le rendu LaTeX n'est pas testé : délimiteurs $, ASCII et commandes interdites seulement.
"""

import math

import numpy as np
import pytest

from mecastruct.core import tensors
from mecastruct.core.errors import MecaStructError
from mecastruct.core.hooke_gauges import (
    bridgeStrain,
    complianceIsotropic,
    complianceOrthotropic,
    gauge,
    gaugeStrain,
    hooke3D,
    hooke3DInverse,
    planeStrain,
    planeStress,
    rosette45,
    rosette60,
    stiffnessIsotropic,
    stiffnessOrthotropic,
    tensorToVoigt,
    voigtToTensor,
    wheatstone,
)
from mecastruct.core.tensors import criteria, plane2D
from tests.golden_tools import DEFAULT_IGNORE, assert_matches, get_case
from tests.test_data_manager import FORBIDDEN_LATEX

GOLDEN = "golden_tensors.json"
PREFIXE = "MecaStruct:TensorAndCriteriaEngine:"


def proche(actual, expected, rel=0.0, abs_=0.0):
    """Égalité à la tolérance près (verifyEqual avec RelTol / AbsTol de MATLAB ; rel = abs = 0 : égalité exacte).

    abs_ peut être un tableau (une tolérance par composante).
    """
    a = np.asarray(actual, dtype=float)
    e = np.asarray(expected, dtype=float)
    ecart = np.abs(a - e)
    assert np.all((ecart <= abs_ + rel * np.abs(e)) | (a == e)), f"{a} attendu {e} (écart {ecart})"


def erreur(identifiant, appel):
    """Vérifie que l'appel lève une MecaStructError d'identifiant 'MecaStruct:TensorAndCriteriaEngine:<id>'."""
    with pytest.raises(MecaStructError) as info:
        appel()
    assert info.value.identifier == PREFIXE + identifiant


def verifier_latex(chaines):
    """Chaînes LaTeX entre $, ASCII, sans commande interdite."""
    for s in chaines:
        assert s.startswith("$") and s.endswith("$"), s
        assert s.isascii(), s
        assert not any(cmd in s for cmd in FORBIDDEN_LATEX), s


def _rotation(theta):
    """Matrice R = [cos θ sin θ ; −sin θ cos θ] de la convention de TensorAndCriteriaEngine."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, s], [-s, c]])


def _epsilon_a(ps, theta):
    """Déformation ε(θ) dans la direction θ d'un état plan de contraintes ps (planeStress)."""
    return (ps["exx"] + ps["eyy"]) / 2 + (ps["exx"] - ps["eyy"]) / 2 * np.cos(2 * theta) + ps["exy"] * np.sin(2 * theta)


def _nombres(x):
    """Valeurs numériques (hors booléens) d'une sortie attendue, dictionnaires et listes parcourus."""
    if isinstance(x, dict):
        for v in x.values():
            yield from _nombres(v)
    elif isinstance(x, list):
        for v in x:
            yield from _nombres(v)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        yield float(x)


def _valeurs_finies(x) -> list[float]:
    """Valeurs absolues finies d'une sortie attendue (scalaire, liste ou matrice)."""
    return [abs(v) for v in _nombres(x) if math.isfinite(v)]


def _est_matrice(x) -> bool:
    """Vrai pour une matrice attendue, écrite en liste de lignes (liste contenant des listes)."""
    return isinstance(x, list) and any(isinstance(v, list) for v in x)


# Familles physiques, classées par NOM de champ (jamais par le dictionnaire qui le contient). Servent aux champs
# attendus à 0 et aux champs nuls en théorie : tolérance = 1e-12 × max de la famille dans le même cas.
# Les noms 'sigma', 'tau', 'sigma1', 'sigma2' et 'tauMax2D' existent dans strain2D et stress2D : le dictionnaire
# départage alors (voir _famille_champ). La famille angle n'a pas de règle « nul en théorie ».
_NOMS_DEFORMATION = {
    "exx",
    "eyy",
    "ezz",
    "gxy",
    "exy",
    "epsI",
    "epsII",
    "eps",
    "eps1",
    "eps2",
    "gammaHalf",
    "gamma",
    "gammaMax",
    "gammaMax2D",
    "readings",
    "center",
}
_NOMS_CONTRAINTE = {
    "sxx",
    "syy",
    "szz",
    "sxy",
    "sigma",
    "sigmaI",
    "sigmaII",
    "sigmaVM",
    "sigmaTresca",
    "sigma1",
    "sigma2",
    "tau",
    "tauMax2D",
    "tauMax3D",
    "principal3D",
    "centerStress",
    "radiusStress",
}
_NOMS_SOUPLESSE = {"S", "Sred"}
_NOMS_RAIDEUR = {"C", "Cred", "Qred", "G"}
_NOMS_ANGLE = {"theta", "thetaP", "thetaTauMax", "anglesDeg"}
# Sortie matricielle de premier niveau : famille du cas (son nom de fonction)
_FAMILLE_DU_CAS = {
    "complianceIsotropic": "souplesse",
    "complianceOrthotropic": "souplesse",
    "stiffnessIsotropic": "raideur",
    "stiffnessOrthotropic": "raideur",
}
# Famille de chaque entrée positionnelle des cas qui sont des listes (ν n'est pas pris en compte)
_FAMILLES_ENTREES = {
    "planeStress": ("contrainte", "contrainte", "contrainte", "raideur"),
    "planeStrain": ("deformation", "deformation", "deformation", "raideur"),
    "rosette45": ("deformation", "deformation", "deformation", "raideur"),
    "rosette60": ("deformation", "deformation", "deformation", "raideur"),
}
_FAMILLES = ("deformation", "contrainte", "souplesse", "raideur", "angle")


# Un champ dont la plus grande valeur attendue est inférieure à SEUIL_NUL × l'échelle de sa famille est traité comme
# nul en théorie : son écart n'est que du bruit d'arrondi (ex. stress2D.tau, attendu ±3,7e-9 pour une échelle de 1e8)
SEUIL_NUL = 1e-9


def _famille(nom: str) -> str | None:
    """Famille physique d'un champ d'après son seul nom (None si le nom n'appartient à aucune famille)."""
    if nom in _NOMS_ANGLE:
        return "angle"
    if nom in _NOMS_DEFORMATION:
        return "deformation"
    if nom in _NOMS_CONTRAINTE:
        return "contrainte"
    if nom in _NOMS_SOUPLESSE:
        return "souplesse"
    if nom in _NOMS_RAIDEUR:
        return "raideur"
    return None


def _famille_champ(identifiant: str, chemin) -> str | None:
    """Famille d'un champ, par ordre de priorité :
    1. angle, reconnu par son nom (theta, thetaP, thetaTauMax, anglesDeg), quel que soit le dictionnaire ;
    2. déformation si le chemin passe par strain2D, contrainte s'il passe par stress2D ;
    3. sinon le nom du champ seul (souplesse, raideur, déformation, contrainte).
    Une matrice de premier niveau prend la famille de son cas.
    """
    if not chemin:
        return _FAMILLE_DU_CAS.get(identifiant)
    nom = chemin[-1]
    if nom in _NOMS_ANGLE:
        return "angle"
    if "strain2D" in chemin:
        return "deformation"
    if "stress2D" in chemin:
        return "contrainte"
    return _famille(nom)


def _feuilles(x, chemin=()):
    """(chemin, valeur) de chaque champ d'une sortie : dictionnaires parcourus, listes et scalaires gardés entiers."""
    if isinstance(x, dict):
        for cle, val in x.items():
            if cle not in DEFAULT_IGNORE:
                yield from _feuilles(val, chemin + (cle,))
    else:
        yield chemin, x


def _tolerances(identifiant):
    """Tolérance abs_ de chaque champ d'un cas golden (règle par champ, voir verifier_golden).

    Renvoie une liste de (chemin, valeur attendue, abs_, étiquette). Étiquettes : 'propre' (champ non nul au-dessus
    du seuil, tolérance 1e-12 × son propre max), 'residu' (checkResidual, 1e-9), 'NaN' (égalité stricte), 'angle'
    (1e-12 × son propre max, ou 1e-12 si nul), 'deformation (nul)' / 'contrainte (nul en théorie)' etc. (champ
    exactement nul ou nul en théorie : tolérance 1e-12 × max de la famille dans le même cas).
    """
    cas = get_case(GOLDEN, identifiant)
    feuilles = list(_feuilles(cas["sortie"]))
    familles = {f: [] for f in _FAMILLES}
    for chemin, val in feuilles:
        famille = _famille_champ(identifiant, chemin)
        if famille and not isinstance(val, str):
            familles[famille] += _valeurs_finies(val)
    for position, famille in enumerate(_FAMILLES_ENTREES.get(identifiant, ())):
        familles[famille].append(abs(float(cas["entrees"][position])))

    lignes = []
    for chemin, val in feuilles:
        if isinstance(val, str) or val is None or isinstance(val, bool):
            lignes.append((chemin, val, 0.0, "texte"))
            continue
        if chemin and chemin[-1] == "checkResidual":
            lignes.append((chemin, val, 1e-9, "residu"))
            continue
        valeurs = _valeurs_finies(val)
        if not valeurs:
            lignes.append((chemin, val, 0.0, "NaN"))
            continue
        famille = _famille_champ(identifiant, chemin)
        if famille == "angle":
            # Pas de règle « nul en théorie » pour les angles : 1e-12 × leur propre échelle (1e-12 si nul)
            lignes.append((chemin, val, 1e-12 * (max(valeurs) or 1.0), "angle"))
            continue
        echelle_famille = max(familles[famille], default=0.0) if famille else 0.0
        if max(valeurs) > 0 and max(valeurs) >= SEUIL_NUL * echelle_famille:
            lignes.append((chemin, val, 1e-12 * max(valeurs), "propre"))
            continue
        # Champ nul en théorie (ou exactement nul) : tolérance = 1e-12 × échelle de sa famille dans le cas
        assert famille and echelle_famille > 0, f"{identifiant}.{'.'.join(chemin)} : pas de famille d'échelle"
        etat = "nul" if max(valeurs) == 0 else "nul en théorie"
        lignes.append((chemin, val, 1e-12 * echelle_famille, f"{famille} ({etat})"))
    return lignes


def verifier_golden(identifiant, actual):
    """Comparaison à un cas golden : rel = 1e-9 et abs_ par champ.

    Règle (autorisée par Théo pour E16, code de test seulement) :
    - champ non nul au-dessus du seuil (scalaire, vecteur ou matrice) : abs_ = 1e-12 × plus grande valeur absolue de
      ce champ ;
    - champ nul en théorie, c'est-à-dire dont la plus grande valeur attendue est inférieure à 1e-9 × l'échelle de sa
      famille dans le cas (ex. stress2D.tau de rosette60, attendu ±3,7e-9 pour des contraintes de 1e8 Pa, écart de
      signe dû à l'arrondi) : abs_ = 1e-12 × l'échelle de la famille. Les champs exactement nuls suivent la même règle.
      La famille se détermine par le nom du champ seul : déformations (exx, eyy, ezz, gxy, exy, epsI, epsII, eps,
      eps1, eps2, gammaHalf, gamma, gammaMax, gammaMax2D, readings, centre de Mohr), contraintes (sxx, syy, szz, sxy,
      sigma, sigmaI, sigmaII, sigmaVM, sigmaTresca, sigma1, sigma2, tau, tauMax2D, tauMax3D, principal3D, centerStress,
      radiusStress), souplesse (S, Sred), raideur (C, Cred, Qred, G). Une matrice de premier niveau prend la famille de
      son cas (complianceIsotropic : souplesse ; stiffnessIsotropic : raideur, etc.). Les entrées de même famille
      comptent aussi (E est une raideur, planeStrain et rosette : e1, e2, e3 sont des déformations) ;
    - angle (theta, thetaP, thetaTauMax, anglesDeg) : pas de règle « nul en théorie » ; abs_ = 1e-12 × leur propre
      échelle, ou 1e-12 si leur valeur attendue est nulle ;
    - checkResidual, résidu sans unité : abs_ = 1e-9.
    Priorité de classement (_famille_champ) : angle par nom, puis dictionnaire strain2D (déformation) ou stress2D
    (contrainte), puis nom seul. Les noms partagés sigma, tau, sigma1, sigma2 et tauMax2D sont ainsi départagés par
    le dictionnaire, ce qui ne s'applique qu'à ces champs.

    Pourquoi la règle par cas (1e-12 × plus grande valeur du cas) est trop large : une seule grande valeur fixe la
    tolérance de tous les champs du cas. Dans planeStress, Qred vaut 2,3e11 : la tolérance devient 0,23 et exx ≈ 4e-4
    pourrait s'écarter de 0,2 sans être vu. La règle par bloc (matrice ou dictionnaire entier) était aussi trop
    large pour les champs placés directement dans un dictionnaire mêlant contraintes et déformations : dans rosette45,
    le dictionnaire entier contient des contraintes de 1,3e8 Pa, donc exy (1e-4) avait une tolérance de 1,3e-4. La
    règle par champ donne à chaque champ l'échelle de sa propre valeur.
    """
    for chemin, attendu, tol, _ in _tolerances(identifiant):
        obtenu = actual
        for cle in chemin:
            obtenu = obtenu[cle]
        assert_matches(obtenu, attendu, rel=1e-9, abs_=tol, path=".".join(chemin))


# -------------------------------------------------------------------------------------------------
# Loi de Hooke isotrope et 3D
# -------------------------------------------------------------------------------------------------
def test_hooke_isotrope_sc():
    E, nu = 210e9, 0.3
    S = complianceIsotropic(E, nu)
    C = stiffnessIsotropic(E, nu)
    G = E / (2 * (1 + nu))
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    proche(S @ C, np.eye(6), abs_=1e-13)
    proche(C @ S, np.eye(6), abs_=1e-13)
    proche(S, S.T)
    proche(C, C.T)
    proche(S[0, 0], 1 / E, rel=1e-14)
    proche(S[0, 1], -nu / E, rel=1e-14)
    proche(S[3, 3], 1 / G, rel=1e-14)
    proche(S[5, 5], 2 * (1 + nu) / E, rel=1e-14)
    proche(C[0, 0], lam + 2 * G, rel=1e-14)
    proche(C[0, 0], E * (1 - nu) / ((1 + nu) * (1 - 2 * nu)), rel=1e-14)
    proche(C[0, 1], lam, rel=1e-14)
    proche(C[4, 4], G, rel=1e-14)
    assert np.count_nonzero(S[:3, 3:]) + np.count_nonzero(C[:3, 3:]) == 0
    assert np.min(np.linalg.eigvalsh(C)) > 0
    # Matériau auxétique admissible
    proche(complianceIsotropic(1e9, -0.5) @ stiffnessIsotropic(1e9, -0.5), np.eye(6), abs_=1e-13)
    # Constantes non admissibles
    erreur("badMaterial", lambda: stiffnessIsotropic(E, 0.5))
    erreur("badMaterial", lambda: complianceIsotropic(-E, 0.3))
    erreur("badMaterial", lambda: complianceIsotropic(E, -1))


def test_hooke3d_aller_retour_thermique():
    E, nu, alpha, dT = 200e9, 0.28, 12e-6, 80
    G = E / (2 * (1 + nu))
    sigV = np.array([120, -30, 45, 20, -15, 60]) * 1e6
    e = hooke3D(sigV, E, nu, alpha, dT)
    assert e.shape == (6,)
    th = alpha * dT
    proche(e[0], (sigV[0] - nu * (sigV[1] + sigV[2])) / E + th, rel=1e-13)
    proche(e[1], (sigV[1] - nu * (sigV[0] + sigV[2])) / E + th, rel=1e-13)
    proche(e[2], (sigV[2] - nu * (sigV[0] + sigV[1])) / E + th, rel=1e-13)
    proche(e[3:], sigV[3:] / G, rel=1e-13)
    s2 = hooke3DInverse(e, E, nu, alpha, dT)
    proche(s2, sigV, abs_=1e-9 * np.max(np.abs(sigV)))
    # Dilatation libre : ε = αΔT·{1 1 1 0 0 0} ; aller-retour → σ = 0
    thermique = np.array([1, 1, 1, 0, 0, 0.0])
    e0 = hooke3D(np.zeros(6), E, nu, alpha, dT)
    proche(e0, th * thermique, rel=1e-15)
    proche(hooke3DInverse(e0, E, nu, alpha, dT), np.zeros(6), abs_=1e-3)
    # Dilatation empêchée : σ = −E αΔT/(1 − 2ν) (état hydrostatique)
    sb = hooke3DInverse(np.zeros(6), E, nu, alpha, dT)
    proche(sb, -E * th / (1 - 2 * nu) * thermique, abs_=1e-6, rel=1e-13)
    # Sans thermique (valeurs par défaut) et entrées tensorielles 3x3
    e1 = hooke3D(sigV, E, nu)
    proche(e1, complianceIsotropic(E, nu) @ sigV, rel=1e-15)
    eT = hooke3D(voigtToTensor(sigV, "stress"), E, nu, alpha, dT)
    proche(eT, e, rel=1e-14)
    sT = hooke3DInverse(voigtToTensor(e, "strain"), E, nu, alpha, dT)
    proche(sT, sigV, abs_=1e-9 * np.max(np.abs(sigV)))
    # Traction simple : εyy = −ν σ/E + αΔT
    eu = hooke3D(np.array([100e6, 0, 0, 0, 0, 0]), E, nu, alpha, dT)
    proche(eu[1], -nu * 100e6 / E + th, rel=1e-13)
    erreur("badInput", lambda: hooke3D([1, 2, 3], E, nu))


# -------------------------------------------------------------------------------------------------
# États plans
# -------------------------------------------------------------------------------------------------
def test_contraintes_planes():
    E, nu = 70e9, 0.33
    sxx, syy, sxy = 100e6, -50e6, 40e6
    r = planeStress(sxx, syy, sxy, E, nu)
    G = E / (2 * (1 + nu))
    proche(r["exx"], (sxx - nu * syy) / E, rel=1e-14)
    proche(r["eyy"], (syy - nu * sxx) / E, rel=1e-14)
    proche(r["gxy"], sxy / G, rel=1e-14)
    proche(r["ezz"], -nu * (sxx + syy) / E, rel=1e-14)
    e3 = hooke3D([sxx, syy, 0, 0, 0, sxy], E, nu)
    proche([r["exx"], r["eyy"], r["ezz"], r["gxy"]], e3[[0, 1, 2, 5]], rel=1e-13)
    proche(r["Sred"] @ [sxx, syy, sxy], [r["exx"], r["eyy"], r["gxy"]], rel=1e-13)
    proche(r["Sred"] @ r["Qred"], np.eye(3), abs_=1e-13)
    # Vectorisation : les scalaires sont étendus à la taille du premier tableau
    rv = planeStress([sxx, 2 * sxx], syy, [sxy, 0], E, nu)
    assert np.shape(rv["exx"]) == (2,)
    proche(rv["exx"][0], r["exx"], rel=1e-14)
    proche(rv["gxy"][1], 0, abs_=0)
    erreur("badInput", lambda: planeStress([1, 2], [1, 2, 3], 0, E, nu))


def test_deformations_planes():
    E, nu = 210e9, 0.3
    exx, eyy, gxy = 400e-6, -100e-6, 300e-6
    r = planeStrain(exx, eyy, gxy, E, nu)
    proche(r["szz"], nu * (r["sxx"] + r["syy"]), rel=1e-14)
    proche(r["ezz"], 0, abs_=0)
    s3 = hooke3DInverse([exx, eyy, 0, 0, 0, gxy], E, nu)
    proche([r["sxx"], r["syy"], r["szz"], r["sxy"]], s3[[0, 1, 2, 5]], rel=1e-13)
    e3 = hooke3D([r["sxx"], r["syy"], r["szz"], 0, 0, r["sxy"]], E, nu)
    proche(e3, [exx, eyy, 0, 0, 0, gxy], abs_=1e-17)
    proche(r["Cred"] @ [exx, eyy, gxy], [r["sxx"], r["syy"], r["sxy"]], rel=1e-13)
    proche(r["Cred"] @ r["Sred"], np.eye(3), abs_=1e-13)
    proche(r["Cred"][2, 2], E / (2 * (1 + nu)), rel=1e-14)


# -------------------------------------------------------------------------------------------------
# Orthotropie et notation de Voigt
# -------------------------------------------------------------------------------------------------
def test_orthotrope():
    c = {
        "E1": 140e9,
        "E2": 10e9,
        "E3": 10e9,
        "nu12": 0.3,
        "nu13": 0.3,
        "nu23": 0.45,
        "G12": 5e9,
        "G13": 5e9,
        "G23": 3.5e9,
    }
    S = complianceOrthotropic(c)
    C = stiffnessOrthotropic(c)
    proche(S, S.T)
    proche(C, C.T, rel=1e-14)
    proche(S @ C, np.eye(6), abs_=1e-12)
    nu21 = 0.3 * 10 / 140
    proche(S[0, 1], -0.3 / 140e9, rel=1e-14)
    proche(S[1, 0], -nu21 / 10e9, rel=1e-14)  # symétrie ν12/E1 = ν21/E2
    proche(S[1, 2], -0.45 / 10e9, rel=1e-14)
    proche([S[3, 3], S[4, 4], S[5, 5]], 1 / np.array([3.5e9, 5e9, 5e9]), rel=1e-14)
    assert np.min(np.linalg.eigvalsh(C)) > 0
    # Traction selon 1 : ε2/ε1 = −ν12, ε3/ε1 = −ν13
    eps = S @ [100e6, 0, 0, 0, 0, 0]
    proche(eps[1] / eps[0], -0.3, rel=1e-14)
    proche(eps[2] / eps[0], -0.3, rel=1e-14)
    # Limite isotrope
    E, nu = 200e9, 0.25
    G = E / (2 * (1 + nu))
    ci = {"E1": E, "E2": E, "E3": E, "nu12": nu, "nu13": nu, "nu23": nu, "G12": G, "G13": G, "G23": G}
    proche(complianceOrthotropic(ci), complianceIsotropic(E, nu), rel=1e-14)
    proche(stiffnessOrthotropic(ci), stiffnessIsotropic(E, nu), rel=1e-12)
    # Coefficients réciproques fournis : cohérents → accepté ; incohérents → erreur explicite
    c["nu21"] = nu21
    proche(complianceOrthotropic(c), S, rel=1e-15)
    c["nu21"] = 0.3
    erreur("orthoSymmetry", lambda: complianceOrthotropic(c))
    # Non défini positif : Δ < 0 (ν = 0,6 isotrope transverse)
    cb = dict(ci, nu12=0.6, nu13=0.6, nu23=0.6)
    erreur("notPositiveDefinite", lambda: complianceOrthotropic(cb))
    erreur("notPositiveDefinite", lambda: stiffnessOrthotropic(cb))
    # Non défini positif : 1 − ν12·ν21 < 0
    cb = dict(ci, nu12=1.2)
    erreur("notPositiveDefinite", lambda: complianceOrthotropic(cb))
    # Module de cisaillement nul
    cb = dict(ci, G12=0)
    erreur("notPositiveDefinite", lambda: stiffnessOrthotropic(cb))
    # Constante manquante
    cb = {nom: val for nom, val in ci.items() if nom != "G23"}
    erreur("badInput", lambda: complianceOrthotropic(cb))


def test_voigt():
    T = np.array([[1, 4, 5], [4, 2, 6], [5, 6, 3]], dtype=float)
    proche(tensorToVoigt(T, "stress"), [1, 2, 3, 6, 5, 4])
    proche(tensorToVoigt(T), [1, 2, 3, 6, 5, 4])
    proche(tensorToVoigt(T, "strain"), [1, 2, 3, 12, 10, 8])
    proche(voigtToTensor([1, 2, 3, 6, 5, 4], "stress"), T)
    proche(voigtToTensor([1, 2, 3, 12, 10, 8], "strain"), T)
    proche(voigtToTensor(tensorToVoigt(T, "strain"), "strain"), T)
    # 2x2
    T2 = np.array([[3, 7], [7, -1]], dtype=float)
    proche(tensorToVoigt(T2, "strain"), [3, -1, 14])
    proche(voigtToTensor([3, -1, 14], "strain"), T2)
    # Travail de déformation : σ:ε = {σ}ᵀ{ε} avec glissements ingénieur
    Ts = np.array([[10, 2, -3], [2, 5, 1], [-3, 1, -4]], dtype=float)
    Te = np.array([[1, 0.5, 0.2], [0.5, -2, 0.3], [0.2, 0.3, 0.7]])
    proche(np.sum(Ts * Te), tensorToVoigt(Ts, "stress") @ tensorToVoigt(Te, "strain"), rel=1e-14)
    # Erreurs
    erreur("notSymmetric", lambda: tensorToVoigt([[1, 2, 0], [3, 4, 0], [0, 0, 1]]))
    erreur("badKind", lambda: tensorToVoigt(np.eye(3), "foo"))
    erreur("badInput", lambda: voigtToTensor([1, 2, 3, 4]))
    erreur("badInput", lambda: tensorToVoigt(np.eye(4)))


# -------------------------------------------------------------------------------------------------
# Jauges, ponts et rosettes
# -------------------------------------------------------------------------------------------------
def test_jauge_bridgman():
    r = gauge(2.1, 500e-6, 120)
    proche(r["dRsurR"], 1.05e-3, rel=1e-14)
    proche(r["dR"], 0.126, rel=1e-13)
    proche(gaugeStrain(2.1, r["dRsurR"]), 500e-6, rel=1e-14)
    rv = gauge(2, [100e-6, -300e-6])
    proche(rv["dRsurR"], [200e-6, -600e-6], rel=1e-14)
    assert math.isnan(rv["R0"])
    proche(gaugeStrain(2, rv["dRsurR"]), [100e-6, -300e-6], rel=1e-14)
    erreur("badInput", lambda: gauge(0, 1e-3))


def test_pont_wheatstone():
    K, Vin, e, nu = 2, 10, 1000e-6, 0.3
    x = K * e
    # Quart de pont
    q = wheatstone("quart", K, Vin, e)
    proche(q["Vout"], Vin * K * e / 4, rel=1e-14)
    proche(q["VoutExact"], Vin * x / (2 * (2 + x)), rel=1e-12)
    proche(q["linearityError"], (q["Vout"] - q["VoutExact"]) / q["VoutExact"], rel=1e-12)
    proche(q["linearityError"], x / 2, rel=1e-9)  # (2 + x)/2 − 1
    proche(q["epsIndicated"], e, rel=1e-14)
    assert q["bridgeFactor"] == 1
    proche(bridgeStrain("quart", K, Vin, q["Vout"]), e, rel=1e-14)
    # Demi-pont (flexion : ε2 = −ε1) : linéaire exact
    d = wheatstone("demi", K, Vin, [e, -e])
    proche(d["Vout"], Vin * K * 2 * e / 4, rel=1e-14)
    proche(d["VoutExact"], d["Vout"], rel=1e-12)
    proche(d["epsMeasured"], e, rel=1e-14)
    proche(d["effectiveFactor"], 2, rel=1e-14)
    proche(bridgeStrain("demi", K, Vin, d["Vout"]), e, rel=1e-14)
    # Demi-pont « Poisson » : facteur 1 + ν
    dp = wheatstone("demi", K, Vin, [e, -nu * e])
    proche(dp["effectiveFactor"], 1 + nu, rel=1e-14)
    proche(bridgeStrain("demi", K, Vin, dp["Vout"], 1 + nu), e, rel=1e-14)
    # Pont complet (ε1 = −ε2 = ε3 = −ε4) : Vout = Vin·K·ε, linéaire exact
    f = wheatstone("complet", K, Vin, [e, -e, e, -e])
    proche(f["Vout"], Vin * K * e, rel=1e-14)
    proche(f["VoutExact"], Vin * x, rel=1e-12)
    assert f["bridgeFactor"] == 4
    proche(bridgeStrain("complet", K, Vin, f["Vout"]), e, rel=1e-14)
    proche(f["eps"], [e, -e, e, -e])
    # Compensation : deux jauges adjacentes de même déformation (thermique) → Vout = 0
    z = wheatstone("demi", K, Vin, [e, e])
    proche(z["Vout"], 0, abs_=1e-18)
    proche(z["VoutExact"], 0, abs_=1e-18)
    assert math.isnan(z["linearityError"])
    assert math.isnan(z["effectiveFactor"]) or z["effectiveFactor"] == 0
    # Réciproque vectorisée et nom alternatif
    proche(bridgeStrain("full", K, Vin, [f["Vout"], -f["Vout"]]), [e, -e], rel=1e-14)
    # Erreurs
    erreur("badConfig", lambda: wheatstone("triple", K, Vin, e))
    erreur("badInput", lambda: wheatstone("quart", K, Vin, [e, e]))
    erreur("badInput", lambda: wheatstone("demi", K, Vin, e))
    erreur("badInput", lambda: wheatstone("complet", K, Vin, [e, e, e, e, e]))
    erreur("badInput", lambda: wheatstone("quart", K, -1, e))
    erreur("badConfig", lambda: bridgeStrain(3, K, Vin, 1e-3))


def _rosette_cas(mat_ps, theta_list):
    """Lectures des jauges d'un état plan connu aux angles donnés (degrés)."""
    return [_epsilon_a(mat_ps, math.radians(a)) for a in theta_list]


def test_rosette45():
    E, nu = 210e9, 0.3
    # État de contraintes planes connu → déformations → lectures des jauges → état retrouvé
    sxx, syy, sxy = 150e6, -60e6, 45e6
    ps = planeStress(sxx, syy, sxy, E, nu)
    e1, e2, e3 = _rosette_cas(ps, [0, 90, 45])
    r = rosette45(e1, e2, e3, E, nu)
    proche(r["exx"], ps["exx"], rel=1e-12)
    proche(r["eyy"], ps["eyy"], rel=1e-12)
    proche(r["exy"], ps["exy"], rel=1e-12)
    proche(r["exy"], e3 - (e1 + e2) / 2, rel=1e-14)
    proche(r["gxy"], ps["gxy"], rel=1e-12)
    proche([r["sxx"], r["syy"], r["sxy"]], [sxx, syy, sxy], rel=1e-10)
    proche(r["ezz"], ps["ezz"], rel=1e-10)
    p2 = plane2D(sxx, syy, sxy)
    proche([r["sigmaI"], r["sigmaII"]], [p2["sigma1"], p2["sigma2"]], rel=1e-10)
    proche(r["thetaP"], p2["thetaP"], abs_=1e-12)
    proche(r["tauMax2D"], p2["rho"], rel=1e-10)
    c = criteria([r["sigmaI"], r["sigmaII"]], 235e6)
    proche(r["sigmaVM"], c["sigmaEqVM"], rel=1e-12)
    proche(r["sigmaTresca"], c["sigmaEqTresca"], rel=1e-12)
    proche(r["principal3D"], c["pr"], rel=1e-14)
    proche(r["mohr"]["center"], (ps["exx"] + ps["eyy"]) / 2, rel=1e-12)
    proche(r["mohr"]["radius"], math.hypot((ps["exx"] - ps["eyy"]) / 2, ps["exy"]), rel=1e-12)
    proche(r["mohr"]["centerStress"], p2["delta"], rel=1e-10)
    proche(r["mohr"]["radiusStress"], p2["rho"], rel=1e-10)
    assert r["checkResidual"] < 1e-16  # lectures ~1e-4 : écart relatif < 1e-12
    proche(r["readings"], [e1, e2, e3])
    proche(r["anglesDeg"], [0, 90, 45])
    proche(r["strain2D"]["eps1"], r["epsI"], rel=1e-14)
    proche(r["stress2D"]["sigma1"], r["sigmaI"], rel=1e-12)
    # Cas d'école en déformations : εxx = 600, εyy = −200, εxy = 250 µdéf
    rk = rosette45(600e-6, -200e-6, 450e-6)
    proche(rk["exy"], 250e-6, rel=1e-12)
    proche([rk["epsI"], rk["epsII"]], (200 + np.array([1, -1]) * math.sqrt(400**2 + 250**2)) * 1e-6, rel=1e-12)
    proche(rk["thetaP"], 0.5 * math.atan2(500, 800), abs_=1e-14)
    proche(rk["gammaMax"], 2 * math.sqrt(400**2 + 250**2) * 1e-6, rel=1e-12)
    # Sans matériau : contraintes non calculées
    assert math.isnan(rk["sxx"]) and math.isnan(rk["sigmaVM"])
    assert rk["stress2D"] is None
    erreur("badMaterial", lambda: rosette45(1e-4, 0, 0, E, 0.6))


def test_rosette60():
    E, nu = 70e9, 0.33
    sxx, syy, sxy = -80e6, 35e6, -25e6
    ps = planeStress(sxx, syy, sxy, E, nu)
    e0, e60, e120 = _rosette_cas(ps, [0, 60, 120])
    r = rosette60(e0, e60, e120, E, nu)
    proche([r["exx"], r["eyy"], r["exy"]], [ps["exx"], ps["eyy"], ps["exy"]], rel=1e-12)
    proche([r["sxx"], r["syy"], r["sxy"]], [sxx, syy, sxy], rel=1e-10)
    p2 = plane2D(sxx, syy, sxy)
    proche([r["sigmaI"], r["sigmaII"]], [p2["sigma1"], p2["sigma2"]], rel=1e-10)
    assert r["checkResidual"] < 1e-16
    proche(r["anglesDeg"], [0, 60, 120])
    # Cohérence des deux rosettes sur le même état
    r45 = rosette45(e0, _epsilon_a(ps, math.pi / 2), _epsilon_a(ps, math.pi / 4), E, nu)
    proche([r45["sigmaI"], r45["sigmaII"], r45["thetaP"]], [r["sigmaI"], r["sigmaII"], r["thetaP"]], rel=1e-10)


def test_rapports_et_latex_hooke_gauges():
    sortie = [
        planeStress(100e6, -50e6, 40e6, 70e9, 0.33),
        planeStress([100e6, 0], -50e6, 40e6, 70e9, 0.33),
        planeStrain(400e-6, -100e-6, 300e-6, 210e9, 0.3),
        gauge(2.1, 500e-6),
        gauge(2.1, [500e-6, -1e-4]),
        wheatstone("quart", 2, 10, 1e-3),
        wheatstone("demi", 2, 10, [1e-3, -1e-3]),
        wheatstone("complet", 2, 10, [1e-3, -1e-3, 1e-3, -1e-3]),
        wheatstone("demi", 2, 10, [1e-3, 1e-3]),
        rosette45(600e-6, -200e-6, 450e-6, 210e9, 0.3),
        rosette45(600e-6, -200e-6, 450e-6),
        rosette60(600e-6, 100e-6, -150e-6, 70e9, 0.33),
    ]
    for r in sortie:
        assert r["report"] and all(isinstance(s, str) for s in r["report"])
        verifier_latex(r["latex"])
    # Matrices LaTeX : lignes séparées par « \\ » ; Cred est la 3e chaîne de planeStrain
    cred = planeStrain(400e-6, -100e-6, 300e-6, 210e9, 0.3)["latex"][2]
    assert "80.769 \\end{array}" in cred
    assert cred.count(" \\\\ ") == 4
    assert " \\\\ " in tensors.principal(np.diag([3e6, 1e6, 0.0]), False)["latex"][0]


def test_erreurs_entrees_hooke_gauges():
    erreur("badMaterial", lambda: planeStrain(1e-3, 0, 0, 210e9, 0.7))
    erreur("badInput", lambda: complianceOrthotropic(42))
    erreur("badKind", lambda: voigtToTensor([1, 2, 3, 4, 5, 6], 2))


# -------------------------------------------------------------------------------------------------
# Cas golden restants (golden_tensors.json)
# -------------------------------------------------------------------------------------------------
def test_golden_complianceIsotropic():
    e = get_case(GOLDEN, "complianceIsotropic")["entrees"]
    verifier_golden("complianceIsotropic", complianceIsotropic(*e))


def test_golden_stiffnessIsotropic():
    e = get_case(GOLDEN, "stiffnessIsotropic")["entrees"]
    verifier_golden("stiffnessIsotropic", stiffnessIsotropic(*e))


def test_golden_hooke3D():
    e = get_case(GOLDEN, "hooke3D")["entrees"]
    verifier_golden("hooke3D", hooke3D(e["sigV"], e["E"], e["nu"], e["alpha"], e["dT"]))


def test_golden_hooke3DInverse():
    e = get_case(GOLDEN, "hooke3DInverse")["entrees"]
    verifier_golden("hooke3DInverse", hooke3DInverse(e["epsV"], e["E"], e["nu"], e["alpha"], e["dT"]))


def test_golden_planeStress():
    verifier_golden("planeStress", planeStress(*get_case(GOLDEN, "planeStress")["entrees"]))


def test_golden_planeStrain():
    verifier_golden("planeStrain", planeStrain(*get_case(GOLDEN, "planeStrain")["entrees"]))


def test_golden_complianceOrthotropic():
    e = get_case(GOLDEN, "complianceOrthotropic")["entrees"]
    verifier_golden("complianceOrthotropic", complianceOrthotropic(e))


def test_golden_stiffnessOrthotropic():
    e = get_case(GOLDEN, "stiffnessOrthotropic")["entrees"]
    verifier_golden("stiffnessOrthotropic", stiffnessOrthotropic(e))


def test_golden_gauge():
    verifier_golden("gauge", gauge(*get_case(GOLDEN, "gauge")["entrees"]))


@pytest.mark.parametrize("identifiant", ["wheatstone_quart", "wheatstone_demi", "wheatstone_complet"])
def test_golden_wheatstone(identifiant):
    e = get_case(GOLDEN, identifiant)["entrees"]
    verifier_golden(identifiant, wheatstone(e["config"], e["K"], e["Vin"], e["eps"]))


def test_golden_bridgeStrain_quart():
    e = get_case(GOLDEN, "bridgeStrain_quart")["entrees"]
    verifier_golden("bridgeStrain_quart", bridgeStrain(e["config"], e["K"], e["Vin"], e["Vout"]))


def test_golden_rosette45():
    verifier_golden("rosette45", rosette45(*get_case(GOLDEN, "rosette45")["entrees"]))


def test_golden_rosette60():
    verifier_golden("rosette60", rosette60(*get_case(GOLDEN, "rosette60")["entrees"]))
