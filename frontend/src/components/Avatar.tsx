import { useState } from "react";
import { avatarUrl } from "@/lib/format";
import { cn } from "@/lib/utils";

/** GitHub avatar with a graceful generated fallback. */
export function Avatar({
  name,
  size = 36,
  className,
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  const [errored, setErrored] = useState(false);
  const src = errored
    ? avatarUrl(name)
    : `https://github.com/${encodeURIComponent(name)}.png?size=${size * 2}`;
  return (
    <img
      src={src}
      onError={() => setErrored(true)}
      alt=""
      width={size}
      height={size}
      style={{ width: size, height: size }}
      className={cn("shrink-0 rounded-full border border-border bg-muted object-cover", className)}
    />
  );
}
