"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, CircleHelp, Minus, Plus } from "lucide-react";

import { CONFIDENCE_DISPLAY } from "@/components/triage/display";
import { cn } from "@/lib/utils";
import type { PossibleCause } from "@/types/triage";

function ConfidenceMeter({ level, label }: { level: number; label: string }) {
  return (
    <span className="inline-flex items-center gap-2" title={label}>
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3].map((n) => (
          <span
            key={n}
            className={cn("h-3 w-1 rounded-full", n <= level ? "bg-forest-700" : "bg-forest-900/15")}
          />
        ))}
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </span>
  );
}

function EvidenceColumn({ title, items, empty, positive }: { title: string; items: string[]; empty: string; positive: boolean }) {
  const Icon = positive ? Plus : Minus;
  return (
    <div className="space-y-2">
      <p className="label-caps flex items-center gap-1.5 text-forest-600">
        <Icon className="size-3" aria-hidden />
        {title}
      </p>
      {items.length ? (
        <ul className="space-y-1.5 text-sm">
          {items.map((item) => (
            <li key={item} className="leading-relaxed">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground italic">{empty}</p>
      )}
    </div>
  );
}

function CauseItem({ cause, defaultOpen }: { cause: PossibleCause; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const confidence = CONFIDENCE_DISPLAY[cause.confidence];
  const panelId = `cause-${cause.name.replace(/\W+/g, "-").toLowerCase()}`;

  return (
    <li className={cn("rounded-3xl border bg-card transition-colors", open ? "border-forest-900/25" : "border-forest-900/10")}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-4 p-5 text-left sm:p-6"
      >
        <span className="flex-1 space-y-1.5">
          <span className="block text-lg leading-snug font-medium">{cause.name}</span>
          <ConfidenceMeter level={confidence.level} label={confidence.label} />
        </span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          className="flex size-9 shrink-0 items-center justify-center rounded-full bg-mint-100"
        >
          <ChevronDown className="size-4" aria-hidden />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={panelId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="space-y-5 px-5 pb-6 sm:px-6">
              <p className="leading-relaxed text-forest-900/85">{cause.explanation}</p>
              <div className="grid gap-5 rounded-2xl bg-mint-50 p-4 sm:grid-cols-2">
                <EvidenceColumn title="Supports" items={cause.supporting_evidence} empty="Nothing yet." positive />
                <EvidenceColumn
                  title="Argues against"
                  items={cause.contradictory_evidence}
                  empty="Nothing checked yet."
                  positive={false}
                />
              </div>
              <p className="flex gap-2.5 text-sm text-muted-foreground">
                <CircleHelp className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>{cause.uncertainty_note}</span>
              </p>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </li>
  );
}

export function PossibleCauses({ causes }: { causes: PossibleCause[] }) {
  return (
    <ul className="space-y-3">
      {causes.map((cause, i) => (
        <CauseItem key={cause.name} cause={cause} defaultOpen={i === 0} />
      ))}
    </ul>
  );
}
