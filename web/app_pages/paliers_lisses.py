"""Page « Paliers lisses » : vérification P, V, PV d'un coussinet (et de sa collerette) sur le diagramme P-V.

Port du classeur « CALCULS PALIERS LISSES.xlsm » de l'auteur, sans catalogue de fabricant : on vérifie les
dimensions saisies.
"""

import streamlit as st

from mecastruct.core import plain_bearing
from mecastruct.plots import machine_plots
from mecastruct.services import machine
from mecastruct.ui import machine_page as mp
from mecastruct.ui import state, widgets

state.init()
P = "pal"
DEFAUT = machine.defaultBearingInput()
mp.init(P, DEFAUT)

st.title("Paliers lisses")
gauche, droite = widgets.zones(P)
with gauche:
    with st.expander("Charges et mouvement", expanded=True):
        mp.num(P, "Fr", "Force radiale Fr", "N", min_value=0.0)
        mp.num(P, "Fa", "Force axiale Fa (collerette)", "N", min_value=0.0)
        mp.num(P, "n", "Fréquence de rotation", "tr/min", min_value=0.0)
        st.caption("Oscillation (remplace la rotation si les deux champs sont renseignés) :")
        mp.num(P, "osc", "Fréquence d'oscillation", "oscillations/min", min_value=0.0)
        mp.num(P, "beta", "Demi-amplitude β", "°", min_value=0.0)
    with st.expander("Coussinet", expanded=True):
        st.selectbox("Matériau", [m["Name"] for m in plain_bearing.materials()], key=f"{P}.materiau")
        mp.num(P, "d", "Alésage d (diamètre de l'arbre)", "mm", min_value=0.0)
        mp.num(P, "L", "Longueur L", "mm", min_value=0.0)
        mp.num(P, "Dfl", "Diamètre de collerette (0 = sans)", "mm", min_value=0.0)
    s = mp.saisie(P, DEFAUT)
    mp.calcul(P, s, machine.computeBearing)
    st.caption(
        "Limites P, V et courbe P-V : ordres de grandeur par famille de matériau, à confirmer sur la documentation "
        "du fabricant du coussinet."
    )
with droite:
    mp.resultats(P, s, machine_plots.pvDiagram)
