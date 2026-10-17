"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Square, Volume2 } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";
import { speakText } from "@/lib/api/client";
import { useI18n, type Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// Spoken clips per script (object URLs), shared by prefetch and play, so playback is instant once
// ready and replaying never calls the API again.
const clips = new Map<string, Promise<string>>();

function clipFor(script: string): Promise<string> {
  let clip = clips.get(script);
  if (!clip) {
    clip = speakText(script).then((blob) => URL.createObjectURL(blob));
    // A failed clip is forgotten so the next tap can try again.
    clip.catch(() => clips.delete(script));
    clips.set(script, clip);
  }
  return clip;
}

// Give the result a moment to render before preparing its audio in the background.
const PREFETCH_DELAY_MS = 1200;

const BROWSER_VOICES: Record<Language, string> = {
  en: "en-IN",
  hi: "hi-IN",
  pa: "pa-IN",
  es: "es-ES",
  fr: "fr-FR",
};

type Status = "idle" | "loading" | "playing";

/** Reads the main points aloud with Gemini TTS; falls back to the browser's own voice. */
export function ReadAloud({ script, language }: { script: string; language: Language }) {
  const { t } = useI18n();
  const [status, setStatus] = useState<Status>("idle");
  const audio = useRef<HTMLAudioElement | null>(null);
  const request = useRef<AbortController | null>(null);

  const stop = () => {
    request.current?.abort();
    audio.current?.pause();
    window.speechSynthesis?.cancel();
    setStatus("idle");
  };

  useEffect(() => {
    const timer = window.setTimeout(() => void clipFor(script).catch(() => undefined), PREFETCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [script]);

  // Stop talking when the result changes or the page goes away.
  useEffect(
    () => () => {
      request.current?.abort();
      audio.current?.pause();
      window.speechSynthesis?.cancel();
    },
    [script],
  );

  const speakInBrowser = () => {
    const synth = window.speechSynthesis;
    if (!synth) return setStatus("idle");
    const utterance = new SpeechSynthesisUtterance(script);
    utterance.lang = BROWSER_VOICES[language];
    utterance.rate = 0.95;
    utterance.onend = () => setStatus("idle");
    utterance.onerror = () => setStatus("idle");
    synth.cancel();
    synth.speak(utterance);
    setStatus("playing");
  };

  const play = async () => {
    if (status !== "idle") return stop();
    setStatus("loading");
    const controller = new AbortController();
    request.current = controller;
    try {
      const url = await clipFor(script);
      if (controller.signal.aborted) return;
      const player = new Audio(url);
      player.addEventListener("ended", () => setStatus("idle"));
      audio.current = player;
      await player.play();
      setStatus("playing");
    } catch {
      if (!controller.signal.aborted) speakInBrowser();
    }
  };

  const label = status === "idle" ? t("readAloud") : status === "loading" ? t("readAloudPreparing") : t("readAloudStop");

  return (
    <button
      type="button"
      onClick={() => void play()}
      aria-pressed={status === "playing"}
      className={cn(
        "inline-flex h-10 shrink-0 items-center gap-2 rounded-full pr-4 pl-1.5 text-sm font-medium transition-colors",
        status === "playing" ? "bg-mint-300 text-forest-900" : "bg-mint-100/10 text-mint-100 hover:bg-mint-100/20",
      )}
    >
      <span
        className={cn(
          "flex size-7 items-center justify-center rounded-full",
          status === "playing" ? "bg-forest-900 text-mint-300" : "bg-mint-300 text-forest-900",
        )}
      >
        {status === "loading" ? (
          <Spinner className="size-3.5" />
        ) : status === "playing" ? (
          <Square className="size-3" fill="currentColor" aria-hidden />
        ) : (
          <Volume2 className="size-3.5" aria-hidden />
        )}
      </span>
      {status === "playing" ? (
        <span className="flex h-4 items-center gap-0.5" aria-hidden>
          {[0, 1, 2, 3].map((bar) => (
            <motion.span
              key={bar}
              className="w-0.5 rounded-full bg-forest-900"
              animate={{ height: [4, 14, 6, 12, 4] }}
              transition={{ duration: 1, repeat: Infinity, delay: bar * 0.12, ease: "easeInOut" }}
            />
          ))}
        </span>
      ) : null}
      {label}
    </button>
  );
}

/** The main points, in the result's language: crop and likely cause, urgency, summary, first steps. */
export function readAloudScript(parts: {
  heading: string;
  urgency: string;
  summary: string;
  nextLabel: string;
  actions: string[];
}): string {
  const steps = parts.actions.slice(0, 3).map((action, i) => `${i + 1}. ${action}`);
  const script = [parts.heading, parts.urgency, parts.summary, steps.length ? `${parts.nextLabel} ${steps.join(" ")}` : ""]
    .filter(Boolean)
    .join(" ");
  return script.length > 1200 ? `${script.slice(0, 1190).replace(/\s+\S*$/, "")}…` : script;
}
