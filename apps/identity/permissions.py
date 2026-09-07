from rest_framework.permissions import BasePermission


class IsContentManager(BasePermission):
    """Superadmin, or a member of the Campaign managers group."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or user.groups.filter(name="Campaign managers").exists()
            ),
        )
