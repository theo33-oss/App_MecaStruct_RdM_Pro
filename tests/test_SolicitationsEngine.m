function tests = test_SolicitationsEngine
%TEST_SOLICITATIONSENGINE Tests unitaires du module SolicitationsEngine (§4 et §9 du contrat).
%   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
tests = functiontests(localfunctions);
end

%% ------------------------------------------------------------------ flexion déviée (Iyz ≠ 0)

function testDeflectionIyz(tc)
% Cornière 100×100×10 sur deux appuis, charge uniforme selon y : la flèche a une composante w
% et le vecteur (v, w) est perpendiculaire à l'axe neutre donné par bendingStress.
L = 4; q = 10e3; E = 210e9;
sec = struct('type', 'L', 'h', 0.1, 'b', 0.1, 't', 0.01);
P = GeometryEngine.analytical(sec);
m = beamModel(L, [0 L], {'pivot', 'appui_simple'});
m.Iz = P.Iz; m.Iy = P.Iy; m.Iyz = P.Iyz; m.S = P.S;
m.distLoads = struct('a', 0, 'b', L, 'dir', 'y', 'coeffs', -q, 'name', 'q');
sol = BeamAndTrussSolver.solveBeam(m);
o = struct('includeShear', false);
dv = SolicitationsEngine.deflection(m, sol, setfield(o, 'plane', 'xy')); %#ok<SFLD>
dw = SolicitationsEngine.deflection(m, sol, setfield(o, 'plane', 'xz')); %#ok<SFLD>
dt = P.Iz*P.Iy - P.Iyz^2;
f0 = 5*q*L^4/(384*E);
checkAgree(tc, dv, f0*P.Iy/dt, 1e-6);
checkAgree(tc, dw, f0*abs(P.Iyz)/dt, 1e-6);
b = SolicitationsEngine.bendingStress(struct('sec', sec, 'Mfz', q*L^2/8, 'Re', 235e6));
verifyEqual(tc, dw.integration.fmax/dv.integration.fmax, abs(b.coefs(3)/b.coefs(2)), 'RelTol', 1e-9);
% énergie de flexion : ∫ Mfz²·Iy/(2E·det) ds
U = SolicitationsEngine.strainEnergy(m, sol);
verifyEqual(tc, U.UMfz + U.UMfy, q^2*L^5/120*P.Iy/(2*E*dt), 'RelTol', 1e-9);
end

%% ------------------------------------------------------------------ utilitaires

function m = beamModel(L, supPos, supTypes)
% Poutre acier E = 210 GPa, Iz = 8e-6, Iy = 3e-6, S = 2e-3, ky = kz = 5/6.
m = struct('L', L, 'E', 210e9, 'G', 80e9, 'S', 2e-3, 'Iz', 8e-6, 'Iy', 3e-6, 'Ix', 1e-6, ...
    'ky', 5/6, 'kz', 5/6);
names = {'A', 'B', 'C'};
m.supports = struct('pos', num2cell(supPos), 'type', supTypes, 'name', names(1:numel(supPos)));
m.pointLoads = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
m.pointMoments = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
m.distLoads = struct('a', {}, 'b', {}, 'dir', {}, 'coeffs', {}, 'name', {});
end

function checkLatex(tc, c)
% Rendu de chaque chaîne LaTeX dans une figure invisible sans avertissement.
f = figure('Visible', 'off');
cl = onCleanup(@() close(f));
ax = axes(f);
for k = 1:numel(c)
    lastwarn('');
    text(ax, 0, 0, c{k}, 'Interpreter', 'latex');
    drawnow;
    [msg, ~] = lastwarn;
    verifyEmpty(tc, msg, sprintf('LaTeX invalide : %s', c{k}));
    verifyTrue(tc, all(double(c{k}) < 128), sprintf('Caractère non ASCII : %s', c{k}));
end
end

function checkAgree(tc, d, fref, tol)
% Les 4 méthodes donnent la même flèche (flexion seule) que la référence.
verifyEqual(tc, d.integration.fmax, fref, 'RelTol', tol);
verifyEqual(tc, d.aires.fmax, fref, 'RelTol', tol);
verifyEqual(tc, d.castigliano.fmaxBending, fref, 'RelTol', tol);
verifyEqual(tc, d.mohr.fmax, fref, 'RelTol', tol);
verifyLessThan(tc, d.integration.residual, 1e-8);
end

%% ------------------------------------------------------------------ traction

function testTractionThreeMethods(tc)
p = struct('N', 5e4, 'S0', 2e-4, 'L0', 1.5, 'E', 2e11, 'nu', 0.3, 'Re', 355e6, 's', 2);
r = SolicitationsEngine.traction(p);
ref = 5e4*1.5/(2e11*2e-4);
verifyEqual(tc, r.dL.analytique, ref, 'RelTol', 1e-12);
verifyEqual(tc, r.dL.integrale, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.dL.energetique, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.sigmaNom, 2.5e8, 'RelTol', 1e-12);
verifyEqual(tc, r.sigmaAdm, 177.5e6, 'RelTol', 1e-12);
verifyFalse(tc, r.okResistance);
verifyEqual(tc, r.K, 2e11*2e-4/1.5, 'RelTol', 1e-12);
verifyEqual(tc, r.U, 0.5*5e4*ref, 'RelTol', 1e-9);   % Clapeyron
verifyEqual(tc, r.epsyy, -0.3*r.epsxx, 'RelTol', 1e-12);
verifyEqual(tc, r.dVsurV, 0.4*r.sigmaNom/2e11, 'RelTol', 1e-12);
verifyEqual(tc, r.dVsurV, r.epsxx + r.epsyy + r.epszz, 'RelTol', 1e-12);
checkLatex(tc, r.latex);
verifyTrue(tc, iscell(r.report) && iscolumn(r.report));
end

function testTractionConicalBar(tc)
F = 1e4; L = 0.8; E = 2e11; d1 = 0.02; d2 = 0.04;
p = struct('N', F, 'S0', pi*d1^2/4, 'L0', L, 'E', E, 'Re', 235e6, ...
    'Sfun', @(x) pi/4*(d1 + (d2 - d1)*x/L).^2);
r = SolicitationsEngine.traction(p);
ref = 4*F*L/(pi*E*d1*d2);
verifyEqual(tc, r.dL.integrale, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.dL.energetique, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.dL.analytique, F*L/(E*pi*d1^2/4), 'RelTol', 1e-12);
end

function testTractionNumericFallback(tc)
% interp1 n'accepte pas les sym : repli integral + différence centrée.
F = 1e4; L = 0.8; E = 2e11; d1 = 0.02; d2 = 0.04;
xs = linspace(0, L, 2001);
p = struct('N', F, 'S0', pi*d1^2/4, 'L0', L, 'E', E, 'Re', 235e6, ...
    'Sfun', @(x) interp1(xs, pi/4*(d1 + (d2 - d1)*xs/L).^2, x, 'spline'));
r = SolicitationsEngine.traction(p);
verifyEqual(tc, r.methodUsed, 'numérique');
ref = 4*F*L/(pi*E*d1*d2);
verifyEqual(tc, r.dL.integrale, ref, 'RelTol', 1e-7);
verifyEqual(tc, r.dL.energetique, r.dL.integrale, 'RelTol', 1e-9);
end

function testTractionThermal(tc)
p = struct('N', 0, 'S0', 1e-4, 'L0', 2, 'E', 2e11, 'nu', 0.3, 'alpha', 12e-6, 'dT', 50, ...
    'Re', 235e6, 'dLmax', 2e-3);
r = SolicitationsEngine.traction(p);
ref = 12e-6*50*2;
verifyEqual(tc, r.dL.analytique, ref, 'RelTol', 1e-12);
verifyEqual(tc, r.dL.integrale, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.dL.energetique, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.epsxx, 6e-4, 'RelTol', 1e-12);
verifyEqual(tc, r.epsyy, 6e-4, 'RelTol', 1e-12);
verifyEqual(tc, r.dVsurV, 18e-4, 'RelTol', 1e-12);
verifyTrue(tc, r.okRigidite);
% Thermique variable : ΔT(x) = 100 x/L → ΔL = α·50·L
p.dTfun = @(x) 100*x/2;
r = SolicitationsEngine.traction(p);
verifyEqual(tc, r.dL.integrale, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.dL.energetique, ref, 'RelTol', 1e-9);
end

function testTractionKtAndErrors(tc)
p = struct('N', -1e4, 'S0', 1e-4, 'L0', 1, 'E', 2e11, 'Kt', 2.5, 'Re', 300e6);
r = SolicitationsEngine.traction(p);
verifyEqual(tc, r.sigmaMax, -2.5e8, 'RelTol', 1e-12);
verifyTrue(tc, r.okResistance);
verifyLessThan(tc, r.dL.analytique, 0);
verifyError(tc, @() SolicitationsEngine.traction(rmfield(p, 'S0')), 'MecaStruct:SolicitationsEngine:missingField');
p.E = -1;
verifyError(tc, @() SolicitationsEngine.traction(p), 'MecaStruct:SolicitationsEngine:invalidInput');
end

%% ------------------------------------------------------------------ cisaillement, matage

function testShear(tc)
p = struct('T', 1e4, 'S', 1e-4, 'k', 1.5, 'Re', 240e6, 's', 2, 'G', 80e9);
r = SolicitationsEngine.shear(p);
verifyEqual(tc, r.tauMoy, 1e8, 'RelTol', 1e-12);
verifyEqual(tc, r.tauMax, 1.5e8, 'RelTol', 1e-12);
verifyEqual(tc, r.tauE, 120e6, 'RelTol', 1e-12);
verifyEqual(tc, r.tauAdm, 60e6, 'RelTol', 1e-12);
verifyFalse(tc, r.ok);
verifyEqual(tc, r.gamma, 1e8/80e9, 'RelTol', 1e-12);
p.criterion = 'VonMises';
r = SolicitationsEngine.shear(p);
verifyEqual(tc, r.tauE, 240e6/sqrt(3), 'RelTol', 1e-12);
p.tauE = 200e6;
r = SolicitationsEngine.shear(p);
verifyEqual(tc, r.tauE, 200e6);
checkLatex(tc, r.latex);
p = rmfield(p, 'tauE');
p.criterion = 'Rankine';
verifyError(tc, @() SolicitationsEngine.shear(p), 'MecaStruct:SolicitationsEngine:invalidInput');
end

function testJourawskiRectangle(tc)
sec = struct('type', 'rectangle', 'b', 0.1, 'h', 0.2);
T = 3e4;
prof = SolicitationsEngine.jourawski(sec, T, 201);
S = 0.02;
verifyEqual(tc, prof.tauMax, 1.5*T/S, 'RelTol', 1e-9);
verifyEqual(tc, prof.yAtMax, 0, 'AbsTol', 1e-12);
verifyEqual(tc, prof.tauMoy, T/S, 'RelTol', 1e-12);
verifyEqual(tc, prof.kNum, 1.5, 'RelTol', 1e-9);
verifyEqual(tc, prof.tau, prof.tauParabola, 'AbsTol', 1e-9*prof.tauMax);
verifyEqual(tc, prof.Iz, 0.1*0.2^3/12, 'RelTol', 1e-12);
verifyEqual(tc, [prof.tau(1) prof.tau(end)], [0 0], 'AbsTol', 1e-6);
verifyEqual(tc, numel(prof.y), 201);
checkLatex(tc, prof.latex);
end

function testJourawskiI(tc)
h = 0.3; b = 0.15; tw = 0.008; tf = 0.012;
sec = struct('type', 'I', 'h', h, 'b', b, 'tw', tw, 'tf', tf);
T = 5e4;
prof = SolicitationsEngine.jourawski(sec, T, 301);
Iz = b*h^3/12 - (b - tw)*(h - 2*tf)^3/12;
Q0 = b*tf*(h/2 - tf/2) + tw*(h/2 - tf)^2/2;
verifyEqual(tc, prof.Iz, Iz, 'RelTol', 1e-10);
verifyEqual(tc, prof.tauMax, T*Q0/(Iz*tw), 'RelTol', 1e-9);
verifyEqual(tc, prof.yAtMax, 0, 'AbsTol', 1e-12);
verifyTrue(tc, all(isnan(prof.tauParabola)));
% Âme : τ ≈ T/S_âme à quelques % près (formule approchée du cours)
verifyEqual(tc, prof.tauMax, T/(tw*(h - 2*tf)), 'RelTol', 0.15);
end

function testBearing(tc)
r = SolicitationsEngine.bearing(struct('F', 2e4, 'Smatee', 4e-4, 'Padm', 40e6));
verifyEqual(tc, r.P, 5e7, 'RelTol', 1e-12);
verifyFalse(tc, r.ok);
verifyEqual(tc, r.SminRequired, 5e-4, 'RelTol', 1e-12);
checkLatex(tc, r.latex);
end

function testKeyDesign(tc)
C = 300; D = 0.04; a = 0.012; b = 0.008; Padm = 60e6; Re = 300e6;
p = struct('C', C, 'D', D, 'a', a, 'b', b, 'Padm', Padm, 'Re', Re, 's', 1.5, 'L', 0.05);
r = SolicitationsEngine.keyDesign(p);
tadm = Re/2/1.5;
verifyEqual(tc, r.F, 2*C/D, 'RelTol', 1e-12);
verifyEqual(tc, r.LminMatage, 4*C/(D*b*Padm), 'RelTol', 1e-12);
verifyEqual(tc, r.LminCis, 2*C/(a*D*tadm), 'RelTol', 1e-12);
verifyEqual(tc, r.Lmin, max(r.LminMatage, r.LminCis), 'RelTol', 1e-12);
verifyEqual(tc, r.P, 4*C/(D*b*0.05), 'RelTol', 1e-12);
verifyEqual(tc, r.tau, 2*C/(a*0.05*D), 'RelTol', 1e-12);
verifyFalse(tc, r.okP);   % P = 75 MPa > 60 MPa
verifyTrue(tc, r.okTau);
% Au minimum de matage, P = Padm exactement
p.L = r.LminMatage;
r2 = SolicitationsEngine.keyDesign(p);
verifyEqual(tc, r2.P, Padm, 'RelTol', 1e-12);
checkLatex(tc, r2.latex);
r3 = SolicitationsEngine.keyDesign(rmfield(p, 'L'));
verifyFalse(tc, isfield(r3, 'P'));
end

function testPinDesign(tc)
F = 5e3; d = 0.008; e = 0.01; Padm = 100e6;
p = struct('F', F, 'd', d, 'e', e, 'Padm', Padm, 'Re', 400e6, 'nShear', 2);
r = SolicitationsEngine.pinDesign(p);
verifyEqual(tc, r.P, 2*F/(d*e), 'RelTol', 1e-12);
verifyEqual(tc, r.tau, 4*F/(2*pi*d^2), 'RelTol', 1e-12);
verifyEqual(tc, r.eMin, 2*F/(d*Padm), 'RelTol', 1e-12);
verifyEqual(tc, r.dMin, max(sqrt(4*F/(2*pi*200e6)), 2*F/(e*Padm)), 'RelTol', 1e-12);
verifyTrue(tc, r.okTau);
verifyFalse(tc, r.okP);
checkLatex(tc, r.latex);
end

%% ------------------------------------------------------------------ torsion

function testTorsionSolid(tc)
Mt = 500; D = 0.04; G = 80e9; L = 1.2;
p = struct('Mt', Mt, 'D', D, 'G', G, 'L', L, 'Re', 300e6, 'thetaAdm', 0.01);
r = SolicitationsEngine.torsion(p);
Ix = pi*D^4/32;
verifyEqual(tc, r.Ix, Ix, 'RelTol', 1e-12);
verifyEqual(tc, r.tauMax, 16*Mt/(pi*D^3), 'RelTol', 1e-12);
verifyEqual(tc, r.theta, Mt/(G*Ix), 'RelTol', 1e-12);
ref = Mt*L/(G*Ix);
verifyEqual(tc, r.phi.analytique, ref, 'RelTol', 1e-12);
verifyEqual(tc, r.phi.integrale, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.phi.energetique, ref, 'RelTol', 1e-9);
verifyEqual(tc, r.U, 0.5*Mt*ref, 'RelTol', 1e-9);
verifyEqual(tc, r.Ktorsion, G*Ix/L, 'RelTol', 1e-12);
verifyEqual(tc, r.tauProfile(end), r.tauMaxNom, 'RelTol', 1e-12);
verifyEqual(tc, r.tauProfile(1), 0, 'AbsTol', 1e-6);
verifyTrue(tc, r.okResistance);
verifyFalse(tc, r.okRigidite);
checkLatex(tc, r.latex);
end

function testTorsionHollowAndVariable(tc)
Mt = 800; D = 0.05; d = 0.04; G = 80e9; L = 2;
p = struct('Mt', Mt, 'D', D, 'd', d, 'G', G, 'L', L, 'Re', 300e6, 'Kt', 1.4, 'criterion', 'VonMises');
r = SolicitationsEngine.torsion(p);
Ix = pi*(D^4 - d^4)/32;
verifyEqual(tc, r.Ix, Ix, 'RelTol', 1e-12);
verifyEqual(tc, r.m, 0.8, 'RelTol', 1e-12);
verifyEqual(tc, r.tauMaxNom, Mt*D/(2*Ix), 'RelTol', 1e-12);
verifyEqual(tc, r.tauMax, 1.4*Mt*D/(2*Ix), 'RelTol', 1e-12);
verifyEqual(tc, r.tauAdm, 300e6/sqrt(3), 'RelTol', 1e-12);
verifyEqual(tc, r.rProfile([1 end]), [d D]/2, 'RelTol', 1e-12);
verifyEqual(tc, r.phi.integrale, Mt*L/(G*Ix), 'RelTol', 1e-9);
% Moment variable Mt(s) = Mt·s/L → φ = Mt L/(2 G Ix)
p.MtFun = @(s) Mt*s/L;
r = SolicitationsEngine.torsion(p);
verifyEqual(tc, r.phi.integrale, Mt*L/(2*G*Ix), 'RelTol', 1e-9);
verifyEqual(tc, r.phi.energetique, Mt*L/(2*G*Ix), 'RelTol', 1e-9);
p.d = D;
verifyError(tc, @() SolicitationsEngine.torsion(p), 'MecaStruct:SolicitationsEngine:invalidInput');
end

%% ------------------------------------------------------------------ contraintes de flexion

function testBendingDeviatedRectangle(tc)
b = 0.1; h = 0.2;
sec = struct('type', 'rectangle', 'b', b, 'h', h);
Mfz = 2e4; Mfy = 5e3; N = 1e5;
r = SolicitationsEngine.bendingStress(struct('sec', sec, 'N', N, 'Mfz', Mfz, 'Mfy', Mfy, 'Re', 235e6, 'Kt', 1.2));
S = b*h; Wz = b*h^2/6; Wy = h*b^2/6;
verifyFalse(tc, r.usedGeneralFormula);
verifyEqual(tc, r.sigmaMaxTraction, N/S + Mfz/Wz + Mfy/Wy, 'RelTol', 1e-12);
verifyEqual(tc, r.sigmaMaxCompression, N/S - Mfz/Wz - Mfy/Wy, 'RelTol', 1e-12);
verifyEqual(tc, r.locMaxTraction, [-h/2 b/2], 'AbsTol', 1e-12);   % σ = −Mfz y/Iz + Mfy z/Iy
verifyEqual(tc, r.sigmaMaxKt, 1.2*r.sigmaMaxAbs, 'RelTol', 1e-12);
verifyEqual(tc, r.sigmaFun(0, 0), N/S, 'RelTol', 1e-12);
na = r.neutralAxis;
verifyEqual(tc, na.a + na.b*na.points(:, 1) + na.c*na.points(:, 2), [0; 0], 'AbsTol', 1e-6);
verifyEqual(tc, r.sigmaProfile, N/S - Mfz*r.yProfile/(b*h^3/12), 'RelTol', 1e-12);
checkLatex(tc, r.latex);
end

function testBendingComposedPropsOnly(tc)
P = struct('S', 0.02, 'Iz', 0.1*0.2^3/12, 'Iy', 0.2*0.1^3/12, 'vyTop', 0.1, 'vyBot', 0.1, ...
    'vzRight', 0.05, 'vzLeft', 0.05);
r = SolicitationsEngine.bendingStress(struct('P', P, 'N', -2e5, 'Mfz', -1e4, 'Re', 235e6, 's', 1.5));
verifyEqual(tc, r.sigmaMaxCompression, -2e5/0.02 - 1e4/(0.1*0.2^2/6), 'RelTol', 1e-12);
verifyEqual(tc, r.sigmaAdm, 235e6/1.5, 'RelTol', 1e-12);
verifyEqual(tc, r.locMaxCompression(1), -0.1, 'AbsTol', 1e-12);
verifyError(tc, @() SolicitationsEngine.bendingStress(struct('Re', 1e8)), 'MecaStruct:SolicitationsEngine:missingField');
end

function testBendingGeneralFormulaL(tc)
sec = struct('type', 'L', 'h', 0.1, 'b', 0.06, 't', 0.008);
P = GeometryEngine.analytical(sec);
Mfz = 3e3; Mfy = -1e3;
r = SolicitationsEngine.bendingStress(struct('sec', sec, 'Mfz', Mfz, 'Mfy', Mfy, 'Re', 235e6));
verifyTrue(tc, r.usedGeneralFormula);
b = r.coefs(2); c = r.coefs(3);
verifyEqual(tc, b*P.Iz + c*P.Iyz, -Mfz, 'RelTol', 1e-10);
verifyEqual(tc, b*P.Iyz + c*P.Iy, Mfy, 'RelTol', 1e-10);
% Extrema = sommets du contour
out = GeometryEngine.outline(sec);
V = out.outer{1};
s = r.sigmaFun(V(:, 2) - P.yG, V(:, 1) - P.zG);
verifyEqual(tc, r.sigmaMaxTraction, max(s), 'RelTol', 1e-12);
verifyEqual(tc, r.sigmaMaxCompression, min(s), 'RelTol', 1e-12);
checkLatex(tc, r.latex);
end

function testBendingDisk(tc)
D = 0.05;
sec = struct('type', 'disque', 'D', D);
r = SolicitationsEngine.bendingStress(struct('sec', sec, 'Mfz', 300, 'Mfy', 400, 'Re', 235e6));
verifyEqual(tc, r.sigmaMaxAbs, 32*500/(pi*D^3), 'RelTol', 1e-9);
end

%% ------------------------------------------------------------------ déformée : cas d'école

function testDeflectionSimplySupportedPointLoad(tc)
L = 4; P = 1e4;
m = beamModel(L, [0 L], {'appui_simple', 'appui_simple'});
m.pointLoads = struct('pos', L/2, 'Fx', 0, 'Fy', -P, 'Fz', 0, 'name', 'F');
d = SolicitationsEngine.deflection(m, []);
EI = 210e9*8e-6;
fref = P*L^3/(48*EI);
checkAgree(tc, d, fref, 1e-6);
verifyEqual(tc, d.integration.sAtFmax, L/2, 'AbsTol', 1e-9);
verifyEqual(tc, d.aires.sAtFmax, L/2, 'AbsTol', 1e-9);
verifyEqual(tc, BeamAndTrussSolver.ppEval(d.integration.vPP, L/2), -fref, 'RelTol', 1e-9);
verifyEqual(tc, d.integration.alpha(1), -P*L^2/(16*EI), 'RelTol', 1e-9);
verifyEqual(tc, d.aires.alpha(1), -P*L^2/(16*EI), 'RelTol', 1e-9);
verifyEqual(tc, d.aires.v, d.integration.v, 'AbsTol', 1e-9*fref);
verifyEqual(tc, height(d.integration.constants), 2);
verifyTrue(tc, istable(d.comparison) && height(d.comparison) == 5);
verifyEqual(tc, d.plane, 'xy');
checkLatex(tc, d.latex);
checkLatex(tc, cellstr(d.mohr.details{1}.formulaLatex));
end

function testDeflectionCantilever(tc)
L = 2; P = 1e3;
m = beamModel(L, 0, {'encastrement'});
m.pointLoads = struct('pos', L, 'Fx', 0, 'Fy', -P, 'Fz', 0, 'name', 'F');
d = SolicitationsEngine.deflection(m, []);
EI = 210e9*8e-6;
checkAgree(tc, d, P*L^3/(3*EI), 1e-6);
verifyEqual(tc, d.integration.sAtFmax, L, 'AbsTol', 1e-12);
% Contribution du tranchant : P L/(ky G S)
c = d.castigliano;
iL = find(c.s0 == L);
verifyEqual(tc, c.vShear(iL), -P*L/(5/6*80e9*2e-3), 'RelTol', 1e-9);
verifyEqual(tc, c.vTotal(iL), c.vBending(iL) + c.vShear(iL), 'RelTol', 1e-12);
verifyEqual(tc, c.alpha(iL), -P*L^2/(2*EI), 'RelTol', 1e-9);
verifyEqual(tc, c.fmax, P*L^3/(3*EI) + P*L/(5/6*80e9*2e-3), 'RelTol', 1e-9);
% Constantes : E I v = P/6 (s^3 − 3 L s^2) → C1 = C2 = 0
verifyEqual(tc, [d.integration.constants.C1 d.integration.constants.C2], [0 0], 'AbsTol', 1e-9);
% Sans tranchant
d2 = SolicitationsEngine.deflection(m, [], struct('includeShear', false, 'methods', {{'castigliano'}}));
verifyEqual(tc, d2.castigliano.vShear, zeros(size(d2.castigliano.vShear)));
verifyFalse(tc, isfield(d2, 'mohr'));
end

function testDeflectionUniformSimplySupported(tc)
L = 5; q = 2e4;
m = beamModel(L, [0 L], {'rotule', 'appui_simple'});
m.distLoads = struct('a', 0, 'b', L, 'dir', 'y', 'coeffs', -q, 'name', 'q');
d = SolicitationsEngine.deflection(m, []);
EI = 210e9*8e-6;
checkAgree(tc, d, 5*q*L^4/(384*EI), 1e-6);
verifyTrue(tc, all(d.mohr.details{1}.tabulated));
verifyTrue(tc, any(contains(d.mohr.details{1}.shapeA, "parabole")));
end

function testDeflectionClampedClampedUniform(tc)
L = 6; q = 1e4;
m = beamModel(L, [0 L], {'encastrement', 'encastrement'});
m.distLoads = struct('a', 0, 'b', L, 'dir', 'y', 'coeffs', -q, 'name', 'q');
d = SolicitationsEngine.deflection(m, []);
EI = 210e9*8e-6;
checkAgree(tc, d, q*L^4/(384*EI), 1e-6);
end

function testDeflectionClampedPinnedUniform(tc)
L = 4; q = 1.5e4;
m = beamModel(L, [0 L], {'encastrement', 'appui_simple'});
m.distLoads = struct('a', 0, 'b', L, 'dir', 'y', 'coeffs', -q, 'name', 'q');
d = SolicitationsEngine.deflection(m, []);
EI = 210e9*8e-6;
fref = q*L^4/EI*(39 + 55*sqrt(33))/65536;
checkAgree(tc, d, fref, 1e-6);
verifyEqual(tc, d.integration.sAtFmax, L*(15 - sqrt(33))/16, 'RelTol', 1e-9);
end

function testDeflectionPlaneXZ(tc)
L = 3; P = 2e3;
m = beamModel(L, [0 L], {'appui_simple', 'appui_simple'});
m.pointLoads = struct('pos', L/2, 'Fx', 0, 'Fy', 0, 'Fz', -P, 'name', 'F');
d = SolicitationsEngine.deflection(m, [], struct('plane', 'xz'));
EIy = 210e9*3e-6;
fref = P*L^3/(48*EIy);
checkAgree(tc, d, fref, 1e-6);
verifyEqual(tc, BeamAndTrussSolver.ppEval(d.integration.vPP, L/2), -fref, 'RelTol', 1e-9);  % w < 0
verifyEqual(tc, d.mohr.v(abs(d.mohr.s0 - L/2) < 1e-9), -fref, 'RelTol', 1e-9);
i0 = find(d.castigliano.s0 == 0);
verifyEqual(tc, d.castigliano.alpha(i0), d.integration.alpha(1), 'RelTol', 1e-9);   % dw/ds
verifyEqual(tc, d.plane, 'xz');
checkLatex(tc, d.latex);
verifyError(tc, @() SolicitationsEngine.deflection(m, [], struct('plane', 'yz')), ...
    'MecaStruct:SolicitationsEngine:invalidInput');
end

function testDeflectionLinearLoadGauss(tc)
% Charge triangulaire : M cubique → Mohr hors table (Gauss) mais exact. f = 0,01304 q0 L^4/(EI)
L = 3; q0 = 1e4;
m = beamModel(L, [0 L], {'appui_simple', 'appui_simple'});
m.distLoads = struct('a', 0, 'b', L, 'dir', 'y', 'coeffs', [-q0/L 0], 'name', 'q');
d = SolicitationsEngine.deflection(m, [], struct('s0', L/2));
EI = 210e9*8e-6;
verifyEqual(tc, d.mohr.v, -5*q0*L^4/(768*EI), 'RelTol', 1e-9);
verifyFalse(tc, all(d.mohr.details{1}.tabulated));
verifyEqual(tc, d.integration.fmax, d.aires.fmax, 'RelTol', 1e-9);
verifyEqual(tc, d.integration.fmax, 0.00652*q0*L^4/EI, 'RelTol', 1e-3);
end

function testMaxwellBetti(tc)
L = 5; a = 1.2; b = 3.7;
m = beamModel(L, [0 3.5], {'rotule', 'appui_simple'});
o = struct('methods', {{'castigliano'}}, 'nCastigliano', 2);
mA = m; mA.pointLoads = struct('pos', a, 'Fx', 0, 'Fy', 1, 'Fz', 0, 'name', 'F');
mB = m; mB.pointLoads = struct('pos', b, 'Fx', 0, 'Fy', 1, 'Fz', 0, 'name', 'F');
o.s0 = b; dA = SolicitationsEngine.deflection(mA, [], o);
o.s0 = a; dB = SolicitationsEngine.deflection(mB, [], o);
sBA = dA.castigliano.vTotal(dA.castigliano.s0 == b);
sAB = dB.castigliano.vTotal(dB.castigliano.s0 == a);
verifyEqual(tc, sBA, sAB, 'RelTol', 1e-9);
verifyNotEqual(tc, sBA, 0);
end

function testClapeyronEnergy(tc)
L = 2; P = 1e3;
m = beamModel(L, 0, {'encastrement'});
m.pointLoads = struct('pos', L, 'Fx', 0, 'Fy', -P, 'Fz', 0, 'name', 'F');
sol = BeamAndTrussSolver.solveBeam(m);
U = SolicitationsEngine.strainEnergy(m, sol);
d = SolicitationsEngine.deflection(m, sol, struct('methods', {{'castigliano'}}, 's0', L));
c = d.castigliano;
verifyEqual(tc, U.UMfz, 0.5*P*abs(c.vBending(c.s0 == L)), 'RelTol', 1e-9);
verifyEqual(tc, U.total, 0.5*P*abs(c.vTotal(c.s0 == L)), 'RelTol', 1e-9);
verifyEqual(tc, U.UTy, P^2*L/(2*5/6*80e9*2e-3), 'RelTol', 1e-12);
verifyEqual(tc, [U.UN U.UTz U.UMt U.UMfy], [0 0 0 0], 'AbsTol', 1e-15);
checkLatex(tc, U.latex);
end

function testStrainEnergyAllTerms(tc)
L = 1.5; F = 2e4; C = 300; Pz = 500;
m = beamModel(L, 0, {'encastrement'});
m.pointLoads = struct('pos', L, 'Fx', F, 'Fy', 0, 'Fz', Pz, 'name', 'F');
m.pointMoments = struct('pos', L, 'Mx', C, 'My', 0, 'Mz', 0, 'name', 'C');
sol = BeamAndTrussSolver.solveBeam(m);
U = SolicitationsEngine.strainEnergy(m, sol);
verifyEqual(tc, U.UN, F^2*L/(2*210e9*2e-3), 'RelTol', 1e-12);
verifyEqual(tc, U.UMt, C^2*L/(2*80e9*1e-6), 'RelTol', 1e-12);
verifyEqual(tc, U.UTz, Pz^2*L/(2*5/6*80e9*2e-3), 'RelTol', 1e-12);
verifyEqual(tc, U.UMfy, Pz^2*L^3/(6*210e9*3e-6), 'RelTol', 1e-12);
% Propriétés du modèle prioritaires
m2 = m; m2.E = 105e9;
U2 = SolicitationsEngine.strainEnergy(m2, sol);
verifyEqual(tc, U2.UN, 2*U.UN, 'RelTol', 1e-12);
end

%% ------------------------------------------------------------------ intégrales de Mohr

function testMohrIntegralTable(tc)
% Trapèze × parabole + triangles sur deux tronçons
A = struct('breaks', [0 1 3], 'coefs', {{[2 1], [-1 5 -2]}});
B = struct('breaks', [0 2 3], 'coefs', {{[1 0], [-2 6]}});
M = SolicitationsEngine.mohrIntegral(A, B, 0, 3);
ex = integral(@(s) BeamAndTrussSolver.ppEval(A, s).*BeamAndTrussSolver.ppEval(B, s), 0, 3, ...
    'RelTol', 1e-13, 'AbsTol', 0, 'Waypoints', [1 2]);
verifyEqual(tc, M.value, ex, 'RelTol', 1e-10);
verifyEqual(tc, M.valueTable, M.value, 'RelTol', 1e-12);
verifyTrue(tc, M.allTabulated);
verifyEqual(tc, height(M.segments), 3);
verifyEqual(tc, sum(M.segments.value), M.valueTable, 'RelTol', 1e-14);
checkLatex(tc, cellstr(M.segments.formulaLatex));
checkLatex(tc, M.latex);
% Formes élémentaires : triangle × triangle même sens = l a b/3
T1 = struct('breaks', [0 2], 'coefs', {{[3 0]}});
M2 = SolicitationsEngine.mohrIntegral(T1, T1);
verifyEqual(tc, M2.valueTable, 2*6*6/3, 'RelTol', 1e-12);
verifyEqual(tc, M2.segments.shapeA(1), "triangle");
% Hors table : degré 3 → Gauss exact
C3 = struct('breaks', [0 1], 'coefs', {{[1 0 0 1]}});
M3 = SolicitationsEngine.mohrIntegral(C3, T1, 0, 1);
verifyFalse(tc, M3.allTabulated);
verifyEqual(tc, M3.valueTable, M3.value, 'RelTol', 1e-12);
verifyEqual(tc, M3.value, 3*(1/5 + 1/2), 'RelTol', 1e-12);
verifyError(tc, @() SolicitationsEngine.mohrIntegral(T1, T1, 1, 1), 'MecaStruct:SolicitationsEngine:invalidInput');
end

%% ------------------------------------------------------------------ flambage

function testBucklingDelegation(tc)
p = struct('E', 210e9, 'Re', 235e6, 'S', 1e-3, 'Iz', 2e-6, 'Iy', 5e-7, 'L', 3, ...
    'condition', 'articule-articule', 'P', 1e4);
b = SolicitationsEngine.buckling(p);
verifyEqual(tc, b.PE, pi^2*210e9*5e-7/9, 'RelTol', 1e-9);
verifyEqual(tc, b.regime, BucklingEngine.analyze(p).regime);
end
