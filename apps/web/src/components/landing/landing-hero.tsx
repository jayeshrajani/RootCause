"use client";

import { motion } from "motion/react";

import { BracketLink, Logo } from "@/components/brand/logo";
import { PillLink } from "@/components/brand/pill";
import { Reveal, RevealText } from "@/components/motion/reveal";
import { FieldRows } from "@/components/visuals/field-rows";

const SIGNALS = ["Photo evidence", "Weather signals", "Satellite indices"];

export function LandingHero() {
  return (
    <div className="grain relative flex min-h-[calc(100dvh-1.25rem)] flex-col overflow-hidden rounded-[20px] bg-mint-300 text-forest-900 sm:min-h-[calc(100dvh-2rem)] sm:rounded-[28px]">
      <FieldRows className="absolute inset-x-0 bottom-0 h-[62%] [mask-image:radial-gradient(ellipse_70%_75%_at_62%_62%,black_45%,transparent_100%)] sm:h-[76%]" />

      <Reveal y={-8} className="relative z-10">
        <nav className="flex items-center justify-between px-5 pt-4 sm:px-8 sm:pt-6" aria-label="Main">
          <BracketLink href="#principles" className="hidden sm:inline-flex">
            How it works
          </BracketLink>
          <Logo className="sm:absolute sm:left-1/2 sm:-translate-x-1/2" />
          <BracketLink href="/auth">Sign in</BracketLink>
        </nav>
      </Reveal>

      <div className="relative z-10 grid flex-1 grid-rows-[auto_1fr_auto] gap-6 px-5 pt-10 pb-6 sm:px-8 sm:pt-16 sm:pb-8 lg:grid-cols-[1.25fr_1fr]">
        <RevealText
          text="Understand crop distress before it spreads."
          className="max-w-[13ch] text-[clamp(2.6rem,7vw,5.75rem)] leading-[0.95] font-medium tracking-[-0.035em]"
          delay={0.15}
        />

        <motion.ul
          className="hidden flex-col items-start gap-2 lg:flex lg:pt-3"
          initial="hidden"
          animate="show"
          variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08, delayChildren: 0.7 } } }}
        >
          {SIGNALS.map((signal) => (
            <motion.li
              key={signal}
              variants={{ hidden: { opacity: 0, x: -8 }, show: { opacity: 1, x: 0 } }}
            >
              <a href="#principles" className="label-caps underline decoration-forest-900/40 underline-offset-4 transition-colors hover:decoration-forest-900">
                {signal}
              </a>
            </motion.li>
          ))}
        </motion.ul>

        <motion.div
          className="pointer-events-none relative hidden self-center justify-self-end sm:block lg:col-start-2 lg:row-start-2"
          initial={{ opacity: 0, scale: 0.96, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ delay: 1.4, duration: 0.9 }}
        >
          <div className="w-60 rounded-2xl border border-white/50 bg-mint-100/70 p-4 shadow-[0_20px_50px_-20px_rgba(22,54,38,0.45)] backdrop-blur-md">
            <p className="label-caps flex items-center gap-2 text-clay-600">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-clay-500 opacity-60" />
                <span className="relative inline-flex size-2 rounded-full bg-clay-500" />
              </span>
              Possible stress patch
            </p>
            <p className="mt-2 text-sm leading-snug">
              Hypothesis, low confidence. Needs a close-up photo and a field check.
            </p>
          </div>
        </motion.div>

        <div className="row-start-3 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between lg:col-span-2">
          <Reveal delay={0.9} className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <PillLink href="/auth">Start a crop report</PillLink>
            <BracketLink href="/report">Skip, try as guest</BracketLink>
          </Reveal>
          <Reveal delay={1.05}>
            <p className="max-w-xs border-l border-forest-900/60 pl-3 text-sm leading-snug">
              Evidence-led triage from your photos, symptoms, weather and satellite signals.
              Hypotheses, never verdicts.
            </p>
          </Reveal>
        </div>
      </div>
    </div>
  );
}
