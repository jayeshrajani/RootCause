"use client";

import type { ReactNode } from "react";
import { Check, CloudSun, Droplets, ListChecks, Satellite, Trophy } from "lucide-react";
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

/** A small, gently swaying plant to bring the field theme into the hero. */
function AnimatedPlant({ className }: { className?: string }) {
  return (
    <motion.svg
      viewBox="0 0 180 210"
      fill="none"
      className={className}
      aria-hidden="true"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 1.1, ease: EASE, delay: 0.5 }}
    >
      <ellipse cx="90" cy="192" rx="54" ry="8" fill="#214735" fillOpacity=".12" />
      <path d="M63 142h54l-7 43H70l-7-43Z" fill="#C77B52" />
      <path d="M61 140c0-4 13-7 29-7s29 3 29 7-13 7-29 7-29-3-29-7Z" fill="#E3A36A" />
      <path d="M90 139c1-31 0-59 1-91" stroke="#376847" strokeWidth="4" strokeLinecap="round" />
      <motion.g animate={{ rotate: [-2, 3, -2] }} transition={{ duration: 4.2, ease: "easeInOut", repeat: Infinity }} style={{ transformOrigin: "91px 75px" }}>
        <path d="M91 104C58 107 48 85 53 68c21-2 39 9 38 36Z" fill="#6E9A65" stroke="#376847" strokeWidth="2" />
        <path d="M87 99 60 73" stroke="#376847" strokeWidth="1.5" strokeLinecap="round" />
      </motion.g>
      <motion.g animate={{ rotate: [2, -3, 2] }} transition={{ duration: 4.8, ease: "easeInOut", repeat: Infinity }} style={{ transformOrigin: "91px 61px" }}>
        <path d="M92 81c1-30 22-40 42-32 1 22-12 38-42 32Z" fill="#83A875" stroke="#376847" strokeWidth="2" />
        <path d="m98 77 28-23" stroke="#376847" strokeWidth="1.5" strokeLinecap="round" />
      </motion.g>
      <motion.g animate={{ rotate: [-3, 2, -3] }} transition={{ duration: 5.1, ease: "easeInOut", repeat: Infinity }} style={{ transformOrigin: "91px 52px" }}>
        <path d="M91 61C73 48 76 29 90 18c17 11 20 28 1 43Z" fill="#A2B986" stroke="#376847" strokeWidth="2" />
        <path d="m91 55-1-29" stroke="#376847" strokeWidth="1.5" strokeLinecap="round" />
      </motion.g>
      <path d="M75 153h30" stroke="#E7A477" strokeWidth="2" strokeLinecap="round" />
    </motion.svg>
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
            <ButtonLink href="#under-the-hood" variant="ghost" className="hidden sm:inline-flex">
              {t("howItWorks")}
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
            href="/report"
            className="h-[76px] w-full max-w-[360px] justify-between gap-5 whitespace-nowrap pr-2 pl-7 text-lg shadow-[0_14px_30px_rgba(22,54,38,0.18)] transition-transform hover:-translate-y-0.5 [&_span]:size-14 [&_span_svg]:size-6"
          >
            {t("startReport")}
          </PillLink>
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
        <AnimatedPlant className="absolute bottom-[-2%] left-1/2 z-10 h-[88%] w-auto -translate-x-1/2 drop-shadow-[0_12px_12px_rgba(22,54,38,0.10)] sm:h-[100%] xl:h-[78%]" />
        <Reveal delay={1.35} className="absolute bottom-[14%] left-4 sm:left-[12%] xl:hidden">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1.5 font-mono text-xs font-medium shadow-sm shadow-forest-900/10 backdrop-blur-sm">
            <CloudSun className="size-3.5" />
            {SAMPLE_WEATHER} · {SAMPLE_HUMIDITY}
          </span>
        </Reveal>
      </div>

      <div aria-hidden className="pointer-events-none absolute inset-0 z-10 hidden xl:block">
        <PreviewCard className="top-[42%] left-[3%] w-[17rem] 2xl:left-[6%]" delay={1.1} tilt={-3}>
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
              <p className="label-caps text-forest-600">{t("heroScanTag")}</p>
              <p className="mt-1 text-sm leading-snug font-medium text-balance">{t("heroScanLabel")}</p>
            </div>
          </div>
        </PreviewCard>

        <PreviewCard className="top-[64%] left-[6%] w-56 2xl:left-[10%]" delay={1.3} tilt={2}>
          <p className="label-caps flex items-center gap-1.5 text-forest-600">
            <CloudSun className="size-3.5" />
            {t("heroWeatherTag")}
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

        <PreviewCard className="top-[30%] right-[3%] w-56 2xl:right-[6%]" delay={1.2} tilt={2.5}>
          <p className="label-caps flex items-center gap-1.5 text-forest-600">
            <Satellite className="size-3.5" />
            {t("heroSatTag")}
          </p>
          <div className="mt-2 flex items-end justify-between gap-3">
            <p className="font-mono text-lg font-medium tracking-tight">
              0.41 <span className="text-sm text-clay-600">↓ 9%</span>
            </p>
            <svg viewBox="0 0 80 28" className="h-7 w-20" aria-hidden>
              <motion.path
                d="M2 6 L14 8 L26 7 L38 11 L50 14 L62 19 L78 23"
                fill="none"
                stroke="#a8621f"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1.6, delay: 1.6, ease: EASE }}
              />
            </svg>
          </div>
          <p className="mt-0.5 text-xs text-forest-700/80">{t("heroSatBody")}</p>
        </PreviewCard>

        <PreviewCard className="top-[60%] right-[6%] w-64 2xl:right-[10%]" delay={1.4} tilt={-2}>
          <p className="label-caps flex items-center gap-1.5 text-forest-600">
            <ListChecks className="size-3.5" />
            {t("doNext")}
          </p>
          <div className="mt-2 flex items-center justify-between gap-3 text-sm">
            <span className="font-medium">{t("heroSampleCause")}</span>
            <span className="font-mono text-xs text-forest-700">82/100</span>
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-forest-900/10">
            <motion.div
              className="h-full rounded-full bg-forest-700"
              initial={{ width: 0 }}
              animate={{ width: "82%" }}
              transition={{ duration: 1.2, delay: 1.8, ease: EASE }}
            />
          </div>
          <p className="mt-2.5 flex items-start gap-2 text-sm leading-snug font-medium">
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
