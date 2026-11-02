"""Page « Roulements » : durée de vie L10 et Lnh, charge équivalente, ensembles iso-fiables et règles de montage.

Formules et règles du cours « Calcul sur les roulements » et « Liaison pivot par roulements » (IUT de Bordeaux).
"""

import streamlit as st

from mecastruct.core import bearings
from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc
from mecastruct.ui import machine_dossier, state, widgets
from mecastruct.ui import machine_page as mp

state.init()
P, ENS = "rlt", "rlt_ens"
DEFAUT, DEFAUT_ENS = mc.defaultBearingInput(), mc.defaultBearingSetInput()
mp.init(P, DEFAUT)
mp.init(ENS, DEFAUT_ENS)

st.title("Roulements")
onglets = st.tabs(["Durée de vie", "Ensemble de roulements", "Règles de montage"])

with onglets[0]:
    gauche, droite = widgets.zones(P)
    with gauche:
        with st.expander("Charges et vitesse", expanded=True):
            mp.num(P, "Fr", "Charge radiale Fr", "N", min_value=0.0)
            mp.num(P, "Fa", "Charge axiale Fa", "N", min_value=0.0)
            mp.num(P, "N", "Fréquence de rotation", "tr/min", min_value=0.0)
        with st.expander("Roulement", expanded=True):
            st.selectbox("Éléments roulants", ["billes", "rouleaux"], key=f"{P}.type")
            mp.num(P, "C", "Charge dynamique de base C", "N", min_value=0.0)
            mp.num(P, "C0", "Charge statique de base C0", "N", min_value=0.0)
            st.checkbox("e et Y dans la table du cours (billes à contact radial)", key=f"{P}.tableau")
            c1, c2, c3 = st.columns(3)
            with c1:
                mp.num(P, "e", "e", min_value=0.0)
            with c2:
                mp.num(P, "X", "X", min_value=0.0)
            with c3:
                mp.num(P, "Y", "Y", min_value=0.0)
        with st.expander("Fiabilité et durée visée", expanded=True):
            mp.num(P, "F", "Fiabilité F", "%", min_value=1.0, max_value=99.9)
            mp.num(P, "Lh", "Durée visée Lh", "h", min_value=0.0)
        s = mp.saisie(P, DEFAUT)
        mp.calcul(P, s, mc.computeBearingLife)
        st.caption(
            "Table du cours : e, X et Y pour les billes à contact radial, interpolés linéairement en Fa/C0. "
            "Pour les autres roulements, saisir e, X et Y du constructeur. Fa/Fr ≤ e : P = Fr ; sinon P = X·Fr + Y·Fa. "
            "Un roulement de butée ne reçoit que Fa (Fr = 0)."
        )
    with droite:
        mp.apercu(lambda: machine_schemas.bearingSection(s))
        mp.resultats(P, s, lambda r: machine_schemas.bearingLife(r, s))

with onglets[1]:
    gauche, droite = widgets.zones(ENS)
    with gauche:
        with st.expander("Durées des roulements en série", expanded=True):
            mp.num(ENS, "L1", "Durée du roulement 1", "h", min_value=0.0)
            mp.num(ENS, "L2", "Durée du roulement 2", "h", min_value=0.0)
            mp.num(ENS, "L3", "Durée du roulement 3 (0 = absent)", "h", min_value=0.0)
        with st.expander("Guidage iso-fiable", expanded=True):
            mp.num(ENS, "LG", "Durée du guidage LG", "h", min_value=0.0)
            mp.num(ENS, "nG", "Nombre de roulements iso-fiables", min_value=1.0, step=1.0)
        s_ens = mp.saisie(ENS, DEFAUT_ENS)
        mp.calcul(ENS, s_ens, mc.computeBearingSet)
        st.caption(
            "Roulements en série sur un même arbre : (Σ Lj^(−1,5))^(−1/1,5). Roulements iso-fiables : chacun dure "
            "LG × n^(2/3), et l'ensemble dure LG."
        )
    with droite:
        mp.apercu(lambda: machine_schemas.bearingSet(s_ens))
        mp.resultats(ENS, s_ens)

with onglets[2]:
    st.markdown(
        "Règle du cours : la bague **tournante par rapport à la charge** se monte **serrée**, la bague **fixe** par "
        "rapport à la charge se monte **glissante**. On ne fabrique pas les roulements : on impose les tolérances "
        "de l'arbre et de l'alésage."
    )
    bague = st.radio("Bague", ["intérieure", "extérieure"], horizontal=True, key="rlt_regle.bague")
    rotations = list(dict.fromkeys(r for (b, r, _), _ in bearings.AJUSTEMENTS if b == bague))
    rotation = st.radio(
        "Rotation de la bague par rapport à la direction de la charge",
        rotations,
        horizontal=True,
        key=f"rlt_regle.rotation.{bague}",
    )
    charges = [c for (b, r, c), _ in bearings.AJUSTEMENTS if (b, r) == (bague, rotation)]
    charge = st.selectbox("Charge", charges, key=f"rlt_regle.charge.{bague}.{rotation}")
    if rotation == "indéfinie":
        st.info(
            "Direction de la charge non définie : le cours conseille un alésage K7 pour une charge normale "
            "ou importante."
        )
    else:
        st.success(f"Bague montée {bearings.mountingRule(bague, rotation)}")
    portee, ajustement = bearings.fitRule(bague, rotation, charge)
    st.write(f"Ajustement conseillé : {portee} {ajustement}")
    with st.expander("Immobilisation axiale (solutions du cours)"):
        st.markdown(
            "- **Bague intérieure** : anneau élastique, épaulement, entretoise (Ø70 H11-d11 en exemple), "
            "écrou à encoche avec rondelle frein.\n"
            "- **Bague extérieure** : épaulement, anneau élastique, chapeau centré (Ø80 H7-h6 en exemple), "
            "entretoise, boîtier de roulement (Ø85 H7-h6 et Ø80 H7-h6), chapeau sur roulement rainuré, "
            "boîtier réglable avec cale."
        )

st.divider()
machine_dossier.bouton(
    "roulements",
    "Roulements",
    [(P, "Durée de vie", DEFAUT, "bearing"), (ENS, "Ensemble de roulements", DEFAUT_ENS, "bearingSet")],
)
