"use client";

import type { ReactNode } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { Check, Mic } from "lucide-react";

import { CropPicker } from "@/components/farmer/crop-picker";
import { AdditionalDetails } from "@/components/farmer/steps/describe-step";
import { LocationStatus, useFieldLocation } from "@/components/farmer/steps/location-step";
import { PhotoStep } from "@/components/farmer/steps/photo-step";
import { FieldMessage } from "@/components/forms/text-field";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

function Part({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`part-${n}`} className="min-w-0 space-y-3">
      <h2 id={`part-${n}`} className="flex items-center gap-2.5 text-lg font-medium">
        <span
          className="flex size-7 items-center justify-center rounded-full bg-forest-900 text-sm text-mint-100"
          aria-hidden
        >
          {n}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

export function CropStep() {
  const { t } = useI18n();
  const { control, setValue, formState } = useFormContext<ReportFormInput>();
  const crop = useWatch({ control, name: "crop" });
  const location = useFieldLocation();

  const choose = (value: ReportFormInput["crop"]) => {
    setValue("crop", value, { shouldDirty: true, shouldValidate: true });
    location.requestOnce();
  };

  return (
    <div className="grid min-w-0 grid-cols-1 items-start gap-6 md:grid-cols-2 md:gap-x-6 lg:gap-x-10">
      <Part n={1} title={t("chooseCrop")}>
        <CropPicker
          value={crop || null}
          label={t("chooseCrop")}
          onChange={(value) => choose(crop === value ? "" : value)}
        />
        <button
          type="button"
          aria-pressed={crop === ""}
          onClick={() => choose("")}
          className={cn(
            "flex min-h-12 w-full items-center justify-center gap-2 rounded-lg border border-dashed px-4 text-sm font-medium transition-colors",
            crop === ""
              ? "border-forest-900 bg-mint-100 text-forest-900"
              : "border-forest-900/25 text-forest-900/70 hover:border-forest-900/50",
          )}
        >
          {crop === "" ? <Check className="size-4" aria-hidden /> : null}
          {t("notSureCrop")}
        </button>
        <FieldMessage id="crop-error" message={formState.errors.crop?.message} />
        <LocationStatus location={location} />
      </Part>

      <div className="min-w-0 space-y-6">
        <Part n={2} title={t("addPhoto")}>
          <PhotoStep />
        </Part>

        <Part n={3} title={t("tellUs")}>
        <button
          type="button"
          disabled
          aria-describedby="voice-soon"
          className="flex min-h-16 w-full cursor-not-allowed items-center gap-4 rounded-lg border border-forest-900/15 bg-white/60 p-4 text-left"
        >
          <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-forest-900/10 text-forest-900/50">
            <Mic className="size-5" aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-medium text-forest-900/70">{t("recordVoice")}</span>
            <span id="voice-soon" className="block text-sm text-muted-foreground">
              {t("voiceSoon")}
            </span>
          </span>
        </button>
        </Part>
      </div>

      <div className="min-w-0 md:col-span-2">
        <AdditionalDetails location={location} />
      </div>
    </div>
  );
}