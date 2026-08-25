# REST endpoints for the notification bell.
#
# Four routes, all scoped to the authenticated user:
#   GET  /api/notifications/                  → list (optionally ?unread=true)
#   GET  /api/notifications/unread-count/    → { unread_count: N }
#   POST /api/notifications/<id>/read/       → mark one as read
#   POST /api/notifications/read-all/        → mark all as read
#
# Auth comes from the project's default JWT auth class (set in REST_FRAMEWORK
# in settings.py). Anonymous users get 401 from IsAuthenticated.
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """List the authenticated user's notifications, newest first.

    The queryset is already scoped to request.user — never trust client input
    for user identity. Supports pagination out of the box (DRF default).
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Per-user isolation: a user can only ever see their own notifications.
        qs = Notification.objects.filter(user=self.request.user)
        # Optional ?unread=true filter for the bell badge refresh.
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(is_read=False)
        return qs


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_as_read(request, pk):
    """Mark a single notification as read.

    Scoped to request.user via .filter(pk=pk, user=request.user) so a user
    can't mark someone else's notification by guessing the pk (returns 404).
    """
    updated = Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    if not updated:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response({"detail": "marked as read"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_all_as_read(request):
    """Mark every unread notification for the current user as read.

    Bulk .update() issues a single SQL UPDATE — efficient even for users
    with thousands of unread notifications. Returns 200 even if nothing
    matched (idempotent).
    """
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({"detail": "all marked as read"})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    """Return just the unread count for the bell badge.

    Kept as a dedicated endpoint (rather than reading length off the list)
    so the frontend can poll it cheaply without serializing full rows.
    """
    count = Notification.objects.filter(
        user=request.user, is_read=False
    ).count()
    return Response({"unread_count": count})