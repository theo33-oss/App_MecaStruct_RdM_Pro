"""Page « Base de données » : matériaux, profilés, pressions de matage, abaques Kt, données utilisateur, documents.

Port des onglets de MecaStruct_App.m (buildDatabaseTab, refreshMaterialTable, refreshProfileTable, addMaterialFromForm,
addProfileFromForm, computeKt). Unités d'affichage comme MATLAB : GPa, MPa, mm, cm², cm⁴, cm³.
Les ajouts de l'utilisateur ne sont pas conservés sur le serveur : il faut télécharger le fichier JSON.
"""

import json
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mecastruct.core import kt_mohr
from mecastruct.core.errors import MecaStructError
from mecastruct.plots.other_plots import ktChart
from mecastruct.services import compute
from mecastruct.ui import state
from mecastruct.ui.widgets import error_box

state.init()
dm = st.session_state["dm"]
DOCS = Path(__file__).resolve().parents[2] / "docs"


def _message_suivant(texte: str) -> None:
    """Message affiché au prochain passage (après un st.rerun qui rafraîchit les tableaux)."""
    st.session_state["db.message"] = texte


def _affiche_message() -> None:
    """Affiche le message mis en attente par _message_suivant, puis l'efface."""
    texte = st.session_state.pop("db.message", None)
    if texte:
        st.success(texte)


def _materiaux() -> None:
    """Tableau des matériaux (filtre par catégorie et recherche), formulaire d'ajout, suppression d'un ajout."""
    T = dm.Materials
    categories = sorted(T["Category"].dropna().unique())
    choisies = st.multiselect("Catégorie", categories, default=categories, key="db.categories")
    recherche = st.text_input("Rechercher un matériau", key="db.recherche")
    vue = T[T["Category"].isin(choisies)]
    if recherche:
        vue = vue[vue["Name"].str.contains(recherche, case=False, regex=False)]
    st.dataframe(
        pd.DataFrame(
            {
                "Nom": vue["Name"],
                "Catégorie": vue["Category"],
                "E (GPa)": vue["E"] / 1e9,
                "G (GPa)": vue["G"] / 1e9,
                "ν (-)": vue["nu"],
                "Re (MPa)": vue["Re"] / 1e6,
                "Rm (MPa)": vue["Rm"] / 1e6,
                "α (1e-6/°C)": vue["alpha"] * 1e6,
                "ρ (kg/m³)": vue["rho"],
                "Ajouté par": vue["Author"],
                "Note": vue["Note"],
            }
        ),
        hide_index=True,
    )

    with st.form("form_materiau"):
        st.subheader("Ajouter un matériau utilisateur")
        nom = st.text_input("Nom", value="Acier utilisateur", key="mat_nom")
        categorie = st.text_input("Catégorie", value="Utilisateur", key="mat_cat")
        E = st.number_input("E (GPa)", value=210.0, key="mat_E")
        G = st.number_input("G (GPa), 0 = calculé par G = E/(2(1+ν))", value=0.0, key="mat_G")
        nu = st.number_input("ν (-)", value=0.3, min_value=-0.999, max_value=0.499, key="mat_nu")
        Re = st.number_input("Re (MPa)", value=300.0, key="mat_Re")
        Rm = st.number_input("Rm (MPa)", value=500.0, key="mat_Rm")
        alpha = st.number_input("α (10⁻⁶/°C)", value=12.0, key="mat_alpha")
        rho = st.number_input("ρ (kg/m³)", value=7850.0, key="mat_rho")
        auteur = st.text_input("Ajouté par", value="Utilisateur", key="mat_auteur")
        if st.form_submit_button("Ajouter / remplacer"):
            try:
                dm.addMaterial(
                    {
                        "Name": nom.strip(),
                        "Category": categorie.strip() or "Utilisateur",
                        "E": E * 1e9,
                        "G": G * 1e9 if G > 0 else math.nan,
                        "nu": nu,
                        "Re": Re * 1e6,
                        "Rm": Rm * 1e6,
                        "alpha": alpha * 1e-6,
                        "rho": rho,
                        "Note": "Matériau utilisateur (saisi dans l'interface).",
                        "Author": auteur.strip(),
                    }
                )
                _message_suivant(f"Matériau « {nom.strip()} » ajouté.")
                st.rerun()
            except MecaStructError as err:
                error_box(err)

    ajouts = dm.Materials.loc[dm.Materials["IsUser"], "Name"].tolist()
    if ajouts:
        cible = st.selectbox("Supprimer un matériau utilisateur", ajouts, key="mat_suppr")
        if st.button("Supprimer le matériau utilisateur choisi", key="mat_suppr_bouton"):
            dm.removeMaterial(cible)
            _message_suivant(f"Matériau « {cible} » supprimé.")
            st.rerun()
    else:
        st.caption("Aucun matériau utilisateur à supprimer.")


def _profiles() -> None:
    """Tableau d'une famille de profilés (unités de MATLAB), formulaire d'ajout d'un profilé utilisateur."""
    famille = st.selectbox("Famille de profilés", dm.listProfileFamilies(), key="pro_fam")
    st.caption("Convention : Iz = axe fort (= Iy Eurocode), Iy = axe faible.")
    T = dm.Profiles[famille]
    st.dataframe(
        pd.DataFrame(
            {
                "Désignation": T["Name"],
                "h (mm)": T["h"] * 1e3,
                "b (mm)": T["b"] * 1e3,
                "a (mm)": T["a"] * 1e3,
                "e (mm)": T["e"] * 1e3,
                "r (mm)": T["r"] * 1e3,
                "S (cm²)": T["S"] * 1e4,
                "Iz (cm⁴)": T["Iz"] * 1e8,
                "Iy (cm⁴)": T["Iy"] * 1e8,
                "Wz (cm³)": T["Wz"] * 1e6,
                "Wy (cm³)": T["Wy"] * 1e6,
                "rz (mm)": T["rz"] * 1e3,
                "ry (mm)": T["ry"] * 1e3,
                "masse (kg/m)": T["mass"],
                "c (mm)": T["c"] * 1e3,
                "Ajouté par": T["Author"],
            }
        ),
        hide_index=True,
    )
    with st.form("form_profil"):
        st.subheader(f"Ajouter un profilé utilisateur ({famille})")
        nom = st.text_input("Désignation", value="IPE 210 util", key="pro_nom")
        h = st.number_input("h (mm)", value=210.0, key="pro_h")
        b = st.number_input("b (mm)", value=105.0, key="pro_b")
        a = st.number_input("a — âme (mm)", value=6.0, key="pro_a")
        e = st.number_input("e — aile (mm)", value=9.0, key="pro_e")
        r = st.number_input("r — congé (mm)", value=12.0, key="pro_r")
        auteur = st.text_input("Ajouté par", value="Utilisateur", key="pro_auteur")
        st.caption("S, Iz, Iy, W et r sont calculés sur la géométrie simplifiée (épaisseurs constantes).")
        if st.form_submit_button("Ajouter le profilé"):
            try:
                dm.addProfile(
                    famille,
                    {
                        "Name": nom.strip(),
                        "h": h * 1e-3,
                        "b": b * 1e-3,
                        "a": a * 1e-3,
                        "e": e * 1e-3,
                        "r": r * 1e-3,
                        "Author": auteur.strip(),
                    },
                )
                _message_suivant(f"Profilé « {nom.strip()} » ajouté à la famille {famille}.")
                st.rerun()
            except MecaStructError as err:
                error_box(err)


def _matage() -> None:
    """Table des pressions de matage admissibles et lecture de Pmin, Pmax pour une liaison et des conditions."""
    B = dm.BearingPressures
    st.dataframe(
        pd.DataFrame(
            {
                "Liaison": B["Liaison"],
                "Conditions": B["Conditions"],
                "Pmin (MPa)": B["Pmin"] / 1e6,
                "Pmax (MPa)": B["Pmax"] / 1e6,
                "Note": B["Note"],
            }
        ),
        hide_index=True,
    )
    liaison = st.selectbox("Liaison", list(dict.fromkeys(B["Liaison"])), key="mat_liaison")
    conditions = st.selectbox(
        "Conditions de fonctionnement", list(dict.fromkeys(B["Conditions"])), key="mat_conditions"
    )
    try:
        pmin, pmax = dm.getBearingPressure(liaison, conditions)
        st.metric("Pmin (matage admissible)", f"{pmin / 1e6:.4g} MPa")
        st.metric("Pmax (matage admissible)", f"{pmax / 1e6:.4g} MPa")
    except MecaStructError as err:
        error_box(err)


def _abaques_kt() -> None:
    """Choix d'un abaque et de ses paramètres, calcul de Kt, graphique avec le point calculé."""
    charts = kt_mohr.ktCharts()
    titres = {c["id"]: c["title"] for c in charts}
    ids = list(titres)
    choix = st.selectbox(
        "Abaque", ids, index=ids.index("arbre_epaulement_flexion"), format_func=titres.get, key="kt_id"
    )
    ch = next(c for c in charts if c["id"] == choix)
    st.markdown(ch["description"])
    st.latex(ch["latex"].strip().strip("$"))
    plaque = choix == "plaque_trou_traction"
    if plaque:
        p1 = st.number_input("d/W (-)", value=0.3, min_value=0.0, max_value=0.999, key="kt_p1_plaque")
        prm = p1
    else:
        p1 = st.number_input("r/d (-)", value=0.1, min_value=0.01, max_value=0.3, key="kt_p1_arbre")
        p2 = st.number_input("D/d (-)", value=1.5, min_value=1.01, max_value=6.0, key="kt_p2_arbre")
        prm = [p1, p2]
    try:
        res = compute.computeKt(choix, prm)["result"]
    except MecaStructError as err:
        error_box(err)
        return
    fig = ktChart(choix)
    fig.add_trace(
        go.Scatter(
            x=[p1],
            y=[res["Kt"]],
            mode="markers",
            marker=dict(size=12, color="rgb(217,84,26)"),
            name=f"K<sub>t</sub> = {res['Kt']:.4g}",
        )
    )
    st.metric("Kt", f"{res['Kt']:.4g}")
    st.plotly_chart(fig)
    st.text("\n".join(res["rapport"]))


def _donnees_utilisateur() -> None:
    """Téléchargement et rechargement des ajouts (JSON). Rien n'est conservé sur le serveur."""
    st.info("Les ajouts ne sont pas conservés sur le serveur : téléchargez le fichier pour les retrouver plus tard.")
    st.download_button(
        "Enregistrer mes ajouts (.json)",
        data=json.dumps(dm.exportUserData(), ensure_ascii=False, indent=2),
        file_name="mecastruct_donnees_utilisateur.json",
        mime="application/json",
    )
    fichier = st.file_uploader("Recharger mes ajouts", type="json", key="donnees_fichier")
    if fichier is not None and st.button("Importer ce fichier", key="donnees_importer"):
        try:
            n = dm.importUserData(json.load(fichier))
            _message_suivant(f"{n} ajout(s) importé(s).")
            st.rerun()
        except MecaStructError as err:
            error_box(err)
        except json.JSONDecodeError:
            st.error("Fichier illisible : ce n'est pas un fichier JSON valide.")


def _documents() -> None:
    """Liens de téléchargement de la note de calcul et du guide, lus dans le dossier docs du dépôt."""
    for nom, libelle in (("NOTE_DE_CALCUL.html", "Note de calcul"), ("GUIDE_UTILISATEUR.html", "Guide d'utilisation")):
        chemin = DOCS / nom
        if chemin.exists():
            st.download_button(f"Télécharger : {libelle}", data=chemin.read_bytes(), file_name=nom, mime="text/html")
        else:
            st.caption(f"{nom} absent du dépôt.")


st.title("Base de données")
_affiche_message()
onglets = st.tabs(["Matériaux", "Profilés", "Pressions de matage", "Abaques Kt", "Mes données", "Documents"])
with onglets[0]:
    _materiaux()
with onglets[1]:
    _profiles()
with onglets[2]:
    _matage()
with onglets[3]:
    _abaques_kt()
with onglets[4]:
    _donnees_utilisateur()
with onglets[5]:
    _documents()
