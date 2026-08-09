import api from "../axiosconfig";

export const datasetApi = {
  uploadFile: async (file, section = "finance") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("section", section);
    const response = await api.post("/datasets/upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  getJobStatus: async (jobId) => {
    const response = await api.get(`/datasets/jobs/${jobId}/`);
    return response.data;
  },

  getDatasets: async (section = "finance") => {
    const response = await api.get(`/datasets/?section=${section}`);
    return response.data;
  },

  getDataset: async (id) => {
    const response = await api.get(`/datasets/${id}/`);
    return response.data;
  },

  getDatasetData: async (id, page = 1, pageSize = 50) => {
    const response = await api.get(`/datasets/${id}/data/?page=${page}&page_size=${pageSize}`);
    return response.data;
  },

  updateCell: async (id, rowId, column, value) => {
    const response = await api.patch(`/datasets/${id}/data/${rowId}/`, {
      column,
      value,
    });
    return response.data;
  },

  addRow: async (id, data) => {
    const response = await api.post(`/datasets/${id}/rows/`, { data });
    return response.data;
  },

  updateRow: async (id, rowId, data) => {
    const response = await api.patch(`/datasets/${id}/rows/${rowId}/`, data);
    return response.data;
  },

  deleteRow: async (id, rowId) => {
    const response = await api.delete(`/datasets/${id}/rows/${rowId}/delete/`);
    return response.data;
  },

  renameColumn: async (id, oldName, newName) => {
    const response = await api.patch(`/datasets/${id}/columns/${oldName}/`, {
      new_name: newName,
    });
    return response.data;
  },

  createTable: async (data) => {
    const response = await api.post(`/datasets/create-manual/`, data);
    return response.data;
  },

  submitDataset: async (id) => {
    const response = await api.post(`/datasets/${id}/submit/`);
    return response.data;
  },

  startReview: async (id) => {
    const response = await api.post(`/datasets/${id}/start-review/`);
    return response.data;
  },

  reviewApprove: async (id, comment = "") => {
    const response = await api.post(`/datasets/${id}/review-approve/`, { comment });
    return response.data;
  },

  approveDataset: async (id, comment = "") => {
    const response = await api.post(`/datasets/${id}/approve/`, { comment });
    return response.data;
  },

  rejectDataset: async (id, comment = "") => {
    const response = await api.post(`/datasets/${id}/reject/`, { comment });
    return response.data;
  },

  deleteDataset: async (id) => {
    const response = await api.delete(`/datasets/${id}/`);
    return response.data;
  },
};
