# Changelog

Toutes les modifications notables du projet Qualys2Human sont documentees ici.

Format de version : `MAJOR.EVOLUTION.MINOR.BUILD`

---

## [1.1.13.2] - 2026-03-16

### Nouvelles fonctionnalites

- **Switchs admin visibilite widgets Tendances** — les admins peuvent masquer/afficher chaque widget pour les utilisateurs via un toggle direct sur le widget. Badge "Masque" + opacite 50% pour les widgets desactives. Bouton "Vue utilisateur" pour simuler la vue.
- **Exclusion mutuelle services** — Q2H arrete l'Updater au demarrage et inversement. Permet la maintenance non planifiee en lancant simplement le service Updater.

---

## [1.1.13.1] - 2026-03-16

### Corrections

- **Widget repartition OS comptait les vulns au lieu des serveurs** — `COUNT(LatestVuln.id)` remplace par `COUNT(DISTINCT Host.id)` sur os_class_distribution et os_type_distribution. Un serveur avec 100 vulns etait compte 100 fois.

---

## [1.1.13.0] - 2026-03-15

### Nouvelles fonctionnalites

- **Systeme de mise a jour web fonctionnel** — upload, validation, planification et execution automatique via l'interface admin
- **Widget repartition OS concentrique** — donut 2 niveaux sur la Vue d'ensemble (classe + type OS)
- **Barre de progression Tendances** — progression simulee avec 3 phases de messages contextuels
- **Script reset-upgrade.py** — nettoyage automatique d'un upgrade bloque (DB + fichiers + services)

### Ameliorations

- **Bandeau maintenance ameliore** — heure exacte + countdown lisible (1h28, 28 min, < 1 min) + bandeau "Mise a jour en cours..." quand status running
- **Bandeau echec upgrade** — bandeau rouge admin si echec (1h, masque si un succes plus recent existe)
- **Page maintenance Updater** — sert la page HTML pour toutes les routes (plus de 404)
- **Version masquee sur login** — le numero de version n'est plus affiche sur la page de connexion (securite)
- **Auto-install service Updater** — le scheduler installe automatiquement le service Windows si absent
- **Persistance package upgrade** — copie vers `upgrades/` au scheduling (plus de perte du zip temporaire)
- **Arret service propre** — `sc stop` au lieu de SIGTERM (evite le redemarrage WinSW)
- **HMAC .env** — lecture du secret depuis .env (meme source que l'Updater)
- **Health check service** — verification via `sc query` au lieu du port HTTP
- **Build inclut updater/** — `build.py` copie le dossier updater dans dist
- **Upgrade manuelle inclut updater/** — `upgrade.py` copie aussi updater/

### Corrections

- **Bandeau "0 minutes"** — suffixe Z ajoute aux datetimes UTC dans l'API
- **"Launch now" sans package** — fallback sur le schedule pending existant
- **Package introuvable** — copie vers emplacement stable au scheduling

---

## [1.1.12.3] - 2026-03-14

### Nouvelles fonctionnalites

- **Widget repartition OS concentrique** — donut 2 niveaux sur la Vue d'ensemble (anneau interieur : classe OS, anneau exterieur : type OS — Windows Server, Ubuntu, RHEL, etc.)

### Ameliorations

- **Bandeau maintenance : heure exacte + countdown lisible** — affiche l'heure de la maintenance + temps restant en format "1h28", "28 min", ou "moins d'une minute"
- **Diagnostic echec upgrade** — bandeau rouge admin si le scheduler d'upgrade echoue (affiche l'erreur exacte pendant 10 min)
- **Logs scheduler upgrade** — log au demarrage + log quand un schedule est detecte

---

## [1.1.12.2] - 2026-03-14

### Ameliorations

- **Barre de progression sur la page Tendances** — remplace le spinner generique par une barre de progression simulee avec messages contextuels (3 phases : chargement metriques → calcul tendances → preparation graphiques)

---

## [1.1.12.1] - 2026-03-14

### Corrections

- **Bandeau maintenance affichait "0 minutes"** — les datetimes UTC renvoyees par l'API `/upgrade/schedule` manquaient le suffixe `Z`, causant une interpretation en heure locale par le navigateur et un decalage egal a l'offset UTC

---

## [1.1.12.0] - 2026-03-14

### Nouvelles fonctionnalites

- **5 nouveaux widgets Tendances** :
  - Vulnerabilites critiques — courbe dediee severite 4 et 5
  - Taux de remediation (%) — pourcentage de vulns corrigees par periode
  - Temps moyen de remediation (jours) — duree moyenne de correction
  - Age moyen des vulns ouvertes (jours) — anciennete moyenne des vulns non corrigees
  - Repartition par categorie — courbes multiples par layer
- **Group by layer** — support de `group_by: 'layer'` dans l'API tendances
- **Resolution des noms de layers** — les courbes de repartition affichent les noms de categories, pas les IDs

### Ameliorations

- Index de performance `ix_vuln_remediation` pour les requetes de remediation
- Snapshots pre-calcules pour les 3 nouvelles metriques (avg_remediation_days, remediation_rate, avg_open_age_days)
- Export PDF inclut les 7 graphiques de tendances
- Aide contextuelle mise a jour avec description des 7 widgets

---

## [1.1.11.1] - 2026-03-14

### Nouvelles fonctionnalites

- **Systeme de mise a jour web (backend)** — Infrastructure complete pour les mises a jour applicatives via l'interface web :
  - Upload chunke avec verification SHA-256 par chunk et reprise
  - Signature Ed25519 des packages (cle privee sur machine de build, cle publique embarquee)
  - Validation de package (integrite zip, signature, comparaison de version)
  - Planification des mises a jour (minimum 15 min dans le futur) avec option immediat (60s)
  - Notifications progressives de maintenance (info 48h, warning 2h, danger 15min)
  - Scheduler en background (poll 30s, pre-flight checks, 3 retries max)
  - Communication IPC securisee HMAC-SHA256 avec le service Q2H-Updater
  - Historique des mises a jour avec statut et duree
  - Detection d'upgrade interrompu au demarrage
- **Q2H-Updater service** — Service Windows standalone d'orchestration des mises a jour :
  - Package Python independant `updater/q2h_updater/` (aucune dependance Q2H)
  - Lecture config.yaml et .env standalone (pas de PyYAML)
  - Verification HMAC-SHA256 du fichier upgrade-request.json (single-use, supprime apres lecture)
  - 6 etapes sequentielles : backup DB (pg_dump), backup fichiers, extraction package, migrations Alembic, refresh mat. view, redemarrage service
  - Rollback automatique complet en cas d'echec (fichiers + base de donnees)
  - Page de maintenance HTTPS statique (4 langues FR/EN/ES/DE, polling /upgrade-status toutes les 2s)
  - Isolation runtime : execution depuis `tmp/python_updater/` (copie Python, ._pth patche)
  - Enregistrement des resultats directement en DB via psycopg2 (Q2H arrete pendant la mise a jour)
  - Service WinSW Manual start (`Qualys2Human-Updater`)
  - 23 tests unitaires et d'integration

### Packaging

- **Installeur** — Copie du repertoire `updater/`, installation du service Qualys2Human-Updater
- **Package** — Inclusion de `updater/` dans l'archive .zip (tests exclus)
- **Scheduler** — Copie du runtime Python via `asyncio.to_thread` (non-bloquant) + patch ._pth

### Frontend — Page admin Mise a jour

- **UpgradeManager** — Nouvelle page admin (`/admin/upgrade`) avec 4 zones :
  - Zone 1 : Etat actuel (version, statut, planification active avec boutons Annuler/Lancer)
  - Zone 2 : Upload & Planification — upload chunke .zip (2 Mo) avec barre de progression, upload .sig, validation (signature, version, integrite), planification DatePicker + seuils de notification configurables, lancement immediat avec confirmation
  - Zone 3 : Historique des 50 dernieres mises a jour (tableau avec statut, duree, erreurs)
  - Zone 4 : Parametres de notification par defaut
- **Internationalisation** — 4 langues (FR, EN, ES, DE) : ~70 cles admin.upgrade.* + aide contextuelle admin-upgrade (4 sections)
- **Onglet admin** — Nouvel onglet "Mise a jour" dans le panneau d'administration
- **Aide contextuelle** — Nouveau topic `admin-upgrade` dans HelpPanel (upload, validation, planification, historique)
- **Auto-refresh** — Polling toutes les 10s pendant qu'une mise a jour est en cours
- **Fallback crypto** — Support des environnements non-HTTPS (FNV-1a fallback pour les checksums d'upload)

### Corrections (code review)

- **Alignement types frontend/backend** — ValidationResult (valid/signature_ok/version_ok), Settings (default_thresholds), History (initiated_by_username)
- **Version courante** — Affichage depuis `/api/version` au lieu du champ schedule.target_version
- **Code mort** — Suppression de l'affichage scheduled_by (non retourne par GET /schedule)

### Securite

- **Path traversal upload** — Sanitisation du nom de fichier via `os.path.basename()` + validation `.zip`
- **Directory traversal upload_id** — Validation UUID format sur l'identifiant d'upload
- **Audit logging** — Ajout d'entrees AuditLog sur cancel_upload et validate_package
- **Validation thresholds** — Les seuils de notification sont valides dans schedule_upgrade (pas seulement dans settings)
- **Type assertion** — Verification Ed25519PrivateKey dans sign_package
- **Info leak** — Suppression du chemin interne sig_path de la reponse upload-sig

### Migration

- Nouvelles tables `upgrade_schedules` et `upgrade_history` (18e migration)
- Index unique partiel `uix_upgrade_schedules_active` — un seul upgrade pending/running a la fois

---

## [1.1.11.0] - 2026-03-13

### Nouvelles fonctionnalites

- **Propositions de regles de categorisation** — Les utilisateurs peuvent proposer des regles depuis la page QIDs non categorises ou les fiches de vulnerabilites. Workflow complet : proposer → revue admin → approuver/modifier/rejeter.
- **Page "Mes propositions"** — Nouvelle page utilisateur pour suivre ses propositions (statut, commentaire admin).
- **Section propositions en attente** — En haut de la page Regles (admin), affiche les propositions avec infos utilisateur (prenom, nom, date). Actions : Approuver / Modifier & Approuver / Rejeter.
- **Acces page QIDs non categorises** — La page orphelines est maintenant accessible a tous les utilisateurs (lecture + proposition). Les controles admin (creation directe, reclassification) restent reserves aux admins.
- **Bouton "Proposer une categorisation"** — Sur les fiches VulnDetail et FullDetail, visible quand le QID n'est pas categorise.
- **Badge propositions** — Compteur de propositions en attente dans le menu admin Regles.

### Ameliorations

- **Suppression de la priorite numerique** — L'ordre des regles est maintenant base sur la date de creation (derniere creee = prioritaire). Backfill automatique depuis les priorites existantes.
- **Colonne "Date de creation"** — Remplace la colonne priorite dans la page Regles.
- **Audit logging** — Toutes les actions de propositions (creation, annulation, approbation, rejet) sont tracees dans le journal d'audit.

### Migration

- Nouvelle table `rule_proposals` (17e migration)
- Ajout `created_at` sur `vuln_layer_rules` (backfill depuis priorite existante)
- Colonne `priority` conservee (deprecated) — suppression prevue dans une version future

---

## [1.1.10.0] - 2026-03-13

### Nouvelles fonctionnalites

- **Purge automatique des donnees** — Les rapports de scan plus anciens que la duree de retention configuree (defaut : 24 mois) sont automatiquement purges au demarrage de l'application. La purge s'execute en tache de fond (non-bloquante) et supprime les rapports, vulnerabilites, jobs d'import et checks de coherence associes.
- **Bouton de purge manuelle** — Sur la page Monitoring, un bouton "Purger les donnees obsoletes" (admin uniquement) permet de declencher la purge a tout moment, avec confirmation modale et affichage du resultat.
- **Duree de retention configurable** — Nouveau parametre dans Admin > Parametres : duree de retention des donnees (6 a 120 mois). Valeur seedee par defaut a 24 mois.
- **Alerte de purge recommandee** — La page Monitoring affiche un bandeau d'information quand des rapports depassent la duree de retention (visible uniquement pour les admins).

### Ameliorations

- **Page Parametres i18n** — Les textes hardcodes en francais de la page Parametres ont ete migres vers des cles de traduction i18next (4 langues).

### Technique

- Service `backend/src/q2h/services/retention.py` : `purge_expired_data()`, `count_purgeable_reports()`, `get_purgeable_reports()`
- Suppression en ordre FK-safe (ReportCoherenceCheck → ImportJob → Vulnerability → ScanReport)
- Garde de concurrence : purge bloquee pendant un import actif (flag in-memory + check DB)
- Audit log automatique pour chaque purge (user, nb rapports/vulns, duree retention)
- Endpoints : `GET/PUT /api/settings/retention`, `POST /api/monitoring/purge`, `GET /api/monitoring/purge/preview`
- Seed `retention_months=24` dans `seed_defaults()`

---

## [1.1.9.1] - 2026-03-12

### Performance

- **Index couvrant `ix_vuln_trends`** — Index composite sur `(scan_report_id, severity, host_id, layer_id, type)` pour les requetes de tendances filtrees. PostgreSQL fait un index-only scan sur ~500 Mo au lieu de parcourir 20 Go de colonnes TEXT. Reduit le temps de chargement de 20s a quelques secondes sur les grosses bases.

---

## [1.1.9.0] - 2026-03-11

### Nouveautes

- **Table pre-agregee `trend_snapshots`** — Les tendances se chargent instantanement en lisant ~200 lignes pre-calculees au lieu de scanner des millions de vulnerabilites. Calcul automatique apres chaque import, reclassification, suppression.
- **Widget combo Moyenne vulns/serveur** — Le widget existant est enrichi avec un histogramme semi-transparent du nombre de serveurs en arriere-plan de la courbe de moyenne. Double axe Y (gauche : moyenne, droite : nombre de serveurs).
- **Widget Nombre de serveurs** — Nouvelle courbe d'evolution du nombre de serveurs dans le temps.
- **Endpoint batch** — Une seule requete API `POST /trends/query` accepte plusieurs metriques et retourne toutes les series d'un coup. Lecture depuis les snapshots (sans filtres) ou fallback sur requete live (avec filtres).
- **Taille de la base de donnees** — Affichage de la taille de la base PostgreSQL sur la page Monitoring (Mo/Go automatique).

### Technique

- Nouvelle migration Alembic : table `trend_snapshots` avec contrainte unique + index + population initiale
- Service `trend_snapshots.py` : `recompute_all_snapshots()` et `recompute_snapshots_for_reports()`
- Hooks sur les 6 points de mutation de donnees (import, reset, delete-report, assign-layer, delete-layer, reclassify)
- Nouveau composant React `TrendComboChart.tsx` (Recharts ComposedChart)

---

## [1.1.8.3] - 2026-03-11

### Corrections

- **Vue d'ensemble : NameError crash** — Le refactoring de `dashboard.py` (extraction de `_build_overview`) a oublie de deballer `report_id` du tuple `fargs`, causant un `NameError` systematique sur le endpoint `/api/dashboard/overview`.

---

## [1.1.8.2] - 2026-03-11

### Corrections

- **Vue materialisee non peuplee apres rollback** — Apres un rollback avec restauration DB echouee (timeout), la vue `latest_vulns` existait mais n'etait pas peuplee. Le `lifespan` FastAPI verifie maintenant `pg_matviews.ispopulated` au demarrage et lance un `REFRESH MATERIALIZED VIEW` si necessaire. L'upgrade script fait de meme apres les migrations.
- **Timeout restauration DB** — Augmente de 300s (5min) a 900s (15min) pour supporter les grosses bases (la restauration du POC timeoutait a 300s).

---

## [1.1.8.1] - 2026-03-11

### Corrections

- **Tendances : 1 seul point de donnees** — Le filtre de fraicheur global (`freshness: active`) etait applique aux requetes Tendances sur la table brute `Vulnerability`, filtrant tout l'historique sauf la derniere semaine. Les tendances forcent maintenant `freshness: all` (la plage de dates gere le perimetre temporel).
- **`_make_interval_days`** — Retour a la syntaxe `text("interval 'N days'")` au lieu de `func.make_interval()` pour une compatibilite maximale avec asyncpg.
- **`upgrade.py` : ._pth non re-patche** — Apres remplacement du repertoire `python/`, le fichier `._pth` perdait le chemin `..\\app\\backend\\src`. Ajout de `_patch_pth()` dans `upgrade_files()` pour re-appliquer le patch systematiquement.

### Ameliorations

- **Journalisation amelioree** — `logger.exception()` ajoute sur les endpoints Dashboard, Recherche et Tendances. Les erreurs SQL/Python sont maintenant tracees dans `logs/q2h.log`.
- **Health check upgrade** — Augmentation des tentatives de 10 a 20 et du delai de 3s a 5s pour supporter les grandes bases de donnees lors des mises a jour.

---

## [1.1.8.0] - 2026-03-10

### Nouvelles fonctionnalites

- **Internationalisation FR/EN/ES/DE** — L'interface de Qualys2Human est desormais disponible en 4 langues : francais, anglais, espagnol, allemand. La langue est detectee automatiquement depuis le navigateur, avec possibilite de la fixer manuellement dans la page Mon Profil.
- **Page Mon Profil** — Nouvelle page Mon Profil avec selecteur de langue et informations du compte. Remplace le placeholder "Coming soon".
- **Aide contextuelle traduite** — Les 14 topics du panneau d'aide sont traduits dans les 4 langues.

### Corrections

- **Premiere connexion** — Le popup de nouveautes ne s'affiche plus inutilement lors de la toute premiere connexion d'un utilisateur. La version courante est initialisee silencieusement.

### Ameliorations

- **Messages d'erreur backend standardises** — Les HTTPException retournent desormais des codes d'erreur (INVALID_CREDENTIALS, ACCOUNT_LOCKED, etc.) au lieu de messages en francais. Le frontend traduit ces codes dans la langue active.
- **Ant Design locale dynamique** — Les composants natifs Ant Design (pagination, validation, dates) s'affichent dans la langue active de l'utilisateur.
- **Release notes multilingues** — Les notes de version >= 1.1.8.0 sont disponibles dans les 4 langues. Les anciennes versions restent en francais.

### Technique

- Stack i18n : `react-i18next` + `i18next` + `i18next-browser-languagedetector`
- 4 fichiers de traduction : `frontend/src/locales/{fr,en,es,de}.json` (~430 cles chacun)
- Configuration : `frontend/src/i18n.ts` (detection navigateur, fallback anglais)
- Preference langue : `User.preferences.language` (JSONB) via `GET/PUT /api/user/preferences`
- Chaine de resolution : preference DB > langue navigateur > anglais (fallback)
- ~40 fichiers frontend modifies pour remplacer le texte hardcode par des appels `t()`
- HelpPanel.tsx reduit de ~460 a ~95 lignes (contenu externalise dans les JSON)
- 6 fichiers backend modifies (codes d'erreur au lieu de messages francais)
- Release notes : format multi-langue `{fr, en, es, de}` pour les nouvelles versions

---

## [1.1.7.0] - 2026-03-10

### Nouvelles fonctionnalites

- **Popup multi-versions** — Le popup de nouveautes affiche desormais toutes les mises a jour depuis la derniere connexion de l'utilisateur. Un utilisateur absent depuis plusieurs versions voit l'integralite des changements, groupes par version (plus recent en premier), dans un modal scrollable.

### Ameliorations

- **Suppression du lien GitHub** — Le lien vers le changelog sur GitHub a ete retire du popup de nouveautes (depot devenu prive).
- **Section "Nouveautes" dans le popup** — Le champ `features` est maintenant affiche dans le popup (icone etoile), en plus des corrections et ameliorations.

### Technique

- Backend : nouveau fichier `release_history.py` contenant l'historique complet des release notes (18 versions)
- Backend : endpoint `GET /api/version` retourne desormais `{current, notes: [...]}` au lieu d'un seul objet
- Frontend : `WhatsNewModal.tsx` reecrit pour accepter un tableau de versions
- Frontend : `MainLayout.tsx` filtre les notes non vues cote client (basé sur `last_seen_version`)

---

## [1.1.6.0] - 2026-03-10

### Nouvelles fonctionnalites

- **Page Tendances v2** — Refonte complete de la page Tendances avec les memes filtres globaux que la Vue d'ensemble (severites, types, categorisation, classe OS, fraicheur, regles entreprise).
- **Graphique : moyenne de vulnerabilites par serveur** — Nouveau graphique montrant l'evolution du ratio vulns/serveur dans le temps, avec granularite configurable (jour, semaine, mois).
- **Raccourcis temporels** — Boutons 3 mois, 6 mois, 1 an synchronises avec le selecteur de dates libre. Le segment se desactive automatiquement si l'utilisateur modifie les dates manuellement.
- **Granularite configurable** — Selecteur jour/semaine/mois pour la precision temporelle des graphiques. Valeur par defaut parametrable dans les regles entreprise (`trend_granularity` dans AppSettings, defaut `week`).
- **Widgets reordonnables et masquables** — Chaque graphique peut etre affiche/masque via un panneau de configuration, et reordonne par drag & drop. Les preferences sont sauvegardees par utilisateur.
- **Auto-refresh debounce** — Les graphiques se rechargent automatiquement (300ms debounce) a chaque changement de filtre, periode ou granularite.

### Corrections

- **Securite : statement_timeout parametre** — La requete `SET LOCAL statement_timeout` est desormais parametree pour prevenir toute injection SQL.
- **Borne date_to corrigee** — La borne superieure de date utilise desormais une exclusion stricte (+1 jour) pour inclure les donnees du jour selectionne.

### Technique

- Backend : nouveau metric `avg_vulns_per_host` dans `POST /api/trends/query` (COUNT vulns / NULLIF COUNT DISTINCT hosts)
- Backend : endpoint `GET /api/trends/default-granularity` (lecture `AppSettings`)
- Backend : champs `types`, `layers`, `os_classes`, `freshness`, `granularity` ajoutes a `TrendQueryRequest`
- Backend : `TrendDataPoint.value` passe de `int` a `float`
- Backend : `trends_layout` ajoute aux preferences utilisateur + endpoint `DELETE /user/preferences/trends-layout`
- Frontend : nouveau composant `TrendTimeBar` (Segmented + RangePicker + selecteur granularite)
- Frontend : nouveau composant `TrendWidgetGrid` (show/hide toggle + drag-to-reorder + persistence)
- Frontend : `TrendChart` formate les valeurs a 1 decimale (Tooltip + YAxis)
- Frontend : `Trends.tsx` entierement reecrit (FilterBar partage + TrendTimeBar + TrendWidgetGrid)
- Suppression de `TrendBuilder.tsx` (remplace par FilterBar + TrendTimeBar)

---

## [1.1.5.0] - 2026-03-03

### Nouvelles fonctionnalites

- **Nom et prenom utilisateurs** — Ajout des champs `first_name` et `last_name` au modele User. Les administrateurs peuvent renseigner le prenom et le nom lors de la creation ou l'edition d'un compte local.
- **Recuperation automatique depuis Active Directory** — A chaque connexion AD, les attributs `givenName` (prenom) et `sn` (nom) sont extraits automatiquement et stockes en base. Fallback sur le split de `displayName` si les attributs individuels sont absents.
- **Colonne « Nom » dans la gestion des utilisateurs** — La liste admin affiche desormais une colonne « Nom » avec le prenom et le nom concatenes.
- **Affichage du nom complet dans le header** — Le header de l'application affiche « Prenom Nom » au lieu du login technique. Si le nom n'est pas renseigne, le username est affiche en fallback.
- **Endpoint `/auth/me` enrichi** — Retourne desormais `first_name` et `last_name` en plus de `username`, `profile` et `must_change_password`.

### Corrections de securite

- **Path traversal sur upload CSV** — Le nom de fichier uploade etait utilise directement comme chemin cible, permettant l'ecriture de fichiers en dehors du repertoire prevu via des sequences `../`. Corrige : utilisation d'un nom UUID genere cote serveur.
- **Authorization upload CSV** — L'endpoint `POST /api/imports/upload` utilisait `get_current_user` au lieu de `require_admin`, permettant a tout utilisateur authentifie de declencher des imports CSV. Corrige : restriction aux administrateurs uniquement.

### Technique

- Migration Alembic `d4e5f6a7b8c9` : ajout colonnes `first_name` (String 100) et `last_name` (String 100) nullable sur la table `users`
- `LdapAuthResult` enrichi avec `first_name` et `last_name`
- `UserCreate`, `UserUpdate`, `UserResponse` enrichis avec `first_name` et `last_name`
- `MeResponse` enrichi avec `first_name` et `last_name`
- `AuthContext.tsx` : interface `User` enrichie avec `firstName` et `lastName`
- `MainLayout.tsx` : affichage `[firstName, lastName].filter(Boolean).join(' ') || username`
- `UserManagement.tsx` : colonne « Nom », champs formulaire « Prenom » et « Nom »

---

## [1.1.4.1] - 2026-03-03

### Corrections de securite

- **Validation serveur de l'identite** — L'identite utilisateur (username, profil) n'est plus jamais lue depuis localStorage. Un nouvel endpoint `GET /api/auth/me` valide le JWT et retourne l'identite reelle depuis la base de donnees. L'injection `localStorage.setItem("user", ...)` via la console navigateur n'a plus aucun effet.
- **Revalidation DB des privileges** — Les dependencies `require_admin` et `require_data_access` passent desormais par `get_verified_user` qui verifie en base que l'utilisateur existe, est actif, n'est pas verrouille, et que son profil actuel correspond. Un token JWT avec un profil obsolete (ex: apres retrogradation) est rejete immediatement.
- **SECRET_KEY dynamique** — La cle de signature JWT est desormais chargee depuis la variable d'environnement `JWT_SECRET` (generee par l'installeur). Le fallback `dev-secret-change-in-prod` ne s'applique qu'en mode developpement.
- **Spinner de verification** — Au chargement de page, un spinner s'affiche pendant la verification serveur, empechant tout flash d'interface non autorisee.

### Technique

- Nouveau endpoint `GET /api/auth/me` dans `auth.py` (valide JWT + check DB user/profile/active/locked)
- Nouvelle dependency `get_verified_user` dans `dependencies.py` (remplace la confiance aveugle au JWT pour admin/data_access)
- `AuthContext.tsx` reecrit : `user` est initialise a `null`, seul `verifyIdentity()` (appel serveur) peut le remplir
- `router.tsx` : `PrivateRoute` affiche un spinner pendant `loading` au lieu de rediriger vers login
- `service.py` : `SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-in-prod")`

---

## [1.1.4.0] - 2026-03-02

### Nouvelles fonctionnalites

- **Mode sombre / clair (Dark Mode)** — Toggle dans le header (icone soleil/lune) pour basculer entre mode clair et mode sombre. Le choix persiste entre sessions via localStorage.
- **Ant Design darkAlgorithm** — Tous les composants natifs Ant Design (Card, Table, Modal, Form, Menu, etc.) s'adaptent automatiquement au theme choisi.
- **AG Grid theme adaptatif** — Les grilles AG Grid utilisent `themeQuartz` avec `colorScheme` dynamique (light/dark).
- **Tokens de theme custom** — Bandeaux QID (orange/bleu), tooltips Recharts, widget drag handles, footer, login page, previews admin s'adaptent au mode sombre.
- **ThemeContext** — Nouveau contexte React (`ThemeProvider`, `useTheme`) fournissant `isDark`, `toggleTheme()` et un objet `tokens` de couleurs semantiques.

### Technique

- Aucun changement backend (purement frontend)
- `ThemeProvider` wrape `ConfigProvider` dans `App.tsx` — le `darkAlgorithm` d'Ant Design gere ~80% du theming
- Les ~20% restants (styles inline) utilisent des tokens semantiques (headerBg, contentBg, surfaceSecondary, etc.)
- Les couleurs semantiques (severites, OS class, layers) restent identiques dans les deux modes
- Le PDF export reste toujours en mode clair

### Fichiers impactes

- `frontend/src/contexts/ThemeContext.tsx` (nouveau)
- `frontend/src/App.tsx`, `frontend/src/layouts/MainLayout.tsx`
- Composants : AppFooter, AnnouncementBanner, CategoryBar, WidgetGrid
- Pages : Login, VulnDetail, FullDetail, Branding
- Pages AG Grid : VulnList, HostList, HostDetail, BasicSearch, OrphanVulns

---

## [1.1.3.0] - 2026-03-02

### Nouvelles fonctionnalites

- **Filtres globaux sur HostDetail** — La fiche serveur respecte desormais les filtres globaux (severites, types) configures dans la barre laterale. Vue filtree par defaut avec toggle pour basculer en vue complete.
- **Toggle Vue filtree / Tout afficher** — Composant Segmented au-dessus des camemberts pour basculer entre les deux modes. Les filtres locaux (clic camembert) sont reinitialises au changement de mode.
- **Resume des filtres actifs** — Tags affichant les filtres globaux actifs sous le toggle (severites et types).
- **Compteur vulns filtre** — Le champ Vulnerabilites dans la carte info affiche "X / total" quand des filtres globaux reduisent la liste.
- **Mode d'authentification par defaut** — L'administrateur peut choisir le mode pre-selectionne (Local ou Active Directory) sur la page de connexion, configurable dans les parametres LDAP.
- **Filtre fraicheur sur HostDetail** — Le filtre global de fraicheur (Actives / Peut-etre obsoletes) est desormais applique sur la fiche serveur. Le tag descriptif affiche les seuils en jours (ex: "Detectees il y a moins de 7 jours").

### Technique

- Filtrage 100% cote client (pas de changement backend) — les donnees sont deja chargees en totalite (page_size=500)
- Chaine de filtrage : filtres globaux → baseVulns → camemberts + filtres locaux → filteredVulns
- Camemberts recalcules sur baseVulns pour refléter la vue active
- Mode auth par defaut : cle `ldap_default_auth_mode` dans AppSettings, expose via `GET /ldap/enabled` (public), configurable via `PUT /ldap/settings`

---

## [1.1.2.0] - 2026-03-02

### Nouvelles fonctionnalites

- **Creation de regles depuis les fiches QID** — Sur VulnDetail et FullDetail, le Select d'assignation directe est remplace par un bouton "Creer une regle" qui ouvre un modal pre-rempli avec le titre de la vulnerabilite. Apres creation, une reclassification automatique est lancee.
- **Composant RuleCreateModal** — Modal reutilisable de creation de regle avec compteur dynamique de QIDs matches (debounce 300ms), sous-modal de creation de categorisation, et option de reclassification automatique.
- **Endpoint match-count** — `GET /api/layers/match-count?pattern=X&match_field=title|category` retourne le nombre de QIDs distincts matches par un pattern (ILIKE sur LatestVuln).

### Technique

- Suppression de l'assignation directe (`PUT /layers/assign`) sur VulnDetail et FullDetail — remplacee par creation de regle + reclassification
- Nouveau composant : `frontend/src/components/RuleCreateModal.tsx`
- OrphanVulns inchange (garde son propre modal inline)

---

## [1.1.1.0] - 2026-03-02

### Nouvelles fonctionnalites

- **Regles entreprise : Classe d'OS** — L'administrateur peut configurer un filtre par defaut sur la classe d'OS (Windows, Linux/Unix). Applique a la premiere connexion et via le bouton "Regles entreprise".
- **Regles entreprise : Fraicheur par defaut** — L'administrateur peut choisir la valeur initiale du filtre fraicheur (Active, Peut-etre obsolete, Tout) pour tous les utilisateurs.
- **Presets utilisateur enrichis** — Les presets personnels incluent desormais les dimensions Classe d'OS et Fraicheur.

### Corrections

- **Fix suppression utilisateur** — Erreur 500 lors de la suppression d'un utilisateur ayant des audit logs ou des presets (violation de cle etrangere). Les audit logs sont conserves (user_id mis a NULL), les presets utilisateur sont supprimes.

### Technique

- Migration Alembic `c3d4e5f6a7b8` : ajout colonnes `os_classes` et `freshness` aux tables `enterprise_presets` et `user_presets`

---

## [1.1.0.0] - 2026-03-01

### Nouvelles fonctionnalites

- **Authentification Active Directory** — Connexion via LDAP / LDAPS avec direct bind (pas de compte de service). Template UPN configurable, support STARTTLS et LDAPS.
- **Auto-provisionnement AD** — Les comptes Active Directory sont automatiquement crees en base de donnees a la premiere connexion, avec le profil determine par les groupes AD.
- **Mapping groupes AD → profils** — Configuration des DN de groupes AD pour chaque profil (admin, user, monitoring). Priorite : admin > user > monitoring.
- **Page d'administration LDAP** — Nouvel onglet dans l'administration avec configuration serveur, template UPN, base de recherche, attribut groupes, parametres TLS.
- **Test de connexion LDAP** — Bouton pour tester un direct bind avec des identifiants, avec resultat inline (succes/echec).
- **Login conditionnel AD** — Le selecteur Local/Active Directory n'apparait sur la page de login que si l'authentification AD est activee.
- **Aide contextuelle LDAP** — Nouveau topic dans le panneau d'aide avec documentation complete de la configuration LDAP.

### Technique

- Ajout dependance `ldap3>=2.9` (pure Python, compatible Windows offline)
- Nouveau service `auth/ldap_service.py` (LdapConfig, LdapAuthResult, LdapService)
- Nouveau router `api/ldap.py` (4 endpoints : settings GET/PUT, test POST, enabled GET)
- Configuration LDAP stockee dans `AppSettings` (table cle-valeur existante, aucune migration necessaire)

---

## [1.0.7.2] - 2026-03-01

### Corrections

- **Fix crash login 500** — `datetime.now(timezone.utc)` produit un datetime timezone-aware, incompatible avec les colonnes `TIMESTAMP WITHOUT TIME ZONE` via asyncpg. Corrige avec `_utcnow()` (naive UTC). Affectait login, verrouillage, et rotation des refresh tokens.
- **Fix flash interface authentifiee** — Apres fermeture/reouverture du navigateur, l'interface authentifiee apparaissait brievement avant la page de login. Ajout d'un etat `sessionChecked` qui bloque le rendu tant que la verification BroadcastChannel n'est pas terminee.

### Ameliorations

- **Page de login** — Formulaire plus compact (440px), logo reduit a 85%, footer colle sous le formulaire, meilleure compatibilite mobile portrait.

---

## [1.0.7.1] - 2026-02-28

### Nouvelles fonctionnalites

- **Timeout d'inactivite** — Session expiree automatiquement apres une periode d'inactivite configurable (defaut 2h). Popup d'avertissement avec compte a rebours X minutes avant l'expiration (defaut 5 min). Boutons "Rester connecte" (refresh token + reset timer) et "Se deconnecter".
- **Verrouillage de compte** — Apres 5 tentatives de connexion echouees, le compte est automatiquement verrouille pendant 15 minutes. Message d'erreur indiquant le temps restant.
- **Deverrouillage admin** — Bouton cadenas dans la gestion des utilisateurs pour deverrouiller manuellement un compte. Colonne "Statut" avec badges (Verrouille, X echec(s), OK).
- **Rotation des refresh tokens** — Chaque appel `/auth/refresh` emet un nouveau refresh token (JTI unique stocke en DB). Detection de reutilisation de token (invalidation immediate). Grace period de 60 secondes pour les requetes concurrentes.
- **Expiration session navigateur** — Fermer toutes les fenetres du navigateur invalide la session. Detection via `sessionStorage` + `BroadcastChannel` pour le multi-onglet.
- **Synchronisation cross-tab** — Deconnexion dans un onglet propage la deconnexion a tous les onglets (via `storage` event).
- **Parametres de session admin** — Card en haut de la page Gestion des utilisateurs : timeout d'inactivite (min 5 min) et avertissement avant expiration (min 1 min). Endpoints `GET/PUT /api/settings/session`.

### Ameliorations

- **Aide contextuelle** — Topic `admin-users` mis a jour pour documenter le timeout, verrouillage et deverrouillage.

---

## [1.0.7.0] - 2026-02-28

### Nouvelles fonctionnalites

- **Harmonisation des fiches QID** — Les deux fiches (QID globale et QID serveur) ont desormais une disposition identique : meme carte Descriptions bordered, memes champs au meme endroit, memes sections (Menace/Impact/Solution, Resultats du scan, Serveurs affectes). Les champs sans objet sur la fiche globale affichent « N/A ».
- **Bandeau d'identification colore** — Bandeau orange pour la fiche QID globale (`/vulnerabilities/:qid`), bandeau bleu pour la fiche QID serveur (`/hosts/:ip/vulnerabilities/:qid`). Identification visuelle instantanee sans avoir a lire.
- **Tableau serveurs sur les deux fiches** — Le tableau AG Grid des serveurs affectes et le camembert de statut de detection apparaissent desormais sur les deux fiches QID. Sur la fiche serveur, la ligne du serveur courant est surlignee en bleu clair.

### Ameliorations

- **Champs supplementaires fiche QID globale** — Ajout CVSS Temporal, CVSS3 Temporal, Bugtraq ID a `VulnDetailResponse` et a la fiche frontend.
- **Champs supplementaires fiche QID serveur** — Ajout Hotes affectes et Occurrences totales a `FullDetailResponse`.
- **Aide contextuelle** — Topics `vuln-detail` et `full-detail` mis a jour pour refleter la nouvelle disposition harmonisee.

---

## [1.0.6.0] - 2026-02-27

### Nouvelles fonctionnalites

- **Orphelines v2 — creation de regles** — Refonte complete de la page orphelines : bouton « Creer une regle » par QID ouvrant un modal pre-rempli (pattern, champ cible, categorisation, priorite). Compteur temps reel affichant le nombre de QID matches. Option « + Creer une categorisation » pour creer un layer sans quitter le workflow. Les QID matches disparaissent apres validation. Bouton « Lancer la reclassification » visible apres creation de regles, redirige vers la page Categorisation.
- **Categorisation unitaire sur fiche QID** — Les admins disposent d'un Select inline dans la fiche vulnerabilite (VulnDetail) pour assigner un layer directement. Update optimiste : l'UI se met a jour instantanement, l'appel API s'execute en arriere-plan avec rollback en cas d'erreur.

### Ameliorations

- **Endpoint GET /vulnerabilities/{qid}** — Retourne desormais `layer_id` et `layer_name` (outerjoin sur VulnLayer).
- **Aide contextuelle** — Topic `admin-layers` mis a jour pour refleter le workflow orphelines v2 (creation de regles au lieu d'assignation directe).

---

## [1.0.5.0] - 2026-02-27

### Nouvelles fonctionnalites

- **Bandeau d'annonce configurable** — L'admin peut configurer un bandeau sous la navigation : message (max 500 chars), 4 couleurs (info, warning, alerte, autre), 3 visibilites (tous, admins, desactive). L'utilisateur peut fermer le bandeau (revient au prochain login ou si le message change).
- **Bandeau de progression (BusyBanner)** — Affiche automatiquement en haut de page quand un import ou une reclassification est en cours. Barre de progression + detail. Reload automatique a la fin.
- **Page vulnerabilites orphelines** — Nouvelle page `/admin/layers/orphans` listant les QID non categorises (AG Grid, tri/filtre par severite). Assignation inline via Select dropdown.
- **Bouton « Categoriser les orphelines »** — Dans la page Categorisation, avec badge compteur du nombre de QID orphelins.

### Corrections

- **Fix dashboard fantome apres suppression rapport** — Ajout `REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vulns` apres `delete_report` et `reset_all`.
- **Fix BusyBanner invisible pendant import CSV** — Flag in-memory `_import_state` couvre le gap avant creation du job DB.
- **Fix aide contextuelle obsolete** — Mise a jour des 8 topics d'aide pour refleter toutes les features actuelles. Ajout du topic `admin-layers`.

### Ameliorations

- **Import CSV asynchrone** — L'upload retourne immediatement, le traitement s'execute en arriere-plan via `asyncio.create_task`.
- **Reclassification optimisee par QID** — SELECT DISTINCT QIDs → matching Python → batch UPDATE via VALUES join (x10 plus rapide).
- **File watcher non-bloquant** — `time.sleep()` remplace par `asyncio.sleep()` dans le watcher (ne bloque plus l'event loop).
- **Texte bandeau en gras** — Le texte du bandeau d'annonce est affiche en gras pour meilleure lisibilite.

---

## [1.0.4.1] - 2026-02-27

### Corrections

- **Fix crash upgrade PyYAML** — Les scripts installer (`upgrade.py`, `database.py`, `uninstall.py`, `config.py`) utilisaient `import yaml` (PyYAML) qui n'est pas disponible dans le Python systeme de l'installeur. Remplacement par un parseur YAML stdlib-only (`load_config()` dans `utils.py`). Corrige `ModuleNotFoundError: No module named 'yaml'` lors de la mise a jour.

---

## [1.0.4.0] - 2026-02-27

### Nouvelles fonctionnalites

- **Widget Repartitions triple donut** — Le dashboard affiche 3 donuts cote a cote : Criticites, Classe d'OS, Categorisation. Pleine largeur, responsive (empile en mobile).
- **Donut Classe d'OS** — Nouveau graphique repartition Windows / NIX / Autre, base sur `Host.os` avec CASE WHEN (12 patterns NIX). Endpoint `os_class_distribution` dans `/dashboard/overview`.
- **Drill-down Classe d'OS** — Clic sur une section du donut ouvre la nouvelle page `/hosts?os_class=X` avec la liste complete des serveurs de cette classe.
- **Drill-down Categorisation** — Clic sur une section du donut ouvre `/vulnerabilities?layer=X` avec la liste des vulns de cette categorisation.
- **Page Liste des serveurs** (`/hosts`) — Nouvelle page avec tableau AG Grid (IP, DNS, OS, Vulnerabilites), export PDF/CSV, clic ligne vers detail serveur.
- **Endpoint GET /hosts** — Liste de serveurs avec `vuln_count`, filtre `os_class` (windows, nix, autre).
- **Endpoint GET /vulnerabilities enrichi** — Nouveau filtre `layer` (0 = non classifie), colonnes `layer_name`/`layer_color` dans la reponse.

### Ameliorations

- **Layout dashboard flexbox** — Remplacement de react-grid-layout par un layout flexbox vertical avec `gap` uniforme. Espacement pixel-perfect, auto-dimensionnement des widgets. Drag-to-reorder conserve via HTML5 Drag & Drop.
- **Tableaux Top 10 auto-height** — AG Grid en `domLayout: autoHeight`, plus d'ascenseur. Les tableaux affichent toutes les lignes.
- **Tooltips donuts** — Affichent le nom de la section survolee (ex: "Urgent (5)", "Windows", nom de layer) au lieu du generique "Vulnerabilites".
- **KPI Quick-wins retire** — Le KPI Quick-wins (toujours a 0, non implemente) est retire du dashboard.
- **Tag Coherence retire** — Le tag "Coherence OK / Anomalies" est retire du dashboard (donnees toujours calculees cote backend pour usage futur).
- **Export PDF mis a jour** — Les 3 donuts (severite + OS class en paire, layer separement) sont inclus dans l'export PDF.
- **Colonne Categorisation dans VulnList** — La liste des vulnerabilites affiche desormais la categorisation avec badge couleur.
- **Card retiree des donuts** — SeverityDonut et LayerDonut n'ont plus de Card englobante (geree par le widget parent).

---

## [1.0.3.0] - 2026-02-26

### Nouvelles fonctionnalites

- **Export PDF par page (client-side)** — Bouton PDF sur chaque page (Overview, VulnList, VulnDetail, HostDetail, FullDetail, Trends). Generation 100% client-side via jsPDF + jspdf-autotable + html2canvas. Compatible offline/air-gapped. Inclut en-tete avec logo, KPIs, graphiques captures, tableaux programmatiques, blocs texte. Layout A4 portrait avec sauts de page automatiques et pieds de page.

---

## [1.0.3.0] - 2026-02-25

### Nouvelles fonctionnalites

- **Filtres per-user** — Chaque utilisateur conserve ses propres filtres dans un localStorage isole (`q2h_filters_{username}`). Login user A / logout / login user B : chacun retrouve ses filtres.
- **Bouton Regles entreprise** — Nouveau bouton (icone BankOutlined) dans la barre de filtres pour reappliquer le preset admin a jour en un clic. Re-fetch le preset depuis le backend pour avoir la derniere version.
- **Migration automatique** — L'ancienne cle partagee `q2h_filters` est automatiquement migree vers la cle per-user au premier login.

### Ameliorations

- **Zone de boutons FilterBar** — Les 2 colonnes (reset + presets) fusionnees en une seule colonne avec `Space`. Ordre : Reset, Regles entreprise, PresetSelector.

---

## [1.0.2.0] - 2026-02-25

### Nouvelles fonctionnalites

- **Drill-down interactif sur tous les graphiques** — Cliquer sur une section de camembert ou une barre filtre le tableau associe. Overview : filtre global par severite/categorie. VulnDetail : filtre par statut de detection. HostDetail : filtre par severite et methode de suivi.
- **Colonne Categorisation avec badge couleur** — Tous les tableaux de vulnerabilites (TopVulnsTable, HostDetail) affichent la categorisation avec un point de couleur.
- **Restriction profil monitoring** — Le profil monitoring n'a acces qu'a la page Monitoring. Backend `require_data_access` bloque l'acces aux donnees (403). Frontend `MonitoringGuard` redirige, navigation filtree.
- **Fraicheur integree dans Regles entreprise** — Les seuils de fraicheur (stale_days, hide_days) sont configurables depuis la page Regles entreprise. Page Parametres supprimee.

### Ameliorations

- **Logo reduit a 75%** — Le logo sur la page de connexion fait desormais 75% de sa taille precedente (`maxHeight: 135px`).
- **Page Parametres supprimee** — Fusionnee dans Regles entreprise. Tab et route retires.

### Corrections de bugs

- **Migration Alembic fiabilisee (BUG-005)** — Remplacement du driver asyncpg par psycopg2 synchrone pour les migrations Alembic, garantissant des transactions atomiques. Reecriture du rename avec un seul `UPDATE ... CASE WHEN` au lieu de multiple statements individuels. Corrige dans `backend/alembic/env.py`, `backend/alembic/versions/a1b2c3d4e5f6`, `installer/upgrade.py`.
- **Tooltip Top 10 cliquable** — Le tooltip du graphique Top 10 interceptait les clics (z-index eleve). Corrige avec `pointerEvents: 'none'` sur le wrapperStyle. Texte "Cliquer pour voir le detail" supprime.

---

## [1.0.1.0] - 2026-02-24

### Nouvelles fonctionnalites

- **Filtre fraicheur (freshness)** — Nouveau filtre frontend/backend pour distinguer les vulns actives, obsoletes ou toutes. Seuils configurables par admin (freshness_stale_days). Endpoints dashboard, vulns et export utilisent desormais la vue `latest_vulns`.
- **Page admin Freshness Settings** — Interface admin pour configurer les seuils de fraicheur et le champ `ignore_before` des watchers (DatePicker).
- **Modele AppSettings** — Table cle/valeur pour les parametres applicatifs globaux (freshness, etc). Migration Alembic `f7b4c5d63a29`.
- **Watcher : ignore_before** — Chaque watch_path supporte un champ `ignore_before` pour filtrer les fichiers CSV par date de modification. Expose dans l'API watcher.
- **Watcher : status enrichi** — Le status du watcher expose desormais : scanning, importing, last_import, last_error, import_count.
- **Popup "Nouveautes" apres login** — A la premiere connexion sur une nouvelle version, un modal affiche les corrections et ameliorations. Persiste par utilisateur via `last_seen_version` dans les preferences JSONB. Endpoint `GET /api/version` pour les release notes. Nouveau composant `WhatsNewModal.tsx`.

### Ameliorations

- **Header sticky** — Le menu de navigation reste visible au scroll. Modifie dans `frontend/src/layouts/MainLayout.tsx`.
- **Nouvelles categories de vulnerabilites** — Remplacement des 4 categories par defaut (OS / Middleware / Applicatif / Reseau) par : OS / Middleware-OS / Middleware-Application / Application. Migration Alembic `a1b2c3d4e5f6`.
- **Affichage de la version** — Version affichee dans le footer, recuperee depuis `/api/health`. Modifie dans `frontend/src/components/AppFooter.tsx`.
- **Import : report_date expose** — La date du rapport est desormais visible dans l'historique des imports.
- **Import : rollback sur erreur** — En cas d'echec d'import, la transaction est correctement annulee (rollback explicite).
- **Preferences : last_seen_version** — Le champ `last_seen_version` est persiste dans les preferences utilisateur JSONB.
- **Migrations host dates** — Les champs `first_seen`/`last_seen` des hosts sont recalcules depuis `report_date`. Migration `d5a2b3c41f07`.
- **Table watch_paths** — Nouvelle table pour configurer les chemins surveilles en BDD. Migration `e6f3a4d52b18`.
- **Favicons** — Ajout de favicons (32px, 192px, .ico) dans `frontend/public/`.
- **Securisation .gitignore** — Ajout de `data/`, `backend/config.yaml`, `memory/` aux exclusions.

### Corrections de bugs

- **upgrade.bat : crash des migrations Alembic** — Le script d'upgrade ne passait pas `Q2H_DATABASE_URL` au subprocess Alembic. Corrige dans `installer/upgrade.py`.
- **Categorisation non effective apres reclassification** — La vue materialisee `latest_vulns` n'etait pas rafraichie apres `_run_reclassify()` et `delete_layer()`. Corrige dans `backend/src/q2h/api/layers.py`.
- **Doublons de vulnerabilites par serveur** — Les endpoints hosts interrogeaient `Vulnerability` au lieu de `LatestVuln`. Corrige dans `backend/src/q2h/api/hosts.py`.
- **Preset entreprise non applique par defaut** — Ajout persistence localStorage (`q2h_filters`). Premier visit = enterprise preset, retour = preferences sauvegardees, reset = retour enterprise. Corrige dans `frontend/src/contexts/FilterContext.tsx`.
- **Tooltip Top 10 vulnerabilites non fonctionnel** — Remplace par le `<Tooltip content={...}>` natif Recharts. Corrige dans `frontend/src/components/dashboard/CategoryBar.tsx`.
- **Watcher : timezone ignore_before** — Suppression du timezone dans `ignore_before` pour eviter les comparaisons invalides.
- **Watcher : chemins UNC** — Autorisation des chemins UNC (`\\server\share`) sans validation de chemin local.
- **Installer : pipeline, login loop, branding paths, erreurs TS** — Corrections multiples du pipeline d'installation et du frontend.
- **Migration rename layers crash asyncpg** — L'utilisation de `op.execute()` avec des strings bruts causait un crash asyncpg. Remplace par `conn.execute(text(...))` explicite. Protection `COALESCE` sur le `setval` pour eviter NULL. Corrige dans `backend/alembic/versions/a1b2c3d4e5f6`.
- **Migration rename layers : UniqueViolationError** — Apres un echec partiel, la migration tentait de renommer des layers deja renommes. Migration rendue idempotente avec noms temporaires (`__tmp_N`). Corrige dans `backend/alembic/versions/a1b2c3d4e5f6`.
- **upgrade.py : erreur migrations tronquee** — Le message d'erreur des migrations etait tronque a 500 caracteres, masquant l'erreur PostgreSQL reelle. Affiche desormais les 30 dernieres lignes de stderr. Corrige dans `installer/upgrade.py`.
- **upgrade.py : rollback ne restaurait pas la DB** — Le rollback ne restaurait que les fichiers, pas la base de donnees. Ajout de la restauration du dump SQL (DROP SCHEMA + psql -f). Corrige dans `installer/upgrade.py`.
- **uninstall.py : PostgreSQL non supprime** — La desinstallation ne supprimait pas le service PostgreSQL (`postgresql-q2h`), bloquant la reinstallation (mot de passe superuser inconnu). Desormais, si on supprime la DB, le service PostgreSQL est aussi arrete et supprime. Corrige dans `installer/uninstall.py`.

---

## [1.0.0.0] - 2026-02-22

### Version initiale (V1)

- Dashboard Overview avec KPIs, Top 10 vulns/hosts, repartition severite et categories
- Drill-down 3 niveaux (overview -> vuln -> host)
- Import CSV Qualys (header, summary, detail) avec coherence checks
- File watcher : surveillance locale + UNC, auto-import
- Vue materialisee `latest_vulns` pour deduplication (host_id, qid)
- Systeme de categorisation par layers avec regles de pattern matching
- Filtres : severite, type, categorie, OS, fraicheur, dates, rapport
- Presets entreprise (admin) + presets utilisateur
- Authentification LDAPS + Kerberos (AD) + local bcrypt + JWT
- Profils : admin, user, monitoring, custom
- Export PDF + CSV sur chaque vue
- Tendances : templates admin + builder utilisateur
- Branding : logo custom + texte footer configurable
- Monitoring : health dashboard
- Installateur offline Windows + script d'upgrade avec backup/rollback
