import { DESCRIPTION_MAX } from "@/lib/constants";

// Stays under Speech-to-Text's 1-minute limit for synchronous recognition, with margin for the stop.
export const MAX_RECORDING_SECONDS = 55;
export const WAV_SAMPLE_RATE = 16_000;

/** The API detects whether the farmer spoke English or Hindi. */
export const AUTO_LANGUAGE = "auto";

// Opus containers the API accepts (target browsers: Chrome desktop and Android Chrome). Speech-to-Text
// V2 can also decode MP4/AAC, but the API does not accept it yet; browsers without Opus use WAV.
const RECORDER_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus"] as const;

export function pickRecorderType(isTypeSupported?: (type: string) => boolean): string | null {
  if (!isTypeSupported) return null;
  return RECORDER_TYPES.find((type) => isTypeSupported(type)) ?? null;
}

export function fileExtension(type: string): string {
  if (type.startsWith("audio/webm")) return "webm";
  if (type.startsWith("audio/ogg")) return "ogg";
  if (type.startsWith("audio/wav")) return "wav";
  return "bin";
}

export function mergeChunks(chunks: readonly Float32Array[]): Float32Array {
  const out = new Float32Array(chunks.reduce((total, chunk) => total + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

/** Average-pool to a lower rate; speech needs no more than 16 kHz. */
export function downsample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (toRate >= fromRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

/** Mono 16-bit PCM WAV. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return new Blob([buffer], { type: "audio/wav" });
}

export type InsertMode = "replace" | "append";

export function combineDescription(existing: string, transcript: string, mode: InsertMode): string {
  const spoken = transcript.trim();
  const typed = existing.trim();
  const combined = mode === "append" && typed ? `${typed} ${spoken}` : spoken;
  return combined.slice(0, DESCRIPTION_MAX);
}

export function formatClock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
