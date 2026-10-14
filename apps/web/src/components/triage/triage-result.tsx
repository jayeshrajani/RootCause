import { FlaskConical } from "lucide-react";

import { PillLink } from "@/components/brand/pill";
import { Reveal } from "@/components/motion/reveal";
import { ActionList } from "@/components/triage/action-list";
import { EvidenceList } from "@/components/triage/evidence-list";
import { DataSourceList, MissingInformationList } from "@/components/triage/info-lists";
import { PossibleCauses } from "@/components/triage/possible-causes";
import { ResultSection } from "@/components/triage/result-section";
import { UrgencyHero } from "@/components/triage/urgency-hero";
import type { TriageResponse } from "@/types/triage";

export function TriageResult({ result }: { result: TriageResponse }) {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-14 px-5 pt-8 pb-10 sm:pt-12">
      <div className="space-y-4">
        {result.analysis_mode === "mock" ? (
          <Reveal y={-6} className="flex items-start gap-3 rounded-2xl border border-clay-400/40 bg-clay-400/10 px-4 py-3 text-sm">
            <FlaskConical className="mt-0.5 size-4 shrink-0 text-clay-600" aria-hidden />
            <p>
              <span className="font-medium text-clay-600">Development preview.</span>{" "}
              <span className="text-forest-900/80">{result.disclaimer}</span>
            </p>
          </Reveal>
        ) : null}
        <UrgencyHero result={result} />
      </div>

      <ResultSection id="actions" index={1} title="What to do next" note="Ordered by urgency.">
        <ActionList actions={result.recommended_actions} />
      </ResultSection>

      <ResultSection
        id="causes"
        index={2}
        title="Possible causes"
        note="Hypotheses to check, not a diagnosis."
      >
        <PossibleCauses causes={result.possible_causes} />
      </ResultSection>

      <ResultSection
        id="evidence"
        index={3}
        title="Evidence"
        note="What was observed, and which sources had no data."
      >
        <EvidenceList evidence={result.evidence} />
      </ResultSection>

      <ResultSection
        id="missing"
        index={4}
        title="What would make this clearer"
        note="Add these to a new report for a more certain triage."
      >
        <MissingInformationList items={result.missing_information} />
      </ResultSection>

      <ResultSection id="sources" index={5} title="Sources">
        <DataSourceList sources={result.data_sources} />
      </ResultSection>

      <Reveal onView className="flex flex-col items-start gap-4 border-t border-forest-900/10 pt-10 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-2xl font-medium tracking-tight">Seen something new in the field?</p>
        <PillLink href="/report">Start a new report</PillLink>
      </Reveal>
    </div>
  );
}
