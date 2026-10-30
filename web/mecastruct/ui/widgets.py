"""Briques d'interface réutilisables : champs liés à la saisie, tableaux éditables, rapports, formules, erreurs.

Chaque champ est lié à saisie[onglet][champ] par sa clé de widget « onglet.champ » : la valeur saisie est recopiée
dans la saisie à chaque passage.
"""

from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from mecastruct.core.errors import MecaStructError
from mecastruct.services.examples import exampleNames, loadExample
from mecastruct.ui import state

# Conseils de correction par fin d'identifiant d'erreur (port de errorHint de MecaStruct_App.m)
_CONSEILS = {
    "mechanism": "la structure peut bouger. Ajoutez un appui ou un encastrement, ou changez le type d'un appui "
    "(voir la légende sous le tableau des appuis).",
    "invalidSupport": "vérifiez le tableau des appuis : type connu et position comprise entre 0 et L.",
    "invalidModel": "une donnée est incohérente (position hors de la poutre, case vide, valeur nulle). "
    "Relisez les tableaux et la longueur L.",
    "invalidExpression": "dans les cases de valeurs, utilisez seulement des nombres, x et + - * / ^ ( ).",
    "invalidDimensions": "vérifiez les dimensions de la section (toutes positives, épaisseurs plus petites que la "
    "largeur).",
}


def _lie(tab: str, champ: str, widget: Callable[..., Any], *args, **kwargs) -> Any:
    """Affiche `widget` lié à saisie[tab][champ] (clé « tab.champ ») et recopie la valeur dans la saisie."""
    cle = f"{tab}.{champ}"
    s = state.saisie(tab)
    if cle not in st.session_state:
        st.session_state[cle] = s[champ]
    valeur = widget(*args, key=cle, **kwargs)
    s[champ] = valeur
    return valeur


def num(tab: str, champ: str, label: str, unit: str = "", help: str | None = None, **kw) -> float:
    """Champ numérique lié à saisie[tab][champ] ; libellé « label (unit) »."""
    libelle = f"{label} ({unit})" if unit else label
    return _lie(tab, champ, st.number_input, libelle, help=help, **kw)


def choice(tab: str, champ: str, label: str, options: list, help: str | None = None) -> str:
    """Liste déroulante liée à saisie[tab][champ]."""
    return _lie(tab, champ, st.selectbox, label, options=options, help=help)


def check(tab: str, champ: str, label: str, help: str | None = None) -> bool:
    """Case à cocher liée à saisie[tab][champ]."""
    return _lie(tab, champ, st.checkbox, label, help=help)


def table(tab: str, champ: str, columns: dict, help: str | None = None) -> list[dict]:
    """Tableau éditable (lignes ajoutables) sur saisie[tab][champ], liste de dicts ; columns = column_config.

    Le tableau de départ est gardé dans « tab.champ.src » : les modifications sont des différences appliquées à
    cette base, donc elle ne doit pas être remplacée à chaque passage (sinon elles seraient appliquées deux fois).
    """
    cle = f"{tab}.{champ}"
    src = f"{cle}.src"
    s = state.saisie(tab)
    if src not in st.session_state:
        st.session_state[src] = pd.DataFrame(s[champ])
    if help:
        st.caption(help)
    edite = st.data_editor(
        st.session_state[src],
        num_rows="dynamic",
        column_config=columns,
        key=cle,
        hide_index=True,
    )
    s[champ] = edite.to_dict("records")
    return s[champ]


def report(lines: list[str]) -> None:
    """Rapport de calcul : les lignes « Résultats » et « Réaction » en encadré, les autres en texte à chasse fixe."""
    for ligne in lines:
        if ligne.startswith(("Résultats", "Réaction")):
            st.info(ligne)
        else:
            st.text(ligne)


def formulas(latex: list[str]) -> None:
    """Formules LaTeX (st.latex), sans les $ de début et de fin."""
    for formule in latex:
        st.latex(formule.strip().strip("$"))


def status(text: str, ok: bool | None = None) -> None:
    """Ligne d'état : verte si ok, rouge si non ok, orange si inconnu (None)."""
    if ok is True:
        st.success(text)
    elif ok is False:
        st.error(text)
    else:
        st.warning(text)


def error_box(err: Exception) -> None:
    """Affiche une erreur de calcul : message et conseil pour MecaStructError, trace complète sinon."""
    if isinstance(err, MecaStructError):
        st.error(err.message)
        conseil = _CONSEILS.get(str(err.identifier).split(":")[-1], "")
        if conseil:
            st.info(f"Conseil : {conseil}")
    else:
        st.exception(err)


def _charge_exemple(tab: str) -> None:
    """Remplace la saisie de l'onglet par l'exemple choisi et supprime les widgets périmés (callback du bouton)."""
    variante = st.session_state.get(f"{tab}.exemple")
    st.session_state["saisie"][tab] = loadExample(tab, variante)
    state.reset_widgets(tab)


def example_picker(tab: str) -> None:
    """Choix d'un exemple d'école (si l'onglet en a plusieurs) et bouton « Charger l'exemple »."""
    noms = exampleNames(tab)
    if noms:
        st.selectbox("Exemple", noms, key=f"{tab}.exemple")
    st.button("Charger l'exemple", key=f"{tab}.charger", on_click=_charge_exemple, args=(tab,))
