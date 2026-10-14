"use client";

import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";

import { cn } from "@/lib/utils";

export interface ResultTab {
  id: string;
  label: string;
  count?: number;
  content: ReactNode;
}

export function ResultTabs({ tabs }: { tabs: ResultTab[] }) {
  const [active, setActive] = useState(tabs[0]?.id);
  const barRef = useRef<HTMLDivElement>(null);
  const baseId = useId();
  const current = tabs.find((t) => t.id === active) ?? tabs[0];

  const select = (id: string) => {
    setActive(id);
    const bar = barRef.current;
    // Keep the tab bar in view when switching from deep inside a long panel.
    if (bar && bar.getBoundingClientRect().top < 64) {
      window.scrollTo({ top: window.scrollY + bar.getBoundingClientRect().top - 72, behavior: "smooth" });
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const index = tabs.findIndex((t) => t.id === active);
    const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    if (next) {
      select(next.id);
      document.getElementById(`${baseId}-tab-${next.id}`)?.focus();
    }
  };

  if (!current) return null;

  return (
    <div>
      <div
        ref={barRef}
        className="sticky top-16 z-20 -mx-5 bg-background/85 px-5 py-3 backdrop-blur-xl lg:top-20 lg:mx-0 lg:px-0"
      >
        <div
          role="tablist"
          aria-label="Triage details"
          onKeyDown={onKeyDown}
          className="grid rounded-full bg-forest-900/[0.06] p-1"
          style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}
        >
          {tabs.map((tab) => {
            const selected = tab.id === current.id;
            return (
              <button
                key={tab.id}
                id={`${baseId}-tab-${tab.id}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`${baseId}-panel-${tab.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => select(tab.id)}
                className={cn(
                  "relative h-10 rounded-full px-2 text-sm font-medium transition-colors",
                  selected ? "text-mint-100" : "text-forest-900/60 hover:text-forest-900",
                )}
              >
                {selected ? (
                  <motion.span
                    layoutId={`${baseId}-pill`}
                    className="absolute inset-0 rounded-full bg-forest-900"
                    transition={{ type: "spring", stiffness: 420, damping: 36 }}
                  />
                ) : null}
                <span className="relative inline-flex items-center gap-1.5">
                  {tab.label}
                  {tab.count ? (
                    <span
                      className={cn(
                        "rounded-full px-1.5 text-[11px] tabular-nums",
                        selected ? "bg-mint-100/20" : "bg-forest-900/10",
                      )}
                    >
                      {tab.count}
                    </span>
                  ) : null}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={current.id}
          id={`${baseId}-panel-${current.id}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${current.id}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.25 }}
          className="pt-3"
        >
          {current.content}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
