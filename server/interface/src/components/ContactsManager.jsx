import React, { useState, useEffect } from "react";
import { fetchContacts, getContactsList } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  Users,
  Download,
  RefreshCw,
  Search,
  Phone,
  Copy,
  Check,
  Maximize2,
  X,
  User,
} from "lucide-react";

export default function ContactsManager({ status, onRefresh }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [contacts, setContacts] = useState([]);
  const [fetchError, setFetchError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [copiedSelected, setCopiedSelected] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);

  const loadList = async () => {
    try {
      const res = await getContactsList();
      if (res.data && res.data.contacts) {
        setContacts(res.data.contacts);
        if (res.data.contacts.length > 0 && !selectedContact) {
          setSelectedContact(res.data.contacts[0]);
        }
      }
    } catch (e) {}
  };

  useEffect(() => {
    loadList();
  }, []);

  useEffect(() => {
    if ((status?.has_contacts || status?.contacts_count > 0) && contacts.length === 0) {
      loadList();
    }
  }, [status?.has_contacts, status?.contacts_count, contacts.length]);

  const handleFetch = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await fetchContacts();
      if (res?.data?.status === "ok") {
        await loadList();
      } else {
        setFetchError(res?.data?.message || res?.data?.status || "Fetch failed");
      }
      await onRefresh();
    } catch (e) {
      setFetchError(e?.message || "Fetch failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyPhone = (phone, idx) => {
    if (phone) {
      navigator.clipboard.writeText(phone);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    }
  };

  const handleCopySelectedPhone = (phone) => {
    if (phone) {
      navigator.clipboard.writeText(phone);
      setCopiedSelected(true);
      setTimeout(() => setCopiedSelected(false), 1500);
    }
  };

  const filtered = contacts.filter((c) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    const name = (c.name || c.display_name || "").toLowerCase();
    const phone = (c.number || c.phone || c.data1 || "").toLowerCase();
    return name.includes(term) || phone.includes(term);
  });

  return (
    <>
      <Card className="border-border bg-surface flex flex-col h-full shadow-sm">
        <CardHeader className="p-3.5 pb-2.5 border-b border-border-muted flex flex-row items-center justify-between">
          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <div className="p-1.5 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Users className="w-3.5 h-3.5" />
            </div>
            <div>
              <CardTitle className="text-xs font-mono font-semibold uppercase tracking-wide text-main">
                {t("contacts.title")}
              </CardTitle>
            </div>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-input border border-border text-cyan-400 font-semibold">
              {contacts.length}
            </span>
            {fetchError && (
              <span className="text-[10px] font-mono text-rose-400">
                {fetchError}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
            <Button
              size="sm"
              variant="outline"
              disabled={loading || !status?.client_connected}
              onClick={handleFetch}
              className="h-7 px-2 text-[11px] font-mono"
            >
              <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
              {t("contacts.sync")}
            </Button>

            {status?.has_contacts && (
              <a href="/api/contacts/download" download="contacts.zip">
                <Button size="sm" variant="ghost" className="h-7 px-2 text-[11px]" title="Export ZIP">
                  <Download className="w-3 h-3" />
                </Button>
              </a>
            )}

            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (!selectedContact && contacts.length > 0) {
                  setSelectedContact(contacts[0]);
                }
                setIsModalOpen(true);
              }}
              className="h-7 w-7 p-0 text-cyan-400 hover:text-cyan-300 hover:bg-cyan-950/20 border border-cyan-500/20"
              title={t("contacts.expand")}
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-3.5 space-y-2.5 flex-1 flex flex-col">
          <div className="flex items-center bg-input px-2.5 py-1.5 rounded-lg border border-border text-xs focus-within:border-cyan-500/50 transition-colors">
            <Search className="w-3.5 h-3.5 text-dim mr-2 rtl:mr-0 rtl:ml-2 flex-shrink-0" />
            <input
              type="text"
              placeholder={t("contacts.search_placeholder")}
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

          <div className="flex-1 max-h-[280px] overflow-y-auto rounded-lg border border-border divide-y divide-border/50 bg-input">
            {filtered.length > 0 ? (
              filtered.map((c, idx) => {
                const name = c.name || c.display_name || "Unknown";
                const phone = c.number || c.phone || c.data1 || "";
                const initial = name.charAt(0).toUpperCase();

                return (
                  <div
                    key={idx}
                    onClick={() => {
                      setSelectedContact(c);
                      setIsModalOpen(true);
                    }}
                    className="flex items-center justify-between p-2.5 hover:bg-surface-elevated/70 transition-colors cursor-pointer text-xs group"
                  >
                    <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
                      <div className="w-7 h-7 rounded-full bg-surface-elevated border border-border flex items-center justify-center font-semibold text-dim text-[10px]">
                        {initial}
                      </div>
                      <div>
                        <span className="font-semibold text-main block text-xs">
                          {name}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 rtl:space-x-reverse">
                      <span className="font-mono text-[11px] text-dim">
                        {phone || "—"}
                      </span>

                      {phone && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCopyPhone(phone, idx);
                          }}
                          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-surface text-dim hover:text-main"
                          title="Copy phone"
                        >
                          {copiedIdx === idx ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="py-8 text-center text-xs text-dim font-mono">
                {contacts.length === 0 ? t("contacts.no_records") : t("contacts.no_matching")}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-6">
          <div className="bg-surface border border-border rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 text-main">
            <div className="p-4 px-6 border-b border-border flex items-center justify-between bg-header">
              <div className="flex items-center space-x-3 rtl:space-x-reverse">
                <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold tracking-tight text-main flex items-center gap-2">
                    {t("contacts.dossier_title")}
                    <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-[10px] font-mono">
                      {filtered.length} / {contacts.length}
                    </span>
                  </h3>
                  <p className="text-xs text-dim">{t("contacts.dossier_desc")}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2 rtl:space-x-reverse">
                {status?.has_contacts && (
                  <a href="/api/contacts/download" download="contacts.zip">
                    <Button size="sm" variant="outline" className="h-8 text-xs font-mono">
                      <Download className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                      {t("contacts.export_zip")}
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
              <div className="md:col-span-5 border-r border-border bg-background flex flex-col h-full rtl:border-r-0 rtl:border-l">
                <div className="p-3 border-b border-border-muted">
                  <div className="flex items-center bg-input px-3 py-1.5 rounded-lg border border-border text-xs focus-within:border-cyan-500/50">
                    <Search className="w-3.5 h-3.5 text-dim mr-2 rtl:mr-0 rtl:ml-2 flex-shrink-0" />
                    <input
                      type="text"
                      placeholder={t("contacts.search_placeholder")}
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
                </div>

                <div className="flex-1 overflow-y-auto divide-y divide-border/40">
                  {filtered.length > 0 ? (
                    filtered.map((c, idx) => {
                      const name = c.name || c.display_name || "Unknown";
                      const phone = c.number || c.phone || c.data1 || "";
                      const isSelected = selectedContact === c;
                      const initial = name.charAt(0).toUpperCase();

                      return (
                        <div
                          key={idx}
                          onClick={() => setSelectedContact(c)}
                          className={`p-3 transition-colors cursor-pointer text-xs flex items-center justify-between border-l-2 rtl:border-l-0 rtl:border-r-2 ${
                            isSelected
                              ? "bg-surface-elevated border-l-cyan-400 rtl:border-r-cyan-400 text-main font-medium"
                              : "bg-transparent border-l-transparent rtl:border-r-transparent text-dim hover:bg-surface-elevated/50"
                          }`}
                        >
                          <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
                            <div className="w-8 h-8 rounded-full bg-surface-elevated border border-border flex items-center justify-center font-semibold text-dim text-xs shadow-inner">
                              {initial}
                            </div>
                            <div>
                              <span className="font-semibold text-main block text-xs">
                                {name}
                              </span>
                              <span className="font-mono text-[11px] text-dim">
                                {phone || "—"}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="py-16 text-center text-xs text-dim font-mono">
                      {t("contacts.no_matching")}
                    </div>
                  )}
                </div>
              </div>

              <div className="md:col-span-7 bg-surface flex flex-col h-full overflow-hidden">
                {selectedContact ? (
                  <div className="flex-1 p-8 sm:p-12 overflow-y-auto flex flex-col justify-center items-center text-center">
                    <div className="max-w-md w-full p-8 sm:p-10 rounded-2xl bg-surface-elevated border border-border shadow-2xl space-y-6">
                      <div className="w-20 h-20 mx-auto rounded-full bg-cyan-600 border-2 border-cyan-400/40 flex items-center justify-center text-white text-2xl font-bold shadow-lg">
                        {(selectedContact.name || selectedContact.display_name || "?").charAt(0).toUpperCase()}
                      </div>

                      <div className="space-y-1">
                        <h2 className="text-xl sm:text-2xl font-bold text-main tracking-tight">
                          {selectedContact.name || selectedContact.display_name || "Unknown Contact"}
                        </h2>
                        <span className="text-xs font-mono text-cyan-400 bg-cyan-950/30 px-2.5 py-0.5 rounded-full border border-cyan-500/20 inline-block">
                          {t("contacts.entry_id")} #{selectedContact.id || "0"}
                        </span>
                      </div>

                      <div className="p-4 rounded-xl bg-input border border-border space-y-3 font-mono">
                        <span className="text-[10px] uppercase text-dim block tracking-wider font-sans">
                          {t("contacts.primary_number")}
                        </span>
                        <div className="text-base sm:text-lg text-main font-semibold tracking-wide">
                          {selectedContact.number || selectedContact.phone || selectedContact.data1 || t("contacts.no_number")}
                        </div>

                        {(selectedContact.number || selectedContact.phone || selectedContact.data1) && (
                          <Button
                            size="sm"
                            variant="default"
                            onClick={() => handleCopySelectedPhone(selectedContact.number || selectedContact.phone || selectedContact.data1)}
                            className="w-full h-8 text-xs font-mono bg-cyan-600 hover:bg-cyan-500 text-white"
                          >
                            {copiedSelected ? (
                              <>
                                <Check className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                                {t("contacts.phone_copied")}
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                                {t("contacts.copy_phone")}
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-dim">
                    <User className="w-12 h-12 text-dim mb-3" />
                    <p className="text-sm font-medium text-main">{t("contacts.no_selected")}</p>
                    <p className="text-xs text-dim max-w-xs mt-1">
                      {t("contacts.no_selected_desc")}
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
