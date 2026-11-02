"""Bornes de taille des saisies (site public) : lignes d'un tableau, profondeur et longueur des textes.

Une saisie plus grosse est refusée avant tout calcul : un fichier importé ne peut pas imposer un calcul sans fin.
Aucun import de streamlit.
"""

from mecastruct.core.errors import MecaStructError

MAX_LIGNES = 200  # lignes par tableau (appuis, charges, combinaisons, nœuds, barres…)
MAX_TEXTE = 2000  # caractères par texte saisi
MAX_PROFONDEUR = 6  # imbrication listes / dictionnaires
MAX_POSITIONS = 500  # positions de base d'un convoi mobile (chacune résout la poutre, 2 à 3 ms)
_ID = "MecaStruct:App:invalidInput"


def checkLimits(saisie: dict) -> None:
    """Refuse une saisie trop volumineuse (tableau de plus de MAX_LIGNES lignes, texte trop long, imbrication).

    Entrée : `saisie` (dict de saisie ou données importées). La clé « section » (résultat de la page Sections,
    ajouté à la saisie par le dossier de validation) n'est pas contrôlée.
    Erreur : MecaStruct:App:invalidInput.
    """
    for cle, valeur in saisie.items():
        if cle != "section":
            _controle(valeur, str(cle), 1)


def _controle(v, chemin: str, profondeur: int) -> None:
    """Contrôle récursif d'une valeur : listes et dictionnaires bornés, textes bornés."""
    if profondeur > MAX_PROFONDEUR:
        raise MecaStructError(_ID, f"Saisie trop imbriquée (champ « {chemin} »).")
    if isinstance(v, str):
        if len(v) > MAX_TEXTE:
            raise MecaStructError(_ID, f"Texte trop long dans le champ « {chemin} » ({MAX_TEXTE} caractères au plus).")
    elif isinstance(v, (list, tuple)):
        if len(v) > MAX_LIGNES:
            raise MecaStructError(_ID, f"Trop de lignes dans « {chemin} » ({MAX_LIGNES} au plus par tableau).")
        for i, x in enumerate(v):
            _controle(x, f"{chemin}[{i}]", profondeur + 1)
    elif isinstance(v, dict):
        for k, x in v.items():
            _controle(x, f"{chemin}.{k}", profondeur + 1)
