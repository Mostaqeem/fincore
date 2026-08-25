# Notification model — the persistent storage for the in-app notification bell.
#
# Two delivery channels (defined in services.py) write rows here:
#   1. The REST API reads from this table to populate the bell dropdown history.
#   2. The WebSocket consumer pushes events to the browser in real time.
#
# A row is only created when `persist=True` is passed to notify_user(). High-
# frequency events like "job_progress" use persist=False so we don't write a
# row per progress tick (which would bloat the DB).
from django.conf import settings
from django.db import models


class Notification(models.Model):
    # TextChoices centralize the allowed `type` values so any new event kind
    # (e.g. "dataset_approved", "password_changed") is one change here.
    class Types(models.TextChoices):
        JOB_QUEUED    = "job_queued",    "Job Queued"
        JOB_STARTED   = "job_started",   "Job Started"
        JOB_PROGRESS  = "job_progress",  "Job Progress"
        JOB_COMPLETED = "job_completed", "Job Completed"
        JOB_FAILED    = "job_failed",    "Job Failed"
        GENERAL       = "general",       "General"

    # FK to your custom user model (AUTH_USER_MODEL points at accounts.User).
    # CASCADE: deleting a user deletes their notifications.
    # related_name="notifications" lets you do user.notifications.all().
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    # `type` is a CharField + choices (not an FK) because notification kinds
    # are a fixed enum — we never need referential integrity to another table.
    type = models.CharField(
        max_length=32,
        choices=Types.choices,
        default=Types.GENERAL,
    )

    # Short headline shown in the bell dropdown (e.g. "File processed successfully").
    title = models.CharField(max_length=255)

    # Optional longer body text (e.g. "1200 rows imported. 3 errors.").
    message = models.TextField(blank=True)

    # Free-form JSON for arbitrary payload data — job_id, row counts, error
    # samples, download URLs, etc. Consumers on the frontend read this dict.
    metadata = models.JSONField(default=dict, blank=True)

    # Read state. Marked by the mark_as_read / mark_all_as_read endpoints.
    is_read = models.BooleanField(default=False)

    # Set once on insert; never updated. auto_now_add=True means you can't
    # manually override this — if you need to backfill, do it in a migration.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Newest first — the bell dropdown reads this directly.
        ordering = ["-created_at"]

        # Composite indexes tuned to the two queries we run constantly:
        #   (user, is_read)        → unread_count + unread-only list endpoint
        #   (user, -created_at)    → paginated history endpoint
        # If you add new query patterns (e.g. filter by type), add an index here.
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        # Admin / shell display. Includes the type and recipient for debugging.
        return f"[{self.type}] {self.title} -> {self.user}"