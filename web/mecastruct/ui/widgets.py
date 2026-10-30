"""Briques d'interface réutilisables : champs liés à la saisie, tableaux éditables, rapports, formules, erreurs.

Chaque champ est lié à saisie[onglet][champ] par sa clé de widget « onglet.champ » : la valeur saisie est recopiée
dans la saisie à chaque passage.
"""

import math
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from mecastruct.core.errors import MecaStructError
from mecastruct.services import compute, project_io
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


def choice(
    tab: str,
    champ: str,
    label: str,
    options: list,
    help: str | None = None,
    format_func: Callable | None = None,
    **kw,
) -> str:
    """Liste déroulante liée à saisie[tab][champ] ; format_func donne le libellé affiché de chaque option."""
    extra = {"format_func": format_func} if format_func is not None else {}
    return _lie(tab, champ, st.selectbox, label, options=options, help=help, **extra, **kw)


def check(tab: str, champ: str, label: str, help: str | None = None, **kw) -> bool:
    """Case à cocher liée à saisie[tab][champ]."""
    return _lie(tab, champ, st.checkbox, label, help=help, **kw)


def text(tab: str, champ: str, label: str, help: str | None = None, **kw) -> str:
    """Champ texte lié à saisie[tab][champ]."""
    return _lie(tab, champ, st.text_input, label, help=help, **kw)


def table(tab: str, champ: str, columns: dict, help: str | None = None) -> list[dict]:
    """Tableau éditable (lignes ajoutables) sur saisie[tab][champ], liste de dicts ; columns = column_config.

    Le tableau de départ est gardé dans « tab.champ.src » : les modifications sont des différences appliquées à
    cette base, donc elle ne doit pas être remplacée à chaque passage (sinon elles seraient appliquées deux fois).
    """
    cle = f"{tab}.{champ}"
    src = f"{cle}.src"
    s = state.saisie(tab)
    if src not in st.session_state:
        st.session_state[src] = pd.DataFrame(s[champ], columns=list(columns) if not s[champ] else None)
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
    if tab == "Beam":
        state.push_beam_history()


def example_picker(tab: str) -> None:
    """Choix d'un exemple d'école (si l'onglet en a plusieurs) et bouton « Charger l'exemple »."""
    noms = exampleNames(tab)
    if noms:
        st.selectbox("Exemple", noms, key=f"{tab}.exemple")
    st.button("Charger l'exemple", key=f"{tab}.charger", on_click=_charge_exemple, args=(tab,))


def choice_materiau(tab: str, champs: list[str], dm: Any, label: str = "Matériau", **kw) -> str:
    """Liste des matériaux liée à saisie[tab]["mat"] ; un changement remplit les champs `champs` (E, G, Re…)."""

    def applique() -> None:
        for champ, valeur in compute._materiau(dm, st.session_state[f"{tab}.mat"], champs).items():
            if math.isfinite(valeur):  # comme applyMaterial : un champ inconnu de la base reste inchangé
                st.session_state[f"{tab}.{champ}"] = valeur

    return choice(tab, "mat", label, dm.listMaterials(), on_change=applique, **kw)


def page_link(page: str, label: str, icon: str | None = None) -> None:
    """Lien vers une page de l'application ; omis hors de la navigation (test d'une page seule)."""
    try:
        st.page_link(page, label=label, icon=icon)
    except st.errors.StreamlitAPIException:
        pass


def _applique(tab: str, saisie: dict) -> None:
    """Remplace la saisie de l'onglet par celle d'un fichier (champs absents : exemple) et vide ses widgets."""
    st.session_state["saisie"][tab] = {**loadExample(tab), **saisie}
    state.reset_widgets(tab)
    if tab == "Beam":  # resetBeamHistory : l'historique repart du problème ouvert
        st.session_state.pop("beam_history", None)
        state.push_beam_history()


def _ouvre(cle: str, lecture: Callable[[str], str]) -> bool:
    """Lit le fichier déposé dans l'uploader `cle` une seule fois ; `lecture(texte)` renvoie un message de succès.

    Erreur de lecture : message rouge sous l'uploader. Succès : le message est gardé pour le passage suivant et la page
    se relance (les widgets repartent de la nouvelle saisie). Renvoie False tant qu'il n'y a rien de neuf.
    """
    fichier = st.file_uploader("Ouvrir (.json)", type="json", key=f"fichier.{cle}", label_visibility="collapsed")
    if fichier is None or st.session_state.get(f"fichier.{cle}.lu") == fichier.file_id:
        return False
    st.session_state[f"fichier.{cle}.lu"] = fichier.file_id
    try:
        st.session_state[f"fichier.{cle}.msg"] = lecture(fichier.getvalue().decode("utf-8-sig"))
    except (MecaStructError, UnicodeDecodeError) as err:
        st.error(getattr(err, "message", "Ce fichier n'est pas un fichier texte JSON."))
        return False
    return True


def file_bar(tab: str) -> None:
    """Ligne « Enregistrer mon problème / Ouvrir un problème / Exporter en tableau » de l'onglet `tab`."""
    colonnes = st.columns(3)
    with colonnes[0]:
        st.download_button(
            "Enregistrer mon problème (.json)",
            lambda: project_io.problemToJson(tab, state.saisie(tab)),  # lu au clic : saisie à jour
            file_name=f"Probleme_{tab}.json",
            mime="application/json",
            key=f"fichier.{tab}.enregistrer",
            on_click="ignore",
        )
    with colonnes[1]:

        def lecture(texte: str) -> str:
            _applique(tab, project_io.problemFromJson(texte, tab)[1])
            return "Problème ouvert."

        if _ouvre(f"{tab}.problème", lecture):
            st.rerun()
    res = state.result(tab)
    feuilles = project_io.resultSheets(tab, res) if res else {}
    with colonnes[2]:
        fmt = st.radio("Format d'export", ["xlsx", "csv"], horizontal=True, key=f"fichier.{tab}.format")
        st.download_button(
            "Exporter en tableau",
            (lambda: project_io.toXlsx(feuilles)) if fmt == "xlsx" else (lambda: project_io.toCsvZip(feuilles)),
            file_name=f"MecaStruct_{tab}.{'xlsx' if fmt == 'xlsx' else 'zip'}",
            mime="application/octet-stream",
            key=f"fichier.{tab}.exporter",
            on_click="ignore",
            disabled=not feuilles,
            help=None if feuilles else "Aucun résultat à exporter : cliquez d'abord sur « Calculer ».",
        )
    msg = st.session_state.pop(f"fichier.{tab}.problème.msg", None)
    if msg:
        st.success(msg)


def project_bar() -> None:
    """Accueil : « Enregistrer tout le projet » et « Ouvrir un projet » (les onglets non relus sont signalés)."""
    st.download_button(
        "Enregistrer tout le projet (.json)",
        lambda: project_io.projectToJson(st.session_state["saisie"]),
        file_name="Projet_MecaStruct.json",
        mime="application/json",
        key="projet.enregistrer",
        on_click="ignore",
    )
    st.caption("Ouvrir un projet")

    def lecture(texte: str) -> str:
        saisies, echecs = project_io.projectFromJson(texte)
        for tab, saisie in saisies.items():
            _applique(tab, saisie)
        if echecs:
            return "Onglets non restaurés (version différente) : " + ", ".join(echecs)
        return "Projet ouvert."

    if _ouvre("projet", lecture):
        st.rerun()
    msg = st.session_state.pop("fichier.projet.msg", None)
    if msg:
        (st.warning if msg.startswith("Onglets") else st.success)(msg)
