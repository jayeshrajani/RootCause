import { UserCheck } from "lucide-react";

import { PRIORITY_DISPLAY } from "@/components/triage/display";
import { cn } from "@/lib/utils";
import type { RecommendedAction } from "@/types/triage";

export function ActionList({ actions }: { actions: RecommendedAction[] }) {
  const sorted = [...actions].sort(
    (a, b) => PRIORITY_DISPLAY[a.priority].order - PRIORITY_DISPLAY[b.priority].order,
  );

  return (
    <ol className="space-y-3">
      {sorted.map((action, index) => {
        const priority = PRIORITY_DISPLAY[action.priority];
        return (
          <li
            key={action.action}
            className="group grid grid-cols-[2.25rem_1fr] gap-4 rounded-3xl border border-forest-900/10 bg-card p-5 transition-colors hover:border-forest-900/25 sm:p-6"
          >
            <span className="flex size-9 items-center justify-center rounded-full bg-mint-100 font-mono text-sm text-forest-700">
              {index + 1}
            </span>
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span className="label-caps inline-flex items-center gap-2 text-forest-700">
                  <span className={cn("size-1.5 rounded-full", priority.dot)} aria-hidden />
                  {priority.label}
                </span>
                {action.requires_expert_verification ? (
                  <span className="label-caps inline-flex items-center gap-1.5 text-forest-600">
                    <UserCheck className="size-3.5" aria-hidden />
                    Confirm with an expert
                  </span>
                ) : null}
              </div>
              <p className="text-lg leading-snug font-medium">{action.action}</p>
              <p className="text-sm text-muted-foreground">{action.rationale}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
