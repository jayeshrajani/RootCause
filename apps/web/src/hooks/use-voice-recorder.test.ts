import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { FakeAudioContext, FakeMediaRecorder, installFakeMedia, removeFakeMedia } from "@/test/fake-media";

afterEach(removeFakeMedia);

describe("useVoiceRecorder", () => {
  it("records with MediaRecorder and releases the microphone on stop", async () => {
    const { track, getUserMedia } = installFakeMedia();
    const onRecorded = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded }));

    await act(() => result.current.start());
    expect(result.current.status).toBe("recording");
    expect(getUserMedia).toHaveBeenCalledWith({ audio: expect.any(Object) });
    expect(FakeMediaRecorder.instances[0].mimeType).toBe("audio/webm;codecs=opus");

    act(() => result.current.stop());

    expect(result.current.status).toBe("idle");
    expect(track.stop).toHaveBeenCalled();
    expect(onRecorded).toHaveBeenCalledWith(expect.any(Blob));
    expect((onRecorded.mock.calls[0][0] as Blob).type).toBe("audio/webm;codecs=opus");
  });

  it("reports an empty recording and still releases the microphone", async () => {
    const { track } = installFakeMedia({ chunkBytes: 0 });
    const onRecorded = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded }));

    await act(() => result.current.start());
    act(() => result.current.stop());

    expect(onRecorded).not.toHaveBeenCalled();
    expect(result.current.error).toBe("empty");
    expect(result.current.status).toBe("idle");
    expect(track.stop).toHaveBeenCalled();
  });

  it("reports an empty WAV fallback recording", async () => {
    const { track } = installFakeMedia({ recorder: false, audioContext: true });
    const onRecorded = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded }));

    await act(() => result.current.start());
    act(() => result.current.stop());

    expect(onRecorded).not.toHaveBeenCalled();
    expect(result.current.error).toBe("empty");
    expect(track.stop).toHaveBeenCalled();
  });

  it("does not report an empty recording when cancelled", async () => {
    installFakeMedia({ chunkBytes: 0 });
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded: vi.fn() }));

    await act(() => result.current.start());
    act(() => result.current.cancel());

    expect(result.current.error).toBeNull();
  });

  it("stops automatically at the maximum duration", async () => {
    installFakeMedia();
    const onRecorded = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded, maxSeconds: 0.3 }));

    await act(() => result.current.start());

    await waitFor(() => expect(onRecorded).toHaveBeenCalledTimes(1), { timeout: 2000 });
    expect(result.current.status).toBe("idle");
  });

  it("discards the clip when cancelled", async () => {
    const { track } = installFakeMedia();
    const onRecorded = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded }));

    await act(() => result.current.start());
    act(() => result.current.cancel());

    expect(onRecorded).not.toHaveBeenCalled();
    expect(track.stop).toHaveBeenCalled();
  });

  it("releases the microphone when the component unmounts mid-recording", async () => {
    const { track } = installFakeMedia();
    const onRecorded = vi.fn();
    const { result, unmount } = renderHook(() => useVoiceRecorder({ onRecorded }));

    await act(() => result.current.start());
    unmount();

    expect(track.stop).toHaveBeenCalled();
    expect(onRecorded).not.toHaveBeenCalled();
  });

  it("falls back to 16 kHz WAV when MediaRecorder cannot produce Opus (e.g. Safari)", async () => {
    installFakeMedia({ recorder: false, audioContext: true });
    const onRecorded = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded }));

    await act(() => result.current.start());
    const processor = FakeAudioContext.instances[0].processor;
    processor?.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array(4800) } });
    act(() => result.current.stop());

    const wav = onRecorded.mock.calls[0][0] as Blob;
    expect(wav.type).toBe("audio/wav");
    expect(wav.size).toBe(44 + 1600 * 2);
    expect(FakeAudioContext.instances[0].close).toHaveBeenCalled();
  });

  it.each([
    ["NotAllowedError", "permission"],
    ["NotFoundError", "no-microphone"],
    ["NotReadableError", "busy"],
  ])("reports %s as %s", async (name, expected) => {
    installFakeMedia({
      getUserMedia: async () => {
        throw new DOMException("denied", name);
      },
    });
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded: vi.fn() }));

    await act(() => result.current.start());

    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBe(expected);
  });

  it("reports unsupported browsers without asking for the microphone", async () => {
    const { getUserMedia } = installFakeMedia({ recorder: false, audioContext: false });
    const { result } = renderHook(() => useVoiceRecorder({ onRecorded: vi.fn() }));

    await act(() => result.current.start());

    expect(result.current.error).toBe("unsupported");
    expect(getUserMedia).not.toHaveBeenCalled();
  });
});
