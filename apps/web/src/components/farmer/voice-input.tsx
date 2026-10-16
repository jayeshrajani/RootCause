"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useFormContext } from "react-hook-form";
import { AlertCircle, Check, Mic, RotateCcw, Square, X } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";
import { useVoiceRecorder, type RecorderError } from "@/hooks/use-voice-recorder";
import { TranscriptionError, transcribeAudio, type TranscriptionFailure } from "@/lib/api/client";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { ReportFormInput } from "@/lib/schemas/report";
import { cn } from "@/lib/utils";
import {
  SPEECH_LANGUAGES,
  combineDescription,
  formatClock,
  speechLanguageFor,
  type InsertMode,
  type SpeechLanguage,
} from "@/lib/voice/audio";

const RECORDER_MESSAGES: Record<RecorderError, TranslationKey> = {
  unsupported: "voiceUnsupported",
  permission: "voicePermission",
  "no-microphone": "voiceNoMic",
  busy: "voiceMicBusy",
  empty: "voiceEmpty",
  failed: "voiceFailed",
};

const FAILURE_MESSAGES: Record<TranscriptionFailure, TranslationKey> = {
  unavailable: "voiceUnavailable",
  "no-speech": "voiceNoSpeech",
  "invalid-audio": "voiceFailed",
  timeout: "voiceFailed",
  network: "voiceFailed",
  failed: "voiceFailed",
};

type Phase =
  | { kind: "idle" }
  | { kind: "transcribing" }
  | { kind: "confirm"; transcript: string }
  | { kind: "done" }
  | { kind: "error"; message: TranslationKey; canRetry: boolean };

const secondaryButton =
  "inline-flex min-h-10 items-center gap-1.5 rounded-full border border-forest-900/20 bg-white px-4 text-sm font-medium transition-colors hover:border-forest-900/50 disabled:opacity-50";
const primaryButton =
  "inline-flex min-h-10 items-center gap-1.5 rounded-full bg-forest-900 px-4 text-sm font-medium text-mint-100 transition-colors hover:bg-forest-700 disabled:opacity-50";

/** Optional voice note: records, transcribes, and fills the report's existing `description`. */
export function VoiceInput({ onTranscribed }: { onTranscribed?: () => void }) {
  const { t, language } = useI18n();
  const { getValues, setValue } = useFormContext<ReportFormInput>();
  // Follows the interface language (which settles after hydration) until the farmer picks one.
  const [pickedLanguage, setPickedLanguage] = useState<SpeechLanguage | null>(null);
  const speechLanguage = pickedLanguage ?? speechLanguageFor(language);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const lastAudio = useRef<Blob | null>(null);
  const request = useRef<AbortController | null>(null);

  const apply = useCallback(
    (transcript: string, mode: InsertMode) => {
      const next = combineDescription(getValues("description") ?? "", transcript, mode);
      setValue("description", next, { shouldDirty: true, shouldValidate: true });
      setPhase({ kind: "done" });
      onTranscribed?.();
    },
    [getValues, onTranscribed, setValue],
  );

  const transcribe = useCallback(
    async (audio: Blob) => {
      lastAudio.current = audio;
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      setPhase({ kind: "transcribing" });
      try {
        const { transcript } = await transcribeAudio(audio, speechLanguage, controller.signal);
        if (controller.signal.aborted) return;
        if ((getValues("description") ?? "").trim()) setPhase({ kind: "confirm", transcript });
        else apply(transcript, "replace");
      } catch (error) {
        if (controller.signal.aborted) return;
        const reason = error instanceof TranscriptionError ? error.reason : "failed";
        setPhase({
          kind: "error",
          message: FAILURE_MESSAGES[reason],
          canRetry: reason !== "unavailable",
        });
      } finally {
        if (request.current === controller) request.current = null;
      }
    },
    [apply, getValues, speechLanguage],
  );

  const recorder = useVoiceRecorder({ onRecorded: (audio) => void transcribe(audio) });

  useEffect(() => () => request.current?.abort(), []);

  const begin = () => {
    setPhase({ kind: "idle" });
    void recorder.start();
  };
  const cancelTranscription = () => {
    request.current?.abort();
    setPhase({ kind: "idle" });
  };
  const retry = () => {
    if (lastAudio.current) void transcribe(lastAudio.current);
  };

  const busy = recorder.status !== "idle" || phase.kind === "transcribing";
  const error =
    phase.kind === "error"
      ? { message: phase.message, canRetry: phase.canRetry }
      : recorder.error && recorder.status === "idle"
        ? { message: RECORDER_MESSAGES[recorder.error], canRetry: false }
        : null;

  return (
    <div className="space-y-3">
      <div role="group" aria-label={t("voiceLanguage")} className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">{t("voiceLanguage")}</span>
        {SPEECH_LANGUAGES.map(({ code, label }) => (
          <button
            key={code}
            type="button"
            lang={code}
            aria-pressed={speechLanguage === code}
            disabled={busy}
            onClick={() => setPickedLanguage(code)}
            className={cn(
              "inline-flex h-9 items-center rounded-full border px-3.5 text-sm transition-colors disabled:opacity-60",
              speechLanguage === code
                ? "border-forest-900 bg-forest-900 text-mint-100"
                : "border-forest-900/15 bg-white/70 hover:border-forest-900/40",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {recorder.status === "recording" ? (
        <div className="rounded-lg border border-red-300 bg-red-50/70 p-4">
          <div className="flex items-center gap-3">
            <span className="relative flex size-3" aria-hidden>
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex size-3 rounded-full bg-red-500" />
            </span>
            <span className="font-medium">{t("voiceRecording")}</span>
            <span className="ml-auto font-mono text-sm tabular-nums" data-testid="voice-timer">
              {formatClock(recorder.elapsed)} / {formatClock(recorder.maxSeconds)}
            </span>
          </div>
          <div className="mt-3 h-1 overflow-hidden rounded-full bg-red-100" aria-hidden>
            <div
              className="h-full bg-red-500 transition-[width] duration-200"
              style={{ width: `${(recorder.elapsed / recorder.maxSeconds) * 100}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={recorder.stop} className={primaryButton}>
              <Square className="size-3.5" aria-hidden />
              {t("voiceStop")}
            </button>
            <button type="button" onClick={recorder.cancel} className={secondaryButton}>
              <X className="size-3.5" aria-hidden />
              {t("voiceCancel")}
            </button>
          </div>
        </div>
      ) : phase.kind === "transcribing" ? (
        <div className="flex min-h-16 items-center gap-3 rounded-lg border border-forest-900/15 bg-white/60 p-4">
          <Spinner className="size-5 text-forest-700" />
          <span className="min-w-0 flex-1 text-sm">{t("voiceTranscribing")}</span>
          <button type="button" onClick={cancelTranscription} className={secondaryButton}>
            {t("voiceCancel")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={begin}
          disabled={recorder.status === "requesting"}
          className="flex min-h-16 w-full items-center gap-4 rounded-lg border border-forest-900/15 bg-white/60 p-4 text-left transition-colors hover:border-forest-900/40 hover:bg-white disabled:cursor-wait"
        >
          <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-forest-900 text-mint-100">
            <Mic className="size-5" aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-medium">
              {phase.kind === "done" ? t("voiceRecordAgain") : t("recordVoice")}
            </span>
            <span className="block text-sm text-muted-foreground">
              {recorder.status === "requesting" ? t("voiceAllowMic") : t("voiceHint")}
            </span>
          </span>
        </button>
      )}

      <div aria-live="polite" className="space-y-2">
        {phase.kind === "done" ? (
          <p className="flex items-center gap-2 text-sm text-forest-700">
            <Check className="size-4 shrink-0" aria-hidden />
            {t("voiceAdded")}
          </p>
        ) : null}

        {phase.kind === "confirm" ? (
          <div className="rounded-lg border border-forest-900/15 bg-mint-100/60 p-3 text-sm">
            <p>{t("voiceExisting")}</p>
            <p lang={speechLanguage} className="mt-2 rounded-md bg-white/80 p-2 italic">
              “{phase.transcript}”
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" className={primaryButton} onClick={() => apply(phase.transcript, "replace")}>
                {t("voiceReplace")}
              </button>
              <button type="button" className={secondaryButton} onClick={() => apply(phase.transcript, "append")}>
                {t("voiceAppend")}
              </button>
              <button type="button" className={secondaryButton} onClick={() => setPhase({ kind: "idle" })}>
                {t("voiceKeepMine")}
              </button>
            </div>
          </div>
        ) : null}

        {error ? (
          <div
            role="alert"
            className="flex flex-wrap items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm"
          >
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
            <p className="min-w-0 flex-1">{t(error.message)}</p>
            {error.canRetry ? (
              <button type="button" onClick={retry} className={secondaryButton}>
                <RotateCcw className="size-3.5" aria-hidden />
                {t("voiceRetry")}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
