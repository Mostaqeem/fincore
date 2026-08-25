import axios from "axios";
import { LAST_ACTIVITY_KEY } from "./components/IdleTimer";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
  headers: { "Content-Type": "application/json" },
});

let refreshPromise = null;

function clearClientSession() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem(LAST_ACTIVITY_KEY);
}

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;

    if (status === 401 && originalRequest && !originalRequest._retry) {
      if (originalRequest.url?.includes("/auth/refresh/")) {
        clearClientSession();
        window.location.href = "/signin";
        return Promise.reject(error);
      }

      const refresh = localStorage.getItem("refresh_token");
      if (!refresh) {
        clearClientSession();
        window.location.href = "/signin";
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post("http://localhost:8000/api/auth/refresh/", { refresh })
            .finally(() => {
              refreshPromise = null;
            });
        }
        const res = await refreshPromise;

        if (res.data?.access) {
          localStorage.setItem("access_token", res.data.access);
        }
        if (res.data?.refresh) {
          localStorage.setItem("refresh_token", res.data.refresh);
        }

        originalRequest.headers.Authorization = `Bearer ${res.data.access}`;
        return api(originalRequest);
      } catch {
        clearClientSession();
        window.location.href = "/signin";
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  },
);

export default api;
