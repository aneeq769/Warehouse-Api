from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsStaffOrReadOnlyForAuthenticated(BasePermission):
    """
    - Anonymous users: GET (list/retrieve) only.
    - Authenticated non-staff: GET only.
    - Staff: full access.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True  # anonymous allowed on safe methods
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
