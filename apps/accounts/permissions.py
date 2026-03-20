from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Only users with role=admin can access."""
    message = "You do not have admin privileges."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin
        )


class IsOwnerOrAdmin(BasePermission):
    """Object-level: only the owner or an admin can access."""
    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        # obj could be a User or any model with a .user field
        if hasattr(obj, "user"):
            return obj.user == request.user
        return obj == request.user