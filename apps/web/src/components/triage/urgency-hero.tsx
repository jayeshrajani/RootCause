"use client";

import { motion } from "motion/react";
import { UserCheck } from "lucide-react";

import { BotanicalPattern } from "@/components/brand/botanical";
import { formatTimestamp, URGENCY_DISPLAY } from "@/components/triage/display";
import { CROP_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { TriageResponse } from "@/types/triage";

const EASE = [0.16, 1, 0.3, 1] as const;

export function UrgencyHero({ result }: { result: TriageResponse }) {
  const urgency = URGENCY_DISPLAY[result.urgency];

  return (
    <motion.section
      aria-label="Triage summary"
      initial={{ opacity: 0, y: 24, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.9, ease: EASE }}
      className="relative overflow-hidden rounded-[28px] bg-forest-900 p-6 text-mint-100 sm:p-10"
    >
      <BotanicalPattern className="text-mint-300/[0.06]" />
      <div className="relative">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="label-caps text-mint-300/80">Triage · {CROP_LABELS[result.crop]}</p>
          <p className="font-mono text-[11px] text-mint-200/50">
            {result.report_id} · <time dateTime={result.generated_at}>{formatTimestamp(result.generated_at)}</time>
          </p>
        </div>

        <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:items-end">
          <div>
            <p className="label-caps text-mint-300/70">Urgency</p>
            <motion.p
              className={cn("mt-2 text-[clamp(3.5rem,11vw,6.5rem)] leading-[0.9] font-medium tracking-[-0.045em]", urgency.text)}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 1, ease: EASE }}
            >
              {urgency.label}
            </motion.p>
            <div className="mt-5 flex max-w-xs gap-1.5" role="img" aria-label={`Urgency ${urgency.level} of 4`}>
              {[1, 2, 3, 4].map((n) => (
                <span key={n} className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-mint-100/15">
                  {n <= urgency.level ? (
                    <motion.span
                      className={cn("absolute inset-0 origin-left rounded-full", urgency.bar)}
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ delay: 0.5 + n * 0.15, duration: 0.6, ease: EASE }}
                    />
                  ) : null}
                </span>
              ))}
            </div>
            <p className="mt-4 text-lg font-medium">{urgency.advice}</p>
            <p className="mt-1 max-w-sm text-sm text-mint-200/70">{result.urgency_reason}</p>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45, duration: 0.9, ease: EASE }}
            className="space-y-5 lg:border-l lg:border-mint-100/15 lg:pl-10"
          >
            <p className="text-lg leading-relaxed text-mint-100/90 sm:text-xl">{result.summary}</p>
            {result.requires_expert_review ? (
              <p className="inline-flex items-center gap-2 rounded-full bg-mint-300 px-4 py-2 text-sm font-medium text-forest-900">
                <UserCheck className="size-4" aria-hidden />
                Expert review recommended
              </p>
            ) : null}
          </motion.div>
        </div>
      </div>
    </motion.section>
  );
}
