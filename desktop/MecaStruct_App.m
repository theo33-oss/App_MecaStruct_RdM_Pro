classdef MecaStruct_App < handle
    %MECASTRUCT_APP Interface graphique de MecaStruct RdM Pro (résistance des matériaux).
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   app = MecaStruct_App() ouvre la fenêtre « MecaStruct RdM Pro ».
    %   app = MecaStruct_App('Visible', 'off') crée l'interface sans l'afficher (tests).
    %   app = MecaStruct_App(..., 'UserFile', f) utilise le fichier de données utilisateur f
    %   (défaut : DataManager.defaultUserFile()).
    %
    %   Interface 100 % programmatique (uifigure, uigridlayout, uitabgroup) : onglets Base de
    %   données, Sections, Poutres, Treillis, Sollicitations (Traction, Cisaillement & Matage,
    %   Torsion, Flexion), Flambage, Tenseurs & Critères, Hooke & Jauges, et panneau latéral
    %   « Formulaire rapide » (DataManager.formulaSheet rendu par PlotEngine.formulaSheet).
    %
    %   Unités de saisie (converties en SI par DataManager.toSI avant l'appel des moteurs) :
    %   dimensions de section en mm ; longueurs de poutre/treillis en m ; forces en kN, moments en
    %   kN·m, charges réparties en kN/m ; E, G en GPa ; Re, Rm, contraintes en MPa ; α en
    %   1e-6/°C ; déformations en µdéf. Résultats affichés en kN, kN·m, MPa, mm, mrad.
    %
    %   Méthodes publiques (utilisables sans interaction) : computeSection, computeBeam,
    %   computeTruss, computeTraction, computeShear, computeKey, computePin, computeTorsion,
    %   computeBending, computeBuckling, computeTensor, computeHooke, computeGauges, computeKt,
    %   useSectionForBeam, sendToTensor, loadExample, runAllExamples, selectTab, showFormula,
    %   exportCurrentPlot, saveUserData, loadUserData, addMaterialFromForm, addProfileFromForm,
    %   et la méthode statique parseFunction.
    %
    %   Voir aussi DataManager, GeometryEngine, BeamAndTrussSolver, SolicitationsEngine,
    %   BucklingEngine, TensorAndCriteriaEngine, PlotEngine.

    properties
        UIFigure                     % fenêtre principale (uifigure)
        DM                           % base de données (DataManager)
        TabGroup                     % groupe d'onglets principal
        Tabs = struct()              % onglets principaux (DB, Sec, Beam, Tr, Sol, Fla, Ten, Hoo)
        H = struct()                 % composants par zone de travail (Sec, Beam, Tr, Tra, Cis, ...)
        Results = struct()           % derniers résultats des moteurs (SI)
        ErrorLog = cell(0, 1)        % erreurs journalisées (toujours ; uialert si fenêtre visible)
        FormulaKey = ''              % clé de la fiche affichée dans le formulaire rapide
        SectionData = []             % dernière section calculée : sec, P, mat
    end

    properties (SetAccess = private)   % lisibles par ValidationReport
        BeamUsesSection = false      % la vérification de la poutre utilise le contour exact de BeamSection
        BeamSection = []             % section transmise à la poutre (figée au transfert : sec, P, mat)
    end

    properties (Hidden)
        ConfirmFcn = @uiconfirm      % boîte « résultat non fiable » (les tests la remplacent)
    end

    properties (Access = private)
        FormulaPanel                % panneau défilant du formulaire
        FormulaAxes                  % axe de rendu de la fiche
        FormulaDrop                  % sélecteur de fiche
        SubSol                       % sous-onglets de Sollicitations
        SubHooke                     % sous-onglets de Hooke & Jauges
        SubDB                        % sous-onglets de la base de données
        ButtonGrid                   % grille des boutons du formulaire (dossier / note / guide)
        BtnVal                       % bouton « Dossier de validation » (onglets de calcul)
        BtnNote                      % bouton « Note de calcul » (Base de données uniquement)
        BtnGuide                     % bouton « Guide » (visible dans tous les onglets)
        SectionWin                   % fenêtre « Voir la section » (une seule, fermée avec l'application)
        BeamHist = {}                % historique de la saisie de Poutres (annuler / rétablir)
        BeamHistPos = 0              % position courante dans BeamHist
        HistBusy = false             % vrai pendant une restauration (pas de nouvelle entrée d'historique)
    end

    properties (Constant, Access = private)
        LoadCases = {'G', 'Q', 'W', 'S'}   % cas de charge : permanentes, exploitation, vent, neige
        SupportTypes = {'appui_simple', 'rotule', 'pivot', 'pivot_glissant', 'encastrement'}
        Comps = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'}
        MatKeys = {'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'}
        WorkKeys = {'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'}
    end

    %% =========================================================================================
    %  Construction, destruction
    %  =========================================================================================
    methods

        function app = MecaStruct_App(varargin)
            %MECASTRUCT_APP Construit l'interface (voir l'aide de la classe).
            %   Options nom/valeur : 'Visible' ('on' | 'off'), 'UserFile' (fichier .mat).
            ip = inputParser;
            ip.FunctionName = 'MecaStruct_App';
            ip.addParameter('Visible', 'on', @(v) any(strcmpi(char(string(v)), {'on', 'off'})));
            ip.addParameter('UserFile', '', @(v) ischar(v) || isstring(v));
            ip.parse(varargin{:});
            vis = lower(char(string(ip.Results.Visible)));
            app.DM = DataManager(char(string(ip.Results.UserFile)));
            ss = get(groot, 'ScreenSize');
            w = max(1000, min(1560, ss(3) - 60));
            h = max(650, min(920, ss(4) - 110));
            app.UIFigure = uifigure('Name', 'MecaStruct RdM Pro', 'Visible', 'off', ...
                'Position', [30 50 w h], 'CloseRequestFcn', @(~, ~) delete(app));
            app.buildUI();
            ex = {'DB', 'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'};
            for k = 1:numel(ex)
                app.loadExample(ex{k});
            end
            app.UIFigure.Visible = vis;
            app.updateFormula();
        end

        function delete(app)
            %DELETE Ferme proprement la fenêtre de l'application.
            if ~isempty(app.SectionWin) && isvalid(app.SectionWin)
                delete(app.SectionWin);
            end
            if ~isempty(app.UIFigure) && isvalid(app.UIFigure)
                delete(app.UIFigure);
            end
        end
    end

    %% =========================================================================================
    %  Méthodes publiques de calcul (sans interaction)
    %  =========================================================================================
    methods

        function computeSection(app)
            %COMPUTESECTION Caractéristiques de la section (analytique, intégrale, tabulée) et contraintes.
            %   app.computeSection() lit l'onglet Sections, calcule GeometryEngine.analytical,
            %   GeometryEngine.integral (mode choisi), GeometryEngine.compare, les profils σ(y)
            %   (SolicitationsEngine.bendingStress) et τ(y) (SolicitationsEngine.jourawski), remplit
            %   les tables de comparaison et de Huygens et trace la section et les profils.
            S = app.H.Sec;
            W = S.W;
            sec = app.buildSection();
            mode = S.mode.Value;
            if strcmp(mode, 'symbolique') && ~GeometryEngine.hasSymbolic()
                mode = 'numerique';
            end
            P = GeometryEngine.analytical(sec);
            C = GeometryEngine.compare(sec);
            Bdef = C.Properties.UserData.integral;
            extra = [];
            if strcmp(mode, 'numerique') && contains(Bdef.method, 'symbolique')
                Bn = GeometryEngine.integral(sec, 'numerique');
                extra = Bn;
            else
                Bn = Bdef;
            end
            mat = app.DM.getMaterial(S.mat.Value);
            bend = SolicitationsEngine.bendingStress(MecaStruct_App.stressGeometry(sec, struct( ...
                'N', app.si(S.N, 'kN'), 'Mfz', app.si(S.Mfz, 'kN.m'), 'Mfy', app.si(S.Mfy, 'kN.m'), ...
                'Kt', S.Kt.Value, 'Re', mat.Re)));
            jour = SolicitationsEngine.jourawski(sec, app.si(S.Ty, 'kN'));

            PlotEngine.section(W.Axes{1}(1), sec, P);
            PlotEngine.sectionStress(W.Axes{2}(1), W.Axes{2}(2), sec, P, bend, jour);
            app.finishWork(W);

            W.Tables.Comp.Data = MecaStruct_App.compareDisplay(C, extra);
            if isfield(P, 'huygens') && istable(P.huygens)
                W.Tables.Huyg.Data = MecaStruct_App.huygensDisplay(P.huygens);
            end
            ds = @DataManager.fromSI;
            summary = {
                sprintf('Section : %s', MecaStruct_App.sectionLabel(sec))
                sprintf('S = %.6g mm² ; yG = %.5g mm ; zG = %.5g mm (repère O1, coin bas-gauche)', ds(P.S, 'mm^2'), ds(P.yG, 'mm'), ds(P.zG, 'mm'))
                sprintf('Iz = %.6g mm⁴ ; Iy = %.6g mm⁴ ; Iyz = %.4g mm⁴ ; Ix = Iz + Iy = %.6g mm⁴', ds(P.Iz, 'mm^4'), ds(P.Iy, 'mm^4'), ds(P.Iyz, 'mm^4'), ds(P.Ix, 'mm^4'))
                sprintf('Moments principaux : I1 = %.6g mm⁴, I2 = %.6g mm⁴, angle = %.4g°', ds(P.I1, 'mm^4'), ds(P.I2, 'mm^4'), rad2deg(P.alphaP))
                sprintf('Constante de torsion J = %.6g mm⁴', ds(P.J, 'mm^4'))
                sprintf('rz = %.5g mm ; ry = %.5g mm ; Wz = %.6g mm³ ; Wy = %.6g mm³', ds(P.rz, 'mm'), ds(P.ry, 'mm'), ds(P.Wz, 'mm^3'), ds(P.Wy, 'mm^3'))
                sprintf('Facteurs de cisaillement : k = %.4g ; ky = %.4g (%s) ; kz = %.4g', P.k, P.ky, P.kSource, P.kz)
                sprintf('Flexion : σ traction max = %.5g MPa ; σ compression max = %.5g MPa ; Kt·|σ|max = %.5g MPa (%s)', ...
                ds(bend.sigmaMaxTraction, 'MPa'), ds(bend.sigmaMaxCompression, 'MPa'), ds(bend.sigmaMaxKt, 'MPa'), MecaStruct_App.okText(bend.ok))
                sprintf('Jourawski : τmax = %.5g MPa en y = %.4g mm ; τmoy = %.5g MPa', ds(jour.tauMax, 'MPa'), ds(jour.yAtMax, 'mm'), ds(jour.tauMoy, 'MPa'))};
            app.setReport(W, summary, '=== Méthode A : analytique et Huygens ===', P.report, ...
                ['=== Méthode B : ' Bn.method ' ==='], Bn.report, '=== Comparaison des méthodes ===', ...
                C.Properties.UserData.report, '=== Contraintes normales (flexion composée) ===', bend.report, ...
                '=== Cisaillement (Jourawski) ===', jour.report);
            W.Status.Text = sprintf('S = %.5g mm², Iz = %.5g mm⁴, Iy = %.5g mm⁴', ds(P.S, 'mm^2'), ds(P.Iz, 'mm^4'), ds(P.Iy, 'mm^4'));
            app.SectionData = struct('sec', sec, 'P', P, 'mat', S.mat.Value);
            app.Results.section = struct('sec', sec, 'P', P, 'Pint', Bn, 'compare', C, 'bend', bend, 'jour', jour);
        end

        function useSectionForBeam(app)
            %USESECTIONFORBEAM Transmet S, Iz, Iy, Ix (constante de torsion), ky de la section aux
            %   onglets Poutres et Flambage (la section est recalculée avec les saisies actuelles).
            %   Profilé du catalogue : valeurs tabulées (la géométrie simplifiée ignore les congés).
            %   Section à Iyz ≠ 0 (cornière…) : le flambage reçoit les moments principaux I1, I2.
            app.computeSection();
            D = app.SectionData;
            P = D.P;
            isProfile = strcmp(D.sec.type, 'profile');
            if isProfile
                Pt = GeometryEngine.tabulated(D.sec);
                for f = {'S', 'Iz', 'Iy', 'ky', 'kz', 'vyTop', 'vyBot', 'vzRight', 'vzLeft'}   % ky·S doit rester l'aire d'âme
                    P.(f{1}) = Pt.(f{1});
                end
            end
            B = app.H.Beam;
            B.S.Value = DataManager.fromSI(P.S, 'mm^2');
            B.Iz.Value = DataManager.fromSI(P.Iz, 'mm^4');
            B.Iy.Value = DataManager.fromSI(P.Iy, 'mm^4');
            J = P.J;
            if ~(isfinite(J) && J > 0)
                J = P.Ix;
            end
            B.Ix.Value = DataManager.fromSI(J, 'mm^4');
            ky = P.ky;
            if ~(isfinite(ky) && ky > 0)
                ky = 1;
            end
            B.ky.Value = ky;
            kz = P.kz;
            if ~(isfinite(kz) && kz > 0)
                kz = ky;
            end
            B.kz.Value = kz;
            B.Iyz.Value = DataManager.fromSI(P.Iyz, 'mm^4');
            B.vy.Value = DataManager.fromSI(max(P.vyTop, P.vyBot), 'mm');
            B.vz.Value = DataManager.fromSI(max(P.vzRight, P.vzLeft), 'mm');
            B.mat.Value = D.mat;
            app.applyMaterial('Beam');
            app.BeamSection = D;
            app.BeamUsesSection = ~isProfile;   % profilé : on vérifie avec les valeurs du catalogue saisies
            F = app.H.Fla;
            F.S.Value = B.S.Value;
            F.Iz.Value = B.Iz.Value;
            F.Iy.Value = B.Iy.Value;
            msg = sprintf('Section reçue : %s', MecaStruct_App.sectionLabel(D.sec));
            msgF = msg;
            if ~isProfile && abs(P.Iyz) > 1e-9 * sqrt(P.Iz * P.Iy)
                % axes non principaux : le flambage se fait autour de l'axe principal faible
                F.Iz.Value = DataManager.fromSI(P.I1, 'mm^4');
                F.Iy.Value = DataManager.fromSI(P.I2, 'mm^4');
                msgF = sprintf('%s — Iyz ≠ 0 : moments principaux I1, I2 (axes tournés de %.4g°)', msg, rad2deg(P.alphaP));
                msg = sprintf('%s — Iyz ≠ 0 : flexion déviée (contraintes et flèches couplées en y et z)', msg);
            end
            F.mat.Value = D.mat;
            app.applyMaterial('Fla');
            src = 'contour exact';
            if isProfile
                src = 'valeurs du catalogue';
            end
            info = sprintf('Section utilisée : %s (importée de Sections, %s).', ...
                MecaStruct_App.sectionLabel(D.sec), src);
            B.secInfo.Text = info;
            F.secInfo.Text = info;
            B.W.Status.Text = msg;
            F.W.Status.Text = msgF;
            app.H.Sec.W.Status.Text = 'Section transmise aux onglets Poutres et Flambage.';
        end

        function fig = showBeamSection(app)
            %SHOWBEAMSECTION Ouvre une fenêtre avec le dessin de la section utilisée par la poutre.
            %   Les valeurs affichées sont celles des champs de l'onglet Poutres (celles du calcul).
            B = app.H.Beam;
            fig = [];
            if isempty(app.BeamSection)
                B.W.Status.Text = 'Section saisie à la main : aucune forme à dessiner. Utilisez « Importer depuis Sections » ou chargez un exemple.';
                return
            end
            D = app.BeamSection;
            if ~isempty(app.SectionWin) && isvalid(app.SectionWin)
                delete(app.SectionWin);   % une seule fenêtre : on la redessine
            end
            fig = uifigure('Name', ['Section de la poutre : ' MecaStruct_App.sectionLabel(D.sec)], 'Position', [200 200 520 560], ...
                'Visible', app.UIFigure.Visible);
            gl = uigridlayout(fig, [2 1], 'RowHeight', {'1x', 40});
            ax = uiaxes(gl);
            PlotEngine.section(ax, D.sec, D.P);
            uilabel(gl, 'Text', sprintf('Valeurs de la poutre : S = %.5g mm², Iz = %.5g mm⁴, Iy = %.5g mm⁴, Iyz = %.5g mm⁴', ...
                B.S.Value, B.Iz.Value, B.Iy.Value, B.Iyz.Value), 'WordWrap', 'on');
            app.SectionWin = fig;
        end

        function applySectionPreset(app)
            %APPLYSECTIONPRESET Règle le type et les dimensions de l'onglet Sections sur le tube ou la cornière choisi.
            S = app.H.Sec;
            P = DataManager.sectionPresets();
            p = P(strcmp({P.name}, S.preset.Value));
            S.type.Value = p.type;
            app.onSectionType();
            for f = fieldnames(p.dims).'
                S.(f{1}).Value = p.dims.(f{1});
            end
            S.W.Status.Text = sprintf('%s : dimensions nominales recopiées (mm). Cliquez sur « Calculer la section » ; congés ignorés.', p.name);
        end

        function computeBeam(app, interactive)
            %COMPUTEBEAM Poutre : PFS/hyperstatisme, torseur de cohésion, déformée (4 méthodes),
            %   énergie de déformation et vérification de résistance au point le plus sollicité.
            %   interactive (défaut false, vrai pour le bouton « Calculer ») : si le résultat est
            %   non fiable (hyperstatique avec Iyz ≠ 0), demande à l'utilisateur de l'afficher ou non.
            if nargin < 2
                interactive = false;
            end
            B = app.H.Beam;
            W = B.W;
            model = app.readBeamModel();
            sol = BeamAndTrussSolver.solveBeam(model);
            if interactive && ~isempty(MecaStruct_App.unreliableNote(sol))
                rep = app.ConfirmFcn(app.UIFigure, ['Poutre hyperstatique avec une section sans axes principaux (Iyz ≠ 0) : ' ...
                    'les réactions sont calculées plan par plan et le couplage y–z est ignoré. ' ...
                    'Les réactions, moments et contraintes ne sont PAS fiables.' newline newline ...
                    'Afficher quand même le résultat ?'], 'Résultat non fiable', ...
                    'Options', {'Oui, afficher', 'Non'}, 'DefaultOption', 2, 'CancelOption', 2, 'Icon', 'warning');
                if ~strcmp(rep, 'Oui, afficher')
                    W.Status.Text = '⚠ Résultat non affiché (hyperstatique avec Iyz ≠ 0). Saisissez la section dans ses axes principaux (Iyz = 0).';
                    return
                end
            end
            d = SolicitationsEngine.deflection(sol.model, sol, ...
                struct('plane', B.plane.Value, 'includeShear', logical(B.shear.Value)));
            U = SolicitationsEngine.strainEnergy(sol.model, sol);
            chk = app.beamCheck(sol);
            app.Results.beam = struct('model', sol.model, 'sol', sol, 'defl', d, 'energy', U, 'check', chk);
            app.Results.beamInputs = {app.captureInputs('Beam'), app.BeamSection};   % saisie de ce calcul (contrôle Eurocode 3)

            % --- tracés
            PlotEngine.beamSchematic(W.Axes{1}(1), sol.model, sol);
            app.armSchematic(W.Axes{1}(1));
            comps = app.selectedComps(sol);
            axs = W.Axes{2};
            n = numel(comps);
            gl = axs(1).Parent;
            rh = repmat({0}, 1, numel(axs));
            rh(1:n) = {'1x'};
            gl.RowHeight = rh;
            for k = n + 1:numel(axs)
                cla(axs(k), 'reset');
                axs(k).Visible = 'off';
            end
            PlotEngine.internalForces(axs(1:n), sol, comps);
            PlotEngine.deflection(W.Axes{3}(1), W.Axes{3}(2), sol.model, d);
            MecaStruct_App.plotEquations(W.Axes{4}(1), sol, comps);
            app.finishWork(W);
            app.armSchematic(W.Axes{1}(1));
            for k = n + 1:numel(axs)
                axs(k).Visible = 'off';
            end

            % --- tables
            R = sol.reactions;
            W.Tables.Reac.Data = table(string({R.name}).', string({R.type}).', [R.pos].', ...
                [R.Rx].' / 1e3, [R.Ry].' / 1e3, [R.Rz].' / 1e3, [R.Mx].' / 1e3, [R.My].' / 1e3, [R.Mz].' / 1e3, ...
                'VariableNames', {'Appui', 'Type', 'Position (m)', 'Rx (kN)', 'Ry (kN)', 'Rz (kN)', ...
                'Mx (kN·m)', 'My (kN·m)', 'Mz (kN·m)'});
            W.Tables.Eq.Data = MecaStruct_App.equationTable(sol);
            cmp = d.comparison;
            W.Tables.Defl.Data = table(string(cmp.Methode), cmp.fmax_m * 1e3, cmp.s_m, cmp.Ecart_pct, ...
                'VariableNames', {'Méthode', 'f max (mm)', 's (m)', 'Écart (%)'});
            W.Tables.Energy.Data = table(["U_N (effort normal)"; "U_Ty (tranchant y)"; "U_Tz (tranchant z)"; ...
                "U_Mt (torsion)"; "U_Mfy (flexion y)"; "U_Mfz (flexion z)"; "Total"], ...
                [U.UN; U.UTy; U.UTz; U.UMt; U.UMfy; U.UMfz; U.total], 'VariableNames', {'Composante', 'U (J)'});
            bd = chk.bend;
            W.Tables.Check.Data = app.kvTable({
                'Abscisse du point le plus sollicité', chk.s, 'm'
                'N(s)', chk.N / 1e3, 'kN'
                'Ty(s)', chk.Ty / 1e3, 'kN'
                'Mfz(s)', chk.Mfz / 1e3, 'kN·m'
                'Mfy(s)', chk.Mfy / 1e3, 'kN·m'
                'σ traction max', bd.sigmaMaxTraction / 1e6, 'MPa'
                'σ compression max', bd.sigmaMaxCompression / 1e6, 'MPa'
                'Kt·|σ|max', bd.sigmaMaxKt / 1e6, 'MPa'
                'σadm = Re/s', bd.sigmaAdm / 1e6, 'MPa'
                'Résistance', bd.ok, ''});

            % --- rapport
            h = sol.h;
            if sol.isostatic
                hTxt = 'isostatique';
            else
                hTxt = 'hyperstatique';
            end
            lines = {
                'Résultats (unités d''affichage : kN, kN·m, MPa, mm, mrad)'
                sprintf('Degré d''hyperstatisme : total h = %d (%s) — axial %d, flexion (x,y) %d, flexion (x,z) %d, torsion %d ; plan 2D : %d', ...
                h.total, hTxt, h.axial, h.xy, h.xz, h.torsion, h.plan2D)};
            for k = 1:numel(R)
                lines{end + 1, 1} = sprintf('Réaction en %s (%s, s = %.4g m) : Rx = %.5g kN, Ry = %.5g kN, Rz = %.5g kN, Mz = %.5g kN·m, My = %.5g kN·m', ...
                    R(k).name, R(k).type, R(k).pos, R(k).Rx / 1e3, R(k).Ry / 1e3, R(k).Rz / 1e3, R(k).Mz / 1e3, R(k).My / 1e3); %#ok<AGROW>
            end
            e = sol.extrema;
            lines{end + 1, 1} = sprintf('Mfz : max %.5g kN·m (s = %.4g m), min %.5g kN·m (s = %.4g m) ; Ty : max %.5g kN, min %.5g kN', ...
                e.Mfz.max / 1e3, e.Mfz.sMax, e.Mfz.min / 1e3, e.Mfz.sMin, e.Ty.max / 1e3, e.Ty.min / 1e3);
            lines{end + 1, 1} = sprintf('Contrôle coupures / intégrale : écart relatif %.3g', sol.methodCheck);
            di = d.integration;
            lines{end + 1, 1} = sprintf('Flèche maximale (intégration, plan %s) : f = %.5g mm en s = %.4g m ; rotation max |α| = %.5g mrad', ...
                d.plane, di.fmax * 1e3, di.sAtFmax, max(abs(di.alpha)) * 1e3);
            lines{end + 1, 1} = sprintf('Énergie de déformation totale U = %.5g J', U.total);
            lines{end + 1, 1} = sprintf('Vérification : Kt·|σ|max = %.5g MPa en s = %.4g m, σadm = %.5g MPa → %s', ...
                bd.sigmaMaxKt / 1e6, chk.s, bd.sigmaAdm / 1e6, MecaStruct_App.okText(bd.ok));
            lines = [{MecaStruct_App.plainVerdict(bd.sigmaMaxKt / 1e6, bd.sigmaAdm / 1e6, bd.ok)}; lines];
            lines{end + 1, 1} = ['Étape suivante : « Envoyer au tenseur » pour les contraintes principales et les critères, ' ...
                'ou l''onglet Flambage si la poutre est comprimée.'];
            limite = ~isempty(MecaStruct_App.unreliableNote(sol));
            if limite
                lines = [{['⚠ LIMITE DE L''APPLICATION : poutre hyperstatique avec Iyz ≠ 0. Les réactions sont calculées plan par plan ' ...
                    '(couplage y–z des inconnues hyperstatiques ignoré) : réactions, moments et contraintes NON fiables. ' ...
                    'Saisir la section dans ses axes principaux (Iyz = 0).']}; lines];
            end
            app.setReport(W, lines, '=== Statique et torseur de cohésion (moteur, SI) ===', sol.report, ...
                '=== Déformée : 4 méthodes ===', d.report, '=== Vérification de résistance ===', chk.report);
            W.Status.Text = sprintf('h = %d (%s) — f max = %.4g mm — Kt·|σ|max = %.4g MPa (%s)', ...
                h.total, hTxt, di.fmax * 1e3, bd.sigmaMaxKt / 1e6, MecaStruct_App.okText(bd.ok));
            if limite
                W.Status.Text = ['⚠ LIMITE : hyperstatique avec Iyz ≠ 0, résultats NON fiables — ' W.Status.Text];
            end
        end

        function applyNationalAnnex(app)
            % Annexe nationale choisie : renseigne γM0 et γM1 (France : 1,0 et 1,0, comme l'EN ; « autre » : champs libres).
            B = app.H.Beam;
            if any(strcmp(B.na.Value, {'EN', 'FR'}))
                B.gM0.Value = 1;
                B.gM1.Value = 1;
            end
        end

        function [r, T] = checkEurocode(app)
            %CHECKEURODE Vérification Eurocode 3 simplifiée (DesignChecks.ec3Bending) de la poutre calculée.
            %   Efforts : dernier « Calculer » ou enveloppe des combinaisons (réglage « Efforts de calcul »).
            B = app.H.Beam;
            if isempty(app.BeamSection) || ~isfield(app.BeamSection, 'sec')
                error('MecaStruct:App:invalidInput', ['Eurocode 3 : la section doit venir d''un profilé ou d''un profil en I ' ...
                    '(« Importer depuis Sections » ou exemple), pas de valeurs saisies à la main.']);
            end
            d = DesignChecks.ibeamDims(app.BeamSection.sec);
            if strcmp(B.ecsrc.Value, 'enveloppe')
                app.computeCombinations();   % efforts à jour : la saisie a pu changer depuis le dernier calcul
                c = app.Results.combos(end, :);
                MEd = max(abs([c.("Mfz max (kN·m)"), c.("Mfz min (kN·m)")])) * 1e3;
                VEd = max(abs([c.("Ty max (kN)"), c.("Ty min (kN)")])) * 1e3;
                src = 'enveloppe des combinaisons';
                Nmax = c.("N max (kN)") * 1e3;
                Nmin = c.("N min (kN)") * 1e3;
                ignored = '';
            else
                if ~isfield(app.Results, 'beamInputs') || ~isequaln(app.Results.beamInputs, {app.captureInputs('Beam'), app.BeamSection})
                    app.computeBeam();   % la saisie a changé depuis le dernier calcul : efforts à refaire
                end
                e = app.Results.beam.sol.extrema;
                MEd = max(abs([e.Mfz.max, e.Mfz.min]));
                VEd = max(abs([e.Ty.max, e.Ty.min]));
                src = 'poutre recalculée avec la saisie actuelle (tous les cas à 1)';
                Nmax = e.N.max;
                Nmin = e.N.min;
                My = max(abs([e.Mfy.max, e.Mfy.min])) / 1e3;
                ignored = '';
                if My > 1e-6
                    ignored = sprintf('Mfy max = %.4g kN·m (flexion déviée non prise en compte)', My);
                end
            end
            NEd = max(abs([Nmax, Nmin]));            % N > 0 : traction ; on associe le N maximal au M maximal (prudent)
            Ncomp = max(0, -Nmin);
            fy = app.si(B.Re, 'MPa');
            r = DesignChecks.ec3Bending(d, app.si(B.S, 'mm^2'), app.si(B.Iz, 'mm^4'), fy, B.gM0.Value, MEd, VEd, Ncomp);
            Lcr = B.Lcr.Value;
            if Lcr <= 0
                Lcr = B.L.Value;
            end
            LcrF = B.LcrF.Value;
            if LcrF <= 0
                LcrF = B.L.Value;   % plan fort : les entretoises latérales ne le réduisent pas
            end
            ltb = DesignChecks.ec3LateralTorsional(d, strcmp(app.BeamSection.sec.type, 'profile'), r.W, fy, B.gM1.Value, ...
                app.si(B.E, 'GPa'), app.si(B.G, 'GPa'), app.si(B.Iy, 'mm^4'), app.si(B.Ix, 'mm^4'), Lcr, B.C1.Value, MEd);
            r.ltb = ltb;
            A = app.si(B.S, 'mm^2');
            r.axial = DesignChecks.ec3AxialBending(d, r, A, fy, B.gM0.Value, NEd, MEd);
            r.buck = [];
            if Ncomp > 0
                r.buck = DesignChecks.ec3FlexuralBuckling(d, strcmp(app.BeamSection.sec.type, 'profile'), A, ...
                    app.si(B.Iz, 'mm^4'), app.si(B.Iy, 'mm^4'), [LcrF Lcr], fy, app.si(B.E, 'GPa'), B.gM1.Value, Ncomp);
            end
            r.inter = [];
            if Ncomp > 0 && MEd > 0 && r.class.class <= 3
                r.inter = DesignChecks.ec3Interaction(r.class.class, r.buck, ltb, A, r.W, fy, B.gM1.Value, Ncomp, MEd, B.Cmy.Value, B.CmLT.Value);
            end
            r.web = DesignChecks.ec3WebShear(d, fy, B.gM1.Value, VEd);
            r.partial = false;
            r.Ncomp = Ncomp;   % compression retenue pour la classe (le dossier la refait à la main)
            r.okAll = r.ok && ltb.ok && r.axial.ok && (isempty(r.buck) || r.buck.ok) && (isempty(r.inter) || r.inter.ok) && r.web.ok;
            cl = r.class;
            redTxt = 'non';
            if r.reduced
                redTxt = 'oui';
            end
            rows = {
                'Efforts utilisés', src, ''
                'fy = Re (EN 1993-1-1 tab. 3.1 : fy dépend de l''épaisseur, non pris en compte)', fy / 1e6, 'MPa'
                'γM0 [EN 1993-1-1 §6.1(1), valeur recommandée 1,0]', B.gM0.Value, '-'
                'Classe de l''aile (c/tf) [tab. 5.2 : 9ε, 10ε, 14ε]', sprintf('%d (%.2f)', cl.classFlange, cl.ratioFlange), ''
                'Classe de l''âme (c/tw) [tab. 5.2 : 72ε, 83ε, 124ε]', sprintf('%d (%.2f)', cl.classWeb, cl.ratioWeb), ''
                'Classe de la section [§5.5]', cl.class, '-'
                'Wpl,y', r.Wpl * 1e6, 'cm³'
                'Wel,y', r.Wel * 1e6, 'cm³'
                'Mc,Rd = W·fy/γM0 [§6.2.5(2), éq. 6.13 / 6.14]', r.Mc / 1e3, 'kN·m'
                'Av [§6.2.6(3)]', r.Av * 1e6, 'mm²'
                'Vpl,Rd = Av·(fy/√3)/γM0 [§6.2.6(2), éq. 6.18]', r.Vpl / 1e3, 'kN'
                'MEd', r.MEd / 1e3, 'kN·m'
                'VEd', r.VEd / 1e3, 'kN'
                'Moment réduit par le tranchant, VEd > 0,5 Vpl,Rd [§6.2.8]', redTxt, ''
                'MEd / MRd [éq. 6.12]', r.ratioM, '-'
                'VEd / Vpl,Rd [éq. 6.17]', r.ratioV, '-'
                'Résistance des sections', r.ok, ''
                'Lcr (entretoises : flambement faible et déversement)', Lcr, 'm'
                'Lcr,y (flambement dans le plan fort ; 0 = L)', LcrF, 'm'
                'Mcr [NCCI SN003, appuis à fourches]', ltb.Mcr / 1e3, 'kN·m'
                'λ̄LT = √(W·fy/Mcr) [§6.3.2.2]', ltb.lambda, '-'
                sprintf('Courbe %s, αLT [tab. 6.5 puis tab. 6.3]', ltb.curve), ltb.alpha, '-'
                'χLT [§6.3.2.3, éq. 6.57, λ̄LT,0 = 0,4, β = 0,75]', ltb.chi, '-'
                'Mb,Rd = χLT·W·fy/γM1 [éq. 6.55]', ltb.MbRd / 1e3, 'kN·m'
                'MEd / Mb,Rd [éq. 6.54]', ltb.ratio, '-'
                'Déversement', ltb.ok, ''
                'NEd (traction ou compression, au maximum)', NEd / 1e3, 'kN'
                'Npl,Rd = A·fy/γM0 [§6.2.4, éq. 6.6]', r.axial.Npl / 1e3, 'kN'};
            ax = r.axial;
            if ax.class12
                rows = [rows; {
                    'n = NEd/Npl,Rd ; a = (A − 2b·tf)/A ≤ 0,5 [§6.2.9.1(5)]', sprintf('n = %.3f ; a = %.3f', ax.n, ax.a), ''
                    'MN,y,Rd = Mpl,y,Rd·(1 − n)/(1 − 0,5a) [éq. 6.36, sans réduction si 6.33 et 6.34]', ax.MNRd / 1e3, 'kN·m'
                    'MEd / MN,y,Rd', ax.ratio, '-'}];
            else
                rows = [rows; {
                    'σx,Ed = NEd/A + MEd/Wel [§6.2.9.2, éq. 6.42]', ax.sigma / 1e6, 'MPa'
                    'σx,Ed / (fy/γM0)', ax.ratio, '-'}];
            end
            rows = [rows; {'Flexion + effort normal', ax.ok, ''}];
            if ~isempty(r.buck)
                for k = 1:2
                    a = r.buck.axes(k);
                    rows = [rows; {
                        sprintf('Flambement %s : Ncr = π²EI/Lcr² [§6.3.1.2, éq. 6.50]', a.axis), a.Ncr / 1e3, 'kN'
                        sprintf('Flambement %s : λ̄, courbe %s, α = %.2f [tab. 6.2, tab. 6.1]', a.axis, a.curve, a.alpha), a.lambda, '-'
                        sprintf('Flambement %s : χ [éq. 6.49]', a.axis), a.chi, '-'
                        sprintf('Flambement %s : Nb,Rd = χ·A·fy/γM1 [éq. 6.47]', a.axis), a.NbRd / 1e3, 'kN'}]; %#ok<AGROW>
                end
                rows = [rows; {
                    'NEd,compression / Nb,Rd [éq. 6.46]', r.buck.ratio, '-'
                    'Flambement', r.buck.ok, ''}];
            end
            if ~isempty(r.inter)
                it = r.inter;
                rows = [rows; {
                    'Interaction N + M, nY = NEd/(χy·NRk/γM1) ; nZ [§6.3.3, annexe B]', sprintf('nY = %.3f ; nZ = %.3f', it.nY, it.nZ), ''
                    'kyy, kzy [annexe B, méthode 2, tableau B.2 ; Cmy, CmLT]', sprintf('kyy = %.3f ; kzy = %.3f (Cmy = %.2f, CmLT = %.2f)', it.kyy, it.kzy, it.Cmy, it.CmLT), ''
                    'NEd/(χy·NRk/γM1) + kyy·MEd/(χLT·My,Rk/γM1) [éq. 6.61]', it.ratio61, '-'
                    'NEd/(χz·NRk/γM1) + kzy·MEd/(χLT·My,Rk/γM1) [éq. 6.62]', it.ratio62, '-'
                    'Interaction N + M', it.ok, ''}];
            elseif Ncomp > 0 && MEd > 0
                rows = [rows; {'ATTENTION', 'N de compression et M présents mais section de classe 4 : interaction non vérifiée', ''}];
            end
            w = r.web;
            if w.needed
                rows = [rows; {
                    'Voilement de l''âme par cisaillement : hw/tw > 72ε/η, vérification requise [EN 1993-1-5 §5]', sprintf('hw/tw = %.1f > %.1f', w.hwTw, w.limit), ''
                    'λ̄w = hw/(86,4·tw·ε) ; χw [tab. 5.1, poteau d''extrémité rigide]', sprintf('λ̄w = %.3f ; χw = %.3f', w.lambda, w.chi), ''
                    'Vb,Rd = χw·fy·hw·tw/(√3·γM1) (semelles négligées)', w.VbRd / 1e3, 'kN'
                    'VEd / Vb,Rd', w.ratio, '-'
                    'Voilement de l''âme', w.ok, ''}];
            else
                rows = [rows; {'Voilement de l''âme par cisaillement', sprintf('sans objet : hw/tw = %.1f ≤ 72ε/η = %.1f [EN 1993-1-1 §6.2.6(6)]', w.hwTw, w.limit), ''}];
            end
            switch B.na.Value
                case 'FR'
                    naTxt = 'France : γM0 = 1,0 ; γM1 = 1,0 ; γM2 = 1,25 (mêmes valeurs que l''EN) ; courbes de flambement et de déversement : valeurs recommandées de l''EN (non comparées au texte de l''annexe française)';
                case 'autre'
                    naTxt = sprintf('autre pays : γM0 = %.3g et γM1 = %.3g saisis ; autres paramètres : valeurs recommandées de l''EN', B.gM0.Value, B.gM1.Value);
                otherwise
                    naTxt = 'valeurs recommandées de l''EN (γM0 = γM1 = 1,0)';
            end
            rows = [rows; {
                'Eurocode 3 (sections, voilement, déversement, N + M, flambement)', r.okAll, ''
                'Non vérifié', 'voilement local sous charges concentrées (EN 1993-1-5 §6), flexion déviée, ELS, assemblages, classe 4', ''
                'Annexe nationale', naTxt, ''
                'Sources', 'docs/NORMES.md', ''}];
            note = MecaStruct_App.unreliableNote(BeamAndTrussSolver.solveBeam(app.readBeamModel()));
            if ~isempty(note)
                rows(end + 1, :) = {'Résultats non fiables', 'poutre hyperstatique avec Iyz ≠ 0 : réactions et efforts plan par plan', ''};
            end
            if ~isempty(ignored)
                rows(end + 1, :) = {'Efforts ignorés', ignored, ''};
            end
            T = app.kvTable(rows);
            B.W.Tables.EC3.Data = T;
            B.W.ResGroup.SelectedTab = ancestor(B.W.Tables.EC3, 'uitab');
            app.Results.ec3 = r;
            B.W.Status.Text = sprintf('%sEurocode 3 : classe %d, MEd/MRd = %.3f, VEd/Vpl,Rd = %.3f, MEd/Mb,Rd = %.3f (%s)', ...
                note, cl.class, r.ratioM, r.ratioV, ltb.ratio, MecaStruct_App.okText(r.okAll));
            if ~isempty(r.inter)
                B.W.Status.Text = sprintf('%s, N + M (6.61/6.62) = %.3f', B.W.Status.Text, r.inter.ratio);
            end
        end

        function [r, T] = checkFatigue(app)
            %CHECKFATIGUE Coefficient de sécurité en fatigue (Goodman) au point le plus sollicité du dernier calcul.
            %   σmax nominale = Kt·σ / Kt du dernier « Calculer » ; Kf = Kt ; amplitude σa = Kf·σmax·(1−R)/2.
            B = app.H.Beam;
            if ~isfield(app.Results, 'beam') || isempty(app.Results.beam)
                error('MecaStruct:App:invalidInput', 'Calculez d''abord la poutre (« Calculer »).');
            end
            Kt = B.Kt.Value;
            if ~(Kt >= 1)
                error('MecaStruct:App:invalidInput', 'Fatigue : Kt doit être ≥ 1.');
            end
            sigMax = app.Results.beam.check.bend.sigmaMaxKt / Kt;
            Rm = app.DM.getMaterial(B.mat.Value).Rm;
            if ~(isfinite(Rm) && Rm > 0)
                error('MecaStruct:App:invalidInput', 'Fatigue : Rm inconnu pour « %s ».', B.mat.Value);
            end
            r = DesignChecks.goodman(sigMax, B.fR.Value, Kt, Rm, B.fka.Value, B.fkb.Value);
            ok = r.n >= B.s.Value;
            rows = {
                'Contrainte nominale max σmax', sigMax / 1e6, 'MPa'
                'R = σmin / σmax', B.fR.Value, '-'
                'Kf (= Kt)', Kt, '-'
                'Amplitude σa = Kf·σmax·(1−R)/2', r.sigmaA / 1e6, 'MPa'
                'Contrainte moyenne σm', r.sigmaM / 1e6, 'MPa'
                'Rm', Rm / 1e6, 'MPa'
                'Limite d''endurance Se = ka·kb·0,5·Rm', r.Se / 1e6, 'MPa'
                'Coefficient de sécurité n = 1 / (σa/Se + σm/Rm)', r.n, '-'
                'Coefficient exigé s', B.s.Value, '-'
                'Fatigue (Goodman)', ok, ''
                'Hypothèses', 'acier, vie infinie, Kf = Kt, chargement uniaxial d''amplitude constante', ''};
            T = app.kvTable(rows);
            B.W.Tables.Fat.Data = T;
            B.W.ResGroup.SelectedTab = ancestor(B.W.Tables.Fat, 'uitab');
            app.Results.fatigue = r;
            B.W.Status.Text = sprintf('Fatigue (Goodman) : n = %.3g pour s = %.3g (%s)', r.n, B.s.Value, MecaStruct_App.okText(ok));
        end

        function [T, best] = findLightestProfile(app, family, deflRatio)
            %FINDLIGHTESTPROFILE Essaie chaque profilé d'une famille avec le chargement de l'onglet Poutres.
            %   [T, best] = app.findLightestProfile('IPE') ; deflRatio : flèche limitée à L/deflRatio (0 = ignorée).
            %   Les champs de section de l'onglet sont remplacés le temps du calcul puis remis. T est trié par aire
            %   croissante ; best = nom du premier profilé qui vérifie (résistance et, si demandé, flèche), '' sinon.
            if nargin < 3 || isempty(deflRatio)
                deflRatio = 0;
            end
            B = app.H.Beam;
            inputs0 = {app.captureInputs('Beam'), app.BeamSection, app.BeamUsesSection};   % saisie avant le balayage (cache de l'export)
            names = cellstr(app.DM.listProfiles(family));
            flds = {'S', 'Iz', 'Iy', 'Ix', 'ky', 'kz', 'vy', 'vz', 'Iyz'};
            old = cellfun(@(f) B.(f).Value, flds, 'UniformOutput', false);
            oldUse = app.BeamUsesSection;
            oldSec = app.BeamSection;
            restore = onCleanup(@() app.restoreBeamSection(flds, old, oldUse, oldSec)); %#ok<NASGU>
            rho = app.DM.getMaterial(B.mat.Value).rho;
            n = numel(names);
            v = nan(n, 6);
            verdict = strings(n, 1);
            ok = false(n, 1);
            for i = 1:n
                p = app.DM.getProfile(family, names{i});
                P = GeometryEngine.analytical(GeometryEngine.fromProfile(p));
                Pt = GeometryEngine.tabulated(GeometryEngine.fromProfile(p));
                B.S.Value = p.S * 1e6;
                B.Iz.Value = p.Iz * 1e12;
                B.Iy.Value = p.Iy * 1e12;
                B.Ix.Value = P.J * 1e12;
                B.ky.Value = Pt.ky;
                B.kz.Value = Pt.kz;
                B.Iyz.Value = 0;
                B.vy.Value = p.h / 2 * 1e3;
                B.vz.Value = p.b / 2 * 1e3;
                app.BeamUsesSection = false;
                try
                    sol = BeamAndTrussSolver.solveBeam(app.readBeamModel());
                    d = SolicitationsEngine.deflection(sol.model, sol, ...
                        struct('plane', B.plane.Value, 'includeShear', logical(B.shear.Value)));
                    chk = app.beamCheck(sol);
                    f = d.integration.fmax * 1e3;
                    okF = deflRatio <= 0 || f <= sol.model.L * 1e3 / deflRatio;
                    v(i, :) = [p.S * 1e6, rho * p.S, chk.bend.sigmaMaxKt / 1e6, chk.bend.sigmaAdm / 1e6, f, ...
                        sol.model.L * 1e3 / max(f, eps)];
                    ok(i) = logical(chk.bend.ok) && okF;
                    verdict(i) = string(MecaStruct_App.okText(ok(i)));
                catch err
                    verdict(i) = "erreur : " + string(err.message);
                end
            end
            [~, ord] = sort(v(:, 1));
            T = table(string(names(:)), v(:, 1), v(:, 2), v(:, 3), v(:, 4), v(:, 5), v(:, 6), verdict, 'VariableNames', ...
                {'Profilé', 'S (mm²)', 'Masse (kg/m)', 'Kt·σ max (MPa)', 'σadm (MPa)', 'f max (mm)', 'L/f (-)', 'Résistance'});
            T = T(ord, :);
            okS = ok(ord);
            best = '';
            if any(okS)
                best = char(T.("Profilé")(find(okS, 1)));
            end
            B.W.Tables.Prof.Data = T;
            B.W.ResGroup.SelectedTab = ancestor(B.W.Tables.Prof, 'uitab');
            app.Results.profiles = T;
            app.Results.profilesInputs = inputs0;
            if isempty(best)
                B.W.Status.Text = sprintf('Aucun profilé %s ne vérifie ce chargement : essayer une autre famille.', family);
            else
                B.W.Status.Text = sprintf('Profilé %s le plus léger qui vérifie : %s. La saisie de la section est inchangée.', family, best);
            end
        end

        function restoreBeamSection(app, flds, old, oldUse, oldSec)
            B = app.H.Beam;
            for k = 1:numel(flds)
                B.(flds{k}).Value = old{k};
            end
            app.BeamUsesSection = oldUse;
            app.BeamSection = oldSec;
        end

        function T = computeCombinations(app)
            %COMPUTECOMBINATIONS Résout chaque combinaison de cas (tableau Combinaisons) puis donne l'enveloppe.
            %   Superposition de cas : exacte pour une poutre linéaire (isostatique ou hyperstatique).
            %   Résultat : table, aussi affichée dans l'onglet Combinaisons et exportable.
            B = app.H.Beam;
            c = B.combo.Data;
            if isempty(c)
                error('MecaStruct:App:invalidInput', 'Aucune combinaison : ajoutez une ligne au tableau Combinaisons.');
            end
            n = size(c, 1);
            v = nan(n, 9);
            verdict = strings(n, 1);
            ok = true(n, 1);
            note = '';
            for i = 1:n
                fac = struct('G', MecaStruct_App.cellNum(c{i, 2}, 'γG'), 'Q', MecaStruct_App.cellNum(c{i, 3}, 'γQ'), ...
                    'W', MecaStruct_App.cellNum(c{i, 4}, 'γW'), 'S', MecaStruct_App.cellNum(c{i, 5}, 'γS'));
                try
                    sol = BeamAndTrussSolver.solveBeam(app.readBeamModel(fac));
                    note = MecaStruct_App.unreliableNote(sol);
                    d = SolicitationsEngine.deflection(sol.model, sol, ...
                        struct('plane', B.plane.Value, 'includeShear', logical(B.shear.Value)));
                    chk = app.beamCheck(sol);
                    e = sol.extrema;
                    v(i, 1:6) = [e.Mfz.max e.Mfz.min e.Ty.max e.Ty.min e.N.max e.N.min] / 1e3;
                    v(i, 7:9) = [d.integration.fmax * 1e3, chk.bend.sigmaMaxKt / 1e6, chk.bend.sigmaAdm / 1e6];
                    ok(i) = logical(chk.bend.ok);
                    verdict(i) = string(MecaStruct_App.okText(chk.bend.ok));
                catch err
                    ok(i) = false;
                    verdict(i) = "erreur : " + string(err.message);
                end
            end
            ok(isnan(v(:, 1))) = false;
            row = nan(1, 9);
            row([1 3 5 7 8]) = max(v(:, [1 3 5 7 8]), [], 1, 'omitnan');
            row([2 4 6]) = min(v(:, [2 4 6]), [], 1, 'omitnan');
            r9 = v(~isnan(v(:, 9)), 9);
            if ~isempty(r9), row(9) = r9(1); end
            allOk = all(ok);
            T = table([string(c(:, 1)); "Enveloppe"], [v(:, 1); row(1)], [v(:, 2); row(2)], [v(:, 3); row(3)], [v(:, 4); row(4)], ...
                [v(:, 5); row(5)], [v(:, 6); row(6)], [v(:, 7); row(7)], [v(:, 8); row(8)], [v(:, 9); row(9)], ...
                [verdict; string(MecaStruct_App.okText(allOk))], 'VariableNames', {'Combinaison', 'Mfz max (kN·m)', ...
                'Mfz min (kN·m)', 'Ty max (kN)', 'Ty min (kN)', 'N max (kN)', 'N min (kN)', 'f max (mm)', ...
                'Kt·σ max (MPa)', 'σadm (MPa)', 'Résistance'});
            B.W.Tables.Combo.Data = T;
            B.W.ResGroup.SelectedTab = ancestor(B.W.Tables.Combo, 'uitab');
            app.Results.combos = T;
            B.W.Status.Text = sprintf('%sCombinaisons : %d calculée(s), enveloppe Kt·σ max = %.4g MPa (%s)', note, n, row(8), ...
                MecaStruct_App.okText(allOk));
        end

        function [T, env] = computeMovingLoad(app)
            %COMPUTEMOVINGLOAD Enveloppe d'un convoi de charges mobiles (1 à n essieux) sur la poutre.
            %   La poutre est résolue pour chaque position du convoi ; l'enveloppe de Mfz, Ty et des réactions
            %   est le max et le min sur les positions (grille réglable plus positions critiques, voir plus bas). Avec « charges fixes »
            %   décoché, seul le convoi est appliqué (ni charges saisies, ni tassement, ni température).
            %   T : table de l'enveloppe le long de la poutre (101 points) ; env : s, Mmax, Mmin, Tmax, Tmin,
            %   extrema exacts (de chaque position) et réactions extrêmes.
            B = app.H.Beam;
            model = app.readBeamModel();
            L = model.L;
            P = MecaStruct_App.parseNumbers(B.mvP.Value, 'Essieux') * 1e3;
            if isempty(P)
                error('MecaStruct:App:invalidInput', 'Charge mobile : saisissez au moins une charge d''essieu (kN).');
            end
            gaps = MecaStruct_App.parseNumbers(B.mvE.Value, 'Écartements');
            if isscalar(gaps)
                gaps = repmat(gaps, 1, numel(P) - 1);   % un seul écartement pour tous (aucun pour un essieu seul)
            end
            if numel(gaps) ~= numel(P) - 1 || any(gaps <= 0)
                error('MecaStruct:App:invalidInput', 'Charge mobile : %d essieu(x) demandent %d écartement(s) positif(s) (ou un seul pour tous).', numel(P), numel(P) - 1);
            end
            if numel(P) > 20
                error('MecaStruct:App:invalidInput', 'Charge mobile : 20 essieux au plus.');
            end
            nPos = round(B.mvN.Value);
            if ~(nPos >= 2 && nPos <= 500)
                error('MecaStruct:App:invalidInput', 'Charge mobile : 2 à 500 positions de base.');
            end
            offs = [0 cumsum(gaps)];
            if ~B.mvFixed.Value
                model.pointLoads = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
                model.pointMoments = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
                model.distLoads = struct('a', {}, 'b', {}, 'dir', {}, 'coeffs', {}, 'name', {});
                model.thermal = struct('epsX', 0, 'kv', 0, 'kw', 0);
                for i = 1:numel(model.supports)
                    model.supports(i).dx = 0; model.supports(i).dy = 0; model.supports(i).dz = 0;
                end
            end
            nF = numel(model.pointLoads);
            s = linspace(0, L, 101);
            hi = -inf(size(s)); lo = inf(size(s)); thi = -inf(size(s)); tlo = inf(size(s));
            ext = struct('Mmax', -inf, 'Mmin', inf, 'Tmax', -inf, 'Tmin', inf);
            ns = numel(model.supports);
            Rmax = -inf(1, ns); Rmin = inf(1, ns);
            % Positions du convoi : la grille, puis chaque essieu sur un appui, une rotule ou un point du tableau (moment et
            % réaction sont linéaires entre ces positions), et la symétrie « essieu et résultante de part et d'autre du
            % milieu » qui donne le moment maximal sous un essieu sur appuis simples.
            pts = [[model.supports.pos], [model.hinges.pos], s];
            cand = [linspace(-offs(end), L, nPos), reshape(pts(:) - offs, 1, [])];
            if abs(sum(P)) > 0
                offR = sum(P .* offs) / sum(P);
                cand = [cand, (L - offs - offR) / 2];
            end
            x0 = unique(cand);
            used = 0;
            for p = 1:numel(x0)
                xs = x0(p) + offs;
                on = xs >= -1e-9 & xs <= L + 1e-9;   % tolérance : un essieu posé sur un appui reste compté
                if ~any(on), continue, end
                m = model;
                for k = find(on)
                    m.pointLoads(end + 1) = struct('pos', min(max(xs(k), 0), L), 'Fx', 0, 'Fy', P(k), 'Fz', 0, 'name', sprintf('E%d', k)); %#ok<AGROW>
                end
                sol = BeamAndTrussSolver.solveBeam(m, struct('internalMethod', 'coupures', 'hyperMethod', 'menabrea', 'useSymbolic', false));
                M = BeamAndTrussSolver.ppEval(sol.Mfz, s, 'left');
                M2 = BeamAndTrussSolver.ppEval(sol.Mfz, s, 'right');
                Ty = BeamAndTrussSolver.ppEval(sol.Ty, s, 'left');
                Ty2 = BeamAndTrussSolver.ppEval(sol.Ty, s, 'right');
                hi = max(hi, max(M(:).', M2(:).')); lo = min(lo, min(M(:).', M2(:).'));
                thi = max(thi, max(Ty(:).', Ty2(:).')); tlo = min(tlo, min(Ty(:).', Ty2(:).'));
                e = sol.extrema;
                ext.Mmax = max(ext.Mmax, e.Mfz.max); ext.Mmin = min(ext.Mmin, e.Mfz.min);
                ext.Tmax = max(ext.Tmax, e.Ty.max); ext.Tmin = min(ext.Tmin, e.Ty.min);
                R = [sol.reactions.Ry];
                Rmax = max(Rmax, R); Rmin = min(Rmin, R);
                used = used + 1;
            end
            if used == 0
                error('MecaStruct:App:invalidInput', 'Charge mobile : aucun essieu sur la poutre.');
            end
            env = struct('s', s, 'Mmax', hi, 'Mmin', lo, 'Tmax', thi, 'Tmin', tlo, 'extrema', ext, ...
                'Rmax', Rmax, 'Rmin', Rmin, 'names', {{model.supports.name}}, 'positions', used, 'fixedLoads', nF);
            T = table(s(:), hi(:) / 1e3, lo(:) / 1e3, thi(:) / 1e3, tlo(:) / 1e3, 'VariableNames', ...
                {'s (m)', 'Mfz max (kN·m)', 'Mfz min (kN·m)', 'Ty max (kN)', 'Ty min (kN)'});
            app.Results.moving = struct('table', T, 'env', env);
            B.W.Tables.Mov.Data = T;
            PlotEngine.movingEnvelope(B.W.Axes{5}, env);
            app.finishAxes(B.W.Axes{5});
            if strcmp(app.UIFigure.Visible, 'on')
                B.W.PlotGroup.SelectedTab = B.W.PlotGroup.Children(5);   % montre l'enveloppe à l'utilisateur
            end
            rt = strings(1, ns);
            for i = 1:ns
                rt(i) = sprintf('%s : %.4g à %.4g kN', model.supports(i).name, Rmin(i) / 1e3, Rmax(i) / 1e3);
            end
            B.W.Status.Text = sprintf('%sCharge mobile (%d positions) : Mfz de %.4g à %.4g kN·m, Ty de %.4g à %.4g kN ; réactions Ry %s', ...
                MecaStruct_App.unreliableNote(sol), used, ext.Mmin / 1e3, ext.Mmax / 1e3, ext.Tmin / 1e3, ext.Tmax / 1e3, strjoin(rt, ' ; '));
        end

        function loadFromBeam(app, key, mode)
            %LOADFROMBEAM Remplit N, Mfz, Mfy (et Ty) de l'onglet Sections ou Flexion avec les efforts de la poutre.
            %   app.loadFromBeam(key, mode) : key = 'Sec' ou 'Fle' ; mode = 'abscisse' (coupure en s, champ
            %   « s sur la poutre ») ou 'max' (point le plus sollicité en contrainte). La poutre est calculée
            %   au besoin. Les efforts sont ceux du torseur de cohésion (convention : actions à droite).
            if ~any(strcmp(key, {'Sec', 'Fle'}))
                error('MecaStruct:App:invalidInput', 'key doit valoir ''Sec'' ou ''Fle''.');
            end
            app.computeBeam();   % toujours : les saisies de la poutre ont pu changer depuis le dernier calcul
            R = app.Results.beam;
            H = app.H.(key);
            if strcmp(mode, 'max')
                s = R.check.s;
            else
                s = H.s0.Value;
                L = R.sol.model.L;
                if ~(s >= 0 && s <= L)
                    error('MecaStruct:App:invalidInput', 'L''abscisse s doit être comprise entre 0 et L = %.4g m.', L);
                end
            end
            ev = @(pp) BeamAndTrussSolver.ppEval(pp, s);
            if strcmp(mode, 'max')
                % efforts du côté de la discontinuité retenu par beamCheck (ppEval prendrait la limite à droite)
                c = R.check;
                H.N.Value = c.N / 1e3;
                H.Mfz.Value = c.Mfz / 1e3;
                H.Mfy.Value = c.Mfy / 1e3;
                if isfield(H, 'Ty')
                    H.Ty.Value = c.Ty / 1e3;
                end
            else
                H.N.Value = ev(R.sol.N) / 1e3;
                H.Mfz.Value = ev(R.sol.Mfz) / 1e3;
                H.Mfy.Value = ev(R.sol.Mfy) / 1e3;
                if isfield(H, 'Ty')
                    H.Ty.Value = ev(R.sol.Ty) / 1e3;
                end
            end
            H.s0.Value = s;
            H.W.Status.Text = sprintf('%sEfforts lus sur la poutre en s = %.4g m : N = %.4g kN, Mfz = %.4g kN·m, Mfy = %.4g kN·m', ...
                MecaStruct_App.unreliableNote(R.sol), s, H.N.Value, H.Mfz.Value, H.Mfy.Value);
            % la contrainte se calcule avec la section de l'onglet Sections, pas forcément celle de la poutre
            Pb = app.beamSectionProps();
            sameSec = ~isempty(app.BeamSection) && ~isempty(app.SectionData) && isequal(app.BeamSection.sec, app.SectionData.sec);
            if ~isempty(app.SectionData) && ~sameSec && abs(Pb.Iz - app.SectionData.P.Iz) > 1e-3 * app.SectionData.P.Iz
                H.W.Status.Text = [H.W.Status.Text sprintf(['  ⚠ Attention : la section de l''onglet Sections (Iz = %.4g mm⁴) ' ...
                    'diffère de celle de la poutre (Iz = %.4g mm⁴) : les contraintes ne concernent pas la même section.'], ...
                    app.SectionData.P.Iz * 1e12, Pb.Iz * 1e12)];
            end
        end

        function sendToTensor(app)
            %SENDTOTENSOR Transmet l'état de contrainte du point le plus sollicité de la poutre
            %   (σxx, contraintes de flexion composée) à l'onglet Tenseurs & Critères et le calcule.
            app.computeBeam();
            chk = app.Results.beam.check;
            T = app.H.Ten;
            T.sig.Data = [chk.sigma / 1e6 0 0; 0 0 0; 0 0 0];
            T.mat.Value = app.H.Beam.mat.Value;
            app.applyMaterial('Ten');
            T.Re.Value = app.H.Beam.Re.Value;
            T.s.Value = app.H.Beam.s.Value;
            app.selectTab('Tenseurs');
            app.computeTensor();
            T.W.Status.Text = sprintf('État reçu de la poutre : s = %.4g m, (y, z) = (%.4g ; %.4g) mm, σxx = %.5g MPa', ...
                chk.s, chk.loc(1) * 1e3, chk.loc(2) * 1e3, chk.sigma / 1e6);
        end

        function computeTruss(app)
            %COMPUTETRUSS Treillis articulé plan : efforts (nœuds et rigidité), réactions, tracé.
            T = app.H.Tr;
            W = T.W;
            truss = app.readTruss();
            tsol = BeamAndTrussSolver.solveTruss(truss);
            scale = T.scale.Value;
            if scale <= 0
                scale = [];
            end
            PlotEngine.truss(W.Axes{1}(1), truss, tsol, scale);
            app.finishWork(W);
            m = size(truss.bars, 1);
            nm = truss.names;
            noeuds = strings(m, 1);
            for i = 1:m
                noeuds(i) = string(nm{truss.bars(i, 1)}) + "–" + string(nm{truss.bars(i, 2)});
            end
            W.Tables.Bars.Data = table((1:m).', noeuds, tsol.L0(:), tsol.N(:) / 1e3, string(tsol.nature(:)), ...
                tsol.sigma(:) / 1e6, tsol.dL(:) * 1e3, 'VariableNames', ...
                {'Barre', 'Nœuds', 'L (m)', 'N (kN)', 'Nature', 'σ (MPa)', 'ΔL (mm)'});
            sup = any(truss.supports, 2);
            W.Tables.Reac.Data = table(string(nm(sup)), tsol.reactions(sup, 1) / 1e3, tsol.reactions(sup, 2) / 1e3, ...
                'VariableNames', {'Nœud', 'Rx (kN)', 'Ry (kN)'});
            W.Tables.Disp.Data = table(string(nm(:)), tsol.displacements(:, 1) * 1e3, tsol.displacements(:, 2) * 1e3, ...
                'VariableNames', {'Nœud', 'ux (mm)', 'uy (mm)'});
            if tsol.mechanism
                hTxt = 'mécanisme, chargement compatible : déplacements non uniques (norme minimale)';
            elseif tsol.isostatic
                hTxt = 'isostatique';
            elseif tsol.h > 0
                hTxt = 'hyperstatique';
            else
                hTxt = 'hypostatique';
            end
            [nMax, iMax] = max(abs(tsol.N));
            lines = {
                sprintf('Treillis plan : %d nœuds, %d barres ; h = m + r − 2n = %d (%s) ; méthode : %s', ...
                size(truss.nodes, 1), m, tsol.h, hTxt, tsol.methodUsed)
                sprintf('Effort maximal : |N| = %.5g kN dans la barre %d (%s) ; σ = %.5g MPa', nMax / 1e3, iMax, noeuds(iMax), tsol.sigma(iMax) / 1e6)};
            app.setReport(W, lines, '=== Démarche (moteur, SI) ===', tsol.report);
            W.Status.Text = sprintf('h = %d (%s) — |N|max = %.4g kN', tsol.h, hTxt, nMax / 1e3);
            app.Results.truss = struct('truss', truss, 'tsol', tsol);
        end

        function computeTraction(app)
            %COMPUTETRACTION Traction/compression (+ thermique, Kt, section variable S(x)).
            T = app.H.Tra;
            W = T.W;
            p = struct('N', app.si(T.N, 'kN'), 'S0', app.si(T.S0, 'mm^2'), 'L0', T.L0.Value, ...
                'E', app.si(T.E, 'GPa'), 'nu', T.nu.Value, 'alpha', app.si(T.alpha, '1e-6/°C'), ...
                'dT', T.dT.Value, 'Kt', T.Kt.Value, 'Re', app.si(T.Re, 'MPa'), 's', T.s.Value);
            if T.dLmax.Value > 0
                p.dLmax = app.si(T.dLmax, 'mm');
            end
            x = linspace(0, p.L0, 201);
            if T.varS.Value
                fS = MecaStruct_App.parseFunction(T.Sexpr.Value);
                Sx = DataManager.toSI(fS(x), 'mm^2');
                if any(~isfinite(Sx)) || any(Sx <= 0) || ~isreal(Sx)
                    error('MecaStruct:App:invalidExpression', 'S(x) doit être réelle, finie et strictement positive sur [0, L0].');
                end
                p.Sfun = @(xx) DataManager.toSI(fS(xx), 'mm^2');
            else
                Sx = p.S0 * ones(size(x));
            end
            r = SolicitationsEngine.traction(p);
            ax = W.Axes{1}(1);
            cla(ax, 'reset');
            hold(ax, 'on');
            plot(ax, x, p.N ./ Sx / 1e6, '-', 'LineWidth', 2, 'DisplayName', '$\sigma_{xx}(x) = N/S(x)$');
            plot(ax, x, p.Kt * p.N ./ Sx / 1e6, '--', 'LineWidth', 1.5, 'DisplayName', '$K_t\,\sigma_{xx}(x)$');
            plot(ax, [0 p.L0], sign(p.N + (p.N == 0)) * r.sigmaAdm / 1e6 * [1 1], ':', 'LineWidth', 1.5, ...
                'DisplayName', '$\pm R_e/s$');
            hold(ax, 'off');
            grid(ax, 'on');
            xlabel(ax, '$x$ (m)', 'Interpreter', 'latex');
            ylabel(ax, '$\sigma_{xx}$ (MPa)', 'Interpreter', 'latex');
            title(ax, 'Contrainte normale le long de la barre');
            legend(ax, 'Interpreter', 'latex', 'Location', 'best');
            ax2 = W.Axes{2}(1);
            cla(ax2, 'reset');
            vals = [r.dL.analytique r.dL.integrale r.dL.energetique] * 1e3;
            bar(ax2, 1:3, vals, 0.5);
            ax2.XTick = 1:3;
            ax2.XTickLabel = {'Analytique', 'Intégrale', 'Énergétique'};
            ylabel(ax2, '$\Delta L$ (mm)', 'Interpreter', 'latex');
            title(ax2, 'Allongement : 3 méthodes');
            grid(ax2, 'on');
            for k = 1:3
                text(ax2, k, vals(k), sprintf('%.5g', vals(k)), 'HorizontalAlignment', 'center', ...
                    'VerticalAlignment', 'bottom');
            end
            app.finishWork(W);
            W.Tables.Syn.Data = app.kvTable({
                'σ nominale = N/S0', r.sigmaNom / 1e6, 'MPa'
                'σ max = Kt·σ', r.sigmaMax / 1e6, 'MPa'
                'σadm = Re/s', r.sigmaAdm / 1e6, 'MPa'
                'Résistance', r.okResistance, ''
                'εxx', r.epsxx * 1e6, 'µdéf'
                'εyy = εzz', r.epsyy * 1e6, 'µdéf'
                'ΔV/V0', r.dVsurV, '-'
                'ΔL analytique', r.dL.analytique * 1e3, 'mm'
                'ΔL intégrale', r.dL.integrale * 1e3, 'mm'
                'ΔL énergétique (Castigliano)', r.dL.energetique * 1e3, 'mm'
                'Raideur K = E S0/L0', r.K / 1e6, 'kN/mm'
                'Énergie U', r.U, 'J'
                'Rigidité (ΔL ≤ ΔLmax)', r.okRigidite, ''});
            app.setReport(W, {sprintf('σmax = %.5g MPa (%s) ; ΔL = %.5g mm (analytique) / %.5g mm (intégrale) / %.5g mm (énergétique)', ...
                r.sigmaMax / 1e6, MecaStruct_App.okText(r.okResistance), vals(1), vals(2), vals(3))}, ...
                '=== Démarche (moteur, SI) ===', r.report);
            W.Status.Text = sprintf('σmax = %.4g MPa (%s) — ΔL = %.4g mm', r.sigmaMax / 1e6, ...
                MecaStruct_App.okText(r.okResistance), vals(2));
            app.Results.traction = r;
        end

        function computeShear(app)
            %COMPUTESHEAR Cisaillement simple, répartition de Jourawski (section de l'onglet
            %   Sections) et matage simple P = F/S.
            C = app.H.Cis;
            W = C.W;
            p = app.shearBase();
            p.T = app.si(C.T, 'kN');
            p.S = app.si(C.S, 'mm^2');
            p.k = C.k.Value;
            p.G = app.si(C.G, 'GPa');
            r = SolicitationsEngine.shear(p);
            sec = app.buildSection();
            P = GeometryEngine.analytical(sec);
            jour = SolicitationsEngine.jourawski(sec, p.T);
            b = SolicitationsEngine.bearing(struct('F', app.si(C.Fm, 'kN'), 'Smatee', app.si(C.Sm, 'mm^2'), ...
                'Padm', app.si(C.Padm, 'MPa')));
            PlotEngine.section(W.Axes{1}(1), sec, P);
            PlotEngine.sectionStress([], W.Axes{2}(1), sec, P, [], jour);
            MecaStruct_App.plotRatios(W.Axes{3}(1), {'τmax/τadm', 'τJourawski/τadm', 'P/Padm'}, ...
                [abs(r.tauMax) / r.tauAdm, abs(jour.tauMax) / r.tauAdm, abs(b.P) / app.si(C.Padm, 'MPa')], ...
                'Taux d''utilisation (cisaillement et matage)');
            app.finishWork(W);
            W.Tables.Syn.Data = app.kvTable({
                'τmoy = T/S', r.tauMoy / 1e6, 'MPa'
                'τmax = k·T/S', r.tauMax / 1e6, 'MPa'
                'τe', r.tauE / 1e6, 'MPa'
                'τadm = τe/s', r.tauAdm / 1e6, 'MPa'
                'Cisaillement', r.ok, ''
                'Glissement γ', r.gamma * 1e3, 'mrad'
                'Jourawski : τmax (section de l''onglet Sections)', jour.tauMax / 1e6, 'MPa'
                'Jourawski : k = τmax·S/T', jour.kNum, '-'
                'Matage : P = F/S', b.P / 1e6, 'MPa'
                'Matage', b.ok, ''
                'Surface matée minimale', b.SminRequired * 1e6, 'mm²'});
            app.setReport(W, {sprintf('τmax = %.5g MPa ≤ τadm = %.5g MPa : %s ; matage P = %.5g MPa : %s', ...
                r.tauMax / 1e6, r.tauAdm / 1e6, MecaStruct_App.okText(r.ok), b.P / 1e6, MecaStruct_App.okText(b.ok))}, ...
                '=== Cisaillement simple ===', r.report, '=== Jourawski ===', jour.report, '=== Matage ===', b.report);
            W.Status.Text = sprintf('τmax = %.4g MPa (%s) — P = %.4g MPa (%s)', r.tauMax / 1e6, ...
                MecaStruct_App.okText(r.ok), b.P / 1e6, MecaStruct_App.okText(b.ok));
            app.Results.shear = struct('shear', r, 'jour', jour, 'bearing', b);
        end

        function computeKey(app)
            %COMPUTEKEY Clavette parallèle : matage P = 4C/(D b L) et cisaillement τ = 2C/(a L D).
            C = app.H.Cis;
            W = C.W;
            p = app.shearBase();
            p.C = app.si(C.C, 'kN.m');
            p.D = app.si(C.Dk, 'mm');
            p.a = app.si(C.ak, 'mm');
            p.b = app.si(C.bk, 'mm');
            p.Padm = app.si(C.Padm, 'MPa');
            if C.Lk.Value > 0
                p.L = app.si(C.Lk, 'mm');
            end
            r = SolicitationsEngine.keyDesign(p);
            rows = {
                'Effort tangentiel F = 2C/D', r.F / 1e3, 'kN'
                'L min (matage)', r.LminMatage * 1e3, 'mm'
                'L min (cisaillement)', r.LminCis * 1e3, 'mm'
                'L min retenue', r.Lmin * 1e3, 'mm'
                'τadm', r.tauAdm / 1e6, 'MPa'};
            if isfield(r, 'P')
                rows = [rows; {
                    'P = 4C/(D b L)', r.P / 1e6, 'MPa'
                    'Matage', r.okP, ''
                    'τ = 2C/(a L D)', r.tau / 1e6, 'MPa'
                    'Cisaillement', r.okTau, ''}];
                MecaStruct_App.plotRatios(W.Axes{3}(1), {'P/Padm', 'τ/τadm'}, [r.P / p.Padm, r.tau / r.tauAdm], ...
                    'Clavette : taux d''utilisation');
                head = sprintf('Clavette L = %.4g mm : P = %.5g MPa (%s), τ = %.5g MPa (%s) ; Lmin = %.4g mm', ...
                    p.L * 1e3, r.P / 1e6, MecaStruct_App.okText(r.okP), r.tau / 1e6, MecaStruct_App.okText(r.okTau), r.Lmin * 1e3);
            else
                MecaStruct_App.plotRatios(W.Axes{3}(1), {'Lmin matage', 'Lmin cisaillement'}, ...
                    [r.LminMatage r.LminCis] * 1e3, 'Clavette : longueurs minimales (mm)');
                head = sprintf('Clavette : longueur minimale Lmin = %.4g mm', r.Lmin * 1e3);
            end
            app.finishWork(W);
            W.Tables.Syn.Data = app.kvTable(rows);
            app.setReport(W, {head}, '=== Clavette parallèle (moteur, SI) ===', r.report);
            W.Status.Text = head;
            app.Results.key = r;
        end

        function computePin(app)
            %COMPUTEPIN Goupille / rivet : P = 2F/(d e) ≤ Padm et τ = 4F/(n π d²) ≤ τadm.
            C = app.H.Cis;
            W = C.W;
            p = app.shearBase();
            p.F = app.si(C.Fp, 'kN');
            p.d = app.si(C.dp, 'mm');
            p.e = app.si(C.ep, 'mm');
            p.Padm = app.si(C.Padm, 'MPa');
            p.nShear = C.np.Value;
            r = SolicitationsEngine.pinDesign(p);
            MecaStruct_App.plotRatios(W.Axes{3}(1), {'P/Padm', 'τ/τadm'}, [r.P / p.Padm, r.tau / r.tauAdm], ...
                'Goupille : taux d''utilisation');
            app.finishWork(W);
            W.Tables.Syn.Data = app.kvTable({
                'P = 2F/(d e)', r.P / 1e6, 'MPa'
                'Matage', r.okP, ''
                'τ = 4F/(n π d²)', r.tau / 1e6, 'MPa'
                'τadm', r.tauAdm / 1e6, 'MPa'
                'Cisaillement', r.okTau, ''
                'd minimal', r.dMin * 1e3, 'mm'
                'e minimale', r.eMin * 1e3, 'mm'});
            head = sprintf('Goupille : P = %.5g MPa (%s), τ = %.5g MPa (%s)', r.P / 1e6, ...
                MecaStruct_App.okText(r.okP), r.tau / 1e6, MecaStruct_App.okText(r.okTau));
            app.setReport(W, {head}, '=== Goupille / rivet (moteur, SI) ===', r.report);
            W.Status.Text = head;
            app.Results.pin = r;
        end

        function computeTorsion(app)
            %COMPUTETORSION Torsion d'un arbre circulaire plein ou creux (3 méthodes pour φ).
            T = app.H.Tor;
            W = T.W;
            p = struct('Mt', app.si(T.Mt, 'kN.m'), 'D', app.si(T.D, 'mm'), 'd', app.si(T.d, 'mm'), ...
                'G', app.si(T.G, 'GPa'), 'L', T.L.Value, 'Kt', T.Kt.Value, 'Re', app.si(T.Re, 'MPa'), ...
                'criterion', T.crit.Value, 's', T.s.Value);
            if T.thetaAdm.Value > 0
                p.thetaAdm = app.si(T.thetaAdm, 'deg/m');
            end
            r = SolicitationsEngine.torsion(p);
            ax = W.Axes{1}(1);
            cla(ax, 'reset');
            hold(ax, 'on');
            rr = r.rProfile * 1e3;
            tt = r.tauProfile / 1e6;
            plot(ax, rr, tt, '-', 'LineWidth', 2, 'Color', [0 0.45 0.74], 'DisplayName', '$\tau(r) = M_t\,r/I_x$');
            plot(ax, -rr, -tt, '-', 'LineWidth', 2, 'Color', [0 0.45 0.74], 'HandleVisibility', 'off');
            plot(ax, [-1 1] * p.D / 2 * 1e3, [-1 1] * r.tauMax / 1e6, 'o', 'MarkerFaceColor', [0.85 0.33 0.1], ...
                'DisplayName', '$K_t\,\tau_{max}$');
            plot(ax, [-1 1] * p.D / 2 * 1e3, r.tauAdm / 1e6 * [1 1], ':', 'LineWidth', 1.5, 'DisplayName', '$\tau_{adm}$');
            hold(ax, 'off');
            grid(ax, 'on');
            xlabel(ax, '$r$ (mm)', 'Interpreter', 'latex');
            ylabel(ax, '$\tau$ (MPa)', 'Interpreter', 'latex');
            title(ax, 'Répartition de la contrainte de torsion sur un diamètre');
            legend(ax, 'Interpreter', 'latex', 'Location', 'best');
            ax2 = W.Axes{2}(1);
            cla(ax2, 'reset');
            s = linspace(0, p.L, 101);
            plot(ax2, s, r.theta * s * 1e3, '-', 'LineWidth', 2);
            grid(ax2, 'on');
            xlabel(ax2, '$s$ (m)', 'Interpreter', 'latex');
            ylabel(ax2, '$\varphi$ (mrad)', 'Interpreter', 'latex');
            title(ax2, sprintf('Rotation des sections : φ(L) = %.4g mrad = %.4g°', r.phi.analytique * 1e3, rad2deg(r.phi.analytique)));
            app.finishWork(W);
            W.Tables.Syn.Data = app.kvTable({
                'Ix = π(D⁴ − d⁴)/32', r.Ix * 1e12, 'mm⁴'
                'τmax nominale', r.tauMaxNom / 1e6, 'MPa'
                'τmax = Kt·τ', r.tauMax / 1e6, 'MPa'
                'τadm', r.tauAdm / 1e6, 'MPa'
                'Résistance', r.okResistance, ''
                'θ = Mt/(G Ix)', rad2deg(r.theta), '°/m'
                'Rigidité', r.okRigidite, ''
                'φ analytique', r.phi.analytique * 1e3, 'mrad'
                'φ intégrale', r.phi.integrale * 1e3, 'mrad'
                'φ énergétique', r.phi.energetique * 1e3, 'mrad'
                'Raideur K = G Ix/L', r.Ktorsion / 1e3, 'kN·m/rad'
                'Énergie U', r.U, 'J'});
            head = sprintf('τmax = %.5g MPa (%s) ; θ = %.4g °/m (%s) ; φ = %.5g mrad', r.tauMax / 1e6, ...
                MecaStruct_App.okText(r.okResistance), rad2deg(r.theta), MecaStruct_App.okText(r.okRigidite), r.phi.analytique * 1e3);
            app.setReport(W, {head}, '=== Démarche (moteur, SI) ===', r.report);
            W.Status.Text = head;
            app.Results.torsion = r;
        end

        function computeBending(app)
            %COMPUTEBENDING Contraintes normales de flexion composée/déviée dans la section de
            %   l'onglet Sections, axe neutre et profil σxx(y).
            F = app.H.Fle;
            W = F.W;
            sec = app.buildSection();
            P = GeometryEngine.analytical(sec);
            bend = SolicitationsEngine.bendingStress(MecaStruct_App.stressGeometry(sec, struct('N', app.si(F.N, 'kN'), ...
                'Mfz', app.si(F.Mfz, 'kN.m'), 'Mfy', app.si(F.Mfy, 'kN.m'), 'Kt', F.Kt.Value, ...
                'Re', app.si(F.Re, 'MPa'), 's', F.s.Value)));
            ax = W.Axes{1}(1);
            PlotEngine.section(ax, sec, P);
            hold(ax, 'on');
            pts = bend.neutralAxis.points;
            if all(isfinite(pts(:)))
                plot(ax, (P.zG + pts(:, 2)) * 1e3, (P.yG + pts(:, 1)) * 1e3, '--', 'Color', [0.85 0.1 0.1], ...
                    'LineWidth', 1.8, 'DisplayName', 'Axe neutre');
            end
            lt = bend.locMaxTraction;
            lc = bend.locMaxCompression;
            plot(ax, (P.zG + lt(2)) * 1e3, (P.yG + lt(1)) * 1e3, '^', 'MarkerSize', 9, 'MarkerFaceColor', [0.85 0.1 0.1], ...
                'Color', [0.85 0.1 0.1], 'DisplayName', '$\sigma_{max}$ traction');
            plot(ax, (P.zG + lc(2)) * 1e3, (P.yG + lc(1)) * 1e3, 'v', 'MarkerSize', 9, 'MarkerFaceColor', [0 0.45 0.74], ...
                'Color', [0 0.45 0.74], 'DisplayName', '$\sigma_{max}$ compression');
            hold(ax, 'off');
            PlotEngine.sectionStress(W.Axes{2}(1), [], sec, P, bend, []);
            app.finishWork(W);
            W.Tables.Syn.Data = app.kvTable({
                'σ traction max', bend.sigmaMaxTraction / 1e6, 'MPa'
                'σ compression max', bend.sigmaMaxCompression / 1e6, 'MPa'
                '|σ|max', bend.sigmaMaxAbs / 1e6, 'MPa'
                'Kt·|σ|max', bend.sigmaMaxKt / 1e6, 'MPa'
                'σadm = Re/s', bend.sigmaAdm / 1e6, 'MPa'
                'Résistance', bend.ok, ''
                'Formule générale (Iyz ≠ 0)', bend.usedGeneralFormula, ''});
            head = sprintf('σ = %.5g / %.5g MPa ; Kt·|σ|max = %.5g MPa ≤ %.5g MPa : %s', bend.sigmaMaxTraction / 1e6, ...
                bend.sigmaMaxCompression / 1e6, bend.sigmaMaxKt / 1e6, bend.sigmaAdm / 1e6, MecaStruct_App.okText(bend.ok));
            app.setReport(W, {head; sprintf('Section : %s', MecaStruct_App.sectionLabel(sec)); ...
                MecaStruct_App.effortReading(F.N.Value, F.Mfz.Value, F.Mfy.Value)}, ...
                '=== Démarche (moteur, SI) ===', bend.report);
            W.Status.Text = head;
            app.Results.bending = struct('sec', sec, 'P', P, 'bend', bend);
        end

        function computeBuckling(app)
            %COMPUTEBUCKLING Flambage : arbre de décision (compression, Rankine, Euler), courbe de
            %   stabilité et mode propre.
            F = app.H.Fla;
            W = F.W;
            p = struct('E', app.si(F.E, 'GPa'), 'Re', app.si(F.Re, 'MPa'), 'S', app.si(F.S, 'mm^2'), ...
                'Iz', app.si(F.Iz, 'mm^4'), 'Iy', app.si(F.Iy, 'mm^4'), 'L', F.L.Value, ...
                'condition', F.cond.Value, 's', F.s.Value);
            if F.P.Value ~= 0   % P < 0 (convention N < 0 en compression) : le moteur retient |P|
                p.P = app.si(F.P, 'kN');
            end
            b = BucklingEngine.analyze(p);
            c = BucklingEngine.stabilityCurve(p.E, p.Re, 0:0.5:max(300, ceil(1.2 * b.lambda)));
            PlotEngine.bucklingCurve(W.Axes{1}(1), c, b);
            ax = W.Axes{2}(1);
            cla(ax, 'reset');
            s = linspace(0, p.L, 301);
            plot(ax, s, b.modeShape(s), '-', 'LineWidth', 2);
            grid(ax, 'on');
            xlabel(ax, '$s$ (m)', 'Interpreter', 'latex');
            ylabel(ax, '$v(s)/v_{max}$', 'Interpreter', 'latex');
            title(ax, sprintf('Mode propre (%s, L'' = %.4g m)', b.conditionText, b.Lp));
            app.finishWork(W);
            rows = {
                'Imin', b.Imin * 1e12, 'mm⁴'
                'Axe de flambement', b.axis, ''
                'rmin', b.rmin * 1e3, 'mm'
                'Longueur de flambage L''', b.Lp, 'm'
                'Élancement λ', b.lambda, '-'
                'λlim = π√(E/Re)', b.lambdaLim, '-'
                'Régime', b.regime, ''
                'PC = Re·S', b.PC / 1e3, 'kN'
                'PE (Euler)', b.PE / 1e3, 'kN'
                'PR (Rankine)', b.PR / 1e3, 'kN'
                'Pcrit retenue', b.Pcrit / 1e3, 'kN'
                'Padm = Pcrit/s', b.Padm / 1e3, 'kN'};
            if isfinite(b.P)
                rows = [rows; {'P appliquée', b.P / 1e3, 'kN'; 'σ appliquée', b.sigmaApplied / 1e6, 'MPa'; ...
                    'Stabilité (P ≤ Padm)', logical(b.ok), ''}];
            end
            W.Tables.Syn.Data = app.kvTable(rows);
            head = sprintf('λ = %.4g (λlim = %.4g) : régime %s — Pcrit = %.5g kN, Padm = %.5g kN', b.lambda, ...
                b.lambdaLim, b.regime, b.Pcrit / 1e3, b.Padm / 1e3);
            if isfinite(b.P)
                head = sprintf('%s — P = %.5g kN : %s', head, b.P / 1e3, MecaStruct_App.okText(logical(b.ok)));
            end
            app.setReport(W, {head}, '=== Démarche (moteur, SI) ===', b.report, '=== Courbe de stabilité ===', c.report);
            W.Status.Text = head;
            app.Results.buckling = struct('analysis', b, 'curve', c);
        end

        function computeTensor(app)
            %COMPUTETENSOR Tenseur des contraintes : principales, facette, Mohr 2D et 3D, critères
            %   (Tresca, Von Mises, contrainte normale maximale) et lieu de plasticité.
            T = app.H.Ten;
            W = T.W;
            sig = double(T.sig.Data);
            if ~isequal(size(sig), [3 3]) || any(~isfinite(sig(:)))
                error('MecaStruct:App:invalidTensor', 'Le tenseur doit être une matrice 3×3 de réels finis (MPa).');
            end
            sig = DataManager.toSI((sig + sig.') / 2, 'MPa');
            if strcmp(T.fmode.Value, 'theta')
                th = app.si(T.theta, 'deg');
                n = [cos(th) sin(th) 0];
            else
                n = [T.nx.Value T.ny.Value T.nz.Value];
                if norm(n) == 0
                    error('MecaStruct:App:invalidNormal', 'La normale n ne doit pas être nulle.');
                end
                th = atan2(n(2), n(1));
            end
            Re = app.si(T.Re, 'MPa');
            Rm = app.si(T.Rm, 'MPa');
            if ~(Rm > 0)
                Rm = NaN;   % Rm absent : le moteur prend alors Re, aucun autre résultat n'en dépend
            end
            sf = T.s.Value;
            pr = TensorAndCriteriaEngine.principal(sig);
            fa = TensorAndCriteriaEngine.facet(sig, n);
            r2 = TensorAndCriteriaEngine.plane2D(sig(1, 1), sig(2, 2), sig(1, 2), th);
            p3 = [pr.sigmaI pr.sigmaII pr.sigmaIII];
            m3 = TensorAndCriteriaEngine.mohr3D(p3);
            cr = TensorAndCriteriaEngine.criteria(p3, Re, sf, Rm);
            lo = TensorAndCriteriaEngine.yieldLoci(Re, sf, Rm);
            isPlane = all(abs(sig(3, :)) <= 1e-12 * max(1, max(abs(sig(:)))));
            if isPlane
                pt = [r2.sigma1 r2.sigma2];
                ptTxt = 'état plan : (σ1, σ2) du plan (x, y)';
            else
                % Tresca et Von Mises ignorent la pression hydrostatique : on retire σII
                pt = [pr.sigmaI - pr.sigmaII, pr.sigmaIII - pr.sigmaII];
                ptTxt = 'état triaxial : point (σI − σII, σIII − σII), même σeq Tresca et Von Mises (pas Rankine)';
            end
            PlotEngine.mohr3D(W.Axes{1}(1), m3, [fa.sigmaN fa.tauNorm]);
            PlotEngine.mohr2D(W.Axes{2}(1), r2, th);
            PlotEngine.yieldLocus(W.Axes{3}(1), lo, pt);
            app.finishWork(W);
            dirs = pr.directions;
            W.Tables.Princ.Data = table(["σI"; "σII"; "σIII"], p3(:) / 1e6, dirs(1, :).', dirs(2, :).', dirs(3, :).', ...
                'VariableNames', {'Contrainte', 'Valeur (MPa)', 'nx', 'ny', 'nz'});
            W.Tables.Crit.Data = table(["Tresca"; "Von Mises"; "Contrainte normale max"], ...
                [cr.sigmaEqTresca; cr.sigmaEqVM; cr.sigmaMaxNormal] / 1e6, ...
                [cr.sigmaAdm; cr.sigmaAdm; cr.sigmaRAdm] / 1e6, [cr.sfTresca; cr.sfVM; cr.sfRankine], ...
                [string(MecaStruct_App.okText(cr.okTresca)); string(MecaStruct_App.okText(cr.okVM)); ...
                string(MecaStruct_App.okText(cr.okRankine))], ...
                'VariableNames', {'Critère', 'σ équivalente (MPa)', 'σ admissible (MPa)', 'Coefficient obtenu', 'Vérification'});
            fn = fa.n(:).';
            W.Tables.Facet.Data = app.kvTable({
                'Normale n', sprintf('(%.4g ; %.4g ; %.4g)', fn), ''
                'Cn = σ·n', sprintf('(%.5g ; %.5g ; %.5g)', fa.Cn / 1e6), 'MPa'
                'σn = Cn·n', fa.sigmaN / 1e6, 'MPa'
                '|τ|', fa.tauNorm / 1e6, 'MPa'
                'σ(θ) plan (x,y)', r2.sigma / 1e6, 'MPa'
                'τ(θ) plan (x,y)', r2.tau / 1e6, 'MPa'
                'θ', rad2deg(th), '°'});
            head = sprintf('σI = %.5g, σII = %.5g, σIII = %.5g MPa ; Tresca %.5g MPa, Von Mises %.5g MPa (σadm = %.5g MPa) : %s / %s', ...
                p3 / 1e6, cr.sigmaEqTresca / 1e6, cr.sigmaEqVM / 1e6, cr.sigmaAdm / 1e6, ...
                MecaStruct_App.okText(cr.okTresca), MecaStruct_App.okText(cr.okVM));
            app.setReport(W, {head; ['Lieu de plasticité : ' ptTxt]}, '=== Contraintes principales ===', pr.report, ...
                '=== Facette ===', fa.report, '=== Mohr plan (x, y) ===', r2.report, '=== Critères ===', cr.report);
            W.Status.Text = sprintf('σI = %.4g MPa, σIII = %.4g MPa — VM = %.4g MPa (%s)', p3(1) / 1e6, p3(3) / 1e6, ...
                cr.sigmaEqVM / 1e6, MecaStruct_App.okText(cr.okVM));
            app.Results.tensor = struct('principal', pr, 'facet', fa, 'plane2D', r2, 'mohr3D', m3, 'criteria', cr, 'loci', lo);
        end

        function computeHooke(app)
            %COMPUTEHOOKE Loi de Hooke : 3D isotrope, contraintes planes, déformations planes ou
            %   orthotrope ; cercle de Mohr des déformations dans le plan (x, y).
            K = app.H.Hoo;
            W = K.W;
            E = app.si(K.E, 'GPa');
            nu = K.nu.Value;
            sigV = DataManager.toSI([K.sxx.Value; K.syy.Value; K.szz.Value; K.syz.Value; K.sxz.Value; K.sxy.Value], 'MPa');
            voigt = {'xx', 'yy', 'zz', 'yz', 'xz', 'xy'};
            switch K.mode.Value
                case 'iso3D'
                    e = TensorAndCriteriaEngine.hooke3D(sigV, E, nu, app.si(K.alpha, '1e-6/°C'), K.dT.Value);
                    Cm = TensorAndCriteriaEngine.stiffnessIsotropic(E, nu);
                    W.Tables.Res.Data = table(["εxx"; "εyy"; "εzz"; "γyz"; "γxz"; "γxy"], e(:) * 1e6, ...
                        'VariableNames', {'Déformation', 'Valeur (µdéf)'});
                    app.setMatrix(W.Tables.Mat, Cm / 1e9, voigt, voigt);
                    exx = e(1); eyy = e(2); exy = e(6) / 2;
                    rep = {'Loi de Hooke 3D isotrope : {ε} = [S]{σ} + αΔT{1 1 1 0 0 0} (glissements ingénieur).'
                        sprintf('εxx = %.5g, εyy = %.5g, εzz = %.5g µdéf ; γyz = %.5g, γxz = %.5g, γxy = %.5g µdéf', e * 1e6)
                        'Table « Matrice » : rigidité [C] en GPa (notation de Voigt).'};
                case 'planeStress'
                    r = TensorAndCriteriaEngine.planeStress(sigV(1), sigV(2), sigV(6), E, nu);
                    W.Tables.Res.Data = table(["εxx"; "εyy"; "εzz"; "γxy"], [r.exx; r.eyy; r.ezz; r.gxy] * 1e6, ...
                        'VariableNames', {'Déformation', 'Valeur (µdéf)'});
                    app.setMatrix(W.Tables.Mat, r.Qred / 1e9, {'xx', 'yy', 'xy'}, {'xx', 'yy', 'xy'});
                    exx = r.exx; eyy = r.eyy; exy = r.gxy / 2;
                    rep = [{'Contraintes planes (σzz = σxz = σyz = 0) ; table « Matrice » : [Q] réduite en GPa.'}; r.report];
                case 'planeStrain'
                    exx = K.exx.Value * 1e-6; eyy = K.eyy.Value * 1e-6; gxy = K.gxy.Value * 1e-6;
                    r = TensorAndCriteriaEngine.planeStrain(exx, eyy, gxy, E, nu);
                    W.Tables.Res.Data = table(["σxx"; "σyy"; "σxy"; "σzz"], [r.sxx; r.syy; r.sxy; r.szz] / 1e6, ...
                        'VariableNames', {'Contrainte', 'Valeur (MPa)'});
                    app.setMatrix(W.Tables.Mat, r.Cred / 1e9, {'xx', 'yy', 'xy'}, {'xx', 'yy', 'xy'});
                    exy = gxy / 2;
                    rep = [{'Déformations planes (εzz = 0 ⇒ σzz = ν(σxx + σyy)) ; table « Matrice » : [C] réduite en GPa.'}; r.report];
                case 'ortho'
                    c = struct('E1', app.si(K.E1, 'GPa'), 'E2', app.si(K.E2, 'GPa'), 'E3', app.si(K.E3, 'GPa'), ...
                        'nu12', K.nu12.Value, 'nu13', K.nu13.Value, 'nu23', K.nu23.Value, ...
                        'G12', app.si(K.G12, 'GPa'), 'G13', app.si(K.G13, 'GPa'), 'G23', app.si(K.G23, 'GPa'));
                    Sm = TensorAndCriteriaEngine.complianceOrthotropic(c);
                    Cm = TensorAndCriteriaEngine.stiffnessOrthotropic(c);
                    e = Sm * sigV;
                    W.Tables.Res.Data = table(["ε11"; "ε22"; "ε33"; "γ23"; "γ13"; "γ12"], e(:) * 1e6, ...
                        'VariableNames', {'Déformation', 'Valeur (µdéf)'});
                    app.setMatrix(W.Tables.Mat, Cm / 1e9, voigt, voigt);
                    exx = e(1); eyy = e(2); exy = e(6) / 2;
                    rep = {'Matériau orthotrope (9 constantes) : {ε} = [S]{σ}, axes d''orthotropie 1, 2, 3 = x, y, z.'
                        sprintf('ε11 = %.5g, ε22 = %.5g, ε33 = %.5g µdéf ; γ23 = %.5g, γ13 = %.5g, γ12 = %.5g µdéf', e * 1e6)
                        'Table « Matrice » : rigidité [C] en GPa (symétrique, définie positive).'};
                otherwise
                    error('MecaStruct:App:invalidMode', 'Mode de loi de Hooke inconnu.');
            end
            r2 = TensorAndCriteriaEngine.plane2DStrain(exx, eyy, exy, 0);
            PlotEngine.mohr2D(W.Axes{1}(1), r2);
            app.finishWork(W);
            app.setReport(W, rep, '=== Mohr des déformations (plan x, y) ===', r2.report);
            W.Status.Text = sprintf('ε1 = %.5g µdéf, ε2 = %.5g µdéf', r2.sigma1 * 1e6, r2.sigma2 * 1e6);
            app.Results.hooke = struct('mode', K.mode.Value, 'exx', exx, 'eyy', eyy, 'exy', exy, 'mohr', r2);
        end

        function computeGauges(app)
            %COMPUTEGAUGES Extensométrie : jauge (Bridgman), pont de Wheatstone et rosette 45°/60°.
            J = app.H.Jau;
            W = J.W;
            g = TensorAndCriteriaEngine.gauge(J.K.Value, J.eps.Value * 1e-6, J.R0.Value);
            e4 = [J.e1.Value J.e2.Value J.e3.Value J.e4.Value] * 1e-6;
            switch J.cfg.Value
                case 'quart'
                    ev = e4(1);
                case 'demi'
                    ev = e4(1:2);
                otherwise
                    ev = e4;
            end
            w = TensorAndCriteriaEngine.wheatstone(J.cfg.Value, J.K.Value, J.Vin.Value, ev);
            eb = TensorAndCriteriaEngine.bridgeStrain(J.cfg.Value, J.K.Value, J.Vin.Value, J.Vout.Value * 1e-3);
            rd = [J.ra.Value J.rb.Value J.rc.Value] * 1e-6;
            E = app.si(J.E, 'GPa');
            if strcmp(J.rtype.Value, '60')
                ro = TensorAndCriteriaEngine.rosette60(rd(1), rd(2), rd(3), E, J.nu.Value);
            else
                ro = TensorAndCriteriaEngine.rosette45(rd(1), rd(2), rd(3), E, J.nu.Value);
            end
            r2e = TensorAndCriteriaEngine.plane2DStrain(ro.exx, ro.eyy, ro.exy, 0);
            r2s = TensorAndCriteriaEngine.plane2D(ro.sxx, ro.syy, ro.sxy, 0);
            PlotEngine.mohr2D(W.Axes{1}(1), r2e);
            PlotEngine.mohr2D(W.Axes{2}(1), r2s);
            app.finishWork(W);
            W.Tables.Ros.Data = app.kvTable({
                'εxx', ro.exx * 1e6, 'µdéf'
                'εyy', ro.eyy * 1e6, 'µdéf'
                'γxy', ro.gxy * 1e6, 'µdéf'
                'εI', ro.epsI * 1e6, 'µdéf'
                'εII', ro.epsII * 1e6, 'µdéf'
                'θP (direction de εI)', rad2deg(ro.thetaP), '°'
                'σxx', ro.sxx / 1e6, 'MPa'
                'σyy', ro.syy / 1e6, 'MPa'
                'σxy', ro.sxy / 1e6, 'MPa'
                'σI', ro.sigmaI / 1e6, 'MPa'
                'σII', ro.sigmaII / 1e6, 'MPa'
                'σ Von Mises', ro.sigmaVM / 1e6, 'MPa'
                'σ Tresca', ro.sigmaTresca / 1e6, 'MPa'});
            W.Tables.Bridge.Data = app.kvTable({
                'Jauge : ΔR/R = K·ε', g.dRsurR, '-'
                'Jauge : ΔR', g.dR, 'Ω'
                'Pont : Vout linéarisée', w.Vout * 1e3, 'mV'
                'Pont : Vout exacte', w.VoutExact * 1e3, 'mV'
                'Pont : erreur de linéarité', w.linearityError * 100, '%'
                'Pont : ε déduite de Vout mesurée', eb * 1e6, 'µdéf'});
            head = sprintf('Rosette : εI = %.5g, εII = %.5g µdéf ; σI = %.5g, σII = %.5g MPa ; pont : Vout = %.5g mV', ...
                ro.epsI * 1e6, ro.epsII * 1e6, ro.sigmaI / 1e6, ro.sigmaII / 1e6, w.Vout * 1e3);
            app.setReport(W, {head; sprintf('Déformation déduite de Vout = %.4g mV : ε = %.5g µdéf', J.Vout.Value, eb * 1e6)}, ...
                '=== Jauge ===', g.report, '=== Pont de Wheatstone ===', w.report, '=== Rosette ===', ro.report);
            W.Status.Text = head;
            app.Results.gauges = struct('gauge', g, 'bridge', w, 'bridgeStrain', eb, 'rosette', ro);
        end

        function computeKt(app)
            %COMPUTEKT Calcule Kt pour l'abaque sélectionné (base de données) et trace l'abaque.
            D = app.H.DB;
            id = D.ktId.Value;
            if strcmp(id, 'plaque_trou_traction')
                prm = D.ktP1.Value;
            else
                prm = [D.ktP1.Value D.ktP2.Value];
            end
            [Kt, info] = DataManager.evalKt(id, prm);
            ax = D.KtAxes;
            PlotEngine.ktChart(ax, id);
            hold(ax, 'on');
            plot(ax, D.ktP1.Value, Kt, 'o', 'MarkerSize', 9, 'MarkerFaceColor', [0.85 0.33 0.1], ...
                'Color', [0.85 0.33 0.1], 'DisplayName', sprintf('$K_t = %.4g$', Kt));
            hold(ax, 'off');
            app.finishAxes(ax);
            D.ktRes.Value = [{sprintf('Kt = %.4g', Kt)}; info.report(:)];
            app.Results.kt = struct('Kt', Kt, 'info', info);
        end

        function loadExample(app, tabName, variant)
            %LOADEXAMPLE Remplit un onglet avec un exemple d'école (sans calculer).
            %   app.loadExample(tabName) ; app.loadExample(tabName, variant)
            %   tabName : 'Base de données', 'Sections', 'Poutres', 'Treillis', 'Traction',
            %   'Cisaillement', 'Torsion', 'Flexion', 'Flambage', 'Tenseurs', 'Hooke', 'Jauges'
            %   (accents et casse ignorés, ou clés internes 'Sec', 'Beam'...).
            %   variant : Poutres 'isostatique' (défaut), 'hyperstatique', 'console', 'deuxtravees' ;
            %   Traction 'variable' (section conique S(x)) ; Hooke 'iso3D' (défaut), 'planeStress',
            %   'planeStrain', 'ortho'.
            if nargin < 3 || isempty(variant)
                variant = '';
            end
            variant = char(variant);
            [~, wk] = MecaStruct_App.resolveName(tabName);
            switch wk
                case 'DB'
                    app.refreshDatabase();
                    D = app.H.DB;
                    D.ktId.Value = 'arbre_epaulement_flexion';
                    D.ktP1.Value = 0.1;
                    D.ktP2.Value = 1.5;
                    app.onKtChartChange(false);
                case 'Sec'
                    S = app.H.Sec;
                    S.type.Value = 'I';
                    vals = struct('b', 100, 'h', 200, 'D', 100, 'd', 80, 'B', 100, 'H', 200, 't', 10, 'tw', 8, 'tf', 12);
                    fn = fieldnames(vals);
                    for k = 1:numel(fn)
                        S.(fn{k}).Value = vals.(fn{k});
                    end
                    S.fam.Value = 'IPE';
                    app.onFamilyChange('Sec');
                    S.prof.Value = app.pickItem(S.prof, 'IPE 200');
                    if GeometryEngine.hasSymbolic()
                        S.mode.Value = 'symbolique';
                    else
                        S.mode.Value = 'numerique';
                    end
                    S.mat.Value = app.pickItem(S.mat, 'S235');
                    S.N.Value = 50; S.Mfz.Value = 20; S.Mfy.Value = 0; S.Ty.Value = 60; S.Kt.Value = 1; S.s0.Value = 3;
                    app.onSectionType();
                case 'Beam'
                    app.loadBeamExample(variant);
                case 'Tr'
                    T = app.H.Tr;
                    T.mat.Value = app.pickItem(T.mat, 'S235');
                    app.applyMaterial('Tr');
                    T.S.Value = 500;
                    T.scale.Value = 0;
                    T.nodes.Data = {'A', 0, 0; 'B', 3, 0; 'C', 6, 0; 'D', 1.5, 2; 'E', 4.5, 2};
                    T.bars.Data = {1, 2; 2, 3; 1, 4; 4, 2; 4, 5; 2, 5; 5, 3};
                    T.sup.Data = {1, true, true; 3, false, true};
                    T.loads.Data = {2, 0, -20; 4, 0, -10; 5, 5, -10};
                case 'Tra'
                    T = app.H.Tra;
                    T.N.Value = 50; T.S0.Value = 314.159; T.L0.Value = 1;
                    T.mat.Value = app.pickItem(T.mat, 'S235');
                    app.applyMaterial('Tra');
                    T.dT.Value = 0; T.Kt.Value = 1; T.s.Value = 1.5; T.dLmax.Value = 0;
                    T.Sexpr.Value = 'pi/4*(20 + 10*x)^2';
                    T.varS.Value = strcmpi(variant, 'variable');
                case 'Cis'
                    C = app.H.Cis;
                    C.T.Value = 10; C.S.Value = 100; C.k.Value = 1.5;
                    C.mat.Value = app.pickItem(C.mat, 'S235');
                    app.applyMaterial('Cis');
                    C.crit.Value = 'Tresca'; C.s.Value = 1.5;
                    C.Fm.Value = 10; C.Sm.Value = 200;
                    app.refreshBearingList();
                    C.PadmSrc.Value = min(2, numel(C.PadmSrc.ItemsData));
                    app.onBearingSelect();
                    C.C.Value = 0.2; C.Dk.Value = 30; C.ak.Value = 10; C.bk.Value = 8; C.Lk.Value = 40;
                    C.Fp.Value = 2; C.dp.Value = 8; C.ep.Value = 12; C.np.Value = 2;
                case 'Tor'
                    T = app.H.Tor;
                    T.Mt.Value = 0.5; T.D.Value = 40; T.d.Value = 0; T.L.Value = 1;
                    T.mat.Value = app.pickItem(T.mat, 'S235');
                    app.applyMaterial('Tor');
                    T.Kt.Value = 1; T.s.Value = 1.5; T.crit.Value = 'Tresca'; T.thetaAdm.Value = 0.25;
                case 'Fle'
                    F = app.H.Fle;
                    F.N.Value = 10; F.Mfz.Value = 15; F.Mfy.Value = 2; F.Kt.Value = 1; F.s0.Value = 3; F.s.Value = 1.5;
                    F.mat.Value = app.pickItem(F.mat, 'S235');
                    app.applyMaterial('Fle');
                case 'Fla'
                    F = app.H.Fla;
                    F.fam.Value = 'HEA';
                    app.onFamilyChange('Fla');
                    F.prof.Value = app.pickItem(F.prof, 'HEA 200');
                    app.loadProfileForBuckling();
                    F.mat.Value = app.pickItem(F.mat, 'S235');
                    app.applyMaterial('Fla');
                    F.L.Value = 4; F.cond.Value = 'articule-articule'; F.P.Value = 300; F.s.Value = 2;
                case 'Ten'
                    T = app.H.Ten;
                    T.sig.Data = [80 30 0; 30 -40 0; 0 0 20];
                    T.fmode.Value = 'theta'; T.theta.Value = 30;
                    T.nx.Value = 1; T.ny.Value = 1; T.nz.Value = 0;
                    T.mat.Value = app.pickItem(T.mat, 'S235');
                    app.applyMaterial('Ten');
                    T.s.Value = 1.5;
                case 'Hoo'
                    K = app.H.Hoo;
                    modes = {'iso3D', 'planeStress', 'planeStrain', 'ortho'};
                    if any(strcmp(variant, modes))
                        K.mode.Value = variant;
                    else
                        K.mode.Value = 'iso3D';
                    end
                    K.mat.Value = app.pickItem(K.mat, 'S235');
                    app.applyMaterial('Hoo');
                    K.dT.Value = 0;
                    K.sxx.Value = 100; K.syy.Value = 50; K.szz.Value = 0; K.syz.Value = 0; K.sxz.Value = 0; K.sxy.Value = 30;
                    K.exx.Value = 500; K.eyy.Value = -150; K.gxy.Value = 200;
                    K.E1.Value = 140; K.E2.Value = 10; K.E3.Value = 10;
                    K.nu12.Value = 0.3; K.nu13.Value = 0.3; K.nu23.Value = 0.4;
                    K.G12.Value = 5; K.G13.Value = 5; K.G23.Value = 3.6;
                    app.onHookeMode();
                case 'Jau'
                    J = app.H.Jau;
                    J.K.Value = 2.1; J.eps.Value = 500; J.R0.Value = 120;
                    J.cfg.Value = 'demi'; J.Vin.Value = 5;
                    J.e1.Value = 500; J.e2.Value = -150; J.e3.Value = 0; J.e4.Value = 0; J.Vout.Value = 1.2;
                    J.rtype.Value = '45'; J.ra.Value = 400; J.rb.Value = -120; J.rc.Value = 250;
                    J.mat.Value = app.pickItem(J.mat, 'S235');
                    app.applyMaterial('Jau');
            end
        end

        function status = runAllExamples(app)
            %RUNALLEXAMPLES Charge un exemple par onglet et calcule tout.
            %   status = app.runAllExamples() renvoie une structure : allOK (logical), ok (structure
            %   de booléens par exemple), messages (structure de textes : 'OK' ou message d'erreur).
            steps = {
                'BaseDeDonnees', 'DB', '', @() app.computeKt()
                'Sections', 'Sec', '', @() app.computeSection()
                'TransfertSection', '', '', @() app.useSectionForBeam()
                'Poutres', 'Beam', 'isostatique', @() app.computeBeam()
                'PoutreHyperstatique', 'Beam', 'hyperstatique', @() app.computeBeam()
                'PoutreConsole', 'Beam', 'console', @() app.computeBeam()
                'PoutreDeuxTravees', 'Beam', 'deuxtravees', @() app.computeBeam()
                'PoutreGerber', 'Beam', 'gerber', @() app.computeBeam()
                'PoutreTassement', 'Beam', 'tassement', @() app.computeBeam()
                'CombinaisonsPoutre', '', '', @() app.computeCombinations()
                'EurocodePoutre', '', '', @() app.checkEurocode()
                'FatiguePoutre', '', '', @() app.checkFatigue()
                'DimensionnementPoutre', '', '', @() app.findLightestProfile(app.H.Beam.pfam.Value, app.H.Beam.pdef.Value)
                'ChargeMobile', '', '', @() app.computeMovingLoad()
                'EnvoiTenseur', '', '', @() app.sendToTensor()
                'Treillis', 'Tr', '', @() app.computeTruss()
                'Traction', 'Tra', '', @() app.computeTraction()
                'TractionSectionVariable', 'Tra', 'variable', @() app.computeTraction()
                'Cisaillement', 'Cis', '', @() app.computeShear()
                'Clavette', 'Cis', '', @() app.computeKey()
                'Goupille', 'Cis', '', @() app.computePin()
                'Torsion', 'Tor', '', @() app.computeTorsion()
                'Flexion', 'Fle', '', @() app.computeBending()
                'Flambage', 'Fla', '', @() app.computeBuckling()
                'Tenseurs', 'Ten', '', @() app.computeTensor()
                'HookeIsotrope3D', 'Hoo', 'iso3D', @() app.computeHooke()
                'HookeContraintesPlanes', 'Hoo', 'planeStress', @() app.computeHooke()
                'HookeDeformationsPlanes', 'Hoo', 'planeStrain', @() app.computeHooke()
                'HookeOrthotrope', 'Hoo', 'ortho', @() app.computeHooke()
                'Jauges', 'Jau', '', @() app.computeGauges()};
            status = struct('allOK', true, 'ok', struct(), 'messages', struct());
            for k = 1:size(steps, 1)
                name = steps{k, 1};
                try
                    if ~isempty(steps{k, 2})
                        app.loadExample(steps{k, 2}, steps{k, 3});
                    end
                    steps{k, 4}();
                    status.ok.(name) = true;
                    status.messages.(name) = 'OK';
                catch err
                    status.ok.(name) = false;
                    status.messages.(name) = err.message;
                    status.allOK = false;
                    app.logError(name, err);
                end
            end
            app.updateFormula();
        end

        function selectTab(app, name, plotIndex)
            %SELECTTAB Sélectionne un onglet (et son sous-onglet) puis met à jour le formulaire.
            %   app.selectTab(name) ; app.selectTab(name, plotIndex) sélectionne aussi l'onglet
            %   graphique n° plotIndex de la zone de travail (ex. 3 = Déformée pour les poutres).
            [tag, wk] = MecaStruct_App.resolveName(name);
            app.TabGroup.SelectedTab = app.Tabs.(tag);
            if strcmp(tag, 'Sol')
                app.SubSol.SelectedTab = app.H.(wk).Tab;
            elseif strcmp(tag, 'Hoo')
                app.SubHooke.SelectedTab = app.H.(wk).Tab;
            end
            if nargin >= 3 && ~isempty(plotIndex) && isfield(app.H, wk) && isfield(app.H.(wk), 'W')
                pg = app.H.(wk).W.PlotGroup;
                app.H.(wk).W.PlotGroup.SelectedTab = pg.Children(plotIndex);
            end
            app.updateFormula();
        end

        function f = openDoc(~, name)
            %OPENDOC Ouvre un document du dossier docs (HTML) dans le navigateur par défaut.
            %   f = app.openDoc('NOTE_DE_CALCUL.html') renvoie le chemin du fichier ouvert.
            f = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'docs', char(name));
            if ~isfile(f)
                error('MecaStruct:App:docMissing', 'Document introuvable : %s', f);
            end
            MecaStruct_App.openInBrowser(f);
        end

        function f = exportValidation(app, key, folder, format)
            %EXPORTVALIDATION Génère le dossier de validation de l'onglet affiché (HTML ou PDF) et l'ouvre.
            %   f = app.exportValidation() utilise l'onglet actif ; app.exportValidation(key) une
            %   zone de travail précise ('Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla',
            %   'Ten', 'Hoo', 'Jau') ; le 3e argument choisit le dossier de sortie, le 4e le format
            %   ('html' ou 'pdf'). Sans format et fenêtre visible, l'application le demande ; sinon HTML.
            %   Le fichier HTML est autonome (images intégrées) : il peut être envoyé tel quel.
            if nargin < 2 || isempty(key)
                key = app.activeWorkKey();
            end
            if any(strcmp(key, {'Home', 'DB', 'Conv'}))
                error('MecaStruct:App:noValidation', 'Pas de dossier de validation pour cet onglet : ouvrir un onglet de calcul.');
            end
            if nargin < 3
                folder = '';
            end
            if nargin < 4 || isempty(format)
                format = 'html';
                if strcmp(app.UIFigure.Visible, 'on')
                    ch = uiconfirm(app.UIFigure, ['Format du dossier de validation :' newline newline ...
                        'HTML : fichier autonome, à ouvrir dans un navigateur.' newline ...
                        'PDF : prêt à remettre (Edge ou Chrome sans fenêtre ; les formules demandent Internet).'], ...
                        'Format du dossier', 'Options', {'HTML', 'PDF', 'Annuler'}, 'DefaultOption', 1, 'CancelOption', 3);
                    if strcmp(ch, 'Annuler')
                        f = '';
                        return
                    end
                    format = lower(ch);
                end
            end
            app.H.(key).W.Status.Text = 'Génération du dossier de validation...';
            drawnow;
            f = ValidationReport.generate(app, key, folder, format);
            app.H.(key).W.Status.Text = ['Dossier de validation : ' f];
            MecaStruct_App.openInBrowser(f);
        end

        function f = saveProblem(app, key, f)
            %SAVEPROBLEM Enregistre la saisie d'un onglet (Beam, Tr...) dans un fichier .mat.
            %   app.saveProblem('Beam', fichier) ; sans fichier, ouvre la boîte « Enregistrer sous ».
            if nargin < 3 || isempty(f)
                [n, p] = uiputfile('*.mat', 'Enregistrer mon problème', ['Probleme_' key '.mat']);
                if isequal(n, 0)
                    f = '';
                    return
                end
                f = fullfile(p, n);
            end
            problem = struct('app', 'MecaStruct', 'key', key, 'values', {app.captureInputs(key)}); %#ok<NASGU>
            save(f, 'problem');
        end

        function n = loadProblem(app, key, f)
            %LOADPROBLEM Recharge un problème enregistré par saveProblem ; renvoie le nombre de champs non restaurés.
            if nargin < 3 || isempty(f)
                [n0, p] = uigetfile('*.mat', 'Ouvrir un problème');
                if isequal(n0, 0)
                    n = 0;
                    return
                end
                f = fullfile(p, n0);
            end
            S = load(f, 'problem');   % une seule variable : un fichier échangé ne charge rien d'autre
            if ~isfield(S, 'problem') || ~strcmp(S.problem.key, key)
                error('MecaStruct:App:badProblemFile', ['Ce fichier n''est pas un problème enregistré depuis cet onglet ' ...
                    '(ou il date d''une autre version de l''application).']);
            end
            n = app.restoreInputs(key, S.problem.values);
            app.H.(key).W.Status.Text = sprintf('Problème ouvert : %s', f);
        end

        function f = saveProject(app, f)
            %SAVEPROJECT Enregistre la saisie de tous les onglets de calcul dans un seul fichier .mat.
            if nargin < 2 || isempty(f)
                [n, p] = uiputfile('*.mat', 'Enregistrer tout le projet', 'Projet_MecaStruct.mat');
                if isequal(n, 0)
                    f = '';
                    return
                end
                f = fullfile(p, n);
            end
            project = struct('app', 'MecaStruct'); %#ok<NASGU>
            for key = MecaStruct_App.projectKeys()
                project.(key{1}) = app.captureInputs(key{1});
            end
            save(f, 'project');
        end

        function failed = loadProject(app, f)
            %LOADPROJECT Recharge un projet enregistré par saveProject ; renvoie les onglets non restaurés (cellstr).
            if nargin < 2 || isempty(f)
                [n0, p] = uigetfile('*.mat', 'Ouvrir un projet');
                if isequal(n0, 0)
                    failed = {};
                    return
                end
                f = fullfile(p, n0);
            end
            S = load(f, 'project');
            if ~isfield(S, 'project') || ~isfield(S.project, 'app')
                error('MecaStruct:App:badProblemFile', 'Ce fichier n''est pas un projet MecaStruct.');
            end
            failed = {};
            for key = MecaStruct_App.projectKeys()
                k = key{1};
                try
                    app.restoreInputs(k, S.project.(k));
                catch
                    failed{end + 1} = k; %#ok<AGROW>
                end
            end
        end

        function files = exportResults(app, key, f)
            %EXPORTRESULTS Écrit les tableaux de résultats d'un onglet : .xlsx (une feuille par tableau) ou .csv (un fichier par tableau).
            %   Poutres : feuilles « Enveloppe » (max/min de chaque effort) et « Efforts » (valeurs le long de la poutre) en plus.
            sheets = app.resultSheets(key);
            if isempty(sheets)
                error('MecaStruct:App:noResults', 'Aucun résultat à exporter : cliquez d''abord sur « Calculer ».');
            end
            [d, base, ext] = fileparts(f);
            files = {};
            if strcmpi(ext, '.csv')
                for k = 1:size(sheets, 1)
                    files{end + 1} = fullfile(d, [base '_' sheets{k, 1} '.csv']); %#ok<AGROW>
                    writetable(sheets{k, 2}, files{end});
                end
            else
                for k = 1:size(sheets, 1)
                    writetable(sheets{k, 2}, f, 'Sheet', sheets{k, 1});
                end
                files = {f};
            end
        end

        function openProjectDialog(app)
            failed = app.loadProject();
            if ~isempty(failed) && strcmp(app.UIFigure.Visible, 'on')
                uialert(app.UIFigure, ['Onglets non restaurés (version différente) : ' strjoin(failed, ', ')], ...
                    'Ouvrir un projet', 'Icon', 'warning');
            end
        end

        function exportResultsDialog(app, key)
            [n, p] = uiputfile({'*.xlsx', 'Excel (une feuille par tableau)'; '*.csv', 'CSV (un fichier par tableau)'}, ...
                'Exporter les tableaux de résultats', ['MecaStruct_' key '.xlsx']);
            if isequal(n, 0)
                return
            end
            files = app.exportResults(key, fullfile(p, n));
            app.H.(key).W.Status.Text = sprintf('Tableaux exportés : %s', strjoin(files, ', '));
        end

        function n = guidedTour(app)
            %GUIDEDTOUR Visite guidée : poutre sur deux appuis, du chargement de l'exemple à la vérification.
            %   Fenêtre masquée : renvoie seulement le nombre d'étapes (sans boîtes de dialogue).
            steps = {
                'Poutres', 'Étape 1/5 : voici une poutre sur deux appuis. Le tableau Appuis donne leur position et leur type (la légende dessous dit ce que chacun bloque).'
                'Poutres', 'Étape 2/5 : les tableaux Forces et Charges réparties donnent le chargement. Une force vers le bas est négative. « Charge rapide » aide à saisir une charge répartie.'
                'Poutres', 'Étape 3/5 : le calcul est lancé pour vous. Regardez le schéma, puis les diagrammes de T et de Mf : le moment est maximal où T change de signe.'
                'Poutres', 'Étape 4/5 : lisez le rapport (en bas). Sa première ligne est le verdict : la poutre résiste-t-elle, avec quelle marge ?'
                'Flambage', 'Étape 5/5 : une poutre comprimée doit aussi être vérifiée au flambage. Chargez un profilé et cliquez sur Calculer. Fin de la visite.'};
            n = size(steps, 1);
            visible = strcmp(app.UIFigure.Visible, 'on');
            if ~visible
                return
            end
            for k = 1:n
                app.selectTab(steps{k, 1});
                if k == 1
                    app.loadExample('Poutres', 'isostatique');
                elseif k == 3
                    app.computeBeam();
                end
                ch = uiconfirm(app.UIFigure, steps{k, 2}, 'Visite guidée', 'Options', {'Suivant', 'Arrêter'}, ...
                    'DefaultOption', 1, 'CancelOption', 2);
                if ~strcmp(ch, 'Suivant')
                    return
                end
            end
        end

        function addQuickLoad(app)
            %ADDQUICKLOAD Ajoute au tableau des charges réparties la charge décrite par « Charge rapide ».
            B = app.H.Beam;
            a = B.qa.Value;
            b = B.qb.Value;
            p1 = B.qp1.Value;
            p2 = B.qp2.Value;
            if b <= a
                error('MecaStruct:App:invalidLoad', 'La charge doit finir après son début (b > a).');
            end
            switch B.qshape.Value
                case 'Uniforme'
                    row = {a, b, B.qdir.Value, 'uniforme', sprintf('%.10g', p1), '', B.qcase.Value};
                case 'Triangulaire croissante (0 → p)'
                    row = {a, b, B.qdir.Value, 'linéaire', sprintf('0 %.10g', p1), '', B.qcase.Value};
                case 'Triangulaire décroissante (p → 0)'
                    row = {a, b, B.qdir.Value, 'linéaire', sprintf('%.10g 0', p1), '', B.qcase.Value};
                otherwise
                    row = {a, b, B.qdir.Value, 'linéaire', sprintf('%.10g %.10g', p1, p2), '', B.qcase.Value};
            end
            app.addTableRow(B.dl, row);
        end

        function pushBeamHistory(app)
            %PUSHBEAMHISTORY Mémorise l'état de la saisie de Poutres (annuler / rétablir) et redessine l'aperçu.
            if app.HistBusy
                return
            end
            snap = struct('vals', {app.captureInputs('Beam')}, 'sec', app.BeamSection, 'use', app.BeamUsesSection, ...
                'info', app.H.Beam.secInfo.Text);
            if app.BeamHistPos >= 1 && isequaln(app.BeamHist{app.BeamHistPos}.vals, snap.vals)
                return
            end
            app.BeamHist = [app.BeamHist(1:app.BeamHistPos), {snap}];
            if numel(app.BeamHist) > 60
                app.BeamHist(1) = [];
            end
            app.BeamHistPos = numel(app.BeamHist);
            app.previewBeam();
        end

        function resetBeamHistory(app)
            % Repart d'un état de référence (après un exemple ou l'ouverture d'un problème).
            app.BeamHist = {};
            app.BeamHistPos = 0;
            app.pushBeamHistory();
        end

        function undoBeam(app, step)
            %UNDOBEAM Annule (step = -1, défaut) ou rétablit (step = +1) la dernière modification de la saisie de Poutres.
            if nargin < 2
                step = -1;
            end
            B = app.H.Beam;
            t = app.BeamHistPos + step;
            if t < 1 || t > numel(app.BeamHist)
                if step < 0
                    B.W.Status.Text = 'Rien à annuler.';
                else
                    B.W.Status.Text = 'Rien à rétablir.';
                end
                return
            end
            snap = app.BeamHist{t};
            items = MecaStruct_App.inputWidgets(B.W.In);
            if numel(items) ~= size(snap.vals, 1)
                return
            end
            app.HistBusy = true;
            try
                for k = 1:numel(items)
                    try
                        if isa(items(k), 'matlab.ui.control.Table')
                            items(k).Data = snap.vals{k, 2};
                        else
                            items(k).Value = snap.vals{k, 2};
                        end
                    catch
                    end
                end
                app.BeamSection = snap.sec;
                app.BeamUsesSection = snap.use;
                B.secInfo.Text = snap.info;
            catch err
                app.HistBusy = false;
                rethrow(err);
            end
            app.HistBusy = false;
            app.BeamHistPos = t;
            app.previewBeam();
            if step < 0
                B.W.Status.Text = 'Modification annulée. Cliquez sur « Calculer » pour mettre à jour les résultats.';
            else
                B.W.Status.Text = 'Modification rétablie. Cliquez sur « Calculer » pour mettre à jour les résultats.';
            end
        end

        function chainEdit(app, orig, src, evt)
            % Appelle le rappel d'origine d'un champ de Poutres puis mémorise l'état.
            if isa(orig, 'function_handle')
                orig(src, evt);
            end
            app.pushBeamHistory();
        end

        function previewBeam(app)
            %PREVIEWBEAM Redessine le schéma de la poutre avec la saisie courante (sans calcul) ; silencieux si la saisie est incomplète.
            B = app.H.Beam;
            ax = B.W.Axes{1}(1);
            try
                model = app.readBeamModel();
                PlotEngine.beamSchematic(ax, model);
            catch
                return
            end
            app.armSchematic(ax);
            B.W.Status.Text = 'Saisie modifiée : cliquez sur « Calculer » pour mettre à jour les résultats. Un clic sur le schéma ajoute un appui, une force ou une rotule.';
        end

        function armSchematic(app, ax)
            % Un clic sur le schéma appelle onSchematicClick (les tracés ne captent pas le clic).
            set(ax.Children, 'HitTest', 'off');
            ax.ButtonDownFcn = @(~, e) app.safeRun(@() app.onSchematicClick(e.IntersectionPoint(1)), 'Schéma');
        end

        function onSchematicClick(app, x, kind)
            %ONSCHEMATICCLICK Ajoute un appui simple, une force verticale de −10 kN ou une rotule à l'abscisse x du schéma.
            %   app.onSchematicClick(x) demande quoi ajouter (fenêtre visible) ; app.onSchematicClick(x, kind) :
            %   kind = 'appui', 'force' ou 'rotule'.
            B = app.H.Beam;
            L = B.L.Value;
            x = min(max(round(x, 3), 0), L);
            if nargin < 3
                if ~strcmp(app.UIFigure.Visible, 'on')
                    return
                end
                opts = {'Appui simple', 'Force −10 kN', 'Rotule', 'Annuler'};
                ch = uiconfirm(app.UIFigure, sprintf('Ajouter à s = %.3g m :', x), 'Schéma de la poutre', ...
                    'Options', opts, 'DefaultOption', 4, 'CancelOption', 4);
                kinds = {'appui', 'force', 'rotule', ''};
                kind = kinds{strcmp(ch, opts)};
                if isempty(kind)
                    return
                end
            end
            switch kind
                case 'appui'
                    app.addTableRow(B.sup, {x, 'appui_simple', ''});
                case 'force'
                    app.addTableRow(B.pl, {x, 0, -10, 0, '', 'G'});
                case 'rotule'
                    app.addTableRow(B.hg, {x, ''});
                otherwise
                    error('MecaStruct:App:invalidInput', 'Ajout au schéma : kind doit valoir ''appui'', ''force'' ou ''rotule''.');
            end
        end

        function showFormula(app, key)
            %SHOWFORMULA Affiche la fiche DataManager.formulaSheet(key) dans le formulaire rapide.
            key = char(key);
            sheet = DataManager.formulaSheet(key);
            w = 340;
            try
                pp = getpixelposition(app.FormulaPanel);
                if pp(3) > 150
                    w = pp(3) - 22;
                end
            catch
            end
            ax = app.FormulaAxes;
            ax.InnerPosition = [1 1 w 400];
            hpx = PlotEngine.formulaSheet(ax, sheet);
            ax.InnerPosition = [1 1 w hpx];
            ax.Toolbar.Visible = 'off';
            disableDefaultInteractivity(ax);
            app.FormulaKey = key;
            if ~isequal(app.FormulaDrop.Value, key)
                app.FormulaDrop.Value = key;
            end
            try
                scroll(app.FormulaPanel, 'top');
            catch
            end
        end

        function exportCurrentPlot(app, name, file)
            %EXPORTCURRENTPLOT Exporte le graphique visible d'une zone de travail (PNG ou PDF).
            %   app.exportCurrentPlot(name, file) : name = onglet ('Sections', 'Poutres'…, ou
            %   'Base de données' pour l'abaque Kt) ; file = chemin .png ou .pdf.
            %   Un seul axe : PlotEngine.exportAxes(axe) ; plusieurs axes : export de l'onglet.
            [~, wk] = MecaStruct_App.resolveName(name);
            if strcmp(wk, 'DB')
                PlotEngine.exportAxes(app.H.DB.KtAxes, file);
                return
            end
            W = app.H.(wk).W;
            t = W.PlotGroup.SelectedTab;
            k = find(W.PlotGroup.Children == t, 1);
            axs = W.Axes{k};
            vis = arrayfun(@(a) isgraphics(a) && strcmp(a.Visible, 'on'), axs);
            axs = axs(vis);
            if isscalar(axs)
                PlotEngine.exportAxes(axs, file);
            else
                ws = warning('off', 'all');
                restore = onCleanup(@() warning(ws));
                PlotEngine.exportAxes(t, file);
                clear restore
            end
        end

        function saveUserData(app, file)
            %SAVEUSERDATA Sauvegarde les matériaux/profilés utilisateur (DataManager.saveUserData).
            if nargin < 2 || isempty(file)
                file = app.DM.UserFile;
            end
            app.DM.saveUserData(file);
            app.H.DB.FileLabel.Text = ['Données utilisateur sauvegardées : ' char(file)];
        end

        function loadUserData(app, file)
            %LOADUSERDATA Charge des données utilisateur (.mat) puis rafraîchit les listes.
            if nargin < 2 || isempty(file)
                file = app.DM.UserFile;
            end
            app.DM.loadUserData(file);
            app.refreshDatabase();
            app.H.DB.FileLabel.Text = ['Données utilisateur chargées : ' char(file)];
        end

        function addMaterialFromForm(app)
            %ADDMATERIALFROMFORM Ajoute (ou remplace) le matériau utilisateur saisi dans le formulaire
            %   de la base de données (G complété par G = E/(2(1+ν)) s'il vaut 0).
            D = app.H.DB;
            name = strtrim(D.mName.Value);
            if isempty(name)
                error('MecaStruct:App:invalidMaterial', 'Le nom du matériau est obligatoire.');
            end
            cat = strtrim(D.mCat.Value);
            if isempty(cat)
                cat = 'Utilisateur';
            end
            G = app.si(D.mG, 'GPa');
            if G <= 0
                G = NaN;
            end
            m = struct('Name', name, 'Category', cat, 'E', app.si(D.mE, 'GPa'), 'G', G, 'nu', D.mNu.Value, ...
                'Re', app.si(D.mRe, 'MPa'), 'Rm', app.si(D.mRm, 'MPa'), 'alpha', app.si(D.mAlpha, '1e-6/°C'), ...
                'rho', D.mRho.Value, 'Note', 'Matériau utilisateur (saisi dans l''interface).', ...
                'Author', strtrim(D.mAuthor.Value));
            app.DM.addMaterial(m);
            app.refreshMaterialTable();
            app.refreshMaterialLists(name);
            app.refreshAuthorLists();
        end

        function addProfileFromForm(app)
            %ADDPROFILEFROMFORM Ajoute (ou remplace) le profilé utilisateur saisi (famille affichée) ;
            %   S, Iz, Iy, W et r sont calculés sur la géométrie simplifiée.
            D = app.H.DB;
            name = strtrim(D.pName.Value);
            if isempty(name)
                error('MecaStruct:App:invalidProfile', 'La désignation du profilé est obligatoire.');
            end
            p = struct('Name', name, 'h', app.si(D.ph, 'mm'), 'b', app.si(D.pb, 'mm'), 'a', app.si(D.pa, 'mm'), ...
                'e', app.si(D.pe, 'mm'), 'r', app.si(D.pr, 'mm'), 'Author', strtrim(D.pAuthor.Value));
            app.DM.addProfile(D.pFam.Value, p);
            app.refreshProfileTable();
            app.refreshProfileLists();
            app.refreshAuthorLists();
        end
    end

    %% =========================================================================================
    %  Méthodes statiques publiques
    %  =========================================================================================
    methods (Static)

        function openInBrowser(f)
            %OPENINBROWSER Ouvre un fichier local dans le navigateur (sans effet si MECASTRUCT_NO_BROWSER, pour les tests).
            if isempty(getenv('MECASTRUCT_NO_BROWSER'))
                web(['file:///' strrep(f, '\', '/')], '-browser');
            end
        end

        function T = unitCatalog()
            %UNITCATALOG Grandeurs et unités du convertisseur (struct : name, units, defFrom, defTo).
            T = MecaStruct_App.unitTable();
        end

        function out = convertUnits(val, quantity, from, to)
            %CONVERTUNITS Conversion d'une valeur entre deux unités d'une même grandeur.
            %   out = MecaStruct_App.convertUnits(val, quantity, from, to)
            %   quantity : 'Longueur', 'Aire', 'Moment quadratique', 'Force', 'Moment', 'Charge linéique',
            %   'Contrainte et pression', 'Module d''Young et de Coulomb', 'Angle', 'Angle par longueur',
            %   'Coefficient de dilatation', 'Masse volumique', 'Déformation', 'Écart de température',
            %   'Température absolue'.
            %   from, to : libellés d'unité de la grandeur (ex. 'kN·m', 'psi', '°F').
            %   Exemple : convertUnits(1, 'Longueur', 'in', 'mm') → 25.4.
            T = MecaStruct_App.unitTable();
            q = T(strcmp({T.name}, char(quantity)));
            if isempty(q)
                error('MecaStruct:App:unknownQuantity', 'Grandeur inconnue : « %s ».', char(quantity));
            end
            i = find(strcmp(q.units(:, 1), char(from)), 1);
            j = find(strcmp(q.units(:, 1), char(to)), 1);
            if isempty(i) || isempty(j)
                error('MecaStruct:App:unknownUnit', 'Unité inconnue pour « %s » : « %s » ou « %s ».', ...
                    char(quantity), char(from), char(to));
            end
            val = double(val);
            if strcmp(q.name, 'Température absolue')
                % températures absolues : passage par le kelvin (décalage d'origine) ; un écart ΔT
                % (champs ΔT de l'application) se convertit sans décalage : « Écart de température »
                switch q.units{i, 2}
                    case 'K', K = val;
                    case 'C', K = val + 273.15;
                    otherwise, K = (val + 459.67) * 5 / 9;
                end
                switch q.units{j, 2}
                    case 'K', out = K;
                    case 'C', out = K - 273.15;
                    otherwise, out = K * 9 / 5 - 459.67;
                end
                return
            end
            out = val .* DataManager.unitFactor(q.units{i, 2}) ./ DataManager.unitFactor(q.units{j, 2});
        end

        function p = stressGeometry(sec, p)
            %STRESSGEOMETRY Ajoute à p la géométrie pour bendingStress : profilé du catalogue → valeurs
            %   tabulées (la géométrie simplifiée ignore les congés : axe faible des IPN/UPN non
            %   conservatif de 15 à 18 %), sinon le contour exact.
            if strcmp(sec.type, 'profile')
                p.P = GeometryEngine.tabulated(sec);
            else
                p.sec = sec;
            end
        end

        function f = parseFunction(expr)
            %PARSEFUNCTION Convertit de manière sûre une expression texte en handle @(x).
            %   f = MecaStruct_App.parseFunction(expr) : expr ne peut contenir que des nombres, la
            %   variable x, pi, les fonctions sqrt, exp, log, log10, sin, cos, tan, abs, les
            %   opérateurs + - * / ^ (rendus élément par élément) et des parenthèses. Toute autre
            %   construction (guillemets, crochets, @, ;, =, autres identificateurs) est refusée.
            %   Le handle est vectorisé : f(x) a toujours la taille de x.
            e = strtrim(char(string(expr)));
            if isempty(e)
                error('MecaStruct:App:invalidExpression', 'Expression vide.');
            end
            if numel(e) > 300
                error('MecaStruct:App:invalidExpression', 'Expression trop longue (300 caractères au plus).');
            end
            if ~isempty(regexp(e, '[^0-9A-Za-z_\.\+\-\*/\^\(\)\s]', 'once'))
                error('MecaStruct:App:invalidExpression', ...
                    'Caractère non autorisé dans « %s » (autorisés : chiffres, x, + - * / ^ ( ) et fonctions usuelles).', e);
            end
            tmp = regexprep(e, '(\d+\.?\d*|\.\d+)([eE][\+\-]?\d+)?', ' ');
            ids = regexp(tmp, '[A-Za-z_]\w*', 'match');
            allowed = {'x', 'pi', 'sqrt', 'exp', 'log', 'log10', 'sin', 'cos', 'tan', 'abs'};
            bad = setdiff(ids, allowed);
            if ~isempty(bad)
                error('MecaStruct:App:invalidExpression', 'Identificateur non autorisé : « %s ».', strjoin(bad, ', '));
            end
            ev = regexprep(e, '(?<!\.)([\*/\^])', '.$1');
            try
                f0 = str2func(['@(x) ' ev]);
                v = f0(linspace(0, 1, 3));
            catch err
                error('MecaStruct:App:invalidExpression', 'Expression invalide « %s » : %s', e, err.message);
            end
            if ~isnumeric(v)
                error('MecaStruct:App:invalidExpression', 'L''expression « %s » ne renvoie pas un nombre.', e);
            end
            f = @(x) f0(x) + zeros(size(x));
        end
    end

    %% =========================================================================================
    %  Construction de l'interface
    %  =========================================================================================
    methods (Access = {?ValidationReport})

        function buildUI(app)
            % Grille principale : onglets à gauche, formulaire rapide à droite.
            g = uigridlayout(app.UIFigure, [1 2]);
            g.ColumnWidth = {'1x', 400};
            g.Padding = [4 4 4 4];
            app.TabGroup = uitabgroup(g);
            app.TabGroup.Layout.Row = 1;
            app.TabGroup.Layout.Column = 1;
            defs = {'Home', 'Accueil', 'materiaux'
                'DB', 'Base de données', 'materiaux'
                'Sec', 'Sections', 'geometrie'
                'Beam', 'Poutres', 'cohesion'
                'Tr', 'Treillis', 'treillis'
                'Sol', 'Sollicitations', 'traction'
                'Fla', 'Flambage', 'flambage'
                'Ten', 'Tenseurs & Critères', 'tenseurs'
                'Hoo', 'Hooke & Jauges', 'hooke'
                'Conv', 'Convertisseur', 'materiaux'};
            for k = 1:size(defs, 1)
                app.Tabs.(defs{k, 1}) = uitab(app.TabGroup, 'Title', defs{k, 2}, 'Tag', defs{k, 1}, ...
                    'UserData', defs{k, 3});
            end
            app.buildHomeTab();
            app.buildDatabaseTab();
            app.buildSectionsTab();
            app.buildBeamTab();
            app.buildTrussTab();
            app.buildSolicitationsTab();
            app.buildBucklingTab();
            app.buildTensorTab();
            app.buildHookeTab();
            app.buildConverterTab();
            app.buildFormulaPanel(g);
            app.TabGroup.SelectionChangedFcn = @(~, ~) app.safeRun(@() app.updateFormula(), 'Formulaire');
        end

        function buildHomeTab(app)
            % Onglet Accueil : par où commencer, conventions de signe et unités de saisie.
            g = uigridlayout(app.Tabs.Home, [11 1]);
            g.RowHeight = {34, 40, 40, 40, 40, 40, 40, 40, 36, 150, '1x'};
            g.Padding = [20 14 20 14];
            g.RowSpacing = 8;
            uilabel(g, 'Text', 'Bienvenue dans MecaStruct RdM Pro', 'FontSize', 22, 'FontWeight', 'bold', ...
                'FontColor', [0 0.35 0.65]);
            uilabel(g, 'WordWrap', 'on', 'Text', ['Chaque onglet est déjà rempli avec un exemple d''école : cliquez sur ' ...
                '« Calculer » pour voir un résultat, puis changez les valeurs. Que voulez-vous faire ?']);
            go = @(name) app.cbk(@() app.selectTab(name), 'Accueil');
            btn = {'Calculer une poutre (réactions, diagrammes, flèche)', 'Poutres'
                'Dimensionner un arbre en torsion', 'Torsion'
                'Vérifier une poutre au flambage', 'Flambage'
                'Convertir une unité (psi, kip, in…)', 'Convertisseur'};
            for k = 1:size(btn, 1)
                uibutton(g, 'Text', btn{k, 1}, 'FontSize', 14, 'HorizontalAlignment', 'left', ...
                    'ButtonPushedFcn', go(btn{k, 2}));
            end
            MecaStruct_App.styleButton(uibutton(g, 'Text', 'Visite guidée en 5 étapes : une poutre de A à Z', ...
                'ButtonPushedFcn', app.cbk(@() app.guidedTour(), 'Visite guidée')), 'primary');
            MecaStruct_App.styleButton(uibutton(g, 'Text', 'Ouvrir le guide d''utilisation (captures d''écran et rappels de RDM)', ...
                'ButtonPushedFcn', app.cbk(@() app.openDoc('GUIDE_UTILISATEUR.html'), 'Guide')), 'primary');
            pg = uigridlayout(g, [1 2]);
            pg.Padding = [0 0 0 0];
            uibutton(pg, 'Text', 'Enregistrer tout le projet (tous les onglets)', ...
                'ButtonPushedFcn', app.cbk(@() app.saveProject(), 'Enregistrement'));
            uibutton(pg, 'Text', 'Ouvrir un projet', 'ButtonPushedFcn', app.cbk(@() app.openProjectDialog(), 'Ouverture'));
            uilabel(g, 'Text', 'À retenir avant de saisir','FontWeight', 'bold', 'FontColor', [0 0.35 0.65]);
            uilabel(g, 'WordWrap', 'on', 'VerticalAlignment', 'top', 'Text', [ ...
                'Unités de saisie : sections en mm, longueurs de poutre en m, forces en kN, moments en kN·m, ' ...
                'charges réparties en kN/m, E et G en GPa, contraintes en MPa.' newline newline ...
                'Signes : une force vers le bas est négative (Fy < 0). N > 0 : traction. ' ...
                'Mfz > 0 : fibres du haut comprimées, fibres du bas tendues. ' newline newline ...
                'Un tableau (appuis, forces…) se remplit avec « Ajouter » ; « Supprimer la sélection » retire la ligne choisie. ' ...
                'Le panneau de droite affiche la fiche de formules de l''onglet ouvert.']);
        end

        function buildConverterTab(app)
            % Onglet Convertisseur : grandeur, valeur, unité de départ et d'arrivée, toutes les unités.
            t = app.Tabs.Conv;
            T = MecaStruct_App.unitTable();
            names = {T.name};
            g = uigridlayout(t, [4 1]);
            g.RowHeight = {78, 56, '1.3x', '1x'};
            g.Padding = [10 10 10 10];
            c = uigridlayout(g, [2 6]);
            c.ColumnWidth = {230, 160, 120, 120, 90, 150};
            c.RowHeight = {20, 30};
            c.Padding = [0 0 0 0];
            lab = {'Grandeur', 'Valeur', 'De', 'Vers'};
            for k = 1:4
                lb = uilabel(c, 'Text', lab{k}, 'FontWeight', 'bold', 'FontColor', [0 0.35 0.65]);
                lb.Layout.Row = 1;
                lb.Layout.Column = k;
            end
            C = struct();
            C.quant = uidropdown(c, 'Items', names, 'Value', names{1}, ...
                'ValueChangedFcn', @(~, ~) app.safeRun(@() app.onConvQuantity(), 'Convertisseur'));
            C.val = uieditfield(c, 'numeric', 'Value', 1, 'ValueDisplayFormat', '%.10g', ...
                'ValueChangedFcn', @(~, ~) app.safeRun(@() app.refreshConverter(), 'Convertisseur'));
            C.from = uidropdown(c, 'ValueChangedFcn', @(~, ~) app.safeRun(@() app.refreshConverter(), 'Convertisseur'));
            C.to = uidropdown(c, 'ValueChangedFcn', @(~, ~) app.safeRun(@() app.refreshConverter(), 'Convertisseur'));
            C.swap = uibutton(c, 'Text', 'Inverser', ...
                'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.swapConverter(), 'Convertisseur'));
            C.copy = uibutton(c, 'Text', 'Copier le résultat', ...
                'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.copyConverter(), 'Convertisseur'));
            ctl = {C.quant, C.val, C.from, C.to, C.swap, C.copy};
            for k = 1:6
                ctl{k}.Layout.Row = 2;
                ctl{k}.Layout.Column = k;
            end
            C.res = uilabel(g, 'FontSize', 22, 'FontWeight', 'bold', 'FontColor', [0.1 0.55 0.2], 'Text', '');
            C.all = uitable(g, 'RowName', {}, 'ColumnName', {'Unité', 'Valeur équivalente'}, ...
                'ColumnWidth', {160, 'auto'});
            bot = uigridlayout(g, [1 2]);
            bot.Padding = [0 0 0 0];
            bot.ColumnWidth = {'1.4x', '1x'};
            C.expect = uitable(bot, 'RowName', {}, 'ColumnName', {'Où', 'Champ', 'Unité attendue'}, ...
                'ColumnWidth', {120, 'auto', 150}, 'Data', MecaStruct_App.expectedUnits());
            C.useful = uitable(bot, 'RowName', {}, 'ColumnName', {'Équivalence utile en RDM', ''}, ...
                'ColumnWidth', {'auto', 'auto'}, 'Data', {
                '1 MPa', '= 1 N/mm² = 10⁶ Pa'
                '1 GPa', '= 1000 MPa (E acier = 190 GPa = 190 000 MPa)'
                '1 daN', '= 10 N'
                '1 kgf', '= 9,80665 N'
                '1 bar', '= 0,1 MPa'
                '1 ksi', '≈ 6,895 MPa'
                '1 psi', '≈ 6,895 kPa'
                '1 kN·m', '= 10⁶ N·mm'
                '1 in', '= 25,4 mm'
                '1 µdéf', '= 10⁻⁶ = 0,0001 %'
                '1 rad', '≈ 57,2958 °'});
            app.H.Conv = C;
            app.onConvQuantity();
        end

        function onConvQuantity(app)
            C = app.H.Conv;
            T = MecaStruct_App.unitTable();
            q = T(strcmp({T.name}, C.quant.Value));
            lab = q.units(:, 1)';
            C.from.Items = lab;
            C.to.Items = lab;
            C.from.Value = lab{q.defFrom};
            C.to.Value = lab{q.defTo};
            app.refreshConverter();
        end

        function swapConverter(app)
            C = app.H.Conv;
            a = C.from.Value;
            C.from.Value = C.to.Value;
            C.to.Value = a;
            app.refreshConverter();
        end

        function copyConverter(app)
            C = app.H.Conv;
            r = MecaStruct_App.convertUnits(C.val.Value, C.quant.Value, C.from.Value, C.to.Value);
            clipboard('copy', sprintf('%.10g', r));
            if ~endsWith(C.res.Text, '(copié)'), C.res.Text = [C.res.Text '   (copié)']; end
        end

        function refreshConverter(app)
            C = app.H.Conv;
            qn = C.quant.Value;
            v = C.val.Value;
            r = MecaStruct_App.convertUnits(v, qn, C.from.Value, C.to.Value);
            C.res.Text = sprintf('%.10g %s = %.10g %s', v, C.from.Value, r, C.to.Value);
            T = MecaStruct_App.unitTable();
            q = T(strcmp({T.name}, qn));
            n = size(q.units, 1);
            d = cell(n, 2);
            for k = 1:n
                d{k, 1} = q.units{k, 1};
                d{k, 2} = sprintf('%.10g', MecaStruct_App.convertUnits(v, qn, C.from.Value, q.units{k, 1}));
            end
            C.all.Data = d;
            app.Results.converter = struct('quantity', qn, 'value', v, 'from', C.from.Value, 'to', C.to.Value, 'result', r);
        end

        function buildFormulaPanel(app, g)
            % Panneau latéral « Formulaire rapide » : sélecteur + panneau défilant.
            p = uipanel(g, 'Title', 'Formulaire rapide', 'FontWeight', 'bold');
            p.Layout.Row = 1;
            p.Layout.Column = 2;
            pg = uigridlayout(p, [3 1]);
            pg.RowHeight = {24, 30, '1x'};
            pg.Padding = [4 4 4 4];
            keys = DataManager.formulaKeys();
            labels = cellfun(@MecaStruct_App.formulaLabel, keys, 'UniformOutput', false);
            app.FormulaDrop = uidropdown(pg, 'Items', labels, 'ItemsData', keys, 'Value', keys{1}, ...
                'ValueChangedFcn', @(s, ~) app.safeRun(@() app.showFormula(s.Value), 'Formulaire'));
            bg = uigridlayout(pg, [1 3]);
            bg.Padding = [0 0 0 0];
            bg.ColumnSpacing = 4;
            bg.ColumnWidth = {'1x', 0, 0};
            app.ButtonGrid = bg;
            app.BtnVal = uibutton(bg, 'Text', 'Dossier de validation de ce problème', 'FontWeight', 'bold', ...
                'Tooltip', 'Génère un fichier HTML autonome (données, hypothèses, équations chiffrées, résultats, diagrammes) à envoyer à un relecteur.', ...
                'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.exportValidation(), 'Dossier de validation'));
            app.BtnNote = uibutton(bg, 'Text', 'Note de calcul', 'FontWeight', 'bold', 'Visible', 'off', ...
                'Tooltip', 'Ouvre le document général : hypothèses, équations, conditions aux limites, démonstrations.', ...
                'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.openDoc('NOTE_DE_CALCUL.html'), 'Note de calcul'));
            MecaStruct_App.styleButton(app.BtnVal, 'accent');
            MecaStruct_App.styleButton(app.BtnNote, 'accent');
            app.BtnGuide = uibutton(bg, 'Text', 'Guide',...
                'Tooltip', 'Ouvre le guide d''utilisation avec captures d''écran et rappels de RDM.', ...
                'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.openDoc('GUIDE_UTILISATEUR.html'), 'Guide'));
            app.FormulaPanel = uipanel(pg, 'Scrollable', 'on', 'BorderType', 'none');
            % Positions en pixels autorisées ici : panneau défilant (hauteur = hauteur de la fiche).
            app.FormulaAxes = uiaxes(app.FormulaPanel, 'Units', 'pixels', 'Position', [1 1 340 400]);
            app.FormulaAxes.Toolbar.Visible = 'off';
            disableDefaultInteractivity(app.FormulaAxes);
        end

        function W = makeWork(app, parent, leftW, key, plotDefs, tableDefs)
            % Zone de travail standard : saisie (gauche, défilante), barre d'export, onglets
            % graphiques (uiaxes) et onglets de résultats (rapport + tables).
            g = uigridlayout(parent, [1 2]);
            g.ColumnWidth = {leftW, '1x'};
            g.Padding = [4 4 4 4];
            g.ColumnSpacing = 6;
            W.In = uigridlayout(g, [1 2]);
            W.In.Layout.Row = 1;
            W.In.Layout.Column = 1;
            W.In.Scrollable = 'on';
            W.In.ColumnWidth = {'1.25x', '1x'};
            W.In.RowSpacing = 4;
            W.In.Padding = [4 4 4 4];
            W.In.UserData = 0;
            rg = uigridlayout(g, [3 1]);
            rg.Layout.Row = 1;
            rg.Layout.Column = 2;
            rg.RowHeight = {26, '1.8x', '1x'};
            rg.Padding = [0 0 0 0];
            rg.RowSpacing = 4;
            bar = uigridlayout(rg, [1 4]);
            bar.ColumnWidth = {'1x', 120, 120, 230};
            bar.Padding = [0 0 0 0];
            W.Status = uilabel(bar, 'Text', 'Saisir les données puis cliquer sur « Calculer ».', 'FontWeight', 'bold');
            uibutton(bar, 'Text', 'Exporter PNG', 'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.exportDialog(key, 'png'), 'Export'));
            uibutton(bar, 'Text', 'Exporter PDF', 'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.exportDialog(key, 'pdf'), 'Export'));
            uibutton(bar, 'Text', 'Exporter en tableau (.xlsx / .csv)', 'Tooltip', 'Écrit les tableaux de résultats : un classeur Excel (.xlsx, une feuille par tableau) ou des fichiers CSV (un par tableau).', ...
                'ButtonPushedFcn', @(~, ~) app.safeRun(@() app.exportResultsDialog(key), 'Export'));
            W.PlotGroup = uitabgroup(rg);
            W.Axes = cell(1, size(plotDefs, 1));
            for k = 1:size(plotDefs, 1)
                t = uitab(W.PlotGroup, 'Title', plotDefs{k, 1}, 'UserData', plotDefs{k, 3});
                rc = plotDefs{k, 2};
                tg = uigridlayout(t, rc);
                tg.Padding = [2 2 2 2];
                tg.RowSpacing = 2;
                axs = gobjects(1, prod(rc));
                for j = 1:prod(rc)
                    axs(j) = app.newAxes(tg);
                end
                W.Axes{k} = axs;
            end
            W.ResGroup = uitabgroup(rg);
            t = uitab(W.ResGroup, 'Title', 'Rapport');
            tg = uigridlayout(t, [1 1]);
            tg.Padding = [0 0 0 0];
            % Texte brut conservé (tests, accès programmatique) mais masqué ; affichage en HTML coloré.
            W.Report = uitextarea(tg, 'Editable', 'off', 'FontName', 'Consolas', 'Value', {''}, 'Visible', 'off');
            W.ReportHTML = uihtml(tg, 'HTMLSource', MecaStruct_App.reportToHTML({'Saisir les données puis cliquer sur « Calculer ».'}));
            W.ReportHTML.Layout.Row = 1;
            W.ReportHTML.Layout.Column = 1;
            W.Tables = struct();
            for k = 1:size(tableDefs, 1)
                t = uitab(W.ResGroup, 'Title', tableDefs{k, 2});
                tg = uigridlayout(t, [1 1]);
                tg.Padding = [0 0 0 0];
                W.Tables.(tableDefs{k, 1}) = uitable(tg, 'RowName', {});
            end
        end

        function ax = newAxes(~, parent)
            % uiaxes (barre d'outils par défaut : export, datatips, déplacement, zoom, restauration).
            ax = uiaxes(parent);
        end

        function finishAxes(~, axs)
            % Datatips, zoom et déplacement actifs après un tracé (PlotEngine fait cla reset).
            for k = 1:numel(axs)
                ax = axs(k);
                if isgraphics(ax) && strcmp(ax.Visible, 'on')
                    ax.Toolbar.Visible = 'on';
                    enableDefaultInteractivity(ax);
                end
            end
        end

        function finishWork(app, W)
            % Interactions sur tous les axes d'une zone de travail.
            for k = 1:numel(W.Axes)
                app.finishAxes(W.Axes{k});
            end
        end

        function vals = captureInputs(app, key)
            % Classe, valeur et clé (libellé de la ligne) de chaque champ de saisie de l'onglet key.
            items = MecaStruct_App.inputWidgets(app.H.(key).W.In);
            vals = cell(numel(items), 3);
            for k = 1:numel(items)
                vals{k, 1} = class(items(k));
                if isa(items(k), 'matlab.ui.control.Table')
                    vals{k, 2} = items(k).Data;
                else
                    vals{k, 2} = items(k).Value;
                end
                vals{k, 3} = MecaStruct_App.inputKey(items(k));
            end
        end

        function n = restoreInputs(app, key, vals)
            % Remet les valeurs de captureInputs ; n = champs non restaurés (introuvables, autre classe, valeur refusée).
            % Fichiers récents (3 colonnes) : champ par champ d'après la clé, donc indépendant de l'ordre des champs.
            % Anciens fichiers (2 colonnes) : par position, en ignorant les champs ajoutés depuis (balise MSv2).
            items = MecaStruct_App.inputWidgets(app.H.(key).W.In);
            if size(vals, 2) < 3
                isNew = arrayfun(@(h) strcmp(h.Tag, 'MSv2'), items);
                if size(vals, 1) == numel(items) - nnz(isNew)
                    items = items(~isNew);   % fichier d'une version sans ces champs
                end
                if size(vals, 1) ~= numel(items)
                    error('MecaStruct:App:badProblemFile', ['Ce fichier n''est pas un problème enregistré depuis cet onglet ' ...
                        '(ou il date d''une autre version de l''application).']);
                end
                target = 1:numel(items);
            else
                target = MecaStruct_App.matchInputs(items, vals);
            end
            n = 0;
            for k = 1:numel(target)
                if target(k) == 0
                    n = n + 1;
                    continue
                end
                try
                    if isa(items(target(k)), 'matlab.ui.control.Table')
                        items(target(k)).Data = vals{k, 2};
                    else
                        items(target(k)).Value = vals{k, 2};
                    end
                catch
                    n = n + 1;
                end
            end
            if strcmp(key, 'Beam')
                app.markBeamManual();
                app.resetBeamHistory();
            end
        end

        function sheets = resultSheets(app, key)
            % {nom de feuille, table} pour chaque tableau de résultats non vide de l'onglet key.
            sheets = cell(0, 2);
            tbl = app.H.(key).W.Tables;
            for nm = fieldnames(tbl)'
                u = tbl.(nm{1});
                d = u.Data;
                if isempty(d)
                    continue
                end
                if istable(d)
                    T = d;
                else
                    if iscell(d), T = cell2table(d); else, T = array2table(d); end
                    cn = u.ColumnName;
                    if iscellstr(cn) && numel(cn) == width(T) %#ok<ISCLSTR>
                        T.Properties.VariableNames = matlab.lang.makeUniqueStrings(matlab.lang.makeValidName(cn), {}, namelengthmax);
                    end
                end
                name = strtrim(regexprep(char(ancestor(u, 'uitab').Title), '[\[\]:*?/\\]', ' '));
                sheets(end + 1, :) = {name(1:min(end, 31)), T}; %#ok<AGROW>
            end
            if strcmp(key, 'Beam') && isfield(app.Results, 'beam') && ~isempty(app.Results.beam)
                sheets = [sheets; MecaStruct_App.beamEffortSheets(app.Results.beam.sol)];
            end
        end

        function confirmOverwrite(app, fcn, s, e)
            % « Charger l'exemple » écrase la saisie : demande confirmation (fenêtre visible seulement).
            if strcmp(app.UIFigure.Visible, 'on')
                ch = uiconfirm(app.UIFigure, 'Remplacer les valeurs saisies de cet onglet par l''exemple ?', ...
                    'Charger l''exemple', 'Options', {'Remplacer', 'Annuler'}, 'DefaultOption', 2, 'CancelOption', 2);
                if ~strcmp(ch, 'Remplacer')
                    return
                end
            end
            fcn(s, e);
        end

        function [h, lb] = addRow(app, g, label, kind, varargin)
            % Ajoute une ligne au panneau de saisie g ; les lignes qui suivent un titre forment une section repliable
            % (titre + 'closed' : fermée au départ).
            [h, lb] = app.addRowRaw(g, label, kind, varargin{:});
            if any(strcmp(kind, {'num', 'drop', 'text', 'check'}))
                h.UserData = label;   % clé de restauration des problèmes enregistrés
            elseif strcmp(kind, 'table')
                h.UserData = ['table ' strjoin(varargin{2}, ' | ')];
            end
            if strcmp(kind, 'title')
                setappdata(g, 'MSsection', h);
            elseif isappdata(g, 'MSsection')
                hs = h;
                if strcmp(kind, 'checks')
                    hs = h(1).Parent;   % la sous-grille qui porte les cases
                end
                hs = [lb(:); hs(:)];
                btn = getappdata(g, 'MSsection');
                s = btn.UserData;
                rh = g.RowHeight;
                r = g.UserData;
                s.rows(end + 1) = r;
                s.h(end + 1) = rh{r};
                s.handles = [s.handles; hs];
                if ~s.open
                    rh{r} = 0;
                    g.RowHeight = rh;
                    set(hs, 'Visible', false);
                end
                btn.UserData = s;
            end
        end

        function toggleSection(app, btn) %#ok<INUSL>
            % Plie ou déplie la section du titre btn : lignes à hauteur 0 et champs masqués (les valeurs saisies sont conservées).
            s = btn.UserData;
            g = btn.Parent;
            s.open = ~s.open;
            rh = g.RowHeight;
            for k = 1:numel(s.rows)
                if s.open
                    rh{s.rows(k)} = s.h(k);
                else
                    rh{s.rows(k)} = 0;
                end
            end
            g.RowHeight = rh;
            set(s.handles(isgraphics(s.handles)), 'Visible', s.open);
            btn.Text = MecaStruct_App.sectionText(s.label, s.open);
            btn.UserData = s;
        end

        function [h, lb] = addRowRaw(app, g, label, kind, varargin)
            % Ajoute une ligne au panneau de saisie g (grille à 2 colonnes, hauteur en pixels).
            r = g.UserData + 1;
            g.UserData = r;
            hpx = 24;
            switch kind
                case {'table', 'textarea', 'note'}
                    hpx = varargin{1};
                case 'checks'
                    hpx = 48;
            end
            rh = g.RowHeight;
            if r == 1
                rh = {};
            end
            rh{r} = hpx;
            g.RowHeight = rh;
            lb = [];
            span = true;
            switch kind
                case 'title'
                    isOpen = isempty(varargin) || ~strcmp(varargin{1}, 'closed');
                    h = uibutton(g, 'Text', MecaStruct_App.sectionText(label, isOpen), 'FontWeight', 'bold', ...
                        'BackgroundColor', [0.17 0.33 0.50], 'FontColor', [1 1 1], 'HorizontalAlignment', 'left', ...
                        'Tooltip', 'Cliquer pour plier ou déplier cette section.', ...
                        'ButtonPushedFcn', @(s, ~) app.toggleSection(s));
                    h.UserData = struct('label', label, 'open', isOpen, 'rows', [], 'h', [], 'handles', gobjects(0, 1));
                case 'note'
                    h = uilabel(g, 'Text', label, 'WordWrap', 'on', 'FontAngle', 'italic', 'VerticalAlignment', 'top');
                case 'button'
                    fcn = varargin{1};
                    if ~isempty(regexp(label, '^(Re)?charger l''exemple', 'once', 'ignorecase'))
                        fcn = @(s, e) app.confirmOverwrite(fcn, s, e);
                    end
                    h = MecaStruct_App.styleButton(uibutton(g, 'Text', label, 'ButtonPushedFcn', fcn));
                case 'buttons'
                    c = varargin{1};
                    h = gobjects(1, 2);
                    for j = 1:2
                        h(j) = MecaStruct_App.styleButton(uibutton(g, 'Text', c{2 * j - 1}, 'ButtonPushedFcn', c{2 * j}));
                        h(j).Layout.Row = r;
                        h(j).Layout.Column = j;
                    end
                    return
                case 'table'
                    cols = varargin{2};
                    h = uitable(g, 'ColumnName', cols, 'RowName', {}, 'Data', cell(0, numel(cols)), ...
                        'ColumnEditable', true(1, numel(cols)));
                    if numel(varargin) >= 3
                        h.ColumnFormat = varargin{3};
                    end
                case 'textarea'
                    h = uitextarea(g, 'Editable', 'off', 'Value', {''});
                otherwise
                    span = false;
                    lb = uilabel(g, 'Text', label);
                    lb.Layout.Row = r;
                    lb.Layout.Column = 1;
                    switch kind
                        case 'num'
                            h = uieditfield(g, 'numeric', 'Value', 0, 'ValueDisplayFormat', '%.6g');
                        case 'drop'
                            h = uidropdown(g, 'Items', varargin{1});
                            if numel(varargin) >= 2
                                h.ItemsData = varargin{2};
                            end
                        case 'text'
                            h = uieditfield(g, 'text');
                        case 'check'
                            h = uicheckbox(g, 'Text', '');
                        case 'checks'
                            names = varargin{1};
                            sub = uigridlayout(g, [2 ceil(numel(names) / 2)]);
                            sub.Padding = [0 0 0 0];
                            sub.RowSpacing = 0;
                            sub.ColumnSpacing = 2;
                            sub.Layout.Row = r;
                            sub.Layout.Column = 2;
                            h = gobjects(1, numel(names));
                            for j = 1:numel(names)
                                h(j) = uicheckbox(sub, 'Text', names{j});
                            end
                            return
                        otherwise
                            error('MecaStruct:App:internal', 'Type de ligne inconnu : %s', kind);
                    end
            end
            h(1).Layout.Row = r;
            if span
                h(1).Layout.Column = [1 2];
            else
                h(1).Layout.Column = 2;
            end
        end

        function cb = cbk(app, fn, title)
            % Callback protégé (try/catch → uialert non bloquant ou journal).
            cb = @(~, ~) app.safeRun(fn, title);
        end

        %% ------------------------------- Base de données -----------------------------------
        function buildDatabaseTab(app)
            t = app.Tabs.DB;
            g = uigridlayout(t, [2 1]);
            g.RowHeight = {30, '1x'};
            g.Padding = [4 4 4 4];
            bar = uigridlayout(g, [1 3]);
            bar.ColumnWidth = {'1x', 240, 240};
            bar.Padding = [0 0 0 0];
            D = struct();
            D.FileLabel = uilabel(bar, 'Text', ['Fichier utilisateur : ' app.DM.UserFile]);
            uibutton(bar, 'Text', 'Sauvegarder les données utilisateur', 'ButtonPushedFcn', app.cbk(@() app.saveDialog(), 'Sauvegarde'));
            uibutton(bar, 'Text', 'Charger des données utilisateur', 'ButtonPushedFcn', app.cbk(@() app.loadDialog(), 'Chargement'));
            sg = uitabgroup(g);
            app.SubDB = sg;

            % --- Matériaux
            tm = uitab(sg, 'Title', 'Matériaux');
            gm = uigridlayout(tm, [1 2]);
            gm.ColumnWidth = {'1x', 310};
            D.MatTable = uitable(gm, 'RowName', {}, ...
                'CellEditCallback', @(~, e) app.safeRun(@() app.onMaterialEdit(e), 'Matériaux'), ...
                'CellSelectionCallback', @(~, e) app.onDbSelect('MatSel', e));
            fm = uigridlayout(gm, [1 2]);
            fm.Scrollable = 'on';
            fm.UserData = 0;
            fm.ColumnWidth = {'1.2x', '1x'};
            fm.RowSpacing = 4;
            app.addRow(fm, 'Ajouter un matériau utilisateur', 'title');
            D.mName = app.addRow(fm, 'Nom', 'text');
            D.mCat = app.addRow(fm, 'Catégorie', 'text');
            D.mE = app.addRow(fm, 'E (GPa)', 'num');
            D.mNu = app.addRow(fm, 'ν (-)', 'num');
            D.mG = app.addRow(fm, 'G (GPa) — calculé', 'num');
            D.mRe = app.addRow(fm, 'Re (MPa)', 'num');
            D.mRm = app.addRow(fm, 'Rm (MPa)', 'num');
            D.mAlpha = app.addRow(fm, 'α (10⁻⁶/°C)', 'num');
            D.mRho = app.addRow(fm, 'ρ (kg/m³)', 'num');
            D.mAuthor = app.addRow(fm, 'Ajouté par', 'drop', {'Utilisateur'});
            D.mAuthor.Editable = 'on';
            D.mAuthor.Tooltip = 'Choisir un nom dans la liste ou taper le sien : il apparaît dans la colonne « Ajouté par ».';
            D.mE.ValueChangedFcn = @(~, ~) app.autoG();
            D.mNu.ValueChangedFcn = @(~, ~) app.autoG();
            app.addRow(fm, '', 'buttons', {'Ajouter / remplacer', app.cbk(@() app.addMaterialFromForm(), 'Matériaux'), ...
                'Supprimer la sélection', app.cbk(@() app.removeSelectedMaterial(), 'Matériaux')});
            app.addRow(fm, ['G est complété automatiquement par G = E/(2(1+ν)). La colonne « Ajouté par » ' ...
                'indique l''origine : « Base fournie » (non modifiable) ou le nom de celui qui a ajouté la ligne ' ...
                '(modifiable directement dans la table).'], 'note', 90);
            D.mE.Value = 210; D.mNu.Value = 0.3; D.mRe.Value = 300; D.mRm.Value = 500; D.mAlpha.Value = 12; D.mRho.Value = 7850;
            D.mName.Value = 'Acier utilisateur'; D.mCat.Value = 'Utilisateur';

            % --- Profilés
            tp = uitab(sg, 'Title', 'Profilés');
            gp = uigridlayout(tp, [1 2]);
            gp.ColumnWidth = {'1x', 310};
            left = uigridlayout(gp, [2 1]);
            left.RowHeight = {26, '1x'};
            left.Padding = [0 0 0 0];
            top = uigridlayout(left, [1 3]);
            top.ColumnWidth = {150, 160, '1x'};
            top.Padding = [0 0 0 0];
            uilabel(top, 'Text', 'Famille de profilés :');
            D.pFam = uidropdown(top, 'Items', cellstr(app.DM.listProfileFamilies()), ...
                'ValueChangedFcn', app.cbk(@() app.refreshProfileTable(), 'Profilés'));
            uilabel(top, 'Text', 'Convention : Iz = axe fort (= Iy Eurocode), Iy = axe faible.');
            D.ProfTable = uitable(left, 'RowName', {});
            fp = uigridlayout(gp, [1 2]);
            fp.Scrollable = 'on';
            fp.UserData = 0;
            fp.ColumnWidth = {'1.2x', '1x'};
            fp.RowSpacing = 4;
            app.addRow(fp, 'Ajouter un profilé (famille affichée)', 'title');
            D.pName = app.addRow(fp, 'Désignation', 'text');
            D.ph = app.addRow(fp, 'h (mm)', 'num');
            D.pb = app.addRow(fp, 'b (mm)', 'num');
            D.pa = app.addRow(fp, 'a — âme (mm)', 'num');
            D.pe = app.addRow(fp, 'e — aile (mm)', 'num');
            D.pr = app.addRow(fp, 'r — congé (mm)', 'num');
            D.pAuthor = app.addRow(fp, 'Ajouté par', 'drop', {'Utilisateur'});
            D.pAuthor.Editable = 'on';
            D.pAuthor.Tooltip = 'Choisir un nom dans la liste ou taper le sien : il apparaît dans la colonne « Ajouté par ».';
            app.addRow(fp, 'Ajouter le profilé', 'button', app.cbk(@() app.addProfileFromForm(), 'Profilés'));
            app.addRow(fp, 'S, Iz, Iy, W et r sont calculés sur la géométrie simplifiée (épaisseurs constantes).', 'note', 50);
            D.pName.Value = 'IPE 210 util'; D.ph.Value = 210; D.pb.Value = 105; D.pa.Value = 6; D.pe.Value = 9; D.pr.Value = 12;

            % --- Matage
            tb = uitab(sg, 'Title', 'Pressions de matage');
            gb = uigridlayout(tb, [2 1]);
            gb.RowHeight = {'1x', 40};
            D.BearTable = uitable(gb, 'RowName', {});
            uilabel(gb, 'Text', ['Pressions admissibles de matage P_adm (MPa) selon la liaison et les conditions ' ...
                'de fonctionnement ; utilisées dans Sollicitations > Cisaillement & Matage.'], 'WordWrap', 'on');

            % --- Abaques Kt
            tk = uitab(sg, 'Title', 'Abaques Kt');
            gk = uigridlayout(tk, [1 2]);
            gk.ColumnWidth = {320, '1x'};
            fk = uigridlayout(gk, [1 2]);
            fk.Scrollable = 'on';
            fk.UserData = 0;
            fk.ColumnWidth = {'1.2x', '1x'};
            fk.RowSpacing = 4;
            charts = DataManager.ktCharts();
            app.addRow(fk, 'Abaque de concentration de contrainte', 'title');
            D.ktId = app.addRow(fk, 'Abaque', 'drop', {charts.title}, {charts.id});
            D.ktId.ValueChangedFcn = app.cbk(@() app.onKtChartChange(true), 'Abaques Kt');
            [D.ktP1, D.ktL1] = app.addRow(fk, 'r/d (-)', 'num');
            [D.ktP2, D.ktL2] = app.addRow(fk, 'D/d (-)', 'num');
            app.addRow(fk, 'Calculer Kt', 'button', app.cbk(@() app.computeKt(), 'Abaques Kt'));
            app.addRow(fk, '', 'buttons', {'Exporter PNG', app.cbk(@() app.exportDialog('DB', 'png'), 'Export'), ...
                'Exporter PDF', app.cbk(@() app.exportDialog('DB', 'pdf'), 'Export')});
            D.ktRes = app.addRow(fk, '', 'textarea', 130);
            D.ktDesc = app.addRow(fk, '', 'textarea', 200);
            D.KtAxes = app.newAxes(gk);
            D.MatSel = [];
            app.H.DB = D;
        end

        function refreshDatabase(app)
            app.refreshMaterialTable();
            app.refreshProfileTable();
            app.refreshBearingTable();
            app.refreshMaterialLists();
            app.refreshProfileLists();
            app.refreshBearingList();
            app.refreshAuthorLists();
        end

        function refreshMaterialTable(app)
            M = app.DM.Materials;
            T = table(M.Name, M.Category, M.E / 1e9, M.G / 1e9, M.nu, M.Re / 1e6, M.Rm / 1e6, M.alpha * 1e6, ...
                M.rho, M.Author, M.Note, 'VariableNames', {'Nom', 'Catégorie', 'E (GPa)', 'G (GPa)', 'ν (-)', ...
                'Re (MPa)', 'Rm (MPa)', 'α (1e-6/°C)', 'ρ (kg/m³)', 'Ajouté par', 'Note'});
            tb = app.H.DB.MatTable;
            tb.Data = T;
            tb.ColumnEditable = [false false true(1, 7) false false];
        end

        function refreshProfileTable(app)
            D = app.H.DB;
            P = app.DM.Profiles.(D.pFam.Value);
            D.ProfTable.Data = table(P.Name, P.h * 1e3, P.b * 1e3, P.a * 1e3, P.e * 1e3, P.r * 1e3, P.S * 1e4, ...
                P.Iz * 1e8, P.Iy * 1e8, P.Wz * 1e6, P.Wy * 1e6, P.rz * 1e3, P.ry * 1e3, P.mass, P.c * 1e3, P.Author, ...
                'VariableNames', {'Désignation', 'h (mm)', 'b (mm)', 'a (mm)', 'e (mm)', 'r (mm)', 'S (cm²)', ...
                'Iz (cm⁴)', 'Iy (cm⁴)', 'Wz (cm³)', 'Wy (cm³)', 'rz (mm)', 'ry (mm)', 'masse (kg/m)', 'c (mm)', 'Ajouté par'});
        end

        function refreshAuthorLists(app)
            %REFRESHAUTHORLISTS Met à jour les listes « Ajouté par » des formulaires (noms déjà utilisés ; on peut en saisir un autre).
            D = app.H.DB;
            P = app.DM.Profiles;
            names = app.DM.Materials.Author(app.DM.Materials.IsUser);
            for f = fieldnames(P)'
                names = [names; P.(f{1}).Author(P.(f{1}).IsUser)]; %#ok<AGROW>
            end
            items = cellstr(unique(["Utilisateur"; names(:)], 'stable'));
            for dd = [D.mAuthor, D.pAuthor]
                old = dd.Value;
                dd.Items = items;
                dd.Value = old;
            end
        end

        function refreshBearingTable(app)
            B = app.DM.BearingPressures;
            app.H.DB.BearTable.Data = table(B.Liaison, B.Conditions, B.Pmin / 1e6, B.Pmax / 1e6, B.Note, ...
                'VariableNames', {'Liaison', 'Conditions', 'Pmin (MPa)', 'Pmax (MPa)', 'Note'});
        end

        function refreshMaterialLists(app, changed)
            %REFRESHMATERIALLISTS Met à jour les menus de matériaux. Un onglet qui utilise un matériau
            %   modifié (nom dans `changed`) ou supprimé reçoit les valeurs à jour (sinon E, Re… resteraient
            %   ceux de l'ancien matériau).
            if nargin < 2
                changed = {};
            end
            changed = cellstr(string(changed));
            names = cellstr(app.DM.listMaterials());
            for k = 1:numel(app.MatKeys)
                key = app.MatKeys{k};
                if isfield(app.H, key) && isfield(app.H.(key), 'mat')
                    dd = app.H.(key).mat;
                    old = dd.Value;
                    dd.Items = names;
                    kept = any(strcmp(old, names));
                    if kept
                        dd.Value = old;
                    end
                    if ~kept || any(strcmp(old, changed))
                        app.applyMaterial(key);
                    end
                end
            end
        end

        function refreshProfileLists(app)
            for key = {'Sec', 'Fla'}
                if isfield(app.H, key{1})
                    app.onFamilyChange(key{1});
                end
            end
        end

        function refreshBearingList(app)
            if ~isfield(app.H, 'Cis')
                return
            end
            B = app.DM.BearingPressures;
            n = height(B);
            items = cell(1, n);
            for i = 1:n
                items{i} = sprintf('%s — %s (%g à %g MPa)', B.Liaison(i), B.Conditions(i), B.Pmin(i) / 1e6, B.Pmax(i) / 1e6);
            end
            dd = app.H.Cis.PadmSrc;
            old = dd.Value;
            dd.Items = items;
            dd.ItemsData = 1:n;
            if isnumeric(old) && isscalar(old) && old >= 1 && old <= n
                dd.Value = old;
            end
        end

        function onBearingSelect(app)
            C = app.H.Cis;
            B = app.DM.BearingPressures;
            i = C.PadmSrc.Value;
            C.Padm.Value = B.Pmin(i) / 1e6;
        end

        function onDbSelect(app, field, e)
            if ~isempty(e.Indices)
                app.H.DB.(field) = unique(e.Indices(:, 1));
            end
        end

        function onMaterialEdit(app, e)
            M = app.DM.Materials;
            row = e.Indices(1);
            col = e.Indices(2);
            if ~M.IsUser(row)
                app.refreshMaterialTable();
                error('MecaStruct:App:readOnly', ['Les matériaux de la « Base fournie » ne sont pas modifiables : ajoutez un ' ...
                    'matériau (formulaire de droite) pour personnaliser une valeur.']);
            end
            fields = {'', '', 'E', 'G', 'nu', 'Re', 'Rm', 'alpha', 'rho'};
            units = {'', '', 'GPa', 'GPa', '-', 'MPa', 'MPa', '1e-6/°C', 'kg/m^3'};
            f = fields{col};
            m = app.DM.getMaterial(M.Name(row));
            m.(f) = DataManager.toSI(double(e.NewData), units{col});
            if any(strcmp(f, {'E', 'nu'}))
                m.G = NaN;
            elseif strcmp(f, 'G')
                m.nu = NaN;
            end
            % retirer les phrases automatiques de completeIsotropic (elles seraient périmées) ; le texte de l'utilisateur reste
            auto = {'Écart de cohérence :.*?\(écart [\d.]+ %\)\.', 'G calculé par G = E/\(2\(1\+ν\)\)\.', ...
                'ν déduit de E et G : ν = E/\(2G\) − 1\.', 'E calculé par E = 2G\(1\+ν\)\.', ...
                'Constantes élastiques incomplètes \(au moins deux de E, G, ν sont nécessaires\)\.'};
            m.Note = strtrim(regexprep(char(strjoin(string(m.Note), ' ')), strjoin(auto, '|'), ''));
            app.DM.addMaterial(m);
            app.refreshMaterialTable();
            app.refreshMaterialLists(m.Name);
        end

        function autoG(app)
            D = app.H.DB;
            nu = D.mNu.Value;
            if D.mE.Value > 0 && nu > -1 && nu < 0.5
                D.mG.Value = D.mE.Value / (2 * (1 + nu));
            end
        end

        function removeSelectedMaterial(app)
            sel = app.H.DB.MatSel;
            if isempty(sel)
                error('MecaStruct:App:noSelection', 'Sélectionner d''abord une ligne de la table des matériaux.');
            end
            names = app.DM.Materials.Name(sel);
            for k = 1:numel(names)
                app.DM.removeMaterial(names(k));
            end
            app.H.DB.MatSel = [];
            app.refreshMaterialTable();
            app.refreshMaterialLists();
        end

        function onKtChartChange(app, compute)
            D = app.H.DB;
            charts = DataManager.ktCharts();
            ch = charts(strcmp({charts.id}, D.ktId.Value));
            if strcmp(ch.id, 'plaque_trou_traction')
                D.ktL1.Text = 'd/W (-)';
                D.ktL2.Text = '(sans objet)';
                D.ktP2.Enable = 'off';
                if D.ktP1.Value <= 0 || D.ktP1.Value >= 1
                    D.ktP1.Value = 0.3;
                end
            else
                D.ktL1.Text = 'r/d (-)';
                D.ktL2.Text = 'D/d (-)';
                D.ktP2.Enable = 'on';
            end
            D.ktDesc.Value = {ch.title; ''; ch.description};
            if compute
                app.computeKt();
            end
        end

        function saveDialog(app)
            [f, p] = uiputfile({'*.mat', 'Données MecaStruct (*.mat)'}, 'Sauvegarder les données utilisateur', app.DM.UserFile);
            if isequal(f, 0)
                return
            end
            app.saveUserData(fullfile(p, f));
        end

        function loadDialog(app)
            [f, p] = uigetfile({'*.mat', 'Données MecaStruct (*.mat)'}, 'Charger des données utilisateur');
            if isequal(f, 0)
                return
            end
            app.loadUserData(fullfile(p, f));
        end

        %% ------------------------------------ Sections --------------------------------------
        function buildSectionsTab(app)
            W = app.makeWork(app.Tabs.Sec, 330, 'Sec', ...
                {'Section', [1 1], ''; 'Contraintes σ(y) et τ(y)', [1 2], ''}, ...
                {'Comp', 'Comparaison des méthodes'; 'Huyg', 'Tableau de Huygens'});
            g = W.In;
            S = struct('W', W);
            types = GeometryEngine.sectionTypes();
            types = types(~strcmp({types.type}, 'composite'));
            app.addRow(g, '1. Géométrie (dimensions en mm)', 'title');
            S.type = app.addRow(g, 'Type de section', 'drop', {types.label}, {types.type});
            S.type.ValueChangedFcn = app.cbk(@() app.onSectionType(), 'Sections');
            dims = {'b', 'b — largeur selon z (mm)'; 'h', 'h — hauteur selon y (mm)'; 'D', 'D — diamètre extérieur (mm)'; ...
                'd', 'd — diamètre intérieur (mm)'; 'B', 'B — largeur (mm)'; 'H', 'H — hauteur (mm)'; ...
                't', 't — épaisseur (mm)'; 'tw', 'tw = a — âme (mm)'; 'tf', 'tf = e — aile (mm)'};
            for k = 1:size(dims, 1)
                S.(dims{k, 1}) = app.addRow(g, dims{k, 2}, 'num');
                S.(dims{k, 1}).Limits = [0 Inf];
            end
            S.fam = app.addRow(g, 'Famille de profilé', 'drop', cellstr(app.DM.listProfileFamilies()));
            S.fam.ValueChangedFcn = app.cbk(@() app.onFamilyChange('Sec'), 'Sections');
            S.prof = app.addRow(g, 'Profilé du catalogue', 'drop', {'-'});
            presets = DataManager.sectionPresets();
            S.preset = app.addRow(g, 'Tube ou cornière courant', 'drop', {presets.name});
            S.preset.Tag = 'MSv2';   % champ ajouté après la première version des fichiers de problème
            S.preset.Tooltip = 'Dimensions nominales de tubes carrés / rectangulaires, ronds et de cornières égales. Congés et arrondis ignorés : écart de quelques % avec les tables.';
            app.addRow(g, 'Remplir les dimensions du tube ou de la cornière', 'button', app.cbk(@() app.applySectionPreset(), 'Sections'));
            S.mode = app.addRow(g, 'Méthode intégrale', 'drop', {'symbolique (int)', 'numérique (integral2)'}, {'symbolique', 'numerique'});
            S.mat = app.addRow(g, 'Matériau', 'drop', cellstr(app.DM.listMaterials()));
            app.addRow(g, '2. Efforts pour σ(y) et τ(y) (facultatif)', 'title');
            app.addRow(g, MecaStruct_App.effortHelp(), 'note', 150);
            S.N = app.addRow(g, 'N : traction > 0 (kN)', 'num');
            S.Mfz = app.addRow(g, 'Mfz : plan (x,y) (kN·m)', 'num');
            S.Mfy = app.addRow(g, 'Mfy : plan (x,z) (kN·m)', 'num');
            S.Ty = app.addRow(g, 'Ty : tranchant en y (kN)', 'num');
            S.N.Tooltip = 'Effort normal : positif en traction, négatif en compression.';
            S.Mfz.Tooltip = 'Moment de flexion autour de z. Mfz > 0 : fibres du haut (y > 0) comprimées, fibres du bas tendues.';
            S.Mfy.Tooltip = 'Moment de flexion autour de y. Mfy > 0 : fibres z > 0 tendues.';
            S.Ty.Tooltip = 'Effort tranchant selon y (pour la répartition de Jourawski).';
            app.addRow(g, '… ou reprendre les efforts de la poutre calculée', 'title');
            S.s0 = app.addRow(g, 's sur la poutre (m)', 'num');
            S.s0.Tooltip = 'Abscisse de la coupure dans l''onglet Poutres (de 0 à L).';
            hb = app.addRow(g, '', 'buttons', {'Efforts en s', app.cbk(@() app.loadFromBeam('Sec', 'abscisse'), 'Sections'), ...
                'Efforts au point critique', app.cbk(@() app.loadFromBeam('Sec', 'max'), 'Sections')});
            hb(1).Tooltip = 'Remplit N, Mfz, Mfy, Ty avec les efforts de la poutre à l''abscisse s.';
            hb(2).Tooltip = 'Remplit N, Mfz, Mfy, Ty avec les efforts de la section la plus sollicitée de la poutre.';
            S.Kt = app.addRow(g, 'Kt (-)', 'num');
            app.addRow(g, '3. Calcul et transfert', 'title');
            S.btnCalc = app.addRow(g, 'Calculer la section', 'button', app.cbk(@() app.computeSection(), 'Sections'));
            hu = app.addRow(g, 'Envoyer vers Poutres et Flambage →', 'button', app.cbk(@() app.useSectionForBeam(), 'Sections'));
            hu.Tooltip = 'Recalcule puis recopie S, Iz, Iy, Ix, Iyz, ky, kz, fibres extrêmes et matériau dans Poutres et Flambage.';
            hr = app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Sections'), 'Sections'));
            hr.Tooltip = 'Remet les dimensions et efforts de l''exemple de l''onglet.';
            app.addRow(g, ['Repère O1 au coin bas-gauche, z horizontal, y vertical. Méthode A : formules fermées + ' ...
                'Huygens ; méthode B : intégrales doubles ; tabulée : catalogue (profilés).'], 'note', 64);
            app.H.Sec = S;
        end

        function onSectionType(app)
            S = app.H.Sec;
            ty = S.type.Value;
            rel = MecaStruct_App.relevantDims(ty);
            for f = {'b', 'h', 'D', 'd', 'B', 'H', 't', 'tw', 'tf'}
                S.(f{1}).Enable = MecaStruct_App.onOff(any(strcmp(f{1}, rel)));
            end
            isP = strcmp(ty, 'profile');
            S.fam.Enable = MecaStruct_App.onOff(isP);
            S.prof.Enable = MecaStruct_App.onOff(isP);
        end

        function onFamilyChange(app, key)
            X = app.H.(key);
            items = cellstr(app.DM.listProfiles(X.fam.Value));
            old = X.prof.Value;
            X.prof.Items = items;
            if any(strcmp(old, items))
                X.prof.Value = old;
            end
        end

        function sec = buildSection(app)
            % Section courante de l'onglet Sections (SI).
            S = app.H.Sec;
            ty = S.type.Value;
            if strcmp(ty, 'profile')
                sec = GeometryEngine.fromProfile(app.DM.getProfile(S.fam.Value, S.prof.Value));
            else
                sec = struct('type', ty);
                rel = MecaStruct_App.relevantDims(ty);
                for k = 1:numel(rel)
                    sec.(rel{k}) = app.si(S.(rel{k}), 'mm');
                end
                sec = GeometryEngine.validateSection(sec);
            end
        end

        %% ------------------------------------- Poutres ---------------------------------------
        function buildBeamTab(app)
            W = app.makeWork(app.Tabs.Beam, 470, 'Beam', ...
                {'Schéma', [1 1], 'equilibre'; 'Diagrammes', [6 1], 'cohesion'; 'Déformée α(s), v(s)', [2 1], 'deformee'; ...
                'Équations par tronçon', [1 1], 'cohesion'; 'Charge mobile', [2 1], 'cohesion'}, ...
                {'Reac', 'Réactions'; 'Eq', 'Équations (texte, SI)'; 'Defl', 'Flèche : 4 méthodes'; ...
                'Energy', 'Énergie'; 'Check', 'Vérification'; 'Combo', 'Combinaisons'; 'Mov', 'Charge mobile'; ...
                'Prof', 'Profilés'; 'EC3', 'Eurocode 3'; 'Fat', 'Fatigue'});
            W.PlotGroup.SelectionChangedFcn = @(~, ~) app.safeRun(@() app.updateFormula(), 'Formulaire');
            g = W.In;
            B = struct('W', W);
            hu = app.addRow(g, '', 'buttons', {'↶ Annuler', app.cbk(@() app.undoBeam(-1), 'Annuler'), ...
                '↷ Rétablir', app.cbk(@() app.undoBeam(1), 'Rétablir')});
            hu(1).Tooltip = 'Annule la dernière modification de la saisie (champs et tableaux de cet onglet).';
            hu(2).Tooltip = 'Rétablit la modification annulée.';
            app.addRow(g, '', 'buttons', {'Enregistrer mon problème', app.cbk(@() app.saveProblem('Beam'), 'Enregistrement'), ...
                'Ouvrir un problème', app.cbk(@() app.loadProblem('Beam'), 'Ouverture')});
            app.addRow(g, 'Exemples', 'title');
            B.example =app.addRow(g, 'Exemple d''école', 'drop', {'Appui-appui : charge uniforme + force', ...
                'Encastrée-appuyée : charge uniforme (hyperstatique)', 'Console : force en bout', ...
                'Deux travées égales : charge uniforme', 'Poutre Gerber : rotule dans la première travée', ...
                'Deux travées : tassement de 10 mm de l''appui B'}, ...
                {'isostatique', 'hyperstatique', 'console', 'deuxtravees', 'gerber', 'tassement'});
            app.addRow(g, 'Charger l''exemple', 'button', app.cbk(@() app.loadExample('Poutres', app.H.Beam.example.Value), 'Poutres'));
            app.addRow(g, 'Poutre et matériau', 'title');
            B.L = app.addRow(g, 'Longueur L (m)', 'num');
            B.L.Limits = [0 Inf];
            B.mat = app.addRow(g, 'Matériau', 'drop', cellstr(app.DM.listMaterials()));
            B.E = app.addRow(g, 'E (GPa)', 'num');
            B.G = app.addRow(g, 'G (GPa)', 'num');
            B.Re = app.addRow(g, 'Re (MPa)', 'num');
            app.addRow(g, 'Section', 'title');
            B.secInfo = app.addRow(g, '', 'note', 40);
            B.secInfo.FontAngle = 'normal';
            B.secInfo.FontWeight = 'bold';
            B.S = app.addRow(g, 'S (mm²)', 'num');
            B.Iz = app.addRow(g, 'Iz — flexion (x,y) (mm⁴)', 'num');
            B.Iy = app.addRow(g, 'Iy — flexion (x,z) (mm⁴)', 'num');
            B.Ix = app.addRow(g, 'Ix — constante de torsion (mm⁴)', 'num');
            B.Iyz = app.addRow(g, 'Iyz — produit d''inertie (mm⁴, 0 si axes principaux)', 'num');
            B.ky = app.addRow(g, 'ky — section réduite, tranchant Ty (-)', 'num');
            B.kz = app.addRow(g, 'kz — section réduite, tranchant Tz (-)', 'num');
            B.vy = app.addRow(g, 'Fibre extrême |y|max (mm)', 'num');
            B.vz = app.addRow(g, 'Fibre extrême |z|max (mm)', 'num');
            for f = {'S', 'Iz', 'Iy', 'Ix', 'Iyz', 'ky', 'kz', 'vy', 'vz'}
                B.(f{1}).ValueChangedFcn = @(~, ~) app.markBeamManual();
            end
            tips = {'L', 'Longueur de la poutre entre ses deux extrémités, en mètres.'
                'E', 'Module d''Young : rigidité du matériau (acier ≈ 190–210 GPa).'
                'G', 'Module de cisaillement : G = E / (2(1+ν)).'
                'Re', 'Limite élastique : contrainte au-delà de laquelle le matériau se déforme définitivement.'
                'S', 'Aire de la section droite.'
                'Iz', 'Moment quadratique pour la flexion dans le plan (x,y), charges verticales.'
                'Iy', 'Moment quadratique pour la flexion dans le plan (x,z), charges horizontales.'
                'Ix', 'Constante de torsion (moment quadratique polaire pour un arbre rond).'
                'Iyz', 'Produit d''inertie : 0 si y et z sont les axes principaux (cas courant).'
                'ky', 'Section réduite : le cisaillement est repris par S/ky ; 1 par défaut.'
                'kz', 'Section réduite : le cisaillement est repris par S/kz ; 1 par défaut.'
                'vy', 'Distance du centre de gravité à la fibre la plus éloignée selon y.'
                'vz', 'Distance du centre de gravité à la fibre la plus éloignée selon z.'
                's', 'Coefficient de sécurité : on exige σ ≤ Re / s (typiquement 1,5 à 3).'
                'Kt', 'Coefficient de concentration de contrainte (1 si aucun trou ni épaulement).'};
            B.tips = tips;
            hb = app.addRow(g, '', 'buttons', {'← Importer depuis Sections', app.cbk(@() app.useSectionForBeam(), 'Poutres'), ...
                'Voir la section', app.cbk(@() app.showBeamSection(), 'Poutres')});
            hb(1).Tooltip = 'Recopie S, Iz, Iy, Ix, Iyz, ky, kz, fibres extrêmes et matériau depuis l''onglet Sections.';
            hb(2).Tooltip = 'Dessine la section utilisée par la poutre (contour, centre de gravité, axes).';
            app.addRow(g, 'Appuis', 'title');
            B.sup = app.addRow(g, '', 'table', 110, {'Position (m)', 'Type', 'Nom'}, {'numeric', app.SupportTypes, 'char'});
            app.addRow(g, '', 'buttons', {'Ajouter un appui', app.cbk(@() app.addTableRow(app.H.Beam.sup, {0, 'appui_simple', ''}), 'Poutres'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Beam.sup), 'Poutres')});
            app.addRow(g, ['Ce que bloque chaque appui : appui_simple et pivot_glissant = déplacements transversaux y et z ' ...
                '(la poutre glisse selon x) ; rotule et pivot = x, y et z (rotations libres) ; ' ...
                'encastrement = tout (déplacements et rotations).'], 'note', 62);
            app.addRow(g, 'Ressorts, tassements, rotules, température', 'title', 'closed');
            app.addRow(g, ['Ressort : appui élastique de raideur k (0 = appui rigide), le déplacement vaut −R/k. Tassement : déplacement imposé de l''appui ' ...
                '(mm, > 0 dans le sens de l''axe, y > 0 vers le haut). L''appui est désigné par son nom (colonne Nom du tableau Appuis).'], 'note', 62);
            B.supx = app.addRow(g, '', 'table', 90, {'Appui (nom)', 'Ressort k (kN/m)', 'Tassement x (mm)', 'Tassement y (mm)', 'Tassement z (mm)'}, ...
                {'char', 'numeric', 'numeric', 'numeric', 'numeric'});
            app.addRow(g, '', 'buttons', {'Ajouter une ligne', app.cbk(@() app.addTableRow(app.H.Beam.supx, {'A', 0, 0, 0, 0}), 'Poutres'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Beam.supx), 'Poutres')});
            app.addRow(g, ['Rotule intermédiaire : le moment de flexion y est nul au point choisi (poutre Gerber) ; la pente y est discontinue. ' ...
                'Pas sur un appui.'], 'note', 40);
            B.hg = app.addRow(g, '', 'table', 70, {'Position (m)', 'Nom'}, {'numeric', 'char'});
            app.addRow(g, '', 'buttons', {'Ajouter une rotule', app.cbk(@() app.addTableRow(app.H.Beam.hg, {1, ''}), 'Poutres'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Beam.hg), 'Poutres')});
            app.addRow(g, ['Température : α vient du matériau. ΔT uniforme : allongement α·ΔT (efforts si la poutre est empêchée de s''allonger). ' ...
                'Gradient : T(face +y) − T(face −y), la hauteur est 2·|y|max (idem z) ; fibre chaude en haut : la poutre se cambre.'], 'note', 62);
            B.thDT = app.addRow(g, 'ΔT uniforme (°C)', 'num');
            B.thGy = app.addRow(g, 'Gradient selon y : T(+y) − T(−y) (°C)', 'num');
            B.thGz = app.addRow(g, 'Gradient selon z : T(+z) − T(−z) (°C)', 'num');
            for f = {'supx', 'hg', 'thDT', 'thGy', 'thGz'}
                B.(f{1}).Tag = 'MSv2';   % champs ajoutés après la première version des fichiers de problème
            end
            app.addRow(g, 'Forces ponctuelles (composantes globales)', 'title');
            app.addRow(g, 'Signes : Fy < 0 = force vers le bas ; Fx > 0 = dans le sens de x (vers la droite) ; Mz > 0 = sens trigonométrique (axes directs).', 'note', 40);
            B.pl = app.addRow(g, '', 'table', 110, {'Position (m)', 'Fx (kN)', 'Fy (kN)', 'Fz (kN)', 'Nom', 'Cas'}, ...
                {'numeric', 'numeric', 'numeric', 'numeric', 'char', app.LoadCases});
            app.addRow(g, '', 'buttons', {'Ajouter une force', app.cbk(@() app.addTableRow(app.H.Beam.pl, {0, 0, -10, 0, '', 'G'}), 'Poutres'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Beam.pl), 'Poutres')});
            app.addRow(g, 'Couples ponctuels', 'title');
            B.pm = app.addRow(g, '', 'table', 90, {'Position (m)', 'Mx (kN·m)', 'My (kN·m)', 'Mz (kN·m)', 'Nom', 'Cas'}, ...
                {'numeric', 'numeric', 'numeric', 'numeric', 'char', app.LoadCases});
            app.addRow(g, '', 'buttons', {'Ajouter un couple', app.cbk(@() app.addTableRow(app.H.Beam.pm, {0, 0, 0, 1, '', 'G'}), 'Poutres'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Beam.pm), 'Poutres')});
            app.addRow(g, 'Charges réparties', 'title');
            B.dl = app.addRow(g, '', 'table', 110, {'a (m)', 'b (m)', 'Dir.', 'Type', 'Valeurs (kN/m)', 'Nom', 'Cas'}, ...
                {'numeric', 'numeric', {'x', 'y', 'z'}, {'uniforme', 'linéaire', 'polynomiale'}, 'char', 'char', app.LoadCases});
            app.addRow(g, '', 'buttons', {'Ajouter une charge', app.cbk(@() app.addTableRow(app.H.Beam.dl, {0, 1, 'y', 'uniforme', '-10', '', 'G'}), 'Poutres'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Beam.dl), 'Poutres')});
            app.addRow(g, 'Charge rapide (ajoute une ligne au tableau ci-dessus)', 'title', 'closed');
            B.qshape = app.addRow(g, 'Forme', 'drop', {'Uniforme', 'Triangulaire croissante (0 → p)', ...
                'Triangulaire décroissante (p → 0)', 'Trapèze (p1 → p2)'});
            B.qdir = app.addRow(g, 'Direction', 'drop', {'x', 'y', 'z'});
            B.qdir.Value = 'y';
            B.qcase = app.addRow(g, 'Cas de charge', 'drop', app.LoadCases);
            B.qa = app.addRow(g, 'Début a (m)', 'num');
            B.qb = app.addRow(g, 'Fin b (m)', 'num');
            B.qb.Value = 1;
            B.qp1 = app.addRow(g, 'p ou p1 (kN/m, < 0 : vers le bas)', 'num');
            B.qp1.Value = -10;
            B.qp2 = app.addRow(g, 'p2 (kN/m, trapèze seulement)', 'num');
            app.addRow(g, 'Ajouter cette charge', 'button', app.cbk(@() app.addQuickLoad(), 'Charge rapide'));
            app.addRow(g, ['Valeurs : uniforme « p0 » ; linéaire « p1 p2 » (de a à b) ; polynomiale : coefficients ' ...
                'en ξ = s − a, ordre décroissant (kN/m, kN/m², ...). py < 0 : charge descendante.'], 'note', 50);
            app.addRow(g, 'Calcul et affichage', 'title');
            B.comps = app.addRow(g, 'Diagrammes', 'checks', app.Comps);
            B.plane = app.addRow(g, 'Plan de la déformée', 'drop', {'(x,y) : v, Mfz, Iz', '(x,z) : w, Mfy, Iy'}, {'xy', 'xz'});
            B.shear = app.addRow(g, 'Tranchant dans Castigliano', 'check');
            B.selfw = app.addRow(g, 'Poids propre (ρ·S·g, cas G)', 'check');
            B.selfw.Tooltip = 'Ajoute une charge répartie descendante ρ·S·g sur toute la poutre (ρ du matériau choisi).';
            app.addRow(g, 'Combinaisons de cas (G permanentes, Q exploitation, W vent, S neige)', 'title', 'closed');
            app.addRow(g, ['Chaque charge porte un cas (colonne Cas). « Calculer » additionne tous les cas avec le coefficient 1. ' ...
                '« Calculer les combinaisons » résout chaque ligne avec ses coefficients puis donne l''enveloppe (onglet Combinaisons).'], 'note', 62);
            B.combo = app.addRow(g, '', 'table', 90, {'Combinaison', 'γG', 'γQ', 'γW', 'γS'}, ...
                {'char', 'numeric', 'numeric', 'numeric', 'numeric'});
            app.addRow(g, '', 'buttons', {'Ajouter une combinaison', app.cbk(@() app.addTableRow(app.H.Beam.combo, {'Nouvelle', 1, 1, 0, 0}), 'Poutres'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Beam.combo), 'Poutres')});
            app.addRow(g, 'Calculer les combinaisons', 'button', app.cbk(@() app.computeCombinations(), 'Combinaisons'));
            app.addRow(g, 'Charge mobile (convoi d''essieux, enveloppe)', 'title', 'closed');
            app.addRow(g, ['Un convoi d''essieux verticaux (Fy) traverse la poutre. La poutre est résolue pour chaque position, puis l''enveloppe de Mfz, Ty ' ...
                'et des réactions est tracée (onglet graphique « Charge mobile » et tableau). Essieux de gauche à droite, F < 0 = vers le bas.'], 'note', 62);
            B.mvP = app.addRow(g, 'Essieux (kN, de gauche à droite)', 'text');
            B.mvP.Value = '-100';
            B.mvE = app.addRow(g, 'Écartement(s) entre essieux (m)', 'text');
            B.mvE.Value = '1.5';
            B.mvN = app.addRow(g, 'Positions de base du convoi (+ positions critiques)', 'num');
            B.mvN.Value = 61;
            B.mvFixed = app.addRow(g, 'Ajouter les charges fixes saisies', 'check');
            app.addRow(g, 'Calculer l''enveloppe de la charge mobile', 'button', app.cbk(@() app.computeMovingLoad(), 'Charge mobile'));
            for f = {'mvP', 'mvE', 'mvN', 'mvFixed'}
                B.(f{1}).Tag = 'MSv2';
            end
            app.addRow(g, 'Dimensionnement : profilé le plus léger', 'title', 'closed');
            B.pfam = app.addRow(g, 'Famille de profilés', 'drop', {'IPE', 'HEA', 'HEB', 'IPN', 'UPN', 'UAP'});
            B.pdef = app.addRow(g, 'Flèche max L / … (0 = ignorée)', 'num');
            B.pdef.Tooltip = 'Exemple : 300 impose f ≤ L/300. En plus de la condition de résistance Kt·σ ≤ Re/s.';
            app.addRow(g, 'Chercher le profilé le plus léger', 'button', ...
                app.cbk(@() app.findLightestProfile(app.H.Beam.pfam.Value, app.H.Beam.pdef.Value), 'Dimensionnement'));
            app.addRow(g, 'Eurocode 3 simplifié (flexion + tranchant)', 'title', 'closed');
            app.addRow(g, ['Profilés IPE, HEA, HEB, IPN et sections en I, classes 1 à 3, fy = Re : flexion, tranchant, voilement de l''âme par ' ...
                'cisaillement, déversement, flambement et interaction N + M (6.3.3, flexion autour de l''axe fort). Utiliser l''enveloppe d''une ' ...
                'combinaison ELU (γG = 1,35, γQ = 1,5).'], 'note', 62);
            B.na = app.addRow(g, 'Annexe nationale', 'drop', {'Valeurs recommandées de l''EN', 'France (NF EN 1993-1-1/NA)', 'Autre : saisir γM0 et γM1'}, ...
                {'EN', 'FR', 'autre'});
            B.na.Tooltip = 'La France retient γM0 = γM1 = 1,0 et γM2 = 1,25 : mêmes valeurs que l''EN. Pour un autre pays, saisir ses valeurs.';
            B.na.ValueChangedFcn = @(~, ~) app.applyNationalAnnex();
            B.gM0 = app.addRow(g, 'γM0 (-), résistance des sections', 'num');
            B.gM1 = app.addRow(g, 'γM1 (-), stabilité (déversement)', 'num');
            B.Cmy = app.addRow(g, 'Cmy (-), moment équivalent, flambement (1 = prudent)', 'num');
            B.CmLT = app.addRow(g, 'CmLT (-), moment équivalent, déversement (1 = prudent)', 'num');
            B.Cmy.Tooltip = 'Tableau B.3 de l''EN 1993-1-1 : 0,6 + 0,4ψ (moment linéaire, ψ = rapport des moments d''extrémité), 0,95 à 0,9 (charge répartie). Entre 0,4 et 1.';
            B.CmLT.Tooltip = 'Idem pour le déversement. Entre 0,4 et 1 ; 1 est toujours du côté de la sécurité.';
            for f = {'na', 'Cmy', 'CmLT'}
                B.(f{1}).Tag = 'MSv2';
            end
            B.Lcr = app.addRow(g, 'Lcr : longueur entre maintiens latéraux (m, 0 = L)', 'num');
            B.LcrF = app.addRow(g, 'Lcr,y : longueur de flambement dans le plan fort (m, 0 = L)', 'num');
            B.LcrF.Tooltip = 'Flambement autour de l''axe fort (y-y) : les entretoises latérales n''y changent rien. Par défaut (0), la longueur de la poutre.';
            B.LcrF.Tag = 'MSv2';   % champ ajouté après la première version des fichiers de problème
            B.C1 = app.addRow(g, 'C1 : forme du moment (1 = uniforme, prudent)', 'num');
            B.C1.Tooltip = 'NCCI SN003 : 1,13 pour une charge uniforme sur appuis simples ; 1,35 pour une charge ponctuelle centrée ; 1,77 pour des moments d''extrémité ψ = 0.';
            B.ecsrc = app.addRow(g, 'Efforts de calcul', 'drop', {'Dernier « Calculer »', 'Enveloppe des combinaisons'}, ...
                {'courant', 'enveloppe'});
            app.addRow(g, 'Vérifier selon l''Eurocode 3', 'button', app.cbk(@() app.checkEurocode(), 'Eurocode 3'));
            app.addRow(g, 'Fatigue (Goodman)', 'title', 'closed');
            B.fR = app.addRow(g, 'R = σmin / σmax (-1 alterné, 0 répété)', 'num');
            B.fka = app.addRow(g, 'ka : état de surface (-)', 'num');
            B.fkb = app.addRow(g, 'kb : effet de taille (-)', 'num');
            B.fka.Tooltip = 'Poli 1 ; usiné 0,7 à 0,9 ; laminé 0,6 à 0,8 ; brut de forge 0,4 à 0,6 (acier).';
            B.fkb.Tooltip = 'Petite pièce (d ≤ 8 mm) 1 ; 0,85 à 0,9 pour 10 à 50 mm ; 0,7 à 0,8 au-delà.';
            app.addRow(g, 'Vérifier la fatigue', 'button', app.cbk(@() app.checkFatigue(), 'Fatigue'));
            app.addRow(g, 'Sécurité et calcul', 'title');
            B.s = app.addRow(g, 'Coefficient de sécurité s (-)', 'num');
            B.Kt = app.addRow(g, 'Kt (-)', 'num');
            B.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeBeam(true), 'Poutres'));
            app.addRow(g, 'Envoyer au tenseur (point le plus sollicité)', 'button', app.cbk(@() app.sendToTensor(), 'Poutres'));
            for k = 1:size(B.tips, 1)
                B.(B.tips{k, 1}).Tooltip = B.tips{k, 2};
            end
            B = rmfield(B, 'tips');
            app.H.Beam = B;
            app.hookBeamHistory();
        end

        function hookBeamHistory(app)
            % Chaque modification d'un champ ou d'un tableau de Poutres crée une entrée d'historique (annuler / rétablir) et redessine l'aperçu.
            items = MecaStruct_App.inputWidgets(app.H.Beam.W.In);
            for k = 1:numel(items)
                w = items(k);
                if isa(w, 'matlab.ui.control.Table')
                    w.CellEditCallback = @(~, ~) app.pushBeamHistory();
                elseif isprop(w, 'ValueChangedFcn')
                    orig = w.ValueChangedFcn;
                    if iscell(orig) && ~isempty(orig)
                        c = orig;
                        orig = @(s, e) c{1}(s, e, c{2:end});
                    end
                    w.ValueChangedFcn = @(s, e) app.chainEdit(orig, s, e);
                end
            end
        end

        function markBeamManual(app)
            app.BeamUsesSection = false;
            app.BeamSection = [];
            app.H.Beam.secInfo.Text = 'Section utilisée : valeurs saisies à la main (aucune forme associée).';
        end

        function loadBeamExample(app, variant)
            B = app.H.Beam;
            if ~any(strcmp(variant, {'isostatique', 'hyperstatique', 'console', 'deuxtravees', 'gerber', 'tassement'}))
                variant = 'isostatique';
            end
            B.example.Value = variant;
            B.mat.Value = app.pickItem(B.mat, 'S235');
            app.applyMaterial('Beam');
            p = app.DM.getProfile('IPE', 'IPE 300');
            P = GeometryEngine.analytical(GeometryEngine.fromProfile(p));
            Pt = GeometryEngine.tabulated(GeometryEngine.fromProfile(p));
            P.ky = Pt.ky;   % ky·S = aire d'âme avec la surface du catalogue
            P.kz = Pt.kz;
            B.S.Value = p.S * 1e6;
            B.Iz.Value = p.Iz * 1e12;
            B.Iy.Value = p.Iy * 1e12;
            B.Ix.Value = P.J * 1e12;
            B.ky.Value = P.ky;
            B.kz.Value = P.kz;
            B.Iyz.Value = 0;
            B.vy.Value = p.h / 2 * 1e3;
            B.vz.Value = p.b / 2 * 1e3;
            app.BeamUsesSection = false;
            app.BeamSection = struct('sec', GeometryEngine.fromProfile(p), 'P', P, 'mat', B.mat.Value);
            B.secInfo.Text = 'Section utilisée : profilé IPE 300 (exemple, valeurs du catalogue).';
            B.pm.Data = cell(0, 6);
            B.supx.Data = cell(0, 5);
            B.hg.Data = cell(0, 2);
            B.thDT.Value = 0;
            B.thGy.Value = 0;
            B.thGz.Value = 0;
            B.selfw.Value = false;
            B.na.Value = 'EN';
            B.gM0.Value = 1;
            B.gM1.Value = 1;
            B.Cmy.Value = 1;
            B.CmLT.Value = 1;
            B.Lcr.Value = 0;
            B.LcrF.Value = 0;
            B.C1.Value = 1;
            B.ecsrc.Value = 'courant';
            B.mvP.Value = '-100';
            B.mvE.Value = '1.5';
            B.mvN.Value = 61;
            B.mvFixed.Value = false;
            B.fR.Value = 0;
            B.fka.Value = 1;
            B.fkb.Value = 1;
            B.combo.Data = {'ELS', 1, 1, 0, 0; 'ELU', 1.35, 1.5, 0, 0};
            switch variant
                case 'hyperstatique'
                    B.L.Value = 5;
                    B.sup.Data = {0, 'encastrement', 'A'; 5, 'appui_simple', 'B'};
                    B.pl.Data = cell(0, 6);
                    B.dl.Data = {0, 5, 'y', 'uniforme', '-10', 'q', 'G'};
                case 'console'
                    B.L.Value = 3;
                    B.sup.Data = {0, 'encastrement', 'A'};
                    B.pl.Data = {3, 0, -10, 0, 'F', 'Q'};
                    B.dl.Data = cell(0, 7);
                case 'deuxtravees'
                    B.L.Value = 8;
                    B.sup.Data = {0, 'pivot', 'A'; 4, 'appui_simple', 'B'; 8, 'appui_simple', 'C'};
                    B.pl.Data = cell(0, 6);
                    B.dl.Data = {0, 8, 'y', 'uniforme', '-10', 'q', 'G'};
                case 'gerber'
                    B.L.Value = 8;
                    B.sup.Data = {0, 'pivot', 'A'; 4, 'appui_simple', 'B'; 8, 'appui_simple', 'C'};
                    B.hg.Data = {2, 'R1'};
                    B.pl.Data = cell(0, 6);
                    B.dl.Data = {0, 8, 'y', 'uniforme', '-10', 'q', 'G'};
                case 'tassement'
                    B.L.Value = 8;
                    B.sup.Data = {0, 'pivot', 'A'; 4, 'appui_simple', 'B'; 8, 'appui_simple', 'C'};
                    B.supx.Data = {'B', 0, 0, -10, 0};
                    B.pl.Data = cell(0, 6);
                    B.dl.Data = {0, 8, 'y', 'uniforme', '-10', 'q', 'G'};
                otherwise
                    B.L.Value = 6;
                    B.sup.Data = {0, 'pivot', 'A'; 6, 'appui_simple', 'B'};
                    B.pl.Data = {2, 0, -20, 0, 'F', 'Q'};
                    B.dl.Data = {0, 6, 'y', 'uniforme', '-10', 'q', 'G'};
            end
            vals = [false true false false false true];
            for k = 1:numel(B.comps)
                B.comps(k).Value = vals(k);
            end
            B.plane.Value = 'xy';
            B.shear.Value = true;
            B.s.Value = 1.5;
            B.Kt.Value = 1;
            app.resetBeamHistory();
        end

        function model = readBeamModel(app, fac)
            % Modèle de poutre SI à partir des champs et des tables.
            %   fac : coefficient de chaque cas (struct G, Q, W, S) ; défaut 1 partout. Un cas à 0 est omis.
            B = app.H.Beam;
            if nargin < 2
                fac = struct('G', 1, 'Q', 1, 'W', 1, 'S', 1);
            end
            kc = @(d, i, col) MecaStruct_App.caseFactor(fac, d, i, col);
            model = struct();
            model.L = B.L.Value;
            if ~(model.L > 0)
                error('MecaStruct:App:invalidInput', 'La longueur L doit être strictement positive.');
            end
            model.E = app.si(B.E, 'GPa');
            model.G = app.si(B.G, 'GPa');
            model.S = app.si(B.S, 'mm^2');
            model.Iz = app.si(B.Iz, 'mm^4');
            model.Iy = app.si(B.Iy, 'mm^4');
            model.Ix = app.si(B.Ix, 'mm^4');
            model.ky = B.ky.Value;
            model.kz = B.kz.Value;
            model.Iyz = app.si(B.Iyz, 'mm^4');
            if model.Iyz^2 >= model.Iz * model.Iy
                error('MecaStruct:App:invalidInput', 'Il faut Iyz² < Iz·Iy (matrice d''inertie définie positive).');
            end
            d = B.sup.Data;
            sup = struct('pos', {}, 'type', {}, 'name', {});
            for i = 1:size(d, 1)
                sup(i).pos = MecaStruct_App.cellNum(d{i, 1}, 'Appui : position');
                sup(i).type = char(d{i, 2});
                sup(i).name = char(string(d{i, 3}));
            end
            for i = 1:numel(sup)
                sup(i).spring = 0; sup(i).dx = 0; sup(i).dy = 0; sup(i).dz = 0;
            end
            d = B.supx.Data;
            for i = 1:size(d, 1)
                j = find(strcmp({sup.name}, char(string(d{i, 1}))), 1);
                if isempty(j)
                    error('MecaStruct:App:invalidInput', 'Ressorts et tassements : aucun appui ne s''appelle « %s ».', char(string(d{i, 1})));
                end
                sup(j).spring = DataManager.toSI(MecaStruct_App.cellNum(d{i, 2}, 'Ressort k'), 'kN/m');
                % tassements et température : actions permanentes, rangées dans le cas G (pondérées par γG dans une combinaison)
                sup(j).dx = fac.G * MecaStruct_App.cellNum(d{i, 3}, 'Tassement x') * 1e-3;
                sup(j).dy = fac.G * MecaStruct_App.cellNum(d{i, 4}, 'Tassement y') * 1e-3;
                sup(j).dz = fac.G * MecaStruct_App.cellNum(d{i, 5}, 'Tassement z') * 1e-3;
            end
            model.supports = sup;
            d = B.hg.Data;
            hg = struct('pos', {}, 'name', {});
            for i = 1:size(d, 1)
                hg(i).pos = MecaStruct_App.cellNum(d{i, 1}, 'Rotule : position');
                hg(i).name = char(string(d{i, 2}));
            end
            model.hinges = hg;
            th = app.beamThermal();
            model.thermal = struct('epsX', fac.G * th.epsX, 'kv', fac.G * th.kv, 'kw', fac.G * th.kw);
            d = B.pl.Data;
            pl = struct('pos', {}, 'Fx', {}, 'Fy', {}, 'Fz', {}, 'name', {});
            for i = 1:size(d, 1)
                k = kc(d, i, 6);
                if k == 0, continue, end
                n = numel(pl) + 1;
                pl(n).pos = MecaStruct_App.cellNum(d{i, 1}, 'Force : position');
                pl(n).Fx = k * DataManager.toSI(MecaStruct_App.cellNum(d{i, 2}, 'Fx'), 'kN');
                pl(n).Fy = k * DataManager.toSI(MecaStruct_App.cellNum(d{i, 3}, 'Fy'), 'kN');
                pl(n).Fz = k * DataManager.toSI(MecaStruct_App.cellNum(d{i, 4}, 'Fz'), 'kN');
                pl(n).name = char(string(d{i, 5}));
            end
            model.pointLoads = pl;
            d = B.pm.Data;
            pm = struct('pos', {}, 'Mx', {}, 'My', {}, 'Mz', {}, 'name', {});
            for i = 1:size(d, 1)
                k = kc(d, i, 6);
                if k == 0, continue, end
                n = numel(pm) + 1;
                pm(n).pos = MecaStruct_App.cellNum(d{i, 1}, 'Couple : position');
                pm(n).Mx = k * DataManager.toSI(MecaStruct_App.cellNum(d{i, 2}, 'Mx'), 'kN.m');
                pm(n).My = k * DataManager.toSI(MecaStruct_App.cellNum(d{i, 3}, 'My'), 'kN.m');
                pm(n).Mz = k * DataManager.toSI(MecaStruct_App.cellNum(d{i, 4}, 'Mz'), 'kN.m');
                pm(n).name = char(string(d{i, 5}));
            end
            model.pointMoments = pm;
            d = B.dl.Data;
            dl = struct('a', {}, 'b', {}, 'dir', {}, 'coeffs', {}, 'name', {});
            for i = 1:size(d, 1)
                k = kc(d, i, 7);
                if k == 0, continue, end
                n = numel(dl) + 1;
                a = MecaStruct_App.cellNum(d{i, 1}, 'Charge répartie : a');
                b = MecaStruct_App.cellNum(d{i, 2}, 'Charge répartie : b');
                dl(n).a = a;
                dl(n).b = b;
                dl(n).dir = char(d{i, 3});
                dl(n).coeffs = k * DataManager.toSI(MecaStruct_App.distCoeffs(d{i, 4}, d{i, 5}, a, b), 'kN/m');
                dl(n).name = char(string(d{i, 6}));
            end
            if B.selfw.Value && fac.G ~= 0
                rho = app.DM.getMaterial(B.mat.Value).rho;
                if ~(isfinite(rho) && rho > 0)
                    error('MecaStruct:App:invalidInput', 'Poids propre : masse volumique inconnue pour « %s ».', B.mat.Value);
                end
                n = numel(dl) + 1;
                dl(n).a = 0;
                dl(n).b = model.L;
                dl(n).dir = 'y';
                dl(n).coeffs = -fac.G * rho * 9.80665 * model.S;
                dl(n).name = 'poids propre';
            end
            model.distLoads = dl;
        end

        function th = beamThermal(app)
            % Action thermique de la poutre : epsX = α·ΔT, courbures kv = −α·Δgy/hy et kw = −α·Δgz/hz (1/m).
            %   v'' thermique = −α·(T(+y) − T(−y))/h : la face chaude s'allonge, la poutre se cambre vers elle.
            B = app.H.Beam;
            th = struct('epsX', 0, 'kv', 0, 'kw', 0);
            if B.thDT.Value == 0 && B.thGy.Value == 0 && B.thGz.Value == 0
                return
            end
            alpha = app.DM.getMaterial(B.mat.Value).alpha;
            if ~(isfinite(alpha) && alpha > 0)
                error('MecaStruct:App:invalidInput', 'Température : coefficient de dilatation inconnu pour « %s ».', B.mat.Value);
            end
            th.epsX = alpha * B.thDT.Value;
            if B.thGy.Value ~= 0
                if ~(B.vy.Value > 0)
                    error('MecaStruct:App:invalidInput', 'Gradient thermique selon y : renseignez la fibre extrême |y|max (hauteur = 2·|y|max).');
                end
                th.kv = -alpha * B.thGy.Value / (2 * B.vy.Value * 1e-3);
            end
            if B.thGz.Value ~= 0
                if ~(B.vz.Value > 0)
                    error('MecaStruct:App:invalidInput', 'Gradient thermique selon z : renseignez la fibre extrême |z|max (hauteur = 2·|z|max).');
                end
                th.kw = -alpha * B.thGz.Value / (2 * B.vz.Value * 1e-3);
            end
        end

        function comps = selectedComps(app, sol)
            cb = app.H.Beam.comps;
            sel = arrayfun(@(c) logical(c.Value), cb);
            comps = app.Comps(sel);
            if isempty(comps)
                for k = 1:numel(app.Comps)
                    c = sol.(app.Comps{k});
                    if any(cellfun(@(v) any(v ~= 0), c.coefs))
                        comps{end + 1} = app.Comps{k}; %#ok<AGROW>
                    end
                end
                if isempty(comps)
                    comps = {'Ty', 'Mfz'};
                end
            end
        end

        function P = beamSectionProps(app)
            % Propriétés de section utilisées pour la vérification (SI).
            if app.BeamUsesSection && ~isempty(app.BeamSection)
                P = app.BeamSection.P;
                return
            end
            B = app.H.Beam;
            vy = app.si(B.vy, 'mm');
            vz = app.si(B.vz, 'mm');
            if ~(vy > 0 && vz > 0)
                error('MecaStruct:App:invalidInput', 'Les distances aux fibres extrêmes |y|max et |z|max doivent être > 0.');
            end
            P = struct('S', app.si(B.S, 'mm^2'), 'Iz', app.si(B.Iz, 'mm^4'), 'Iy', app.si(B.Iy, 'mm^4'), 'Iyz', app.si(B.Iyz, 'mm^4'), ...
                'vyTop', vy, 'vyBot', vy, 'vzRight', vz, 'vzLeft', vz);
        end

        function chk = beamCheck(app, sol)
            % Vérification de résistance au point le plus sollicité (flexion composée/déviée).
            B = app.H.Beam;
            L = sol.model.L;
            s = unique([linspace(0, L, 1201), sol.breaks(:).']);
            ev = @(pp, side) BeamAndTrussSolver.ppEval(pp, s, side);
            N = [ev(sol.N, 'left'), ev(sol.N, 'right')];
            Ty = [ev(sol.Ty, 'left'), ev(sol.Ty, 'right')];
            Tz = [ev(sol.Tz, 'left'), ev(sol.Tz, 'right')];
            Mfz = [ev(sol.Mfz, 'left'), ev(sol.Mfz, 'right')];
            Mfy = [ev(sol.Mfy, 'left'), ev(sol.Mfy, 'right')];
            ss = [s s];
            P = app.beamSectionProps();
            score = abs(N) / P.S + abs(Mfz) * max(P.vyTop, P.vyBot) / P.Iz + abs(Mfy) * max(P.vzRight, P.vzLeft) / P.Iy;
            % le score (somme linéaire des termes) est exact pour un rectangle mais pas pour un disque ni
            % pour Iyz ≠ 0 : on retient les meilleurs candidats et on garde celui dont σ exact est maximal
            [~, ord] = sort(score, 'descend');
            [~, iMz] = max(abs(Mfz));
            [~, iMy] = max(abs(Mfy));
            cand = unique([ord(1:min(10, numel(ord))), iMz, iMy], 'stable');
            useSec = app.BeamUsesSection && ~isempty(app.BeamSection);
            if useSec
                srcTxt = 'section de l''onglet Sections (contour exact)';
            else
                srcTxt = 'section saisie (fibres extrêmes symétriques |y|max, |z|max)';
            end
            best = -Inf;
            for c = cand
                pc = struct('N', N(c), 'Mfz', Mfz(c), 'Mfy', Mfy(c), 'Kt', B.Kt.Value, 'Re', app.si(B.Re, 'MPa'), 's', B.s.Value);
                if useSec
                    pc.sec = app.BeamSection.sec;
                    pc.Pcore = app.BeamSection.P;
                else
                    pc.P = P;
                end
                bc = SolicitationsEngine.bendingStress(pc);
                if bc.sigmaMaxAbs > best * (1 + 1e-12)
                    best = bc.sigmaMaxAbs;
                    i = c;
                    bend = bc;
                end
            end
            if abs(bend.sigmaMaxTraction) >= abs(bend.sigmaMaxCompression)
                sig = bend.sigmaMaxTraction;
                loc = bend.locMaxTraction;
            else
                sig = bend.sigmaMaxCompression;
                loc = bend.locMaxCompression;
            end
            chk = struct('s', ss(i), 'N', N(i), 'Ty', Ty(i), 'Tz', Tz(i), 'Mfz', Mfz(i), 'Mfy', Mfy(i), ...
                'bend', bend, 'sigma', sig, 'loc', loc, 'ok', bend.ok);
            chk.report = [{sprintf(['Point le plus sollicité : s = %.4g m (N = %.5g kN, Mfz = %.5g kN·m, ' ...
                'Mfy = %.5g kN·m) ; %s.'], ss(i), N(i) / 1e3, Mfz(i) / 1e3, Mfy(i) / 1e3, srcTxt)}; bend.report(:)];
        end

        %% ------------------------------------- Treillis ---------------------------------------
        function buildTrussTab(app)
            W = app.makeWork(app.Tabs.Tr, 380, 'Tr', {'Treillis', [1 1], ''}, ...
                {'Bars', 'Barres'; 'Reac', 'Réactions'; 'Disp', 'Déplacements'});
            W.PlotGroup.Parent.RowHeight = {26, '5x', '1x'};   % schéma agrandi, rapport réduit
            g = W.In;
            T = struct('W', W);
            app.addRow(g, '', 'buttons', {'Enregistrer mon problème', app.cbk(@() app.saveProblem('Tr'), 'Enregistrement'), ...
                'Ouvrir un problème', app.cbk(@() app.loadProblem('Tr'), 'Ouverture')});
            app.addRow(g, 'Matériau et section des barres', 'title');
            T.mat =app.addRow(g, 'Matériau', 'drop', cellstr(app.DM.listMaterials()));
            T.E = app.addRow(g, 'E (GPa)', 'num');
            T.S = app.addRow(g, 'S (mm²)', 'num');
            T.scale = app.addRow(g, 'Amplification déformée (0 = auto)', 'num');
            app.addRow(g, 'Nœuds (coordonnées en m)', 'title');
            T.nodes = app.addRow(g, '', 'table', 130, {'Nom', 'x (m)', 'y (m)'}, {'char', 'numeric', 'numeric'});
            app.addRow(g, '', 'buttons', {'Ajouter un nœud', app.cbk(@() app.addTableRow(app.H.Tr.nodes, {'', 0, 0}), 'Treillis'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Tr.nodes), 'Treillis')});
            app.addRow(g, 'Barres (numéros des nœuds)', 'title');
            T.bars = app.addRow(g, '', 'table', 130, {'Nœud i', 'Nœud j'}, {'numeric', 'numeric'});
            app.addRow(g, '', 'buttons', {'Ajouter une barre', app.cbk(@() app.addTableRow(app.H.Tr.bars, {1, 2}), 'Treillis'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Tr.bars), 'Treillis')});
            app.addRow(g, 'Appuis (ddl bloqués)', 'title');
            T.sup = app.addRow(g, '', 'table', 90, {'Nœud', 'Bloqué x', 'Bloqué y'}, {'numeric', 'logical', 'logical'});
            app.addRow(g, '', 'buttons', {'Ajouter un appui', app.cbk(@() app.addTableRow(app.H.Tr.sup, {1, true, true}), 'Treillis'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Tr.sup), 'Treillis')});
            app.addRow(g, 'Charges nodales', 'title');
            T.loads = app.addRow(g, '', 'table', 90, {'Nœud', 'Fx (kN)', 'Fy (kN)'}, {'numeric', 'numeric', 'numeric'});
            app.addRow(g, '', 'buttons', {'Ajouter une charge', app.cbk(@() app.addTableRow(app.H.Tr.loads, {1, 0, -10}), 'Treillis'), ...
                'Supprimer la sélection', app.cbk(@() app.delTableRow(app.H.Tr.loads), 'Treillis')});
            T.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeTruss(), 'Treillis'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Treillis'), 'Treillis'));
            app.H.Tr = T;
        end

        function truss = readTruss(app)
            T = app.H.Tr;
            nd = T.nodes.Data;
            n = size(nd, 1);
            if n < 2
                error('MecaStruct:App:invalidInput', 'Le treillis doit comporter au moins 2 nœuds.');
            end
            X = zeros(n, 2);
            names = cell(n, 1);
            for i = 1:n
                names{i} = strtrim(char(string(nd{i, 1})));
                if isempty(names{i})
                    names{i} = sprintf('N%d', i);
                end
                X(i, 1) = MecaStruct_App.cellNum(nd{i, 2}, 'Nœud : x');
                X(i, 2) = MecaStruct_App.cellNum(nd{i, 3}, 'Nœud : y');
            end
            bd = T.bars.Data;
            bars = zeros(size(bd, 1), 2);
            for i = 1:size(bd, 1)
                bars(i, :) = [MecaStruct_App.nodeIndex(bd{i, 1}, n), MecaStruct_App.nodeIndex(bd{i, 2}, n)];
            end
            sd = T.sup.Data;
            sup = false(n, 2);
            for i = 1:size(sd, 1)
                j = MecaStruct_App.nodeIndex(sd{i, 1}, n);
                sup(j, 1) = sup(j, 1) || logical(sd{i, 2});
                sup(j, 2) = sup(j, 2) || logical(sd{i, 3});
            end
            ld = T.loads.Data;
            loads = zeros(n, 2);
            for i = 1:size(ld, 1)
                j = MecaStruct_App.nodeIndex(ld{i, 1}, n);
                loads(j, :) = loads(j, :) + DataManager.toSI([MecaStruct_App.cellNum(ld{i, 2}, 'Fx'), ...
                    MecaStruct_App.cellNum(ld{i, 3}, 'Fy')], 'kN');
            end
            truss = struct('nodes', X, 'bars', bars, 'E', app.si(T.E, 'GPa'), 'S', app.si(T.S, 'mm^2'), ...
                'supports', sup, 'loads', loads, 'names', {names});
        end

        %% ---------------------------------- Sollicitations ------------------------------------
        function buildSolicitationsTab(app)
            g = uigridlayout(app.Tabs.Sol, [1 1]);
            g.Padding = [0 0 0 0];
            sg = uitabgroup(g, 'SelectionChangedFcn', @(~, ~) app.safeRun(@() app.updateFormula(), 'Formulaire'));
            app.SubSol = sg;
            tTra = uitab(sg, 'Title', 'Traction / Compression', 'UserData', 'traction');
            tCis = uitab(sg, 'Title', 'Cisaillement & Matage', 'UserData', 'cisaillement');
            tTor = uitab(sg, 'Title', 'Torsion', 'UserData', 'torsion');
            tFle = uitab(sg, 'Title', 'Flexion', 'UserData', 'flexion');
            mats = cellstr(app.DM.listMaterials());
            crits = {{'Tresca (τe = Re/2)', 'Von Mises (τe = Re/√3)'}, {'Tresca', 'VonMises'}};

            % --- Traction
            W = app.makeWork(tTra, 340, 'Tra', {'σ(x) le long de la barre', [1 1], ''; 'ΔL : 3 méthodes', [1 1], ''}, {'Syn', 'Synthèse'});
            g = W.In;
            T = struct('W', W, 'Tab', tTra);
            app.addRow(g, 'Barre et chargement', 'title');
            T.N = app.addRow(g, 'N (kN, > 0 traction)', 'num');
            T.S0 = app.addRow(g, 'S0 (mm²)', 'num');
            T.L0 = app.addRow(g, 'L0 (m)', 'num');
            T.mat = app.addRow(g, 'Matériau', 'drop', mats);
            T.E = app.addRow(g, 'E (GPa)', 'num');
            T.nu = app.addRow(g, 'ν (-)', 'num');
            T.alpha = app.addRow(g, 'α (10⁻⁶/°C)', 'num');
            T.Re = app.addRow(g, 'Re (MPa)', 'num');
            T.dT = app.addRow(g, 'ΔT (°C)', 'num');
            T.Kt = app.addRow(g, 'Kt (-)', 'num');
            T.s = app.addRow(g, 'Coefficient de sécurité s (-)', 'num');
            T.dLmax = app.addRow(g, 'ΔL max (mm, 0 = sans limite)', 'num');
            app.addRow(g, 'Section variable', 'title');
            T.varS = app.addRow(g, 'Utiliser S(x)', 'check');
            T.Sexpr = app.addRow(g, 'S(x) (mm², x en m)', 'text');
            app.addRow(g, ['Expression en x (m) donnant S en mm² : nombres, x, pi, sqrt, exp, log, sin, cos, tan, abs, ' ...
                '+ − * / ^. Exemple (barre conique d = 20 → 30 mm) : pi/4*(20 + 10*x)^2.'], 'note', 64);
            T.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeTraction(), 'Traction'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Traction'), 'Traction'));
            app.H.Tra = T;

            % --- Cisaillement & matage
            W = app.makeWork(tCis, 360, 'Cis', {'Section', [1 1], ''; 'τ(y) : Jourawski', [1 1], ''; 'Vérifications', [1 1], ''}, {'Syn', 'Synthèse'});
            g = W.In;
            C = struct('W', W, 'Tab', tCis);
            app.addRow(g, 'Matériau et critère', 'title');
            C.mat = app.addRow(g, 'Matériau', 'drop', mats);
            C.Re = app.addRow(g, 'Re (MPa)', 'num');
            C.G = app.addRow(g, 'G (GPa)', 'num');
            C.crit = app.addRow(g, 'Critère (τe)', 'drop', crits{:});
            C.s = app.addRow(g, 'Coefficient de sécurité s (-)', 'num');
            app.addRow(g, 'Cisaillement simple et Jourawski', 'title');
            C.T = app.addRow(g, 'T (kN)', 'num');
            C.S = app.addRow(g, 'S cisaillée (mm²)', 'num');
            C.k = app.addRow(g, 'k = τmax/τmoy (-)', 'num');
            app.addRow(g, 'Jourawski : section de l''onglet Sections, Ty = T.', 'note', 24);
            app.addRow(g, 'Matage', 'title');
            C.Fm = app.addRow(g, 'F (kN)', 'num');
            C.Sm = app.addRow(g, 'S matée (mm²)', 'num');
            C.PadmSrc = app.addRow(g, 'Table de matage', 'drop', {'-'});
            C.PadmSrc.ValueChangedFcn = app.cbk(@() app.onBearingSelect(), 'Matage');
            C.Padm = app.addRow(g, 'P_adm (MPa)', 'num');
            C.btnCalc = app.addRow(g, 'Calculer cisaillement et matage', 'button', app.cbk(@() app.computeShear(), 'Cisaillement'));
            app.addRow(g, 'Clavette parallèle', 'title');
            C.C = app.addRow(g, 'Couple C (kN·m)', 'num');
            C.Dk = app.addRow(g, 'Diamètre d''arbre D (mm)', 'num');
            C.ak = app.addRow(g, 'Largeur a (mm)', 'num');
            C.bk = app.addRow(g, 'Hauteur b (mm)', 'num');
            C.Lk = app.addRow(g, 'Longueur L (mm, 0 = dimensionner)', 'num');
            C.btnKey = app.addRow(g, 'Calculer la clavette', 'button', app.cbk(@() app.computeKey(), 'Clavette'));
            app.addRow(g, 'Goupille / rivet', 'title');
            C.Fp = app.addRow(g, 'F (kN)', 'num');
            C.dp = app.addRow(g, 'd (mm)', 'num');
            C.ep = app.addRow(g, 'e — épaisseur matée (mm)', 'num');
            C.np = app.addRow(g, 'Sections cisaillées n (-)', 'num');
            C.btnPin = app.addRow(g, 'Calculer la goupille', 'button', app.cbk(@() app.computePin(), 'Goupille'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Cisaillement'), 'Cisaillement'));
            app.H.Cis = C;

            % --- Torsion
            W = app.makeWork(tTor, 330, 'Tor', {'τ(r)', [1 1], ''; 'φ(s)', [1 1], ''}, {'Syn', 'Synthèse'});
            g = W.In;
            T = struct('W', W, 'Tab', tTor);
            app.addRow(g, 'Arbre circulaire', 'title');
            T.Mt = app.addRow(g, 'Mt (kN·m)', 'num');
            T.D = app.addRow(g, 'D (mm)', 'num');
            T.d = app.addRow(g, 'd — alésage (mm, 0 = plein)', 'num');
            T.L = app.addRow(g, 'L (m)', 'num');
            T.mat = app.addRow(g, 'Matériau', 'drop', mats);
            T.G = app.addRow(g, 'G (GPa)', 'num');
            T.Re = app.addRow(g, 'Re (MPa)', 'num');
            T.crit = app.addRow(g, 'Critère (τe)', 'drop', crits{:});
            T.s = app.addRow(g, 'Coefficient de sécurité s (-)', 'num');
            T.Kt = app.addRow(g, 'Kt (-)', 'num');
            T.thetaAdm = app.addRow(g, 'θ admissible (°/m, 0 = sans)', 'num');
            T.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeTorsion(), 'Torsion'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Torsion'), 'Torsion'));
            app.H.Tor = T;

            % --- Flexion
            W = app.makeWork(tFle, 330, 'Fle', {'Section et axe neutre', [1 1], ''; 'σxx(y)', [1 1], ''}, {'Syn', 'Synthèse'});
            g = W.In;
            F = struct('W', W, 'Tab', tFle);
            app.addRow(g, 'Section : celle de l''onglet Sections.', 'note', 24);
            app.addRow(g, 'Efforts dans la section étudiée', 'title');
            app.addRow(g, MecaStruct_App.effortHelp(), 'note', 150);
            F.N = app.addRow(g, 'N : traction > 0 (kN)', 'num');
            F.Mfz = app.addRow(g, 'Mfz : plan (x,y) (kN·m)', 'num');
            F.Mfy = app.addRow(g, 'Mfy : plan (x,z) (kN·m)', 'num');
            F.N.Tooltip = 'Effort normal : positif en traction, négatif en compression.';
            F.Mfz.Tooltip = 'Moment de flexion autour de z (charges dans le plan x,y). Mfz > 0 : fibres du haut (y > 0) comprimées, fibres du bas tendues.';
            F.Mfy.Tooltip = 'Moment de flexion autour de y (charges dans le plan x,z). Mfy > 0 : fibres z > 0 tendues.';
            app.addRow(g, 'Reprendre les efforts de la poutre', 'title');
            F.s0 = app.addRow(g, 's sur la poutre (m)', 'num');
            F.s0.Tooltip = 'Abscisse de la coupure dans l''onglet Poutres (de 0 à L).';
            app.addRow(g, '', 'buttons', {'Efforts en s', app.cbk(@() app.loadFromBeam('Fle', 'abscisse'), 'Flexion'), ...
                'Efforts au point critique', app.cbk(@() app.loadFromBeam('Fle', 'max'), 'Flexion')});
            app.addRow(g, 'Kt, matériau et sécurité', 'title');
            F.Kt = app.addRow(g, 'Kt (-)', 'num');
            F.mat = app.addRow(g, 'Matériau', 'drop', mats);
            F.Re = app.addRow(g, 'Re (MPa)', 'num');
            F.s = app.addRow(g, 'Coefficient de sécurité s (-)', 'num');
            F.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeBending(), 'Flexion'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Flexion'), 'Flexion'));
            app.H.Fle = F;

            for key = {'Tra', 'Cis', 'Tor', 'Fle'}
                k = key{1};
                app.H.(k).mat.ValueChangedFcn = app.cbk(@() app.applyMaterial(k), 'Matériau');
            end
        end

        function p = shearBase(app)
            C = app.H.Cis;
            p = struct('Re', app.si(C.Re, 'MPa'), 'criterion', C.crit.Value, 's', C.s.Value);
        end

        %% ------------------------------------- Flambage ---------------------------------------
        function buildBucklingTab(app)
            W = app.makeWork(app.Tabs.Fla, 340, 'Fla', {'Courbe de stabilité', [1 1], ''; 'Mode propre', [1 1], ''}, {'Syn', 'Synthèse'});
            g = W.In;
            F = struct('W', W);
            app.addRow(g, 'Section', 'title');
            F.secInfo = app.addRow(g, '', 'note', 40);
            F.secInfo.FontAngle = 'normal';
            F.secInfo.FontWeight = 'bold';
            F.fam = app.addRow(g, 'Famille de profilé', 'drop', cellstr(app.DM.listProfileFamilies()));
            F.fam.ValueChangedFcn = app.cbk(@() app.onFamilyChange('Fla'), 'Flambage');
            F.prof = app.addRow(g, 'Profilé', 'drop', {'-'});
            app.addRow(g, 'Charger le profilé', 'button', app.cbk(@() app.loadProfileForBuckling(), 'Flambage'));
            app.addRow(g, '← Importer depuis Sections', 'button', app.cbk(@() app.useSectionForBeam(), 'Flambage'));
            F.S = app.addRow(g, 'S (mm²)', 'num');
            F.Iz = app.addRow(g, 'Iz (mm⁴)', 'num');
            F.Iy = app.addRow(g, 'Iy (mm⁴)', 'num');
            app.addRow(g, 'Poutre comprimée', 'title');
            F.mat = app.addRow(g, 'Matériau', 'drop', cellstr(app.DM.listMaterials()));
            F.E = app.addRow(g, 'E (GPa)', 'num');
            F.Re = app.addRow(g, 'Re (MPa)', 'num');
            F.L = app.addRow(g, 'Longueur L (m)', 'num');
            conds = BucklingEngine.listConditions();
            F.cond = app.addRow(g, 'Conditions aux limites', 'drop', cellstr(conds.Libelle + " (L' = " + conds.CoefficientTexte + " L)"), ...
                cellstr(conds.Condition));
            F.P = app.addRow(g, 'P appliquée (kN, 0 = aucune)', 'num');
            F.s = app.addRow(g, 'Coefficient de sécurité s (-)', 'num');
            F.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeBuckling(), 'Flambage'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Flambage'), 'Flambage'));
            app.H.Fla = F;
            app.H.Fla.mat.ValueChangedFcn = app.cbk(@() app.applyMaterial('Fla'), 'Matériau');
        end

        function loadProfileForBuckling(app)
            F = app.H.Fla;
            p = app.DM.getProfile(F.fam.Value, F.prof.Value);
            F.S.Value = p.S * 1e6;
            F.Iz.Value = p.Iz * 1e12;
            F.Iy.Value = p.Iy * 1e12;
            F.W.Status.Text = sprintf('Profilé %s chargé (valeurs du catalogue).', p.Name);
            F.secInfo.Text = sprintf('Section utilisée : profilé %s (valeurs du catalogue).', p.Name);
        end

        %% ------------------------------------- Tenseurs ---------------------------------------
        function buildTensorTab(app)
            W = app.makeWork(app.Tabs.Ten, 340, 'Ten', {'Tricercle de Mohr', [1 1], 'tenseurs'; ...
                'Mohr 2D (plan x, y)', [1 1], 'mohr_cercle'; 'Lieu de plasticité', [1 1], 'criteres'}, ...
                {'Princ', 'Principales'; 'Crit', 'Critères'; 'Facet', 'Facette'});
            W.PlotGroup.SelectionChangedFcn = @(~, ~) app.safeRun(@() app.updateFormula(), 'Formulaire');
            g = W.In;
            T = struct('W', W);
            app.addRow(g, 'Tenseur des contraintes σ (MPa)', 'title');
            T.sig = app.addRow(g, '', 'table', 100, {'x', 'y', 'z'});
            T.sig.RowName = {'x', 'y', 'z'};
            T.sig.Data = zeros(3);
            T.sig.ColumnFormat = {'numeric', 'numeric', 'numeric'};
            T.sig.CellEditCallback = @(s, e) MecaStruct_App.symmetrize(s, e);
            app.addRow(g, 'La saisie est symétrisée automatiquement (σij = σji).', 'note', 24);
            app.addRow(g, 'Facette', 'title');
            T.fmode = app.addRow(g, 'Définition', 'drop', {'Angle θ dans le plan (x, y)', 'Normale n (nx, ny, nz)'}, {'theta', 'n'});
            T.theta = app.addRow(g, 'θ (°)', 'num');
            T.nx = app.addRow(g, 'nx (-)', 'num');
            T.ny = app.addRow(g, 'ny (-)', 'num');
            T.nz = app.addRow(g, 'nz (-)', 'num');
            app.addRow(g, 'Critères', 'title');
            T.mat = app.addRow(g, 'Matériau', 'drop', cellstr(app.DM.listMaterials()));
            T.Re = app.addRow(g, 'Re = σe (MPa)', 'num');
            T.Rm = app.addRow(g, 'σR (MPa, fragiles : Rm)', 'num');
            T.s = app.addRow(g, 'Coefficient de sécurité s (-)', 'num');
            T.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeTensor(), 'Tenseurs'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Tenseurs'), 'Tenseurs'));
            app.H.Ten = T;
            app.H.Ten.mat.ValueChangedFcn = app.cbk(@() app.applyMaterial('Ten'), 'Matériau');
        end

        %% ---------------------------------- Hooke & jauges ------------------------------------
        function buildHookeTab(app)
            g = uigridlayout(app.Tabs.Hoo, [1 1]);
            g.Padding = [0 0 0 0];
            sg = uitabgroup(g, 'SelectionChangedFcn', @(~, ~) app.safeRun(@() app.updateFormula(), 'Formulaire'));
            app.SubHooke = sg;
            tH = uitab(sg, 'Title', 'Loi de Hooke', 'UserData', 'hooke');
            tJ = uitab(sg, 'Title', 'Jauges, pont et rosettes', 'UserData', 'extensometrie');
            mats = cellstr(app.DM.listMaterials());

            W = app.makeWork(tH, 340, 'Hoo', {'Mohr des déformations (x, y)', [1 1], ''}, {'Res', 'Résultats'; 'Mat', 'Matrice'});
            g = W.In;
            K = struct('W', W, 'Tab', tH);
            K.mode = app.addRow(g, 'Loi', 'drop', {'Hooke 3D isotrope', 'Contraintes planes', 'Déformations planes', ...
                'Orthotrope (9 constantes)'}, {'iso3D', 'planeStress', 'planeStrain', 'ortho'});
            K.mode.ValueChangedFcn = @(~, ~) app.onHookeMode();
            app.addRow(g, 'Matériau isotrope', 'title');
            K.mat = app.addRow(g, 'Matériau', 'drop', mats);
            K.E = app.addRow(g, 'E (GPa)', 'num');
            K.nu = app.addRow(g, 'ν (-)', 'num');
            K.alpha = app.addRow(g, 'α (10⁻⁶/°C)', 'num');
            K.dT = app.addRow(g, 'ΔT (°C)', 'num');
            app.addRow(g, 'Contraintes (MPa)', 'title');
            for f = {'sxx', 'σxx'; 'syy', 'σyy'; 'szz', 'σzz'; 'syz', 'σyz'; 'sxz', 'σxz'; 'sxy', 'σxy'}.'
                K.(f{1}) = app.addRow(g, [f{2} ' (MPa)'], 'num');
            end
            app.addRow(g, 'Déformations planes (µdéf)', 'title');
            K.exx = app.addRow(g, 'εxx (µdéf)', 'num');
            K.eyy = app.addRow(g, 'εyy (µdéf)', 'num');
            K.gxy = app.addRow(g, 'γxy = 2εxy (µdéf)', 'num');
            app.addRow(g, 'Orthotrope (axes 1, 2, 3 = x, y, z)', 'title');
            for f = {'E1', 'E1 (GPa)'; 'E2', 'E2 (GPa)'; 'E3', 'E3 (GPa)'; 'nu12', 'ν12 (-)'; 'nu13', 'ν13 (-)'; ...
                    'nu23', 'ν23 (-)'; 'G12', 'G12 (GPa)'; 'G13', 'G13 (GPa)'; 'G23', 'G23 (GPa)'}.'
                K.(f{1}) = app.addRow(g, f{2}, 'num');
            end
            K.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeHooke(), 'Hooke'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Hooke', app.H.Hoo.mode.Value), 'Hooke'));
            app.H.Hoo = K;
            app.H.Hoo.mat.ValueChangedFcn = app.cbk(@() app.applyMaterial('Hoo'), 'Matériau');

            W = app.makeWork(tJ, 340, 'Jau', {'Mohr des déformations (rosette)', [1 1], ''; ...
                'Mohr des contraintes (rosette)', [1 1], ''}, {'Ros', 'Rosette'; 'Bridge', 'Jauge et pont'});
            g = W.In;
            J = struct('W', W, 'Tab', tJ);
            app.addRow(g, 'Jauge (loi de Bridgman)', 'title');
            J.K = app.addRow(g, 'Facteur de jauge K (-)', 'num');
            J.eps = app.addRow(g, 'ε (µdéf)', 'num');
            J.R0 = app.addRow(g, 'R0 (Ω)', 'num');
            app.addRow(g, 'Pont de Wheatstone', 'title');
            J.cfg = app.addRow(g, 'Montage', 'drop', {'Quart de pont', 'Demi-pont', 'Pont complet'}, {'quart', 'demi', 'complet'});
            J.Vin = app.addRow(g, 'Alimentation Vin (V)', 'num');
            J.e1 = app.addRow(g, 'ε1 (µdéf)', 'num');
            J.e2 = app.addRow(g, 'ε2 (µdéf)', 'num');
            J.e3 = app.addRow(g, 'ε3 (µdéf)', 'num');
            J.e4 = app.addRow(g, 'ε4 (µdéf)', 'num');
            J.Vout = app.addRow(g, 'Vout mesurée (mV)', 'num');
            app.addRow(g, 'Rosette', 'title');
            J.rtype = app.addRow(g, 'Type', 'drop', {'Rectangulaire 0°/90°/45°', 'Delta 0°/60°/120°'}, {'45', '60'});
            J.ra = app.addRow(g, 'ε à 0° (µdéf)', 'num');
            J.rb = app.addRow(g, 'ε à 90° (rect.) / 60° (delta) (µdéf)', 'num');
            J.rc = app.addRow(g, 'ε à 45° (rect.) / 120° (delta) (µdéf)', 'num');
            J.mat = app.addRow(g, 'Matériau', 'drop', mats);
            J.E = app.addRow(g, 'E (GPa)', 'num');
            J.nu = app.addRow(g, 'ν (-)', 'num');
            J.btnCalc = app.addRow(g, 'Calculer', 'button', app.cbk(@() app.computeGauges(), 'Jauges'));
            app.addRow(g, 'Recharger l''exemple', 'button', app.cbk(@() app.loadExample('Jauges'), 'Jauges'));
            app.H.Jau = J;
            app.H.Jau.mat.ValueChangedFcn = app.cbk(@() app.applyMaterial('Jau'), 'Matériau');

            for key = {'Sec', 'Beam', 'Tr'}
                k = key{1};
                app.H.(k).mat.ValueChangedFcn = app.cbk(@() app.applyMaterial(k), 'Matériau');
            end
        end

        function onHookeMode(app)
            K = app.H.Hoo;
            m = K.mode.Value;
            iso = ~strcmp(m, 'ortho');
            sigOn = any(strcmp(m, {'iso3D', 'planeStress', 'ortho'}));
            for f = {'E', 'nu', 'mat'}
                K.(f{1}).Enable = MecaStruct_App.onOff(iso);
            end
            K.alpha.Enable = MecaStruct_App.onOff(strcmp(m, 'iso3D'));
            K.dT.Enable = K.alpha.Enable;
            for f = {'sxx', 'syy', 'sxy'}
                K.(f{1}).Enable = MecaStruct_App.onOff(sigOn);
            end
            for f = {'szz', 'syz', 'sxz'}
                K.(f{1}).Enable = MecaStruct_App.onOff(any(strcmp(m, {'iso3D', 'ortho'})));
            end
            for f = {'exx', 'eyy', 'gxy'}
                K.(f{1}).Enable = MecaStruct_App.onOff(strcmp(m, 'planeStrain'));
            end
            for f = {'E1', 'E2', 'E3', 'nu12', 'nu13', 'nu23', 'G12', 'G13', 'G23'}
                K.(f{1}).Enable = MecaStruct_App.onOff(~iso);
            end
        end

        %% -------------------------------- Utilitaires communs ---------------------------------
        function applyMaterial(app, key)
            % Copie les caractéristiques du matériau choisi dans les champs de la zone key.
            X = app.H.(key);
            m = app.DM.getMaterial(X.mat.Value);
            map = {'E', 'E', 'GPa'; 'G', 'G', 'GPa'; 'nu', 'nu', '-'; 'Re', 'Re', 'MPa'; 'Rm', 'Rm', 'MPa'; ...
                'alpha', 'alpha', '1e-6/°C'};
            for k = 1:size(map, 1)
                f = map{k, 1};
                if isfield(X, f) && isfinite(m.(map{k, 2}))
                    X.(f).Value = DataManager.fromSI(m.(map{k, 2}), map{k, 3});
                end
            end
        end

        function v = si(~, h, unit)
            % Valeur d'un champ convertie en SI.
            v = DataManager.toSI(h.Value, unit);
        end

        function setReport(~, W, varargin)
            % Rapport (cell colonne de char) dans la zone de texte des résultats.
            out = cell(0, 1);
            for k = 1:numel(varargin)
                a = varargin{k};
                if ischar(a) || isstring(a)
                    a = cellstr(a);
                end
                a = cellfun(@char, a(:), 'UniformOutput', false);
                out = [out; a]; %#ok<AGROW>
            end
            W.Report.Value = out;
            nHead = 0;
            if nargin >= 3
                a = varargin{1};
                if ischar(a) || isstring(a)
                    a = cellstr(a);
                end
                nHead = numel(a);
            end
            W.ReportHTML.HTMLSource = MecaStruct_App.reportToHTML(out, nHead);
        end

        function T = kvTable(~, rows)
            % Table Grandeur / Valeur / Unité (valeurs mises en forme).
            n = size(rows, 1);
            v = strings(n, 1);
            for i = 1:n
                x = rows{i, 2};
                if islogical(x) && isscalar(x)
                    v(i) = string(MecaStruct_App.okText(x));
                elseif isnumeric(x) && isscalar(x)
                    v(i) = string(sprintf('%.6g', x));
                elseif isnumeric(x)
                    v(i) = string(mat2str(x, 5));
                else
                    v(i) = string(x);
                end
            end
            T = table(string(rows(:, 1)), v, string(rows(:, 3)), 'VariableNames', {'Grandeur', 'Valeur', 'Unité'});
        end

        function setMatrix(~, tb, M, rn, cn)
            tb.Data = M;
            tb.RowName = rn;
            tb.ColumnName = cn;
        end

        function addTableRow(app, tb, row)
            d = tb.Data;
            if isempty(d)
                d = row;
            else
                d(end + 1, :) = row;
            end
            tb.Data = d;
            app.noteTableEdit(tb);
        end

        function noteTableEdit(app, tb)
            % Tableau de Poutres modifié par un bouton : entrée d'historique.
            if isfield(app.H, 'Beam') && isfield(app.H.Beam, 'combo') && ...
                    any(arrayfun(@(f) isequal(app.H.Beam.(f{1}), tb), {'sup', 'supx', 'hg', 'pl', 'pm', 'dl', 'combo'}))
                app.pushBeamHistory();
            end
        end

        function delTableRow(app, tb)
            d = tb.Data;
            if isempty(d)
                return
            end
            rows = [];
            try
                sel = tb.Selection;
                if ~isempty(sel)
                    rows = unique(sel(:, 1));
                end
            catch
            end
            if isempty(rows)
                rows = size(d, 1);
            end
            rows = rows(rows >= 1 & rows <= size(d, 1));
            d(rows, :) = [];
            tb.Data = d;
            app.noteTableEdit(tb);
        end

        function v = pickItem(~, dd, wanted)
            % Valeur de liste déroulante : wanted s'il existe, sinon le premier élément.
            items = dd.Items;
            if ~isempty(dd.ItemsData)
                items = dd.ItemsData;
            end
            if any(strcmp(items, wanted))
                v = wanted;
            else
                v = items{1};
            end
        end

        function exportDialog(app, key, fmt)
            % Export interactif (dialogue de fichier ouvert uniquement au clic de l'utilisateur).
            [f, p] = uiputfile({['*.' fmt], upper(fmt)}, 'Exporter le graphique', ['MecaStruct_' key '.' fmt]);
            if isequal(f, 0)
                return
            end
            app.exportCurrentPlot(key, fullfile(p, f));
        end

        function safeRun(app, fn, title)
            % Exécute fn ; en cas d'erreur : uialert non bloquant (fenêtre visible) et journal.
            try
                fn();
            catch err
                app.logError(title, err);
                if ~isempty(app.UIFigure) && isvalid(app.UIFigure) && strcmp(app.UIFigure.Visible, 'on')
                    msg = err.message;
                    hint = MecaStruct_App.errorHint(err.identifier);
                    if ~isempty(hint)
                        msg = sprintf('%s\n\nPiste : %s', msg, hint);
                    end
                    uialert(app.UIFigure, msg, title, 'Icon', 'error');
                end
            end
        end

        function logError(app, title, err)
            app.ErrorLog{end + 1, 1} = sprintf('[%s] %s : %s', char(datetime('now', 'Format', 'HH:mm:ss')), ...
                char(title), err.message);
        end

        function updateFormula(app)
            % Fiche du formulaire correspondant à l'onglet (et au sous-onglet) actif.
            wk = app.activeWorkKey();
            isDB = strcmp(wk, 'DB');
            isConv = strcmp(wk, 'Conv');
            if ~isempty(app.ButtonGrid) && isvalid(app.ButtonGrid)
                noVal = isDB || isConv || strcmp(wk, 'Home');
                app.BtnVal.Visible = ~noVal;
                app.BtnNote.Visible = isDB;
                app.BtnGuide.Visible = true;
                if isDB
                    app.ButtonGrid.ColumnWidth = {0, '1x', '1x'};
                elseif noVal
                    app.ButtonGrid.ColumnWidth = {0, 0, '1x'};
                else
                    app.ButtonGrid.ColumnWidth = {'2x', 0, '1x'};
                end
            end
            key = app.currentFormulaKey();
            if ~strcmp(key, app.FormulaKey)
                app.showFormula(key);
            end
        end

        function wk = activeWorkKey(app)
            % Clé de la zone de travail affichée : DB, Sec, Beam, Tr, Tra, Cis, Tor, Fle, Fla, Ten, Hoo ou Jau.
            t = app.TabGroup.SelectedTab;
            wk = t.Tag;
            switch t.Tag
                case 'Sol'
                    cand = {'Tra', 'Cis', 'Tor', 'Fle'};
                    sel = app.SubSol.SelectedTab;
                case 'Hoo'
                    cand = {'Hoo', 'Jau'};
                    sel = app.SubHooke.SelectedTab;
                otherwise
                    return
            end
            for k = 1:numel(cand)
                if isequal(app.H.(cand{k}).Tab, sel)
                    wk = cand{k};
                    return
                end
            end
        end

        function key = currentFormulaKey(app)
            t = app.TabGroup.SelectedTab;
            key = t.UserData;
            switch t.Tag
                case 'Sol'
                    key = app.SubSol.SelectedTab.UserData;
                case 'Hoo'
                    key = app.SubHooke.SelectedTab.UserData;
                case {'Beam', 'Ten'}
                    pt = app.H.(t.Tag).W.PlotGroup.SelectedTab;
                    if ~isempty(pt.UserData)
                        key = pt.UserData;
                    end
            end
        end
    end

    %% =========================================================================================
    %  Utilitaires statiques privés
    %  =========================================================================================
    methods (Static, Access = private)

        function btn = styleButton(btn, role)
            % Couleur d'un bouton selon son rôle : primary (calcul), danger (suppression), accent (dossier, note), secondary
            % (défaut). Sans rôle donné, il est déduit du libellé. Couleurs de milieu de gamme : lisibles en thème clair et sombre.
            if nargin < 2
                if ~isempty(regexp(btn.Text, '^(Calculer|Vérifier|Chercher)', 'once'))
                    role = 'primary';
                elseif ~isempty(regexp(btn.Text, '^Supprimer', 'once'))
                    role = 'danger';
                else
                    role = 'secondary';
                end
            end
            fills = struct('primary', [0.12 0.42 0.72], 'danger', [0.72 0.25 0.25], 'accent', [0.10 0.50 0.45]);
            if isfield(fills, role)
                btn.BackgroundColor = fills.(role);
                btn.FontColor = [1 1 1];
                btn.FontWeight = 'bold';
            end
        end

        function t = sectionText(label, open)
            % Texte du titre d'une section repliable : ▾ ouverte, ▸ fermée.
            arrow = {char(9656), char(9662)};
            t = [arrow{open + 1} ' ' label];
        end

        function k = caseFactor(fac, d, i, col)
            % Coefficient du cas de charge de la ligne i (colonne col du tableau d) ; sans colonne Cas : cas G.
            c = 'G';
            if size(d, 2) >= col && ~isempty(d{i, col})
                c = char(string(d{i, col}));
            end
            if ~isfield(fac, c)
                error('MecaStruct:App:invalidInput', 'Cas de charge inconnu « %s » (attendu : G, Q, W ou S).', c);
            end
            k = fac.(c);
        end

        function k = projectKeys()
            % Onglets de calcul enregistrés dans un projet.
            k = {'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'};
        end

        function sheets = beamEffortSheets(sol)
            % Feuilles « Enveloppe » (max/min de chaque effort) et « Efforts » (valeurs le long de la poutre), en kN et kN·m.
            comps = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'};
            unit = {'kN', 'kN', 'kN', 'kN·m', 'kN·m', 'kN·m'};
            ext = zeros(6, 4);
            for k = 1:6
                e = sol.extrema.(comps{k});
                ext(k, :) = [e.max / 1e3, e.sMax, e.min / 1e3, e.sMin];
            end
            env = table(string(comps(:)), string(unit(:)), ext(:, 1), ext(:, 2), ext(:, 3), ext(:, 4), 'VariableNames', ...
                {'Effort', 'Unité', 'Max', 's du max (m)', 'Min', 's du min (m)'});
            L = sol.N.breaks(end);
            s = unique([linspace(0, L, 201), sol.N.breaks(:).']).';
            eff = table(s, 'VariableNames', {'s (m)'});
            for k = 1:6
                eff.(sprintf('%s (%s)', comps{k}, unit{k})) = BeamAndTrussSolver.ppEval(sol.(comps{k}), s) / 1e3;
            end
            sheets = {'Enveloppe', env; 'Efforts', eff};
        end

        function k = inputKey(h)
            % Clé d'un champ de saisie dans un problème enregistré : libellé de la ligne (colonnes pour un tableau), '' sinon.
            k = '';
            if ischar(h.UserData)
                k = h.UserData;
            end
        end

        function target = matchInputs(items, vals)
            % Pour chaque valeur enregistrée, le champ de même clé et même classe (0 si absent ou déjà attribué).
            target = zeros(1, size(vals, 1));
            used = false(numel(items), 1);   % colonnes comme keys et cls : sinon & produit une matrice N×N
            keys = arrayfun(@MecaStruct_App.inputKey, items(:), 'UniformOutput', false);
            cls = arrayfun(@class, items(:), 'UniformOutput', false);
            for k = 1:size(vals, 1)
                j = find(strcmp(keys, vals{k, 3}) & strcmp(cls, vals{k, 1}) & ~used, 1);
                if ~isempty(j)
                    target(k) = j;
                    used(j) = true;
                end
            end
        end

        function items = inputWidgets(root)
            % Champs de saisie d'un panneau, dans un ordre stable : champs à valeur, cases, listes, puis tableaux.
            v = findobj(root, '-property', 'Value');
            v = v(~arrayfun(@(h) isa(h, 'matlab.ui.control.TextArea'), v));
            items = [v(:); findobj(root, 'Type', 'uitable')];
        end

        function s = unreliableNote(sol)
            %UNRELIABLENOTE Avertissement « résultat non fiable » : poutre hyperstatique avec Iyz ≠ 0 (chaîne vide sinon).
            s = '';
            if ~sol.isostatic && isfield(sol.model, 'Iyz') && sol.model.Iyz ~= 0
                s = '⚠ Résultats NON fiables (hyperstatique, Iyz ≠ 0) — ';
            end
        end

        function s = plainVerdict(sig, adm, ok)
            % Verdict en une phrase : la pièce tient-elle, avec quelle marge.
            marge = (adm - sig) / adm * 100;
            if ok
                s = sprintf('Verdict : la poutre résiste. Contrainte %.1f MPa pour %.1f MPa admissibles, marge %.0f %%.', sig, adm, marge);
            else
                s = sprintf('Verdict : la poutre NE résiste PAS. Contrainte %.1f MPa pour %.1f MPa admissibles (dépassement %.0f %%). Augmentez la section ou réduisez la charge.', ...
                    sig, adm, -marge);
            end
        end

        function h = errorHint(id)
            % Conseil de correction en français pour les erreurs de saisie courantes ('' si aucun).
            map = {
                'mechanism', 'la structure peut bouger. Ajoutez un appui ou un encastrement, ou changez le type d''un appui (voir la légende sous le tableau des appuis).'
                'invalidSupport', 'vérifiez le tableau des appuis : type connu et position comprise entre 0 et L.'
                'invalidModel', 'une donnée est incohérente (position hors de la poutre, case vide, valeur nulle). Relisez les tableaux et la longueur L.'
                'invalidExpression', 'dans les cases de valeurs, utilisez seulement des nombres, x et + - * / ^ ( ).'
                'invalidDimensions', 'vérifiez les dimensions de la section (toutes positives, épaisseurs plus petites que la largeur).'};
            h = '';
            tok = regexp(char(id), '[^:]+$', 'match', 'once');
            k = find(strcmp(map(:, 1), tok), 1);
            if ~isempty(k)
                h = map{k, 2};
            end
        end

        function s = effortReading(N, Mfz, Mfy)
            % Lecture en français des efforts saisis (où la section est tendue ou comprimée).
            if N > 0
                a = sprintf('N = %.4g kN : traction', N);
            elseif N < 0
                a = sprintf('N = %.4g kN : compression', N);
            else
                a = 'N = 0';
            end
            if Mfz > 0
                b = sprintf('Mfz = %.4g kN·m : fibres du haut (y > 0) comprimées, du bas tendues', Mfz);
            elseif Mfz < 0
                b = sprintf('Mfz = %.4g kN·m : fibres du haut (y > 0) tendues, du bas comprimées', Mfz);
            else
                b = 'Mfz = 0';
            end
            if Mfy > 0
                c = sprintf('Mfy = %.4g kN·m : fibres z > 0 tendues, z < 0 comprimées', Mfy);
            elseif Mfy < 0
                c = sprintf('Mfy = %.4g kN·m : fibres z > 0 comprimées, z < 0 tendues', Mfy);
            else
                c = 'Mfy = 0';
            end
            s = sprintf('Lecture des efforts : %s ; %s ; %s.', a, b, c);
        end

        function s = effortHelp()
            % Aide de saisie des efforts (flexion composée déviée).
            s = ['Efforts au point étudié, repère de la poutre : x = ligne moyenne, y vertical vers le haut, z horizontal. ' ...
                'N > 0 : traction. Mfz (charges verticales) > 0 : fibres du haut comprimées, fibres du bas tendues ' ...
                '(poutre sur 2 appuis chargée vers le bas). Mfy (charges horizontales) > 0 : fibres z > 0 tendues. ' ...
                'Pour une poutre déjà calculée : « Efforts en s » ou « Efforts au point critique » remplit N, Mfz, Mfy.'];
        end

        function T = unitTable()
            % Grandeurs et unités du convertisseur : {libellé affiché, clé DataManager.unitFactor}.
            S = {
                'Longueur', {'mm' 'mm'; 'cm' 'cm'; 'm' 'm'; 'µm' 'µm'; 'km' 'km'; 'in' 'in'; 'ft' 'ft'}, 'm', 'mm'
                'Aire', {'mm²' 'mm²'; 'cm²' 'cm²'; 'm²' 'm²'; 'in²' 'in²'; 'ft²' 'ft²'}, 'cm²', 'mm²'
                'Moment quadratique', {'mm⁴' 'mm⁴'; 'cm⁴' 'cm⁴'; 'm⁴' 'm⁴'; 'in⁴' 'in⁴'; 'ft⁴' 'ft⁴'}, 'cm⁴', 'mm⁴'
                'Force', {'N' 'N'; 'daN' 'daN'; 'kN' 'kN'; 'MN' 'MN'; 'kgf' 'kgf'; 'tf' 'tf'; 'lbf' 'lbf'; 'kip' 'kip'}, 'kN', 'N'
                'Moment', {'N·mm' 'N.mm'; 'N·m' 'N.m'; 'daN·m' 'daN.m'; 'kN·m' 'kN.m'; 'kN·mm' 'kN.mm'; 'kgf·m' 'kgf.m'; ...
                    'kgf·cm' 'kgf.cm'; 'lbf·in' 'lbf.in'; 'lbf·ft' 'lbf.ft'; 'kip·in' 'kip.in'; 'kip·ft' 'kip.ft'}, 'kN·m', 'N·mm'
                'Charge linéique', {'N/m' 'N/m'; 'N/mm' 'N/mm'; 'daN/m' 'daN/m'; 'kN/m' 'kN/m'; 'kgf/m' 'kgf/m'; ...
                    'lbf/in' 'lbf/in'; 'lbf/ft' 'lbf/ft'; 'kip/ft' 'kip/ft'}, 'kN/m', 'N/mm'
                'Contrainte et pression', {'Pa' 'Pa'; 'kPa' 'kPa'; 'MPa' 'MPa'; 'GPa' 'GPa'; 'N/mm²' 'N/mm²'; 'bar' 'bar'; ...
                    'kgf/cm²' 'kgf/cm²'; 'kgf/mm²' 'kgf/mm²'; 'psi' 'psi'; 'ksi' 'ksi'}, 'MPa', 'psi'
                'Module d''Young et de Coulomb', {'MPa' 'MPa'; 'GPa' 'GPa'; 'Pa' 'Pa'; 'N/mm²' 'N/mm²'; 'kgf/mm²' 'kgf/mm²'; ...
                    'psi' 'psi'; 'ksi' 'ksi'; 'Mpsi' 'Mpsi'}, 'GPa', 'MPa'
                'Angle', {'rad' 'rad'; 'mrad' 'mrad'; '°' '°'; 'arcmin' 'arcmin'; 'arcsec' 'arcsec'; 'tour' 'turn'}, 'rad', '°'
                'Angle par longueur', {'rad/m' 'rad/m'; 'mrad/m' 'mrad/m'; '°/m' '°/m'}, 'rad/m', '°/m'
                'Coefficient de dilatation', {'1/°C' '1/°C'; '10⁻⁶/°C' '1e-6/°C'; '1/°F' '1/°F'; '10⁻⁶/°F' '1e-6/°F'}, '10⁻⁶/°C', '1/°C'
                'Masse volumique', {'kg/m³' 'kg/m³'; 'g/cm³' 'g/cm³'; 'lb/ft³' 'lb/ft³'; 'lb/in³' 'lb/in³'}, 'kg/m³', 'g/cm³'
                'Déformation', {'-' '-'; '%' '%'; 'µdéf' 'µdéf'; 'mm/m' 'mm/m'}, 'µdéf', '-'
                'Écart de température', {'°C' '°C'; 'K' 'K'; '°F' '°F'}, '°C', '°F'
                'Température absolue', {'°C' 'C'; 'K' 'K'; '°F' 'F'}, '°C', '°F'};
            T = struct('name', {}, 'units', {}, 'defFrom', {}, 'defTo', {});
            for k = 1:size(S, 1)
                lab = S{k, 2}(:, 1);
                T(end + 1) = struct('name', S{k, 1}, 'units', {S{k, 2}}, ...
                    'defFrom', find(strcmp(lab, S{k, 3}), 1), 'defTo', find(strcmp(lab, S{k, 4}), 1)); %#ok<AGROW>
            end
        end

        function D = expectedUnits()
            % Unités des champs de saisie de chaque onglet (rappel dans le convertisseur).
            D = {
                'Matériaux', 'E, G', 'GPa'
                'Matériaux', 'Re, Rm, contraintes', 'MPa'
                'Sections', 'dimensions b, h, D, d, B, H, t, tw, tf', 'mm'
                'Sections', 'N, Ty ; Mfz, Mfy', 'kN ; kN·m'
                'Poutres', 'L, positions, a, b', 'm'
                'Poutres', 'S ; Iz, Iy, Ix ; vy, vz', 'mm² ; mm⁴ ; mm'
                'Poutres', 'forces ; couples ; charges réparties', 'kN ; kN·m ; kN/m'
                'Treillis', 'coordonnées ; S ; forces', 'm ; mm² ; kN'
                'Traction', 'N ; S0 ; L0 ; ΔT ; α', 'kN ; mm² ; m ; °C ; 10⁻⁶/°C'
                'Cisaillement', 'T, F ; S ; C ; D, a, b, L, d, e', 'kN ; mm² ; kN·m ; mm'
                'Torsion', 'Mt ; D, d ; L ; θ adm', 'kN·m ; mm ; m ; °/m'
                'Flexion', 'N ; Mfz, Mfy', 'kN ; kN·m'
                'Flambage', 'L ; S ; Iz, Iy ; P', 'm ; mm² ; mm⁴ ; kN'
                'Tenseurs', 'σij', 'MPa'
                'Hooke', 'σ ; ε, γ ; E', 'MPa ; µdéf ; GPa'
                'Jauges', 'ε ; R0 ; Vin ; Vout', 'µdéf ; Ω ; V ; mV'
                'Résultats', 'tous les rapports et graphes', 'mm, kN, kN·m, MPa, mrad'};
        end

        function html = reportToHTML(lines, nHead)
            % Rapport en HTML : synthèse (nHead premières lignes) en grand et gras, titres « === »
            % en bandeaux, verdicts en vert/rouge, valeurs numériques après « = » en gras coloré.
            if nargin < 2
                nHead = 0;
            end
            body = cell(numel(lines), 1);
            for k = 1:numel(lines)
                s = char(lines{k});
                s = strrep(strrep(strrep(s, '&', '&amp;'), '<', '&lt;'), '>', '&gt;');
                if startsWith(strtrim(s), '===')
                    t = strtrim(regexprep(s, '^\s*=+\s*|\s*=+\s*$', ''));
                    body{k} = ['<div class="sec">' t '</div>'];
                    continue
                end
                s = regexprep(s, '(?<![>\w])(?<!NON )(?<!non )(vérifiée?s?|respectée?)(?!\w)', '<span class="ok">$1</span>');
                s = regexprep(s, '(NON vérifiée?s?|non vérifiée?s?|NON respectée?)', '<span class="ko">$1</span>');
                s = regexprep(s, '(=\s*)(-?\d+(?:[.,]\d+)?(?:e[+-]?\d+)?)', '$1<span class="num">$2</span>');
                if k <= nHead
                    body{k} = ['<div class="head">' s '</div>'];
                else
                    body{k} = ['<div class="ln">' s '</div>'];
                end
            end
            css = ['body{background:#1b1d21;color:#d9dde3;font:13px Consolas,monospace;margin:6px 10px;}' ...
                '.head{font:bold 16px "Segoe UI",sans-serif;color:#ffffff;background:#26456e;border-left:5px solid #4da3ff;' ...
                'padding:6px 10px;margin:2px 0 8px;white-space:pre-wrap;}' ...
                '.sec{font:bold 14px "Segoe UI",sans-serif;color:#ffd479;border-bottom:1px solid #6b5a2a;margin:14px 0 4px;padding-bottom:2px;}' ...
                '.ln{white-space:pre-wrap;line-height:1.45;min-height:1em;}' ...
                '.num{color:#ffb454;font-weight:bold;}' ...
                '.ok{color:#5fe08a;font-weight:bold;}' ...
                '.ko{color:#ff6b6b;font-weight:bold;background:#4a1f1f;padding:0 3px;border-radius:3px;}'];
            html = ['<!doctype html><html><head><meta charset="utf-8"><style>' css '</style></head><body>' ...
                strjoin(body', '') '</body></html>'];
        end

        function [tag, wk] = resolveName(name)
            % Onglet principal (tag) et zone de travail (wk) d'après un nom d'onglet.
            s = lower(char(string(name)));
            s = regexprep(s, '[éèêë]', 'e');
            s = regexprep(s, '[àâ]', 'a');
            s = regexprep(s, '[^a-z]', '');
            map = {
                {'accueil', 'home'}, 'Home', 'Home'
                {'basededonnees', 'bdd', 'db', 'materiaux', 'donnees', 'base'}, 'DB', 'DB'
                {'sections', 'section', 'sec', 'geometrie'}, 'Sec', 'Sec'
                {'poutres', 'poutre', 'beam'}, 'Beam', 'Beam'
                {'treillis', 'tr', 'truss'}, 'Tr', 'Tr'
                {'sollicitations', 'sol', 'traction', 'tra', 'tractioncompression', 'compression'}, 'Sol', 'Tra'
                {'cisaillement', 'cisaillementmatage', 'cis', 'matage', 'clavette', 'goupille'}, 'Sol', 'Cis'
                {'torsion', 'tor'}, 'Sol', 'Tor'
                {'flexion', 'fle'}, 'Sol', 'Fle'
                {'flambage', 'fla'}, 'Fla', 'Fla'
                {'tenseurs', 'tenseur', 'tenseurscriteres', 'ten', 'criteres'}, 'Ten', 'Ten'
                {'convertisseur', 'conversion', 'unites', 'conv'}, 'Conv', 'Conv'
                {'hooke', 'hookejauges', 'hoo', 'loidehooke'}, 'Hoo', 'Hoo'
                {'jauges', 'jau', 'extensometrie', 'jaugespontetrosettes', 'rosettes'}, 'Hoo', 'Jau'};
            for k = 1:size(map, 1)
                if any(strcmp(s, map{k, 1}))
                    tag = map{k, 2};
                    wk = map{k, 3};
                    return
                end
            end
            error('MecaStruct:App:unknownTab', 'Onglet inconnu : « %s ».', char(string(name)));
        end

        function s = formulaLabel(key)
            labels = struct('materiaux', 'Matériaux', 'geometrie', 'Géométrie des sections', ...
                'equilibre', 'Équilibre (PFS)', 'cohesion', 'Torseur de cohésion', 'treillis', 'Treillis', ...
                'traction', 'Traction / compression', 'cisaillement', 'Cisaillement', 'matage', 'Matage', ...
                'torsion', 'Torsion', 'flexion', 'Flexion', 'deformee', 'Déformée', 'energie', 'Énergie', ...
                'mohr_integrales', 'Intégrales de Mohr', 'flambage', 'Flambage', 'tenseurs', 'Tenseurs', ...
                'mohr_cercle', 'Cercle de Mohr', 'criteres', 'Critères', 'hooke', 'Loi de Hooke', ...
                'extensometrie', 'Extensométrie');
            if isfield(labels, key)
                s = labels.(key);
            else
                s = key;
            end
        end

        function rel = relevantDims(ty)
            switch ty
                case 'rectangle'
                    rel = {'b', 'h'};
                case 'disque'
                    rel = {'D'};
                case 'couronne'
                    rel = {'D', 'd'};
                case 'rectangle_creux'
                    rel = {'B', 'H', 't'};
                case {'I', 'T', 'U'}
                    rel = {'h', 'b', 'tw', 'tf'};
                case 'L'
                    rel = {'h', 'b', 't'};
                otherwise
                    rel = {};
            end
        end

        function s = onOff(tf)
            if tf
                s = 'on';
            else
                s = 'off';
            end
        end

        function s = okText(tf)
            if all(tf)
                s = 'vérifié';
            else
                s = 'NON vérifié';
            end
        end

        function s = sectionLabel(sec)
            switch sec.type
                case 'profile'
                    s = sprintf('profilé %s', sec.name);
                case 'rectangle'
                    s = sprintf('rectangle b = %.4g mm × h = %.4g mm', sec.b * 1e3, sec.h * 1e3);
                case 'disque'
                    s = sprintf('disque D = %.4g mm', sec.D * 1e3);
                case 'couronne'
                    s = sprintf('couronne D = %.4g mm, d = %.4g mm', sec.D * 1e3, sec.d * 1e3);
                case 'rectangle_creux'
                    s = sprintf('rectangle creux B = %.4g × H = %.4g mm, t = %.4g mm', sec.B * 1e3, sec.H * 1e3, sec.t * 1e3);
                case {'I', 'T', 'U'}
                    s = sprintf('profil en %s : h = %.4g, b = %.4g, tw = %.4g, tf = %.4g mm', sec.type, ...
                        sec.h * 1e3, sec.b * 1e3, sec.tw * 1e3, sec.tf * 1e3);
                case 'L'
                    s = sprintf('cornière L : h = %.4g, b = %.4g, t = %.4g mm', sec.h * 1e3, sec.b * 1e3, sec.t * 1e3);
                otherwise
                    s = sec.type;
            end
        end

        function T = compareDisplay(C, extra)
            % Table de comparaison des méthodes en unités d'affichage (mm, mm², mm³, mm⁴).
            names = C.Properties.RowNames;
            units = C.Properties.UserData.units;
            f = ones(numel(names), 1);
            u = strings(numel(names), 1);
            for k = 1:numel(names)
                switch units{k}
                    case 'm^2'
                        f(k) = 1e6; u(k) = "mm²";
                    case 'm'
                        f(k) = 1e3; u(k) = "mm";
                    case 'm^3'
                        f(k) = 1e9; u(k) = "mm³";
                    case 'm^4'
                        f(k) = 1e12; u(k) = "mm⁴";
                    otherwise
                        u(k) = string(units{k});
                end
            end
            T = table(string(names(:)), u, C.Analytique .* f, C.Integrale .* f, C.Tabulee .* f, C.EcartMax_pct, ...
                'VariableNames', {'Grandeur', 'Unité', 'Analytique', 'Intégrale', 'Tabulée', 'Écart max (%)'});
            if ~isempty(extra)
                v = zeros(numel(names), 1);
                for k = 1:numel(names)
                    v(k) = extra.(names{k}) * f(k);
                end
                T.('Intégrale numérique') = v;
            end
        end

        function T = huygensDisplay(Hy)
            % Tableau de Huygens en mm, mm², mm⁴.
            vn = Hy.Properties.VariableNames;
            T = table();
            for k = 1:numel(vn)
                v = vn{k};
                x = Hy.(v);
                switch v
                    case 'Label'
                        T.('Élément') = string(x);
                    case 'S_i'
                        T.('S_i (mm²)') = x * 1e6;
                    case {'zG_i', 'yG_i', 'dy_i', 'dz_i'}
                        T.([v ' (mm)']) = x * 1e3;
                    otherwise
                        T.([v ' (mm⁴)']) = x * 1e12;
                end
            end
        end

        function T = equationTable(sol)
            eqs = sol.equations;
            n = numel(eqs);
            T = table((1:n).', [eqs.s1].', [eqs.s2].', 'VariableNames', {'Tronçon', 's1 (m)', 's2 (m)'});
            comps = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'};
            for k = 1:numel(comps)
                T.([comps{k} '(s)']) = string({eqs.([comps{k} '_txt'])}).';
            end
        end

        function plotEquations(ax, sol, comps)
            % Équations LaTeX par tronçon des composantes sélectionnées.
            cla(ax, 'reset');
            hold(ax, 'on');
            eqs = sol.equations;
            y = 0.2;
            for k = 1:numel(eqs)
                text(ax, 0.01, y, sprintf('Tronçon %d : s ∈ [%.4g ; %.4g] m', k, eqs(k).s1, eqs(k).s2), ...
                    'Interpreter', 'none', 'FontWeight', 'bold', 'VerticalAlignment', 'middle', 'Color', [0 0.35 0.65]);
                y = y + 1;
                for c = 1:numel(comps)
                    text(ax, 0.04, y, char(eqs(k).(comps{c})), 'Interpreter', 'latex', 'FontSize', 12, ...
                        'VerticalAlignment', 'middle');
                    y = y + 1.2;
                end
                y = y + 0.3;
            end
            hold(ax, 'off');
            ax.YDir = 'reverse';
            xlim(ax, [0 1]);
            ylim(ax, [-0.4 max(y, 1)]);
            ax.XTick = [];
            ax.YTick = [];
            ax.Visible = 'off';
        end

        function plotRatios(ax, labels, vals, ttl)
            % Diagramme en barres (taux d'utilisation ou longueurs).
            cla(ax, 'reset');
            n = numel(vals);
            b = bar(ax, 1:n, vals, 0.5);
            b.FaceColor = 'flat';
            for k = 1:n
                if vals(k) > 1 && contains(ttl, 'utilisation')
                    b.CData(k, :) = [0.85 0.15 0.15];
                else
                    b.CData(k, :) = [0 0.45 0.74];
                end
                text(ax, k, vals(k), sprintf('%.4g', vals(k)), 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');
            end
            hold(ax, 'on');
            if contains(ttl, 'utilisation')
                plot(ax, [0.5 n + 0.5], [1 1], 'r--', 'LineWidth', 1.5);
            end
            hold(ax, 'off');
            ax.XTick = 1:n;
            ax.XTickLabel = labels;
            grid(ax, 'on');
            title(ax, ttl);
        end

        function symmetrize(src, e)
            d = src.Data;
            i = e.Indices(1);
            j = e.Indices(2);
            d(j, i) = d(i, j);
            src.Data = d;
        end

        function v = cellNum(x, what)
            % Nombre réel fini lu dans une cellule de table.
            if isnumeric(x) || islogical(x)
                v = double(x);
            else
                v = str2double(strrep(char(string(x)), ',', '.'));
            end
            if ~isscalar(v) || ~isfinite(v)
                error('MecaStruct:App:invalidInput', '%s : valeur numérique invalide.', what);
            end
        end

        function v = parseNumbers(txt, what)
            % Liste de nombres séparés par des espaces, virgules ou points-virgules (« 100 100, 50 ») ; virgule décimale non admise.
            parts = strsplit(strtrim(regexprep(char(string(txt)), '[;,]+', ' ')));
            parts = parts(~cellfun(@isempty, parts));
            v = str2double(parts);
            if any(~isfinite(v))
                error('MecaStruct:App:invalidInput', '%s : liste de nombres invalide (« %s »).', what, char(string(txt)));
            end
        end

        function j = nodeIndex(x, n)
            j = MecaStruct_App.cellNum(x, 'Numéro de nœud');
            if j ~= round(j) || j < 1 || j > n
                error('MecaStruct:App:invalidInput', 'Numéro de nœud %g invalide (1 à %d).', j, n);
            end
        end

        function c = distCoeffs(type, vals, a, b)
            % Coefficients (ordre polyval, variable locale ξ = s − a) d'une charge répartie (kN/m).
            s = strtrim(regexprep(char(string(vals)), '[;]', ' '));
            v = sscanf(strrep(s, ',', '.'), '%f').';
            if isempty(v) || any(~isfinite(v))
                error('MecaStruct:App:invalidInput', 'Charge répartie : valeurs « %s » invalides.', s);
            end
            t = regexprep(lower(char(string(type))), '[éè]', 'e');
            switch t
                case 'uniforme'
                    c = v(1);
                case 'lineaire'
                    if numel(v) < 2
                        error('MecaStruct:App:invalidInput', 'Charge linéaire : deux valeurs « p1 p2 » attendues.');
                    end
                    c = [(v(2) - v(1)) / (b - a), v(1)];
                case 'polynomiale'
                    c = v;
                otherwise
                    error('MecaStruct:App:invalidInput', 'Type de charge répartie inconnu : %s.', t);
            end
        end
    end
end
