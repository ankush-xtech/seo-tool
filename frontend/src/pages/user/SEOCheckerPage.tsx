import { useState } from "react";
import SEOService, { SEOCheckResult } from "../../services/seo.service";

// ─── Score ring component ─────────────────────────────────────────────────────
function ScoreRing({ score }: { score: number }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <svg width="130" height="130" viewBox="0 0 130 130">
      <circle cx="65" cy="65" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
      <circle
        cx="65" cy="65" r={r} fill="none"
        stroke={color} strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${filled} ${circ}`}
        transform="rotate(-90 65 65)"
        style={{ transition: "stroke-dasharray 0.8s ease" }}
      />
      <text x="65" y="60" textAnchor="middle" fill={color} fontSize="28" fontWeight="700">
        {Math.round(score)}
      </text>
      <text x="65" y="78" textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="11">
        / 100
      </text>
    </svg>
  );
}

// ─── Check card ───────────────────────────────────────────────────────────────
interface CheckCardProps {
  title: string;
  score: number | null;
  data: Record<string, any>;
  weight: number;
}

function CheckCard({ title, score, data, weight }: CheckCardProps) {
  const [open, setOpen] = useState(false);
  const s = score ?? 0;
  const color = s >= 70 ? "var(--success)" : s >= 40 ? "var(--warning)" : "var(--danger)";
  const bgColor = s >= 70 ? "var(--success-bg)" : s >= 40 ? "rgba(245,158,11,0.1)" : "var(--danger-bg)";

  const keyItems = Object.entries(data || {})
    .filter(([k, v]) => k !== "score" && k !== "errors" && typeof v !== "object" && v !== null)
    .slice(0, 5);

  const errors = (data?.errors || []) as string[];

  return (
    <div className="check-card" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="check-card-header" onClick={() => setOpen(!open)} style={{ cursor: "pointer" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
          <div className="check-score-badge" style={{ background: bgColor, color }}>
            {Math.round(s)}
          </div>
          <div>
            <div className="check-title">{title}</div>
            <div className="check-weight">Weight: {weight}%</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="check-bar-wrap">
            <div className="check-bar-fill" style={{ width: `${s}%`, background: color }} />
          </div>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
            style={{ transform: open ? "rotate(180deg)" : "none", transition: ".2s", color: "var(--text-hint)" }}>
            <path d="M2 5l5 5 5-5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
        </div>
      </div>

      {open && (
        <div className="check-card-body">
          {keyItems.map(([k, v]) => (
            <div key={k} className="check-kv">
              <span className="check-k">{k.replace(/_/g, " ")}</span>
              <span className="check-v">{String(v)}</span>
            </div>
          ))}
          {errors.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {errors.map((e, i) => (
                <div key={i} className="check-error">{e}</div>
              ))}
            </div>
          )}
          {keyItems.length === 0 && errors.length === 0 && (
            <div style={{ color: "var(--text-hint)", fontSize: 12 }}>No detail available</div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Check definitions ────────────────────────────────────────────────────────
const CHECKS = [
  { key: "dns",         title: "DNS Records",       weight: 15 },
  { key: "https",       title: "HTTPS & Redirect",  weight: 20 },
  { key: "meta",        title: "Title & Meta",       weight: 20 },
  { key: "ssl",         title: "SSL Certificate",    weight: 15 },
  { key: "speed",       title: "Page Speed",         weight: 10 },
  { key: "robots",      title: "Robots.txt",         weight:  5 },
  { key: "sitemap",     title: "Sitemap.xml",        weight:  5 },
  { key: "mobile",      title: "Mobile Friendly",    weight:  5 },
  { key: "social_meta", title: "Social Meta (OG)",   weight:  3 },
  { key: "headings",    title: "Heading Structure",  weight:  2 },
];

// ─── Main page ────────────────────────────────────────────────────────────────
export default function SEOCheckerPage() {
  const [domain, setDomain] = useState("");
  const [isChecking, setIsChecking] = useState(false);
  const [result, setResult] = useState<SEOCheckResult | null>(null);
  const [error, setError] = useState("");

  const handleCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) return;
    setIsChecking(true);
    setError("");
    setResult(null);
    try {
      const res = await SEOService.checkDomain(domain.trim());
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Check failed. Make sure the domain is valid.");
    } finally {
      setIsChecking(false);
    }
  };

  const scoreLabel = (s: number) =>
    s >= 70 ? "Good" : s >= 40 ? "Needs Work" : "Poor";

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">SEO Checker</h1>
        <p className="page-subtitle">Run a full SEO audit on any domain — instant results</p>
      </div>

      {/* Input */}
      <form onSubmit={handleCheck} style={{ display: "flex", gap: 10, marginBottom: 24, maxWidth: 560 }}>
        <input
          type="text"
          value={domain}
          onChange={e => setDomain(e.target.value)}
          placeholder="e.g. example.com"
          style={{ flex: 1, height: 42 }}
          disabled={isChecking}
        />
        <button
          type="submit"
          className="btn-primary"
          style={{ width: "auto", padding: "0 24px", height: 42 }}
          disabled={isChecking || !domain.trim()}
        >
          {isChecking ? <span className="btn-spinner" /> : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.3"/>
              <path d="M10 10l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
          )}
          {isChecking ? "Checking…" : "Check SEO"}
        </button>
      </form>

      {isChecking && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--text-muted)", marginBottom: 24 }}>
          <div className="spinner" />
          <span>Running 10 SEO checks on <strong style={{ color: "var(--text)" }}>{domain}</strong> — this takes 10–20 seconds…</span>
        </div>
      )}

      {error && <div className="alert alert-error" style={{ marginBottom: 20 }}>{error}</div>}

      {result && (
        <div>
          {/* Score summary */}
          <div className="seo-summary">
            <div className="seo-ring-wrap">
              <ScoreRing score={result.overall_score} />
              <div style={{ marginTop: 8, textAlign: "center" }}>
                <div style={{ fontSize: 16, fontWeight: 600 }}>{result.domain}</div>
                <div style={{
                  fontSize: 13, marginTop: 4,
                  color: result.overall_score >= 70 ? "var(--success)" :
                         result.overall_score >= 40 ? "var(--warning)" : "var(--danger)"
                }}>
                  {scoreLabel(result.overall_score)}
                </div>
              </div>
            </div>

            <div className="seo-scores-grid">
              {CHECKS.map(c => {
                const s = result.checks[c.key as keyof typeof result.checks]?.score ?? 0;
                const color = s >= 70 ? "var(--success)" : s >= 40 ? "var(--warning)" : "var(--danger)";
                return (
                  <div key={c.key} className="mini-score">
                    <div className="mini-score-val" style={{ color }}>{Math.round(s)}</div>
                    <div className="mini-score-label">{c.title}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Check cards */}
          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-muted)", marginBottom: 12, textTransform: "uppercase", letterSpacing: ".06em" }}>
              Detailed Results — click any card to expand
            </div>
            <div className="checks-list">
              {CHECKS.map(c => (
                <CheckCard
                  key={c.key}
                  title={c.title}
                  weight={c.weight}
                  score={result.checks[c.key as keyof typeof result.checks]?.score ?? 0}
                  data={result.checks[c.key as keyof typeof result.checks] ?? {}}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
