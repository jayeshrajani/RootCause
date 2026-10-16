"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";

import { CropPicker } from "@/components/farmer/crop-picker";
import { CROP_LABELS, CROP_LOCAL_NAMES } from "@/lib/constants";
import { objectUrlFor } from "@/lib/object-urls";
import { useI18n } from "@/lib/i18n";
import type { Crop } from "@/types/triage";

/** Shown between crop identification and diagnosis when the crop is uncertain. */
export function CropConfirm({
  photo,
  candidates,
  onChoose,
}: {
  photo?: File;
  candidates: Crop[];
  onChoose: (crop: Crop | null) => void;
}) {
  const { t } = useI18n();
  const [showAll, setShowAll] = useState(candidates.length === 0);

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-labelledby="crop-confirm-title"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-end justify-center bg-forest-900/70 p-4 backdrop-blur-sm sm:items-center"
    >
      <motion.div
        initial={{ y: 24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-[28px] bg-background p-6 shadow-2xl"
      >
        <div className="flex items-start gap-4">
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
            <img src={objectUrlFor(photo)} alt="" className="size-16 shrink-0 rounded-2xl object-cover" />
          ) : null}
          <div>
            <h2 id="crop-confirm-title" className="text-xl font-medium">
              {t("confirmCropTitle")}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{t("confirmCropBody")}</p>
          </div>
        </div>

        {candidates.length ? (
          <div className="mt-5 grid gap-2">
            {candidates.map((crop, i) => (
              <button
                key={crop}
                type="button"
                onClick={() => onChoose(crop)}
                autoFocus={i === 0}
                className="flex items-center justify-between rounded-2xl border border-forest-900/15 bg-white/80 px-4 py-3 text-left transition-colors hover:border-forest-900 hover:bg-forest-900 hover:text-mint-100"
              >
                <span>
                  <span className="block font-medium">{CROP_LABELS[crop]}</span>
                  {CROP_LOCAL_NAMES[crop] ? (
                    <span className="block text-xs opacity-70">{CROP_LOCAL_NAMES[crop]}</span>
                  ) : null}
                </span>
                {i === 0 ? (
                  <span className="text-xs opacity-70">{t("confirmCropLikely")}</span>
                ) : (
                  <ArrowRight className="size-4 opacity-60" aria-hidden />
                )}
              </button>
            ))}
          </div>
        ) : null}

        {showAll ? (
          <div className="mt-5">
            <CropPicker value={null} onChange={onChoose} label={t("confirmCropTitle")} />
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="mt-4 text-sm font-medium text-forest-700 underline-offset-2 hover:underline"
          >
            {t("confirmCropOther")}
          </button>
        )}

        <button
          type="button"
          onClick={() => onChoose(null)}
          className="mt-5 block w-full rounded-full py-2 text-sm text-muted-foreground hover:text-foreground"
        >
          {t("confirmCropSkip")}
        </button>
      </motion.div>
    </motion.div>
  );
}
