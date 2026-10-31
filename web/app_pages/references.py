"""Page « Références » : les normes sur lesquelles l'application s'appuie ou qu'elle cite.

Numéro, titre, année et rôle seulement : les textes des normes sont protégés (AFNOR) et ne sont pas reproduits.
Le détail clause par clause des vérifications Eurocode 3 est dans docs/NORMES.md du dépôt.
"""

import streamlit as st

# (numéro, titre, année, rôle dans l'application)
NORMES = [
    (
        "NF EN 1993-1-1",
        "Eurocode 3 : calcul des structures en acier. Partie 1-1 : règles générales et règles pour les bâtiments",
        "2005 + A1:2014",
        "Base de la flexion, du tranchant et du flambement : classes de section, résistances de flexion et de "
        "cisaillement, flambement par flexion, déversement, flexion + effort normal (page Poutres, Eurocode 3). "
        "Indice de classement AFNOR : à compléter.",
    ),
    (
        "NF EN 1993-1-1/NA",
        "Annexe nationale française à l'Eurocode 3, partie 1-1",
        "à compléter",
        "Proposée dans la page Poutres pour les coefficients partiels γM0 et γM1 (valeurs de l'EN). "
        "Les autres paramètres de l'annexe ne sont pas appliqués.",
    ),
    (
        "EN 1993-1-5",
        "Eurocode 3 : calcul des structures en acier. Partie 1-5 : plaques planes",
        "2006",
        "Voilement de l'âme par cisaillement (§5), signalé dans les résultats Eurocode 3 de la page Poutres.",
    ),
    (
        "EN 1993-1-9",
        "Eurocode 3 : calcul des structures en acier. Partie 1-9 : fatigue",
        "2005",
        "Citée seulement pour dire qu'elle n'est pas traitée : la fatigue de la page Poutres est une droite de "
        "Goodman, pas la vérification par catégories de détail.",
    ),
    (
        "EN 338",
        "Bois de structure : classes de résistance",
        "2016",
        "Source du bois C24 de la base de matériaux.",
    ),
    (
        "EN 1992-1-1",
        "Eurocode 2 : calcul des structures en béton. Partie 1-1 : règles générales et règles pour les bâtiments",
        "2004",
        "Source des bétons C25/30 et C30/37 de la base de matériaux (tableau 3.1).",
    ),
]

st.title("Références")
st.caption(
    "Normes sur lesquelles l'application s'appuie ou qu'elle cite. Seuls le numéro, le titre et l'année sont donnés : "
    "les textes sont protégés (AFNOR) et se consultent chez l'éditeur. Avant tout usage professionnel, vérifier les "
    "valeurs et les clauses dans le texte officiel et dans l'annexe nationale du pays."
)
for numero, titre, annee, role in NORMES:
    with st.container(border=True):
        st.markdown(f"**{numero}** — {annee}")
        st.markdown(titre)
        st.caption(f"Dans l'application : {role}")
