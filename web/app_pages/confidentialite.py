"""Page « Politique de confidentialité » : ce que le site fait, ou ne fait pas, des données."""

import streamlit as st

st.title("Politique de confidentialité")

st.subheader("Ce que le site collecte")
st.markdown(
    "Le site ne demande aucune donnée personnelle : pas de compte, pas de formulaire, pas de paiement. "
    "L'éditeur ne collecte volontairement aucune donnée personnelle et n'utilise ni mesure d'audience ni publicité."
)

st.subheader("Vos saisies de calcul")
st.markdown(
    "Les valeurs que vous saisissez sont traitées par le serveur pendant votre session, pour faire le calcul. "
    "Elles ne sont pas enregistrées sur le disque, ni partagées avec les autres visiteurs, ni conservées "
    "après la fermeture de la session. Les fichiers utiles (problème, projet, matériaux ajoutés, résultats, "
    "dossier de validation) se téléchargent sur votre appareil ; le serveur n'en garde pas de copie.\n\n"
    "Les fichiers que vous rechargez sont lus pendant la session puis oubliés avec elle."
)

st.subheader("Données techniques traitées par l'hébergeur")
st.markdown(
    "Comme tout site web, le site est servi par un hébergeur (voir les mentions légales). Celui-ci traite des données "
    "techniques de connexion, par exemple votre adresse IP, la date de la visite et le type de navigateur, "
    "pour acheminer les pages et protéger le service. Ces données sont gérées par l'hébergeur, selon sa propre "
    "politique de confidentialité. En cas d'erreur de calcul, le journal technique du serveur peut contenir "
    "le nom d'une combinaison de charges que vous avez saisi."
)

st.subheader("Ressources externes")
st.markdown(
    "Les pages du site n'appellent aucun service externe (ni police, ni image, ni script venus d'un autre site).\n\n"
    "Une seule exception, hors du site : le **dossier de validation** que vous téléchargez (fichier HTML) charge, "
    "quand vous l'ouvrez avec une connexion Internet, MathJax (pour les formules) depuis `cdnjs.cloudflare.com` "
    "et Plotly (pour les diagrammes) depuis son réseau de diffusion `cdn.plot.ly`. Votre navigateur "
    "contacte alors ces services, qui reçoivent par exemple votre adresse IP. Sans connexion, le dossier "
    "reste lisible, mais les formules apparaissent en LaTeX brut et les diagrammes sont absents."
)

st.subheader("Vos droits")
st.markdown(
    "Selon le Règlement général sur la protection des données (RGPD) et la loi Informatique et Libertés, "
    "vous pouvez demander l'accès à vos données, leur rectification, leur effacement, ou vous opposer à leur "
    "traitement. L'éditeur ne détenant aucune donnée personnelle vous concernant, il vous indiquera "
    "le cas échéant ce qu'il ignore.\n\n"
    "Pour exercer ces droits : [À COMPLÉTER PAR L'ÉDITEUR] (contact). "
    "Si vous estimez que vos droits ne sont pas respectés, vous pouvez déposer une réclamation auprès de la "
    "CNIL : [cnil.fr](https://www.cnil.fr)."
)

st.caption("Dernière mise à jour : 2 novembre 2026")
