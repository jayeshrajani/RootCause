"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { AlertTriangle, ExternalLink, FlaskConical, LocateFixed, MapPin, ShieldCheck, Sprout, Store } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { fetchAgriShops, fetchTreatment } from "@/lib/api/client";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { ActiveIngredient, Shop, TreatmentPlan, TriageResponse } from "@/types/triage";

const EASE = [0.16, 1, 0.3, 1] as const;

// Cached per result and language so switching tabs never refetches.
const plans = new Map<string, Promise<TreatmentPlan>>();
const shopLists = new Map<string, Promise<Shop[]>>();

function cached<T>(store: Map<string, Promise<T>>, key: string, load: () => Promise<T>): Promise<T> {
  let value = store.get(key);
  if (!value) {
    value = load();
    value.catch(() => store.delete(key));
    store.set(key, value);
  }
  return value;
}

const KIND_KEYS: Record<ActiveIngredient["kind"], TranslationKey> = {
  fungicide: "kindFungicide",
  insecticide: "kindInsecticide",
  bactericide: "kindBactericide",
  biological: "kindBiological",
  nutrient: "kindNutrient",
  other: "kindOther",
};

/** "18.52° N, 73.86° E" (as shown on results) back to coordinates. */
export function parseApproximateLocation(text: string | null | undefined) {
  const match = text?.match(/([\d.]+)°\s*([NS]),\s*([\d.]+)°\s*([EW])/);
  if (!match) return null;
  const latitude = Number(match[1]) * (match[2] === "S" ? -1 : 1);
  const longitude = Number(match[3]) * (match[4] === "W" ? -1 : 1);
  return Number.isFinite(latitude) && Number.isFinite(longitude) ? { latitude, longitude } : null;
}

type Load<T> = { state: "loading" } | { state: "ready"; value: T } | { state: "error" };

function Heading({ icon: Icon, children }: { icon: typeof Sprout; children: React.ReactNode }) {
  return (
    <h3 className="label-caps flex items-center gap-1.5 text-forest-600">
      <Icon className="size-3.5" aria-hidden />
      {children}
    </h3>
  );
}

function Shops({ result }: { result: TriageResponse }) {
  const { t } = useI18n();
  const known = parseApproximateLocation(result.approximate_location);
  const [where, setWhere] = useState<{ latitude: number; longitude: number } | { place: string } | null>(
    known ?? (result.location_label ? { place: result.location_label } : null),
  );
  const [shops, setShops] = useState<Load<Shop[]> | null>(null);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    if (!where) return;
    let live = true;
    const key = "place" in where ? where.place : `${where.latitude.toFixed(2)},${where.longitude.toFixed(2)}`;
    cached(shopLists, key, () => fetchAgriShops(where))
      .then((value) => live && setShops({ state: "ready", value }))
      .catch(() => live && setShops({ state: "error" }));
    return () => {
      live = false;
    };
  }, [where]);

  const locate = () => {
    if (!("geolocation" in navigator)) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false);
        setShops(null);
        setWhere({ latitude: coords.latitude, longitude: coords.longitude });
      },
      () => setLocating(false),
      { enableHighAccuracy: false, timeout: 15_000, maximumAge: 10 * 60_000 },
    );
  };

  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <Heading icon={Store}>{t("treatShops")}</Heading>
        <span className="font-mono text-[10px] text-muted-foreground">Google Maps · Gemini</span>
      </div>

      {!where ? (
        <button
          type="button"
          onClick={locate}
          disabled={locating}
          className="flex w-full items-center gap-3 rounded-2xl border border-dashed border-forest-900/20 bg-white/60 p-4 text-left transition-colors hover:border-forest-900/40"
        >
          <span className="flex size-10 items-center justify-center rounded-full bg-forest-900 text-mint-100">
            {locating ? <Spinner className="size-4" /> : <LocateFixed className="size-4" aria-hidden />}
          </span>
          <span>
            <span className="block font-medium">{t("treatShopsLocate")}</span>
            <span className="block text-sm text-muted-foreground">{t("treatShopsLocateHint")}</span>
          </span>
        </button>
      ) : !shops ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
      ) : shops.state === "error" ? (
        <p className="rounded-2xl bg-destructive/5 p-4 text-sm text-destructive">{t("treatShopsError")}</p>
      ) : shops.state === "ready" && shops.value.length === 0 ? (
        <p className="rounded-2xl bg-mint-100/60 p-4 text-sm">{t("treatShopsNone")}</p>
      ) : shops.state === "ready" ? (
        <ul className="grid gap-2 sm:grid-cols-2">
          {shops.value.map((shop, i) => (
            <motion.li
              key={shop.place_id ?? shop.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.06, ease: EASE }}
              className="flex flex-col rounded-2xl border border-forest-900/10 bg-white/80 p-4"
            >
              <p className="font-medium leading-snug">{shop.name}</p>
              {shop.address ? (
                <p className="mt-1 flex gap-1.5 text-xs leading-relaxed text-muted-foreground">
                  <MapPin className="mt-0.5 size-3 shrink-0" aria-hidden />
                  {shop.address}
                </p>
              ) : null}
              {shop.offers ? <p className="mt-1.5 text-xs text-forest-700">{shop.offers}</p> : null}
              {shop.maps_uri ? (
                <a
                  href={shop.maps_uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-full bg-forest-900 px-3 py-1.5 text-xs font-medium text-mint-100 transition-colors hover:bg-forest-700"
                >
                  {t("treatOpenMaps")}
                  <ExternalLink className="size-3" aria-hidden />
                </a>
              ) : null}
            </motion.li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

/** Treatment guidance (practices first, generic ingredients, safety) and nearby agri-input shops. */
export function TreatPanel({ result }: { result: TriageResponse }) {
  const { t } = useI18n();
  const top = result.possible_causes[0];
  const crop = result.crop ?? result.detected_crop ?? "";
  const language = result.response_language ?? "en";
  const [plan, setPlan] = useState<Load<TreatmentPlan>>({ state: "loading" });

  useEffect(() => {
    if (!top) return;
    let live = true;
    const request = {
      crop: crop || "unknown crop",
      cause: top.name,
      evidence_fit_score: top.evidence_fit_score,
      response_language: language,
    };
    cached(plans, `${result.report_id}:${language}`, () => fetchTreatment(request))
      .then((value) => live && setPlan({ state: "ready", value }))
      .catch(() => live && setPlan({ state: "error" }));
    return () => {
      live = false;
    };
  }, [crop, language, result.report_id, top]);

  if (!top) return <p className="text-sm text-muted-foreground">{t("treatNoCause")}</p>;

  return (
    <div className="space-y-6">
      {plan.state === "loading" ? (
        <div className="space-y-3">
          <Skeleton className="h-16 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
        </div>
      ) : plan.state === "error" ? (
        <p className="rounded-2xl bg-destructive/5 p-4 text-sm text-destructive">{t("treatError")}</p>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE }}
          className="space-y-6"
        >
          {plan.value.confirm_first ? (
            <div className="flex gap-3 rounded-2xl border border-clay-400/40 bg-clay-400/10 p-4 text-sm">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-clay-600" aria-hidden />
              <p>
                <span className="font-medium text-clay-600">{t("treatConfirmTitle")}</span> {t("treatConfirmBody")}
              </p>
            </div>
          ) : null}

          <section className="space-y-3">
            <Heading icon={Sprout}>{t("treatNonChemical")}</Heading>
            <ol className="space-y-2">
              {plan.value.non_chemical_steps.map((step, i) => (
                <li key={step} className="flex gap-3 rounded-2xl bg-white/70 p-3 text-sm leading-relaxed">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-mint-100 font-mono text-xs text-forest-700">
                    {i + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </section>

          {plan.value.active_ingredients.length ? (
            <section className="space-y-3">
              <Heading icon={FlaskConical}>{t("treatIngredients")}</Heading>
              <ul className={cn("grid gap-2", plan.value.active_ingredients.length > 1 && "sm:grid-cols-2")}>
                {plan.value.active_ingredients.map((item) => (
                  <li key={item.name} className="rounded-2xl border border-forest-900/10 bg-white/80 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium capitalize">{item.name}</p>
                      <span className="rounded-full bg-mint-100 px-2 py-0.5 text-[11px] text-forest-700">
                        {t(KIND_KEYS[item.kind])}
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{item.note}</p>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">{t("treatLabelNote")}</p>
            </section>
          ) : null}

          <section className="space-y-3">
            <Heading icon={ShieldCheck}>{t("treatSafety")}</Heading>
            <ul className="space-y-1.5 text-sm">
              {plan.value.safety.map((point) => (
                <li key={point} className="flex gap-2.5 leading-relaxed">
                  <span className="mt-[9px] size-1 shrink-0 rounded-full bg-forest-700" aria-hidden />
                  {point}
                </li>
              ))}
            </ul>
            <p className="rounded-2xl bg-forest-900 p-4 text-sm leading-relaxed text-mint-100">{plan.value.expert_note}</p>
          </section>
        </motion.div>
      )}

      <Shops result={result} />
    </div>
  );
}
