"""Panneau « Formulaire rapide » (à droite, repliable) : fiche de formules de la page (port de buildFormulaPanel)."""

import streamlit as st

from mecastruct.core import data_manager
from mecastruct.core.utils import load_json
from mecastruct.ui import widgets

# Libellés des fiches (port de formulaLabel de MecaStruct_App.m)
_LIBELLES = {
    "materiaux": "Matériaux",
    "geometrie": "Géométrie des sections",
    "equilibre": "Équilibre (PFS)",
    "cohesion": "Torseur de cohésion",
    "treillis": "Treillis",
    "traction": "Traction / compression",
    "cisaillement": "Cisaillement",
    "matage": "Matage",
    "torsion": "Torsion",
    "flexion": "Flexion",
    "deformee": "Déformée",
    "energie": "Énergie",
    "mohr_integrales": "Intégrales de Mohr",
    "flambage": "Flambage",
    "tenseurs": "Tenseurs",
    "mohr_cercle": "Cercle de Mohr",
    "criteres": "Critères",
    "hooke": "Loi de Hooke",
    "extensometrie": "Extensométrie",
}


def _fiche(key: str, titre: bool = True) -> None:
    """Sélecteur de fiche et formules de la clé `key` (là où l'appelant se trouve : panneau ou tiroir)."""
    cles = data_manager.formulaKeys()
    if titre:
        st.subheader("Formulaire rapide")
    choix = st.selectbox(
        "Fiche",
        cles,
        index=cles.index(key),
        format_func=lambda k: _LIBELLES.get(k, k),
        key=f"formule.{key}",
    )
    notes = load_json("formula_notes.json")["notes"]
    for fiche in data_manager.formulaSheet(choix):
        st.markdown(f"**{fiche['title']}**")
        if fiche["title"] in notes:
            st.caption(f"*{notes[fiche['title']]}*")
        # le KaTeX de Streamlit ne connaît pas \mbox (fiches exportées de MATLAB) : \text est son équivalent
        st.latex(str(fiche["latex"]).strip().strip("$").replace(r"\mbox{", r"\text{"))
        if fiche.get("vars"):
            st.caption(str(fiche["vars"]))


@st.dialog("Formulaire rapide", width="large", position="right", icon=":material/function:")
def _tiroir(key: str) -> None:
    _fiche(key, titre=False)


def _css_panneau() -> str:
    """Style du panneau à droite : fixé sous l'en-tête, replié = simple barre ; déplié, il repousse la page à gauche.

    La page n'est repoussée que sur un écran large (1400 px et plus) ; sur un écran étroit, le panneau passe dessus.
    """
    fond, bord = ("#0E0B16", "#6E6590") if widgets._theme_sombre() else ("#FFFFFF", "#8E86AA")
    return (
        '[class*="st-key-formulaire_droite"] { position: fixed; top: 4rem; right: 1rem; z-index: 30; '
        f"width: 13rem; max-height: calc(100vh - 5rem); overflow-y: auto; background: {fond}; "
        f"border: 1px solid {bord}; border-radius: 0.5rem; }} "
        '[class*="st-key-formulaire_droite"]:has(details[open]) { width: 26rem; max-width: 92vw; } '
        # formule plus large que le panneau : barre de défilement au lieu d'une formule coupée
        '[class*="st-key-formulaire_droite"] .katex-display { overflow-x: auto; overflow-y: hidden; } '
        "@media (min-width: 1400px) { "
        '[data-testid="stMain"]:has([class*="st-key-formulaire_droite"] details[open]) '
        '[data-testid="stMainBlockContainer"] { padding-right: 28rem; } }'
    )


def formula_panel(key: str | None) -> None:
    """Formules de la clé `key` : panneau repliable fixé à droite, ou en mode compact derrière un bouton (tiroir).

    Rien si `key` vaut None. Replié, le panneau est une barre « Formulaire rapide » ; déplié, il garde la fiche
    visible à droite pendant qu'on saisit, et la page se décale pour ne rien cacher.
    """
    if key is None:
        return
    if widgets.is_compact():
        if st.button("Formulaire", key=f"formule.{key}.ouvrir", icon=":material/function:"):
            _tiroir(key)
        return
    st.sidebar.html("<style>" + _css_panneau() + "</style>")
    with st.container(key="formulaire_droite"):
        with st.expander("Formulaire rapide", expanded=False, icon=":material/function:"):
            _fiche(key, titre=False)
