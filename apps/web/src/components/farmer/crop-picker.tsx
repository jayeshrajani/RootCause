"use client";

import { useId, type ReactNode } from "react";
import { LayoutGroup, motion } from "motion/react";
import { Check } from "lucide-react";

import { CROP_LOCAL_NAMES } from "@/lib/constants";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { CROPS, type Crop } from "@/types/triage";

export const CROP_KEYS: Record<Crop, TranslationKey> = {
  rice: "cropRice",
  wheat: "cropWheat",
  maize: "cropMaize",
  cotton: "cropCotton",
  sugarcane: "cropSugarcane",
  soybean: "cropSoybean",
  groundnut: "cropGroundnut",
  chickpea: "cropChickpea",
  tomato: "cropTomato",
  potato: "cropPotato",
  onion: "cropOnion",
  chilli: "cropChilli",
  other: "cropOther",
};

interface CropPickerProps {
  value: Crop | null;
  onChange: (crop: Crop) => void;
  label: string;
  disabled?: boolean;
  /** Rendered as a two-column cell after the crops, e.g. an "I'm not sure" option. */
  extra?: ReactNode;
}

export function CropPicker({ value, onChange, label, disabled, extra }: CropPickerProps) {
  const { t } = useI18n();
  const group = useId();
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="sr-only">{label}</legend>
      <LayoutGroup id={group}>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          {CROPS.map((crop) => {
            const active = value === crop;
            const local = crop !== "other" ? CROP_LOCAL_NAMES[crop] : null;
            return (
              <motion.button
                key={crop}
                type="button"
                aria-pressed={active}
                onClick={() => onChange(crop)}
                whileTap={{ scale: 0.97 }}
                className={cn(
                  "relative isolate flex min-h-[4.25rem] items-center justify-between gap-2 overflow-hidden rounded-2xl border px-4 py-3 text-left transition-[border-color,box-shadow,translate] duration-200 disabled:opacity-60",
                  crop === "other" && "max-sm:col-span-2",
                  active
                    ? "border-forest-900 text-mint-100"
                    : "border-forest-900/10 bg-white/85 hover:-translate-y-0.5 hover:border-forest-900/30 hover:shadow-[0_12px_24px_-18px_rgba(22,54,38,0.55)]",
                )}
              >
                {active ? (
                  <motion.span
                    layoutId="crop-active"
                    className="absolute inset-0 -z-10 bg-forest-900"
                    transition={{ type: "spring", stiffness: 420, damping: 36 }}
                    aria-hidden
                  />
                ) : null}
                <span className="min-w-0">
                  <span className="block font-medium leading-tight">{t(CROP_KEYS[crop])}</span>
                  {local ? (
                    <span
                      className={cn(
                        "mt-0.5 block text-xs leading-tight",
                        active ? "text-mint-200/80" : "text-muted-foreground",
                      )}
                    >
                      {local}
                    </span>
                  ) : null}
                </span>
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full transition-colors duration-200",
                    active ? "bg-mint-300 text-forest-900" : "border border-forest-900/15",
                  )}
                  aria-hidden
                >
                  {active ? (
                    <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 22 }}>
                      <Check className="size-3.5" strokeWidth={3} />
                    </motion.span>
                  ) : null}
                </span>
              </motion.button>
            );
          })}
          {extra ? <div className="col-span-2 min-w-0">{extra}</div> : null}
        </div>
      </LayoutGroup>
    </fieldset>
  );
}
