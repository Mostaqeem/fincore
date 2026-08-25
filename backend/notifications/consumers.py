# WebSocket consumer for the in-app notification bell.
#
# Architecture:
#   - One WebSocket connection per user (the frontend opens it after login).
#   - Each connected user joins a personal channel-layer group named
#     `user_<id>`. Any backend code that wants to push to that user does:
#         channel_layer.group_send(f"user_{user.id}", {...})
#   - This consumer listens for events of type "notification.message" and
#     forwards the payload as JSON over the socket to the browser.
#
# Why a group instead of sending directly to channel_name?
#   The Redis channel layer can fan-out the same event to multiple workers /
#   processes. If the user has 3 tabs open, each tab is its own consumer
#   instance, but they're all members of the same group — so one group_send
#   hits all three.
import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    # Custom close code 4401 mirrors the standard 401 for unauthenticated WS.
    # Browsers don't enforce subprotocol codes, but debugging tools will show it.

    async def connect(self):
        # self.scope["user"] is populated by JWTAuthMiddleware (middleware.py).
        # If the token is missing/invalid, scope["user"] is AnonymousUser.
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        # Group name pattern: "user_<id>". Anything you want to push to this
        # user uses this exact string (see services.notify_user).
        self.group_name = f"user_{user.id}"

        # Join the group. group_add is idempotent — safe to call twice.
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Accept the WebSocket handshake (sends the 101 Switching Protocols).
        await self.accept()

    async def disconnect(self, close_code):
        # Best-effort cleanup. hasattr guard handles the case where connect()
        # bailed out before group_name was set (e.g. unauthenticated close).
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Handler name convention: Channels dispatches based on the event's `type`
    # field. An event sent with type="notification.message" is routed to the
    # method `notification_message` here (dots become underscores).
    async def notification_message(self, event):
        # event["payload"] is whatever services.notify_user() passed to
        # group_send. Wrap it in json.dumps and ship it to the browser.
        await self.send(text_data=json.dumps(event["payload"]))