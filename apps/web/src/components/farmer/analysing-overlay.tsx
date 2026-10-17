"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check } from "lucide-react";

import { LogoMark } from "@/components/brand/logo";
import { objectUrlFor } from "@/lib/object-urls";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const EASE = [0.16, 1, 0.3, 1] as const;
const STEP_MS = 1500;

/** Each line names work the API really does for this report; only the pacing is staged. */
function stepsFor(phase: "identify" | "analyse", hasLocation: boolean, hasDescription: boolean): TranslationKey[] {
  if (phase === "identify") return ["logIsolate", "logVenation", "logRankCrops"];
  return [
    "logLesions",
    ...(hasDescription ? (["logListen"] as const) : []),
    ...(hasLocation ? (["logWeather", "logSatellite"] as const) : []),
    "logPatterns",
    "logHypotheses",
    "logEvidence",
    "logPlan",
  ];
}

function Corner({ className }: { className: string }) {
  return <span aria-hidden className={cn("absolute size-5 border-mint-300/80", className)} />;
}

export function AnalysingOverlay({
  photo,
  phase = "analyse",
  coordinates,
  transcript,
  hasDescription = false,
}: {
  photo?: File;
  phase?: "identify" | "analyse";
  coordinates?: { latitude: string; longitude: string } | null;
  transcript?: string | null;
  hasDescription?: boolean;
}) {
  const { t } = useI18n();
  const steps = stepsFor(phase, Boolean(coordinates), hasDescription || Boolean(transcript));
  const [active, setActive] = useState(0);

  // The last line stays "in progress" until the real response arrives.
  useEffect(() => {
    const id = window.setInterval(() => setActive((s) => Math.min(s + 1, steps.length - 1)), STEP_MS);
    return () => window.clearInterval(id);
  }, [steps.length]);

  const hud = coordinates
    ? `${Number(coordinates.latitude).toFixed(2)}°N  ${Number(coordinates.longitude).toFixed(2)}°E`
    : "RGB · 3ch";

  return (
    <motion.div
      role="status"
      aria-live="polite"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-8 overflow-y-auto bg-forest-950/95 px-6 py-10 text-mint-100 backdrop-blur-md"
    >
      <div className="relative size-52 shrink-0 sm:size-60">
        <div className="relative size-full overflow-hidden rounded-[24px] bg-forest-800 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.6)]">
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
            <img src={objectUrlFor(photo)} alt="" className="size-full object-cover opacity-75 saturate-[0.85]" />
          ) : (
            <div className="flex size-full items-center justify-center">
              <LogoMark className="size-16 text-mint-300/60" />
            </div>
          )}
          <div
            aria-hidden
            className="absolute inset-0 bg-[linear-gradient(rgba(181,227,196,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(181,227,196,0.08)_1px,transparent_1px)] bg-[size:24px_24px]"
          />
          <motion.div
            aria-hidden
            className="absolute inset-x-0 h-20 border-b border-mint-300/70 bg-gradient-to-b from-transparent to-mint-300/25"
            initial={{ top: "-25%" }}
            animate={{ top: "100%" }}
            transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
          />
          <span className="absolute bottom-2.5 left-3 font-mono text-[10px] tracking-wider text-mint-200/80">
            {hud}
          </span>
          <motion.span
            className="absolute top-2.5 right-3 flex items-center gap-1.5 font-mono text-[10px] tracking-wider text-mint-200/80"
            animate={{ opacity: [1, 0.35, 1] }}
            transition={{ duration: 1.4, repeat: Infinity }}
          >
            <span className="size-1.5 rounded-full bg-mint-300" />
            LIVE
          </motion.span>
        </div>
        <Corner className="-top-2 -left-2 rounded-tl-lg border-t-2 border-l-2" />
        <Corner className="-top-2 -right-2 rounded-tr-lg border-t-2 border-r-2" />
        <Corner className="-bottom-2 -left-2 rounded-bl-lg border-b-2 border-l-2" />
        <Corner className="-right-2 -bottom-2 rounded-br-lg border-r-2 border-b-2" />
      </div>

      <div className="w-full max-w-sm">
        <div className="mb-3 flex items-center justify-between font-mono text-[11px] tracking-wider text-mint-200/50 uppercase">
          <span>{phase === "identify" ? t("identifyingCrop") : t("analysing")}</span>
          <span className="tabular-nums">
            {String(active + 1).padStart(2, "0")}/{String(steps.length).padStart(2, "0")}
          </span>
        </div>
        <div className="mb-4 h-px overflow-hidden bg-mint-100/10">
          <motion.div
            className="h-full bg-mint-300"
            animate={{ width: `${((active + 1) / steps.length) * 100}%` }}
            transition={{ duration: 0.6, ease: EASE }}
          />
        </div>
        <ol className="space-y-2.5">
          <AnimatePresence initial={false}>
            {steps.slice(0, active + 1).map((key, index) => {
              const done = index < active;
              return (
                <motion.li
                  key={key}
                  initial={{ opacity: 0, y: 8, filter: "blur(4px)" }}
                  animate={{ opacity: done ? 0.45 : 1, y: 0, filter: "blur(0px)" }}
                  transition={{ duration: 0.45, ease: EASE }}
                  className="flex items-center gap-3 text-[15px]"
                >
                  <span className="flex size-5 shrink-0 items-center justify-center">
                    {done ? (
                      <Check className="size-4 text-mint-300" aria-hidden />
                    ) : (
                      <motion.span
                        className="size-3.5 rounded-full border-2 border-mint-300 border-t-transparent"
                        animate={{ rotate: 360 }}
                        transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
                      />
                    )}
                  </span>
                  <span className={cn(!done && "font-medium")}>{t(key)}</span>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ol>
        {transcript ? (
          <p className="mt-6 border-l-2 border-mint-300/40 pl-3 text-sm text-mint-200/70">
            <span className="font-mono text-[10px] tracking-wider uppercase">{t("logYouSaid")}</span>
            <span className="mt-0.5 line-clamp-2 block italic">“{transcript}”</span>
          </p>
        ) : null}
      </div>
    </motion.div>
  );
}
