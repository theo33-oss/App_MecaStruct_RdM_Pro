"""Page « Convertisseur » : conversion entre unités de toutes les grandeurs (port de buildConverterTab).

Les champs de saisie de l'application restent en mm, m, kN et MPa ; les résultats aussi.
"""

import pandas as pd
import streamlit as st

from mecastruct.core import units
from mecastruct.core.errors import MecaStructError
from mecastruct.ui import state
from mecastruct.ui.widgets import error_box

# Unités attendues dans les champs de saisie (port de expectedUnits de MecaStruct_App.m)
UNITES_ATTENDUES = [
    ("Matériaux", "E, G", "GPa"),
    ("Matériaux", "Re, Rm, contraintes", "MPa"),
    ("Sections", "dimensions b, h, D, d, B, H, t, tw, tf", "mm"),
    ("Sections", "N, Ty ; Mfz, Mfy", "kN ; kN·m"),
    ("Poutres", "L, positions, a, b", "m"),
    ("Poutres", "S ; Iz, Iy, Ix ; vy, vz", "mm² ; mm⁴ ; mm"),
    ("Poutres", "forces ; couples ; charges réparties", "kN ; kN·m ; kN/m"),
    ("Treillis", "coordonnées ; S ; forces", "m ; mm² ; kN"),
    ("Traction", "N ; S0 ; L0 ; ΔT ; α", "kN ; mm² ; m ; °C ; 10⁻⁶/°C"),
    ("Cisaillement", "T, F ; S ; C ; D, a, b, L, d, e", "kN ; mm² ; kN·m ; mm"),
    ("Torsion", "Mt ; D, d ; L ; θ adm", "kN·m ; mm ; m ; °/m"),
    ("Flexion", "N ; Mfz, Mfy", "kN ; kN·m"),
    ("Flambage", "L ; S ; Iz, Iy ; P", "m ; mm² ; mm⁴ ; kN"),
    ("Tenseurs", "σij", "MPa"),
    ("Hooke", "σ ; ε, γ ; E", "MPa ; µdéf ; GPa"),
    ("Jauges", "ε ; R0 ; Vin ; Vout", "µdéf ; Ω ; V ; mV"),
    ("Résultats", "tous les rapports et graphes", "mm, kN, kN·m, MPa, mrad"),
]

# Équivalences utiles en RDM (port du tableau « useful » de buildConverterTab)
EQUIVALENCES = [
    ("1 MPa", "= 1 N/mm² = 10⁶ Pa"),
    ("1 GPa", "= 1000 MPa (E acier = 190 GPa = 190 000 MPa)"),
    ("1 daN", "= 10 N"),
    ("1 kgf", "= 9,80665 N"),
    ("1 bar", "= 0,1 MPa"),
    ("1 ksi", "≈ 6,895 MPa"),
    ("1 psi", "≈ 6,895 kPa"),
    ("1 kN·m", "= 10⁶ N·mm"),
    ("1 in", "= 25,4 mm"),
    ("1 µdéf", "= 10⁻⁶ = 0,0001 %"),
    ("1 rad", "≈ 57,2958 °"),
]

state.init()
GRANDEURS = units.unitCatalog()
NOMS = [g["name"] for g in GRANDEURS]


def _grandeur(nom: str) -> dict:
    """Entrée du catalogue d'unités pour la grandeur `nom`."""
    return next(g for g in GRANDEURS if g["name"] == nom)


def _libelles(nom: str) -> list[str]:
    """Libellés des unités de la grandeur `nom`, dans l'ordre du catalogue."""
    return [u["label"] for u in _grandeur(nom)["units"]]


def _unites_par_defaut() -> None:
    """Remet « De » et « Vers » sur les unités par défaut de la grandeur choisie (indices 1-based du catalogue)."""
    g = _grandeur(st.session_state["conv.grandeur"])
    libelles = _libelles(g["name"])
    st.session_state["conv.de"] = libelles[g["defFrom"] - 1]
    st.session_state["conv.vers"] = libelles[g["defTo"] - 1]


def _inverser() -> None:
    """Échange les unités « De » et « Vers »."""
    de, vers = st.session_state["conv.de"], st.session_state["conv.vers"]
    st.session_state["conv.de"], st.session_state["conv.vers"] = vers, de


st.title("Convertisseur")
if "conv.de" not in st.session_state:
    st.session_state.setdefault("conv.grandeur", NOMS[0])
    _unites_par_defaut()

c1, c2, c3, c4, c5 = st.columns([2, 1.2, 1.2, 1.2, 1])
grandeur = c1.selectbox("Grandeur", NOMS, key="conv.grandeur", on_change=_unites_par_defaut)
valeur = c2.number_input("Valeur", value=1.0, format="%.10g", key="conv.valeur")
c3.selectbox("De", _libelles(grandeur), key="conv.de")
c4.selectbox("Vers", _libelles(grandeur), key="conv.vers")
c5.button("Inverser", on_click=_inverser)
de, vers = st.session_state["conv.de"], st.session_state["conv.vers"]

try:
    resultat = units.convertUnits(valeur, grandeur, de, vers)
    st.metric(f"{valeur:.10g} {de} =", f"{float(resultat):.10g} {vers}")
    st.caption("Valeur à copier (bouton en haut à droite du cadre) :")
    st.code(f"{float(resultat):.10g}", language=None)
    st.dataframe(
        pd.DataFrame(
            {
                "Unité": _libelles(grandeur),
                "Valeur équivalente": [
                    f"{float(units.convertUnits(valeur, grandeur, de, u)):.10g}" for u in _libelles(grandeur)
                ],
            }
        ),
        hide_index=True,
    )
except MecaStructError as err:
    error_box(err)

st.info("Les champs de saisie de l'application sont en mm, m, kN et MPa ; les résultats aussi.")

col_attendues, col_equivalences = st.columns([1.4, 1])
with col_attendues:
    st.subheader("Unités attendues dans les champs")
    st.dataframe(
        pd.DataFrame(UNITES_ATTENDUES, columns=["Où", "Champ", "Unité attendue"]),
        hide_index=True,
    )
with col_equivalences:
    st.subheader("Équivalences utiles en RDM")
    st.dataframe(pd.DataFrame(EQUIVALENCES, columns=["Équivalence", ""]), hide_index=True)
