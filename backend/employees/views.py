from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model

from .models import (
    Department,
    EmployeeActivityLog,
    EmployeeDocument,
    EmployeeNotification,
    EmployeeProfile,
    Role,
    RoleDepartment,
)
from .permissions import (
    IsAdminUser,
    IsEmployeeOrAdmin,
    get_employee_profile,
)
from .serializers import (
    DepartmentSerializer,
    EmployeeActivityLogSerializer,
    EmployeeDocumentSerializer,
    EmployeeNotificationSerializer,
    EmployeeProfileSerializer,
    RoleDepartmentSerializer,
    RoleDepartmentWriteSerializer,
    RoleSerializer,
    UserAdminSerializer,
)

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

User = get_user_model()


class UserManagementViewSet(viewsets.ModelViewSet):
    """Admin-only management of user accounts and their employee profiles."""

    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminUser]
    EDITABLE_FIELDS = {"first_name", "last_name", "is_active", "is_verified", "is_staff"}
    queryset = User.objects.select_related(
        "employee_profile", "employee_profile__department"
    ).order_by("-date_joined")

    def create(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        """Allow updating only the whitelisted fields (email is immutable)."""
        data = {
            key: value
            for key, value in request.data.items()
            if key in self.EDITABLE_FIELDS
        }
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsEmployeeOrAdmin()]
        return [IsAdminUser()]


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    queryset = EmployeeProfile.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeProfileSerializer
    filterset_fields = ["department", "status", "employment_type"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return self.queryset.none()
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(user=user)

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        profile = serializer.save()
        self.apply_roles(profile)

    def perform_update(self, serializer):
        profile = serializer.save()
        self.apply_roles(profile)

    def apply_roles(self, profile):
        role_ids = self.request.data.get("roles")
        if role_ids is None:
            return
        valid_ids = Role.objects.filter(id__in=role_ids).values_list("id", flat=True)
        profile.roles.set(list(valid_ids))


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related(
        "department_assignments", "department_assignments__department"
    ).all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == "departments":
            return RoleDepartmentWriteSerializer
        return RoleSerializer

    @action(detail=True, methods=["get", "post", "delete"])
    def departments(self, request, pk=None):
        role = self.get_object()
        if request.method == "GET":
            assignments = role.department_assignments.select_related("department").all()
            return Response(RoleDepartmentSerializer(assignments, many=True).data)

        if request.method == "POST":
            serializer = RoleDepartmentWriteSerializer(
                data={**request.data, "role": role.id}
            )
            serializer.is_valid(raise_exception=True)
            assignment, created = RoleDepartment.objects.update_or_create(
                role=role,
                department=serializer.validated_data["department"],
                defaults={
                    "modules": serializer.validated_data.get("modules", []),
                    "is_active": serializer.validated_data.get("is_active", True),
                },
            )
            return Response(
                RoleDepartmentSerializer(assignment).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        assignment_id = request.query_params.get("assignment_id")
        assignment = RoleDepartment.objects.filter(
            pk=assignment_id, role=role
        ).first()
        if assignment is None:
            return Response(
                {"error": "Assignment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmployeeActivityLog.objects.select_related("employee__user").all()
    serializer_class = EmployeeActivityLogSerializer
    permission_classes = [IsAdminUser]


class EmployeeNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeNotificationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            queryset = EmployeeNotification.objects.all()
            employee_id = self.request.query_params.get("employee")
            if employee_id:
                queryset = queryset.filter(employee_id=employee_id)
            return queryset
        profile = get_employee_profile(user)
        if profile is None:
            return EmployeeNotification.objects.none()
        return EmployeeNotification.objects.filter(employee=profile)

    def perform_create(self, serializer):
        profile = get_employee_profile(self.request.user)
        serializer.save(employee=profile)


class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeDocumentSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return EmployeeDocument.objects.select_related(
                "employee__user", "uploaded_by", "verified_by"
            ).all()
        profile = get_employee_profile(user)
        if profile is None:
            return EmployeeDocument.objects.none()
        return EmployeeDocument.objects.filter(employee=profile)


class MyProfileView(APIView):
    """Richer profile payload for the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = get_employee_profile(user)
        profile_data = EmployeeProfileSerializer(profile).data if profile else None

        return Response({
            "is_admin": user.is_staff or user.is_superuser,
            "is_employee": profile is not None,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_verified": user.is_verified,
            },
            "profile": profile_data,
        })


class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_employee_profile(request.user)
        if profile is None:
            return Response({"notifications": [], "unread_count": 0})

        queryset = EmployeeNotification.objects.filter(employee=profile)
        serializer = EmployeeNotificationSerializer(queryset, many=True)
        return Response({
            "notifications": serializer.data,
            "unread_count": queryset.filter(is_read=False).count(),
        })

    def post(self, request):
        profile = get_employee_profile(request.user)
        if profile is None:
            return Response({"error": "No employee profile"}, status=status.HTTP_404_NOT_FOUND)

        notification_id = request.data.get("notification_id")
        if notification_id:
            notification = EmployeeNotification.objects.filter(
                id=notification_id, employee=profile
            ).first()
            if not notification:
                return Response(
                    {"error": "Notification not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            notification.mark_as_read()
            return Response({"success": True, "id": notification.id})

        queryset = EmployeeNotification.objects.filter(employee=profile, is_read=False)
        updated = queryset.update(is_read=True, read_at=None)
        return Response({"success": True, "marked_read": updated})
