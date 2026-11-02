"""Page « Trains épicycloïdaux » : raison basique, vitesses des trois éléments par la formule de Willis, montage.

Méthode du cours « Trains épicycloïdaux » (IUT de Bordeaux) : bloquer le porte-satellites pour la raison basique,
puis composer les vitesses par rapport au bâti.
"""

import streamlit as st

from mecastruct.core import planetary
from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc
from mecastruct.ui import machine_dossier, state, widgets
from mecastruct.ui import machine_page as mp

state.init()
P = "epi"
DEFAUT = mc.defaultPlanetaryInput()
mp.init(P, DEFAUT)

st.title("Trains épicycloïdaux")
gauche, droite = widgets.zones(P)
with gauche:
    with st.expander("Dentures", expanded=True):
        mp.num(P, "Z1", "Planétaire Z1", min_value=1.0, max_value=1000.0, step=1.0)
        mp.num(P, "Z21", "Satellite engrenant le planétaire Z21", min_value=1.0, max_value=1000.0, step=1.0)
        mp.num(
            P,
            "Z22",
            "Satellite engrenant la couronne Z22 (= Z21 si satellite simple)",
            min_value=1.0,
            max_value=1000.0,
            step=1.0,
        )
        mp.num(P, "Z4", "Couronne Z4", min_value=1.0, max_value=1000.0, step=1.0)
        mp.num(P, "nSat", "Nombre de satellites", min_value=1.0, max_value=24.0, step=1.0)
    with st.expander("Cinématique", expanded=True):
        st.selectbox("Élément bloqué", planetary.ELEMENTS, key=f"{P}.bloque")
        st.selectbox("Élément d'entrée", planetary.ELEMENTS, key=f"{P}.entree")
        mp.num(P, "Ne", "Fréquence de rotation de l'entrée", "tr/min")
    s = mp.saisie(P, DEFAUT)
    mp.calcul(P, s, mc.computePlanetary)
    st.caption(
        "L'élément restant est la sortie. Montage : entraxes Z4 = Z1 + Z21 + Z22 et règle du haricot, (Z1 + Z4)/n_sat "
        "entier. Les trois éléments doivent être distincts pour le bloqué et l'entrée."
    )
with droite:
    mp.apercu(lambda: machine_schemas.planetaryTrain(s))
    mp.resultats(P, s)

st.divider()
machine_dossier.bouton("epicycloidaux", "Trains épicycloïdaux", [(P, "Train épicycloïdal", DEFAUT, "planetary")])
