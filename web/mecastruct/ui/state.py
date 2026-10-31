"""État de session Streamlit : DataManager, saisie par onglet et résultats, propres à chaque visiteur.

Les clés de widgets commencent par « onglet. » : reset_widgets(onglet) les supprime quand la saisie
change par programme.
"""

import copy
import pickle

import streamlit as st

from mecastruct.core.data_manager import DataManager
from mecastruct.services.examples import loadExample
from mecastruct.services.project_io import PROJECT_KEYS as ONGLETS


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
    """Enregistre le dernier résultat de calcul de l'onglet `tab` et la saisie qui l'a donné (voir is_current)."""
    st.session_state["res"][tab] = res
    st.session_state[f"saisie_calculee_{tab}"] = repr(st.session_state["saisie"].get(tab))


def is_current(tab: str) -> bool:
    """Vrai si l'onglet `tab` a un résultat calculé avec la saisie actuelle (sinon la saisie a changé depuis)."""
    return result(tab) is not None and st.session_state.get(f"saisie_calculee_{tab}") == repr(
        st.session_state["saisie"].get(tab)
    )


def result(tab: str) -> dict | None:
    """Dernier résultat de l'onglet `tab`, ou None s'il n'a pas encore été calculé."""
    return st.session_state["res"].get(tab)


def reset_widgets(tab: str) -> None:
    """Supprime de st.session_state les clés de widgets de l'onglet `tab` (à appeler avant un st.rerun)."""
    prefixe = f"{tab}."
    for cle in [k for k in st.session_state.keys() if k.startswith(prefixe)]:
        del st.session_state[cle]


HISTORIQUE_MAX = 10


def push_beam_history() -> None:
    """Empile la saisie Poutres courante (état de départ, après un calcul ou un exemple) ; ignore un état identique."""
    h = st.session_state.setdefault("beam_history", [])
    pos = st.session_state.get("beam_history_pos", -1)
    snap = copy.deepcopy(saisie("Beam"))
    if 0 <= pos < len(h) and pickle.dumps(h[pos]) == pickle.dumps(snap):
        return
    del h[pos + 1 :]  # un nouvel état efface ce qui pouvait être rétabli
    h.append(snap)
    del h[:-HISTORIQUE_MAX]
    st.session_state["beam_history_pos"] = len(h) - 1


def move_beam_history(step: int) -> str:
    """Annule (step = -1) ou rétablit (step = +1) la saisie Poutres ; renvoie le message d'état."""
    h = st.session_state.get("beam_history", [])
    cible = st.session_state.get("beam_history_pos", -1) + step
    if not 0 <= cible < len(h):
        return "Rien à annuler." if step < 0 else "Rien à rétablir."
    st.session_state["saisie"]["Beam"] = copy.deepcopy(h[cible])
    st.session_state["beam_history_pos"] = cible
    reset_widgets("Beam")
    verbe = "annulée" if step < 0 else "rétablie"
    return f"Modification {verbe}. Cliquez sur « Calculer » pour mettre à jour les résultats."
