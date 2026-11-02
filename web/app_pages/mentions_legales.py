"""Page « Mentions légales » : éditeur, hébergeur, contact et propriété intellectuelle."""

import streamlit as st

st.title("Mentions légales")

st.subheader("Éditeur du site")
st.markdown(
    "MecaStruct RdM Pro est un site gratuit, sans compte ni paiement.\n\n"
    "- **Éditeur** : [À COMPLÉTER PAR L'ÉDITEUR]\n"
    "- **Directeur de la publication** : l'éditeur, [À COMPLÉTER PAR L'ÉDITEUR]\n"
    "- **Contact** : [À COMPLÉTER PAR L'ÉDITEUR]"
)

st.subheader("Hébergeur")
st.markdown("[À COMPLÉTER PAR L'ÉDITEUR] (nom, adresse postale, coordonnées de contact de l'hébergeur)")

st.subheader("Propriété intellectuelle")
st.markdown(
    "Les calculs, les programmes et les textes de ce site sont l'œuvre de l'éditeur, à partir de son cours de "
    "Résistance des Matériaux. Toute reproduction ou réutilisation sans accord préalable de l'éditeur est interdite, "
    "sauf pour une courte citation avec indication de la source.\n\n"
    "Les ouvrages et cours qui ont servi de référence sont cités seulement par leur titre et leur auteur, "
    "dans la section « Auteur et sources » de la page d'accueil et dans la page Références. "
    "Leur contenu reste la propriété de leurs auteurs et éditeurs."
)

st.subheader("Signaler un problème")
st.markdown("Pour signaler une erreur de calcul ou un contenu à retirer, écrivez à l'adresse de contact ci-dessus.")

st.caption("Dernière mise à jour : 2 novembre 2026")
