import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Code2, GitBranch, ShieldAlert } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Badge } from "@/components/ui/badge";
import { InfoTip } from "@/components/ui/tooltip";
import { fmtInterval, fmtPct, qualityVariant } from "@/lib/format";
import type { Author, TimelineCommit } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ContributorDetail } from "./ContributorDetail";
import { VerdictBadge } from "./primitives";

const qualityToneClass = {
  success: "text-success-foreground",
  warning: "text-warning-foreground",
  danger: "text-danger-foreground",
  info: "text-info-foreground",
  neutral: "text-muted-foreground",
} as const;

export function ContributorCard({
  author,
  timeline,
  analysisId,
  open,
  active,
  onToggle,
  onHover,
}: {
  author: Author;
  timeline: TimelineCommit[];
  analysisId?: number;
  open: boolean;
  active: boolean;
  onToggle: () => void;
  onHover: (key: string | null) => void;
}) {
  const flags = author.integrity_flags ?? [];
  const qTone = qualityVariant(author.quality_score);

  return (
    <div
      onMouseEnter={() => onHover(author.author)}
      onMouseLeave={() => onHover(null)}
      className={cn(
        "overflow-hidden rounded-lg border bg-card transition-colors",
        active ? "border-primary/40" : "border-border",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-accent/40 sm:gap-4 sm:px-4"
      >
        <Avatar name={author.author} size={36} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">{author.author}</span>
            {flags.length > 0 && (
              <InfoTip label={`${flags.length} integrity signal(s) — expand to review`}>
                <Badge variant="danger" className="cursor-help">
                  <ShieldAlert />
                  {flags.length}
                </Badge>
              </InfoTip>
            )}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <GitBranch className="size-3" />
              {fmtInterval(author.ownership_interval, author.ownership_pct)} owned
            </span>
            <span className="inline-flex items-center gap-1">
              <Code2 className="size-3" />
              {fmtPct(author.effort_pct)} effort
            </span>
            <span className="tnum">{author.stats.commits} commits</span>
          </div>
        </div>

        {/* Quality */}
        <div className="hidden w-16 text-right md:block">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Quality
          </div>
          <div className={cn("tnum text-sm font-semibold", qualityToneClass[qTone])}>
            {author.quality_score == null ? "N/A" : author.quality_score.toFixed(0)}
          </div>
        </div>

        {/* Impact score */}
        <div className="w-14 text-right">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Impact
          </div>
          <div className="tnum text-sm font-semibold">{author.score}</div>
        </div>

        <div className="hidden sm:block">
          <VerdictBadge role={author.role} />
        </div>

        <ChevronDown
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <ContributorDetail
              author={author}
              timeline={timeline}
              analysisId={analysisId}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
