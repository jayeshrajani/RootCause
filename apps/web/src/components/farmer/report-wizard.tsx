"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FormProvider, useForm, useFormContext, useWatch, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, Camera, Check, Sparkles } from "lucide-react";

import { BotanicalPattern } from "@/components/brand/botanical";
import { pillClass, PillIcon } from "@/components/brand/pill";
import { AnalysingOverlay } from "@/components/farmer/analysing-overlay";
import { CROP_KEYS } from "@/components/farmer/crop-picker";
import { CropStep } from "@/components/farmer/steps/crop-step";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, submitTriageReport } from "@/lib/api/client";
import { MAX_IMAGES } from "@/lib/constants";
import { rememberReport } from "@/lib/last-report";
import { objectUrlFor } from "@/lib/object-urls";
import {
  reportFormDefaults,
  reportFormSchema,
  type ReportFormInput,
  type ReportFormValues,
} from "@/lib/schemas/report";
import { saveLatestTriage } from "@/lib/triage-storage";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type FieldName = FieldPath<ReportFormInput>;

const FIELDS = new Set<string>(Object.keys(reportFormDefaults));

function ReportProgress() {
  const { t } = useI18n();
  const { control } = useFormContext<ReportFormInput>();
  const [crop, images, description, duration] = useWatch({
    control,
    name: ["crop", "images", "description", "symptom_duration"],
  });
  const hasDetails = Boolean(description.trim() || duration);
  const steps = [
    { label: t("progressCrop"), value: crop ? t(CROP_KEYS[crop]) : t("cropFromPhoto"), done: Boolean(crop) },
    { label: t("progressPhotos"), value: `${images.length}/${MAX_IMAGES}`, done: images.length > 0 },
    { label: t("progressDetails"), value: hasDetails ? t("detailsAdded") : t("optional"), done: hasDetails },
  ];

  return (
    <ol className="grid grid-cols-3 gap-1.5 rounded-2xl bg-mint-100/[0.06] p-1.5 ring-1 ring-mint-100/10 lg:w-[28rem]">
      {steps.map((step, index) => (
        <li
          key={step.label}
          className={cn(
            "min-w-0 rounded-xl px-3 py-2.5 transition-colors duration-500",
            step.done && "bg-mint-100/[0.08]",
          )}
        >
          <span className="flex items-center gap-2">
            <span
              className={cn(
                "flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold transition-colors duration-300",
                step.done ? "bg-mint-300 text-forest-900" : "text-mint-100/70 ring-1 ring-mint-100/30",
              )}
              aria-hidden
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={step.done ? "done" : "todo"}
                  initial={{ scale: 0.4, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.4, opacity: 0 }}
                  transition={{ type: "spring", stiffness: 500, damping: 26 }}
                >
                  {step.done ? <Check className="size-3" strokeWidth={3.5} /> : index + 1}
                </motion.span>
              </AnimatePresence>
            </span>
            <span className="truncate text-xs text-mint-200/70">{step.label}</span>
          </span>
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={step.value}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
              className="mt-1 block truncate text-sm font-medium text-mint-100 sm:text-base"
            >
              {step.value}
            </motion.span>
          </AnimatePresence>
        </li>
      ))}
    </ol>
  );
}

function ReadySummary() {
  const { t } = useI18n();
  const { control } = useFormContext<ReportFormInput>();
  const [images, crop, place] = useWatch({ control, name: ["images", "crop", "location_label"] });

  if (!images.length) {
    return (
      <p className="hidden min-w-0 flex-1 items-center gap-2 text-sm text-muted-foreground sm:flex">
        <Camera className="size-4 shrink-0" aria-hidden />
        <span className="truncate">{t("notEnough")}</span>
      </p>
    );
  }
  return (
    <div className="hidden min-w-0 flex-1 items-center gap-3 sm:flex">
      <span className="flex shrink-0 -space-x-2.5">
        {images.map((file) => (
          // eslint-disable-next-line @next/next/no-img-element -- local blob preview
          <img
            key={objectUrlFor(file)}
            src={objectUrlFor(file)}
            alt=""
            className="size-9 rounded-full object-cover ring-2 ring-background"
          />
        ))}
      </span>
      <span className="min-w-0 truncate text-sm">
        <span className="font-medium">{crop ? t(CROP_KEYS[crop]) : t("cropFromPhoto")}</span>
        {place.trim() ? <span className="text-muted-foreground">, {place.trim()}</span> : null}
      </span>
    </div>
  );
}

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
        className="mx-auto w-full max-w-6xl px-4 pt-5 pb-32 sm:px-6 sm:pt-8 lg:px-8"
      >
        <header className="relative mb-9 overflow-hidden rounded-[28px] bg-forest-900 text-mint-100 sm:mb-12">
          <BotanicalPattern className="text-mint-300/[0.07]" />
          <div className="absolute -top-24 -right-16 size-80 rounded-full bg-[radial-gradient(circle,rgba(182,224,196,0.22),transparent_65%)]" aria-hidden />
          <div className="relative grid gap-6 p-5 sm:p-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end lg:gap-10 lg:p-10">
            <div className="max-w-xl">
              <h1 className="text-[2rem] leading-[1.05] font-medium tracking-tight sm:text-[2.75rem]">{t("reportTitle")}</h1>
              <p className="mt-3 max-w-[46ch] text-sm leading-relaxed text-mint-100/75 sm:text-base">
                {t("reportSubtitle")}
              </p>
            </div>
            <ReportProgress />
          </div>
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

        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-forest-900/10 bg-background/85 backdrop-blur-xl">
          <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 lg:px-8">
            <ReadySummary />
            <button
              type="submit"
              disabled={formState.isSubmitting}
              className={pillClass("dark", "w-full shrink-0 justify-between active:scale-[0.98] sm:ml-auto sm:w-auto")}
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
