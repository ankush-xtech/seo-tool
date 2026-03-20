import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";

// ─── Bar Chart — daily fetched domains ───────────────────────────────────────
export function DailyFetchChart({ data }: { data: { date: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "var(--text-hint)" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--text-hint)" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--bg2)",
            border: "0.5px solid var(--border)",
            borderRadius: 6,
            fontSize: 12,
            color: "var(--text)",
          }}
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
        />
        <Bar dataKey="count" fill="var(--accent)" radius={[3, 3, 0, 0]} name="Domains" />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Pie Chart — score distribution ──────────────────────────────────────────
const PIE_COLORS = ["#22c55e", "#f59e0b", "#ef4444"];

export function ScoreDistChart({ data }: { data: { good: number; average: number; poor: number } }) {
  const chartData = [
    { name: "Good (70+)", value: data.good },
    { name: "Average (40-69)", value: data.average },
    { name: "Poor (<40)", value: data.poor },
  ].filter(d => d.value > 0);

  if (chartData.length === 0) {
    return (
      <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-hint)", fontSize: 13 }}>
        No scored domains yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={160}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={65}
          dataKey="value"
          paddingAngle={2}
        >
          {chartData.map((_, i) => (
            <Cell key={i} fill={PIE_COLORS[i]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "var(--bg2)",
            border: "0.5px solid var(--border)",
            borderRadius: 6,
            fontSize: 12,
            color: "var(--text)",
          }}
        />
        <Legend
          iconSize={8}
          iconType="circle"
          formatter={(value) => (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ─── TLD bar chart ────────────────────────────────────────────────────────────
export function TLDChart({ data }: { data: { tld: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
        <XAxis type="number" tick={{ fontSize: 10, fill: "var(--text-hint)" }} axisLine={false} tickLine={false} />
        <YAxis
          type="category" dataKey="tld"
          tick={{ fontSize: 11, fill: "var(--text-muted)" }}
          axisLine={false} tickLine={false} width={32}
          tickFormatter={v => `.${v}`}
        />
        <Tooltip
          contentStyle={{
            background: "var(--bg2)",
            border: "0.5px solid var(--border)",
            borderRadius: 6,
            fontSize: 12,
            color: "var(--text)",
          }}
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          formatter={(v) => [v, "Domains"]}
          labelFormatter={(v) => `.${v}`}
        />
        <Bar dataKey="count" fill="#4f7cf8" radius={[0, 3, 3, 0]} name="Domains" />
      </BarChart>
    </ResponsiveContainer>
  );
}
