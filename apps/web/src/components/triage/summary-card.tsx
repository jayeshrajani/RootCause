"use client";

import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Camera, ChevronDown, FlaskConical, MessageSquareText, Sparkles } from "lucide-react";

import { BotanicalPattern } from "@/components/brand/botanical";
import {
  CONFIDENCE_DISPLAY,
  DATA_SOURCE_STATUS_DISPLAY,
  formatTimestamp,
  SOURCE_DISPLAY,
  URGENCY_DISPLAY,
} from "@/components/triage/display";
import { ConfidenceMeter } from "@/components/triage/possible-causes";
import { CROP_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { TriageResponse } from "@/types/triage";

const EASE = [0.16, 1, 0.3, 1] as const;
const VISIBLE_OBSERVATIONS = 3;

function cropHeading(result: TriageResponse): { name: string; note?: string } {
  if (result.crop) return { name: CROP_LABELS[result.crop] };
  if (result.detected_crop) {
    const name = result.detected_crop.charAt(0).toUpperCase() + result.detected_crop.slice(1);
    return { name, note: "identified from photo" };
  }
  return { name: "Crop unclear" };
}

/** "Early blight (fungal leaf spot)" -> ["Early blight", "fungal leaf spot"] */
function splitName(name: string): [string, string | undefined] {
  const match = name.match(/^(.*?)\s*\((.+)\)\s*$/);
  return match ? [match[1]!, match[2]] : [name, undefined];
}

function Section({ icon: Icon, title, children }: { icon: typeof Camera; title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <p className="label-caps flex items-center gap-1.5 text-mint-300/60">
        <Icon className="size-3.5" aria-hidden />
        {title}
      </p>
      {children}
    </section>
  );
}

function Clamp({ text, lines, className }: { text: string; lines: 2 | 3; className?: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > (lines === 2 ? 120 : 180);
  return (
    <div className={className}>
      <p className={cn(!open && long && (lines === 2 ? "line-clamp-2" : "line-clamp-3"))}>{text}</p>
      {long ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="mt-1 text-xs font-medium text-mint-300 underline-offset-2 hover:underline"
        >
          {open ? "Less" : "More"}
        </button>
      ) : null}
    </div>
  );
}

function farmerWords(observation: string): string | null {
  const quoted = observation.match(/“([\s\S]+)”/);
  return quoted?.[1] ?? null;
}

export function SummaryCard({ result }: { result: TriageResponse }) {
  const [showAllObs, setShowAllObs] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const urgency = URGENCY_DISPLAY[result.urgency];
  const top = result.possible_causes[0];
  const crop = cropHeading(result);
  const [disease, diseaseNote] = top ? splitName(top.name) : ["Cause unclear", undefined];
  const engine = result.data_sources.find((s) => s.kind === "analysis_engine")?.name;
  const isMock = result.analysis_mode === "mock";

  const observations = result.evidence.filter(
    (e) => e.source === "photo" && e.availability === "available",
  );
  const shownObs = showAllObs ? observations : observations.slice(0, VISIBLE_OBSERVATIONS);
  const farmer = result.evidence.find((e) => e.source === "farmer_report");
  const farmerText = farmer ? farmerWords(farmer.observation) : null;
  const notChecked = result.evidence.filter((e) => e.availability !== "available");

  return (
    <motion.section
      aria-label="Triage summary"
      initial={{ opacity: 0, y: 20, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.8, ease: EASE }}
      className="relative overflow-hidden rounded-[28px] bg-forest-900 p-6 text-mint-100 sm:p-7"
    >
      <BotanicalPattern className="text-mint-300/[0.06]" />
      <div className="relative space-y-6">
        <header>
          <p className="text-lg font-medium text-mint-300">
            {crop.name}
            {crop.note ? (
              <span className="ml-2 text-xs font-normal whitespace-nowrap text-mint-200/50">
                {crop.note}
              </span>
            ) : null}
          </p>
          <h1 className="mt-1 text-[clamp(1.9rem,6vw,2.6rem)] leading-[1.02] font-medium tracking-[-0.03em]">
            {disease}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            {diseaseNote ? <span className="text-sm text-mint-200/70">{diseaseNote}</span> : null}
            {top ? (
              <ConfidenceMeter
                tone="dark"
                level={CONFIDENCE_DISPLAY[top.confidence].level}
                label={`Likely · ${CONFIDENCE_DISPLAY[top.confidence].label.toLowerCase()}`}
              />
            ) : null}
          </div>
        </header>

        <div className="rounded-2xl bg-mint-100/[0.06] p-4 ring-1 ring-mint-100/10">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm">
              <span className={cn("font-medium", urgency.text)}>{urgency.label} urgency</span>
              <span className="text-mint-200/70"> · {urgency.advice}</span>
            </p>
            <span className="flex w-16 shrink-0 gap-1" role="img" aria-label={`Urgency ${urgency.level} of 4`}>
              {[1, 2, 3, 4].map((n) => (
                <span key={n} className="relative h-1 flex-1 overflow-hidden rounded-full bg-mint-100/15">
                  {n <= urgency.level ? (
                    <motion.span
                      className={cn("absolute inset-0 origin-left rounded-full", urgency.bar)}
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ delay: 0.4 + n * 0.12, duration: 0.5, ease: EASE }}
                    />
                  ) : null}
                </span>
              ))}
            </span>
          </div>
          <Clamp
            text={result.urgency_reason}
            lines={2}
            className="mt-1.5 text-[13px] leading-relaxed text-mint-200/65"
          />
        </div>

        <Clamp text={result.summary} lines={3} className="text-sm leading-relaxed text-mint-100/85" />

        {observations.length ? (
          <Section icon={Camera} title="What we saw">
            <ul className="space-y-1.5">
              <AnimatePresence initial={false}>
                {shownObs.map((e) => (
                  <motion.li
                    key={e.id}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex gap-2.5 text-sm leading-snug text-mint-100/85"
                  >
                    <span className="mt-[7px] size-1 shrink-0 rounded-full bg-mint-300" aria-hidden />
                    {e.observation}
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
            {observations.length > VISIBLE_OBSERVATIONS ? (
              <button
                type="button"
                onClick={() => setShowAllObs((v) => !v)}
                aria-expanded={showAllObs}
                className="text-xs font-medium text-mint-300 underline-offset-2 hover:underline"
              >
                {showAllObs ? "Show less" : `Show all ${observations.length}`}
              </button>
            ) : null}
          </Section>
        ) : null}

        {farmerText ? (
          <Section icon={MessageSquareText} title="You told us">
            <p className="line-clamp-3 text-sm leading-relaxed text-mint-100/75 italic">
              “{farmerText}”
            </p>
          </Section>
        ) : null}

        <div className="border-t border-mint-100/10 pt-4 text-xs leading-relaxed text-mint-200/60">
          <button
            type="button"
            onClick={() => setShowMore((v) => !v)}
            aria-expanded={showMore}
            className="flex w-full items-center gap-2 text-left"
          >
            {isMock ? (
              <FlaskConical className="size-3.5 shrink-0 text-clay-400" aria-hidden />
            ) : (
              <Sparkles className="size-3.5 shrink-0" aria-hidden />
            )}
            <span className="flex-1">
              <span className={cn("font-medium", isMock ? "text-clay-400" : "text-mint-200/85")}>
                {isMock ? "Mock result" : `AI triage${engine ? ` · ${engine}` : ""}`}
              </span>{" "}
              · Not a diagnosis
            </span>
            <motion.span animate={{ rotate: showMore ? 180 : 0 }} aria-hidden>
              <ChevronDown className="size-3.5" />
            </motion.span>
          </button>
          <AnimatePresence initial={false}>
            {showMore ? (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="space-y-3 pt-3">
                  <p className="font-mono text-[11px]">
                    {result.report_id} ·{" "}
                    <time dateTime={result.generated_at}>{formatTimestamp(result.generated_at)}</time>
                  </p>
                  <p>{result.disclaimer}</p>
                  {notChecked.length ? (
                    <p>
                      Not checked yet:{" "}
                      {notChecked.map((e) => SOURCE_DISPLAY[e.source].label).join(" · ")}. Missing
                      data is never treated as normal.
                    </p>
                  ) : null}
                  <ul className="space-y-1">
                    {result.data_sources.map((s) => (
                      <li key={s.id} className="flex items-center justify-between gap-3">
                        <span className="truncate">{s.name}</span>
                        <span className="flex shrink-0 items-center gap-1.5">
                          <span className={cn("size-1.5 rounded-full", DATA_SOURCE_STATUS_DISPLAY[s.status].dot)} aria-hidden />
                          {DATA_SOURCE_STATUS_DISPLAY[s.status].label}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </motion.section>
  );
}
