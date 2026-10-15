"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FormProvider, useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, Sparkles } from "lucide-react";

import { pillClass, PillIcon } from "@/components/brand/pill";
import { AnalysingOverlay } from "@/components/farmer/analysing-overlay";
import { CropStep } from "@/components/farmer/steps/crop-step";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, submitTriageReport } from "@/lib/api/client";
import { rememberReport } from "@/lib/last-report";
import {
  reportFormDefaults,
  reportFormSchema,
  type ReportFormInput,
  type ReportFormValues,
} from "@/lib/schemas/report";
import { saveLatestTriage } from "@/lib/triage-storage";
import { useI18n } from "@/lib/i18n";

type FieldName = FieldPath<ReportFormInput>;

const FIELDS = new Set<string>(Object.keys(reportFormDefaults));

export function ReportWizard() {
  const router = useRouter();
  const { language, t } = useI18n();
  const [submitError, setSubmitError] = useState<ApiError | null>(null);

  const form = useForm<ReportFormInput, unknown, ReportFormValues>({
    resolver: zodResolver(reportFormSchema),
    defaultValues: reportFormDefaults,
    mode: "onTouched",
  });
  const { handleSubmit, setError, getValues, formState } = form;

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      const result = await submitTriageReport(values, language);
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
        {formState.isSubmitting ? <AnalysingOverlay photo={getValues("images")[0]} /> : null}
      </AnimatePresence>

      <form
        onSubmit={(e) => void submit(e)}
        noValidate
        className="mx-auto w-full max-w-6xl px-4 pt-5 pb-28 sm:px-6 sm:pt-8 lg:px-8"
      >
        <header className="relative mb-7 overflow-hidden rounded-[24px] bg-forest-900 px-5 py-6 text-mint-100 sm:mb-9 sm:px-8 sm:py-8">
          <div className="absolute inset-y-0 right-0 hidden w-[38%] bg-[radial-gradient(ellipse_at_80%_30%,rgba(182,224,196,0.16),transparent_65%)] sm:block" aria-hidden />
          <div className="relative max-w-2xl">
            <p className="label-caps text-mint-300/70">{t("reportEyebrow")}</p>
            <h1 className="mt-3 text-3xl leading-tight font-medium sm:text-4xl">{t("reportTitle")}</h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-mint-100/75 sm:text-base">
              {t("reportSubtitle")}
            </p>
          </div>
          <ol className="relative mt-6 grid grid-cols-3 gap-2 border-t border-mint-100/15 pt-4 sm:max-w-xl sm:gap-4">
            {[t("chooseCrop"), t("addPhoto"), t("tellUs")].map((step, index) => (
              <li key={step} className="flex min-w-0 flex-col items-start gap-2 text-xs leading-tight text-mint-100/85 sm:flex-row sm:items-center sm:text-sm">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-mint-300 text-xs font-semibold text-forest-900">
                  {index + 1}
                </span>
                <span className="line-clamp-2 whitespace-normal">{step}</span>
              </li>
            ))}
          </ol>
        </header>

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
                <p className="font-medium text-destructive">{submitError.kind === "validation" ? t("notEnough") : t("reportError")}</p>
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
