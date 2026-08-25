import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import NotificationBell from "./NotificationBell";
import "./TopBar.css";

function TopBar({ title, titleIcon }) {
  const { user, logout } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/signin");
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="banner">
          <i className={titleIcon}></i> {title}
        </div>
      </div>
      <div className="topbar-right">
        {/* Live notification bell — badge, dropdown, real-time toasts. */}
        <NotificationBell />
        <div className="user-dropdown-wrapper" ref={dropdownRef}>
          <div
            className="user-dropdown"
            onClick={() => setShowDropdown(!showDropdown)}
            style={{ cursor: "pointer" }}
          >
            <div className="avatar">
              {user?.email ? user.email[0].toUpperCase() : "U"}
            </div>
            <div className="user-info">
              <div className="user-name">{user?.email || "User"}</div>
              <div className="user-role">Member</div>
            </div>
            <i className={`fas fa-chevron-${showDropdown ? "up" : "down"}`}></i>
          </div>
          <div className={`user-dropdown-menu ${showDropdown ? "show" : ""}`}>
            <Link
              to="/forgot-password"
              className="dropdown-item"
              onClick={() => setShowDropdown(false)}
            >
              <i className="fas fa-key"></i>
              Change Password
            </Link>
            <div className="dropdown-divider"></div>
            <button className="dropdown-item logout" onClick={handleLogout}>
              <i className="fas fa-sign-out-alt"></i>
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}

export default TopBar;
