import React, { useState, useEffect } from "react";
import { fetchCallLogs, getLatestCallLogs } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  PhoneMissed,
  PhoneOff,
  Download,
  RefreshCw,
  Search,
  Copy,
  Check,
  Maximize2,
  X,
  Clock,
  User,
  Shield,
} from "lucide-react";

export default function CallLogsManager({ status, onRefresh }) {
  const { t } = useTranslation();
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(false);
  const [calls, setCalls] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [copiedSelected, setCopiedSelected] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedCall, setSelectedCall] = useState(null);

  const loadCalls = async () => {
    try {
      const res = await getLatestCallLogs();
      if (Array.isArray(res.data)) {
        setCalls(res.data);
        if (res.data.length > 0 && !selectedCall) {
          setSelectedCall(res.data[0]);
        }
      }
    } catch (e) {}
  };

  useEffect(() => {
    loadCalls();
  }, []);

  useEffect(() => {
    if (status?.call_logs_count > 0 && calls.length === 0) {
      loadCalls();
    }
  }, [status?.call_logs_count, calls.length]);

  const handleFetch = async (targetHours = hours) => {
    setLoading(true);
    try {
      const res = await fetchCallLogs(Number(targetHours));
      if (res?.data?.status === "ok" && Array.isArray(res?.data?.data)) {
        setCalls(res.data.data);
        if (res.data.data.length > 0) {
          setSelectedCall(res.data.data[0]);
        }
      }
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const handleCopyNumber = (num, idx) => {
    if (num) {
      navigator.clipboard.writeText(num);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    }
  };

  const handleCopySelectedNumber = () => {
    if (selectedCall?.number) {
      navigator.clipboard.writeText(selectedCall.number);
      setCopiedSelected(true);
      setTimeout(() => setCopiedSelected(false), 1500);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds || seconds <= 0) return "0s";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  const formatDate = (dateVal) => {
    if (!dateVal) return "";
    try {
      const d = typeof dateVal === "number" ? new Date(dateVal) : new Date(Number(dateVal));
      if (isNaN(d.getTime())) return String(dateVal);
      return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return String(dateVal);
    }
  };

  const getCallTypeMeta = (type) => {
    switch (type) {
      case 1:
        return {
          label: t("call_logs.incoming"),
          icon: PhoneIncoming,
          badgeVariant: "success",
          textColor: "text-emerald-400",
          bgColor: "bg-emerald-500/10 border-emerald-500/30",
        };
      case 2:
        return {
          label: t("call_logs.outgoing"),
          icon: PhoneOutgoing,
          badgeVariant: "default",
          textColor: "text-sky-400",
          bgColor: "bg-sky-500/10 border-sky-500/30",
        };
      case 3:
        return {
          label: t("call_logs.missed"),
          icon: PhoneMissed,
          badgeVariant: "destructive",
          textColor: "text-rose-400",
          bgColor: "bg-rose-500/10 border-rose-500/30",
        };
      case 5:
        return {
          label: t("call_logs.rejected"),
          icon: PhoneOff,
          badgeVariant: "warning",
          textColor: "text-amber-400",
          bgColor: "bg-amber-500/10 border-amber-500/30",
        };
      default:
        return {
          label: "CALL",
          icon: Phone,
          badgeVariant: "secondary",
          textColor: "text-slate-400",
          bgColor: "bg-surface-elevated border-border",
        };
    }
  };

  const handleExportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(calls, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", `call_logs_${Date.now()}.json`);
    document.body.appendChild(dlAnchor);
    dlAnchor.click();
    dlAnchor.remove();
  };

  const filtered = calls.filter((c) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (c.number || "").toLowerCase().includes(term) ||
      (c.name || "").toLowerCase().includes(term)
    );
  });

  return (
    <>
      <Card className="border-border bg-surface flex flex-col h-full shadow-sm">
        <CardHeader className="p-3.5 pb-2.5 border-b border-border-muted flex flex-row items-center justify-between">
          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <div className="p-1.5 rounded-md bg-surface-elevated border border-border text-amber-400">
              <Phone className="w-3.5 h-3.5" />
            </div>
            <div>
              <CardTitle className="text-xs font-mono font-semibold uppercase tracking-wide text-main">
                {t("call_logs.title")}
              </CardTitle>
            </div>
          </div>

          <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
            <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-mono">
              {calls.length}
            </Badge>

            <Button
              size="sm"
              variant="outline"
              onClick={() => setIsModalOpen(true)}
              className="h-6 w-6 p-0 text-dim hover:text-main"
              title={t("call_logs.expand")}
            >
              <Maximize2 className="w-3 h-3" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-3.5 space-y-3 flex-1 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="relative">
              <Search className="w-3 h-3 absolute left-2.5 rtl:left-auto rtl:right-2.5 top-2 text-dim" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder={t("call_logs.search_placeholder")}
                className="w-full bg-input border border-border rounded-md pl-7 rtl:pl-2 rtl:pr-7 pr-2 py-1 text-xs font-mono text-main placeholder:text-dim/60 outline-none"
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-1.5 text-xs">
              <div className="flex items-center space-x-1 rtl:space-x-reverse">
                <div className="flex bg-input p-0.5 rounded-lg border border-border font-mono text-[10px]">
                  {[12, 24, 72].map((h) => (
                    <button
                      key={h}
                      type="button"
                      onClick={() => {
                        setHours(h);
                        handleFetch(h);
                      }}
                      className={`px-1.5 py-0.5 rounded font-medium transition-colors ${
                        Number(hours) === h ? "bg-surface-elevated text-main font-semibold shadow-sm" : "text-dim hover:text-main"
                      }`}
                    >
                      {h}h
                    </button>
                  ))}
                </div>

                <div className="relative flex items-center bg-input rounded-lg border border-border focus-within:border-amber-500/60 transition-colors">
                  <input
                    type="number"
                    min="1"
                    value={hours}
                    onChange={(e) => setHours(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleFetch(Number(hours) || 24);
                    }}
                    className="w-14 pl-2 pr-5 py-1 bg-transparent text-main text-xs font-mono focus:outline-none text-right rtl:text-left rtl:pr-2 rtl:pl-5"
                    placeholder="24"
                  />
                  <span className="absolute right-1.5 rtl:right-auto rtl:left-1.5 text-[10px] text-dim pointer-events-none font-mono select-none">
                    h
                  </span>
                </div>
              </div>

              <Button
                size="sm"
                variant="default"
                disabled={loading || !status?.client_connected}
                onClick={() => handleFetch(hours)}
                className="h-7 px-2.5 text-xs font-mono font-medium bg-amber-600 hover:bg-amber-500 text-white whitespace-nowrap flex-shrink-0"
              >
                <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
                {t("call_logs.fetch")}
              </Button>
            </div>
          </div>

          <div className="border border-border rounded-xl bg-input overflow-hidden flex-1 min-h-[220px] max-h-[260px] flex flex-col">
            <div className="overflow-y-auto flex-1 divide-y divide-border-muted">
              {filtered.length === 0 ? (
                <div className="p-6 text-center text-xs font-mono text-dim flex flex-col items-center justify-center h-full">
                  <Phone className="w-6 h-6 mb-2 text-dim/40" />
                  <p>{calls.length === 0 ? t("call_logs.no_records") : t("call_logs.no_matching")}</p>
                </div>
              ) : (
                filtered.map((call, idx) => {
                  const meta = getCallTypeMeta(call.type);
                  const Icon = meta.icon;
                  return (
                    <div
                      key={idx}
                      onClick={() => {
                        setSelectedCall(call);
                        setIsModalOpen(true);
                      }}
                      className="p-2.5 hover:bg-surface-elevated/70 transition-colors cursor-pointer flex items-center justify-between space-x-2 rtl:space-x-reverse"
                    >
                      <div className="flex items-center space-x-2.5 rtl:space-x-reverse min-w-0">
                        <div className={`p-1.5 rounded-md border ${meta.bgColor} ${meta.textColor} flex-shrink-0`}>
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                            <span className="text-xs font-mono font-semibold text-main truncate">
                              {call.name || call.number}
                            </span>
                            {call.name && (
                              <span className="text-[10px] font-mono text-dim truncate">
                                ({call.number})
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] font-mono text-dim flex items-center space-x-2 rtl:space-x-reverse">
                            <span>{formatDate(call.date)}</span>
                            <span>•</span>
                            <span className={call.duration > 0 ? "text-main" : "text-rose-400"}>
                              {formatDuration(call.duration)}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-1 rtl:space-x-reverse flex-shrink-0">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCopyNumber(call.number, idx);
                          }}
                          className="h-6 w-6 p-0 text-dim hover:text-main"
                          title={t("call_logs.copy_number")}
                        >
                          {copiedIdx === idx ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="relative w-full max-w-5xl h-[85vh] bg-surface border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            <div className="p-4 px-6 border-b border-border flex items-center justify-between bg-header">
              <div className="flex items-center space-x-3 rtl:space-x-reverse">
                <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
                  <Phone className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-sm font-mono font-bold text-main">
                    {t("call_logs.studio_title")}
                  </h2>
                  <p className="text-[11px] text-dim">
                    {t("call_logs.studio_desc")} ({calls.length} records)
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2 rtl:space-x-reverse">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleExportJson}
                  className="h-8 text-xs font-mono"
                >
                  <Download className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                  {t("call_logs.export_json")}
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setIsModalOpen(false)}
                  className="h-8 w-8 p-0 text-dim hover:text-main"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
              <div className="w-full md:w-5/12 border-r md:border-r border-border flex flex-col bg-background/50">
                <div className="p-3 border-b border-border bg-surface">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 rtl:left-auto rtl:right-2.5 top-2.5 text-dim" />
                    <input
                      type="text"
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      placeholder={t("call_logs.search_placeholder")}
                      className="w-full bg-input border border-border rounded-lg pl-8 rtl:pl-2 rtl:pr-8 pr-2 py-1.5 text-xs font-mono text-main placeholder:text-dim/60 outline-none"
                    />
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto divide-y divide-border-muted">
                  {filtered.map((call, idx) => {
                    const isSelected = selectedCall === call;
                    const meta = getCallTypeMeta(call.type);
                    const Icon = meta.icon;
                    return (
                      <div
                        key={idx}
                        onClick={() => setSelectedCall(call)}
                        className={`p-3 transition-colors cursor-pointer flex items-center justify-between ${
                          isSelected ? "bg-surface-elevated border-l-2 border-amber-500" : "hover:bg-surface-elevated/50"
                        }`}
                      >
                        <div className="flex items-center space-x-2.5 rtl:space-x-reverse min-w-0">
                          <div className={`p-1.5 rounded-md border ${meta.bgColor} ${meta.textColor} flex-shrink-0`}>
                            <Icon className="w-3.5 h-3.5" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs font-mono font-semibold text-main truncate">
                              {call.name || call.number}
                            </div>
                            <div className="text-[10px] font-mono text-dim flex items-center space-x-2 rtl:space-x-reverse">
                              <span>{formatDate(call.date)}</span>
                              <span>•</span>
                              <span className={call.duration > 0 ? "text-main" : "text-rose-400"}>
                                {formatDuration(call.duration)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <Badge variant={meta.badgeVariant} className="text-[9px] px-1.5 py-0 font-mono">
                          {meta.label}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="w-full md:w-7/12 flex-1 flex flex-col bg-surface p-6 overflow-y-auto">
                {selectedCall ? (
                  <div className="space-y-6 max-w-xl mx-auto w-full">
                    {(() => {
                      const meta = getCallTypeMeta(selectedCall.type);
                      const Icon = meta.icon;
                      return (
                        <div className="p-4 rounded-xl bg-input border border-border space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
                              <div className={`p-2 rounded-lg border ${meta.bgColor} ${meta.textColor}`}>
                                <Icon className="w-5 h-5" />
                              </div>
                              <div>
                                <h3 className="text-sm font-mono font-bold text-main">
                                  {selectedCall.name || selectedCall.number}
                                </h3>
                                <p className="text-[11px] font-mono text-dim">
                                  {selectedCall.name ? selectedCall.number : meta.label}
                                </p>
                              </div>
                            </div>

                            <Badge variant={meta.badgeVariant} className="text-xs font-mono px-2 py-0.5">
                              {meta.label}
                            </Badge>
                          </div>

                          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border-muted text-xs font-mono">
                            <div className="bg-surface p-2.5 rounded-lg border border-border space-y-1">
                              <span className="text-[10px] text-dim flex items-center space-x-1 rtl:space-x-reverse">
                                <Clock className="w-3 h-3" />
                                <span>{t("call_logs.duration")}</span>
                              </span>
                              <span className="text-sm font-semibold text-main block">
                                {formatDuration(selectedCall.duration)}
                              </span>
                            </div>

                            <div className="bg-surface p-2.5 rounded-lg border border-border space-y-1">
                              <span className="text-[10px] text-dim flex items-center space-x-1 rtl:space-x-reverse">
                                <Clock className="w-3 h-3" />
                                <span>{t("call_logs.timestamp")}</span>
                              </span>
                              <span className="text-sm font-semibold text-main block truncate">
                                {formatDate(selectedCall.date)}
                              </span>
                            </div>
                          </div>

                          <div className="pt-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={handleCopySelectedNumber}
                              className="w-full text-xs font-mono"
                            >
                              {copiedSelected ? (
                                <>
                                  <Check className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5 text-emerald-400" />
                                  {t("call_logs.copied")}
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                                  {t("call_logs.copy_number")} ({selectedCall.number})
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      );
                    })()}

                    <div className="space-y-2">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-dim">
                        RAW TELEPHONY METADATA
                      </span>
                      <pre className="p-3 bg-input border border-border rounded-xl font-mono text-xs text-main overflow-x-auto">
                        {JSON.stringify(selectedCall, null, 2)}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6 text-dim font-mono">
                    <Phone className="w-8 h-8 mb-2 text-dim/30" />
                    <p className="text-sm">{t("call_logs.no_selected")}</p>
                    <p className="text-xs text-dim/60 mt-1">{t("call_logs.no_selected_desc")}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
