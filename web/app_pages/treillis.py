"""Page « Treillis » : treillis articulé plan (efforts dans les barres, réactions, déplacements).

Port de l'onglet « Treillis » de MecaStruct_App.m (buildTrussTab, computeTruss). Le moteur et l'interface MATLAB sont
plans (2D) : la saisie 3D de la fiche n'est pas portée.
"""

import streamlit as st

from mecastruct.plots import other_plots
from mecastruct.services import compute
from mecastruct.ui import state, widgets
from mecastruct.ui.formula_panel import formula_panel

state.init()
dm = st.session_state["dm"]
saisie = state.saisie("Tr")


def _num(label: str) -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, format="%.5g", default=0.0)


def _noeud(label: str) -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, format="%d", step=1, min_value=1, default=1)


def _calcule() -> None:
    """Calcul du treillis avec la saisie courante ; le résultat est gardé pour l'affichage."""
    try:
        state.set_result("Tr", compute.computeTruss(saisie, dm))
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop("Tr", None)


def _saisie() -> None:
    widgets.choice_materiau("Tr", ["E"], dm)
    widgets.num("Tr", "E", "E", "GPa")
    widgets.num("Tr", "S", "S", "mm²", min_value=0.0)
    widgets.num("Tr", "scale", "Amplification déformée (0 = auto)", "", min_value=0.0)
    st.markdown("**Nœuds** (coordonnées en m)")
    widgets.table(
        "Tr",
        "nodes",
        {
            "name": st.column_config.TextColumn("Nom", default=""),
            "x": _num("x (m)"),
            "y": _num("y (m)"),
        },
    )
    st.markdown("**Barres** (numéros des nœuds, à partir de 1)")
    widgets.table(
        "Tr",
        "bars",
        {
            "i": _noeud("Nœud i"),
            "j": st.column_config.NumberColumn("Nœud j", format="%d", step=1, min_value=1, default=2),
        },
    )
    st.markdown("**Appuis** (ddl bloqués)")
    widgets.table(
        "Tr",
        "sup",
        {
            "node": _noeud("Nœud"),
            "bx": st.column_config.CheckboxColumn("Bloqué x", default=True),
            "by": st.column_config.CheckboxColumn("Bloqué y", default=True),
        },
    )
    st.markdown("**Charges nodales**")
    widgets.table(
        "Tr",
        "loads",
        {
            "node": _noeud("Nœud"),
            "Fx": _num("Fx (kN)"),
            "Fy": st.column_config.NumberColumn("Fy (kN)", format="%.5g", default=-10.0),
        },
    )


def _figure(res: dict | None):
    """Treillis dessiné : avec efforts si le calcul date de la saisie actuelle, sinon aperçu de la saisie."""
    if res is None or not state.is_current("Tr"):
        try:
            return other_plots.truss(compute._readTruss(saisie))
        except Exception as err:  # saisie incomplète : l'aperçu est seulement omis
            st.caption(f"Aperçu indisponible : {err}")
            return None
    r = res["result"]
    return other_plots.truss(r["truss"], r["tsol"], saisie["scale"] if saisie["scale"] > 0 else None)


def _resultats(res: dict) -> None:
    st.success(res["status"])
    t = res["tables"]
    onglets = st.tabs(["Barres", "Réactions", "Déplacements", "Rapport", "Formules"])
    with onglets[0]:
        st.dataframe(t["Barres"], hide_index=True)
    with onglets[1]:
        st.dataframe(t["Réactions"], hide_index=True)
    with onglets[2]:
        st.dataframe(t["Déplacements"], hide_index=True)
    with onglets[3]:
        widgets.report(res["result"]["rapport"])
    with onglets[4]:
        widgets.formulas(res["result"]["tsol"]["latex"])


st.title("Treillis")
formula_panel("treillis")

gauche, droite = widgets.zones("Tr")
with gauche:
    calcule = widgets.calc_button("Tr.calc")
    synthese = st.container()
    widgets.file_bar("Tr")
    widgets.example_picker("Tr")
    with st.expander("Matériau, section et nœuds", expanded=True):
        _saisie()
    if calcule:
        _calcule()
    widgets.synthese_resultat("Tr", synthese)

with droite:
    resultat = state.result("Tr")
    figure = _figure(resultat)
    if figure is not None:
        widgets.plot(figure)
    if resultat is None:
        st.caption(
            "Aperçu du treillis saisi, mis à jour à chaque modification. Cliquez sur « Calculer » pour les efforts."
        )
    elif not state.is_current("Tr"):
        st.caption(
            "Le dessin suit la saisie. Les efforts et les tableaux datent du dernier « Calculer » : "
            "cliquez dessus pour les actualiser."
        )
    widgets.validation_button("Tr")
    widgets.explanation_panel("Tr")
    if resultat is not None:
        _resultats(resultat)
