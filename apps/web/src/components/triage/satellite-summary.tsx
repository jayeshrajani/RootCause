"use client";

import { Satellite } from "lucide-react";

import { useI18n, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { SatelliteAnalysis, SatelliteLimitation, VegetationTrend } from "@/types/triage";

const TREND_KEYS: Record<VegetationTrend, TranslationKey> = {
  improving: "satTrendImproving",
  stable: "satTrendStable",
  declining: "satTrendDeclining",
  unknown: "satTrendUnknown",
};

const TREND_TONE: Record<VegetationTrend, string> = {
  improving: "bg-mint-300/20 text-mint-200",
  stable: "bg-mint-100/10 text-mint-200/80",
  declining: "bg-clay-400/20 text-clay-400",
  unknown: "bg-mint-100/10 text-mint-200/60",
};

const LIMITATION_KEYS: Partial<Record<SatelliteLimitation, TranslationKey>> = {
  approximate_location: "satLimitApproxLocation",
  low_vegetation: "satLimitLowVegetation",
  stale_observation: "satLimitStale",
  no_baseline: "satLimitNoBaseline",
};

function ndviKey(ndvi: number): TranslationKey {
  if (ndvi < 0.2) return "satNdviBare";
  if (ndvi < 0.4) return "satNdviSparse";
  if (ndvi < 0.6) return "satNdviModerate";
  return "satNdviDense";
}

function ndmiKey(ndmi: number): TranslationKey {
  if (ndmi < 0) return "satNdmiDry";
  if (ndmi < 0.2) return "satNdmiModerate";
  return "satNdmiGood";
}

function Gauge({ value, label, hint }: { value: number; label: string; hint: string }) {
  // NDVI/NDMI range -1..1; show 0..1 as the useful band for crops.
  const width = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-mint-200/70">{label}</span>
        <span className="font-mono text-mint-100">{value.toFixed(2)}</span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-mint-100/15" aria-hidden>
        <div className="h-full rounded-full bg-mint-300" style={{ width: `${width}%` }} />
      </div>
      <p className="text-[11px] text-mint-200/60">{hint}</p>
    </div>
  );
}

export function SatelliteSummary({ satellite }: { satellite: SatelliteAnalysis }) {
  const { language, t } = useI18n();
  const title = (
    <p className="label-caps flex items-center gap-1.5 text-mint-300/60">
      <Satellite className="size-3.5" aria-hidden />
      {t("satTitle")}
    </p>
  );

  if (satellite.status !== "available" || satellite.ndvi === null) {
    const key: TranslationKey =
      satellite.reason === "water"
        ? "satWater"
        : satellite.status === "insufficient_data"
          ? "satCloudy"
        : satellite.status === "not_requested"
          ? "satNeedsLocation"
          : satellite.status === "not_configured"
            ? "satNotConfigured"
            : "satUnavailable";
    return (
      <section className="space-y-2">
        {title}
        <p className="text-sm leading-relaxed text-mint-100/70">{t(key)}</p>
      </section>
    );
  }

  const date = satellite.observation_date
    ? new Intl.DateTimeFormat(language, { day: "numeric", month: "short" }).format(
        new Date(`${satellite.observation_date}T00:00:00`),
      )
    : null;
  const notes = satellite.limitations
    .map((item) => LIMITATION_KEYS[item])
    .filter((key): key is TranslationKey => Boolean(key));
  const explanationKey: TranslationKey | null = satellite.interpretable
    ? satellite.trend === "declining"
      ? "satExplainDeclining"
      : satellite.trend === "improving"
        ? "satExplainImproving"
        : "satExplainStable"
    : null;

  return (
    <section className="space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {title}
        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", TREND_TONE[satellite.trend])}>
          {t(TREND_KEYS[satellite.trend])}
          {satellite.ndvi_change !== null ? ` · ${satellite.ndvi_change > 0 ? "+" : ""}${satellite.ndvi_change.toFixed(2)}` : ""}
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Gauge value={satellite.ndvi} label={t("satNdvi")} hint={t(ndviKey(satellite.ndvi))} />
        {satellite.ndmi !== null ? (
          <Gauge value={satellite.ndmi} label={t("satNdmi")} hint={t(ndmiKey(satellite.ndmi))} />
        ) : null}
      </div>
      {explanationKey ? (
        <p className="text-sm leading-relaxed text-mint-100/85">{t(explanationKey)}</p>
      ) : null}
      {notes.length ? (
        <ul className="space-y-1 text-xs leading-relaxed text-mint-200/60">
          {notes.map((key) => (
            <li key={key}>• {t(key)}</li>
          ))}
        </ul>
      ) : null}
      <p className="text-[11px] text-mint-200/50">
        {[
          date ? `${t("satObserved")} ${date}` : null,
          satellite.valid_pixel_coverage !== null
            ? `${Math.round(satellite.valid_pixel_coverage * 100)}% ${t("satCloudFree")}`
            : null,
          satellite.buffer_m ? `${satellite.buffer_m} m ${t("satAroundPoint")}` : t("satFieldBoundary"),
          "Sentinel-2",
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </section>
  );
}
