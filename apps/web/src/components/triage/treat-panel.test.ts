import { describe, expect, it } from "vitest";

import { parseApproximateLocation } from "@/components/triage/treat-panel";

describe("parseApproximateLocation", () => {
  it("reads the coordinates shown on results", () => {
    expect(parseApproximateLocation("18.52° N, 73.86° E")).toEqual({ latitude: 18.52, longitude: 73.86 });
    expect(parseApproximateLocation("33.87° S, 151.21° W")).toEqual({ latitude: -33.87, longitude: -151.21 });
  });

  it("returns null when there is no usable location", () => {
    expect(parseApproximateLocation(null)).toBeNull();
    expect(parseApproximateLocation("Nashik, Maharashtra")).toBeNull();
  });
});
