# WebSocket authentication middleware.
#
# Problem: browser JS cannot send an `Authorization: Bearer ...` header on a
# WebSocket connection — the WebSocket API doesn't expose custom headers.
#
# Solution: the client passes the JWT as a query string param when opening
# the socket: `ws://host/ws/notifications/?token=<JWT>`. This middleware
# reads that param, validates the token via SimpleJWT, and attaches the
# resolved user to scope["user"] before the consumer runs.
#
# Note: tokens passed via query strings can end up in access logs / referrer
# headers. For production behind Nginx, strip the `token` query param in
# your proxy logs. Token expiry also means the socket will silently 4401 —
# the React store handles reconnection with a fresh token.
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_key):
    """Resolve a User from a SimpleJWT access token.

    Wrapped in @database_sync_to_async because Django ORM calls are sync,
    but Channels consumers/middleware run on an async event loop. Without
    this wrapper, the DB query would block the loop.

    Returns AnonymousUser on any failure (bad signature, expired, user
    deleted) so the consumer can decide to close the connection.
    """
    try:
        token = AccessToken(token_key)
        # SimpleJWT stores the user id under the "user_id" claim by default.
        return User.objects.get(id=token["user_id"])
    except (TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # scope["query_string"] is bytes (e.g. b"token=abc&foo=bar"). Decode
        # then parse_qs gives us a dict of lists.
        query = parse_qs(scope["query_string"].decode())
        token_key = query.get("token", [None])[0]

        # If no token at all, default to AnonymousUser — the consumer will
        # then close the connection with 4401.
        scope["user"] = (
            await get_user_from_token(token_key)
            if token_key
            else AnonymousUser()
        )

        # Hand off to the next middleware in the stack (eventually the consumer).
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Compatibility shim matching channels' AuthMiddlewareStack naming.

    Use this in asgi.py instead of calling JWTAuthMiddleware directly so
    future middleware additions stack the same way as the built-in helpers.
    """
    return JWTAuthMiddleware(inner)