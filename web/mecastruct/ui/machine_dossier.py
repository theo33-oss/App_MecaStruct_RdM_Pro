"""Bouton « Dossier de validation de cette page » des pages de cours « Éléments de machines ».

Chaque calcul de la page garde son résultat sous « <clé>.res » = {res, empreinte de la saisie} (machine_page.calcul).
Le dossier réunit les calculs dont le résultat est à jour, sans les recalculer (services/machine_validation.py).
"""

from datetime import datetime

import streamlit as st

from mecastruct.services import machine_validation
from mecastruct.ui import widgets


def _etat(calculs: list[tuple[str, str, dict, str]]) -> tuple[list[tuple], tuple]:
    """Calculs pour machine_validation.generate (résultat None s'il n'est pas à jour) et leurs empreintes."""
    liste, empreintes = [], []
    for cle, nom, defaut, typ in calculs:
        s = {k: st.session_state.get(f"{cle}.{k}", v) for k, v in defaut.items()}  # comme machine_page.saisie
        calc = st.session_state.get(f"{cle}.res")
        res = calc["res"] if calc is not None and calc["empreinte"] == repr(s) else None
        liste.append((nom, typ, s, res))
        empreintes.append(None if res is None else repr(s))
    return liste, tuple(empreintes)


def _genere(nom: str, titre: str, calculs: list[tuple[str, str, dict, str]]) -> None:
    """Écrit le dossier avec les résultats à jour et le garde sous « validation.<nom> » (callback du bouton)."""
    q = st.session_state
    liste, empreintes = _etat(calculs)
    try:
        html = machine_validation.generate(titre, liste, q["dm"])
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        q[f"validation.{nom}.erreur"] = err
        q.pop(f"validation.{nom}", None)
        return
    q.pop(f"validation.{nom}.erreur", None)
    heure = datetime.now().strftime("%H:%M:%S")
    q[f"validation.{nom}"] = (machine_validation.fileName(titre), html, heure, empreintes)


def bouton(nom: str, titre: str, calculs: list[tuple[str, str, dict, str]]) -> None:
    """« Dossier de validation de cette page », puis le fichier HTML à télécharger tant que la saisie n'a pas changé.

    Entrées : nom (clé du dossier en session), titre (de la page), calculs = [(clé du calcul, titre du calcul, saisie
    par défaut, type de machine_validation.TYPES)]. Actif si au moins un calcul a un résultat à jour.
    """
    liste, empreintes = _etat(calculs)
    absents = [n for n, _, _, res in liste if res is None]
    st.button(
        "Dossier de validation de cette page",
        key=f"validation.{nom}.bouton",
        on_click=_genere,
        args=(nom, titre, calculs),
        disabled=len(absents) == len(liste),
        help="Cliquez d'abord sur « Calculer » dans au moins un onglet." if len(absents) == len(liste) else None,
    )
    if absents and len(absents) < len(liste):
        st.caption(f"Non inclus dans le dossier (pas de résultat à jour) : {', '.join(absents)}.")
    err = st.session_state.get(f"validation.{nom}.erreur")
    if err is not None:
        widgets.error_box(err)
    dossier = st.session_state.get(f"validation.{nom}")
    if dossier is not None and dossier[3] != empreintes:  # le dossier ne correspond plus à la page
        dossier = None
    widgets.dossier_download(f"validation.{nom}", dossier)
