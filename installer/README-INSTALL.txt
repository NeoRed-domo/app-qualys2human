=====================================================
  Qualys2Human - Guide d'installation rapide
  NeoRed (c) 2026
=====================================================

PREREQUIS
---------
- Windows Server 2019 ou superieur
- Aucun logiciel a installer au prealable
  (Python, PostgreSQL et WinSW sont inclus dans le package)

INSTALLATION
------------
1. Extraire l'archive ou lancer le .exe auto-extractible
   en tant qu'administrateur.

2. L'installateur demarre automatiquement.
   Suivre les instructions a l'ecran:
   - Repertoire d'installation (defaut: C:\Q2H)
   - Port HTTPS (defaut: 8443)
   - Mot de passe administrateur (obligatoire, 10+ caracteres)
   - Nom du service Windows (defaut: Qualys2Human)

3. L'installateur va automatiquement:
   - Verifier les prerequis (OS, espace disque, port)
   - Installer PostgreSQL en mode silencieux
   - Generer un certificat TLS auto-signe
   - Copier les fichiers applicatifs
   - Generer la configuration (config.yaml)
   - Creer et demarrer le service Windows

4. L'application est accessible a:
   https://localhost:8443 (ou le port choisi)

PREMIER LANCEMENT
-----------------
- Identifiant: admin
- Mot de passe: celui choisi a l'installation
- Le service demarre automatiquement au boot du serveur.

MISE A JOUR
-----------
1. Extraire la nouvelle version dans un dossier temporaire
2. Executer installer\upgrade.bat en tant qu'administrateur
3. La mise a jour sauvegarde automatiquement:
   - La configuration (config.yaml, certificats, cles)
   - La base de donnees (dump SQL)
   Backup dans: <repertoire>\backups\YYYY-MM-DD-HHmm\
4. En cas d'echec, rollback automatique

DESINSTALLATION
-----------
1. Executer installer\uninstall.bat en tant qu'administrateur
2. Choisir si la base de donnees doit etre supprimee
3. Le service et les fichiers sont supprimes

CONFIGURATION
-------------
Fichier de configuration: <repertoire>\config.yaml

Sections principales:
- server: port, certificats TLS
- database: connexion PostgreSQL (mot de passe auto-genere)
- watcher: surveillance automatique de dossiers pour import CSV

FILE WATCHER (Import automatique)
---------------------------------
Pour activer l'import automatique de fichiers CSV:
1. Editer config.yaml
2. Mettre watcher.enabled a true
3. Ajouter les chemins a surveiller dans watcher.paths
4. Redemarrer le service:
   WinSW-x64.exe restart Qualys2Human.xml

CERTIFICATS TLS
---------------
Un certificat auto-signe est genere a l'installation.
Pour utiliser un certificat d'entreprise:
1. Remplacer les fichiers dans <repertoire>\certs\
   - server.crt (certificat)
   - server.key (cle privee)
2. Redemarrer le service

GESTION DU SERVICE
------------------
Le service est gere via WinSW (dans le repertoire d'installation):
- Demarrer:      WinSW-x64.exe start Qualys2Human.xml
- Arreter:       WinSW-x64.exe stop Qualys2Human.xml
- Redemarrer:    WinSW-x64.exe restart Qualys2Human.xml
- Statut:        WinSW-x64.exe status Qualys2Human.xml
- Desinstaller:  WinSW-x64.exe uninstall Qualys2Human.xml

SUPPORT
-------
Repository: https://github.com/NeoRed-domo/Qualys2Human
