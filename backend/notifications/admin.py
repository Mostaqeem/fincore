# Django admin registration for the Notification model.
#
# Useful for debugging during development — lets you inspect rows, mark them
# read manually, or delete stuck notifications without going through the API.
from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    # Columns shown on the changelist.
    list_display = ("id", "user", "type", "title", "is_read", "created_at")

    # Right-sidebar filters.
    list_filter = ("type", "is_read", "created_at")

    # Searchable fields. user__email traverses the FK to match on email.
    search_fields = ("title", "message", "user__email")

    # created_at is auto-set on insert; never editable.
    readonly_fields = ("created_at",)

    # Match the model's default ordering (newest first).
    ordering = ("-created_at",)