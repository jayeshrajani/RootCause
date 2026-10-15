"use client";

import { Images } from "lucide-react";

import { useI18n } from "@/lib/i18n";

export function EvidenceFit({
  score,
  weatherScore,
  referenceScore = null,
  referenceWeight = null,
}: {
  score: number | null;
  weatherScore: number | null;
  referenceScore?: number | null;
  referenceWeight?: number | null;
}) {
  const { language, t } = useI18n();
  if (score === null) return null;

  const referenceShare = referenceScore !== null ? (referenceWeight ?? 0) : 0;
  const usesReferences = referenceShare > 0;
  let weighting = weatherScore === null ? t("analysisOnly") : t("weightedAnalysisWeather");
  if (usesReferences) {
    const percent = new Intl.NumberFormat(language, { style: "percent" });
    const weatherWeight = weatherScore === null ? 0 : 10;
    const parts: [number, string][] = [
      [100 - weatherWeight - referenceShare, t("scoreAnalysis")],
      [referenceShare, t("scoreReferences")],
      [weatherWeight, t("scoreWeather")],
    ];
    weighting = parts
      .filter(([weight]) => weight > 0)
      .map(([weight, label]) => `${percent.format(weight / 100)} ${label}`)
      .join(" · ");
  }
  const referenceText = usesReferences ? `${referenceScore}/100 ${t("referenceMatch")}` : null;
  const details = [weighting, referenceText, t("notProbability")].filter(Boolean).join(". ");

  return (
    <span
      role="img"
      aria-label={`${score}/100 ${t("evidenceFit")}. ${details}.`}
      title={`${details}.`}
      className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground"
    >
      <span className="h-1.5 w-10 overflow-hidden rounded-full bg-forest-900/15" aria-hidden>
        <span className="block h-full rounded-full bg-forest-700" style={{ width: `${score}%` }} />
      </span>
      <span>{score}/100 {t("scoreFit")}</span>
      <span className="text-[10px] text-muted-foreground/80">
        {weighting}
      </span>
      {referenceText ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-mint-100 px-2 py-0.5 text-[10px] font-medium text-forest-800">
          <Images className="size-3" aria-hidden />
          {referenceText}
        </span>
      ) : null}
    </span>
  );
}