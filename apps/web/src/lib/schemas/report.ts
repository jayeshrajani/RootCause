import { z } from "zod";

import {
  ACCEPTED_IMAGE_TYPES,
  DESCRIPTION_MAX,
  DESCRIPTION_MIN,
  LOCATION_LABEL_MAX,
  MAX_IMAGE_BYTES,
  MAX_IMAGES,
} from "@/lib/constants";
import { CROPS, SYMPTOM_DURATIONS } from "@/types/triage";

const acceptedTypes: readonly string[] = ACCEPTED_IMAGE_TYPES;

function coordinate(label: string, limit: number) {
  return z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .refine((value) => {
      const n = Number(value);
      return Number.isFinite(n) && Math.abs(n) <= limit;
    }, `${label} must be a number between -${limit} and ${limit}`);
}

// Validated again on the server; this schema only gives fast, friendly feedback.
export const reportFormSchema = z.object({
  crop: z.union([z.enum(CROPS), z.literal("")]).refine((v) => v !== "", "Choose a crop"),
  images: z
    .array(z.instanceof(File))
    .min(1, "Add at least one photo of the affected crop")
    .max(MAX_IMAGES, `Add no more than ${MAX_IMAGES} photos`)
    .refine(
      (files) => files.every((f) => acceptedTypes.includes(f.type)),
      "Photos must be JPEG, PNG or WebP images",
    )
    .refine(
      (files) => files.every((f) => f.size <= MAX_IMAGE_BYTES),
      `Each photo must be ${MAX_IMAGE_BYTES / (1024 * 1024)} MB or smaller`,
    ),
  description: z
    .string()
    .trim()
    .min(DESCRIPTION_MIN, `Describe what you see in at least ${DESCRIPTION_MIN} characters`)
    .max(DESCRIPTION_MAX, `Keep the description under ${DESCRIPTION_MAX} characters`),
  symptom_duration: z.union([z.enum(SYMPTOM_DURATIONS), z.literal("")]),
  latitude: coordinate("Latitude", 90),
  longitude: coordinate("Longitude", 180),
  location_label: z.string().trim().max(LOCATION_LABEL_MAX, "Keep the place name short"),
});

export type ReportFormInput = z.input<typeof reportFormSchema>;
export type ReportFormValues = z.output<typeof reportFormSchema>;

export const reportFormDefaults: ReportFormInput = {
  crop: "",
  images: [],
  description: "",
  symptom_duration: "",
  latitude: "",
  longitude: "",
  location_label: "",
};
