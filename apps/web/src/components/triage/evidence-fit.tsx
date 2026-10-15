"use client";

import { useI18n } from "@/lib/i18n";

export function EvidenceFit({
  score,
  weatherScore,
}: {
  score: number | null;
  weatherScore: number | null;
}) {
  const { t } = useI18n();
  if (score === null) return null;

  const weighting =
    weatherScore === null
      ? t("analysisOnly")
      : t("weightedAnalysisWeather");

  return (
    <span
      role="img"
      aria-label={`${score}/100 ${t("evidenceFit")}. ${weighting}. ${t("notProbability")}.`}
      title={`${weighting}. ${t("notProbability")}.`}
      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
    >
      <span className="h-1.5 w-10 overflow-hidden rounded-full bg-forest-900/15" aria-hidden>
        <span className="block h-full rounded-full bg-forest-700" style={{ width: `${score}%` }} />
      </span>
      <span>{score}/100 {t("scoreFit")}</span>
      <span className="text-[10px] text-muted-foreground/80">
        {weighting}
      </span>
    </span>
  );
}