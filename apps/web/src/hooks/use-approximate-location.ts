"use client";

import { useCallback, useState } from "react";

// Two decimals is roughly 1 km: enough for weather lookups without pinpointing a farm.
const COORDINATE_DECIMALS = 4;

type LocationState =
  | { status: "idle" }
  | { status: "locating" }
  | { status: "error"; message: string };

const ERROR_MESSAGES: Record<number, string> = {
  1: "Location permission was denied. Enter a village or district instead, or allow location access.",
  2: "Your location could not be determined. Enter a village or district instead.",
  3: "Finding your location took too long. Try again or enter a village or district instead.",
};

export function useApproximateLocation(
  onLocated: (coords: { latitude: string; longitude: string }) => void,
) {
  const [state, setState] = useState<LocationState>({ status: "idle" });

  const locate = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setState({ status: "error", message: "This browser can't share your location." });
      return;
    }
    setState({ status: "locating" });
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        onLocated({
          latitude: coords.latitude.toFixed(COORDINATE_DECIMALS),
          longitude: coords.longitude.toFixed(COORDINATE_DECIMALS),
        });
        setState({ status: "idle" });
      },
      (error) =>
        setState({
          status: "error",
          message: ERROR_MESSAGES[error.code] ?? ERROR_MESSAGES[2],
        }),
      { enableHighAccuracy: false, timeout: 15_000, maximumAge: 10 * 60_000 },
    );
  }, [onLocated]);

  return { state, locate };
}
