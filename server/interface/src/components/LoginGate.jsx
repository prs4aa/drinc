import React, { useState } from "react";
import { login, setAuthToken } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import ThemeSelector from "./ThemeSelector";
import { Button } from "./ui/button";
import {
  ShieldAlert,
  RadioTower,
  Lock,
  KeyRound,
  User,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertTriangle,
  Terminal,
} from "lucide-react";

export default function LoginGate({ onLoginSuccess }) {
  const { t, language, setLanguage, isRtl } = useTranslation();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) return;

    setLoading(true);
    setError(null);

    try {
      const res = await login(username.trim(), password);
      if (res?.data?.status === "ok" && res?.data?.token) {
        setAuthToken(res.data.token);
        onLoginSuccess();
      } else {
        setError(t("auth.invalid_credentials"));
      }
    } catch (err) {
      if (err?.response?.status === 429) {
        setError(t("auth.rate_limited"));
      } else if (err?.response?.status === 401) {
        setError(t("auth.invalid_credentials"));
      } else {
        setError(t("auth.network_error"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`min-h-screen bg-background text-main flex flex-col justify-between selection:bg-accent selection:text-white ${isRtl ? "font-sans" : ""}`}>
      <header className="p-4 sm:p-6 flex items-center justify-between border-b border-border/60 bg-header/80 backdrop-blur-md">
        <div className="flex items-center space-x-3 rtl:space-x-reverse">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-b from-zinc-800 to-zinc-950 border border-zinc-700/80 flex items-center justify-center shadow-md shadow-black/40 ring-1 ring-emerald-500/20">
            <RadioTower className="w-[18px] h-[18px] text-emerald-400 drop-shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
          </div>
          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <span className="runic-text text-base tracking-widest text-main font-bold">
              {t("app.title")}
            </span>
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
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-md bg-surface border border-border rounded-2xl shadow-2xl p-6 sm:p-8 space-y-6 relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
          <div className="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="text-center space-y-2">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-surface-elevated border border-border flex items-center justify-center shadow-inner text-emerald-400 mb-4 ring-1 ring-emerald-500/30">
              <Lock className="w-7 h-7" />
            </div>
            <h1 className="text-base sm:text-lg font-mono font-bold uppercase tracking-wider text-main">
              {t("auth.title")}
            </h1>
            <p className="text-xs text-dim font-sans">
              {t("auth.subtitle")}
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/50 text-rose-300 text-xs flex items-start space-x-2.5 rtl:space-x-reverse animate-in fade-in">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400 mt-0.5" />
              <span className="leading-relaxed font-sans">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4 font-mono text-xs">
            <div className="space-y-1.5">
              <label className="text-[11px] text-dim font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-dim" />
                {t("auth.username")}
              </label>
              <div className="flex items-center bg-input border border-border rounded-xl px-3 py-2 focus-within:border-emerald-500/60 focus-within:ring-1 focus-within:ring-emerald-500/20 transition-all">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={t("auth.username_placeholder")}
                  disabled={loading}
                  autoComplete="username"
                  required
                  className="w-full bg-transparent text-main placeholder-dim/60 outline-none text-xs"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] text-dim font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <KeyRound className="w-3.5 h-3.5 text-dim" />
                {t("auth.password")}
              </label>
              <div className="flex items-center bg-input border border-border rounded-xl px-3 py-2 focus-within:border-emerald-500/60 focus-within:ring-1 focus-within:ring-emerald-500/20 transition-all">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("auth.password_placeholder")}
                  disabled={loading}
                  autoComplete="current-password"
                  required
                  className="w-full bg-transparent text-main placeholder-dim/60 outline-none text-xs"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-dim hover:text-main p-1 transition-colors"
                  title={showPassword ? t("auth.hide_password") : t("auth.show_password")}
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full h-10 mt-2 text-xs font-mono font-bold tracking-wider uppercase bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950/40 transition-all duration-150"
            >
              {loading ? (
                <>
                  <RadioTower className="w-4 h-4 mr-2 rtl:mr-0 rtl:ml-2 animate-spin" />
                  {t("auth.authenticating")}
                </>
              ) : (
                <>
                  <Lock className="w-3.5 h-3.5 mr-2 rtl:mr-0 rtl:ml-2" />
                  {t("auth.login_button")}
                </>
              )}
            </Button>
          </form>

          <div className="pt-2 border-t border-border-muted/60 text-center">
            <span className="text-[10px] font-mono text-dim block tracking-tight">
              {t("auth.security_note")}
            </span>
          </div>
        </div>
      </main>

      <footer className="p-4 text-center text-xs text-dim font-mono border-t border-border/40">
        <span>ᛊᚦᛟᚹᛁᚾᛝᚲ • ENCRYPTED GATEWAY</span>
      </footer>
    </div>
  );
}
