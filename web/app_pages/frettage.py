"""Page « Frettage » : liaison arbre / moyeu serrée, choix de l'ajustement normalisé et température de chauffe.

Port du classeur « Calculs de frettage normalises.xlsm » de l'auteur (NF E22-620).
"""

import streamlit as st

from mecastruct.core import fits, shrink_fit
from mecastruct.services import machine
from mecastruct.ui import machine_page as mp
from mecastruct.ui import state, widgets

state.init()
dm = st.session_state["dm"]
P = "fre"
DEFAUT = machine.defaultShrinkInput()
mp.init(P, DEFAUT)


def _norme() -> None:
    """Qualités, lissage et jeu de montage conseillés par la norme pour le diamètre saisi (bouton)."""
    n = shrink_fit.normValues(st.session_state[f"{P}.d"])
    st.session_state[f"{P}.horsTable"] = n is None
    if n is None:
        return
    st.session_state[f"{P}.qa"], st.session_state[f"{P}.qm"] = int(n["qualiteArbre"]), int(n["qualiteMoyeu"])
    st.session_state[f"{P}.lissage"], st.session_state[f"{P}.jeu"] = n["lissage"], n["jeu"]


st.title("Frettage")
gauche, droite = widgets.zones(P)
with gauche:
    with st.expander("Efforts à transmettre", expanded=True):
        mp.num(P, "C", "Couple C", "N·m", min_value=0.0)
        mp.num(P, "Fa", "Effort axial Fa", "N", min_value=0.0)
        mp.num(P, "f", "Coefficient d'adhérence f", min_value=0.01)
        mp.num(P, "s", "Coefficient de sécurité sur l'effort", min_value=1.0)
    with st.expander("Géométrie", expanded=True):
        mp.num(P, "d", "Diamètre frettée d", "mm", min_value=0.0)
        mp.num(P, "di", "Diamètre intérieur de l'arbre (0 = plein)", "mm", min_value=0.0)
        mp.num(P, "D", "Diamètre extérieur du moyeu D", "mm", min_value=0.0)
        mp.num(P, "L", "Longueur frettée L", "mm", min_value=0.0)
    with st.expander("Matériaux", expanded=True):
        noms = dm.listMaterials()
        st.selectbox("Matériau de l'arbre", noms, key=f"{P}.matArbre")
        st.selectbox("Matériau du moyeu", noms, key=f"{P}.matMoyeu")
    with st.expander("Tolérances et montage", expanded=True):
        c1, c2 = st.columns(2)
        c1.selectbox("Qualité arbre", fits.QUALITES, key=f"{P}.qa")
        c2.selectbox("Qualité moyeu (H)", fits.QUALITES, key=f"{P}.qm")
        mp.num(P, "lissage", "Lissage (perte de serrage)", "µm", min_value=0.0)
        mp.num(P, "jeu", "Jeu de montage à chaud", "mm", min_value=0.0)
        st.button("Valeurs conseillées par la norme pour ce diamètre", key=f"{P}.norme", on_click=_norme)
        if st.session_state.get(f"{P}.horsTable"):
            st.warning("Diamètre hors table : saisir les valeurs.")
    s = mp.saisie(P, DEFAUT)
    mp.calcul(P, s, lambda x: machine.computeShrinkFit(x, dm))
    st.caption(
        "Alésage normal H. L'arbre retenu est le moins serré dont l'écart inférieur couvre le serrage utile + le "
        "lissage. Contraintes : Lamé, arbre 2p/(1 − (di/d)²), moyeu Von Mises à l'alésage."
    )
with droite:
    mp.resultats(P, s)
