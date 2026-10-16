"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FormProvider, useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, Sparkles } from "lucide-react";

import { pillClass, PillIcon } from "@/components/brand/pill";
import { AnalysingOverlay } from "@/components/farmer/analysing-overlay";
import { CropConfirm } from "@/components/farmer/crop-confirm";
import { CropStep } from "@/components/farmer/steps/crop-step";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, identifyCrop, submitTriageReport } from "@/lib/api/client";
import { rememberReport } from "@/lib/last-report";
import {
  reportFormDefaults,
  reportFormSchema,
  type ReportFormInput,
  type ReportFormValues,
} from "@/lib/schemas/report";
import { saveLatestTriage } from "@/lib/triage-storage";
import type { Crop } from "@/types/triage";

type FieldName = FieldPath<ReportFormInput>;

const FIELDS = new Set<string>(Object.keys(reportFormDefaults));

const ERROR_TITLES: Record<ApiError["kind"], string> = {
  network: "Couldn't reach RootCause",
  timeout: "The analysis took too long",
  validation: "Please check your report",
  server: "Analysis didn't finish",
};

export function ReportWizard() {
  const router = useRouter();
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
  const { handleSubmit, setError, getValues, formState } = form;

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
      for (const { field, message } of apiError.fieldErrors) {
        if (FIELDS.has(field)) setError(field as FieldName, { type: "server", message });
      }
      setSubmitError(apiError);
    }
  });

  return (
    <FormProvider {...form}>
      <AnimatePresence>
        {formState.isSubmitting && cropQuestion === null ? (
          <AnalysingOverlay key={phase} photo={getValues("images")[0]} phase={phase} />
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
        className="mx-auto w-full max-w-6xl px-4 pt-6 pb-28 sm:px-6 sm:pt-8 lg:px-8"
      >
        <h1 className="text-3xl leading-tight font-medium sm:text-4xl">Report a crop problem</h1>
        <p className="mt-2 mb-6 text-muted-foreground sm:mb-8 sm:text-lg">
          Choose the crop and add a photo. Everything else is optional.
        </p>

        <CropStep />

        <AnimatePresence>
          {submitError ? (
            <motion.div
              role="alert"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-8 flex gap-3 rounded-2xl border border-destructive/25 bg-destructive/5 p-4 text-sm"
            >
              <AlertCircle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden />
              <div>
                <p className="font-medium text-destructive">{ERROR_TITLES[submitError.kind]}</p>
                <p className="mt-0.5 text-forest-900/80">{submitError.message}</p>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-forest-900/10 bg-background/80 backdrop-blur-xl">
          <div className="mx-auto flex max-w-6xl justify-end px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 lg:px-8">
            <button
              type="submit"
              disabled={formState.isSubmitting}
              className={pillClass("dark", "w-full justify-between sm:w-auto")}
            >
              Get triage
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
