import type { Metadata } from "next";

import { AppFooterNote } from "@/components/app/app-header";
import { LatestTriageResult } from "@/components/triage/latest-triage-result";

export const metadata: Metadata = { title: "Triage result" };

export default function ResultsPage() {
  return (
    <>
      <LatestTriageResult />
      <AppFooterNote />
    </>
  );
}
