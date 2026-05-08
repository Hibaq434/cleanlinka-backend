from rest_framework.permissions import BasePermission


class IsCollector(BasePermission):
    """
    Allows access only to authenticated users with role COLLECTOR.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'COLLECTOR'
        )