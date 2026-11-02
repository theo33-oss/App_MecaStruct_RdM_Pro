"""Page « Flambage » : poutre droite comprimée (compression, Rankine ou Euler), courbe de stabilité, mode propre.

Port de l'onglet « Flambage » de MecaStruct_App.m (buildBucklingTab, loadProfileForBuckling, computeBuckling).
"""

import math

import streamlit as st

from mecastruct.core import buckling
from mecastruct.plots import other_plots
from mecastruct.services import compute
from mecastruct.ui import state, transfert, widgets
from mecastruct.ui.formula_panel import formula_panel

REGIMES = {
    "compression": ("Poutre trapue : compression simple", st.warning),
    "rankine": ("Poutre moyenne : formule de Rankine", st.info),
    "euler": ("Poutre élancée : formule d'Euler", st.success),
}

state.init()
dm = st.session_state["dm"]
saisie = state.saisie("Fla")
CONDITIONS = {c["Condition"]: f"{c['Libelle']} (L' = {c['CoefficientTexte']} L)" for c in buckling.listConditions()}


def _charge_profile() -> None:
    """Charge S, Iz, Iy du profilé choisi, valeurs du catalogue (callback de « Charger le profilé »)."""
    nom = st.session_state["Fla.prof"]
    p = dm.getProfile(st.session_state["Fla.fam"], nom)
    st.session_state["Fla.S"] = p["S"] * 1e6
    st.session_state["Fla.Iz"] = p["Iz"] * 1e12
    st.session_state["Fla.Iy"] = p["Iy"] * 1e12
    st.session_state["Fla_info"] = f"Section utilisée : profilé {p['Name']} (valeurs du catalogue)."


def _importe_section() -> None:
    """Importe la section de la page Sections (useSectionForBeam : Poutres la reçoit aussi, comme MATLAB)."""
    if transfert.envoie_section(dm) is None:
        st.session_state["Fla_msg"] = "Calculez d'abord une section dans la page Sections."


def _section_manuelle() -> None:
    st.session_state["Fla_info"] = "Section utilisée : valeurs saisies à la main."


def _calcule() -> None:
    try:
        state.set_result("Fla", compute.computeBuckling(saisie, dm))
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop("Fla", None)


def _saisie() -> None:
    with st.expander("Section", expanded=True):
        info = st.session_state.get("Fla_info")
        if info:
            st.markdown(f"**{info}**")
        widgets.choice("Fla", "fam", "Famille de profilé", dm.listProfileFamilies())
        profils = dm.listProfiles(saisie["fam"])
        if saisie["prof"] not in profils:
            saisie["prof"] = profils[0]
            st.session_state.pop("Fla.prof", None)
        widgets.choice("Fla", "prof", "Profilé", profils)
        st.button("Charger le profilé", key="Fla.charger_profil", on_click=_charge_profile)
        st.button(
            "← Importer depuis Sections",
            key="Fla.importer",
            on_click=_importe_section,
            help="Recopie S, Iz, Iy et le matériau de la page Sections (à calculer d'abord).",
        )
        if message := st.session_state.pop("Fla_msg", None):
            st.warning(message)
        for champ, label, unite in (("S", "S", "mm²"), ("Iz", "Iz", "mm⁴"), ("Iy", "Iy", "mm⁴")):
            widgets.num("Fla", champ, label, unite, min_value=0.0, on_change=_section_manuelle, format="%.6g")
    with st.expander("Poutre comprimée", expanded=True):
        widgets.choice_materiau("Fla", ["E", "Re"], dm)
        widgets.num("Fla", "E", "E", "GPa")
        widgets.num("Fla", "Re", "Re", "MPa")
        widgets.num("Fla", "L", "Longueur L", "m", min_value=0.0)
        widgets.choice("Fla", "cond", "Conditions aux limites", list(CONDITIONS), format_func=CONDITIONS.get)
        widgets.num("Fla", "P", "P appliquée (compression > 0, 0 = aucune)", "kN")
        widgets.num("Fla", "s", "Coefficient de sécurité s", "-")


def _resultats(res: dict) -> None:
    b, c = res["result"]["analysis"], res["result"]["curve"]
    titre, boite = REGIMES[b["regime"]]
    boite(f"**Régime : {titre}** — λ = {b['lambda']:.4g} (λlim = {b['lambdaLim']:.4g})")
    if math.isfinite(b["P"]):  # P = 0 : aucune charge appliquée, pas de verdict
        mot = "vérifié" if b["ok"] else "NON vérifié"
        widgets.status(f"P = {b['P'] / 1e3:.5g} kN, Padm = {b['Padm'] / 1e3:.5g} kN : {mot}", bool(b["ok"]))
    if buckling.alerteSeuilLambdaLim(b["lambda"], b["lambdaLim"]):
        st.warning(
            f"λ = {b['lambda']:.4g} est à moins de 10 % de λlim = {b['lambdaLim']:.4g} : la charge critique "
            "change de modèle au seuil (Rankine → Euler) et saute de Re·S/2 à Re·S. "
            "Verdict à interpréter avec prudence."
        )
    widgets.plot(other_plots.bucklingCurve(c, b))
    widgets.plot(other_plots.bucklingMode(b))
    st.dataframe(res["tables"]["Synthèse"], hide_index=True)
    onglets = st.tabs(["Démonstration", "Rapport", "Formules"])
    with onglets[0]:
        st.caption(b["modeText"])
        widgets.formulas(b["derivation"])
    with onglets[1]:
        widgets.report(res["result"]["rapport"])
    with onglets[2]:
        widgets.formulas(b["latex"])


st.title("Flambage")
formula_panel("flambage")

gauche, droite = widgets.zones("Fla")
with gauche:
    calcule = widgets.calc_button("Fla.calc")
    synthese = st.container()
    widgets.file_bar("Fla")
    widgets.example_picker("Fla")
    _saisie()
    if calcule:
        _calcule()
    widgets.synthese_resultat("Fla", synthese)

with droite:
    widgets.validation_button("Fla")
    widgets.explanation_panel("Fla")
    if state.result("Fla") is not None:
        _resultats(state.result("Fla"))
