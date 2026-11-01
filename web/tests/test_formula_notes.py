"""Explications courtes du formulaire rapide : chaque note vise une formule existante et tient sur 2 lignes."""

from mecastruct.core import data_manager
from mecastruct.core.utils import load_json

NOTES = load_json("formula_notes.json")["notes"]


def test_chaque_note_vise_un_titre_existant():
    titres = {f["title"] for k in data_manager.formulaKeys() for f in data_manager.formulaSheet(k)}
    assert set(NOTES) <= titres, sorted(set(NOTES) - titres)


def test_notes_courtes():
    # 120 caractères ≈ 2 lignes en petite police dans le panneau de 26rem
    trop_longues = {t: len(n) for t, n in NOTES.items() if len(n) > 120}
    assert not trop_longues


def test_menabrea_explique():
    assert "Théorème de Ménabréa" in NOTES and "Théorème de Castigliano" in NOTES
