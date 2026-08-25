# Bug Fixes & Troubleshooting Guide

This document outlines the issues encountered during the implementation of the Dynamic Schema Importer and their solutions.

---

## Issue 1: Celery Task Not Executing

### Symptom
After uploading a file, the job status remained `pending` indefinitely. The Celery worker was running but not picking up tasks.

### Root Cause
The task was being queued but not executed. This was later discovered to be a timing issue - the task was running but took too long.

### Solution
Ran the task synchronously to verify it worked:
```bash
cd backend
source ../.venv/bin/activate
python -c "
from datasets.tasks import process_import_job
process_import_job('job-id-here')
"
```

---

## Issue 2: Slow Row-by-Row Insert (Initial Implementation)

### Symptom
The import task was extremely slow for large files (750 rows took over 2 minutes). The job remained in `processing` status for too long.

### Root Cause
The original implementation inserted data row-by-row using `cursor.execute()` inside a loop:

```python
# SLOW - inserts one row at a time
for _, row in df.iterrows():
    cursor.execute(insert_sql, values)
```

### Solution
Replaced with PostgreSQL's `COPY` command for bulk insert:

```python
# FAST - bulk insert using COPY
import io

buffer = io.StringIO()
for _, row in df.iterrows():
    values = [...]
    buffer.write('\t'.join(values) + '\n')

buffer.seek(0)
cursor.copy_expert(copy_sql, buffer)
```

**File Modified:** `datasets/utils/schema_inference.py` - `create_table_and_insert()` function

---

## Issue 3: Cell Edit Failing - Data Type Mismatch

### Symptom
When trying to edit a cell (PATCH request), the API returned a 500 error:
```
can't adapt type 'numpy.int64'
```

### Root Cause
Two problems:

1. **Type Casting Issue**: The `cast_value()` function only handled `'VARCHAR'` but PostgreSQL returns the type as `'character varying'` (or just `'varchar'`).

2. **PostgreSQL Type Names**: When querying `information_schema.columns`, PostgreSQL returns:
   - `character varying(15)` instead of `VARCHAR(15)`
   - `numeric` instead of `NUMERIC`

### Solution
Updated the `cast_value()` function in `schema_inference.py` to handle more type variations:

```python
def cast_value(value, pg_type):
    pg_type_upper = pg_type.upper()

    if 'BIGINT' in pg_type_upper or 'INT' in pg_type_upper:
        return int(value)
    elif 'NUMERIC' in pg_type_upper or 'DECIMAL' in pg_type_upper or 'REAL' in pg_type_upper or 'FLOAT' in pg_type_upper or 'DOUBLE' in pg_type_upper:
        return float(value)
    elif pg_type_upper == 'BOOLEAN' or 'BOOL' in pg_type_upper:
        # Handle boolean conversion
        ...
    elif 'TIMESTAMP' in pg_type_upper or 'DATE' in pg_type_upper:
        return pd.to_datetime(value)
    elif 'CHARACTER' in pg_type_upper or 'VARCHAR' in pg_type_upper or 'TEXT' in pg_type_upper:
        return str(value)
    else:
        return str(value)
```

**File Modified:** `datasets/utils/schema_inference.py` - `cast_value()` function

---

## Issue 4: Date Parsing Warning

### Symptom
When importing files with date columns, pandas showed warnings:
```
UserWarning: Could not infer format, each element will be parsed individually
```

### Root Cause
The `infer_pg_type()` function uses `pd.to_datetime()` without specifying a format, causing pandas to guess the format for each value.

### Impact
This is a minor issue - dates are still correctly parsed, just with a performance warning. The warning doesn't affect functionality.

**Resolved:** `infer_pg_type()` now calls `pd.to_datetime(..., format='mixed')`, so pandas uses its fast format-inference path and the warning no longer appears. See Issue 7 for details.

---

## Issue 5: COPY Failure — `date/time field value out of range: "74"`

### Symptom
Importing a file with integer columns (e.g. `Age`, `Year`) failed during the bulk insert:
```
Error: date/time field value out of range: "74"
HINT:  Perhaps you need a different "datestyle" setting.
CONTEXT:  COPY ds_risk_b5288cb1, line 1, column Age: "74"
```
This hit **every integer column**, not just `Age` (`Year`, `Quarter`, `Month`, `Week`, counts, etc.).

### Root Cause
Two interacting bugs in `infer_pg_type()`:

1. **`apply(float.is_integer)` raises `TypeError` on integer columns.** With pandas 3.0 + numpy 2.5:
   ```
   TypeError: descriptor 'is_integer' for 'float' objects doesn't apply to a 'int' object
   ```
   The surrounding `except Exception: pass` swallowed it, so the numeric branch **silently never returned** a type.

2. **`pd.to_datetime()` treats integers as nanoseconds since epoch.** `Age = [74, 25, 48, ...]` parsed as `1970-01-01 00:00:00.000000074`. The "conservative" guard `years.between(1900, 2100).all()` passed because **1970 is inside the range**, so the column was inferred as `TIMESTAMP`. `CREATE TABLE` then made `Age` a timestamp column, and `COPY` of `"74"` failed.

### Solution
- Replaced `numeric_series.apply(float.is_integer)` with `pd.api.types.is_integer_dtype(numeric_series)` — integer columns now correctly become `BIGINT`.
- Hardened the date branch so **purely numeric columns never go through `to_datetime`** (prevents the nanoseconds-since-epoch gotcha from ever firing again).

**File Modified:** `datasets/utils/schema_inference.py` - `infer_pg_type()`

---

## Issue 6: Bare Time-of-Day Columns Broke COPY

### Symptom
A column of times (e.g. `TransactionTime` = `11:25:37`) was inferred as `TIMESTAMP` and then failed during `COPY` because Postgres cannot load a bare time into a `timestamp` column.

### Root Cause
`pd.to_datetime("11:25:37", format='mixed')` returns **today's date** with that time (e.g. `2026-08-02 11:25:37`). The year was inside 1900–2100, so the guard passed and the column was typed `TIMESTAMP`.

### Solution
Added a `pure_time` guard in `infer_pg_type()`: if more than 50% of the sampled values match `HH:MM(:SS)`, the column is **not** classified as `TIMESTAMP` and falls through to `VARCHAR`/`TEXT`.

**File Modified:** `datasets/utils/schema_inference.py` - `infer_pg_type()`

---

## Issue 7: 1M-Row Upload Extremely Slow (Dateutil Warning + iterrows Loop)

### Symptom
Uploading `banking_data_1M.csv` (1M rows, 51 columns) left the job stuck in `processing` for a very long time. The worker log showed:
```
UserWarning: Could not infer format, so each element will be parsed individually,
falling back to `dateutil`. To ensure parsing is consistent and as-expected,
please specify a format.
```

### Root Cause
Three compounding bottlenecks:

1. **`pd.to_datetime(series, errors='coerce')` without a format** parses every element individually via `dateutil`. Measured: **41.5s for a single non-date column** over 1M rows. `infer_pg_type()` ran this for every column.
2. **Schema inference ran full-column parses** (`to_numeric`, `to_datetime`, `str.len`, etc.) on all 1M rows.
3. **`create_table_and_insert()` built the COPY buffer with `df.iterrows()`** — a pure-Python loop over every row/cell (minutes-to-hours for 1M rows) that also materialized a huge in-memory string buffer before `copy_expert` ran.

### Solution
Reworked `schema_inference.py` for speed and bounded memory:

- **Sample-based inference:** only 10k–50k rows are used to pick a type (`INFERENCE_SAMPLE_SIZE = 50000`, `PREFILTER_SAMPLE_SIZE = 10000`).
- **Cheap regex pre-filters** (`_looks_numeric`, `_looks_datetime`) skip the expensive full-column parses for non-numeric / non-date text columns.
- **`format='mixed'`** passed to `pd.to_datetime` (fast format inference; real date columns now parse in ~0.5s).
- **Boolean check gated** behind a sample pre-filter so text columns don't pay for a full 1M-row string pass.
- **UUIDs excluded** from date-like detection — `CustomerID`/`TransactionID`/`LoanID` have dashes and were hitting the slow date parser (~5s each).
- **Chunked insert:** `create_table_and_insert()` now serializes in 100k-row chunks via C-optimized `df.to_csv(...)` and calls `cursor.copy_expert` per chunk, reporting `PROGRESS` per chunk and keeping memory bounded.

### Verified Results (banking_data_1M.csv, 1M rows)
- Read: ~18–20s
- Schema inference: ~13s (was ~30s+ before the UUID fix)
- `COPY` insert of 1,000,000 rows: ~64s — **no more error**
- Correct types: `Age`→`bigint`, `Year/Quarter/Month/Week`→`bigint`, `OpenDate`/`TransactionDate`→`timestamp`, `TransactionTime`→`varchar`, amounts→`numeric`

Full 1M-row upload is now roughly ~95s end-to-end.

**Files Modified:** `datasets/utils/schema_inference.py` - `infer_pg_type()`, `_looks_numeric()`, `_looks_datetime()`, `create_table_and_insert()`

---

## Issue 8: Orphaned Datasets with `created_by=None` Block Workflow

### Symptom
Datasets created via the import pipeline had `created_by=None`. The frontend "Submit for Review" button never appears because it requires `isCreator` (`DataEditor.jsx:449`) — which is always `false` when `created_by` is null. Without submission, the status never reaches `submitted`/`in_review`, so reviewer/approver buttons never render.

### Root Cause
Early uploads were processed by the Celery worker before the `ImportJob.created_by` field was properly populated, or datasets were inserted via `CreateManualTableView` in a context where the request user was not linked. The resulting Dataset rows had `created_by = NULL`.

**Verified DB State:**
```
cards_csv       | finance | draft | created_by=None
TestFinance_csv | finance | draft | created_by=None
```

No user could submit these tables — the creator check blocked everyone.

### Solution
Patched orphaned datasets to assign `created_by` to the appropriate user. The Celery task (`datasets/tasks.py:57`) already passes `created_by=job.created_by` correctly; the issue was in existing data from early uploads.

```python
# Quick fix — assign orphaned datasets to the first non-staff user
from datasets.models import Dataset
from accounts.models import User

owner = User.objects.filter(is_staff=False).first()
Dataset.objects.filter(created_by__isnull=True).update(created_by=owner)
```

**Files involved:** `datasets/views.py` (`CreateManualTableView`), `datasets/tasks.py`

---

## Issue 9: Missing `RoleDepartment` Binding for Approver on Finance

### Symptom
Even after a dataset reaches `reviewed` status, no approver sees the "Approve" button because `can_approve` for finance is empty. The reviewer/approver workflow buttons never appear for users who have the correct role but lack a `RoleDepartment` binding.

### Root Cause
The seed migration (`employees/migrations/0003_seed_default_roles.py`) only created the Role objects (CREATOR, REVIEWER, APPROVER). It did **not** create `RoleDepartment` records linking roles to departments with module lists. The capability system requires three things to align:

1. User has an `EmployeeProfile` with a department
2. Profile has the role assigned
3. A `RoleDepartment` record binds that role to the department with the right module

Without step 3, `get_active_role_assignments()` returns an empty list and the user gets zero capabilities.

**Verified DB State:**
```
RoleDepartment rows:
  CREATOR  → FINANCE  [finance]
  REVIEWER → FINANCE  [finance]
  APPROVER → IT       [it]          ← missing APPROVER → FINANCE
```

No approver was bound to finance, so `can_approve` was empty for the finance module. The reviewer had `can_review` but the approver could never act.

### Solution
Created the missing `RoleDepartment` binding. To prevent this for fresh installs, seed `RoleDepartment` records alongside roles in a migration, binding each role to every existing department with appropriate modules (FINANCE→finance, IT→it, RISK→risk):

```python
# Fix existing data — bind APPROVER to FINANCE
from employees.models import Role, Department, RoleDepartment

finance = Department.objects.get(name="FINANCE")
approver = Role.objects.get(name="APPROVER")
RoleDepartment.objects.get_or_create(
    role=approver, department=finance,
    defaults={"modules": ["finance"], "is_active": True},
)
```

**Files involved:** `employees/migrations/0003_seed_default_roles.py`, `employees/permissions.py`

---

## Summary of Files Modified

| File | Changes |
|------|---------|
| `datasets/utils/schema_inference.py` | 1. Changed `create_table_and_insert()` to use COPY command<br>2. Updated `cast_value()` to handle more PostgreSQL types<br>3. Fixed integer detection (`is_integer_dtype`) and hardened date inference (Issues 5–6)<br>4. Added sample-based inference + chunked `to_csv` insert for 1M-row performance (Issue 7) |
| `datasets/tasks.py` | Created Celery task for async import processing |
| `datasets/views.py` | Created REST API views for all endpoints |
| `datasets/serializers.py` | Created DRF serializers |
| `datasets/models.py` | Created Dataset, DatasetColumn, ImportJob models |
| `datasets/urls.py` | URL routing |
| `userconfig/settings.py` | Added datasets app, MEDIA_ROOT/URL, Celery config |
| `userconfig/urls.py` | Included datasets URLs |
| `employees/permissions.py` | RBAC capability resolution (`get_active_role_assignments`, `user_module_capabilities`) — Issue 9 |
| `employees/migrations/0003_seed_default_roles.py` | Seeded CREATOR/REVIEWER/APPROVER roles — Issue 9 |

---

## Testing Commands

```bash
# Upload a file
curl -X POST http://localhost:8000/api/datasets/upload/ \
  -F "file=@/path/to/file.csv" \
  -F "section=finance"

# Check job status
curl http://localhost:8000/api/datasets/jobs/<job_id>/

# Get paginated data
curl "http://localhost:8000/api/datasets/<dataset_id>/data/?page=1&page_size=50"

# Edit a cell
curl -X PATCH "http://localhost:8000/api/datasets/<id>/data/<row_id>/" \
  -H "Content-Type: application/json" \
  -d '{"column": "column_name", "value": "new_value"}'

# Promote dataset
curl -X POST "http://localhost:8000/api/datasets/<id>/promote/"

# List all datasets for a section
curl "http://localhost:8000/api/datasets/?section=finance"
```

---

## Notes

- The Django server must be restarted after code changes for them to take effect
- Celery worker must be running: `celery -A userconfig worker --loglevel=info`
- Redis must be running (via Docker or directly)
