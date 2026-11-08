% Lancer.m : ouvre MecaStruct RdM Pro depuis n'importe quel dossier courant de MATLAB.
% Utilisation : ouvrir ce fichier dans MATLAB puis cliquer sur « Exécuter », ou taper Lancer.
here = fileparts(mfilename('fullpath'));
cd(here);
addpath(here);
app = MecaStruct_App(); %#ok<NASGU>
