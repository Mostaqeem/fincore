from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.UploadView.as_view(), name='upload'),
    path('create-manual/', views.CreateManualTableView.as_view(), name='create-manual'),
    path('table-stats/', views.TableStatsView.as_view(), name='table-stats'),
    path('jobs/<uuid:job_id>/', views.JobStatusView.as_view(), name='job-status'),
    path('', views.DatasetListView.as_view(), name='dataset-list'),
    path('<int:pk>/', views.DatasetDetailView.as_view(), name='dataset-detail'),
    path('<int:pk>/data/', views.DatasetDataView.as_view(), name='dataset-data'),
    path('<int:pk>/data/<int:row_id>/', views.CellEditView.as_view(), name='cell-edit'),
    path('<int:pk>/rows/', views.RowAddView.as_view(), name='row-add'),
    path('<int:pk>/rows/<int:row_id>/', views.RowUpdateView.as_view(), name='row-update'),
    path('<int:pk>/rows/<int:row_id>/delete/', views.RowDeleteView.as_view(), name='row-delete'),
    path('<int:pk>/columns/<str:column_name>/', views.ColumnRenameView.as_view(), name='column-rename'),
    path('<int:pk>/submit/', views.SubmitView.as_view(), name='submit'),
    path('<int:pk>/start-review/', views.StartReviewView.as_view(), name='start-review'),
    path('<int:pk>/review-approve/', views.ReviewApproveView.as_view(), name='review-approve'),
    path('<int:pk>/approve/', views.ApproveView.as_view(), name='approve'),
    path('<int:pk>/reject/', views.RejectView.as_view(), name='reject'),
]
