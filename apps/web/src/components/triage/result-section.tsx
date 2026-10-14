import type { ReactNode } from "react";

import { Reveal } from "@/components/motion/reveal";

interface ResultSectionProps {
  id: string;
  index: number;
  title: string;
  note?: string;
  children: ReactNode;
}

export function ResultSection({ id, index, title, note, children }: ResultSectionProps) {
  return (
    <section aria-labelledby={id} className="grid gap-6 border-t border-forest-900/10 pt-8 lg:grid-cols-[15rem_1fr] lg:gap-12">
      <Reveal onView className="lg:sticky lg:top-24 lg:self-start">
        <p className="font-mono text-xs text-forest-500">{String(index).padStart(2, "0")}</p>
        <h2 id={id} className="mt-2 text-2xl font-medium tracking-tight">
          {title}
        </h2>
        {note ? <p className="mt-1.5 text-sm text-muted-foreground">{note}</p> : null}
      </Reveal>
      <Reveal onView delay={0.1}>
        {children}
      </Reveal>
    </section>
  );
}
