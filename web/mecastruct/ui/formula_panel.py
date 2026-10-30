"""Panneau « Formulaire rapide » de la barre latérale : fiche de formules de la page (port de buildFormulaPanel)."""

import streamlit as st

from mecastruct.core import data_manager

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


def formula_panel(key: str | None) -> None:
    """Sélecteur de fiche et formules de la clé `key`, dans la barre latérale ; rien si `key` vaut None."""
    if key is None:
        return
    cles = data_manager.formulaKeys()
    with st.sidebar:
        st.subheader("Formulaire rapide")
        choix = st.selectbox(
            "Fiche",
            cles,
            index=cles.index(key),
            format_func=lambda k: _LIBELLES.get(k, k),
            key=f"formule.{key}",
        )
        for fiche in data_manager.formulaSheet(choix):
            st.markdown(f"**{fiche['title']}**")
            st.latex(str(fiche["latex"]).strip().strip("$"))
            if fiche.get("vars"):
                st.caption(str(fiche["vars"]))
