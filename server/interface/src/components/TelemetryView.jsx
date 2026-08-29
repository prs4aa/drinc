import React, { useState } from "react";
import { fetchTelemetry, getTelemetry } from "../api/client";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  MapPin,
  Battery,
  BatteryCharging,
  BatteryFull,
  BatteryMedium,
  BatteryLow,
  Wifi,
  HardDrive,
  Cpu,
  Smartphone,
  ExternalLink,
  RefreshCw,
  Zap,
  Thermometer,
  Navigation,
  Target,
  Copy,
  Check,
  Globe,
  Clock,
} from "lucide-react";

export default function TelemetryView({ status, onRefresh }) {
  const [loading, setLoading] = useState(false);
  const [telemetryData, setTelemetryData] = useState(null);
  const [copiedCoords, setCopiedCoords] = useState(false);
  const [copiedIp, setCopiedIp] = useState(false);

  const data = telemetryData || status?.telemetry;

  const handleFetch = async () => {
    setLoading(true);
    try {
      await fetchTelemetry();
      await onRefresh();
      const res = await getTelemetry();
      if (res.data) {
        setTelemetryData(res.data);
      }
    } finally {
      setLoading(false);
    }
  };

  const loc = data?.location;
  const battery = data?.battery;
  const network = data?.network;
  const storage = data?.storage;
  const memory = data?.memory;
  const device = data?.device;

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

  const getBatteryIcon = () => {
    if (!battery) return <Battery className="w-5 h-5 text-slate-500" />;
    if (battery.charging) return <BatteryCharging className="w-5 h-5 text-emerald-400" />;
    if (battery.level >= 75) return <BatteryFull className="w-5 h-5 text-emerald-400" />;
    if (battery.level >= 25) return <BatteryMedium className="w-5 h-5 text-amber-400" />;
    return <BatteryLow className="w-5 h-5 text-rose-400" />;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-white">System Diagnostics & Location</h2>
          <p className="text-xs text-slate-400 mt-0.5">Real-time hardware telemetry and GPS sensor telemetry</p>
        </div>

        <Button
          size="sm"
          variant="outline"
          disabled={loading || !status?.client_connected}
          onClick={handleFetch}
          className="self-start sm:self-auto h-8 text-xs font-medium"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Acquiring Fix..." : "Query Telemetry & GPS"}
        </Button>
      </div>

      {data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="border-border/60 bg-surface/60">
            <CardHeader className="p-4 pb-3 flex flex-row items-center justify-between border-b border-border/30">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-md bg-rose-500/10 text-rose-400">
                  <MapPin className="w-4 h-4" />
                </div>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  GPS Location
                </CardTitle>
              </div>

              <Badge
                variant={
                  loc?.status === "available" || loc?.latitude
                    ? "success"
                    : loc?.status === "permission_denied"
                    ? "destructive"
                    : "secondary"
                }
                className="text-[10px] px-2 py-0.5"
              >
                {loc?.status ? loc.status.toUpperCase() : loc?.latitude ? "LOCKED" : "UNAVAILABLE"}
              </Badge>
            </CardHeader>

            <CardContent className="p-4 space-y-3">
              {loc?.latitude != null && loc?.longitude != null ? (
                <>
                  <div className="grid grid-cols-2 gap-2 font-mono text-xs">
                    <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                      <span className="text-[10px] uppercase text-slate-500 tracking-wider block font-sans">
                        Latitude
                      </span>
                      <span className="text-slate-100 font-medium text-sm block mt-0.5">
                        {loc.latitude.toFixed(6)}
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                      <span className="text-[10px] uppercase text-slate-500 tracking-wider block font-sans">
                        Longitude
                      </span>
                      <span className="text-slate-100 font-medium text-sm block mt-0.5">
                        {loc.longitude.toFixed(6)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-400 px-1 pt-0.5">
                    <span className="flex items-center gap-1.5">
                      <Target className="w-3.5 h-3.5 text-slate-500" />
                      Accuracy: <strong className="text-slate-200">{loc.accuracy ? `±${loc.accuracy}m` : "N/A"}</strong>
                    </span>

                    <span className="flex items-center gap-1.5">
                      <Navigation className="w-3.5 h-3.5 text-slate-500" />
                      Altitude: <strong className="text-slate-200">{loc.altitude ? `${Math.round(loc.altitude)}m` : "N/A"}</strong>
                    </span>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <a
                      href={`https://www.google.com/maps?q=${loc.latitude},${loc.longitude}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1"
                    >
                      <Button size="sm" variant="default" className="w-full h-8 text-xs">
                        <ExternalLink className="w-3 h-3 mr-1.5" />
                        View in Google Maps
                      </Button>
                    </a>

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleCopyCoords}
                      className="h-8 px-3 text-xs"
                      title="Copy Coordinates"
                    >
                      {copiedCoords ? (
                        <Check className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Copy className="w-3 h-3 text-slate-400" />
                      )}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="py-6 text-center text-xs text-slate-500">
                  Location coordinates unavailable. Tap "Query Telemetry & GPS" to acquire fix.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/60 bg-surface/60">
            <CardHeader className="p-4 pb-3 flex flex-row items-center justify-between border-b border-border/30">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400">
                  {getBatteryIcon()}
                </div>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Battery & Power
                </CardTitle>
              </div>

              {battery && (
                <Badge
                  variant={battery.level > 20 ? "success" : "destructive"}
                  className="text-[10px] px-2 py-0.5"
                >
                  {battery.charging ? "CHARGING" : "DISCHARGING"}
                </Badge>
              )}
            </CardHeader>

            <CardContent className="p-4 space-y-3">
              {battery ? (
                <>
                  <div className="flex items-baseline justify-between">
                    <div className="flex items-baseline space-x-2">
                      <span className="text-3xl font-bold font-mono tracking-tight text-white">
                        {battery.level}%
                      </span>
                      <span className="text-xs text-slate-400">capacity</span>
                    </div>

                    <span className="text-xs font-medium px-2 py-0.5 rounded bg-background border border-border/60 text-slate-300">
                      {battery.plugged}
                    </span>
                  </div>

                  <div className="w-full bg-background rounded-full h-2 overflow-hidden border border-border/40">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        battery.level > 40
                          ? "bg-emerald-500"
                          : battery.level > 15
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      }`}
                      style={{ width: `${Math.max(0, Math.min(100, battery.level))}%` }}
                    />
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-1 text-xs">
                    <div className="p-2 rounded-lg bg-background/80 border border-border/50 text-center">
                      <span className="text-[10px] uppercase text-slate-500 block font-mono">Temp</span>
                      <span className="font-semibold text-slate-200 text-xs mt-0.5 block">
                        {battery.temperature}°C
                      </span>
                    </div>

                    <div className="p-2 rounded-lg bg-background/80 border border-border/50 text-center">
                      <span className="text-[10px] uppercase text-slate-500 block font-mono">Voltage</span>
                      <span className="font-semibold text-slate-200 text-xs mt-0.5 block">
                        {battery.voltage}V
                      </span>
                    </div>

                    <div className="p-2 rounded-lg bg-background/80 border border-border/50 text-center">
                      <span className="text-[10px] uppercase text-slate-500 block font-mono">Health</span>
                      <span className="font-semibold text-slate-200 text-xs mt-0.5 block">
                        {battery.health}
                      </span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="py-6 text-center text-xs text-slate-500">No battery telemetry</div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/60 bg-surface/60">
            <CardHeader className="p-4 pb-3 flex flex-row items-center justify-between border-b border-border/30">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-md bg-sky-500/10 text-sky-400">
                  <Wifi className="w-4 h-4" />
                </div>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Network Connectivity
                </CardTitle>
              </div>

              {network?.type && (
                <Badge variant="secondary" className="text-[10px] px-2 py-0.5">
                  {network.type.toUpperCase()}
                </Badge>
              )}
            </CardHeader>

            <CardContent className="p-4 space-y-2.5">
              {network ? (
                <>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                      <span className="text-[10px] uppercase text-slate-500 block font-mono">Network Type</span>
                      <span className="font-semibold text-slate-100 mt-0.5 block">{network.type || "Unknown"}</span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                      <span className="text-[10px] uppercase text-slate-500 block font-mono">SSID / Carrier</span>
                      <span className="font-semibold text-slate-100 truncate mt-0.5 block">
                        {network.ssid || network.carrier || "—"}
                      </span>
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg bg-background/80 border border-border/50 flex items-center justify-between font-mono text-xs">
                    <div>
                      <span className="text-[10px] uppercase text-slate-500 block font-sans">Device IP Address</span>
                      <span className="text-slate-100 font-semibold mt-0.5 block">{network.ip || "—"}</span>
                    </div>

                    {network.ip && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={handleCopyIp}
                        className="h-7 w-7 p-0 text-slate-400 hover:text-white"
                        title="Copy IP"
                      >
                        {copiedIp ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                <div className="py-6 text-center text-xs text-slate-500">No network data</div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/60 bg-surface/60">
            <CardHeader className="p-4 pb-3 flex flex-row items-center justify-between border-b border-border/30">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-md bg-purple-500/10 text-purple-400">
                  <HardDrive className="w-4 h-4" />
                </div>
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Storage & Memory
                </CardTitle>
              </div>
            </CardHeader>

            <CardContent className="p-4 space-y-3">
              {storage && (
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between text-slate-400 text-[11px]">
                    <span>Disk Storage</span>
                    <span className="font-mono text-slate-200">
                      {formatBytes(storage.used_bytes)} / {formatBytes(storage.total_bytes)} ({calcPercentage(storage.used_bytes, storage.total_bytes)}%)
                    </span>
                  </div>
                  <div className="w-full bg-background rounded-full h-2 overflow-hidden border border-border/40">
                    <div
                      className="bg-purple-500 h-full rounded-full transition-all"
                      style={{ width: `${calcPercentage(storage.used_bytes, storage.total_bytes)}%` }}
                    />
                  </div>
                </div>
              )}

              {memory && (
                <div className="space-y-1.5 text-xs pt-1">
                  <div className="flex justify-between text-slate-400 text-[11px]">
                    <span>RAM Utilization</span>
                    <span className="font-mono text-slate-200">
                      {formatBytes(memory.used_bytes)} / {formatBytes(memory.total_bytes)} ({calcPercentage(memory.used_bytes, memory.total_bytes)}%)
                    </span>
                  </div>
                  <div className="w-full bg-background rounded-full h-2 overflow-hidden border border-border/40">
                    <div
                      className="bg-blue-500 h-full rounded-full transition-all"
                      style={{ width: `${calcPercentage(memory.used_bytes, memory.total_bytes)}%` }}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {device && (
            <Card className="md:col-span-2 border-border/60 bg-surface/60">
              <CardHeader className="p-4 pb-3 flex flex-row items-center justify-between border-b border-border/30">
                <div className="flex items-center space-x-2">
                  <div className="p-1.5 rounded-md bg-slate-700/50 text-slate-300">
                    <Smartphone className="w-4 h-4" />
                  </div>
                  <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Hardware Specifications
                  </CardTitle>
                </div>
              </CardHeader>

              <CardContent className="p-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                    <span className="text-[10px] uppercase text-slate-500 block font-mono">Model</span>
                    <span className="font-semibold text-slate-200 mt-0.5 block">{device.manufacturer} {device.model}</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                    <span className="text-[10px] uppercase text-slate-500 block font-mono">OS Version</span>
                    <span className="font-semibold text-slate-200 mt-0.5 block">Android {device.android_version} (API {device.sdk})</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                    <span className="text-[10px] uppercase text-slate-500 block font-mono">Patch Level</span>
                    <span className="font-semibold text-slate-200 mt-0.5 block">{device.security_patch}</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                    <span className="text-[10px] uppercase text-slate-500 block font-mono">Uptime</span>
                    <span className="font-semibold text-slate-200 mt-0.5 block">
                      {device.uptime_seconds
                        ? `${Math.floor(device.uptime_seconds / 3600)}h ${Math.floor((device.uptime_seconds % 3600) / 60)}m`
                        : "N/A"}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      ) : (
        <div className="p-12 text-center border border-dashed border-border/60 rounded-xl bg-surface/30">
          <p className="text-sm font-medium text-slate-300">No cached telemetry data</p>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Connect an Android device and query telemetry to view GPS coordinates, battery status, and device diagnostics.
          </p>
          <Button
            size="sm"
            variant="outline"
            disabled={loading || !status?.client_connected}
            onClick={handleFetch}
            className="mt-4"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Query Telemetry Now
          </Button>
        </div>
      )}
    </div>
  );
}
