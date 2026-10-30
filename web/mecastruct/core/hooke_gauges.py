"""Loi de Hooke, orthotropie, Voigt, jauges, ponts de Wheatstone et rosettes : port de TensorAndCriteriaEngine.m (E16).

complianceIsotropic, stiffnessIsotropic, hooke3D, hooke3DInverse : loi isotrope 3D avec dilatation thermique ;
planeStress, planeStrain : contraintes et déformations planes ;
complianceOrthotropic, stiffnessOrthotropic : 9 constantes ;
tensorToVoigt, voigtToTensor : notation de Voigt (cisaillement ingénieur pour les déformations) ;
gauge, gaugeStrain : loi de Bridgman ; wheatstone, bridgeStrain : ponts de Wheatstone ;
rosette45, rosette60 : rosettes.
Unités SI strictes (Pa, déformations sans dimension, tensions en V). Chaque résultat contient `report` et `latex`.
"""

import math

import numpy as np

from mecastruct.core.tensors import (
    _echelle,
    _erreur,
    _fmt,
    _matTex,
    _positif,
    _reelFini,
    _scalaire,
    _tableau,
    _tex,
    _umdef,
    _vecTxt,
    _voigtToTensor,
    plane2D,
    plane2DStrain,
)
from mecastruct.core.utils import is_num

# Montages de pont : nom normalisé → (nom, nombre de jauges actives, facteur de pont nominal)
_MONTAGES = {
    "quart": ("quart", 1, 1),
    "quart de pont": ("quart", 1, 1),
    "quart-de-pont": ("quart", 1, 1),
    "quarter": ("quart", 1, 1),
    "demi": ("demi", 2, 2),
    "demi-pont": ("demi", 2, 2),
    "demi pont": ("demi", 2, 2),
    "half": ("demi", 2, 2),
    "complet": ("complet", 4, 4),
    "pont complet": ("complet", 4, 4),
    "pont-complet": ("complet", 4, 4),
    "full": ("complet", 4, 4),
}
_THERMIQUE = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])  # {1 1 1 0 0 0} : dilatation isotrope


# -------------------------------------------------------------------------------------------------
# Contrôles et conventions
# -------------------------------------------------------------------------------------------------
def _verifierMateriau(E, nu) -> None:
    """Constantes isotropes : E > 0 (Pa) et −1 < ν < 0,5 (checkMaterial)."""
    if not is_num(E) or not math.isfinite(E) or E <= 0:
        raise _erreur("badMaterial", "Le module d'Young E doit être un scalaire strictement positif (Pa).")
    if not is_num(nu) or not math.isfinite(nu) or nu <= -1 or nu >= 0.5:
        raise _erreur("badMaterial", "Le coefficient de Poisson doit vérifier −1 < ν < 0,5.")


def _nonNul(x, nom: str) -> float:
    """Scalaire réel fini non nul (nonZeroScalar)."""
    x = _scalaire(x, nom)
    if x == 0:
        raise _erreur("badInput", f"{nom} ne doit pas être nul.")
    return x


def _facteurKind(kind) -> float:
    """Facteur des termes de cisaillement de Voigt : 1 pour les contraintes, 2 pour les déformations (kindFactor)."""
    if not isinstance(kind, str):
        raise _erreur("badKind", "kind doit valoir 'stress' ou 'strain'.")
    cle = kind.strip().lower()
    if cle in ("stress", "contrainte", "contraintes"):
        return 1.0
    if cle in ("strain", "deformation", "deformations", "déformation", "déformations"):
        return 2.0
    raise _erreur("badKind", f"kind doit valoir 'stress' ou 'strain' (reçu « {kind} »).")


def _estVecteur(v) -> bool:
    """Vrai pour un vecteur : scalaire, 1-D, ou 2-D dont une dimension vaut 1 (isvector de MATLAB)."""
    forme = np.shape(v)
    return len(forme) <= 1 or (len(forme) == 2 and 1 in forme)


def _voigt6(v, kind: str, nom: str) -> np.ndarray:
    """Vecteur de Voigt à 6 composantes ; un tenseur 3x3 est converti par tensorToVoigt (asVoigt6)."""
    if np.shape(v) == (3, 3):
        v = tensorToVoigt(v, kind)
    if not _reelFini(v) or np.size(v) != 6 or not _estVecteur(v):
        raise _erreur("badInput", f"{nom} doit être un vecteur de Voigt réel à 6 composantes (ou un tenseur 3x3).")
    return np.asarray(v, dtype=float).ravel()


def _memesTailles(valeurs, noms):
    """Trois tableaux de même taille : les scalaires sont étendus à la taille du premier tableau non scalaire."""
    A = [_tableau(x, n) for x, n in zip(valeurs, noms, strict=True)]
    forme = A[0].shape
    if A[0].ndim == 0:
        if A[1].ndim != 0:
            forme = A[1].shape
        elif A[2].ndim != 0:
            forme = A[2].shape
    B = [np.full(forme, float(x)) if x.ndim == 0 else x for x in A]
    if any(x.shape != forme for x in B):
        raise _erreur(
            "badInput", f"{noms[0]}, {noms[1]} et {noms[2]} doivent être des scalaires ou des tableaux de même taille."
        )
    return B


def _montage(config) -> tuple[str, int, int]:
    """Nom normalisé, nombre de jauges actives et facteur de pont d'un montage (bridgeConfig)."""
    if not isinstance(config, str):
        raise _erreur("badConfig", "Le montage doit être 'quart', 'demi' ou 'complet'.")
    cle = config.strip().lower()
    if cle not in _MONTAGES:
        raise _erreur("badConfig", f"Montage « {config} » inconnu : utiliser 'quart', 'demi' ou 'complet'.")
    return _MONTAGES[cle]


# -------------------------------------------------------------------------------------------------
# Loi de Hooke isotrope 3D
# -------------------------------------------------------------------------------------------------
def complianceIsotropic(E: float, nu: float) -> np.ndarray:
    """Matrice de souplesse isotrope 6x6 [S] ({ε} = [S]{σ}), notation de Voigt.

    Entrées : E (Pa, > 0), nu (−1 < ν < 0,5). Sortie : np.ndarray 6x6 (1/Pa), ordre [xx yy zz yz xz xy],
    cisaillement ingénieur (γ = 2ε).
    """
    _verifierMateriau(E, nu)
    G = E / (2 * (1 + nu))
    S = np.zeros((6, 6))
    S[:3, :3] = (-nu / E) * np.ones((3, 3)) + ((1 + nu) / E) * np.eye(3)
    S[3:, 3:] = np.eye(3) / G
    return S


def stiffnessIsotropic(E: float, nu: float) -> np.ndarray:
    """Matrice de rigidité isotrope 6x6 [C] ({σ} = [C]{ε}), notation de Voigt.

    Entrées : E (Pa, > 0), nu (−1 < ν < 0,5). Sortie : np.ndarray 6x6 (Pa), ordre [xx yy zz yz xz xy].
    """
    _verifierMateriau(E, nu)
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    C = np.zeros((6, 6))
    C[:3, :3] = lam * np.ones((3, 3)) + 2 * mu * np.eye(3)
    C[3:, 3:] = mu * np.eye(3)
    return C


def hooke3D(sigV, E: float, nu: float, alpha: float = 0.0, dT: float = 0.0) -> np.ndarray:
    """Loi de Hooke 3D isotrope avec dilatation thermique : {ε} = [S]{σ} + αΔT{1 1 1 0 0 0}.

    Entrées : sigV (Voigt 6 composantes en Pa, ou tenseur 3x3), E (Pa), nu, alpha (1/°C), dT (°C).
    Sortie : np.ndarray de 6 déformations [εxx εyy εzz γyz γxz γxy] (glissements ingénieur).
    """
    alpha = _scalaire(alpha, "alpha")
    dT = _scalaire(dT, "dT")
    sigV = _voigt6(sigV, "stress", "sigV")
    S = complianceIsotropic(E, nu)
    return S @ sigV + alpha * dT * _THERMIQUE


def hooke3DInverse(epsV, E: float, nu: float, alpha: float = 0.0, dT: float = 0.0) -> np.ndarray:
    """Loi de Hooke 3D inverse : {σ} = [C]({ε} − αΔT{1 1 1 0 0 0}).

    Entrées : epsV (Voigt 6 composantes, glissements ingénieur, ou tenseur 3x3), E (Pa), nu, alpha (1/°C), dT (°C).
    Sortie : np.ndarray de 6 contraintes [σxx σyy σzz σyz σxz σxy] (Pa).
    """
    alpha = _scalaire(alpha, "alpha")
    dT = _scalaire(dT, "dT")
    epsV = _voigt6(epsV, "strain", "epsV")
    C = stiffnessIsotropic(E, nu)
    return C @ (epsV - alpha * dT * _THERMIQUE)


# -------------------------------------------------------------------------------------------------
# États plans
# -------------------------------------------------------------------------------------------------
def planeStress(sxx, syy, sxy, E: float, nu: float) -> dict:
    """Loi de Hooke en contraintes planes (σzz = σxz = σyz = 0).

    Entrées : sxx, syy, sxy (Pa, scalaires ou tableaux de même taille), E (Pa), nu.
    Sortie : dict avec exx, eyy, gxy (= σxy/G), exy (= gxy/2), ezz (= −ν(σxx+σyy)/E), Sred (1/Pa, 3x3 sur
    [xx yy xy]), Qred (Pa, inverse de Sred), G (Pa), report, latex.
    """
    _verifierMateriau(E, nu)
    sxx, syy, sxy = _memesTailles((sxx, syy, sxy), ("sxx", "syy", "sxy"))
    G = E / (2 * (1 + nu))
    exx = (sxx - nu * syy) / E
    eyy = (syy - nu * sxx) / E
    gxy = sxy / G
    exy = gxy / 2
    ezz = -nu * (sxx + syy) / E
    Sred = np.array([[1, -nu, 0], [-nu, 1, 0], [0, 0, 2 * (1 + nu)]]) / E
    Qred = E / (1 - nu**2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])

    rep = [
        f"Contraintes planes (σzz = 0) : E = {_fmt(E / 1e9)} GPa ; ν = {_fmt(nu)} ; "
        f"G = E/(2(1+ν)) = {_fmt(G / 1e9)} GPa",
        "   εxx = (σxx − ν·σyy)/E ; εyy = (σyy − ν·σxx)/E ; γxy = σxy/G ; εzz = −ν·(σxx + σyy)/E",
    ]
    lat = [
        r"$\varepsilon_{xx} = \frac{\sigma_{xx} - \nu\,\sigma_{yy}}{E},\ \ \varepsilon_{yy} = "
        r"\frac{\sigma_{yy} - \nu\,\sigma_{xx}}{E},\ \ \gamma_{xy} = \frac{2(1+\nu)}{E}\sigma_{xy} = "
        r"\frac{\sigma_{xy}}{G}$",
        r"$\varepsilon_{zz} = -\frac{\nu}{E}(\sigma_{xx} + \sigma_{yy})$",
        r"$[S_{red}] = \frac{1}{E}\left[ \begin{array}{ccc} 1 & -\nu & 0 \\ -\nu & 1 & 0 \\ 0 & 0 & 2(1+\nu) "
        r"\end{array} \right] = " + _matTex(Sred * 1e9) + r"\ \mathrm{GPa}^{-1}$",
    ]
    if np.ndim(sxx) == 0:
        rep += [
            f"   σxx = {_fmt(sxx / 1e6)} MPa ; σyy = {_fmt(syy / 1e6)} MPa ; σxy = {_fmt(sxy / 1e6)} MPa",
            f"   → εxx = {_fmt(exx * 1e6)} µdéf ; εyy = {_fmt(eyy * 1e6)} µdéf ; γxy = {_fmt(gxy * 1e6)} µdéf ; "
            f"εzz = {_fmt(ezz * 1e6)} µdéf",
        ]
        lat.append(
            r"$\varepsilon_{xx} = "
            + _tex(exx * 1e6)
            + r",\ \ \varepsilon_{yy} = "
            + _tex(eyy * 1e6)
            + r",\ \ \gamma_{xy} = "
            + _tex(gxy * 1e6)
            + r",\ \ \varepsilon_{zz} = "
            + _tex(ezz * 1e6)
            + r"\ \ (\mu\mathrm{def})$"
        )
    else:
        rep.append(f"   Calcul vectorisé sur {np.size(sxx)} états de contraintes.")
    return {
        "exx": exx,
        "eyy": eyy,
        "gxy": gxy,
        "exy": exy,
        "ezz": ezz,
        "Sred": Sred,
        "Qred": Qred,
        "G": G,
        "report": rep,
        "latex": lat,
    }


def planeStrain(exx, eyy, gxy, E: float, nu: float) -> dict:
    """Loi de Hooke en déformations planes (εzz = γxz = γyz = 0).

    Entrées : exx, eyy (sans dimension), gxy (glissement ingénieur γxy = 2εxy), scalaires ou tableaux de même
    taille ; E (Pa), nu. Sortie : dict avec sxx, syy, sxy, szz (Pa), ezz (= 0), Cred (Pa, 3x3 sur [xx yy xy]),
    Sred (1/Pa), G (Pa), report, latex.
    """
    _verifierMateriau(E, nu)
    exx, eyy, gxy = _memesTailles((exx, eyy, gxy), ("exx", "eyy", "gxy"))
    k = E / ((1 + nu) * (1 - 2 * nu))
    G = E / (2 * (1 + nu))
    sxx = k * ((1 - nu) * exx + nu * eyy)
    syy = k * (nu * exx + (1 - nu) * eyy)
    sxy = G * gxy
    szz = nu * (sxx + syy)
    ezz = np.zeros_like(exx)
    Cred = k * np.array([[1 - nu, nu, 0], [nu, 1 - nu, 0], [0, 0, (1 - 2 * nu) / 2]])
    Sred = (1 + nu) / E * np.array([[1 - nu, -nu, 0], [-nu, 1 - nu, 0], [0, 0, 2]])

    rep = [
        f"Déformations planes (εzz = 0) : E = {_fmt(E / 1e9)} GPa ; ν = {_fmt(nu)} ; "
        f"E/((1+ν)(1−2ν)) = {_fmt(k / 1e9)} GPa",
        "   σxx = E/((1+ν)(1−2ν))·[(1−ν)εxx + νεyy] ; σyy = E/((1+ν)(1−2ν))·[νεxx + (1−ν)εyy] ; σxy = G·γxy",
        "   εzz = 0 ⇒ σzz = ν·(σxx + σyy)",
    ]
    lat = [
        r"$\sigma_{xx} = \frac{E}{(1+\nu)(1-2\nu)}\left[(1-\nu)\varepsilon_{xx} + \nu\,\varepsilon_{yy}\right],\ \ "
        r"\sigma_{yy} = \frac{E}{(1+\nu)(1-2\nu)}\left[\nu\,\varepsilon_{xx} + (1-\nu)\varepsilon_{yy}\right]$",
        r"$\sigma_{xy} = G\,\gamma_{xy},\ \ \varepsilon_{zz} = 0 \Rightarrow "
        r"\sigma_{zz} = \nu(\sigma_{xx} + \sigma_{yy})$",
        r"$[C_{red}] = \frac{E}{(1+\nu)(1-2\nu)}\left[ \begin{array}{ccc} 1-\nu & \nu & 0 \\ \nu & 1-\nu & 0 \\ "
        r"0 & 0 & \frac{1-2\nu}{2} \end{array} \right] = " + _matTex(Cred / 1e9) + r"\ \mathrm{GPa}$",
    ]
    if np.ndim(exx) == 0:
        rep += [
            f"   εxx = {_fmt(exx * 1e6)} µdéf ; εyy = {_fmt(eyy * 1e6)} µdéf ; γxy = {_fmt(gxy * 1e6)} µdéf",
            f"   → σxx = {_fmt(sxx / 1e6)} MPa ; σyy = {_fmt(syy / 1e6)} MPa ; σxy = {_fmt(sxy / 1e6)} MPa ; "
            f"σzz = {_fmt(szz / 1e6)} MPa",
        ]
        lat.append(
            r"$\sigma_{xx} = "
            + _tex(sxx / 1e6)
            + r",\ \ \sigma_{yy} = "
            + _tex(syy / 1e6)
            + r",\ \ \sigma_{xy} = "
            + _tex(sxy / 1e6)
            + r",\ \ \sigma_{zz} = "
            + _tex(szz / 1e6)
            + r"\ \ (\mathrm{MPa})$"
        )
    else:
        rep.append(f"   Calcul vectorisé sur {np.size(exx)} états de déformations.")
    return {
        "sxx": sxx,
        "syy": syy,
        "sxy": sxy,
        "szz": szz,
        "ezz": ezz,
        "Cred": Cred,
        "Sred": Sred,
        "G": G,
        "report": rep,
        "latex": lat,
    }


# -------------------------------------------------------------------------------------------------
# Orthotropie
# -------------------------------------------------------------------------------------------------
def _orthoCheck(c: dict) -> dict:
    """Contrôle des 9 constantes orthotropes (positivité, symétrie ν_ij/E_i = ν_ji/E_j, définie positivité).

    Entrée : c, dict avec E1 E2 E3 (Pa), nu12 nu13 nu23, G12 G13 G23 (Pa) ; nu21 nu31 nu32 optionnels.
    Sortie : dict des 9 constantes (floats) complété par nu21, nu31, nu32 déduits.
    """
    if not isinstance(c, dict):
        raise _erreur("badInput", "Les constantes orthotropes doivent être fournies dans une structure scalaire.")
    req = ["E1", "E2", "E3", "nu12", "nu13", "nu23", "G12", "G13", "G23"]
    manquantes = [nom for nom in req if nom not in c]
    if manquantes:
        raise _erreur("badInput", f"Constantes orthotropes manquantes : {', '.join(manquantes)}.")
    k = {nom: _scalaire(c[nom], nom) for nom in req}
    for module in ["E1", "E2", "E3", "G12", "G13", "G23"]:
        if k[module] <= 0:
            raise _erreur(
                "notPositiveDefinite",
                f"Le module {module} doit être strictement positif (matrice de souplesse non définie positive).",
            )
    k["nu21"] = k["nu12"] * k["E2"] / k["E1"]
    k["nu31"] = k["nu13"] * k["E3"] / k["E1"]
    k["nu32"] = k["nu23"] * k["E3"] / k["E2"]
    # (coefficient fourni, réciproque, module du coefficient, module de la réciproque)
    reciproques = [("nu21", "nu12", "E2", "E1"), ("nu31", "nu13", "E3", "E1"), ("nu32", "nu23", "E3", "E2")]
    for f, rev, ei, ej in reciproques:
        if f in c and c[f] is not None and not (is_num(c[f]) and math.isnan(c[f])):
            donne = _scalaire(c[f], f)
            attendu = k[f]
            tol = 1e-2 * max(abs(attendu), abs(donne)) + 1e-12
            if abs(donne - attendu) > tol:
                raise _erreur(
                    "orthoSymmetry",
                    f"Symétrie non respectée : {rev}/{ej} = {k[rev] / k[ej]:g} mais {f}/{ei} = {donne / k[ei]:g} "
                    f"(il faut ν_ij/E_i = ν_ji/E_j ; {f} attendu = {attendu:g}).",
                )
    # Définie positivité : critères de Sylvester sur le bloc normal adimensionné
    p12 = 1 - k["nu12"] * k["nu21"]
    p13 = 1 - k["nu13"] * k["nu31"]
    p23 = 1 - k["nu23"] * k["nu32"]
    Delta = (
        1
        - k["nu12"] * k["nu21"]
        - k["nu23"] * k["nu32"]
        - k["nu13"] * k["nu31"]
        - 2 * k["nu21"] * k["nu32"] * k["nu13"]
    )
    a = k["nu12"] * math.sqrt(k["E2"] / k["E1"])
    b = k["nu13"] * math.sqrt(k["E3"] / k["E1"])
    cc = k["nu23"] * math.sqrt(k["E3"] / k["E2"])
    Sn = np.array([[1, -a, -b], [-a, 1, -cc], [-b, -cc, 1]])
    try:
        np.linalg.cholesky(Sn)
        definie = True
    except np.linalg.LinAlgError:
        definie = False
    if not definie or p12 <= 0 or p13 <= 0 or p23 <= 0 or Delta <= 0:
        raise _erreur(
            "notPositiveDefinite",
            "Constantes orthotropes non admissibles : la matrice de souplesse n'est pas définie positive "
            "(énergie de déformation non positive). Conditions : "
            f"1 − ν12·ν21 = {p12:.4g}, 1 − ν13·ν31 = {p13:.4g}, 1 − ν23·ν32 = {p23:.4g}, "
            f"Δ = 1 − ν12·ν21 − ν23·ν32 − ν13·ν31 − 2·ν21·ν32·ν13 = {Delta:.4g} (toutes doivent être > 0).",
        )
    return k


def complianceOrthotropic(c: dict) -> np.ndarray:
    """Matrice de souplesse orthotrope 6x6 à partir de 9 constantes, notation de Voigt.

    Entrée : c, dict E1 E2 E3 (Pa), nu12 nu13 nu23, G12 G13 G23 (Pa) ; nu21, nu31, nu32 optionnels (contrôlés).
    Sortie : np.ndarray 6x6 (1/Pa), ordre [11 22 33 23 13 12], cisaillement ingénieur.
    """
    k = _orthoCheck(c)
    S = np.zeros((6, 6))
    S[0, 0] = 1 / k["E1"]
    S[1, 1] = 1 / k["E2"]
    S[2, 2] = 1 / k["E3"]
    S[0, 1] = S[1, 0] = -k["nu12"] / k["E1"]
    S[0, 2] = S[2, 0] = -k["nu13"] / k["E1"]
    S[1, 2] = S[2, 1] = -k["nu23"] / k["E2"]
    S[3, 3] = 1 / k["G23"]
    S[4, 4] = 1 / k["G13"]
    S[5, 5] = 1 / k["G12"]
    return S


def stiffnessOrthotropic(c: dict) -> np.ndarray:
    """Matrice de rigidité orthotrope 6x6 [C] = [S]⁻¹, à partir des mêmes constantes que complianceOrthotropic.

    Entrée : c (voir complianceOrthotropic). Sortie : np.ndarray 6x6 (Pa), ordre [11 22 33 23 13 12].
    Le bloc normal est inversé après mise à l'échelle diagonale (conditionnement).
    """
    S = complianceOrthotropic(c)
    d = np.sqrt(1 / np.diag(S[:3, :3]))
    Dm = np.diag(d)
    Sn = Dm @ S[:3, :3] @ Dm
    Cn = Dm @ np.linalg.solve(Sn, np.eye(3)) @ Dm
    C = np.zeros((6, 6))
    C[:3, :3] = (Cn + Cn.T) / 2
    C[3, 3] = 1 / S[3, 3]
    C[4, 4] = 1 / S[4, 4]
    C[5, 5] = 1 / S[5, 5]
    return C


# -------------------------------------------------------------------------------------------------
# Notation de Voigt
# -------------------------------------------------------------------------------------------------
def tensorToVoigt(T, kind: str = "stress") -> np.ndarray:
    """Conversion d'un tenseur symétrique 3x3 (ou 2x2) en vecteur de Voigt.

    Entrées : T (tenseur symétrique), kind = 'stress' (défaut) ou 'strain' (cisaillements doublés : glissements).
    Sortie : np.ndarray [Txx Tyy Tzz Tyz Txz Txy] (6) ou [Txx Tyy Txy] (3, 2x2), avec le facteur de kind.
    """
    f = _facteurKind(kind)
    if not _reelFini(T):
        raise _erreur("badInput", "Le tenseur doit être numérique, réel et fini.")
    A = np.asarray(T, dtype=float)
    if A.ndim == 2 and A.shape[0] == A.shape[1]:
        sc = np.max(np.abs(A))
        if sc > 0 and np.max(np.abs(A - A.T)) > 1e-10 * sc:
            raise _erreur("notSymmetric", "Le tenseur à convertir doit être symétrique.")
    if A.shape == (3, 3):
        return np.array([A[0, 0], A[1, 1], A[2, 2], f * A[1, 2], f * A[0, 2], f * A[0, 1]])
    if A.shape == (2, 2):
        return np.array([A[0, 0], A[1, 1], f * A[0, 1]])
    raise _erreur("badInput", "Le tenseur doit être de taille 3x3 ou 2x2.")


def voigtToTensor(v, kind: str = "stress") -> np.ndarray:
    """Conversion d'un vecteur de Voigt en tenseur symétrique (inverse de tensorToVoigt).

    Entrées : v (6 composantes [xx yy zz yz xz xy], ou 3 composantes [xx yy xy]), kind = 'stress' (défaut) ou
    'strain' (cisaillements de v = glissements ingénieur, divisés par 2 dans le tenseur).
    Sortie : np.ndarray 3x3 (ou 2x2) symétrique.
    """
    f = _facteurKind(kind)
    if not _reelFini(v) or not _estVecteur(v):
        raise _erreur("badInput", "Le vecteur de Voigt doit être un vecteur numérique, réel et fini.")
    w = np.asarray(v, dtype=float).ravel()
    if w.size == 6:
        w[3:] /= f
        return _voigtToTensor(w)
    if w.size == 3:
        return np.array([[w[0], w[2] / f], [w[2] / f, w[1]]])
    raise _erreur("badInput", "Le vecteur de Voigt doit avoir 6 (ou 3) composantes.")


# -------------------------------------------------------------------------------------------------
# Jauges et ponts de Wheatstone
# -------------------------------------------------------------------------------------------------
def gauge(K: float, eps, R0: float | None = None) -> dict:
    """Loi de Bridgman d'une jauge de déformation : ΔR/R = K·ε.

    Entrées : K (facteur de jauge, ≠ 0, ≈ 2 pour les métalliques), eps (déformation, scalaire ou tableau),
    R0 (résistance nominale en Ω, optionnelle). Sorties : K, eps, dRsurR = K·ε, R0 (NaN si absent),
    dR = R0·ΔR/R (Ω, NaN si R0 absent), report, latex.
    """
    K = _nonNul(K, "K")
    eps = _tableau(eps, "eps")
    R0 = math.nan if R0 is None else _positif(R0, "R0")
    dRsurR = K * eps
    dR = R0 * dRsurR

    rep = [f"Loi de Bridgman : ΔR/R = K·ε avec K = {_fmt(K)}"]
    lat = [r"$\frac{\Delta R}{R} = K\,\varepsilon$"]
    if np.ndim(eps) == 0:
        rep.append(f"   ε = {_fmt(eps * 1e6)} µdéf → ΔR/R = {_fmt(dRsurR)}")
        lat.append(
            r"$\frac{\Delta R}{R} = "
            + _tex(K)
            + r" \times "
            + _tex(eps * 1e6)
            + r" \cdot 10^{-6} = "
            + _tex(dRsurR)
            + "$"
        )
        if not math.isnan(R0):
            rep.append(f"   R0 = {_fmt(R0)} Ω → ΔR = {_fmt(dR)} Ω")
            lat.append(
                r"$\Delta R = R_0\,\frac{\Delta R}{R} = "
                + _tex(R0)
                + r" \times "
                + _tex(dRsurR)
                + " = "
                + _tex(dR)
                + r"\ \Omega$"
            )
    else:
        rep.append(f"   Calcul vectorisé sur {eps.size} déformations.")
    return {"K": K, "eps": eps, "dRsurR": dRsurR, "R0": R0, "dR": dR, "report": rep, "latex": lat}


def gaugeStrain(K: float, dRsurR) -> np.ndarray:
    """Déformation mesurée par une jauge : ε = (ΔR/R)/K (loi de Bridgman inversée).

    Entrées : K (facteur de jauge, ≠ 0), dRsurR (variation relative de résistance, scalaire ou tableau).
    Sortie : np.ndarray de déformations, de même forme que dRsurR.
    """
    K = _nonNul(K, "K")
    return _tableau(dRsurR, "dRsurR") / K


def wheatstone(config: str, K: float, Vin: float, eps) -> dict:
    """Tension de sortie d'un pont de Wheatstone équipé de jauges (quart, demi, complet).

    Entrées : config ('quart', 'demi' ou 'complet') ; K (facteur de jauge) ; Vin (V, > 0) ; eps (déformations des
    jauges actives : 1 à 4 valeurs, les jauges inactives doivent être nulles).
    Sorties : dict avec config, K, Vin, eps (4 valeurs), nActive, Vout = Vin·K/4·(ε1 − ε2 + ε3 − ε4) (V),
    VoutExact (V, formule des résistances), linearityError (sans dimension, NaN si VoutExact = 0), epsIndicated
    (= 4·Vout/(K·Vin)), bridgeFactor (1, 2 ou 4), effectiveFactor (= epsIndicated/ε1, NaN si ε1 = 0),
    epsMeasured (= epsIndicated/bridgeFactor), report, latex.
    """
    cfg, nAct, nFac = _montage(config)
    K = _nonNul(K, "K")
    Vin = _positif(Vin, "Vin")
    if not _reelFini(eps) or not _estVecteur(eps):
        raise _erreur("badInput", "eps doit être un vecteur numérique réel et fini (1 à 4 déformations).")
    e = np.asarray(eps, dtype=float).ravel()
    if e.size > 4:
        raise _erreur("badInput", "Un pont de Wheatstone comporte au plus 4 jauges (eps de 1 à 4 composantes).")
    if e.size < nAct:
        raise _erreur("badInput", f"Le montage « {cfg} » nécessite {nAct} déformation(s) de jauges actives.")
    e4 = np.zeros(4)
    e4[: e.size] = e
    if np.any(e4[nAct:] != 0):
        raise _erreur(
            "badInput",
            f"Montage « {cfg} » : seules les {nAct} première(s) jauge(s) sont actives "
            "(les autres doivent être nulles).",
        )
    comb = e4[0] - e4[1] + e4[2] - e4[3]
    Vout = Vin * K / 4 * comb
    # Formule exacte R1/(R1+R2) − R4/(R3+R4) = (R1·R3 − R2·R4)/((R1+R2)(R3+R4)), Ri = R(1 + xi), forme développée
    x = K * e4
    VoutExact = Vin * (x[0] - x[1] + x[2] - x[3] + x[0] * x[2] - x[1] * x[3]) / ((2 + x[0] + x[1]) * (2 + x[2] + x[3]))
    linErr = (Vout - VoutExact) / VoutExact if VoutExact != 0 else math.nan
    epsInd = 4 * Vout / (K * Vin)
    effF = epsInd / e4[0] if e4[0] != 0 else math.nan
    epsMes = epsInd / nFac

    rep = [
        f"Pont de Wheatstone, montage « {cfg} » ({nAct} jauge(s) active(s)) : K = {_fmt(K)} ; Vin = {_fmt(Vin)} V",
        f"   Déformations ε1..ε4 = {_vecTxt(e4 * 1e6, 6)} µdéf",
        f"   Vout = Vin·K/4·(ε1 − ε2 + ε3 − ε4) = {_fmt(Vout * 1e3)} mV (linéarisé)",
        f"   Vout exact = Vin·(R1/(R1+R2) − R4/(R3+R4)) = {_fmt(VoutExact * 1e3)} mV ; "
        f"erreur de linéarisation = {_fmt(linErr * 100)} %",
        f"   Déformation indiquée 4·Vout/(K·Vin) = {_fmt(epsInd * 1e6)} µdéf ; facteur de pont nominal = {nFac} "
        f"→ ε mesurée = {_fmt(epsMes * 1e6)} µdéf",
        "Jauges opposées (1-3, 2-4) : effets additionnés ; jauges adjacentes (1-2, 3-4) : effets soustraits "
        "(compensation thermique).",
    ]
    lat = [
        r"$V_{out} = \frac{V_{in}\,K}{4}(\varepsilon_1 - \varepsilon_2 + \varepsilon_3 - \varepsilon_4) = "
        + _tex(Vout * 1e3)
        + r"\ \mathrm{mV}$",
        r"$V_{out}^{exact} = V_{in}\left(\frac{R_1}{R_1+R_2} - \frac{R_4}{R_3+R_4}\right) = "
        + _tex(VoutExact * 1e3)
        + r"\ \mathrm{mV}$",
        r"$\varepsilon_{ind} = \frac{4\,V_{out}}{K\,V_{in}} = "
        + _tex(epsInd * 1e6)
        + r"\ \mu\mathrm{def},\ \ \varepsilon = \frac{\varepsilon_{ind}}{"
        + str(nFac)
        + "} = "
        + _tex(epsMes * 1e6)
        + r"\ \mu\mathrm{def}$",
    ]
    return {
        "config": cfg,
        "K": K,
        "Vin": Vin,
        "eps": e4,
        "nActive": nAct,
        "Vout": Vout,
        "VoutExact": VoutExact,
        "linearityError": linErr,
        "epsIndicated": epsInd,
        "bridgeFactor": nFac,
        "effectiveFactor": effF,
        "epsMeasured": epsMes,
        "report": rep,
        "latex": lat,
    }


def bridgeStrain(config: str, K: float, Vin: float, Vout, factor: float | None = None) -> np.ndarray:
    """Déformation déduite de la tension de sortie d'un pont (réciproque de wheatstone).

    Entrées : config ('quart', 'demi', 'complet') ; K ; Vin (V, > 0) ; Vout (V, scalaire ou tableau) ;
    factor (facteur de pont, défaut 1, 2 ou 4 selon le montage ; par exemple 1 + ν pour un demi-pont « Poisson »).
    Sortie : np.ndarray, eps = 4·Vout/(K·Vin)/factor.
    """
    _, _, nFac = _montage(config)
    K = _nonNul(K, "K")
    Vin = _positif(Vin, "Vin")
    Vout = _tableau(Vout, "Vout")
    factor = nFac if factor is None else _nonNul(factor, "factor")
    return 4 * Vout / (K * Vin) / factor


# -------------------------------------------------------------------------------------------------
# Rosettes
# -------------------------------------------------------------------------------------------------
def _rosetteCore(exx, eyy, exy, E, nu, lectures, angles, titre: str) -> dict:
    """Exploitation commune des rosettes : déformations principales, contraintes planes et cercle de Mohr.

    Entrées : exx, eyy, exy (sans dimension, exy = γxy/2), E et nu (Pa, sans dimension, ou None), lectures
    (jauges), angles (degrés), titre (première ligne du rapport). Sortie : dict des champs de rosette45.
    """
    hasMat = E is not None and nu is not None
    if hasMat:
        _verifierMateriau(E, nu)
    dE = (exx + eyy) / 2
    rhoE = math.hypot((exx - eyy) / 2, exy)
    epsI = dE + rhoE
    epsII = dE - rhoE
    thetaP = 0.5 * math.atan2(2 * exy, exx - eyy)
    gammaMax = 2 * rhoE
    th = np.asarray(angles, dtype=float) * math.pi / 180
    recalcul = dE + (exx - eyy) / 2 * np.cos(2 * th) + exy * np.sin(2 * th)
    checkResidual = float(np.max(np.abs(recalcul - lectures)))
    r = {
        "readings": lectures,
        "anglesDeg": np.asarray(angles, dtype=float),
        "exx": exx,
        "eyy": eyy,
        "exy": exy,
        "gxy": 2 * exy,
        "epsI": epsI,
        "epsII": epsII,
        "thetaP": thetaP,
        "gammaMax": gammaMax,
        "checkResidual": checkResidual,
    }
    if hasMat:
        k = E / (1 - nu**2)
        G = E / (2 * (1 + nu))
        sxx = k * (exx + nu * eyy)
        syy = k * (eyy + nu * exx)
        sxy = G * 2 * exy
        sI = k * (epsI + nu * epsII)
        sII = k * (epsII + nu * epsI)
        r.update(
            ezz=-nu / (1 - nu) * (exx + eyy),
            sxx=sxx,
            syy=syy,
            sxy=sxy,
            sigmaI=sI,
            sigmaII=sII,
            tauMax2D=(sI - sII) / 2,
            principal3D=np.sort([sI, sII, 0.0])[::-1],
            sigmaVM=math.sqrt(sI**2 - sI * sII + sII**2),
            sigmaTresca=max(abs(sI), abs(sII), abs(sI - sII)),
        )
        cS = (sI + sII) / 2
        rS = (sI - sII) / 2
    else:
        r.update(
            ezz=math.nan,
            sxx=math.nan,
            syy=math.nan,
            sxy=math.nan,
            sigmaI=math.nan,
            sigmaII=math.nan,
            tauMax2D=math.nan,
            principal3D=np.full(3, math.nan),
            sigmaVM=math.nan,
            sigmaTresca=math.nan,
        )
        cS = rS = math.nan
    r["mohr"] = {"center": dE, "radius": rhoE, "centerStress": cS, "radiusStress": rS}
    r["strain2D"] = plane2DStrain(exx, eyy, exy, thetaP)
    r["stress2D"] = plane2D(r["sxx"], r["syy"], r["sxy"], thetaP) if hasMat else None

    sc = _echelle(exx, eyy, exy)
    rep = [
        titre,
        f"   Lectures : {_vecTxt(lectures * 1e6, 6)} µdéf aux angles {_vecTxt(angles, 4)}°",
        f"   εxx = {_fmt(_umdef(exx, sc))} µdéf ; εyy = {_fmt(_umdef(eyy, sc))} µdéf ; "
        f"εxy = {_fmt(_umdef(exy, sc))} µdéf ; γxy = {_fmt(_umdef(2 * exy, sc))} µdéf",
        f"   Vérification : écart max entre lectures et ε(θk) recalculées = {checkResidual:.2e}",
        f"Déformations principales : εI = {_fmt(_umdef(epsI, sc))} µdéf ; εII = {_fmt(_umdef(epsII, sc))} µdéf ; "
        f"θP = {_fmt(thetaP * 180 / math.pi)}° (direction de εI depuis x)",
        f"Cercle de Mohr des déformations : centre = {_fmt(_umdef(dE, sc))} µdéf ; "
        f"rayon = {_fmt(_umdef(rhoE, sc))} µdéf ; γmax = {_fmt(_umdef(gammaMax, sc))} µdéf",
    ]
    lat = [
        r"$\varepsilon_{I,II} = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} \pm \sqrt{\left(\frac{\varepsilon_{xx}"
        r"-\varepsilon_{yy}}{2}\right)^2 + \varepsilon_{xy}^2} = "
        + _tex(_umdef(dE, sc))
        + r" \pm "
        + _tex(_umdef(rhoE, sc))
        + r"\ \mu\mathrm{def}$",
        r"$\varepsilon_I = "
        + _tex(_umdef(epsI, sc))
        + r",\ \ \varepsilon_{II} = "
        + _tex(_umdef(epsII, sc))
        + r"\ \mu\mathrm{def},\ \ \theta_P = \frac{1}{2}\mathrm{atan2}(2\varepsilon_{xy},\ \varepsilon_{xx}-"
        r"\varepsilon_{yy}) = " + _tex(thetaP * 180 / math.pi) + r"^\circ$",
    ]
    if hasMat:
        sVM = r["sigmaVM"]
        rep += [
            f"Contraintes planes (E = {_fmt(E / 1e9)} GPa ; ν = {_fmt(nu)}) :",
            f"   σxx = E/(1−ν²)·(εxx + ν·εyy) = {_fmt(r['sxx'] / 1e6)} MPa ; "
            f"σyy = E/(1−ν²)·(εyy + ν·εxx) = {_fmt(r['syy'] / 1e6)} MPa ; "
            f"σxy = E/(1+ν)·εxy = {_fmt(r['sxy'] / 1e6)} MPa",
            f"   σI = E/(1−ν²)·(εI + ν·εII) = {_fmt(sI / 1e6)} MPa ; "
            f"σII = E/(1−ν²)·(εII + ν·εI) = {_fmt(sII / 1e6)} MPa ; "
            f"τmax plan = {_fmt(r['tauMax2D'] / 1e6)} MPa",
            f"   εzz = −ν/(1−ν)·(εxx + εyy) = {_fmt(r['ezz'] * 1e6)} µdéf ; σVM = √(σI² − σI·σII + σII²) = "
            f"{_fmt(sVM / 1e6)} MPa ; σeq Tresca = {_fmt(r['sigmaTresca'] / 1e6)} MPa",
        ]
        lat += [
            r"$\sigma_{xx} = \frac{E}{1-\nu^2}(\varepsilon_{xx} + \nu\,\varepsilon_{yy}) = "
            + _tex(r["sxx"] / 1e6)
            + r",\ \ \sigma_{yy} = \frac{E}{1-\nu^2}(\varepsilon_{yy} + \nu\,\varepsilon_{xx}) = "
            + _tex(r["syy"] / 1e6)
            + r"\ \mathrm{MPa}$",
            r"$\sigma_{xy} = \frac{E}{1+\nu}\varepsilon_{xy} = " + _tex(r["sxy"] / 1e6) + r"\ \mathrm{MPa}$",
            r"$\sigma_I = \frac{E}{1-\nu^2}(\varepsilon_I + \nu\,\varepsilon_{II}) = "
            + _tex(sI / 1e6)
            + r",\ \ \sigma_{II} = \frac{E}{1-\nu^2}(\varepsilon_{II} + \nu\,\varepsilon_I) = "
            + _tex(sII / 1e6)
            + r"\ \mathrm{MPa}$",
            r"$\sigma_{VM} = \sqrt{\sigma_I^2 - \sigma_I\sigma_{II} + \sigma_{II}^2} = "
            + _tex(sVM / 1e6)
            + r"\ \mathrm{MPa}$",
        ]
    else:
        rep.append("Matériau (E, ν) non fourni : contraintes non calculées.")
    r["report"] = rep
    r["latex"] = lat
    return r


def rosette45(e1: float, e2: float, e3: float, E: float | None = None, nu: float | None = None) -> dict:
    """Dépouillement d'une rosette rectangulaire (jauges à 0°, 90° et 45°).

    Entrées : e1 (jauge à 0°, selon x), e2 (jauge à 90°, selon y), e3 (jauge à 45°), déformations sans dimension ;
    E (Pa) et nu optionnels (sans eux, les contraintes valent NaN).
    Convention du cours : εxx = ε1, εyy = ε2, εxy = γxy/2 = ε3 − (ε1 + ε2)/2.
    Sortie : dict avec readings, anglesDeg, exx, eyy, exy, gxy, epsI, epsII, thetaP (rad), gammaMax, checkResidual,
    ezz, sxx, syy, sxy (Pa), sigmaI, sigmaII, tauMax2D, principal3D, sigmaVM, sigmaTresca (Pa), mohr, strain2D,
    stress2D (None sans matériau), report, latex.
    """
    e1 = _scalaire(e1, "e1")
    e2 = _scalaire(e2, "e2")
    e3 = _scalaire(e3, "e3")
    exx = e1
    eyy = e2
    exy = e3 - (e1 + e2) / 2
    r = _rosetteCore(
        exx,
        eyy,
        exy,
        E,
        nu,
        np.array([e1, e2, e3]),
        [0.0, 90.0, 45.0],
        "Rosette rectangulaire à 45° : jauge 1 à 0° (x), jauge 2 à 90° (y), jauge 3 à 45°",
    )
    lat = [
        r"$\varepsilon_{xx} = \varepsilon_1 = "
        + _tex(exx * 1e6)
        + r",\ \ \varepsilon_{yy} = \varepsilon_2 = "
        + _tex(eyy * 1e6)
        + r"\ \ (\mu\mathrm{def})$",
        r"$\varepsilon_{xy} = \frac{\gamma_{xy}}{2} = \varepsilon_3 - \frac{\varepsilon_1+\varepsilon_2}{2} = "
        + _tex(exy * 1e6)
        + r"\ \mu\mathrm{def}$",
    ]
    r["latex"] = lat + r["latex"]
    r["report"] = [
        r["report"][0],
        "   Formules du cours : εxx = ε1 ; εyy = ε2 ; εxy = γxy/2 = ε3 − (ε1 + ε2)/2",
        *r["report"][1:],
    ]
    return r


def rosette60(e0: float, e60: float, e120: float, E: float | None = None, nu: float | None = None) -> dict:
    """Dépouillement d'une rosette delta (jauges à 0°, 60° et 120°).

    Entrées : e0, e60, e120 (déformations mesurées à 0°, 60°, 120° depuis x) ; E (Pa) et nu optionnels.
    Formules : εxx = ε0, εyy = (2(ε60 + ε120) − ε0)/3, εxy = (ε60 − ε120)/√3.
    Sortie : mêmes champs que rosette45 (readings = [e0 e60 e120], anglesDeg = [0 60 120]).
    """
    e0 = _scalaire(e0, "e0")
    e60 = _scalaire(e60, "e60")
    e120 = _scalaire(e120, "e120")
    exx = e0
    eyy = (2 * (e60 + e120) - e0) / 3
    exy = (e60 - e120) / math.sqrt(3)
    r = _rosetteCore(
        exx,
        eyy,
        exy,
        E,
        nu,
        np.array([e0, e60, e120]),
        [0.0, 60.0, 120.0],
        "Rosette delta à 60° : jauges à 0° (x), 60° et 120°",
    )
    lat = [
        r"$\varepsilon_{xx} = \varepsilon_0 = " + _tex(exx * 1e6) + r",\ \ \varepsilon_{yy} = \frac{2(\varepsilon_{60}"
        r"+\varepsilon_{120}) - \varepsilon_0}{3} = " + _tex(eyy * 1e6) + r"\ \ (\mu\mathrm{def})$",
        r"$\varepsilon_{xy} = \frac{\gamma_{xy}}{2} = \frac{\varepsilon_{60} - \varepsilon_{120}}{\sqrt{3}} = "
        + _tex(exy * 1e6)
        + r"\ \mu\mathrm{def}$",
    ]
    r["latex"] = lat + r["latex"]
    r["report"] = [
        r["report"][0],
        "   Formules : εxx = ε0 ; εyy = (2(ε60 + ε120) − ε0)/3 ; εxy = γxy/2 = (ε60 − ε120)/√3",
        *r["report"][1:],
    ]
    return r
