classdef TensorAndCriteriaEngine
    %TENSORANDCRITERIAENGINE Analyse locale : tenseurs, cercles de Mohr, critères, loi de Hooke, extensométrie.
    %   Classe statique, sans dépendance interne et sans aucun tracé : les cercles et lieux de
    %   plasticité sont renvoyés sous forme de listes de points, tracés ensuite par PlotEngine.
    %
    %   Unités SI strictes : contraintes en Pa, déformations sans dimension (m/m), angles en rad,
    %   tensions électriques en V, coefficients de dilatation en 1/°C, écarts de température en °C.
    %   Les textes (report) affichent les contraintes en MPa et les déformations en µdéf pour la
    %   lisibilité ; les champs numériques restent en SI.
    %
    %   Convention de Voigt : [xx yy zz yz xz xy] ; dans les vecteurs de déformation, les termes de
    %   cisaillement sont des glissements « ingénieur » gamma = 2*epsilon.
    %
    %   Convention de signe 2D (plane2D, plane2DStrain) : facette de normale n = (cos θ, sin θ),
    %   tangente t = (−sin θ, cos θ) = z ∧ n, θ compté positivement dans le sens trigonométrique
    %   depuis x ; σ = Cn·n et τ = Cn·t. On a ainsi τ(θ) = σ'x'y' de la rotation tensorielle
    %   σ' = R σ Rᵀ avec R = [cos θ  sin θ ; −sin θ  cos θ] (lignes = n et t). Dans le plan de Mohr
    %   (σ en abscisse, τ en ordonnée), le point de la facette θ part de A(σxx, σxy) (θ = 0) et tourne
    %   de 2θ dans le sens horaire ; B(σyy, −σxy) correspond à θ = 90°.
    %
    %   Méthodes publiques :
    %     principal, facet, plane2D, plane2DStrain, mohr3D, criteria, yieldLoci,
    %     complianceIsotropic, stiffnessIsotropic, hooke3D, hooke3DInverse, planeStress, planeStrain,
    %     complianceOrthotropic, stiffnessOrthotropic, tensorToVoigt, voigtToTensor,
    %     gauge, gaugeStrain, wheatstone, bridgeStrain, rosette45, rosette60.
    %
    %   Erreurs : identifiants 'MecaStruct:TensorAndCriteriaEngine:<id>' avec <id> parmi
    %   badInput, notSymmetric, zeroVector, badMaterial, notPositiveDefinite, orthoSymmetry,
    %   badConfig, badKind.

    methods (Static)

        %% ================================================================================
        %  Tenseur 3D : contraintes principales
        %  ================================================================================
        function r = principal(sig, useSymbolic)
            %PRINCIPAL Contraintes principales, invariants, directions principales et grandeurs octaédriques.
            %   r = TensorAndCriteriaEngine.principal(sig)
            %   r = TensorAndCriteriaEngine.principal(sig, useSymbolic)
            %   Entrées :
            %     sig         : tenseur des contraintes 3x3 symétrique (Pa). Un tenseur 2x2 (état plan)
            %                   est complété par des zéros ; un vecteur de Voigt 6x1 est accepté.
            %     useSymbolic : (optionnel, défaut = Symbolic Math Toolbox disponible) calcule aussi
            %                   det(σ − λI) symboliquement (syms) et l'ajoute dans latex.
            %   Sorties (structure r) :
            %     sigma          : tenseur 3x3 symétrisé (Pa)
            %     I1, I2, I3     : invariants (Pa, Pa², Pa³) ; I1 = tr σ,
            %                      I2 = (σxxσyy − σxy²) + (σxxσzz − σxz²) + (σzzσyy − σyz²), I3 = det σ
            %     charPoly       : [1 −I1 I2 −I3] (polynôme σi³ − I1 σi² + I2 σi − I3 = 0)
            %     rootsCharPoly  : racines de charPoly obtenues par roots (3x1, décroissantes)
            %     eigVals        : valeurs propres obtenues par eig (3x1, décroissantes)
            %     rootsEigDiff   : écart relatif max entre les deux méthodes
            %     sigmaI, sigmaII, sigmaIII : contraintes principales σI ≥ σII ≥ σIII (Pa)
            %     directions     : 3x3, colonnes unitaires nI, nII, nIII formant un trièdre direct
            %     residual       : max ||(σ − σi I) ni|| / max|σ|
            %     tauMax         : (σI − σIII)/2 (Pa)
            %     sigmaOct, tauOct : I1/3 et (1/3)√((σI−σII)² + (σII−σIII)² + (σIII−σI)²) (Pa)
            %     deviator, J2, J3 : déviateur s = σ − (I1/3) I, J2 = ½ s:s, J3 = det s
            %     charPolySym    : coefficients [1 −I1 I2 −I3] (SI) issus du calcul symbolique ([] sinon)
            %     methodUsed     : 'symbolique' (polynôme obtenu par syms) ou 'numérique'
            %     report, latex
            T = TensorAndCriteriaEngine.asTensor(sig, 'sig');
            symOK = TensorAndCriteriaEngine.symbolicAvailable();
            if nargin < 2 || isempty(useSymbolic)
                useSymbolic = symOK;
            end
            useSymbolic = logical(useSymbolic(1)) && symOK;

            sc = max(abs(T(:)));
            if sc == 0
                sc = 1;
            end

            % --- Invariants et polynôme caractéristique
            I1 = T(1,1) + T(2,2) + T(3,3);
            I2 = (T(1,1)*T(2,2) - T(1,2)^2) + (T(1,1)*T(3,3) - T(1,3)^2) + (T(3,3)*T(2,2) - T(2,3)^2);
            I3 = det(T);
            charPoly = [1, -I1, I2, -I3];

            % --- Méthode 1 : racines du polynôme (mis à l'échelle pour le conditionnement)
            pScaled = [1, -I1/sc, I2/sc^2, -I3/sc^3];
            rr = roots(pScaled);
            rr = sort(real(rr(:)) * sc, 'descend');

            % --- Méthode 2 : valeurs et vecteurs propres
            [V, D] = eig(T);
            [ev, idx] = sort(real(diag(D)), 'descend');
            V = real(V(:, idx));
            V(:, 1) = V(:, 1) / norm(V(:, 1));
            V(:, 2) = V(:, 2) - (V(:, 1).' * V(:, 2)) * V(:, 1);
            V(:, 2) = V(:, 2) / norm(V(:, 2));
            for k = 1:2
                [~, im] = max(abs(V(:, k)));
                if V(im, k) < 0
                    V(:, k) = -V(:, k);
                end
            end
            V(:, 3) = cross(V(:, 1), V(:, 2));
            V(:, 3) = V(:, 3) / norm(V(:, 3));

            res = zeros(1, 3);
            for k = 1:3
                res(k) = norm(T * V(:, k) - ev(k) * V(:, k)) / sc;
            end
            rootsEigDiff = max(abs(rr - ev)) / sc;

            % --- Grandeurs dérivées
            tauMax = (ev(1) - ev(3)) / 2;
            sigmaOct = I1 / 3;
            tauOct = sqrt((ev(1)-ev(2))^2 + (ev(2)-ev(3))^2 + (ev(3)-ev(1))^2) / 3;
            Sdev = T - sigmaOct * eye(3);
            J2 = 0.5 * sum(Sdev(:).^2);
            J3 = det(Sdev);

            % --- Polynôme caractéristique symbolique (optionnel)
            charPolySym = [];
            symTex = '';
            symTxt = '';
            symErr = NaN;
            symNote = '';
            methodUsed = 'numérique';
            if useSymbolic
                try
                    lam = sym('lambda');
                    Tm = sym(T / 1e6);
                    pl = expand(det(Tm - lam * sym(eye(3))));
                    cs = double(coeffs(pl, lam, 'All'));
                    if numel(cs) < 4
                        cs = [zeros(1, 4 - numel(cs)), cs];
                    end
                    charPolySym = -cs .* [1, 1e6, 1e12, 1e18];
                    symErr = max(abs((charPolySym - charPoly) ./ [1, sc, sc^2, sc^3]));
                    symTex = TensorAndCriteriaEngine.polyTex(cs, '\lambda');
                    symTxt = TensorAndCriteriaEngine.polyTxt(cs, 'λ');
                    methodUsed = 'symbolique';
                catch ME
                    symNote = ME.message;
                end
            end

            r = struct();
            r.sigma = T;
            r.I1 = I1;
            r.I2 = I2;
            r.I3 = I3;
            r.charPoly = charPoly;
            r.rootsCharPoly = rr;
            r.eigVals = ev;
            r.rootsEigDiff = rootsEigDiff;
            r.sigmaI = ev(1);
            r.sigmaII = ev(2);
            r.sigmaIII = ev(3);
            r.directions = V;
            r.residual = max(res);
            r.tauMax = tauMax;
            r.sigmaOct = sigmaOct;
            r.tauOct = tauOct;
            r.deviator = Sdev;
            r.J2 = J2;
            r.J3 = J3;
            r.charPolySym = charPolySym;
            r.methodUsed = methodUsed;

            % --- Affichage (valeurs nettoyées des résidus d'arrondi)
            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            Tc = TensorAndCriteriaEngine.clean(T, sc) / 1e6;
            evc = TensorAndCriteriaEngine.clean(ev, sc) / 1e6;
            rrc = TensorAndCriteriaEngine.clean(rr, sc * 1e3) / 1e6;
            I1c = TensorAndCriteriaEngine.clean(I1, sc) / 1e6;
            I2c = TensorAndCriteriaEngine.clean(I2, sc^2) / 1e12;
            I3c = TensorAndCriteriaEngine.clean(I3, sc^3) / 1e18;
            Vc = TensorAndCriteriaEngine.clean(V, 1);
            pMPa = [1, -I1c, I2c, -I3c];
            tmc = TensorAndCriteriaEngine.clean(tauMax, sc) / 1e6;
            toc_ = TensorAndCriteriaEngine.clean(tauOct, sc) / 1e6;
            soc = TensorAndCriteriaEngine.clean(sigmaOct, sc) / 1e6;
            names = {'I', 'II', 'III'};

            rep = {};
            rep{end+1} = 'Analyse du tenseur des contraintes σ (valeurs en MPa) :';
            for i = 1:3
                rep{end+1} = sprintf('   | %12s %12s %12s |', F(Tc(i,1)), F(Tc(i,2)), F(Tc(i,3))); %#ok<AGROW>
            end
            rep{end+1} = 'Invariants :';
            rep{end+1} = sprintf('   I1 = tr σ = %s MPa', F(I1c));
            rep{end+1} = sprintf('   I2 = (σxx·σyy − σxy²) + (σxx·σzz − σxz²) + (σzz·σyy − σyz²) = %s MPa²', F(I2c));
            rep{end+1} = sprintf('   I3 = det σ = %s MPa³', F(I3c));
            rep{end+1} = sprintf('Équation caractéristique det(σ − σi·I) = 0 ⇔ σi³ − I1·σi² + I2·σi − I3 = 0 : %s = 0 (λ en MPa)', ...
                TensorAndCriteriaEngine.polyTxt(pMPa, 'λ'));
            if strcmp(methodUsed, 'symbolique')
                rep{end+1} = sprintf('Calcul symbolique (Symbolic Math Toolbox) : det(σ − λ·I) = %s', symTxt);
                rep{end+1} = sprintf('   écart relatif avec les invariants calculés numériquement : %.2e', symErr);
            elseif useSymbolic
                rep{end+1} = ['Calcul symbolique indisponible (repli numérique) : ' symNote];
            end
            rep{end+1} = sprintf('Méthode 1 — racines du polynôme caractéristique (roots) : %s MPa', ...
                TensorAndCriteriaEngine.vecTxt(rrc, 6));
            rep{end+1} = sprintf('Méthode 2 — valeurs propres du tenseur (eig) : %s MPa', ...
                TensorAndCriteriaEngine.vecTxt(evc, 6));
            rep{end+1} = sprintf('   écart relatif maximal roots / eig : %.2e', rootsEigDiff);
            rep{end+1} = sprintf('Contraintes principales (σI ≥ σII ≥ σIII) : σI = %s MPa ; σII = %s MPa ; σIII = %s MPa', ...
                F(evc(1)), F(evc(2)), F(evc(3)));
            rep{end+1} = 'Directions principales, solutions de (σ − σi·I)·ni = 0 (unitaires, trièdre direct) :';
            for k = 1:3
                rep{end+1} = sprintf('   n%s = %s', names{k}, TensorAndCriteriaEngine.vecTxt(Vc(:, k), 5)); %#ok<AGROW>
            end
            rep{end+1} = sprintf('   det[nI nII nIII] = %.6f ; résidu max ||(σ − σi·I)·ni|| / max|σij| = %.2e', det(V), max(res));
            rep{end+1} = sprintf('Cisaillement maximal : τmax = (σI − σIII)/2 = %s MPa', F(tmc));
            rep{end+1} = sprintf('Facette octaédrique : σoct = I1/3 = %s MPa ; τoct = (1/3)·√((σI−σII)² + (σII−σIII)² + (σIII−σI)²) = %s MPa', ...
                F(soc), F(toc_));
            rep{end+1} = sprintf('Déviateur : J2 = %s MPa² ; J3 = %s MPa³ ; √(3·J2) = %s MPa (contrainte de Von Mises)', ...
                F(J2 / 1e12), F(TensorAndCriteriaEngine.clean(J3, sc^3) / 1e18), F(sqrt(3 * J2) / 1e6));
            rep{end+1} = ['Méthode du polynôme caractéristique : ' methodUsed];

            lat = {};
            lat{end+1} = ['$\sigma = ' TensorAndCriteriaEngine.matTex(Tc) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$I_1 = \mathrm{tr}\,\sigma = ' X(I1c) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$I_2 = (\sigma_{xx}\sigma_{yy} - \sigma_{xy}^2) + (\sigma_{xx}\sigma_{zz} - \sigma_{xz}^2) + ' ...
                '(\sigma_{zz}\sigma_{yy} - \sigma_{yz}^2) = ' X(I2c) '\ \mathrm{MPa}^2$'];
            lat{end+1} = ['$I_3 = \mathrm{det}\,\sigma = ' X(I3c) '\ \mathrm{MPa}^3$'];
            lat{end+1} = ['$\sigma_i^3 - I_1\,\sigma_i^2 + I_2\,\sigma_i - I_3 = 0\ \ \Rightarrow\ \ ' ...
                TensorAndCriteriaEngine.polyTex(pMPa, '\lambda') ' = 0$'];
            if strcmp(methodUsed, 'symbolique')
                lat{end+1} = ['$\mathrm{det}(\sigma - \lambda I) = ' symTex ' = 0\ \ (\lambda\ \mathrm{en\ MPa})$'];
            end
            lat{end+1} = ['$\sigma_I = ' X(evc(1)) ',\ \ \sigma_{II} = ' X(evc(2)) ',\ \ \sigma_{III} = ' X(evc(3)) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\vec{n}_I = ' TensorAndCriteriaEngine.vecTex(Vc(:, 1), 4) ',\ \ \vec{n}_{II} = ' ...
                TensorAndCriteriaEngine.vecTex(Vc(:, 2), 4) ',\ \ \vec{n}_{III} = ' TensorAndCriteriaEngine.vecTex(Vc(:, 3), 4) '$'];
            lat{end+1} = ['$\tau_{max} = \frac{\sigma_I - \sigma_{III}}{2} = ' X(tmc) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\sigma_{oct} = \frac{I_1}{3} = ' X(soc) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\tau_{oct} = \frac{1}{3}\sqrt{(\sigma_I-\sigma_{II})^2 + (\sigma_{II}-\sigma_{III})^2 + ' ...
                '(\sigma_{III}-\sigma_I)^2} = ' X(toc_) '\ \mathrm{MPa}$'];

            r.report = rep(:);
            r.latex = lat(:);
        end

        %% ================================================================================
        %  Vecteur contrainte sur une facette
        %  ================================================================================
        function r = facet(sig, n, t)
            %FACET Vecteur contrainte Cn = σ·n sur une facette, composantes normale et tangentielle.
            %   r = TensorAndCriteriaEngine.facet(sig, n)
            %   r = TensorAndCriteriaEngine.facet(sig, n, t)
            %   Entrées :
            %     sig : tenseur des contraintes 3x3 symétrique (Pa) (2x2 accepté, complété par des zéros)
            %     n   : normale à la facette (3 composantes, ou 2 en plan) ; normalisée automatiquement
            %     t   : (optionnel) direction tangentielle ; normalisée et, si elle n'est pas orthogonale
            %           à n, projetée sur le plan de la facette (signalé dans report)
            %   Sorties (structure r) :
            %     n (3x1 unitaire), Cn = σ·n (Pa), sigmaN = Cn·n (Pa), normalVec = sigmaN·n,
            %     tauVec = Cn − sigmaN·n (vecteur cisaillement, Pa), tauNorm = ||tauVec|| (Pa),
            %     tauDir (direction unitaire du cisaillement, zéros si τ nul),
            %     t (3x1 unitaire ou [] si non fourni), tauT = Cn·t (Pa, NaN si t non fourni),
            %     tProjected (logical), report, latex
            T = TensorAndCriteriaEngine.asTensor(sig, 'sig');
            n = TensorAndCriteriaEngine.asVector3(n, 'n');
            nn = norm(n);
            if nn == 0
                TensorAndCriteriaEngine.err('zeroVector', 'La normale n de la facette ne doit pas être nulle.');
            end
            n = n / nn;
            sc = max(abs(T(:)));
            if sc == 0
                sc = 1;
            end
            Cn = T * n;
            sigmaN = Cn.' * n;
            tauVec = Cn - sigmaN * n;
            tauNorm = norm(tauVec);
            if tauNorm > 1e-12 * sc
                tauDir = tauVec / tauNorm;
            else
                tauDir = zeros(3, 1);
            end

            tOut = [];
            tauT = NaN;
            projected = false;
            if nargin >= 3 && ~isempty(t)
                t = TensorAndCriteriaEngine.asVector3(t, 't');
                nt = norm(t);
                if nt == 0
                    TensorAndCriteriaEngine.err('zeroVector', 'La direction tangentielle t ne doit pas être nulle.');
                end
                t = t / nt;
                proj = t.' * n;
                if abs(proj) > 1e-9
                    t = t - proj * n;
                    nt = norm(t);
                    if nt < 1e-9
                        TensorAndCriteriaEngine.err('badInput', ...
                            'La direction t est colinéaire à n : direction tangentielle indéfinie.');
                    end
                    t = t / nt;
                    projected = true;
                end
                tOut = t;
                tauT = Cn.' * t;
            end

            r = struct();
            r.n = n;
            r.Cn = Cn;
            r.sigmaN = sigmaN;
            r.normalVec = sigmaN * n;
            r.tauVec = tauVec;
            r.tauNorm = tauNorm;
            r.tauDir = tauDir;
            r.t = tOut;
            r.tauT = tauT;
            r.tProjected = projected;

            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            nc = TensorAndCriteriaEngine.clean(n, 1);
            Cnc = TensorAndCriteriaEngine.clean(Cn, sc) / 1e6;
            snc = TensorAndCriteriaEngine.clean(sigmaN, sc) / 1e6;
            tvc = TensorAndCriteriaEngine.clean(tauVec, sc) / 1e6;
            tnc = TensorAndCriteriaEngine.clean(tauNorm, sc) / 1e6;

            rep = {};
            rep{end+1} = 'Vecteur contrainte sur la facette de normale n (contraintes en MPa) :';
            rep{end+1} = sprintf('   n (normalisée) = %s', TensorAndCriteriaEngine.vecTxt(nc, 5));
            rep{end+1} = sprintf('   Cn = σ·n = %s MPa', TensorAndCriteriaEngine.vecTxt(Cnc, 6));
            rep{end+1} = sprintf('   Contrainte normale σn = Cn·n = %s MPa (%s)', F(snc), ...
                TensorAndCriteriaEngine.ifelse(sigmaN >= 0, 'traction', 'compression'));
            rep{end+1} = sprintf('   Vecteur cisaillement τ = Cn − σn·n = %s MPa', TensorAndCriteriaEngine.vecTxt(tvc, 6));
            rep{end+1} = sprintf('   Cisaillement ||τ|| = √(||Cn||² − σn²) = %s MPa', F(tnc));
            if ~isempty(tOut)
                if projected
                    rep{end+1} = '   t non orthogonale à n : projetée sur le plan de la facette puis normalisée.';
                end
                rep{end+1} = sprintf('   t = %s ; τt = Cn·t = %s MPa', TensorAndCriteriaEngine.vecTxt(TensorAndCriteriaEngine.clean(tOut, 1), 5), ...
                    F(TensorAndCriteriaEngine.clean(tauT, sc) / 1e6));
            end

            lat = {};
            lat{end+1} = ['$\vec{n} = ' TensorAndCriteriaEngine.vecTex(nc, 4) '$'];
            lat{end+1} = ['$\vec{C}_n = \sigma \cdot \vec{n} = ' TensorAndCriteriaEngine.vecTex(Cnc, 5) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\sigma_n = \vec{C}_n \cdot \vec{n} = ' X(snc) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\vec{\tau} = \vec{C}_n - \sigma_n\,\vec{n} = ' TensorAndCriteriaEngine.vecTex(tvc, 5) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\left|\vec{\tau}\right| = \sqrt{\left|\vec{C}_n\right|^2 - \sigma_n^2} = ' X(tnc) '\ \mathrm{MPa}$'];
            if ~isempty(tOut)
                lat{end+1} = ['$\tau_t = \vec{C}_n \cdot \vec{t} = ' X(TensorAndCriteriaEngine.clean(tauT, sc) / 1e6) '\ \mathrm{MPa}$'];
            end
            r.report = rep(:);
            r.latex = lat(:);
        end

        %% ================================================================================
        %  État plan : cercle de Mohr
        %  ================================================================================
        function r = plane2D(sxx, syy, sxy, theta)
            %PLANE2D État de contraintes plan : contraintes sur une facette θ, cercle de Mohr, directions principales.
            %   r = TensorAndCriteriaEngine.plane2D(sxx, syy, sxy, theta)
            %   Entrées : sxx, syy, sxy (Pa, scalaires) ; theta (rad, scalaire ou tableau, défaut 0) :
            %     angle de la normale n = (cos θ, sin θ) à la facette, compté depuis x.
            %   Formules du cours :
            %     σ(θ) = (σxx+σyy)/2 + (σxx−σyy)/2·cos 2θ + σxy·sin 2θ
            %     τ(θ) = −(σxx−σyy)/2·sin 2θ + σxy·cos 2θ      (τ = Cn·t, t = (−sin θ, cos θ))
            %   Sorties (structure r) :
            %     theta, sigma, tau (même taille que theta), delta (centre (σxx+σyy)/2),
            %     rho (rayon √(((σxx−σyy)/2)² + σxy²)), sigma1 = δ + ρ, sigma2 = δ − ρ,
            %     thetaP = ½·atan2(2σxy, σxx−σyy) (direction de σ1), thetaTauMax = thetaP − π/4
            %     (facette où τ = +ρ), tauMax2D = ρ, pointA = [σxx σxy], pointB = [σyy −σxy],
            %     circle (N x 2 [σ τ], cercle fermé), principal3D (= tri décroissant de [σ1 σ2 0]),
            %     tauMax3D (avec σzz = 0), kind = 'stress', sxx, syy, sxy, report, latex
            sxx = TensorAndCriteriaEngine.scalarIn(sxx, 'sxx');
            syy = TensorAndCriteriaEngine.scalarIn(syy, 'syy');
            sxy = TensorAndCriteriaEngine.scalarIn(sxy, 'sxy');
            if nargin < 4 || isempty(theta)
                theta = 0;
            end
            theta = TensorAndCriteriaEngine.arrayIn(theta, 'theta');

            r = TensorAndCriteriaEngine.mohrCore(sxx, syy, sxy, theta);
            r.kind = 'stress';
            r.sxx = sxx;
            r.syy = syy;
            r.sxy = sxy;
            p3 = sort([r.sigma1, r.sigma2, 0], 'descend');
            r.principal3D = p3;
            r.tauMax3D = (p3(1) - p3(3)) / 2;

            sc = max(abs([sxx, syy, sxy]));
            if sc == 0
                sc = 1;
            end
            C = @(x) TensorAndCriteriaEngine.clean(x, sc) / 1e6;
            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);

            rep = {};
            rep{end+1} = sprintf('État plan de contraintes : σxx = %s MPa ; σyy = %s MPa ; σxy = %s MPa', ...
                F(C(sxx)), F(C(syy)), F(C(sxy)));
            rep{end+1} = 'Convention : n = (cos θ, sin θ), t = (−sin θ, cos θ) = z ∧ n, σ = Cn·n, τ = Cn·t (θ > 0 sens trigonométrique).';
            rep{end+1} = '   σ(θ) = (σxx+σyy)/2 + (σxx−σyy)/2·cos 2θ + σxy·sin 2θ';
            rep{end+1} = '   τ(θ) = −(σxx−σyy)/2·sin 2θ + σxy·cos 2θ';
            if isscalar(theta)
                rep{end+1} = sprintf('Facette θ = %s° : σ = %s MPa ; τ = %s MPa', F(theta * 180 / pi), F(C(r.sigma)), F(C(r.tau)));
            else
                rep{end+1} = sprintf('Facettes : %d valeurs de θ entre %s° et %s° (champs sigma et tau).', ...
                    numel(theta), F(min(theta(:)) * 180 / pi), F(max(theta(:)) * 180 / pi));
            end
            rep{end+1} = sprintf('Cercle de Mohr : centre δ = (σxx+σyy)/2 = %s MPa ; rayon ρ = √(((σxx−σyy)/2)² + σxy²) = %s MPa', ...
                F(C(r.delta)), F(C(r.rho)));
            rep{end+1} = sprintf('   A(σxx, σxy) = (%s ; %s) MPa ; B(σyy, −σxy) = (%s ; %s) MPa', ...
                F(C(sxx)), F(C(sxy)), F(C(syy)), F(C(-sxy)));
            rep{end+1} = sprintf('Contraintes principales planes : σ1 = δ + ρ = %s MPa ; σ2 = δ − ρ = %s MPa', ...
                F(C(r.sigma1)), F(C(r.sigma2)));
            rep{end+1} = sprintf('Direction principale : θP = ½·atan2(2σxy, σxx − σyy) = %s° (σ1), θP + 90° (σ2)', ...
                F(r.thetaP * 180 / pi));
            rep{end+1} = sprintf('Cisaillement maximal dans le plan : τmax = ρ = %s MPa (facette θ = θP − 45° = %s°)', ...
                F(C(r.rho)), F(r.thetaTauMax * 180 / pi));
            rep{end+1} = sprintf('Avec σzz = 0 : contraintes principales 3D = %s MPa ; τmax 3D = %s MPa', ...
                TensorAndCriteriaEngine.vecTxt(C(p3), 6), F(C(r.tauMax3D)));
            rep{end+1} = 'Sur le cercle de Mohr, le point de la facette θ se déduit de A par une rotation de 2θ (sens horaire).';

            lat = {};
            lat{end+1} = '$\sigma(\theta) = \frac{\sigma_{xx}+\sigma_{yy}}{2} + \frac{\sigma_{xx}-\sigma_{yy}}{2}\cos 2\theta + \sigma_{xy}\sin 2\theta$';
            lat{end+1} = '$\tau(\theta) = -\frac{\sigma_{xx}-\sigma_{yy}}{2}\sin 2\theta + \sigma_{xy}\cos 2\theta$';
            if isscalar(theta)
                lat{end+1} = ['$\theta = ' X(theta * 180 / pi) '^\circ :\ \ \sigma = ' X(C(r.sigma)) '\ \mathrm{MPa},\ \ \tau = ' ...
                    X(C(r.tau)) '\ \mathrm{MPa}$'];
            end
            lat{end+1} = ['$\delta = \frac{\sigma_{xx}+\sigma_{yy}}{2} = ' X(C(r.delta)) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\rho = \sqrt{\left(\frac{\sigma_{xx}-\sigma_{yy}}{2}\right)^2 + \sigma_{xy}^2} = ' X(C(r.rho)) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\sigma_1 = \delta + \rho = ' X(C(r.sigma1)) '\ \mathrm{MPa},\ \ \sigma_2 = \delta - \rho = ' ...
                X(C(r.sigma2)) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\theta_P = \frac{1}{2}\mathrm{atan2}(2\sigma_{xy},\ \sigma_{xx}-\sigma_{yy}) = ' X(r.thetaP * 180 / pi) '^\circ$'];
            lat{end+1} = ['$\tau_{max} = \rho = ' X(C(r.rho)) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$A(\sigma_{xx},\ \sigma_{xy}) = (' X(C(sxx)) ',\ ' X(C(sxy)) '),\ \ B(\sigma_{yy},\ -\sigma_{xy}) = (' ...
                X(C(syy)) ',\ ' X(C(-sxy)) ')\ \mathrm{MPa}$'];
            r.report = rep(:);
            r.latex = lat(:);
        end

        function r = plane2DStrain(exx, eyy, exy, theta)
            %PLANE2DSTRAIN État plan de déformations : ε(θ), γ(θ)/2, cercle de Mohr des déformations.
            %   r = TensorAndCriteriaEngine.plane2DStrain(exx, eyy, exy, theta)
            %   Entrées : exx, eyy (sans dimension), exy = γxy/2 (composante TENSORIELLE),
            %     theta (rad, scalaire ou tableau, défaut 0).
            %   Formules : ε(θ) = (εxx+εyy)/2 + (εxx−εyy)/2·cos 2θ + εxy·sin 2θ
            %              γ(θ)/2 = −(εxx−εyy)/2·sin 2θ + εxy·cos 2θ
            %   Sorties : mêmes champs que plane2D (sigma, tau, delta, rho, sigma1, sigma2, thetaP,
            %     thetaTauMax, tauMax2D, pointA = [εxx εxy], pointB = [εyy −εxy], circle [ε γ/2]) pour
            %     pouvoir être tracées par le même code, plus les alias explicites :
            %     eps (= ε(θ)), gammaHalf (= γ(θ)/2), gamma (= γ(θ)), eps1, eps2 (déformations
            %     principales), gammaMax2D (= 2ρ), exx, eyy, exy, gxy (= 2 exy), kind = 'strain',
            %     report, latex.
            exx = TensorAndCriteriaEngine.scalarIn(exx, 'exx');
            eyy = TensorAndCriteriaEngine.scalarIn(eyy, 'eyy');
            exy = TensorAndCriteriaEngine.scalarIn(exy, 'exy');
            if nargin < 4 || isempty(theta)
                theta = 0;
            end
            theta = TensorAndCriteriaEngine.arrayIn(theta, 'theta');

            r = TensorAndCriteriaEngine.mohrCore(exx, eyy, exy, theta);
            r.kind = 'strain';
            r.exx = exx;
            r.eyy = eyy;
            r.exy = exy;
            r.gxy = 2 * exy;
            r.eps = r.sigma;
            r.gammaHalf = r.tau;
            r.gamma = 2 * r.tau;
            r.eps1 = r.sigma1;
            r.eps2 = r.sigma2;
            r.gammaMax2D = 2 * r.rho;

            sc = max(abs([exx, eyy, exy]));
            if sc == 0
                sc = 1;
            end
            U = @(x) TensorAndCriteriaEngine.clean(x, sc) * 1e6;   % en µdéf
            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);

            rep = {};
            rep{end+1} = sprintf('État plan de déformations : εxx = %s µdéf ; εyy = %s µdéf ; εxy = γxy/2 = %s µdéf (γxy = %s µdéf)', ...
                F(U(exx)), F(U(eyy)), F(U(exy)), F(U(2 * exy)));
            rep{end+1} = '   ε(θ) = (εxx+εyy)/2 + (εxx−εyy)/2·cos 2θ + εxy·sin 2θ ; γ(θ)/2 = −(εxx−εyy)/2·sin 2θ + εxy·cos 2θ';
            if isscalar(theta)
                rep{end+1} = sprintf('Direction θ = %s° : ε = %s µdéf ; γ/2 = %s µdéf', F(theta * 180 / pi), F(U(r.eps)), F(U(r.gammaHalf)));
            else
                rep{end+1} = sprintf('Directions : %d valeurs de θ (champs eps et gammaHalf).', numel(theta));
            end
            rep{end+1} = sprintf('Cercle de Mohr des déformations : centre = %s µdéf ; rayon = %s µdéf', F(U(r.delta)), F(U(r.rho)));
            rep{end+1} = sprintf('Déformations principales : ε1 = %s µdéf ; ε2 = %s µdéf ; θP = %s°', ...
                F(U(r.eps1)), F(U(r.eps2)), F(r.thetaP * 180 / pi));
            rep{end+1} = sprintf('Glissement maximal dans le plan : γmax = ε1 − ε2 = %s µdéf', F(U(r.gammaMax2D)));

            lat = {};
            lat{end+1} = '$\varepsilon(\theta) = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} + \frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\cos 2\theta + \varepsilon_{xy}\sin 2\theta$';
            lat{end+1} = '$\frac{\gamma(\theta)}{2} = -\frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\sin 2\theta + \varepsilon_{xy}\cos 2\theta$';
            if isscalar(theta)
                lat{end+1} = ['$\theta = ' X(theta * 180 / pi) '^\circ :\ \ \varepsilon = ' X(U(r.eps)) '\ \mu\mathrm{def},\ \ \frac{\gamma}{2} = ' ...
                    X(U(r.gammaHalf)) '\ \mu\mathrm{def}$'];
            end
            lat{end+1} = ['$\varepsilon_{1,2} = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} \pm \sqrt{\left(\frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\right)^2 + \varepsilon_{xy}^2} = ' ...
                X(U(r.delta)) ' \pm ' X(U(r.rho)) '\ \mu\mathrm{def}$'];
            lat{end+1} = ['$\varepsilon_1 = ' X(U(r.eps1)) '\ \mu\mathrm{def},\ \ \varepsilon_2 = ' X(U(r.eps2)) '\ \mu\mathrm{def}$'];
            lat{end+1} = ['$\theta_P = \frac{1}{2}\mathrm{atan2}(2\varepsilon_{xy},\ \varepsilon_{xx}-\varepsilon_{yy}) = ' X(r.thetaP * 180 / pi) '^\circ$'];
            lat{end+1} = ['$\gamma_{max} = \varepsilon_1 - \varepsilon_2 = ' X(U(r.gammaMax2D)) '\ \mu\mathrm{def}$'];
            r.report = rep(:);
            r.latex = lat(:);
        end

        %% ================================================================================
        %  Tricercle de Mohr
        %  ================================================================================
        function m = mohr3D(pr, nPts)
            %MOHR3D Tricercle de Mohr à partir des contraintes principales.
            %   m = TensorAndCriteriaEngine.mohr3D(pr)
            %   m = TensorAndCriteriaEngine.mohr3D(pr, nPts)
            %   Entrées :
            %     pr   : [σI σII σIII] (Pa) (triées automatiquement) ; [σ1 σ2] (état plan, σ3 = 0 ajouté) ;
            %            ou tenseur 3x3 / 2x2 (contraintes principales calculées par eig)
            %     nPts : (optionnel) nombre de points par cercle (défaut 361)
            %   Sorties (structure m) :
            %     pr (1x3 décroissant), pairs = [1 2 ; 2 3 ; 1 3] (contraintes principales délimitant
            %     chaque cercle), centers (1x3) = [(σI+σII)/2, (σII+σIII)/2, (σI+σIII)/2],
            %     radii (1x3) = [(σI−σII)/2, (σII−σIII)/2, (σI−σIII)/2] (le 3e est le grand cercle),
            %     circles (1x3 cell de N x 2 [σ τ], cercles fermés), tauMax (= radii(3)),
            %     sigmaMin, sigmaMax, report, latex
            p = TensorAndCriteriaEngine.principalTriplet(pr);
            if nargin < 2 || isempty(nPts)
                nPts = 361;
            end
            nPts = max(5, round(TensorAndCriteriaEngine.scalarIn(nPts, 'nPts')));
            centers = [(p(1) + p(2)) / 2, (p(2) + p(3)) / 2, (p(1) + p(3)) / 2];
            radii = [(p(1) - p(2)) / 2, (p(2) - p(3)) / 2, (p(1) - p(3)) / 2];
            phi = linspace(0, 2 * pi, nPts).';
            circles = cell(1, 3);
            for k = 1:3
                circles{k} = [centers(k) + radii(k) * cos(phi), radii(k) * sin(phi)];
            end
            m = struct();
            m.pr = p;
            m.pairs = [1 2; 2 3; 1 3];
            m.centers = centers;
            m.radii = radii;
            m.circles = circles;
            m.tauMax = radii(3);
            m.sigmaMin = p(3);
            m.sigmaMax = p(1);

            sc = max(abs(p));
            if sc == 0
                sc = 1;
            end
            C = @(x) TensorAndCriteriaEngine.clean(x, sc) / 1e6;
            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            rep = {};
            rep{end+1} = sprintf('Tricercle de Mohr : σI = %s MPa ≥ σII = %s MPa ≥ σIII = %s MPa', F(C(p(1))), F(C(p(2))), F(C(p(3))));
            rep{end+1} = sprintf('   cercle (σI, σII)   : centre = %s MPa ; rayon = %s MPa', F(C(centers(1))), F(C(radii(1))));
            rep{end+1} = sprintf('   cercle (σII, σIII) : centre = %s MPa ; rayon = %s MPa', F(C(centers(2))), F(C(radii(2))));
            rep{end+1} = sprintf('   cercle (σI, σIII)  : centre = %s MPa ; rayon = %s MPa = τmax', F(C(centers(3))), F(C(radii(3))));
            rep{end+1} = 'Les points (σn, τ) de toutes les facettes sont dans le grand cercle et hors des deux petits.';
            lat = {};
            lat{end+1} = ['$C_{I,II} = \frac{\sigma_I+\sigma_{II}}{2} = ' X(C(centers(1))) ',\ \ R_{I,II} = \frac{\sigma_I-\sigma_{II}}{2} = ' ...
                X(C(radii(1))) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$C_{II,III} = \frac{\sigma_{II}+\sigma_{III}}{2} = ' X(C(centers(2))) ',\ \ R_{II,III} = \frac{\sigma_{II}-\sigma_{III}}{2} = ' ...
                X(C(radii(2))) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$C_{I,III} = \frac{\sigma_I+\sigma_{III}}{2} = ' X(C(centers(3))) ',\ \ R_{I,III} = \frac{\sigma_I-\sigma_{III}}{2} = ' ...
                X(C(radii(3))) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\tau_{max} = R_{I,III} = ' X(C(radii(3))) '\ \mathrm{MPa}$'];
            m.report = rep(:);
            m.latex = lat(:);
        end

        %% ================================================================================
        %  Critères de résistance
        %  ================================================================================
        function c = criteria(pr, Re, s, sigmaR)
            %CRITERIA Critères de Tresca, de Von Mises et de la contrainte normale maximale (Rankine).
            %   c = TensorAndCriteriaEngine.criteria(pr, Re, s, sigmaR)
            %   Entrées :
            %     pr     : [σI σII σIII] (Pa) (triées automatiquement), [σ1 σ2] (état plan) ou tenseur 3x3
            %     Re     : limite élastique σe (Pa, > 0)
            %     s      : (optionnel) coefficient de sécurité (défaut 1)
            %     sigmaR : (optionnel) contrainte de rupture pour le critère des matériaux fragiles
            %              (défaut Re ; l'interface passe Rm quand il est connu)
            %   Sorties (structure c) :
            %     pr, Re, s, sigmaR,
            %     sigmaEqTresca = σI − σIII, sigmaEqVM = (1/√2)·√((σI−σII)² + (σII−σIII)² + (σIII−σI)²),
            %     sigmaMaxNormal = max|σi|, tauMax = (σI − σIII)/2, sigmaAdm = Re/s, sigmaRAdm = sigmaR/s,
            %     okTresca, okVM (σeq ≤ σadm), okRankine (max|σi| ≤ sigmaR/s),
            %     sfTresca = Re/σeqTresca, sfVM = Re/σeqVM, sfRankine = sigmaR/max|σi| (coefficients
            %     de sécurité obtenus, Inf si contrainte nulle), report, latex
            p = TensorAndCriteriaEngine.principalTriplet(pr);
            Re = TensorAndCriteriaEngine.posScalar(Re, 'Re');
            if nargin < 3 || isempty(s)
                s = 1;
            end
            s = TensorAndCriteriaEngine.posScalar(s, 's');
            if nargin < 4 || isempty(sigmaR) || (isscalar(sigmaR) && isnumeric(sigmaR) && isnan(sigmaR))
                sigmaR = Re;
            end
            sigmaR = TensorAndCriteriaEngine.posScalar(sigmaR, 'sigmaR');

            c = struct();
            c.pr = p;
            c.Re = Re;
            c.s = s;
            c.sigmaR = sigmaR;
            c.sigmaEqTresca = p(1) - p(3);
            c.sigmaEqVM = sqrt(((p(1) - p(2))^2 + (p(2) - p(3))^2 + (p(3) - p(1))^2) / 2);
            c.sigmaMaxNormal = max(abs(p));
            c.tauMax = (p(1) - p(3)) / 2;
            c.sigmaAdm = Re / s;
            c.sigmaRAdm = sigmaR / s;
            tol = 1e-12;
            c.okTresca = c.sigmaEqTresca <= c.sigmaAdm * (1 + tol);
            c.okVM = c.sigmaEqVM <= c.sigmaAdm * (1 + tol);
            c.okRankine = c.sigmaMaxNormal <= c.sigmaRAdm * (1 + tol);
            c.sfTresca = TensorAndCriteriaEngine.safeRatio(Re, c.sigmaEqTresca);
            c.sfVM = TensorAndCriteriaEngine.safeRatio(Re, c.sigmaEqVM);
            c.sfRankine = TensorAndCriteriaEngine.safeRatio(sigmaR, c.sigmaMaxNormal);

            sc = max([abs(p), Re]);
            C = @(x) TensorAndCriteriaEngine.clean(x, sc) / 1e6;
            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            V = @(ok) TensorAndCriteriaEngine.ifelse(ok, 'vérifié', 'NON vérifié');
            K = @(ok) TensorAndCriteriaEngine.ifelse(ok, '\le', '>');

            rep = {};
            rep{end+1} = sprintf('Contraintes principales : σI = %s MPa ; σII = %s MPa ; σIII = %s MPa', F(C(p(1))), F(C(p(2))), F(C(p(3))));
            rep{end+1} = sprintf('Contrainte admissible : σadm = Re/s = %s / %s = %s MPa', F(Re / 1e6), F(s), F(c.sigmaAdm / 1e6));
            rep{end+1} = sprintf('Tresca : σeq = σI − σIII = %s MPa (τmax = %s MPa) → critère %s ; coefficient obtenu Re/σeq = %s', ...
                F(C(c.sigmaEqTresca)), F(C(c.tauMax)), V(c.okTresca), F(c.sfTresca));
            rep{end+1} = sprintf('Von Mises : σeq = (1/√2)·√((σI−σII)² + (σII−σIII)² + (σIII−σI)²) = %s MPa → critère %s ; coefficient obtenu = %s', ...
                F(C(c.sigmaEqVM)), V(c.okVM), F(c.sfVM));
            rep{end+1} = sprintf('Contrainte normale maximale (matériaux fragiles) : max|σi| = %s MPa ≤ σR/s = %s MPa ? → %s ; coefficient obtenu = %s', ...
                F(C(c.sigmaMaxNormal)), F(c.sigmaRAdm / 1e6), V(c.okRankine), F(c.sfRankine));
            if c.sigmaEqVM > 0
                rep{end+1} = sprintf('Rapport σeq Tresca / σeq Von Mises = %s (compris entre 1 et 2/√3 ≈ 1,1547)', ...
                    F(c.sigmaEqTresca / c.sigmaEqVM));
            end

            lat = {};
            lat{end+1} = ['$\sigma_{adm} = \frac{R_e}{s} = \frac{' X(Re / 1e6) '}{' X(s) '} = ' X(c.sigmaAdm / 1e6) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\sigma_{eq}^{\mathrm{Tresca}} = \sigma_I - \sigma_{III} = ' X(C(c.sigmaEqTresca)) '\ \mathrm{MPa}\ ' ...
                K(c.okTresca) '\ \sigma_{adm}$'];
            lat{end+1} = ['$\sigma_{eq}^{\mathrm{VM}} = \frac{1}{\sqrt{2}}\sqrt{(\sigma_I-\sigma_{II})^2 + (\sigma_{II}-\sigma_{III})^2 + ' ...
                '(\sigma_{III}-\sigma_I)^2} = ' X(C(c.sigmaEqVM)) '\ \mathrm{MPa}\ ' K(c.okVM) '\ \sigma_{adm}$'];
            lat{end+1} = ['$\mathrm{max}\left|\sigma_i\right| = ' X(C(c.sigmaMaxNormal)) '\ \mathrm{MPa}\ ' K(c.okRankine) ...
                '\ \frac{\sigma_R}{s} = ' X(c.sigmaRAdm / 1e6) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$s_{\mathrm{Tresca}} = \frac{R_e}{\sigma_{eq}^{\mathrm{Tresca}}} = ' X(c.sfTresca) ...
                ',\ \ s_{\mathrm{VM}} = \frac{R_e}{\sigma_{eq}^{\mathrm{VM}}} = ' X(c.sfVM) '$'];
            c.report = rep(:);
            c.latex = lat(:);
        end

        function L = yieldLoci(Re, s, sigmaR, nPts)
            %YIELDLOCI Lieux de plasticité en contraintes planes (σ1, σ2) : Tresca, Von Mises, Rankine.
            %   L = TensorAndCriteriaEngine.yieldLoci(Re, s, sigmaR)
            %   L = TensorAndCriteriaEngine.yieldLoci(Re, s, sigmaR, nPts)
            %   Entrées : Re (Pa), s (défaut 1), sigmaR (défaut Re), nPts (points de l'ellipse, défaut 361).
            %   Sorties (structure L), toutes les courbes fermées, colonnes [σ1 σ2] (Pa) :
            %     tresca   : hexagone max(|σ1|, |σ2|, |σ1 − σ2|) = σadm (7 x 2)
            %     vonMises : ellipse exacte σ1² − σ1·σ2 + σ2² = σadm² (nPts x 2), paramétrée par
            %                σ1 = σadm (cos φ + sin φ/√3), σ2 = σadm (cos φ − sin φ/√3)
            %     rankine  : carré max(|σ1|, |σ2|) = sigmaR/s (5 x 2)
            %     sigmaAdm = Re/s, sigmaRAdm = sigmaR/s, report, latex
            Re = TensorAndCriteriaEngine.posScalar(Re, 'Re');
            if nargin < 2 || isempty(s)
                s = 1;
            end
            s = TensorAndCriteriaEngine.posScalar(s, 's');
            if nargin < 3 || isempty(sigmaR) || (isscalar(sigmaR) && isnumeric(sigmaR) && isnan(sigmaR))
                sigmaR = Re;
            end
            sigmaR = TensorAndCriteriaEngine.posScalar(sigmaR, 'sigmaR');
            if nargin < 4 || isempty(nPts)
                nPts = 361;
            end
            nPts = max(9, round(TensorAndCriteriaEngine.scalarIn(nPts, 'nPts')));

            a = Re / s;
            b = sigmaR / s;
            L = struct();
            L.tresca = a * [1 0; 1 1; 0 1; -1 0; -1 -1; 0 -1; 1 0];
            phi = linspace(0, 2 * pi, nPts).';
            L.vonMises = a * [cos(phi) + sin(phi) / sqrt(3), cos(phi) - sin(phi) / sqrt(3)];
            L.vonMises(end, :) = L.vonMises(1, :);
            L.rankine = b * [1 1; -1 1; -1 -1; 1 -1; 1 1];
            L.sigmaAdm = a;
            L.sigmaRAdm = b;

            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            rep = {};
            rep{end+1} = sprintf('Lieux de plasticité en contraintes planes (σ3 = 0) ; σadm = Re/s = %s MPa :', F(a / 1e6));
            rep{end+1} = '   Tresca : max(|σ1|, |σ2|, |σ1 − σ2|) = σadm → hexagone de sommets (±σadm, 0), (0, ±σadm), ±(σadm, σadm)';
            rep{end+1} = sprintf('   Von Mises : σ1² − σ1·σ2 + σ2² = σadm² → ellipse de demi-axes √2·σadm = %s MPa (bissectrice σ1 = σ2) et √(2/3)·σadm = %s MPa (σ1 = −σ2)', ...
                F(sqrt(2) * a / 1e6), F(sqrt(2 / 3) * a / 1e6));
            rep{end+1} = sprintf('   Contrainte normale maximale : max(|σ1|, |σ2|) = σR/s = %s MPa → carré', F(b / 1e6));
            rep{end+1} = 'L''hexagone de Tresca est inscrit dans l''ellipse de Von Mises (Tresca plus sécuritaire).';
            lat = {};
            lat{end+1} = ['$\mathrm{max}(|\sigma_1|,\ |\sigma_2|,\ |\sigma_1-\sigma_2|) = \sigma_{adm} = \frac{R_e}{s} = ' X(a / 1e6) '\ \mathrm{MPa}$'];
            lat{end+1} = ['$\sigma_1^2 - \sigma_1\sigma_2 + \sigma_2^2 = \sigma_{adm}^2 = ' X((a / 1e6)^2) '\ \mathrm{MPa}^2$'];
            lat{end+1} = ['$\mathrm{max}(|\sigma_1|,\ |\sigma_2|) = \frac{\sigma_R}{s} = ' X(b / 1e6) '\ \mathrm{MPa}$'];
            L.report = rep(:);
            L.latex = lat(:);
        end

        %% ================================================================================
        %  Loi de Hooke
        %  ================================================================================
        function S = complianceIsotropic(E, nu)
            %COMPLIANCEISOTROPIC Matrice de souplesse isotrope 6x6 [S] ({ε} = [S]{σ}), notation de Voigt.
            %   S = TensorAndCriteriaEngine.complianceIsotropic(E, nu)
            %   Entrées : E (Pa, > 0), nu (−1 < ν < 0,5).
            %   Sortie : S (1/Pa), ordre [xx yy zz yz xz xy], cisaillement ingénieur :
            %     S(1:3,1:3) = (1/E)[1 −ν −ν ; −ν 1 −ν ; −ν −ν 1], S(4:6,4:6) = (1/G) I, G = E/(2(1+ν)).
            TensorAndCriteriaEngine.checkMaterial(E, nu);
            G = E / (2 * (1 + nu));
            S = zeros(6);
            S(1:3, 1:3) = (-nu / E) * ones(3) + ((1 + nu) / E) * eye(3);
            S(4:6, 4:6) = eye(3) / G;
        end

        function C = stiffnessIsotropic(E, nu)
            %STIFFNESSISOTROPIC Matrice de rigidité isotrope 6x6 [C] ({σ} = [C]{ε}), notation de Voigt.
            %   C = TensorAndCriteriaEngine.stiffnessIsotropic(E, nu)
            %   Entrées : E (Pa, > 0), nu (−1 < ν < 0,5).
            %   Sortie : C (Pa), ordre [xx yy zz yz xz xy], cisaillement ingénieur :
            %     C(1:3,1:3) = λ·1 + 2μ·I, C(4:6,4:6) = μ·I, λ = Eν/((1+ν)(1−2ν)), μ = G = E/(2(1+ν)).
            TensorAndCriteriaEngine.checkMaterial(E, nu);
            lambda = E * nu / ((1 + nu) * (1 - 2 * nu));
            mu = E / (2 * (1 + nu));
            C = zeros(6);
            C(1:3, 1:3) = lambda * ones(3) + 2 * mu * eye(3);
            C(4:6, 4:6) = mu * eye(3);
        end

        function e = hooke3D(sigV, E, nu, alpha, dT)
            %HOOKE3D Loi de Hooke 3D isotrope avec dilatation thermique : {ε} = [S]{σ} + αΔT{1 1 1 0 0 0}.
            %   e = TensorAndCriteriaEngine.hooke3D(sigV, E, nu, alpha, dT)
            %   Entrées : sigV (vecteur de Voigt 6x1 [σxx σyy σzz σyz σxz σxy] en Pa, ou tenseur 3x3),
            %     E (Pa), nu, alpha (1/°C, défaut 0), dT (°C, défaut 0).
            %   Sortie : e, vecteur de Voigt 6x1 [εxx εyy εzz γyz γxz γxy] (glissements ingénieur).
            if nargin < 4 || isempty(alpha)
                alpha = 0;
            end
            if nargin < 5 || isempty(dT)
                dT = 0;
            end
            alpha = TensorAndCriteriaEngine.scalarIn(alpha, 'alpha');
            dT = TensorAndCriteriaEngine.scalarIn(dT, 'dT');
            sigV = TensorAndCriteriaEngine.asVoigt6(sigV, 'stress', 'sigV');
            S = TensorAndCriteriaEngine.complianceIsotropic(E, nu);
            e = S * sigV + alpha * dT * [1; 1; 1; 0; 0; 0];
        end

        function sigV = hooke3DInverse(epsV, E, nu, alpha, dT)
            %HOOKE3DINVERSE Loi de Hooke 3D inverse : {σ} = [C]({ε} − αΔT{1 1 1 0 0 0}).
            %   sigV = TensorAndCriteriaEngine.hooke3DInverse(epsV, E, nu, alpha, dT)
            %   Entrées : epsV (vecteur de Voigt 6x1 [εxx εyy εzz γyz γxz γxy], glissements ingénieur,
            %     ou tenseur des déformations 3x3), E (Pa), nu, alpha (1/°C, défaut 0), dT (°C, défaut 0).
            %   Sortie : sigV, vecteur de Voigt 6x1 [σxx σyy σzz σyz σxz σxy] (Pa).
            if nargin < 4 || isempty(alpha)
                alpha = 0;
            end
            if nargin < 5 || isempty(dT)
                dT = 0;
            end
            alpha = TensorAndCriteriaEngine.scalarIn(alpha, 'alpha');
            dT = TensorAndCriteriaEngine.scalarIn(dT, 'dT');
            epsV = TensorAndCriteriaEngine.asVoigt6(epsV, 'strain', 'epsV');
            C = TensorAndCriteriaEngine.stiffnessIsotropic(E, nu);
            sigV = C * (epsV - alpha * dT * [1; 1; 1; 0; 0; 0]);
        end

        function r = planeStress(sxx, syy, sxy, E, nu)
            %PLANESTRESS Loi de Hooke en contraintes planes (σzz = σxz = σyz = 0).
            %   r = TensorAndCriteriaEngine.planeStress(sxx, syy, sxy, E, nu)
            %   Entrées : sxx, syy, sxy (Pa, scalaires ou tableaux de même taille), E (Pa), nu.
            %   Sorties (structure r) :
            %     exx = (σxx − νσyy)/E, eyy = (σyy − νσxx)/E, gxy = 2(1+ν)σxy/E = σxy/G, exy = gxy/2,
            %     ezz = −ν(σxx + σyy)/E,
            %     Sred = (1/E)[1 −ν 0 ; −ν 1 0 ; 0 0 2(1+ν)] ({εxx εyy γxy} = Sred·{σxx σyy σxy}),
            %     Qred = inv(Sred) = E/(1−ν²)[1 ν 0 ; ν 1 0 ; 0 0 (1−ν)/2], G, report, latex
            TensorAndCriteriaEngine.checkMaterial(E, nu);
            [sxx, syy, sxy] = TensorAndCriteriaEngine.sameSize3(sxx, syy, sxy, 'sxx', 'syy', 'sxy');
            G = E / (2 * (1 + nu));
            r = struct();
            r.exx = (sxx - nu * syy) / E;
            r.eyy = (syy - nu * sxx) / E;
            r.gxy = sxy / G;
            r.exy = r.gxy / 2;
            r.ezz = -nu * (sxx + syy) / E;
            r.Sred = [1, -nu, 0; -nu, 1, 0; 0, 0, 2 * (1 + nu)] / E;
            r.Qred = E / (1 - nu^2) * [1, nu, 0; nu, 1, 0; 0, 0, (1 - nu) / 2];
            r.G = G;

            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            rep = {};
            rep{end+1} = sprintf('Contraintes planes (σzz = 0) : E = %s GPa ; ν = %s ; G = E/(2(1+ν)) = %s GPa', F(E / 1e9), F(nu), F(G / 1e9));
            rep{end+1} = '   εxx = (σxx − ν·σyy)/E ; εyy = (σyy − ν·σxx)/E ; γxy = σxy/G ; εzz = −ν·(σxx + σyy)/E';
            lat = {};
            lat{end+1} = '$\varepsilon_{xx} = \frac{\sigma_{xx} - \nu\,\sigma_{yy}}{E},\ \ \varepsilon_{yy} = \frac{\sigma_{yy} - \nu\,\sigma_{xx}}{E},\ \ \gamma_{xy} = \frac{2(1+\nu)}{E}\sigma_{xy} = \frac{\sigma_{xy}}{G}$';
            lat{end+1} = '$\varepsilon_{zz} = -\frac{\nu}{E}(\sigma_{xx} + \sigma_{yy})$';
            lat{end+1} = ['$[S_{red}] = \frac{1}{E}\left[ \begin{array}{ccc} 1 & -\nu & 0 \\ -\nu & 1 & 0 \\ 0 & 0 & 2(1+\nu) \end{array} \right] = ' ...
                TensorAndCriteriaEngine.matTex(r.Sred * 1e9) '\ \mathrm{GPa}^{-1}$'];
            if isscalar(sxx)
                rep{end+1} = sprintf('   σxx = %s MPa ; σyy = %s MPa ; σxy = %s MPa', F(sxx / 1e6), F(syy / 1e6), F(sxy / 1e6));
                rep{end+1} = sprintf('   → εxx = %s µdéf ; εyy = %s µdéf ; γxy = %s µdéf ; εzz = %s µdéf', ...
                    F(r.exx * 1e6), F(r.eyy * 1e6), F(r.gxy * 1e6), F(r.ezz * 1e6));
                lat{end+1} = ['$\varepsilon_{xx} = ' X(r.exx * 1e6) ',\ \ \varepsilon_{yy} = ' X(r.eyy * 1e6) ',\ \ \gamma_{xy} = ' ...
                    X(r.gxy * 1e6) ',\ \ \varepsilon_{zz} = ' X(r.ezz * 1e6) '\ \ (\mu\mathrm{def})$'];
            else
                rep{end+1} = sprintf('   Calcul vectorisé sur %d états de contraintes.', numel(sxx));
            end
            r.report = rep(:);
            r.latex = lat(:);
        end

        function r = planeStrain(exx, eyy, gxy, E, nu)
            %PLANESTRAIN Loi de Hooke en déformations planes (εzz = γxz = γyz = 0).
            %   r = TensorAndCriteriaEngine.planeStrain(exx, eyy, gxy, E, nu)
            %   Entrées : exx, eyy, gxy (glissement ingénieur γxy = 2εxy), scalaires ou tableaux de même
            %     taille ; E (Pa) ; nu.
            %   Sorties (structure r) :
            %     sxx = E/((1+ν)(1−2ν))·[(1−ν)εxx + νεyy], syy = E/((1+ν)(1−2ν))·[νεxx + (1−ν)εyy],
            %     sxy = G·γxy, szz = ν(σxx + σyy) (εzz = 0), ezz = 0,
            %     Cred = E/((1+ν)(1−2ν))[1−ν ν 0 ; ν 1−ν 0 ; 0 0 (1−2ν)/2],
            %     Sred = inv(Cred) = (1+ν)/E [1−ν −ν 0 ; −ν 1−ν 0 ; 0 0 2], G, report, latex
            TensorAndCriteriaEngine.checkMaterial(E, nu);
            [exx, eyy, gxy] = TensorAndCriteriaEngine.sameSize3(exx, eyy, gxy, 'exx', 'eyy', 'gxy');
            k = E / ((1 + nu) * (1 - 2 * nu));
            G = E / (2 * (1 + nu));
            r = struct();
            r.sxx = k * ((1 - nu) * exx + nu * eyy);
            r.syy = k * (nu * exx + (1 - nu) * eyy);
            r.sxy = G * gxy;
            r.szz = nu * (r.sxx + r.syy);
            r.ezz = zeros(size(exx));
            r.Cred = k * [1 - nu, nu, 0; nu, 1 - nu, 0; 0, 0, (1 - 2 * nu) / 2];
            r.Sred = (1 + nu) / E * [1 - nu, -nu, 0; -nu, 1 - nu, 0; 0, 0, 2];
            r.G = G;

            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            rep = {};
            rep{end+1} = sprintf('Déformations planes (εzz = 0) : E = %s GPa ; ν = %s ; E/((1+ν)(1−2ν)) = %s GPa', F(E / 1e9), F(nu), F(k / 1e9));
            rep{end+1} = '   σxx = E/((1+ν)(1−2ν))·[(1−ν)εxx + νεyy] ; σyy = E/((1+ν)(1−2ν))·[νεxx + (1−ν)εyy] ; σxy = G·γxy';
            rep{end+1} = '   εzz = 0 ⇒ σzz = ν·(σxx + σyy)';
            lat = {};
            lat{end+1} = '$\sigma_{xx} = \frac{E}{(1+\nu)(1-2\nu)}\left[(1-\nu)\varepsilon_{xx} + \nu\,\varepsilon_{yy}\right],\ \ \sigma_{yy} = \frac{E}{(1+\nu)(1-2\nu)}\left[\nu\,\varepsilon_{xx} + (1-\nu)\varepsilon_{yy}\right]$';
            lat{end+1} = '$\sigma_{xy} = G\,\gamma_{xy},\ \ \varepsilon_{zz} = 0 \Rightarrow \sigma_{zz} = \nu(\sigma_{xx} + \sigma_{yy})$';
            lat{end+1} = ['$[C_{red}] = \frac{E}{(1+\nu)(1-2\nu)}\left[ \begin{array}{ccc} 1-\nu & \nu & 0 \\ \nu & 1-\nu & 0 \\ 0 & 0 & \frac{1-2\nu}{2} \end{array} \right] = ' ...
                TensorAndCriteriaEngine.matTex(r.Cred / 1e9) '\ \mathrm{GPa}$'];
            if isscalar(exx)
                rep{end+1} = sprintf('   εxx = %s µdéf ; εyy = %s µdéf ; γxy = %s µdéf', F(exx * 1e6), F(eyy * 1e6), F(gxy * 1e6));
                rep{end+1} = sprintf('   → σxx = %s MPa ; σyy = %s MPa ; σxy = %s MPa ; σzz = %s MPa', ...
                    F(r.sxx / 1e6), F(r.syy / 1e6), F(r.sxy / 1e6), F(r.szz / 1e6));
                lat{end+1} = ['$\sigma_{xx} = ' X(r.sxx / 1e6) ',\ \ \sigma_{yy} = ' X(r.syy / 1e6) ',\ \ \sigma_{xy} = ' X(r.sxy / 1e6) ...
                    ',\ \ \sigma_{zz} = ' X(r.szz / 1e6) '\ \ (\mathrm{MPa})$'];
            else
                rep{end+1} = sprintf('   Calcul vectorisé sur %d états de déformations.', numel(exx));
            end
            r.report = rep(:);
            r.latex = lat(:);
        end

        function S = complianceOrthotropic(c)
            %COMPLIANCEORTHOTROPIC Matrice de souplesse orthotrope 6x6 (9 constantes), notation de Voigt.
            %   S = TensorAndCriteriaEngine.complianceOrthotropic(c)
            %   Entrée : structure c à champs E1, E2, E3 (Pa), nu12, nu13, nu23, G12, G13, G23 (Pa).
            %     ν_ij = −ε_j/ε_i sous contrainte uniaxiale σ_i. Champs optionnels nu21, nu31, nu32 :
            %     s'ils sont fournis, la symétrie ν_ij/E_i = ν_ji/E_j est contrôlée (tolérance relative 1 %).
            %   Sortie : S (1/Pa), ordre [11 22 33 23 13 12], glissements ingénieur :
            %     S(1:3,1:3) = [1/E1 −ν21/E2 −ν31/E3 ; −ν12/E1 1/E2 −ν32/E3 ; −ν13/E1 −ν23/E2 1/E3],
            %     S(4,4) = 1/G23, S(5,5) = 1/G13, S(6,6) = 1/G12.
            %   Erreurs : constantes non positives, symétrie non respectée, matrice non définie positive
            %     (1 − ν12ν21 > 0, 1 − ν13ν31 > 0, 1 − ν23ν32 > 0, Δ = 1 − ν12ν21 − ν23ν32 − ν13ν31 − 2ν21ν32ν13 > 0).
            k = TensorAndCriteriaEngine.orthoCheck(c);
            S = zeros(6);
            S(1, 1) = 1 / k.E1;
            S(2, 2) = 1 / k.E2;
            S(3, 3) = 1 / k.E3;
            S(1, 2) = -k.nu12 / k.E1;
            S(2, 1) = S(1, 2);
            S(1, 3) = -k.nu13 / k.E1;
            S(3, 1) = S(1, 3);
            S(2, 3) = -k.nu23 / k.E2;
            S(3, 2) = S(2, 3);
            S(4, 4) = 1 / k.G23;
            S(5, 5) = 1 / k.G13;
            S(6, 6) = 1 / k.G12;
        end

        function C = stiffnessOrthotropic(c)
            %STIFFNESSORTHOTROPIC Matrice de rigidité orthotrope 6x6 [C] = [S]⁻¹ (9 constantes).
            %   C = TensorAndCriteriaEngine.stiffnessOrthotropic(c)
            %   Entrée : structure c (voir complianceOrthotropic). Mêmes contrôles (symétrie, définie positivité).
            %   Sortie : C (Pa), ordre [11 22 33 23 13 12], glissements ingénieur ; C(4,4) = G23,
            %     C(5,5) = G13, C(6,6) = G12 ; bloc normal inversé après mise à l'échelle diagonale.
            S = TensorAndCriteriaEngine.complianceOrthotropic(c);
            d = sqrt(1 ./ diag(S(1:3, 1:3)));          % √E_i
            Dm = diag(d);
            Sn = Dm * S(1:3, 1:3) * Dm;                % adimensionnel, diagonale unité
            Cn = Dm * (Sn \ eye(3)) * Dm;
            C = zeros(6);
            C(1:3, 1:3) = (Cn + Cn.') / 2;
            C(4, 4) = 1 / S(4, 4);
            C(5, 5) = 1 / S(5, 5);
            C(6, 6) = 1 / S(6, 6);
        end

        function v = tensorToVoigt(T, kind)
            %TENSORTOVOIGT Conversion d'un tenseur symétrique en vecteur de Voigt.
            %   v = TensorAndCriteriaEngine.tensorToVoigt(T, kind)
            %   Entrées : T (3x3 symétrique, ou 2x2) ; kind = 'stress' (défaut) ou 'strain'.
            %   Sortie : 3x3 → v 6x1 [Txx Tyy Tzz Tyz Txz Txy] ('stress') ou
            %            [Txx Tyy Tzz 2Tyz 2Txz 2Txy] ('strain', glissements ingénieur) ;
            %            2x2 → v 3x1 [Txx Tyy Txy] ou [Txx Tyy 2Txy].
            if nargin < 2 || isempty(kind)
                kind = 'stress';
            end
            f = TensorAndCriteriaEngine.kindFactor(kind);
            if ~isnumeric(T) || ~isreal(T) || any(~isfinite(T(:)))
                TensorAndCriteriaEngine.err('badInput', 'Le tenseur doit être numérique, réel et fini.');
            end
            T = double(T);
            sc = max(abs(T(:)));
            if sc > 0 && max(max(abs(T - T.'))) > 1e-10 * sc
                TensorAndCriteriaEngine.err('notSymmetric', 'Le tenseur à convertir doit être symétrique.');
            end
            if isequal(size(T), [3 3])
                v = [T(1,1); T(2,2); T(3,3); f * T(2,3); f * T(1,3); f * T(1,2)];
            elseif isequal(size(T), [2 2])
                v = [T(1,1); T(2,2); f * T(1,2)];
            else
                TensorAndCriteriaEngine.err('badInput', 'Le tenseur doit être de taille 3x3 ou 2x2.');
            end
        end

        function T = voigtToTensor(v, kind)
            %VOIGTTOTENSOR Conversion d'un vecteur de Voigt en tenseur symétrique.
            %   T = TensorAndCriteriaEngine.voigtToTensor(v, kind)
            %   Entrées : v (6 composantes [xx yy zz yz xz xy], ou 3 composantes [xx yy xy]) ;
            %     kind = 'stress' (défaut) ou 'strain' (les termes de cisaillement de v sont alors des
            %     glissements ingénieur, divisés par 2 dans le tenseur).
            %   Sortie : T 3x3 (ou 2x2) symétrique.
            if nargin < 2 || isempty(kind)
                kind = 'stress';
            end
            f = TensorAndCriteriaEngine.kindFactor(kind);
            if ~isnumeric(v) || ~isreal(v) || any(~isfinite(v(:))) || ~isvector(v)
                TensorAndCriteriaEngine.err('badInput', 'Le vecteur de Voigt doit être un vecteur numérique, réel et fini.');
            end
            v = double(v(:));
            if numel(v) == 6
                T = [v(1), v(6) / f, v(5) / f; v(6) / f, v(2), v(4) / f; v(5) / f, v(4) / f, v(3)];
            elseif numel(v) == 3
                T = [v(1), v(3) / f; v(3) / f, v(2)];
            else
                TensorAndCriteriaEngine.err('badInput', 'Le vecteur de Voigt doit avoir 6 (ou 3) composantes.');
            end
        end

        %% ================================================================================
        %  Extensométrie
        %  ================================================================================
        function r = gauge(K, eps, R0)
            %GAUGE Loi de Bridgman d'une jauge de déformation : ΔR/R = K·ε.
            %   r = TensorAndCriteriaEngine.gauge(K, eps)
            %   r = TensorAndCriteriaEngine.gauge(K, eps, R0)
            %   Entrées : K (facteur de jauge, ≠ 0, ≈ 2 pour les jauges métalliques), eps (déformation,
            %     scalaire ou tableau), R0 (optionnel, résistance nominale en Ω).
            %   Sorties (structure r) : K, eps, dRsurR = K·ε, R0 (NaN si non fourni), dR = R0·ΔR/R (Ω),
            %     report, latex
            K = TensorAndCriteriaEngine.nonZeroScalar(K, 'K');
            eps = TensorAndCriteriaEngine.arrayIn(eps, 'eps');
            if nargin < 3 || isempty(R0)
                R0 = NaN;
            else
                R0 = TensorAndCriteriaEngine.posScalar(R0, 'R0');
            end
            r = struct();
            r.K = K;
            r.eps = eps;
            r.dRsurR = K * eps;
            r.R0 = R0;
            r.dR = R0 * r.dRsurR;
            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            rep = {};
            rep{end+1} = sprintf('Loi de Bridgman : ΔR/R = K·ε avec K = %s', F(K));
            lat = {};
            lat{end+1} = '$\frac{\Delta R}{R} = K\,\varepsilon$';
            if isscalar(eps)
                rep{end+1} = sprintf('   ε = %s µdéf → ΔR/R = %s', F(eps * 1e6), F(r.dRsurR));
                lat{end+1} = ['$\frac{\Delta R}{R} = ' X(K) ' \times ' X(eps * 1e6) ' \cdot 10^{-6} = ' X(r.dRsurR) '$'];
                if ~isnan(R0)
                    rep{end+1} = sprintf('   R0 = %s Ω → ΔR = %s Ω', F(R0), F(r.dR));
                    lat{end+1} = ['$\Delta R = R_0\,\frac{\Delta R}{R} = ' X(R0) ' \times ' X(r.dRsurR) ' = ' X(r.dR) '\ \Omega$'];
                end
            else
                rep{end+1} = sprintf('   Calcul vectorisé sur %d déformations.', numel(eps));
            end
            r.report = rep(:);
            r.latex = lat(:);
        end

        function eps = gaugeStrain(K, dRsurR)
            %GAUGESTRAIN Déformation mesurée par une jauge : ε = (ΔR/R)/K (loi de Bridgman inversée).
            %   eps = TensorAndCriteriaEngine.gaugeStrain(K, dRsurR)
            %   Entrées : K (facteur de jauge, ≠ 0), dRsurR (variation relative de résistance, tableau).
            %   Sortie : eps (même taille que dRsurR).
            K = TensorAndCriteriaEngine.nonZeroScalar(K, 'K');
            dRsurR = TensorAndCriteriaEngine.arrayIn(dRsurR, 'dRsurR');
            eps = dRsurR / K;
        end

        function r = wheatstone(config, K, Vin, eps)
            %WHEATSTONE Tension de sortie d'un pont de Wheatstone équipé de jauges (quart, demi, complet).
            %   r = TensorAndCriteriaEngine.wheatstone(config, K, Vin, eps)
            %   Entrées :
            %     config : 'quart' (jauge 1 active), 'demi' (jauges 1 et 2, bras adjacents) ou
            %              'complet' (jauges 1 à 4) ; les bras 1 et 3 sont opposés, 1-2 et 3-4 adjacents
            %     K      : facteur de jauge
            %     Vin    : tension d'alimentation (V)
            %     eps    : déformations des jauges actives [ε1], [ε1 ε2] ou [ε1 ε2 ε3 ε4] (les jauges
            %              inactives, si fournies, doivent être nulles)
            %   Sorties (structure r) :
            %     config, K, Vin, eps (1x4), nActive,
            %     Vout = Vin·K/4·(ε1 − ε2 + ε3 − ε4) (linéarisé, V),
            %     VoutExact = Vin·(R1/(R1+R2) − R4/(R3+R4)) avec Ri = R(1 + K εi) (V),
            %     linearityError = (Vout − VoutExact)/VoutExact (NaN si VoutExact = 0),
            %     epsIndicated = 4·Vout/(K·Vin) = ε1 − ε2 + ε3 − ε4, bridgeFactor (facteur nominal :
            %     1 quart, 2 demi (ε2 = −ε1, flexion), 4 complet (ε1 = −ε2 = ε3 = −ε4)),
            %     effectiveFactor = epsIndicated/ε1 (NaN si ε1 = 0), epsMeasured = epsIndicated/bridgeFactor,
            %     report, latex
            [cfg, nAct, nFac] = TensorAndCriteriaEngine.bridgeConfig(config);
            K = TensorAndCriteriaEngine.nonZeroScalar(K, 'K');
            Vin = TensorAndCriteriaEngine.posScalar(Vin, 'Vin');
            if ~isnumeric(eps) || ~isreal(eps) || isempty(eps) || ~isvector(eps) || any(~isfinite(eps))
                TensorAndCriteriaEngine.err('badInput', 'eps doit être un vecteur numérique réel et fini (1 à 4 déformations).');
            end
            eps = double(eps(:).');
            if numel(eps) > 4
                TensorAndCriteriaEngine.err('badInput', 'Un pont de Wheatstone comporte au plus 4 jauges (eps de 1 à 4 composantes).');
            end
            if numel(eps) < nAct
                TensorAndCriteriaEngine.err('badInput', 'Le montage « %s » nécessite %d déformation(s) de jauges actives.', cfg, nAct);
            end
            e4 = zeros(1, 4);
            e4(1:numel(eps)) = eps;
            if any(e4(nAct+1:end) ~= 0)
                TensorAndCriteriaEngine.err('badInput', 'Montage « %s » : seules les %d première(s) jauge(s) sont actives (les autres doivent être nulles).', cfg, nAct);
            end
            comb = e4(1) - e4(2) + e4(3) - e4(4);
            Vout = Vin * K / 4 * comb;
            % Formule exacte R1/(R1+R2) − R4/(R3+R4) = (R1·R3 − R2·R4)/((R1+R2)(R3+R4)), Ri = R(1 + xi),
            % écrite sous forme développée (numérateur exactement nul pour un pont équilibré).
            x = K * e4;
            VoutExact = Vin * (x(1) - x(2) + x(3) - x(4) + x(1) * x(3) - x(2) * x(4)) / ...
                ((2 + x(1) + x(2)) * (2 + x(3) + x(4)));
            if VoutExact ~= 0
                linErr = (Vout - VoutExact) / VoutExact;
            else
                linErr = NaN;
            end
            r = struct();
            r.config = cfg;
            r.K = K;
            r.Vin = Vin;
            r.eps = e4;
            r.nActive = nAct;
            r.Vout = Vout;
            r.VoutExact = VoutExact;
            r.linearityError = linErr;
            r.epsIndicated = 4 * Vout / (K * Vin);
            r.bridgeFactor = nFac;
            if e4(1) ~= 0
                r.effectiveFactor = r.epsIndicated / e4(1);
            else
                r.effectiveFactor = NaN;
            end
            r.epsMeasured = r.epsIndicated / nFac;

            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            rep = {};
            rep{end+1} = sprintf('Pont de Wheatstone, montage « %s » (%d jauge(s) active(s)) : K = %s ; Vin = %s V', cfg, nAct, F(K), F(Vin));
            rep{end+1} = sprintf('   Déformations ε1..ε4 = %s µdéf', TensorAndCriteriaEngine.vecTxt(e4 * 1e6, 6));
            rep{end+1} = sprintf('   Vout = Vin·K/4·(ε1 − ε2 + ε3 − ε4) = %s mV (linéarisé)', F(Vout * 1e3));
            rep{end+1} = sprintf('   Vout exact = Vin·(R1/(R1+R2) − R4/(R3+R4)) = %s mV ; erreur de linéarisation = %s %%', ...
                F(VoutExact * 1e3), F(linErr * 100));
            rep{end+1} = sprintf('   Déformation indiquée 4·Vout/(K·Vin) = %s µdéf ; facteur de pont nominal = %d → ε mesurée = %s µdéf', ...
                F(r.epsIndicated * 1e6), nFac, F(r.epsMeasured * 1e6));
            rep{end+1} = 'Jauges opposées (1-3, 2-4) : effets additionnés ; jauges adjacentes (1-2, 3-4) : effets soustraits (compensation thermique).';
            lat = {};
            lat{end+1} = ['$V_{out} = \frac{V_{in}\,K}{4}(\varepsilon_1 - \varepsilon_2 + \varepsilon_3 - \varepsilon_4) = ' X(Vout * 1e3) '\ \mathrm{mV}$'];
            lat{end+1} = ['$V_{out}^{exact} = V_{in}\left(\frac{R_1}{R_1+R_2} - \frac{R_4}{R_3+R_4}\right) = ' X(VoutExact * 1e3) '\ \mathrm{mV}$'];
            lat{end+1} = ['$\varepsilon_{ind} = \frac{4\,V_{out}}{K\,V_{in}} = ' X(r.epsIndicated * 1e6) '\ \mu\mathrm{def},\ \ \varepsilon = \frac{\varepsilon_{ind}}{' ...
                sprintf('%d', nFac) '} = ' X(r.epsMeasured * 1e6) '\ \mu\mathrm{def}$'];
            r.report = rep(:);
            r.latex = lat(:);
        end

        function eps = bridgeStrain(config, K, Vin, Vout, factor)
            %BRIDGESTRAIN Déformation déduite de la tension de sortie d'un pont (réciproque de wheatstone).
            %   eps = TensorAndCriteriaEngine.bridgeStrain(config, K, Vin, Vout)
            %   eps = TensorAndCriteriaEngine.bridgeStrain(config, K, Vin, Vout, factor)
            %   Entrées : config ('quart', 'demi', 'complet'), K, Vin (V), Vout (V, scalaire ou tableau),
            %     factor (optionnel) : facteur de pont ; défaut 1 (quart), 2 (demi), 4 (complet) ;
            %     par exemple 1 + ν pour un demi-pont « Poisson ».
            %   Sortie : eps = 4·Vout/(K·Vin)/factor.
            [~, ~, nFac] = TensorAndCriteriaEngine.bridgeConfig(config);
            K = TensorAndCriteriaEngine.nonZeroScalar(K, 'K');
            Vin = TensorAndCriteriaEngine.posScalar(Vin, 'Vin');
            Vout = TensorAndCriteriaEngine.arrayIn(Vout, 'Vout');
            if nargin < 5 || isempty(factor)
                factor = nFac;
            end
            factor = TensorAndCriteriaEngine.nonZeroScalar(factor, 'factor');
            eps = 4 * Vout / (K * Vin) / factor;
        end

        function r = rosette45(e1, e2, e3, E, nu)
            %ROSETTE45 Dépouillement d'une rosette rectangulaire (jauges à 0°, 90° et 45°).
            %   r = TensorAndCriteriaEngine.rosette45(e1, e2, e3, E, nu)
            %   Entrées : e1 (jauge à 0°, selon x), e2 (jauge à 90°, selon y), e3 (jauge à 45°)
            %     (déformations sans dimension) ; E (Pa) et nu optionnels (contraintes non calculées,
            %     NaN, s'ils sont omis ou vides).
            %   Convention du cours : εxx = ε1, εyy = ε2, εxy = γxy/2 = ε3 − (ε1+ε2)/2.
            %   Sorties (structure r) :
            %     readings = [e1 e2 e3], anglesDeg = [0 90 45], exx, eyy, exy, gxy (= 2 exy),
            %     epsI, epsII (déformations principales), thetaP (rad, direction de epsI depuis x),
            %     gammaMax (= epsI − epsII), ezz (= −ν/(1−ν)(εxx+εyy) en contraintes planes),
            %     sxx, syy, sxy (contraintes planes, Pa), sigmaI, sigmaII (Pa), tauMax2D,
            %     principal3D (tri de [σI σII 0]), sigmaVM (= √(σI² − σIσII + σII²)),
            %     sigmaTresca (= max(|σI|, |σII|, |σI−σII|)),
            %     mohr (structure : center, radius (cercle des déformations), centerStress, radiusStress),
            %     strain2D (résultat de plane2DStrain), stress2D (résultat de plane2D, [] sans matériau),
            %     checkResidual (écart entre lectures et ε(θk) recalculées), report, latex
            e1 = TensorAndCriteriaEngine.scalarIn(e1, 'e1');
            e2 = TensorAndCriteriaEngine.scalarIn(e2, 'e2');
            e3 = TensorAndCriteriaEngine.scalarIn(e3, 'e3');
            if nargin < 4
                E = [];
            end
            if nargin < 5
                nu = [];
            end
            exx = e1;
            eyy = e2;
            exy = e3 - (e1 + e2) / 2;
            r = TensorAndCriteriaEngine.rosetteCore(exx, eyy, exy, E, nu, [e1 e2 e3], [0 90 45], ...
                'Rosette rectangulaire à 45° : jauge 1 à 0° (x), jauge 2 à 90° (y), jauge 3 à 45°');
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            lat = {};
            lat{end+1} = ['$\varepsilon_{xx} = \varepsilon_1 = ' X(exx * 1e6) ',\ \ \varepsilon_{yy} = \varepsilon_2 = ' X(eyy * 1e6) '\ \ (\mu\mathrm{def})$'];
            lat{end+1} = ['$\varepsilon_{xy} = \frac{\gamma_{xy}}{2} = \varepsilon_3 - \frac{\varepsilon_1+\varepsilon_2}{2} = ' X(exy * 1e6) '\ \mu\mathrm{def}$'];
            r.latex = [lat(:); r.latex];
            r.report = [r.report(1); {'   Formules du cours : εxx = ε1 ; εyy = ε2 ; εxy = γxy/2 = ε3 − (ε1 + ε2)/2'}; r.report(2:end)];
        end

        function r = rosette60(e0, e60, e120, E, nu)
            %ROSETTE60 Dépouillement d'une rosette delta (jauges à 0°, 60° et 120°).
            %   r = TensorAndCriteriaEngine.rosette60(e0, e60, e120, E, nu)
            %   Entrées : e0, e60, e120 (déformations mesurées à 0°, 60°, 120° depuis x) ; E (Pa), nu
            %     optionnels.
            %   Formules (ε(θ) = (εxx+εyy)/2 + (εxx−εyy)/2·cos 2θ + εxy·sin 2θ) :
            %     εxx = ε0, εyy = (2(ε60 + ε120) − ε0)/3, εxy = (ε60 − ε120)/√3.
            %   Sorties : mêmes champs que rosette45 (readings = [e0 e60 e120], anglesDeg = [0 60 120]).
            e0 = TensorAndCriteriaEngine.scalarIn(e0, 'e0');
            e60 = TensorAndCriteriaEngine.scalarIn(e60, 'e60');
            e120 = TensorAndCriteriaEngine.scalarIn(e120, 'e120');
            if nargin < 4
                E = [];
            end
            if nargin < 5
                nu = [];
            end
            exx = e0;
            eyy = (2 * (e60 + e120) - e0) / 3;
            exy = (e60 - e120) / sqrt(3);
            r = TensorAndCriteriaEngine.rosetteCore(exx, eyy, exy, E, nu, [e0 e60 e120], [0 60 120], ...
                'Rosette delta à 60° : jauges à 0° (x), 60° et 120°');
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            lat = {};
            lat{end+1} = ['$\varepsilon_{xx} = \varepsilon_0 = ' X(exx * 1e6) ',\ \ \varepsilon_{yy} = \frac{2(\varepsilon_{60}+\varepsilon_{120}) - \varepsilon_0}{3} = ' ...
                X(eyy * 1e6) '\ \ (\mu\mathrm{def})$'];
            lat{end+1} = ['$\varepsilon_{xy} = \frac{\gamma_{xy}}{2} = \frac{\varepsilon_{60} - \varepsilon_{120}}{\sqrt{3}} = ' X(exy * 1e6) '\ \mu\mathrm{def}$'];
            r.latex = [lat(:); r.latex];
            r.report = [r.report(1); {'   Formules : εxx = ε0 ; εyy = (2(ε60 + ε120) − ε0)/3 ; εxy = γxy/2 = (ε60 − ε120)/√3'}; r.report(2:end)];
        end
    end

    %% ====================================================================================
    %  Méthodes internes
    %  ====================================================================================
    methods (Static, Access = private)

        function r = mohrCore(a, b, c, theta)
            %MOHRCORE Calcul commun des cercles de Mohr 2D (contraintes ou déformations tensorielles).
            r = struct();
            r.theta = theta;
            r.sigma = (a + b) / 2 + (a - b) / 2 * cos(2 * theta) + c * sin(2 * theta);
            r.tau = -(a - b) / 2 * sin(2 * theta) + c * cos(2 * theta);
            r.delta = (a + b) / 2;
            r.rho = hypot((a - b) / 2, c);
            r.sigma1 = r.delta + r.rho;
            r.sigma2 = r.delta - r.rho;
            r.thetaP = 0.5 * atan2(2 * c, a - b);
            r.thetaTauMax = r.thetaP - pi / 4;
            r.tauMax2D = r.rho;
            r.pointA = [a, c];
            r.pointB = [b, -c];
            phi = linspace(0, 2 * pi, 361).';
            r.circle = [r.delta + r.rho * cos(phi), r.rho * sin(phi)];
            r.circle(end, :) = r.circle(1, :);
        end

        function r = rosetteCore(exx, eyy, exy, E, nu, readings, anglesDeg, title)
            %ROSETTECORE Exploitation commune des rosettes : principales, contraintes planes, Mohr.
            hasMat = ~isempty(E) && ~isempty(nu);
            if hasMat
                TensorAndCriteriaEngine.checkMaterial(E, nu);
            end
            dE = (exx + eyy) / 2;
            rhoE = hypot((exx - eyy) / 2, exy);
            r = struct();
            r.readings = readings;
            r.anglesDeg = anglesDeg;
            r.exx = exx;
            r.eyy = eyy;
            r.exy = exy;
            r.gxy = 2 * exy;
            r.epsI = dE + rhoE;
            r.epsII = dE - rhoE;
            r.thetaP = 0.5 * atan2(2 * exy, exx - eyy);
            r.gammaMax = 2 * rhoE;
            th = anglesDeg * pi / 180;
            recomputed = dE + (exx - eyy) / 2 * cos(2 * th) + exy * sin(2 * th);
            r.checkResidual = max(abs(recomputed - readings));
            if hasMat
                k = E / (1 - nu^2);
                G = E / (2 * (1 + nu));
                r.ezz = -nu / (1 - nu) * (exx + eyy);
                r.sxx = k * (exx + nu * eyy);
                r.syy = k * (eyy + nu * exx);
                r.sxy = G * 2 * exy;
                r.sigmaI = k * (r.epsI + nu * r.epsII);
                r.sigmaII = k * (r.epsII + nu * r.epsI);
                r.tauMax2D = (r.sigmaI - r.sigmaII) / 2;
                r.principal3D = sort([r.sigmaI, r.sigmaII, 0], 'descend');
                r.sigmaVM = sqrt(r.sigmaI^2 - r.sigmaI * r.sigmaII + r.sigmaII^2);
                r.sigmaTresca = max([abs(r.sigmaI), abs(r.sigmaII), abs(r.sigmaI - r.sigmaII)]);
                cS = (r.sigmaI + r.sigmaII) / 2;
                rS = (r.sigmaI - r.sigmaII) / 2;
            else
                r.ezz = NaN;
                r.sxx = NaN;
                r.syy = NaN;
                r.sxy = NaN;
                r.sigmaI = NaN;
                r.sigmaII = NaN;
                r.tauMax2D = NaN;
                r.principal3D = NaN(1, 3);
                r.sigmaVM = NaN;
                r.sigmaTresca = NaN;
                cS = NaN;
                rS = NaN;
            end
            r.mohr = struct('center', dE, 'radius', rhoE, 'centerStress', cS, 'radiusStress', rS);
            r.strain2D = TensorAndCriteriaEngine.plane2DStrain(exx, eyy, exy, r.thetaP);
            if hasMat
                r.stress2D = TensorAndCriteriaEngine.plane2D(r.sxx, r.syy, r.sxy, r.thetaP);
            else
                r.stress2D = [];
            end

            F = @(x) TensorAndCriteriaEngine.fmt(x, 6);
            X = @(x) TensorAndCriteriaEngine.tex(x, 5);
            sc = max(abs([exx, eyy, exy]));
            if sc == 0
                sc = 1;
            end
            U = @(x) TensorAndCriteriaEngine.clean(x, sc) * 1e6;
            rep = {};
            rep{end+1} = title;
            rep{end+1} = sprintf('   Lectures : %s µdéf aux angles %s°', TensorAndCriteriaEngine.vecTxt(readings * 1e6, 6), ...
                TensorAndCriteriaEngine.vecTxt(anglesDeg, 4));
            rep{end+1} = sprintf('   εxx = %s µdéf ; εyy = %s µdéf ; εxy = %s µdéf ; γxy = %s µdéf', ...
                F(U(exx)), F(U(eyy)), F(U(exy)), F(U(2 * exy)));
            rep{end+1} = sprintf('   Vérification : écart max entre lectures et ε(θk) recalculées = %.2e', r.checkResidual);
            rep{end+1} = sprintf('Déformations principales : εI = %s µdéf ; εII = %s µdéf ; θP = %s° (direction de εI depuis x)', ...
                F(U(r.epsI)), F(U(r.epsII)), F(r.thetaP * 180 / pi));
            rep{end+1} = sprintf('Cercle de Mohr des déformations : centre = %s µdéf ; rayon = %s µdéf ; γmax = %s µdéf', ...
                F(U(dE)), F(U(rhoE)), F(U(r.gammaMax)));
            lat = {};
            lat{end+1} = ['$\varepsilon_{I,II} = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} \pm \sqrt{\left(\frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\right)^2 + \varepsilon_{xy}^2} = ' ...
                X(U(dE)) ' \pm ' X(U(rhoE)) '\ \mu\mathrm{def}$'];
            lat{end+1} = ['$\varepsilon_I = ' X(U(r.epsI)) ',\ \ \varepsilon_{II} = ' X(U(r.epsII)) '\ \mu\mathrm{def},\ \ \theta_P = \frac{1}{2}\mathrm{atan2}(2\varepsilon_{xy},\ \varepsilon_{xx}-\varepsilon_{yy}) = ' ...
                X(r.thetaP * 180 / pi) '^\circ$'];
            if hasMat
                rep{end+1} = sprintf('Contraintes planes (E = %s GPa ; ν = %s) :', F(E / 1e9), F(nu));
                rep{end+1} = sprintf('   σxx = E/(1−ν²)·(εxx + ν·εyy) = %s MPa ; σyy = E/(1−ν²)·(εyy + ν·εxx) = %s MPa ; σxy = E/(1+ν)·εxy = %s MPa', ...
                    F(r.sxx / 1e6), F(r.syy / 1e6), F(r.sxy / 1e6));
                rep{end+1} = sprintf('   σI = E/(1−ν²)·(εI + ν·εII) = %s MPa ; σII = E/(1−ν²)·(εII + ν·εI) = %s MPa ; τmax plan = %s MPa', ...
                    F(r.sigmaI / 1e6), F(r.sigmaII / 1e6), F(r.tauMax2D / 1e6));
                rep{end+1} = sprintf('   εzz = −ν/(1−ν)·(εxx + εyy) = %s µdéf ; σVM = √(σI² − σI·σII + σII²) = %s MPa ; σeq Tresca = %s MPa', ...
                    F(r.ezz * 1e6), F(r.sigmaVM / 1e6), F(r.sigmaTresca / 1e6));
                lat{end+1} = ['$\sigma_{xx} = \frac{E}{1-\nu^2}(\varepsilon_{xx} + \nu\,\varepsilon_{yy}) = ' X(r.sxx / 1e6) ...
                    ',\ \ \sigma_{yy} = \frac{E}{1-\nu^2}(\varepsilon_{yy} + \nu\,\varepsilon_{xx}) = ' X(r.syy / 1e6) '\ \mathrm{MPa}$'];
                lat{end+1} = ['$\sigma_{xy} = \frac{E}{1+\nu}\varepsilon_{xy} = ' X(r.sxy / 1e6) '\ \mathrm{MPa}$'];
                lat{end+1} = ['$\sigma_I = \frac{E}{1-\nu^2}(\varepsilon_I + \nu\,\varepsilon_{II}) = ' X(r.sigmaI / 1e6) ...
                    ',\ \ \sigma_{II} = \frac{E}{1-\nu^2}(\varepsilon_{II} + \nu\,\varepsilon_I) = ' X(r.sigmaII / 1e6) '\ \mathrm{MPa}$'];
                lat{end+1} = ['$\sigma_{VM} = \sqrt{\sigma_I^2 - \sigma_I\sigma_{II} + \sigma_{II}^2} = ' X(r.sigmaVM / 1e6) '\ \mathrm{MPa}$'];
            else
                rep{end+1} = 'Matériau (E, ν) non fourni : contraintes non calculées.';
            end
            r.report = rep(:);
            r.latex = lat(:);
        end

        function k = orthoCheck(c)
            %ORTHOCHECK Contrôle des 9 constantes orthotropes (positivité, symétrie, définie positivité).
            if ~isstruct(c) || ~isscalar(c)
                TensorAndCriteriaEngine.err('badInput', 'Les constantes orthotropes doivent être fournies dans une structure scalaire.');
            end
            req = {'E1', 'E2', 'E3', 'nu12', 'nu13', 'nu23', 'G12', 'G13', 'G23'};
            missing = req(~isfield(c, req));
            if ~isempty(missing)
                TensorAndCriteriaEngine.err('badInput', 'Constantes orthotropes manquantes : %s.', strjoin(missing, ', '));
            end
            k = struct();
            for i = 1:numel(req)
                k.(req{i}) = TensorAndCriteriaEngine.scalarIn(c.(req{i}), req{i});
            end
            mods = {'E1', 'E2', 'E3', 'G12', 'G13', 'G23'};
            for i = 1:numel(mods)
                if k.(mods{i}) <= 0
                    TensorAndCriteriaEngine.err('notPositiveDefinite', ...
                        'Le module %s doit être strictement positif (matrice de souplesse non définie positive).', mods{i});
                end
            end
            k.nu21 = k.nu12 * k.E2 / k.E1;
            k.nu31 = k.nu13 * k.E3 / k.E1;
            k.nu32 = k.nu23 * k.E3 / k.E2;
            % Symétrie ν_ij/E_i = ν_ji/E_j si les coefficients réciproques sont fournis
            recip = {'nu21', 'nu12', 'E2', 'E1'; 'nu31', 'nu13', 'E3', 'E1'; 'nu32', 'nu23', 'E3', 'E2'};
            for i = 1:size(recip, 1)
                f = recip{i, 1};
                if isfield(c, f) && ~isempty(c.(f)) && ~(isnumeric(c.(f)) && isscalar(c.(f)) && isnan(c.(f)))
                    given = TensorAndCriteriaEngine.scalarIn(c.(f), f);
                    expected = k.(f);
                    tol = 1e-2 * max(abs(expected), abs(given)) + 1e-12;
                    if abs(given - expected) > tol
                        TensorAndCriteriaEngine.err('orthoSymmetry', ...
                            ['Symétrie non respectée : %s/%s = %g mais %s/%s = %g (il faut ν_ij/E_i = ν_ji/E_j ; ' ...
                            '%s attendu = %g).'], recip{i, 2}, recip{i, 4}, k.(recip{i, 2}) / k.(recip{i, 4}), ...
                            f, recip{i, 3}, given / k.(recip{i, 3}), f, expected);
                    end
                end
            end
            % Définie positivité (critère de Sylvester sur le bloc normal adimensionné)
            p12 = 1 - k.nu12 * k.nu21;
            p13 = 1 - k.nu13 * k.nu31;
            p23 = 1 - k.nu23 * k.nu32;
            Delta = 1 - k.nu12 * k.nu21 - k.nu23 * k.nu32 - k.nu13 * k.nu31 - 2 * k.nu21 * k.nu32 * k.nu13;
            a = k.nu12 * sqrt(k.E2 / k.E1);
            b = k.nu13 * sqrt(k.E3 / k.E1);
            cc = k.nu23 * sqrt(k.E3 / k.E2);
            Sn = [1, -a, -b; -a, 1, -cc; -b, -cc, 1];
            [~, pChol] = chol(Sn);
            if pChol ~= 0 || p12 <= 0 || p13 <= 0 || p23 <= 0 || Delta <= 0
                TensorAndCriteriaEngine.err('notPositiveDefinite', ...
                    ['Constantes orthotropes non admissibles : la matrice de souplesse n''est pas définie positive ' ...
                    '(énergie de déformation non positive). Conditions : 1 − ν12·ν21 = %.4g, 1 − ν13·ν31 = %.4g, ' ...
                    '1 − ν23·ν32 = %.4g, Δ = 1 − ν12·ν21 − ν23·ν32 − ν13·ν31 − 2·ν21·ν32·ν13 = %.4g ' ...
                    '(toutes doivent être > 0).'], p12, p13, p23, Delta);
            end
        end

        function [cfg, nAct, nFac] = bridgeConfig(config)
            %BRIDGECONFIG Normalisation du nom de montage d'un pont de Wheatstone.
            if isstring(config) && isscalar(config)
                config = char(config);
            end
            if ~ischar(config)
                TensorAndCriteriaEngine.err('badConfig', 'Le montage doit être ''quart'', ''demi'' ou ''complet''.');
            end
            key = lower(strtrim(config));
            switch key
                case {'quart', 'quart de pont', 'quart-de-pont', 'quarter'}
                    cfg = 'quart';
                    nAct = 1;
                    nFac = 1;
                case {'demi', 'demi-pont', 'demi pont', 'half'}
                    cfg = 'demi';
                    nAct = 2;
                    nFac = 2;
                case {'complet', 'pont complet', 'pont-complet', 'full'}
                    cfg = 'complet';
                    nAct = 4;
                    nFac = 4;
                otherwise
                    TensorAndCriteriaEngine.err('badConfig', 'Montage « %s » inconnu : utiliser ''quart'', ''demi'' ou ''complet''.', config);
            end
        end

        function p = principalTriplet(pr)
            %PRINCIPALTRIPLET Contraintes principales triées [σI σII σIII] à partir de diverses entrées.
            if ~isnumeric(pr) || ~isreal(pr) || isempty(pr) || any(~isfinite(pr(:)))
                TensorAndCriteriaEngine.err('badInput', 'Les contraintes principales doivent être numériques, réelles et finies.');
            end
            pr = double(pr);
            if isequal(size(pr), [3 3]) || isequal(size(pr), [2 2])
                T = TensorAndCriteriaEngine.asTensor(pr, 'pr');
                p = reshape(sort(eig(T), 'descend'), 1, 3);
            elseif isvector(pr) && numel(pr) == 3
                p = sort(reshape(pr, 1, 3), 'descend');
            elseif isvector(pr) && numel(pr) == 2
                p = sort([reshape(pr, 1, 2), 0], 'descend');
            elseif isvector(pr) && numel(pr) == 6
                T = TensorAndCriteriaEngine.voigtToTensor(pr, 'stress');
                p = reshape(sort(eig(T), 'descend'), 1, 3);
            else
                TensorAndCriteriaEngine.err('badInput', ...
                    'pr doit être [σI σII σIII], [σ1 σ2] (état plan) ou un tenseur 3x3.');
            end
        end

        function T = asTensor(T, name)
            %ASTENSOR Validation et mise en forme d'un tenseur symétrique 3x3.
            if ~isnumeric(T) || ~isreal(T) || isempty(T) || any(~isfinite(T(:)))
                TensorAndCriteriaEngine.err('badInput', 'Le tenseur %s doit être numérique, réel et fini.', name);
            end
            T = double(T);
            if isequal(size(T), [2 2])
                T = [T, zeros(2, 1); zeros(1, 3)];
            elseif isvector(T) && numel(T) == 6
                T = TensorAndCriteriaEngine.voigtToTensor(T, 'stress');
            elseif ~isequal(size(T), [3 3])
                TensorAndCriteriaEngine.err('badInput', '%s doit être un tenseur 3x3 (ou 2x2, ou un vecteur de Voigt à 6 composantes).', name);
            end
            sc = max(abs(T(:)));
            asym = max(max(abs(T - T.')));
            if sc > 0 && asym > 1e-10 * sc
                TensorAndCriteriaEngine.err('notSymmetric', 'Le tenseur %s n''est pas symétrique (écart max %g).', name, asym);
            end
            T = (T + T.') / 2;
        end

        function v = asVector3(v, name)
            %ASVECTOR3 Validation d'un vecteur à 3 composantes (2 composantes complétées par 0).
            if ~isnumeric(v) || ~isreal(v) || ~isvector(v) || any(~isfinite(v(:)))
                TensorAndCriteriaEngine.err('badInput', 'Le vecteur %s doit être numérique, réel et fini.', name);
            end
            v = double(v(:));
            if numel(v) == 2
                v = [v; 0];
            elseif numel(v) ~= 3
                TensorAndCriteriaEngine.err('badInput', 'Le vecteur %s doit avoir 3 composantes (ou 2 en plan).', name);
            end
        end

        function v = asVoigt6(v, kind, name)
            %ASVOIGT6 Validation d'un vecteur de Voigt 6x1 (tenseur 3x3 converti).
            if isnumeric(v) && isequal(size(v), [3 3])
                v = TensorAndCriteriaEngine.tensorToVoigt(v, kind);
            end
            if ~isnumeric(v) || ~isreal(v) || ~isvector(v) || numel(v) ~= 6 || any(~isfinite(v(:)))
                TensorAndCriteriaEngine.err('badInput', '%s doit être un vecteur de Voigt réel à 6 composantes (ou un tenseur 3x3).', name);
            end
            v = double(v(:));
        end

        function x = scalarIn(x, name)
            %SCALARIN Validation d'un scalaire réel fini.
            if ~isnumeric(x) || ~isreal(x) || ~isscalar(x) || ~isfinite(x)
                TensorAndCriteriaEngine.err('badInput', '%s doit être un scalaire réel fini.', name);
            end
            x = double(x);
        end

        function x = posScalar(x, name)
            %POSSCALAR Validation d'un scalaire réel fini strictement positif.
            x = TensorAndCriteriaEngine.scalarIn(x, name);
            if x <= 0
                TensorAndCriteriaEngine.err('badInput', '%s doit être strictement positif.', name);
            end
        end

        function x = nonZeroScalar(x, name)
            %NONZEROSCALAR Validation d'un scalaire réel fini non nul.
            x = TensorAndCriteriaEngine.scalarIn(x, name);
            if x == 0
                TensorAndCriteriaEngine.err('badInput', '%s ne doit pas être nul.', name);
            end
        end

        function x = arrayIn(x, name)
            %ARRAYIN Validation d'un tableau numérique réel fini non vide.
            if ~isnumeric(x) || ~isreal(x) || isempty(x) || any(~isfinite(x(:)))
                TensorAndCriteriaEngine.err('badInput', '%s doit être un tableau numérique réel, fini et non vide.', name);
            end
            x = double(x);
        end

        function [a, b, c] = sameSize3(a, b, c, na, nb, nc)
            %SAMESIZE3 Validation de trois tableaux de même taille (expansion des scalaires).
            a = TensorAndCriteriaEngine.arrayIn(a, na);
            b = TensorAndCriteriaEngine.arrayIn(b, nb);
            c = TensorAndCriteriaEngine.arrayIn(c, nc);
            sz = size(a);
            if isscalar(a)
                if ~isscalar(b)
                    sz = size(b);
                elseif ~isscalar(c)
                    sz = size(c);
                end
            end
            if isscalar(a), a = a * ones(sz); end
            if isscalar(b), b = b * ones(sz); end
            if isscalar(c), c = c * ones(sz); end
            if ~isequal(size(a), sz) || ~isequal(size(b), sz) || ~isequal(size(c), sz)
                TensorAndCriteriaEngine.err('badInput', '%s, %s et %s doivent être des scalaires ou des tableaux de même taille.', na, nb, nc);
            end
        end

        function checkMaterial(E, nu)
            %CHECKMATERIAL Validation des constantes élastiques isotropes (E > 0, −1 < ν < 0,5).
            if ~isnumeric(E) || ~isreal(E) || ~isscalar(E) || ~isfinite(E) || E <= 0
                TensorAndCriteriaEngine.err('badMaterial', 'Le module d''Young E doit être un scalaire strictement positif (Pa).');
            end
            if ~isnumeric(nu) || ~isreal(nu) || ~isscalar(nu) || ~isfinite(nu) || nu <= -1 || nu >= 0.5
                TensorAndCriteriaEngine.err('badMaterial', 'Le coefficient de Poisson doit vérifier −1 < ν < 0,5.');
            end
        end

        function f = kindFactor(kind)
            %KINDFACTOR Facteur des termes de cisaillement en notation de Voigt (1 contraintes, 2 déformations).
            if isstring(kind) && isscalar(kind)
                kind = char(kind);
            end
            if ~ischar(kind)
                TensorAndCriteriaEngine.err('badKind', 'kind doit valoir ''stress'' ou ''strain''.');
            end
            switch lower(strtrim(kind))
                case {'stress', 'contrainte', 'contraintes'}
                    f = 1;
                case {'strain', 'deformation', 'deformations', 'déformation', 'déformations'}
                    f = 2;
                otherwise
                    TensorAndCriteriaEngine.err('badKind', 'kind doit valoir ''stress'' ou ''strain'' (reçu « %s »).', kind);
            end
        end

        function tf = symbolicAvailable()
            %SYMBOLICAVAILABLE Disponibilité de la Symbolic Math Toolbox (résultat mis en cache).
            persistent cached
            if isempty(cached)
                try
                    cached = license('test', 'Symbolic_Toolbox') && ~isempty(ver('symbolic'));
                catch
                    cached = false;
                end
            end
            tf = cached;
        end

        function q = safeRatio(a, b)
            %SAFERATIO Rapport a/b valant Inf si b est nul.
            if b == 0
                q = Inf;
            else
                q = a / b;
            end
        end

        function out = ifelse(cond, a, b)
            %IFELSE Sélection conditionnelle de deux valeurs.
            if cond
                out = a;
            else
                out = b;
            end
        end

        function x = clean(x, ref)
            %CLEAN Annule les résidus d'arrondi (|x| ≤ 1e-12·ref) pour l'affichage.
            x(abs(x) <= 1e-12 * ref) = 0;
            x = x + 0;
        end

        function s = fmt(x, prec)
            %FMT Formatage texte d'un nombre (prec chiffres significatifs).
            if nargin < 2
                prec = 6;
            end
            x = x + 0;
            if isnan(x)
                s = 'NaN';
            elseif isinf(x)
                if x > 0
                    s = 'Inf';
                else
                    s = '-Inf';
                end
            else
                s = sprintf('%.*g', prec, x);
            end
        end

        function s = tex(x, prec)
            %TEX Formatage LaTeX d'un nombre (notation 1.5 \cdot 10^{-3} pour les exposants).
            if nargin < 2
                prec = 5;
            end
            x = x + 0;
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
            s = sprintf('%.*g', prec, x);
            k = strfind(s, 'e');
            if ~isempty(k)
                mant = s(1:k-1);
                ex = str2double(s(k+1:end));
                if strcmp(mant, '1')
                    s = sprintf('10^{%d}', ex);
                elseif strcmp(mant, '-1')
                    s = sprintf('-10^{%d}', ex);
                else
                    s = sprintf('%s \\cdot 10^{%d}', mant, ex);
                end
            end
        end

        function s = vecTxt(v, prec)
            %VECTXT Formatage texte d'un vecteur : (a ; b ; c).
            if nargin < 2
                prec = 6;
            end
            parts = arrayfun(@(x) TensorAndCriteriaEngine.fmt(x, prec), v(:).', 'UniformOutput', false);
            s = ['(' strjoin(parts, ' ; ') ')'];
        end

        function s = vecTex(v, prec)
            %VECTEX Formatage LaTeX d'un vecteur : (a,\ b,\ c).
            if nargin < 2
                prec = 5;
            end
            parts = arrayfun(@(x) TensorAndCriteriaEngine.tex(x, prec), v(:).', 'UniformOutput', false);
            s = ['(' TensorAndCriteriaEngine.joinRaw(parts, ',\ ') ')'];
        end

        function s = matTex(M)
            %MATTEX Formatage LaTeX d'une matrice (environnement array entre crochets).
            rows = cell(1, size(M, 1));
            for i = 1:size(M, 1)
                rows{i} = TensorAndCriteriaEngine.joinRaw(arrayfun(@(x) TensorAndCriteriaEngine.tex(x, 5), M(i, :), ...
                    'UniformOutput', false), ' & ');
            end
            s = ['\left[ \begin{array}{' repmat('c', 1, size(M, 2)) '} ' TensorAndCriteriaEngine.joinRaw(rows, ' \\ ') ...
                ' \end{array} \right]'];
        end

        function s = joinRaw(parts, delim)
            %JOINRAW Concaténation de chaînes avec un séparateur pris littéralement.
            %   (strjoin interprète les séquences d'échappement du séparateur : '\\' deviendrait '\'.)
            if isempty(parts)
                s = '';
                return
            end
            s = parts{1};
            for k = 2:numel(parts)
                s = [s delim parts{k}]; %#ok<AGROW>
            end
        end

        function s = polyTex(c, var)
            %POLYTEX Formatage LaTeX d'un polynôme (coefficients décroissants, ordre polyval).
            n = numel(c) - 1;
            s = '';
            for k = 1:numel(c)
                p = n - k + 1;
                a = c(k) + 0;
                if a == 0
                    continue
                end
                mag = abs(a);
                if p == 0 || mag ~= 1
                    cs = TensorAndCriteriaEngine.tex(mag, 6);
                else
                    cs = '';
                end
                if p == 0
                    term = cs;
                elseif p == 1
                    term = strtrim([cs '\,' var]);
                else
                    term = sprintf('%s\\,%s^{%d}', cs, var, p);
                end
                if isempty(cs) && p > 0
                    term = regexprep(term, '^\\,', '');
                end
                if isempty(s)
                    if a < 0
                        s = ['-' term];
                    else
                        s = term;
                    end
                elseif a < 0
                    s = [s ' - ' term]; %#ok<AGROW>
                else
                    s = [s ' + ' term]; %#ok<AGROW>
                end
            end
            if isempty(s)
                s = '0';
            end
        end

        function s = polyTxt(c, var)
            %POLYTXT Formatage texte d'un polynôme (coefficients décroissants).
            n = numel(c) - 1;
            s = '';
            sup = {'', '', '²', '³', '⁴', '⁵', '⁶'};
            for k = 1:numel(c)
                p = n - k + 1;
                a = c(k) + 0;
                if a == 0
                    continue
                end
                mag = abs(a);
                if p == 0 || mag ~= 1
                    cs = TensorAndCriteriaEngine.fmt(mag, 6);
                else
                    cs = '';
                end
                if p == 0
                    term = cs;
                else
                    if p + 1 <= numel(sup) && p >= 2
                        pw = sup{p + 1};
                    elseif p == 1
                        pw = '';
                    else
                        pw = sprintf('^%d', p);
                    end
                    if isempty(cs)
                        term = [var pw];
                    else
                        term = [cs '·' var pw];
                    end
                end
                if isempty(s)
                    if a < 0
                        s = ['−' term];
                    else
                        s = term;
                    end
                elseif a < 0
                    s = [s ' − ' term]; %#ok<AGROW>
                else
                    s = [s ' + ' term]; %#ok<AGROW>
                end
            end
            if isempty(s)
                s = '0';
            end
        end

        function err(id, fmtStr, varargin)
            %ERR Lève une erreur 'MecaStruct:TensorAndCriteriaEngine:<id>' avec un message formaté.
            msg = sprintf(fmtStr, varargin{:});
            error(['MecaStruct:TensorAndCriteriaEngine:' id], '%s', msg);
        end
    end
end
