"""Page « Références » : normes citées par l'application, sans texte de norme ni lien Drive."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGE = str(Path(__file__).resolve().parents[1] / "app_pages" / "references.py")


def _textes(at: AppTest) -> str:
    return " | ".join(e.value for e in [*at.markdown, *at.caption])


def test_la_page_liste_l_eurocode_3_et_les_normes_citees():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception
    texte = _textes(at)
    for numero in ("NF EN 1993-1-1", "EN 1993-1-5", "EN 338", "EN 1992-1-1"):
        assert numero in texte
    assert texte.count("Dans l'application :") == 6  # un rôle par norme


def test_normes_non_utilisees_et_liens_prives_absents():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    texte = _textes(at)
    for interdit in ("B5560", "ISO 527", "drive.google", "docs.google"):
        assert interdit not in texte


def test_la_page_est_dans_le_groupe_outils_de_la_navigation():
    source = (Path(PAGE).parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
    outils = source[source.index("Outils") :]
    assert "references.py" in outils
