# notify_user() — the single integration point for sending notifications.
#
# Call this from anywhere (Celery tasks, DRF views, signals, management
# commands) and it will:
#   1. Optionally persist a Notification row in the DB (so it shows up in
#      the bell dropdown history and unread count).
#   2. Push a real-time event over WebSocket to the user's open tabs
#      (toasts, live progress, etc.).
#
# Usage:
#   from notifications.services import notify_user
#   notify_user(user, type="job_completed", title="Done!",
#               message="1200 rows imported", metadata={"job_id": job.id},
#               persist=True)
#
# When to set persist:
#   - True  for terminal / important events (job_completed, job_failed,
#     job_queued) — these belong in the bell history.
#   - False for high-frequency events (job_progress per chunk) — pushing
#     1000 rows/sec to the DB would bloat the table; the WebSocket
#     fan-out is enough for the UI.
#
# Safe to call from:
#   - Sync code (DRF views, signals) — async_to_sync handles the bridge.
#   - Celery workers — group_send via async_to_sync works fine as long as
#     channels_redis points at the same Redis instance as the broker.
#
# The function returns the Notification row (or None if persist=False) so
# callers can chain further actions on it if needed.
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification
from .serializers import NotificationSerializer


def notify_user(user, *, type, title, message="", metadata=None, persist=True):
    # Step 1: persist the row (optional).
    notification = None
    if persist:
        notification = Notification.objects.create(
            user=user,
            type=type,
            title=title,
            message=message,
            metadata=metadata or {},
        )

    # Step 2: build the WebSocket payload.
    #   - When persist=True:  send the full serialized row (includes id,
    #     created_at, is_read) so the frontend can insert it into the
    #     bell list directly.
    #   - When persist=False: send a minimal payload with just the fields
    #     the UI needs (typically title + metadata for live progress).
    payload = {
        # `kind` lets the frontend dispatch on event type if you ever
        # route non-notification messages through the same channel.
        "kind": "notification",
        "data": (
            NotificationSerializer(notification).data
            if notification
            else {
                "type": type,
                "title": title,
                "message": message,
                "metadata": metadata or {},
            }
        ),
    }

    # Step 3: fan-out via the channel layer.
    #   get_channel_layer() reads CHANNEL_LAYERS from settings — make sure
    #   that config is present or this will raise.
    #   async_to_sync is required because group_send is a coroutine and
    #   this function itself is sync.
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        # `type` here becomes the consumer method name (dots → underscores):
        #   "notification.message" → NotificationConsumer.notification_message
        {"type": "notification.message", "payload": payload},
    )
    return notification