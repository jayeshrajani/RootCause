import { ShieldAlert } from "lucide-react";

import { PRIORITY_DISPLAY } from "@/components/triage/display";
import { cn } from "@/lib/utils";
import type { RecommendedAction } from "@/types/triage";

export function ActionList({ actions }: { actions: RecommendedAction[] }) {
  const sorted = [...actions].sort(
    (a, b) => PRIORITY_DISPLAY[a.priority].order - PRIORITY_DISPLAY[b.priority].order,
  );

  if (!sorted.length) {
    return <p className="text-muted-foreground">No specific steps came out of this report.</p>;
  }

  return (
    <ol className="space-y-2.5">
      {sorted.map((action, index) => {
        const priority = PRIORITY_DISPLAY[action.priority];
        return (
          <li
            key={action.action}
            className="grid grid-cols-[2rem_1fr] gap-3 rounded-2xl border border-forest-900/10 bg-card p-4 sm:gap-4 sm:px-5"
          >
            <span className="flex size-8 items-center justify-center rounded-full bg-mint-100 font-mono text-xs text-forest-700">
              {index + 1}
            </span>
            <div className="min-w-0 space-y-1.5">
              <p className="label-caps flex items-center gap-2 text-forest-700">
                <span className={cn("size-1.5 rounded-full", priority.dot)} aria-hidden />
                {priority.label}
              </p>
              <p className="leading-snug font-medium">{action.action}</p>
              <p className="text-sm text-muted-foreground">{action.rationale}</p>
              {action.addresses || action.requires_expert_verification ? (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {action.addresses ? (
                    <span className="rounded-full bg-mint-100 px-2.5 py-1 text-xs text-forest-700">
                      For: {action.addresses}
                    </span>
                  ) : null}
                  {action.requires_expert_verification ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-clay-400/15 px-2.5 py-1 text-xs text-clay-600">
                      <ShieldAlert className="size-3" aria-hidden />
                      Check product and dose locally
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
