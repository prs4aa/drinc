import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

export const getStatus = () => apiClient.get("/status");
export const getLogs = () => apiClient.get("/logs");
export const clearLogs = () => apiClient.post("/logs/clear");
export const startServer = () => apiClient.post("/server/start");
export const stopServer = () => apiClient.post("/server/stop");
export const killServer = () => apiClient.post("/server/kill");
export const disconnectClient = () => apiClient.post("/client/disconnect");
export const startMic = () => apiClient.post("/client/mic/start");
export const stopMic = () => apiClient.post("/client/mic/stop");
export const fetchContacts = () => apiClient.post("/client/contacts");
export const getContactsList = () => apiClient.get("/contacts/list");
export const fetchSms = (hours = 24) => apiClient.post("/client/sms", { hours });
export const getLatestSms = () => apiClient.get("/sms/latest");
export const listCameras = () => apiClient.post("/client/cameras");
export const captureCamera = (camId = "0") => apiClient.post("/client/camera/capture", { cam_id: camId });
export const fetchCallLogs = (hours = 24) => apiClient.post("/client/call_logs", { hours });
export const getLatestCallLogs = () => apiClient.get("/call_logs/latest");
export const fetchTelemetry = () => apiClient.post("/client/telemetry");
export const getTelemetry = () => apiClient.get("/client/telemetry");
export const clearAllData = () => apiClient.post("/data/clear");

export default apiClient;
