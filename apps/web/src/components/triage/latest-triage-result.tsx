"use client";

import { useEffect, useState } from "react";
import { Languages, LoaderCircle, RotateCw } from "lucide-react";

import { LeafIllustration } from "@/components/brand/botanical";
import { PillLink } from "@/components/brand/pill";
import { Reveal } from "@/components/motion/reveal";
import { TriageResult } from "@/components/triage/triage-result";
import { Skeleton } from "@/components/ui/skeleton";
import { useLatestTriage } from "@/hooks/use-latest-triage";
import { translateTriage } from "@/lib/api/client";
import { useI18n } from "@/lib/i18n";
import { readTranslation, saveTranslation } from "@/lib/triage-storage";
import { cn } from "@/lib/utils";
import type { TriageResponse } from "@/types/triage";

type TranslationStatus = "original" | "translating" | "translated" | "failed" | "sample";

/** Shows the saved result in the selected language, translating AI results on demand. */
function useTranslatedTriage(result: TriageResponse | null) {
  const { language } = useI18n();
  const [translations, setTranslations] = useState<Partial<Record<string, TriageResponse>>>({});
  const [failedKey, setFailedKey] = useState<string | null>(null);

  const key = result ? `${result.report_id}:${language}` : null;
  const needsTranslation = Boolean(
    result && result.analysis_mode === "ai" && (result.response_language ?? "en") !== language,
  );
  const cached = needsTranslation && result && key
    ? translations[key] ?? readTranslation(result.report_id, language)
    : null;
  const hasCached = cached !== null;

  useEffect(() => {
    if (!needsTranslation || !result || !key || hasCached || failedKey === key) return;
    const controller = new AbortController();
    translateTriage(result, language, controller.signal)
      .then((translated) => {
        saveTranslation(translated);
        setTranslations((current) => ({ ...current, [key]: translated }));
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailedKey(key);
      });
    return () => controller.abort();
  }, [failedKey, hasCached, key, language, needsTranslation, result]);

  let status: TranslationStatus = "original";
  if (result?.analysis_mode === "mock" && language !== "en") status = "sample";
  else if (needsTranslation) status = cached ? "translated" : failedKey === key ? "failed" : "translating";

  return { shown: cached ?? result, status, retry: () => setFailedKey(null) };
}

function TranslationNotice({ status, onRetry }: { status: TranslationStatus; onRetry: () => void }) {
  const { t } = useI18n();
  if (status === "original" || status === "translated") return null;

  return (
    <p className={cn(
      "mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl px-4 py-3 text-sm sm:mt-8",
      status === "failed" ? "bg-clay-400/15 text-forest-900" : "bg-forest-900/[0.06] text-forest-800",
    )}>
      {status === "translating"
        ? <LoaderCircle className="size-4 shrink-0 animate-spin" aria-hidden />
        : <Languages className="size-4 shrink-0" aria-hidden />}
      <span className="flex-1">
        {status === "translating" ? t("translatingAnalysis") : status === "failed" ? t("translationFailed") : t("sampleEnglishOnly")}
      </span>
      {status === "failed" ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-forest-900 px-3.5 text-xs font-medium text-mint-100 transition hover:bg-forest-800 focus-visible:ring-2 focus-visible:ring-forest-900 focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          <RotateCw className="size-3.5" aria-hidden />
          {t("tryAgain")}
        </button>
      ) : null}
    </p>
  );
}

export function LatestTriageResult() {
  const { t } = useI18n();
  const stored = useLatestTriage();
  const { shown, status, retry } = useTranslatedTriage(stored.state === "ready" ? stored.result : null);

  if (stored.state === "loading") {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-6 px-5 pt-12" aria-busy="true" aria-label={t("loadingResult")}>
        <Skeleton className="h-80 w-full rounded-[28px] bg-forest-900/10" />
        <Skeleton className="h-40 w-full rounded-3xl bg-forest-900/5" />
      </div>
    );
  }

  if (stored.state === "missing") {
    return (
      <Reveal className="mx-auto flex max-w-md flex-1 flex-col items-center justify-center gap-6 px-5 py-20 text-center">
        <LeafIllustration className="h-40 text-forest-700/50" />
        <div className="space-y-2">
          <h1 className="text-3xl font-medium tracking-tight">{t("noResultTitle")}</h1>
          <p className="text-muted-foreground">{t("noResultBody")}</p>
        </div>
        <PillLink href="/report">{t("startReport")}</PillLink>
      </Reveal>
    );
  }

  return (
    <>
      <div role="status" aria-live="polite" className="mx-auto w-full max-w-6xl px-5">
        <TranslationNotice status={status} onRetry={retry} />
      </div>
      <div
        aria-busy={status === "translating"}
        className={cn("transition-opacity duration-300", status === "translating" && "pointer-events-none opacity-50")}
      >
        <TriageResult result={shown ?? stored.result} />
      </div>
    </>
  );
}
