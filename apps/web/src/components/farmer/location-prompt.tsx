"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { LocateFixed } from "lucide-react";

import type { FieldLocation } from "@/components/farmer/steps/location-step";
import { useI18n } from "@/lib/i18n";

const ASKED_KEY = "rootcause:location-asked";

async function permissionState(): Promise<PermissionState | "unknown"> {
  try {
    const status = await navigator.permissions?.query({ name: "geolocation" });
    return status?.state ?? "unknown";
  } catch {
    return "unknown";
  }
}

/** Asks for location once per visit with our own explanation first, so the browser's prompt
 * only appears after the farmer chooses to share. Already granted: locate silently. */
export function LocationPrompt({ location }: { location: FieldLocation }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const shareButton = useRef<HTMLButtonElement>(null);
  const { hasCoords, requestOnce } = location;

  // Focus without scrolling the report underneath (autoFocus would jump the page on phones).
  useEffect(() => {
    if (open) shareButton.current?.focus({ preventScroll: true });
  }, [open]);

  useEffect(() => {
    if (hasCoords || sessionStorage.getItem(ASKED_KEY) || !("geolocation" in navigator)) return;
    let cancelled = false;
    void permissionState().then((state) => {
      if (cancelled || state === "denied") return;
      if (state === "granted") requestOnce();
      else setOpen(true);
    });
    return () => {
      cancelled = true;
    };
    // Only on arrival; later changes are handled by the location controls.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const close = (share: boolean) => {
    sessionStorage.setItem(ASKED_KEY, "1");
    setOpen(false);
    if (share) requestOnce();
  };

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="location-prompt-title"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-end justify-center bg-forest-900/60 p-4 backdrop-blur-sm sm:items-center"
        >
          <motion.div
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 32, opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="w-full max-w-md rounded-[28px] bg-background p-6 shadow-2xl"
          >
            <div className="relative mb-5 flex size-14 items-center justify-center rounded-full bg-forest-900 text-mint-100">
              <motion.span
                aria-hidden
                className="absolute inset-0 rounded-full border-2 border-forest-900"
                animate={{ scale: [1, 1.6], opacity: [0.5, 0] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
              />
              <LocateFixed className="size-6" aria-hidden />
            </div>
            <h2 id="location-prompt-title" className="text-2xl font-medium tracking-tight">
              {t("locTitle")}
            </h2>
            <p className="mt-2 leading-relaxed text-muted-foreground">{t("locBody")}</p>
            <div className="mt-6 flex flex-col gap-2 sm:flex-row-reverse">
              <button
                ref={shareButton}
                type="button"
                onClick={() => close(true)}
                className="inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-full bg-forest-900 px-5 font-medium text-mint-100 transition-colors hover:bg-forest-700"
              >
                <LocateFixed className="size-4" aria-hidden />
                {t("locAllow")}
              </button>
              <button
                type="button"
                onClick={() => close(false)}
                className="inline-flex min-h-12 items-center justify-center rounded-full px-5 text-sm text-muted-foreground hover:text-foreground"
              >
                {t("locLater")}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
