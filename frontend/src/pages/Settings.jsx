import { useState, useEffect, useCallback } from "react";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";
import { employeesApi } from "../services/employeesApi";
import "./Settings.css";

const MODULES = [
  { key: "finance", label: "Finance" },
  { key: "it", label: "IT" },
  { key: "risk", label: "Risk" },
  { key: "reports", label: "Reports" },
];

const CAPABILITIES = [
  { key: "can_view", label: "View" },
  { key: "can_create", label: "Create tables" },
  { key: "can_edit", label: "Edit data" },
  { key: "can_delete", label: "Delete tables" },
  { key: "can_review", label: "Review" },
  { key: "can_approve", label: "Approve" },
];

const EMPLOYMENT_TYPES = ["FULL_TIME", "PART_TIME", "CONTRACT", "INTERN", "EXECUTIVE"];
const EMPLOYEE_STATUSES = ["ACTIVE", "INACTIVE", "ON_LEAVE", "TERMINATED", "PROBATION"];

function formatLabel(value) {
  return value
    .split("_")
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(" ");
}

function statusClass(status) {
  const map = {
    ACTIVE: "st-active",
    INACTIVE: "st-inactive",
    ON_LEAVE: "st-leave",
    TERMINATED: "st-terminated",
    PROBATION: "st-probation",
  };
  return map[status] || "";
}

function Settings() {
  const [activeTab, setActiveTab] = useState("users");
  const [departments, setDepartments] = useState([]);
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState({ type: "", message: "" });

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [depts, usersData, rolesData] = await Promise.all([
        employeesApi.getDepartments(),
        employeesApi.getUsers(),
        employeesApi.getRoles(),
      ]);
      setDepartments(depts);
      setUsers(usersData);
      setRoles(rolesData);
    } catch (err) {
      setError("Failed to load settings: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const showFeedback = (type, message) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback({ type: "", message: "" }), 3000);
  };

  const renderTabNav = () => (
    <div className="settings-tabs">
      <button
        className={`settings-tab ${activeTab === "users" ? "active" : ""}`}
        onClick={() => setActiveTab("users")}
      >
        <i className="fas fa-users"></i> Users
      </button>
      <button
        className={`settings-tab ${activeTab === "roles" ? "active" : ""}`}
        onClick={() => setActiveTab("roles")}
      >
        <i className="fas fa-user-tag"></i> Roles
      </button>
      <button
        className={`settings-tab ${activeTab === "departments" ? "active" : ""}`}
        onClick={() => setActiveTab("departments")}
      >
        <i className="fas fa-building"></i> Departments
      </button>
    </div>
  );

  return (
    <div className="settings-page">
      <Sidebar activePage="/settings" />
      <div className="main-wrapper">
        <TopBar title="Settings" titleIcon="fas fa-cog" />
        <div className="settings-content">
          {renderTabNav()}
          {feedback.message && (
            <div className={`feedback-banner ${feedback.type}`}>
              <i className={`fas ${feedback.type === "error" ? "fa-exclamation-circle" : "fa-check-circle"}`}></i>{" "}
              {feedback.message}
            </div>
          )}
          {error && (
            <div className="feedback-banner error">
              <i className="fas fa-exclamation-circle"></i> {error}
            </div>
          )}
          {loading ? (
            <div className="settings-loading">
              <i className="fas fa-spinner fa-spin"></i> Loading settings...
            </div>
          ) : (
            <>
              {activeTab === "users" && (
                <UsersTab
                  users={users}
                  departments={departments}
                  roles={roles}
                  onRefresh={loadAll}
                  showFeedback={showFeedback}
                />
              )}
              {activeTab === "roles" && (
                <RolesTab
                  roles={roles}
                  departments={departments}
                  onRefresh={loadAll}
                  showFeedback={showFeedback}
                />
              )}
              {activeTab === "departments" && (
                <DepartmentsTab
                  departments={departments}
                  onRefresh={loadAll}
                  showFeedback={showFeedback}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function roleNameById(roles, id) {
  const role = roles.find((r) => r.id === id);
  return role ? role.name : null;
}

function UsersTab({ users, departments, roles, onRefresh, showFeedback }) {
  const [editingUser, setEditingUser] = useState(null);

  const openEdit = (user) => {
    setEditingUser({
      ...user,
      form: {
        first_name: user.first_name || "",
        last_name: user.last_name || "",
        is_active: user.is_active,
        is_verified: user.is_verified,
        is_staff: user.is_staff,
        department: user.employee?.department ?? "",
        job_title: user.employee?.job_title || "",
        employment_type: user.employee?.employment_type || "FULL_TIME",
        status: user.employee?.status || "ACTIVE",
        roles: user.roles || [],
        create_profile: !user.has_profile,
      },
    });
  };

  const closeEdit = () => setEditingUser(null);

  const toggleRole = (roleId) => {
    const current = editingUser.form.roles;
    const next = current.includes(roleId)
      ? current.filter((id) => id !== roleId)
      : [...current, roleId];
    setEditingUser({ ...editingUser, form: { ...editingUser.form, roles: next } });
  };

  const saveUser = async () => {
    const u = editingUser;
    try {
      await employeesApi.updateUser(u.id, {
        first_name: u.form.first_name,
        last_name: u.form.last_name,
        is_active: u.form.is_active,
        is_verified: u.form.is_verified,
        is_staff: u.form.is_staff,
      });

      if (u.has_profile) {
        await employeesApi.updateProfile(u.employee.id, {
          department: u.form.department || null,
          job_title: u.form.job_title,
          employment_type: u.form.employment_type,
          status: u.form.status,
          roles: u.form.roles,
        });
      } else if (u.form.create_profile) {
        await employeesApi.createProfile({
          user: u.id,
          department: u.form.department || null,
          job_title: u.form.job_title,
          employment_type: u.form.employment_type,
          status: u.form.status,
          roles: u.form.roles,
        });
      }

      showFeedback("success", "User updated successfully");
      closeEdit();
      onRefresh();
    } catch (err) {
      const detail = err.response?.data || {};
      const message =
        detail.department || detail.job_title || detail.user || detail.detail
          ? (detail.department?.[0] || detail.job_title?.[0] || detail.user?.[0] || detail.detail)
          : err.message;
      showFeedback("error", "Failed to update: " + message);
    }
  };

  const activeCount = users.filter((u) => u.has_profile && u.is_active).length;

  return (
    <div className="settings-panel">
      <div className="panel-header">
        <h3>
          <i className="fas fa-users"></i> User Management
        </h3>
        <span className="panel-subtitle">
          {users.length} users · {activeCount} active employees
        </span>
      </div>
      <div className="table-wrap">
        <table className="settings-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Department</th>
              <th>Job Title</th>
              <th>Status</th>
              <th>Roles</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  <div className="user-cell">
                    <div className="user-avatar">{u.email.charAt(0).toUpperCase()}</div>
                    <div>
                      <div className="user-fullname">{u.full_name || "—"}</div>
                      <div className="user-meta">{u.is_verified ? "Verified" : "Unverified"}</div>
                    </div>
                  </div>
                </td>
                <td>{u.email}</td>
                <td>{u.employee?.department_name || <span className="muted">Not assigned</span>}</td>
                <td>{u.employee?.job_title || <span className="muted">—</span>}</td>
                <td>
                  {u.employee ? (
                    <span className={`status-badge ${statusClass(u.employee.status)}`}>
                      {formatLabel(u.employee.status)}
                    </span>
                  ) : (
                    <span className="muted">No profile</span>
                  )}
                </td>
                <td>
                  {u.is_staff ? (
                    <span className="role-badge admin">Admin</span>
                  ) : (u.roles || []).length > 0 ? (
                    <div className="role-badges">
                      {(u.roles || []).map((roleId) => {
                        const name = roleNameById(roles, roleId);
                        return name ? (
                          <span key={roleId} className="role-badge">
                            {formatLabel(name)}
                          </span>
                        ) : null;
                      })}
                    </div>
                  ) : (
                    <span className="role-badge none">No role</span>
                  )}
                </td>
                <td className="actions-cell">
                  <button className="btn btn-outline btn-sm" onClick={() => openEdit(u)}>
                    <i className="fas fa-pen"></i> Edit
                  </button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan="7" className="empty-cell">
                  No users found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editingUser && (
        <div className="modal-overlay" onClick={closeEdit}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>
                <i className="fas fa-user-cog"></i> Edit User
              </h4>
              <button className="modal-close" onClick={closeEdit}>
                <i className="fas fa-times"></i>
              </button>
            </div>

            <div className="modal-section-title">
              <i className="fas fa-id-card"></i> Account Info
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>First name</label>
                <input
                  type="text"
                  value={editingUser.form.first_name}
                  onChange={(e) =>
                    setEditingUser({ ...editingUser, form: { ...editingUser.form, first_name: e.target.value } })
                  }
                />
              </div>
              <div className="form-group">
                <label>Last name</label>
                <input
                  type="text"
                  value={editingUser.form.last_name}
                  onChange={(e) =>
                    setEditingUser({ ...editingUser, form: { ...editingUser.form, last_name: e.target.value } })
                  }
                />
              </div>
            </div>
            <div className="form-row">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editingUser.form.is_active}
                  onChange={(e) =>
                    setEditingUser({ ...editingUser, form: { ...editingUser.form, is_active: e.target.checked } })
                  }
                />
                Active
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editingUser.form.is_verified}
                  onChange={(e) =>
                    setEditingUser({ ...editingUser, form: { ...editingUser.form, is_verified: e.target.checked } })
                  }
                />
                Verified
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editingUser.form.is_staff}
                  onChange={(e) =>
                    setEditingUser({ ...editingUser, form: { ...editingUser.form, is_staff: e.target.checked } })
                  }
                />
                Admin
              </label>
            </div>

            {!editingUser.has_profile && (
              <label className="checkbox-label create-profile-toggle">
                <input
                  type="checkbox"
                  checked={editingUser.form.create_profile}
                  onChange={(e) =>
                    setEditingUser({ ...editingUser, form: { ...editingUser.form, create_profile: e.target.checked } })
                  }
                />
                Create employee profile for this user
              </label>
            )}

            {(editingUser.has_profile || editingUser.form.create_profile) && (
              <>
                <div className="modal-section-title">
                  <i className="fas fa-user-tag"></i> Roles
                </div>
                <div className="role-checklist">
                  {roles.map((r) => (
                    <label className="checkbox-label" key={r.id}>
                      <input
                        type="checkbox"
                        checked={editingUser.form.roles.includes(r.id)}
                        onChange={() => toggleRole(r.id)}
                      />
                      <span>{formatLabel(r.name)}</span>
                      {!r.is_active && <span className="muted"> (inactive)</span>}
                    </label>
                  ))}
                  {roles.length === 0 && <span className="muted">No roles defined yet.</span>}
                </div>

                <div className="modal-section-title">
                  <i className="fas fa-briefcase"></i> Employee Profile
                </div>
                <div className="form-group">
                  <label>Department</label>
                  <select
                    value={editingUser.form.department}
                    onChange={(e) =>
                      setEditingUser({ ...editingUser, form: { ...editingUser.form, department: e.target.value } })
                    }
                  >
                    <option value="">— Select department —</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Job title</label>
                    <input
                      type="text"
                      value={editingUser.form.job_title}
                      onChange={(e) =>
                        setEditingUser({ ...editingUser, form: { ...editingUser.form, job_title: e.target.value } })
                      }
                      placeholder="e.g. Analyst"
                    />
                  </div>
                  <div className="form-group">
                    <label>Employment type</label>
                    <select
                      value={editingUser.form.employment_type}
                      onChange={(e) =>
                        setEditingUser({ ...editingUser, form: { ...editingUser.form, employment_type: e.target.value } })
                      }
                    >
                      {EMPLOYMENT_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {formatLabel(t)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="form-group">
                  <label>Status</label>
                  <select
                    value={editingUser.form.status}
                    onChange={(e) =>
                      setEditingUser({ ...editingUser, form: { ...editingUser.form, status: e.target.value } })
                    }
                  >
                    {EMPLOYEE_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {formatLabel(s)}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            <div className="modal-actions">
              <button className="btn btn-primary" onClick={saveUser}>
                <i className="fas fa-check"></i> Save Changes
              </button>
              <button className="btn btn-outline" onClick={closeEdit}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RolesTab({ roles, departments, onRefresh, showFeedback }) {
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);

  const emptyRole = {
    id: null,
    name: "",
    description: "",
    can_view: true,
    can_create: false,
    can_edit: false,
    can_delete: false,
    can_review: false,
    can_approve: false,
    is_active: true,
    department_assignments: [],
  };

  const openNew = () => {
    setEditing({ ...emptyRole });
    setAdding(true);
  };

  const openEdit = (role) => {
    setEditing({
      ...role,
      department_assignments: role.department_assignments || [],
    });
    setAdding(false);
  };

  const close = () => setEditing(null);

  const setCap = (key) => {
    setEditing({ ...editing, [key]: !editing[key] });
  };

  const saveRole = async () => {
    if (!editing) return;
    if (!editing.name.trim()) {
      showFeedback("error", "Role name is required");
      return;
    }
    const payload = {
      name: editing.name.trim().toUpperCase(),
      description: editing.description,
      can_view: editing.can_view,
      can_create: editing.can_create,
      can_edit: editing.can_edit,
      can_delete: editing.can_delete,
      can_review: editing.can_review,
      can_approve: editing.can_approve,
      is_active: editing.is_active,
    };
    try {
      if (adding) {
        await employeesApi.createRole(payload);
        showFeedback("success", "Role created");
      } else {
        await employeesApi.updateRole(editing.id, payload);
        showFeedback("success", "Role updated");
      }
      close();
      onRefresh();
    } catch (err) {
      showFeedback("error", "Failed to save role: " + (err.response?.data?.detail || err.message));
    }
  };

  const deleteRole = async (role) => {
    if (!window.confirm(`Delete role "${role.name}"?`)) return;
    try {
      await employeesApi.deleteRole(role.id);
      showFeedback("success", "Role deleted");
      onRefresh();
    } catch (err) {
      showFeedback("error", "Failed to delete: " + (err.response?.data?.detail || err.message));
    }
  };

  const addAssignment = async (assignment) => {
    if (!assignment.department) {
      showFeedback("error", "Select a department");
      return;
    }
    try {
      await employeesApi.addRoleDepartment(editing.id, {
        department: assignment.department,
        modules: assignment.modules,
      });
      showFeedback("success", "Department access added");
      onRefresh();
    } catch (err) {
      showFeedback("error", "Failed to add: " + (err.response?.data?.detail || err.message));
    }
  };

  const removeAssignment = async (assignment) => {
    try {
      await employeesApi.removeRoleDepartment(editing.id, assignment.id);
      showFeedback("success", "Department access removed");
      onRefresh();
    } catch (err) {
      showFeedback("error", "Failed to remove: " + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="settings-panel">
      <div className="panel-header">
        <h3>
          <i className="fas fa-user-tag"></i> Roles
        </h3>
        <button className="btn btn-primary btn-sm" onClick={openNew}>
          <i className="fas fa-plus"></i> Add Role
        </button>
      </div>
      <p className="panel-desc">
        Roles define what a user can do (create, review, approve, ...). Assign each role to one or
        more departments and pick which modules the role applies to. Users then get these roles.
      </p>

      {roles.length === 0 && (
        <div className="empty-cell">No roles yet. Add one to grant access.</div>
      )}

      <div className="perm-grid">
        {roles.map((role) => (
          <div className={`perm-card ${role.is_active ? "" : "disabled"}`} key={role.id}>
            <div className="perm-card-head">
              <div>
                <div className="perm-title">{formatLabel(role.name)}</div>
                <div className="perm-sub">
                  {role.description || "No description"} ·{" "}
                  {role.is_active ? "Active" : "Inactive"}
                </div>
              </div>
              <div className="perm-head-actions">
                <button className="icon-btn" title="Edit" onClick={() => openEdit(role)}>
                  <i className="fas fa-pen"></i>
                </button>
                <button className="icon-btn danger" title="Delete" onClick={() => deleteRole(role)}>
                  <i className="fas fa-trash-alt"></i>
                </button>
              </div>
            </div>

            <div className="role-caps">
              {CAPABILITIES.map((cap) => (
                <span
                  key={cap.key}
                  className={`cap-chip ${role[cap.key] ? "on" : ""}`}
                  title={cap.label}
                >
                  <i className={`fas ${role[cap.key] ? "fa-check" : "fa-times"}`}></i> {cap.label}
                </span>
              ))}
            </div>

            {role.department_assignments.length > 0 && (
              <div className="role-depts">
                {role.department_assignments.map((assignment) => (
                  <div className="role-dept-row" key={assignment.id}>
                    <span className="dept-chip">{assignment.department_name}</span>
                    <span className="module-chips">
                      {assignment.modules.map((m) => (
                        <span key={m} className="module-chip">
                          {formatLabel(m)}
                        </span>
                      ))}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {editing && (
        <div className="modal-overlay" onClick={close}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>
                <i className="fas fa-user-tag"></i> {adding ? "Add Role" : "Edit Role"}
              </h4>
              <button className="modal-close" onClick={close}>
                <i className="fas fa-times"></i>
              </button>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  placeholder="e.g. Creator"
                />
              </div>
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea
                value={editing.description}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                placeholder="What does this role do?"
                rows={2}
              />
            </div>

            <div className="modal-section-title">
              <i className="fas fa-key"></i> Capabilities
            </div>
            <div className="role-checklist">
              {CAPABILITIES.map((cap) => (
                <label className="checkbox-label" key={cap.key}>
                  <input
                    type="checkbox"
                    checked={editing[cap.key]}
                    onChange={() => setCap(cap.key)}
                  />
                  <span>{cap.label}</span>
                </label>
              ))}
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editing.is_active}
                  onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })}
                />
                <span>Active</span>
              </label>
            </div>

            {!adding && (
              <>
                <div className="modal-section-title">
                  <i className="fas fa-building"></i> Department Access
                </div>
                <DepartmentAssignmentManager
                  role={editing}
                  departments={departments}
                  onAdd={addAssignment}
                  onRemove={removeAssignment}
                  showFeedback={showFeedback}
                />
              </>
            )}

            <div className="modal-actions">
              <button className="btn btn-primary" onClick={saveRole}>
                <i className="fas fa-check"></i> {adding ? "Create Role" : "Save Changes"}
              </button>
              <button className="btn btn-outline" onClick={close}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DepartmentAssignmentManager({ role, departments, onAdd, onRemove }) {
  const [department, setDepartment] = useState("");
  const [modules, setModules] = useState([]);

  const toggleModule = (key) => {
    setModules((prev) =>
      prev.includes(key) ? prev.filter((m) => m !== key) : [...prev, key]
    );
  };

  const submit = () => {
    onAdd({ department, modules });
    setDepartment("");
    setModules([]);
  };

  return (
    <div className="dept-assign">
      {role.department_assignments.length > 0 ? (
        <div className="role-depts">
          {role.department_assignments.map((assignment) => (
            <div className="role-dept-row" key={assignment.id}>
              <span className="dept-chip">{assignment.department_name}</span>
              <span className="module-chips">
                {assignment.modules.map((m) => (
                  <span key={m} className="module-chip">
                    {formatLabel(m)}
                  </span>
                ))}
              </span>
              <button
                className="icon-btn danger"
                title="Remove access"
                onClick={() => onRemove(assignment)}
              >
                <i className="fas fa-trash-alt"></i>
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-cell">No departments assigned yet.</div>
      )}

      <div className="form-row" style={{ marginTop: 12 }}>
        <div className="form-group">
          <label>Department</label>
          <select value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">— Select department —</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Modules</label>
          <div className="module-checkboxes">
            {MODULES.map((m) => (
              <label className="checkbox-label" key={m.key}>
                <input
                  type="checkbox"
                  checked={modules.includes(m.key)}
                  onChange={() => toggleModule(m.key)}
                />
                <span>{m.label}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
      <button className="btn btn-outline btn-sm" onClick={submit}>
        <i className="fas fa-plus"></i> Add Department Access
      </button>
    </div>
  );
}

function DepartmentsTab({ departments, onRefresh, showFeedback }) {
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const addDepartment = async () => {
    if (!name.trim()) {
      showFeedback("error", "Department name is required");
      return;
    }
    try {
      await employeesApi.createDepartment({
        name: name.trim().toUpperCase(),
        description,
      });
      showFeedback("success", "Department created");
      setShowAdd(false);
      setName("");
      setDescription("");
      onRefresh();
    } catch (err) {
      showFeedback("error", "Failed to create: " + (err.response?.data?.name?.[0] || err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="settings-panel">
      <div className="panel-header">
        <h3>
          <i className="fas fa-building"></i> Departments
        </h3>
        <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(true)}>
          <i className="fas fa-plus"></i> Add Department
        </button>
      </div>
      <div className="dept-grid">
        {departments.map((d) => (
          <div className={`dept-card ${d.is_active ? "" : "disabled"}`} key={d.id}>
            <i className="fas fa-building dept-icon"></i>
            <div>
              <div className="dept-name">{d.name}</div>
              <div className="dept-desc">{d.description || "No description"}</div>
            </div>
          </div>
        ))}
        {departments.length === 0 && <div className="empty-cell">No departments yet.</div>}
      </div>

      {showAdd && (
        <div className="modal-overlay" onClick={() => setShowAdd(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>
                <i className="fas fa-plus-circle"></i> Add Department
              </h4>
              <button className="modal-close" onClick={() => setShowAdd(false)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="form-group">
              <label>Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Operations"
              />
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={3}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={addDepartment}>
                <i className="fas fa-plus"></i> Create
              </button>
              <button className="btn btn-outline" onClick={() => setShowAdd(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Settings;
