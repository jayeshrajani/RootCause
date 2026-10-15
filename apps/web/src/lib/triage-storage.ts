import type { TriageResponse } from "@/types/triage";

// Milestone 0 has no persistence: the latest result lives only in this browser tab.
const STORAGE_KEY = "rootcause:latest-triage";
const CHANGE_EVENT = "rootcause:triage-stored";
const TRANSLATION_PREFIX = "rootcause:triage-translation:";

export function saveLatestTriage(result: TriageResponse): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(result));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function readTranslation(reportId: string, language: string): TriageResponse | null {
  try {
    return parseStoredTriage(sessionStorage.getItem(`${TRANSLATION_PREFIX}${reportId}:${language}`));
  } catch {
    return null;
  }
}

export function saveTranslation(result: TriageResponse): void {
  try {
    sessionStorage.setItem(
      `${TRANSLATION_PREFIX}${result.report_id}:${result.response_language}`,
      JSON.stringify(result),
    );
  } catch {
    // Storage may be full or blocked; the translation still shows for this view.
  }
}

export function readLatestTriageRaw(): string | null {
  return sessionStorage.getItem(STORAGE_KEY);
}

export function subscribeToLatestTriage(callback: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, callback);
  return () => window.removeEventListener(CHANGE_EVENT, callback);
}

export function parseStoredTriage(raw: string | null): TriageResponse | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value === "object" && value !== null && "report_id" in value) {
      return value as TriageResponse;
    }
  } catch {
    // Corrupt entries are treated as missing.
  }
  return null;
}
