from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Department(models.Model):
    """Department model for organizing employees and permissions"""

    class DepartmentType(models.TextChoices):
        FINANCE = "FINANCE", "Finance"
        IT = "IT", "Information Technology"
        RISK = "RISK", "Risk Management"
        HR = "HR", "Human Resources"
        LEGAL = "LEGAL", "Legal"
        COMPLIANCE = "COMPLIANCE", "Compliance"
        OPERATIONS = "OPERATIONS", "Operations"
        EXECUTIVE = "EXECUTIVE", "Executive"

    name = models.CharField(max_length=50, choices=DepartmentType.choices, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return self.get_name_display()


class EmployeeProfile(models.Model):
    """Extended employee information linked to the User model"""

    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full Time"
        PART_TIME = "PART_TIME", "Part Time"
        CONTRACT = "CONTRACT", "Contract"
        INTERN = "INTERN", "Intern"
        EXECUTIVE = "EXECUTIVE", "Executive"

    class EmployeeStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        ON_LEAVE = "ON_LEAVE", "On Leave"
        TERMINATED = "TERMINATED", "Terminated"
        PROBATION = "PROBATION", "Probation"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )

    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    job_title = models.CharField(max_length=100)
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE,
    )

    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="USA")
    postal_code = models.CharField(max_length=20, blank=True)

    date_of_hire = models.DateField(null=True, blank=True)
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subordinates",
    )

    is_verified_employee = models.BooleanField(default=False)
    has_nda_signed = models.BooleanField(default=False)
    has_security_clearance = models.BooleanField(default=False)
    security_clearance_level = models.CharField(
        max_length=20,
        choices=[
            ("NONE", "None"),
            ("BASIC", "Basic"),
            ("CONFIDENTIAL", "Confidential"),
            ("SECRET", "Secret"),
            ("TOP_SECRET", "Top Secret"),
        ],
        default="NONE",
    )

    roles = models.ManyToManyField(
        "Role",
        related_name="employees",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_id"]
        verbose_name = "Employee Profile"
        verbose_name_plural = "Employee Profiles"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - {self.employee_id}"

    def save(self, *args, **kwargs):
        if not self.employee_id:
            self.employee_id = self.generate_employee_id()
        super().save(*args, **kwargs)

    def generate_employee_id(self):
        import random
        import string

        year = timezone.now().year
        prefix = f"EMP-{year}-"
        existing_ids = EmployeeProfile.objects.filter(
            employee_id__startswith=prefix
        ).values_list("employee_id", flat=True)

        if existing_ids:
            numbers = [int(id.split("-")[-1]) for id in existing_ids]
            next_number = max(numbers) + 1
        else:
            next_number = 1

        return f"{prefix}{str(next_number).zfill(4)}"

    def clean(self):
        if self.date_of_hire and self.date_of_hire > timezone.now().date():
            raise ValidationError("Date of hire cannot be in the future")
        if self.manager and self.manager == self:
            raise ValidationError("An employee cannot be their own manager")

    def is_active_employee(self):
        """ACTIVE and PROBATION employees are allowed into the system."""
        return self.status in (
            self.EmployeeStatus.ACTIVE,
            self.EmployeeStatus.PROBATION,
        )

    def is_terminated(self):
        return self.status == self.EmployeeStatus.TERMINATED

    def can_access_sensitive_data(self):
        return self.is_verified_employee and self.has_security_clearance


class Role(models.Model):
    """Custom role with a set of capabilities, e.g. creator, reviewer, approver."""

    CAPABILITY_FIELDS = [
        "can_view",
        "can_create",
        "can_edit",
        "can_delete",
        "can_review",
        "can_approve",
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    can_view = models.BooleanField(default=True)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_review = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name

    def has_capability(self, capability):
        if not self.is_active:
            return False
        attr = f"can_{capability}" if not capability.startswith("can_") else capability
        if not hasattr(self, attr):
            return False
        return bool(getattr(self, attr))

    def capabilities_list(self):
        """List of capability keys this role grants."""
        return [cap for cap in self.CAPABILITY_FIELDS if getattr(self, cap)]


class RoleDepartment(models.Model):
    """Scope a role to a department and the modules it applies to.

    A user in `department` holding `role` gets the role's capabilities for the
    modules listed in `modules`.
    """

    MODULES = ["finance", "it", "risk", "reports"]

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="department_assignments",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    modules = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["role", "department"]
        verbose_name = "Role Department"
        verbose_name_plural = "Role Departments"

    def __str__(self):
        return f"{self.role.name} - {self.department.name}"

    def applies_to_module(self, module):
        return str(module).lower() in self.modules


class EmployeeActivityLog(models.Model):
    """Track employee activities for audit purposes"""

    class ActivityType(models.TextChoices):
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"
        VIEW = "VIEW", "View"
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        APPROVE = "APPROVE", "Approve"
        REJECT = "REJECT", "Reject"
        DOWNLOAD = "DOWNLOAD", "Download"
        EXPORT = "EXPORT", "Export"

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    description = models.TextField()
    module = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Employee Activity Log"
        verbose_name_plural = "Employee Activity Logs"

    def __str__(self):
        return f"{self.employee} - {self.activity_type} - {self.timestamp}"


class EmployeeNotification(models.Model):
    """Notifications for employees"""

    class NotificationPriority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.MEDIUM,
    )
    is_read = models.BooleanField(default=False)
    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Employee Notification"
        verbose_name_plural = "Employee Notifications"

    def __str__(self):
        return f"{self.employee} - {self.title}"

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class EmployeeDocument(models.Model):
    """Store documents related to employees (NDA, contracts, etc.)"""

    class DocumentType(models.TextChoices):
        NDA = "NDA", "NDA Agreement"
        CONTRACT = "CONTRACT", "Employment Contract"
        OFFER_LETTER = "OFFER_LETTER", "Offer Letter"
        ID_PROOF = "ID_PROOF", "Identity Proof"
        ADDRESS_PROOF = "ADDRESS_PROOF", "Address Proof"
        COMPLIANCE = "COMPLIANCE", "Compliance Document"
        OTHER = "OTHER", "Other"

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="employee_documents/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_documents",
    )
    upload_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_documents",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-upload_date"]
        verbose_name = "Employee Document"
        verbose_name_plural = "Employee Documents"

    def __str__(self):
        return f"{self.employee} - {self.document_type} - {self.title}"
