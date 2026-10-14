"use client";

import { useFormContext, useWatch } from "react-hook-form";
import { motion } from "motion/react";
import { Check } from "lucide-react";

import { FieldMessage } from "@/components/forms/text-field";
import { CROP_LABELS, CROP_SCIENTIFIC } from "@/lib/constants";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";
import { CROPS } from "@/types/triage";

export function CropStep() {
  const { register, control, formState } = useFormContext<ReportFormInput>();
  const selected = useWatch({ control, name: "crop" });

  return (
    <fieldset aria-describedby={formState.errors.crop ? "crop-error" : undefined}>
      <legend className="sr-only">Crop</legend>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-3">
        {CROPS.map((crop, index) => {
          const isSelected = selected === crop;
          return (
            <motion.label
              key={crop}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.03 * index, duration: 0.5 }}
              whileTap={{ scale: 0.97 }}
              className={cn(
                "relative flex min-h-24 cursor-pointer flex-col justify-between rounded-2xl border p-4 transition-colors duration-300 has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-mint-400",
                isSelected
                  ? "border-forest-900 bg-forest-900 text-mint-100"
                  : "border-forest-900/10 bg-white/70 hover:border-forest-900/35 hover:bg-white",
              )}
            >
              <input type="radio" value={crop} className="sr-only" {...register("crop")} />
              <span className="pr-6 text-lg leading-tight font-medium">{CROP_LABELS[crop]}</span>
              <span className={cn("text-xs italic", isSelected ? "text-mint-200/70" : "text-forest-900/45")}>
                {CROP_SCIENTIFIC[crop]}
              </span>
              {isSelected ? (
                <motion.span
                  layoutId="crop-check"
                  className="absolute top-3 right-3 flex size-6 items-center justify-center rounded-full bg-mint-300 text-forest-900"
                  transition={{ type: "spring", stiffness: 500, damping: 34 }}
                >
                  <Check className="size-3.5" strokeWidth={2.5} aria-hidden />
                </motion.span>
              ) : null}
            </motion.label>
          );
        })}
      </div>
      <div className="mt-3">
        <FieldMessage id="crop-error" message={formState.errors.crop?.message} />
      </div>
    </fieldset>
  );
}
