classdef DataManager < handle
    %DATAMANAGER Base de données de MecaStruct_RdM_Pro.
    %   Application de Théo Brun, basée sur son cours de Résistance des Matériaux et sur les sources citées dans README.md (section « Auteur et sources »).
    %   Matériaux (valeurs du cours complétées par des valeurs usuelles), catalogue de profilés
    %   européens (IPN, IPE, HEA, HEB, UPN, UAP), pressions admissibles de matage, abaques de
    %   concentration de contraintes Kt (ajustements de Peterson), table des intégrales de Mohr,
    %   formulaires LaTeX par thème et conversions d'unités.
    %
    %   dm = DataManager()            valeurs par défaut + fichier utilisateur par défaut
    %                                 (<dossier de DataManager.m>/userdata/MecaStruct_UserDB.mat)
    %   dm = DataManager(userFile)    valeurs par défaut + fichier utilisateur indiqué
    %
    %   Toutes les valeurs sont stockées en SI strict : m, m², m³, m⁴, Pa, kg/m³, kg/m, 1/°C.
    %   Convention des profilés : Iz (application) = Iy (Eurocode) = axe fort ;
    %   Iy (application) = Iz (Eurocode) = axe faible ; idem pour W et r.
    %
    %   Méthodes d'instance : listMaterials, getMaterial, addMaterial, removeMaterial,
    %   listProfileFamilies, listProfiles, getProfile, addProfile, removeProfile,
    %   saveUserData, loadUserData, getBearingPressure, setBearingPressure, resetBearingPressures.
    %   Méthodes statiques : completeIsotropic, toSI, fromSI, unitFactor, hasSymbolic,
    %   formulaKeys, formulaSheet, mohrTable, ktCharts, evalKt, bearingTableDefault,
    %   defaultUserFile.
    %
    %   Voir aussi docs/ARCHITECTURE.md (§1).

    properties
        % Table des matériaux : Name, Category (string), E, G (Pa), nu, Re, Rm (Pa),
        % alpha (1/°C), rho (kg/m³), Note (string), IsUser (logical).
        Materials table
        % Structure de tables par famille (IPN, IPE, HEA, HEB, UPN, UAP) : Name, h, b, a, e, r (m),
        % S (m²), Iz, Iy (m⁴), Wz, Wy (m³), rz, ry (m), mass (kg/m), c (m, NaN hors U), IsUser.
        Profiles struct
        % Table des pressions admissibles de matage : Liaison, Conditions (string), Pmin, Pmax (Pa), Note.
        BearingPressures table
        % Chemin du fichier .mat des données utilisateur.
        UserFile char = ''
    end

    properties (Access = private)
        DefaultMaterials table      % base matériaux par défaut (pour restauration)
        DefaultProfiles struct      % catalogue par défaut (pour restauration)
    end

    properties (Constant, Access = private)
        Families = {'IPN', 'IPE', 'HEA', 'HEB', 'UPN', 'UAP'}
        MaterialVars = {'Name', 'Category', 'E', 'G', 'nu', 'Re', 'Rm', 'alpha', 'rho', 'Note', 'IsUser', 'Author'}
        ProfileVars = {'Name', 'h', 'b', 'a', 'e', 'r', 'S', 'Iz', 'Iy', 'Wz', 'Wy', 'rz', 'ry', 'mass', 'c', 'IsUser', 'Author'}
        BaseAuthor = "Base fournie"      % valeur de Author des lignes de la base par défaut
        BearingVars = {'Liaison', 'Conditions', 'Pmin', 'Pmax', 'Note'}
        RhoSteel = 7850
    end

    %% =========================================================================================
    %  Constructeur, validation des propriétés
    %  =========================================================================================
    methods

        function obj = DataManager(userFile)
            %DATAMANAGER Construit la base : valeurs par défaut puis fusion du fichier utilisateur.
            %   obj = DataManager() utilise le fichier utilisateur par défaut
            %   (<dossier de DataManager.m>/userdata/MecaStruct_UserDB.mat).
            %   obj = DataManager(userFile) utilise le fichier .mat userFile.
            %   Le fichier n'est lu que s'il existe ; s'il est illisible, il est ignoré avec
            %   l'avertissement 'MecaStruct:DataManager:userFileIgnored'.
            if nargin < 1 || isempty(userFile)
                userFile = DataManager.defaultUserFile();
            end
            obj.UserFile = char(string(userFile));
            obj.DefaultMaterials = DataManager.defaultMaterialsTable();
            obj.DefaultProfiles = DataManager.defaultProfiles();
            obj.Materials = obj.DefaultMaterials;
            obj.Profiles = obj.DefaultProfiles;
            obj.BearingPressures = DataManager.bearingTableDefault();
            if isfile(obj.UserFile)
                try
                    obj.loadUserData(obj.UserFile);
                catch err
                    warning('MecaStruct:DataManager:userFileIgnored', ...
                        'Fichier utilisateur ignoré (%s) : %s', obj.UserFile, err.message);
                end
            end
        end

        function set.Materials(obj, T)
            % Validation : table contenant toutes les variables du contrat.
            DataManager.checkTableVars(T, DataManager.MaterialVars, 'Materials');
            obj.Materials = T;
        end

        function set.Profiles(obj, P)
            % Validation : structure contenant une table par famille de profilés.
            if ~isstruct(P) || ~isscalar(P)
                error('MecaStruct:DataManager:invalidProperty', ...
                    'Profiles doit être une structure scalaire (un champ par famille).');
            end
            fams = DataManager.Families;
            for k = 1:numel(fams)
                if ~isfield(P, fams{k})
                    error('MecaStruct:DataManager:invalidProperty', ...
                        'Profiles doit contenir le champ %s.', fams{k});
                end
                DataManager.checkTableVars(P.(fams{k}), DataManager.ProfileVars, ['Profiles.' fams{k}]);
            end
            obj.Profiles = P;
        end

        function set.BearingPressures(obj, T)
            % Validation : table des pressions de matage conforme au contrat.
            DataManager.checkTableVars(T, DataManager.BearingVars, 'BearingPressures');
            obj.BearingPressures = T;
        end

        %% -------------------------------------------------------------------------------------
        %  Matériaux
        %  -------------------------------------------------------------------------------------

        function names = listMaterials(obj)
            %LISTMATERIALS Noms des matériaux disponibles.
            %   names = dm.listMaterials() renvoie un vecteur string colonne.
            names = obj.Materials.Name(:);
        end

        function m = getMaterial(obj, name)
            %GETMATERIAL Caractéristiques d'un matériau.
            %   m = dm.getMaterial(name) renvoie une structure : Name, Category, E, G, nu, Re, Rm,
            %   alpha, rho, Note (+ IsUser). Toutes les valeurs sont en SI (Pa, 1/°C, kg/m³).
            %   La recherche ignore la casse, les accents, les espaces et la ponctuation
            %   ('xc38' trouve 'XC 38') ; un préfixe non ambigu est accepté.
            %   Erreur 'MecaStruct:DataManager:unknownMaterial' si le matériau est introuvable.
            idx = DataManager.matchName(obj.Materials.Name, name);
            if isempty(idx)
                error('MecaStruct:DataManager:unknownMaterial', ...
                    'Matériau inconnu : « %s ».', char(strjoin(string(name), ' ')));
            end
            r = obj.Materials(idx, :);
            m = struct('Name', char(r.Name), 'Category', char(r.Category), 'E', r.E, 'G', r.G, ...
                'nu', r.nu, 'Re', r.Re, 'Rm', r.Rm, 'alpha', r.alpha, 'rho', r.rho, ...
                'Note', char(r.Note), 'IsUser', r.IsUser, 'Author', char(r.Author));
        end

        function addMaterial(obj, m)
            %ADDMATERIAL Ajoute (ou remplace) un matériau utilisateur.
            %   dm.addMaterial(m) avec m structure scalaire (ou table d'une ligne) : Name (requis),
            %   Category, E, G, nu, Re, Rm, alpha, rho (SI), Note. Les champs absents valent NaN ;
            %   la constante élastique manquante est complétée par completeIsotropic
            %   (G = E/(2(1+ν))). Le matériau est marqué IsUser = true ; un matériau de même nom
            %   (casse et espaces ignorés) est remplacé à la même position.
            if istable(m)
                if height(m) ~= 1
                    error('MecaStruct:DataManager:invalidMaterial', ...
                        'addMaterial attend une table d''une seule ligne.');
                end
                m = table2struct(m);
            end
            if ~isstruct(m) || ~isscalar(m) || ~isfield(m, 'Name') || DataManager.isBlank(m.Name)
                error('MecaStruct:DataManager:invalidMaterial', ...
                    'Le matériau doit être une structure scalaire avec un champ Name non vide.');
            end
            m = DataManager.prepareMaterial(m, 'Utilisateur', 'Matériau utilisateur.');
            m = DataManager.completeIsotropic(m);
            row = DataManager.materialRow(m, true);
            T = obj.Materials;
            idx = DataManager.exactIndex(T.Name, m.Name);
            if isempty(idx)
                T = [T; row];
            else
                T(idx, :) = row;
            end
            obj.Materials = T;
        end

        function removeMaterial(obj, name)
            %REMOVEMATERIAL Supprime un matériau utilisateur.
            %   dm.removeMaterial(name) supprime le matériau utilisateur name (nom exact, casse et
            %   espaces ignorés). Si ce matériau remplaçait un matériau de la base par défaut, ce
            %   dernier est restauré. Erreurs : 'MecaStruct:DataManager:unknownMaterial',
            %   'MecaStruct:DataManager:notUserMaterial' (matériau de la base par défaut).
            T = obj.Materials;
            idx = DataManager.exactIndex(T.Name, name);
            if isempty(idx)
                error('MecaStruct:DataManager:unknownMaterial', ...
                    'Matériau inconnu : « %s ».', char(strjoin(string(name), ' ')));
            end
            if ~T.IsUser(idx)
                error('MecaStruct:DataManager:notUserMaterial', ...
                    ['Seuls les matériaux utilisateur peuvent être supprimés (« %s » appartient ' ...
                    'à la base par défaut).'], char(T.Name(idx)));
            end
            iDef = DataManager.exactIndex(obj.DefaultMaterials.Name, T.Name(idx));
            if isempty(iDef)
                T(idx, :) = [];
            else
                T(idx, :) = obj.DefaultMaterials(iDef, :);
            end
            obj.Materials = T;
        end

        %% -------------------------------------------------------------------------------------
        %  Profilés
        %  -------------------------------------------------------------------------------------

        function fams = listProfileFamilies(~)
            %LISTPROFILEFAMILIES Familles de profilés disponibles.
            %   fams = dm.listProfileFamilies() renvoie ["IPN","IPE","HEA","HEB","UPN","UAP"].
            fams = string(DataManager.Families);
        end

        function names = listProfiles(obj, family)
            %LISTPROFILES Désignations des profilés d'une famille.
            %   names = dm.listProfiles(family) renvoie un vecteur string colonne (ex. "IPE 200").
            %   family : 'IPN', 'IPE', 'HEA', 'HEB', 'UPN' ou 'UAP' (casse ignorée).
            fam = DataManager.checkFamily(family);
            names = obj.Profiles.(fam).Name(:);
        end

        function p = getProfile(obj, family, name)
            %GETPROFILE Caractéristiques d'un profilé du catalogue.
            %   p = dm.getProfile(family, name) renvoie une structure : Family, Name, h, b,
            %   a (épaisseur d'âme), e (épaisseur d'aile), r (rayon de congé), S, Iz (axe fort),
            %   Iy (axe faible), Wz, Wy, rz, ry, mass (kg/m), c (UPN/UAP : distance dos d'âme → G,
            %   NaN sinon) (+ IsUser). Valeurs en SI (m, m², m⁴, m³).
            %   name : "IPE 200", "IPE200", "200" ou 200 (la famille est ajoutée si absente).
            %   Erreur 'MecaStruct:DataManager:unknownProfile' si le profilé est introuvable.
            fam = DataManager.checkFamily(family);
            T = obj.Profiles.(fam);
            idx = DataManager.profileIndex(T.Name, fam, name);
            if isempty(idx)
                error('MecaStruct:DataManager:unknownProfile', ...
                    'Profilé inconnu dans la famille %s : « %s ».', fam, char(strjoin(string(name), ' ')));
            end
            r = T(idx, :);
            p = struct('Family', fam, 'Name', char(r.Name), 'h', r.h, 'b', r.b, 'a', r.a, ...
                'e', r.e, 'r', r.r, 'S', r.S, 'Iz', r.Iz, 'Iy', r.Iy, 'Wz', r.Wz, 'Wy', r.Wy, ...
                'rz', r.rz, 'ry', r.ry, 'mass', r.mass, 'c', r.c, 'IsUser', r.IsUser, 'Author', char(r.Author));
        end

        function addProfile(obj, family, p)
            %ADDPROFILE Ajoute (ou remplace) un profilé utilisateur.
            %   dm.addProfile(family, p) avec p structure scalaire (SI) : Name, h, b, a, e (requis),
            %   r (défaut 0), S, Iz, Iy (calculés sur la géométrie simplifiée d'épaisseurs
            %   constantes s'ils manquent), c (UPN/UAP : calculé s'il manque ; NaN pour I/H),
            %   Wz, Wy, rz, ry (calculés s'ils manquent : Wz = Iz/(h/2), Wy = Iy/(b/2) pour I/H,
            %   Wy = Iy/max(c, b−c) pour U, rz = sqrt(Iz/S), ry = sqrt(Iy/S)), mass (défaut
            %   7850·S). Le nom est préfixé par la famille si nécessaire. IsUser = true.
            fam = DataManager.checkFamily(family);
            if istable(p)
                if height(p) ~= 1
                    error('MecaStruct:DataManager:invalidProfile', ...
                        'addProfile attend une table d''une seule ligne.');
                end
                p = table2struct(p);
            end
            if ~isstruct(p) || ~isscalar(p) || ~isfield(p, 'Name') || DataManager.isBlank(p.Name)
                error('MecaStruct:DataManager:invalidProfile', ...
                    'Le profilé doit être une structure scalaire avec un champ Name non vide.');
            end
            row = DataManager.buildProfileRow(fam, p);
            T = obj.Profiles.(fam);
            idx = DataManager.profileIndex(T.Name, fam, row.Name);
            if isempty(idx)
                T = [T; row];
            else
                T(idx, :) = row;
            end
            P = obj.Profiles;
            P.(fam) = T;
            obj.Profiles = P;
        end

        function removeProfile(obj, family, name)
            %REMOVEPROFILE Supprime un profilé utilisateur (extension du contrat).
            %   dm.removeProfile(family, name) supprime le profilé utilisateur ; si celui-ci
            %   remplaçait un profilé du catalogue, ce dernier est restauré.
            %   Erreurs : 'MecaStruct:DataManager:unknownProfile', 'MecaStruct:DataManager:notUserProfile'.
            fam = DataManager.checkFamily(family);
            T = obj.Profiles.(fam);
            idx = DataManager.profileIndex(T.Name, fam, name);
            if isempty(idx)
                error('MecaStruct:DataManager:unknownProfile', ...
                    'Profilé inconnu dans la famille %s : « %s ».', fam, char(strjoin(string(name), ' ')));
            end
            if ~T.IsUser(idx)
                error('MecaStruct:DataManager:notUserProfile', ...
                    'Seuls les profilés utilisateur peuvent être supprimés (« %s » appartient au catalogue).', ...
                    char(T.Name(idx)));
            end
            D = obj.DefaultProfiles.(fam);
            iDef = DataManager.profileIndex(D.Name, fam, T.Name(idx));
            if isempty(iDef)
                T(idx, :) = [];
            else
                T(idx, :) = D(iDef, :);
            end
            P = obj.Profiles;
            P.(fam) = T;
            obj.Profiles = P;
        end

        %% -------------------------------------------------------------------------------------
        %  Données utilisateur
        %  -------------------------------------------------------------------------------------

        function saveUserData(obj, file)
            %SAVEUSERDATA Sauvegarde les données utilisateur dans un fichier .mat.
            %   dm.saveUserData() écrit dans dm.UserFile ; dm.saveUserData(file) écrit dans file.
            %   Seuls les ajouts utilisateur (matériaux et profilés IsUser = true) et la table des
            %   pressions de matage (modifiable) sont enregistrés, dans la variable
            %   MecaStructUserDB (champs version, created, materials, profiles, bearingPressures).
            %   Le dossier est créé si nécessaire.
            if nargin < 2 || isempty(file)
                file = obj.UserFile;
            end
            file = char(string(file));
            if isempty(file)
                error('MecaStruct:DataManager:noUserFile', 'Aucun fichier utilisateur indiqué.');
            end
            folder = fileparts(file);
            if ~isempty(folder) && ~isfolder(folder)
                [ok, msg] = mkdir(folder);
                if ~ok
                    error('MecaStruct:DataManager:saveFailed', ...
                        'Impossible de créer le dossier %s : %s', folder, msg);
                end
            end
            MecaStructUserDB = struct();
            MecaStructUserDB.version = 1;
            MecaStructUserDB.created = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
            MecaStructUserDB.materials = obj.Materials(obj.Materials.IsUser, :);
            prof = struct();
            fams = DataManager.Families;
            for k = 1:numel(fams)
                T = obj.Profiles.(fams{k});
                prof.(fams{k}) = T(T.IsUser, :);
            end
            MecaStructUserDB.profiles = prof;
            MecaStructUserDB.bearingPressures = obj.BearingPressures;
            try
                save(file, 'MecaStructUserDB', '-v7');
            catch err
                error('MecaStruct:DataManager:saveFailed', ...
                    'Échec de la sauvegarde dans %s : %s', file, err.message);
            end
        end

        function loadUserData(obj, file)
            %LOADUSERDATA Charge et fusionne les données utilisateur d'un fichier .mat.
            %   dm.loadUserData() lit dm.UserFile ; dm.loadUserData(file) lit file.
            %   Les matériaux et profilés du fichier sont ajoutés (ou remplacent ceux de même nom)
            %   avec IsUser = true ; la table des pressions de matage du fichier remplace la table
            %   courante. Erreurs : 'MecaStruct:DataManager:fileNotFound',
            %   'MecaStruct:DataManager:invalidUserFile'.
            if nargin < 2 || isempty(file)
                file = obj.UserFile;
            end
            file = char(string(file));
            if ~isfile(file)
                error('MecaStruct:DataManager:fileNotFound', 'Fichier utilisateur introuvable : %s', file);
            end
            S = struct();
            if any(strcmp({whos('-file', file).name}, 'MecaStructUserDB'))
                S = load(file, 'MecaStructUserDB');   % une seule variable : un fichier échangé ne charge rien d'autre
            end
            if ~isfield(S, 'MecaStructUserDB') || ~isstruct(S.MecaStructUserDB)
                error('MecaStruct:DataManager:invalidUserFile', ...
                    'Le fichier %s ne contient pas de variable MecaStructUserDB.', file);
            end
            db = S.MecaStructUserDB;
            if isfield(db, 'materials') && istable(db.materials)
                for k = 1:height(db.materials)
                    obj.addMaterial(table2struct(db.materials(k, :)));
                end
            end
            if isfield(db, 'profiles') && isstruct(db.profiles)
                fn = fieldnames(db.profiles);
                for i = 1:numel(fn)
                    if ~any(strcmpi(fn{i}, DataManager.Families)) || ~istable(db.profiles.(fn{i}))
                        continue
                    end
                    Tp = db.profiles.(fn{i});
                    for k = 1:height(Tp)
                        obj.addProfile(fn{i}, table2struct(Tp(k, :)));
                    end
                end
            end
            if isfield(db, 'bearingPressures') && istable(db.bearingPressures) ...
                    && height(db.bearingPressures) > 0
                obj.BearingPressures = DataManager.validateBearingTable(db.bearingPressures);
            end
        end

        %% -------------------------------------------------------------------------------------
        %  Pressions de matage
        %  -------------------------------------------------------------------------------------

        function [pmin, pmax] = getBearingPressure(obj, liaison, conditions)
            %GETBEARINGPRESSURE Pression admissible de matage (Pa).
            %   [pmin, pmax] = dm.getBearingPressure(liaison, conditions)
            %   liaison : libellé de la table ou mots-clés non ambigus (ex. 'fixe',
            %   'glissant sous charge', 'glissant sans charge', 'articulation') ;
            %   conditions : 'médiocres', 'moyennes', 'très bonnes' (accents et casse ignorés,
            %   préfixe accepté : 'tres', 'moy'…). Erreurs : 'MecaStruct:DataManager:bearingNotFound',
            %   'MecaStruct:DataManager:bearingAmbiguous'.
            T = obj.BearingPressures;
            mL = DataManager.matchLiaison(T.Liaison, liaison);
            idx = DataManager.matchCondition(T.Conditions, mL, conditions);
            pmin = T.Pmin(idx);
            pmax = T.Pmax(idx);
        end

        function setBearingPressure(obj, liaison, conditions, pmin, pmax, note)
            %SETBEARINGPRESSURE Modifie ou ajoute une ligne de la table de matage (extension du contrat).
            %   dm.setBearingPressure(liaison, conditions, pmin, pmax, note)
            %   pmin, pmax en Pa (0 < pmin ≤ pmax). La ligne de même liaison et mêmes conditions
            %   (accents, casse et ponctuation ignorés) est remplacée, sinon une ligne est ajoutée.
            %   note : texte libre (défaut « Valeur utilisateur »). La table modifiée est
            %   enregistrée par saveUserData.
            if nargin < 6 || DataManager.isBlank(note)
                note = "Valeur utilisateur";
            end
            if ~(isnumeric(pmin) && isscalar(pmin) && isnumeric(pmax) && isscalar(pmax) ...
                    && isfinite(pmin) && isfinite(pmax) && pmin > 0 && pmax >= pmin)
                error('MecaStruct:DataManager:invalidBearing', ...
                    'Les pressions doivent vérifier 0 < Pmin ≤ Pmax (Pa).');
            end
            if DataManager.isBlank(liaison) || DataManager.isBlank(conditions)
                error('MecaStruct:DataManager:invalidBearing', ...
                    'La liaison et les conditions doivent être renseignées.');
            end
            T = obj.BearingPressures;
            kL = cellfun(@DataManager.normKey, cellstr(T.Liaison), 'UniformOutput', false);
            kC = cellfun(@DataManager.normKey, cellstr(T.Conditions), 'UniformOutput', false);
            idx = find(strcmp(kL, DataManager.normKey(liaison)) & strcmp(kC, DataManager.normKey(conditions)), 1);
            row = table(string(liaison), string(conditions), double(pmin), double(pmax), string(note), ...
                'VariableNames', DataManager.BearingVars);
            if isempty(idx)
                T = [T; row];
            else
                T(idx, :) = row;
            end
            obj.BearingPressures = T;
        end

        function resetBearingPressures(obj)
            %RESETBEARINGPRESSURES Restaure la table de matage par défaut (extension du contrat).
            obj.BearingPressures = DataManager.bearingTableDefault();
        end
    end

    %% =========================================================================================
    %  Méthodes statiques publiques
    %  =========================================================================================
    methods (Static)

        function f = defaultUserFile()
            %DEFAULTUSERFILE Chemin par défaut du fichier utilisateur.
            %   f = DataManager.defaultUserFile() renvoie
            %   <dossier de DataManager.m>/userdata/MecaStruct_UserDB.mat (char).
            f = fullfile(DataManager.dataFolder('userdata'), 'MecaStruct_UserDB.mat');
        end

        function d = dataFolder(name)
            %DATAFOLDER Dossier d'écriture <dossier du code>/<name>, ou <prefdir>/MecaStruct/<name> si le code est en lecture seule.
            root = fileparts(mfilename('fullpath'));
            [ok, a] = fileattrib(root);
            if ok && isstruct(a) && ~a.UserWrite
                root = fullfile(prefdir, 'MecaStruct');
            end
            d = fullfile(root, name);
        end

        function m = completeIsotropic(m)
            %COMPLETEISOTROPIC Complète la constante élastique manquante d'un matériau isotrope.
            %   m = DataManager.completeIsotropic(m) ; m structure scalaire avec E, G (Pa) et nu
            %   éventuellement absents ou NaN :
            %     E et nu connus → G = E/(2(1+ν)) ;  E et G connus → ν = E/(2G) − 1 ;
            %     G et nu connus → E = 2G(1+ν).
            %   Si E, G et ν sont donnés, la cohérence est vérifiée : un écart relatif
            %   |G − E/(2(1+ν))|/(E/(2(1+ν))) > 5 % est signalé dans m.Note.
            %   Si moins de deux constantes sont connues, rien n'est calculé (note ajoutée).
            %   Erreurs : 'MecaStruct:DataManager:invalidNu' (ν hors de ]−1 ; 0,5[),
            %   'MecaStruct:DataManager:invalidModulus' (E ou G ≤ 0).
            if ~isstruct(m) || ~isscalar(m)
                error('MecaStruct:DataManager:invalidMaterial', ...
                    'completeIsotropic attend une structure scalaire.');
            end
            E = DataManager.numField(m, 'E');
            G = DataManager.numField(m, 'G');
            nu = DataManager.numField(m, 'nu');
            note = '';
            if isfield(m, 'Note') && ~DataManager.isBlank(m.Note)
                note = char(strjoin(string(m.Note), ' '));
            end
            if (isfinite(E) && E <= 0) || (isfinite(G) && G <= 0)
                error('MecaStruct:DataManager:invalidModulus', ...
                    'Les modules E et G doivent être strictement positifs.');
            end
            known = isfinite([E, G, nu]);
            if all(known)
                DataManager.checkNu(nu);
                Gth = E/(2*(1 + nu));
                gap = abs(G - Gth)/Gth;
                if gap > 0.05 && ~contains(note, 'Écart de cohérence')
                    note = DataManager.appendNote(note, sprintf(['Écart de cohérence : G = %.4g GPa ' ...
                        'alors que E/(2(1+ν)) = %.4g GPa (écart %.1f %%).'], G/1e9, Gth/1e9, 100*gap));
                end
            elseif known(1) && known(3)
                DataManager.checkNu(nu);
                G = E/(2*(1 + nu));
                note = DataManager.appendNote(note, 'G calculé par G = E/(2(1+ν)).');
            elseif known(1) && known(2)
                nu = E/(2*G) - 1;
                DataManager.checkNu(nu);
                note = DataManager.appendNote(note, 'ν déduit de E et G : ν = E/(2G) − 1.');
            elseif known(2) && known(3)
                DataManager.checkNu(nu);
                E = 2*G*(1 + nu);
                note = DataManager.appendNote(note, 'E calculé par E = 2G(1+ν).');
            else
                note = DataManager.appendNote(note, ...
                    'Constantes élastiques incomplètes (au moins deux de E, G, ν sont nécessaires).');
            end
            m.E = E;
            m.G = G;
            m.nu = nu;
            m.Note = note;
        end

        function v = toSI(val, unit)
            %TOSI Conversion d'une valeur vers le SI.
            %   v = DataManager.toSI(val, unit) = val .* DataManager.unitFactor(unit).
            %   Exemple : DataManager.toSI(200, 'MPa') → 2e8 (Pa).
            if ~(isnumeric(val) || islogical(val))
                error('MecaStruct:DataManager:invalidValue', 'La valeur à convertir doit être numérique.');
            end
            v = double(val) .* DataManager.unitFactor(unit);
        end

        function v = fromSI(val, unit)
            %FROMSI Conversion d'une valeur SI vers l'unité indiquée.
            %   v = DataManager.fromSI(val, unit) = val ./ DataManager.unitFactor(unit).
            %   Exemple : DataManager.fromSI(2e8, 'MPa') → 200.
            if ~(isnumeric(val) || islogical(val))
                error('MecaStruct:DataManager:invalidValue', 'La valeur à convertir doit être numérique.');
            end
            v = double(val) ./ DataManager.unitFactor(unit);
        end

        function f = unitFactor(unit)
            %UNITFACTOR Facteur de conversion vers le SI (valeur_SI = valeur·f).
            %   f = DataManager.unitFactor(unit). Unités reconnues :
            %   'm','cm','mm','µm'/'um' ; 'm^2','cm^2','mm^2' ; 'm^3','cm^3','mm^3' ;
            %   'm^4','cm^4','mm^4' ; 'N','kN','MN','daN' ; 'N.m','kN.m','N.mm','daN.m' ;
            %   'N/m','kN/m','N/mm' ; 'Pa','kPa','MPa','GPa' ; 'rad','mrad','deg','°' ;
            %   'rad/m','deg/m','°/m' ; '1/°C','1e-6/°C' ; 'kg/m^3' ; 'kg/m' ; '-'
            %   (+ variantes : '·' ou '*' pour '.', exposants ², ³, ⁴, 'Nm', 'N/mm^2', '°C' et 'K'
            %   pour des écarts de température, 'µdef', '%', 'km', 'bar', 'W', 'kW', 'tr/min', 'J').
            %   Unités du convertisseur : 'in','ft','in^2','in^4','lbf','kip','kgf','lbf.in','lbf.ft',
            %   'kip.in','kip.ft','kgf.m','lbf/in','lbf/ft','psi','ksi','kgf/cm^2','kgf/mm^2','lb/ft^3',
            %   '°F' (écart), 'turn','arcmin','arcsec'.
            %   Les espaces sont ignorés ; la casse n'est ignorée que si la correspondance est
            %   unique. Erreur 'MecaStruct:DataManager:unknownUnit' si l'unité est inconnue.
            persistent map
            if isempty(map)
                map = DataManager.buildUnitMap();
            end
            if ~(ischar(unit) || (isstring(unit) && isscalar(unit)))
                error('MecaStruct:DataManager:unknownUnit', 'L''unité doit être un texte.');
            end
            u = DataManager.normalizeUnit(unit);
            if isKey(map, u)
                f = map(u);
                return
            end
            k = keys(map);
            hit = find(strcmpi(k, u));
            if isscalar(hit)
                f = map(k{hit});
                return
            end
            error('MecaStruct:DataManager:unknownUnit', 'Unité inconnue : « %s ».', char(unit));
        end

        function tf = hasSymbolic()
            %HASSYMBOLIC Disponibilité de la Symbolic Math Toolbox.
            %   tf = DataManager.hasSymbolic() : implémentation unique, appelée par tous les moteurs.
            persistent cached
            if isempty(cached)
                try
                    cached = logical(license('test', 'Symbolic_Toolbox')) && ~isempty(ver('symbolic'));
                catch
                    cached = false;
                end
            end
            tf = cached;
        end

        function keys = formulaKeys()
            %FORMULAKEYS Clés des fiches du formulaire rapide.
            %   keys = DataManager.formulaKeys() renvoie un cell ligne de 19 clés.
            keys = {'materiaux', 'geometrie', 'equilibre', 'cohesion', 'treillis', 'traction', ...
                'cisaillement', 'matage', 'torsion', 'flexion', 'deformee', 'energie', ...
                'mohr_integrales', 'flambage', 'tenseurs', 'mohr_cercle', 'criteres', 'hooke', ...
                'extensometrie'};
        end

        function sheet = formulaSheet(key)
            %FORMULASHEET Fiche de formules d'un thème (formulaire rapide).
            %   sheet = DataManager.formulaSheet(key) renvoie une structure colonne de champs
            %   title (texte français), latex (chaîne LaTeX MATLAB entre $...$, sous-ensemble
            %   autorisé, ASCII) et vars (définitions des variables avec unités SI).
            %   key : une des clés de DataManager.formulaKeys() (casse et accents ignorés).
            %   Erreur 'MecaStruct:DataManager:unknownFormulaKey' si la clé est inconnue.
            k = lower(DataManager.stripAccents(strtrim(char(string(key)))));
            switch k
                case 'materiaux',       C = DataManager.sheetMateriaux();
                case 'geometrie',       C = DataManager.sheetGeometrie();
                case 'equilibre',       C = DataManager.sheetEquilibre();
                case 'cohesion',        C = DataManager.sheetCohesion();
                case 'treillis',        C = DataManager.sheetTreillis();
                case 'traction',        C = DataManager.sheetTraction();
                case 'cisaillement',    C = DataManager.sheetCisaillement();
                case 'matage',          C = DataManager.sheetMatage();
                case 'torsion',         C = DataManager.sheetTorsion();
                case 'flexion',         C = DataManager.sheetFlexion();
                case 'deformee',        C = DataManager.sheetDeformee();
                case 'energie',         C = DataManager.sheetEnergie();
                case 'mohr_integrales', C = DataManager.sheetMohrIntegrales();
                case 'flambage',        C = DataManager.sheetFlambage();
                case 'tenseurs',        C = DataManager.sheetTenseurs();
                case 'mohr_cercle',     C = DataManager.sheetMohrCercle();
                case 'criteres',        C = DataManager.sheetCriteres();
                case 'hooke',           C = DataManager.sheetHooke();
                case 'extensometrie',   C = DataManager.sheetExtensometrie();
                otherwise
                    error('MecaStruct:DataManager:unknownFormulaKey', ...
                        'Clé de formulaire inconnue : « %s ». Clés valides : %s.', k, ...
                        strjoin(DataManager.formulaKeys(), ', '));
            end
            sheet = cell2struct(C, {'title', 'latex', 'vars'}, 2);
        end

        function P = sectionPresets()
            %SECTIONPRESETS Tubes et cornières courants (dimensions nominales, mm) pour remplir l'onglet Sections.
            %   P = DataManager.sectionPresets() : struct colonne, champs name, type ('rectangle_creux', 'couronne' ou 'L'),
            %   dims (struct : B, H, t | D, d | h, b, t, en mm). Séries usuelles : tubes carrés et rectangulaires EN 10219 /
            %   EN 10210, tubes ronds EN 10210, cornières à ailes égales EN 10056-1. Les caractéristiques sont calculées par
            %   l'application à partir de ces dimensions, congés et arrondis ignorés : l'écart avec les tables des fabricants
            %   est de quelques pour cent (la section réelle a des angles arrondis).
            rhs = [40 40 3; 50 50 3; 60 60 4; 80 80 4; 100 100 5; 120 120 5; 140 140 6; 150 150 6; 200 200 8; ...
                60 40 3; 80 40 3; 100 50 4; 120 80 5; 150 100 6; 200 100 6; 250 150 8];   % H, B, t
            chs = [33.7 3.2; 42.4 3.2; 48.3 3.2; 60.3 3.6; 76.1 3.6; 88.9 4; 114.3 4.5; 139.7 5; 168.3 5; 219.1 6.3; 273 8];   % D, t
            ang = [40 4; 50 5; 60 6; 70 7; 80 8; 100 10; 120 12; 150 15];   % côté, t
            P = struct('name', {}, 'type', {}, 'dims', {});
            for k = 1:size(rhs, 1)
                if rhs(k, 1) == rhs(k, 2)
                    nm = sprintf('SHS %gx%gx%g', rhs(k, 1), rhs(k, 2), rhs(k, 3));
                else
                    nm = sprintf('RHS %gx%gx%g', rhs(k, 1), rhs(k, 2), rhs(k, 3));
                end
                P(end + 1) = struct('name', nm, 'type', 'rectangle_creux', ...
                    'dims', struct('B', rhs(k, 2), 'H', rhs(k, 1), 't', rhs(k, 3))); %#ok<AGROW>
            end
            for k = 1:size(chs, 1)
                P(end + 1) = struct('name', sprintf('CHS %gx%g', chs(k, 1), chs(k, 2)), 'type', 'couronne', ...
                    'dims', struct('D', chs(k, 1), 'd', chs(k, 1) - 2 * chs(k, 2))); %#ok<AGROW>
            end
            for k = 1:size(ang, 1)
                P(end + 1) = struct('name', sprintf('L %gx%gx%g', ang(k, 1), ang(k, 1), ang(k, 2)), 'type', 'L', ...
                    'dims', struct('h', ang(k, 1), 'b', ang(k, 1), 't', ang(k, 2))); %#ok<AGROW>
            end
            P = P(:);
        end

        function T = mohrTable()
            %MOHRTABLE Table des intégrales de Mohr ∫_0^l Mi·Mj ds.
            %   T = DataManager.mohrTable() renvoie une structure colonne (25 entrées : toutes les
            %   combinaisons ordonnées de 5 formes) de champs :
            %     id          'forme1_x_forme2'
            %     shape1/2    'rectangle' | 'triangle' (0 à gauche, max à droite) |
            %                 'triangle_inverse' (max à gauche, 0 à droite) |
            %                 'trapeze' ([M_gauche M_droite]) | 'parabole' (charge uniforme, nulle aux
            %                 extrémités, flèche f au milieu : M(s) = 4 f s (l−s)/l²)
            %     latex       formule (a : valeurs du diagramme 1, b : valeurs du diagramme 2)
            %     fun         handle @(l, a, b) : a, b vecteurs des valeurs caractéristiques
            %                 (rectangle [M], triangle [M], trapèze [M1 M2], parabole [f])
            %     description texte français
            %   Exemples : triangle × triangle (même sens) l·a·b/3 ; sens opposés l·a·b/6 ;
            %   triangle × trapèze l/6·a·(b1 + 2 b2) ; trapèze × trapèze
            %   l/6·[a1(2b1+b2) + a2(b1+2b2)] ; parabole × parabole 8/15·l·a·b.
            sh = {'rectangle', 'triangle', 'triangle_inverse', 'trapeze', 'parabole'};
            C = {
                1, 1, @(l, a, b) l.*a(1).*b(1),                                   'l\,@A\,@B'
                1, 2, @(l, a, b) l.*a(1).*b(1)/2,                                 '\frac{l}{2}\,@A\,@B'
                1, 3, @(l, a, b) l.*a(1).*b(1)/2,                                 '\frac{l}{2}\,@A\,@B'
                1, 4, @(l, a, b) l.*a(1).*(b(1) + b(2))/2,                        '\frac{l}{2}\,@A\,\left(@B1 + @B2\right)'
                1, 5, @(l, a, b) 2*l.*a(1).*b(1)/3,                               '\frac{2\,l}{3}\,@A\,@B'
                2, 2, @(l, a, b) l.*a(1).*b(1)/3,                                 '\frac{l}{3}\,@A\,@B'
                2, 3, @(l, a, b) l.*a(1).*b(1)/6,                                 '\frac{l}{6}\,@A\,@B'
                2, 4, @(l, a, b) l.*a(1).*(b(1) + 2*b(2))/6,                      '\frac{l}{6}\,@A\,\left(@B1 + 2\,@B2\right)'
                2, 5, @(l, a, b) l.*a(1).*b(1)/3,                                 '\frac{l}{3}\,@A\,@B'
                3, 3, @(l, a, b) l.*a(1).*b(1)/3,                                 '\frac{l}{3}\,@A\,@B'
                3, 4, @(l, a, b) l.*a(1).*(2*b(1) + b(2))/6,                      '\frac{l}{6}\,@A\,\left(2\,@B1 + @B2\right)'
                3, 5, @(l, a, b) l.*a(1).*b(1)/3,                                 '\frac{l}{3}\,@A\,@B'
                4, 4, @(l, a, b) l.*(a(1).*(2*b(1) + b(2)) + a(2).*(b(1) + 2*b(2)))/6, ...
                '\frac{l}{6}\left[@A1\,\left(2\,@B1 + @B2\right) + @A2\,\left(@B1 + 2\,@B2\right)\right]'
                4, 5, @(l, a, b) l.*(a(1) + a(2)).*b(1)/3,                        '\frac{l}{3}\,\left(@A1 + @A2\right)\,@B'
                5, 5, @(l, a, b) 8*l.*a(1).*b(1)/15,                              '\frac{8\,l}{15}\,@A\,@B'
                };
            n = numel(sh);
            recs = cell(n, n);
            for k = 1:size(C, 1)
                i = C{k, 1};
                j = C{k, 2};
                f = C{k, 3};
                recs{i, j} = DataManager.mohrRecord(sh{i}, sh{j}, f, C{k, 4}, false);
                if i ~= j
                    g = @(l, a, b) f(l, b, a);
                    recs{j, i} = DataManager.mohrRecord(sh{j}, sh{i}, g, C{k, 4}, true);
                end
            end
            recs = recs.';
            T = vertcat(recs{:});
        end

        function charts = ktCharts()
            %KTCHARTS Abaques de coefficients de concentration de contrainte Kt disponibles.
            %   charts = DataManager.ktCharts() renvoie une structure colonne de champs :
            %     id          identifiant à passer à evalKt
            %     title       titre français
            %     params      cellstr des paramètres adimensionnels ({'d/W'} ou {'r/d','D/d'})
            %     ranges      matrice n×2 [min max] des domaines de validité (une ligne par paramètre)
            %     description texte français (géométrie, contrainte nominale, ajustement)
            %   et, en complément : paramFields (noms des champs de prm pour evalKt), curves
            %   (valeurs de D/d tabulées, [] pour la plaque), table ([D/d A b] de Peterson) et
            %   latex (formule de l'ajustement).
            c1 = struct('id', 'plaque_trou_traction', ...
                'title', 'Plaque percée d''un trou central, en traction', ...
                'params', {{'d/W'}}, ...
                'ranges', [0 1], ...
                'description', ['Plaque de largeur W et d''épaisseur t percée d''un trou central de ' ...
                'diamètre d, sollicitée en traction F. Kt est rapporté à la contrainte nominale sur ' ...
                'la section nette : σnom = F/((W − d)·t). Ajustement (Peterson) : ' ...
                'Kt = 3 − 3,13·(d/W) + 3,66·(d/W)² − 1,53·(d/W)³, pour 0 ≤ d/W < 1 (Kt ≥ 1).'], ...
                'paramFields', {{'dW'}}, ...
                'curves', [], ...
                'table', [], ...
                'latex', ['$K_t = 3 - 3{,}13\,\frac{d}{W} + 3{,}66\left(\frac{d}{W}\right)^2 - ' ...
                '1{,}53\left(\frac{d}{W}\right)^3 \qquad \sigma_{nom} = \frac{F}{(W-d)\,t}$']);
            ids = {'arbre_epaulement_flexion', 'arbre_epaulement_torsion', 'arbre_epaulement_traction'};
            titles = {'Arbre épaulé (congé r) en flexion', 'Arbre épaulé (congé r) en torsion', ...
                'Arbre épaulé (congé r) en traction'};
            nominal = {'σnom = 32·Mf/(π·d³)', 'τnom = 16·Mt/(π·d³)', 'σnom = 4·F/(π·d²)'};
            nomLatex = {'\sigma_{nom} = \frac{32\,M_f}{\pi\,d^3}', '\tau_{nom} = \frac{16\,M_t}{\pi\,d^3}', ...
                '\sigma_{nom} = \frac{4\,F}{\pi\,d^2}'};
            charts = c1;
            for k = 1:3
                tab = DataManager.petersonTable(ids{k});
                ck = struct('id', ids{k}, ...
                    'title', titles{k}, ...
                    'params', {{'r/d', 'D/d'}}, ...
                    'ranges', [0.01 0.30; tab(1, 1) tab(end, 1)], ...
                    'description', sprintf(['Arbre de diamètres D et d raccordés par un congé de rayon r. ' ...
                    'Contrainte nominale dans le petit diamètre : %s. Ajustement de Peterson ' ...
                    'Kt = A·(r/d)^b, A et b tabulés pour D/d = %s et interpolés linéairement en D/d ' ...
                    '(D/d hors table : valeurs de la borne la plus proche) ; validité 0,01 ≤ r/d ≤ 0,30 ; ' ...
                    'Kt ≥ 1.'], nominal{k}, strjoin(compose('%.4g', tab(:, 1).'), ' ; ')), ...
                    'paramFields', {{'rd', 'Dd'}}, ...
                    'curves', tab(:, 1).', ...
                    'table', tab, ...
                    'latex', ['$K_t = A\left(\frac{D}{d}\right)\,\left(\frac{r}{d}\right)^{b(D/d)} \qquad ' ...
                    nomLatex{k} '$']);
                charts(end + 1, 1) = ck; %#ok<AGROW>
            end
        end

        function [Kt, info] = evalKt(id, prm)
            %EVALKT Coefficient de concentration de contrainte Kt d'un abaque.
            %   Kt = DataManager.evalKt(id, prm)
            %   [Kt, info] = DataManager.evalKt(id, prm)
            %   id :
            %     'plaque_trou_traction'      prm = d/W (numérique, vectorisé) ou structure avec
            %                                 dW (ou d_W, dsurW) ou d et W
            %     'arbre_epaulement_flexion'  prm = [r/d, D/d] (ou matrice n×2) ou structure avec
            %     'arbre_epaulement_torsion'  rd (ou r_d, rsurd) et Dd (ou D_d, Dsurd), ou r, d, D
            %     'arbre_epaulement_traction' (rd vectorisé, Dd scalaire ou de même taille)
            %   Ajustements de Peterson Kt = A·(r/d)^b avec interpolation linéaire de A et b en D/d
            %   (D/d hors table : borne la plus proche) ; plaque : Kt = 3 − 3,13x + 3,66x² − 1,53x³,
            %   x = d/W. Résultat borné inférieurement à 1.
            %   info : id, A, b, inRange (logical, domaine de validité de ktCharts respecté),
            %   params, report (cell colonne), latex (cell).
            %   Erreurs : 'MecaStruct:DataManager:unknownKt', 'MecaStruct:DataManager:ktParams'.
            idc = lower(strtrim(char(string(id))));
            info = struct('id', idc, 'A', NaN, 'b', NaN, 'inRange', true, 'params', struct(), ...
                'report', {{}}, 'latex', {{}});
            switch idc
                case 'plaque_trou_traction'
                    x = DataManager.ktPlateParam(prm);
                    Kt = 3 - 3.13*x + 3.66*x.^2 - 1.53*x.^3;
                    Kt = max(Kt, 1);
                    info.params = struct('dW', x);
                    info.inRange = all(x(:) >= 0 & x(:) < 1);
                    info.report = {'Plaque percée d''un trou central en traction (section nette).'; ...
                        'Kt = 3 − 3,13·(d/W) + 3,66·(d/W)² − 1,53·(d/W)³'};
                    if isscalar(x)
                        info.report{end + 1, 1} = sprintf('d/W = %.4g  →  Kt = %.4g', x, Kt);
                        info.latex = {sprintf(['$K_t = 3 - 3{,}13 \\times %.4g + 3{,}66 \\times %.4g^2 - ' ...
                            '1{,}53 \\times %.4g^3 = %.4g$'], x, x, x, Kt)};
                    else
                        info.latex = {['$K_t = 3 - 3{,}13\,\frac{d}{W} + 3{,}66\left(\frac{d}{W}\right)^2 ' ...
                            '- 1{,}53\left(\frac{d}{W}\right)^3$']};
                    end
                case {'arbre_epaulement_flexion', 'arbre_epaulement_torsion', 'arbre_epaulement_traction'}
                    [rd, Dd] = DataManager.ktShaftParams(prm);
                    tab = DataManager.petersonTable(idc);
                    Ddc = min(max(Dd, tab(1, 1)), tab(end, 1));
                    A = interp1(tab(:, 1), tab(:, 2), Ddc, 'linear');
                    b = interp1(tab(:, 1), tab(:, 3), Ddc, 'linear');
                    Kt = max(A .* rd.^b, 1);
                    info.A = A;
                    info.b = b;
                    info.params = struct('rd', rd, 'Dd', Dd);
                    info.inRange = all(rd(:) >= 0.01 - 1e-12 & rd(:) <= 0.30 + 1e-12) ...
                        && all(Dd(:) >= tab(1, 1) - 1e-12 & Dd(:) <= tab(end, 1) + 1e-12);
                    modes = struct('arbre_epaulement_flexion', 'flexion', ...
                        'arbre_epaulement_torsion', 'torsion', 'arbre_epaulement_traction', 'traction');
                    info.report = {sprintf('Arbre épaulé en %s : ajustement de Peterson Kt = A·(r/d)^b.', ...
                        modes.(idc))};
                    if isscalar(rd) && isscalar(Dd)
                        info.report{end + 1, 1} = sprintf(['r/d = %.4g ; D/d = %.4g  →  A = %.5g ; ' ...
                            'b = %.5g (interpolation linéaire en D/d)'], rd, Dd, A, b);
                        info.report{end + 1, 1} = sprintf('Kt = %.5g × %.4g^(%.5g) = %.4g', A, rd, b, Kt);
                        info.latex = {sprintf('$K_t = A\\left(\\frac{r}{d}\\right)^{b} = %.5g \\times %.4g^{%.5g} = %.4g$', ...
                            A, rd, b, Kt)};
                    else
                        info.latex = {'$K_t = A\left(\frac{D}{d}\right)\,\left(\frac{r}{d}\right)^{b(D/d)}$'};
                    end
                    if any(Dd(:) ~= Ddc(:))
                        info.report{end + 1, 1} = sprintf(['Attention : D/d hors de la table [%.4g ; %.4g], ' ...
                            'coefficients de la borne la plus proche utilisés.'], tab(1, 1), tab(end, 1));
                    end
                otherwise
                    allCharts = DataManager.ktCharts();
                    names = {allCharts.id};
                    error('MecaStruct:DataManager:unknownKt', ...
                        'Abaque Kt inconnu : « %s ». Abaques disponibles : %s.', idc, strjoin(names, ', '));
            end
            if ~info.inRange
                info.report{end + 1, 1} = 'Attention : paramètres hors du domaine de validité de l''abaque (extrapolation).';
            end
        end

        function T = bearingTableDefault()
            %BEARINGTABLEDEFAULT Table par défaut des pressions admissibles de matage.
            %   T = DataManager.bearingTableDefault() : table (Liaison, Conditions, Pmin, Pmax (Pa),
            %   Note) pour clavette / cannelures (fixe, glissant sans charge, glissant sous charge)
            %   × conditions (médiocres, moyennes, très bonnes) — valeurs usuelles du Guide du
            %   dessinateur — complétée par une articulation (axe pivotant sous charge) pour
            %   couvrir les faibles valeurs. Plage globale 0,5 à 150 MPa.
            lia = ["Clavette / cannelures - fixe"; ...
                "Clavette / cannelures - glissant sans charge"; ...
                "Clavette / cannelures - glissant sous charge"; ...
                "Articulation - axe pivotant sous charge"];
            cond = ["médiocres", "moyennes", "très bonnes"];
            P = [35 50 60 100 80 150
                15 20 20 30 25 40
                3 10 5 15 10 20
                0.5 2 2 5 5 10];
            condTxt = ["conditions médiocres : chocs, vibrations, ajustement ou lubrification médiocres", ...
                "conditions moyennes : fonctionnement courant", ...
                "très bonnes conditions : charge régulière, ajustement précis, bonne lubrification"];
            src = ["Valeur usuelle (Guide du dessinateur industriel)", ...
                "Valeur usuelle (Guide du dessinateur industriel)", ...
                "Valeur usuelle (Guide du dessinateur industriel)", ...
                "Valeur usuelle (axe acier traité dans bague bronze, rotation ou oscillation sous charge ; complète la plage 0,5 à 150 MPa)"];
            n = numel(lia)*numel(cond);
            Liaison = strings(n, 1);
            Conditions = strings(n, 1);
            Pmin = zeros(n, 1);
            Pmax = zeros(n, 1);
            Note = strings(n, 1);
            r = 0;
            for i = 1:numel(lia)
                for j = 1:numel(cond)
                    r = r + 1;
                    Liaison(r) = lia(i);
                    Conditions(r) = cond(j);
                    Pmin(r) = P(i, 2*j - 1)*1e6;
                    Pmax(r) = P(i, 2*j)*1e6;
                    Note(r) = src(i) + " ; " + condTxt(j) + ".";
                end
            end
            T = table(Liaison, Conditions, Pmin, Pmax, Note);
        end
    end

    %% =========================================================================================
    %  Méthodes statiques privées : données par défaut
    %  =========================================================================================
    methods (Static, Access = private)

        function T = defaultMaterialsTable()
            % Base matériaux par défaut (valeurs du cours, complétées par des valeurs usuelles).
            mats = {};
            % --- Aciers d'usage général (cours : E = 190 GPa, α = 12e-6, ν = 0,3)
            catAG = 'Acier d''usage général';
            nuances = {'S185', 185, 290; 'S235', 235, 340; 'S275', 275, 410; 'S355', 355, 490};
            for k = 1:size(nuances, 1)
                mats{end + 1} = DataManager.mat(nuances{k, 1}, catAG, 190e9, NaN, 0.3, ...
                    nuances{k, 2}*1e6, nuances{k, 3}*1e6, 12e-6, 7850, ...
                    sprintf(['Cours : E = 190 GPa, ν = 0,3, α = 12e-6 /°C, Re = %d MPa, Rm = %d MPa ' ...
                    '(plage du cours : Re = 185 à 355 MPa, Rm = 290 à 490 MPa). ρ : valeur usuelle.'], ...
                    nuances{k, 2}, nuances{k, 3})); %#ok<AGROW>
            end
            % --- Aciers de construction mécanique (cours : E = 210 GPa, G = 80 GPa, ν = 0,3)
            catXC = 'Acier de construction mécanique';
            xc = {'XC 38', 320, 550; 'XC 42', 340, 590; 'XC 48', 360, 630};
            for k = 1:size(xc, 1)
                mats{end + 1} = DataManager.mat(xc{k, 1}, catXC, 210e9, 80e9, 0.3, ...
                    xc{k, 2}*1e6, xc{k, 3}*1e6, 11e-6, 7850, ...
                    sprintf(['Cours : E = 210 GPa, G = 80 GPa, ν = 0,3, α = 10 à 12,5e-6 /°C ' ...
                    '(11e-6 retenu). Re = %d MPa et Rm = %d MPa : valeurs usuelles (état normalisé, ' ...
                    'à adapter au traitement thermique). ρ : valeur usuelle.'], xc{k, 2}, xc{k, 3})); %#ok<AGROW>
            end
            % --- Alliages d'aluminium (cours corrigé : E = 90 GPa et G = 32 GPa -> 70 et 27 GPa)
            catAl = 'Alliage d''aluminium';
            al = {'Aluminium 5356', 2640};   % l'Aluminium 2017 vient de la fiche Euralliage (plus bas)
            for k = 1:size(al, 1)
                mats{end + 1} = DataManager.mat(al{k, 1}, catAl, 70e9, 27e9, 0.3, 200e6, 300e6, ...
                    23e-6, al{k, 2}, ...
                    ['Valeurs corrigées : le support de cours donne E = 90 GPa et G = 32 GPa, ' ...
                    'incohérents avec les alliages d''aluminium (E ≈ 70 à 74 GPa). Retenu : ' ...
                    'E = 70 GPa, G = 27 GPa, ν = 0,3, α = 23e-6 /°C (EN 1999-1-1, §3.2.5). ' ...
                    'Re = 200 MPa et Rm = 300 MPa : bornes basses du cours (200 à 220 et 300 à 320 MPa). ' ...
                    'ρ : valeur usuelle.']); %#ok<AGROW>
            end
            % --- Titane TA6V (cours corrigé : Re et Rm d'un titane non allié -> valeurs du TA6V recuit)
            mats{end + 1} = DataManager.mat('Titane TA6V', 'Alliage de titane', 116e9, NaN, 0.34, ...
                830e6, 900e6, 9e-6, 4430, ...
                ['Valeurs corrigées : le support de cours donne Re = 100 à 120 MPa et ' ...
                'Rm = 300 à 350 MPa, valeurs d''un titane non allié. Retenu pour le TA6V recuit : ' ...
                'Re = 830 MPa et Rm = 900 MPa (valeurs usuelles : Re ≈ 830–880 MPa, Rm ≈ 900–950 MPa, ' ...
                'bornes basses). E = 116 GPa et α = 9e-6 /°C (milieu de 8,5 à 9,5) : valeurs du cours. ' ...
                'ν = 0,34 et ρ : valeurs usuelles.']);
            % --- Fontes (cours : G = 40 GPa)
            mats{end + 1} = DataManager.mat('FGL 200', 'Fonte', 100e9, 40e9, 0.26, 130e6, 200e6, ...
                11e-6, 7200, ...
                ['Cours : G = 40 GPa (fontes). Valeurs usuelles (EN-GJL-200) : E = 100 GPa ' ...
                '(88 à 113 GPa), ν = 0,26, Rm = 200 MPa, α ≈ 10 à 12e-6 /°C, ρ = 7200 kg/m³. ' ...
                'Fonte grise fragile sans limite élastique franche : Re = Rp0,1 ≈ 130 MPa ; ' ...
                'utiliser le critère de la contrainte normale maximale.']);
            mats{end + 1} = DataManager.mat('FGL 250', 'Fonte', 103e9, 40e9, 0.26, 165e6, 250e6, ...
                11e-6, 7200, ...
                ['Cours : G = 40 GPa (fontes). Valeurs usuelles (EN-GJL-250) : E = 103 GPa ' ...
                '(103 à 118 GPa), ν = 0,26, Rm = 250 MPa, α ≈ 10 à 12e-6 /°C, ρ = 7200 kg/m³. ' ...
                'Fonte grise fragile sans limite élastique franche : Re = Rp0,1 ≈ 165 MPa ; ' ...
                'utiliser le critère de la contrainte normale maximale.']);
            mats{end + 1} = DataManager.mat('FGS 400-15', 'Fonte', 169e9, 40e9, 0.275, 250e6, 400e6, ...
                12.5e-6, 7100, ...
                ['Cours : G = 40 GPa (fontes). Valeurs usuelles (EN-GJS-400-15, fonte à graphite ' ...
                'sphéroïdal) : E = 169 GPa, ν = 0,275, Re = Rp0,2 = 250 MPa, Rm = 400 MPa, ' ...
                'α = 12,5e-6 /°C, ρ = 7100 kg/m³. G usuel ≈ 66 GPa.']);
            % --- Laiton (cours : G = 34 GPa)
            mats{end + 1} = DataManager.mat('Laiton CuZn39Pb3', 'Alliage de cuivre', 96e9, 34e9, 0.37, ...
                250e6, 430e6, 20.9e-6, 8400, ...
                ['Cours : G = 34 GPa (laiton). CW614N, laiton de décolletage, barre état R430 (fiche Euralliage « CuZn39Pb3 ») : ' ...
                'Rm = 430 MPa, Rp0,2 ≈ 250 MPa (valeur indicative de la fiche, mise entre parenthèses), ρ = 8,4 g/cm³. ' ...
                'E = 96 GPa, ν = 0,37 et α = 20,9e-6 /°C : valeurs usuelles (absentes de la fiche).']);
            % --- Plexiglas (cours corrigé : G = 1,1 GPa)
            mats{end + 1} = DataManager.mat('Plexiglas (PMMA)', 'Polymère', 3.0e9, 1.1e9, 0.37, ...
                65e6, 70e6, 70e-6, 1190, ...
                ['G = 1,1 GPa : le support indique 11 GPa, incohérent avec E ≈ 3 GPa ; 1,1 GPa ' ...
                'retenu. Valeurs usuelles : E = 3 GPa, ν = 0,37, Rm ≈ 70 MPa, α ≈ 70e-6 /°C, ' ...
                'ρ = 1190 kg/m³. Matériau fragile sans limite élastique franche : Re ≈ 65 MPa.']);
            % --- Bois et béton : matériau supposé homogène, élastique et isotrope (voir les notes)
            woods = {'Bois C24 (EN 338)', 11e9, 0.69e9, 24e6, 24e6, 5e-6, 420, ...
                ['Résineux C24, EN 338 : E0,mean = 11 GPa (le long des fibres), G,mean = 0,69 GPa, fm,k = 24 MPa (flexion), ρmean = 420 kg/m³, ' ...
                'α ≈ 5e-6 /°C (EN 1995-1-1). Re = Rm = fm,k (valeur caractéristique, à diviser par γM et multiplier par kmod). ' ...
                'Bois orthotrope : G ≠ E/(2(1+ν)), pas de cohérence isotrope ; contraintes admissibles transversales très inférieures. ν = 0,3 par défaut.']
                'Lamellé-collé GL24h (EN 14080)', 11.5e9, 0.65e9, 24e6, 24e6, 5e-6, 420, ...
                ['Lamellé-collé homogène GL24h, EN 14080 : E0,g,mean = 11,5 GPa, G,g,mean = 0,65 GPa, fm,g,k = 24 MPa, ρmean ≈ 420 kg/m³, α ≈ 5e-6 /°C. ' ...
                'Re = Rm = fm,g,k caractéristique (diviser par γM, multiplier par kmod). Orthotrope : G ≠ E/(2(1+ν)), pas de cohérence isotrope. ν = 0,3 par défaut.']};
            for k = 1:size(woods, 1)
                mats{end + 1} = DataManager.mat(woods{k, 1}, 'Bois', woods{k, 2}, woods{k, 3}, 0.3, woods{k, 4}, woods{k, 5}, ...
                    woods{k, 6}, woods{k, 7}, woods{k, 8}); %#ok<AGROW>
            end
            concretes = {'Béton C25/30 (EN 1992-1-1)', 31e9, 25e6, 33e6; 'Béton C30/37 (EN 1992-1-1)', 33e9, 30e6, 38e6};
            for k = 1:size(concretes, 1)
                mats{end + 1} = DataManager.mat(concretes{k, 1}, 'Béton', concretes{k, 2}, 0.4 * concretes{k, 2}, 0.2, ...
                    concretes{k, 3}, concretes{k, 4}, 10e-6, 2500, ...
                    sprintf(['EN 1992-1-1, tableau 3.1 : Ecm = %.0f GPa, fck = %.0f MPa (Re), fcm = %.0f MPa (Rm), ν = 0,2, G ≈ 0,4·Ecm, α = 10e-6 /°C, ' ...
                    'ρ = 2500 kg/m³ (béton armé). ATTENTION : béton non fissuré, élastique linéaire ; la résistance en traction est négligeable, ' ...
                    'donc l''application ne dimensionne pas le béton armé (voir EN 1992).'], concretes{k, 2} / 1e9, concretes{k, 3} / 1e6, concretes{k, 4} / 1e6)); %#ok<AGROW>
            end
            mats = [mats, DataManager.euralliageMaterials()];
            rows = cell(numel(mats), 1);
            for k = 1:numel(mats)
                m = DataManager.completeIsotropic(mats{k});
                rows{k} = DataManager.materialRow(m, false);
            end
            T = vertcat(rows{:});
        end

        function mats = euralliageMaterials()
            %EURALLIAGEMATERIALS Alliages d'aluminium et de cuivre tirés des fiches du site Euralliage (euralliage.com).
            %   Rm et Rp0,2 : valeurs MINIMALES des fiches (normes EN 485-2, EN 755-2/754-2, EN 12163/12164, EN 1652), état et produit
            %   cités dans chaque note. Aluminium : E, G, ν, α, ρ de la fiche. Cuivre et alliages : la fiche ne donne ni E ni α,
            %   ni G : valeurs usuelles (notées). Les valeurs entre parenthèses de la fiche (Rp0,2 indicatif) sont reprises
            %   telles quelles et signalées. Fiches consultées en octobre 2026 : tableaux parfois mal alignés, à confirmer
            %   dans la norme ou chez le fournisseur avant tout dimensionnement.
            src = 'Source : Euralliage (euralliage.com), fiche ';
            mats = {};
            % --- aluminium : {nom, E GPa, G GPa, Re, Rm, α µm/m/K, ρ, ν, note}
            al = {
                'Aluminium 2017', 72.5, 27.2, 260, 380, 22.9, 2790, 0.33, ...
                    '2017A (EN AW-AlCu4MgSi(A)), barre filée état T4 < 25 mm : Rm 380, Rp0,2 260 MPa.'
                'Aluminium 1050A-H14', 69, 25.9, 85, 105, 23.5, 2700, 0.33, ...
                    '1050A (pur), tôle H14 : Rm 105 à 145, Rp0,2 85 MPa minimum (Rm = borne basse).'
                'Aluminium 3003-H14', 69.5, 26.1, 125, 145, 23.1, 2730, 0.33, ...
                    '3003, tôle H14 : Rm 145 à 185, Rp0,2 125 MPa minimum (Rm = borne basse).'
                'Aluminium 5052-H32', 69, 25.9, 130, 210, 23.5, 2700, 0.33, ...
                    '5052, tôle H22/H32 : Rm 210 à 260, Rp0,2 130 MPa minimum (Rm = borne basse).'
                'Aluminium 5754-H22', 70.5, 26.5, 130, 220, 23.7, 2680, 0.33, ...
                    '5754, tôle H22/H32 : Rm 220 à 270, Rp0,2 130 MPa minimum (Rm = borne basse).'
                'Aluminium 5083-H116', 71, 26.8, 200, 285, 23.8, 2660, 0.33, ...
                    '5083 (marine), tôle H116 : Rm 285 à 305, Rp0,2 200 à 215 MPa (bornes basses).'
                'Aluminium 6060-T6', 69.5, 26.1, 140, 170, 23.4, 2700, 0.33, ...
                    '6060, profilé filé T6, épaisseur 3 à 25 mm : Rm 170, Rp0,2 140 MPa. E, G, α de la fiche (état T5).'
                'Aluminium 6061-T6', 70, 26.3, 240, 290, 23.3, 2700, 0.33, ...
                    '6061, tôle T6 de 0,4 à 12,5 mm : Rm 290, Rp0,2 240 MPa.'
                'Aluminium 6082-T6', 70, 26.4, 255, 310, 23.1, 2710, 0.33, ...
                    '6082, barre étirée T6 : Rm 310, Rp0,2 255 MPa.'
                'Aluminium 2024-T351', 73, 27.4, 310, 425, 23.1, 2790, 0.33, ...
                    '2024, barre étirée T351 < 80 mm : Rm 425, Rp0,2 310 MPa. E, G, α de la fiche (état O).'
                'Aluminium 7075-T6', 72, 27.1, 460, 520, 23.5, 2810, 0.33, ...
                    '7075, barre étirée T6 < 80 mm : Rm 520, Rp0,2 460 MPa.'};
            for k = 1:size(al, 1)
                mats{end + 1} = DataManager.mat(al{k, 1}, 'Alliage d''aluminium', al{k, 2} * 1e9, al{k, 3} * 1e9, al{k, 8}, ...
                    al{k, 4} * 1e6, al{k, 5} * 1e6, al{k, 6} * 1e-6, al{k, 7}, [src 'de l''alliage. ' al{k, 9}]); %#ok<AGROW>
            end
            % --- cuivre et alliages : {nom, catégorie, E GPa, ν, Re, Rm, α, ρ, note}
            cu = {
                'Cuivre Cu-a1 (recuit)', 'Cuivre', 120, 0.34, 60, 230, 16.5, 8900, ...
                    'Cu-a1, état O (recuit) : Rm 230, Rp0,2 60 MPa, ρ 8,90 g/cm³ (page « alliages de cuivre »).'
                'Cuivre Cu-a1 (écroui H14)', 'Cuivre', 120, 0.34, 320, 350, 16.5, 8900, ...
                    'Cu-a1, état H14 : Rm 350, Rp0,2 320 MPa, ρ 8,90 g/cm³.'
                'Cuivre-chrome-zirconium CuCrZr (TER)', 'Alliage de cuivre', 130, 0.33, 400, 470, 17, 8940, ...
                    'CuCrZr, état traité (TER) : Rm 470, Rp0,2 400 MPa, ρ 8,94 g/cm³.'
                'Cuivre-béryllium CuBe2 (TER)', 'Alliage de cuivre', 130, 0.30, 1230, 1390, 17, 8500, ...
                    'CuBe2, état traité (TER) : Rm 1390, Rp0,2 1230 MPa, ρ 8,50 g/cm³.'
                'Laiton CuZn33 (recuit)', 'Alliage de cuivre', 105, 0.37, 120, 340, 20, 8500, ...
                    'CuZn33, état O : Rm 340, Rp0,2 120 MPa, ρ 8,50 g/cm³.'
                'Laiton CuZn33 (écroui H14)', 'Alliage de cuivre', 105, 0.37, 430, 525, 20, 8500, ...
                    'CuZn33, état H14 : Rm 525, Rp0,2 430 MPa, ρ 8,50 g/cm³.'
                'Laiton CuZn36Pb3 (H)', 'Alliage de cuivre', 100, 0.37, 300, 390, 20.5, 8500, ...
                    'CuZn36Pb3, état H : Rm 390, Rp0,2 300 MPa, ρ 8,50 g/cm³.'
                'Laiton CuZn40Pb3 (H)', 'Alliage de cuivre', 100, 0.37, 350, 430, 20.5, 8500, ...
                    'CuZn40Pb3, état H : Rm 430, Rp0,2 350 MPa, ρ 8,50 g/cm³.'
                'Laiton CuZn38Sn1 (recuit)', 'Alliage de cuivre', 100, 0.37, 200, 400, 20.5, 8450, ...
                    'CuZn38Sn1, état O : Rm 400, Rp0,2 200 MPa, ρ 8,45 g/cm³.'
                'Laiton CuZn23Al4', 'Alliage de cuivre', 110, 0.35, 400, 700, 20, 7800, ...
                    'CuZn23Al4 : Rm 700, Rp0,2 400 MPa (état non précisé par la fiche), ρ 7,80 g/cm³.'
                'Laiton CuZn37 R370 (CW508L)', 'Alliage de cuivre', 105, 0.37, 300, 370, 20.2, 8400, ...
                    'CuZn37 (CW508L), barre Ø 2 à 40 mm état R370 : Rm 370 MPa, Rp0,2 (300) MPa indicatif, ρ 8,4 g/cm³.'
                'Laiton CuZn37 R440 (CW508L)', 'Alliage de cuivre', 105, 0.37, 400, 440, 20.2, 8400, ...
                    'CuZn37 (CW508L), barre Ø 2 à 10 mm état R440 : Rm 440 MPa, Rp0,2 (400) MPa indicatif, ρ 8,4 g/cm³.'
                'Laiton CuZn39Pb2 R410 (CW612N)', 'Alliage de cuivre', 100, 0.37, 250, 410, 20.5, 8400, ...
                    'CuZn39Pb2 (CW612N), barre de décolletage état R410 : Rm 410 MPa, Rp0,2 (250) MPa indicatif, ρ 8,4 g/cm³.'
                'Bronze CuSn6 R400 (CW452K)', 'Alliage de cuivre', 115, 0.34, 250, 400, 18.5, 8800, ...
                    'CuSn6 (CW452K), barre Ø 2 à 60 mm état R400 : Rm 400 MPa, Rp0,2 (250) MPa indicatif, ρ 8,8 g/cm³ (valeur minimale).'
                'Bronze CuSn6 R470 (CW452K)', 'Alliage de cuivre', 115, 0.34, 350, 470, 18.5, 8800, ...
                    'CuSn6 (CW452K), barre état R470 : Rm 470 MPa, Rp0,2 (350) MPa indicatif, ρ 8,8 g/cm³ (valeur minimale).'
                'Bronze CuSn8 R450 (CW453K)', 'Alliage de cuivre', 115, 0.34, 280, 450, 18.5, 8800, ...
                    'CuSn8 (CW453K), barre Ø 2 à 40 mm état R450 : Rm 450 MPa, Rp0,2 (280) MPa indicatif, ρ 8,8 g/cm³ (valeur minimale).'
                'Bronze CuSn8 R550 (CW453K)', 'Alliage de cuivre', 115, 0.34, 430, 550, 18.5, 8800, ...
                    'CuSn8 (CW453K), barre Ø 2 à 12 mm état R550 : Rm 550 MPa, Rp0,2 (430) MPa indicatif, ρ 8,8 g/cm³ (valeur minimale).'
                'Bronze CuSn9P (recuit)', 'Alliage de cuivre', 115, 0.34, 210, 405, 18.5, 8800, ...
                    'CuSn9P, état O : Rm 405, Rp0,2 210 MPa, ρ 8,80 g/cm³ (page « alliages de cuivre »).'
                'Bronze CuSn9P (écroui H14)', 'Alliage de cuivre', 115, 0.34, 730, 740, 18.5, 8800, ...
                    'CuSn9P, état H14 : Rm 740, Rp0,2 730 MPa, ρ 8,80 g/cm³.'
                'Cupro-aluminium CuAl9Ni3Fe2 (recuit)', 'Alliage de cuivre', 120, 0.33, 250, 690, 16.5, 7700, ...
                    'CuAl9Ni3Fe2, état O : Rm 690, Rp0,2 250 MPa, ρ 7,70 g/cm³ (page « alliages de cuivre »).'
                'Cupro-aluminium CuAl10Ni5Fe4 R680 (CW307G)', 'Alliage de cuivre', 120, 0.33, 480, 680, 16.2, 7600, ...
                    'CuAl10Ni5Fe4 (CW307G), barre Ø 10 à 80 mm état R680 : Rm 680 MPa, Rp0,2 (480) MPa indicatif, ρ 7,6 g/cm³.'
                'Cupro-aluminium CuAl10Ni5Fe4 R740 (CW307G)', 'Alliage de cuivre', 120, 0.33, 530, 740, 16.2, 7600, ...
                    'CuAl10Ni5Fe4 (CW307G), barre Ø 10 à 80 mm état R740 : Rm 740 MPa, Rp0,2 (530) MPa indicatif, ρ 7,6 g/cm³.'};
            for k = 1:size(cu, 1)
                mats{end + 1} = DataManager.mat(cu{k, 1}, cu{k, 2}, cu{k, 3} * 1e9, NaN, cu{k, 4}, cu{k, 5} * 1e6, cu{k, 6} * 1e6, ...
                    cu{k, 7} * 1e-6, cu{k, 8}, [src 'de l''alliage. ' cu{k, 9} ' E, ν et α : valeurs usuelles (la fiche n''en donne pas) ; G = E/(2(1+ν)).']); %#ok<AGROW>
            end
        end

        function m = mat(name, category, E, G, nu, Re, Rm, alpha, rho, note)
            % Construction d'une structure matériau (SI).
            m = struct('Name', name, 'Category', category, 'E', E, 'G', G, 'nu', nu, 'Re', Re, ...
                'Rm', Rm, 'alpha', alpha, 'rho', rho, 'Note', note);
        end

        function P = defaultProfiles()
            % Catalogue des profilés européens (valeurs ArcelorMittal / tables européennes).
            % Colonnes des matrices (unités catalogue) :
            % [désignation h b a(tw) e(tf) r (mm)  A (cm²)  masse (kg/m)
            %  Iy_EC (cm⁴) Wel,y_EC (cm³) iy_EC (cm)  Iz_EC (cm⁴) Wel,z_EC (cm³) iz_EC (cm)  c (cm)]
            % Conversion : Iz(app) = Iy_EC (axe fort), Iy(app) = Iz_EC (axe faible), idem W et r.
            % UPN/UAP : Wel,z_EC = Iz_EC/(b − c) (fibre la plus éloignée du centre de gravité),
            % c = distance dos d'âme → centre de gravité.
            IPN = [ ...
                80  80  42  3.9  5.9  3.9   7.57  5.94   77.67  19.42  3.20    6.29   3.00  0.91  NaN
                100 100 50  4.5  6.8  4.5  10.6   8.34  171     34.2   4.01   12.2    4.88  1.07  NaN
                120 120 58  5.1  7.7  5.1  14.2  11.1   328     54.7   4.81   21.5    7.41  1.23  NaN
                140 140 66  5.7  8.6  5.7  18.2  14.3   573     81.9   5.61   35.2   10.7   1.40  NaN
                160 160 74  6.3  9.5  6.3  22.8  17.9   935    117     6.40   54.7   14.8   1.55  NaN
                180 180 82  6.9 10.4  6.9  27.9  21.9  1450    161     7.20   81.3   19.8   1.71  NaN
                200 200 90  7.5 11.3  7.5  33.4  26.2  2140    214     8.00  117     26.0   1.87  NaN
                220 220 98  8.1 12.2  8.1  39.5  31.1  3060    278     8.80  162     33.1   2.02  NaN
                240 240 106 8.7 13.1  8.7  46.1  36.2  4250    354     9.59  221     41.7   2.20  NaN
                260 260 113 9.4 14.1  9.4  53.3  41.9  5740    442    10.4   288     51.0   2.32  NaN
                280 280 119 10.1 15.2 10.1 61.0  47.9  7590    542    11.1   364     61.2   2.45  NaN
                300 300 125 10.8 16.2 10.8 69.0  54.2  9800    653    11.9   451     72.2   2.56  NaN];
            IPE = [ ...
                80  80  46  3.8  5.2  5    7.64   6.0    80.14  20.03  3.24    8.49   3.69  1.05  NaN
                100 100 55  4.1  5.7  7   10.32   8.1   171.0   34.20  4.07   15.92   5.79  1.24  NaN
                120 120 64  4.4  6.3  7   13.21  10.4   317.8   52.96  4.90   27.67   8.65  1.45  NaN
                140 140 73  4.7  6.9  7   16.43  12.9   541.2   77.32  5.74   44.92  12.31  1.65  NaN
                160 160 82  5.0  7.4  9   20.09  15.8   869.3  108.7   6.58   68.31  16.66  1.84  NaN
                180 180 91  5.3  8.0  9   23.95  18.8  1317    146.3   7.42  100.9   22.16  2.05  NaN
                200 200 100 5.6  8.5 12   28.48  22.4  1943    194.3   8.26  142.4   28.47  2.24  NaN
                220 220 110 5.9  9.2 12   33.37  26.2  2772    252.0   9.11  204.9   37.25  2.48  NaN
                240 240 120 6.2  9.8 15   39.12  30.7  3892    324.3   9.97  283.6   47.27  2.69  NaN
                270 270 135 6.6 10.2 15   45.95  36.1  5790    428.9  11.23  419.9   62.20  3.02  NaN
                300 300 150 7.1 10.7 15   53.81  42.2  8356    557.1  12.46  603.8   80.50  3.35  NaN
                330 330 160 7.5 11.5 18   62.61  49.1 11770    713.1  13.71  788.1   98.52  3.55  NaN
                360 360 170 8.0 12.7 18   72.73  57.1 16270    903.6  14.95 1043    122.8   3.79  NaN
                400 400 180 8.6 13.5 21   84.46  66.3 23130   1156    16.55 1318    146.4   3.95  NaN
                450 450 190 9.4 14.6 21   98.82  77.6 33740   1500    18.48 1676    176.4   4.12  NaN
                500 500 200 10.2 16.0 21 115.5   90.7 48200   1928    20.43 2142    214.2   4.31  NaN
                550 550 210 11.1 17.2 24 134.4  105.5 67120   2441    22.35 2668    254.1   4.45  NaN
                600 600 220 12.0 19.0 24 156.0  122.4 92080   3069    24.30 3387    307.9   4.66  NaN];
            HEA = [ ...
                100 96  100 5.0  8.0 12   21.24  16.7    349.2   72.76  4.06   133.8   26.76  2.51  NaN
                120 114 120 5.0  8.0 12   25.34  19.9    606.2  106.3   4.89   230.9   38.48  3.02  NaN
                140 133 140 5.5  8.5 12   31.42  24.7   1033    155.4   5.73   389.3   55.62  3.52  NaN
                160 152 160 6.0  9.0 15   38.77  30.4   1673    220.1   6.57   615.6   76.95  3.98  NaN
                180 171 180 6.0  9.5 15   45.25  35.5   2510    293.6   7.45   924.6  102.7   4.52  NaN
                200 190 200 6.5 10.0 18   53.83  42.3   3692    388.6   8.28  1336    133.6   4.98  NaN
                220 210 220 7.0 11.0 18   64.34  50.5   5410    515.2   9.17  1955    177.7   5.51  NaN
                240 230 240 7.5 12.0 21   76.84  60.3   7763    675.1  10.05  2769    230.7   6.00  NaN
                260 250 260 7.5 12.5 24   86.82  68.2  10450    836.4  10.97  3668    282.1   6.50  NaN
                280 270 280 8.0 13.0 24   97.26  76.4  13670   1013    11.86  4763    340.2   7.00  NaN
                300 290 300 8.5 14.0 27  112.5   88.3  18260   1260    12.74  6310    420.6   7.49  NaN
                320 310 300 9.0 15.5 27  124.4   97.6  22930   1479    13.58  6985    465.7   7.49  NaN
                340 330 300 9.5 16.5 27  133.5  104.8  27690   1678    14.40  7436    495.7   7.46  NaN
                360 350 300 10.0 17.5 27 142.8  112.1  33090   1891    15.22  7887    525.8   7.43  NaN
                400 390 300 11.0 19.0 27 159.0  124.8  45070   2311    16.84  8564    570.9   7.34  NaN
                450 440 300 11.5 21.0 27 178.0  139.8  63720   2896    18.92  9465    631.0   7.29  NaN
                500 490 300 12.0 23.0 27 197.5  155.1  86970   3550    20.98 10370    691.1   7.24  NaN
                550 540 300 12.5 24.0 27 211.8  166.2 111900   4146    22.99 10820    721.3   7.15  NaN
                600 590 300 13.0 25.0 27 226.5  177.8 141200   4787    24.97 11270    751.4   7.05  NaN];
            HEB = [ ...
                100 100 100 6.0 10.0 12   26.04  20.4    449.5   89.91  4.16   167.3   33.45  2.53  NaN
                120 120 120 6.5 11.0 12   34.01  26.7    864.4  144.1   5.04   317.5   52.92  3.06  NaN
                140 140 140 7.0 12.0 12   42.96  33.7   1509    215.6   5.93   549.7   78.52  3.58  NaN
                160 160 160 8.0 13.0 15   54.25  42.6   2492    311.5   6.78   889.2  111.2   4.05  NaN
                180 180 180 8.5 14.0 15   65.25  51.2   3831    425.7   7.66  1363    151.4   4.57  NaN
                200 200 200 9.0 15.0 18   78.08  61.3   5696    569.6   8.54  2003    200.3   5.07  NaN
                220 220 220 9.5 16.0 18   91.04  71.5   8091    735.5   9.43  2843    258.5   5.59  NaN
                240 240 240 10.0 17.0 21 106.0   83.2  11260    938.3  10.31  3923    326.9   6.08  NaN
                260 260 260 10.0 17.5 24 118.4   93.0  14920   1148    11.22  5135    395.0   6.58  NaN
                280 280 280 10.5 18.0 24 131.4  103.1  19270   1376    12.11  6595    471.0   7.09  NaN
                300 300 300 11.0 19.0 27 149.1  117.0  25170   1678    12.99  8563    570.9   7.58  NaN
                320 320 300 11.5 20.5 27 161.3  126.7  30820   1926    13.82  9239    615.9   7.57  NaN
                340 340 300 12.0 21.5 27 170.9  134.2  36660   2156    14.65  9690    646.0   7.53  NaN
                360 360 300 12.5 22.5 27 180.6  141.8  43190   2400    15.46 10140    676.1   7.49  NaN
                400 400 300 13.5 24.0 27 197.8  155.3  57680   2884    17.08 10820    721.3   7.40  NaN
                450 450 300 14.0 26.0 27 218.0  171.1  79890   3551    19.14 11720    781.4   7.33  NaN
                500 500 300 14.5 28.0 27 238.6  187.3 107200   4287    21.19 12620    841.6   7.27  NaN
                550 550 300 15.0 29.0 27 254.1  199.4 136700   4971    23.20 13080    871.8   7.17  NaN
                600 600 300 15.5 30.0 27 270.0  211.9 171000   5701    25.17 13530    902.0   7.08  NaN];
            UPN = [ ...
                80  80  45  6.0  8.0  8.0  11.0   8.64   106     26.5   3.10   19.4    6.36  1.33  1.45
                100 100 50  6.0  8.5  8.5  13.5  10.6    206     41.2   3.91   29.3    8.49  1.47  1.55
                120 120 55  7.0  9.0  9.0  17.0  13.4    364     60.7   4.62   43.2   11.1   1.59  1.60
                140 140 60  7.0 10.0 10.0  20.4  16.0    605     86.4   5.45   62.7   14.8   1.75  1.75
                160 160 65  7.5 10.5 10.5  24.0  18.8    925    116     6.21   85.3   18.3   1.89  1.84
                180 180 70  8.0 11.0 11.0  28.0  22.0   1350    150     6.95  114     22.4   2.02  1.92
                200 200 75  8.5 11.5 11.5  32.2  25.3   1910    191     7.70  148     27.0   2.14  2.01
                220 220 80  9.0 12.5 12.5  37.4  29.4   2690    245     8.48  197     33.6   2.30  2.14
                240 240 85  9.5 13.0 13.0  42.3  33.2   3600    300     9.22  248     39.6   2.42  2.23
                260 260 90 10.0 14.0 14.0  48.3  37.9   4820    371     9.99  317     47.7   2.56  2.36
                280 280 95 10.0 15.0 15.0  53.3  41.8   6280    448    10.9   399     57.2   2.74  2.53
                300 300 100 10.0 16.0 16.0 58.8  46.2   8030    535    11.7   495     67.8   2.90  2.70];
            UAP = [ ...
                80  80  45  5.0  8.0   8.0   10.67  8.38   107.1  26.78  3.17   21.33   7.38  1.41  1.61
                100 100 50  5.5  8.5   8.5   13.38 10.50   209.5  41.90  3.96   32.83   9.95  1.57  1.70
                130 130 55  6.0  9.5   9.5   17.50 13.74   459.6  70.71  5.12   51.34  13.77  1.71  1.77
                150 150 65  7.0 10.25 10.25  22.84 17.93   796.1 106.1   5.90   93.25  21.10  2.02  2.08
                175 175 70  7.5 10.75 10.75  27.06 21.24  1272   145.4   6.86  126.4   25.95  2.16  2.13
                200 200 75  8.0 11.5  11.5   31.98 25.10  1946   194.6   7.80  169.7   32.20  2.30  2.23
                220 220 80  8.0 12.5  12.5   36.27 28.47  2710   246.4   8.64  222.3   39.70  2.48  2.40
                250 250 85  9.0 13.5  13.5   43.80 34.38  4136   330.9   9.72  295.4   49.15  2.60  2.49
                300 300 100 9.5 16.0  16.0   58.60 46.00  8170   544.7  11.81  562.1   79.88  3.10  2.96];
            P = struct();
            P.IPN = DataManager.profileTable('IPN', IPN);
            P.IPE = DataManager.profileTable('IPE', IPE);
            P.HEA = DataManager.profileTable('HEA', HEA);
            P.HEB = DataManager.profileTable('HEB', HEB);
            P.UPN = DataManager.profileTable('UPN', UPN);
            P.UAP = DataManager.profileTable('UAP', UAP);
        end

        function T = profileTable(fam, D)
            % Conversion d'une matrice catalogue (unités usuelles, notation Eurocode) en table SI.
            n = size(D, 1);
            Name = strings(n, 1);
            for k = 1:n
                Name(k) = sprintf('%s %d', fam, D(k, 1));
            end
            mm = 1e-3;
            T = table(Name, D(:, 2)*mm, D(:, 3)*mm, D(:, 4)*mm, D(:, 5)*mm, D(:, 6)*mm, ...
                D(:, 7)*1e-4, D(:, 9)*1e-8, D(:, 12)*1e-8, D(:, 10)*1e-6, D(:, 13)*1e-6, ...
                D(:, 11)*1e-2, D(:, 14)*1e-2, D(:, 8), D(:, 15)*1e-2, false(n, 1), repmat(DataManager.BaseAuthor, n, 1), ...
                'VariableNames', DataManager.ProfileVars);
        end

        function row = buildProfileRow(fam, p)
            % Ligne de table d'un profilé utilisateur (champs manquants calculés).
            name = strtrim(char(strjoin(string(p.Name), ' ')));
            if ~startsWith(DataManager.normKey(name), lower(fam))
                name = [fam ' ' name];
            end
            isU = any(strcmp(fam, {'UPN', 'UAP'}));
            h = DataManager.posField(p, 'h', true);
            b = DataManager.posField(p, 'b', true);
            a = DataManager.posField(p, 'a', true);
            e = DataManager.posField(p, 'e', true);
            if 2*e >= h || a >= b
                error('MecaStruct:DataManager:invalidProfile', ...
                    'Géométrie incohérente : il faut 2e < h et a < b.');
            end
            r = DataManager.numField(p, 'r');
            if ~isfinite(r), r = 0; end
            if r < 0
                error('MecaStruct:DataManager:invalidProfile', 'Le rayon de congé r doit être positif.');
            end
            hw = h - 2*e;                          % hauteur de l'âme entre ailes
            Sgeo = 2*b*e + hw*a;
            S = DataManager.posField(p, 'S', false, Sgeo);
            Iz = DataManager.posField(p, 'Iz', false, (b*h^3 - (b - a)*hw^3)/12);
            if isU
                cGeo = (e*b^2 + hw*a^2/2)/Sgeo;    % dos d'âme → G (géométrie simplifiée)
                c = DataManager.posField(p, 'c', false, cGeo);
                IyGeo = 2*(e*b^3/12 + e*b*(b/2 - c)^2) + hw*a^3/12 + hw*a*(a/2 - c)^2;
                Iy = DataManager.posField(p, 'Iy', false, IyGeo);
                vz = max(c, b - c);
            else
                c = NaN;
                Iy = DataManager.posField(p, 'Iy', false, (2*e*b^3 + hw*a^3)/12);
                vz = b/2;
            end
            Wz = DataManager.posField(p, 'Wz', false, Iz/(h/2));
            Wy = DataManager.posField(p, 'Wy', false, Iy/vz);
            rz = DataManager.posField(p, 'rz', false, sqrt(Iz/S));
            ry = DataManager.posField(p, 'ry', false, sqrt(Iy/S));
            mass = DataManager.posField(p, 'mass', false, DataManager.RhoSteel*S);
            row = table(string(name), h, b, a, e, r, S, Iz, Iy, Wz, Wy, rz, ry, mass, c, true, DataManager.authorOf(p, true), ...
                'VariableNames', DataManager.ProfileVars);
        end

        function row = materialRow(m, isUser)
            % Ligne de table d'un matériau (structure déjà préparée et complétée).
            row = table(string(m.Name), string(m.Category), m.E, m.G, m.nu, m.Re, m.Rm, m.alpha, ...
                m.rho, string(m.Note), logical(isUser), DataManager.authorOf(m, isUser), ...
                'VariableNames', DataManager.MaterialVars);
        end

        function a = authorOf(s, isUser)
            % « Ajouté par » : nom saisi (champ Author), « Utilisateur » à défaut ; la base par défaut n'a pas d'auteur.
            if ~isUser
                a = DataManager.BaseAuthor;
            elseif isfield(s, 'Author') && ~DataManager.isBlank(s.Author)
                a = string(strtrim(char(strjoin(string(s.Author), ' '))));
            else
                a = "Utilisateur";
            end
        end

        function out = prepareMaterial(m, defCategory, defNote)
            % Normalisation d'une structure matériau saisie par l'utilisateur.
            out = struct();
            out.Name = strtrim(char(strjoin(string(m.Name), ' ')));
            out.Category = defCategory;
            if isfield(m, 'Category') && ~DataManager.isBlank(m.Category)
                out.Category = char(strjoin(string(m.Category), ' '));
            end
            fields = {'E', 'G', 'nu', 'Re', 'Rm', 'alpha', 'rho'};
            for k = 1:numel(fields)
                v = NaN;
                if isfield(m, fields{k}) && ~isempty(m.(fields{k}))
                    v = m.(fields{k});
                    if ~(isnumeric(v) || islogical(v)) || ~isscalar(v) || ~isreal(v)
                        error('MecaStruct:DataManager:invalidMaterial', ...
                            'Le champ %s doit être un scalaire réel (SI).', fields{k});
                    end
                    v = double(v);
                end
                out.(fields{k}) = v;
            end
            if out.Re < 0 || out.Rm < 0
                error('MecaStruct:DataManager:invalidMaterial', 'Re et Rm doivent être positifs (Pa).');
            end
            if out.rho <= 0
                error('MecaStruct:DataManager:invalidMaterial', 'La masse volumique doit être strictement positive.');
            end
            out.Note = defNote;
            if isfield(m, 'Note') && ~DataManager.isBlank(m.Note)
                out.Note = char(strjoin(string(m.Note), ' '));
            end
            if isfield(m, 'Author')
                out.Author = m.Author;
            end
        end

        function tab = petersonTable(id)
            % Coefficients de Peterson [D/d, A, b] (Kt = A·(r/d)^b) — arbre épaulé avec congé.
            switch id
                case 'arbre_epaulement_flexion'
                    tab = [1.01 0.91938 -0.17032
                        1.02 0.96048 -0.17711
                        1.03 0.98061 -0.18381
                        1.05 0.98137 -0.19653
                        1.07 0.97527 -0.20958
                        1.10 0.95120 -0.23757
                        1.20 0.97098 -0.21796
                        1.50 0.93836 -0.25759
                        2.00 0.90879 -0.28598
                        3.00 0.89334 -0.30860
                        6.00 0.87868 -0.33243];
                case 'arbre_epaulement_torsion'
                    tab = [1.09 0.90337 -0.12692
                        1.20 0.83425 -0.21649
                        1.33 0.84897 -0.23161
                        2.00 0.86331 -0.23865];
                case 'arbre_epaulement_traction'
                    tab = [1.01 0.98413 -0.10474
                        1.02 1.01220 -0.12474
                        1.05 1.00480 -0.17076
                        1.07 0.98498 -0.19548
                        1.10 0.98450 -0.20818
                        1.15 0.98084 -0.22485
                        1.20 0.96272 -0.25527
                        1.30 0.99682 -0.25751
                        1.50 0.99957 -0.28221
                        2.00 1.01470 -0.30035];
                otherwise
                    error('MecaStruct:DataManager:unknownKt', 'Abaque Kt inconnu : « %s ».', id);
            end
        end

        function x = ktPlateParam(prm)
            % Lecture du paramètre d/W de la plaque trouée.
            x = [];
            if isnumeric(prm)
                x = double(prm);
            elseif isstruct(prm) && isscalar(prm)
                x = DataManager.firstField(prm, {'dW', 'd_W', 'dsurW', 'd_sur_W', 'dOverW', 'ratio'});
                if isempty(x) && isfield(prm, 'd') && isfield(prm, 'W')
                    x = double(prm.d)./double(prm.W);
                end
            end
            if isempty(x) || ~isreal(x) || any(~isfinite(x(:))) || any(x(:) < 0) || any(x(:) >= 1)
                error('MecaStruct:DataManager:ktParams', ...
                    'Plaque trouée : le paramètre d/W doit être réel, avec 0 ≤ d/W < 1.');
            end
        end

        function [rd, Dd] = ktShaftParams(prm)
            % Lecture des paramètres r/d et D/d de l'arbre épaulé.
            rd = [];
            Dd = [];
            if isnumeric(prm)
                prm = double(prm);
                if numel(prm) == 2
                    rd = prm(1);
                    Dd = prm(2);
                elseif ismatrix(prm) && size(prm, 2) == 2
                    rd = prm(:, 1);
                    Dd = prm(:, 2);
                end
            elseif isstruct(prm) && isscalar(prm)
                rd = DataManager.firstField(prm, {'rd', 'r_d', 'rsurd', 'r_sur_d', 'rOverd'});
                Dd = DataManager.firstField(prm, {'Dd', 'D_d', 'Dsurd', 'D_sur_d', 'DOverd'});
                if isempty(rd) && isfield(prm, 'r') && isfield(prm, 'd')
                    rd = double(prm.r)./double(prm.d);
                end
                if isempty(Dd) && isfield(prm, 'D') && isfield(prm, 'd')
                    Dd = double(prm.D)./double(prm.d);
                end
            end
            if isempty(rd) || isempty(Dd)
                error('MecaStruct:DataManager:ktParams', ...
                    'Arbre épaulé : paramètres attendus [r/d, D/d] ou structure (rd, Dd) ou (r, d, D).');
            end
            if ~isreal(rd) || ~isreal(Dd) || any(~isfinite(rd(:))) || any(~isfinite(Dd(:))) ...
                    || any(rd(:) <= 0) || any(Dd(:) <= 1)
                error('MecaStruct:DataManager:ktParams', ...
                    'Arbre épaulé : il faut r/d > 0 et D/d > 1.');
            end
        end

        function rec = mohrRecord(s1, s2, f, expr, swapped)
            % Enregistrement d'une entrée de la table des intégrales de Mohr.
            if swapped
                sym1 = 'b'; sym2 = 'a';
            else
                sym1 = 'a'; sym2 = 'b';
            end
            ex = expr;
            ex = strrep(ex, '@A1', [sym1 '_1']);
            ex = strrep(ex, '@A2', [sym1 '_2']);
            ex = strrep(ex, '@A', sym1);
            ex = strrep(ex, '@B1', [sym2 '_1']);
            ex = strrep(ex, '@B2', [sym2 '_2']);
            ex = strrep(ex, '@B', sym2);
            % Après substitution, la forme 1 porte toujours les valeurs a et la forme 2 les valeurs b
            % (pour une entrée symétrique, @A désigne les valeurs de la forme 2, donc b).
            latex = ['$\int_0^l M_1\,M_2\,ds = ' ex '$'];
            desc = sprintf('Diagramme 1 : %s ; diagramme 2 : %s.', ...
                DataManager.mohrShapeText(s1, 'a'), DataManager.mohrShapeText(s2, 'b'));
            rec = struct('id', [s1 '_x_' s2], 'shape1', s1, 'shape2', s2, 'latex', latex, ...
                'fun', f, 'description', desc);
        end

        function txt = mohrShapeText(shape, sym)
            % Description textuelle d'une forme élémentaire de diagramme.
            switch shape
                case 'rectangle'
                    txt = sprintf('rectangle de valeur %s', sym);
                case 'triangle'
                    txt = sprintf('triangle (0 à gauche, %s à droite)', sym);
                case 'triangle_inverse'
                    txt = sprintf('triangle inversé (%s à gauche, 0 à droite)', sym);
                case 'trapeze'
                    txt = sprintf('trapèze (%s1 à gauche, %s2 à droite)', sym, sym);
                otherwise
                    txt = sprintf('parabole (charge uniforme, nulle aux extrémités, flèche %s au milieu)', sym);
            end
        end

        function map = buildUnitMap()
            % Table des facteurs de conversion vers le SI.
            mu = char(181);   % µ (signe micro)
            dg = char(176);   % °
            e = char(233);    % é
            U = {
                'm', 1; 'cm', 1e-2; 'mm', 1e-3; [mu 'm'], 1e-6; 'um', 1e-6; 'km', 1e3
                'm^2', 1; 'cm^2', 1e-4; 'mm^2', 1e-6
                'm^3', 1; 'cm^3', 1e-6; 'mm^3', 1e-9
                'm^4', 1; 'cm^4', 1e-8; 'mm^4', 1e-12
                'N', 1; 'kN', 1e3; 'MN', 1e6; 'daN', 10
                'N.m', 1; 'kN.m', 1e3; 'N.mm', 1e-3; 'daN.m', 10; 'MN.m', 1e6; 'kN.mm', 1
                'Nm', 1; 'kNm', 1e3; 'Nmm', 1e-3; 'daNm', 10
                'N/m', 1; 'kN/m', 1e3; 'N/mm', 1e3; 'daN/m', 10; 'MN/m', 1e6
                'Pa', 1; 'kPa', 1e3; 'MPa', 1e6; 'GPa', 1e9; 'N/m^2', 1; 'N/mm^2', 1e6; 'bar', 1e5
                'rad', 1; 'mrad', 1e-3; 'deg', pi/180; dg, pi/180
                'rad/m', 1; 'mrad/m', 1e-3; 'deg/m', pi/180; [dg '/m'], pi/180
                ['1/' dg 'C'], 1; ['1e-6/' dg 'C'], 1e-6; ['/' dg 'C'], 1; '1/K', 1; '1e-6/K', 1e-6
                '1/C', 1; '1e-6/C', 1e-6
                [dg 'C'], 1; 'K', 1
                'kg/m^3', 1; 'g/cm^3', 1e3; 'kg/m', 1
                '-', 1; '%', 1e-2; [mu 'def'], 1e-6; [mu 'd' e 'f'], 1e-6; 'udef', 1e-6; 'mm/m', 1e-3
                'W', 1; 'kW', 1e3; 'tr/min', 2*pi/60; 'rad/s', 1; 'J', 1; 'kJ', 1e3
                % --- unités anglo-saxonnes et anciennes (convertisseur)
                'in', 0.0254; 'ft', 0.3048; 'in^2', 0.0254^2; 'ft^2', 0.3048^2; 'in^4', 0.0254^4; 'ft^4', 0.3048^4
                'lbf', 4.4482216152605; 'kip', 4448.2216152605; 'kgf', 9.80665; 'tf', 9806.65
                'lbf.in', 4.4482216152605 * 0.0254; 'lbf.ft', 4.4482216152605 * 0.3048
                'kip.in', 4448.2216152605 * 0.0254; 'kip.ft', 4448.2216152605 * 0.3048; 'kgf.m', 9.80665; 'kgf.cm', 9.80665e-2
                'lbf/in', 4.4482216152605 / 0.0254; 'lbf/ft', 4.4482216152605 / 0.3048; 'kip/ft', 4448.2216152605 / 0.3048; 'kgf/m', 9.80665
                'psi', 6894.757293168; 'ksi', 6894757.293168; 'kgf/cm^2', 98066.5; 'kgf/mm^2', 9806650; 'Mpsi', 6894757293.168
                'lb/ft^3', 16.01846337; 'lb/in^3', 27679.9047
                [dg 'F'], 5 / 9; ['1/' dg 'F'], 9 / 5; ['1e-6/' dg 'F'], 1.8e-6
                'turn', 2 * pi; 'arcmin', pi / 10800; 'arcsec', pi / 648000
                };
            map = containers.Map(U(:, 1), U(:, 2));
        end

        function u = normalizeUnit(unit)
            % Normalisation d'une chaîne d'unité (espaces, symboles de produit, exposants).
            u = strtrim(char(unit));
            u = strrep(u, ' ', '');
            u = strrep(u, char(160), '');                  % espace insécable
            u = strrep(u, char(183), '.');                 % ·
            u = strrep(u, char(8901), '.');                % ⋅
            u = strrep(u, char(215), '.');                 % ×
            u = strrep(u, '*', '.');
            u = strrep(u, char(178), '^2');                % ²
            u = strrep(u, char(179), '^3');                % ³
            u = strrep(u, char(8308), '^4');               % ⁴
            u = strrep(u, char(956), char(181));           % μ grec → µ
            u = strrep(u, char(186), char(176));           % º → °
            u = strrep(u, char(8722), '-');                % − (signe moins)
            if isempty(u)
                u = '-';
            end
        end

        %% -------------------------------------------------------------------------------------
        %  Fiches du formulaire (cell N×3 : titre, LaTeX, variables)
        %  -------------------------------------------------------------------------------------

        function C = sheetMateriaux()
            C = {
                'Relation d''isotropie (module de Coulomb)', '$G = \frac{E}{2\,(1+\nu)}$', ...
                'G : module d''élasticité transversale (Pa) ; E : module d''Young (Pa) ; ν : coefficient de Poisson (sans dimension). Sert à compléter la constante manquante d''un matériau isotrope.'
                'Coefficient de Poisson déduit de E et G', '$\nu = \frac{E}{2\,G} - 1 \qquad -1 < \nu < \frac{1}{2}$', ...
                'E, G (Pa) ; ν (–). Si E, G et ν sont tous donnés, la cohérence est vérifiée (écart signalé au-delà de 5 %).'
                'Module d''Young déduit de G et ν', '$E = 2\,G\,(1+\nu)$', ...
                'E, G (Pa) ; ν (–).'
                'Module de compressibilité volumique', '$K = \frac{E}{3\,(1-2\,\nu)}$', ...
                'K : module de compressibilité (Pa) ; E (Pa) ; ν (–).'
                'Coefficients de Lamé', '$\lambda = \frac{E\,\nu}{(1+\nu)\,(1-2\,\nu)} \qquad \mu = G$', ...
                'λ, μ : coefficients de Lamé (Pa).'
                'Loi de Hooke (traction et cisaillement)', '$\sigma = E\,\varepsilon \qquad \tau = G\,\gamma$', ...
                'σ, τ : contraintes normale et tangentielle (Pa) ; ε : allongement relatif (–) ; γ : glissement (rad).'
                'Contraintes admissibles', '$\sigma_{adm} = \frac{R_e}{s} \qquad \tau_{adm} = \frac{\tau_e}{s}$', ...
                'Re : limite élastique (Pa) ; Rm : résistance à la rupture (Pa) ; s : coefficient de sécurité (–) ; τe : limite élastique au glissement (Pa).'
                'Limite élastique au glissement', '$\tau_e = \frac{R_e}{2}\ \mathrm{(Tresca)} \qquad \tau_e = \frac{R_e}{\sqrt{3}}\ \mathrm{(Von\ Mises)}$', ...
                'τe : limite élastique en cisaillement (Pa) ; Re : limite élastique en traction (Pa).'
                'Dilatation thermique', '$\varepsilon_{th} = \alpha\,\Delta T \qquad \Delta L_{th} = \alpha\,\Delta T\,L_0$', ...
                'α : coefficient de dilatation linéique (1/°C) ; ΔT : variation de température (°C) ; L0 : longueur initiale (m).'
                'Masse linéique', '$m_l = \rho\,S$', ...
                'ρ : masse volumique (kg/m³) ; S : aire de la section (m²) ; ml : masse linéique (kg/m).'
                'Rayons de giration des profilés', '$r_z = \sqrt{\frac{I_z}{S}} \qquad r_y = \sqrt{\frac{I_y}{S}}$', ...
                'Iz : moment quadratique de l''axe fort (m⁴, noté Iy dans les catalogues Eurocode) ; Iy : axe faible (m⁴) ; S (m²) ; rz, ry (m).'
                'Modules de flexion élastiques des profilés', '$W_z = \frac{I_z}{h/2} \qquad W_y = \frac{I_y}{v_{z,max}}$', ...
                'h : hauteur (m) ; vz,max : distance de G à la fibre la plus éloignée selon z : b/2 pour I et H, b − c pour U (c : distance dos d''âme – G) (m) ; W (m³).'
                'Pression de matage', '$P = \frac{F}{S_{matee}} \le P_{adm}$', ...
                'F : effort transmis (N) ; S matée : surface de contact projetée (m²) ; Padm : pression admissible (Pa).'
                'Plage des pressions admissibles', '$0{,}5\ \mathrm{MPa} \le P_{adm} \le 150\ \mathrm{MPa}$', ...
                'Selon la liaison (clavette ou cannelures : fixe, glissant sans charge, glissant sous charge ; articulation sous charge) et les conditions de fonctionnement (médiocres, moyennes, très bonnes).'
                'Coefficient de concentration de contrainte', '$K_t = \frac{\sigma_{max}}{\sigma_{nom}} \ge 1$', ...
                'σmax : contrainte maximale réelle (Pa) ; σnom : contrainte nominale (Pa) ; Kt (–).'
                'Abaques de Peterson : arbre épaulé', '$K_t = A\left(\frac{r}{d}\right)^{b} \qquad A,\ b = f\left(\frac{D}{d}\right)$', ...
                'r : rayon du congé (m) ; d, D : petit et grand diamètres (m) ; A, b : coefficients tabulés (flexion, torsion, traction), interpolés linéairement en D/d.'
                'Plaque trouée en traction (section nette)', '$K_t = 3 - 3{,}13\,\frac{d}{W} + 3{,}66\left(\frac{d}{W}\right)^2 - 1{,}53\left(\frac{d}{W}\right)^3 \qquad \sigma_{nom} = \frac{F}{(W-d)\,t}$', ...
                'd : diamètre du trou (m) ; W : largeur de la plaque (m) ; t : épaisseur (m) ; F : effort de traction (N).'
                };
        end

        function C = sheetGeometrie()
            C = {
                'Aire de la section', '$S = \int\!\!\int_S dS \qquad dS = dy\,dz = r\,dr\,d\theta$', ...
                'S : aire (m²) ; y, z : coordonnées cartésiennes (m) ; r, θ : coordonnées polaires (m, rad).'
                'Moments statiques (repère O1)', '$M_{O_1z_1} = \int\!\!\int_S y_1\,dS \qquad M_{O_1y_1} = \int\!\!\int_S z_1\,dS$', ...
                'y1, z1 : coordonnées dans le repère (O1, y1, z1) (m) ; moments statiques (m³).'
                'Centre de surface G', '$y_G = \frac{M_{O_1z_1}}{S} \qquad z_G = \frac{M_{O_1y_1}}{S}$', ...
                'yG, zG : coordonnées de G dans le repère O1 (m).'
                'Section composée : barycentre', '$y_G = \frac{\sum_i S_i\,y_{G_i}}{\sum_i S_i} \qquad z_G = \frac{\sum_i S_i\,z_{G_i}}{\sum_i S_i}$', ...
                'Si : aire de l''élément i (m², négative pour un évidement) ; yGi, zGi : centre de surface de l''élément i (m).'
                'Moments quadratiques en G', '$I_{Gz} = \int\!\!\int_S y^2\,dS \qquad I_{Gy} = \int\!\!\int_S z^2\,dS$', ...
                'y, z mesurés depuis G (m) ; IGz, IGy (m⁴).'
                'Produit d''inertie', '$I_{Gyz} = \int\!\!\int_S y\,z\,dS$', ...
                'IGyz (m⁴) : nul si la section admet un axe de symétrie (y ou z).'
                'Moment quadratique polaire', '$I_x = \int\!\!\int_S r^2\,dS = I_{Gz} + I_{Gy}$', ...
                'r : distance au point G (m) ; Ix (m⁴).'
                'Théorème de Huygens', '$I_{O_1z_1} = I_{Gz} + S\,d_y^2 \qquad I_{O_1y_1} = I_{Gy} + S\,d_z^2$', ...
                'dy, dz : distances entre les axes parallèles (m) ; S (m²).'
                'Huygens pour une section composée', '$I_{Gz} = \sum_i \left(I_{G_iz_i} + S_i\,d_{yi}^2\right) \qquad I_{Gy} = \sum_i \left(I_{G_iy_i} + S_i\,d_{zi}^2\right)$', ...
                'IGizi, IGiyi : moments propres de l''élément i (m⁴) ; dyi = yGi − yG, dzi = zGi − zG (m).'
                'Rectangle b × h', '$S = b\,h \qquad I_{Gz} = \frac{b\,h^3}{12} \qquad I_{Gy} = \frac{h\,b^3}{12}$', ...
                'b : largeur selon z (m) ; h : hauteur selon y (m).'
                'Disque plein', '$S = \frac{\pi\,D^2}{4} \qquad I_{Gz} = I_{Gy} = \frac{\pi\,D^4}{64} \qquad I_x = \frac{\pi\,D^4}{32}$', ...
                'D : diamètre (m).'
                'Couronne', '$m = \frac{d}{D} \qquad S = \frac{\pi\,D^2}{4}\left(1-m^2\right) \qquad I_{Gz} = \frac{\pi\,D^4}{64}\left(1-m^4\right) \qquad I_x = \frac{\pi\,D^4}{32}\left(1-m^4\right)$', ...
                'D, d : diamètres extérieur et intérieur (m) ; m (–).'
                'Rayons de giration', '$r_z = \sqrt{\frac{I_{Gz}}{S}} \qquad r_y = \sqrt{\frac{I_{Gy}}{S}}$', ...
                'rz, ry (m).'
                'Modules de flexion', '$W_z = \frac{I_{Gz}}{v_{y,max}} \qquad W_y = \frac{I_{Gy}}{v_{z,max}}$', ...
                'vy,max, vz,max : distances de G aux fibres extrêmes (m) ; Wz, Wy (m³).'
                'Axes principaux d''inertie', '$\tan\left(2\,\alpha_P\right) = \frac{-2\,I_{Gyz}}{I_{Gz} - I_{Gy}}$', ...
                'αP : angle de l''axe principal mesuré depuis z (rad).'
                'Moments quadratiques principaux', '$I_{1,2} = \frac{I_{Gz}+I_{Gy}}{2} \pm \sqrt{\left(\frac{I_{Gz}-I_{Gy}}{2}\right)^2 + I_{Gyz}^2}$', ...
                'I1 ≥ I2 (m⁴).'
                'Facteur de forme en cisaillement', '$k = \frac{\tau_{max}}{\tau_{moy}} \qquad k_{rect} = \frac{3}{2} \qquad k_{disque} = \frac{4}{3} \qquad k_{tube} = \frac{4}{3}\left(1 + \frac{r\,R}{r^2+R^2}\right) \qquad k_I = \frac{S}{S_{ame}}$', ...
                'r, R : rayons intérieur et extérieur du tube (m) ; S âme : aire de l''âme (m²) ; k (–).'
                'Coefficient de section réduite', '$S_{red} = k_y\,S \qquad k_{y,rect} = \frac{5}{6} \qquad k_{y,disque} = \frac{6}{7} \qquad k_{y,tube} = \frac{1}{2} \qquad k_{y,I} = \frac{S_{ame}}{S}$', ...
                'ky (–) : coefficient de section réduite (énergie d''effort tranchant) ; S red (m²).'
                };
        end

        function C = sheetEquilibre()
            C = {
                'Principe fondamental de la statique', '$\sum \vec{F}_{ext} = \vec{0} \qquad \sum \vec{M}_A\left(\vec{F}_{ext}\right) = \vec{0}$', ...
                'Forces (N) ; moments (N·m) ; A : point quelconque.'
                'Équations scalaires dans le plan (x, y)', '$\sum F_x = 0 \qquad \sum F_y = 0 \qquad \sum M_{Az} = 0$', ...
                'Trois équations pour un problème plan (N, N, N·m).'
                'Moment d''une force', '$\vec{M}_A\left(\vec{F}\right) = \overrightarrow{AP} \wedge \vec{F} \qquad M_{Az} = (x_P - x_A)\,F_y - (y_P - y_A)\,F_x$', ...
                'P : point d''application (coordonnées en m) ; F (N) ; MA (N·m).'
                'Transport des moments', '$\vec{M}_A = \vec{M}_B + \overrightarrow{AB} \wedge \vec{R}$', ...
                'R : résultante du torseur (N) ; MA, MB : moments en A et B (N·m) ; AB (m).'
                'Résultante d''une charge répartie', '$R = \int_a^b q(x)\,dx \qquad x_R = \frac{1}{R}\int_a^b x\,q(x)\,dx$', ...
                'q(x) : intensité linéique (N/m) ; a, b : bornes (m) ; xR : position de la résultante (m).'
                'Charges uniforme et triangulaire', '$R = q\,L\ \ \left(x_R = \frac{L}{2}\right) \qquad R = \frac{q_0\,L}{2}\ \ \left(x_R = \frac{2\,L}{3}\right)$', ...
                'q : charge uniforme (N/m) ; q0 : valeur maximale de la charge triangulaire, nulle en x = 0 (N/m) ; L : longueur chargée (m).'
                'Inconnues de liaison (problème plan)', '$\begin{array}{lc} \mbox{appui simple, pivot glissant} & 1\ (Y) \\ \mbox{rotule, pivot} & 2\ (X,\ Y) \\ \mbox{encastrement} & 3\ (X,\ Y,\ M) \end{array}$', ...
                'X, Y : composantes de la réaction (N) ; M : moment d''encastrement (N·m).'
                'Degré d''hyperstatisme', '$h = n_{inconnues} - n_{equations} \qquad h_{plan} = r - 3$', ...
                'r : nombre d''inconnues de liaison du problème plan ; h = 0 : isostatique ; h > 0 : hyperstatique ; h < 0 : mécanisme.'
                'Poutre sur deux appuis, force ponctuelle', '$Y_A = \frac{P\,(L-a)}{L} \qquad Y_B = \frac{P\,a}{L}$', ...
                'P : force descendante appliquée en s = a (N) ; L : portée (m) ; YA, YB : réactions verticales (N).'
                'Théorème de Ménabréa', '$\frac{\partial U}{\partial X_i} = 0$', ...
                'Xi : inconnue hyperstatique (N ou N·m) ; U : énergie de déformation (J).'
                'Superposition (structure isostatique associée)', '$M(s) = M_0(s) + \sum_i X_i\,m_i(s)$', ...
                'M0 : moment sous les charges seules (N·m) ; mi : moment dû à Xi = 1 (m ou –).'
                'Système de Ménabréa', '$\sum_j \delta_{ij}\,X_j = -\delta_{i0} \qquad \delta_{ij} = \int_0^L \frac{m_i\,m_j}{E\,I_z}\,ds \qquad \delta_{i0} = \int_0^L \frac{m_i\,M_0}{E\,I_z}\,ds$', ...
                'E (Pa) ; Iz (m⁴) ; δij : coefficients d''influence (m/N ou 1/(N·m)).'
                'Termes axial, de tranchant et de torsion', '$\delta_{ij} = \int_0^L \left(\frac{n_i\,n_j}{E\,S} + \frac{t_i\,t_j}{k_y\,G\,S} + \frac{m_{ti}\,m_{tj}}{G\,I_x}\right) ds$', ...
                'ni, ti, mti : efforts normal, tranchant et moment de torsion dus à Xi = 1 ; S (m²) ; G (Pa) ; Ix (m⁴) ; ky (–).'
                'Exemple : poutre encastrée-appuyée, charge uniforme', '$R_B = \frac{3\,q\,L}{8} \qquad M_A = -\frac{q\,L^2}{8}$', ...
                'q : charge uniforme descendante (N/m) ; L : portée (m) ; RB : réaction de l''appui (N) ; MA : moment d''encastrement (N·m).'
                'Exemple : deux travées égales, charge uniforme', '$R_{centre} = \frac{5\,q\,L}{4} \qquad R_{rive} = \frac{3\,q\,L}{8}$', ...
                'L : longueur d''une travée (m) ; q (N/m).'
                };
        end

        function C = sheetCohesion()
            C = {
                'Définition du torseur de cohésion', '$\left\{T_{coh}\right\}_G = \left\{T_{ext,\ droite}\right\}_G = -\left\{T_{ext,\ gauche}\right\}_G$', ...
                'Actions extérieures appliquées à droite de la coupure (s < x ≤ L), réduites au centre de surface G(s) de la section.'
                'Composantes du torseur de cohésion', '$\vec{R} = N\,\vec{x} + T_y\,\vec{y} + T_z\,\vec{z} \qquad \vec{M}_G = M_t\,\vec{x} + M_{fy}\,\vec{y} + M_{fz}\,\vec{z}$', ...
                'N : effort normal (N) ; Ty, Tz : efforts tranchants (N) ; Mt : moment de torsion (N·m) ; Mfy, Mfz : moments de flexion (N·m).'
                'Effort normal', '$N(s) = \sum_{droite} F_{xi} + \int_s^L p_x\,dx$', ...
                'N > 0 : traction ; Fxi : forces axiales à droite (N) ; px : charge linéique axiale (N/m).'
                'Efforts tranchants', '$T_y(s) = \sum_{droite} F_{yi} + \int_s^L p_y\,dx \qquad T_z(s) = \sum_{droite} F_{zi} + \int_s^L p_z\,dx$', ...
                'py, pz : charges linéiques (N/m) ; py < 0 pour une charge descendante (q = −py).'
                'Moment de torsion', '$M_t(s) = \sum_{droite} M_{xi}$', ...
                'Mxi : couples d''axe x appliqués à droite de la coupure (N·m).'
                'Moment de flexion Mfz', '$M_{fz}(s) = \sum_{droite}\left[(x_i - s)\,F_{yi} + C_{zi}\right] + \int_s^L (x - s)\,p_y\,dx$', ...
                'xi : abscisse de la force i (m) ; Fyi (N) ; Czi : couple d''axe z (N·m) ; py (N/m).'
                'Moment de flexion Mfy', '$M_{fy}(s) = \sum_{droite}\left[-(x_i - s)\,F_{zi} + C_{yi}\right] - \int_s^L (x - s)\,p_z\,dx$', ...
                'Fzi (N) ; Cyi : couple d''axe y (N·m) ; pz (N/m).'
                'Charges réparties sur [s, L]', '$\vec{S}_M = \int_s^L -q(x)\,dx\,\vec{y} \qquad \vec{M}_M = \int_s^L \overrightarrow{GP} \wedge \left(-q(x)\,dx\,\vec{y}\right)$', ...
                'P : point courant d''abscisse x (m) ; q : intensité descendante (N/m).'
                'Relations différentielles', '$\frac{dT_y}{ds} = -p_y = q \qquad T_y = -\frac{dM_{fz}}{ds} \qquad T_z = \frac{dM_{fy}}{ds} \qquad \frac{dN}{ds} = -p_x$', ...
                's : abscisse de la section (m) ; q (N/m).'
                'Méthode intégrale', '$T_y(s) = \int q\,ds \qquad M_{fz}(s) = -\int T_y\,ds \qquad M_{fy}(s) = \int T_z\,ds$', ...
                'Intégration depuis s = L (efforts nuls en L+) ; constantes fixées par les sauts aux charges ponctuelles.'
                'Discontinuités', '$T_y(a^-) = T_y(a^+) + F_y \qquad M_{fz}(a^-) = M_{fz}(a^+) + C_z$', ...
                'Force ponctuelle Fy (N) ou couple Cz (N·m) appliqué en s = a (m).'
                'Extremum du moment fléchissant', '$\frac{dM_{fz}}{ds} = -T_y = 0 \ \Rightarrow \ M_{fz}\ \mathrm{extremal}$', ...
                'Le moment est extrémal là où l''effort tranchant s''annule ou change de signe.'
                'Poutre sur deux appuis, force centrée', '$|T_y| = \frac{P}{2} \qquad M_{fz,max} = \frac{P\,L}{4}$', ...
                'P : force descendante au milieu (N) ; L : portée (m).'
                'Poutre sur deux appuis, charge uniforme', '$M_{fz}(s) = \frac{q\,s\,(L-s)}{2} \qquad M_{fz,max} = \frac{q\,L^2}{8}$', ...
                'q : charge uniforme descendante (N/m) ; L (m).'
                'Console encastrée en s = 0, force en bout', '$T_y = -P \qquad M_{fz}(s) = -P\,(L-s) \qquad M_{fz}(0) = -P\,L$', ...
                'P : force descendante appliquée en s = L (N).'
                };
        end

        function C = sheetTreillis()
            C = {
                'Hypothèses', '$N_{ij} = \mathrm{cste} \qquad \mbox{barres bi-articulees, charges aux noeuds}$', ...
                'Chaque barre ij n''est soumise qu''à un effort normal constant Nij (N).'
                'Vecteur unitaire et longueur de la barre ij', '$\vec{u}_{ij} = \frac{\overrightarrow{P_iP_j}}{L_{ij}} \qquad L_{ij} = \sqrt{(x_j-x_i)^2 + (y_j-y_i)^2}$', ...
                'xi, yi : coordonnées du nœud i (m) ; Lij : longueur (m).'
                'Équilibre du nœud i (méthode des nœuds)', '$\sum_j N_{ij}\,\vec{u}_{ij} + \vec{F}_i + \vec{R}_i = \vec{0}$', ...
                'Nij : effort normal (N, > 0 en traction) ; Fi : charge nodale (N) ; Ri : réaction d''appui (N).'
                'Forme matricielle', '$\left[A\right]\left\{\begin{array}{c} N \\ R \end{array}\right\} = \left\{-F\right\}$', ...
                '[A] : matrice des cosinus directeurs ; {N} : efforts dans les barres (N) ; {R} : réactions (N) ; {F} : charges nodales (N).'
                'Degré d''hyperstatisme', '$h = m + r - 2\,n\ \ \mathrm{(plan)} \qquad h = m + r - 3\,n\ \ \mathrm{(espace)}$', ...
                'm : nombre de barres ; r : nombre de réactions ; n : nombre de nœuds ; h < 0 : mécanisme.'
                'Nature de l''effort', '$N > 0\ :\ \mathrm{traction} \qquad N < 0\ :\ \mathrm{compression}$', ...
                'N : effort normal (N).'
                'Contrainte normale', '$\sigma_{xx} = \frac{N}{S}$', ...
                'S : section de la barre (m²) ; σxx (Pa).'
                'Allongement d''une barre', '$\Delta L = \frac{N\,L}{E\,S}$', ...
                'L : longueur (m) ; E : module d''Young (Pa) ; S (m²) ; ΔL (m).'
                'Raideur d''une barre', '$k = \frac{E\,S}{L}$', ...
                'k (N/m).'
                'Matrice de rigidité élémentaire (plan)', '$\left[K_e\right] = \frac{E\,S}{L}\left[\begin{array}{cccc} c^2 & c\,s & -c^2 & -c\,s \\ c\,s & s^2 & -c\,s & -s^2 \\ -c^2 & -c\,s & c^2 & c\,s \\ -c\,s & -s^2 & c\,s & s^2 \end{array}\right]$', ...
                'c = cos θ, s = sin θ : cosinus directeurs de la barre ; [Ke] (N/m).'
                'Assemblage et résolution (méthode des rigidités)', '$\left[K\right]\left\{U\right\} = \left\{F\right\} + \left\{R\right\}$', ...
                'U : déplacements nodaux (m), nuls aux degrés de liberté bloqués ; [K] (N/m).'
                'Effort normal à partir des déplacements', '$N_{ij} = \frac{E\,S}{L}\,\vec{u}_{ij}\cdot\left(\vec{U}_j - \vec{U}_i\right)$', ...
                'Ui, Uj : déplacements des nœuds i et j (m).'
                };
        end

        function C = sheetTraction()
            C = {
                'Contrainte normale', '$\sigma_{xx} = \frac{N}{S_0}$', ...
                'N : effort normal (N, > 0 en traction) ; S0 : section initiale (m²) ; σxx (Pa).'
                'Concentration de contrainte et condition de résistance', '$\sigma_{max} = K_t\,\frac{N}{S_0} \le \frac{R_e}{s}$', ...
                'Kt : coefficient de concentration (–) ; Re : limite élastique (Pa) ; s : coefficient de sécurité (–).'
                'Coefficient de concentration de contrainte', '$K_t = \frac{\sigma_{max}}{\sigma_{nom}}$', ...
                'σmax, σnom : contraintes maximale et nominale (Pa).'
                'Section minimale', '$S_0 \ge \frac{s\,K_t\,|N|}{R_e}$', ...
                'S0 (m²).'
                'Allongement relatif', '$\varepsilon_{xx} = \frac{\sigma_{xx}}{E} + \alpha\,\Delta T$', ...
                'E : module d''Young (Pa) ; α : coefficient de dilatation (1/°C) ; ΔT : variation de température (°C).'
                'Déformations transversales', '$\varepsilon_{yy} = \varepsilon_{zz} = -\nu\,\frac{\sigma_{xx}}{E} + \alpha\,\Delta T$', ...
                'ν : coefficient de Poisson (–).'
                'Variation relative de volume', '$\frac{\Delta V}{V_0} = \varepsilon_{xx} + \varepsilon_{yy} + \varepsilon_{zz} = (1-2\,\nu)\,\frac{\sigma_{xx}}{E} + 3\,\alpha\,\Delta T$', ...
                'Sans effet thermique : ΔV/V0 = (1 − 2ν)·ΔL/L0 (–).'
                'Allongement : méthode analytique', '$\Delta L = \frac{N\,L_0}{E\,S_0} + \alpha\,\Delta T\,L_0$', ...
                'L0 : longueur initiale (m) ; ΔL (m).'
                'Raideur de la barre', '$K = \frac{E\,S_0}{L_0} \qquad N = K\,\Delta L_{meca}$', ...
                'K (N/m) ; ΔL méca : allongement mécanique (m).'
                'Allongement : méthode intégrale', '$\Delta L = \int_0^{L_0} \left(\frac{N(x)}{E\,S(x)} + \alpha\,\Delta T(x)\right) dx$', ...
                'N(x), S(x), ΔT(x) : effort, section et variation de température le long de la barre.'
                'Énergie de déformation', '$U = \int_0^{L_0} \frac{N^2}{2\,E\,S}\,dx$', ...
                'U (J).'
                'Allongement : méthode énergétique (Castigliano)', '$\Delta L = \frac{\partial U}{\partial F}$', ...
                'F : effort appliqué à l''extrémité (N).'
                'Condition de rigidité', '$\Delta L \le \Delta L_{max}$', ...
                'ΔLmax : allongement admissible (m).'
                'Barre conique (diamètres d1 et d2)', '$\Delta L = \frac{4\,F\,L}{\pi\,E\,d_1\,d_2}$', ...
                'd1, d2 : diamètres extrêmes (m) ; L : longueur (m) ; F (N).'
                'Contrainte thermique (dilatation empêchée)', '$\sigma_{xx} = -E\,\alpha\,\Delta T$', ...
                'Barre bi-encastrée chauffée de ΔT : compression si ΔT > 0.'
                'Barre suspendue sous son poids propre', '$\sigma_{max} = \rho\,g\,L \qquad \Delta L = \frac{\rho\,g\,L^2}{2\,E}$', ...
                'ρ : masse volumique (kg/m³) ; g = 9,81 m/s² ; L (m).'
                };
        end

        function C = sheetCisaillement()
            C = {
                'Contrainte tangentielle moyenne', '$\tau_{moy} = \frac{T}{S}$', ...
                'T : effort tranchant (N) ; S : section cisaillée (m²) ; τ (Pa).'
                'Contrainte maximale et condition de résistance', '$\tau_{max} = k\,\frac{T}{S} \le \frac{\tau_e}{s}$', ...
                'k : facteur de forme (–) ; τe : limite élastique au glissement (Pa) ; s : coefficient de sécurité (–).'
                'Limite élastique au glissement', '$\tau_e = \frac{R_e}{2}\ \mathrm{(Tresca)} \qquad \tau_e = \frac{R_e}{\sqrt{3}}\ \mathrm{(Von\ Mises)}$', ...
                'Re : limite élastique (Pa).'
                'Glissement', '$\gamma = \frac{\Delta y}{\Delta x} = \frac{\tau}{G}$', ...
                'γ : glissement (rad) ; G : module de Coulomb (Pa).'
                'Formule de Jourawski', '$\tau_{yx}(y) = \frac{T_y}{I_z\,b(y)} \int\!\!\int_{S(y)} \eta\,dS = \frac{T_y\,Q(y)}{I_z\,b(y)}$', ...
                'b(y) : largeur de la section à l''ordonnée y (m) ; Q(y) : moment statique de la partie située au-dessus de y (m³) ; Iz (m⁴).'
                'Section rectangulaire', '$\tau(y) = \frac{6\,T}{b\,h^3}\left(\frac{h^2}{4} - y^2\right) = \frac{3}{2}\,\frac{T}{S}\left[1 - \left(\frac{2\,y}{h}\right)^2\right]$', ...
                'b, h : largeur et hauteur (m) ; y mesuré depuis G (m) ; τmax = 1,5·T/S en y = 0.'
                'Disque plein', '$\tau_{max} = \frac{4}{3}\,\frac{T}{S}$', ...
                'S = πD²/4 (m²).'
                'Tube mince', '$\tau_{max} \approx 2\,\frac{T}{S}$', ...
                'Limite de k = 4/3·(1 + rR/(r² + R²)) quand r → R.'
                'Poutre en I', '$\tau_{max} \approx \frac{T}{S_{ame}} \qquad k = \frac{S}{S_{ame}}$', ...
                'S âme : aire de l''âme (m²).'
                'Coefficient de section réduite (énergie)', '$k_y = \frac{I_z^2}{S\,\int \frac{Q(y)^2}{b(y)}\,dy}$', ...
                'ky (–) : 5/6 pour le rectangle ; disque : 9/10 par cette formule, 6/7 retenu par le cours (élasticité, Cowper).'
                'Énergie d''effort tranchant', '$U_T = \int_0^L \frac{T_y^2}{2\,k_y\,G\,S}\,ds$', ...
                'UT (J).'
                'Section minimale', '$S \ge \frac{k\,T\,s}{\tau_e}$', ...
                'S (m²).'
                'Flèche due à l''effort tranchant', '$v_T(s_0) = \int_0^L \frac{T_y\,\overline{t}}{k_y\,G\,S}\,ds$', ...
                't̄ : effort tranchant dû à une force unité en s0 (–) ; vT (m).'
                };
        end

        function C = sheetMatage()
            C = {
                'Pression de matage', '$P = \frac{F}{S_{matee}} \le P_{adm}$', ...
                'F : effort transmis (N) ; S matée : surface de contact projetée (m²) ; Padm : pression admissible (Pa).'
                'Surface minimale', '$S_{min} = \frac{F}{P_{adm}}$', ...
                'S min (m²).'
                'Contact cylindrique : surface projetée', '$S_{matee} = d\,e$', ...
                'd : diamètre (m) ; e : épaisseur de la pièce (m).'
                'Clavette : effort tangentiel', '$F = \frac{2\,C}{D}$', ...
                'C : couple transmis (N·m) ; D : diamètre de l''arbre (m).'
                'Clavette : matage', '$P = \frac{4\,C}{D\,b\,L} \le P_{adm}$', ...
                'b : hauteur de la clavette (m, contact sur b/2) ; L : longueur de la clavette (m).'
                'Clavette : cisaillement', '$\tau = \frac{2\,C}{a\,L\,D} \le \frac{\tau_e}{s}$', ...
                'a : largeur de la clavette (m) ; τe : limite élastique au glissement (Pa).'
                'Clavette : longueur minimale', '$L_{min} = \max\left(\frac{4\,C}{D\,b\,P_{adm}},\ \frac{2\,C}{a\,D\,\tau_{adm}}\right)$', ...
                'τadm = τe/s (Pa).'
                'Rivet ou goupille : matage', '$P = \frac{2\,F}{d\,e} \le P_{adm}$', ...
                'Formule du cours ; d : diamètre (m) ; e : épaisseur de la pièce (m).'
                'Rivet ou goupille : cisaillement', '$\tau = \frac{4\,F}{n\,\pi\,d^2} \le \frac{\tau_e}{s}$', ...
                'n : nombre de sections cisaillées (–).'
                'Goupille : dimensions minimales', '$d_{min} = \sqrt{\frac{4\,F}{n\,\pi\,\tau_{adm}}} \qquad e_{min} = \frac{2\,F}{d\,P_{adm}}$', ...
                'dmin, emin (m).'
                'Arbre cannelé', '$P = \frac{2\,C}{D_m\,n\,h\,L} \le P_{adm} \qquad D_m = \frac{D+d}{2} \qquad h = \frac{D-d}{2}$', ...
                'n : nombre de cannelures ; h : hauteur portante (m) ; L : longueur (m) ; D, d : diamètres extérieur et intérieur (m).'
                'Pressions admissibles usuelles (MPa)', '$\begin{array}{lccc} & \mathrm{mediocres} & \mathrm{moyennes} & \mathrm{tres\ bonnes} \\ \mathrm{fixe} & 35\textrm{-}50 & 60\textrm{-}100 & 80\textrm{-}150 \\ \mathrm{glissant\ sans\ charge} & 15\textrm{-}20 & 20\textrm{-}30 & 25\textrm{-}40 \\ \mathrm{glissant\ sous\ charge} & 3\textrm{-}10 & 5\textrm{-}15 & 10\textrm{-}20 \end{array}$', ...
                'Clavettes et cannelures (valeurs usuelles, Guide du dessinateur) ; articulation sous charge : 0,5 à 10 MPa.'
                };
        end

        function C = sheetTorsion()
            C = {
                'Angle unitaire de torsion', '$\theta = \frac{d\varphi}{ds} = \frac{M_t}{G\,I_x} \le \overline{\theta}$', ...
                'θ (rad/m) ; φ : rotation (rad) ; Mt : moment de torsion (N·m) ; G (Pa) ; Ix (m⁴) ; θ̄ : angle unitaire admissible (rad/m).'
                'Contrainte tangentielle', '$\tau(r) = \frac{M_t\,r}{I_x} \qquad \tau_{max} = \frac{M_t}{I_x}\,\frac{D}{2}$', ...
                'r : rayon courant (m) ; D : diamètre extérieur (m) ; τ (Pa).'
                'Condition de résistance', '$\tau_{max} = K_t\,\frac{M_t}{I_x}\,\frac{D}{2} \le \frac{\tau_e}{s}$', ...
                'Kt (–) ; τe : limite élastique au glissement (Pa) ; s (–).'
                'Moment quadratique polaire', '$I_x = \frac{\pi\,D^4}{32}\ \mathrm{(plein)} \qquad I_x = \frac{\pi\,\left(D^4 - d^4\right)}{32}\ \mathrm{(creux)}$', ...
                'D, d : diamètres extérieur et intérieur (m) ; Ix (m⁴).'
                'Module de torsion', '$W_t = \frac{I_x}{D/2} = \frac{\pi\,D^3}{16}\ \mathrm{(plein)}$', ...
                'Wt (m³).'
                'Rotation : méthode analytique', '$\varphi(L) = \frac{M_t\,L}{G\,I_x}$', ...
                'L : longueur (m) ; φ (rad).'
                'Rotation : méthode intégrale', '$\varphi(L) = \int_0^L \frac{M_t(s)}{G\,I_x(s)}\,ds$', ...
                'Mt(s), Ix(s) : moment et moment polaire variables (N·m, m⁴).'
                'Rotation : méthode énergétique', '$U = \int_0^L \frac{M_t^2}{2\,G\,I_x}\,ds \qquad \varphi = \frac{\partial U}{\partial C}$', ...
                'U (J) ; C : couple appliqué (N·m).'
                'Raideur en torsion', '$K = \frac{G\,I_x}{L} \qquad M_t = K\,\varphi$', ...
                'K (N·m/rad).'
                'Glissement', '$\gamma(r) = r\,\theta \qquad \tau = G\,\gamma$', ...
                'γ (rad).'
                'Diamètre minimal (résistance)', '$D \ge \left(\frac{16\,K_t\,M_t\,s}{\pi\,\tau_e}\right)^{1/3}$', ...
                'Arbre plein ; D (m).'
                'Diamètre minimal (rigidité)', '$D \ge \left(\frac{32\,M_t}{\pi\,G\,\overline{\theta}}\right)^{1/4}$', ...
                'Arbre plein ; θ̄ (rad/m).'
                'Puissance transmise', '$P = M_t\,\omega \qquad \omega = \frac{2\,\pi\,N}{60}$', ...
                'P (W) ; ω (rad/s) ; N : vitesse de rotation (tr/min).'
                'Tube mince fermé (Bredt)', '$\tau = \frac{M_t}{2\,A_m\,e}$', ...
                'Am : aire délimitée par la ligne moyenne (m²) ; e : épaisseur (m).'
                'Profil mince ouvert', '$I_t \approx \sum_i \frac{b_i\,t_i^3}{3} \qquad \tau_{max} = \frac{M_t\,t_{max}}{I_t}$', ...
                'bi, ti : longueur et épaisseur des parois (m) ; It : constante de torsion (m⁴).'
                };
        end

        function C = sheetFlexion()
            C = {
                'Contrainte normale (axes principaux)', '$\sigma_{xx}(y,z) = \frac{N}{S} - \frac{M_{fz}}{I_{Gz}}\,y + \frac{M_{fy}}{I_{Gy}}\,z$', ...
                'N (N) ; Mfz, Mfy (N·m) ; S (m²) ; IGz, IGy (m⁴) ; y, z mesurés depuis G (m) ; σxx (Pa).'
                'Flexion simple', '$\sigma_{xx} = -\frac{M_{fz}}{I_{Gz}}\,y \qquad |\sigma|_{max} = \frac{|M_{fz}|}{W_z}$', ...
                'Wz : module de flexion (m³).'
                'Modules de flexion usuels', '$W_z = \frac{I_{Gz}}{v} \qquad W_{rect} = \frac{b\,h^2}{6} \qquad W_{disque} = \frac{\pi\,D^3}{32}$', ...
                'v : distance de G à la fibre la plus éloignée (m) ; b, h, D (m).'
                'Condition de résistance', '$|\sigma_{max}| = K_t\,|\sigma_{nom}| \le \frac{R_e}{s}$', ...
                'Kt (–) ; Re (Pa) ; s (–).'
                'Dimensionnement', '$W_z \ge \frac{s\,K_t\,|M_{fz}|_{max}}{R_e}$', ...
                'Wz (m³).'
                'Forme générale (axes non principaux)', '$\sigma_{xx} = \frac{N}{S} + b\,y + c\,z \qquad \left[\begin{array}{cc} I_{Gz} & I_{Gyz} \\ I_{Gyz} & I_{Gy} \end{array}\right] \left[\begin{array}{c} b \\ c \end{array}\right] = \left[\begin{array}{c} -M_{fz} \\ M_{fy} \end{array}\right]$', ...
                'IGyz : produit d''inertie (m⁴) ; b, c : gradients de contrainte (Pa/m).'
                'Axe neutre', '$\sigma_{xx} = 0 \ \Rightarrow \ \frac{N}{S} - \frac{M_{fz}}{I_{Gz}}\,y + \frac{M_{fy}}{I_{Gy}}\,z = 0$', ...
                'Droite de la section où la contrainte normale s''annule.'
                'Efforts résultants', '$N = \int\!\!\int_S \sigma_{xx}\,dS \qquad M_{fz} = -\int\!\!\int_S y\,\sigma_{xx}\,dS \qquad M_{fy} = \int\!\!\int_S z\,\sigma_{xx}\,dS$', ...
                'Définition des efforts intérieurs à partir des contraintes.'
                'Courbure (Navier-Bernoulli)', '$\frac{1}{R} = \frac{M_{fz}}{E\,I_{Gz}}$', ...
                'R : rayon de courbure de la ligne moyenne (m) ; E (Pa).'
                'Cisaillement de flexion (Jourawski)', '$\tau_{yx}(y) = \frac{T_y\,Q(y)}{I_{Gz}\,b(y)}$', ...
                'Ty (N) ; Q(y) (m³) ; b(y) (m).'
                'Flexion composée', '$\sigma_{max} = \frac{|N|}{S} + \frac{|M_{fz}|}{W_z}$', ...
                'Traction (ou compression) et flexion combinées (Pa).'
                'Flexion et torsion (arbre)', '$\sigma_{eq} = \sqrt{\sigma^2 + 4\,\tau^2}\ \mathrm{(Tresca)} \qquad \sigma_{eq} = \sqrt{\sigma^2 + 3\,\tau^2}\ \mathrm{(Von\ Mises)}$', ...
                'σ : contrainte de flexion (Pa) ; τ : contrainte de torsion (Pa).'
                'Énergie de flexion', '$U_f = \int_0^L \frac{M_{fz}^2}{2\,E\,I_{Gz}}\,ds$', ...
                'Uf (J).'
                };
        end

        function C = sheetDeformee()
            C = {
                'Équation de la déformée', '$E\,I_z\,v'''' = M_{fz} \qquad \alpha(s) = \frac{dv}{ds}$', ...
                'v : flèche selon +y (m) ; α : rotation (rad) ; E (Pa) ; Iz (m⁴) ; Mfz (N·m).'
                'Flexion dans le plan (x, z)', '$E\,I_y\,w'''' = -M_{fy}$', ...
                'w : flèche selon +z (m) ; Iy (m⁴) ; Mfy (N·m).'
                'Méthode 1 : double intégration par tronçon', '$E\,I\,v_k''(s) = \int M_k\,ds + C_{1k} \qquad E\,I\,v_k(s) = \int\!\!\int M_k\,ds\,ds + C_{1k}\,s + C_{2k}$', ...
                'Mk : moment sur le tronçon k ; C1k, C2k : 2n constantes d''intégration.'
                'Conditions de continuité', '$v_k(s_k) = v_{k+1}(s_k) \qquad v_k''(s_k) = v_{k+1}''(s_k)$', ...
                'sk : frontière entre les tronçons k et k+1 (m).'
                'Conditions aux limites', '$v = 0\ \mathrm{(appui)} \qquad v = 0,\ v'' = 0\ \mathrm{(encastrement)}$', ...
                'Conditions cinématiques imposées par les liaisons.'
                'Méthode 2 : aires (rotation)', '$\alpha_Q - \alpha_P = \frac{1}{E\,I}\int_P^Q M\,ds$', ...
                'αP, αQ : rotations aux points P et Q (rad).'
                'Méthode 2 : moment des aires', '$v(s) = v_0 + \alpha_0\,s + \frac{1}{E\,I}\sum_k A_k\,\left(s - \overline{s}_k\right)$', ...
                'Ak : aire du diagramme de moment du tronçon k situé avant s (N·m²) ; s̄k : abscisse de son centre de gravité (m) ; v0, α0 : flèche et rotation en s = 0.'
                'Flèche d''une console (moment des aires)', '$f = \frac{1}{E\,I}\left|\int_0^L (L - s)\,M\,ds\right|$', ...
                'Console encastrée en s = 0 : aire × bras de levier (m).'
                'Méthode 3 : Castigliano (forces unités)', '$v(s_0) = \int_0^L \frac{M\,\overline{m}}{E\,I_z}\,ds + \int_0^L \frac{T\,\overline{t}}{k_y\,G\,S}\,ds$', ...
                'm̄, t̄ : moment et effort tranchant dus à une force unité en s0 ; ky (–) ; G (Pa) ; S (m²).'
                'Charge fictive', '$q_i = \left(\frac{\partial U}{\partial \Phi}\right)_{\Phi = 0}$', ...
                'Φ : force fictive appliquée au point et dans la direction cherchés (N).'
                'Théorème de Maxwell-Betti', '$s_{ij} = s_{ji}$', ...
                'sij : déplacement en i dû à une force unité en j (m/N).'
                'Méthode 4 : intégrales de Mohr', '$v(s_0) = \frac{1}{E\,I}\int_0^L M\,\overline{m}\,ds = \frac{1}{E\,I}\sum_{troncons} \int_0^{l} M_i\,M_j\,ds$', ...
                'Intégrales tabulées par formes élémentaires (rectangle, triangle, trapèze, parabole).'
                'Poutre sur deux appuis, force centrée', '$f = \frac{P\,L^3}{48\,E\,I}$', ...
                'P (N) ; L (m) ; f (m).'
                'Poutre sur deux appuis, charge uniforme', '$f = \frac{5\,q\,L^4}{384\,E\,I}$', ...
                'q (N/m).'
                'Console, force en bout', '$f = \frac{P\,L^3}{3\,E\,I} \qquad \alpha_{max} = \frac{P\,L^2}{2\,E\,I}$', ...
                'P (N) ; α (rad).'
                'Console, charge uniforme', '$f = \frac{q\,L^4}{8\,E\,I}$', ...
                'q (N/m).'
                'Poutre bi-encastrée, charge uniforme', '$f = \frac{q\,L^4}{384\,E\,I} \qquad M_{enc} = -\frac{q\,L^2}{12} \qquad M_{mil} = \frac{q\,L^2}{24}$', ...
                'Menc, Mmil : moments aux encastrements et à mi-portée (N·m).'
                'Condition de rigidité', '$f = |v|_{max} \le \overline{f}$', ...
                'f̄ : flèche admissible (m).'
                'Courbure exacte', '$\frac{1}{R} = \frac{v''''}{\left(1 + {v''}^2\right)^{3/2}} \approx v''''$', ...
                'Hypothèse des petites rotations (v'' ≪ 1).'
                };
        end

        function C = sheetEnergie()
            C = {
                'Énergie de déformation d''une poutre', '$U = \int_0^L \left(\frac{N^2}{2\,E\,S} + \frac{T_y^2}{2\,k_y\,G\,S} + \frac{T_z^2}{2\,k_z\,G\,S} + \frac{M_t^2}{2\,G\,I_x} + \frac{M_{fy}^2}{2\,E\,I_y} + \frac{M_{fz}^2}{2\,E\,I_z}\right) ds$', ...
                'U (J) ; N, Ty, Tz (N) ; Mt, Mfy, Mfz (N·m) ; E, G (Pa) ; S (m²) ; Ix, Iy, Iz (m⁴) ; ky, kz (–).'
                'Densité volumique d''énergie', '$\frac{dU}{dV} = \frac{1}{2}\,\sigma_{ij}\,\varepsilon_{ij} \qquad U = \frac{1}{2}\int\!\!\int\!\!\int_V \sigma_{ij}\,\varepsilon_{ij}\,dV$', ...
                'σij (Pa) ; εij (–) ; V (m³).'
                'Théorème de Clapeyron', '$W_{ext} = \frac{1}{2}\sum_i F_i\,u_i = U$', ...
                'Fi : forces (N) ; ui : déplacements de leurs points d''application dans leur direction (m).'
                'Théorème de Castigliano', '$u_i = \frac{\partial U}{\partial F_i} \qquad \omega_i = \frac{\partial U}{\partial C_i}$', ...
                'ui (m) ; ωi : rotation (rad) ; Ci : couple (N·m).'
                'Théorème de Ménabréa', '$\frac{\partial U}{\partial X_i} = 0$', ...
                'Xi : inconnue hyperstatique (N ou N·m).'
                'Méthode des forces unités (Maxwell-Mohr)', '$u = \int_0^L \left(\frac{N\,\overline{n}}{E\,S} + \frac{T\,\overline{t}}{k\,G\,S} + \frac{M_t\,\overline{m}_t}{G\,I_x} + \frac{M_f\,\overline{m}}{E\,I}\right) ds$', ...
                'n̄, t̄, m̄t, m̄ : efforts dus à une force (ou un couple) unité au point cherché.'
                'Charge fictive', '$q_i = \left(\frac{\partial U}{\partial \Phi}\right)_{\Phi = 0} = \int_0^L \frac{M^P\,\overline{M}^1}{E\,I_z}\,ds + \int_0^L \frac{T^P\,\overline{T}^1}{k_y\,G\,S}\,ds$', ...
                'M^P, T^P : efforts sous les charges réelles ; M̄¹, T̄¹ : efforts sous la charge fictive unité.'
                'Théorème de Maxwell-Betti', '$F_1\,u_{12} = F_2\,u_{21} \qquad s_{ij} = s_{ji}$', ...
                'uij : déplacement en i dû à la force appliquée en j (m).'
                'Traction-compression', '$U = \frac{N^2\,L}{2\,E\,S} = \frac{1}{2}\,K\,\Delta L^2$', ...
                'K = ES/L (N/m).'
                'Torsion', '$U = \frac{M_t^2\,L}{2\,G\,I_x}$', ...
                'Mt (N·m) ; Ix (m⁴).'
                'Flexion', '$U = \int_0^L \frac{M_{fz}^2}{2\,E\,I_z}\,ds$', ...
                'Mfz (N·m) ; Iz (m⁴).'
                'Effort tranchant', '$U_T = \int_0^L \frac{T_y^2}{2\,k_y\,G\,S}\,ds$', ...
                'Ty (N) ; ky (–).'
                'Coefficients d''influence', '$\delta_{ij} = \int_0^L \frac{m_i\,m_j}{E\,I}\,ds$', ...
                'mi : moment dû à une action unité i.'
                };
        end

        function C = sheetMohrIntegrales()
            C = {
                'Définition', '$\int_0^l M_i(s)\,M_j(s)\,ds$', ...
                'Mi, Mj : diagrammes élémentaires sur un tronçon de longueur l (N·m ou m) ; a : valeurs du diagramme 1, b : du diagramme 2.'
                'Rectangle × rectangle', '$\int_0^l M_i\,M_j\,ds = l\,a\,b$', ...
                'a, b : valeurs constantes.'
                'Rectangle × triangle', '$\int_0^l M_i\,M_j\,ds = \frac{1}{2}\,l\,a\,b$', ...
                'b : valeur maximale du triangle.'
                'Rectangle × trapèze', '$\int_0^l M_i\,M_j\,ds = \frac{l}{2}\,a\,\left(b_1 + b_2\right)$', ...
                'b1, b2 : valeurs extrêmes du trapèze.'
                'Rectangle × parabole', '$\int_0^l M_i\,M_j\,ds = \frac{2}{3}\,l\,a\,f$', ...
                'f : flèche de la parabole (milieu), nulle aux extrémités.'
                'Triangle × triangle (même sens)', '$\int_0^l M_i\,M_j\,ds = \frac{1}{3}\,l\,M_1\,M_3$', ...
                'M1, M3 : valeurs maximales, atteintes à la même extrémité.'
                'Triangle × triangle (sens opposés)', '$\int_0^l M_i\,M_j\,ds = \frac{1}{6}\,l\,a\,b$', ...
                'Maximums aux extrémités opposées.'
                'Triangle × trapèze', '$\int_0^l M_i\,M_j\,ds = \frac{l}{6}\,M_3\,\left(2\,M_1 + M_2\right)$', ...
                'Triangle de valeur M3 culminant du côté de M1 ; trapèze de valeurs M1 et M2.'
                'Trapèze × trapèze', '$\int_0^l M_i\,M_j\,ds = \frac{l}{6}\left[a_1\,\left(2\,b_1 + b_2\right) + a_2\,\left(b_1 + 2\,b_2\right)\right]$', ...
                'a1, a2 et b1, b2 : valeurs à gauche et à droite des deux trapèzes.'
                'Parabole × triangle', '$\int_0^l M_i\,M_j\,ds = \frac{1}{3}\,l\,f\,b$', ...
                'Quel que soit le sens du triangle.'
                'Parabole × trapèze', '$\int_0^l M_i\,M_j\,ds = \frac{l}{3}\,f\,\left(b_1 + b_2\right)$', ...
                'f : flèche de la parabole ; b1, b2 : valeurs du trapèze.'
                'Parabole × parabole', '$\int_0^l M_i\,M_j\,ds = \frac{8}{15}\,l\,f_1\,f_2$', ...
                'f1, f2 : flèches des deux paraboles.'
                'Diagramme parabolique (charge uniforme)', '$M(s) = \frac{4\,f\,s\,(l-s)}{l^2} \qquad f = \frac{q\,l^2}{8}$', ...
                'q : charge uniforme sur le tronçon (N/m) ; f (N·m).'
                'Application : flèche', '$v(s_0) = \frac{1}{E\,I}\int_0^L M\,\overline{m}\,ds$', ...
                'm̄ : moment dû à une force unité en s0 ; E (Pa) ; I (m⁴).'
                'Application : coefficients de Ménabréa', '$\delta_{ij} = \frac{1}{E\,I}\int_0^L m_i\,m_j\,ds$', ...
                'mi : moment dû à l''inconnue hyperstatique Xi = 1.'
                'Décomposition des diagrammes', '$M_{troncon} = M_{trapeze} + M_{parabole}$', ...
                'Sur chaque tronçon, le diagramme sous charge uniforme = trapèze (valeurs d''extrémité) + parabole (f = ql²/8).'
                };
        end

        function C = sheetFlambage()
            C = {
                'Inertie et rayon de giration minimaux', '$I_{min} = \min\left(I_z,\ I_y\right) \qquad r_{min} = \sqrt{\frac{I_{min}}{S}}$', ...
                'Iz, Iy (m⁴) ; S (m²) ; rmin (m).'
                'Longueurs de flambement', '$\begin{array}{lc} \mbox{encastree-libre} & L'' = 2\,L \\ \mbox{articulee-articulee} & L'' = L \\ \mbox{encastree-articulee} & L'' = \frac{L}{\sqrt{2}} \\ \mbox{encastree-encastree} & L'' = \frac{L}{2} \end{array}$', ...
                'L : longueur de la poutre (m) ; L'' : longueur de flambement (m).'
                'Élancement', '$\lambda = \frac{L''}{r_{min}}$', ...
                'λ (–).'
                'Élancement limite', '$\lambda_{lim} = \pi\,\sqrt{\frac{E}{\sigma_e}}$', ...
                'E : module d''Young (Pa) ; σe : limite élastique (Pa).'
                'Compression simple (λ < 20)', '$P_C = \sigma_e\,S$', ...
                'PC (N).'
                'Équation d''Euler', '$v'''' + k^2\,v = 0 \qquad k^2 = \frac{P_c}{E\,I_{min}}$', ...
                'v : flèche (m) ; Pc : charge de compression (N) ; k (rad/m).'
                'Solution et conditions aux limites', '$v(s) = A\,\cos(k\,s) + B\,\sin(k\,s) \qquad v(0) = v(L) = 0 \Rightarrow \sin(k\,L) = 0 \Rightarrow k\,L = n\,\pi$', ...
                'Cas articulé-articulé ; n entier (mode n).'
                'Déformée critique', '$v(s) = B\,\sin\left(\frac{\pi\,s}{L''}\right)$', ...
                'B : amplitude indéterminée (m).'
                'Charge critique d''Euler (λ ≥ λlim)', '$P_E = \frac{\pi^2\,E\,I_{min}}{{L''}^2}$', ...
                'PE (N).'
                'Contrainte critique d''Euler', '$\sigma_E = \frac{\pi^2\,E}{\lambda^2}$', ...
                'σE (Pa).'
                'Formule de Rankine (20 ≤ λ < λlim)', '$\frac{1}{P_R} = \frac{1}{P_E} + \frac{1}{P_C} \qquad P_R = \frac{\sigma_e\,S}{1 + \left(\frac{\lambda}{\lambda_{lim}}\right)^2}$', ...
                'PR (N).'
                'Charge admissible', '$P_{adm} = \frac{P_{crit}}{s} \qquad P \le P_{adm}$', ...
                's : coefficient de sécurité (–) ; P : effort de compression appliqué (N).'
                'Arbre de décision', '$\begin{array}{ll} \lambda < 20 & P_{crit} = P_C \\ 20 \le \lambda < \lambda_{lim} & P_{crit} = P_R \\ \lambda \ge \lambda_{lim} & P_{crit} = P_E \end{array}$', ...
                'Choix du régime selon l''élancement.'
                'Poutre encastrée-articulée', '$\tan(k\,L) = k\,L \ \Rightarrow \ k\,L = 4{,}4934$', ...
                'Premier mode ; L'' = π/k ≈ 0,699 L ≈ L/√2.'
                };
        end

        function C = sheetTenseurs()
            C = {
                'Tenseur des contraintes', '$\left[\sigma\right] = \left[\begin{array}{ccc} \sigma_{xx} & \sigma_{xy} & \sigma_{xz} \\ \sigma_{xy} & \sigma_{yy} & \sigma_{yz} \\ \sigma_{xz} & \sigma_{yz} & \sigma_{zz} \end{array}\right]$', ...
                'Composantes (Pa) ; tenseur symétrique.'
                'Vecteur contrainte sur la facette de normale n', '$\vec{C}_n = \left[\sigma\right]\,\vec{n}$', ...
                'n : normale unitaire ; Cn (Pa).'
                'Composantes normale et tangentielle', '$\sigma_n = \vec{C}_n \cdot \vec{n} \qquad \tau = \vec{C}_n \cdot \vec{t} \qquad |\tau| = \sqrt{|\vec{C}_n|^2 - \sigma_n^2}$', ...
                't : vecteur unitaire tangent à la facette ; σn, τ (Pa).'
                'Premier et troisième invariants', '$I_1 = \sigma_{xx} + \sigma_{yy} + \sigma_{zz} \qquad I_3 = \det\left[\sigma\right]$', ...
                'I1 (Pa) ; I3 (Pa³).'
                'Deuxième invariant', '$I_2 = \left(\sigma_{xx}\,\sigma_{yy} - \sigma_{xy}^2\right) + \left(\sigma_{xx}\,\sigma_{zz} - \sigma_{xz}^2\right) + \left(\sigma_{zz}\,\sigma_{yy} - \sigma_{yz}^2\right)$', ...
                'I2 (Pa²).'
                'Équation caractéristique', '$\det\left(\left[\sigma\right] - \sigma_i\,\left[I\right]\right) = 0 \ \Rightarrow \ \sigma_i^3 - I_1\,\sigma_i^2 + I_2\,\sigma_i - I_3 = 0$', ...
                'σi : contraintes principales (Pa).'
                'Directions principales', '$\left(\left[\sigma\right] - \sigma_i\,\left[I\right]\right)\vec{n}_i = \vec{0} \qquad \sigma_I \ge \sigma_{II} \ge \sigma_{III}$', ...
                'ni : direction principale unitaire.'
                'Cisaillement maximal', '$\tau_{max} = \frac{\sigma_I - \sigma_{III}}{2}$', ...
                'τmax (Pa).'
                'Contraintes octaédriques', '$\sigma_{oct} = \frac{I_1}{3} \qquad \tau_{oct} = \frac{1}{3}\sqrt{\left(\sigma_I - \sigma_{II}\right)^2 + \left(\sigma_{II} - \sigma_{III}\right)^2 + \left(\sigma_{III} - \sigma_I\right)^2}$', ...
                'σoct, τoct (Pa).'
                'Changement de repère', '$\left[\sigma''\right] = \left[R\right]\left[\sigma\right]\left[R\right]^T$', ...
                '[R] : matrice de passage (lignes = vecteurs de la nouvelle base).'
                'État plan : contrainte normale sur la facette θ', '$\sigma(\theta) = \frac{\sigma_{xx}+\sigma_{yy}}{2} + \frac{\sigma_{xx}-\sigma_{yy}}{2}\,\cos 2\theta + \sigma_{xy}\,\sin 2\theta$', ...
                'θ : angle de la normale à la facette depuis x (rad).'
                'État plan : contrainte tangentielle sur la facette θ', '$\tau(\theta) = -\frac{\sigma_{xx}-\sigma_{yy}}{2}\,\sin 2\theta + \sigma_{xy}\,\cos 2\theta$', ...
                'τ (Pa).'
                'Contraintes principales planes', '$\sigma_{1,2} = \frac{\sigma_{xx}+\sigma_{yy}}{2} \pm \sqrt{\left(\frac{\sigma_{xx}-\sigma_{yy}}{2}\right)^2 + \sigma_{xy}^2}$', ...
                'σ1 ≥ σ2 (Pa).'
                'Directions principales planes', '$\tan 2\theta_P = \frac{2\,\sigma_{xy}}{\sigma_{xx} - \sigma_{yy}}$', ...
                'θP (rad).'
                'Tenseur des déformations', '$\varepsilon_{xy} = \frac{\gamma_{xy}}{2} \qquad \left[\varepsilon\right] = \left[\begin{array}{ccc} \varepsilon_{xx} & \varepsilon_{xy} & \varepsilon_{xz} \\ \varepsilon_{xy} & \varepsilon_{yy} & \varepsilon_{yz} \\ \varepsilon_{xz} & \varepsilon_{yz} & \varepsilon_{zz} \end{array}\right]$', ...
                'ε (–) ; γ : glissement (rad).'
                'Équations d''équilibre local', '$\frac{\partial \sigma_{ij}}{\partial x_j} + f_i = 0$', ...
                'fi : forces volumiques (N/m³).'
                };
        end

        function C = sheetMohrCercle()
            C = {
                'Centre du cercle de Mohr', '$\delta = \frac{\sigma_{xx} + \sigma_{yy}}{2}$', ...
                'δ (Pa).'
                'Rayon du cercle de Mohr', '$\rho = \sqrt{\left(\frac{\sigma_{xx} - \sigma_{yy}}{2}\right)^2 + \sigma_{xy}^2}$', ...
                'ρ (Pa).'
                'Contraintes principales', '$\sigma_1 = \delta + \rho \qquad \sigma_2 = \delta - \rho$', ...
                'σ1, σ2 (Pa).'
                'Points représentatifs des facettes x et y', '$A\left(\sigma_{xx},\ \sigma_{yx}\right) \qquad B\left(\sigma_{yy},\ -\sigma_{xy}\right)$', ...
                'A et B sont diamétralement opposés.'
                'Équation du cercle', '$\left(\sigma - \delta\right)^2 + \tau^2 = \rho^2$', ...
                'Lieu des points (σ, τ) des facettes contenant z.'
                'Rotation de la facette', '$\theta\ \mathrm{(facette)} \ \Rightarrow \ 2\,\theta\ \mathrm{(cercle)}$', ...
                'Une rotation θ de la facette correspond à une rotation 2θ sur le cercle.'
                'Contrainte normale sur la facette θ', '$\sigma(\theta) = \delta + \frac{\sigma_{xx}-\sigma_{yy}}{2}\,\cos 2\theta + \sigma_{xy}\,\sin 2\theta$', ...
                'θ (rad).'
                'Contrainte tangentielle sur la facette θ', '$\tau(\theta) = -\frac{\sigma_{xx}-\sigma_{yy}}{2}\,\sin 2\theta + \sigma_{xy}\,\cos 2\theta$', ...
                'τ (Pa).'
                'Cisaillement maximal (plan)', '$\tau_{max} = \rho$', ...
                'Atteint sur les facettes à 45° des directions principales.'
                'Angle principal', '$2\,\theta_P = \mathrm{atan2}\left(2\,\sigma_{xy},\ \sigma_{xx} - \sigma_{yy}\right)$', ...
                'θP (rad).'
                'Tricercle de Mohr', '$C_1 = \frac{\sigma_{II}+\sigma_{III}}{2},\ R_1 = \frac{\sigma_{II}-\sigma_{III}}{2} \qquad C_2 = \frac{\sigma_{I}+\sigma_{III}}{2},\ R_2 = \frac{\sigma_{I}-\sigma_{III}}{2} \qquad C_3 = \frac{\sigma_{I}+\sigma_{II}}{2},\ R_3 = \frac{\sigma_{I}-\sigma_{II}}{2}$', ...
                'Ci : centres (Pa) ; Ri : rayons (Pa).'
                'Zone admissible des facettes', '$\left(\sigma_n - C_2\right)^2 + \tau^2 \le R_2^2 \qquad \left(\sigma_n - C_1\right)^2 + \tau^2 \ge R_1^2 \qquad \left(\sigma_n - C_3\right)^2 + \tau^2 \ge R_3^2$', ...
                'Le point (σn, τ) de toute facette est dans le grand cercle et hors des deux petits.'
                'Cercle de Mohr des déformations', '$\delta_{\varepsilon} = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} \qquad \rho_{\varepsilon} = \sqrt{\left(\frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\right)^2 + \left(\frac{\gamma_{xy}}{2}\right)^2}$', ...
                'ε (–) ; γxy/2 en ordonnée.'
                };
        end

        function C = sheetCriteres()
            C = {
                'Critère de Tresca', '$\sigma_{eq} = \sigma_I - \sigma_{III} \le \frac{\sigma_e}{s}$', ...
                'σI ≥ σII ≥ σIII : contraintes principales (Pa) ; σe : limite élastique (Pa) ; s (–).'
                'Critère de Von Mises', '$\sigma_{eq} = \frac{1}{\sqrt{2}}\sqrt{\left(\sigma_I - \sigma_{II}\right)^2 + \left(\sigma_{II} - \sigma_{III}\right)^2 + \left(\sigma_{III} - \sigma_I\right)^2} \le \frac{\sigma_e}{s}$', ...
                'σeq : contrainte équivalente (Pa).'
                'Von Mises en contraintes planes', '$\sigma_{eq} = \sqrt{\sigma_I^2 - \sigma_I\,\sigma_{II} + \sigma_{II}^2} = \sqrt{\sigma_{xx}^2 + \sigma_{yy}^2 - \sigma_{xx}\,\sigma_{yy} + 3\,\sigma_{xy}^2}$', ...
                'État plan (σzz = σxz = σyz = 0).'
                'Von Mises : forme générale', '$\sigma_{eq} = \sqrt{\frac{1}{2}\left[\left(\sigma_{xx}-\sigma_{yy}\right)^2 + \left(\sigma_{yy}-\sigma_{zz}\right)^2 + \left(\sigma_{zz}-\sigma_{xx}\right)^2\right] + 3\left(\sigma_{xy}^2 + \sigma_{yz}^2 + \sigma_{xz}^2\right)}$', ...
                'Composantes dans un repère quelconque (Pa).'
                'Contrainte normale maximale (matériaux fragiles)', '$\max_i |\sigma_i| \le \frac{\sigma_R}{s}$', ...
                'σR : résistance à la rupture (Pa).'
                'Coefficient de sécurité obtenu', '$s_{obtenu} = \frac{\sigma_e}{\sigma_{eq}}$', ...
                's obtenu (–).'
                'Contrainte admissible', '$\sigma_{adm} = \frac{\sigma_e}{s}$', ...
                'σadm (Pa).'
                'Limite élastique au glissement', '$\tau_e = \frac{\sigma_e}{2}\ \mathrm{(Tresca)} \qquad \tau_e = \frac{\sigma_e}{\sqrt{3}}\ \mathrm{(Von\ Mises)}$', ...
                'τe (Pa).'
                'Cisaillement pur', '$\sigma_{eq,T} = 2\,\tau \qquad \sigma_{eq,VM} = \sqrt{3}\,\tau$', ...
                'τ : cisaillement (Pa).'
                'Arbre en flexion et torsion', '$\sigma_{eq,T} = \sqrt{\sigma^2 + 4\,\tau^2} \qquad \sigma_{eq,VM} = \sqrt{\sigma^2 + 3\,\tau^2}$', ...
                'σ : contrainte normale de flexion (Pa) ; τ : contrainte de torsion (Pa).'
                'Lieu de Tresca (hexagone)', '$\max\left(|\sigma_1|,\ |\sigma_2|,\ |\sigma_1 - \sigma_2|\right) = \sigma_e$', ...
                'Contraintes planes (σ1, σ2) (Pa).'
                'Lieu de Von Mises (ellipse)', '$\sigma_1^2 - \sigma_1\,\sigma_2 + \sigma_2^2 = \sigma_e^2$', ...
                'Contraintes planes (Pa).'
                'Lieu de la contrainte normale maximale (carré)', '$\max\left(|\sigma_1|,\ |\sigma_2|\right) = \sigma_R$', ...
                'Critère de Rankine (Pa).'
                };
        end

        function C = sheetHooke()
            C = {
                'Loi de Hooke 3D isotrope', '$\varepsilon_{ij} = \frac{1+\nu}{E}\,\sigma_{ij} - \frac{\nu}{E}\,\mathrm{tr}(\sigma)\,\delta_{ij} + \alpha\,\Delta T\,\delta_{ij}$', ...
                'E (Pa) ; ν (–) ; α (1/°C) ; ΔT (°C) ; δij : symbole de Kronecker.'
                'Forme inverse (coefficients de Lamé)', '$\sigma_{ij} = \lambda\,\mathrm{tr}(\varepsilon)\,\delta_{ij} + 2\,\mu\,\varepsilon_{ij} - (3\,\lambda + 2\,\mu)\,\alpha\,\Delta T\,\delta_{ij}$', ...
                'λ, μ : coefficients de Lamé (Pa).'
                'Déformation normale', '$\varepsilon_{xx} = \frac{1}{E}\left[\sigma_{xx} - \nu\left(\sigma_{yy} + \sigma_{zz}\right)\right] + \alpha\,\Delta T$', ...
                'Idem pour εyy et εzz par permutation.'
                'Glissements', '$\gamma_{xy} = \frac{\sigma_{xy}}{G} \qquad \gamma_{yz} = \frac{\sigma_{yz}}{G} \qquad \gamma_{xz} = \frac{\sigma_{xz}}{G}$', ...
                'G = E/(2(1+ν)) (Pa) ; γ = 2ε (rad).'
                'Notation de Voigt', '$\left\{\varepsilon\right\} = \left[S\right]\left\{\sigma\right\} \qquad \left\{\sigma\right\} = \left[C\right]\left\{\varepsilon\right\} \qquad \left[C\right] = \left[S\right]^{-1}$', ...
                'Ordre [xx yy zz yz xz xy] ; glissements ingénieur ; [S] (1/Pa), [C] (Pa).'
                'Matrice de souplesse isotrope', '$\left[S\right] = \left[\begin{array}{cccccc} \frac{1}{E} & -\frac{\nu}{E} & -\frac{\nu}{E} & 0 & 0 & 0 \\ -\frac{\nu}{E} & \frac{1}{E} & -\frac{\nu}{E} & 0 & 0 & 0 \\ -\frac{\nu}{E} & -\frac{\nu}{E} & \frac{1}{E} & 0 & 0 & 0 \\ 0 & 0 & 0 & \frac{1}{G} & 0 & 0 \\ 0 & 0 & 0 & 0 & \frac{1}{G} & 0 \\ 0 & 0 & 0 & 0 & 0 & \frac{1}{G} \end{array}\right]$', ...
                '[S] (1/Pa).'
                'Contraintes planes', '$\varepsilon_{xx} = \frac{\sigma_{xx} - \nu\,\sigma_{yy}}{E} \qquad \varepsilon_{yy} = \frac{\sigma_{yy} - \nu\,\sigma_{xx}}{E} \qquad \gamma_{xy} = \frac{\sigma_{xy}}{G} \qquad \varepsilon_{zz} = -\frac{\nu}{E}\left(\sigma_{xx} + \sigma_{yy}\right)$', ...
                'σzz = σxz = σyz = 0.'
                'Contraintes planes : forme inverse', '$\sigma_{xx} = \frac{E}{1-\nu^2}\left(\varepsilon_{xx} + \nu\,\varepsilon_{yy}\right) \qquad \sigma_{yy} = \frac{E}{1-\nu^2}\left(\varepsilon_{yy} + \nu\,\varepsilon_{xx}\right) \qquad \sigma_{xy} = G\,\gamma_{xy}$', ...
                'σ (Pa).'
                'Déformations planes', '$\varepsilon_{zz} = 0 \ \Rightarrow \ \sigma_{zz} = \nu\left(\sigma_{xx} + \sigma_{yy}\right)$', ...
                'εzz = γxz = γyz = 0.'
                'Déformations planes : forme inverse', '$\sigma_{xx} = \frac{E}{(1+\nu)\,(1-2\,\nu)}\left[(1-\nu)\,\varepsilon_{xx} + \nu\,\varepsilon_{yy}\right]$', ...
                'Idem pour σyy par permutation ; σxy = G γxy.'
                'Matériau orthotrope (souplesse)', '$\varepsilon_1 = \frac{\sigma_1}{E_1} - \frac{\nu_{21}}{E_2}\,\sigma_2 - \frac{\nu_{31}}{E_3}\,\sigma_3 \qquad \gamma_{12} = \frac{\tau_{12}}{G_{12}}$', ...
                '9 constantes : E1, E2, E3, ν12, ν13, ν23, G12, G13, G23.'
                'Symétrie de la souplesse orthotrope', '$\frac{\nu_{12}}{E_1} = \frac{\nu_{21}}{E_2} \qquad \frac{\nu_{13}}{E_1} = \frac{\nu_{31}}{E_3} \qquad \frac{\nu_{23}}{E_2} = \frac{\nu_{32}}{E_3}$', ...
                '[S] symétrique et définie positive.'
                'Variation de volume', '$\frac{\Delta V}{V} = \mathrm{tr}(\varepsilon) = \frac{1-2\,\nu}{E}\,\mathrm{tr}(\sigma) + 3\,\alpha\,\Delta T$', ...
                'ΔV/V (–).'
                'Relations entre constantes', '$G = \frac{E}{2\,(1+\nu)} \qquad \lambda = \frac{E\,\nu}{(1+\nu)\,(1-2\,\nu)} \qquad \mu = G$', ...
                'Matériau isotrope : deux constantes indépendantes.'
                };
        end

        function C = sheetExtensometrie()
            C = {
                'Loi de la jauge (Bridgman)', '$\frac{\Delta R}{R} = K\,\varepsilon$', ...
                'K : facteur de jauge (≈ 2) ; R : résistance (Ω) ; ε : déformation (–).'
                'Résistance d''un conducteur', '$R = \frac{\rho_e\,L}{S}$', ...
                'ρe : résistivité (Ω·m) ; L : longueur (m) ; S : section (m²).'
                'Pont de Wheatstone (linéarisé)', '$V_{out} = \frac{V_{in}\,K}{4}\left(\varepsilon_1 - \varepsilon_2 + \varepsilon_3 - \varepsilon_4\right)$', ...
                'Vin : tension d''alimentation (V) ; Vout : tension de sortie (V) ; εi : déformation de la jauge i.'
                'Équilibre du pont', '$R_1\,R_3 = R_2\,R_4 \ \Rightarrow \ V_{out} = 0$', ...
                'Ri (Ω).'
                'Quart de pont', '$V_{out} = \frac{V_{in}\,K\,\varepsilon}{4}$', ...
                'Une jauge active.'
                'Demi-pont', '$V_{out} = \frac{V_{in}\,K\,\varepsilon}{2}$', ...
                'Deux jauges actives sur des bras adjacents, déformations opposées (flexion).'
                'Pont complet', '$V_{out} = V_{in}\,K\,\varepsilon$', ...
                'Quatre jauges actives (ε1 = ε3 = ε, ε2 = ε4 = −ε).'
                'Déformation indiquée', '$\varepsilon_{ind} = \frac{4\,V_{out}}{K\,V_{in}}$', ...
                'À diviser par le facteur de pont (1, 2 ou 4).'
                'Jauge orientée à θ', '$\varepsilon(\theta) = \varepsilon_{xx}\,\cos^2\theta + \varepsilon_{yy}\,\sin^2\theta + \gamma_{xy}\,\sin\theta\,\cos\theta$', ...
                'θ : angle de la jauge depuis x (rad).'
                'Rosette à 45°', '$\varepsilon_{xx} = \varepsilon_1 \qquad \varepsilon_{yy} = \varepsilon_2 \qquad \varepsilon_{xy} = \frac{\gamma_{xy}}{2} = \varepsilon_3 - \frac{\varepsilon_1 + \varepsilon_2}{2}$', ...
                'ε1 à 0°, ε2 à 90°, ε3 à 45°.'
                'Rosette à 60° (delta)', '$\varepsilon_{xx} = \varepsilon_0 \qquad \varepsilon_{yy} = \frac{2\left(\varepsilon_{60} + \varepsilon_{120}\right) - \varepsilon_0}{3} \qquad \gamma_{xy} = \frac{2\left(\varepsilon_{60} - \varepsilon_{120}\right)}{\sqrt{3}}$', ...
                'Jauges à 0°, 60° et 120°.'
                'Déformations principales', '$\varepsilon_{1,2} = \frac{\varepsilon_{xx}+\varepsilon_{yy}}{2} \pm \sqrt{\left(\frac{\varepsilon_{xx}-\varepsilon_{yy}}{2}\right)^2 + \left(\frac{\gamma_{xy}}{2}\right)^2}$', ...
                'ε1 ≥ ε2 (–).'
                'Direction principale', '$\tan 2\theta_P = \frac{\gamma_{xy}}{\varepsilon_{xx} - \varepsilon_{yy}}$', ...
                'θP (rad).'
                'Contraintes (état plan de contrainte)', '$\sigma_{xx} = \frac{E}{1-\nu^2}\left(\varepsilon_{xx} + \nu\,\varepsilon_{yy}\right) \qquad \sigma_{yy} = \frac{E}{1-\nu^2}\left(\varepsilon_{yy} + \nu\,\varepsilon_{xx}\right) \qquad \sigma_{xy} = G\,\gamma_{xy}$', ...
                'E, G (Pa) ; ν (–).'
                };
        end

        %% -------------------------------------------------------------------------------------
        %  Utilitaires
        %  -------------------------------------------------------------------------------------

        function checkTableVars(T, vars, label)
            % Vérifie qu'une table contient les variables requises.
            if ~istable(T)
                error('MecaStruct:DataManager:invalidProperty', '%s doit être une table.', label);
            end
            missing = setdiff(vars, T.Properties.VariableNames, 'stable');
            if ~isempty(missing)
                error('MecaStruct:DataManager:invalidProperty', ...
                    '%s : variables manquantes : %s.', label, strjoin(missing, ', '));
            end
        end

        function T = validateBearingTable(T)
            % Validation d'une table de pressions de matage chargée depuis un fichier.
            DataManager.checkTableVars(T, DataManager.BearingVars, 'bearingPressures');
            T = T(:, DataManager.BearingVars);
            T.Liaison = string(T.Liaison);
            T.Conditions = string(T.Conditions);
            T.Note = string(T.Note);
            if ~isnumeric(T.Pmin) || ~isnumeric(T.Pmax) || any(~isfinite(T.Pmin)) ...
                    || any(~isfinite(T.Pmax)) || any(T.Pmin <= 0) || any(T.Pmax < T.Pmin)
                error('MecaStruct:DataManager:invalidUserFile', ...
                    'Table de matage invalide : il faut 0 < Pmin ≤ Pmax.');
            end
        end

        function fam = checkFamily(family)
            % Normalise et vérifie une famille de profilés.
            if ~(ischar(family) || (isstring(family) && isscalar(family)))
                error('MecaStruct:DataManager:unknownFamily', 'La famille de profilés doit être un texte.');
            end
            fam = upper(strtrim(char(family)));
            if ~any(strcmp(fam, DataManager.Families))
                error('MecaStruct:DataManager:unknownFamily', ...
                    'Famille de profilés inconnue : « %s » (familles : %s).', fam, ...
                    strjoin(DataManager.Families, ', '));
            end
        end

        function idx = profileIndex(names, fam, name)
            % Indice d'un profilé dans une famille (nom exact, casse et espaces ignorés).
            if isnumeric(name)
                name = num2str(name);
            end
            q = DataManager.normKey(name);
            f = lower(fam);
            if ~startsWith(q, f)
                q = [f q];
            end
            keysN = cellfun(@DataManager.normKey, cellstr(names), 'UniformOutput', false);
            idx = find(strcmp(keysN, q), 1);
        end

        function idx = exactIndex(names, name)
            % Indice d'un nom (casse, accents, espaces et ponctuation ignorés), [] si absent.
            keysN = cellfun(@DataManager.normKey, cellstr(names), 'UniformOutput', false);
            idx = find(strcmp(keysN, DataManager.normKey(name)), 1);
        end

        function idx = matchName(names, name)
            % Recherche tolérante : correspondance exacte normalisée, sinon préfixe unique.
            idx = DataManager.exactIndex(names, name);
            if ~isempty(idx)
                return
            end
            q = DataManager.normKey(name);
            if isempty(q)
                return
            end
            keysN = cellfun(@DataManager.normKey, cellstr(names), 'UniformOutput', false);
            hit = find(startsWith(keysN, q));
            if isscalar(hit)
                idx = hit;
            end
        end

        function mask = matchLiaison(liaisons, q)
            % Lignes de la table de matage correspondant à une liaison (exacte ou mots-clés).
            keysL = cellfun(@DataManager.normKey, cellstr(liaisons), 'UniformOutput', false);
            qk = DataManager.normKey(q);
            mask = strcmp(keysL, qk);
            if any(mask)
                return
            end
            qw = DataManager.normWords(q);
            if isempty(qw)
                error('MecaStruct:DataManager:bearingNotFound', 'Liaison non précisée.');
            end
            ok = false(numel(keysL), 1);
            for i = 1:numel(keysL)
                lw = DataManager.normWords(liaisons(i));
                hitAll = true;
                for j = 1:numel(qw)
                    if ~any(startsWith(lw, qw{j}))
                        hitAll = false;
                        break
                    end
                end
                ok(i) = hitAll;
            end
            u = unique(keysL(ok));
            if isempty(u)
                error('MecaStruct:DataManager:bearingNotFound', ...
                    'Liaison inconnue dans la table de matage : « %s ».', char(strjoin(string(q), ' ')));
            end
            if numel(u) > 1
                error('MecaStruct:DataManager:bearingAmbiguous', ...
                    'Liaison ambiguë : « %s » (%d liaisons correspondent).', char(strjoin(string(q), ' ')), numel(u));
            end
            mask = strcmp(keysL, u{1});
        end

        function idx = matchCondition(conds, mask, q)
            % Ligne de la table de matage (parmi mask) correspondant aux conditions.
            keysC = cellfun(@DataManager.normKey, cellstr(conds), 'UniformOutput', false);
            qk = DataManager.normKey(q);
            hit = find(mask & strcmp(keysC, qk));
            if isempty(hit) && ~isempty(qk)
                hit = find(mask & startsWith(keysC, qk));
            end
            if isempty(hit)
                error('MecaStruct:DataManager:bearingNotFound', ...
                    'Conditions inconnues pour cette liaison : « %s » (attendu : médiocres, moyennes, très bonnes).', ...
                    char(strjoin(string(q), ' ')));
            end
            if numel(hit) > 1
                error('MecaStruct:DataManager:bearingAmbiguous', ...
                    'Conditions ambiguës : « %s ».', char(strjoin(string(q), ' ')));
            end
            idx = hit;
        end

        function k = normKey(s)
            % Clé normalisée : minuscules, sans accents, sans espaces ni ponctuation.
            if isnumeric(s)
                s = num2str(s);
            end
            s = char(strjoin(string(s), ' '));
            k = regexprep(lower(DataManager.stripAccents(s)), '[^a-z0-9]', '');
        end

        function w = normWords(s)
            % Mots normalisés (minuscules, sans accents).
            s = char(strjoin(string(s), ' '));
            w = regexp(lower(DataManager.stripAccents(s)), '[a-z0-9]+', 'match');
        end

        function s = stripAccents(s)
            % Remplace les lettres accentuées usuelles par leur lettre de base.
            s = char(s);
            rep = {'àáâãäå', 'a'; 'ç', 'c'; 'èéêë', 'e'; 'ìíîï', 'i'; 'ñ', 'n'; 'òóôõö', 'o'; ...
                'ùúûü', 'u'; 'ýÿ', 'y'; 'ÀÁÂÃÄÅ', 'A'; 'Ç', 'C'; 'ÈÉÊË', 'E'; 'ÌÍÎÏ', 'I'; ...
                'Ñ', 'N'; 'ÒÓÔÕÖ', 'O'; 'ÙÚÛÜ', 'U'; 'Ý', 'Y'};
            for k = 1:size(rep, 1)
                s(ismember(s, rep{k, 1})) = rep{k, 2};
            end
            s = strrep(s, 'œ', 'oe');
            s = strrep(s, 'Œ', 'OE');
        end

        function tf = isBlank(v)
            % Vrai si v est vide (texte vide, missing ou tableau vide).
            if isempty(v)
                tf = true;
            elseif isstring(v)
                tf = all(ismissing(v)) || all(strlength(strtrim(v)) == 0);
            elseif ischar(v)
                tf = isempty(strtrim(v));
            else
                tf = false;
            end
        end

        function v = numField(s, f)
            % Valeur numérique scalaire d'un champ (NaN si absent ou vide).
            v = NaN;
            if isfield(s, f) && ~isempty(s.(f))
                x = s.(f);
                if (isnumeric(x) || islogical(x)) && isscalar(x) && isreal(x)
                    v = double(x);
                end
            end
        end

        function v = posField(s, f, required, default)
            % Champ numérique strictement positif ; valeur par défaut si absent / NaN.
            v = DataManager.numField(s, f);
            if ~isfinite(v)
                if required
                    error('MecaStruct:DataManager:invalidProfile', ...
                        'Le champ %s (SI) est requis et doit être un réel strictement positif.', f);
                end
                v = default;
            end
            if ~(isfinite(v) && v > 0)
                error('MecaStruct:DataManager:invalidProfile', ...
                    'Le champ %s doit être un réel strictement positif (valeur : %g).', f, v);
            end
        end

        function v = firstField(s, names)
            % Valeur numérique du premier champ présent parmi names ([] si aucun).
            v = [];
            for k = 1:numel(names)
                if isfield(s, names{k}) && ~isempty(s.(names{k}))
                    v = double(s.(names{k}));
                    return
                end
            end
        end

        function checkNu(nu)
            % Vérifie −1 < ν < 0,5.
            if ~(nu > -1 && nu < 0.5)
                error('MecaStruct:DataManager:invalidNu', ...
                    'Coefficient de Poisson hors de l''intervalle ]−1 ; 0,5[ : ν = %g.', nu);
            end
        end

        function note = appendNote(note, txt)
            % Ajoute une phrase à une note (sans doublon).
            note = char(note);
            if contains(note, txt)
                return
            end
            if isempty(strtrim(note))
                note = txt;
            else
                note = [strtrim(note) ' ' txt];
            end
        end
    end
end
