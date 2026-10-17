import { describe, expect, it } from "vitest";

import { readAloudScript } from "@/components/triage/read-aloud";

describe("readAloudScript", () => {
  it("speaks the cause, urgency, summary and the first three steps in order", () => {
    const script = readAloudScript({
      heading: "Potato: Early blight.",
      urgency: "Moderate urgency. Act within the next few days.",
      summary: "Brown ringed spots on the lower leaves.",
      nextLabel: "What to do next:",
      actions: ["Remove spotted leaves", "Avoid overhead watering", "Check nearby plants", "Ask an expert"],
    });

    expect(script).toBe(
      "Potato: Early blight. Moderate urgency. Act within the next few days. Brown ringed spots on the lower leaves. What to do next: 1. Remove spotted leaves 2. Avoid overhead watering 3. Check nearby plants",
    );
  });

  it("stays within the API's 1200-character limit, cutting at a word", () => {
    const script = readAloudScript({ heading: "", urgency: "", summary: "word ".repeat(400), nextLabel: "", actions: [] });

    expect(script.length).toBeLessThanOrEqual(1200);
    expect(script.endsWith("word…")).toBe(true);
  });
});
