import { useState, useEffect, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import CompetitorService, {
  CompetitorAnalysis, ComparisonResponse, CompetitorEntry, Insight,
  ListingOption, AnalysisProgress,
} from "../../services/competitor.service";

// ── Score color helper ──────────────────────────────────────────────────────

function scoreColor(score: number | null): string {
  if (score === null || score === undefined) return "var(--text-hint)";
  if (score >= 70) return "var(--success)";
  if (score >= 40) return "var(--warning)";
  return "var(--danger)";
}

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return n.toLocaleString();
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function CompetitorPage() {
  // State
  const [mode, setMode] = useState<"listing" | "manual">("listing");
  const [listings, setListings] = useState<ListingOption[]>([]);
  const [selectedListing, setSelectedListing] = useState<ListingOption | null>(null);
  const [manualDomain, setManualDomain] = useState("");
  const [category, setCategory] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [maxCompetitors, setMaxCompetitors] = useState(10);
  const [includeSeo, setIncludeSeo] = useState(true);
  const [includeSemrush, setIncludeSemrush] = useState(true);

  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [analyses, setAnalyses] = useState<CompetitorAnalysis[]>([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState<CompetitorAnalysis | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Load listings and past analyses on mount ──────────────────────────────

  useEffect(() => {
    CompetitorService.getListingsWithWebsites().then(setListings).catch(() => {});
    CompetitorService.listAnalyses({ per_page: 50 }).then(r => setAnalyses(r.items)).catch(() => {});
  }, []);

  // ── Polling ───────────────────────────────────────────────────────────────

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const p = await CompetitorService.getProgress();
        setProgress(p);
        if (!p.running) {
          stopPolling();
          // Refresh analyses list
          const res = await CompetitorService.listAnalyses({ per_page: 50 });
          setAnalyses(res.items);
          // Auto-load the completed analysis
          if (p.analysis_id) {
            const completed = res.items.find(a => a.id === p.analysis_id);
            if (completed) {
              setSelectedAnalysis(completed);
              loadComparison(completed.id);
            }
          }
        }
      } catch {
        stopPolling();
      }
    }, 2000);
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPolling(), []);

  // ── Start analysis ────────────────────────────────────────────────────────

  const handleStart = async () => {
    setError("");
    const targetDomain = mode === "listing" ? selectedListing?.website || "" : manualDomain;
    if (!targetDomain.trim()) {
      setError("Please enter or select a target domain.");
      return;
    }

    try {
      setLoading(true);
      await CompetitorService.startAnalysis({
        target_domain: targetDomain,
        business_listing_id: mode === "listing" ? selectedListing?.id : undefined,
        category: mode === "listing" ? selectedListing?.category || undefined : category || undefined,
        city: mode === "listing" ? selectedListing?.city || undefined : city || undefined,
        state: mode === "listing" ? selectedListing?.state || undefined : state || undefined,
        max_competitors: maxCompetitors,
        include_seo_checks: includeSeo,
        include_semrush: includeSemrush,
      });
      setComparison(null);
      setSelectedAnalysis(null);
      startPolling();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  };

  // ── Load comparison ───────────────────────────────────────────────────────

  const loadComparison = async (analysisId: number) => {
    try {
      const data = await CompetitorService.getComparison(analysisId);
      setComparison(data);
    } catch {
      setError("Failed to load comparison data");
    }
  };

  const selectAnalysis = (a: CompetitorAnalysis) => {
    setSelectedAnalysis(a);
    if (a.status === "done") loadComparison(a.id);
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Competitor Analysis</h1>
        <p className="page-subtitle">Find and compare competitors for any business website</p>
      </div>

      {/* ── Analysis Launcher ──────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <button
            className={`btn ${mode === "listing" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setMode("listing")}
          >From Business Listing</button>
          <button
            className={`btn ${mode === "manual" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setMode("manual")}
          >Manual Domain</button>
        </div>

        {mode === "listing" ? (
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>
              Select a business with a website
            </label>
            <select
              className="form-input"
              value={selectedListing?.id || ""}
              onChange={e => {
                const l = listings.find(x => x.id === Number(e.target.value));
                setSelectedListing(l || null);
              }}
            >
              <option value="">-- Choose a business --</option>
              {listings.map(l => (
                <option key={l.id} value={l.id}>
                  {l.business_name} — {l.website} ({l.city || "N/A"})
                </option>
              ))}
            </select>
            {selectedListing && (
              <div style={{ marginTop: 8, fontSize: 13, color: "var(--text-muted)" }}>
                Category: {selectedListing.category || "N/A"} | City: {selectedListing.city || "N/A"} |
                Rating: {selectedListing.rating ?? "N/A"} ({selectedListing.reviews_count ?? 0} reviews)
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>Domain</label>
              <input className="form-input" placeholder="example.com.au" value={manualDomain}
                onChange={e => setManualDomain(e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>Category</label>
              <input className="form-input" placeholder="e.g. Dentist" value={category}
                onChange={e => setCategory(e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>City</label>
              <input className="form-input" placeholder="e.g. Melbourne" value={city}
                onChange={e => setCity(e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>State</label>
              <input className="form-input" placeholder="e.g. VIC" value={state}
                onChange={e => setState(e.target.value)} />
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={includeSeo} onChange={e => setIncludeSeo(e.target.checked)} />
            Run SEO Checks
          </label>
          <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={includeSemrush} onChange={e => setIncludeSemrush(e.target.checked)} />
            Include Semrush Data
          </label>
          <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
            Max Competitors:
            <input type="number" className="form-input" style={{ width: 60 }} min={1} max={20}
              value={maxCompetitors} onChange={e => setMaxCompetitors(Number(e.target.value))} />
          </label>
          <button className="btn btn-primary" onClick={handleStart}
            disabled={loading || (progress?.running ?? false)}>
            {loading ? "Starting..." : "Find Competitors"}
          </button>
        </div>

        {error && <div style={{ color: "var(--danger)", marginTop: 12, fontSize: 13 }}>{error}</div>}

        {/* Progress bar */}
        {progress?.running && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
              <span style={{ color: "var(--text-muted)" }}>
                {progress.phase === "discovering" ? "Discovering competitors..." :
                 progress.phase === "enriching" ? "Analyzing competitors..." :
                 progress.phase === "analyzing" ? "Generating insights..." : "Processing..."}
              </span>
              <span style={{ color: "var(--accent)" }}>{progress.done}/{progress.total} ({progress.percent}%)</span>
            </div>
            <div style={{ height: 6, background: "var(--bg3)", borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                height: "100%", width: `${progress.percent}%`,
                background: "var(--accent)", borderRadius: 3, transition: "width 0.3s",
              }} />
            </div>
          </div>
        )}
      </div>

      {/* ── Past Analyses Chips ─────────────────────────────────────────── */}
      {analyses.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
          {analyses.slice(0, 20).map(a => (
            <button
              key={a.id}
              className={`btn ${selectedAnalysis?.id === a.id ? "btn-primary" : "btn-secondary"}`}
              style={{ fontSize: 12, padding: "6px 12px" }}
              onClick={() => selectAnalysis(a)}
            >
              <span style={{
                width: 8, height: 8, borderRadius: "50%", display: "inline-block", marginRight: 6,
                background: a.status === "done" ? "var(--success)" :
                            a.status === "running" ? "var(--accent)" :
                            a.status === "failed" ? "var(--danger)" : "var(--warning)",
              }} />
              {a.target_domain}
              <span style={{ color: "var(--text-hint)", marginLeft: 6 }}>
                ({a.competitors_found})
              </span>
            </button>
          ))}
        </div>
      )}

      {/* ── Comparison Dashboard ────────────────────────────────────────── */}
      {comparison && comparison.target && (
        <ComparisonDashboard comparison={comparison}
          onExport={() => selectedAnalysis && CompetitorService.exportCsv(selectedAnalysis.id)} />
      )}

      {/* ── Empty state ────────────────────────────────────────────────── */}
      {!comparison && !progress?.running && analyses.length === 0 && (
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style={{ opacity: 0.3, marginBottom: 16 }}>
            <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="2"/>
            <path d="M16 24h16M24 16v16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <h3 style={{ color: "var(--text-muted)" }}>No analyses yet</h3>
          <p style={{ color: "var(--text-hint)", fontSize: 14 }}>
            Select a business or enter a domain above to find competitors
          </p>
        </div>
      )}
    </div>
  );
}

// ── Comparison Dashboard Sub-component ──────────────────────────────────────

function ComparisonDashboard({ comparison, onExport }: {
  comparison: ComparisonResponse;
  onExport: () => void;
}) {
  const { target, competitors, insights } = comparison;
  if (!target) return null;

  const allEntries = [target, ...competitors];

  // Data for bar chart
  const barData = allEntries.map(e => ({
    name: e.domain.length > 20 ? e.domain.substring(0, 18) + "..." : e.domain,
    "SEO Score": e.seo_overall_score ?? 0,
    "Domain Authority": e.domain_authority ?? 0,
    isTarget: e.is_target,
  }));

  // Data for radar chart (target vs best competitor)
  const bestComp = competitors[0];
  const seoChecks = ["dns", "https", "meta", "robots", "sitemap", "ssl", "speed", "mobile", "social_meta", "headings"];
  const radarData = seoChecks.map(check => ({
    check: check.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase()),
    Target: (target as any)[`seo_${check}_score`] ?? 0,
    ...(bestComp ? { "Top Competitor": (bestComp as any)[`seo_${check}_score`] ?? 0 } : {}),
  }));

  return (
    <div>
      {/* Header with export */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, margin: 0 }}>
          {target.domain}
          <span style={{ fontSize: 13, color: "var(--text-muted)", marginLeft: 8 }}>
            vs {competitors.length} competitor{competitors.length !== 1 ? "s" : ""}
          </span>
        </h2>
        <button className="btn btn-secondary" onClick={onExport} style={{ fontSize: 12 }}>
          Export CSV
        </button>
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
        {/* Score comparison bar chart */}
        <div className="card">
          <h3 style={{ fontSize: 14, marginBottom: 12, color: "var(--text-muted)" }}>Score Comparison</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--text-hint)" }} />
              <YAxis tick={{ fontSize: 11, fill: "var(--text-hint)" }} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: "var(--bg2)", border: "1px solid var(--bg3)", borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="SEO Score" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Domain Authority" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* SEO breakdown radar */}
        <div className="card">
          <h3 style={{ fontSize: 14, marginBottom: 12, color: "var(--text-muted)" }}>SEO Check Breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--bg3)" />
              <PolarAngleAxis dataKey="check" tick={{ fontSize: 10, fill: "var(--text-hint)" }} />
              <PolarRadiusAxis tick={{ fontSize: 9, fill: "var(--text-hint)" }} domain={[0, 100]} />
              <Radar name="Target" dataKey="Target" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.3} />
              {bestComp && (
                <Radar name="Top Competitor" dataKey="Top Competitor" stroke="var(--danger)" fill="var(--danger)" fillOpacity={0.15} />
              )}
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Comparison table */}
      <div className="card" style={{ marginBottom: 24, overflowX: "auto" }}>
        <h3 style={{ fontSize: 14, marginBottom: 12, color: "var(--text-muted)" }}>Side-by-Side Comparison</h3>
        <table className="data-table" style={{ fontSize: 13 }}>
          <thead>
            <tr>
              <th>Metric</th>
              <th style={{ background: "rgba(79, 124, 248, 0.1)" }}>{target.domain} (Target)</th>
              {competitors.map(c => <th key={c.id}>{c.domain}</th>)}
            </tr>
          </thead>
          <tbody>
            <MetricRow label="SEO Score" field="seo_overall_score" target={target} competitors={competitors} isScore />
            <MetricRow label="Organic Traffic" field="organic_traffic" target={target} competitors={competitors} />
            <MetricRow label="Organic Keywords" field="organic_keywords" target={target} competitors={competitors} />
            <MetricRow label="Domain Authority" field="domain_authority" target={target} competitors={competitors} />
            <MetricRow label="Backlinks" field="backlinks_total" target={target} competitors={competitors} />
            <MetricRow label="Referring Domains" field="referring_domains" target={target} competitors={competitors} />
            <MetricRow label="Maps Rating" field="maps_rating" target={target} competitors={competitors} />
            <MetricRow label="Maps Reviews" field="maps_reviews" target={target} competitors={competitors} />
          </tbody>
        </table>
      </div>

      {/* Insights */}
      {insights.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 16, marginBottom: 16 }}>Actionable Insights</h3>
          <div style={{ display: "grid", gap: 12 }}>
            {insights.map(insight => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Metric row helper ───────────────────────────────────────────────────────

function MetricRow({ label, field, target, competitors, isScore }: {
  label: string;
  field: string;
  target: CompetitorEntry;
  competitors: CompetitorEntry[];
  isScore?: boolean;
}) {
  const targetVal = (target as any)[field];

  return (
    <tr>
      <td style={{ fontWeight: 500 }}>{label}</td>
      <td style={{
        background: "rgba(79, 124, 248, 0.05)",
        color: isScore ? scoreColor(targetVal) : undefined,
        fontWeight: isScore ? 600 : undefined,
      }}>
        {isScore && targetVal != null ? `${targetVal}/100` : fmt(targetVal)}
      </td>
      {competitors.map(c => {
        const val = (c as any)[field];
        const isBetter = targetVal != null && val != null && val > targetVal;
        return (
          <td key={c.id} style={{
            color: isScore ? scoreColor(val) :
                   isBetter ? "var(--danger)" : undefined,
            fontWeight: isScore ? 600 : undefined,
          }}>
            {isScore && val != null ? `${val}/100` : fmt(val)}
            {isBetter && !isScore && <span style={{ fontSize: 10, marginLeft: 4 }}>^</span>}
          </td>
        );
      })}
    </tr>
  );
}

// ── Insight card ────────────────────────────────────────────────────────────

function InsightCard({ insight }: { insight: Insight }) {
  const severityColors = {
    high: "var(--danger)",
    medium: "var(--warning)",
    low: "var(--success)",
  };

  return (
    <div className="card" style={{
      borderLeft: `3px solid ${severityColors[insight.severity]}`,
      padding: "14px 18px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span className={`badge badge-${insight.severity === "high" ? "danger" : insight.severity === "medium" ? "warning" : "success"}`}>
          {insight.severity.toUpperCase()}
        </span>
        <span style={{ fontWeight: 600, fontSize: 14 }}>{insight.title}</span>
      </div>
      <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
        {insight.description}
      </p>
    </div>
  );
}
