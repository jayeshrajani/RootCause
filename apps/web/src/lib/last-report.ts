import type { ReportFormValues } from "@/lib/schemas/report";

// Kept in memory only, so photos never touch storage; lost on page reload.
let lastReport: ReportFormValues | null = null;

export function rememberReport(values: ReportFormValues): void {
  lastReport = values;
}

export function recallReport(): ReportFormValues | null {
  return lastReport;
}
