import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * Determinate progress bar with a smooth tween between values — driven by the
 * real backend stage index, not a fake timer.
 */
export function Progress({
  value,
  className,
}: {
  value: number; // 0..100
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "relative h-1.5 w-full overflow-hidden rounded-full bg-muted",
        className,
      )}
    >
      <motion.div
        className="h-full rounded-full bg-primary"
        initial={false}
        animate={{ width: `${clamped}%` }}
        transition={{ type: "spring", stiffness: 120, damping: 22 }}
      />
    </div>
  );
}
