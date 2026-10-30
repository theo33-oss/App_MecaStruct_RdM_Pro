% make_screenshots.m - régénère les captures du guide utilisateur (docs/img/*.png).
% Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
% Usage : depuis la racine du projet, run('docs/make_screenshots.m')
root = fileparts(fileparts(mfilename('fullpath')));
cd(root);
out = fullfile(root, 'docs', 'img');
if ~exist(out, 'dir'), mkdir(out); end
app = MecaStruct_App();
app.UIFigure.Position = [30 50 1500 860];
st = app.runAllExamples();
disp(st.messages);
% l'exemple poutre affiché = isostatique (runAllExamples finit sur « tassement »)
app.loadExample('Poutres', 'isostatique'); app.computeBeam();
app.computeSection(); app.computeTruss(); app.computeTraction(); app.computeBending();
shots = {
    '01_base_de_donnees', 'Base de données', []
    '02_sections', 'Sections', []
    '03_poutre_sollicitations', 'Poutres', 2
    '04_poutre_deformee', 'Poutres', 3
    '05_treillis', 'Treillis', []
    '06_traction', 'Traction', []
    '07_cisaillement', 'Cisaillement', []
    '08_torsion', 'Torsion', []
    '09_flexion', 'Flexion', []
    '10_flambage', 'Flambage', []
    '11_tenseurs_mohr', 'Tenseurs', []
    '12_hooke', 'Hooke', []
    '13_jauges', 'Jauges', []
    '14_convertisseur', 'Convertisseur', []};
for k = 1:size(shots, 1)
    app.selectTab(shots{k, 2}, shots{k, 3});
    drawnow; pause(1.5);
    exportapp(app.UIFigure, fullfile(out, [shots{k, 1} '.png']));
end
delete(app);
