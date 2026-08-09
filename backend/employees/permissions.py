from rest_framework import permissions


def get_employee_profile(user):
    profile = getattr(user, "employee_profile", None)
    if profile is None:
        return None
    return profile


def get_active_role_assignments(user):
    """Return active RoleDepartment assignments for a user's department."""
    profile = get_employee_profile(user)
    if profile is None or not profile.department_id:
        return []
    role_ids = profile.roles.filter(is_active=True).values_list("id", flat=True)
    return list(profile.department.role_assignments.filter(
        role_id__in=role_ids,
        is_active=True,
    ).select_related("role"))


def user_has_capability(user, module, capability):
    """Can this user perform `capability` for `module` (finance/it/risk/reports)?"""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True

    profile = get_employee_profile(user)
    if profile is None or not profile.is_active_employee():
        return False

    # Viewing a module is implied by having any capability in that module.
    if capability == "can_view":
        return bool(user_module_capabilities(user, module))

    for assignment in get_active_role_assignments(user):
        if module and not assignment.applies_to_module(module):
            continue
        if assignment.role.has_capability(capability):
            return True
    return False


def user_module_capabilities(user, module):
    """List of capability keys granted to the user for `module`."""
    if not user or not user.is_authenticated:
        return []
    if user.is_staff:
        return ["can_view", "can_create", "can_edit", "can_delete", "can_review", "can_approve"]

    profile = get_employee_profile(user)
    if profile is None or not profile.is_active_employee():
        return []

    caps = set()
    for assignment in get_active_role_assignments(user):
        if module and not assignment.applies_to_module(module):
            continue
        caps.update(assignment.role.capabilities_list())
    return sorted(caps)


def all_module_capabilities(user):
    """Map of module -> list of granted capabilities for every module."""
    modules = ["finance", "it", "risk", "reports"]
    return {
        module: user_module_capabilities(user, module)
        for module in modules
    }


class IsEmployeeOrAdmin(permissions.BasePermission):
    """Allow only admin users or verified/active employees."""

    message = "You must be an active employee or admin to access this resource."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        profile = get_employee_profile(user)
        return profile is not None and profile.is_active_employee()


class HasModuleAccess(permissions.BasePermission):
    """
    Enforce module access from Role capabilities.

    The view must declare a `module` attribute and optionally a
    `required_capability` (defaults to "can_view").
    """

    message = "You do not have permission to access this module."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True

        profile = get_employee_profile(user)
        if profile is None or not profile.is_active_employee():
            return False

        module = getattr(view, "module", None) or view.kwargs.get("module", "")
        if not module:
            return False

        capability = getattr(view, "required_capability", "can_view")
        return user_has_capability(user, module, capability)


class IsAdminUser(permissions.BasePermission):
    """Allow only admin (staff) users."""

    message = "Only admins can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_staff
        )
