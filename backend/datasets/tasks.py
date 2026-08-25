"""Celery tasks for the datasets app.

process_import_job is the heavy worker that turns an uploaded CSV/Excel
file into a Postgres table + Dataset row. It reports progress through two
mechanisms in parallel:

  1. self.update_state()       — polled by DatasetManager via /jobs/<uuid>/
                                 (existing behavior, kept for backward
                                 compat with the polling UI).
  2. notify_user() from the notifications app — pushes events to the
                                 user's WebSocket so toasts and the bell
                                 update in real time.

The notify_user() calls are deliberately tagged persist=False for the
high-frequency `job_progress` events (one per COPY chunk) so we don't
write a row per chunk to the database. The terminal `job_completed` /
`job_failed` events use persist=True so they appear in bell history.
"""
from celery import shared_task
from django.db import transaction, connection
from django.utils import timezone
from datetime import timedelta

from notifications.services import notify_user

from .models import Dataset, DatasetColumn, ImportJob
from .utils.schema_inference import (
    read_uploaded_file,
    build_schema,
    generate_table_name,
    create_table_and_insert,
)

STALE_JOB_THRESHOLD_MINUTES = 30


def _notify_progress(user, job_id, current, total, phase):
    """Build the `job_progress` payload and push it via WebSocket.

    Kept as a tiny helper so the callback in process_import_job stays
    readable. persist=False: progress ticks are high-frequency and
    shouldn't bloat the notifications table — they only matter in the
    live UI (progress bar + toast on completion).
    """
    if not total:
        return
    notify_user(
        user,
        type="job_progress",
        title=f"Processing… {current}/{total} rows",
        metadata={
            "job_id": str(job_id),
            "current": current,
            "total": total,
            "percent": round(current / total * 100, 1),
            "phase": phase,
        },
        persist=False,
    )


@shared_task(bind=True)
def process_import_job(self, job_id):
    """Process an import job with ACID compliance, progress reporting,
    and real-time notifications.

    Notification timeline:
      job_started   → on entering this function (persist=False)
      job_progress  → per COPY chunk (persist=False)
      job_completed → on success (persist=True)
      job_failed    → on any exception (persist=True)

    Note: `job_queued` is fired by the view (UploadView.post) right
    before .delay() — that's when the user just hit Upload, before the
    worker even picks it up.
    """
    job = ImportJob.objects.get(id=job_id)
    user = job.created_by  # may be None for system-created jobs
    job.status = 'processing'
    job.celery_task_id = self.request.id
    job.save()

    # Live toast: the worker has picked up the job.
    if user:
        notify_user(
            user,
            type="job_started",
            title=f"Processing {job.original_filename}",
            metadata={"job_id": str(job.id)},
            persist=False,
        )

    # Closure passed into create_table_and_insert so it can notify on
    # each COPY chunk without needing to know about notifications itself.
    def on_progress(current, total, phase):
        if user:
            _notify_progress(user, job.id, current, total, phase)

    table_name = None

    try:
        file_path = job.source_file.path
        with open(file_path, 'rb') as f:
            df = read_uploaded_file(f)

        total_rows = len(df)

        schema, df = build_schema(df)
        table_name = generate_table_name(job.section)

        job.pending_table_name = table_name
        job.save()

        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': total_rows, 'phase': 'creating_table'}
        )

        with transaction.atomic():
            # create_table_and_insert invokes on_progress(...) per COPY
            # chunk alongside its existing self.update_state() call.
            row_count = create_table_and_insert(
                table_name, schema, df, task=self, on_progress=on_progress
            )

            dataset = Dataset.objects.create(
                name=job.original_filename.replace('.', '_'),
                original_filename=job.original_filename,
                source_file=job.source_file,
                table_name=table_name,
                row_count=row_count,
                status='draft',
                section=job.section,
                created_by=job.created_by,
            )

            for col in schema:
                DatasetColumn.objects.create(
                    dataset=dataset,
                    column_name=col['column_name'],
                    data_type=col['data_type'],
                    ordinal_position=col['ordinal_position'],
                )

            job.dataset = dataset
            job.status = 'done'
            job.finished_at = timezone.now()
            job.pending_table_name = None
            job.save()

        # Bell + toast: terminal success event. persist=True so this
        # shows up in the bell dropdown history.
        if user:
            notify_user(
                user,
                type="job_completed",
                title=f"{job.original_filename} processed",
                message=f"{row_count} rows imported.",
                metadata={
                    "job_id": str(job.id),
                    "dataset_id": str(dataset.id),
                    "rows_processed": row_count,
                },
                persist=True,
            )

        return {'status': 'done', 'dataset_id': str(dataset.id)}

    except Exception as e:
        # Best-effort cleanup of the half-created physical table.
        if table_name:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            except Exception:
                pass

        try:
            if job.source_file:
                job.source_file.delete(save=False)
        except Exception:
            pass

        job.status = 'failed'
        job.error_message = str(e)
        job.finished_at = timezone.now()
        job.pending_table_name = None
        job.save()

        # Bell + toast: terminal failure event. persist=True so the
        # user can find it later in the bell.
        if user:
            notify_user(
                user,
                type="job_failed",
                title=f"{job.original_filename} failed",
                message=str(e),
                metadata={
                    "job_id": str(job.id),
                    "error": str(e),
                },
                persist=True,
            )

        return {'status': 'failed', 'error': str(e)}


@shared_task
def cleanup_stale_jobs():
    """Clean up jobs stuck in 'processing' status for too long."""
    cutoff_time = timezone.now() - timedelta(minutes=STALE_JOB_THRESHOLD_MINUTES)

    stale_jobs = ImportJob.objects.filter(
        status='processing',
        created_at__lt=cutoff_time
    )

    cleaned_count = 0

    for job in stale_jobs:
        if job.pending_table_name:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP TABLE IF EXISTS "{job.pending_table_name}"')
            except Exception:
                pass

        try:
            if job.source_file:
                job.source_file.delete(save=False)
        except Exception:
            pass

        job.status = 'failed'
        job.error_message = 'Job timed out due to worker failure or long processing time'
        job.finished_at = timezone.now()
        job.pending_table_name = None
        job.save()

        cleaned_count += 1

    return {'cleaned_count': cleaned_count}