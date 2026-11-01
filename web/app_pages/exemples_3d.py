"""Cas d'école du mode « Ossature 3D » en plus de ceux du moteur frame3d : hangar, toit, treillis, pylône, passerelle.

Données au format de frame3d.solveFrame3D (SI : m, N, Pa). Aucun import de streamlit : testables seuls.
"""

import math

from mecastruct.core import frame3d

EXPLICATIONS = {
    "Console": "Poutre IPE 200 de 2 m encastrée à un bout, libre à l'autre, force de 10 kN vers le bas en bout : "
    "le cas de base, flèche P·L³/(3·E·I).",
    "Potence en L": "Poteau tube vertical de 3 m encastré au sol, bras horizontal de 1,5 m : la charge en bout fait "
    "fléchir le bras et tordre le poteau.",
    "Portique 3D": "Quatre poteaux HEB 200 encastrés et quatre poutres IPE 200 en cadre à 3 m, charge répartie sur "
    "les poutres et poussée horizontale.",
    "Table 4 pieds": "Plateau en cadre rectangulaire sur 4 pieds ronds posés sur rotules, charges sur les coins et "
    "poussée latérale : les pieds travaillent en flexion.",
    "Hangar contreventé": "3 portiques à deux pentes reliés par des pannes, croix de Saint-André (barres articulées) "
    "dans la première travée, neige et vent.",
    "Abri toit 4 pans": "Kiosque 6 m × 4 m : 4 poteaux, ceinture, arêtiers et faîtage d'un toit à quatre pentes "
    "sous la neige ; on voit la poussée des arêtiers sur la ceinture.",
    "Poutre treillis triangulaire": "Poutre légère de 9 m à section en triangle : 3 membrures en tube, cadres soudés, "
    "diagonales articulées. Beaucoup de raideur pour peu de matière.",
    "Pylône treillis": "Tour de 12 m à base triangulaire qui se rétrécit vers le haut : jambes en tube, ceintures "
    "soudées, diagonales articulées ; vent et poids d'une antenne.",
    "Passerelle Warren": "Passerelle de 12 m : deux poutres Warren reliées par des traverses et des entretoises, "
    "charge de foule sur le tablier.",
}


def _materiau(dm) -> dict:
    acier = dm.getMaterial("S235")
    return {"E": acier["E"], "G": acier["G"], "rho": acier["rho"]}


class _Ossature:
    """Petit outil d'écriture : nœuds et éléments numérotés à la suite, même matériau partout."""

    def __init__(self, dm):
        self.mat, self.noeuds, self.elements = _materiau(dm), [], []

    def noeud(self, i, x, y, z, appui="libre", **kw):
        self.noeuds.append({"id": i, "x": x, "y": y, "z": z, "appui": appui, **kw})

    def barre(self, ni, nj, sec, articulee=False) -> int:
        art = {"liaison_i": "articulee", "liaison_j": "articulee"} if articulee else {}
        self.elements.append({"id": len(self.elements) + 1, "ni": ni, "nj": nj, **self.mat, **sec, **art})
        return len(self.elements)

    def donnees(self, **charges) -> dict:
        return {"noeuds": self.noeuds, "elements": self.elements, "poids_propre": True, **charges}


def hangar(dm) -> dict:
    """Hangar 8 m × 10 m : 3 portiques à deux pentes (poteaux HEB 200, arbalétriers IPE 240), pannes IPE 160,
    croix de Saint-André en ronds de 20 mm articulés dans les deux long-pans de la première travée."""
    o = _Ossature(dm)
    poteau, arba, panne = (
        frame3d._profil(dm, "HEB", 200),
        frame3d._profil(dm, "IPE", 240),
        frame3d._profil(dm, "IPE", 160),
    )
    croix = frame3d.sectionRond(0.02)
    profil = [(0, 0), (0, 4), (4, 5.5), (8, 4), (8, 0)]  # pied gauche, rive, faîtage, rive, pied droit (x, z en m)
    for k in range(3):
        for i, (x, z) in enumerate(profil):
            o.noeud(10 * k + i + 1, x, 5.0 * k, z, "encastrement" if z == 0 else "libre")
    arbas = []
    for k in range(3):
        b = 10 * k
        o.barre(b + 1, b + 2, poteau), o.barre(b + 5, b + 4, poteau)
        arbas += [o.barre(b + 2, b + 3, arba), o.barre(b + 3, b + 4, arba)]
    for k in range(2):  # pannes de rive et de faîtage entre portiques voisins
        for i in (2, 3, 4):
            o.barre(10 * k + i, 10 * (k + 1) + i, panne)
    for pied, rive in ((1, 2), (5, 4)):  # croix de Saint-André dans les long-pans, première travée
        o.barre(pied, 10 + rive, croix, True), o.barre(10 + pied, rive, croix, True)
    return o.donnees(
        charges_reparties=[{"element": i, "qz": -6e3} for i in arbas],  # neige : 6 kN/m sur les arbalétriers
        charges_nodales=[{"noeud": 10 * k + 2, "Fx": 5e3} for k in range(3)],  # vent sur le long-pan gauche
    )


def abri_quatre_pans(dm) -> dict:
    """Kiosque 6 m × 4 m, poteaux tube 114,3 × 5 de 3 m, ceinture IPE 160, toit à quatre pans : faîtage de 2 m à
    4,5 m de haut, 4 arêtiers et 2 chevrons intermédiaires en tube 76,1 × 4 ; neige 1,5 kN/m sur le toit."""
    o = _Ossature(dm)
    poteau, ceinture, toit = (
        frame3d.sectionTube(0.1143, 0.005),
        frame3d._profil(dm, "IPE", 160),
        frame3d.sectionTube(0.0761, 0.004),
    )
    coins = [(0, 0), (6, 0), (6, 4), (0, 4)]
    for k, (x, y) in enumerate(coins):
        o.noeud(k + 1, x, y, 0, "encastrement")
        o.noeud(k + 11, x, y, 3)
        o.barre(k + 1, k + 11, poteau)
    o.noeud(21, 2, 2, 4.5), o.noeud(22, 4, 2, 4.5)  # extrémités du faîtage
    o.noeud(23, 3, 0, 3), o.noeud(24, 3, 4, 3)  # milieux des long-pans (pieds des chevrons)
    for ni, nj in ((11, 23), (23, 12), (12, 13), (13, 24), (24, 14), (14, 11)):  # ceinture
        o.barre(ni, nj, ceinture)
    toiture = [o.barre(21, 22, toit)]
    toiture += [o.barre(11, 21, toit), o.barre(14, 21, toit), o.barre(12, 22, toit), o.barre(13, 22, toit)]
    toiture += [o.barre(23, 21, toit), o.barre(23, 22, toit), o.barre(24, 21, toit), o.barre(24, 22, toit)]
    return o.donnees(charges_reparties=[{"element": i, "qz": -1.5e3} for i in toiture])


def poutre_triangulaire(dm) -> dict:
    """Poutre treillis de 9 m à section triangulaire (base 0,8 m, hauteur 0,7 m), 6 panneaux : membrures en tube
    60,3 × 4 continues, cadres de station soudés en tube 33,7 × 3, diagonales en ronds de 16 mm articulés ;
    appuis à rotule aux deux bouts. Les cadres soudés empêchent chaque membrure de tourner sur son axe."""
    o = _Ossature(dm)
    corde, cadre, treillis = (
        frame3d.sectionTube(0.0603, 0.004),
        frame3d.sectionTube(0.0337, 0.003),
        frame3d.sectionRond(0.016),
    )
    n, L, b, h = 6, 9.0, 0.8, 0.7
    for i in range(n + 1):
        x = L * i / n
        appui = "rotule" if i in (0, n) else "libre"
        o.noeud(100 + i, x, -b / 2, 0, appui), o.noeud(200 + i, x, b / 2, 0, appui), o.noeud(300 + i, x, 0, h)
    for i in range(n):
        for ligne in (100, 200, 300):
            o.barre(ligne + i, ligne + i + 1, corde)
    for i in range(n + 1):  # cadre triangulaire soudé de chaque station
        o.barre(100 + i, 200 + i, cadre), o.barre(200 + i, 300 + i, cadre), o.barre(300 + i, 100 + i, cadre)
    for i in range(n):  # diagonales en zigzag sur les trois faces
        a, c = (i, i + 1) if i % 2 == 0 else (i + 1, i)
        o.barre(100 + a, 200 + c, treillis, True)
        o.barre(100 + a, 300 + c, treillis, True), o.barre(200 + a, 300 + c, treillis, True)
    return o.donnees(charges_nodales=[{"noeud": 300 + i, "Fz": -2e3} for i in range(1, n)])


def pylone(dm) -> dict:
    """Pylône de 12 m, 6 niveaux, base en triangle de 2 m de côté réduite à 0,8 m en tête ; jambes tube 88,9 × 5,
    ceintures soudées en cornière équivalente (tube 42,4 × 3), diagonales en ronds de 20 mm articulés ; pieds à
    rotule ; vent 3 kN et antenne 5 kN en tête. Les ceintures soudées empêchent les jambes de tourner sur leur axe."""
    o = _Ossature(dm)
    jambe, ceinture, treillis = (
        frame3d.sectionTube(0.0889, 0.005),
        frame3d.sectionTube(0.0424, 0.003),
        frame3d.sectionRond(0.02),
    )
    niveaux, H = 6, 12.0
    for k in range(niveaux + 1):
        cote = 2.0 + (0.8 - 2.0) * k / niveaux
        r = cote / math.sqrt(3)  # rayon du cercle circonscrit au triangle
        for j in range(3):
            a = math.radians(90 + 120 * j)
            o.noeud(10 * k + j + 1, r * math.cos(a), r * math.sin(a), H * k / niveaux, "rotule" if k == 0 else "libre")
    for k in range(niveaux):
        for j in range(3):
            o.barre(10 * k + j + 1, 10 * (k + 1) + j + 1, jambe)
            o.barre(10 * (k + 1) + j + 1, 10 * (k + 1) + (j + 1) % 3 + 1, ceinture)
            bas, haut = (j, (j + 1) % 3) if k % 2 == 0 else ((j + 1) % 3, j)
            o.barre(10 * k + bas + 1, 10 * (k + 1) + haut + 1, treillis, True)  # diagonale de la face
    tete = [10 * niveaux + j + 1 for j in range(3)]
    return o.donnees(
        charges_nodales=[{"noeud": i, "Fx": 1e3, "Fz": -5e3 / 3} for i in tete],  # vent et antenne répartis
    )


def passerelle_warren(dm) -> dict:
    """Passerelle de 12 m, largeur 2 m, hauteur 1,5 m : deux poutres Warren (membrures tube 101,6 × 6, diagonales
    tube 60,3 × 4 soudées), traverses IPE 160 sous le tablier, entretoises hautes ; foule 5 kN/m² sur 2 m."""
    o = _Ossature(dm)
    membrure, diag, traverse = (
        frame3d.sectionTube(0.1016, 0.006),
        frame3d.sectionTube(0.0603, 0.004),
        frame3d._profil(dm, "IPE", 160),
    )
    n, L, B, H = 6, 12.0, 2.0, 1.5
    for c, y in enumerate((0.0, B)):
        for i in range(n + 1):
            o.noeud(100 * c + i, L * i / n, y, 0, "rotule" if i in (0, n) else "libre")
        for i in range(n):
            o.noeud(100 * c + 50 + i, L * (i + 0.5) / n, y, H)
    bas = []
    for c in (0, 100):
        bas += [o.barre(c + i, c + i + 1, membrure) for i in range(n)]
        for i in range(n - 1):
            o.barre(c + 50 + i, c + 51 + i, membrure)
        for i in range(n):
            o.barre(c + i, c + 50 + i, diag), o.barre(c + 50 + i, c + i + 1, diag)
    for i in range(n + 1):
        o.barre(i, 100 + i, traverse)
    for i in range(n):
        o.barre(50 + i, 150 + i, diag)  # entretoises hautes
    q = 5e3 * B / 2  # 5 kN/m² sur 2 m de large, moitié par poutre
    return o.donnees(charges_reparties=[{"element": i, "qz": -q} for i in bas])


AJOUTS = {
    "Hangar contreventé": hangar,
    "Abri toit 4 pans": abri_quatre_pans,
    "Poutre treillis triangulaire": poutre_triangulaire,
    "Pylône treillis": pylone,
    "Passerelle Warren": passerelle_warren,
}


def exemples(dm) -> dict[str, dict]:
    """Exemples du moteur frame3d, suivis des cas d'école de cette page."""
    return {**frame3d.exemples(), **{nom: f(dm) for nom, f in AJOUTS.items()}}
