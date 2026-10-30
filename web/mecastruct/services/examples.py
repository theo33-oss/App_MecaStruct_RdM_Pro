"""Exemples d'école par onglet (port de loadExample, loadBeamExample et runAllExamples de MecaStruct_App.m).

Les valeurs par défaut de chaque onglet (compute.defaultXxxInput) sont celles que MATLAB charge au démarrage ; les
variantes ne changent que ce qui les distingue. Les onglets « Beam » reprennent les saisies de E18 (defaultBeamInput).
"""

from mecastruct.core import geometry
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import beam_design, beam_services, compute

BEAM_VARIANTS = ("isostatique", "hyperstatique", "console", "deuxtravees", "gerber", "tassement")
TRACTION_VARIANTS = ("constante", "variable")
HOOKE_VARIANTS = ("iso3D", "planeStress", "planeStrain", "ortho")

_DEFAUTS = {
    "Sec": compute.defaultSectionInput,
    "Tr": compute.defaultTrussInput,
    "Cis": compute.defaultShearInput,
    "Tor": compute.defaultTorsionInput,
    "Fle": compute.defaultBendingInput,
    "Fla": compute.defaultBucklingInput,
    "Ten": compute.defaultTensorInput,
    "Jau": compute.defaultGaugesInput,
}


def exampleNames(tab: str) -> list[str]:
    """Variantes d'exemple d'un onglet (liste vide si l'onglet n'a qu'un exemple)."""
    return {"Beam": list(BEAM_VARIANTS), "Tra": list(TRACTION_VARIANTS), "Hoo": list(HOOKE_VARIANTS)}.get(tab, [])


def _appui(pos: float, type_: str, name: str) -> dict:
    """Appui de poutre : position (m), type, nom."""
    return {"pos": pos, "type": type_, "name": name}


def _chargeQ(L: float) -> dict:
    """Charge répartie permanente q = −10 kN/m sur toute la poutre (dl de l'exemple)."""
    return {"a": 0.0, "b": L, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}


def _beamExample(variant: str) -> dict:
    """loadBeamExample : saisie de la poutre d'exemple (IPE 300, S235), variante donnée."""
    B = beam_services.defaultBeamInput()
    B["shear"] = True
    B["section"] = geometry.fromProfile(DataManager().getProfile("IPE", "IPE 300"))
    B["secTabulated"] = True  # l'exemple garde les valeurs du catalogue, comme BeamUsesSection = false
    if variant == "hyperstatique":
        B.update(
            L=5.0,
            sup=[_appui(0.0, "encastrement", "A"), _appui(5.0, "appui_simple", "B")],
            pl=[],
            dl=[_chargeQ(5.0)],
        )
    elif variant == "console":
        B.update(
            L=3.0,
            sup=[_appui(0.0, "encastrement", "A")],
            pl=[{"pos": 3.0, "Fx": 0.0, "Fy": -10.0, "Fz": 0.0, "name": "F", "case": "Q"}],
            dl=[],
        )
    elif variant in ("deuxtravees", "gerber", "tassement"):
        B.update(
            L=8.0,
            sup=[_appui(0.0, "pivot", "A"), _appui(4.0, "appui_simple", "B"), _appui(8.0, "appui_simple", "C")],
            pl=[],
            dl=[_chargeQ(8.0)],
        )
        if variant == "gerber":
            B["hg"] = [{"pos": 2.0, "name": "R1"}]
        if variant == "tassement":
            B["supx"] = [{"name": "B", "k": 0.0, "dx": 0.0, "dy": -10.0, "dz": 0.0}]
    return B


def loadExample(tab: str, variant: str | None = None) -> dict:
    """Saisie de l'exemple d'école d'un onglet (sans calcul).

    Entrées : `tab` ∈ "Sec", "Beam", "Tr", "Tra", "Cis", "Tor", "Fle", "Fla", "Ten", "Hoo", "Jau" ; `variant` (voir
    exampleNames), ignorée si inconnue ou sans objet. Erreur : MecaStruct:App:unknownTab.
    """
    if tab == "Beam":
        return _beamExample(variant if variant in BEAM_VARIANTS else "isostatique")
    if tab == "Tra":
        return {**compute.defaultTractionInput(), "varS": variant == "variable"}
    if tab == "Hoo":
        saisie = compute.defaultHookeInput()
        if variant in HOOKE_VARIANTS:
            saisie["mode"] = variant
        return saisie
    if tab not in _DEFAUTS:
        raise MecaStructError("MecaStruct:App:unknownTab", f"Onglet inconnu : « {tab} ».")
    return _DEFAUTS[tab]()


def _transfertSection(dm: DataManager) -> dict:
    """useSectionForBeam sur l'exemple de Sections : la section et le matériau passent dans la saisie Poutres."""
    S = loadExample("Sec")
    r = compute.computeSection(S, dm)["result"]
    return beam_design.sectionToBeamInput(loadExample("Beam"), r["sec"], r["P"], dm.getMaterial(S["mat"]))


def runAllExamples(dm: DataManager) -> dict:
    """Charge un exemple par onglet et calcule tout ; une étape en erreur n'arrête pas les autres.

    Sortie : {étape: {"ok": bool, "message": str}}, « OK » ou le message d'erreur. Les étapes de poutre suivent
    l'ordre de MATLAB : la poutre des étapes suivantes est celle de la dernière étape « Poutres » (tassement).
    """
    beam = loadExample("Beam", "tassement")
    etapes = [
        ("BaseDeDonnees", lambda: compute.computeKt("arbre_epaulement_flexion", [0.1, 1.5])),
        ("Sections", lambda: compute.computeSection(loadExample("Sec"), dm)),
        ("TransfertSection", lambda: _transfertSection(dm)),
        ("Poutres", lambda: beam_services.computeBeam(loadExample("Beam", "isostatique"), dm)),
        ("PoutreHyperstatique", lambda: beam_services.computeBeam(loadExample("Beam", "hyperstatique"), dm)),
        ("PoutreConsole", lambda: beam_services.computeBeam(loadExample("Beam", "console"), dm)),
        ("PoutreDeuxTravees", lambda: beam_services.computeBeam(loadExample("Beam", "deuxtravees"), dm)),
        ("PoutreGerber", lambda: beam_services.computeBeam(loadExample("Beam", "gerber"), dm)),
        ("PoutreTassement", lambda: beam_services.computeBeam(beam, dm)),
        ("CombinaisonsPoutre", lambda: beam_services.computeCombinations(beam, dm)),
        ("EurocodePoutre", lambda: beam_design.checkEurocode(beam, dm)),
        ("FatiguePoutre", lambda: beam_design.checkFatigue(beam, dm)),
        ("DimensionnementPoutre", lambda: beam_design.findLightestProfile(beam, dm, beam["pfam"], beam["pdef"])),
        ("ChargeMobile", lambda: beam_design.computeMovingLoad(beam, dm)),
        ("EnvoiTenseur", lambda: beam_design.sendToTensor(beam_services.computeBeam(beam, dm))),
        ("Treillis", lambda: compute.computeTruss(loadExample("Tr"), dm)),
        ("Traction", lambda: compute.computeTraction(loadExample("Tra"), dm)),
        ("TractionSectionVariable", lambda: compute.computeTraction(loadExample("Tra", "variable"), dm)),
        ("Cisaillement", lambda: compute.computeShear(loadExample("Cis"), dm)),
        ("Clavette", lambda: compute.computeKey(loadExample("Cis"), dm)),
        ("Goupille", lambda: compute.computePin(loadExample("Cis"), dm)),
        ("Torsion", lambda: compute.computeTorsion(loadExample("Tor"), dm)),
        ("Flexion", lambda: compute.computeBending(loadExample("Fle"), dm)),
        ("Flambage", lambda: compute.computeBuckling(loadExample("Fla"), dm)),
        ("Tenseurs", lambda: compute.computeTensor(loadExample("Ten"), dm)),
        ("HookeIsotrope3D", lambda: compute.computeHooke(loadExample("Hoo", "iso3D"), dm)),
        ("HookeContraintesPlanes", lambda: compute.computeHooke(loadExample("Hoo", "planeStress"), dm)),
        ("HookeDeformationsPlanes", lambda: compute.computeHooke(loadExample("Hoo", "planeStrain"), dm)),
        ("HookeOrthotrope", lambda: compute.computeHooke(loadExample("Hoo", "ortho"), dm)),
        ("Jauges", lambda: compute.computeGauges(loadExample("Jau"), dm)),
    ]
    sortie = {}
    for nom, etape in etapes:
        try:
            etape()
            sortie[nom] = {"ok": True, "message": "OK"}
        except Exception as err:  # une étape en échec ne doit pas arrêter les autres (catch de MATLAB)
            sortie[nom] = {"ok": False, "message": str(err)}
    return sortie
