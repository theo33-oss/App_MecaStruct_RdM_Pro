function tests = test_TensorAndCriteriaEngine
%TEST_TENSORANDCRITERIAENGINE Tests unitaires du module TensorAndCriteriaEngine (§6 et §9 du contrat).
%   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
%   Cas couverts : traction simple, cisaillement pur (Tresca = 2τ, Von Mises = √3·τ), exemple 3D à
%   valeurs propres connues, tenseur tourné quelconque, état hydrostatique, polynôme caractéristique
%   (roots, eig, symbolique), facette, cohérence plane2D / rotation tensorielle R·σ·Rᵀ (convention
%   τ = Cn·t avec t = (−sin θ, cos θ)), cercle de Mohr des déformations, tricercle, critères, lieux de
%   plasticité, Hooke isotrope (S·C = I), aller-retour hooke3D / hooke3DInverse avec dilatation
%   thermique, contraintes et déformations planes, orthotropie (symétrie, définie positivité),
%   notation de Voigt, jauges (Bridgman), pont de Wheatstone et sa réciproque, rosettes à 45° et 60°,
%   format des sorties report/latex et rendu LaTeX sans avertissement, erreurs attendues.
%
%   Lancement : r = runtests('test_TensorAndCriteriaEngine'); disp(table(r))
tests = functiontests(localfunctions);
end

function setupOnce(tc)
tc.TestData.hasSym = license('test', 'Symbolic_Toolbox') && ~isempty(ver('symbolic'));
end

%% =====================================================================================
%  Contraintes principales
%  =====================================================================================
function testTractionSimple(tc)
s0 = 150e6;
sig = diag([s0, 0, 0]);
r = TensorAndCriteriaEngine.principal(sig, false);
verifyEqual(tc, [r.sigmaI, r.sigmaII, r.sigmaIII], [s0, 0, 0], 'AbsTol', 1e-12 * s0);
verifyEqual(tc, r.I1, s0, 'RelTol', 1e-14);
verifyEqual(tc, r.I2, 0, 'AbsTol', 1e-12 * s0^2);
verifyEqual(tc, r.I3, 0, 'AbsTol', 1e-12 * s0^3);
verifyEqual(tc, r.charPoly, [1, -s0, 0, 0], 'AbsTol', 1e-12 * [1, s0, s0^2, s0^3]);
verifyEqual(tc, r.rootsCharPoly, [s0; 0; 0], 'AbsTol', 1e-9 * s0);
verifyEqual(tc, r.eigVals, [s0; 0; 0], 'AbsTol', 1e-12 * s0);
verifyEqual(tc, r.tauMax, s0 / 2, 'RelTol', 1e-12);
verifyEqual(tc, abs(r.directions(:, 1)), [1; 0; 0], 'AbsTol', 1e-12);
verifyEqual(tc, det(r.directions), 1, 'AbsTol', 1e-12);
verifyEqual(tc, r.sigmaOct, s0 / 3, 'RelTol', 1e-12);
verifyEqual(tc, r.tauOct, sqrt(2) * s0 / 3, 'RelTol', 1e-12);
verifyEqual(tc, r.methodUsed, 'numérique');

c = TensorAndCriteriaEngine.criteria([r.sigmaI, r.sigmaII, r.sigmaIII], 235e6, 1.5);
verifyEqual(tc, c.sigmaEqTresca, s0, 'RelTol', 1e-12);
verifyEqual(tc, c.sigmaEqVM, s0, 'RelTol', 1e-12);
verifyEqual(tc, c.sigmaMaxNormal, s0, 'RelTol', 1e-12);
verifyEqual(tc, c.sigmaAdm, 235e6 / 1.5, 'RelTol', 1e-14);
verifyTrue(tc, c.okTresca && c.okVM && c.okRankine);
verifyEqual(tc, c.sfTresca, 235 / 150, 'RelTol', 1e-12);
verifyEqual(tc, c.sfVM, 235 / 150, 'RelTol', 1e-12);

% Facette inclinée à 45° : σn = τ = σ/2 ; formules du cours en 2D : σ = σ0 cos²θ, τ = −σ0 sinθ cosθ
f = TensorAndCriteriaEngine.facet(sig, [1 1 0]);
verifyEqual(tc, f.sigmaN, s0 / 2, 'RelTol', 1e-12);
verifyEqual(tc, f.tauNorm, s0 / 2, 'RelTol', 1e-12);
th = linspace(0, pi, 13);
p = TensorAndCriteriaEngine.plane2D(s0, 0, 0, th);
verifyEqual(tc, p.sigma, s0 * cos(th).^2, 'AbsTol', 1e-12 * s0);
verifyEqual(tc, p.tau, -s0 * sin(th) .* cos(th), 'AbsTol', 1e-12 * s0);
end

function testCisaillementPur(tc)
tau = 80e6;
sig = [0, tau, 0; tau, 0, 0; 0, 0, 0];
r = TensorAndCriteriaEngine.principal(sig, false);
verifyEqual(tc, [r.sigmaI, r.sigmaII, r.sigmaIII], [tau, 0, -tau], 'AbsTol', 1e-12 * tau);
verifyEqual(tc, r.tauMax, tau, 'RelTol', 1e-12);
verifyEqual(tc, abs(r.directions(:, 1).' * [1; 1; 0] / sqrt(2)), 1, 'AbsTol', 1e-12);
verifyEqual(tc, abs(r.directions(:, 3).' * [1; -1; 0] / sqrt(2)), 1, 'AbsTol', 1e-12);
verifyEqual(tc, abs(r.directions(:, 2).' * [0; 0; 1]), 1, 'AbsTol', 1e-12);
verifyEqual(tc, det(r.directions), 1, 'AbsTol', 1e-12);
verifyEqual(tc, r.I2, -tau^2, 'RelTol', 1e-14);

c = TensorAndCriteriaEngine.criteria(sig, 300e6);
verifyEqual(tc, c.sigmaEqTresca, 2 * tau, 'RelTol', 1e-12);
verifyEqual(tc, c.sigmaEqVM, sqrt(3) * tau, 'RelTol', 1e-12);
verifyEqual(tc, c.sigmaMaxNormal, tau, 'RelTol', 1e-12);
verifyEqual(tc, c.tauMax, tau, 'RelTol', 1e-12);
verifyEqual(tc, c.sigmaR, 300e6);                       % défaut sigmaR = Re
verifyTrue(tc, c.okTresca && c.okVM && c.okRankine);

p = TensorAndCriteriaEngine.plane2D(0, 0, tau, pi / 4);
verifyEqual(tc, p.sigma, tau, 'RelTol', 1e-12);
verifyEqual(tc, p.tau, 0, 'AbsTol', 1e-12 * tau);
verifyEqual(tc, p.thetaP, pi / 4, 'AbsTol', 1e-14);
verifyEqual(tc, p.delta, 0, 'AbsTol', 1e-20);
verifyEqual(tc, p.rho, tau, 'RelTol', 1e-14);
verifyEqual(tc, [p.sigma1, p.sigma2], [tau, -tau], 'RelTol', 1e-14);
verifyEqual(tc, p.tauMax2D, tau, 'RelTol', 1e-14);
end

function testExemple3DValeursConnues(tc)
% σ = [5 2 0 ; 2 2 0 ; 0 0 −3] MPa : σI = 6, σII = 1, σIII = −3 MPa (bloc 2x2 : (7 ± 5)/2)
sig = [5, 2, 0; 2, 2, 0; 0, 0, -3] * 1e6;
r = TensorAndCriteriaEngine.principal(sig);
verifyEqual(tc, r.I1, 4e6, 'RelTol', 1e-14);
verifyEqual(tc, r.I2, -15e12, 'RelTol', 1e-14);
verifyEqual(tc, r.I3, -18e18, 'RelTol', 1e-12);
verifyEqual(tc, r.charPoly, [1, -4e6, -15e12, 18e18], 'RelTol', 1e-12);
verifyEqual(tc, r.eigVals, [6; 1; -3] * 1e6, 'RelTol', 1e-12);
verifyEqual(tc, r.rootsCharPoly, [6; 1; -3] * 1e6, 'RelTol', 1e-12);
verifyLessThan(tc, r.rootsEigDiff, 1e-12);
verifyEqual(tc, [r.sigmaI, r.sigmaII, r.sigmaIII], [6, 1, -3] * 1e6, 'RelTol', 1e-12);
% Directions : nI = (2, 1, 0)/√5, nII = (−1, 2, 0)/√5, nIII = nI ∧ nII = (0, 0, 1)
verifyEqual(tc, r.directions(:, 1), [2; 1; 0] / sqrt(5), 'AbsTol', 1e-12);
verifyEqual(tc, r.directions(:, 2), [-1; 2; 0] / sqrt(5), 'AbsTol', 1e-12);
verifyEqual(tc, r.directions(:, 3), [0; 0; 1], 'AbsTol', 1e-12);
verifyEqual(tc, cross(r.directions(:, 1), r.directions(:, 2)), r.directions(:, 3), 'AbsTol', 1e-12);
verifyLessThan(tc, r.residual, 1e-13);
verifyEqual(tc, r.tauMax, 4.5e6, 'RelTol', 1e-12);
verifyEqual(tc, r.sigmaOct, 4e6 / 3, 'RelTol', 1e-12);
verifyEqual(tc, r.tauOct, sqrt(122) / 3 * 1e6, 'RelTol', 1e-12);
% Liens avec le déviateur : τoct = √(2 J2/3), σVM = √(3 J2)
verifyEqual(tc, r.tauOct, sqrt(2 * r.J2 / 3), 'RelTol', 1e-12);
c = TensorAndCriteriaEngine.criteria(sig, 235e6);
verifyEqual(tc, c.sigmaEqVM, sqrt(3 * r.J2), 'RelTol', 1e-12);
verifyEqual(tc, c.sigmaEqTresca, 9e6, 'RelTol', 1e-12);
% Polynôme caractéristique nul aux valeurs propres
verifyEqual(tc, polyval(r.charPoly, r.eigVals) / 1e18, zeros(3, 1), 'AbsTol', 1e-9);
% Entrées équivalentes : vecteur de Voigt
rv = TensorAndCriteriaEngine.principal([5 2 -3 0 0 2] * 1e6, false);
verifyEqual(tc, rv.eigVals, r.eigVals, 'RelTol', 1e-12);
end

function testTenseurTourneQuelconque(tc)
lam = [250, -40, -120] * 1e6;
a = 0.7; b = -0.4; g = 1.9;
Rz = [cos(a), -sin(a), 0; sin(a), cos(a), 0; 0, 0, 1];
Rx = [1, 0, 0; 0, cos(b), -sin(b); 0, sin(b), cos(b)];
Rz2 = [cos(g), -sin(g), 0; sin(g), cos(g), 0; 0, 0, 1];
Q = Rz * Rx * Rz2;
sig = Q * diag(lam) * Q.';
sig = (sig + sig.') / 2;
r = TensorAndCriteriaEngine.principal(sig, false);
verifyEqual(tc, r.eigVals.', lam, 'RelTol', 1e-12);
verifyEqual(tc, r.rootsCharPoly.', lam, 'RelTol', 1e-10);
verifyEqual(tc, abs(Q.' * r.directions), eye(3), 'AbsTol', 1e-10);
verifyEqual(tc, r.directions.' * r.directions, eye(3), 'AbsTol', 1e-13);
verifyEqual(tc, det(r.directions), 1, 'AbsTol', 1e-13);
verifyEqual(tc, r.I1, sum(lam), 'RelTol', 1e-12);
verifyEqual(tc, r.I2, lam(1) * lam(2) + lam(2) * lam(3) + lam(1) * lam(3), 'RelTol', 1e-12);
verifyEqual(tc, r.I3, prod(lam), 'RelTol', 1e-12);

% Trièdre direct et résidu sur une série de tenseurs aléatoires (graine fixée)
rs = RandStream('mt19937ar', 'Seed', 17);
for k = 1:25
    A = (rand(rs, 3) - 0.5) * 400e6;
    A = (A + A.') / 2;
    rk = TensorAndCriteriaEngine.principal(A, false);
    verifyEqual(tc, det(rk.directions), 1, 'AbsTol', 1e-12);
    verifyEqual(tc, rk.directions.' * rk.directions, eye(3), 'AbsTol', 1e-12);
    verifyLessThan(tc, rk.residual, 1e-12);
    verifyTrue(tc, issorted(flipud(rk.eigVals)));
    verifyEqual(tc, rk.rootsCharPoly, rk.eigVals, 'AbsTol', 1e-8 * max(abs(A(:))));
end
end

function testEtatHydrostatique(tc)
p = -50e6;
r = TensorAndCriteriaEngine.principal(p * eye(3), false);
verifyEqual(tc, r.eigVals, p * ones(3, 1), 'RelTol', 1e-14);
verifyEqual(tc, r.rootsCharPoly, p * ones(3, 1), 'RelTol', 1e-4);   % racine triple : précision ~ eps^(1/3)
verifyEqual(tc, r.tauMax, 0, 'AbsTol', 1e-20);
verifyEqual(tc, r.tauOct, 0, 'AbsTol', 1e-20);
verifyEqual(tc, r.directions, eye(3), 'AbsTol', 1e-14);
c = TensorAndCriteriaEngine.criteria(p * eye(3), 235e6);
verifyEqual(tc, c.sigmaEqTresca, 0, 'AbsTol', 1e-20);
verifyEqual(tc, c.sigmaEqVM, 0, 'AbsTol', 1e-20);
verifyEqual(tc, c.sfTresca, Inf);
verifyEqual(tc, c.sfVM, Inf);
verifyEqual(tc, c.sigmaMaxNormal, 50e6, 'RelTol', 1e-14);
% Tenseur nul
r0 = TensorAndCriteriaEngine.principal(zeros(3), false);
verifyEqual(tc, r0.eigVals, zeros(3, 1));
verifyEqual(tc, det(r0.directions), 1, 'AbsTol', 1e-14);
end

function testPolynomeSymbolique(tc)
sig = [120, 30, 0; 30, -40, 10; 0, 10, 25] * 1e6;
rn = TensorAndCriteriaEngine.principal(sig, false);
verifyEqual(tc, rn.methodUsed, 'numérique');
verifyEmpty(tc, rn.charPolySym);
% Valeurs de référence (calcul symbolique exact en MPa) : −λ³ + 105 λ² + 3800 λ − 154500
verifyEqual(tc, rn.charPoly, [1, -105e6, -3800e12, 154500e18], 'RelTol', 1e-12);
if tc.TestData.hasSym
    rs = TensorAndCriteriaEngine.principal(sig);
    verifyEqual(tc, rs.methodUsed, 'symbolique');
    verifyEqual(tc, rs.charPolySym, rn.charPoly, 'RelTol', 1e-12);
    verifyTrue(tc, any(contains(rs.latex, '\mathrm{det}(\sigma - \lambda I)')));
    verifyEqual(tc, rs.eigVals, rn.eigVals, 'RelTol', 1e-14);
else
    rs = TensorAndCriteriaEngine.principal(sig, true);
    verifyEqual(tc, rs.methodUsed, 'numérique');
end
end

%% =====================================================================================
%  Facette, Mohr 2D et 3D
%  =====================================================================================
function testFacette(tc)
sig = [120, 30, -20; 30, -40, 10; -20, 10, 25] * 1e6;
r = TensorAndCriteriaEngine.facet(sig, [1 2 2]);
n = [1; 2; 2] / 3;
Cn = sig * n;
verifyEqual(tc, r.n, n, 'AbsTol', 1e-15);
verifyEqual(tc, r.Cn, Cn, 'RelTol', 1e-14);
verifyEqual(tc, r.sigmaN, Cn.' * n, 'RelTol', 1e-14);
verifyEqual(tc, r.tauVec.' * n, 0, 'AbsTol', 1e-8);
verifyEqual(tc, r.tauNorm, sqrt(Cn.' * Cn - (Cn.' * n)^2), 'RelTol', 1e-12);
verifyEqual(tc, r.normalVec + r.tauVec, Cn, 'RelTol', 1e-14);
verifyTrue(tc, isnan(r.tauT));
% Tangente fournie orthogonale
t = [2; -1; 0] / sqrt(5);
r2 = TensorAndCriteriaEngine.facet(sig, n, t);
verifyFalse(tc, r2.tProjected);
verifyEqual(tc, r2.tauT, Cn.' * t, 'RelTol', 1e-13);
% Tangente non orthogonale : projetée sur le plan de la facette
r3 = TensorAndCriteriaEngine.facet(sig, n, [1 0 0]);
verifyTrue(tc, r3.tProjected);
verifyEqual(tc, r3.t.' * n, 0, 'AbsTol', 1e-15);
verifyEqual(tc, norm(r3.t), 1, 'AbsTol', 1e-15);
verifyEqual(tc, r3.tauT, Cn.' * r3.t, 'RelTol', 1e-12);
% Erreurs
verifyError(tc, @() TensorAndCriteriaEngine.facet(sig, [0 0 0]), 'MecaStruct:TensorAndCriteriaEngine:zeroVector');
verifyError(tc, @() TensorAndCriteriaEngine.facet(sig, n, 2 * n), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.facet(sig, [1 2 3 4]), 'MecaStruct:TensorAndCriteriaEngine:badInput');
end

function testPlane2DCoherenceRotation(tc)
% Convention : n = (cos θ, sin θ), t = (−sin θ, cos θ) ; σ = Cn·n, τ = Cn·t,
% identiques aux composantes σ'11 et σ'12 de σ' = R σ Rᵀ avec R = [cos θ sin θ ; −sin θ cos θ].
sxx = 120e6; syy = -40e6; sxy = 30e6;
S = [sxx, sxy; sxy, syy];
th = linspace(-pi, pi, 37);
r = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy, th);
verifyEqual(tc, size(r.sigma), size(th));
verifyEqual(tc, size(r.tau), size(th));
for k = 1:numel(th)
    c = cos(th(k)); s = sin(th(k));
    R = [c, s; -s, c];
    Sp = R * S * R.';
    verifyEqual(tc, r.sigma(k), Sp(1, 1), 'AbsTol', 1e-12 * 120e6);
    verifyEqual(tc, r.tau(k), Sp(1, 2), 'AbsTol', 1e-12 * 120e6);
    n = [c; s]; t = [-s; c];
    Cn = S * n;
    verifyEqual(tc, r.tau(k), Cn.' * t, 'AbsTol', 1e-12 * 120e6);
    f = TensorAndCriteriaEngine.facet(S, n, t);
    verifyEqual(tc, f.sigmaN, r.sigma(k), 'AbsTol', 1e-12 * 120e6);
    verifyEqual(tc, f.tauT, r.tau(k), 'AbsTol', 1e-12 * 120e6);
end
rho = sqrt(80^2 + 30^2) * 1e6;
verifyEqual(tc, r.delta, 40e6, 'RelTol', 1e-14);
verifyEqual(tc, r.rho, rho, 'RelTol', 1e-14);
verifyEqual(tc, [r.sigma1; r.sigma2], sort(eig(S), 'descend'), 'RelTol', 1e-12);
verifyEqual(tc, r.thetaP, 0.5 * atan2(60, 160), 'AbsTol', 1e-15);
verifyEqual(tc, r.pointA, [sxx, sxy]);
verifyEqual(tc, r.pointB, [syy, -sxy]);
verifyEqual(tc, r.tauMax2D, rho, 'RelTol', 1e-14);
% Facettes principales et de cisaillement maximal
p1 = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy, r.thetaP);
verifyEqual(tc, p1.sigma, r.sigma1, 'RelTol', 1e-12);
verifyEqual(tc, p1.tau, 0, 'AbsTol', 1e-12 * rho);
p2 = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy, r.thetaP + pi / 2);
verifyEqual(tc, p2.sigma, r.sigma2, 'RelTol', 1e-12);
p3 = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy, r.thetaTauMax);
verifyEqual(tc, p3.tau, rho, 'RelTol', 1e-12);
verifyEqual(tc, p3.sigma, r.delta, 'RelTol', 1e-12);
% Cercle : fermé, points à distance ρ du centre ; points des facettes sur le cercle
verifyEqual(tc, size(r.circle, 2), 2);
verifyEqual(tc, r.circle(1, :), r.circle(end, :));
verifyEqual(tc, hypot(r.circle(:, 1) - r.delta, r.circle(:, 2)), rho * ones(size(r.circle, 1), 1), 'RelTol', 1e-12);
verifyEqual(tc, hypot(r.sigma - r.delta, r.tau), rho * ones(size(th)), 'RelTol', 1e-12);
% Sens de parcours : le point de la facette θ se déduit de A par une rotation de −2θ (horaire)
angA = atan2(sxy, sxx - r.delta);
angT = atan2(r.tau, r.sigma - r.delta);
dAng = angle(exp(1i * (angT - (angA - 2 * th))));
verifyEqual(tc, dAng, zeros(size(th)), 'AbsTol', 1e-12);
% État 3D associé (σzz = 0)
verifyEqual(tc, r.principal3D, sort([r.sigma1, r.sigma2, 0], 'descend'));
verifyEqual(tc, r.tauMax3D, (max([r.sigma1, 0]) - min([r.sigma2, 0])) / 2, 'RelTol', 1e-14);
% Valeur par défaut θ = 0 et tableau 2D de θ
r0 = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy);
verifyEqual(tc, [r0.sigma, r0.tau], [sxx, sxy], 'RelTol', 1e-14);
thm = reshape(linspace(0, pi, 6), 2, 3);
rm = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy, thm);
verifyEqual(tc, size(rm.sigma), [2, 3]);
end

function testPlane2DStrain(tc)
exx = 500e-6; eyy = -200e-6; exy = 150e-6;
Ee = [exx, exy; exy, eyy];
th = linspace(0, pi, 19);
r = TensorAndCriteriaEngine.plane2DStrain(exx, eyy, exy, th);
for k = 1:numel(th)
    c = cos(th(k)); s = sin(th(k));
    R = [c, s; -s, c];
    Ep = R * Ee * R.';
    verifyEqual(tc, r.eps(k), Ep(1, 1), 'AbsTol', 1e-12 * 500e-6);
    verifyEqual(tc, r.gammaHalf(k), Ep(1, 2), 'AbsTol', 1e-12 * 500e-6);
end
verifyEqual(tc, r.gamma, 2 * r.gammaHalf, 'RelTol', 1e-15);
verifyEqual(tc, [r.eps1; r.eps2], sort(eig(Ee), 'descend'), 'RelTol', 1e-12);
verifyEqual(tc, r.gammaMax2D, r.eps1 - r.eps2, 'RelTol', 1e-12);
verifyEqual(tc, r.gxy, 300e-6, 'RelTol', 1e-15);
verifyEqual(tc, r.pointA, [exx, exy]);
verifyEqual(tc, r.pointB, [eyy, -exy]);
verifyEqual(tc, r.kind, 'strain');
verifyEqual(tc, r.delta, 150e-6, 'RelTol', 1e-14);
verifyEqual(tc, r.rho, sqrt(350^2 + 150^2) * 1e-6, 'RelTol', 1e-14);
end

function testMohr3D(tc)
m = TensorAndCriteriaEngine.mohr3D([50e6, -100e6, 200e6]);
verifyEqual(tc, m.pr, [200, 50, -100] * 1e6);
verifyEqual(tc, m.centers, [125, -25, 50] * 1e6, 'RelTol', 1e-14);
verifyEqual(tc, m.radii, [75, 75, 150] * 1e6, 'RelTol', 1e-14);
verifyEqual(tc, m.tauMax, 150e6, 'RelTol', 1e-14);
verifyEqual(tc, numel(m.circles), 3);
for k = 1:3
    C = m.circles{k};
    verifyEqual(tc, size(C, 2), 2);
    verifyEqual(tc, hypot(C(:, 1) - m.centers(k), C(:, 2)), m.radii(k) * ones(size(C, 1), 1), 'RelTol', 1e-12);
end
% État plan [σ1 σ2] : σ3 = 0 ajouté ; tenseur 3x3 accepté
mp = TensorAndCriteriaEngine.mohr3D([80e6, -30e6]);
verifyEqual(tc, mp.pr, [80e6, 0, -30e6]);
sig = [5, 2, 0; 2, 2, 0; 0, 0, -3] * 1e6;
mt = TensorAndCriteriaEngine.mohr3D(sig);
verifyEqual(tc, mt.pr, [6, 1, -3] * 1e6, 'RelTol', 1e-12);
% Tout point (σn, τ) d'une facette est dans le grand cercle et hors des deux petits
rs = RandStream('mt19937ar', 'Seed', 3);
for k = 1:50
    f = TensorAndCriteriaEngine.facet(sig, randn(rs, 3, 1));
    dBig = hypot(f.sigmaN - mt.centers(3), f.tauNorm) - mt.radii(3);
    d1 = hypot(f.sigmaN - mt.centers(1), f.tauNorm) - mt.radii(1);
    d2 = hypot(f.sigmaN - mt.centers(2), f.tauNorm) - mt.radii(2);
    verifyLessThanOrEqual(tc, dBig, 1e-6);
    verifyGreaterThanOrEqual(tc, d1, -1e-6);
    verifyGreaterThanOrEqual(tc, d2, -1e-6);
end
end

%% =====================================================================================
%  Critères et lieux de plasticité
%  =====================================================================================
function testCriteres(tc)
c = TensorAndCriteriaEngine.criteria([50e6, -100e6, 200e6], 355e6, 1.2, 490e6);
verifyEqual(tc, c.pr, [200, 50, -100] * 1e6);
verifyEqual(tc, c.sigmaEqTresca, 300e6, 'RelTol', 1e-14);
verifyEqual(tc, c.sigmaEqVM, sqrt(67500) * 1e6, 'RelTol', 1e-14);
verifyEqual(tc, c.sigmaMaxNormal, 200e6, 'RelTol', 1e-14);
verifyEqual(tc, c.sigmaAdm, 355e6 / 1.2, 'RelTol', 1e-14);
verifyFalse(tc, c.okTresca);                 % 300 > 295,8 MPa
verifyTrue(tc, c.okVM);                      % 259,8 ≤ 295,8 MPa
verifyTrue(tc, c.okRankine);                 % 200 ≤ 490/1,2 MPa
verifyEqual(tc, c.sfTresca, 355 / 300, 'RelTol', 1e-14);
verifyEqual(tc, c.sfVM, 355 / sqrt(67500), 'RelTol', 1e-14);
verifyEqual(tc, c.sfRankine, 490 / 200, 'RelTol', 1e-14);
verifyEqual(tc, c.sigmaRAdm, 490e6 / 1.2, 'RelTol', 1e-14);
% Rapport Tresca / Von Mises compris entre 1 et 2/√3
verifyGreaterThanOrEqual(tc, c.sigmaEqTresca / c.sigmaEqVM, 1);
verifyLessThanOrEqual(tc, c.sigmaEqTresca / c.sigmaEqVM, 2 / sqrt(3) + 1e-12);
% Contraintes planes : σVM = √(σ1² − σ1σ2 + σ2²)
cp = TensorAndCriteriaEngine.criteria([120e6, -70e6], 235e6);
verifyEqual(tc, cp.sigmaEqVM, sqrt(120^2 + 120 * 70 + 70^2) * 1e6, 'RelTol', 1e-14);
verifyEqual(tc, cp.sigmaEqTresca, 190e6, 'RelTol', 1e-14);
% Matériau fragile : contrainte normale maximale non vérifiée
cf = TensorAndCriteriaEngine.criteria([-250e6, 0, 0], 300e6, 1, 200e6);
verifyFalse(tc, cf.okRankine);
verifyEqual(tc, cf.sigmaMaxNormal, 250e6);
% Entrées : vecteur de Voigt et valeur NaN de sigmaR (→ Re)
cv = TensorAndCriteriaEngine.criteria([5 2 -3 0 0 2] * 1e6, 235e6, 1, NaN);
verifyEqual(tc, cv.sigmaEqTresca, 9e6, 'RelTol', 1e-12);
verifyEqual(tc, cv.sigmaR, 235e6);
% Erreurs
verifyError(tc, @() TensorAndCriteriaEngine.criteria([1 2 3], -1), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.criteria([1 2 3], 235e6, 0), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.criteria([1 2 3 4], 235e6), 'MecaStruct:TensorAndCriteriaEngine:badInput');
end

function testLieuxPlasticite(tc)
Re = 235e6; s = 1.5; sR = 340e6;
L = TensorAndCriteriaEngine.yieldLoci(Re, s, sR);
a = Re / s;
verifyEqual(tc, L.sigmaAdm, a, 'RelTol', 1e-15);
% Ellipse exacte de Von Mises : σ1² − σ1σ2 + σ2² = σadm²
V = L.vonMises;
verifyEqual(tc, size(V, 2), 2);
verifyGreaterThan(tc, size(V, 1), 100);
verifyEqual(tc, V(1, :), V(end, :));
verifyEqual(tc, V(:, 1).^2 - V(:, 1) .* V(:, 2) + V(:, 2).^2, a^2 * ones(size(V, 1), 1), 'RelTol', 1e-12);
% Hexagone de Tresca : fermé, max(|σ1|, |σ2|, |σ1 − σ2|) = σadm aux sommets et sur les côtés
H = L.tresca;
verifyEqual(tc, size(H), [7, 2]);
verifyEqual(tc, H(1, :), H(end, :));
fT = @(P) max([abs(P(:, 1)), abs(P(:, 2)), abs(P(:, 1) - P(:, 2))], [], 2);
verifyEqual(tc, fT(H), a * ones(7, 1), 'RelTol', 1e-14);
mid = (H(1:end-1, :) + H(2:end, :)) / 2;
verifyEqual(tc, fT(mid), a * ones(6, 1), 'RelTol', 1e-14);
% Hexagone inscrit dans l'ellipse (sommets sur l'ellipse)
verifyEqual(tc, H(:, 1).^2 - H(:, 1) .* H(:, 2) + H(:, 2).^2, a^2 * ones(7, 1), 'RelTol', 1e-14);
% Carré de Rankine
Q = L.rankine;
verifyEqual(tc, size(Q), [5, 2]);
verifyEqual(tc, Q(1, :), Q(end, :));
verifyEqual(tc, max(abs(Q), [], 2), sR / s * ones(5, 1), 'RelTol', 1e-14);
% Cohérence avec criteria sur quelques points de l'ellipse
for k = 1:30:size(V, 1)
    c = TensorAndCriteriaEngine.criteria(V(k, :), Re, s);
    verifyEqual(tc, c.sigmaEqVM, a, 'RelTol', 1e-12);
end
% Valeurs par défaut (s = 1, sigmaR = Re)
L1 = TensorAndCriteriaEngine.yieldLoci(Re);
verifyEqual(tc, L1.sigmaAdm, Re);
verifyEqual(tc, max(abs(L1.rankine(:))), Re);
end

%% =====================================================================================
%  Loi de Hooke
%  =====================================================================================
function testHookeIsotropeSC(tc)
E = 210e9; nu = 0.3;
S = TensorAndCriteriaEngine.complianceIsotropic(E, nu);
C = TensorAndCriteriaEngine.stiffnessIsotropic(E, nu);
G = E / (2 * (1 + nu));
lam = E * nu / ((1 + nu) * (1 - 2 * nu));
verifyEqual(tc, S * C, eye(6), 'AbsTol', 1e-13);
verifyEqual(tc, C * S, eye(6), 'AbsTol', 1e-13);
verifyEqual(tc, S, S.');
verifyEqual(tc, C, C.');
verifyEqual(tc, S(1, 1), 1 / E, 'RelTol', 1e-14);
verifyEqual(tc, S(1, 2), -nu / E, 'RelTol', 1e-14);
verifyEqual(tc, S(4, 4), 1 / G, 'RelTol', 1e-14);
verifyEqual(tc, S(6, 6), 2 * (1 + nu) / E, 'RelTol', 1e-14);
verifyEqual(tc, C(1, 1), lam + 2 * G, 'RelTol', 1e-14);
verifyEqual(tc, C(1, 1), E * (1 - nu) / ((1 + nu) * (1 - 2 * nu)), 'RelTol', 1e-14);
verifyEqual(tc, C(1, 2), lam, 'RelTol', 1e-14);
verifyEqual(tc, C(5, 5), G, 'RelTol', 1e-14);
verifyEqual(tc, nnz(S(1:3, 4:6)) + nnz(C(1:3, 4:6)), 0);
verifyGreaterThan(tc, min(eig(C)), 0);
% Matériau auxétique admissible
verifyEqual(tc, TensorAndCriteriaEngine.complianceIsotropic(1e9, -0.5) * TensorAndCriteriaEngine.stiffnessIsotropic(1e9, -0.5), ...
    eye(6), 'AbsTol', 1e-13);
% Constantes non admissibles
verifyError(tc, @() TensorAndCriteriaEngine.stiffnessIsotropic(E, 0.5), 'MecaStruct:TensorAndCriteriaEngine:badMaterial');
verifyError(tc, @() TensorAndCriteriaEngine.complianceIsotropic(-E, 0.3), 'MecaStruct:TensorAndCriteriaEngine:badMaterial');
verifyError(tc, @() TensorAndCriteriaEngine.complianceIsotropic(E, -1), 'MecaStruct:TensorAndCriteriaEngine:badMaterial');
end

function testHooke3DAllerRetourThermique(tc)
E = 200e9; nu = 0.28; alpha = 12e-6; dT = 80;
G = E / (2 * (1 + nu));
sigV = [120; -30; 45; 20; -15; 60] * 1e6;
e = TensorAndCriteriaEngine.hooke3D(sigV, E, nu, alpha, dT);
verifyEqual(tc, size(e), [6, 1]);
th = alpha * dT;
verifyEqual(tc, e(1), (sigV(1) - nu * (sigV(2) + sigV(3))) / E + th, 'RelTol', 1e-13);
verifyEqual(tc, e(2), (sigV(2) - nu * (sigV(1) + sigV(3))) / E + th, 'RelTol', 1e-13);
verifyEqual(tc, e(3), (sigV(3) - nu * (sigV(1) + sigV(2))) / E + th, 'RelTol', 1e-13);
verifyEqual(tc, e(4:6), sigV(4:6) / G, 'RelTol', 1e-13);
s2 = TensorAndCriteriaEngine.hooke3DInverse(e, E, nu, alpha, dT);
verifyEqual(tc, s2, sigV, 'AbsTol', 1e-9 * max(abs(sigV)));
% Dilatation libre : ε = αΔT·{1 1 1 0 0 0} ; aller-retour → σ = 0
e0 = TensorAndCriteriaEngine.hooke3D(zeros(6, 1), E, nu, alpha, dT);
verifyEqual(tc, e0, th * [1; 1; 1; 0; 0; 0], 'RelTol', 1e-15);
verifyEqual(tc, TensorAndCriteriaEngine.hooke3DInverse(e0, E, nu, alpha, dT), zeros(6, 1), 'AbsTol', 1e-3);
% Dilatation empêchée : σ = −E αΔT/(1 − 2ν) (état hydrostatique)
sb = TensorAndCriteriaEngine.hooke3DInverse(zeros(6, 1), E, nu, alpha, dT);
verifyEqual(tc, sb, -E * th / (1 - 2 * nu) * [1; 1; 1; 0; 0; 0], 'AbsTol', 1e-6, 'RelTol', 1e-13);
% Sans thermique (valeurs par défaut) et entrées tensorielles 3x3
e1 = TensorAndCriteriaEngine.hooke3D(sigV, E, nu);
verifyEqual(tc, e1, TensorAndCriteriaEngine.complianceIsotropic(E, nu) * sigV, 'RelTol', 1e-15);
eT = TensorAndCriteriaEngine.hooke3D(TensorAndCriteriaEngine.voigtToTensor(sigV, 'stress'), E, nu, alpha, dT);
verifyEqual(tc, eT, e, 'RelTol', 1e-14);
sT = TensorAndCriteriaEngine.hooke3DInverse(TensorAndCriteriaEngine.voigtToTensor(e, 'strain'), E, nu, alpha, dT);
verifyEqual(tc, sT, sigV, 'AbsTol', 1e-9 * max(abs(sigV)));
% Traction simple : εyy = −ν σ/E + αΔT
eu = TensorAndCriteriaEngine.hooke3D([100e6; 0; 0; 0; 0; 0], E, nu, alpha, dT);
verifyEqual(tc, eu(2), -nu * 100e6 / E + th, 'RelTol', 1e-13);
verifyError(tc, @() TensorAndCriteriaEngine.hooke3D([1 2 3], E, nu), 'MecaStruct:TensorAndCriteriaEngine:badInput');
end

function testContraintesPlanes(tc)
E = 70e9; nu = 0.33;
sxx = 100e6; syy = -50e6; sxy = 40e6;
r = TensorAndCriteriaEngine.planeStress(sxx, syy, sxy, E, nu);
G = E / (2 * (1 + nu));
verifyEqual(tc, r.exx, (sxx - nu * syy) / E, 'RelTol', 1e-14);
verifyEqual(tc, r.eyy, (syy - nu * sxx) / E, 'RelTol', 1e-14);
verifyEqual(tc, r.gxy, sxy / G, 'RelTol', 1e-14);
verifyEqual(tc, r.ezz, -nu * (sxx + syy) / E, 'RelTol', 1e-14);
e3 = TensorAndCriteriaEngine.hooke3D([sxx; syy; 0; 0; 0; sxy], E, nu);
verifyEqual(tc, [r.exx; r.eyy; r.ezz; r.gxy], e3([1 2 3 6]), 'RelTol', 1e-13);
verifyEqual(tc, r.Sred * [sxx; syy; sxy], [r.exx; r.eyy; r.gxy], 'RelTol', 1e-13);
verifyEqual(tc, r.Sred * r.Qred, eye(3), 'AbsTol', 1e-13);
% Vectorisation
rv = TensorAndCriteriaEngine.planeStress([sxx, 2 * sxx], syy, [sxy, 0], E, nu);
verifyEqual(tc, size(rv.exx), [1, 2]);
verifyEqual(tc, rv.exx(1), r.exx, 'RelTol', 1e-14);
verifyEqual(tc, rv.gxy(2), 0);
verifyError(tc, @() TensorAndCriteriaEngine.planeStress([1 2], [1 2 3], 0, E, nu), 'MecaStruct:TensorAndCriteriaEngine:badInput');
end

function testDeformationsPlanes(tc)
E = 210e9; nu = 0.3;
exx = 400e-6; eyy = -100e-6; gxy = 300e-6;
r = TensorAndCriteriaEngine.planeStrain(exx, eyy, gxy, E, nu);
verifyEqual(tc, r.szz, nu * (r.sxx + r.syy), 'RelTol', 1e-14);
verifyEqual(tc, r.ezz, 0);
s3 = TensorAndCriteriaEngine.hooke3DInverse([exx; eyy; 0; 0; 0; gxy], E, nu);
verifyEqual(tc, [r.sxx; r.syy; r.szz; r.sxy], s3([1 2 3 6]), 'RelTol', 1e-13);
e3 = TensorAndCriteriaEngine.hooke3D([r.sxx; r.syy; r.szz; 0; 0; r.sxy], E, nu);
verifyEqual(tc, e3, [exx; eyy; 0; 0; 0; gxy], 'AbsTol', 1e-17);
verifyEqual(tc, r.Cred * [exx; eyy; gxy], [r.sxx; r.syy; r.sxy], 'RelTol', 1e-13);
verifyEqual(tc, r.Cred * r.Sred, eye(3), 'AbsTol', 1e-13);
verifyEqual(tc, r.Cred(3, 3), E / (2 * (1 + nu)), 'RelTol', 1e-14);
end

function testOrthotrope(tc)
c = struct('E1', 140e9, 'E2', 10e9, 'E3', 10e9, 'nu12', 0.3, 'nu13', 0.3, 'nu23', 0.45, ...
    'G12', 5e9, 'G13', 5e9, 'G23', 3.5e9);
S = TensorAndCriteriaEngine.complianceOrthotropic(c);
C = TensorAndCriteriaEngine.stiffnessOrthotropic(c);
verifyEqual(tc, S, S.');
verifyEqual(tc, C, C.', 'RelTol', 1e-14);
verifyEqual(tc, S * C, eye(6), 'AbsTol', 1e-12);
nu21 = 0.3 * 10 / 140;
verifyEqual(tc, S(1, 2), -0.3 / 140e9, 'RelTol', 1e-14);
verifyEqual(tc, S(2, 1), -nu21 / 10e9, 'RelTol', 1e-14);       % symétrie ν12/E1 = ν21/E2
verifyEqual(tc, S(2, 3), -0.45 / 10e9, 'RelTol', 1e-14);
verifyEqual(tc, [S(4, 4), S(5, 5), S(6, 6)], 1 ./ [3.5e9, 5e9, 5e9], 'RelTol', 1e-14);
verifyGreaterThan(tc, min(eig(C)), 0);
% Traction selon 1 : ε2/ε1 = −ν12, ε3/ε1 = −ν13
eps = S * [100e6; 0; 0; 0; 0; 0];
verifyEqual(tc, eps(2) / eps(1), -0.3, 'RelTol', 1e-14);
verifyEqual(tc, eps(3) / eps(1), -0.3, 'RelTol', 1e-14);
% Limite isotrope
E = 200e9; nu = 0.25; G = E / (2 * (1 + nu));
ci = struct('E1', E, 'E2', E, 'E3', E, 'nu12', nu, 'nu13', nu, 'nu23', nu, 'G12', G, 'G13', G, 'G23', G);
verifyEqual(tc, TensorAndCriteriaEngine.complianceOrthotropic(ci), TensorAndCriteriaEngine.complianceIsotropic(E, nu), 'RelTol', 1e-14);
verifyEqual(tc, TensorAndCriteriaEngine.stiffnessOrthotropic(ci), TensorAndCriteriaEngine.stiffnessIsotropic(E, nu), 'RelTol', 1e-12);
% Coefficients réciproques fournis : cohérents → accepté ; incohérents → erreur explicite
c.nu21 = nu21;
verifyEqual(tc, TensorAndCriteriaEngine.complianceOrthotropic(c), S, 'RelTol', 1e-15);
c.nu21 = 0.3;
verifyError(tc, @() TensorAndCriteriaEngine.complianceOrthotropic(c), 'MecaStruct:TensorAndCriteriaEngine:orthoSymmetry');
% Non défini positif : Δ < 0 (ν = 0,6 isotrope transverse)
cb = ci; cb.nu12 = 0.6; cb.nu13 = 0.6; cb.nu23 = 0.6;
verifyError(tc, @() TensorAndCriteriaEngine.complianceOrthotropic(cb), 'MecaStruct:TensorAndCriteriaEngine:notPositiveDefinite');
verifyError(tc, @() TensorAndCriteriaEngine.stiffnessOrthotropic(cb), 'MecaStruct:TensorAndCriteriaEngine:notPositiveDefinite');
% Non défini positif : 1 − ν12·ν21 < 0
cb = ci; cb.nu12 = 1.2;
verifyError(tc, @() TensorAndCriteriaEngine.complianceOrthotropic(cb), 'MecaStruct:TensorAndCriteriaEngine:notPositiveDefinite');
% Module de cisaillement nul
cb = ci; cb.G12 = 0;
verifyError(tc, @() TensorAndCriteriaEngine.stiffnessOrthotropic(cb), 'MecaStruct:TensorAndCriteriaEngine:notPositiveDefinite');
% Constante manquante
cb = rmfield(ci, 'G23');
verifyError(tc, @() TensorAndCriteriaEngine.complianceOrthotropic(cb), 'MecaStruct:TensorAndCriteriaEngine:badInput');
end

function testVoigt(tc)
T = [1, 4, 5; 4, 2, 6; 5, 6, 3];
verifyEqual(tc, TensorAndCriteriaEngine.tensorToVoigt(T, 'stress'), [1; 2; 3; 6; 5; 4]);
verifyEqual(tc, TensorAndCriteriaEngine.tensorToVoigt(T), [1; 2; 3; 6; 5; 4]);
verifyEqual(tc, TensorAndCriteriaEngine.tensorToVoigt(T, 'strain'), [1; 2; 3; 12; 10; 8]);
verifyEqual(tc, TensorAndCriteriaEngine.voigtToTensor([1 2 3 6 5 4], 'stress'), T);
verifyEqual(tc, TensorAndCriteriaEngine.voigtToTensor([1 2 3 12 10 8], 'strain'), T);
verifyEqual(tc, TensorAndCriteriaEngine.voigtToTensor(TensorAndCriteriaEngine.tensorToVoigt(T, 'strain'), 'strain'), T);
% 2x2
T2 = [3, 7; 7, -1];
verifyEqual(tc, TensorAndCriteriaEngine.tensorToVoigt(T2, 'strain'), [3; -1; 14]);
verifyEqual(tc, TensorAndCriteriaEngine.voigtToTensor([3 -1 14], 'strain'), T2);
% Travail de déformation : σ:ε = {σ}ᵀ{ε} avec glissements ingénieur
Ts = [10, 2, -3; 2, 5, 1; -3, 1, -4];
Te = [1, 0.5, 0.2; 0.5, -2, 0.3; 0.2, 0.3, 0.7];
verifyEqual(tc, sum(sum(Ts .* Te)), TensorAndCriteriaEngine.tensorToVoigt(Ts, 'stress').' * ...
    TensorAndCriteriaEngine.tensorToVoigt(Te, 'strain'), 'RelTol', 1e-14);
% Erreurs
verifyError(tc, @() TensorAndCriteriaEngine.tensorToVoigt([1 2 0; 3 4 0; 0 0 1]), 'MecaStruct:TensorAndCriteriaEngine:notSymmetric');
verifyError(tc, @() TensorAndCriteriaEngine.tensorToVoigt(eye(3), 'foo'), 'MecaStruct:TensorAndCriteriaEngine:badKind');
verifyError(tc, @() TensorAndCriteriaEngine.voigtToTensor([1 2 3 4]), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.tensorToVoigt(eye(4)), 'MecaStruct:TensorAndCriteriaEngine:badInput');
end

%% =====================================================================================
%  Extensométrie
%  =====================================================================================
function testJaugeBridgman(tc)
r = TensorAndCriteriaEngine.gauge(2.1, 500e-6, 120);
verifyEqual(tc, r.dRsurR, 1.05e-3, 'RelTol', 1e-14);
verifyEqual(tc, r.dR, 0.126, 'RelTol', 1e-13);
verifyEqual(tc, TensorAndCriteriaEngine.gaugeStrain(2.1, r.dRsurR), 500e-6, 'RelTol', 1e-14);
rv = TensorAndCriteriaEngine.gauge(2, [100e-6, -300e-6]);
verifyEqual(tc, rv.dRsurR, [200e-6, -600e-6], 'RelTol', 1e-14);
verifyTrue(tc, isnan(rv.R0));
verifyEqual(tc, TensorAndCriteriaEngine.gaugeStrain(2, rv.dRsurR), [100e-6, -300e-6], 'RelTol', 1e-14);
verifyError(tc, @() TensorAndCriteriaEngine.gauge(0, 1e-3), 'MecaStruct:TensorAndCriteriaEngine:badInput');
end

function testPontWheatstone(tc)
K = 2; Vin = 10; e = 1000e-6; x = K * e; nu = 0.3;
% Quart de pont
q = TensorAndCriteriaEngine.wheatstone('quart', K, Vin, e);
verifyEqual(tc, q.Vout, Vin * K * e / 4, 'RelTol', 1e-14);
verifyEqual(tc, q.VoutExact, Vin * x / (2 * (2 + x)), 'RelTol', 1e-12);
verifyEqual(tc, q.linearityError, (q.Vout - q.VoutExact) / q.VoutExact, 'RelTol', 1e-12);
verifyEqual(tc, q.linearityError, x / 2, 'RelTol', 1e-9);             % (2 + x)/2 − 1
verifyEqual(tc, q.epsIndicated, e, 'RelTol', 1e-14);
verifyEqual(tc, q.bridgeFactor, 1);
verifyEqual(tc, TensorAndCriteriaEngine.bridgeStrain('quart', K, Vin, q.Vout), e, 'RelTol', 1e-14);
% Demi-pont (flexion : ε2 = −ε1) : linéaire exact
d = TensorAndCriteriaEngine.wheatstone('demi', K, Vin, [e, -e]);
verifyEqual(tc, d.Vout, Vin * K * 2 * e / 4, 'RelTol', 1e-14);
verifyEqual(tc, d.VoutExact, d.Vout, 'RelTol', 1e-12);
verifyEqual(tc, d.epsMeasured, e, 'RelTol', 1e-14);
verifyEqual(tc, d.effectiveFactor, 2, 'RelTol', 1e-14);
verifyEqual(tc, TensorAndCriteriaEngine.bridgeStrain('demi', K, Vin, d.Vout), e, 'RelTol', 1e-14);
% Demi-pont « Poisson » : facteur 1 + ν
dp = TensorAndCriteriaEngine.wheatstone('demi', K, Vin, [e, -nu * e]);
verifyEqual(tc, dp.effectiveFactor, 1 + nu, 'RelTol', 1e-14);
verifyEqual(tc, TensorAndCriteriaEngine.bridgeStrain('demi', K, Vin, dp.Vout, 1 + nu), e, 'RelTol', 1e-14);
% Pont complet (ε1 = −ε2 = ε3 = −ε4) : Vout = Vin·K·ε, linéaire exact
f = TensorAndCriteriaEngine.wheatstone('complet', K, Vin, [e, -e, e, -e]);
verifyEqual(tc, f.Vout, Vin * K * e, 'RelTol', 1e-14);
verifyEqual(tc, f.VoutExact, Vin * x, 'RelTol', 1e-12);
verifyEqual(tc, f.bridgeFactor, 4);
verifyEqual(tc, TensorAndCriteriaEngine.bridgeStrain('complet', K, Vin, f.Vout), e, 'RelTol', 1e-14);
verifyEqual(tc, f.eps, [e, -e, e, -e]);
% Compensation : deux jauges adjacentes de même déformation (thermique) → Vout = 0
z = TensorAndCriteriaEngine.wheatstone('demi', K, Vin, [e, e]);
verifyEqual(tc, z.Vout, 0, 'AbsTol', 1e-18);
verifyEqual(tc, z.VoutExact, 0, 'AbsTol', 1e-18);
verifyTrue(tc, isnan(z.linearityError));
verifyTrue(tc, isnan(z.effectiveFactor) || z.effectiveFactor == 0);
% Réciproque vectorisée et noms alternatifs
verifyEqual(tc, TensorAndCriteriaEngine.bridgeStrain("full", K, Vin, [f.Vout, -f.Vout]), [e, -e], 'RelTol', 1e-14);
% Erreurs
verifyError(tc, @() TensorAndCriteriaEngine.wheatstone('triple', K, Vin, e), 'MecaStruct:TensorAndCriteriaEngine:badConfig');
verifyError(tc, @() TensorAndCriteriaEngine.wheatstone('quart', K, Vin, [e, e]), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.wheatstone('demi', K, Vin, e), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.wheatstone('complet', K, Vin, [e e e e e]), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.wheatstone('quart', K, -1, e), 'MecaStruct:TensorAndCriteriaEngine:badInput');
verifyError(tc, @() TensorAndCriteriaEngine.bridgeStrain(3, K, Vin, 1e-3), 'MecaStruct:TensorAndCriteriaEngine:badConfig');
end

function testRosette45(tc)
E = 210e9; nu = 0.3;
% État de contraintes planes connu → déformations → lectures des jauges → état retrouvé
sxx = 150e6; syy = -60e6; sxy = 45e6;
ps = TensorAndCriteriaEngine.planeStress(sxx, syy, sxy, E, nu);
epsAt = @(th) (ps.exx + ps.eyy) / 2 + (ps.exx - ps.eyy) / 2 * cos(2 * th) + ps.exy * sin(2 * th);
e1 = epsAt(0); e2 = epsAt(pi / 2); e3 = epsAt(pi / 4);
r = TensorAndCriteriaEngine.rosette45(e1, e2, e3, E, nu);
verifyEqual(tc, r.exx, ps.exx, 'RelTol', 1e-12);
verifyEqual(tc, r.eyy, ps.eyy, 'RelTol', 1e-12);
verifyEqual(tc, r.exy, ps.exy, 'RelTol', 1e-12);
verifyEqual(tc, r.exy, e3 - (e1 + e2) / 2, 'RelTol', 1e-14);
verifyEqual(tc, r.gxy, ps.gxy, 'RelTol', 1e-12);
verifyEqual(tc, [r.sxx, r.syy, r.sxy], [sxx, syy, sxy], 'RelTol', 1e-10);
verifyEqual(tc, r.ezz, ps.ezz, 'RelTol', 1e-10);
p2 = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy);
verifyEqual(tc, [r.sigmaI, r.sigmaII], [p2.sigma1, p2.sigma2], 'RelTol', 1e-10);
verifyEqual(tc, r.thetaP, p2.thetaP, 'AbsTol', 1e-12);
verifyEqual(tc, r.tauMax2D, p2.rho, 'RelTol', 1e-10);
c = TensorAndCriteriaEngine.criteria([r.sigmaI, r.sigmaII], 235e6);
verifyEqual(tc, r.sigmaVM, c.sigmaEqVM, 'RelTol', 1e-12);
verifyEqual(tc, r.sigmaTresca, c.sigmaEqTresca, 'RelTol', 1e-12);
verifyEqual(tc, r.principal3D, c.pr, 'RelTol', 1e-14);
verifyEqual(tc, r.mohr.center, (ps.exx + ps.eyy) / 2, 'RelTol', 1e-12);
verifyEqual(tc, r.mohr.radius, hypot((ps.exx - ps.eyy) / 2, ps.exy), 'RelTol', 1e-12);
verifyEqual(tc, r.mohr.centerStress, p2.delta, 'RelTol', 1e-10);
verifyEqual(tc, r.mohr.radiusStress, p2.rho, 'RelTol', 1e-10);
verifyLessThan(tc, r.checkResidual, 1e-16);          % lectures ~1e-4 : écart relatif < 1e-12
verifyEqual(tc, r.readings, [e1, e2, e3]);
verifyEqual(tc, r.anglesDeg, [0, 90, 45]);
verifyEqual(tc, r.strain2D.eps1, r.epsI, 'RelTol', 1e-14);
verifyEqual(tc, r.stress2D.sigma1, r.sigmaI, 'RelTol', 1e-12);
% Cas d'école en déformations : εxx = 600, εyy = −200, εxy = 250 µdéf
rk = TensorAndCriteriaEngine.rosette45(600e-6, -200e-6, 450e-6);
verifyEqual(tc, rk.exy, 250e-6, 'RelTol', 1e-12);
verifyEqual(tc, [rk.epsI, rk.epsII], (200 + [1, -1] * sqrt(400^2 + 250^2)) * 1e-6, 'RelTol', 1e-12);
verifyEqual(tc, rk.thetaP, 0.5 * atan2(500, 800), 'AbsTol', 1e-14);
verifyEqual(tc, rk.gammaMax, 2 * sqrt(400^2 + 250^2) * 1e-6, 'RelTol', 1e-12);
% Sans matériau : contraintes non calculées
verifyTrue(tc, isnan(rk.sxx) && isnan(rk.sigmaVM));
verifyEmpty(tc, rk.stress2D);
verifyError(tc, @() TensorAndCriteriaEngine.rosette45(1e-4, 0, 0, E, 0.6), 'MecaStruct:TensorAndCriteriaEngine:badMaterial');
end

function testRosette60(tc)
E = 70e9; nu = 0.33;
sxx = -80e6; syy = 35e6; sxy = -25e6;
ps = TensorAndCriteriaEngine.planeStress(sxx, syy, sxy, E, nu);
epsAt = @(th) (ps.exx + ps.eyy) / 2 + (ps.exx - ps.eyy) / 2 * cos(2 * th) + ps.exy * sin(2 * th);
e0 = epsAt(0); e60 = epsAt(pi / 3); e120 = epsAt(2 * pi / 3);
r = TensorAndCriteriaEngine.rosette60(e0, e60, e120, E, nu);
verifyEqual(tc, [r.exx, r.eyy, r.exy], [ps.exx, ps.eyy, ps.exy], 'RelTol', 1e-12);
verifyEqual(tc, [r.sxx, r.syy, r.sxy], [sxx, syy, sxy], 'RelTol', 1e-10);
p2 = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy);
verifyEqual(tc, [r.sigmaI, r.sigmaII], [p2.sigma1, p2.sigma2], 'RelTol', 1e-10);
verifyLessThan(tc, r.checkResidual, 1e-16);          % lectures ~1e-4 : écart relatif < 1e-12
verifyEqual(tc, r.anglesDeg, [0, 60, 120]);
% Cohérence des deux rosettes sur le même état
r45 = TensorAndCriteriaEngine.rosette45(e0, epsAt(pi / 2), epsAt(pi / 4), E, nu);
verifyEqual(tc, [r45.sigmaI, r45.sigmaII, r45.thetaP], [r.sigmaI, r.sigmaII, r.thetaP], 'RelTol', 1e-10);
end

%% =====================================================================================
%  Format des sorties, LaTeX et erreurs générales
%  =====================================================================================
function testFormatReportLatex(tc)
% Aucun avertissement pendant les calculs (ni à la construction des chaînes)
res = verifyWarningFree(tc, @() allResults(tc));
names = fieldnames(res);
% Matrices LaTeX : lignes séparées par « \\ » (et non « \ »)
verifyTrue(tc, contains(res.planeStrain.latex{3}, '80.769 \end{array}') && ...
    numel(strfind(res.planeStrain.latex{3}, ' \\ ')) == 4);
verifyTrue(tc, contains(res.principalNum.latex{1}, ' \\ '));
verifyTrue(tc, contains(res.facet.latex{1}, ',\ '));
for i = 1:numel(names)
    r = res.(names{i});
    verifyTrue(tc, isfield(r, 'report') && isfield(r, 'latex'), names{i});
    verifyTrue(tc, iscell(r.report) && iscolumn(r.report) && ~isempty(r.report), [names{i} ' : report']);
    verifyTrue(tc, all(cellfun(@(s) ischar(s) && (isrow(s) || isempty(s)), r.report)), [names{i} ' : report char']);
    verifyTrue(tc, iscell(r.latex) && iscolumn(r.latex) && ~isempty(r.latex), [names{i} ' : latex']);
    verifyTrue(tc, all(cellfun(@(s) ischar(s) && isrow(s), r.latex)), [names{i} ' : latex char']);
end
end

function testRenduLatex(tc)
res = allResults(tc);
names = fieldnames(res);
forbidden = '\\iint|\\iiint|\\implies|\\text\{|\\dfrac|\\tfrac|\\boldsymbol|\\geqslant|\\leqslant|pmatrix|bmatrix|\{align|\{cases';
fig = figure('Visible', 'off');
cleaner = onCleanup(@() close(fig));
ax = axes(fig);
for i = 1:numel(names)
    lat = res.(names{i}).latex;
    for k = 1:numel(lat)
        s = lat{k};
        lbl = sprintf('%s{%d} : %s', names{i}, k, s);
        verifyTrue(tc, all(double(s) < 128), ['Caractère non ASCII : ' lbl]);
        verifyLessThan(tc, numel(s), 1000, lbl);
        verifyEqual(tc, nnz(s == '$'), 2, ['Délimiteurs $ : ' lbl]);
        verifyTrue(tc, s(1) == '$' && s(end) == '$', ['Délimiteurs $ : ' lbl]);
        verifyEmpty(tc, regexp(s, forbidden, 'once'), ['Commande LaTeX interdite : ' lbl]);
        lastwarn('');
        h = text(ax, 0.02, 0.5, s, 'Interpreter', 'latex');
        drawnow;
        [w, id] = lastwarn;
        verifyEmpty(tc, w, sprintf('Rendu LaTeX en échec (%s) : %s', id, lbl));
        delete(h);
    end
end
end

function testErreursEntrees(tc)
id = @(s) ['MecaStruct:TensorAndCriteriaEngine:' s];
verifyError(tc, @() TensorAndCriteriaEngine.principal([1 2 0; 3 4 0; 0 0 1]), id('notSymmetric'));
verifyError(tc, @() TensorAndCriteriaEngine.principal(ones(4)), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.principal([1 NaN 0; NaN 1 0; 0 0 1]), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.principal('abc'), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.plane2D('a', 0, 0), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.plane2D([1 2], 0, 0), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.plane2D(1, 0, 0, NaN), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.plane2DStrain(1e-3, 0, 1i), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.mohr3D([1 2 3 4]), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.yieldLoci(0), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.planeStrain(1e-3, 0, 0, 210e9, 0.7), id('badMaterial'));
verifyError(tc, @() TensorAndCriteriaEngine.complianceOrthotropic(42), id('badInput'));
verifyError(tc, @() TensorAndCriteriaEngine.voigtToTensor([1 2 3 4 5 6], 2), id('badKind'));
% Entrées tolérées : tenseur 2x2 (complété par des zéros)
r2 = TensorAndCriteriaEngine.principal([100e6, 20e6; 20e6, -30e6], false);
verifyEqual(tc, r2.sigma(3, :), [0, 0, 0]);
pl = TensorAndCriteriaEngine.plane2D(100e6, -30e6, 20e6);
verifyEqual(tc, sort([r2.sigmaI, r2.sigmaII, r2.sigmaIII], 'descend'), pl.principal3D, 'RelTol', 1e-12);
end

%% =====================================================================================
%  Fonctions utilitaires
%  =====================================================================================
function res = allResults(tc)
%ALLRESULTS Jeu de résultats couvrant toutes les méthodes qui renvoient report/latex.
sig = [120, 30, -20; 30, -40, 10; -20, 10, 25] * 1e6;
res = struct();
res.principalSym = TensorAndCriteriaEngine.principal(sig, tc.TestData.hasSym);
res.principalNum = TensorAndCriteriaEngine.principal(sig, false);
res.principalHydro = TensorAndCriteriaEngine.principal(-50e6 * eye(3), false);
res.principalZero = TensorAndCriteriaEngine.principal(zeros(3), false);
res.facet = TensorAndCriteriaEngine.facet(sig, [1 2 2]);
res.facetT = TensorAndCriteriaEngine.facet(sig, [1 2 2], [1 0 0]);
res.plane2D = TensorAndCriteriaEngine.plane2D(120e6, -40e6, 30e6, pi / 6);
res.plane2DVec = TensorAndCriteriaEngine.plane2D(120e6, -40e6, 30e6, linspace(0, pi, 7));
res.plane2DStrain = TensorAndCriteriaEngine.plane2DStrain(500e-6, -200e-6, 150e-6, pi / 8);
res.plane2DStrainVec = TensorAndCriteriaEngine.plane2DStrain(500e-6, -200e-6, 150e-6, [0 1 2]);
res.mohr3D = TensorAndCriteriaEngine.mohr3D([200e6, 50e6, -100e6]);
res.criteriaOK = TensorAndCriteriaEngine.criteria([200e6, 50e6, -100e6], 355e6, 1.1, 490e6);
res.criteriaKO = TensorAndCriteriaEngine.criteria([400e6, 50e6, -100e6], 235e6, 1.5);
res.criteriaZero = TensorAndCriteriaEngine.criteria([0 0 0], 235e6);
res.yieldLoci = TensorAndCriteriaEngine.yieldLoci(235e6, 1.5, 340e6);
res.planeStress = TensorAndCriteriaEngine.planeStress(100e6, -50e6, 40e6, 70e9, 0.33);
res.planeStressVec = TensorAndCriteriaEngine.planeStress([100e6, 0], -50e6, 40e6, 70e9, 0.33);
res.planeStrain = TensorAndCriteriaEngine.planeStrain(400e-6, -100e-6, 300e-6, 210e9, 0.3);
res.gauge = TensorAndCriteriaEngine.gauge(2.1, 500e-6, 120);
res.gaugeVec = TensorAndCriteriaEngine.gauge(2.1, [500e-6, -1e-4]);
res.wheatQuart = TensorAndCriteriaEngine.wheatstone('quart', 2, 10, 1e-3);
res.wheatDemi = TensorAndCriteriaEngine.wheatstone('demi', 2, 10, [1e-3, -1e-3]);
res.wheatComplet = TensorAndCriteriaEngine.wheatstone('complet', 2, 10, [1e-3, -1e-3, 1e-3, -1e-3]);
res.wheatNul = TensorAndCriteriaEngine.wheatstone('demi', 2, 10, [1e-3, 1e-3]);
res.rosette45 = TensorAndCriteriaEngine.rosette45(600e-6, -200e-6, 450e-6, 210e9, 0.3);
res.rosette45NoMat = TensorAndCriteriaEngine.rosette45(600e-6, -200e-6, 450e-6);
res.rosette60 = TensorAndCriteriaEngine.rosette60(600e-6, 100e-6, -150e-6, 70e9, 0.33);
end
