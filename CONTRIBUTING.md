# Contribuer

Projet jeune, maintenu par une seule personne (étudiant) : les réponses peuvent prendre du temps.

## Signaler un bug
Ouvrir une *issue* GitHub avec le modèle « Bug » : version de MATLAB, système, étapes pour reproduire, résultat obtenu et résultat attendu (avec la source du calcul de référence), capture d'écran ou message d'erreur.

## Proposer une amélioration
Ouvrir une *issue* avec le modèle « Idée » avant de coder : besoin, cas d'usage, méthode ou référence théorique.

## Soumettre une modification
1. Faire un *fork* puis une branche dédiée.
2. Garder les changements petits et ciblés.
3. Conserver le style du code MATLAB existant (commentaires en français).
4. Lancer les tests : `run('desktop/tests/run_all_tests.m')` (contrôle rapide : `setenv('MECASTRUCT_FAST_TESTS','1')` avant). Ajouter un test pour tout nouveau calcul.
5. Citer la source de toute formule ou valeur nouvelle (voir [REFERENCES.md](REFERENCES.md)). Ne pas copier de texte, figure ou tableau protégés par le droit d'auteur.
6. Ouvrir une *pull request* qui décrit le changement.

En participant, vous acceptez le [code de conduite](CODE_OF_CONDUCT.md).
