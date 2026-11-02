"""Page « Cookies et traceurs » : ce que le navigateur garde pour le fonctionnement du site."""

import streamlit as st

st.title("Cookies et traceurs")

st.markdown(
    "Ce site n'utilise que des traceurs strictement nécessaires à son fonctionnement. "
    "Il n'utilise aucune mesure d'audience ni aucune publicité. Pour cette raison, il n'affiche pas de bandeau "
    "de consentement."
)

st.subheader("Ce que le navigateur enregistre")
st.table(
    {
        "Nom": ["_streamlit_xsrf", "NEXT_LOCALE", "stActiveTheme-…, stSidebarCollapsed, stSidebarSectionsState"],
        "Type": ["Cookie", "Cookie", "Stockage local du navigateur"],
        "Rôle": [
            "Protège la session contre les requêtes frauduleuses (sécurité de Streamlit, le logiciel du site).",
            "Mémorise la langue de l'interface de Streamlit.",
            "Mémorisent vos préférences d'affichage : thème, menu replié ou déplié.",
        ],
    }
)
st.markdown(
    "Ces éléments sont posés par Streamlit, le logiciel sur lequel repose le site. Ils ne servent ni à vous suivre "
    "ni à vous identifier. Vous pouvez les effacer à tout moment dans les réglages de votre navigateur : "
    "le site continuera de fonctionner, avec ses réglages d'origine.\n\n"
    "Le choix d'affichage (PC, tablette, téléphone) et le contraste sont gardés seulement pendant la session, "
    "sur le serveur."
)

st.subheader("Hébergeur")
st.markdown(
    "L'hébergeur du site peut poser ses propres traceurs ou journaux techniques ; ils ne dépendent pas de l'éditeur. "
    "Voir la politique de confidentialité et les mentions légales."
)

st.caption("Dernière mise à jour : 2 novembre 2026")
