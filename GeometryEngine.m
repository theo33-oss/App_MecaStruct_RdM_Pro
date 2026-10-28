classdef GeometryEngine
    %GEOMETRYENGINE Caractéristiques géométriques des sections droites (moteur statique, SI strict).
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   Dimensions en m, aires en m², moments statiques et modules en m³, moments quadratiques en m⁴.
    %   Repère de saisie O1 : z horizontal vers la droite, y vertical vers le haut (origine : coin
    %   bas-gauche de la section, sauf 'composite' : repère utilisateur). Moments quadratiques en G :
    %     Iz = ∬ y² dS, Iy = ∬ z² dS, Iyz = ∬ y·z dS (y, z mesurés depuis G), Ix = Iz + Iy.
    %
    %   Types de section (sec.type) et champs (m) :
    %     'rectangle'        b (selon z), h (selon y)                       O1 = coin bas-gauche
    %     'disque'           D                                              O1 = coin bas-gauche du carré englobant
    %     'couronne'         D, d (0 ≤ d < D)                               idem
    %     'rectangle_creux'  B (selon z), H (selon y), t (épaisseur)        O1 = coin bas-gauche
    %     'I'                h, b, tw (âme « a »), tf (aile « e »)          symétrique
    %     'T'                h, b, tw, tf — aile en haut
    %     'U'                h, b, tw, tf — âme à gauche, ailes vers la droite
    %     'L'                h (aile verticale), b (aile horizontale), t    O1 = angle en bas à gauche
    %     'profile'          family, name, h, b, a, e (+ S, Iz, Iy, Wz, Wy, rz, ry, c du catalogue,
    %                        cf. DataManager.getProfile) : géométrie simplifiée en I (IPN, IPE, HEA, HEB)
    %                        ou en U (UPN, UAP) d'épaisseurs constantes a, e (congés ignorés)
    %     'composite'        rects (N×4 [z1 z2 y1 y2]), holes (M×4, optionnel) ; extensions
    %                        optionnelles disks (K×3 [zc yc R]) et diskHoles (K×3) — repère utilisateur.
    %                        Les rectangles (et disques) ne doivent pas se chevaucher ; les trous
    %                        doivent être contenus dans la matière et ne pas se chevaucher.
    %
    %   Méthodes publiques :
    %     sec   = GeometryEngine.validateSection(sec)   contrôle et normalisation d'une section
    %     prims = GeometryEngine.primitives(sec)        décomposition en rectangles / disques / couronnes
    %     P     = GeometryEngine.analytical(sec)        méthode A : formules fermées + Huygens
    %     P     = GeometryEngine.integral(sec, mode)    méthode B : intégrales doubles ('symbolique' | 'numerique')
    %     P     = GeometryEngine.tabulated(sec)         valeurs du catalogue (type 'profile')
    %     C     = GeometryEngine.compare(sec)           tableau comparatif des méthodes
    %     b     = GeometryEngine.widthAt(sec, y, side)  largeur b(y), y depuis G
    %     Q     = GeometryEngine.firstMomentAbove(sec, y)  moment statique de la partie au-dessus de y
    %     out   = GeometryEngine.outline(sec)           contours fermés (z, y) dans O1
    %     f     = GeometryEngine.shearFactors(sec)      facteurs k (Jourawski) et ky (section réduite)
    %     sec   = GeometryEngine.fromProfile(p)         section 'profile' à partir d'un profilé du catalogue
    %     T     = GeometryEngine.sectionTypes()         description des types reconnus
    %     tf    = GeometryEngine.hasSymbolic()          Symbolic Math Toolbox disponible
    %
    %   Voir aussi SolicitationsEngine.jourawski, PlotEngine.section.

    methods (Static)

        %% =====================================================================================
        %  Validation et décomposition
        %  =====================================================================================

        function sec = validateSection(sec)
            %VALIDATESECTION Contrôle et normalise une structure de section.
            %   sec = GeometryEngine.validateSection(sec)
            %   Entrée : structure scalaire sec (champ type + dimensions en m, cf. aide de la classe).
            %   Sortie : même structure, sec.type mis sous forme canonique ('rectangle', 'disque',
            %   'couronne', 'rectangle_creux', 'I', 'T', 'U', 'L', 'profile', 'composite'), dimensions
            %   converties en double. Pour 'profile' : champs profileShape ('I' ou 'U'), tw (= a),
            %   tf (= e), family et name ajoutés. Pour 'composite' : holes, disks, diskHoles complétés
            %   (matrices vides si absents).
            %   Erreurs : MecaStruct:GeometryEngine:invalidInput, :missingField, :unknownType,
            %   :invalidDimensions, :overlap, :holeOutside.
            if ~isstruct(sec) || ~isscalar(sec)
                error('MecaStruct:GeometryEngine:invalidInput', ...
                    'La section doit être une structure scalaire (champ sec.type obligatoire).');
            end
            if ~isfield(sec, 'type') || isempty(sec.type) || ...
                    ~(ischar(sec.type) || (isstring(sec.type) && isscalar(sec.type)))
                error('MecaStruct:GeometryEngine:missingField', ...
                    'Champ obligatoire manquant : sec.type (texte).');
            end
            key = lower(strtrim(char(sec.type)));
            key = strrep(strrep(key, ' ', '_'), '-', '_');
            switch key
                case {'rectangle', 'rect', 'rectangulaire'}
                    t = 'rectangle';
                case {'disque', 'disk', 'cercle', 'circle', 'rond', 'circulaire'}
                    t = 'disque';
                case {'couronne', 'tube', 'annulus', 'anneau', 'tube_circulaire'}
                    t = 'couronne';
                case {'rectangle_creux', 'caisson', 'tube_rectangulaire', 'creux'}
                    t = 'rectangle_creux';
                case 'i'
                    t = 'I';
                case 't'
                    t = 'T';
                case 'u'
                    t = 'U';
                case {'l', 'corniere', 'cornière'}
                    t = 'L';
                case {'profile', 'profil', 'profilé', 'profile_catalogue'}
                    t = 'profile';
                case {'composite', 'composee', 'composée', 'quelconque'}
                    t = 'composite';
                otherwise
                    error('MecaStruct:GeometryEngine:unknownType', ...
                        ['Type de section inconnu : ''%s''. Types reconnus : rectangle, disque, ' ...
                        'couronne, rectangle_creux, I, T, U, L, profile, composite.'], char(sec.type));
            end
            sec.type = t;
            switch t
                case 'rectangle'
                    sec.b = GeometryEngine.dimField(sec, 'b', 'largeur selon z');
                    sec.h = GeometryEngine.dimField(sec, 'h', 'hauteur selon y');
                case 'disque'
                    sec.D = GeometryEngine.dimField(sec, 'D', 'diamètre');
                case 'couronne'
                    sec.D = GeometryEngine.dimField(sec, 'D', 'diamètre extérieur');
                    sec.d = GeometryEngine.dimField(sec, 'd', 'diamètre intérieur', true);
                    if sec.d >= sec.D
                        error('MecaStruct:GeometryEngine:invalidDimensions', ...
                            'Couronne : le diamètre intérieur d (%g m) doit être inférieur à D (%g m).', ...
                            sec.d, sec.D);
                    end
                case 'rectangle_creux'
                    sec.B = GeometryEngine.dimField(sec, 'B', 'largeur extérieure selon z');
                    sec.H = GeometryEngine.dimField(sec, 'H', 'hauteur extérieure selon y');
                    sec.t = GeometryEngine.dimField(sec, 't', 'épaisseur de paroi');
                    if 2*sec.t >= min(sec.B, sec.H)
                        error('MecaStruct:GeometryEngine:invalidDimensions', ...
                            'Rectangle creux : il faut 2t < min(B, H) (t = %g m, B = %g m, H = %g m).', ...
                            sec.t, sec.B, sec.H);
                    end
                case {'I', 'T', 'U'}
                    sec.h = GeometryEngine.dimField(sec, 'h', 'hauteur totale');
                    sec.b = GeometryEngine.dimField(sec, 'b', 'largeur des ailes');
                    sec.tw = GeometryEngine.dimField(sec, 'tw', 'épaisseur d''âme a');
                    sec.tf = GeometryEngine.dimField(sec, 'tf', 'épaisseur d''aile e');
                    GeometryEngine.checkThinWalls(t, sec.h, sec.b, sec.tw, sec.tf);
                case 'L'
                    sec.h = GeometryEngine.dimField(sec, 'h', 'longueur de l''aile verticale');
                    sec.b = GeometryEngine.dimField(sec, 'b', 'longueur de l''aile horizontale');
                    sec.t = GeometryEngine.dimField(sec, 't', 'épaisseur');
                    if sec.t >= min(sec.h, sec.b)
                        error('MecaStruct:GeometryEngine:invalidDimensions', ...
                            'Cornière L : il faut t < min(h, b) (t = %g m, h = %g m, b = %g m).', ...
                            sec.t, sec.h, sec.b);
                    end
                case 'profile'
                    sec = GeometryEngine.resolveProfile(sec);
                case 'composite'
                    sec = GeometryEngine.validateComposite(sec);
            end
        end

        function prims = primitives(sec)
            %PRIMITIVES Décomposition d'une section en primitives élémentaires signées.
            %   prims = GeometryEngine.primitives(sec)
            %   Sortie : struct colonne, un élément par primitive, champs :
            %     kind  'rect' | 'disk' | 'annulus'
            %     sign  +1 (matière) ou -1 (trou)
            %     z1, z2, y1, y2  limites du rectangle (pour un disque / une couronne : carré englobant)
            %     zc, yc          centre (rectangle : centre de gravité)
            %     R, Ri           rayons extérieur / intérieur (NaN pour un rectangle ; Ri = 0 : disque)
            %     label           nom de l'élément (ex. 'Aile supérieure', 'Âme')
            %   Toutes les coordonnées sont dans le repère O1 (m).
            sec = GeometryEngine.validateSection(sec);
            prims = GeometryEngine.buildPrims(sec);
        end

        %% =====================================================================================
        %  Méthode A : analytique + Huygens
        %  =====================================================================================

        function P = analytical(sec)
            %ANALYTICAL Méthode A : formules fermées et décomposition en éléments + théorème de Huygens.
            %   P = GeometryEngine.analytical(sec)
            %   Sections élémentaires (rectangle, disque, couronne, rectangle creux) : formules fermées
            %   du cours (S = bh, Iz = bh³/12, Iz = πD⁴/64·(1 − m⁴)…). Sections composées (I, T, U, L,
            %   profilé, composite) : barycentre par les moments statiques zG = M_O1y/S, yG = M_O1z/S,
            %   puis Huygens I_Gz = Σ (I_Gz,i + S_i·dy_i²), I_Gy = Σ (I_Gy,i + S_i·dz_i²),
            %   I_Gyz = Σ S_i·dy_i·dz_i.
            %   Sortie P (SI) : S, zG, yG (repère O1), MO1z, MO1y, Iz, Iy, Iyz (en G), Ix (= Iz + Iy),
            %   J (constante de torsion), Jmethod, I1, I2 (I1 ≥ I2), alphaP (rad, axe 1 depuis z),
            %   rz, ry, vyTop, vyBot, vzRight, vzLeft, Wz, Wy, k, ky, kSource ('cours' | 'numérique'),
            %   shear (résultat complet de shearFactors), bbox ([zmin zmax ymin ymax] dans O1),
            %   type, method ('analytique'), huygens (table : Label, S_i, zG_i, yG_i, IGz_i, IGy_i,
            %   dy_i, dz_i, SDy2, SDz2, Iz_i, Iy_i, SDyDz — valeurs signées, trous négatifs),
            %   report (cell colonne de texte), latex (cell de chaînes LaTeX).
            sec = GeometryEngine.validateSection(sec);
            prims = GeometryEngine.buildPrims(sec);
            core = GeometryEngine.huygensCore(prims);
            [core, repClosed, texClosed] = GeometryEngine.closedForm(sec, core);
            P = GeometryEngine.assembleP(sec, prims, core, 'analytique');
            P.huygens = core.table;

            rep = {sprintf('Méthode A — formules fermées et théorème de Huygens (%s)', ...
                GeometryEngine.typeLabel(sec))};
            rep{end+1, 1} = GeometryEngine.describeSection(sec);
            tex = {};
            if ~isempty(repClosed)
                rep = [rep; repClosed];
                tex = [tex; texClosed];
            else
                [repH, texH] = GeometryEngine.huygensText(core);
                rep = [rep; repH];
                tex = [tex; texH];
            end
            if strcmp(sec.type, 'profile')
                rep{end+1, 1} = ['Remarque : géométrie simplifiée (âme et ailes d''épaisseurs constantes ' ...
                    'a et e, congés de raccordement et inclinaison des ailes ignorés) : un écart de ' ...
                    'quelques % avec les valeurs du catalogue est attendu (voir GeometryEngine.compare).'];
            end
            [repC, texC] = GeometryEngine.commonText(P);
            P.report = [rep; repC];
            P.latex = [tex; texC];
        end

        %% =====================================================================================
        %  Méthode B : intégrales doubles
        %  =====================================================================================

        function P = integral(sec, mode)
            %INTEGRAL Méthode B : intégration surfacique exacte (symbolique) ou numérique.
            %   P = GeometryEngine.integral(sec)            mode par défaut : 'symbolique' si la
            %                                                Symbolic Math Toolbox est disponible,
            %                                                sinon 'numerique'
            %   P = GeometryEngine.integral(sec, mode)      mode = 'symbolique' | 'numerique'
            %   Chaque primitive est intégrée séparément (signe -1 pour les trous) :
            %     rectangle : dS = dy·dz, y ∈ [y1, y2], z ∈ [z1, z2] (int imbriqués ou integral2) ;
            %     disque / couronne : dS = r·dr·dθ, r ∈ [Ri, R], θ ∈ [0, 2π], y = yc + r·sin θ,
            %                         z = zc + r·cos θ.
            %   S = ∬ dS ; M_O1z = ∬ y1 dS ; M_O1y = ∬ z1 dS ; zG = M_O1y/S ; yG = M_O1z/S ;
            %   I_Gz = ∬ (y1 − yG)² dS ; I_Gy = ∬ (z1 − zG)² dS ; I_Gyz = ∬ (y1 − yG)(z1 − zG) dS ;
            %   Ix = ∬ r² dS (contrôle : = I_Gz + I_Gy).
            %   Sortie : mêmes champs que analytical (sans huygens), plus integrals (cell de chaînes
            %   LaTeX des intégrales posées avec leurs bornes numériques), IxDirect (∬ r² dS),
            %   methodUsed ('symbolique' | 'numérique'), method ('intégrale symbolique' |
            %   'intégrale numérique'). Repli numérique automatique sans Symbolic Math Toolbox.
            sec = GeometryEngine.validateSection(sec);
            if nargin < 2 || isempty(mode)
                if GeometryEngine.hasSymbolic()
                    mode = 'symbolique';
                else
                    mode = 'numerique';
                end
            end
            mode = GeometryEngine.normalizeMode(mode);
            prims = GeometryEngine.buildPrims(sec);
            notes = {};
            R = [];
            if strcmp(mode, 'symbolique') && ~GeometryEngine.hasSymbolic()
                notes{end+1, 1} = ['Symbolic Math Toolbox indisponible : repli sur l''intégration ' ...
                    'numérique (integral2).'];
                mode = 'numerique';
            end
            if strcmp(mode, 'symbolique')
                try
                    R = GeometryEngine.integrateSymbolic(prims);
                catch err
                    notes{end+1, 1} = sprintf(['Échec du calcul symbolique (%s) : repli sur ' ...
                        'l''intégration numérique (integral2).'], err.message);
                    mode = 'numerique';
                end
            end
            if strcmp(mode, 'numerique')
                R = GeometryEngine.integrateNumeric(prims);
            end
            core = struct('S', R.S, 'MO1z', R.MO1z, 'MO1y', R.MO1y, 'yG', R.yG, 'zG', R.zG, ...
                'Iz', R.Iz, 'Iy', R.Iy, 'Iyz', R.Iyz);
            core = GeometryEngine.cleanIyz(core);
            if strcmp(mode, 'symbolique')
                methodLabel = 'intégrale symbolique';
                methodUsed = 'symbolique';
            else
                methodLabel = 'intégrale numérique';
                methodUsed = 'numérique';
            end
            P = GeometryEngine.assembleP(sec, prims, core, methodLabel);
            P.IxDirect = R.IxDirect;
            P.methodUsed = methodUsed;
            P.integrals = GeometryEngine.integralStrings(prims, R);

            fs = @GeometryEngine.fs;
            if strcmp(mode, 'symbolique')
                rep = {'Méthode B — intégration surfacique exacte (calcul symbolique, int imbriqués)'};
            else
                rep = {'Méthode B — intégration surfacique numérique (integral2, tolérance relative 1e-13)'};
            end
            rep{end+1, 1} = GeometryEngine.describeSection(sec);
            rep = [rep; notes];
            rep{end+1, 1} = ['Coordonnées (y, z) dans le repère O1 ; rectangles : dS = dy·dz ; ' ...
                'disques et couronnes : dS = r·dr·dθ avec y = yc + r·sin θ, z = zc + r·cos θ.'];
            for k = 1:numel(prims)
                p = prims(k);
                if p.sign > 0, sgTxt = '+'; else, sgTxt = '−'; end
                if strcmp(p.kind, 'rect')
                    rep{end+1, 1} = sprintf('  %d. %s (%s) : z ∈ [%s ; %s] m, y ∈ [%s ; %s] m', k, ...
                        p.label, sgTxt, fs(p.z1), fs(p.z2), fs(p.y1), fs(p.y2)); %#ok<AGROW>
                else
                    rep{end+1, 1} = sprintf(['  %d. %s (%s) : centre (zc = %s m, yc = %s m), ' ...
                        'r ∈ [%s ; %s] m, θ ∈ [0 ; 2π]'], k, p.label, sgTxt, fs(p.zc), fs(p.yc), ...
                        fs(p.Ri), fs(p.R)); %#ok<AGROW>
                end
                rep{end+1, 1} = sprintf(['     S_%d = %s m², M_O1z,%d = %s m³, M_O1y,%d = %s m³ ; ' ...
                    'contributions en G : I_Gz = %s m⁴, I_Gy = %s m⁴, I_Gyz = %s m⁴'], ...
                    k, fs(R.Si(k)), k, fs(R.MO1zi(k)), k, fs(R.MO1yi(k)), fs(R.Izi(k)), ...
                    fs(R.Iyi(k)), fs(R.Iyzi(k))); %#ok<AGROW>
            end
            rep{end+1, 1} = sprintf('Aire : S = ∬ dS = %s m² (%s cm²)', fs(P.S), fs(P.S*1e4));
            rep{end+1, 1} = sprintf('Moments statiques : M_O1z = ∬ y1 dS = %s m³ ; M_O1y = ∬ z1 dS = %s m³', ...
                fs(P.MO1z), fs(P.MO1y));
            rep{end+1, 1} = sprintf('Barycentre : yG = M_O1z/S = %s m ; zG = M_O1y/S = %s m', ...
                fs(P.yG), fs(P.zG));
            rep{end+1, 1} = sprintf('I_Gz = ∬ y² dS = %s m⁴ (%s cm⁴) ; I_Gy = ∬ z² dS = %s m⁴ (%s cm⁴)', ...
                fs(P.Iz), fs(P.Iz*1e8), fs(P.Iy), fs(P.Iy*1e8));
            rep{end+1, 1} = sprintf('Produit d''inertie : I_Gyz = ∬ y·z dS = %s m⁴', fs(P.Iyz));
            ecIx = abs(P.IxDirect - (P.Iz + P.Iy)) / max(abs(P.IxDirect), realmin);
            rep{end+1, 1} = sprintf(['Contrôle : Ix = ∬ r² dS = %s m⁴ ; I_Gz + I_Gy = %s m⁴ ' ...
                '(écart relatif %.2g)'], fs(P.IxDirect), fs(P.Iz + P.Iy), ecIx);
            tex = {['$S = \int\!\!\int_S dS = ' GeometryEngine.texNum(P.S) '\ \mathrm{m^2}$']; ...
                ['$y_G = \frac{1}{S}\int\!\!\int_S y_1\,dS = \frac{' GeometryEngine.texNum(P.MO1z) ...
                '}{' GeometryEngine.texNum(P.S) '} = ' GeometryEngine.texNum(P.yG) '\ \mathrm{m}$']; ...
                ['$z_G = \frac{1}{S}\int\!\!\int_S z_1\,dS = \frac{' GeometryEngine.texNum(P.MO1y) ...
                '}{' GeometryEngine.texNum(P.S) '} = ' GeometryEngine.texNum(P.zG) '\ \mathrm{m}$']; ...
                ['$I_{Gz} = \int\!\!\int_S y^2\,dS = ' GeometryEngine.texNum(P.Iz) '\ \mathrm{m^4}$']; ...
                ['$I_{Gy} = \int\!\!\int_S z^2\,dS = ' GeometryEngine.texNum(P.Iy) '\ \mathrm{m^4}$']; ...
                ['$I_{Gyz} = \int\!\!\int_S y\,z\,dS = ' GeometryEngine.texNum(P.Iyz) '\ \mathrm{m^4}$']; ...
                ['$I_x = \int\!\!\int_S r^2\,dS = ' GeometryEngine.texNum(P.IxDirect) ...
                '\ \mathrm{m^4}$']};
            [repC, texC] = GeometryEngine.commonText(P);
            P.report = [rep; repC];
            P.latex = [tex; texC];
        end

        %% =====================================================================================
        %  Valeurs tabulées et comparaison
        %  =====================================================================================

        function P = tabulated(sec)
            %TABULATED Caractéristiques d'un profilé lues dans le catalogue (type 'profile' uniquement).
            %   P = GeometryEngine.tabulated(sec)
            %   sec doit contenir les champs du catalogue (DataManager.getProfile) : h, b, a, e, S,
            %   Iz (axe fort), Iy (axe faible) et, s'ils existent, Wz, Wy, rz, ry, c (UPN/UAP : distance
            %   dos d'âme → G), J ou It (constante de torsion). Les valeurs absentes sont déduites
            %   (rz = sqrt(Iz/S), Wz = Iz/(h/2)…). Rappel : Iz(application) = Iy(Eurocode).
            %   Sortie : mêmes champs que analytical (sans huygens) ; method = 'tabulée'.
            %   Erreur MecaStruct:GeometryEngine:notProfile si sec.type ≠ 'profile'.
            sec = GeometryEngine.validateSection(sec);
            if ~strcmp(sec.type, 'profile')
                error('MecaStruct:GeometryEngine:notProfile', ...
                    ['Les valeurs tabulées n''existent que pour un profilé du catalogue ' ...
                    '(sec.type = ''profile'') ; type fourni : ''%s''.'], sec.type);
            end
            S = GeometryEngine.catField(sec, 'S', 'aire');
            Iz = GeometryEngine.catField(sec, 'Iz', 'moment quadratique axe fort');
            Iy = GeometryEngine.catField(sec, 'Iy', 'moment quadratique axe faible');
            h = sec.h; b = sec.b; a = sec.tw; e = sec.tf;
            notes = {};
            yG = h/2;
            if strcmp(sec.profileShape, 'U')
                c = GeometryEngine.optField(sec, 'c');
                if isfinite(c) && c > 0
                    zG = c;
                else
                    core = GeometryEngine.huygensCore(GeometryEngine.buildPrims(sec));
                    zG = core.zG;
                    notes{end+1, 1} = ['Distance c (dos d''âme → G) absente du catalogue : zG calculé ' ...
                        'sur la géométrie simplifiée.'];
                end
            else
                zG = b/2;
            end
            P = struct();
            P.type = 'profile';
            P.method = 'tabulée';
            P.S = S;
            P.zG = zG;
            P.yG = yG;
            P.MO1z = S*yG;
            P.MO1y = S*zG;
            P.Iz = Iz;
            P.Iy = Iy;
            P.Iyz = 0;
            P.Ix = Iz + Iy;
            [P.I1, P.I2, P.alphaP] = GeometryEngine.principal(Iz, Iy, 0);
            rz = GeometryEngine.optField(sec, 'rz');
            ry = GeometryEngine.optField(sec, 'ry');
            if ~(isfinite(rz) && rz > 0), rz = sqrt(Iz/S); end
            if ~(isfinite(ry) && ry > 0), ry = sqrt(Iy/S); end
            P.rz = rz;
            P.ry = ry;
            P.vyTop = h - yG;
            P.vyBot = yG;
            P.vzRight = b - zG;
            P.vzLeft = zG;
            Wz = GeometryEngine.optField(sec, 'Wz');
            Wy = GeometryEngine.optField(sec, 'Wy');
            if ~(isfinite(Wz) && Wz > 0), Wz = Iz/max(P.vyTop, P.vyBot); end
            if ~(isfinite(Wy) && Wy > 0), Wy = Iy/max(P.vzRight, P.vzLeft); end
            P.Wz = Wz;
            P.Wy = Wy;
            J = GeometryEngine.optField(sec, 'J');
            if ~isfinite(J), J = GeometryEngine.optField(sec, 'It'); end
            if isfinite(J) && J > 0
                P.J = J;
                P.Jmethod = 'valeur du catalogue';
            else
                P.J = NaN;
                P.Jmethod = 'non tabulée (voir la méthode analytique : Σ l·t³/3)';
            end
            if strcmp(sec.profileShape, 'I')
                Sw = (h - 2*e)*a;
                P.k = S/Sw;
                P.ky = Sw/S;
                P.kSource = 'cours';
                kTxt = sprintf(['k = S/S_âme = %s, ky = S_âme/S = %s (S_âme = (h − 2e)·a = %s m², ' ...
                    'S du catalogue)'], GeometryEngine.fs(P.k), GeometryEngine.fs(P.ky), GeometryEngine.fs(Sw));
            else
                f = GeometryEngine.shearFactors(sec);
                P.k = f.kNum;
                P.ky = f.kyNum;
                P.kSource = 'numérique';
                kTxt = sprintf(['k = %s (Jourawski), ky = %s (énergie), calculés sur la géométrie ' ...
                    'simplifiée'], GeometryEngine.fs(P.k), GeometryEngine.fs(P.ky));
            end
            prims = GeometryEngine.buildPrims(sec);
            P.kz = GeometryEngine.shearZ(sec, prims, P.ky);
            kTxt = sprintf('%s ; kz = %s (énergie, effort tranchant Tz, géométrie simplifiée)', kTxt, GeometryEngine.fs(P.kz));
            P.bbox = [0 b 0 h];
            fs = @GeometryEngine.fs;
            rep = {sprintf('Valeurs tabulées du catalogue — %s', GeometryEngine.describeSection(sec))};
            rep{end+1, 1} = ['Convention : Iz (application) = axe fort = Iy (Eurocode) ; ' ...
                'Iy (application) = axe faible = Iz (Eurocode).'];
            rep = [rep; notes];
            rep{end+1, 1} = sprintf('S = %s m² (%s cm²)', fs(S), fs(S*1e4));
            rep{end+1, 1} = sprintf('G : yG = h/2 = %s m ; zG = %s m (repère O1)', fs(yG), fs(zG));
            rep{end+1, 1} = sprintf('Iz = %s m⁴ (%s cm⁴) ; Iy = %s m⁴ (%s cm⁴) ; Iyz = 0 (symétrie)', ...
                fs(Iz), fs(Iz*1e8), fs(Iy), fs(Iy*1e8));
            rep{end+1, 1} = sprintf('Ix = Iz + Iy = %s m⁴', fs(P.Ix));
            rep{end+1, 1} = sprintf('rz = %s m ; ry = %s m', fs(rz), fs(ry));
            rep{end+1, 1} = sprintf('Wz = %s m³ (%s cm³) ; Wy = %s m³ (%s cm³)', fs(Wz), fs(Wz*1e6), ...
                fs(Wy), fs(Wy*1e6));
            rep{end+1, 1} = sprintf('J : %s', P.Jmethod);
            rep{end+1, 1} = ['Cisaillement : ' kTxt];
            P.report = rep;
            P.latex = {['$S = ' GeometryEngine.texNum(S) '\ \mathrm{m^2},\ I_{Gz} = ' ...
                GeometryEngine.texNum(Iz) '\ \mathrm{m^4},\ I_{Gy} = ' GeometryEngine.texNum(Iy) ...
                '\ \mathrm{m^4}$']; ...
                ['$r_z = \sqrt{\frac{I_{Gz}}{S}} = ' GeometryEngine.texNum(rz) '\ \mathrm{m},\ r_y = ' ...
                GeometryEngine.texNum(ry) '\ \mathrm{m}$']; ...
                ['$W_z = ' GeometryEngine.texNum(Wz) '\ \mathrm{m^3},\ W_y = ' GeometryEngine.texNum(Wy) ...
                '\ \mathrm{m^3}$']; ...
                ['$k = ' GeometryEngine.texNum(P.k) ',\ k_y = ' GeometryEngine.texNum(P.ky) '$']};
            P.shear = struct('kCours', NaN, 'kyCours', NaN, 'kNum', NaN, 'kyNum', NaN);
            if strcmp(sec.profileShape, 'I')
                P.shear.kCours = P.k;
                P.shear.kyCours = P.ky;
            else
                P.shear.kNum = P.k;
                P.shear.kyNum = P.ky;
            end
        end

        function C = compare(sec)
            %COMPARE Tableau comparatif des méthodes A (analytique), B (intégrale) et tabulée.
            %   C = GeometryEngine.compare(sec)
            %   Sortie : table, lignes (RowNames) S, yG, zG, Iz, Iy, Iyz, Ix, rz, ry, Wz, Wy ; colonnes
            %   Analytique, Integrale, Tabulee (NaN si la section n'est pas un profilé), EcartMax_pct
            %   (plus grand écart relatif entre les colonnes disponibles, en % ; référence : la plus
            %   grande valeur absolue de la ligne ; pour Iyz : max(Iz, Iy) ; pour yG, zG : plancher
            %   1e-6 × dimension de la section). C.Properties.UserData contient units (cellstr),
            %   analytical, integral, tabulated (structures P) et report (texte, écarts commentés).
            %   Pour un profilé, l'écart analytique (géométrie simplifiée) / catalogue est de quelques
            %   % à cause des congés de raccordement : il est rapporté tel quel.
            sec = GeometryEngine.validateSection(sec);
            A = GeometryEngine.analytical(sec);
            B = GeometryEngine.integral(sec);
            names = {'S', 'yG', 'zG', 'Iz', 'Iy', 'Iyz', 'Ix', 'rz', 'ry', 'Wz', 'Wy'};
            units = {'m^2', 'm', 'm', 'm^4', 'm^4', 'm^4', 'm^4', 'm', 'm', 'm^3', 'm^3'};
            isProfile = strcmp(sec.type, 'profile');
            if isProfile
                T = GeometryEngine.tabulated(sec);
            else
                T = [];
            end
            n = numel(names);
            va = zeros(n, 1); vb = zeros(n, 1); vt = NaN(n, 1);
            ec = zeros(n, 1); ecAB = zeros(n, 1); ecT = zeros(n, 1);
            Lref = max(A.bbox(2) - A.bbox(1), A.bbox(4) - A.bbox(3));
            for k = 1:n
                va(k) = A.(names{k});
                vb(k) = B.(names{k});
                if isProfile
                    vt(k) = T.(names{k});
                end
                vals = [va(k) vb(k) vt(k)];
                vals = vals(~isnan(vals));
                switch names{k}
                    case 'Iyz'
                        den = max([abs(vals), A.Iz, A.Iy]);
                    case {'yG', 'zG'}
                        den = max([abs(vals), 1e-6*Lref]);
                    otherwise
                        den = max(abs(vals));
                end
                if den > 0
                    ec(k) = 100*(max(vals) - min(vals))/den;
                    ecAB(k) = 100*abs(va(k) - vb(k))/den;
                end
                if isProfile && vt(k) ~= 0
                    ecT(k) = 100*abs(va(k) - vt(k))/abs(vt(k));
                end
            end
            C = table(va, vb, vt, ec, 'VariableNames', {'Analytique', 'Integrale', 'Tabulee', ...
                'EcartMax_pct'}, 'RowNames', names);
            rep = {sprintf('Comparaison des méthodes — %s', GeometryEngine.describeSection(sec))};
            rep{end+1, 1} = sprintf('Méthode B : %s.', B.method);
            [mxAB, iAB] = max(ecAB);
            rep{end+1, 1} = sprintf(['Analytique / intégrale : écart relatif maximal %.3g %% (%s) — ' ...
                'les deux méthodes sont exactes et doivent coïncider.'], mxAB, names{iAB});
            if isProfile
                [mxT, iT] = max(ecT);
                rep{end+1, 1} = sprintf(['Catalogue / géométrie simplifiée : écart maximal %.3g %% (%s, ' ...
                    'relatif au catalogue). Écart attendu de quelques %% : les congés de raccordement (r) ' ...
                    'et l''inclinaison éventuelle des ailes ne sont pas modélisés par la géométrie simplifiée.'], ...
                    mxT, names{iT});
                if mxT > 10
                    rep{end+1, 1} = ['Écart supérieur à 10 % : typique des profilés à ailes inclinées (UPN, IPN), ' ...
                        'dont l''épaisseur d''aile e du catalogue est une valeur moyenne ; les grandeurs relatives ' ...
                        'à l''axe faible (zG, Iy, Wy) sont les plus affectées. Utiliser les valeurs tabulées ' ...
                        'pour le dimensionnement.'];
                end
                for k = 1:n
                    if ~strcmp(names{k}, 'Iyz') && vt(k) ~= 0
                        rep{end+1, 1} = sprintf('  %s : analytique %s, catalogue %s %s (écart %+.2f %%)', ...
                            names{k}, GeometryEngine.fs(va(k)), GeometryEngine.fs(vt(k)), units{k}, ...
                            100*(va(k) - vt(k))/vt(k)); %#ok<AGROW>
                    end
                end
            end
            C.Properties.Description = strjoin(rep', ' ');
            C.Properties.UserData = struct('units', {units}, 'analytical', A, 'integral', B, ...
                'tabulated', T, 'report', {rep}, 'ecartAB_pct', max(ecAB));
        end

        %% =====================================================================================
        %  Largeur, moment statique, contours, facteurs de cisaillement
        %  =====================================================================================

        function b = widthAt(sec, y, side)
            %WIDTHAT Largeur b(y) de la section à la cote y mesurée depuis G (vectorisé, exact).
            %   b = GeometryEngine.widthAt(sec, y)
            %   b = GeometryEngine.widthAt(sec, y, side)
            %   y    : cotes depuis G (m), tableau quelconque ; b a la même taille (m).
            %   side : traitement des cotes où la largeur est discontinue (jonction âme/aile, bords) :
            %          'max' (défaut) : plus grande des deux limites (largeur de la section fermée,
            %          ex. jonction âme/aile → largeur de l'aile, bord supérieur → largeur du bord) ;
            %          'dessus' / 'above' : limite par au-dessus (y+) ; 'dessous' / 'below' : limite
            %          par en dessous (y−). En dehors de la section : b = 0.
            if nargin < 3 || isempty(side)
                side = 'max';
            end
            side = GeometryEngine.normalizeSide(side);
            sec = GeometryEngine.validateSection(sec);
            prims = GeometryEngine.buildPrims(sec);
            core = GeometryEngine.huygensCore(prims);
            GeometryEngine.checkNumeric(y, 'y');
            b = GeometryEngine.widthCore(prims, core.yG, double(y), side);
        end

        function Q = firstMomentAbove(sec, y)
            %FIRSTMOMENTABOVE Moment statique par rapport à (G, z) de la partie située au-dessus de y.
            %   Q = GeometryEngine.firstMomentAbove(sec, y)
            %   Q(y) = ∫_{η > y} η dS (η mesuré depuis G), en m³ ; y depuis G (m), vectorisé, exact
            %   (rectangles : formule polynomiale ; disques : segment circulaire
            %   Q = 2/3·(R² − u²)^(3/2) + (yc − yG)·A_segment). Q(0) = moment statique de la demi-section
            %   supérieure ; Q = 0 hors de la section. Exemples : rectangle Q(y) = b/2·(h²/4 − y²) ;
            %   disque Q(y) = 2/3·(R² − y²)^(3/2).
            sec = GeometryEngine.validateSection(sec);
            prims = GeometryEngine.buildPrims(sec);
            core = GeometryEngine.huygensCore(prims);
            GeometryEngine.checkNumeric(y, 'y');
            Q = GeometryEngine.firstMomentCore(prims, core.yG, double(y));
        end

        function out = outline(sec)
            %OUTLINE Contours fermés de la section dans le repère O1 (pour le tracé).
            %   out = GeometryEngine.outline(sec)
            %   out.outer : cell de matrices N×2 [z y] fermées (premier point = dernier), sens
            %               trigonométrique ;
            %   out.holes : cell de contours de trous (sens horaire) ;
            %   out.bbox  : [zmin zmax ymin ymax] (m).
            %   Les cercles sont discrétisés avec 240 segments (≥ 120 points).
            sec = GeometryEngine.validateSection(sec);
            prims = GeometryEngine.buildPrims(sec);
            out = struct('outer', {{}}, 'holes', {{}}, 'bbox', GeometryEngine.bboxPrims(prims));
            nC = 240;
            switch sec.type
                case 'rectangle'
                    out.outer = {GeometryEngine.rectPoly(0, sec.b, 0, sec.h)};
                case 'disque'
                    R = sec.D/2;
                    out.outer = {GeometryEngine.circlePoly(R, R, R, nC)};
                case 'couronne'
                    R = sec.D/2;
                    out.outer = {GeometryEngine.circlePoly(R, R, R, nC)};
                    if sec.d > 0
                        out.holes = {flipud(GeometryEngine.circlePoly(R, R, sec.d/2, nC))};
                    end
                case 'rectangle_creux'
                    t = sec.t;
                    out.outer = {GeometryEngine.rectPoly(0, sec.B, 0, sec.H)};
                    out.holes = {flipud(GeometryEngine.rectPoly(t, sec.B - t, t, sec.H - t))};
                case {'I', 'T', 'U', 'L', 'profile'}
                    out.outer = {GeometryEngine.shapePoly(sec)};
                case 'composite'
                    ps = polyshape();
                    for k = 1:numel(prims)
                        p = prims(k);
                        if p.sign < 0, continue; end
                        ps = union(ps, GeometryEngine.primPolyshape(p, nC));
                    end
                    for k = 1:numel(prims)
                        p = prims(k);
                        if p.sign > 0, continue; end
                        ps = subtract(ps, GeometryEngine.primPolyshape(p, nC));
                    end
                    isH = ishole(ps);
                    for k = 1:numboundaries(ps)
                        [zb, yb] = boundary(ps, k);
                        poly = GeometryEngine.closePoly([zb(:) yb(:)]);
                        if isH(k)
                            out.holes{end+1} = GeometryEngine.orientPoly(poly, false);
                        else
                            out.outer{end+1} = GeometryEngine.orientPoly(poly, true);
                        end
                    end
            end
        end

        function f = shearFactors(sec)
            %SHEARFACTORS Facteurs de cisaillement : k (τmax = k·T/S) et ky (section réduite ky·S).
            %   f = GeometryEngine.shearFactors(sec)
            %   Sortie :
            %     kCours, kyCours : valeurs du cours — rectangle 3/2 et 5/6 ; disque 4/3 et 6/7 ;
            %                       couronne (tube) 4/3·(1 + r·R/(r² + R²)) et 1/2 ; I : S/S_âme et
            %                       S_âme/S (S_âme = tw·(h − 2tf)) ; NaN sinon.
            %     kNum   = τmax·S/T = S·max[Q(y)/b(y)]/Iz (Jourawski τ = T·Q/(Iz·b)) ;
            %     kyNum  = Iz²/(S·∫ Q(y)²/b(y) dy) (égalité des énergies de cisaillement) ;
            %     yAtMax : cote (depuis G) du maximum de τ ; Sweb (I : aire d'âme, NaN sinon) ;
            %     connected (false si b(y) s'annule entre deux parties : kNum = kyNum = NaN) ;
            %     report, latex.
            %   Résultats exacts de l'intégration : rectangle kNum = 3/2, kyNum = 5/6 ; disque kNum = 4/3,
            %   kyNum = 9/10 (la valeur du cours 6/7 provient de la théorie de l'élasticité, Cowper
            %   ν = 0 : écart +5 %, la répartition de Jourawski ne retenant que τxy moyen sur la
            %   largeur) ; couronne kNum = 4/3·(1 + rR/(r² + R²)) exactement, kyNum → 2/3 pour un tube
            %   mince (valeur du cours 1/2 : flux tangent à la paroi). Les valeurs du cours sont
            %   retenues dans P.k / P.ky lorsqu'elles existent (P.kSource = 'cours').
            sec = GeometryEngine.validateSection(sec);
            prims = GeometryEngine.buildPrims(sec);
            core = GeometryEngine.huygensCore(prims);
            f = GeometryEngine.shearCore(sec, prims, core);
        end

        %% =====================================================================================
        %  Utilitaires publics
        %  =====================================================================================

        function sec = fromProfile(p)
            %FROMPROFILE Construit une section 'profile' à partir d'une structure de profilé.
            %   sec = GeometryEngine.fromProfile(p)
            %   p : structure renvoyée par DataManager.getProfile (Family, Name, h, b, a, e, r, S, Iz,
            %   Iy, Wz, Wy, rz, ry, mass, c) ou toute structure contenant au moins h, b, a, e.
            %   Sortie : copie de p avec type = 'profile', family et name renseignés, validée.
            if ~isstruct(p) || ~isscalar(p)
                error('MecaStruct:GeometryEngine:invalidInput', ...
                    'Le profilé doit être une structure scalaire (cf. DataManager.getProfile).');
            end
            sec = p;
            sec.type = 'profile';
            if ~isfield(sec, 'family') && isfield(sec, 'Family')
                sec.family = char(sec.Family);
            end
            if ~isfield(sec, 'name') && isfield(sec, 'Name')
                sec.name = char(sec.Name);
            end
            sec = GeometryEngine.validateSection(sec);
        end

        function T = sectionTypes()
            %SECTIONTYPES Description des types de section reconnus.
            %   T = GeometryEngine.sectionTypes()
            %   Sortie : struct colonne, champs type, label (texte français), fields (cellstr des
            %   dimensions, m), origin (description du repère O1).
            T = struct('type', {'rectangle'; 'disque'; 'couronne'; 'rectangle_creux'; 'I'; 'T'; ...
                'U'; 'L'; 'profile'; 'composite'}, ...
                'label', {'Rectangle plein'; 'Disque plein'; 'Couronne (tube circulaire)'; ...
                'Rectangle creux (caisson)'; 'Profil en I symétrique'; 'Profil en T'; 'Profil en U'; ...
                'Cornière L'; 'Profilé du catalogue'; 'Section composée de rectangles'}, ...
                'fields', {{'b', 'h'}; {'D'}; {'D', 'd'}; {'B', 'H', 't'}; {'h', 'b', 'tw', 'tf'}; ...
                {'h', 'b', 'tw', 'tf'}; {'h', 'b', 'tw', 'tf'}; {'h', 'b', 't'}; ...
                {'family', 'name', 'h', 'b', 'a', 'e', 'S', 'Iz', 'Iy'}; {'rects', 'holes'}}, ...
                'origin', {'coin bas-gauche'; 'coin bas-gauche du carré englobant'; ...
                'coin bas-gauche du carré englobant'; 'coin bas-gauche'; 'coin bas-gauche'; ...
                'coin bas-gauche (aile en haut)'; 'coin bas-gauche (âme à gauche)'; ...
                'angle en bas à gauche'; 'coin bas-gauche'; 'repère utilisateur'});
        end

        function tf = hasSymbolic()
            %HASSYMBOLIC Indique si la Symbolic Math Toolbox est disponible (résultat mis en cache).
            %   tf = GeometryEngine.hasSymbolic()
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

    end

    methods (Static, Access = private)

        %% =====================================================================================
        %  Validation (privé)
        %  =====================================================================================

        function v = dimField(sec, name, label, allowZero)
            % Dimension obligatoire réelle finie strictement positive (ou positive si allowZero).
            if nargin < 4
                allowZero = false;
            end
            if ~isfield(sec, name) || isempty(sec.(name))
                error('MecaStruct:GeometryEngine:missingField', ...
                    'Champ obligatoire manquant : sec.%s (%s, en m).', name, label);
            end
            v = sec.(name);
            if ~isnumeric(v) || ~isscalar(v) || ~isreal(v) || ~isfinite(v) || v < 0 || (v == 0 && ~allowZero)
                error('MecaStruct:GeometryEngine:invalidDimensions', ...
                    'La dimension sec.%s (%s) doit être un réel strictement positif (m).', name, label);
            end
            v = double(v);
        end

        function checkThinWalls(t, h, b, tw, tf)
            % Cohérence des épaisseurs des profils I, T, U.
            switch t
                case 'I'
                    ok = tw <= b && 2*tf < h;
                    msg = 'Profil I : il faut tw ≤ b et 2·tf < h';
                case 'T'
                    ok = tw <= b && tf < h;
                    msg = 'Profil T : il faut tw ≤ b et tf < h';
                otherwise
                    ok = tw < b && 2*tf < h;
                    msg = 'Profil U : il faut tw < b et 2·tf < h';
            end
            if ~ok
                error('MecaStruct:GeometryEngine:invalidDimensions', ...
                    '%s (h = %g m, b = %g m, tw = %g m, tf = %g m).', msg, h, b, tw, tf);
            end
        end

        function sec = resolveProfile(sec)
            % Profilé du catalogue : famille → forme simplifiée I ou U, épaisseurs a, e.
            fam = '';
            if isfield(sec, 'family') && ~isempty(sec.family)
                fam = upper(strtrim(char(sec.family)));
            elseif isfield(sec, 'Family') && ~isempty(sec.Family)
                fam = upper(strtrim(char(sec.Family)));
            end
            nm = '';
            if isfield(sec, 'name') && ~isempty(sec.name)
                nm = char(sec.name);
            elseif isfield(sec, 'Name') && ~isempty(sec.Name)
                nm = char(sec.Name);
            end
            if isempty(fam) && ~isempty(nm)
                tok = regexp(upper(nm), '^\s*([A-Z]+)', 'tokens', 'once');
                if ~isempty(tok), fam = tok{1}; end
            end
            shape = '';
            if isfield(sec, 'profileShape') && ~isempty(sec.profileShape)
                shape = upper(char(sec.profileShape));
            elseif isfield(sec, 'shape') && ~isempty(sec.shape)
                shape = upper(char(sec.shape));
            end
            if ~any(strcmp(shape, {'I', 'U'}))
                if ~isempty(fam)
                    if startsWith(fam, 'U')
                        shape = 'U';
                    else
                        shape = 'I';
                    end
                else
                    c = GeometryEngine.optField(sec, 'c');
                    if isfinite(c)
                        shape = 'U';
                    else
                        shape = 'I';
                    end
                end
            end
            sec.h = GeometryEngine.dimField(sec, 'h', 'hauteur du profilé');
            sec.b = GeometryEngine.dimField(sec, 'b', 'largeur des ailes');
            if isfield(sec, 'a') && ~isempty(sec.a)
                a = GeometryEngine.dimField(sec, 'a', 'épaisseur d''âme');
            else
                a = GeometryEngine.dimField(sec, 'tw', 'épaisseur d''âme a');
            end
            if isfield(sec, 'e') && ~isempty(sec.e)
                e = GeometryEngine.dimField(sec, 'e', 'épaisseur d''aile');
            else
                e = GeometryEngine.dimField(sec, 'tf', 'épaisseur d''aile e');
            end
            GeometryEngine.checkThinWalls(shape, sec.h, sec.b, a, e);
            sec.a = a;
            sec.e = e;
            sec.tw = a;
            sec.tf = e;
            sec.profileShape = shape;
            sec.family = fam;
            sec.name = nm;
        end

        function sec = validateComposite(sec)
            % Section composite : rectangles, trous rectangulaires, disques et trous circulaires.
            rects = GeometryEngine.matField(sec, 'rects', 4);
            holes = GeometryEngine.matField(sec, 'holes', 4);
            disks = GeometryEngine.matField(sec, 'disks', 3);
            dholes = GeometryEngine.matField(sec, 'diskHoles', 3);
            if isempty(rects) && isempty(disks)
                error('MecaStruct:GeometryEngine:missingField', ...
                    'Section composite : sec.rects (N×4 [z1 z2 y1 y2], m) doit contenir au moins un rectangle.');
            end
            allR = [rects; holes];
            if any(allR(:, 2) <= allR(:, 1)) || any(allR(:, 4) <= allR(:, 3))
                error('MecaStruct:GeometryEngine:invalidDimensions', ...
                    'Section composite : chaque rectangle [z1 z2 y1 y2] doit vérifier z2 > z1 et y2 > y1.');
            end
            allD = [disks; dholes];
            if any(allD(:, 3) <= 0)
                error('MecaStruct:GeometryEngine:invalidDimensions', ...
                    'Section composite : chaque disque [zc yc R] doit avoir un rayon R > 0.');
            end
            bb = [Inf -Inf Inf -Inf];
            if ~isempty(rects)
                bb = [min(rects(:, 1)) max(rects(:, 2)) min(rects(:, 3)) max(rects(:, 4))];
            end
            if ~isempty(disks)
                bb = [min(bb(1), min(disks(:, 1) - disks(:, 3))), max(bb(2), max(disks(:, 1) + disks(:, 3))), ...
                    min(bb(3), min(disks(:, 2) - disks(:, 3))), max(bb(4), max(disks(:, 2) + disks(:, 3)))];
            end
            Lref = max(bb(2) - bb(1), bb(4) - bb(3));
            tolA = 1e-10*Lref^2;
            tolL = 1e-9*Lref;
            % matière : pas de chevauchement
            for i = 1:size(rects, 1)
                for j = i+1:size(rects, 1)
                    if GeometryEngine.rectOverlap(rects(i, :), rects(j, :)) > tolA
                        error('MecaStruct:GeometryEngine:overlap', ...
                            'Section composite : les rectangles %d et %d se chevauchent.', i, j);
                    end
                end
                for j = 1:size(disks, 1)
                    if GeometryEngine.rectDiskDistance(rects(i, :), disks(j, 1:2)) < disks(j, 3) - tolL
                        error('MecaStruct:GeometryEngine:overlap', ...
                            'Section composite : le rectangle %d et le disque %d se chevauchent.', i, j);
                    end
                end
            end
            for i = 1:size(disks, 1)
                for j = i+1:size(disks, 1)
                    if hypot(disks(i, 1) - disks(j, 1), disks(i, 2) - disks(j, 2)) < disks(i, 3) + disks(j, 3) - tolL
                        error('MecaStruct:GeometryEngine:overlap', ...
                            'Section composite : les disques %d et %d se chevauchent.', i, j);
                    end
                end
            end
            % trous : contenus dans la matière, sans chevauchement mutuel
            for i = 1:size(holes, 1)
                hA = (holes(i, 2) - holes(i, 1))*(holes(i, 4) - holes(i, 3));
                cov = 0;
                for j = 1:size(rects, 1)
                    cov = cov + GeometryEngine.rectOverlap(holes(i, :), rects(j, :));
                end
                if cov < hA - tolA
                    error('MecaStruct:GeometryEngine:holeOutside', ...
                        'Section composite : le trou rectangulaire %d n''est pas entièrement contenu dans les rectangles.', i);
                end
                for j = i+1:size(holes, 1)
                    if GeometryEngine.rectOverlap(holes(i, :), holes(j, :)) > tolA
                        error('MecaStruct:GeometryEngine:overlap', ...
                            'Section composite : les trous rectangulaires %d et %d se chevauchent.', i, j);
                    end
                end
                for j = 1:size(dholes, 1)
                    if GeometryEngine.rectDiskDistance(holes(i, :), dholes(j, 1:2)) < dholes(j, 3) - tolL
                        error('MecaStruct:GeometryEngine:overlap', ...
                            'Section composite : le trou rectangulaire %d et le trou circulaire %d se chevauchent.', i, j);
                    end
                end
            end
            for i = 1:size(dholes, 1)
                zc = dholes(i, 1); yc = dholes(i, 2); Rh = dholes(i, 3);
                inDisk = false;
                for j = 1:size(disks, 1)
                    if hypot(zc - disks(j, 1), yc - disks(j, 2)) + Rh <= disks(j, 3) + tolL
                        inDisk = true;
                    end
                end
                inRects = false;
                if ~inDisk && ~isempty(rects)
                    [rr, tt] = meshgrid([0 0.25 0.5 0.75 0.9 1]*Rh, linspace(0, 2*pi, 361));
                    zs = zc + rr(:).*cos(tt(:));
                    ys = yc + rr(:).*sin(tt(:));
                    inside = false(size(zs));
                    for j = 1:size(rects, 1)
                        inside = inside | (zs >= rects(j, 1) - tolL & zs <= rects(j, 2) + tolL & ...
                            ys >= rects(j, 3) - tolL & ys <= rects(j, 4) + tolL);
                    end
                    inRects = all(inside);
                end
                if ~inDisk && ~inRects
                    error('MecaStruct:GeometryEngine:holeOutside', ...
                        'Section composite : le trou circulaire %d n''est pas entièrement contenu dans la matière.', i);
                end
                for j = i+1:size(dholes, 1)
                    if hypot(zc - dholes(j, 1), yc - dholes(j, 2)) < Rh + dholes(j, 3) - tolL
                        error('MecaStruct:GeometryEngine:overlap', ...
                            'Section composite : les trous circulaires %d et %d se chevauchent.', i, j);
                    end
                end
            end
            sec.rects = rects;
            sec.holes = holes;
            sec.disks = disks;
            sec.diskHoles = dholes;
        end

        function M = matField(sec, name, nc)
            % Matrice optionnelle à nc colonnes (vide si absente).
            if ~isfield(sec, name) || isempty(sec.(name))
                M = zeros(0, nc);
                return;
            end
            M = sec.(name);
            if ~isnumeric(M) || ~ismatrix(M) || size(M, 2) ~= nc || ~isreal(M) || any(~isfinite(M(:)))
                error('MecaStruct:GeometryEngine:invalidDimensions', ...
                    'Section composite : sec.%s doit être une matrice réelle finie à %d colonnes (m).', name, nc);
            end
            M = double(M);
        end

        function a = rectOverlap(r1, r2)
            % Aire de l'intersection de deux rectangles [z1 z2 y1 y2].
            a = max(0, min(r1(2), r2(2)) - max(r1(1), r2(1))) * max(0, min(r1(4), r2(4)) - max(r1(3), r2(3)));
        end

        function d = rectDiskDistance(r, c)
            % Distance du centre c = [zc yc] au rectangle r (0 si le centre est dans le rectangle).
            dz = max([r(1) - c(1), 0, c(1) - r(2)]);
            dy = max([r(3) - c(2), 0, c(2) - r(4)]);
            d = hypot(dz, dy);
        end

        function v = catField(sec, name, label)
            % Valeur obligatoire du catalogue (profilé).
            v = GeometryEngine.optField(sec, name);
            if ~(isfinite(v) && v > 0)
                error('MecaStruct:GeometryEngine:missingField', ...
                    'Valeur du catalogue manquante ou invalide : sec.%s (%s, SI).', name, label);
            end
        end

        function v = optField(sec, name)
            % Valeur numérique scalaire optionnelle (NaN si absente ou invalide).
            v = NaN;
            if isfield(sec, name)
                x = sec.(name);
                if isnumeric(x) && isscalar(x) && isreal(x)
                    v = double(x);
                end
            end
        end

        function checkNumeric(y, name)
            % Tableau numérique réel.
            if ~isnumeric(y) || ~isreal(y)
                error('MecaStruct:GeometryEngine:invalidInput', ...
                    'L''argument %s doit être un tableau numérique réel (m, depuis G).', name);
            end
        end

        function mode = normalizeMode(mode)
            % Mode d'intégration : 'symbolique' ou 'numerique'.
            if ~(ischar(mode) || (isstring(mode) && isscalar(mode)))
                error('MecaStruct:GeometryEngine:unknownMode', ...
                    'Le mode d''intégration doit être ''symbolique'' ou ''numerique''.');
            end
            key = lower(strtrim(char(mode)));
            switch key
                case {'symbolique', 'symbolic', 'sym', 'exacte', 'exact', 'int'}
                    mode = 'symbolique';
                case {'numerique', 'numérique', 'numeric', 'num', 'integral2'}
                    mode = 'numerique';
                otherwise
                    error('MecaStruct:GeometryEngine:unknownMode', ...
                        'Mode d''intégration inconnu : ''%s'' (''symbolique'' ou ''numerique'').', key);
            end
        end

        function side = normalizeSide(side)
            % Côté de la limite pour widthAt.
            if ~(ischar(side) || (isstring(side) && isscalar(side)))
                error('MecaStruct:GeometryEngine:invalidInput', ...
                    'L''option side doit être ''max'', ''dessus'' ou ''dessous''.');
            end
            switch lower(strtrim(char(side)))
                case {'max', 'ferme', 'fermé', 'closure'}
                    side = 'max';
                case {'dessus', 'above', 'haut', 'plus', '+'}
                    side = 'above';
                case {'dessous', 'below', 'bas', 'moins', '-'}
                    side = 'below';
                otherwise
                    error('MecaStruct:GeometryEngine:invalidInput', ...
                        'Option side inconnue : ''%s'' (''max'', ''dessus'' ou ''dessous'').', char(side));
            end
        end

        %% =====================================================================================
        %  Primitives (privé)
        %  =====================================================================================

        function prims = buildPrims(sec)
            % Décomposition (sec déjà validée).
            prims = struct('kind', {}, 'sign', {}, 'z1', {}, 'z2', {}, 'y1', {}, 'y2', {}, ...
                'zc', {}, 'yc', {}, 'R', {}, 'Ri', {}, 'label', {});
            switch sec.type
                case 'rectangle'
                    prims = GeometryEngine.addRect(prims, 0, sec.b, 0, sec.h, 1, 'Rectangle');
                case 'disque'
                    R = sec.D/2;
                    prims = GeometryEngine.addDisk(prims, 'disk', R, R, R, 0, 1, 'Disque');
                case 'couronne'
                    R = sec.D/2;
                    prims = GeometryEngine.addDisk(prims, 'annulus', R, R, R, sec.d/2, 1, 'Couronne');
                case 'rectangle_creux'
                    t = sec.t;
                    prims = GeometryEngine.addRect(prims, 0, sec.B, 0, sec.H, 1, 'Rectangle extérieur');
                    prims = GeometryEngine.addRect(prims, t, sec.B - t, t, sec.H - t, -1, 'Évidement intérieur');
                case 'I'
                    prims = GeometryEngine.primsI(prims, sec.h, sec.b, sec.tw, sec.tf);
                case 'T'
                    h = sec.h; b = sec.b; tw = sec.tw; tf = sec.tf;
                    prims = GeometryEngine.addRect(prims, (b - tw)/2, (b + tw)/2, 0, h - tf, 1, 'Âme');
                    prims = GeometryEngine.addRect(prims, 0, b, h - tf, h, 1, 'Aile');
                case 'U'
                    prims = GeometryEngine.primsU(prims, sec.h, sec.b, sec.tw, sec.tf);
                case 'L'
                    h = sec.h; b = sec.b; t = sec.t;
                    prims = GeometryEngine.addRect(prims, 0, t, 0, h, 1, 'Aile verticale');
                    prims = GeometryEngine.addRect(prims, t, b, 0, t, 1, 'Aile horizontale');
                case 'profile'
                    if strcmp(sec.profileShape, 'U')
                        prims = GeometryEngine.primsU(prims, sec.h, sec.b, sec.tw, sec.tf);
                    else
                        prims = GeometryEngine.primsI(prims, sec.h, sec.b, sec.tw, sec.tf);
                    end
                case 'composite'
                    for k = 1:size(sec.rects, 1)
                        r = sec.rects(k, :);
                        prims = GeometryEngine.addRect(prims, r(1), r(2), r(3), r(4), 1, sprintf('Rectangle %d', k));
                    end
                    for k = 1:size(sec.disks, 1)
                        d = sec.disks(k, :);
                        prims = GeometryEngine.addDisk(prims, 'disk', d(1), d(2), d(3), 0, 1, sprintf('Disque %d', k));
                    end
                    for k = 1:size(sec.holes, 1)
                        r = sec.holes(k, :);
                        prims = GeometryEngine.addRect(prims, r(1), r(2), r(3), r(4), -1, sprintf('Trou %d', k));
                    end
                    for k = 1:size(sec.diskHoles, 1)
                        d = sec.diskHoles(k, :);
                        prims = GeometryEngine.addDisk(prims, 'disk', d(1), d(2), d(3), 0, -1, ...
                            sprintf('Trou circulaire %d', k));
                    end
            end
            prims = prims(:);
        end

        function prims = primsI(prims, h, b, tw, tf)
            % Profil I symétrique : aile inférieure, âme, aile supérieure.
            prims = GeometryEngine.addRect(prims, 0, b, 0, tf, 1, 'Aile inférieure');
            prims = GeometryEngine.addRect(prims, (b - tw)/2, (b + tw)/2, tf, h - tf, 1, 'Âme');
            prims = GeometryEngine.addRect(prims, 0, b, h - tf, h, 1, 'Aile supérieure');
        end

        function prims = primsU(prims, h, b, tw, tf)
            % Profil U : âme à gauche (pleine hauteur), ailes vers la droite.
            prims = GeometryEngine.addRect(prims, 0, tw, 0, h, 1, 'Âme');
            prims = GeometryEngine.addRect(prims, tw, b, 0, tf, 1, 'Aile inférieure');
            prims = GeometryEngine.addRect(prims, tw, b, h - tf, h, 1, 'Aile supérieure');
        end

        function prims = addRect(prims, z1, z2, y1, y2, sg, label)
            % Ajoute un rectangle [z1 z2] × [y1 y2].
            p = struct('kind', 'rect', 'sign', sg, 'z1', z1, 'z2', z2, 'y1', y1, 'y2', y2, ...
                'zc', (z1 + z2)/2, 'yc', (y1 + y2)/2, 'R', NaN, 'Ri', NaN, 'label', label);
            if isempty(prims)
                prims = p;
            else
                prims(end+1, 1) = p;
            end
        end

        function prims = addDisk(prims, kind, zc, yc, R, Ri, sg, label)
            % Ajoute un disque ou une couronne de centre (zc, yc).
            p = struct('kind', kind, 'sign', sg, 'z1', zc - R, 'z2', zc + R, 'y1', yc - R, 'y2', yc + R, ...
                'zc', zc, 'yc', yc, 'R', R, 'Ri', Ri, 'label', label);
            if isempty(prims)
                prims = p;
            else
                prims(end+1, 1) = p;
            end
        end

        function [A, zc, yc, Igz, Igy] = primProps(p)
            % Aire et moments quadratiques propres (non signés) d'une primitive.
            switch p.kind
                case 'rect'
                    w = p.z2 - p.z1;
                    hh = p.y2 - p.y1;
                    A = w*hh;
                    Igz = w*hh^3/12;
                    Igy = hh*w^3/12;
                case 'disk'
                    A = pi*p.R^2;
                    Igz = pi*p.R^4/4;
                    Igy = Igz;
                otherwise
                    A = pi*(p.R^2 - p.Ri^2);
                    Igz = pi*(p.R^4 - p.Ri^4)/4;
                    Igy = Igz;
            end
            zc = p.zc;
            yc = p.yc;
        end

        function bb = bboxPrims(prims)
            % Boîte englobante [zmin zmax ymin ymax] de la matière.
            pos = prims([prims.sign] > 0);
            bb = [min([pos.z1]) max([pos.z2]) min([pos.y1]) max([pos.y2])];
        end

        function L = refLength(prims)
            % Dimension caractéristique (plus grand côté de la boîte englobante).
            bb = GeometryEngine.bboxPrims(prims);
            L = max(bb(2) - bb(1), bb(4) - bb(3));
        end

        function lev = levels(prims)
            % Cotes y (repère O1) où la largeur b(y) change de loi.
            lev = zeros(1, 0);
            for k = 1:numel(prims)
                p = prims(k);
                switch p.kind
                    case 'rect'
                        lev = [lev, p.y1, p.y2]; %#ok<AGROW>
                    otherwise
                        lev = [lev, p.yc - p.R, p.yc + p.R]; %#ok<AGROW>
                        if p.Ri > 0
                            lev = [lev, p.yc - p.Ri, p.yc + p.Ri]; %#ok<AGROW>
                        end
                end
            end
            lev = sort(lev);
            L = GeometryEngine.refLength(prims);
            keep = [true, diff(lev) > 1e-12*L];
            lev = lev(keep);
        end

        %% =====================================================================================
        %  Calculs (privé)
        %  =====================================================================================

        function core = huygensCore(prims)
            % Moments statiques, barycentre et théorème de Huygens (valeurs signées).
            n = numel(prims);
            Si = zeros(n, 1); zc = zeros(n, 1); yc = zeros(n, 1); IGz = zeros(n, 1); IGy = zeros(n, 1);
            sg = [prims.sign]';
            for k = 1:n
                [Si(k), zc(k), yc(k), IGz(k), IGy(k)] = GeometryEngine.primProps(prims(k));
            end
            Ss = sg.*Si;
            S = sum(Ss);
            if ~(S > 0)
                error('MecaStruct:GeometryEngine:invalidDimensions', ...
                    'L''aire nette de la section est nulle ou négative (S = %g m²).', S);
            end
            MO1z = sum(Ss.*yc);
            MO1y = sum(Ss.*zc);
            yG = MO1z/S;
            zG = MO1y/S;
            dy = yc - yG;
            dz = zc - zG;
            Lref = GeometryEngine.refLength(prims);
            dy(abs(dy) <= 1e-12*Lref) = 0;   % résidus d'arrondi (éléments centrés sur G)
            dz(abs(dz) <= 1e-12*Lref) = 0;
            IGzs = sg.*IGz;
            IGys = sg.*IGy;
            SDy2 = Ss.*dy.^2;
            SDz2 = Ss.*dz.^2;
            SDyDz = Ss.*dy.*dz;
            Izi = IGzs + SDy2;
            Iyi = IGys + SDz2;
            core = struct('S', S, 'MO1z', MO1z, 'MO1y', MO1y, 'yG', yG, 'zG', zG, ...
                'Iz', sum(Izi), 'Iy', sum(Iyi), 'Iyz', sum(SDyDz));
            core = GeometryEngine.cleanIyz(core);
            Label = {prims.label}';
            core.table = table(Label, Ss, zc, yc, IGzs, IGys, dy, dz, SDy2, SDz2, Izi, Iyi, SDyDz, ...
                'VariableNames', {'Label', 'S_i', 'zG_i', 'yG_i', 'IGz_i', 'IGy_i', 'dy_i', 'dz_i', ...
                'SDy2', 'SDz2', 'Iz_i', 'Iy_i', 'SDyDz'});
        end

        function core = cleanIyz(core)
            % Annule un produit d'inertie résiduel (arrondi) pour une section symétrique.
            if abs(core.Iyz) <= 1e-12*max(abs(core.Iz), abs(core.Iy))
                core.Iyz = 0;
            end
        end

        function [core, rep, tex] = closedForm(sec, core)
            % Formules fermées des sections élémentaires (rapport + LaTeX) ; vide sinon.
            rep = {};
            tex = {};
            fs = @GeometryEngine.fs;
            tn = @GeometryEngine.texNum;
            switch sec.type
                case 'rectangle'
                    b = sec.b; h = sec.h;
                    S = b*h; Iz = b*h^3/12; Iy = h*b^3/12;
                    rep = {sprintf('S = b·h = %s × %s = %s m² (%s cm²)', fs(b), fs(h), fs(S), fs(S*1e4)); ...
                        sprintf('G au centre : zG = b/2 = %s m ; yG = h/2 = %s m', fs(b/2), fs(h/2)); ...
                        sprintf('I_Gz = b·h³/12 = %s m⁴ (%s cm⁴)', fs(Iz), fs(Iz*1e8)); ...
                        sprintf('I_Gy = h·b³/12 = %s m⁴ (%s cm⁴)', fs(Iy), fs(Iy*1e8)); ...
                        'I_Gyz = 0 (deux axes de symétrie)'};
                    tex = {['$S = b\,h = ' tn(b) ' \times ' tn(h) ' = ' tn(S) '\ \mathrm{m^2}$']; ...
                        ['$z_G = \frac{b}{2} = ' tn(b/2) '\ \mathrm{m},\ y_G = \frac{h}{2} = ' tn(h/2) '\ \mathrm{m}$']; ...
                        ['$I_{Gz} = \frac{b\,h^3}{12} = ' tn(Iz) '\ \mathrm{m^4}$']; ...
                        ['$I_{Gy} = \frac{h\,b^3}{12} = ' tn(Iy) '\ \mathrm{m^4}$']};
                    zG = b/2; yG = h/2;
                case 'disque'
                    D = sec.D;
                    S = pi*D^2/4; Iz = pi*D^4/64; Iy = Iz;
                    rep = {sprintf('S = π·D²/4 = %s m² (%s cm²)', fs(S), fs(S*1e4)); ...
                        sprintf('G au centre : zG = yG = D/2 = %s m', fs(D/2)); ...
                        sprintf('I_Gz = I_Gy = π·D⁴/64 = %s m⁴ (%s cm⁴)', fs(Iz), fs(Iz*1e8)); ...
                        sprintf('Ix = π·D⁴/32 = %s m⁴', fs(2*Iz))};
                    tex = {['$S = \frac{\pi D^2}{4} = ' tn(S) '\ \mathrm{m^2}$']; ...
                        ['$I_{Gz} = I_{Gy} = \frac{\pi D^4}{64} = ' tn(Iz) '\ \mathrm{m^4}$']; ...
                        ['$I_x = \frac{\pi D^4}{32} = ' tn(2*Iz) '\ \mathrm{m^4}$']};
                    zG = D/2; yG = D/2;
                case 'couronne'
                    D = sec.D; d = sec.d; m = d/D;
                    S = pi*D^2/4*(1 - m^2); Iz = pi*D^4/64*(1 - m^4); Iy = Iz;
                    rep = {sprintf('m = d/D = %s', fs(m)); ...
                        sprintf('S = π·D²/4·(1 − m²) = %s m² (%s cm²)', fs(S), fs(S*1e4)); ...
                        sprintf('G au centre : zG = yG = D/2 = %s m', fs(D/2)); ...
                        sprintf('I_Gz = I_Gy = π·D⁴/64·(1 − m⁴) = %s m⁴ (%s cm⁴)', fs(Iz), fs(Iz*1e8)); ...
                        sprintf('Ix = π·D⁴/32·(1 − m⁴) = %s m⁴', fs(2*Iz))};
                    tex = {['$m = \frac{d}{D} = ' tn(m) '$']; ...
                        ['$S = \frac{\pi D^2}{4}\left(1 - m^2\right) = ' tn(S) '\ \mathrm{m^2}$']; ...
                        ['$I_{Gz} = I_{Gy} = \frac{\pi D^4}{64}\left(1 - m^4\right) = ' tn(Iz) '\ \mathrm{m^4}$']; ...
                        ['$I_x = \frac{\pi D^4}{32}\left(1 - m^4\right) = ' tn(2*Iz) '\ \mathrm{m^4}$']};
                    zG = D/2; yG = D/2;
                case 'rectangle_creux'
                    B = sec.B; H = sec.H; t = sec.t;
                    bi = B - 2*t; hi = H - 2*t;
                    S = B*H - bi*hi; Iz = (B*H^3 - bi*hi^3)/12; Iy = (H*B^3 - hi*bi^3)/12;
                    rep = {sprintf('Rectangle extérieur B×H moins évidement (B − 2t)×(H − 2t) = %s × %s m', fs(bi), fs(hi)); ...
                        sprintf('S = B·H − (B − 2t)(H − 2t) = %s m² (%s cm²)', fs(S), fs(S*1e4)); ...
                        sprintf('G au centre : zG = B/2 = %s m ; yG = H/2 = %s m', fs(B/2), fs(H/2)); ...
                        sprintf('I_Gz = [B·H³ − (B − 2t)(H − 2t)³]/12 = %s m⁴ (%s cm⁴)', fs(Iz), fs(Iz*1e8)); ...
                        sprintf('I_Gy = [H·B³ − (H − 2t)(B − 2t)³]/12 = %s m⁴ (%s cm⁴)', fs(Iy), fs(Iy*1e8)); ...
                        'I_Gyz = 0 (deux axes de symétrie)'};
                    tex = {['$S = B\,H - (B-2t)(H-2t) = ' tn(S) '\ \mathrm{m^2}$']; ...
                        ['$I_{Gz} = \frac{B\,H^3 - (B-2t)(H-2t)^3}{12} = ' tn(Iz) '\ \mathrm{m^4}$']; ...
                        ['$I_{Gy} = \frac{H\,B^3 - (H-2t)(B-2t)^3}{12} = ' tn(Iy) '\ \mathrm{m^4}$']};
                    zG = B/2; yG = H/2;
                otherwise
                    return;
            end
            core.S = S;
            core.zG = zG;
            core.yG = yG;
            core.MO1z = S*yG;
            core.MO1y = S*zG;
            core.Iz = Iz;
            core.Iy = Iy;
            core.Iyz = 0;
        end

        function P = assembleP(sec, prims, core, method)
            % Champs communs des méthodes analytique et intégrale.
            P = struct();
            P.type = sec.type;
            P.method = method;
            P.S = core.S;
            P.zG = core.zG;
            P.yG = core.yG;
            P.MO1z = core.MO1z;
            P.MO1y = core.MO1y;
            P.Iz = core.Iz;
            P.Iy = core.Iy;
            P.Iyz = core.Iyz;
            P.Ix = core.Iz + core.Iy;
            [P.I1, P.I2, P.alphaP] = GeometryEngine.principal(core.Iz, core.Iy, core.Iyz);
            P.rz = sqrt(core.Iz/core.S);
            P.ry = sqrt(core.Iy/core.S);
            bb = GeometryEngine.bboxPrims(prims);
            P.vyTop = bb(4) - core.yG;
            P.vyBot = core.yG - bb(3);
            P.vzRight = bb(2) - core.zG;
            P.vzLeft = core.zG - bb(1);
            P.Wz = core.Iz/max(P.vyTop, P.vyBot);
            P.Wy = core.Iy/max(P.vzRight, P.vzLeft);
            [P.J, P.Jmethod, P.Jlatex] = GeometryEngine.torsionConstant(sec, prims);
            f = GeometryEngine.shearCore(sec, prims, core);
            if ~isnan(f.kCours)
                P.k = f.kCours;
                P.ky = f.kyCours;
                P.kSource = 'cours';
            else
                P.k = f.kNum;
                P.ky = f.kyNum;
                P.kSource = 'numérique';
            end
            P.kz = GeometryEngine.shearZ(sec, prims, P.ky);
            P.shear = f;
            P.bbox = bb;
            P.report = {};
            P.latex = {};
        end

        function [I1, I2, alphaP] = principal(Iz, Iy, Iyz)
            % Moments principaux (I1 ≥ I2) et angle de l'axe 1 depuis z :
            % I(α) = Iz cos²α + Iy sin²α − 2 Iyz sinα cosα ; tan 2α = −2 Iyz/(Iz − Iy).
            m = (Iz + Iy)/2;
            R = hypot((Iz - Iy)/2, Iyz);
            I1 = m + R;
            I2 = m - R;
            if R <= 1e-12*abs(m)
                alphaP = 0;
            elseif Iyz == 0
                if Iz >= Iy
                    alphaP = 0;
                else
                    alphaP = pi/2;
                end
            else
                alphaP = 0.5*atan2(-2*Iyz, Iz - Iy);
            end
        end

        function [J, txt, tex] = torsionConstant(sec, prims)
            % Constante de torsion J selon le type de section.
            tn = @GeometryEngine.texNum;
            switch sec.type
                case 'rectangle'
                    [J, txt, tex] = GeometryEngine.saintVenant(sec.b, sec.h);
                case 'disque'
                    J = pi*sec.D^4/32;
                    txt = 'exacte : J = Ix = π·D⁴/32';
                    tex = ['$J = I_x = \frac{\pi D^4}{32} = ' tn(J) '\ \mathrm{m^4}$'];
                case 'couronne'
                    J = pi*(sec.D^4 - sec.d^4)/32;
                    txt = 'exacte : J = Ix = π·(D⁴ − d⁴)/32';
                    tex = ['$J = I_x = \frac{\pi \left(D^4 - d^4\right)}{32} = ' tn(J) '\ \mathrm{m^4}$'];
                case 'rectangle_creux'
                    t = sec.t;
                    Am = (sec.B - t)*(sec.H - t);
                    pm = 2*((sec.B - t) + (sec.H - t));
                    J = 4*Am^2*t/pm;
                    txt = sprintf(['Bredt (caisson mince) : J = 4·Am²·t/pm avec Am = (B − t)(H − t) = %s m², ' ...
                        'pm = 2[(B − t) + (H − t)] = %s m'], GeometryEngine.fs(Am), GeometryEngine.fs(pm));
                    tex = ['$J = \frac{4\,A_m^2\,t}{p_m} = \frac{4 \times ' tn(Am) '^2 \times ' tn(t) '}{' ...
                        tn(pm) '} = ' tn(J) '\ \mathrm{m^4}$'];
                case {'I', 'T', 'U', 'L', 'profile'}
                    [J, txt, tex] = GeometryEngine.openThinWalled(prims);
                otherwise
                    hasHoles = any([prims.sign] < 0);
                    hasDisks = any(~strcmp({prims.kind}, 'rect'));
                    if hasHoles || hasDisks
                        J = NaN;
                        txt = ['non calculée (section composite avec trou(s) ou disque(s) : ' ...
                            'section fermée ou massive, aucune formule simple)'];
                        tex = '$J : \mathrm{non\ calculee}$';
                    elseif isscalar(prims)
                        [J, txt, tex] = GeometryEngine.saintVenant(prims(1).z2 - prims(1).z1, ...
                            prims(1).y2 - prims(1).y1);
                    else
                        % Σ l·t³/3 ne vaut que pour des parois minces formant une section ouverte
                        w = [prims.z2] - [prims.z1];
                        hh = [prims.y2] - [prims.y1];
                        ps = polyshape();
                        for k = 1:numel(prims)
                            ps = union(ps, polyshape([prims(k).z1 prims(k).z2 prims(k).z2 prims(k).z1], ...
                                [prims(k).y1 prims(k).y1 prims(k).y2 prims(k).y2]));
                        end
                        if any(min(w, hh)./max(w, hh) > 0.2) || ps.NumHoles > 0
                            J = NaN;
                            txt = ['non calculée (rectangles épais ou formant un contour fermé : ' ...
                                'la formule des parois minces ouvertes ne s''applique pas)'];
                            tex = '$J : \mathrm{non\ calculee}$';
                        else
                            [J, txt, tex] = GeometryEngine.openThinWalled(prims);
                        end
                    end
            end
        end

        function [J, txt, tex] = saintVenant(b, h)
            % Rectangle plein (Saint-Venant, série) : a = grand côté, c = petit côté.
            a = max(b, h);
            c = min(b, h);
            n = 1:2:199;
            s = sum(tanh(n*pi*a/(2*c))./n.^5);
            J = a*c^3/3*(1 - 192*c/(pi^5*a)*s);
            beta = J/(a*c^3);
            txt = sprintf(['Saint-Venant (rectangle plein, a = %s m, c = %s m, série de 100 termes) : ' ...
                'J = β·a·c³ avec β = %.5f'], GeometryEngine.fs(a), GeometryEngine.fs(c), beta);
            tex = ['$J = \frac{a\,c^3}{3}\left[1 - \frac{192\,c}{\pi^5 a}\sum_{n\ impair} \frac{1}{n^5}' ...
                '\tanh\frac{n \pi a}{2 c}\right] = ' GeometryEngine.texNum(beta, 4) ' \times a\,c^3 = ' ...
                GeometryEngine.texNum(J) '\ \mathrm{m^4}$'];
        end

        function [J, txt, tex] = openThinWalled(prims)
            % Section ouverte à parois minces : J ≈ Σ l·t³/3.
            J = 0;
            for k = 1:numel(prims)
                p = prims(k);
                w = p.z2 - p.z1;
                hh = p.y2 - p.y1;
                J = J + max(w, hh)*min(w, hh)^3/3;
            end
            txt = sprintf(['parois minces ouvertes : J ≈ Σ l_i·t_i³/3 sur les %d rectangles ' ...
                '(l = grand côté, t = épaisseur)'], numel(prims));
            tex = ['$J \approx \sum \frac{l_i\,t_i^3}{3} = ' GeometryEngine.texNum(J) '\ \mathrm{m^4}$'];
        end

        function f = shearCore(sec, prims, core)
            % Facteurs de cisaillement (cours, Jourawski, énergie).
            S = core.S;
            Iz = core.Iz;
            yG = core.yG;
            fs = @GeometryEngine.fs;
            tn = @GeometryEngine.texNum;
            [kC, kyC, Sweb, courseTxt] = GeometryEngine.courseShear(sec, core);
            Lref = GeometryEngine.refLength(prims);
            tolW = 1e-12*Lref;
            lev = GeometryEngine.levels(prims);
            yb = lev - yG;
            connected = true;
            % étranglement : largeur nulle (d'un côté) à une cote intérieure où Q ≠ 0
            % (parties disjointes ou contact ponctuel, ex. disque posé sur un rectangle)
            bb = GeometryEngine.bboxPrims(prims);
            for k = 1:numel(lev)
                if lev(k) > bb(3) + tolW && lev(k) < bb(4) - tolW
                    bA = GeometryEngine.widthCore(prims, yG, yb(k), 'above');
                    bB = GeometryEngine.widthCore(prims, yG, yb(k), 'below');
                    if min(bA, bB) <= tolW && ...
                            abs(GeometryEngine.firstMomentCore(prims, yG, yb(k))) > 1e-9*S*Lref
                        connected = false;
                    end
                end
            end
            bestR = -Inf;
            yBest = NaN;
            intQ2b = 0;
            absTol = 1e-15*Iz^2/S;
            for k = 1:numel(yb) - 1
                a = yb(k);
                c = yb(k+1);
                if c - a <= tolW
                    continue;
                end
                if GeometryEngine.widthCore(prims, yG, (a + c)/2, 'above') <= tolW
                    connected = false;
                    continue;
                end
                t = linspace(a, c, 201);
                if a < 0 && c > 0
                    t = unique([t, 0]);
                end
                bt = GeometryEngine.widthCore(prims, yG, t, 'above');
                bt(end) = GeometryEngine.widthCore(prims, yG, c, 'below');
                Qt = GeometryEngine.firstMomentCore(prims, yG, t);
                rt = zeros(size(t));
                ok = bt > tolW;
                rt(ok) = Qt(ok)./bt(ok);
                [rmax, im] = max(rt);
                ym = t(im);
                lo = t(max(im - 1, 1));
                hi = t(min(im + 1, numel(t)));
                if hi > lo
                    g = @(x) -GeometryEngine.firstMomentCore(prims, yG, x) ./ ...
                        max(GeometryEngine.widthCore(prims, yG, x, 'above'), tolW);
                    [xo, fo] = fminbnd(g, lo, hi, optimset('TolX', 1e-12*Lref, 'Display', 'off'));
                    if -fo > rmax
                        rmax = -fo;
                        ym = xo;
                    end
                end
                if rmax > bestR
                    bestR = rmax;
                    yBest = ym;
                end
                fun = @(x) GeometryEngine.q2b(prims, yG, x, tolW);
                intQ2b = intQ2b + integral(fun, a, c, 'RelTol', 1e-12, 'AbsTol', absTol);
            end
            if connected && isfinite(bestR) && intQ2b > 0
                kNum = S*bestR/Iz;
                kyNum = Iz^2/(S*intQ2b);
                if abs(yBest) <= 1e-9*Lref
                    yBest = 0;
                end
            else
                kNum = NaN;
                kyNum = NaN;
                yBest = NaN;
            end
            f = struct();
            f.kCours = kC;
            f.kyCours = kyC;
            f.kNum = kNum;
            f.kyNum = kyNum;
            f.yAtMax = yBest;
            f.Sweb = Sweb;
            f.connected = connected;
            rep = {'Facteurs de cisaillement (effort tranchant Ty, flexion autour de z)'};
            rep{end+1, 1} = ['Valeurs du cours : ' courseTxt];
            if connected
                rep{end+1, 1} = sprintf(['Jourawski : τ(y) = T·Q(y)/(Iz·b(y)) ; maximum de Q/b en y = %s m ' ...
                    '(depuis G) : kNum = S·Q/(Iz·b) = %s'], fs(yBest), fs(kNum));
                rep{end+1, 1} = sprintf(['Énergie : 1/(ky·S) = ∫ Q(y)²/(Iz²·b(y)) dy ⇒ kyNum = Iz²/(S·∫ Q²/b dy) ' ...
                    '= %s (∫ Q²/b dy = %s m⁶)'], fs(kyNum), fs(intQ2b));
            else
                rep{end+1, 1} = ['Section non connexe ou à contact ponctuel selon y (b(y) nulle entre deux ' ...
                    'parties alors que Q ≠ 0) : Jourawski non applicable, kNum = kyNum = NaN.'];
            end
            switch sec.type
                case 'disque'
                    rep{end+1, 1} = sprintf(['Disque : l''intégration exacte donne kyNum = 9/10 = %s (1/ky = 10/9) ; ' ...
                        'valeur du cours 6/7 = %s (écart %.2f %%) : 6/7 résulte de la théorie de l''élasticité ' ...
                        '(Cowper, ν = 0), alors que la répartition de Jourawski ne retient que τxy moyen sur ' ...
                        'la largeur et néglige τxz.'], fs(kyNum), fs(6/7), 100*(kyNum - 6/7)/(6/7));
                case 'rectangle'
                    rep{end+1, 1} = 'Rectangle : kNum = 3/2 et kyNum = 5/6 exactement (valeurs du cours).';
                case 'couronne'
                    rep{end+1, 1} = sprintf(['Couronne : kNum coïncide exactement avec 4/3·(1 + rR/(r² + R²)) ; ' ...
                        'kyNum = %s tend vers 2/3 pour un tube mince : la formule énergétique ne retient que ' ...
                        'τxy moyen sur la largeur horizontale b(y), alors que la valeur 1/2 du cours suppose ' ...
                        'un flux de cisaillement tangent à la paroi (τxz pris en compte en haut et en bas).'], ...
                        fs(kyNum));
                case {'I', 'profile'}
                    if ~isnan(kC)
                        rep{end+1, 1} = sprintf(['Profil en I : la formule du cours (S/S_âme) suppose τ uniforme ' ...
                            'dans l''âme ; Jourawski donne τmax en G : écart kNum/kCours = %+.2f %%.'], ...
                            100*(kNum - kC)/kC);
                    end
            end
            tex = {['$k = \frac{\tau_{max}\,S}{T} = \frac{S\,Q(y)}{I_{Gz}\,b(y)} = ' tn(kNum) '$']; ...
                ['$k_y = \frac{I_{Gz}^2}{S \int Q(y)^2/b(y)\,dy} = ' tn(kyNum) '$']};
            if ~isnan(kC)
                tex{end+1, 1} = ['$k_{cours} = ' tn(kC) ',\ k_{y,cours} = ' tn(kyC) '$'];
            end
            f.report = rep;
            f.latex = tex;
        end

        function kz = shearZ(sec, prims, ky)
            % Coefficient de section réduite kz (effort tranchant Tz) : même calcul énergétique que ky,
            % sur la section dont on échange les axes y et z.
            if any(strcmp(sec.type, {'rectangle', 'disque', 'couronne'}))
                kz = ky;   % valeur du cours indépendante de la direction
                return
            end
            pr = prims;
            for k = 1:numel(pr)
                [pr(k).z1, pr(k).y1] = deal(prims(k).y1, prims(k).z1);
                [pr(k).z2, pr(k).y2] = deal(prims(k).y2, prims(k).z2);
                [pr(k).zc, pr(k).yc] = deal(prims(k).yc, prims(k).zc);
            end
            f = GeometryEngine.shearCore(struct('type', 'composite'), pr, GeometryEngine.huygensCore(pr));
            kz = f.kyNum;
            if ~(isfinite(kz) && kz > 0)
                kz = ky;   % section non connexe selon z : pas de valeur énergétique
            end
        end

        function [kC, kyC, Sweb, txt] = courseShear(sec, core)
            % Valeurs tabulées du cours pour k et ky.
            Sweb = NaN;
            fs = @GeometryEngine.fs;
            switch sec.type
                case 'rectangle'
                    kC = 3/2; kyC = 5/6;
                    txt = 'rectangle : k = 3/2, ky = 5/6';
                case 'disque'
                    kC = 4/3; kyC = 6/7;
                    txt = 'disque : k = 4/3, ky = 6/7';
                case 'couronne'
                    R = sec.D/2; r = sec.d/2;
                    kC = 4/3*(1 + r*R/(r^2 + R^2));
                    if r == 0
                        kyC = 6/7;   % d = 0 : c'est un disque plein
                        txt = sprintf('couronne avec d = 0 (disque plein) : k = %s, ky = 6/7', fs(kC));
                    else
                        kyC = 1/2;
                        txt = sprintf('tube : k = 4/3·(1 + rR/(r² + R²)) = %s, ky = 1/2 (tube mince)', fs(kC));
                    end
                case 'I'
                    Sweb = sec.tw*(sec.h - 2*sec.tf);
                    kC = core.S/Sweb; kyC = Sweb/core.S;
                    txt = sprintf('poutre en I : k = S/S_âme = %s, ky = S_âme/S = %s (S_âme = tw·(h − 2tf) = %s m²)', ...
                        fs(kC), fs(kyC), fs(Sweb));
                case 'profile'
                    if strcmp(sec.profileShape, 'I')
                        Sweb = sec.tw*(sec.h - 2*sec.tf);
                        kC = core.S/Sweb; kyC = Sweb/core.S;
                        txt = sprintf(['profilé en I : k = S/S_âme = %s, ky = S_âme/S = %s (S_âme = a·(h − 2e) = %s m², ' ...
                            'S de la géométrie simplifiée)'], fs(kC), fs(kyC), fs(Sweb));
                    else
                        kC = NaN; kyC = NaN;
                        txt = 'aucune valeur du cours pour un profilé en U (valeurs numériques retenues)';
                    end
                otherwise
                    kC = NaN; kyC = NaN;
                    txt = 'aucune valeur du cours pour ce type (valeurs numériques retenues)';
            end
        end

        function v = q2b(prims, yG, x, tolW)
            % Intégrande Q(y)²/b(y) (nul où b est nul : extrémités des disques).
            Q = GeometryEngine.firstMomentCore(prims, yG, x);
            b = GeometryEngine.widthCore(prims, yG, x, 'above');
            v = zeros(size(x));
            ok = b > tolW;
            v(ok) = Q(ok).^2./b(ok);
        end

        function b = widthCore(prims, yG, yrel, side)
            % Largeur b(y) (y depuis G), avec recalage des cotes proches d'une discontinuité.
            yy = yrel + yG;
            lev = GeometryEngine.levels(prims);
            L = GeometryEngine.refLength(prims);
            tol = 1e-10*L;
            for k = 1:numel(lev)
                m = abs(yy - lev(k)) <= tol;
                yy(m) = lev(k);
            end
            switch side
                case 'above'
                    b = GeometryEngine.widthSide(prims, yy, true);
                case 'below'
                    b = GeometryEngine.widthSide(prims, yy, false);
                otherwise
                    b = max(GeometryEngine.widthSide(prims, yy, true), GeometryEngine.widthSide(prims, yy, false));
            end
            b(abs(b) <= 1e-12*L) = 0;
            b(isnan(yrel)) = NaN;
        end

        function b = widthSide(prims, yy, above)
            % Somme signée des largeurs des primitives (limite par au-dessus ou par en dessous).
            b = zeros(size(yy));
            for k = 1:numel(prims)
                p = prims(k);
                switch p.kind
                    case 'rect'
                        if above
                            in = yy >= p.y1 & yy < p.y2;
                        else
                            in = yy > p.y1 & yy <= p.y2;
                        end
                        w = (p.z2 - p.z1)*in;
                    case 'disk'
                        w = 2*sqrt(max(p.R^2 - (yy - p.yc).^2, 0));
                    otherwise
                        w = 2*sqrt(max(p.R^2 - (yy - p.yc).^2, 0)) - 2*sqrt(max(p.Ri^2 - (yy - p.yc).^2, 0));
                end
                b = b + p.sign*w;
            end
        end

        function Q = firstMomentCore(prims, yG, yrel)
            % Moment statique par rapport à (G, z) de la partie au-dessus de y (y depuis G).
            % Pour y < 0, Q est calculé comme l'opposé du moment de la partie inférieure
            % (meilleure précision relative ; les deux expressions sont mathématiquement égales).
            yy = yrel + yG;
            Qa = zeros(size(yy));
            Qb = zeros(size(yy));
            for k = 1:numel(prims)
                p = prims(k);
                switch p.kind
                    case 'rect'
                        w = p.z2 - p.z1;
                        lo = max(yy, p.y1);
                        qa = w*((p.y2 - yG)^2 - (lo - yG).^2)/2;
                        qa(yy >= p.y2) = 0;
                        hi = min(yy, p.y2);
                        qb = w*((hi - yG).^2 - (p.y1 - yG)^2)/2;
                        qb(yy <= p.y1) = 0;
                    case 'disk'
                        [qa, qb] = GeometryEngine.diskQ(yy, p.yc, p.R, yG);
                    otherwise
                        [qa, qb] = GeometryEngine.diskQ(yy, p.yc, p.R, yG);
                        if p.Ri > 0
                            [qai, qbi] = GeometryEngine.diskQ(yy, p.yc, p.Ri, yG);
                            qa = qa - qai;
                            qb = qb - qbi;
                        end
                end
                Qa = Qa + p.sign*qa;
                Qb = Qb + p.sign*qb;
            end
            Q = Qa;
            neg = yrel < 0;
            Q(neg) = -Qb(neg);
            bb = GeometryEngine.bboxPrims(prims);
            tol = 1e-12*max(bb(2) - bb(1), bb(4) - bb(3));
            Q(yy <= bb(3) + tol | yy >= bb(4) - tol) = 0;
            Q(isnan(yrel)) = NaN;
        end

        function [qa, qb] = diskQ(yy, yc, R, yG)
            % Moments statiques (par rapport à la cote yG) des segments de disque au-dessus (qa) et
            % au-dessous (qb) de la cote yy : qa = 2/3 (R² − u²)^(3/2) + (yc − yG)·A_dessus,
            % qb = −2/3 (R² − u²)^(3/2) + (yc − yG)·A_dessous, u = yy − yc.
            u = min(max(yy - yc, -R), R);
            s = sqrt(max(R^2 - u.^2, 0));
            Aa = R^2*acos(u/R) - u.*s;
            Ab = R^2*acos(-u/R) + u.*s;
            qa = (2/3)*s.^3 + (yc - yG)*Aa;
            qb = -(2/3)*s.^3 + (yc - yG)*Ab;
        end

        %% =====================================================================================
        %  Intégration (privé)
        %  =====================================================================================

        function R = integrateSymbolic(prims)
            % Intégrales doubles exactes (Symbolic Math Toolbox), primitive par primitive.
            y = sym('y', 'real');
            z = sym('z', 'real');
            r = sym('r', 'positive');
            th = sym('theta', 'real');
            n = numel(prims);
            F1 = sym(zeros(3, n));
            for k = 1:n
                p = prims(k);
                if strcmp(p.kind, 'rect')
                    F1(:, k) = p.sign*int(int([1; y; z], y, sym(p.y1), sym(p.y2)), z, sym(p.z1), sym(p.z2));
                else
                    yp = sym(p.yc) + r*sin(th);
                    zp = sym(p.zc) + r*cos(th);
                    F1(:, k) = p.sign*int(int([1; yp; zp]*r, r, sym(GeometryEngine.innerRadius(p)), sym(p.R)), ...
                        th, sym(0), 2*sym(pi));
                end
            end
            S = sum(F1(1, :));
            MO1z = sum(F1(2, :));
            MO1y = sum(F1(3, :));
            yG = MO1z/S;
            zG = MO1y/S;
            F2 = sym(zeros(4, n));
            for k = 1:n
                p = prims(k);
                if strcmp(p.kind, 'rect')
                    dy = y - yG;
                    dz = z - zG;
                    F2(:, k) = p.sign*int(int([dy^2; dz^2; dy*dz; dy^2 + dz^2], y, sym(p.y1), sym(p.y2)), ...
                        z, sym(p.z1), sym(p.z2));
                else
                    dy = sym(p.yc) + r*sin(th) - yG;
                    dz = sym(p.zc) + r*cos(th) - zG;
                    F2(:, k) = p.sign*int(int([dy^2; dz^2; dy*dz; dy^2 + dz^2]*r, r, ...
                        sym(GeometryEngine.innerRadius(p)), sym(p.R)), th, sym(0), 2*sym(pi));
                end
            end
            D1 = double(F1);
            D2 = double(F2);
            R = struct();
            R.Si = D1(1, :);
            R.MO1zi = D1(2, :);
            R.MO1yi = D1(3, :);
            R.Izi = D2(1, :);
            R.Iyi = D2(2, :);
            R.Iyzi = D2(3, :);
            R.Ixi = D2(4, :);
            R.S = double(S);
            R.MO1z = double(MO1z);
            R.MO1y = double(MO1y);
            R.yG = double(yG);
            R.zG = double(zG);
            R.Iz = double(sum(F2(1, :)));
            R.Iy = double(sum(F2(2, :)));
            R.Iyz = double(sum(F2(3, :)));
            R.IxDirect = double(sum(F2(4, :)));
        end

        function R = integrateNumeric(prims)
            % Intégrales doubles numériques (integral2) en coordonnées adimensionnées (x/L).
            L = GeometryEngine.refLength(prims);
            opts = {'AbsTol', 1e-15, 'RelTol', 1e-13};
            n = numel(prims);
            R = struct();
            R.Si = zeros(1, n); R.MO1zi = zeros(1, n); R.MO1yi = zeros(1, n);
            R.Izi = zeros(1, n); R.Iyi = zeros(1, n); R.Iyzi = zeros(1, n); R.Ixi = zeros(1, n);
            for k = 1:n
                p = prims(k);
                if strcmp(p.kind, 'rect')
                    lim = {p.z1/L, p.z2/L, p.y1/L, p.y2/L};
                    R.Si(k) = p.sign*L^2*integral2(@(zz, yy) ones(size(zz)), lim{:}, opts{:});
                    R.MO1zi(k) = p.sign*L^3*integral2(@(zz, yy) yy, lim{:}, opts{:});
                    R.MO1yi(k) = p.sign*L^3*integral2(@(zz, yy) zz, lim{:}, opts{:});
                else
                    lim = {0, 2*pi, GeometryEngine.innerRadius(p)/L, p.R/L};
                    ycs = p.yc/L;
                    zcs = p.zc/L;
                    R.Si(k) = p.sign*L^2*integral2(@(tt, rr) rr, lim{:}, opts{:});
                    R.MO1zi(k) = p.sign*L^3*integral2(@(tt, rr) (ycs + rr.*sin(tt)).*rr, lim{:}, opts{:});
                    R.MO1yi(k) = p.sign*L^3*integral2(@(tt, rr) (zcs + rr.*cos(tt)).*rr, lim{:}, opts{:});
                end
            end
            R.S = sum(R.Si);
            R.MO1z = sum(R.MO1zi);
            R.MO1y = sum(R.MO1yi);
            R.yG = R.MO1z/R.S;
            R.zG = R.MO1y/R.S;
            yGs = R.yG/L;
            zGs = R.zG/L;
            for k = 1:n
                p = prims(k);
                if strcmp(p.kind, 'rect')
                    lim = {p.z1/L, p.z2/L, p.y1/L, p.y2/L};
                    R.Izi(k) = p.sign*L^4*integral2(@(zz, yy) (yy - yGs).^2, lim{:}, opts{:});
                    R.Iyi(k) = p.sign*L^4*integral2(@(zz, yy) (zz - zGs).^2, lim{:}, opts{:});
                    R.Iyzi(k) = p.sign*L^4*integral2(@(zz, yy) (yy - yGs).*(zz - zGs), lim{:}, opts{:});
                    R.Ixi(k) = p.sign*L^4*integral2(@(zz, yy) (yy - yGs).^2 + (zz - zGs).^2, lim{:}, opts{:});
                else
                    lim = {0, 2*pi, GeometryEngine.innerRadius(p)/L, p.R/L};
                    dyc = p.yc/L - yGs;
                    dzc = p.zc/L - zGs;
                    R.Izi(k) = p.sign*L^4*integral2(@(tt, rr) (dyc + rr.*sin(tt)).^2.*rr, lim{:}, opts{:});
                    R.Iyi(k) = p.sign*L^4*integral2(@(tt, rr) (dzc + rr.*cos(tt)).^2.*rr, lim{:}, opts{:});
                    R.Iyzi(k) = p.sign*L^4*integral2(@(tt, rr) (dyc + rr.*sin(tt)).*(dzc + rr.*cos(tt)).*rr, ...
                        lim{:}, opts{:});
                    R.Ixi(k) = p.sign*L^4*integral2(@(tt, rr) ((dyc + rr.*sin(tt)).^2 + ...
                        (dzc + rr.*cos(tt)).^2).*rr, lim{:}, opts{:});
                end
            end
            R.Iz = sum(R.Izi);
            R.Iy = sum(R.Iyi);
            R.Iyz = sum(R.Iyzi);
            R.IxDirect = sum(R.Ixi);
        end

        function Ri = innerRadius(p)
            % Rayon intérieur d'une primitive circulaire (0 pour un disque).
            if strcmp(p.kind, 'annulus') && p.Ri > 0
                Ri = p.Ri;
            else
                Ri = 0;
            end
        end

        function c = integralStrings(prims, R)
            % Chaînes LaTeX des intégrales posées (bornes numériques), primitive par primitive.
            tn = @GeometryEngine.texNum;
            c = {};
            yG = R.yG;
            zG = R.zG;
            for k = 1:numel(prims)
                p = prims(k);
                if p.sign > 0, sg = ''; else, sg = '-'; end
                ks = int2str(k);
                if strcmp(p.kind, 'rect')
                    dbl = ['\int_{' tn(p.z1) '}^{' tn(p.z2) '}\!\!\int_{' tn(p.y1) '}^{' tn(p.y2) '} '];
                    dS = 'dy\,dz';
                    ey = ['\left(y' GeometryEngine.offStr(-yG) '\right)'];
                    ez = ['\left(z' GeometryEngine.offStr(-zG) '\right)'];
                    my = 'y\,';
                    mz = 'z\,';
                else
                    dbl = ['\int_{0}^{2\pi}\!\!\int_{' tn(GeometryEngine.innerRadius(p)) '}^{' tn(p.R) '} '];
                    dS = 'r\,dr\,d\theta';
                    ey = ['\left(r\sin\theta' GeometryEngine.offStr(p.yc - yG) '\right)'];
                    ez = ['\left(r\cos\theta' GeometryEngine.offStr(p.zc - zG) '\right)'];
                    my = ['\left(' tn(p.yc) ' + r\sin\theta\right) '];
                    mz = ['\left(' tn(p.zc) ' + r\cos\theta\right) '];
                end
                c{end+1, 1} = ['$S^{(' ks ')} = ' sg dbl dS ' = ' tn(R.Si(k)) '\ \mathrm{m^2}$']; %#ok<AGROW>
                c{end+1, 1} = ['$M_{O_1z}^{(' ks ')} = ' sg dbl my dS ' = ' tn(R.MO1zi(k)) '\ \mathrm{m^3}$']; %#ok<AGROW>
                c{end+1, 1} = ['$M_{O_1y}^{(' ks ')} = ' sg dbl mz dS ' = ' tn(R.MO1yi(k)) '\ \mathrm{m^3}$']; %#ok<AGROW>
                c{end+1, 1} = ['$I_{Gz}^{(' ks ')} = ' sg dbl ey '^2\,' dS ' = ' tn(R.Izi(k)) '\ \mathrm{m^4}$']; %#ok<AGROW>
                c{end+1, 1} = ['$I_{Gy}^{(' ks ')} = ' sg dbl ez '^2\,' dS ' = ' tn(R.Iyi(k)) '\ \mathrm{m^4}$']; %#ok<AGROW>
                c{end+1, 1} = ['$I_{Gyz}^{(' ks ')} = ' sg dbl ey ez '\,' dS ' = ' tn(R.Iyzi(k)) '\ \mathrm{m^4}$']; %#ok<AGROW>
                c{end+1, 1} = ['$I_{x}^{(' ks ')} = ' sg dbl '\left[' ey '^2 + ' ez '^2\right] ' dS ' = ' ...
                    tn(R.Ixi(k)) '\ \mathrm{m^4}$']; %#ok<AGROW>
            end
        end

        %% =====================================================================================
        %  Contours (privé)
        %  =====================================================================================

        function P = rectPoly(z1, z2, y1, y2)
            % Rectangle fermé, sens trigonométrique.
            P = [z1 y1; z2 y1; z2 y2; z1 y2; z1 y1];
        end

        function P = circlePoly(zc, yc, R, n)
            % Cercle fermé à n segments, sens trigonométrique.
            t = linspace(0, 2*pi, n + 1)';
            P = [zc + R*cos(t), yc + R*sin(t)];
            P(end, :) = P(1, :);
        end

        function P = shapePoly(sec)
            % Contour extérieur des profils I, T, U, L (sens trigonométrique).
            switch sec.type
                case 'profile'
                    shape = sec.profileShape;
                otherwise
                    shape = sec.type;
            end
            h = sec.h; b = sec.b;
            switch shape
                case 'I'
                    tw = sec.tw; tf = sec.tf; zl = (b - tw)/2; zr = (b + tw)/2;
                    P = [0 0; b 0; b tf; zr tf; zr h-tf; b h-tf; b h; 0 h; 0 h-tf; zl h-tf; zl tf; 0 tf; 0 0];
                case 'T'
                    tw = sec.tw; tf = sec.tf; zl = (b - tw)/2; zr = (b + tw)/2;
                    P = [zl 0; zr 0; zr h-tf; b h-tf; b h; 0 h; 0 h-tf; zl h-tf; zl 0];
                case 'U'
                    tw = sec.tw; tf = sec.tf;
                    P = [0 0; b 0; b tf; tw tf; tw h-tf; b h-tf; b h; 0 h; 0 0];
                otherwise
                    t = sec.t;
                    P = [0 0; b 0; b t; t t; t h; 0 h; 0 0];
            end
            keep = [true; any(abs(diff(P)) > 0, 2)];
            P = P(keep, :);
        end

        function ps = primPolyshape(p, n)
            % polyshape d'une primitive (contour ouvert).
            if strcmp(p.kind, 'rect')
                ps = polyshape([p.z1 p.z2 p.z2 p.z1], [p.y1 p.y1 p.y2 p.y2]);
            else
                c = GeometryEngine.circlePoly(p.zc, p.yc, p.R, n);
                ps = polyshape(c(1:end-1, 1), c(1:end-1, 2));
            end
        end

        function P = closePoly(P)
            % Ferme un contour (dernier point = premier).
            P = P(all(isfinite(P), 2), :);
            if ~isempty(P) && any(P(1, :) ~= P(end, :))
                P(end+1, :) = P(1, :);
            end
        end

        function P = orientPoly(P, ccw)
            % Impose le sens de parcours (ccw = true : trigonométrique).
            a = 0.5*sum(P(1:end-1, 1).*P(2:end, 2) - P(2:end, 1).*P(1:end-1, 2));
            if (a < 0) == ccw
                P = flipud(P);
            end
        end

        %% =====================================================================================
        %  Textes (privé)
        %  =====================================================================================

        function s = typeLabel(sec)
            % Nom lisible du type de section.
            switch sec.type
                case 'rectangle', s = 'rectangle plein';
                case 'disque', s = 'disque plein';
                case 'couronne', s = 'couronne';
                case 'rectangle_creux', s = 'rectangle creux';
                case 'I', s = 'profil en I';
                case 'T', s = 'profil en T';
                case 'U', s = 'profil en U';
                case 'L', s = 'cornière L';
                case 'profile', s = 'profilé du catalogue';
                otherwise, s = 'section composite';
            end
        end

        function s = describeSection(sec)
            % Description de la section avec ses dimensions (mm).
            mm = @(x) sprintf('%.6g mm', 1000*x);
            switch sec.type
                case 'rectangle'
                    s = sprintf('Rectangle : b = %s (selon z), h = %s (selon y)', mm(sec.b), mm(sec.h));
                case 'disque'
                    s = sprintf('Disque : D = %s', mm(sec.D));
                case 'couronne'
                    s = sprintf('Couronne : D = %s, d = %s', mm(sec.D), mm(sec.d));
                case 'rectangle_creux'
                    s = sprintf('Rectangle creux : B = %s, H = %s, t = %s', mm(sec.B), mm(sec.H), mm(sec.t));
                case {'I', 'T', 'U'}
                    s = sprintf('Profil %s : h = %s, b = %s, tw = %s, tf = %s', sec.type, mm(sec.h), ...
                        mm(sec.b), mm(sec.tw), mm(sec.tf));
                case 'L'
                    s = sprintf('Cornière L : h = %s, b = %s, t = %s', mm(sec.h), mm(sec.b), mm(sec.t));
                case 'profile'
                    nm = strtrim(sec.name);
                    if isempty(nm), nm = sec.family; end
                    if isempty(nm), nm = 'profilé'; end
                    s = sprintf('Profilé %s (géométrie simplifiée en %s) : h = %s, b = %s, a = %s, e = %s', ...
                        nm, sec.profileShape, mm(sec.h), mm(sec.b), mm(sec.tw), mm(sec.tf));
                otherwise
                    s = sprintf(['Section composite : %d rectangle(s), %d trou(s) rectangulaire(s), ' ...
                        '%d disque(s), %d trou(s) circulaire(s) (repère utilisateur)'], size(sec.rects, 1), ...
                        size(sec.holes, 1), size(sec.disks, 1), size(sec.diskHoles, 1));
            end
        end

        function [rep, tex] = huygensText(core)
            % Démarche de Huygens (rapport + LaTeX).
            fs = @GeometryEngine.fs;
            tn = @GeometryEngine.texNum;
            T = core.table;
            n = height(T);
            rep = {sprintf('Décomposition en %d élément(s) (repère O1 ; valeurs signées, trous négatifs) :', n)};
            for k = 1:n
                rep{end+1, 1} = sprintf(['  %d. %s : S_i = %s m², zG_i = %s m, yG_i = %s m, IGz_i = %s m⁴, ' ...
                    'IGy_i = %s m⁴'], k, T.Label{k}, fs(T.S_i(k)), fs(T.zG_i(k)), fs(T.yG_i(k)), ...
                    fs(T.IGz_i(k)), fs(T.IGy_i(k))); %#ok<AGROW>
            end
            rep{end+1, 1} = sprintf('Aire : S = Σ S_i = %s m² (%s cm²)', fs(core.S), fs(core.S*1e4));
            rep{end+1, 1} = sprintf('Moments statiques : M_O1z = Σ S_i·yG_i = %s m³ ; M_O1y = Σ S_i·zG_i = %s m³', ...
                fs(core.MO1z), fs(core.MO1y));
            rep{end+1, 1} = sprintf('Barycentre : yG = M_O1z/S = %s m ; zG = M_O1y/S = %s m', fs(core.yG), fs(core.zG));
            rep{end+1, 1} = 'Théorème de Huygens (dy_i = yG_i − yG, dz_i = zG_i − zG) :';
            for k = 1:n
                rep{end+1, 1} = sprintf(['  %d. dy = %s m, dz = %s m : Iz_i = IGz_i + S_i·dy² = %s%s = %s m⁴ ; ' ...
                    'Iy_i = IGy_i + S_i·dz² = %s%s = %s m⁴'], k, fs(T.dy_i(k)), fs(T.dz_i(k)), ...
                    fs(T.IGz_i(k)), GeometryEngine.plusTxt(T.SDy2(k)), fs(T.Iz_i(k)), fs(T.IGy_i(k)), ...
                    GeometryEngine.plusTxt(T.SDz2(k)), fs(T.Iy_i(k))); %#ok<AGROW>
            end
            rep{end+1, 1} = sprintf('I_Gz = Σ (IGz_i + S_i·dy_i²) = %s m⁴ (%s cm⁴)', fs(core.Iz), fs(core.Iz*1e8));
            rep{end+1, 1} = sprintf('I_Gy = Σ (IGy_i + S_i·dz_i²) = %s m⁴ (%s cm⁴)', fs(core.Iy), fs(core.Iy*1e8));
            rep{end+1, 1} = sprintf('I_Gyz = Σ S_i·dy_i·dz_i = %s m⁴', fs(core.Iyz));
            tex = {['$S = \sum S_i = ' tn(core.S) '\ \mathrm{m^2}$']; ...
                ['$y_G = \frac{M_{O_1z_1}}{S} = \frac{\sum S_i\,y_{Gi}}{\sum S_i} = \frac{' tn(core.MO1z) '}{' ...
                tn(core.S) '} = ' tn(core.yG) '\ \mathrm{m}$']; ...
                ['$z_G = \frac{M_{O_1y_1}}{S} = \frac{\sum S_i\,z_{Gi}}{\sum S_i} = \frac{' tn(core.MO1y) '}{' ...
                tn(core.S) '} = ' tn(core.zG) '\ \mathrm{m}$']};
            for k = 1:min(n, 12)
                ks = int2str(k);
                if T.SDy2(k) == 0
                    term = ' + 0';
                else
                    term = GeometryEngine.offStr(T.SDy2(k));
                end
                tex{end+1, 1} = ['$(' ks '):\ S_{' ks '} = ' tn(T.S_i(k)) ',\ I_{Gz_{' ks '}} + S_{' ks ...
                    '}\,d_{y' ks '}^2 = ' tn(T.IGz_i(k)) term ' = ' tn(T.Iz_i(k)) '$']; %#ok<AGROW>
            end
            tex = [tex; ...
                {['$I_{Gz} = \sum \left(I_{Gz_i} + S_i\,d_{y_i}^2\right) = ' tn(core.Iz) '\ \mathrm{m^4}$']; ...
                ['$I_{Gy} = \sum \left(I_{Gy_i} + S_i\,d_{z_i}^2\right) = ' tn(core.Iy) '\ \mathrm{m^4}$']; ...
                ['$I_{Gyz} = \sum S_i\,d_{y_i}\,d_{z_i} = ' tn(core.Iyz) '\ \mathrm{m^4}$']}];
        end

        function [rep, tex] = commonText(P)
            % Grandeurs dérivées communes (rapport + LaTeX).
            fs = @GeometryEngine.fs;
            tn = @GeometryEngine.texNum;
            rep = {sprintf('Moment polaire : Ix = I_Gz + I_Gy = %s m⁴ (%s cm⁴)', fs(P.Ix), fs(P.Ix*1e8))};
            if P.Iyz ~= 0
                rep{end+1, 1} = sprintf(['Axes principaux : I1,2 = (Iz + Iy)/2 ± √[((Iz − Iy)/2)² + Iyz²] ⇒ ' ...
                    'I1 = %s m⁴, I2 = %s m⁴ ; tan 2α = −2·Iyz/(Iz − Iy) ⇒ αP = %s rad (%s°) depuis z'], ...
                    fs(P.I1), fs(P.I2), fs(P.alphaP), fs(P.alphaP*180/pi));
            else
                rep{end+1, 1} = sprintf(['Axes principaux : Iyz = 0, les axes (G, z) et (G, y) sont principaux ; ' ...
                    'I1 = %s m⁴, I2 = %s m⁴, αP = %s°'], fs(P.I1), fs(P.I2), fs(P.alphaP*180/pi));
            end
            rep{end+1, 1} = sprintf('Rayons de giration : rz = √(Iz/S) = %s m (%s mm) ; ry = √(Iy/S) = %s m (%s mm)', ...
                fs(P.rz), fs(P.rz*1e3), fs(P.ry), fs(P.ry*1e3));
            rep{end+1, 1} = sprintf(['Fibres extrêmes : vy,haut = %s m, vy,bas = %s m, vz,droite = %s m, ' ...
                'vz,gauche = %s m'], fs(P.vyTop), fs(P.vyBot), fs(P.vzRight), fs(P.vzLeft));
            rep{end+1, 1} = sprintf('Modules de flexion : Wz = Iz/vy,max = %s m³ (%s cm³) ; Wy = Iy/vz,max = %s m³ (%s cm³)', ...
                fs(P.Wz), fs(P.Wz*1e6), fs(P.Wy), fs(P.Wy*1e6));
            rep{end+1, 1} = sprintf('Constante de torsion : J = %s m⁴ — %s', fs(P.J), P.Jmethod);
            rep{end+1, 1} = sprintf('Cisaillement : k = %s, ky = %s (source : %s) ; Jourawski kNum = %s, énergie kyNum = %s ; kz = %s (Tz)', ...
                fs(P.k), fs(P.ky), P.kSource, fs(P.shear.kNum), fs(P.shear.kyNum), fs(P.kz));
            rep = [rep; P.shear.report(2:end)];
            tex = {['$I_x = I_{Gz} + I_{Gy} = ' tn(P.Ix) '\ \mathrm{m^4}$']};
            if P.Iyz ~= 0
                tex{end+1, 1} = ['$I_{1,2} = \frac{I_{Gz}+I_{Gy}}{2} \pm \sqrt{\left(\frac{I_{Gz}-I_{Gy}}{2}\right)^2 ' ...
                    '+ I_{Gyz}^2} \Rightarrow I_1 = ' tn(P.I1) ',\ I_2 = ' tn(P.I2) '\ \mathrm{m^4}$'];
                tex{end+1, 1} = ['$\tan 2\alpha_P = \frac{-2\,I_{Gyz}}{I_{Gz}-I_{Gy}} \Rightarrow \alpha_P = ' ...
                    tn(P.alphaP*180/pi, 4) '^{\circ}$'];
            else
                tex{end+1, 1} = ['$I_{Gyz} = 0 \Rightarrow I_1 = ' tn(P.I1) ',\ I_2 = ' tn(P.I2) ...
                    '\ \mathrm{m^4},\ \alpha_P = ' tn(P.alphaP*180/pi, 4) '^{\circ}$'];
            end
            tex = [tex; ...
                {['$r_z = \sqrt{\frac{I_{Gz}}{S}} = ' tn(P.rz) '\ \mathrm{m},\ r_y = \sqrt{\frac{I_{Gy}}{S}} = ' ...
                tn(P.ry) '\ \mathrm{m}$']; ...
                ['$W_z = \frac{I_{Gz}}{v_{y,max}} = \frac{' tn(P.Iz) '}{' tn(max(P.vyTop, P.vyBot)) '} = ' ...
                tn(P.Wz) '\ \mathrm{m^3}$']; ...
                ['$W_y = \frac{I_{Gy}}{v_{z,max}} = \frac{' tn(P.Iy) '}{' tn(max(P.vzRight, P.vzLeft)) '} = ' ...
                tn(P.Wy) '\ \mathrm{m^3}$']; ...
                P.Jlatex}];
            tex = [tex; P.shear.latex];
        end

        function s = fs(x)
            % Format numérique des rapports.
            s = sprintf('%.6g', x);
        end

        function s = plusTxt(x)
            % Terme additif signé pour les rapports : « + x » ou « − |x| ».
            if x < 0
                s = [' − ' GeometryEngine.fs(-x)];
            else
                s = [' + ' GeometryEngine.fs(x)];
            end
        end

        function s = texNum(x, nd)
            % Nombre au format LaTeX (puissances de 10 explicites).
            if nargin < 2
                nd = 5;
            end
            if isnan(x)
                s = '\mathrm{NaN}';
                return;
            end
            if isinf(x)
                if x > 0, s = '\infty'; else, s = '-\infty'; end
                return;
            end
            if x == 0
                s = '0';
                return;
            end
            s = sprintf(['%.' int2str(nd) 'g'], x);
            k = strfind(s, 'e');
            if ~isempty(k)
                mant = s(1:k-1);
                ex = str2double(s(k+1:end));
                if strcmp(mant, '1')
                    s = sprintf('10^{%d}', ex);
                elseif strcmp(mant, '-1')
                    s = sprintf('-10^{%d}', ex);
                else
                    s = [mant ' \times 10^{' int2str(ex) '}'];
                end
            end
        end

        function s = offStr(v)
            % Terme additif signé « + v » ou « - |v| » (vide si v = 0).
            if v == 0
                s = '';
            elseif v > 0
                s = [' + ' GeometryEngine.texNum(v)];
            else
                s = [' - ' GeometryEngine.texNum(-v)];
            end
        end

    end
end
