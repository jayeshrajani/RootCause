"use client";

import { useState, type DragEvent } from "react";
import { Controller, useFormContext } from "react-hook-form";
import { AnimatePresence, motion } from "motion/react";
import { Camera, ImagePlus, Maximize, SunMedium, Leaf, X } from "lucide-react";

import { FieldMessage } from "@/components/forms/text-field";
import { ACCEPTED_IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES } from "@/lib/constants";
import { objectUrlFor, releaseObjectUrl } from "@/lib/object-urls";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";

const TIPS = [
  { icon: SunMedium, text: "Daylight, no flash" },
  { icon: Maximize, text: "Fill the frame" },
  { icon: Leaf, text: "Add a healthy leaf" },
];

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function PhotoGrid({ files, onRemove }: { files: File[]; onRemove: (index: number) => void }) {
  return (
    <motion.ul layout className="grid grid-cols-3 gap-2.5 sm:gap-3">
      <AnimatePresence mode="popLayout">
        {files.map((file, index) => (
          <motion.li
            key={objectUrlFor(file)}
            layout
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            className="group relative aspect-square overflow-hidden rounded-2xl bg-mint-200"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
            <img src={objectUrlFor(file)} alt={`Photo ${index + 1}`} className="size-full object-cover" />
            <span className="absolute bottom-2 left-2 rounded-full bg-forest-950/60 px-2 py-0.5 text-[11px] text-white backdrop-blur">
              {formatSize(file.size)}
            </span>
            <button
              type="button"
              onClick={() => onRemove(index)}
              className="absolute top-2 right-2 flex size-8 items-center justify-center rounded-full bg-white/90 text-forest-900 shadow-sm transition-transform hover:scale-105"
              aria-label={`Remove photo ${index + 1}`}
            >
              <X className="size-4" />
            </button>
          </motion.li>
        ))}
      </AnimatePresence>
    </motion.ul>
  );
}

export function PhotoStep() {
  const { control, formState } = useFormContext<ReportFormInput>();
  const [dragging, setDragging] = useState(false);
  const error = formState.errors.images?.message;

  return (
    <Controller
      control={control}
      name="images"
      render={({ field }) => {
        const files = field.value;
        const remaining = MAX_IMAGES - files.length;
        const add = (picked: File[]) => {
          if (picked.length) field.onChange([...files, ...picked]);
        };
        const onDrop = (event: DragEvent) => {
          event.preventDefault();
          setDragging(false);
          add(Array.from(event.dataTransfer.files));
        };

        return (
          <div className="space-y-4">
            {remaining > 0 ? (
              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed px-6 text-center transition-colors duration-300 has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-mint-400",
                  files.length ? "py-8" : "py-14",
                  dragging
                    ? "border-forest-700 bg-mint-200"
                    : error
                      ? "border-destructive/50 bg-white/60"
                      : "border-forest-900/20 bg-white/60 hover:border-forest-900/40 hover:bg-white",
                )}
              >
                <input
                  type="file"
                  accept={ACCEPTED_IMAGE_TYPES.join(",")}
                  multiple
                  className="sr-only"
                  aria-describedby="images-hint"
                  onChange={(event) => {
                    add(Array.from(event.target.files ?? []));
                    event.target.value = "";
                  }}
                  onBlur={field.onBlur}
                />
                <motion.span
                  className="flex size-14 items-center justify-center rounded-full bg-forest-900 text-mint-100"
                  animate={dragging ? { scale: 1.1 } : { scale: 1 }}
                >
                  {files.length ? <ImagePlus className="size-6" /> : <Camera className="size-6" />}
                </motion.span>
                <span className="text-lg font-medium">
                  {files.length ? `Add another photo` : "Take or choose photos"}
                </span>
                <span id="images-hint" className="text-sm text-muted-foreground">
                  {remaining} of {MAX_IMAGES} left · JPEG, PNG or WebP · up to{" "}
                  {MAX_IMAGE_BYTES / (1024 * 1024)} MB each
                </span>
              </label>
            ) : null}

            {files.length ? (
              <PhotoGrid
                files={files}
                onRemove={(index) => {
                  const removed = files[index];
                  field.onChange(files.filter((_, i) => i !== index));
                  if (removed) releaseObjectUrl(removed);
                }}
              />
            ) : null}

            <FieldMessage id="images-error" message={error} />

            <ul className="flex flex-wrap gap-2 pt-2">
              {TIPS.map(({ icon: Icon, text }) => (
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
