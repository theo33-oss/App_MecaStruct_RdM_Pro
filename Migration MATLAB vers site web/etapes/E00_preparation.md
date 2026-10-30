# E00 — Préparation (à faire par Théo, à la main)

Durée : ≈ 1 h. Claude Code n'intervient pas dans cette étape.

## 1. Mettre le projet sur GitHub

Le dossier est déjà un dépôt git local (branche `main`) mais sans dépôt distant.

1. Sur https://github.com/new : nom `mecastruct-rdm-pro`, **Private** (ou Public : voir remarque),
   ne cocher ni README ni .gitignore. Créer.
2. Dans un terminal (PowerShell) dans `C:\Users\tbrun\Documents\5_MecaStruct_RdM_Pro` :
   ```
   git add -A
   git commit -m "Plan de migration web"
   git remote add origin https://github.com/<ton-identifiant>/mecastruct-rdm-pro.git
   git push -u origin main
   ```
Remarque : Streamlit Community Cloud (gratuit) accepte **une** application privée ; les autres doivent
être publiques. Un dépôt privé convient donc pour cette application.

## 2. Installer Python 3.12

1. Télécharger Python 3.12 (Windows installer 64-bit) sur https://www.python.org/downloads/ .
2. Pendant l'installation : cocher **« Add python.exe to PATH »**.
3. Vérifier dans un nouveau terminal : `py -3.12 --version` → `Python 3.12.x`.

## 3. Installer Claude Code (si ce n'est pas déjà fait)

Suivre https://docs.claude.com/en/docs/claude-code/setup puis, dans le dossier du projet : `claude`.
Vérifier que `/model haiku` fonctionne.

## 4. Exporter la base et les cas de référence depuis MATLAB

1. Ouvrir MATLAB (R2025b), ouvrir `Migration MATLAB vers site web/matlab/export_database_json.m`, cliquer sur
   **Exécuter**. Résultat attendu dans la fenêtre de commande : 8 fichiers listés dans `web/data/`.
2. Ouvrir `Migration MATLAB vers site web/matlab/export_golden_json.m`, cliquer sur **Exécuter** (quelques
   minutes). Résultat attendu : 8 fichiers `web/tests/golden/golden_*.json` et le nombre de cas de chacun.
3. Lire les lignes `[erreur MATLAB]` éventuelles affichées :
   - `erreur_tabulated_rectangle` et `truss_mecanisme` : erreurs **attendues** (cas de contrôle).
   - `convert_4` / `convert_5` : si l'erreur dit « Unité inconnue », c'est seulement que le libellé
     d'unité (ex. `°C`) est écrit autrement dans le catalogue ; sans gravité, le test Python lira les
     libellés dans `web/data/units.json`.
   - toute autre erreur : la noter dans `Migration MATLAB vers site web/BLOCAGES.md` (le cas sera ignoré par les
     tests Python, mais il vaut mieux comprendre pourquoi).
4. Ouvrir un des fichiers JSON (ex. `web/data/materials.json`) dans un éditeur pour vérifier qu'il est
   lisible (accents corrects).
5. Committer et pousser :
   ```
   git add -A
   git commit -m "E00 : export JSON de la base et des cas de référence MATLAB"
   git push
   ```

## 5. Cocher E00

Dans `Migration MATLAB vers site web/PROGRESSION.md`, cocher E00, committer.

C'est tout : la suite se fait avec Claude Code (voir `00_LISEZMOI.md`).
