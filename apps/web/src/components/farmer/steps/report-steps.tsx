"use client";

import { useState, type ReactNode } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { Check } from "lucide-react";

import { CropPicker } from "@/components/farmer/crop-picker";
import { AdditionalDetails } from "@/components/farmer/steps/describe-step";
import { LocationStatus, useFieldLocation } from "@/components/farmer/steps/location-step";
import { PhotoStep } from "@/components/farmer/steps/photo-step";
import { VoiceInput } from "@/components/farmer/voice-input";
import { FieldMessage } from "@/components/forms/text-field";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";

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
  const { control, setValue, formState } = useFormContext<ReportFormInput>();
  const crop = useWatch({ control, name: "crop" });
  const location = useFieldLocation();
  const [detailsOpen, setDetailsOpen] = useState(false);

  const reviewTranscript = () => {
    setDetailsOpen(true);
    // Wait for the details panel to expand, then bring the editable text into view.
    window.setTimeout(() => {
      document.getElementById("description")?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    }, 450);
  };

  const choose = (value: ReportFormInput["crop"]) => {
    setValue("crop", value, { shouldDirty: true, shouldValidate: true });
    location.requestOnce();
  };

  return (
    <div className="grid min-w-0 grid-cols-1 items-start gap-6 md:grid-cols-2 md:gap-x-6 lg:gap-x-10">
      <Part n={1} title="Choose your crop">
        <CropPicker
          value={crop || null}
          label="Choose your crop"
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
          I&apos;m not sure. Guess from the photo and ask me.
        </button>
        <FieldMessage id="crop-error" message={formState.errors.crop?.message} />
        <LocationStatus location={location} />
      </Part>

      <div className="min-w-0 space-y-6">
        <Part n={2} title="Add a photo">
          <PhotoStep />
        </Part>

        <Part n={3} title="Tell us what you see">
          <VoiceInput onTranscribed={reviewTranscript} />
        </Part>
      </div>

      <div className="min-w-0 md:col-span-2">
        <AdditionalDetails location={location} open={detailsOpen} onOpenChange={setDetailsOpen} />
      </div>
    </div>
  );
}