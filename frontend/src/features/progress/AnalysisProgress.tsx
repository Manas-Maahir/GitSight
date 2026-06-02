import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, ArrowLeft, Check, Loader2, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { createJob, pollJob, ApiError } from "@/lib/api";
import { repoLabel } from "@/lib/format";
import type { AnalysisResult, JobStatus, Stage } from "@/lib/types";
import { cn } from "@/lib/utils";

// Shown before the first poll returns; replaced by the backend's own stage list.
const FALLBACK_STAGES: Stage[] = [
  { key: "cloning", label: "Cloning repository", state: "active" },
  { key: "parsing_history", label: "Parsing git history", state: "pending" },
  { key: "attribution", label: "Attribution analysis", state: "pending" },
  { key: "quality", label: "Code quality", state: "pending" },
  { key: "ownership_modeling", label: "Ownership modeling", state: "pending" },
  { key: "integrity", label: "Integrity forensics", state: "pending" },
  { key: "scoring", label: "Scoring contributions", state: "pending" },
  { key: "explaining", label: "Generating explanations", state: "pending" },
];

function progressPct(stages: Stage[], done: boolean): number {
  if (done) return 100;
  if (!stages.length) return 4;
  const completed = stages.filter((s) => s.state === "done").length;
  const active = stages.some((s) => s.state === "active") ? 0.5 : 0;
  return Math.min(98, ((completed + active) / stages.length) * 100);
}

export function AnalysisProgress({
  url,
  onComplete,
  onBack,
}: {
  url: string;
  onComplete: (result: AnalysisResult) => void;
  onBack: () => void;
}) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const startRef = useRef<number>(Date.now());

  // Run the job: create, then poll to completion, surfacing live stages.
  useEffect(() => {
    const controller = new AbortController();
    startRef.current = Date.now();
    setError(null);
    setStatus(null);
    setElapsed(0);

    (async () => {
      try {
        const job = await createJob(url);
        const result = await pollJob(job.job_id, setStatus, {
          signal: controller.signal,
        });
        if (!controller.signal.aborted) onComplete(result);
      } catch (err) {
        if (controller.signal.aborted) return;
        const message =
          err instanceof ApiError
            ? err.message
            : "Analysis failed. The repository may be private, very large, or unreachable.";
        setError(message);
      }
    })();

    return () => controller.abort();
  }, [url, attempt, onComplete]);

  // Elapsed timer (purely cosmetic; the stages are the real signal).
  useEffect(() => {
    if (error) return;
    const id = setInterval(() => {
      setElapsed((Date.now() - startRef.current) / 1000);
    }, 250);
    return () => clearInterval(id);
  }, [error, attempt]);

  const stages = status?.stages?.length ? status.stages : FALLBACK_STAGES;
  const done = status?.status === "done";
  const pct = progressPct(stages, done);
  const commits =
    typeof status?.meta?.commits === "number" ? (status.meta.commits as number) : null;

  // Soft, honest ETA: extrapolate from elapsed and fraction complete.
  const eta =
    pct > 8 && pct < 96 && elapsed > 1.5
      ? Math.max(1, Math.round((elapsed / pct) * (100 - pct)))
      : null;

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-16 sm:py-24">
      <div className="surface p-6 sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {error ? "Analysis failed" : done ? "Finalizing" : "Analyzing repository"}
            </p>
            <h2 className="mt-1 truncate font-mono text-lg font-semibold">
              {repoLabel(url)}
            </h2>
          </div>
          {!error && (
            <div className="shrink-0 text-right">
              <div className="tnum text-sm font-medium">{elapsed.toFixed(0)}s</div>
              <div className="text-[11px] text-muted-foreground">
                {eta ? `~${eta}s left (est.)` : "elapsed"}
              </div>
            </div>
          )}
        </div>

        {error ? (
          <ErrorPanel message={error} onRetry={() => setAttempt((a) => a + 1)} onBack={onBack} />
        ) : (
          <>
            <div className="mt-5">
              <Progress value={pct} />
              <div className="mt-1.5 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>
                  {commits != null
                    ? `${commits.toLocaleString()} commits parsed`
                    : "Live pipeline — each step is a real stage of analysis"}
                </span>
                <span className="tnum">{Math.round(pct)}%</span>
              </div>
            </div>

            <ol className="mt-6 space-y-1">
              {stages.map((stage, i) => (
                <StageRow key={stage.key} stage={stage} index={i} />
              ))}
            </ol>

            <div className="mt-6">
              <Button variant="ghost" size="sm" onClick={onBack}>
                <ArrowLeft />
                Cancel
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StageRow({ stage, index }: { stage: Stage; index: number }) {
  return (
    <motion.li
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03, duration: 0.25 }}
      className={cn(
        "flex items-center gap-3 rounded-md px-2 py-1.5 text-sm transition-colors",
        stage.state === "active" && "bg-accent/60",
      )}
    >
      <StageIndicator state={stage.state} />
      <span
        className={cn(
          "flex-1",
          stage.state === "pending" && "text-muted-foreground",
          stage.state === "done" && "text-muted-foreground",
          stage.state === "active" && "font-medium text-foreground",
          stage.state === "error" && "text-danger-foreground",
        )}
      >
        {stage.label}
      </span>
      <AnimatePresence>
        {stage.state === "active" && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-[11px] text-muted-foreground"
          >
            in progress
          </motion.span>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

function StageIndicator({ state }: { state: Stage["state"] }) {
  if (state === "done")
    return (
      <span className="grid size-5 place-items-center rounded-full bg-success/15 text-success">
        <Check className="size-3" />
      </span>
    );
  if (state === "active")
    return (
      <span className="grid size-5 place-items-center rounded-full bg-primary/15 text-primary">
        <Loader2 className="size-3 animate-spin" />
      </span>
    );
  if (state === "error")
    return (
      <span className="grid size-5 place-items-center rounded-full bg-danger/15 text-danger">
        <AlertCircle className="size-3" />
      </span>
    );
  return (
    <span className="grid size-5 place-items-center">
      <span className="size-1.5 rounded-full bg-border" />
    </span>
  );
}

function ErrorPanel({
  message,
  onRetry,
  onBack,
}: {
  message: string;
  onRetry: () => void;
  onBack: () => void;
}) {
  return (
    <div className="mt-5">
      <div className="flex items-start gap-3 rounded-md border border-danger/30 bg-danger-subtle p-3">
        <AlertCircle className="mt-0.5 size-4 shrink-0 text-danger" />
        <p className="text-sm text-danger-foreground">{message}</p>
      </div>
      <div className="mt-4 flex gap-2">
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RotateCcw />
          Retry
        </Button>
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft />
          Back
        </Button>
      </div>
    </div>
  );
}
