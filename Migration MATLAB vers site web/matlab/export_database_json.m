%EXPORT_DATABASE_JSON Exporte la base de données de MecaStruct (DataManager) en JSON pour la version web.
%   À lancer UNE FOIS dans MATLAB (ouvrir ce fichier puis cliquer sur « Exécuter »).
%   Écrit dans <racine du projet>/web/data/ :
%     materials.json          matériaux (SI : Pa, 1/°C, kg/m³)
%     profiles.json           profilés IPN, IPE, HEA, HEB, UPN, UAP (SI : m, m², m⁴, kg/m)
%     bearing_pressures.json  pressions de matage admissibles (Pa)
%     section_presets.json    tubes et cornières courants (mm)
%     formula_sheets.json     fiches de formules LaTeX par clé
%     kt_charts.json          abaques Kt (métadonnées + table de Peterson)
%     mohr_table.json         table des intégrales de Mohr (sans les fonctions, à porter en Python)
%     units.json              catalogue du convertisseur + facteurs vers le SI de chaque code d'unité
%   Application de Théo Brun. Script écrit pour la migration web (Migration MATLAB vers site web).

here = fileparts(mfilename('fullpath'));             % .../Migration MATLAB vers site web/matlab
root = fileparts(fileparts(here));         % racine du projet
addpath(fullfile(root, 'desktop'));
outDir = fullfile(root, 'web', 'data');
if ~exist(outDir, 'dir')
    mkdir(outDir);
end
fprintf('Export de la base vers %s\n', outDir);

dm = DataManager();

% --- matériaux
mats = table2struct(dm.Materials);
writeJson(fullfile(outDir, 'materials.json'), mats);

% --- profilés
fams = cellstr(dm.listProfileFamilies());
prof = struct();
for k = 1:numel(fams)
    prof.(fams{k}) = table2struct(dm.Profiles.(fams{k}));
end
writeJson(fullfile(outDir, 'profiles.json'), prof);

% --- pressions de matage
writeJson(fullfile(outDir, 'bearing_pressures.json'), table2struct(dm.BearingPressures));

% --- préréglages de sections (tubes, cornières)
writeJson(fullfile(outDir, 'section_presets.json'), DataManager.sectionPresets());

% --- fiches de formules
keys = DataManager.formulaKeys();
sheets = struct();
for k = 1:numel(keys)
    sheets.(keys{k}) = DataManager.formulaSheet(keys{k});
end
writeJson(fullfile(outDir, 'formula_sheets.json'), struct('keys', {keys}, 'sheets', sheets));

% --- abaques Kt
writeJson(fullfile(outDir, 'kt_charts.json'), DataManager.ktCharts());

% --- table des intégrales de Mohr (le champ fun est une fonction : non exportable)
T = DataManager.mohrTable();
if isfield(T, 'fun')
    T = rmfield(T, 'fun');
end
writeJson(fullfile(outDir, 'mohr_table.json'), T);

% --- unités : catalogue du convertisseur + facteur SI de chaque code
catOut = {};
try
    ucat = MecaStruct_App.unitCatalog();
    catOut = cell(numel(ucat), 1);
    codes = {};
    for k = 1:numel(ucat)
        u = ucat(k).units;
        rows = cell(size(u, 1), 1);
        for i = 1:size(u, 1)
            rows{i} = struct('label', u{i, 1}, 'code', u{i, 2});
            codes{end + 1} = u{i, 2}; %#ok<AGROW>
        end
        catOut{k} = struct('name', ucat(k).name, 'units', {rows}, ...
            'defFrom', ucat(k).defFrom, 'defTo', ucat(k).defTo);
    end
catch err
    warning('Catalogue du convertisseur non exporté : %s', err.message);
    codes = {};
end
% codes documentés dans ARCHITECTURE.md (toSI / fromSI)
codes = [codes, {'m', 'cm', 'mm', 'µm', 'um', 'm^2', 'cm^2', 'mm^2', 'm^3', 'cm^3', 'mm^3', ...
    'm^4', 'cm^4', 'mm^4', 'N', 'kN', 'MN', 'daN', 'N.m', 'kN.m', 'N.mm', 'daN.m', 'N/m', 'kN/m', ...
    'N/mm', 'Pa', 'kPa', 'MPa', 'GPa', 'rad', 'mrad', 'deg', '°', 'rad/m', 'deg/m', '°/m', ...
    '1/°C', '1e-6/°C', 'kg/m^3', 'kg/m', '-'}];
codes = unique(codes, 'stable');
factors = {};
for k = 1:numel(codes)
    try
        factors{end + 1} = struct('code', codes{k}, 'factor', DataManager.unitFactor(codes{k})); %#ok<AGROW>
    catch err
        factors{end + 1} = struct('code', codes{k}, 'factor', NaN, 'erreur', err.message); %#ok<AGROW>
    end
end
writeJson(fullfile(outDir, 'units.json'), struct('catalog', {catOut}, 'factors', {factors}));

fprintf('Terminé : %d fichiers JSON écrits dans %s\n', 8, outDir);

%% ------------------------------------------------------------------------
function writeJson(file, data)
% Écrit data en JSON UTF-8 lisible. NaN et Inf sont écrits NaN / Infinity
% (accepté par json.load de Python).
txt = jsonencode(data, 'PrettyPrint', true, 'ConvertInfAndNaN', false);
fid = fopen(file, 'w', 'n', 'UTF-8');
if fid < 0
    error('Impossible d''écrire %s', file);
end
fprintf(fid, '%s', txt);
fclose(fid);
fprintf('  %s\n', file);
end
