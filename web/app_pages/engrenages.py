"""Page « Engrenages » : engrènement à denture droite (géométrie, efforts, pied de dent, module) et train en série.

Formules du cours « Les engrenages » (IUT de Bordeaux) : relations géométriques, rapports, puissance et couple,
résistance d'une dent modélisée par une poutre.
"""

import streamlit as st

from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc
from mecastruct.ui import machine_dossier, state, widgets
from mecastruct.ui import machine_page as mp

state.init()
dm = st.session_state["dm"]
P, TRN = "eng", "trn"
DEFAUT, DEFAUT_TRN = mc.defaultGearInput(), mc.defaultGearTrainInput()
mp.init(P, DEFAUT)
mp.init(TRN, DEFAUT_TRN)

st.title("Engrenages")
onglets = st.tabs(["Engrènement", "Train d'engrenages"])

with onglets[0]:
    gauche, droite = widgets.zones(P)
    with gauche:
        with st.expander("Géométrie", expanded=True):
            mp.num(P, "m", "Module m", "mm", min_value=0.1)
            c1, c2 = st.columns(2)
            with c1:
                mp.num(P, "Z1", "Dents du pignon Z1", min_value=1.0, step=1.0)
            with c2:
                mp.num(P, "Z2", "Dents de la roue Z2", min_value=1.0, step=1.0)
        with st.expander("Transmission", expanded=True):
            mp.num(P, "P", "Puissance au pignon P", "W", min_value=0.0)
            mp.num(P, "N", "Fréquence de rotation du pignon", "tr/min", min_value=0.1)
        with st.expander("Denture et matériau", expanded=True):
            mp.num(P, "k", "Largeur de denture k = b/m", min_value=1.0)
            st.selectbox("Matériau du pignon", dm.listMaterials(), key=f"{P}.materiau")
            mp.num(P, "s", "Coefficient de sécurité sur l'effort s", min_value=1.0)
        s = mp.saisie(P, DEFAUT)
        mp.calcul(P, s, lambda x: mc.computeGearMesh(x, dm))
        st.caption(
            "Angle de pression 20°, dent à profil normal. Contrainte de flexion en pied de dent (poutre encastrée) "
            "comparée à Rpe = Re/s : Re est la limite élastique du matériau de la base (valeur moyenne à minorer). "
            "Usuellement k entre 6 et 10 et s = 1,5 si l'effort est mal connu."
        )
    with droite:
        mp.apercu(lambda: machine_schemas.gearMesh(s))
        mp.resultats(P, s)

with onglets[1]:
    gauche, droite = widgets.zones(TRN)
    with gauche:
        with st.expander("Entrée", expanded=True):
            mp.num(TRN, "P", "Puissance d'entrée P", "W", min_value=0.0)
            mp.num(TRN, "N", "Fréquence de rotation d'entrée", "tr/min", min_value=0.1)
            mp.num(TRN, "eta", "Rendement d'un engrènement η", min_value=0.01, max_value=1.0)
        for i in (1, 2, 3):
            with st.expander(f"Engrènement {i} (menant Z{2 * i - 1}, mené Z{2 * i})", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    mp.num(TRN, f"Z{2 * i - 1}", f"Dents menant Z{2 * i - 1}", min_value=1.0, step=1.0)
                with c2:
                    mp.num(TRN, f"Z{2 * i}", f"Dents mené Z{2 * i}", min_value=1.0, step=1.0)
        s_trn = mp.saisie(TRN, DEFAUT_TRN)
        mp.calcul(TRN, s_trn, mc.computeGearTrain)
        st.caption(
            "Chaque engrènement extérieur inverse le sens : rapport −Zmenant/Zmené. La puissance diminue de η à chaque "
            "engrènement et le couple se calcule par C = P/ω."
        )
    with droite:
        mp.apercu(lambda: machine_schemas.gearTrain(s_trn))
        mp.resultats(TRN, s_trn)

st.divider()
machine_dossier.bouton(
    "engrenages",
    "Engrenages",
    [(P, "Engrènement", DEFAUT, "gearMesh"), (TRN, "Train d'engrenages", DEFAUT_TRN, "gearTrain")],
)
