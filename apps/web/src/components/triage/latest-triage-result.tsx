"use client";

import { LeafIllustration } from "@/components/brand/botanical";
import { PillLink } from "@/components/brand/pill";
import { Reveal } from "@/components/motion/reveal";
import { TriageResult } from "@/components/triage/triage-result";
import { Skeleton } from "@/components/ui/skeleton";
import { useLatestTriage } from "@/hooks/use-latest-triage";

export function LatestTriageResult() {
  const stored = useLatestTriage();

  if (stored.state === "loading") {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-6 px-5 pt-12" aria-busy="true" aria-label="Loading result">
        <Skeleton className="h-80 w-full rounded-[28px] bg-forest-900/10" />
        <Skeleton className="h-40 w-full rounded-3xl bg-forest-900/5" />
      </div>
    );
  }

  if (stored.state === "missing") {
    return (
      <Reveal className="mx-auto flex max-w-md flex-1 flex-col items-center justify-center gap-6 px-5 py-20 text-center">
        <LeafIllustration className="h-40 text-forest-700/50" />
        <div className="space-y-2">
          <h1 className="text-3xl font-medium tracking-tight">No result yet</h1>
          <p className="text-muted-foreground">
            Results stay in this browser tab for now. Send a report to see its triage here.
          </p>
        </div>
        <PillLink href="/report">Start a crop report</PillLink>
      </Reveal>
    );
  }

  return <TriageResult result={stored.result} />;
}
