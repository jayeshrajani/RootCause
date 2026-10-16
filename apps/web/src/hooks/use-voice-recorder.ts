"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  MAX_RECORDING_SECONDS,
  WAV_SAMPLE_RATE,
  downsample,
  encodeWav,
  mergeChunks,
  pickRecorderType,
} from "@/lib/voice/audio";

export type RecorderStatus = "idle" | "requesting" | "recording";
export type RecorderError = "unsupported" | "permission" | "no-microphone" | "busy" | "failed";

interface Session {
  stream: MediaStream;
  keep: boolean;
  timer?: number;
  recorder?: MediaRecorder;
  context?: AudioContext;
  source?: MediaStreamAudioSourceNode;
  processor?: ScriptProcessorNode;
  samples: Float32Array[];
}

function classify(error: unknown): RecorderError {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "permission";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "no-microphone";
  if (name === "NotReadableError" || name === "AbortError") return "busy";
  return "failed";
}

function audioContextClass(): typeof AudioContext | undefined {
  if (typeof window === "undefined") return undefined;
  const legacy = window as unknown as { webkitAudioContext?: typeof AudioContext };
  return window.AudioContext ?? legacy.webkitAudioContext;
}

/** Records up to `maxSeconds` of microphone audio and hands the finished clip to `onRecorded`.
 * The microphone is released as soon as recording stops, is cancelled, or the component unmounts. */
export function useVoiceRecorder({
  onRecorded,
  maxSeconds = MAX_RECORDING_SECONDS,
}: {
  onRecorded: (audio: Blob) => void;
  maxSeconds?: number;
}) {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<RecorderError | null>(null);
  const session = useRef<Session | null>(null);
  const mounted = useRef(false);
  const onRecordedRef = useRef(onRecorded);

  useEffect(() => {
    onRecordedRef.current = onRecorded;
  }, [onRecorded]);

  const release = useCallback((current: Session) => {
    if (session.current === current) session.current = null;
    window.clearInterval(current.timer);
    current.stream.getTracks().forEach((track) => track.stop());
    current.processor?.disconnect();
    current.source?.disconnect();
    void current.context?.close().catch(() => undefined);
  }, []);

  const finish = useCallback(
    (keep: boolean) => {
      const current = session.current;
      if (!current) return;
      current.keep = keep;
      if (current.recorder) {
        // onstop releases the microphone and delivers the clip.
        if (current.recorder.state !== "inactive") current.recorder.stop();
        else release(current);
        return;
      }
      const rate = current.context?.sampleRate ?? WAV_SAMPLE_RATE;
      const samples = keep ? downsample(mergeChunks(current.samples), rate, WAV_SAMPLE_RATE) : null;
      release(current);
      setStatus("idle");
      if (samples && samples.length > 0) onRecordedRef.current(encodeWav(samples, WAV_SAMPLE_RATE));
    },
    [release],
  );

  const stop = useCallback(() => finish(true), [finish]);
  const cancel = useCallback(() => finish(false), [finish]);

  const start = useCallback(async () => {
    if (session.current) return;
    setError(null);
    const recorderType =
      typeof MediaRecorder === "undefined"
        ? null
        : pickRecorderType(MediaRecorder.isTypeSupported?.bind(MediaRecorder));
    const AudioContextClass = audioContextClass();
    if (!navigator.mediaDevices?.getUserMedia || (!recorderType && !AudioContextClass)) {
      setError("unsupported");
      return;
    }

    setStatus("requesting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      setStatus("idle");
      setError(classify(err));
      return;
    }
    if (!mounted.current) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }

    const current: Session = { stream, keep: true, samples: [] };
    try {
      if (recorderType) {
        const recorder = new MediaRecorder(stream, { mimeType: recorderType });
        const chunks: Blob[] = [];
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunks.push(event.data);
        };
        recorder.onstop = () => {
          release(current);
          setStatus("idle");
          if (current.keep && chunks.length > 0) {
            onRecordedRef.current(new Blob(chunks, { type: recorder.mimeType || recorderType }));
          }
        };
        recorder.onerror = () => {
          current.keep = false;
          release(current);
          setStatus("idle");
          setError("failed");
        };
        current.recorder = recorder;
        recorder.start(1000);
      } else if (AudioContextClass) {
        const context = new AudioContextClass();
        const source = context.createMediaStreamSource(stream);
        const processor = context.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = (event) => {
          current.samples.push(new Float32Array(event.inputBuffer.getChannelData(0)));
        };
        source.connect(processor);
        processor.connect(context.destination);
        Object.assign(current, { context, source, processor });
      }
    } catch {
      release(current);
      setStatus("idle");
      setError("failed");
      return;
    }

    const startedAt = Date.now();
    current.timer = window.setInterval(() => {
      const seconds = (Date.now() - startedAt) / 1000;
      setElapsed(Math.min(maxSeconds, seconds));
      if (seconds >= maxSeconds) finish(true);
    }, 200);
    session.current = current;
    setElapsed(0);
    setStatus("recording");
  }, [finish, maxSeconds, release]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      const current = session.current;
      if (!current) return;
      current.keep = false;
      if (current.recorder && current.recorder.state !== "inactive") current.recorder.stop();
      release(current);
    };
  }, [release]);

  return { status, elapsed, error, start, stop, cancel, maxSeconds };
}
