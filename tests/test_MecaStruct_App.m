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
verifyEqual(testCase, titles, {'Base de données', 'Sections', 'Poutres', 'Treillis', 'Sollicitations', ...
    'Flambage', 'Tenseurs & Critères', 'Hooke & Jauges', 'Convertisseur'});
verifyEqual(testCase, numel(app.H.Tra.Tab.Parent.Children), 4, 'Sous-onglets de Sollicitations.');
verifyTrue(testCase, ismember(app.FormulaKey, DataManager.formulaKeys()));
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
% saisies de la poutre modifiées sans recalcul : « Lire en s » relit la poutre à jour
app.H.Beam.dl.Data = {0, 6, 'y', 'uniforme', '-20', 'q'};
F.s0.Value = 3;
app.loadFromBeam('Fle', 'abscisse');
verifyEqual(testCase, F.Mfz.Value, 110, 'AbsTol', 1e-9);              % 73,33·3 − 20·9/2 − 20·1
S.s0.Value = 99;
verifyError(testCase, @() app.loadFromBeam('Sec', 'abscisse'), 'MecaStruct:App:invalidInput');
end

function testPointLePlusSollicitSurSaut(testCase)
% couple de 20 kN·m en s = 4 sur 6 m : Mfz saute de −13,33 à +6,67 ; « Point le plus sollicité » doit
% lire 13,33 kN·m (côté retenu par la vérification), pas la limite à droite
app = testCase.TestData.app;
app.loadExample('Poutres', 'isostatique');
B = app.H.Beam;
B.pl.Data = cell(0, 5);
B.dl.Data = cell(0, 6);
B.pm.Data = {4, 0, 0, 20, 'C'};
app.loadFromBeam('Fle', 'max');
verifyEqual(testCase, abs(app.H.Fle.Mfz.Value), 20 * 4 / 6, 'AbsTol', 1e-6);
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
app.addMaterialFromForm();
m = app.DM.getMaterial('Acier test app');
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
