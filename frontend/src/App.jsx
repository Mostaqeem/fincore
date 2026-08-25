import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import Signup from "./pages/Signup";
import Signin from "./pages/Signin";
import Dashboard from "./pages/Dashboard";
import Finance from "./pages/Finance";
import IT from "./pages/IT";
import RiskManagement from "./pages/RiskManagement";
import Settings from "./pages/Settings";
import ForgotPassword from "./components/ForgotPassword";
import IdleTimer from "./components/IdleTimer";
import { useAuth } from "./context/AuthContext";
import { useNotificationStore } from "./store/notifications";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <p style={{ textAlign: "center", marginTop: 60 }}>Loading...</p>;
  return user ? children : <Navigate to="/signin" />;
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <p style={{ textAlign: "center", marginTop: 60 }}>Loading...</p>;
  if (!user) return <Navigate to="/signin" />;
  return user.is_admin || user.is_staff ? children : <Navigate to="/dashboard" />;
}

function App() {
  const { user } = useAuth();
  const fetchNotifications = useNotificationStore((s) => s.fetchNotifications);
  const connect = useNotificationStore((s) => s.connect);
  const disconnect = useNotificationStore((s) => s.disconnect);

  // Notification socket lifecycle — follows auth state:
  //   - logged in:  fetch bell history + open the live WebSocket
  //   - logged out: close the socket (cleanup runs on unmount/null)
  useEffect(() => {
    if (user) {
      fetchNotifications();
      connect();
    } else {
      disconnect();
    }
    return () => disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  return (
    <>
      {/* Global toast container — toasts arrive via WebSocket events. */}
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
      <IdleTimer />
      <Routes>
      <Route path="/signup" element={<Signup />} />
      <Route path="/signin" element={<Signin />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/finance"
        element={
          <ProtectedRoute>
            <Finance />
          </ProtectedRoute>
        }
      />
      <Route
        path="/it"
        element={
          <ProtectedRoute>
            <IT />
          </ProtectedRoute>
        }
      />
      <Route
        path="/risk-management"
        element={
          <ProtectedRoute>
            <RiskManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <AdminRoute>
            <Settings />
          </AdminRoute>
        }
      />
      <Route path="*" element={<Navigate to="/signin" />} />
      </Routes>
    </>
  );
}

export default App;
