classdef SolicitationsEngine
    %SOLICITATIONSENGINE Sollicitations simples et composées (classe statique, unités SI strictes).
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   Traction/compression (+ thermique), cisaillement (Jourawski), matage (clavette, goupille),
    %   torsion, flexion (contraintes, déformée par 4 méthodes), énergie de déformation, intégrales
    %   de Mohr ; le flambage est délégué à BucklingEngine.
    %
    %   Méthodes publiques :
    %     r    = SolicitationsEngine.traction(p)
    %     r    = SolicitationsEngine.shear(p)
    %     prof = SolicitationsEngine.jourawski(sec, T, n)
    %     r    = SolicitationsEngine.bearing(p)
    %     r    = SolicitationsEngine.keyDesign(p)
    %     r    = SolicitationsEngine.pinDesign(p)
    %     r    = SolicitationsEngine.torsion(p)
    %     r    = SolicitationsEngine.bendingStress(p)
    %     d    = SolicitationsEngine.deflection(model, sol, opts)
    %     U    = SolicitationsEngine.strainEnergy(model, sol)
    %     M    = SolicitationsEngine.mohrIntegral(ppA, ppB, a, b)
    %     b    = SolicitationsEngine.buckling(p)
    %
    %   Contraintes admissibles : σadm = Re/s ; τadm = τe/s avec τe = p.tauE si fourni, sinon
    %   Re/2 (p.criterion = 'Tresca', défaut) ou Re/√3 ('VonMises').
    %
    %   Voir aussi GeometryEngine, BeamAndTrussSolver, DataManager, BucklingEngine.

    methods (Static)

        %% ================================ Traction ================================

        function r = traction(p)
            %TRACTION Traction/compression simple avec dilatation thermique (3 méthodes pour ΔL).
            %   r = SolicitationsEngine.traction(p)
            %   p : N (N, > 0 traction), S0 (m²), L0 (m), E (Pa), nu (défaut 0,3), alpha (1/°C, 0),
            %       dT (°C, 0), Kt (1), Re (Pa), s (1), dLmax (m, Inf) ; optionnels Sfun(x), Nfun(x),
            %       dTfun(x) (handles vectorisés, x ∈ [0, L0]).
            %   r : sigmaNom, sigmaMax (= Kt·σnom), sigmaAdm (= Re/s), okResistance, epsxx, epsyy,
            %       epszz, dVsurV (= (1−2ν)σ/E + 3αΔT), dL.analytique (N L0/(E S0) + αΔT L0),
            %       dL.integrale (∫ N/(E S) + αΔT dx), dL.energetique (Castigliano ∂U/∂F + thermique),
            %       K (= E S0/L0), U (énergie mécanique), okRigidite, methodUsed, report, latex.
            p = seStruct(p);
            N = seReq(p, 'N');
            S0 = seReqPos(p, 'S0');
            L0 = seReqPos(p, 'L0');
            E = seReqPos(p, 'E');
            nu = seOpt(p, 'nu', 0.3);
            alpha = seOpt(p, 'alpha', 0);
            dT = seOpt(p, 'dT', 0);
            Kt = seOpt(p, 'Kt', 1);
            Re = seReqPos(p, 'Re');
            s = seOpt(p, 's', 1);
            dLmax = seOpt(p, 'dLmax', Inf);
            Nfun = seFun(p, 'Nfun', N);
            Sfun = seFun(p, 'Sfun', S0);
            dTfun = seFun(p, 'dTfun', dT);
            variable = isfield(p, 'Nfun') || isfield(p, 'Sfun') || isfield(p, 'dTfun');

            r = struct();
            r.sigmaNom = N/S0;
            sigWorst = r.sigmaNom;
            if isfield(p, 'Nfun') || isfield(p, 'Sfun')   % section ou effort variables : on vérifie la section la plus chargée
                xs = linspace(0, L0, 201);
                sx = Nfun(xs)./Sfun(xs);
                [~, iw] = max(abs(sx));
                sigWorst = sx(iw);
            end
            r.sigmaMax = Kt*sigWorst;
            r.sigmaAdm = Re/s;
            r.okResistance = abs(r.sigmaMax) <= r.sigmaAdm;
            r.epsxx = r.sigmaNom/E + alpha*dT;
            r.epsyy = -nu*r.sigmaNom/E + alpha*dT;
            r.epszz = r.epsyy;
            r.dVsurV = (1 - 2*nu)*r.sigmaNom/E + 3*alpha*dT;

            % Méthode 1 : analytique (section S0 et effort N constants)
            dL.analytique = N*L0/(E*S0) + alpha*dT*L0;
            % Méthodes 2 et 3 : intégrale et énergétique (Castigliano, F = effort en extrémité)
            fMech = @(x) Nfun(x)./(E*Sfun(x));
            fTh = @(x) alpha*dTfun(x);
            fU = @(x, F) (Nfun(x) + F - N).^2./(2*E*Sfun(x));
            [Imech, Ith, dUdF, U, methodUsed] = seCastigliano(fMech, fTh, fU, L0, N);
            dL.integrale = Imech + Ith;
            dL.energetique = dUdF + Ith;
            r.dL = dL;
            r.K = E*S0/L0;
            r.U = U;
            if variable   % l'analytique (S0, N constants) n'est pas représentative
                r.okRigidite = max(abs([dL.integrale dL.energetique])) <= dLmax;
            else
                r.okRigidite = max(abs([dL.analytique dL.integrale dL.energetique])) <= dLmax;
            end
            r.methodUsed = methodUsed;

            rep = {
                sprintf('Contrainte nominale : σ = N/S0 = %s / %s = %s Pa', seF(N), seF(S0), seF(r.sigmaNom))
                sprintf('Contrainte maximale : σmax = Kt·σ = %s × %s = %s Pa', seF(Kt), seF(sigWorst), seF(r.sigmaMax))
                sprintf('Contrainte admissible : σadm = Re/s = %s Pa → résistance %s', seF(r.sigmaAdm), seOk(r.okResistance))
                sprintf('Déformations : εxx = %s ; εyy = εzz = %s ; ΔV/V0 = %s', seF(r.epsxx), seF(r.epsyy), seF(r.dVsurV))
                sprintf('ΔL analytique (N L0/(E S0) + αΔT L0) = %s m', seF(dL.analytique))
                sprintf('ΔL intégrale (∫ N/(E S) + αΔT dx, %s) = %s m', methodUsed, seF(dL.integrale))
                sprintf('ΔL énergétique (Castigliano ∂U/∂F + thermique, %s) = %s m', methodUsed, seF(dL.energetique))
                sprintf('Raideur K = E S0/L0 = %s N/m ; énergie U = %s J', seF(r.K), seF(U))
                sprintf('Rigidité (|ΔL| ≤ ΔLmax = %s m) : %s', seF(dLmax), seOk(r.okRigidite))};
            if variable
                rep{end+1, 1} = 'Section, effort ou température variables : la méthode analytique utilise S0, N et ΔT constants.';
            end
            r.report = rep;
            r.latex = {
                sprintf('$\\sigma_{xx} = \\frac{N}{S_0} = \\frac{%s}{%s} = %s\\,\\mathrm{Pa}$', seT(N), seT(S0), seT(r.sigmaNom))
                sprintf('$\\sigma_{max} = K_t\\,\\sigma_{nom} = %s \\le \\frac{R_e}{s} = %s$', seT(r.sigmaMax), seT(r.sigmaAdm))
                sprintf('$\\varepsilon_{xx} = \\frac{\\sigma_{xx}}{E} + \\alpha\\,\\Delta T = %s$', seT(r.epsxx))
                sprintf('$\\varepsilon_{yy} = \\varepsilon_{zz} = -\\nu\\,\\frac{\\sigma_{xx}}{E} + \\alpha\\,\\Delta T = %s$', seT(r.epsyy))
                sprintf('$\\frac{\\Delta V}{V_0} = (1-2\\nu)\\,\\frac{\\sigma_{xx}}{E} + 3\\,\\alpha\\,\\Delta T = %s$', seT(r.dVsurV))
                sprintf('$\\Delta L = \\frac{N\\,L_0}{E\\,S_0} + \\alpha\\,\\Delta T\\,L_0 = %s\\,\\mathrm{m}$', seT(dL.analytique))
                sprintf('$\\Delta L = \\int_0^{L_0} \\left( \\frac{N(x)}{E\\,S(x)} + \\alpha\\,\\Delta T(x) \\right) dx = %s\\,\\mathrm{m}$', seT(dL.integrale))
                sprintf('$U = \\int_0^{L_0} \\frac{N^2}{2\\,E\\,S}\\,dx = %s\\,\\mathrm{J}, \\ \\Delta L = \\frac{\\partial U}{\\partial F} + \\alpha\\,\\Delta T\\,L_0 = %s\\,\\mathrm{m}$', seT(U), seT(dL.energetique))
                sprintf('$K = \\frac{E\\,S_0}{L_0} = %s\\,\\mathrm{N/m}$', seT(r.K))};
        end

        %% ============================== Cisaillement ==============================

        function r = shear(p)
            %SHEAR Cisaillement simple : τmoy = T/S, τmax = k·T/S ≤ τe/s, γ = τmoy/G.
            %   r = SolicitationsEngine.shear(p)
            %   p : T (N), S (m²), k (1), Re (Pa) ou tauE (Pa), criterion ('Tresca' | 'VonMises'),
            %       s (1), G (Pa, optionnel).
            %   r : tauMoy, tauMax, tauE, tauAdm, ok, gamma (NaN sans G), report, latex.
            p = seStruct(p);
            T = seReq(p, 'T');
            S = seReqPos(p, 'S');
            k = seOpt(p, 'k', 1);
            s = seOpt(p, 's', 1);
            G = seOpt(p, 'G', NaN);
            [tauE, tauTxt] = seTauE(p);
            r = struct();
            r.tauMoy = T/S;
            r.tauMax = k*T/S;
            r.tauE = tauE;
            r.tauAdm = tauE/s;
            r.ok = abs(r.tauMax) <= r.tauAdm;
            r.gamma = r.tauMoy/G;
            r.report = {
                sprintf('Contrainte moyenne : τmoy = T/S = %s / %s = %s Pa', seF(T), seF(S), seF(r.tauMoy))
                sprintf('Contrainte maximale : τmax = k·T/S = %s Pa (k = %s)', seF(r.tauMax), seF(k))
                sprintf('%s ; τadm = τe/s = %s Pa → %s', tauTxt, seF(r.tauAdm), seOk(r.ok))
                sprintf('Glissement : γ = τmoy/G = %s rad', seF(r.gamma))};
            r.latex = {
                sprintf('$\\tau_{moy} = \\frac{T}{S} = %s\\,\\mathrm{Pa}$', seT(r.tauMoy))
                sprintf('$\\tau_{max} = k\\,\\frac{T}{S} = %s \\le \\frac{\\tau_e}{s} = %s$', seT(r.tauMax), seT(r.tauAdm))
                sprintf('$\\gamma = \\frac{\\tau}{G} = %s\\,\\mathrm{rad}$', seT(r.gamma))};
        end

        function prof = jourawski(sec, T, n)
            %JOURAWSKI Répartition de Jourawski τ(y) = T·Q(y)/(Iz·b(y)) sur la hauteur de la section.
            %   prof = SolicitationsEngine.jourawski(sec, T, n)
            %   sec : section (GeometryEngine) ; T : effort tranchant Ty (N) ; n : nombre de points (201).
            %   prof : y (depuis G, bas → haut), b, Q, tau, tauMax, yAtMax, tauMoy (= T/S),
            %          kNum (= τmax·S/T), tauParabola (rectangle : 1,5 T/S (1 − (2y/h)²), NaN sinon),
            %          Iz, report, latex.
            if nargin < 3 || isempty(n)
                n = 201;
            end
            if ~isnumeric(T) || ~isscalar(T) || ~isfinite(T)
                error('MecaStruct:SolicitationsEngine:invalidInput', 'T doit être un réel fini.');
            end
            P = GeometryEngine.analytical(sec);
            sec = GeometryEngine.validateSection(sec);
            y = linspace(-P.vyBot, P.vyTop, max(3, round(n)));
            b = GeometryEngine.widthAt(sec, y);
            Q = GeometryEngine.firstMomentAbove(sec, y);
            ratio = zeros(size(y));
            in = b > 0;
            ratio(in) = Q(in)./b(in);
            tau = T*ratio/P.Iz;
            [rmax, iMax] = max(ratio);
            prof = struct();
            prof.y = y;
            prof.b = b;
            prof.Q = Q;
            prof.tau = tau;
            prof.tauMax = T*rmax/P.Iz;
            prof.yAtMax = y(iMax);
            prof.tauMoy = T/P.S;
            prof.kNum = rmax*P.S/P.Iz;
            if strcmp(sec.type, 'rectangle')
                prof.tauParabola = 1.5*T/P.S*(1 - (2*y/sec.h).^2);
            else
                prof.tauParabola = NaN(size(y));
            end
            prof.Iz = P.Iz;
            prof.report = {
                sprintf('Jourawski : τ(y) = T·Q(y)/(Iz·b(y)), T = %s N, Iz = %s m⁴', seF(T), seF(P.Iz))
                sprintf('τmax = %s Pa en y = %s m (depuis G) ; τmoy = T/S = %s Pa', seF(prof.tauMax), seF(prof.yAtMax), seF(prof.tauMoy))
                sprintf('Facteur de forme k = τmax·S/T = %s', seF(prof.kNum))};
            prof.latex = {
                '$\tau_{yx}(y) = \frac{T_y}{I_z\,b(y)} \int\!\!\int_{S(y)} \eta\,dS$'
                sprintf('$\\tau_{max} = %s\\,\\mathrm{Pa}, \\ k = \\frac{\\tau_{max}\\,S}{T} = %s$', seT(prof.tauMax), seT(prof.kNum))};
            if strcmp(sec.type, 'rectangle')
                prof.latex{end+1, 1} = '$\tau(y) = \frac{3}{2}\,\frac{T}{S}\left[1 - \left(\frac{2y}{h}\right)^2\right]$';
            end
        end

        %% ================================= Matage =================================

        function r = bearing(p)
            %BEARING Matage : P = F/S_matée ≤ Padm.
            %   r = SolicitationsEngine.bearing(p) ; p : F (N), Smatee (m²), Padm (Pa).
            %   r : P, ok, SminRequired (= F/Padm), report, latex.
            p = seStruct(p);
            F = seReq(p, 'F');
            Sm = seReqPos(p, 'Smatee');
            Padm = seReqPos(p, 'Padm');
            r = struct('P', F/Sm, 'ok', abs(F/Sm) <= Padm, 'SminRequired', abs(F)/Padm);
            r.report = {
                sprintf('Pression de matage : P = F/S = %s / %s = %s Pa', seF(F), seF(Sm), seF(r.P))
                sprintf('Padm = %s Pa → %s ; surface minimale F/Padm = %s m²', seF(Padm), seOk(r.ok), seF(r.SminRequired))};
            r.latex = {sprintf('$P = \\frac{F}{S} = %s \\le P_{adm} = %s\\,\\mathrm{Pa}$', seT(r.P), seT(Padm))};
        end

        function r = keyDesign(p)
            %KEYDESIGN Clavette parallèle : matage P = 4C/(D b L) et cisaillement τ = 2C/(a L D).
            %   r = SolicitationsEngine.keyDesign(p)
            %   p : C (N·m), D (m, diamètre de l'arbre), a (largeur), b (hauteur), Padm (Pa),
            %       Re ou tauE, criterion, s (1), L (m, optionnel).
            %   r : F (= 2C/D), LminMatage (= 4C/(D b Padm)), LminCis (= 2C/(a D τadm)), Lmin,
            %       tauAdm, et si L : P, tau, okP, okTau ; report, latex.
            p = seStruct(p);
            C = abs(seReq(p, 'C'));
            D = seReqPos(p, 'D');
            a = seReqPos(p, 'a');
            b = seReqPos(p, 'b');
            Padm = seReqPos(p, 'Padm');
            s = seOpt(p, 's', 1);
            [tauE, tauTxt] = seTauE(p);
            r = struct();
            r.F = 2*C/D;
            r.tauAdm = tauE/s;
            r.LminMatage = 4*C/(D*b*Padm);
            r.LminCis = 2*C/(a*D*r.tauAdm);
            r.Lmin = max(r.LminMatage, r.LminCis);
            r.report = {
                sprintf('Effort tangentiel sur la clavette : F = 2C/D = %s N', seF(r.F))
                sprintf('Matage (hauteur b/2 en contact) : L ≥ 4C/(D b Padm) = %s m', seF(r.LminMatage))
                sprintf('%s ; cisaillement : L ≥ 2C/(a D τadm) = %s m', tauTxt, seF(r.LminCis))
                sprintf('Longueur minimale : Lmin = %s m', seF(r.Lmin))};
            r.latex = {
                sprintf('$F = \\frac{2\\,C}{D} = %s\\,\\mathrm{N}$', seT(r.F))
                sprintf('$L_{min} = \\frac{4\\,C}{D\\,b\\,P_{adm}} = %s\\,\\mathrm{m}$', seT(r.LminMatage))
                sprintf('$L_{min} = \\frac{2\\,C}{a\\,D\\,\\tau_{adm}} = %s\\,\\mathrm{m}$', seT(r.LminCis))};
            if isfield(p, 'L') && ~isempty(p.L)
                L = seReqPos(p, 'L');
                r.P = 4*C/(D*b*L);
                r.tau = 2*C/(a*L*D);
                r.okP = r.P <= Padm;
                r.okTau = r.tau <= r.tauAdm;
                r.report{end+1, 1} = sprintf('Avec L = %s m : P = %s Pa (%s), τ = %s Pa (%s)', ...
                    seF(L), seF(r.P), seOk(r.okP), seF(r.tau), seOk(r.okTau));
                r.latex{end+1, 1} = sprintf('$P = \\frac{4\\,C}{D\\,b\\,L} = %s, \\ \\tau = \\frac{2\\,C}{a\\,L\\,D} = %s$', seT(r.P), seT(r.tau));
            end
        end

        function r = pinDesign(p)
            %PINDESIGN Goupille / rivet : P = 2F/(d e) ≤ Padm et τ = 4F/(nShear π d²) ≤ τadm.
            %   r = SolicitationsEngine.pinDesign(p)
            %   p : F (N), d (m), e (m, épaisseur matée), Padm (Pa), Re ou tauE, criterion, s (1),
            %       nShear (nombre de sections cisaillées, 1).
            %   r : P, tau, tauAdm, dMin (max des conditions de cisaillement et de matage à e donné),
            %       eMin (= 2F/(d Padm)), okP, okTau, report, latex.
            p = seStruct(p);
            F = abs(seReq(p, 'F'));
            d = seReqPos(p, 'd');
            e = seReqPos(p, 'e');
            Padm = seReqPos(p, 'Padm');
            s = seOpt(p, 's', 1);
            ns = seOpt(p, 'nShear', 1);
            [tauE, tauTxt] = seTauE(p);
            r = struct();
            r.P = 2*F/(d*e);
            r.tau = 4*F/(ns*pi*d^2);
            r.tauAdm = tauE/s;
            r.dMin = max(sqrt(4*F/(ns*pi*r.tauAdm)), 2*F/(e*Padm));
            r.eMin = 2*F/(d*Padm);
            r.okP = r.P <= Padm;
            r.okTau = r.tau <= r.tauAdm;
            r.report = {
                sprintf('Matage (formule du cours) : P = 2F/(d e) = %s Pa ≤ %s → %s', seF(r.P), seF(Padm), seOk(r.okP))
                sprintf('Cisaillement : τ = 4F/(n π d²) = %s Pa (n = %d) ; %s ; τadm = %s → %s', ...
                seF(r.tau), round(ns), tauTxt, seF(r.tauAdm), seOk(r.okTau))
                sprintf('Dimensions minimales : d ≥ %s m ; e ≥ %s m', seF(r.dMin), seF(r.eMin))};
            r.latex = {
                sprintf('$P = \\frac{2\\,F}{d\\,e} = %s \\le P_{adm} = %s$', seT(r.P), seT(Padm))
                sprintf('$\\tau = \\frac{4\\,F}{n\\,\\pi\\,d^2} = %s \\le \\tau_{adm} = %s$', seT(r.tau), seT(r.tauAdm))};
        end

        %% ================================= Torsion =================================

        function r = torsion(p)
            %TORSION Torsion d'un arbre circulaire plein ou creux (3 méthodes pour φ).
            %   r = SolicitationsEngine.torsion(p)
            %   p : Mt (N·m), D (m), d (m, 0), G (Pa), L (m), Kt (1), Re ou tauE, criterion, s (1),
            %       thetaAdm (rad/m, Inf) ; optionnels MtFun(s), IxFun(s) (handles vectorisés).
            %   r : Ix (= π(D⁴ − d⁴)/32), m (= d/D), tauMaxNom (= Mt D/(2 Ix)), tauMax (Kt·), tauAdm,
            %       okResistance, theta (= Mt/(G Ix)), okRigidite, phi.analytique (Mt L/(G Ix)),
            %       phi.integrale (∫ Mt/(G Ix) ds), phi.energetique (∂U/∂C), Ktorsion (= G Ix/L), U,
            %       rProfile, tauProfile (τ(r) = Mt r/Ix), methodUsed, report, latex.
            p = seStruct(p);
            Mt = seReq(p, 'Mt');
            D = seReqPos(p, 'D');
            d = seOpt(p, 'd', 0);
            if d < 0 || d >= D
                error('MecaStruct:SolicitationsEngine:invalidInput', 'Il faut 0 ≤ d < D.');
            end
            G = seReqPos(p, 'G');
            L = seReqPos(p, 'L');
            Kt = seOpt(p, 'Kt', 1);
            s = seOpt(p, 's', 1);
            thetaAdm = seOpt(p, 'thetaAdm', Inf);
            [tauE, tauTxt] = seTauE(p);
            Ix = pi*(D^4 - d^4)/32;
            MtFun = seFun(p, 'MtFun', Mt);
            IxFun = seFun(p, 'IxFun', Ix);
            r = struct();
            r.Ix = Ix;
            r.m = d/D;
            r.tauMaxNom = Mt*D/(2*Ix);
            r.tauMax = Kt*r.tauMaxNom;
            r.tauAdm = tauE/s;
            r.okResistance = abs(r.tauMax) <= r.tauAdm;
            r.theta = Mt/(G*Ix);
            r.okRigidite = abs(r.theta) <= thetaAdm;
            phi.analytique = Mt*L/(G*Ix);
            fInt = @(x) MtFun(x)./(G*IxFun(x));
            fU = @(x, C) (MtFun(x) + C - Mt).^2./(2*G*IxFun(x));
            [phiInt, ~, dUdC, U, methodUsed] = seCastigliano(fInt, [], fU, L, Mt);
            phi.integrale = phiInt;
            phi.energetique = dUdC;
            r.phi = phi;
            r.Ktorsion = G*Ix/L;
            r.U = U;
            r.rProfile = linspace(d/2, D/2, 101);
            r.tauProfile = Mt*r.rProfile/Ix;
            r.methodUsed = methodUsed;
            r.report = {
                sprintf('Moment quadratique polaire : Ix = π(D⁴ − d⁴)/32 = %s m⁴ (m = d/D = %s)', seF(Ix), seF(r.m))
                sprintf('τmax nominale = Mt·(D/2)/Ix = %s Pa ; avec Kt = %s : %s Pa', seF(r.tauMaxNom), seF(Kt), seF(r.tauMax))
                sprintf('%s ; τadm = %s Pa → résistance %s', tauTxt, seF(r.tauAdm), seOk(r.okResistance))
                sprintf('Angle unitaire θ = Mt/(G Ix) = %s rad/m → rigidité %s', seF(r.theta), seOk(r.okRigidite))
                sprintf('φ analytique (Mt L/(G Ix)) = %s rad', seF(phi.analytique))
                sprintf('φ intégrale (∫ Mt/(G Ix) ds, %s) = %s rad', methodUsed, seF(phi.integrale))
                sprintf('φ énergétique (∂U/∂C, %s) = %s rad', methodUsed, seF(phi.energetique))
                sprintf('Raideur K = G Ix/L = %s N·m/rad ; U = %s J', seF(r.Ktorsion), seF(U))};
            r.latex = {
                sprintf('$I_x = \\frac{\\pi\\,(D^4 - d^4)}{32} = %s\\,\\mathrm{m^4}$', seT(Ix))
                sprintf('$\\tau(r) = \\frac{M_t\\,r}{I_x}, \\ \\tau_{max} = K_t\\,\\frac{M_t}{I_x}\\,\\frac{D}{2} = %s\\,\\mathrm{Pa}$', seT(r.tauMax))
                sprintf('$\\theta = \\frac{d\\varphi}{ds} = \\frac{M_t}{G\\,I_x} = %s\\,\\mathrm{rad/m}$', seT(r.theta))
                sprintf('$\\varphi = \\frac{M_t\\,L}{G\\,I_x} = %s\\,\\mathrm{rad}$', seT(phi.analytique))
                sprintf('$\\varphi = \\int_0^L \\frac{M_t}{G\\,I_x}\\,ds = %s\\,\\mathrm{rad}$', seT(phi.integrale))
                sprintf('$U = \\int_0^L \\frac{M_t^2}{2\\,G\\,I_x}\\,ds = %s\\,\\mathrm{J}, \\ \\varphi = \\frac{\\partial U}{\\partial C} = %s$', seT(U), seT(phi.energetique))};
        end

        %% ============================ Flexion : contraintes ============================

        function r = bendingStress(p)
            %BENDINGSTRESS Contraintes normales de flexion composée / déviée dans une section.
            %   r = SolicitationsEngine.bendingStress(p)
            %   p : sec (section GeometryEngine) ou P (propriétés : S, Iz, Iy, Iyz, vyTop, vyBot,
            %       vzRight, vzLeft), N (0), Mfz (0), Mfy (0) (N, N·m), Kt (1), Re, s (1).
            %   σ(y, z) = N/S − Mfz·y/Iz + Mfy·z/Iy (axes principaux) ; si |Iyz| non négligeable :
            %   σ = N/S + b·y + c·z avec [Iz Iyz; Iyz Iy]·[b; c] = [−Mfz; Mfy].
            %   r : sigmaFun (@(y,z), depuis G), sigmaMaxTraction, sigmaMaxCompression,
            %       locMaxTraction, locMaxCompression ([y z]), sigmaMaxAbs, sigmaMaxKt, sigmaAdm, ok,
            %       neutralAxis (a, b, c, points 2×2 [y z]), usedGeneralFormula, yProfile,
            %       sigmaProfile (z = 0), coefs [a b c], report, latex.
            %   Extrema : sommets du contour (GeometryEngine.outline) ; sans sec, coins du rectangle
            %   englobant (exact pour un rectangle, majorant sinon).
            p = seStruct(p);
            N = seOpt(p, 'N', 0);
            Mfz = seOpt(p, 'Mfz', 0);
            Mfy = seOpt(p, 'Mfy', 0);
            Kt = seOpt(p, 'Kt', 1);
            Re = seReqPos(p, 'Re');
            s = seOpt(p, 's', 1);
            hasSec = isfield(p, 'sec') && ~isempty(p.sec);
            if hasSec
                P = GeometryEngine.analytical(p.sec);
            elseif isfield(p, 'P') && ~isempty(p.P)
                P = p.P;
            else
                error('MecaStruct:SolicitationsEngine:missingField', 'Il faut fournir p.sec ou p.P.');
            end
            Iyz = 0;
            if isfield(P, 'Iyz') && ~isempty(P.Iyz)
                Iyz = P.Iyz;
            end
            general = abs(Iyz) > 1e-9*sqrt(P.Iz*P.Iy);
            a = N/P.S;
            if general
                bc = [P.Iz Iyz; Iyz P.Iy] \ [-Mfz; Mfy];
                b = bc(1);
                c = bc(2);
            else
                b = -Mfz/P.Iz;
                c = Mfy/P.Iy;
            end
            sig = @(y, z) a + b*y + c*z;
            % Points candidats [y z] depuis G
            if hasSec
                sec = GeometryEngine.validateSection(p.sec);
                out = GeometryEngine.outline(sec);
                V = vertcat(out.outer{:}, out.holes{:});
                pts = [V(:, 2) - P.yG, V(:, 1) - P.zG];
                if any(strcmp(sec.type, {'disque', 'couronne'})) && hypot(b, c) > 0
                    u = [b c]/hypot(b, c);
                    pts = [pts; sec.D/2*u; -sec.D/2*u];
                end
            else
                [Y, Z] = ndgrid([P.vyTop, -P.vyBot], [P.vzRight, -P.vzLeft]);
                pts = [Y(:) Z(:)];
            end
            sv = sig(pts(:, 1), pts(:, 2));
            [smax, iMax] = max(sv);
            [smin, iMin] = min(sv);
            r = struct();
            r.sigmaFun = sig;
            r.coefs = [a b c];
            r.sigmaMaxTraction = smax;
            r.sigmaMaxCompression = smin;
            r.locMaxTraction = pts(iMax, :);
            r.locMaxCompression = pts(iMin, :);
            r.sigmaMaxAbs = max(abs([smax smin]));
            r.sigmaMaxKt = Kt*r.sigmaMaxAbs;
            r.sigmaAdm = Re/s;
            r.ok = r.sigmaMaxKt <= r.sigmaAdm;
            % Axe neutre a + b y + c z = 0
            na = struct('a', a, 'b', b, 'c', c, 'points', NaN(2, 2));
            yE = max(P.vyTop, P.vyBot);
            zE = max(P.vzRight, P.vzLeft);
            if abs(b)*yE >= abs(c)*zE && b ~= 0
                zz = [-zE; zE];
                na.points = [-(a + c*zz)/b, zz];
            elseif c ~= 0
                yy = [-yE; yE];
                na.points = [yy, -(a + b*yy)/c];
            end
            r.neutralAxis = na;
            r.usedGeneralFormula = general;
            r.yProfile = linspace(-P.vyBot, P.vyTop, 101);
            r.sigmaProfile = sig(r.yProfile, 0);
            if general
                ftxt = 'Formule générale (Iyz non négligeable) : σ = N/S + b·y + c·z, [Iz Iyz; Iyz Iy]·[b; c] = [−Mfz; Mfy]';
            else
                ftxt = 'Axes principaux : σ = N/S − Mfz·y/Iz + Mfy·z/Iy';
            end
            r.report = {
                ftxt
                sprintf('σ(y, z) = %s %s·y %s·z (Pa, y et z en m depuis G)', seF(a), seSgn(b), seSgn(c))
                sprintf('Traction maximale : %s Pa en (y, z) = (%s, %s) m', seF(smax), seF(r.locMaxTraction(1)), seF(r.locMaxTraction(2)))
                sprintf('Compression maximale : %s Pa en (y, z) = (%s, %s) m', seF(smin), seF(r.locMaxCompression(1)), seF(r.locMaxCompression(2)))
                sprintf('|σ|max = %s Pa ; Kt·|σ|max = %s Pa ; σadm = Re/s = %s Pa → %s', ...
                seF(r.sigmaMaxAbs), seF(r.sigmaMaxKt), seF(r.sigmaAdm), seOk(r.ok))
                sprintf('Axe neutre : %s %s·y %s·z = 0', seF(a), seSgn(b), seSgn(c))};
            if general
                f1 = sprintf('$\\sigma_{xx} = \\frac{N}{S} + b\\,y + c\\,z, \\ \\left[\\begin{array}{cc} I_z & I_{yz} \\\\ I_{yz} & I_y \\end{array}\\right] \\left[\\begin{array}{c} b \\\\ c \\end{array}\\right] = \\left[\\begin{array}{c} -M_{fz} \\\\ M_{fy} \\end{array}\\right]$');
            else
                f1 = '$\sigma_{xx} = \frac{N}{S} - \frac{M_{fz}}{I_z}\,y + \frac{M_{fy}}{I_y}\,z$';
            end
            r.latex = {
                f1
                sprintf('$\\sigma_{xx}(y,z) = %s %s\\,y %s\\,z$', seT(a), seTs(b), seTs(c))
                sprintf('$\\sigma_{max} = %s, \\ \\sigma_{min} = %s\\,\\mathrm{Pa}$', seT(smax), seT(smin))
                sprintf('$K_t\\,|\\sigma|_{max} = %s \\le \\frac{R_e}{s} = %s$', seT(r.sigmaMaxKt), seT(r.sigmaAdm))};
        end

        %% ============================ Flexion : déformée ============================

        function d = deflection(model, sol, opts)
            %DEFLECTION Déformée d'une poutre par 4 méthodes (intégration, aires, Castigliano, Mohr).
            %   d = SolicitationsEngine.deflection(model, sol, opts)
            %   model : modèle de poutre (BeamAndTrussSolver) ; sol : solution de solveBeam (calculée
            %   si vide).
            %   opts : plane ('xy' : E Iz v'' = Mfz | 'xz' : E Iy w'' = −Mfy), nPoints (201),
            %          nCastigliano (41), includeShear (true), methods (défaut
            %          {'integration','aires','castigliano','mohr'}), s0 (points d'intérêt ; défaut :
            %          flèche max (intégration), milieux des travées, extrémités libres).
            %   d : s, plane, integration (v, alpha, vPP, alphaPP, constants, equations, fmax,
            %       sAtFmax, residual : résidu des moindres carrés rapporté à max|M|·L²), aires (v, alpha, areas, alpha0, v0, fmax, sAtFmax, residual),
            %       castigliano (s0, vBending, vShear, vTotal, alpha, fmax, sAtFmax, fmaxBending,
            %       sAtFmaxBending), mohr (s0, v, details), comparison (table Methode, fmax_m, s_m,
            %       Ecart_pct), report, latex.
            %   fmax = |v| maximal (m), positif.
            if nargin < 3
                opts = struct();
            end
            if nargin < 2 || isempty(sol)
                sol = BeamAndTrussSolver.solveBeam(model, seFastOpts());
            end
            o = seDeflOpts(opts);
            m = sol.model;
            L = m.L;
            [Mz, My] = seBendMoments(sol, m);
            switch o.plane
                case 'xy'
                    M = Mz; T = sol.Ty; EI = m.E*m.Iz; kGS = m.ky*m.G*m.S;
                    vn = 'v'; It = 'I_z';
                otherwise
                    M = BeamAndTrussSolver.ppScale(My, -1); T = sol.Tz; EI = m.E*m.Iy; kGS = m.kz*m.G*m.S;
                    vn = 'w'; It = 'I_y';
            end
            conds = seConditions(m.supports);
            d = struct();
            d.s = unique([linspace(0, L, o.nPoints), M.breaks]);
            d.plane = o.plane;

            % --- 1. Intégration tronçon par tronçon (toujours calculée : sert aux points s0)
            I = seIntegration(M, EI, conds);
            sAll = d.s;
            I.v = BeamAndTrussSolver.ppEval(I.vPP, sAll);
            I.alpha = BeamAndTrussSolver.ppEval(I.alphaPP, sAll);
            [I.fmax, I.sAtFmax] = sePPMaxAbs(I.vPP, I.alphaPP);
            for k = 1:numel(I.equations)
                I.equations{k} = strrep(strrep(I.equations{k}, '@V', vn), '@I', It);
            end
            if isempty(o.s0)
                s0 = seDefaultS0(m.supports, L, I.sAtFmax);
            else
                s0 = unique(min(max(o.s0(:).', 0), L));
            end
            rows = {};
            if ismember('integration', o.methods)
                d.integration = I;
                rows(end+1, :) = {"Intégration", I.fmax, I.sAtFmax};
            end

            % --- 2. Aires et moments des aires
            if ismember('aires', o.methods)
                A = seAires(M, EI, conds, sAll);
                d.aires = A;
                rows(end+1, :) = {"Aires", A.fmax, A.sAtFmax};
            end

            % --- 3. Castigliano / forces unités (solveBeam sous charge unité)
            cache = struct('s', {}, 'mb', {}, 'tb', {});
            if ismember('castigliano', o.methods)
                sC = unique([linspace(0, L, o.nCastigliano), s0]);
                nC = numel(sC);
                vB = zeros(1, nC); vS = zeros(1, nC); al = zeros(1, nC);
                for i = 1:nC
                    [mb, tb] = seUnitSolve(m, sC(i), 'force', o.plane);
                    [mc, ~] = seUnitSolve(m, sC(i), 'couple', o.plane);
                    cache(end+1) = struct('s', sC(i), 'mb', mb, 'tb', tb); %#ok<AGROW>
                    vB(i) = seIntProd(M, mb)/EI;
                    if o.includeShear
                        vS(i) = seIntProd(T, tb)/kGS;
                    end
                    al(i) = seIntProd(M, mc)/EI;
                end
                Cg = struct('s0', sC, 'vBending', vB, 'vShear', vS, 'vTotal', vB + vS, 'alpha', al);
                [Cg.fmax, iT] = max(abs(Cg.vTotal));
                Cg.sAtFmax = sC(iT);
                [Cg.fmaxBending, iB] = max(abs(vB));
                Cg.sAtFmaxBending = sC(iB);
                d.castigliano = Cg;
                rows(end+1, :) = {"Castigliano (flexion)", Cg.fmaxBending, Cg.sAtFmaxBending};
                if o.includeShear
                    rows(end+1, :) = {"Castigliano (flexion + tranchant)", Cg.fmax, Cg.sAtFmax};
                end
            end

            % --- 4. Intégrales de Mohr (tabulées) avec le diagramme unité
            if ismember('mohr', o.methods)
                nM = numel(s0);
                vM = zeros(1, nM);
                det = cell(1, nM);
                for i = 1:nM
                    j = find([cache.s] == s0(i), 1);
                    if isempty(j)
                        mb = seUnitSolve(m, s0(i), 'force', o.plane);
                    else
                        mb = cache(j).mb;
                    end
                    mi = SolicitationsEngine.mohrIntegral(M, mb, 0, L);
                    vM(i) = mi.valueTable/EI;
                    det{i} = mi.segments;
                end
                Mo = struct('s0', s0, 'v', vM, 'details', {det});
                [fM, iM] = max(abs(vM));
                Mo.fmax = fM;
                Mo.sAtFmax = s0(iM);
                d.mohr = Mo;
                rows(end+1, :) = {"Mohr (tabulé)", fM, s0(iM)};
            end

            % --- Comparaison
            fref = I.fmax;
            ec = zeros(size(rows, 1), 1);
            for k = 1:size(rows, 1)
                if fref > 0
                    ec(k) = 100*(rows{k, 2} - fref)/fref;
                end
            end
            d.comparison = table(vertcat(rows{:, 1}), cell2mat(rows(:, 2)), cell2mat(rows(:, 3)), ec, ...
                'VariableNames', {'Methode', 'fmax_m', 's_m', 'Ecart_pct'});

            rep = {sprintf('Plan (%s) : E·%s·%s'''' = %s, E·%s = %s N·m²', o.plane, strrep(It, '_', ''), vn, ...
                seIf(strcmp(o.plane, 'xy'), 'Mfz', '−Mfy'), strrep(It, '_', ''), seF(EI))};
            if seIyz(m) ~= 0
                rep{end+1, 1} = sprintf(['Flexion déviée (Iyz = %s m⁴) : courbures couplées, [v''''; −w''''] = [Iz −Iyz; −Iyz Iy]⁻¹·[Mfz; Mfy]/E ; ' ...
                    'le moment ci-dessus est le moment équivalent %s = %s·E·%s''''.'], seF(seIyz(m)), ...
                    seIf(strcmp(o.plane, 'xy'), 'Mz,eq', '−My,eq'), strrep(It, '_', ''), vn);
                if ~sol.isostatic
                    rep{end+1, 1} = ['Attention : poutre hyperstatique avec Iyz ≠ 0. Les réactions sont calculées plan par plan ' ...
                        '(couplage y–z des inconnues hyperstatiques négligé) : saisir la section dans ses axes principaux pour un calcul exact.'];
                end
            end
            rep{end+1, 1} = sprintf('Intégration : %d tronçons, %d constantes, résidu relatif %s ; flèche max %s m en s = %s m', ...
                numel(M.breaks) - 1, 2*(numel(M.breaks) - 1), seF(I.residual), seF(I.fmax), seF(I.sAtFmax));
            if isfield(d, 'aires')
                rep{end+1, 1} = sprintf('Aires : α0 = %s rad, %s0 = %s m ; flèche max %s m en s = %s m', ...
                    seF(d.aires.alpha0), vn, seF(d.aires.v0), seF(d.aires.fmax), seF(d.aires.sAtFmax));
            end
            if isfield(d, 'castigliano')
                rep{end+1, 1} = sprintf('Castigliano (forces unités, %d points) : flexion %s m, avec tranchant %s m', ...
                    numel(d.castigliano.s0), seF(d.castigliano.fmaxBending), seF(d.castigliano.fmax));
            end
            if isfield(d, 'mohr')
                for i = 1:numel(d.mohr.s0)
                    rep{end+1, 1} = sprintf('Mohr : %s(%s m) = %s m', vn, seF(d.mohr.s0(i)), seF(d.mohr.v(i))); %#ok<AGROW>
                end
            end
            for k = 1:height(d.comparison)
                rep{end+1, 1} = sprintf('%s : f = %s m en s = %s m (écart %s %%)', d.comparison.Methode(k), ...
                    seF(d.comparison.fmax_m(k)), seF(d.comparison.s_m(k)), seF(d.comparison.Ecart_pct(k))); %#ok<AGROW>
            end
            d.report = rep;
            Mt = seIf(strcmp(o.plane, 'xy'), 'M_{fz}', '-M_{fy}');
            d.latex = [{
                sprintf('$E\\,%s\\,%s''''(s) = %s(s)$', It, vn, Mt)
                sprintf('$\\alpha(s) = \\alpha_0 + \\frac{1}{E\\,%s} \\int_0^s M\\,ds, \\ %s(s) = %s_0 + \\alpha_0\\,s + \\frac{1}{E\\,%s} \\sum_k A_k\\,(s - \\overline{s}_k)$', It, vn, vn, It)
                sprintf('$%s(s_0) = \\int_0^L \\frac{M\\,\\overline{m}}{E\\,%s}\\,ds + \\int_0^L \\frac{T\\,\\overline{t}}{k\\,G\\,S}\\,ds$', vn, It)
                sprintf('$f = |%s|_{max} = %s\\,\\mathrm{m} \\ (s = %s\\,\\mathrm{m})$', vn, seT(I.fmax), seT(I.sAtFmax))}; I.equations(:)];
        end

        %% ============================ Énergie, Mohr, flambage ============================

        function U = strainEnergy(model, sol)
            %STRAINENERGY Énergie de déformation élastique (6 termes, intégration exacte des pp).
            %   U = SolicitationsEngine.strainEnergy(model, sol)
            %   U = ∫ (N²/(2ES) + Ty²/(2 ky G S) + Tz²/(2 kz G S) + Mt²/(2 G Ix) + Mfy²/(2 E Iy)
            %         + Mfz²/(2 E Iz)) ds.
            %   model : propriétés (E, G, S, Iz, Iy, Ix, ky, kz) prioritaires sur sol.model si fournies ;
            %   sol : solution de solveBeam (calculée si vide).
            %   U : UN, UTy, UTz, UMt, UMfy, UMfz, total (J), report, latex.
            if nargin < 2 || isempty(sol)
                sol = BeamAndTrussSolver.solveBeam(model, seFastOpts());
            end
            m = sol.model;
            if isstruct(model)
                for f = {'E', 'G', 'S', 'Iz', 'Iy', 'Ix', 'ky', 'kz', 'Iyz'}
                    if isfield(model, f{1}) && ~isempty(model.(f{1}))
                        m.(f{1}) = model.(f{1});
                    end
                end
            end
            q = @(pp, k) seIntProd(pp, pp)/(2*k);
            [Mz, My] = seBendMoments(sol, m);   % moments équivalents (égaux à Mfz, Mfy si Iyz = 0)
            U = struct();
            U.UN = q(sol.N, m.E*m.S);
            U.UTy = q(sol.Ty, m.ky*m.G*m.S);
            U.UTz = q(sol.Tz, m.kz*m.G*m.S);
            U.UMt = q(sol.Mt, m.G*m.Ix);
            U.UMfy = seIntProd(sol.Mfy, My)/(2*m.E*m.Iy);
            U.UMfz = seIntProd(sol.Mfz, Mz)/(2*m.E*m.Iz);
            U.total = U.UN + U.UTy + U.UTz + U.UMt + U.UMfy + U.UMfz;
            U.report = {
                sprintf('Effort normal : UN = %s J', seF(U.UN))
                sprintf('Tranchant : UTy = %s J ; UTz = %s J', seF(U.UTy), seF(U.UTz))
                sprintf('Torsion : UMt = %s J', seF(U.UMt))
                sprintf('Flexion : UMfy = %s J ; UMfz = %s J', seF(U.UMfy), seF(U.UMfz))
                sprintf('Énergie totale : U = %s J', seF(U.total))};
            U.latex = {
                '$U = \int_0^L \left( \frac{N^2}{2ES} + \frac{T_y^2}{2k_yGS} + \frac{T_z^2}{2k_zGS} + \frac{M_t^2}{2GI_x} + \frac{M_{fy}^2}{2EI_y} + \frac{M_{fz}^2}{2EI_z} \right) ds$'
                sprintf('$U = %s\\,\\mathrm{J}$', seT(U.total))};
        end

        function M = mohrIntegral(ppA, ppB, a, b)
            %MOHRINTEGRAL Intégrale de Mohr ∫_a^b MA·MB ds, exacte et par la table (formes élémentaires).
            %   M = SolicitationsEngine.mohrIntegral(ppA, ppB, a, b)  (a, b : défaut bornes de ppA)
            %   Chaque tronçon est décomposé en trapèze (rectangle / triangle / triangle inversé /
            %   trapèze) + parabole (degré ≤ 2) et les produits sont lus dans DataManager.mohrTable ;
            %   au-delà du degré 2, quadrature de Gauss exacte (« hors table »).
            %   M : value (exacte, ppIntegral), valueTable (somme des tronçons), segments (table s1, s2,
            %       shapeA, shapeB, formulaLatex, value, tabulated), allTabulated, report, latex.
            if nargin < 3 || isempty(a)
                a = ppA.breaks(1);
            end
            if nargin < 4 || isempty(b)
                b = ppA.breaks(end);
            end
            if ~(b > a)
                error('MecaStruct:SolicitationsEngine:invalidInput', 'mohrIntegral : il faut a < b.');
            end
            prod = BeamAndTrussSolver.ppMultiply(ppA, ppB);
            M = struct();
            M.value = BeamAndTrussSolver.ppIntegral(prod, a, b);
            br = prod.breaks;
            tolB = 1e-12*max(abs([a b br]));
            br = unique([a, br(br > a + tolB & br < b - tolB), b]);
            Ra = BeamAndTrussSolver.ppRefine(ppA, br);
            Rb = BeamAndTrussSolver.ppRefine(ppB, br);
            tab = DataManager.mohrTable();
            ids = {tab.id};
            n = numel(br) - 1;
            s1 = br(1:n).'; s2 = br(2:n+1).';
            shA = strings(n, 1); shB = strings(n, 1); fl = strings(n, 1);
            val = zeros(n, 1); tb = false(n, 1);
            for k = 1:n
                ca = seCoefAt(Ra, (s1(k) + s2(k))/2);
                cb = seCoefAt(Rb, (s1(k) + s2(k))/2);
                [pa, okA, dA] = seDecompose(ca, s1(k), s2(k));
                [pb, okB, dB] = seDecompose(cb, s1(k), s2(k));
                shA(k) = seShapeName(pa, okA);
                shB(k) = seShapeName(pb, okB);
                l = s2(k) - s1(k);
                if okA && okB
                    tb(k) = true;
                    terms = {};
                    for i = 1:numel(pa)
                        for j = 1:numel(pb)
                            e = tab(strcmp(ids, [pa(i).shape '_x_' pb(j).shape]));
                            val(k) = val(k) + e.fun(l, pa(i).vals, pb(j).vals);
                            terms{end+1} = seMohrTex(e.latex, l, pa(i).vals, pb(j).vals); %#ok<AGROW>
                        end
                    end
                    if isempty(terms)
                        fl(k) = "$0$";
                    else
                        fl(k) = string(['$' strjoin(terms, ' + ') ' = ' seT(val(k)) '$']);
                    end
                else
                    ng = ceil((dA + dB + 1)/2) + 1;
                    [x, w] = seGauss(ng);
                    sg = (s1(k) + s2(k))/2 + l/2*x;
                    val(k) = l/2*sum(w.*polyval(ca, sg).*polyval(cb, sg));
                    fl(k) = string(sprintf('$\\int_{%s}^{%s} M_A\\,M_B\\,ds = \\frac{l}{2}\\sum_{i=1}^{%d} w_i\\,M_A\\,M_B = %s$', ...
                        seT(s1(k)), seT(s2(k)), ng, seT(val(k))));
                end
            end
            M.valueTable = sum(val);
            M.segments = table(s1, s2, shA, shB, fl, val, tb, 'VariableNames', ...
                {'s1', 's2', 'shapeA', 'shapeB', 'formulaLatex', 'value', 'tabulated'});
            M.allTabulated = all(tb);
            M.report = {
                sprintf('Intégrale de Mohr sur [%s, %s] m : %d tronçon(s)', seF(a), seF(b), n)
                sprintf('Valeur par la table : %s ; valeur exacte : %s', seF(M.valueTable), seF(M.value))
                seIf(M.allTabulated, 'Tous les tronçons sont tabulés.', 'Certains tronçons (degré > 2) sont calculés par Gauss (hors table).')};
            M.latex = {sprintf('$\\int_{%s}^{%s} M_A\\,M_B\\,ds = %s$', seT(a), seT(b), seT(M.value))};
        end

        function b = buckling(p)
            %BUCKLING Flambage : délégation à BucklingEngine.analyze(p).
            %   b = SolicitationsEngine.buckling(p) — voir BucklingEngine.analyze.
            b = BucklingEngine.analyze(p);
        end
    end
end

%% =====================================================================
%%                          FONCTIONS LOCALES
%% =====================================================================

function p = seStruct(p)
% Contrôle de la structure de paramètres.
if ~isstruct(p) || ~isscalar(p)
    error('MecaStruct:SolicitationsEngine:invalidInput', 'Les paramètres doivent être une structure scalaire.');
end
end

function v = seReq(p, f)
% Champ numérique scalaire obligatoire.
if ~isfield(p, f) || isempty(p.(f))
    error('MecaStruct:SolicitationsEngine:missingField', 'Champ obligatoire manquant : %s.', f);
end
v = p.(f);
if ~isnumeric(v) || ~isscalar(v) || ~isreal(v) || isnan(v)
    error('MecaStruct:SolicitationsEngine:invalidInput', 'Le champ %s doit être un réel scalaire.', f);
end
v = double(v);
end

function v = seReqPos(p, f)
% Champ obligatoire strictement positif.
v = seReq(p, f);
if ~(v > 0)
    error('MecaStruct:SolicitationsEngine:invalidInput', 'Le champ %s doit être strictement positif.', f);
end
end

function v = seOpt(p, f, def)
% Champ numérique optionnel.
if isfield(p, f) && ~isempty(p.(f))
    v = seReq(p, f);
else
    v = def;
end
end

function fh = seFun(p, f, c)
% Handle optionnel ; à défaut, fonction constante (compatible sym).
if isfield(p, f) && ~isempty(p.(f))
    if ~isa(p.(f), 'function_handle')
        error('MecaStruct:SolicitationsEngine:invalidInput', '%s doit être un handle de fonction.', f);
    end
    fh = p.(f);
else
    fh = @(x) c + 0*x;
end
end

function [tauE, txt] = seTauE(p)
% Résistance élastique au glissement τe.
if isfield(p, 'tauE') && ~isempty(p.tauE)
    tauE = seReqPos(p, 'tauE');
    txt = sprintf('τe fourni = %s Pa', seF(tauE));
    return
end
Re = seReqPos(p, 'Re');
crit = 'tresca';
if isfield(p, 'criterion') && ~isempty(p.criterion)
    crit = lower(strrep(char(p.criterion), ' ', ''));
end
switch crit
    case 'tresca'
        tauE = Re/2;
        txt = sprintf('τe = Re/2 = %s Pa (Tresca)', seF(tauE));
    case {'vonmises', 'von_mises'}
        tauE = Re/sqrt(3);
        txt = sprintf('τe = Re/√3 = %s Pa (Von Mises)', seF(tauE));
    otherwise
        error('MecaStruct:SolicitationsEngine:invalidInput', 'criterion doit valoir ''Tresca'' ou ''VonMises''.');
end
end

function [Imain, Ith, dUdF, U, methodUsed] = seCastigliano(fMain, fTh, fU, L, F0)
% Intégrale ∫_0^L fMain, intégrale thermique ∫ fTh, énergie U(F) = ∫ fU(x, F) et ∂U/∂F en F0.
% Symbolique (int, diff) si les handles acceptent des sym, sinon integral + différence centrée
% (exacte : U est quadratique en F).
Ith = 0;
if BeamAndTrussSolver.hasSymbolic()
    try
        x = sym('x', 'real');
        F = sym('F', 'real');
        Imain = double(int(fMain(x), x, 0, L));
        if ~isempty(fTh)
            Ith = double(int(fTh(x), x, 0, L));
        end
        Us = int(fU(x, F), x, 0, L);
        dUdF = double(subs(diff(Us, F), F, F0));
        U = double(subs(Us, F, F0));
        if all(isfinite([Imain Ith dUdF U]))
            methodUsed = 'symbolique';
            return
        end
    catch
        % repli numérique ci-dessous
    end
end
q = @(f) integral(f, 0, L, 'RelTol', 1e-13, 'AbsTol', 0);
Imain = q(fMain);
if ~isempty(fTh)
    Ith = q(fTh);
end
h = max(abs(F0), 1);
U = q(@(x) fU(x, F0));
dUdF = (q(@(x) fU(x, F0 + h)) - q(@(x) fU(x, F0 - h)))/(2*h);
methodUsed = 'numérique';
end

function o = seFastOpts()
% Chemin rapide de solveBeam pour les appels internes.
o = struct('internalMethod', 'coupures', 'hyperMethod', 'menabrea', 'useSymbolic', false);
end

function o = seDeflOpts(opts)
% Options de deflection.
o = struct('plane', 'xy', 'nPoints', 201, 'nCastigliano', 41, 'includeShear', true, ...
    'methods', {{'integration', 'aires', 'castigliano', 'mohr'}}, 's0', []);
if isempty(opts)
    return
end
if ~isstruct(opts) || ~isscalar(opts)
    error('MecaStruct:SolicitationsEngine:invalidInput', 'opts doit être une structure scalaire.');
end
for f = fieldnames(o).'
    if isfield(opts, f{1}) && ~isempty(opts.(f{1}))
        o.(f{1}) = opts.(f{1});
    end
end
o.plane = lower(char(o.plane));
if ~ismember(o.plane, {'xy', 'xz'})
    error('MecaStruct:SolicitationsEngine:invalidInput', 'opts.plane doit valoir ''xy'' ou ''xz''.');
end
o.methods = cellstr(o.methods);
bad = setdiff(o.methods, {'integration', 'aires', 'castigliano', 'mohr'});
if ~isempty(bad)
    error('MecaStruct:SolicitationsEngine:invalidInput', 'Méthode de déformée inconnue : %s.', bad{1});
end
o.nPoints = max(2, round(o.nPoints));
o.nCastigliano = max(2, round(o.nCastigliano));
o.includeShear = logical(o.includeShear);
end

function c = seConditions(sup)
% Conditions cinématiques [pos, type] : type 0 = déplacement nul, 1 = rotation nulle.
c = zeros(0, 2);
for i = 1:numel(sup)
    c(end+1, :) = [sup(i).pos 0]; %#ok<AGROW>
    if strcmp(sup(i).type, 'encastrement')
        c(end+1, :) = [sup(i).pos 1]; %#ok<AGROW>
    end
end
end

function k = seSeg(br, s)
% Indice du tronçon contenant s.
k = find(br(1:end-1) <= s, 1, 'last');
if isempty(k)
    k = 1;
end
k = min(k, numel(br) - 1);
end

function c = sePolyAdd(a, b)
% Somme de deux vecteurs de coefficients (ordre polyval).
n = max(numel(a), numel(b));
c = [zeros(1, n - numel(a)) a] + [zeros(1, n - numel(b)) b];
end

function I = seIntegration(M, EI, conds)
% Double intégration tronçon par tronçon : E I v_k = P_k(s) + C1k s + C2k (2n constantes).
br = M.breaks;
n = numel(br) - 1;
P1 = cell(1, n); P2 = cell(1, n);
for k = 1:n
    P1{k} = polyint(M.coefs{k});
    P2{k} = polyint(P1{k});
end
A = zeros(0, 2*n); b = zeros(0, 1);
for j = 1:n-1
    sb = br(j+1);
    row = zeros(1, 2*n); row(2*j-1:2*j) = [sb 1]; row(2*j+1:2*j+2) = -[sb 1];
    A(end+1, :) = row; b(end+1, 1) = polyval(P2{j+1}, sb) - polyval(P2{j}, sb); %#ok<AGROW>
    row = zeros(1, 2*n); row(2*j-1) = 1; row(2*j+1) = -1;
    A(end+1, :) = row; b(end+1, 1) = polyval(P1{j+1}, sb) - polyval(P1{j}, sb); %#ok<AGROW>
end
for i = 1:size(conds, 1)
    sp = conds(i, 1);
    k = seSeg(br, sp);
    row = zeros(1, 2*n);
    if conds(i, 2) == 0
        row(2*k-1:2*k) = [sp 1];
        rhs = -polyval(P2{k}, sp);
    else
        row(2*k-1) = 1;
        rhs = -polyval(P1{k}, sp);
    end
    A(end+1, :) = row; b(end+1, 1) = rhs; %#ok<AGROW>
end
x = lsqminnorm(A, b);
I = struct();
% Résidu rapporté à l'échelle de E I v (max|M|·L²) : b peut être nul en hyperstatique compatible
Ls = br(end) - br(1);
scale = max(abs(BeamAndTrussSolver.ppEval(M, linspace(br(1), br(end), 201))))*Ls^2;
I.residual = norm(A*x - b)/max(scale, realmin);
cv = cell(1, n); eq = cell(n, 1);
for k = 1:n
    pk = sePolyAdd(P2{k}, [x(2*k-1) x(2*k)]);
    cv{k} = pk/EI;
    eq{k} = sprintf('$E\\,@I\\,@V_{%d}(s) = %s, \\ %s \\le s \\le %s$', k, ...
        BeamAndTrussSolver.poly2latex(pk, 's'), seT(br(k)), seT(br(k+1)));
end
I.vPP = struct('breaks', br, 'coefs', {cv});
I.alphaPP = BeamAndTrussSolver.ppDerivative(I.vPP);
I.constants = table((1:n).', br(1:n).', br(2:n+1).', x(1:2:end), x(2:2:end), ...
    'VariableNames', {'Troncon', 's1', 's2', 'C1', 'C2'});
I.equations = eq;
end

function [f, sf] = sePPMaxAbs(vPP, aPP)
% Maximum de |v| : points de rupture et racines de v' = 0 dans chaque tronçon.
br = vPP.breaks;
cand = br;
for k = 1:numel(br) - 1
    rt = roots(aPP.coefs{k});
    rt = real(rt(abs(imag(rt)) < 1e-9*max(1, abs(rt))));
    cand = [cand, rt(rt > br(k) & rt < br(k+1)).']; %#ok<AGROW>
end
v = max(abs(BeamAndTrussSolver.ppEval(vPP, cand, 'left')), abs(BeamAndTrussSolver.ppEval(vPP, cand, 'right')));
[f, i] = max(v);
sf = cand(i);
end

function A = seAires(M, EI, conds, sEval)
% Méthode des aires et des moments des aires :
% α(s) = α0 + (1/EI)∫_0^s M ; v(s) = v0 + α0 s + (1/EI) Σ A_k (s − s̄_k).
br = M.breaks;
n = numel(br) - 1;
IA = cell(1, n); IS = cell(1, n);
Ak = zeros(n, 1); Sk = zeros(n, 1);
for k = 1:n
    IA{k} = polyint(M.coefs{k});
    IS{k} = polyint(conv([1 0], M.coefs{k}));
    Ak(k) = polyval(IA{k}, br(k+1)) - polyval(IA{k}, br(k));
    Sk(k) = polyval(IS{k}, br(k+1)) - polyval(IS{k}, br(k));
end
cumA = [0; cumsum(Ak)];
cumS = [0; cumsum(Sk)];
known = @(s) seAiresKnown(s, br, IA, IS, cumA, cumS);
nc = size(conds, 1);
Q = zeros(nc, 2); r = zeros(nc, 1);
for i = 1:nc
    [fv, fa] = known(conds(i, 1));
    if conds(i, 2) == 0
        Q(i, :) = [1 conds(i, 1)]; r(i) = -fv/EI;
    else
        Q(i, :) = [0 1]; r(i) = -fa/EI;
    end
end
x = lsqminnorm(Q, r);
A = struct();
A.v0 = x(1);
A.alpha0 = x(2);
A.residual = norm(Q*x - r);
[fv, fa] = known(sEval);
A.v = A.v0 + A.alpha0*sEval + fv/EI;
A.alpha = A.alpha0 + fa/EI;
sb = (Sk./Ak).';
sb(abs(Ak.') <= 1e-14*max(abs(Ak))) = NaN;
A.areas = table((1:n).', br(1:n).', br(2:n+1).', Ak, sb.', 'VariableNames', {'Troncon', 's1', 's2', 'Aire', 'sBar'});
% Flèche maximale : extrémités et zéros de α(s) dans chaque tronçon
cand = br;
for k = 1:n
    pa = sePolyAdd(IA{k}, EI*A.alpha0 + cumA(k) - polyval(IA{k}, br(k)));
    rt = roots(pa);
    rt = real(rt(abs(imag(rt)) < 1e-9*max(1, abs(rt))));
    cand = [cand, rt(rt > br(k) & rt < br(k+1)).']; %#ok<AGROW>
end
fv = known(cand);
vc = abs(A.v0 + A.alpha0*cand + fv/EI);
[A.fmax, i] = max(vc);
A.sAtFmax = cand(i);
end

function [Fv, Fa] = seAiresKnown(s, br, IA, IS, cumA, cumS)
% Contribution des aires (sans α0, v0), multipliée par EI : Fv = ∫_0^s (s − t) M dt, Fa = ∫_0^s M.
Fv = zeros(size(s)); Fa = zeros(size(s));
for ii = 1:numel(s)
    k = seSeg(br, s(ii));
    a = cumA(k) + polyval(IA{k}, s(ii)) - polyval(IA{k}, br(k));
    m1 = cumS(k) + polyval(IS{k}, s(ii)) - polyval(IS{k}, br(k));
    Fv(ii) = s(ii)*a - m1;
    Fa(ii) = a;
end
end

function [mb, tb] = seUnitSolve(m, s0, kind, plane)
% Diagrammes m̄, t̄ de la poutre sous charge unité (force ou couple) en s0 (solveBeam rapide).
mu = m;
mu.distLoads = struct('a', {}, 'b', {}, 'dir', {}, 'coeffs', {}, 'name', {});
mu.pointLoads = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
mu.pointMoments = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
xy = strcmp(plane, 'xy');
if strcmp(kind, 'force')
    mu.pointLoads = struct('pos', s0, 'Fx', 0, 'Fy', double(xy), 'Fz', double(~xy), 'name', 'F1');
else
    % Couple conjugué de dv/ds (xy : Mz = +1) ou de dw/ds (xz : My = −1)
    mu.pointMoments = struct('pos', s0, 'Mx', 0, 'My', -double(~xy), 'Mz', double(xy), 'name', 'C1');
end
su = BeamAndTrussSolver.solveBeam(mu, seFastOpts());
if xy
    mb = su.Mfz; tb = su.Ty;
else
    mb = BeamAndTrussSolver.ppScale(su.Mfy, -1); tb = su.Tz;
end
end

function v = seIntProd(a, b)
% ∫_0^L a·b ds exacte.
v = BeamAndTrussSolver.ppIntegral(BeamAndTrussSolver.ppMultiply(a, b));
end

function v = seIyz(m)
% Produit d'inertie du modèle (0 si absent : axes principaux).
v = 0;
if isfield(m, 'Iyz') && ~isempty(m.Iyz) && isfinite(m.Iyz)
    v = double(m.Iyz);
end
end

function [Mz, My] = seBendMoments(sol, m)
% Moments équivalents de la flexion déviée : E·Iz·v'' = Mz et E·Iy·w'' = −My, avec
% [v''; −w''] = [Iz −Iyz; −Iyz Iy]⁻¹·[Mfz; Mfy]/E (σ = N/S + b·y + c·z, b = −E·v'', c = −E·w'').
% Sans Iyz : Mz = Mfz, My = Mfy.
Iyz = seIyz(m);
if Iyz == 0
    Mz = sol.Mfz;
    My = sol.Mfy;
    return
end
dt = m.Iz*m.Iy - Iyz^2;
if dt <= 0
    error('MecaStruct:SolicitationsEngine:invalidInput', 'Il faut Iyz² < Iz·Iy.');
end
lin = @(a, b) BeamAndTrussSolver.ppAdd(BeamAndTrussSolver.ppScale(sol.Mfz, a), BeamAndTrussSolver.ppScale(sol.Mfy, b));
Mz = lin(m.Iz*m.Iy/dt, m.Iz*Iyz/dt);
My = lin(m.Iy*Iyz/dt, m.Iy*m.Iz/dt);
end

function s0 = seDefaultS0(sup, L, sMax)
% Points d'intérêt : flèche max, milieux des travées, extrémités libres.
ps = unique([sup.pos]);
s0 = sMax;
if numel(ps) > 1
    s0 = [s0, (ps(1:end-1) + ps(2:end))/2];
end
tol = 1e-9*L;
if isempty(ps) || min(ps) > tol
    s0(end+1) = 0;
end
if isempty(ps) || max(ps) < L - tol
    s0(end+1) = L;
end
s0 = uniquetol(s0, 1e-12);
end

function c = seCoefAt(pp, s)
% Coefficients du tronçon contenant s.
c = pp.coefs{seSeg(pp.breaks, s)};
end

function q = seShift(c, a)
% Coefficients de p(ξ + a) (variable locale ξ = s − a).
q = 0;
for i = 1:numel(c)
    q = sePolyAdd(conv(q, [1 a]), c(i));
end
end

function [parts, ok, deg] = seDecompose(c, s1, s2)
% Décomposition d'un tronçon en forme linéaire (rectangle, triangle, triangle inversé, trapèze)
% + parabole (flèche f au milieu) si degré ≤ 2.
l = s2 - s1;
q = seShift(c, s1);
nq = numel(q);
pw = (nq-1:-1:0);
mag = abs(q).*l.^pw;
sc = max(mag);
deg = 0;
if sc > 0
    deg = max(pw(mag > 1e-11*sc));
end
parts = struct('shape', {}, 'vals', {});
ok = deg <= 2;
if ~ok
    return
end
M1 = polyval(c, s1); M2 = polyval(c, s2);
f = polyval(c, (s1 + s2)/2) - (M1 + M2)/2;
tol = 1e-11*max(sc, realmin);
if abs(M1) <= tol && abs(M2) <= tol
    % pas de partie linéaire
elseif abs(M1 - M2) <= tol
    parts(end+1) = struct('shape', 'rectangle', 'vals', (M1 + M2)/2);
elseif abs(M1) <= tol
    parts(end+1) = struct('shape', 'triangle', 'vals', M2);
elseif abs(M2) <= tol
    parts(end+1) = struct('shape', 'triangle_inverse', 'vals', M1);
else
    parts(end+1) = struct('shape', 'trapeze', 'vals', [M1 M2]);
end
if abs(f) > tol
    parts(end+1) = struct('shape', 'parabole', 'vals', f);
end
end

function s = seShapeName(parts, ok)
% Libellé de la décomposition.
if ~ok
    s = "hors table";
elseif isempty(parts)
    s = "nul";
else
    s = string(strjoin({parts.shape}, ' + '));
end
end

function s = seMohrTex(tex, l, a, b)
% Formule de la table avec valeurs numériques substituées (sans les $).
k = strfind(tex, '= ');
s = tex(k(1)+2:end-1);
rep = {'a_1', a, 1; 'a_2', a, 2; 'b_1', b, 1; 'b_2', b, 2; 'a', a, 1; 'b', b, 1};
for i = 1:size(rep, 1)
    v = rep{i, 2};
    if numel(v) >= rep{i, 3}
        s = regexprep(s, ['(?<![\\a-zA-Z_])' rep{i, 1} '(?![a-zA-Z_])'], seRx(seTp(v(rep{i, 3}))));
    end
end
s = regexprep(s, '(?<![\\a-zA-Z_])l(?![a-zA-Z_])', seRx(seTp(l)));
end

function s = seRx(s)
% Échappement des barres obliques inverses pour une chaîne de remplacement de regexprep.
s = strrep(s, '\', '\\');
end

function [x, w] = seGauss(n)
% Points et poids de Gauss-Legendre sur [−1, 1] (Golub-Welsch).
bb = (1:n-1)./sqrt(4*(1:n-1).^2 - 1);
[V, Dg] = eig(diag(bb, 1) + diag(bb, -1));
x = diag(Dg).';
w = 2*V(1, :).^2;
end

function s = seF(v)
% Nombre en texte (%.4g, sans « -0 »).
s = sprintf('%.4g', v + 0);
end

function s = seSgn(v)
% Terme signé pour l'affichage d'une expression linéaire.
if v < 0
    s = sprintf('− %.4g', -v);
else
    s = sprintf('+ %.4g', v);
end
end

function s = seT(v)
% Nombre en LaTeX (puissances de 10 écrites \cdot 10^{n}).
if isnan(v)
    s = '\mathrm{NaN}';
    return
end
str = sprintf('%.4g', v);
tok = regexp(str, '^(-?[\d.]+)e([+-]\d+)$', 'tokens', 'once');
if isempty(tok)
    s = str;
else
    s = sprintf('%s \\cdot 10^{%d}', tok{1}, str2double(tok{2}));
end
end

function s = seTp(v)
% Nombre LaTeX entre parenthèses s'il est négatif.
s = seT(v);
if v < 0
    s = ['\left(' s '\right)'];
end
end

function s = seTs(v)
% Terme LaTeX signé.
if v < 0
    s = ['- ' seT(-v)];
else
    s = ['+ ' seT(v)];
end
end

function s = seOk(tf)
% Verdict texte.
if tf
    s = 'vérifiée';
else
    s = 'NON vérifiée';
end
end

function out = seIf(c, a, b)
% Opérateur conditionnel.
if c
    out = a;
else
    out = b;
end
end
