"use client";

import { motion } from "motion/react";

import { ButtonLink } from "@/components/brand/button";
import { PillLink } from "@/components/brand/pill";
import { useI18n } from "@/lib/i18n";
import { INVESTIGATION_LIMIT } from "@/lib/visit";

const EASE = [0.16, 1, 0.3, 1] as const;

/** A potted seedling having a well-earned nap. */
function NappingPlant() {
  return (
    <div className="relative mx-auto h-44 w-40" aria-hidden>
      {["z", "z", "Z"].map((letter, i) => (
        <motion.span
          key={i}
          className="absolute font-mono font-medium text-forest-600"
          style={{ right: 6 - i * 4, top: 34 - i * 16, fontSize: 13 + i * 5 }}
          animate={{ opacity: [0, 1, 0], y: [6, -6, -14] }}
          transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.6, ease: "easeOut" }}
        >
          {letter}
        </motion.span>
      ))}
      <svg viewBox="0 0 160 180" fill="none" className="size-full">
        <ellipse cx="80" cy="168" rx="46" ry="7" fill="#214735" fillOpacity=".12" />
        <path d="M56 124h48l-6 40H62l-6-40Z" fill="#C77B52" />
        <path d="M54 122c0-4 12-6 26-6s26 2 26 6-12 6-26 6-26-2-26-6Z" fill="#E3A36A" />
        <motion.g
          style={{ transformOrigin: "80px 120px" }}
          animate={{ rotate: [12, 15, 12] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
        >
          <path d="M80 120c0-24 2-44 10-62" stroke="#376847" strokeWidth="4" strokeLinecap="round" />
          <path d="M84 92C58 98 46 82 48 66c18-3 36 6 36 26Z" fill="#6E9A65" stroke="#376847" strokeWidth="2" />
          <path d="M90 58c4-22 24-30 40-22-2 20-18 30-40 22Z" fill="#A2B986" stroke="#376847" strokeWidth="2" />
          {/* Closed, contented eyes and a small smile on the top leaf. */}
          <path d="M104 46q3 3 6 0M116 44q3 3 6 0" stroke="#214735" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M110 52q4 3 8 0" stroke="#214735" strokeWidth="1.6" strokeLinecap="round" />
        </motion.g>
      </svg>
    </div>
  );
}

/** Shown instead of the report once this visit has used all its investigations. */
export function InvestigationLimit({ hasResult }: { hasResult: boolean }) {
  const { t } = useI18n();
  return (
    <motion.section
      role="status"
      aria-labelledby="limit-title"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: EASE }}
      className="mx-auto flex w-full max-w-lg flex-col items-center px-5 py-12 text-center sm:py-20"
    >
      <NappingPlant />
      <p className="label-caps mt-6 text-forest-600">
        {INVESTIGATION_LIMIT}/{INVESTIGATION_LIMIT} {t("limitBadge")}
      </p>
      <h1 id="limit-title" className="mt-3 text-3xl leading-tight font-medium tracking-tight sm:text-4xl">
        {t("limitTitle")}
      </h1>
      <p className="mt-3 leading-relaxed text-muted-foreground">{t("limitBody")}</p>
      <div className="mt-8 flex flex-col items-center gap-3">
        {hasResult ? <PillLink href="/results">{t("limitLastResult")}</PillLink> : null}
        {hasResult ? (
          <ButtonLink href="/" variant="ghost">
            {t("limitHome")}
          </ButtonLink>
        ) : (
          <PillLink href="/">{t("limitHome")}</PillLink>
        )}
      </div>
    </motion.section>
  );
}
