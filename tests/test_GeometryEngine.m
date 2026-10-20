function tests = test_GeometryEngine
%TEST_GEOMETRYENGINE Tests unitaires du moteur GeometryEngine (propriétés des sections droites).
%   Lancer : r = runtests('tests/test_GeometryEngine.m');
%   Couvre : formules fermées (rectangle, disque, couronne, rectangle creux, I, T, U, L),
%   analytique ≡ intégrale symbolique ≡ intégrale numérique (1e-9) pour tous les types, Huygens,
%   moments statiques Q(y) et largeurs b(y) exacts, facteurs de cisaillement (Jourawski, énergie),
%   profilés (catalogue, comparaison), contours, validité des chaînes LaTeX, erreurs attendues.
tests = functiontests(localfunctions);
end

%% ---------------------------------------------------------------------------------------------
%  Préparation
%  ---------------------------------------------------------------------------------------------

function setupOnce(tc)
root = fileparts(fileparts(mfilename('fullpath')));
addpath(root);
tc.TestData.hasSym = GeometryEngine.hasSymbolic();
tc.TestData.secs = allSections();
end

function S = allSections()
% Jeu de sections couvrant tous les types (dimensions en m).
S = struct('name', {}, 'sec', {});
S(end+1).name = 'rectangle';
S(end).sec = struct('type', 'rectangle', 'b', 0.1, 'h', 0.2);
S(end+1).name = 'disque';
S(end).sec = struct('type', 'disque', 'D', 0.1);
S(end+1).name = 'couronne';
S(end).sec = struct('type', 'couronne', 'D', 0.1, 'd', 0.08);
S(end+1).name = 'rectangle_creux';
S(end).sec = struct('type', 'rectangle_creux', 'B', 0.1, 'H', 0.2, 't', 0.01);
S(end+1).name = 'I';
S(end).sec = struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.0056, 'tf', 0.0085);
S(end+1).name = 'T';
S(end).sec = struct('type', 'T', 'h', 0.1, 'b', 0.08, 'tw', 0.008, 'tf', 0.01);
S(end+1).name = 'U';
S(end).sec = struct('type', 'U', 'h', 0.2, 'b', 0.075, 'tw', 0.0085, 'tf', 0.0115);
S(end+1).name = 'L_egal';
S(end).sec = struct('type', 'L', 'h', 0.1, 'b', 0.1, 't', 0.01);
S(end+1).name = 'L_inegal';
S(end).sec = struct('type', 'L', 'h', 0.12, 'b', 0.08, 't', 0.012);
S(end+1).name = 'profile_IPE200';
S(end).sec = ipe200();
S(end+1).name = 'profile_UPN200';
S(end).sec = upn200();
S(end+1).name = 'composite_trou';
S(end).sec = struct('type', 'composite', 'rects', [0 0.2 0 0.02; 0.09 0.11 0.02 0.2], ...
    'holes', [0.02 0.05 0.005 0.015]);
S(end+1).name = 'composite_trou_circulaire';
S(end).sec = struct('type', 'composite', 'rects', [0 0.2 0 0.1], 'diskHoles', [0.13 0.04 0.025]);
S(end+1).name = 'composite_disque';
S(end).sec = struct('type', 'composite', 'rects', [-0.05 0.05 -0.1 0], 'disks', [0 0.03 0.03]);
end

function sec = ipe200()
% IPE 200 (valeurs du catalogue, SI ; Iz = axe fort).
sec = struct('type', 'profile', 'family', 'IPE', 'name', 'IPE 200', 'h', 0.2, 'b', 0.1, ...
    'a', 0.0056, 'e', 0.0085, 'r', 0.012, 'S', 28.5e-4, 'Iz', 1943e-8, 'Iy', 142.4e-8, ...
    'Wz', 194.3e-6, 'Wy', 28.47e-6, 'rz', 0.0826, 'ry', 0.0224, 'mass', 22.4, 'c', NaN);
end

function sec = upn200()
% UPN 200 (valeurs du catalogue, SI ; c = distance dos d'âme → G).
sec = struct('type', 'profile', 'family', 'UPN', 'name', 'UPN 200', 'h', 0.2, 'b', 0.075, ...
    'a', 0.0085, 'e', 0.0115, 'r', 0.0115, 'S', 32.2e-4, 'Iz', 1910e-8, 'Iy', 148e-8, ...
    'Wz', 191e-6, 'Wy', 27e-6, 'rz', 0.077, 'ry', 0.0214, 'mass', 25.3, 'c', 0.0201);
end

function verifyRel(tc, actual, expected, tol, msg)
% Comparaison relative élément par élément (absolue si la valeur attendue est nulle).
if nargin < 5, msg = ''; end
den = max(abs(expected), realmin);
err = abs(actual - expected)./den;
err(expected == 0) = abs(actual(expected == 0));
tc.verifyLessThanOrEqual(max(err(:)), tol, msg);
end

function d = propDiff(A, B)
% Écart relatif maximal entre deux jeux de propriétés (Iyz rapporté à max(Iz, Iy)).
flds = {'S', 'yG', 'zG', 'MO1z', 'MO1y', 'Iz', 'Iy', 'Iyz', 'Ix', 'I1', 'I2', 'rz', 'ry', ...
    'vyTop', 'vyBot', 'vzRight', 'vzLeft', 'Wz', 'Wy'};
Lref = max(A.bbox(2) - A.bbox(1), A.bbox(4) - A.bbox(3));
d = 0;
for k = 1:numel(flds)
    a = A.(flds{k});
    b = B.(flds{k});
    switch flds{k}
        case 'Iyz'
            den = max([abs(a), A.Iz, A.Iy]);
        case {'yG', 'zG', 'vyTop', 'vyBot', 'vzRight', 'vzLeft'}
            den = max(abs(a), Lref);
        case {'MO1z', 'MO1y'}
            den = max(abs(a), A.S*Lref);
        otherwise
            den = abs(a);
    end
    d = max(d, abs(a - b)/den);
end
if A.Iyz ~= 0 || B.Iyz ~= 0
    d = max(d, abs(A.alphaP - B.alphaP));
end
end

%% ---------------------------------------------------------------------------------------------
%  Formules fermées
%  ---------------------------------------------------------------------------------------------

function testRectangleClosedForm(tc)
b = 0.1; h = 0.2;
P = GeometryEngine.analytical(struct('type', 'rectangle', 'b', b, 'h', h));
verifyRel(tc, P.S, b*h, 1e-12);
verifyRel(tc, P.Iz, b*h^3/12, 1e-12);
verifyRel(tc, P.Iy, h*b^3/12, 1e-12);
tc.verifyEqual(P.Iyz, 0);
verifyRel(tc, P.Ix, b*h^3/12 + h*b^3/12, 1e-12);
verifyRel(tc, [P.yG P.zG], [h/2 b/2], 1e-12);
verifyRel(tc, [P.MO1z P.MO1y], [b*h*h/2 b*h*b/2], 1e-12);
verifyRel(tc, [P.I1 P.I2], [b*h^3/12 h*b^3/12], 1e-12);
tc.verifyEqual(P.alphaP, 0);
verifyRel(tc, [P.rz P.ry], [h/sqrt(12) b/sqrt(12)], 1e-12);
verifyRel(tc, [P.vyTop P.vyBot P.vzRight P.vzLeft], [h/2 h/2 b/2 b/2], 1e-12);
verifyRel(tc, [P.Wz P.Wy], [b*h^2/6 h*b^2/6], 1e-12);
tc.verifyEqual(P.method, 'analytique');
tc.verifyEqual(P.kSource, 'cours');
verifyRel(tc, [P.k P.ky], [3/2 5/6], 1e-12);
end

function testRectangleWiderThanTall(tc)
% b > h : l'axe principal 1 (inertie max) est l'axe y, alphaP = pi/2.
P = GeometryEngine.analytical(struct('type', 'rectangle', 'b', 0.3, 'h', 0.1));
verifyRel(tc, P.I1, P.Iy, 1e-12);
verifyRel(tc, P.I2, P.Iz, 1e-12);
verifyRel(tc, P.alphaP, pi/2, 1e-12);
end

function testRectangleSaintVenant(tc)
% beta = J/(a c^3) : valeurs de référence (Timoshenko) 1 -> 0.1406, 2 -> 0.2287, 10 -> 0.3123.
ratios = [1 2 10];
betaRef = [0.1406 0.2287 0.3123];
c = 0.02;
for k = 1:numel(ratios)
    P = GeometryEngine.analytical(struct('type', 'rectangle', 'b', c, 'h', ratios(k)*c));
    beta = P.J/(ratios(k)*c*c^3);
    tc.verifyLessThanOrEqual(abs(beta - betaRef(k)), 2e-4, sprintf('beta(%g)', ratios(k)));
end
% grand allongement : J -> a c^3 / 3 (1 - 0.630 c/a)
P = GeometryEngine.analytical(struct('type', 'rectangle', 'b', 0.001, 'h', 1));
verifyRel(tc, P.J, 1*0.001^3/3*(1 - 192/pi^5*0.001*sum(1./(1:2:199).^5)), 1e-9);
end

function testDisque(tc)
D = 0.1;
P = GeometryEngine.analytical(struct('type', 'disque', 'D', D));
verifyRel(tc, P.S, pi*D^2/4, 1e-12);
verifyRel(tc, [P.Iz P.Iy], [pi*D^4/64 pi*D^4/64], 1e-12);
verifyRel(tc, P.Ix, pi*D^4/32, 1e-12);
verifyRel(tc, P.J, pi*D^4/32, 1e-12);
verifyRel(tc, [P.yG P.zG], [D/2 D/2], 1e-12);
verifyRel(tc, P.Wz, pi*D^3/32, 1e-12);
verifyRel(tc, P.rz, D/4, 1e-12);
tc.verifyEqual(P.alphaP, 0);
end

function testCouronne(tc)
D = 0.1; d = 0.06; m = d/D;
P = GeometryEngine.analytical(struct('type', 'couronne', 'D', D, 'd', d));
verifyRel(tc, P.S, pi*D^2/4*(1 - m^2), 1e-12);
verifyRel(tc, [P.Iz P.Iy], pi*D^4/64*(1 - m^4)*[1 1], 1e-12);
verifyRel(tc, P.Ix, pi*D^4/32*(1 - m^4), 1e-12);
verifyRel(tc, P.J, pi*(D^4 - d^4)/32, 1e-12);
verifyRel(tc, P.Wz, pi*D^3/32*(1 - m^4), 1e-12);
% couronne d = 0 : identique au disque
P0 = GeometryEngine.analytical(struct('type', 'couronne', 'D', D, 'd', 0));
Pd = GeometryEngine.analytical(struct('type', 'disque', 'D', D));
verifyRel(tc, [P0.S P0.Iz P0.Ix], [Pd.S Pd.Iz Pd.Ix], 1e-12);
end

function testRectangleCreux(tc)
B = 0.1; H = 0.2; t = 0.01;
P = GeometryEngine.analytical(struct('type', 'rectangle_creux', 'B', B, 'H', H, 't', t));
verifyRel(tc, P.S, B*H - (B - 2*t)*(H - 2*t), 1e-12);
verifyRel(tc, P.Iz, (B*H^3 - (B - 2*t)*(H - 2*t)^3)/12, 1e-12);
verifyRel(tc, P.Iy, (H*B^3 - (H - 2*t)*(B - 2*t)^3)/12, 1e-12);
Am = (B - t)*(H - t);
pm = 2*((B - t) + (H - t));
verifyRel(tc, P.J, 4*Am^2*t/pm, 1e-12);
tc.verifyEqual(height(P.huygens), 2);
tc.verifyLessThan(P.huygens.S_i(2), 0);
end

function testISection(tc)
h = 0.2; b = 0.1; tw = 0.0056; tf = 0.0085;
P = GeometryEngine.analytical(struct('type', 'I', 'h', h, 'b', b, 'tw', tw, 'tf', tf));
verifyRel(tc, P.S, 2*b*tf + (h - 2*tf)*tw, 1e-12);
verifyRel(tc, P.Iz, (b*h^3 - (b - tw)*(h - 2*tf)^3)/12, 1e-12);
verifyRel(tc, P.Iy, (2*tf*b^3 + (h - 2*tf)*tw^3)/12, 1e-12);
verifyRel(tc, [P.yG P.zG], [h/2 b/2], 1e-12);
tc.verifyEqual(P.Iyz, 0);
verifyRel(tc, P.J, (2*b*tf^3 + (h - 2*tf)*tw^3)/3, 1e-12);
Sw = tw*(h - 2*tf);
verifyRel(tc, [P.k P.ky], [P.S/Sw Sw/P.S], 1e-12);
tc.verifyEqual(P.huygens.Label, {'Aile inférieure'; 'Âme'; 'Aile supérieure'});
end

function testTSection(tc)
h = 0.1; b = 0.08; tw = 0.008; tf = 0.01;
P = GeometryEngine.analytical(struct('type', 'T', 'h', h, 'b', b, 'tw', tw, 'tf', tf));
S = tw*(h - tf) + b*tf;
yG = (tw*(h - tf)^2/2 + b*tf*(h - tf/2))/S;
IO1z = tw*(h - tf)^3/3 + b*(h^3 - (h - tf)^3)/3;
verifyRel(tc, P.S, S, 1e-12);
verifyRel(tc, P.yG, yG, 1e-12);
verifyRel(tc, P.zG, b/2, 1e-12);
verifyRel(tc, P.Iz, IO1z - S*yG^2, 1e-12);
verifyRel(tc, P.Iy, (h - tf)*tw^3/12 + tf*b^3/12, 1e-12);
tc.verifyEqual(P.Iyz, 0);
verifyRel(tc, [P.vyTop P.vyBot], [h - yG, yG], 1e-12);
verifyRel(tc, P.Wz, P.Iz/yG, 1e-12);
tc.verifyEqual(P.kSource, 'numérique');
end

function testUSection(tc)
h = 0.2; b = 0.075; tw = 0.0085; tf = 0.0115;
P = GeometryEngine.analytical(struct('type', 'U', 'h', h, 'b', b, 'tw', tw, 'tf', tf));
S = h*tw + 2*(b - tw)*tf;
zG = (h*tw^2/2 + 2*tf*(b^2 - tw^2)/2)/S;
IO1y = h*tw^3/3 + 2*tf*(b^3 - tw^3)/3;
verifyRel(tc, P.S, S, 1e-12);
verifyRel(tc, P.zG, zG, 1e-12);
verifyRel(tc, P.yG, h/2, 1e-12);
verifyRel(tc, P.Iz, (b*h^3 - (b - tw)*(h - 2*tf)^3)/12, 1e-12);
verifyRel(tc, P.Iy, IO1y - S*zG^2, 1e-12);
verifyRel(tc, [P.vzLeft P.vzRight], [zG, b - zG], 1e-12);
verifyRel(tc, P.Wy, P.Iy/(b - zG), 1e-12);
verifyRel(tc, P.J, (h*tw^3 + 2*(b - tw)*tf^3)/3, 1e-12);
end

function testLSection(tc)
cases = [0.1 0.1 0.01; 0.12 0.08 0.012];
for c = 1:size(cases, 1)
    h = cases(c, 1); b = cases(c, 2); t = cases(c, 3);
    P = GeometryEngine.analytical(struct('type', 'L', 'h', h, 'b', b, 't', t));
    S = t*h + (b - t)*t;
    yG = (t*h^2/2 + (b - t)*t^2/2)/S;
    zG = (h*t^2/2 + t*(b^2 - t^2)/2)/S;
    Iz = t*h^3/3 + (b - t)*t^3/3 - S*yG^2;
    Iy = h*t^3/3 + t*(b^3 - t^3)/3 - S*zG^2;
    Iyz = t^2*h^2/4 + (b^2 - t^2)*t^2/4 - S*yG*zG;
    verifyRel(tc, [P.S P.yG P.zG], [S yG zG], 1e-12);
    verifyRel(tc, [P.Iz P.Iy], [Iz Iy], 1e-12);
    verifyRel(tc, P.Iyz, Iyz, 1e-11);
    tc.verifyLessThan(P.Iyz, 0, 'Iyz < 0 pour une cornière à angle en bas à gauche');
    % invariants des axes principaux
    verifyRel(tc, P.I1 + P.I2, Iz + Iy, 1e-12);
    verifyRel(tc, P.I1*P.I2, Iz*Iy - Iyz^2, 1e-10);
    tc.verifyGreaterThanOrEqual(P.I1, P.I2);
    % I(alpha) = Iz cos^2 + Iy sin^2 - 2 Iyz sin cos : maximum en alphaP
    Ia = @(a) Iz*cos(a).^2 + Iy*sin(a).^2 - 2*Iyz*sin(a).*cos(a);
    verifyRel(tc, Ia(P.alphaP), P.I1, 1e-11);
    verifyRel(tc, Ia(P.alphaP + pi/2), P.I2, 1e-10);
    aa = linspace(-pi/2, pi/2, 2001);
    tc.verifyLessThanOrEqual(max(Ia(aa)), P.I1*(1 + 1e-12));
    verifyRel(tc, P.J, (h*t^3 + (b - t)*t^3)/3, 1e-12);
end
P = GeometryEngine.analytical(struct('type', 'L', 'h', 0.1, 'b', 0.1, 't', 0.01));
verifyRel(tc, P.alphaP, pi/4, 1e-12);
end

%% ---------------------------------------------------------------------------------------------
%  Analytique ≡ intégrale
%  ---------------------------------------------------------------------------------------------

function testAnalyticalEqualsSymbolicIntegral(tc)
tc.assumeTrue(tc.TestData.hasSym, 'Symbolic Math Toolbox indisponible');
secs = tc.TestData.secs;
for k = 1:numel(secs)
    A = GeometryEngine.analytical(secs(k).sec);
    B = GeometryEngine.integral(secs(k).sec, 'symbolique');
    tc.verifyEqual(B.methodUsed, 'symbolique', secs(k).name);
    tc.verifyEqual(B.method, 'intégrale symbolique', secs(k).name);
    tc.verifyLessThanOrEqual(propDiff(A, B), 1e-9, secs(k).name);
    verifyRel(tc, B.IxDirect, B.Iz + B.Iy, 1e-12, secs(k).name);
    if isnan(A.J)
        tc.verifyTrue(isnan(B.J), secs(k).name);
    else
        verifyRel(tc, B.J, A.J, 1e-9, secs(k).name);
    end
end
end

function testAnalyticalEqualsNumericIntegral(tc)
secs = tc.TestData.secs;
for k = 1:numel(secs)
    A = GeometryEngine.analytical(secs(k).sec);
    N = GeometryEngine.integral(secs(k).sec, 'numerique');
    tc.verifyEqual(N.methodUsed, 'numérique', secs(k).name);
    tc.verifyEqual(N.method, 'intégrale numérique', secs(k).name);
    tc.verifyLessThanOrEqual(propDiff(A, N), 1e-9, secs(k).name);
    verifyRel(tc, N.IxDirect, N.Iz + N.Iy, 1e-10, secs(k).name);
end
end

function testIntegralFieldsAndDefaultMode(tc)
sec = struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.0056, 'tf', 0.0085);
P = GeometryEngine.integral(sec);
if tc.TestData.hasSym
    tc.verifyEqual(P.methodUsed, 'symbolique');
else
    tc.verifyEqual(P.methodUsed, 'numérique');
end
tc.verifyTrue(iscellstr(P.integrals));
tc.verifyEqual(numel(P.integrals), 7*3);
tc.verifyTrue(all(startsWith(P.integrals, '$')) && all(endsWith(P.integrals, '$')));
tc.verifyTrue(contains(P.integrals{1}, '\int_{0}^{0.1}\!\!\int_{0}^{0.0085}'));
req = {'S', 'zG', 'yG', 'Iz', 'Iy', 'Iyz', 'Ix', 'J', 'I1', 'I2', 'alphaP', 'rz', 'ry', 'vyTop', ...
    'vyBot', 'vzRight', 'vzLeft', 'Wz', 'Wy', 'MO1z', 'MO1y', 'k', 'ky', 'kSource', 'method', ...
    'report', 'latex', 'integrals', 'methodUsed'};
tc.verifyTrue(all(isfield(P, req)));
tc.verifyFalse(isfield(P, 'huygens'));
% disque : intégrale en coordonnées polaires
Pd = GeometryEngine.integral(struct('type', 'disque', 'D', 0.1), 'numerique');
tc.verifyTrue(contains(Pd.integrals{1}, 'r\,dr\,d\theta'));
% alias de mode
Pn = GeometryEngine.integral(sec, 'numérique');
tc.verifyEqual(Pn.methodUsed, 'numérique');
end

function testAnalyticalFields(tc)
P = GeometryEngine.analytical(struct('type', 'T', 'h', 0.1, 'b', 0.08, 'tw', 0.008, 'tf', 0.01));
req = {'S', 'zG', 'yG', 'Iz', 'Iy', 'Iyz', 'Ix', 'J', 'I1', 'I2', 'alphaP', 'rz', 'ry', 'vyTop', ...
    'vyBot', 'vzRight', 'vzLeft', 'Wz', 'Wy', 'MO1z', 'MO1y', 'k', 'ky', 'kSource', 'method', ...
    'report', 'latex', 'huygens'};
tc.verifyTrue(all(isfield(P, req)));
verifyRel(tc, P.Ix, P.Iz + P.Iy, 1e-15);
verifyRel(tc, P.yG, P.MO1z/P.S, 1e-15);
verifyRel(tc, P.zG, P.MO1y/P.S, 1e-15);
end

%% ---------------------------------------------------------------------------------------------
%  Huygens
%  ---------------------------------------------------------------------------------------------

function testHuygensTable(tc)
secs = tc.TestData.secs;
cols = {'Label', 'S_i', 'zG_i', 'yG_i', 'IGz_i', 'IGy_i', 'dy_i', 'dz_i', 'SDy2', 'SDz2', ...
    'Iz_i', 'Iy_i'};
for k = 1:numel(secs)
    P = GeometryEngine.analytical(secs(k).sec);
    T = P.huygens;
    tc.verifyClass(T, 'table');
    tc.verifyTrue(all(ismember(cols, T.Properties.VariableNames)), secs(k).name);
    verifyRel(tc, sum(T.S_i), P.S, 1e-12, secs(k).name);
    verifyRel(tc, sum(T.Iz_i), P.Iz, 1e-12, secs(k).name);
    verifyRel(tc, sum(T.Iy_i), P.Iy, 1e-12, secs(k).name);
    verifyRel(tc, sum(T.S_i.*T.yG_i)/sum(T.S_i), P.yG, 1e-12, secs(k).name);
    verifyRel(tc, T.SDy2, T.S_i.*T.dy_i.^2, 1e-12, secs(k).name);
    verifyRel(tc, T.SDz2, T.S_i.*T.dz_i.^2, 1e-12, secs(k).name);
    verifyRel(tc, T.Iz_i, T.IGz_i + T.SDy2, 1e-12, secs(k).name);
    verifyRel(tc, T.Iy_i, T.IGy_i + T.SDz2, 1e-12, secs(k).name);
    tc.verifyLessThanOrEqual(abs(sum(T.SDyDz) - P.Iyz), 1e-12*max(P.Iz, P.Iy), secs(k).name);
end
% I : Huygens explicite sur les ailes
h = 0.2; b = 0.1; tw = 0.0056; tf = 0.0085;
P = GeometryEngine.analytical(struct('type', 'I', 'h', h, 'b', b, 'tw', tw, 'tf', tf));
verifyRel(tc, P.huygens.dy_i(1), -(h/2 - tf/2), 1e-12);
verifyRel(tc, P.huygens.SDy2(3), b*tf*(h/2 - tf/2)^2, 1e-12);
verifyRel(tc, P.huygens.IGz_i(2), tw*(h - 2*tf)^3/12, 1e-12);
end

%% ---------------------------------------------------------------------------------------------
%  Moment statique Q(y) et largeur b(y)
%  ---------------------------------------------------------------------------------------------

function testFirstMomentRectangle(tc)
b = 0.1; h = 0.2;
sec = struct('type', 'rectangle', 'b', b, 'h', h);
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, 0), b*h^2/8, 1e-12);
y = linspace(-h/2, h/2, 41);
Q = GeometryEngine.firstMomentAbove(sec, y);
tc.verifySize(Q, size(y));
tc.verifyLessThanOrEqual(max(abs(Q - b/2*(h^2/4 - y.^2))), 1e-12*b*h^2/8);
tc.verifyEqual(GeometryEngine.firstMomentAbove(sec, [-0.3; 0.3]), [0; 0]);
Ym = [0 0.05; -0.05 0.02];
Qm = GeometryEngine.firstMomentAbove(sec, Ym);
tc.verifySize(Qm, [2 2]);
verifyRel(tc, Qm, b/2*(h^2/4 - Ym.^2), 1e-12);
end

function testFirstMomentDisque(tc)
D = 0.1; R = D/2;
sec = struct('type', 'disque', 'D', D);
y = linspace(-R, R, 51);
Q = GeometryEngine.firstMomentAbove(sec, y);
tc.verifyLessThanOrEqual(max(abs(Q - 2/3*(R^2 - y.^2).^(3/2))), 1e-12*R^3);
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, 0), 2/3*R^3, 1e-12);
end

function testFirstMomentCouronne(tc)
D = 0.1; d = 0.06; R = D/2; r = d/2;
sec = struct('type', 'couronne', 'D', D, 'd', d);
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, 0), 2/3*(R^3 - r^3), 1e-12);
y = 0.04;
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, y), 2/3*(R^2 - y^2)^(3/2), 1e-12);
y = 0.01;
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, y), 2/3*((R^2 - y^2)^(3/2) - (r^2 - y^2)^(3/2)), 1e-12);
end

function testFirstMomentISymmetric(tc)
h = 0.2; b = 0.1; tw = 0.0056; tf = 0.0085;
sec = struct('type', 'I', 'h', h, 'b', b, 'tw', tw, 'tf', tf);
Q0 = b*tf*(h/2 - tf/2) + tw*(h/2 - tf)^2/2;
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, 0), Q0, 1e-12);
yf = h/2 - tf/3;   % dans l'aile supérieure
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, yf), b/2*(h^2/4 - yf^2), 1e-12);
yw = 0.05;         % dans l'âme
verifyRel(tc, GeometryEngine.firstMomentAbove(sec, yw), b*tf*(h/2 - tf/2) + tw/2*((h/2 - tf)^2 - yw^2), 1e-12);
y = linspace(-h/2, h/2, 37);
dsym = GeometryEngine.firstMomentAbove(sec, -y) - GeometryEngine.firstMomentAbove(sec, y);
tc.verifyLessThanOrEqual(max(abs(dsym)), 1e-12*Q0);
tc.verifyEqual(GeometryEngine.firstMomentAbove(sec, [-h/2 h/2]), [0 0]);
end

function testFirstMomentDerivativeConsistency(tc)
% dQ/dy = -y b(y) (partout où b est continue) et Q -> 0 aux fibres extrêmes.
secs = tc.TestData.secs;
for k = 1:numel(secs)
    sec = secs(k).sec;
    P = GeometryEngine.analytical(sec);
    yv = linspace(-P.vyBot, P.vyTop, 157);
    yv = yv(2:end-1) + 1e-4*(P.vyTop + P.vyBot)*0.37;
    yv = yv(yv < P.vyTop);
    hstep = 1e-7*(P.vyTop + P.vyBot);
    dQ = (GeometryEngine.firstMomentAbove(sec, yv + hstep) - GeometryEngine.firstMomentAbove(sec, yv - hstep))/(2*hstep);
    bL = GeometryEngine.widthAt(sec, yv - hstep, 'dessous');
    bR = GeometryEngine.widthAt(sec, yv + hstep, 'dessus');
    smooth = abs(bL - bR) <= 1e-9*max(bL + bR);
    ref = -yv.*GeometryEngine.widthAt(sec, yv);
    scale = max(abs(ref)) + eps;
    tc.verifyLessThanOrEqual(max(abs(dQ(smooth) - ref(smooth)))/scale, 1e-5, secs(k).name);
    tc.verifyLessThanOrEqual(abs(GeometryEngine.firstMomentAbove(sec, -P.vyBot)), 1e-15, secs(k).name);
    tc.verifyLessThanOrEqual(abs(GeometryEngine.firstMomentAbove(sec, P.vyTop)), 1e-15, secs(k).name);
    % moment statique de la demi-section supérieure = - moment de la partie inférieure (ΣS·y = 0)
    Qint = integral(@(t) GeometryEngine.widthAt(sec, t).*t, 0, P.vyTop, 'RelTol', 1e-10, 'AbsTol', 0, ...
        'Waypoints', [0.25 0.5 0.75]*P.vyTop);
    verifyRel(tc, GeometryEngine.firstMomentAbove(sec, 0), Qint, 1e-6, secs(k).name);
end
end

function testWidthAt(tc)
b = 0.1; h = 0.2;
rect = struct('type', 'rectangle', 'b', b, 'h', h);
tc.verifyEqual(GeometryEngine.widthAt(rect, [-0.05 0 0.05]), [b b b]);
tc.verifyEqual(GeometryEngine.widthAt(rect, [-0.2 0.2]), [0 0]);
tc.verifyEqual(GeometryEngine.widthAt(rect, h/2), b);
tc.verifyEqual(GeometryEngine.widthAt(rect, h/2, 'dessus'), 0);
tc.verifyEqual(GeometryEngine.widthAt(rect, h/2, 'dessous'), b);
D = 0.1; R = D/2;
disk = struct('type', 'disque', 'D', D);
y = linspace(-R, R, 21)';
bw = GeometryEngine.widthAt(disk, y);
tc.verifySize(bw, size(y));
tc.verifyLessThanOrEqual(max(abs(bw - 2*sqrt(R^2 - y.^2))), 1e-12*D);
cour = struct('type', 'couronne', 'D', 0.1, 'd', 0.06);
verifyRel(tc, GeometryEngine.widthAt(cour, 0), 0.04, 1e-12);
creux = struct('type', 'rectangle_creux', 'B', 0.1, 'H', 0.2, 't', 0.01);
verifyRel(tc, GeometryEngine.widthAt(creux, [0 0.095]), [0.02 0.1], 1e-12);
hI = 0.2; bI = 0.1; tw = 0.0056; tf = 0.0085;
sI = struct('type', 'I', 'h', hI, 'b', bI, 'tw', tw, 'tf', tf);
verifyRel(tc, GeometryEngine.widthAt(sI, [0 0.05 -0.05]), [tw tw tw], 1e-12);
verifyRel(tc, GeometryEngine.widthAt(sI, [hI/2 - tf/2, -hI/2 + tf/2]), [bI bI], 1e-12);
yj = hI/2 - tf;     % jonction âme / aile supérieure
verifyRel(tc, GeometryEngine.widthAt(sI, yj), bI, 1e-12);
verifyRel(tc, GeometryEngine.widthAt(sI, yj, 'below'), tw, 1e-12);
verifyRel(tc, GeometryEngine.widthAt(sI, yj, 'above'), bI, 1e-12);
verifyRel(tc, GeometryEngine.widthAt(sI, -yj, 'dessous'), bI, 1e-12);
verifyRel(tc, GeometryEngine.widthAt(sI, -yj, 'dessus'), tw, 1e-12);
% recalage des cotes affectées d'erreurs d'arrondi
verifyRel(tc, GeometryEngine.widthAt(sI, yj*(1 + 1e-14), 'dessous'), tw, 1e-12);
tc.verifyTrue(isnan(GeometryEngine.widthAt(sI, NaN)));
end

%% ---------------------------------------------------------------------------------------------
%  Facteurs de cisaillement
%  ---------------------------------------------------------------------------------------------

function testShearFactorsRectangle(tc)
f = GeometryEngine.shearFactors(struct('type', 'rectangle', 'b', 0.1, 'h', 0.2));
tc.verifyEqual(f.kCours, 3/2);
tc.verifyEqual(f.kyCours, 5/6);
verifyRel(tc, f.kNum, 3/2, 1e-9);
verifyRel(tc, f.kyNum, 5/6, 1e-9);
tc.verifyLessThanOrEqual(abs(f.yAtMax), 1e-12);
tc.verifyTrue(f.connected);
tc.verifyTrue(iscellstr(f.report) && iscellstr(f.latex));
end

function testJourawskiRectangleMax(tc)
% tau(y) = T Q(y)/(Iz b(y)) : maximum 1,5 T/S en G, parabole 3/2 T/S (1 - (2y/h)^2).
b = 0.1; h = 0.2; T = 1e4;
sec = struct('type', 'rectangle', 'b', b, 'h', h);
P = GeometryEngine.analytical(sec);
y = linspace(-h/2, h/2, 101);
tau = T*GeometryEngine.firstMomentAbove(sec, y)./(P.Iz*GeometryEngine.widthAt(sec, y));
tc.verifyLessThanOrEqual(max(abs(tau - 1.5*T/(b*h)*(1 - (2*y/h).^2))), 1e-9*T/(b*h));
verifyRel(tc, max(tau), 1.5*T/P.S, 1e-12);
verifyRel(tc, P.shear.kNum*T/P.S, 1.5*T/P.S, 1e-9);
end

function testShearFactorsDisque(tc)
f = GeometryEngine.shearFactors(struct('type', 'disque', 'D', 0.08));
verifyRel(tc, f.kNum, 4/3, 1e-9);
verifyRel(tc, f.kyNum, 9/10, 1e-9);   % intégration exacte : 9/10 (cours : 6/7, élasticité)
tc.verifyEqual(f.kCours, 4/3);
tc.verifyEqual(f.kyCours, 6/7);
tc.verifyTrue(any(contains(f.report, '9/10')));
end

function testShearFactorsCouronne(tc)
D = 0.1; d = 0.08; R = D/2; r = d/2;
f = GeometryEngine.shearFactors(struct('type', 'couronne', 'D', D, 'd', d));
verifyRel(tc, f.kCours, 4/3*(1 + r*R/(r^2 + R^2)), 1e-12);
verifyRel(tc, f.kNum, 4/3*(1 + r*R/(r^2 + R^2)), 1e-9);
tc.verifyEqual(f.kyCours, 1/2);
% tube mince : Jourawski (coupes horizontales) -> ky = 2/3 ; k -> 2
ft = GeometryEngine.shearFactors(struct('type', 'couronne', 'D', 0.1, 'd', 0.0998));
verifyRel(tc, ft.kNum, 2, 1e-5);
verifyRel(tc, ft.kyNum, 2/3, 2e-2);
end

function testShearFactorsI(tc)
h = 0.2; b = 0.1; tw = 0.0056; tf = 0.0085;
sec = struct('type', 'I', 'h', h, 'b', b, 'tw', tw, 'tf', tf);
f = GeometryEngine.shearFactors(sec);
P = GeometryEngine.analytical(sec);
Sw = tw*(h - 2*tf);
verifyRel(tc, f.Sweb, Sw, 1e-12);
verifyRel(tc, f.kCours, P.S/Sw, 1e-12);
verifyRel(tc, f.kyCours, Sw/P.S, 1e-12);
Q0 = b*tf*(h/2 - tf/2) + tw*(h/2 - tf)^2/2;
verifyRel(tc, f.kNum, P.S*Q0/(P.Iz*tw), 1e-9);
tc.verifyGreaterThan(f.kyNum, 0);
tc.verifyLessThan(f.kyNum, 1);
end

function testShearFactorsRectangleCompositeAndT(tc)
% composite d'un seul rectangle : valeurs exactes 3/2 et 5/6 retrouvées numériquement
f = GeometryEngine.shearFactors(struct('type', 'composite', 'rects', [1 1.1 2 2.3]));
tc.verifyTrue(isnan(f.kCours));
verifyRel(tc, f.kNum, 3/2, 1e-9);
verifyRel(tc, f.kyNum, 5/6, 1e-9);
% T : maximum de tau en G (dans l'âme)
sec = struct('type', 'T', 'h', 0.1, 'b', 0.08, 'tw', 0.008, 'tf', 0.01);
P = GeometryEngine.analytical(sec);
fT = GeometryEngine.shearFactors(sec);
verifyRel(tc, fT.kNum, P.S*GeometryEngine.firstMomentAbove(sec, 0)/(P.Iz*0.008), 1e-9);
tc.verifyEqual(P.k, fT.kNum);
tc.verifyEqual(P.ky, fT.kyNum);
end

function testShearFactorsDisconnected(tc)
sec = struct('type', 'composite', 'rects', [0 0.1 0 0.02; 0 0.1 0.08 0.1]);
f = GeometryEngine.shearFactors(sec);
tc.verifyFalse(f.connected);
tc.verifyTrue(isnan(f.kNum) && isnan(f.kyNum));
P = GeometryEngine.analytical(sec);
verifyRel(tc, P.Iz, 2*(0.1*0.02^3/12 + 0.1*0.02*0.04^2), 1e-12);
tc.verifyTrue(isnan(P.k) && isnan(P.ky));
% disque posé sur un rectangle (contact ponctuel) : étranglement détecté
fc = GeometryEngine.shearFactors(struct('type', 'composite', 'rects', [-0.05 0.05 -0.1 0], ...
    'disks', [0 0.03 0.03]));
tc.verifyFalse(fc.connected);
tc.verifyTrue(isnan(fc.kNum));
end

%% ---------------------------------------------------------------------------------------------
%  Profilés, valeurs tabulées, comparaison
%  ---------------------------------------------------------------------------------------------

function testProfileIPEAnalytical(tc)
sec = ipe200();
P = GeometryEngine.analytical(sec);
PI = GeometryEngine.analytical(struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.0056, 'tf', 0.0085));
tc.verifyLessThanOrEqual(propDiff(PI, P), 1e-14);
tc.verifyTrue(any(contains(P.report, 'géométrie simplifiée')));
verifyRel(tc, P.S, 27.248e-4, 1e-12);
end

function testTabulatedIPE(tc)
sec = ipe200();
T = GeometryEngine.tabulated(sec);
tc.verifyEqual(T.method, 'tabulée');
tc.verifyEqual([T.S T.Iz T.Iy T.Wz T.Wy T.rz T.ry], [28.5e-4 1943e-8 142.4e-8 194.3e-6 28.47e-6 0.0826 0.0224]);
tc.verifyEqual([T.yG T.zG T.Iyz], [0.1 0.05 0]);
verifyRel(tc, T.Ix, 1943e-8 + 142.4e-8, 1e-15);
verifyRel(tc, [T.I1 T.I2], [1943e-8 142.4e-8], 1e-12);
tc.verifyEqual(T.alphaP, 0);
Sw = 0.0056*(0.2 - 2*0.0085);
verifyRel(tc, [T.k T.ky], [28.5e-4/Sw Sw/28.5e-4], 1e-12);
tc.verifyTrue(isnan(T.J));
tc.verifyTrue(iscellstr(T.report) && iscolumn(T.report));
% valeurs absentes : déduites
s2 = rmfield(sec, {'rz', 'ry', 'Wz', 'Wy'});
T2 = GeometryEngine.tabulated(s2);
verifyRel(tc, [T2.rz T2.ry T2.Wz T2.Wy], [sqrt(1943e-8/28.5e-4) sqrt(142.4e-8/28.5e-4) 1943e-8/0.1 142.4e-8/0.05], 1e-12);
end

function testTabulatedUPN(tc)
sec = upn200();
T = GeometryEngine.tabulated(sec);
tc.verifyEqual(T.zG, 0.0201);
verifyRel(tc, [T.vzLeft T.vzRight], [0.0201 0.075 - 0.0201], 1e-12);
tc.verifyEqual(T.kSource, 'numérique');
P = GeometryEngine.analytical(sec);
h = 0.2; b = 0.075; tw = 0.0085; tf = 0.0115;
S = h*tw + 2*(b - tw)*tf;
verifyRel(tc, P.S, S, 1e-12);
verifyRel(tc, P.zG, (h*tw^2/2 + 2*tf*(b^2 - tw^2)/2)/S, 1e-12);
% famille déduite du nom ou de c
s2 = rmfield(sec, 'family');
v = GeometryEngine.validateSection(s2);
tc.verifyEqual(v.profileShape, 'U');
s3 = rmfield(rmfield(sec, 'family'), 'name');
v3 = GeometryEngine.validateSection(s3);
tc.verifyEqual(v3.profileShape, 'U');
end

function testTabulatedErrorNonProfile(tc)
tc.verifyError(@() GeometryEngine.tabulated(struct('type', 'rectangle', 'b', 0.1, 'h', 0.2)), ...
    'MecaStruct:GeometryEngine:notProfile');
s = rmfield(ipe200(), 'Iz');
tc.verifyError(@() GeometryEngine.tabulated(s), 'MecaStruct:GeometryEngine:missingField');
end

function testCompareProfile(tc)
C = GeometryEngine.compare(ipe200());
tc.verifyClass(C, 'table');
tc.verifyEqual(C.Properties.RowNames, {'S'; 'yG'; 'zG'; 'Iz'; 'Iy'; 'Iyz'; 'Ix'; 'rz'; 'ry'; 'Wz'; 'Wy'});
tc.verifyEqual(C.Properties.VariableNames, {'Analytique', 'Integrale', 'Tabulee', 'EcartMax_pct'});
verifyRel(tc, C.Analytique, C.Integrale, 1e-9);
tc.verifyEqual(C{'Iz', 'Tabulee'}, 1943e-8);
% écart attendu de quelques % (congés) : rapporté, pas caché
tc.verifyGreaterThan(C{'Iz', 'EcartMax_pct'}, 1);
tc.verifyLessThan(C{'Iz', 'EcartMax_pct'}, 10);
verifyRel(tc, C{'S', 'EcartMax_pct'}, 100*(28.5e-4 - 27.248e-4)/28.5e-4, 1e-9);
tc.verifyLessThan(C{'yG', 'EcartMax_pct'}, 1e-9);
tc.verifyEqual(C{'Iyz', 'EcartMax_pct'}, 0);
rep = C.Properties.UserData.report;
tc.verifyTrue(iscellstr(rep)); %#ok<ISCLSTR> cell de char exigée par le contrat
tc.verifyTrue(any(contains(rep, 'congés')));
tc.verifyTrue(isstruct(C.Properties.UserData.tabulated));
end

function testCompareNonProfile(tc)
secs = tc.TestData.secs;
for k = 1:numel(secs)
    if strcmp(secs(k).sec.type, 'profile'), continue; end
    C = GeometryEngine.compare(secs(k).sec);
    tc.verifyTrue(all(isnan(C.Tabulee)), secs(k).name);
    tc.verifyLessThan(max(C.EcartMax_pct), 1e-7, secs(k).name);
end
end

function testFromProfile(tc)
p = struct('Family', "IPE", 'Name', "IPE 200", 'h', 0.2, 'b', 0.1, 'a', 0.0056, 'e', 0.0085, ...
    'r', 0.012, 'S', 28.5e-4, 'Iz', 1943e-8, 'Iy', 142.4e-8, 'Wz', 194.3e-6, 'Wy', 28.47e-6, ...
    'rz', 0.0826, 'ry', 0.0224, 'mass', 22.4, 'c', NaN);
sec = GeometryEngine.fromProfile(p);
tc.verifyEqual(sec.type, 'profile');
tc.verifyEqual(sec.family, 'IPE');
tc.verifyEqual(sec.name, 'IPE 200');
tc.verifyEqual(sec.profileShape, 'I');
T = GeometryEngine.tabulated(sec);
tc.verifyEqual(T.Iz, 1943e-8);
end

%% ---------------------------------------------------------------------------------------------
%  Composite
%  ---------------------------------------------------------------------------------------------

function testCompositeEqualsI(tc)
h = 0.2; b = 0.1; tw = 0.0056; tf = 0.0085;
rects = [0 b 0 tf; (b - tw)/2 (b + tw)/2 tf h - tf; 0 b h - tf h];
PC = GeometryEngine.analytical(struct('type', 'composite', 'rects', rects));
PI = GeometryEngine.analytical(struct('type', 'I', 'h', h, 'b', b, 'tw', tw, 'tf', tf));
tc.verifyLessThanOrEqual(propDiff(PI, PC), 1e-13);
verifyRel(tc, PC.J, PI.J, 1e-12);
% translation du repère utilisateur : G translaté, inerties inchangées
PT = GeometryEngine.analytical(struct('type', 'composite', 'rects', rects + [1 1 -2 -2]));
verifyRel(tc, [PT.zG PT.yG], [PI.zG + 1, PI.yG - 2], 1e-12);
verifyRel(tc, [PT.Iz PT.Iy], [PI.Iz PI.Iy], 1e-9);
end

function testCompositeHoles(tc)
% plaque percée d'un trou circulaire centré
sec = struct('type', 'composite', 'rects', [0 0.2 0 0.1], 'diskHoles', [0.1 0.05 0.03]);
P = GeometryEngine.analytical(sec);
R = 0.03;
verifyRel(tc, P.S, 0.02 - pi*R^2, 1e-12);
verifyRel(tc, P.Iz, 0.2*0.1^3/12 - pi*R^4/4, 1e-12);
verifyRel(tc, P.Iy, 0.1*0.2^3/12 - pi*R^4/4, 1e-12);
tc.verifyTrue(isnan(P.J));
verifyRel(tc, GeometryEngine.widthAt(sec, 0), 0.2 - 2*R, 1e-12);
% trou rectangulaire excentré : Huygens avec aire négative
sec2 = struct('type', 'composite', 'rects', [0 0.1 0 0.2], 'holes', [0.02 0.04 0.02 0.06]);
P2 = GeometryEngine.analytical(sec2);
S = 0.02 - 0.0008;
yG = (0.02*0.1 - 0.0008*0.04)/S;
Iz = 0.1*0.2^3/12 + 0.02*(0.1 - yG)^2 - (0.02*0.04^3/12 + 0.0008*(0.04 - yG)^2);
verifyRel(tc, [P2.S P2.yG P2.Iz], [S yG Iz], 1e-12);
tc.verifyLessThan(P2.huygens.S_i(2), 0);
tc.verifyNotEqual(P2.Iyz, 0);
end

%% ---------------------------------------------------------------------------------------------
%  Primitives et contours
%  ---------------------------------------------------------------------------------------------

function testPrimitives(tc)
pr = GeometryEngine.primitives(struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.0056, 'tf', 0.0085));
tc.verifyTrue(iscolumn(pr));
tc.verifyEqual(numel(pr), 3);
tc.verifyTrue(all(isfield(pr, {'kind', 'sign', 'z1', 'z2', 'y1', 'y2', 'zc', 'yc', 'R', 'Ri', 'label'})));
tc.verifyEqual({pr.kind}, {'rect', 'rect', 'rect'});
tc.verifyEqual(pr(3).label, 'Aile supérieure');
tc.verifyEqual([pr(2).z1 pr(2).z2 pr(2).y1 pr(2).y2], [0.0472 0.0528 0.0085 0.1915], 'AbsTol', 1e-15);
pc = GeometryEngine.primitives(struct('type', 'couronne', 'D', 0.1, 'd', 0.06));
tc.verifyEqual(pc.kind, 'annulus');
tc.verifyEqual([pc.zc pc.yc pc.R pc.Ri pc.sign], [0.05 0.05 0.05 0.03 1]);
ph = GeometryEngine.primitives(struct('type', 'rectangle_creux', 'B', 0.1, 'H', 0.2, 't', 0.01));
tc.verifyEqual([ph.sign], [1 -1]);
end

function testOutline(tc)
secs = tc.TestData.secs;
for k = 1:numel(secs)
    sec = secs(k).sec;
    out = GeometryEngine.outline(sec);
    P = GeometryEngine.analytical(sec);
    tc.verifyTrue(iscell(out.outer) && iscell(out.holes), secs(k).name);
    tc.verifyNotEmpty(out.outer, secs(k).name);
    A = 0;
    curved = any(strcmp(sec.type, {'disque', 'couronne'})) || ...
        (strcmp(sec.type, 'composite') && (isfield(sec, 'disks') || isfield(sec, 'diskHoles')));
    polys = [out.outer(:); out.holes(:)];
    for j = 1:numel(polys)
        p = polys{j};
        tc.verifyEqual(size(p, 2), 2);
        tc.verifyEqual(p(1, :), p(end, :), secs(k).name);
    end
    for j = 1:numel(out.outer)
        p = out.outer{j};
        a = 0.5*sum(p(1:end-1, 1).*p(2:end, 2) - p(2:end, 1).*p(1:end-1, 2));
        tc.verifyGreaterThan(a, 0, 'contour extérieur en sens trigonométrique');
        A = A + a;
    end
    for j = 1:numel(out.holes)
        p = out.holes{j};
        a = 0.5*sum(p(1:end-1, 1).*p(2:end, 2) - p(2:end, 1).*p(1:end-1, 2));
        tc.verifyLessThan(a, 0, 'trou en sens horaire');
        A = A + a;
    end
    if curved
        verifyRel(tc, A, P.S, 1e-3, secs(k).name);
    else
        verifyRel(tc, A, P.S, 1e-12, secs(k).name);
    end
    tc.verifyEqual(out.bbox, P.bbox, 'AbsTol', 1e-15);
end
outD = GeometryEngine.outline(struct('type', 'disque', 'D', 0.1));
tc.verifyGreaterThanOrEqual(size(outD.outer{1}, 1), 121);
outC = GeometryEngine.outline(struct('type', 'couronne', 'D', 0.1, 'd', 0.06));
tc.verifyEqual(numel(outC.holes), 1);
tc.verifyGreaterThanOrEqual(size(outC.holes{1}, 1), 121);
r = hypot(outC.holes{1}(:, 1) - 0.05, outC.holes{1}(:, 2) - 0.05);
tc.verifyEqual(r, 0.03*ones(size(r)), 'AbsTol', 1e-15);
outI = GeometryEngine.outline(struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.0056, 'tf', 0.0085));
tc.verifyEqual(size(outI.outer{1}, 1), 13);
tc.verifyEmpty(outI.holes);
outCo = GeometryEngine.outline(struct('type', 'composite', 'rects', [0 0.1 0 0.2], 'holes', [0.02 0.04 0.02 0.06]));
tc.verifyEqual(numel(outCo.outer), 1);
tc.verifyEqual(numel(outCo.holes), 1);
end

%% ---------------------------------------------------------------------------------------------
%  Textes : rapport et LaTeX
%  ---------------------------------------------------------------------------------------------

function testReportFormat(tc)
secs = tc.TestData.secs;
for k = 1:numel(secs)
    A = GeometryEngine.analytical(secs(k).sec);
    N = GeometryEngine.integral(secs(k).sec, 'numerique');
    f = GeometryEngine.shearFactors(secs(k).sec);
    for P = {A, N, f}
        r = P{1}.report;
        tc.verifyTrue(iscellstr(r) && iscolumn(r), secs(k).name); %#ok<ISCLSTR> cell de char exigée
        tc.verifyNotEmpty(r);
        tc.verifyTrue(iscellstr(P{1}.latex), secs(k).name);
    end
end
end

function testLatexValid(tc)
secs = tc.TestData.secs;
strs = {};
for k = 1:numel(secs)
    sec = secs(k).sec;
    A = GeometryEngine.analytical(sec);
    N = GeometryEngine.integral(sec, 'numerique');
    strs = [strs; A.latex(:); N.latex(:); N.integrals(:)]; %#ok<AGROW>
    if strcmp(sec.type, 'profile')
        T = GeometryEngine.tabulated(sec);
        strs = [strs; T.latex(:)]; %#ok<AGROW>
    end
end
if tc.TestData.hasSym
    B = GeometryEngine.integral(secs(5).sec, 'symbolique');
    strs = [strs; B.latex(:); B.integrals(:)];
end
forbidden = {'\iint', '\iiint', '\implies', '\text{', '\dfrac', '\tfrac', '\boldsymbol', ...
    '\geqslant', '\leqslant', 'pmatrix', 'bmatrix', '{align', '{cases'};
for k = 1:numel(strs)
    s = strs{k};
    tc.verifyTrue(ischar(s));
    tc.verifyTrue(all(double(s) < 128), ['caractère non ASCII : ' s]);
    tc.verifyLessThan(numel(s), 1000);
    tc.verifyTrue(startsWith(s, '$') && endsWith(s, '$'), s);
    tc.verifyFalse(any(cellfun(@(f) contains(s, f), forbidden)), ['commande interdite : ' s]);
end
% rendu effectif sans avertissement
fig = figure('Visible', 'off');
cleanup = onCleanup(@() close(fig));
ax = axes(fig);
for k = 1:numel(strs)
    lastwarn('');
    th = text(ax, 0.05, 0.5, strs{k}, 'Interpreter', 'latex');
    drawnow;
    [msg, id] = lastwarn;
    tc.verifyEmpty(msg, sprintf('LaTeX invalide (%s) : %s', id, strs{k}));
    delete(th);
end
clear cleanup
end

%% ---------------------------------------------------------------------------------------------
%  Validation et erreurs
%  ---------------------------------------------------------------------------------------------

function testTypeAliases(tc)
P1 = GeometryEngine.analytical(struct('type', 'Rectangle', 'b', 0.1, 'h', 0.2));
P2 = GeometryEngine.analytical(struct('type', "rectangle", 'b', 0.1, 'h', 0.2));
tc.verifyEqual(P1.Iz, P2.Iz);
P3 = GeometryEngine.analytical(struct('type', 'i', 'h', 0.2, 'b', 0.1, 'tw', 0.0056, 'tf', 0.0085));
tc.verifyEqual(P3.type, 'I');
T = GeometryEngine.sectionTypes();
tc.verifyEqual(numel(T), 10);
tc.verifyTrue(all(isfield(T, {'type', 'label', 'fields', 'origin'})));
end

function testErrors(tc)
id = 'MecaStruct:GeometryEngine:';
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'hexagone')), [id 'unknownType']);
tc.verifyError(@() GeometryEngine.analytical(struct('b', 0.1)), [id 'missingField']);
tc.verifyError(@() GeometryEngine.analytical(42), [id 'invalidInput']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'rectangle', 'b', 0.1)), [id 'missingField']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'rectangle', 'b', -0.1, 'h', 0.2)), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'couronne', 'D', 0.1, 'd', 0.1)), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'I', 'h', 0.2, 'b', 0.1, 'tw', 0.005, 'tf', 0.1)), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'U', 'h', 0.2, 'b', 0.01, 'tw', 0.01, 'tf', 0.01)), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'L', 'h', 0.1, 'b', 0.05, 't', 0.05)), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'rectangle_creux', 'B', 0.1, 'H', 0.2, 't', 0.05)), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'composite', 'rects', [0 1 0 1; 0.5 2 0.5 2])), [id 'overlap']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'composite', 'rects', [0 1 0 1], 'holes', [0.5 1.5 0.2 0.4])), [id 'holeOutside']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'composite', 'rects', [0 1 0 1], 'holes', [0.1 0.5 0.1 0.5; 0.3 0.6 0.3 0.6])), [id 'overlap']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'composite', 'rects', [0 1 0 1], 'diskHoles', [0.9 0.5 0.2])), [id 'holeOutside']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'composite', 'rects', [0 1 1 0])), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'composite', 'rects', [0 1 0])), [id 'invalidDimensions']);
tc.verifyError(@() GeometryEngine.analytical(struct('type', 'composite', 'rects', [0 1 0 1], 'disks', [1.2 0.5 0.3])), [id 'overlap']);
tc.verifyError(@() GeometryEngine.integral(struct('type', 'rectangle', 'b', 0.1, 'h', 0.2), 'monte-carlo'), [id 'unknownMode']);
tc.verifyError(@() GeometryEngine.widthAt(struct('type', 'rectangle', 'b', 0.1, 'h', 0.2), 0, 'gauche'), [id 'invalidInput']);
tc.verifyError(@() GeometryEngine.firstMomentAbove(struct('type', 'rectangle', 'b', 0.1, 'h', 0.2), 'a'), [id 'invalidInput']);
end
