// Notifications store — WebSocket-driven real-time + REST history.
//
// Responsibilities:
//   1. Hold the bell state: notifications list, unread count, WS status.
//   2. Fetch the user's notification history from REST on connect.
//   3. Open a WebSocket to /ws/notifications/?token=<JWT> and dispatch
//      incoming events into the store + bell badge.
//   4. Auto-reconnect with backoff on disconnect.
//   5. Mark individual notifications as read via the REST endpoint.
//
// Consumed by:
//   - NotificationBell.jsx (renders the list and badge)
//   - App.jsx (calls connect/disconnect on auth changes)
//
// The WebSocket URL is hardcoded to localhost:8000 because the React dev
// server (Vite, port 5173) and the Django backend are on different
// origins — `window.location.host` would point at Vite, not Daphne.

import { create } from "zustand";
import toast from "react-hot-toast";
import api from "../axiosconfig";

const WS_URL = "ws://localhost:8000/ws/notifications/";

// Map notification types → toast styling. Persistent types (job_completed,
// job_failed, etc.) already get a toast; transient job_progress is
// handled separately because it's high-frequency.
const TOAST_BY_TYPE = {
  job_completed: (data) => toast.success(data.title),
  job_failed: (data) => toast.error(data.title),
  job_queued: (data) => toast(data.title, { icon: "⏳" }),
  job_started: (data) => toast(data.title, { icon: "▶️" }),
};

export const useNotificationStore = create((set, get) => ({
  // ---------- state ----------
  notifications: [],
  unreadCount: 0,
  connected: false,
  socket: null,
  // progress[jobId] = { current, total, percent, phase } — only set by
  // job_progress events (high-frequency; not persisted to the bell).
  progress: {},

  // ---------- actions ----------

  // Fetch the user's notification history from REST and prime the bell.
  // Called once after login / on socket reconnect.
  fetchNotifications: async () => {
    try {
      const { data } = await api.get("/notifications/");
      set({
        notifications: data,
        unreadCount: data.filter((n) => !n.is_read).length,
      });
    } catch (err) {
      // Non-fatal — the bell will simply show empty until a successful
      // fetch. The WS may still deliver new events in the meantime.
      console.warn("Failed to fetch notifications:", err);
    }
  },

  // Open the WebSocket. Safe to call repeatedly — no-ops if already open
  // or if the user isn't authenticated.
  connect: () => {
    const token = localStorage.getItem("access_token");
    if (!token || get().socket) return;

    const socket = new WebSocket(`${WS_URL}?token=${token}`);

    socket.onopen = () => set({ connected: true });

    socket.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return; // ignore non-JSON frames
      }

      // Only handle "notification" frames; ignore anything else the
      // channel layer might be used for in the future.
      if (payload?.kind !== "notification") return;
      const data = payload.data;
      if (!data?.type) return;

      // job_progress is high-frequency — don't toast, don't add to the
      // bell list. Just stash in the progress map for live progress bars.
      if (data.type === "job_progress") {
        const jobId = data.metadata?.job_id;
        if (jobId) {
          set((state) => ({
            progress: { ...state.progress, [jobId]: data.metadata },
          }));
        }
        return;
      }

      // Terminal/persisted event — toast and prepend to bell list.
      const toastFn = TOAST_BY_TYPE[data.type];
      if (toastFn) {
        toastFn(data);
      } else {
        toast(data.title || "Notification");
      }

      set((state) => ({
        notifications: [data, ...state.notifications],
        unreadCount: state.unreadCount + 1,
      }));
    };

    socket.onclose = () => {
      set({ socket: null, connected: false });
      // Auto-reconnect with backoff. We re-read the token each time so
      // a refresh issued in another tab takes effect on the next attempt.
      setTimeout(() => {
        if (localStorage.getItem("access_token")) {
          get().connect();
        }
      }, 3000);
    };

    socket.onerror = (e) => {
      // Errors are followed by onclose, so we just log here.
      console.warn("Notification socket error:", e);
    };

    set({ socket });
  },

  // Close the WebSocket. Called on logout.
  disconnect: () => {
    const { socket } = get();
    if (socket) {
      socket.onclose = null; // suppress the reconnect-on-close path
      socket.close();
    }
    set({
      socket: null,
      connected: false,
      notifications: [],
      unreadCount: 0,
      progress: {},
    });
  },

  // Mark a single notification as read (optimistic update).
  markAsRead: async (id) => {
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, is_read: true } : n
      ),
      unreadCount: Math.max(0, state.unreadCount - 1),
    }));
    try {
      await api.post(`/notifications/${id}/read/`);
    } catch (err) {
      // Roll back on failure.
      console.warn("Failed to mark as read:", err);
      set((state) => ({
        notifications: state.notifications.map((n) =>
          n.id === id ? { ...n, is_read: false } : n
        ),
        unreadCount: state.unreadCount + 1,
      }));
    }
  },

  // Mark every unread notification as read (optimistic update).
  markAllAsRead: async () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, is_read: true })),
      unreadCount: 0,
    }));
    try {
      await api.post("/notifications/read-all/");
    } catch (err) {
      console.warn("Failed to mark all as read:", err);
    }
  },
}));