# URL routes for the notifications app.
#
# Mounted under /api/notifications/ in userconfig/urls.py. Order matters only
# when routes can overlap — `<int:pk>/read/` is specific enough that the
# ordering here doesn't affect routing.
from django.urls import path

from . import views

urlpatterns = [
    # List notifications (optionally ?unread=true). DRF ListAPIView handles
    # pagination (page / page_size) automatically.
    path("", views.NotificationListView.as_view(), name="notification-list"),

    # Just the count — used by the bell badge to poll cheaply.
    path("unread-count/", views.unread_count, name="notification-unread-count"),

    # Mark a single notification as read. 404 if it doesn't belong to the caller.
    path("<int:pk>/read/", views.mark_as_read, name="notification-read"),

    # Mark every unread notification for the user as read.
    path("read-all/", views.mark_all_as_read, name="notification-read-all"),
]