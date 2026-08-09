# Dynamic Schema Importer — Project Spec

## Problem Statement

Build a full-stack web application (Django backend + React frontend) that lets a user
upload a CSV or Excel file, automatically infers a database schema from its columns,
stores the data in PostgreSQL, and lets the user preview and edit the imported data
(cell edits, row add/delete, column rename) in a paginated table before "promoting"
it into a final, permanent table. The data should be accessible to the frontend via a
REST API.

Key constraints:
- Single file per import (no multi-file relational/foreign-key inference for now).
- PostgreSQL is the target database.
- Large or slow uploads should not block the HTTP request — processing happens
  asynchronously via Celery.
- The original uploaded file is archived (not discarded) so processing can be re-run
  if needed.
- Editing happens on a "staging" table; a separate "promote" step finalizes it.

---

## Architecture Overview

```
React (upload .csv/.xls/.xlsx)
        │
        ▼
Django Upload API  →  saves original file  →  creates ImportJob (status: pending)
        │
        ▼
Celery Worker (async)
        │
        ├─ Read file (pandas)
        ├─ Infer column types (int/float/bool/timestamp/text)
        ├─ Sanitize column names, dedupe
        ├─ CREATE TABLE (dynamic, raw SQL) + COPY bulk insert (PostgreSQL)
        ├─ Create Dataset + DatasetColumn metadata rows
        └─ ImportJob status → done (linked to Dataset) or failed (error_message)
        │
        ▼
React polls /jobs/<id>/ until status = done → gets dataset_id
        │
        ▼
React Data Grid (paginated preview)
        │
        ├─ Double-click cell → edit → PATCH (cast value to column type first)
        ├─ Add row → POST
        ├─ Delete row → DELETE
        ├─ Rename column → PATCH (ALTER TABLE ... RENAME COLUMN)
        │
        ▼
"Promote" → Dataset.status = confirmed (staging table is already final)
```

### ACID Compliance & Reliability

- **Atomic Transactions**: All schema creation, data insertion, and metadata writes happen inside `transaction.atomic()`.
- **Progress Reporting**: Celery task reports progress via `AsyncResult.info` (current/total/phase).
- **Stale Job Cleanup**: Celery Beat runs `cleanup_stale_jobs` every 30 minutes to drop orphaned staging tables and mark failed jobs.
- **Defensive Cleanup**: On task failure, staging table is dropped and source file is deleted.
- **Pending Table Tracking**: `ImportJob.pending_table_name` stores the staging table name for cleanup on failure or timeout.

### Why staging vs. final tables
The staging table IS a real Postgres table (not a temp/JSON representation) — this
gives typed columns, easy pagination via `LIMIT`/`OFFSET`, and simple `UPDATE`/`DELETE`/
`ALTER TABLE` statements for edits. "Promotion" just flips a status flag; the table
was already named uniquely and stays in place.

---

## Data Models

### `Dataset`
| Field | Type | Notes |
|---|---|---|
| id | UUIDField | Primary key |
| name | CharField | Display name (usually original filename) |
| original_filename | CharField | |
| source_file | FileField | Archived upload, `uploads/%Y/%m/%d/` |
| table_name | CharField (unique) | Actual Postgres table name, e.g. `ds_finance_a1b2c3d4` |
| row_count | IntegerField | Kept in sync on add/delete |
| status | CharField | `staging` \| `confirmed` |
| section | CharField | `finance` \| `it` \| `risk` |
| uploaded_at | DateTimeField | auto_now_add |
| created_by | ForeignKey → User | Nullable, tracks uploader |

### `DatasetColumn`
| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| dataset | FK → Dataset | CASCADE delete |
| column_name | CharField | Sanitized, Postgres-safe identifier |
| data_type | CharField | e.g. `BIGINT`, `NUMERIC`, `TEXT`, `VARCHAR(n)`, `BOOLEAN`, `TIMESTAMP` |
| ordinal_position | IntegerField | Preserves original column order |

### `ImportJob`
| Field | Type | Notes |
|---|---|---|
| id | UUIDField | Primary key (UUID) |
| original_filename | CharField | |
| source_file | FileField | |
| status | CharField | `pending` \| `processing` \| `done` \| `failed` |
| error_message | TextField (nullable) | Populated on failure |
| dataset | FK → Dataset (nullable) | Set once processing completes |
| section | CharField | `finance` (default) |
| pending_table_name | CharField (nullable) | Staging table name for cleanup |
| celery_task_id | CharField (nullable) | Celery task ID for progress tracking |
| created_at | DateTimeField | auto_now_add |
| finished_at | DateTimeField (nullable) | Set on completion |

---

## Type Inference Rules (pandas → Postgres)

1. **All values numeric** (via `pd.to_numeric`, coercing errors):
   - All whole numbers → `BIGINT`
   - Any decimals → `NUMERIC`
2. **All values boolean-like** (`true/false/0/1/yes/no`, case-insensitive) → `BOOLEAN`
3. **All values parseable as dates** (via `pd.to_datetime`) → `TIMESTAMP`
   - **Conservative check**: Only returns `TIMESTAMP` if parsed years are between 1900-2100.
   - Falls through to `VARCHAR`/`TEXT` for ambiguous date-like values (e.g., numeric columns like `credit_score: 327`).
4. **Otherwise, text**:
   - Max string length ≤ 255 → `VARCHAR(max_length)`
   - Longer → `TEXT`

Column name sanitization: lowercase, non-alphanumeric → `_`, must start with a letter
or underscore, truncated to 63 chars (Postgres identifier limit), duplicates get a
numeric suffix (`name`, `name_1`, `name_2`, ...).

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/datasets/upload/` | Upload file → creates `ImportJob`, queues Celery task, returns `job_id` immediately (202) |
| GET | `/api/datasets/jobs/<job_id>/` | Poll job status; returns `dataset_id` when done, `error` when failed. Includes progress info from Celery. |
| GET | `/api/datasets/` | List datasets (filtered by `section` query param) |
| GET | `/api/datasets/<id>/` | Get dataset detail with column metadata |
| GET | `/api/datasets/<id>/data/?page=&page_size=` | Paginated rows + column metadata + total_count/total_pages |
| PATCH | `/api/datasets/<id>/data/<row_id>/` | Edit one cell: `{ "column": ..., "value": ... }`, casts value to column type |
| PATCH | `/api/datasets/<id>/data/<row_id>/` | Update entire row: body = `{ column_name: value, ... }` |
| POST | `/api/datasets/<id>/rows/` | Add a new row: body = `{ column_name: value, ... }` |
| DELETE | `/api/datasets/<id>/rows/<row_id>/` | Delete a row |
| PATCH | `/api/datasets/<id>/columns/<column_name>/` | Rename column: `{ "new_name": ... }`, does `ALTER TABLE ... RENAME COLUMN` |
| POST | `/api/datasets/<id>/promote/` | Finalize: `status → confirmed` |
| DELETE | `/api/datasets/<id>/` | Discard: `DROP TABLE`, delete `Dataset` row |

---

## Celery Configuration

- **Broker**: Redis at `redis://localhost:6379/0`
- **Result Backend**: Redis (`redis://localhost:6379/0`)
- **Beat Scheduler**: `django_celery_beat.schedulers:DatabaseScheduler` (database-backed)
- **Periodic Task**: `cleanup_stale_jobs` runs every 30 minutes to clean up stuck jobs

### Running the Workers

```bash
# Terminal 1: Django dev server
cd backend
python manage.py runserver

# Terminal 2: Celery Worker
cd backend
celery -A userconfig worker -l info

# Terminal 3: Celery Beat (for periodic cleanup)
cd backend
celery -A userconfig beat -l info
```

---

## Implementation Steps

### Step 0 — Environment setup
- Django + DRF + `psycopg2-binary` + `pandas` + `openpyxl` + `xlrd` + `django-cors-headers`
- Celery + Redis + `django-celery-results` + `django-celery-beat`
- React app (Vite) + `axios`
- Local Postgres database + Redis server (Docker)

### Step 1 — Django settings
- Add `rest_framework`, `corsheaders`, `datasets`, `django_celery_beat` to `INSTALLED_APPS`
- Configure `CORS_ALLOWED_ORIGINS` for the React dev server
- Configure `DATABASES` for Postgres
- Configure `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_BEAT_SCHEDULER`
- Configure `MEDIA_ROOT` / `MEDIA_URL` for archived file uploads
- Create `config/celery.py` app instance, wire into `config/__init__.py`

### Step 2 — Models
- Implement `Dataset`, `DatasetColumn`, `ImportJob` as specified above
- Run migrations: `makemigrations` / `migrate`

### Step 3 — Schema inference utility module
- `datasets/utils/schema_inference.py`:
  - `sanitize_identifier(name)` — safe Postgres identifier
  - `make_unique_names(names)` — dedupe collisions
  - `infer_pg_type(series)` — pandas Series → Postgres type string (with year-range check for timestamps)
  - `read_uploaded_file(file_obj)` — dispatch by extension (csv/xls/xlsx) to pandas
  - `build_schema(df)` — sanitize + infer full column schema
  - `create_table_and_insert(table_name, schema, df, task=None)` — raw SQL `CREATE TABLE` + PostgreSQL `COPY` bulk insert with progress reporting
  - `cast_value(value, pg_type)` — casts string input to proper Python type per column type

### Step 4 — Celery task (`datasets/tasks.py`)
- `process_import_job(job_id)`:
  - Load `ImportJob`, mark `processing`, store `celery_task_id`
  - Generate staging table name, store in `pending_table_name`
  - Open archived file, run `read_uploaded_file` → `build_schema` → `create_table_and_insert`
  - Create `Dataset` + `DatasetColumn` rows inside `transaction.atomic()`
  - Mark job `done` and link `dataset`, or `failed` with `error_message` on exception
  - On failure: drop staging table, delete source file
- `cleanup_stale_jobs()`:
  - Runs every 30 minutes via Celery Beat
  - Finds jobs stuck in `processing` for >30 minutes
  - Drops their `pending_table_name` tables
  - Deletes source files
  - Marks jobs as `failed` with timeout message

### Step 5 — Upload view
- Accept multipart file upload
- Validate extension (.csv, .xls, .xlsx)
- Create `ImportJob` with archived `source_file`
- Call `process_import_job.delay(job.id)`
- Return `{ job_id, status }` with HTTP 202 (does not block)

### Step 6 — Job status view
- `GET /jobs/<job_id>/` → returns current status, `dataset_id` if done, `error` if failed
- Includes progress info from Celery `AsyncResult` (`current`, `total`, `phase`)

### Step 7 — Data preview view
- Paginated `SELECT * FROM "<table_name>" ORDER BY id LIMIT/OFFSET`
- Also returns `total_count`, `total_pages`, and column metadata from `information_schema.columns`

### Step 8 — Cell edit view
- `PATCH` with `{ column, value }`
- Look up column's `data_type`, run `cast_value`
- Run parameterized `UPDATE ... SET "<column>" = %s WHERE id = %s`
- Return error (not exception) on cast failure

### Step 9 — Row add / delete views
- Add: parameterized `INSERT ... RETURNING id`, increment `Dataset.row_count`
- Delete: parameterized `DELETE ... WHERE id = %s`, decrement `Dataset.row_count`

### Step 10 — Column rename view
- Sanitize new name
- `ALTER TABLE "<table>" RENAME COLUMN "<old>" TO "<new>"`
- Update corresponding `DatasetColumn.column_name`

### Step 11 — Promote (finalize) view
- Update `Dataset.status = 'confirmed'`
- (Table was already permanent; just flip the status flag)

### Step 12 — Discard view
- `DROP TABLE IF EXISTS "<table_name>"`
- Delete the `Dataset` row (cascades to `DatasetColumn`)

### Step 13 — URLs
- Wire all views under `/api/datasets/...` as listed in the API table above
- Serve `MEDIA_URL` in dev via Django static helpers

### Step 14 — React: API client
- Thin `axios` wrapper module (`services/datasetApi.js`) with one function per endpoint

### Step 15 — React: Upload + polling component
- File input → `uploadFile()` → receive `job_id`
- Poll `getJobStatus(job_id)` with exponential backoff (1s→1.5s→… capped at 10s)
- Show progress bar when available, "large file" message after 15s

### Step 16 — React: Preview/edit data grid
- Paginated table (Next/Back buttons) fed by `getPage`
- Double-click cell → inline `<input>` → save on Enter, cancel on Escape, calls `updateCell`
- Buttons/UI for add row, delete row, rename column
- "Confirm / Promote" and "Discard" actions at the bottom

### Step 17 — Frontend pages
- `Finance.jsx`, `IT.jsx`, `RiskManagement.jsx` — section-specific upload pages
- All use the same dataset API client with section parameter

---

## End-to-end Verification Checklist

- [ ] Upload returns `job_id` immediately, does not block
- [ ] Celery worker log shows task running; status flips pending → processing → done
- [ ] Broken/corrupt file → job status `failed` with readable `error_message`
- [ ] Archived file exists on disk under `media/uploads/...`
- [ ] Mixed-type CSV (text, numbers, dates, weird column names, duplicate names) infers correctly
- [ ] Pagination Next/Back works across boundaries
- [ ] Cell edit: valid value persists; invalid value (e.g. text into numeric column) shows error
- [ ] Add row appears on next fetch; row_count increments
- [ ] Delete row removes it; row_count decrements
- [ ] Rename column updates both Postgres and `DatasetColumn` metadata
- [ ] Promote sets `status = confirmed`
- [ ] Discard drops the table and removes the `Dataset` record

---

## Deferred / Future Work

- Multi-file imports with foreign-key/relationship inference between tables
- True real-time multi-user collaborative editing (would need websockets)
- Docker Compose setup (Django + Postgres + Redis + Celery worker) — to be done later

---

## Developer Navigation Guide

### Project Structure

```
/home/mostaqeem/Desktop/User authentication and authorization project/
├── backend/
│   ├── datasets/                    # Main Django app for data import
│   │   ├── models.py                # Dataset, DatasetColumn, ImportJob models
│   │   ├── views.py                 # API views (upload, status, data CRUD)
│   │   ├── serializers.py           # DRF serializers
│   │   ├── tasks.py                 # Celery tasks (process_import_job, cleanup_stale_jobs)
│   │   ├── urls.py                  # URL routing for datasets app
│   │   └── utils/
│   │       └── schema_inference.py  # Schema inference, bulk insert, type casting
│   ├── userconfig/
│   │   ├── settings.py              # Django settings (Celery, DB, CORS)
│   │   ├── urls.py                  # Main URL config
│   │   └── celery.py                # Celery app instance
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Finance.jsx          # Finance section upload/preview UI
│   │   │   ├── IT.jsx              # IT section upload/preview UI
│   │   │   └── RiskManagement.jsx  # Risk section upload/preview UI
│   │   ├── services/
│   │   │   └── datasetApi.js       # API client for all dataset endpoints
│   │   └── components/
│   │       └── DataEditor.jsx      # Reusable data grid component
│   └── package.json
├── docker-compose.yml                # Redis container definition
├── .env                             # Environment variables (DB, secrets)
└── schema_importer_spec.md          # This specification
```

### How to Navigate the Codebase

#### Backend Flow

1. **Upload Request** → `datasets/views.py:UploadView.post()`
   - Creates `ImportJob` record
   - Calls `process_import_job.delay(job_id)`
   - Returns 202 with `job_id`

2. **Celery Task** → `datasets/tasks.py:process_import_job()`
   - Reads file with `schema_inference.py:read_uploaded_file()`
   - Infers schema with `schema_inference.py:build_schema()`
   - Creates table + bulk inserts with `schema_inference.py:create_table_and_insert()`
   - Creates `Dataset` + `DatasetColumn` records
   - Updates `ImportJob.status` to `done` or `failed`

3. **Frontend Polling** → `datasets/views.py:JobStatusView.get()`
   - Queries `ImportJob` by UUID
   - Gets progress from Celery `AsyncResult` if task is running

4. **Data Access** → `datasets/views.py:DatasetDataView.get()`
   - Queries dynamic table via raw SQL
   - Returns paginated rows + column metadata

5. **Edits** → `datasets/views.py:CellEditView.patch()`, `RowAddView`, `RowDeleteView`, `ColumnRenameView`
   - All use raw SQL against the dynamic staging table
   - Update `Dataset.row_count` accordingly

#### Key Files to Know

| File | Purpose |
|------|---------|
| `datasets/models.py` | Core data models |
| `datasets/tasks.py` | Async import processing + cleanup |
| `datasets/views.py` | All API endpoints |
| `datasets/utils/schema_inference.py` | Schema inference, bulk COPY insert, type casting |
| `datasets/serializers.py` | Request/response serialization |
| `frontend/src/services/datasetApi.js` | Frontend API client |
| `frontend/src/pages/Finance.jsx` | Example section page with upload + preview |
| `userconfig/settings.py` | Django + Celery configuration |

### Running the Application

```bash
# Terminal 1: Start Redis (Docker)
docker-compose up -d  # or: docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Start Django
cd backend
python manage.py runserver

# Terminal 3: Start Celery Worker
cd backend
celery -A userconfig worker -l info

# Terminal 4: Start Celery Beat (optional, for periodic cleanup)
cd backend
celery -A userconfig beat -l info

# Terminal 5: Start React frontend
cd frontend
npm run dev
```

### Testing a New Upload

1. Start all services (Django, Celery Worker, Redis)
2. Open React frontend (e.g., http://localhost:5173)
3. Navigate to Finance section
4. Upload a CSV/Excel file
5. Watch:
   - Job ID returned immediately
   - Polling starts, progress shows
   - Celery Worker logs show task processing
   - On success: dataset appears in list
   - On failure: error message shown
