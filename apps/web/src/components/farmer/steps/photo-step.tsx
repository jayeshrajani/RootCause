"use client";

import { useRef, useState, type DragEvent } from "react";
import { Controller, useFormContext } from "react-hook-form";
import { AnimatePresence, motion } from "motion/react";
import { Camera, ImagePlus, Maximize, Plus, SunMedium, Leaf, X } from "lucide-react";

import { LeafIllustration } from "@/components/brand/botanical";
import { CameraCapture } from "@/components/farmer/camera-capture";
import { FieldMessage } from "@/components/forms/text-field";
import { ACCEPTED_IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES } from "@/lib/constants";
import { objectUrlFor, releaseObjectUrl } from "@/lib/object-urls";
import type { ReportFormInput } from "@/lib/schemas/report";
import { nextStepId, scrollToStep } from "@/lib/step-scroll";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

const VIEWFINDER_CORNERS = [
  "top-4 left-4 border-t-2 border-l-2 rounded-tl-xl",
  "top-4 right-4 border-t-2 border-r-2 rounded-tr-xl",
  "bottom-4 left-4 border-b-2 border-l-2 rounded-bl-xl",
  "bottom-4 right-4 border-b-2 border-r-2 rounded-br-xl",
];

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function PhotoSlots({
  files,
  onAdd,
  onRemove,
  addLabel,
  removeLabel,
}: {
  files: File[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  addLabel: string;
  removeLabel: string;
}) {
  return (
    <ul className="grid grid-cols-3 gap-2.5 sm:gap-3">
      <AnimatePresence mode="popLayout" initial={false}>
        {Array.from({ length: MAX_IMAGES }, (_, index) => {
          const file = files[index];
          if (!file) {
            return (
              <motion.li key={`slot-${index}`} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <button
                  type="button"
                  onClick={onAdd}
                  className="flex aspect-square w-full flex-col items-center justify-center gap-1.5 rounded-2xl border-2 border-dashed border-forest-900/20 bg-white/50 text-forest-900/60 transition-colors hover:border-forest-900/45 hover:bg-white hover:text-forest-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
                >
                  <Plus className="size-5" aria-hidden />
                  <span className="text-xs font-medium">{addLabel}</span>
                </button>
              </motion.li>
            );
          }
          return (
            <motion.li
              key={objectUrlFor(file)}
              layout
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85 }}
              transition={{ type: "spring", stiffness: 380, damping: 30 }}
              className="relative aspect-square overflow-hidden rounded-2xl bg-mint-200 shadow-[0_14px_30px_-20px_rgba(22,54,38,0.7)]"
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
              <img src={objectUrlFor(file)} alt={`${removeLabel} ${index + 1}`} className="size-full object-cover" />
              <span className="absolute bottom-2 left-2 rounded-full bg-forest-950/60 px-2 py-0.5 text-[11px] text-white backdrop-blur">
                {formatSize(file.size)}
              </span>
              <button
                type="button"
                onClick={() => onRemove(index)}
                className="absolute top-2 right-2 flex size-8 items-center justify-center rounded-full bg-white/90 text-forest-900 shadow-sm transition-transform hover:scale-105"
                aria-label={`${removeLabel} ${index + 1}`}
              >
                <X className="size-4" />
              </button>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}

export function PhotoStep() {
  const { t } = useI18n();
  const { control, formState, getValues } = useFormContext<ReportFormInput>();
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const error = formState.errors.images?.message;
  const formats = `${t("imageFormat")}, ${MAX_IMAGE_BYTES / (1024 * 1024)} ${t("maxPerPhoto")}`;

  const openCamera = () => {
    // Phones open their own camera app via `capture`; desktops ignore it and show a file picker.
    const touch = window.matchMedia("(pointer: coarse)").matches;
    if (touch || !navigator.mediaDevices?.getUserMedia) cameraInput.current?.click();
    else setCameraOpen(true);
  };

  return (
    <Controller
      control={control}
      name="images"
      render={({ field }) => {
        const files = field.value;
        const remaining = MAX_IMAGES - files.length;
        const add = (picked: File[]) => {
          if (!picked.length) return;
          field.onChange([...files, ...picked]);
          if (files.length === 0) scrollToStep(nextStepId(getValues(), "photo"), 700);
        };
        const dropProps = {
          onDragOver: (event: DragEvent) => {
            event.preventDefault();
            setDragging(true);
          },
          onDragLeave: () => setDragging(false),
          onDrop: (event: DragEvent) => {
            event.preventDefault();
            setDragging(false);
            add(Array.from(event.dataTransfer.files));
          },
        };

        return (
          <div className="space-y-4">
            <AnimatePresence>
              {cameraOpen ? (
                <CameraCapture
                  onCapture={(file) => add([file])}
                  onClose={() => setCameraOpen(false)}
                />
              ) : null}
            </AnimatePresence>
            <input
              ref={cameraInput}
              type="file"
              accept={ACCEPTED_IMAGE_TYPES.join(",")}
              capture="environment"
              className="sr-only"
              tabIndex={-1}
              aria-label={t("takePhotoTitle")}
              aria-describedby={error ? "images-hint images-error" : "images-hint"}
              onChange={(event) => {
                add(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
              onBlur={field.onBlur}
            />
            <input
              ref={(element) => {
                fileInput.current = element;
                field.ref(element);
              }}
              type="file"
              accept={ACCEPTED_IMAGE_TYPES.join(",")}
              multiple
              className="sr-only"
              tabIndex={-1}
              aria-label={t("chooseFiles")}
              aria-invalid={!!error || undefined}
              aria-describedby={error ? "images-hint images-error" : "images-hint"}
              onChange={(event) => {
                add(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
              onBlur={field.onBlur}
            />

            {files.length === 0 ? (
              <div
                {...dropProps}
                className={cn(
                  "relative isolate flex min-h-[19rem] flex-col items-center justify-center gap-5 overflow-hidden rounded-[24px] px-6 py-10 text-center transition-colors duration-300 lg:min-h-[23.5rem]",
                  dragging ? "bg-mint-200" : "bg-forest-900/[0.045]",
                  error && "ring-2 ring-destructive/40",
                )}
              >
                {VIEWFINDER_CORNERS.map((corner) => (
                  <motion.span
                    key={corner}
                    aria-hidden
                    className={cn("absolute size-9 border-forest-900/35", corner)}
                    animate={dragging ? { scale: 0.86 } : { scale: 1 }}
                  />
                ))}
                <LeafIllustration className="absolute -right-8 -bottom-16 -z-10 h-72 rotate-12 text-forest-900/[0.07]" />
                <motion.span
                  className="flex size-16 items-center justify-center rounded-full bg-forest-900 text-mint-100 shadow-[0_16px_32px_-14px_rgba(22,54,38,0.7)]"
                  animate={dragging ? { scale: 1.08 } : { scale: 1 }}
                >
                  <Camera className="size-7" aria-hidden />
                </motion.span>
                <div>
                  <p className="text-lg font-medium">{t("addPhotos")}</p>
                  <p id="images-hint" className="mt-1 text-sm text-muted-foreground">
                    {t("upToPhotos")}
                    <br />
                    {formats}
                  </p>
                </div>
                <div className="grid w-full max-w-sm grid-cols-1 gap-2 min-[400px]:grid-cols-2">
                  <button
                    type="button"
                    onClick={openCamera}
                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-forest-900 px-5 text-sm font-medium text-mint-100 transition-colors hover:bg-forest-800 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
                  >
                    <Camera className="size-4 shrink-0" aria-hidden />
                    {t("takePhoto")}
                  </button>
                  <button
                    type="button"
                    onClick={() => fileInput.current?.click()}
                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-forest-900/20 bg-white px-5 text-sm font-medium transition-colors hover:border-forest-900/40 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
                  >
                    <ImagePlus className="size-4 shrink-0" aria-hidden />
                    {t("chooseFiles")}
                  </button>
                </div>
              </div>
            ) : (
              <div {...dropProps} className={cn("space-y-3 rounded-[24px] p-1 transition-colors", dragging && "bg-mint-200")}>
                <PhotoSlots
                  files={files}
                  addLabel={t("addPhoto")}
                  removeLabel={t("removePhoto")}
                  onAdd={() => fileInput.current?.click()}
                  onRemove={(index) => {
                    const removed = files[index];
                    field.onChange(files.filter((_, i) => i !== index));
                    if (removed) releaseObjectUrl(removed);
                  }}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p id="images-hint" className="text-xs text-muted-foreground">
                    {formats}
                  </p>
                  {remaining > 0 ? (
                    <button
                      type="button"
                      onClick={openCamera}
                      className="inline-flex min-h-10 items-center gap-2 rounded-full border border-forest-900/15 bg-white/80 px-4 text-sm font-medium transition-colors hover:border-forest-900/40 active:scale-[0.98]"
                    >
                      <Camera className="size-4" aria-hidden />
                      {t("takePhoto")}
                    </button>
                  ) : null}
                </div>
              </div>
            )}

            <FieldMessage id="images-error" message={error} />

            <ul className="flex flex-wrap gap-2">
              {[
                { icon: SunMedium, text: t("daylight") },
                { icon: Maximize, text: t("fillFrame") },
                { icon: Leaf, text: t("includeHealthy") },
              ].map(({ icon: Icon, text }) => (
                <li
                  key={text}
                  className="flex items-center gap-1.5 rounded-full bg-mint-100 px-3 py-1.5 text-xs text-forest-700"
                >
                  <Icon className="size-3.5" aria-hidden />
                  {text}
                </li>
              ))}
            </ul>
          </div>
        );
      }}
    />
  );
}
