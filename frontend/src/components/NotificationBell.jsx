// NotificationBell — the bell icon + dropdown shown in the top bar.
//
// Reads state from the notifications store (useNotificationStore) so it
// updates in real time as WebSocket events arrive:
//   - red badge shows the unread count
//   - clicking the bell opens a dropdown listing notifications
//   - clicking a notification marks it as read (dismisses highlight)
//   - "Mark all read" clears the whole list highlight
//
// Styling intentionally mirrors the TopBar / user-dropdown aesthetic
// (white dropdown, soft shadow, fade-in animation, blue accents) — see
// NotificationBell.css.

import { useState, useRef, useEffect } from "react";
import { formatDistanceToNow } from "date-fns";
import { useNotificationStore } from "../store/notifications";
import "./NotificationBell.css";

// Map notification types to Font Awesome icons + a tint color so the
// list is scannable at a glance. Icons match the app's existing icon set.
const TYPE_META = {
  job_completed: { icon: "fa-check-circle", color: "#1a7a3a" },
  job_failed: { icon: "fa-exclamation-circle", color: "#d32f2f" },
  job_queued: { icon: "fa-hourglass-half", color: "#b3802b" },
  job_started: { icon: "fa-play", color: "#3b7bd6" },
  job_progress: { icon: "fa-spinner", color: "#3b7bd6" },
  general: { icon: "fa-bell", color: "#5e7499" },
};

function typeMeta(type) {
  return TYPE_META[type] || TYPE_META.general;
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Subscribe to the store. Selectors keep re-renders scoped to the
  // fields this component actually reads.
  const notifications = useNotificationStore((s) => s.notifications);
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const markAsRead = useNotificationStore((s) => s.markAsRead);
  const markAllAsRead = useNotificationStore((s) => s.markAllAsRead);

  // Close the dropdown when the user clicks anywhere outside it.
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // "Mark all read" closes nothing — it keeps the dropdown open so the
  // user sees the list flatten to read state. Opening a notification
  // marks it read but keeps the list open for quick triage.
  const handleItemClick = (n) => {
    if (!n.is_read) markAsRead(n.id);
  };

  return (
    <div className="notification-bell" ref={ref}>
      <button
        className={`notification-bell__button ${open ? "active" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        aria-expanded={open}
      >
        <i className="fas fa-bell"></i>
        {unreadCount > 0 && (
          <span className="notification-bell__badge">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notification-bell__panel">
          <div className="notification-bell__header">
            <span>Notifications</span>
            {unreadCount > 0 && (
              <button
                className="notification-bell__mark-all"
                onClick={markAllAsRead}
              >
                Mark all read
              </button>
            )}
          </div>

          {notifications.length === 0 ? (
            <div className="notification-bell__empty">
              <i className="fas fa-bell-slash"></i>
              <p>No notifications yet.</p>
            </div>
          ) : (
            <ul className="notification-bell__list">
              {notifications.map((n) => {
                const meta = typeMeta(n.type);
                return (
                  <li
                    key={n.id}
                    className={`notification-bell__item ${n.is_read ? "is-read" : ""}`}
                    onClick={() => handleItemClick(n)}
                  >
                    <span
                      className="notification-bell__item-icon"
                      style={{ color: meta.color }}
                    >
                      <i className={`fas ${meta.icon}`}></i>
                    </span>
                    <div className="notification-bell__item-body">
                      <p className="notification-bell__item-title">{n.title}</p>
                      {n.message && (
                        <p className="notification-bell__item-message">{n.message}</p>
                      )}
                      <p className="notification-bell__item-time">
                        {formatDistanceToNow(new Date(n.created_at), {
                          addSuffix: true,
                        })}
                      </p>
                    </div>
                    {!n.is_read && (
                      <span className="notification-bell__item-dot"></span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}