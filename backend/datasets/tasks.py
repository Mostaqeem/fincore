from celery import shared_task
from django.db import transaction, connection
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from .models import Dataset, DatasetColumn, ImportJob
from .utils.schema_inference import (
    read_uploaded_file,
    build_schema,
    generate_table_name,
    create_table_and_insert,
)

STALE_JOB_THRESHOLD_MINUTES = 30


@shared_task(bind=True)
def process_import_job(self, job_id):
    """Process an import job with ACID compliance and progress reporting."""
    job = ImportJob.objects.get(id=job_id)
    job.status = 'processing'
    job.celery_task_id = self.request.id
    job.save()

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
            row_count = create_table_and_insert(table_name, schema, df, self)
            
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

        return {'status': 'done', 'dataset_id': str(dataset.id)}

    except Exception as e:
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
