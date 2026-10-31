"""Page « Hooke & jauges » : loi de Hooke (4 modes) et extensométrie (jauge, pont de Wheatstone, rosettes).

Port des onglets de MecaStruct_App.m (buildHookeTab, onHookeMode, computeHooke, computeGauges). La fiche de formules
suit le sous-onglet ouvert.
"""

import streamlit as st

from mecastruct.plots import other_plots
from mecastruct.services import compute
from mecastruct.services.examples import loadExample
from mecastruct.ui import state, widgets
from mecastruct.ui.formula_panel import formula_panel

MODES = {
    "iso3D": "Hooke 3D isotrope",
    "planeStress": "Contraintes planes",
    "planeStrain": "Déformations planes",
    "ortho": "Orthotrope (9 constantes)",
}
MONTAGES = {"quart": "Quart de pont", "demi": "Demi-pont", "complet": "Pont complet"}
ROSETTES = {"45": "Rectangulaire 0°/90°/45°", "60": "Delta 0°/60°/120°"}

state.init()
dm = st.session_state["dm"]


def _calcule(cle: str, travail) -> None:
    try:
        state.set_result(cle, travail())
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop(cle, None)


def _recharge_hooke() -> None:
    """Recharge l'exemple du mode courant (loadExample('Hooke', mode) de MATLAB)."""
    mode = st.session_state.get("Hoo.mode", state.saisie("Hoo")["mode"])
    st.session_state["saisie"]["Hoo"] = loadExample("Hoo", mode)
    state.reset_widgets("Hoo")


# ------------------------------------------------------------------------------------------- Loi de Hooke


def _hooke_saisie() -> None:
    saisie = state.saisie("Hoo")
    mode = widgets.choice("Hoo", "mode", "Loi", list(MODES), format_func=MODES.get)
    iso, ortho = mode != "ortho", mode == "ortho"
    sig_xy = mode in ("iso3D", "planeStress", "ortho")
    sig_3d = mode in ("iso3D", "ortho")
    with st.expander("Matériau isotrope", expanded=True):
        widgets.choice_materiau("Hoo", ["E", "nu", "alpha"], dm, disabled=not iso)
        widgets.num("Hoo", "E", "E", "GPa", disabled=not iso)
        widgets.num("Hoo", "nu", "ν", "-", disabled=not iso)
        widgets.num("Hoo", "alpha", "α", "10⁻⁶/°C", disabled=mode != "iso3D")
        widgets.num("Hoo", "dT", "ΔT", "°C", disabled=mode != "iso3D")
    with st.expander("Contraintes (MPa)", expanded=True):
        for champ, nom, actif in (
            ("sxx", "σxx", sig_xy),
            ("syy", "σyy", sig_xy),
            ("szz", "σzz", sig_3d),
            ("syz", "σyz", sig_3d),
            ("sxz", "σxz", sig_3d),
            ("sxy", "σxy", sig_xy),
        ):
            widgets.num("Hoo", champ, nom, "MPa", disabled=not actif)
    with st.expander("Déformations planes (µdéf)", expanded=mode == "planeStrain"):
        for champ, nom in (("exx", "εxx"), ("eyy", "εyy"), ("gxy", "γxy = 2εxy")):
            widgets.num("Hoo", champ, nom, "µdéf", disabled=mode != "planeStrain")
    with st.expander("Orthotrope (axes 1, 2, 3 = x, y, z)", expanded=ortho):
        for champ, nom, unite in (
            ("E1", "E1", "GPa"),
            ("E2", "E2", "GPa"),
            ("E3", "E3", "GPa"),
            ("nu12", "ν12", "-"),
            ("nu13", "ν13", "-"),
            ("nu23", "ν23", "-"),
            ("G12", "G12", "GPa"),
            ("G13", "G13", "GPa"),
            ("G23", "G23", "GPa"),
        ):
            widgets.num("Hoo", champ, nom, unite, disabled=not ortho)
    colonnes = st.columns(2)
    if colonnes[0].button("Calculer", key="Hoo.calc", type="primary", width="stretch"):
        _calcule("Hoo", lambda: compute.computeHooke(saisie, dm))
    colonnes[1].button("Recharger l'exemple", key="Hoo.recharger", on_click=_recharge_hooke)


def _hooke_resultats() -> None:
    res = state.result("Hoo")
    if res is None:
        return
    r, t = res["result"], res["tables"]
    st.success(res["status"])
    st.plotly_chart(other_plots.mohr2D(r["mohr"]))
    onglets = st.tabs(["Résultats", "Matrice", "Rapport", "Formules"])
    with onglets[0]:
        st.dataframe(t["Résultats"], hide_index=True)
    with onglets[1]:
        st.caption("Rigidité [C] en GPa (symétrique, définie positive).")
        st.dataframe(t["Matrice"])
    with onglets[2]:
        widgets.report(r["rapport"])
    with onglets[3]:
        widgets.formulas(r["mohr"]["latex"])


# ------------------------------------------------------------------------------------------------- Jauges


def _jauges_saisie() -> None:
    saisie = state.saisie("Jau")
    with st.expander("Jauge (loi de Bridgman)", expanded=True):
        widgets.num("Jau", "K", "Facteur de jauge K", "-")
        widgets.num("Jau", "eps", "ε", "µdéf")
        widgets.num("Jau", "R0", "R0", "Ω")
    with st.expander("Pont de Wheatstone", expanded=True):
        widgets.choice("Jau", "cfg", "Montage", list(MONTAGES), format_func=MONTAGES.get)
        widgets.num("Jau", "Vin", "Alimentation Vin", "V")
        for champ in ("e1", "e2", "e3", "e4"):
            widgets.num("Jau", champ, f"ε{champ[1]}", "µdéf")
        widgets.num("Jau", "Vout", "Vout mesurée", "mV")
    with st.expander("Rosette", expanded=True):
        widgets.choice("Jau", "rtype", "Type", list(ROSETTES), format_func=ROSETTES.get)
        widgets.num("Jau", "ra", "ε à 0°", "µdéf")
        widgets.num("Jau", "rb", "ε à 90° (rect.) / 60° (delta)", "µdéf")
        widgets.num("Jau", "rc", "ε à 45° (rect.) / 120° (delta)", "µdéf")
        widgets.choice_materiau("Jau", ["E", "nu"], dm)
        widgets.num("Jau", "E", "E", "GPa")
        widgets.num("Jau", "nu", "ν", "-")
    colonnes = st.columns(2)
    if colonnes[0].button("Calculer", key="Jau.calc", type="primary", width="stretch"):
        _calcule("Jau", lambda: compute.computeGauges(saisie, dm))
    colonnes[1].button("Recharger l'exemple", key="Jau.recharger", on_click=widgets._charge_exemple, args=("Jau",))


def _jauges_resultats() -> None:
    res = state.result("Jau")
    if res is None:
        return
    r, t = res["result"], res["tables"]
    st.success(res["status"])
    graphes = st.tabs(["Mohr des déformations (rosette)", "Mohr des contraintes (rosette)"])
    with graphes[0]:
        st.plotly_chart(other_plots.mohr2D(r["mohrDeformations"]))
    with graphes[1]:
        st.plotly_chart(other_plots.mohr2D(r["mohrContraintes"]))
    onglets = st.tabs(["Rosette", "Jauge et pont", "Rapport", "Formules"])
    with onglets[0]:
        st.dataframe(t["Rosette"], hide_index=True)
    with onglets[1]:
        st.dataframe(t["Jauge et pont"], hide_index=True)
    with onglets[2]:
        widgets.report(r["rapport"])
    with onglets[3]:
        for latex in (r["gauge"]["latex"], r["bridge"]["latex"], r["rosette"]["latex"]):
            widgets.formulas(latex)


ONGLETS = [
    ("Loi de Hooke", "hooke", "Hoo", _hooke_saisie, _hooke_resultats),
    ("Jauges, pont et rosettes", "extensometrie", "Jau", _jauges_saisie, _jauges_resultats),
]

st.title("Hooke & jauges")
onglets = st.tabs([titre for titre, *_ in ONGLETS], key="Hoo_onglet", on_change="rerun")
for onglet, (_, fiche, tab, saisie_fn, resultats_fn) in zip(onglets, ONGLETS, strict=True):
    if onglet.open:
        formula_panel(fiche)  # la fiche suit le sous-onglet ouvert
    with onglet:
        gauche, droite = st.columns([1, 2], gap="large")
        with gauche:
            widgets.file_bar(tab)
            saisie_fn()
        with droite:
            widgets.validation_button(tab)
            resultats_fn()
