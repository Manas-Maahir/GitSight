import { Download } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { downloadCsv } from "@/lib/export";
import type { AnalysisResult } from "@/lib/types";
import { ContributionChart } from "./ContributionChart";
import { ContributorTable } from "./ContributorTable";
import { OwnershipEffortChart } from "./OwnershipEffortChart";
import { RepoSummaryHeader } from "./RepoSummaryHeader";
import { TrustBanner } from "./TrustBanner";
import { EmptyState } from "./states";

/** Header action: exposed to AppShell so it sits in the top bar. */
export function DashboardActions({ data }: { data: AnalysisResult }) {
  return (
    <Button variant="outline" size="sm" onClick={() => downloadCsv(data)}>
      <Download />
      Export CSV
    </Button>
  );
}

export function DashboardView({ data }: { data: AnalysisResult }) {
  // Cross-highlight key shared by the charts and the contributor table.
  const [activeKey, setActiveKey] = useState<string | null>(null);

  if (!data.authors.length) {
    return (
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6">
        <RepoSummaryHeader data={data} />
        <div className="mt-6">
          <EmptyState
            title="No contributors to analyse"
            body="This repository has no commit history that could be attributed — it may be empty, a fresh fork, or contain only merge commits."
          />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6">
      <RepoSummaryHeader data={data} />

      <div className="mt-6 space-y-4">
        <TrustBanner data={data} />

        <div className="grid gap-4 lg:grid-cols-2">
          <ContributionChart
            authors={data.authors}
            activeKey={activeKey}
            onHover={setActiveKey}
          />
          <OwnershipEffortChart
            authors={data.authors}
            activeKey={activeKey}
            onHover={setActiveKey}
          />
        </div>

        <div className="pt-2">
          <ContributorTable
            authors={data.authors}
            timeline={data.timeline}
            analysisId={data.analysis_id}
            activeKey={activeKey}
            onHover={setActiveKey}
          />
        </div>
      </div>
    </div>
  );
}
