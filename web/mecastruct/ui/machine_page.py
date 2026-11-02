"""Squelette commun des pages « Éléments de machines » : saisie, Calculer, résultats et explications du calcul.

Comme le mode Ossature 3D, la saisie vit dans les clés de widgets « <page>.<champ> » et le résultat sous
« <page>.res » avec l'empreinte de la saisie qui l'a donné (résultat périmé signalé).
"""

from collections.abc import Callable
from typing import Any

import streamlit as st

from mecastruct.ui import widgets


def init(page: str, defaut: dict) -> None:
    """Valeurs de départ des champs de `page` (exemple d'école), sans écraser une saisie en cours."""
    for k, v in defaut.items():
        st.session_state.setdefault(f"{page}.{k}", v)


def num(page: str, champ: str, label: str, unite: str = "", **kw) -> None:
    """Champ numérique « label (unité) » de la page."""
    st.number_input(f"{label} ({unite})" if unite else label, key=f"{page}.{champ}", format="%.6g", **kw)


def saisie(page: str, defaut: dict) -> dict:
    """Saisie courante de `page` (mêmes clés que `defaut`)."""
    return {k: st.session_state.get(f"{page}.{k}", v) for k, v in defaut.items()}


def calcul(page: str, s: dict, travail: Callable[[dict], dict]) -> None:
    """Bouton « Calculer » ; garde le résultat et l'empreinte de la saisie, ou affiche l'erreur."""
    if widgets.calc_button(f"{page}.calc"):
        try:
            st.session_state[f"{page}.res"] = {"res": travail(s), "empreinte": repr(s)}
        except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
            st.session_state.pop(f"{page}.res", None)
            widgets.error_box(err)


def apercu(dessin: Callable[[], Any]) -> None:
    """Schéma dessiné d'après la saisie actuelle : il suit chaque valeur modifiée, avant même « Calculer »."""
    try:
        fig = dessin()
    except Exception as err:  # saisie incomplète ou hors du domaine dessinable : le schéma est seulement omis
        st.caption(f"Schéma indisponible : {getattr(err, 'message', err)}")
        return
    widgets.plot(fig)


def resultats(page: str, s: dict, graphique: Callable[[dict], Any] | None = None) -> None:
    """Ligne d'état, graphique, synthèse et explications du calcul (formules remplies et démarche)."""
    calc = st.session_state.get(f"{page}.res")
    if calc is None:
        st.info("Renseignez les données, puis cliquez sur « Calculer ».")
        return
    if calc["empreinte"] != repr(s):
        st.warning(
            "Saisie modifiée depuis le dernier calcul : les résultats affichés datent de l'ancienne saisie. "
            "Cliquez sur « Calculer » pour les actualiser."
        )
    res = calc["res"]
    widgets.status(res["status"], res["ok"])
    onglets = [("Synthèse", lambda: st.dataframe(res["tables"]["Synthèse"], hide_index=True))]
    if graphique is not None:
        onglets.insert(0, ("Graphique", lambda: widgets.plot(graphique(res["result"]))))
    onglets.append(("Explications du calcul", lambda: explications(res)))
    widgets.tabs(onglets)


def explications(res: dict) -> None:
    """Formules appliquées aux données (avec les valeurs), puis la démarche détaillée du moteur."""
    st.markdown("**Formules appliquées à vos données**")
    widgets.formulas(res["result"]["latex"])
    st.markdown("**Démarche**")
    for ligne in res["result"]["rapport"][1:]:
        st.markdown(f"- {ligne}")
