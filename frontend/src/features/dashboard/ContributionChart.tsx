import { useMemo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useTokens } from "@/lib/useTokens";
import type { Author } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Slice {
  key: string;
  label: string;
  value: number;
}

/**
 * Impact distribution donut. Contributors under 2% of total impact are grouped
 * as "Others". Hovering a slice or a table row cross-highlights via activeKey.
 */
export function ContributionChart({
  authors,
  activeKey,
  onHover,
}: {
  authors: Author[];
  activeKey: string | null;
  onHover: (key: string | null) => void;
}) {
  const t = useTokens();

  const slices = useMemo<Slice[]>(() => {
    const total = authors.reduce((s, a) => s + a.score, 0) || 1;
    const threshold = total * 0.02;
    const major: Slice[] = [];
    let others = 0;
    let othersCount = 0;
    for (const a of authors) {
      if (a.score >= threshold) {
        major.push({ key: a.author, label: a.author, value: a.score });
      } else {
        others += a.score;
        othersCount += 1;
      }
    }
    major.sort((a, b) => b.value - a.value);
    if (others > 0) {
      major.push({ key: "__others__", label: `Others (${othersCount})`, value: others });
    }
    return major;
  }, [authors]);

  // Monochrome ramp: primary leads, then graphite steps. Active stays solid,
  // others fade — restrained, no rainbow.
  const palette = useMemo(() => {
    const base = [t.primary, t["muted-foreground"], t.foreground, t.border];
    return slices.map((_, i) => {
      if (i === 0) return t.primary;
      return base[(i % (base.length - 1)) + 1];
    });
  }, [slices, t]);

  const total = slices.reduce((s, x) => s + x.value, 0) || 1;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Impact distribution</CardTitle>
        <CardDescription>Contributors under 2% grouped as "Others"</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative h-44 w-full sm:w-44">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="label"
                innerRadius="64%"
                outerRadius="100%"
                paddingAngle={slices.length > 1 ? 2 : 0}
                stroke={t.card}
                strokeWidth={2}
                isAnimationActive={false}
              >
                {slices.map((s, i) => {
                  const dim = activeKey != null && activeKey !== s.key;
                  return (
                    <Cell
                      key={s.key}
                      fill={palette[i]}
                      fillOpacity={dim ? 0.25 : 1}
                      onMouseEnter={() => onHover(s.key)}
                      onMouseLeave={() => onHover(null)}
                      style={{ transition: "fill-opacity 150ms", cursor: "pointer" }}
                    />
                  );
                })}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>

        <ul className="flex-1 space-y-1.5">
          {slices.map((s, i) => {
            const active = activeKey === s.key;
            return (
              <li
                key={s.key}
                onMouseEnter={() => onHover(s.key)}
                onMouseLeave={() => onHover(null)}
                className={cn(
                  "flex items-center gap-2 rounded px-1.5 py-1 text-xs transition-colors",
                  active && "bg-accent",
                )}
              >
                <span
                  className="size-2.5 shrink-0 rounded-sm"
                  style={{ backgroundColor: palette[i] }}
                />
                <span className="flex-1 truncate">{s.label}</span>
                <span className="tnum text-muted-foreground">
                  {Math.round((s.value / total) * 100)}%
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>

      {/* Screen-reader accessible table mirrors the chart. */}
      <table className="sr-only">
        <caption>Impact distribution by contributor</caption>
        <thead>
          <tr>
            <th>Contributor</th>
            <th>Share</th>
          </tr>
        </thead>
        <tbody>
          {slices.map((s) => (
            <tr key={s.key}>
              <td>{s.label}</td>
              <td>{Math.round((s.value / total) * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
