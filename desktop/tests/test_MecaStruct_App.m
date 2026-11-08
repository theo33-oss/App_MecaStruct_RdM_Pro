function tests = test_MecaStruct_App
%TEST_MECASTRUCT_APP Tests de l'interface graphique MecaStruct_App (création invisible).
%   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
%   Création sans fenêtre visible, exemples de tous les onglets, valeurs de référence, transfert
%   section → poutre → tenseur, formulaire rapide, export, données utilisateur, erreurs
%   journalisées, analyse sûre des expressions, fermeture propre.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
testCase.TestData.nFig0 = numel(findall(groot, 'Type', 'figure'));
testCase.TestData.tmp = tempname;
mkdir(testCase.TestData.tmp);
testCase.TestData.userFile = fullfile(testCase.TestData.tmp, 'userdb.mat');
testCase.TestData.app = MecaStruct_App('Visible', 'off', 'UserFile', testCase.TestData.userFile);
end

function teardownOnce(testCase)
app = testCase.TestData.app;
fig = app.UIFigure;
delete(app);
verifyFalse(testCase, isvalid(fig), 'La fenêtre doit être détruite par delete(app).');
verifyEqual(testCase, numel(findall(groot, 'Type', 'figure')), testCase.TestData.nFig0, ...
    'Aucune figure ne doit rester ouverte après delete(app).');
if isfolder(testCase.TestData.tmp)
    rmdir(testCase.TestData.tmp, 's');
end
end

%% ------------------------------------------------------------------------------------------
function testCreationInvisible(testCase)
app = testCase.TestData.app;
verifyTrue(testCase, isvalid(app.UIFigure));
verifyEqual(testCase, app.UIFigure.Name, 'MecaStruct RdM Pro');
verifyEqual(testCase, char(app.UIFigure.Visible), 'off');
titles = {app.TabGroup.Children.Title};
verifyEqual(testCase, titles, {'Accueil', 'Base de données', 'Sections', 'Poutres', 'Treillis', 'Sollicitations', ...
    'Flambage', 'Tenseurs & Critères', 'Hooke & Jauges', 'Convertisseur'});
verifyEqual(testCase, numel(app.H.Tra.Tab.Parent.Children), 4, 'Sous-onglets de Sollicitations.');
verifyTrue(testCase, ismember(app.FormulaKey, DataManager.formulaKeys()));
end

function testAideLot2(testCase)
app = testCase.TestData.app;
app.computeBeam();
rep = strjoin(app.H.Beam.W.Report.Value, newline);
verifyTrue(testCase, contains(rep, 'Verdict : la poutre résiste'));
verifyTrue(testCase, contains(rep, 'Étape suivante'));
end

function testProblemeEtChargeRapide(testCase)
app = testCase.TestData.app;
f = fullfile(testCase.TestData.tmp, 'pb.mat');
app.H.Beam.L.Value = 7.5;
app.saveProblem('Beam', f);
app.H.Beam.L.Value = 3;
n = app.loadProblem('Beam', f);
verifyEqual(testCase, app.H.Beam.L.Value, 7.5);
verifyEqual(testCase, n, 0, 'Aucun champ non restauré.');
verifyError(testCase, @() app.loadProblem('Tr', f), 'MecaStruct:App:badProblemFile');
app.loadExample('Poutres', 'isostatique');
n0 = size(app.H.Beam.dl.Data, 1);
app.H.Beam.qshape.Value = 'Trapèze (p1 → p2)';
app.H.Beam.qp2.Value = -20;
app.addQuickLoad();
verifyEqual(testCase, size(app.H.Beam.dl.Data, 1), n0 + 1);
app.computeBeam();
app.H.Beam.qb.Value = app.H.Beam.qa.Value;
verifyError(testCase, @() app.addQuickLoad(), 'MecaStruct:App:invalidLoad');
verifyEqual(testCase, app.guidedTour(), 5);
app.loadExample('Poutres', 'isostatique');
end

function testProjetEtExportTableaux(testCase)
app = testCase.TestData.app;
tmp = testCase.TestData.tmp;
app.loadExample('Poutres', 'isostatique');
app.H.Beam.L.Value = 6.5;
fp = fullfile(tmp, 'projet.mat');
app.saveProject(fp);
app.H.Beam.L.Value = 2;
failed = app.loadProject(fp);
verifyEmpty(testCase, failed);
verifyEqual(testCase, app.H.Beam.L.Value, 6.5);
app.loadExample('Poutres', 'isostatique');
app.computeBeam();
fx = fullfile(tmp, 'poutre.xlsx');
app.exportResults('Beam', fx);
names = sheetnames(fx);
verifyTrue(testCase, all(ismember(["Enveloppe", "Efforts"], names)));
env = readtable(fx, 'Sheet', 'Enveloppe', 'VariableNamingRule', 'preserve');
verifyEqual(testCase, env.Max(string(env.Effort) == "Mfz"), app.Results.beam.sol.extrema.Mfz.max / 1e3, 'AbsTol', 1e-9);
eff = readtable(fx, 'Sheet', 'Efforts', 'VariableNamingRule', 'preserve');
verifyEqual(testCase, eff.("s (m)")(end), app.Results.beam.sol.N.breaks(end), 'AbsTol', 1e-12);
files = app.exportResults('Beam', fullfile(tmp, 'poutre.csv'));
verifyTrue(testCase, all(cellfun(@isfile, files)));
end

function testCombinaisonsEtPoidsPropre(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
app.H.Beam.combo.Data = {'G seul', 1, 0, 0, 0; 'G+Q', 1, 1, 0, 0; 'ELU', 1.35, 1.5, 0, 0};
T = app.computeCombinations();
verifyEqual(testCase, height(T), 4);
app.computeBeam();
ref = app.Results.beam.sol.extrema.Mfz.max / 1e3;
verifyEqual(testCase, T.("Mfz max (kN·m)")(2), ref, 'RelTol', 1e-9, 'G+Q = calcul avec tous les cas à 1.');
verifyGreaterThan(testCase, T.("Mfz max (kN·m)")(1), 0);
verifyLessThan(testCase, T.("Mfz max (kN·m)")(1), ref, 'Sans le cas Q, le moment est plus petit.');
verifyEqual(testCase, T.("f max (mm)")(end), max(T.("f max (mm)")(1:end-1)), 'Enveloppe = maximum des combinaisons.');
f0 = app.Results.beam.defl.integration.fmax;
app.H.Beam.selfw.Value = true;
app.computeBeam();
verifyGreaterThan(testCase, app.Results.beam.defl.integration.fmax, f0, 'Le poids propre augmente la flèche.');
app.H.Beam.selfw.Value = false;
app.loadExample('Poutres', 'isostatique');
end

function testProfileLePlusLeger(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
S0 = app.H.Beam.S.Value;
[T, best] = app.findLightestProfile('IPE');
verifyEqual(testCase, app.H.Beam.S.Value, S0, 'La saisie de section doit être remise.');
verifyNotEmpty(testCase, best);
verifyTrue(testCase, issorted(T.("S (mm²)")));
iBest = find(T.("Profilé") == string(best));
verifyLessThanOrEqual(testCase, T.("Kt·σ max (MPa)")(iBest), T.("σadm (MPa)")(iBest));
if iBest > 1
    verifyGreaterThan(testCase, T.("Kt·σ max (MPa)")(iBest - 1), T.("σadm (MPa)")(iBest - 1), 'Le profilé précédent ne vérifie pas.');
end
[~, bestF] = app.findLightestProfile('IPE', 1000);
verifyNotEqual(testCase, bestF, best, 'Une flèche L/1000 impose un profilé plus gros.');
end

function testSectionsRepliables(testCase)
% Les sections du panneau de saisie se plient et se déplient ; fermées, leurs champs sont masqués mais gardent leur valeur.
app = testCase.TestData.app;
B = app.H.Beam;
allBtn = findall(B.W.In, 'Type', 'uibutton');
btn = allBtn(contains({allBtn.Text}, 'Eurocode 3 simplifié'));
verifyEqual(testCase, numel(btn), 1);
verifyTrue(testCase, startsWith(btn.Text, char(9656)), 'Fermée au départ.');
verifyFalse(testCase, logical(B.Lcr.Visible));
rows = btn.UserData.rows;
verifyEqual(testCase, cell2mat(btn.Parent.RowHeight(rows)), zeros(1, numel(rows)));
app.loadExample('Poutres', 'isostatique');
app.computeBeam();
r = app.checkEurocode();   % section fermée : le calcul lit les mêmes champs
verifyTrue(testCase, r.ok);
btn.ButtonPushedFcn(btn, []);
verifyTrue(testCase, logical(B.Lcr.Visible));
verifyTrue(testCase, startsWith(btn.Text, char(9662)));
verifyGreaterThan(testCase, sum(cell2mat(btn.Parent.RowHeight(rows))), 0);
btn.ButtonPushedFcn(btn, []);
verifyFalse(testCase, logical(B.Lcr.Visible));
verifyTrue(testCase, logical(B.btnCalc.Visible), 'Le bouton Calculer n''appartient à aucune section fermée.');
end

function testStyleBoutons(testCase)
% Couleur par rôle : calcul en bleu, suppression en rouge, les autres boutons gardent le style par défaut.
app = testCase.TestData.app;
B = app.H.Beam;
verifyEqual(testCase, B.btnCalc.BackgroundColor, [0.12 0.42 0.72]);
btns = findall(B.W.In, 'Type', 'uibutton');
del = btns(strcmp({btns.Text}, 'Supprimer la sélection'));
verifyGreaterThan(testCase, numel(del), 0);
verifyTrue(testCase, all(arrayfun(@(b) isequal(b.BackgroundColor, [0.72 0.25 0.25]), del)));
ex = btns(strcmp({btns.Text}, 'Charger l''exemple'));
verifyFalse(testCase, isequal(ex(1).BackgroundColor, [0.12 0.42 0.72]), 'Charger l''exemple reste neutre.');
end

function testEurocodeEtFatigue(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
app.computeBeam();
e = app.Results.beam.sol.extrema;
r = app.checkEurocode();
verifyEqual(testCase, r.MEd, max(abs([e.Mfz.max, e.Mfz.min])), 'RelTol', 1e-12);
verifyEqual(testCase, r.class.class, 1);
verifyGreaterThan(testCase, r.ratioM, 0.3);
verifyLessThan(testCase, r.ratioM, 0.7);
verifyTrue(testCase, r.ok);
verifyGreaterThan(testCase, r.ltb.Mcr, 0);
verifyEqual(testCase, r.okAll, r.ok && r.ltb.ok);
app.H.Beam.Lcr.Value = 1;
rShort = app.checkEurocode();
verifyLessThan(testCase, rShort.ltb.ratio, r.ltb.ratio, 'Un maintien latéral rapproché réduit le déversement.');
app.H.Beam.Lcr.Value = 0;
verifyTrue(testCase, isfield(r, 'axial') && isempty(r.buck) && ~r.partial, 'Sans effort normal : pas de flambement.');
% avec une compression de 100 kN (pivot en A retient x)
app.H.Beam.pl.Data = {2, 0, -20, 0, 'F', 'Q'; 6, -100, 0, 0, 'N', 'Q'};
app.computeBeam();
rN = app.checkEurocode();
verifyNotEmpty(testCase, rN.buck);
verifyNotEmpty(testCase, rN.inter, 'Compression + moment : l''interaction 6.3.3 est vérifiée.');
verifyEqual(testCase, rN.inter.ratio, max(rN.inter.ratio61, rN.inter.ratio62));
verifyGreaterThan(testCase, rN.inter.ratio, rN.buck.ratio, 'Le moment s''ajoute à la compression.');
verifyEqual(testCase, rN.buck.NEd, 100e3, 'RelTol', 1e-6);
verifyEqual(testCase, rN.axial.n, 100e3 / rN.axial.Npl, 'RelTol', 1e-12);
app.loadExample('Poutres', 'isostatique');
app.computeBeam();
app.computeCombinations();
app.H.Beam.ecsrc.Value = 'enveloppe';
rEnv = app.checkEurocode();
verifyGreaterThan(testCase, rEnv.ratioM, r.ratioM, 'L''ELU est plus défavorable que le cas courant.');
app.H.Beam.ecsrc.Value = 'courant';
app.H.Beam.fR.Value = -1;
f1 = app.checkFatigue();
app.H.Beam.fR.Value = 0;
f0 = app.checkFatigue();
verifyGreaterThan(testCase, f0.n, f1.n, 'Un chargement répété (R = 0) est moins sévère que l''alterné.');
verifyGreaterThan(testCase, f1.n, 0);
app.H.Beam.fR.Value = 0;
app.H.Beam.S.ValueChangedFcn(app.H.Beam.S, []);
verifyError(testCase, @() app.checkEurocode(), 'MecaStruct:App:invalidInput');
app.loadExample('Poutres', 'isostatique');
end

function testDossierEtendu(testCase)
% Le dossier de la poutre inclut combinaisons, Eurocode 3, fatigue et profilé le plus léger, recalculés à la main.
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
app.computeBeam();
app.computeCombinations();
app.checkEurocode();
app.checkFatigue();
app.findLightestProfile('IPE');
% une saisie modifiée après coup doit être reprise par le dossier (pas de tableau périmé)
app.H.Beam.dl.Data = {0, 6, 'y', 'uniforme', '-12', 'q', 'G'};
f = ValidationReport.generate(app, 'Beam', fullfile(testCase.TestData.tmp, 'etendu'));
h = fileread(f);
for t = {'Combinaison dimensionnante', 'Eurocode 3 : classes', 'Fatigue (Goodman modifié', 'Profilé le plus léger, famille IPE', ...
        'Eurocode 3 (EN 1993-1-1)', 'Déversement : poutre à fourches'}
    verifyTrue(testCase, contains(h, t{1}), t{1});
end
verifyFalse(testCase, contains(h, '<span class="ko">ÉCART'), 'Tous les recalculs à la main concordent avec le solveur.');
verifyGreaterThan(testCase, numel(strfind(h, '<span class="ok">concordent')), 40);
app.loadExample('Poutres', 'isostatique');
end

function testDocumentsEtRapportHTML(testCase)
app = testCase.TestData.app;
setenv('MECASTRUCT_NO_BROWSER', '1');
cleanup = onCleanup(@() setenv('MECASTRUCT_NO_BROWSER', ''));
for nm = {'NOTE_DE_CALCUL.html', 'GUIDE_UTILISATEUR.html'}
    verifyTrue(testCase, isfile(app.openDoc(nm{1})), nm{1});
end
verifyError(testCase, @() app.openDoc('inexistant.html'), 'MecaStruct:App:docMissing');
app.computeTorsion();
h = app.H.Tor.W.ReportHTML.HTMLSource;
verifyTrue(testCase, contains(h, 'class="head"') && contains(h, 'class="sec"') && contains(h, 'class="num"'));
verifyTrue(testCase, contains(h, '<span class="ko">NON vérifié'), 'Verdict négatif en rouge.');
end

function testEffortsDepuisPoutre(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
app.computeBeam();
F = app.H.Fle;
F.s0.Value = 3;
app.loadFromBeam('Fle', 'abscisse');
verifyEqual(testCase, F.Mfz.Value, 65, 'AbsTol', 1e-9);            % 43,33·3 − 5·9 − 20·1
verifyEqual(testCase, F.N.Value, 0, 'AbsTol', 1e-9);
app.loadFromBeam('Fle', 'max');
verifyEqual(testCase, F.Mfz.Value, 67.2222222, 'AbsTol', 1e-3);    % Mmax de la poutre
verifyEqual(testCase, F.s0.Value, 2.3333, 'AbsTol', 5e-3);
S = app.H.Sec;
app.loadFromBeam('Sec', 'abscisse');
verifyEqual(testCase, S.Ty.Value, 6.6666667, 'AbsTol', 1e-6);      % Ty(3) = -(43,33 - 30 - 20)
% section de l'onglet Sections ≠ section de la poutre : avertissement dans la ligne d'état
app.computeSection();
app.loadFromBeam('Fle', 'abscisse');
verifyTrue(testCase, contains(F.W.Status.Text, 'Attention'));
app.computeBending();
txt = strjoin(app.H.Fle.W.Report.Value, ' ');
verifyTrue(testCase, contains(txt, 'fibres du haut'));
% saisies de la poutre modifiées sans recalcul : « Efforts en s » relit la poutre à jour
app.H.Beam.dl.Data = {0, 6, 'y', 'uniforme', '-20', 'q', 'G'};
F.s0.Value = 3;
app.loadFromBeam('Fle', 'abscisse');
verifyEqual(testCase, F.Mfz.Value, 110, 'AbsTol', 1e-9);              % 73,33·3 − 20·9/2 − 20·1
S.s0.Value = 99;
verifyError(testCase, @() app.loadFromBeam('Sec', 'abscisse'), 'MecaStruct:App:invalidInput');
end

function testPointLePlusSollicitSurSaut(testCase)
% couple de 20 kN·m en s = 4 sur 6 m : Mfz saute de −13,33 à +6,67 ; « Efforts au point critique » doit
% lire 13,33 kN·m (côté retenu par la vérification), pas la limite à droite
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
B = app.H.Beam;
B.pl.Data = cell(0, 6);
B.dl.Data = cell(0, 7);
B.pm.Data = {4, 0, 0, 20, 'C', 'G'};
app.loadFromBeam('Fle', 'max');
verifyEqual(testCase, abs(app.H.Fle.Mfz.Value), 20 * 4 / 6, 'AbsTol', 1e-6);
end

function testVerificationMainPlanZEtDisque(testCase)
% plan (x, z) : le §3 recalcule aussi Tz et Mfy ; disque en flexion biaxiale : pas de faux écart
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
B = app.H.Beam;
B.pl.Data = {2, 0, -20, -8, 'F', 'G'};
[nOK, nTot] = ValidationReport.handCheck(app, 'Beam');
verifyEqual(testCase, nOK, nTot);
B.pl.Data = {2, 0, -20, 0, 'F', 'G'};
[~, nTot0] = ValidationReport.handCheck(app, 'Beam');
verifyGreaterThan(testCase, nTot, nTot0, 'Les contrôles du plan (x, z) doivent s''ajouter.');
S = app.H.Sec;
S.type.Value = 'disque'; S.D.Value = 60;
app.useSectionForBeam();
B.pl.Data = {2, 0, -5, -5, 'F', 'G'};
[nOK, nTot] = ValidationReport.handCheck(app, 'Beam');
verifyEqual(testCase, nOK, nTot, 'Disque en flexion biaxiale : contrainte à la main ≠ solveur.');
end

function testLimiteHyperstatiqueIyz(testCase)
% cornière (Iyz ≠ 0) sur poutre hyperstatique : la limite est dite dans l'état, le rapport et le dossier
app = testCase.TestData.app;
setenv('MECASTRUCT_NO_BROWSER', '1');
cleanup = onCleanup(@() setenv('MECASTRUCT_NO_BROWSER', ''));
S = app.H.Sec;
S.type.Value = 'L'; S.h.Value = 100; S.b.Value = 100; S.t.Value = 10;
app.useSectionForBeam();
app.loadExample('Poutres', 'hyperstatique');
B = app.H.Beam;
B.Iyz.Value = -1.066e6;   % le chargement d'exemple remet Iyz à 0 : on le remet pour cet essai
app.computeBeam();
verifyTrue(testCase, contains(B.W.Status.Text, 'LIMITE'));
verifyTrue(testCase, contains(strjoin(B.W.Report.Value, ' '), 'NON fiables'));
f = ValidationReport.generate(app, 'Beam', fullfile(testCase.TestData.tmp, 'limite'));
h = fileread(f);
verifyTrue(testCase, contains(h, 'LIMITE DU LOGICIEL') && contains(h, 'NON fiables'));
verifyTrue(testCase, contains(h, 'integrity="sha384-'));
end

function testConvertisseur(testCase)
cv = @MecaStruct_App.convertUnits;
verifyEqual(testCase, cv(1, 'Longueur', 'in', 'mm'), 25.4, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Longueur', 'ft', 'in'), 12, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Force', 'kN', 'N'), 1000, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Force', 'kgf', 'N'), 9.80665, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Force', 'kip', 'lbf'), 1000, 'RelTol', 1e-9);
verifyEqual(testCase, cv(1, 'Contrainte et pression', 'ksi', 'MPa'), 6.894757293168, 'RelTol', 1e-9);
verifyEqual(testCase, cv(1, 'Contrainte et pression', 'MPa', 'N/mm²'), 1, 'RelTol', 1e-12);
verifyEqual(testCase, cv(190, 'Module d''Young et de Coulomb', 'GPa', 'MPa'), 190000, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Moment', 'kN·m', 'N·mm'), 1e6, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Aire', 'in²', 'mm²'), 645.16, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Moment quadratique', 'in⁴', 'mm⁴'), 25.4^4, 'RelTol', 1e-12);
verifyEqual(testCase, cv(1, 'Charge linéique', 'kN/m', 'N/mm'), 1, 'RelTol', 1e-12);
verifyEqual(testCase, cv(180, 'Angle', '°', 'rad'), pi, 'RelTol', 1e-12);
verifyEqual(testCase, cv(0, 'Température absolue', '°C', '°F'), 32, 'AbsTol', 1e-10);
verifyEqual(testCase, cv(100, 'Température absolue', '°C', 'K'), 373.15, 'AbsTol', 1e-10);
verifyEqual(testCase, cv(-40, 'Température absolue', '°F', '°C'), -40, 'AbsTol', 1e-10);
% un écart ΔT n'a pas de décalage : 50 °C d'écart = 90 °F d'écart
verifyEqual(testCase, cv(50, 'Écart de température', '°C', '°F'), 90, 'AbsTol', 1e-10);
verifyEqual(testCase, cv(90, 'Écart de température', '°F', 'K'), 50, 'AbsTol', 1e-10);
verifyEqual(testCase, cv(500, 'Déformation', 'µdéf', '%'), 0.05, 'RelTol', 1e-12);
% aller-retour pour toutes les unités de toutes les grandeurs
T = MecaStruct_App.unitCatalog();
for k = 1:numel(T)
    lab = T(k).units(:, 1);
    for i = 1:numel(lab)
        for j = 1:numel(lab)
            x = cv(cv(7.5, T(k).name, lab{i}, lab{j}), T(k).name, lab{j}, lab{i});
            verifyEqual(testCase, x, 7.5, 'RelTol', 1e-12, sprintf('%s : %s ↔ %s', T(k).name, lab{i}, lab{j}));
        end
    end
end
verifyError(testCase, @() cv(1, 'Longueur', 'in', 'furlong'), 'MecaStruct:App:unknownUnit');
verifyError(testCase, @() cv(1, 'Vitesse', 'm/s', 'km/h'), 'MecaStruct:App:unknownQuantity');
% interface : mise à jour du résultat affiché
app = testCase.TestData.app;
app.selectTab('Convertisseur');
C = app.H.Conv;
C.quant.Value = 'Force';
C.quant.ValueChangedFcn(C.quant, []);
C.val.Value = 12.5;
C.from.Value = 'kN';
C.to.Value = 'N';
C.val.ValueChangedFcn(C.val, []);
verifyEqual(testCase, C.res.Text, '12.5 kN = 12500 N');
verifyEqual(testCase, size(C.all.Data, 1), 8);
verifyError(testCase, @() app.exportValidation('Conv'), 'MecaStruct:App:noValidation');
end

function testDossierValidation(testCase)
app = testCase.TestData.app;
app.runAllExamples();
setenv('MECASTRUCT_NO_BROWSER', '1');
cleanup = onCleanup(@() setenv('MECASTRUCT_NO_BROWSER', ''));
verifyError(testCase, @() app.exportValidation('DB'), 'MecaStruct:App:noValidation');
verifyError(testCase, @() ValidationReport.generate(app, 'XYZ'), 'MecaStruct:Validation:unknownKey');
out = fullfile(testCase.TestData.tmp, 'valid');
for key = {'Beam'}   % un seul dossier complet (diagrammes exportés) : suffisant et plus rapide
    f = app.exportValidation(key{1}, out);
    verifyTrue(testCase, isfile(f), key{1});
    h = fileread(f);
    for needle = {'Bilan automatique', 'Données du problème', 'vérification indépendante', 'data:image/png;base64', 'Avis du relecteur', ...
            'Sommaire', 'href="#formules"', 'id="formules"', 'Théorème de Ménabréa'}
        verifyTrue(testCase, contains(h, needle{1}), sprintf('%s : « %s » absent', key{1}, needle{1}));
    end
    verifyFalse(testCase, contains(h, 'Exemple : deux travées égales'), [key{1} ' : §7 non filtré']);
    verifyFalse(testCase, contains(h, 'Section indisponible'), [key{1} ' : section en erreur']);
    verifyFalse(testCase, contains(h, 'non exécutée'), [key{1} ' : vérification indépendante absente']);
    verifyFalse(testCase, contains(h, '<span class="ko">ÉCART'), [key{1} ' : écart solveur / vérification à la main']);
end
% §3 de tous les modules : la vérification à la main concorde avec le solveur sur les exemples
for key = {'Sec', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'}
    [nOK, nTot] = ValidationReport.handCheck(app, key{1});
    verifyGreaterThan(testCase, nTot, 0, [key{1} ' : aucun contrôle']);
    verifyEqual(testCase, nOK, nTot, [key{1} ' : écart solveur / vérification à la main']);
end
% §7 : chaque formule retenue existe dans les fiches du module (une coquille la ferait disparaître)
for key = {'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'}
    m = ValidationReport.meta(key{1});
    titles = cellfun(@(f) {DataManager.formulaSheet(f).title}, m.forms, 'UniformOutput', false);
    titles = [titles{:}];
    missing = setdiff(m.keep, titles);
    verifyEmpty(testCase, missing, sprintf('%s : formules introuvables : %s', key{1}, strjoin(missing, ' | ')));
end
% boutons : Dossier sur les onglets de calcul, Note et Guide seulement sur la Base de données
app.selectTab('Torsion');
btn = @(t) findall(app.UIFigure, 'Type', 'uibutton', 'Text', t);
verifyTrue(testCase, logical(btn('Dossier de validation de ce problème').Visible));
verifyFalse(testCase, logical(btn('Note de calcul').Visible));
app.selectTab('Base de données');
verifyFalse(testCase, logical(btn('Dossier de validation de ce problème').Visible));
verifyTrue(testCase, logical(btn('Note de calcul').Visible));
end

function testRunAllExamples(testCase)
app = testCase.TestData.app;
status = app.runAllExamples();
names = fieldnames(status.ok);
msg = strjoin(cellfun(@(n) sprintf('%s : %s', n, status.messages.(n)), names, 'UniformOutput', false), newline);
verifyTrue(testCase, status.allOK, msg);
verifyGreaterThanOrEqual(testCase, numel(names), 20);
for k = 1:numel(names)
    verifyTrue(testCase, status.ok.(names{k}), sprintf('%s : %s', names{k}, status.messages.(names{k})));
end
% chaque zone de travail : rapport et premier axe remplis
keys = {'Sec', 'Beam', 'Tr', 'Tra', 'Cis', 'Tor', 'Fle', 'Fla', 'Ten', 'Hoo', 'Jau'};
for k = 1:numel(keys)
    W = app.H.(keys{k}).W;
    verifyGreaterThan(testCase, numel(W.Report.Value), 1, ['Rapport vide : ' keys{k}]);
    for j = 1:numel(W.Axes)
        ax = W.Axes{j}(1);
        verifyNotEmpty(testCase, ax.Children, sprintf('Axe vide : %s, onglet graphique %d', keys{k}, j));
    end
    tf = fieldnames(W.Tables);
    for j = 1:numel(tf)
        verifyNotEmpty(testCase, W.Tables.(tf{j}).Data, sprintf('Table vide : %s.%s', keys{k}, tf{j}));
    end
end
verifyNotEmpty(testCase, app.H.DB.KtAxes.Children);
verifyNotEmpty(testCase, app.H.DB.MatTable.Data);
end

function testSectionRectangle(testCase)
app = testCase.TestData.app;
app.loadExample('Sections');
S = app.H.Sec;
S.type.Value = 'rectangle';
S.b.Value = 100;
S.h.Value = 200;
app.computeSection();
P = app.Results.section.P;
b = 0.1; h = 0.2;
verifyEqual(testCase, P.S, b * h, 'RelTol', 1e-12);
verifyEqual(testCase, P.Iz, b * h^3 / 12, 'RelTol', 1e-9);
verifyEqual(testCase, P.Iy, h * b^3 / 12, 'RelTol', 1e-9);
verifyEqual(testCase, app.Results.section.Pint.Iz, b * h^3 / 12, 'RelTol', 1e-9);
verifyEqual(testCase, app.Results.section.jour.tauMax, 1.5 * 60e3 / (b * h), 'RelTol', 1e-6);
T = S.W.Tables.Comp.Data;
iz = strcmp(T.Grandeur, "Iz");
verifyEqual(testCase, T.Analytique(iz), b * h^3 / 12 * 1e12, 'RelTol', 1e-9);
verifyEqual(testCase, T.('Intégrale')(iz), b * h^3 / 12 * 1e12, 'RelTol', 1e-9);
% transfert vers la poutre et le flambage
app.useSectionForBeam();
verifyEqual(testCase, app.H.Beam.Iz.Value, b * h^3 / 12 * 1e12, 'RelTol', 1e-12);
verifyEqual(testCase, app.H.Beam.S.Value, b * h * 1e6, 'RelTol', 1e-12);
verifyEqual(testCase, app.H.Beam.ky.Value, P.ky, 'RelTol', 1e-12);
verifyEqual(testCase, app.H.Fla.Iy.Value, h * b^3 / 12 * 1e12, 'RelTol', 1e-12);
verifyEqual(testCase, app.H.Beam.Ix.Value, P.J * 1e12, 'RelTol', 1e-12);
% la section transmise est figée : recalculer une autre section ne change pas la vérification de la poutre
app.loadExample('Poutres', 'console');
app.useSectionForBeam();
app.computeBeam();
sig0 = app.Results.beam.check.sigma;
S.b.Value = 50;
app.computeSection();
app.computeBeam();
verifyEqual(testCase, app.Results.beam.check.sigma, sig0, 'RelTol', 1e-12);
% cornière (Iyz ≠ 0) : le flambage reçoit les moments principaux, l'inertie faible est I2
S.type.Value = 'L'; S.h.Value = 100; S.b.Value = 100; S.t.Value = 10;
app.useSectionForBeam();
PL = app.SectionData.P;
verifyEqual(testCase, min(app.H.Fla.Iz.Value, app.H.Fla.Iy.Value), PL.I2 * 1e12, 'RelTol', 1e-9);
verifyEqual(testCase, app.H.Beam.Iyz.Value, PL.Iyz * 1e12, 'RelTol', 1e-9);
verifyEqual(testCase, app.H.Beam.kz.Value, PL.kz, 'RelTol', 1e-12);
app.computeBeam();   % console chargée en y : la cornière fléchit aussi selon z
verifyGreaterThan(testCase, app.Results.beam.defl.integration.fmax, 0);
verifyTrue(testCase, any(contains(app.Results.beam.defl.report, 'Flexion déviée')));
verifyLessThan(testCase, PL.I2, 0.5 * PL.Iz);
% profilé du catalogue : valeurs tabulées, pas la géométrie simplifiée
S.type.Value = 'profile'; S.fam.Value = 'IPN';
S.prof.Items = cellstr(app.DM.listProfiles('IPN'));
S.prof.Value = 'IPN 200';
app.useSectionForBeam();
p = app.DM.getProfile('IPN', 'IPN 200');
verifyEqual(testCase, app.H.Fla.Iy.Value, p.Iy * 1e12, 'RelTol', 1e-9);
verifyEqual(testCase, app.H.Beam.S.Value, p.S * 1e6, 'RelTol', 1e-9);
end

function testBeamConsole(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres', 'console');
app.H.Beam.shear.Value = false;
app.computeBeam();
R = app.Results.beam;
F = 10e3; L = 3;
E = 190e9; Iz = app.H.Beam.Iz.Value * 1e-12;
verifyEqual(testCase, R.sol.reactions(1).Ry, F, 'RelTol', 1e-9);
verifyEqual(testCase, R.sol.reactions(1).Mz, F * L, 'RelTol', 1e-9);
verifyEqual(testCase, BeamAndTrussSolver.ppEval(R.sol.Mfz, 0), -F * L, 'RelTol', 1e-9);
verifyEqual(testCase, R.defl.integration.fmax, F * L^3 / (3 * E * Iz), 'RelTol', 1e-6);
% point le plus sollicité à l'encastrement : σ = |Mfz|·vy/Iz
verifyEqual(testCase, R.check.s, 0, 'AbsTol', 1e-12);
verifyEqual(testCase, abs(R.check.sigma), F * L * 0.150 / Iz, 'RelTol', 1e-6);
T = app.H.Beam.W.Tables.Reac.Data;
verifyEqual(testCase, T.('Ry (kN)')(1), 10, 'RelTol', 1e-9);
verifyEqual(testCase, height(app.H.Beam.W.Tables.Eq.Data), numel(R.sol.equations));
% envoi au tenseur
app.sendToTensor();
verifyEqual(testCase, app.H.Ten.sig.Data(1, 1), R.check.sigma / 1e6, 'RelTol', 1e-12);
verifyEqual(testCase, app.Results.tensor.criteria.sigmaEqVM, abs(R.check.sigma), 'RelTol', 1e-9);
verifyEqual(testCase, app.TabGroup.SelectedTab.Title, 'Tenseurs & Critères');
verifyEqual(testCase, app.FormulaKey, 'tenseurs');
end

function testBeamHyperstatic(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres', 'hyperstatique');
app.computeBeam();
R = app.Results.beam;
q = 10e3; L = 5;
verifyEqual(testCase, R.sol.h.xy, 1);
verifyEqual(testCase, R.sol.reactions(2).Ry, 3 * q * L / 8, 'RelTol', 1e-9);
verifyEqual(testCase, BeamAndTrussSolver.ppEval(R.sol.Mfz, 0), -q * L^2 / 8, 'RelTol', 1e-9);
verifyGreaterThanOrEqual(testCase, height(app.H.Beam.W.Tables.Defl.Data), 4);
end

function testTruss(testCase)
app = testCase.TestData.app;
app.loadExample('Treillis');
app.computeTruss();
t = app.Results.truss.tsol;
verifyTrue(testCase, logical(t.isostatic));
verifyEqual(testCase, sum(t.reactions(:, 2)), 40e3, 'RelTol', 1e-9);
verifyEqual(testCase, sum(t.reactions(:, 1)), -5e3, 'RelTol', 1e-9);
verifyEqual(testCase, height(app.H.Tr.W.Tables.Bars.Data), 7);
end

function testTractionValues(testCase)
app = testCase.TestData.app;
app.loadExample('Traction');
app.computeTraction();
r = app.Results.traction;
T = app.H.Tra;
N = 50e3; S0 = T.S0.Value * 1e-6; E = T.E.Value * 1e9;
verifyEqual(testCase, r.dL.analytique, N * 1 / (E * S0), 'RelTol', 1e-12);
verifyEqual(testCase, r.dL.integrale, N * 1 / (E * S0), 'RelTol', 1e-6);
% barre conique d1 = 20 mm → d2 = 30 mm : ΔL = 4 F L/(π E d1 d2)
app.loadExample('Traction', 'variable');
app.computeTraction();
r = app.Results.traction;
verifyEqual(testCase, r.dL.integrale, 4 * N * 1 / (pi * E * 0.020 * 0.030), 'RelTol', 1e-6);
verifyEqual(testCase, r.dL.energetique, 4 * N * 1 / (pi * E * 0.020 * 0.030), 'RelTol', 1e-6);
end

function testTorsionAndBuckling(testCase)
app = testCase.TestData.app;
app.loadExample('Torsion');
app.computeTorsion();
r = app.Results.torsion;
G = app.H.Tor.G.Value * 1e9;
Ix = pi * 0.040^4 / 32;
verifyEqual(testCase, r.phi.analytique, 500 * 1 / (G * Ix), 'RelTol', 1e-12);
verifyEqual(testCase, r.tauMax, 500 * 0.020 / Ix, 'RelTol', 1e-12);
app.loadExample('Flambage');
app.computeBuckling();
b = app.Results.buckling.analysis;
F = app.H.Fla;
Imin = min(F.Iz.Value, F.Iy.Value) * 1e-12;
verifyEqual(testCase, b.PE, pi^2 * F.E.Value * 1e9 * Imin / 4^2, 'RelTol', 1e-9);
end

function testHookeAndGauges(testCase)
app = testCase.TestData.app;
app.loadExample('Hooke', 'planeStress');
app.computeHooke();
K = app.H.Hoo;
E = K.E.Value * 1e9; nu = K.nu.Value;
verifyEqual(testCase, app.Results.hooke.exx, (100e6 - nu * 50e6) / E, 'RelTol', 1e-12);
app.loadExample('Jauges');
app.computeGauges();
ro = app.Results.gauges.rosette;
verifyEqual(testCase, ro.exy, 250e-6 - (400e-6 - 120e-6) / 2, 'RelTol', 1e-12);
end

function testFormulaFollowsTabs(testCase)
app = testCase.TestData.app;
cases = {'Base de données', 'materiaux'; 'Sections', 'geometrie'; 'Poutres', 'equilibre'; ...
    'Treillis', 'treillis'; 'Traction', 'traction'; 'Cisaillement', 'cisaillement'; 'Torsion', 'torsion'; ...
    'Flexion', 'flexion'; 'Flambage', 'flambage'; 'Tenseurs', 'tenseurs'; 'Hooke', 'hooke'; ...
    'Jauges', 'extensometrie'};
for k = 1:size(cases, 1)
    app.selectTab(cases{k, 1});
    verifyEqual(testCase, app.FormulaKey, cases{k, 2}, cases{k, 1});
end
app.selectTab('Poutres', 3);
verifyEqual(testCase, app.FormulaKey, 'deformee');
app.selectTab('Tenseurs', 3);
verifyEqual(testCase, app.FormulaKey, 'criteres');
app.showFormula('energie');
verifyEqual(testCase, app.FormulaKey, 'energie');
end

function testParseFunction(testCase)
f = MecaStruct_App.parseFunction('pi/4*(20 + 10*x)^2');
x = [0 0.5 1];
verifyEqual(testCase, f(x), pi / 4 * (20 + 10 * x).^2, 'RelTol', 1e-14);
g = MecaStruct_App.parseFunction('1.5e2');
verifyEqual(testCase, g([1 2 3]), [150 150 150]);
h = MecaStruct_App.parseFunction('sqrt(x) + exp(-x/2)*cos(x)');
verifyEqual(testCase, h(4), 2 + exp(-2) * cos(4), 'RelTol', 1e-14);
bad = {'system(''dir'')', 'exit', 'x; delete(1)', '[x x]', 'eval(x)', '@(x) x', 'e', 'x == 1', '', 'sin(x'};
for k = 1:numel(bad)
    verifyError(testCase, @() MecaStruct_App.parseFunction(bad{k}), 'MecaStruct:App:invalidExpression', bad{k});
end
end

function testCallbackErrorIsLogged(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres');
B = app.H.Beam;
B.sup.Data = cell(0, 3);
n0 = numel(app.ErrorLog);
B.btnCalc.ButtonPushedFcn(B.btnCalc, []);
verifyEqual(testCase, numel(app.ErrorLog), n0 + 1, 'Une poutre sans appui doit être signalée.');
verifyTrue(testCase, contains(app.ErrorLog{end}, 'Poutres'));
verifyError(testCase, @() app.loadExample('Inconnu'), 'MecaStruct:App:unknownTab');
app.loadExample('Poutres');
end

function testUserDataRoundTrip(testCase)
app = testCase.TestData.app;
D = app.H.DB;
D.mName.Value = 'Acier test app';
D.mCat.Value = 'Utilisateur';
D.mE.Value = 200; D.mNu.Value = 0.25; D.mG.Value = 0;
D.mRe.Value = 300; D.mRm.Value = 450; D.mAlpha.Value = 12; D.mRho.Value = 7800;
D.mAuthor.Value = 'Théo';
app.addMaterialFromForm();
m = app.DM.getMaterial('Acier test app');
verifyEqual(testCase, m.Author, 'Théo');
verifyTrue(testCase, any(strcmp(D.mAuthor.Items, 'Théo')), 'Le nom saisi est proposé ensuite dans la liste.');
verifyEqual(testCase, string(app.H.DB.MatTable.Data.("Ajouté par")(strcmp(app.H.DB.MatTable.Data.Nom, "Acier test app"))), "Théo");
verifyEqual(testCase, m.G, 200e9 / (2 * 1.25), 'RelTol', 1e-12);
verifyEqual(testCase, m.Re, 300e6, 'RelTol', 1e-12);
verifyTrue(testCase, any(strcmp(app.H.Beam.mat.Items, 'Acier test app')));
D.pFam.Value = 'IPE';
D.pName.Value = 'IPE 999';
D.ph.Value = 210; D.pb.Value = 105; D.pa.Value = 6; D.pe.Value = 9; D.pr.Value = 0;
app.addProfileFromForm();
p = app.DM.getProfile('IPE', 'IPE 999');
verifyEqual(testCase, p.h, 0.210, 'RelTol', 1e-12);
f = fullfile(testCase.TestData.tmp, 'roundtrip.mat');
app.saveUserData(f);
verifyTrue(testCase, isfile(f));
dm2 = DataManager(f);
verifyEqual(testCase, dm2.getMaterial('Acier test app').E, 200e9, 'RelTol', 1e-12);
verifyEqual(testCase, dm2.getProfile('IPE', 'IPE 999').b, 0.105, 'RelTol', 1e-12);
app.loadUserData(f);
verifyTrue(testCase, any(app.DM.Materials.IsUser));
end

function testExport(testCase)
app = testCase.TestData.app;
app.loadExample('Sections');
app.computeSection();
app.selectTab('Sections', 1);
f1 = fullfile(testCase.TestData.tmp, 'section.png');
app.exportCurrentPlot('Sections', f1);
verifyTrue(testCase, isfile(f1));
app.loadExample('Poutres');
app.computeBeam();
app.selectTab('Poutres', 2);
f2 = fullfile(testCase.TestData.tmp, 'diagrammes.png');
app.exportCurrentPlot('Poutres', f2);
verifyTrue(testCase, isfile(f2));
app.loadExample('Base de données');
app.computeKt();
f3 = fullfile(testCase.TestData.tmp, 'kt.pdf');
app.exportCurrentPlot('Base de données', f3);
verifyTrue(testCase, isfile(f3));
d = dir(f3);
verifyGreaterThan(testCase, d.bytes, 1000);
end

%% ------------------------------------------------------------------------------------------
function testInfoSectionPoutre(testCase)
% bandeau « Section utilisée » de l'onglet Poutres et fenêtre « Voir la section »
app = testCase.TestData.app;
B = app.H.Beam;
app.loadExample('Poutres');
verifyTrue(testCase, contains(B.secInfo.Text, 'IPE 300'));
S = app.H.Sec;
S.type.Value = 'disque'; S.D.Value = 60;
app.useSectionForBeam();
verifyTrue(testCase, contains(B.secInfo.Text, 'disque'));
verifyTrue(testCase, contains(app.H.Fla.secInfo.Text, 'disque'));
fig = app.showBeamSection();
verifyTrue(testCase, isvalid(fig));
delete(fig);
B.ky.Value = 2; B.ky.ValueChangedFcn([], []);
verifyTrue(testCase, contains(B.secInfo.Text, 'main'));
verifyEmpty(testCase, app.showBeamSection());
end

%% ------------------------------------------------------------------------------------------
%  Ressorts, tassements, rotules, température, charge mobile, historique, catalogue, formats
%% ------------------------------------------------------------------------------------------
function testRessortsTassementsRotules(testCase)
app = testCase.TestData.app;
B = app.H.Beam;
% poutre Gerber : isostatique, moment nul à la rotule, contrôle écrit dans le dossier
app.loadExample('Poutres', 'gerber');
app.computeBeam();
sol = app.Results.beam.sol;
verifyEqual(testCase, [sol.reactions.Ry], [10e3 60e3 10e3], 'RelTol', 1e-9);
setenv('MECASTRUCT_NO_BROWSER', '1');
cl = onCleanup(@() setenv('MECASTRUCT_NO_BROWSER', ''));
f = ValidationReport.generate(app, 'Beam', fullfile(testCase.TestData.tmp, 'gerber'));
h = fileread(f);
verifyTrue(testCase, contains(h, 'à la rotule R1'), 'Le dossier contrôle le moment nul à la rotule.');
verifyFalse(testCase, contains(h, 'ÉCART'), 'Aucun écart dans le dossier de la poutre Gerber.');
% tassement de 10 mm de B : les deux méthodes concordent et l'appui est déchargé
app.loadExample('Poutres', 'tassement');
app.computeBeam();
s1 = app.Results.beam.sol;
verifyLessThan(testCase, s1.hyperCheck, 1e-9);
B.supx.Data = cell(0, 5);
app.computeBeam();
s0 = app.Results.beam.sol;
verifyLessThan(testCase, s1.reactions(2).Ry, s0.reactions(2).Ry, 'Le tassement de B décharge cet appui.');
% ressort et gradient thermique via les champs de saisie
app.loadExample('Poutres', 'hyperstatique');
B.supx.Data = {'B', 5000, 0, 0, 0};
app.computeBeam();
verifyEqual(testCase, app.Results.beam.sol.model.supports(2).spring, 5e6, 'RelTol', 1e-12);
B.supx.Data = cell(0, 5);
B.thGy.Value = 20;
app.computeBeam();
verifyEqual(testCase, app.Results.beam.sol.model.thermal.kv, -12e-6 * 20 / (2 * B.vy.Value * 1e-3), 'RelTol', 1e-12);
B.thGy.Value = 0;
B.supx.Data = {'Z', 0, 0, 0, 0};
verifyError(testCase, @() app.computeBeam(), 'MecaStruct:App:invalidInput');
B.supx.Data = cell(0, 5);
% fichier de problème d'une version sans ces champs : les champs MSv2 sont absents du fichier
app.loadExample('Poutres', 'isostatique');
f = fullfile(testCase.TestData.tmp, 'ancien.mat');
app.saveProblem('Beam', f);
S = load(f);
vals = S.problem.values;
v = findobj(B.W.In, '-property', 'Value');
v = v(~arrayfun(@(x) isa(x, 'matlab.ui.control.TextArea'), v));
widgets = [v(:); findobj(B.W.In, 'Type', 'uitable')];
isNew = arrayfun(@(x) strcmp(x.Tag, 'MSv2'), widgets);
verifyGreaterThan(testCase, nnz(isNew), 5);
verifyEqual(testCase, numel(widgets), size(vals, 1));
problem = struct('app', 'MecaStruct', 'key', 'Beam', 'values', {vals(~isNew, 1:2)}); %#ok<NASGU>
save(f, 'problem');
verifyEqual(testCase, app.loadProblem('Beam', f), 0, 'Un ancien fichier se recharge.');
end

function testResultatNonFiable(testCase)
% Poutre hyperstatique avec Iyz ≠ 0 : « Calculer » demande ; « Non » n'affiche aucun résultat, « Oui » l'affiche.
app = testCase.TestData.app;
B = app.H.Beam;
app.loadExample('Poutres', 'hyperstatique');
B.Iyz.Value = -1.066e6;   % le chargement d'exemple remet Iyz à 0 : on le remet pour cet essai
app.Results = struct();
app.ConfirmFcn = @(varargin) 'Non';
app.computeBeam(true);
verifyFalse(testCase, isfield(app.Results, 'beam'), 'Non : aucun résultat affiché.');
verifyTrue(testCase, contains(B.W.Status.Text, 'non affiché'));
app.ConfirmFcn = @(varargin) 'Oui, afficher';
app.computeBeam(true);
verifyTrue(testCase, isfield(app.Results, 'beam'), 'Oui : le résultat est affiché, avec la limite signalée.');
app.ConfirmFcn = @uiconfirm;
end

function testRestaurationParCle(testCase)
% Un champ dont le libellé n'existe plus dans l'application est compté comme non restauré, sans toucher aux autres.
app = testCase.TestData.app;
B = app.H.Beam;
f = fullfile(testCase.TestData.tmp, 'cle.mat');
B.L.Value = 7.5;
app.saveProblem('Beam', f);
S = load(f);
problem = S.problem;
problem.values(strcmp(problem.values(:, 3), B.L.UserData), 3) = {'libellé supprimé'};
save(f, 'problem');
B.L.Value = 3;
verifyEqual(testCase, app.loadProblem('Beam', f), 1, 'Le champ au libellé inconnu est compté.');
verifyEqual(testCase, B.L.Value, 3, 'Il n''est pas restauré.');
end

function testHistoriqueEtSchema(testCase)
app = testCase.TestData.app;
B = app.H.Beam;
app.loadExample('Poutres', 'isostatique');
n0 = size(B.pl.Data, 1);
app.onSchematicClick(2.5, 'force');
verifyEqual(testCase, size(B.pl.Data, 1), n0 + 1, 'Un clic sur le schéma ajoute une force.');
app.onSchematicClick(3, 'rotule');
verifyEqual(testCase, size(B.hg.Data, 1), 1);
app.onSchematicClick(1, 'appui');
verifyEqual(testCase, size(B.sup.Data, 1), 3);
app.undoBeam(-1);
verifyEqual(testCase, size(B.sup.Data, 1), 2, 'Annuler retire l''appui ajouté.');
app.undoBeam(-1);
verifyEqual(testCase, size(B.hg.Data, 1), 0);
app.undoBeam(1);
verifyEqual(testCase, size(B.hg.Data, 1), 1, 'Rétablir remet la rotule.');
verifyError(testCase, @() app.onSchematicClick(1, 'poutre'), 'MecaStruct:App:invalidInput');
app.loadExample('Poutres', 'isostatique');
app.undoBeam(-1);
verifyTrue(testCase, contains(B.W.Status.Text, 'Rien à annuler'), 'L''historique repart à zéro après un exemple.');
app.computeBeam();
verifyNotEmpty(testCase, B.W.Axes{1}(1).ButtonDownFcn, 'Le schéma reste cliquable après un calcul.');
end

function testChargeMobile(testCase)
app = testCase.TestData.app;
B = app.H.Beam;
app.loadExample('Poutres', 'isostatique');
B.L.Value = 6;
B.sup.Data = {0, 'pivot', 'A'; 6, 'appui_simple', 'B'};
B.pl.Data = cell(0, 6);
B.dl.Data = cell(0, 7);
B.mvP.Value = '-100 -100';
B.mvE.Value = '1.5';
B.mvN.Value = 241;
[T, env] = app.computeMovingLoad();
% référence statique : moment maximal sous un essieu
P = 100e3; e = 1.5; L = 6; best = 0;
for x = linspace(0, L - e, 20001)
    RB = P * (2 * x + e) / L;
    RA = 2 * P - RB;
    best = max([best, RA * x, RA * (x + e) - P * e]);
end
verifyEqual(testCase, env.extrema.Mmax, best, 'RelTol', 1e-6);
verifyEqual(testCase, env.Rmax, [175e3 175e3], 'RelTol', 1e-9);
verifyEqual(testCase, height(T), 101);
verifyEqual(testCase, max(T.("Mfz max (kN·m)")), best / 1e3, 'RelTol', 5e-3);
B.mvN.Value = 2;   % grille grossière : les positions critiques donnent le même maximum
[~, env2] = app.computeMovingLoad();
verifyEqual(testCase, env2.extrema.Mmax, best, 'RelTol', 1e-6);
B.mvN.Value = 241;
B.mvE.Value = '1 2';
verifyError(testCase, @() app.computeMovingLoad(), 'MecaStruct:App:invalidInput');
B.mvE.Value = '1.5';
B.mvP.Value = '-100';
[~, env1] = app.computeMovingLoad();
verifyEqual(testCase, env1.extrema.Mmax, P * L / 4, 'RelTol', 1e-4, 'Une charge : PL/4.');
app.loadExample('Poutres', 'isostatique');
end

function testCatalogueTubesEtMateriaux(testCase)
app = testCase.TestData.app;
S = app.H.Sec;
P = DataManager.sectionPresets();
verifyGreaterThan(testCase, numel(P), 30);
% carré 100x100x5 : A = 100² − 90² (angles vifs)
S.preset.Value = 'SHS 100x100x5';
app.applySectionPreset();
verifyEqual(testCase, S.type.Value, 'rectangle_creux');
app.computeSection();
verifyEqual(testCase, app.Results.section.P.S, 1900e-6, 'RelTol', 1e-9);
for k = 1:numel(P)   % tous les gabarits donnent une section valide
    S.preset.Value = P(k).name;
    app.applySectionPreset();
    app.computeSection();
    verifyGreaterThan(testCase, app.Results.section.P.S, 0, P(k).name);
end
app.loadExample('Sections');
dm = app.DM;
for nm = ["Bois C24 (EN 338)", "Lamellé-collé GL24h (EN 14080)", "Béton C25/30 (EN 1992-1-1)", "Béton C30/37 (EN 1992-1-1)"]
    m = dm.getMaterial(nm);
    verifyGreaterThan(testCase, m.E, 1e9, char(nm));
end
verifyEqual(testCase, dm.getMaterial('Béton C25/30 (EN 1992-1-1)').E, 31e9);
verifyEqual(testCase, dm.getMaterial('Bois C24 (EN 338)').E, 11e9);
end

function testFormatDuDossier(testCase)
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
setenv('MECASTRUCT_NO_BROWSER', '1');
cl = onCleanup(@() setenv('MECASTRUCT_NO_BROWSER', ''));
verifyError(testCase, @() ValidationReport.generate(app, 'Beam', testCase.TestData.tmp, 'docx'), 'MecaStruct:Validation:format');
f = app.exportValidation('Beam', fullfile(testCase.TestData.tmp, 'fmt'));
verifyTrue(testCase, endsWith(f, '.html'), 'Format par défaut : HTML.');
if isempty(ValidationReport.findBrowser())
    return
end
fp = app.exportValidation('Beam', fullfile(testCase.TestData.tmp, 'fmt'), 'pdf');
verifyTrue(testCase, endsWith(fp, '.pdf') && isfile(fp));
fid = fopen(fp, 'r');
head = fread(fid, 5, '*char').';
fclose(fid);
verifyEqual(testCase, head, '%PDF-');
end
