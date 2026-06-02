import { Clock, FileCode, GitCommitHorizontal, ScrollText } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  fileName,
  fmtInterval,
  fmtNumber,
  fmtPct,
  fmtSigned,
  qualityVariant,
} from "@/lib/format";
import type { Author, TimelineCommit } from "@/lib/types";
import { ConfidenceBadge, Metric } from "./primitives";
import { IntegritySignals } from "./evidence/IntegritySignals";
import { InstructorReview } from "./InstructorReview";

export function ContributorDetail({
  author,
  timeline,
  analysisId,
}: {
  author: Author;
  timeline: TimelineCommit[];
  analysisId?: number;
}) {
  const attr = author.attribution ?? author.stats.attribution ?? {};
  const quality = author.quality;
  const flags = author.integrity_flags ?? [];
  const commits = timeline.filter((c) => c.author === author.author);
  const files = author.stats.files ?? [];

  return (
    <div className="space-y-6 border-t border-border bg-background/40 px-4 py-5">
      {/* Why this verdict */}
      {author.explanation && (
        <section className="rounded-md border border-border bg-card p-3">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <h4 className="flex items-center gap-2 text-sm font-semibold">
              <ScrollText className="size-4 text-muted-foreground" />
              Why this verdict
            </h4>
            <ConfidenceBadge
              confidence={author.explanation.confidence}
              regime={author.explanation.regime}
            />
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {author.explanation.summary}
          </p>
          {author.explanation.caveats && author.explanation.caveats.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {author.explanation.caveats.map((c, i) => (
                <li key={i} className="text-[11px] text-muted-foreground/80">
                  • {c}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Attribution breakdown */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric
          label="Ownership"
          value={fmtInterval(author.ownership_interval, author.ownership_pct)}
          sub={`${fmtNumber(attr.owned_lines)} lines · ${attr.owned_files ?? 0} files · 90% CI`}
          tip="Surviving lines owned at HEAD (git blame), reported as a 90% confidence interval."
        />
        <Metric
          label="Effort (churn)"
          value={fmtPct(author.effort_pct)}
          sub={`+${fmtNumber(attr.effort_added)} / -${fmtNumber(attr.effort_deleted)}`}
          tip="Authored insertions/deletions over history — work done, regardless of whether it survived."
        />
        <Metric
          label="Divergence"
          value={fmtSigned(author.divergence)}
          sub="effort − ownership"
          tone={(author.divergence ?? 0) > 20 ? "warning" : "default"}
          tip="High positive divergence means churn that did not survive into the final codebase."
        />
        <Metric
          label="Code quality"
          value={author.quality_score == null ? "Not assessed" : author.quality_score.toFixed(1)}
          tone={qualityVariant(author.quality_score)}
          sub={
            quality?.assessed
              ? `${quality.functions ?? 0} fns · avg CC ${quality.avg_cc ?? "—"}${
                  quality.complex_functions ? ` · ${quality.complex_functions} complex` : ""
                }`
              : undefined
          }
          tip="Blended complexity + maintainability over owned code. Not assessed when no supported source is owned."
        />
      </section>

      {/* Integrity signals */}
      <IntegritySignals flags={flags} />

      {/* Instructor review */}
      {analysisId != null && (
        <InstructorReview
          analysisId={analysisId}
          author={author.author}
          systemRole={author.role}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Files */}
        <section>
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <FileCode className="size-4 text-muted-foreground" />
            Files modified ({files.length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {files.slice(0, 14).map((f, i) => (
              <span
                key={i}
                title={f}
                className="max-w-[180px] truncate rounded border border-border bg-muted/40 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground"
              >
                {fileName(f)}
              </span>
            ))}
            {files.length > 14 && (
              <span className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
                +{files.length - 14} more
              </span>
            )}
            {files.length === 0 && (
              <span className="text-xs text-muted-foreground">No file data.</span>
            )}
          </div>
        </section>

        {/* Commit history */}
        <section>
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Clock className="size-4 text-muted-foreground" />
            Commit history ({commits.length})
          </h4>
          <ScrollArea className="h-52 rounded-md border border-border">
            <ul className="divide-y divide-border">
              {commits.map((c, i) => (
                <li key={i} className="px-3 py-2">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-medium">{c.msg}</span>
                    <time className="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {c.date}
                    </time>
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-[11px]">
                    <span className="text-success-foreground">+{c.insertions}</span>
                    <span className="text-danger-foreground">-{c.deletions}</span>
                    {c.files?.length > 0 && (
                      <span className="text-muted-foreground">
                        <GitCommitHorizontal className="mr-0.5 inline size-3" />
                        {c.files.length} file{c.files.length === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                </li>
              ))}
              {commits.length === 0 && (
                <li className="px-3 py-4 text-xs text-muted-foreground">
                  No commit details available.
                </li>
              )}
            </ul>
          </ScrollArea>
        </section>
      </div>
    </div>
  );
}
