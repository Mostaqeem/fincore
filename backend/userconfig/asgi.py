# ASGI config for the userconfig project.
#
# This is the entry point for ASGI servers (Daphne, Uvicorn). It splits
# incoming connections by protocol:
#
#   "http"      → Django's normal ASGI app (REST API, admin, static files).
#   "websocket" → Channel routing. Connections go through:
#                   AllowedHostsOriginValidator  (rejects bad Origin headers)
#                   JWTAuthMiddlewareStack       (parses ?token=... JWT)
#                   URLRouter(websocket_urlpatterns)  (matches path → consumer)
#
# The order in asgi.py matters — middleware wraps the consumer from the
# outside in. AllowedHostsOriginValidator is outermost so it can reject
# connections before we waste time validating a token.
#
# get_asgi_application() MUST be called before importing anything from
# channels.routing / notifications.* — Django's app registry has to be
# ready before channels tries to resolve models / settings.

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "userconfig.settings")

# Initialize Django (loads settings, registers apps). Must run before any
# imports that touch Django models or the channel layer.
django_asgi_app = get_asgi_application()

# Imports below intentionally come AFTER get_asgi_app() — they rely on
# Django being set up.
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from notifications.middleware import JWTAuthMiddlewareStack
from notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # WebSocket connections flow: OriginValidator → JWTAuth → URLRouter
        # → NotificationConsumer (or any future consumer you register).
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)