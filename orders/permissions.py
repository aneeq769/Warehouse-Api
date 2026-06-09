from rest_framework.permissions import BasePermission


class IsOwnerOrStaff(BasePermission):
    """
    Object-level permission: owner can read/cancel their own order.
    Staff can access any order.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.customer == request.user
