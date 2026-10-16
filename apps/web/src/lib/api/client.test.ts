import { afterEach, describe, expect, it, vi } from "vitest";

import { submitTriageReport, TranscriptionError, transcribeAudio } from "@/lib/api/client";
import { reportFormDefaults, type ReportFormValues } from "@/lib/schemas/report";

function photo(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], "leaf.jpg", { type: "image/jpeg" });
}

function values(description: string): ReportFormValues {
  return { ...reportFormDefaults, images: [photo()], description } as ReportFormValues;
}

function sentForm(fetchMock: ReturnType<typeof vi.fn>): FormData {
  return (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
}

afterEach(() => vi.unstubAllGlobals());

describe("triage submission with optional description", () => {
  it("submits without a description", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ report_id: "r1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await submitTriageReport(values(""));

    const form = sentForm(fetchMock);
    expect(form.has("description")).toBe(false);
    expect(form.getAll("images")).toHaveLength(1);
  });

  it("sends a voice transcript as the ordinary description", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ report_id: "r1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await submitTriageReport(values("पत्ते पीले हो रहे हैं"));

    expect(sentForm(fetchMock).get("description")).toBe("पत्ते पीले हो रहे हैं");
  });
});

describe("transcribeAudio", () => {
  const audio = new Blob([new Uint8Array(1024)], { type: "audio/webm;codecs=opus" });

  it("posts the recording and language", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ transcript: "ok", language: "hi-IN" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(transcribeAudio(audio, "hi-IN")).resolves.toEqual({ transcript: "ok", language: "hi-IN" });
    const form = sentForm(fetchMock);
    expect(form.get("language")).toBe("hi-IN");
    expect((form.get("audio") as File).name).toBe("voice-note.webm");
  });

  it.each([
    [503, "transcription_unavailable", "unavailable"],
    [422, "no_speech_detected", "no-speech"],
    [415, "unsupported_audio_type", "invalid-audio"],
    [504, "transcription_timeout", "timeout"],
    [502, "transcription_failed", "failed"],
  ])("maps HTTP %s %s to %s", async (status, code, reason) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: { code, message: "m", details: [] } }), { status })),
    );

    await expect(transcribeAudio(audio, "en-IN")).rejects.toMatchObject({ reason });
  });

  it("reports network failures", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));

    const error = await transcribeAudio(audio, "en-IN").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(TranscriptionError);
    expect((error as TranscriptionError).reason).toBe("network");
  });
});
