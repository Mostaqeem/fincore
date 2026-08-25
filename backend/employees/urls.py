from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"users", views.UserManagementViewSet, basename="user")
router.register(r"departments", views.DepartmentViewSet, basename="department")
router.register(r"profiles", views.EmployeeProfileViewSet, basename="employee-profile")
router.register(r"roles", views.RoleViewSet, basename="role")
router.register(r"activities", views.EmployeeActivityLogViewSet, basename="employee-activity")
router.register(r"notifications", views.EmployeeNotificationViewSet, basename="employee-notification")
router.register(r"documents", views.EmployeeDocumentViewSet, basename="employee-document")

urlpatterns = [
    path("me/", views.MyProfileView.as_view(), name="my-profile"),
    path("me/notifications/", views.MyNotificationsView.as_view(), name="my-notifications"),
    path("department-stats/", views.DepartmentStatsView.as_view(), name="department-stats"),
    path("", include(router.urls)),
]