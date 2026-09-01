import React, { useState } from "react";
import { selectClient, disconnectSpecificClient } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardHeader, CardContent } from "./ui/card";
import {
  Smartphone,
  CheckCircle2,
  Circle,
  Unlink,
  Battery,
  BatteryCharging,
  BatteryFull,
  BatteryMedium,
  BatteryLow,
  Wifi,
  Radio,
  Mic,
  Cpu,
} from "lucide-react";

export default function ClientSelector({ status, onRefresh }) {
  const { t, isRtl } = useTranslation();
  const [switchingId, setSwitchingId] = useState(null);
  const [disconnectingId, setDisconnectingId] = useState(null);

  const clients = status?.clients || [];
  const activeClientId = status?.active_client_id;
  const clientCount = clients.length;

  const handleSelectClient = async (clientId) => {
    if (clientId === activeClientId) return;
    setSwitchingId(clientId);
    try {
      await selectClient(clientId);
      if (onRefresh) await onRefresh();
    } finally {
      setSwitchingId(null);
    }
  };

  const handleDisconnectDevice = async (e, clientId) => {
    e.stopPropagation();
    setDisconnectingId(clientId);
    try {
      await disconnectSpecificClient(clientId);
      if (onRefresh) await onRefresh();
    } finally {
      setDisconnectingId(null);
    }
  };

  const getBatteryIcon = (batteryLevel, charging) => {
    if (batteryLevel == null) return <Battery className="w-3.5 h-3.5 text-dim" />;
    if (charging) return <BatteryCharging className="w-3.5 h-3.5 text-emerald-400" />;
    if (batteryLevel >= 75) return <BatteryFull className="w-3.5 h-3.5 text-emerald-400" />;
    if (batteryLevel >= 25) return <BatteryMedium className="w-3.5 h-3.5 text-amber-400" />;
    return <BatteryLow className="w-3.5 h-3.5 text-rose-400" />;
  };

  if (clientCount === 0) {
    return null;
  }

  return (
    <Card className="border-border bg-surface shadow-sm overflow-hidden">
      <CardHeader className="p-3 pb-2 flex flex-row items-center justify-between border-b border-border-muted bg-surface-elevated/40">
        <div className="flex items-center space-x-2 rtl:space-x-reverse">
          <Smartphone className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-main uppercase">
            {t("clients.title")}
          </span>
        </div>
        <div className="flex items-center space-x-2 rtl:space-x-reverse">
          <Badge variant="secondary" className="text-[10px] font-mono px-2 py-0.5">
            {clientCount > 1
              ? t("clients.devices_connected", { count: clientCount }).replace("{{count}}", clientCount)
              : t("clients.single_connected")}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {clients.map((client) => {
            const isActive = client.is_active || client.id === activeClientId;
            const isSwitching = switchingId === client.id;
            const isDisconnecting = disconnectingId === client.id;

            return (
              <div
                key={client.id}
                onClick={() => handleSelectClient(client.id)}
                className={`relative rounded-lg p-3 border transition-all cursor-pointer flex flex-col justify-between select-none ${
                  isActive
                    ? "bg-emerald-950/20 border-emerald-500/60 shadow-[0_0_12px_rgba(16,185,129,0.15)] ring-1 ring-emerald-500/30"
                    : "bg-surface-elevated/60 border-border hover:border-border-hover hover:bg-surface-elevated"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center space-x-2 rtl:space-x-reverse min-w-0">
                    <div className="flex-shrink-0">
                      {isActive ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Circle className="w-4 h-4 text-dim" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                        <span className="text-xs font-semibold text-main truncate font-mono">
                          {client.device_name || client.addr}
                        </span>
                        {isActive && (
                          <Badge variant="success" className="text-[8px] px-1 py-0 font-mono tracking-wider font-bold uppercase">
                            {t("clients.main_label")}
                          </Badge>
                        )}
                      </div>
                      <span className="text-[10px] text-dim font-mono block truncate">
                        {client.addr}
                      </span>
                    </div>
                  </div>

                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={isDisconnecting}
                    onClick={(e) => handleDisconnectDevice(e, client.id)}
                    className="h-6 w-6 p-0 text-dim hover:text-rose-400 hover:bg-rose-950/30 -mt-1 -mr-1 rtl:-mr-0 rtl:-ml-1"
                    title={t("clients.disconnect_device")}
                  >
                    <Unlink className={`w-3 h-3 ${isDisconnecting ? "animate-spin" : ""}`} />
                  </Button>
                </div>

                <div className="mt-3 pt-2 border-t border-border-muted/60 flex items-center justify-between text-[10px] font-mono text-dim">
                  <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
                    {client.battery_level != null && (
                      <div className="flex items-center space-x-1 rtl:space-x-reverse">
                        {getBatteryIcon(client.battery_level, client.battery_charging)}
                        <span className="text-main font-medium">{client.battery_level}%</span>
                      </div>
                    )}
                    {client.network_type && (
                      <div className="flex items-center space-x-1 rtl:space-x-reverse">
                        <Wifi className="w-3 h-3 text-sky-400" />
                        <span>{client.network_type}</span>
                      </div>
                    )}
                    {client.mic_active && (
                      <div className="flex items-center space-x-1 rtl:space-x-reverse text-amber-400 animate-pulse">
                        <Mic className="w-3 h-3" />
                      </div>
                    )}
                  </div>

                  <div>
                    {isActive ? (
                      <span className="text-emerald-400 font-semibold text-[9px] uppercase tracking-wider">
                        {t("clients.active")}
                      </span>
                    ) : (
                      <span className="text-dim hover:text-main text-[9px] uppercase tracking-wider underline cursor-pointer">
                        {isSwitching ? "..." : t("clients.set_active")}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
