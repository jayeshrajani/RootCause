import { Camera } from "lucide-react";

import { PillLink } from "@/components/brand/pill";
import { Reveal } from "@/components/motion/reveal";
import { ActionList } from "@/components/triage/action-list";
import { CropCheck } from "@/components/triage/crop-check";
import { PossibleCauses } from "@/components/triage/possible-causes";
import { QuickChecks } from "@/components/triage/quick-checks";
import { ResultTabs } from "@/components/triage/result-tabs";
import { SummaryCard } from "@/components/triage/summary-card";
import type { TriageResponse } from "@/types/triage";
import { useI18n } from "@/lib/i18n";

export function TriageResult({ result }: { result: TriageResponse }) {
  const { t } = useI18n();
  return (
    <div className="mx-auto w-full max-w-6xl px-5 pt-6 pb-12 sm:pt-10">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-10">
        <div className="lg:sticky lg:top-24 lg:max-h-[calc(100dvh-7rem)] lg:self-start lg:overflow-y-auto lg:rounded-[28px] lg:[scrollbar-width:none]">
          <SummaryCard result={result} />
        </div>

        <Reveal delay={0.15} className="min-w-0">
          <CropCheck key={result.report_id} result={result} />
          {result.status === "insufficient_information" ? (
            <div className="mb-3 flex items-start gap-3 rounded-2xl border border-clay-400/40 bg-clay-400/10 px-4 py-3 text-sm">
              <Camera className="mt-0.5 size-4 shrink-0 text-clay-600" aria-hidden />
              <p>
                <span className="font-medium text-clay-600">{t("insufficientTitle")}</span>{" "}
                {t("insufficientBody")}
              </p>
            </div>
          ) : null}

          <ResultTabs
            tabs={[
              {
                id: "causes",
                label: t("causes"),
                count: result.possible_causes.length,
                content: (
                  <div className="space-y-7">
                    <PossibleCauses causes={result.possible_causes} />
                    <QuickChecks items={result.missing_information} />
                  </div>
                ),
              },
              {
                id: "next",
                label: t("doNext"),
                count: result.recommended_actions.length,
                content: <ActionList actions={result.recommended_actions} />,
              },
            ]}
          />

          <div className="mt-8 flex flex-col items-start gap-3 border-t border-forest-900/10 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="font-medium">{t("seenSomethingNew")}</p>
            <PillLink href="/report">{t("newReport")}</PillLink>
          </div>
        </Reveal>
      </div>
    </div>
  );
}
