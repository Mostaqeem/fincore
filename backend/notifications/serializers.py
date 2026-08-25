# Serializer for the REST endpoints (bell history, mark-as-read, etc.).
#
# All fields are read-only because:
#   - Notifications are created server-side by services.notify_user()
#   - is_read is toggled via dedicated POST endpoints (mark_as_read / mark_all_as_read),
#     not by PATCH on the list endpoint — this avoids partial-update races.
#
# If you later want clients to PATCH a notification (e.g. soft-delete), drop
# the read_only_fields and add the field to `fields`.
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        # Explicit field list (instead of "__all__") so we never accidentally
        # expose `user` — the queryset already scopes to request.user.
        fields = ["id", "type", "title", "message", "metadata", "is_read", "created_at"]
        read_only_fields = fields