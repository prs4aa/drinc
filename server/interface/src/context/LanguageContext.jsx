import React, { createContext, useContext, useState, useEffect } from "react";
import en from "../locales/en.json";
import fa from "../locales/fa.json";

const translations = { en, fa };

const LanguageContext = createContext({
  language: "en",
  setLanguage: () => {},
  t: (key) => key,
  isRtl: false,
});

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    return localStorage.getItem("drink_lang") || "en";
  });

  const setLanguage = (lang) => {
    setLanguageState(lang);
    localStorage.setItem("drink_lang", lang);
  };

  useEffect(() => {
    const isRtl = language === "fa";
    document.documentElement.dir = isRtl ? "rtl" : "ltr";
    document.documentElement.lang = language;
  }, [language]);

  const t = (path) => {
    if (!path) return "";
    const keys = path.split(".");
    let current = translations[language] || translations.en;
    for (const key of keys) {
      if (current && current[key] !== undefined) {
        current = current[key];
      } else {
        let fallback = translations.en;
        for (const fKey of keys) {
          if (fallback && fallback[fKey] !== undefined) {
            fallback = fallback[fKey];
          } else {
            return path;
          }
        }
        return fallback;
      }
    }
    return current;
  };

  const isRtl = language === "fa";

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, isRtl }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  return useContext(LanguageContext);
}
