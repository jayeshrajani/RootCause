"use client";

import { useState, type ReactNode } from "react";

import { LocationPrompt } from "@/components/farmer/location-prompt";
import { AdditionalDetails } from "@/components/farmer/steps/describe-step";
import { LocationStatus, useFieldLocation } from "@/components/farmer/steps/location-step";
import { PhotoStep } from "@/components/farmer/steps/photo-step";
import { VoiceInput } from "@/components/farmer/voice-input";
import { useI18n } from "@/lib/i18n";

function Part({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section id={`part-${n}`} aria-labelledby={`part-${n}-title`} className="min-w-0 scroll-mt-24 space-y-3">
      <h2 id={`part-${n}-title`} className="flex items-center gap-2.5 text-lg font-medium">
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

/** Photo first, then a voice note. The crop is identified from the photo (and asked only when
 * unsure), so the farmer never has to pick it up front. */
export function ReportSteps({
  onTranscribed,
  voiceNotice,
}: {
  onTranscribed: (transcript: string) => void;
  voiceNotice?: ReactNode;
}) {
  const { t } = useI18n();
  const location = useFieldLocation();
  const [detailsOpen, setDetailsOpen] = useState(false);

  return (
    <div className="grid min-w-0 grid-cols-1 items-start gap-6 md:grid-cols-2 md:gap-x-6 lg:gap-x-10">
      <LocationPrompt location={location} />

      <Part n={1} title={t("partPhoto")}>
        <PhotoStep />
        <LocationStatus location={location} />
      </Part>

      <Part n={2} title={t("partSpeak")}>
        <VoiceInput onTranscribed={onTranscribed} />
        {voiceNotice}
      </Part>

      <div className="min-w-0 md:col-span-2">
        <AdditionalDetails location={location} open={detailsOpen} onOpenChange={setDetailsOpen} />
      </div>
    </div>
  );
}
