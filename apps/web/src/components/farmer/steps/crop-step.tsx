"use client";

import type { ReactNode } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { motion } from "motion/react";
import { Check, Sparkles } from "lucide-react";

import { CropPicker } from "@/components/farmer/crop-picker";
import { FieldLocationCard, SymptomsStep } from "@/components/farmer/steps/describe-step";
import { LocationStatus, useFieldLocation } from "@/components/farmer/steps/location-step";
import { PhotoStep } from "@/components/farmer/steps/photo-step";
import { FieldMessage } from "@/components/forms/text-field";
import type { ReportFormInput } from "@/lib/schemas/report";
import { nextStepId, scrollToStep } from "@/lib/step-scroll";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

function Part({ n, title, aside, children }: { n: number; title: string; aside?: string; children: ReactNode }) {
  return (
    <section id={`step-${n}`} aria-labelledby={`part-${n}`} className="min-w-0 scroll-mt-20 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id={`part-${n}`} className="flex items-center gap-2.5 text-lg font-medium sm:text-xl">
          <span
            className="flex size-7 items-center justify-center rounded-full bg-forest-900 text-sm text-mint-100"
            aria-hidden
          >
            {n}
          </span>
          {title}
        </h2>
        {aside ? <span className="text-sm text-muted-foreground">{aside}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function CropStep() {
  const { t } = useI18n();
  const { control, setValue, getValues, formState } = useFormContext<ReportFormInput>();
  const crop = useWatch({ control, name: "crop" });
  const location = useFieldLocation();
  const unsure = crop === "";

  const choose = (value: ReportFormInput["crop"], advance: boolean) => {
    setValue("crop", value, { shouldDirty: true, shouldValidate: true });
    location.requestOnce();
    if (advance) scrollToStep(nextStepId(getValues(), "crop"));
  };

  return (
    <div className="space-y-10 sm:space-y-12">
      <div className="grid min-w-0 grid-cols-1 items-start gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:gap-12">
        <Part n={1} title={t("chooseCrop")}>
          <CropPicker
            value={crop || null}
            label={t("chooseCrop")}
            onChange={(value) => (crop === value ? choose("", false) : choose(value, true))}
            extra={
              <motion.button
                type="button"
                aria-pressed={unsure}
                onClick={() => choose("", true)}
                whileTap={{ scale: 0.98 }}
                className={cn(
                  "flex h-full min-h-[4.25rem] w-full items-center gap-3 rounded-2xl border border-dashed px-4 py-2 text-left text-sm font-medium transition-colors duration-200",
                  unsure
                    ? "border-forest-700 bg-mint-100 text-forest-900"
                    : "border-forest-900/25 text-forest-900/70 hover:border-forest-900/50 hover:bg-white/60",
                )}
              >
                <span
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-full transition-colors",
                    unsure ? "bg-forest-900 text-mint-100" : "bg-forest-900/[0.07]",
                  )}
                  aria-hidden
                >
                  {unsure ? <Check className="size-4" strokeWidth={3} /> : <Sparkles className="size-4" />}
                </span>
                <span className="leading-snug">{t("notSureCrop")}</span>
              </motion.button>
            }
          />
          <FieldMessage id="crop-error" message={formState.errors.crop?.message} />
          <LocationStatus location={location} />
        </Part>

        <Part n={2} title={t("addPhoto")}>
          <PhotoStep />
        </Part>
      </div>

      <FieldLocationCard location={location} />

      <Part n={3} title={t("tellUs")} aside={t("optional")}>
        <SymptomsStep />
      </Part>
    </div>
  );
}