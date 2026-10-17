"use client";

import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, MapPin } from "lucide-react";

import { LocationPrompt } from "@/components/farmer/location-prompt";
import {
  LocationStatus,
  LocationStep,
  useFieldLocation,
  type FieldLocation,
} from "@/components/farmer/steps/location-step";
import { PhotoStep } from "@/components/farmer/steps/photo-step";
import { VoiceInput } from "@/components/farmer/voice-input";
import { BotanicalPattern, LeafIllustration } from "@/components/brand/botanical";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function Part({
  n,
  title,
  className,
  children,
}: {
  n: number;
  title: string;
  className?: string;
  children: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <section
      id={`part-${n}`}
      aria-labelledby={`part-${n}-title`}
      className={cn(
        "min-w-0 scroll-mt-24 rounded-[28px] border border-forest-900/10 bg-white/70 p-4 shadow-[0_30px_60px_-45px_rgba(22,54,38,0.5)] backdrop-blur-sm sm:p-5",
        className,
      )}
    >
      <div className="mb-4 flex items-baseline gap-3 px-1">
        <span className="font-mono text-xs text-forest-500" aria-hidden>
          {t("stepLabel")} 0{n}
        </span>
        <h2 id={`part-${n}-title`} className="text-xl font-medium tracking-tight">
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

/** The page header: brand-mint card with the title, the visit meter and the location state. */
function Hero({ intro, meter, location }: { intro: ReactNode; meter: ReactNode; location: FieldLocation }) {
  return (
    <div className="grain relative overflow-hidden rounded-[28px] bg-mint-300 px-5 pt-5 pb-7 text-forest-900 sm:px-8 sm:pt-6 sm:pb-8">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-1/2 left-1/3 h-[140%] w-[90%] rounded-[50%] bg-[radial-gradient(closest-side,rgba(255,255,255,0.65),rgba(255,255,255,0))]" />
      </div>
      <BotanicalPattern className="text-forest-900/[0.05]" />
      <div className="relative flex flex-wrap items-center justify-between gap-2">
        {meter}
        <span className="inline-flex min-h-7 items-center rounded-full bg-white/60 px-3 backdrop-blur-sm has-[p:empty]:hidden [&_p]:min-h-0 [&_p]:text-xs">
          <LocationStatus location={location} />
        </span>
      </div>
      <div className="relative mt-7 lg:mt-6">{intro}</div>
      <LeafIllustration className="pointer-events-none absolute -right-6 -bottom-10 hidden h-56 rotate-[18deg] text-forest-700/25 md:block" />
    </div>
  );
}

/** Only when the location wasn't shared: an optional, collapsed way to add the field's place. */
function LocationFallback({ location }: { location: FieldLocation }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  if (location.hasCoords || location.state.status === "locating") return null;

  return (
    <section className="rounded-[28px] border border-dashed border-forest-900/20 bg-white/40">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="location-fallback"
        className="flex min-h-14 w-full items-center gap-3 p-4 text-left sm:px-6"
      >
        <MapPin className="size-5 shrink-0 text-forest-600" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block font-medium">{t("addLocationTitle")}</span>
          <span className="block text-sm text-muted-foreground">{t("addLocationHint")}</span>
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} aria-hidden>
          <ChevronDown className="size-5 text-forest-900/50" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id="location-fallback"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-forest-900/10 p-4">
              <LocationStep location={location} />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}

/** Photo first, then a voice note. The crop is identified from the photo (and asked only when
 * unsure), so the farmer never has to pick it up front. */
export function ReportSteps({
  intro,
  meter,
  onTranscribed,
  voiceNotice,
}: {
  intro: ReactNode;
  meter: ReactNode;
  onTranscribed: (transcript: string) => void;
  voiceNotice?: ReactNode;
}) {
  const { t } = useI18n();
  const location = useFieldLocation();

  return (
    <div className="space-y-3 sm:space-y-4">
      <LocationPrompt location={location} />
      <Hero intro={intro} meter={meter} location={location} />

      <div className="grid min-w-0 grid-cols-1 items-stretch gap-3 sm:gap-4 md:grid-cols-[1.15fr_1fr]">
        <Part n={1} title={t("partPhoto")}>
          <PhotoStep />
        </Part>

        <Part n={2} title={t("partSpeak")} className="flex flex-col">
          <div className="flex flex-1 flex-col justify-center gap-3">
            <VoiceInput onTranscribed={onTranscribed} />
            {voiceNotice}
          </div>
        </Part>
      </div>

      <LocationFallback location={location} />
    </div>
  );
}
