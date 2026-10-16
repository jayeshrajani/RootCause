"use client";

import { CloudSun, Images, Satellite } from "lucide-react";

import { cn } from "@/lib/utils";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { EvidenceContribution } from "@/types/triage";

const SIGNAL_KEYS: Record<EvidenceContribution["signal"], TranslationKey> = {
  weather: "scoreWeather",
  satellite: "scoreSatellite",
};
const EFFECT_KEYS: Record<EvidenceContribution["effect"], TranslationKey> = {
  supports: "ledgerSupports",
  weighs_against: "ledgerWeighsAgainst",
  neutral: "ledgerNeutral",
};

/** One rule-based adjustment as a compact chip, e.g. "Weather +8". */
export function LedgerChip({ item }: { item: EvidenceContribution }) {
  const { language, t } = useI18n();
  const Icon = item.signal === "weather" ? CloudSun : Satellite;
  const sign = item.points > 0 ? "+" : item.points < 0 ? "−" : "±";
  const label = `${t(SIGNAL_KEYS[item.signal])} ${sign}${Math.abs(item.points)}`;
  // Reasons are generated in English from measured values; other languages get the effect only.
  const detail = language === "en" ? item.reason : t(EFFECT_KEYS[item.effect]);
  return (
    <span
      title={detail}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium capitalize",
        item.effect === "supports" && "bg-mint-100 text-forest-800",
        item.effect === "weighs_against" && "bg-clay-400/15 text-clay-600",
        item.effect === "neutral" && "bg-forest-900/5 text-muted-foreground",
      )}
    >
      <Icon className="size-3" aria-hidden />
      {label}
      <span className="sr-only">. {detail}</span>
    </span>
  );
}

export function EvidenceFit({
  score,
  referenceScore = null,
  referenceWeight = null,
  ledger = [],
}: {
  score: number | null;
  referenceScore?: number | null;
  referenceWeight?: number | null;
  ledger?: EvidenceContribution[];
}) {
  const { language, t } = useI18n();
  if (score === null) return null;

  const referenceShare = referenceScore !== null ? (referenceWeight ?? 0) : 0;
  const percent = new Intl.NumberFormat(language, { style: "percent" });
  const weighting =
    referenceShare > 0
      ? `${percent.format((100 - referenceShare) / 100)} ${t("scoreAnalysis")} · ${percent.format(referenceShare / 100)} ${t("scoreReferences")}`
      : t("analysisOnly");
  const adjustments = ledger.filter((item) => item.points !== 0);
  const referenceText = referenceShare > 0 ? `${referenceScore}/100 ${t("referenceMatch")}` : null;
  const details = [weighting, referenceText, adjustments.length ? t("ledgerExplain") : null, t("notProbability")]
    .filter(Boolean)
    .join(". ");

  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground">
      <span
        role="img"
        aria-label={`${score}/100 ${t("evidenceFit")}. ${details}.`}
        title={`${details}.`}
        className="inline-flex items-center gap-1.5"
      >
        <span className="h-1.5 w-10 overflow-hidden rounded-full bg-forest-900/15" aria-hidden>
          <span className="block h-full rounded-full bg-forest-700" style={{ width: `${score}%` }} />
        </span>
        <span>{score}/100 {t("scoreFit")}</span>
      </span>
      {referenceText ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-mint-100 px-2 py-0.5 text-[10px] font-medium text-forest-800">
          <Images className="size-3" aria-hidden />
          {referenceText}
        </span>
      ) : null}
      {adjustments.map((item) => (
        <LedgerChip key={item.signal} item={item} />
      ))}
    </span>
  );
}