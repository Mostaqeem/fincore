# Notifications App — Project Guide

This document explains how the WebSocket + REST notification system works in
this project, end to end. It is written for *this* codebase — not a generic
Django Channels tutorial — so the filenames, model, and conventions all
match what's in `backend/notifications/`.

If you only have 2 minutes, read **"The 30-second mental model"** and
**"Where to add things when you grow"** and you'll be able to navigate
the rest as needed.

---

## The 30-second mental model

There are **two delivery channels** that share one source of truth (the
`Notification` table):

| Channel | What it does | Where it lives |
| --- | --- | --- |
| **REST API** | Persistent history. The bell dropdown fetches this on page load, and marks-as-read go through it. | `views.py` → `urls.py` |
| **WebSocket** | Instant push. Toasts, live progress bars, badge updates — no refresh needed. | `consumers.py` + `routing.py` |

The single integration point that feeds both is:

```
notifications.services.notify_user(...)
```

It's safe to call from any sync code (DRF views, Celery tasks, signals).
It does *either or both*:
1. Persist a `Notification` row (`persist=True`) → shows up in bell history.
2. Push a payload to the user's WebSocket group (`persist=True` *or* `False`) → toast / live progress.

---

## File map

```
backend/notifications/
├── models.py        Notification model (the table). Indexes tuned for the
│                    two queries the bell runs.
├── serializers.py   Read-only DRF serializer (frontend never writes via API).
├── views.py         4 endpoints: list, unread-count, mark-one-read, mark-all-read.
├── urls.py          URL routes mounted under /api/notifications/.
├── admin.py         Django admin registration (for debugging).
│
├── consumers.py     NotificationConsumer — one WS connection per user.
├── middleware.py    JWTAuthMiddleware — reads ?token= from the WS URL,
│                    validates via SimpleJWT, attaches user to scope.
├── routing.py       websocket_urlpatterns — /ws/notifications/ → consumer.
│
└── services.py      notify_user() — the only function you usually call.
                     Persists + pushes in one shot.
```

Plus two files outside this app that wire everything in:

```
backend/userconfig/settings.py    INSTALLED_APPS, ASGI_APPLICATION,
                                  CHANNEL_LAYERS, ALLOWED_HOSTS.
backend/userconfig/asgi.py        ProtocolTypeRouter:
                                  http → Django, websocket → channels stack.
```

---

## End-to-end flow: what happens when `notify_user()` is called

```
┌──────────────────────────┐
│ Celery task / DRF view / │
│ signal / mgmt command    │
└────────────┬─────────────┘
             │
             ▼
   services.notify_user(
       user, type="job_completed",
       title="Done!", persist=True)
             │
             ├──► Notification.objects.create(...)   ─► PostgreSQL
             │                                          (bell history)
             │
             └──► channel_layer.group_send(            ─► Redis
                  f"user_{user.id}",
                  {"type": "notification.message",
                   "payload": {...}})
                                  │
                                  ▼ (Redis pub/sub)
                            Daphne / Channels
                                  │
                                  ▼
              NotificationConsumer.notification_message
                                  │
                                  ▼
              socket.send(text_data=json.dumps(payload))
                                  │
                                  ▼
                          Browser JS (Zustand store)
```

Key thing to notice: **the Redis layer is the bridge between the Celery
worker (or any process) and the WebSocket consumers**. They don't share
memory — only the channel layer's group they publish/subscribe to.

---

## Per-file explanation

### `models.py` — the source of truth

The `Notification` row stores:
- `user` (FK to `accounts.User`, the project's custom user model).
- `type` — enum from `Notification.Types` (job_queued, job_started,
  job_progress, job_completed, job_failed, general). Add a new event kind
  here when you need one.
- `title`, `message` — display text.
- `metadata` — free-form `JSONField` (job_id, row counts, error sample,
  download URL, anything). The frontend reads this dict.
- `is_read`, `created_at` — read state + timestamp.

**Indexes** are tuned to the two queries the bell runs constantly:
- `(user, is_read)` — unread badge / unread-only list.
- `(user, -created_at)` — paginated history.

If you add a new query pattern (e.g. "filter by type for an admin view"),
add a matching composite index in `Meta.indexes`.

`ordering = ["-created_at"]` makes the list endpoint return newest-first
without an explicit `order_by()`.

### `serializers.py`

`NotificationSerializer` exposes every field the frontend needs and **no
others**. All fields are `read_only_fields` because:

- Rows are created server-side by `notify_user()`, never by the API.
- Read state is flipped via dedicated `POST /<id>/read/` and
  `POST /read-all/` endpoints, not by `PATCH` on the list endpoint. This
  avoids partial-update races when the bell dropdown races the WS push.

The `user` field is deliberately **not** exposed — every queryset is
already scoped to `request.user`, so leaking it would be a privacy bug.

### `views.py` — the REST surface

Four function/class views, all wrapped in `IsAuthenticated`:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/notifications/` | List notifications for the caller (paginated by DRF). `?unread=true` filters. |
| `GET /api/notifications/unread-count/` | Returns `{"unread_count": N}` for the badge. |
| `POST /api/notifications/<id>/read/` | Mark one as read. 404 if the row isn't the caller's. |
| `POST /api/notifications/read-all/` | Mark all unread as read (idempotent, single SQL UPDATE). |

Every queryset filters by `request.user`. A user cannot read or mark
another user's notifications, even if they guess an id.

### `consumers.py` — the WebSocket consumer

`NotificationConsumer` is the server-side handler for every WS connection
on `/ws/notifications/`.

Connection lifecycle:
1. `connect()` — `self.scope["user"]` was set by `JWTAuthMiddleware`.
   If it's an `AnonymousUser`, we close with code `4401` and bail.
2. Otherwise, join the channel-layer group named `user_<id>`. Any code
   can later push to this group with:
   ```
   channel_layer.group_send(f"user_{user.id}", {...})
   ```
3. `accept()` — completes the WS handshake (sends `101 Switching Protocols`).
4. `disconnect()` — best-effort cleanup; removes the consumer from the group.

Handler naming convention: Channels dispatches based on the event's
`type` field. An event sent with `type="notification.message"` lands in
the method `notification_message` here. (Dots become underscores.)

### `middleware.py` — JWT auth for WebSockets

**The problem:** the browser JS `WebSocket` API does not let you set
custom headers like `Authorization: Bearer ...`. So we pass the JWT as a
query string: `ws://host/ws/notifications/?token=<JWT>`.

`JWTAuthMiddleware`:
1. Reads `scope["query_string"]` (bytes) and parses it.
2. Extracts `?token=`.
3. Resolves the user via SimpleJWT's `AccessToken` (which gives us the
   `user_id` claim).
4. Sets `scope["user"]` to either the `User` instance or `AnonymousUser`.

The DB lookup is wrapped in `@database_sync_to_async` because Django's ORM
is sync but Channels runs on an async event loop. Without that wrapper,
the ORM call would block the loop.

Production caveat: JWTs in URLs can land in proxy access logs / referrer
headers. Strip the `token` param in your Nginx config if you go to prod,
and rotate tokens regularly.

`JWTAuthMiddlewareStack` is a thin wrapper that mirrors the built-in
`AuthMiddlewareStack` naming, so the asgi.py call site reads naturally.

### `routing.py`

Maps WS paths to consumers. Currently just one route:

```python
re_path(r"ws/notifications/$", NotificationConsumer.as_asgi())
```

Add new WS endpoints here (e.g. `re_path(r"ws/chat/$", ChatConsumer)`).

### `services.py` — the integration point

```python
notify_user(
    user,
    type="job_completed",     # one of Notification.Types values
    title="File processed",
    message="1200 rows imported",
    metadata={"job_id": job.id, "rows_processed": 1200},
    persist=True,             # True = save a row in the bell history
)
```

Behavior:
- **If `persist=True`**: create a `Notification` row, then push the
  full serialized row over the WS so the frontend can drop it into the
  bell list directly (id, created_at, is_read all included).
- **If `persist=False`**: skip the DB write, push a minimal payload
  (type + title + metadata) — used for high-frequency events like
  per-chunk job progress where writing a row per tick would bloat the table.

The push goes through `channel_layer.group_send(...)`, which is async;
we wrap with `async_to_sync(...)` so this function itself can be called
from sync code (Celery, DRF views, signals, shell, mgmt commands).

The function returns the `Notification` instance (or `None` if
`persist=False`) so callers can chain further actions on it.

---

## How `asgi.py` ties it together

```python
django_asgi_app = get_asgi_application()       # MUST come first

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from notifications.middleware import JWTAuthMiddlewareStack
from notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http":      django_asgi_app,
    "websocket": AllowedHostsOriginValidator(   # outermost: rejects bad Origin
                    JWTAuthMiddlewareStack(    # sets scope["user"]
                        URLRouter(websocket_urlpatterns)  # matches path → consumer
                    )
                ),
})
```

Middleware ordering is **outer → inner**, so a request flows:
`AllowedHosts → JWTAuth → URLRouter → Consumer`.

`get_asgi_app()` must run before any `channels.*` or `notifications.*`
import because they touch Django's app registry / settings. The
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", ...)` call before it
makes that possible.

---

## How `settings.py` ties it together

Four additions to `INSTALLED_APPS`:
- `'daphne'` — **must be listed before `django.contrib.staticfiles`**.
  Gives you an ASGI-capable `runserver` in dev.
- `'channels'` — provides `ProtocolTypeRouter`, `URLRouter`, etc.
- `'notifications'` — this app.

One new setting:
- `ASGI_APPLICATION = "userconfig.asgi.application"` — tells Channels
  where the ASGI entrypoint lives.

`CHANNEL_LAYERS` — the Redis-backed transport used by `group_send`. Same
Redis as the Celery broker is fine; they use separate key namespaces.
For a busy app, point at a separate logical DB index
(`redis://127.0.0.1:6379/1`) to keep concerns isolated.

`ALLOWED_HOSTS` — `Channels.websocket.security.AllowedHostsOriginValidator`
checks the WebSocket `Origin` header against this list. In dev with Vite
on `localhost:5173`, you need `localhost` (and `127.0.0.1`) here, or WS
upgrades will be rejected.

---

## How a row reaches the bell dropdown (request/response walk)

1. Frontend logs in, stores `access_token` in `localStorage`.
2. After login, the Zustand store opens:
   ```
   new WebSocket("ws://localhost:8000/ws/notifications/?token=<ACCESS_TOKEN>")
   ```
3. Daphne routes to `ProtocolTypeRouter["websocket"]` → `AllowedHostsOriginValidator`
   passes (origin is localhost) → `JWTAuthMiddleware` reads `?token=`,
   resolves the user, attaches to `scope` → `URLRouter` matches
   `/ws/notifications/` → `NotificationConsumer.connect()`.
4. Consumer checks `scope["user"]` (authenticated), joins group
   `user_<id>`, sends `101 Switching Protocols`.
5. Frontend now also calls `GET /api/notifications/` to populate the bell
   dropdown with history.
6. **Some time later**, a Celery task (or view) calls `notify_user(...)`.
   `services.py` writes to Postgres and/or pushes to Redis.
7. Channels worker reads the message off Redis, finds the consumer's group
   membership, and invokes
   `NotificationConsumer.notification_message(event)`.
8. Consumer does `socket.send(text_data=json.dumps(payload))`.
9. Browser JS receives the JSON, the Zustand store prepends it to the
   bell list and toasts it.

If the user has 3 tabs open, step 7–9 happens three times (each tab is
its own consumer + group member) — that's why we use a group instead of
sending to a single `channel_name`.

---

## Token expiry & reconnect

Access tokens expire (5 minutes by your `SIMPLE_JWT` config). When that
happens:

- The WS connection is **not** proactively closed by the server — it
  just keeps existing with a stale token. New `notify_user` calls still
  reach the consumer.
- When the token expires *and* the browser tries to open a *new* socket
  (e.g. after a tab refresh), `JWTAuthMiddleware` will reject it → the
  consumer's `connect()` closes with `4401`.

Frontend pattern (in the Zustand store):
- On `socket.onclose`, wait a few seconds and reconnect with a freshly
  read `localStorage.getItem("access_token")`. If the user has been idle
  past their refresh-token lifetime, the new socket will fail and the
  app should redirect to `/signin`.
- Optionally: re-fetch `/api/notifications/unread-count/` on reconnect so
  the badge reflects any DB writes that happened while disconnected.

---

## Where to add things when you grow

| You want to... | Edit |
| --- | --- |
| Add a new event type (e.g. `dataset_approved`) | Add it to `Notification.Types` in `models.py`, then use `type="dataset_approved"` in your `notify_user(...)` call. |
| Add a new REST endpoint (e.g. delete a notification) | Add a view in `views.py`, register it in `urls.py`. Keep the queryset scoped to `request.user`. |
| Add a new WebSocket endpoint (e.g. live chat) | Create a new consumer in `consumers.py` (or a new file), add it to `websocket_urlpatterns` in `routing.py`. |
| Switch from Redis to another channel layer (e.g. in-memory for tests) | Override `CHANNEL_LAYERS["default"]` in a test settings module. The `InMemoryChannelLayer` is built into Channels. |
| Add email notification on the same event | After `notify_user(...)`, also enqueue a Celery task that calls `django.core.mail.send_mail(...)`. Or extend `services.py` with an optional `email=True` flag. |
| Auto-delete old notifications | Add a Celery beat task that runs `Notification.objects.filter(created_at__lt=...).delete()` periodically. 90 days is a reasonable default. |
| Add user preferences (mute certain types) | Add a `NotificationPreference` model FK to user; check it inside `notify_user(...)` before persisting / pushing. |

---

## Debugging checklist

1. **WS handshake fails (no 101)** — check `ALLOWED_HOSTS`, check the
   `?token=` is present, check `AccessToken` validity with `python manage.py shell`.
2. **`notify_user` raises `AttributeError: 'NoneType' has no attribute 'group_send'`** — Redis isn't reachable or `CHANNEL_LAYERS` isn't configured. Verify `docker compose up -d redis`.
3. **Toast fires but bell doesn't update** — the consumer is connected
   (WS events arrive) but the REST fetch on login failed; check
   `GET /api/notifications/` directly.
4. **Bell updates but no toast** — the frontend dispatch in the Zustand
   store isn't matching the `type` field. Add a `console.log(payload)` in
   `socket.onmessage`.
5. **`4401` immediately on connect** — JWT is bad / expired / missing
   `user_id` claim. Validate with `python manage.py shell`:
   ```python
   from rest_framework_simplejwt.tokens import AccessToken
   AccessToken("paste-token-here")  # should not raise
   ```
6. **Django `runserver` says "staticfiles" instead of daphne** —
   `daphne` is not first in `INSTALLED_APPS`. Re-check the order.

---

## Glossary

- **Channel layer** — the transport (Redis, in-memory, etc.) that lets
  separate processes talk to each other in real time.
- **Group** — a named pub/sub topic inside the channel layer. Send to a
  group, all its members receive it.
- **Consumer** — the Python class that handles a WebSocket connection.
  Maps 1:1 to one browser tab.
- **Scope** — like `request` but for ASGI. Carries connection metadata
  (headers, query string, path, and `user` once middleware runs).
- **Persist** — the `persist=True` argument to `notify_user`. Controls
  whether a row is written to the `notifications_notification` table.