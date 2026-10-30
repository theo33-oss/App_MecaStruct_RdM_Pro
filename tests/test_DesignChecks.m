function tests = test_DesignChecks
%TEST_DESIGNCHECKS Tests de DesignChecks : Eurocode 3 simplifié (IPE 300 de référence) et fatigue de Goodman.
%   Application de Théo Brun, basée sur son cours de Résistance des Matériaux.
tests = functiontests(localfunctions);
end

function d = ipe300()
dm = DataManager([tempname '.mat']);
d = DesignChecks.ibeamDims(GeometryEngine.fromProfile(dm.getProfile('IPE', 'IPE 300')));
end

function testIPE300Catalogue(testCase)
d = ipe300();
verifyEqual(testCase, d.h, 0.3, 'AbsTol', 1e-9);
r = DesignChecks.ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 50e3);
verifyEqual(testCase, r.class.class, 1);
verifyEqual(testCase, r.Wpl, 628.4e-6, 'RelTol', 5e-3, 'Wpl,y du catalogue : 628,4 cm³.');
verifyEqual(testCase, r.Av, 2568e-6, 'RelTol', 1e-2, 'Av du catalogue : 25,68 cm².');
verifyEqual(testCase, r.Mc, 147.7e3, 'RelTol', 5e-3, 'Mpl,Rd = 147,7 kN·m en S235.');
verifyFalse(testCase, r.reduced);
verifyTrue(testCase, r.ok);
verifyEqual(testCase, r.ratioM, 100e3 / r.Mc, 'RelTol', 1e-12);
end

function testInteractionTranchant(testCase)
d = ipe300();
r0 = DesignChecks.ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 0);
r = DesignChecks.ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 0.8 * r0.Vpl);
verifyTrue(testCase, r.reduced);
verifyEqual(testCase, r.rho, (2 * 0.8 - 1)^2, 'AbsTol', 1e-12);
verifyLessThan(testCase, r.MRd, r0.Mc);
r2 = DesignChecks.ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.1, 100e3, 0);
verifyEqual(testCase, r2.Mc, r0.Mc / 1.1, 'RelTol', 1e-12, 'γM0 diminue la résistance.');
end

function testClasses(testCase)
% classe 3 : aile c/tf = 12 (entre 10ε et 14ε) → module élastique
d3 = struct('h', 0.4, 'b', 0.25, 'tw', 0.01, 'tf', 0.01, 'r', 0);
r = DesignChecks.ec3Bending(d3, 2 * 0.25 * 0.01 + 0.38 * 0.01, 1e-4, 235e6, 1.0, 50e3, 10e3);
verifyEqual(testCase, r.class.class, 3);
verifyEqual(testCase, r.W, r.Wel);
% classe 4 refusée
d4 = struct('h', 0.5, 'b', 0.3, 'tw', 0.01, 'tf', 0.01, 'r', 0);
verifyError(testCase, @() DesignChecks.ec3Bending(d4, 0.01, 1e-4, 235e6, 1.0, 1e3, 1e3), 'MecaStruct:Design:class4');
% un acier plus résistant durcit les limites (ε plus petit)
c = DesignChecks.classify(ipe300(), 460e6, 0, 0, 5381e-6, 8356e-8);
verifyLessThan(testCase, c.eps, 1);
end

function testSectionNonSupportee(testCase)
verifyError(testCase, @() DesignChecks.ibeamDims(struct('type', 'rectangle')), 'MecaStruct:Design:unsupportedSection');
dm = DataManager([tempname '.mat']);
upn = cellstr(dm.listProfiles('UPN'));
sec = GeometryEngine.fromProfile(dm.getProfile('UPN', upn{1}));
verifyError(testCase, @() DesignChecks.ibeamDims(sec), 'MecaStruct:Design:unsupportedSection');
end

function testDeversementIPE300(testCase)
% Calcul à la main (IPE 300, S235, E = 210 GPa, G = 81 GPa, Iz = 603,8 cm⁴, It = 20,1 cm⁴, Lcr = 4 m, C1 = 1) :
% Iw ≈ 126·10³ cm⁶, Mcr ≈ 159,8 kN·m, λ̄LT ≈ 0,96, courbe b (h/b = 2), χLT ≈ 0,72, Mb,Rd ≈ 107 kN·m.
d = ipe300();
b = DesignChecks.ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 50e3, 10e3);
r = DesignChecks.ec3LateralTorsional(d, true, b.W, 235e6, 1.0, 210e9, 81e9, 603.8e-8, 20.1e-8, 4, 1, 50e3);
verifyEqual(testCase, r.Mcr, 159.8e3, 'RelTol', 3e-2);
verifyEqual(testCase, r.lambda, 0.96, 'RelTol', 3e-2);
verifyEqual(testCase, r.curve, 'b');
verifyEqual(testCase, r.chi, 0.72, 'RelTol', 3e-2);
verifyEqual(testCase, r.MbRd, 107e3, 'RelTol', 3e-2);
verifyLessThan(testCase, r.MbRd, b.Mc, 'Le déversement réduit la résistance.');
% maintien latéral serré : plus de réduction
r2 = DesignChecks.ec3LateralTorsional(d, true, b.W, 235e6, 1.0, 210e9, 81e9, 603.8e-8, 20.1e-8, 1, 1, 50e3);
verifyEqual(testCase, r2.chi, 1, 'AbsTol', 0.1);
verifyGreaterThan(testCase, r2.MbRd, r.MbRd);
% un moment non uniforme (C1 > 1) augmente Mcr
r3 = DesignChecks.ec3LateralTorsional(d, true, b.W, 235e6, 1.0, 210e9, 81e9, 603.8e-8, 20.1e-8, 4, 1.77, 50e3);
verifyEqual(testCase, r3.Mcr, 1.77 * r.Mcr, 'RelTol', 1e-12);
% choix de courbe : laminé élancé → c ; soudé → c / d
dt = struct('h', 0.6, 'b', 0.2, 'tw', 0.01, 'tf', 0.015, 'r', 0);
verifyEqual(testCase, DesignChecks.ec3LateralTorsional(dt, true, 2e-3, 235e6, 1, 210e9, 81e9, 1e-5, 1e-7, 3, 1, 1e3).curve, 'c');
verifyEqual(testCase, DesignChecks.ec3LateralTorsional(dt, false, 2e-3, 235e6, 1, 210e9, 81e9, 1e-5, 1e-7, 3, 1, 1e3).curve, 'd');
verifyEqual(testCase, DesignChecks.ec3LateralTorsional(d, false, b.W, 235e6, 1, 210e9, 81e9, 603.8e-8, 20.1e-8, 4, 1, 1e3).curve, 'c');
verifyError(testCase, @() DesignChecks.ec3LateralTorsional(d, true, b.W, 235e6, 1, 210e9, 81e9, 603.8e-8, 20.1e-8, 0, 1, 1e3), ...
    'MecaStruct:Design:invalidInput');
end

function testFlambementIPE300(testCase)
% À la main (IPE 300, S235, Lcr = 3 m, E = 210 GPa) : axe faible Ncr = 1390 kN, λ̄ = 0,954, courbe b (h/b = 2, tf ≤ 40 mm),
% Φ = 1,083, χ = 0,627, Nb,Rd = 792 kN ; axe fort λ̄ = 0,256, courbe a, χ = 0,988.
d = ipe300();
r = DesignChecks.ec3FlexuralBuckling(d, true, 5381e-6, 8356e-8, 603.8e-8, 3, 235e6, 210e9, 1.0, 500e3);
verifyEqual(testCase, r.governing, 2, 'L''axe faible gouverne.');
z = r.axes(2);
verifyEqual(testCase, z.Ncr, 1390e3, 'RelTol', 1e-2);
verifyEqual(testCase, z.lambda, 0.954, 'RelTol', 1e-2);
verifyEqual(testCase, z.curve, 'b');
verifyEqual(testCase, z.chi, 0.627, 'RelTol', 1e-2);
verifyEqual(testCase, r.NbRd, 792e3, 'RelTol', 1e-2);
verifyEqual(testCase, r.axes(1).curve, 'a');
verifyFalse(testCase, r.axes(1).needed, 'NEd/Ncr = 0,026 ≤ 0,04 : pas de vérification sur l''axe fort (6.3.1.2(4)).');
r1000 = DesignChecks.ec3FlexuralBuckling(d, true, 5381e-6, 8356e-8, 603.8e-8, 3, 235e6, 210e9, 1.0, 1000e3);
verifyTrue(testCase, r1000.axes(1).needed);
verifyEqual(testCase, r1000.axes(1).chi, 0.988, 'RelTol', 1e-2);
verifyEqual(testCase, r.ratio, 500e3 / r.NbRd, 'RelTol', 1e-12);
% barre trapue : pas de vérification (λ̄ ≤ 0,2)
rs = DesignChecks.ec3FlexuralBuckling(d, true, 5381e-6, 8356e-8, 603.8e-8, 0.3, 235e6, 210e9, 1.0, 500e3);
verifyEqual(testCase, rs.axes(2).chi, 1);
verifyFalse(testCase, rs.axes(2).needed);
verifyError(testCase, @() DesignChecks.ec3FlexuralBuckling(d, true, 5381e-6, 8356e-8, 603.8e-8, 3, 460e6, 210e9, 1.0, 1e3), ...
    'MecaStruct:Design:unsupportedSteel');
% soudé : une courbe plus défavorable
rw = DesignChecks.ec3FlexuralBuckling(d, false, 5381e-6, 8356e-8, 603.8e-8, 3, 235e6, 210e9, 1.0, 500e3);
verifyEqual(testCase, rw.axes(2).curve, 'c');
verifyLessThan(testCase, rw.NbRd, r.NbRd);
end

function testFlexionEffortNormal(testCase)
d = ipe300();
b = DesignChecks.ec3Bending(d, 5381e-6, 8356e-8, 235e6, 1.0, 100e3, 0);
% N faible : aucune réduction (6.33 et 6.34 vérifiées)
r1 = DesignChecks.ec3AxialBending(d, b, 5381e-6, 235e6, 1.0, 200e3, 100e3);
verifyTrue(testCase, r1.free);
verifyEqual(testCase, r1.MNRd, b.Mc, 'RelTol', 1e-12);
% N = 400 kN : n = 0,316 ; a = 0,4035 ; MN = Mpl·(1 − n)/(1 − 0,5·a) = 0,857·Mpl
r2 = DesignChecks.ec3AxialBending(d, b, 5381e-6, 235e6, 1.0, 400e3, 100e3);
verifyFalse(testCase, r2.free);
verifyEqual(testCase, r2.n, 0.3163, 'RelTol', 1e-3);
verifyEqual(testCase, r2.a, 0.4035, 'RelTol', 1e-3);
verifyEqual(testCase, r2.MNRd / b.Mc, 0.8565, 'RelTol', 2e-3);
% N = Npl : plus de capacité en flexion
r3 = DesignChecks.ec3AxialBending(d, b, 5381e-6, 235e6, 1.0, 5381e-6 * 235e6, 1e3);
verifyFalse(testCase, r3.ok);
% classe 3 : contrainte élastique N/A + M/Wel
d3 = struct('h', 0.4, 'b', 0.25, 'tw', 0.01, 'tf', 0.01, 'r', 0);
A3 = 2 * 0.25 * 0.01 + 0.38 * 0.01;
b3 = DesignChecks.ec3Bending(d3, A3, 1e-4, 235e6, 1.0, 50e3, 10e3);
r4 = DesignChecks.ec3AxialBending(d3, b3, A3, 235e6, 1.0, 100e3, 50e3);
verifyFalse(testCase, r4.class12);
verifyEqual(testCase, r4.sigma, 100e3 / A3 + 50e3 / b3.Wel, 'RelTol', 1e-12);
end

function testGoodman(testCase)
r = DesignChecks.goodman(100e6, -1, 1, 400e6, 1, 1);
verifyEqual(testCase, r.Se, 200e6, 'RelTol', 1e-12);
verifyEqual(testCase, r.n, 2, 'RelTol', 1e-12, 'Alterné : n = Se / σa.');
r = DesignChecks.goodman(100e6, 0, 1, 400e6, 1, 1);
verifyEqual(testCase, r.n, 1 / (50 / 200 + 50 / 400), 'RelTol', 1e-12);
r = DesignChecks.goodman(100e6, -1, 2, 400e6, 0.8, 1);
verifyEqual(testCase, r.n, 0.8 * 200e6 / (2 * 100e6), 'RelTol', 1e-12, 'Kf et ka agissent comme attendu.');
verifyError(testCase, @() DesignChecks.goodman(100e6, 1, 1, 400e6, 1, 1), 'MecaStruct:Design:invalidInput');
r0 = DesignChecks.goodman(0, 0, 1, 400e6, 1, 1);
verifyEqual(testCase, r0.n, Inf);
end

function testInteractionAnnexeB(testCase)
% Valeurs recalculées à la main : A = 1e-2 m², W = 1e-3 m³, fy = 235 MPa, N = 500 kN, M = 100 kN·m, Cmy = CmLT = 0,9
buck = struct('axes', struct('chi', {0.8, 0.5}, 'lambda', {0.8, 1.2}));
ltb = struct('chi', 0.7);
r = DesignChecks.ec3Interaction(1, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 500e3, 100e3, 0.9, 0.9);
verifyEqual(testCase, r.nY, 0.265957, 'RelTol', 1e-5);
verifyEqual(testCase, r.nZ, 0.425532, 'RelTol', 1e-5);
verifyEqual(testCase, r.kyy, 1.043617, 'RelTol', 1e-5, 'kyy = min(0,9(1+0,6·nY) ; 0,9(1+0,8·nY)) en classe 1 avec λ̄y = 0,8.');
verifyEqual(testCase, r.kzy, 0.934534, 'RelTol', 1e-5);
verifyEqual(testCase, r.ratio61, 0.9004, 'RelTol', 1e-3);
verifyEqual(testCase, r.ratio62, 0.9936, 'RelTol', 1e-3);
verifyTrue(testCase, r.ok);
r2 = DesignChecks.ec3Interaction(1, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 600e3, 100e3, 0.9, 0.9);
verifyFalse(testCase, r2.ok, 'Plus de compression : l''interaction dépasse 1.');
verifyError(testCase, @() DesignChecks.ec3Interaction(1, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 5e5, 1e5, 1.2, 0.9), 'MecaStruct:Design:invalidInput');
verifyError(testCase, @() DesignChecks.ec3Interaction(4, buck, ltb, 1e-2, 1e-3, 235e6, 1.0, 5e5, 1e5, 0.9, 0.9), 'MecaStruct:Design:class4');
end

function testVoilementAme(testCase)
% Âme élancée soudée : hw = 0,96 m, tw = 6 mm (hw/tw = 160 > 72ε/η = 60) ; λ̄w = 1,852 ; χw = 1,37/(0,7 + λ̄w)
d = struct('h', 1.0, 'b', 0.3, 'tw', 0.006, 'tf', 0.02, 'r', 0);
w = DesignChecks.ec3WebShear(d, 235e6, 1.0, 300e3);
verifyTrue(testCase, w.needed);
verifyEqual(testCase, w.lambda, 0.96 / (86.4 * 0.006), 'RelTol', 1e-12);
verifyEqual(testCase, w.chi, 1.37 / (0.7 + w.lambda), 'RelTol', 1e-12);
verifyEqual(testCase, w.VbRd, 419.5e3, 'RelTol', 1e-3);
verifyEqual(testCase, w.ratio, 300e3 / w.VbRd, 'RelTol', 1e-12);
% profilé laminé : sans objet (IPE 300 : hw/tw = 35)
w2 = DesignChecks.ec3WebShear(struct('h', 0.3, 'b', 0.15, 'tw', 0.0071, 'tf', 0.0107, 'r', 0.015), 235e6, 1.0, 100e3);
verifyFalse(testCase, w2.needed);
verifyTrue(testCase, w2.ok);
end

function testClasseSousCompression(testCase)
% IPE 300 : âme c/tw = 248,6 / 7,1 = 35,0. Flexion seule : classe 1 (72ε). Compression pure (ψ = 1, α = 1) : 33ε, 38ε → classe 2.
d = ipe300();
A = 5381e-6; Iz = 8356e-8;
c0 = DesignChecks.classify(d, 235e6, 0, 1e3, A, Iz);
verifyEqual(testCase, c0.psi, -1, 'AbsTol', 1e-12);
verifyEqual(testCase, c0.classWeb, 1);
c1 = DesignChecks.classify(d, 235e6, 0.5 * A * 235e6, 0, A, Iz);
verifyEqual(testCase, c1.alpha, 1, 'AbsTol', 1e-12);
verifyEqual(testCase, c1.classWeb, 2);
% compression et flexion avec ψ = −0,2 (α = 0,833) : limite 396ε/(13α − 1) ≈ 40,3ε, donc encore classe 1
sC = 1e6 / A;
sM = 1.5 * sC;
c2 = DesignChecks.classify(d, 235e6, 1e6, sM * Iz / ((d.h - 2 * d.tf) / 2), A, Iz);
verifyEqual(testCase, c2.psi, -0.2, 'RelTol', 1e-9);
verifyEqual(testCase, c2.alpha, 1 / 1.2, 'RelTol', 1e-9);
verifyEqual(testCase, c2.classWeb, 1);
end

function testLongueurFortSeparee(testCase)
% Lcr,y (axe fort) et Lcr,z (axe faible) distincts : Ncr = π²·E·I/L² pour chaque axe.
d = ipe300();
r = DesignChecks.ec3FlexuralBuckling(d, true, 5381e-6, 8356e-8, 603.8e-8, [6 3], 235e6, 210e9, 1.0, 100e3);
verifyEqual(testCase, r.axes(1).Ncr, pi^2 * 210e9 * 8356e-8 / 6^2, 'RelTol', 1e-12);
verifyEqual(testCase, r.axes(2).Ncr, pi^2 * 210e9 * 603.8e-8 / 3^2, 'RelTol', 1e-12);
end

function testCourbeTresEpaisse(testCase)
% Laminé, h/b = 2,4 et tf = 120 mm : non tabulé, courbe d sur les deux axes (α = 0,76).
d = struct('h', 0.6, 'b', 0.25, 'tw', 0.02, 'tf', 0.12, 'r', 0);
r = DesignChecks.ec3FlexuralBuckling(d, true, 0.05, 1e-3, 1e-2, 3, 235e6, 210e9, 1.0, 0);
verifyEqual(testCase, r.axes(1).curve, 'd');
verifyEqual(testCase, r.axes(2).curve, 'd');
verifyEqual(testCase, r.axes(2).alpha, 0.76, 'AbsTol', 1e-12);
end
