"""Briques d'interface réutilisables : champs liés à la saisie, tableaux éditables, rapports, formules, erreurs.

Chaque champ est lié à saisie[onglet][champ] par sa clé de widget « onglet.champ » : la valeur saisie est recopiée
dans la saisie à chaque passage.
"""

import math
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any, NamedTuple

import pandas as pd
import streamlit as st

from mecastruct.core.errors import MecaStructError
from mecastruct.services import compute, project_io, validation_report
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


def agent_mobile() -> bool:
    """Vrai sur téléphone ou tablette d'après le User-Agent (Streamlit n'expose pas la largeur d'écran côté Python)."""
    try:
        agent = st.context.headers.get("User-Agent", "")
    except Exception:  # hors session (test d'un module seul) : affichage ordinateur
        return False
    return any(marque in agent for marque in ("Mobi", "Android", "iPhone", "iPad"))


def is_compact() -> bool:
    """Mode compact : choix de l'interrupteur de la barre latérale, sinon détection par le User-Agent."""
    try:
        return bool(st.session_state.get("mode_compact", agent_mobile()))
    except Exception:  # hors session
        return False


def plot(fig: Any, **kw) -> None:
    """Graphique Plotly : sur mobile, sans barre d'outils, sans zoom (le doigt fait défiler la page), moins haut."""
    if is_compact():
        fig.update_layout(
            height=max(300, int((fig.layout.height or 450) * 0.75)),
            margin={"l": 40, "r": 8, "b": 70},
            legend={"orientation": "h", "y": -0.2, "x": 0},
            dragmode=False,
        )
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        config = {"displayModeBar": False, "scrollZoom": False, "responsive": True}
    else:
        config = {"displaylogo": False, "scrollZoom": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
    st.plotly_chart(fig, config=config, **kw)


def synthese(valeurs: list[dict]) -> None:
    """Rangée de st.metric (dicts label, value, delta facultatifs) ; passe à la ligne si la place manque."""
    with st.container(horizontal=True):
        for v in valeurs:
            st.metric(border=True, delta_arrow="off", **v)


_MORCEAU = re.compile(r"^(?P<label>[^=:]{1,25}?) = (?P<value>[^()]+?)(?: \((?P<note>[^()]+)\))?$")


def synthese_statut(status: str) -> None:
    """Rangée de st.metric tirée d'une ligne d'état « A = 1 u, B = 2 u (vérifié) — C = 3 u » ; rien sans « x = y »."""
    valeurs = []
    for morceau in re.split(r",\s|\s—\s", status):
        m = _MORCEAU.match(morceau.strip())
        if m is None:
            continue
        valeur, _, verdict = m["value"].partition(" : ")
        note = (m["note"] or verdict).strip()
        v = {"label": m["label"].strip(), "value": valeur.strip()}
        if note:
            v["delta"] = note
            v["delta_color"] = {"vérifié": "green", "NON vérifié": "red"}.get(note, "off")
        valeurs.append(v)
    if valeurs:
        synthese(valeurs)


def synthese_resultat(tab: str, conteneur: Any) -> None:
    """Remplit `conteneur` (réservé sous « Calculer ») avec les valeurs clés du résultat de l'onglet `tab`."""
    res = state.result(tab)
    if isinstance(res, dict) and res.get("status"):
        with conteneur:
            synthese_statut(res["status"])


def calc_button(key: str, label: str = "Calculer") -> bool:
    """Bouton principal pleine largeur, à placer en haut de la colonne de saisie ; True au clic.

    Le calcul se lance plus bas, une fois les champs affichés : la saisie est alors à jour.
    """
    return st.button(label, key=key, type="primary", width="stretch", icon=":material/calculate:")


def tabs(contenus: list[tuple[str, Callable[[], Any]]]) -> None:
    """Affiche des onglets ; `contenus` = liste de (titre, fonction d'affichage sans argument)."""
    for onglet, (_, affiche) in zip(st.tabs([titre for titre, _ in contenus]), contenus, strict=True):
        with onglet:
            affiche()


def graphs(key: str, contenus: list[tuple[str, Callable[[], Any]]], dessous: tuple[str, ...] = ()) -> list:
    """Graphiques les uns sous les autres, chacun avec son titre ; l'interrupteur « Graphiques en onglets » les groupe.

    Les titres de `dessous` ne sont pas tracés en mode empilé : ils sont renvoyés, pour que l'appelant les range avec
    ses propres onglets (en mode onglets, ils restent dans les onglets des graphiques et la liste renvoyée est vide).
    """
    en_onglets = len(contenus) > 1 and st.toggle("Graphiques en onglets", key=key)
    if en_onglets:
        tabs(contenus)
        return []
    for titre, affiche in contenus:
        if titre not in dessous:
            st.subheader(titre)
            affiche()
    return [c for c in contenus if c[0] in dessous]


POSITIONS = ("Haut", "Bas")


class Volet(NamedTuple):
    """Un volet de saisie : clé, titre, position par défaut (« Haut » ou « Bas »), ouvert par défaut, affichage."""

    cle: str
    titre: str
    defaut: str
    ouvert: bool
    saisie: Callable[[], None]


def _cle_position(page: str, volet: Volet) -> str:
    return f"mise_en_page.{page}.{volet.cle}"  # hors du préfixe « page. » : un exemple chargé ne la vide pas


def _raz_mise_en_page(page: str, volets: list[Volet]) -> None:
    """Remet le découpage par défaut (callback du bouton)."""
    for v in volets:
        st.session_state[_cle_position(page, v)] = v.defaut


def panels(page: str, volets: list[Volet]) -> None:
    """Volets de saisie en deux zones (haut, puis « Fonctions avancées ») et volet « Mise en page » pour les déplacer.

    Les positions sont gardées dans st.session_state["mise_en_page"][page] : elles survivent à un changement de page.
    Dans chaque zone, les volets suivent l'ordre de `volets`.
    """
    stock = st.session_state.setdefault("mise_en_page", {}).setdefault(page, {})
    for v in volets:
        cle = _cle_position(page, v)
        if cle not in st.session_state:  # première visite, ou widget supprimé par un changement de page
            st.session_state[cle] = stock.get(v.cle, v.defaut)
        stock[v.cle] = st.session_state[cle]
    haut = [v for v in volets if stock[v.cle] == "Haut"]
    bas = [v for v in volets if stock[v.cle] != "Haut"]
    for zone in (haut, bas):
        if zone is bas and bas:
            st.subheader("Fonctions avancées")
        for v in zone:
            with st.expander(v.titre, expanded=v.ouvert):
                v.saisie()
    with st.expander("Mise en page"):
        st.caption("Pour chaque volet : en haut de la colonne, ou dans les fonctions avancées en bas.")
        for v in volets:
            st.radio(v.titre, POSITIONS, horizontal=True, key=_cle_position(page, v))
        st.button(
            "Réinitialiser la mise en page",
            key=f"mise_en_page.{page}.raz",
            on_click=_raz_mise_en_page,
            args=(page, volets),
        )


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
    """Volet « Fichiers » (fermé) de l'onglet `tab` : enregistrer, ouvrir, exporter en tableau, en pile verticale."""
    with st.expander("Fichiers"):
        st.download_button(
            "Enregistrer mon problème (.json)",
            lambda: project_io.problemToJson(tab, state.saisie(tab)),  # lu au clic : saisie à jour
            file_name=f"Probleme_{tab}.json",
            mime="application/json",
            key=f"fichier.{tab}.enregistrer",
            on_click="ignore",
            width="stretch",
        )

        def lecture(texte: str) -> str:
            _applique(tab, project_io.problemFromJson(texte, tab)[1])
            return "Problème ouvert."

        if _ouvre(f"{tab}.problème", lecture):
            st.rerun()
        res = state.result(tab)
        feuilles = project_io.resultSheets(tab, res) if res else {}
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
            width="stretch",
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


def _extras_precedents(tab: str) -> dict | None:
    """Résultats facultatifs déjà calculés dans la session (Poutres : combinaisons, Eurocode 3, fatigue, profilé)."""
    if tab != "Beam":
        return None
    cles = {"combos": "BeamCombo", "ec3": "BeamEC3", "fatigue": "BeamFat", "profiles": "BeamProf"}
    return {nom: state.result(cle) for nom, cle in cles.items()}


def _genere_validation(tab: str) -> None:
    """Recalcule la page `tab` avec la saisie actuelle et garde le dossier de validation HTML (callback du bouton)."""
    q = st.session_state
    saisie = state.saisie(tab)
    if tab in ("Cis", "Fle") and state.result("Sec") is not None:  # section de la page Sections, comme au calcul
        saisie["section"] = state.result("Sec")["result"]["sec"]
    try:
        res = validation_report.recompute(tab, saisie, q["dm"], _extras_precedents(tab))
        html = validation_report.generate(tab, saisie, res, q["dm"])
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        q[f"validation.{tab}.erreur"] = err
        q.pop(f"validation.{tab}", None)
        return
    q.pop(f"validation.{tab}.erreur", None)
    q[f"validation.{tab}"] = (validation_report.fileName(tab), html, datetime.now().strftime("%H:%M:%S"))


def validation_button(tab: str) -> None:
    """« Dossier de validation de ce problème » : recalcule la page, puis propose le fichier HTML à télécharger.

    Actif seulement s'il y a un résultat pour l'onglet `tab`. Le PDF s'obtient par Imprimer → Enregistrer en PDF.
    """
    res = state.result(tab)
    st.button(
        "Dossier de validation de ce problème",
        key=f"validation.{tab}.bouton",
        on_click=_genere_validation,
        args=(tab,),
        disabled=res is None,
        help=None if res else "Cliquez d'abord sur « Calculer ».",
    )
    err = st.session_state.get(f"validation.{tab}.erreur")
    if err is not None:
        error_box(err)
    dossier = st.session_state.get(f"validation.{tab}")
    if dossier is not None:
        nom, html, heure = dossier
        st.download_button(
            f"Télécharger le dossier ({nom})",
            html,
            file_name=nom,
            mime="text/html",
            key=f"validation.{tab}.telecharger",
            on_click="ignore",
        )
        st.caption(
            f"Dossier généré à {heure} avec la saisie de ce moment. Formules affichées par MathJax (connexion "
            "Internet requise). Pour un PDF : ouvrir le fichier, Imprimer → Enregistrer en PDF."
        )
