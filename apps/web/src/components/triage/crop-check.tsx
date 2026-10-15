"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence } from "motion/react";
import { AlertCircle, Check, Sprout } from "lucide-react";

import { AnalysingOverlay } from "@/components/farmer/analysing-overlay";
import { CropPicker } from "@/components/farmer/crop-picker";
import { detectedCropName } from "@/components/triage/summary-card";
import { ApiError, submitTriageReport } from "@/lib/api/client";
import { recallReport, rememberReport } from "@/lib/last-report";
import { saveLatestTriage } from "@/lib/triage-storage";
import type { Crop, TriageResponse } from "@/types/triage";
import { useI18n } from "@/lib/i18n";

export function CropCheck({ result }: { result: TriageResponse }) {
  const { language, t } = useI18n();
  const [confirmed, setConfirmed] = useState(false);
  const [picking, setPicking] = useState(!result.detected_crop);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const report = recallReport();

  if (result.crop || confirmed) return null;

  const rerun = async (crop: Crop) => {
    if (!report) return;
    setBusy(true);
    setError(null);
    try {
      const values = { ...report, crop };
      const next = await submitTriageReport(values, language);
      rememberReport(values);
      saveLatestTriage(next);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-labelledby="crop-check-title"
      className="mb-6 rounded-lg border border-forest-900/15 bg-white p-4 sm:p-5"
    >
      <AnimatePresence>{busy ? <AnalysingOverlay photo={report?.images[0]} /> : null}</AnimatePresence>

      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-mint-100 text-forest-700">
          <Sprout className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 id="crop-check-title" className="text-lg font-medium">
            {result.detected_crop
              ? `${t("cropConfirm")} ${detectedCropName(result.detected_crop, t)}?`
              : t("chooseCropForAdvice")}
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {result.detected_crop ? t("guessedFromPhoto") : t("chooseCropAdvice")}
          </p>
        </div>
      </div>

      {result.detected_crop && !picking ? (
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setConfirmed(true)}
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-forest-900 px-4 font-medium text-mint-100"
          >
            <Check className="size-4" aria-hidden />
            {t("yesCorrect")}
          </button>
          <button
            type="button"
            onClick={() => setPicking(true)}
            className="inline-flex min-h-12 items-center justify-center rounded-lg border border-forest-900/20 px-4 font-medium"
          >
            {t("changeCrop")}
          </button>
        </div>
      ) : null}

      {picking ? (
        report ? (
          <div className="mt-4">
            <CropPicker
              value={null}
              onChange={(crop) => void rerun(crop)}
              disabled={busy}
              label={t("chooseCrop")}
            />
            <p className="mt-3 text-xs text-muted-foreground">
              {t("checkingPhotosAgain")}
            </p>
          </div>
        ) : (
          <p className="mt-4 text-sm">
            {t("photosGone")} {" "}
            <Link href="/report" className="font-medium underline underline-offset-2">
              {t("newReport")}
            </Link>{" "}
            {t("chooseCropFirst")}
          </p>
        )
      ) : null}

      {error ? (
        <p role="alert" className="mt-3 flex items-start gap-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
    </section>
  );
}
