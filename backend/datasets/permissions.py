from rest_framework import permissions

from employees.permissions import user_has_capability

MODULE_ALIASES = {
    "risk": "risk",
    "risk-management": "risk",
    "risk_management": "risk",
    "finance": "finance",
    "it": "it",
    "reports": "reports",
}


def resolve_module(section):
    """Normalize a section string (finance/it/risk) to a module key."""
    if not section:
        return None
    return MODULE_ALIASES.get(str(section).lower())


class HasSectionAccess(permissions.BasePermission):
    """
    Grants access based on the dataset section (finance/it/risk) and the
    capability required by the view (`required_capability`, defaults to
    "can_view").

    The section is resolved from the request query param, request body,
    or a `get_section(request)` method on the view.
    """

    message = "You do not have permission to access this section."

    def get_required_capability(self, request, view):
        if hasattr(view, "get_required_capability"):
            return view.get_required_capability(request)
        return getattr(view, "required_capability", "can_view")

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(view, "get_section"):
            section = view.get_section(request)
        else:
            section = request.query_params.get("section") or request.data.get("section")

        module = resolve_module(section)
        capability = self.get_required_capability(request, view)

        if module is None:
            return user_has_capability(request.user, None, capability)

        return user_has_capability(request.user, module, capability)
