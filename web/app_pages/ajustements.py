"""Page « Ajustements » : écarts normalisés ISO 286 d'un alésage et d'un arbre, jeu ou serrage.

Port du classeur « ecarts-normalises.xlsm » de l'auteur (tables dans web/data/iso286.json).
"""

import streamlit as st

from mecastruct.core import fits
from mecastruct.plots import machine_plots
from mecastruct.services import machine
from mecastruct.ui import machine_page as mp
from mecastruct.ui import state, widgets

state.init()
P = "aju"
DEFAUT = machine.defaultFitInput()
mp.init(P, DEFAUT)

st.title("Ajustements ISO 286")
gauche, droite = widgets.zones(P)
with gauche:
    mp.num(P, "d", "Diamètre nominal", "mm", min_value=0.0, max_value=3150.0)
    c1, c2 = st.columns(2)
    c1.selectbox("Alésage", fits.LETTRES_ALESAGE, key=f"{P}.alesage")
    c2.selectbox("Qualité alésage", fits.QUALITES, key=f"{P}.qa")
    c1.selectbox("Arbre", fits.LETTRES_ARBRE, key=f"{P}.arbre")
    c2.selectbox("Qualité arbre", fits.QUALITES, key=f"{P}.qb")
    s = mp.saisie(P, DEFAUT)
    mp.calcul(P, s, machine.computeFit)
    st.caption(
        "Tables de l'ISO 286-1/-2 (jusqu'à 3150 mm). Correction Δ appliquée à K, M, N (qualités ≤ 8) et P à ZC "
        "(≤ 7). Jeu négatif = serrage. Usuels : H7/g6 glissant, H7/h6 glissant juste, H7/k6 incertain, H7/p6 serré."
    )
with droite:
    mp.resultats(P, s, lambda r: machine_plots.fitZones(r, f"{s['alesage']}{s['qa']}", f"{s['arbre']}{s['qb']}"))
