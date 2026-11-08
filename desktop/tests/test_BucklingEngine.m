function tests = test_BucklingEngine
%TEST_BUCKLINGENGINE Tests unitaires du module BucklingEngine (flambage).
%   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
%   Cas couverts (§9 d'ARCHITECTURE.md + cas supplémentaires) :
%     - régime d'Euler (λ grand) avec valeur calculée à la main ;
%     - régime de Rankine, régime de compression simple, frontières de l'arbre de décision ;
%     - cohérence 1/PR = 1/PE + 1/PC ; σE = PE/S ;
%     - coefficients de longueur de flambage L' ; choix de l'axe de plus faible inertie ;
%     - modes propres (conditions aux limites, équation différentielle, normalisation) ;
%     - équation caractéristique (symbolique et repli numérique) ;
%     - courbe de stabilité ; vérification d'un effort P ; rapport et LaTeX ; erreurs attendues.
%
%   Lancement : r = runtests('tests/test_BucklingEngine.m');
tests = functiontests(localfunctions);
end

% =====================================================================
%  Données de référence
% =====================================================================

function p = baseParams(condition)
% Section rectangulaire fictive : S = 1e-3 m², Iz = 2e-6 m⁴, Iy = 5e-7 m⁴ (rmin = √5e-4 m)
p = struct('E', 210e9, 'Re', 235e6, 'S', 1e-3, 'Iz', 2e-6, 'Iy', 5e-7, 'L', 3, ...
    'condition', condition, 's', 1);
end

function conds = allConditions()
conds = {'encastre-libre', 'articule-articule', 'encastre-articule', 'encastre-encastre'};
end

% =====================================================================
%  Régimes
% =====================================================================

function testEulerHandCalculation(tc)
% Barre ronde pleine D = 20 mm, L = 2 m, articulée-articulée, acier E = 210 GPa, Re = 235 MPa.
% À la main : S = πD²/4, I = πD⁴/64, r = D/4 = 5 mm, λ = L/r = 400 > λlim = π√(E/Re) ≈ 93,91
%   ⇒ Euler : PE = π² E I / L² = π³ E D⁴/(64 L²) ≈ 4069,57 N ; σE = π² E/λ² ≈ 12,954 MPa.
D = 0.02; L = 2; E = 210e9; Re = 235e6;
S = pi*D^2/4; I = pi*D^4/64;
p = struct('E', E, 'Re', Re, 'S', S, 'Iz', I, 'Iy', I, 'L', L, 'condition', 'articule-articule');
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.regime, 'euler');
tc.verifyEqual(r.rmin, D/4, 'RelTol', 1e-12);
tc.verifyEqual(r.Lp, L, 'RelTol', 1e-15);
tc.verifyEqual(r.lambda, 400, 'RelTol', 1e-12);
tc.verifyEqual(r.lambdaLim, pi*sqrt(E/Re), 'RelTol', 1e-14);
tc.verifyEqual(r.lambdaLim, 93.913, 'RelTol', 1e-5);
PEhand = pi^3*E*D^4/(64*L^2);
tc.verifyEqual(r.PE, PEhand, 'RelTol', 1e-12);
tc.verifyEqual(r.PE, 4069.5738, 'RelTol', 1e-6);          % valeur numérique à la main
tc.verifyEqual(r.sigmaE, pi^2*E/400^2, 'RelTol', 1e-12);
tc.verifyEqual(r.sigmaE, 12.95386e6, 'RelTol', 1e-6);
tc.verifyEqual(r.sigmaE*S, r.PE, 'RelTol', 1e-12);          % σE = PE/S
tc.verifyEqual(r.Pcrit, r.PE, 'RelTol', 0);
tc.verifyEqual(r.Padm, r.PE, 'RelTol', 1e-15);              % s = 1 par défaut
tc.verifyEqual(r.s, 1);
tc.verifyEqual(r.PC, Re*S, 'RelTol', 1e-15);
tc.verifyLessThan(r.PE, r.PC);
tc.verifyEqual(r.sigmaCrit, r.Pcrit/S, 'RelTol', 1e-15);
tc.verifyEmpty(r.ok);                                      % P non fourni
tc.verifyTrue(isnan(r.sigmaApplied));
end

function testEulerIPE200(tc)
% IPE 200 (catalogue) : S = 28,48 cm², Iz(app) = 1943 cm⁴ (axe fort), Iy(app) = 142,4 cm⁴,
% L = 5 m articulée : flambage autour de l'axe faible (G, y).
p = struct('E', 210e9, 'Re', 235e6, 'S', 28.48e-4, 'Iz', 1943e-8, 'Iy', 142.4e-8, 'L', 5, ...
    'condition', 'articule-articule', 's', 3);
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.axis, 'y');
tc.verifyEqual(r.Imin, 142.4e-8);
tc.verifyEqual(r.Imax, 1943e-8);
tc.verifyEqual(r.rmin, sqrt(142.4e-8/28.48e-4), 'RelTol', 1e-14);
tc.verifyEqual(r.lambda, 5/sqrt(142.4e-8/28.48e-4), 'RelTol', 1e-12);
tc.verifyEqual(r.regime, 'euler');
PE = pi^2*210e9*142.4e-8/5^2;
tc.verifyEqual(r.PE, PE, 'RelTol', 1e-12);
tc.verifyEqual(r.PE, 118056.26, 'RelTol', 1e-6);
tc.verifyEqual(r.Padm, PE/3, 'RelTol', 1e-12);
end

function testRankineCase(tc)
% Encastrée-encastrée L = 3 m : L' = 1,5 m, λ = 1,5/√5e-4 ≈ 67,08 ∈ [20 ; 93,91[ ⇒ Rankine.
p = baseParams('encastre-encastre');
p.s = 2;
r = BucklingEngine.analyze(p);
lam = 1.5/sqrt(5e-4);
lamLim = pi*sqrt(210e9/235e6);
PR = 235e6*1e-3/(1 + (lam/lamLim)^2);
tc.verifyEqual(r.regime, 'rankine');
tc.verifyEqual(r.Lp, 1.5, 'RelTol', 1e-15);
tc.verifyEqual(r.lambda, lam, 'RelTol', 1e-12);
tc.verifyEqual(r.PR, PR, 'RelTol', 1e-12);
tc.verifyEqual(r.PR, 155606, 'RelTol', 1e-5);               % valeur à la main
tc.verifyEqual(r.Pcrit, r.PR, 'RelTol', 0);
tc.verifyEqual(r.Padm, PR/2, 'RelTol', 1e-12);
tc.verifyEqual(r.sigmaAdm, PR/2/1e-3, 'RelTol', 1e-12);
tc.verifyEqual(r.PE, pi^2*210e9*5e-7/1.5^2, 'RelTol', 1e-12);
tc.verifyEqual(r.PC, 235e3, 'RelTol', 1e-15);
% Dans la zone de Rankine : PR < PC et σE > Re (Euler serait non conservatif)
tc.verifyLessThan(r.PR, r.PC);
tc.verifyGreaterThan(r.sigmaE, 235e6);
end

function testCompressionCase(tc)
% Poutre courte articulée L = 0,2 m : λ = 0,2/0,02236 ≈ 8,94 < 20 ⇒ compression simple PC = Re S.
p = baseParams('articule-articule');
p.L = 0.2;
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.regime, 'compression');
tc.verifyEqual(r.lambda, 0.2/sqrt(5e-4), 'RelTol', 1e-12);
tc.verifyLessThan(r.lambda, 20);
tc.verifyEqual(r.Pcrit, 235e6*1e-3, 'RelTol', 1e-15);
tc.verifyEqual(r.Pcrit, r.PC, 'RelTol', 0);
tc.verifyEqual(r.sigmaCrit, 235e6, 'RelTol', 1e-15);
tc.verifyGreaterThan(r.sigmaE, r.Re);
% Les trois modèles sont tout de même calculés
tc.verifyEqual(r.PE, pi^2*210e9*5e-7/0.2^2, 'RelTol', 1e-12);
tc.verifyEqual(r.PR, r.PC/(1 + (r.lambda/r.lambdaLim)^2), 'RelTol', 1e-12);
end

function testDecisionBoundaries(tc)
% Frontières : λ = λC → Rankine (inégalité large) ; λ juste sous λC → compression ;
% λ = λlim(1 ± 1e-9) → Euler / Rankine.
p = baseParams('articule-articule');
p.L = 1.5;                                   % λ ≈ 67,08 : zone de Rankine
r0 = BucklingEngine.analyze(p);
tc.verifyEqual(r0.regime, 'rankine');
q = p; q.lambdaCompression = r0.lambda;
r1 = BucklingEngine.analyze(q);
tc.verifyEqual(r1.regime, 'rankine');
tc.verifyEqual(r1.lambdaCompression, r0.lambda);
q.lambdaCompression = r0.lambda*(1 + 1e-12);
r2 = BucklingEngine.analyze(q);
tc.verifyEqual(r2.regime, 'compression');
% Frontière d'Euler : L tel que λ = λlim (1 ± 1e-9)
lamLim = r0.lambdaLim;
q = p;
q.L = lamLim*(1 + 1e-9)*r0.rmin;
tc.verifyEqual(BucklingEngine.analyze(q).regime, 'euler');
q.L = lamLim*(1 - 1e-9)*r0.rmin;
r3 = BucklingEngine.analyze(q);
tc.verifyEqual(r3.regime, 'rankine');
% À λ = λlim : PE = PC et PR = PC/2 (discontinuité de la courbe du cours)
tc.verifyEqual(r3.PE, r3.PC, 'RelTol', 1e-8);
tc.verifyEqual(r3.PR, r3.PC/2, 'RelTol', 1e-8);
% Seuil par défaut
tc.verifyEqual(r0.lambdaCompression, 20);
end

function testLambdaLimBelowCompressionLimit(tc)
% Matériau peu rigide : E/Re = 30 ⇒ λlim = π√30 ≈ 17,2 < 20 ; pour λ = 18, Euler est retenu
% (σE ≤ Re, choix sécuritaire), la zone de Rankine est vide.
E = 3e9; Re = 100e6;
p = struct('E', E, 'Re', Re, 'S', 1e-4, 'Iz', 1e-8, 'Iy', 1e-8, 'L', 18*1e-2, ...
    'condition', 'articule-articule');
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.lambdaLim, pi*sqrt(30), 'RelTol', 1e-14);
tc.verifyEqual(r.lambda, 18, 'RelTol', 1e-12);
tc.verifyEqual(r.regime, 'euler');
tc.verifyLessThanOrEqual(r.sigmaE, Re);
tc.verifyTrue(any(contains(r.report, 'Cas particulier')));
% Courbe correspondante : pas de zone de Rankine
c = BucklingEngine.stabilityCurve(E, Re);
tc.verifyFalse(any(c.zone == 2));
tc.verifyTrue(all(c.zone(c.lambda >= c.lambdaLim) == 3));
end

function testRankineIdentity(tc)
% 1/PR = 1/PE + 1/PC quel que soit le cas (λ de 2 à 1000, 4 conditions)
conds = allConditions();
Ls = [0.05 0.3 1 2.5 6 15];
for i = 1:numel(conds)
    for j = 1:numel(Ls)
        p = baseParams(conds{i});
        p.L = Ls(j);
        r = BucklingEngine.analyze(p);
        tc.verifyEqual(1/r.PR, 1/r.PE + 1/r.PC, 'RelTol', 1e-12, ...
            sprintf('1/PR ≠ 1/PE + 1/PC (%s, L = %g)', conds{i}, Ls(j)));
        tc.verifyLessThan(r.PR, min(r.PE, r.PC));
        tc.verifyEqual(r.PE, r.sigmaE*r.S, 'RelTol', 1e-12);
        tc.verifyEqual(r.PE, r.PC*(r.lambdaLim/r.lambda)^2, 'RelTol', 1e-12);
        % Charge critique retenue cohérente avec l'arbre de décision
        if r.lambda >= r.lambdaLim
            tc.verifyEqual(r.regime, 'euler');
            tc.verifyEqual(r.Pcrit, r.PE);
        elseif r.lambda < 20
            tc.verifyEqual(r.regime, 'compression');
            tc.verifyEqual(r.Pcrit, r.PC);
        else
            tc.verifyEqual(r.regime, 'rankine');
            tc.verifyEqual(r.Pcrit, r.PR);
        end
    end
end
end

% =====================================================================
%  Longueur de flambage et plan de flambage
% =====================================================================

function testEffectiveLengthCoefficients(tc)
expected = [2, 1, 1/sqrt(2), 0.5];
conds = allConditions();
for i = 1:numel(conds)
    tc.verifyEqual(BucklingEngine.effectiveLengthCoefficient(conds{i}), expected(i), 'RelTol', 1e-15);
    p = baseParams(conds{i});
    p.L = 2.7;
    r = BucklingEngine.analyze(p);
    tc.verifyEqual(r.coefLp, expected(i), 'RelTol', 1e-15);
    tc.verifyEqual(r.Lp, expected(i)*2.7, 'RelTol', 1e-15);
    tc.verifyEqual(r.lambda, expected(i)*2.7/sqrt(5e-4), 'RelTol', 1e-12);
    tc.verifyEqual(r.PE, pi^2*210e9*5e-7/(expected(i)*2.7)^2, 'RelTol', 1e-12);
    tc.verifyEqual(r.condition, conds{i});
end
% Rapports de charges critiques d'Euler : 1/4, 1, 2, 4 fois le cas articulé
p = baseParams('articule-articule'); p.L = 10;
PEref = BucklingEngine.analyze(p).PE;
ratios = [0.25, 1, 2, 4];
for i = 1:numel(conds)
    p.condition = conds{i};
    tc.verifyEqual(BucklingEngine.analyze(p).PE/PEref, ratios(i), 'RelTol', 1e-12);
end
% Table des conditions
T = BucklingEngine.listConditions();
tc.verifyClass(T, 'table');
tc.verifyEqual(height(T), 4);
tc.verifyEqual(cellstr(T.Condition), conds(:));
tc.verifyEqual(T.Coefficient, expected(:), 'RelTol', 1e-15);
end

function testConditionAliases(tc)
p = baseParams('Encastré-Libre');
tc.verifyEqual(BucklingEngine.analyze(p).condition, 'encastre-libre');
p.condition = "articule_articule";
tc.verifyEqual(BucklingEngine.analyze(p).condition, 'articule-articule');
p.condition = 'Encastré articulé';
tc.verifyEqual(BucklingEngine.analyze(p).condition, 'encastre-articule');
p.condition = 'bi-encastre';
tc.verifyEqual(BucklingEngine.analyze(p).condition, 'encastre-encastre');
tc.verifyEqual(BucklingEngine.effectiveLengthCoefficient('ENCASTRE-ENCASTRE'), 0.5);
end

function testWeakAxisChoice(tc)
% Iy < Iz : flambage autour de (G, y) (plan (x, z))
p = baseParams('articule-articule');
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.axis, 'y');
tc.verifyEqual(r.Imin, 5e-7);
tc.verifyEqual(r.Imax, 2e-6);
tc.verifyTrue(contains(r.planeText, '(x, z)'));
tc.verifyEqual(r.rmin, sqrt(5e-7/1e-3), 'RelTol', 1e-15);
% Iz < Iy : flambage autour de (G, z) (plan (x, y))
p.Iz = 3e-7; p.Iy = 8e-7;
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.axis, 'z');
tc.verifyEqual(r.Imin, 3e-7);
tc.verifyEqual(r.Imax, 8e-7);
tc.verifyTrue(contains(r.planeText, '(x, y)'));
tc.verifyEqual(r.PE, pi^2*210e9*3e-7/3^2, 'RelTol', 1e-12);
% Iz = Iy (section circulaire) : convention axe z, Imin = Imax
p.Iz = 4e-7; p.Iy = 4e-7;
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.axis, 'z');
tc.verifyEqual(r.Imin, r.Imax);
tc.verifyTrue(contains(r.planeText, 'équivalentes'));
end

% =====================================================================
%  Vérification d'un effort appliqué et coefficient de sécurité
% =====================================================================

function testAppliedLoadCheck(tc)
p = baseParams('articule-articule');     % Euler, PE ≈ 115 145 N
p.s = 2;
r = BucklingEngine.analyze(p);
Padm = r.PE/2;
p.P = 0.9*Padm;
r = BucklingEngine.analyze(p);
tc.verifyTrue(r.ok);
tc.verifyClass(r.ok, 'logical');
tc.verifyEqual(r.P, 0.9*Padm);
tc.verifyEqual(r.sigmaApplied, 0.9*Padm/1e-3, 'RelTol', 1e-15);
tc.verifyEqual(r.safetyObtained, r.Pcrit/(0.9*Padm), 'RelTol', 1e-14);
tc.verifyEqual(r.utilization, 0.9, 'RelTol', 1e-12);
tc.verifyTrue(any(contains(r.report, 'VÉRIFIÉ')));
p.P = 1.1*Padm;
r = BucklingEngine.analyze(p);
tc.verifyFalse(r.ok);
tc.verifyTrue(any(contains(r.report, 'NON VÉRIFIÉ')));
% Effort négatif (convention N < 0 en compression) : |P| retenu
p.P = -0.5*Padm;
r = BucklingEngine.analyze(p);
tc.verifyTrue(r.ok);
tc.verifyEqual(r.P, 0.5*Padm, 'RelTol', 1e-15);
tc.verifyTrue(any(contains(r.report, '|P| retenu')));
% Égalité : P = Padm vérifié
p.P = Padm;
tc.verifyTrue(BucklingEngine.analyze(p).ok);
% NaN ou vide : absent
p.P = NaN;
r = BucklingEngine.analyze(p);
tc.verifyEmpty(r.ok);
tc.verifyTrue(isnan(r.P));
p.P = [];
tc.verifyEmpty(BucklingEngine.analyze(p).ok);
% P = 0 : sécurité infinie
p.P = 0;
r = BucklingEngine.analyze(p);
tc.verifyTrue(r.ok);
tc.verifyEqual(r.safetyObtained, Inf);
end

function testSafetyFactor(tc)
conds = allConditions();
for i = 1:numel(conds)
    p = baseParams(conds{i});
    r1 = BucklingEngine.analyze(p);
    p.s = 2.5;
    r2 = BucklingEngine.analyze(p);
    tc.verifyEqual(r2.Pcrit, r1.Pcrit);
    tc.verifyEqual(r2.Padm, r1.Pcrit/2.5, 'RelTol', 1e-15);
    tc.verifyEqual(r2.s, 2.5);
end
end

% =====================================================================
%  Modes propres
% =====================================================================

function testModeShapesMatchContract(tc)
L = 2.4;
s = linspace(0, L, 2001);
kLca = fzero(@(x) tan(x) - x, [4.4, 4.6]);
expected = {
    @(x) 1 - cos(pi*x/(2*L))                                  % encastré-libre
    @(x) sin(pi*x/L)                                          % articulé-articulé
    @(x) sin(kLca*x/L) - kLca*x/L + kLca*(1 - cos(kLca*x/L))  % encastré-articulé (non normalisé)
    @(x) (1 - cos(2*pi*x/L))/2};                              % encastré-encastré
conds = allConditions();
for i = 1:numel(conds)
    p = baseParams(conds{i});
    p.L = L;
    r = BucklingEngine.analyze(p);
    v = r.modeShape(s);
    tc.verifySize(v, size(s));                                % vectorisé
    ve = expected{i}(s);
    if i == 3
        [~, im] = max(ve);
        sm = fminbnd(@(x) -expected{3}(x), s(max(im-1, 1)), s(min(im+1, numel(s))), ...
            optimset('TolX', 1e-14));
        ve = ve/expected{3}(sm);
        tc.verifyEqual(r.modeSMax, sm, 'RelTol', 1e-6);
        tc.verifyEqual(r.modeK*L, 4.493409457909064, 'RelTol', 1e-12);
    end
    tc.verifyEqual(v, ve, 'AbsTol', 1e-9, sprintf('Mode %s différent du contrat', conds{i}));
    % Normalisation : max = 1, atteint en modeSMax
    tc.verifyEqual(max(v), 1, 'AbsTol', 1e-5);               % maximum hors grille possible
    tc.verifyLessThanOrEqual(max(v), 1 + 1e-12);
    tc.verifyEqual(r.modeShape(r.modeSMax), 1, 'AbsTol', 1e-12);
    tc.verifyGreaterThanOrEqual(min(v), -1e-12);
end
end

function testModeBoundaryConditionsAndODE(tc)
% Contrôle indépendant (différences finies sur modeShape) des conditions aux limites et de
% l'équation v'''' + k² v'' = 0, plus le contrôle interne modeCheck.
L = 3;
conds = allConditions();
for i = 1:numel(conds)
    p = baseParams(conds{i});
    r = BucklingEngine.analyze(p);
    v = r.modeShape;
    k = r.modeK;
    h = 1e-5*L;
    % Dérivées par différences finies décentrées aux extrémités (ordre 2)
    d1_0 = (-3*v(0) + 4*v(h) - v(2*h))/(2*h);
    d1_L = (3*v(L) - 4*v(L - h) + v(L - 2*h))/(2*h);
    tc.verifyEqual(v(0), 0, 'AbsTol', 1e-12);
    switch conds{i}
        case 'encastre-libre'
            tc.verifyEqual(d1_0/k, 0, 'AbsTol', 1e-8);
            tc.verifyEqual(r.modeDerivatives.d2(L)/k^2, 0, 'AbsTol', 1e-12);       % moment nul
            tc.verifyEqual((r.modeDerivatives.d3(L) + k^2*r.modeDerivatives.d1(L))/k^3, 0, ...
                'AbsTol', 1e-12);                                                  % tranchant nul
            tc.verifyEqual(k*L, pi/2, 'RelTol', 1e-14);
        case 'articule-articule'
            tc.verifyEqual(v(L), 0, 'AbsTol', 1e-12);
            tc.verifyEqual(r.modeDerivatives.d2(0)/k^2, 0, 'AbsTol', 1e-12);
            tc.verifyEqual(r.modeDerivatives.d2(L)/k^2, 0, 'AbsTol', 1e-12);
            tc.verifyEqual(k*L, pi, 'RelTol', 1e-14);
        case 'encastre-articule'
            tc.verifyEqual(d1_0/k, 0, 'AbsTol', 1e-8);
            tc.verifyEqual(v(L), 0, 'AbsTol', 1e-12);
            tc.verifyEqual(r.modeDerivatives.d2(L)/k^2, 0, 'AbsTol', 1e-12);
        case 'encastre-encastre'
            tc.verifyEqual(d1_0/k, 0, 'AbsTol', 1e-8);
            tc.verifyEqual(v(L), 0, 'AbsTol', 1e-12);
            tc.verifyEqual(d1_L/k, 0, 'AbsTol', 1e-8);
            tc.verifyEqual(k*L, 2*pi, 'RelTol', 1e-14);
    end
    % Équation différentielle par différences finies : v'''' + k² v'' = 0 (points intérieurs)
    hh = 3e-3*L;
    si = linspace(0.1*L, 0.9*L, 41);
    d2 = (v(si + hh) - 2*v(si) + v(si - hh))/hh^2;
    d4 = (v(si + 2*hh) - 4*v(si + hh) + 6*v(si) - 4*v(si - hh) + v(si - 2*hh))/hh^4;
    tc.verifyLessThan(max(abs(d4 + k^2*d2))/k^4, 1e-3, ...
        sprintf('Équation différentielle non vérifiée (%s)', conds{i}));
    % Cohérence des dérivées analytiques avec les différences finies
    tc.verifyEqual(r.modeDerivatives.d2(si), d2, 'AbsTol', 1e-4*k^2);
    % Contrôle interne
    mc = r.modeCheck;
    tc.verifyTrue(mc.ok, sprintf('modeCheck non conforme (%s)', conds{i}));
    tc.verifyLessThan(max(abs(mc.bcResiduals)), 1e-12);
    tc.verifyLessThan(mc.odeResidual, 1e-12);
    tc.verifyNumElements(mc.bcLabels, 4);
end
end

% =====================================================================
%  Équation caractéristique et dérivation
% =====================================================================

function testCharacteristicEquationNumeric(tc)
kLref = [pi/2, pi, 4.493409457909064, 2*pi];
conds = allConditions();
for i = 1:numel(conds)
    p = baseParams(conds{i});
    p.useSymbolic = false;
    r = BucklingEngine.analyze(p);
    tc.verifyEqual(r.methodUsed, 'numérique');
    ce = r.charEquation;
    tc.verifyEqual(ce.kL, kLref(i), 'RelTol', 1e-12);
    tc.verifyEqual(ce.kLNumeric, kLref(i), 'RelTol', 1e-12);
    tc.verifyTrue(ce.verified);
    tc.verifyEqual(ce.coefLpExact, pi/kLref(i), 'RelTol', 1e-12);
    tc.verifyEqual(ce.PEexact, kLref(i)^2*210e9*5e-7/3^2, 'RelTol', 1e-12);
    tc.verifyTrue(iscell(r.derivation) && iscolumn(r.derivation));
    tc.verifyGreaterThanOrEqual(numel(r.derivation), 8);
    tc.verifyTrue(any(contains(r.derivation, 'k^2')));
end
% Encastré-articulé : le L' = L/√2 du cours est légèrement sécuritaire (PE cours < PE exact)
p = baseParams('encastre-articule'); p.useSymbolic = false;
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.charEquation.coefLpExact, 0.6991556596, 'RelTol', 1e-8);
tc.verifyLessThan(r.PE, r.charEquation.PEexact);
tc.verifyEqual(r.charEquation.PEexact/r.PE, 4.493409457909064^2/(2*pi^2), 'RelTol', 1e-12);
% Articulé : l'équation caractéristique sin(kL) = 0 apparaît dans la dérivation
p = baseParams('articule-articule'); p.useSymbolic = false;
r = BucklingEngine.analyze(p);
tc.verifyEqual(r.charEquation.text, 'sin(kL) = 0');
tc.verifyTrue(any(contains(r.derivation, '\sin(k\,L) = 0')));
tc.verifyTrue(any(contains(r.derivation, 'v''''(s) + k^2\,v(s) = 0')));
end

function testCharacteristicEquationSymbolic(tc)
tc.assumeTrue(BucklingEngine.hasSymbolic(), 'Symbolic Math Toolbox indisponible');
kLref = [pi/2, pi, 4.493409457909064, 2*pi];
conds = allConditions();
for i = 1:numel(conds)
    p = baseParams(conds{i});
    p.useSymbolic = true;
    r = BucklingEngine.analyze(p);
    tc.verifyEqual(r.methodUsed, 'symbolique');
    ce = r.charEquation;
    sy = ce.symbolic;
    tc.verifyTrue(sy.ok);
    tc.verifyTrue(sy.dsolveVerified, 'dsolve : sin(kL) = 0 non retrouvé');
    tc.verifyEqual(ce.kL, kLref(i), 'RelTol', 1e-12);
    tc.verifyTrue(ce.verified);
    tc.verifyTrue(contains(sy.charEquation, 'sin'));
    tc.verifyTrue(contains(sy.P1, 'pi^2'));
    tc.verifyTrue(any(contains(r.derivation, 'dsolve')));
    tc.verifyTrue(any(contains(r.report, 'dsolve')));
end
% Vérification indépendante du P1 symbolique : π² E I / L²
p = baseParams('articule-articule');
r = BucklingEngine.analyze(p);
P1 = str2sym(r.charEquation.symbolic.P1);
val = double(subs(P1, [sym('E'), sym('Imin'), sym('L')], [210e9, 5e-7, 3]));
tc.verifyEqual(val, r.PE, 'RelTol', 1e-12);
end

% =====================================================================
%  Courbe de stabilité
% =====================================================================

function testStabilityCurveDefault(tc)
E = 210e9; Re = 235e6;
c = BucklingEngine.stabilityCurve(E, Re);
lam = 0:0.5:300;
tc.verifyEqual(c.lambda, lam);
tc.verifyEqual(c.lambdaLim, pi*sqrt(E/Re), 'RelTol', 1e-14);
tc.verifyEqual(c.lambdaCompression, 20);
tc.verifySize(c.sigmaEuler, size(lam));
tc.verifySize(c.sigmaRankine, size(lam));
tc.verifySize(c.sigmaPalier, size(lam));
tc.verifySize(c.sigmaDesign, size(lam));
% Euler : NaN en λ = 0 (pas d'Inf), hyperbole ailleurs
tc.verifyTrue(isnan(c.sigmaEuler(1)));
tc.verifyFalse(any(isinf(c.sigmaEuler)));
tc.verifyFalse(any(isinf(c.sigmaDesign)) || any(isnan(c.sigmaDesign)));
tc.verifyEqual(c.sigmaEuler(2:end), pi^2*E./lam(2:end).^2, 'RelTol', 1e-14);
tc.verifyEqual(c.sigmaRankine, Re./(1 + (lam/c.lambdaLim).^2), 'RelTol', 1e-14);
tc.verifyEqual(c.sigmaRankine(1), Re);
tc.verifyEqual(c.sigmaPalier, Re*ones(size(lam)));
% Courbe de dimensionnement (arbre de décision)
iC = lam < 20; iE = lam >= c.lambdaLim; iR = ~iC & ~iE;
tc.verifyEqual(c.sigmaDesign(iC), Re*ones(1, nnz(iC)));
tc.verifyEqual(c.sigmaDesign(iR), c.sigmaRankine(iR));
tc.verifyEqual(c.sigmaDesign(iE), c.sigmaEuler(iE));
tc.verifyEqual(c.zone(iC), ones(1, nnz(iC)));
tc.verifyEqual(c.zone(iR), 2*ones(1, nnz(iR)));
tc.verifyEqual(c.zone(iE), 3*ones(1, nnz(iE)));
tc.verifyTrue(all(c.sigmaDesign <= Re));
% Points remarquables : σE(λlim) = Re, σR(λlim) = Re/2
cL = BucklingEngine.stabilityCurve(E, Re, [c.lambdaLim, 20]);
tc.verifyEqual(cL.sigmaEuler(1), Re, 'RelTol', 1e-12);
tc.verifyEqual(cL.sigmaRankine(1), Re/2, 'RelTol', 1e-12);
tc.verifyEqual(cL.sigmaDesign(1), Re, 'RelTol', 1e-12);       % λ = λlim : Euler
tc.verifyEqual(cL.sigmaDesign(2), Re/(1 + (20/c.lambdaLim)^2), 'RelTol', 1e-12);   % λ = 20 : Rankine
% Rapport et LaTeX
tc.verifyTrue(iscell(c.report) && iscolumn(c.report) && all(cellfun(@ischar, c.report)));
tc.verifyTrue(iscell(c.latex) && all(cellfun(@ischar, c.latex)));
end

function testStabilityCurveCustomAndConsistency(tc)
% λ en colonne → sortie en ligne ; λC personnalisé ; cohérence avec analyze
c = BucklingEngine.stabilityCurve(70e9, 200e6, (0:10:200).', 10);
tc.verifyEqual(c.lambda, 0:10:200);
tc.verifyEqual(c.lambdaCompression, 10);
tc.verifyEqual(c.sigmaDesign(c.lambda < 10), 200e6*ones(1, 1));
conds = allConditions();
Ls = [0.2 1 3 8];
for i = 1:numel(conds)
    for j = 1:numel(Ls)
        p = baseParams(conds{i});
        p.L = Ls(j);
        r = BucklingEngine.analyze(p);
        cc = BucklingEngine.stabilityCurve(p.E, p.Re, r.lambda);
        tc.verifyEqual(cc.sigmaDesign, r.Pcrit/r.S, 'RelTol', 1e-12, ...
            sprintf('Courbe ≠ analyse (%s, L = %g)', conds{i}, Ls(j)));
        tc.verifyEqual(cc.sigmaEuler, r.sigmaE, 'RelTol', 1e-12);
    end
end
end

% =====================================================================
%  Rapport et LaTeX
% =====================================================================

function testReportContent(tc)
cases = {'articule-articule', 0.2, 'COMPRESSION SIMPLE'; ...
         'encastre-encastre', 3, 'RANKINE'; ...
         'articule-articule', 3, 'EULER'};
for i = 1:size(cases, 1)
    p = baseParams(cases{i, 1});
    p.L = cases{i, 2};
    p.P = 1e4;
    r = BucklingEngine.analyze(p);
    rep = r.report;
    tc.verifyTrue(iscell(rep) && iscolumn(rep) && all(cellfun(@ischar, rep)));
    tc.verifyTrue(any(contains(rep, cases{i, 3})), sprintf('Régime %s non expliqué', cases{i, 3}));
    % Comparaison des trois modèles quel que soit le régime
    tc.verifyTrue(any(contains(rep, 'Comparaison des trois modèles')));
    tc.verifyTrue(any(startsWith(strtrim(rep), 'Compression  PC')));
    tc.verifyTrue(any(startsWith(strtrim(rep), 'Euler        PE')));
    tc.verifyTrue(any(startsWith(strtrim(rep), 'Rankine      PR')));
    tc.verifyTrue(any(contains(rep, '← retenu')));
    tc.verifyTrue(any(contains(rep, 'λlim')));
    tc.verifyTrue(any(contains(rep, 'Padm')));
    tc.verifyTrue(any(contains(rep, 'Mode propre')));
    tc.verifyTrue(ischar(r.planeText) && ~isempty(r.planeText));
    tc.verifyTrue(any(strcmp(r.methodUsed, {'symbolique', 'numérique'})));
end
p = baseParams('encastre-articule');
r = BucklingEngine.analyze(p);
tc.verifyTrue(any(contains(r.report, 'L/√2')));
end

function testLatexStrings(tc)
% Toutes les chaînes LaTeX (analyse, dérivation, courbe) : sous-ensemble autorisé, ASCII,
% < 1000 caractères, rendu sans avertissement.
strs = {};
conds = allConditions();
Ls = [0.2 3 12];
for i = 1:numel(conds)
    for j = 1:numel(Ls)
        p = baseParams(conds{i});
        p.L = Ls(j);
        p.P = 2e4;
        p.useSymbolic = (j == 2);
        r = BucklingEngine.analyze(p);
        tc.verifyTrue(iscell(r.latex) && all(cellfun(@ischar, r.latex)));
        strs = [strs; r.latex(:); r.derivation(:)]; %#ok<AGROW>
    end
end
p = baseParams('articule-articule'); p.P = 1e9; p.s = 3;   % cas non vérifié
r = BucklingEngine.analyze(p);
strs = [strs; r.latex(:)];
p.P = 0;                                                   % sécurité infinie
r = BucklingEngine.analyze(p);
strs = [strs; r.latex(:)];
c = BucklingEngine.stabilityCurve(210e9, 235e6);
strs = [strs; c.latex(:); {BucklingEngine.analyze(p).charEquation.latex}];
verifyLatexValid(tc, strs);
end

function verifyLatexValid(tc, strs)
% Vérifie une liste de chaînes LaTeX MATLAB (restrictions §0.4 du contrat + rendu).
forbidden = {'\iint', '\iiint', '\implies', '\text{', '\dfrac', '\tfrac', '\boldsymbol', ...
    '\geqslant', '\leqslant', 'pmatrix', 'bmatrix', '{align', '{cases'};
f = figure('Visible', 'off');
cleaner = onCleanup(@() close(f));
ax = axes(f);
[w0, id0] = lastwarn;
for i = 1:numel(strs)
    s = strs{i};
    tc.verifyClass(s, 'char');
    tc.verifyTrue(startsWith(s, '$') && endsWith(s, '$'), ['Délimiteurs $ absents : ' s]);
    tc.verifyLessThan(numel(s), 1000);
    tc.verifyTrue(all(double(s) < 128), ['Caractère non ASCII dans : ' s]);
    for j = 1:numel(forbidden)
        tc.verifyFalse(contains(s, forbidden{j}), sprintf('Commande interdite %s dans : %s', forbidden{j}, s));
    end
    lastwarn('');
    h = text(ax, 0.05, 0.5, s, 'Interpreter', 'latex');
    drawnow;
    w = lastwarn;
    tc.verifyEmpty(w, sprintf('Rendu LaTeX en échec pour %s : %s', s, w));
    delete(h);
end
lastwarn(w0, id0);
clear cleaner
end

% =====================================================================
%  Erreurs attendues
% =====================================================================

function testErrors(tc)
p = baseParams('articule-articule');
tc.verifyError(@() BucklingEngine.analyze(rmfield(p, 'Iy')), 'MecaStruct:BucklingEngine:missingField');
tc.verifyError(@() BucklingEngine.analyze(rmfield(p, 'condition')), 'MecaStruct:BucklingEngine:missingField');
tc.verifyError(@() BucklingEngine.analyze(42), 'MecaStruct:BucklingEngine:invalidInput');
tc.verifyError(@() BucklingEngine.analyze([p p]), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.E = -1;
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.S = 0;
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.L = NaN;
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.Iz = 'abc';
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.s = 0;
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.P = Inf;
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.P = [1 2];
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.lambdaCompression = -5;
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:invalidInput');
q = p; q.condition = 'libre-libre';
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:condition');
q = p; q.condition = 3;
tc.verifyError(@() BucklingEngine.analyze(q), 'MecaStruct:BucklingEngine:condition');
tc.verifyError(@() BucklingEngine.effectiveLengthCoefficient('glissiere'), 'MecaStruct:BucklingEngine:condition');
tc.verifyError(@() BucklingEngine.stabilityCurve(210e9), 'MecaStruct:BucklingEngine:invalidInput');
tc.verifyError(@() BucklingEngine.stabilityCurve(210e9, -1), 'MecaStruct:BucklingEngine:invalidInput');
tc.verifyError(@() BucklingEngine.stabilityCurve(210e9, 235e6, [-1 2]), 'MecaStruct:BucklingEngine:invalidInput');
tc.verifyError(@() BucklingEngine.stabilityCurve(210e9, 235e6, [1 Inf]), 'MecaStruct:BucklingEngine:invalidInput');
tc.verifyError(@() BucklingEngine.stabilityCurve(210e9, 235e6, ones(2)), 'MecaStruct:BucklingEngine:invalidInput');
end

function testResultStructureContract(tc)
% Champs exigés par le contrat (§5)
p = baseParams('encastre-libre');
p.P = 1e3;
r = BucklingEngine.analyze(p);
fields = {'Imin', 'Imax', 'axis', 'planeText', 'rmin', 'coefLp', 'Lp', 'lambda', 'lambdaLim', ...
    'regime', 'PC', 'PE', 'PR', 'sigmaE', 'Pcrit', 'Padm', 'ok', 'sigmaApplied', 'modeShape', ...
    'derivation', 'methodUsed', 'report', 'latex'};
for i = 1:numel(fields)
    tc.verifyTrue(isfield(r, fields{i}), ['Champ manquant : ' fields{i}]);
end
tc.verifyTrue(isscalar(r));
tc.verifyClass(r.modeShape, 'function_handle');
tc.verifyTrue(any(strcmp(r.axis, {'y', 'z'})));
tc.verifyTrue(any(strcmp(r.regime, {'compression', 'rankine', 'euler'})));
c = BucklingEngine.stabilityCurve(210e9, 235e6);
cf = {'lambda', 'sigmaEuler', 'sigmaRankine', 'sigmaPalier', 'sigmaDesign', 'lambdaLim', 'lambdaCompression'};
for i = 1:numel(cf)
    tc.verifyTrue(isfield(c, cf{i}), ['Champ manquant (courbe) : ' cf{i}]);
end
end
