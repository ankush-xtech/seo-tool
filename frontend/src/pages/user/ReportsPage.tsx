import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../services/api";

interface ExportConfig {
  type: "domains" | "seo_audit";
  tld: string;
  status: string;
  min_score: string;
  max_score: string;
}

function buildExportUrl(config: ExportConfig): string {
  const base = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
  const params = new URLSearchParams();
  if (config.tld) params.set("tld", config.tld);
  if (config.status && config.type === "domains") params.set("status", config.status);
  if (config.min_score) params.set("min_score", config.min_score);
  if (config.max_score && config.type === "domains") params.set("max_score", config.max_score);

  const endpoint = config.type === "domains" ? "domains/csv" : "seo-audit/csv";
  return `${base}/reports/${endpoint}?${params}`;
}

const TLDS = ["", "com", "net", "org", "io", "co", "app", "dev", "ai"];
const STATUSES = ["", "pending", "running", "done", "failed"];

export default function ReportsPage() {
  const [config, setConfig] = useState<ExportConfig>({
    type: "domains",
    tld: "",
    status: "done",
    min_score: "",
    max_score: "",
  });
  const [digestSending, setDigestSending] = useState(false);
  const [digestMsg, setDigestMsg] = useState("");

  const { data: summary } = useQuery({
    queryKey: ["report-summary"],
    queryFn: async () => {
      const { data } = await api.get("/reports/summary");
      return data;
    },
  });

  const set = (k: keyof ExportConfig) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setConfig(c => ({ ...c, [k]: e.target.value }));

  const handleExport = () => {
    const url = buildExportUrl(config);
    window.open(url, "_blank");
  };

  const handleDigest = async () => {
    setDigestSending(true);
    setDigestMsg("");
    try {
      const { data } = await api.post("/reports/digest/send");
      setDigestMsg(data.message);
    } catch (err: any) {
      setDigestMsg(err?.response?.data?.detail || "Failed to send digest");
    } finally {
      setDigestSending(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Reports & Exports</h1>
        <p className="page-subtitle">Download data as CSV or trigger email digests</p>
      </div>

      {/* Summary stats */}
      {summary && (
        <div className="stats-grid" style={{ marginBottom: 24 }}>
          <div className="stat-card">
            <div className="stat-label">Total domains</div>
            <div className="stat-value">{summary.total_domains?.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Checked domains</div>
            <div className="stat-value" style={{ color: "var(--success)" }}>{summary.checked?.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg SEO score</div>
            <div className="stat-value">{summary.avg_seo_score ?? "—"}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Report date</div>
            <div className="stat-value" style={{ fontSize: 16 }}>{summary.date}</div>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* Export Builder */}
        <div className="chart-card" style={{ gridColumn: "span 1" }}>
          <div className="chart-title">Export builder</div>

          <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 8 }}>
            <div className="field">
              <label>Export type</label>
              <select value={config.type} onChange={set("type")} className="filter-select" style={{ width: "100%", height: 40 }}>
                <option value="domains">Domain list (all fields)</option>
                <option value="seo_audit">SEO audit results (scores per check)</option>
              </select>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="field">
                <label>TLD filter</label>
                <select value={config.tld} onChange={set("tld")} className="filter-select" style={{ width: "100%", height: 40 }}>
                  {TLDS.map(t => <option key={t} value={t}>{t ? `.${t}` : "All TLDs"}</option>)}
                </select>
              </div>
              {config.type === "domains" && (
                <div className="field">
                  <label>Status filter</label>
                  <select value={config.status} onChange={set("status")} className="filter-select" style={{ width: "100%", height: 40 }}>
                    {STATUSES.map(s => <option key={s} value={s}>{s || "All statuses"}</option>)}
                  </select>
                </div>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="field">
                <label>Min score</label>
                <input type="number" value={config.min_score} onChange={set("min_score")}
                  placeholder="e.g. 60" min="0" max="100" />
              </div>
              {config.type === "domains" && (
                <div className="field">
                  <label>Max score</label>
                  <input type="number" value={config.max_score} onChange={set("max_score")}
                    placeholder="e.g. 100" min="0" max="100" />
                </div>
              )}
            </div>

            <button className="btn-primary" onClick={handleExport} style={{ marginTop: 4 }}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1v8M4 6l3 3 3-3M2 11v1a1 1 0 001 1h8a1 1 0 001-1v-1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Download CSV
            </button>
          </div>
        </div>

        {/* Quick exports + Digest */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Quick exports */}
          <div className="chart-card">
            <div className="chart-title">Quick exports</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
              {[
                { label: "All domains today", url: `/reports/domains/csv?date_from=${new Date().toISOString().split("T")[0]}` },
                { label: "High-scoring domains (70+)", url: "/reports/domains/csv?min_score=70&status=done" },
                { label: "Failed checks", url: "/reports/domains/csv?status=failed" },
                { label: "Full SEO audit export", url: "/reports/seo-audit/csv" },
              ].map(item => (
                <button key={item.label} className="btn-secondary"
                  style={{ justifyContent: "flex-start", fontSize: 13 }}
                  onClick={() => {
                    const base = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
                    window.open(`${base}${item.url}`, "_blank");
                  }}>
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                    <path d="M6.5 1v7M4 5.5l2.5 2.5 2.5-2.5M2 10v1a1 1 0 001 1h7a1 1 0 001-1v-1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Email digest */}
          <div className="chart-card">
            <div className="chart-title">Email digest</div>
            <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 6, marginBottom: 14, lineHeight: 1.6 }}>
              Send a summary email with today's domain stats, top TLDs, and score distribution to your admin email.
            </p>
            {digestMsg && (
              <div className={`alert ${digestMsg.includes("not") ? "alert-error" : "alert-success"}`} style={{ marginBottom: 12 }}>
                {digestMsg}
              </div>
            )}
            <button className="btn-primary" onClick={handleDigest} disabled={digestSending}>
              {digestSending ? <span className="btn-spinner" /> : (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M1 1l6 5.5L13 1M1 1h12v10a1 1 0 01-1 1H2a1 1 0 01-1-1V1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                </svg>
              )}
              {digestSending ? "Sending…" : "Send digest now"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
