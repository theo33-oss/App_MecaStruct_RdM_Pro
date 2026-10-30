"""État de session Streamlit : DataManager, saisie par onglet et résultats, propres à chaque visiteur.

Les clés de widgets commencent par « onglet. » : reset_widgets(onglet) les supprime quand la saisie
change par programme.
"""

import streamlit as st

from mecastruct.core.data_manager import DataManager
from mecastruct.services.examples import loadExample

ONGLETS = ("Sec", "Beam", "Tr", "Tra", "Cis", "Tor", "Fle", "Fla", "Ten", "Hoo", "Jau")


def init() -> None:
    """Crée dm, saisie (exemple d'école de chaque onglet, comme au démarrage de MATLAB) et res, s'ils sont absents."""
    if "dm" not in st.session_state:
        st.session_state["dm"] = DataManager()
    if "saisie" not in st.session_state:
        st.session_state["saisie"] = {tab: loadExample(tab) for tab in ONGLETS}
    if "res" not in st.session_state:
        st.session_state["res"] = {}


def saisie(tab: str) -> dict:
    """Saisie courante de l'onglet `tab` (dict, unités d'affichage de MATLAB)."""
    return st.session_state["saisie"][tab]


def set_result(tab: str, res: dict) -> None:
    """Enregistre le dernier résultat de calcul de l'onglet `tab`."""
    st.session_state["res"][tab] = res


def result(tab: str) -> dict | None:
    """Dernier résultat de l'onglet `tab`, ou None s'il n'a pas encore été calculé."""
    return st.session_state["res"].get(tab)


def reset_widgets(tab: str) -> None:
    """Supprime de st.session_state les clés de widgets de l'onglet `tab` (à appeler avant un st.rerun)."""
    prefixe = f"{tab}."
    for cle in [k for k in st.session_state.keys() if k.startswith(prefixe)]:
        del st.session_state[cle]
