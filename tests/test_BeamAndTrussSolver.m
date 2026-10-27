function tests = test_BeamAndTrussSolver
%TEST_BEAMANDTRUSSSOLVER Tests unitaires du module BeamAndTrussSolver.
%   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
%   Couvre les utilitaires pp (§0.5), la résolution des poutres (§3 et §9 :
%   cas d'école isostatiques et hyperstatiques, plans xy et xz, torsion,
%   effort axial, couples, charges linéaires), l'équivalence coupures ≡
%   intégrale et Ménabréa ≡ intégration, les mécanismes, les treillis 2D/3D
%   (isostatiques, hyperstatiques, mécanismes), le format des rapports et la
%   validité des chaînes LaTeX.
%
%   Lancement : r = runtests('tests/test_BeamAndTrussSolver.m');
tests = functiontests(localfunctions);
end

%% =====================================================================
%%                       UTILITAIRES pp
%% =====================================================================

function testPpEvalSides(tc)
pp = struct('breaks', [0 1 3], 'coefs', {{[2 0], 5}});
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 1), 5);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 1, 'right'), 5);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 1, 'left'), 2);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 0, 'left'), 0);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 3), 5);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 3, 'left'), 5);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, [0.5 2; 1 3]), [1 5; 5 5]);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, [0.25; 0.5]), [0.5; 1]);
% tolérance relative 1e-12·L aux points de rupture
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 1 - 1e-14), 5);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 1 + 1e-14, 'left'), 2, 'AbsTol', 1e-12);
% prolongement hors du domaine
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, -1), -2);
tc.verifyEqual(BeamAndTrussSolver.ppEval(pp, 4), 5);
tc.verifyEmpty(BeamAndTrussSolver.ppEval(pp, []));
tc.verifyError(@() BeamAndTrussSolver.ppEval(pp, 1, 'milieu'), 'MecaStruct:BeamAndTrussSolver:invalidArgument');
tc.verifyError(@() BeamAndTrussSolver.ppEval(struct('a', 1), 1), 'MecaStruct:BeamAndTrussSolver:invalidPP');
tc.verifyError(@() BeamAndTrussSolver.ppEval(struct('breaks', [0 1 2], 'coefs', {{1}}), 1), ...
    'MecaStruct:BeamAndTrussSolver:invalidPP');
end

function testPpSample(tc)
pp = struct('breaks', [0 1 3], 'coefs', {{[2 0], 5}});
[s, v] = BeamAndTrussSolver.ppSample(pp, 5);
tc.verifySize(s, [1 10]);
tc.verifySize(v, [1 10]);
tc.verifyEqual(s([5 6]), [1 1]);
tc.verifyEqual(v([5 6]), [2 5]);
tc.verifyEqual(s([1 end]), [0 3]);
idx = [1:4 7:10];
tc.verifyEqual(v(idx), BeamAndTrussSolver.ppEval(pp, s(idx)), 'AbsTol', 1e-14);
[s60, ~] = BeamAndTrussSolver.ppSample(pp);
tc.verifyNumElements(s60, 120);
tc.verifyError(@() BeamAndTrussSolver.ppSample(pp, 1), 'MecaStruct:BeamAndTrussSolver:invalidArgument');
end

function testPpIntegrateDerivative(tc)
pp = struct('breaks', [0 1 3], 'coefs', {{[2 0], 5}});
P = BeamAndTrussSolver.ppIntegrate(pp, 2);
% primitive : s² + 2 sur [0,1], 5s - 2 sur [1,3]
tc.verifyEqual(BeamAndTrussSolver.ppEval(P, [0 0.5 1 2 3]), [2 2.25 3 8 13], 'AbsTol', 1e-13);
tc.verifyEqual(BeamAndTrussSolver.ppEval(P, 1, 'left'), BeamAndTrussSolver.ppEval(P, 1, 'right'), 'AbsTol', 1e-13);
P0 = BeamAndTrussSolver.ppIntegrate(pp);
tc.verifyEqual(BeamAndTrussSolver.ppEval(P0, 0), 0, 'AbsTol', 1e-15);
Dp = BeamAndTrussSolver.ppDerivative(P);
t = [0.1 0.7 1.3 2.9];
tc.verifyEqual(BeamAndTrussSolver.ppEval(Dp, t), BeamAndTrussSolver.ppEval(pp, t), 'AbsTol', 1e-12);
Dc = BeamAndTrussSolver.ppDerivative(BeamAndTrussSolver.ppConst([0 2], 7));
tc.verifyEqual(BeamAndTrussSolver.ppEval(Dc, 1), 0);
% intégration double d'une constante : s²/2
P2 = BeamAndTrussSolver.ppIntegrate(BeamAndTrussSolver.ppIntegrate(BeamAndTrussSolver.ppConst([0 1 2 4], 1)));
tc.verifyEqual(BeamAndTrussSolver.ppEval(P2, [0.5 1.5 3 4]), [0.5 1.5 3 4].^2 / 2, 'RelTol', 1e-13);
end

function testPpAddScaleMultiplyRefine(tc)
A = struct('breaks', [0 2 4], 'coefs', {{[1 0], [-1 4]}});
B = struct('breaks', [0 1 4], 'coefs', {{3, [1 1]}});
fA = @(s) (s < 2) .* s + (s >= 2) .* (4 - s);
fB = @(s) (s < 1) * 3 + (s >= 1) .* (s + 1);
t = [0.3 0.9 1.4 1.99 2.5 3.7];
C = BeamAndTrussSolver.ppAdd(A, B);
tc.verifyEqual(C.breaks, [0 1 2 4]);
tc.verifyEqual(BeamAndTrussSolver.ppEval(C, t), fA(t) + fB(t), 'AbsTol', 1e-13);
C2 = BeamAndTrussSolver.ppAdd(A, 10);
tc.verifyEqual(BeamAndTrussSolver.ppEval(C2, t), fA(t) + 10, 'AbsTol', 1e-13);
M = BeamAndTrussSolver.ppMultiply(A, B);
tc.verifyEqual(M.breaks, [0 1 2 4]);
tc.verifyEqual(BeamAndTrussSolver.ppEval(M, t), fA(t) .* fB(t), 'AbsTol', 1e-12);
S = BeamAndTrussSolver.ppScale(A, -2);
tc.verifyEqual(BeamAndTrussSolver.ppEval(S, t), -2 * fA(t), 'AbsTol', 1e-13);
R = BeamAndTrussSolver.ppRefine(A, [0.5 3 5 -1]);
tc.verifyEqual(R.breaks, [0 0.5 2 3 4]);
tc.verifyEqual(BeamAndTrussSolver.ppEval(R, t), fA(t), 'AbsTol', 1e-13);
% fusion des points de rupture avec tolérance relative 1e-12·L
Bn = struct('breaks', [0 2 + 1e-13 4], 'coefs', {{1, 2}});
Cn = BeamAndTrussSolver.ppAdd(A, Bn);
tc.verifyNumElements(Cn.breaks, 3);
% le résultat reste une structure pp valide
tc.verifyTrue(iscell(C.coefs) && numel(C.coefs) == numel(C.breaks) - 1);
end

function testPpIntegralZeroConst(tc)
A = struct('breaks', [0 2 4], 'coefs', {{[1 0], [-1 4]}});
tc.verifyEqual(BeamAndTrussSolver.ppIntegral(A, 0, 4), 4, 'RelTol', 1e-13);
tc.verifyEqual(BeamAndTrussSolver.ppIntegral(A), 4, 'RelTol', 1e-13);
tc.verifyEqual(BeamAndTrussSolver.ppIntegral(A, 1, 3), 3, 'RelTol', 1e-13);
tc.verifyEqual(BeamAndTrussSolver.ppIntegral(A, 3, 1), -3, 'RelTol', 1e-13);
tc.verifyEqual(BeamAndTrussSolver.ppIntegral(A, [0 1], [4 3]), [4 3], 'RelTol', 1e-13);
Z = BeamAndTrussSolver.ppZero([0 1 2]);
tc.verifyEqual(Z.coefs, {0, 0});
tc.verifyEqual(BeamAndTrussSolver.ppEval(Z, [0 1.5 2]), [0 0 0]);
K = BeamAndTrussSolver.ppConst([0 1 2], 3);
tc.verifyEqual(BeamAndTrussSolver.ppIntegral(K, 0, 2), 6, 'RelTol', 1e-14);
tc.verifyError(@() BeamAndTrussSolver.ppConst([0 0 1], 1), 'MecaStruct:BeamAndTrussSolver:invalidPP');
tc.verifyError(@() BeamAndTrussSolver.ppZero(1), 'MecaStruct:BeamAndTrussSolver:invalidPP');
end

function testPoly2latexPoly2str(tc)
tc.verifyEqual(BeamAndTrussSolver.poly2latex([-3 2 -1]), '-3\,s^{2} + 2\,s - 1');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([1 0 0]), 's^{2}');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([-1 0 4]), '-s^{2} + 4');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([0 0]), '0');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([]), '0');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([2.5e-5 0]), '2.5 \cdot 10^{-5}\,s');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([1 -1], 'x'), 'x - 1');
tc.verifyEqual(BeamAndTrussSolver.poly2latex(12345.678), '1.235 \cdot 10^{4}');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([1e-20 1]), '1');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([0 -5000 0]), '-5000\,s');
tc.verifyEqual(BeamAndTrussSolver.poly2latex([2 3], '\xi'), '2\,\xi + 3');
tc.verifyEqual(BeamAndTrussSolver.poly2str([-1500 3000 -250]), '-1500*s^2 + 3000*s - 250');
% tronçon [9, 10] d'une console : l'équation imprimée doit redonner M(10) = 0 (termes qui se compensent)
c = [-617.3 12346 -61730];
f = str2func(['@(s) ' BeamAndTrussSolver.poly2str(c)]);
tc.verifyEqual(f(10), 0, 'AbsTol', 1e-6);
tc.verifyEqual(BeamAndTrussSolver.poly2str([0.5 -2 0]), '0.5*s^2 - 2*s');
tc.verifyEqual(BeamAndTrussSolver.poly2str([1 0], 'x'), 'x');
tc.verifyEqual(BeamAndTrussSolver.poly2str(0), '0');
tc.verifyEqual(BeamAndTrussSolver.poly2str(-0.25), '-0.25');
cases = {[1 -2 3 -4], [-1 -1 -1], [3 0 -2 0 1], [-7.5 1e-3]};
for k = 1:numel(cases)
    tc.verifyEmpty(strfind(BeamAndTrussSolver.poly2latex(cases{k}), '+ -'));
    tc.verifyEmpty(strfind(BeamAndTrussSolver.poly2str(cases{k}), '+ -'));
end
end

function testHasSymbolic(tc)
tf = BeamAndTrussSolver.hasSymbolic();
tc.verifyClass(tf, 'logical');
tc.verifySize(tf, [1 1]);
tc.verifyEqual(tf, logical(license('test', 'Symbolic_Toolbox')) && ~isempty(ver('symbolic')));
end

%% =====================================================================
%%                  POUTRES : CAS D'ÉCOLE (§9)
%% =====================================================================

function testSimplySupportedCentralLoad(tc)
L = 4; P = 1e4; EI = 210e9 * 8e-6;
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addF(m, L/2, 0, -P, 0);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyTrue(sol.isostatic);
tc.verifyEqual([sol.h.axial sol.h.xy sol.h.xz sol.h.torsion sol.h.total sol.h.plan2D], [0 0 0 0 0 0]);
tc.verifyEqual([sol.reactions.Ry], [P/2 P/2], 'RelTol', 1e-12);
tc.verifyEqual([sol.reactions.Rx sol.reactions.Rz sol.reactions.Mz], zeros(1, 6));
tc.verifyEqual(sol.extrema.Mfz.max, P*L/4, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.sMax, L/2, 'AbsTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfz, L/2), P*L/4, 'RelTol', 1e-12);
% saut de Ty : Ty(a-) = Ty(a+) + Fy
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Ty, L/2, 'left'), ...
    BeamAndTrussSolver.ppEval(sol.Ty, L/2, 'right') - P, 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Ty, 1), -P/2, 'RelTol', 1e-12);
% flèche (double intégration avec ppIntegrate) : PL³/(48EI)
v = deflectionAt(sol, EI, [0 0; L 0], L/2);
tc.verifyEqual(v, -P*L^3/(48*EI), 'RelTol', 1e-10);
tc.verifyLessThan(sol.methodCheck, 1e-12);
tc.verifyEmpty(sol.menabrea);
tc.verifyEmpty(sol.reactionsMenabrea);
tc.verifyEmpty(sol.reactionsIntegration);
tc.verifyEqual(sol.breaks, [0 L/2 L]);
tc.verifyEqual(sol.equations(1).Mfz, '$M_{fz}(s) = 5000\,s$');
tc.verifyEqual(sol.equations(1).Mfz_txt, 'Mfz(s) = 5000*s');
tc.verifyEqual(sol.equations(2).Ty_txt, 'Ty(s) = 5000');
tc.verifyEqual(sol.equations(1).N, '$N(s) = 0$');
end

function testCantileverTipLoad(tc)
L = 3; P = 2e3; EI = 210e9 * 8e-6;
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addF(m, L, 0, -P, 0);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyTrue(sol.isostatic);
tc.verifyEqual(sol.h.total, 0);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfz, 0), -P*L, 'RelTol', 1e-12);
tc.verifyEqual(sol.reactions.Ry, P, 'RelTol', 1e-12);
tc.verifyEqual(sol.reactions.Mz, P*L, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.min, -P*L, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.sMin, 0);
v = deflectionAt(sol, EI, [0 0; 0 1], L);
tc.verifyEqual(v, -P*L^3/(3*EI), 'RelTol', 1e-10);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

function testSimplySupportedUniform(tc)
L = 6; q = 5e3; EI = 210e9 * 8e-6;
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addQ(m, 0, L, 'y', -q);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual([sol.reactions.Ry], [q*L/2 q*L/2], 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.max, q*L^2/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.sMax, L/2, 'RelTol', 1e-10);
v = deflectionAt(sol, EI, [0 0; L 0], L/2);
tc.verifyEqual(v, -5*q*L^4/(384*EI), 'RelTol', 1e-10);
% relations différentielles : dTy/ds = -py et Ty = -dMfz/ds
dT = BeamAndTrussSolver.ppDerivative(sol.Ty);
dM = BeamAndTrussSolver.ppDerivative(sol.Mfz);
t = [0.4 2.2 5.1];
tc.verifyEqual(BeamAndTrussSolver.ppEval(dT, t), q * ones(1, 3), 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(dM, t), -BeamAndTrussSolver.ppEval(sol.Ty, t), 'RelTol', 1e-12);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

function testProppedCantileverUniform(tc)
L = 5; q = 1e3; EI = 210e9 * 8e-6;
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addQ(m, 0, L, 'y', -q);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyFalse(sol.isostatic);
tc.verifyEqual(sol.h.xy, 1);
tc.verifyEqual(sol.h.plan2D, 1);
tc.verifyEqual(sol.reactions(2).Ry, 3*q*L/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.reactions(1).Ry, 5*q*L/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.reactions(1).Mz, q*L^2/8, 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfz, 0), -q*L^2/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.max, 9*q*L^2/128, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.sMax, 5*L/8, 'RelTol', 1e-10);
% Ménabréa : système de base console, X = Y_B
tc.verifyTrue(isfield(sol.menabrea, 'xy'));
tc.verifyEqual(sol.menabrea.xy.unknowns, {'Y_B'});
tc.verifyEqual(sol.menabrea.xy.X, 3*q*L/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.menabrea.xy.delta, L^3/(3*EI), 'RelTol', 1e-12);
tc.verifyEqual(sol.menabrea.xy.rhs, q*L^4/(8*EI), 'RelTol', 1e-12);
tc.verifyEqual(sol.reactionsIntegration(2).Ry, 3*q*L/8, 'RelTol', 1e-10);
tc.verifyEqual(sol.reactionsMenabrea(1).Mz, q*L^2/8, 'RelTol', 1e-12);
tc.verifyLessThan(sol.hyperCheck, 1e-10);
% compatibilité cinématique : v(0) = v'(0) = v(L) = 0 vérifiées ensemble
[~, res] = deflectionAt(sol, EI, [0 0; 0 1; L 0], L/2);
tc.verifyLessThan(res, 1e-12);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

function testTwoEqualSpansUniform(tc)
L = 4; q = 2e3; EI = 210e9 * 8e-6;
m = baseModel(2*L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addSup(m, 2*L, 'appui_simple', 'C');
m = addQ(m, 0, 2*L, 'y', -q);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual(sol.h.xy, 1);
tc.verifyEqual(sol.reactions(2).Ry, 5*q*L/4, 'RelTol', 1e-12);
tc.verifyEqual([sol.reactions([1 3]).Ry], [3*q*L/8 3*q*L/8], 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfz, L), -q*L^2/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.menabrea.xy.unknowns, {'Y_B'});
tc.verifyEqual([sol.reactionsMenabrea.Ry], [sol.reactionsIntegration.Ry], 'RelTol', 1e-10);
[~, res] = deflectionAt(sol, EI, [0 0; L 0; 2*L 0], L/2);
tc.verifyLessThan(res, 1e-12);
end

function testFixedFixedUniform(tc)
L = 4; q = 3e3; EI = 210e9 * 8e-6;
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, L, 'encastrement', 'B');
m = addQ(m, 0, L, 'y', -q);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual([sol.h.axial sol.h.xy sol.h.xz sol.h.torsion sol.h.total], [1 2 2 1 6]);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfz, [0 L/2 L]), [-q*L^2/12, q*L^2/24, -q*L^2/12], 'RelTol', 1e-11);
tc.verifyEqual([sol.reactions.Ry], [q*L/2 q*L/2], 'RelTol', 1e-12);
tc.verifyEqual([sol.reactions.Mz], [q*L^2/12, -q*L^2/12], 'RelTol', 1e-11);
v = deflectionAt(sol, EI, [0 0; 0 1], L/2);
tc.verifyEqual(v, -q*L^4/(384*EI), 'RelTol', 1e-10);
[~, res] = deflectionAt(sol, EI, [0 0; 0 1; L 0; L 1], L/2);
tc.verifyLessThan(res, 1e-12);
tc.verifyEqual(sort(sol.menabrea.xy.unknowns), sort({'Y_B', 'Mz_B'}));
tc.verifySize(sol.menabrea.xy.delta, [2 2]);
tc.verifyLessThan(sol.hyperCheck, 1e-10);
end

function testAxialBarFixedFixed(tc)
L = 4; F = 6e3;
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, L, 'encastrement', 'B');
m = addF(m, L/2, F, 0, 0);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual(sol.h.axial, 1);
tc.verifyEqual([sol.reactions.Rx], [-F/2 -F/2], 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.N, [1 3]), [F/2 -F/2], 'RelTol', 1e-12);
tc.verifyEqual(sol.menabrea.axial.unknowns, {'X_B'});
tc.verifyEqual(sol.menabrea.axial.X, -F/2, 'RelTol', 1e-12);
tc.verifyEqual(sol.reactionsIntegration(1).Rx, -F/2, 'RelTol', 1e-10);
% position quelconque : répartition selon les raideurs
a = 1;
m2 = baseModel(L);
m2 = addSup(m2, 0, 'pivot', 'A');
m2 = addSup(m2, L, 'rotule', 'B');
m2 = addF(m2, a, F, 0, 0);
sol2 = BeamAndTrussSolver.solveBeam(m2, struct('useSymbolic', false));
tc.verifyEqual([sol2.reactions.Rx], [-F*(L-a)/L, -F*a/L], 'RelTol', 1e-12);
tc.verifyEqual(sol2.h.axial, 1);
tc.verifyEqual(sol2.h.xy, 0);
end

function testLoadsInPlaneXZ(tc)
L = 4; P = 8e3; q = 2e3; C0 = 5e3; a = 1;
% (a) force Fz centrée sur poutre sur deux appuis
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addF(m, L/2, 0, 0, -P);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual([sol.reactions.Rz], [P/2 P/2], 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfy, L/2), -P*L/4, 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Tz, 1), -P/2, 'RelTol', 1e-12);
dM = BeamAndTrussSolver.ppDerivative(sol.Mfy);
t = [0.5 1.7 2.6 3.9];
tc.verifyEqual(BeamAndTrussSolver.ppEval(dM, t), BeamAndTrussSolver.ppEval(sol.Tz, t), 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.max, 0);
tc.verifyLessThan(sol.methodCheck, 1e-12);
% (b) encastrée-appuyée dans le plan xz, charge pz uniforme
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addQ(m, 0, L, 'z', -q);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual(sol.h.xz, 1);
tc.verifyEqual(sol.reactions(2).Rz, 3*q*L/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.reactions(1).My, -q*L^2/8, 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfy, 0), q*L^2/8, 'RelTol', 1e-12);
tc.verifyEqual(sol.reactionsIntegration(1).My, -q*L^2/8, 'RelTol', 1e-10);
tc.verifyLessThan(sol.hyperCheck, 1e-10);
% flèche w : E Iy w'' = -Mfy, w(L/2) pour la console équivalente
EIy = 210e9 * 3e-6;
I1 = BeamAndTrussSolver.ppIntegrate(BeamAndTrussSolver.ppScale(sol.Mfy, -1/EIy));
I2 = BeamAndTrussSolver.ppIntegrate(I1);
wmax = max(abs(BeamAndTrussSolver.ppEval(I2, linspace(0, L, 41))));
tc.verifyGreaterThan(wmax, 0);
tc.verifyEqual(BeamAndTrussSolver.ppEval(I2, L), 0, 'AbsTol', 1e-12 * wmax);
% (c) couple My sur poutre sur deux appuis
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addC(m, a, 0, C0, 0);
sol = BeamAndTrussSolver.solveBeam(m, struct('useSymbolic', false));
tc.verifyEqual([sol.reactions.Rz], [-C0/L, C0/L], 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfy, a, 'left') - BeamAndTrussSolver.ppEval(sol.Mfy, a, 'right'), ...
    C0, 'RelTol', 1e-12);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

function testTorsion(tc)
L = 4; C = 900; a = 1;
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addC(m, L, C, 0, 0);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual(sol.reactions.Mx, -C, 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mt, [0 2 L]), [C C C], 'RelTol', 1e-12);
tc.verifyEqual(sol.h.torsion, 0);
% arbre bi-encastré : couple en a
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, L, 'encastrement', 'B');
m = addC(m, a, C, 0, 0);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual(sol.h.torsion, 1);
tc.verifyEqual([sol.reactions.Mx], [-C*(L-a)/L, -C*a/L], 'RelTol', 1e-12);
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mt, [0.5 2]), [C*(L-a)/L, -C*a/L], 'RelTol', 1e-12);
tc.verifyTrue(isfield(sol.menabrea, 'torsion'));
tc.verifyEqual(sol.menabrea.torsion.unknowns, {'Mx_B'});
tc.verifyEqual(sol.reactionsIntegration(2).Mx, -C*a/L, 'RelTol', 1e-10);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

function testPointCouple(tc)
L = 4; C0 = 4e3; a = 1;
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addC(m, a, 0, 0, C0);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual([sol.reactions.Ry], [C0/L, -C0/L], 'RelTol', 1e-12);
Ml = BeamAndTrussSolver.ppEval(sol.Mfz, a, 'left');
Mr = BeamAndTrussSolver.ppEval(sol.Mfz, a, 'right');
tc.verifyEqual(Ml, C0*a/L, 'RelTol', 1e-12);
tc.verifyEqual(Mr, -C0*(L-a)/L, 'RelTol', 1e-12);
tc.verifyEqual(Ml - Mr, C0, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.max, C0*a/L, 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.min, -C0*(L-a)/L, 'RelTol', 1e-12);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

function testTriangularLinearLoad(tc)
L = 6; q0 = 3e3;
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addQ(m, 0, L, 'y', [-q0/L, 0]);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual([sol.reactions.Ry], [q0*L/6, q0*L/3], 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.max, q0*L^2/(9*sqrt(3)), 'RelTol', 1e-12);
tc.verifyEqual(sol.extrema.Mfz.sMax, L/sqrt(3), 'RelTol', 1e-9);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

function testPartialTrapezoidLoadLocalXi(tc)
% charge linéaire de p1 = -2000 (s = 1) à p2 = -6000 (s = 3), ξ = s - a
L = 4; a = 1; b = 3; p1 = -2000; p2 = -6000;
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addQ(m, a, b, 'y', [(p2 - p1)/(b - a), p1]);
sol = BeamAndTrussSolver.solveBeam(m);
W = (b - a) * (p1 + p2) / 2;
xbar = a + (b - a) * (p1 + 2*p2) / (3*(p1 + p2));
RB = -W * xbar / L;
RA = -W - RB;
tc.verifyEqual([sol.reactions.Ry], [RA RB], 'RelTol', 1e-12);
tc.verifyEqual(sol.breaks, [0 1 3 4]);
p = @(x) p1 + (p2 - p1)/(b - a) * (x - a);
for s = [0.5 1.5 2 2.7 3.5]
    Ty = RB + integral(@(x) p(x) .* (x >= a & x <= b), s, L, 'AbsTol', 1e-12, 'RelTol', 1e-13, ...
        'Waypoints', [a b]);
    Mz = (L - s) * RB + integral(@(x) (x - s) .* p(x) .* (x >= a & x <= b), s, L, 'AbsTol', 1e-12, ...
        'RelTol', 1e-13, 'Waypoints', [a b]);
    tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Ty, s), Ty, 'RelTol', 1e-9);
    tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfz, s), Mz, 'RelTol', 1e-9);
end
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mfz, 2), 6000, 'RelTol', 1e-12);
tc.verifyEqual(sol.model.distLoads(1).coeffs, [(p2 - p1)/(b - a), p1]);
tc.verifyLessThan(sol.methodCheck, 1e-12);
end

%% =====================================================================
%%            POUTRES : ÉQUIVALENCE DES MÉTHODES
%% =====================================================================

function testCutsEqualIntegral(tc)
models = mixedModels();
symOpts = false;
if BeamAndTrussSolver.hasSymbolic()
    symOpts = [false true];
end
comps = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'};
for k = 1:numel(models)
    for us = symOpts
        sol = BeamAndTrussSolver.solveBeam(models{k}, struct('useSymbolic', us));
        tc.verifyLessThan(sol.methodCheck, 1e-10, sprintf('modèle %d, symbolique = %d', k, us));
        if us
            tc.verifyEqual(sol.internalIntegral.methodUsed, 'symbolique');
        else
            tc.verifyEqual(sol.internalIntegral.methodUsed, 'numérique');
        end
        tc.verifyLessThan(max(abs(sol.internalIntegral.closure)), 1e-8 * (1 + max(abs([sol.reactions.Ry]))));
        t = linspace(0, sol.model.L, 37);
        for c = 1:6
            v1 = BeamAndTrussSolver.ppEval(sol.(comps{c}), t);
            v2 = BeamAndTrussSolver.ppEval(sol.internalIntegral.(comps{c}), t);
            tc.verifyEqual(v2, v1, 'AbsTol', 1e-9 * (1 + max(abs(v1))));
        end
    end
end
end

function testMenabreaEqualsIntegration(tc)
models = mixedModels();
f = {'Rx', 'Ry', 'Rz', 'Mx', 'My', 'Mz'};
nHyper = 0;
for k = 1:numel(models)
    sol = BeamAndTrussSolver.solveBeam(models{k}, struct('useSymbolic', false));
    if sol.isostatic
        continue
    end
    nHyper = nHyper + 1;
    tc.verifyLessThan(sol.hyperCheck, 1e-9, sprintf('modèle %d', k));
    for j = 1:numel(f)
        a = [sol.reactionsMenabrea.(f{j})];
        b = [sol.reactionsIntegration.(f{j})];
        tc.verifyEqual(b, a, 'AbsTol', 1e-8 * (1 + max(abs(a))));
        tc.verifyEqual([sol.reactions.(f{j})], a);
    end
end
tc.verifyGreaterThanOrEqual(nHyper, 3);
end

function testShearEnergyMenabrea(tc)
L = 3; q = 4e3; E = 210e9; G = 80e9; S = 2e-3; Iz = 8e-6; ky = 5/6;
m = baseModel(L);
m.ky = ky;
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addQ(m, 0, L, 'y', -q);
sol = BeamAndTrussSolver.solveBeam(m, struct('includeShearEnergy', true, 'useSymbolic', false));
EI = E * Iz; kGS = ky * G * S;
RB = (q*L^4/(8*EI) + q*L^2/(2*kGS)) / (L^3/(3*EI) + L/kGS);
tc.verifyEqual(sol.reactions(2).Ry, RB, 'RelTol', 1e-11);
tc.verifyEqual(sol.reactionsIntegration(2).Ry, RB, 'RelTol', 1e-9);
tc.verifyTrue(sol.menabrea.xy.includeShear);
tc.verifyLessThan(sol.hyperCheck, 1e-9);
sol0 = BeamAndTrussSolver.solveBeam(m, struct('useSymbolic', false));
tc.verifyEqual(sol0.reactions(2).Ry, 3*q*L/8, 'RelTol', 1e-12);
tc.verifyGreaterThan(sol.reactions(2).Ry, sol0.reactions(2).Ry);
end

%% =====================================================================
%%        POUTRES : MÉCANISMES, ERREURS, OPTIONS, FORMAT
%% =====================================================================

function testMechanismDetection(tc)
L = 4;
% un seul appui simple, force excentrée : mécanisme
m = baseModel(L);
m = addSup(m, 0, 'appui_simple', 'A');
m = addF(m, 2, 0, -1e3, 0);
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:mechanism');
% deux appuis simples et effort axial : mécanisme axial
m = baseModel(L);
m = addSup(m, 0, 'appui_simple', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addF(m, 2, 1e3, 0, 0);
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:mechanism');
% aucune liaison et force : mécanisme
m = baseModel(L);
m = addF(m, 2, 0, -1e3, 0);
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:mechanism');
% torsion sans encastrement : mécanisme
m = baseModel(L);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addC(m, 2, 500, 0, 0);
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:mechanism');
% deux appuis au même point, force ailleurs : mécanisme
m = baseModel(L);
m = addSup(m, 1, 'pivot', 'A');
m = addSup(m, 1, 'appui_simple', 'B');
m = addF(m, 3, 0, -1e3, 0);
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:mechanism');
% sous-problèmes non chargés ou chargements équilibrés : pas d'erreur
m = baseModel(L);
m = addSup(m, 0, 'appui_simple', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addF(m, 2, 0, -1e3, 0);
m = addC(m, 1, 300, 0, 0);
m = addC(m, 3, -300, 0, 0);
sol = BeamAndTrussSolver.solveBeam(m);
tc.verifyEqual([sol.reactions.Ry], [500 500], 'RelTol', 1e-12);
tc.verifyEqual(sol.h.axial, 0);
tc.verifyEqual(sol.h.torsion, 0);
tc.verifyEqual(sol.h.plan2D, -1);
% Mt(s) = Σ_droite Mx : entre les deux couples, seul -300 (en s = 3) est à droite
tc.verifyEqual(BeamAndTrussSolver.ppEval(sol.Mt, [0.5 2 3.5]), [0 -300 0], 'AbsTol', 1e-12);
% appui unique sous la force : chargement compatible
m = baseModel(L);
m = addSup(m, 2, 'appui_simple', 'A');
m = addF(m, 2, 0, -1e3, 0);
sol = BeamAndTrussSolver.solveBeam(m, struct('useSymbolic', false));
tc.verifyEqual(sol.reactions.Ry, 1e3, 'RelTol', 1e-12);
tc.verifyEqual(sol.h.total, 0);
end

function testInvalidInputs(tc)
tc.verifyError(@() BeamAndTrussSolver.solveBeam(struct('L', 0)), 'MecaStruct:Beam:invalidModel');
tc.verifyError(@() BeamAndTrussSolver.solveBeam(struct('E', 1)), 'MecaStruct:Beam:invalidModel');
tc.verifyError(@() BeamAndTrussSolver.solveBeam(42), 'MecaStruct:Beam:invalidModel');
m = baseModel(4);
m = addSup(m, 0, 'glissiere_bizarre', 'A');
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:invalidSupport');
m = addSup(baseModel(4), 5, 'pivot', 'A');
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:invalidModel');
m = addQ(addSup(baseModel(4), 0, 'encastrement', 'A'), 2, 2, 'y', -1);
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:invalidModel');
m = addQ(addSup(baseModel(4), 0, 'encastrement', 'A'), 0, 2, 'w', -1);
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m), 'MecaStruct:Beam:invalidModel');
m = addSup(baseModel(4), 0, 'encastrement', 'A');
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m, struct('internalMethod', 'foo')), 'MecaStruct:Beam:invalidOption');
tc.verifyError(@() BeamAndTrussSolver.solveBeam(m, struct('hyperMethod', 'bar')), 'MecaStruct:Beam:invalidOption');
mE = baseModel(4);
mE.E = -1;
tc.verifyError(@() BeamAndTrussSolver.solveBeam(mE), 'MecaStruct:Beam:invalidModel');
end

function testNormalizationAndDefaults(tc)
m = struct('L', 2);
m.supports = struct('pos', {0, 2}, 'type', {'Pivot', 'appui simple'});
m.pointLoads = struct('pos', 1, 'Fy', -100);
m.pointMoments = [];
m.distLoads = [];
sol = BeamAndTrussSolver.solveBeam(m, struct('useSymbolic', false));
mdl = sol.model;
for f = {'E', 'G', 'S', 'Iz', 'Iy', 'Ix', 'ky', 'kz'}
    tc.verifyTrue(isfield(mdl, f{1}) && isscalar(mdl.(f{1})) && mdl.(f{1}) > 0, f{1});
end
tc.verifyEqual({mdl.supports.name}, {'A', 'B'});
tc.verifyEqual({mdl.supports.type}, {'pivot', 'appui_simple'});
tc.verifyEqual([mdl.pointLoads.Fx mdl.pointLoads.Fz], [0 0]);
tc.verifyEqual(mdl.pointLoads.name, 'F1');
tc.verifyTrue(isstruct(mdl.pointMoments) && isempty(mdl.pointMoments));
tc.verifyTrue(all(isfield(mdl.pointMoments, {'pos', 'Mx', 'My', 'Mz', 'name'})));
tc.verifyTrue(all(isfield(mdl.distLoads, {'a', 'b', 'dir', 'coeffs', 'name'})));
tc.verifyEqual([sol.reactions.Ry], [50 50], 'RelTol', 1e-12);
tc.verifyTrue(any(contains(sol.report, 'non fourni')));
% structure des réactions et des équations (contrat)
tc.verifyEqual(fieldnames(sol.reactions)', {'name', 'pos', 'type', 'Rx', 'Ry', 'Rz', 'Mx', 'My', 'Mz'});
tc.verifyEqual(fieldnames(sol.equations)', {'s1', 's2', 'N', 'N_txt', 'Ty', 'Ty_txt', 'Tz', 'Tz_txt', ...
    'Mt', 'Mt_txt', 'Mfy', 'Mfy_txt', 'Mfz', 'Mfz_txt'});
tc.verifyEqual([sol.equations.s1], sol.breaks(1:end-1));
tc.verifyEqual([sol.equations.s2], sol.breaks(2:end));
for c = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'}
    e = sol.extrema.(c{1});
    tc.verifyEqual(sort(fieldnames(e))', sort({'max', 'sMax', 'min', 'sMin'}));
    pp = sol.(c{1});
    tc.verifyEqual(pp.breaks, sol.breaks);
    tc.verifyTrue(iscell(pp.coefs) && numel(pp.coefs) == numel(pp.breaks) - 1);
end
for f = {'model', 'h', 'isostatic', 'reactions', 'breaks', 'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz', ...
        'internalIntegral', 'methodCheck', 'equations', 'extrema', 'menabrea', 'reactionsMenabrea', ...
        'reactionsIntegration', 'report', 'latex'}
    tc.verifyTrue(isfield(sol, f{1}), f{1});
end
tc.verifyEqual(sort(fieldnames(sol.h))', sort({'axial', 'xy', 'xz', 'torsion', 'total', 'plan2D'}));
% modèle sans aucune liaison ni charge : tout est nul, pas d'erreur
sol0 = BeamAndTrussSolver.solveBeam(struct('L', 1), struct('useSymbolic', false));
tc.verifyEmpty(sol0.reactions);
tc.verifyEqual(sol0.extrema.Mfz.max, 0);
end

function testOptions(tc)
L = 5; q = 1e3;
m = baseModel(L);
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, L, 'appui_simple', 'B');
m = addQ(m, 0, L, 'y', -q);
s1 = BeamAndTrussSolver.solveBeam(m, struct('internalMethod', 'coupures'));
tc.verifyEmpty(s1.internalIntegral);
tc.verifyTrue(isnan(s1.methodCheck));
s2 = BeamAndTrussSolver.solveBeam(m, struct('internalMethod', 'integrale', 'useSymbolic', false));
tc.verifyEqual(s2.Mfz, s2.internalIntegral.Mfz);
tc.verifyEqual(BeamAndTrussSolver.ppEval(s2.Mfz, 0), -q*L^2/8, 'RelTol', 1e-12);
tc.verifyTrue(isnan(s2.methodCheck));
s3 = BeamAndTrussSolver.solveBeam(m, struct('hyperMethod', 'menabrea', 'useSymbolic', false));
tc.verifyEmpty(s3.reactionsIntegration);
tc.verifyNotEmpty(s3.reactionsMenabrea);
tc.verifyNotEmpty(s3.menabrea);
tc.verifyTrue(isnan(s3.hyperCheck));
s4 = BeamAndTrussSolver.solveBeam(m, struct('hyperMethod', 'integration', 'useSymbolic', false));
tc.verifyEmpty(s4.reactionsMenabrea);
tc.verifyEmpty(s4.menabrea);
tc.verifyEqual(s4.reactions(2).Ry, 3*q*L/8, 'RelTol', 1e-10);
fast = struct('internalMethod', 'coupures', 'hyperMethod', 'menabrea', 'useSymbolic', false);
s5 = BeamAndTrussSolver.solveBeam(m, fast);
tc.verifyEqual(s5.reactions(2).Ry, 3*q*L/8, 'RelTol', 1e-12);
tc.verifyEqual(s5.Mfz, s1.Mfz);
end

function testFastPathPerformance(tc)
m = baseModel(6);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, 3, 'appui_simple', 'B');
m = addSup(m, 6, 'appui_simple', 'C');
m = addF(m, 1, 0, -1000, 0);
m = addF(m, 2, 0, -2000, 0);
m = addF(m, 4, 0, -1500, 0);
m = addF(m, 5, 0, -500, 0);
fast = struct('internalMethod', 'coupures', 'hyperMethod', 'menabrea', 'useSymbolic', false);
for k = 1:3
    BeamAndTrussSolver.solveBeam(m, fast);
end
t = zeros(1, 15);
for k = 1:15
    t0 = tic;
    sol = BeamAndTrussSolver.solveBeam(m, fast);
    t(k) = toc(t0);
end
tc.verifyLessThan(median(t), 0.020, sprintf('chemin rapide trop lent : %.1f ms', 1000*median(t)));
tc.verifyEqual(sum([sol.reactions.Ry]), 5000, 'RelTol', 1e-12);
end

function testReportAndLatexFormat(tc)
sols = {};
models = mixedModels();
for k = 1:numel(models)
    sols{end+1} = BeamAndTrussSolver.solveBeam(models{k}, struct('useSymbolic', false)); %#ok<AGROW>
end
forbidden = {'\iint', '\iiint', '\implies', '\text{', '\dfrac', '\tfrac', '\boldsymbol', '\geqslant', ...
    '\leqslant', 'pmatrix', 'bmatrix', '{align', '{cases'};
for k = 1:numel(sols)
    s = sols{k};
    tc.verifyTrue(iscell(s.report) && size(s.report, 2) == 1 && all(cellfun(@ischar, s.report)));
    tc.verifyTrue(iscell(s.latex) && all(cellfun(@ischar, s.latex)));
    strs = [s.latex(:); {s.equations.N}'; {s.equations.Ty}'; {s.equations.Tz}'; {s.equations.Mt}'; ...
        {s.equations.Mfy}'; {s.equations.Mfz}'];
    for i = 1:numel(strs)
        str = strs{i};
        tc.verifyTrue(startsWith(str, '$') && endsWith(str, '$'), str);
        tc.verifyLessThan(numel(str), 1000);
        tc.verifyTrue(all(double(str) < 128), ['caractère non ASCII : ' str]);
        for f = 1:numel(forbidden)
            tc.verifyEmpty(strfind(str, forbidden{f}), ['commande interdite dans ' str]);
        end
    end
end
end

function testLatexRendersWithoutWarning(tc)
models = mixedModels();
strs = {};
for k = 1:numel(models)
    s = BeamAndTrussSolver.solveBeam(models{k}, struct('useSymbolic', false));
    strs = [strs; s.latex(:); {s.equations.Mfz}'; {s.equations.Mfy}'; {s.equations.Ty}'; {s.equations.N}']; %#ok<AGROW>
end
t = BeamAndTrussSolver.solveTruss(triangleTruss(1000));
strs = [strs; t.latex(:)];
strs = unique(strs, 'stable');
verifyLatexRenders(tc, strs);
end

%% =====================================================================
%%                            TREILLIS
%% =====================================================================

function testTrussTriangleIsostatic(tc)
P = 1000;
tr = triangleTruss(P);
t = BeamAndTrussSolver.solveTruss(tr);
tc.verifyEqual(t.dim, 2);
tc.verifyEqual(t.h, 0);
tc.verifyTrue(t.isostatic);
tc.verifyFalse(t.mechanism);
% résolution à la main : N_AC = N_BC = -P√13/6, N_AB = P/3
Nhand = [P/3; -P*sqrt(13)/6; -P*sqrt(13)/6];
tc.verifyEqual(t.N, Nhand, 'RelTol', 1e-12);
tc.verifyEqual(t.Njoints, Nhand, 'RelTol', 1e-12);
tc.verifyEqual(t.Nstiffness, Nhand, 'RelTol', 1e-10);
tc.verifyEqual(t.reactions, [0 P/2; 0 P/2; 0 0], 'AbsTol', 1e-9);
tc.verifyEqual(t.nature, {'Traction'; 'Compression'; 'Compression'});
tc.verifyEqual(t.L0, [4; sqrt(13); sqrt(13)], 'RelTol', 1e-14);
tc.verifyEqual(t.sigma, Nhand / 1e-4, 'RelTol', 1e-12);
tc.verifyEqual(t.dL, Nhand .* t.L0 / (210e9 * 1e-4), 'RelTol', 1e-12);
tc.verifySize(t.A, [6 6]);
% Clapeyron : travail de P = énergie de déformation
U = sum(t.N.^2 .* t.L0 / (210e9 * 1e-4)) / 2;
tc.verifyEqual(0.5 * P * (-t.displacements(3, 2)), U, 'RelTol', 1e-10);
tc.verifyEqual(t.displacements(1, :), [0 0]);
tc.verifyEqual(t.displacements(2, 2), 0);
T = t.table;
tc.verifyClass(T, 'table');
tc.verifyEqual(T.Properties.VariableNames, {'Barre', 'Noeuds', 'L_m', 'N_N', 'Nature', 'Sigma_Pa', 'dL_m'});
tc.verifyEqual(height(T), 3);
tc.verifyEqual(string(T.Noeuds(2)), "A-C");
tc.verifyTrue(iscell(t.report) && size(t.report, 2) == 1);
tc.verifyTrue(contains(t.methodUsed, 'nœuds'));
end

function testTrussHyperstaticThreeBars(tc)
P = 2e4; a = 1.5; H = 2;
tr.nodes = [-a H; 0 H; a H; 0 0];
tr.bars = [1 4; 2 4; 3 4];
tr.E = 200e9;
tr.S = 3e-4;
tr.supports = logical([1 1; 1 1; 1 1; 0 0]);
tr.loads = [0 0; 0 0; 0 0; 0 -P];
tr.names = {'A'; 'B'; 'C'; 'D'};
t = BeamAndTrussSolver.solveTruss(tr);
tc.verifyEqual(t.h, 1);
tc.verifyFalse(t.isostatic);
tc.verifyFalse(t.mechanism);
tc.verifyEmpty(t.Njoints);
ca = H / sqrt(a^2 + H^2);
N2 = P / (1 + 2*ca^3);
N1 = P * ca^2 / (1 + 2*ca^3);
tc.verifyEqual(t.N, [N1; N2; N1], 'RelTol', 1e-10);
tc.verifyEqual(t.Nstiffness, t.N);
tc.verifyEqual(sum(t.reactions(:, 2)), P, 'RelTol', 1e-12);
tc.verifyEqual(t.nature, {'Traction'; 'Traction'; 'Traction'});
% équilibre nodal vérifié avec la matrice des nœuds [A]{N,R} = {-F}
st = tr.supports.';
Rb = reshape(t.reactions.', [], 1);
Rb = Rb(st(:));
F = reshape(tr.loads.', [], 1);
tc.verifyLessThan(norm(t.A * [t.N; Rb] + F, Inf), 1e-8 * P);
tc.verifyEqual(t.methodUsed, 'méthode des rigidités');
end

function testTrussHyperstaticBraced(tc)
% carré à deux diagonales (h = 1) : équilibre et Clapeyron
P = 5e3;
tr.nodes = [0 0; 2 0; 2 2; 0 2];
tr.bars = [1 2; 2 3; 3 4; 4 1; 1 3; 2 4];
tr.E = 210e9;
tr.S = [2e-4; 2e-4; 2e-4; 2e-4; 1e-4; 1e-4];
tr.supports = logical([1 1; 0 1; 0 0; 0 0]);
tr.loads = [0 0; 0 0; P 0; 0 -P];
t = BeamAndTrussSolver.solveTruss(tr);
tc.verifyEqual(t.h, 1);
U = sum(t.N.^2 .* t.L0 ./ (tr.E * tr.S)) / 2;
W = 0.5 * sum(sum(tr.loads .* t.displacements));
tc.verifyEqual(W, U, 'RelTol', 1e-10);
st = tr.supports.';
Rb = reshape(t.reactions.', [], 1);
Rb = Rb(st(:));
F = reshape(tr.loads.', [], 1);
tc.verifyLessThan(norm(t.A * [t.N; Rb] + F, Inf), 1e-8 * P);
tc.verifyEqual(t.dL, t.N .* t.L0 ./ (tr.E * tr.S), 'RelTol', 1e-12);
end

function testTruss3DTripod(tc)
P = 9e3; R = 1; H = 2;
tr.nodes = [R 0 0; -R/2 R*sqrt(3)/2 0; -R/2 -R*sqrt(3)/2 0; 0 0 H];
tr.bars = [1 4; 2 4; 3 4];
tr.E = 210e9;
tr.S = 1e-4;
tr.supports = logical([1 1 1; 1 1 1; 1 1 1; 0 0 0]);
tr.loads = [zeros(3, 3); 0 0 -P];
t = BeamAndTrussSolver.solveTruss(tr);
tc.verifyEqual(t.dim, 3);
tc.verifyEqual(t.h, 0);
tc.verifyTrue(t.isostatic);
cb = H / sqrt(R^2 + H^2);
tc.verifyEqual(t.N, -P/(3*cb) * ones(3, 1), 'RelTol', 1e-12);
tc.verifyEqual(t.reactions(1:3, 3), P/3 * ones(3, 1), 'RelTol', 1e-12);
tc.verifyEqual(t.Nstiffness, t.Njoints, 'RelTol', 1e-10);
% charge dissymétrique : nœuds ≡ rigidités
tr.loads = [zeros(3, 3); 1e3 -2e3 -P];
t2 = BeamAndTrussSolver.solveTruss(tr);
tc.verifyEqual(t2.Nstiffness, t2.Njoints, 'RelTol', 1e-9);
tc.verifyEqual(sum(t2.reactions, 1), -tr.loads(4, :), 'RelTol', 1e-10);
tc.verifySize(t2.displacements, [4 3]);
end

function testTrussMechanism(tc)
tr.nodes = [0 0; 1 0; 1 1; 0 1];
tr.bars = [1 2; 2 3; 3 4; 4 1];
tr.E = 210e9;
tr.S = 1e-4;
tr.supports = logical([1 1; 0 1; 0 0; 0 0]);
tr.loads = [0 0; 0 0; 1000 0; 0 0];
tc.verifyError(@() BeamAndTrussSolver.solveTruss(tr), 'MecaStruct:Truss:mechanism');
tr.loads = zeros(4, 2);
t = BeamAndTrussSolver.solveTruss(tr);
tc.verifyTrue(t.mechanism);
tc.verifyFalse(t.isostatic);
tc.verifyEqual(t.N, zeros(4, 1), 'AbsTol', 1e-12);
tc.verifyEqual(t.nature, repmat({'Nul'}, 4, 1));
end

function testTrussInvalidInputs(tc)
tr = triangleTruss(1000);
bad = tr;
bad.bars = [1 2; 2 5];
tc.verifyError(@() BeamAndTrussSolver.solveTruss(bad), 'MecaStruct:Truss:invalidModel');
bad = tr;
bad.supports = true(2, 2);
tc.verifyError(@() BeamAndTrussSolver.solveTruss(bad), 'MecaStruct:Truss:invalidModel');
bad = tr;
bad.nodes(3, :) = bad.nodes(1, :);
bad.bars = [1 2; 1 3; 2 3];
tc.verifyError(@() BeamAndTrussSolver.solveTruss(bad), 'MecaStruct:Truss:invalidModel');
bad = tr;
bad.S = [1 2];
tc.verifyError(@() BeamAndTrussSolver.solveTruss(bad), 'MecaStruct:Truss:invalidModel');
tc.verifyError(@() BeamAndTrussSolver.solveTruss(42), 'MecaStruct:Truss:invalidModel');
% noms par défaut et charges absentes
ok = rmfield(tr, 'loads');
t = BeamAndTrussSolver.solveTruss(ok);
tc.verifyEqual(t.N, zeros(3, 1));
tc.verifyEqual(t.names, {'A'; 'B'; 'C'});
end

%% =====================================================================
%%                       FONCTIONS D'AIDE
%% =====================================================================

function m = baseModel(L)
m = struct('L', L, 'E', 210e9, 'G', 80e9, 'S', 2e-3, 'Iz', 8e-6, 'Iy', 3e-6, 'Ix', 1e-6, 'ky', 1, 'kz', 1);
m.supports = struct('pos', {}, 'type', {}, 'name', {});
m.pointLoads = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
m.pointMoments = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
m.distLoads = struct('a', {}, 'b', {}, 'dir', {}, 'coeffs', {}, 'name', {});
end

function m = addSup(m, pos, type, name)
m.supports(end+1) = struct('pos', pos, 'type', type, 'name', name);
end

function m = addF(m, pos, Fx, Fy, Fz)
m.pointLoads(end+1) = struct('pos', pos, 'Fx', Fx, 'Fy', Fy, 'Fz', Fz, ...
    'name', sprintf('F%d', numel(m.pointLoads) + 1));
end

function m = addC(m, pos, Mx, My, Mz)
m.pointMoments(end+1) = struct('pos', pos, 'Mx', Mx, 'My', My, 'Mz', Mz, ...
    'name', sprintf('C%d', numel(m.pointMoments) + 1));
end

function m = addQ(m, a, b, dir, coeffs)
m.distLoads(end+1) = struct('a', a, 'b', b, 'dir', dir, 'coeffs', coeffs, ...
    'name', sprintf('q%d', numel(m.distLoads) + 1));
end

function [v, res] = deflectionAt(sol, EI, conds, sEval)
% Flèche par double intégration (ppIntegrate) : E I v'' = Mfz, v = I2 + C1 + C2 s.
% conds : lignes [s, type] avec type 0 : v(s) = 0, type 1 : v'(s) = 0.
I1 = BeamAndTrussSolver.ppIntegrate(BeamAndTrussSolver.ppScale(sol.Mfz, 1/EI), 0);
I2 = BeamAndTrussSolver.ppIntegrate(I1, 0);
nc = size(conds, 1);
A = zeros(nc, 2);
b = zeros(nc, 1);
for k = 1:nc
    s = conds(k, 1);
    if conds(k, 2) == 0
        A(k, :) = [1, s];
        b(k) = -BeamAndTrussSolver.ppEval(I2, s);
    else
        A(k, :) = [0, 1];
        b(k) = -BeamAndTrussSolver.ppEval(I1, s);
    end
end
C = A \ b;
v = BeamAndTrussSolver.ppEval(I2, sEval) + C(1) + C(2) * sEval;
scale = max(abs(BeamAndTrussSolver.ppEval(I2, linspace(0, sol.model.L, 21))));
res = norm(A * C - b, Inf) / max(scale, realmin);
end

function tr = triangleTruss(P)
tr = struct('nodes', [0 0; 4 0; 2 3], 'bars', [1 2; 1 3; 2 3], 'E', 210e9, 'S', 1e-4, ...
    'supports', logical([1 1; 0 1; 0 0]), 'loads', [0 0; 0 0; 0 -P]);
end

function models = mixedModels()
% Modèles variés (3D, charges polynomiales, couples) pour les comparaisons.
models = {};
% 1 : isostatique 3D complet (console)
m = baseModel(5);
m = addSup(m, 0, 'encastrement', 'A');
m = addF(m, 1.5, 300, -2000, 800);
m = addF(m, 5, -100, 500, -400);
m = addC(m, 2.5, 150, -600, 900);
m = addQ(m, 1, 4, 'y', [100, -400, -1500]);
m = addQ(m, 0, 3, 'z', [200, -300]);
m = addQ(m, 2, 5, 'x', 50);
models{end+1} = m;
% 2 : deux travées, charges ponctuelles, couple et charge partielle
m = baseModel(8);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, 3, 'appui_simple', 'B');
m = addSup(m, 8, 'appui_simple', 'C');
m = addF(m, 1, 0, -4000, 0);
m = addF(m, 5.5, 0, -2500, 1000);
m = addC(m, 6, 0, 0, 3000);
m = addQ(m, 4, 7, 'y', [-500, -1000]);
models{end+1} = m;
% 3 : bi-encastrée, chargement 3D (hyperstatique dans les 4 sous-problèmes)
m = baseModel(6);
m = addSup(m, 0, 'encastrement', 'A');
m = addSup(m, 6, 'encastrement', 'B');
m = addF(m, 2, 1200, -3000, 1500);
m = addC(m, 4, 700, 400, -800);
m = addQ(m, 0, 6, 'y', [-200, -1000]);
m = addQ(m, 1, 5, 'z', 600);
m = addQ(m, 3, 6, 'x', [100, 0]);
models{end+1} = m;
% 4 : quatre appuis dont un encastrement intermédiaire
m = baseModel(10);
m = addSup(m, 0, 'rotule', 'A');
m = addSup(m, 3, 'appui_simple', 'B');
m = addSup(m, 6, 'encastrement', 'C');
m = addSup(m, 10, 'pivot_glissant', 'D');
m = addF(m, 1.5, 0, -5000, -2000);
m = addF(m, 8, 2000, -1000, 0);
m = addQ(m, 0, 10, 'y', -800);
m = addQ(m, 6, 10, 'z', [300, 0, -100]);
m = addC(m, 9, 250, 0, 0);
models{end+1} = m;
% 5 : isostatique, charge parabolique en ξ
m = baseModel(4);
m = addSup(m, 0, 'pivot', 'A');
m = addSup(m, 4, 'appui_simple', 'B');
m = addQ(m, 0.5, 3.5, 'y', [-1000, 3000, -500]);
models{end+1} = m;
end

function verifyLatexRenders(tc, strs)
% Rendu dans une figure invisible : aucun avertissement de l'interpréteur LaTeX.
f = figure('Visible', 'off');
cleaner = onCleanup(@() close(f));
ax = axes(f);
ws = warning('off', 'MATLAB:handle_graphics:exceptions:SceneNode');
restore = onCleanup(@() warning(ws));
% contrôle du mécanisme de détection
lastwarn('');
h = text(ax, 0.1, 0.5, '$\dfrac{1}{2}$', 'Interpreter', 'latex');
drawnow;
msg = lastwarn;
delete(h);
tc.assertNotEmpty(msg, 'La détection des erreurs LaTeX ne fonctionne pas dans cet environnement.');
for i = 1:numel(strs)
    lastwarn('');
    h = text(ax, 0.1, 0.5, strs{i}, 'Interpreter', 'latex');
    drawnow;
    [msg, id] = lastwarn;
    tc.verifyEmpty(msg, sprintf('LaTeX invalide (%s) : %s', id, strs{i}));
    delete(h);
end
clear restore cleaner
end
