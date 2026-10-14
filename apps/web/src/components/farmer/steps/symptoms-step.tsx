"use client";

import { useFormContext, useWatch } from "react-hook-form";
import { motion } from "motion/react";
import { Check, Plus } from "lucide-react";

import { FieldMessage, inputClass } from "@/components/forms/text-field";
import { DESCRIPTION_MAX, SYMPTOM_DURATION_LABELS, SYMPTOM_PHRASES } from "@/lib/constants";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";
import { SYMPTOM_DURATIONS } from "@/types/triage";

function togglePhrase(text: string, phrase: string): string {
  const sentence = `${phrase}.`;
  if (text.includes(sentence)) {
    return text.replace(sentence, "").replace(/\s{2,}/g, " ").trim();
  }
  return text.trim() ? `${text.trim()} ${sentence}` : sentence;
}

function Chip({
  active,
  onClick,
  children,
  icon = true,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  icon?: boolean;
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-10 items-center gap-1.5 rounded-full border px-4 text-sm transition-colors duration-200",
        active
          ? "border-forest-900 bg-forest-900 text-mint-100"
          : "border-forest-900/15 bg-white/70 text-forest-900 hover:border-forest-900/40",
      )}
    >
      {icon ? (
        active ? <Check className="size-3.5" aria-hidden /> : <Plus className="size-3.5 opacity-50" aria-hidden />
      ) : null}
      {children}
    </motion.button>
  );
}

export function SymptomsStep() {
  const { register, control, setValue, formState } = useFormContext<ReportFormInput>();
  const description = useWatch({ control, name: "description" });
  const duration = useWatch({ control, name: "symptom_duration" });
  const error = formState.errors.description?.message;

  return (
    <div className="space-y-9">
      <div className="space-y-3">
        <p className="text-sm font-medium">Tap anything you notice</p>
        <div className="flex flex-wrap gap-2">
          {SYMPTOM_PHRASES.map((phrase) => (
            <Chip
              key={phrase}
              active={description.includes(`${phrase}.`)}
              onClick={() =>
                setValue("description", togglePhrase(description, phrase), {
                  shouldValidate: formState.isSubmitted || !!error,
                  shouldDirty: true,
                })
              }
            >
              {phrase}
            </Chip>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="description" className="block text-sm font-medium">
          Describe it in your own words
        </label>
        <textarea
          id="description"
          rows={5}
          maxLength={DESCRIPTION_MAX}
          placeholder="e.g. Started on the lower leaves near the canal. About a quarter of the field."
          aria-invalid={!!error || undefined}
          aria-describedby={error ? "description-error" : undefined}
          className={cn(inputClass, "h-auto min-h-36 resize-none py-3.5 leading-relaxed")}
          {...register("description")}
        />
        <div className="flex items-start justify-between gap-4">
          <FieldMessage id="description-error" message={error} />
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            {description.length}/{DESCRIPTION_MAX}
          </span>
        </div>
      </div>

      <div className="space-y-3" role="group" aria-labelledby="duration-label">
        <p id="duration-label" className="text-sm font-medium">
          How long has this been going on?{" "}
          <span className="font-normal text-muted-foreground">Optional</span>
        </p>
        <div className="flex flex-wrap gap-2">
          {SYMPTOM_DURATIONS.map((value) => (
            <Chip
              key={value}
              icon={false}
              active={duration === value}
              onClick={() => setValue("symptom_duration", duration === value ? "" : value)}
            >
              {SYMPTOM_DURATION_LABELS[value]}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  );
}
