# WebSocket URL routing for the notifications app.
#
# This file is imported by userconfig/asgi.py and registered under the
# "websocket" protocol in ProtocolTypeRouter. Each pattern here becomes a
# WebSocket endpoint the browser can connect to.
#
# URL convention:
#   - Path: /ws/notifications/   (frontend uses this verbatim)
#   - Query: ?token=<JWT>        (consumed by JWTAuthMiddleware)
#
# If you add another consumer (e.g. live chat), add a new re_path here:
#   re_path(r"ws/chat/$", ChatConsumer.as_asgi()),
from django.urls import re_path

from .consumers import NotificationConsumer

websocket_urlpatterns = [
    # re_path (not path) because Channels' URLRouter uses regex patterns.
    # Trailing $ prevents accidental prefix matches like /ws/notifications/extra/.
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
]