"use client";

import { useFormContext, useWatch } from "react-hook-form";
import { MapPin, Mic } from "lucide-react";

import { LocationStep, type FieldLocation } from "@/components/farmer/steps/location-step";
import { Chip } from "@/components/forms/chip";
import { FieldMessage, inputClass } from "@/components/forms/text-field";
import {
  DESCRIPTION_MAX,
  SYMPTOM_PHRASES,
} from "@/lib/constants";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";
import { SYMPTOM_DURATIONS } from "@/types/triage";
import { useI18n, type TranslationKey } from "@/lib/i18n";

const DURATION_KEYS: Record<(typeof SYMPTOM_DURATIONS)[number], TranslationKey> = {
  less_than_3_days: "durationShort",
  "3_to_7_days": "durationWeek",
  "1_to_2_weeks": "durationFortnight",
  more_than_2_weeks: "durationLong",
  not_sure: "durationUnsure",
};
const SYMPTOM_KEYS: Record<string, TranslationKey> = {
  "Yellowing leaves": "symptomYellow",
  "Brown or black spots": "symptomSpots",
  "Wilting or drooping": "symptomWilting",
  "Holes in leaves": "symptomHoles",
  "White or grey powder": "symptomPowder",
  "Curling leaves": "symptomCurl",
  "Dry, burnt edges": "symptomEdges",
  "Stunted growth": "symptomStunted",
  "Rotting stem or fruit": "symptomRot",
  "Insects visible": "symptomInsects",
};

function togglePhrase(text: string, phrase: string): string {
  const sentence = `${phrase}.`;
  if (text.includes(sentence)) {
    return text.replace(sentence, "").replace(/\s{2,}/g, " ").trim();
  }
  return text.trim() ? `${text.trim()} ${sentence}` : sentence;
}

export function SymptomsStep() {
  const { t } = useI18n();
  const { register, control, setValue, formState } = useFormContext<ReportFormInput>();
  const [description, duration] = useWatch({ control, name: ["description", "symptom_duration"] });
  const errors = formState.errors;
  const error = errors.description?.message;

  return (
    <div className="grid gap-x-10 gap-y-8 rounded-[24px] border border-forest-900/10 bg-white/60 p-5 sm:p-7 md:grid-cols-2">
      <button
        type="button"
        disabled
        aria-describedby="voice-soon"
        className="flex min-h-16 w-full cursor-not-allowed items-center gap-4 rounded-2xl border border-dashed border-forest-900/20 bg-white/50 p-4 text-left md:col-span-2"
      >
        <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-forest-900/[0.08] text-forest-900/60">
          <Mic className="size-5" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium text-forest-900/80">{t("recordVoice")}</span>
          <span id="voice-soon" className="block text-sm text-muted-foreground">
            {t("voiceSoon")}
          </span>
        </span>
      </button>

      <div className="min-w-0 space-y-7">
        <fieldset className="min-w-0">
          <legend className="mb-3 text-sm font-medium">{t("tapSymptoms")}</legend>
          <div className="flex flex-wrap gap-2">
            {SYMPTOM_PHRASES.map((phrase) => (
              <Chip
                key={phrase}
                size="sm"
                active={description.includes(`${phrase}.`)}
                onClick={() =>
                  setValue("description", togglePhrase(description, phrase), {
                    shouldValidate: !!error,
                    shouldDirty: true,
                  })
                }
              >
                {t(SYMPTOM_KEYS[phrase] ?? "symptomYellow")}
              </Chip>
            ))}
          </div>
        </fieldset>

        <fieldset className="min-w-0">
          <legend className="mb-3 text-sm font-medium">{t("symptomDuration")}</legend>
          <div className="flex flex-wrap gap-2">
            {SYMPTOM_DURATIONS.map((value) => (
              <Chip
                key={value}
                size="sm"
                icon={false}
                active={duration === value}
                onClick={() =>
                  setValue("symptom_duration", duration === value ? "" : value, {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
              >
                {t(DURATION_KEYS[value])}
              </Chip>
            ))}
          </div>
          <FieldMessage id="duration-error" message={errors.symptom_duration?.message} />
        </fieldset>
      </div>

      <div className="min-w-0 space-y-2">
        <label htmlFor="description" className="block text-sm font-medium">
          {t("typeSymptoms")}
        </label>
        <textarea
          id="description"
          rows={4}
          maxLength={DESCRIPTION_MAX}
          placeholder={t("descriptionPlaceholder")}
          aria-invalid={!!error || undefined}
          aria-describedby={error ? "description-error" : undefined}
          className={cn(inputClass, "h-auto min-h-36 resize-none py-3 leading-relaxed")}
          {...register("description")}
        />
        <p className="text-right text-xs text-muted-foreground tabular-nums">
          {description.length}/{DESCRIPTION_MAX}
        </p>
        <FieldMessage id="description-error" message={error} />
      </div>
    </div>
  );
}

export function FieldLocationCard({ location }: { location: FieldLocation }) {
  const { t } = useI18n();
  return (
    <section
      id="step-location"
      aria-labelledby="where-field"
      className="scroll-mt-20 rounded-[24px] border border-forest-900/10 bg-white/60 p-5 sm:p-7"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="where-field" className="flex items-center gap-2.5 text-lg font-medium">
          <span className="flex size-7 items-center justify-center rounded-full bg-mint-200 text-forest-800" aria-hidden>
            <MapPin className="size-4" />
          </span>
          {t("whereField")}
        </h2>
        <span className="text-sm text-muted-foreground">{t("optional")}</span>
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground sm:pl-[2.375rem]">{t("locationWhy")}</p>
      <div className="mt-5">
        <LocationStep location={location} />
      </div>
    </section>
  );
}
