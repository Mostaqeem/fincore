# Notification System — Known Bugs & Issues

During implementation, the following bugs and issues were encountered and
resolved. This file serves as a reference for future debugging.

---

## Bug 1: channels_redis TimeoutError with redis 8.0.1

**Symptom:**
```
redis.exceptions.TimeoutError: Timeout reading from 127.0.0.1:6379
WebSocket DISCONNECT /ws/notifications/
WebSocket HANDSHAKING /ws/notifications/
WebSocket CONNECT /ws/notifications/
```

**Root cause:**
`channels_redis 4.3.0` has an incompatibility with `redis-py 8.0.1`. The
async connection pool used by channels_redis times out reading responses
from Redis, even though Redis itself is running and responsive to both
sync and async ping commands.

**How to reproduce:**
- Install `channels_redis==4.3.0` and `redis==8.0.1`
- Start Redis (`docker compose up -d redis`)
- Attempt a WebSocket connection to `/ws/notifications/`

**Fix:**
Pin `redis` to a version compatible with `channels_redis 4.3.0`:
```
redis==5.0.1
```
Then reinstall dependencies:
```
pip install -r requirements.txt
```

**Verification:**
```python
python -c "
import redis.asyncio as aioredis
import asyncio
async def test():
    r = aioredis.Redis(host='127.0.0.1', port=6379)
    print(await r.ping())
    await r.aclose()
asyncio.run(test())
"
```
If this returns `True`, the async Redis connection works and channels_redis
should connect successfully.

---

## Bug 2: Missing notifications in review/approval/rejection workflow

**Symptom:**
When a user rejected, reviewed, or approved a table through the web
interface, no notification was pushed to any user — neither a toast nor a
bell history entry appeared.

**Root cause:**
The `datasets/views.py` file was never updated to call `notify_user()` when
these operations occurred. Only `UploadView.post` had a `notify_user` call
(from Phase 3).

**Missing notifications (5 views):**

| View | What happens | Was missing |
|---|---|---|
| `SubmitView.post` | Creator submits table for review | `review_submitted` notification |
| `StartReviewView.post` | Reviewer begins reviewing | `review_started` notification |
| `ReviewApproveView.post` | Reviewer approves the review | `review_approved` notification |
| `ApproveView.post` | Final approval confirmed | `table_approved` notification |
| `RejectView.post` | Reviewer/approver rejects table | `table_rejected` notification |

**Fix:**
Added `notify_user()` calls to each of the 5 views in `datasets/views.py`.
Initially used `request.user` as the recipient, but this was later
corrected (see Bug 3).

**Files modified:**
- `backend/datasets/views.py` — added `notify_user()` calls after each
  status change and `dataset.save()`

---

## Bug 3: Incorrect notification recipients

**Symptom:**
After Bug 2 was fixed, notifications were being sent to `request.user`
(the person performing the action — the reviewer/approver), but the user
wanted notifications to go to other people who have permission to the
table, not the actor.

**User's requirement:**
> "The current user who is logged in the one who is reviewing or approving
> or creating the table I don't think he needs to be notified. He knows
> what he is doing the others should be notified. Who specifically has
> permission to the table."

**Root cause:**
The initial fix used `notify_user(request.user, ...)` which notifies the
actor themselves. The user clarified that:
- The actor does not need a notification (they already know their action)
- The creator (`dataset.created_by`) should be notified instead
- Other users with review/approve permissions should also be notified

**Challenge: Duplicated notification logic across views**

The first pass added inline notification code to all 5 views. Each view
duplicated the same pattern:

```python
from employees.permissions import user_has_capability
from django.contrib.auth import get_user_model

User = get_user_model()
interested_users = User.objects.filter(is_active=True).exclude(id=request.user.id)
for user in interested_users:
    if user_has_capability(user, dataset.section, 'can_review') or \
       user_has_capability(user, dataset.section, 'can_approve'):
        notify_user(
            user,
            type="review_submitted",
            title=f"Table submitted for review: {dataset.name}",
            metadata={"dataset_id": str(dataset.id)},
            persist=True,
        )
```

This was repeated in `SubmitView`, `StartReviewView`, `ReviewApproveView`,
and `ApproveView` — with only the `type` and `title` changing each time.
This violates DRY and makes future changes error-prone.

Additionally, `RejectView` had a separate bug: it only notified the
rejector (`request.user`) — the person who rejected the table. The table
creator was never told their table was rejected, and other reviewers had
no idea the workflow ended.

**Fix: Reusable helper function**

Extracted a single helper `views.py:41-58`:

```python
def _notify_interested_users(exclude_user, dataset, notification_type, title, metadata=None):
    """Notify all active users with review/approve permission for a dataset's section."""
    User = get_user_model()
    meta = {"dataset_id": str(dataset.id), "section": dataset.section}
    if metadata:
        meta.update(metadata)

    interested_users = User.objects.filter(is_active=True).exclude(id=exclude_user.id)
    for user in interested_users:
        if user_has_capability(user, dataset.section, 'can_review') or \
           user_has_capability(user, dataset.section, 'can_approve'):
            notify_user(
                user,
                type=notification_type,
                title=title,
                metadata=meta,
                persist=True,
            )
```

Key design decisions in the helper:
1. **`exclude_user` is required** — forces the caller to think about who
   should NOT receive the notification (the actor)
2. **`dataset_id` and `section` are always in metadata** — no caller
   forgets to include them
3. **`metadata` is optional** — callers can pass extra context like
   `{"comment": "..."}` which gets merged in
4. **`persist=True` by default** — every notification is saved to the DB
   for the bell icon history

**Refactored views (each lost ~10 lines):**

```python
# Before (in SubmitView, StartReviewView, etc.)
from employees.permissions import user_has_capability
from django.contrib.auth import get_user_model
User = get_user_model()
interested_users = User.objects.filter(is_active=True).exclude(id=request.user.id)
for user in interested_users:
    if user_has_capability(user, dataset.section, 'can_review') or \
       user_has_capability(user, dataset.section, 'can_approve'):
        notify_user(user, type=..., title=..., metadata=..., persist=True)

# After (in all 4 views)
_notify_interested_users(
    exclude_user=request.user,
    dataset=dataset,
    notification_type="review_submitted",
    title=f"Table submitted for review: {dataset.name}",
)
```

**RejectView fix (two notification calls):**

The rejector was only notifying themselves. Fixed to:

```python
# 1. Notify the table creator so they know their table was rejected.
if dataset.created_by:
    notify_user(
        dataset.created_by,
        type="table_rejected",
        title=f"Table rejected: {dataset.name}",
        metadata=rejection_meta,
        persist=True,
    )

# 2. Notify other reviewers/approvers so they know the workflow ended.
_notify_interested_users(
    exclude_user=request.user,
    dataset=dataset,
    notification_type="table_rejected",
    title=f"Table rejected: {dataset.name}",
    metadata=rejection_meta,
)
```

The creator gets a direct `notify_user()` call (not the helper) because
the helper always excludes one user — but the creator should always be
notified regardless of whether they have `can_review`/`can_approve`.

**Final per-view recipient rules:**

| View | Who is notified | How |
|---|---|---|
| `SubmitView.post` | Reviewers/approvers for the section, excluding submitter | `_notify_interested_users` |
| `StartReviewView.post` | Other reviewers/approvers, excluding the reviewer | `_notify_interested_users` |
| `ReviewApproveView.post` | Other reviewers/approvers, excluding the reviewer | `_notify_interested_users` |
| `ApproveView.post` | Other reviewers/approvers, excluding the approver | `_notify_interested_users` |
| `RejectView.post` | **Table creator** + other reviewers/approvers, excluding rejector | Direct call + `_notify_interested_users` |

**Imports moved to top of file:**

`get_user_model` and `user_has_capability` were previously imported inside
each view function (lazy imports). Moved to the top of `views.py` — this
is standard Python practice (PEP 8) and avoids repeated import overhead.

---

## Bug 4: Redis sync PING works but async channels_redis times out

**Symptom:**
- `redis-cli ping` returns `PONG` ✅
- `redis.Redis(host='127.0.0.1', port=6379).ping()` returns `True` ✅
- `redis.asyncio.Redis(host='127.0.0.1', port=6379).ping()` returns `True` ✅
- `channels_redis.RedisChannelLayer` times out ❌

**Root cause:**
`channels_redis 4.3.0` creates its own connection pool with internal
timeout configurations that conflict with `redis-py 8.0.1`'s async
protocol changes. The direct async ping works because it uses a simpler
code path, while channels_redis's pool management triggers the timeout.

**This is a version compatibility issue, not a Redis availability issue.**
Even when Redis is confirmed running and accessible, channels_redis can
still time out if the version mismatch is present.

**Fix:** Same as Bug 1 — pin `redis==5.0.1`.

---

## Prevention Checklist

Before deploying or updating the notification system:

1. **Verify Redis version compatibility:**
   ```
   pip show redis channels_redis
   ```
   - `redis` should be `>=4.6.0` and `<8.0.0` for `channels_redis 4.3.x`
   - Or upgrade `channels_redis` to `>=5.0.0` to support `redis 8.x`

2. **Test WebSocket connectivity:**
   ```python
   from channels.testing import WebsocketCommunicator
   from userconfig.asgi import application
   # Should connect without TimeoutError
   ```

3. **Verify notifications in all workflow views:**
   ```
   grep -n "notify_user\|_notify_interested_users" datasets/views.py
   ```
   Confirm all 6 workflow views (Upload + 5 review workflow) have
   notification calls. The 5 review workflow views should use
   `_notify_interested_users` (not inline code). `RejectView` should
   have TWO calls: one direct to the creator, one via the helper.

4. **Verify notification recipients:**
   - `request.user` should NOT be the recipient in review workflow views
   - `dataset.created_by` should be notified on rejection (direct call)
   - Users with `can_review`/`can_approve` permissions should be
     notified via `_notify_interested_users`

5. **Check channels layer health:**
   ```python
   from channels.layers import get_channel_layer
   layer = get_channel_layer()
   print(layer)  # Should not be None
   ```
