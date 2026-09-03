import React, { useState, useEffect, useMemo, useRef } from "react";
import { fetchSms, getLatestSms, getContactsList, getAuthenticatedUrl } from "../api/client";
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
  CheckCheck,
  Maximize2,
  X,
  Clock,
  User,
  Phone,
  Shield,
} from "lucide-react";

function getDigits(str) {
  if (!str) return "";
  return String(str).replace(/\D/g, "");
}

function matchContact(address, contacts) {
  if (!address || !contacts || !Array.isArray(contacts) || contacts.length === 0) return null;
  const rawAddr = String(address).trim().toLowerCase();
  const digitsAddr = getDigits(address);

  for (let i = 0; i < contacts.length; i++) {
    const c = contacts[i];
    if (!c) continue;
    const phone = c.number || c.phone || c.data1 || "";
    const name = c.name || c.display_name || "";

    if (phone) {
      const rawPhone = String(phone).trim().toLowerCase();
      if (rawPhone === rawAddr) return c;

      const digitsPhone = getDigits(phone);
      if (digitsPhone && digitsAddr) {
        if (digitsPhone === digitsAddr) return c;
        if (digitsPhone.length >= 7 && digitsAddr.length >= 7) {
          const compLen = Math.min(Math.min(digitsPhone.length, digitsAddr.length), 10);
          if (digitsPhone.slice(-compLen) === digitsAddr.slice(-compLen)) {
            return c;
          }
        }
      }
    }

    if (name && rawAddr && name.toLowerCase() === rawAddr) {
      return c;
    }
  }
  return null;
}

const AVATAR_COLORS = [
  "bg-teal-600 text-teal-100",
  "bg-blue-600 text-blue-100",
  "bg-indigo-600 text-indigo-100",
  "bg-purple-600 text-purple-100",
  "bg-emerald-600 text-emerald-100",
  "bg-rose-600 text-rose-100",
  "bg-amber-600 text-amber-100",
  "bg-cyan-600 text-cyan-100",
];

function getAvatarClass(str) {
  if (!str) return AVATAR_COLORS[0];
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = str.charCodeAt(i) + ((h << 5) - h);
  }
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

function formatTime(dateVal) {
  if (!dateVal) return "";
  try {
    const d = typeof dateVal === "number" ? new Date(dateVal) : new Date(Number(dateVal));
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return "";
  }
}

function formatDate(dateVal) {
  if (!dateVal) return "";
  try {
    const d = typeof dateVal === "number" ? new Date(dateVal) : new Date(Number(dateVal));
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) {
      return "Yesterday";
    }
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch (e) {
    return "";
  }
}

function formatDateDivider(dateVal, t) {
  if (!dateVal) return "";
  try {
    const d = typeof dateVal === "number" ? new Date(dateVal) : new Date(Number(dateVal));
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    if (d.toDateString() === now.toDateString()) return t("sms.today");
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return t("sms.yesterday");
    return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  } catch (e) {
    return "";
  }
}

function isDifferentDay(d1, d2) {
  if (!d1 || !d2) return true;
  try {
    const date1 = typeof d1 === "number" ? new Date(d1) : new Date(Number(d1));
    const date2 = typeof d2 === "number" ? new Date(d2) : new Date(Number(d2));
    return date1.toDateString() !== date2.toDateString();
  } catch (e) {
    return false;
  }
}

export default function SmsManager({ status, onRefresh }) {
  const { t } = useTranslation();
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedAddress, setSelectedAddress] = useState(null);
  const [copiedMsgIdx, setCopiedMsgIdx] = useState(null);
  const [copiedPhone, setCopiedPhone] = useState(false);
  const [copiedChat, setCopiedChat] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const chatEndRef = useRef(null);

  const loadSms = async () => {
    try {
      const res = await getLatestSms();
      if (Array.isArray(res.data)) {
        setMessages(res.data);
      }
    } catch (e) {}
  };

  const loadContacts = async () => {
    try {
      const res = await getContactsList();
      if (res?.data?.contacts && Array.isArray(res.data.contacts)) {
        setContacts(res.data.contacts);
      }
    } catch (e) {}
  };

  useEffect(() => {
    loadSms();
    loadContacts();
  }, []);

  useEffect(() => {
    if (status?.sms_count > 0 && messages.length === 0) {
      loadSms();
    }
    if ((status?.has_contacts || status?.contacts_count > 0) && contacts.length === 0) {
      loadContacts();
    }
  }, [status?.sms_count, status?.has_contacts, status?.contacts_count, messages.length, contacts.length]);

  const handleFetch = async (targetHours = hours) => {
    setLoading(true);
    try {
      const res = await fetchSms(Number(targetHours));
      if (res?.data?.status === "ok" && Array.isArray(res?.data?.data)) {
        setMessages(res.data.data);
      }
      await loadContacts();
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const handleCopyMessage = (body, id) => {
    if (body) {
      navigator.clipboard.writeText(body);
      setCopiedMsgIdx(id);
      setTimeout(() => setCopiedMsgIdx(null), 1500);
    }
  };

  const handleCopyPhone = (phone) => {
    if (phone) {
      navigator.clipboard.writeText(phone);
      setCopiedPhone(true);
      setTimeout(() => setCopiedPhone(false), 1500);
    }
  };

  const handleCopyChat = (thread) => {
    if (!thread || !thread.messages.length) return;
    const lines = thread.messages.map((m) => {
      const sender = m.type === 1 ? (thread.displayName || thread.address) : "You";
      const time = m.date ? new Date(Number(m.date)).toLocaleString() : "";
      return `[${time}] ${sender}: ${m.body}`;
    });
    navigator.clipboard.writeText(lines.join("\n"));
    setCopiedChat(true);
    setTimeout(() => setCopiedChat(false), 1500);
  };

  const threads = useMemo(() => {
    const map = new Map();

    for (let i = 0; i < messages.length; i++) {
      const m = messages[i];
      const addr = m.address || "Unknown";
      if (!map.has(addr)) {
        const contact = matchContact(addr, contacts);
        const name = contact ? (contact.name || contact.display_name) : null;
        map.set(addr, {
          address: addr,
          contact,
          displayName: name || addr,
          displayNumber: addr,
          hasContact: Boolean(name),
          messages: [],
          lastMessage: m,
          lastDate: Number(m.date) || 0,
        });
      }
      const thread = map.get(addr);
      thread.messages.push({ ...m, _id: `${addr}_${i}` });
      const mDate = Number(m.date) || 0;
      if (mDate >= thread.lastDate) {
        thread.lastDate = mDate;
        thread.lastMessage = m;
      }
    }

    const threadList = Array.from(map.values());
    for (const thread of threadList) {
      thread.messages.sort((a, b) => (Number(a.date) || 0) - (Number(b.date) || 0));
    }

    threadList.sort((a, b) => b.lastDate - a.lastDate);
    return threadList;
  }, [messages, contacts]);

  const filteredThreads = useMemo(() => {
    if (!searchTerm.trim()) return threads;
    const term = searchTerm.toLowerCase();
    return threads.filter((t) => {
      if ((t.displayName || "").toLowerCase().includes(term)) return true;
      if ((t.address || "").toLowerCase().includes(term)) return true;
      return t.messages.some((m) => (m.body || "").toLowerCase().includes(term));
    });
  }, [threads, searchTerm]);

  const activeThread = useMemo(() => {
    if (selectedAddress) {
      const found = filteredThreads.find((t) => t.address === selectedAddress) || threads.find((t) => t.address === selectedAddress);
      if (found) return found;
    }
    return filteredThreads[0] || threads[0] || null;
  }, [selectedAddress, filteredThreads, threads]);

  useEffect(() => {
    if (isModalOpen && activeThread && chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedAddress, isModalOpen, messages]);

  const openThreadModal = (addr) => {
    setSelectedAddress(addr);
    setIsModalOpen(true);
  };

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
            {messages.length > 0 && (
              <a href={getAuthenticatedUrl("/sms/download")} download="sms_messages.json">
                <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-dim hover:text-main" title="Export JSON">
                  <Download className="w-3.5 h-3.5" />
                </Button>
              </a>
            )}

            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (!selectedAddress && threads.length > 0) {
                  setSelectedAddress(threads[0].address);
                }
                setIsModalOpen(true);
              }}
              className="h-7 w-7 p-0 text-teal-400 hover:text-teal-300 hover:bg-teal-950/20 border border-teal-500/20"
              title={t("sms.expand")}
            >
              <Maximize2 className="w-3.5 h-3.5" />
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

            <div className="flex flex-wrap items-center justify-between gap-1.5 text-xs">
              <div className="flex items-center space-x-1 rtl:space-x-reverse">
                <div className="flex bg-input p-0.5 rounded-lg border border-border font-mono text-[10px]">
                  {[24, 72, 168].map((h) => (
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
                      {h === 24 ? "24h" : h === 72 ? "3d" : "7d"}
                    </button>
                  ))}
                </div>

                <div className="relative flex items-center bg-input rounded-lg border border-border focus-within:border-teal-500/60 transition-colors">
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
                variant="outline"
                disabled={loading || !status?.client_connected}
                onClick={() => handleFetch(Number(hours) || 24)}
                className="h-7 px-2.5 text-xs font-mono text-teal-400 hover:text-teal-300 border-teal-500/30 hover:bg-teal-950/20 whitespace-nowrap flex-shrink-0"
              >
                <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
                {t("sms.fetch")}
              </Button>
            </div>
          </div>

          <div className="flex-1 max-h-[280px] overflow-y-auto rounded-lg border border-border divide-y divide-border/50 bg-input overscroll-contain">
            {filteredThreads.length > 0 ? (
              filteredThreads.map((thread, idx) => {
                const initial = (thread.displayName || "?").charAt(0).toUpperCase();
                const avatarColor = getAvatarClass(thread.displayName || thread.address);
                const lastMsg = thread.lastMessage;
                const isInbound = lastMsg?.type === 1;

                return (
                  <div
                    key={idx}
                    onClick={() => openThreadModal(thread.address)}
                    className="p-3 hover:bg-surface-elevated/70 transition-colors cursor-pointer text-xs space-y-1.5 group"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2.5 rtl:space-x-reverse min-w-0">
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-[11px] flex-shrink-0 ${avatarColor}`}>
                          {initial}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                            <span className="font-semibold text-main text-xs truncate">
                              {thread.displayName}
                            </span>
                            {thread.hasContact && (
                              <span className="font-mono text-[10px] text-dim truncate">
                                ({thread.address})
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-1.5 rtl:space-x-reverse flex-shrink-0">
                        <span className="text-dim text-[10px] font-mono">
                          {formatDate(thread.lastDate)}
                        </span>
                        <Badge variant="secondary" className="text-[9px] px-1 py-0 font-mono">
                          {thread.messages.length}
                        </Badge>
                      </div>
                    </div>

                    <div className="flex items-center space-x-1.5 rtl:space-x-reverse text-dim">
                      {isInbound ? (
                        <ArrowDownLeft className="w-3 h-3 text-teal-400 flex-shrink-0" />
                      ) : (
                        <ArrowUpRight className="w-3 h-3 text-sky-400 flex-shrink-0" />
                      )}
                      <p className="font-sans text-xs line-clamp-1 leading-relaxed truncate">
                        {lastMsg?.body || "—"}
                      </p>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="py-8 text-center text-xs text-dim font-mono">
                {messages.length === 0 ? t("sms.no_records") : t("sms.no_matching")}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-2 sm:p-4 md:p-6">
          <div className="bg-surface border border-border rounded-2xl w-full max-w-6xl h-[90vh] max-h-[90vh] flex flex-col shadow-2xl overflow-hidden text-main">
            <div className="p-3.5 sm:p-4 px-5 border-b border-border flex items-center justify-between bg-header flex-shrink-0">
              <div className="flex items-center space-x-3 rtl:space-x-reverse">
                <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/30">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold tracking-tight text-main flex items-center gap-2">
                    {t("sms.studio_title")}
                    <span className="px-2 py-0.5 rounded-full bg-teal-500/10 border border-teal-500/20 text-teal-400 text-[10px] font-mono">
                      {filteredThreads.length} {t("sms.conversations")} • {messages.length} {t("sms.messages")}
                    </span>
                  </h3>
                  <p className="text-xs text-dim">{t("sms.studio_desc")}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2 rtl:space-x-reverse">
                {messages.length > 0 && (
                  <a href={getAuthenticatedUrl("/sms/download")} download="sms_messages.json">
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

            <div className="flex-1 min-h-0 flex flex-col md:flex-row overflow-hidden">
              <div className="w-full md:w-5/12 lg:w-4/12 border-r border-border bg-background/50 flex flex-col h-full min-h-0 overflow-hidden rtl:border-r-0 rtl:border-l flex-shrink-0">
                <div className="p-3 border-b border-border-muted space-y-2 flex-shrink-0">
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

                <div className="flex-1 min-h-0 overflow-y-auto divide-y divide-border/30 overscroll-contain">
                  {filteredThreads.length > 0 ? (
                    filteredThreads.map((tItem, idx) => {
                      const isSelected = activeThread?.address === tItem.address;
                      const initial = (tItem.displayName || "?").charAt(0).toUpperCase();
                      const avatarColor = getAvatarClass(tItem.displayName || tItem.address);
                      const lastMsg = tItem.lastMessage;
                      const isInbound = lastMsg?.type === 1;

                      return (
                        <div
                          key={idx}
                          onClick={() => setSelectedAddress(tItem.address)}
                          className={`p-3.5 transition-colors cursor-pointer text-xs space-y-1.5 border-l-2 rtl:border-l-0 rtl:border-r-2 ${
                            isSelected
                              ? "bg-surface-elevated border-l-teal-400 rtl:border-r-teal-400 text-main font-medium shadow-xs"
                              : "bg-transparent border-l-transparent rtl:border-r-transparent text-dim hover:bg-surface-elevated/50"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2.5 rtl:space-x-reverse min-w-0">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm ${avatarColor}`}>
                                {initial}
                              </div>
                              <div className="min-w-0">
                                <span className="font-semibold text-main block text-xs truncate">
                                  {tItem.displayName}
                                </span>
                                {tItem.hasContact && (
                                  <span className="font-mono text-[11px] text-dim block truncate">
                                    {tItem.address}
                                  </span>
                                )}
                              </div>
                            </div>

                            <div className="flex flex-col items-end space-y-1 flex-shrink-0">
                              <span className="text-[10px] font-mono text-dim">
                                {formatDate(tItem.lastDate)}
                              </span>
                              <Badge variant={isSelected ? "success" : "secondary"} className="text-[9px] px-1.5 py-0 font-mono">
                                {tItem.messages.length}
                              </Badge>
                            </div>
                          </div>

                          <div className="flex items-center space-x-1.5 rtl:space-x-reverse text-dim">
                            {isInbound ? (
                              <ArrowDownLeft className="w-3 h-3 text-teal-400 flex-shrink-0" />
                            ) : (
                              <ArrowUpRight className="w-3 h-3 text-sky-400 flex-shrink-0" />
                            )}
                            <p className="line-clamp-1 text-[11px] leading-relaxed truncate font-sans">
                              {lastMsg?.body || "—"}
                            </p>
                          </div>
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

              <div className="w-full md:w-7/12 lg:w-8/12 bg-surface flex flex-col h-full min-h-0 overflow-hidden">
                {activeThread ? (
                  <div className="flex flex-col h-full min-h-0">
                    <div className="p-3.5 sm:p-4 px-5 border-b border-border bg-header flex items-center justify-between gap-3 flex-shrink-0">
                      <div className="flex items-center space-x-3 rtl:space-x-reverse min-w-0">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm shadow-md flex-shrink-0 ${getAvatarClass(activeThread.displayName || activeThread.address)}`}>
                          {(activeThread.displayName || "?").charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center space-x-2 rtl:space-x-reverse">
                            <span className="font-bold text-sm sm:text-base text-main truncate">
                              {activeThread.displayName}
                            </span>
                            {activeThread.hasContact && (
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0 font-sans border-teal-500/30 text-teal-400 flex items-center gap-1">
                                <User className="w-2.5 h-2.5" />
                                {t("sms.saved_contact")}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center space-x-2 rtl:space-x-reverse text-xs text-dim font-mono mt-0.5">
                            <span className="flex items-center gap-1">
                              <Phone className="w-3 h-3 text-dim" />
                              {activeThread.address}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleCopyPhone(activeThread.address)}
                              className="text-dim hover:text-main transition-colors p-0.5"
                              title={t("sms.copy_number")}
                            >
                              {copiedPhone ? (
                                <Check className="w-3 h-3 text-emerald-400" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 rtl:space-x-reverse flex-shrink-0">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleCopyChat(activeThread)}
                          className="h-8 px-2.5 text-xs font-mono"
                        >
                          {copiedChat ? (
                            <>
                              <Check className="w-3.5 h-3.5 mr-1 rtl:mr-0 rtl:ml-1 text-emerald-400" />
                              {t("sms.chat_copied")}
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5 mr-1 rtl:mr-0 rtl:ml-1" />
                              {t("sms.copy_chat")}
                            </>
                          )}
                        </Button>
                        <Badge variant="secondary" className="text-xs font-mono px-2 py-1">
                          {activeThread.messages.length} {t("sms.messages")}
                        </Badge>
                      </div>
                    </div>

                    <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-4 sm:p-6 space-y-3 bg-background/40">
                      {activeThread.messages.map((msg, idx) => {
                        const prevMsg = idx > 0 ? activeThread.messages[idx - 1] : null;
                        const showDateDivider = isDifferentDay(msg.date, prevMsg?.date);
                        const isInbound = msg.type === 1;

                        return (
                          <React.Fragment key={msg._id || idx}>
                            {showDateDivider && (
                              <div className="flex justify-center my-3">
                                <span className="text-[10px] font-mono font-medium px-3 py-0.5 rounded-full bg-surface-elevated border border-border text-dim shadow-xs">
                                  {formatDateDivider(msg.date, t)}
                                </span>
                              </div>
                            )}

                            {isInbound ? (
                              <div className="flex flex-col items-start max-w-[85%] sm:max-w-[75%] space-y-1">
                                <div className="p-3.5 sm:p-4 rounded-2xl rounded-tl-xs bg-surface-elevated border border-border/80 text-main shadow-sm text-xs sm:text-sm font-sans leading-relaxed whitespace-pre-wrap select-text break-words">
                                  {msg.body}
                                  <div className="flex items-center justify-between gap-3 mt-2 pt-1 border-t border-border/40 text-[10px] text-dim font-mono">
                                    <span className="flex items-center gap-1">
                                      <ArrowDownLeft className="w-3 h-3 text-teal-400" />
                                      {formatTime(msg.date)}
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => handleCopyMessage(msg.body, msg._id || idx)}
                                      className="hover:text-main transition-colors p-0.5"
                                      title={t("sms.copy_text")}
                                    >
                                      {copiedMsgIdx === (msg._id || idx) ? (
                                        <Check className="w-3 h-3 text-emerald-400" />
                                      ) : (
                                        <Copy className="w-3 h-3 text-dim" />
                                      )}
                                    </button>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div className="flex flex-col items-end max-w-[85%] sm:max-w-[75%] space-y-1 self-end ml-auto rtl:ml-0 rtl:mr-auto">
                                <div className="p-3.5 sm:p-4 rounded-2xl rounded-tr-xs bg-teal-600 dark:bg-teal-600 border border-teal-500/40 text-white shadow-sm text-xs sm:text-sm font-sans leading-relaxed whitespace-pre-wrap select-text break-words">
                                  <span className="text-white/95">{msg.body}</span>
                                  <div className="flex items-center justify-between gap-3 mt-2 pt-1 border-t border-teal-500/30 text-[10px] text-teal-200/90 font-mono">
                                    <span className="flex items-center gap-1 text-teal-200">
                                      <ArrowUpRight className="w-3 h-3" />
                                      {formatTime(msg.date)}
                                    </span>
                                    <div className="flex items-center gap-1.5">
                                      <CheckCheck className="w-3.5 h-3.5 text-teal-200" />
                                      <button
                                        type="button"
                                        onClick={() => handleCopyMessage(msg.body, msg._id || idx)}
                                        className="hover:text-white transition-colors p-0.5 text-teal-200"
                                        title={t("sms.copy_text")}
                                      >
                                        {copiedMsgIdx === (msg._id || idx) ? (
                                          <Check className="w-3 h-3 text-white" />
                                        ) : (
                                          <Copy className="w-3 h-3" />
                                        )}
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            )}
                          </React.Fragment>
                        );
                      })}
                      <div ref={chatEndRef} />
                    </div>

                    <div className="p-2.5 px-4 border-t border-border bg-header/90 flex items-center justify-between text-[11px] text-dim font-mono flex-shrink-0">
                      <span className="flex items-center gap-1.5 text-dim truncate">
                        <Shield className="w-3.5 h-3.5 text-teal-400 flex-shrink-0" />
                        <span className="truncate">{t("sms.read_only_notice")}</span>
                      </span>
                      <span className="text-dim flex-shrink-0">
                        {activeThread.messages.length} {t("sms.messages")}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-dim">
                    <MessageSquare className="w-12 h-12 text-dim mb-3 opacity-40" />
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
