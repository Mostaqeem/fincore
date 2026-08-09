# FINcore

### Enterprise Data Governance Platform

Dynamic schema importing · Multi-stage approval workflows · Fine-grained RBAC

A full-stack platform that turns raw CSV/Excel files into governed, PostgreSQL-backed
datasets. Files are uploaded, automatically scanned for schema and column types, and
turned into real database tables that teams can preview, correct, and route through a
multi-stage review-and-approval workflow — all behind a role-based access control model
scoped to departments and modules.

Instead of people hand-editing spreadsheets with no audit trail and no access control,
FINcore gives every action a place in a formal pipeline: **upload → auto-schema →
asynchronous processing → collaborative editing → review → approve → govern.**

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Architecture & Workflow](#architecture--workflow)
- [Access Control Model](#access-control-model)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Screenshots](#screenshots)
- [Security & Production Hardening](#security--production-hardening)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

Most organizations still govern sensitive data through loose spreadsheets: no schema
contract, no versioning, no approval trail, and no way to answer "who changed this, and
who allowed it?"

**FINcore** solves that with a full-stack **data governance platform**:

- **Schema inference** — drop in a `.csv` or Excel file and the system reads the data,
  infers the appropriate PostgreSQL types (`BIGINT`, `NUMERIC`, `BOOLEAN`, `TIMESTAMP`,
  `VARCHAR`, `TEXT`) from an intelligent sampled analysis, sanitizes and de-duplicates
  column names, and physically builds a typed table.
- **Async, non-blocking processing** — large files never block the HTTP request. Uploads
  are dispatched to a Celery worker over Redis and report live progress back to the UI.
- **A governed edit surface** — imported data opens in a paginated grid where users can
  edit cells (with type-corrected casting), add/delete rows, and rename columns — all
  restricted to editable states (`draft` / `rejected`).
- **A formal approval pipeline** — a table flows `draft → submitted → in review →
  reviewed → confirmed` (or `rejected`), and **no user can review or approve their own
  work** — a separation-of-duties guarantee that mirrors real audit requirements.
- **Module-scoped RBAC** — employees belong to departments, hold roles with explicit
  capabilities (`can_view`, `can_create`, `can_edit`, `can_delete`, `can_review`,
  `can_approve`), and those capabilities are granted *per module* (finance / IT / risk).

The result is a system where trustworthy data is a process, not a promise.

---

## Key Features

### Authentication & Email Verification
- Custom email-based user model (`AUTH_USER_MODEL`) on top of Django's auth primitives.
- **JWT authentication** (access + refresh tokens) via `djangorestframework-simplejwt`.
- Registration with **4-digit OTP email verification** (10‑minute expiry), resend OTP,
  and a complete **forgot-password** flow with OTP validation.
- Branded transactional **HTML email templates** for welcome and password reset.

### Dynamic Schema Importer
- Accepts `.csv`, `.xls`, and `.xlsx` uploads.
- **Type inference** tuned for scale: 50K-row sampled inference and a cheap regex
  pre-filter before expensive `pandas` parsing keeps very long text columns (millions of
  rows) from paying a full `to_datetime`/`to_numeric` penalty. UUID columns are
  explicitly excluded from date detection.
- Column-name sanitization and de-duplication into safe PostgreSQL identifiers.
- **Chunked `COPY` bulk inserts** (100K rows per block) for fast, memory-bounded imports
  that pipeline progress updates per chunk.
- Manual table creation as an alternative to file uploads.

### Asynchronous Processing Pipeline
- Upload creates an `ImportJob` (`pending → processing → done/failed`) and hands off to a
  **Celery worker** backed by Redis.
- Real-time **progress reporting** (`current / total / phase`) surfacing as percentage
  progress in the UI via polling with exponential backoff.
- **ACID guarantees**: table creation, `COPY` insert, and metadata writes run inside a
  single `transaction.atomic()` block.
- **Reliability**: on any failure the partial staging table is dropped and the orphaned
  source file is deleted; a Celery Beat job cleans up jobs stuck in `processing` past a
  30-minute threshold.

### Data Editing Workbench
- Paginated data grid API (`LIMIT / OFFSET` + page metadata and column type info).
- In-grid **cell editing** with values cast to the column's PostgreSQL type before write.
- **Row add / update / delete** and **column rename** via `ALTER TABLE ... RENAME COLUMN`.
- Editing is state-aware: only `draft` or `rejected` datasets are mutable.

### Approval Workflow (Separation of Duties)
- Formal status lifecycle per dataset:
  `draft → submitted → in review → reviewed → confirmed` (or `rejected` for rework).
- Role-gated actions — submitting, starting review, review-approving, final approval, and
  rejection each require a distinct capability.
- Self-review protection: a table's creator cannot review, approve, or reject their own
  dataset.
- Full audit metadata trail per transition — who acted, when, and with what comment.

### Fine-Grained RBAC & Administration
- **Roles** is a configurable set of boolean capabilities (`can_view`, `can_create`,
  `can_edit`, `can_delete`, `can_review`, `can_approve`).
- **Role–Department** assignments scope a role to a department *and* the modules it
  applies to (finance, IT, risk, reports) via JSON module lists.
- Admin area for user management, department management, role assignment, audit activity
  logs, notifications, and employee document tracking.

---

## Tech Stack

| Tier | Technology | Purpose |
|---|---|---|
| Backend | Docker | Containerized services & reproducible runs |
| Database | PostgreSQL + `psycopg2` | Primary store, dynamic tables & typed columns |
| Queue | Celery + `celery-beat` + Redis | Async imports, progress reporting, scheduled cleanup |
| Data | pandas + openpyxl + xlrd | CSV/Excel parsing & type inference |
| API | Django REST Framework + SimpleJWT | JSON API, token auth, permission classes |
| Email | Django SMTP with transactional templates | OTP & password-reset emails |
| Frontend | React 19, React Router 7 | SPA with protected/admin routing |
| Build | Vite + React Compiler + Oxlint | Fast HMR builds, compiler-enabled, linted |
| HTTP | Axios | Interceptors, JWT header injection |

---

## Architecture & Workflow

```
User uploads .csv / .xls / .xlsx
        │
        ▼
  Django Upload API                       (ImportJob created: pending)
        │
        ▼
  Celery Worker (Redis broker)
        │
        ├─ Read file (pandas / openpyxl)
        ├─ Infer column types (sampled + pre-filtered)
        ├─ Sanitize & dedupe identifiers
        ├─ CREATE TABLE (dynamic SQL) + chunked COPY insert   ◄── transaction.atomic()
        ├─ Write Dataset + DatasetColumn metadata
        └─ ImportJob → done (linked to Dataset) | failed (error_message)
        │
        ▼
  React polls /jobs/<id>/  →  live progress (current/total/phase)
        │
        ▼
  Paginated Data Grid
        ├─ Edit cell        → type-cast PATCH
        ├─ Add row / delete row / rename column
        └─ Submit for review
        │
        ▼
  Approval pipeline (draft → submitted → in_review → reviewed → confirmed / rejected)
```

### Status Lifecycle

```
                  ┌──────────────  rejected  ◄────────┐  (sent back for rework)
                  ▼                                   │
  draft  ──►  submitted  ──►  in review  ──►  reviewed ──►  confirmed
                  (creator)     (reviewer)     (reviewer)      (approver)
```

Every transition records `who`, `when`, and `what comment` — and creators can *never*
approve their own data.

---

## Access-Control Model

Permissions are the product of **three entities**:

```text
EmployeeProfile ──► Role (capability flags) ──► RoleDepartment ──► Module (finance / it / risk / reports)
```

- **Role** — a named set of capabilities (`can_view`, `can_create`, `can_edit`,
  `can_delete`, `can_review`, `can_approve`).
- **RoleDepartment** — binds a Role to a Department and lists the `modules` the role
  grants within that department.
- **Module scoping** — the same user can be a *creator* in finance but only a *viewer*
  in IT.

Access is enforced through reusable DRF permission classes
(`HasSectionAccess`, `HasModuleAccess`, `IsAdminUser`, `IsEmployeeOrAdmin`) and a pure
function `user_has_capability(user, module, capability)` that drives all dataset and
employee endpoints. Staff bypass the checks; everyone else is evaluated against their
active role assignments.

---

## API Endpoints

### Authentication (`/api/auth/`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/register/` | Create account + send OTP |
| POST | `/login/` | Obtain access/refresh token |
| POST | `/refresh/` | Refresh access token |
| GET | `/me/` | Current user profile |
| POST | `/verify-otp/` | Verify registration OTP |
| POST | `/resend-otp/` | Resend a new OTP |
| POST | `/forgot-password/` | Request a password reset OTP |
| POST | `/verify-forgot-password-otp/` | Verify the reset OTP |
| POST | `/reset-password/` | Set a new password |

### Datasets (`/api/datasets/`) — all endpoints enforce module-scoped capabilities
| Method | Endpoint | Description |
|---|---|---|
| POST | `/upload/` | Create an async import job |
| GET | `/jobs/<uuid>/` | Poll import progress & result |
| POST | `/create-manual/` | Create a table from scratch |
| GET | `/` | List datasets for a section |
| GET | `/<pk>/` | Dataset details |
| GET | `/<pk>/data/` | Paginated rows + column types |
| PATCH | `/<pk>/data/<row>/` | Edit a single cell (typed cast) |
| POST | `/<pk>/rows/` | Add a row |
| PATCH | `/<pk>/rows/<row>/` | Update a row |
| DELETE | `/<pk>/rows/<row>/delete/` | Delete a row |
| PATCH | `/<pk>/columns/<col>/` | Rename a column |
| POST | `/<pk>/submit/` | Submit for review |
| POST | `/<pk>/start-review/` | Start review (reviewer) |
| POST | `/<pk>/review-approve/` | Review-approve (reviewer) |
| POST | `/<pk>/approve/` | Final approve (approver) |
| POST | `/<pk>/reject/` | Reject back for rework |

### Employees (`/api/employees/`)
Users, departments, profiles (with employee IDs), roles, role-department assignments,
activity logs, notifications, and documents — CRUD + `me/` + `me/notifications/`.

---

## Project Structure

```
.
├── backend/
│   ├── userconfig/          # project settings, URLs, WSGI, Celery app
│   ├── accounts/            # custom User, JWT, OTP verification, password reset
│   ├── datasets/            # schema inference, async import, grid edit, workflow
│   │   └── utils/schema_inference.py
│   ├── employees/           # departments, profiles, roles, permissions, logs
│   ├── manage.py
├── frontend/
│   ├── src/
│   │   ├── components/      # Sidebar, TopBar, DataEditor, DatasetManager, OTP modal
│   │   ├── pages/           # Signin, Signup, Dashboard, Finance, IT, Risk
│   │   ├── context/         # AuthContext (JWT persistence)
│   │   └── services/        # Axios API clients + interceptors
│   └── package.json
├── Dockerfile               # backend container (python:3.12-slim)
├── docker-compose.yml       # Redis broker/backend for Celery
├── requirements.txt
└── schema_importer_spec.md  # original spec for the importer
```

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node 18+
- PostgreSQL running locally (or a managed instance)
- Docker + Docker Compose (for Redis)

### 1. Configure the backend environment

Create a `backend/.env` from the settings expectations (`DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_HOST`, `DB_PORT`):

```bash
DB_NAME=governance
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DJANGO_SECRET_KEY=<generate-a-random-one>
```

> ⚠️ The repo ships with a dev `SECRET_KEY` and SMTP creds in `backend/userconfig/settings.py`.
> Replace them with environment variables before any production use — see
> [Security & Production Hardening](#security--production-hardening).

### 2. Start Redis

```bash
docker compose up -d
```

### 3. Backend — install, migrate, run

```bash
cd backend
pip install -r ../requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### 4. Celery worker + beat (separate terminals)

```bash
cd backend
celery -A userconfig worker --loglevel=info
```

```bash
cd backend
celery -A userconfig beat --loglevel=info
```

### 5. Frontend — install & run

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL (default `http://localhost:5173`), register an account, verify the OTP
that lands in your inbox, then upload a `.csv` to watch the pipeline run end-to-end.

### Try this first
1. Register + verify your email (OTP).
2. Upload a `.csv` with mixed-typed columns — watch live progress in the upload modal.
3. Open the grid and edit a cell, add/delete rows, rename a column.
4. Run the approval pipeline and confirm the creator/self-review guard blocks acting on
   their own table.

---

## Screenshots

*(Add screenshots here once compiled — e.g. `docs/screenshots/dashboard.png`,
`docs/screenshots/importer.png`, `docs/screenshots/workflow.png`)*

| Dashboard | Upload & progress | Grid editor |
|---|---|---|
| `docs/screenshots/dashboard.png` | `docs/screenshots/upload.png` | `docs/screenshots/editor.png` |

---

## Security & Production Hardening

The codebase is a working prototype with a few things to tighten before it ever ships to
production — implementing this list would make the deployment genuinely production-ready:

- **Secrets management** — `SECRET_KEY` and the SMTP app-password are hardcoded in
  `backend/userconfig/settings.py`. Move every secret to environment variables / a real
  secret manager and **rotate every leaked value** (the SMTP password has shipped in git
  history).
- **`DEBUG` = `False`** and a strict `ALLOWED_HOSTS` behind TLS in all deployed
  environments.
- **CORS lockdown** — replace `CORS_ALLOW_ALL_ORIGINS = True` with an explicit
  allow-list of application origins.
- **JWT lifetimes** — the demo uses a 1‑minute access token / 2‑hour refresh token;
  production should pick a balanced policy plus rotation/revocation of refresh tokens.
- **Logging & observability** — wire structured logging, request tracing, and threat
  alerts on Auth/Zendesk-style dashboards.
- **Test coverage expansion** — add unit tests for accounts and employees apps to match
  the existing dataset tests.

Frame kept intentionally honest: these are the known production-readiness gaps, and
showing the checklist in a portfolio is often as strong a signal as the code itself.

---

## Roadmap

Work-in-progress / future hardening:

- [x] Dynamic schema import (CSV / XLS / XLSX)
- [x] Async import with live progress & stale-job cleanup
- [x] Full approval workflow with separation of duties
- [x] Department + module-scoped RBAC
- [ ] Multi-file relational import & foreign-key inference
- [ ] Dataset versioning & diffing to visualize reviewers' changes
- [ ] Streaming/parallel imports and sharded writes for very large files
- [ ] Audit-trail dashboard (visual timeline per dataset)
- [ ] Notifications surfacing when it is your turn to review
- [ ] Document OCR / verification workflow polish

---

## License

MIT `LICENSE` pending — reach out for a copy.
```