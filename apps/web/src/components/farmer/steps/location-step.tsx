"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { AnimatePresence, motion } from "motion/react";
import { Check, LocateFixed, MapPin } from "lucide-react";

import { FieldMessage, TextField } from "@/components/forms/text-field";
import { Spinner } from "@/components/ui/spinner";
import { useApproximateLocation } from "@/hooks/use-approximate-location";
import { searchLocations } from "@/lib/api/client";
import type { ReportFormInput } from "@/lib/schemas/report";
import type { LocationOption } from "@/types/location";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export function useFieldLocation() {
  const { control, setValue, getValues, formState } = useFormContext<ReportFormInput>();
  const [latitude, longitude, label] = useWatch({
    control,
    name: ["latitude", "longitude", "location_label"],
  });
  const pending = useRef(false);
  const asked = useRef(false);

  const onLocated = useCallback(
    (coords: { latitude: string; longitude: string }) => {
      // Ignore a late fix if the farmer has typed a place in the meantime.
      if (!pending.current) return;
      pending.current = false;
      setValue("location_label", "", { shouldValidate: true, shouldDirty: true });
      setValue("latitude", coords.latitude, { shouldDirty: true });
      setValue("longitude", coords.longitude, { shouldValidate: true, shouldDirty: true });
    },
    [setValue],
  );
  const { state, locate } = useApproximateLocation(onLocated);

  const request = useCallback(() => {
    asked.current = true;
    pending.current = true;
    locate();
  }, [locate]);

  const requestOnce = useCallback(() => {
    const values = getValues();
    if (asked.current || values.latitude || values.location_label) return;
    request();
  }, [getValues, request]);

  const cancel = useCallback(() => {
    pending.current = false;
  }, []);

  const hasCoords = Boolean(
    latitude && longitude && !formState.errors.latitude && !formState.errors.longitude,
  );
  return { state, hasCoords, label: label.trim(), request, requestOnce, cancel };
}

export type FieldLocation = ReturnType<typeof useFieldLocation>;

export function LocationStatus({ location }: { location: FieldLocation }) {
  const { t } = useI18n();
  const { state, hasCoords, label } = location;
  let content: React.ReactNode = null;
  if (state.status === "locating") {
    content = (
      <>
        <Spinner className="size-4" /> {t("findingLocation")}
      </>
    );
  } else if (hasCoords) {
    content = (
      <>
        <Check className="size-4 text-forest-700" aria-hidden />
        {label ? `${t("locationAdded")}: ${label}` : t("locationAdded")}
      </>
    );
  } else if (label) {
    content = (
      <>
        <MapPin className="size-4 text-forest-600" aria-hidden />
        {t("confirmLocation")}
      </>
    );
  } else if (state.status === "error") {
    content = (
      <>
        <MapPin className="size-4 text-clay-600" aria-hidden />
        {t("locationUnavailable")}
      </>
    );
  }

  return (
    <p role="status" className="flex min-h-5 items-center gap-2 text-sm text-forest-900/80">
      {content}
    </p>
  );
}

export function LocationStep({ location }: { location: FieldLocation }) {
  const { t } = useI18n();
  const { register, setValue, formState } = useFormContext<ReportFormInput>();
  const errors = formState.errors;
  const { state, hasCoords } = location;
  const locationField = register("location_label");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<LocationOption[]>([]);
  const [searchStatus, setSearchStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [showMatches, setShowMatches] = useState(false);

  useEffect(() => {
    const normalizedQuery = query.trim();
    if (hasCoords || !showMatches || normalizedQuery.length < 2) return;

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void searchLocations(normalizedQuery, controller.signal)
        .then((locations) => {
          setMatches(locations);
          setSearchStatus("ready");
        })
        .catch(() => {
          if (!controller.signal.aborted) setSearchStatus("error");
        });
    }, 300);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [hasCoords, query, showMatches]);

  const selectLocation = (selected: LocationOption) => {
    const label = [selected.name, selected.admin1, selected.country].filter(Boolean).join(", ");
    setValue("location_label", label, { shouldDirty: true, shouldValidate: true });
    setValue("latitude", selected.latitude.toFixed(2), { shouldDirty: true });
    setValue("longitude", selected.longitude.toFixed(2), {
      shouldDirty: true,
      shouldValidate: true,
    });
    setQuery(label);
    setShowMatches(false);
    setMatches([]);
    location.cancel();
  };

  return (
    <div className="space-y-4">
      <motion.button
        type="button"
        onClick={() => {
          setQuery("");
          location.request();
        }}
        disabled={state.status === "locating"}
        whileTap={{ scale: 0.98 }}
        className={cn(
          "flex w-full items-center gap-4 rounded-lg border p-4 text-left transition-colors duration-300",
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
          <span className="block font-medium">
            {state.status === "locating"
              ? t("findingLocation")
              : hasCoords
                ? t("locationAdded")
                : t("useCurrentLocation")}
          </span>
          <span className={cn("block text-sm", hasCoords ? "text-mint-200/80" : "text-muted-foreground")}>
            {hasCoords ? t("refreshLocation") : t("locationPrecision")}
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
            className="text-sm text-destructive"
          >
            {t("locationPermission")}
          </motion.p>
        ) : null}
      </AnimatePresence>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        {t("enterAnotherLocation")}
        <span className="h-px flex-1 bg-border" />
      </div>

      <TextField
        label={t("villageDistrict")}
        placeholder={t("searchPlace")}
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showMatches && matches.length > 0}
        aria-controls="location-options"
        error={errors.location_label?.message}
        {...locationField}
        value={query}
        onFocus={() => setShowMatches(true)}
        onChange={(event) => {
          void locationField.onChange(event);
          setQuery(event.target.value);
          setShowMatches(true);
          setMatches([]);
          setSearchStatus(event.target.value.trim().length >= 2 ? "loading" : "idle");
          location.cancel();
          setValue("latitude", "", { shouldDirty: true });
          setValue("longitude", "", { shouldValidate: true, shouldDirty: true });
        }}
      />
      {showMatches && query.trim().length >= 2 ? (
        <div className="overflow-hidden rounded-xl border border-forest-900/15 bg-white shadow-lg shadow-forest-900/10">
          {searchStatus === "loading" ? (
            <p role="status" className="px-4 py-3 text-sm text-muted-foreground">
              {t("findingPlaces")}
            </p>
          ) : searchStatus === "error" ? (
            <p role="status" className="px-4 py-3 text-sm text-muted-foreground">
              {t("placeSearchUnavailable")}
            </p>
          ) : matches.length ? (
            <ul id="location-options" role="listbox" aria-label="Matching locations">
              {matches.map((match) => (
                <li key={`${match.latitude},${match.longitude}`} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectLocation(match)}
                    className="flex w-full items-center justify-between gap-4 border-b border-forest-900/5 px-4 py-3 text-left last:border-0 hover:bg-mint-50 focus-visible:bg-mint-50 focus-visible:outline-none"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-forest-900">{match.name}</span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {[match.admin1, match.country].filter(Boolean).join(", ")}
                      </span>
                    </span>
                    <MapPin className="size-4 shrink-0 text-forest-600" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          ) : searchStatus === "ready" ? (
            <p role="status" className="px-4 py-3 text-sm text-muted-foreground">
              {t("noPlaceMatch")}
            </p>
          ) : null}
        </div>
      ) : null}
      <FieldMessage id="location-error" message={errors.latitude?.message ?? errors.longitude?.message} />
    </div>
  );
}
