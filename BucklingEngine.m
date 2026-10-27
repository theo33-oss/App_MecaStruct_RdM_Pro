classdef BucklingEngine
    %BUCKLINGENGINE Flambage des poutres droites comprimées : Euler, Rankine, compression simple.
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   Moteur de calcul statique (SI strict : N, m, Pa, m², m⁴), sans tracé ni dépendance
    %   interne. Démarche du cours :
    %     I_min = min(Iz, Iy) ; r_min = sqrt(I_min/S) ; L' = coef·L (encastré-libre 2L,
    %     articulé-articulé L, encastré-articulé L/sqrt(2), encastré-encastré L/2) ;
    %     λ = L'/r_min ; λlim = π·sqrt(E/Re) ;
    %     λ < 20          : compression simple  P_C = Re·S
    %     20 ≤ λ < λlim   : Rankine             P_R = Re·S/(1 + (λ/λlim)²)  (1/P_R = 1/P_E + 1/P_C)
    %     λ ≥ λlim        : Euler               P_E = π²·E·I_min/L'²        (σ_E = π²E/λ²)
    %
    %   Méthodes publiques :
    %     r  = BucklingEngine.analyze(p)                          analyse complète
    %     c  = BucklingEngine.stabilityCurve(E, Re, lambdaVec, lambdaCompression)
    %     T  = BucklingEngine.listConditions()                    conditions aux limites reconnues
    %     k  = BucklingEngine.effectiveLengthCoefficient(cond)    coefficient L'/L du cours
    %     tf = BucklingEngine.hasSymbolic()                       Symbolic Math Toolbox disponible
    %
    %   Voir aussi SolicitationsEngine.buckling, PlotEngine.bucklingCurve.

    methods (Static)

        function r = analyze(p)
            %ANALYZE Analyse au flambage d'une poutre droite comprimée (arbre de décision du cours).
            %   r = BucklingEngine.analyze(p)
            %
            %   Entrées (structure p, unités SI) :
            %     p.E          module d'Young (Pa)
            %     p.Re         limite élastique σe (Pa)
            %     p.S          aire de la section droite (m²)
            %     p.Iz, p.Iy   moments quadratiques principaux en G (m⁴)
            %     p.L          longueur de la poutre (m)
            %     p.condition  'encastre-libre' | 'articule-articule' | 'encastre-articule' |
            %                  'encastre-encastre' (accents, majuscules, '_' et espaces tolérés ;
            %                  l'encastrement est en s = 0, l'articulation ou l'extrémité libre en s = L)
            %     p.s          coefficient de sécurité (défaut 1)
            %     p.P          effort de compression appliqué (N, optionnel ; vide ou NaN = absent ;
            %                  une valeur négative est lue comme un effort normal N < 0 : on retient |P|)
            %     p.lambdaCompression  élancement limite de la compression simple (défaut 20)
            %     p.useSymbolic        résolution symbolique de l'équation différentielle
            %                          (défaut : BucklingEngine.hasSymbolic())
            %
            %   Sorties (structure r) :
            %     Imin, Imax (m⁴), axis ('y' ou 'z' : axe de flexion de plus faible inertie),
            %     planeText, rmin (m), coefLp, Lp (m), lambda, lambdaLim, lambdaCompression,
            %     regime ('compression' | 'rankine' | 'euler'), PC, PE, PR (N), sigmaE (Pa),
            %     Pcrit, Padm (N), sigmaCrit, sigmaAdm (Pa), P (N, NaN si absent),
            %     ok (logical, [] si P absent), sigmaApplied (Pa, NaN si P absent),
            %     safetyObtained (= Pcrit/P), utilization (= P/Padm),
            %     modeShape (handle @(s), max = 1), modeDerivatives (struct d1..d4 de handles),
            %     modeK (k du mode, rad/m), modeSMax (abscisse du maximum), modeText,
            %     modeCheck (vérification numérique des conditions aux limites et de l'équation),
            %     charEquation (équation caractéristique, racine exacte k·L, coefficient L' exact),
            %     derivation (cell LaTeX de la résolution de v'' + k² v = 0), methodUsed
            %     ('symbolique' | 'numérique'), condition, conditionText, s, report, latex.

            if ~isstruct(p) || ~isscalar(p)
                error('MecaStruct:BucklingEngine:invalidInput', ...
                    'Les données du flambage doivent être une structure scalaire p.');
            end
            required = {'E', 'Re', 'S', 'Iz', 'Iy', 'L', 'condition'};
            for i = 1:numel(required)
                if ~isfield(p, required{i})
                    error('MecaStruct:BucklingEngine:missingField', ...
                        'Champ obligatoire manquant pour le flambage : p.%s.', required{i});
                end
            end
            E = BucklingEngine.checkPositive(p.E, 'E (module d''Young)');
            Re = BucklingEngine.checkPositive(p.Re, 'Re (limite élastique)');
            S = BucklingEngine.checkPositive(p.S, 'S (aire de la section)');
            Iz = BucklingEngine.checkPositive(p.Iz, 'Iz (moment quadratique)');
            Iy = BucklingEngine.checkPositive(p.Iy, 'Iy (moment quadratique)');
            L = BucklingEngine.checkPositive(p.L, 'L (longueur)');
            cond = BucklingEngine.normalizeCondition(p.condition);
            sf = 1;
            if isfield(p, 's') && ~isempty(p.s)
                sf = BucklingEngine.checkPositive(p.s, 's (coefficient de sécurité)');
            end
            lc = 20;
            if isfield(p, 'lambdaCompression') && ~isempty(p.lambdaCompression)
                lc = BucklingEngine.checkNonNegative(p.lambdaCompression, ...
                    'lambdaCompression (élancement de fin de compression simple)');
            end
            hasP = false;
            Pval = NaN;
            pNegative = false;
            if isfield(p, 'P') && ~isempty(p.P)
                if ~isnumeric(p.P) || ~isscalar(p.P) || ~isreal(p.P) || isinf(p.P)
                    error('MecaStruct:BucklingEngine:invalidInput', ...
                        'L''effort de compression P doit être un scalaire réel fini (N).');
                end
                if ~isnan(p.P)
                    hasP = true;
                    pNegative = p.P < 0;
                    Pval = abs(double(p.P));
                end
            end
            useSym = BucklingEngine.hasSymbolic();
            if isfield(p, 'useSymbolic') && ~isempty(p.useSymbolic)
                useSym = logical(p.useSymbolic(1)) && BucklingEngine.hasSymbolic();
            end

            info = BucklingEngine.conditionInfo(cond);

            % ---- 1) Plan de flambage : inertie la plus faible ----
            tolI = 1e-12*max(Iz, Iy);
            if Iy < Iz - tolI
                Imin = Iy; Imax = Iz; ax = 'y';
                planeText = sprintf(['Flambage dans le plan (x, z) : flexion autour de l''axe (G, y), ' ...
                    'déplacement w selon z (Imin = Iy = %.5g m⁴ < Iz = %.5g m⁴).'], Iy, Iz);
            elseif Iz < Iy - tolI
                Imin = Iz; Imax = Iy; ax = 'z';
                planeText = sprintf(['Flambage dans le plan (x, y) : flexion autour de l''axe (G, z), ' ...
                    'déplacement v selon y (Imin = Iz = %.5g m⁴ < Iy = %.5g m⁴).'], Iz, Iy);
            else
                Imin = min(Iz, Iy); Imax = max(Iz, Iy); ax = 'z';
                planeText = sprintf(['Iz = Iy = %.5g m⁴ : toutes les directions transversales sont ' ...
                    'équivalentes ; plan (x, y) retenu par convention (flexion autour de (G, z)).'], Imin);
            end

            % ---- 2) à 4) Rayon de giration, longueur de flambage, élancements ----
            rmin = sqrt(Imin/S);
            coefLp = info.coef;
            Lp = coefLp*L;
            lambda = Lp/rmin;
            lambdaLim = pi*sqrt(E/Re);

            % ---- Les trois modèles (calculés quel que soit le régime) ----
            PC = Re*S;
            PE = pi^2*E*Imin/Lp^2;
            PR = Re*S/(1 + (lambda/lambdaLim)^2);
            sigmaE = pi^2*E/lambda^2;

            % ---- 5) Arbre de décision ----
            if lambda >= lambdaLim
                regime = 'euler';
                Pcrit = PE;
            elseif lambda < lc
                regime = 'compression';
                Pcrit = PC;
            else
                regime = 'rankine';
                Pcrit = PR;
            end
            Padm = Pcrit/sf;
            sigmaCrit = Pcrit/S;
            sigmaAdm = Padm/S;

            % ---- Vérification si P fourni ----
            if hasP
                ok = Pval <= Padm;
                sigmaApplied = Pval/S;
                if Pval > 0
                    safetyObtained = Pcrit/Pval;
                else
                    safetyObtained = Inf;
                end
                utilization = Pval/Padm;
            else
                ok = [];
                sigmaApplied = NaN;
                safetyObtained = NaN;
                utilization = NaN;
            end

            % ---- Mode propre et vérification numérique ----
            md = BucklingEngine.modeFunctions(cond, L);
            modeCheck = BucklingEngine.checkMode(md, cond, L);

            % ---- Équation caractéristique (symbolique si possible, sinon numérique) ----
            ce = BucklingEngine.characteristicEquation(cond, useSym);
            ce.kLCourse = pi/coefLp;
            ce.coefLpExact = pi/ce.kL;
            ce.PEexact = ce.kL^2*E*Imin/L^2;
            methodUsed = ce.method;

            % ---- Dérivation LaTeX ----
            derivation = BucklingEngine.buildDerivation(cond, E, Imin, L, Lp, PE, ce);

            % ---- Assemblage ----
            r = struct();
            r.condition = cond;
            r.conditionText = info.label;
            r.E = E; r.Re = Re; r.S = S; r.Iz = Iz; r.Iy = Iy; r.L = L; r.s = sf;
            r.Imin = Imin;
            r.Imax = Imax;
            r.axis = ax;
            r.planeText = planeText;
            r.rmin = rmin;
            r.coefLp = coefLp;
            r.Lp = Lp;
            r.lambda = lambda;
            r.lambdaLim = lambdaLim;
            r.lambdaCompression = lc;
            r.regime = regime;
            r.PC = PC;
            r.PE = PE;
            r.PR = PR;
            r.sigmaE = sigmaE;
            r.Pcrit = Pcrit;
            r.Padm = Padm;
            r.sigmaCrit = sigmaCrit;
            r.sigmaAdm = sigmaAdm;
            r.P = Pval;
            r.ok = ok;
            r.sigmaApplied = sigmaApplied;
            r.safetyObtained = safetyObtained;
            r.utilization = utilization;
            r.modeShape = md.v;
            r.modeDerivatives = struct('d1', md.d1, 'd2', md.d2, 'd3', md.d3, 'd4', md.d4);
            r.modeK = md.k;
            r.modeSMax = md.sMax;
            r.modeText = md.text;
            r.modeCheck = modeCheck;
            r.charEquation = ce;
            r.derivation = derivation;
            r.methodUsed = methodUsed;
            r.report = BucklingEngine.buildReport(r, info, hasP, pNegative);
            r.latex = BucklingEngine.buildLatex(r, info, hasP);
        end

        function c = stabilityCurve(E, Re, lambdaVec, lambdaCompression)
            %STABILITYCURVE Courbes de stabilité σcr(λ) : palier, Euler, Rankine, dimensionnement.
            %   c = BucklingEngine.stabilityCurve(E, Re)
            %   c = BucklingEngine.stabilityCurve(E, Re, lambdaVec)
            %   c = BucklingEngine.stabilityCurve(E, Re, lambdaVec, lambdaCompression)
            %
            %   Entrées : E (Pa), Re (Pa), lambdaVec (vecteur d'élancements ≥ 0, défaut 0:0.5:300),
            %             lambdaCompression (défaut 20).
            %   Sorties (structure c, vecteurs ligne) :
            %     lambda        élancements
            %     sigmaEuler    π²E/λ² (Pa) ; NaN en λ = 0 (hyperbole non bornée)
            %     sigmaRankine  Re/(1 + (λ/λlim)²) (Pa)
            %     sigmaPalier   Re (Pa)
            %     sigmaDesign   courbe de dimensionnement (arbre de décision du cours) (Pa)
            %     zone          1 compression, 2 Rankine, 3 Euler
            %     lambdaLim     π·sqrt(E/Re) ; lambdaCompression ; E ; Re ; report ; latex

            if nargin < 2
                error('MecaStruct:BucklingEngine:invalidInput', ...
                    'stabilityCurve attend au moins E et Re.');
            end
            E = BucklingEngine.checkPositive(E, 'E (module d''Young)');
            Re = BucklingEngine.checkPositive(Re, 'Re (limite élastique)');
            if nargin < 3 || isempty(lambdaVec)
                lambdaVec = 0:0.5:300;
            end
            if nargin < 4 || isempty(lambdaCompression)
                lambdaCompression = 20;
            end
            lc = BucklingEngine.checkNonNegative(lambdaCompression, ...
                'lambdaCompression (élancement de fin de compression simple)');
            if ~isnumeric(lambdaVec) || ~isreal(lambdaVec) || ~isvector(lambdaVec) ...
                    || any(~isfinite(lambdaVec)) || any(lambdaVec < 0)
                error('MecaStruct:BucklingEngine:invalidInput', ...
                    'lambdaVec doit être un vecteur réel d''élancements finis et positifs ou nuls.');
            end
            lam = double(lambdaVec(:)).';
            lambdaLim = pi*sqrt(E/Re);

            sigmaEuler = pi^2*E./lam.^2;
            sigmaEuler(lam == 0) = NaN;
            sigmaRankine = Re./(1 + (lam/lambdaLim).^2);
            sigmaPalier = Re*ones(size(lam));

            isEuler = lam >= lambdaLim;
            isComp = ~isEuler & lam < lc;
            isRank = ~isEuler & ~isComp;
            zone = zeros(size(lam));
            zone(isComp) = 1;
            zone(isRank) = 2;
            zone(isEuler) = 3;
            sigmaDesign = sigmaPalier;
            sigmaDesign(isRank) = sigmaRankine(isRank);
            sigmaDesign(isEuler) = sigmaEuler(isEuler);

            c = struct();
            c.lambda = lam;
            c.sigmaEuler = sigmaEuler;
            c.sigmaRankine = sigmaRankine;
            c.sigmaPalier = sigmaPalier;
            c.sigmaDesign = sigmaDesign;
            c.zone = zone;
            c.lambdaLim = lambdaLim;
            c.lambdaCompression = lc;
            c.E = E;
            c.Re = Re;

            rep = {
                '=== Courbe de stabilité σcr(λ) ==='
                sprintf('E = %.5g Pa (%.4g GPa), Re = %.5g Pa (%.4g MPa)', E, E/1e9, Re, Re/1e6)
                sprintf('Élancement limite : λlim = π·√(E/Re) = %.5g (σE(λlim) = Re)', lambdaLim)
                sprintf('Domaine tracé : λ ∈ [%.4g ; %.4g] (%d points)', min(lam), max(lam), numel(lam))
                sprintf('Palier de compression simple : σ = Re = %.4g MPa pour λ < %.4g', Re/1e6, lc)
                sprintf('Rankine : σR = Re/(1 + (λ/λlim)²) pour %.4g ≤ λ < %.4g', lc, lambdaLim)
                sprintf('Euler : σE = π²E/λ² pour λ ≥ %.4g (non défini en λ = 0 : valeur NaN)', lambdaLim)
                };
            if lambdaLim > lc
                rep{end+1, 1} = sprintf(['Remarque : la courbe de dimensionnement du cours est discontinue : ' ...
                    'en λ = %.4g, Re → σR = %.4g MPa ; en λ = λlim, σR = Re/2 = %.4g MPa → σE = Re = %.4g MPa.'], ...
                    lc, Re/(1 + (lc/lambdaLim)^2)/1e6, Re/2e6, Re/1e6);
            else
                rep{end+1, 1} = sprintf(['Remarque : λlim = %.4g ≤ %.4g : zone de Rankine vide ; ' ...
                    'Euler est retenu dès λ ≥ λlim (choix sécuritaire).'], lambdaLim, lc);
            end
            c.report = rep;
            T = @BucklingEngine.texNum;
            c.latex = {
                ['$\lambda_{lim} = \pi\sqrt{\frac{E}{R_e}} = \pi\sqrt{\frac{' T(E) '}{' T(Re) '}} = ' T(lambdaLim) '$']
                '$\sigma_E = \frac{\pi^2\,E}{\lambda^2}\ \ (\lambda \ge \lambda_{lim})$'
                ['$\sigma_R = \frac{R_e}{1+\left(\frac{\lambda}{\lambda_{lim}}\right)^2}\ \ (' ...
                T(lc) ' \le \lambda < \lambda_{lim})$']
                ['$\sigma = R_e = ' T(Re) '\ \mathrm{Pa}\ \ (\lambda < ' T(lc) ')$']
                };
        end

        function T = listConditions()
            %LISTCONDITIONS Conditions aux limites reconnues et coefficients de longueur de flambage.
            %   T = BucklingEngine.listConditions() renvoie une table : Condition (identifiant à
            %   passer dans p.condition), Libelle (texte affichable), Coefficient (L'/L du cours),
            %   CoefficientTexte.
            ids = {'encastre-libre'; 'articule-articule'; 'encastre-articule'; 'encastre-encastre'};
            n = numel(ids);
            lab = cell(n, 1); coef = zeros(n, 1); ctxt = cell(n, 1);
            for i = 1:n
                info = BucklingEngine.conditionInfo(ids{i});
                lab{i} = info.label;
                coef(i) = info.coef;
                ctxt{i} = info.coefText;
            end
            T = table(string(ids), string(lab), coef, string(ctxt), ...
                'VariableNames', {'Condition', 'Libelle', 'Coefficient', 'CoefficientTexte'});
        end

        function coef = effectiveLengthCoefficient(condition)
            %EFFECTIVELENGTHCOEFFICIENT Coefficient L'/L de la longueur de flambage (valeurs du cours).
            %   coef = BucklingEngine.effectiveLengthCoefficient(condition)
            %   encastré-libre 2 ; articulé-articulé 1 ; encastré-articulé 1/sqrt(2) ;
            %   encastré-encastré 1/2.
            info = BucklingEngine.conditionInfo(BucklingEngine.normalizeCondition(condition));
            coef = info.coef;
        end

        function tf = hasSymbolic()
            %HASSYMBOLIC Vrai si la Symbolic Math Toolbox est installée et sous licence.
            %   tf = BucklingEngine.hasSymbolic()
            persistent cached
            if isempty(cached)
                cached = license('test', 'Symbolic_Toolbox') && ~isempty(ver('symbolic'));
            end
            tf = cached;
        end
    end

    methods (Static, Access = private)

        % ================================================================
        %  Validation des entrées
        % ================================================================

        function x = checkPositive(x, name)
            %CHECKPOSITIVE Scalaire réel fini strictement positif.
            if ~isnumeric(x) || ~isscalar(x) || ~isreal(x) || ~isfinite(x) || x <= 0
                error('MecaStruct:BucklingEngine:invalidInput', ...
                    'La grandeur %s doit être un scalaire réel fini strictement positif.', name);
            end
            x = double(x);
        end

        function x = checkNonNegative(x, name)
            %CHECKNONNEGATIVE Scalaire réel fini positif ou nul.
            if ~isnumeric(x) || ~isscalar(x) || ~isreal(x) || ~isfinite(x) || x < 0
                error('MecaStruct:BucklingEngine:invalidInput', ...
                    'La grandeur %s doit être un scalaire réel fini positif ou nul.', name);
            end
            x = double(x);
        end

        function cond = normalizeCondition(c)
            %NORMALIZECONDITION Identifiant canonique de la condition aux limites.
            if isstring(c) && isscalar(c)
                c = char(c);
            end
            if ~ischar(c) || isempty(c)
                error('MecaStruct:BucklingEngine:condition', ...
                    'La condition aux limites doit être un texte (ex. ''articule-articule'').');
            end
            t = lower(strtrim(c));
            t = regexprep(t, '[éèêë]', 'e');
            t = regexprep(t, '[\s_–—/]+', '-');
            t = regexprep(t, '-+', '-');
            switch t
                case {'encastre-libre', 'libre-encastre', 'console'}
                    cond = 'encastre-libre';
                case {'articule-articule', 'rotule-rotule', 'bi-articule', 'biarticule'}
                    cond = 'articule-articule';
                case {'encastre-articule', 'articule-encastre', 'encastre-rotule', 'rotule-encastre'}
                    cond = 'encastre-articule';
                case {'encastre-encastre', 'bi-encastre', 'biencastre'}
                    cond = 'encastre-encastre';
                otherwise
                    error('MecaStruct:BucklingEngine:condition', ...
                        ['Condition aux limites inconnue : ''%s''. Valeurs admises : ''encastre-libre'', ' ...
                        '''articule-articule'', ''encastre-articule'', ''encastre-encastre''.'], c);
            end
        end

        function info = conditionInfo(cond)
            %CONDITIONINFO Libellé, coefficient de longueur de flambage et racine exacte de référence.
            switch cond
                case 'encastre-libre'
                    info.label = 'encastré-libre';
                    info.coef = 2;
                    info.coefText = '2';
                    info.coefTex = '2';
                    info.kLRef = pi/2;
                case 'articule-articule'
                    info.label = 'articulé-articulé';
                    info.coef = 1;
                    info.coefText = '1';
                    info.coefTex = '1';
                    info.kLRef = pi;
                case 'encastre-articule'
                    info.label = 'encastré-articulé';
                    info.coef = 1/sqrt(2);
                    info.coefText = '1/√2';
                    info.coefTex = '\frac{1}{\sqrt{2}}';
                    info.kLRef = BucklingEngine.kLClampedPinned();
                case 'encastre-encastre'
                    info.label = 'encastré-encastré';
                    info.coef = 0.5;
                    info.coefText = '1/2';
                    info.coefTex = '\frac{1}{2}';
                    info.kLRef = 2*pi;
                otherwise
                    error('MecaStruct:BucklingEngine:condition', 'Condition aux limites inconnue : %s.', cond);
            end
            info.id = cond;
        end

        function x = kLClampedPinned()
            %KLCLAMPEDPINNED Première racine non nulle de tan(x) = x (encastré-articulé), 4,4934...
            persistent val
            if isempty(val)
                val = fzero(@(t) sin(t) - t.*cos(t), [4, 4.7]);
            end
            x = val;
        end

        % ================================================================
        %  Modes propres
        % ================================================================

        function m = modeFunctions(cond, L)
            %MODEFUNCTIONS Mode propre normalisé (max = 1) et ses quatre dérivées analytiques.
            switch cond
                case 'articule-articule'
                    k = pi/L;
                    m.v = @(s) sin(k*s);
                    m.d1 = @(s) k*cos(k*s);
                    m.d2 = @(s) -k^2*sin(k*s);
                    m.d3 = @(s) -k^3*cos(k*s);
                    m.d4 = @(s) k^4*sin(k*s);
                    m.sMax = L/2;
                    m.text = 'v(s) = sin(π s/L) (maximum en s = L/2)';
                case 'encastre-libre'
                    k = pi/(2*L);
                    m.v = @(s) 1 - cos(k*s);
                    m.d1 = @(s) k*sin(k*s);
                    m.d2 = @(s) k^2*cos(k*s);
                    m.d3 = @(s) -k^3*sin(k*s);
                    m.d4 = @(s) -k^4*cos(k*s);
                    m.sMax = L;
                    m.text = ['v(s) = 1 − cos(π s/(2L)) (encastrement en s = 0, extrémité libre en s = L, ' ...
                        'maximum en s = L)'];
                case 'encastre-encastre'
                    k = 2*pi/L;
                    m.v = @(s) (1 - cos(k*s))/2;
                    m.d1 = @(s) k*sin(k*s)/2;
                    m.d2 = @(s) k^2*cos(k*s)/2;
                    m.d3 = @(s) -k^3*sin(k*s)/2;
                    m.d4 = @(s) -k^4*cos(k*s)/2;
                    m.sMax = L/2;
                    m.text = 'v(s) = (1 − cos(2π s/L))/2 (maximum en s = L/2)';
                case 'encastre-articule'
                    kL = BucklingEngine.kLClampedPinned();
                    k = kL/L;
                    % Maximum : v'(s) = 0 ⇔ tan(ks/2) = kL ⇒ ks* = 2·atan(kL)
                    uMax = 2*atan(kL);
                    fmax = sin(uMax) - uMax + kL*(1 - cos(uMax));
                    m.v = @(s) (sin(k*s) - k*s + kL*(1 - cos(k*s)))/fmax;
                    m.d1 = @(s) (k*cos(k*s) - k + kL*k*sin(k*s))/fmax;
                    m.d2 = @(s) (-k^2*sin(k*s) + kL*k^2*cos(k*s))/fmax;
                    m.d3 = @(s) (-k^3*cos(k*s) - kL*k^3*sin(k*s))/fmax;
                    m.d4 = @(s) (k^4*sin(k*s) - kL*k^4*cos(k*s))/fmax;
                    m.sMax = uMax/k;
                    m.text = sprintf(['v(s) = [sin(ks) − ks + kL(1 − cos ks)]/%.6g avec kL = %.6g ' ...
                        '(encastrement en s = 0, articulation en s = L, maximum en s = %.4f L)'], ...
                        fmax, kL, uMax/kL);
                otherwise
                    error('MecaStruct:BucklingEngine:condition', 'Condition aux limites inconnue : %s.', cond);
            end
            m.k = k;
            m.kL = k*L;
        end

        function mc = checkMode(m, cond, L)
            %CHECKMODE Vérifie numériquement conditions aux limites, équation et normalisation du mode.
            k = m.k;
            switch cond
                case 'articule-articule'
                    labels = {'v(0) = 0', 'v''''(0) = 0 (moment nul)', 'v(L) = 0', 'v''''(L) = 0 (moment nul)'};
                    res = [m.v(0), m.d2(0)/k^2, m.v(L), m.d2(L)/k^2];
                case 'encastre-libre'
                    labels = {'v(0) = 0', 'v''(0) = 0', 'v''''(L) = 0 (moment nul)', ...
                        'v''''''(L) + k² v''(L) = 0 (effort tranchant nul)'};
                    res = [m.v(0), m.d1(0)/k, m.d2(L)/k^2, (m.d3(L) + k^2*m.d1(L))/k^3];
                case 'encastre-articule'
                    labels = {'v(0) = 0', 'v''(0) = 0', 'v(L) = 0', 'v''''(L) = 0 (moment nul)'};
                    res = [m.v(0), m.d1(0)/k, m.v(L), m.d2(L)/k^2];
                otherwise % 'encastre-encastre'
                    labels = {'v(0) = 0', 'v''(0) = 0', 'v(L) = 0', 'v''(L) = 0'};
                    res = [m.v(0), m.d1(0)/k, m.v(L), m.d1(L)/k];
            end
            sg = linspace(0, L, 801);
            odeRes = max(abs(m.d4(sg) + k^2*m.d2(sg)))/k^4;
            % Contrôle indépendant : dérivée seconde par différences finies centrées
            h = 1e-4*L;
            si = linspace(0.02*L, 0.98*L, 97);
            fd2 = (m.v(si + h) - 2*m.v(si) + m.v(si - h))/h^2;
            fdRes = max(abs(fd2 - m.d2(si)))/k^2;
            % Contrôle indépendant : dérivée première par différences finies centrées
            fd1 = (m.v(si + h) - m.v(si - h))/(2*h);
            fd1Res = max(abs(fd1 - m.d1(si)))/k;
            vg = m.v(sg);
            normRes = max(abs(m.v(m.sMax) - 1), max(max(abs(vg)) - 1, 0));
            tol = 1e-9;
            mc = struct();
            mc.k = k;
            mc.kL = k*L;
            mc.equation = 'v'''''''' + k² v'''' = 0 (dérivée seconde de E·Imin·v'''' + P·v = M_0 + R·(L − s))';
            mc.bcLabels = labels;
            mc.bcResiduals = res;
            mc.odeResidual = odeRes;
            mc.fdResidual = max(fdRes, fd1Res);
            mc.normResidual = normRes;
            mc.tolerance = tol;
            mc.ok = all(abs(res) < tol) && odeRes < tol && mc.fdResidual < 1e-5 && normRes < 1e-12;
        end

        % ================================================================
        %  Équation caractéristique
        % ================================================================

        function d = bcDeterminant(cond, x)
            %BCDETERMINANT Déterminant du système des conditions aux limites (L = 1, k = x).
            %   Solution générale de v'''' + k² v'' = 0 : v = A sin(ks) + B cos(ks) + C s + D.
            phi0 = @(t) [sin(x*t), cos(x*t), t, 1];
            phi1 = @(t) [x*cos(x*t), -x*sin(x*t), 1, 0];
            phi2 = @(t) [-x^2*sin(x*t), -x^2*cos(x*t), 0, 0];
            phi3 = @(t) [-x^3*cos(x*t), x^3*sin(x*t), 0, 0];
            switch cond
                case 'articule-articule'
                    M = [phi0(0); phi2(0); phi0(1); phi2(1)];
                case 'encastre-libre'
                    M = [phi0(0); phi1(0); phi2(1); phi3(1) + x^2*phi1(1)];
                case 'encastre-articule'
                    M = [phi0(0); phi1(0); phi0(1); phi2(1)];
                otherwise % 'encastre-encastre'
                    M = [phi0(0); phi1(0); phi0(1); phi1(1)];
            end
            d = det(M);
        end

        function x = firstRoot(f)
            %FIRSTROOT Première racine positive (x > 0,5) d'une fonction scalaire par balayage + fzero.
            xs = 0.5:0.01:20;
            ys = zeros(size(xs));
            for i = 1:numel(xs)
                ys(i) = f(xs(i));
            end
            j = find(sign(ys(1:end-1)) ~= sign(ys(2:end)) | ys(1:end-1) == 0, 1);
            if isempty(j)
                error('MecaStruct:BucklingEngine:noRoot', ...
                    'Aucune racine de l''équation caractéristique trouvée sur ]0,5 ; 20].');
            end
            if ys(j) == 0
                x = xs(j);
            else
                x = fzero(f, [xs(j), xs(j+1)]);
            end
        end

        function ce = characteristicEquation(cond, useSym)
            %CHARACTERISTICEQUATION Équation caractéristique, première racine k·L et vérifications.
            info = BucklingEngine.conditionInfo(cond);
            switch cond
                case 'articule-articule'
                    ce.latex = '$\sin(k\,L) = 0$';
                    ce.text = 'sin(kL) = 0';
                case 'encastre-libre'
                    ce.latex = '$\cos(k\,L) = 0$';
                    ce.text = 'cos(kL) = 0';
                case 'encastre-articule'
                    ce.latex = '$\tan(k\,L) = k\,L$';
                    ce.text = 'tan(kL) = kL';
                otherwise
                    ce.latex = '$2 - 2\cos(k\,L) - k\,L\,\sin(k\,L) = 0$';
                    ce.text = '2 − 2 cos(kL) − kL sin(kL) = 0';
            end
            ce.kLReference = info.kLRef;
            ce.symbolic = struct('ok', false, 'message', '', 'generalSolution', '', ...
                'solutionBC', '', 'charEquation', '', 'kGeneral', '', 'kConditions', '', 'P1', '', ...
                'dsolveVerified', false, 'determinant', '', 'kL', NaN);
            % Racine numérique (toujours calculée : contrôle croisé)
            kLnum = BucklingEngine.firstRoot(@(x) BucklingEngine.bcDeterminant(cond, x));
            ce.kLNumeric = kLnum;
            ce.method = 'numérique';
            ce.kL = kLnum;
            ce.determinant = 'det[M(kL)] évalué numériquement (solution A sin ks + B cos ks + C s + D)';
            if useSym
                try
                    sy = BucklingEngine.symbolicSolve(cond);
                    ce.symbolic = sy;
                    if sy.ok
                        ce.method = 'symbolique';
                        ce.kL = sy.kL;
                        ce.determinant = sy.determinant;
                    end
                catch ME
                    ce.symbolic.message = ['Échec de la résolution symbolique : ' ME.message];
                end
            end
            ce.verified = abs(ce.kL - info.kLRef) <= 1e-9*info.kLRef ...
                && abs(kLnum - info.kLRef) <= 1e-9*info.kLRef;
            if strcmp(ce.method, 'symbolique')
                ce.verified = ce.verified && ce.symbolic.dsolveVerified;
            end
        end

        function sy = symbolicSolve(cond)
            %SYMBOLICSOLVE Résolution symbolique (dsolve) et déterminant des conditions aux limites.
            %   Résultats indépendants des valeurs numériques : mis en cache par condition.
            persistent cache
            if isempty(cache)
                cache = containers.Map('KeyType', 'char', 'ValueType', 'any');
            end
            if isKey(cache, cond)
                sy = cache(cond);
                return
            end
            sy = struct('ok', false, 'message', '', 'generalSolution', '', 'solutionBC', '', ...
                'charEquation', '', 'kGeneral', '', 'kConditions', '', 'P1', '', 'dsolveVerified', false, ...
                'determinant', '', 'kL', NaN);

            % --- 1) Cas de référence articulé-articulé : dsolve de v'' + k² v = 0 ---
            sS = sym('s');
            kS = sym('k', 'positive');
            LS = sym('L', 'positive');
            ES = sym('E', 'positive');
            IS = sym('Imin', 'positive');
            vF = symfun(str2sym('v(s)'), sS);
            ode = diff(vF, sS, 2) + kS^2*vF == 0;
            vGen = dsolve(ode);
            vBC = dsolve(ode, vF(0) == 0);
            names = arrayfun(@char, symvar(vBC), 'UniformOutput', false);
            cst = names(~ismember(names, {'s', 'k', 'L'}));
            if isempty(cst)
                error('MecaStruct:BucklingEngine:symbolic', 'Constante d''intégration introuvable.');
            end
            Cs = sym(cst{1});
            charEq = simplify(subs(vBC, sS, LS)/Cs);
            ratio = simplify(charEq/sin(kS*LS));
            isSin = isempty(symvar(ratio)) && abs(abs(double(ratio)) - 1) < 1e-14;
            kSol = solve(charEq == 0, kS, 'ReturnConditions', true);
            if isempty(kSol.parameters)
                k1 = kSol.k(1);
            else
                k1 = subs(kSol.k(1), kSol.parameters(1), 1);
            end
            P1 = simplify(k1^2*ES*IS);
            okP1 = isAlways(P1 == sym(pi)^2*ES*IS/LS^2, 'Unknown', 'false');
            sy.generalSolution = char(vGen);
            sy.solutionBC = char(vBC);
            sy.charEquation = char(charEq);
            sy.kGeneral = char(kSol.k(1));
            if isempty(kSol.conditions)
                sy.kConditions = '';
            else
                sy.kConditions = char(kSol.conditions(1));
            end
            sy.P1 = char(P1);
            sy.dsolveVerified = isSin && okP1;

            % --- 2) Condition étudiée : déterminant des 4 conditions aux limites (L = 1, k = x) ---
            xS = sym('x', 'positive');
            tS = sym('t', 'real');
            cf = sym('c', [1 4]);
            w = cf(1)*sin(xS*tS) + cf(2)*cos(xS*tS) + cf(3)*tS + cf(4);
            w1 = diff(w, tS); w2 = diff(w, tS, 2); w3 = diff(w, tS, 3);
            at = @(f, t0) subs(f, tS, t0);
            switch cond
                case 'articule-articule'
                    bc = [at(w, 0); at(w2, 0); at(w, 1); at(w2, 1)];
                case 'encastre-libre'
                    bc = [at(w, 0); at(w1, 0); at(w2, 1); at(w3, 1) + xS^2*at(w1, 1)];
                case 'encastre-articule'
                    bc = [at(w, 0); at(w1, 0); at(w, 1); at(w2, 1)];
                otherwise
                    bc = [at(w, 0); at(w1, 0); at(w, 1); at(w1, 1)];
            end
            M = jacobian(bc, cf);
            dM = simplify(det(M));
            fdet = matlabFunction(dM, 'Vars', xS);
            x0 = BucklingEngine.firstRoot(fdet);
            xr = vpasolve(dM == 0, xS, [x0 - 0.01, x0 + 0.01]);
            if isempty(xr)
                kLs = x0;
            else
                kLs = double(xr(1));
            end
            sy.determinant = ['det[M(x)] = ' char(dM) ' (x = kL)'];
            sy.kL = kLs;
            sy.ok = true;
            sy.message = 'Résolution symbolique effectuée (dsolve, det, vpasolve).';
            cache(cond) = sy;
        end

        % ================================================================
        %  Textes : dérivation, rapport, LaTeX
        % ================================================================

        function d = buildDerivation(cond, E, Imin, L, Lp, PE, ce)
            %BUILDDERIVATION Étapes LaTeX de la résolution de l'équation de flambage.
            T = @BucklingEngine.texNum;
            d = {'$E\,I_{min}\,v''''(s) = M_f(s),\ \ k^2 = \frac{P}{E\,I_{min}}$'};
            switch cond
                case 'articule-articule'
                    d = [d; {
                        '$M_f(s) = -P\,v(s) \Rightarrow v''''(s) + k^2\,v(s) = 0$'
                        '$v(s) = A\cos(k\,s) + B\sin(k\,s)$'
                        '$v(0) = 0 \Rightarrow A = 0$'
                        '$v(L) = 0 \Rightarrow B\sin(k\,L) = 0$'
                        '$B \neq 0 \Rightarrow \sin(k\,L) = 0 \Rightarrow k\,L = n\,\pi$'
                        '$n = 1 : P_E = k^2\,E\,I_{min} = \frac{\pi^2\,E\,I_{min}}{L^2},\ \ L'' = L$'
                        '$v(s) = B\sin\left(\frac{\pi\,s}{L}\right)$'}];
                case 'encastre-libre'
                    d = [d; {
                        '$M_f(s) = P\,(\delta - v(s)),\ \ \delta = v(L)$'
                        '$v''''(s) + k^2\,v(s) = k^2\,\delta$'
                        '$v(s) = A\cos(k\,s) + B\sin(k\,s) + \delta$'
                        '$v(0) = 0 \Rightarrow A = -\delta,\ \ v''(0) = 0 \Rightarrow B = 0$'
                        '$v(L) = \delta \Rightarrow \delta\cos(k\,L) = 0 \Rightarrow \cos(k\,L) = 0$'
                        '$k\,L = \frac{\pi}{2} \Rightarrow P_E = \frac{\pi^2\,E\,I_{min}}{(2\,L)^2},\ \ L'' = 2\,L$'
                        '$v(s) = \delta\left(1 - \cos\frac{\pi\,s}{2\,L}\right)$'}];
                case 'encastre-encastre'
                    d = [d; {
                        '$M_f(s) = M_0 - P\,v(s)\ \ \textrm{(mode symetrique)}$'
                        '$v''''(s) + k^2\,v(s) = \frac{M_0}{E\,I_{min}}$'
                        '$v(s) = A\cos(k\,s) + B\sin(k\,s) + \frac{M_0}{P}$'
                        '$v(0) = 0,\ v''(0) = 0 \Rightarrow A = -\frac{M_0}{P},\ \ B = 0$'
                        '$v(L) = 0,\ v''(L) = 0 \Rightarrow \cos(k\,L) = 1,\ \ \sin(k\,L) = 0$'
                        '$\det = 2 - 2\cos(k\,L) - k\,L\,\sin(k\,L) = 0 \Rightarrow k\,L = 2\,\pi$'
                        '$P_E = \frac{4\,\pi^2\,E\,I_{min}}{L^2} = \frac{\pi^2\,E\,I_{min}}{(L/2)^2},\ \ L'' = \frac{L}{2}$'
                        '$v(s) = \frac{1}{2}\left(1 - \cos\frac{2\,\pi\,s}{L}\right)$'}];
                otherwise % 'encastre-articule'
                    kLx = ce.kLReference;
                    d = [d; {
                        '$M_f(s) = R\,(L - s) - P\,v(s)\ \ \textrm{(R : reaction de l''articulation)}$'
                        '$v''''(s) + k^2\,v(s) = \frac{R}{E\,I_{min}}\,(L - s)$'
                        '$v(s) = A\cos(k\,s) + B\sin(k\,s) + \frac{R}{P}\,(L - s)$'
                        '$v(0) = 0 \Rightarrow A = -\frac{R\,L}{P},\ \ v''(0) = 0 \Rightarrow B = \frac{R}{k\,P}$'
                        '$v(L) = 0 \Rightarrow \tan(k\,L) = k\,L$'
                        ['$k\,L = ' sprintf('%.4f', kLx) ' \Rightarrow P = \frac{' sprintf('%.4g', kLx^2) ...
                        '\,E\,I_{min}}{L^2} = \frac{\pi^2\,E\,I_{min}}{(' sprintf('%.4f', pi/kLx) '\,L)^2}$']
                        '$\textrm{Cours : } L'' = \frac{L}{\sqrt{2}} \Rightarrow P_E = \frac{2\,\pi^2\,E\,I_{min}}{L^2}$'
                        '$v(s) \propto \sin(k\,s) - k\,s + k\,L\,(1 - \cos(k\,s))$'}];
                    d = [d; {'$\textrm{Reference (articule-articule) : } \sin(k\,L) = 0 \Rightarrow k = \frac{\pi}{L}$'}];
            end
            if any(strcmp(cond, {'encastre-libre', 'encastre-encastre'}))
                d = [d; {'$\textrm{Reference (articule-articule) : } \sin(k\,L) = 0 \Rightarrow k = \frac{\pi}{L}$'}];
            end
            if strcmp(ce.method, 'symbolique') && ce.symbolic.dsolveVerified
                d = [d; {'$\textrm{dsolve (articule-articule) : } v(0) = 0 \Rightarrow v(s) = C\,\sin(k\,s),\ \ v(L) = 0 \Rightarrow \sin(k\,L) = 0$'}];
            end
            d = [d; {
                ['$\textrm{Equation caracteristique : } ' ce.latex(2:end-1) ' \Rightarrow k\,L = ' ...
                sprintf('%.6g', ce.kL) '$']
                ['$P_E = \frac{\pi^2\,E\,I_{min}}{L''^2} = \frac{\pi^2 \times ' T(E) ' \times ' T(Imin) ...
                '}{\left(' T(Lp) '\right)^2} = ' T(PE) '\ \mathrm{N}$']
                ['$k = \sqrt{\frac{P_E}{E\,I_{min}}} = \frac{\pi}{L''} = ' T(pi/Lp) '\ \mathrm{m^{-1}},\ \ L = ' ...
                T(L) '\ \mathrm{m}$']}];
        end

        function rep = buildReport(r, info, hasP, pNegative)
            %BUILDREPORT Rapport texte (cell colonne de char) : démarche, régime, comparaison.
            lc = r.lambdaCompression;
            rep = {
                '=== Flambage — analyse selon l''arbre de décision du cours ==='
                sprintf('Données : E = %.5g Pa (%.4g GPa), Re = %.5g Pa (%.4g MPa), S = %.5g m² (%.5g mm²)', ...
                r.E, r.E/1e9, r.Re, r.Re/1e6, r.S, r.S*1e6)
                sprintf('          Iz = %.5g m⁴, Iy = %.5g m⁴, L = %.5g m, coefficient de sécurité s = %.4g', ...
                r.Iz, r.Iy, r.L, r.s)
                sprintf('Conditions aux limites : %s → L'' = %s × L = %.5g m', info.label, info.coefText, r.Lp)
                '1) Plan de flambage (la poutre flambe suivant l''inertie la plus faible) :'
                sprintf('   Imin = min(Iz, Iy) = I%s = %.5g m⁴ ; Imax = %.5g m⁴', r.axis, r.Imin, r.Imax)
                ['   ' r.planeText]
                '2) Rayon de giration minimal :'
                sprintf('   rmin = √(Imin/S) = √(%.5g/%.5g) = %.5g m (%.4g mm)', r.Imin, r.S, r.rmin, r.rmin*1e3)
                '3) Élancement :'
                sprintf('   λ = L''/rmin = %.5g/%.5g = %.5g', r.Lp, r.rmin, r.lambda)
                '4) Élancement limite (σE = Re) :'
                sprintf('   λlim = π·√(E/Re) = π·√(%.5g/%.5g) = %.5g', r.E, r.Re, r.lambdaLim)
                '5) Arbre de décision :'
                sprintf('   λ < %.4g → compression simple ; %.4g ≤ λ < λlim → Rankine ; λ ≥ λlim → Euler', lc, lc)
                };
            sE = r.sigmaE/1e6; ReM = r.Re/1e6;
            switch r.regime
                case 'compression'
                    rep = [rep; {
                        sprintf('   λ = %.4g < %.4g → régime retenu : COMPRESSION SIMPLE.', r.lambda, lc)
                        '   Poutre courte (trapue) : la ruine survient par écrasement/plastification de la section'
                        '   avant toute instabilité ; la charge critique est la charge de plastification Pcrit = PC = Re·S.'
                        sprintf(['   Euler n''est pas pertinent : σE = π²E/λ² = %.5g MPa > Re = %.4g MPa ' ...
                        '(la poutre plastifierait avant de flamber élastiquement).'], sE, ReM)}];
                case 'rankine'
                    rep = [rep; {
                        sprintf('   %.4g ≤ λ = %.4g < λlim = %.4g → régime retenu : RANKINE.', lc, r.lambda, r.lambdaLim)
                        '   Élancement intermédiaire : plastification et instabilité interagissent ; la formule de Rankine'
                        '   1/PR = 1/PE + 1/PC combine les deux modes de ruine : Pcrit = PR = Re·S/(1 + (λ/λlim)²).'
                        sprintf(['   Euler surestimerait la charge (σE = %.5g MPa > Re = %.4g MPa) et la compression ' ...
                        'simple ignorerait l''instabilité.'], sE, ReM)}];
                otherwise
                    rep = [rep; {
                        sprintf('   λ = %.4g ≥ λlim = %.4g → régime retenu : EULER.', r.lambda, r.lambdaLim)
                        sprintf(['   Poutre élancée : σE = π²E/λ² = %.5g MPa ≤ Re = %.4g MPa, l''instabilité ' ...
                        'élastique survient avant la plastification : Pcrit = PE = π²·E·Imin/L''².'], sE, ReM)
                        '   La compression simple surestimerait la résistance (PC > PE) ; Rankine reste plus prudent (PR < PE).'}];
                    if r.lambdaLim <= lc && r.lambda < lc
                        rep = [rep; {sprintf(['   Cas particulier : λlim = %.4g ≤ %.4g (zone de Rankine vide) ; ' ...
                            'Euler est retenu en priorité sur la compression simple car σE ≤ Re (choix sécuritaire).'], ...
                            r.lambdaLim, lc)}];
                    end
            end
            % ---- Comparaison des trois modèles ----
            names = {'Compression  PC = Re·S', 'Euler        PE = π²E·Imin/L''²', ...
                'Rankine      PR = Re·S/(1+(λ/λlim)²)'};
            vals = [r.PC, r.PE, r.PR];
            ids = {'compression', 'euler', 'rankine'};
            rep = [rep; {
                '6) Comparaison des trois modèles (calculés quel que soit le régime) :'
                sprintf('   %-40s %-28s %-14s %s', 'Modèle', 'Charge critique', 'σ = P/S', 'P/Pcrit retenu')}];
            for i = 1:3
                if strcmp(ids{i}, r.regime)
                    mark = '  ← retenu';
                else
                    mark = '';
                end
                rep = [rep; {sprintf('   %-40s %12.5g N (%9.4g kN)  %9.4g MPa  %8.4f%s', names{i}, vals(i), ...
                    vals(i)/1e3, vals(i)/r.S/1e6, vals(i)/r.Pcrit, mark)}]; %#ok<AGROW>
            end
            invSum = 1/r.PE + 1/r.PC;
            [pmin, imin] = min(vals);
            rep = [rep; {
                sprintf('   Contrôle de Rankine : 1/PR = %.6g N⁻¹ ; 1/PE + 1/PC = %.6g N⁻¹ (écart relatif %.1e)', ...
                1/r.PR, invSum, abs(1/r.PR - invSum)/invSum)
                sprintf('   Contrainte critique d''Euler : σE = π²E/λ² = %.5g Pa (%.5g MPa)', r.sigmaE, sE)
                sprintf(['   Modèle le plus défavorable : %s (%.5g N) ; par construction PR ≤ min(PE, PC) ' ...
                '(PR/min = %.4f).'], strtrim(strtok(names{imin}, ' ')), pmin, r.PR/min(r.PE, r.PC))
                '7) Charge critique et charge admissible :'
                sprintf('   Pcrit = %s = %.5g N (%.4g kN) ; σcrit = Pcrit/S = %.5g MPa', ...
                BucklingEngine.regimeSymbol(r.regime), r.Pcrit, r.Pcrit/1e3, r.sigmaCrit/1e6)
                sprintf('   Padm = Pcrit/s = %.5g/%.4g = %.5g N (%.4g kN) ; σadm = %.5g MPa', ...
                r.Pcrit, r.s, r.Padm, r.Padm/1e3, r.sigmaAdm/1e6)
                '8) Vérification :'}];
            if hasP
                if pNegative
                    rep = [rep; {'   P < 0 interprété comme un effort normal N < 0 (compression) : |P| retenu.'}];
                end
                if r.ok
                    verdict = 'VÉRIFIÉ'; cmp = '≤';
                else
                    verdict = 'NON VÉRIFIÉ (risque de flambage)'; cmp = '>';
                end
                rep = [rep; {
                    sprintf('   P = %.5g N (%.4g kN) ; σ = P/S = %.5g MPa', r.P, r.P/1e3, r.sigmaApplied/1e6)
                    sprintf('   P %s Padm = %.5g N → %s', cmp, r.Padm, verdict)
                    sprintf('   Coefficient de sécurité obtenu Pcrit/P = %.4g (requis s = %.4g) ; taux d''utilisation P/Padm = %.1f %%', ...
                    r.safetyObtained, r.s, 100*r.utilization)}];
            else
                rep = [rep; {'   Aucun effort P fourni : seule la charge admissible Padm est calculée.'}];
            end
            mc = r.modeCheck;
            if mc.ok
                mcTxt = 'conforme';
            else
                mcTxt = 'NON conforme';
            end
            ce = r.charEquation;
            rep = [rep; {
                '9) Mode propre de flambage (normalisé, max = 1) :'
                ['   ' r.modeText]
                sprintf(['   Vérification numérique : conditions aux limites (résidu max %.1e), équation %s ' ...
                '(résidu %.1e), différences finies (écart %.1e) → %s.'], max(abs(mc.bcResiduals)), ...
                'v⁽⁴⁾ + k²v'''' = 0', mc.odeResidual, mc.fdResidual, mcTxt)
                sprintf('   Conditions vérifiées : %s', strjoin(mc.bcLabels, ' ; '))
                sprintf('10) Résolution de l''équation différentielle (méthode %s) :', ce.method)
                '   E·Imin·v'''' = Mf(s) avec Mf = −P·v (+ moment d''encastrement / réaction) ⇒ v'''' + k²·v = second membre, k² = P/(E·Imin).'
                sprintf('   Équation caractéristique : %s ⇒ première racine kL = %.10g (référence %.10g) → %s.', ...
                ce.text, ce.kL, ce.kLReference, BucklingEngine.yesNo(ce.verified, 'vérifiée', 'NON vérifiée'))}];
            if strcmp(ce.method, 'symbolique')
                sy = ce.symbolic;
                rep = [rep; {
                    sprintf('   Cas de référence articulé-articulé, dsolve(v'''' + k²v = 0) : v(s) = %s', ...
                    sy.generalSolution)
                    sprintf('   avec v(0) = 0 : v(s) = %s ; v(L) = 0 ⇒ %s = 0 ⇒ k = %s (%s) ⇒ P1 = %s', ...
                    sy.solutionBC, sy.charEquation, sy.kGeneral, sy.kConditions, sy.P1)
                    sprintf('   Cas étudié (%s) : %s', info.label, sy.determinant)}];
            else
                rep = [rep; {
                    '   Solution générale v = A sin(ks) + B cos(ks) + C s + D ; les 4 conditions aux limites donnent'
                    '   un système homogène M(kL)·{A B C D} = 0 dont le déterminant s''annule pour la charge critique.'}];
                if ~isempty(ce.symbolic.message)
                    rep = [rep; {['   ' ce.symbolic.message]}];
                end
            end
            rep = [rep; {sprintf('   k = π/L'' = %.5g m⁻¹ ; P = k²·E·Imin = %.5g N', pi/r.Lp, r.PE)}];
            % ---- Remarques ----
            rep = [rep; {'Remarques :'}];
            if strcmp(r.condition, 'encastre-articule')
                rep = [rep; {sprintf(['   L'' = L/√2 = 0,7071 L (valeur du cours). La résolution exacte (tan kL = kL, ' ...
                    'kL = %.4f) donne L''exact = %.4f L, soit PE exact = %.5g N (%+.2f %% par rapport au cours) : ' ...
                    'la valeur du cours est légèrement sécuritaire.'], ce.kL, ce.coefLpExact, ce.PEexact, ...
                    100*(ce.PEexact/r.PE - 1))}];
            end
            if r.lambdaLim > lc
                rep = [rep; {sprintf(['   La courbe de dimensionnement du cours est discontinue : en λ = %.4g, ' ...
                    'Re → σR = %.4g MPa ; en λ = λlim, σR = Re/2 alors que σE = Re.'], lc, ...
                    r.Re/(1 + (lc/r.lambdaLim)^2)/1e6)}];
            end
            if r.s < 1
                rep = [rep; {'   Attention : coefficient de sécurité s < 1 (non sécuritaire).'}];
            end
            rep = [rep; {sprintf('   Méthode de résolution : %s.', r.methodUsed)}];
        end

        function lat = buildLatex(r, info, hasP)
            %BUILDLATEX Formules clés avec valeurs numériques (LaTeX MATLAB).
            T = @BucklingEngine.texNum;
            if strcmp(r.axis, 'y')
                Iname = 'I_y';
            else
                Iname = 'I_z';
            end
            switch r.regime
                case 'compression'
                    regLine = ['$\lambda = ' T(r.lambda) ' < \lambda_C = ' T(r.lambdaCompression) ...
                        ' \Rightarrow \textrm{compression simple}$'];
                    pName = 'P_C';
                case 'rankine'
                    regLine = ['$\lambda_C = ' T(r.lambdaCompression) ' \le \lambda = ' T(r.lambda) ...
                        ' < \lambda_{lim} = ' T(r.lambdaLim) ' \Rightarrow \textrm{Rankine}$'];
                    pName = 'P_R';
                otherwise
                    regLine = ['$\lambda = ' T(r.lambda) ' \ge \lambda_{lim} = ' T(r.lambdaLim) ...
                        ' \Rightarrow \textrm{Euler}$'];
                    pName = 'P_E';
            end
            lat = {
                ['$I_{min} = \min(I_z, I_y) = ' Iname ' = ' T(r.Imin) '\ \mathrm{m^4}$']
                ['$r_{min} = \sqrt{\frac{I_{min}}{S}} = \sqrt{\frac{' T(r.Imin) '}{' T(r.S) '}} = ' ...
                T(r.rmin) '\ \mathrm{m}$']
                ['$L'' = ' info.coefTex '\,L = ' T(r.Lp) '\ \mathrm{m}$']
                ['$\lambda = \frac{L''}{r_{min}} = \frac{' T(r.Lp) '}{' T(r.rmin) '} = ' T(r.lambda) '$']
                ['$\lambda_{lim} = \pi\sqrt{\frac{E}{R_e}} = \pi\sqrt{\frac{' T(r.E) '}{' T(r.Re) '}} = ' ...
                T(r.lambdaLim) '$']
                regLine
                ['$P_C = R_e\,S = ' T(r.Re) ' \times ' T(r.S) ' = ' T(r.PC) '\ \mathrm{N}$']
                ['$P_E = \frac{\pi^2\,E\,I_{min}}{L''^2} = \frac{\pi^2 \times ' T(r.E) ' \times ' T(r.Imin) ...
                '}{\left(' T(r.Lp) '\right)^2} = ' T(r.PE) '\ \mathrm{N}$']
                ['$P_R = \frac{R_e\,S}{1+\left(\frac{\lambda}{\lambda_{lim}}\right)^2} = \frac{' T(r.PC) ...
                '}{1+\left(\frac{' T(r.lambda) '}{' T(r.lambdaLim) '}\right)^2} = ' T(r.PR) '\ \mathrm{N}$']
                ['$\frac{1}{P_R} = \frac{1}{P_E} + \frac{1}{P_C} = ' T(1/r.PR) '\ \mathrm{N^{-1}}$']
                ['$\sigma_E = \frac{\pi^2\,E}{\lambda^2} = ' T(r.sigmaE) '\ \mathrm{Pa}$']
                ['$P_{crit} = ' pName ' = ' T(r.Pcrit) '\ \mathrm{N} \Rightarrow P_{adm} = \frac{P_{crit}}{s} = \frac{' ...
                T(r.Pcrit) '}{' T(r.s) '} = ' T(r.Padm) '\ \mathrm{N}$']
                };
            if hasP
                if r.ok
                    cmp = '\le';
                else
                    cmp = '>';
                end
                lat = [lat; {
                    ['$P = ' T(r.P) '\ \mathrm{N} ' cmp ' P_{adm} = ' T(r.Padm) '\ \mathrm{N}$']
                    ['$\sigma = \frac{P}{S} = ' T(r.sigmaApplied) '\ \mathrm{Pa},\ \ \frac{P_{crit}}{P} = ' ...
                    T(r.safetyObtained) '$']}];
            end
        end

        function s = regimeSymbol(regime)
            %REGIMESYMBOL Nom de la charge critique retenue.
            switch regime
                case 'compression'
                    s = 'PC (compression simple)';
                case 'rankine'
                    s = 'PR (Rankine)';
                otherwise
                    s = 'PE (Euler)';
            end
        end

        function s = yesNo(tf, sYes, sNo)
            %YESNO Choix d'un texte selon un booléen.
            if tf
                s = sYes;
            else
                s = sNo;
            end
        end

        function s = texNum(x)
            %TEXNUM Nombre au format LaTeX (4 chiffres significatifs, puissance de 10 si besoin).
            if isnan(x)
                s = '\mathrm{NaN}';
                return
            end
            if isinf(x)
                if x > 0
                    s = '\infty';
                else
                    s = '-\infty';
                end
                return
            end
            if x == 0
                s = '0';
                return
            end
            % Mantisse et exposant APRÈS arrondi à 4 chiffres significatifs (évite '1e+04'
            % pour 9999,5 ou une mantisse égale à 10)
            tok = regexp(sprintf('%.3e', x), '^([-+]?[\d.]+)e([-+]\d+)$', 'tokens', 'once');
            m = str2double(tok{1});
            e = str2double(tok{2});
            if e >= -3 && e <= 3
                s = sprintf('%.4g', x);
            elseif e == 4
                s = sprintf('%.0f', x);
            else
                s = [sprintf('%.4g', m) ' \times 10^{' sprintf('%d', e) '}'];
            end
        end
    end
end
