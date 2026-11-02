"""Tests des services des onglets hors Poutres et des exemples d'école (E20).

Tests portés de tests/test_MecaStruct_App.m (testSectionRectangle, testTruss, testTractionValues,
testTorsionAndBuckling, testHookeAndGauges, testParseFunction, testRunAllExamples).
"""

import math

import pandas as pd
import pytest

from mecastruct.core import kt_mohr, solicitations
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.core.units import toSI
from mecastruct.services import compute, examples


@pytest.fixture(scope="module")
def dm():
    return DataManager()


def test_run_all_examples_ok(dm):
    """Toutes les étapes de runAllExamples réussissent (testRunAllExamples)."""
    res = examples.runAllExamples(dm)
    assert len(res) >= 20
    assert {nom: v["message"] for nom, v in res.items() if not v["ok"]} == {}


_CALCULS = [
    ("Sec", compute.computeSection),
    ("Tr", compute.computeTruss),
    ("Tra", compute.computeTraction),
    ("Cis", compute.computeShear),
    ("Cis", compute.computeKey),
    ("Cis", compute.computePin),
    ("Tor", compute.computeTorsion),
    ("Fle", compute.computeBending),
    ("Fla", compute.computeBuckling),
    ("Ten", compute.computeTensor),
    ("Hoo", compute.computeHooke),
    ("Jau", compute.computeGauges),
]


@pytest.mark.parametrize("tab, calcul", _CALCULS, ids=lambda x: getattr(x, "__name__", x))
def test_chaque_calcul_remplit_rapport_et_tableaux(dm, tab, calcul):
    """Chaque onglet donne un rapport, un texte d'état et des tableaux non vides (testRunAllExamples)."""
    out = calcul(examples.loadExample(tab), dm)
    assert out["status"]
    assert len(out["result"]["rapport"]) > 1
    assert out["tables"]
    for tb in out["tables"].values():
        assert isinstance(tb, pd.DataFrame) and not tb.empty


def test_traction_comme_le_moteur(dm):
    """Le service renvoie le résultat du moteur appelé directement avec les valeurs SI."""
    ex = examples.loadExample("Tra")
    p = {
        "N": toSI(ex["N"], "kN"),
        "S0": toSI(ex["S0"], "mm^2"),
        "L0": ex["L0"],
        "E": toSI(ex["E"], "GPa"),
        "nu": ex["nu"],
        "alpha": toSI(ex["alpha"], "1e-6/°C"),
        "dT": ex["dT"],
        "Kt": ex["Kt"],
        "Re": toSI(ex["Re"], "MPa"),
        "s": ex["s"],
    }
    assert compute.computeTraction(ex, dm)["result"]["sigmaNom"] == pytest.approx(
        solicitations.traction(p)["sigmaNom"], rel=1e-12
    )


def test_traction_allongement_et_barre_conique(dm):
    """ΔL = N L / (E S0) ; barre conique d 20 → 30 mm : ΔL = 4 N L / (π E d1 d2) (testTractionValues)."""
    ex = examples.loadExample("Tra")
    E = toSI(ex["E"], "GPa")
    N = toSI(ex["N"], "kN")
    S0 = toSI(ex["S0"], "mm^2")
    r = compute.computeTraction(ex, dm)["result"]
    assert r["dL"]["analytique"] == pytest.approx(N * 1 / (E * S0), rel=1e-12)
    assert r["dL"]["integrale"] == pytest.approx(N * 1 / (E * S0), rel=1e-6)
    r = compute.computeTraction(examples.loadExample("Tra", "variable"), dm)["result"]
    assert r["dL"]["integrale"] == pytest.approx(4 * N / (math.pi * E * 0.020 * 0.030), rel=1e-6)
    assert r["dL"]["energetique"] == pytest.approx(4 * N / (math.pi * E * 0.020 * 0.030), rel=1e-6)


def test_section_rectangle(dm):
    """Section 100 × 200 mm : S, Iz, Iy, τmax de Jourawski et colonne « Analytique » (testSectionRectangle)."""
    S = examples.loadExample("Sec")
    S.update(type="rectangle", b=100.0, h=200.0)
    out = compute.computeSection(S, dm)
    r = out["result"]
    b, h = 0.1, 0.2
    assert r["P"]["S"] == pytest.approx(b * h, rel=1e-12)
    assert r["P"]["Iz"] == pytest.approx(b * h**3 / 12, rel=1e-9)
    assert r["P"]["Iy"] == pytest.approx(h * b**3 / 12, rel=1e-9)
    assert r["Pint"]["Iz"] == pytest.approx(b * h**3 / 12, rel=1e-9)
    assert r["jour"]["tauMax"] == pytest.approx(1.5 * 60e3 / (b * h), rel=1e-6)
    comp = out["tables"]["Comparaison des méthodes"]
    iz = comp.loc[comp["Grandeur"] == "Iz"].iloc[0]
    assert iz["Analytique"] == pytest.approx(b * h**3 / 12 * 1e12, rel=1e-9)
    assert iz["Intégrale"] == pytest.approx(b * h**3 / 12 * 1e12, rel=1e-9)


def test_treillis_isostatique(dm):
    """Treillis d'exemple : isostatique, réactions 40 kN en Ry et −5 kN en Rx, 7 barres (testTruss)."""
    out = compute.computeTruss(examples.loadExample("Tr"), dm)
    t = out["result"]["tsol"]
    assert t["isostatic"]
    assert t["reactions"][:, 1].sum() == pytest.approx(40e3, rel=1e-9)
    assert t["reactions"][:, 0].sum() == pytest.approx(-5e3, rel=1e-9)
    assert len(out["tables"]["Barres"]) == 7


def test_torsion_et_flambage(dm):
    """φ = Mt L /(G Ix), τmax = Kt Mt r /Ix, PE = π² E Imin / L'² (testTorsionAndBuckling)."""
    ex = examples.loadExample("Tor")
    G = toSI(ex["G"], "GPa")
    Ix = math.pi * 0.040**4 / 32
    r = compute.computeTorsion(ex, dm)["result"]
    assert r["phi"]["analytique"] == pytest.approx(500 * 1 / (G * Ix), rel=1e-12)
    assert r["tauMax"] == pytest.approx(500 * 0.020 / Ix, rel=1e-12)
    ex = examples.loadExample("Fla")
    b = compute.computeBuckling(ex, dm)["result"]["analysis"]
    Imin = min(toSI(ex["Iz"], "mm^4"), toSI(ex["Iy"], "mm^4"))
    assert b["PE"] == pytest.approx(math.pi**2 * toSI(ex["E"], "GPa") * Imin / 4**2, rel=1e-9)


def test_hooke_contraintes_planes_et_jauges(dm):
    """εxx = (σxx − ν σyy)/E en contraintes planes ; γxy de la rosette = 250 − (400 − 120)/2 µdéf."""
    ex = examples.loadExample("Hoo", "planeStress")
    r = compute.computeHooke(ex, dm)["result"]
    E = toSI(ex["E"], "GPa")
    assert r["exx"] == pytest.approx((100e6 - ex["nu"] * 50e6) / E, rel=1e-12)
    r = compute.computeGauges(examples.loadExample("Jau"), dm)["result"]
    assert r["rosette"]["exy"] == pytest.approx(250e-6 - (400e-6 - 120e-6) / 2, rel=1e-12)


def test_kt_comme_le_moteur():
    """computeKt renvoie la valeur de kt_mohr.evalKt pour l'abaque de l'exemple de la base."""
    out = compute.computeKt("arbre_epaulement_flexion", [0.1, 1.5])
    assert out["result"]["Kt"] == pytest.approx(kt_mohr.evalKt("arbre_epaulement_flexion", [0.1, 1.5]), rel=1e-12)
    assert out["result"]["rapport"][0].startswith("Kt = ")


@pytest.mark.parametrize("mode", examples.HOOKE_VARIANTS)
def test_hooke_matrice_par_mode(dm, mode):
    """Chaque loi de Hooke donne une table Résultats et une table Matrice (6 × 6 en 3D, 3 × 3 en plan)."""
    out = compute.computeHooke(examples.loadExample("Hoo", mode), dm)
    assert out["tables"]["Matrice"].shape == ((6, 6) if mode in ("iso3D", "ortho") else (3, 3))
    assert out["result"]["mode"] == mode


def test_parse_function_valeurs():
    """Expressions autorisées : puissance ^, constantes, fonctions usuelles (testParseFunction)."""
    f = compute.parseFunction("pi/4*(20 + 10*x)^2")
    x = [0.0, 0.5, 1.0]
    assert list(f(x)) == pytest.approx([math.pi / 4 * (20 + 10 * xi) ** 2 for xi in x], rel=1e-14)
    assert list(compute.parseFunction("1.5e2")([1, 2, 3])) == [150.0, 150.0, 150.0]
    g = compute.parseFunction("sqrt(x) + exp(-x/2)*cos(x)")
    assert g(4.0) == pytest.approx(2 + math.exp(-2) * math.cos(4), rel=1e-14)


@pytest.mark.parametrize(
    "expr",
    ["system('dir')", "exit", "x; delete(1)", "[x x]", "eval(x)", "@(x) x", "e", "x == 1", "", "sin(x", "x.real"],
)
def test_parse_function_refuse(expr):
    """Toute construction hors liste est refusée avec l'identifiant invalidExpression (testParseFunction)."""
    with pytest.raises(MecaStructError) as err:
        compute.parseFunction(expr)
    assert err.value.identifier == "MecaStruct:App:invalidExpression"


def test_beton_refuse_en_traction_et_flexion(dm):
    """Béton : vérification en traction et en flexion refusée (fck n'est pas une limite en traction)."""
    beton = "Béton C25/30 (EN 1992-1-1)"
    tra = {**examples.loadExample("Tra"), "mat": beton}
    with pytest.raises(MecaStructError, match="Béton : résistance en traction négligeable"):
        compute.computeTraction(tra, dm)
    compute.computeTraction({**tra, "N": -50.0}, dm)  # compression : calcul conservé
    with pytest.raises(MecaStructError, match="Béton : résistance en traction négligeable"):
        compute.computeBending({**examples.loadExample("Fle"), "mat": beton}, dm)


def test_section_variable_hors_domaine_refusee(dm):
    """S(x) négative sur [0, L0] : erreur invalidExpression, pas de calcul."""
    ex = examples.loadExample("Tra", "variable")
    ex["Sexpr"] = "-x"
    with pytest.raises(MecaStructError) as err:
        compute.computeTraction(ex, dm)
    assert err.value.identifier == "MecaStruct:App:invalidExpression"


def test_exemples_variantes_et_onglet_inconnu():
    """Variantes de poutre appliquées, onglet inconnu refusé (testCallbackErrorIsLogged)."""
    assert examples.loadExample("Beam", "console")["L"] == 3.0
    assert len(examples.loadExample("Beam", "console")["sup"]) == 1
    assert examples.loadExample("Beam", "tassement")["supx"][0]["name"] == "B"
    assert examples.loadExample("Beam", "inconnue")["L"] == 6.0  # variante inconnue : isostatique
    assert examples.exampleNames("Tra") == ["constante", "variable"]
    with pytest.raises(MecaStructError) as err:
        examples.loadExample("Inconnu")
    assert err.value.identifier == "MecaStruct:App:unknownTab"
