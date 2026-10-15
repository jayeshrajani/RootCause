import type { ReportFormInput } from "@/lib/schemas/report";

const STACKED_LAYOUT = "(max-width: 1023px)";

/** The next report section still worth the farmer's attention after finishing `after`. */
export function nextStepId(values: ReportFormInput, after: "crop" | "photo" | "location"): string {
  if (after === "crop" && values.images.length === 0) return "step-2";
  if (after !== "location" && !(values.latitude && values.longitude)) return "step-location";
  return "step-3";
}

/** On the stacked (phone/tablet) report layout, glide to the next section after a choice. */
export function scrollToStep(id: string, delay = 350): void {
  if (!window.matchMedia(STACKED_LAYOUT).matches) return;
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.setTimeout(() => {
    document.getElementById(id)?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  }, delay);
}
