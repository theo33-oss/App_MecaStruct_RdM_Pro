classdef BeamAndTrussSolver
    %BEAMANDTRUSSSOLVER Statique des poutres droites et des treillis (classe statique, unités SI).
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   BeamAndTrussSolver regroupe les calculs du module « Équilibre, treillis,
    %   efforts intérieurs » de MecaStruct_RdM_Pro.
    %
    %   Utilitaires de polynômes par morceaux (structure pp : breaks 1×(n+1),
    %   coefs 1×n cell de vecteurs ligne en variable GLOBALE s, ordre polyval) :
    %     ppEval, ppSample, ppIntegrate, ppDerivative, ppAdd, ppScale,
    %     ppMultiply, ppRefine, ppIntegral, ppZero, ppConst, poly2latex,
    %     poly2str, hasSymbolic.
    %
    %   Poutres : sol = BeamAndTrussSolver.solveBeam(model, opts)
    %     PFS en A (isostatique), Ménabréa et méthode d'intégration
    %     (hyperstatique), torseur de cohésion par coupures et par la méthode
    %     intégrale (symbolique si disponible), équations par tronçon, extrema.
    %
    %   Treillis : tsol = BeamAndTrussSolver.solveTruss(truss)
    %     Méthode des nœuds matricielle (isostatique) et méthode des rigidités.
    %
    %   Convention du cours : {T_coh} = {actions extérieures à DROITE} = -{actions
    %   à GAUCHE}, réduit au centre G(s) de la section d'abscisse s.
    %   Toutes les grandeurs sont en unités SI (N, m, Pa, N·m, rad).
    %
    %   Voir aussi SolicitationsEngine, PlotEngine.

    methods (Static)

        %% ============ Utilitaires de polynômes par morceaux (§0.5) ============

        function v = ppEval(pp, s, side)
            %PPEVAL Évaluation vectorisée d'un polynôme par morceaux.
            %   v = BeamAndTrussSolver.ppEval(pp, s) évalue pp aux abscisses s (m).
            %   v = BeamAndTrussSolver.ppEval(pp, s, side) choisit, aux points de
            %   rupture intérieurs, la limite à droite (side = 'right', défaut) ou
            %   à gauche (side = 'left'). En s = L la limite à gauche est toujours
            %   utilisée, en s = 0 la limite à droite ; hors de [breaks(1),
            %   breaks(end)] les polynômes extrêmes sont prolongés.
            %   Points de rupture reconnus à 1e-12·L près. v a la taille de s.
            if nargin < 3 || isempty(side)
                side = 'right';
            end
            pp = btsCheckPP(pp);
            v = btsEval(pp, s, btsSideIsLeft(side));
        end

        function [s, v] = ppSample(pp, nPerSeg)
            %PPSAMPLE Échantillonnage d'un polynôme par morceaux pour le tracé.
            %   [s, v] = BeamAndTrussSolver.ppSample(pp, nPerSeg) renvoie deux
            %   vecteurs ligne : chaque tronçon est échantillonné par nPerSeg
            %   points (défaut 60) ; les points de rupture sont dupliqués (limite
            %   à gauche puis limite à droite), ce qui rend les sauts visibles.
            if nargin < 2 || isempty(nPerSeg)
                nPerSeg = 60;
            end
            if ~isnumeric(nPerSeg) || ~isscalar(nPerSeg) || ~isfinite(nPerSeg) || nPerSeg < 2
                error('MecaStruct:BeamAndTrussSolver:invalidArgument', ...
                    'nPerSeg doit être un entier supérieur ou égal à 2.');
            end
            pp = btsCheckPP(pp);
            [s, v] = btsSample(pp, round(nPerSeg));
        end

        function ppI = ppIntegrate(pp, C0)
            %PPINTEGRATE Primitive continue d'un polynôme par morceaux.
            %   ppI = BeamAndTrussSolver.ppIntegrate(pp, C0) renvoie la primitive
            %   continue de pp valant C0 (défaut 0) en s = breaks(1). Les points
            %   de rupture sont conservés ; le degré augmente de 1.
            if nargin < 2 || isempty(C0)
                C0 = 0;
            end
            if ~isnumeric(C0) || ~isscalar(C0)
                error('MecaStruct:BeamAndTrussSolver:invalidArgument', 'C0 doit être un scalaire.');
            end
            pp = btsCheckPP(pp);
            ppI = btsIntegratePP(pp, double(C0));
        end

        function ppD = ppDerivative(pp)
            %PPDERIVATIVE Dérivée d'un polynôme par morceaux.
            %   ppD = BeamAndTrussSolver.ppDerivative(pp) dérive chaque tronçon
            %   (les éventuels sauts aux points de rupture ne produisent pas de
            %   distribution de Dirac).
            pp = btsCheckPP(pp);
            c = pp.coefs;
            for k = 1:numel(c)
                d = polyder(c{k});
                if isempty(d)
                    d = 0;
                end
                c{k} = d(:).';
            end
            ppD = struct('breaks', pp.breaks, 'coefs', {c});
        end

        function ppC = ppAdd(ppA, ppB)
            %PPADD Somme de deux polynômes par morceaux.
            %   ppC = BeamAndTrussSolver.ppAdd(ppA, ppB) : les points de rupture
            %   sont fusionnés (tolérance relative 1e-12·L) ; ppB peut aussi être
            %   un scalaire (constante ajoutée).
            ppA = btsCheckPP(ppA);
            if isnumeric(ppB) && isscalar(ppB)
                ppB = struct('breaks', ppA.breaks([1 end]), 'coefs', {{double(ppB)}});
            end
            ppB = btsCheckPP(ppB);
            br = btsMergeBreaks([ppA.breaks, ppB.breaks]);
            cA = btsRefineCoefs(ppA, br);
            cB = btsRefineCoefs(ppB, br);
            c = cell(1, numel(cA));
            for k = 1:numel(cA)
                c{k} = btsPolyAdd(cA{k}, cB{k});
            end
            ppC = struct('breaks', br, 'coefs', {c});
        end

        function ppC = ppScale(pp, k)
            %PPSCALE Produit d'un polynôme par morceaux par un scalaire.
            %   ppC = BeamAndTrussSolver.ppScale(pp, k) renvoie k·pp.
            if ~isnumeric(k) || ~isscalar(k)
                error('MecaStruct:BeamAndTrussSolver:invalidArgument', 'k doit être un scalaire.');
            end
            pp = btsCheckPP(pp);
            c = pp.coefs;
            for i = 1:numel(c)
                c{i} = double(k) * c{i};
            end
            ppC = struct('breaks', pp.breaks, 'coefs', {c});
        end

        function ppC = ppMultiply(ppA, ppB)
            %PPMULTIPLY Produit de deux polynômes par morceaux.
            %   ppC = BeamAndTrussSolver.ppMultiply(ppA, ppB) : fusion des points
            %   de rupture puis produit (conv) tronçon par tronçon.
            ppA = btsCheckPP(ppA);
            ppB = btsCheckPP(ppB);
            br = btsMergeBreaks([ppA.breaks, ppB.breaks]);
            cA = btsRefineCoefs(ppA, br);
            cB = btsRefineCoefs(ppB, br);
            c = cell(1, numel(cA));
            for k = 1:numel(cA)
                c{k} = conv(cA{k}, cB{k});
            end
            ppC = struct('breaks', br, 'coefs', {c});
        end

        function ppR = ppRefine(pp, newBreaks)
            %PPREFINE Ajout de points de rupture à un polynôme par morceaux.
            %   ppR = BeamAndTrussSolver.ppRefine(pp, newBreaks) insère les points
            %   de newBreaks situés dans [breaks(1), breaks(end)] (les autres sont
            %   ignorés) ; la fonction représentée est inchangée.
            pp = btsCheckPP(pp);
            nb = double(newBreaks(:).');
            tol = btsTol(pp.breaks);
            nb = nb(isfinite(nb) & nb >= pp.breaks(1) - tol & nb <= pp.breaks(end) + tol);
            br = btsMergeBreaks([pp.breaks, nb]);
            br(1) = pp.breaks(1);
            br(end) = pp.breaks(end);
            ppR = struct('breaks', br, 'coefs', {btsRefineCoefs(pp, br)});
        end

        function I = ppIntegral(pp, a, b)
            %PPINTEGRAL Intégrale exacte d'un polynôme par morceaux de a à b.
            %   I = BeamAndTrussSolver.ppIntegral(pp, a, b) ; a et b par défaut
            %   breaks(1) et breaks(end) ; vectorisé (a et b de même taille ou
            %   scalaires) ; I < 0 si b < a.
            pp = btsCheckPP(pp);
            if nargin < 2 || isempty(a)
                a = pp.breaks(1);
            end
            if nargin < 3 || isempty(b)
                b = pp.breaks(end);
            end
            P = btsIntegratePP(pp, 0);
            I = btsEval(P, b, false) - btsEval(P, a, false);
        end

        function pp = ppZero(breaks)
            %PPZERO Polynôme par morceaux identiquement nul.
            %   pp = BeamAndTrussSolver.ppZero(breaks) ; breaks strictement
            %   croissants (au moins 2 valeurs).
            pp = BeamAndTrussSolver.ppConst(breaks, 0);
        end

        function pp = ppConst(breaks, c)
            %PPCONST Polynôme par morceaux constant.
            %   pp = BeamAndTrussSolver.ppConst(breaks, c) vaut c sur chaque
            %   tronçon ; breaks strictement croissants (au moins 2 valeurs).
            if nargin < 2 || isempty(c)
                c = 0;
            end
            br = double(breaks(:).');
            if numel(br) < 2 || any(~isfinite(br)) || any(diff(br) <= 0)
                error('MecaStruct:BeamAndTrussSolver:invalidPP', ...
                    'Les points de rupture doivent être finis, strictement croissants (au moins 2 valeurs).');
            end
            if ~isnumeric(c) || ~isscalar(c)
                error('MecaStruct:BeamAndTrussSolver:invalidArgument', 'La constante doit être un scalaire.');
            end
            pp = struct('breaks', br, 'coefs', {repmat({double(c)}, 1, numel(br) - 1)});
        end

        function str = poly2latex(c, var)
            %POLY2LATEX Écriture LaTeX (sans les $) d'un polynôme.
            %   str = BeamAndTrussSolver.poly2latex(c, var) : c coefficients
            %   (ordre polyval), var nom de la variable (défaut 's'). Format %.8g (%.4g pour un seul terme),
            %   puissances de 10 écrites \cdot 10^{n}, termes nuls omis, signes
            %   propres (jamais « + - »), '0' si le polynôme est nul.
            if nargin < 2 || isempty(var)
                var = 's';
            end
            str = btsPolyStr(c, char(var), true);
        end

        function str = poly2str(c, var)
            %POLY2STR Écriture texte d'un polynôme.
            %   str = BeamAndTrussSolver.poly2str(c, var) : version texte de
            %   poly2latex (ex. '-1500*s^2 + 3000*s - 250'), même format.
            if nargin < 2 || isempty(var)
                var = 's';
            end
            str = btsPolyStr(c, char(var), false);
        end

        function tf = hasSymbolic()
            %HASSYMBOLIC Disponibilité de la Symbolic Math Toolbox.
            %   tf = BeamAndTrussSolver.hasSymbolic() renvoie true si la licence
            %   et la toolbox symbolique sont disponibles (résultat mémorisé).
            tf = btsHasSymbolic();
        end

        %% ============================ Poutres (§3) ============================

        function sol = solveBeam(model, opts)
            %SOLVEBEAM Résolution statique complète d'une poutre droite.
            %   sol = BeamAndTrussSolver.solveBeam(model, opts)
            %   model : L, E, G, S, Iz, Iy, Ix, ky, kz, supports (pos, type, name),
            %     pointLoads (pos, Fx, Fy, Fz, name), pointMoments (pos, Mx, My, Mz,
            %     name), distLoads (a, b, dir, coeffs en variable locale ξ = s - a,
            %     name). Types d'appui : 'appui_simple', 'rotule', 'pivot',
            %     'pivot_glissant', 'encastrement'.
            %   opts (optionnel) : internalMethod ('both' | 'coupures' |
            %     'integrale'), hyperMethod ('both' | 'menabrea' | 'integration'),
            %     useSymbolic (défaut hasSymbolic()), includeShearEnergy (false).
            %   sol : model, h, isostatic, reactions, breaks, N, Ty, Tz, Mt, Mfy,
            %     Mfz (pp), internalIntegral, methodCheck, equations, extrema,
            %     menabrea, reactionsMenabrea, reactionsIntegration, report, latex
            %     (+ methodUsed, hyperCheck, integration).
            %   Erreur 'MecaStruct:Beam:mechanism' si la poutre est un mécanisme
            %   pour le chargement appliqué.
            if nargin < 2
                opts = [];
            end
            sol = btsSolveBeam(model, opts);
        end

        %% ============================ Treillis (§3) ============================

        function tsol = solveTruss(truss)
            %SOLVETRUSS Résolution d'un treillis articulé 2D ou 3D.
            %   tsol = BeamAndTrussSolver.solveTruss(truss)
            %   truss : nodes (n×2 ou n×3, m), bars (m×2 indices), E, S (scalaires
            %     ou m×1), supports (n×dim logical, true = ddl bloqué), loads
            %     (n×dim, N), names (cellstr n×1, optionnel).
            %   tsol : dim, h (= m + r - dim·n), isostatic, mechanism, L0, N,
            %     nature, sigma, dL, reactions, displacements, Njoints (méthode
            %     des nœuds [A]{N,R} = {-F}, si isostatique), Nstiffness (méthode
            %     des rigidités), A, methodUsed, table, report, latex.
            %   Erreur 'MecaStruct:Truss:mechanism' si le treillis est un
            %   mécanisme incompatible avec le chargement.
            tsol = btsSolveTruss(truss);
        end
    end
end

%% =====================================================================
%%                 FONCTIONS LOCALES : POLYNÔMES PAR MORCEAUX
%% =====================================================================

function tol = btsTol(br)
% Tolérance de fusion des points de rupture : 1e-12·L (L = max|breaks|).
m = max(abs(br(:)));
if isempty(m) || ~isfinite(m) || m == 0
    tol = 1e-12;
else
    tol = 1e-12 * m;
end
end

function pp = btsCheckPP(pp)
% Validation légère et normalisation d'une structure pp.
if ~isstruct(pp) || ~isscalar(pp) || ~isfield(pp, 'breaks') || ~isfield(pp, 'coefs')
    error('MecaStruct:BeamAndTrussSolver:invalidPP', ...
        'Structure pp invalide : champs ''breaks'' et ''coefs'' requis.');
end
br = double(pp.breaks(:).');
c = pp.coefs;
if isnumeric(c)
    c = num2cell(double(c), 2).';
end
if ~iscell(c) || numel(br) < 2 || numel(c) ~= numel(br) - 1 || any(diff(br) <= 0)
    error('MecaStruct:BeamAndTrussSolver:invalidPP', ...
        'Structure pp invalide : numel(coefs) doit valoir numel(breaks) - 1 et breaks doit être croissant.');
end
c = reshape(c, 1, []);
for k = 1:numel(c)
    ck = double(c{k});
    if isempty(ck)
        ck = 0;
    end
    c{k} = ck(:).';
end
pp = struct('breaks', br, 'coefs', {c});
end

function tf = btsSideIsLeft(side)
if ~(ischar(side) || (isstring(side) && isscalar(side)))
    error('MecaStruct:BeamAndTrussSolver:invalidArgument', 'side doit valoir ''right'' ou ''left''.');
end
switch lower(char(side))
    case 'left'
        tf = true;
    case 'right'
        tf = false;
    otherwise
        error('MecaStruct:BeamAndTrussSolver:invalidArgument', 'side doit valoir ''right'' ou ''left''.');
end
end

function idx = btsSegIndex(br, s, leftSide)
% Indice du tronçon contenant chaque abscisse s (vecteur colonne).
n = numel(br) - 1;
if n == 1
    idx = ones(numel(s), 1);
    return
end
tol = btsTol(br);
st = br(1:n);
if leftSide
    idx = sum(st < s(:) - tol, 2);
else
    idx = sum(st <= s(:) + tol, 2);
end
idx(idx < 1) = 1;
idx(idx > n) = n;
end

function v = btsEval(pp, s, leftSide)
% Évaluation de pp (format cellule) aux points s.
sz = size(s);
s = double(s(:));
c = pp.coefs;
n = numel(c);
if n == 1
    v = polyval(c{1}, s);
else
    idx = btsSegIndex(pp.breaks, s, leftSide);
    v = zeros(size(s));
    for k = 1:n
        m = (idx == k);
        if any(m)
            v(m) = polyval(c{k}, s(m));
        end
    end
end
v = reshape(v, sz);
end

function [s, v] = btsSample(pp, nP)
n = numel(pp.coefs);
s = zeros(1, n * nP);
v = zeros(1, n * nP);
for k = 1:n
    t = linspace(pp.breaks(k), pp.breaks(k+1), nP);
    j = (k-1)*nP + (1:nP);
    s(j) = t;
    v(j) = polyval(pp.coefs{k}, t);
end
end

function P = btsIntegratePP(pp, C0)
c = pp.coefs;
br = pp.breaks;
val = C0;
for k = 1:numel(c)
    q = polyint(c{k});
    q(end) = q(end) + val - polyval(q, br(k));
    c{k} = q;
    val = polyval(q, br(k+1));
end
P = struct('breaks', br, 'coefs', {c});
end

function br = btsMergeBreaks(x)
% Fusion triée de points de rupture (tolérance relative 1e-12·L).
x = sort(double(x(:).'));
x = x(isfinite(x));
if isempty(x)
    br = x;
    return
end
tol = btsTol(x);
keep = [true, diff(x) > tol];
br = x(keep);
end

function c = btsRefineCoefs(pp, br)
% Coefficients de pp sur la nouvelle subdivision br (variable globale : copie).
n = numel(br) - 1;
c = cell(1, n);
mid = (br(1:n) + br(2:n+1)) / 2;
idx = btsSegIndex(pp.breaks, mid(:), false);
for k = 1:n
    c{k} = pp.coefs{idx(k)};
end
end

function c = btsPolyAdd(a, b)
na = numel(a);
nb = numel(b);
n = max(na, nb);
c = [zeros(1, n - na), a(:).'] + [zeros(1, n - nb), b(:).'];
end

function v = btsPad(v, len)
v = v(:).';
if numel(v) < len
    v = [zeros(1, len - numel(v)), v];
elseif numel(v) > len
    v = v(end-len+1:end);
end
end

function g = btsShiftPoly(c, a)
% Coefficients en s du polynôme p(s) = Σ c_i (s - a)^(n-i) (schéma de Horner).
c = double(c(:).');
g = c(1);
for i = 2:numel(c)
    g = btsPolyAdd(conv(g, [1, -a]), c(i));
end
end

function str = btsPolyStr(c, var, isTex)
% Écriture d'un polynôme (texte ou LaTeX), termes nuls omis.
if ~isnumeric(c)
    error('MecaStruct:BeamAndTrussSolver:invalidArgument', 'Les coefficients doivent être numériques.');
end
c = double(c(:).');
str = '';
if isempty(c)
    str = '0';
    return
end
mx = max(abs(c(isfinite(c))));
if isempty(mx)
    mx = 0;
end
nC = numel(c);
% coefficients en variable globale s : les termes se compensent sur les tronçons éloignés de s = 0,
% 4 chiffres ne suffisent plus dès qu'il y a plusieurs termes
fmt = '%.4g';
if nnz(c ~= 0) > 1
    fmt = '%.8g';
end
for i = 1:nC
    a = c(i);
    if a == 0 || (isfinite(a) && abs(a) <= 1e-12 * mx)
        continue
    end
    p = nC - i;
    if isTex
        mag = btsTexNum(abs(a), fmt);
    else
        mag = sprintf(fmt, abs(a));
    end
    if p == 0
        term = mag;
    else
        if isTex
            if p == 1
                vp = var;
            else
                vp = sprintf('%s^{%d}', var, p);
            end
            if strcmp(mag, '1')
                term = vp;
            else
                term = [mag '\,' vp];
            end
        else
            if p == 1
                vp = var;
            else
                vp = sprintf('%s^%d', var, p);
            end
            if strcmp(mag, '1')
                term = vp;
            else
                term = [mag '*' vp];
            end
        end
    end
    if isempty(str)
        if a < 0
            str = ['-' term];
        else
            str = term;
        end
    elseif a < 0
        str = [str ' - ' term]; %#ok<AGROW>
    else
        str = [str ' + ' term]; %#ok<AGROW>
    end
end
if isempty(str)
    str = '0';
end
end

function s = btsNum(v)
% Nombre pour les textes de rapport (%.6g, -0 affiché 0).
s = sprintf('%.6g', v + 0);
end

function s = btsTexNum(v, fmt)
% Nombre au format LaTeX (%.4g par défaut, exposant écrit \cdot 10^{n}, -0 affiché 0).
if nargin < 2
    fmt = '%.4g';
end
s = sprintf(fmt, v + 0);
if strcmp(s, 'Inf')
    s = '\infty';
    return
elseif strcmp(s, '-Inf')
    s = '-\infty';
    return
elseif strcmp(s, 'NaN')
    s = '\mathrm{NaN}';
    return
end
k = strfind(s, 'e');
if ~isempty(k)
    mant = s(1:k-1);
    ex = str2double(s(k+1:end));
    if strcmp(mant, '1')
        s = sprintf('10^{%d}', ex);
    elseif strcmp(mant, '-1')
        s = sprintf('-10^{%d}', ex);
    else
        s = [mant ' \cdot 10^{' sprintf('%d', ex) '}'];
    end
end
end

function tf = btsHasSymbolic()
tf = DataManager.hasSymbolic();
end

%% =====================================================================
%%            FONCTIONS LOCALES : REPRÉSENTATION MATRICIELLE
%% =====================================================================
% Pour la performance, les efforts intérieurs sont manipulés en interne sous
% forme de matrices n×(D+1) (une ligne de coefficients polyval par tronçon,
% même degré maximal D), puis convertis en structures pp à la fin.

function [x, w] = btsGauss(ng)
% Points et poids de Gauss-Legendre sur [-1, 1] (Golub-Welsch), mémorisés.
persistent cache
if isempty(cache)
    cache = cell(1, 60);
end
if ng <= numel(cache) && ~isempty(cache{ng})
    x = cache{ng}{1};
    w = cache{ng}{2};
    return
end
if ng == 1
    x = 0;
    w = 2;
else
    k = 1:ng-1;
    beta = k ./ sqrt(4*k.^2 - 1);
    J = diag(beta, 1) + diag(beta, -1);
    [V, Dg] = eig(J);
    [x, ix] = sort(diag(Dg));
    w = 2 * (V(1, ix).').^2;
end
x = x(:);
w = w(:);
if ng <= numel(cache)
    cache{ng} = {x, w};
end
end

function G = btsGaussData(br, ng, D)
% Points de Gauss sur chaque tronçon (intégration exacte jusqu'au degré 2ng-1).
[xg, wg] = btsGauss(ng);
n = numel(br) - 1;
a = br(1:n);
b = br(2:n+1);
half = (b - a) / 2;
mid = (a + b) / 2;
pts = mid + half .* xg;
wts = half .* wg;
G.pts = pts(:);
G.w = wts(:);
seg = repmat(1:n, ng, 1);
G.seg = seg(:);
G.V = G.pts .^ (D:-1:0);
end

function vals = btsGaussVals(G, C)
vals = sum(G.V .* C(G.seg, :), 2);
end

function P = btsMatIntegrate(C, br)
% Primitive continue (nulle en br(1)) d'une représentation matricielle.
[n, w] = size(C);
P = [C ./ (w:-1:1), zeros(n, 1)];
val = 0;
for k = 1:n
    P(k, end) = val - polyval(P(k, :), br(k));
    val = polyval(P(k, :), br(k+1));
end
end

function v = btsMatEval(C, br, p)
% Évaluation (limite à droite) d'une représentation matricielle aux points p.
p = double(p(:));
if isempty(p)
    v = zeros(0, 1);
    return
end
idx = btsSegIndex(br, p, false);
pw = size(C, 2)-1:-1:0;
v = sum(C(idx, :) .* (p .^ pw), 2);
end

function C = btsCleanMat(C, br, absTol)
% Annule les termes dont la contribution maximale sur le tronçon est < absTol.
if absTol <= 0
    return
end
[n, w] = size(C);
smax = max(abs(br(1:n)), abs(br(2:n+1))).';
pw = w-1:-1:0;
bound = abs(C) .* (max(smax, 1e-300) .^ pw);
C(bound < absTol) = 0;
end

function pp = btsMatToPP(C, br)
n = size(C, 1);
c = cell(1, n);
for k = 1:n
    row = C(k, :);
    i1 = find(row ~= 0, 1);
    if isempty(i1)
        c{k} = 0;
    else
        c{k} = row(i1:end);
    end
end
pp = struct('breaks', br, 'coefs', {c});
end

function mx = btsMatMaxAbs(C, br)
% Maximum de |C| estimé aux bornes et aux points intérieurs de chaque tronçon.
n = size(C, 1);
mx = 0;
for k = 1:n
    t = linspace(br(k), br(k+1), 9);
    mx = max(mx, max(abs(polyval(C(k, :), t))));
end
end

function [T, M] = btsCutBend(br, tol, fx, fv, cx, cv, dl, D)
% Méthode des coupures (somme des actions à droite) pour un problème plan :
%   T(s) = Σ_droite F + ∫_s^L p dx ; M(s) = Σ_droite [(x - s) F + C] + ∫_s^L (x - s) p dx
n = numel(br) - 1;
T = zeros(n, D+1);
M = zeros(n, D+1);
sR = br(2:end).';
sL = br(1:n).';
if ~isempty(fx)
    msk = double(fx(:).' >= sR - tol);
    Fs = msk * fv(:);
    T(:, D+1) = Fs;
    M(:, D) = -Fs;
    M(:, D+1) = msk * (fv(:) .* fx(:));
end
if ~isempty(cx)
    msk = double(cx(:).' >= sR - tol);
    M(:, D+1) = M(:, D+1) + msk * cv(:);
end
for j = 1:numel(dl)
    d = dl(j);
    right = d.a >= sR - tol;
    if any(right)
        T(right, D+1) = T(right, D+1) + d.I0;
        M(right, D) = M(right, D) - d.I0;
        M(right, D+1) = M(right, D+1) + d.I1;
    end
    inside = (d.a <= sL + tol) & (d.b >= sR - tol);
    if any(inside)
        % T(s) = P(b) - P(s) ; M(s) = Q(b) - Q(s) - s·P(b) + s·P(s)
        Tin = btsPad(-d.P, D+1);
        Tin(D+1) = Tin(D+1) + d.Pb;
        Min = btsPad(-d.Q, D+1) + btsPad([d.P 0], D+1);
        Min(D) = Min(D) - d.Pb;
        Min(D+1) = Min(D+1) + d.Qb;
        T(inside, :) = T(inside, :) + Tin;
        M(inside, :) = M(inside, :) + Min;
    end
end
end

%% =====================================================================
%%                  FONCTIONS LOCALES : POUTRES
%% =====================================================================

function o = btsBeamOpts(opts)
o = struct('internalMethod', 'both', 'hyperMethod', 'both', 'useSymbolic', [], ...
    'includeShearEnergy', false);
if ~isempty(opts)
    if ~isstruct(opts) || ~isscalar(opts)
        error('MecaStruct:Beam:invalidOption', 'Les options doivent être une structure scalaire.');
    end
    if isfield(opts, 'internalMethod') && ~isempty(opts.internalMethod)
        v = btsAscii(lower(char(opts.internalMethod)));
        if ~ismember(v, {'both', 'coupures', 'integrale'})
            error('MecaStruct:Beam:invalidOption', ...
                'internalMethod doit valoir ''both'', ''coupures'' ou ''integrale''.');
        end
        o.internalMethod = v;
    end
    if isfield(opts, 'hyperMethod') && ~isempty(opts.hyperMethod)
        v = btsAscii(lower(char(opts.hyperMethod)));
        if ~ismember(v, {'both', 'menabrea', 'integration'})
            error('MecaStruct:Beam:invalidOption', ...
                'hyperMethod doit valoir ''both'', ''menabrea'' ou ''integration''.');
        end
        o.hyperMethod = v;
    end
    if isfield(opts, 'useSymbolic') && ~isempty(opts.useSymbolic)
        if ~isscalar(opts.useSymbolic) || ~(islogical(opts.useSymbolic) || isnumeric(opts.useSymbolic))
            error('MecaStruct:Beam:invalidOption', 'useSymbolic doit être un booléen.');
        end
        o.useSymbolic = logical(opts.useSymbolic);
    end
    if isfield(opts, 'includeShearEnergy') && ~isempty(opts.includeShearEnergy)
        if ~isscalar(opts.includeShearEnergy) || ~(islogical(opts.includeShearEnergy) || isnumeric(opts.includeShearEnergy))
            error('MecaStruct:Beam:invalidOption', 'includeShearEnergy doit être un booléen.');
        end
        o.includeShearEnergy = logical(opts.includeShearEnergy);
    end
end
if isempty(o.useSymbolic)
    o.useSymbolic = btsHasSymbolic();
else
    o.useSymbolic = o.useSymbolic && btsHasSymbolic();
end
end

function s = btsAscii(s)
% Suppression des accents usuels (comparaison d'options et de types).
s = strrep(s, 'é', 'e');
s = strrep(s, 'è', 'e');
s = strrep(s, 'ê', 'e');
s = strrep(s, 'à', 'a');
s = strrep(s, 'â', 'a');
s = strrep(s, 'î', 'i');
s = strrep(s, 'ô', 'o');
s = strrep(s, 'û', 'u');
s = strrep(s, 'ç', 'c');
end

function tf = btsIsNum(v)
tf = isnumeric(v) && isscalar(v) && isreal(v) && isfinite(v);
end

function v = btsVec(sa, f)
% Champ f d'un tableau de structures sous forme de vecteur ligne.
if isempty(sa)
    v = zeros(1, 0);
else
    v = [sa.(f)];
    v = double(v(:).');
end
end

function c = btsCellField(sa, f)
if isempty(sa)
    c = cell(1, 0);
else
    c = {sa.(f)};
end
end

function v = btsReqPos(s, f, what, i, L, tol)
if ~isfield(s, f) || ~btsIsNum(s.(f))
    error('MecaStruct:Beam:invalidModel', '%s n°%d : champ ''%s'' (m) manquant ou invalide.', what, i, f);
end
v = double(s.(f));
if v < -tol || v > L + tol
    error('MecaStruct:Beam:invalidModel', ...
        '%s n°%d : %s = %g m hors de la poutre [0, %g] m.', what, i, f, v, L);
end
v = min(max(v, 0), L);
end

function v = btsOptNum(s, f, what, i)
v = 0;
if isfield(s, f) && ~isempty(s.(f))
    if ~btsIsNum(s.(f))
        error('MecaStruct:Beam:invalidModel', '%s n°%d : champ ''%s'' invalide (réel fini attendu).', what, i, f);
    end
    v = double(s.(f));
end
end

function nm = btsOptName(s, def)
nm = def;
if isfield(s, 'name') && ~isempty(s.name) && (ischar(s.name) || (isstring(s.name) && isscalar(s.name)))
    nm = strtrim(char(s.name));
    if isempty(nm)
        nm = def;
    end
end
end

function arr = btsGetArr(model, f)
arr = [];
if isfield(model, f) && ~isempty(model.(f))
    arr = model.(f);
    if ~isstruct(arr)
        error('MecaStruct:Beam:invalidModel', 'model.%s doit être un tableau de structures (ou vide).', f);
    end
end
end

function t = btsNormType(t, i)
if ~(ischar(t) || (isstring(t) && isscalar(t)))
    error('MecaStruct:Beam:invalidSupport', 'Appui n°%d : type invalide.', i);
end
t0 = char(t);
t = btsAscii(lower(strtrim(t0)));
t = regexprep(t, '[\s\-]+', '_');
switch t
    case {'appui_simple', 'appui', 'appui_ponctuel', 'simple', 'appui_plan'}
        t = 'appui_simple';
    case {'rotule', 'articulation', 'rotule_spherique'}
        t = 'rotule';
    case 'pivot'
        t = 'pivot';
    case {'pivot_glissant', 'glissiere'}
        t = 'pivot_glissant';
    case {'encastrement', 'encastre', 'encastree'}
        t = 'encastrement';
    otherwise
        error('MecaStruct:Beam:invalidSupport', ...
            ['Appui n°%d : type ''%s'' inconnu (attendu : appui_simple, rotule, pivot, ' ...
            'pivot_glissant, encastrement).'], i, t0);
end
end

function [m, notes] = btsNormalizeModel(model)
% Normalisation du modèle de poutre (champs par défaut, tableaux vides typés).
if ~isstruct(model) || ~isscalar(model)
    error('MecaStruct:Beam:invalidModel', 'Le modèle de poutre doit être une structure scalaire.');
end
if ~isfield(model, 'L') || ~btsIsNum(model.L) || model.L <= 0
    error('MecaStruct:Beam:invalidModel', 'model.L (longueur, m) doit être un réel strictement positif.');
end
notes = cell(0, 1);
m = model;
m.L = double(model.L);
L = m.L;
tol = 1e-12 * L;
defs = {'E', 210e9, 'Pa'; 'S', 1e-3, 'm²'; 'Iz', 1e-5, 'm⁴'; 'Iy', 1e-5, 'm⁴'};
for k = 1:size(defs, 1)
    f = defs{k, 1};
    if ~isfield(model, f) || isempty(model.(f))
        m.(f) = defs{k, 2};
        notes{end+1, 1} = sprintf('%s non fourni : valeur par défaut %g %s (sans effet sur les réactions d''un sous-problème homogène).', ...
            f, defs{k, 2}, defs{k, 3}); %#ok<AGROW>
    elseif ~btsIsNum(model.(f)) || model.(f) <= 0
        error('MecaStruct:Beam:invalidModel', 'model.%s doit être un réel strictement positif.', f);
    else
        m.(f) = double(model.(f));
    end
end
if ~isfield(model, 'G') || isempty(model.G)
    m.G = m.E / 2.6;
    notes{end+1, 1} = sprintf('G non fourni : G = E/(2(1+0,3)) = %g Pa.', m.G);
elseif ~btsIsNum(model.G) || model.G <= 0
    error('MecaStruct:Beam:invalidModel', 'model.G doit être un réel strictement positif.');
else
    m.G = double(model.G);
end
if ~isfield(model, 'Ix') || isempty(model.Ix)
    m.Ix = m.Iz + m.Iy;
    notes{end+1, 1} = sprintf('Ix non fourni : Ix = Iz + Iy = %g m⁴.', m.Ix);
elseif ~btsIsNum(model.Ix) || model.Ix <= 0
    error('MecaStruct:Beam:invalidModel', 'model.Ix doit être un réel strictement positif.');
else
    m.Ix = double(model.Ix);
end
for f = {'ky', 'kz'}
    if ~isfield(model, f{1}) || isempty(model.(f{1}))
        m.(f{1}) = 1;
    elseif ~btsIsNum(model.(f{1})) || model.(f{1}) <= 0
        error('MecaStruct:Beam:invalidModel', 'model.%s doit être un réel strictement positif.', f{1});
    else
        m.(f{1}) = double(model.(f{1}));
    end
end

% --- appuis
arr = btsGetArr(model, 'supports');
sup = struct('pos', {}, 'type', {}, 'name', {});
for i = 1:numel(arr)
    si = arr(i);
    if i <= 26
        def = char('A' + i - 1);
    else
        def = sprintf('A%d', i);
    end
    if ~isfield(si, 'type')
        error('MecaStruct:Beam:invalidSupport', 'Appui n°%d : champ ''type'' manquant.', i);
    end
    sup(i).pos = btsReqPos(si, 'pos', 'Appui', i, L, tol);
    sup(i).type = btsNormType(si.type, i);
    sup(i).name = btsOptName(si, def);
end
m.supports = sup;

% --- forces ponctuelles
arr = btsGetArr(model, 'pointLoads');
pl = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
for i = 1:numel(arr)
    si = arr(i);
    pl(i).pos = btsReqPos(si, 'pos', 'Force ponctuelle', i, L, tol);
    pl(i).Fx = btsOptNum(si, 'Fx', 'Force ponctuelle', i);
    pl(i).Fy = btsOptNum(si, 'Fy', 'Force ponctuelle', i);
    pl(i).Fz = btsOptNum(si, 'Fz', 'Force ponctuelle', i);
    pl(i).name = btsOptName(si, sprintf('F%d', i));
end
m.pointLoads = pl;

% --- couples ponctuels
arr = btsGetArr(model, 'pointMoments');
pm = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
for i = 1:numel(arr)
    si = arr(i);
    pm(i).pos = btsReqPos(si, 'pos', 'Couple ponctuel', i, L, tol);
    pm(i).Mx = btsOptNum(si, 'Mx', 'Couple ponctuel', i);
    pm(i).My = btsOptNum(si, 'My', 'Couple ponctuel', i);
    pm(i).Mz = btsOptNum(si, 'Mz', 'Couple ponctuel', i);
    pm(i).name = btsOptName(si, sprintf('C%d', i));
end
m.pointMoments = pm;

% --- charges réparties
arr = btsGetArr(model, 'distLoads');
dl = struct('a', {}, 'b', {}, 'dir', {}, 'coeffs', {}, 'name', {});
for i = 1:numel(arr)
    si = arr(i);
    a = btsReqPos(si, 'a', 'Charge répartie', i, L, tol);
    b = btsReqPos(si, 'b', 'Charge répartie', i, L, tol);
    if b - a <= tol
        error('MecaStruct:Beam:invalidModel', 'Charge répartie n°%d : il faut a < b (a = %g m, b = %g m).', i, a, b);
    end
    if ~isfield(si, 'dir') || ~(ischar(si.dir) || (isstring(si.dir) && isscalar(si.dir))) ...
            || ~ismember(lower(char(si.dir)), {'x', 'y', 'z'})
        error('MecaStruct:Beam:invalidModel', 'Charge répartie n°%d : dir doit valoir ''x'', ''y'' ou ''z''.', i);
    end
    if ~isfield(si, 'coeffs') || isempty(si.coeffs) || ~isnumeric(si.coeffs) || ~isvector(si.coeffs) ...
            || any(~isfinite(si.coeffs(:))) || ~isreal(si.coeffs)
        error('MecaStruct:Beam:invalidModel', ...
            'Charge répartie n°%d : coeffs (N/m, ordre polyval en ξ = s - a) manquants ou invalides.', i);
    end
    dl(i).a = a;
    dl(i).b = b;
    dl(i).dir = lower(char(si.dir));
    dl(i).coeffs = double(si.coeffs(:).');
    dl(i).name = btsOptName(si, sprintf('q%d', i));
end
m.distLoads = dl;
end

function d = btsPrepDist(dlm)
% Pré-calculs des charges réparties : polynôme global, primitives, résultantes.
d = struct('a', {}, 'b', {}, 'dir', {}, 'pg', {}, 'P', {}, 'Q', {}, 'Pa', {}, 'Pb', {}, ...
    'Qa', {}, 'Qb', {}, 'I0', {}, 'I1', {}, 'deg', {}, 'absInt', {}, 'name', {}, 'coeffs', {});
for k = 1:numel(dlm)
    a = dlm(k).a;
    b = dlm(k).b;
    pg = btsShiftPoly(dlm(k).coeffs, a);
    i1 = find(pg ~= 0, 1);
    if isempty(i1)
        pg = 0;
    else
        pg = pg(i1:end);
    end
    P = polyint(pg);
    Q = polyint([pg 0]);
    Pa = polyval(P, a);
    Pb = polyval(P, b);
    Qa = polyval(Q, a);
    Qb = polyval(Q, b);
    t = linspace(a, b, 9);
    d(k).a = a;
    d(k).b = b;
    d(k).dir = dlm(k).dir;
    d(k).pg = pg;
    d(k).P = P;
    d(k).Q = Q;
    d(k).Pa = Pa;
    d(k).Pb = Pb;
    d(k).Qa = Qa;
    d(k).Qb = Qb;
    d(k).I0 = Pb - Pa;
    d(k).I1 = Qb - Qa;
    d(k).deg = numel(pg) - 1;
    d(k).absInt = (b - a) * max(abs(polyval(pg, t)));
    d(k).name = dlm(k).name;
    d(k).coeffs = dlm(k).coeffs;
end
end

function id = btsTexId(name, i)
id = regexprep(char(name), '[^A-Za-z0-9]', '');
if isempty(id)
    id = sprintf('%d', i);
end
end

function unk = btsMakeUnk(sup, iF, fTxt, fTex, fField, fUnit, fTexUnit, iC, cTxt, cTex, cField, cSgn)
% Liste des inconnues de liaison d'un sous-problème.
unk = struct('kind', {}, 'sup', {}, 'pos', {}, 'name', {}, 'tex', {}, 'field', {}, ...
    'sgn', {}, 'unit', {}, 'texUnit', {});
for i = iF(:).'
    id = btsTexId(sup(i).name, i);
    unk(end+1) = struct('kind', 'F', 'sup', i, 'pos', sup(i).pos, ...
        'name', sprintf(fTxt, sup(i).name), 'tex', sprintf(fTex, id), 'field', fField, ...
        'sgn', 1, 'unit', fUnit, 'texUnit', fTexUnit); %#ok<AGROW>
end
for i = iC(:).'
    id = btsTexId(sup(i).name, i);
    unk(end+1) = struct('kind', 'C', 'sup', i, 'pos', sup(i).pos, ...
        'name', sprintf(cTxt, sup(i).name), 'tex', sprintf(cTex, id), 'field', cField, ...
        'sgn', cSgn, 'unit', 'N·m', 'texUnit', 'N\,m'); %#ok<AGROW>
end
end

function sps = btsBuildSubs(mdl, dl, nameA)
% Définition des 4 sous-problèmes indépendants (axial, xy, xz, torsion).
% Le plan (x,z) est traité comme un problème plan équivalent : F' = Fz,
% C' = -Cy, p' = pz, alors Tz = T' et Mfy = -M'.
sup = mdl.supports;
ns = numel(sup);
types = btsCellField(sup, 'type');
bu = find(ismember(types, {'rotule', 'pivot', 'encastrement'}));
enc = find(strcmp(types, 'encastrement'));
allIdx = 1:ns;
PL = mdl.pointLoads;
PM = mdl.pointMoments;
plPos = btsVec(PL, 'pos');
pmPos = btsVec(PM, 'pos');
dirs = btsCellField(dl, 'dir');
none = zeros(1, 0);

s1 = struct();
s1.name = 'axial';
s1.label = 'Axial (u)';
s1.kind = 'bar';
s1.fx = plPos; s1.fv = btsVec(PL, 'Fx');
s1.cx = none; s1.cv = none;
s1.dl = dl(strcmp(dirs, 'x'));
s1.unk = btsMakeUnk(sup, bu, 'X_%s', 'X_{%s}', 'Rx', 'N', 'N', [], '', '', '', 1);
s1.stiff = mdl.E * mdl.S; s1.stiffTxt = 'E·S'; s1.stiffTex = 'E\,S';
s1.shear = Inf;
s1.eqTxt = {'Σ Fx = 0'}; s1.eqTex = {'\sum F_{x} = 0'};
s1.rowSign = 1;
s1.intTxt = 'E·S·u''(s) = N(s)  ->  u(s) = C1 + (1/ES)·∫_0^s N dx';
s1.intTex = '$E\,S\,u''(s) = N(s) \Rightarrow u(s) = C_1 + \frac{1}{E\,S}\int_0^s N\,dx$';
s1.dispTxt = 'u'; s1.constNames = {'C1 = u(0)'};
s1.energyTxt = 'U = ∫ N²/(2·E·S) ds';
s1.energyTex = '$\delta_{ij} = \int_0^L \frac{n_i\,n_j}{E\,S}\,ds,\ \ \delta_{i0} = \int_0^L \frac{n_i\,N_0}{E\,S}\,ds$';
s1.compT = 'N'; s1.compM = '';

s2 = struct();
s2.name = 'xy';
s2.label = 'Flexion (x,y)';
s2.kind = 'bend';
s2.fx = plPos; s2.fv = btsVec(PL, 'Fy');
s2.cx = pmPos; s2.cv = btsVec(PM, 'Mz');
s2.dl = dl(strcmp(dirs, 'y'));
s2.unk = btsMakeUnk(sup, allIdx, 'Y_%s', 'Y_{%s}', 'Ry', 'N', 'N', enc, 'Mz_%s', 'M_{z%s}', 'Mz', 1);
s2.stiff = mdl.E * mdl.Iz; s2.stiffTxt = 'E·Iz'; s2.stiffTex = 'E\,I_z';
s2.shear = mdl.ky * mdl.G * mdl.S; s2.shearTxt = 'ky·G·S'; s2.shearTex = 'k_y\,G\,S';
s2.eqTxt = {'Σ Fy = 0', sprintf('Σ Mz(%s) = 0', nameA)};
s2.eqTex = {'\sum F_{y} = 0', ['\sum M_{z}(' btsTexId(nameA, 0) ') = 0']};
s2.rowSign = [1 1];
s2.intTxt = 'E·Iz·v''''(s) = Mfz(s)  ->  v(s) = C1 + C2·s + (1/EIz)·∫∫ Mfz';
s2.intTex = '$E\,I_z\,v''''(s) = M_{fz}(s) \Rightarrow v(s) = C_1 + C_2\,s + \frac{1}{E\,I_z}\int_0^s\!\!\int_0^t M_{fz}\,dx\,dt$';
s2.dispTxt = 'v'; s2.constNames = {'C1 = v(0)', 'C2 = v''(0)'};
s2.energyTxt = 'U = ∫ Mfz²/(2·E·Iz) ds';
s2.energyTex = '$\delta_{ij} = \int_0^L \frac{m_i\,m_j}{E\,I_z}\,ds,\ \ \delta_{i0} = \int_0^L \frac{m_i\,M_0}{E\,I_z}\,ds$';
s2.compT = 'Ty'; s2.compM = 'Mfz';

s3 = struct();
s3.name = 'xz';
s3.label = 'Flexion (x,z)';
s3.kind = 'bend';
s3.fx = plPos; s3.fv = btsVec(PL, 'Fz');
s3.cx = pmPos; s3.cv = -btsVec(PM, 'My');
s3.dl = dl(strcmp(dirs, 'z'));
s3.unk = btsMakeUnk(sup, allIdx, 'Z_%s', 'Z_{%s}', 'Rz', 'N', 'N', enc, 'My_%s', 'M_{y%s}', 'My', -1);
s3.stiff = mdl.E * mdl.Iy; s3.stiffTxt = 'E·Iy'; s3.stiffTex = 'E\,I_y';
s3.shear = mdl.kz * mdl.G * mdl.S; s3.shearTxt = 'kz·G·S'; s3.shearTex = 'k_z\,G\,S';
s3.eqTxt = {'Σ Fz = 0', sprintf('Σ My(%s) = 0', nameA)};
s3.eqTex = {'\sum F_{z} = 0', ['\sum M_{y}(' btsTexId(nameA, 0) ') = 0']};
s3.rowSign = [1 -1];
s3.intTxt = 'E·Iy·w''''(s) = -Mfy(s)  ->  w(s) = C1 + C2·s - (1/EIy)·∫∫ Mfy';
s3.intTex = '$E\,I_y\,w''''(s) = -M_{fy}(s) \Rightarrow w(s) = C_1 + C_2\,s - \frac{1}{E\,I_y}\int_0^s\!\!\int_0^t M_{fy}\,dx\,dt$';
s3.dispTxt = 'w'; s3.constNames = {'C1 = w(0)', 'C2 = w''(0)'};
s3.energyTxt = 'U = ∫ Mfy²/(2·E·Iy) ds';
s3.energyTex = '$\delta_{ij} = \int_0^L \frac{m_i\,m_j}{E\,I_y}\,ds,\ \ \delta_{i0} = \int_0^L \frac{m_i\,M_0}{E\,I_y}\,ds$';
s3.compT = 'Tz'; s3.compM = 'Mfy';

s4 = struct();
s4.name = 'torsion';
s4.label = 'Torsion (θx)';
s4.kind = 'bar';
s4.fx = pmPos; s4.fv = btsVec(PM, 'Mx');
s4.cx = none; s4.cv = none;
s4.dl = dl([]);
s4.unk = btsMakeUnk(sup, enc, 'Mx_%s', 'M_{x%s}', 'Mx', 'N·m', 'N\,m', [], '', '', '', 1);
s4.stiff = mdl.G * mdl.Ix; s4.stiffTxt = 'G·Ix'; s4.stiffTex = 'G\,I_x';
s4.shear = Inf;
s4.eqTxt = {'Σ Mx = 0'}; s4.eqTex = {'\sum M_{x} = 0'};
s4.rowSign = 1;
s4.intTxt = 'G·Ix·φ''(s) = Mt(s)  ->  φ(s) = C1 + (1/GIx)·∫_0^s Mt dx';
s4.intTex = '$G\,I_x\,\varphi''(s) = M_t(s) \Rightarrow \varphi(s) = C_1 + \frac{1}{G\,I_x}\int_0^s M_t\,dx$';
s4.dispTxt = 'φ'; s4.constNames = {'C1 = φ(0)'};
s4.energyTxt = 'U = ∫ Mt²/(2·G·Ix) ds';
s4.energyTex = '$\delta_{ij} = \int_0^L \frac{t_i\,t_j}{G\,I_x}\,ds,\ \ \delta_{i0} = \int_0^L \frac{t_i\,M_{t0}}{G\,I_x}\,ds$';
s4.compT = 'Mt'; s4.compM = '';

if ~isfield(s1, 'shearTxt')
    s1.shearTxt = ''; s1.shearTex = '';
    s4.shearTxt = ''; s4.shearTex = '';
end
sps = {s1, s2, s3, s4};
end

function order = btsBaseOrder(unk, isBend)
% Ordre de préférence des réactions conservées dans le système de base :
% encastrement (console) d'abord, sinon appuis extrêmes (poutre sur 2 appuis).
nu = numel(unk);
if nu == 0
    order = zeros(1, 0);
    return
end
pos = btsVec(unk, 'pos');
isC = strcmp(btsCellField(unk, 'kind'), 'C');
supIdx = btsVec(unk, 'sup');
iF = find(~isC);
[~, k] = sort(pos(iF));
iF = iF(k);
order = zeros(1, 0);
if isBend && any(isC)
    c1 = find(isC, 1);
    f1 = iF(supIdx(iF) == supIdx(c1));
    order = [f1, c1];
end
if ~isempty(iF)
    order = [order, iF(1), iF(end), iF(2:end-1)];
end
order = [order, find(isC)];
order = unique(order, 'stable');
end

function sp = btsSolveSub(sp, br, tol, D, Gq, o, L, xA)
% Résolution d'un sous-problème (réactions puis efforts intérieurs par coupures).
n = numel(br) - 1;
isBend = strcmp(sp.kind, 'bend');
neq = 1 + double(isBend);
nu = numel(sp.unk);
[TL, ML] = btsCutBend(br, tol, sp.fx, sp.fv, sp.cx, sp.cv, sp.dl, D);
TU = zeros(n, D+1, nu);
MU = zeros(n, D+1, nu);
sR = br(2:end).';
for j = 1:nu
    msk = double(sp.unk(j).pos >= sR - tol);
    if isBend && sp.unk(j).kind == 'C'
        MU(:, D+1, j) = msk;
    else
        TU(:, D+1, j) = msk;
        if isBend
            MU(:, D, j) = -msk;
            MU(:, D+1, j) = msk * sp.unk(j).pos;
        end
    end
end

% --- équations d'équilibre A·R + b = 0 (moments au point A d'abscisse xA)
I0 = 0;
I1 = 0;
absP = 0;
loadedDist = false;
for k = 1:numel(sp.dl)
    I0 = I0 + sp.dl(k).I0;
    I1 = I1 + sp.dl(k).I1;
    absP = absP + sp.dl(k).absInt;
    loadedDist = loadedDist || any(sp.dl(k).pg ~= 0);
end
A = zeros(neq, nu);
bv = zeros(neq, 1);
bv(1) = sum(sp.fv) + I0;
for j = 1:nu
    if ~isBend || sp.unk(j).kind == 'F'
        A(1, j) = 1;
    end
end
scaleEq = sum(abs(sp.fv)) + absP;
if isBend
    for j = 1:nu
        if sp.unk(j).kind == 'F'
            A(2, j) = sp.unk(j).pos - xA;
        else
            A(2, j) = 1;
        end
    end
    bv(2) = sum((sp.fx - xA) .* sp.fv) + sum(sp.cv) + I1 - xA * I0;
    scaleEq = [scaleEq; scaleEq * L + sum(abs(sp.cv))];
end
loaded = any(sp.fv ~= 0) || any(sp.cv ~= 0) || loadedDist;

if nu == 0
    rA = 0;
else
    rA = rank(A);
end
R = zeros(nu, 1);
men = [];
intg = [];
Rmen = [];
Rint = [];
hyperCheck = NaN;
degenerate = false;
if rA < neq
    % liaisons insuffisantes : chargement compatible ou mécanisme
    if nu > 0
        R = pinv(A) * (-bv);
    end
    res = abs(A * R + bv);
    if any(res > 1e-9 * scaleEq)
        error('MecaStruct:Beam:mechanism', ...
            ['Mécanisme : sous-problème %s, liaisons insuffisantes ou mal disposées pour le ' ...
            'chargement appliqué (%d inconnue(s) de liaison, rang %d < %d équation(s)).'], ...
            sp.label, nu, rA, neq);
    end
    h = nu - rA;
    if h > 0
        degenerate = true;
        [R, intg] = btsIntegration(sp, A, bv, TL, ML, TU, MU, br, o, true);
        Rint = R;
        Rmen = R;
    end
    status = 'liaisons insuffisantes, chargement compatible';
else
    h = nu - neq;
    if h == 0
        R = -(A \ bv);
        status = 'isostatique';
    elseif ~loaded
        status = 'hyperstatique non chargé';
        Rmen = R;
        Rint = R;
    else
        status = 'hyperstatique';
        doMen = any(strcmp(o.hyperMethod, {'both', 'menabrea'}));
        doInt = any(strcmp(o.hyperMethod, {'both', 'integration'}));
        if doMen
            [Rmen, men] = btsMenabrea(sp, A, bv, TL, ML, TU, MU, Gq, o, isBend);
        end
        if doInt
            [Rint, intg] = btsIntegration(sp, A, bv, TL, ML, TU, MU, br, o, false);
        end
        if doMen
            R = Rmen;
        else
            R = Rint;
        end
        if doMen && doInt
            hyperCheck = btsReactionDiff(Rmen, Rint, sp.unk, isBend, scaleEq);
        end
    end
end

% --- nettoyage des réactions (bruit numérique)
R = btsCleanReactions(R, sp.unk, isBend, scaleEq);
if ~isempty(Rmen)
    Rmen = btsCleanReactions(Rmen, sp.unk, isBend, scaleEq);
end
if ~isempty(Rint)
    Rint = btsCleanReactions(Rint, sp.unk, isBend, scaleEq);
end

T = TL;
M = ML;
if nu > 0
    Rr = reshape(R, 1, 1, nu);
    T = T + sum(TU .* Rr, 3);
    M = M + sum(MU .* Rr, 3);
end
sp.A = A;
sp.b = bv;
sp.scaleEq = scaleEq;
sp.loaded = loaded;
sp.nunk = nu;
sp.neq = neq;
sp.rank = rA;
sp.h = h;
sp.R = R;
sp.T = T;
sp.M = M;
sp.men = men;
sp.int = intg;
sp.Rmen = Rmen;
sp.Rint = Rint;
sp.hyperCheck = hyperCheck;
sp.status = status;
sp.degenerate = degenerate;
sp.loadMoments = btsLoadMoments(sp, xA);
end

function R = btsCleanReactions(R, unk, isBend, scaleEq)
% Annule les réactions de l'ordre du bruit numérique (relatif à l'échelle des charges).
for j = 1:numel(R)
    if isBend && unk(j).kind == 'C'
        sc = scaleEq(end);
    else
        sc = scaleEq(1);
    end
    if abs(R(j)) <= 1e-13 * sc
        R(j) = 0;
    end
end
R = R + 0;
end

function lm = btsLoadMoments(sp, xA)
% Moments au point A des charges du sous-problème (affichage du transport).
lm = struct('label', {}, 'value', {});
if ~strcmp(sp.kind, 'bend')
    return
end
sg = sp.rowSign(end);
if sg < 0
    pre = '-';
else
    pre = '';
end
for j = 1:numel(sp.fx)
    if sp.fv(j) ~= 0
        lm(end+1) = struct('label', sprintf('force en s = %s : %s(%s - %s)·(%s)', btsNum(sp.fx(j)), pre, ...
            btsNum(sp.fx(j)), btsNum(xA), btsNum(sp.fv(j))), 'value', sg * (sp.fx(j) - xA) * sp.fv(j)); %#ok<AGROW>
    end
end
for j = 1:numel(sp.cx)
    if sp.cv(j) ~= 0
        lm(end+1) = struct('label', sprintf('couple en s = %s', btsNum(sp.cx(j))), 'value', sg * sp.cv(j)); %#ok<AGROW>
    end
end
for k = 1:numel(sp.dl)
    d = sp.dl(k);
    if any(d.pg ~= 0)
        lm(end+1) = struct('label', sprintf('charge répartie %s : ∫(x - %s)·p dx sur [%s ; %s]', d.name, ...
            btsNum(xA), btsNum(d.a), btsNum(d.b)), 'value', sg * (d.I1 - xA * d.I0)); %#ok<AGROW>
    end
end
end

function e = btsReactionDiff(R1, R2, unk, isBend, scaleEq)
% Écart relatif max entre deux jeux de réactions.
e = 0;
for j = 1:numel(R1)
    if isBend && unk(j).kind == 'C'
        sc = scaleEq(end);
    else
        sc = scaleEq(1);
    end
    den = max([abs(R1(j)), sc]);
    if den == 0
        den = 1;
    end
    e = max(e, abs(R1(j) - R2(j)) / den);
end
end

function [R, men] = btsMenabrea(sp, A, bv, TL, ML, TU, MU, Gq, o, isBend)
% Théorème de Ménabréa : dU/dXi = 0 sur un système de base isostatique.
[neq, nu] = size(A);
order = btsBaseOrder(sp.unk, isBend);
base = zeros(1, 0);
for j = order
    cand = [base, j];
    if rank(A(:, cand)) == numel(cand)
        base = cand;
    end
    if numel(base) == neq
        break
    end
end
Xi = setdiff(1:nu, base, 'stable');
Ab = A(:, base);
R0 = -(Ab \ bv);
rb = -(Ab \ A(:, Xi));
h = numel(Xi);
if isBend
    U = MU;
    P0 = ML;
else
    U = TU;
    P0 = TL;
end
Ub = U(:, :, base);
P0 = P0 + sum(Ub .* reshape(R0, 1, 1, []), 3);
v0 = btsGaussVals(Gq, P0);
V = zeros(numel(Gq.w), h);
for i = 1:h
    Pi = U(:, :, Xi(i)) + sum(Ub .* reshape(rb(:, i), 1, 1, []), 3);
    V(:, i) = btsGaussVals(Gq, Pi);
end
delta = (V.' * (Gq.w .* V)) / sp.stiff;
d0 = (V.' * (Gq.w .* v0)) / sp.stiff;
withShear = isBend && o.includeShearEnergy && isfinite(sp.shear);
if withShear
    TUb = TU(:, :, base);
    Q0 = TL + sum(TUb .* reshape(R0, 1, 1, []), 3);
    q0 = btsGaussVals(Gq, Q0);
    W = zeros(numel(Gq.w), h);
    for i = 1:h
        Qi = TU(:, :, Xi(i)) + sum(TUb .* reshape(rb(:, i), 1, 1, []), 3);
        W(:, i) = btsGaussVals(Gq, Qi);
    end
    delta = delta + (W.' * (Gq.w .* W)) / sp.shear;
    d0 = d0 + (W.' * (Gq.w .* q0)) / sp.shear;
end
rhs = -d0;
if rcond(delta) < 1e-14
    X = lsqminnorm(delta, rhs);
else
    X = delta \ rhs;
end
R = zeros(nu, 1);
R(Xi) = X;
R(base) = R0 + rb * X;
names = btsCellField(sp.unk, 'name');
texs = btsCellField(sp.unk, 'tex');
men = struct('subproblem', sp.name, 'label', sp.label, 'unknowns', {names(Xi)}, ...
    'unknownsTex', {texs(Xi)}, 'base', {names(base)}, 'delta', delta, 'delta0', d0, ...
    'rhs', rhs, 'X', X, 'includeShear', withShear, 'sgn', btsVec(sp.unk(Xi), 'sgn'));   % sgn : plan équivalent -> réaction physique
end

function [v, th] = btsBendDisp(M, T, br, P, EI, kGS, useShear)
% Flèche et rotation (intégrations depuis s = 0, constantes nulles) aux points P.
I1 = btsMatIntegrate(M, br);
I2 = btsMatIntegrate(I1, br);
th = btsMatEval(I1, br, P) / EI;
v = btsMatEval(I2, br, P) / EI;
if useShear
    v = v + btsMatEval(btsMatIntegrate(T, br), br, P) / kGS;
end
end

function [R, info] = btsIntegration(sp, A, bv, TL, ML, TU, MU, br, o, forceLsq)
% Méthode d'intégration : réactions + constantes résolues simultanément
% (équilibre + conditions cinématiques aux liaisons).
isBend = strcmp(sp.kind, 'bend');
[neq, nu] = size(A);
nc = neq;
P = btsVec(sp.unk, 'pos');
useShear = isBend && o.includeShearEnergy && isfinite(sp.shear);
Vp = zeros(nu, nu);
THp = zeros(nu, nu);
if isBend
    [vL, thL] = btsBendDisp(ML, TL, br, P, sp.stiff, sp.shear, useShear);
    for j = 1:nu
        [Vp(:, j), THp(:, j)] = btsBendDisp(MU(:, :, j), TU(:, :, j), br, P, sp.stiff, sp.shear, useShear);
    end
else
    vL = btsMatEval(btsMatIntegrate(TL, br), br, P) / sp.stiff;
    thL = zeros(nu, 1);
    for j = 1:nu
        Vp(:, j) = btsMatEval(btsMatIntegrate(TU(:, :, j), br), br, P) / sp.stiff;
    end
end
K = zeros(nu + nc);
f = zeros(nu + nc, 1);
K(1:neq, 1:nu) = A;
f(1:neq) = -bv;
cond = cell(1, nu);
for k = 1:nu
    r = neq + k;
    supName = sp.unk(k).name;
    us = strfind(supName, '_');
    if ~isempty(us)
        supName = supName(us(1)+1:end);
    end
    if isBend && sp.unk(k).kind == 'C'
        K(r, 1:nu) = THp(k, :);
        K(r, nu+2) = 1;
        f(r) = -thL(k);
        if useShear   % avec le tranchant, v' = θ + T/kGS : l'encastrement impose la rotation de section θ = 0
            cond{k} = sprintf('θ(%s) = 0', supName);
        else
            cond{k} = sprintf('%s''(%s) = 0', sp.dispTxt, supName);
        end
    elseif isBend
        K(r, 1:nu) = Vp(k, :);
        K(r, nu+1) = 1;
        K(r, nu+2) = P(k);
        f(r) = -vL(k);
        cond{k} = sprintf('%s(%s) = 0', sp.dispTxt, supName);
    else
        K(r, 1:nu) = Vp(k, :);
        K(r, nu+1) = 1;
        f(r) = -vL(k);
        cond{k} = sprintf('%s(%s) = 0', sp.dispTxt, supName);
    end
end
% équilibrage des lignes et colonnes (unités hétérogènes)
rs = max(abs(K), [], 2);
rs(rs == 0) = 1;
Ks = K ./ rs;
fs = f ./ rs;
cs = max(abs(Ks), [], 1);
cs(cs == 0) = 1;
Ks = Ks ./ cs;
if forceLsq || rcond(Ks) < 1e-12
    zs = lsqminnorm(Ks, fs);
else
    zs = Ks \ fs;
end
z = zs ./ cs.';
R = z(1:nu);
names = btsCellField(sp.unk, 'name');
constNames = sp.constNames;
if useShear
    constNames{2} = sprintf('C2 = θ(0) (rotation de section ; %s''(0) = C2 + T(0)/(k·G·S))', sp.dispTxt);
end
info = struct('subproblem', sp.name, 'label', sp.label, 'unknowns', {[names, constNames]}, ...
    'K', K, 'f', f, 'solution', z, 'constants', z(nu+1:end), 'conditions', {cond}, ...
    'includeShear', useShear);
end

function [C6, closure, methodUsed] = btsIntegralMethod(br, tol, act, dl, D, useSym)
% Méthode intégrale : intégration des relations différentielles depuis s = L
% (valeurs nulles en L+), sauts aux actions ponctuelles.
% C6 : cellule 1×6 de matrices (N, Ty, Tz, Mt, Mfy, Mfz).
n = numel(br) - 1;
W = D + 3;
C6 = repmat({zeros(n, W)}, 1, 6);
endv = zeros(6, 1);
fl = {'Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz'};
if useSym
    methodUsed = 'symbolique';
    xs = sym('x');
    ss = sym('s');
else
    methodUsed = 'numérique';
end
for k = n:-1:1
    sR = br(k+1);
    sL = br(k);
    endv = endv + btsJumps(act, fl, sR, tol);
    px = 0;
    py = 0;
    pz = 0;
    for j = 1:numel(dl)
        if dl(j).a <= sL + tol && dl(j).b >= sR - tol
            switch dl(j).dir
                case 'x'
                    px = btsPolyAdd(px, dl(j).pg);
                case 'y'
                    py = btsPolyAdd(py, dl(j).pg);
                otherwise
                    pz = btsPolyAdd(pz, dl(j).pg);
            end
        end
    end
    if useSym
        I = int([poly2sym(px, xs); poly2sym(py, xs); poly2sym(pz, xs)], xs, ss, sym(sR));
        NS = sym(endv(1)) + I(1);
        TyS = sym(endv(2)) + I(2);
        TzS = sym(endv(3)) + I(3);
        I2 = int([subs(TyS, ss, xs); subs(TzS, ss, xs)], xs, ss, sym(sR));
        MfzS = sym(endv(6)) + I2(1);
        MfyS = sym(endv(5)) - I2(2);
        cN = btsSym2Poly(NS, ss);
        cTy = btsSym2Poly(TyS, ss);
        cTz = btsSym2Poly(TzS, ss);
        cMfz = btsSym2Poly(MfzS, ss);
        cMfy = btsSym2Poly(MfyS, ss);
    else
        Px = polyint(px);
        cN = -Px;
        cN(end) = cN(end) + endv(1) + polyval(Px, sR);
        Py = polyint(py);
        cTy = -Py;
        cTy(end) = cTy(end) + endv(2) + polyval(Py, sR);
        Pz = polyint(pz);
        cTz = -Pz;
        cTz(end) = cTz(end) + endv(3) + polyval(Pz, sR);
        ITy = polyint(cTy);
        cMfz = -ITy;
        cMfz(end) = cMfz(end) + endv(6) + polyval(ITy, sR);
        ITz = polyint(cTz);
        cMfy = ITz;
        cMfy(end) = cMfy(end) + endv(5) - polyval(ITz, sR);
    end
    cMt = endv(4);
    rows = {cN, cTy, cTz, cMt, cMfy, cMfz};
    for c = 1:6
        C6{c}(k, :) = btsPad(rows{c}, W);
        endv(c) = polyval(rows{c}, sL);
    end
end
closure = endv + btsJumps(act, fl, br(1), tol);
end

function c = btsSym2Poly(e, ss)
% Coefficients (double, ordre polyval) d'un polynôme symbolique en s.
e = expand(e);
if isempty(symvar(e))
    c = double(e);
else
    c = double(sym2poly(subs(e, symvar(e), ss)));
end
end

function j = btsJumps(act, fl, a, tol)
j = zeros(6, 1);
for c = 1:6
    lst = act.(fl{c});
    if ~isempty(lst)
        j(c) = sum(lst(abs(lst(:, 1) - a) <= tol, 2));
    end
end
end

function e = btsExtrema(pp)
% Extrema d'un pp : bornes de chaque tronçon (limites) et racines de la dérivée.
br = pp.breaks;
c = pp.coefs;
nk = numel(c);
csC = cell(1, nk);
cvC = cell(1, nk);
for k = 1:nk
    ck = c{k};
    a = br(k);
    b = br(k+1);
    ss = [a, b];
    if numel(ck) > 2
        r = roots(polyder(ck));
        r = r(abs(imag(r)) <= 1e-9 * max(1, abs(real(r))));
        r = real(r);
        r = r(r > a & r < b);
        ss = [ss, r(:).']; %#ok<AGROW>
    end
    csC{k} = ss;
    cvC{k} = polyval(ck, ss);
end
cs = [csC{:}];
cv = [cvC{:}];
[vmax, i1] = max(cv);
[vmin, i2] = min(cv);
e = struct('max', vmax, 'sMax', cs(i1), 'min', vmin, 'sMin', cs(i2));
end

function sol = btsSolveBeam(model, opts)
o = btsBeamOpts(opts);
[mdl, notes] = btsNormalizeModel(model);
L = mdl.L;
sup = mdl.supports;
ns = numel(sup);
dl = btsPrepDist(mdl.distLoads);
D = 1;
if ~isempty(dl)
    D = max(btsVec(dl, 'deg')) + 2;
end
br = btsMergeBreaks([0, L, btsVec(sup, 'pos'), btsVec(mdl.pointLoads, 'pos'), ...
    btsVec(mdl.pointMoments, 'pos'), btsVec(dl, 'a'), btsVec(dl, 'b')]);
br(1) = 0;
br(end) = L;
tol = btsTol(br);
n = numel(br) - 1;
Gq = btsGaussData(br, D + 1, D);

if ns > 0
    xA = sup(1).pos;
    nameA = sup(1).name;
else
    xA = 0;
    nameA = 'O';
end

% --- 4 sous-problèmes indépendants
sps = btsBuildSubs(mdl, dl, nameA);
for k = 1:4
    sps{k} = btsSolveSub(sps{k}, br, tol, D, Gq, o, L, xA);
end

% --- degré d'hyperstatisme
h = struct('axial', sps{1}.h, 'xy', sps{2}.h, 'xz', sps{3}.h, 'torsion', sps{4}.h, ...
    'total', sps{1}.h + sps{2}.h + sps{3}.h + sps{4}.h, ...
    'plan2D', sps{1}.nunk + sps{2}.nunk - 3);
isostatic = (h.total == 0);

% --- réactions
reactions = btsReactionStruct(sup);
reacMen = reactions;
reacInt = reactions;
anyMen = false;
anyInt = false;
for k = 1:4
    s = sps{k};
    for j = 1:s.nunk
        u = s.unk(j);
        reactions(u.sup).(u.field) = u.sgn * s.R(j) + 0;
        if ~isostatic
            vm = s.R(j);
            vi = s.R(j);
            if ~isempty(s.Rmen)
                vm = s.Rmen(j);
            end
            if ~isempty(s.Rint)
                vi = s.Rint(j);
            end
            reacMen(u.sup).(u.field) = u.sgn * vm + 0;
            reacInt(u.sup).(u.field) = u.sgn * vi + 0;
        end
    end
    anyMen = anyMen || ~isempty(s.men);
    anyInt = anyInt || ~isempty(s.int);
end
hyperMen = any(strcmp(o.hyperMethod, {'both', 'menabrea'}));
hyperInt = any(strcmp(o.hyperMethod, {'both', 'integration'}));
if ~hyperMen
    reacMen = [];
end
if ~hyperInt
    reacInt = [];
end

% --- échelles (nettoyage et comparaison)
scaleF = 0;
scaleC = 0;
for k = 1:4
    scaleF = max(scaleF, sps{k}.scaleEq(1));
    if numel(sps{k}.scaleEq) > 1
        scaleC = max(scaleC, sps{k}.scaleEq(2));
    end
end
scaleC = max(scaleC, sum(abs(sps{4}.fv)));

% --- torseur de cohésion par coupures (superposition des actions à droite)
Cc = {sps{1}.T, sps{2}.T, sps{3}.T, sps{4}.T, -sps{3}.M, sps{2}.M};
maxF = max([btsMatMaxAbs(Cc{1}, br), btsMatMaxAbs(Cc{2}, br), btsMatMaxAbs(Cc{3}, br), scaleF]);
maxM = max([btsMatMaxAbs(Cc{4}, br), btsMatMaxAbs(Cc{5}, br), btsMatMaxAbs(Cc{6}, br), maxF * L, scaleC]);
compScale = [maxF maxF maxF maxM maxM maxM];

% --- méthode intégrale
methodCheck = NaN;
internalIntegral = [];
closure = [];
methodUsed = 'numérique';
doCut = any(strcmp(o.internalMethod, {'both', 'coupures'}));
doIntg = any(strcmp(o.internalMethod, {'both', 'integrale'}));
compNames = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'};
if doIntg
    act = btsActions(mdl, reactions);
    [Ci, closure, methodUsed] = btsIntegralMethod(br, tol, act, dl, D, o.useSymbolic);
    if doCut
        methodCheck = 0;
        for c = 1:6
            dmax = 0;
            for k = 1:n
                t = linspace(br(k), br(k+1), 7);
                dmax = max(dmax, max(abs(polyval(Cc{c}(k, :), t) - polyval(Ci{c}(k, :), t))));
            end
            if compScale(c) > 0
                methodCheck = max(methodCheck, dmax / compScale(c));
            elseif dmax > 0
                methodCheck = max(methodCheck, dmax);
            end
        end
    end
    internalIntegral = struct();
    for c = 1:6
        internalIntegral.(compNames{c}) = btsMatToPP(btsCleanMat(Ci{c}, br, 1e-12 * compScale(c)), br);
    end
    internalIntegral.methodUsed = methodUsed;
    internalIntegral.closure = closure(:).';
end

% --- pp principaux
sol = struct();
sol.model = mdl;
sol.h = h;
sol.isostatic = isostatic;
sol.reactions = reactions;
sol.breaks = br;
if doCut
    for c = 1:6
        sol.(compNames{c}) = btsMatToPP(btsCleanMat(Cc{c}, br, 1e-12 * compScale(c)), br);
    end
else
    for c = 1:6
        sol.(compNames{c}) = internalIntegral.(compNames{c});
    end
end
sol.internalIntegral = internalIntegral;
sol.methodCheck = methodCheck;

% --- équations par tronçon
texNames = {'N', 'T_{y}', 'T_{z}', 'M_{t}', 'M_{fy}', 'M_{fz}'};
tmpl = struct('s1', 0, 's2', 0, 'N', '', 'N_txt', '', 'Ty', '', 'Ty_txt', '', 'Tz', '', 'Tz_txt', '', ...
    'Mt', '', 'Mt_txt', '', 'Mfy', '', 'Mfy_txt', '', 'Mfz', '', 'Mfz_txt', '');
eqs = repmat(tmpl, 1, n);
for k = 1:n
    eqs(k).s1 = br(k);
    eqs(k).s2 = br(k+1);
    for c = 1:6
        ck = sol.(compNames{c}).coefs{k};
        eqs(k).(compNames{c}) = ['$' texNames{c} '(s) = ' btsPolyStr(ck, 's', true) '$'];
        eqs(k).([compNames{c} '_txt']) = [compNames{c} '(s) = ' btsPolyStr(ck, 's', false)];
    end
end
sol.equations = eqs;

% --- extrema
ext = struct();
for c = 1:6
    ext.(compNames{c}) = btsExtrema(sol.(compNames{c}));
end
sol.extrema = ext;

% --- Ménabréa / intégration
menab = [];
integ = [];
hyperCheck = NaN;
for k = 1:4
    s = sps{k};
    if ~isempty(s.men)
        if isempty(menab)
            menab = struct();
        end
        menab.(s.name) = s.men;
    end
    if ~isempty(s.int)
        if isempty(integ)
            integ = struct();
        end
        integ.(s.name) = s.int;
    end
    if ~isnan(s.hyperCheck)
        if isnan(hyperCheck)
            hyperCheck = s.hyperCheck;
        else
            hyperCheck = max(hyperCheck, s.hyperCheck);
        end
    end
end
sol.menabrea = menab;
sol.reactionsMenabrea = reacMen;
sol.reactionsIntegration = reacInt;
if isostatic
    sol.reactionsMenabrea = [];
    sol.reactionsIntegration = [];
end
sol.hyperCheck = hyperCheck;
sol.integration = integ;
sol.methodUsed = methodUsed;
if ~doIntg
    sol.methodUsed = 'coupures';
end

% --- rapport
ctx = struct('mdl', mdl, 'notes', {notes}, 'br', br, 'subs', {sps}, 'h', h, 'xA', xA, ...
    'nameA', nameA, 'isostatic', isostatic, 'reactions', reactions, 'o', o, ...
    'methodCheck', methodCheck, 'closure', closure, 'eqs', eqs, 'extrema', ext, ...
    'methodUsed', methodUsed, 'doCut', doCut, 'doIntg', doIntg, 'anyMen', anyMen, 'anyInt', anyInt, ...
    'dl', dl);
[sol.report, sol.latex] = btsBeamReport(ctx);
end

function r = btsReactionStruct(sup)
r = struct('name', {}, 'pos', {}, 'type', {}, 'Rx', {}, 'Ry', {}, 'Rz', {}, 'Mx', {}, 'My', {}, 'Mz', {});
for i = 1:numel(sup)
    r(i).name = sup(i).name;
    r(i).pos = sup(i).pos;
    r(i).type = sup(i).type;
    r(i).Rx = 0;
    r(i).Ry = 0;
    r(i).Rz = 0;
    r(i).Mx = 0;
    r(i).My = 0;
    r(i).Mz = 0;
end
end

function act = btsActions(mdl, reac)
% Actions ponctuelles (charges + réactions) par composante : [pos valeur].
PL = mdl.pointLoads;
PM = mdl.pointMoments;
pp = btsVec(PL, 'pos').';
pm = btsVec(PM, 'pos').';
rp = btsVec(reac, 'pos').';
act.Fx = [pp, btsVec(PL, 'Fx').'; rp, btsVec(reac, 'Rx').'];
act.Fy = [pp, btsVec(PL, 'Fy').'; rp, btsVec(reac, 'Ry').'];
act.Fz = [pp, btsVec(PL, 'Fz').'; rp, btsVec(reac, 'Rz').'];
act.Mx = [pm, btsVec(PM, 'Mx').'; rp, btsVec(reac, 'Mx').'];
act.My = [pm, btsVec(PM, 'My').'; rp, btsVec(reac, 'My').'];
act.Mz = [pm, btsVec(PM, 'Mz').'; rp, btsVec(reac, 'Mz').'];
end

function s = btsLinEq(coefs, names, cst, isTex, withZero)
% Combinaison linéaire « a·X + b·Y + c » (= 0 si withZero).
if nargin < 5
    withZero = true;
end
s = '';
mx = max(abs([coefs(:); cst]));
if isempty(mx)
    mx = 0;
end
for j = 1:numel(coefs)
    c = coefs(j);
    if c == 0 || abs(c) <= 1e-13 * mx
        continue
    end
    if isTex
        mag = btsTexNum(abs(c));
        if strcmp(mag, '1')
            term = names{j};
        else
            term = [mag '\,' names{j}];
        end
    else
        mag = btsNum(abs(c));
        if strcmp(mag, '1')
            term = names{j};
        else
            term = [mag '·' names{j}];
        end
    end
    s = btsAppendTerm(s, term, c < 0);
end
if cst ~= 0 && abs(cst) > 1e-13 * mx
    if isTex
        mag = btsTexNum(abs(cst));
    else
        mag = btsNum(abs(cst));
    end
    s = btsAppendTerm(s, mag, cst < 0);
end
if isempty(s)
    s = '0';
end
if withZero
    s = [s ' = 0'];
end
end

function s = btsAppendTerm(s, term, neg)
if isempty(s)
    if neg
        s = ['-' term];
    else
        s = term;
    end
elseif neg
    s = [s ' - ' term];
else
    s = [s ' + ' term];
end
end

function t = btsDofText(type)
switch type
    case {'appui_simple', 'pivot_glissant'}
        t = 'v, w';
    case {'rotule', 'pivot'}
        t = 'u, v, w';
    otherwise
        t = 'u, v, w, θx, θy, θz';
end
end

function s = btsJoinNums(v)
c = cell(1, numel(v));
for i = 1:numel(v)
    c{i} = btsNum(v(i));
end
s = strjoin(c, ', ');
end

function [rep, tex] = btsBeamReport(c)
% Rapport détaillé (texte) et formules clés (LaTeX) de solveBeam.
mdl = c.mdl;
sps = c.subs;
L = mdl.L;
texA = btsTexId(c.nameA, 0);
rep = cell(0, 1);
tex = cell(0, 1);
rep{end+1, 1} = '=== Poutre droite : résolution statique (BeamAndTrussSolver.solveBeam) ===';
rep{end+1, 1} = sprintf(['Données (SI) : L = %s m ; E = %s Pa ; G = %s Pa ; S = %s m² ; Iz = %s m⁴ ; ' ...
    'Iy = %s m⁴ ; Ix = %s m⁴ ; ky = %s ; kz = %s'], btsNum(L), btsNum(mdl.E), btsNum(mdl.G), ...
    btsNum(mdl.S), btsNum(mdl.Iz), btsNum(mdl.Iy), btsNum(mdl.Ix), btsNum(mdl.ky), btsNum(mdl.kz));
for k = 1:numel(c.notes)
    rep{end+1, 1} = ['  Remarque : ' c.notes{k}]; %#ok<AGROW>
end
rep{end+1, 1} = ['Convention : torseur de cohésion = actions extérieures à DROITE de la section, ' ...
    'réduit au centre G(s) ; réactions = efforts exercés par les appuis sur la poutre (repère global).'];
tex{end+1, 1} = '$\{T_{coh}\}_{G} = \{T_{ext,\,droite}\}_{G} = -\{T_{ext,\,gauche}\}_{G}$';

% --- données
sup = mdl.supports;
if isempty(sup)
    rep{end+1, 1} = 'Liaisons : aucune.';
else
    rep{end+1, 1} = 'Liaisons :';
    for i = 1:numel(sup)
        rep{end+1, 1} = sprintf('  %s : %s en s = %s m (ddl bloqués : %s)', sup(i).name, ...
            strrep(sup(i).type, '_', ' '), btsNum(sup(i).pos), btsDofText(sup(i).type)); %#ok<AGROW>
    end
end
PL = mdl.pointLoads;
if ~isempty(PL)
    rep{end+1, 1} = 'Forces ponctuelles :';
    for i = 1:numel(PL)
        rep{end+1, 1} = sprintf('  %s en s = %s m : Fx = %s N ; Fy = %s N ; Fz = %s N', PL(i).name, ...
            btsNum(PL(i).pos), btsNum(PL(i).Fx), btsNum(PL(i).Fy), btsNum(PL(i).Fz)); %#ok<AGROW>
    end
end
PM = mdl.pointMoments;
if ~isempty(PM)
    rep{end+1, 1} = 'Couples ponctuels :';
    for i = 1:numel(PM)
        rep{end+1, 1} = sprintf('  %s en s = %s m : Mx = %s N·m ; My = %s N·m ; Mz = %s N·m', PM(i).name, ...
            btsNum(PM(i).pos), btsNum(PM(i).Mx), btsNum(PM(i).My), btsNum(PM(i).Mz)); %#ok<AGROW>
    end
end
dl = c.dl;
if ~isempty(dl)
    rep{end+1, 1} = 'Charges réparties (ξ = s - a, variable locale) :';
    for i = 1:numel(dl)
        d = dl(i);
        if d.I0 ~= 0
            xr = sprintf(' ; résultante %s N appliquée en s = %s m', btsNum(d.I0), btsNum(d.I1 / d.I0));
        else
            xr = sprintf(' ; résultante nulle, moment %s N·m', btsNum(d.I1));
        end
        rep{end+1, 1} = sprintf('  %s : p_%s(ξ) = %s N/m sur [%s ; %s] m, soit p_%s(s) = %s%s', d.name, d.dir, ...
            btsPolyStr(d.coeffs, 'ξ', false), btsNum(d.a), btsNum(d.b), d.dir, ...
            btsPolyStr(d.pg, 's', false), xr); %#ok<AGROW>
        if d.a == 0
            xiTex = '\xi = s';
        else
            xiTex = ['\xi = s - ' btsTexNum(d.a)];
        end
        tex{end+1, 1} = ['$p_{' d.dir '}(\xi) = ' btsPolyStr(d.coeffs, '\xi', true) ',\ \ ' xiTex ...
            ',\ \ \int_{' btsTexNum(d.a) '}^{' btsTexNum(d.b) '} p_{' d.dir '}\,ds = ' btsTexNum(d.I0) '$']; %#ok<AGROW>
    end
end
rep{end+1, 1} = sprintf('Points de rupture (tronçons) : s = [%s] m', btsJoinNums(c.br));

% --- hyperstatisme
rep{end+1, 1} = '--- Degré d''hyperstatisme (4 sous-problèmes indépendants) ---';
for k = 1:4
    s = sps{k};
    if s.nunk > 0
        nm = strjoin(btsCellField(s.unk, 'name'), ', ');
    else
        nm = '-';
    end
    extra = '';
    if s.rank < s.neq
        if s.nunk == 0 && ~s.loaded
            extra = ' (aucune liaison ni charge : sans objet)';
        else
            extra = ' (liaisons insuffisantes mais chargement équilibré : pas de mécanisme effectif)';
        end
    elseif s.h > 0 && ~s.loaded
        extra = ' (non chargé : réactions nulles)';
    end
    rep{end+1, 1} = sprintf('  %s : %d inconnue(s) [%s], %d équation(s) -> h = %d%s', s.label, s.nunk, nm, ...
        s.neq, s.h, extra); %#ok<AGROW>
end
H = c.h;
if c.isostatic
    st = 'isostatique';
else
    st = 'hyperstatique';
end
rep{end+1, 1} = sprintf('  h total = %d + %d + %d + %d = %d ; h plan (x,y) = %d + %d - 3 = %d -> poutre %s', ...
    H.axial, H.xy, H.xz, H.torsion, H.total, sps{1}.nunk, sps{2}.nunk, H.plan2D, st);
tex{end+1, 1} = sprintf('$h = h_{N} + h_{xy} + h_{xz} + h_{t} = %d + %d + %d + %d = %d$', ...
    H.axial, H.xy, H.xz, H.torsion, H.total);
tex{end+1, 1} = sprintf('$h_{plan} = r_{N} + r_{xy} - 3 = %d + %d - 3 = %d$', sps{1}.nunk, sps{2}.nunk, H.plan2D);

% --- PFS
rep{end+1, 1} = sprintf('--- Principe fondamental de la statique : résultantes et moments au point %s (s = %s m) ---', ...
    c.nameA, btsNum(c.xA));
rep{end+1, 1} = sprintf(['  Transport des moments : M_%s(F) = M_P(F) + %sP ∧ F avec %sP = (x_P - x_%s)·x, ' ...
    'soit (x_P - x_%s)·Fy selon z et -(x_P - x_%s)·Fz selon y.'], c.nameA, c.nameA, c.nameA, c.nameA, c.nameA, c.nameA);
tex{end+1, 1} = ['$\overrightarrow{M}_{' texA '}(\vec{F}) = \overrightarrow{M}_{P}(\vec{F}) + \overrightarrow{' ...
    texA 'P} \wedge \vec{F}$'];
for k = 1:4
    s = sps{k};
    if s.nunk == 0 && ~s.loaded
        continue
    end
    rep{end+1, 1} = sprintf('  [%s]', s.label); %#ok<AGROW>
    if ~isempty(s.loadMoments)
        parts = cell(1, numel(s.loadMoments));
        for j = 1:numel(s.loadMoments)
            parts{j} = sprintf('%s = %s N·m', s.loadMoments(j).label, btsNum(s.loadMoments(j).value));
        end
        if strcmp(s.name, 'xy')
            ax = 'z';
        else
            ax = 'y';
        end
        rep{end+1, 1} = sprintf('    Moments des charges en %s (selon %s) : %s', c.nameA, ax, strjoin(parts, ' ; ')); %#ok<AGROW>
    end
    sg = btsVec(s.unk, 'sgn');
    nmT = btsCellField(s.unk, 'name');
    nmX = btsCellField(s.unk, 'tex');
    for r = 1:s.neq
        coefs = s.rowSign(r) * s.A(r, :) .* sg;
        cst = s.rowSign(r) * s.b(r);
        rep{end+1, 1} = sprintf('    %s : %s', s.eqTxt{r}, btsLinEq(coefs, nmT, cst, false)); %#ok<AGROW>
        tex{end+1, 1} = ['$' s.eqTex{r} ' :\ ' btsLinEq(coefs, nmX, cst, true) '$']; %#ok<AGROW>
    end
    if s.rank == s.neq && s.h == 0
        parts = cell(1, s.nunk);
        for j = 1:s.nunk
            val = s.unk(j).sgn * s.R(j);
            parts{j} = sprintf('%s = %s %s', s.unk(j).name, btsNum(val), s.unk(j).unit);
            tex{end+1, 1} = ['$' s.unk(j).tex ' = ' btsTexNum(val) '\ \mathrm{' s.unk(j).texUnit '}$']; %#ok<AGROW>
        end
        rep{end+1, 1} = ['    => ' strjoin(parts, ' ; ')]; %#ok<AGROW>
    elseif s.h > 0 && s.rank == s.neq
        if s.loaded
            rep{end+1, 1} = sprintf(['    => %d équation(s) pour %d inconnue(s) : hyperstatique d''ordre %d, ' ...
                'résolution par Ménabréa / intégration ci-dessous.'], s.neq, s.nunk, s.h); %#ok<AGROW>
        else
            rep{end+1, 1} = sprintf('    => hyperstatique d''ordre %d non chargé : toutes les réactions sont nulles.', s.h); %#ok<AGROW>
        end
    else
        rep{end+1, 1} = '    => liaisons insuffisantes mais chargement compatible (aucun mouvement de mécanisme sollicité).'; %#ok<AGROW>
        if s.degenerate
            rep{end+1, 1} = '    => liaisons à la fois redondantes et insuffisantes : réactions de norme minimale (méthode d''intégration).'; %#ok<AGROW>
        end
    end
end

% --- hyperstatique : Ménabréa et intégration
for k = 1:4
    s = sps{k};
    if ~isempty(s.men)
        men = s.men;
        rep{end+1, 1} = sprintf('--- Théorème de Ménabréa : %s (h = %d) ---', s.label, s.h); %#ok<AGROW>
        rep{end+1, 1} = sprintf(['  Système de base isostatique : réactions conservées [%s] ; inconnues ' ...
            'hyperstatiques X = [%s] (déplacements correspondants nuls).'], strjoin(men.base, ', '), ...
            strjoin(men.unknowns, ', ')); %#ok<AGROW>
        if strcmp(s.kind, 'bend')
            msg = sprintf(['  M(s) = M0(s) + Σ Xi·mi(s) ; %s ; ∂U/∂Xi = 0 -> Σj δij·Xj = -δi0, ' ...
                'δij = ∫ mi·mj/(%s) ds'], s.energyTxt, s.stiffTxt);
            if men.includeShear
                msg = [msg sprintf(' + ∫ ti·tj/(%s) ds', s.shearTxt)]; %#ok<AGROW>
            end
        else
            msg = sprintf(['  N(s) = N0(s) + Σ Xi·ni(s) ; %s ; ∂U/∂Xi = 0 -> Σj δij·Xj = -δi0, ' ...
                'δij = ∫ ni·nj/(%s) ds'], s.energyTxt, s.stiffTxt);
        end
        rep{end+1, 1} = msg; %#ok<AGROW>
        tex{end+1, 1} = '$\frac{\partial U}{\partial X_{i}} = 0 \Rightarrow \sum_{j} \delta_{ij}\,X_{j} = -\delta_{i0}$'; %#ok<AGROW>
        tex{end+1, 1} = s.energyTex; %#ok<AGROW>
        hX = numel(men.X);
        xn = cell(1, hX);
        for i = 1:hX
            xn{i} = sprintf('X_{%d}', i);
        end
        for i = 1:hX
            rep{end+1, 1} = sprintf('  Ligne %d : δ = [%s] ; -δ%d0 = %s', i, btsJoinNums(men.delta(i, :)), i, ...
                btsNum(men.rhs(i))); %#ok<AGROW>
            tex{end+1, 1} = ['$' btsLinEq(men.delta(i, :), xn, 0, true, false) ' = ' btsTexNum(men.rhs(i)) '$']; %#ok<AGROW>
        end
        parts = cell(1, hX);
        for i = 1:hX
            xi = men.sgn(i) * men.X(i);
            parts{i} = sprintf('X%d = %s = %s', i, men.unknowns{i}, btsNum(xi));
            tex{end+1, 1} = ['$X_{' sprintf('%d', i) '} = ' men.unknownsTex{i} ' = ' btsTexNum(xi) '$']; %#ok<AGROW>
        end
        rep{end+1, 1} = ['  Solution : ' strjoin(parts, ' ; ')]; %#ok<AGROW>
    end
    if ~isempty(s.int)
        it = s.int;
        rep{end+1, 1} = sprintf('--- Méthode d''intégration : %s ---', s.label); %#ok<AGROW>
        rep{end+1, 1} = ['  ' s.intTxt]; %#ok<AGROW>
        tex{end+1, 1} = s.intTex; %#ok<AGROW>
        rep{end+1, 1} = sprintf('  Inconnues (%d) : %s', numel(it.unknowns), strjoin(it.unknowns, ', ')); %#ok<AGROW>
        rep{end+1, 1} = sprintf('  Équations : %d d''équilibre + conditions cinématiques %s', s.neq, ...
            strjoin(it.conditions, ', ')); %#ok<AGROW>
        parts = cell(1, numel(it.solution));
        for i = 1:numel(it.solution)
            nmi = it.unknowns{i};
            eqp = strfind(nmi, ' =');
            if ~isempty(eqp)
                nmi = nmi(1:eqp(1)-1);
            end
            sg = 1;
            if i <= numel(s.unk)   % réactions de liaison ; les constantes d'intégration suivent
                sg = s.unk(i).sgn;
            end
            parts{i} = sprintf('%s = %s', nmi, btsNum(sg * it.solution(i)));
        end
        rep{end+1, 1} = ['  Solution : ' strjoin(parts, ' ; ')]; %#ok<AGROW>
    end
    if ~isnan(s.hyperCheck)
        rep{end+1, 1} = sprintf('  Écart relatif maximal Ménabréa / intégration (%s) : %.3g', s.label, s.hyperCheck); %#ok<AGROW>
    end
end

% --- réactions
rep{end+1, 1} = '--- Réactions (efforts exercés par les appuis sur la poutre, repère global) ---';
R = c.reactions;
if isempty(R)
    rep{end+1, 1} = '  aucune liaison.';
end
for i = 1:numel(R)
    rep{end+1, 1} = sprintf(['  %s (%s, s = %s m) : Rx = %s N ; Ry = %s N ; Rz = %s N ; Mx = %s N·m ; ' ...
        'My = %s N·m ; Mz = %s N·m'], R(i).name, strrep(R(i).type, '_', ' '), btsNum(R(i).pos), ...
        btsNum(R(i).Rx), btsNum(R(i).Ry), btsNum(R(i).Rz), btsNum(R(i).Mx), btsNum(R(i).My), btsNum(R(i).Mz)); %#ok<AGROW>
end

% --- torseur de cohésion
compNames = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'};
if c.doCut
    rep{end+1, 1} = '--- Torseur de cohésion : méthode des coupures (somme des actions à droite) ---';
    rep{end+1, 1} = ['  N(s) = Σdroite Fx + ∫_s^L px dx ; Ty(s) = Σdroite Fy + ∫_s^L py dx ; ' ...
        'Tz(s) = Σdroite Fz + ∫_s^L pz dx ; Mt(s) = Σdroite Mx'];
    rep{end+1, 1} = ['  Mfz(s) = Σdroite [(xi - s)·Fyi + Czi] + ∫_s^L (x - s)·py dx ; ' ...
        'Mfy(s) = Σdroite [-(xi - s)·Fzi + Cyi] - ∫_s^L (x - s)·pz dx'];
    tex{end+1, 1} = '$N(s) = \sum_{droite} F_{xi} + \int_{s}^{L} p_x\,dx,\ \ T_y(s) = \sum_{droite} F_{yi} + \int_{s}^{L} p_y\,dx$';
    tex{end+1, 1} = '$M_{fz}(s) = \sum_{droite} \left[ (x_i - s)\,F_{yi} + C_{zi} \right] + \int_{s}^{L} (x - s)\,p_y\,dx$';
    tex{end+1, 1} = '$M_{fy}(s) = \sum_{droite} \left[ -(x_i - s)\,F_{zi} + C_{yi} \right] - \int_{s}^{L} (x - s)\,p_z\,dx$';
else
    rep{end+1, 1} = '--- Torseur de cohésion (méthode intégrale uniquement) ---';
end
for k = 1:numel(c.eqs)
    e = c.eqs(k);
    rep{end+1, 1} = sprintf('  Tronçon %d : s ∈ [%s ; %s] m', k, btsNum(e.s1), btsNum(e.s2)); %#ok<AGROW>
    nz = 0;
    for cc = 1:6
        txt = e.([compNames{cc} '_txt']);
        if ~endsWith(txt, '= 0')
            rep{end+1, 1} = ['    ' txt]; %#ok<AGROW>
            nz = nz + 1;
        end
    end
    if nz == 0
        rep{end+1, 1} = '    toutes les composantes sont nulles'; %#ok<AGROW>
    end
end
if c.doIntg
    rep{end+1, 1} = sprintf(['--- Méthode intégrale (%s) : intégration depuis s = L (valeurs nulles en L+), ' ...
        'sauts aux actions ponctuelles ---'], c.methodUsed);
    rep{end+1, 1} = ['  dN/ds = -px ; dTy/ds = -py (= q) ; dTz/ds = -pz ; dMfz/ds = -Ty ; dMfy/ds = Tz ; ' ...
        'Ty(a-) = Ty(a+) + Fy ; Mfz(a-) = Mfz(a+) + Cz ; Mfy(a-) = Mfy(a+) + Cy'];
    tex{end+1, 1} = '$\frac{dN}{ds} = -p_x,\ \ \frac{dT_y}{ds} = -p_y,\ \ T_y = -\frac{dM_{fz}}{ds},\ \ T_z = \frac{dM_{fy}}{ds}$';
    tex{end+1, 1} = '$T_y(s) = T_y(b^{-}) + \int_{s}^{b} p_y\,dx,\ \ M_{fz}(s) = M_{fz}(b^{-}) + \int_{s}^{b} T_y\,dx$';
    if ~isempty(c.closure)
        rep{end+1, 1} = sprintf(['  Fermeture en s = 0- (équilibre global, doit être nulle) : N = %s ; Ty = %s ; ' ...
            'Tz = %s ; Mt = %s ; Mfy = %s ; Mfz = %s'], btsNum(c.closure(1)), btsNum(c.closure(2)), ...
            btsNum(c.closure(3)), btsNum(c.closure(4)), btsNum(c.closure(5)), btsNum(c.closure(6)));
    end
    if ~isnan(c.methodCheck)
        rep{end+1, 1} = sprintf('  Écart relatif maximal coupures / intégrale : %.3g', c.methodCheck);
    end
end

% --- extrema
rep{end+1, 1} = '--- Extrema des efforts intérieurs ---';
units = {'N', 'N', 'N', 'N·m', 'N·m', 'N·m'};
texUnits = {'N', 'N', 'N', 'N\,m', 'N\,m', 'N\,m'};
texBase = {'N_{', 'T_{y,', 'T_{z,', 'M_{t,', 'M_{fy,', 'M_{fz,'};
for cc = 1:6
    e = c.extrema.(compNames{cc});
    rep{end+1, 1} = sprintf('  %s : max = %s %s en s = %s m ; min = %s %s en s = %s m', compNames{cc}, ...
        btsNum(e.max), units{cc}, btsNum(e.sMax), btsNum(e.min), units{cc}, btsNum(e.sMin)); %#ok<AGROW>
    if e.max ~= 0 || e.min ~= 0
        tex{end+1, 1} = ['$' texBase{cc} 'max} = ' btsTexNum(e.max) '\ \mathrm{' texUnits{cc} '}\ (s = ' ...
            btsTexNum(e.sMax) '\ \mathrm{m}),\ \ ' texBase{cc} 'min} = ' btsTexNum(e.min) '\ \mathrm{' ...
            texUnits{cc} '}\ (s = ' btsTexNum(e.sMin) '\ \mathrm{m})$']; %#ok<AGROW>
    end
end
end

%% =====================================================================
%%                  FONCTIONS LOCALES : TREILLIS
%% =====================================================================

function tsol = btsSolveTruss(truss)
if ~isstruct(truss) || ~isscalar(truss)
    error('MecaStruct:Truss:invalidModel', 'Le treillis doit être une structure scalaire.');
end
for f = {'nodes', 'bars', 'supports'}
    if ~isfield(truss, f{1}) || isempty(truss.(f{1}))
        error('MecaStruct:Truss:invalidModel', 'Champ truss.%s manquant ou vide.', f{1});
    end
end
nodes = double(truss.nodes);
[n, dim] = size(nodes);
if ~(dim == 2 || dim == 3) || any(~isfinite(nodes(:)))
    error('MecaStruct:Truss:invalidModel', 'truss.nodes doit être une matrice n×2 ou n×3 de coordonnées finies (m).');
end
bars = double(truss.bars);
if size(bars, 2) ~= 2 || any(bars(:) ~= round(bars(:))) || any(bars(:) < 1) || any(bars(:) > n) ...
        || any(bars(:, 1) == bars(:, 2))
    error('MecaStruct:Truss:invalidModel', 'truss.bars doit être une matrice m×2 d''indices de nœuds distincts (1..%d).', n);
end
m = size(bars, 1);
notes = cell(0, 1);
E = btsTrussProp(truss, 'E', m, 210e9);
S = btsTrussProp(truss, 'S', m, 1e-4);
if ~isfield(truss, 'E') || isempty(truss.E)
    notes{end+1, 1} = 'E non fourni : 210 GPa par défaut (sans effet sur N si isostatique).';
end
if ~isfield(truss, 'S') || isempty(truss.S)
    notes{end+1, 1} = 'S non fourni : 1e-4 m² par défaut (sans effet sur N si isostatique).';
end
sups = truss.supports;
if ~(islogical(sups) || isnumeric(sups)) || ~isequal(size(sups), [n dim])
    error('MecaStruct:Truss:invalidModel', 'truss.supports doit être une matrice logique %d×%d.', n, dim);
end
sups = logical(sups);
if isfield(truss, 'loads') && ~isempty(truss.loads)
    loads = double(truss.loads);
    if ~isequal(size(loads), [n dim]) || any(~isfinite(loads(:)))
        error('MecaStruct:Truss:invalidModel', 'truss.loads doit être une matrice %d×%d de forces finies (N).', n, dim);
    end
else
    loads = zeros(n, dim);
end
names = btsTrussNames(truss, n);

% --- géométrie
dX = nodes(bars(:, 2), :) - nodes(bars(:, 1), :);
L0 = sqrt(sum(dX.^2, 2));
if any(L0 <= 1e-12 * max(1, max(abs(nodes(:)))))
    error('MecaStruct:Truss:invalidModel', 'Barre de longueur nulle (nœuds confondus).');
end
e = dX ./ L0;

% --- méthode des nœuds : [A]{N, R} = {-F}
r = nnz(sups);
h = m + r - dim * n;
nd = dim * n;
A = zeros(nd, m + r);
for b = 1:m
    i = bars(b, 1);
    j = bars(b, 2);
    A((i-1)*dim + (1:dim), b) = A((i-1)*dim + (1:dim), b) + e(b, :).';
    A((j-1)*dim + (1:dim), b) = A((j-1)*dim + (1:dim), b) - e(b, :).';
end
st = sups.';
blocked = find(st(:));
for k = 1:r
    A(blocked(k), m + k) = 1;
end
Fv = reshape(loads.', [], 1);
rankA = rank(A);
mechanism = rankA < nd;
scaleF = max(norm(Fv, Inf), 0);
if mechanism
    z = lsqminnorm(A, -Fv);
    res = norm(A * z + Fv, Inf);
    if res > 1e-9 * scaleF
        error('MecaStruct:Truss:mechanism', ...
            ['Mécanisme : rang([A]) = %d < %d équations (h = m + r - %d·n = %d) ; le treillis ne ' ...
            'peut pas équilibrer le chargement appliqué.'], rankA, nd, dim, h);
    end
end
isostatic = (h == 0) && ~mechanism;
Njoints = [];
Rj = [];
if isostatic
    z = A \ (-Fv);
    Njoints = z(1:m);
    Rj = z(m+1:end);
end

% --- méthode des rigidités
kb = E .* S ./ L0;
K = zeros(nd);
for b = 1:m
    ke = kb(b) * (e(b, :).' * e(b, :));
    di = (bars(b, 1)-1)*dim + (1:dim);
    dj = (bars(b, 2)-1)*dim + (1:dim);
    K(di, di) = K(di, di) + ke;
    K(dj, dj) = K(dj, dj) + ke;
    K(di, dj) = K(di, dj) - ke;
    K(dj, di) = K(dj, di) - ke;
end
free = true(nd, 1);
free(blocked) = false;
u = zeros(nd, 1);
Kff = K(free, free);
if any(free)
    if mechanism || rcond(Kff) < 1e-14
        u(free) = lsqminnorm(Kff, Fv(free));
    else
        u(free) = Kff \ Fv(free);
    end
end
U = reshape(u, dim, n).';
Nst = kb .* sum(e .* (U(bars(:, 2), :) - U(bars(:, 1), :)), 2);
Rfull = K * u - Fv;
Rfull(free) = 0;
reactions = reshape(Rfull, dim, n).';
if isostatic
    N = Njoints;
    reacJ = zeros(nd, 1);
    reacJ(blocked) = Rj;
    reactions = reshape(reacJ, dim, n).';
    methodUsed = 'méthode des nœuds (vérifiée par la méthode des rigidités)';
else
    N = Nst;
    methodUsed = 'méthode des rigidités';
end
scaleN = max([abs(N); scaleF]);
N(abs(N) <= 1e-13 * scaleN) = 0;
reactions(abs(reactions) <= 1e-13 * max(scaleN, 1e-300)) = 0;
thr = 1e-9 * max([abs(N); 0]);
nature = repmat({'Nul'}, m, 1);
nature(N > thr) = {'Traction'};
nature(N < -thr) = {'Compression'};
sigma = N ./ S;
dL = N .* L0 ./ (E .* S);

ecart = NaN;
if isostatic
    ecart = max(abs(Njoints - Nst)) / max([abs(Njoints); scaleF; 1e-300]);
end

% --- tableau récapitulatif
Barre = (1:m).';
Noeuds = strings(m, 1);
for b = 1:m
    Noeuds(b) = string(names{bars(b, 1)}) + "-" + string(names{bars(b, 2)});
end
tbl = table(Barre, Noeuds, L0, N, string(nature), sigma, dL, ...
    'VariableNames', {'Barre', 'Noeuds', 'L_m', 'N_N', 'Nature', 'Sigma_Pa', 'dL_m'});

tsol = struct();
tsol.dim = dim;
tsol.h = h;
tsol.isostatic = isostatic;
tsol.mechanism = mechanism;
tsol.L0 = L0;
tsol.N = N;
tsol.nature = nature;
tsol.sigma = sigma;
tsol.dL = dL;
tsol.reactions = reactions;
tsol.displacements = U;
tsol.Njoints = Njoints;
tsol.Nstiffness = Nst;
tsol.A = A;
tsol.methodUsed = methodUsed;
tsol.table = tbl;
tsol.rank = rankA;
tsol.ecartMethodes = ecart;
tsol.names = names;
[tsol.report, tsol.latex] = btsTrussReport(tsol, nodes, bars, E, S, sups, loads, names, notes, blocked, r, m, n);
end

function v = btsTrussProp(truss, f, m, def)
if ~isfield(truss, f) || isempty(truss.(f))
    v = def * ones(m, 1);
    return
end
v = double(truss.(f)(:));
if isscalar(v)
    v = v * ones(m, 1);
end
if numel(v) ~= m || any(~isfinite(v)) || any(v <= 0)
    error('MecaStruct:Truss:invalidModel', 'truss.%s doit être un scalaire ou un vecteur %d×1 strictement positif.', f, m);
end
end

function names = btsTrussNames(truss, n)
names = cell(n, 1);
ok = false;
if isfield(truss, 'names') && ~isempty(truss.names)
    nm = truss.names;
    if isstring(nm)
        nm = cellstr(nm);
    end
    if iscell(nm) && numel(nm) == n
        ok = true;
        for i = 1:n
            if ~(ischar(nm{i}) || isstring(nm{i})) || strlength(string(nm{i})) == 0
                ok = false;
                break
            end
            names{i} = char(nm{i});
        end
    end
end
if ~ok
    for i = 1:n
        if n <= 26
            names{i} = char('A' + i - 1);
        else
            names{i} = sprintf('N%d', i);
        end
    end
end
end

function [rep, tex] = btsTrussReport(t, nodes, bars, E, S, sups, loads, names, notes, blocked, r, m, n)
dim = t.dim;
ax = 'xyz';
rep = cell(0, 1);
tex = cell(0, 1);
rep{end+1, 1} = sprintf('=== Treillis articulé %dD : %d nœuds, %d barres (BeamAndTrussSolver.solveTruss) ===', dim, n, m);
for k = 1:numel(notes)
    rep{end+1, 1} = ['  Remarque : ' notes{k}]; %#ok<AGROW>
end
rep{end+1, 1} = 'Nœuds (m), ddl bloqués et charges (N) :';
for i = 1:n
    bl = ax(sups(i, :));
    if isempty(bl)
        bl = '-';
    end
    rep{end+1, 1} = sprintf('  %s : (%s) ; bloqué : %s ; F = (%s)', names{i}, btsJoinNums(nodes(i, :)), bl, ...
        btsJoinNums(loads(i, :))); %#ok<AGROW>
end
rep{end+1, 1} = 'Barres :';
for b = 1:m
    rep{end+1, 1} = sprintf('  Barre %d : %s-%s, L = %s m, E = %s Pa, S = %s m²', b, names{bars(b, 1)}, ...
        names{bars(b, 2)}, btsNum(t.L0(b)), btsNum(E(b)), btsNum(S(b))); %#ok<AGROW>
end
rep{end+1, 1} = sprintf('Degré d''hyperstatisme : h = m + r - %d·n = %d + %d - %d·%d = %d ; rang([A]) = %d / %d', ...
    dim, m, r, dim, n, t.h, t.rank, dim * n);
tex{end+1, 1} = sprintf('$h = m + r - %d\\,n = %d + %d - %d \\cdot %d = %d$', dim, m, r, dim, n, t.h);
if t.mechanism
    rep{end+1, 1} = '  ATTENTION : mécanisme (rang insuffisant) ; chargement compatible, solution de norme minimale.';
elseif t.isostatic
    rep{end+1, 1} = '  Treillis isostatique (strictement indéformable).';
else
    rep{end+1, 1} = sprintf('  Treillis hyperstatique d''ordre %d : méthode des rigidités nécessaire.', t.h);
end

% --- méthode des nœuds
rep{end+1, 1} = '--- Méthode des nœuds : équilibre de chaque nœud, Σ F = 0, sous forme [A]{N, R} = {-F} ---';
rep{end+1, 1} = '  Convention : N > 0 traction ; une barre tendue tire le nœud vers l''autre extrémité (vecteur unitaire e_ij).';
tex{end+1, 1} = '$\sum_{barres} N_{b}\,\vec{e}_{b} + \vec{R}_{i} + \vec{F}_{i} = \vec{0}\ \Rightarrow\ [A]\,\{N;R\} = \{-F\}$';
colNames = cell(1, m + r);
for b = 1:m
    colNames{b} = sprintf('N%d', b);
end
for k = 1:r
    nodeIdx = ceil(blocked(k) / dim);
    d = blocked(k) - (nodeIdx-1)*dim;
    colNames{m + k} = sprintf('R%s%s', ax(d), names{nodeIdx});
end
if n <= 40
    for i = 1:n
        for d = 1:dim
            row = (i-1)*dim + d;
            rep{end+1, 1} = sprintf('  Nœud %s, direction %s : %s', names{i}, ax(d), ...
                btsLinEq(t.A(row, :), colNames, loads(i, d), false)); %#ok<AGROW>
        end
    end
end
if t.isostatic
    rep{end+1, 1} = '  Système carré inversible : résolution directe (méthode des nœuds).';
    rep{end+1, 1} = sprintf('  Écart relatif méthode des nœuds / méthode des rigidités : %.3g', t.ecartMethodes);
else
    rep{end+1, 1} = '  Système non carré (ou singulier) : la méthode des nœuds seule ne suffit pas.';
end

% --- méthode des rigidités
rep{end+1, 1} = '--- Méthode des rigidités : [K]{u} = {F}, k_b = E·S/L, N_b = k_b·e_b·(u_j - u_i) ---';
tex{end+1, 1} = '$[K_{b}] = \frac{E_b\,S_b}{L_b} \left[ \begin{array}{cc} \vec{e}\,\vec{e}^{T} & -\vec{e}\,\vec{e}^{T} \\ -\vec{e}\,\vec{e}^{T} & \vec{e}\,\vec{e}^{T} \end{array} \right]$';
tex{end+1, 1} = '$N_{b} = \frac{E_b\,S_b}{L_b}\,\vec{e}_{b} \cdot \left( \vec{u}_{j} - \vec{u}_{i} \right)$';
for i = 1:n
    rep{end+1, 1} = sprintf('  Déplacement de %s : (%s) m', names{i}, btsJoinNums(t.displacements(i, :))); %#ok<AGROW>
end

% --- résultats
rep{end+1, 1} = sprintf('--- Efforts normaux (%s) ---', t.methodUsed);
for b = 1:m
    rep{end+1, 1} = sprintf('  Barre %d (%s-%s) : N = %s N (%s) ; σ = N/S = %s Pa ; ΔL = N·L/(E·S) = %s m', b, ...
        names{bars(b, 1)}, names{bars(b, 2)}, btsNum(t.N(b)), t.nature{b}, btsNum(t.sigma(b)), btsNum(t.dL(b))); %#ok<AGROW>
    if b <= 40
        tex{end+1, 1} = ['$N_{' sprintf('%d', b) '} = ' btsTexNum(t.N(b)) '\ \mathrm{N}\ (\mathrm{' t.nature{b} ...
            '}),\ \ \sigma_{' sprintf('%d', b) '} = \frac{N}{S} = ' btsTexNum(t.sigma(b)) '\ \mathrm{Pa},\ \ \Delta L_{' ...
            sprintf('%d', b) '} = \frac{N\,L}{E\,S} = ' btsTexNum(t.dL(b)) '\ \mathrm{m}$']; %#ok<AGROW>
    end
end
rep{end+1, 1} = '--- Réactions d''appui (N) ---';
for i = 1:n
    if any(sups(i, :))
        rep{end+1, 1} = sprintf('  %s : R = (%s)', names{i}, btsJoinNums(t.reactions(i, :))); %#ok<AGROW>
    end
end
end
