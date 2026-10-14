import type { TriageResponse } from "@/types/triage";

// Milestone 0 has no persistence: the latest result lives only in this browser tab.
const STORAGE_KEY = "rootcause:latest-triage";
const CHANGE_EVENT = "rootcause:triage-stored";

export function saveLatestTriage(result: TriageResponse): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(result));
  window.dispatchEvent(new Event(CHANGE_EVENT));
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
