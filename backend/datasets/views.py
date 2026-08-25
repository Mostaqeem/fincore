import math
from celery.result import AsyncResult
from django.contrib.auth import get_user_model
from django.http import Http404
from django.db import connection
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.permissions import user_has_capability
from notifications.services import notify_user

from .models import Dataset, DatasetColumn, ImportJob
from .permissions import HasSectionAccess
from .serializers import (
    DatasetSerializer, ImportJobSerializer, UploadSerializer,
    CellEditSerializer, RowAddSerializer, ColumnRenameSerializer,
    DatasetColumnSerializer, CreateTableSerializer,
)
from .tasks import process_import_job
from .utils.schema_inference import cast_value, sanitize_identifier

EDITABLE_STATUSES = ('draft', 'rejected')


def get_dataset_or_404(pk):
    try:
        return Dataset.objects.get(pk=pk)
    except Dataset.DoesNotExist:
        raise Http404


def conflict(message):
    return Response({'error': message}, status=status.HTTP_409_CONFLICT)


def _notify_interested_users(exclude_user, dataset, notification_type, title, metadata=None):
    """Notify all active users with review/approve permission for a dataset's section."""
    User = get_user_model()
    meta = {"dataset_id": str(dataset.id), "section": dataset.section}
    if metadata:
        meta.update(metadata)

    interested_users = User.objects.filter(is_active=True).exclude(id=exclude_user.id)
    for user in interested_users:
        if user_has_capability(user, dataset.section, 'can_review') or \
           user_has_capability(user, dataset.section, 'can_approve'):
            notify_user(
                user,
                type=notification_type,
                title=title,
                metadata=meta,
                persist=True,
            )


class UploadView(APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_create"

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']
        section = serializer.validated_data.get('section', 'finance')

        job = ImportJob.objects.create(
            original_filename=uploaded_file.name,
            source_file=uploaded_file,
            section=section,
            status='pending',
            created_by=request.user,
        )

        # Fire a `job_queued` notification before the worker picks up the
        # task — gives the user immediate feedback that their upload was
        # accepted. The terminal job_started / job_completed / job_failed
        # events come from process_import_job itself (see datasets/tasks.py).
        notify_user(
            request.user,
            type="job_queued",
            title=f"{uploaded_file.name} queued for processing",
            metadata={"job_id": str(job.id), "section": section},
            persist=True,
        )

        process_import_job.delay(str(job.id))

        return Response(
            {'job_id': str(job.id), 'status': 'pending'},
            status=status.HTTP_202_ACCEPTED
        )


class JobStatusView(APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_view"

    def get_section(self, request):
        try:
            job = ImportJob.objects.get(id=request.parser_context['kwargs']['job_id'])
            return job.section
        except (ImportJob.DoesNotExist, KeyError):
            return None

    def get(self, request, job_id):
        try:
            job = ImportJob.objects.get(id=job_id)
        except ImportJob.DoesNotExist:
            return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

        data = {
            'id': str(job.id),
            'status': job.status,
            'original_filename': job.original_filename,
            'created_at': job.created_at,
            'finished_at': job.finished_at,
        }

        if job.celery_task_id:
            try:
                async_result = AsyncResult(job.celery_task_id)
                if async_result.state == 'PROGRESS':
                    info = async_result.info
                    if isinstance(info, dict):
                        data['progress'] = {
                            'current': info.get('current', 0),
                            'total': info.get('total', 0),
                            'phase': info.get('phase', 'processing'),
                        }
            except Exception:
                pass

        if job.status == 'done' and job.dataset:
            data['dataset_id'] = str(job.dataset.id)
        elif job.status == 'failed':
            data['error_message'] = job.error_message

        return Response(data)


class DatasetListView(APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_view"

    def get(self, request):
        section = request.query_params.get('section', 'finance')
        datasets = Dataset.objects.filter(section=section)
        serializer = DatasetSerializer(datasets, many=True)
        return Response(serializer.data)


class TableStatsView(APIView):
    """Return the number of existing tables per department/section."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        section_counts = (
            Dataset.objects
            .values('section')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        choices = dict(Dataset.SECTION_CHOICES)
        return Response({
            'departments': [
                {
                    'name': choices.get(item['section'], item['section']),
                    'count': item['count'],
                }
                for item in section_counts
            ]
        })


class DatasetDetailView(APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]

    def get_section(self, request):
        try:
            return self.get_object(request.parser_context['kwargs']['pk']).section
        except (Http404, KeyError):
            return None

    def get_required_capability(self, request):
        return "can_delete" if request.method == "DELETE" else "can_view"

    def get_object(self, pk):
        try:
            return Dataset.objects.get(pk=pk)
        except Dataset.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        dataset = self.get_object(pk)
        serializer = DatasetSerializer(dataset)
        return Response(serializer.data)

    def delete(self, request, pk):
        dataset = self.get_object(pk)
        table_name = dataset.table_name

        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')

        dataset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DatasetDataView(APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_view"

    def get_section(self, request):
        try:
            return self.get_object(request.parser_context['kwargs']['pk']).section
        except (Http404, KeyError):
            return None

    def get_object(self, pk):
        try:
            return Dataset.objects.get(pk=pk)
        except Dataset.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        dataset = self.get_object(pk)
        table_name = dataset.table_name

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        offset = (page - 1) * page_size

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            total_count = cursor.fetchone()[0]

            cursor.execute(
                f'SELECT * FROM "{table_name}" ORDER BY id LIMIT %s OFFSET %s',
                [page_size, offset]
            )
            rows = cursor.fetchall()

            column_names = [desc[0] for desc in cursor.description]
            rows = [dict(zip(column_names, row)) for row in rows]

            cursor.execute(f'''
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s AND column_name != 'id'
                ORDER BY ordinal_position
            ''', [table_name])
            columns_info = cursor.fetchall()

        columns = [{'name': c[0], 'type': c[1]} for c in columns_info]
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

        return Response({
            'columns': columns,
            'rows': rows,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
        })


class DatasetEditMixin:
    """Requires can_edit and an editable dataset state (draft/rejected)."""

    def get_required_capability(self, request):
        return "can_edit"

    def _ensure_editable(self, request, dataset):
        if dataset.status not in EDITABLE_STATUSES:
            return conflict(
                f"Dataset is '{dataset.status}' and cannot be edited. "
                "Only draft or rejected tables can be edited."
            )
        return None


class CellEditView(DatasetEditMixin, APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def patch(self, request, pk, row_id):
        try:
            dataset = Dataset.objects.get(pk=pk)
        except Dataset.DoesNotExist:
            return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)

        blocked = self._ensure_editable(request, dataset)
        if blocked:
            return blocked

        serializer = CellEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        column_name = serializer.validated_data['column']
        value = serializer.validated_data['value']

        column = dataset.columns.filter(column_name=column_name).first()
        if not column:
            return Response({'error': 'Column not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            typed_value = cast_value(value, column.data_type)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE "{dataset.table_name}" SET "{column_name}" = %s WHERE id = %s',
                [typed_value, row_id]
            )

        return Response({'success': True, 'column': column_name, 'value': typed_value})


class RowAddView(DatasetEditMixin, APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def post(self, request, pk):
        try:
            dataset = Dataset.objects.get(pk=pk)
        except Dataset.DoesNotExist:
            return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)

        blocked = self._ensure_editable(request, dataset)
        if blocked:
            return blocked

        serializer = RowAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data['data']
        columns = list(data.keys())
        values = list(data.values())

        columns_str = ', '.join([f'"{c}"' for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))

        with connection.cursor() as cursor:
            cursor.execute(
                f'INSERT INTO "{dataset.table_name}" ({columns_str}) VALUES ({placeholders}) RETURNING id',
                values
            )
            new_id = cursor.fetchone()[0]

        dataset.row_count += 1
        dataset.save()

        return Response({'id': new_id, 'row_count': dataset.row_count}, status=status.HTTP_201_CREATED)


class RowUpdateView(DatasetEditMixin, APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def patch(self, request, pk, row_id):
        try:
            dataset = Dataset.objects.get(pk=pk)
        except Dataset.DoesNotExist:
            return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)

        blocked = self._ensure_editable(request, dataset)
        if blocked:
            return blocked

        data = request.data

        if not data:
            return Response({'error': 'No data provided'}, status=status.HTTP_400_BAD_REQUEST)

        set_clauses = []
        values = []
        for column_name, value in data.items():
            set_clauses.append(f'"{column_name}" = %s')
            values.append(value)

        values.append(row_id)

        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE "{dataset.table_name}" SET {", ".join(set_clauses)} WHERE id = %s',
                values
            )

        return Response({'success': True, 'id': row_id})


class RowDeleteView(DatasetEditMixin, APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def delete(self, request, pk, row_id):
        try:
            dataset = Dataset.objects.get(pk=pk)
        except Dataset.DoesNotExist:
            return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)

        blocked = self._ensure_editable(request, dataset)
        if blocked:
            return blocked

        with connection.cursor() as cursor:
            cursor.execute(f'DELETE FROM "{dataset.table_name}" WHERE id = %s', [row_id])

        dataset.row_count = max(0, dataset.row_count - 1)
        dataset.save()

        return Response({'success': True, 'row_count': dataset.row_count})


class ColumnRenameView(DatasetEditMixin, APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def patch(self, request, pk, column_name):
        try:
            dataset = Dataset.objects.get(pk=pk)
        except Dataset.DoesNotExist:
            return Response({'error': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)

        blocked = self._ensure_editable(request, dataset)
        if blocked:
            return blocked

        serializer = ColumnRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_name = sanitize_identifier(serializer.validated_data['new_name'])

        column = dataset.columns.filter(column_name=column_name).first()
        if not column:
            return Response({'error': 'Column not found'}, status=status.HTTP_404_NOT_FOUND)

        with connection.cursor() as cursor:
            cursor.execute(
                f'ALTER TABLE "{dataset.table_name}" RENAME COLUMN "{column_name}" TO "{new_name}"'
            )

        column.column_name = new_name
        column.save()

        return Response({'success': True, 'old_name': column_name, 'new_name': new_name})


class SubmitView(APIView):
    """Creator submits a draft/rejected table for review."""

    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_create"

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def post(self, request, pk):
        dataset = get_dataset_or_404(pk)

        if dataset.status not in ('draft', 'rejected'):
            return conflict(f"Only draft or rejected tables can be submitted (current: {dataset.status}).")

        if dataset.created_by_id and dataset.created_by_id != request.user.id:
            return Response(
                {'error': "Only the table's creator can submit it for review."},
                status=status.HTTP_403_FORBIDDEN,
            )

        dataset.status = 'submitted'
        dataset.submitted_by = request.user
        dataset.submitted_at = timezone.now()
        dataset.rejection_comment = ''
        dataset.save()

        _notify_interested_users(
            exclude_user=request.user,
            dataset=dataset,
            notification_type="review_submitted",
            title=f"Table submitted for review: {dataset.name}",
        )

        return Response({'success': True, 'status': dataset.status})


class StartReviewView(APIView):
    """Reviewer begins reviewing a submitted table."""

    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_review"

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def post(self, request, pk):
        dataset = get_dataset_or_404(pk)

        if dataset.status != 'submitted':
            return conflict(f"Only submitted tables can enter review (current: {dataset.status}).")

        if dataset.created_by_id == request.user.id:
            return Response(
                {'error': "A table's creator cannot review their own table."},
                status=status.HTTP_403_FORBIDDEN,
            )

        dataset.status = 'in_review'
        dataset.save()

        _notify_interested_users(
            exclude_user=request.user,
            dataset=dataset,
            notification_type="review_started",
            title=f"Review started for {dataset.name}",
        )

        return Response({'success': True, 'status': dataset.status})


class ReviewApproveView(APIView):
    """Reviewer approves a reviewed-in table, moving it to reviewed (pending final approval)."""

    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_review"

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def post(self, request, pk):
        dataset = get_dataset_or_404(pk)

        if dataset.status != 'in_review':
            return conflict(f"Only tables in review can be review-approved (current: {dataset.status}).")

        if dataset.created_by_id == request.user.id:
            return Response(
                {'error': "A table's creator cannot review their own table."},
                status=status.HTTP_403_FORBIDDEN,
            )

        dataset.status = 'reviewed'
        dataset.reviewed_by = request.user
        dataset.reviewed_at = timezone.now()
        dataset.review_comment = request.data.get('comment', '')
        dataset.rejection_comment = ''
        dataset.save()

        _notify_interested_users(
            exclude_user=request.user,
            dataset=dataset,
            notification_type="review_approved",
            title=f"Table review approved: {dataset.name}",
            metadata={"comment": dataset.review_comment},
        )

        return Response({'success': True, 'status': dataset.status})


class ApproveView(APIView):
    """Approver confirms a reviewed table, moving it to confirmed."""

    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_approve"

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def post(self, request, pk):
        dataset = get_dataset_or_404(pk)

        if dataset.status != 'reviewed':
            return conflict(f"Only reviewed tables can be approved (current: {dataset.status}).")

        if dataset.created_by_id == request.user.id:
            return Response(
                {'error': "A table's creator cannot approve their own table."},
                status=status.HTTP_403_FORBIDDEN,
            )

        dataset.status = 'confirmed'
        dataset.approved_by = request.user
        dataset.approved_at = timezone.now()
        dataset.approval_comment = request.data.get('comment', '')
        dataset.rejection_comment = ''
        dataset.save()

        _notify_interested_users(
            exclude_user=request.user,
            dataset=dataset,
            notification_type="table_approved",
            title=f"Table approved: {dataset.name}",
            metadata={"comment": dataset.approval_comment},
        )

        return Response({'success': True, 'status': dataset.status})


class RejectView(APIView):
    """Reviewer or approver rejects a table, returning it to rejected for rework."""

    permission_classes = [IsAuthenticated, HasSectionAccess]

    def get_section(self, request):
        try:
            return Dataset.objects.get(pk=request.parser_context['kwargs']['pk']).section
        except (Dataset.DoesNotExist, KeyError):
            return None

    def get_required_capability(self, request):
        return "can_review"

    def post(self, request, pk):
        dataset = get_dataset_or_404(pk)

        if dataset.status not in ('in_review', 'reviewed'):
            return conflict(f"Only tables in review/reviewed can be rejected (current: {dataset.status}).")

        can_review = user_has_capability(request.user, dataset.section, 'can_review')
        can_approve = user_has_capability(request.user, dataset.section, 'can_approve')
        if not (can_review or can_approve):
            return Response(
                {'error': "You do not have permission to reject this table."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if dataset.created_by_id == request.user.id:
            return Response(
                {'error': "A table's creator cannot reject their own table."},
                status=status.HTTP_403_FORBIDDEN,
            )

        dataset.status = 'rejected'
        dataset.rejection_comment = request.data.get('comment', '')
        dataset.save()

        rejection_meta = {"comment": dataset.rejection_comment}

        # 1. Notify the table creator so they know their table was rejected.
        if dataset.created_by:
            notify_user(
                dataset.created_by,
                type="table_rejected",
                title=f"Table rejected: {dataset.name}",
                metadata=rejection_meta,
                persist=True,
            )

        # 2. Notify other reviewers/approvers so they know the workflow ended.
        _notify_interested_users(
            exclude_user=request.user,
            dataset=dataset,
            notification_type="table_rejected",
            title=f"Table rejected: {dataset.name}",
            metadata=rejection_meta,
        )

        return Response({'success': True, 'status': dataset.status})


class CreateManualTableView(APIView):
    permission_classes = [IsAuthenticated, HasSectionAccess]
    required_capability = "can_create"

    def post(self, request):
        serializer = CreateTableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        name = data['name']
        section = data.get('section', 'finance')
        col_count = data['col_count']
        row_count = data['row_count']
        
        from .utils.schema_inference import generate_table_name
        table_name = generate_table_name(section)
        
        # 1. Create the physical table
        columns_def = ['id SERIAL PRIMARY KEY']
        columns_info = []
        for i in range(1, col_count + 1):
            col_name = f"column_{i}"
            columns_def.append(f'"{col_name}" TEXT')
            columns_info.append({
                'column_name': col_name,
                'data_type': 'TEXT',
                'ordinal_position': i
            })
        
        create_sql = f'CREATE TABLE "{table_name}" ({", ".join(columns_def)})'
        
        with connection.cursor() as cursor:
            cursor.execute(create_sql)
            
            # Insert empty rows
            if row_count > 0:
                cols_str = ', '.join([f'"{c["column_name"]}"' for c in columns_info])
                vals_str = ', '.join(['%s'] * col_count)
                
                # Bulk insert empty rows
                empty_row = [None] * col_count
                insert_sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({vals_str})'
                
                # We use a loop for simplicity in creating the exact number of requested rows
                for _ in range(row_count):
                    cursor.execute(insert_sql, empty_row)

        # 2. Create Dataset record
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        original_filename = f"manual_{section}_{timestamp}.csv"
        
        dataset = Dataset.objects.create(
            name=name,
            original_filename=original_filename,
            source_file=None, # FileField allow null if not specified otherwise in DB, but models.py says source_file = models.FileField(...)
            table_name=table_name,
            row_count=row_count,
            status='draft',
            section=section,
            created_by=request.user
        )
        
        # 3. Create DatasetColumn records
        for col in columns_info:
            DatasetColumn.objects.create(
                dataset=dataset,
                **col
            )
            
        return Response({
            'id': dataset.id,
            'name': dataset.name,
            'table_name': table_name
        }, status=status.HTTP_201_CREATED)
