import type { ReportFormValues } from "@/lib/schemas/report";
import type { ApiErrorBody, TriageResponse } from "@/types/triage";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const REQUEST_TIMEOUT_MS = 60_000;

export type ApiErrorKind = "network" | "timeout" | "validation" | "server";

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    message: string,
    readonly fieldErrors: { field: string; message: string }[] = [],
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiErrorBody).error?.message === "string"
  );
}

function toFormData(values: ReportFormValues): FormData {
  const form = new FormData();
  form.append("crop", values.crop);
  form.append("description", values.description);
  form.append("latitude", values.latitude);
  form.append("longitude", values.longitude);
  if (values.symptom_duration) form.append("symptom_duration", values.symptom_duration);
  if (values.location_label) form.append("location_label", values.location_label);
  for (const image of values.images) form.append("images", image, image.name);
  return form;
}

export async function submitTriageReport(values: ReportFormValues): Promise<TriageResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/triage`, {
      method: "POST",
      body: toFormData(values),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("timeout", "The analysis took too long. Check your connection and try again.");
    }
    throw new ApiError(
      "network",
      `Can't reach the RootCause service at ${API_BASE_URL}. Check your internet connection, or make sure the API server is running, then try again.`,
    );
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (isApiErrorBody(body)) {
      const fieldErrors = body.error.details.flatMap((d) =>
        d.field ? [{ field: d.field, message: d.message }] : [],
      );
      const kind = response.status >= 500 ? "server" : "validation";
      throw new ApiError(kind, body.error.message, fieldErrors, response.status);
    }
    throw new ApiError(
      "server",
      `The RootCause service returned an unexpected error (HTTP ${response.status}). Please try again.`,
      [],
      response.status,
    );
  }

  return body as TriageResponse;
}
