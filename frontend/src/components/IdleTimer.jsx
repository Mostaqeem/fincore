import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export const IDLE_TIMEOUT_MS = 300 * 1000;
export const LAST_ACTIVITY_KEY = "last_activity";

const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "click",
  "keydown",
  "keyup",
  "scroll",
  "touchstart",
];

export default function IdleTimer() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const timerRef = useRef(null);
  const lastActivityRef = useRef(Date.now());

  useEffect(() => {
    if (!user) return;

    const persistActivity = () => {
      const now = Date.now();
      lastActivityRef.current = now;
      try {
        localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
      } catch {}
    };

    const fireLogout = () => {
      logout();
      navigate("/signin");
    };

    const checkIdle = () => {
      const idle = Date.now() - lastActivityRef.current;
      if (idle >= IDLE_TIMEOUT_MS) {
        fireLogout();
      } else {
        timerRef.current = setTimeout(checkIdle, IDLE_TIMEOUT_MS - idle);
      }
    };

    const handleActivity = () => persistActivity();

    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      const idle = Date.now() - lastActivityRef.current;
      if (idle >= IDLE_TIMEOUT_MS) {
        fireLogout();
      } else {
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(checkIdle, IDLE_TIMEOUT_MS - idle);
      }
    };

    ACTIVITY_EVENTS.forEach((evt) =>
      window.addEventListener(evt, handleActivity, { passive: true }),
    );
    document.addEventListener("visibilitychange", handleVisibility);

    lastActivityRef.current = Date.now();
    persistActivity();
    timerRef.current = setTimeout(checkIdle, IDLE_TIMEOUT_MS);

    return () => {
      clearTimeout(timerRef.current);
      ACTIVITY_EVENTS.forEach((evt) =>
        window.removeEventListener(evt, handleActivity),
      );
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [user, logout, navigate]);

  return null;
}
