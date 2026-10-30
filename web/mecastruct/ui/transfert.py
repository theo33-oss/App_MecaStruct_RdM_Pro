"""Transfert de la section de la page Sections vers les pages Poutres et Flambage (useSectionForBeam de MATLAB)."""

import streamlit as st

from mecastruct.core.data_manager import DataManager
from mecastruct.core.units import fromSI
from mecastruct.services import beam_design, compute
from mecastruct.ui import state


def envoie_section(dm: DataManager) -> str | None:
    """Recopie la section calculée de Sections dans les saisies Poutres et Flambage, puis réinitialise leurs widgets.

    Poutres reçoit S, Iz, Iy, Ix, Iyz, ky, kz, fibres extrêmes et matériau ; Flambage reçoit S, Iz, Iy, matériau, E et
    Re (moments principaux I1 et I2 si Iyz ≠ 0 hors profilé, car le flambage se fait autour de l'axe principal faible).
    Entrée : `dm` (base de matériaux). Sortie : « principaux » si Flambage a reçu I1 et I2, « ok » sinon, None si la
    section n'a pas encore été calculée. Le texte de section utilisée de Flambage est gardé dans « Fla_info ».
    """
    r = state.result("Sec")
    if r is None:
        return None
    res = r["result"]
    mat = state.saisie("Sec")["mat"]
    beam = beam_design.sectionToBeamInput(state.saisie("Beam"), res["sec"], res["P"], dm.getMaterial(mat))
    st.session_state["saisie"]["Beam"] = beam
    state.reset_widgets("Beam")
    fla = st.session_state["saisie"]["Fla"]
    fla.update(S=beam["S"], Iz=beam["Iz"], Iy=beam["Iy"], mat=mat, **compute._materiau(dm, mat, ["E", "Re"]))
    P = res["P"]
    principaux = res["sec"]["type"] != "profile" and abs(P["Iyz"]) > 1e-9 * (P["Iz"] * P["Iy"]) ** 0.5
    texte = f"Section utilisée : {compute._sectionLabel(res['sec'])} (importée de Sections"
    if principaux:
        fla.update(Iz=fromSI(P["I1"], "mm^4"), Iy=fromSI(P["I2"], "mm^4"))
        texte += f", Iyz ≠ 0 : moments principaux I1, I2, axes tournés de {P['alphaP'] * 180 / 3.141592653589793:.4g}°"
    st.session_state["Fla_info"] = texte + ")."
    state.reset_widgets("Fla")
    return "principaux" if principaux else "ok"
