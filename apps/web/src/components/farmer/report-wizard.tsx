"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FormProvider, useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, ArrowLeft, ArrowRight, Send } from "lucide-react";

import { pillClass, PillIcon } from "@/components/brand/pill";
import { CropStep } from "@/components/farmer/steps/crop-step";
import { LocationStep } from "@/components/farmer/steps/location-step";
import { PhotoStep } from "@/components/farmer/steps/photo-step";
import { ReviewStep } from "@/components/farmer/steps/review-step";
import { SymptomsStep } from "@/components/farmer/steps/symptoms-step";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, submitTriageReport } from "@/lib/api/client";
import {
  reportFormDefaults,
  reportFormSchema,
  type ReportFormInput,
  type ReportFormValues,
} from "@/lib/schemas/report";
import { saveLatestTriage } from "@/lib/triage-storage";
import { cn } from "@/lib/utils";

type FieldName = FieldPath<ReportFormInput>;

const STEPS: { label: string; title: string; help: string; fields: FieldName[] }[] = [
  {
    label: "Crop",
    title: "Which crop is affected?",
    help: "Pick the closest match.",
    fields: ["crop"],
  },
  {
    label: "Photos",
    title: "Show us the problem.",
    help: "One to three clear close-ups. A healthy leaf next to a sick one helps a lot.",
    fields: ["images"],
  },
  {
    label: "Symptoms",
    title: "What do you see?",
    help: "Tap what matches, then add anything else in your own words.",
    fields: ["description", "symptom_duration"],
  },
  {
    label: "Location",
    title: "Roughly where is the field?",
    help: "Used for local weather and satellite context. About 1 km is close enough.",
    fields: ["latitude", "longitude", "location_label"],
  },
  {
    label: "Review",
    title: "Ready to send?",
    help: "Check your report. You can change anything before sending.",
    fields: [],
  },
];

const ERROR_TITLES: Record<ApiError["kind"], string> = {
  network: "Couldn't reach RootCause",
  timeout: "The request timed out",
  validation: "Please check your report",
  server: "Something went wrong",
};

const slide = {
  enter: (dir: number) => ({ opacity: 0, x: dir * 40, filter: "blur(4px)" }),
  center: { opacity: 1, x: 0, filter: "blur(0px)" },
  exit: (dir: number) => ({ opacity: 0, x: dir * -40, filter: "blur(4px)" }),
};

export function ReportWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [reached, setReached] = useState(0);
  const [direction, setDirection] = useState(1);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);

  const form = useForm<ReportFormInput, unknown, ReportFormValues>({
    resolver: zodResolver(reportFormSchema),
    defaultValues: reportFormDefaults,
    mode: "onTouched",
  });
  const { trigger, handleSubmit, setError, formState } = form;
  const isLast = step === STEPS.length - 1;
  const current = STEPS[step]!;

  const goTo = (next: number) => {
    setDirection(next > step ? 1 : -1);
    setStep(next);
    setReached((r) => Math.max(r, next));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      const result = await submitTriageReport(values);
      saveLatestTriage(result);
      router.push("/results");
    } catch (error) {
      const apiError =
        error instanceof ApiError
          ? error
          : new ApiError("server", "Something unexpected went wrong. Please try again.");
      let firstStep = -1;
      for (const { field, message } of apiError.fieldErrors) {
        const index = STEPS.findIndex((s) => s.fields.includes(field as FieldName));
        if (index >= 0) {
          setError(field as FieldName, { type: "server", message });
          if (firstStep < 0 || index < firstStep) firstStep = index;
        }
      }
      setSubmitError(apiError);
      if (firstStep >= 0) goTo(firstStep);
    }
  }, (errors) => {
    const index = STEPS.findIndex((s) => s.fields.some((f) => f in errors));
    if (index >= 0) goTo(index);
  });

  const next = async () => {
    if (isLast) return submit();
    if (await trigger(current.fields, { shouldFocus: true })) goTo(step + 1);
  };

  return (
    <FormProvider {...form}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void next();
        }}
        noValidate
        className="mx-auto w-full max-w-2xl px-5 pt-8 pb-36 sm:pt-12"
      >
        <nav aria-label="Report progress" className="mb-10">
          <div className="mb-3 flex items-baseline justify-between">
            <p className="label-caps text-forest-600">
              Step {String(step + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}
            </p>
            <p className="label-caps text-forest-900/50">{current.label}</p>
          </div>
          <ol className="grid grid-cols-5 gap-1.5">
            {STEPS.map((s, i) => (
              <li key={s.label}>
                <button
                  type="button"
                  disabled={i > reached || formState.isSubmitting}
                  onClick={() => goTo(i)}
                  aria-label={`${s.label}${i === step ? " (current)" : ""}`}
                  aria-current={i === step ? "step" : undefined}
                  className="block h-6 w-full cursor-pointer disabled:cursor-default"
                >
                  <span className="relative block h-1 overflow-hidden rounded-full bg-forest-900/10">
                    <motion.span
                      className="absolute inset-y-0 left-0 rounded-full bg-forest-900"
                      initial={false}
                      animate={{ width: i < step ? "100%" : i === step ? "50%" : "0%" }}
                      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <AnimatePresence mode="wait" custom={direction} initial={false}>
          <motion.section
            key={step}
            custom={direction}
            variants={slide}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            aria-labelledby="step-title"
          >
            <h1
              id="step-title"
              className="text-[clamp(2rem,6vw,3.25rem)] leading-[1.02] font-medium tracking-[-0.035em]"
            >
              {current.title}
            </h1>
            <p className="mt-3 mb-8 max-w-lg text-muted-foreground sm:text-lg">{current.help}</p>

            {step === 0 ? <CropStep /> : null}
            {step === 1 ? <PhotoStep /> : null}
            {step === 2 ? <SymptomsStep /> : null}
            {step === 3 ? <LocationStep /> : null}
            {step === 4 ? <ReviewStep goTo={goTo} /> : null}
          </motion.section>
        </AnimatePresence>

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
          <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 px-5 py-3.5 pb-[max(0.875rem,env(safe-area-inset-bottom))]">
            <button
              type="button"
              onClick={() => goTo(step - 1)}
              disabled={step === 0 || formState.isSubmitting}
              className={cn(
                "inline-flex h-12 items-center gap-2 rounded-full px-4 text-[15px] font-medium transition-[opacity,background-color] hover:bg-forest-900/5",
                step === 0 && "pointer-events-none opacity-0",
              )}
            >
              <ArrowLeft className="size-4" aria-hidden />
              Back
            </button>
            <button type="submit" disabled={formState.isSubmitting} className={pillClass("dark")}>
              {isLast ? (formState.isSubmitting ? "Sending…" : "Get triage") : "Continue"}
              <PillIcon>
                {formState.isSubmitting ? (
                  <Spinner className="size-4" />
                ) : isLast ? (
                  <Send className="size-4" />
                ) : (
                  <ArrowRight className="size-4" />
                )}
              </PillIcon>
            </button>
          </div>
        </div>
      </form>
    </FormProvider>
  );
}
