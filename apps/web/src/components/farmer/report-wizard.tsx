"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { FormProvider, useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, Camera, Sparkles } from "lucide-react";

import { pillClass, PillIcon } from "@/components/brand/pill";
import { AnalysingOverlay } from "@/components/farmer/analysing-overlay";
import { InvestigationLimit } from "@/components/farmer/investigation-limit";
import { CropConfirm } from "@/components/farmer/crop-confirm";
import { ReportSteps } from "@/components/farmer/steps/report-steps";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, identifyCrop, submitTriageReport } from "@/lib/api/client";
import { useI18n } from "@/lib/i18n";
import { rememberReport } from "@/lib/last-report";
import {
  reportFormDefaults,
  reportFormSchema,
  type ReportFormInput,
  type ReportFormValues,
} from "@/lib/schemas/report";
import { scrollToStep } from "@/lib/step-scroll";
import { readLatestTriageRaw, saveLatestTriage } from "@/lib/triage-storage";
import { INVESTIGATION_LIMIT, investigationsLeft } from "@/lib/visit";
import type { Crop } from "@/types/triage";

type FieldName = FieldPath<ReportFormInput>;

const FIELDS = new Set<string>(Object.keys(reportFormDefaults));

const ERROR_TITLES: Record<ApiError["kind"], string> = {
  network: "Couldn't reach RootCause",
  timeout: "The analysis took too long",
  validation: "Please check your report",
  server: "Analysis didn't finish",
  limit: "That's all for this visit",
};

const noSubscribe = () => () => {};

// The last fresh visit we scrolled for; back/forward re-shows keep their scroll position.
let scrolledFor: string | null = null;

/** Pages stay alive between navigations (Cache Components / Activity), so key the form on
 * `bfcacheId`: every "New report" link starts a fresh report at step 1, while browser back still
 * restores the one in progress. */
export function ReportWizard() {
  const { bfcacheId } = useRouter();
  return <ReportForm key={bfcacheId} visit={bfcacheId} />;
}

function ReportForm({ visit }: { visit: string }) {
  const router = useRouter();
  const { t } = useI18n();
  // Set by a voice note: shown while analysing, and starts the triage once a photo is added.
  const [heard, setHeard] = useState<string | null>(null);
  const [waitingForPhoto, setWaitingForPhoto] = useState(false);
  // Read from the visit cookie in the browser; the server render assumes a full allowance.
  const left = useSyncExternalStore(noSubscribe, investigationsLeft, () => INVESTIGATION_LIMIT);
  const [hitLimit, setHitLimit] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [phase, setPhase] = useState<"identify" | "analyse">("analyse");
  const [cropQuestion, setCropQuestion] = useState<{
    candidates: Crop[];
    answer: (crop: Crop | null) => void;
  } | null>(null);

  const form = useForm<ReportFormInput, unknown, ReportFormValues>({
    resolver: zodResolver(reportFormSchema),
    defaultValues: reportFormDefaults,
    mode: "onTouched",
  });
  const { handleSubmit, setError, getValues, formState, watch } = form;

  // A new report starts at the top, even when arriving from a scrolled results page.
  useEffect(() => {
    if (scrolledFor === visit) return;
    scrolledFor = visit;
    window.scrollTo({ top: 0 });
  }, [visit]);

  /** Stage 1: identify the crop; continue automatically when confident, otherwise ask. */
  async function resolveCrop(values: ReportFormValues): Promise<Crop | ""> {
    if (values.crop) return values.crop;
    setPhase("identify");
    const identified = await identifyCrop(values);
    if (identified?.crop && !identified.needs_confirmation) return identified.crop;
    const choice = await new Promise<Crop | null>((resolve) =>
      setCropQuestion({ candidates: identified?.candidates ?? [], answer: resolve }),
    );
    setCropQuestion(null);
    return choice ?? "";
  }

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    if (investigationsLeft() === 0) {
      setHitLimit(true);
      return;
    }
    try {
      const crop = await resolveCrop(values);
      setPhase("analyse");
      const result = await submitTriageReport({ ...values, crop });
      rememberReport(values);
      saveLatestTriage(result);
      router.push("/results");
    } catch (error) {
      const apiError =
        error instanceof ApiError
          ? error
          : new ApiError("server", "Something unexpected went wrong. Please try again.");
      if (apiError.kind === "limit") {
        setHitLimit(true);
        return;
      }
      for (const { field, message } of apiError.fieldErrors) {
        if (FIELDS.has(field)) setError(field as FieldName, { type: "server", message });
      }
      setSubmitError(apiError);
    }
  });

  const onTranscribed = (transcript: string) => {
    setHeard(transcript);
    if (getValues("images").length > 0) {
      void submit();
    } else {
      setWaitingForPhoto(true);
      scrollToStep("part-1", 0);
    }
  };

  // The farmer already described the problem by voice: start as soon as the photo arrives.
  const waitingRef = useRef(waitingForPhoto);
  useEffect(() => {
    waitingRef.current = waitingForPhoto;
  }, [waitingForPhoto]);
  useEffect(() => {
    const subscription = watch((values, { name }) => {
      if (name !== "images" || !waitingRef.current || !values.images?.length) return;
      setWaitingForPhoto(false);
      void submit();
    });
    return () => subscription.unsubscribe();
  }, [watch, submit]);

  const coordinates = getValues("latitude") && getValues("longitude")
    ? { latitude: getValues("latitude"), longitude: getValues("longitude") }
    : null;

  if (hitLimit || left === 0) {
    return <InvestigationLimit hasResult={readLatestTriageRaw() !== null} />;
  }

  return (
    <FormProvider {...form}>
      <AnimatePresence>
        {formState.isSubmitting && cropQuestion === null ? (
          <AnalysingOverlay
            key={phase}
            photo={getValues("images")[0]}
            phase={phase}
            coordinates={coordinates}
            transcript={heard}
            hasDescription={Boolean(getValues("description")?.trim())}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {cropQuestion !== null ? (
          <CropConfirm
            photo={getValues("images")[0]}
            candidates={cropQuestion.candidates}
            onChoose={cropQuestion.answer}
          />
        ) : null}
      </AnimatePresence>

      <form
        onSubmit={(e) => void submit(e)}
        noValidate
        className="mx-auto w-full max-w-6xl px-3 pt-3 pb-28 sm:px-6 sm:pt-6 lg:px-8 lg:pb-16"
      >
        <ReportSteps
          intro={
            <>
              <div className="lg:flex lg:items-end lg:justify-between lg:gap-10">
                <h1 className="max-w-[16ch] text-[clamp(2.1rem,6vw,3.25rem)] leading-[1] font-medium tracking-[-0.035em] text-balance lg:max-w-none">
                  {t("reportHeading")}
                </h1>
                <p className="mt-4 max-w-[46ch] text-forest-900/70 sm:text-lg lg:mt-0 lg:max-w-[34ch] lg:text-base">
                  {t("reportLead")}
                </p>
              </div>
            </>
          }
          meter={
            <span className="inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1.5 font-mono text-[11px] text-forest-700 backdrop-blur-sm">
              <span className="flex gap-1" aria-hidden>
                {Array.from({ length: INVESTIGATION_LIMIT }, (_, i) => (
                  <span
                    key={i}
                    className={i < left ? "size-1.5 rounded-full bg-forest-700" : "size-1.5 rounded-full bg-forest-900/15"}
                  />
                ))}
              </span>
              {left} {t(left === 1 ? "investigationLeft" : "investigationsLeft")}
            </span>
          }
          onTranscribed={onTranscribed}
          voiceNotice={
            waitingForPhoto ? (
              <p role="status" className="flex items-center justify-center gap-2 text-sm font-medium text-clay-600">
                <Camera className="size-4 shrink-0" aria-hidden />
                {t("voiceNeedPhoto")}
              </p>
            ) : null
          }
        />

        <AnimatePresence>
          {submitError ? (
            <motion.div
              role="alert"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-6 flex gap-3 rounded-2xl border border-destructive/25 bg-destructive/5 p-4 text-sm"
            >
              <AlertCircle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden />
              <div>
                <p className="font-medium text-destructive">{ERROR_TITLES[submitError.kind]}</p>
                <p className="mt-0.5 text-forest-900/80">{submitError.message}</p>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        {/* Inline on desktop; a thumb-reachable bar on phones. */}
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-forest-900/10 bg-background/80 backdrop-blur-xl lg:static lg:mt-8 lg:border-0 lg:bg-transparent lg:backdrop-blur-none">
          <div className="mx-auto flex max-w-6xl items-center justify-end gap-6 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 lg:px-0 lg:py-0">
            <p className="hidden text-sm text-muted-foreground lg:block">{t("reportReady")}</p>
            <button
              type="submit"
              disabled={formState.isSubmitting}
              className={pillClass("dark", "w-full justify-between sm:w-auto lg:h-16 lg:pl-8 lg:text-lg")}
            >
              {t("getTriage")}
              <PillIcon>
                {formState.isSubmitting ? <Spinner className="size-4" /> : <Sparkles className="size-4" />}
              </PillIcon>
            </button>
          </div>
        </div>
      </form>
    </FormProvider>
  );
}
