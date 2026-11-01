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
    "": [st.Page("app_pages/accueil.py", title="Accueil", icon="🏠", default=True)],
    "🧮 Calcul": [
        st.Page("app_pages/poutres.py", title="Poutres", icon="📏"),
        st.Page("app_pages/treillis.py", title="Treillis", icon="🔺"),
        st.Page("app_pages/sollicitations.py", title="Sollicitations", icon="🔩"),
        st.Page("app_pages/flambage.py", title="Flambage", icon="📐"),
    ],
    "🧱 Matériau & section": [
        st.Page("app_pages/sections.py", title="Sections", icon="🟦"),
        st.Page("app_pages/tenseurs.py", title="Tenseurs & critères", icon="⭕"),
        st.Page("app_pages/hooke_jauges.py", title="Hooke & jauges", icon="📈"),
    ],
    "🛠️ Outils": [
        st.Page("app_pages/base_de_donnees.py", title="Base de données", icon="📚"),
        st.Page("app_pages/convertisseur.py", title="Convertisseur", icon="🔁"),
        st.Page("app_pages/references.py", title="Références", icon="📖"),
    ],
}
pg = st.navigation(pages, position="sidebar" if widgets.vue() == "pc" else "top")
if widgets.vue() == "pc":
    st.sidebar.html("<style>" + widgets.css_menu_gauche() + "</style>")
pg.run()
