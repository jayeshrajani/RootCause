"use client";

import { useSyncExternalStore } from "react";

// Preview only: no auth backend yet. Only a display name/email is kept on-device; never passwords.
const STORAGE_KEY = "rootcause:profile";
const CHANGE_EVENT = "rootcause:profile-changed";

export type Profile = { kind: "guest" } | { kind: "member"; name: string; email: string };

function read(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

function subscribe(callback: () => void) {
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

export function saveProfile(profile: Profile | null) {
  if (profile) localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  else localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function parse(raw: string | null | undefined): Profile | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<Profile>;
    if (value.kind === "guest") return { kind: "guest" };
    if (value.kind === "member" && typeof value.name === "string" && typeof value.email === "string") {
      return { kind: "member", name: value.name, email: value.email };
    }
  } catch {
    // Treat corrupt entries as signed out.
  }
  return null;
}

/** `undefined` while rendering on the server, then the stored profile (or null). */
export function useProfile(): Profile | null | undefined {
  const raw = useSyncExternalStore<string | null | undefined>(subscribe, read, () => undefined);
  return raw === undefined ? undefined : parse(raw);
}
