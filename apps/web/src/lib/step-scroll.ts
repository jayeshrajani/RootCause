const STACKED_LAYOUT = "(max-width: 1023px)";

/** On the stacked (phone/tablet) report layout, glide to the next section after a choice. */
export function scrollToStep(id: string, delay = 350): void {
  if (!window.matchMedia(STACKED_LAYOUT).matches) return;
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.setTimeout(() => {
    document.getElementById(id)?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  }, delay);
}
