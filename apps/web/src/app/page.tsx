"use client";

import { BotanicalPattern, LeafIllustration } from "@/components/brand/botanical";
import { Logo } from "@/components/brand/logo";
import { PillLink } from "@/components/brand/pill";
import { LandingHero } from "@/components/landing/landing-hero";
import { Reveal, Stagger, StaggerItem } from "@/components/motion/reveal";
import { useI18n } from "@/lib/i18n";

export default function HomePage() {
  const { t } = useI18n();
  const principles = [
    { title: t("observed"), body: t("observedBody") },
    { title: t("suspected"), body: t("suspectedBody") },
    { title: t("missing"), body: t("missingBody") },
    { title: t("nextSteps"), body: t("nextStepsBody") },
  ];
  const steps = [
    { title: t("photograph"), body: t("photographBody") },
    { title: t("describe"), body: t("describeBody") },
    { title: t("triage"), body: t("triageBody") },
  ];
  return (
    <main className="flex-1">
      <div className="relative bg-forest-900 p-2.5 sm:p-4">
        <BotanicalPattern className="text-mint-300/[0.09]" />
        <LandingHero />
      </div>

      <section id="principles" className="mx-auto max-w-6xl scroll-mt-6 px-5 py-24 sm:px-8 sm:py-32">
        <div className="grid gap-12 lg:grid-cols-[1fr_1.4fr]">
          <Reveal onView>
            <p className="label-caps text-forest-600">{t("method")}</p>
            <h2 className="mt-4 text-4xl leading-[1.02] font-medium tracking-[-0.03em] sm:text-5xl">
              {t("triageNotVerdict")}
            </h2>
          </Reveal>
          <Stagger className="grid gap-px overflow-hidden rounded-3xl border bg-border sm:grid-cols-2">
            {principles.map((item, index) => (
              <StaggerItem key={item.title} className="bg-card p-6 sm:p-8">
                <p className="font-mono text-xs text-forest-500">0{index + 1}</p>
                <h3 className="mt-6 text-xl font-medium">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.body}</p>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <section className="border-y bg-mint-100/60">
        <div className="mx-auto grid max-w-6xl gap-12 px-5 py-24 sm:px-8 sm:py-28 lg:grid-cols-[1.4fr_1fr] lg:items-center">
          <div>
            <Reveal onView>
              <p className="label-caps text-forest-600">{t("threeSteps")}</p>
            </Reveal>
            <Stagger className="mt-8 divide-y divide-forest-900/15 border-y border-forest-900/15">
              {steps.map((step, index) => (
                <StaggerItem
                  key={step.title}
                  className="grid grid-cols-[4.5rem_1fr] items-baseline gap-4 py-7 sm:grid-cols-[7rem_1fr]"
                >
                  <span className="text-5xl font-extralight tracking-tight text-forest-500 sm:text-6xl">
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="text-2xl font-medium tracking-tight">{step.title}</h3>
                    <p className="mt-1 text-muted-foreground">{step.body}</p>
                  </div>
                </StaggerItem>
              ))}
            </Stagger>
          </div>
          <Reveal onView delay={0.2} className="hidden justify-center lg:flex">
            <LeafIllustration className="h-[420px] text-forest-700/70" />
          </Reveal>
        </div>
      </section>

      <section className="px-2.5 py-2.5 sm:px-4 sm:py-4">
        <div className="relative overflow-hidden rounded-[20px] bg-forest-900 px-6 py-20 text-mint-100 sm:rounded-[28px] sm:px-12 sm:py-28">
          <BotanicalPattern className="text-mint-300/[0.07]" />
          <Reveal onView className="relative mx-auto flex max-w-3xl flex-col items-center gap-8 text-center">
            <h2 className="text-4xl leading-[1.02] font-medium tracking-[-0.03em] sm:text-6xl">
              {t("fieldProblem")}
            </h2>
            <p className="max-w-md text-mint-200/80">
              {t("landingCtaBody")}
            </p>
            <PillLink href="/report" tone="light">
              {t("startReport")}
            </PillLink>
          </Reveal>
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-10 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <Logo className="text-forest-900" />
        <p className="max-w-md">
          {t("footerDisclaimer")}
        </p>
        <p>Leaf by leaf. Field by field.</p>
      </footer>
    </main>
  );
}
