import { formatTimestamp, AVAILABILITY_DISPLAY, SOURCE_DISPLAY } from "@/components/triage/display";
import { cn } from "@/lib/utils";
import type { Evidence } from "@/types/triage";

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  return (
    <ul className="divide-y divide-forest-900/10 rounded-3xl border border-forest-900/10 bg-card">
      {evidence.map((item) => {
        const source = SOURCE_DISPLAY[item.source];
        const availability = AVAILABILITY_DISPLAY[item.availability];
        const observed = item.availability === "available";
        const Icon = source.icon;
        return (
          <li key={item.id} className="flex gap-4 p-5 sm:p-6">
            <span
              className={cn(
                "flex size-10 shrink-0 items-center justify-center rounded-full",
                observed ? "bg-mint-200 text-forest-900" : "border border-dashed border-forest-900/25 text-forest-900/40",
              )}
            >
              <Icon className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">{source.label}</p>
                <span className={cn("rounded-full px-2.5 py-0.5 text-xs", availability.className)}>
                  {availability.label}
                </span>
              </div>
              <p className={cn("text-sm leading-relaxed", !observed && "text-muted-foreground")}>
                {item.observation}
              </p>
              {item.observed_at ? (
                <p className="font-mono text-[11px] text-muted-foreground">
                  <time dateTime={item.observed_at}>{formatTimestamp(item.observed_at)}</time>
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
