import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { hslVar, useTokens } from "@/lib/useTokens";
import type { Author } from "@/lib/types";

/**
 * Ownership vs effort, side by side, for the top contributors. Makes "who owns
 * the surviving code vs who churned" legible at a glance. Effort far exceeding
 * ownership (high divergence) is tinted to flag churn that did not survive.
 */
export function OwnershipEffortChart({
  authors,
  activeKey,
  onHover,
}: {
  authors: Author[];
  activeKey: string | null;
  onHover: (key: string | null) => void;
}) {
  const t = useTokens();

  const rows = useMemo(() => {
    return [...authors]
      .sort((a, b) => b.score - a.score)
      .slice(0, 6)
      .map((a) => ({
        key: a.author,
        name: a.author,
        ownership: Math.round(a.ownership_pct ?? a.ownership_interval?.point ?? 0),
        effort: Math.round(a.effort_pct ?? 0),
        divergence: a.divergence ?? 0,
      }));
  }, [authors]);

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Ownership vs effort</CardTitle>
        <CardDescription>
          Surviving lines owned (blue) against authored churn (graphite)
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="h-[220px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 0, right: 8, bottom: 0, left: 8 }}
              barCategoryGap={10}
            >
              <XAxis
                type="number"
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: t["muted-foreground"], fontSize: 11 }}
                axisLine={{ stroke: t.border }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={88}
                tick={{ fill: t["muted-foreground"], fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <RTooltip
                cursor={{ fill: hslVar("muted", 0.5) }}
                contentStyle={{
                  background: t.card,
                  border: `1px solid ${t.border}`,
                  borderRadius: 8,
                  fontSize: 12,
                  color: t.foreground,
                }}
                formatter={(value: number, name: string) => [`${value}%`, name]}
              />
              <Bar
                dataKey="ownership"
                name="Ownership"
                radius={[0, 3, 3, 0]}
                onMouseEnter={(_, i) => onHover(rows[i]?.key ?? null)}
                onMouseLeave={() => onHover(null)}
              >
                {rows.map((r) => (
                  <Cell
                    key={r.key}
                    fill={t.primary}
                    fillOpacity={activeKey && activeKey !== r.key ? 0.3 : 1}
                  />
                ))}
              </Bar>
              <Bar
                dataKey="effort"
                name="Effort"
                radius={[0, 3, 3, 0]}
                onMouseEnter={(_, i) => onHover(rows[i]?.key ?? null)}
                onMouseLeave={() => onHover(null)}
              >
                {rows.map((r) => (
                  <Cell
                    key={r.key}
                    fill={r.divergence > 20 ? t.warning : t["muted-foreground"]}
                    fillOpacity={activeKey && activeKey !== r.key ? 0.3 : 0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
