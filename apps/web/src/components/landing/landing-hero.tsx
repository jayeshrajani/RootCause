"use client";

import { ArrowRight, LogIn } from "lucide-react";

import { ButtonLink } from "@/components/brand/button";
import { Logo } from "@/components/brand/logo";
import { PillLink } from "@/components/brand/pill";
import { Reveal, RevealText } from "@/components/motion/reveal";
import { FieldRows } from "@/components/visuals/field-rows";

export function LandingHero() {
  return (
    <div className="grain relative flex min-h-[calc(100svh-1.25rem)] flex-col overflow-hidden rounded-[20px] bg-mint-300 text-forest-900 sm:min-h-[calc(100dvh-2rem)] sm:rounded-[28px]">
      <Reveal y={-8} className="relative z-10">
        <nav className="flex items-center justify-between gap-3 px-4 pt-4 sm:px-7 sm:pt-6" aria-label="Main">
          <Logo className="pl-1" />
          <div className="flex items-center gap-1 sm:gap-2">
            <ButtonLink href="#principles" variant="ghost" className="hidden sm:inline-flex">
              How it works
            </ButtonLink>
            <ButtonLink href="/auth" variant="outline">
              <LogIn aria-hidden />
              Sign in
            </ButtonLink>
          </div>
        </nav>
      </Reveal>

      <div className="relative z-10 flex flex-1 flex-col px-5 pt-8 pb-5 sm:grid sm:grid-rows-[auto_1fr_auto] sm:gap-6 sm:px-8 sm:pt-16 sm:pb-8">
        <RevealText
          text="Understand crop distress before it spreads."
          className="max-w-[13ch] text-[clamp(2.75rem,12vw,5.75rem)] leading-[0.92] font-medium tracking-[-0.04em] sm:leading-[0.95] sm:tracking-[-0.035em]"
          delay={0.15}
        />

        <Reveal delay={0.6} className="mt-4 sm:hidden">
          <p className="max-w-[32ch] text-[15px] leading-snug text-forest-900/75">
            Photos, symptoms, weather and satellite signals. Hypotheses, never verdicts.
          </p>
        </Reveal>

        {/* Phone: its own band in the flow. sm+: full backdrop behind the content. */}
        <div className="relative -mx-5 my-2 min-h-[34svh] flex-1 sm:absolute sm:inset-x-0 sm:bottom-0 sm:-z-10 sm:m-0 sm:h-[74%]">
          <FieldRows className="absolute inset-0 [mask-image:linear-gradient(to_bottom,transparent,black_18%,black_80%,transparent)] sm:[mask-image:radial-gradient(ellipse_58%_62%_at_64%_55%,black_30%,transparent_85%)]" />
        </div>

        <div className="flex flex-col gap-4 sm:row-start-3 sm:flex-row sm:items-end sm:justify-between">
          <Reveal delay={0.9} className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:gap-3">
            <PillLink href="/auth" className="h-14 w-full justify-between sm:h-12 sm:w-auto">
              Start a crop report
            </PillLink>
            <ButtonLink href="/report" variant="outline" size="lg" className="h-14 w-full sm:h-12 sm:w-auto">
              Try as guest
              <ArrowRight className="transition-transform group-hover:translate-x-0.5" aria-hidden />
            </ButtonLink>
          </Reveal>
          <Reveal delay={1.05} className="hidden sm:block">
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
