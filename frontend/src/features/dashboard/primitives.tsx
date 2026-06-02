import { AlertTriangle, Star, User } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { InfoTip } from "@/components/ui/tooltip";
import {
  confidenceVariant,
  reliabilityVariant,
  roleVariant,
  type SemanticVariant,
} from "@/lib/format";
import type { Confidence, ReliabilityBand, Role } from "@/lib/types";
import { cn } from "@/lib/utils";

export function VerdictBadge({ role }: { role: Role }) {
  const variant = roleVariant(role);
  const Icon = role.includes("Major")
    ? Star
    : role.includes("Free")
      ? AlertTriangle
      : User;
  return (
    <Badge variant={variant}>
      <Icon />
      {role}
    </Badge>
  );
}

export function ConfidenceBadge({
  confidence,
  regime,
}: {
  confidence: Confidence;
  regime?: string;
}) {
  return (
    <InfoTip
      label={`Confidence regime: ${regime ?? "cold-start"} — deliberately conservative until calibrated against instructor reviews.`}
    >
      <Badge variant={confidenceVariant(confidence)} className="cursor-help">
        Confidence: {confidence}
      </Badge>
    </InfoTip>
  );
}

export function ReliabilityBadge({ band }: { band: ReliabilityBand }) {
  return <Badge variant={reliabilityVariant(band)}>Reliability: {band}</Badge>;
}

/** Compact labelled metric used in the contributor detail grid. */
export function Metric({
  label,
  value,
  sub,
  tone = "default",
  tip,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "default" | "muted" | SemanticVariant;
  tip?: string;
}) {
  const valueTone = {
    default: "text-foreground",
    muted: "text-muted-foreground",
    neutral: "text-muted-foreground",
    info: "text-info-foreground",
    success: "text-success-foreground",
    warning: "text-warning-foreground",
    danger: "text-danger-foreground",
  }[tone];

  const body = (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-1 tnum text-base font-semibold", valueTone)}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );

  return tip ? (
    <InfoTip label={tip}>
      <div className="cursor-help">{body}</div>
    </InfoTip>
  ) : (
    body
  );
}
