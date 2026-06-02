import { GitCommitHorizontal, ShieldAlert, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { fmtNumber, repoLabel } from "@/lib/format";
import type { AnalysisResult } from "@/lib/types";
import { ReliabilityBadge } from "./primitives";

export function RepoSummaryHeader({ data }: { data: AnalysisResult }) {
  const flagged = data.authors.filter(
    (a) => (a.integrity_flags ?? []).length > 0,
  ).length;
  const freeRiders = data.authors.filter((a) => a.role === "Free Rider").length;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="font-mono text-xl font-semibold tracking-tight sm:text-2xl">
          {repoLabel(data.repo)}
        </h1>
        {data.cached && (
          <Badge variant="neutral" title="Served from cache — repository HEAD unchanged">
            cached
          </Badge>
        )}
        {data.truncated && (
          <Badge variant="warning" title="Analysis limited to the most recent commits">
            limited to 1,000 commits
          </Badge>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <GitCommitHorizontal className="size-4" />
          <span className="tnum text-foreground">{fmtNumber(data.total_commits)}</span>
          commits analysed
        </span>
        <Separator orientation="vertical" className="h-4" />
        <span className="inline-flex items-center gap-1.5">
          <Users className="size-4" />
          <span className="tnum text-foreground">{data.authors.length}</span>
          contributors
        </span>
        {(flagged > 0 || freeRiders > 0) && (
          <>
            <Separator orientation="vertical" className="h-4" />
            <span className="inline-flex items-center gap-1.5 text-warning-foreground">
              <ShieldAlert className="size-4" />
              <span className="tnum">{flagged}</span> flagged for review
            </span>
          </>
        )}
        {data.reliability && (
          <>
            <Separator orientation="vertical" className="h-4" />
            <ReliabilityBadge band={data.reliability.band} />
          </>
        )}
      </div>
    </div>
  );
}
