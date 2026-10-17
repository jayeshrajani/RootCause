import type { ReportFormValues } from "@/lib/schemas/report";
import type { ApiErrorBody, CropIdentification, TriageResponse } from "@/types/triage";
import type { LocationOption } from "@/types/location";
import type { Language } from "@/lib/i18n";
import { fileExtension } from "@/lib/voice/audio";
import { VISIT_HEADER, markLimitReached, recordInvestigation, visitId } from "@/lib/visit";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const REQUEST_TIMEOUT_MS = 60_000;

export type ApiErrorKind = "network" | "timeout" | "validation" | "server" | "limit";

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

function toFormData(values: ReportFormValues, language: Language): FormData {
  const form = new FormData();
  for (const image of values.images) form.append("images", image, image.name);
  const optional = {
    description: values.description,
    crop: values.crop,
    symptom_duration: values.symptom_duration,
    latitude: values.latitude,
    longitude: values.longitude,
    location_label: values.location_label,
    response_language: language,
  };
  for (const [key, value] of Object.entries(optional)) if (value) form.append(key, value);
  return form;
}

export async function submitTriageReport(
  values: ReportFormValues,
  language: Language = "en",
): Promise<TriageResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/triage`, {
      method: "POST",
      headers: { [VISIT_HEADER]: visitId() },
      body: toFormData(values, language),
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
    if (response.status === 429 && isApiErrorBody(body) && body.error.code === "investigation_limit") {
      markLimitReached();
      throw new ApiError("limit", body.error.message, [], 429);
    }
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

  recordInvestigation();
  return body as TriageResponse;
}

const IDENTIFY_TIMEOUT_MS = 20_000;

/** Stage 1: which crop the photos show. Sending coordinates warms weather and satellite lookups.
 * Returns null on any failure so the farmer can still continue. */
export async function identifyCrop(values: ReportFormValues): Promise<CropIdentification | null> {
  const form = new FormData();
  for (const image of values.images) form.append("images", image, image.name);
  if (values.latitude && values.longitude) {
    form.append("latitude", values.latitude);
    form.append("longitude", values.longitude);
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/triage/identify`, {
      method: "POST",
      body: form,
      signal: AbortSignal.timeout(IDENTIFY_TIMEOUT_MS),
    });
    if (!response.ok) return null;
    const body: unknown = await response.json();
    return typeof body === "object" && body !== null && "needs_confirmation" in body
      ? (body as CropIdentification)
      : null;
  } catch {
    return null;
  }
}

export async function translateTriage(
  result: TriageResponse,
  language: Language,
  signal: AbortSignal,
): Promise<TriageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/triage/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result, target_language: language }),
    signal,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || typeof body !== "object" || body === null || !("report_id" in body)) {
    const message = isApiErrorBody(body) ? body.error.message : "Translation is unavailable.";
    throw new ApiError("server", message, [], response.status);
  }
  return body as TriageResponse;
}

export async function searchLocations(query: string, signal: AbortSignal): Promise<LocationOption[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/locations/search?q=${encodeURIComponent(query)}`,
    { signal },
  );
  if (!response.ok) throw new Error("Location search unavailable");
  const result: unknown = await response.json();
  if (
    typeof result !== "object" ||
    result === null ||
    !("locations" in result) ||
    !Array.isArray(result.locations)
  ) {
    throw new Error("Unexpected location search response");
  }
  return result.locations as LocationOption[];
}

const TRANSCRIBE_TIMEOUT_MS = 45_000;

export type TranscriptionFailure =
  | "unavailable"
  | "no-speech"
  | "invalid-audio"
  | "timeout"
  | "network"
  | "failed";

export class TranscriptionError extends Error {
  constructor(
    readonly reason: TranscriptionFailure,
    message: string,
  ) {
    super(message);
    this.name = "TranscriptionError";
  }
}

export interface Transcription {
  transcript: string;
  language: string;
}

const TRANSCRIPTION_REASONS: Record<string, TranscriptionFailure> = {
  transcription_unavailable: "unavailable",
  no_speech_detected: "no-speech",
  empty_audio: "no-speech",
  unsupported_audio_type: "invalid-audio",
  audio_too_large: "invalid-audio",
  transcription_timeout: "timeout",
};

function withTimeout(signal: AbortSignal | undefined, ms: number): AbortSignal {
  const timeout = AbortSignal.timeout(ms);
  return signal && typeof AbortSignal.any === "function" ? AbortSignal.any([signal, timeout]) : (signal ?? timeout);
}

/** Speech to text for the optional description. Aborting `signal` rejects with an AbortError. */
export async function transcribeAudio(
  audio: Blob,
  language: string,
  signal?: AbortSignal,
): Promise<Transcription> {
  const form = new FormData();
  form.append("audio", audio, `voice-note.${fileExtension(audio.type)}`);
  form.append("language", language);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/transcribe`, {
      method: "POST",
      body: form,
      signal: withTimeout(signal, TRANSCRIBE_TIMEOUT_MS),
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new TranscriptionError("timeout", "Transcription took too long.");
    }
    throw new TranscriptionError("network", `Can't reach the RootCause service at ${API_BASE_URL}.`);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const code = isApiErrorBody(body) ? body.error.code : "";
    const message = isApiErrorBody(body) ? body.error.message : `HTTP ${response.status}`;
    throw new TranscriptionError(TRANSCRIPTION_REASONS[code] ?? "failed", message);
  }
  if (
    typeof body !== "object" ||
    body === null ||
    !("transcript" in body) ||
    typeof body.transcript !== "string"
  ) {
    throw new TranscriptionError("failed", "Unexpected transcription response.");
  }
  return body as Transcription;
}

const SPEAK_TIMEOUT_MS = 45_000;

/** Gemini text-to-speech for a result summary; resolves to a playable WAV blob. */
export async function speakText(text: string, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/v1/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    signal: withTimeout(signal, SPEAK_TIMEOUT_MS),
  });
  if (!response.ok) throw new Error(`Read-aloud failed (HTTP ${response.status})`);
  return response.blob();
}
