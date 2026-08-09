import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Sidebar.css";

function Sidebar({ activePage }) {
  const location = useLocation();
  const { user } = useAuth();

  const isAdmin = user?.is_admin || user?.is_staff || false;

  const isActive = (path) => {
    if (activePage) return activePage === path;
    return location.pathname === path;
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <i className="fas fa-bolt"></i>
        <span>FinCore</span>
      </div>
      <div className="sidebar-menu">
        <div className="menu-label">Main</div>
        <Link to="/dashboard" className={`menu-item ${isActive("/dashboard") ? "active" : ""}`}>
          <i className="fas fa-chart-pie"></i>
          <span>Dashboard</span>
        </Link>
        <Link to="/finance" className={`menu-item ${isActive("/finance") ? "active" : ""}`}>
          <i className="fas fa-coins"></i>
          <span>Finance</span>
        </Link>
        <Link to="/it" className={`menu-item ${isActive("/it") ? "active" : ""}`}>
          <i className="fas fa-server"></i>
          <span>IT</span>
        </Link>
        <Link to="/risk-management" className={`menu-item ${isActive("/risk-management") ? "active" : ""}`}>
          <i className="fas fa-shield-alt"></i>
          <span>Risk Management</span>
        </Link>
        <div className="menu-item" style={{cursor: 'not-allowed', opacity: 0.6}}>
          <i className="fas fa-file-invoice"></i>
          <span>Reports</span>
        </div>
        <div className="menu-label">Insights</div>
        <div className="menu-item" style={{cursor: 'not-allowed', opacity: 0.6}}>
          <i className="fas fa-credit-card"></i>
          <span>Transactions</span>
        </div>
        <div className="menu-item" style={{cursor: 'not-allowed', opacity: 0.6}}>
          <i className="fas fa-user-tie"></i>
          <span>Compliance</span>
        </div>
        <div className="menu-item" style={{cursor: 'not-allowed', opacity: 0.6}}>
          <i className="fas fa-robot"></i>
          <span>AI Analytics</span>
        </div>
      </div>
      {isAdmin && (
        <div className="sidebar-settings">
          <Link to="/settings" className={`menu-item ${isActive("/settings") ? "active" : ""}`}>
            <i className="fas fa-cog"></i>
            <span>Settings</span>
          </Link>
        </div>
      )}
      <div className="sidebar-footer">
        <i className="fas fa-life-ring"></i>
        <span>Support v2.4</span>
      </div>
    </aside>
  );
}

export default Sidebar;
