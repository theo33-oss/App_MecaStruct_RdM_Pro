%EXPORT_GOLDEN_JSON Calcule des cas de référence avec les moteurs MATLAB et les écrit en JSON.
%   Ces fichiers (« golden files ») servent à vérifier que la version Python donne EXACTEMENT
%   les mêmes résultats que MATLAB. À lancer dans MATLAB (ouvrir ce fichier, « Exécuter »).
%   Durée : quelques minutes. Relancer si vous modifiez un moteur MATLAB.
%
%   Sortie : <racine du projet>/web/tests/golden/golden_<module>.json
%   Chaque fichier est une liste de cas :
%     id          identifiant court du cas
%     description texte
%     fonction    fonction MATLAB appelée (ex. 'GeometryEngine.analytical')
%     entrees     arguments (structures en SI)
%     sortie      résultat, nettoyé : les fonctions sont remplacées par '<fonction>', les tables
%                 par des listes d'objets, les polynômes par morceaux (pp) par
%                 {breaks, coefs, s, valeurs} (41 points), les champs texte longs (report, latex,
%                 equations...) sont retirés.
%     erreur      '' ou 'identifiant | message' si MATLAB a levé une erreur (cas d'erreur attendu)
%   NaN et Inf sont écrits NaN / Infinity / -Infinity (lus tels quels par json.load en Python).
%   Application de Théo Brun. Script écrit pour la migration web (Migration MATLAB vers site web).

here = fileparts(mfilename('fullpath'));
root = fileparts(fileparts(here));
addpath(fullfile(root, 'desktop'));
outDir = fullfile(root, 'web', 'tests', 'golden');
if ~exist(outDir, 'dir')
    mkdir(outDir);
end
fprintf('Export des cas de référence vers %s\n', outDir);
dm = DataManager();

%% ======================= DataManager ===================================
C = {};
C{end+1} = runCase('complete_E_nu', 'G calculé depuis E et nu', 'DataManager.completeIsotropic', ...
    struct('E', 210e9, 'nu', 0.3), @() DataManager.completeIsotropic(struct('E', 210e9, 'nu', 0.3)));
C{end+1} = runCase('complete_E_G', 'nu calculé depuis E et G', 'DataManager.completeIsotropic', ...
    struct('E', 210e9, 'G', 80e9), @() DataManager.completeIsotropic(struct('E', 210e9, 'G', 80e9)));
C{end+1} = runCase('complete_G_nu', 'E calculé depuis G et nu', 'DataManager.completeIsotropic', ...
    struct('G', 80e9, 'nu', 0.3), @() DataManager.completeIsotropic(struct('G', 80e9, 'nu', 0.3)));
dW = [0 0.1 0.2 0.3 0.5 0.7 0.9];
C{end+1} = runCase('kt_plaque', 'Kt plaque trouée', 'DataManager.evalKt', ...
    struct('id', 'plaque_trou_traction', 'prm', dW), @() DataManager.evalKt('plaque_trou_traction', dW));
prmShaft = [0.02 1.1; 0.05 1.2; 0.1 1.5; 0.2 2; 0.05 3; 0.1 1.05; 0.3 1.3];
for id = {'arbre_epaulement_flexion', 'arbre_epaulement_torsion', 'arbre_epaulement_traction'}
    C{end+1} = runCase(['kt_' id{1}], 'Kt arbre épaulé (une ligne de prm = [r/d D/d])', 'DataManager.evalKt', ...
        struct('id', id{1}, 'prm', prmShaft), @() ktRows(id{1}, prmShaft)); %#ok<SAGROW>
end
mt = dm.getMaterial('S235');
C{end+1} = runCase('get_material_S235', 'getMaterial', 'DataManager.getMaterial', 'S235', @() mt);
C{end+1} = runCase('get_profile_IPE200', 'getProfile', 'DataManager.getProfile', ...
    struct('family', 'IPE', 'name', 'IPE 200'), @() dm.getProfile('IPE', 'IPE 200'));
bp = dm.BearingPressures;
for k = 1:height(bp)
    li = char(bp.Liaison(k));
    co = char(bp.Conditions(k));
    C{end+1} = runCase(sprintf('bearing_%d', k), 'getBearingPressure (Pa)', 'DataManager.getBearingPressure', ...
        struct('liaison', li, 'conditions', co), @() bearingPair(dm, li, co)); %#ok<SAGROW>
end
writeCases(fullfile(outDir, 'golden_datamanager.json'), C);

%% ======================= GeometryEngine ================================
pIPE = dm.getProfile('IPE', 'IPE 200');
pUPN = dm.getProfile('UPN', 'UPN 100');
secs = { ...
    'rect_100x200',      struct('type', 'rectangle', 'b', 0.1, 'h', 0.2); ...
    'disque_50',         struct('type', 'disque', 'D', 0.05); ...
    'couronne_60_40',    struct('type', 'couronne', 'D', 0.06, 'd', 0.04); ...
    'caisson_100x150x5', struct('type', 'rectangle_creux', 'B', 0.1, 'H', 0.15, 't', 0.005); ...
    'I_200',             struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.0056, 'tf', 0.0085); ...
    'T_100',             struct('type', 'T', 'h', 0.1, 'b', 0.08, 'tw', 0.008, 'tf', 0.01); ...
    'U_120',             struct('type', 'U', 'h', 0.12, 'b', 0.055, 'tw', 0.007, 'tf', 0.009); ...
    'L_80x60x8',         struct('type', 'L', 'h', 0.08, 'b', 0.06, 't', 0.008); ...
    'composite_T_inv',   struct('type', 'composite', 'rects', [0 0.1 0 0.01; 0.045 0.055 0.01 0.11]); ...
    'profile_IPE200',    GeometryEngine.fromProfile(pIPE); ...
    'profile_UPN100',    GeometryEngine.fromProfile(pUPN)};
C = {};
for k = 1:size(secs, 1)
    id = secs{k, 1};
    sec = secs{k, 2};
    C{end+1} = runCase([id '_analytical'], 'Méthode A (Huygens)', 'GeometryEngine.analytical', sec, ...
        @() GeometryEngine.analytical(sec)); %#ok<SAGROW>
    C{end+1} = runCase([id '_integral_num'], 'Méthode B numérique', 'GeometryEngine.integral', ...
        struct('sec', sec, 'mode', 'numerique'), @() GeometryEngine.integral(sec, 'numerique')); %#ok<SAGROW>
    C{end+1} = runCase([id '_shearFactors'], 'Facteurs de cisaillement', 'GeometryEngine.shearFactors', sec, ...
        @() GeometryEngine.shearFactors(sec)); %#ok<SAGROW>
    C{end+1} = runCase([id '_compare'], 'Tableau de comparaison', 'GeometryEngine.compare', sec, ...
        @() GeometryEngine.compare(sec)); %#ok<SAGROW>
    try
        P = GeometryEngine.analytical(sec);
        ys = linspace(-0.98 * P.vyBot, 0.98 * P.vyTop, 9);
        C{end+1} = runCase([id '_widthAt'], 'b(y), y depuis G', 'GeometryEngine.widthAt', ...
            struct('sec', sec, 'y', ys), @() GeometryEngine.widthAt(sec, ys)); %#ok<SAGROW>
        C{end+1} = runCase([id '_firstMomentAbove'], 'Q(y), y depuis G', 'GeometryEngine.firstMomentAbove', ...
            struct('sec', sec, 'y', ys), @() GeometryEngine.firstMomentAbove(sec, ys)); %#ok<SAGROW>
    catch err
        fprintf('  (widthAt/firstMomentAbove ignorés pour %s : %s)\n', id, err.message);
    end
    if strcmp(sec.type, 'profile')
        C{end+1} = runCase([id '_tabulated'], 'Valeurs du catalogue', 'GeometryEngine.tabulated', sec, ...
            @() GeometryEngine.tabulated(sec)); %#ok<SAGROW>
    end
end
C{end+1} = runCase('erreur_tabulated_rectangle', 'Erreur attendue', 'GeometryEngine.tabulated', secs{1, 2}, ...
    @() GeometryEngine.tabulated(secs{1, 2}));
writeCases(fullfile(outDir, 'golden_geometry.json'), C);

%% ======================= Poutres =======================================
B = beamCases(pIPE);
C = {};
for k = 1:size(B, 1)
    id = B{k, 1};
    m = B{k, 3};
    C{end+1} = runCase([id '_solveBeam'], B{k, 2}, 'BeamAndTrussSolver.solveBeam', m, ...
        @() BeamAndTrussSolver.solveBeam(m)); %#ok<SAGROW>
    try
        sol = BeamAndTrussSolver.solveBeam(m);
        plane = B{k, 4};
        dop = struct('includeShear', false, 'plane', plane);
        C{end+1} = runCase([id '_deflection'], ['Flèche 4 méthodes, plan ' plane ', sans tranchant'], ...
            'SolicitationsEngine.deflection', struct('modele', m, 'opts', dop), ...
            @() SolicitationsEngine.deflection(m, sol, dop)); %#ok<SAGROW>
        C{end+1} = runCase([id '_strainEnergy'], 'Énergie de déformation', 'SolicitationsEngine.strainEnergy', m, ...
            @() SolicitationsEngine.strainEnergy(m, sol)); %#ok<SAGROW>
    catch err
        fprintf('  (flèche/énergie ignorées pour %s : %s)\n', id, err.message);
    end
end
writeCases(fullfile(outDir, 'golden_beam.json'), C);

%% ======================= Treillis ======================================
C = {};
tri = struct('nodes', [0 0; 4 0; 2 2], 'bars', [1 2; 2 3; 1 3], 'E', 210e9, 'S', 1e-4, ...
    'supports', logical([1 1; 0 1; 0 0]), 'loads', [0 0; 0 0; 0 -10e3]);
C{end+1} = runCase('truss_triangle', 'Triangle isostatique 2D', 'BeamAndTrussSolver.solveTruss', tri, ...
    @() BeamAndTrussSolver.solveTruss(tri));
hyp = struct('nodes', [0 0; 2 0; 4 0; 2 -2], 'bars', [1 4; 2 4; 3 4], 'E', 210e9, 'S', 2e-4, ...
    'supports', logical([1 1; 1 1; 1 1; 0 0]), 'loads', [0 0; 0 0; 0 0; 5e3 -20e3]);
C{end+1} = runCase('truss_3barres_hyper', 'Trois barres concourantes, hyperstatique', ...
    'BeamAndTrussSolver.solveTruss', hyp, @() BeamAndTrussSolver.solveTruss(hyp));
tp = struct('nodes', [0 0 0; 2 0 0; 1 1.732 0; 1 0.577 2], 'bars', [1 4; 2 4; 3 4], 'E', 210e9, ...
    'S', 1e-4, 'supports', logical([1 1 1; 1 1 1; 1 1 1; 0 0 0]), 'loads', [0 0 0; 0 0 0; 0 0 0; 0 0 -30e3]);
C{end+1} = runCase('truss_tripode_3D', 'Tripode 3D', 'BeamAndTrussSolver.solveTruss', tp, ...
    @() BeamAndTrussSolver.solveTruss(tp));
mec = struct('nodes', [0 0; 2 0; 2 2; 0 2], 'bars', [1 2; 2 3; 3 4], 'E', 210e9, 'S', 1e-4, ...
    'supports', logical([1 1; 0 0; 0 0; 0 0]), 'loads', [0 0; 0 0; 1e3 0; 0 0]);
C{end+1} = runCase('truss_mecanisme', 'Mécanisme (erreur ou drapeau attendu)', 'BeamAndTrussSolver.solveTruss', ...
    mec, @() BeamAndTrussSolver.solveTruss(mec));
writeCases(fullfile(outDir, 'golden_truss.json'), C);

%% ======================= Sollicitations ================================
C = {};
p = struct('N', 50e3, 'S0', 2e-4, 'L0', 1.5, 'E', 210e9, 'nu', 0.3, 'Re', 235e6, 's', 2);
C{end+1} = runCase('traction', 'Traction simple', 'SolicitationsEngine.traction', p, @() SolicitationsEngine.traction(p));
p2 = p; p2.alpha = 12e-6; p2.dT = 40; p2.Kt = 2.1; p2.dLmax = 1e-3;
C{end+1} = runCase('traction_thermique_Kt', 'Traction + dilatation + Kt', 'SolicitationsEngine.traction', p2, ...
    @() SolicitationsEngine.traction(p2));
p = struct('T', 20e3, 'S', 1e-3, 'k', 1.5, 'Re', 235e6, 's', 2, 'G', 80e9);
C{end+1} = runCase('shear', 'Cisaillement', 'SolicitationsEngine.shear', p, @() SolicitationsEngine.shear(p));
p.criterion = 'VonMises';
C{end+1} = runCase('shear_vonmises', 'Cisaillement (Von Mises)', 'SolicitationsEngine.shear', p, ...
    @() SolicitationsEngine.shear(p));
for k = [1 5 9]
    sec = secs{k, 2};
    C{end+1} = runCase(['jourawski_' secs{k, 1}], 'Jourawski, T = 30 kN, 51 points', 'SolicitationsEngine.jourawski', ...
        struct('sec', sec, 'T', 30e3, 'n', 51), @() SolicitationsEngine.jourawski(sec, 30e3, 51)); %#ok<SAGROW>
end
p = struct('F', 10e3, 'Smatee', 1e-4, 'Padm', 50e6);
C{end+1} = runCase('bearing', 'Matage', 'SolicitationsEngine.bearing', p, @() SolicitationsEngine.bearing(p));
p = struct('C', 200, 'D', 0.03, 'a', 0.008, 'b', 0.007, 'Padm', 60e6, 'Re', 235e6, 's', 2, 'L', 0.04);
C{end+1} = runCase('keyDesign', 'Clavette', 'SolicitationsEngine.keyDesign', p, @() SolicitationsEngine.keyDesign(p));
p = struct('F', 5e3, 'd', 0.008, 'e', 0.01, 'Padm', 80e6, 'Re', 235e6, 's', 2, 'nShear', 2);
C{end+1} = runCase('pinDesign', 'Goupille', 'SolicitationsEngine.pinDesign', p, @() SolicitationsEngine.pinDesign(p));
p = struct('Mt', 300, 'D', 0.04, 'd', 0, 'G', 80e9, 'L', 1, 'Re', 235e6, 's', 2);
C{end+1} = runCase('torsion_plein', 'Torsion arbre plein', 'SolicitationsEngine.torsion', p, @() SolicitationsEngine.torsion(p));
p.d = 0.03; p.Kt = 1.4; p.thetaAdm = 0.25 * pi / 180;
C{end+1} = runCase('torsion_creux', 'Torsion arbre creux + Kt', 'SolicitationsEngine.torsion', p, @() SolicitationsEngine.torsion(p));
p = struct('sec', secs{1, 2}, 'N', 10e3, 'Mfz', 5e3, 'Mfy', 1e3, 'Re', 235e6, 's', 1.5);
C{end+1} = runCase('bending_rect', 'Flexion composée rectangle', 'SolicitationsEngine.bendingStress', p, ...
    @() SolicitationsEngine.bendingStress(p));
p = struct('sec', secs{8, 2}, 'N', 0, 'Mfz', 1e3, 'Mfy', 0, 'Re', 235e6, 's', 1);
C{end+1} = runCase('bending_L', 'Flexion cornière (Iyz non nul)', 'SolicitationsEngine.bendingStress', p, ...
    @() SolicitationsEngine.bendingStress(p));
ppA = struct('breaks', [0 2], 'coefs', {{[5 0]}});
ppB = struct('breaks', [0 2], 'coefs', {{[-3 6 0]}});
C{end+1} = runCase('mohrIntegral_triangle_parabole', 'Intégrale de Mohr', 'SolicitationsEngine.mohrIntegral', ...
    struct('ppA', ppA, 'ppB', ppB, 'a', 0, 'b', 2), @() SolicitationsEngine.mohrIntegral(ppA, ppB, 0, 2));
writeCases(fullfile(outDir, 'golden_solicitations.json'), C);

%% ======================= Flambage ======================================
C = {};
conds = {'encastre-libre', 'articule-articule', 'encastre-articule', 'encastre-encastre'};
for k = 1:numel(conds)
    p = struct('E', 210e9, 'Re', 235e6, 'S', 1e-3, 'Iz', 2e-6, 'Iy', 5e-7, 'L', 2, ...
        'condition', conds{k}, 's', 2, 'P', 50e3);
    C{end+1} = runCase(['buckling_' conds{k}], 'Euler (élancé)', 'BucklingEngine.analyze', p, ...
        @() BucklingEngine.analyze(p)); %#ok<SAGROW>
end
for L = [0.05 0.6]
    p = struct('E', 210e9, 'Re', 235e6, 'S', 1e-3, 'Iz', 2e-6, 'Iy', 5e-7, 'L', L, ...
        'condition', 'articule-articule', 's', 2, 'P', 50e3);
    C{end+1} = runCase(sprintf('buckling_L%g', L), 'Compression ou Rankine', 'BucklingEngine.analyze', p, ...
        @() BucklingEngine.analyze(p)); %#ok<SAGROW>
end
lam = 0:10:300;
C{end+1} = runCase('stabilityCurve', 'Courbe de stabilité', 'BucklingEngine.stabilityCurve', ...
    struct('E', 210e9, 'Re', 235e6, 'lambdaVec', lam), @() BucklingEngine.stabilityCurve(210e9, 235e6, lam));
writeCases(fullfile(outDir, 'golden_buckling.json'), C);

%% ======================= Tenseurs, Hooke, jauges =======================
T = 'TensorAndCriteriaEngine';
sig = [80 30 0; 30 -20 10; 0 10 40] * 1e6;
C = {};
C{end+1} = runCase('principal', 'Contraintes principales 3D', [T '.principal'], sig, ...
    @() TensorAndCriteriaEngine.principal(sig, false));
C{end+1} = runCase('facet', 'Vecteur contrainte sur une facette', [T '.facet'], struct('sig', sig, 'n', [1 1 0]), ...
    @() TensorAndCriteriaEngine.facet(sig, [1 1 0]));
C{end+1} = runCase('plane2D', 'Mohr 2D, theta = 30°', [T '.plane2D'], [80e6 -20e6 30e6 pi/6], ...
    @() TensorAndCriteriaEngine.plane2D(80e6, -20e6, 30e6, pi/6));
C{end+1} = runCase('plane2DStrain', 'Mohr 2D déformations, theta = 20°', [T '.plane2DStrain'], ...
    [500e-6 -200e-6 150e-6 pi/9], @() TensorAndCriteriaEngine.plane2DStrain(500e-6, -200e-6, 150e-6, pi/9));
pr = [100 40 -20] * 1e6;
C{end+1} = runCase('mohr3D', 'Tricercle', [T '.mohr3D'], pr, @() TensorAndCriteriaEngine.mohr3D(pr));
C{end+1} = runCase('criteria', 'Tresca, Von Mises, Rankine', [T '.criteria'], struct('pr', pr, 'Re', 235e6, 's', 1.5), ...
    @() TensorAndCriteriaEngine.criteria(pr, 235e6, 1.5));
C{end+1} = runCase('yieldLoci', 'Lieux de plasticité', [T '.yieldLoci'], struct('Re', 235e6, 's', 1.5), ...
    @() TensorAndCriteriaEngine.yieldLoci(235e6, 1.5));
C{end+1} = runCase('complianceIsotropic', '[S] 6x6', [T '.complianceIsotropic'], [210e9 0.3], ...
    @() TensorAndCriteriaEngine.complianceIsotropic(210e9, 0.3));
C{end+1} = runCase('stiffnessIsotropic', '[C] 6x6', [T '.stiffnessIsotropic'], [210e9 0.3], ...
    @() TensorAndCriteriaEngine.stiffnessIsotropic(210e9, 0.3));
sv = [100 50 0 0 0 20]' * 1e6;
C{end+1} = runCase('hooke3D', 'Hooke 3D + dilatation', [T '.hooke3D'], struct('sigV', sv, 'E', 210e9, 'nu', 0.3, 'alpha', 12e-6, 'dT', 50), ...
    @() TensorAndCriteriaEngine.hooke3D(sv, 210e9, 0.3, 12e-6, 50));
ev = TensorAndCriteriaEngine.hooke3D(sv, 210e9, 0.3, 12e-6, 50);
C{end+1} = runCase('hooke3DInverse', 'Hooke 3D inverse', [T '.hooke3DInverse'], struct('epsV', ev, 'E', 210e9, 'nu', 0.3, 'alpha', 12e-6, 'dT', 50), ...
    @() TensorAndCriteriaEngine.hooke3DInverse(ev, 210e9, 0.3, 12e-6, 50));
C{end+1} = runCase('planeStress', 'Contraintes planes', [T '.planeStress'], [100e6 50e6 20e6 210e9 0.3], ...
    @() TensorAndCriteriaEngine.planeStress(100e6, 50e6, 20e6, 210e9, 0.3));
C{end+1} = runCase('planeStrain', 'Déformations planes', [T '.planeStrain'], [500e-6 -100e-6 200e-6 210e9 0.3], ...
    @() TensorAndCriteriaEngine.planeStrain(500e-6, -100e-6, 200e-6, 210e9, 0.3));
co = struct('E1', 140e9, 'E2', 10e9, 'E3', 10e9, 'nu12', 0.3, 'nu13', 0.3, 'nu23', 0.4, ...
    'G12', 5e9, 'G13', 5e9, 'G23', 3.5e9);
C{end+1} = runCase('complianceOrthotropic', 'Orthotrope [S]', [T '.complianceOrthotropic'], co, ...
    @() TensorAndCriteriaEngine.complianceOrthotropic(co));
C{end+1} = runCase('stiffnessOrthotropic', 'Orthotrope [C]', [T '.stiffnessOrthotropic'], co, ...
    @() TensorAndCriteriaEngine.stiffnessOrthotropic(co));
C{end+1} = runCase('gauge', 'Jauge K = 2,1', [T '.gauge'], [2.1 500e-6], @() TensorAndCriteriaEngine.gauge(2.1, 500e-6));
C{end+1} = runCase('wheatstone_quart', 'Pont quart', [T '.wheatstone'], struct('config', 'quart', 'K', 2.1, 'Vin', 5, 'eps', [500e-6 0 0 0]), ...
    @() TensorAndCriteriaEngine.wheatstone('quart', 2.1, 5, [500e-6 0 0 0]));
C{end+1} = runCase('wheatstone_demi', 'Pont demi', [T '.wheatstone'], struct('config', 'demi', 'K', 2.1, 'Vin', 5, 'eps', [500e-6 -150e-6 0 0]), ...
    @() TensorAndCriteriaEngine.wheatstone('demi', 2.1, 5, [500e-6 -150e-6 0 0]));
C{end+1} = runCase('wheatstone_complet', 'Pont complet', [T '.wheatstone'], struct('config', 'complet', 'K', 2.1, 'Vin', 5, 'eps', [500e-6 -150e-6 500e-6 -150e-6]), ...
    @() TensorAndCriteriaEngine.wheatstone('complet', 2.1, 5, [500e-6 -150e-6 500e-6 -150e-6]));
C{end+1} = runCase('bridgeStrain_quart', 'Déformation lue (pont quart)', [T '.bridgeStrain'], struct('config', 'quart', 'K', 2.1, 'Vin', 5, 'Vout', 1.3e-3), ...
    @() TensorAndCriteriaEngine.bridgeStrain('quart', 2.1, 5, 1.3e-3));
C{end+1} = runCase('rosette45', 'Rosette 45°', [T '.rosette45'], [600e-6 -200e-6 300e-6 210e9 0.3], ...
    @() TensorAndCriteriaEngine.rosette45(600e-6, -200e-6, 300e-6, 210e9, 0.3));
C{end+1} = runCase('rosette60', 'Rosette 60°', [T '.rosette60'], [600e-6 -100e-6 250e-6 210e9 0.3], ...
    @() TensorAndCriteriaEngine.rosette60(600e-6, -100e-6, 250e-6, 210e9, 0.3));
writeCases(fullfile(outDir, 'golden_tensors.json'), C);

%% ======================= Eurocode 3 et fatigue =========================
C = {};
p300 = dm.getProfile('IPE', 'IPE 300');
s300 = GeometryEngine.fromProfile(p300);
J300 = GeometryEngine.analytical(s300).J;
d = DesignChecks.ibeamDims(s300);
C{end+1} = runCase('ibeamDims_IPE300', 'Dimensions', 'DesignChecks.ibeamDims', s300, @() DesignChecks.ibeamDims(s300));
C{end+1} = runCase('classify_flexion', 'Classe, flexion seule', 'DesignChecks.classify', ...
    struct('d', d, 'fy', 235e6, 'Nc', 0, 'Mz', 100e3, 'A', p300.S, 'Iz', p300.Iz), ...
    @() DesignChecks.classify(d, 235e6, 0, 100e3, p300.S, p300.Iz));
C{end+1} = runCase('classify_compression', 'Classe, compression + flexion', 'DesignChecks.classify', ...
    struct('d', d, 'fy', 355e6, 'Nc', 600e3, 'Mz', 50e3, 'A', p300.S, 'Iz', p300.Iz), ...
    @() DesignChecks.classify(d, 355e6, 600e3, 50e3, p300.S, p300.Iz));
b = DesignChecks.ec3Bending(d, p300.S, p300.Iz, 235e6, 1.0, 100e3, 150e3, 0);
C{end+1} = runCase('ec3Bending', 'Flexion + tranchant', 'DesignChecks.ec3Bending', ...
    struct('d', d, 'S', p300.S, 'Iz', p300.Iz, 'fy', 235e6, 'gM0', 1, 'MEd', 100e3, 'VEd', 150e3, 'Nc', 0), @() b);
C{end+1} = runCase('ec3Bending_VEd_fort', 'Flexion + fort tranchant (6.2.8)', 'DesignChecks.ec3Bending', ...
    struct('d', d, 'S', p300.S, 'Iz', p300.Iz, 'fy', 235e6, 'gM0', 1, 'MEd', 100e3, 'VEd', 400e3, 'Nc', 0), ...
    @() DesignChecks.ec3Bending(d, p300.S, p300.Iz, 235e6, 1.0, 100e3, 400e3, 0));
ltb = DesignChecks.ec3LateralTorsional(d, true, b.W, 235e6, 1.0, 210e9, 81e9, p300.Iy, J300, 4, 1, 100e3);
C{end+1} = runCase('ec3LateralTorsional', 'Déversement, Lcr = 4 m', 'DesignChecks.ec3LateralTorsional', ...
    struct('d', d, 'rolled', true, 'W', b.W, 'fy', 235e6, 'gM1', 1, 'E', 210e9, 'G', 81e9, 'Iweak', p300.Iy, ...
    'It', J300, 'Lcr', 4, 'C1', 1, 'MEd', 100e3), @() ltb);
buck = DesignChecks.ec3FlexuralBuckling(d, true, p300.S, p300.Iz, p300.Iy, [6 3], 235e6, 210e9, 1.0, 300e3);
C{end+1} = runCase('ec3FlexuralBuckling', 'Flambement, Lcr = [6 3] m', 'DesignChecks.ec3FlexuralBuckling', ...
    struct('d', d, 'rolled', true, 'A', p300.S, 'Iy', p300.Iz, 'Iz', p300.Iy, 'Lcr', [6 3], 'fy', 235e6, ...
    'E', 210e9, 'gM1', 1, 'NEd', 300e3), @() buck);
C{end+1} = runCase('ec3AxialBending', 'N + M (6.2.9)', 'DesignChecks.ec3AxialBending', ...
    struct('b', b, 'A', p300.S, 'fy', 235e6, 'gM0', 1, 'NEd', 300e3, 'MEd', 100e3), ...
    @() DesignChecks.ec3AxialBending(d, b, p300.S, 235e6, 1.0, 300e3, 100e3));
cls = pickField(b, {'cls', 'class', 'classe', 'sectionClass'}, 1);
if isstruct(cls)   % b.cls est la structure de classification : on prend le numéro de classe
    cls = pickField(cls, {'class', 'classe', 'sectionClass'}, 1);
end
C{end+1} = runCase('ec3Interaction', 'Interaction 6.61/6.62', 'DesignChecks.ec3Interaction', ...
    struct('cls', cls, 'A', p300.S, 'W', b.W, 'fy', 235e6, 'gM1', 1, 'NEd', 300e3, 'MEd', 100e3, 'Cmy', 1, 'CmLT', 1), ...
    @() DesignChecks.ec3Interaction(cls, buck, ltb, p300.S, b.W, 235e6, 1.0, 300e3, 100e3, 1, 1));
C{end+1} = runCase('ec3WebShear', 'Voilement âme', 'DesignChecks.ec3WebShear', ...
    struct('d', d, 'fy', 235e6, 'gM1', 1, 'VEd', 150e3), @() DesignChecks.ec3WebShear(d, 235e6, 1.0, 150e3));
C{end+1} = runCase('goodman_R0', 'Goodman, R = 0', 'DesignChecks.goodman', [150e6 0 1.8 400e6 0.8 0.9], ...
    @() DesignChecks.goodman(150e6, 0, 1.8, 400e6, 0.8, 0.9));
C{end+1} = runCase('goodman_alterne', 'Goodman, R = -1', 'DesignChecks.goodman', [150e6 -1 1 400e6 1 1], ...
    @() DesignChecks.goodman(150e6, -1, 1, 400e6, 1, 1));
writeCases(fullfile(outDir, 'golden_design.json'), C);

%% ======================= Convertisseur =================================
C = {};
conv = {1, 'Longueur', 'in', 'mm'; 10, 'Force', 'kip', 'kN'; 1, 'Contrainte et pression', 'ksi', 'MPa'; ...
    100, 'Température absolue', '°C', '°F'; 20, 'Écart de température', '°C', '°F'};
for k = 1:size(conv, 1)
    a = conv(k, :);
    C{end+1} = runCase(sprintf('convert_%d', k), 'convertUnits', 'MecaStruct_App.convertUnits', ...
        struct('val', a{1}, 'quantity', a{2}, 'from', a{3}, 'to', a{4}), ...
        @() MecaStruct_App.convertUnits(a{1}, a{2}, a{3}, a{4})); %#ok<SAGROW>
end
writeCases(fullfile(outDir, 'golden_units.json'), C);

fprintf('Terminé. Vérifiez qu''aucun cas n''a d''erreur inattendue (champ "erreur").\n');

%% =======================================================================
%%                          FONCTIONS LOCALES
%% =======================================================================

function B = beamCases(pIPE)
% Liste des poutres de référence : {id, description, modèle SI, plan de flèche}.
B = {};
m = base(4); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 4, 'appui_simple', 'B'); m = addF(m, 2, 0, -10e3, 0);
B(end+1, :) = {'appui_appui_force_centree', 'R = P/2, Mmax = PL/4, f = PL³/48EI', m, 'xy'};
m = base(3); m = addSup(m, 0, 'encastrement', 'A'); m = addF(m, 3, 0, -5e3, 0);
B(end+1, :) = {'console_force_bout', 'Mfz(0) = -PL, f = PL³/3EI', m, 'xy'};
m = base(6); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 6, 'appui_simple', 'B'); m = addQ(m, 0, 6, 'y', -5e3);
B(end+1, :) = {'appui_appui_uniforme', 'qL²/8, 5qL⁴/384EI', m, 'xy'};
m = base(5); m = addSup(m, 0, 'encastrement', 'A'); m = addSup(m, 5, 'appui_simple', 'B'); m = addQ(m, 0, 5, 'y', -8e3);
B(end+1, :) = {'encastree_appuyee_uniforme', 'RB = 3qL/8, MA = -qL²/8', m, 'xy'};
m = base(8); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 4, 'appui_simple', 'B'); m = addSup(m, 8, 'appui_simple', 'C');
m = addQ(m, 0, 8, 'y', -10e3);
B(end+1, :) = {'deux_travees_uniforme', 'appui central 5qL/4', m, 'xy'};
m = base(6); m = addSup(m, 0, 'encastrement', 'A'); m = addSup(m, 6, 'encastrement', 'B'); m = addQ(m, 0, 6, 'y', -4e3);
B(end+1, :) = {'bi_encastree_uniforme', '-qL²/12, qL²/24, qL⁴/384EI', m, 'xy'};
m = base(2); m = addSup(m, 0, 'encastrement', 'A'); m = addSup(m, 2, 'encastrement', 'B'); m = addF(m, 1, 20e3, 0, 0);
B(end+1, :) = {'barre_axiale_bi_encastree', 'F/2 de chaque côté', m, 'xy'};
m = base(4); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 4, 'appui_simple', 'B'); m = addF(m, 1.5, 0, 0, 6e3);
B(end+1, :) = {'plan_xz_force', 'Flexion dans le plan (x,z)', m, 'xz'};
m = base(2); m = addSup(m, 0, 'encastrement', 'A'); m = addC(m, 2, 1e3, 0, 0);
B(end+1, :) = {'torsion_console', 'Couple de torsion en bout', m, 'xy'};
m = base(6); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 6, 'appui_simple', 'B'); m = addQ(m, 0, 6, 'y', [-2000 0]);
B(end+1, :) = {'charge_triangulaire', '0 -> 12 kN/m', m, 'xy'};
m = base(5); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 5, 'appui_simple', 'B'); m = addQ(m, 1, 3, 'y', [-2000 -4000]);
B(end+1, :) = {'trapeze_partiel', 'charge trapèze entre 1 et 3 m (variable locale)', m, 'xy'};
m = base(4); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 4, 'appui_simple', 'B'); m = addC(m, 1.5, 0, 0, 10e3);
B(end+1, :) = {'couple_ponctuel', 'Cz = 10 kN.m en 1,5 m', m, 'xy'};
m = base(8); m = addSup(m, 0, 'appui_simple', 'A'); m = addSup(m, 4, 'appui_simple', 'B'); m = addSup(m, 8, 'appui_simple', 'C');
m = addQ(m, 0, 8, 'y', -10e3); m.hinges = struct('pos', 2, 'name', 'R1');
B(end+1, :) = {'gerber_isostatique', 'rotule en 2 m, R = [10 60 10] kN', m, 'xy'};
m = base(8); m = addSup(m, 0, 'encastrement', 'A'); m = addSup(m, 4, 'appui_simple', 'B'); m = addSup(m, 8, 'appui_simple', 'C');
m = addQ(m, 0, 8, 'y', -10e3); m.hinges = struct('pos', 2, 'name', 'R1');
B(end+1, :) = {'gerber_hyperstatique', 'rotule + encastrement', m, 'xy'};
m = base(8); m = addSup(m, 0, 'pivot', 'A'); m = addSup(m, 4, 'appui_simple', 'B'); m = addSup(m, 8, 'appui_simple', 'C');
m.supports(2).spring = 1e6; m.supports(1).spring = 0; m.supports(3).spring = 0;
m = addQ(m, 0, 8, 'y', -10e3);
B(end+1, :) = {'appui_elastique', 'appui central k = 1e6 N/m', m, 'xy'};
m = base(5); m = addSup(m, 0, 'encastrement', 'A'); m = addSup(m, 5, 'appui_simple', 'B'); m = addQ(m, 0, 5, 'y', -8e3);
m.supports(2).dy = -0.01; m.supports(1).dy = 0;
B(end+1, :) = {'tassement_appui', 'tassement de B : -10 mm', m, 'xy'};
m = base(6); m = addSup(m, 0, 'encastrement', 'A'); m = addSup(m, 6, 'encastrement', 'B');
m.thermal = struct('epsX', 12e-6 * 30, 'kv', 1e-3, 'kw', 0);
B(end+1, :) = {'thermique_bi_encastree', 'dilatation + courbure thermique', m, 'xy'};
m = struct('L', 4, 'E', 190e9, 'G', 73.0769e9, 'S', pIPE.S, 'Iz', pIPE.Iz, 'Iy', pIPE.Iy, ...
    'Ix', GeometryEngine.analytical(GeometryEngine.fromProfile(pIPE)).J, 'ky', 1, 'kz', 1);
m.supports = struct('pos', {0, 4}, 'type', {'pivot', 'appui_simple'}, 'name', {'A', 'B'});
m.pointLoads = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
m.pointMoments = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
m.distLoads = struct('a', 0, 'b', 4, 'dir', 'y', 'coeffs', -10e3, 'name', 'q1');
B(end+1, :) = {'readme_IPE200', 'Cas du README : Mmax = 20 kN.m, f = 9,029 mm', m, 'xy'};
end

function m = base(L)
m = struct('L', L, 'E', 210e9, 'G', 80e9, 'S', 2e-3, 'Iz', 8e-6, 'Iy', 3e-6, 'Ix', 1e-6, 'ky', 1, 'kz', 1);
m.supports = struct('pos', {}, 'type', {}, 'name', {});
m.pointLoads = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
m.pointMoments = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
m.distLoads = struct('a', {}, 'b', {}, 'dir', {}, 'coeffs', {}, 'name', {});
end

function m = addSup(m, pos, type, name)
m.supports(end+1).pos = pos;
m.supports(end).type = type;
m.supports(end).name = name;
end

function m = addF(m, pos, Fx, Fy, Fz)
m.pointLoads(end+1) = struct('pos', pos, 'Fx', Fx, 'Fy', Fy, 'Fz', Fz, 'name', sprintf('F%d', numel(m.pointLoads) + 1));
end

function m = addC(m, pos, Mx, My, Mz)
m.pointMoments(end+1) = struct('pos', pos, 'Mx', Mx, 'My', My, 'Mz', Mz, 'name', sprintf('C%d', numel(m.pointMoments) + 1));
end

function m = addQ(m, a, b, dir, coeffs)
m.distLoads(end+1) = struct('a', a, 'b', b, 'dir', dir, 'coeffs', coeffs, 'name', sprintf('q%d', numel(m.distLoads) + 1));
end

function out = ktRows(id, prm)
% evalKt ligne par ligne (pour éviter toute ambiguïté de vectorisation).
out = zeros(size(prm, 1), 1);
for k = 1:size(prm, 1)
    out(k) = DataManager.evalKt(id, prm(k, :));
end
end

function out = bearingPair(dm, li, co)
[pmin, pmax] = dm.getBearingPressure(li, co);
out = struct('pmin', pmin, 'pmax', pmax);
end

function v = pickField(s, names, def)
v = def;
for k = 1:numel(names)
    if isfield(s, names{k})
        v = s.(names{k});
        return
    end
end
end

function c = runCase(id, desc, fname, inputs, fh)
% Exécute fh() et range entrées + sortie (ou erreur) dans une structure prête pour JSON.
c = struct('id', id, 'description', desc, 'fonction', fname);
c.entrees = sanitize(inputs, 0);
c.sortie = [];
c.erreur = '';
try
    c.sortie = sanitize(fh(), 0);
catch err
    c.erreur = [err.identifier ' | ' err.message];
    fprintf('  [erreur MATLAB] %s : %s\n', id, err.message);
end
end

function out = sanitize(x, depth)
% Convertit une valeur MATLAB en valeur encodable en JSON (voir l'en-tête du script).
skip = {'report', 'latex', 'derivation', 'equations', 'integrals', 'internalIntegral', ...
    'sigmaFun', 'modeShape', 'fun', 'model'};
if depth > 9
    out = '<profondeur maximale>';
    return
end
if isa(x, 'function_handle')
    out = '<fonction>';
elseif isa(x, 'sym')
    try
        out = double(x);
    catch
        out = char(string(x));
    end
elseif istable(x)
    out = sanitize(table2struct(x), depth + 1);
    if isstruct(out)
        out = {out};
    end
elseif isstruct(x)
    if isscalar(x) && isfield(x, 'breaks') && isfield(x, 'coefs')
        out = ppToJson(x);
    elseif isempty(x)
        out = {};
    else
        f = fieldnames(x);
        f = f(~ismember(f, skip));
        cells = cell(numel(x), 1);
        for k = 1:numel(x)
            s = struct();
            for j = 1:numel(f)
                s.(f{j}) = sanitize(x(k).(f{j}), depth + 1);
            end
            cells{k} = s;
        end
        if isscalar(x)
            out = cells{1};
        else
            out = cells;
        end
    end
elseif iscell(x)
    if isempty(x)
        out = {};
    elseif isvector(x)
        out = cell(1, numel(x));
        for k = 1:numel(x)
            out{k} = sanitize(x{k}, depth + 1);
        end
    else
        out = cell(1, size(x, 1));
        for r = 1:size(x, 1)
            out{r} = sanitize(x(r, :), depth + 1);
        end
    end
elseif isstring(x)
    if isscalar(x)
        out = char(x);
    else
        out = cellstr(x(:)');
    end
elseif iscategorical(x)
    out = cellstr(string(x(:)'));
elseif isnumeric(x) || islogical(x)
    if numel(x) > 6000
        out = sprintf('<tableau %s non exporté>', mat2str(size(x)));
    elseif isnumeric(x) && ~isreal(x)
        out = struct('re', real(double(x)), 'im', imag(double(x)));
    else
        out = x;
        if isnumeric(x)
            out = double(x);
        end
    end
elseif ischar(x)
    out = x;
elseif isobject(x)
    out = ['<objet ' class(x) '>'];
else
    out = ['<' class(x) '>'];
end
end

function out = ppToJson(pp)
% Polynôme par morceaux : points de rupture, coefficients et 41 valeurs régulièrement espacées.
s = linspace(pp.breaks(1), pp.breaks(end), 41);
try
    v = BeamAndTrussSolver.ppEval(pp, s);
catch
    v = NaN(size(s));
end
cf = pp.coefs;
if ~iscell(cf)
    cf = num2cell(cf, 2)';
end
out = struct('breaks', double(pp.breaks), 'coefs', {cellfun(@double, cf, 'UniformOutput', false)}, ...
    's', s, 'valeurs', v);
end

function writeCases(file, C)
% Encode chaque cas séparément (un cas non encodable n'empêche pas les autres).
parts = cell(1, numel(C));
for k = 1:numel(C)
    try
        parts{k} = jsonencode(C{k}, 'PrettyPrint', true, 'ConvertInfAndNaN', false);
    catch err
        e = struct('id', C{k}.id, 'description', C{k}.description, 'fonction', C{k}.fonction, ...
            'entrees', [], 'sortie', [], 'erreur', ['export JSON impossible | ' err.message]);
        parts{k} = jsonencode(e, 'PrettyPrint', true);
        fprintf('  [export] %s non encodable : %s\n', C{k}.id, err.message);
    end
end
txt = ['[' newline strjoin(parts, [',' newline]) newline ']'];
fid = fopen(file, 'w', 'n', 'UTF-8');
if fid < 0
    error('Impossible d''écrire %s', file);
end
fprintf(fid, '%s', txt);
fclose(fid);
fprintf('  %s : %d cas\n', file, numel(C));
end
