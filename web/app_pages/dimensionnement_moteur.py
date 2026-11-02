"""Page « Dimensionnement moteur » : couple équivalent thermique d'un cycle, choix du moteur, inertie ramenée.

Méthode du cours « Description et étude des chaînes de transmission de puissance » (IUT de Bordeaux) : couple
quadratique moyen sur les phases d'accélération, de régime établi et de freinage, puis choix du moteur.
"""

import streamlit as st

from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc
from mecastruct.ui import machine_dossier, state, widgets
from mecastruct.ui import machine_page as mp

state.init()
P = "mot"
DEFAUT = mc.defaultMotorInput()
mp.init(P, DEFAUT)

st.title("Dimensionnement moteur")
gauche, droite = widgets.zones(P)
with gauche:
    with st.expander("Cycle (couple et durée de chaque phase)", expanded=True):
        mp.num(P, "Ca", "Couple en accélération Ca", "N·m")
        mp.num(P, "ta", "Durée de l'accélération", "s", min_value=0.0)
        mp.num(P, "Cc", "Couple en régime établi Cc", "N·m")
        mp.num(P, "tc", "Durée du régime établi", "s", min_value=0.0)
        mp.num(P, "Cfr", "Couple au freinage", "N·m")
        mp.num(P, "tfr", "Durée du freinage", "s", min_value=0.0)
    with st.expander("Moteur choisi", expanded=True):
        mp.num(P, "Cn", "Couple nominal", "N·m", min_value=0.0)
        mp.num(P, "Cmax", "Couple maxi", "N·m", min_value=0.0)
        mp.num(P, "Nmax", "Vitesse maxi", "tr/min", min_value=0.0)
        mp.num(P, "Nreq", "Vitesse requise par le cahier des charges", "tr/min", min_value=0.0)
    with st.expander("Inertie ramenée à l'arbre moteur", expanded=False):
        mp.num(P, "Jm", "Inertie du moteur Jm", "kg·m²", min_value=0.0)
        mp.num(P, "Js", "Inertie de la charge ramenée à sa sortie Js", "kg·m²", min_value=0.0)
        mp.num(P, "rs", "Rapport de réduction vers la sortie", min_value=0.01)
    s = mp.saisie(P, DEFAUT)
    mp.calcul(P, s, mc.computeMotor)
    st.caption(
        "Les durées des phases ne figurent pas dans le cours : les valeurs par défaut retrouvent le couple équivalent "
        "de 61 N·m du cours. Remplacer par les durées de votre cycle. Vitesse requise également à saisir."
    )
    with st.expander("Classification des organes de transmission (cours)"):
        st.markdown(
            "- **Transformer l'énergie** : moteurs électriques, thermiques, hydrauliques, pneumatiques ; vérins ; "
            "freins.\n"
            "- **Transformer le mouvement** : vis-écrou, bielle-manivelle, came, pignon-crémaillère, tambour ou "
            "poulie.\n"
            "- **Adapter la vitesse ou la puissance** : réducteurs (engrenages, courroie, chaîne), boîtes de "
            "vitesses, embrayages, coupleurs hydrauliques.\n"
            "- **Transporter ou distribuer l'énergie** : arbres, courroies, chaînes, câbles, joints de cardan, "
            "tuyauteries, différentiels."
        )
with droite:
    mp.apercu(lambda: machine_schemas.motorCycle(s))
    mp.resultats(P, s)

st.divider()
machine_dossier.bouton("moteur", "Dimensionnement moteur", [(P, "Choix du moteur", DEFAUT, "motor")])
