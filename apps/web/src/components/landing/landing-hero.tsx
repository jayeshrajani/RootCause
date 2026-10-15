"use client";

import type { ReactNode } from "react";
import { ArrowRight, Check, CloudSun, Droplets, ListChecks, LogIn, Trophy } from "lucide-react";
import { motion } from "motion/react";

import { ButtonLink } from "@/components/brand/button";
import { LanguageSwitcher } from "@/components/app/language-switcher";
import { LeafIllustration } from "@/components/brand/botanical";
import { Logo } from "@/components/brand/logo";
import { PillLink } from "@/components/brand/pill";
import { Reveal, RevealText } from "@/components/motion/reveal";
import { FieldRows } from "@/components/visuals/field-rows";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const EASE = [0.16, 1, 0.3, 1] as const;
const SAMPLE_WEATHER = "22–33°C";
const SAMPLE_HUMIDITY = "72%";

/** Decorative sample of what a report returns; floats gently beside the headline. */
function PreviewCard({ className, delay, tilt, children }: { className: string; delay: number; tilt: number; children: ReactNode }) {
  return (
    <motion.div
      className={cn("absolute", className)}
      initial={{ opacity: 0, y: 28, rotate: 0 }}
      animate={{ opacity: 1, y: 0, rotate: tilt }}
      transition={{ duration: 1.1, ease: EASE, delay }}
    >
      <motion.div
        animate={{ y: [0, -7, 0] }}
        transition={{ duration: 5 + delay * 1.5, ease: "easeInOut", repeat: Infinity }}
        className="rounded-[22px] border border-white/70 bg-white/70 p-4 text-left shadow-[0_28px_50px_-28px_rgba(22,54,38,0.55)] backdrop-blur-md"
      >
        {children}
      </motion.div>
    </motion.div>
  );
}

export function LandingHero() {
  const { language, t } = useI18n();
  const titleLead = t("heroTitleLead");
  const titleAccent = t("heroTitleAccent");
  const longTitle = titleLead.length + titleAccent.length > 40;
  const indicScript = language === "hi" || language === "pa";

  return (
    <div className="grain relative flex min-h-[calc(100svh-1.25rem)] flex-col overflow-hidden rounded-[20px] bg-mint-300 text-forest-900 sm:min-h-[calc(100dvh-2rem)] sm:rounded-[28px]">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-[42%] left-1/2 h-[95%] w-[130%] -translate-x-1/2 rounded-[50%] bg-[radial-gradient(closest-side,rgba(255,255,255,0.72),rgba(255,255,255,0))]" />
        <div className="absolute inset-x-0 bottom-0 h-[55%] bg-gradient-to-b from-transparent to-mint-400/50" />
      </div>

      <Reveal y={-8} className="relative z-20">
        <nav className="flex items-center justify-between gap-3 px-4 pt-4 sm:px-7 sm:pt-6" aria-label="Main">
          <Logo className="pl-1" />
          <div className="flex items-center gap-1 sm:gap-2">
            <LanguageSwitcher className="border-transparent bg-white/35" />
            <ButtonLink href="#principles" variant="ghost" className="hidden sm:inline-flex">
              {t("howItWorks")}
            </ButtonLink>
            <ButtonLink href="/auth" variant="outline">
              <LogIn aria-hidden />
              {t("signIn")}
            </ButtonLink>
          </div>
        </nav>
      </Reveal>

      <div className="relative z-20 flex flex-1 flex-col items-center justify-center px-5 pt-10 pb-2 text-center sm:px-8 sm:pt-8">
        <Reveal delay={0.08}>
          <p className="inline-flex max-w-full items-center gap-2 rounded-full border border-forest-900/10 bg-white/65 px-3 py-2 text-xs font-medium text-forest-900 shadow-sm shadow-forest-900/5 backdrop-blur-sm sm:text-sm">
            <Trophy className="size-4 shrink-0 text-clay-600" aria-hidden />
            <span>{t("builtFor")}</span>
            <span aria-label="Google" className="shrink-0 font-semibold">
              <span className="text-[#4285f4]">G</span>
              <span className="text-[#ea4335]">o</span>
              <span className="text-[#fbbc05]">o</span>
              <span className="text-[#4285f4]">g</span>
              <span className="text-[#34a853]">l</span>
              <span className="text-[#ea4335]">e</span>
            </span>
            <span>AI Builder Cup</span>
            <span className="font-mono text-[10px] text-forest-600">2026</span>
          </p>
        </Reveal>

        <RevealText
          text={titleLead}
          accent={titleAccent}
          accentClassName="bg-[linear-gradient(transparent_56%,rgba(227,163,95,0.6)_56%,rgba(227,163,95,0.6)_88%,transparent_88%)] bg-left bg-no-repeat"
          className={cn(
            "mt-7 font-medium text-balance sm:mt-8",
            longTitle
              ? "max-w-[14em] text-[clamp(2.3rem,min(9vw,8.5svh),4.75rem)] leading-[1] tracking-[-0.035em]"
              : "max-w-[10em] text-[clamp(2.75rem,min(12vw,10.5svh),5.75rem)] leading-[0.95] tracking-[-0.04em]",
            indicScript && "leading-[1.18] tracking-normal",
          )}
          delay={0.15}
        />

        <Reveal delay={0.6} className="mt-5">
          <p className="mx-auto max-w-[37ch] text-[15px] leading-snug text-forest-900/75 sm:text-base">
            {t("heroDescription")}
          </p>
        </Reveal>

        <Reveal delay={0.9} className="mt-8 flex w-full flex-col items-center gap-3 sm:mt-9">
          <PillLink
            href="/auth"
            className="h-[76px] w-full max-w-[360px] justify-between gap-5 whitespace-nowrap pr-2 pl-7 text-lg shadow-[0_14px_30px_rgba(22,54,38,0.18)] transition-transform hover:-translate-y-0.5 [&_span]:size-14 [&_span_svg]:size-6"
          >
            {t("startReport")}
          </PillLink>
          <ButtonLink href="/report" variant="ghost" size="md" className="gap-2 text-forest-900/70">
            {t("tryGuest")}
            <ArrowRight className="transition-transform group-hover:translate-x-0.5" aria-hidden />
          </ButtonLink>
        </Reveal>
      </div>

      <div aria-hidden className="pointer-events-none relative z-10 -mt-10 h-[30svh] min-h-48 sm:-mt-20 sm:h-[34svh]">
        <motion.div
          className="absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.6, delay: 0.3 }}
        >
          <FieldRows className="absolute inset-0 [mask-image:radial-gradient(ellipse_80%_95%_at_50%_100%,black_35%,transparent_88%)]" />
        </motion.div>
        <Reveal delay={1.2} className="absolute top-[38%] right-4 sm:right-[12%] xl:hidden">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-xs font-medium shadow-sm shadow-forest-900/10 backdrop-blur-sm">
            <span className="size-2 rounded-full bg-clay-500" />
            {t("likely")} · {t("heroSampleCause")}
          </span>
        </Reveal>
        <Reveal delay={1.35} className="absolute bottom-[14%] left-4 sm:left-[12%] xl:hidden">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1.5 font-mono text-xs font-medium shadow-sm shadow-forest-900/10 backdrop-blur-sm">
            <CloudSun className="size-3.5" />
            {SAMPLE_WEATHER} · {SAMPLE_HUMIDITY}
          </span>
        </Reveal>
      </div>

      <div aria-hidden className="pointer-events-none absolute inset-0 z-10 hidden xl:block">
        <PreviewCard className="top-[46%] left-[4%] w-52 2xl:w-60" delay={1.1} tilt={-3}>
          <div className="flex items-center gap-3.5">
            <div className="relative h-16 w-12 shrink-0 overflow-hidden rounded-xl bg-mint-200">
              <LeafIllustration className="absolute inset-0 m-auto h-14 text-forest-700" />
              <motion.span
                className="absolute inset-x-0 top-0 h-4 bg-gradient-to-b from-transparent via-clay-400/80 to-transparent"
                initial={{ y: "-100%" }}
                animate={{ y: ["-100%", "400%"] }}
                transition={{ duration: 2.2, ease: "easeInOut", repeat: Infinity, repeatDelay: 0.5 }}
              />
            </div>
            <div className="min-w-0">
              <p className="label-caps text-forest-600">{t("photograph")}</p>
              <p className="mt-1 text-sm leading-snug font-medium">{t("heroScanLabel")}</p>
            </div>
          </div>
        </PreviewCard>

        <PreviewCard className="top-[67%] left-[10%] w-56" delay={1.3} tilt={2}>
          <p className="label-caps flex items-center gap-1.5 text-forest-600">
            <CloudSun className="size-3.5" />
            {t("recentWeather")}
          </p>
          <p className="mt-2 flex items-center gap-2 font-mono text-lg font-medium tracking-tight">
            {SAMPLE_WEATHER}
            <span className="inline-flex items-center gap-0.5 text-forest-700">
              <Droplets className="size-4" />
              {SAMPLE_HUMIDITY}
            </span>
          </p>
          <p className="mt-0.5 text-xs text-forest-700/80">{t("heroSampleWeather")}</p>
        </PreviewCard>

        <PreviewCard className="top-[44%] right-[4%] w-52 2xl:w-60" delay={1.2} tilt={3}>
          <div className="flex items-center justify-between gap-3">
            <p className="label-caps text-forest-600">{t("likely")}</p>
            <span className="relative flex size-2.5">
              <span className="absolute inset-0 animate-ping rounded-full bg-clay-500/60" />
              <span className="relative size-2.5 rounded-full bg-clay-500" />
            </span>
          </div>
          <p className="mt-1.5 text-xl leading-tight font-medium">{t("heroSampleCause")}</p>
          <div className="mt-3 flex items-center gap-2">
            <span className="flex gap-1">
              {[0, 1, 2].map((step) => (
                <span key={step} className={cn("h-1.5 w-5 rounded-full", step < 2 ? "bg-forest-700" : "bg-forest-900/15")} />
              ))}
            </span>
            <span className="text-[11px] text-forest-700/80">{t("confidenceMedium")}</span>
          </div>
        </PreviewCard>

        <PreviewCard className="top-[66%] right-[10%] w-64" delay={1.4} tilt={-2}>
          <p className="label-caps flex items-center gap-1.5 text-forest-600">
            <ListChecks className="size-3.5" />
            {t("doNext")}
          </p>
          <p className="mt-2 flex items-start gap-2 text-sm leading-snug font-medium">
            <span className="mt-0.5 grid size-4 shrink-0 place-items-center rounded-full bg-forest-900 text-mint-100">
              <Check className="size-2.5" strokeWidth={3.5} />
            </span>
            {t("heroSampleAction")}
          </p>
        </PreviewCard>
      </div>
    </div>
  );
}
