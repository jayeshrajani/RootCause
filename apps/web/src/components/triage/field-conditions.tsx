"use client";

import { CloudRain, CloudSun, Droplets, MapPin, Sun, Thermometer } from "lucide-react";

import { BotanicalPattern } from "@/components/brand/botanical";
import { SatelliteSummary } from "@/components/triage/satellite-summary";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { TriageResponse, WeatherPattern } from "@/types/triage";

const PATTERN_KEYS: Record<WeatherPattern, TranslationKey> = {
  wet: "fieldPatternWet",
  hot_dry: "fieldPatternHotDry",
  cold: "fieldPatternCold",
  humid: "fieldPatternHumid",
  dry: "fieldPatternDry",
  mild: "fieldPatternMild",
};

function Stat({ icon: Icon, value, label }: { icon: typeof Sun; value: string; label: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-mint-100/10">
        <Icon className="size-4 text-mint-300" aria-hidden />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block text-sm font-medium text-mint-100">{value}</span>
        <span className="block text-[11px] text-mint-200/60">{label}</span>
      </span>
    </div>
  );
}

/** Weather and satellite context, shown once, above the causes it helps rank. */
export function FieldConditions({ result }: { result: TriageResponse }) {
  const { language, t } = useI18n();
  const facts = result.weather_facts ?? null;
  const place = result.location_label ?? result.approximate_location;
  if (!facts && !result.satellite && !result.weather_summary) return null;
  const number = new Intl.NumberFormat(language, { maximumFractionDigits: 1 });

  return (
    <section
      aria-labelledby="field-conditions-title"
      className="relative mb-5 overflow-hidden rounded-[24px] bg-forest-900 p-5 text-mint-100 sm:p-6"
    >
      <BotanicalPattern className="text-mint-300/[0.05]" />
      <div className="relative space-y-4">
        <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id="field-conditions-title" className="text-lg font-medium">
            {t("fieldConditions")}
          </h2>
          {place ? (
            <p className="flex items-center gap-1 text-xs text-mint-200/60">
              <MapPin className="size-3" aria-hidden />
              {place}
            </p>
          ) : null}
        </header>

        <div className="grid gap-5 sm:grid-cols-2 sm:gap-6">
          <section className="space-y-3">
            <p className="label-caps flex items-center gap-1.5 text-mint-300/60">
              <CloudSun className="size-3.5" aria-hidden />
              {t("recentWeather")}
              {facts ? ` · ${facts.days} ${t("fieldDays")}` : ""}
            </p>
            {facts ? (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <Stat
                    icon={Thermometer}
                    value={`${number.format(facts.temp_min_c)}–${number.format(facts.temp_max_c)} °C`}
                    label={t("fieldTempRange")}
                  />
                  <Stat
                    icon={CloudRain}
                    value={`${number.format(facts.rain_total_mm)} mm`}
                    label={`${facts.wet_days} ${t("fieldRainyDays")}`}
                  />
                  <Stat icon={Droplets} value={`${facts.humid_days}/${facts.days}`} label={t("fieldHumidDays")} />
                  <Stat icon={Sun} value={`${facts.hot_days}/${facts.days}`} label={t("fieldHotDays")} />
                </div>
                <p className="text-sm leading-relaxed text-mint-100/85">{t(PATTERN_KEYS[facts.pattern])}</p>
              </>
            ) : (
              <p className="text-sm leading-relaxed text-mint-100/70">
                {result.weather_summary ?? t("weatherUnavailable")}
              </p>
            )}
          </section>

          {result.satellite ? (
            <div className="border-t border-mint-100/10 pt-4 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-6">
              <SatelliteSummary satellite={result.satellite} />
            </div>
          ) : null}
        </div>

        <p className="text-[11px] leading-relaxed text-mint-200/50">{t("fieldConditionsNote")}</p>
      </div>
    </section>
  );
}
