"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, CircleHelp, Minus, Plus } from "lucide-react";

import { EvidenceFit, LedgerChip } from "@/components/triage/evidence-fit";
import { cn } from "@/lib/utils";
import type { PossibleCause } from "@/types/triage";
import { useI18n } from "@/lib/i18n";

export function ConfidenceMeter({
  level,
  label,
  tone = "light",
}: {
  level: number;
  label: string;
  tone?: "light" | "dark";
}) {
  const on = tone === "dark" ? "bg-mint-300" : "bg-forest-700";
  const off = tone === "dark" ? "bg-mint-100/20" : "bg-forest-900/15";
  return (
    <span className="inline-flex items-center gap-2" title={label}>
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3].map((n) => (
          <span key={n} className={cn("h-3 w-1 rounded-full", n <= level ? on : off)} />
        ))}
      </span>
      <span className={cn("text-xs", tone === "dark" ? "text-mint-200/70" : "text-muted-foreground")}>
        {label}
      </span>
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

function CauseItem({
  cause,
  defaultOpen,
  referenceWeight,
}: {
  cause: PossibleCause;
  defaultOpen: boolean;
  referenceWeight: number | null;
}) {
  const { language, t } = useI18n();
  const [open, setOpen] = useState(defaultOpen);
  const panelId = `cause-${cause.name.replace(/\W+/g, "-").toLowerCase()}`;

  return (
    <li className={cn("rounded-3xl border bg-card transition-colors", open ? "border-forest-900/25" : "border-forest-900/10")}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-4 p-4 text-left sm:px-5"
      >
        <span className="flex-1 space-y-1">
          <span className="block leading-snug font-medium sm:text-lg">{cause.name}</span>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <EvidenceFit
              score={cause.evidence_fit_score}
              referenceScore={cause.reference_score ?? null}
              referenceWeight={referenceWeight}
              ledger={cause.evidence_ledger}
            />
          </span>
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
            <div className="space-y-4 px-4 pb-5 sm:px-5">
              <p className="text-[15px] leading-relaxed text-forest-900/85">{cause.explanation}</p>
              <div className="grid gap-5 rounded-2xl bg-mint-50 p-4 sm:grid-cols-2">
                <EvidenceColumn title={t("supports")} items={cause.supporting_evidence} empty={t("nothingYet")} positive />
                <EvidenceColumn
                  title={t("arguesAgainst")}
                  items={cause.contradictory_evidence}
                  empty={t("nothingChecked")}
                  positive={false}
                />
              </div>
              {language === "en" && cause.evidence_ledger?.length ? (
                <ul className="space-y-1.5" aria-label={t("fieldConditions")}>
                  {cause.evidence_ledger.map((item) => (
                    <li key={item.signal} className="flex flex-wrap items-start gap-2 text-sm">
                      <LedgerChip item={item} />
                      <span className="flex-1 text-muted-foreground">{item.reason}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
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

export function PossibleCauses({
  causes,
  referenceWeight = null,
}: {
  causes: PossibleCause[];
  referenceWeight?: number | null;
}) {
  return (
    <ul className="space-y-2.5">
      {causes.map((cause, i) => (
        <CauseItem key={cause.name} cause={cause} defaultOpen={i === 0} referenceWeight={referenceWeight} />
      ))}
    </ul>
  );
}
