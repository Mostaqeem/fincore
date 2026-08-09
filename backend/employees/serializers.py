from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Department,
    EmployeeActivityLog,
    EmployeeDocument,
    EmployeeNotification,
    EmployeeProfile,
    Role,
    RoleDepartment,
)
from .permissions import all_module_capabilities

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class RoleDepartmentSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = RoleDepartment
        fields = [
            "id",
            "role",
            "role_name",
            "department",
            "department_name",
            "modules",
            "is_active",
        ]


class RoleSerializer(serializers.ModelSerializer):
    department_assignments = RoleDepartmentSerializer(many=True, read_only=True)
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "can_view",
            "can_create",
            "can_edit",
            "can_delete",
            "can_review",
            "can_approve",
            "is_active",
            "capabilities",
            "department_assignments",
        ]

    def get_capabilities(self, obj):
        return obj.capabilities_list()


class RoleDepartmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleDepartment
        fields = ["role", "department", "modules", "is_active"]

    def validate_modules(self, value):
        allowed = set(RoleDepartment.MODULES)
        for module in value:
            if module not in allowed:
                raise serializers.ValidationError(
                    f"Invalid module '{module}'. Allowed: {', '.join(sorted(allowed))}."
                )
        return value


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "is_verified"]


class UserAdminSerializer(serializers.ModelSerializer):
    """Admin-facing user record with employee profile info."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    has_profile = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "is_verified",
            "is_staff",
            "has_profile",
            "employee",
            "roles",
        ]

    def get_has_profile(self, obj):
        return hasattr(obj, "employee_profile")

    def get_roles(self, obj):
        profile = getattr(obj, "employee_profile", None)
        if profile is None:
            return []
        return [r.id for r in profile.roles.all()]

    def get_employee(self, obj):
        profile = getattr(obj, "employee_profile", None)
        if profile is None:
            return None
        return {
            "id": profile.id,
            "employee_id": profile.employee_id,
            "department": profile.department_id,
            "department_name": profile.department.name if profile.department else None,
            "job_title": profile.job_title,
            "employment_type": profile.employment_type,
            "status": profile.status,
        }


def get_profile_roles_and_capabilities(profile):
    """Helper shared by profile serializers: roles + per-module capabilities."""
    roles = [r.id for r in profile.roles.all()]
    capabilities = all_module_capabilities(profile.user)
    return roles, capabilities


class EmployeeProfileSerializer(serializers.ModelSerializer):
    user_details = UserBasicSerializer(source="user", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    manager_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeProfile
        fields = "__all__"
        read_only_fields = ["employee_id", "created_at", "updated_at"]

    def get_manager_name(self, obj):
        if obj.manager:
            return f"{obj.manager.user.get_full_name() or obj.manager.user.email}"
        return None

    def get_roles(self, obj):
        return [r.id for r in obj.roles.all()]

    def get_capabilities(self, obj):
        return all_module_capabilities(obj.user)


class EmployeeSummarySerializer(serializers.ModelSerializer):
    """Lightweight employee payload embedded in the auth user response."""

    department_key = serializers.CharField(source="department.name", read_only=True)
    department_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeProfile
        fields = [
            "employee_id",
            "job_title",
            "employment_type",
            "status",
            "department_key",
            "department_name",
            "roles",
            "capabilities",
        ]

    def get_department_name(self, obj):
        if obj.department:
            return obj.department.get_name_display()
        return None

    def get_roles(self, obj):
        return [r.id for r in obj.roles.all()]

    def get_capabilities(self, obj):
        return all_module_capabilities(obj.user)


class EmployeeActivityLogSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeActivityLog
        fields = "__all__"

    def get_employee_name(self, obj):
        return f"{obj.employee.user.get_full_name() or obj.employee.user.email}"


class EmployeeNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeNotification
        fields = "__all__"
        read_only_fields = ["created_at"]


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeDocument
        fields = "__all__"

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.get_full_name() or obj.uploaded_by.email}"
        return None

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return f"{obj.verified_by.get_full_name() or obj.verified_by.email}"
        return None
