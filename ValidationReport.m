classdef ValidationReport
    %VALIDATIONREPORT Dossier de validation d'un problème traité dans MecaStruct_App.
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   file = ValidationReport.generate(app, key) recalcule l'onglet `key`, puis écrit un fichier
    %   HTML autonome (images intégrées) contenant : les données du problème, les hypothèses du
    %   modèle avec contrôles d'applicabilité, les équations avec valeurs chiffrées, une
    %   vérification indépendante « à la main » comparée au solveur, les tableaux de résultats, les
    %   diagrammes et le rapport détaillé du solveur. Le fichier est destiné à un relecteur qui
    %   valide (ou non) le calcul, le modèle et les hypothèses.
    %
    %   key : 'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'.
    %   file = ValidationReport.generate(app, key, folder) choisit le dossier de sortie (défaut :
    %   <dossier du projet>/validation).
    %
    %   Voir aussi MecaStruct_App, DataManager.formulaSheet.

    methods (Static)

        function exe = findBrowser()
            %FINDBROWSER Chemin d'Edge ou de Chrome (impression PDF sans fenêtre), '' s'il n'y en a pas.
            cand = {'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
                'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
                'C:\Program Files\Google\Chrome\Application\chrome.exe'
                'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
                '/usr/bin/google-chrome'
                '/usr/bin/chromium'
                '/usr/bin/chromium-browser'
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'};
            exe = '';
            for k = 1:numel(cand)
                if isfile(cand{k})
                    exe = cand{k};
                    return
                end
            end
        end

        function pdf = toPDF(htmlFile)
            %TOPDF Convertit un dossier HTML en PDF avec Edge ou Chrome sans fenêtre (les formules MathJax demandent Internet).
            %   pdf = ValidationReport.toPDF(htmlFile) écrit le PDF à côté du fichier HTML.
            exe = ValidationReport.findBrowser();
            if isempty(exe)
                error('MecaStruct:Validation:noBrowser', ['Export PDF : aucun navigateur Edge ou Chrome trouvé. Générez le dossier en HTML, ' ...
                    'ouvrez-le dans un navigateur puis imprimez-le en PDF.']);
            end
            pdf = regexprep(htmlFile, '\.html$', '.pdf');
            prof = tempname;
            cl = onCleanup(@() ValidationReport.rmTemp(prof));
            args = {exe, '--headless', '--disable-gpu', '--no-pdf-header-footer', '--virtual-time-budget=25000', ...
                ['--user-data-dir=' prof], ['--print-to-pdf=' pdf], ['file:///' strrep(htmlFile, '\', '/')]};
            jargs = javaArray('java.lang.String', numel(args));
            for k = 1:numel(args)
                jargs(k) = java.lang.String(args{k});
            end
            if ispc
                sink = 'NUL';
            else
                sink = '/dev/null';
            end
            pb = java.lang.ProcessBuilder(jargs);
            pb.redirectErrorStream(true);
            pb.redirectOutput(java.io.File(sink));   % sortie jetée : un tampon plein bloquerait le navigateur
            proc = pb.start();
            if ~proc.waitFor(int64(90), java.util.concurrent.TimeUnit.SECONDS)   % délai : un navigateur bloqué n'immobilise pas MATLAB
                proc.destroyForcibly();
            end
            if ~isfile(pdf)
                error('MecaStruct:Validation:pdf', 'Export PDF : le navigateur n''a pas écrit le fichier (délai de 90 s dépassé ou erreur).');
            end
        end

        function file = generate(app, key, folder, format)
            %GENERATE Écrit le dossier de validation de l'onglet `key` et renvoie le chemin du fichier.
            %   format : 'html' (défaut) ou 'pdf' (le HTML est conservé à côté ; PDF par Edge ou Chrome sans fenêtre).
            if nargin < 3 || isempty(folder)
                folder = DataManager.dataFolder('validation');
            end
            if nargin < 4 || isempty(format)
                format = 'html';
            end
            format = lower(char(format));
            if ~any(strcmp(format, {'html', 'pdf'}))
                error('MecaStruct:Validation:format', 'Format du dossier : ''html'' ou ''pdf''.');
            end
            if ~isfolder(folder)
                mkdir(folder);
            end
            m = ValidationReport.meta(key);
            errs = {};
            % thème clair dès le recalcul : couleurs de texte et de fond figées au tracé (gris clair invisible, fonds noirs)
            try
                th0 = app.UIFigure.Theme;
                app.UIFigure.Theme = 'light';
                clTheme = onCleanup(@() ValidationReport.restoreTheme(app, th0)); %#ok<NASGU>
            catch
            end
            for k = 1:numel(m.calls)
                try
                    app.(m.calls{k})();
                catch err
                    errs{end + 1} = sprintf('%s : %s', m.calls{k}, err.message); %#ok<AGROW>
                end
            end
            errs = [errs, ValidationReport.refreshExtras(app, key)];   % combinaisons, Eurocode 3, fatigue, profilé déjà calculés
            W = app.H.(key).W;
            [chkHTML, nWarn, nKo] = ValidationReport.safeTwo(@() ValidationReport.hypothesesHTML(app, key));
            [hcHTML, nOK, nTot] = ValidationReport.safeHand(@() ValidationReport.handHTML(app, key, true));
            S = {'donnees',    '1. Données du problème',                            ValidationReport.safe(@() ValidationReport.inputsHTML(app, key))
                 'hypotheses', '2. Hypothèses du modèle et applicabilité',          chkHTML
                 'verif',      '3. Équations et vérification indépendante',         hcHTML
                 'resultats',  '4. Résultats du solveur',                           ValidationReport.safe(@() ValidationReport.resultsHTML(app, key))
                 'diagrammes', '5. Diagrammes',                                     ValidationReport.safe(@() ValidationReport.plotsHTML(app, key, m))
                 'rapport',    '6. Rapport détaillé du solveur (étapes de calcul)', ValidationReport.safe(@() ValidationReport.reportHTML(W))
                 'formules',   '7. Formules utilisées pour ce calcul',              ValidationReport.safe(@() ValidationReport.formulasHTML(m))
                 'avis',       '8. Avis du relecteur',                              ValidationReport.reviewHTML()};
            toc = '<nav class="toc" id="top"><strong>Sommaire</strong><ol>';
            body = '';
            for k = 1:size(S, 1)
                toc = [toc '<li><a href="#' S{k, 1} '">' ValidationReport.esc(regexprep(S{k, 2}, '^\d+\. ', '')) '</a></li>']; %#ok<AGROW>
                body = [body ValidationReport.section(S{k, :})]; %#ok<AGROW>
            end
            body = [toc '</ol></nav>' body];
            status = '';
            try
                status = char(W.Status.Text);
            catch
            end
            head = ValidationReport.headHTML(m, status, nOK, nTot, nWarn, nKo, errs);
            html = ['<!doctype html><html lang="fr"><head><meta charset="utf-8">' ...
                '<meta name="viewport" content="width=device-width, initial-scale=1">' ...
                '<title>Dossier de validation - ' ValidationReport.esc(m.title) '</title>' ...
                '<script>window.MathJax={tex:{inlineMath:[[''$'',''$'']]}};</script>' ...
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-chtml.min.js" ' ...
                'integrity="sha384-vO3GhWOnJNToPPbwt7p2sFBxI/klrkF8WbEn4uFdj6Mf3Y305DcOVeAkQN/KdOoV" crossorigin="anonymous" ' ...
                'onerror="document.getElementById(''mjwarn'').style.display=''block''"></script>' ...
                '<style>' ValidationReport.css() '</style></head><body><main>' ...
                '<div id="mjwarn" class="warnbox" style="display:none"><strong>Formules non affichées :</strong> le script MathJax ' ...
                '(cdnjs.cloudflare.com) n''a pas pu être chargé, probablement faute de connexion Internet. Les équations apparaissent en LaTeX brut ; ' ...
                'les valeurs chiffrées et les tableaux restent lisibles.</div>' head body '</main></body></html>'];
            stamp = char(datetime('now', 'Format', 'yyyyMMdd_HHmmss'));
            name = regexprep(m.title, '[^A-Za-z0-9]+', '_');
            file = fullfile(folder, sprintf('Validation_%s_%s.html', name, stamp));
            fid = fopen(file, 'w', 'n', 'UTF-8');
            if fid < 0
                error('MecaStruct:Validation:write', 'Impossible d''écrire %s', file);
            end
            cl = onCleanup(@() fclose(fid));
            fprintf(fid, '%s', html);
            clear cl
            if strcmp(format, 'pdf')
                file = ValidationReport.toPDF(file);
            end
        end

        function [nOK, nTot] = handCheck(app, key)
            %HANDCHECK Recalcule l'onglet `key` et compte les contrôles à la main qui concordent (§3), sans écrire de dossier.
            m = ValidationReport.meta(key);
            for k = 1:numel(m.calls)
                app.(m.calls{k})();
            end
            [~, nOK, nTot] = ValidationReport.handHTML(app, key);
        end

        function m = meta(key)
            %META Titre, onglet, calculs à relancer et fiches de formules de chaque zone de travail.
            switch key
                case 'Sec'
                    m = struct('title', 'Section droite', 'sel', 'Sections', 'calls', {{'computeSection'}}, 'forms', {{'geometrie'}});
                case 'Beam'
                    m = struct('title', 'Poutre', 'sel', 'Poutres', 'calls', {{'computeBeam'}}, 'forms', {{'equilibre', 'cohesion', 'deformee', 'energie', 'mohr_integrales'}});
                case 'Tr'
                    m = struct('title', 'Treillis', 'sel', 'Treillis', 'calls', {{'computeTruss'}}, 'forms', {{'treillis'}});
                case 'Tra'
                    m = struct('title', 'Traction-compression', 'sel', 'Traction', 'calls', {{'computeTraction'}}, 'forms', {{'traction'}});
                case 'Cis'
                    m = struct('title', 'Cisaillement et matage', 'sel', 'Cisaillement', 'calls', {{'computeShear', 'computeKey', 'computePin'}}, 'forms', {{'cisaillement', 'matage'}});
                case 'Tor'
                    m = struct('title', 'Torsion', 'sel', 'Torsion', 'calls', {{'computeTorsion'}}, 'forms', {{'torsion'}});
                case 'Fle'
                    m = struct('title', 'Flexion', 'sel', 'Flexion', 'calls', {{'computeBending'}}, 'forms', {{'flexion'}});
                case 'Fla'
                    m = struct('title', 'Flambage', 'sel', 'Flambage', 'calls', {{'computeBuckling'}}, 'forms', {{'flambage'}});
                case 'Ten'
                    m = struct('title', 'Tenseurs et criteres', 'sel', 'Tenseurs', 'calls', {{'computeTensor'}}, 'forms', {{'tenseurs', 'mohr_cercle', 'criteres'}});
                case 'Hoo'
                    m = struct('title', 'Loi de Hooke', 'sel', 'Hooke', 'calls', {{'computeHooke'}}, 'forms', {{'hooke'}});
                case 'Jau'
                    m = struct('title', 'Jauges et rosettes', 'sel', 'Jauges', 'calls', {{'computeGauges'}}, 'forms', {{'extensometrie'}});
                otherwise
                    error('MecaStruct:Validation:unknownKey', 'Zone de travail inconnue : %s', char(string(key)));
            end
            % Formules du §7 : seulement celles appliquées par le solveur et les contrôles du §3.
            switch key
                case 'Sec', m.keep = {'Aire de la section', 'Centre de surface G', 'Moments quadratiques en G', 'Théorème de Huygens', 'Modules de flexion'};
                case 'Beam', m.keep = {'Principe fondamental de la statique', 'Degré d''hyperstatisme', 'Composantes du torseur de cohésion', 'Relations différentielles', 'Équation de la déformée', 'Conditions aux limites', 'Théorème de Ménabréa'};
                case 'Tr', m.keep = {'Équilibre du nœud i (méthode des nœuds)', 'Degré d''hyperstatisme', 'Contrainte normale', 'Allongement d''une barre'};
                case 'Tra', m.keep = {'Contrainte normale', 'Concentration de contrainte et condition de résistance', 'Allongement : méthode analytique', 'Condition de rigidité'};
                case 'Cis', m.keep = {'Contrainte tangentielle moyenne', 'Contrainte maximale et condition de résistance', 'Pression de matage', 'Clavette : matage', 'Clavette : cisaillement', 'Rivet ou goupille : cisaillement'};
                case 'Tor', m.keep = {'Contrainte tangentielle', 'Condition de résistance', 'Rotation : méthode analytique', 'Moment quadratique polaire', 'Puissance transmise'};
                case 'Fle', m.keep = {'Flexion simple', 'Condition de résistance', 'Axe neutre', 'Flexion composée'};
                case 'Fla', m.keep = {'Longueurs de flambement', 'Élancement', 'Élancement limite', 'Charge critique d''Euler (λ ≥ λlim)', 'Formule de Rankine (20 ≤ λ < λlim)', 'Charge admissible'};
                case 'Ten', m.keep = {'Contraintes principales planes', 'Rayon du cercle de Mohr', 'Critère de Tresca', 'Critère de Von Mises', 'Coefficient de sécurité obtenu'};
                case 'Hoo', m.keep = {'Loi de Hooke 3D isotrope', 'Contraintes planes', 'Variation de volume', 'Relations entre constantes'};
                case 'Jau', m.keep = {'Loi de la jauge (Bridgman)', 'Quart de pont', 'Rosette à 45°', 'Rosette à 60° (delta)', 'Déformations principales', 'Contraintes (état plan de contrainte)'};
            end
        end
    end

    %% =============================================================================================
    %  Sections HTML
    %  =============================================================================================
    methods (Static, Access = private)

        function html = headHTML(m, status, nOK, nTot, nWarn, nKo, errs)
            e = ValidationReport.esc;
            html = ['<h1>Dossier de validation : ' e(m.title) '</h1>' ...
                '<p class="meta">Généré le ' char(datetime('now', 'Format', 'dd/MM/yyyy HH:mm')) ' par MecaStruct RdM Pro, application de Théo Brun (MATLAB ' version('-release') ').</p>' ...
                '<div class="box"><strong>Objet.</strong> Ce document rassemble les données du problème, les hypothèses, les équations avec valeurs chiffrées, ' ...
                'les résultats du solveur et les diagrammes. Il permet de vérifier trois points : (1) le solveur a bien calculé, ' ...
                '(2) le modèle est applicable à ce cas, (3) les hypothèses sont justifiées. Chaque résultat important est recalculé à la main, ' ...
                'indépendamment du solveur, au §3.</div>'];
            if ~isempty(status)
                html = [html '<div class="status">' e(status) '</div>'];
            end
            html = [html '<p><strong>Bilan automatique :</strong> '];
            if nTot == 0
                html = [html '<span class="ko">vérification indépendante non exécutée (voir §3) : aucun contrôle de calcul n''a pu être fait</span>'];
            else
                html = [html sprintf('<span class="ok">%d / %d contrôles de calcul concordent</span>', nOK, nTot)];
            end
            if nTot > nOK
                html = [html sprintf(' ; <span class="ko">%d écart(s) à examiner</span>', nTot - nOK)];
            end
            if nKo > 0
                html = [html sprintf(' ; <span class="ko">%d hypothèse(s) NON satisfaite(s)</span>', nKo)];
            end
            if nWarn > 0
                html = [html sprintf(' ; <span class="warn">%d point(s) d''attention sur les hypothèses</span>', nWarn)];
            end
            html = [html '.</p>'];
            if ~isempty(errs)
                html = [html '<div class="warnbox"><strong>Erreurs rencontrées lors du recalcul :</strong><br>' strjoin(cellfun(e, errs, 'UniformOutput', false), '<br>') '</div>'];
            end
        end

        function html = section(id, title, content)
            html = ['<h2 id="' id '">' ValidationReport.esc(title) '<a class="top" href="#top">↑ sommaire</a></h2>' content];
        end

        function html = inputsHTML(app, key)
            html = ValidationReport.inputsOf(app.H.(key).W);
            if any(strcmp(key, {'Cis', 'Fle'}))
                html = [html '<h3>Section utilisée (onglet Sections)</h3>' ValidationReport.inputsOf(app.H.Sec.W)];
            end
        end

        function html = inputsOf(W)
            % Lecture des champs de saisie de la zone de travail, ligne par ligne.
            ch = W.In.Children;
            rows = zeros(numel(ch), 1);
            for k = 1:numel(ch)
                try
                    rows(k) = 10 * ch(k).Layout.Row(1) + ch(k).Layout.Column(1);   % ligne, puis colonne
                catch
                    rows(k) = 0;
                end
            end
            [~, ord] = sort(rows);
            ch = ch(ord);
            e = ValidationReport.esc;
            html = '';
            open = false;
            lastLabel = '';
            for k = 1:numel(ch)
                c = ch(k);
                switch class(c)
                    case 'matlab.ui.control.Label'
                        col = c.Layout.Column;
                        if numel(col) == 2 || ~isempty(strfind(c.FontWeight, 'bold')) %#ok<STREMP>
                            if strcmp(c.FontWeight, 'bold') && ~contains(c.Text, 'Calcul et transfert')   % titre d'étape de l'interface : sans objet dans le dossier
                                if open
                                    html = [html '</table>']; %#ok<AGROW>
                                end
                                ttl = regexprep(c.Text, '^(\d+\.\s*|…\s*ou\s*)', '');   % numéros d'étapes de l'interface ≠ numéros du dossier
                                html = [html '<h3>' e([upper(ttl(1:min(1, end))) ttl(2:end)]) '</h3><table class="kv">']; %#ok<AGROW>
                                open = true;
                                lastLabel = '';
                            end
                        else
                            lastLabel = c.Text;
                        end
                    case {'matlab.ui.control.NumericEditField', 'matlab.ui.control.DropDown', ...
                            'matlab.ui.control.EditField', 'matlab.ui.control.CheckBox'}
                        if ~open
                            html = [html '<table class="kv">']; %#ok<AGROW>
                            open = true;
                        end
                        if strcmp(c.Enable, 'on')
                            html = [html '<tr><td>' e(lastLabel) '</td><td class="v">' e(ValidationReport.valStr(c)) '</td></tr>']; %#ok<AGROW>
                        end
                    case 'matlab.ui.control.Table'
                        if open
                            html = [html '</table>']; %#ok<AGROW>
                            open = false;
                        end
                        html = [html ValidationReport.tableHTML(c.Data, c.ColumnName, [])]; %#ok<AGROW>
                    case 'matlab.ui.container.GridLayout'
                        cb = c.Children;
                        txt = {};
                        for j = 1:numel(cb)
                            if isa(cb(j), 'matlab.ui.control.CheckBox')
                                txt{end + 1} = sprintf('%s : %s', cb(j).Text, ValidationReport.yesNo(cb(j).Value)); %#ok<AGROW>
                            end
                        end
                        if ~isempty(txt)
                            if ~open
                                html = [html '<table class="kv">']; %#ok<AGROW>
                                open = true;
                            end
                            html = [html '<tr><td>' e(lastLabel) '</td><td class="v">' e(strjoin(txt, ' ; ')) '</td></tr>']; %#ok<AGROW>
                        end
                end
            end
            if open
                html = [html '</table>'];
            end
        end

        function s = valStr(c)
            switch class(c)
                case 'matlab.ui.control.NumericEditField'
                    s = sprintf('%.6g', c.Value);
                case 'matlab.ui.control.CheckBox'
                    s = ValidationReport.yesNo(c.Value);
                case 'matlab.ui.control.DropDown'
                    s = char(string(c.Value));
                    data = c.ItemsData;
                    idx = [];
                    try
                        if iscell(data)
                            idx = find(cellfun(@(x) isequal(x, c.Value), data), 1);
                        elseif ~isempty(data)
                            idx = find(data == c.Value, 1);
                        end
                    catch
                    end
                    if ~isempty(idx)
                        s = char(string(c.Items{idx}));
                    end
                otherwise
                    s = char(string(c.Value));
            end
        end

        function s = yesNo(v)
            if v
                s = 'oui';
            else
                s = 'non';
            end
        end

        function [html, nWarn, nKo] = hypothesesHTML(app, key)
            e = ValidationReport.esc;
            stat = [ValidationReport.hypStatements(key), ValidationReport.extraStatements(app, key)];
            html = '<h3>Hypothèses du modèle (à valider)</h3><table><tr><th>Hypothèse</th><th>Avis du relecteur</th></tr>';
            for k = 1:numel(stat)
                html = [html '<tr><td>' e(stat{k}) '</td><td class="rv">' ValidationReport.choices() '</td></tr>']; %#ok<AGROW>
            end
            html = [html '</table>'];
            chk = ValidationReport.autoChecks(app, key);
            nWarn = 0;
            nKo = 0;
            html = [html '<h3>Contrôles d''applicabilité faits par le logiciel</h3>' ...
                '<table><tr><th>Contrôle</th><th>Valeurs</th><th>Résultat</th></tr>'];
            for k = 1:size(chk, 1)
                switch chk{k, 3}
                    case 'ok'
                        st = '<span class="ok">satisfait</span>';
                    case 'warn'
                        st = '<span class="warn">point d''attention</span>';
                        nWarn = nWarn + 1;
                    otherwise
                        st = '<span class="ko">NON satisfait</span>';
                        nKo = nKo + 1;
                end
                html = [html '<tr><td>' e(chk{k, 1}) '</td><td>' e(chk{k, 2}) '</td><td>' st '</td></tr>']; %#ok<AGROW>
            end
            html = [html '</table>'];
        end

        function s = choices()
            s = '&#9744; valide &nbsp; &#9744; à revoir &nbsp; &#9744; non applicable';
        end

        function [html, nOK, nTot] = handHTML(app, key, withExtras)
            e = ValidationReport.esc;
            rows = ValidationReport.handRows(app, key);
            if nargin >= 3 && withExtras && strcmp(key, 'Beam')
                rows = [rows; ValidationReport.handExtras(app)];
            end
            nOK = 0;
            nTot = 0;
            html = ['<p>Pour chaque grandeur, la formule est écrite avec les valeurs de ce problème, calculée à la main ' ...
                '(sans appeler le solveur) puis comparée à la valeur du solveur.</p>' ...
                '<table class="hand"><tr><th>Grandeur</th><th>Formule avec valeurs</th><th>Valeur à la main</th><th>Valeur solveur</th><th>Écart</th><th>Verdict</th></tr>'];
            for k = 1:numel(rows)
                r = rows{k};
                if isempty(r.hand)
                    html = [html '<tr><td colspan="6" class="grp">' e(r.label) '</td></tr>']; %#ok<AGROW>
                    continue
                end
                nTot = nTot + 1;
                d = abs(r.hand - r.solver);
                tol = r.tol;
                if isnan(tol)
                    tol = 1e-6 * max(abs(r.solver), abs(r.hand)) + 1e-12;
                end
                ok = d <= tol;
                nOK = nOK + ok;
                if ok
                    v = '<span class="ok">concordent</span>';
                else
                    v = '<span class="ko">ÉCART</span>';
                end
                un = '';
                if ~isempty(r.unit)
                    un = [' ' e(r.unit)];
                end
                html = [html '<tr><td>' e(r.label) '</td><td class="fm">' ValidationReport.mj(r.latex) '</td>' ...
                    '<td class="n">' sprintf('%.8g', r.hand) un '</td><td class="n">' sprintf('%.8g', r.solver) un '</td>' ...
                    '<td class="n">' sprintf('%.2g', d) '</td><td>' v '</td></tr>']; %#ok<AGROW>
            end
            html = [html '</table>'];
            L = ValidationReport.latexBlocks(app, key);
            if ~isempty(L)
                html = [html '<h3>Équations avec valeurs, telles qu''écrites par le solveur</h3>'];
                for k = 1:size(L, 1)
                    html = [html '<div class="eqblock"><div class="eqtitle">' e(L{k, 1}) '</div>']; %#ok<AGROW>
                    for j = 1:numel(L{k, 2})
                        html = [html '<div class="eq">' ValidationReport.mjRaw(L{k, 2}{j}) '</div>']; %#ok<AGROW>
                    end
                    html = [html '</div>']; %#ok<AGROW>
                end
            end
        end

        function L = latexBlocks(app, key)
            paths = struct('Sec', {{'section.P', 'section.bend', 'section.jour'}}, ...
                'Beam', {{'beam.sol', 'beam.defl'}}, 'Tr', {{'truss.tsol'}}, 'Tra', {{'traction'}}, ...
                'Cis', {{'shear.shear', 'shear.jour', 'shear.bearing', 'key', 'pin'}}, 'Tor', {{'torsion'}}, ...
                'Fle', {{'bending.bend'}}, 'Fla', {{'buckling.analysis'}}, ...
                'Ten', {{'tensor.principal', 'tensor.facet', 'tensor.plane2D', 'tensor.criteria'}}, ...
                'Hoo', {{'hooke.mohr'}}, 'Jau', {{'gauges.gauge', 'gauges.bridge', 'gauges.rosette'}});
            names = struct('section', 'Section', 'bend', 'Flexion', 'jour', 'Cisaillement (Jourawski)', 'sol', 'Poutre : statique', ...
                'defl', 'Poutre : déformée', 'tsol', 'Treillis', 'shear', 'Cisaillement', 'bearing', 'Matage', 'key', 'Clavette', ...
                'pin', 'Goupille', 'analysis', 'Flambage', 'principal', 'Contraintes principales', 'facet', 'Facette', ...
                'plane2D', 'Mohr plan', 'criteria', 'Critères', 'mohr', 'Cercle de Mohr', 'gauge', 'Jauge', 'bridge', 'Pont', 'rosette', 'Rosette', ...
                'P', 'Section : analytique', 'traction', 'Traction', 'torsion', 'Torsion');
            L = cell(0, 2);
            p = paths.(key);
            for k = 1:numel(p)
                parts = strsplit(p{k}, '.');
                s = app.Results;
                okp = true;
                for j = 1:numel(parts)
                    if isstruct(s) && isfield(s, parts{j})
                        s = s.(parts{j});
                    else
                        okp = false;
                        break
                    end
                end
                if okp && isstruct(s) && isfield(s, 'latex') && ~isempty(s.latex)
                    lat = s.latex;
                    if ischar(lat) || isstring(lat)
                        lat = cellstr(lat);
                    end
                    nm = parts{end};
                    if isfield(names, nm)
                        nm = names.(nm);
                    end
                    L(end + 1, :) = {nm, lat(:)}; %#ok<AGROW>
                end
            end
        end

        function html = resultsHTML(app, key)
            W = app.H.(key).W;
            html = '';
            tn = fieldnames(W.Tables);
            titles = {};
            try
                tabs = W.ResGroup.Children;
                titles = {tabs(2:end).Title};
            catch
            end
            for k = 1:numel(tn)
                t = W.Tables.(tn{k});
                ttl = tn{k};
                if k <= numel(titles)
                    ttl = titles{k};
                end
                rn = [];
                try
                    if iscell(t.RowName) && ~isempty(t.RowName)
                        rn = t.RowName;
                    end
                catch
                end
                html = [html '<h3>' ValidationReport.esc(ttl) '</h3>' ValidationReport.tableHTML(t.Data, t.ColumnName, rn)]; %#ok<AGROW>
            end
            if isempty(html)
                html = '<p>Aucun tableau.</p>';
            end
        end

        function html = plotsHTML(app, key, m)
            W = app.H.(key).W;
            if ~isprop(app.UIFigure, 'Theme')
                error('MecaStruct:Validation:oldMatlab', 'Diagrammes indisponibles : MATLAB R2025a ou plus récent requis (version installée : %s).', version('-release'));
            end
            th = app.UIFigure.Theme;
            app.UIFigure.Theme = 'light';
            cl = onCleanup(@() ValidationReport.restoreTheme(app, th));
            tmp = tempname;
            mkdir(tmp);
            cl2 = onCleanup(@() ValidationReport.rmTemp(tmp));
            html = '';
            for k = 1:numel(W.Axes)
                try
                    app.selectTab(m.sel, k);
                catch
                end
                drawnow;
                pause(0.4);
                ttl = sprintf('Diagramme %d', k);
                try
                    ttl = W.PlotGroup.Children(k).Title;
                catch
                end
                imgs = '';
                axs = W.Axes{k};
                for j = 1:numel(axs)
                    ax = axs(j);
                    % axe inutilisé = axe vidé (cla) ; axe de pur texte = équations déjà données au §6 ;
                    % la propriété Visible n'est pas fiable (« off » sur un axe tracé selon la sélection d'onglet)
                    if ~isgraphics(ax) || isempty(ax.Children) || all(arrayfun(@(c) isa(c, 'matlab.graphics.primitive.Text'), ax.Children))
                        continue
                    end
                    f = fullfile(tmp, sprintf('p%d_%d.png', k, j));
                    try
                        exportgraphics(ax, f, 'Resolution', 130);
                        imgs = [imgs '<figure><img alt="' ValidationReport.esc(ttl) '" src="data:image/png;base64,' ValidationReport.b64(f) '"></figure>']; %#ok<AGROW>
                    catch err
                        imgs = [imgs '<p class="warn">Diagramme non exporté : ' ValidationReport.esc(err.message) '</p>']; %#ok<AGROW>
                    end
                end
                if ~isempty(imgs)
                    html = [html '<h3>' ValidationReport.esc(ttl) '</h3>' imgs]; %#ok<AGROW>
                end
            end
            try
                app.selectTab(m.sel, 1);
            catch
            end
            if isempty(html)
                html = '<p>Aucun diagramme disponible.</p>';
            end
        end

        function html = reportHTML(W)
            lines = W.Report.Value;
            e = ValidationReport.esc;
            html = '<details open><summary>Afficher / masquer</summary><div class="rep">';
            for k = 1:numel(lines)
                s = char(lines{k});
                if startsWith(strtrim(s), '===')
                    html = [html '<div class="rsec">' e(strtrim(regexprep(s, '^\s*=+\s*|\s*=+\s*$', ''))) '</div>']; %#ok<AGROW>
                else
                    html = [html '<div class="rln">' e(s) '</div>']; %#ok<AGROW>
                end
            end
            html = [html '</div></details>'];
        end

        function html = formulasHTML(m)
            e = ValidationReport.esc;
            html = '';
            seen = {};
            for k = 1:numel(m.forms)
                sh = DataManager.formulaSheet(m.forms{k});
                for j = 1:numel(sh)
                    if ~ismember(sh(j).title, m.keep) || ismember(sh(j).title, seen)
                        continue
                    end
                    seen{end + 1} = sh(j).title; %#ok<AGROW>
                    html = [html '<div class="eqblock"><div class="eqtitle">' e(sh(j).title) '</div>' ...
                        '<div class="eq">' ValidationReport.mjRaw(sh(j).latex) '</div>' ...
                        '<div class="var">' e(sh(j).vars) '</div></div>']; %#ok<AGROW>
                end
            end
            html = [html '<p class="muted">Fiches complètes : onglet Base de données, bouton Note de calcul.</p>'];
        end

        function html = reviewHTML()
            html = ['<table><tr><th>Question</th><th>Avis</th></tr>' ...
                '<tr><td>Le modèle physique est adapté à ce problème (hypothèses du §2).</td><td class="rv">' ValidationReport.choices() '</td></tr>' ...
                '<tr><td>Les équations du §3 sont justes.</td><td class="rv">' ValidationReport.choices() '</td></tr>' ...
                '<tr><td>Les valeurs du solveur sont cohérentes avec ma vérification.</td><td class="rv">' ValidationReport.choices() '</td></tr>' ...
                '<tr><td>Les diagrammes (§5) sont cohérents (signes, allures, extrema).</td><td class="rv">' ValidationReport.choices() '</td></tr>' ...
                '<tr><td>Les données d''entrée (§1) sont correctes.</td><td class="rv">' ValidationReport.choices() '</td></tr>' ...
                '</table>' ...
                '<p>Commentaires :</p><div class="comment"></div>' ...
                '<p>Relecteur : ______________________ &nbsp; Date : ____________ &nbsp; Conclusion : &#9744; validé &nbsp; &#9744; validé avec réserves &nbsp; &#9744; refusé</p>'];
        end
    end

    %% =============================================================================================
    %  Hypothèses et contrôles d'applicabilité
    %  =============================================================================================
    methods (Static, Access = private)

        function s = extraStatements(app, key)
            % Hypothèses des résultats ajoutés à l'onglet Poutres, seulement s'ils ont été calculés.
            s = {};
            if ~strcmp(key, 'Beam')
                return
            end
            R = app.Results;
            if isfield(R, 'combos') && ~isempty(R.combos)
                s{end + 1} = ['Combinaisons : superposition linéaire des cas G, Q, W, S avec les coefficients saisis (non imposés par une norme) ; ' ...
                    'l''enveloppe associe des maxima non simultanés.'];
            end
            if isfield(R, 'ec3') && ~isempty(R.ec3)
                s{end + 1} = ['Eurocode 3 (EN 1993-1-1) : valeurs recommandées, annexe nationale non appliquée ; fy = Re sans réduction avec l''épaisseur ; ' ...
                    'profilés IPE, HEA, HEB, IPN ou sections en I, classes 1 à 3 ; flexion autour de l''axe fort.'];
                s{end + 1} = ['Déversement : poutre à fourches, charge au centre de torsion, Iw estimé par Iz(h − tf)²/4, C1 et Lcr saisis, ' ...
                    'pas de coefficient f de répartition du moment.'];
                s{end + 1} = ['Efforts de calcul : N et M maximaux associés sans être simultanés (prudent) ; interaction N + M (§6.3.3) par l''annexe B, ' ...
                    'tableau B.2, avec Cmy et CmLT saisis ; voilement de l''âme par cisaillement (EN 1993-1-5 §5) sans la contribution des semelles.'];
            end
            if isfield(R, 'fatigue') && ~isempty(R.fatigue)
                s{end + 1} = 'Fatigue : droite de Goodman modifiée, acier, vie infinie, Se = ka·kb·0,5·Rm, Kf = Kt, amplitude constante (Shigley, chap. 6).';
            end
            if isfield(R, 'profiles') && ~isempty(R.profiles)
                s{end + 1} = ['Profilé le plus léger : critère Kt·σ ≤ Re/s (et flèche si demandée), sans Eurocode 3, avec le chargement saisi ; ' ...
                    'section supposée sans produit d''inertie.'];
            end
        end

        function s = hypStatements(key)
            common = {'Matériau homogène, isotrope, élastique linéaire (σ = E ε jusqu''à Re).', ...
                'Petits déplacements et petites déformations : équilibre écrit sur la géométrie non déformée.'};
            switch key
                case 'Sec'
                    s = {'Section constituée de rectangles, disques et couronnes (additifs ou soustractifs).', ...
                        'Les profilés du catalogue sont modélisés par une géométrie simplifiée (congés ignorés).', ...
                        'Contrainte de cisaillement de Jourawski uniforme sur la largeur b(y) de la section.'};
                case 'Beam'
                    s = [common, {'Poutre droite à section et matériau constants, longueur très supérieure à la hauteur.', ...
                        'Sections planes qui restent planes et perpendiculaires à la ligne moyenne (Bernoulli).', ...
                        'Effet de l''effort tranchant sur la flèche négligé, sauf option Castigliano avec tranchant.', ...
                        'Liaisons parfaites (sans frottement), appuis rigides (aucun tassement).', ...
                        'Charges dans le plan de symétrie, sans déversement ni instabilité.'}];
                case 'Tr'
                    s = [common, {'Barres articulées sans frottement aux nœuds.', ...
                        'Charges et appuis uniquement aux nœuds ; poids propre négligé.', ...
                        'Chaque barre ne subit qu''un effort normal constant.', ...
                        'Le flambage des barres comprimées n''est pas vérifié ici.'}];
                case 'Tra'
                    s = [common, {'Barre droite, effort normal centré, contrainte uniforme dans la section (Saint-Venant).', ...
                        'Concentration de contrainte représentée par un coefficient Kt appliqué à la contrainte nominale.', ...
                        'Si la section est variable : variation lente de S(x) (pas de changement brusque).'}];
                case 'Cis'
                    s = [common, {'Cisaillement simple : τ uniforme sur la section cisaillée (premier ordre).', ...
                        'Matage : pression uniforme sur la surface projetée.', ...
                        'Critère de résistance au glissement : τe = Re/2 (Tresca) ou Re/√3 (Von Mises).', ...
                        'Pressions admissibles de matage prises dans la table du cours.'}];
                case 'Tor'
                    s = [common, {'Arbre de section circulaire (pleine ou creuse), constante.', ...
                        'Sections planes qui restent planes et circulaires ; rayons qui restent droits.', ...
                        'Moment de torsion constant le long de l''arbre ; zones d''appui et de variation de section écartées (Saint-Venant).'}];
                case 'Fle'
                    s = [common, {'Sections planes qui restent planes (Navier-Bernoulli) ; flexion composée déviée par superposition.', ...
                        'Axes principaux, ou formule générale si le produit d''inertie n''est pas nul.', ...
                        'Contrainte maximale cherchée aux points du contour de la section.'}];
                case 'Fla'
                    s = {'Poutre droite, section constante, compression centrée, imperfections négligées.', ...
                        'Flambage dans le plan de plus faible inertie.', ...
                        'Arbre de décision du cours : compression simple (λ < 20), Rankine, Euler (λ ≥ λlim).', ...
                        'Conditions aux limites idéalisées (longueur de flambement L'' = c·L).'};
                case 'Ten'
                    s = [common, {'Tenseur des contraintes symétrique en un point.', ...
                        'Matériau ductile pour Tresca et Von Mises ; contrainte normale maximale pour un matériau fragile.'}];
                case 'Hoo'
                    s = [common, {'Matériau isotrope (2 constantes E, ν) ou orthotrope aux axes d''orthotropie alignés sur x, y, z.', ...
                        'Cisaillements en notation d''ingénieur dans Voigt (γ = 2ε).'}];
                case 'Jau'
                    s = {'Loi de la jauge ΔR/R = K ε (K constant, pas d''effet de température).', ...
                        'Pont de Wheatstone linéarisé ; l''erreur de linéarité est affichée.', ...
                        'Rosette : état de déformation plan, contraintes planes pour passer aux contraintes.'};
                otherwise
                    s = common;
            end
        end

        function chk = autoChecks(app, key)
            chk = cell(0, 3);
            add = @(t, d, st) ValidationReport.addChk(t, d, st);
            switch key
                case 'Sec'
                    C = app.Results.section.compare;
                    % seulement analytique / intégrale : la colonne tabulée du catalogue s'écarte de la géométrie simplifiée
                    ec = C.Properties.UserData.ecartAB_pct;
                    chk = [chk; add('Méthodes analytique et intégrale concordantes', sprintf('écart maximal %.3g %%', ec), ec < 1e-6)];
                    sec = app.Results.section.sec;
                    if strcmp(sec.type, 'profile')
                        chk = [chk; add('Profilé du catalogue : géométrie simplifiée', 'congés ignorés : voir l''écart avec les valeurs tabulées au §4', 'warn')];
                    end
                case 'Beam'
                    B = app.Results.beam;
                    L = B.model.L;
                    vy = max(app.H.Beam.vy.Value, 1e-9) * 1e-3;
                    chk = [chk; add('Poutre élancée : L/h ≥ 10 (h ≈ 2·vy)', sprintf('L/h = %.3g', L / (2 * vy)), ...
                        ValidationReport.lvl(L / (2 * vy) >= 10, 'warn'))];
                    f = abs(B.defl.integration.fmax);
                    chk = [chk; add('Petits déplacements : f max / L ≤ 1/50', sprintf('f max/L = 1/%.3g', L / max(f, eps)), ...
                        ValidationReport.lvl(f / L <= 1 / 50, 'warn'))];
                    bd = B.check.bend;
                    chk = [chk; add('Domaine élastique : σ max ≤ Re', sprintf('σ max = %.4g MPa ; Re = %.4g MPa', bd.sigmaMaxAbs / 1e6, bd.sigmaAdm * app.H.Beam.s.Value / 1e6), ...
                        ValidationReport.lvl(bd.sigmaMaxAbs <= bd.sigmaAdm * app.H.Beam.s.Value, 'ko'))];
                    chk = [chk; add('Résistance avec coefficient de sécurité : Kt·σ max ≤ Re/s', sprintf('%.4g MPa ≤ %.4g MPa', bd.sigmaMaxKt / 1e6, bd.sigmaAdm / 1e6), ...
                        ValidationReport.lvl(logical(bd.ok), 'ko'))];
                    nmin = B.sol.extrema.N.min;
                    if nmin < -1e-6
                        chk = [chk; add('Effort normal de compression présent', sprintf('N min = %.4g kN : vérifier le flambage (onglet Flambage)', nmin / 1e3), 'warn')];
                    end
                    if ~B.sol.isostatic
                        chk = [chk; add('Poutre hyperstatique : réactions par Ménabréa et par intégration', sprintf('écart coupures/intégrale = %.2g', B.sol.methodCheck), ...
                            ValidationReport.lvl(B.sol.methodCheck < 1e-6, 'warn'))];
                    end
                    if ~B.sol.isostatic && app.H.Beam.Iyz.Value ~= 0
                        chk = [chk; add('LIMITE DU LOGICIEL : poutre hyperstatique avec Iyz ≠ 0', ...
                            ['réactions calculées plan par plan : le couplage y–z des inconnues hyperstatiques est ignoré, ' ...
                            'réactions, moments et contraintes NON fiables ; saisir la section dans ses axes principaux (Iyz = 0)'], ...
                            ValidationReport.lvl(false, 'ko'))];
                    end
                    mo = B.sol.model;
                    if any([mo.supports.spring] > 0) || any(abs([mo.supports.dx mo.supports.dy mo.supports.dz]) > 0) ...
                            || ~isempty(mo.hinges) || any(abs([mo.thermal.epsX mo.thermal.kv mo.thermal.kw]) > 0)
                        chk = [chk; add('Ressorts, tassements, rotules ou température présents', ...
                            ['les réactions ne sont pas recalculées à la main (le dossier contrôle l''équilibre, les conditions aux appuis et le moment nul aux rotules) ; ' ...
                            'elles sont obtenues par deux méthodes indépendantes (Ménabréa et intégration) et la flèche par quatre'], 'warn')];
                    end
                    chk = [chk; add('Effet de l''effort tranchant sur la flèche', sprintf('inclus dans Castigliano : %s', ValidationReport.yesNo(app.H.Beam.shear.Value)),...
                        ValidationReport.lvl(app.H.Beam.shear.Value || L / (2 * vy) >= 10, 'warn'))];
                    chk = [chk; ValidationReport.extraChecks(app)];
                case 'Tr'
                    R = app.Results.truss;
                    ts = R.tsol;
                    chk = [chk; add('Treillis non mécanisme (h ≥ 0)', sprintf('h = %d', ts.h), ValidationReport.lvl(ts.h >= 0 && ~ts.mechanism, 'ko'))];
                    Re = app.DM.getMaterial(app.H.Tr.mat.Value).Re;
                    chk = [chk; add('Domaine élastique : |σ| max ≤ Re', sprintf('|σ| max = %.4g MPa ; Re = %.4g MPa', max(abs(ts.sigma)) / 1e6, Re / 1e6), ...
                        ValidationReport.lvl(max(abs(ts.sigma)) <= Re, 'ko'))];
                    nc = nnz(strcmp(ts.nature, 'Compression'));
                    if nc > 0
                        chk = [chk; add('Barres comprimées : flambage à vérifier', sprintf('%d barre(s) en compression, |N| max = %.4g kN', nc, max(abs(ts.N(ts.N < 0))) / 1e3), 'warn')];
                    end
                    Lmin = min(ts.L0);
                    umax = max(vecnorm(ts.displacements, 2, 2));
                    chk = [chk; add('Petits déplacements : u max / L min ≤ 1 %', sprintf('u max = %.4g mm ; L min = %.4g m', umax * 1e3, Lmin), ...
                        ValidationReport.lvl(umax / Lmin <= 0.01, 'warn'))];
                case 'Tra'
                    r = app.Results.traction;
                    T = app.H.Tra;
                    chk = [chk; add('Domaine élastique : σ max ≤ Re', sprintf('σ max = %.4g MPa ; Re = %.4g MPa', abs(r.sigmaMax) / 1e6, T.Re.Value), ...
                        ValidationReport.lvl(abs(r.sigmaMax) / 1e6 <= T.Re.Value, 'ko'))];
                    chk = [chk; add('Résistance : Kt·σ ≤ Re/s', sprintf('%.4g MPa ≤ %.4g MPa', abs(r.sigmaMax) / 1e6, r.sigmaAdm / 1e6), ValidationReport.lvl(logical(r.okResistance), 'ko'))];
                    chk = [chk; add('Petites déformations : |ΔL|/L0 ≤ 1 %', sprintf('%.3g %%', 100 * abs(r.dL.integrale) / T.L0.Value), ...
                        ValidationReport.lvl(abs(r.dL.integrale) / T.L0.Value <= 0.01, 'warn'))];
                    if T.N.Value < 0
                        chk = [chk; add('Effort de compression : flambage à vérifier', 'voir l''onglet Flambage', 'warn')];
                    end
                    if T.varS.Value
                        chk = [chk; add('Section variable', 'hypothèse : variation lente de S(x) ; ΔL analytique à S constante non représentatif', 'warn')];
                    end
                case 'Cis'
                    r = app.Results.shear.shear;
                    b = app.Results.shear.bearing;
                    chk = [chk; add('Cisaillement : k·T/S ≤ τe/s', sprintf('%.4g MPa ≤ %.4g MPa', r.tauMax / 1e6, r.tauAdm / 1e6), ValidationReport.lvl(logical(r.ok), 'ko'))];
                    chk = [chk; add('Matage : P ≤ Padm', sprintf('%.4g MPa ≤ %.4g MPa', b.P / 1e6, app.H.Cis.Padm.Value), ValidationReport.lvl(logical(b.ok), 'ko'))];
                    chk = [chk; add('Pression admissible dans la plage du cours (0,5 à 150 MPa)', sprintf('Padm = %.4g MPa', app.H.Cis.Padm.Value), ...
                        ValidationReport.lvl(app.H.Cis.Padm.Value >= 0.5 && app.H.Cis.Padm.Value <= 150, 'warn'))];
                    if isfield(app.Results, 'pin')
                        chk = [chk; add('Matage de la goupille : formule du cours P = 2F/(d e)', 'beaucoup de manuels écrivent F/(d e) : à confirmer avec le montage', 'warn')];
                    end
                case 'Tor'
                    r = app.Results.torsion;
                    T = app.H.Tor;
                    chk = [chk; add('Résistance : Kt·τ max ≤ τe/s', sprintf('%.4g MPa ≤ %.4g MPa', r.tauMax / 1e6, r.tauAdm / 1e6), ValidationReport.lvl(logical(r.okResistance), 'ko'))];
                    chk = [chk; add('Rigidité : θ ≤ θ admissible', sprintf('θ = %.4g °/m ; θ adm = %.4g °/m', rad2deg(r.theta), T.thetaAdm.Value), ...
                        ValidationReport.lvl(logical(r.okRigidite), 'ko'))];
                    chk = [chk; add('Arbre long devant son diamètre (Saint-Venant) : L/D ≥ 3', sprintf('L/D = %.3g', T.L.Value * 1e3 / T.D.Value), ...
                        ValidationReport.lvl(T.L.Value * 1e3 / T.D.Value >= 3, 'warn'))];
                case 'Fle'
                    R = app.Results.bending;
                    bd = R.bend;
                    Re = app.H.Fle.Re.Value;
                    chk = [chk; add('Domaine élastique : |σ| max ≤ Re', sprintf('%.4g MPa ≤ %.4g MPa', bd.sigmaMaxAbs / 1e6, Re), ValidationReport.lvl(bd.sigmaMaxAbs / 1e6 <= Re, 'ko'))];
                    chk = [chk; add('Résistance : Kt·|σ| max ≤ Re/s', sprintf('%.4g MPa ≤ %.4g MPa', bd.sigmaMaxKt / 1e6, bd.sigmaAdm / 1e6), ValidationReport.lvl(logical(bd.ok), 'ko'))];
                    chk = [chk; add('Axes principaux (Iyz = 0) ou formule générale utilisée', sprintf('formule générale : %s', ValidationReport.yesNo(bd.usedGeneralFormula)), 'ok')];
                case 'Fla'
                    b = app.Results.buckling.analysis;
                    chk = [chk; add('Régime de flambage', sprintf('λ = %.4g ; λlim = %.4g ; régime %s', b.lambda, b.lambdaLim, b.regime), 'ok')];
                    chk = [chk; add('Élancement raisonnable : λ ≤ 200', sprintf('λ = %.4g', b.lambda), ValidationReport.lvl(b.lambda <= 200, 'warn'))];
                    if b.lambda < 20
                        chk = [chk; add('Poutre trapue (λ < 20) : compression simple', 'le flambage est négligeable', 'ok')];
                    end
                    if isfinite(b.P)
                        chk = [chk; add('Stabilité : P ≤ Padm', sprintf('%.4g kN ≤ %.4g kN', b.P / 1e3, b.Padm / 1e3), ValidationReport.lvl(logical(b.ok), 'ko'))];
                    end
                    if strcmp(app.H.Fla.cond.Value, 'encastre-articule')
                        chk = [chk; add('Encastré-articulé : L'' = L/√2 (valeur exacte 0,6992 L)', 'écart de 1 % sur L'', du côté sécuritaire', 'warn')];
                    end
                case 'Ten'
                    r = app.Results.tensor;
                    chk = [chk; add('Tenseur symétrique (symétrisé automatiquement)', 'σij = σji', 'ok')];
                    chk = [chk; add('Critère de Von Mises respecté', sprintf('σVM = %.4g MPa ≤ %.4g MPa', r.criteria.sigmaEqVM / 1e6, r.criteria.sigmaAdm / 1e6), ...
                        ValidationReport.lvl(logical(r.criteria.okVM), 'ko'))];
                    chk = [chk; add('Critère de Tresca respecté', sprintf('%.4g MPa ≤ %.4g MPa', r.criteria.sigmaEqTresca / 1e6, r.criteria.sigmaAdm / 1e6), ...
                        ValidationReport.lvl(logical(r.criteria.okTresca), 'ko'))];
                case 'Hoo'
                    K = app.H.Hoo;
                    nu = K.nu.Value;
                    if strcmp(K.mode.Value, 'ortho')
                        chk = [chk; add('Matériau orthotrope : [S] symétrique, [C] définie positive', 'vérifié par le solveur (erreur sinon)', 'ok')];
                    else
                        chk = [chk; add('Coefficient de Poisson dans ]−1 ; 0,5[', sprintf('ν = %.4g', nu), ValidationReport.lvl(nu > -1 && nu < 0.5, 'ko'))];
                        chk = [chk; add('Module de Young positif', sprintf('E = %.4g GPa', K.E.Value), ValidationReport.lvl(K.E.Value > 0, 'ko'))];
                    end
                    if strcmp(K.mode.Value, 'planeStress')
                        chk = [chk; add('Contraintes planes : σzz = σxz = σyz = 0 par hypothèse', 'les valeurs de σzz, σxz, σyz saisies sont ignorées', 'warn')];
                    end
                case 'Jau'
                    J = app.Results.gauges;
                    chk = [chk; add('Facteur de jauge usuel (1,8 à 2,2 pour une jauge métallique)', sprintf('K = %.4g', app.H.Jau.K.Value), ...
                        ValidationReport.lvl(app.H.Jau.K.Value >= 1.8 && app.H.Jau.K.Value <= 2.2, 'warn'))];
                    chk = [chk; add('Linéarisation du pont : erreur ≤ 1 %', sprintf('%.3g %%', J.bridge.linearityError * 100), ...
                        ValidationReport.lvl(abs(J.bridge.linearityError) <= 0.01, 'warn'))];
            end
        end

        function chk = extraChecks(app)
            % Contrôles d'applicabilité des résultats ajoutés à l'onglet Poutres (si calculés).
            chk = cell(0, 3);
            add = @(t, d, st) ValidationReport.addChk(t, d, st);
            R = app.Results;
            B = app.H.Beam;
            if isfield(R, 'combos') && ~isempty(R.combos)
                T = R.combos;
                nErr = sum(contains(string(T.("Résistance")), "erreur"));
                chk = [chk; add('Combinaisons : toutes résolues sans erreur', sprintf('%d combinaison(s), %d en erreur', height(T) - 1, nErr), ValidationReport.lvl(nErr == 0, 'ko'))];
                env = T(end, :);
                chk = [chk; add('Combinaisons : résistance sur l''enveloppe (Kt·σ ≤ Re/s)', sprintf('%.4g MPa ≤ %.4g MPa', env.("Kt·σ max (MPa)"), env.("σadm (MPa)")), ...
                    ValidationReport.lvl(env.("Kt·σ max (MPa)") <= env.("σadm (MPa)"), 'ko'))];
            end
            if isfield(R, 'ec3') && ~isempty(R.ec3)
                r = R.ec3;
                chk = [chk; add('Eurocode 3 : classe de section 1 à 3', sprintf('classe %d', r.class.class), ValidationReport.lvl(r.class.class <= 3, 'ko'))];
                chk = [chk; add('Eurocode 3 : résistance des sections (flexion, tranchant)', sprintf('MEd/MRd = %.3f ; VEd/Vpl,Rd = %.3f', r.ratioM, r.ratioV), ValidationReport.lvl(r.ok, 'ko'))];
                chk = [chk; add('Eurocode 3 : déversement', sprintf('MEd/Mb,Rd = %.3f (Lcr = %.4g m, C1 = %.3g)', r.ltb.ratio, max(B.Lcr.Value, 0) + (B.Lcr.Value <= 0) * B.L.Value, B.C1.Value), ValidationReport.lvl(r.ltb.ok, 'ko'))];
                chk = [chk; add('Eurocode 3 : flexion + effort normal', sprintf('rapport = %.3f', r.axial.ratio), ValidationReport.lvl(r.axial.ok, 'ko'))];
                if ~isempty(r.buck)
                    chk = [chk; add('Eurocode 3 : flambement', sprintf('NEd/Nb,Rd = %.3f', r.buck.ratio), ValidationReport.lvl(r.buck.ok, 'ko'))];
                end
                if ~isempty(r.inter)
                    chk = [chk; add('Eurocode 3 : interaction N + M (6.61 et 6.62, annexe B)', sprintf('rapport = %.3f (Cmy = %.2f, CmLT = %.2f)', r.inter.ratio, r.inter.Cmy, r.inter.CmLT), ValidationReport.lvl(r.inter.ok, 'ko'))];
                end
                chk = [chk; add('Eurocode 3 : voilement de l''âme par cisaillement', ValidationReport.yesNoWeb(r.web), ValidationReport.lvl(r.web.ok, 'ko'))];
                chk = [chk; add('Eurocode 3 : annexe nationale', 'seules γM0 et γM1 sont paramétrables (France : mêmes valeurs que l''EN) ; vérifier les autres paramètres dans l''annexe du pays', 'warn')];
                chk = [chk; add('Eurocode 3 : fy = Re', sprintf('fy = %.4g MPa, sans réduction avec l''épaisseur (EN 1993-1-1 tableau 3.1)', B.Re.Value), 'warn')];
            end
            if isfield(R, 'fatigue') && ~isempty(R.fatigue)
                chk = [chk; add('Fatigue (Goodman) : n ≥ s', sprintf('n = %.3g ; s = %.3g', R.fatigue.n, B.s.Value), ValidationReport.lvl(R.fatigue.n >= B.s.Value, 'ko'))];
                chk = [chk; add('Fatigue : limite d''endurance estimée (ka, kb saisis)', sprintf('Se = %.4g MPa', R.fatigue.Se / 1e6), 'warn')];
            end
            if isfield(R, 'profiles') && ~isempty(R.profiles)
                ok = ~contains(string(R.profiles.("Résistance")), "NON") & ~contains(string(R.profiles.("Résistance")), "erreur");
                chk = [chk; add('Profilé le plus léger : au moins un profilé de la famille vérifie', sprintf('%d profilé(s) sur %d', sum(ok), height(R.profiles)), ValidationReport.lvl(any(ok), 'warn'))];
            end
        end

        function row = addChk(t, d, st)
            if islogical(st)
                if st
                    st = 'ok';
                else
                    st = 'ko';
                end
            end
            row = {t, d, st};
        end

        function st = lvl(cond, bad)
            if cond
                st = 'ok';
            else
                st = bad;
            end
        end
    end

    %% =============================================================================================
    %  Vérification indépendante « à la main » (aucun appel aux moteurs de calcul)
    %  =============================================================================================
    methods (Static, Access = private)

        function r = hc(label, latex, hand, solver, unit, tol)
            if nargin < 6
                tol = NaN;
            end
            r = struct('label', label, 'latex', latex, 'hand', hand, 'solver', solver, 'unit', unit, 'tol', tol);
        end

        function r = grp(label)
            r = struct('label', label, 'latex', '', 'hand', [], 'solver', [], 'unit', '', 'tol', NaN);
        end

        function rows = handRows(app, key)
            switch key
                case 'Sec', rows = ValidationReport.handSec(app);
                case 'Beam', rows = ValidationReport.handBeam(app);
                case 'Tr', rows = ValidationReport.handTruss(app);
                case 'Tra', rows = ValidationReport.handTra(app);
                case 'Cis', rows = ValidationReport.handCis(app);
                case 'Tor', rows = ValidationReport.handTor(app);
                case 'Fle', rows = ValidationReport.handFle(app);
                case 'Fla', rows = ValidationReport.handFla(app);
                case 'Ten', rows = ValidationReport.handTen(app);
                case 'Hoo', rows = ValidationReport.handHoo(app);
                case 'Jau', rows = ValidationReport.handJau(app);
                otherwise, rows = {};
            end
        end

        function rows = handSec(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            R = app.Results.section;
            sec = R.sec;
            P = R.P;
            rows = {};
            mm = @(x) x * 1e3;
            switch sec.type
                case 'rectangle'
                    b = mm(sec.b); h = mm(sec.h);
                    S = b * h; Iz = b * h^3 / 12; Iy = h * b^3 / 12;
                    fS = sprintf('S=b\\,h=%s\\times%s', n(b), n(h));
                    fIz = sprintf('I_z=\\frac{b\\,h^3}{12}=\\frac{%s\\times%s^3}{12}', n(b), n(h));
                    fIy = sprintf('I_y=\\frac{h\\,b^3}{12}=\\frac{%s\\times%s^3}{12}', n(h), n(b));
                case 'disque'
                    D = mm(sec.D);
                    S = pi * D^2 / 4; Iz = pi * D^4 / 64; Iy = Iz;
                    fS = sprintf('S=\\frac{\\pi D^2}{4}=\\frac{\\pi\\times%s^2}{4}', n(D));
                    fIz = sprintf('I_z=\\frac{\\pi D^4}{64}=\\frac{\\pi\\times%s^4}{64}', n(D));
                    fIy = 'I_y=I_z';
                case 'couronne'
                    D = mm(sec.D); d = mm(sec.d);
                    S = pi * (D^2 - d^2) / 4; Iz = pi * (D^4 - d^4) / 64; Iy = Iz;
                    fS = sprintf('S=\\frac{\\pi(D^2-d^2)}{4}=\\frac{\\pi(%s^2-%s^2)}{4}', n(D), n(d));
                    fIz = sprintf('I_z=\\frac{\\pi(D^4-d^4)}{64}=\\frac{\\pi(%s^4-%s^4)}{64}', n(D), n(d));
                    fIy = 'I_y=I_z';
                case 'rectangle_creux'
                    B = mm(sec.B); H = mm(sec.H); t = mm(sec.t);
                    S = B * H - (B - 2 * t) * (H - 2 * t);
                    Iz = (B * H^3 - (B - 2 * t) * (H - 2 * t)^3) / 12;
                    Iy = (H * B^3 - (H - 2 * t) * (B - 2 * t)^3) / 12;
                    fS = sprintf('S=BH-(B-2t)(H-2t)=%s\\times%s-%s\\times%s', n(B), n(H), n(B - 2 * t), n(H - 2 * t));
                    fIz = sprintf('I_z=\\frac{BH^3-(B-2t)(H-2t)^3}{12}');
                    fIy = sprintf('I_y=\\frac{HB^3-(H-2t)(B-2t)^3}{12}');
                case 'I'
                    h = mm(sec.h); b = mm(sec.b); tw = mm(sec.tw); tf = mm(sec.tf);
                    S = 2 * b * tf + tw * (h - 2 * tf);
                    Iz = (b * h^3 - (b - tw) * (h - 2 * tf)^3) / 12;
                    Iy = (2 * tf * b^3 + (h - 2 * tf) * tw^3) / 12;
                    fS = sprintf('S=2\\,b\\,t_f+t_w(h-2t_f)=2\\times%s\\times%s+%s\\times%s', n(b), n(tf), n(tw), n(h - 2 * tf));
                    fIz = sprintf('I_z=\\frac{b\\,h^3-(b-t_w)(h-2t_f)^3}{12}=\\frac{%s\\times%s^3-%s\\times%s^3}{12}', n(b), n(h), n(b - tw), n(h - 2 * tf));
                    fIy = sprintf('I_y=\\frac{2\\,t_f\\,b^3+(h-2t_f)\\,t_w^3}{12}');
                otherwise
                    rows = {ValidationReport.grp(['Section de type « ' sec.type ' » : formules fermées non recalculées ici ; la comparaison analytique / intégrale / tabulée est au §4.'])};
                    return
            end
            rows = {ValidationReport.grp('Caractéristiques géométriques (mm, mm², mm⁴)')
                hc('Aire S', [fS '=' n(S) '\,\mathrm{mm^2}'], S, P.S * 1e6, 'mm²')
                hc('Moment quadratique Iz', [fIz '=' n(Iz) '\,\mathrm{mm^4}'], Iz, P.Iz * 1e12, 'mm⁴')
                hc('Moment quadratique Iy', [fIy '=' n(Iy) '\,\mathrm{mm^4}'], Iy, P.Iy * 1e12, 'mm⁴')
                hc('Rayon de giration rz', sprintf('r_z=\\sqrt{I_z/S}=\\sqrt{%s/%s}', n(Iz), n(S)), sqrt(Iz / S), P.rz * 1e3, 'mm')
                hc('Module de flexion Wz', sprintf('W_z=\\frac{I_z}{v_{max}}=\\frac{%s}{%s}', n(Iz), n(max(P.vyTop, P.vyBot) * 1e3)), ...
                Iz / (max(P.vyTop, P.vyBot) * 1e3), P.Wz * 1e9, 'mm³')};
        end

        function rows = handTra(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            T = app.H.Tra;
            r = app.Results.traction;
            N = T.N.Value * 1e3; S0 = T.S0.Value; L0 = T.L0.Value; E = T.E.Value * 1e3;
            nu = T.nu.Value; al = T.alpha.Value * 1e-6; dT = T.dT.Value; Kt = T.Kt.Value; Re = T.Re.Value; s = T.s.Value;
            sig = N / S0;
            dLa = N * L0 * 1e3 / (E * S0) + al * dT * L0 * 1e3;
            rows = {
                ValidationReport.grp('Contraintes (N en N, S en mm², contraintes en MPa)')
                hc('Contrainte nominale', sprintf('\\sigma=\\frac{N}{S_0}=\\frac{%s\\,\\mathrm{N}}{%s\\,\\mathrm{mm^2}}=%s\\,\\mathrm{MPa}', n(N), n(S0), n(sig)), sig, r.sigmaNom / 1e6, 'MPa')
                hc('Contrainte maximale', sprintf('\\sigma_{max}=K_t\\,\\sigma=%s\\times%s=%s\\,\\mathrm{MPa}', n(Kt), n(sig), n(Kt * sig)), Kt * sig, r.sigmaMax / 1e6, 'MPa')
                hc('Contrainte admissible', sprintf('\\sigma_{adm}=\\frac{R_e}{s}=\\frac{%s}{%s}=%s\\,\\mathrm{MPa}', n(Re), n(s), n(Re / s)), Re / s, r.sigmaAdm / 1e6, 'MPa')
                ValidationReport.grp('Déformations et allongement')
                hc('Déformation longitudinale', sprintf('\\varepsilon_{xx}=\\frac{\\sigma}{E}+\\alpha\\Delta T=\\frac{%s}{%s}+%s\\times%s', n(sig), n(E), n(al), n(dT)), sig / E + al * dT, r.epsxx, '')
                hc('Déformation transversale', sprintf('\\varepsilon_{yy}=-\\nu\\frac{\\sigma}{E}+\\alpha\\Delta T=-%s\\times\\frac{%s}{%s}+\\alpha\\Delta T', n(nu), n(sig), n(E)), -nu * sig / E + al * dT, r.epsyy, '')
                hc('Variation relative de volume', sprintf('\\frac{\\Delta V}{V}=(1-2\\nu)\\frac{\\sigma}{E}+3\\alpha\\Delta T=(1-2\\times%s)\\frac{%s}{%s}+3\\alpha\\Delta T', n(nu), n(sig), n(E)), (1 - 2 * nu) * sig / E + 3 * al * dT, r.dVsurV, '')
                hc('Allongement (section constante)', sprintf('\\Delta L=\\frac{N\\,L_0}{E\\,S_0}+\\alpha\\Delta T L_0=\\frac{%s\\times%s}{%s\\times%s}', n(N), n(L0 * 1e3), n(E), n(S0)), dLa, r.dL.analytique * 1e3, 'mm')};
            if T.varS.Value
                fS = MecaStruct_App.parseFunction(T.Sexpr.Value);
                Sx = @(x) DataManager.toSI(fS(x), 'mm^2');
                dLi = integral(@(x) N ./ (E * 1e6 * Sx(x)), 0, L0) * 1e3 + al * dT * L0 * 1e3;
                rows{end + 1, 1} = hc('Allongement (section variable S(x))', ...
                    sprintf('\\Delta L=\\int_0^{%s}\\frac{N}{E\\,S(x)}dx+\\alpha\\Delta T L_0\\ \\text{avec}\\ S(x)=%s', n(L0), strrep(T.Sexpr.Value, '*', '\cdot ')), dLi, r.dL.integrale * 1e3, 'mm');
            else
                rows{end + 1, 1} = hc('Allongement (intégrale)', sprintf('\\Delta L=\\int_0^{L_0}\\left(\\frac{N}{E S}+\\alpha\\Delta T\\right)dx'), dLa, r.dL.integrale * 1e3, 'mm');
            end
            rows{end + 1, 1} = hc('Raideur K', sprintf('K=\\frac{E\\,S_0}{L_0}=\\frac{%s\\times%s}{%s}', n(E), n(S0), n(L0 * 1e3)), E * S0 / (L0 * 1e3), r.K / 1e3, 'N/mm');
        end

        function rows = handCis(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            C = app.H.Cis;
            R = app.Results;
            rows = {};
            Re = C.Re.Value; s = C.s.Value;
            if contains(lower(C.crit.Value), 'tresca')
                tauE = Re / 2;
                fte = sprintf('\\tau_e=\\frac{R_e}{2}=\\frac{%s}{2}', n(Re));
            else
                tauE = Re / sqrt(3);
                fte = sprintf('\\tau_e=\\frac{R_e}{\\sqrt3}=\\frac{%s}{\\sqrt3}', n(Re));
            end
            if isfield(R, 'shear')
                r = R.shear.shear;
                b = R.shear.bearing;
                T = C.T.Value * 1e3; S = C.S.Value; k = C.k.Value;
                rows = [rows; {
                    ValidationReport.grp('Cisaillement simple (T en N, S en mm², contraintes en MPa)')
                    hc('Contrainte moyenne', sprintf('\\tau_{moy}=\\frac{T}{S}=\\frac{%s}{%s}', n(T), n(S)), T / S, r.tauMoy / 1e6, 'MPa')
                    hc('Contrainte maximale', sprintf('\\tau_{max}=k\\frac{T}{S}=%s\\times\\frac{%s}{%s}', n(k), n(T), n(S)), k * T / S, r.tauMax / 1e6, 'MPa')
                    hc('Limite élastique au cisaillement', fte, tauE, r.tauE / 1e6, 'MPa')
                    hc('Contrainte admissible', sprintf('\\tau_{adm}=\\frac{\\tau_e}{s}=\\frac{%s}{%s}', n(tauE), n(s)), tauE / s, r.tauAdm / 1e6, 'MPa')
                    ValidationReport.grp('Matage')
                    hc('Pression de matage', sprintf('P=\\frac{F}{S_{mat}}=\\frac{%s}{%s}', n(C.Fm.Value * 1e3), n(C.Sm.Value)), C.Fm.Value * 1e3 / C.Sm.Value, b.P / 1e6, 'MPa')}];
            end
            if isfield(R, 'key') && isfield(R.key, 'F')
                k2 = R.key;
                Cc = C.C.Value * 1e6; D = C.Dk.Value; a = C.ak.Value; bh = C.bk.Value; Lk = C.Lk.Value;
                rows = [rows; {
                    ValidationReport.grp('Clavette parallèle (C en N·mm, dimensions en mm)')
                    hc('Effort tangentiel', sprintf('F=\\frac{2C}{D}=\\frac{2\\times%s}{%s}', n(Cc), n(D)), 2 * Cc / D, k2.F, 'N')}];
                if isfield(k2, 'P')
                    rows = [rows; {
                        hc('Pression de matage', sprintf('P=\\frac{4C}{D\\,b\\,L}=\\frac{4\\times%s}{%s\\times%s\\times%s}', n(Cc), n(D), n(bh), n(Lk)), 4 * Cc / (D * bh * Lk), k2.P / 1e6, 'MPa')
                        hc('Contrainte de cisaillement', sprintf('\\tau=\\frac{2C}{a\\,L\\,D}=\\frac{2\\times%s}{%s\\times%s\\times%s}', n(Cc), n(a), n(Lk), n(D)), 2 * Cc / (a * Lk * D), k2.tau / 1e6, 'MPa')}];
                end
            end
            if isfield(R, 'pin')
                p = R.pin;
                F = C.Fp.Value * 1e3; d = C.dp.Value; e2 = C.ep.Value; ns = C.np.Value;
                rows = [rows; {
                    ValidationReport.grp('Goupille / rivet (F en N, d et e en mm)')
                    hc('Pression de matage (formule du cours)', sprintf('P=\\frac{2F}{d\\,e}=\\frac{2\\times%s}{%s\\times%s}', n(F), n(d), n(e2)), 2 * F / (d * e2), p.P / 1e6, 'MPa')
                    hc('Contrainte de cisaillement', sprintf('\\tau=\\frac{4F}{n\\pi d^2}=\\frac{4\\times%s}{%s\\times\\pi\\times%s^2}', n(F), n(ns), n(d)), 4 * F / (ns * pi * d^2), p.tau / 1e6, 'MPa')}];
            end
        end

        function rows = handTor(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            T = app.H.Tor;
            r = app.Results.torsion;
            Mt = T.Mt.Value * 1e6; D = T.D.Value; d = T.d.Value; G = T.G.Value * 1e3; L = T.L.Value * 1e3;
            Kt = T.Kt.Value; Re = T.Re.Value; s = T.s.Value;
            Ix = pi * (D^4 - d^4) / 32;
            tau = Mt * (D / 2) / Ix;
            if contains(lower(T.crit.Value), 'tresca')
                tauE = Re / 2;
                fte = sprintf('\\tau_e=\\frac{R_e}{2}=\\frac{%s}{2}', n(Re));
            else
                tauE = Re / sqrt(3);
                fte = sprintf('\\tau_e=\\frac{R_e}{\\sqrt3}=\\frac{%s}{\\sqrt3}', n(Re));
            end
            th = Mt / (G * Ix);
            rows = {
                ValidationReport.grp('Arbre circulaire (Mt en N·mm, D et d en mm, G en MPa)')
                hc('Moment quadratique polaire', sprintf('I_x=\\frac{\\pi(D^4-d^4)}{32}=\\frac{\\pi(%s^4-%s^4)}{32}', n(D), n(d)), Ix, r.Ix * 1e12, 'mm⁴')
                hc('Contrainte de torsion nominale', sprintf('\\tau=\\frac{M_t\\,D/2}{I_x}=\\frac{%s\\times%s}{%s}', n(Mt), n(D / 2), n(Ix)), tau, r.tauMaxNom / 1e6, 'MPa')
                hc('Contrainte maximale', sprintf('\\tau_{max}=K_t\\,\\tau=%s\\times%s', n(Kt), n(tau)), Kt * tau, r.tauMax / 1e6, 'MPa')
                hc('Limite élastique au cisaillement', fte, tauE, (r.tauAdm * s) / 1e6, 'MPa')
                hc('Contrainte admissible', sprintf('\\tau_{adm}=\\frac{\\tau_e}{s}=\\frac{%s}{%s}', n(tauE), n(s)), tauE / s, r.tauAdm / 1e6, 'MPa')
                hc('Angle unitaire de torsion', sprintf('\\theta=\\frac{M_t}{G\\,I_x}=\\frac{%s}{%s\\times%s}\\ \\mathrm{rad/mm}\\ \\times\\frac{180}{\\pi}\\times1000', n(Mt), n(G), n(Ix)), rad2deg(th) * 1e3, rad2deg(r.theta), '°/m')
                hc('Rotation totale', sprintf('\\varphi=\\theta\\,L=%s\\times%s', n(th), n(L)), th * L * 1e3, r.phi.analytique * 1e3, 'mrad')
                hc('Raideur de torsion', sprintf('K=\\frac{G\\,I_x}{L}=\\frac{%s\\times%s}{%s}', n(G), n(Ix), n(L)), G * Ix / L, r.Ktorsion * 1e3, 'N·mm/rad')};
        end

        function rows = handFle(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            R = app.Results.bending;
            bd = R.bend;
            P = R.P;
            F = app.H.Fle;
            N = F.N.Value * 1e3; Mfz = F.Mfz.Value * 1e6; Mfy = F.Mfy.Value * 1e6;
            S = P.S * 1e6; Iz = P.Iz * 1e12; Iy = P.Iy * 1e12;
            rows = {ValidationReport.grp('Contrainte normale σ = N/S − Mfz·y/Iz + Mfy·z/Iy (N, N·mm, mm)')};
            if abs(P.Iyz) > 1e-9 * max(P.Iz, P.Iy)
                rows{end + 1, 1} = ValidationReport.grp('Produit d''inertie non nul : formule générale utilisée par le solveur (non recalculée ici).');
                return
            end
            lt = bd.locMaxTraction * 1e3;
            lc = bd.locMaxCompression * 1e3;
            s1 = N / S - Mfz / Iz * lt(1) + Mfy / Iy * lt(2);
            s2 = N / S - Mfz / Iz * lc(1) + Mfy / Iy * lc(2);
            rows = [rows; {
                hc('σ au point de traction maximale', sprintf('\\sigma=\\frac{%s}{%s}-\\frac{%s}{%s}\\times(%s)+\\frac{%s}{%s}\\times(%s)', n(N), n(S), n(Mfz), n(Iz), n(lt(1)), n(Mfy), n(Iy), n(lt(2))), s1, bd.sigmaMaxTraction / 1e6, 'MPa')
                hc('σ au point de compression maximale', sprintf('\\sigma=\\frac{%s}{%s}-\\frac{%s}{%s}\\times(%s)+\\frac{%s}{%s}\\times(%s)', n(N), n(S), n(Mfz), n(Iz), n(lc(1)), n(Mfy), n(Iy), n(lc(2))), s2, bd.sigmaMaxCompression / 1e6, 'MPa')
                hc('Contrainte amplifiée Kt·|σ|max', sprintf('K_t|\\sigma|_{max}=%s\\times%s', n(F.Kt.Value), n(max(abs([s1 s2])))), F.Kt.Value * max(abs([s1 s2])), bd.sigmaMaxKt / 1e6, 'MPa')
                hc('Contrainte admissible', sprintf('\\sigma_{adm}=\\frac{R_e}{s}=\\frac{%s}{%s}', n(F.Re.Value), n(F.s.Value)), F.Re.Value / F.s.Value, bd.sigmaAdm / 1e6, 'MPa')}];
        end

        function rows = handFla(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            F = app.H.Fla;
            b = app.Results.buckling.analysis;
            E = F.E.Value * 1e3; Re = F.Re.Value; S = F.S.Value; Iz = F.Iz.Value; Iy = F.Iy.Value;
            L = F.L.Value * 1e3; s = F.s.Value;
            switch F.cond.Value
                case 'encastre-libre', c = 2;
                case 'articule-articule', c = 1;
                case 'encastre-articule', c = 1 / sqrt(2);
                case 'encastre-encastre', c = 0.5;
                otherwise, c = NaN;
            end
            Imin = min(Iz, Iy);
            rmin = sqrt(Imin / S);
            Lp = c * L;
            lam = Lp / rmin;
            lim = pi * sqrt(E / Re);
            PE = pi^2 * E * Imin / Lp^2;
            PC = Re * S;
            PR = PC / (1 + (lam / lim)^2);
            if lam < 20
                Pc = PC; reg = 'compression simple (λ < 20)';
            elseif lam < lim
                Pc = PR; reg = 'Rankine (20 ≤ λ < λlim)';
            else
                Pc = PE; reg = 'Euler (λ ≥ λlim)';
            end
            rows = {
                ValidationReport.grp('Flambage (E, Re en MPa ; S en mm² ; I en mm⁴ ; L en mm ; charges en kN)')
                hc('Inertie minimale', sprintf('I_{min}=\\min(I_z,I_y)=\\min(%s;%s)', n(Iz), n(Iy)), Imin, b.Imin * 1e12, 'mm⁴')
                hc('Rayon de giration minimal', sprintf('r_{min}=\\sqrt{I_{min}/S}=\\sqrt{%s/%s}', n(Imin), n(S)), rmin, b.rmin * 1e3, 'mm')
                hc('Longueur de flambement', sprintf('L''=c\\,L=%s\\times%s', n(c), n(L)), Lp * 1e-3, b.Lp, 'm')
                hc('Élancement', sprintf('\\lambda=\\frac{L''}{r_{min}}=\\frac{%s}{%s}', n(Lp), n(rmin)), lam, b.lambda, '')
                hc('Élancement limite', sprintf('\\lambda_{lim}=\\pi\\sqrt{E/R_e}=\\pi\\sqrt{%s/%s}', n(E), n(Re)), lim, b.lambdaLim, '')
                hc('Charge d''Euler', sprintf('P_E=\\frac{\\pi^2E\\,I_{min}}{L''^2}=\\frac{\\pi^2\\times%s\\times%s}{%s^2}', n(E), n(Imin), n(Lp)), PE / 1e3, b.PE / 1e3, 'kN')
                hc('Charge de compression simple', sprintf('P_C=R_e\\,S=%s\\times%s', n(Re), n(S)), PC / 1e3, b.PC / 1e3, 'kN')
                hc('Charge de Rankine', sprintf('P_R=\\frac{R_eS}{1+(\\lambda/\\lambda_{lim})^2}=\\frac{%s}{1+(%s/%s)^2}', n(PC), n(lam), n(lim)), PR / 1e3, b.PR / 1e3, 'kN')
                ValidationReport.grp(['Régime retenu par l''arbre de décision : ' reg])
                hc('Charge critique retenue', sprintf('P_{crit}=%s\\,\\mathrm{kN}', n(Pc / 1e3)), Pc / 1e3, b.Pcrit / 1e3, 'kN')
                hc('Charge admissible', sprintf('P_{adm}=\\frac{P_{crit}}{s}=\\frac{%s}{%s}', n(Pc / 1e3), n(s)), Pc / s / 1e3, b.Padm / 1e3, 'kN')};
        end

        function rows = handTen(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            T = app.H.Ten;
            r = app.Results.tensor;
            sg = double(T.sig.Data);
            sg = (sg + sg.') / 2;
            ev = sort(eig(sg), 'descend');
            I1 = trace(sg);
            I2 = (trace(sg)^2 - trace(sg^2)) / 2;
            I3 = det(sg);
            pr = r.principal;
            Re = T.Re.Value; s = T.s.Value;
            tre = ev(1) - ev(3);
            vm = sqrt(0.5 * ((ev(1) - ev(2))^2 + (ev(2) - ev(3))^2 + (ev(1) - ev(3))^2));
            fa = r.facet;
            nv = fa.n(:);
            Cn = sg * nv;
            sn = dot(Cn, nv);
            tn = norm(Cn - sn * nv);   % même définition que le solveur ; √(|C|² − σn²) donne du bruit près de 0
            rows = {
                ValidationReport.grp('Invariants et contraintes principales (MPa)')
                hc('Premier invariant', sprintf('I_1=\\mathrm{tr}\\,\\sigma=%s+%s+%s', n(sg(1, 1)), n(sg(2, 2)), n(sg(3, 3))), I1, pr.I1 / 1e6, 'MPa')
                hc('Deuxième invariant', sprintf('I_2=\\tfrac12[(\\mathrm{tr}\\,\\sigma)^2-\\mathrm{tr}(\\sigma^2)]'), I2, pr.I2 / 1e12, 'MPa²')
                hc('Troisième invariant', sprintf('I_3=\\det\\sigma'), I3, pr.I3 / 1e18, 'MPa³')
                hc('Contrainte principale σI', sprintf('\\sigma_I=\\max\\ \\mathrm{eig}(\\sigma)'), ev(1), pr.sigmaI / 1e6, 'MPa')
                hc('Contrainte principale σII', sprintf('\\sigma_{II}'), ev(2), pr.sigmaII / 1e6, 'MPa')
                hc('Contrainte principale σIII', sprintf('\\sigma_{III}=\\min\\ \\mathrm{eig}(\\sigma)'), ev(3), pr.sigmaIII / 1e6, 'MPa')
                ValidationReport.grp('Critères de résistance')
                hc('Tresca', sprintf('\\sigma_I-\\sigma_{III}=%s-(%s)', n(ev(1)), n(ev(3))), tre, r.criteria.sigmaEqTresca / 1e6, 'MPa')
                hc('Von Mises', sprintf('\\sigma_{VM}=\\sqrt{\\tfrac12[(\\sigma_I-\\sigma_{II})^2+(\\sigma_{II}-\\sigma_{III})^2+(\\sigma_I-\\sigma_{III})^2]}'), vm, r.criteria.sigmaEqVM / 1e6, 'MPa')
                hc('Contrainte admissible', sprintf('\\frac{R_e}{s}=\\frac{%s}{%s}', n(Re), n(s)), Re / s, r.criteria.sigmaAdm / 1e6, 'MPa')
                ValidationReport.grp('Facette de normale n')
                hc('Contrainte normale', sprintf('\\sigma_n=\\vec n^T[\\sigma]\\vec n'), sn, fa.sigmaN / 1e6, 'MPa')
                hc('Contrainte tangentielle', sprintf('\\tau=\\sqrt{|\\vec C|^2-\\sigma_n^2}'), tn, fa.tauNorm / 1e6, 'MPa')};
        end

        function rows = handHoo(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            K = app.H.Hoo;
            W = K.W;
            R = app.Results.hooke;
            E = K.E.Value * 1e3; nu = K.nu.Value; G = E / (2 * (1 + nu));
            al = K.alpha.Value * 1e-6; dT = K.dT.Value;
            sx = K.sxx.Value; sy = K.syy.Value; sz = K.szz.Value; syz = K.syz.Value; sxz = K.sxz.Value; sxy = K.sxy.Value;
            D = W.Tables.Res.Data;
            if istable(D)
                v = D{:, 2};
            else
                v = cell2mat(D(:, 2));
            end
            rows = {};
            switch K.mode.Value
                case 'iso3D'
                    exx = (sx - nu * (sy + sz)) / E + al * dT;
                    eyy = (sy - nu * (sx + sz)) / E + al * dT;
                    ezz = (sz - nu * (sx + sy)) / E + al * dT;
                    rows = {
                        ValidationReport.grp('Hooke isotrope 3D (contraintes en MPa, E en MPa) ; déformations en µdéf')
                        hc('εxx', sprintf('\\varepsilon_{xx}=\\frac{\\sigma_{xx}-\\nu(\\sigma_{yy}+\\sigma_{zz})}{E}+\\alpha\\Delta T=\\frac{%s-%s(%s+%s)}{%s}', n(sx), n(nu), n(sy), n(sz), n(E)), exx * 1e6, v(1), 'µdéf')
                        hc('εyy', sprintf('\\varepsilon_{yy}=\\frac{\\sigma_{yy}-\\nu(\\sigma_{xx}+\\sigma_{zz})}{E}+\\alpha\\Delta T'), eyy * 1e6, v(2), 'µdéf')
                        hc('εzz', sprintf('\\varepsilon_{zz}=\\frac{\\sigma_{zz}-\\nu(\\sigma_{xx}+\\sigma_{yy})}{E}+\\alpha\\Delta T'), ezz * 1e6, v(3), 'µdéf')
                        hc('γyz', sprintf('\\gamma_{yz}=\\frac{\\tau_{yz}}{G}=\\frac{%s}{%s}', n(syz), n(G)), syz / G * 1e6, v(4), 'µdéf')
                        hc('γxz', sprintf('\\gamma_{xz}=\\frac{\\tau_{xz}}{G}'), sxz / G * 1e6, v(5), 'µdéf')
                        hc('γxy', sprintf('\\gamma_{xy}=\\frac{\\tau_{xy}}{G}=\\frac{%s}{%s}', n(sxy), n(G)), sxy / G * 1e6, v(6), 'µdéf')};
                case 'planeStress'
                    exx = (sx - nu * sy) / E;
                    eyy = (sy - nu * sx) / E;
                    ezz = -nu * (sx + sy) / E;
                    rows = {
                        ValidationReport.grp('Contraintes planes (σzz = τxz = τyz = 0) ; déformations en µdéf')
                        hc('εxx', sprintf('\\varepsilon_{xx}=\\frac{\\sigma_{xx}-\\nu\\sigma_{yy}}{E}=\\frac{%s-%s\\times%s}{%s}', n(sx), n(nu), n(sy), n(E)), exx * 1e6, v(1), 'µdéf')
                        hc('εyy', sprintf('\\varepsilon_{yy}=\\frac{\\sigma_{yy}-\\nu\\sigma_{xx}}{E}'), eyy * 1e6, v(2), 'µdéf')
                        hc('εzz', sprintf('\\varepsilon_{zz}=-\\frac{\\nu(\\sigma_{xx}+\\sigma_{yy})}{E}'), ezz * 1e6, v(3), 'µdéf')
                        hc('γxy', sprintf('\\gamma_{xy}=\\frac{\\tau_{xy}}{G}=\\frac{%s}{%s}', n(sxy), n(G)), sxy / G * 1e6, v(4), 'µdéf')};
                case 'planeStrain'
                    ex = K.exx.Value * 1e-6; ey = K.eyy.Value * 1e-6; gx = K.gxy.Value * 1e-6;
                    c = E / ((1 + nu) * (1 - 2 * nu));
                    sxx = c * ((1 - nu) * ex + nu * ey);
                    syy = c * ((1 - nu) * ey + nu * ex);
                    sxy2 = G * gx;
                    szz = nu * (sxx + syy);
                    rows = {
                        ValidationReport.grp('Déformations planes (εzz = γxz = γyz = 0) ; contraintes en MPa')
                        hc('σxx', sprintf('\\sigma_{xx}=\\frac{E}{(1+\\nu)(1-2\\nu)}[(1-\\nu)\\varepsilon_{xx}+\\nu\\varepsilon_{yy}]'), sxx, v(1), 'MPa')
                        hc('σyy', sprintf('\\sigma_{yy}=\\frac{E}{(1+\\nu)(1-2\\nu)}[(1-\\nu)\\varepsilon_{yy}+\\nu\\varepsilon_{xx}]'), syy, v(2), 'MPa')
                        hc('σxy', sprintf('\\tau_{xy}=G\\,\\gamma_{xy}=%s\\times%s', n(G), n(gx)), sxy2, v(3), 'MPa')
                        hc('σzz', sprintf('\\sigma_{zz}=\\nu(\\sigma_{xx}+\\sigma_{yy})'), szz, v(4), 'MPa')};
                case 'ortho'
                    E1 = K.E1.Value * 1e3; E2 = K.E2.Value * 1e3; E3 = K.E3.Value * 1e3;
                    n12 = K.nu12.Value; n13 = K.nu13.Value; n23 = K.nu23.Value;
                    G12 = K.G12.Value * 1e3; G13 = K.G13.Value * 1e3; G23 = K.G23.Value * 1e3;
                    n21 = n12 * E2 / E1; n31 = n13 * E3 / E1; n32 = n23 * E3 / E2;
                    e11 = sx / E1 - n21 * sy / E2 - n31 * sz / E3;
                    e22 = -n12 * sx / E1 + sy / E2 - n32 * sz / E3;
                    e33 = -n13 * sx / E1 - n23 * sy / E2 + sz / E3;
                    rows = {
                        ValidationReport.grp('Orthotrope : [S] symétrique, ν21 = ν12·E2/E1, ν31 = ν13·E3/E1, ν32 = ν23·E3/E2 ; déformations en µdéf')
                        hc('ε11', sprintf('\\varepsilon_{11}=\\frac{\\sigma_{11}}{E_1}-\\frac{\\nu_{21}\\sigma_{22}}{E_2}-\\frac{\\nu_{31}\\sigma_{33}}{E_3}'), e11 * 1e6, v(1), 'µdéf')
                        hc('ε22', sprintf('\\varepsilon_{22}=-\\frac{\\nu_{12}\\sigma_{11}}{E_1}+\\frac{\\sigma_{22}}{E_2}-\\frac{\\nu_{32}\\sigma_{33}}{E_3}'), e22 * 1e6, v(2), 'µdéf')
                        hc('ε33', sprintf('\\varepsilon_{33}=-\\frac{\\nu_{13}\\sigma_{11}}{E_1}-\\frac{\\nu_{23}\\sigma_{22}}{E_2}+\\frac{\\sigma_{33}}{E_3}'), e33 * 1e6, v(3), 'µdéf')
                        hc('γ23', sprintf('\\gamma_{23}=\\frac{\\tau_{23}}{G_{23}}'), syz / G23 * 1e6, v(4), 'µdéf')
                        hc('γ13', sprintf('\\gamma_{13}=\\frac{\\tau_{13}}{G_{13}}'), sxz / G13 * 1e6, v(5), 'µdéf')
                        hc('γ12', sprintf('\\gamma_{12}=\\frac{\\tau_{12}}{G_{12}}'), sxy / G12 * 1e6, v(6), 'µdéf')};
            end
            ex = R.exx; ey = R.eyy; exy = R.exy;
            cen = (ex + ey) / 2;
            rad = sqrt(((ex - ey) / 2)^2 + exy^2);
            rows = [rows; {
                ValidationReport.grp('Cercle de Mohr des déformations dans le plan (x, y), en µdéf')
                hc('Centre', sprintf('\\delta=\\frac{\\varepsilon_{xx}+\\varepsilon_{yy}}{2}'), cen * 1e6, (R.mohr.sigma1 + R.mohr.sigma2) / 2 * 1e6, 'µdéf')
                hc('Déformation principale ε1', sprintf('\\varepsilon_1=\\delta+\\rho,\\ \\rho=\\sqrt{\\left(\\frac{\\varepsilon_{xx}-\\varepsilon_{yy}}{2}\\right)^2+\\varepsilon_{xy}^2}'), (cen + rad) * 1e6, R.mohr.sigma1 * 1e6, 'µdéf')
                hc('Déformation principale ε2', sprintf('\\varepsilon_2=\\delta-\\rho'), (cen - rad) * 1e6, R.mohr.sigma2 * 1e6, 'µdéf')}];
        end

        function rows = handJau(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            J = app.H.Jau;
            R = app.Results.gauges;
            K = J.K.Value; eps = J.eps.Value * 1e-6; R0 = J.R0.Value; Vin = J.Vin.Value;
            e4 = [J.e1.Value J.e2.Value J.e3.Value J.e4.Value] * 1e-6;
            switch J.cfg.Value
                case 'quart', ev = [e4(1) 0 0 0]; fac = 1;
                case 'demi', ev = [e4(1) e4(2) 0 0]; fac = 2;
                otherwise, ev = e4; fac = 4;
            end
            Vout = Vin * K / 4 * (ev(1) - ev(2) + ev(3) - ev(4));
            Vm = J.Vout.Value * 1e-3;
            ebr = 4 * Vm / (K * Vin) / fac;
            ra = J.ra.Value * 1e-6; rb = J.rb.Value * 1e-6; rc = J.rc.Value * 1e-6;
            E = J.E.Value * 1e3; nu = J.nu.Value;
            if strcmp(J.rtype.Value, '60')
                exx = ra; eyy = (2 * (rb + rc) - ra) / 3; exy = (rb - rc) / sqrt(3);
                fr = sprintf('\\varepsilon_{xx}=\\varepsilon_0,\\ \\varepsilon_{yy}=\\frac{2(\\varepsilon_{60}+\\varepsilon_{120})-\\varepsilon_0}{3},\\ \\varepsilon_{xy}=\\frac{\\varepsilon_{60}-\\varepsilon_{120}}{\\sqrt3}');
            else
                exx = ra; eyy = rb; exy = rc - (ra + rb) / 2;
                fr = sprintf('\\varepsilon_{xx}=\\varepsilon_0,\\ \\varepsilon_{yy}=\\varepsilon_{90},\\ \\varepsilon_{xy}=\\varepsilon_{45}-\\frac{\\varepsilon_0+\\varepsilon_{90}}{2}');
            end
            cen = (exx + eyy) / 2;
            rad = sqrt(((exx - eyy) / 2)^2 + exy^2);
            sxx = E / (1 - nu^2) * (exx + nu * eyy);
            syy = E / (1 - nu^2) * (eyy + nu * exx);
            sxy = E / (1 + nu) * exy;
            cs = (sxx + syy) / 2;
            rs = sqrt(((sxx - syy) / 2)^2 + sxy^2);
            rows = {
                ValidationReport.grp('Jauge (loi de Bridgman)')
                hc('Variation relative de résistance', sprintf('\\frac{\\Delta R}{R}=K\\,\\varepsilon=%s\\times%s', n(K), n(eps)), K * eps, R.gauge.dRsurR, '')
                hc('Variation de résistance', sprintf('\\Delta R=R_0\\,K\\,\\varepsilon=%s\\times%s\\times%s', n(R0), n(K), n(eps)), R0 * K * eps, R.gauge.dR, 'Ω')
                ValidationReport.grp('Pont de Wheatstone')
                hc('Tension de sortie linéarisée', sprintf('V_{out}=\\frac{V_{in}K}{4}(\\varepsilon_1-\\varepsilon_2+\\varepsilon_3-\\varepsilon_4)=\\frac{%s\\times%s}{4}(\\ldots)', n(Vin), n(K)), Vout * 1e3, R.bridge.Vout * 1e3, 'mV')
                hc('Déformation déduite de Vout mesurée', sprintf('\\varepsilon=\\frac{4V_{out}}{K\\,V_{in}}\\Big/\\text{facteur de pont}=\\frac{4\\times%s}{%s\\times%s}\\Big/%d', n(Vm), n(K), n(Vin), fac), ebr * 1e6, R.bridgeStrain * 1e6, 'µdéf')
                ValidationReport.grp('Rosette (déformations en µdéf, contraintes en MPa)')
                hc('Déformation εxx', fr, exx * 1e6, R.rosette.exx * 1e6, 'µdéf')
                hc('Déformation εyy', '\varepsilon_{yy}', eyy * 1e6, R.rosette.eyy * 1e6, 'µdéf')
                hc('Déformation εxy', '\varepsilon_{xy}', exy * 1e6, R.rosette.exy * 1e6, 'µdéf')
                hc('Déformation principale εI', sprintf('\\varepsilon_I=\\delta+\\rho=%s+%s', n(cen * 1e6), n(rad * 1e6)), (cen + rad) * 1e6, R.rosette.epsI * 1e6, 'µdéf')
                hc('Déformation principale εII', sprintf('\\varepsilon_{II}=\\delta-\\rho'), (cen - rad) * 1e6, R.rosette.epsII * 1e6, 'µdéf')
                hc('Contrainte σxx (contraintes planes)', sprintf('\\sigma_{xx}=\\frac{E}{1-\\nu^2}(\\varepsilon_{xx}+\\nu\\varepsilon_{yy})=\\frac{%s}{1-%s^2}(\\ldots)', n(E), n(nu)), sxx, R.rosette.sxx / 1e6, 'MPa')
                hc('Contrainte σyy', sprintf('\\sigma_{yy}=\\frac{E}{1-\\nu^2}(\\varepsilon_{yy}+\\nu\\varepsilon_{xx})'), syy, R.rosette.syy / 1e6, 'MPa')
                hc('Contrainte σxy', sprintf('\\tau_{xy}=\\frac{E}{1+\\nu}\\varepsilon_{xy}'), sxy, R.rosette.sxy / 1e6, 'MPa')
                hc('Contrainte principale σI', sprintf('\\sigma_I=\\frac{\\sigma_{xx}+\\sigma_{yy}}{2}+\\sqrt{\\left(\\frac{\\sigma_{xx}-\\sigma_{yy}}{2}\\right)^2+\\tau_{xy}^2}'), (cs + rs), R.rosette.sigmaI / 1e6, 'MPa')};
        end

        function rows = handTruss(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            R = app.Results.truss;
            tr = R.truss;
            ts = R.tsol;
            X = tr.nodes;
            B = tr.bars;
            m = size(B, 1);
            dim = size(X, 2);
            E = tr.E(:) .* ones(m, 1);
            S = tr.S(:) .* ones(m, 1);
            Lh = zeros(m, 1);
            U = zeros(m, dim);
            for k = 1:m
                dv = X(B(k, 2), :) - X(B(k, 1), :);
                Lh(k) = norm(dv);
                U(k, :) = dv / Lh(k);
            end
            sigH = ts.N(:) ./ S;
            dLH = ts.N(:) .* Lh ./ (E .* S);
            % compatibilité : allongement déduit des déplacements nodaux
            dLc = zeros(m, 1);
            for k = 1:m
                dLc(k) = U(k, :) * (ts.displacements(B(k, 2), :) - ts.displacements(B(k, 1), :)).';
            end
            % équilibre nodal : Σ N u + F + R = 0
            nn = size(X, 1);
            res = tr.loads + ts.reactions;
            for k = 1:m
                res(B(k, 1), :) = res(B(k, 1), :) + ts.N(k) * U(k, :);
                res(B(k, 2), :) = res(B(k, 2), :) - ts.N(k) * U(k, :);
            end
            fscale = max([1; abs(tr.loads(:)); abs(ts.reactions(:))]);
            rows = {
                ValidationReport.grp('Équilibre et compatibilité (vérifiés indépendamment du solveur)')
                hc('Résidu d''équilibre de tous les nœuds (N)', sprintf('\\max_i\\left\\|\\sum_j N_{ij}\\vec u_{ij}+\\vec F_i+\\vec R_i\\right\\|\\ \\text{(attendu 0)}'), max(vecnorm(res, 2, 2)), 0, 'N', 1e-6 * fscale)
                hc('Somme des forces extérieures + réactions (N)', sprintf('\\left\\|\\sum_i(\\vec F_i+\\vec R_i)\\right\\|\\ \\text{(attendu 0)}'), norm(sum(tr.loads + ts.reactions, 1)), 0, 'N', 1e-6 * fscale)
                hc('Compatibilité : allongement des barres (max d''écart)', sprintf('\\Delta L_{barre}=\\vec u_{ij}\\cdot(\\vec u_j-\\vec u_i)\\ \\text{contre}\\ \\frac{N\\,L}{E\\,S}'), max(abs(dLc - dLH)) * 1e3, 0, 'mm', 1e-6 * max(1e-3, max(abs(dLH)) * 1e3))
                hc('Longueurs des barres (écart max)', sprintf('L=\\sqrt{(x_j-x_i)^2+(y_j-y_i)^2}'), max(abs(Lh - ts.L0(:))), 0, 'm', 1e-9)
                hc('Contraintes σ = N/S (écart max)', sprintf('\\sigma=\\frac{N}{S}'), max(abs(sigH - ts.sigma(:))) / 1e6, 0, 'MPa', 1e-6 * max(1, max(abs(sigH)) / 1e6))
                hc('Hyperstatisme', sprintf('h=m+r-d\\,n=%d+%d-%d\\times%d', m, nnz(tr.supports), dim, nn), m + nnz(tr.supports) - dim * nn, ts.h, '')};
            % tableau par barre : formule et valeurs
            rows{end + 1, 1} = ValidationReport.grp('Détail par barre : N (solveur), σ = N/S et ΔL = N·L/(E·S) recalculés');
            for k = 1:m
                nm = sprintf('Barre %d (nœuds %d–%d)', k, B(k, 1), B(k, 2));
                rows{end + 1, 1} = hc([nm ' : σ'], sprintf('\\sigma=\\frac{%s\\,\\mathrm{N}}{%s\\,\\mathrm{m^2}}', n(ts.N(k)), n(S(k))), sigH(k) / 1e6, ts.sigma(k) / 1e6, 'MPa'); %#ok<AGROW>
                rows{end + 1, 1} = hc([nm ' : ΔL'], sprintf('\\Delta L=\\frac{N\\,L}{E\\,S}=\\frac{%s\\times%s}{%s\\times%s}', n(ts.N(k)), n(Lh(k)), n(E(k)), n(S(k))), dLH(k) * 1e3, ts.dL(k) * 1e3, 'mm'); %#ok<AGROW>
            end
        end

        function rows = handBeam(app)
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            B = app.Results.beam;
            sol = B.sol;
            mo = sol.model;
            L = mo.L;
            rea = sol.reactions;
            pl = mo.pointLoads;
            pm = mo.pointMoments;
            dl = mo.distLoads;
            Fx = []; if ~isempty(pl), Fx = [pl.Fx]; end
            rRx = [rea.Rx];
            distX = struct('a', {}, 'b', {}, 'c', {});
            for k = 1:numel(dl)
                if strcmp(char(dl(k).dir), 'x')
                    distX(end + 1) = struct('a', dl(k).a, 'b', dl(k).b, 'c', dl(k).coeffs); %#ok<AGROW>
                end
            end
            qint = @(d, f) integral(@(x) arrayfun(@(xx) polyval(d.c, xx - d.a) * f(xx), x), d.a, d.b);
            sumFx = sum(Fx) + sum(rRx) + sum(arrayfun(@(d) qint(d, @(x) 1), distX));
            rows = {
                ValidationReport.grp('Équilibre axial, recalculé à partir du modèle et des réactions du solveur')
                hc('Équilibre des forces en x (N)', sprintf('\\sum F_x=%s\\ \\text{(attendu 0)}', n(sumFx)), sumFx, 0, 'N', 1e-6 * max([1, abs(Fx), abs(rRx)]) * max(1, L))};
            % --- plan (x, y) toujours ; plan (x, z) seulement s'il y a des charges ou des réactions en z
            rows = [rows; ValidationReport.beamPlaneRows(sol, 'y')];
            hasZ = (~isempty(pl) && any([pl.Fz] ~= 0)) || (~isempty(pm) && any([pm.My] ~= 0)) || ...
                (~isempty(dl) && any(strcmp({dl.dir}, 'z'))) || any([rea.Rz] ~= 0) || any([rea.My] ~= 0);
            if hasZ
                rows = [rows; ValidationReport.beamPlaneRows(sol, 'z')];
            end
            rows = [rows; ValidationReport.handImposed(B)];
            % --- contrainte au point le plus sollicité
            chk = B.check;
            bd = chk.bend;
            P = app.H.Beam;
            S = P.S.Value; Iz = P.Iz.Value; Iy = P.Iy.Value;
            secT = '';
            if app.BeamUsesSection && ~isempty(app.BeamSection)
                secT = app.BeamSection.sec.type;
            end
            if P.Iyz.Value ~= 0
                rows{end + 1, 1} = ValidationReport.grp(sprintf(['Contrainte au point le plus sollicité : Iyz ≠ 0, flexion déviée : NON recalculée à la main ' ...
                    '(la loi de Navier à axes principaux ne s''applique pas). Valeur du solveur : |σ|max = %.6g MPa'], bd.sigmaMaxAbs / 1e6));
            elseif any(strcmp(secT, {'T', 'U', 'L', 'composite'}))
                rows{end + 1, 1} = ValidationReport.grp(sprintf(['Contrainte au point le plus sollicité : section dissymétrique (%s), contour exact utilisé par le solveur : ' ...
                    'NON recalculée à la main. Valeur du solveur : |σ|max = %.6g MPa'], secT, bd.sigmaMaxAbs / 1e6));
            else
                % maximum de |σ| de la loi de Navier, trouvé sans le solveur : sur les 4 coins des fibres extrêmes
                % saisies, ou sur le cercle (module du moment résultant) pour un disque ou une couronne
                if any(strcmp(secT, {'disque', 'couronne'}))
                    Rr = app.BeamSection.sec.D / 2 * 1e3;
                    sh = abs(chk.N) / S + hypot(chk.Mfz, chk.Mfy) * 1e3 * Rr / Iz;
                    ftxt = sprintf('|\\sigma|_{max}=\\frac{|N|}{S}+\\frac{\\sqrt{M_{fz}^2+M_{fy}^2}\\,R}{I}=\\frac{%s}{%s}+\\frac{%s\\times%s}{%s}', ...
                        n(abs(chk.N)), n(S), n(hypot(chk.Mfz, chk.Mfy) * 1e3), n(Rr), n(Iz));
                else
                    vy = P.vy.Value; vz = P.vz.Value;
                    [Yc, Zc] = ndgrid([-vy vy], [-vz vz]);
                    sh = max(abs(chk.N / S - chk.Mfz * 1e3 * Yc(:) / Iz + chk.Mfy * 1e3 * Zc(:) / Iy));
                    ftxt = sprintf('|\\sigma|_{max}=\\max_{\\pm v_y,\\pm v_z}\\left|\\frac{%s}{%s}-\\frac{%s\\,y}{%s}+\\frac{%s\\,z}{%s}\\right|', ...
                        n(chk.N), n(S), n(chk.Mfz * 1e3), n(Iz), n(chk.Mfy * 1e3), n(Iy));
                end
                rows = [rows; {
                    ValidationReport.grp('Contrainte maximale au point le plus sollicité (N en N, M en N·mm)')
                    hc('|σ| max (loi de Navier, sans le solveur)', ftxt, sh, bd.sigmaMaxAbs / 1e6, 'MPa')}];
            end
            cmp = B.defl.comparison;
            bendOnly = ~contains(cmp.Methode, 'tranchant');   % la ligne « flexion + tranchant » s'écarte de l'effet de l'effort tranchant
            rows{end + 1, 1} = ValidationReport.grp(sprintf('Flèche (flexion seule) : écart maximal entre les méthodes = %.3g %% (la ligne « flexion + tranchant » de Castigliano est à part ; voir §4)', max(abs(cmp.Ecart_pct(bendOnly)))));
        end

        function t = yesNoWeb(w)
            % Texte du contrôle du voilement de l'âme.
            if w.needed
                t = sprintf('hw/tw = %.1f > %.1f : VEd/Vb,Rd = %.3f', w.hwTw, w.limit, w.ratio);
            else
                t = sprintf('sans objet : hw/tw = %.1f ≤ %.1f', w.hwTw, w.limit);
            end
        end

        function rows = handImposed(B)
            %HANDIMPOSED Contrôles des appuis élastiques, tassements et rotules : conditions que le résultat doit vérifier,
            %   lues sur la solution (flèche aux appuis, moment aux rotules), sans refaire le calcul des réactions.
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            mo = B.sol.model;
            sup = mo.supports;
            rows = cell(0, 1);
            hasSup = ~isempty(sup) && (any([sup.spring] > 0) || any(abs([sup.dx sup.dy sup.dz]) > 0));
            if hasSup
                rows{end + 1, 1} = ValidationReport.grp('Appuis élastiques et tassements : déplacement de chaque appui = tassement − R/k (flèche de la déformée, plan affiché)');
                if strcmp(B.defl.plane, 'xy')
                    rf = 'Ry'; df = 'dy';
                else
                    rf = 'Rz'; df = 'dz';
                end
                for i = 1:numel(sup)
                    d = sup(i).(df);
                    if sup(i).spring > 0
                        d = d - B.sol.reactions(i).(rf) / sup(i).spring;
                    end
                    v = BeamAndTrussSolver.ppEval(B.defl.integration.vPP, sup(i).pos, 'left');
                    rows{end + 1, 1} = hc(sprintf('Déplacement de l''appui %s (mm)', sup(i).name), ...
                        sprintf('v(s_%d)=d-\\frac{R}{k}=%s-\\frac{%s}{%s}', i, n(sup(i).(df) * 1e3), n(B.sol.reactions(i).(rf)), n(max(sup(i).spring, eps))), ...
                        d * 1e3, v * 1e3, 'mm', 1e-6 * max(1, abs(d * 1e3))); %#ok<AGROW>
                end
            end
            hg = mo.hinges;
            if ~isempty(hg)
                rows{end + 1, 1} = ValidationReport.grp('Rotules intermédiaires : moment de flexion nul');
                mscale = max(abs(BeamAndTrussSolver.ppEval(B.sol.Mfz, linspace(0, mo.L, 41))));
                for i = 1:numel(hg)
                    m = BeamAndTrussSolver.ppEval(B.sol.Mfz, hg(i).pos, 'left');
                    rows{end + 1, 1} = hc(sprintf('M_fz à la rotule %s (N·m)', hg(i).name), ...
                        sprintf('M_{fz}(%s)=%s\\ \\text{(attendu 0)}', n(hg(i).pos), n(m)), 0, m, 'N·m', 1e-6 * max(1, mscale)); %#ok<AGROW>
                end
            end
        end

        function rows = handExtras(app)
            %HANDEXTRAS Contrôles des résultats ajoutés à l'onglet Poutres (présents seulement s'ils ont été calculés) :
            %   combinaisons, Eurocode 3, fatigue, profilé le plus léger.
            rows = {};
            if isfield(app.Results, 'combos') && ~isempty(app.Results.combos)
                rows = [rows; ValidationReport.safeRows(@() ValidationReport.handCombos(app), 'Combinaisons')];
            end
            if isfield(app.Results, 'ec3') && ~isempty(app.Results.ec3)
                rows = [rows; ValidationReport.safeRows(@() ValidationReport.handEC3(app), 'Eurocode 3')];
            end
            if isfield(app.Results, 'fatigue') && ~isempty(app.Results.fatigue)
                rows = [rows; ValidationReport.safeRows(@() ValidationReport.handFatigue(app), 'Fatigue')];
            end
            if isfield(app.Results, 'profiles') && ~isempty(app.Results.profiles)
                rows = [rows; ValidationReport.safeRows(@() ValidationReport.handProfiles(app), 'Profilé le plus léger')];
            end
        end

        function rows = safeRows(fn, name)
            try
                rows = fn();
            catch err
                rows = {ValidationReport.grp(sprintf('%s : contrôle impossible (%s)', name, err.message))};
            end
        end

        function errs = refreshExtras(app, key)
            %REFRESHEXTRAS Recalcule, avant d'écrire le dossier, les résultats « extras » déjà calculés dans la session
            %   (sinon le dossier afficherait des tableaux périmés par rapport à la saisie actuelle).
            errs = {};
            if ~strcmp(key, 'Beam')
                return
            end
            B = app.H.Beam;
            steps = {'combos', @() app.computeCombinations(), 'computeCombinations'
                'ec3', @() app.checkEurocode(), 'checkEurocode'
                'fatigue', @() app.checkFatigue(), 'checkFatigue'
                'profiles', @() app.findLightestProfile(B.pfam.Value, B.pdef.Value), 'findLightestProfile'};
            for k = 1:size(steps, 1)
                % le balayage des profilés (le plus long) n'est refait que si la saisie a changé depuis le dernier balayage
                fresh = strcmp(steps{k, 1}, 'profiles') && isfield(app.Results, 'profilesInputs') ...
                    && isequaln(app.Results.profilesInputs, {app.captureInputs('Beam'), app.BeamSection, app.BeamUsesSection});
                if isfield(app.Results, steps{k, 1}) && ~isempty(app.Results.(steps{k, 1})) && ~fresh
                    try
                        steps{k, 2}();
                    catch err
                        errs{end + 1} = sprintf('%s : %s', steps{k, 3}, err.message); %#ok<AGROW>
                    end
                end
            end
        end

        function rows = handCombos(app)
            %HANDCOMBOS Combinaisons : équilibre et torseur de chaque combinaison, superposition des cas, tableau = recalcul.
            %   Ces contrôles font appel au solveur de poutre (ils vérifient la cohérence des combinaisons, pas le solveur).
            hc = @ValidationReport.hc;
            B = app.H.Beam;
            c = B.combo.Data;
            T = app.Results.combos;
            caseNames = {'G', 'Q', 'W', 'S'};
            used = false(1, 4);
            for tb = {B.pl.Data, B.pm.Data, B.dl.Data}
                d = tb{1};
                col = size(d, 2);
                for i = 1:size(d, 1)
                    k = find(strcmp(caseNames, char(string(d{i, col}))), 1);
                    if ~isempty(k), used(k) = true; end
                end
            end
            if B.selfw.Value, used(1) = true; end
            s = linspace(0, B.L.Value, 21);
            sols = struct();
            for k = find(used)
                fac = struct('G', 0, 'Q', 0, 'W', 0, 'S', 0);
                fac.(caseNames{k}) = 1;
                sols.(caseNames{k}) = BeamAndTrussSolver.solveBeam(app.readBeamModel(fac));
            end
            rows = {ValidationReport.grp(['Combinaisons : chaque ligne est résolue séparément, puis comparée (équilibre, superposition des cas, tableau). ' ...
                'Ces contrôles utilisent le solveur : ils vérifient la cohérence des combinaisons.'])};
            gov = struct('Mfz', {{'', -Inf}}, 'Ty', {{'', -Inf}});
            for i = 1:size(c, 1)
                g = cellfun(@(j) ValidationReport.cellNumber(c{i, j}), {2, 3, 4, 5});
                fac = struct('G', g(1), 'Q', g(2), 'W', g(3), 'S', g(4));
                sol = BeamAndTrussSolver.solveBeam(app.readBeamModel(fac));
                nm = char(string(c{i, 1}));
                rows{end + 1, 1} = ValidationReport.grp(sprintf('Combinaison « %s » : γG = %g, γQ = %g, γW = %g, γS = %g', nm, g)); %#ok<AGROW>
                rows = [rows; ValidationReport.beamPlaneRows(sol, 'y')]; %#ok<AGROW>
                % superposition : Mfz(combinaison) = somme des γ·Mfz(cas), en 21 abscisses
                sup = zeros(size(s));
                for k = find(used)
                    sup = sup + g(k) * BeamAndTrussSolver.ppEval(sols.(caseNames{k}).Mfz, s);
                end
                direct = BeamAndTrussSolver.ppEval(sol.Mfz, s);
                rows{end + 1, 1} = hc('Moment fléchissant : superposition des cas (somme sur 21 abscisses de |Mfz|)', ...
                    '\sum_s \left|\sum_c \gamma_c\,M_{fz,c}(s)\right|', sum(abs(sup)) / 1e3, sum(abs(direct)) / 1e3, 'kN·m'); %#ok<AGROW>
                e = sol.extrema;
                rows{end + 1, 1} = hc('Tableau Combinaisons : Mfz max = recalcul de la combinaison', 'M_{fz,max}', ...
                    e.Mfz.max / 1e3, T.("Mfz max (kN·m)")(i), 'kN·m'); %#ok<AGROW>
                rows{end + 1, 1} = hc('Tableau Combinaisons : Mfz min = recalcul de la combinaison', 'M_{fz,min}', ...
                    e.Mfz.min / 1e3, T.("Mfz min (kN·m)")(i), 'kN·m'); %#ok<AGROW>
                rows{end + 1, 1} = hc('Tableau Combinaisons : Ty max = recalcul de la combinaison', 'T_{y,max}', ...
                    e.Ty.max / 1e3, T.("Ty max (kN)")(i), 'kN'); %#ok<AGROW>
                if e.Mfz.max > gov.Mfz{2}, gov.Mfz = {nm, e.Mfz.max}; end
                if e.Ty.max > gov.Ty{2}, gov.Ty = {nm, e.Ty.max}; end
            end
            n = height(T);
            rows{end + 1, 1} = hc('Enveloppe : Mfz max = plus grand Mfz max des combinaisons', 'M_{fz,max}^{env}=\max_i M_{fz,max,i}', ...
                max(T.("Mfz max (kN·m)")(1:n - 1)), T.("Mfz max (kN·m)")(n), 'kN·m'); %#ok<AGROW>
            rows{end + 1, 1} = ValidationReport.grp(sprintf(['Combinaison dimensionnante : « %s » pour Mfz max, « %s » pour Ty max. ' ...
                'L''enveloppe associe des maxima qui ne sont pas simultanés : elle est prudente.'], gov.Mfz{1}, gov.Ty{1})); %#ok<AGROW>
        end

        function rows = handEC3(app)
            %HANDEC3 Eurocode 3 : recalcul avec d'autres écritures (Wpl = 2·Sy, formules explicites) sans appeler DesignChecks.
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            B = app.H.Beam;
            r = app.Results.ec3;
            sec = app.BeamSection.sec;
            rolled = strcmp(sec.type, 'profile');
            if rolled
                h = sec.h; b = sec.b; tw = sec.a; tf = sec.e; rr = 0;
                if isfield(sec, 'r') && isfinite(sec.r), rr = sec.r; end
            else
                h = sec.h; b = sec.b; tw = sec.tw; tf = sec.tf; rr = 0;
            end
            fy = B.Re.Value * 1e6; g0 = B.gM0.Value; g1 = B.gM1.Value;
            E = B.E.Value * 1e9; G = B.G.Value * 1e9;
            A = B.S.Value * 1e-6; Iy = B.Iz.Value * 1e-12; Iw_ = B.Iy.Value * 1e-12; It = B.Ix.Value * 1e-12;
            Lcr = B.Lcr.Value;
            if Lcr <= 0, Lcr = B.L.Value; end
            LcrF = B.LcrF.Value;
            if LcrF <= 0, LcrF = B.L.Value; end
            C1 = B.C1.Value;
            MEd = r.MEd; VEd = r.VEd;
            Npl = A * fy / g0;
            NEd = r.axial.n * Npl;
            rows = {ValidationReport.grp('Eurocode 3 : classes, résistances, déversement, N + M (EN 1993-1-1) ; efforts de calcul pris dans les résultats de la poutre')};
            % --- classes (tableau 5.2)
            eps = sqrt(235e6 / fy);
            hw = h - 2 * tf;
            cf = (b - tw - 2 * rr) / 2;
            cw = hw - 2 * rr;
            % âme (tableau 5.2, feuille 2) : ψ et α aux bords de l'âme, compression seule (r.Ncomp) avec la flexion MEd
            sCw = r.Ncomp / A;
            sMw = abs(MEd) * (hw / 2) / Iy;
            psiW = -1;
            if sCw + sMw > 0, psiW = (sCw - sMw) / (sCw + sMw); end
            alW = min(1, 1 / (1 - psiW));
            if alW > 0.5, limW = [396 / (13 * alW - 1), 456 / (13 * alW - 1)]; else, limW = [36 / alW, 41.5 / alW]; end
            if psiW > -1, limW(3) = 42 / (0.67 + 0.33 * psiW); else, limW(3) = 62 * (1 - psiW) * sqrt(-psiW); end
            kf = find(cf / tf <= [9 10 14] * eps, 1); if isempty(kf), kf = 4; end
            kw = find(cw / tw <= limW * eps, 1); if isempty(kw), kw = 4; end
            cls = max(kf, kw);
            rows = [rows; {
                hc('ε = √(235/fy)', sprintf('\\varepsilon=\\sqrt{235/%s}', n(fy / 1e6)), eps, r.class.eps, '')
                hc('Aile : c/tf', sprintf('c/t_f=\\frac{(b-t_w-2r)/2}{t_f}=\\frac{%s}{%s}', n(cf * 1e3), n(tf * 1e3)), cf / tf, r.class.ratioFlange, '')
                hc('Âme : c/tw', sprintf('c/t_w=\\frac{h-2t_f-2r}{t_w}=\\frac{%s}{%s}', n(cw * 1e3), n(tw * 1e3)), cw / tw, r.class.ratioWeb, '')
                hc('Classe de la section (tableau 5.2 : aile 9ε, 10ε, 14ε ; âme selon ψ et α)', sprintf('\\text{classe}=\\max(%d,%d)', kf, kw), cls, r.class.class, '', 0)}];
            if cls > 3
                return
            end
            % --- flexion et tranchant (6.2.5, 6.2.6, 6.2.8)
            hfil = (1 - pi / 4) * rr^2;
            Sy = b * tf * (h - tf) / 2 + tw * (hw / 2) * (hw / 4) + 2 * hfil * (hw / 2 - 0.2234 * rr);
            Wpl = 2 * Sy;
            Wel = Iy / (h / 2);
            W = Wpl;
            if cls == 3, W = Wel; end
            Mc = W * fy / g0;
            eta = 1.2; if fy > 460e6, eta = 1.0; end
            Av = max(A - 2 * b * tf + (tw + 2 * rr) * tf, eta * hw * tw);
            Vpl = Av * (fy / sqrt(3)) / g0;
            red = abs(VEd) > 0.5 * Vpl;
            MRd = Mc;
            if red
                rho = (2 * abs(VEd) / Vpl - 1)^2;
                MRd = max(0, min(Mc, (W - rho * (hw * tw)^2 / (4 * tw)) * fy / g0));
            end
            rows = [rows; {
                hc('Wpl = 2·Sy (moment statique d''une demi-section)', sprintf('W_{pl}=2\\left[b t_f\\frac{h-t_f}{2}+t_w\\frac{h_w}{2}\\frac{h_w}{4}+2A_f(\\tfrac{h_w}{2}-0{,}2234r)\\right]=%s', n(Wpl * 1e6)), Wpl * 1e6, r.Wpl * 1e6, 'cm³')
                hc('Wel = Iy/(h/2)', sprintf('W_{el}=\\frac{I_y}{h/2}=\\frac{%s}{%s}', n(Iy * 1e8), n(h * 50)), Wel * 1e6, r.Wel * 1e6, 'cm³')
                hc('Mc,Rd = W·fy/γM0 (§6.2.5, éq. 6.13/6.14)', sprintf('M_{c,Rd}=\\frac{%s\\times%s}{%s}', n(W * 1e6), n(fy / 1e6), n(g0)), Mc / 1e3, r.Mc / 1e3, 'kN·m')
                hc('Av (§6.2.6(3))', sprintf('A_v=\\max(A-2bt_f+(t_w+2r)t_f,\\ \\eta h_w t_w)=%s', n(Av * 1e6)), Av * 1e6, r.Av * 1e6, 'mm²')
                hc('Vpl,Rd = Av·(fy/√3)/γM0 (§6.2.6(2))', sprintf('V_{pl,Rd}=\\frac{%s\\,(%s/\\sqrt3)}{%s}', n(Av * 1e6), n(fy / 1e6), n(g0)), Vpl / 1e3, r.Vpl / 1e3, 'kN')
                hc('MRd après réduction par le tranchant (§6.2.8)', sprintf('V_{Ed}=%s\\ \\text{kN}\\ \\ \\text{; réduction : }%d', n(VEd / 1e3), red), MRd / 1e3, r.MRd / 1e3, 'kN·m')
                hc('MEd / MRd (éq. 6.12)', sprintf('\\frac{%s}{%s}', n(MEd / 1e3), n(MRd / 1e3)), MEd / MRd, r.ratioM, '')
                hc('VEd / Vpl,Rd (éq. 6.17)', sprintf('\\frac{%s}{%s}', n(VEd / 1e3), n(Vpl / 1e3)), VEd / Vpl, r.ratioV, '')}];
            % --- déversement (6.3.2.3 ; Mcr : NCCI SN003)
            Iw = Iw_ * (h - tf)^2 / 4;
            Mcr = C1 * pi^2 * E * Iw_ / Lcr^2 * sqrt(Iw / Iw_ + Lcr^2 * G * It / (pi^2 * E * Iw_));
            lam = sqrt(W * fy / Mcr);
            tall = h / b > 2 + 1e-9;
            if rolled, cv = 'bc'; else, cv = 'cd'; end
            alt = [0.21 0.34 0.49 0.76];
            al = alt(cv(1 + tall) - 'a' + 1);
            Phi = 0.5 * (1 + al * (lam - 0.4) + 0.75 * lam^2);
            chi = min([1, 1 / lam^2, 1 / (Phi + sqrt(max(Phi^2 - 0.75 * lam^2, 0)))]);
            if lam <= 0.4, chi = 1; end
            Mb = chi * W * fy / g1;
            rows = [rows; {
                hc('Mcr (poutre à fourches, charge au centre de torsion)', sprintf('M_{cr}=C_1\\frac{\\pi^2EI_z}{L_{cr}^2}\\sqrt{\\frac{I_w}{I_z}+\\frac{L_{cr}^2GI_t}{\\pi^2EI_z}}\\ ;\\ C_1=%s,\\ L_{cr}=%s\\ \\text{m}', n(C1), n(Lcr)), Mcr / 1e3, r.ltb.Mcr / 1e3, 'kN·m')
                hc('λ̄LT = √(W·fy/Mcr)', sprintf('\\bar\\lambda_{LT}=\\sqrt{\\frac{%s\\times%s}{%s}}', n(W * 1e6), n(fy / 1e6), n(Mcr / 1e3)), lam, r.ltb.lambda, '')
                hc(sprintf('αLT (courbe %s, tableaux 6.5 puis 6.3)', cv(1 + tall)), sprintf('\\alpha_{LT}=%s', n(al)), al, r.ltb.alpha, '')
                hc('χLT (éq. 6.57, λ̄LT,0 = 0,4, β = 0,75)', sprintf('\\chi_{LT}=\\frac{1}{\\Phi_{LT}+\\sqrt{\\Phi_{LT}^2-0{,}75\\bar\\lambda_{LT}^2}},\\ \\Phi_{LT}=%s', n(Phi)), chi, r.ltb.chi, '')
                hc('Mb,Rd = χLT·W·fy/γM1 (éq. 6.55)', sprintf('M_{b,Rd}=%s\\times%s\\times%s/%s', n(chi), n(W * 1e6), n(fy / 1e6), n(g1)), Mb / 1e3, r.ltb.MbRd / 1e3, 'kN·m')
                hc('MEd / Mb,Rd (éq. 6.54)', sprintf('\\frac{%s}{%s}', n(MEd / 1e3), n(Mb / 1e3)), MEd / Mb, r.ltb.ratio, '')}];
            % --- flexion + effort normal (6.2.9)
            n_ = NEd / Npl;
            if cls <= 2
                a_ = min((A - 2 * b * tf) / A, 0.5);
                free = n_ <= 0.25 && NEd <= 0.5 * hw * tw * fy / g0;
                if free
                    MN = Mc;
                elseif n_ >= 1
                    MN = 0;
                else
                    MN = min(Mc, Mc * (1 - n_) / (1 - 0.5 * a_));
                end
                MN = min(MN, MRd);
                rows = [rows; {
                    hc('n = NEd/Npl,Rd', sprintf('n=\\frac{%s}{%s}', n(NEd / 1e3), n(Npl / 1e3)), n_, r.axial.n, '')
                    hc('MN,y,Rd (§6.2.9.1, éq. 6.36 ; sans réduction si 6.33 et 6.34)', sprintf('M_{N,y,Rd}=M_{pl,y,Rd}\\frac{1-n}{1-0{,}5a},\\ a=%s', n(a_)), MN / 1e3, r.axial.MNRd / 1e3, 'kN·m')}];
            else
                sig = NEd / A + MEd / Wel;
                rows = [rows; {
                    hc('σx,Ed = NEd/A + MEd/Wel (§6.2.9.2, éq. 6.42)', sprintf('\\sigma_{x,Ed}=\\frac{%s}{%s}+\\frac{%s}{%s}', n(NEd / 1e3), n(A * 1e6), n(MEd / 1e3), n(Wel * 1e6)), sig / 1e6, r.axial.sigma / 1e6, 'MPa')}];
            end
            % --- flambement par flexion (6.3.1), axe faible z-z
            if ~isempty(r.buck)
                Nc = r.buck.NEd;
                hb = h / b;
                if rolled
                    if hb > 1.2
                        if tf * 1e3 > 100, cz = 'd'; elseif tf * 1e3 > 40, cz = 'c'; else, cz = 'b'; end
                    else
                        if tf * 1e3 > 100, cz = 'd'; else, cz = 'c'; end
                    end
                else
                    if tf * 1e3 > 40, cz = 'd'; else, cz = 'c'; end
                end
                alt = [0.21 0.34 0.49 0.76];
                alz = alt(cz - 'a' + 1);
                Ncr = pi^2 * E * Iw_ / Lcr^2;
                lz = sqrt(A * fy / Ncr);
                Pz = 0.5 * (1 + alz * (lz - 0.2) + lz^2);
                chz = min(1, 1 / (Pz + sqrt(max(Pz^2 - lz^2, 0))));
                if lz <= 0.2 || Nc / Ncr <= 0.04, chz = 1; end
                rows = [rows; {
                    hc('Flambement z-z : Ncr = π²·E·Iz/Lcr²', sprintf('N_{cr}=\\frac{\\pi^2EI_z}{L_{cr}^2}=%s\\ \\text{kN}', n(Ncr / 1e3)), Ncr / 1e3, r.buck.axes(2).Ncr / 1e3, 'kN')
                    hc(sprintf('Flambement z-z : λ̄ (courbe %s, tableaux 6.2 et 6.1)', cz), sprintf('\\bar\\lambda=\\sqrt{\\frac{Af_y}{N_{cr}}}=%s', n(lz)), lz, r.buck.axes(2).lambda, '')
                    hc('Flambement z-z : χ (éq. 6.49)', sprintf('\\chi=\\frac{1}{\\Phi+\\sqrt{\\Phi^2-\\bar\\lambda^2}},\\ \\Phi=%s', n(Pz)), chz, r.buck.axes(2).chi, '')
                    hc('Flambement z-z : Nb,Rd = χ·A·fy/γM1 (éq. 6.47)', sprintf('N_{b,Rd}=%s\\times%s\\times%s/%s', n(chz), n(A * 1e6), n(fy / 1e6), n(g1)), chz * A * fy / g1 / 1e3, r.buck.axes(2).NbRd / 1e3, 'kN')}];
            end
            % --- interaction N + M (6.3.3, annexe B, tableau B.2) : refait avec le χ de l'axe fort recalculé ici
            if ~isempty(r.inter)
                hb = h / b;
                if rolled
                    if hb > 1.2
                        if tf * 1e3 > 100, cy = 'd'; elseif tf * 1e3 > 40, cy = 'b'; else, cy = 'a'; end
                    else
                        if tf * 1e3 > 100, cy = 'd'; else, cy = 'b'; end
                    end
                else
                    if tf * 1e3 > 40, cy = 'c'; else, cy = 'b'; end
                end
                aly = [0.21 0.34 0.49 0.76];
                aly = aly(cy - 'a' + 1);
                Ncry = pi^2 * E * Iy / LcrF^2;   % axe fort : longueur du plan fort, pas la longueur entre entretoises
                ly = sqrt(A * fy / Ncry);
                Py = 0.5 * (1 + aly * (ly - 0.2) + ly^2);
                chy = min(1, 1 / (Py + sqrt(max(Py^2 - ly^2, 0))));
                if ly <= 0.2 || Nc / Ncry <= 0.04, chy = 1; end
                nY_ = Nc / (chy * A * fy / g1);
                nZ_ = Nc / (chz * A * fy / g1);
                Cmy = B.Cmy.Value; CmL = B.CmLT.Value;
                if cls <= 2
                    kyy = min(Cmy * (1 + (ly - 0.2) * nY_), Cmy * (1 + 0.8 * nY_));
                    if lz >= 0.4
                        kzy = max(1 - 0.1 * lz * nZ_ / (CmL - 0.25), 1 - 0.1 * nZ_ / (CmL - 0.25));
                    else
                        kzy = min(0.6 + lz, 1 - 0.1 * lz * nZ_ / (CmL - 0.25));
                    end
                else
                    kyy = min(Cmy * (1 + 0.6 * ly * nY_), Cmy * (1 + 0.6 * nY_));
                    kzy = max(1 - 0.05 * lz * nZ_ / (CmL - 0.25), 1 - 0.05 * nZ_ / (CmL - 0.25));
                end
                dn = chi * W * fy / g1;
                rows = [rows; {
                    hc(sprintf('Flambement y-y : χy (courbe %s)', cy), sprintf('\\chi_y=\\frac{1}{\\Phi+\\sqrt{\\Phi^2-\\bar\\lambda_y^2}},\\ \\bar\\lambda_y=%s', n(ly)), chy, r.buck.axes(1).chi, '')
                    hc('kyy (annexe B, tableau B.2)', sprintf('k_{yy}=C_{my}\\left[1+(\\bar\\lambda_y-0{,}2)n_Y\\right]\\le C_{my}(1+0{,}8\\,n_Y)\\ ;\\ n_Y=%s', n(nY_)), kyy, r.inter.kyy, '')
                    hc('kzy (annexe B, tableau B.2)', sprintf('k_{zy}=1-\\frac{0{,}1\\bar\\lambda_z n_Z}{C_{mLT}-0{,}25}\\ ;\\ n_Z=%s', n(nZ_)), kzy, r.inter.kzy, '')
                    hc('Éq. 6.61 : N/(χy·NRk/γM1) + kyy·M/(χLT·My,Rk/γM1)', sprintf('%s+%s\\frac{%s}{%s}', n(nY_), n(kyy), n(MEd / 1e3), n(dn / 1e3)), nY_ + kyy * MEd / dn, r.inter.ratio61, '')
                    hc('Éq. 6.62 : N/(χz·NRk/γM1) + kzy·M/(χLT·My,Rk/γM1)', sprintf('%s+%s\\frac{%s}{%s}', n(nZ_), n(kzy), n(MEd / 1e3), n(dn / 1e3)), nZ_ + kzy * MEd / dn, r.inter.ratio62, '')}];
            end
            % --- voilement de l'âme par cisaillement (EN 1993-1-5 §5, âme non raidie)
            et = 1.2 - 0.2 * (fy > 460e6);
            if hw / tw > 72 * eps / et
                lw = hw / (86.4 * tw * eps);
                if lw < 0.83 / et, chw = et; elseif lw < 1.08, chw = 0.83 / lw; else, chw = 1.37 / (0.7 + lw); end
                Vb = chw * fy * hw * tw / (sqrt(3) * g1);
                rows = [rows; {
                    hc('Voilement de l''âme : χw (tableau 5.1, poteau d''extrémité rigide)', sprintf('\\bar\\lambda_w=\\frac{h_w}{86{,}4\\,t_w\\varepsilon}=%s', n(lw)), chw, r.web.chi, '')
                    hc('Vb,Rd = χw·fy·hw·tw/(√3·γM1)', sprintf('V_{b,Rd}=\\frac{%s\\times%s\\times%s}{\\sqrt3\\times%s}', n(chw), n(fy / 1e6), n(hw * tw * 1e6), n(g1)), Vb / 1e3, r.web.VbRd / 1e3, 'kN')}];
            else
                rows{end + 1, 1} = ValidationReport.grp(sprintf('Voilement de l''âme par cisaillement : hw/tw = %.1f ≤ 72ε/η = %.1f, sans objet.', hw / tw, 72 * eps / et));
            end
            rows{end + 1, 1} = ValidationReport.grp(['Non recalculé : voilement local sous charges concentrées, flexion déviée, ELS, classe 4 ; annexe nationale : seules γM0 et γM1 sont paramétrables. ' ...
                'Le recalcul reprend les mêmes formules écrites autrement (Wpl par le moment statique d''une demi-section) : il détecte les erreurs de programmation, pas un choix de formule discutable.']);
        end

        function rows = handFatigue(app)
            %HANDFATIGUE Fatigue : Goodman recalculé à partir des champs de saisie et de la contrainte de la poutre.
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            B = app.H.Beam;
            f = app.Results.fatigue;
            bd = app.Results.beam.check.bend;
            Kt = B.Kt.Value; R = B.fR.Value;
            Rm = app.DM.getMaterial(B.mat.Value).Rm;
            smax = bd.sigmaMaxAbs;
            Se = B.fka.Value * B.fkb.Value * min(0.5 * Rm, 700e6);
            sa = Kt * smax * (1 - R) / 2;
            sm = smax * (1 + R) / 2;
            nn = 1 / (sa / Se + max(sm, 0) / Rm);
            rows = {ValidationReport.grp('Fatigue (Goodman modifié, Shigley chap. 6) : recalcul à partir des champs de saisie')
                hc('σmax nominale = Kt·σmax / Kt (la contrainte nominale n''est pas reconstruite à tort)', sprintf('\\sigma_{max}=\\frac{K_t\\sigma_{max}}{K_t}=\\frac{%s}{%s}', n(bd.sigmaMaxKt / 1e6), n(Kt)), bd.sigmaMaxKt / Kt / 1e6, smax / 1e6, 'MPa')
                hc('Se = ka·kb·min(0,5·Rm ; 700 MPa)', sprintf('S_e=%s\\times%s\\times\\min(0{,}5\\times%s,\\,700)', n(B.fka.Value), n(B.fkb.Value), n(Rm / 1e6)), Se / 1e6, f.Se / 1e6, 'MPa')
                hc('σa = Kf·σmax·(1−R)/2', sprintf('\\sigma_a=%s\\times%s\\times\\frac{1-(%s)}{2}', n(Kt), n(smax / 1e6), n(R)), sa / 1e6, f.sigmaA / 1e6, 'MPa')
                hc('σm = σmax·(1+R)/2', sprintf('\\sigma_m=%s\\times\\frac{1+(%s)}{2}', n(smax / 1e6), n(R)), sm / 1e6, f.sigmaM / 1e6, 'MPa')
                hc('n = 1/(σa/Se + σm/Rm)', sprintf('n=\\frac{1}{%s/%s+%s/%s}', n(sa / 1e6), n(Se / 1e6), n(max(sm, 0) / 1e6), n(Rm / 1e6)), nn, f.n, '')
                ValidationReport.grp('Hypothèses non recalculables : acier, vie infinie, Kf = Kt (sensibilité à l''entaille q = 1), chargement uniaxial d''amplitude constante. Autre vérification de fatigue des constructions métalliques : EN 1993-1-9, non traitée.')};
        end

        function rows = handProfiles(app)
            %HANDPROFILES Profilé le plus léger : cohérence du tableau (tri, σadm, masse, L/f, choix du premier qui vérifie).
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            B = app.H.Beam;
            T = app.Results.profiles;
            L = B.L.Value;
            rho = app.DM.getMaterial(B.mat.Value).rho;
            S = T.("S (mm²)");
            inv = sum(diff(S(~isnan(S))) < 0);
            sadm = T.("σadm (MPa)");
            sadm = sadm(~isnan(sadm));
            ok = ~contains(string(T.("Résistance")), "NON") & ~contains(string(T.("Résistance")), "erreur");
            rows = {ValidationReport.grp(sprintf('Profilé le plus léger, famille %s : %d profilés essayés avec le chargement de l''onglet', char(B.pfam.Value), height(T)))
                hc('Tri par aire croissante : nombre d''inversions', '\#\{i:\ S_{i+1}<S_i\}', inv, 0, '', 0)
                hc('σadm = Re/s (tous les profilés)', sprintf('\\sigma_{adm}=\\frac{%s}{%s}', n(B.Re.Value), n(B.s.Value)), B.Re.Value / B.s.Value, sadm(1), 'MPa')};
            i1 = find(ok, 1);
            if isempty(i1)
                rows{end + 1, 1} = ValidationReport.grp('Aucun profilé de cette famille ne vérifie le chargement : pas de profilé retenu.');
                return
            end
            m_ = T.("Masse (kg/m)")(i1);
            Sb = T.("S (mm²)")(i1);
            rows = [rows; {
                hc(sprintf('Masse linéique du profilé retenu (%s) = ρ·S', char(T.("Profilé")(i1))), sprintf('m=\\rho S=%s\\times%s\\times10^{-6}', n(rho), n(Sb)), rho * Sb * 1e-6, m_, 'kg/m')
                hc('Le profilé retenu est le plus léger qui vérifie', '\min\{S_i:\ \text{vérifié}\}', min(S(ok)), Sb, 'mm²')
                hc('L/f du profilé retenu = L / f max', sprintf('\\frac{L}{f}=\\frac{%s}{%s}', n(L * 1e3), n(T.("f max (mm)")(i1))), L * 1e3 / T.("f max (mm)")(i1), T.("L/f (-)")(i1), '')}];
            if B.pdef.Value > 0
                rows{end + 1, 1} = hc(sprintf('Critère de flèche L/%g respecté par le profilé retenu (0 = oui)', B.pdef.Value), ...
                    sprintf('\\frac{L}{f}\\ge %s', n(B.pdef.Value)), double(T.("L/f (-)")(i1) < B.pdef.Value), 0, '', 0);
            end
            rows{end + 1, 1} = ValidationReport.grp(['Non recalculé ici : la contrainte de chaque profilé (poids propre et moments dépendent du profilé). ' ...
                'Pour la contrôler, importer le profilé retenu dans l''onglet Poutres et consulter son dossier de validation.']);
        end

        function v = cellNumber(x)
            if isnumeric(x)
                v = x;
            else
                v = str2double(strrep(char(string(x)), ',', '.'));
            end
            if ~isfinite(v)
                error('MecaStruct:Validation:invalidInput', 'Valeur non numérique dans le tableau des combinaisons.');
            end
        end

        function rows = beamPlaneRows(sol, plane)
            %BEAMPLANEROWS Équilibre global et torseur de cohésion (par la gauche) d'un plan de flexion.
            %   plane 'y' : plan (x, y), Mfz et Ty ; plane 'z' : plan (x, z) équivalent (F' = Fz, C' = −My,
            %   p' = pz), avec Mfy = −M' et Tz = T'.
            hc = @ValidationReport.hc;
            n = @ValidationReport.num;
            mo = sol.model;
            L = mo.L;
            rea = sol.reactions;
            pl = mo.pointLoads;
            pm = mo.pointMoments;
            dl = mo.distLoads;
            if strcmp(plane, 'y')
                fF = 'Fy'; fC = 'Mz'; fR = 'Ry'; sC = 1; sM = 1; Mpp = sol.Mfz; Tpp = sol.Ty;
                lab = '(x, y)'; nM = 'Mfz'; nT = 'Ty'; nF = 'y';
            else
                fF = 'Fz'; fC = 'My'; fR = 'Rz'; sC = -1; sM = -1; Mpp = sol.Mfy; Tpp = sol.Tz;
                lab = '(x, z)'; nM = 'Mfy'; nT = 'Tz'; nF = 'z';
            end
            px = []; F = [];
            if ~isempty(pl), px = [pl.pos]; F = [pl.(fF)]; end
            cx = []; C = [];
            if ~isempty(pm), cx = [pm.pos]; C = sC * [pm.(fC)]; end
            rp = [rea.pos]; rR = [rea.(fR)]; rM = sC * [rea.(fC)];
            dist = struct('a', {}, 'b', {}, 'c', {});
            for k = 1:numel(dl)
                if strcmp(char(dl(k).dir), nF)
                    dist(end + 1) = struct('a', dl(k).a, 'b', dl(k).b, 'c', dl(k).coeffs); %#ok<AGROW>
                end
            end
            qint = @(d, f) integral(@(x) arrayfun(@(xx) polyval(d.c, xx - d.a) * f(xx), x), d.a, d.b);
            sumF = sum(F) + sum(rR) + sum(arrayfun(@(d) qint(d, @(x) 1), dist));
            sumM = sum(px .* F) + sum(C) + sum(rp .* rR) + sum(rM) + sum(arrayfun(@(d) qint(d, @(x) x), dist));
            fsc = max([1, abs(F), abs(rR)]);
            tolE = 1e-6 * fsc * max(1, L);
            rows = {
                ValidationReport.grp(sprintf('Équilibre global de la poutre, plan %s, recalculé à partir du modèle et des réactions du solveur', lab))
                hc(sprintf('Équilibre des forces en %s (N)', nF), sprintf('\\sum F_%s=\\sum F_{ext}+\\sum R=%s\\ \\text{(attendu 0)}', nF, n(sumF)), sumF, 0, 'N', tolE)
                hc(sprintf('Équilibre des moments du plan %s, en s = 0 (N·m)', lab), sprintf('\\sum M(0)=\\sum x_iF_i+\\int x\\,p\\,dx+\\sum C+\\sum(x_RR+M_R)=%s\\ \\text{(attendu 0)}', n(sumM)), sumM, 0, 'N·m', tolE * max(1, L))};
            % coupes : abscisses types et extremum, décalées si elles tombent sur une charge ou un appui
            s0 = [L * [0.1 0.25 0.5 0.75 0.9], sol.extrema.(nM).sMax];
            posAll = [px, cx, rp];
            for k = 1:numel(s0)
                if any(abs(posAll - s0(k)) < 1e-9)
                    if s0(k) + 1e-6 * L > L   % charge en s = L : couper juste avant, sinon la somme à gauche l'inclut
                        s0(k) = s0(k) - 1e-6 * L;
                    else
                        s0(k) = s0(k) + 1e-6 * L;
                    end
                end
            end
            rows{end + 1, 1} = ValidationReport.grp(sprintf('Plan %s : %s et %s recalculés en sommant les actions à GAUCHE de la coupure (le solveur somme à droite)', lab, nM, nT));
            for k = 1:numel(s0)
                s = s0(k);
                Mh = 0; Th = 0;
                for i = 1:numel(px)
                    if px(i) < s, Mh = Mh + (s - px(i)) * F(i); Th = Th - F(i); end
                end
                for i = 1:numel(cx)
                    if cx(i) < s, Mh = Mh - C(i); end
                end
                for i = 1:numel(rp)
                    if rp(i) < s, Mh = Mh + (s - rp(i)) * rR(i) - rM(i); Th = Th - rR(i); end
                end
                for i = 1:numel(dist)
                    d = dist(i);
                    if s > d.a
                        bb = min(d.b, s);
                        Mh = Mh + integral(@(x) arrayfun(@(xx) polyval(d.c, xx - d.a) * (s - xx), x), d.a, bb);
                        Th = Th - integral(@(x) arrayfun(@(xx) polyval(d.c, xx - d.a), x), d.a, bb);
                    end
                end
                Mh = sM * Mh;
                Ms = BeamAndTrussSolver.ppEval(Mpp, s);
                Ts = BeamAndTrussSolver.ppEval(Tpp, s);
                tolM = 1e-6 * max(1, abs(Ms)) + 1e-6;
                tolT = 1e-6 * max(1, abs(Ts)) + 1e-6;
                rows{end + 1, 1} = hc(sprintf('%s en s = %.4g m', nM, s), sprintf('M(s)=\\sum_{gauche}\\left[(s-x_i)F_{i}-C_{i}\\right]+\\int(s-x)p\\,dx=%s\\,\\mathrm{kN\\cdot m}', n(Mh / 1e3)), Mh / 1e3, Ms / 1e3, 'kN·m', tolM / 1e3); %#ok<AGROW>
                rows{end + 1, 1} = hc(sprintf('%s en s = %.4g m', nT, s), sprintf('T(s)=-\\sum_{gauche}F-\\int p\\,dx=%s\\,\\mathrm{kN}', n(Th / 1e3)), Th / 1e3, Ts / 1e3, 'kN', tolT / 1e3); %#ok<AGROW>
            end
        end
    end

    %% =============================================================================================
    %  Utilitaires
    %  =============================================================================================
    methods (Static, Access = private)

        function e = esc(varargin)
            %ESC Échappe les caractères HTML ; sans argument renvoie le handle de la fonction.
            if nargin == 0
                e = @ValidationReport.esc;
                return
            end
            s = char(string(varargin{1}));
            s = strrep(s, '&', '&amp;');
            s = strrep(s, '<', '&lt;');
            e = strrep(s, '>', '&gt;');
        end

        function s = num(x)
            s = sprintf('%.6g', x);
        end

        function s = mj(latex)
            % Formule en ligne pour MathJax (le LaTeX est échappé pour le HTML).
            s = ['$' ValidationReport.esc(latex) '$'];
        end

        function s = mjRaw(latex)
            % Chaîne LaTeX déjà délimitée par des dollars (moteurs, fiches).
            s = ValidationReport.esc(latex);
        end

        function s = b64(file)
            fid = fopen(file, 'r');
            cl = onCleanup(@() fclose(fid));
            bytes = fread(fid, Inf, '*uint8');
            s = char(matlab.net.base64encode(bytes));
            clear cl
        end

        function restoreTheme(app, th)
            try
                if isvalid(app.UIFigure)
                    app.UIFigure.Theme = th;
                end
            catch
            end
        end

        function rmTemp(folder)
            try
                if isfolder(folder)
                    rmdir(folder, 's');
                end
            catch
            end
        end

        function html = safe(fn)
            % Un bloc qui échoue ne doit pas empêcher la génération du dossier.
            try
                html = fn();
            catch err
                html = ['<p class="warnbox">Section indisponible : ' ValidationReport.esc(err.message) '</p>'];
            end
        end

        function [html, nWarn, nKo] = safeTwo(fn)
            nWarn = 0;
            nKo = 0;
            try
                [html, nWarn, nKo] = fn();
            catch err
                html = ['<p class="warnbox">Section indisponible : ' ValidationReport.esc(err.message) '</p>'];
            end
        end

        function [html, nOK, nTot] = safeHand(fn)
            nOK = 0;
            nTot = 0;
            try
                [html, nOK, nTot] = fn();
            catch err
                html = ['<p class="warnbox">Section indisponible : ' ValidationReport.esc(err.message) '</p>'];
            end
        end

        function html = tableHTML(D, cols, rowNames)
            e = ValidationReport.esc;
            if istable(D)
                cols = D.Properties.VariableNames;
                D = table2cell(D);
            elseif isnumeric(D) || islogical(D)
                D = num2cell(D);
            end
            if isempty(D)
                html = '<p class="muted">(tableau vide)</p>';
                return
            end
            if ischar(cols) || isstring(cols)
                cols = cellstr(cols);
            end
            html = '<table class="data">';
            if ~isempty(cols)
                html = [html '<tr>'];
                if ~isempty(rowNames)
                    html = [html '<th></th>'];
                end
                for j = 1:numel(cols)
                    html = [html '<th>' e(cols{j}) '</th>']; %#ok<AGROW>
                end
                html = [html '</tr>'];
            end
            for i = 1:size(D, 1)
                html = [html '<tr>']; %#ok<AGROW>
                if ~isempty(rowNames)
                    html = [html '<th>' e(rowNames{i}) '</th>']; %#ok<AGROW>
                end
                for j = 1:size(D, 2)
                    v = D{i, j};
                    if islogical(v)
                        t = ValidationReport.yesNo(v);
                    elseif isnumeric(v) && isscalar(v)
                        t = sprintf('%.6g', v);
                    else
                        t = char(string(v));
                    end
                    html = [html '<td>' e(t) '</td>']; %#ok<AGROW>
                end
                html = [html '</tr>']; %#ok<AGROW>
            end
            html = [html '</table>'];
        end

        function c = css()
            c = ['body{background:#fff;color:#1f2328;font:15px/1.55 system-ui,"Segoe UI",sans-serif;margin:0}' ...
                'main{max-width:1000px;margin:0 auto;padding:20px 16px 80px}' ...
                'h1{font-size:1.7rem;margin:0 0 4px;color:#14406e}' ...
                'h2{margin-top:36px;padding:6px 10px;background:#14406e;color:#fff;border-radius:4px;font-size:1.15rem}' ...
                'h3{margin:20px 0 6px;color:#14406e}' ...
                'html{scroll-behavior:smooth}h2{scroll-margin-top:8px;display:flex;justify-content:space-between;align-items:baseline;gap:12px}' ...
                'h2 a.top{color:#cfe0f5;font-size:.8rem;font-weight:normal;text-decoration:none;white-space:nowrap}h2 a.top:hover{color:#fff}' ...
                '.toc{border:1px solid #cfd6df;background:#f5f8fc;border-radius:6px;padding:8px 14px;margin:16px 0}' ...
                '.toc ol{margin:6px 0 0;padding-left:22px;columns:2 260px}.toc a{color:#1f5fa8;text-decoration:none}.toc a:hover{text-decoration:underline}' ...
                '.meta{color:#5b6370;margin-top:0}' ...
                '.box{border:1px solid #cfd6df;background:#f5f8fc;border-radius:6px;padding:8px 14px;margin:12px 0}' ...
                '.status{font-size:1.15rem;font-weight:bold;background:#e8f1fb;border-left:6px solid #1f5fa8;padding:8px 12px;margin:12px 0}' ...
                '.warnbox{background:#fff3d6;border-left:5px solid #d9a400;padding:6px 12px;margin:10px 0}' ...
                'table{border-collapse:collapse;width:100%;margin:8px 0;font-size:.92rem}' ...
                'th,td{border:1px solid #cfd6df;padding:4px 7px;text-align:left;vertical-align:top}' ...
                'th{background:#eef2f7}' ...
                'td.v,td.n{font-family:Consolas,monospace}td.n{text-align:right;white-space:nowrap}' ...
                'table.kv td:first-child{width:55%}' ...
                '.hand{table-layout:fixed}.hand th:nth-child(1){width:17%}.hand th:nth-child(2){width:34%}.hand th:nth-child(3),.hand th:nth-child(4){width:14%}.hand th:nth-child(5){width:8%}.hand th:nth-child(6){width:13%}.hand td{overflow-wrap:anywhere}' ...
                'td.grp{background:#eef2f7;font-weight:bold;color:#14406e}' ...
                'td.fm{font-size:.88rem}td.rv{white-space:nowrap;font-size:.85rem}' ...
                '.ok{color:#1d7a3a;font-weight:bold}.ko{color:#b3261e;font-weight:bold}.warn{color:#9a6a00;font-weight:bold}' ...
                '.muted{color:#5b6370}' ...
                'figure{margin:10px 0;text-align:center}figure img{max-width:100%;border:1px solid #cfd6df}' ...
                '.eqblock{border:1px solid #e1e6ee;border-radius:6px;padding:6px 12px;margin:8px 0}' ...
                '.eqtitle{font-weight:bold;color:#14406e}.eq{margin:2px 0}.var{color:#5b6370;font-size:.85rem}' ...
                '.rep{font-family:Consolas,monospace;font-size:.85rem;background:#f7f8fa;border:1px solid #e1e6ee;padding:8px 12px}' ...
                '.rsec{font-weight:bold;color:#14406e;margin-top:10px;border-bottom:1px solid #cfd6df}.rln{white-space:pre-wrap}' ...
                '.comment{border:1px solid #9aa5b4;min-height:90px;border-radius:4px}' ...
                'mjx-container{overflow-x:auto;overflow-y:hidden;max-width:100%}' ...
                '.rep{overflow-x:auto}.rln{overflow-wrap:anywhere}figure img{height:auto;display:block;margin:0 auto}' ...
                '@media(max-width:760px){table{display:block;overflow-x:auto}.hand{table-layout:auto}td.rv{white-space:normal}h2{flex-wrap:wrap}}' ...
                '@media print{h2{break-after:avoid}table,figure,.eqblock{break-inside:avoid}h2 a.top{display:none}}'];
        end
    end
end
