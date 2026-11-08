classdef DesignChecks
    %DESIGNCHECKS Vérifications de dimensionnement : Eurocode 3 simplifié (flexion + effort tranchant,
    %   profilés en I) et fatigue de Goodman. Unités SI (m, N, Pa) ; aucun accès à l'interface.
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux.
    %
    %   Sources (détail dans docs/NORMES.md) :
    %     - NF EN 1993-1-1:2005 (+ A1:2014) et son annexe nationale NF EN 1993-1-1/NA : tableau 5.2 (classes),
    %       6.2.5 (flexion), 6.2.6 (tranchant), 6.2.8 (flexion + tranchant), 6.3.2.3 (déversement des laminés),
    %       tableaux 6.3 et 6.5 (courbes), 6.1 (γM0 = γM1 = 1,0 recommandés), 3.2.6 (E = 210 GPa, G = 81 GPa).
    %     - NCCI SN003a/b (Access Steel / CTICM) pour le moment critique élastique Mcr.
    %     - Fatigue : droite de Goodman modifiée et facteurs de Marin, Budynas & Nisbett, Shigley's Mechanical
    %       Engineering Design, chap. 6 (la fatigue des constructions métalliques relève de l'EN 1993-1-9, non traitée).
    %
    %   Limites assumées (rappelées dans les résultats) :
    %     - EC3 : flexion simple autour de l'axe fort et effort tranchant (EN 1993-1-1, 6.2.5, 6.2.6, 6.2.8) et
    %       déversement (6.3.2.3) ; classes 1 à 3 (la classe 4, section efficace, est refusée) ; flambement,
    %       effort normal, interaction N + M (6.3.3, annexe B, axe fort), voilement de l'âme par cisaillement ;
    %       pas de flexion déviée ; fy = Re du matériau (pas de réduction avec l'épaisseur).
    %     - Goodman : limite d'endurance estimée Se = ka·kb·0,5·Rm (acier), Kf = Kt (sensibilité à l'entaille q = 1).

    methods (Static)

        function d = ibeamDims(sec)
            %IBEAMDIMS Dimensions h, b, tw, tf, r (m) d'une section 'profile' (IPE, HEA, HEB, IPN) ou 'I'.
            switch char(sec.type)
                case 'profile'
                    if ~ismember(char(sec.family), {'IPE', 'HEA', 'HEB', 'IPN'})
                        error('MecaStruct:Design:unsupportedSection', ...
                            'Eurocode 3 : seuls les profilés IPE, HEA, HEB, IPN et les sections en I sont traités (section : %s).', ...
                            char(sec.family));
                    end
                    r = 0;
                    if isfield(sec, 'r') && isfinite(sec.r)
                        r = sec.r;
                    end
                    d = struct('h', sec.h, 'b', sec.b, 'tw', sec.a, 'tf', sec.e, 'r', r);
                case 'I'
                    d = struct('h', sec.h, 'b', sec.b, 'tw', sec.tw, 'tf', sec.tf, 'r', 0);
                otherwise
                    error('MecaStruct:Design:unsupportedSection', ...
                        'Eurocode 3 : la section doit être un profilé IPE, HEA, HEB, IPN ou un profil en I (section : %s).', ...
                        char(sec.type));
            end
        end

        function c = classify(d, fy, Nc, Mz, A, Iz)
            %CLASSIFY Classe de section (EN 1993-1-1, tableau 5.2) sous compression Nc (N, ≥ 0) et moment fort Mz (N·m). fy en Pa ; A, Iz en m², m⁴.
            %   Aile en console : c/tf ≤ 9ε, 10ε, 14ε. Âme (feuille 2) : σ = Nc/A ± |Mz|·(hw/2)/Iz aux bords de l'âme, ψ = σ2/σ1,
            %   α = dc/d = 1/(1 − ψ) ≤ 1. Classes 1 et 2 : 396ε/(13α − 1) et 456ε/(13α − 1) si α > 0,5, sinon 36ε/α et 41,5ε/α.
            %   Classe 3 : 42ε/(0,67 + 0,33ψ), ou 62ε(1 − ψ)√(−ψ) si ψ ≤ −1. Flexion seule : ψ = −1, soit 72ε, 83ε, 124ε.
            %   La traction est ignorée : elle donnerait des limites plus larges, donc c'est du côté de la sécurité.
            eps = sqrt(235e6 / fy);
            hw = d.h - 2 * d.tf;
            cf = (d.b - d.tw - 2 * d.r) / 2;
            cw = hw - 2 * d.r;
            sC = max(Nc, 0) / A;
            sM = abs(Mz) * (hw / 2) / Iz;
            psi = -1;
            if sC + sM > 0
                psi = (sC - sM) / (sC + sM);
            end
            alpha = min(1, 1 / (1 - psi));
            if alpha > 0.5
                lim = [396 / (13 * alpha - 1), 456 / (13 * alpha - 1)];
            else
                lim = [36 / alpha, 41.5 / alpha];
            end
            if psi > -1
                lim(3) = 42 / (0.67 + 0.33 * psi);
            else
                lim(3) = 62 * (1 - psi) * sqrt(-psi);
            end
            rf = cf / d.tf;
            rw = cw / d.tw;
            c = struct('eps', eps, 'cf', cf, 'cw', cw, 'ratioFlange', rf, 'ratioWeb', rw, 'psi', psi, 'alpha', alpha, ...
                'classFlange', DesignChecks.pick(rf, [9 10 14] * eps), ...
                'classWeb', DesignChecks.pick(rw, lim * eps));
            c.class = max(c.classFlange, c.classWeb);
        end

        function r = ec3Bending(d, S, Iz, fy, gM0, MEd, VEd, Nc)
            %EC3BENDING Résistance en flexion (axe fort) et en effort tranchant d'un profil en I.
            %   d : ibeamDims ; S (m²), Iz (m⁴) ; fy (Pa) ; gM0 (-) ; MEd (N·m), VEd (N) : valeurs de calcul.
            %   Nc : compression de calcul (N, défaut 0) : elle abaisse les limites de classe de l'âme (voir classify).
            %   Réduction du moment si VEd > 0,5·Vpl,Rd (6.2.8). Erreur 'MecaStruct:Design:class4' en classe 4.
            if nargin < 8
                Nc = 0;
            end
            if ~(fy > 0 && gM0 > 0)
                error('MecaStruct:Design:invalidInput', 'fy et γM0 doivent être strictement positifs.');
            end
            cl = DesignChecks.classify(d, fy, Nc, MEd, S, Iz);
            if cl.class == 4
                error('MecaStruct:Design:class4', ['Section de classe 4 (aile %.1f, âme %.1f) : la section efficace n''est ' ...
                    'pas traitée. Choisir un profilé plus trapu.'], cl.ratioFlange, cl.ratioWeb);
            end
            hw = d.h - 2 * d.tf;
            Wpl = d.b * d.tf * (d.h - d.tf) + d.tw * hw^2 / 4 ...
                + 4 * (1 - pi / 4) * d.r^2 * (hw / 2 - 0.2234 * d.r);
            Wel = Iz / (d.h / 2);
            if cl.class <= 2
                W = Wpl;
            else
                W = Wel;
            end
            Mc = W * fy / gM0;
            eta = 1.2;
            if fy > 460e6
                eta = 1.0;
            end
            Av = max(S - 2 * d.b * d.tf + (d.tw + 2 * d.r) * d.tf, eta * hw * d.tw);
            Vpl = Av * (fy / sqrt(3)) / gM0;
            reduced = abs(VEd) > 0.5 * Vpl;
            rho = 0;
            MRd = Mc;
            if reduced
                rho = (2 * abs(VEd) / Vpl - 1)^2;
                Aw = hw * d.tw;
                MRd = max(0, min(Mc, (W - rho * Aw^2 / (4 * d.tw)) * fy / gM0));
            end
            r = struct('class', cl, 'Wpl', Wpl, 'Wel', Wel, 'W', W, 'Mc', Mc, 'Av', Av, 'Vpl', Vpl, ...
                'reduced', reduced, 'rho', rho, 'MRd', MRd, 'MEd', abs(MEd), 'VEd', abs(VEd), ...
                'ratioM', abs(MEd) / MRd, 'ratioV', abs(VEd) / Vpl);
            r.ok = r.ratioM <= 1 && r.ratioV <= 1;
        end

        function r = ec3LateralTorsional(d, rolled, W, fy, gM1, E, G, Iweak, It, Lcr, C1, MEd)
            %EC3LATERALTORSIONAL Résistance au déversement d'un profil en I (EN 1993-1-1, 6.3.2.3, cas des laminés).
            %   d : ibeamDims ; rolled : true (laminé) ou false (soudé) ; W : module de flexion de la classe (Wpl ou Wel, m³) ;
            %   fy (Pa) ; gM1 (-) ; E, G (Pa) ; Iweak : moment quadratique de l'axe faible (m⁴) ; It : constante de torsion (m⁴) ;
            %   Lcr : longueur entre maintiens latéraux (m) ; C1 : facteur de forme du moment (1 = moment uniforme, prudent).
            %   Mcr (poutre à fourches, charge au centre de torsion, doublement symétrique) : NCCI SN003a/b,
            %     Mcr = C1·π²·E·Iz/Lcr²·√(Iw/Iz + Lcr²·G·It/(π²·E·Iz)), avec Iw ≈ Iz·(h − tf)²/4 (parois minces).
            %   λ̄LT = √(W·fy/Mcr) ; ΦLT = 0,5·[1 + αLT·(λ̄LT − 0,4) + 0,75·λ̄LT²] ;
            %   χLT = 1/(ΦLT + √(ΦLT² − 0,75·λ̄LT²)), borné par 1 et 1/λ̄LT² (6.57) ; Mb,Rd = χLT·W·fy/γM1 (6.55).
            %   Courbe (tableau 6.5, valeurs recommandées) : laminé h/b ≤ 2 → b, > 2 → c ; soudé h/b ≤ 2 → c, > 2 → d ;
            %   α (tableau 6.3) : a 0,21 ; b 0,34 ; c 0,49 ; d 0,76. L'annexe nationale peut modifier ces choix.
            %   Non pris en compte : coefficient f de répartition du moment (6.58, favorable) et le niveau d'application de la charge.
            if ~(Lcr > 0 && C1 > 0 && gM1 > 0 && Iweak > 0 && It > 0)
                error('MecaStruct:Design:invalidInput', 'Déversement : Lcr, C1, γM1, Iz et It doivent être strictement positifs.');
            end
            Iw = Iweak * (d.h - d.tf)^2 / 4;
            Mcr = C1 * pi^2 * E * Iweak / Lcr^2 * sqrt(Iw / Iweak + Lcr^2 * G * It / (pi^2 * E * Iweak));
            lam = sqrt(W * fy / Mcr);
            hb = d.h / d.b;
            tall = hb > 2 + 1e-9;
            if rolled
                curves = 'bc';
            else
                curves = 'cd';
            end
            curve = curves(1 + tall);
            alpha = DesignChecks.alphaOf(curve);
            beta = 0.75;
            lam0 = 0.4;
            Phi = 0.5 * (1 + alpha * (lam - lam0) + beta * lam^2);
            chi = min([1, 1 / lam^2, 1 / (Phi + sqrt(max(Phi^2 - beta * lam^2, 0)))]);
            if lam <= lam0
                chi = 1;   % 6.3.2.3(1) : pas de réduction pour λ̄LT ≤ λ̄LT,0 (6.56)
            end
            Mb = chi * W * fy / gM1;
            r = struct('Iw', Iw, 'Mcr', Mcr, 'lambda', lam, 'curve', curve, 'alpha', alpha, 'Phi', Phi, 'chi', chi, ...
                'MbRd', Mb, 'MEd', abs(MEd), 'ratio', abs(MEd) / Mb);
            r.ok = r.ratio <= 1;
        end

        function r = ec3FlexuralBuckling(d, rolled, A, Iy, Iz, Lcr, fy, E, gM1, NEd)
            %EC3FLEXURALBUCKLING Flambement par flexion d'une barre comprimée en I (EN 1993-1-1, 6.3.1).
            %   d : ibeamDims ; rolled : laminé (true) ou soudé ; A (m²) ; Iy (axe fort), Iz (axe faible) en m⁴ ;
            %   Lcr (m) : scalaire, ou [Lcr,y Lcr,z] pour l'axe fort y-y et l'axe faible z-z (le plan fort n'est pas
            %   contreventé par les entretoises : sa longueur est celle de la poutre) ;
            %   fy, E (Pa) ; gM1 (-) ; NEd : effort de compression (N, positif).
            %   Ncr = π²·E·I/Lcr² ; λ̄ = √(A·fy/Ncr) ; Φ = 0,5·[1 + α·(λ̄ − 0,2) + λ̄²] ; χ = 1/(Φ + √(Φ² − λ̄²)) ≤ 1 (6.49) ;
            %   Nb,Rd = χ·A·fy/γM1 (6.47). Pas de vérification si λ̄ ≤ 0,2 ou NEd/Ncr ≤ 0,04 (6.3.1.2(4)).
            %   Courbes (tableau 6.2, aciers S235 à S420) : laminé h/b > 1,2 : tf ≤ 40 mm → a (y-y), b (z-z) ;
            %   40 < tf ≤ 100 mm → b, c ; laminé h/b ≤ 1,2 : tf ≤ 100 mm → b, c ; soudé : tf ≤ 40 mm → b, c ; tf > 40 mm → c, d.
            %   Laminé h/b > 1,2 avec tf > 100 mm : non tabulé, courbe d par prudence.
            %   α (tableau 6.1) : a0 0,13 ; a 0,21 ; b 0,34 ; c 0,49 ; d 0,76. Aciers S460 : courbes différentes, refusés.
            if fy > 420e6
                error('MecaStruct:Design:unsupportedSteel', ['Flambement : le tableau 6.2 retenu vaut pour les aciers jusqu''à S420 ' ...
                    '(fy = %.0f MPa).'], fy / 1e6);
            end
            if isscalar(Lcr)
                Lcr = [Lcr Lcr];
            end
            if ~(all(Lcr > 0) && gM1 > 0 && A > 0 && Iy > 0 && Iz > 0)
                error('MecaStruct:Design:invalidInput', 'Flambement : Lcr, γM1, A, Iy et Iz doivent être strictement positifs.');
            end
            tf = d.tf * 1e3;
            hb = d.h / d.b;
            curves = {'a', 'b'};
            if rolled
                if hb > 1.2
                    if tf > 100
                        curves = {'d', 'd'};   % non tabulé : courbe d par prudence
                    elseif tf > 40
                        curves = {'b', 'c'};
                    end
                else
                    curves = {'b', 'c'};
                    if tf > 100, curves = {'d', 'd'}; end
                end
            else
                curves = {'b', 'c'};
                if tf > 40, curves = {'c', 'd'}; end
            end
            I = [Iy, Iz];
            axisName = {'y-y', 'z-z'};
            ax = repmat(struct('axis', '', 'Ncr', 0, 'lambda', 0, 'curve', '', 'alpha', 0, 'Phi', 0, 'chi', 1, 'NbRd', 0, 'needed', true), 1, 2);
            for k = 1:2
                Ncr = pi^2 * E * I(k) / Lcr(k)^2;
                lam = sqrt(A * fy / Ncr);
                al = DesignChecks.alphaOf(curves{k});
                Phi = 0.5 * (1 + al * (lam - 0.2) + lam^2);
                chi = min(1, 1 / (Phi + sqrt(max(Phi^2 - lam^2, 0))));
                needed = ~(lam <= 0.2 || abs(NEd) / Ncr <= 0.04);
                if ~needed
                    chi = 1;
                end
                ax(k) = struct('axis', axisName{k}, 'Ncr', Ncr, 'lambda', lam, 'curve', curves{k}, 'alpha', al, 'Phi', Phi, ...
                    'chi', chi, 'NbRd', chi * A * fy / gM1, 'needed', needed);
            end
            [~, g] = min([ax.NbRd]);
            r = struct('axes', ax, 'governing', g, 'NbRd', ax(g).NbRd, 'NEd', abs(NEd), 'ratio', abs(NEd) / ax(g).NbRd);
            r.ok = r.ratio <= 1;
        end

        function r = ec3AxialBending(d, b, A, fy, gM0, NEd, MEd)
            %EC3AXIALBENDING Flexion + effort normal, section de classe 1 à 3, flexion autour de l'axe fort (EN 1993-1-1, 6.2.9).
            %   b : résultat de ec3Bending ; NEd (N, signe ignoré) ; MEd (N·m).
            %   Classes 1 et 2 (6.2.9.1) : MN,y,Rd = Mpl,y,Rd·(1 − n)/(1 − 0,5·a) ≤ Mpl,y,Rd (6.36), n = NEd/Npl,Rd,
            %   a = (A − 2·b·tf)/A ≤ 0,5 ; sans réduction si NEd ≤ 0,25·Npl,Rd et NEd ≤ 0,5·hw·tw·fy/γM0 (6.33, 6.34) ;
            %   plafonné par le moment réduit par le tranchant. Classe 3 (6.2.9.2) : σx,Ed = N/A + M/Wel ≤ fy/γM0 (6.42).
            NEd = abs(NEd);
            Npl = A * fy / gM0;
            n = NEd / Npl;
            hw = d.h - 2 * d.tf;
            if b.class.class <= 2
                a = min((A - 2 * d.b * d.tf) / A, 0.5);
                free = n <= 0.25 && NEd <= 0.5 * hw * d.tw * fy / gM0;
                if free
                    MN = b.Mc;
                elseif n >= 1
                    MN = 0;
                else
                    MN = min(b.Mc, b.Mc * (1 - n) / (1 - 0.5 * a));
                end
                MN = min(MN, b.MRd);
                ratio = abs(MEd) / max(MN, eps);
                if MN <= 0, ratio = Inf; end
                r = struct('class12', true, 'n', n, 'a', a, 'free', free, 'Npl', Npl, 'MNRd', MN, 'ratio', ratio);
            else
                sig = NEd / A + abs(MEd) / b.Wel;
                r = struct('class12', false, 'n', n, 'a', NaN, 'free', false, 'Npl', Npl, 'MNRd', NaN, ...
                    'sigma', sig, 'ratio', sig / (fy / gM0));
            end
            r.ok = r.ratio <= 1;
        end

        function r = ec3Interaction(cls, buck, ltb, A, W, fy, gM1, NEd, MEd, Cmy, CmLT)
            %EC3INTERACTION Interaction compression + flexion autour de l'axe fort d'un profil en I (EN 1993-1-1, 6.3.3, éq. 6.61 et 6.62).
            %   cls : classe de section (1 à 3) ; buck : ec3FlexuralBuckling (χy, χz, λ̄y, λ̄z) ; ltb : ec3LateralTorsional (χLT) ;
            %   A (m²) ; W (m³, Wpl en classe 1-2, Wel en classe 3) ; fy (Pa) ; gM1 ; NEd (N, compression) ; MEd (N·m, axe fort) ;
            %   Cmy, CmLT : facteurs de moment uniforme équivalent (tableau B.3 ; 1 = prudent, valeurs admises de 0,4 à 1).
            %   NEd/(χy·NRk/γM1) + kyy·MEd/(χLT·My,Rk/γM1) ≤ 1 (6.61) ; NEd/(χz·NRk/γM1) + kzy·MEd/(χLT·My,Rk/γM1) ≤ 1 (6.62).
            %   Facteurs kyy et kzy : annexe B (méthode 2), tableau B.2 (barres sensibles aux déformations de torsion, profils en I) :
            %     classes 1-2 : kyy = Cmy·[1 + (λ̄y − 0,2)·nY] ≤ Cmy·(1 + 0,8·nY) ;
            %       kzy = 1 − 0,1·λ̄z·nZ/(CmLT − 0,25) ≥ 1 − 0,1·nZ/(CmLT − 0,25) si λ̄z ≥ 0,4 ;
            %       kzy = 0,6 + λ̄z ≤ 1 − 0,1·λ̄z·nZ/(CmLT − 0,25) si λ̄z < 0,4 ;
            %     classe 3 : kyy = Cmy·(1 + 0,6·λ̄y·nY) ≤ Cmy·(1 + 0,6·nY) ; kzy = 1 − 0,05·λ̄z·nZ/(CmLT − 0,25) ≥ 1 − 0,05·nZ/(CmLT − 0,25).
            %   nY = NEd/(χy·NRk/γM1), nZ = NEd/(χz·NRk/γM1). Flexion autour de l'axe fort seulement (pas de My,z).
            if ~(Cmy >= 0.4 && Cmy <= 1 && CmLT >= 0.4 && CmLT <= 1)
                error('MecaStruct:Design:invalidInput', 'Cmy et CmLT doivent être compris entre 0,4 et 1 (tableau B.3).');
            end
            if ~(cls >= 1 && cls <= 3)
                error('MecaStruct:Design:class4', 'Interaction 6.3.3 : classes 1 à 3 seulement.');
            end
            NRk = A * fy;
            MyRk = W * fy;
            ay = buck.axes(1);
            az = buck.axes(2);
            nY = abs(NEd) / (ay.chi * NRk / gM1);
            nZ = abs(NEd) / (az.chi * NRk / gM1);
            if cls <= 2
                kyy = min(Cmy * (1 + (ay.lambda - 0.2) * nY), Cmy * (1 + 0.8 * nY));
                if az.lambda >= 0.4
                    kzy = max(1 - 0.1 * az.lambda * nZ / (CmLT - 0.25), 1 - 0.1 * nZ / (CmLT - 0.25));
                else
                    kzy = min(0.6 + az.lambda, 1 - 0.1 * az.lambda * nZ / (CmLT - 0.25));
                end
            else
                kyy = min(Cmy * (1 + 0.6 * ay.lambda * nY), Cmy * (1 + 0.6 * nY));
                kzy = max(1 - 0.05 * az.lambda * nZ / (CmLT - 0.25), 1 - 0.05 * nZ / (CmLT - 0.25));
            end
            den = ltb.chi * MyRk / gM1;
            r61 = nY + kyy * abs(MEd) / den;
            r62 = nZ + kzy * abs(MEd) / den;
            r = struct('nY', nY, 'nZ', nZ, 'kyy', kyy, 'kzy', kzy, 'ratio61', r61, 'ratio62', r62, ...
                'ratio', max(r61, r62), 'Cmy', Cmy, 'CmLT', CmLT);
            r.ok = r.ratio <= 1;
        end

        function r = ec3WebShear(d, fy, gM1, VEd)
            %EC3WEBSHEAR Voilement de l'âme par cisaillement, âme non raidie sauf aux appuis (EN 1993-1-1 6.2.6(6), EN 1993-1-5 §5).
            %   Vérification nécessaire si hw/tw > 72·ε/η (η = 1,2 jusqu'à S460, 1,0 au-delà). Sinon : sans objet.
            %   λ̄w = hw/(86,4·tw·ε) (raidisseurs aux appuis seulement, éq. 5.6) ; poteau d'extrémité rigide (tableau 5.1) :
            %   χw = η si λ̄w < 0,83/η ; 0,83/λ̄w si λ̄w < 1,08 ; 1,37/(0,7 + λ̄w) au-delà ; Vb,Rd = χw·fy·hw·tw/(√3·γM1)
            %   (la contribution des semelles est négligée : côté sécurité). Les charges concentrées (voilement local, §6) ne sont pas vérifiées.
            eps = sqrt(235e6 / fy);
            eta = 1.2;
            if fy > 460e6
                eta = 1.0;
            end
            hw = d.h - 2 * d.tf;
            lim = 72 * eps / eta;
            r = struct('hwTw', hw / d.tw, 'limit', lim, 'needed', hw / d.tw > lim, 'VEd', abs(VEd));
            if ~r.needed
                r.lambda = NaN; r.chi = NaN; r.VbRd = Inf; r.ratio = 0; r.ok = true;
                return
            end
            lam = hw / (86.4 * d.tw * eps);
            if lam < 0.83 / eta
                chi = eta;
            elseif lam < 1.08
                chi = 0.83 / lam;
            else
                chi = 1.37 / (0.7 + lam);
            end
            r.lambda = lam;
            r.chi = chi;
            r.VbRd = chi * fy * hw * d.tw / (sqrt(3) * gM1);
            r.ratio = abs(VEd) / r.VbRd;
            r.ok = r.ratio <= 1;
        end

        function r = goodman(sigMax, R, Kf, Rm, ka, kb)
            %GOODMAN Coefficient de sécurité en fatigue (droite de Goodman modifiée), contrainte nominale sigMax (Pa).
            %   R = σmin/σmax dans [-1, 1[ (-1 : alterné, 0 : répété). Kf s'applique à l'amplitude seulement.
            if ~(R >= -1 && R < 1)
                error('MecaStruct:Design:invalidInput', 'Le rapport R = σmin/σmax doit vérifier -1 ≤ R < 1.');
            end
            if ~(sigMax >= 0 && Rm > 0 && ka > 0 && kb > 0 && Kf >= 1)
                error('MecaStruct:Design:invalidInput', 'Fatigue : σmax ≥ 0, Rm > 0, ka > 0, kb > 0 et Kf ≥ 1 sont requis.');
            end
            Sep = min(0.5 * Rm, 700e6);
            Se = ka * kb * Sep;
            sigA = Kf * sigMax * (1 - R) / 2;
            sigM = sigMax * (1 + R) / 2;
            den = sigA / Se + max(sigM, 0) / Rm;
            n = 1 / max(den, eps);
            if den == 0
                n = Inf;
            end
            r = struct('sigmaA', sigA, 'sigmaM', sigM, 'Se', Se, 'n', n);
        end
    end

    methods (Static, Access = private)
        function k = pick(x, lims)
            k = find(x <= lims, 1);
            if isempty(k)
                k = 4;
            end
        end

        function a = alphaOf(curve)
            %ALPHAOF Facteur d'imperfection α de la courbe a0, a, b, c ou d (tableaux 6.1 et 6.3).
            t = struct('a0', 0.13, 'a', 0.21, 'b', 0.34, 'c', 0.49, 'd', 0.76);
            a = t.(char(curve));
        end
    end
end
