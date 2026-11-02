"""Page « Sollicitations » : traction, cisaillement et matage, torsion, flexion (quatre sous-onglets).

Port des onglets de MecaStruct_App.m (buildSolicitationsTab, computeTraction, computeShear, computeKey, computePin,
computeTorsion, computeBending). Cisaillement et flexion utilisent la section de la page Sections.
"""

import streamlit as st

from mecastruct.core import geometry, key_pin
from mecastruct.plots import section_plots, sollicitation_plots
from mecastruct.services import beam_design, beam_services, compute, machine
from mecastruct.ui import machine_page, state, widgets
from mecastruct.ui.formula_panel import formula_panel

CRITERES = {"Tresca": "Tresca (τe = Re/2)", "VonMises": "Von Mises (τe = Re/√3)"}
FORMES_CLE = {"A": "A (bouts ronds)", "B": "B (bouts droits)", "C": "C (un bout rond)"}
# goupille sous couple : (clé, libellé, valeur de départ) ; T en N·m, longueurs en mm
GOUPILLE_COUPLE = [
    ("T", "Couple T (N·m)", 50.0),
    ("D", "Diamètre de l'arbre D (mm)", 30.0),
    ("D1", "Diamètre extérieur du moyeu D1 (mm)", 50.0),
    ("d", "Diamètre de la goupille d (mm)", 8.0),
    ("dint", "Alésage d'une goupille élastique (0 = pleine) (mm)", 0.0),
    ("l", "Longueur engagée l (mm)", 30.0),
]
ONGLETS = [
    ("Traction / compression", "traction", "Tra"),
    ("Cisaillement & matage", "cisaillement", "Cis"),
    ("Torsion", "torsion", "Tor"),
    ("Flexion", "flexion", "Fle"),
]

state.init()
dm = st.session_state["dm"]


def _calcule(cle: str, travail) -> dict | None:
    """Résultat de `travail()` gardé sous `cle` ; en cas d'erreur, message affiché et résultat effacé (None)."""
    try:
        res = travail()
    except Exception as err:  # MecaStructError : message et conseil ; autre erreur : trace complète
        widgets.error_box(err)
        st.session_state["res"].pop(cle, None)
        return None
    state.set_result(cle, res)
    return res


def _tau_adm(saisie: dict) -> float:
    """τadm (MPa) du matériau et du critère de la saisie Cisaillement, comme pour la clavette et la goupille."""
    return compute.computeKey(saisie, dm)["result"]["tauAdm"] / 1e6


def _section_des_sections(saisie: dict) -> None:
    """La section de la saisie est celle de la page Sections (dernier calcul), comme SectionData de MATLAB."""
    r = state.result("Sec")
    if r is not None:
        saisie["section"] = r["result"]["sec"]


def _synthese(res: dict | None) -> None:
    """Ligne d'état, tableau de synthèse et rapport d'un calcul."""
    if res is None:
        return
    st.success(res["status"])
    st.dataframe(res["tables"]["Synthèse"], hide_index=True)
    with st.expander("Rapport"):
        widgets.report(res["result"]["rapport"])


# ------------------------------------------------------------------------------------------------- Traction


def _traction_saisie(calcule: bool) -> None:
    saisie = state.saisie("Tra")
    with st.expander("Barre et chargement", expanded=True):
        widgets.num("Tra", "N", "N (> 0 traction)", "kN")
        widgets.num("Tra", "S0", "S0", "mm²", min_value=0.0)
        widgets.num("Tra", "L0", "L0", "m", min_value=0.0)
        widgets.choice_materiau("Tra", ["E", "nu", "alpha", "Re"], dm)
        widgets.num("Tra", "E", "E", "GPa")
        widgets.num("Tra", "nu", "ν", "-")
        widgets.num("Tra", "alpha", "α", "10⁻⁶/°C")
        widgets.num("Tra", "Re", "Re", "MPa")
        widgets.num("Tra", "dT", "ΔT", "°C")
        widgets.num("Tra", "Kt", "Kt", "-", min_value=1.0)
        widgets.num("Tra", "s", "Coefficient de sécurité s", "-")
        widgets.num("Tra", "dLmax", "ΔL max (0 = sans limite)", "mm", min_value=0.0)
    with st.expander("Section variable", expanded=bool(saisie["varS"])):
        widgets.check("Tra", "varS", "Utiliser S(x)")
        widgets.text("Tra", "Sexpr", "S(x) (mm², x en m)")
        st.caption(
            "Expression en x (m) donnant S en mm² : nombres, x, pi, sqrt, exp, log, sin, cos, tan, abs, + − * / ^. "
            "Exemple (barre conique d = 20 → 30 mm) : pi/4*(20 + 10*x)^2."
        )
    if calcule:
        _calcule("Tra", lambda: compute.computeTraction(saisie, dm))


def _traction_resultats() -> None:
    res = state.result("Tra")
    if res is None:
        return
    r, saisie = res["result"], state.saisie("Tra")
    widgets.plot(sollicitation_plots.tractionStress(r["x"], saisie["N"] * 1e3, r["Sx"], saisie["Kt"], r["sigmaAdm"]))
    widgets.plot(sollicitation_plots.elongations(r["dL"]))
    _synthese(res)
    widgets.formulas(r["latex"])


# ------------------------------------------------------------------------------- Cisaillement et matage


def _applique_matage() -> None:
    """P_adm prend la pression admissible minimale de la ligne choisie dans la table de matage."""
    i = st.session_state["Cis_matage"]
    if i != "-":
        st.session_state["Cis.Padm"] = float(dm.BearingPressures["Pmin"].iloc[i]) / 1e6


def _cisaillement_saisie(calcule: bool) -> None:
    saisie = state.saisie("Cis")

    def materiau() -> None:
        widgets.choice_materiau("Cis", ["Re", "G"], dm)
        widgets.num("Cis", "Re", "Re", "MPa")
        widgets.num("Cis", "G", "G", "GPa")
        widgets.choice("Cis", "crit", "Critère (τe)", list(CRITERES), format_func=CRITERES.get)
        widgets.num("Cis", "s", "Coefficient de sécurité s", "-")

    def simple() -> None:
        widgets.num("Cis", "T", "T", "kN")
        widgets.num("Cis", "S", "S cisaillée", "mm²", min_value=0.0)
        widgets.num("Cis", "k", "k = τmax/τmoy", "-")
        st.caption("Jourawski : section de la page Sections, Ty = T.")
        widgets.num("Cis", "Fm", "F", "kN")
        widgets.num("Cis", "Sm", "S matée", "mm²", min_value=0.0)
        T = dm.BearingPressures
        st.selectbox(
            "Table de matage",
            ["-", *range(len(T))],
            key="Cis_matage",
            format_func=lambda i: "-" if i == "-" else f"{T['Liaison'].iloc[i]} — {T['Conditions'].iloc[i]}",
            on_change=_applique_matage,
        )
        widgets.num("Cis", "Padm", "P_adm", "MPa", min_value=0.0)

    def clavette() -> None:
        widgets.num("Cis", "C", "Couple C", "kN·m")
        widgets.num("Cis", "Dk", "Diamètre d'arbre D", "mm")
        widgets.num("Cis", "ak", "Largeur a", "mm")
        widgets.num("Cis", "bk", "Hauteur b", "mm")
        widgets.num("Cis", "Lk", "Longueur L (0 = dimensionner)", "mm", min_value=0.0)
        if st.button("Calculer la clavette", key="Cis.key"):
            _calcule("CisKey", lambda: compute.computeKey(saisie, dm))
        st.markdown("**Clavette normalisée NF E22-177** : b × h, t1 et t2 lus d'après D ; C, D, L et P_adm ci-dessus.")
        st.radio("Forme", list(key_pin.FORMES), key="Cis_cle_forme", horizontal=True, format_func=FORMES_CLE.get)
        if st.button("Vérifier la clavette normalisée", key="Cis.keystd"):
            _calcule(
                "CisKeyStd",
                lambda: machine.computeKeyStandard(saisie, st.session_state["Cis_cle_forme"], _tau_adm(saisie)),
            )

    def goupille() -> None:
        widgets.num("Cis", "Fp", "F", "kN")
        widgets.num("Cis", "dp", "d", "mm")
        widgets.num("Cis", "ep", "e — épaisseur matée", "mm")
        widgets.num("Cis", "np", "Sections cisaillées n", "-", step=1)
        if st.button("Calculer la goupille", key="Cis.pin"):
            _calcule("CisPin", lambda: compute.computePin(saisie, dm))
        st.markdown("**Goupille transmettant un couple** (arbre / moyeu ; P_adm et matériau ci-dessus)")
        st.radio("Montage", ["transversale", "longitudinale"], key="Cis_gc_montage", horizontal=True)
        q = st.session_state
        inutile = "l" if q["Cis_gc_montage"] == "transversale" else "D1"
        for cle, label, defaut in GOUPILLE_COUPLE:
            q.setdefault(f"Cis_gc_{cle}", defaut)
            if cle != inutile:
                st.number_input(label, key=f"Cis_gc_{cle}", min_value=0.0, format="%.6g")
        if st.button("Vérifier la goupille sous couple", key="Cis.pintorque"):
            p = {cle: q.get(f"Cis_gc_{cle}", defaut) for cle, _, defaut in GOUPILLE_COUPLE}
            p.update(montage=q["Cis_gc_montage"], Padm=saisie["Padm"])
            _calcule("CisPinT", lambda: machine.computePinTorque({**p, "tauAdm": _tau_adm(saisie)}))

    widgets.panels(
        "Cis",
        [
            widgets.Volet("materiau", "Matériau et critère", "Haut", True, materiau),
            widgets.Volet("simple", "Cisaillement simple, Jourawski et matage", "Haut", True, simple),
            widgets.Volet("clavette", "Clavette parallèle", "Bas", False, clavette),
            widgets.Volet("goupille", "Goupille / rivet", "Bas", False, goupille),
        ],
    )
    if calcule:
        _section_des_sections(saisie)
        _calcule("Cis", lambda: compute.computeShear(saisie, dm))


def _cisaillement_resultats() -> None:
    res = state.result("Cis")
    if res is not None:
        r, saisie = res["result"], state.saisie("Cis")
        sec = saisie["section"]
        P = geometry.analytical(sec)
        shear, jour, bearing = r["shear"], r["jour"], r["bearing"]
        taux = [
            abs(shear["tauMax"]) / shear["tauAdm"],
            abs(jour["tauMax"]) / shear["tauAdm"],
            abs(bearing["P"]) / (saisie["Padm"] * 1e6),
        ]
        widgets.plot(section_plots.section(sec, P))
        widgets.plot(section_plots.sectionStress(sec, P, None, jour))
        widgets.plot(
            sollicitation_plots.ratios(
                ["τmax/τadm", "τJourawski/τadm", "P/Padm"], taux, "Taux d'utilisation (cisaillement et matage)"
            )
        )
        _synthese(res)
    for cle, titre in (("CisKey", "Clavette"), ("CisPin", "Goupille")):
        autre = state.result(cle)
        if autre is not None:
            st.subheader(titre)
            _synthese(autre)
    for cle, titre in (("CisKeyStd", "Clavette normalisée"), ("CisPinT", "Goupille sous couple")):
        autre = state.result(cle)
        if autre is not None:
            st.subheader(titre)
            widgets.status(autre["status"], autre["ok"])
            st.dataframe(autre["tables"]["Synthèse"], hide_index=True)
            with st.expander("Explications du calcul"):
                machine_page.explications(autre)


# ------------------------------------------------------------------------------------------------- Torsion


def _torsion_saisie(calcule: bool) -> None:
    saisie = state.saisie("Tor")
    with st.expander("Arbre circulaire", expanded=True):
        widgets.num("Tor", "Mt", "Mt", "kN·m")
        widgets.num("Tor", "D", "D", "mm", min_value=0.0)
        widgets.num("Tor", "d", "d — alésage (0 = plein)", "mm", min_value=0.0)
        widgets.num("Tor", "L", "L", "m", min_value=0.0)
        widgets.choice_materiau("Tor", ["G", "Re"], dm)
        widgets.num("Tor", "G", "G", "GPa")
        widgets.num("Tor", "Re", "Re", "MPa")
        widgets.choice("Tor", "crit", "Critère (τe)", list(CRITERES), format_func=CRITERES.get)
        widgets.num("Tor", "s", "Coefficient de sécurité s", "-")
        widgets.num("Tor", "Kt", "Kt", "-", min_value=1.0)
        widgets.num("Tor", "thetaAdm", "θ admissible (0 = sans)", "°/m", min_value=0.0)
    if calcule:
        _calcule("Tor", lambda: compute.computeTorsion(saisie, dm))


def _torsion_resultats() -> None:
    res = state.result("Tor")
    if res is None:
        return
    r, saisie = res["result"], state.saisie("Tor")
    widgets.plot(sollicitation_plots.torsionStress(r, saisie["D"] * 1e-3))
    widgets.plot(sollicitation_plots.torsionAngle(saisie["L"], r["theta"], r["phi"]["analytique"]))
    _synthese(res)
    widgets.formulas(r["latex"])


# ------------------------------------------------------------------------------------------------- Flexion


def _efforts_poutre(mode: str) -> None:
    """Remplit N, Mfz, Mfy avec les efforts de la poutre, recalculée d'abord (callback ; loadFromBeam de MATLAB)."""
    cible = st.session_state["saisie"]["Fle"]
    cible["s0"] = st.session_state.get("Fle.s0", cible["s0"])
    try:
        res = beam_services.computeBeam(state.saisie("Beam"), dm)
        state.set_result("Beam", res)
        nouvelle = beam_design.loadFromBeam(cible, res, "Fle", mode)
    except Exception as err:  # MecaStructError : abscisse hors de la poutre, poutre incalculable…
        st.session_state["Fle_msg"] = ("error", str(getattr(err, "message", err)))
        return
    st.session_state["saisie"]["Fle"] = nouvelle
    state.reset_widgets("Fle")
    note = "⚠ Résultats NON fiables (hyperstatique, Iyz ≠ 0) — " if res["unreliable"] else ""
    st.session_state["Fle_msg"] = (
        "info",
        f"{note}Efforts lus sur la poutre en s = {nouvelle['s0']:.4g} m : N = {nouvelle['N']:.4g} kN, "
        f"Mfz = {nouvelle['Mfz']:.4g} kN·m, Mfy = {nouvelle['Mfy']:.4g} kN·m",
    )


def _flexion_saisie(calcule: bool) -> None:
    saisie = state.saisie("Fle")
    st.caption("Section : celle de la page Sections (à calculer d'abord ; sinon la section de l'exemple).")
    with st.expander("Efforts dans la section étudiée", expanded=True):
        widgets.num(
            "Fle", "N", "N : traction > 0", "kN", help="Effort normal : positif en traction, négatif en compression."
        )
        widgets.num(
            "Fle",
            "Mfz",
            "Mfz : plan (x,y)",
            "kN·m",
            help="Moment de flexion autour de z (charges dans le plan x,y). Mfz > 0 : fibres du haut (y > 0) "
            "comprimées, fibres du bas tendues.",
        )
        widgets.num(
            "Fle",
            "Mfy",
            "Mfy : plan (x,z)",
            "kN·m",
            help="Moment de flexion autour de y (charges dans le plan x,z). Mfy > 0 : fibres z > 0 tendues.",
        )
    with st.expander("Reprendre les efforts de la poutre", expanded=True):
        widgets.num(
            "Fle",
            "s0",
            "s sur la poutre",
            "m",
            help="Abscisse de la coupure dans la page Poutres (de 0 à L).",
            min_value=0.0,
        )
        colonnes = st.columns(2)
        colonnes[0].button("Efforts en s", key="Fle.efforts_s", on_click=_efforts_poutre, args=("abscisse",))
        colonnes[1].button("Efforts au point critique", key="Fle.efforts_max", on_click=_efforts_poutre, args=("max",))
        genre, texte = st.session_state.pop("Fle_msg", (None, None))
        if genre == "error":
            st.error(texte)
        elif genre:
            st.info(texte)
    with st.expander("Kt, matériau et sécurité", expanded=True):
        widgets.num("Fle", "Kt", "Kt", "-", min_value=1.0)
        widgets.choice_materiau("Fle", ["Re"], dm)
        widgets.num("Fle", "Re", "Re", "MPa")
        widgets.num("Fle", "s", "Coefficient de sécurité s", "-")
    if calcule:
        _section_des_sections(saisie)
        _calcule("Fle", lambda: compute.computeBending(saisie, dm))


def _flexion_resultats() -> None:
    res = state.result("Fle")
    if res is None:
        return
    r = res["result"]
    widgets.plot(sollicitation_plots.bendingMarks(section_plots.section(r["sec"], r["P"]), r["P"], r["bend"]))
    widgets.plot(section_plots.sectionStress(r["sec"], r["P"], r["bend"], None))
    _synthese(res)
    widgets.formulas(r["bend"]["latex"])


SOUS_PAGES = {
    "Tra": (_traction_saisie, _traction_resultats),
    "Cis": (_cisaillement_saisie, _cisaillement_resultats),
    "Tor": (_torsion_saisie, _torsion_resultats),
    "Fle": (_flexion_saisie, _flexion_resultats),
}

st.title("Sollicitations")
onglets = st.tabs([titre for titre, _, _ in ONGLETS], key="Sol_onglet", on_change="rerun")
for onglet, (_, fiche, tab) in zip(onglets, ONGLETS, strict=True):
    if onglet.open:
        formula_panel(fiche)  # la fiche suit le sous-onglet ouvert
    with onglet:
        gauche, droite = widgets.zones(tab)
        with gauche:
            calcule = widgets.calc_button(f"{tab}.calc")
            synthese = st.container()
            widgets.file_bar(tab)
            widgets.example_picker(tab)
            SOUS_PAGES[tab][0](calcule)
            widgets.synthese_resultat(tab, synthese)
        with droite:
            widgets.validation_button(tab)
            widgets.explanation_panel(tab)
            SOUS_PAGES[tab][1]()
