"""Page « Conditions d'utilisation » : usage pédagogique, absence de garantie, limites du service."""

import streamlit as st

st.title("Conditions d'utilisation")

st.subheader("Un outil pédagogique et de pré-dimensionnement")
st.markdown(
    "MecaStruct RdM Pro aide à apprendre la Résistance des Matériaux et à pré-dimensionner des pièces et des "
    "structures. Il ne remplace ni une note de calcul certifiée, ni les normes en vigueur, ni l'avis d'un "
    "ingénieur."
)

st.subheader("Résultats à vérifier")
st.markdown(
    "Les résultats dépendent des hypothèses et des limites décrites dans le site (page d'accueil et dossier de "
    "validation). Vous devez les vérifier avant tout usage réel : le site est fourni gratuitement et sans garantie "
    "d'exactitude, d'exhaustivité ou d'adaptation à un besoin particulier."
)

st.subheader("Responsabilité")
st.markdown(
    "L'utilisation du site et de ses résultats se fait sous votre seule responsabilité. L'éditeur ne peut être "
    "tenu responsable des dommages, directs ou indirects, qui résulteraient d'une erreur de saisie, d'une "
    "interprétation des résultats ou d'une indisponibilité du site, dans les limites permises par la loi."
)

st.subheader("Limites du service")
st.markdown(
    "Le site est gratuit et hébergé sur une offre gratuite : il peut être mis en veille après un temps sans visite "
    "(le réveil prend quelques dizaines de secondes), être lent quand il y a beaucoup de visiteurs, "
    "ou être interrompu sans préavis. Les calculs en cours et les saisies non téléchargées sont perdus à "
    "la fermeture de la session."
)

st.subheader("Propriété intellectuelle")
st.markdown(
    "Les calculs et les textes sont l'œuvre de l'éditeur (voir les mentions légales). Vous pouvez utiliser les "
    "résultats de vos calculs librement ; vous ne pouvez pas reproduire le site, ses programmes ou ses textes "
    "sans accord de l'éditeur."
)

st.subheader("Droit applicable")
st.markdown("Ces conditions sont soumises au droit français. Tout litige relève des tribunaux français compétents.")

st.caption("Dernière mise à jour : 2 novembre 2026")
