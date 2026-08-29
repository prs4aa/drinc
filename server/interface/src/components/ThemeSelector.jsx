import React, { useState, useEffect, useRef } from "react";
import { ChevronDown, Check } from "lucide-react";

export const THEMES = [
  {
    id: "midnight",
    name: "Default",
    colors: ["#09090b", "#141417", "#3b82f6", "#10b981"],
  },
  {
    id: "tokyo-night",
    name: "Tokyo Night",
    colors: ["#13141f", "#1c1e2e", "#7aa2f7", "#bb9af7"],
  },
  {
    id: "catppuccin-mocha",
    name: "Catppuccin Mocha",
    colors: ["#11111b", "#1e1e2e", "#89b4fa", "#cba6f7"],
  },
  {
    id: "catppuccin-latte",
    name: "Catppuccin Latte",
    colors: ["#e6e9ef", "#ffffff", "#1e66f5", "#40a02b"],
  },
  {
    id: "everforest",
    name: "Everforest",
    colors: ["#171c1f", "#242b2f", "#a7c080", "#e69875"],
  },
  {
    id: "nord",
    name: "Nord",
    colors: ["#1e222a", "#2e3440", "#88c0d0", "#81a1c1"],
  },
  {
    id: "dracula",
    name: "Dracula",
    colors: ["#14151b", "#21222c", "#bd93f9", "#ff79c6"],
  },
  {
    id: "gruvbox",
    name: "Gruvbox Dark",
    colors: ["#161819", "#242627", "#fe8019", "#fabd2f"],
  },
  {
    id: "one-dark",
    name: "One Dark Pro",
    colors: ["#16181d", "#21252b", "#61afef", "#98c379"],
  },
  {
    id: "cyberpunk",
    name: "Cyberpunk Neon",
    colors: ["#07070e", "#121224", "#00f0ff", "#ff0055"],
  },
];

export function PaletteBoxesIcon({ colors, className = "w-3.5 h-3.5" }) {
  return (
    <svg viewBox="0 0 14 14" className={className} fill="none">
      <rect x="1" y="1" width="5" height="5" rx="1" fill={colors[0]} />
      <rect x="8" y="1" width="5" height="5" rx="1" fill={colors[1]} />
      <rect x="1" y="8" width="5" height="5" rx="1" fill={colors[2]} />
      <rect x="8" y="8" width="5" height="5" rx="1" fill={colors[3]} />
    </svg>
  );
}

export default function ThemeSelector() {
  const [currentTheme, setCurrentTheme] = useState(() => {
    return localStorage.getItem("drink_theme") || "midnight";
  });
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", currentTheme);
    localStorage.setItem("drink_theme", currentTheme);
  }, [currentTheme]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const active = THEMES.find((t) => t.id === currentTheme) || THEMES[0];

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-1.5 rtl:space-x-reverse bg-surface px-2.5 py-1 rounded-md border border-border text-xs font-mono text-main hover:bg-surface-elevated transition-colors"
        title="Switch Color Palette"
      >
        <PaletteBoxesIcon colors={active.colors} className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="hidden sm:inline text-[11px] font-medium">{active.name}</span>
        <ChevronDown className="w-3 h-3 text-dim" />
      </button>

      {isOpen && (
        <div className="absolute right-0 rtl:right-auto rtl:left-0 mt-1.5 w-52 bg-surface border border-border rounded-xl shadow-2xl py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2.5 py-1 text-[10px] uppercase font-mono tracking-wider text-dim border-b border-border">
            Color Palette
          </div>

          <div className="max-h-72 overflow-y-auto py-1 space-y-0.5">
            {THEMES.map((t) => {
              const isSelected = t.id === currentTheme;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    setCurrentTheme(t.id);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 text-xs transition-colors rounded-lg ${
                    isSelected
                      ? "bg-surface-elevated text-main font-semibold"
                      : "text-dim hover:text-main hover:bg-surface-elevated/60"
                  }`}
                >
                  <div className="flex items-center space-x-2 rtl:space-x-reverse">
                    <PaletteBoxesIcon colors={t.colors} className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="text-[11px] truncate">{t.name}</span>
                  </div>

                  {isSelected && <Check className="w-3.5 h-3.5 text-accent" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
