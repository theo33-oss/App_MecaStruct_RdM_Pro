# Mode d'emploi du plan de migration (pour Théo)

Ce dossier contient tout ce qu'il faut pour faire traduire MecaStruct RdM Pro en application web par
Claude Code, étape par étape, avec le modèle Haiku.

| Fichier | Rôle |
| --- | --- |
| `PLAN.md` | Plan maître : choix techniques, architecture, règles de traduction, liste des étapes |
| `CLAUDE.md` | Règles pour Claude Code, à lui faire lire en premier à chaque session (voir le message type ci-dessous) |
| `PROGRESSION.md` | Cases à cocher : où en est la migration |
| `BLOCAGES.md` | Où Claude Code note un problème qu'il n'arrive pas à résoudre |
| `etapes/E00…E33` | Une fiche par session de travail, très guidée |
| `matlab/export_*.m` | Deux scripts à lancer une fois dans MATLAB (étape E00) |

## 1. Une fois au début : étape E00 (à la main, ≈ 1 h)

Suivre `etapes/E00_preparation.md` : créer le dépôt GitHub, installer Python, lancer les deux scripts
MATLAB d'export. C'est la seule étape où tu fais tout toi-même.

## 2. Ensuite, pour chaque étape E01 à E33

1. Ouvrir un terminal dans le dossier du projet et lancer Claude Code avec Haiku :
   `claude --model haiku` (ou, dans une session déjà ouverte : `/model haiku`).
   Pour les étapes marquées **Sonnet conseillé** dans `PLAN.md` (E08, E09, E13, E31) :
   `claude --model sonnet`.
2. Commencer chaque étape par une session vide : `/clear`.
3. Coller ce message (en remplaçant `E06` par le numéro de l'étape) :

   ```
   Exécute l'étape E06 de la migration web.
   Lis d'abord « Migration MATLAB vers site web/CLAUDE.md », puis « Migration MATLAB vers site web/PLAN.md » (sections 3 et 4),
   Migration MATLAB vers site web/PROGRESSION.md, puis la fiche Migration MATLAB vers site web/etapes/E06_*.md.
   Suis la fiche à la lettre, dans l'ordre. Arrête-toi à la fin de l'étape.
   ```
4. À la fin, Claude Code doit afficher : tests verts, case cochée dans `PROGRESSION.md`, commit fait.
   Vérifie toi-même rapidement :
   - `python -m pytest -q` dans `web/` → tout vert ;
   - `git log --oneline -3` → le commit de l'étape est là ;
   - à partir de E23 : `streamlit run streamlit_app.py` et regarder la page.
5. `git push` pour sauvegarder sur GitHub (et, après E32, mettre le site en ligne).

## 3. Si ça bloque

- Claude Code écrit le problème dans `BLOCAGES.md` après 3 essais. Relance alors la même étape avec
  Sonnet (`/model sonnet`) en lui disant : « Lis Migration MATLAB vers site web/BLOCAGES.md et résous le dernier
  blocage, puis termine l'étape Exx. »
- Si un test golden échoue de très peu (ex. écart 1e-8 sur une intégration numérique), c'est normal pour
  les intégrations numériques : la fiche indique la tolérance à utiliser. Ne jamais accepter qu'il
  modifie un fichier golden.
- Si une étape a cassé quelque chose : `git reset --hard HEAD~1` revient au commit précédent.

## 4. Durée indicative

≈ 33 sessions de 20 à 60 min chacune. Les moteurs (E02 à E17) sont le cœur du travail : une fois
qu'ils passent les tests golden, l'interface (E23 à E30) va vite. Tu peux mettre en ligne une première
version dès E26 (Poutres) en faisant E32 en avance, puis compléter les autres pages.

## 5. Où travailler

- **Sur ton PC** (recommandé) : Claude Code en ligne de commande dans `C:\Users\tbrun\Documents\5_MecaStruct_RdM_Pro`.
  Tu vois tout de suite le résultat avec `streamlit run`.
- **Claude Code sur le web** (claude.ai/code) : possible une fois le dépôt sur GitHub. Il travaille dans
  une copie du dépôt et pousse une branche ; tu fusionnes ensuite sur GitHub.
