"""Page « Poutres » : saisie, calcul, diagrammes, tableaux de résultats et fonctions avancées.

Port de l'onglet « Poutres » de MecaStruct_App.m (buildBeamTab, computeBeam, addQuickLoad, applyNationalAnnex,
computeCombinations, checkEurocode, checkFatigue, findLightestProfile, computeMovingLoad, sendToTensor, historique).
"""

import numpy as np
import streamlit as st

from mecastruct.core import geometry
from mecastruct.core.pp import asPP
from mecastruct.plots import beam_plots
from mecastruct.services import beam_design, beam_services
from mecastruct.services.compute import _sectionLabel
from mecastruct.ui import state, widgets
from mecastruct.ui.formula_panel import formula_panel

TYPES_APPUI = ["appui_simple", "rotule", "pivot", "pivot_glissant", "encastrement"]
CAS = ["G", "Q", "W", "S"]
COMPOSANTES = ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]
FAMILLES = ["IPE", "HEA", "HEB", "IPN", "UPN", "UAP"]
FORMES = {
    "Uniforme": "uniforme",
    "Triangulaire croissante (0 → p)": "triangle_croissant",
    "Triangulaire décroissante (p → 0)": "triangle_decroissant",
    "Trapèze (p1 → p2)": "trapeze",
}
ANNEXES = {
    "EN": "Valeurs recommandées de l'EN",
    "FR": "France (NF EN 1993-1-1/NA)",
    "autre": "Autre : saisir γM0 et γM1",
}
NON_VERIFIE = (
    "Non vérifiés : voilement sous charges concentrées, flexion déviée, ELS, classe 4 ; annexe nationale : seules "
    "γM0 et γM1 sont paramétrables."
)

state.init()
dm = st.session_state["dm"]
saisie = state.saisie("Beam")
if "beam_history" not in st.session_state:
    state.push_beam_history()


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


def _etat(texte: str, ok: bool | None = None) -> None:
    """Ligne d'état de la page : texte, et verdict (True vert, False rouge, None orange)."""
    st.session_state["Beam_etat"] = (texte, ok)


def _essaie(cle: str, travail):
    """Résultat de `travail()` gardé sous `cle` ; en cas d'erreur, message affiché et résultat effacé (None)."""
    try:
        valeur = travail()
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop(cle, None)
        return None
    state.set_result(cle, valeur)
    return valeur


def _calcule() -> None:
    """Calcul de la poutre avec la saisie courante ; le résultat est gardé pour l'affichage."""
    res = _essaie("Beam", lambda: beam_services.computeBeam(saisie, dm))
    if res is not None:
        _etat(res["status"], None if res["unreliable"] else res["check"]["bend"]["ok"])
        state.push_beam_history()


def _historique(step: int) -> None:
    """Annuler (-1) ou rétablir (+1) la dernière modification de la saisie (callback des boutons)."""
    st.session_state["Beam_msg"] = ("info", state.move_beam_history(step))


def _applique_annexe() -> None:
    """Annexe nationale choisie : γM0 et γM1 valent 1 pour l'EN et la France ; « autre » : champs libres."""
    if st.session_state["Beam.na"] in ("EN", "FR"):
        st.session_state["Beam.gM0"] = 1.0
        st.session_state["Beam.gM1"] = 1.0


def _ajoute_charge_rapide() -> None:
    """Ajoute une ligne au tableau des charges réparties d'après « Charge rapide » (callback du bouton)."""
    q = st.session_state
    try:
        nouvelle = beam_services.addQuickLoad(
            saisie,
            FORMES[q["Beam_qforme"]],
            q["Beam_qa"],
            q["Beam_qb"],
            q["Beam_qp1"],
            q["Beam_qp2"],
            q["Beam_qdir"],
            q["Beam_qcas"],
        )
    except Exception as err:  # b ≤ a
        q["Beam_msg"] = ("error", str(getattr(err, "message", err)))
        return
    q["saisie"]["Beam"] = nouvelle
    state.reset_widgets("Beam")


def _envoie_tenseur() -> None:
    """Transmet l'état de contrainte du point le plus sollicité à la saisie Tenseurs (sendToTensor)."""
    q = st.session_state
    try:
        res = beam_services.computeBeam(saisie, dm)
        etat = beam_design.sendToTensor(res)
    except Exception as err:
        q["Beam_msg"] = ("error", str(getattr(err, "message", err)))
        return
    state.set_result("Beam", res)
    q["saisie"]["Ten"].update(
        sig=etat["sig"].tolist(),
        mat=saisie["mat"],
        Re=saisie["Re"],
        Rm=dm.getMaterial(saisie["mat"])["Rm"] / 1e6,
        s=saisie["s"],
    )
    state.reset_widgets("Ten")
    y, z = etat["loc"][0] * 1e3, etat["loc"][1] * 1e3
    q["Beam_msg"] = (
        "tenseur",
        f"État transmis à la page Tenseurs & critères : s = {etat['s']:.4g} m, (y, z) = ({y:.4g} ; {z:.4g}) mm, "
        f"σxx = {etat['sig'][0, 0]:.5g} MPa",
    )


def _utilise_profile() -> None:
    """Met le profilé retenu dans la saisie (section, S, Iz…), comme « Importer depuis Sections » (callback)."""
    best = st.session_state["res"]["BeamProf"][1]
    sec = geometry.fromProfile(best)
    st.session_state["saisie"]["Beam"] = beam_design.sectionToBeamInput(saisie, sec, geometry.analytical(sec), None)
    state.reset_widgets("Beam")


def _affiche_message() -> None:
    """Message laissé par un bouton à callback (erreur, information, lien vers la page Tenseurs)."""
    genre, texte = st.session_state.pop("Beam_msg", (None, None))
    if genre == "error":
        st.error(texte)
    elif genre:
        st.info(texte)
    if genre == "tenseur":
        widgets.page_link("app_pages/tenseurs.py", "Ouvrir Tenseurs & critères", "⭕")


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


def _saisie_charge_rapide() -> None:
    st.selectbox("Forme", list(FORMES), key="Beam_qforme")
    st.selectbox("Direction", ["x", "y", "z"], index=1, key="Beam_qdir")
    st.selectbox("Cas de charge", CAS, key="Beam_qcas")
    st.number_input("Début a (m)", value=0.0, key="Beam_qa")
    st.number_input("Fin b (m)", value=1.0, key="Beam_qb")
    st.number_input("p ou p1 (kN/m, < 0 : vers le bas)", value=-10.0, key="Beam_qp1")
    st.number_input("p2 (kN/m, trapèze seulement)", value=0.0, key="Beam_qp2")
    st.button("Ajouter cette charge", key="Beam_qajout", on_click=_ajoute_charge_rapide)


def _saisie_actions_imposees() -> None:
    st.caption(
        "Ressort : appui élastique de raideur k (0 = appui rigide), le déplacement vaut −R/k. Tassement : déplacement "
        "imposé de l'appui (mm, > 0 dans le sens de l'axe, y > 0 vers le haut). L'appui est désigné par son nom "
        "(colonne Nom du tableau Appuis)."
    )
    widgets.table(
        "Beam",
        "supx",
        {
            "name": _texte("Appui (nom)"),
            "k": _num("Ressort k (kN/m)"),
            "dx": _num("Tassement x (mm)"),
            "dy": _num("Tassement y (mm)"),
            "dz": _num("Tassement z (mm)"),
        },
    )
    widgets.table(
        "Beam",
        "hg",
        {"pos": _num("Position (m)"), "name": _texte("Nom")},
        help="Rotule intermédiaire : le moment de flexion y est nul au point choisi (poutre Gerber) ; la pente y est "
        "discontinue. Pas sur un appui.",
    )
    st.caption(
        "Température : α vient du matériau. ΔT uniforme : allongement α·ΔT (efforts si la poutre est empêchée de "
        "s'allonger). Gradient : T(face +y) − T(face −y), la hauteur est 2·|y|max (idem z) ; fibre chaude en haut : la "
        "poutre se cambre."
    )
    widgets.num("Beam", "thDT", "ΔT uniforme", "°C")
    widgets.num("Beam", "thGy", "Gradient selon y : T(+y) − T(−y)", "°C")
    widgets.num("Beam", "thGz", "Gradient selon z : T(+z) − T(−z)", "°C")
    widgets.check(
        "Beam",
        "selfw",
        "Poids propre (ρ·S·g, cas G)",
        help="Ajoute une charge répartie descendante ρ·S·g sur toute la poutre (ρ du matériau choisi).",
    )


def _saisie_combinaisons() -> None:
    st.caption(
        "Chaque charge porte un cas (colonne Cas). « Calculer » additionne tous les cas avec le coefficient 1. "
        "« Calculer les combinaisons » résout chaque ligne avec ses coefficients puis donne l'enveloppe."
    )
    widgets.table(
        "Beam",
        "combo",
        {
            "name": _texte("Combinaison"),
            "gG": _num("γG"),
            "gQ": _num("γQ"),
            "gW": _num("γW"),
            "gS": _num("γS"),
        },
    )
    if st.button("Calculer les combinaisons", key="Beam_bcombo"):
        T = _essaie("BeamCombo", lambda: beam_services.computeCombinations(saisie, dm))
        if T is not None:
            env = T.iloc[-1]
            _etat(
                f"Combinaisons : {len(T) - 1} calculée(s), enveloppe Kt·σ max = {env['Kt·σ max (MPa)']:.4g} MPa "
                f"({env['Résistance']})",
                env["Résistance"] == "vérifié",
            )


def _saisie_charge_mobile() -> None:
    st.caption(
        "Un convoi d'essieux verticaux (Fy) traverse la poutre. La poutre est résolue pour chaque position, puis "
        "l'enveloppe de Mfz, Ty et des réactions est tracée. Essieux de gauche à droite, F < 0 = vers le bas."
    )
    widgets.text("Beam", "mvP", "Essieux (kN, de gauche à droite)")
    widgets.text("Beam", "mvE", "Écartement(s) entre essieux (m)")
    widgets.num("Beam", "mvN", "Positions de base du convoi (+ positions critiques)", "", min_value=2, step=1)
    widgets.check("Beam", "mvFixed", "Ajouter les charges fixes saisies")
    if st.button("Calculer l'enveloppe de la charge mobile", key="Beam_bmobile"):
        r = _essaie("BeamMov", lambda: beam_design.computeMovingLoad(saisie, dm))
        if r is not None:
            e = r[1]["extrema"]
            _etat(
                f"Charge mobile ({r[1]['positions']} positions) : Mfz de {e['Mmin'] / 1e3:.4g} à "
                f"{e['Mmax'] / 1e3:.4g} kN·m, Ty de {e['Tmin'] / 1e3:.4g} à {e['Tmax'] / 1e3:.4g} kN"
            )


def _saisie_profile() -> None:
    widgets.choice("Beam", "pfam", "Famille de profilés", FAMILLES)
    widgets.num(
        "Beam",
        "pdef",
        "Flèche max L / … (0 = ignorée)",
        "",
        help="Exemple : 300 impose f ≤ L/300. En plus de la condition de résistance Kt·σ ≤ Re/s.",
        min_value=0.0,
    )
    if st.button("Chercher le profilé le plus léger", key="Beam_bprofil"):
        r = _essaie("BeamProf", lambda: beam_design.findLightestProfile(saisie, dm, saisie["pfam"], saisie["pdef"]))
        if r is not None:
            best = r[1]
            if best is None:
                _etat(f"Aucun profilé {saisie['pfam']} ne vérifie ce chargement : essayer une autre famille.", False)
            else:
                _etat(
                    f"Profilé {saisie['pfam']} le plus léger qui vérifie : {best['Name']}. "
                    "La saisie de la section est inchangée.",
                    True,
                )


def _saisie_eurocode() -> None:
    st.caption(
        "Profilés IPE, HEA, HEB, IPN et sections en I, classes 1 à 3, fy = Re : flexion, tranchant, voilement de l'âme "
        "par cisaillement, déversement, flambement et interaction N + M (6.3.3, flexion autour de l'axe fort). "
        "Utiliser l'enveloppe d'une combinaison ELU (γG = 1,35, γQ = 1,5)."
    )
    widgets.choice(
        "Beam",
        "na",
        "Annexe nationale",
        list(ANNEXES),
        format_func=ANNEXES.get,
        help="La France retient γM0 = γM1 = 1,0 et γM2 = 1,25 : mêmes valeurs que l'EN. Pour un autre pays, saisir "
        "ses valeurs.",
        on_change=_applique_annexe,
    )
    widgets.num("Beam", "gM0", "γM0 (-), résistance des sections")
    widgets.num("Beam", "gM1", "γM1 (-), stabilité (déversement)")
    widgets.num(
        "Beam",
        "Cmy",
        "Cmy (-), moment équivalent, flambement (1 = prudent)",
        help="Tableau B.3 de l'EN 1993-1-1 : 0,6 + 0,4ψ (moment linéaire, ψ = rapport des moments d'extrémité), "
        "0,95 à 0,9 (charge répartie). Entre 0,4 et 1.",
    )
    widgets.num(
        "Beam",
        "CmLT",
        "CmLT (-), moment équivalent, déversement (1 = prudent)",
        help="Idem pour le déversement. Entre 0,4 et 1 ; 1 est toujours du côté de la sécurité.",
    )
    widgets.num("Beam", "Lcr", "Lcr : longueur entre maintiens latéraux (m, 0 = L)")
    widgets.num(
        "Beam",
        "LcrF",
        "Lcr,y : longueur de flambement dans le plan fort (m, 0 = L)",
        help="Flambement autour de l'axe fort (y-y) : les entretoises latérales n'y changent rien. Par défaut (0), "
        "la longueur de la poutre.",
    )
    widgets.num(
        "Beam",
        "C1",
        "C1 : forme du moment (1 = uniforme, prudent)",
        help="NCCI SN003 : 1,13 pour une charge uniforme sur appuis simples ; 1,35 pour une charge ponctuelle "
        "centrée ; 1,77 pour des moments d'extrémité ψ = 0.",
    )
    widgets.choice(
        "Beam",
        "ecsrc",
        "Efforts de calcul",
        ["courant", "enveloppe"],
        format_func={"courant": "Dernier « Calculer »", "enveloppe": "Enveloppe des combinaisons"}.get,
    )
    st.caption(NON_VERIFIE)
    if st.button("Vérifier selon l'Eurocode 3", key="Beam_bec3"):
        source = "enveloppe" if saisie["ecsrc"] == "enveloppe" else "poutre"
        r = _essaie("BeamEC3", lambda: beam_design.checkEurocode(saisie, dm, source))
        if r is not None:
            e = r[0]
            texte = (
                f"Eurocode 3 : classe {e['class']['class']}, MEd/MRd = {e['ratioM']:.3f}, "
                f"VEd/Vpl,Rd = {e['ratioV']:.3f}, MEd/Mb,Rd = {e['ltb']['ratio']:.3f} "
                f"({'vérifié' if e['okAll'] else 'NON vérifié'})"
            )
            if e["inter"]:
                texte += f", N + M (6.61/6.62) = {e['inter']['ratio']:.3f}"
            _etat(texte, bool(e["okAll"]))


def _saisie_fatigue() -> None:
    widgets.num("Beam", "fR", "R = σmin / σmax (-1 alterné, 0 répété)", "")
    widgets.num(
        "Beam",
        "fka",
        "ka : état de surface",
        "-",
        help="Poli 1 ; usiné 0,7 à 0,9 ; laminé 0,6 à 0,8 ; brut de forge 0,4 à 0,6 (acier).",
    )
    widgets.num(
        "Beam",
        "fkb",
        "kb : effet de taille",
        "-",
        help="Petite pièce (d ≤ 8 mm) 1 ; 0,85 à 0,9 pour 10 à 50 mm ; 0,7 à 0,8 au-delà.",
    )
    if st.button("Vérifier la fatigue", key="Beam_bfatigue"):
        r = _essaie("BeamFat", lambda: beam_design.checkFatigue(saisie, dm))
        if r is not None:
            n = r[0]["n"]
            ok = n >= saisie["s"]
            verdict = "vérifié" if ok else "NON vérifié"
            _etat(f"Fatigue (Goodman) : n = {n:.3g} pour s = {saisie['s']:.3g} ({verdict})", ok)


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


def _table(df) -> None:
    st.dataframe(df, hide_index=True)


def _affiche_profiles() -> None:
    """Tableau des essais et bouton « Utiliser ce profilé »."""
    T, best = state.result("BeamProf")
    _table(T)
    if best is not None:
        st.button(f"Utiliser le profilé {best['Name']}", key="Beam_utilise", on_click=_utilise_profile)


def _resultats(res: dict | None) -> None:
    """Ligne d'état, graphiques (empilés ou en onglets), onglets de résultats (ceux des calculs faits)."""
    r = state.result
    texte, ok = st.session_state.get("Beam_etat", (None, None))
    if texte:
        widgets.status(texte, ok)
    graphes = [("Schéma", lambda: _schema(res))]
    tables = []
    if res is not None:
        sol, d, t = res["sol"], res["defl"], res["tables"]
        comps = st.session_state.get("Beam.comps") or None
        if not comps:
            comps = [c for c in COMPOSANTES if any(np.any(k != 0) for k in asPP(sol[c]).coefs)] or ["Ty", "Mfz"]
        graphes += [
            ("Diagrammes", lambda: st.plotly_chart(beam_plots.internalForces(sol, comps))),
            ("Déformée α(s), v(s)", lambda: st.plotly_chart(beam_plots.deflection(res["model"], d))),
            ("Équations par tronçon", lambda: _equations_par_troncon(sol, comps)),
        ]
        tables += [
            ("Rapport", lambda: widgets.report(res["rapport"])),
            ("Réactions", lambda: _table(t["Réactions"])),
            ("Équations", lambda: (_table(t["Équations"]), widgets.formulas(sol["latex"]))),
            ("Flèche : 4 méthodes", lambda: _table(t["Flèche : 4 méthodes"])),
            ("Énergie", lambda: _table(t["Énergie"])),
            ("Contraintes", lambda: _table(t["Contraintes"])),
        ]
    if r("BeamCombo") is not None:
        graphes.append(("Combinaisons", lambda: st.plotly_chart(beam_plots.combinations(r("BeamCombo")))))
        tables.append(("Combinaisons", lambda: _table(r("BeamCombo"))))
    if r("BeamMov") is not None:
        graphes.append(("Charge mobile", lambda: st.plotly_chart(beam_plots.movingEnvelope(r("BeamMov")[1]))))
        tables.append(("Charge mobile", lambda: _table(r("BeamMov")[0])))
    if r("BeamProf") is not None:
        tables.append(("Profilés", _affiche_profiles))
    if r("BeamEC3") is not None:
        tables.append(("Eurocode 3", lambda: _table(r("BeamEC3")[1])))
    if r("BeamFat") is not None:
        tables.append(("Fatigue", lambda: _table(r("BeamFat")[1])))
    tables = widgets.graphs("Beam_graphes_onglets", graphes, dessous=("Équations par tronçon",)) + tables
    if tables:
        widgets.tabs(tables)


st.title("Poutres")
formula_panel("equilibre")

gauche, droite = st.columns([1, 2], gap="large")
with gauche:
    calcule = widgets.calc_button("Beam.calc")
    colonnes = st.columns(2)
    colonnes[0].button(
        "↶ Annuler",
        key="Beam_annuler",
        on_click=_historique,
        args=(-1,),
        help="Annule la dernière modification de la saisie (retour à l'état du dernier calcul ou exemple).",
    )
    colonnes[1].button("↷ Rétablir", key="Beam_retablir", on_click=_historique, args=(1,))
    widgets.file_bar("Beam")
    widgets.example_picker("Beam")
    with st.expander("Poutre et matériau", expanded=True):
        _saisie_poutre_et_section()
    with st.expander("Section", expanded=True):
        _saisie_section()
    with st.expander("Appuis et charges", expanded=True):
        _saisie_charges()
    with st.expander("Charge rapide (ajoute une ligne au tableau des charges réparties)"):
        _saisie_charge_rapide()
    with st.expander("Ressorts, tassements, rotules, température, poids propre"):
        _saisie_actions_imposees()
    with st.expander("Calcul et affichage", expanded=True):
        _saisie_options()
    with st.expander("Combinaisons de cas (G permanentes, Q exploitation, W vent, S neige)"):
        _saisie_combinaisons()
    with st.expander("Charge mobile (convoi d'essieux, enveloppe)"):
        _saisie_charge_mobile()
    with st.expander("Dimensionnement : profilé le plus léger"):
        _saisie_profile()
    with st.expander("Eurocode 3 simplifié (flexion + tranchant)"):
        _saisie_eurocode()
    with st.expander("Fatigue (Goodman)"):
        _saisie_fatigue()
    if calcule:
        _calcule()
    st.button("Envoyer au tenseur (point le plus sollicité)", key="Beam_btenseur", on_click=_envoie_tenseur)
    st.caption(
        "Les efforts de la poutre se reprennent dans Sections : « Efforts en s » et « Efforts au point critique »."
    )
    _affiche_message()

with droite:
    widgets.validation_button("Beam")
    if state.result("Beam") is None and st.session_state.get("Beam_etat") is None:
        st.info("Aperçu de la poutre saisie. Cliquez sur « Calculer » pour les diagrammes et les résultats.")
    _resultats(state.result("Beam"))
