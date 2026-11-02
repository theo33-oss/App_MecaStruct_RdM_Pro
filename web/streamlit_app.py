"""Point d'entrée de MecaStruct RdM Pro (version web) : navigation entre les pages.

Lancement local : streamlit run streamlit_app.py
"""

import streamlit as st

from mecastruct.ui import state, widgets

state.init()

pages = {
    "": [st.Page("app_pages/accueil.py", title="Accueil", icon="🏠", default=True)],
    "🧮 Calcul": [
        st.Page("app_pages/poutres.py", title="Poutres", icon="📏"),
        st.Page("app_pages/treillis.py", title="Treillis", icon="🔺"),
        st.Page("app_pages/sections.py", title="Sections", icon="🟦"),
        st.Page("app_pages/sollicitations.py", title="Sollicitations", icon="🔩"),
        st.Page("app_pages/flambage.py", title="Flambage", icon="📐"),
        st.Page("app_pages/tenseurs.py", title="Tenseurs & critères", icon="⭕"),
        st.Page("app_pages/hooke_jauges.py", title="Hooke & jauges", icon="📈"),
    ],
    "⚙️ Éléments de machines": [
        st.Page("app_pages/ajustements.py", title="Ajustements ISO 286", icon="📏"),
        st.Page("app_pages/frettage.py", title="Frettage", icon="🔧"),
        st.Page("app_pages/paliers_lisses.py", title="Paliers lisses", icon="⚙️"),
        st.Page("app_pages/roulements.py", title="Roulements", icon="🔘"),
        st.Page("app_pages/engrenages.py", title="Engrenages", icon="⚙️"),
        st.Page("app_pages/epicycloidaux.py", title="Trains épicycloïdaux", icon="🪐"),
        st.Page("app_pages/freins_embrayages.py", title="Freins et embrayages", icon="🛑"),
        st.Page("app_pages/dimensionnement_moteur.py", title="Dimensionnement moteur", icon="🔌"),
    ],
    "🛠️ Outils": [
        st.Page("app_pages/base_de_donnees.py", title="Base de données", icon="📚"),
        st.Page("app_pages/convertisseur.py", title="Convertisseur", icon="🔁"),
        st.Page("app_pages/references.py", title="Références", icon="📖"),
    ],
    "ℹ️ Informations": [
        st.Page("app_pages/mentions_legales.py", title="Mentions légales", icon="⚖️"),
        st.Page("app_pages/confidentialite.py", title="Politique de confidentialité", icon="🔒"),
        st.Page("app_pages/cookies.py", title="Cookies et traceurs", icon="🍪"),
        st.Page("app_pages/conditions.py", title="Conditions d'utilisation", icon="📄"),
    ],
}
pg = st.navigation(pages, position="sidebar" if widgets.vue() == "pc" else "top")
# après st.navigation pour que l'onglet du navigateur porte le titre de la page ouverte
st.set_page_config(
    page_title="MecaStruct RdM Pro" if pg.title == "Accueil" else f"{pg.title} · MecaStruct RdM Pro",
    page_icon=":material/architecture:",
    layout="wide",
    initial_sidebar_state="auto",
)
if widgets.vue() == "pc":
    st.sidebar.html("<style>" + widgets.css_menu_gauche() + "</style>")
if pg.title != "Accueil":  # l'accueil a déjà l'interrupteur, à côté du choix d'affichage
    widgets.contraste_toggle(st.sidebar)
pg.run()
