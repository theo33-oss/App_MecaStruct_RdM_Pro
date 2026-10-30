"""Page « Poutres » 1/2 : saisie de base, calcul, diagrammes et tableaux de résultats.

Port de l'onglet « Poutres » de MecaStruct_App.m (buildBeamTab, computeBeam). Les fonctions avancées (combinaisons,
Eurocode 3, fatigue, profilé le plus léger, charge mobile, actions imposées, historique) viennent en E27.
"""

import numpy as np
import streamlit as st

from mecastruct.core.pp import asPP
from mecastruct.plots import beam_plots
from mecastruct.services import beam_design, beam_services
from mecastruct.services.compute import _sectionLabel
from mecastruct.ui import state, widgets
from mecastruct.ui.formula_panel import formula_panel

TYPES_APPUI = ["appui_simple", "rotule", "pivot", "pivot_glissant", "encastrement"]
CAS = ["G", "Q", "W", "S"]
COMPOSANTES = ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]

state.init()
dm = st.session_state["dm"]
saisie = state.saisie("Beam")


def _num(label: str, **kw) -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, format="%.5g", default=0.0, **kw)


def _texte(label: str) -> st.column_config.TextColumn:
    return st.column_config.TextColumn(label, default="")


def _cas() -> st.column_config.SelectboxColumn:
    return st.column_config.SelectboxColumn("Cas", options=CAS, default="G", required=True)


def _applique_materiau() -> None:
    """E, G, Re prennent les valeurs du matériau choisi (callback de la liste, applyMaterial de MATLAB)."""
    m = dm.getMaterial(st.session_state["Beam.mat"])
    st.session_state["Beam.E"] = m["E"] / 1e9
    st.session_state["Beam.G"] = m["G"] / 1e9
    st.session_state["Beam.Re"] = m["Re"] / 1e6


def _section_manuelle() -> None:
    """Une valeur de section est saisie à la main : la forme associée n'est plus valable (markBeamManual)."""
    saisie["section"] = None
    saisie["secTabulated"] = False


def _importe_section() -> None:
    """Recopie la section de la page Sections dans la saisie Poutres (useSectionForBeam)."""
    res = state.result("Sec")["result"]
    mat = dm.getMaterial(st.session_state["saisie"]["Sec"]["mat"])
    st.session_state["saisie"]["Beam"] = beam_design.sectionToBeamInput(saisie, res["sec"], res["P"], mat)
    state.reset_widgets("Beam")


def _calcule() -> None:
    """Calcul de la poutre avec la saisie courante ; le résultat est gardé pour l'affichage."""
    try:
        state.set_result("Beam", beam_services.computeBeam(saisie, dm))
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop("Beam", None)


def _saisie_poutre_et_section() -> None:
    """Longueur, matériau, E, G, Re puis propriétés de la section."""
    widgets.num(
        "Beam",
        "L",
        "Longueur L",
        "m",
        help="Longueur de la poutre entre ses deux extrémités, en mètres.",
        min_value=0.0,
    )
    widgets.choice("Beam", "mat", "Matériau", dm.listMaterials(), on_change=_applique_materiau)
    widgets.num("Beam", "E", "E", "GPa", help="Module d'Young : rigidité du matériau (acier ≈ 190–210 GPa).")
    widgets.num("Beam", "G", "G", "GPa", help="Module de cisaillement : G = E / (2(1+ν)).")
    widgets.num(
        "Beam",
        "Re",
        "Re",
        "MPa",
        help="Limite élastique : contrainte au-delà de laquelle le matériau se déforme définitivement.",
    )


def _saisie_section() -> None:
    sec = saisie.get("section")
    if sec is None:
        st.markdown("**Section utilisée : valeurs saisies à la main (aucune forme associée).**")
    else:
        origine = "valeurs du catalogue" if saisie.get("secTabulated") else "contour exact"
        st.markdown(f"**Section utilisée : {_sectionLabel(sec)} (importée de Sections, {origine}).**")
    champs = [
        ("S", "S", "mm²", "Aire de la section droite."),
        (
            "Iz",
            "Iz — flexion (x,y)",
            "mm⁴",
            "Moment quadratique pour la flexion dans le plan (x,y), charges verticales.",
        ),
        (
            "Iy",
            "Iy — flexion (x,z)",
            "mm⁴",
            "Moment quadratique pour la flexion dans le plan (x,z), charges horizontales.",
        ),
        (
            "Ix",
            "Ix — constante de torsion",
            "mm⁴",
            "Constante de torsion (moment quadratique polaire pour un arbre rond).",
        ),
        (
            "Iyz",
            "Iyz — produit d'inertie (0 si axes principaux)",
            "mm⁴",
            "Produit d'inertie : 0 si y et z sont les axes principaux (cas courant).",
        ),
        (
            "ky",
            "ky — section réduite, tranchant Ty",
            "-",
            "Section réduite : le cisaillement est repris par S/ky ; 1 par défaut.",
        ),
        (
            "kz",
            "kz — section réduite, tranchant Tz",
            "-",
            "Section réduite : le cisaillement est repris par S/kz ; 1 par défaut.",
        ),
        ("vy", "Fibre extrême |y|max", "mm", "Distance du centre de gravité à la fibre la plus éloignée selon y."),
        ("vz", "Fibre extrême |z|max", "mm", "Distance du centre de gravité à la fibre la plus éloignée selon z."),
    ]
    for champ, label, unite, aide in champs:
        widgets.num("Beam", champ, label, unite, help=aide, on_change=_section_manuelle, format="%.6g")
    st.button(
        "← Importer depuis Sections",
        key="Beam.importer",
        on_click=_importe_section,
        disabled=state.result("Sec") is None,
        help="Recopie S, Iz, Iy, Ix, Iyz, ky, kz, fibres extrêmes et matériau de la page Sections (à calculer avant).",
    )


def _saisie_charges() -> None:
    st.caption(
        "Signes : Fy < 0 = force vers le bas ; Fx > 0 = dans le sens de x (vers la droite) ; "
        "Mz > 0 = sens trigonométrique (axes directs)."
    )
    widgets.table(
        "Beam",
        "sup",
        {
            "pos": _num("Position (m)"),
            "type": st.column_config.SelectboxColumn(
                "Type", options=TYPES_APPUI, default="appui_simple", required=True
            ),
            "name": _texte("Nom"),
        },
        help="Appuis. appui_simple et pivot_glissant bloquent les déplacements transversaux y et z (la poutre glisse "
        "selon x) ; rotule et pivot bloquent x, y et z (rotations libres) ; encastrement bloque tout.",
    )
    st.markdown("**Forces ponctuelles** (composantes globales)")
    widgets.table(
        "Beam",
        "pl",
        {
            "pos": _num("Position (m)"),
            "Fx": _num("Fx (kN)"),
            "Fy": _num("Fy (kN)"),
            "Fz": _num("Fz (kN)"),
            "name": _texte("Nom"),
            "case": _cas(),
        },
    )
    st.markdown("**Couples ponctuels**")
    widgets.table(
        "Beam",
        "pm",
        {
            "pos": _num("Position (m)"),
            "Mx": _num("Mx (kN·m)"),
            "My": _num("My (kN·m)"),
            "Mz": _num("Mz (kN·m)"),
            "name": _texte("Nom"),
            "case": _cas(),
        },
    )
    st.markdown("**Charges réparties**")
    widgets.table(
        "Beam",
        "dl",
        {
            "a": _num("a (m)"),
            "b": _num("b (m)"),
            "dir": st.column_config.SelectboxColumn("Dir.", options=["x", "y", "z"], default="y", required=True),
            "type": st.column_config.SelectboxColumn(
                "Type", options=["uniforme", "linéaire", "polynomiale"], default="uniforme", required=True
            ),
            "vals": st.column_config.TextColumn("Valeurs (kN/m)", default="-10"),
            "name": _texte("Nom"),
            "case": _cas(),
        },
        help="Valeurs : uniforme « p0 » ; linéaire « p1 p2 » (de a à b) ; polynomiale : coefficients en ξ = s − a, "
        "ordre décroissant (kN/m, kN/m², ...). py < 0 : charge descendante.",
    )


def _saisie_options() -> None:
    widgets.choice(
        "Beam",
        "plane",
        "Plan de la déformée",
        ["xy", "xz"],
        format_func={"xy": "(x,y) : v, Mfz, Iz", "xz": "(x,z) : w, Mfy, Iy"}.get,
    )
    widgets.check("Beam", "shear", "Tranchant dans Castigliano")
    st.multiselect(
        "Diagrammes",
        COMPOSANTES,
        key="Beam.comps",
        help="Composantes tracées ; aucune choisie = celles qui ne sont pas nulles.",
    )
    widgets.num(
        "Beam",
        "s",
        "Coefficient de sécurité s",
        "-",
        help="Coefficient de sécurité : on exige σ ≤ Re / s (typiquement 1,5 à 3).",
    )
    widgets.num(
        "Beam",
        "Kt",
        "Kt",
        "-",
        help="Coefficient de concentration de contrainte (1 si aucun trou ni épaulement).",
    )


def _schema(res: dict | None) -> None:
    """Schéma de la poutre : avec réactions après calcul, sinon aperçu de la saisie (sol=None)."""
    try:
        if res is None:
            fig = beam_plots.beamSchematic(beam_services.buildBeamModel(saisie, dm), None)
        else:
            fig = beam_plots.beamSchematic(res["model"], res["sol"])
    except Exception as err:  # saisie incomplète : l'aperçu est seulement omis
        st.caption(f"Aperçu indisponible : {err}")
        return
    st.plotly_chart(fig)


def _equations_par_troncon(sol: dict, comps: list[str]) -> None:
    """Équations LaTeX de chaque tronçon pour les composantes tracées."""
    for k, eq in enumerate(sol["equations"], start=1):
        st.markdown(f"**Tronçon {k} : s ∈ [{eq['s1']:.4g} ; {eq['s2']:.4g}] m**")
        widgets.formulas([eq[c] for c in comps])


def _resultats(res: dict) -> None:
    sol, d = res["sol"], res["defl"]
    ok = res["check"]["bend"]["ok"]
    if res["unreliable"]:
        st.warning(res["status"])
    else:
        widgets.status(res["status"], ok)
    comps = st.session_state.get("Beam.comps") or None
    if not comps:
        comps = [c for c in COMPOSANTES if any(np.any(k != 0) for k in asPP(sol[c]).coefs)] or ["Ty", "Mfz"]
    graphes = st.tabs(["Schéma", "Diagrammes", "Déformée α(s), v(s)", "Équations par tronçon"])
    with graphes[0]:
        _schema(res)
    with graphes[1]:
        st.plotly_chart(beam_plots.internalForces(sol, comps))
    with graphes[2]:
        st.plotly_chart(beam_plots.deflection(res["model"], d))
    with graphes[3]:
        _equations_par_troncon(sol, comps)

    tables = res["tables"]
    onglets = st.tabs(["Rapport", "Réactions", "Équations", "Flèche : 4 méthodes", "Énergie", "Contraintes"])
    with onglets[0]:
        widgets.report(res["rapport"])
    with onglets[1]:
        st.dataframe(tables["Réactions"], hide_index=True)
    with onglets[2]:
        st.dataframe(tables["Équations"], hide_index=True)
        widgets.formulas(sol["latex"])
    with onglets[3]:
        st.dataframe(tables["Flèche : 4 méthodes"], hide_index=True)
    with onglets[4]:
        st.dataframe(tables["Énergie"], hide_index=True)
    with onglets[5]:
        st.dataframe(tables["Contraintes"], hide_index=True)


st.title("Poutres")
formula_panel("equilibre")

gauche, droite = st.columns([1, 2], gap="large")
with gauche:
    widgets.example_picker("Beam")
    with st.expander("Poutre et matériau", expanded=True):
        _saisie_poutre_et_section()
    with st.expander("Section", expanded=True):
        _saisie_section()
    with st.expander("Appuis et charges", expanded=True):
        _saisie_charges()
    with st.expander("Calcul et affichage", expanded=True):
        _saisie_options()
    calc = st.button("Calculer", type="primary", width="stretch")
    if calc:
        _calcule()

with droite:
    resultat = state.result("Beam")
    if resultat is None:
        st.info("Aperçu de la poutre saisie. Cliquez sur « Calculer » pour les diagrammes et les résultats.")
        _schema(None)
    else:
        _resultats(resultat)
