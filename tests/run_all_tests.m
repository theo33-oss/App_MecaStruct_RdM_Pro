%RUN_ALL_TESTS Lance toute la suite de tests de MecaStruct_RdM_Pro et affiche un résumé.
%   run('tests/run_all_tests.m') ou, depuis le dossier du projet : run_all_tests
%   Exécute tous les fichiers tests/test_*.m (matlab.unittest), affiche un tableau par fichier
%   puis la liste des tests en échec. Termine par une erreur 'MecaStruct:tests:failed' si au moins
%   un test échoue (aucun échec silencieux) ; la variable runAllResults reste dans l'espace de travail.

import matlab.unittest.TestSuite
import matlab.unittest.TestRunner

testsDir = fileparts(mfilename('fullpath'));
if isempty(testsDir)
    testsDir = fullfile(pwd, 'tests');
end
rootDir = fileparts(testsDir);
addpath(rootDir, testsDir);

suite = TestSuite.fromFolder(testsDir);
if isempty(suite)
    error('MecaStruct:tests:empty', 'Aucun test trouvé dans %s.', testsDir);
end
fprintf('MecaStruct_RdM_Pro : %d tests dans %s\n\n', numel(suite), testsDir);
runner = TestRunner.withTextOutput;
runAllResults = runner.run(suite);

% Résumé par fichier
files = regexprep({runAllResults.Name}, '/.*$', '');
[uf, ~, idx] = unique(files, 'stable');
nPass = accumarray(idx(:), [runAllResults.Passed]', [], @sum);
nFail = accumarray(idx(:), [runAllResults.Failed]', [], @sum);
nInc = accumarray(idx(:), [runAllResults.Incomplete]', [], @sum);
dur = accumarray(idx(:), [runAllResults.Duration]', [], @sum);
summary = table(string(uf(:)), nPass, nFail, nInc, round(dur, 1), ...
    'VariableNames', {'Fichier', 'Reussis', 'Echecs', 'Incomplets', 'Duree_s'});
fprintf('\n===================== RÉSUMÉ =====================\n');
disp(summary);
nTot = numel(runAllResults);
nOK = nnz([runAllResults.Passed]);
fprintf('Total : %d/%d tests réussis (%.1f s)\n', nOK, nTot, sum([runAllResults.Duration]));
bad = runAllResults(~[runAllResults.Passed]);
if ~isempty(bad)
    fprintf('\nTests en échec ou incomplets :\n');
    for k = 1:numel(bad)
        fprintf('  - %s\n', bad(k).Name);
    end
    error('MecaStruct:tests:failed', '%d test(s) en échec ou incomplet(s) sur %d.', numel(bad), nTot);
end
fprintf('Tous les tests sont réussis.\n');
