"""Tests de l'export du dossier de validation en PDF et en Word (dossier_export)."""

import io

import pytest
from docx import Document

from mecastruct.core.data_manager import DataManager
from mecastruct.services import dossier_export as de
from mecastruct.services import machine_courses as mc
from mecastruct.services import machine_validation as mv
from mecastruct.services import validation_report as vr
from mecastruct.services.examples import loadExample


@pytest.fixture(scope="module")
def dossiers():
    """Un dossier de page de cours (sans diagramme) et un dossier de Traction (avec diagrammes Plotly)."""
    dm = DataManager()
    s = mc.defaultGearInput()
    cours = mv.generate("Engrenages", [("Engrènement", "gearMesh", s, mc.computeGearMesh(s, dm))], dm)
    t = loadExample("Tra")
    return {"cours": cours, "Tra": vr.generate("Tra", t, vr.recompute("Tra", t, dm), dm)}


@pytest.mark.parametrize("cle", ["cours", "Tra"])
def test_pdf(dossiers, cle):
    pdf = de.toPdf(dossiers[cle])
    assert pdf.startswith(b"%PDF") and len(pdf) > 10_000


@pytest.mark.parametrize("cle", ["cours", "Tra"])
def test_word(dossiers, cle):
    """Le .docx se relit : titres des 8 parties, tableaux, formules en images, note pour les diagrammes."""
    doc = Document(io.BytesIO(de.toDocx(dossiers[cle])))
    textes = [p.text for p in doc.paragraphs]
    for _, titre in vr._SECTIONS:
        assert titre in textes
    assert len(doc.tables) >= 5 and len(doc.inline_shapes) >= 5
    assert (de._NOTE_FIG in textes) == (cle == "Tra")
    assert not any("MathJax" in t and "n'a pas pu" in t for t in textes)  # avertissement caché du HTML non repris


def test_export_garde_le_html_et_choisit_le_format(dossiers):
    html = dossiers["cours"]
    assert de.export(html, "HTML") is html
    assert de.export(html, "PDF").startswith(b"%PDF") and de.export(html, "Word").startswith(b"PK")
    assert set(de.FORMATS) == {"HTML", "PDF", "Word"}


def test_formules_reecrites_pour_mathtext():
    assert (
        de._compatible(r"x \le \tfrac12 + \underbrace{a+b}_{\text{t}} \leq y") == r"x \leq \frac{1}{2} + {a+b} \leq y"
    )
    assert de._image(r"\frac{a}{b} \leq \sqrt{x}") is not None
    assert de._image(r"\begin{array}{cc} 1 & 2 \end{array}") is None  # matrice : reste en LaTeX brut


def test_formule_trop_large_coupee_avant_chaque_egal():
    assert de._morceaux(r"a = \left( b = c \right) = d_{x=1}") == ["a", r"= \left( b = c \right)", "= d_{x=1}"]
    longue = " + ".join(["123.456"] * 12)
    assert len(de._dessins(f"M = {longue} = 5", 100)) == 3
    assert all(w <= 100 for _, w, _ in de._dessins(f"M = {longue} = 5", 100))
