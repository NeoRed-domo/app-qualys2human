<p align="center">
  <img src=".github/logo.png" alt="Qualys2Human" width="400">
</p>

<h1 align="center">Qualys2Human</h1>

<p align="center">
  Web application that ingests Qualys vulnerability CSV reports and produces interactive dashboards for security operations teams.
</p>

**Author:** NeoRed
**License:** Private
**Version:** 1.1.15.8

---

## Features

- **Interactive dashboard** — KPIs, severity distribution, Top 10 vulnerabilities/hosts, triple donut charts (severity, OS class, categorization) with click-through drill-down
- **OS distribution widget** — Concentric donut chart showing OS class (inner ring) and OS type (outer ring: Windows Server, Ubuntu, RHEL, etc.)
- **3-level drill-down** — Overview > Vulnerability/Host detail > Full detail (host + QID)
- **Customizable widgets** — Drag & drop reordering with per-user persistence
- **Copy widget to clipboard** — Hover any widget, chart, or KPI card to reveal a copy button. Captures as PNG and copies to clipboard for presentations
- **Remediation campaigns** — Track remediation of specific vulnerabilities (multi-QID). Dedicated dashboard with KPIs (real % / operational %), evolution chart, host lists (affected/remediated/exceptions). Dynamic scope: new hosts auto-included on next import. Retroactive start dates with background snapshot computation. Exception management with free-form comments. Pre-computed host status table for instant display
- **Dark / Light mode** — Theme toggle in header (sun/moon icon), persisted in localStorage, Ant Design darkAlgorithm + custom semantic tokens
- **CSV import** — Manual upload (admin only) or automatic via file watcher on local/UNC directories, with deduplication
- **Coherence checks** — Detects mismatches between report header and detail data
- **Trends** — 7 widgets (avg vulns/host, host count, critical count, remediation rate, avg remediation time, avg open age, category breakdown), pre-aggregated snapshots, progress bar with contextual messages, configurable granularity (day/week/month), batch API, covering indexes
- **Filters & presets** — Enterprise rules (admin) + per-user presets, 8 filter dimensions (severity, type, category, OS class, freshness, dates, report)
- **Categorization** — Layer-based classification with regex rules, inline assignment, orphan management, optimized single-pass reclassification (CTE + IS DISTINCT FROM), and rule proposals (user > admin review > approve/reject)
- **Export** — Client-side PDF (jsPDF) and server-side CSV/PDF on every page
- **Internationalization** — Full UI in 4 languages (French, English, Spanish, German) with automatic browser detection and user preference override
- **What's New popup** — Multi-version release notes popup after login, showing all changes since the user's last visit, multilingual, scrollable
- **Web-based upgrade system** — Upload signed packages (.zip + Ed25519 .sig), validate, schedule or launch immediately, automatic execution with backup/rollback, maintenance page during upgrade, progress tracking, failure diagnostics, admin recovery tools (reset state, rescan sources)
- **Administration** — User management (with first/last name, AD auto-provisioning), enterprise rules, layer rules, branding (custom logo, footer, announcement banner), LDAP/AD settings, upgrade management
- **Monitoring** — System health dashboard (CPU, RAM, disk, database size, DB pool, proactive alerts), data retention with automatic purge
- **Authentication** — JWT (access + refresh with rotation & reuse detection) + bcrypt + Active Directory (LDAP/LDAPS direct bind)
- **Session security** — Account lockout (5 attempts / 15 min), configurable inactivity timeout with warning, cross-tab logout sync, browser session expiration
- **Global search** — Search vulnerabilities or hosts by keyword across all fields
- **User profiles** — Profile page with language selector, first/last name display in header
- **Windows service** — Offline deployment via WinSW, interactive installer with backup/rollback, Q2H-Updater service for web upgrades
- **Performance optimizations** — Parallel dashboard queries (asyncio.gather), snapshot fast-path for trends, covering indexes for remediation metrics

## Architecture

```
+---------------------------------------------+
|           Browser (React 19)                |
|  Ant Design + Recharts + AG Grid            |
|  react-i18next (FR/EN/ES/DE)                |
+-------------------+-------------------------+
                    | HTTPS (JWT)
+-------------------v-------------------------+
|           FastAPI (Python 3.12)              |
|  REST API + File Watcher + Export            |
+-------------------+-------------------------+
                    | asyncpg
+-------------------v-------------------------+
|           PostgreSQL 18 (embedded)           |
|  Materialized view for deduplication         |
+---------------------------------------------+
```

### Tech stack

| Layer | Technologies |
|-------|-------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Polars, ReportLab, psutil, ldap3 |
| Frontend | React 19, TypeScript, Vite 7, Ant Design 6, Recharts 3, AG Grid 35, react-i18next |
| Database | PostgreSQL 18 (embedded/portable), asyncpg |
| Service | WinSW (Windows), Uvicorn, TLS (self-signed auto-generated) |
| Target | Windows Server 2016+, 100% offline / air-gapped |

## Quick start (development)

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 16+

### Backend

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn q2h.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The application will be available at `http://localhost:3000` (proxied to the backend on port 8000).

### Default credentials

- **Username:** `admin`
- **Password:** `Qualys2Human!`

> The default password must be changed on first login.

## Deployment (production)

See the [installation guide](installer/README-INSTALL.txt) for Windows Server deployment.

```bash
# Build (frontend + backend + embedded Python)
python scripts/build.py

# Package (offline zip)
python scripts/package.py

# Install
installer\install.bat
```

The resulting archive contains everything needed for a fully offline deployment: embedded Python, all dependencies, frontend build, installer scripts, and PostgreSQL.

## Project structure

```
qualys2human/
+-- backend/
|   +-- src/q2h/
|   |   +-- api/           # FastAPI endpoints (19 routers)
|   |   +-- auth/          # Authentication + JWT + LDAP service
|   |   +-- db/            # SQLAlchemy models + Alembic migrations
|   |   +-- ingestion/     # CSV parser + importer
|   |   +-- watcher/       # File watcher (auto-import)
|   |   +-- upgrade/       # Upgrade system (scheduler, chunked upload, version)
|   |   +-- services/       # Business logic (trend snapshots, campaign snapshots, retention)
|   |   +-- config.py      # YAML configuration
|   |   +-- main.py         # FastAPI application + version
|   |   +-- service.py      # Windows service entry point
|   |   +-- release_history.py  # Release notes history (28+ versions)
|   +-- alembic/            # 20 migrations
|   +-- pyproject.toml
+-- frontend/
|   +-- src/
|   |   +-- api/            # Axios client + JWT interceptors
|   |   +-- components/     # Reusable components (help, charts, export)
|   |   +-- contexts/       # AuthContext, FilterContext, ThemeContext
|   |   +-- layouts/        # MainLayout, AdminLayout
|   |   +-- locales/        # Translations (fr, en, es, de)
|   |   +-- pages/          # Application pages
|   |   +-- i18n.ts         # i18next configuration
|   +-- vite.config.ts
+-- updater/
|   +-- q2h_updater/       # Q2H-Updater service (backup, extract, migrate, restart)
+-- data/branding/          # Default logos + SVG template
+-- installer/              # Install/upgrade/uninstall scripts
+-- scripts/                # Build + package + reset-upgrade scripts
+-- docs/plans/             # Design documents
```

## Tests

```bash
cd backend
pytest -v
```

## API

The REST API is automatically documented via Swagger UI:
- Development: `http://localhost:8000/docs`
- Production: `https://<server>:8443/docs`

### Main endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/auth/login` | Authentication (local or AD) |
| POST | `/api/auth/refresh` | Token refresh with rotation |
| GET | `/api/auth/me` | Current user identity (server-validated) |
| GET | `/api/dashboard/overview` | KPIs and summary |
| GET | `/api/vulnerabilities` | Vulnerability list (deduplicated) |
| GET | `/api/vulnerabilities/{qid}` | Vulnerability detail |
| GET | `/api/hosts` | Host list |
| GET | `/api/hosts/{ip}/vulnerabilities/{qid}` | Full detail (host + QID) |
| POST | `/api/trends/query` | Trend query (multi-metric, multi-granularity) |
| GET | `/api/search` | Global search (vulnerabilities or hosts) |
| GET | `/api/export/csv` | CSV export |
| GET | `/api/export/pdf` | PDF export |
| POST | `/api/imports/upload` | Manual CSV import (admin) |
| GET | `/api/monitoring` | System health |
| GET/PUT | `/api/user/preferences` | User preferences (language, layout) |
| GET | `/api/version` | Version + release notes history |
| GET/PUT | `/api/settings/banner` | Announcement banner |
| GET/PUT | `/api/ldap/settings` | LDAP/AD configuration (admin) |
| POST | `/api/rules/proposals` | Propose a categorization rule (user) |
| GET | `/api/rules/proposals/pending/count` | Pending proposal count (admin badge) |
| POST | `/api/upgrade/upload` | Upload upgrade package (chunked, admin) |
| POST | `/api/upgrade/validate/{id}` | Validate package (signature + version) |
| POST | `/api/upgrade/schedule` | Schedule upgrade at specific time |
| POST | `/api/upgrade/launch-now` | Launch upgrade immediately |
| GET | `/api/upgrade/schedule` | Current schedule status (all users) |
| GET | `/api/upgrade/history` | Upgrade history (admin) |
| GET | `/api/campaigns` | List campaigns with KPIs |
| POST | `/api/campaigns` | Create campaign (admin) |
| GET | `/api/campaigns/{id}` | Campaign detail (KPIs, chart, hosts) |
| PUT | `/api/campaigns/{id}` | Update campaign (admin) |
| DELETE | `/api/campaigns/{id}` | Delete campaign (admin) |
| POST | `/api/campaigns/{id}/recompute` | Recompute snapshots + host statuses (admin) |
| POST | `/api/campaigns/{id}/exceptions` | Add host exception (admin) |
| DELETE | `/api/campaigns/{id}/exceptions/{eid}` | Remove exception (admin) |

## Web Upgrade System

The application includes a built-in upgrade system accessible from the admin UI:

1. **Upload** — Chunked upload of signed `.zip` package + `.sig` signature file
2. **Validate** — Ed25519 signature verification + version check (must be newer)
3. **Schedule** — Set a date/time or launch immediately
4. **Execute** — Background scheduler triggers the upgrade:
   - Backup database (pg_dump) + config files
   - Extract package (replace app/, python/, updater/)
   - Run Alembic migrations
   - Refresh materialized views
   - Restart Q2H service
5. **Rollback** — Automatic rollback on failure (restore from backup)

The `Qualys2Human-Updater` Windows service handles the actual upgrade while Q2H is stopped. A maintenance page is served during the process.

```bash
# Reset a stuck upgrade
python scripts/reset-upgrade.py --install-dir C:\Q2H
```

## Security

- Server-side identity validation on every request (JWT + DB check)
- Refresh token rotation with JTI tracking and reuse detection
- Account lockout after 5 failed attempts (15 min auto-unlock + admin override)
- Path traversal protection on file serving and CSV upload
- LDAP filter injection prevention (escape_filter_chars)
- ILIKE pattern escaping on all search inputs
- Security headers (X-Content-Type-Options, X-Frame-Options)
- UUID-based filenames for uploads (no user-controlled paths)
- Password minimum length enforcement (8 characters)
- Dynamic JWT secret in production (generated by installer)
- Ed25519 signed upgrade packages (integrity + authenticity)
- Version number hidden on login page (prevents version fingerprinting)
