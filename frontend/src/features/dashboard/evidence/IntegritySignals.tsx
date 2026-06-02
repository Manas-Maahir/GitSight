import { ChevronDown, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { flagLabel, severityVariant, shortSha } from "@/lib/format";
import type { IntegrityFlag } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Integrity signals rendered as an evidence chain: severity-coded headers that
 * expand to the specific commit SHAs backing each signal. Explicitly advisory —
 * these never change the impact score.
 */
export function IntegritySignals({ flags }: { flags: IntegrityFlag[] }) {
  if (flags.length === 0) return null;
  return (
    <section>
      <header className="mb-2 flex items-center gap-2">
        <ShieldAlert className="size-4 text-danger" />
        <h4 className="text-sm font-semibold">Integrity signals ({flags.length})</h4>
      </header>
      <p className="mb-3 text-xs text-muted-foreground">
        Advisory forensic signals for human review — they do not change the impact score.
      </p>
      <ul className="space-y-2">
        {flags.map((flag, i) => (
          <FlagRow key={i} flag={flag} />
        ))}
      </ul>
    </section>
  );
}

function FlagRow({ flag }: { flag: IntegrityFlag }) {
  const [open, setOpen] = useState(false);
  const evidence = flag.evidence ?? [];
  const hasEvidence = evidence.length > 0;

  return (
    <li className="overflow-hidden rounded-md border border-border bg-muted/20">
      <button
        type="button"
        disabled={!hasEvidence}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-3 px-3 py-2 text-left",
          hasEvidence && "hover:bg-accent/50",
        )}
      >
        <Badge variant={severityVariant(flag.severity)} className="shrink-0">
          {flag.severity}
        </Badge>
        <span className="min-w-0 flex-1">
          <span className="text-sm font-medium">{flagLabel(flag.type)}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {flag.detail}
          </span>
        </span>
        {hasEvidence && (
          <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
            {evidence.length} commit{evidence.length === 1 ? "" : "s"}
            <ChevronDown
              className={cn("size-3.5 transition-transform", open && "rotate-180")}
            />
          </span>
        )}
      </button>

      {open && hasEvidence && (
        <ul className="border-t border-border bg-background/40 px-3 py-2">
          {evidence.map((e, i) => (
            <li
              key={i}
              className="flex items-start gap-2 py-1 text-xs text-muted-foreground"
            >
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground">
                {shortSha(e.commit)}
              </code>
              {e.detail && <span className="pt-0.5">{e.detail}</span>}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
