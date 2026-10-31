"""Point d'entrée de MecaStruct RdM Pro (version web) : navigation entre les pages.

Lancement local : streamlit run streamlit_app.py
"""

import streamlit as st

from mecastruct.ui import state, widgets

st.set_page_config(
    page_title="MecaStruct RdM Pro", page_icon=":material/architecture:", layout="wide", initial_sidebar_state="auto"
)
state.init()

pages = {
    "": [st.Page("app_pages/accueil.py", title="Accueil", icon=":material/home:", default=True)],
    "Calcul": [
        st.Page("app_pages/poutres.py", title="Poutres", icon=":material/horizontal_rule:"),
        st.Page("app_pages/treillis.py", title="Treillis", icon=":material/change_history:"),
        st.Page("app_pages/sollicitations.py", title="Sollicitations", icon=":material/ssid_chart:"),
        st.Page("app_pages/flambage.py", title="Flambage", icon=":material/compress:"),
    ],
    "Matériau & section": [
        st.Page("app_pages/sections.py", title="Sections", icon=":material/crop_square:"),
        st.Page("app_pages/tenseurs.py", title="Tenseurs & critères", icon=":material/grid_on:"),
        st.Page("app_pages/hooke_jauges.py", title="Hooke & jauges", icon=":material/sensors:"),
    ],
    "Outils": [
        st.Page("app_pages/base_de_donnees.py", title="Base de données", icon=":material/database:"),
        st.Page("app_pages/convertisseur.py", title="Convertisseur", icon=":material/swap_horiz:"),
    ],
}
pg = st.navigation(pages, position="sidebar" if widgets.vue() == "pc" else "top")
pg.run()
