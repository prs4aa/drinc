import React, { useState } from "react";
import { clearLogs } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Terminal, Trash2, RefreshCw, Search, Copy, Check } from "lucide-react";

export default function LogsView({ logs, autoRefresh, setAutoRefresh, onRefresh }) {
  const { t } = useTranslation();
  const [levelFilter, setLevelFilter] = useState("ALL");
  const [searchTerm, setSearchTerm] = useState("");
  const [clearing, setClearing] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleClear = async () => {
    setClearing(true);
    try {
      await clearLogs();
      await onRefresh();
    } finally {
      setClearing(false);
    }
  };

  const handleCopyLogs = () => {
    if (logs && logs.length > 0) {
      navigator.clipboard.writeText(logs.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const filteredLogs = (logs || []).filter((log) => {
    if (levelFilter !== "ALL") {
      if (!log.includes(`[${levelFilter}]`)) {
        return false;
      }
    }
    if (searchTerm.trim()) {
      if (!log.toLowerCase().includes(searchTerm.toLowerCase())) {
        return false;
      }
    }
    return true;
  });

  return (
    <Card className="border-border bg-surface overflow-hidden shadow-sm">
      <CardHeader className="p-4 border-b border-border flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-header">
        <div className="flex items-center space-x-3 rtl:space-x-reverse">
          <div className="flex items-center space-x-1.5 pr-2 rtl:pr-0 rtl:pl-2 border-r rtl:border-r-0 rtl:border-l border-border">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600 inline-block" />
          </div>

          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <Terminal className="w-4 h-4 text-dim" />
            <CardTitle className="text-xs font-mono font-semibold tracking-tight text-main">
              {t("logs.console_title")}
            </CardTitle>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-input px-2 py-0.5 rounded-md border border-border text-xs">
            <label className="flex items-center space-x-1.5 rtl:space-x-reverse text-dim cursor-pointer text-[11px]">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded bg-surface border-border text-accent"
              />
              <span>{t("logs.live")}</span>
            </label>
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={handleCopyLogs}
            disabled={!logs || logs.length === 0}
            className="h-7 px-2.5 text-xs"
            title="Copy Logs"
          >
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </Button>

          <Button size="sm" variant="outline" onClick={onRefresh} className="h-7 px-2.5 text-xs">
            <RefreshCw className="w-3 h-3" />
          </Button>

          <Button
            size="sm"
            variant="destructive"
            disabled={clearing || !logs || logs.length === 0}
            onClick={handleClear}
            className="h-7 px-2.5 text-xs"
          >
            <Trash2 className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1" />
            {t("logs.clear")}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-4 space-y-3 bg-surface">
        <div className="flex flex-wrap gap-2 text-xs">
          <div className="flex items-center bg-input px-2.5 py-1 rounded-md border border-border flex-1 min-w-[200px]">
            <Search className="w-3 h-3 text-dim mr-2 rtl:mr-0 rtl:ml-2 flex-shrink-0" />
            <input
              type="text"
              placeholder={t("logs.search_placeholder")}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-transparent text-main placeholder-dim w-full focus:outline-none text-xs font-mono"
            />
          </div>

          <div className="flex items-center space-x-1 rtl:space-x-reverse bg-input p-0.5 rounded-md border border-border">
            {["ALL", "INFO", "WARN", "ERROR"].map((lvl) => (
              <button
                key={lvl}
                type="button"
                onClick={() => setLevelFilter(lvl)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium transition-colors ${
                  levelFilter === lvl
                    ? "bg-surface-elevated text-main font-semibold"
                    : "text-dim hover:text-main"
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-input border border-border rounded-lg p-3 font-mono text-xs max-h-[300px] overflow-y-auto space-y-1" dir="ltr">
          {filteredLogs.length > 0 ? (
            filteredLogs.map((line, idx) => {
              let isError = line.includes("[ERROR]");
              let isWarn = line.includes("[WARN]");
              let isInfo = line.includes("[INFO]");

              return (
                <div
                  key={idx}
                  className={`leading-relaxed flex items-start space-x-2.5 py-0.5 ${
                    isError
                      ? "text-rose-400 bg-rose-950/20 px-1 rounded"
                      : isWarn
                      ? "text-amber-400 bg-amber-950/10 px-1 rounded"
                      : isInfo
                      ? "text-main"
                      : "text-dim"
                  }`}
                >
                  <span className="text-dim/60 select-none text-[10px] flex-shrink-0 pt-0.5 font-mono w-6 text-right">
                    {idx + 1}
                  </span>
                  <span className="flex-1 break-all text-[11px]">{line}</span>
                </div>
              );
            })
          ) : (
            <div className="text-dim text-center py-8 font-mono text-xs">
              {t("logs.no_logs")}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
