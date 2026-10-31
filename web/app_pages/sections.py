"""Page « Sections droites » : caractéristiques de la section (3 méthodes), contraintes σ(y) et τ(y), transfert.

Port de l'onglet « Sections » de MecaStruct_App.m (buildSectionsTab, computeSection, applySectionPreset,
useSectionForBeam). Disposition commune aux pages de calcul : saisie à gauche, résultats à droite.
"""

import pandas as pd
import streamlit as st

from mecastruct.core import geometry
from mecastruct.core.data_manager import sectionPresets
from mecastruct.plots import section_plots
from mecastruct.services import beam_design, beam_services, compute
from mecastruct.ui import state, transfert, widgets
from mecastruct.ui.formula_panel import formula_panel

# Dimensions pertinentes par type (port de relevantDims de MecaStruct_App.m)
DIMENSIONS_PAR_TYPE = {
    "rectangle": ("b", "h"),
    "disque": ("D",),
    "couronne": ("D", "d"),
    "rectangle_creux": ("B", "H", "t"),
    "I": ("h", "b", "tw", "tf"),
    "T": ("h", "b", "tw", "tf"),
    "U": ("h", "b", "tw", "tf"),
    "L": ("h", "b", "t"),
}
LIBELLES_DIMENSIONS = {
    "b": "b — largeur selon z (mm)",
    "h": "h — hauteur selon y (mm)",
    "D": "D — diamètre extérieur (mm)",
    "d": "d — diamètre intérieur (mm)",
    "B": "B — largeur (mm)",
    "H": "H — hauteur (mm)",
    "t": "t — épaisseur (mm)",
    "tw": "tw = a — âme (mm)",
    "tf": "tf = e — aile (mm)",
}
TYPE_PROFILE = "profile"
TYPE_COMPOSITE = "composite"

state.init()
dm = st.session_state["dm"]
saisie = state.saisie("Sec")


def _applique_preset() -> None:
    """Règle le type et les dimensions sur le tube ou la cornière choisi (callback du bouton)."""
    nom = st.session_state["Sec.preset"]
    preset = next(p for p in sectionPresets() if p["name"] == nom)
    s = st.session_state["saisie"]["Sec"]
    s["type"] = preset["type"]
    s.update({cle: float(valeur) for cle, valeur in preset["dims"].items()})
    state.reset_widgets("Sec")


def _calcule() -> None:
    """Calcul de la section avec la saisie courante ; le résultat est gardé pour l'affichage."""
    try:
        state.set_result("Sec", compute.computeSection(saisie, dm))
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop("Sec", None)


def _envoie_vers_poutres() -> None:
    """Transmet la section calculée aux saisies Poutres et Flambage (callback du bouton)."""
    envoi = transfert.envoie_section(dm)
    if envoi is not None:
        st.session_state["Sec.envoye"] = envoi


def _efforts_poutre(mode: str) -> None:
    """Remplit N, Mfz, Mfy, Ty avec les efforts de la poutre, recalculée d'abord (loadFromBeam de MATLAB).

    mode : 'abscisse' (coupure en s0) ou 'max' (point le plus sollicité). Le message est gardé dans « Sec_msg ».
    """
    cible = st.session_state["saisie"]["Sec"]
    cible["s0"] = st.session_state.get("Sec.s0", cible["s0"])
    try:
        res = beam_services.computeBeam(state.saisie("Beam"), dm)
        state.set_result("Beam", res)
        nouvelle = beam_design.loadFromBeam(cible, res, "Sec", mode)
    except Exception as err:  # MecaStructError : abscisse hors de la poutre, poutre incalculable…
        st.session_state["Sec_msg"] = ("error", str(getattr(err, "message", err)))
        return
    st.session_state["saisie"]["Sec"] = nouvelle
    state.reset_widgets("Sec")
    note = "⚠ Résultats NON fiables (hyperstatique, Iyz ≠ 0) — " if res["unreliable"] else ""
    msg = (
        f"{note}Efforts lus sur la poutre en s = {nouvelle['s0']:.4g} m : N = {nouvelle['N']:.4g} kN, "
        f"Mfz = {nouvelle['Mfz']:.4g} kN·m, Mfy = {nouvelle['Mfy']:.4g} kN·m"
    )
    r = state.result("Sec")
    beam = state.saisie("Beam")
    if r is not None and beam["section"] != r["result"]["sec"]:
        iz_sec = r["result"]["P"]["Iz"] * 1e12
        if abs(beam["Iz"] - iz_sec) > 1e-3 * iz_sec:
            msg += (
                f"  ⚠ Attention : la section de la page Sections (Iz = {iz_sec:.4g} mm⁴) diffère de celle de la poutre "
                f"(Iz = {beam['Iz']:.4g} mm⁴) : les contraintes ne concernent pas la même section."
            )
    st.session_state["Sec_msg"] = ("info", msg)


def _saisie_geometrie() -> None:
    """Type de section, profilé du catalogue, préréglages, dimensions pertinentes et sections composées."""
    types = geometry.sectionTypes()
    libelles = {t["type"]: t["label"] for t in types}
    type_choisi = widgets.choice("Sec", "type", "Type de section", list(libelles), format_func=libelles.get)
    if type_choisi == TYPE_PROFILE:
        familles = dm.listProfileFamilies()
        fam = widgets.choice("Sec", "fam", "Famille de profilé", familles)
        profils = dm.listProfiles(fam)
        if saisie["prof"] not in profils:
            saisie["prof"] = profils[0]
            st.session_state.pop("Sec.prof", None)
        widgets.choice("Sec", "prof", "Profilé du catalogue", profils)
    st.caption("Tube ou cornière courant")
    noms_preset = [p["name"] for p in sectionPresets()]
    st.selectbox("Préréglage", noms_preset, key="Sec.preset")
    st.button("Remplir les dimensions du préréglage", key="Sec.preset_bouton", on_click=_applique_preset)

    if type_choisi in DIMENSIONS_PAR_TYPE:
        for champ in DIMENSIONS_PAR_TYPE[type_choisi]:
            widgets.num("Sec", champ, LIBELLES_DIMENSIONS[champ], "mm", min_value=0.0)
    if type_choisi == TYPE_COMPOSITE:
        st.caption("Rectangles pleins (mm) : chaque ligne donne z1, z2, y1, y2 (repère O1, coin bas-gauche).")
        colonnes = {
            cle: st.column_config.NumberColumn(f"{cle} (mm)", format="%.4g") for cle in ("z1", "z2", "y1", "y2")
        }
        widgets.table("Sec", "rects", colonnes)
        st.caption("Trous rectangulaires (mm), même format.")
        widgets.table("Sec", "holes", colonnes)


def _saisie_efforts_et_methode() -> None:
    """Méthode intégrale, matériau, efforts N, Mfz, Mfy, Ty, et Kt pour les contraintes."""
    widgets.choice(
        "Sec",
        "mode",
        "Méthode intégrale",
        ["symbolique", "numerique"],
        format_func=lambda m: {"symbolique": "symbolique (int)", "numerique": "numérique (integral2)"}[m],
    )
    widgets.choice("Sec", "mat", "Matériau", dm.listMaterials())
    widgets.num("Sec", "N", "N : traction > 0", "kN")
    widgets.num("Sec", "Mfz", "Mfz : plan (x, y), fibres du haut comprimées si > 0", "kN·m")
    widgets.num("Sec", "Mfy", "Mfy : plan (x, z), fibres z > 0 tendues si > 0", "kN·m")
    widgets.num("Sec", "Ty", "Ty : tranchant en y", "kN")
    st.markdown("**… ou reprendre les efforts de la poutre calculée**")
    widgets.num(
        "Sec",
        "s0",
        "s sur la poutre",
        "m",
        help="Abscisse de la coupure dans la page Poutres (de 0 à L).",
        min_value=0.0,
    )
    colonnes = st.columns(2)
    colonnes[0].button(
        "Efforts en s",
        key="Sec.efforts_s",
        on_click=_efforts_poutre,
        args=("abscisse",),
        help="Remplit N, Mfz, Mfy, Ty avec les efforts de la poutre à l'abscisse s.",
    )
    colonnes[1].button(
        "Efforts au point critique",
        key="Sec.efforts_max",
        on_click=_efforts_poutre,
        args=("max",),
        help="Remplit N, Mfz, Mfy, Ty avec les efforts de la section la plus sollicitée de la poutre.",
    )
    niveau, message = st.session_state.pop("Sec_msg", (None, None))
    if niveau == "error":
        st.error(message)
    elif niveau:
        st.info(message)
    widgets.num("Sec", "Kt", "Kt (-)", min_value=1.0)


def _resultats(res: dict, tables: dict, statut: str) -> None:
    """Graphiques (section, contraintes) puis résultats (comparaison, Huygens, cisaillement, rapport, formules)."""
    sec, P = res["sec"], res["P"]
    st.success(statut)
    widgets.graphs(
        "Sec_graphes_onglets",
        [
            ("Section", lambda: widgets.plot(section_plots.section(sec, P))),
            (
                "Contraintes σ(y) et τ(y)",
                lambda: widgets.plot(section_plots.sectionStress(sec, P, res["bend"], res["jour"])),
            ),
        ],
    )

    onglets = st.tabs(
        ["Comparaison des méthodes", "Tableau de Huygens", "Facteurs de cisaillement", "Rapport", "Formules"]
    )
    with onglets[0]:
        st.dataframe(tables["Comparaison des méthodes"], hide_index=True)
    with onglets[1]:
        if "Tableau de Huygens" in tables:
            st.dataframe(tables["Tableau de Huygens"], hide_index=True)
        else:
            st.caption("Pas de tableau de Huygens pour cette section.")
    with onglets[2]:
        facteurs = {k: v for k, v in P["shear"].items() if isinstance(v, (int, float, str))}
        st.dataframe(pd.DataFrame([facteurs]).T.rename(columns={0: "Valeur"}))
    with onglets[3]:
        widgets.report(res["rapport"])
    with onglets[4]:
        widgets.formulas(P["latex"])

    if st.button("Utiliser cette section pour une poutre", key="Sec.transfert"):
        _envoie_vers_poutres()
    envoi = st.session_state.pop("Sec.envoye", False)
    if envoi:
        st.success("Section transmise aux pages Poutres et Flambage.")
        if envoi == "principaux":
            st.info("Iyz ≠ 0 : Flambage reçoit les moments principaux I1 et I2 ; Poutres garde Iz, Iy et Iyz.")
        widgets.page_link("app_pages/poutres.py", "Ouvrir Poutres", ":material/horizontal_rule:")
        widgets.page_link("app_pages/flambage.py", "Ouvrir Flambage", ":material/compress:")


st.title("Sections droites")
formula_panel("geometrie")

gauche, droite = st.columns([1, 2], gap="large")
with gauche:
    calc = widgets.calc_button("Sec.calc")
    synthese = st.container()
    widgets.file_bar("Sec")
    widgets.example_picker("Sec")
    with st.expander("Type de section", expanded=True):
        _saisie_geometrie()
    with st.expander("Matériau, méthode et efforts pour σ(y) et τ(y)", expanded=True):
        _saisie_efforts_et_methode()
    if calc:
        _calcule()
    widgets.synthese_resultat("Sec", synthese)

with droite:
    widgets.validation_button("Sec")
    r = state.result("Sec")
    if r is not None:
        _resultats(r["result"], r["tables"], r["status"])
