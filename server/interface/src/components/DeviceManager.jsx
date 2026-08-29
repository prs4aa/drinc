import React, { useState } from "react";
import { disconnectClient } from "../api/client";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  Smartphone,
  Unlink,
  Wifi,
  WifiOff,
  Radio,
  Copy,
  Check,
  Server,
  ShieldCheck,
} from "lucide-react";

export default function DeviceManager({ status, onRefresh }) {
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await disconnectClient();
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const handleCopyAddr = () => {
    if (status?.client_addr) {
      navigator.clipboard.writeText(status.client_addr);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isConnected = !!status?.client_connected;
  const device = status?.telemetry?.device;

  return (
    <Card className="overflow-hidden border-border/80 shadow-md">
      <CardHeader className="flex flex-row items-center justify-between pb-3 bg-gradient-to-r from-surface to-surface-elevated">
        <div className="flex items-center space-x-2.5">
          <div
            className={`p-2 rounded-xl border transition-colors ${
              isConnected
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-blue-500/10 border-blue-500/30 text-blue-400"
            }`}
          >
            {isConnected ? (
              <Smartphone className="w-4 h-4" />
            ) : (
              <Radio className="w-4 h-4 animate-pulse" />
            )}
          </div>
          <div>
            <CardTitle className="text-sm font-semibold">
              {isConnected ? "Connected Device" : "Device Gateway"}
            </CardTitle>
            <p className="text-[11px] text-slate-400">
              {isConnected ? "Active peer session" : `Listener active on port ${status?.tcp_port || 33110}`}
            </p>
          </div>
        </div>

        <Badge variant={isConnected ? "success" : "secondary"}>
          <span
            className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
              isConnected ? "bg-emerald-400 animate-pulse" : "bg-blue-400 animate-ping"
            }`}
          />
          {isConnected ? "ONLINE" : "LISTENING"}
        </Badge>
      </CardHeader>

      <CardContent className="p-4 space-y-3.5">
        {isConnected ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-xl bg-background/80 border border-border/70">
              <div className="space-y-0.5">
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block">
                  Device Hardware
                </span>
                <span className="text-xs font-semibold text-slate-100 flex items-center gap-1.5">
                  <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
                  {device ? `${device.manufacturer} ${device.model}` : "Android Client"}
                </span>
              </div>

              {device?.android_version && (
                <span className="px-2 py-0.5 rounded-md bg-surface border border-border/60 text-[11px] text-slate-300 font-mono">
                  Android {device.android_version}
                </span>
              )}
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-background/50 border border-border/50 text-xs">
              <div className="flex items-center space-x-2">
                <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-slate-400">Socket Peer:</span>
                <span className="font-mono text-slate-200 font-medium">
                  {status.client_addr}
                </span>
              </div>
              <button
                type="button"
                onClick={handleCopyAddr}
                className="p-1 rounded-md hover:bg-surface text-slate-400 hover:text-slate-200 transition-colors"
                title="Copy Address"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>

            <Button
              size="sm"
              variant="destructive"
              disabled={loading}
              onClick={handleDisconnect}
              className="w-full"
            >
              <Unlink className="w-3.5 h-3.5 mr-1.5" />
              Disconnect Device
            </Button>
          </div>
        ) : (
          <div className="text-center py-4 space-y-3">
            <div className="relative w-12 h-12 mx-auto flex items-center justify-center">
              <div className="absolute inset-0 rounded-full bg-blue-500/10 animate-ping" />
              <div className="w-10 h-10 rounded-full bg-surface-elevated border border-blue-500/30 flex items-center justify-center text-blue-400 shadow-inner">
                <Radio className="w-5 h-5" />
              </div>
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium text-slate-200">
                Waiting for Android Client
              </p>
              <p className="text-[11px] text-slate-400 max-w-[260px] mx-auto">
                The TCP listener is actively waiting for inbound connections on port{" "}
                <span className="text-blue-400 font-mono">{status?.tcp_port || 33110}</span>.
              </p>
            </div>

            <div className="p-2 rounded-lg bg-background/50 border border-border/40 text-[11px] font-mono text-slate-400 text-center">
              Target Port: {status?.tcp_port || 33110}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
