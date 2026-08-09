import api from "../axiosconfig";

export const employeesApi = {
  getMe: async () => {
    const response = await api.get("/employees/me/");
    return response.data;
  },

  getUsers: async () => {
    const response = await api.get("/employees/users/");
    return response.data;
  },

  updateUser: async (id, data) => {
    const response = await api.patch(`/employees/users/${id}/`, data);
    return response.data;
  },

  getProfiles: async () => {
    const response = await api.get("/employees/profiles/");
    return response.data;
  },

  createProfile: async (data) => {
    const response = await api.post("/employees/profiles/", data);
    return response.data;
  },

  updateProfile: async (id, data) => {
    const response = await api.patch(`/employees/profiles/${id}/`, data);
    return response.data;
  },

  deleteProfile: async (id) => {
    const response = await api.delete(`/employees/profiles/${id}/`);
    return response.data;
  },

  getDepartments: async () => {
    const response = await api.get("/employees/departments/");
    return response.data;
  },

  createDepartment: async (data) => {
    const response = await api.post("/employees/departments/", data);
    return response.data;
  },

  getRoles: async () => {
    const response = await api.get("/employees/roles/");
    return response.data;
  },

  createRole: async (data) => {
    const response = await api.post("/employees/roles/", data);
    return response.data;
  },

  updateRole: async (id, data) => {
    const response = await api.patch(`/employees/roles/${id}/`, data);
    return response.data;
  },

  deleteRole: async (id) => {
    const response = await api.delete(`/employees/roles/${id}/`);
    return response.data;
  },

  getRoleDepartments: async (roleId) => {
    const response = await api.get(`/employees/roles/${roleId}/departments/`);
    return response.data;
  },

  addRoleDepartment: async (roleId, data) => {
    const response = await api.post(`/employees/roles/${roleId}/departments/`, data);
    return response.data;
  },

  removeRoleDepartment: async (roleId, assignmentId) => {
    const response = await api.delete(`/employees/roles/${roleId}/departments/?assignment_id=${assignmentId}`);
    return response.data;
  },
};
