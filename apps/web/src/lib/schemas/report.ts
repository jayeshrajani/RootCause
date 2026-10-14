import { z } from "zod";

import {
  ACCEPTED_IMAGE_TYPES,
  DESCRIPTION_MAX,
  LOCATION_LABEL_MAX,
  MAX_IMAGE_BYTES,
  MAX_IMAGES,
} from "@/lib/constants";
import { CROPS, SYMPTOM_DURATIONS } from "@/types/triage";

const acceptedTypes: readonly string[] = ACCEPTED_IMAGE_TYPES;

function optionalCoordinate(label: string, limit: number) {
  return z
    .string()
    .trim()
    .refine((value) => {
      if (value === "") return true;
      const n = Number(value);
      return Number.isFinite(n) && Math.abs(n) <= limit;
    }, `${label} must be a number between -${limit} and ${limit}`);
}

// Only photos are required. Validated again on the server; this gives fast feedback.
export const reportFormSchema = z
  .object({
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
      .max(DESCRIPTION_MAX, `Keep the description under ${DESCRIPTION_MAX} characters`),
    crop: z.union([z.enum(CROPS), z.literal("")]),
    symptom_duration: z.union([z.enum(SYMPTOM_DURATIONS), z.literal("")]),
    latitude: optionalCoordinate("Latitude", 90),
    longitude: optionalCoordinate("Longitude", 180),
    location_label: z.string().trim().max(LOCATION_LABEL_MAX, "Keep the place name short"),
  })
  .superRefine((v, ctx) => {
    if (!v.latitude !== !v.longitude) {
      ctx.addIssue({
        code: "custom",
        path: [v.latitude ? "longitude" : "latitude"],
        message: "Add both latitude and longitude, or leave both empty",
      });
    }
  });

export type ReportFormInput = z.input<typeof reportFormSchema>;
export type ReportFormValues = z.output<typeof reportFormSchema>;

export const reportFormDefaults: ReportFormInput = {
  images: [],
  description: "",
  crop: "",
  symptom_duration: "",
  latitude: "",
  longitude: "",
  location_label: "",
};
