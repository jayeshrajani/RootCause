"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import { LogoMark } from "@/components/brand/logo";
import { objectUrlFor } from "@/lib/object-urls";
import { useI18n } from "@/lib/i18n";

export function AnalysingOverlay({ photo, phase = "analyse" }: { photo?: File; phase?: "identify" | "analyse" }) {
  const { t } = useI18n();
  const stages =
    phase === "identify"
      ? [t("identifyingCrop")]
      : [t("checkingField"), t("analysing"), t("observed"), t("triage"), t("nextSteps")];
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setStage((s) => Math.min(s + 1, stages.length - 1)), 1600);
    return () => window.clearInterval(id);
  }, [stages.length]);

  return (
    <motion.div
      role="status"
      aria-live="polite"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-10 bg-forest-900/95 px-6 text-mint-100 backdrop-blur-md"
    >
      <div className="relative size-56 overflow-hidden rounded-[28px] bg-forest-800 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.6)] sm:size-64">
        {photo ? (
          // eslint-disable-next-line @next/next/no-img-element -- local blob preview
          <img src={objectUrlFor(photo)} alt="" className="size-full object-cover opacity-80" />
        ) : (
          <div className="flex size-full items-center justify-center">
            <LogoMark className="size-16 text-mint-300/60" />
          </div>
        )}
        <motion.div
          className="absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-mint-300/35 to-transparent"
          initial={{ top: "-30%" }}
          animate={{ top: "100%" }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="absolute inset-0 rounded-[28px] ring-1 ring-mint-300/30 ring-inset" />
      </div>

      <div className="flex h-16 flex-col items-center gap-2 text-center">
        <AnimatePresence mode="wait">
          <motion.p
            key={stage}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35 }}
            className="text-xl font-medium tracking-tight"
          >
            {stages[stage]}…
          </motion.p>
        </AnimatePresence>
        <p className="text-sm text-mint-200/60">{t("analysing")}…</p>
      </div>
    </motion.div>
  );
}
