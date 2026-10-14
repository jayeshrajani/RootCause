import type { Metadata } from "next";

import { ReportWizard } from "@/components/farmer/report-wizard";

export const metadata: Metadata = { title: "New report" };

export default function ReportPage() {
  return <ReportWizard />;
}
