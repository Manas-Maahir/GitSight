import { cn } from "@/lib/utils";

/** Wordmark + mark. The mark is a simple geometric glyph — no gradients/glow. */
export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <circle cx="8" cy="8" r="2.1" fill="currentColor" />
          <circle
            cx="8"
            cy="8"
            r="5.4"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeOpacity="0.55"
            strokeDasharray="2.4 2.2"
          />
        </svg>
      </span>
      <span className="text-[15px] font-semibold tracking-tight">
        Git<span className="text-muted-foreground">Sight</span>
      </span>
    </div>
  );
}
