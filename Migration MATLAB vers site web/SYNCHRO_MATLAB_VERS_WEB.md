# Synchroniser une modification MATLAB vers le site web

À utiliser **après la migration** (ou en cours de route), chaque fois que Théo modifie le code MATLAB
(`*.m`) ou la base de données du `DataManager`. Le code MATLAB n'est jamais supprimé ni déplacé : il reste
la référence, et le site doit toujours donner les mêmes résultats que lui.

**Modèle conseillé** : Sonnet (Haiku possible pour une petite modification).

## Principe

1. MATLAB est la référence. Théo modifie MATLAB, puis relance les deux scripts d'export, ce qui
   régénère les fichiers de référence `web/data/*.json` et `web/tests/golden/*.json`.
2. Les tests Python comparent le code du site à ces nouveaux fichiers. Un test qui échoue montre
   exactement ce qui a changé côté MATLAB et reste à porter.
3. Claude Code porte la modification en Python jusqu'à ce que tous les tests soient verts.
4. Théo pousse sur GitHub, et Streamlit Community Cloud redéploie le site tout seul.

Cas particulier. Une modification MATLAB dans un module que la migration n'a pas encore atteint (étape
pas encore faite) n'a rien à synchroniser. Elle sera prise en compte quand l'étape sera faite, à condition
d'avoir relancé les scripts d'export avant.

## Ce que fait Théo (à la main)

1. Modifier le MATLAB et vérifier qu'il fonctionne.
2. **Relancer** dans MATLAB `Migration MATLAB vers site web/matlab/export_database_json.m` (si la base a
   changé, par exemple un nouveau profilé) et `export_golden_json.m` (si un calcul a changé).
3. Dans GitHub Desktop, faire un commit des modifications MATLAB **et** des JSON régénérés
   (message du type `MATLAB : <ce qui a changé>`).
4. Lancer Claude Code et coller le message type ci-dessous.

## Message type à coller dans Claude Code

```
Fais une synchronisation MATLAB vers web. Lis d'abord « Migration MATLAB vers site web/CLAUDE.md », puis « Migration MATLAB vers site web/SYNCHRO_MATLAB_VERS_WEB.md » et « Migration MATLAB vers site web/PLAN.md » (sections 3, 4 et 6), puis « Migration MATLAB vers site web/DERNIERE_SYNCHRO.md ». Suis la procédure à la lettre. Ne modifie, ne supprime et ne déplace aucun fichier MATLAB. Arrête-toi à la fin de la procédure.
```

## Procédure de Claude Code (dans l'ordre)

1. **Trouver le point de départ.** Lire `DERNIERE_SYNCHRO.md`. S'il contient un identifiant de commit,
   c'est la base `BASE`. Sinon, `BASE` est le commit qui a le message `E00 : export JSON de la base et
   des cas de référence MATLAB` (`git log --oneline --grep "E00 : export JSON"`).
2. **Lister les fichiers MATLAB modifiés** depuis `BASE` :
   `git diff --name-only BASE HEAD -- "*.m"` puis, pour chacun, `git diff BASE HEAD -- <fichier>`.
   Lister aussi les fichiers JSON de référence modifiés : `git diff --stat BASE HEAD -- web/data web/tests/golden`.
   Si rien n'a changé, le dire à Théo et s'arrêter.
3. **Associer chaque fonction MATLAB modifiée à son module Python** avec le tableau du `PLAN.md` (§ 6)
   et les fiches `etapes/*.md` (colonne « À lire »). Écrire cette liste à Théo avant de coder.
4. **Lancer les tests** (`python -m pytest -q`). Les tests qui échouent après le nouvel export des
   fichiers de référence désignent ce qui est à porter. Ne jamais corriger un test ni modifier un fichier
   golden : c'est le code Python qui change.
5. **Porter la modification** dans `web/mecastruct/` en respectant les conventions du `PLAN.md` § 4
   (noms MATLAB, unités SI, docstrings, aucun TODO). Relire seulement les lignes MATLAB modifiées
   (le résultat de `git diff`), pas le fichier entier.
6. **Cas particuliers.**
   - *Nouvelle fonction ou nouvelle option MATLAB* : la porter, puis écrire dans `BLOCAGES.md` le cas
     de test à ajouter dans `Migration MATLAB vers site web/matlab/export_golden_json.m` (ce script peut être
     modifié pendant une synchronisation) et demander à Théo de le relancer.
   - *Nouveau champ de saisie ou nouvel onglet* : ajouter le champ dans `web/app_pages/` et le service
     correspondant (`web/mecastruct/services/`), avec la même étiquette qu'en MATLAB.
   - *Base de données modifiée seulement* (matériau, profilé…) : aucun code à changer si les JSON
     régénérés sont lus par le site. Vérifier juste que les tests passent.
7. **Vérifier.** `python -m pytest -q` entièrement vert, `python -m ruff check .` sans erreur.
8. **Enregistrer.** Dans `DERNIERE_SYNCHRO.md`, écrire la date, l'identifiant du commit HEAD
   (`git rev-parse HEAD`) et 1 à 3 lignes sur ce qui a été synchronisé. Puis `git add -A` et
   `git commit -m "SYNC : <résumé>"`. Ne pas faire `git push`.
9. **Dire à Théo** de cliquer sur « Push origin » dans GitHub Desktop, puis d'attendre 1 à 2 minutes
   que le site se mette à jour.

## Garde-fous

- Aucun fichier MATLAB n'est modifié, supprimé, déplacé ni renommé par Claude Code.
- Si l'ancien Python et le nouveau MATLAB divergent sans que Théo l'ait voulu (test qui échoue sur
  un module que Théo n'a pas touché), le signaler dans `BLOCAGES.md` au lieu de « corriger » les tests.
- Après 3 tentatives infructueuses sur le même problème : arrêter et écrire dans `BLOCAGES.md`.
