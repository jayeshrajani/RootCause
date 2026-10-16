"use client";

import { Check } from "lucide-react";

import { CROP_LABELS, CROP_LOCAL_NAMES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { CROPS, type Crop } from "@/types/triage";

interface CropPickerProps {
  value: Crop | null;
  onChange: (crop: Crop) => void;
  label: string;
  disabled?: boolean;
}

export function CropPicker({ value, onChange, label, disabled }: CropPickerProps) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="sr-only">{label}</legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-2 lg:grid-cols-3">
        {CROPS.map((crop) => {
          const active = value === crop;
          return (
            <button
              key={crop}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(crop)}
              className={cn(
                "flex min-h-14 items-center justify-between gap-2 rounded-lg border px-3.5 py-2 text-left transition-colors duration-200 disabled:opacity-60",
                active
                  ? "border-forest-900 bg-forest-900 text-mint-100"
                  : "border-forest-900/15 bg-white/80 hover:border-forest-900/40",
              )}
            >
              <span className="min-w-0">
                <span className="block font-medium leading-tight">{CROP_LABELS[crop]}</span>
                {CROP_LOCAL_NAMES[crop] ? (
                  <span
                    className={cn(
                      "block text-xs leading-tight",
                      active ? "text-mint-200/80" : "text-muted-foreground",
                    )}
                  >
                    {CROP_LOCAL_NAMES[crop]}
                  </span>
                ) : null}
              </span>
              {active ? <Check className="size-4 shrink-0" aria-hidden /> : null}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
