"use client";

import { useRef, useState, type DragEvent } from "react";
import { Controller, useFormContext } from "react-hook-form";
import { AnimatePresence, motion } from "motion/react";
import { Camera, ImagePlus, Sparkles, X } from "lucide-react";

import { CameraCapture } from "@/components/farmer/camera-capture";
import { LeafIllustration } from "@/components/brand/botanical";
import { FieldMessage } from "@/components/forms/text-field";
import { Spinner } from "@/components/ui/spinner";
import { ACCEPTED_IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES } from "@/lib/constants";
import { objectUrlFor, releaseObjectUrl } from "@/lib/object-urls";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";

// Demo photos served from /public/samples; named by plant only so nothing hints at the answer.
const SAMPLES = [
  { file: "chilli-plant.jpg", label: "Chilli" },
  { file: "potato-leaf.jpg", label: "Potato" },
  { file: "tomato-leaf.jpg", label: "Tomato" },
] as const;

/** One-tap sample photos, so anyone trying the app needn't hunt for a sick plant. */
function SampleShelf({ onPick }: { onPick: (file: File) => void }) {
  const [loading, setLoading] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const pick = async (name: string) => {
    setLoading(name);
    setFailed(false);
    try {
      const response = await fetch(`/samples/${name}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      onPick(new File([blob], name, { type: blob.type || "image/jpeg" }));
    } catch {
      setFailed(true);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="rounded-2xl border border-dashed border-forest-900/15 p-3">
      <p className="mb-2.5 flex items-center gap-1.5 px-0.5 text-xs font-medium text-forest-700">
        <Sparkles className="size-3.5" aria-hidden />
        No plant handy? Try a sample photo
      </p>
      <ul className="grid grid-cols-3 gap-2">
        {SAMPLES.map(({ file, label }) => (
          <li key={file}>
            <button
              type="button"
              onClick={() => void pick(file)}
              disabled={loading !== null}
              aria-label={`Use the sample ${label.toLowerCase()} photo`}
              className="group relative block aspect-[4/3] w-full overflow-hidden rounded-xl bg-mint-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700 disabled:cursor-wait"
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- small static demo thumbnails */}
              <img
                src={`/samples/${file}`}
                alt=""
                loading="lazy"
                className="size-full object-cover transition-transform duration-500 group-hover:scale-110"
              />
              <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-forest-950/80 to-transparent px-2 pt-5 pb-1.5 text-left text-xs font-medium text-white">
                {label}
              </span>
              {loading === file ? (
                <span className="absolute inset-0 flex items-center justify-center bg-forest-950/40">
                  <Spinner className="size-5 text-white" />
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
      {failed ? (
        <p role="alert" className="mt-2 text-xs text-destructive">
          Couldn&apos;t load that sample. Try another, or add your own photo.
        </p>
      ) : null}
    </div>
  );
}

function PhotoGrid({ files, onRemove }: { files: File[]; onRemove: (index: number) => void }) {
  return (
    <motion.ul layout className="grid grid-cols-4 gap-2">
      <AnimatePresence mode="popLayout">
        {files.map((file, index) => (
          <motion.li
            key={objectUrlFor(file)}
            layout
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            className="group relative aspect-square overflow-hidden rounded-xl bg-mint-200"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
            <img src={objectUrlFor(file)} alt={`Photo ${index + 2}`} className="size-full object-cover" />
            <button
              type="button"
              onClick={() => onRemove(index)}
              className="absolute top-1.5 right-1.5 flex size-6 items-center justify-center rounded-full bg-white/90 text-forest-900 shadow-sm transition-transform hover:scale-105"
              aria-label={`Remove photo ${index + 2}`}
            >
              <X className="size-3.5" />
            </button>
          </motion.li>
        ))}
      </AnimatePresence>
    </motion.ul>
  );
}

export function PhotoStep() {
  const { control, formState } = useFormContext<ReportFormInput>();
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const error = formState.errors.images?.message;

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
          if (picked.length) field.onChange([...files, ...picked]);
        };
        const onDrop = (event: DragEvent) => {
          event.preventDefault();
          setDragging(false);
          add(Array.from(event.dataTransfer.files));
        };

        return (
          <div className="space-y-4">
            <AnimatePresence>
              {cameraOpen ? (
                <CameraCapture
                  onCapture={(file) => add([file])}
                  onClose={() => setCameraOpen(false)}
                  onChooseFiles={() => {
                    setCameraOpen(false);
                    fileInput.current?.click();
                  }}
                />
              ) : null}
            </AnimatePresence>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                "relative overflow-hidden rounded-[22px] transition-colors duration-300",
                files.length ? "bg-forest-900" : "bg-mint-100/70",
                dragging && "bg-mint-200",
                error && !files.length && "ring-2 ring-destructive/40",
              )}
            >
              <input
                ref={cameraInput}
                type="file"
                accept={ACCEPTED_IMAGE_TYPES.join(",")}
                capture="environment"
                className="sr-only"
                tabIndex={-1}
                aria-label="Take a photo"
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
                aria-label="Choose photo files"
                aria-invalid={!!error || undefined}
                aria-describedby={error ? "images-hint images-error" : "images-hint"}
                onChange={(event) => {
                  add(Array.from(event.target.files ?? []));
                  event.target.value = "";
                }}
                onBlur={field.onBlur}
              />

              <div className={cn("relative w-full", files.length ? "aspect-[4/3] md:aspect-[16/10]" : "aspect-[16/10] md:aspect-[2/1]")}>
                {files.length ? (
                  // eslint-disable-next-line @next/next/no-img-element -- local blob preview
                  <img
                    src={objectUrlFor(files[0])}
                    alt="Photo 1"
                    className="absolute inset-0 size-full object-cover"
                  />
                ) : (
                  <>
                    <div
                      aria-hidden
                      className="absolute inset-0 bg-[linear-gradient(rgba(22,54,38,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(22,54,38,0.06)_1px,transparent_1px)] bg-[size:28px_28px]"
                    />
                    <LeafIllustration className="absolute inset-0 m-auto h-[70%] text-forest-700/15" />
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
                      <motion.span
                        className="flex size-16 items-center justify-center rounded-full bg-forest-900 text-mint-100 shadow-[0_14px_30px_-12px_rgba(22,54,38,0.6)]"
                        animate={dragging ? { scale: 1.12 } : { scale: [1, 1.04, 1] }}
                        transition={dragging ? undefined : { duration: 3, repeat: Infinity, ease: "easeInOut" }}
                      >
                        <Camera className="size-7" aria-hidden />
                      </motion.span>
                      <span className="text-lg font-medium">Add crop photos</span>
                      <span className="max-w-[26ch] text-sm text-forest-900/60">
                        The affected leaf, close up. Drop photos here or use the buttons below.
                      </span>
                    </div>
                  </>
                )}
                {/* Viewfinder corners */}
                {[
                  "top-3 left-3 border-t-2 border-l-2 rounded-tl-lg",
                  "top-3 right-3 border-t-2 border-r-2 rounded-tr-lg",
                  "bottom-3 left-3 border-b-2 border-l-2 rounded-bl-lg",
                  "right-3 bottom-3 border-r-2 border-b-2 rounded-br-lg",
                ].map((corner) => (
                  <span
                    key={corner}
                    aria-hidden
                    className={cn(
                      "pointer-events-none absolute size-6",
                      files.length ? "border-white/80" : "border-forest-900/30",
                      corner,
                    )}
                  />
                ))}
                {files.length ? (
                  <button
                    type="button"
                    onClick={() => {
                      const removed = files[0];
                      field.onChange(files.slice(1));
                      if (removed) releaseObjectUrl(removed);
                    }}
                    className="absolute top-4 right-4 flex size-9 items-center justify-center rounded-full bg-white/90 text-forest-900 shadow-sm transition-transform hover:scale-105"
                    aria-label="Remove photo 1"
                  >
                    <X className="size-4" />
                  </button>
                ) : null}
              </div>
            </div>

            {files.length > 1 ? (
              <PhotoGrid
                files={files.slice(1)}
                onRemove={(index) => {
                  const removed = files[index + 1];
                  field.onChange(files.filter((_, i) => i !== index + 1));
                  if (removed) releaseObjectUrl(removed);
                }}
              />
            ) : null}

            {remaining > 0 ? (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={openCamera}
                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-forest-900 px-4 text-sm font-medium text-mint-100 transition-colors hover:bg-forest-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
                  >
                    <Camera className="size-4 shrink-0" aria-hidden />
                    {files.length ? "Another photo" : "Take photo"}
                  </button>
                  <button
                    type="button"
                    onClick={() => fileInput.current?.click()}
                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-forest-900/15 bg-white px-4 text-sm font-medium transition-colors hover:border-forest-900/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
                  >
                    <ImagePlus className="size-4 shrink-0" aria-hidden />
                    Choose files
                  </button>
                </div>
                <p id="images-hint" className="text-center text-xs text-muted-foreground">
                  {remaining} of {MAX_IMAGES} left · JPEG, PNG or WebP · up to{" "}
                  {MAX_IMAGE_BYTES / (1024 * 1024)} MB each
                </p>
              </div>
            ) : null}

            {files.length === 0 ? <SampleShelf onPick={(file) => add([file])} /> : null}

            <FieldMessage id="images-error" message={error} />

          </div>
        );
      }}
    />
  );
}
