import React, { useState, useEffect } from "react";
import { fetchSms, getLatestSms } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  MessageSquare,
  Download,
  RefreshCw,
  Search,
  ArrowDownLeft,
  ArrowUpRight,
  Copy,
  Check,
  Maximize2,
  X,
  Clock,
  User,
} from "lucide-react";

export default function SmsManager({ status, onRefresh }) {
  const { t } = useTranslation();
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [copiedSelected, setCopiedSelected] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState(null);

  const loadSms = async () => {
    try {
      const res = await getLatestSms();
      if (Array.isArray(res.data)) {
        setMessages(res.data);
        if (res.data.length > 0 && !selectedMessage) {
          setSelectedMessage(res.data[0]);
        }
      }
    } catch (e) {}
  };

  useEffect(() => {
    loadSms();
  }, []);

  useEffect(() => {
    if (status?.sms_count > 0 && messages.length === 0) {
      loadSms();
    }
  }, [status?.sms_count, messages.length]);

  const handleFetch = async (targetHours = hours) => {
    setLoading(true);
    try {
      const res = await fetchSms(Number(targetHours));
      if (res?.data?.status === "ok" && Array.isArray(res?.data?.data)) {
        setMessages(res.data.data);
        if (res.data.data.length > 0) {
          setSelectedMessage(res.data.data[0]);
        }
      }
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const handleCopyBody = (body, idx) => {
    if (body) {
      navigator.clipboard.writeText(body);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    }
  };

  const handleCopySelected = () => {
    if (selectedMessage?.body) {
      navigator.clipboard.writeText(selectedMessage.body);
      setCopiedSelected(true);
      setTimeout(() => setCopiedSelected(false), 1500);
    }
  };

  const filtered = messages.filter((m) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (m.address || "").toLowerCase().includes(term) ||
      (m.body || "").toLowerCase().includes(term)
    );
  });

  return (
    <>
      <Card className="border-border bg-surface flex flex-col h-full shadow-sm">
        <CardHeader className="p-3.5 pb-2.5 border-b border-border-muted flex flex-row items-center justify-between">
          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <div className="p-1.5 rounded-md bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <MessageSquare className="w-3.5 h-3.5" />
            </div>
            <div>
              <CardTitle className="text-xs font-mono font-semibold uppercase tracking-wide text-main">
                {t("sms.title")}
              </CardTitle>
            </div>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-input border border-border text-teal-400 font-semibold">
              {messages.length}
            </span>
          </div>

          <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
            <Button
              size="sm"
              variant="outline"
              disabled={loading || !status?.client_connected}
              onClick={() => handleFetch(hours)}
              className="h-7 px-2 text-[11px] font-mono"
            >
              <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
              {t("sms.fetch")}
            </Button>

            {messages.length > 0 && (
              <a href="/api/sms/download" download="sms_messages.json">
                <Button size="sm" variant="ghost" className="h-7 px-2 text-[11px]" title="Export JSON">
                  <Download className="w-3 h-3" />
                </Button>
              </a>
            )}

            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (!selectedMessage && messages.length > 0) {
                  setSelectedMessage(messages[0]);
                }
                setIsModalOpen(true);
              }}
              className="h-7 px-2 text-xs font-mono text-teal-400 hover:text-teal-300 hover:bg-teal-950/20 border border-teal-500/20"
              title={t("sms.expand")}
            >
              <Maximize2 className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1" />
              {t("sms.expand")}
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-3.5 space-y-2.5 flex-1 flex flex-col">
          <div className="flex flex-col gap-2">
            <div className="flex items-center bg-input px-2.5 py-1.5 rounded-lg border border-border text-xs focus-within:border-teal-500/50 transition-colors">
              <Search className="w-3.5 h-3.5 text-dim mr-2 rtl:mr-0 rtl:ml-2 flex-shrink-0" />
              <input
                type="text"
                placeholder={t("sms.search_placeholder")}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-transparent text-main placeholder-dim w-full focus:outline-none text-xs font-sans"
              />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm("")}
                  className="text-dim hover:text-main text-xs px-1"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            <div className="flex items-center justify-between gap-2 text-xs">
              <div className="flex bg-input p-0.5 rounded-lg border border-border font-mono text-[10px]">
                {[24, 72, 168].map((h) => (
                  <button
                    key={h}
                    type="button"
                    onClick={() => {
                      setHours(h);
                      handleFetch(h);
                    }}
                    className={`px-2 py-1 rounded font-medium transition-colors ${
                      Number(hours) === h ? "bg-surface-elevated text-main font-semibold shadow-sm" : "text-dim hover:text-main"
                    }`}
                  >
                    {h === 24 ? "24h" : h === 72 ? "3d" : "7d"}
                  </button>
                ))}
              </div>

              <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                <div className="relative flex items-center bg-input rounded-lg border border-border focus-within:border-teal-500/60 transition-colors">
                  <input
                    type="number"
                    min="1"
                    value={hours}
                    onChange={(e) => setHours(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleFetch(Number(hours) || 24);
                    }}
                    className="w-20 pl-3 pr-8 py-1.5 bg-transparent text-main text-xs font-mono focus:outline-none text-right rtl:text-left rtl:pr-3 rtl:pl-8"
                    placeholder="24"
                  />
                  <span className="absolute right-3 rtl:right-auto rtl:left-3 text-[11px] text-dim pointer-events-none font-mono select-none">
                    h
                  </span>
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  disabled={loading || !status?.client_connected}
                  onClick={() => handleFetch(Number(hours) || 24)}
                  className="h-7 px-2.5 text-xs font-mono text-teal-400 hover:text-teal-300 border-teal-500/30 hover:bg-teal-950/20"
                  title="Fetch SMS for custom timeframe"
                >
                  <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
                  {t("sms.fetch")}
                </Button>
              </div>
            </div>
          </div>

          <div className="flex-1 max-h-[280px] overflow-y-auto rounded-lg border border-border divide-y divide-border/50 bg-input">
            {filtered.length > 0 ? (
              filtered.map((m, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    setSelectedMessage(m);
                    setIsModalOpen(true);
                  }}
                  className="p-3 hover:bg-surface-elevated/70 transition-colors cursor-pointer text-xs space-y-1 group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2 rtl:space-x-reverse">
                      <Badge
                        variant={m.type === 1 ? "success" : "secondary"}
                        className="text-[9px] px-1.5 py-0 font-mono"
                      >
                        {m.type === 1 ? (
                          <>
                            <ArrowDownLeft className="w-2.5 h-2.5 mr-0.5 rtl:mr-0 rtl:ml-0.5 inline" />
                            {t("sms.in")}
                          </>
                        ) : (
                          <>
                            <ArrowUpRight className="w-2.5 h-2.5 mr-0.5 rtl:mr-0 rtl:ml-0.5 inline" />
                            {t("sms.out")}
                          </>
                        )}
                      </Badge>
                      <span className="font-mono font-semibold text-main text-xs">
                        {m.address}
                      </span>
                    </div>

                    <span className="text-dim text-[10px] font-mono">
                      {m.date ? new Date(Number(m.date)).toLocaleDateString() : "—"}
                    </span>
                  </div>

                  <p className="text-dim font-sans text-xs line-clamp-2 leading-relaxed">
                    {m.body}
                  </p>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-xs text-dim font-mono">
                {messages.length === 0 ? t("sms.no_records") : t("sms.no_matching")}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-6">
          <div className="bg-surface border border-border rounded-2xl w-full max-w-6xl h-[88vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 text-main">
            <div className="p-4 px-6 border-b border-border flex items-center justify-between bg-header">
              <div className="flex items-center space-x-3 rtl:space-x-reverse">
                <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/30">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold tracking-tight text-main flex items-center gap-2">
                    {t("sms.studio_title")}
                    <span className="px-2 py-0.5 rounded-full bg-teal-500/10 border border-teal-500/20 text-teal-400 text-[10px] font-mono">
                      {filtered.length} / {messages.length}
                    </span>
                  </h3>
                  <p className="text-xs text-dim">{t("sms.studio_desc")}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2 rtl:space-x-reverse">
                {messages.length > 0 && (
                  <a href="/api/sms/download" download="sms_messages.json">
                    <Button size="sm" variant="outline" className="h-8 text-xs font-mono">
                      <Download className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                      {t("sms.export_json")}
                    </Button>
                  </a>
                )}

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setIsModalOpen(false)}
                  className="h-8 w-8 p-0 text-dim hover:text-main rounded-lg"
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </div>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden">
              <div className="md:col-span-4 border-r border-border bg-background flex flex-col h-full rtl:border-r-0 rtl:border-l">
                <div className="p-3 border-b border-border-muted space-y-2">
                  <div className="flex items-center bg-input px-3 py-1.5 rounded-lg border border-border text-xs focus-within:border-teal-500/50">
                    <Search className="w-3.5 h-3.5 text-dim mr-2 rtl:mr-0 rtl:ml-2 flex-shrink-0" />
                    <input
                      type="text"
                      placeholder={t("sms.filter_conversations")}
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="bg-transparent text-main placeholder-dim w-full focus:outline-none text-xs"
                    />
                    {searchTerm && (
                      <button
                        type="button"
                        onClick={() => setSearchTerm("")}
                        className="text-dim hover:text-main"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="flex bg-input p-0.5 rounded-lg border border-border text-[11px] font-mono">
                      {[
                        { label: "24h", val: 24 },
                        { label: "3d", val: 72 },
                        { label: "7d", val: 168 },
                        { label: "30d", val: 720 },
                      ].map((p) => (
                        <button
                          key={p.val}
                          type="button"
                          onClick={() => {
                            setHours(p.val);
                            handleFetch(p.val);
                          }}
                          className={`flex-1 py-1 rounded text-center transition-colors ${
                            Number(hours) === p.val
                              ? "bg-surface-elevated text-main font-semibold shadow-sm"
                              : "text-dim hover:text-main"
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center space-x-2 rtl:space-x-reverse">
                      <div className="relative flex-1 flex items-center bg-input rounded-lg border border-border focus-within:border-teal-500/60 transition-colors">
                        <input
                          type="number"
                          min="1"
                          value={hours}
                          onChange={(e) => setHours(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleFetch(Number(hours) || 24);
                          }}
                          className="w-full pl-4 pr-16 py-1.5 bg-transparent text-main text-xs font-mono focus:outline-none"
                          placeholder="24"
                        />
                        <span className="absolute right-3.5 rtl:right-auto rtl:left-3.5 text-xs text-dim pointer-events-none font-mono select-none">
                          {t("sms.hours")}
                        </span>
                      </div>

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={loading || !status?.client_connected}
                        onClick={() => handleFetch(Number(hours) || 24)}
                        className="h-7 px-3 text-xs font-mono text-teal-400 hover:text-teal-300 border-teal-500/30 hover:bg-teal-950/20"
                      >
                        <RefreshCw className={`w-3 h-3 mr-1.5 rtl:mr-0 rtl:ml-1.5 ${loading ? "animate-spin" : ""}`} />
                        {t("sms.fetch")}
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto divide-y divide-border/40">
                  {filtered.length > 0 ? (
                    filtered.map((m, idx) => {
                      const isSelected = selectedMessage === m;
                      return (
                        <div
                          key={idx}
                          onClick={() => setSelectedMessage(m)}
                          className={`p-3.5 transition-colors cursor-pointer text-xs space-y-1.5 border-l-2 rtl:border-l-0 rtl:border-r-2 ${
                            isSelected
                              ? "bg-surface-elevated border-l-teal-400 rtl:border-r-teal-400 text-main font-medium"
                              : "bg-transparent border-l-transparent rtl:border-r-transparent text-dim hover:bg-surface-elevated/50"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                              <Badge
                                variant={m.type === 1 ? "success" : "secondary"}
                                className="text-[9px] px-1.5 py-0 font-mono"
                              >
                                {m.type === 1 ? t("sms.in") : t("sms.out")}
                              </Badge>
                              <span className="font-mono font-semibold text-main">
                                {m.address}
                              </span>
                            </div>

                            <span className="text-[10px] font-mono text-dim">
                              {m.date ? new Date(Number(m.date)).toLocaleDateString() : ""}
                            </span>
                          </div>

                          <p className="text-dim line-clamp-2 text-[11px] leading-relaxed">
                            {m.body}
                          </p>
                        </div>
                      );
                    })
                  ) : (
                    <div className="py-16 text-center text-xs text-dim font-mono">
                      {t("sms.no_matching")}
                    </div>
                  )}
                </div>
              </div>

              <div className="md:col-span-8 bg-surface flex flex-col h-full overflow-hidden">
                {selectedMessage ? (
                  <div className="flex flex-col h-full">
                    <div className="p-5 border-b border-border bg-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                      <div className="flex items-center space-x-3 rtl:space-x-reverse">
                        <div className="w-10 h-10 rounded-xl bg-surface-elevated border border-border flex items-center justify-center text-dim shadow-inner">
                          <User className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center space-x-2 rtl:space-x-reverse">
                            <span className="font-mono font-bold text-base text-main">
                              {selectedMessage.address}
                            </span>
                            <Badge
                              variant={selectedMessage.type === 1 ? "success" : "secondary"}
                              className="text-[10px] font-mono px-2 py-0.5"
                            >
                              {selectedMessage.type === 1 ? t("sms.incoming") : t("sms.outgoing")}
                            </Badge>
                          </div>
                          <p className="text-xs text-dim flex items-center gap-1.5 mt-0.5 font-mono">
                            <Clock className="w-3 h-3 text-dim" />
                            {selectedMessage.date ? new Date(Number(selectedMessage.date)).toLocaleString() : "—"}
                          </p>
                        </div>
                      </div>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleCopySelected}
                        className="h-8 px-3 text-xs font-mono self-start sm:self-auto"
                      >
                        {copiedSelected ? (
                          <>
                            <Check className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5 text-emerald-400" />
                            {t("sms.copied")}
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                            {t("sms.copy_text")}
                          </>
                        )}
                      </Button>
                    </div>

                    <div className="flex-1 p-6 sm:p-10 overflow-y-auto bg-background flex flex-col justify-start">
                      <div className="max-w-3xl w-full mx-auto space-y-4">
                        <div className="text-[11px] font-mono uppercase tracking-widest text-dim">
                          {t("sms.raw_payload")}
                        </div>

                        <div className="p-8 sm:p-10 rounded-2xl bg-surface border border-border shadow-xl space-y-6">
                          <p className="text-base sm:text-lg text-main leading-relaxed font-sans select-text whitespace-pre-wrap">
                            {selectedMessage.body}
                          </p>

                          <div className="pt-6 border-t border-border flex flex-wrap items-center justify-between text-xs text-dim font-mono gap-2">
                            <span>{t("sms.length")}: {selectedMessage.body?.length || 0} {t("sms.characters")}</span>
                            <span>{t("sms.direction")}: {selectedMessage.type === 1 ? t("sms.rx") : t("sms.tx")}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-dim">
                    <MessageSquare className="w-12 h-12 text-dim mb-3" />
                    <p className="text-sm font-medium text-main">{t("sms.no_selected")}</p>
                    <p className="text-xs text-dim max-w-xs mt-1">
                      {t("sms.no_selected_desc")}
                    </p>
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
