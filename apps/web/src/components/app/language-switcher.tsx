"use client";

import { Languages } from "lucide-react";

import { LANGUAGE_LABELS, LANGUAGES, useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LanguageSwitcher({ className }: { className?: string }) {
  const { language, setLanguage, t } = useI18n();

  return (
    <label className={cn("relative inline-flex h-10 items-center gap-1.5 rounded-full border border-forest-900/15 bg-white/60 px-2 text-xs text-forest-900 sm:gap-2 sm:px-3 sm:text-sm", className)}>
      <Languages className="size-4 shrink-0 text-forest-600" aria-hidden />
      <span className="sr-only">{t("language")}</span>
      <select
        aria-label={t("language")}
        value={language}
        onChange={(event) => setLanguage(event.target.value as (typeof LANGUAGES)[number])}
        className="max-w-16 appearance-none bg-transparent pr-0.5 font-medium outline-none sm:max-w-28 sm:pr-1"
      >
        {LANGUAGES.map((code) => (
          <option key={code} value={code}>
            {LANGUAGE_LABELS[code]}
          </option>
        ))}
      </select>
    </label>
  );
}