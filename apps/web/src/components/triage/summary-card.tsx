"use client";

import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Camera, ChevronDown, CloudSun, FlaskConical, MapPin, MessageSquareText, Sparkles, type LucideIcon } from "lucide-react";

import { BotanicalPattern } from "@/components/brand/botanical";
import { CONFIDENCE_DISPLAY, DATA_SOURCE_STATUS_DISPLAY, formatTimestamp, URGENCY_DISPLAY } from "@/components/triage/display";
import { ConfidenceMeter } from "@/components/triage/possible-causes";
import { cn } from "@/lib/utils";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { Crop, SourceKind, TriageResponse } from "@/types/triage";

const EASE = [0.16, 1, 0.3, 1] as const;
const VISIBLE_OBSERVATIONS = 3;

const CROP_KEYS: Record<Crop, TranslationKey> = {
  rice: "cropRice", wheat: "cropWheat", maize: "cropMaize", cotton: "cropCotton",
  sugarcane: "cropSugarcane", soybean: "cropSoybean", groundnut: "cropGroundnut",
  chickpea: "cropChickpea", tomato: "cropTomato", potato: "cropPotato",
  onion: "cropOnion", chilli: "cropChilli", other: "cropOther",
};
const SOURCE_KEYS: Record<SourceKind, TranslationKey> = {
  farmer_report: "sourceYourReport", photo: "sourcePhotos", weather: "sourceWeather",
  satellite: "sourceSatellite", knowledge_base: "sourceGuidance", analysis_engine: "sourceEngine",
};
const STATUS_KEYS: Record<string, TranslationKey> = {
  used: "sourceUsed", unavailable: "sourceUnavailable", not_integrated: "sourceNotConnected",
  received_not_analysed: "sourceReceived",
};
const URGENCY_KEYS: Record<TriageResponse["urgency"], TranslationKey> = {
  low: "urgencyLow", moderate: "urgencyModerate", high: "urgencyHigh", critical: "urgencyCritical",
};
const ADVICE_KEYS: Record<TriageResponse["urgency"], TranslationKey> = {
  low: "monitorAdvice", moderate: "actSoonAdvice", high: "actNowAdvice", critical: "expertTodayAdvice",
};
const CONFIDENCE_KEYS: Record<TriageResponse["possible_causes"][number]["confidence"], TranslationKey> = {
  low: "confidenceLow", medium: "confidenceMedium", high: "confidenceHigh",
};

function cropHeading(result: TriageResponse, t: (key: TranslationKey) => string) {
  if (result.crop) return { name: t(CROP_KEYS[result.crop]) };
  if (result.detected_crop) return { name: detectedCropName(result.detected_crop, t), note: t("cropGuess") };
  return { name: t("cropUnclear") };
}

/** Localized name for a crop read from photos; unknown crops keep the model's wording. */
export function detectedCropName(detected: string, t: (key: TranslationKey) => string): string {
  const key = detected.trim().toLowerCase();
  if (Object.hasOwn(CROP_KEYS, key)) return t(CROP_KEYS[key as Crop]);
  return detected.charAt(0).toUpperCase() + detected.slice(1);
}

function splitName(name: string): [string, string | undefined] {
  const match = name.match(/^(.*?)\s*\((.+)\)\s*$/);
  return match ? [match[1]!, match[2]] : [name, undefined];
}

function Section({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return <section className="space-y-2"><p className="label-caps flex items-center gap-1.5 text-mint-300/60"><Icon className="size-3.5" aria-hidden />{title}</p>{children}</section>;
}

function Clamp({ text, lines, className, less, more }: { text: string; lines: 2 | 3; className?: string; less: string; more: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > (lines === 2 ? 120 : 180);
  return <div className={className}><p className={cn(!open && long && (lines === 2 ? "line-clamp-2" : "line-clamp-3"))}>{text}</p>{long ? <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="mt-1 text-xs font-medium text-mint-300 underline-offset-2 hover:underline">{open ? less : more}</button> : null}</div>;
}

function farmerWords(observation: string): string | null {
  return observation.match(/“([\s\S]+)”/)?.[1] ?? null;
}

export function SummaryCard({ result }: { result: TriageResponse }) {
  const { t } = useI18n();
  const [showAllObs, setShowAllObs] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const urgency = URGENCY_DISPLAY[result.urgency];
  const top = result.possible_causes[0];
  const crop = cropHeading(result, t);
  const [disease, diseaseNote] = top ? splitName(top.name) : [t("cropUnclear"), undefined];
  const engine = result.data_sources.find((source) => source.kind === "analysis_engine")?.name;
  const isMock = result.analysis_mode === "mock";
  const observations = result.evidence.filter((item) => item.source === "photo" && item.availability === "available");
  const shownObservations = showAllObs ? observations : observations.slice(0, VISIBLE_OBSERVATIONS);
  const farmer = result.evidence.find((item) => item.source === "farmer_report");
  const farmerText = farmer ? farmerWords(farmer.observation) : null;
  const notChecked = result.evidence.filter((item) => item.availability !== "available");
  const hasLocation = Boolean(result.location_label || result.approximate_location);
  const weatherText = result.weather_summary ?? t("weatherUnavailable");

  return (
    <motion.section aria-label={t("triage")} initial={{ opacity: 0, y: 20, scale: 0.985 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.8, ease: EASE }} className="relative overflow-hidden rounded-[28px] bg-forest-900 p-6 text-mint-100 sm:p-7">
      <BotanicalPattern className="text-mint-300/[0.06]" />
      <div className="relative space-y-6">
        <header>
          <p className="text-lg font-medium text-mint-300">{crop.name}{crop.note ? <span className="ml-2 text-xs font-normal text-mint-200/50">{crop.note}</span> : null}</p>
          <h1 className="mt-1 text-[clamp(1.9rem,6vw,2.6rem)] leading-[1.02] font-medium">{disease}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            {diseaseNote ? <span className="text-sm text-mint-200/70">{diseaseNote}</span> : null}
            {top ? <ConfidenceMeter tone="dark" level={CONFIDENCE_DISPLAY[top.confidence].level} label={`${t("confidenceLikely")} · ${t(CONFIDENCE_KEYS[top.confidence]).toLowerCase()}`} /> : null}
          </div>
        </header>

        <div className="rounded-2xl bg-mint-100/[0.06] p-4 ring-1 ring-mint-100/10">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm"><span className={cn("font-medium", urgency.text)}>{t(URGENCY_KEYS[result.urgency])} {t("urgencyWord")}</span><span className="text-mint-200/70"> · {t(ADVICE_KEYS[result.urgency])}</span></p>
            <span className="flex w-16 shrink-0 gap-1" role="img" aria-label={`${t(URGENCY_KEYS[result.urgency])} ${t("urgencyWord")}`}>
              {[1, 2, 3, 4].map((step) => <span key={step} className="relative h-1 flex-1 overflow-hidden rounded-full bg-mint-100/15">{step <= urgency.level ? <motion.span className={cn("absolute inset-0 origin-left rounded-full", urgency.bar)} initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.4 + step * 0.12, duration: 0.5, ease: EASE }} /> : null}</span>)}
            </span>
          </div>
          <Clamp text={result.urgency_reason} lines={2} className="mt-1.5 text-[13px] leading-relaxed text-mint-200/65" less={t("less")} more={t("more")} />
        </div>

        <Clamp text={result.summary} lines={3} className="text-sm leading-relaxed text-mint-100/85" less={t("less")} more={t("more")} />

        {hasLocation ? <div className="grid gap-4 border-t border-mint-100/10 pt-4 sm:grid-cols-2"><Section icon={MapPin} title={t("fieldLocation")}><p className="text-sm leading-relaxed text-mint-100/85">{result.location_label ?? result.approximate_location}</p></Section><Section icon={CloudSun} title={t("recentWeather")}><p className="text-sm leading-relaxed text-mint-100/85">{weatherText}</p></Section></div> : null}

        {observations.length ? <Section icon={Camera} title={t("whatWeSaw")}><ul className="space-y-1.5"><AnimatePresence initial={false}>{shownObservations.map((item) => <motion.li key={item.id} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="flex gap-2.5 text-sm leading-snug text-mint-100/85"><span className="mt-[7px] size-1 shrink-0 rounded-full bg-mint-300" aria-hidden />{item.observation}</motion.li>)}</AnimatePresence></ul>{observations.length > VISIBLE_OBSERVATIONS ? <button type="button" onClick={() => setShowAllObs((value) => !value)} aria-expanded={showAllObs} className="text-xs font-medium text-mint-300 underline-offset-2 hover:underline">{showAllObs ? t("showLess") : `${t("showAll")} ${observations.length}`}</button> : null}</Section> : null}
        {farmerText ? <Section icon={MessageSquareText} title={t("youToldUs")}><p className="line-clamp-3 text-sm italic leading-relaxed text-mint-100/75">“{farmerText}”</p></Section> : null}

        <div className="border-t border-mint-100/10 pt-4 text-xs leading-relaxed text-mint-200/60">
          <button type="button" onClick={() => setShowMore((value) => !value)} aria-expanded={showMore} className="flex w-full items-center gap-2 text-left">
            {isMock ? <FlaskConical className="size-3.5 shrink-0 text-clay-400" aria-hidden /> : <Sparkles className="size-3.5 shrink-0" aria-hidden />}
            <span className="flex-1"><span className={cn("font-medium", isMock ? "text-clay-400" : "text-mint-200/85")}>{isMock ? t("mockResult") : `${t("aiTriage")}${engine ? ` · ${engine}` : ""}`}</span> · {t("notDiagnosis")}</span>
            <motion.span animate={{ rotate: showMore ? 180 : 0 }} aria-hidden><ChevronDown className="size-3.5" /></motion.span>
          </button>
          <AnimatePresence initial={false}>{showMore ? <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden"><div className="space-y-3 pt-3">
            <p className="font-mono text-[11px]">{result.report_id} · <time dateTime={result.generated_at}>{formatTimestamp(result.generated_at)}</time></p>
            <p>{t("footerDisclaimer")}</p>
            {notChecked.length ? <p>{t("notCheckedYet")} {notChecked.map((item) => t(SOURCE_KEYS[item.source])).join(" · ")}. {t("missingNotNormal")}</p> : null}
            <ul className="space-y-1">{result.data_sources.map((source) => <li key={source.id} className="flex items-center justify-between gap-3"><span className="truncate">{source.kind === "analysis_engine" ? source.name : t(SOURCE_KEYS[source.kind])}</span><span className="flex shrink-0 items-center gap-1.5"><span className={cn("size-1.5 rounded-full", DATA_SOURCE_STATUS_DISPLAY[source.status].dot)} aria-hidden />{t(STATUS_KEYS[source.status])}</span></li>)}</ul>
          </div></motion.div> : null}</AnimatePresence>
        </div>
      </div>
    </motion.section>
  );
}
