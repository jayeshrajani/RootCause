"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import type { MissingInformation } from "@/types/triage";

/** Field checks that help tell the possible causes apart. Ticks are local only. */
export function QuickChecks({ items }: { items: MissingInformation[] }) {
  const [done, setDone] = useState<Set<number>>(new Set());

  if (!items.length) return null;

  const toggle = (i: number) =>
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  return (
    <div className="space-y-2.5">
      <p className="label-caps text-forest-600">Quick checks to tell them apart</p>
      <ul className="space-y-2">
        {items.map((item, i) => {
          const checked = done.has(i);
          return (
            <li key={item.item}>
              <button
                type="button"
                onClick={() => toggle(i)}
                aria-pressed={checked}
                className="flex w-full gap-3 rounded-2xl border border-dashed border-forest-900/20 p-4 text-left transition-colors hover:border-forest-900/40"
              >
                <span
                  className={cn(
                    "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors",
                    checked ? "border-forest-900 bg-forest-900 text-mint-100" : "border-forest-900/30",
                  )}
                >
                  {checked ? (
                    <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}>
                      <Check className="size-3" strokeWidth={3} aria-hidden />
                    </motion.span>
                  ) : null}
                </span>
                <span className={cn("space-y-0.5 transition-opacity", checked && "opacity-55")}>
                  <span className="block text-[15px] leading-snug font-medium">{item.item}</span>
                  <span className="block text-sm text-muted-foreground">{item.reason}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
