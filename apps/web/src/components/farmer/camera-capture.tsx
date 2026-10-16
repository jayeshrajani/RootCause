"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";
import { Camera, ImagePlus, Leaf, Maximize, SunMedium, X, type LucideIcon } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";
import { useI18n, type TranslationKey } from "@/lib/i18n";

const TIPS: { icon: LucideIcon; key: TranslationKey }[] = [
  { icon: SunMedium, key: "daylight" },
  { icon: Maximize, key: "fillFrame" },
  { icon: Leaf, key: "includeHealthy" },
];

export function CameraCapture({
  onCapture,
  onClose,
  onChooseFiles,
}: {
  onCapture: (file: File) => void;
  onClose: () => void;
  onChooseFiles: () => void;
}) {
  const { t } = useI18n();
  const video = useRef<HTMLVideoElement>(null);
  const shutter = useRef<HTMLButtonElement>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      })
      .then((s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        if (video.current) video.current.srcObject = s;
      })
      .catch((e: unknown) => {
        const name = e instanceof DOMException ? e.name : "";
        const errorKeys: Record<string, TranslationKey> = {
          NotAllowedError: "cameraBlocked",
          NotFoundError: "cameraMissing",
          NotReadableError: "cameraBusy",
        };
        setError(t(errorKeys[name] ?? "cameraFailed"));
      });
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [t]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const capture = () => {
    const el = video.current;
    if (!el || !el.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = el.videoWidth;
    canvas.height = el.videoHeight;
    canvas.getContext("2d")?.drawImage(el, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        onCapture(new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" }));
        onClose();
      },
      "image/jpeg",
      0.9,
    );
  };

  return createPortal(
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label={t("takePhotoTitle")}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col bg-forest-950 text-mint-100"
    >
      <div className="flex items-center justify-between px-4 py-3">
        <p className="font-medium">{t("takePhotoTitle")}</p>
        <button
          type="button"
          onClick={onClose}
          className="flex size-11 items-center justify-center rounded-full bg-white/10 hover:bg-white/20"
          aria-label={t("closeCamera")}
        >
          <X className="size-5" />
        </button>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center px-4">
        {error ? (
          <div className="flex max-w-sm flex-col items-center gap-4 text-center">
            <p role="alert" className="text-mint-100/90">
              {error}
            </p>
            <button
              type="button"
              onClick={onChooseFiles}
              className="inline-flex min-h-12 items-center gap-2 rounded-full bg-mint-100 px-5 text-sm font-medium text-forest-900 active:scale-[0.98]"
            >
              <ImagePlus className="size-4" aria-hidden />
              {t("chooseFiles")}
            </button>
          </div>
        ) : (
          <>
            <video
              ref={video}
              autoPlay
              playsInline
              muted
              onLoadedData={() => {
                setReady(true);
                shutter.current?.focus();
              }}
              className="max-h-full max-w-full rounded-lg object-contain"
            />
            {!ready ? <Spinner className="absolute size-8" /> : null}
          </>
        )}
      </div>

      <div className="flex flex-col items-center gap-4 px-4 pt-4 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
        {!error ? (
          <>
            <ul className="flex flex-wrap justify-center gap-2">
              {TIPS.map(({ icon: Icon, key }) => (
                <li
                  key={key}
                  className="flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-xs text-mint-100/90"
                >
                  <Icon className="size-3.5" aria-hidden />
                  {t(key)}
                </li>
              ))}
            </ul>
            <button
              ref={shutter}
              type="button"
              onClick={capture}
              disabled={!ready}
              aria-label={t("capturePhoto")}
              className="flex size-18 items-center justify-center rounded-full bg-mint-100 text-forest-900 ring-4 ring-mint-100/30 transition-transform active:scale-95 disabled:opacity-50"
            >
              <Camera className="size-7" aria-hidden />
            </button>
          </>
        ) : null}
      </div>
    </motion.div>,
    document.body,
  );
}
