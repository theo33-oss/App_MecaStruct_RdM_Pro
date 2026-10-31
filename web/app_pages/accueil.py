"""Page d'Accueil : par où commencer, unités de saisie, conventions de signe, « Comment faire », limites et sources.

Port de buildHomeTab (MecaStruct_App.m) ; la visite guidée devient un encadré de texte.
"""

import streamlit as st

from mecastruct.ui import state, widgets

state.init()

st.title("Bienvenue dans MecaStruct RdM Pro")
st.write(
    "Chaque onglet est déjà rempli avec un exemple d'école : cliquez sur « Calculer » pour voir un résultat, "
    "puis changez les valeurs. Que voulez-vous faire ?"
)

widgets.vue_selector()

st.page_link(
    "app_pages/poutres.py",
    label="Calculer une poutre (réactions, diagrammes, flèche)",
    icon="📏",
)
st.page_link("app_pages/sollicitations.py", label="Dimensionner un arbre en torsion", icon="🔩")
st.page_link("app_pages/flambage.py", label="Vérifier une poutre au flambage", icon="📐")
st.page_link("app_pages/convertisseur.py", label="Convertir une unité (psi, kip, in…)", icon="🔁")

with st.expander("Comment faire : une poutre de A à Z (5 étapes)", expanded=True):
    st.markdown(
        "1. **Appuis** : le tableau Appuis donne leur position et leur type "
        "(la légende dessous dit ce que chacun bloque).\n"
        "2. **Chargement** : les tableaux Forces et Charges réparties donnent le chargement. "
        "Une force vers le bas est négative. « Charge rapide » aide à saisir une charge répartie.\n"
        "3. **Calcul** : lancez le calcul, regardez le schéma, puis les diagrammes de T et de Mf : "
        "le moment est maximal où T change de signe.\n"
        "4. **Rapport** : lisez le rapport. Sa première ligne est le verdict : "
        "la poutre résiste-t-elle, avec quelle marge ?\n"
        "5. **Flambage** : une poutre comprimée doit aussi être vérifiée au flambage (page Flambage)."
    )

st.subheader("Projet")
widgets.project_bar()

st.subheader("À retenir avant de saisir")
st.markdown(
    "**Unités de saisie** : sections en mm, longueurs de poutre en m, forces en kN, moments en kN·m, "
    "charges réparties en kN/m, E et G en GPa, contraintes en MPa."
)
st.markdown(
    "**Signes** : une force vers le bas est négative (Fy < 0). N > 0 : traction. "
    "Mfz > 0 : fibres du haut comprimées, fibres du bas tendues. "
    "Torseur de cohésion : actions à droite de la coupe."
)
st.markdown(
    "Un tableau (appuis, forces…) se remplit avec « Ajouter » ; "
    "« Supprimer la sélection » retire la ligne choisie. "
    "Le panneau de gauche affiche la fiche de formules de la page ouverte."
)

with st.expander("Limites connues de l'application"):
    st.markdown(
        "- **Poutre hyperstatique avec Iyz ≠ 0** (section sans axes principaux, par exemple une cornière) : "
        "les réactions sont calculées plan par plan, le couplage y–z est ignoré. "
        "Saisir la section dans ses axes principaux (Iyz = 0). "
        "En isostatique, Iyz ≠ 0 est traité exactement.\n"
        "- **Dossier de validation, contrainte au point le plus sollicité** : non recalculée à la main "
        "pour une section dissymétrique ni pour Iyz ≠ 0 ; le dossier le dit.\n"
        "- **Normes** : seules les vérifications Eurocode 3 de la documentation sont normatives ; "
        "l'interaction N + M (annexe B) est à vérifier dans le texte de l'EN 1993-1-1.\n"
        "- **Formules** : MathJax demande Internet ; hors connexion, les équations restent en LaTeX brut."
    )

with st.expander("Auteur et sources"):
    st.markdown(
        "Application de **Théo Brun**, basée sur son cours de Résistance des Matériaux.\n\n"
        "- Cours de RDM de l'auteur : formules, conventions de signe, arbre de décision du flambage, matériaux, "
        "pressions de matage.\n"
        "- Théorie classique de la RDM : Fanchon (*Guide du calcul en mécanique*), *Mémotech*, "
        "cours de RDM des IUT GMP "
        "(Navier, Huygens, Jourawski, Euler, Castigliano, Ménabréa, cercles de Mohr, Tresca, Von Mises, Hooke).\n"
        "- Pilkey, *Peterson's Stress Concentration Factors* : ajustements des abaques Kt.\n"
        "- Tables de profilés Eurocode 3 et fabricants : dimensions et caractéristiques des profilés.\n"
        "- MathJax (cdnjs) : affichage des formules."
    )
