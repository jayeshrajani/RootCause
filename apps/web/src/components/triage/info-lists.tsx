import { DATA_SOURCE_STATUS_DISPLAY, formatTimestamp, SOURCE_DISPLAY } from "@/components/triage/display";
import { cn } from "@/lib/utils";
import type { DataSource, MissingInformation } from "@/types/triage";

export function MissingInformationList({ items }: { items: MissingInformation[] }) {
  if (!items.length) {
    return <p className="text-muted-foreground">No gaps were identified.</p>;
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {items.map((item) => (
        <li key={item.item} className="rounded-3xl border border-dashed border-forest-900/25 p-5">
          <p className="font-medium leading-snug">{item.item}</p>
          <p className="mt-1.5 text-sm text-muted-foreground">{item.reason}</p>
        </li>
      ))}
    </ul>
  );
}

export function DataSourceList({ sources }: { sources: DataSource[] }) {
  return (
    <ul className="divide-y divide-forest-900/10 border-y border-forest-900/10">
      {sources.map((source) => {
        const status = DATA_SOURCE_STATUS_DISPLAY[source.status];
        const Icon = SOURCE_DISPLAY[source.kind].icon;
        return (
          <li key={source.id} className="grid grid-cols-[1.25rem_1fr] gap-x-4 gap-y-1 py-4 sm:grid-cols-[1.25rem_1fr_auto]">
            <Icon className="mt-0.5 size-4 text-forest-900/50" aria-hidden />
            <div className="min-w-0">
              <p className="text-sm font-medium">{source.name}</p>
              <p className="text-xs text-muted-foreground">{source.description}</p>
              {source.retrieved_at ? (
                <p className="font-mono text-[11px] text-muted-foreground">
                  Retrieved <time dateTime={source.retrieved_at}>{formatTimestamp(source.retrieved_at)}</time>
                </p>
              ) : null}
            </div>
            <p className="col-start-2 flex items-center gap-2 text-xs text-forest-700 sm:col-start-3 sm:justify-end">
              <span className={cn("size-1.5 rounded-full", status.dot)} aria-hidden />
              {status.label}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
