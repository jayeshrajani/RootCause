import { BotanicalPattern, LeafIllustration } from "@/components/brand/botanical";
import { Logo } from "@/components/brand/logo";
import { PillLink } from "@/components/brand/pill";
import { LandingHero } from "@/components/landing/landing-hero";
import { Reveal, Stagger, StaggerItem } from "@/components/motion/reveal";

const PRINCIPLES = [
  {
    title: "Observed",
    body: "What your photos and words actually show, kept apart from any guess.",
  },
  {
    title: "Suspected",
    body: "Possible causes with their confidence, and the evidence that argues against them.",
  },
  {
    title: "Missing",
    body: "What would make the picture clearer, so you know exactly what to check.",
  },
  {
    title: "Next steps",
    body: "Safe actions ranked by urgency, flagged when an expert should confirm.",
  },
];

const STEPS = [
  {
    title: "Photograph",
    body: "Up to three close-ups of the affected leaves, stems or fruit.",
  },
  {
    title: "Describe",
    body: "Tap the symptoms you see, add a few words, and roughly where the field is.",
  },
  {
    title: "Triage",
    body: "See how urgent it looks, what it might be, and what to do next.",
  },
];

export default function HomePage() {
  return (
    <main className="flex-1">
      <div className="relative bg-forest-900 p-2.5 sm:p-4">
        <BotanicalPattern className="text-mint-300/[0.09]" />
        <LandingHero />
      </div>

      <section id="principles" className="mx-auto max-w-6xl scroll-mt-6 px-5 py-24 sm:px-8 sm:py-32">
        <div className="grid gap-12 lg:grid-cols-[1fr_1.4fr]">
          <Reveal onView>
            <p className="label-caps text-forest-600">The RootCause method</p>
            <h2 className="mt-4 text-4xl leading-[1.02] font-medium tracking-[-0.03em] sm:text-5xl">
              A triage,
              <br />
              not a verdict.
            </h2>
          </Reveal>
          <Stagger className="grid gap-px overflow-hidden rounded-3xl border bg-border sm:grid-cols-2">
            {PRINCIPLES.map((item, index) => (
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
              <p className="label-caps text-forest-600">Two minutes, three steps</p>
            </Reveal>
            <Stagger className="mt-8 divide-y divide-forest-900/15 border-y border-forest-900/15">
              {STEPS.map((step, index) => (
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
              Something wrong in the field?
            </h2>
            <p className="max-w-md text-mint-200/80">
              Send a report now. It is free, works on any phone, and never claims more certainty
              than the evidence allows.
            </p>
            <PillLink href="/auth" tone="light">
              Start a crop report
            </PillLink>
          </Reveal>
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-10 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <Logo className="text-forest-900" />
        <p className="max-w-md">
          Triage guidance, not a confirmed diagnosis. Check with a local agricultural expert before
          treating crops.
        </p>
        <p>Google AI Builder Cup 2026</p>
      </footer>
    </main>
  );
}
