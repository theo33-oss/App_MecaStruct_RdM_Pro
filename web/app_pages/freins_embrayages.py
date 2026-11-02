"""Page « Freins et embrayages » : couple et pression d'un frein à disque, synchronisation d'un embrayage.

Formules du cours « Frein – Embrayage » (IUT de Bordeaux, ICM S5) : pression de contact constante ou usure constante,
équation du mouvement de l'arbre moteur et de l'arbre récepteur.
"""

import streamlit as st

from mecastruct.services import machine_courses as mc
from mecastruct.ui import machine_page as mp
from mecastruct.ui import state, widgets

state.init()
FRE, EMB = "frn", "emb"
DEFAUT_FRE, DEFAUT_EMB = mc.defaultBrakeInput(), mc.defaultClutchInput()
mp.init(FRE, DEFAUT_FRE)
mp.init(EMB, DEFAUT_EMB)

st.title("Freins et embrayages")
onglets = st.tabs(["Frein à disque", "Embrayage"])

with onglets[0]:
    gauche, droite = widgets.zones(FRE)
    with gauche:
        with st.expander("Effort et garniture", expanded=True):
            mp.num(FRE, "F", "Effort presseur F par surface", "N", min_value=0.0)
            mp.num(FRE, "f", "Coefficient de frottement f", min_value=0.0, max_value=1.0)
            mp.num(FRE, "n", "Nombre de surfaces frottantes n", min_value=1.0, step=1.0)
        with st.expander("Géométrie du disque", expanded=True):
            mp.num(FRE, "Ri", "Rayon intérieur Ri", "mm", min_value=0.0)
            mp.num(FRE, "Re", "Rayon extérieur Re", "mm", min_value=0.1)
        mp.num(FRE, "N", "Fréquence de rotation du disque au freinage", "tr/min", min_value=0.0)
        s_fre = mp.saisie(FRE, DEFAUT_FRE)
        mp.calcul(FRE, s_fre, mc.computeBrake)
        st.caption(
            "Couple Cf = n·f·F·(2/3)(Re³ − Ri³)/(Re² − Ri²) en pression constante, ou n·f·F·(Re + Ri)/2 en usure "
            "constante. La puissance spécifique moyenne est à comparer à la limite du fabricant de la garniture."
        )
    with droite:
        mp.resultats(FRE, s_fre)

with onglets[1]:
    gauche, droite = widgets.zones(EMB)
    with gauche:
        with st.expander("Moteur et récepteur", expanded=True):
            mp.num(EMB, "CM", "Couple moteur CM", "N·m", min_value=0.0)
            mp.num(EMB, "NM", "Fréquence de rotation du moteur", "tr/min", min_value=0.0)
            mp.num(EMB, "JR", "Inertie du récepteur JR", "kg·m²", min_value=0.0)
            mp.num(EMB, "CR", "Couple résistant CR (négatif)", "N·m", max_value=0.0)
        with st.expander("Manœuvre", expanded=True):
            mp.num(EMB, "ts", "Durée de synchronisation visée", "s", min_value=0.1)
            mp.num(EMB, "cadence", "Cadence", "manœuvres/h", min_value=0.0)
        s_emb = mp.saisie(EMB, DEFAUT_EMB)
        mp.calcul(EMB, s_emb, mc.computeClutch)
        st.caption(
            "Pendant la synchronisation le moteur est supposé à vitesse constante : le couple d'embrayage vaut "
            "|CR| + JR·ω/ts. Vérification indicative : ce couple doit rester inférieur au couple moteur."
        )
    with droite:
        mp.resultats(EMB, s_emb)
