"use client";

import { useCallback } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { AnimatePresence, motion } from "motion/react";
import { Check, LocateFixed } from "lucide-react";

import { TextField } from "@/components/forms/text-field";
import { Spinner } from "@/components/ui/spinner";
import { useApproximateLocation } from "@/hooks/use-approximate-location";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";

export function LocationStep() {
  const { register, control, setValue, formState } = useFormContext<ReportFormInput>();
  const [latitude, longitude] = useWatch({ control, name: ["latitude", "longitude"] });
  const errors = formState.errors;

  const onLocated = useCallback(
    (coords: { latitude: string; longitude: string }) => {
      setValue("latitude", coords.latitude, { shouldValidate: true, shouldDirty: true });
      setValue("longitude", coords.longitude, { shouldValidate: true, shouldDirty: true });
    },
    [setValue],
  );
  const { state, locate } = useApproximateLocation(onLocated);
  const hasCoords = Boolean(latitude && longitude && !errors.latitude && !errors.longitude);

  return (
    <div className="space-y-8">
      <motion.button
        type="button"
        onClick={locate}
        disabled={state.status === "locating"}
        whileTap={{ scale: 0.98 }}
        className={cn(
          "flex w-full items-center gap-4 rounded-3xl border p-5 text-left transition-colors duration-300",
          hasCoords
            ? "border-forest-900 bg-forest-900 text-mint-100"
            : "border-forest-900/15 bg-white/70 hover:border-forest-900/40 hover:bg-white",
        )}
      >
        <span
          className={cn(
            "flex size-12 shrink-0 items-center justify-center rounded-full",
            hasCoords ? "bg-mint-300 text-forest-900" : "bg-forest-900 text-mint-100",
          )}
        >
          {state.status === "locating" ? (
            <Spinner className="size-5" />
          ) : hasCoords ? (
            <Check className="size-5" />
          ) : (
            <LocateFixed className="size-5" />
          )}
        </span>
        <span className="flex-1">
          <span className="block text-lg font-medium">
            {state.status === "locating"
              ? "Finding your location…"
              : hasCoords
                ? "Location added"
                : "Use my current location"}
          </span>
          <span className={cn("block text-sm", hasCoords ? "text-mint-200/80" : "text-muted-foreground")}>
            {hasCoords
              ? `${latitude}, ${longitude} · tap to refresh`
              : "Rounded to about 1 km. Your exact farm isn't needed."}
          </span>
        </span>
      </motion.button>

      <AnimatePresence>
        {state.status === "error" ? (
          <motion.p
            role="status"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="-mt-4 text-sm text-destructive"
          >
            {state.message}
          </motion.p>
        ) : null}
      </AnimatePresence>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or enter it yourself
        <span className="h-px flex-1 bg-border" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Latitude"
          placeholder="e.g. 18.52"
          autoComplete="off"
          error={errors.latitude?.message}
          {...register("latitude")}
        />
        <TextField
          label="Longitude"
          placeholder="e.g. 73.86"
          autoComplete="off"
          error={errors.longitude?.message}
          {...register("longitude")}
        />
      </div>
      <TextField
        label={
          <>
            Village or district <span className="font-normal text-muted-foreground">Optional</span>
          </>
        }
        placeholder="e.g. Near Baramati, Pune"
        autoComplete="address-level2"
        error={errors.location_label?.message}
        {...register("location_label")}
      />
    </div>
  );
}
