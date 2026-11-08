classdef PlotEngine
    %PLOTENGINE Moteur d'affichage graphique de MecaStruct_RdM_Pro (classe statique).
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   Toutes les fonctions tracent sur un axe fourni (axes ou uiaxes) passé en premier
    %   argument ; si cet argument est vide, une figure est créée. L'axe est effacé, la
    %   grille activée et l'interpréteur LaTeX utilisé pour titres, labels et légendes.
    %   Aucun calcul mécanique n'est effectué ici : les structures tracées sont celles
    %   renvoyées par les moteurs (SI strict) ; seules des conversions d'affichage sont
    %   faites (kN, kN·m, MPa, mm, mrad, µdéf).
    %
    %   Fonctions : beamSchematic, internalForces, deflection, section, sectionStress,
    %   bucklingCurve, mohr2D, mohr3D, yieldLocus, truss, formulaSheet, ktChart, exportAxes.
    %
    %   Voir aussi BeamAndTrussSolver, GeometryEngine, BucklingEngine,
    %   TensorAndCriteriaEngine, SolicitationsEngine.

    methods (Static)

        %% ========================= Poutre : schéma =========================
        function ax = beamSchematic(ax, model, sol)
            %BEAMSCHEMATIC Schéma de la poutre : appuis, forces, couples, charges réparties, réactions.
            %   ax = PlotEngine.beamSchematic(ax, model)
            %   ax = PlotEngine.beamSchematic(ax, model, sol)
            %   model : modèle de poutre (§3 du contrat, SI) ; sol : résultat de
            %   BeamAndTrussSolver.solveBeam (optionnel) → réactions tracées en vert avec valeurs.
            %   Symboles : appui simple (triangle sur rouleaux), rotule/pivot (triangle + cercle),
            %   pivot glissant (triangle + cercle sur rouleaux), encastrement (mur hachuré).
            if nargin < 3
                sol = [];
            end
            if ~isstruct(model) || ~isfield(model, 'L') || ~isnumeric(model.L) || ~isscalar(model.L) || model.L <= 0
                error('MecaStruct:PlotEngine:invalidInput', 'model.L (longueur, m) doit être un réel strictement positif.');
            end
            ax = peAxes(ax);
            L = double(model.L);
            fg = ax.XColor;
            cLoad = [0.80 0.10 0.10];
            cDist = [0.90 0.45 0.00];
            cReac = [0.10 0.60 0.20];
            h = 0.05 * L;          % taille des symboles d'appui
            Ha = 0.20 * L;         % longueur des flèches de force
            Hq = 0.10 * L;         % hauteur max des charges réparties
            Hr = 0.12 * L;         % longueur des flèches de réaction
            hs = 0.025 * L;        % taille des pointes de flèches
            yTop = 0.05 * L;
            yBot = -0.05 * L;
            hLeg = gobjects(0);
            legTxt = {};
            keyX = [0 L];

            hBeam = plot(ax, [0 L], [0 0], '-', 'Color', fg, 'LineWidth', 4);
            hLeg(end+1) = hBeam;
            legTxt{end+1} = 'Poutre';

            % ---- appuis
            sup = peArr(model, 'supports');
            for i = 1:numel(sup)
                x = sup(i).pos;
                keyX(end+1) = x; %#ok<AGROW>
                typ = lower(char(sup(i).type));
                if strcmp(typ, 'encastrement')
                    if x < L / 2
                        phi = -pi / 2;
                    else
                        phi = pi / 2;
                    end
                else
                    phi = 0;
                end
                peSupport(ax, [x 0], typ, h, phi, fg);
                nm = peName(sup(i), sprintf('%c', 'A' + i - 1));
                if strcmp(typ, 'encastrement')
                    text(ax, x + sign(phi) * 1.8 * h, -1.6 * h, ['$' peTexName(nm) '$'], 'Interpreter', 'latex', ...
                        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', 'Color', fg, 'FontSize', 11);
                else
                    text(ax, x - 0.9 * h, -0.5 * h, ['$' peTexName(nm) '$'], 'Interpreter', 'latex', ...
                        'HorizontalAlignment', 'right', 'VerticalAlignment', 'middle', 'Color', fg, 'FontSize', 11);
                end
                yBot = min(yBot, -1.6 * h);
                % ressort (zigzag sous l'appui) et tassement imposé (note)
                note = '';
                if isfield(sup, 'spring') && ~isempty(sup(i).spring) && sup(i).spring > 0
                    zy = linspace(-1.1 * h, -3.1 * h, 9);
                    zx = x + 0.5 * h * [0 1 -1 1 -1 1 -1 1 0];
                    plot(ax, zx, zy, '-', 'Color', fg, 'LineWidth', 1.2);
                    plot(ax, [x - h, x + h], [zy(end) zy(end)] - 0.1 * h, '-', 'Color', fg, 'LineWidth', 2);
                    note = sprintf('k = %s kN/m', peNum(sup(i).spring / 1e3));
                    yBot = min(yBot, -3.6 * h);
                end
                if isfield(sup, 'dy')
                    dd = [sup(i).dx sup(i).dy sup(i).dz];
                    if any(dd ~= 0)
                        note = strtrim(sprintf('%s tassement (mm) : %s', note, strtrim(sprintf('%s ', peNum(dd(1) * 1e3), peNum(dd(2) * 1e3), peNum(dd(3) * 1e3)))));
                    end
                end
                if ~isempty(note)
                    text(ax, x, yBot - 0.4 * h, note, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
                        'Color', fg, 'FontSize', 8);
                    yBot = yBot - 1.6 * h;
                end
            end

            % ---- rotules intermédiaires
            hg = peArr(model, 'hinges');
            for i = 1:numel(hg)
                keyX(end+1) = hg(i).pos; %#ok<AGROW>
                plot(ax, hg(i).pos, 0, 'o', 'MarkerSize', 10, 'MarkerFaceColor', ax.Color, 'MarkerEdgeColor', fg, 'LineWidth', 1.8);
            end

            % ---- charges réparties
            dl = peArr(model, 'distLoads');
            pmaxAll = 0;
            for i = 1:numel(dl)
                xi = linspace(0, dl(i).b - dl(i).a, 50);
                pmaxAll = max(pmaxAll, max(abs(polyval(dl(i).coeffs, xi))));
            end
            firstDist = true;
            placed = zeros(0, 3);   % [a b sommet] des charges y déjà tracées (empilement si recouvrement)
            for i = 1:numel(dl)
                a = dl(i).a;
                b = dl(i).b;
                keyX = [keyX a b]; %#ok<AGROW>
                c = dl(i).coeffs;
                xs = linspace(a, b, 120);
                ps = polyval(c, xs - a);
                nmTex = peTexName(peName(dl(i), sprintf('q%d', i)));
                dirc = lower(char(dl(i).dir));
                switch dirc
                    case 'y'
                        ov = placed(:, 1) < b & placed(:, 2) > a;
                        base = 0;
                        if any(ov)
                            base = max(placed(ov, 3));
                            plot(ax, [a b], [base base], ':', 'Color', cDist, 'LineWidth', 1);
                        end
                        if pmaxAll > 0
                            env = base + Hq * abs(ps) / pmaxAll;
                        else
                            env = base + zeros(size(xs));
                        end
                        hE = plot(ax, xs, env, '-', 'Color', cDist, 'LineWidth', 1.5);
                        plot(ax, [a a], [base env(1)], '-', 'Color', cDist, 'LineWidth', 1);
                        plot(ax, [b b], [base env(end)], '-', 'Color', cDist, 'LineWidth', 1);
                        nArr = max(5, round(14 * (b - a) / L));
                        xa = linspace(a, b, nArr);
                        pa = polyval(c, xa - a);
                        for k = 1:nArr
                            hk = Hq * abs(pa(k)) / max(pmaxAll, realmin);
                            if hk < 0.15 * Hq
                                continue
                            end
                            if pa(k) < 0
                                peArrow(ax, [xa(k) base + hk], [xa(k) base], cDist, 0.6 * hs, 1);
                            else
                                peArrow(ax, [xa(k) base], [xa(k) base + hk], cDist, 0.6 * hs, 1);
                            end
                        end
                        if isscalar(c)
                            lab = sprintf('$%s = %s$ kN/m', nmTex, peNum(c / 1e3));
                            text(ax, (a + b) / 2, max(env) + 0.02 * L, lab, 'Interpreter', 'latex', 'Color', cDist, ...
                                'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontSize', 10);
                        else
                            text(ax, a, env(1) + 0.02 * L, sprintf('$%s(%s) = %s$ kN/m', nmTex, peNum(a), peNum(ps(1) / 1e3)), ...
                                'Interpreter', 'latex', 'Color', cDist, 'HorizontalAlignment', 'left', ...
                                'VerticalAlignment', 'bottom', 'FontSize', 9);
                            text(ax, b, env(end) + 0.02 * L, sprintf('$%s(%s) = %s$ kN/m', nmTex, peNum(b), peNum(ps(end) / 1e3)), ...
                                'Interpreter', 'latex', 'Color', cDist, 'HorizontalAlignment', 'right', ...
                                'VerticalAlignment', 'bottom', 'FontSize', 9);
                        end
                        yTop = max(yTop, max(env) + 0.08 * L);
                        placed(end+1, :) = [a b max(env) + 0.07 * L]; %#ok<AGROW>
                    case 'x'
                        hE = plot(ax, xs, 0.03 * L * ones(size(xs)), ':', 'Color', cDist, 'LineWidth', 1.2);
                        nArr = max(3, round(8 * (b - a) / L));
                        xa = linspace(a, b, nArr + 1);
                        pa = polyval(c, (xa(1:end-1) + xa(2:end)) / 2 - a);
                        for k = 1:nArr
                            if pa(k) >= 0
                                peArrow(ax, [xa(k) 0.03 * L], [xa(k+1) 0.03 * L], cDist, 0.5 * hs, 1);
                            else
                                peArrow(ax, [xa(k+1) 0.03 * L], [xa(k) 0.03 * L], cDist, 0.5 * hs, 1);
                            end
                        end
                        text(ax, (a + b) / 2, 0.05 * L, sprintf('$p_x$ : $%s$', nmTex), 'Interpreter', 'latex', ...
                            'Color', cDist, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontSize', 9);
                        yTop = max(yTop, 0.1 * L);
                    otherwise
                        nArr = max(3, round(10 * (b - a) / L));
                        xa = linspace(a, b, nArr);
                        pa = polyval(c, xa - a);
                        mk = repmat('o', 1, nArr);
                        mk(pa < 0) = 'x';
                        hE = plot(ax, xs, 0.03 * L * ones(size(xs)), ':', 'Color', cDist, 'LineWidth', 1.2);
                        for k = 1:nArr
                            plot(ax, xa(k), 0.03 * L, mk(k), 'Color', cDist, 'MarkerSize', 7, 'LineWidth', 1.2);
                        end
                        text(ax, (a + b) / 2, 0.05 * L, sprintf('$p_z$ : $%s$', nmTex), 'Interpreter', 'latex', ...
                            'Color', cDist, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontSize', 9);
                        yTop = max(yTop, 0.1 * L);
                end
                if firstDist
                    hLeg(end+1) = hE; %#ok<AGROW>
                    legTxt{end+1} = peTx('Charges réparties'); %#ok<AGROW>
                    firstDist = false;
                end
            end

            % ---- forces ponctuelles
            pl = peArr(model, 'pointLoads');
            firstLoad = true;
            for i = 1:numel(pl)
                x = pl(i).pos;
                keyX(end+1) = x; %#ok<AGROW>
                nmTex = peTexName(peName(pl(i), sprintf('F%d', i)));
                Fx = peField(pl(i), 'Fx');
                Fy = peField(pl(i), 'Fy');
                Fz = peField(pl(i), 'Fz');
                hF = gobjects(0);
                if Fy ~= 0
                    if Fy < 0
                        hF = peArrow(ax, [x Ha], [x 0], cLoad, hs, 2);
                    else
                        hF = peArrow(ax, [x 0], [x Ha], cLoad, hs, 2);
                    end
                    text(ax, x, Ha + 0.015 * L, sprintf('$%s = %s$ kN', peTexComp(nmTex, 'y'), peNum(Fy / 1e3)), ...
                        'Interpreter', 'latex', 'Color', cLoad, 'HorizontalAlignment', 'center', ...
                        'VerticalAlignment', 'bottom', 'FontSize', 10);
                    yTop = max(yTop, Ha + 0.09 * L);
                end
                if Fx ~= 0
                    yx = 0.012 * L;
                    if x > L / 2
                        p1 = [x yx];
                        p2 = [x + sign(Fx) * Ha * 0.6 yx];
                        if Fx < 0
                            [p1, p2] = deal([x + Ha * 0.6 yx], [x yx]);
                        end
                    else
                        p2 = [x yx];
                        p1 = [x - sign(Fx) * Ha * 0.6 yx];
                        if Fx < 0
                            [p1, p2] = deal([x yx], [x - Ha * 0.6 yx]);
                        end
                    end
                    hF = peArrow(ax, p1, p2, cLoad, hs, 2);
                    text(ax, (p1(1) + p2(1)) / 2, yx + 0.02 * L, sprintf('$%s = %s$ kN', peTexComp(nmTex, 'x'), peNum(Fx / 1e3)), ...
                        'Interpreter', 'latex', 'Color', cLoad, 'HorizontalAlignment', 'center', ...
                        'VerticalAlignment', 'bottom', 'FontSize', 10);
                end
                if Fz ~= 0
                    if Fz > 0
                        mk = 'o';
                    else
                        mk = 'x';
                    end
                    hF = plot(ax, x, 0, mk, 'Color', cLoad, 'MarkerSize', 12, 'LineWidth', 2);
                    plot(ax, x, 0, '.', 'Color', cLoad, 'MarkerSize', 10);
                    text(ax, x, -0.03 * L, sprintf('$%s = %s$ kN', peTexComp(nmTex, 'z'), peNum(Fz / 1e3)), ...
                        'Interpreter', 'latex', 'Color', cLoad, 'HorizontalAlignment', 'center', ...
                        'VerticalAlignment', 'top', 'FontSize', 10);
                end
                if firstLoad && ~isempty(hF)
                    hLeg(end+1) = hF(1); %#ok<AGROW>
                    legTxt{end+1} = 'Forces'; %#ok<AGROW>
                    firstLoad = false;
                end
            end

            % ---- couples ponctuels
            pm = peArr(model, 'pointMoments');
            for i = 1:numel(pm)
                x = pm(i).pos;
                keyX(end+1) = x; %#ok<AGROW>
                nmTex = peTexName(peName(pm(i), sprintf('C%d', i)));
                Mz = peField(pm(i), 'Mz');
                parts = {};
                if Mz ~= 0
                    hC = peArcArrow(ax, [x 0], 1.6 * h, Mz, cLoad, 0.8 * hs, 1.8);
                    parts{end+1} = sprintf('$%s = %s$ kN$\\cdot$m', peTexComp(nmTex, 'z'), peNum(Mz / 1e3)); %#ok<AGROW>
                    if firstLoad
                        hLeg(end+1) = hC; %#ok<AGROW>
                        legTxt{end+1} = 'Forces'; %#ok<AGROW>
                        firstLoad = false;
                    end
                end
                for cc = {'Mx', 'My'}
                    v = peField(pm(i), cc{1});
                    if v ~= 0
                        parts{end+1} = sprintf('$%s = %s$ kN$\\cdot$m', peTexComp(nmTex, lower(cc{1}(2))), peNum(v / 1e3)); %#ok<AGROW>
                        plot(ax, x, 0, 'd', 'Color', cLoad, 'MarkerFaceColor', cLoad, 'MarkerSize', 7);
                    end
                end
                if ~isempty(parts)
                    text(ax, x, -1.8 * h, strjoin(parts, ', '), 'Interpreter', 'latex', 'Color', cLoad, ...
                        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', 'FontSize', 10);
                    yBot = min(yBot, -1.8 * h - 0.07 * L);
                end
            end

            % ---- réactions
            if ~isempty(sol) && isstruct(sol) && isfield(sol, 'reactions') && ~isempty(sol.reactions)
                R = sol.reactions;
                firstR = true;
                for i = 1:numel(R)
                    x = R(i).pos;
                    nm = peTexName(peName(R(i), sprintf('%c', 'A' + i - 1)));
                    isEnc = strcmpi(char(R(i).type), 'encastrement');
                    hR = gobjects(0);
                    y0 = -1.75 * h;
                    if isEnc
                        y0 = -1.3 * h;
                    end
                    if R(i).Ry ~= 0
                        if R(i).Ry > 0
                            hR = peArrow(ax, [x y0 - Hr], [x y0], cReac, hs, 2);
                        else
                            hR = peArrow(ax, [x y0], [x y0 - Hr], cReac, hs, 2);
                        end
                    end
                    lines = {};
                    if R(i).Rx ~= 0
                        yx = y0 - 0.35 * Hr;
                        sd = 1 - 2 * (x > L / 2);   % côté extérieur : gauche si x < L/2, droite sinon
                        xo = x - sd * 0.8 * Hr;
                        if sign(R(i).Rx) == sd
                            hR = peArrow(ax, [xo yx], [x yx], cReac, hs, 2);
                        else
                            hR = peArrow(ax, [x yx], [xo yx], cReac, hs, 2);
                        end
                        lines{end+1} = sprintf('$X_{%s} = %s$ kN', nm, peNum(R(i).Rx / 1e3)); %#ok<AGROW>
                    end
                    if R(i).Ry ~= 0 || ~isEnc
                        lines{end+1} = sprintf('$Y_{%s} = %s$ kN', nm, peNum(R(i).Ry / 1e3)); %#ok<AGROW>
                    end
                    if R(i).Mz ~= 0
                        hR = peArcArrow(ax, [x 0], 1.6 * h, R(i).Mz, cReac, 0.8 * hs, 1.8);
                        lines{end+1} = sprintf('$M_{%s} = %s$ kN$\\cdot$m', nm, peNum(R(i).Mz / 1e3)); %#ok<AGROW>
                    end
                    if isfield(R(i), 'Rz') && R(i).Rz ~= 0
                        lines{end+1} = sprintf('$Z_{%s} = %s$ kN', nm, peNum(R(i).Rz / 1e3)); %#ok<AGROW>
                    end
                    if isfield(R(i), 'My') && R(i).My ~= 0
                        lines{end+1} = sprintf('$M_{y%s} = %s$ kN$\\cdot$m', nm, peNum(R(i).My / 1e3)); %#ok<AGROW>
                    end
                    if isfield(R(i), 'Mx') && R(i).Mx ~= 0
                        lines{end+1} = sprintf('$M_{x%s} = %s$ kN$\\cdot$m', nm, peNum(R(i).Mx / 1e3)); %#ok<AGROW>
                    end
                    yl = y0 - Hr - 0.015 * L;
                    text(ax, x, yl, lines, 'Interpreter', 'latex', 'Color', cReac, ...
                        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', 'FontSize', 10);
                    yBot = min(yBot, yl - 0.06 * L * numel(lines));
                    if firstR && ~isempty(hR)
                        hLeg(end+1) = hR(1); %#ok<AGROW>
                        legTxt{end+1} = 'R\''{e}actions'; %#ok<AGROW>
                        firstR = false;
                    end
                end
            end

            axis(ax, 'equal');
            xlim(ax, [-0.15 * L, 1.15 * L]);
            ylim(ax, [yBot - 0.02 * L, yTop + 0.02 * L]);
            ax.YTick = [];
            ax.YGrid = 'off';
            kx = uniquetol(keyX(:).', 1e-9);
            if numel(kx) <= 12
                ax.XTick = kx;
            end
            xlabel(ax, '$s$ (m)', 'Interpreter', 'latex');
            title(ax, peTx('Schéma de la poutre'), 'Interpreter', 'latex');
            legend(ax, hLeg, legTxt, 'Interpreter', 'latex', 'Location', 'southoutside', 'Orientation', 'horizontal');
            hold(ax, 'off');
        end

        %% ========================= Poutre : diagrammes =========================
        function axList = movingEnvelope(axList, env)
            %MOVINGENVELOPE Enveloppe des efforts d'une charge mobile : moment Mfz (axe 1) et tranchant Ty (axe 2).
            %   axList = PlotEngine.movingEnvelope(axList, env)
            %   env : s (m), Mmax, Mmin (N·m), Tmax, Tmin (N), mêmes longueurs ; tracé en kN et kN·m.
            if numel(axList) < 2
                error('MecaStruct:PlotEngine:invalidAxes', 'Il faut deux axes (moment et tranchant).');
            end
            names = {'Mmax', 'Mmin', 'Tmax', 'Tmin'};
            ttl = {'Enveloppe du moment $M_{fz}(s)$', 'Enveloppe du tranchant $T_y(s)$'};
            yl = {'$M_{fz}$ (kN$\cdot$m)', '$T_y$ (kN)'};
            for k = 1:2
                ax = peAxes(axList(k));
                axList(k) = ax;
                fg = ax.XColor;
                hi = env.(names{2*k - 1}) / 1e3;
                lo = env.(names{2*k}) / 1e3;
                s = env.s;
                fill(ax, [s fliplr(s)], [hi fliplr(lo)], [0.00 0.45 0.74], 'FaceAlpha', 0.25, 'EdgeColor', 'none');
                h1 = plot(ax, s, hi, '-', 'Color', [0.00 0.45 0.74], 'LineWidth', 1.8);
                h2 = plot(ax, s, lo, '-', 'Color', [0.85 0.15 0.15], 'LineWidth', 1.8);
                plot(ax, [s(1) s(end)], [0 0], '-', 'Color', fg, 'LineWidth', 0.8);
                span = max(max(hi) - min(lo), eps);
                ylim(ax, [min(lo) - 0.1 * span, max(hi) + 0.1 * span]);
                xlim(ax, [s(1) s(end)]);
                title(ax, ttl{k}, 'Interpreter', 'latex', 'Color', fg);
                ylabel(ax, yl{k}, 'Interpreter', 'latex');
                if k == 2
                    xlabel(ax, '$s$ (m)', 'Interpreter', 'latex');
                end
                legend(ax, [h1 h2], {'maximum', 'minimum'}, 'Interpreter', 'latex', 'Location', 'southoutside', 'Orientation', 'horizontal');
            end
        end

        function axList = internalForces(axList, sol, comps)
            %INTERNALFORCES Diagrammes des efforts intérieurs alignés sur s ∈ [0, L].
            %   axList = PlotEngine.internalForces(axList, sol, comps)
            %   sol   : résultat de BeamAndTrussSolver.solveBeam ;
            %   comps : cellstr ⊂ {'N','Ty','Tz','Mt','Mfy','Mfz'} (défaut : composantes non nulles,
            %           {'Ty','Mfz'} si toutes nulles) ; un axe par composante (axList vide → figure).
            %   Aires remplies (bleu > 0, rouge < 0), sauts visibles, extrema annotés, axes x liés.
            all6 = {'N', 'Ty', 'Tz', 'Mt', 'Mfy', 'Mfz'};
            if ~isstruct(sol) || ~isfield(sol, 'Mfz')
                error('MecaStruct:PlotEngine:invalidInput', 'sol doit être un résultat de BeamAndTrussSolver.solveBeam.');
            end
            if nargin < 3 || isempty(comps)
                comps = {};
                for k = 1:6
                    c = sol.(all6{k});
                    if any(cellfun(@(v) any(v ~= 0), c.coefs))
                        comps{end+1} = all6{k}; %#ok<AGROW>
                    end
                end
                if isempty(comps)
                    comps = {'Ty', 'Mfz'};
                end
            end
            comps = cellstr(comps);
            if ~all(ismember(comps, all6))
                error('MecaStruct:PlotEngine:invalidInput', 'comps doit être inclus dans {N, Ty, Tz, Mt, Mfy, Mfz}.');
            end
            n = numel(comps);
            if isempty(axList)
                f = figure('Name', 'Efforts intérieurs');
                tl = tiledlayout(f, n, 1, 'TileSpacing', 'compact');
                axList = gobjects(n, 1);
                for k = 1:n
                    axList(k) = nexttile(tl);
                end
            elseif numel(axList) < n
                error('MecaStruct:PlotEngine:invalidAxes', 'Il faut un axe par composante (%d axes fournis, %d requis).', ...
                    numel(axList), n);
            end
            info = struct( ...
                'N',   {{'Effort normal $N(s)$', '$N$ (kN)', 'N'}}, ...
                'Ty',  {{'Effort tranchant $T_y(s)$', '$T_y$ (kN)', 'T_y'}}, ...
                'Tz',  {{'Effort tranchant $T_z(s)$', '$T_z$ (kN)', 'T_z'}}, ...
                'Mt',  {{'Moment de torsion $M_t(s)$', '$M_t$ (kN$\cdot$m)', 'M_t'}}, ...
                'Mfy', {{'Moment fl\''{e}chissant $M_{fy}(s)$', '$M_{fy}$ (kN$\cdot$m)', 'M_{fy}'}}, ...
                'Mfz', {{'Moment fl\''{e}chissant $M_{fz}(s)$', '$M_{fz}$ (kN$\cdot$m)', 'M_{fz}'}});
            L = sol.(comps{1}).breaks(end);
            cPos = [0.00 0.45 0.74];
            cNeg = [0.85 0.15 0.15];
            for k = 1:n
                ax = peAxes(axList(k));
                axList(k) = ax;
                fg = ax.XColor;
                c = comps{k};
                pp = sol.(c);
                [s, v] = BeamAndTrussSolver.ppSample(pp, 80);
                v = v / 1e3;
                vp = max(v, 0);
                vn = min(v, 0);
                h1 = fill(ax, [s fliplr(s)], [vp zeros(size(vp))], cPos, 'FaceAlpha', 0.30, 'EdgeColor', 'none');
                h2 = fill(ax, [s fliplr(s)], [vn zeros(size(vn))], cNeg, 'FaceAlpha', 0.30, 'EdgeColor', 'none');
                plot(ax, [0 L], [0 0], '-', 'Color', fg, 'LineWidth', 0.8);
                h3 = plot(ax, s, v, '-', 'Color', fg, 'LineWidth', 1.8);
                % extrema
                vMax = max(v);
                vMin = min(v);
                span = max(vMax - vMin, max(abs([vMax vMin])));
                if span == 0
                    span = 1;
                end
                if isfield(sol, 'extrema') && isfield(sol.extrema, c)
                    e = sol.extrema.(c);
                    vMax = e.max / 1e3; sMax = e.sMax;
                    vMin = e.min / 1e3; sMin = e.sMin;
                else
                    [vMax, iM] = max(v); sMax = s(iM);
                    [vMin, im] = min(v); sMin = s(im);
                end
                lo = min([v 0]);
                hi = max([v 0]);
                if hi - lo == 0
                    hi = 1; lo = -1;
                end
                ylim(ax, [lo - 0.30 * (hi - lo), hi + 0.30 * (hi - lo)]);   % avant les étiquettes : elles s'en servent
                xlim(ax, [0 L]);
                tol = 1e-9 * span;
                if abs(vMax) > tol
                    peExtremum(ax, sMax, vMax, L, 'max', info.(c){3}, peUnitTex(c), cPos);
                end
                if abs(vMin) > tol && abs(vMin - vMax) > tol
                    peExtremum(ax, sMin, vMin, L, 'min', info.(c){3}, peUnitTex(c), cNeg);
                end
                title(ax, info.(c){1}, 'Interpreter', 'latex');
                ylabel(ax, info.(c){2}, 'Interpreter', 'latex');
                if k == n
                    xlabel(ax, '$s$ (m)', 'Interpreter', 'latex');
                end
                legend(ax, [h3 h1 h2], {'Diagramme', '$> 0$', '$< 0$'}, 'Interpreter', 'latex', ...
                    'Location', 'northeastoutside');
                hold(ax, 'off');
            end
            if n > 1
                linkaxes(axList(1:n), 'x');
            end
            for k = 1:n
                xlim(axList(k), [0 L]);
            end
        end

        %% ========================= Poutre : déformée =========================
        function [axAlpha, axV] = deflection(axAlpha, axV, model, d)
            %DEFLECTION Rotation α(s) et déformée v(s) par les différentes méthodes.
            %   [axAlpha, axV] = PlotEngine.deflection(axAlpha, axV, model, d)
            %   d : résultat de SolicitationsEngine.deflection (SI). Tracés : intégration (exacte,
            %   trait plein), aires (tirets), Castigliano (marqueurs, avec et sans tranchant),
            %   Mohr (marqueurs), poutre non déformée, appuis et flèche maximale annotée.
            %   Unités affichées : mrad et mm. Si les deux axes sont vides, une figure est créée ;
            %   si un seul est vide, seul l'autre est tracé.
            if ~isstruct(d) || ~isfield(d, 's')
                error('MecaStruct:PlotEngine:invalidInput', 'd doit être un résultat de SolicitationsEngine.deflection.');
            end
            if isempty(axAlpha) && isempty(axV)
                f = figure('Name', 'Déformée');
                tl = tiledlayout(f, 2, 1, 'TileSpacing', 'compact');
                axAlpha = nexttile(tl);
                axV = nexttile(tl);
            end
            L = double(model.L);
            s = d.s(:).';
            isXZ = isfield(d, 'plane') && strcmpi(char(d.plane), 'xz');
            if isXZ
                vName = 'w'; aName = '\beta';
            else
                vName = 'v'; aName = '\alpha';
            end
            cI = [0.00 0.45 0.74];
            cA = [0.85 0.33 0.10];
            cC = [0.47 0.67 0.19];
            cS = [0.49 0.18 0.56];
            cM = [0.93 0.69 0.13];
            sup = peArr(model, 'supports');
            supX = arrayfun(@(q) q.pos, sup);

            if ~isempty(axAlpha)
                ax = peAxes(axAlpha);
                axAlpha = ax;
                fg = ax.XColor;
                hh = gobjects(0); lab = {};
                plot(ax, [0 L], [0 0], '-', 'Color', fg, 'LineWidth', 0.8);
                if peHas(d, 'integration', 'alpha')
                    hh(end+1) = plot(ax, s, 1e3 * d.integration.alpha(:).', '-', 'Color', cI, 'LineWidth', 2);
                    lab{end+1} = ['$' aName '(s)$ int\''{e}gration'];
                end
                if peHas(d, 'aires', 'alpha')
                    hh(end+1) = plot(ax, s, 1e3 * d.aires.alpha(:).', '--', 'Color', cA, 'LineWidth', 1.5);
                    lab{end+1} = ['$' aName '(s)$ aires'];
                end
                if peHas(d, 'castigliano', 'alpha') && peHas(d, 'castigliano', 's0')
                    hh(end+1) = plot(ax, d.castigliano.s0(:).', 1e3 * d.castigliano.alpha(:).', 'o', 'Color', cC, ...
                        'MarkerFaceColor', cC, 'MarkerSize', 7, 'MarkerIndices', peMk(numel(d.castigliano.s0)));
                    lab{end+1} = 'Castigliano';
                end
                xlim(ax, [0 L]);
                title(ax, ['Rotation $' aName '(s) = d' vName '/ds$'], 'Interpreter', 'latex');
                ylabel(ax, ['$' aName '$ (mrad)'], 'Interpreter', 'latex');
                xlabel(ax, '$s$ (m)', 'Interpreter', 'latex');
                if ~isempty(hh)
                    legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'southoutside', 'NumColumns', 3);   % hors du tracé : ne cache pas la courbe
                end
                hold(ax, 'off');
            end

            if ~isempty(axV)
                ax = peAxes(axV);
                axV = ax;
                fg = ax.XColor;
                hh = gobjects(0); lab = {};
                hh(end+1) = plot(ax, [0 L], [0 0], '-', 'Color', [0.6 0.6 0.6], 'LineWidth', 4);
                lab{end+1} = 'Poutre non d\''{e}form\''{e}e';
                if ~isempty(supX)
                    plot(ax, supX, zeros(size(supX)), '^', 'Color', fg, 'MarkerFaceColor', [0.8 0.8 0.8], 'MarkerSize', 9);
                end
                vAll = 0;
                if peHas(d, 'integration', 'v')
                    vI = 1e3 * d.integration.v(:).';
                    vAll = [vAll vI];
                    hh(end+1) = plot(ax, s, vI, '-', 'Color', cI, 'LineWidth', 2);
                    lab{end+1} = 'Int\''{e}gration (exacte)';
                end
                if peHas(d, 'aires', 'v')
                    hh(end+1) = plot(ax, s, 1e3 * d.aires.v(:).', '--', 'Color', cA, 'LineWidth', 1.5);
                    lab{end+1} = 'Aires';
                end
                if peHas(d, 'castigliano', 's0')
                    c0 = d.castigliano.s0(:).';
                    if peHas(d, 'castigliano', 'vBending')
                        hh(end+1) = plot(ax, c0, 1e3 * d.castigliano.vBending(:).', 'o', 'Color', cC, ...
                            'MarkerFaceColor', cC, 'MarkerSize', 7, 'MarkerIndices', peMk(numel(d.castigliano.s0)));
                        lab{end+1} = 'Castigliano (flexion)';
                    end
                    if peHas(d, 'castigliano', 'vTotal') && (~isfield(d.castigliano, 'vShear') || any(d.castigliano.vShear(:) ~= 0))   % sans effort tranchant, vTotal = flexion
                        vT = 1e3 * d.castigliano.vTotal(:).';
                        vAll = [vAll vT];
                        hh(end+1) = plot(ax, c0, vT, 's', 'Color', cS, 'MarkerSize', 10, 'LineWidth', 1.5, 'MarkerIndices', peMk(numel(c0)));
                        lab{end+1} = 'Castigliano (+ tranchant)';
                    end
                end
                if peHas(d, 'mohr', 's0') && peHas(d, 'mohr', 'v')
                    hh(end+1) = plot(ax, d.mohr.s0(:).', 1e3 * d.mohr.v(:).', 'x', 'Color', cM, 'MarkerSize', 11, 'LineWidth', 2);
                    lab{end+1} = 'Int\''{e}grales de Mohr';
                end
                if peHas(d, 'integration', 'sAtFmax') && peHas(d, 'integration', 'v')
                    sf = d.integration.sAtFmax(1);
                    vf = interp1(s, 1e3 * d.integration.v(:).', sf);
                    plot(ax, sf, vf, 'p', 'Color', cS, 'MarkerFaceColor', cS, 'MarkerSize', 12);
                    plot(ax, [sf sf], [0 vf], ':', 'Color', cS, 'LineWidth', 1.2);
                    lbl = sprintf('$f_{max} = %s$ mm en $s = %s$ m', peNum(abs(vf)), peNum(sf));
                end
                lo = min(vAll); hi = max(vAll);
                if hi - lo == 0
                    hi = 1; lo = -1;
                end
                ylim(ax, [lo - 0.3 * (hi - lo), hi + 0.3 * (hi - lo)]);
                xlim(ax, [0 L]);
                if exist('lbl', 'var')
                    % étiquette sous le minimum de la flèche, dans la marge libre : aucun marqueur ni courbe dessous
                    yl = ylim(ax);
                    text(ax, sf, vf - 0.06 * (yl(2) - yl(1)), lbl, 'Interpreter', 'latex', 'Color', cS, 'VerticalAlignment', 'top', ...
                        'HorizontalAlignment', 'center', 'FontSize', 11, 'BackgroundColor', ax.Color, 'Margin', 1);
                end
                title(ax, [peTx('Déformée') ' $' vName '(s)$'], 'Interpreter', 'latex');
                ylabel(ax, ['$' vName '$ (mm)'], 'Interpreter', 'latex');
                xlabel(ax, '$s$ (m)', 'Interpreter', 'latex');
                legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'southoutside', 'NumColumns', 3);
                hold(ax, 'off');
            end
            if ~isempty(axAlpha) && ~isempty(axV)
                linkaxes([axAlpha axV], 'x');
                xlim(axAlpha, [0 L]);
                xlim(axV, [0 L]);
            end
        end

        %% ========================= Section droite =========================
        function ax = section(ax, sec, P)
            %SECTION Géométrie de la section droite : contour, G, axes (G,y,z), axes principaux, cotes.
            %   ax = PlotEngine.section(ax, sec)
            %   ax = PlotEngine.section(ax, sec, P)
            %   sec : section (§2 du contrat) ; P : propriétés (GeometryEngine.analytical/integral/
            %   tabulated) ; si P est absent, GeometryEngine.analytical(sec) est utilisé.
            %   Dessin en mm, z horizontal, y vertical, repère O1 (coin bas-gauche).
            if nargin < 3 || isempty(P)
                P = GeometryEngine.analytical(sec);
            end
            ax = peAxes(ax);
            fg = ax.XColor;
            out = GeometryEngine.outline(sec);
            k = 1e3;
            ps = polyshape();
            for i = 1:numel(out.outer)
                o = out.outer{i}(1:end-1, :) * k;
                ps = union(ps, polyshape(o(:, 1), o(:, 2), 'Simplify', false));
            end
            for i = 1:numel(out.holes)
                o = out.holes{i}(1:end-1, :) * k;
                ps = subtract(ps, polyshape(o(:, 1), o(:, 2), 'Simplify', false));
            end
            hS = plot(ax, ps, 'FaceColor', [0.55 0.70 0.90], 'FaceAlpha', 0.6, 'EdgeColor', fg, 'LineWidth', 1.5);
            bb = out.bbox * k;               % [zmin zmax ymin ymax]
            W = bb(2) - bb(1);
            H = bb(4) - bb(3);
            D = max(W, H);
            zG = P.zG * k;
            yG = P.yG * k;
            hs = 0.035 * D;
            % axes (G, z, y)
            cAx = [0.85 0.15 0.15];
            hA = peArrow(ax, [bb(1) - 0.12 * D, yG], [bb(2) + 0.18 * D, yG], cAx, hs, 1.2);
            peArrow(ax, [zG, bb(3) - 0.12 * D], [zG, bb(4) + 0.18 * D], cAx, hs, 1.2);
            text(ax, bb(2) + 0.19 * D, yG, '$z$', 'Interpreter', 'latex', 'Color', cAx, 'FontSize', 13, ...
                'VerticalAlignment', 'middle');
            text(ax, zG, bb(4) + 0.19 * D, '$y$', 'Interpreter', 'latex', 'Color', cAx, 'FontSize', 13, ...
                'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');
            hG = plot(ax, zG, yG, 'o', 'Color', fg, 'MarkerFaceColor', cAx, 'MarkerSize', 8);
            text(ax, zG + 0.02 * D, yG + 0.02 * D, '$G$', 'Interpreter', 'latex', 'FontSize', 13, 'Color', fg, ...
                'VerticalAlignment', 'bottom');
            hh = [hS hG hA];
            lab = {'Section', '$G$', 'Axes $(G, y, z)$'};
            % axes principaux
            if isfield(P, 'Iyz') && abs(P.Iyz) > 1e-9 * max(P.Iz, P.Iy)
                a = P.alphaP;
                cP = [0.10 0.55 0.20];
                Lp = 0.75 * D;
                u1 = [cos(a) sin(a)];
                u2 = [-sin(a) cos(a)];
                hP = plot(ax, zG + Lp * [-u1(1) u1(1)], yG + Lp * [-u1(2) u1(2)], '--', 'Color', cP, 'LineWidth', 1.4);
                plot(ax, zG + Lp * [-u2(1) u2(1)], yG + Lp * [-u2(2) u2(2)], '--', 'Color', cP, 'LineWidth', 1.4);
                text(ax, zG + 1.02 * Lp * u1(1), yG + 1.02 * Lp * u1(2), '$1$', 'Interpreter', 'latex', 'Color', cP, 'FontSize', 12);
                text(ax, zG + 1.02 * Lp * u2(1), yG + 1.02 * Lp * u2(2), '$2$', 'Interpreter', 'latex', 'Color', cP, 'FontSize', 12);
                th = linspace(0, a, 30);
                plot(ax, zG + 0.3 * D * cos(th), yG + 0.3 * D * sin(th), '-', 'Color', cP, 'LineWidth', 1);
                text(ax, zG + 0.32 * D * cos(a / 2), yG + 0.32 * D * sin(a / 2), ...
                    sprintf('$\\alpha_P = %s^\\circ$', peNum(a * 180 / pi)), 'Interpreter', 'latex', 'Color', cP, 'FontSize', 10);
                hh(end+1) = hP;
                lab{end+1} = sprintf('Axes principaux ($I_1 = %s$, $I_2 = %s$ mm$^4$)', peNum(P.I1 * 1e12), peNum(P.I2 * 1e12));
            end
            % cotes
            cD = fg;
            peDim(ax, [bb(1) bb(3) - 0.25 * D], [bb(2) bb(3) - 0.25 * D], sprintf('%s mm', peNum(W)), 'below', cD, hs);
            peDim(ax, [bb(1) - 0.25 * D bb(3)], [bb(1) - 0.25 * D bb(4)], sprintf('%s mm', peNum(H)), 'left', cD, hs);
            peDim(ax, [bb(2) + 0.08 * D bb(3)], [bb(2) + 0.08 * D yG], sprintf('$y_G = %s$', peNum(yG - bb(3))), 'right', cD, hs);
            peDim(ax, [bb(1) bb(4) + 0.08 * D], [zG bb(4) + 0.08 * D], sprintf('$z_G = %s$', peNum(zG - bb(1))), 'above', cD, hs);
            axis(ax, 'equal');
            xlim(ax, [bb(1) - 0.45 * D, bb(2) + 0.45 * D]);
            ylim(ax, [bb(3) - 0.40 * D, bb(4) + 0.30 * D]);
            xlabel(ax, '$z$ (mm)', 'Interpreter', 'latex');
            ylabel(ax, '$y$ (mm)', 'Interpreter', 'latex');
            title(ax, {sprintf('Section : $S = %s$ mm$^2$', peNum(P.S * 1e6)), ...
                sprintf('$I_{Gz} = %s$ mm$^4$, $I_{Gy} = %s$ mm$^4$, $I_{yz} = %s$ mm$^4$', ...
                peNum(P.Iz * 1e12), peNum(P.Iy * 1e12), peNum(peField(P, 'Iyz') * 1e12))}, 'Interpreter', 'latex');
            legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'southoutside');
            hold(ax, 'off');
        end

        %% ========================= Section : contraintes =========================
        function [axSigma, axTau] = sectionStress(axSigma, axTau, sec, P, bend, jour)
            %SECTIONSTRESS Profils de contraintes dans la section : σxx(y) linéaire et τ(y) de Jourawski.
            %   [axSigma, axTau] = PlotEngine.sectionStress(axSigma, axTau, sec, P, bend, jour)
            %   bend : résultat de SolicitationsEngine.bendingStress (yProfile, sigmaProfile,
            %          neutralAxis) ; jour : résultat de SolicitationsEngine.jourawski (y, tau,
            %          tauMax, yAtMax, tauMoy, tauParabola). y depuis G, affichage en mm et MPa.
            %   bend ou jour vide → l'axe correspondant n'est pas tracé. Axes vides → figure créée.
            %   sec et P servent au contour de la section (hauteur) en arrière-plan.
            if nargin < 6
                jour = [];
            end
            if isempty(axSigma) && isempty(axTau)
                f = figure('Name', 'Contraintes dans la section');
                tl = tiledlayout(f, 1, 2, 'TileSpacing', 'compact');
                axSigma = nexttile(tl);
                axTau = nexttile(tl);
            end
            if isempty(P)
                P = GeometryEngine.analytical(sec);
            end
            yTopS = P.vyTop * 1e3;
            yBotS = -P.vyBot * 1e3;
            cT = [0.85 0.15 0.15];
            cC = [0.00 0.45 0.74];
            if ~isempty(axSigma) && ~isempty(bend)
                ax = peAxes(axSigma);
                axSigma = ax;
                fg = ax.XColor;
                y = bend.yProfile(:).' * 1e3;
                sg = bend.sigmaProfile(:).' / 1e6;
                sp = max(sg, 0);
                sn = min(sg, 0);
                h1 = fill(ax, [sp zeros(size(sp))], [y fliplr(y)], cT, 'FaceAlpha', 0.3, 'EdgeColor', 'none');
                h2 = fill(ax, [sn zeros(size(sn))], [y fliplr(y)], cC, 'FaceAlpha', 0.3, 'EdgeColor', 'none');
                plot(ax, [0 0], [yBotS yTopS], '-', 'Color', fg, 'LineWidth', 2.5);
                h3 = plot(ax, sg, y, '-', 'Color', fg, 'LineWidth', 1.8);
                hh = [h3 h1 h2];
                lab = {'$\sigma_{xx}(y)$ \`{a} $z = 0$', 'Traction', 'Compression'};
                sMax = max(abs(sg));
                if sMax == 0
                    sMax = 1;
                end
                % axe neutre (z = 0) : a + b·y = 0
                if isfield(bend, 'neutralAxis') && isstruct(bend.neutralAxis) && isfield(bend.neutralAxis, 'b') ...
                        && bend.neutralAxis.b ~= 0
                    yn = -bend.neutralAxis.a / bend.neutralAxis.b * 1e3;
                    if yn >= yBotS - 1e-9 && yn <= yTopS + 1e-9
                        hN = plot(ax, 1.3 * sMax * [-1 1], [yn yn], '--', 'Color', [0.10 0.55 0.20], 'LineWidth', 1.5);
                        hh(end+1) = hN;
                        lab{end+1} = sprintf('Axe neutre ($y = %s$ mm)', peNum(yn));
                    end
                end
                [~, iT] = max(y);
                [~, iB] = min(y);
                text(ax, sg(iT), y(iT), sprintf(' $%s$ MPa', peNum(sg(iT))), 'Interpreter', 'latex', 'Color', fg, ...
                    'VerticalAlignment', 'bottom', 'HorizontalAlignment', peSignAlign(sg(iT)), 'FontSize', 10);
                text(ax, sg(iB), y(iB), sprintf(' $%s$ MPa', peNum(sg(iB))), 'Interpreter', 'latex', 'Color', fg, ...
                    'VerticalAlignment', 'top', 'HorizontalAlignment', peSignAlign(sg(iB)), 'FontSize', 10);
                xlim(ax, 1.5 * sMax * [-1 1]);
                dy = yTopS - yBotS;
                ylim(ax, [yBotS - 0.15 * dy, yTopS + 0.15 * dy]);
                xlabel(ax, '$\sigma_{xx}$ (MPa)', 'Interpreter', 'latex');
                ylabel(ax, '$y$ (mm)', 'Interpreter', 'latex');
                title(ax, 'Contrainte normale $\sigma_{xx}(y)$', 'Interpreter', 'latex');
                legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'southoutside');
                hold(ax, 'off');
            end
            if ~isempty(axTau) && ~isempty(jour)
                ax = peAxes(axTau);
                axTau = ax;
                fg = ax.XColor;
                y = jour.y(:).' * 1e3;
                t = jour.tau(:).' / 1e6;
                fill(ax, [t zeros(size(t))], [y fliplr(y)], [0.49 0.18 0.56], 'FaceAlpha', 0.25, 'EdgeColor', 'none');
                plot(ax, [0 0], [yBotS yTopS], '-', 'Color', fg, 'LineWidth', 2.5);
                h1 = plot(ax, t, y, '-', 'Color', [0.49 0.18 0.56], 'LineWidth', 1.8);
                hh = h1;
                lab = {'Jourawski $\tau(y) = \frac{T\,Q(y)}{I_z\,b(y)}$'};
                if isfield(jour, 'tauParabola') && any(isfinite(jour.tauParabola(:)))
                    hP = plot(ax, jour.tauParabola(:).' / 1e6, y, ':', 'Color', fg, 'LineWidth', 1.8);
                    hh(end+1) = hP;
                    lab{end+1} = 'Parabole $\frac{3T}{2S}\left(1 - \frac{4y^2}{h^2}\right)$';
                end
                if isfield(jour, 'tauMoy')
                    hm = plot(ax, jour.tauMoy / 1e6 * [1 1], [yBotS yTopS], '--', 'Color', [0.10 0.55 0.20], 'LineWidth', 1.2);
                    hh(end+1) = hm;
                    lab{end+1} = sprintf('$\\tau_{moy} = T/S = %s$ MPa', peNum(jour.tauMoy / 1e6));
                end
                tM = jour.tauMax / 1e6;
                yM = jour.yAtMax * 1e3;
                plot(ax, tM, yM, 'o', 'Color', [0.49 0.18 0.56], 'MarkerFaceColor', [0.49 0.18 0.56], 'MarkerSize', 7);
                text(ax, tM, yM + 0.05 * (yTopS - yBotS), sprintf('$\\tau_{max} = %s$ MPa', peNum(tM)), 'Interpreter', 'latex', ...
                    'Color', fg, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontSize', 10, ...
                    'BackgroundColor', ax.Color, 'Margin', 0.5);
                tAbs = max(abs([t tM]));
                if tAbs == 0
                    tAbs = 1;
                end
                if tM >= 0
                    xlim(ax, [-0.15 * tAbs, 1.6 * tAbs]);
                else
                    xlim(ax, [-1.6 * tAbs, 0.15 * tAbs]);
                end
                dy = yTopS - yBotS;
                ylim(ax, [yBotS - 0.15 * dy, yTopS + 0.15 * dy]);
                xlabel(ax, '$\tau_{xy}$ (MPa)', 'Interpreter', 'latex');
                ylabel(ax, '$y$ (mm)', 'Interpreter', 'latex');
                title(ax, 'Contrainte de cisaillement $\tau(y)$', 'Interpreter', 'latex');
                legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'southoutside');
                hold(ax, 'off');
            end
        end

        %% ========================= Flambage =========================
        function ax = bucklingCurve(ax, curve, b)
            %BUCKLINGCURVE Courbe de stabilité σcr(λ) : palier, Euler, Rankine, dimensionnement.
            %   ax = PlotEngine.bucklingCurve(ax, curve)
            %   ax = PlotEngine.bucklingCurve(ax, curve, b)
            %   curve : BucklingEngine.stabilityCurve ; b : BucklingEngine.analyze (optionnel) →
            %   point critique (λ, Pcrit/S) et point de fonctionnement (λ, P/S) si P fourni.
            %   Zones de régime ombrées et annotées, droites λ = 20 et λ = λlim. Affichage en MPa.
            if nargin < 3
                b = [];
            end
            ax = peAxes(ax);
            fg = ax.XColor;
            lam = curve.lambda(:).';
            Re = curve.Re / 1e6;
            lc = curve.lambdaCompression;
            ll = curve.lambdaLim;
            lMax = max(lam);
            yMax = 1.35 * Re;
            % zones
            zc = {[0.75 0.75 0.75], [0.93 0.69 0.13], [0.30 0.60 0.90]};
            zx = [0, min(lc, ll); min(lc, ll), ll; ll, max(ll, lMax)];
            % Noms des domaines : poutre trapue (courte), moyenne, élancée (longue), avec leur formule.
            zl = {sprintf('Poutre trapue (courte)\nλ < %s : compression simple', peNum(lc)), ...
                sprintf('Poutre moyenne\n%s ≤ λ < λlim\nRankine', peNum(lc)), ...
                sprintf('Poutre élancée (longue)\nλ ≥ λlim : Euler')};
            zn = {sprintf('Poutre trapue (courte) : λ < %s', peNum(lc)), 'Poutre moyenne : Rankine', 'Poutre élancée (longue) : Euler'};
            active = 0;
            if ~isempty(b) && isstruct(b) && isfield(b, 'regime')
                active = find(strcmp(char(b.regime), {'compression', 'rankine', 'euler'}), 1);
            end
            for k = 1:3
                if zx(k, 2) > zx(k, 1)
                    patch(ax, [zx(k, 1) zx(k, 2) zx(k, 2) zx(k, 1)], [0 0 yMax yMax], zc{k}, ...
                        'FaceAlpha', 0.16 + 0.10 * (k == active), 'EdgeColor', 'none', 'HandleVisibility', 'off');
                    col = fg;
                    txt = zl{k};
                    if k == active
                        col = [0.85 0.15 0.15];
                        txt = sprintf('%s\n(votre poutre)', zl{k});
                    end
                    if zx(k, 2) - zx(k, 1) < 0.15 * lMax
                        % zone étroite : étiquette verticale
                        t1 = zn{k};
                        if k == active
                            t1 = [t1 '  (votre poutre)'];
                        end
                        % sous le palier (σ = Re) : cette zone est vide, rien n'y est tracé
                        text(ax, mean(zx(k, :)), 0.45 * yMax, t1, 'Interpreter', 'none', 'Color', col, ...
                            'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', 'FontSize', 10, ...
                            'FontWeight', 'bold', 'Rotation', 90);
                    else
                        text(ax, mean(zx(k, :)), 0.985 * yMax, txt, 'Interpreter', 'none', 'Color', col, ...
                            'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', 'FontSize', 10, ...
                            'FontWeight', 'bold');
                    end
                end
            end
            hP = plot(ax, lam, curve.sigmaPalier / 1e6, '--', 'Color', [0.4 0.4 0.4], 'LineWidth', 1.2);
            sE = curve.sigmaEuler / 1e6;
            sE(sE > yMax) = NaN;
            hE = plot(ax, lam, sE, ':', 'Color', [0.00 0.45 0.74], 'LineWidth', 1.6);
            hR = plot(ax, lam, curve.sigmaRankine / 1e6, '-.', 'Color', [0.85 0.33 0.10], 'LineWidth', 1.4);
            sD = curve.sigmaDesign / 1e6;
            lD = lam;
            if isfield(curve, 'zone')
                jmp = find(diff(curve.zone) ~= 0);
                for j = numel(jmp):-1:1
                    lD = [lD(1:jmp(j)) NaN lD(jmp(j)+1:end)];
                    sD = [sD(1:jmp(j)) NaN sD(jmp(j)+1:end)];
                end
            end
            hD = plot(ax, lD, sD, '-', 'Color', fg, 'LineWidth', 2.5);
            % étiquettes des seuils au pied de la droite, sur fond d'axe : elles ne traversent ni courbe ni droite
            bg = {'BackgroundColor', ax.Color, 'Margin', 0.5};
            xline(ax, lc, '-', 'HandleVisibility', 'off', 'Color', fg);
            xline(ax, ll, '-', 'HandleVisibility', 'off', 'Color', fg);
            text(ax, lc, 0.02 * yMax, sprintf('$\\lambda = %s$', peNum(lc)), 'Interpreter', 'latex', 'Color', fg, 'Rotation', 90, ...
                'HorizontalAlignment', 'left', 'VerticalAlignment', 'top', 'FontSize', 10);   % à droite de la droite (texte tourné)
            text(ax, ll, 0.02 * yMax, sprintf('$\\lambda_{lim} = %s$', peNum(ll)), 'Interpreter', 'latex', 'Color', fg, 'Rotation', 90, ...
                'HorizontalAlignment', 'left', 'VerticalAlignment', 'top', 'FontSize', 10);
            hh = [hP hE hR hD];
            lab = {'Palier $\sigma = R_e$', 'Euler $\frac{\pi^2 E}{\lambda^2}$', ...
                'Rankine $\frac{R_e}{1+(\lambda/\lambda_{lim})^2}$', 'Dimensionnement'};
            if ~isempty(b) && isstruct(b) && isfield(b, 'lambda')
                sc = b.Pcrit / b.S / 1e6;
                hc = plot(ax, b.lambda, sc, 'p', 'Color', [0.85 0.15 0.15], 'MarkerFaceColor', [0.85 0.15 0.15], 'MarkerSize', 13);
                text(ax, b.lambda, sc + 0.05 * yMax, sprintf('$\\lambda = %s$, $\\sigma_{cr} = %s$ MPa', peNum(b.lambda), peNum(sc)), ...
                    'Interpreter', 'latex', 'Color', fg, 'VerticalAlignment', 'bottom', ...
                    'HorizontalAlignment', peHAlign(b.lambda, lMax), 'FontSize', 10, bg{:});
                hh(end+1) = hc;
                rg = char(b.regime);
                lab{end+1} = sprintf('Point critique (%s)', [upper(rg(1)) rg(2:end)]);
                if isfield(b, 'sigmaApplied') && isfinite(b.sigmaApplied)
                    sa = b.sigmaApplied / 1e6;
                    ha = plot(ax, b.lambda, sa, 'o', 'Color', [0.10 0.55 0.20], 'MarkerFaceColor', [0.10 0.55 0.20], 'MarkerSize', 9);
                    plot(ax, [b.lambda b.lambda], [sa sc], ':', 'Color', [0.10 0.55 0.20], 'LineWidth', 1.2, 'HandleVisibility', 'off');
                    text(ax, b.lambda, sa - 0.05 * yMax, sprintf('$\\sigma = P/S = %s$ MPa', peNum(sa)), 'Interpreter', 'latex', ...
                        'Color', [0.10 0.55 0.20], 'VerticalAlignment', 'top', 'HorizontalAlignment', peHAlign(b.lambda, lMax), ...
                        'FontSize', 10, bg{:});
                    hh(end+1) = ha;
                    lab{end+1} = 'Point de fonctionnement';
                end
            end
            xlim(ax, [0 lMax]);
            ylim(ax, [0 yMax]);
            xlabel(ax, '$\lambda = L''/r_{min}$', 'Interpreter', 'latex');
            ylabel(ax, '$\sigma_{cr}$ (MPa)', 'Interpreter', 'latex');
            title(ax, sprintf('Courbe de flambage ($E = %s$ GPa, $R_e = %s$ MPa)', peNum(curve.E / 1e9), peNum(Re)), ...
                'Interpreter', 'latex');
            legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'southoutside', 'NumColumns', 3);
            hold(ax, 'off');
        end

        %% ========================= Cercle de Mohr 2D =========================
        function ax = mohr2D(ax, r2D, theta)
            %MOHR2D Cercle de Mohr plan : A, B, centre δ, rayon ρ, σ1, σ2, angle 2θ, point de facette.
            %   ax = PlotEngine.mohr2D(ax, r2D)
            %   ax = PlotEngine.mohr2D(ax, r2D, theta)
            %   r2D : TensorAndCriteriaEngine.plane2D (MPa affichés) ou plane2DStrain (µdéf, ε et γ/2).
            %   theta (rad) : facette tracée (défaut r2D.theta si scalaire non nul). Le point de la
            %   facette se déduit de A par une rotation de 2θ (sens horaire) autour du centre.
            if nargin < 3 || isempty(theta)
                theta = [];
                if isfield(r2D, 'theta') && isscalar(r2D.theta) && r2D.theta ~= 0
                    theta = r2D.theta;
                end
            end
            ax = peAxes(ax);
            fg = ax.XColor;
            isStrain = isfield(r2D, 'kind') && strcmpi(r2D.kind, 'strain');
            if isStrain
                k = 1e6; un = '$\mu$d\''{e}f'; sN = '\varepsilon'; tN = '\gamma/2';
                n1 = '\varepsilon_1'; n2 = '\varepsilon_2';
                Alab = '$A(\varepsilon_{xx}, \varepsilon_{xy})$'; Blab = '$B(\varepsilon_{yy}, -\varepsilon_{xy})$';
            else
                k = 1e-6; un = 'MPa'; sN = '\sigma'; tN = '\tau';
                n1 = '\sigma_1'; n2 = '\sigma_2';
                Alab = '$A(\sigma_{xx}, \sigma_{xy})$'; Blab = '$B(\sigma_{yy}, -\sigma_{xy})$';
            end
            c = r2D.delta * k;
            R = r2D.rho * k;
            A = r2D.pointA * k;
            B = r2D.pointB * k;
            ext = max([abs(c) + R, R, 1e-12]);
            hs = 0.04 * ext;
            peArrow(ax, [min(0, c - R) - 0.15 * ext, 0], [max(0, c + R) + 0.2 * ext, 0], fg, hs, 1);
            peArrow(ax, [0, -1.25 * max(R, 0.2 * ext)], [0, 1.3 * max(R, 0.2 * ext)], fg, hs, 1);
            text(ax, max(0, c + R) + 0.21 * ext, 0, ['$' sN '$'], 'Interpreter', 'latex', 'Color', fg, 'FontSize', 13);
            text(ax, 0.02 * ext, 1.3 * max(R, 0.2 * ext), ['$' tN '$'], 'Interpreter', 'latex', 'Color', fg, ...
                'FontSize', 13, 'VerticalAlignment', 'top');
            phi = linspace(0, 2 * pi, 361);
            hC = plot(ax, c + R * cos(phi), R * sin(phi), '-', 'Color', [0.00 0.45 0.74], 'LineWidth', 2);
            plot(ax, [A(1) B(1)], [A(2) B(2)], '-', 'Color', fg, 'LineWidth', 1);
            hA = plot(ax, A(1), A(2), 'o', 'Color', [0.85 0.15 0.15], 'MarkerFaceColor', [0.85 0.15 0.15], 'MarkerSize', 8);
            hB = plot(ax, B(1), B(2), 's', 'Color', [0.10 0.55 0.20], 'MarkerFaceColor', [0.10 0.55 0.20], 'MarkerSize', 8);
            % étiquettes sur fond d'axe et décalées des marqueurs, axes et droites : aucune superposition
            bg = {'BackgroundColor', ax.Color, 'Margin', 0.5};
            % A et B : étiquette radiale, à l'extérieur du cercle (ne coupe ni le cercle ni les droites)
            for q = {A, Alab, [0.85 0.15 0.15]; B, Blab, [0.10 0.55 0.20]}.'
                u = (q{1} - [c 0]) / max(R, eps);
                text(ax, q{1}(1) + 0.05 * ext * u(1), q{1}(2) + 0.05 * ext * u(2), q{2}, 'Interpreter', 'latex', 'Color', q{3}, ...
                    'FontSize', 10, 'VerticalAlignment', peVAlign(-u(2)), 'HorizontalAlignment', peSignAlign(u(1)));
            end
            hD = plot(ax, c, 0, '+', 'Color', fg, 'MarkerSize', 10, 'LineWidth', 1.5);
            text(ax, c, -0.06 * ext, sprintf('$\\delta = %s$', peNum(c)), 'Interpreter', 'latex', 'Color', fg, ...
                'VerticalAlignment', 'top', 'HorizontalAlignment', 'center', 'FontSize', 10, bg{:});
            plot(ax, [c c + R * cos(pi / 4)], [0 R * sin(pi / 4)], '-', 'Color', fg, 'LineWidth', 0.8);
            text(ax, c + 0.55 * R * cos(pi / 4), 0.55 * R * sin(pi / 4), sprintf('$\\rho = %s$', peNum(R)), ...
                'Interpreter', 'latex', 'Color', fg, 'HorizontalAlignment', 'right', 'VerticalAlignment', 'bottom', 'FontSize', 10, bg{:});
            h1 = plot(ax, [c + R, c - R], [0 0], 'd', 'Color', fg, 'MarkerFaceColor', [0.93 0.69 0.13], 'MarkerSize', 8);
            text(ax, c + R + 0.03 * ext, 0.05 * ext, sprintf('$%s = %s$', n1, peNum(c + R)), 'Interpreter', 'latex', 'Color', fg, ...
                'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'left', 'FontSize', 10);
            text(ax, c - R - 0.03 * ext, 0.05 * ext, sprintf('$%s = %s$', n2, peNum(c - R)), 'Interpreter', 'latex', 'Color', fg, ...
                'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'right', 'FontSize', 10);
            hh = [hC hA hB hD h1];
            lab = {['Cercle de Mohr (' un ')'], '$A$', '$B$', '$\delta$', ['$' n1 '$, $' n2 '$']};
            if ~isempty(theta) && R > 0
                d0 = A - [c 0];
                a0 = atan2(d0(2), d0(1));
                a1 = a0 - 2 * theta;
                Pf = [c + R * cos(a1), R * sin(a1)];
                ang = linspace(a0, a1, 60);
                plot(ax, c + 0.35 * R * cos(ang), 0.35 * R * sin(ang), '-', 'Color', [0.49 0.18 0.56], 'LineWidth', 1.5);
                peArrow(ax, [c + 0.35 * R * cos(ang(end-1)), 0.35 * R * sin(ang(end-1))], ...
                    [c + 0.35 * R * cos(ang(end)), 0.35 * R * sin(ang(end))], [0.49 0.18 0.56], 0.6 * hs, 1.5);
                plot(ax, [c Pf(1)], [0 Pf(2)], '--', 'Color', [0.49 0.18 0.56], 'LineWidth', 1);
                plot(ax, [c A(1)], [0 A(2)], '--', 'Color', [0.85 0.15 0.15], 'LineWidth', 1);
                am = (a0 + a1) / 2;
                text(ax, c + 0.42 * R * cos(am), 0.42 * R * sin(am), sprintf('$2\\theta = %s^\\circ$', peNum(2 * theta * 180 / pi)), ...
                    'Interpreter', 'latex', 'Color', [0.49 0.18 0.56], 'FontSize', 10, bg{:});
                hF = plot(ax, Pf(1), Pf(2), 'p', 'Color', [0.49 0.18 0.56], 'MarkerFaceColor', [0.49 0.18 0.56], 'MarkerSize', 13);
                if Pf(1) >= c
                    ha = 'right';
                else
                    ha = 'left';
                end
                up = 2 * (Pf(2) >= 0) - 1;
                if up > 0
                    va = 'bottom';
                else
                    va = 'top';
                end
                text(ax, Pf(1), Pf(2) + up * 0.09 * ext, sprintf('$%s = %s$, $%s = %s$', sN, peNum(Pf(1)), tN, peNum(Pf(2))), ...
                    'Interpreter', 'latex', 'Color', [0.49 0.18 0.56], 'FontSize', 10, 'VerticalAlignment', va, ...
                    'HorizontalAlignment', ha, bg{:});
                hh(end+1) = hF;
                lab{end+1} = sprintf('Facette $\\theta = %s^\\circ$', peNum(theta * 180 / pi));
            end
            axis(ax, 'equal');
            xl = [min(0, c - R) - 0.65 * ext, max(0, c + R) + 0.65 * ext];   % marges pour les étiquettes σ1, σ2, A, B hors du cercle
            yl = 1.45 * max(R, 0.2 * ext) * [-1 1];
            xlim(ax, xl);
            ylim(ax, yl);
            xlabel(ax, sprintf('$%s$ (%s)', sN, un), 'Interpreter', 'latex');
            ylabel(ax, sprintf('$%s$ (%s)', tN, un), 'Interpreter', 'latex');
            title(ax, 'Cercle de Mohr', 'Interpreter', 'latex');
            legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'eastoutside');
            hold(ax, 'off');
        end

        %% ========================= Tricercle de Mohr =========================
        function ax = mohr3D(ax, m3, point)
            %MOHR3D Tricercle de Mohr et zone admissible ombrée (entre le grand et les petits cercles).
            %   ax = PlotEngine.mohr3D(ax, m3)
            %   ax = PlotEngine.mohr3D(ax, m3, point)
            %   m3 : TensorAndCriteriaEngine.mohr3D ; point : [σn τ] (Pa) d'une facette (optionnel,
            %   ex. issu de TensorAndCriteriaEngine.facet). Affichage en MPa.
            if nargin < 3
                point = [];
            end
            ax = peAxes(ax);
            fg = ax.XColor;
            k = 1e-6;
            p = m3.pr * k;
            ce = m3.centers * k;
            ra = m3.radii * k;
            ext = max([abs(p), ra(3), 1e-12]);
            hh = gobjects(0); lab = {};
            % zone admissible : grand cercle moins les deux petits
            if ra(3) > 1e-12 * ext && max(ra(1:2)) < (1 - 1e-9) * ra(3)   % sinon zone réduite au grand cercle
                ps = peCirclePoly(ce(3), ra(3));
                for j = 1:2
                    if ra(j) > 1e-9 * ext
                        ps = subtract(ps, peCirclePoly(ce(j), ra(j)));
                    end
                end
                hZ = plot(ax, ps, 'FaceColor', [0.30 0.60 0.90], 'FaceAlpha', 0.25, 'EdgeColor', 'none');
                hh(end+1) = hZ; lab{end+1} = 'Zone admissible $(\sigma_n, \tau)$';
            end
            cols = {[0.85 0.33 0.10], [0.10 0.55 0.20], [0.00 0.45 0.74]};
            names = {'$(\sigma_I, \sigma_{II})$', '$(\sigma_{II}, \sigma_{III})$', '$(\sigma_I, \sigma_{III})$'};
            phi = linspace(0, 2 * pi, 361);
            for j = 1:3
                hh(end+1) = plot(ax, ce(j) + ra(j) * cos(phi), ra(j) * sin(phi), '-', 'Color', cols{j}, 'LineWidth', 1.8); %#ok<AGROW>
                lab{end+1} = ['Cercle ' names{j}]; %#ok<AGROW>
            end
            plot(ax, [min(0, p(3)) - 0.15 * ext, max(0, p(1)) + 0.15 * ext], [0 0], '-', 'Color', fg, 'LineWidth', 0.8);
            plot(ax, [0 0], 1.2 * max(ra(3), 0.2 * ext) * [-1 1], '-', 'Color', fg, 'LineWidth', 0.8);
            plot(ax, p, [0 0 0], 'o', 'Color', fg, 'MarkerFaceColor', fg, 'MarkerSize', 6);
            tn = {'\sigma_I', '\sigma_{II}', '\sigma_{III}'};
            va = {'top', 'bottom', 'top'};
            for j = 1:3
                if j == 2      % contraintes extrêmes : à l'extérieur du grand cercle ; la médiane, au point de tangence, sur fond d'axe
                    text(ax, p(j), 0.06 * ext, sprintf('$%s = %s$', tn{j}, peNum(p(j))), 'Interpreter', 'latex', 'Color', fg, ...
                        'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'center', 'FontSize', 10, 'BackgroundColor', ax.Color, 'Margin', 0.5);
                else
                    text(ax, p(j) + (2 - j) * 0.03 * ext, 0.05 * ext, sprintf('$%s = %s$', tn{j}, peNum(p(j))), 'Interpreter', 'latex', ...
                        'Color', fg, 'VerticalAlignment', 'bottom', 'HorizontalAlignment', peSignAlign(2 - j), 'FontSize', 10);
                end
            end
            if ra(3) > 0
                plot(ax, [ce(3) ce(3)], [0 ra(3)], ':', 'Color', fg, 'LineWidth', 1);
                text(ax, ce(3), ra(3), sprintf('$\\tau_{max} = %s$ MPa', peNum(ra(3))), 'Interpreter', 'latex', ...
                    'Color', fg, 'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'center', 'FontSize', 10, 'BackgroundColor', ax.Color, 'Margin', 0.5);
            end
            if ~isempty(point)
                q = point(:).' * k;
                hq = plot(ax, q(1), q(2), 'p', 'Color', [0.85 0.15 0.15], 'MarkerFaceColor', [0.85 0.15 0.15], 'MarkerSize', 13);
                text(ax, q(1), q(2) + 0.06 * ext, sprintf('$(%s, %s)$', peNum(q(1)), peNum(q(2))), 'Interpreter', 'latex', ...
                    'Color', [0.85 0.15 0.15], 'FontSize', 10, 'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'center', 'BackgroundColor', ax.Color, 'Margin', 0.5);
                hh(end+1) = hq; lab{end+1} = 'Facette';
            end
            axis(ax, 'equal');
            xlim(ax, [min(0, p(3)) - 0.6 * ext, max(0, p(1)) + 0.6 * ext]);
            ylim(ax, 1.3 * max(ra(3), 0.2 * ext) * [-1 1]);
            xlabel(ax, '$\sigma_n$ (MPa)', 'Interpreter', 'latex');
            ylabel(ax, '$\tau$ (MPa)', 'Interpreter', 'latex');
            title(ax, 'Tricercle de Mohr', 'Interpreter', 'latex');
            legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'eastoutside');
            hold(ax, 'off');
        end

        %% ========================= Lieux de plasticité =========================
        function ax = yieldLocus(ax, loci, point)
            %YIELDLOCUS Lieux de plasticité en contraintes planes : Tresca, Von Mises, Rankine.
            %   ax = PlotEngine.yieldLocus(ax, loci)
            %   ax = PlotEngine.yieldLocus(ax, loci, point)
            %   loci : TensorAndCriteriaEngine.yieldLoci ; point : [σ1 σ2] (Pa) de l'état de
            %   contrainte (optionnel). Affichage en MPa.
            if nargin < 3
                point = [];
            end
            ax = peAxes(ax);
            fg = ax.XColor;
            k = 1e-6;
            T = loci.tresca * k;
            V = loci.vonMises * k;
            Rk = loci.rankine * k;
            a = loci.sigmaAdm * k;
            ext = max([abs(Rk(:)); abs(V(:)); abs(T(:))]);
            if ~isempty(point)
                ext = max(ext, max(abs(point(:))) * k);
            end
            fill(ax, T(:, 1), T(:, 2), [0.85 0.33 0.10], 'FaceAlpha', 0.10, 'EdgeColor', 'none', 'HandleVisibility', 'off');
            plot(ax, 1.2 * ext * [-1 1], [0 0], '-', 'Color', fg, 'LineWidth', 0.8, 'HandleVisibility', 'off');
            plot(ax, [0 0], 1.2 * ext * [-1 1], '-', 'Color', fg, 'LineWidth', 0.8, 'HandleVisibility', 'off');
            plot(ax, 1.2 * ext * [-1 1], 1.2 * ext * [-1 1], ':', 'Color', [0.6 0.6 0.6], 'HandleVisibility', 'off');
            plot(ax, 1.2 * ext * [-1 1], 1.2 * ext * [1 -1], ':', 'Color', [0.6 0.6 0.6], 'HandleVisibility', 'off');
            hR = plot(ax, Rk(:, 1), Rk(:, 2), '-.', 'Color', [0.10 0.55 0.20], 'LineWidth', 1.5);
            hV = plot(ax, V(:, 1), V(:, 2), '-', 'Color', [0.00 0.45 0.74], 'LineWidth', 2);
            hT = plot(ax, T(:, 1), T(:, 2), '-', 'Color', [0.85 0.33 0.10], 'LineWidth', 2);
            hh = [hT hV hR];
            lab = {'Tresca (hexagone)', 'Von Mises (ellipse)', 'Contrainte normale max (carr\''{e})'};
            text(ax, a, 0, sprintf(' $%s$', peNum(a)), 'Interpreter', 'latex', 'Color', fg, 'FontSize', 10, ...
                'VerticalAlignment', 'top');
            text(ax, 0, a, sprintf(' $%s$', peNum(a)), 'Interpreter', 'latex', 'Color', fg, 'FontSize', 10, ...
                'VerticalAlignment', 'bottom');
            if ~isempty(point)
                q = point(:).' * k;
                hq = plot(ax, q(1), q(2), 'p', 'Color', [0.49 0.18 0.56], 'MarkerFaceColor', [0.49 0.18 0.56], 'MarkerSize', 14);
                plot(ax, [0 q(1)], [0 q(2)], '--', 'Color', [0.49 0.18 0.56], 'HandleVisibility', 'off');
                text(ax, q(1), q(2) - 0.07 * ext, sprintf('$(%s, %s)$', peNum(q(1)), peNum(q(2))), 'Interpreter', 'latex', ...
                    'Color', [0.49 0.18 0.56], 'FontSize', 10, 'VerticalAlignment', 'top', 'HorizontalAlignment', 'center', ...
                    'BackgroundColor', ax.Color, 'Margin', 0.5);
                hh(end+1) = hq;
                lab{end+1} = '\''{E}tat de contrainte $(\sigma_1, \sigma_2)$';
            end
            axis(ax, 'equal');
            xlim(ax, 1.25 * ext * [-1 1]);
            ylim(ax, 1.25 * ext * [-1 1]);
            xlabel(ax, '$\sigma_1$ (MPa)', 'Interpreter', 'latex');
            ylabel(ax, '$\sigma_2$ (MPa)', 'Interpreter', 'latex');
            title(ax, sprintf('Lieux de plasticit\\''{e} ($\\sigma_{adm} = %s$ MPa)', peNum(a)), 'Interpreter', 'latex');
            legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'eastoutside');
            hold(ax, 'off');
        end

        %% ========================= Treillis =========================
        function ax = truss(ax, truss, tsol, scale)
            %TRUSS Treillis : barres colorées (traction rouge, compression bleue, nulle grise), N, appuis,
            %   charges, réactions et déformée amplifiée en pointillé.
            %   ax = PlotEngine.truss(ax, truss)
            %   ax = PlotEngine.truss(ax, truss, tsol)
            %   ax = PlotEngine.truss(ax, truss, tsol, scale)
            %   truss : modèle (§3) ; tsol : BeamAndTrussSolver.solveTruss (optionnel) ;
            %   scale : facteur d'amplification de la déformée (défaut : 10 % de l'encombrement
            %   pour le plus grand déplacement ; 0 → pas de déformée). 2D et 3D.
            if nargin < 3
                tsol = [];
            end
            if nargin < 4
                scale = [];
            end
            ax = peAxes(ax);
            fg = ax.XColor;
            X = double(truss.nodes);
            [n, dim] = size(X);
            bars = double(truss.bars);
            m = size(bars, 1);
            if dim == 2
                X3 = [X zeros(n, 1)];
            else
                X3 = X;
            end
            span = max(max(X3, [], 1) - min(X3, [], 1));
            if span == 0
                span = 1;
            end
            if isfield(truss, 'names') && numel(truss.names) == n
                names = cellstr(truss.names);
            else
                names = arrayfun(@(i) sprintf('%d', i), (1:n).', 'UniformOutput', false);
            end
            cT = [0.85 0.15 0.15]; cC = [0.00 0.45 0.74]; c0 = [0.6 0.6 0.6];
            cL = [0.80 0.10 0.10]; cR = [0.10 0.60 0.20];
            hh = gobjects(0); lab = {};
            % déformée
            if ~isempty(tsol) && isfield(tsol, 'displacements') && ~(isscalar(scale) && scale == 0)
                U = tsol.displacements;
                if dim == 2
                    U = [U zeros(n, 1)];
                end
                umax = max(sqrt(sum(U.^2, 2)));
                if umax > 0
                    if isempty(scale)
                        scale = 0.1 * span / umax;
                    end
                    Xd = X3 + scale * U;
                    for b = 1:m
                        P = Xd(bars(b, :), :);
                        hd = plot3(ax, P(:, 1), P(:, 2), P(:, 3), ':', 'Color', [0.49 0.18 0.56], 'LineWidth', 1.5);
                    end
                    hh(end+1) = hd;
                    lab{end+1} = sprintf('D\\''{e}form\\''{e}e ($\\times %s$)', peNum(scale));
                end
            end
            hasN = ~isempty(tsol) && isfield(tsol, 'N');
            seen = false(1, 4);
            for b = 1:m
                P = X3(bars(b, :), :);
                col = fg; kind = 4;
                if hasN
                    switch tsol.nature{b}
                        case 'Traction', col = cT; kind = 1;
                        case 'Compression', col = cC; kind = 2;
                        otherwise, col = c0; kind = 3;
                    end
                end
                hb = plot3(ax, P(:, 1), P(:, 2), P(:, 3), '-', 'Color', col, 'LineWidth', 3);
                if ~seen(kind)
                    seen(kind) = true;
                    hh(end+1) = hb; %#ok<AGROW>
                    labs = {'Traction', 'Compression', 'Barre nulle', 'Barre'};
                    lab{end+1} = labs{kind}; %#ok<AGROW>
                end
                if hasN
                    M = mean(P, 1);
                    text(ax, M(1), M(2), M(3), sprintf('$N_{%d} = %s$', b, peNum(tsol.N(b) / 1e3)), ...
                        'Interpreter', 'latex', 'Color', col, 'FontSize', 9, 'HorizontalAlignment', 'center', ...
                        'BackgroundColor', ax.Color, 'Margin', 1);
                end
            end
            plot3(ax, X3(:, 1), X3(:, 2), X3(:, 3), 'o', 'Color', fg, 'MarkerFaceColor', ax.Color, 'MarkerSize', 6, ...
                'HandleVisibility', 'off');
            for i = 1:n
                text(ax, X3(i, 1), X3(i, 2), X3(i, 3), ['  $' peTexName(names{i}) '$'], 'Interpreter', 'latex', ...
                    'Color', fg, 'FontSize', 11, 'VerticalAlignment', 'bottom');
            end
            % appuis
            if isfield(truss, 'supports') && ~isempty(truss.supports)
                S = logical(truss.supports);
                for i = 1:n
                    if ~any(S(i, :))
                        continue
                    end
                    if dim == 2
                        if all(S(i, 1:2))
                            peSupport(ax, X(i, :), 'pivot', 0.05 * span, 0, fg);
                        elseif S(i, 2)
                            peSupport(ax, X(i, :), 'pivot_glissant', 0.05 * span, 0, fg);
                        else
                            peSupport(ax, X(i, :), 'pivot_glissant', 0.05 * span, -pi / 2, fg);
                        end
                    else
                        plot3(ax, X3(i, 1), X3(i, 2), X3(i, 3), '^', 'Color', fg, 'MarkerFaceColor', [0.8 0.8 0.8], ...
                            'MarkerSize', 12, 'HandleVisibility', 'off');
                    end
                end
            end
            % charges et réactions
            La = 0.15 * span;
            hs = 0.03 * span;
            vecs = {};
            if isfield(truss, 'loads') && ~isempty(truss.loads)
                vecs{end+1} = {double(truss.loads), cL, 'Charges', 1};
            end
            if ~isempty(tsol) && isfield(tsol, 'reactions')
                vecs{end+1} = {tsol.reactions, cR, 'R\''{e}actions', -1};
            end
            for v = 1:numel(vecs)
                F = vecs{v}{1};
                col = vecs{v}{2};
                Fmax = max(sqrt(sum(F.^2, 2)));
                first = true;
                for i = 1:n
                    f = F(i, :);
                    nf = norm(f);
                    if nf <= 1e-12 * max(Fmax, realmin)
                        continue
                    end
                    u = f / nf;
                    if dim == 2
                        u = [u 0]; %#ok<AGROW>
                    end
                    if vecs{v}{4} > 0
                        p1 = X3(i, :) - La * u;      % charge : pointe sur le nœud
                        p2 = X3(i, :);
                    else
                        p1 = X3(i, :) - 1.6 * La * u;  % réaction : décalée sous l'appui
                        p2 = X3(i, :) - 0.6 * La * u;
                    end
                    if dim == 2
                        ha = peArrow(ax, p1(1:2), p2(1:2), col, hs, 2);
                    else
                        ha = quiver3(ax, p1(1), p1(2), p1(3), p2(1) - p1(1), p2(2) - p1(2), p2(3) - p1(3), 0, ...
                            'Color', col, 'LineWidth', 2, 'MaxHeadSize', 0.6);
                    end
                    if dim == 2
                        txt = sprintf('$(%s, %s)$ kN', peNum(f(1) / 1e3), peNum(f(2) / 1e3));
                    else
                        txt = sprintf('$(%s, %s, %s)$ kN', peNum(f(1) / 1e3), peNum(f(2) / 1e3), peNum(f(3) / 1e3));
                    end
                    text(ax, p1(1), p1(2), p1(3), txt, 'Interpreter', 'latex', 'Color', col, 'FontSize', 9, ...
                        'HorizontalAlignment', 'center', 'VerticalAlignment', peVAlign(u(2)));
                    if first
                        hh(end+1) = ha(1); %#ok<AGROW>
                        lab{end+1} = vecs{v}{3}; %#ok<AGROW>
                        first = false;
                    end
                end
            end
            axis(ax, 'equal');
            mn = min(X3, [], 1) - [0.12 0.3 0.3] * span;   % marges x serrées : flèches de charges et réactions visibles en y
            mx = max(X3, [], 1) + [0.12 0.3 0.3] * span;
            xlim(ax, [mn(1) mx(1)]);
            ylim(ax, [mn(2) mx(2)]);
            if dim == 3
                zlim(ax, [mn(3) mx(3)]);
                view(ax, 3);
                zlabel(ax, '$z$ (m)', 'Interpreter', 'latex');
            else
                view(ax, 2);
            end
            xlabel(ax, '$x$ (m)', 'Interpreter', 'latex');
            ylabel(ax, '$y$ (m)', 'Interpreter', 'latex');
            if hasN
                title(ax, 'Treillis : efforts normaux $N$ (kN)', 'Interpreter', 'latex');
            else
                title(ax, 'Treillis', 'Interpreter', 'latex');
            end
            legend(ax, hh, lab, 'Interpreter', 'latex', 'Location', 'southoutside', 'Orientation', 'horizontal');
            hold(ax, 'off');
        end

        %% ========================= Formulaire =========================
        function hpx = formulaSheet(ax, sheet)
            %FORMULASHEET Rendu vertical d'une fiche de formules (titres, formules LaTeX, variables).
            %   hpx = PlotEngine.formulaSheet(ax, sheet)
            %   sheet : DataManager.formulaSheet(key) (struct colonne title, latex, vars) ou une clé.
            %   Les titres et définitions (texte accentué) sont affichés en texte simple, les
            %   formules en LaTeX. Une unité de l'axe vertical vaut un pixel : hpx est la hauteur
            %   conseillée de l'axe (pixels) pour que le rendu ne soit pas comprimé.
            if ischar(sheet) || isstring(sheet)
                sheet = DataManager.formulaSheet(sheet);
            end
            ax = peAxes(ax);
            fg = ax.XColor;
            wpx = 600;
            try
                pos = getpixelposition(ax);
                if pos(3) > 50
                    wpx = pos(3);
                end
            catch
            end
            nch = max(30, floor(wpx / 6.2));
            y = 8;
            for i = 1:numel(sheet)
                text(ax, 0.01, y, char(sheet(i).title), 'Interpreter', 'none', 'FontWeight', 'bold', ...
                    'FontSize', 11, 'Color', [0.00 0.45 0.74], 'VerticalAlignment', 'top');
                y = y + 26;
                lx = char(sheet(i).latex);
                if contains(lx, {'\frac', '\int', '\sum', '\sqrt', '\begin{array}', '\oint'})
                    hl = 58;
                    if contains(lx, '\begin{array}')
                        hl = 36 + 26 * (numel(strfind(lx, '\\')) + 1);
                    end
                else
                    hl = 32;
                end
                text(ax, 0.04, y + hl / 2, lx, 'Interpreter', 'latex', 'FontSize', 13, 'Color', fg, ...
                    'VerticalAlignment', 'middle');
                y = y + hl;
                vl = peWrap(char(sheet(i).vars), nch);
                if ~isempty(vl)
                    text(ax, 0.04, y, vl, 'Interpreter', 'none', 'FontSize', 9, 'Color', fg, ...
                        'VerticalAlignment', 'top');
                    y = y + 17 * numel(vl);
                end
                y = y + 14;
            end
            hpx = ceil(y + 8);
            ax.YDir = 'reverse';
            xlim(ax, [0 1]);
            ylim(ax, [0 hpx]);
            ax.XTick = [];
            ax.YTick = [];
            ax.XGrid = 'off';
            ax.YGrid = 'off';
            ax.Visible = 'off';
            hold(ax, 'off');
        end

        %% ========================= Abaques Kt =========================
        function ax = ktChart(ax, id)
            %KTCHART Abaque de coefficient de concentration de contrainte Kt.
            %   ax = PlotEngine.ktChart(ax, id)
            %   id : identifiant de DataManager.ktCharts() ('plaque_trou_traction',
            %   'arbre_epaulement_flexion', 'arbre_epaulement_torsion', 'arbre_epaulement_traction').
            %   Plaque : Kt(d/W) ; arbres : une courbe Kt(r/d) par valeur tabulée de D/d.
            charts = DataManager.ktCharts();
            idc = lower(strtrim(char(string(id))));
            j = find(strcmp({charts.id}, idc), 1);
            if isempty(j)
                error('MecaStruct:PlotEngine:unknownKt', 'Abaque Kt inconnu : « %s ».', idc);
            end
            ch = charts(j);
            ax = peAxes(ax);
            if isempty(ch.curves)
                x = linspace(ch.ranges(1, 1), min(ch.ranges(1, 2), 0.95), 200);
                plot(ax, x, DataManager.evalKt(idc, x), '-', 'Color', [0.00 0.45 0.74], 'LineWidth', 2);
                xlabel(ax, '$d/W$', 'Interpreter', 'latex');
                legend(ax, {'$K_t(d/W)$'}, 'Interpreter', 'latex', 'Location', 'northeast');
            else
                x = linspace(ch.ranges(1, 1), ch.ranges(1, 2), 200).';
                cols = lines(numel(ch.curves));
                lab = cell(1, numel(ch.curves));
                for k = 1:numel(ch.curves)
                    Kt = DataManager.evalKt(idc, [x, ch.curves(k) * ones(size(x))]);
                    plot(ax, x, Kt, '-', 'Color', cols(k, :), 'LineWidth', 1.8);
                    lab{k} = sprintf('$D/d = %s$', peNum(ch.curves(k)));
                end
                xlabel(ax, '$r/d$', 'Interpreter', 'latex');
                legend(ax, lab, 'Interpreter', 'latex', 'Location', 'northeast');
            end
            yl = ylim(ax);
            ylim(ax, [1 max(yl(2), 1.5)]);
            ylabel(ax, '$K_t$', 'Interpreter', 'latex');
            title(ax, peTx(ch.title), 'Interpreter', 'latex');
            hold(ax, 'off');
        end

        %% ========================= Export =========================
        function exportAxes(ax, file)
            %EXPORTAXES Export d'un axe (ou d'une figure / mise en page) en image ou PDF vectoriel.
            %   PlotEngine.exportAxes(ax, file)
            %   Extension : .png, .jpg, .jpeg, .tif, .tiff, .gif (300 dpi) ou .pdf, .emf, .eps
            %   (vectoriel). Le dossier est créé si besoin. Utilise exportgraphics.
            if isempty(ax) || ~isgraphics(ax)
                error('MecaStruct:PlotEngine:invalidAxes', 'Objet graphique invalide pour l''export.');
            end
            file = char(file);
            [d, ~, ext] = fileparts(file);
            ext = lower(ext);
            if ~isempty(d) && ~isfolder(d)
                mkdir(d);
            end
            switch ext
                case {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif'}
                    exportgraphics(ax, file, 'Resolution', 300);
                case {'.pdf', '.emf', '.eps'}
                    exportgraphics(ax, file, 'ContentType', 'vector');
                otherwise
                    error('MecaStruct:PlotEngine:invalidFormat', ...
                        'Format d''export non pris en charge : « %s » (png, jpg, tif, gif, pdf, emf, eps).', ext);
            end
        end
    end
end

%% ============================== Fonctions locales ==============================

function ax = peAxes(ax)
% Prépare l'axe : création si vide, effacement, grille, LaTeX pour les graduations.
if isempty(ax)
    f = figure();
    ax = axes(f);
elseif ~isscalar(ax) || ~isgraphics(ax, 'axes')
    error('MecaStruct:PlotEngine:invalidAxes', 'Le premier argument doit être un axes ou un uiaxes valide (ou vide).');
end
legend(ax, 'off');
cla(ax, 'reset');
hold(ax, 'on');
grid(ax, 'on');
box(ax, 'on');
ax.TickLabelInterpreter = 'latex';
end

function s = peTx(s)
% Remplace les lettres accentuées par leurs commandes LaTeX (mode texte), chaîne ASCII.
s = char(s);
map = {'é', '\''{e}'; 'è', '\`{e}'; 'ê', '\^{e}'; 'ë', '\"{e}'; 'à', '\`{a}'; 'â', '\^{a}'; ...
    'î', '\^{i}'; 'ï', '\"{i}'; 'ô', '\^{o}'; 'ù', '\`{u}'; 'û', '\^{u}'; 'ç', '\c{c}'; ...
    'É', '\''{E}'; 'È', '\`{E}'; 'À', '\`{A}'; '’', ''''; '–', '--'};
for k = 1:size(map, 1)
    s = strrep(s, map{k, 1}, map{k, 2});
end
s(s > 127) = '?';
end

function s = peNum(v)
% Nombre formaté pour l'affichage (4 chiffres significatifs, pas de -0).
if abs(v) < 1e-12 * max(1, abs(v)) || v == 0
    v = 0;
end
s = sprintf('%.4g', v);
s = strrep(s, 'e+0', 'e');
s = strrep(s, 'e-0', 'e-');
s = strrep(s, 'e+', 'e');
end

function s = peTexName(name)
% Nom ASCII sûr pour LaTeX : lettres + indice numérique (F1 → F_{1}).
name = char(name);
name = name(isstrprop(name, 'alphanum') & name < 128);
if isempty(name)
    name = 'X';
end
tok = regexp(name, '^([A-Za-z]+)(\d*)$', 'tokens', 'once');
if ~isempty(tok) && ~isempty(tok{2})
    s = [tok{1} '_{' tok{2} '}'];
elseif ~isempty(tok)
    s = tok{1};
else
    s = ['\mathrm{' name '}'];
end
end

function s = peTexComp(nmTex, c)
% Ajoute la composante (x, y, z) à un nom LaTeX éventuellement indicé.
if endsWith(nmTex, '}') && contains(nmTex, '_{')
    s = [nmTex(1:end-1) ',' c '}'];
else
    s = [nmTex '_{' c '}'];
end
end

function u = peUnitTex(c)
if any(strcmp(c, {'N', 'Ty', 'Tz'}))
    u = 'kN';
else
    u = 'kN$\cdot$m';
end
end

function nm = peName(s, def)
if isfield(s, 'name') && ~isempty(s.name)
    nm = char(s.name);
else
    nm = def;
end
end

function v = peField(s, f)
if isfield(s, f) && ~isempty(s.(f))
    v = double(s.(f));
else
    v = 0;
end
end

function arr = peArr(model, f)
if isfield(model, f) && ~isempty(model.(f))
    arr = model.(f);
else
    arr = struct([]);
end
end

function tf = peHas(d, f, g)
tf = isfield(d, f) && isstruct(d.(f)) && ~isempty(d.(f)) && isfield(d.(f), g) && ~isempty(d.(f).(g)) ...
    && any(isfinite(d.(f).(g)(:)));
end

function a = peHAlign(x, L)
if x > 0.6 * L
    a = 'right';
else
    a = 'left';
end
end

function a = peSignAlign(v)
if v < 0
    a = 'right';
else
    a = 'left';
end
end

function a = peVAlign(uy)
if uy > 0
    a = 'top';
else
    a = 'bottom';
end
end

function h = peArrow(ax, p1, p2, col, hs, lw)
% Flèche de p1 vers p2 (coordonnées données) : trait + pointe triangulaire pleine.
d = p2 - p1;
Ld = norm(d);
if Ld == 0
    h = plot(ax, p2(1), p2(2), '.', 'Color', col);
    return
end
u = d / Ld;
nrm = [-u(2) u(1)];
hs = min(hs, 0.6 * Ld);
base = p2 - hs * u;
h = plot(ax, [p1(1) base(1)], [p1(2) base(2)], '-', 'Color', col, 'LineWidth', lw);
tri = [p2; base + 0.38 * hs * nrm; base - 0.38 * hs * nrm];
patch(ax, tri(:, 1), tri(:, 2), col, 'EdgeColor', col, 'HandleVisibility', 'off');
end

function h = peArcArrow(ax, c, r, M, col, hs, lw)
% Couple : arc fléché autour de c, sens trigonométrique si M > 0.
if M > 0
    th = linspace(-pi / 3, 4 * pi / 3, 60);
else
    th = linspace(4 * pi / 3, -pi / 3, 60);
end
x = c(1) + r * cos(th);
y = c(2) + r * sin(th);
h = plot(ax, x(1:end-2), y(1:end-2), '-', 'Color', col, 'LineWidth', lw);
peArrow(ax, [x(end-3) y(end-3)], [x(end) y(end)], col, hs, lw);
end

function peSupport(ax, p, typ, h, phi, fg)
% Symbole normalisé de liaison, pointe sur p, corps du côté -y local tourné de phi.
R = [cos(phi) -sin(phi); sin(phi) cos(phi)];
T = @(Q) (R * Q.').' + p;
fillC = [0.82 0.82 0.82];
switch typ
    case 'encastrement'
        w = T([-1.1 * h 0; 1.1 * h 0]);
        plot(ax, w(:, 1), w(:, 2), '-', 'Color', fg, 'LineWidth', 3);
        for xi = linspace(-1.1 * h, 1.1 * h, 7)
            q = T([xi 0; xi - 0.4 * h -0.4 * h]);
            plot(ax, q(:, 1), q(:, 2), '-', 'Color', fg, 'LineWidth', 1);
        end
        return
    case {'appui_simple', 'pivot_glissant'}
        rolling = true;
    otherwise
        rolling = false;
end
tri = T([0 0; -0.6 * h -h; 0.6 * h -h]);
patch(ax, tri(:, 1), tri(:, 2), fillC, 'EdgeColor', fg, 'LineWidth', 1.2);
if ~strcmp(typ, 'appui_simple')
    th = linspace(0, 2 * pi, 40).';
    q = T(0.18 * h * [cos(th) sin(th)]);
    patch(ax, q(:, 1), q(:, 2), [1 1 1], 'EdgeColor', fg, 'LineWidth', 1.2);
end
if rolling
    th = linspace(0, 2 * pi, 30).';
    for xc = [-0.33 0.33] * h
        q = T([xc + 0.15 * h * cos(th), -1.15 * h + 0.15 * h * sin(th)]);
        patch(ax, q(:, 1), q(:, 2), fillC, 'EdgeColor', fg);
    end
    yg = -1.3 * h;
else
    yg = -h;
end
g = T([-0.9 * h yg; 0.9 * h yg]);
plot(ax, g(:, 1), g(:, 2), '-', 'Color', fg, 'LineWidth', 1.5);
for xi = linspace(-0.8 * h, 0.9 * h, 6)
    q = T([xi yg; xi - 0.25 * h yg - 0.25 * h]);
    plot(ax, q(:, 1), q(:, 2), '-', 'Color', fg, 'LineWidth', 0.8);
end
end

function peExtremum(ax, s, v, L, kind, nameTex, unitTex, col)
% Marque et annote un extremum d'un diagramme.
plot(ax, s, v, 'o', 'Color', col, 'MarkerFaceColor', col, 'MarkerSize', 6, 'HandleVisibility', 'off');
% Étiquette décalée hors de la courbe (5 % de la hauteur de l'axe) et sur fond d'axe : rien ne la traverse.
yl = ylim(ax);
off = 0.05 * (yl(2) - yl(1));
if strcmp(kind, 'max')
    va = 'bottom';
else
    va = 'top';
    off = -off;
end
text(ax, s, v + off, sprintf(' ${%s}_{%s} = %s$ %s en $s = %s$ m ', nameTex, kind, peNum(v), unitTex, peNum(s)), ...
    'Interpreter', 'latex', 'Color', col, 'FontSize', 9, 'VerticalAlignment', va, ...
    'HorizontalAlignment', peHAlign(s, L), 'BackgroundColor', ax.Color, 'Margin', 1);
end

function peDim(ax, p1, p2, txt, where, col, hs)
% Cote : flèche double entre p1 et p2 avec texte.
peArrow(ax, (p1 + p2) / 2, p1, col, hs, 0.8);
peArrow(ax, (p1 + p2) / 2, p2, col, hs, 0.8);
m = (p1 + p2) / 2;
switch where
    case 'below'
        args = {'HorizontalAlignment', 'center', 'VerticalAlignment', 'top'};
    case 'above'
        args = {'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom'};
    case 'left'
        args = {'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'Rotation', 90};
    otherwise
        args = {'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle'};
end
text(ax, m(1), m(2), txt, 'Interpreter', 'latex', 'Color', col, 'FontSize', 10, 'BackgroundColor', ax.Color, 'Margin', 0.5, args{:});
end

function ps = peCirclePoly(c, r)
th = linspace(0, 2 * pi, 361);
th(end) = [];
ps = polyshape(c + r * cos(th), r * sin(th), 'Simplify', false);
end

function out = peWrap(s, n)
% Découpe un texte en lignes d'au plus n caractères (retours à la ligne conservés).
out = {};
paras = strsplit(s, newline);
for k = 1:numel(paras)
    w = strsplit(strtrim(paras{k}), ' ');
    line = '';
    for j = 1:numel(w)
        if isempty(line)
            line = w{j};
        elseif numel(line) + 1 + numel(w{j}) <= n
            line = [line ' ' w{j}]; %#ok<AGROW>
        else
            out{end+1, 1} = line; %#ok<AGROW>
            line = w{j};
        end
    end
    if ~isempty(line)
        out{end+1, 1} = line; %#ok<AGROW>
    end
end
end

function idx = peMk(n)
% Indices de marqueurs (au plus 15, répartis) pour ne pas surcharger les courbes denses.
idx = unique(round(linspace(1, n, min(n, 15))));
end
