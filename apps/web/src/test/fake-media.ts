import { vi } from "vitest";

export class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  static chunkBytes = 2048;
  static isTypeSupported = (type: string) => type === "audio/webm;codecs=opus";

  state: "inactive" | "recording" = "inactive";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(
    readonly stream: MediaStream,
    readonly options: { mimeType: string },
  ) {
    FakeMediaRecorder.instances.push(this);
  }

  get mimeType(): string {
    return this.options.mimeType;
  }

  start(): void {
    this.state = "recording";
  }

  stop(): void {
    this.state = "inactive";
    const bytes = new Uint8Array(FakeMediaRecorder.chunkBytes);
    this.ondataavailable?.({ data: new Blob([bytes], { type: this.mimeType }) });
    this.onstop?.();
  }
}

export interface FakeProcessor {
  onaudioprocess: ((event: { inputBuffer: { getChannelData: () => Float32Array } }) => void) | null;
  connect: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
}

export class FakeAudioContext {
  static instances: FakeAudioContext[] = [];
  sampleRate = 48_000;
  destination = {};
  processor: FakeProcessor | null = null;
  close = vi.fn(async () => undefined);

  constructor() {
    FakeAudioContext.instances.push(this);
  }

  createMediaStreamSource() {
    return { connect: vi.fn(), disconnect: vi.fn() };
  }

  createScriptProcessor(): FakeProcessor {
    this.processor = { onaudioprocess: null, connect: vi.fn(), disconnect: vi.fn() };
    return this.processor;
  }
}

/** Fake microphone, MediaRecorder and (optionally) Web Audio for jsdom tests. */
export function installFakeMedia(
  options: {
    recorder?: boolean;
    audioContext?: boolean;
    /** Bytes MediaRecorder delivers on stop; 0 simulates a recording with no audio. */
    chunkBytes?: number;
    getUserMedia?: (constraints: MediaStreamConstraints) => Promise<MediaStream>;
  } = {},
) {
  const { recorder = true, audioContext = false, chunkBytes = 2048 } = options;
  const track = { stop: vi.fn() };
  const stream = { getTracks: () => [track] } as unknown as MediaStream;
  const getUserMedia = vi.fn(options.getUserMedia ?? (async () => stream));
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  FakeMediaRecorder.instances = [];
  FakeMediaRecorder.chunkBytes = chunkBytes;
  FakeAudioContext.instances = [];
  vi.stubGlobal("MediaRecorder", recorder ? FakeMediaRecorder : undefined);
  vi.stubGlobal("AudioContext", audioContext ? FakeAudioContext : undefined);
  return { track, stream, getUserMedia };
}

export function removeFakeMedia(): void {
  Reflect.deleteProperty(navigator, "mediaDevices");
}
