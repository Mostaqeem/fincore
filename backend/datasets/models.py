import uuid
from django.db import models
from django.conf import settings


class Dataset(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('reviewed', 'Reviewed'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
    ]

    SECTION_CHOICES = [
        ('finance', 'Finance'),
        ('it', 'IT'),
        ('risk', 'Risk Management'),
    ]

    WORKFLOW_ORDER = {
        'draft': 0,
        'submitted': 1,
        'in_review': 2,
        'reviewed': 3,
        'confirmed': 4,
        'rejected': -1,
    }

    name = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    source_file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    table_name = models.CharField(max_length=63, unique=True)
    row_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, default='finance')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='datasets'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_datasets'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_datasets'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_datasets'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_comment = models.TextField(blank=True)
    rejection_comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.name} ({self.section})"


class DatasetColumn(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='columns')
    column_name = models.CharField(max_length=63)
    data_type = models.CharField(max_length=50)
    ordinal_position = models.IntegerField()

    class Meta:
        ordering = ['ordinal_position']
        unique_together = ['dataset', 'column_name']

    def __str__(self):
        return f"{self.dataset.name}.{self.column_name}"


class ImportJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_filename = models.CharField(max_length=255)
    source_file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(null=True, blank=True)
    dataset = models.ForeignKey(Dataset, on_delete=models.SET_NULL, null=True, blank=True, related_name='import_jobs')
    section = models.CharField(max_length=20, default='finance')
    pending_table_name = models.CharField(max_length=63, null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_jobs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"ImportJob {self.id} - {self.status}"
