import { Users } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Author, TimelineCommit } from "@/lib/types";
import { ContributorCard } from "./ContributorCard";

type SortKey = "impact" | "ownership" | "effort" | "quality" | "flags";

const SORT_LABELS: Record<SortKey, string> = {
  impact: "Impact score",
  ownership: "Ownership",
  effort: "Effort",
  quality: "Code quality",
  flags: "Integrity flags",
};

function sortValue(a: Author, key: SortKey): number {
  switch (key) {
    case "ownership":
      return a.ownership_pct ?? a.ownership_interval?.point ?? 0;
    case "effort":
      return a.effort_pct ?? 0;
    case "quality":
      return a.quality_score ?? -1;
    case "flags":
      return (a.integrity_flags ?? []).length;
    default:
      return a.score;
  }
}

export function ContributorTable({
  authors,
  timeline,
  analysisId,
  activeKey,
  onHover,
}: {
  authors: Author[];
  timeline: TimelineCommit[];
  analysisId?: number;
  activeKey: string | null;
  onHover: (key: string | null) => void;
}) {
  const [sort, setSort] = useState<SortKey>("impact");
  const [openKey, setOpenKey] = useState<string | null>(null);

  const sorted = useMemo(
    () => [...authors].sort((a, b) => sortValue(b, sort) - sortValue(a, sort)),
    [authors, sort],
  );

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Users className="size-4 text-muted-foreground" />
          Contributors
          <span className="tnum text-muted-foreground">({authors.length})</span>
        </h2>
        <div className="flex items-center gap-2">
          <span className="hidden text-xs text-muted-foreground sm:inline">Sort by</span>
          <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
            <SelectTrigger className="h-8 w-[150px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                <SelectItem key={k} value={k}>
                  {SORT_LABELS[k]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        {sorted.map((author) => (
          <ContributorCard
            key={author.author}
            author={author}
            timeline={timeline}
            analysisId={analysisId}
            open={openKey === author.author}
            active={activeKey === author.author}
            onToggle={() =>
              setOpenKey((k) => (k === author.author ? null : author.author))
            }
            onHover={onHover}
          />
        ))}
      </div>
    </section>
  );
}
