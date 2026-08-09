from django.contrib import admin
from .models import Dataset, DatasetColumn, ImportJob


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'table_name', 'row_count', 'status', 'created_by', 'uploaded_at']
    list_filter = ['section', 'status']
    search_fields = ['name', 'table_name']
    readonly_fields = [
        'created_by', 'submitted_by', 'submitted_at',
        'reviewed_by', 'reviewed_at', 'review_comment',
        'approved_by', 'approved_at', 'approval_comment',
        'rejection_comment',
    ]


@admin.register(DatasetColumn)
class DatasetColumnAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'column_name', 'data_type', 'ordinal_position']
    list_filter = ['data_type']
    search_fields = ['column_name', 'dataset__name']


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_filename', 'section', 'status', 'created_by', 'created_at', 'finished_at']
    list_filter = ['status', 'section']
    search_fields = ['original_filename']
