import { describe, expect, it } from "vitest";

import { DESCRIPTION_MAX } from "@/lib/constants";
import {
  combineDescription,
  downsample,
  encodeWav,
  fileExtension,
  formatClock,
  pickRecorderType,
} from "@/lib/voice/audio";

function readBytes(blob: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

describe("voice audio helpers", () => {
  it("prefers containers Speech-to-Text can decode and falls back to WAV otherwise", () => {
    expect(pickRecorderType((t) => t === "audio/webm;codecs=opus")).toBe("audio/webm;codecs=opus");
    expect(pickRecorderType((t) => t === "audio/ogg;codecs=opus")).toBe("audio/ogg;codecs=opus");
    expect(pickRecorderType((t) => t === "audio/mp4")).toBeNull();
    expect(pickRecorderType(undefined)).toBeNull();
  });

  it("maps recording types to upload extensions", () => {
    expect(fileExtension("audio/webm;codecs=opus")).toBe("webm");
    expect(fileExtension("audio/ogg")).toBe("ogg");
    expect(fileExtension("audio/wav")).toBe("wav");
  });

  it("encodes mono 16-bit WAV with a valid header", async () => {
    const wav = encodeWav(new Float32Array([0, 0.5, -0.5, 1]), 16_000);
    const view = new DataView(await readBytes(wav));
    const text = (start: number) =>
      String.fromCharCode(...Array.from({ length: 4 }, (_, i) => view.getUint8(start + i)));

    expect(wav.type).toBe("audio/wav");
    expect(wav.size).toBe(44 + 4 * 2);
    expect(text(0)).toBe("RIFF");
    expect(text(8)).toBe("WAVE");
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(16_000);
    expect(view.getInt16(44 + 3 * 2, true)).toBe(0x7fff);
  });

  it("downsamples to speech rate", () => {
    expect(downsample(new Float32Array(48_000), 48_000, 16_000)).toHaveLength(16_000);
    expect(downsample(new Float32Array(10), 8_000, 16_000)).toHaveLength(10);
  });

  it("replaces or appends transcripts and respects the description limit", () => {
    expect(combineDescription("", "  पत्ते पीले हैं ", "replace")).toBe("पत्ते पीले हैं");
    expect(combineDescription("My notes.", "Spots too.", "append")).toBe("My notes. Spots too.");
    expect(combineDescription("My notes.", "Spots too.", "replace")).toBe("Spots too.");
    expect(combineDescription("a", "b".repeat(DESCRIPTION_MAX + 50), "append")).toHaveLength(
      DESCRIPTION_MAX,
    );
  });

  it("formats the recording clock", () => {
    expect(formatClock(0)).toBe("0:00");
    expect(formatClock(9.7)).toBe("0:09");
    expect(formatClock(60)).toBe("1:00");
  });
});
