"use client";

import { useMemo, useSyncExternalStore } from "react";

import {
  parseStoredTriage,
  readLatestTriageRaw,
  subscribeToLatestTriage,
} from "@/lib/triage-storage";
import type { TriageResponse } from "@/types/triage";

type StoredTriage =
  | { state: "loading" }
  | { state: "missing" }
  | { state: "ready"; result: TriageResponse };

export function useLatestTriage(): StoredTriage {
  // undefined on the server (unknown), string | null in the browser.
  const raw = useSyncExternalStore<string | null | undefined>(
    subscribeToLatestTriage,
    readLatestTriageRaw,
    () => undefined,
  );

  return useMemo(() => {
    if (raw === undefined) return { state: "loading" };
    const result = parseStoredTriage(raw);
    return result ? { state: "ready", result } : { state: "missing" };
  }, [raw]);
}
