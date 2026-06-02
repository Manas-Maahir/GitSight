import { Info, ShieldCheck, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { reliabilityVariant } from "@/lib/format";
import type { AnalysisResult } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Calibrated-confidence panel. Calm by default (this is information, not an
 * alarm) and only escalates color when reliability is genuinely low. Explains
 * *why* confidence is bounded — the product's core honesty signal.
 */
export function TrustBanner({ data }: { data: AnalysisResult }) {
  const reliability = data.reliability;
  const band = reliability?.band ?? "high";
  const variant = reliabilityVariant(band);
  const low = band === "low" || band === "unreliable";

  // The regime is reported per-author by explain.annotate; surface the dominant.
  const regime =
    data.authors.find((a) => a.explanation?.regime)?.explanation?.regime ??
    "cold-start";

  const tone = low
    ? "border-warning/30 bg-warning-subtle"
    : "border-border bg-muted/30";

  const Icon = low ? ShieldAlert : ShieldCheck;
  const factors = reliability?.factors ?? [];

  return (
    <div className={cn("surface flex items-start gap-3 p-4", tone)}>
      <span
        className={cn(
          "mt-0.5 grid size-8 shrink-0 place-items-center rounded-md",
          low ? "bg-warning/15 text-warning" : "bg-primary/10 text-primary",
        )}
      >
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">Trust & calibration</h2>
          <Badge variant={variant}>Reliability: {band}</Badge>
          <Badge variant={regime === "calibrated" ? "success" : "neutral"}>
            {regime === "calibrated" ? "Calibrated" : "Cold-start"}
          </Badge>
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          {low
            ? "This repository's history may distort line-level attribution. "
            : "Attribution reliability is sound. "}
          {regime === "calibrated"
            ? "Confidence is calibrated against recorded instructor reviews."
            : "Confidence is held conservatively (cold-start) until reviews calibrate the model — verdicts are a prompt for review, not a conclusion."}
        </p>
        {low && factors.length > 0 && (
          <ul className="mt-2 space-y-1">
            {factors.map((f, i) => (
              <li
                key={i}
                className="flex items-start gap-1.5 text-[11px] text-muted-foreground"
              >
                <Info className="mt-0.5 size-3 shrink-0" />
                <span>{f.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
