from rest_framework import serializers
from .models import Dataset, DatasetColumn, ImportJob


class DatasetColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatasetColumn
        fields = ['id', 'column_name', 'data_type', 'ordinal_position']


class DatasetSerializer(serializers.ModelSerializer):
    columns = DatasetColumnSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Dataset
        fields = [
            'id', 'name', 'original_filename', 'table_name', 'row_count',
            'status', 'section', 'uploaded_at', 'columns',
            'created_by', 'created_by_name',
            'submitted_by', 'submitted_by_name', 'submitted_at',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at', 'review_comment',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_comment',
            'rejection_comment',
        ]
        read_only_fields = ['id', 'table_name', 'row_count', 'status', 'uploaded_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return obj.submitted_by.get_full_name() or obj.submitted_by.email
        return None

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.email
        return None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return None


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = ['id', 'original_filename', 'status', 'error_message', 'dataset', 'section', 'created_at', 'finished_at']
        read_only_fields = ['id', 'status', 'error_message', 'dataset', 'created_at', 'finished_at']


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    section = serializers.ChoiceField(choices=Dataset.SECTION_CHOICES, default='finance')


class CellEditSerializer(serializers.Serializer):
    column = serializers.CharField()
    value = serializers.CharField(allow_blank=True)


class RowAddSerializer(serializers.Serializer):
    data = serializers.DictField()


class ColumnRenameSerializer(serializers.Serializer):
    new_name = serializers.CharField(max_length=63)


class CreateTableSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    col_count = serializers.IntegerField(min_value=1)
    row_count = serializers.IntegerField(min_value=0)
    section = serializers.CharField(max_length=20, default='finance')
