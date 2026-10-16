"use client";

import { useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, SlidersHorizontal } from "lucide-react";

import { LocationStep, type FieldLocation } from "@/components/farmer/steps/location-step";
import { Chip } from "@/components/forms/chip";
import { FieldMessage, inputClass } from "@/components/forms/text-field";
import {
  DESCRIPTION_MAX,
  SYMPTOM_DURATION_LABELS,
  SYMPTOM_PHRASES,
} from "@/lib/constants";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";
import { SYMPTOM_DURATIONS } from "@/types/triage";

const DETAIL_FIELDS = ["description", "symptom_duration", "latitude", "longitude", "location_label"];

function togglePhrase(text: string, phrase: string): string {
  const sentence = `${phrase}.`;
  if (text.includes(sentence)) {
    return text.replace(sentence, "").replace(/\s{2,}/g, " ").trim();
  }
  return text.trim() ? `${text.trim()} ${sentence}` : sentence;
}

export function AdditionalDetails({
  location,
  open: openProp,
  onOpenChange,
}: {
  location: FieldLocation;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const { register, control, setValue, formState } = useFormContext<ReportFormInput>();
  const [description, duration] = useWatch({ control, name: ["description", "symptom_duration"] });
  const [openState, setOpenState] = useState(false);
  const open = openProp ?? openState;
  const setOpen = (next: boolean) => {
    if (openProp === undefined) setOpenState(next);
    onOpenChange?.(next);
  };
  const errors = formState.errors;
  const error = errors.description?.message;
  const isOpen = open || DETAIL_FIELDS.some((f) => f in errors);

  return (
    <section className="rounded-lg border border-forest-900/10 bg-white/50">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={isOpen}
        aria-controls="additional-details"
        className="flex min-h-16 w-full items-center gap-4 p-4 text-left"
      >
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-mint-100 text-forest-700">
          <SlidersHorizontal className="size-4" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium">
            Additional details <span className="font-normal text-muted-foreground">(optional)</span>
          </span>
          <span className="block text-sm text-muted-foreground">
            Location, what you notice, and how long
          </span>
        </span>
        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} aria-hidden>
          <ChevronDown className="size-5 text-forest-900/50" />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen ? (
          <motion.div
            id="additional-details"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-1 gap-6 border-t border-forest-900/10 p-4 pt-6 md:grid-cols-2 lg:gap-x-10 lg:p-6">
              <div className="min-w-0 space-y-3">
                <p className="text-sm font-medium">Where is the field?</p>
                <LocationStep location={location} />
              </div>

              <div className="min-w-0 space-y-3">
                <p className="text-sm font-medium">Tap what you notice</p>
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
                      {phrase}
                    </Chip>
                  ))}
                </div>
              </div>

              <div className="min-w-0 space-y-2">
                <label htmlFor="description" className="block text-sm font-medium">
                  Or type it
                </label>
                <textarea
                  id="description"
                  rows={4}
                  maxLength={DESCRIPTION_MAX}
                  placeholder="e.g. Started on the lower leaves three days ago. About a quarter of the field."
                  aria-invalid={!!error || undefined}
                  aria-describedby={error ? "description-error" : undefined}
                  className={cn(inputClass, "h-auto min-h-32 resize-none py-3 leading-relaxed")}
                  {...register("description")}
                />
                <p className="text-right text-xs text-muted-foreground tabular-nums">
                  {description.length}/{DESCRIPTION_MAX}
                </p>
                <FieldMessage id="description-error" message={error} />
              </div>

              <fieldset className="min-w-0 space-y-3">
                <legend className="mb-3 text-sm font-medium">How long has this been going on?</legend>
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
                      {SYMPTOM_DURATION_LABELS[value]}
                    </Chip>
                  ))}
                </div>
                <FieldMessage id="duration-error" message={errors.symptom_duration?.message} />
              </fieldset>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}
