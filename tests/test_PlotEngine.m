function tests = test_PlotEngine
%TEST_PLOTENGINE Tests du moteur d'affichage PlotEngine (§7 et §9 du contrat).
%   Chaque fonction est exécutée sur des sorties réelles des moteurs, dans un axes d'une
%   figure invisible ET dans un uiaxes d'une uifigure invisible ; on vérifie l'absence
%   d'erreur et d'avertissement (lastwarn vide), le contenu graphique attendu, puis on
%   exporte des PNG (dossier tempdir/MecaStruct_PlotEngine_png ou variable d'environnement
%   MECASTRUCT_PNG_DIR).
tests = functiontests(localfunctions);
end

%% ------------------------------------------------------------------ fixtures
function setupOnce(tc)
d = getenv('MECASTRUCT_PNG_DIR');
if isempty(d)
    d = fullfile(tempdir, 'MecaStruct_PlotEngine_png');
end
if ~isfolder(d)
    mkdir(d);
end
tc.TestData.png = d;
tc.TestData.warnState = warning;
end

function teardownOnce(tc)
warning(tc.TestData.warnState);
end

function setup(tc)
tc.TestData.figs = gobjects(0);
end

function teardown(tc)
for k = 1:numel(tc.TestData.figs)
    if isgraphics(tc.TestData.figs(k))
        delete(tc.TestData.figs(k));
    end
end
end

%% ------------------------------------------------------------------ outils
function [ax, uax] = makeAxes(tc, w, h)
% Un axes (figure invisible) et un uiaxes (uifigure invisible), thème clair.
if nargin < 2
    w = 900; h = 600;
end
f = figure('Visible', 'off', 'Position', [0 0 w h]);
uf = uifigure('Visible', 'off', 'Position', [0 0 w h]);
try
    theme(f, 'light');
    theme(uf, 'light');
catch
end
tc.TestData.figs(end+1) = f;
tc.TestData.figs(end+1) = uf;
ax = axes(f);
uax = uiaxes(uf, 'Position', [10 10 w-20 h-20]);
end

function runBoth(tc, name, fn, check)
% Exécute fn(ax) sur axes et uiaxes, vérifie l'absence d'avertissement, exporte en PNG.
[ax, uax] = makeAxes(tc);
targets = {ax, uax};
kinds = {'axes', 'uiaxes'};
for k = 1:2
    lastwarn('');
    fn(targets{k});
    drawnow;
    [msg, id] = lastwarn;
    tc.verifyEmpty(msg, sprintf('%s (%s) : avertissement %s', name, kinds{k}, id));
    if nargin >= 4
        check(targets{k});
    end
    PlotEngine.exportAxes(targets{k}, fullfile(tc.TestData.png, [name '_' kinds{k} '.png']));
    tc.verifyTrue(isfile(fullfile(tc.TestData.png, [name '_' kinds{k} '.png'])));
end
end

function n = nType(ax, type)
n = numel(findall(ax, 'Type', type));
end

function t = allText(ax)
h = findobj(ax.Children, 'flat', 'Type', 'text');
t = {};
for k = 1:numel(h)
    s = h(k).String;
    if iscell(s)
        t = [t; s(:)]; %#ok<AGROW>
    else
        t{end+1, 1} = char(s); %#ok<AGROW>
    end
end
end

function tf = hasText(ax, pat)
tf = any(contains(allText(ax), pat));
end

function n = nLegend(ax)
lg = ax.Legend;
if isempty(lg)
    n = 0;
else
    n = numel(lg.String);
end
end

function [m, sol] = beamSS()
% Appui-appui avec force, couple, charge linéaire et effort axial.
m = struct('L', 6, 'E', 210e9, 'Iz', 8e-6, 'S', 3e-3, 'G', 81e9);
m.supports = struct('pos', {0, 6}, 'type', {'rotule', 'appui_simple'}, 'name', {'A', 'B'});
m.pointLoads = struct('pos', {2}, 'Fx', {5e3}, 'Fy', {-20e3}, 'Fz', {0}, 'name', {'F1'});
m.pointMoments = struct('pos', {4}, 'Mx', {0}, 'My', {0}, 'Mz', {8e3}, 'name', {'C1'});
m.distLoads = struct('a', {3}, 'b', {6}, 'dir', {'y'}, 'coeffs', {[-2e3 -4e3]}, 'name', {'q'});
sol = BeamAndTrussSolver.solveBeam(m);
end

function [m, sol] = beamCantilever()
m = struct('L', 4, 'E', 210e9, 'Iz', 8e-6, 'S', 3e-3, 'G', 81e9);
m.supports = struct('pos', {0}, 'type', {'encastrement'}, 'name', {'A'});
m.pointLoads = struct('pos', {4}, 'Fx', {0}, 'Fy', {-10e3}, 'Fz', {0}, 'name', {'P'});
m.distLoads = struct('a', {0}, 'b', {4}, 'dir', {'y'}, 'coeffs', {-5e3}, 'name', {'q'});
sol = BeamAndTrussSolver.solveBeam(m);
end

function [m, sol] = beamHyper()
% Encastrée-appuyée, charge uniforme + appui glissant intermédiaire, charge parabolique.
m = struct('L', 5, 'E', 210e9, 'Iz', 1e-5, 'S', 4e-3, 'G', 81e9);
m.supports = struct('pos', {0, 5}, 'type', {'encastrement', 'pivot_glissant'}, 'name', {'A', 'B'});
m.pointLoads = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
m.distLoads = struct('a', {0, 1}, 'b', {5, 4}, 'dir', {'y', 'y'}, 'coeffs', {-8e3, [1e3 -3e3 -2e3]}, ...
    'name', {'q1', 'q2'});
sol = BeamAndTrussSolver.solveBeam(m);
end

%% ------------------------------------------------------------------ beamSchematic
function testBeamSchematicSimplySupported(tc)
[m, sol] = beamSS();
runBoth(tc, 'beam_appui_appui', @(ax) PlotEngine.beamSchematic(ax, m, sol), @(ax) chk(ax));
    function chk(ax)
        tc.verifyEqual(nLegend(ax), 4);                    % poutre, réparties, forces, réactions
        tc.verifyTrue(hasText(ax, 'Y_{A}'));
        tc.verifyTrue(hasText(ax, 'Y_{B}'));
        tc.verifyTrue(hasText(ax, 'X_{A}'));
        tc.verifyTrue(hasText(ax, 'F_{1,y} = -20'));
        tc.verifyTrue(hasText(ax, 'C_{1,z} = 8'));
        tc.verifyEqual(ax.XTick, [0 2 3 4 6], 'AbsTol', 1e-9);
        tc.verifyGreaterThan(nType(ax, 'patch'), 10);        % pointes de flèches + appuis
    end
end

function testBeamSchematicCantileverAndNoSol(tc)
[m, sol] = beamCantilever();
runBoth(tc, 'beam_console', @(ax) PlotEngine.beamSchematic(ax, m, sol), ...
    @(ax) tc.verifyTrue(hasText(ax, 'M_{A} = 80')));
% sans solution : pas de réactions
runBoth(tc, 'beam_console_sans_sol', @(ax) PlotEngine.beamSchematic(ax, m), ...
    @(ax) tc.verifyEqual(nLegend(ax), 3));
end

function testBeamSchematicHyperAndOtherDirections(tc)
[m, sol] = beamHyper();
runBoth(tc, 'beam_hyper', @(ax) PlotEngine.beamSchematic(ax, m, sol), ...
    @(ax) tc.verifyTrue(hasText(ax, 'q_{2}(1)')));
m2 = struct('L', 3, 'E', 210e9, 'Iz', 1e-6, 'Iy', 1e-6, 'S', 1e-3);
m2.supports = struct('pos', {0}, 'type', {'encastrement'}, 'name', {'A'});
m2.pointLoads = struct('pos', {3}, 'Fx', {-2e3}, 'Fy', {0}, 'Fz', {1e3}, 'name', {'F'});
m2.pointMoments = struct('pos', {3}, 'Mx', {500}, 'My', {0}, 'Mz', {0}, 'name', {'C'});
m2.distLoads = struct('a', {0, 1}, 'b', {2, 3}, 'dir', {'x', 'z'}, 'coeffs', {1e3, -800}, 'name', {'px', 'pz'});
sol2 = BeamAndTrussSolver.solveBeam(m2);
runBoth(tc, 'beam_3d', @(ax) PlotEngine.beamSchematic(ax, m2, sol2), @(ax) chk(ax));
    function chk(ax)
        tc.verifyTrue(hasText(ax, 'F_{z} = 1'));
        tc.verifyTrue(hasText(ax, 'C_{x} = 0.5'));
        tc.verifyTrue(hasText(ax, 'Z_{A}'));
    end
end

function testBeamSchematicErrors(tc)
tc.verifyError(@() PlotEngine.beamSchematic([], struct('L', -1)), 'MecaStruct:PlotEngine:invalidInput');
f = figure('Visible', 'off');
tc.TestData.figs(end+1) = f;
[m, ~] = beamSS();
tc.verifyError(@() PlotEngine.beamSchematic(f, m), 'MecaStruct:PlotEngine:invalidAxes');
end

%% ------------------------------------------------------------------ internalForces
function testInternalForcesAxesAndUiaxes(tc)
[~, sol] = beamSS();
comps = {'N', 'Ty', 'Mfz'};
f = figure('Visible', 'off', 'Position', [0 0 900 900]);
uf = uifigure('Visible', 'off', 'Position', [0 0 900 900]);
tc.TestData.figs(end+1) = f;
tc.TestData.figs(end+1) = uf;
tl = tiledlayout(f, 3, 1);
axl = [nexttile(tl) nexttile(tl) nexttile(tl)];
g = uigridlayout(uf, [3 1]);
uaxl = [uiaxes(g) uiaxes(g) uiaxes(g)];
sets = {axl, uaxl};
names = {'axes', 'uiaxes'};
for k = 1:2
    lastwarn('');
    out = PlotEngine.internalForces(sets{k}, sol, comps);
    drawnow;
    tc.verifyEmpty(lastwarn);
    tc.verifyEqual(numel(out), 3);
    for j = 1:3
        tc.verifyEqual(out(j).XLim, [0 6], 'AbsTol', 1e-12);
        tc.verifyEqual(nType(out(j), 'patch'), 2);            % aires > 0 et < 0
        tc.verifyEqual(nLegend(out(j)), 3);
    end
    % extrema annotés : Ty min = -YA en s = 0, Mfz max en s = 2
    tc.verifyTrue(hasText(out(2), sprintf('{T_y}_{min} = %.4g', -sol.reactions(1).Ry / 1e3)));
    tc.verifyTrue(hasText(out(3), '{M_{fz}}_{max}'));
    % axes x liés
    xlim(out(1), [1 2]);
    tc.verifyEqual(out(3).XLim, [1 2], 'AbsTol', 1e-12);
    xlim(out(1), [0 6]);
    if k == 1
        exportgraphics(f, fullfile(tc.TestData.png, 'efforts_axes.png'));
    else
        exportapp(uf, fullfile(tc.TestData.png, 'efforts_uiaxes.png'));
    end
    tc.verifyTrue(contains(names{k}, 'axes'));
end
end

function testInternalForcesDefaultsAndErrors(tc)
[~, sol] = beamHyper();
lastwarn('');
axl = PlotEngine.internalForces([], sol);
tc.TestData.figs(end+1) = ancestor(axl(1), 'figure');
tc.TestData.figs(end).Visible = 'off';
tc.verifyEmpty(lastwarn);
tc.verifyEqual(numel(axl), 2);                                   % Ty et Mfz non nuls
exportgraphics(ancestor(axl(1), 'figure'), fullfile(tc.TestData.png, 'efforts_hyper.png'));
tc.verifyError(@() PlotEngine.internalForces([], sol, {'Mx'}), 'MecaStruct:PlotEngine:invalidInput');
[ax, ~] = makeAxes(tc);
tc.verifyError(@() PlotEngine.internalForces(ax, sol, {'Ty', 'Mfz'}), 'MecaStruct:PlotEngine:invalidAxes');
tc.verifyError(@() PlotEngine.internalForces(ax, struct('a', 1)), 'MecaStruct:PlotEngine:invalidInput');
end

%% ------------------------------------------------------------------ deflection
function testDeflection(tc)
[m, sol] = beamSS();
d = SolicitationsEngine.deflection(m, sol);
[a1, u1] = makeAxes(tc);
[a2, u2] = makeAxes(tc);
pairs = {{a1, a2}, {u1, u2}};
kinds = {'axes', 'uiaxes'};
for k = 1:2
    lastwarn('');
    [axA, axV] = PlotEngine.deflection(pairs{k}{1}, pairs{k}{2}, m, d);
    drawnow;
    tc.verifyEmpty(lastwarn);
    tc.verifyGreaterThanOrEqual(nLegend(axV), 4);               % poutre, intégration, aires, Castigliano...
    tc.verifyGreaterThanOrEqual(nLegend(axA), 2);
    tc.verifyTrue(hasText(axV, 'f_{max}'));
    tc.verifyEqual(axV.XLim, [0 6], 'AbsTol', 1e-12);
    PlotEngine.exportAxes(axA, fullfile(tc.TestData.png, ['rotation_' kinds{k} '.png']));
    PlotEngine.exportAxes(axV, fullfile(tc.TestData.png, ['deformee_' kinds{k} '.png']));
end
% console : fmax = PL^3/(3EI) affichée (mm)
mc = struct('L', 2, 'E', 210e9, 'Iz', 1e-6, 'S', 1e-3, 'G', 81e9);
mc.supports = struct('pos', {0}, 'type', {'encastrement'}, 'name', {'A'});
mc.pointLoads = struct('pos', {2}, 'Fx', {0}, 'Fy', {-1e3}, 'Fz', {0}, 'name', {'P'});
solc = BeamAndTrussSolver.solveBeam(mc);
dc = SolicitationsEngine.deflection(mc, solc);
lastwarn('');
[~, axV] = PlotEngine.deflection(a1, a2, mc, dc);
tc.verifyEmpty(lastwarn);
f = 1e3 * 2^3 / (3 * 210e9 * 1e-6) * 1e3;
tc.verifyTrue(hasText(axV, sprintf('f_{max} = %.4g', f)));
% un seul axe
lastwarn('');
[axA, axV] = PlotEngine.deflection([], u2, mc, dc);
tc.verifyEmpty(lastwarn);
tc.verifyEmpty(axA);
tc.verifyTrue(isgraphics(axV));
tc.verifyError(@() PlotEngine.deflection(a1, a2, mc, struct()), 'MecaStruct:PlotEngine:invalidInput');
end

%% ------------------------------------------------------------------ section
function testSectionShapes(tc)
secs = {struct('type', 'rectangle', 'b', 0.1, 'h', 0.2), ...
    struct('type', 'couronne', 'D', 0.1, 'd', 0.06), ...
    struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.006, 'tf', 0.009), ...
    struct('type', 'T', 'h', 0.12, 'b', 0.1, 'tw', 0.01, 'tf', 0.012), ...
    struct('type', 'U', 'h', 0.12, 'b', 0.055, 'tw', 0.007, 'tf', 0.009), ...
    struct('type', 'rectangle_creux', 'B', 0.1, 'H', 0.15, 't', 0.008), ...
    struct('type', 'composite', 'rects', [0 0.1 0 0.02; 0.04 0.06 0.02 0.12], 'holes', [0.01 0.03 0.005 0.015])};
for k = 1:numel(secs)
    sec = secs{k};
    P = GeometryEngine.analytical(sec);
    runBoth(tc, ['section_' sec.type], @(ax) PlotEngine.section(ax, sec, P), @(ax) chk(ax, P));
end
    function chk(ax, P)
        tc.verifyEqual(nType(ax, 'polygon'), 1);
        % axes principaux tracés seulement si Iyz ≠ 0 (composite à trou excentré)
        tc.verifyEqual(nLegend(ax), 3 + (abs(P.Iyz) > 1e-9 * max(P.Iz, P.Iy)));
        tc.verifyTrue(hasText(ax, '$G$'));
        tc.verifyTrue(any(contains(allText(ax), 'y_G')));
    end
end

function testSectionPrincipalAxes(tc)
sec = struct('type', 'L', 'h', 0.1, 'b', 0.06, 't', 0.01);
P = GeometryEngine.analytical(sec);
tc.assertGreaterThan(abs(P.Iyz), 0);
runBoth(tc, 'section_L', @(ax) PlotEngine.section(ax, sec, P), @(ax) chk(ax));
% P absent : calcul analytique interne
runBoth(tc, 'section_L_sansP', @(ax) PlotEngine.section(ax, sec), @(ax) chk(ax));
    function chk(ax)
        tc.verifyEqual(nLegend(ax), 4);
        tc.verifyTrue(hasText(ax, '\alpha_P'));
        tc.verifyTrue(hasText(ax, sprintf('%.4g', P.alphaP * 180 / pi)));
    end
end

%% ------------------------------------------------------------------ sectionStress
function testSectionStress(tc)
sec = struct('type', 'rectangle', 'b', 0.05, 'h', 0.1);
P = GeometryEngine.analytical(sec);
bend = SolicitationsEngine.bendingStress(struct('sec', sec, 'N', 20e3, 'Mfz', 3e3, 'Mfy', 0, 'Re', 235e6));
jour = SolicitationsEngine.jourawski(sec, 10e3);
[a1, u1] = makeAxes(tc);
[a2, u2] = makeAxes(tc);
pairs = {{a1, a2}, {u1, u2}};
kinds = {'axes', 'uiaxes'};
for k = 1:2
    lastwarn('');
    [axS, axT] = PlotEngine.sectionStress(pairs{k}{1}, pairs{k}{2}, sec, P, bend, jour);
    drawnow;
    tc.verifyEmpty(lastwarn);
    tc.verifyTrue(any(contains(axS.Legend.String, 'Axe neutre')));
    tc.verifyEqual(nLegend(axT), 3);                             % Jourawski, parabole, tau moy
    tc.verifyTrue(hasText(axT, sprintf('\\tau_{max} = %.4g', 1.5 * 10e3 / 0.005 / 1e6)));
    PlotEngine.exportAxes(axS, fullfile(tc.TestData.png, ['sigma_' kinds{k} '.png']));
    PlotEngine.exportAxes(axT, fullfile(tc.TestData.png, ['tau_' kinds{k} '.png']));
end
% profilé en I : pas de parabole de référence ; un seul profil
secI = struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.006, 'tf', 0.009);
jI = SolicitationsEngine.jourawski(secI, 50e3);
lastwarn('');
[axS, axT] = PlotEngine.sectionStress([], u2, secI, [], [], jI);
tc.verifyEmpty(lastwarn);
tc.verifyEmpty(axS);
tc.verifyEqual(nLegend(axT), 2);
PlotEngine.exportAxes(axT, fullfile(tc.TestData.png, 'tau_I.png'));
end

%% ------------------------------------------------------------------ flambage
function testBucklingCurve(tc)
c = BucklingEngine.stabilityCurve(210e9, 235e6);
b = BucklingEngine.analyze(struct('E', 210e9, 'Re', 235e6, 'S', 1e-3, 'Iz', 2e-6, 'Iy', 1e-6, 'L', 2, ...
    'condition', 'articule-articule', 'P', 80e3));
runBoth(tc, 'flambage', @(ax) PlotEngine.bucklingCurve(ax, c, b), @(ax) chk(ax, 6));
bE = BucklingEngine.analyze(struct('E', 210e9, 'Re', 235e6, 'S', 1e-3, 'Iz', 2e-6, 'Iy', 1e-6, 'L', 5, ...
    'condition', 'encastre-libre'));
runBoth(tc, 'flambage_euler', @(ax) PlotEngine.bucklingCurve(ax, c, bE), @(ax) chk(ax, 5));
runBoth(tc, 'flambage_seul', @(ax) PlotEngine.bucklingCurve(ax, c), @(ax) chk(ax, 4));
    function chk(ax, nl)
        tc.verifyEqual(nLegend(ax), nl);
        tc.verifyEqual(ax.XLim, [0 300]);
        tc.verifyTrue(hasText(ax, 'Rankine'));
        tc.verifyEqual(nType(ax, 'ConstantLine'), 2);   % λ = 20 et λlim
    end
end

%% ------------------------------------------------------------------ Mohr
function testMohr2DStressAndStrain(tc)
r = TensorAndCriteriaEngine.plane2D(80e6, -20e6, 30e6, 0.3);
runBoth(tc, 'mohr2D', @(ax) PlotEngine.mohr2D(ax, r), @(ax) chk(ax, 6));
runBoth(tc, 'mohr2D_sans_facette', @(ax) PlotEngine.mohr2D(ax, r, []), @(ax) chk(ax, 6));
r0 = TensorAndCriteriaEngine.plane2D(80e6, -20e6, 30e6);
runBoth(tc, 'mohr2D_theta0', @(ax) PlotEngine.mohr2D(ax, r0), @(ax) chk(ax, 5));
e = TensorAndCriteriaEngine.plane2DStrain(400e-6, -100e-6, 150e-6);
runBoth(tc, 'mohr2D_deformations', @(ax) PlotEngine.mohr2D(ax, e, pi / 8), @(ax) chk(ax, 6));
% point de facette : σ(θ), τ(θ) du moteur (rotation de 2θ de A)
[ax, ~] = makeAxes(tc);
PlotEngine.mohr2D(ax, r);
tc.verifyTrue(hasText(ax, sprintf('\\sigma = %.4g', r.sigma / 1e6)));
tc.verifyTrue(hasText(ax, sprintf('\\tau = %.4g', r.tau / 1e6)));
    function chk(ax, nl)
        tc.verifyEqual(nLegend(ax), nl);
        tc.verifyTrue(hasText(ax, '\rho ='));
        tc.verifyTrue(hasText(ax, '\delta ='));
    end
end

function testMohr3D(tc)
m3 = TensorAndCriteriaEngine.mohr3D([100e6 30e6 -40e6]);
runBoth(tc, 'mohr3D', @(ax) PlotEngine.mohr3D(ax, m3, [20e6 50e6]), @(ax) chk(ax, 5, 1));
pr = TensorAndCriteriaEngine.principal([50e6 20e6 0; 20e6 -10e6 0; 0 0 0]);
m3b = TensorAndCriteriaEngine.mohr3D([pr.sigmaI pr.sigmaII pr.sigmaIII]);
runBoth(tc, 'mohr3D_plan', @(ax) PlotEngine.mohr3D(ax, m3b), @(ax) chk(ax, 4, 1));
% traction simple : petit cercle confondu avec le grand, l'autre réduit à un point → pas de zone
m3c = TensorAndCriteriaEngine.mohr3D([100e6 0 0]);
runBoth(tc, 'mohr3D_traction', @(ax) PlotEngine.mohr3D(ax, m3c), @(ax) chk(ax, 3, 0));
    function chk(ax, nl, np)
        tc.verifyEqual(nLegend(ax), nl);
        tc.verifyEqual(nType(ax, 'polygon'), np);                % zone admissible ombrée
        tc.verifyTrue(hasText(ax, '\tau_{max}'));
    end
end

function testYieldLocus(tc)
L = TensorAndCriteriaEngine.yieldLoci(235e6, 1.5, 300e6);
runBoth(tc, 'lieux', @(ax) PlotEngine.yieldLocus(ax, L, [120e6 -60e6]), @(ax) chk(ax, 4));
runBoth(tc, 'lieux_sans_point', @(ax) PlotEngine.yieldLocus(ax, L), @(ax) chk(ax, 3));
    function chk(ax, nl)
        tc.verifyEqual(nLegend(ax), nl);
        tc.verifyTrue(hasText(ax, sprintf('%.4g', 235 / 1.5)));
    end
end

%% ------------------------------------------------------------------ treillis
function testTruss2D(tc)
t = struct('nodes', [0 0; 4 0; 2 3], 'bars', [1 2; 2 3; 1 3], 'E', 210e9, 'S', 1e-4, ...
    'supports', logical([1 1; 0 1; 0 0]), 'loads', [0 0; 0 0; 10e3 -30e3], 'names', {{'A'; 'B'; 'C'}});
ts = BeamAndTrussSolver.solveTruss(t);
runBoth(tc, 'treillis', @(ax) PlotEngine.truss(ax, t, ts), @(ax) chk(ax));
runBoth(tc, 'treillis_sans_sol', @(ax) PlotEngine.truss(ax, t), ...
    @(ax) tc.verifyEqual(nLegend(ax), 2));                       % barres, charges
runBoth(tc, 'treillis_sans_deformee', @(ax) PlotEngine.truss(ax, t, ts, 0), ...
    @(ax) tc.verifyFalse(any(contains(ax.Legend.String, 'form'))));
    function chk(ax)
        tc.verifyEqual(nLegend(ax), 5);                          % déformée, traction, compression, charges, réactions
        for b = 1:3
            tc.verifyTrue(hasText(ax, sprintf('N_{%d} = %.4g', b, ts.N(b) / 1e3)));
        end
        red = findobj(ax.Children, 'flat', 'Type', 'line', 'LineWidth', 3, 'Color', [0.85 0.15 0.15]);
        blue = findobj(ax.Children, 'flat', 'Type', 'line', 'LineWidth', 3, 'Color', [0.00 0.45 0.74]);
        tc.verifyEqual(numel(red), nnz(strcmp(ts.nature, 'Traction')));
        tc.verifyEqual(numel(blue), nnz(strcmp(ts.nature, 'Compression')));
    end
end

function testTrussHyperAndZeroBar(tc)
% treillis hyperstatique avec barre nulle (nœud D non chargé relié à C seul par deux barres alignées)
t = struct('nodes', [0 0; 3 0; 6 0; 3 3; 6 3], 'bars', [1 2; 2 3; 1 4; 2 4; 3 4; 4 5; 3 5; 2 5], ...
    'E', 210e9, 'S', 2e-4, 'supports', logical([1 1; 0 0; 1 1; 0 0; 0 0]), ...
    'loads', [0 0; 0 -20e3; 0 0; 5e3 0; 0 0]);
ts = BeamAndTrussSolver.solveTruss(t);
runBoth(tc, 'treillis_hyper', @(ax) PlotEngine.truss(ax, t, ts, 50), ...
    @(ax) tc.verifyTrue(any(contains(ax.Legend.String, '\times 50'))));
end

function testTruss3D(tc)
t = struct('nodes', [0 0 0; 2 0 0; 1 2 0; 1 0.7 2], 'bars', [1 4; 2 4; 3 4], 'E', 210e9, 'S', 1e-4, ...
    'supports', logical([1 1 1; 1 1 1; 1 1 1; 0 0 0]), 'loads', [0 0 0; 0 0 0; 0 0 0; 1e3 0 -10e3]);
ts = BeamAndTrussSolver.solveTruss(t);
runBoth(tc, 'treillis_3D', @(ax) PlotEngine.truss(ax, t, ts), @(ax) chk(ax));
    function chk(ax)
        tc.verifyEqual(numel(findobj(ax.Children, 'flat', 'Type', 'line', 'LineWidth', 3)), 3);
        tc.verifyEqual(numel(findobj(ax.Children, 'flat', 'Type', 'quiver')), 4);   % 1 charge + 3 réactions
    end
end

%% ------------------------------------------------------------------ formulaire
function testFormulaSheetAllKeys(tc)
keys = DataManager.formulaKeys();
[ax, uax] = makeAxes(tc, 700, 900);
targets = {ax, uax};
for k = 1:numel(keys)
    sheet = DataManager.formulaSheet(keys{k});
    for j = 1:2
        lastwarn('');
        h = PlotEngine.formulaSheet(targets{j}, sheet);
        drawnow;
        [msg, id] = lastwarn;
        tc.verifyEmpty(msg, sprintf('Fiche %s : %s', keys{k}, id));
        tc.verifyGreaterThan(h, 30 * numel(sheet));
        tc.verifyEqual(numel(findobj(targets{j}.Children, 'flat', 'Type', 'text', 'Interpreter', 'latex')), numel(sheet));
        tc.verifyEqual(targets{j}.YLim, [0 h]);
    end
end
% rendu à la hauteur conseillée (une unité = un pixel)
sheet = DataManager.formulaSheet('flexion');
h = PlotEngine.formulaSheet(ax, sheet);
f = ancestor(ax, 'figure');
f.Position = [0 0 700 h + 20];
ax.Units = 'pixels';
ax.Position = [10 10 680 h];
h2 = PlotEngine.formulaSheet(ax, sheet);
tc.verifyEqual(h2, h);
PlotEngine.exportAxes(ax, fullfile(tc.TestData.png, 'formulaire_flexion.png'));
% clé directe
lastwarn('');
h3 = PlotEngine.formulaSheet(uax, 'mohr_cercle');
tc.verifyEmpty(lastwarn);
tc.verifyGreaterThan(h3, 0);
end

%% ------------------------------------------------------------------ Kt
function testKtCharts(tc)
charts = DataManager.ktCharts();
for k = 1:numel(charts)
    id = charts(k).id;
    nCurves = max(1, numel(charts(k).curves));
    runBoth(tc, ['kt_' id], @(ax) PlotEngine.ktChart(ax, id), @(ax) chk(ax, nCurves));
end
[ax, ~] = makeAxes(tc);
tc.verifyError(@() PlotEngine.ktChart(ax, 'inconnu'), 'MecaStruct:PlotEngine:unknownKt');
    function chk(ax, n)
        tc.verifyEqual(nType(ax, 'line'), n);
        tc.verifyGreaterThanOrEqual(min(ax.YLim), 1);
    end
end

%% ------------------------------------------------------------------ export
function testExportAxes(tc)
[ax, uax] = makeAxes(tc);
r = TensorAndCriteriaEngine.plane2D(50e6, 10e6, -20e6, 0.2);
PlotEngine.mohr2D(ax, r);
PlotEngine.mohr2D(uax, r);
d = fullfile(tc.TestData.png, 'export_sub');
if isfolder(d)
    rmdir(d, 's');
end
files = {fullfile(d, 'a.png'), fullfile(d, 'a.pdf'), fullfile(d, 'u.png'), fullfile(d, 'u.pdf')};
PlotEngine.exportAxes(ax, files{1});
PlotEngine.exportAxes(ax, files{2});
PlotEngine.exportAxes(uax, files{3});
PlotEngine.exportAxes(uax, files{4});
for k = 1:4
    tc.verifyTrue(isfile(files{k}));
    info = dir(files{k});
    tc.verifyGreaterThan(info.bytes, 1000);
end
fid = fopen(files{2}, 'r');
hdr = fread(fid, 5, '*char').';
fclose(fid);
tc.verifyEqual(hdr, '%PDF-');
tc.verifyError(@() PlotEngine.exportAxes(ax, fullfile(d, 'a.xyz')), 'MecaStruct:PlotEngine:invalidFormat');
tc.verifyError(@() PlotEngine.exportAxes([], fullfile(d, 'a.png')), 'MecaStruct:PlotEngine:invalidAxes');
end

%% ------------------------------------------------------------------ création de figure
function testEmptyAxesCreatesFigure(tc)
r = TensorAndCriteriaEngine.plane2D(50e6, 10e6, -20e6);
nBefore = numel(findall(groot, 'Type', 'figure'));
ax = PlotEngine.mohr2D([], r);
f = ancestor(ax, 'figure');
f.Visible = 'off';
tc.TestData.figs(end+1) = f;
tc.verifyTrue(isgraphics(ax, 'axes'));
tc.verifyEqual(numel(findall(groot, 'Type', 'figure')), nBefore + 1);
% axe fourni : aucune figure créée, axe effacé à chaque appel
[ax2, ~] = makeAxes(tc);
n1 = numel(findall(groot, 'Type', 'figure'));
PlotEngine.mohr2D(ax2, r);
c1 = numel(ax2.Children);
PlotEngine.mohr2D(ax2, r);
tc.verifyEqual(numel(ax2.Children), c1);
tc.verifyEqual(numel(findall(groot, 'Type', 'figure')), n1);
end
