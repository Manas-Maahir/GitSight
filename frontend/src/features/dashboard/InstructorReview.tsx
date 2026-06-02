import { Check } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { submitReview } from "@/lib/api";
import type { Role } from "@/lib/types";

const ROLES: Role[] = ["Major Contributor", "Minor Contributor", "Free Rider"];

/**
 * Instructor calibration: confirm the automated verdict, or correct it. Both
 * paths feed the calibration label set (agreements matter, not just
 * disagreements). Uses a proper Select + toast confirmation.
 */
export function InstructorReview({
  analysisId,
  author,
  systemRole,
}: {
  analysisId: number;
  author: string;
  systemRole: Role;
}) {
  const [correction, setCorrection] = useState<Role | "">("");
  const [busy, setBusy] = useState(false);
  const [recorded, setRecorded] = useState(false);

  const send = async (role: Role) => {
    setBusy(true);
    try {
      const res = await submitReview({ analysisId, author, instructorRole: role });
      setRecorded(true);
      toast.success(
        res.agreed === false
          ? `Correction recorded — ${author} marked ${role}.`
          : `Confirmed — ${author} as ${role}.`,
      );
    } catch {
      toast.error("Could not record review. Is the backend reachable?");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-md border border-border bg-muted/20 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          Instructor review
        </span>
        {recorded && (
          <span className="inline-flex items-center gap-1 text-xs text-success-foreground">
            <Check className="size-3.5" /> recorded
          </span>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={() => send(systemRole)}
        >
          <Check />
          Agree
        </Button>
        <span className="text-xs text-muted-foreground">or correct to</span>
        <Select value={correction} onValueChange={(v) => setCorrection(v as Role)}>
          <SelectTrigger className="h-8 w-[180px] text-xs">
            <SelectValue placeholder="Choose role…" />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          disabled={!correction || busy}
          onClick={() => correction && send(correction)}
        >
          Save
        </Button>
      </div>
    </section>
  );
}
