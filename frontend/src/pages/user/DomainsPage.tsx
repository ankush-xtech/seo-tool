import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import DomainService, { DomainFilters, DomainStatus, Domain, ImportCsvResponse } from "../../services/domain.service";
import { useAuth } from "../../context/AuthContext";
import api from "../../services/api";

// Type for recently checked domain from progress endpoint
interface RecentlyChecked {
  id: number;
  name: string;
  check_status: string;
  seo_score: number;
  verdict: string;
  email: string | null;
  phone: string | null;
  checked_at: string;
}

const STATUS_COLORS: Record<DomainStatus, string> = {
  pending: "badge-warning",
  running: "badge-info",
  done: "badge-success",
  failed: "badge-danger",
  skipped: "badge-neutral",
};

const VERDICT_COLORS: Record<string, { bg: string; color: string }> = {
  "SEO Required":      { bg: "rgba(239,68,68,0.12)",    color: "#ef4444" },
  "Needs Improvement": { bg: "rgba(245,158,11,0.12)",   color: "#f59e0b" },
  "Good Foundation":   { bg: "rgba(34,197,94,0.12)",    color: "#22c55e" },
  "Unreachable":       { bg: "rgba(255,255,255,0.05)",  color: "#5a6278" },
};

const TLDS = ["com", "net", "org", "io", "co", "app", "dev", "ai", "info"];

// ─── Fetch Modal ─────────────────────────────────────────────────────────────
interface FetchResult {
  status: string; message: string; fetch_date: string;
  total_fetched: number; new_domains: number; duplicates_skipped: number;
  duration_seconds: number; seo_check_count?: number;
}

function ImportCsvModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<ImportCsvResponse | null>(null);
  const [error, setError] = useState("");

  const getImportErrorMessage = (err: any) => {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail;

    if (status === 404) {
      return "Import API not found (404): backend is running old code. Restart backend server and try again.";
    }
    if (status === 400) {
      return detail || "Invalid CSV file. Ensure first column contains domain names.";
    }
    if (status === 401) {
      return "Session expired. Please login again.";
    }
    if (status === 413) {
      return "CSV file is too large. Please upload a smaller file.";
    }
    return detail || `Import failed${status ? ` (HTTP ${status})` : ""}`;
  };

  const handleImport = async () => {
    if (!file) return;
    const isCsv = file.name.toLowerCase().endsWith(".csv") || file.type === "text/csv";
    if (!isCsv) {
      setError("Invalid file type. Please select a .csv file.");
      return;
    }

    setIsImporting(true);
    setError("");
    setResult(null);
    try {
      const data = await DomainService.importCsv(file);
      setResult(data);
      onDone();
    } catch (err: any) {
      setError(getImportErrorMessage(err));
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && !isImporting && onClose()}>
      <div className="modal" style={{ maxWidth: 680 }}>
        <h2 className="modal-title">Import CSV Domains</h2>

        {!result ? (
          <>
            <div style={{ background: "var(--bg3)", borderRadius: "var(--radius-sm)", padding: "10px 12px", marginBottom: 14, fontSize: 12, color: "var(--text-muted)" }}>
              Upload a CSV where the first column contains domain names.
              Header is optional (for example: <strong style={{ color: "var(--text)" }}>domain</strong>).
            </div>

            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const selected = e.target.files?.[0] || null;
                setFile(selected);
                if (!selected) {
                  setError("");
                  return;
                }
                const isCsv = selected.name.toLowerCase().endsWith(".csv") || selected.type === "text/csv";
                setError(isCsv ? "" : "Invalid file type. Please select a .csv file.");
              }}
              disabled={isImporting}
              style={{ marginBottom: 12 }}
            />

            {file && (
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10 }}>
                Selected: <strong style={{ color: "var(--text)" }}>{file.name}</strong>
              </div>
            )}

            {error && <div className="alert alert-error" style={{ marginBottom: 12 }}>{error}</div>}

            <div className="modal-actions">
              <button className="btn-secondary" onClick={onClose} disabled={isImporting}>Cancel</button>
              <button className="btn-primary" style={{ width: "auto", padding: "0 20px" }} onClick={handleImport} disabled={!file || isImporting}>
                {isImporting ? "Importing…" : "Import CSV"}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="alert alert-success" style={{ marginBottom: 14 }}>
              Import completed for {result.filename}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0,1fr))", gap: 8, marginBottom: 14 }}>
              {[
                { label: "Rows", value: result.total_rows },
                { label: "Valid", value: result.valid_rows },
                { label: "Imported", value: result.imported_count },
                { label: "Duplicate", value: result.duplicate_count },
                { label: "Invalid", value: result.invalid_count },
              ].map((item) => (
                <div key={item.label} style={{ background: "var(--bg3)", borderRadius: "var(--radius-sm)", padding: "10px 12px" }}>
                  <div style={{ fontSize: 11, color: "var(--text-hint)", marginBottom: 3 }}>{item.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 600 }}>{item.value.toLocaleString()}</div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Import report (first {result.report_rows.length} rows)</div>
            <div style={{ maxHeight: 260, overflowY: "auto", border: "0.5px solid var(--border)", borderRadius: "var(--radius-sm)", marginBottom: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>Domain</th>
                    <th>Status</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.report_rows.map((row, idx) => (
                    <tr key={`${row.domain}-${idx}`}>
                      <td>{row.domain}</td>
                      <td>{row.status}</td>
                      <td>{row.reason || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {result.report_truncated && (
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
                Report truncated to first 500 rows.
              </div>
            )}

            <div className="modal-actions">
              <button className="btn-primary" style={{ width: "auto", padding: "0 20px" }} onClick={onClose}>
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function FetchModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const today = new Date();
  const getDate = (n: number) => {
    const d = new Date(today); d.setDate(d.getDate() - n);
    return d.toISOString().split("T")[0];
  };
  const [fetchDate, setFetchDate] = useState(getDate(1));
  const [isFetching, setIsFetching] = useState(false);
  const [result, setResult] = useState<FetchResult | null>(null);
  const [error, setError] = useState("");

  const quickDates = [
    { label: "Yesterday", value: getDate(1) },
    { label: "2 days ago", value: getDate(2) },
    { label: "3 days ago", value: getDate(3) },
  ];

  const handleFetch = async () => {
    setIsFetching(true); setError(""); setResult(null);
    try {
      const { data } = await api.post(`/fetch/run?fetch_date=${fetchDate}`);
      setResult(data);
      if (data.status === "success") onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Fetch failed");
    } finally { setIsFetching(false); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && !isFetching && onClose()}>
      <div className="modal" style={{ maxWidth: 500 }}>
        <h2 className="modal-title">Fetch New Domains from WhoisDS</h2>
        {!result ? (
          <>
            <div style={{ background: "var(--accent-bg)", border: "0.5px solid rgba(79,124,248,0.25)",
              borderRadius: "var(--radius-sm)", padding: "10px 14px", fontSize: 12,
              color: "var(--text-muted)", lineHeight: 1.7, marginBottom: 18 }}>
              Downloads ~70,000 newly registered domains from <strong style={{ color: "var(--accent)" }}>whoisds.com</strong>,
              stores them in your database, then <strong style={{ color: "var(--text)" }}>checks ALL domains</strong> for
              SEO issues, email and phone — running in background batches of 100.
            </div>

            <div className="field" style={{ marginBottom: 12 }}>
              <label>Date to fetch</label>
              <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                {quickDates.map(opt => (
                  <button key={opt.value} className="btn-secondary"
                    style={{ fontSize: 12, padding: "0 10px", height: 30,
                      background: fetchDate === opt.value ? "var(--accent-bg)" : "",
                      borderColor: fetchDate === opt.value ? "var(--accent)" : "",
                      color: fetchDate === opt.value ? "var(--accent)" : "" }}
                    onClick={() => setFetchDate(opt.value)} disabled={isFetching}>
                    {opt.label}
                  </button>
                ))}
              </div>
              <input type="date" value={fetchDate} max={getDate(1)}
                onChange={e => setFetchDate(e.target.value)} disabled={isFetching}
                style={{ height: 38, padding: "0 12px", width: "100%",
                  background: "var(--bg3)", border: "0.5px solid var(--border)",
                  borderRadius: "var(--radius-sm)", color: "var(--text)" }} />
            </div>

            {error && <div className="alert alert-error" style={{ marginBottom: 14 }}>{error}</div>}

            {isFetching && (
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px",
                background: "var(--bg3)", borderRadius: "var(--radius-sm)", marginBottom: 16 }}>
                <div className="spinner" style={{ flexShrink: 0 }} />
                <div>
                  <div style={{ fontWeight: 500, fontSize: 13 }}>Downloading from WhoisDS.com…</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>
                    This takes 30–90 seconds. Do not close this window.
                  </div>
                </div>
              </div>
            )}

            <div className="modal-actions">
              <button className="btn-secondary" onClick={onClose} disabled={isFetching}>Cancel</button>
              <button className="btn-primary" style={{ width: "auto", padding: "0 24px" }}
                onClick={handleFetch} disabled={isFetching || !fetchDate}>
                {isFetching ? <span className="btn-spinner" /> : null}
                {isFetching ? "Downloading…" : `Fetch ${fetchDate}`}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className={`alert ${result.status === "success" ? "alert-success" : "alert-error"}`}
              style={{ marginBottom: 20 }}>{result.message}</div>
            {result.status === "success" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
                {[
                  { label: "Total in ZIP",       value: result.total_fetched.toLocaleString(),        color: "var(--text)" },
                  { label: "New domains added",   value: result.new_domains.toLocaleString(),          color: "var(--success)" },
                  { label: "Duplicates skipped",  value: result.duplicates_skipped.toLocaleString(),   color: "var(--text-muted)" },
                  { label: "Checking in BG",      value: `All ${(result as any).total_pending_check?.toLocaleString() || "—"} domains`, color: "var(--accent)" },
                ].map(item => (
                  <div key={item.label} style={{ background: "var(--bg3)",
                    borderRadius: "var(--radius-sm)", padding: "12px 14px" }}>
                    <div style={{ fontSize: 11, color: "var(--text-hint)", marginBottom: 4 }}>{item.label}</div>
                    <div style={{ fontSize: 20, fontWeight: 600, color: item.color }}>{item.value}</div>
                  </div>
                ))}
              </div>
            )}
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16, lineHeight: 1.6 }}>
              SEO checks are running in the background. The domain list will update automatically every 10 seconds.
            </div>
            <div className="modal-actions">
              <button className="btn-primary" style={{ width: "auto", padding: "0 24px" }} onClick={onClose}>
                View Domains
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── SEO Result Detail Drawer ─────────────────────────────────────────────────
function DomainDetailDrawer({ domain, onClose }: { domain: Domain; onClose: () => void }) {
  const { data: results } = useQuery({
    queryKey: ["seo-results", domain.id],
    queryFn: async () => {
      const { data } = await api.get(`/seo/results/${domain.id}`);
      return data;
    },
    enabled: !!domain.id,
  });

  const latest = results?.[0];
  const meta = latest?.dns_data || {};

  const scoreColor = (s: number) => s >= 70 ? "#22c55e" : s >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 520 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
          <div>
            <h2 className="modal-title" style={{ marginBottom: 4 }}>{domain.name}</h2>
            <a href={`https://${domain.name}`} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 12, color: "var(--accent)" }}>Open website ↗</a>
          </div>
          <button className="btn-secondary" style={{ padding: "0 10px", height: 30, fontSize: 12 }}
            onClick={onClose}>Close</button>
        </div>

        {!latest ? (
          <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)", fontSize: 13 }}>
            {domain.check_status === "pending"
              ? "SEO check is pending — check back in a few minutes"
              : "No SEO data available"}
          </div>
        ) : (
          <>
            {/* Score */}
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20,
              background: "var(--bg3)", borderRadius: "var(--radius-sm)", padding: "14px 16px" }}>
              <div style={{ fontSize: 42, fontWeight: 700,
                color: scoreColor(latest.overall_score || 0) }}>
                {latest.overall_score || 0}
              </div>
              <div>
                <div style={{ fontWeight: 500, fontSize: 15 }}>
                  {meta.verdict || "—"}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>
                  {meta.reachable ? "Website is reachable" : "Website unreachable"}
                </div>
              </div>
            </div>

            {/* Contact info */}
            {(meta.email || meta.phone) && (
              <div style={{ background: "rgba(79,124,248,0.08)", border: "0.5px solid rgba(79,124,248,0.2)",
                borderRadius: "var(--radius-sm)", padding: "10px 14px", marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--accent)",
                  textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 8 }}>
                  Contact Info Found
                </div>
                {meta.email && (
                  <div style={{ fontSize: 13, marginBottom: 4, display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ color: "var(--text-muted)", width: 50 }}>Email</span>
                    <a href={`mailto:${meta.email}`} style={{ color: "var(--accent)" }}>{meta.email}</a>
                  </div>
                )}
                {meta.phone && (
                  <div style={{ fontSize: 13, display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ color: "var(--text-muted)", width: 50 }}>Phone</span>
                    <a href={`tel:${meta.phone}`} style={{ color: "var(--accent)" }}>{meta.phone}</a>
                  </div>
                )}
              </div>
            )}

            {/* SEO Checks */}
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-hint)",
              textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 10 }}>
              SEO Checks
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {[
                { label: "HTTPS", score: latest.https_score },
                { label: "Meta description", score: latest.meta_score },
                { label: "H1 heading", score: latest.heading_score },
                { label: "Mobile viewport", score: latest.mobile_score },
              ].map(item => {
                const s = item.score ?? 0;
                const status = s >= 80 ? "pass" : s >= 40 ? "warn" : "fail";
                const color = status === "pass" ? "#22c55e" : status === "warn" ? "#f59e0b" : "#ef4444";
                const icon = status === "pass" ? "✓" : status === "warn" ? "!" : "✗";
                return (
                  <div key={item.label} style={{ display: "flex", alignItems: "center",
                    justifyContent: "space-between", padding: "8px 12px",
                    background: "var(--bg3)", borderRadius: "var(--radius-sm)" }}>
                    <span style={{ fontSize: 13 }}>{item.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color,
                      background: `${color}18`, padding: "2px 10px", borderRadius: 10 }}>
                      {icon} {status}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Title + Description */}
            {(meta.title || meta.description) && (
              <div style={{ marginTop: 16, padding: "12px 14px",
                background: "var(--bg3)", borderRadius: "var(--radius-sm)" }}>
                {meta.title && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 11, color: "var(--text-hint)", marginBottom: 3 }}>PAGE TITLE</div>
                    <div style={{ fontSize: 13 }}>{meta.title}</div>
                  </div>
                )}
                {meta.description && (
                  <div>
                    <div style={{ fontSize: 11, color: "var(--text-hint)", marginBottom: 3 }}>META DESCRIPTION</div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>{meta.description}</div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Live Check Progress Bar ─────────────────────────────────────────────────
function CheckProgressBar({ onRecentlyChecked }: { onRecentlyChecked?: (items: RecentlyChecked[]) => void }) {
  const lastSinceRef = useRef<string | null>(null);

  const { data, refetch } = useQuery({
    queryKey: ["check-progress"],
    queryFn: async () => {
      const params = lastSinceRef.current ? `?since=${encodeURIComponent(lastSinceRef.current)}` : "";
      const { data } = await api.get(`/fetch/check-progress${params}`);
      return data;
    },
    refetchInterval: (query) => ((query.state.data as any)?.running ? 2000 : 10000),
  });

  // Forward recently checked domains to parent for live table updates
  useEffect(() => {
    if (data?.recently_checked?.length && onRecentlyChecked) {
      onRecentlyChecked(data.recently_checked);
      // Set the watermark so next poll only gets new items
      const latest = data.recently_checked[data.recently_checked.length - 1];
      lastSinceRef.current = latest.checked_at;
    }
  }, [data?.recently_checked]);

  if (!data || (!data.running && data.total === 0)) return null;

  const done = (data.done || 0) + (data.failed || 0);
  const total = data.total || 0;
  const percent = data.percent || 0;
  const reachable = data.done || 0;
  const failed = data.failed || 0;
  const running = data.running_in_db || 0;

  return (
    <div style={{
      background: "var(--bg2)", border: "0.5px solid var(--border)",
      borderRadius: "var(--radius)", padding: "14px 18px", marginBottom: 16,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {data.running ? (
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)",
              display: "inline-block", animation: "pulse 1.5s infinite" }} />
          ) : (
            <span style={{ fontSize: 14 }}>✅</span>
          )}
          <span style={{ fontSize: 13, fontWeight: 500 }}>
            {data.running ? "SEO checks running…" : "SEO checks complete"}
          </span>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
          {done.toLocaleString()} / {total.toLocaleString()} domains checked ({percent}%)
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: 6, background: "var(--bg3)", borderRadius: 3, overflow: "hidden", marginBottom: 10 }}>
        <div style={{
          height: "100%", borderRadius: 3,
          width: `${percent}%`,
          background: data.running
            ? "linear-gradient(90deg, var(--accent), #7c3aed)"
            : "var(--success)",
          transition: "width 0.5s ease",
        }} />
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: 20, fontSize: 12, color: "var(--text-muted)" }}>
        <span>✓ <strong style={{ color: "var(--success)" }}>{reachable.toLocaleString()}</strong> reachable</span>
        <span>✗ <strong style={{ color: "var(--danger)" }}>{failed.toLocaleString()}</strong> unreachable</span>
        {running > 0 && (
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} />
            <strong style={{ color: "var(--accent)" }}>{running.toLocaleString()}</strong> checking now
          </span>
        )}
        <span>⏳ <strong style={{ color: "var(--warning)" }}>{(data.pending_in_db || 0).toLocaleString()}</strong> still pending</span>
        {!data.running && data.pending_in_db > 0 && (
          <button className="btn-secondary" style={{ fontSize: 11, padding: "0 10px", height: 22, marginLeft: "auto" }}
            onClick={async () => {
              await api.post("/fetch/check-pending");
              refetch();
            }}>
            Resume checking
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Main Domains Page ────────────────────────────────────────────────────────
export default function DomainsPage() {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState<DomainFilters>({
    page: 1, per_page: 50, sort_by: "fetched_date", sort_dir: "desc",
  });
  const [showFetchModal, setShowFetchModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [selectedDomain, setSelectedDomain] = useState<Domain | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Track live status updates from progress endpoint
  const [liveUpdates, setLiveUpdates] = useState<Map<number, RecentlyChecked>>(new Map());
  // Track IDs that were recently updated (for highlight animation)
  const [recentIds, setRecentIds] = useState<Set<number>>(new Set());

  const handleRecentlyChecked = useCallback((items: RecentlyChecked[]) => {
    if (!items.length) return;
    setLiveUpdates(prev => {
      const next = new Map(prev);
      items.forEach(item => next.set(item.id, item));
      return next;
    });
    // Mark as recently changed for highlight
    const newIds = new Set(items.map(i => i.id));
    setRecentIds(prev => new Set([...prev, ...newIds]));
    // Clear highlight after 3 seconds
    setTimeout(() => {
      setRecentIds(prev => {
        const next = new Set(prev);
        newIds.forEach(id => next.delete(id));
        return next;
      });
    }, 3000);
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["domains", filters],
    queryFn: () => DomainService.list(filters),
    refetchInterval: autoRefresh ? 5_000 : false,
  });

  // Clear live updates when fresh data arrives from server (it already includes the updates)
  useEffect(() => {
    if (data) setLiveUpdates(new Map());
  }, [data]);

  const { data: stats } = useQuery({
    queryKey: ["domain-stats"],
    queryFn: DomainService.getStats,
    refetchInterval: autoRefresh ? 10_000 : 15_000,
  });

  // Auto-enable refresh when pending > 0
  useEffect(() => {
    if (stats && stats.pending_check > 0) setAutoRefresh(true);
    else setAutoRefresh(false);
  }, [stats?.pending_check]);

  // Filter changes (TLD, status, search, sort) always reset to page 1
  const setFilter = (key: keyof DomainFilters, value: any) =>
    setFilters(f => ({ ...f, [key]: value, page: 1 }));

  // Page changes only — do NOT reset to page 1
  const setPage = (page: number) =>
    setFilters(f => ({ ...f, page }));

  const handleFetchDone = () => {
    setAutoRefresh(true);
    queryClient.invalidateQueries({ queryKey: ["domains"] });
    queryClient.invalidateQueries({ queryKey: ["domain-stats"] });
  };

  const getVerdictFromResult = (domain: Domain): string | null => {
    if (domain.check_status === "pending") return null;
    if (domain.check_status === "failed") return "Unreachable";
    if (domain.seo_score === null) return null;
    if (domain.seo_score >= 75) return "Good Foundation";
    if (domain.seo_score >= 50) return "Needs Improvement";
    return "SEO Required";
  };

  const scoreBarColor = (score: number | null) => {
    if (score === null) return "var(--text-hint)";
    if (score >= 70) return "var(--success)";
    if (score >= 40) return "var(--warning)";
    return "var(--danger)";
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{
        display: "flex", alignItems: "flex-start",
        justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="page-title">Domains</h1>
          <p className="page-subtitle" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            Newly registered domains — fetched from WhoisDS.com daily
            {autoRefresh && (
              <span style={{ display: "flex", alignItems: "center", gap: 5,
                fontSize: 11, color: "var(--accent)",
                background: "var(--accent-bg)", padding: "2px 8px", borderRadius: 10 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%",
                  background: "var(--accent)", display: "inline-block",
                  animation: "pulse 1.5s ease-in-out infinite" }} />
                Live updating
              </span>
            )}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {isAdmin && stats && stats.pending_check > 0 && (
            <button className="btn-secondary" style={{ fontSize: 12 }}
              onClick={async () => {
                await api.post(`/fetch/check-pending?count=100`);
                setAutoRefresh(true);
              }}>
              Check {stats.pending_check.toLocaleString()} pending
            </button>
          )}
          <button className="btn-secondary" onClick={() => {
            DomainService.exportCsv({ tld: filters.tld, status: filters.status, min_score: filters.min_score, date_from: filters.date_from, date_to: filters.date_to });
          }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1v8M4 6l3 3 3-3M2 10v2a1 1 0 001 1h8a1 1 0 001-1v-2"
                stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Export CSV
          </button>
          {isAdmin && (
            <button className="btn-secondary" onClick={() => setShowImportModal(true)}>
              Import CSV
            </button>
          )}
          {isAdmin && (
            <button className="btn-primary" style={{ width: "auto", padding: "0 16px" }}
              onClick={() => setShowFetchModal(true)}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M7 1.5S5 4 5 7s2 5.5 2 5.5M7 1.5S9 4 9 7s-2 5.5-2 5.5M1.5 7h11"
                  stroke="currentColor" strokeWidth="1.3"/>
              </svg>
              Fetch New Domains
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="stats-grid" style={{ marginBottom: 20 }}>
          {[
            { label: "Total domains", value: stats.total_domains.toLocaleString(), color: "var(--text)" },
            { label: "Fetched today", value: stats.fetched_today.toLocaleString(), color: "var(--accent)" },
            { label: "Pending check", value: stats.pending_check.toLocaleString(), color: "var(--warning)" },
            { label: "SEO checked", value: stats.checked.toLocaleString(), color: "var(--success)" },
            ...(stats.avg_seo_score !== null ? [{ label: "Avg score", value: String(stats.avg_seo_score), color: "var(--text)" }] : []),
          ].map(s => (
            <div key={s.label} className="stat-card">
              <div className="stat-label">{s.label}</div>
              <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Live SEO Check Progress Bar */}
      <CheckProgressBar onRecentlyChecked={handleRecentlyChecked} />

      {/* Filters */}
      <div className="filter-bar">
        <input type="text" placeholder="Search domain…" value={filters.search || ""}
          onChange={e => setFilter("search", e.target.value || undefined)} style={{ width: 200 }} />
        <select value={filters.tld || ""} onChange={e => setFilter("tld", e.target.value || undefined)}
          className="filter-select">
          <option value="">All TLDs</option>
          {TLDS.map(t => <option key={t} value={t}>.{t}</option>)}
        </select>
        <select value={filters.status || ""}
          onChange={e => setFilter("status", (e.target.value || undefined) as any)} className="filter-select">
          <option value="">All statuses</option>
          <option value="pending">Pending check</option>
          <option value="done">Checked</option>
          <option value="failed">Unreachable</option>
        </select>
        <select value={filters.sort_by || "fetched_date"}
          onChange={e => setFilter("sort_by", e.target.value)} className="filter-select">
          <option value="fetched_date">Sort: Date</option>
          <option value="seo_score">Sort: SEO Score</option>
          <option value="name">Sort: Name</option>
        </select>
        <select value={filters.per_page || 50}
          onChange={e => setFilters(f => ({ ...f, per_page: Number(e.target.value), page: 1 }))}
          className="filter-select">
          <option value={25}>25 / page</option>
          <option value={50}>50 / page</option>
          <option value={100}>100 / page</option>
          <option value={200}>200 / page</option>
        </select>
        <button className="btn-secondary" style={{ padding: "0 10px", fontSize: 12 }}
          onClick={() => setFilters({ page: 1, per_page: 50, sort_by: "fetched_date", sort_dir: "desc" })}>
          Clear
        </button>
      </div>

      {/* Domain Table */}
      <div className="table-container" style={{ marginTop: 12 }}>
        <div className="table-header">
          <span className="table-title">
            {data ? `${data.total.toLocaleString()} domains` : "Loading…"}
          </span>
          <span style={{ fontSize: 12, color: "var(--text-hint)" }}>
            Page {filters.page} of {data ? Math.ceil(data.total / (filters.per_page || 50)) : "—"}
          </span>
        </div>

        {isLoading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
        ) : !data?.domains.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">🌐</div>
            <div className="empty-state-title">No domains yet</div>
            <div className="empty-state-text">
              {isAdmin ? 'Click "Fetch New Domains" to pull from WhoisDS.com' : "No domains available yet"}
            </div>
            {isAdmin && (
              <button className="btn-primary" style={{ marginTop: 16, width: "auto", padding: "0 20px" }}
                onClick={() => setShowFetchModal(true)}>
                Fetch New Domains
              </button>
            )}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>TLD</th>
                  <th>SEO Verdict</th>
                  <th>Score</th>
                  <th>Email Found</th>
                  <th>Phone Found</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.domains.map(d => {
                  // Merge live updates from progress polling into table row
                  const live = liveUpdates.get(d.id);
                  const effectiveStatus = (live?.check_status || d.check_status) as DomainStatus;
                  const effectiveScore = live ? live.seo_score : d.seo_score;
                  const isRunning = effectiveStatus === "running";
                  const isJustChecked = recentIds.has(d.id);

                  // Compute verdict using live data if available
                  const verdict = live
                    ? (live.check_status === "failed" ? "Unreachable" : live.verdict)
                    : getVerdictFromResult({ ...d, check_status: effectiveStatus, seo_score: effectiveScore });
                  const vc = verdict ? VERDICT_COLORS[verdict] : null;

                  return (
                    <tr key={d.id} style={{
                      transition: "background 0.5s ease",
                      background: isJustChecked
                        ? "rgba(79,124,248,0.08)"
                        : isRunning
                          ? "rgba(245,158,11,0.05)"
                          : undefined,
                    }}>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, maxWidth: 220 }}>
                        <a href={`https://${d.name}`} target="_blank" rel="noopener noreferrer"
                          style={{ color: "var(--accent)", display: "flex", alignItems: "center", gap: 4 }}>
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 200 }}>
                            {d.name}
                          </span>
                          <svg width="9" height="9" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0 }}>
                            <path d="M2 8L8 2M8 2H4M8 2v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                          </svg>
                        </a>
                      </td>
                      <td><span className="badge badge-neutral">.{d.tld}</span></td>
                      <td>
                        {verdict && vc ? (
                          <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 8px",
                            borderRadius: 10, background: vc.bg, color: vc.color, whiteSpace: "nowrap",
                            transition: "all 0.3s ease" }}>
                            {verdict}
                          </span>
                        ) : isRunning ? (
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 5,
                            fontSize: 11, color: "var(--accent)", fontWeight: 500 }}>
                            <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} />
                            Checking…
                          </span>
                        ) : effectiveStatus === "pending" ? (
                          <span style={{ fontSize: 11, color: "var(--text-hint)" }}>Waiting…</span>
                        ) : "—"}
                      </td>
                      <td>
                        {effectiveScore !== null && effectiveScore !== undefined ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontWeight: 600, fontSize: 13,
                              color: scoreBarColor(effectiveScore), minWidth: 28,
                              transition: "color 0.3s ease" }}>
                              {effectiveScore}
                            </span>
                            <div style={{ width: 50, height: 4, background: "var(--bg3)", borderRadius: 2, overflow: "hidden" }}>
                              <div style={{ height: "100%", borderRadius: 2,
                                width: `${effectiveScore}%`, background: scoreBarColor(effectiveScore),
                                transition: "width 0.5s ease, background 0.3s ease" }} />
                            </div>
                          </div>
                        ) : isRunning ? (
                          <span className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} />
                        ) : <span style={{ color: "var(--text-hint)", fontSize: 12 }}>—</span>}
                      </td>

                      {/* Email + Phone — use live data or lazy load from SEO result */}
                      <td style={{ fontSize: 12 }}>
                        {live?.email ? (
                          <a href={`mailto:${live.email}`} style={{ color: "var(--accent)", fontSize: 11 }}
                            onClick={e => e.stopPropagation()}>
                            {live.email.length > 25 ? live.email.slice(0, 25) + "…" : live.email}
                          </a>
                        ) : (
                          <EmailCell domainId={d.id} checkStatus={effectiveStatus} field="email" />
                        )}
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {live?.phone ? (
                          <a href={`tel:${live.phone}`} style={{ color: "var(--accent)", fontSize: 11 }}
                            onClick={e => e.stopPropagation()}>
                            {live.phone.length > 25 ? live.phone.slice(0, 25) + "…" : live.phone}
                          </a>
                        ) : (
                          <EmailCell domainId={d.id} checkStatus={effectiveStatus} field="phone" />
                        )}
                      </td>

                      <td>
                        {isRunning ? (
                          <span className="badge badge-info" style={{
                            display: "inline-flex", alignItems: "center", gap: 4,
                            animation: "pulse 1.5s infinite",
                          }}>
                            <span className="spinner" style={{ width: 8, height: 8, borderWidth: 1.5,
                              borderColor: "currentColor", borderTopColor: "transparent" }} />
                            running
                          </span>
                        ) : (
                          <span className={`badge ${STATUS_COLORS[effectiveStatus]}`}
                            style={{ transition: "all 0.3s ease" }}>
                            {effectiveStatus}
                          </span>
                        )}
                      </td>
                      <td>
                        {(effectiveStatus === "done" || effectiveStatus === "failed") && (
                          <button className="btn-secondary"
                            style={{ padding: "0 10px", height: 26, fontSize: 11 }}
                            onClick={() => setSelectedDomain({ ...d, check_status: effectiveStatus, seo_score: effectiveScore })}>
                            Details
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total > (filters.per_page || 50) && (() => {
          const currentPage = filters.page || 1;
          const totalPages = Math.ceil(data.total / (filters.per_page || 50));
          // Build visible page numbers (window of 5 around current)
          const pageNums: number[] = [];
          const start = Math.max(1, currentPage - 2);
          const end = Math.min(totalPages, currentPage + 2);
          for (let i = start; i <= end; i++) pageNums.push(i);

          return (
            <div className="pagination" style={{ display: "flex", alignItems: "center", gap: 6,
              justifyContent: "center", padding: "16px 0", flexWrap: "wrap" }}>
              {/* First + Prev */}
              <button className="btn-secondary" style={{ padding: "0 10px", fontSize: 12 }}
                disabled={currentPage <= 1} onClick={() => setPage(1)}>«</button>
              <button className="btn-secondary" style={{ padding: "0 10px", fontSize: 12 }}
                disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>‹ Prev</button>

              {/* Ellipsis before */}
              {start > 1 && (
                <span style={{ fontSize: 12, color: "var(--text-hint)", padding: "0 4px" }}>…</span>
              )}

              {/* Page number buttons */}
              {pageNums.map(n => (
                <button key={n}
                  className={n === currentPage ? "btn-primary" : "btn-secondary"}
                  style={{ padding: "0 10px", minWidth: 34, fontSize: 12,
                    width: "auto",
                    fontWeight: n === currentPage ? 600 : 400 }}
                  onClick={() => setPage(n)}>
                  {n}
                </button>
              ))}

              {/* Ellipsis after */}
              {end < totalPages && (
                <span style={{ fontSize: 12, color: "var(--text-hint)", padding: "0 4px" }}>…</span>
              )}

              {/* Next + Last */}
              <button className="btn-secondary" style={{ padding: "0 10px", fontSize: 12 }}
                disabled={currentPage >= totalPages} onClick={() => setPage(currentPage + 1)}>Next ›</button>
              <button className="btn-secondary" style={{ padding: "0 10px", fontSize: 12 }}
                disabled={currentPage >= totalPages} onClick={() => setPage(totalPages)}>»</button>

              {/* Info */}
              <span style={{ fontSize: 12, color: "var(--text-hint)", marginLeft: 8 }}>
                Page {currentPage} of {totalPages.toLocaleString()} · {data.total.toLocaleString()} domains
              </span>
            </div>
          );
        })()}
      </div>

      {showFetchModal && (
        <FetchModal onClose={() => setShowFetchModal(false)} onDone={handleFetchDone} />
      )}
      {showImportModal && (
        <ImportCsvModal onClose={() => setShowImportModal(false)} onDone={handleFetchDone} />
      )}
      {selectedDomain && (
        <DomainDetailDrawer domain={selectedDomain} onClose={() => setSelectedDomain(null)} />
      )}

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        @keyframes fadeHighlight {
          0% { background: rgba(79,124,248,0.15); }
          100% { background: transparent; }
        }
        tr { transition: background 0.5s ease; }
      `}</style>
    </div>
  );
}

// ─── Email/Phone cell — lazy loads from SEO result ───────────────────────────
function EmailCell({ domainId, checkStatus, field }: {
  domainId: number; checkStatus: DomainStatus; field: "email" | "phone"
}) {
  const enabled = checkStatus === "done";
  const { data } = useQuery({
    queryKey: ["seo-results", domainId],
    queryFn: async () => {
      const { data } = await api.get(`/seo/results/${domainId}`);
      return data;
    },
    enabled,
    staleTime: 300_000,
  });

  if (!enabled) return <span style={{ color: "var(--text-hint)" }}>—</span>;
  if (!data) return <span style={{ color: "var(--text-hint)", fontSize: 11 }}>…</span>;

  const meta = data?.[0]?.dns_data || {};
  const value = meta[field];

  if (!value) return <span style={{ color: "var(--text-hint)" }}>—</span>;

  return (
    <a href={field === "email" ? `mailto:${value}` : `tel:${value}`}
      style={{ color: "var(--accent)", fontSize: 11 }}
      onClick={e => e.stopPropagation()}>
      {value.length > 25 ? value.slice(0, 25) + "…" : value}
    </a>
  );
}
