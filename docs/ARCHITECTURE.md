# MecaStruct_RdM_Pro — Architecture et contrat d'interfaces

Ce document est la **source de vérité** des interfaces entre modules. Tout fichier `.m` doit respecter
exactement les noms de méthodes, d'arguments et de champs décrits ici. Une déviation n'est permise que si
elle est indispensable ; elle doit alors être signalée (et ce document mis à jour par l'intégrateur).

---

## 0. Conventions globales

### 0.1 Fichiers

| Fichier (racine du dossier) | Type | Rôle |
| --- | --- | --- |
| `DataManager.m` | classe *handle* (+ méthodes statiques) | Base de données : matériaux, profilés, pressions de matage, abaques Kt, table des intégrales de Mohr, formulaires LaTeX, conversions d'unités |
| `GeometryEngine.m` | classe statique | Propriétés des sections droites (analytique/Huygens, intégrale symbolique/numérique, tabulée) |
| `BeamAndTrussSolver.m` | classe statique | PFS, hyperstatisme (Ménabréa), torseur de cohésion (coupures et intégrale), treillis (nœuds et rigidité), utilitaires polynômes par morceaux |
| `SolicitationsEngine.m` | classe statique | Traction/compression, cisaillement (Jourawski), matage (clavette, goupille), torsion, flexion (contraintes, 4 méthodes de déformée), énergie, intégrales de Mohr ; délègue le flambage |
| `BucklingEngine.m` | classe statique | Flambage : Euler, Rankine, compression, arbre de décision, courbe de stabilité |
| `TensorAndCriteriaEngine.m` | classe statique | Tenseurs 3D/2D, Mohr, critères (Tresca, Von Mises, contrainte normale max), Hooke (isotrope, plan, orthotrope), extensométrie |
| `PlotEngine.m` | classe statique | Moteur d'affichage graphique : tous les tracés, sur un axe fourni (`axes` ou `uiaxes`) |
| `MecaStruct_App.m` | classe *handle* | Interface graphique programmatique (`uifigure`, `uigridlayout`, `uitabgroup`) |
| `tests/test_<Module>.m` | tests `matlab.unittest` (fonctions) | Un fichier de tests par module |
| `tests/run_all_tests.m` | script | Lance toute la suite |

Séparation stricte : **les moteurs de calcul ne tracent rien** et ne dépendent pas de l'interface ;
`PlotEngine` ne calcule rien de mécanique (il ne fait que tracer les structures renvoyées par les moteurs) ;
`MecaStruct_App` orchestre (lecture des champs → conversion SI → appel moteur → `PlotEngine` → affichage).

Dépendances autorisées (A → B signifie « A appelle B ») :

```
MecaStruct_App → tous
PlotEngine → BeamAndTrussSolver (utilitaires pp), GeometryEngine (outline, widthAt), TensorAndCriteriaEngine (lieux)
SolicitationsEngine → GeometryEngine, BeamAndTrussSolver, DataManager (statiques), BucklingEngine
DataManager, GeometryEngine, BeamAndTrussSolver, BucklingEngine, TensorAndCriteriaEngine → aucune dépendance interne
```

### 0.2 Style de code

- MATLAB R2025b (testé), compatible R2022b+. Code **100 % complet** : aucun `TODO`, aucun bloc tronqué.
- Commentaires, messages et textes d'interface **en français** ; noms de méthodes en camelCase (anglais ou
  termes du cours) **exactement comme ci-dessous**. Fichiers encodés en UTF-8.
- Moteurs : `classdef X` avec `methods (Static)` uniquement (sauf `DataManager`, classe *handle*).
- Chaque méthode publique a une ligne d'aide H1 et une description des entrées/sorties.
- Erreurs : `error('MecaStruct:<Module>:<id>', '<message en français>')`.
- Paramètres : passés sous forme de **structure** `p` à champs nommés ; les champs optionnels ont une valeur
  par défaut documentée (utiliser `isfield`).
- Chaque résultat de calcul est une structure scalaire qui contient au minimum :
  - `report` : `cell` colonne de `char`, lignes de texte en français décrivant la démarche et les résultats
    numériques (affichées telles quelles dans l'interface) ;
  - `latex` : `cell` de `char`, formules clés **avec valeurs numériques** au format LaTeX MATLAB (voir 0.4).
- Symbolic Math Toolbox **optionnelle** : tester `BeamAndTrussSolver.hasSymbolic()` /
  `DataManager.hasSymbolic()` (même implémentation : `license('test','Symbolic_Toolbox') && ~isempty(ver('symbolic'))`).
  Toute méthode symbolique a un repli numérique ; le champ `methodUsed` indique `'symbolique'` ou `'numérique'`.
- Aucune interaction bloquante dans les moteurs (pas de `input`, `uiwait`, `keyboard`, `pause`, dialogues).

### 0.3 Unités et repères

- **Moteurs : SI strict** — N, m, Pa, N·m, rad, °C, 1/°C, m², m³, m⁴. Les conversions se font dans
  l'interface via `DataManager.toSI` / `DataManager.fromSI`.
- Repère poutre : `x` = ligne moyenne (abscisse `s ∈ [0, L]`), `y` vertical vers le haut, `z` tel que
  (x, y, z) direct. Section droite dessinée avec `z` horizontal (vers la droite) et `y` vertical.
- `Iz = ∬ y² dS` (axe fort d'un profilé en I debout, flexion dans le plan (x,y) : `Mfz`, `Ty`, flèche `v`),
  `Iy = ∬ z² dS`, `Iyz = ∬ y z dS` (par rapport à G), `Ix = Iz + Iy` (moment polaire).
  **Attention profilés** : les catalogues Eurocode notent `Iy` l'axe fort ; ici `Iz(app) = Iy(EC)` et
  `Iy(app) = Iz(EC)` (idem pour W et r).
- Torseur de cohésion (convention du cours) : `{T_coh} = {Actions extérieures à DROITE} = −{Actions à GAUCHE}`,
  réduit au centre de surface G(s) de la section d'abscisse s :
  - `N(s) = Σ_droite Fx + ∫_s^L px dx` (N > 0 : traction)
  - `Ty(s) = Σ_droite Fy + ∫_s^L py dx`
  - `Tz(s) = Σ_droite Fz + ∫_s^L pz dx`
  - `Mt(s) = Σ_droite Mx`
  - `Mfz(s) = Σ_droite [(xi − s)·Fyi + Czi] + ∫_s^L (x − s)·py dx`
  - `Mfy(s) = Σ_droite [−(xi − s)·Fzi + Cyi] − ∫_s^L (x − s)·pz dx`
  - Relations différentielles : `dTy/ds = −py = q` (q = intensité descendante du cours), `Ty = −dMfz/ds`,
    `Tz = dMfy/ds`.
  - Sauts : force ponctuelle `Fy` en a : `Ty(a−) = Ty(a+) + Fy` ; couple `Cz` en a : `Mfz(a−) = Mfz(a+) + Cz`.
- Charges : composantes dans le repère global. `py < 0` = charge descendante (le `q` du cours vaut `−py`).
- Contrainte normale : `σxx(s,y,z) = N/S − (Mfz/Iz)·y + (Mfy/Iy)·z` (axes principaux). Si `|Iyz|` non
  négligeable, forme générale : `σ = N/S + b·y + c·z` avec `[Iz Iyz; Iyz Iy]·[b; c] = [−Mfz; Mfy]`.
- Déformée : `E·Iz·v'' = Mfz` (v selon +y) et `E·Iy·w'' = −Mfy` (w selon +z). Rotation `α(s) = dv/ds`.
- Réactions : efforts exercés **par l'appui sur la poutre**, composantes globales.

### 0.4 LaTeX MATLAB (testé sur R2025b)

Chaînes délimitées par `$...$`, interprétées par `text(...,'Interpreter','latex')`.

- **Autorisé** : `\frac`, `\sqrt`, `\int`, `\int\!\!\int` (intégrale double), `\oint`, `\sum`, `\left( \right)`,
  `\left[ \right]`, `\overline`, `\vec`, `\overrightarrow`, `\mathrm{}`, `\textrm{}`, `\mbox{}`, `\mathbf{}`,
  `\displaystyle`, `\le`, `\ge`, `\leq`, `\geq`, `\Rightarrow`, `\wedge`, `\cdot`, `\times`, `\,`, `\!`, `\ `,
  `\begin{array}{ccc} ... \end{array}`, lettres grecques (`\varphi`, `\epsilon`, `\varepsilon`, `\lambda`...).
- **Interdit** (provoque l'avertissement `MATLAB:handle_graphics:exceptions:SceneNode`) : `\iint`, `\iiint`,
  `\implies`, `\text{}`, `\dfrac`, `\tfrac`, `\boldsymbol`, `\geqslant`, `\leqslant`, environnements amsmath
  (`pmatrix`, `bmatrix`, `align`, `cases`).
- **Pas d'accents ni de caractères non ASCII dans les chaînes LaTeX** (mettre les textes accentués dans les
  champs texte simples). Longueur < 1000 caractères par chaîne.
- Validation automatique (utilisée dans les tests) : tracer la chaîne dans une figure invisible puis
  vérifier que `lastwarn` est vide.

### 0.5 Polynômes par morceaux (structure `pp`)

Tous les efforts intérieurs, déformées, etc. le long de la poutre sont des **polynômes par morceaux** exacts :

```matlab
pp.breaks  % 1×(n+1), abscisses croissantes (m), pp.breaks(1) = 0, pp.breaks(end) = L
pp.coefs   % 1×n cell ; pp.coefs{k} = vecteur ligne de coefficients (ordre polyval) en variable GLOBALE s,
           % valable sur [breaks(k), breaks(k+1)]
```

Utilitaires **statiques publics de `BeamAndTrussSolver`** (utilisés par `SolicitationsEngine`, `PlotEngine`,
`MecaStruct_App`) :

| Signature | Rôle |
| --- | --- |
| `v = ppEval(pp, s, side)` | évaluation vectorisée ; `side = 'right'` (défaut) ou `'left'` aux points de rupture ; en `s = L` → limite à gauche, en `s = 0` → limite à droite |
| `[s, v] = ppSample(pp, nPerSeg)` | échantillonnage pour tracé, points de rupture dupliqués (sauts visibles) ; `nPerSeg` défaut 60 |
| `ppI = ppIntegrate(pp, C0)` | primitive **continue** valant `C0` en `s = breaks(1)` |
| `ppD = ppDerivative(pp)` | dérivée |
| `ppC = ppAdd(ppA, ppB)` / `ppC = ppScale(pp, k)` / `ppC = ppMultiply(ppA, ppB)` | opérations (fusion des points de rupture) |
| `ppR = ppRefine(pp, newBreaks)` | ajoute des points de rupture |
| `I = ppIntegral(pp, a, b)` | intégrale exacte de a à b |
| `pp = ppZero(breaks)` / `pp = ppConst(breaks, c)` | constructeurs |
| `str = poly2latex(c, var)` | LaTeX d'un polynôme (`%.4g`, signes propres, `'0'` si nul), sans les `$` |
| `str = poly2str(c, var)` | version texte |
| `tf = hasSymbolic()` | disponibilité de la Symbolic Math Toolbox |

---

## 1. `DataManager` (classe handle)

### Propriétés (publiques en lecture)

- `Materials` : `table` — variables `Name` (string), `Category` (string), `E`, `G` (Pa), `nu`, `Re`, `Rm` (Pa),
  `alpha` (1/°C), `rho` (kg/m³), `Note` (string : plages de valeurs, source « cours » / « valeur usuelle »,
  remarques), `IsUser` (logical).
- `Profiles` : `struct` à champs `IPN, IPE, HEA, HEB, UPN, UAP`, chacun une `table` — `Name` (string, ex.
  `"IPN 200"`), `h`, `b`, `a` (épaisseur d'âme), `e` (épaisseur d'aile), `r` (rayon de congé), `S`, `Iz`
  (axe fort), `Iy` (axe faible), `Wz`, `Wy` (modules élastiques), `rz`, `ry`, `mass` (kg/m), `c` (UPN/UAP :
  distance dos d'âme → centre de gravité ; NaN sinon), `IsUser`. **Toutes valeurs en SI.**
- `BearingPressures` : `table` — `Liaison` (string), `Conditions` (string : `"médiocres"`, `"moyennes"`,
  `"très bonnes"`), `Pmin`, `Pmax` (Pa), `Note`.
- `UserFile` : chemin du fichier utilisateur (défaut `<dossier de DataManager.m>/userdata/MecaStruct_UserDB.mat`).

### Base matériaux par défaut (valeurs du cours, à saisir telles quelles)

- Aciers d'usage général, `E = 190 GPa` : nuances S185 (Re 185 / Rm 290), S235 (235/340), S275 (275/410),
  S355 (355/490) MPa ; ν = 0,3 ; G calculé ; α = 12e-6.
- Aciers de construction mécanique XC 38, XC 42, XC 48 : `E = 210 GPa`, `G = 80 GPa`, `ν = 0,3`,
  `α = 10 à 12,5e-6` (stocker 11e-6 et la plage en `Note`), Re/Rm usuels (note « valeur usuelle »).
- Aluminium 2017 et 5356 : `E = 90 GPa`, `G = 32 GPa`, `Re = 200 à 220`, `Rm = 300 à 320 MPa`,
  `α = 22,5 à 24e-6`. Note : « valeur du cours ; E usuel ≈ 72–74 GPa ».
- Titane TA6V : `E = 116 GPa`, `Re = 100 à 120`, `Rm = 300 à 350 MPa`, `α = 8,5 à 9,5e-6`. Note :
  « valeurs du support de cours ; valeurs usuelles TA6V : Re ≈ 830–880 MPa, Rm ≈ 900–950 MPa ».
- Fontes FGL et FGS (`G = 40 GPa`), Laiton (`G = 34 GPa`), Plexiglas (`G = 1,1 GPa`, note « le support
  indique 11 GPa, incohérent avec E ≈ 3 GPa ; 1,1 GPa retenu »). Autres constantes : valeurs usuelles.
- Toute constante manquante est complétée par `G = E/(2(1+ν))` ; si E, G et ν sont donnés, vérifier
  `−1 < ν < 0,5` et la cohérence (note si écart > 5 %).
- Valeurs : quand une plage est donnée, `Re`/`Rm` = borne basse (sécuritaire) et la plage en `Note`.

### Catalogue de profilés

IPN 80 → IPN 300 (au minimum 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300), IPE 80 → 600,
HEA 100 → 600, HEB 100 → 600, UPN 80 → 300, UAP 80 → 300 : valeurs normalisées réelles (tables européennes).
Cohérence vérifiée par les tests : `rz ≈ sqrt(Iz/S)` et `ry ≈ sqrt(Iy/S)` à 2 % près, `Wz ≈ Iz/(h/2)` à 2 %.

### Méthodes d'instance

| Signature | Rôle |
| --- | --- |
| `obj = DataManager()` / `DataManager(userFile)` | charge les valeurs par défaut puis fusionne le fichier utilisateur s'il existe |
| `names = listMaterials(obj)` | `string` colonne |
| `m = getMaterial(obj, name)` | `struct` : `Name, Category, E, G, nu, Re, Rm, alpha, rho, Note` |
| `addMaterial(obj, m)` | ajoute/remplace (complète via `completeIsotropic`), `IsUser = true` |
| `removeMaterial(obj, name)` | uniquement les matériaux utilisateur |
| `fams = listProfileFamilies(obj)` | `["IPN","IPE","HEA","HEB","UPN","UAP"]` |
| `names = listProfiles(obj, family)` | `string` colonne |
| `p = getProfile(obj, family, name)` | `struct` : `Family, Name, h, b, a, e, r, S, Iz, Iy, Wz, Wy, rz, ry, mass, c` |
| `addProfile(obj, family, p)` | ajout utilisateur (champs manquants `rz, ry, Wz, Wy` calculés) |
| `saveUserData(obj, file)` / `loadUserData(obj, file)` | sauvegarde/chargement `.mat` des seuls ajouts utilisateur (`file` optionnel → `UserFile`) |
| `[pmin, pmax] = getBearingPressure(obj, liaison, conditions)` | Pa |

### Méthodes statiques

| Signature | Rôle |
| --- | --- |
| `m = completeIsotropic(m)` | complète `E`, `G` ou `nu` manquant (NaN ou absent) |
| `v = toSI(val, unit)` / `v = fromSI(val, unit)` / `f = unitFactor(unit)` | unités : `'m','cm','mm','µm'/'um'`, `'m^2','cm^2','mm^2'`, `'m^3','cm^3','mm^3'`, `'m^4','cm^4','mm^4'`, `'N','kN','MN','daN'`, `'N.m','kN.m','N.mm','daN.m'`, `'N/m','kN/m','N/mm'`, `'Pa','kPa','MPa','GPa'`, `'rad','mrad','deg','°'`, `'rad/m','deg/m','°/m'`, `'1/°C','1e-6/°C'`, `'kg/m^3'`, `'kg/m'`, `'-'` ; erreur si unité inconnue |
| `tf = hasSymbolic()` | Symbolic Math Toolbox disponible |
| `keys = formulaKeys()` | `{'materiaux','geometrie','equilibre','cohesion','treillis','traction','cisaillement','matage','torsion','flexion','deformee','energie','mohr_integrales','flambage','tenseurs','mohr_cercle','criteres','hooke','extensometrie'}` |
| `sheet = formulaSheet(key)` | `struct` colonne, champs `title` (texte français), `latex` (LaTeX MATLAB valide, cf. 0.4), `vars` (texte : définitions des variables avec unités SI) — couvre **toutes** les formules du cahier des charges du module |
| `T = mohrTable()` | `struct` colonne des intégrales de Mohr `∫_0^l Mi·Mj ds` : `id`, `shape1`, `shape2`, `latex`, `fun` (handle `@(l, a, b)` où `a`, `b` sont les vecteurs de valeurs caractéristiques des deux diagrammes : rectangle `[M]`, triangle `[M]` (max à droite, 0 à gauche), triangle inversé, trapèze `[M_gauche M_droite]`, parabole `[f]` (charge uniforme, nulle aux extrémités, flèche f au milieu)) ; couvre au moins rectangle, triangle (même sens / opposé), trapèze, parabole et leurs produits croisés |
| `charts = ktCharts()` | `struct` colonne des abaques Kt : `id`, `title`, `params` (cellstr), `ranges`, `description` |
| `Kt = evalKt(id, prm)` | Kt pour l'abaque `id` (`'plaque_trou_traction'` (d/W), `'arbre_epaulement_flexion'`, `'arbre_epaulement_torsion'`, `'arbre_epaulement_traction'` (r/d, D/d)) ; ajustements de Peterson, interpolation en D/d, `Kt ≥ 1` |
| `T = bearingTableDefault()` | table des pressions admissibles par défaut (clavette/cannelures : glissant sous charge, glissant sans charge, fixe × conditions médiocres/moyennes/très bonnes ; plage globale 0,5 à 150 MPa) |

---

## 2. `GeometryEngine` (statique)

### Structure de section `sec`

`sec.type` et dimensions (m) :

| `type` | Champs | Origine O1 et disposition |
| --- | --- | --- |
| `'rectangle'` | `b` (selon z), `h` (selon y) | coin bas-gauche |
| `'disque'` | `D` | coin bas-gauche du carré englobant |
| `'couronne'` | `D`, `d` | idem |
| `'rectangle_creux'` | `B`, `H`, `t` (épaisseur constante) | coin bas-gauche |
| `'I'` | `h`, `b`, `tw` (âme, « a »), `tf` (aile, « e ») — symétrique | coin bas-gauche |
| `'T'` | `h`, `b`, `tw`, `tf` — aile en haut | coin bas-gauche |
| `'U'` | `h`, `b`, `tw`, `tf` — âme à gauche, ailes vers la droite | coin bas-gauche |
| `'L'` | `h` (aile verticale), `b` (aile horizontale), `t` | angle en bas à gauche |
| `'profile'` | `family`, `name` + tous les champs de `DataManager.getProfile` | géométrie simplifiée I (IPN/IPE/HEA/HEB) ou U (UPN/UAP) d'épaisseurs constantes `a`, `e` (congés ignorés) |
| `'composite'` | `rects` (N×4 : `[z1 z2 y1 y2]`), `holes` (M×4, optionnel) | repère utilisateur |

### Méthodes

| Signature | Rôle |
| --- | --- |
| `prims = primitives(sec)` | `struct` colonne : `kind` (`'rect'`,`'disk'`,`'annulus'`), `sign` (+1/−1), `z1,z2,y1,y2` (rect), `zc,yc,R,Ri` (disque/couronne), `label` (ex. `'Aile supérieure'`, `'Âme'`) — repère O1 |
| `P = analytical(sec)` | **Méthode A** : formules fermées + décomposition de Huygens |
| `P = integral(sec, mode)` | **Méthode B** : intégrales doubles, `mode = 'symbolique'` (défaut si dispo, `int`) ou `'numerique'` (`integral2`) ; `dS = dy dz` ou `r dr dθ` |
| `P = tabulated(sec)` | valeurs du catalogue (`type = 'profile'` uniquement ; erreur sinon) |
| `C = compare(sec)` | `table` : lignes `S, yG, zG, Iz, Iy, Iyz, Ix, rz, ry, Wz, Wy`, colonnes `Analytique`, `Integrale`, `Tabulee` (NaN si sans objet), `EcartMax_pct` |
| `b = widthAt(sec, y)` | largeur b(y), `y` mesuré **depuis G** (vectorisé) |
| `Q = firstMomentAbove(sec, y)` | moment statique par rapport à (G, z) de la partie au-dessus de `y` (depuis G) : `Q(y) = ∫_{η>y} η dS` (vectorisé, exact) |
| `out = outline(sec)` | `out.outer` (cell de N×2 `[z y]` fermés), `out.holes` (cell), repère O1 ; cercles discrétisés (≥ 120 points) |
| `f = shearFactors(sec)` | `kCours`, `kyCours` (valeurs du cours : rectangle 3/2 et 5/6 ; disque 4/3 et 6/7 ; tube `4/3(1 + rR/(r²+R²))` et 1/2 ; I `S/S_âme` et `S_âme/S` ; NaN sinon), `kNum = τmax·S/T` (Jourawski), `kyNum = Iz²/(S·∫ Q(y)²/b(y) dy)` (énergie) |

Champs de `P` (analytique et intégrale) : `S, zG, yG` (repère O1), `Iz, Iy, Iyz` (en G), `Ix` (= Iz+Iy),
`J` (constante de torsion : exacte disque/couronne, `≈ Σ b t³/3` parois minces ouvertes, formule de
Saint-Venant pour le rectangle, Bredt pour le caisson), `I1, I2` (principaux, I1 ≥ I2), `alphaP`
(angle rad de l'axe principal 1 depuis z), `rz, ry`, `vyTop, vyBot, vzRight, vzLeft` (distances de G aux
fibres extrêmes, positives), `Wz = Iz/max(vyTop,vyBot)`, `Wy = Iy/max(vzRight,vzLeft)`, `MO1z = ∬ y1 dS`,
`MO1y = ∬ z1 dS` (moments statiques dans le repère O1), `k, ky, kSource` (`'cours'` ou `'numérique'`),
`kz` (section réduite pour Tz : calcul énergétique sur la section aux axes y et z échangés ; = ky pour rectangle, disque, couronne),
`method` (`'analytique'` / `'intégrale symbolique'` / `'intégrale numérique'` / `'tabulée'`), `report`,
`latex`. En plus pour `analytical` : `huygens` (`table` : `Label, S_i, zG_i, yG_i, IGz_i, IGy_i, dy_i, dz_i,
SDy2, SDz2, Iz_i, Iy_i`). En plus pour `integral` : `integrals` (cell de chaînes LaTeX des intégrales
posées avec leurs bornes), `methodUsed`.

---

## 3. `BeamAndTrussSolver` (statique)

### Modèle de poutre `model`

```matlab
model.L          % longueur (m)
model.E, model.G % Pa
model.S          % m²
model.Iz, model.Iy, model.Ix   % m⁴ (Ix = constante de torsion utilisée pour G·Ix)
model.ky, model.kz             % coefficients de section réduite (défaut 1)
model.Iyz                      % m⁴, produit d'inertie (optionnel, défaut 0). Utilisé par SolicitationsEngine.deflection et
                               % strainEnergy (flexion déviée, courbures couplées). Le solveur de réactions (BeamAndTrussSolver)
                               % l'ignore : poutre hyperstatique avec Iyz ≠ 0 = LIMITE (réactions non fiables), signalée par l'application.
model.supports     % struct array : pos (m), type, name (ex. 'A')
model.pointLoads   % struct array : pos, Fx, Fy, Fz (N), name
model.pointMoments % struct array : pos, Mx, My, Mz (N·m), name
model.distLoads    % struct array : a, b (m), dir ('x'|'y'|'z'), coeffs (N/m, ordre polyval, variable
                   %   LOCALE ξ = s − a), name ; uniforme : coeffs = p0 ; linéaire p1→p2 : [(p2−p1)/(b−a), p1]
```

Tableaux vides autorisés (`struct('pos',{},...)` ou `[]`). Types d'appuis et degrés de liberté bloqués :

| `type` | u (x) | v (y) | w (z) | θx | θy | θz | inconnues en 2D (plan x,y) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `'appui_simple'` | | ✓ | ✓ | | | | 1 (Y) |
| `'rotule'` | ✓ | ✓ | ✓ | | | | 2 (X, Y) |
| `'pivot'` | ✓ | ✓ | ✓ | | | | 2 (X, Y) |
| `'pivot_glissant'` | | ✓ | ✓ | | | | 1 (Y) |
| `'encastrement'` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 3 (X, Y, M) |

Sous-problèmes indépendants : axial (u ; 1 équation), flexion (x,y) (v, θz ; 2 équations), flexion (x,z)
(w, θy ; 2 équations), torsion (θx ; 1 équation). Degré d'hyperstatisme de chaque sous-problème
= inconnues − équations ; `h.plan2D` = inconnues(axial + xy) − 3. Sous-problème sans liaison mais sans
charge (ou charges équilibrées) : réactions nulles, pas d'erreur. Mécanisme réel → erreur
`MecaStruct:Beam:mechanism`.

### `sol = solveBeam(model, opts)`

`opts` (tous optionnels) : `internalMethod` = `'both'` (défaut) | `'coupures'` | `'integrale'` ;
`hyperMethod` = `'both'` (défaut) | `'menabrea'` | `'integration'` ; `useSymbolic` (défaut `hasSymbolic()`) ;
`includeShearEnergy` (défaut `false`). Chemin rapide pour les appels internes répétés :
`struct('internalMethod','coupures','hyperMethod','menabrea','useSymbolic',false)`.

- Méthode **coupures** : sommes à droite zone par zone (points de rupture : 0, L, appuis, charges
  ponctuelles, couples, extrémités des charges réparties) → polynômes par morceaux.
- Méthode **intégrale** : intégration de `dTy/ds = −py`, `dMfz/ds = −Ty`, `dMfy/ds = Tz`, `dN/ds = −px` depuis
  l'extrémité s = L (valeurs nulles en L+) avec sauts aux charges ponctuelles ; `int` symbolique si dispo,
  sinon `polyint`. Les deux méthodes doivent coïncider (`sol.methodCheck` = écart relatif max).
- Hyperstatique, **Ménabréa** : choix automatique des inconnues hyperstatiques Xi (sous-système
  isostatique de base non singulier), `M = M0 + Σ Xi·mi`, système `Σj δij Xj = −δi0` avec
  `δij = ∫ mi mj/(EI) ds` (+ `∫ ti tj/(k G S) ds` si `includeShearEnergy`) ; idem axial (`∫ ni nj/(ES)`) et
  torsion (`∫ ti tj/(G Ix)`).
- Hyperstatique, **intégration** : réactions + 2 constantes inconnues résolues simultanément
  (équilibre + conditions cinématiques v = 0 / v' = 0 aux liaisons). Doit coïncider avec Ménabréa.

Champs de `sol` :

| Champ | Contenu |
| --- | --- |
| `model` | modèle normalisé (champs par défaut ajoutés) |
| `h` | `struct` : `axial, xy, xz, torsion, total, plan2D` |
| `isostatic` | logical (`h.total == 0`) |
| `reactions` | `struct` array par appui : `name, pos, type, Rx, Ry, Rz, Mx, My, Mz` |
| `breaks` | points de rupture |
| `N, Ty, Tz, Mt, Mfy, Mfz` | `pp` (méthode retenue : coupures) |
| `internalIntegral` | `struct` avec les mêmes 6 `pp` issus de la méthode intégrale (vide si non calculée) |
| `methodCheck` | écart relatif max entre les deux méthodes |
| `equations` | `struct` array par tronçon : `s1, s2`, et pour chaque composante `C ∈ {N,Ty,Tz,Mt,Mfy,Mfz}` un champ `C` (LaTeX complet `'$M_{fz}(s) = ...$'`) et `C_txt` (texte) |
| `extrema` | `struct` : pour chaque composante, champ `struct('max',…,'sMax',…,'min',…,'sMin',…)` |
| `menabrea` | si hyperstatique : `struct` par sous-problème hyperstatique : `unknowns` (noms), `delta` (matrice), `rhs`, `X` |
| `reactionsMenabrea`, `reactionsIntegration` | réactions par chaque méthode (vide si non calculées) |
| `report`, `latex` | démarche (PFS en A, transport des moments, hyperstatisme, système de Ménabréa, valeurs) |

### Treillis

```matlab
truss.nodes     % n×2 (ou n×3) coordonnées (m)
truss.bars      % m×2 indices de nœuds
truss.E, truss.S % scalaires ou m×1 (Pa, m²)
truss.supports  % n×dim logical (true = ddl bloqué)
truss.loads     % n×dim forces nodales (N)
truss.names     % cellstr n×1 optionnel (noms de nœuds)
```

`tsol = solveTruss(truss)` → `dim`, `h` (= m + r − dim·n), `isostatic`, `mechanism`, `L0` (m×1),
`N` (m×1), `nature` (cellstr `'Traction'` / `'Compression'` / `'Nul'`, seuil relatif 1e-9),
`sigma`, `dL` (`N·L/(E·S)`), `reactions` (n×dim), `displacements` (n×dim, méthode des rigidités),
`Njoints` (méthode des nœuds `[A]{N,R} = {−F}` si isostatique, sinon `[]`), `Nstiffness`, `A`,
`methodUsed`, `table` (`table` MATLAB : `Barre, Noeuds, L_m, N_N, Nature, Sigma_Pa, dL_m`), `report`, `latex`.

---

## 4. `SolicitationsEngine` (statique)

`τe` : `p.tauE` si fourni, sinon `Re/2` (`p.criterion = 'Tresca'`, défaut) ou `Re/√3` (`'VonMises'`).
Coefficient de sécurité `p.s` (défaut 1). Admissibles : `σadm = Re/s`, `τadm = τe/s`.

| Signature | Entrées `p` | Sorties principales |
| --- | --- | --- |
| `r = traction(p)` | `N` (N, >0 traction), `S0`, `L0`, `E`, `nu`, `alpha` (0), `dT` (0), `Kt` (1), `Re`, `s`, `dLmax` (Inf) ; optionnels `Sfun(x)`, `Nfun(x)`, `dTfun(x)` (handles vectorisés) | `sigmaNom, sigmaMax, sigmaAdm, okResistance, epsxx, epsyy, epszz, dVsurV` (= (1−2ν)σ/E + 3αΔT), `dL.analytique, dL.integrale, dL.energetique` (Castigliano mécanique + αΔT·L0), `K` (= E S0/L0), `U`, `okRigidite`, `methodUsed` |
| `r = shear(p)` | `T`, `S`, `k` (1), `Re` / `tauE`, `criterion`, `s`, `G` | `tauMoy, tauMax, tauE, tauAdm, ok, gamma` (= τmoy/G) |
| `prof = jourawski(sec, T, n)` | section, effort tranchant, nb de points (défaut 201) | `y` (depuis G, bas→haut), `b`, `Q`, `tau`, `tauMax`, `yAtMax`, `tauMoy`, `kNum`, `tauParabola` (rectangle : `1.5 T/S (1 − (2y/h)²)`, NaN sinon), `Iz`, `report`, `latex` |
| `r = bearing(p)` | `F`, `Smatee`, `Padm` | `P, ok, SminRequired` |
| `r = keyDesign(p)` | `C` (N·m), `D`, `a` (largeur), `b` (hauteur), `Padm`, `Re`/`tauE`, `criterion`, `s`, `L` (optionnel) | `F` (= 2C/D), `LminMatage` (= 4C/(D b Padm)), `LminCis` (= 2C/(a D τadm)), `Lmin`, et si `L` : `P` (= 4C/(D b L)), `tau` (= 2C/(a L D)), `okP, okTau` |
| `r = pinDesign(p)` | `F`, `d`, `e`, `Padm`, `Re`/`tauE`, `criterion`, `s`, `nShear` (1) | `P` (= 2F/(d e), formule du cours), `tau` (= 4F/(nShear π d²)), `dMin, eMin, okP, okTau` |
| `r = torsion(p)` | `Mt`, `D`, `d` (0), `G`, `L`, `Kt` (1), `Re`/`tauE`, `criterion`, `s`, `thetaAdm` (rad/m, Inf) ; optionnels `MtFun(s)`, `IxFun(s)` | `Ix, m, tauMaxNom, tauMax, tauAdm, okResistance, theta, okRigidite, phi.analytique, phi.integrale, phi.energetique, Ktorsion, U, rProfile, tauProfile, methodUsed` |
| `r = bendingStress(p)` | `sec` (ou `P` = propriétés), `N`, `Mfz`, `Mfy`, `Kt` (1), `Re`, `s` | `sigmaFun` (handle `@(y,z)` depuis G), `sigmaMaxTraction, sigmaMaxCompression, locMaxTraction, locMaxCompression` (`[y z]`), `sigmaMaxAbs, sigmaMaxKt, sigmaAdm, ok, neutralAxis` (`struct` : `a, b, c` de `a + b·y + c·z = 0`, et 2 points `[y z]`), `usedGeneralFormula`, `yProfile, sigmaProfile` (à z = 0) |
| `d = deflection(model, sol, opts)` | voir ci-dessous | |
| `U = strainEnergy(model, sol)` | | `UN, UTy, UTz, UMt, UMfy, UMfz, total` (exact, pp) |
| `M = mohrIntegral(ppA, ppB, a, b)` | deux `pp`, intervalle | `value` (exact), `valueTable`, `segments` (`table` : `s1, s2, shapeA, shapeB, formulaLatex, value, tabulated`), `allTabulated` |
| `b = buckling(p)` | | délègue à `BucklingEngine.analyze(p)` |

### `d = deflection(model, sol, opts)`

`opts` : `plane` (`'xy'` défaut : Mfz, Ty, Iz, ky, v | `'xz'` : Mfy, Tz, Iy, kz, w), `nPoints` (201),
`nCastigliano` (41), `includeShear` (true), `methods` (défaut les 4 : `{'integration','aires','castigliano','mohr'}`),
`s0` (points d'intérêt ; défaut : abscisse de la flèche max (intégration) et milieu de chaque travée).

1. **integration** : double intégration **tronçon par tronçon** avec 2n constantes `C1k, C2k`
   (continuité de v et v' aux frontières, v = 0 / v' = 0 aux liaisons ; système surdéterminé si
   hyperstatique → moindres carrés + résidu rapporté).
2. **aires** : `α(s) = α0 + (1/EI)∫_0^s M`, `v(s) = v0 + α0·s + (1/EI)·Σ Aire_k·(s − s̄_k)` (aires et
   centres de gravité des tronçons du diagramme), α0, v0 fixés par deux conditions d'appui.
3. **castigliano** (charge fictive / forces unités) : `v(s0) = ∫ M·m̄/(EI) + ∫ T·t̄/(k G S)` avec
   `m̄, t̄` = solution de `solveBeam` (chemin rapide) sous force unité en s0 (rotation : couple unité).
4. **mohr** : `mohrIntegral` sur chaque tronçon (décomposition trapèze + parabole ; hors table → Gauss).

Sorties : `d.s` ; `d.integration` (`v, alpha, vPP, alphaPP, constants` (`table` : `Troncon, s1, s2, C1, C2`),
`equations` (cell LaTeX), `fmax, sAtFmax, residual`) ; `d.aires` (`v, alpha, areas` (`table` : `Troncon,
s1, s2, Aire, sBar`), `fmax, sAtFmax`) ; `d.castigliano` (`s0, vBending, vShear, vTotal, alpha, fmax, sAtFmax`) ;
`d.mohr` (`s0, v, details` (cell de tables `mohrIntegral.segments` par point)) ; `d.comparison`
(`table` : `Methode, fmax_m, s_m, Ecart_pct`) ; `d.plane`, `d.report`, `d.latex`.

---

## 5. `BucklingEngine` (statique)

`r = analyze(p)` — `p` : `E`, `Re`, `S`, `Iz`, `Iy`, `L`, `condition` ∈ `{'encastre-libre','articule-articule',
'encastre-articule','encastre-encastre'}`, `s` (1), `P` (N de compression, optionnel), `lambdaCompression` (20).

Sorties : `Imin, Imax, axis` (`'y'` ou `'z'` : axe de flexion de plus faible inertie), `planeText`, `rmin`,
`coefLp` (2, 1, 1/√2, 0,5), `Lp`, `lambda`, `lambdaLim` (= π√(E/Re)), `regime` (`'compression'`,
`'rankine'`, `'euler'`), `PC` (= Re·S), `PE` (= π² E Imin/L'²), `PR` (= Re S/(1+(λ/λlim)²)),
`sigmaE` (= π² E/λ²), `Pcrit` (selon régime), `Padm` (= Pcrit/s), `ok` (si `P` fourni), `sigmaApplied`,
`modeShape` (handle `@(s)` normalisé, max = 1, selon les conditions : articulé `sin(πs/L)`, encastré-libre
`1 − cos(πs/(2L))`, encastré-encastré `(1 − cos(2πs/L))/2`, encastré-articulé `sin(ks) − ks + kL(1 − cos ks)`
normalisé, kL = 4,4934), `derivation` (cell LaTeX : équation `v'' + k²v = 0`, solution, conditions,
`sin(kL) = 0`…), `methodUsed`, `report`, `latex`.

`c = stabilityCurve(E, Re, lambdaVec)` (défaut `0:0.5:300`) → `lambda, sigmaEuler, sigmaRankine,
sigmaPalier, sigmaDesign` (arbre de décision), `lambdaLim, lambdaCompression`.

---

## 6. `TensorAndCriteriaEngine` (statique)

| Signature | Sorties |
| --- | --- |
| `r = principal(sig)` (3×3 symétrique) | `I1, I2, I3, charPoly` (`[1 −I1 I2 −I3]`), `rootsCharPoly`, `eigVals` (triées décroissantes), `sigmaI, sigmaII, sigmaIII, directions` (3×3, colonnes unitaires, trièdre direct), `tauMax` (= (σI − σIII)/2), `sigmaOct, tauOct, methodUsed, report, latex` |
| `r = facet(sig, n, t)` | `n` (normalisé), `Cn` (= σ·n), `sigmaN`, `tauVec`, `tauNorm`, `tauT` (si `t` fourni) |
| `r = plane2D(sxx, syy, sxy, theta)` | `sigma, tau` (formules du cours, θ en rad, vectorisé), `delta, rho, sigma1, sigma2, thetaP` (½·atan2(2σxy, σxx−σyy)), `tauMax2D, pointA` (`[σxx σxy]`), `pointB` (`[σyy −σxy]`), `circle` (N×2 `[σ τ]`), `report, latex` |
| `r = plane2DStrain(exx, eyy, exy, theta)` | idem en déformations (`ε`, `γ/2`) |
| `m = mohr3D(pr)` (`pr = [σI σII σIII]`) | `centers` (1×3), `radii` (1×3), `circles` (cell de N×2) |
| `c = criteria(pr, Re, s, sigmaR)` | `sigmaEqTresca` (= σI − σIII), `sigmaEqVM`, `sigmaMaxNormal`, `sigmaAdm`, `okTresca, okVM, okRankine` (vs `sigmaR/s`, `sigmaR` défaut Rm ou Re), `sfTresca, sfVM` (coefficients obtenus), `report, latex` |
| `L = yieldLoci(Re, s, sigmaR)` | lieux en contraintes planes (σ1, σ2) : `tresca` (hexagone fermé), `vonMises` (ellipse N×2), `rankine` (carré), `sigmaAdm` |
| `S = complianceIsotropic(E, nu)` / `C = stiffnessIsotropic(E, nu)` | 6×6 Voigt `[xx yy zz yz xz xy]`, déformations de cisaillement **ingénieur** (γ = 2ε) |
| `e = hooke3D(sigV, E, nu, alpha, dT)` / `sigV = hooke3DInverse(epsV, E, nu, alpha, dT)` | vecteurs de Voigt 6×1 |
| `r = planeStress(sxx, syy, sxy, E, nu)` | `exx, eyy, gxy, ezz` (= −ν(σxx+σyy)/E), `Sred` 3×3 |
| `r = planeStrain(exx, eyy, gxy, E, nu)` | `sxx, syy, sxy, szz` (= ν(σxx+σyy)), `Cred` 3×3 |
| `S = complianceOrthotropic(c)` / `C = stiffnessOrthotropic(c)` | `c` : `E1,E2,E3,nu12,nu13,nu23,G12,G13,G23` ; vérifie symétrie et définie positivité |
| `v = tensorToVoigt(T, kind)` / `T = voigtToTensor(v, kind)` | `kind` = `'stress'` ou `'strain'` |
| `r = gauge(K, eps)` / `eps = gaugeStrain(K, dRsurR)` | loi de Bridgman `ΔR/R = K ε` |
| `r = wheatstone(config, K, Vin, eps)` | `config` = `'quart'`, `'demi'`, `'complet'` ; `Vout = Vin·K/4·(ε1 − ε2 + ε3 − ε4)` (linéarisé) |
| `eps = bridgeStrain(config, K, Vin, Vout)` | déformation indiquée `4 Vout/(K Vin)` divisée par le facteur de pont |
| `r = rosette45(e1, e2, e3, E, nu)` | ε1 à 0°, ε2 à 90°, ε3 à 45° : `exx = e1, eyy = e2, exy = e3 − (e1+e2)/2, gxy`, déformations principales, `thetaP`, contraintes (contraintes planes), principales, `mohr` (centre, rayon), `report, latex` |
| `r = rosette60(e0, e60, e120, E, nu)` | idem rosette delta |

---

## 7. `PlotEngine` (statique)

Toutes les fonctions prennent l'axe cible en premier argument (`axes` ou `uiaxes`) ; si vide, une figure
est créée. Elles effacent l'axe, utilisent l'interpréteur LaTeX pour titres/labels/légendes, activent la
grille, et ne créent jamais de dialogue.

| Signature | Tracé |
| --- | --- |
| `beamSchematic(ax, model, sol)` | poutre, appuis (triangle, rotule, encastrement hachuré…), forces, couples, charges réparties, réactions (si `sol`) avec valeurs |
| `internalForces(axList, sol, comps)` | diagrammes alignés (`comps` ⊂ `{'N','Ty','Tz','Mt','Mfy','Mfz'}`, un axe par composante), aires remplies, extrema annotés, axes x liés |
| `deflection(axAlpha, axV, model, d)` | α(s) et v(s) : intégration (exacte), aires, Castigliano (avec tranchant, marqueurs), poutre non déformée, flèche max annotée |
| `section(ax, sec, P)` | géométrie, G, axes (G,y,z), axes principaux si Iyz ≠ 0, cotes |
| `sectionStress(axSigma, axTau, sec, P, bend, jour)` | profils σxx(y) (linéaire) et τ(y) (Jourawski, parabole de référence) |
| `bucklingCurve(ax, curve, b)` | palier σe, Euler, Rankine, courbe de dimensionnement, λ = 20 et λlim, point de fonctionnement |
| `mohr2D(ax, r2D, theta)` | cercle, A, B, centre δ, rayon ρ, σ1, σ2, angle 2θ, point de la facette |
| `mohr3D(ax, m3, point)` | tricercle, zone admissible hachurée/ombrée |
| `yieldLocus(ax, loci, point)` | hexagone de Tresca, ellipse de Von Mises, carré de Rankine, point de l'état de contrainte |
| `truss(ax, truss, tsol, scale)` | barres colorées (traction rouge, compression bleue, nulle grise), efforts, appuis, charges, déformée amplifiée |
| `formulaSheet(ax, sheet)` | rendu d'une fiche (titres, formules LaTeX, variables) ; renvoie la hauteur conseillée en pixels |
| `ktChart(ax, id)` | abaque Kt |
| `exportAxes(ax, file)` | `exportgraphics` (PNG, ou PDF vectoriel) |

---

## 8. `MecaStruct_App`

`app = MecaStruct_App()` ou `MecaStruct_App('Visible','off')` (tests). Propriété publique `UIFigure`.
`delete(app)` ferme proprement.

Onglets : **Base de données** (matériaux, profilés, matage, abaques Kt, ajout/sauvegarde utilisateur) ·
**Sections** · **Poutres** (modèle, PFS, cohésion, diagrammes, équations par tronçon, déformée 4 méthodes) ·
**Treillis** · **Sollicitations** (sous-onglets Traction, Cisaillement & Matage, Torsion, Flexion) ·
**Flambage** · **Tenseurs & Critères** · **Hooke & Jauges**. Panneau latéral **Formulaire rapide**
(`DataManager.formulaSheet`) mis à jour à chaque changement d'onglet.

Unités de saisie (converties en SI à la frontière) : dimensions de section en mm ; longueurs de poutre/treillis
en m ; forces en kN, moments en kN·m, charges réparties en kN/m ; E, G en GPa ; Re, Rm, contraintes en MPa ;
α en 10⁻⁶/°C ; déformations en µdéf. Résultats : kN, kN·m, MPa, mm, mrad.

Méthodes publiques (testables sans interaction) : `computeSection`, `computeBeam`, `computeTruss`,
`computeTraction`, `computeShear`, `computeKey`, `computePin`, `computeTorsion`, `computeBending`,
`computeBuckling`, `computeTensor`, `computeHooke`, `computeGauges`, `loadExample(tabName)`,
`status = runAllExamples()` (charge un exemple par onglet, calcule tout, renvoie un `struct` de booléens
et messages). Callbacks protégés par `try/catch` → `uialert` (non bloquant). Aucun `uiwait`.

---

## 9. Cas de validation (tests)

- Sections : rectangle 100×200 mm (S, Iz = bh³/12), disque, couronne, I, T, U, L (Iyz ≠ 0) ; analytique ≡
  intégrale (1e-9 relatif) ; Huygens ; `firstMomentAbove(0)` rectangle = b h²/8 ; Jourawski max rectangle =
  1,5 T/S ; `kyNum` rectangle = 5/6.
- Poutres : appui-appui force centrée (R = P/2, Mmax = PL/4, f = PL³/(48EI)) ; console force en bout
  (Mfz(0) = −PL, f = PL³/(3EI)) ; appui-appui charge uniforme (qL²/8, 5qL⁴/(384EI)) ; encastrée-appuyée
  uniforme (R_B = 3qL/8, M_A = −qL²/8) ; deux travées égales uniformes (appui central 5qL/4) ;
  bi-encastrée uniforme (−qL²/12, qL²/24, qL⁴/(384EI)) ; barre bi-encastrée effort axial au milieu
  (F/2 de chaque côté) ; coupures ≡ intégrale ; Ménabréa ≡ intégration ; 4 méthodes de flèche concordantes.
- Treillis : triangle isostatique (méthode des nœuds ≡ rigidité), treillis hyperstatique.
- Sollicitations : ΔL = NL/(ES) (3 méthodes), barre conique `ΔL = 4FL/(π E d1 d2)`, torsion φ = ML/(G Ix),
  arbre creux, clavette, goupille, contraintes de flexion.
- Flambage : régimes, PE, PR, courbe.
- Tenseurs : traction simple, cisaillement pur (Tresca 2τ, VM √3 τ), exemple 3D, cohérence Mohr 2D avec
  rotation `R σ Rᵀ`, `S·C = I`, rosette.
- DataManager : relation G, cohérence des profilés, aller-retour d'unités, **toutes les chaînes LaTeX des
  formulaires rendues sans avertissement**, table de Mohr ≡ intégration numérique.
- PlotEngine : chaque fonction s'exécute sans erreur ni avertissement sur des sorties réelles des moteurs.
- App : création invisible, `runAllExamples` entièrement OK, fermeture.

---

## Dossier de validation et convertisseur (hors moteurs)

- `ValidationReport.generate(app, key[, folder])` : écrit un HTML autonome (§1 données, §2 hypothèses et limites,
  §3 vérification à la main sans le solveur, §4 résultats, §5 diagrammes, §6 rapport, §7 formules utilisées, §8 avis).
  Clés : `Sec, Beam, Tr, Tra, Cis, Tor, Fle, Fla, Ten, Hoo, Jau`. `ValidationReport.handCheck(app, key)` renvoie `[nOK, nTot]`
  des contrôles du §3 (utilisé par les tests). Les limites de l'application sont des lignes `ko` du §2.
- `MecaStruct_App.convertUnits(val, quantity, from, to)` : convertisseur d'unités (dont `Écart de température` sans décalage
  d'origine et `Température absolue`).
- `MecaStruct_App.stressGeometry(sec, p)` : profilé du catalogue → valeurs tabulées pour `bendingStress` (sinon contour exact).
- Les moteurs appellent tous `DataManager.hasSymbolic()` (implémentation unique).
