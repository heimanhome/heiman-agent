import i18n from "i18next";
import { initReactI18next } from "react-i18next";

function mergeLocale(mods: Record<string, unknown>): Record<string, unknown> {
  return Object.assign(
    {},
    ...Object.values(mods).map((m) => (m as { default: unknown }).default ?? m),
  );
}

const zh = mergeLocale(
  import.meta.glob("./locales/zh/*.json", { eager: true }),
);
const en = mergeLocale(
  import.meta.glob("./locales/en/*.json", { eager: true }),
);

export const LANG_KEY = "web:lang";
export type Lang = "zh" | "en";

function readLang(): Lang {
  if (typeof localStorage === "undefined") return "zh";
  const v = localStorage.getItem(LANG_KEY);
  return v === "en" ? "en" : "zh";
}

i18n.use(initReactI18next).init({
  resources: {
    zh: { app: zh },
    en: { app: en },
  },
  lng: readLang(),
  fallbackLng: "zh",
  defaultNS: "app",
  ns: ["app"],
  interpolation: { escapeValue: false },
});

function syncHtmlLang(lng: string) {
  if (typeof document !== "undefined") {
    document.documentElement.lang = lng === "en" ? "en" : "zh-CN";
  }
}
syncHtmlLang(i18n.language);
i18n.on("languageChanged", (lng) => {
  if (typeof localStorage !== "undefined") localStorage.setItem(LANG_KEY, lng);
  syncHtmlLang(lng);
});

export default i18n;
