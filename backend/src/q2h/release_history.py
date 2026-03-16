"""Release notes history — ordered newest-first.

Each entry contains user-facing changes only (no technical details).
Fields: version, date, title, features, fixes, improvements.

For versions >= 1.1.8.0, use multi-lang structure:
{
    "version": "1.1.8.0",
    "title": {"fr": "...", "en": "...", "es": "...", "de": "..."},
    "features": [{"fr": "...", "en": "...", "es": "...", "de": "..."}],
    "fixes": [{"fr": "...", "en": "...", "es": "...", "de": "..."}],
    "improvements": [{"fr": "...", "en": "...", "es": "...", "de": "..."}],
}
Older entries stay as plain French strings.
"""

RELEASE_NOTES_HISTORY: list[dict] = [
    {
        "version": "1.1.13.2",
        "date": "2026-03-16",
        "title": {
            "fr": "Visibilité widgets Tendances + Exclusion mutuelle services",
            "en": "Trends Widget Visibility + Service Mutual Exclusion",
            "es": "Visibilidad widgets Tendencias + Exclusión mutua servicios",
            "de": "Trends-Widget-Sichtbarkeit + Gegenseitiger Dienstausschluss",
        },
        "features": [
            {
                "fr": "Les admins peuvent masquer des widgets Tendances pour les utilisateurs (toggle direct sur chaque widget)",
                "en": "Admins can hide Trends widgets from users (toggle directly on each widget)",
                "es": "Los administradores pueden ocultar widgets de Tendencias para los usuarios",
                "de": "Admins können Trends-Widgets für Benutzer ausblenden",
            },
            {
                "fr": "Exclusion mutuelle des services Q2H et Updater (maintenance non planifiée possible)",
                "en": "Mutual exclusion between Q2H and Updater services (unplanned maintenance possible)",
                "es": "Exclusión mutua entre servicios Q2H y Updater (mantenimiento no planificado posible)",
                "de": "Gegenseitiger Ausschluss zwischen Q2H- und Updater-Diensten",
            },
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.1.13.1",
        "date": "2026-03-16",
        "title": {
            "fr": "Correctif répartition OS",
            "en": "OS Distribution Fix",
            "es": "Corrección distribución SO",
            "de": "Betriebssystemverteilung-Korrektur",
        },
        "features": [],
        "fixes": [
            {
                "fr": "Le widget répartition OS comptait les vulnérabilités au lieu des serveurs uniques",
                "en": "OS distribution widget counted vulnerabilities instead of unique hosts",
                "es": "El widget de distribución de SO contaba vulnerabilidades en vez de servidores únicos",
                "de": "Das Betriebssystemverteilungs-Widget zählte Schwachstellen statt eindeutiger Hosts",
            },
        ],
        "improvements": [],
    },
    {
        "version": "1.1.13.0",
        "date": "2026-03-15",
        "title": {
            "fr": "Mise à jour web + Répartition OS + Tendances",
            "en": "Web Upgrade + OS Distribution + Trends",
            "es": "Actualización web + Distribución SO + Tendencias",
            "de": "Web-Upgrade + Betriebssystemverteilung + Trends",
        },
        "features": [
            {
                "fr": "Système de mise à jour via l'interface web entièrement fonctionnel",
                "en": "Fully functional web-based upgrade system",
                "es": "Sistema de actualización web completamente funcional",
                "de": "Voll funktionsfähiges webbasiertes Upgrade-System",
            },
            {
                "fr": "Widget répartition des OS (donut concentrique classe + type)",
                "en": "OS distribution widget (concentric donut class + type)",
                "es": "Widget de distribución de SO (donut concéntrico clase + tipo)",
                "de": "Betriebssystemverteilungs-Widget (konzentrischer Donut Klasse + Typ)",
            },
            {
                "fr": "Barre de progression sur la page Tendances",
                "en": "Progress bar on Trends page",
                "es": "Barra de progreso en la página de Tendencias",
                "de": "Fortschrittsbalken auf der Trends-Seite",
            },
        ],
        "fixes": [
            {
                "fr": "Bandeau maintenance : heure exacte, countdown lisible, état 'en cours'",
                "en": "Maintenance banner: exact time, readable countdown, 'in progress' state",
                "es": "Banner de mantenimiento: hora exacta, cuenta regresiva legible, estado 'en curso'",
                "de": "Wartungsbanner: genaue Uhrzeit, lesbarer Countdown, Status 'in Bearbeitung'",
            },
        ],
        "improvements": [
            {
                "fr": "Version masquée sur la page de connexion (sécurité)",
                "en": "Version hidden on login page (security)",
                "es": "Versión oculta en la página de inicio de sesión (seguridad)",
                "de": "Version auf der Anmeldeseite ausgeblendet (Sicherheit)",
            },
        ],
    },
    {
        "version": "1.1.12.3",
        "date": "2026-03-14",
        "title": {
            "fr": "Répartition des OS + améliorations upgrade",
            "en": "OS Distribution + upgrade improvements",
            "es": "Distribución de SO + mejoras de actualización",
            "de": "Betriebssystemverteilung + Upgrade-Verbesserungen",
        },
        "features": [
            {
                "fr": "Donut concentrique répartition des OS sur la Vue d'ensemble (classe + type)",
                "en": "Concentric OS distribution donut on Overview (class + type)",
                "es": "Donut concéntrico de distribución de SO en Vista general (clase + tipo)",
                "de": "Konzentrischer Betriebssystem-Donut auf der Übersicht (Klasse + Typ)",
            },
        ],
        "fixes": [],
        "improvements": [
            {
                "fr": "Bandeau maintenance avec heure exacte et countdown lisible (1h28, 28 min, < 1 min)",
                "en": "Maintenance banner with exact time and readable countdown (1h28, 28 min, < 1 min)",
                "es": "Banner de mantenimiento con hora exacta y cuenta regresiva legible",
                "de": "Wartungsbanner mit genauer Uhrzeit und lesbarem Countdown",
            },
            {
                "fr": "Diagnostic d'échec upgrade visible dans un bandeau rouge admin",
                "en": "Upgrade failure diagnostic shown in red admin banner",
                "es": "Diagnóstico de error de actualización en banner rojo de administrador",
                "de": "Upgrade-Fehlerdiagnose im roten Admin-Banner angezeigt",
            },
        ],
    },
    {
        "version": "1.1.12.2",
        "date": "2026-03-14",
        "title": {
            "fr": "Barre de progression Tendances",
            "en": "Trends Progress Bar",
            "es": "Barra de progreso de Tendencias",
            "de": "Trends-Fortschrittsbalken",
        },
        "features": [],
        "fixes": [],
        "improvements": [
            {
                "fr": "Barre de progression avec messages contextuels sur la page Tendances (remplace le spinner générique)",
                "en": "Progress bar with contextual messages on the Trends page (replaces generic spinner)",
                "es": "Barra de progreso con mensajes contextuales en la página de Tendencias (reemplaza el spinner genérico)",
                "de": "Fortschrittsbalken mit kontextbezogenen Meldungen auf der Trends-Seite (ersetzt den generischen Spinner)",
            },
        ],
    },
    {
        "version": "1.1.12.1",
        "date": "2026-03-14",
        "title": {
            "fr": "Correctif bandeau maintenance",
            "en": "Maintenance Banner Fix",
            "es": "Corrección del banner de mantenimiento",
            "de": "Wartungsbanner-Korrektur",
        },
        "features": [],
        "fixes": [
            {
                "fr": "Le bandeau maintenance affichait « 0 minutes » au lieu du temps restant réel (décalage fuseau horaire UTC)",
                "en": "Maintenance banner showed \"0 minutes\" instead of actual remaining time (UTC timezone offset issue)",
                "es": "El banner de mantenimiento mostraba \"0 minutos\" en lugar del tiempo restante real (problema de zona horaria UTC)",
                "de": "Wartungsbanner zeigte „0 Minuten" statt der tatsächlichen Restzeit an (UTC-Zeitzonenversatz)",
            },
        ],
        "improvements": [],
    },
    {
        "version": "1.1.12.0",
        "date": "2026-03-14",
        "title": {
            "fr": "Expansion des tendances — 5 nouveaux widgets",
            "en": "Trends Expansion — 5 New Widgets",
            "es": "Expansión de tendencias — 5 nuevos widgets",
            "de": "Trends-Erweiterung — 5 neue Widgets",
        },
        "features": [
            {
                "fr": "Vulnérabilités critiques — courbe dédiée sévérité 4 et 5",
                "en": "Critical vulnerabilities — dedicated severity 4 and 5 trend line",
                "es": "Vulnerabilidades críticas — línea dedicada para severidad 4 y 5",
                "de": "Kritische Schwachstellen — dedizierte Trendlinie für Schweregrad 4 und 5",
            },
            {
                "fr": "Taux de remédiation — pourcentage de vulnérabilités corrigées par période",
                "en": "Remediation rate — percentage of fixed vulnerabilities per period",
                "es": "Tasa de remediación — porcentaje de vulnerabilidades corregidas por período",
                "de": "Behebungsrate — Prozentsatz behobener Schwachstellen pro Zeitraum",
            },
            {
                "fr": "Temps moyen de remédiation — durée moyenne de correction en jours",
                "en": "Average remediation time — average fix duration in days",
                "es": "Tiempo medio de remediación — duración media de corrección en días",
                "de": "Durchschnittliche Behebungszeit — mittlere Korrekturdauer in Tagen",
            },
            {
                "fr": "Âge moyen des vulnérabilités ouvertes — ancienneté moyenne en jours",
                "en": "Average open vulnerability age — average age in days",
                "es": "Edad media de vulnerabilidades abiertas — antigüedad media en días",
                "de": "Durchschnittsalter offener Schwachstellen — mittleres Alter in Tagen",
            },
            {
                "fr": "Répartition par catégorie — courbes multiples par catégorisation",
                "en": "Category breakdown — multiple lines per categorization layer",
                "es": "Distribución por categoría — líneas múltiples por categorización",
                "de": "Verteilung nach Kategorie — mehrere Linien pro Kategorisierung",
            },
        ],
        "fixes": [],
        "improvements": [
            {
                "fr": "Index de performance pour les requêtes de remédiation",
                "en": "Performance index for remediation queries",
                "es": "Índice de rendimiento para consultas de remediación",
                "de": "Leistungsindex für Behebungsabfragen",
            },
            {
                "fr": "Export PDF inclut tous les graphiques de tendances",
                "en": "PDF export includes all trend charts",
                "es": "Exportación PDF incluye todos los gráficos de tendencias",
                "de": "PDF-Export enthält alle Trend-Diagramme",
            },
        ],
    },
    {
        "version": "1.1.11.0",
        "date": "2026-03-13",
        "title": {
            "fr": "Propositions de règles de catégorisation",
            "en": "Rule Proposals",
            "es": "Propuestas de reglas de categorización",
            "de": "Regelvorschläge",
        },
        "features": [
            {
                "fr": "Les utilisateurs peuvent proposer des règles de catégorisation",
                "en": "Users can propose categorization rules",
                "es": "Los usuarios pueden proponer reglas de categorización",
                "de": "Benutzer können Kategorisierungsregeln vorschlagen",
            },
            {
                "fr": "Revue des propositions par les admins (approuver, modifier, rejeter)",
                "en": "Admin proposal review (approve, modify, reject)",
                "es": "Revisión de propuestas por admins (aprobar, modificar, rechazar)",
                "de": "Admin-Prüfung von Vorschlägen (genehmigen, ändern, ablehnen)",
            },
            {
                "fr": "Page 'Mes propositions' pour suivre ses soumissions",
                "en": "'My Proposals' page to track submissions",
                "es": "Página 'Mis propuestas' para seguir las solicitudes",
                "de": "Seite 'Meine Vorschläge' zur Nachverfolgung",
            },
            {
                "fr": "Accès à la page QIDs non catégorisés pour tous les utilisateurs",
                "en": "Uncategorized QIDs page accessible to all users",
                "es": "Página de QIDs sin categorizar accesible para todos",
                "de": "Seite nicht kategorisierter QIDs für alle Benutzer zugänglich",
            },
            {
                "fr": "Suppression de la priorité numérique — les règles les plus récentes sont prioritaires",
                "en": "Numeric priority removed — newest rules take precedence",
                "es": "Prioridad numérica eliminada — las reglas más recientes prevalecen",
                "de": "Numerische Priorität entfernt — neuere Regeln haben Vorrang",
            },
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.1.10.0",
        "date": "2026-03-13",
        "title": {
            "fr": "Rétention des données + purge automatique",
            "en": "Data retention + automatic purge",
            "es": "Retención de datos + purga automática",
            "de": "Datenaufbewahrung + automatische Bereinigung",
        },
        "features": [
            {
                "fr": "Purge automatique des anciens rapports au démarrage (configurable, défaut : 24 mois)",
                "en": "Automatic purge of old reports at startup (configurable, default: 24 months)",
                "es": "Purga automática de informes antiguos al iniciar (configurable, defecto: 24 meses)",
                "de": "Automatische Bereinigung alter Berichte beim Start (konfigurierbar, Standard: 24 Monate)",
            },
            {
                "fr": "Bouton de purge manuelle sur la page Monitoring (admin)",
                "en": "Manual purge button on the Monitoring page (admin)",
                "es": "Botón de purga manual en la página de Monitoring (admin)",
                "de": "Manueller Bereinigungs-Button auf der Monitoring-Seite (Admin)",
            },
            {
                "fr": "Durée de rétention configurable dans Admin > Paramètres (6 à 120 mois)",
                "en": "Configurable retention period in Admin > Settings (6 to 120 months)",
                "es": "Período de retención configurable en Admin > Parámetros (6 a 120 meses)",
                "de": "Konfigurierbare Aufbewahrungsdauer in Admin > Einstellungen (6 bis 120 Monate)",
            },
        ],
        "fixes": [],
        "improvements": [
            {
                "fr": "Page Paramètres entièrement traduite (i18n)",
                "en": "Settings page fully translated (i18n)",
                "es": "Página de parámetros completamente traducida (i18n)",
                "de": "Einstellungsseite vollständig übersetzt (i18n)",
            },
        ],
    },
    {
        "version": "1.1.9.1",
        "date": "2026-03-12",
        "title": {
            "fr": "Performance tendances",
            "en": "Trends performance",
            "es": "Rendimiento tendencias",
            "de": "Trends-Performance",
        },
        "features": [],
        "fixes": [],
        "improvements": [
            {
                "fr": "Index couvrant pour les requêtes de tendances filtrées — chargement beaucoup plus rapide sur les grosses bases",
                "en": "Covering index for filtered trend queries — much faster loading on large databases",
                "es": "Índice compuesto para consultas de tendencias filtradas — carga más rápida",
                "de": "Abdeckender Index für gefilterte Trend-Abfragen — deutlich schnelleres Laden",
            },
        ],
    },
    {
        "version": "1.1.9.0",
        "date": "2026-03-11",
        "title": {
            "fr": "Tendances optimisées + widget combo",
            "en": "Optimized trends + combo widget",
            "es": "Tendencias optimizadas + widget combinado",
            "de": "Optimierte Trends + Kombi-Widget",
        },
        "features": [
            {
                "fr": "Tableau pré-agrégé trend_snapshots : chargement instantané des tendances",
                "en": "Pre-aggregated trend_snapshots table: instant trend loading",
                "es": "Tabla pre-agregada trend_snapshots: carga instantánea",
                "de": "Voraggregierte trend_snapshots-Tabelle: sofortiges Laden",
            },
            {
                "fr": "Widget combo : courbe moyenne vulns/serveur + histogramme nombre de serveurs",
                "en": "Combo widget: avg vulns/host line + host count bars",
                "es": "Widget combinado: línea prom. vulns/servidor + barras cantidad servidores",
                "de": "Kombi-Widget: Durchschn. Schwachstellen/Host + Balken Serveranzahl",
            },
            {
                "fr": "Nouveau widget Nombre de serveurs",
                "en": "New Host Count widget",
                "es": "Nuevo widget Cantidad de servidores",
                "de": "Neues Widget Anzahl Server",
            },
            {
                "fr": "Endpoint batch : une seule requête pour toutes les métriques",
                "en": "Batch endpoint: single request for all metrics",
                "es": "Endpoint batch: una sola petición para todas las métricas",
                "de": "Batch-Endpunkt: eine Anfrage für alle Metriken",
            },
            {
                "fr": "Taille de la base de données sur la page Monitoring",
                "en": "Database size on the Monitoring page",
                "es": "Tamaño de la base de datos en la página Monitoring",
                "de": "Datenbankgröße auf der Monitoring-Seite",
            },
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.1.8.3",
        "date": "2026-03-11",
        "title": {
            "fr": "Correctif Vue d'ensemble",
            "en": "Overview fix",
            "es": "Corrección Vista general",
            "de": "Übersicht-Korrektur",
        },
        "features": [],
        "fixes": [
            {
                "fr": "Vue d'ensemble : corrigé un crash (NameError) introduit lors du refactoring",
                "en": "Overview: fixed a crash (NameError) introduced during refactoring",
                "es": "Vista general: corregido un crash (NameError) introducido durante la refactorización",
                "de": "Übersicht: Absturz (NameError) behoben, der beim Refactoring eingeführt wurde",
            },
        ],
        "improvements": [],
    },
    {
        "version": "1.1.8.2",
        "date": "2026-03-11",
        "title": {
            "fr": "Correctifs vue matérialisée + upgrade robuste",
            "en": "Materialized view fix + robust upgrade",
            "es": "Corrección vista materializada + actualización robusta",
            "de": "Materialized-View-Fix + robustes Upgrade",
        },
        "features": [],
        "fixes": [
            {
                "fr": "Vue matérialisée auto-réparée au démarrage si non peuplée",
                "en": "Materialized view auto-repaired on startup if not populated",
                "es": "Vista materializada auto-reparada al inicio si no está poblada",
                "de": "Materialisierte Ansicht wird beim Start automatisch repariert",
            },
            {
                "fr": "Upgrade : refresh de la vue matérialisée après les migrations",
                "en": "Upgrade: refresh materialized view after migrations",
                "es": "Actualización: refresh de la vista materializada después de las migraciones",
                "de": "Upgrade: Aktualisierung der materialisierten Ansicht nach Migrationen",
            },
        ],
        "improvements": [
            {
                "fr": "Timeout de restauration DB étendu à 15 minutes",
                "en": "DB restore timeout extended to 15 minutes",
                "es": "Timeout de restauración de BD extendido a 15 minutos",
                "de": "DB-Wiederherstellungs-Timeout auf 15 Minuten verlängert",
            },
        ],
    },
    {
        "version": "1.1.8.1",
        "date": "2026-03-11",
        "title": {
            "fr": "Correctifs critiques POC",
            "en": "Critical POC fixes",
            "es": "Correcciones críticas POC",
            "de": "Kritische POC-Korrekturen",
        },
        "features": [],
        "fixes": [
            {
                "fr": "Tendances : corrigé le filtre fraîcheur qui ne laissait qu'un seul point de données",
                "en": "Trends: fixed freshness filter that left only one data point",
                "es": "Tendencias: corregido el filtro de frescura que dejaba solo un punto de datos",
                "de": "Trends: Frische-Filter korrigiert, der nur einen Datenpunkt übrig ließ",
            },
            {
                "fr": "Intervalles de fraîcheur : retour à la syntaxe SQL compatible avec toutes les configurations",
                "en": "Freshness intervals: reverted to SQL syntax compatible with all configurations",
                "es": "Intervalos de frescura: revertido a sintaxis SQL compatible con todas las configuraciones",
                "de": "Frische-Intervalle: Zurück zur SQL-Syntax, die mit allen Konfigurationen kompatibel ist",
            },
            {
                "fr": "Mise à jour : le fichier ._pth est maintenant re-patché après remplacement de Python",
                "en": "Upgrade: the ._pth file is now re-patched after Python directory replacement",
                "es": "Actualización: el archivo ._pth se repara después del reemplazo del directorio Python",
                "de": "Upgrade: Die ._pth-Datei wird nach dem Ersetzen des Python-Verzeichnisses neu gepatcht",
            },
        ],
        "improvements": [
            {
                "fr": "Journalisation améliorée sur les endpoints Vue d'ensemble, Recherche et Tendances",
                "en": "Improved logging on Overview, Search, and Trends endpoints",
                "es": "Registro mejorado en los endpoints de Vista general, Búsqueda y Tendencias",
                "de": "Verbesserte Protokollierung bei Übersicht, Suche und Trends-Endpunkten",
            },
            {
                "fr": "Vérification de santé étendue lors de la mise à jour (pour les grandes bases de données)",
                "en": "Extended health check during upgrade (for large databases)",
                "es": "Verificación de salud extendida durante la actualización (para bases de datos grandes)",
                "de": "Erweiterte Gesundheitsprüfung beim Upgrade (für große Datenbanken)",
            },
        ],
    },
    {
        "version": "1.1.8.0",
        "date": "2026-03-10",
        "title": {
            "fr": "Internationalisation FR/EN/ES/DE",
            "en": "Internationalization FR/EN/ES/DE",
            "es": "Internacionalización FR/EN/ES/DE",
            "de": "Internationalisierung FR/EN/ES/DE",
        },
        "features": [
            {
                "fr": "Interface disponible en 4 langues : français, anglais, espagnol, allemand",
                "en": "Interface available in 4 languages: French, English, Spanish, German",
                "es": "Interfaz disponible en 4 idiomas: francés, inglés, español, alemán",
                "de": "Oberfläche in 4 Sprachen verfügbar: Französisch, Englisch, Spanisch, Deutsch",
            },
            {
                "fr": "Détection automatique de la langue du navigateur",
                "en": "Automatic browser language detection",
                "es": "Detección automática del idioma del navegador",
                "de": "Automatische Erkennung der Browsersprache",
            },
            {
                "fr": "Sélecteur de langue dans la page Mon Profil",
                "en": "Language selector in the My Profile page",
                "es": "Selector de idioma en la página Mi Perfil",
                "de": "Sprachauswahl auf der Mein-Profil-Seite",
            },
        ],
        "fixes": [
            {
                "fr": "Première connexion : le popup de nouveautés ne s'affiche plus inutilement",
                "en": "First login: the release notes popup no longer shows unnecessarily",
                "es": "Primer inicio de sesión: el popup de novedades ya no se muestra innecesariamente",
                "de": "Erstanmeldung: Das Release-Notes-Popup wird nicht mehr unnötig angezeigt",
            },
        ],
        "improvements": [
            {
                "fr": "Messages d'erreur backend standardisés (codes au lieu de texte français)",
                "en": "Standardized backend error messages (codes instead of French text)",
                "es": "Mensajes de error del backend estandarizados (códigos en lugar de texto en francés)",
                "de": "Standardisierte Backend-Fehlermeldungen (Codes statt französischem Text)",
            },
        ],
    },
    {
        "version": "1.1.7.0",
        "date": "2026-03-10",
        "title": "Popup multi-versions & repo prive",
        "features": [
            "Le popup de nouveautes affiche desormais toutes les mises a jour depuis votre derniere connexion",
        ],
        "fixes": [],
        "improvements": [
            "Suppression du lien vers le changelog GitHub (depot devenu prive)",
        ],
    },
    {
        "version": "1.1.6.0",
        "date": "2026-03-10",
        "title": "Tendances v2 -- filtres globaux & moyenne vulns/serveur",
        "features": [
            "Page Tendances refondue avec les memes filtres globaux que la Vue d'ensemble",
            "Nouveau graphique : evolution de la moyenne de vulnerabilites par serveur",
            "Raccourcis temporels (3 mois, 6 mois, 1 an) avec selection personnalisee",
            "Granularite configurable (jour, semaine, mois) -- defaut entreprise parametrable",
            "Widgets reordonnables et masquables avec persistance par utilisateur",
        ],
        "fixes": [
            "Correction de la borne date_to (off-by-one sur les requetes tendances)",
        ],
        "improvements": [
            "Formatage des valeurs decimales a 1 chiffre apres la virgule sur les graphiques",
        ],
    },
    {
        "version": "1.1.5.0",
        "date": "2026-03-03",
        "title": "Nom/prenom utilisateurs & securite",
        "features": [
            "Nom et prenom des utilisateurs (saisie manuelle ou recuperation automatique depuis Active Directory)",
            "Affichage du nom complet dans le header de l'application",
        ],
        "fixes": [
            "Correction d'une faille path traversal sur l'upload CSV",
            "Restriction de l'upload CSV aux administrateurs uniquement",
        ],
        "improvements": [],
    },
    {
        "version": "1.1.4.1",
        "date": "2026-03-03",
        "title": "Securite -- validation serveur de l'identite",
        "features": [],
        "fixes": [
            "L'identite utilisateur est desormais validee exclusivement cote serveur (anti-injection localStorage)",
            "Les privileges admin sont reverifies en base a chaque requete",
        ],
        "improvements": [
            "Cle de signature JWT dynamique (generee par l'installeur en production)",
        ],
    },
    {
        "version": "1.1.4.0",
        "date": "2026-03-02",
        "title": "Mode sombre / clair",
        "features": [
            "Toggle mode sombre / clair dans le header",
            "Tous les composants (Ant Design, AG Grid, graphiques) s'adaptent au theme choisi",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.1.3.0",
        "date": "2026-03-02",
        "title": "Filtres globaux sur fiche serveur",
        "features": [
            "La fiche serveur respecte desormais les filtres globaux (severites, types, fraicheur)",
            "Toggle Vue filtree / Tout afficher sur la fiche serveur",
            "Mode d'authentification par defaut configurable (Local ou Active Directory)",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.1.2.0",
        "date": "2026-03-02",
        "title": "Creation de regles depuis les fiches QID",
        "features": [
            "Bouton 'Creer une regle' sur les fiches vulnerabilite avec modal pre-rempli",
            "Compteur dynamique de QIDs correspondants lors de la creation de regles",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.1.1.0",
        "date": "2026-03-02",
        "title": "Regles entreprise enrichies",
        "features": [
            "Regles entreprise : filtre par classe d'OS (Windows, Linux/Unix) par defaut",
            "Regles entreprise : fraicheur par defaut configurable",
        ],
        "fixes": [
            "Correction de la suppression d'utilisateur ayant des audit logs ou des presets",
        ],
        "improvements": [],
    },
    {
        "version": "1.1.0.0",
        "date": "2026-03-01",
        "title": "Authentification Active Directory",
        "features": [
            "Connexion via LDAP / LDAPS avec direct bind",
            "Auto-provisionnement des comptes AD a la premiere connexion",
            "Mapping groupes AD vers profils (admin, user, monitoring)",
            "Page d'administration LDAP avec test de connexion",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.0.7.2",
        "date": "2026-03-01",
        "title": "Corrections login & flash interface",
        "features": [],
        "fixes": [
            "Correction du crash 500 a la connexion (compatibilite asyncpg)",
            "Correction du flash d'interface authentifiee a la reouverture du navigateur",
        ],
        "improvements": [
            "Page de login plus compacte et mieux adaptee au mobile",
        ],
    },
    {
        "version": "1.0.7.1",
        "date": "2026-02-28",
        "title": "Securite des sessions",
        "features": [
            "Timeout d'inactivite configurable avec avertissement avant expiration",
            "Verrouillage de compte apres 5 tentatives echouees (15 min)",
            "Deverrouillage admin dans la gestion des utilisateurs",
            "Rotation des refresh tokens avec detection de reutilisation",
            "Expiration de session a la fermeture du navigateur",
            "Synchronisation de deconnexion entre onglets",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.0.7.0",
        "date": "2026-02-28",
        "title": "Harmonisation des fiches QID",
        "features": [
            "Les fiches QID globale et serveur ont desormais la meme disposition",
            "Bandeau d'identification colore : orange (globale) / bleu (serveur)",
            "Tableau des serveurs affectes sur les deux fiches",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.0.6.0",
        "date": "2026-02-27",
        "title": "Orphelines v2 & categorisation unitaire",
        "features": [
            "Creation de regles de categorisation depuis la page orphelines",
            "Categorisation unitaire sur la fiche vulnerabilite (admin)",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.0.5.0",
        "date": "2026-02-27",
        "title": "Bandeau d'annonce & progression",
        "features": [
            "Bandeau d'annonce configurable par l'admin (message, couleur, visibilite)",
            "Bandeau de progression automatique pendant les imports et reclassifications",
            "Page de categorisation des vulnerabilites orphelines",
        ],
        "fixes": [
            "Correction du dashboard apres suppression de rapport",
        ],
        "improvements": [
            "Import CSV asynchrone (retour immediat)",
        ],
    },
    {
        "version": "1.0.4.0",
        "date": "2026-02-27",
        "title": "Triple donut & liste des serveurs",
        "features": [
            "Widget repartitions : 3 donuts (Criticites, Classe d'OS, Categorisation)",
            "Drill-down sur les donuts (clic pour filtrer)",
            "Page Liste des serveurs avec tableau AG Grid",
        ],
        "fixes": [],
        "improvements": [
            "Layout dashboard ameliore (flexbox, widgets auto-dimensionnes)",
        ],
    },
    {
        "version": "1.0.3.0",
        "date": "2026-02-26",
        "title": "Export PDF & filtres per-user",
        "features": [
            "Export PDF par page (100% client-side, compatible offline)",
            "Filtres par utilisateur (chaque user conserve ses propres filtres)",
            "Bouton Regles entreprise pour reappliquer le preset admin",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.0.2.0",
        "date": "2026-02-25",
        "title": "Drill-down interactif & profil monitoring",
        "features": [
            "Drill-down interactif sur tous les graphiques (clic pour filtrer)",
            "Restriction du profil monitoring a la page Monitoring uniquement",
            "Fraicheur integree dans les Regles entreprise",
        ],
        "fixes": [],
        "improvements": [],
    },
    {
        "version": "1.0.1.0",
        "date": "2026-02-24",
        "title": "Filtre fraicheur & file watcher",
        "features": [
            "Filtre fraicheur pour distinguer les vulns actives, obsoletes ou toutes",
            "File watcher : surveillance automatique de repertoires pour auto-import",
            "Popup de nouveautes apres mise a jour",
        ],
        "fixes": [],
        "improvements": [
            "Header sticky (visible au scroll)",
            "Version affichee dans le footer",
        ],
    },
]
