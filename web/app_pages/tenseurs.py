"""Page « Tenseurs & critères » : contraintes principales, facette, cercles de Mohr, critères, lieux de plasticité.

Port de l'onglet « Tenseurs & Critères » de MecaStruct_App.m (buildTensorTab, computeTensor, symmetrize). La page reçoit
aussi l'état de contrainte envoyé par la page Poutres (« Envoyer au tenseur »).
"""

import numpy as np
import pandas as pd
import streamlit as st

from mecastruct.plots import other_plots
from mecastruct.services import compute
from mecastruct.ui import state, widgets
from mecastruct.ui.formula_panel import formula_panel

AXES = ["x", "y", "z"]
FACETTES = {"theta": "Angle θ dans le plan (x, y)", "n": "Normale n (nx, ny, nz)"}

state.init()
dm = st.session_state["dm"]
saisie = state.saisie("Ten")


def _edite_tenseur() -> None:
    """Applique la cellule modifiée en gardant le tenseur symétrique (σij = σji), puis change la clé de l'éditeur."""
    tab = st.session_state["saisie"]["Ten"]
    v = st.session_state.get("Ten.sig.v", 0)
    edits = st.session_state.get(f"Ten.sig.ed{v}", {}).get("edited_rows", {})
    tab["sig"] = compute.symmetrize(tab["sig"], edits)
    st.session_state["Ten.sig.v"] = v + 1


def _calcule() -> None:
    try:
        state.set_result("Ten", compute.computeTensor(saisie, dm))
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop("Ten", None)


def _saisie() -> None:
    with st.expander("Tenseur des contraintes σ (MPa)", expanded=True):
        v = st.session_state.setdefault("Ten.sig.v", 0)
        st.data_editor(
            pd.DataFrame(saisie["sig"], index=AXES, columns=AXES),
            key=f"Ten.sig.ed{v}",
            on_change=_edite_tenseur,
            num_rows="fixed",
            column_config={a: st.column_config.NumberColumn(a, format="%.5g") for a in AXES},
        )
        st.caption("La saisie est symétrisée automatiquement (σij = σji).")
    with st.expander("Facette", expanded=True):
        mode = widgets.choice("Ten", "fmode", "Définition", list(FACETTES), format_func=FACETTES.get)
        widgets.num("Ten", "theta", "θ", "°", disabled=mode != "theta")
        for n in ("nx", "ny", "nz"):
            widgets.num("Ten", n, n, "-", disabled=mode != "n")
    with st.expander("Critères", expanded=True):
        widgets.choice_materiau("Ten", ["Re", "Rm"], dm)
        widgets.num("Ten", "Re", "Re = σe", "MPa")
        widgets.num("Ten", "Rm", "σR (fragiles : Rm)", "MPa")
        widgets.num("Ten", "s", "Coefficient de sécurité s", "-")


def _point_critere(r: dict) -> list[float]:
    """Point tracé sur le lieu de plasticité : (σ1, σ2) en état plan, sinon (σI − σII, σIII − σII), en Pa."""
    pr = r["principal"]
    sig = np.array(saisie["sig"], dtype=float)
    if np.all(np.abs(sig[2, :]) <= 1e-12 * max(1.0, np.max(np.abs(sig)))):
        return [r["plane2D"]["sigma1"], r["plane2D"]["sigma2"]]
    return [pr["sigmaI"] - pr["sigmaII"], pr["sigmaIII"] - pr["sigmaII"]]


def _resultats(res: dict) -> None:
    r, t = res["result"], res["tables"]
    ok = bool(r["criteria"]["okTresca"] and r["criteria"]["okVM"])
    widgets.status(res["status"], ok)
    fa = r["facet"]
    graphes = st.tabs(["Tricercle de Mohr", "Mohr 2D (plan x, y)", "Lieu de plasticité"])
    with graphes[0]:
        st.plotly_chart(other_plots.mohr3D(r["mohr3D"], [fa["sigmaN"], fa["tauNorm"]]))
    with graphes[1]:
        st.plotly_chart(other_plots.mohr2D(r["plane2D"], r["plane2D"]["theta"]))
    with graphes[2]:
        st.plotly_chart(other_plots.yieldLocus(r["loci"], _point_critere(r)))
    onglets = st.tabs(["Principales", "Critères", "Facette", "Rapport", "Formules"])
    for onglet, nom in zip(onglets[:3], ("Principales", "Critères", "Facette"), strict=True):
        with onglet:
            st.dataframe(t[nom], hide_index=True)
    with onglets[3]:
        widgets.report(r["rapport"])
    with onglets[4]:
        for cle in ("principal", "facet", "plane2D", "mohr3D", "criteria", "loci"):
            widgets.formulas(r[cle]["latex"])


st.title("Tenseurs & critères")
formula_panel("tenseurs")

gauche, droite = st.columns([1, 2], gap="large")
with gauche:
    widgets.example_picker("Ten")
    _saisie()
    if st.button("Calculer", key="Ten.calc", type="primary", width="stretch"):
        _calcule()

with droite:
    if state.result("Ten") is not None:
        _resultats(state.result("Ten"))
