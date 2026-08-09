from django.contrib import admin
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

User = get_user_model()


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


class RoleDepartmentInline(admin.TabularInline):
    model = RoleDepartment
    extra = 0


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "can_view",
        "can_create",
        "can_edit",
        "can_delete",
        "can_review",
        "can_approve",
        "is_active",
    )
    list_filter = ("is_active", "can_create", "can_review", "can_approve")
    search_fields = ("name", "description")
    inlines = [RoleDepartmentInline]


@admin.register(RoleDepartment)
class RoleDepartmentAdmin(admin.ModelAdmin):
    list_display = ("role", "department", "modules", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("role__name", "department__name")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "user",
        "department",
        "job_title",
        "employment_type",
        "status",
        "is_verified_employee",
    )
    list_filter = ("department", "status", "employment_type", "is_verified_employee")
    search_fields = ("employee_id", "user__email", "user__first_name", "user__last_name", "job_title")
    autocomplete_fields = ("user", "manager")
    raw_id_fields = ("user", "manager")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(employee_profile__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(EmployeeActivityLog)
class EmployeeActivityLogAdmin(admin.ModelAdmin):
    list_display = ("employee", "activity_type", "module", "description", "timestamp")
    list_filter = ("activity_type", "module")
    search_fields = ("employee__user__email", "description")
    readonly_fields = ("employee", "activity_type", "description", "module", "ip_address", "user_agent", "timestamp")


@admin.register(EmployeeNotification)
class EmployeeNotificationAdmin(admin.ModelAdmin):
    list_display = ("employee", "title", "priority", "is_read", "created_at")
    list_filter = ("priority", "is_read")
    search_fields = ("employee__user__email", "title")


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ("employee", "document_type", "title", "is_verified", "upload_date")
    list_filter = ("document_type", "is_verified")
    search_fields = ("employee__user__email", "title")
