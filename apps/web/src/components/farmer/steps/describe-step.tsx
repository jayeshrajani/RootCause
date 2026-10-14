"use client";

import { useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, Mic, SlidersHorizontal } from "lucide-react";

import { Chip } from "@/components/forms/chip";
import { FieldMessage, inputClass } from "@/components/forms/text-field";
import { LocationStep } from "@/components/farmer/steps/location-step";
import {
  CROP_LABELS,
  DESCRIPTION_MAX,
  SYMPTOM_DURATION_LABELS,
  SYMPTOM_PHRASES,
} from "@/lib/constants";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";
import { CROPS, SYMPTOM_DURATIONS } from "@/types/triage";

const DETAIL_FIELDS = ["crop", "symptom_duration", "latitude", "longitude", "location_label"] as const;

function togglePhrase(text: string, phrase: string): string {
  const sentence = `${phrase}.`;
  if (text.includes(sentence)) {
    return text.replace(sentence, "").replace(/\s{2,}/g, " ").trim();
  }
  return text.trim() ? `${text.trim()} ${sentence}` : sentence;
}

function DetailsPanel() {
  const { control, setValue, formState } = useFormContext<ReportFormInput>();
  const [crop, duration] = useWatch({ control, name: ["crop", "symptom_duration"] });
  const [open, setOpen] = useState(false);
  const hasErrors = DETAIL_FIELDS.some((f) => f in formState.errors);
  const isOpen = open || hasErrors;
  const filled = [crop, duration].filter(Boolean).length;

  return (
    <div className="rounded-3xl border border-forest-900/10 bg-white/50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={isOpen}
        aria-controls="report-details"
        className="flex w-full items-center gap-4 p-5 text-left"
      >
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-mint-100 text-forest-700">
          <SlidersHorizontal className="size-4" aria-hidden />
        </span>
        <span className="flex-1">
          <span className="block font-medium">Add details for a sharper result</span>
          <span className="block text-sm text-muted-foreground">
            {filled ? `${filled} added · ` : ""}Crop, how long, and where. All optional.
          </span>
        </span>
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} aria-hidden>
          <ChevronDown className="size-5 text-forest-900/50" />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen ? (
          <motion.div
            id="report-details"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="space-y-8 border-t border-forest-900/10 px-5 pt-6 pb-6">
              <div className="space-y-3" role="group" aria-labelledby="crop-label">
                <p id="crop-label" className="text-sm font-medium">
                  Crop <span className="font-normal text-muted-foreground">We&apos;ll try to tell from the photo if you skip this</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  {CROPS.map((value) => (
                    <Chip
                      key={value}
                      size="sm"
                      icon={false}
                      active={crop === value}
                      onClick={() => setValue("crop", crop === value ? "" : value, { shouldDirty: true })}
                    >
                      {CROP_LABELS[value]}
                    </Chip>
                  ))}
                </div>
              </div>

              <div className="space-y-3" role="group" aria-labelledby="duration-label">
                <p id="duration-label" className="text-sm font-medium">
                  How long has this been going on?
                </p>
                <div className="flex flex-wrap gap-2">
                  {SYMPTOM_DURATIONS.map((value) => (
                    <Chip
                      key={value}
                      size="sm"
                      icon={false}
                      active={duration === value}
                      onClick={() =>
                        setValue("symptom_duration", duration === value ? "" : value, { shouldDirty: true })
                      }
                    >
                      {SYMPTOM_DURATION_LABELS[value]}
                    </Chip>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-medium">Where is the field?</p>
                <LocationStep />
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export function DescribeStep() {
  const { register, control, setValue, formState } = useFormContext<ReportFormInput>();
  const description = useWatch({ control, name: "description" });
  const error = formState.errors.description?.message;

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <div className="relative">
          <label htmlFor="description" className="sr-only">
            Describe the problem
          </label>
          <textarea
            id="description"
            rows={5}
            maxLength={DESCRIPTION_MAX}
            placeholder="e.g. Started on the lower leaves three days ago. About a quarter of the field. We sprayed last week."
            aria-invalid={!!error || undefined}
            aria-describedby={error ? "description-error" : "description-hint"}
            className={cn(inputClass, "h-auto min-h-40 resize-none py-4 pr-16 leading-relaxed")}
            {...register("description")}
          />
          <button
            type="button"
            disabled
            aria-describedby="voice-soon"
            className="absolute right-3 bottom-3 flex size-11 cursor-not-allowed items-center justify-center rounded-full bg-forest-900/[0.06] text-forest-900/35"
          >
            <Mic className="size-5" aria-hidden />
            <span className="sr-only">Record a voice note</span>
          </button>
        </div>
        <div className="flex items-start justify-between gap-4">
          <p id="description-hint" className="text-xs text-muted-foreground">
            <span id="voice-soon">Voice notes in your language are coming soon.</span>
          </p>
          <span className="text-xs text-muted-foreground tabular-nums">
            {description.length}/{DESCRIPTION_MAX}
          </span>
        </div>
        <FieldMessage id="description-error" message={error} />
      </div>

      <div className="space-y-3">
        <p className="text-sm font-medium">Or tap what you notice</p>
        <div className="flex flex-wrap gap-2">
          {SYMPTOM_PHRASES.map((phrase) => (
            <Chip
              key={phrase}
              active={description.includes(`${phrase}.`)}
              onClick={() =>
                setValue("description", togglePhrase(description, phrase), {
                  shouldValidate: !!error,
                  shouldDirty: true,
                })
              }
            >
              {phrase}
            </Chip>
          ))}
        </div>
      </div>

      <DetailsPanel />
    </div>
  );
}
