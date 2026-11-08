function tests = test_DataManager
%TEST_DATAMANAGER Tests unitaires du module DataManager (§1 et §9 de ARCHITECTURE.md).
%   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
%   Les tests n'écrivent jamais dans le dossier userdata réel : tous les fichiers utilisateur
%   sont créés dans tempdir.
tests = functiontests(localfunctions);
end

%% ---------------------------------------------------------------------------------------------
%  Fixtures
%  ---------------------------------------------------------------------------------------------

function setup(tc)
% Base neuve, fichier utilisateur inexistant dans un dossier temporaire.
tc.TestData.dir = tempname;
mkdir(tc.TestData.dir);
tc.TestData.file = fullfile(tc.TestData.dir, 'userdb.mat');
tc.TestData.dm = DataManager(tc.TestData.file);
end

function teardown(tc)
if isfolder(tc.TestData.dir)
    rmdir(tc.TestData.dir, 's');
end
end

%% ---------------------------------------------------------------------------------------------
%  Construction et propriétés
%  ---------------------------------------------------------------------------------------------

function testConstructionDefaults(tc)
dm = tc.TestData.dm;
tc.verifyClass(dm, 'DataManager');
tc.verifyTrue(isa(dm, 'handle'));
tc.verifyEqual(dm.UserFile, tc.TestData.file);
tc.verifyTrue(istable(dm.Materials));
tc.verifyTrue(all(ismember({'Name','Category','E','G','nu','Re','Rm','alpha','rho','Note','IsUser'}, ...
    dm.Materials.Properties.VariableNames)));
tc.verifyClass(dm.Materials.Name, 'string');
tc.verifyClass(dm.Materials.IsUser, 'logical');
tc.verifyFalse(any(dm.Materials.IsUser));
tc.verifyTrue(isstruct(dm.Profiles));
tc.verifyTrue(istable(dm.BearingPressures));
tc.verifyFalse(isfile(tc.TestData.file));
end

function testDefaultUserFilePath(tc)
f = DataManager.defaultUserFile();
[folder, name, ext] = fileparts(f);
tc.verifyEqual([name ext], 'MecaStruct_UserDB.mat');
[~, last] = fileparts(folder);
tc.verifyEqual(last, 'userdata');
tc.verifyEqual(fileparts(folder), fileparts(which('DataManager')));
end

function testHasSymbolic(tc)
tf = DataManager.hasSymbolic();
tc.verifyClass(tf, 'logical');
tc.verifyTrue(isscalar(tf));
tc.verifyEqual(tf, logical(license('test', 'Symbolic_Toolbox')) && ~isempty(ver('symbolic')));
end

%% ---------------------------------------------------------------------------------------------
%  Matériaux
%  ---------------------------------------------------------------------------------------------

function testMaterialsCourseValues(tc)
dm = tc.TestData.dm;
names = dm.listMaterials();
tc.verifyClass(names, 'string');
tc.verifyEqual(size(names, 2), 1);
% Aciers d'usage général
ag = {'S185', 185, 290; 'S235', 235, 340; 'S275', 275, 410; 'S355', 355, 490};
for k = 1:size(ag, 1)
    m = dm.getMaterial(ag{k, 1});
    tc.verifyEqual(m.E, 190e9);
    tc.verifyEqual(m.nu, 0.3);
    tc.verifyEqual(m.Re, ag{k, 2}*1e6);
    tc.verifyEqual(m.Rm, ag{k, 3}*1e6);
    tc.verifyEqual(m.alpha, 12e-6, 'RelTol', 1e-12);
    tc.verifyEqual(m.G, 190e9/2.6, 'RelTol', 1e-12);
end
% Aciers de construction mécanique
for nm = ["XC 38", "XC 42", "XC 48"]
    m = dm.getMaterial(nm);
    tc.verifyEqual(m.E, 210e9);
    tc.verifyEqual(m.G, 80e9);
    tc.verifyEqual(m.nu, 0.3);
    tc.verifyEqual(m.alpha, 11e-6, 'RelTol', 1e-12);
    tc.verifyTrue(contains(m.Note, '12,5'));
    tc.verifyTrue(contains(m.Note, 'usuelle'));
    tc.verifyGreaterThan(m.Rm, m.Re);
end
% Aluminium
m = dm.getMaterial('Aluminium 5356');
tc.verifyEqual([m.E m.G m.Re m.Rm], [70e9 27e9 200e6 300e6]);
tc.verifyTrue(contains(m.Note, '90 GPa'));
tc.verifyTrue(m.alpha >= 22.5e-6 && m.alpha <= 24e-6);
% Aluminium 2017 : fiche Euralliage 2017A, T4
m = dm.getMaterial('Aluminium 2017');
tc.verifyEqual([m.E m.G m.Re m.Rm m.rho], [72.5e9 27.2e9 260e6 380e6 2790]);
tc.verifyTrue(contains(m.Note, 'Euralliage'));
tc.verifyTrue(m.alpha >= 22.5e-6 && m.alpha <= 24e-6);
% Euralliage : valeurs de la fiche et valeurs usuelles signalées
m = dm.getMaterial('Aluminium 6061-T6');
tc.verifyEqual([m.E m.G m.Re m.Rm m.rho], [70e9 26.3e9 240e6 290e6 2700]);
m = dm.getMaterial('Aluminium 7075-T6');
tc.verifyEqual([m.Re m.Rm m.rho], [460e6 520e6 2810]);
m = dm.getMaterial('Bronze CuSn8 R450 (CW453K)');
tc.verifyEqual([m.Re m.Rm m.rho], [280e6 450e6 8800]);
tc.verifyTrue(contains(m.Note, 'valeurs usuelles'));
tc.verifyGreaterThan(sum(contains(string(dm.Materials.Note), 'Euralliage')), 25);
% Titane TA6V
m = dm.getMaterial('Titane TA6V');
tc.verifyEqual([m.E m.Re m.Rm], [116e9 830e6 900e6]);
tc.verifyTrue(contains(m.Note, '100 à 120'));
tc.verifyTrue(contains(m.Note, '950'));
tc.verifyTrue(m.alpha >= 8.5e-6 && m.alpha <= 9.5e-6);
% Fontes, laiton, Plexiglas
tc.verifyEqual(dm.getMaterial('FGL 250').G, 40e9);
tc.verifyEqual(dm.getMaterial('FGS 400-15').G, 40e9);
tc.verifyEqual(dm.getMaterial('Laiton CuZn39Pb3').G, 34e9);
pm = dm.getMaterial('Plexiglas');
tc.verifyEqual(pm.G, 1.1e9);
tc.verifyTrue(contains(pm.Note, '11 GPa'));
end

function testMaterialsGlobalConsistency(tc)
T = tc.TestData.dm.Materials;
tc.verifyTrue(all(isfinite([T.E; T.G; T.nu; T.Re; T.Rm; T.alpha; T.rho])));
tc.verifyTrue(all(T.nu > -1 & T.nu < 0.5));
tc.verifyTrue(all(T.Rm >= T.Re));
tc.verifyTrue(all(T.E > 1e9 & T.E < 300e9));     % SI strict (Pa)
for k = 1:height(T)
    Gth = T.E(k)/(2*(1 + T.nu(k)));
    gap = abs(T.G(k) - Gth)/Gth;
    if contains(T.Note(k), 'G calculé') || contains(T.Note(k), 'déduit')
        tc.verifyEqual(T.G(k), Gth, 'RelTol', 1e-12, char(T.Name(k)));
    end
    if gap > 0.05
        tc.verifyTrue(contains(T.Note(k), 'cohérence'), char(T.Name(k)));
    end
end
end

function testGetMaterialStructAndErrors(tc)
dm = tc.TestData.dm;
m = dm.getMaterial('xc38');
tc.verifyEqual(m.Name, 'XC 38');
tc.verifyTrue(all(isfield(m, {'Name','Category','E','G','nu','Re','Rm','alpha','rho','Note'})));
tc.verifyError(@() dm.getMaterial('Unobtainium'), 'MecaStruct:DataManager:unknownMaterial');
end

function testCompleteIsotropic(tc)
m = DataManager.completeIsotropic(struct('E', 200e9, 'nu', 0.25));
tc.verifyEqual(m.G, 80e9, 'RelTol', 1e-12);
m = DataManager.completeIsotropic(struct('E', 210e9, 'G', 80e9, 'nu', NaN));
tc.verifyEqual(m.nu, 210/160 - 1, 'RelTol', 1e-12);
m = DataManager.completeIsotropic(struct('G', 80e9, 'nu', 0.3));
tc.verifyEqual(m.E, 208e9, 'RelTol', 1e-12);
m = DataManager.completeIsotropic(struct('E', 200e9, 'G', 50e9, 'nu', 0.3));
tc.verifyTrue(contains(m.Note, 'cohérence'));
m = DataManager.completeIsotropic(struct('E', 200e9));
tc.verifyTrue(isnan(m.G) && isnan(m.nu));
tc.verifyError(@() DataManager.completeIsotropic(struct('E', 200e9, 'nu', 0.6)), ...
    'MecaStruct:DataManager:invalidNu');
tc.verifyError(@() DataManager.completeIsotropic(struct('E', 100e9, 'G', 20e9)), ...
    'MecaStruct:DataManager:invalidNu');
tc.verifyError(@() DataManager.completeIsotropic(struct('E', -1, 'nu', 0.3)), ...
    'MecaStruct:DataManager:invalidModulus');
end

function testAddRemoveMaterial(tc)
dm = tc.TestData.dm;
n0 = height(dm.Materials);
dm.addMaterial(struct('Name', 'Mon acier', 'E', 200e9, 'nu', 0.3, 'Re', 300e6, 'Rm', 450e6));
tc.verifyEqual(height(dm.Materials), n0 + 1);
m = dm.getMaterial('Mon acier');
tc.verifyEqual(m.G, 200e9/2.6, 'RelTol', 1e-12);
tc.verifyTrue(m.IsUser);
tc.verifyEqual(m.Author, 'Utilisateur');
tc.verifyEqual(dm.getMaterial('S235').Author, 'Base fournie');
dm.addMaterial(struct('Name', 'Acier de Théo', 'E', 200e9, 'nu', 0.3, 'Author', ' Théo '));
tc.verifyEqual(dm.getMaterial('Acier de Théo').Author, 'Théo');
dm.removeMaterial('Acier de Théo');
% Remplacement d'un matériau utilisateur de même nom
dm.addMaterial(struct('Name', 'mon  ACIER', 'E', 210e9, 'nu', 0.3));
tc.verifyEqual(height(dm.Materials), n0 + 1);
tc.verifyEqual(dm.getMaterial('Mon acier').E, 210e9);
% Surcharge d'un matériau par défaut puis restauration
dm.addMaterial(struct('Name', 'S235', 'E', 200e9, 'nu', 0.3, 'Re', 240e6, 'Rm', 360e6));
tc.verifyEqual(dm.getMaterial('S235').E, 200e9);
dm.removeMaterial('S235');
tc.verifyEqual(dm.getMaterial('S235').E, 190e9);
tc.verifyFalse(dm.getMaterial('S235').IsUser);
dm.removeMaterial('Mon acier');
tc.verifyEqual(height(dm.Materials), n0);
tc.verifyError(@() dm.removeMaterial('S355'), 'MecaStruct:DataManager:notUserMaterial');
tc.verifyError(@() dm.removeMaterial('Inconnu'), 'MecaStruct:DataManager:unknownMaterial');
tc.verifyError(@() dm.addMaterial(struct('E', 1e9)), 'MecaStruct:DataManager:invalidMaterial');
end

%% ---------------------------------------------------------------------------------------------
%  Profilés
%  ---------------------------------------------------------------------------------------------

function testProfileCatalogContents(tc)
dm = tc.TestData.dm;
tc.verifyEqual(dm.listProfileFamilies(), ["IPN","IPE","HEA","HEB","UPN","UAP"]);
expected = struct( ...
    'IPN', 80:20:300, ...
    'IPE', [80 100 120 140 160 180 200 220 240 270 300 330 360 400 450 500 550 600], ...
    'HEA', [100:20:360 400:50:600], ...
    'HEB', [100:20:360 400:50:600], ...
    'UPN', 80:20:300, ...
    'UAP', [80 100 130 150 175 200 220 250 300]);
fams = fieldnames(expected);
for i = 1:numel(fams)
    names = dm.listProfiles(fams{i});
    tc.verifyClass(names, 'string');
    tc.verifyEqual(names, compose("%s %d", string(fams{i}), expected.(fams{i})(:)), fams{i});
end
end

function testProfileConsistency(tc)
P = tc.TestData.dm.Profiles;
fams = {'IPN','IPE','HEA','HEB','UPN','UAP'};
vars = {'Name','h','b','a','e','r','S','Iz','Iy','Wz','Wy','rz','ry','mass','c','IsUser'};
for i = 1:numel(fams)
    T = P.(fams{i});
    tc.verifyTrue(all(ismember(vars, T.Properties.VariableNames)), fams{i});
    isU = any(strcmp(fams{i}, {'UPN','UAP'}));
    for k = 1:height(T)
        r = T(k, :);
        lab = char(r.Name);
        % SI strict
        tc.verifyTrue(r.h > 0.05 && r.h < 0.7 && r.b > 0.03 && r.b < 0.31 && r.S < 0.05, lab);
        tc.verifyGreaterThan(r.Iz, r.Iy, lab);
        tc.verifyEqual(r.rz, sqrt(r.Iz/r.S), 'RelTol', 0.02, lab);
        tc.verifyEqual(r.ry, sqrt(r.Iy/r.S), 'RelTol', 0.02, lab);
        tc.verifyEqual(r.Wz, r.Iz/(r.h/2), 'RelTol', 0.02, lab);
        Sgeo = 2*r.b*r.e + (r.h - 2*r.e)*r.a;
        tc.verifyEqual(r.S, Sgeo, 'RelTol', 0.15, lab);
        tc.verifyEqual(r.mass, 7850*r.S, 'RelTol', 0.03, lab);
        if isU
            tc.verifyTrue(isfinite(r.c) && r.c > 0 && r.c < r.b/2, lab);
            tc.verifyEqual(r.Wy, r.Iy/(r.b - r.c), 'RelTol', 0.02, lab);
        else
            tc.verifyTrue(isnan(r.c), lab);
            tc.verifyEqual(r.Wy, r.Iy/(r.b/2), 'RelTol', 0.02, lab);
        end
        tc.verifyFalse(r.IsUser, lab);
    end
end
end

function testProfileReferenceValues(tc)
% Quelques valeurs de référence des tables européennes (Iz app = Iy Eurocode).
dm = tc.TestData.dm;
p = dm.getProfile('IPE', 'IPE 200');
tc.verifyEqual(p.Family, 'IPE');
tc.verifyEqual([p.h p.b p.a p.e], [0.200 0.100 0.0056 0.0085], 'RelTol', 1e-12);
tc.verifyEqual(p.S, 28.48e-4, 'RelTol', 1e-12);
tc.verifyEqual(p.Iz, 1943e-8, 'RelTol', 1e-12);
tc.verifyEqual(p.Iy, 142.4e-8, 'RelTol', 1e-12);
p = dm.getProfile('heb', 300);
tc.verifyEqual(p.Iz, 25170e-8, 'RelTol', 1e-12);
p = dm.getProfile('HEA', 'HEA200');
tc.verifyEqual(p.h, 0.190, 'RelTol', 1e-12);
p = dm.getProfile('UPN', "100");
tc.verifyEqual(p.c, 0.0155, 'RelTol', 1e-12);
tc.verifyTrue(all(isfield(p, {'Family','Name','h','b','a','e','r','S','Iz','Iy','Wz','Wy','rz','ry','mass','c'})));
tc.verifyError(@() dm.getProfile('IPE', 'IPE 210'), 'MecaStruct:DataManager:unknownProfile');
tc.verifyError(@() dm.getProfile('XYZ', 'IPE 200'), 'MecaStruct:DataManager:unknownFamily');
end

function testAddProfileComputesMissing(tc)
dm = tc.TestData.dm;
h = 0.2; b = 0.1; a = 0.006; e = 0.01;
dm.addProfile('IPE', struct('Name', '200 perso', 'h', h, 'b', b, 'a', a, 'e', e));
p = dm.getProfile('IPE', 'IPE 200 perso');
hw = h - 2*e;
S = 2*b*e + hw*a;
Iz = (b*h^3 - (b - a)*hw^3)/12;
Iy = (2*e*b^3 + hw*a^3)/12;
tc.verifyEqual(p.S, S, 'RelTol', 1e-12);
tc.verifyEqual(p.Iz, Iz, 'RelTol', 1e-12);
tc.verifyEqual(p.Iy, Iy, 'RelTol', 1e-12);
tc.verifyEqual(p.Wz, Iz/(h/2), 'RelTol', 1e-12);
tc.verifyEqual(p.Wy, Iy/(b/2), 'RelTol', 1e-12);
tc.verifyEqual(p.rz, sqrt(Iz/S), 'RelTol', 1e-12);
tc.verifyEqual(p.ry, sqrt(Iy/S), 'RelTol', 1e-12);
tc.verifyTrue(isnan(p.c));
tc.verifyTrue(p.IsUser);
% Profilé en U : c et Iy calculés autour du centre de gravité
dm.addProfile('UPN', struct('Name', 'UPN X', 'h', h, 'b', b, 'a', a, 'e', e));
q = dm.getProfile('UPN', 'UPN X');
cRef = (e*b^2 + hw*a^2/2)/S;
IyRef = 2*(e*b^3/12 + e*b*(b/2 - cRef)^2) + hw*a^3/12 + hw*a*(a/2 - cRef)^2;
tc.verifyEqual(q.c, cRef, 'RelTol', 1e-12);
tc.verifyEqual(q.Iy, IyRef, 'RelTol', 1e-12);
tc.verifyEqual(q.Wy, IyRef/max(cRef, b - cRef), 'RelTol', 1e-12);
% Valeurs fournies conservées
dm.addProfile('HEB', struct('Name', 'HEB 999', 'h', 1, 'b', 0.3, 'a', 0.02, 'e', 0.04, 'Iz', 1e-2));
tc.verifyEqual(dm.getProfile('HEB', 999).Iz, 1e-2);
dm.removeProfile('HEB', 999);
tc.verifyError(@() dm.getProfile('HEB', 999), 'MecaStruct:DataManager:unknownProfile');
tc.verifyError(@() dm.removeProfile('HEB', 300), 'MecaStruct:DataManager:notUserProfile');
tc.verifyError(@() dm.addProfile('IPE', struct('Name', 'bad', 'h', 0.1, 'b', 0.1, 'a', 0.01)), ...
    'MecaStruct:DataManager:invalidProfile');
tc.verifyError(@() dm.addProfile('IPE', struct('Name', 'bad', 'h', 0.02, 'b', 0.1, 'a', 0.01, 'e', 0.01)), ...
    'MecaStruct:DataManager:invalidProfile');
end

%% ---------------------------------------------------------------------------------------------
%  Unités
%  ---------------------------------------------------------------------------------------------

function testUnitsAllContractUnits(tc)
units = {'m',1; 'cm',1e-2; 'mm',1e-3; [char(181) 'm'],1e-6; 'um',1e-6; ...
    'm^2',1; 'cm^2',1e-4; 'mm^2',1e-6; 'm^3',1; 'cm^3',1e-6; 'mm^3',1e-9; ...
    'm^4',1; 'cm^4',1e-8; 'mm^4',1e-12; 'N',1; 'kN',1e3; 'MN',1e6; 'daN',10; ...
    'N.m',1; 'kN.m',1e3; 'N.mm',1e-3; 'daN.m',10; 'N/m',1; 'kN/m',1e3; 'N/mm',1e3; ...
    'Pa',1; 'kPa',1e3; 'MPa',1e6; 'GPa',1e9; 'rad',1; 'mrad',1e-3; 'deg',pi/180; ...
    char(176),pi/180; 'rad/m',1; 'deg/m',pi/180; [char(176) '/m'],pi/180; ...
    ['1/' char(176) 'C'],1; ['1e-6/' char(176) 'C'],1e-6; 'kg/m^3',1; 'kg/m',1; '-',1};
x = [0 1.5 -3; 2 7 1e3];
for k = 1:size(units, 1)
    u = units{k, 1};
    tc.verifyEqual(DataManager.unitFactor(u), units{k, 2}, 'RelTol', 1e-15, u);
    tc.verifyEqual(DataManager.toSI(x, u), x*units{k, 2}, 'RelTol', 1e-15, u);
    tc.verifyEqual(DataManager.fromSI(DataManager.toSI(x, u), u), x, 'AbsTol', 1e-12*max(abs(x(:))), u);
    tc.verifyEqual(DataManager.unitFactor(string(u)), units{k, 2}, 'RelTol', 1e-15, u);
end
end

function testUnitsExamplesAndErrors(tc)
tc.verifyEqual(DataManager.toSI(200, 'MPa'), 2e8);
tc.verifyEqual(DataManager.fromSI(2e8, 'MPa'), 200);
tc.verifyEqual(DataManager.toSI(180, 'deg'), pi, 'RelTol', 1e-15);
tc.verifyEqual(DataManager.toSI(5, 'kN.m'), 5000);
tc.verifyEqual(DataManager.toSI(1, ['cm' char(178)]), 1e-4, 'RelTol', 1e-15);   % cm²
tc.verifyEqual(DataManager.toSI(1, ['N' char(183) 'm']), 1);                    % N·m
tc.verifyEqual(DataManager.toSI(1, ' kN / m '), 1e3);
tc.verifyError(@() DataManager.unitFactor('furlong'), 'MecaStruct:DataManager:unknownUnit');
tc.verifyError(@() DataManager.toSI(1, 'parsec'), 'MecaStruct:DataManager:unknownUnit');
tc.verifyError(@() DataManager.unitFactor(12), 'MecaStruct:DataManager:unknownUnit');
tc.verifyError(@() DataManager.toSI('a', 'm'), 'MecaStruct:DataManager:invalidValue');
end

%% ---------------------------------------------------------------------------------------------
%  Formulaires LaTeX
%  ---------------------------------------------------------------------------------------------

function testFormulaKeys(tc)
k = DataManager.formulaKeys();
tc.verifyEqual(k, {'materiaux','geometrie','equilibre','cohesion','treillis','traction', ...
    'cisaillement','matage','torsion','flexion','deformee','energie','mohr_integrales', ...
    'flambage','tenseurs','mohr_cercle','criteres','hooke','extensometrie'});
tc.verifyError(@() DataManager.formulaSheet('inexistant'), 'MecaStruct:DataManager:unknownFormulaKey');
end

function testFormulaSheetsStructure(tc)
keys = DataManager.formulaKeys();
forbidden = {'\iint', '\iiint', '\implies', '\text{', '\dfrac', '\tfrac', '\boldsymbol', ...
    '\geqslant', '\leqslant', 'pmatrix', 'bmatrix', '{align', '{cases'};
for i = 1:numel(keys)
    s = DataManager.formulaSheet(keys{i});
    tc.verifyTrue(isstruct(s) && iscolumn(s), keys{i});
    tc.verifyEqual(sort(fieldnames(s)), sort({'title'; 'latex'; 'vars'}), keys{i});
    tc.verifyGreaterThanOrEqual(numel(s), 6, keys{i});
    for j = 1:numel(s)
        lab = sprintf('%s #%d', keys{i}, j);
        L = s(j).latex;
        tc.verifyClass(L, 'char', lab);
        tc.verifyTrue(~isempty(strtrim(s(j).title)) && ~isempty(strtrim(s(j).vars)), lab);
        tc.verifyTrue(startsWith(L, '$') && endsWith(L, '$'), lab);
        tc.verifyTrue(all(double(L) < 128), [lab ' : caractère non ASCII']);
        tc.verifyLessThan(numel(L), 1000, lab);
        tc.verifyFalse(any(cellfun(@(f) contains(L, f), forbidden)), [lab ' : commande interdite']);
    end
end
end

function testFormulaSheetsRenderWithoutWarning(tc)
% Toutes les chaînes LaTeX des fiches, de la table de Mohr et des abaques Kt sont rendues sans
% avertissement par l'interpréteur LaTeX de MATLAB.
strs = {};
keys = DataManager.formulaKeys();
for i = 1:numel(keys)
    s = DataManager.formulaSheet(keys{i});
    for j = 1:numel(s)
        strs(end + 1, :) = {s(j).latex, sprintf('%s #%d', keys{i}, j)}; %#ok<AGROW>
    end
end
T = DataManager.mohrTable();
for j = 1:numel(T)
    strs(end + 1, :) = {T(j).latex, ['mohr ' T(j).id]}; %#ok<AGROW>
end
C = DataManager.ktCharts();
for j = 1:numel(C)
    strs(end + 1, :) = {C(j).latex, ['kt ' C(j).id]}; %#ok<AGROW>
end
[~, info] = DataManager.evalKt('arbre_epaulement_flexion', [0.1 1.5]);
strs(end + 1, :) = {info.latex{1}, 'evalKt arbre'};
[~, info] = DataManager.evalKt('plaque_trou_traction', 0.3);
strs(end + 1, :) = {info.latex{1}, 'evalKt plaque'};

fig = figure('Visible', 'off');
cleanup = onCleanup(@() close(fig));
ax = axes(fig);
ws = warning('on', 'all');    % un avertissement désactivé ne renseignerait pas lastwarn
restoreW = onCleanup(@() warning(ws));
for k = 1:size(strs, 1)
    cla(ax);
    lastwarn('');
    h = text(ax, 0, 0.5, strs{k, 1}, 'Interpreter', 'latex', 'FontSize', 10);
    drawnow;
    [msg, id] = lastwarn();
    tc.verifyEmpty(msg, sprintf('%s : %s (%s) -> %s', strs{k, 2}, msg, id, strs{k, 1}));
    delete(h);
end
end

%% ---------------------------------------------------------------------------------------------
%  Table des intégrales de Mohr
%  ---------------------------------------------------------------------------------------------

function testMohrTableAgainstIntegral(tc)
T = DataManager.mohrTable();
tc.verifyTrue(iscolumn(T));
tc.verifyTrue(all(isfield(T, {'id','shape1','shape2','latex','fun'})));
shapes = {'rectangle','triangle','triangle_inverse','trapeze','parabole'};
tc.verifyEqual(numel(T), numel(shapes)^2);
l = 2.7;
vals = struct('rectangle', 3.2, 'triangle', -1.7, 'triangle_inverse', 2.3, ...
    'trapeze', [1.9 -0.8], 'parabole', 4.1);
valsB = struct('rectangle', -0.6, 'triangle', 2.9, 'triangle_inverse', 1.1, ...
    'trapeze', [-2.2 3.4], 'parabole', -1.3);
for k = 1:numel(T)
    a = vals.(T(k).shape1);
    b = valsB.(T(k).shape2);
    f1 = shapeFun(T(k).shape1, l, a);
    f2 = shapeFun(T(k).shape2, l, b);
    ref = integral(@(s) f1(s).*f2(s), 0, l, 'AbsTol', 1e-14, 'RelTol', 1e-13);
    tc.verifyEqual(T(k).fun(l, a, b), ref, 'RelTol', 1e-9, T(k).id);
    tc.verifyEqual(T(k).id, [T(k).shape1 '_x_' T(k).shape2]);
end
% Les entrées demandées existent
ids = {T.id};
for need = {'rectangle_x_rectangle','rectangle_x_triangle','rectangle_x_trapeze','rectangle_x_parabole', ...
        'triangle_x_triangle','triangle_x_triangle_inverse','triangle_x_trapeze','trapeze_x_trapeze', ...
        'parabole_x_triangle','parabole_x_trapeze','parabole_x_parabole'}
    tc.verifyTrue(any(strcmp(ids, need{1})), need{1});
end
% Valeurs de cours
get = @(id) T(strcmp(ids, id)).fun;
f = get('triangle_x_triangle');          tc.verifyEqual(f(6, 2, 5), 6/3*2*5, 'RelTol', 1e-12);
f = get('triangle_x_triangle_inverse');  tc.verifyEqual(f(6, 2, 5), 6/6*2*5, 'RelTol', 1e-12);
f = get('triangle_inverse_x_trapeze');   tc.verifyEqual(f(6, 3, [1 2]), 6/6*3*(2*1 + 2), 'RelTol', 1e-12);
f = get('parabole_x_parabole');          tc.verifyEqual(f(1, 1, 1), 8/15, 'RelTol', 1e-12);
end

function f = shapeFun(shape, l, v)
% Diagramme élémentaire sur [0, l].
switch shape
    case 'rectangle',        f = @(s) v(1) + 0*s;
    case 'triangle',         f = @(s) v(1)*s/l;
    case 'triangle_inverse', f = @(s) v(1)*(1 - s/l);
    case 'trapeze',          f = @(s) v(1)*(1 - s/l) + v(2)*s/l;
    case 'parabole',         f = @(s) 4*v(1)*s.*(l - s)/l^2;
end
end

%% ---------------------------------------------------------------------------------------------
%  Abaques Kt
%  ---------------------------------------------------------------------------------------------

function testKtCharts(tc)
C = DataManager.ktCharts();
tc.verifyTrue(iscolumn(C));
tc.verifyTrue(all(isfield(C, {'id','title','params','ranges','description'})));
tc.verifyEqual(sort({C.id}), sort({'plaque_trou_traction','arbre_epaulement_flexion', ...
    'arbre_epaulement_torsion','arbre_epaulement_traction'}));
for k = 1:numel(C)
    tc.verifyTrue(iscellstr(C(k).params));
    tc.verifyEqual(size(C(k).ranges), [numel(C(k).params) 2]);
    tc.verifyTrue(all(C(k).ranges(:, 2) > C(k).ranges(:, 1)));
end
end

function testEvalKtPlate(tc)
tc.verifyEqual(DataManager.evalKt('plaque_trou_traction', 0), 3);
x = 0.3;
tc.verifyEqual(DataManager.evalKt('plaque_trou_traction', x), 3 - 3.13*x + 3.66*x^2 - 1.53*x^3, 'RelTol', 1e-12);
tc.verifyEqual(DataManager.evalKt('plaque_trou_traction', struct('d', 0.01, 'W', 0.05)), ...
    DataManager.evalKt('plaque_trou_traction', 0.2), 'RelTol', 1e-12);
xs = linspace(0, 0.99, 50);
K = DataManager.evalKt('plaque_trou_traction', xs);
tc.verifyEqual(size(K), size(xs));
tc.verifyTrue(all(K >= 1) && all(diff(K) <= 0));
tc.verifyError(@() DataManager.evalKt('plaque_trou_traction', 1.2), 'MecaStruct:DataManager:ktParams');
tc.verifyError(@() DataManager.evalKt('inconnu', 0.1), 'MecaStruct:DataManager:unknownKt');
end

function testEvalKtShaft(tc)
ids = {'arbre_epaulement_flexion', 'arbre_epaulement_torsion', 'arbre_epaulement_traction'};
C = DataManager.ktCharts();
for i = 1:numel(ids)
    c = C(strcmp({C.id}, ids{i}));
    tab = c.table;
    % Aux points de la table : Kt = A (r/d)^b exactement
    for j = 1:size(tab, 1)
        [Kt, info] = DataManager.evalKt(ids{i}, [0.1 tab(j, 1)]);
        tc.verifyEqual(Kt, max(tab(j, 2)*0.1^tab(j, 3), 1), 'RelTol', 1e-12, ids{i});
        tc.verifyTrue(info.inRange);
        tc.verifyTrue(iscolumn(info.report) && iscell(info.latex));
    end
    % Interpolation linéaire de A et b en D/d
    Dm = (tab(1, 1) + tab(2, 1))/2;
    [~, info] = DataManager.evalKt(ids{i}, struct('rd', 0.05, 'Dd', Dm));
    tc.verifyEqual(info.A, (tab(1, 2) + tab(2, 2))/2, 'RelTol', 1e-12);
    tc.verifyEqual(info.b, (tab(1, 3) + tab(2, 3))/2, 'RelTol', 1e-12);
    % Kt décroît avec r/d, croît avec D/d, Kt >= 1
    rd = linspace(0.01, 0.3, 30)';
    K = DataManager.evalKt(ids{i}, [rd, 1.5*ones(30, 1)]);
    tc.verifyTrue(all(K >= 1) && all(diff(K) <= 1e-12), ids{i});
    tc.verifyGreaterThan(DataManager.evalKt(ids{i}, [0.02 2]), DataManager.evalKt(ids{i}, [0.02 1.1]));
    % Structure r, d, D équivalente
    tc.verifyEqual(DataManager.evalKt(ids{i}, struct('r', 2, 'd', 20, 'D', 30)), ...
        DataManager.evalKt(ids{i}, [0.1 1.5]), 'RelTol', 1e-12);
    % Hors domaine signalé
    [~, info] = DataManager.evalKt(ids{i}, [0.5 1.5]);
    tc.verifyFalse(info.inRange);
end
% Ordre de grandeur classique (flexion, r/d = 0,1, D/d = 2 : Kt ≈ 1,7)
tc.verifyEqual(DataManager.evalKt('arbre_epaulement_flexion', [0.1 2]), 1.7, 'RelTol', 0.06);
tc.verifyError(@() DataManager.evalKt('arbre_epaulement_flexion', [0.1 0.9]), 'MecaStruct:DataManager:ktParams');
tc.verifyError(@() DataManager.evalKt('arbre_epaulement_flexion', struct('x', 1)), 'MecaStruct:DataManager:ktParams');
end

%% ---------------------------------------------------------------------------------------------
%  Pressions de matage
%  ---------------------------------------------------------------------------------------------

function testBearingTableDefault(tc)
T = DataManager.bearingTableDefault();
tc.verifyEqual(T.Properties.VariableNames, {'Liaison','Conditions','Pmin','Pmax','Note'});
tc.verifyClass(T.Liaison, 'string');
tc.verifyEqual(min(T.Pmin), 0.5e6);
tc.verifyEqual(max(T.Pmax), 150e6);
tc.verifyTrue(all(T.Pmax >= T.Pmin));
tc.verifyTrue(all(ismember(T.Conditions, ["médiocres", "moyennes", "très bonnes"])));
tc.verifyTrue(all(contains(T.Note, 'usuelle')));
dm = tc.TestData.dm;
ref = {'fixe', [35 50; 60 100; 80 150]; 'glissant sans charge', [15 20; 20 30; 25 40]; ...
    'glissant sous charge', [3 10; 5 15; 10 20]};
cond = {'médiocres', 'moyennes', 'très bonnes'};
for i = 1:size(ref, 1)
    for j = 1:3
        [pmin, pmax] = dm.getBearingPressure(ref{i, 1}, cond{j});
        tc.verifyEqual([pmin pmax], ref{i, 2}(j, :)*1e6, [ref{i, 1} ' ' cond{j}]);
    end
end
[pmin, pmax] = dm.getBearingPressure('Clavette / cannelures - fixe', 'tres bonnes');
tc.verifyEqual([pmin pmax], [80 150]*1e6);
tc.verifyError(@() dm.getBearingPressure('soudure', 'moyennes'), 'MecaStruct:DataManager:bearingNotFound');
tc.verifyError(@() dm.getBearingPressure('glissant', 'moyennes'), 'MecaStruct:DataManager:bearingAmbiguous');
tc.verifyError(@() dm.getBearingPressure('fixe', 'excellentes'), 'MecaStruct:DataManager:bearingNotFound');
end

function testBearingEdit(tc)
dm = tc.TestData.dm;
n0 = height(dm.BearingPressures);
dm.setBearingPressure('Clavette / cannelures - fixe', 'moyennes', 70e6, 90e6, 'essai');
[pmin, pmax] = dm.getBearingPressure('fixe', 'moyennes');
tc.verifyEqual([pmin pmax], [70e6 90e6]);
tc.verifyEqual(height(dm.BearingPressures), n0);
dm.setBearingPressure('Goupille', 'moyennes', 20e6, 30e6);
tc.verifyEqual(height(dm.BearingPressures), n0 + 1);
tc.verifyError(@() dm.setBearingPressure('X', 'moyennes', 30e6, 20e6), 'MecaStruct:DataManager:invalidBearing');
dm.resetBearingPressures();
tc.verifyEqual(dm.BearingPressures, DataManager.bearingTableDefault());
end

%% ---------------------------------------------------------------------------------------------
%  Sauvegarde / chargement des données utilisateur
%  ---------------------------------------------------------------------------------------------

function testSaveLoadRoundTrip(tc)
dm = tc.TestData.dm;
file = fullfile(tc.TestData.dir, 'sub', 'db.mat');
dm.addMaterial(struct('Name', 'Alliage X', 'Category', 'Essai', 'E', 70e9, 'G', 26e9, ...
    'Re', 250e6, 'Rm', 310e6, 'alpha', 23e-6, 'rho', 2700, 'Note', 'note'));
dm.addProfile('UAP', struct('Name', '123', 'h', 0.123, 'b', 0.05, 'a', 0.006, 'e', 0.009));
dm.setBearingPressure('Clavette / cannelures - fixe', 'moyennes', 61e6, 99e6, 'modifiée');
dm.saveUserData(file);
tc.verifyTrue(isfile(file));
S = load(file);
tc.verifyEqual(height(S.MecaStructUserDB.materials), 1);
tc.verifyEqual(height(S.MecaStructUserDB.profiles.UAP), 1);
tc.verifyEqual(height(S.MecaStructUserDB.profiles.IPE), 0);
% Rechargement dans une base neuve
dm2 = DataManager(fullfile(tc.TestData.dir, 'absent.mat'));
dm2.loadUserData(file);
m1 = dm.getMaterial('Alliage X');
m2 = dm2.getMaterial('Alliage X');
tc.verifyEqual(m2, m1);
tc.verifyEqual(dm2.getProfile('UAP', 'UAP 123'), dm.getProfile('UAP', 'UAP 123'));
[pmin, pmax] = dm2.getBearingPressure('fixe', 'moyennes');
tc.verifyEqual([pmin pmax], [61e6 99e6]);
tc.verifyEqual(height(dm2.Materials), height(dm.Materials));
% Le constructeur fusionne le fichier utilisateur
dm3 = DataManager(file);
tc.verifyTrue(dm3.getMaterial('Alliage X').IsUser);
% Sauvegarde par défaut dans UserFile
dm3.UserFile = fullfile(tc.TestData.dir, 'defaut.mat');
dm3.saveUserData();
tc.verifyTrue(isfile(dm3.UserFile));
end

function testLoadErrors(tc)
dm = tc.TestData.dm;
tc.verifyError(@() dm.loadUserData(fullfile(tc.TestData.dir, 'nope.mat')), ...
    'MecaStruct:DataManager:fileNotFound');
bad = fullfile(tc.TestData.dir, 'bad.mat');
x = 1;
save(bad, 'x');
tc.verifyError(@() dm.loadUserData(bad), 'MecaStruct:DataManager:invalidUserFile');
% Un fichier utilisateur invalide est ignoré par le constructeur, avec avertissement
tc.verifyWarning(@() DataManager(bad), 'MecaStruct:DataManager:userFileIgnored');
end
