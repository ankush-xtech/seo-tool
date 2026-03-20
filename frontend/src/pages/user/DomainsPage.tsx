import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import DomainService, { DomainFilters, DomainStatus } from "../../services/domain.service";
import { useAuth } from "../../context/AuthContext";
import { useTaskPoller } from "../../hooks/useTaskPoller";

const STATUS_COLORS: Record<DomainStatus, string> = {
  pending: "badge-warning",
  running: "badge-info",
  done: "badge-success",
  failed: "badge-danger",
  skipped: "badge-neutral",
};

const TLDS = ["com", "net", "org", "io", "co", "app", "dev", "ai", "info"];

export default function DomainsPage() {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState<DomainFilters>({
    page: 1,
    per_page: 50,
    sort_by: "fetched_date",
    sort_dir: "desc",
  });

  const [fetchMsg, setFetchMsg] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isFetching, setIsFetching] = useState(false);

  // Domain list query
  const { data, isLoading } = useQuery({
    queryKey: ["domains", filters],
    queryFn: () => DomainService.list(filters),
  });

  // Stats query
  const { data: stats } = useQuery({
    queryKey: ["domain-stats"],
    queryFn: DomainService.getStats,
    refetchInterval: 15_000,
  });

  // Task poller for manual fetch
  const { status: taskStatus, isPolling, startPolling } = useTaskPoller({
    onSuccess: (result) => {
      setIsFetching(false);
      setFetchMsg(
        `Fetch complete — ${result.new_domains as number} new domains, ` +
        `${result.duplicates_skipped as number} duplicates skipped`
      );
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      queryClient.invalidateQueries({ queryKey: ["domain-stats"] });
    },
    onError: (err) => {
      setIsFetching(false);
      setFetchError(`Fetch failed: ${err}`);
    },
  });

  const handleFetch = async () => {
    setIsFetching(true);
    setFetchMsg(null);
    setFetchError(null);
    try {
      const res = await DomainService.triggerFetch();
      if (res.task_id) {
        startPolling(res.task_id);
      } else {
        setIsFetching(false);
        setFetchMsg("Fetch queued");
      }
    } catch (err: any) {
      setIsFetching(false);
      setFetchError(err?.response?.data?.detail || "Failed to trigger fetch");
    }
  };

  const setFilter = (key: keyof DomainFilters, value: any) => {
    setFilters((f) => ({ ...f, [key]: value, page: 1 }));
  };

  const handleExport = () => {
    const url = DomainService.getExportUrl({
      tld: filters.tld,
      status: filters.status,
      min_score: filters.min_score,
    });
    // Trigger download with auth header via anchor trick
    window.open(url, "_blank");
  };

  const scoreClass = (score: number | null) => {
    if (score === null) return "";
    if (score >= 70) return "score-high";
    if (score >= 40) return "score-mid";
    return "score-low";
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="page-title">Domains</h1>
          <p className="page-subtitle">Newly registered domains — fetched daily</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button className="btn-secondary" onClick={handleExport}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1v8M4 6l3 3 3-3M2 10v2a1 1 0 001 1h8a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Export CSV
          </button>
          {isAdmin && (
            <button
              className="btn-primary"
              style={{ width: "auto", padding: "0 16px" }}
              onClick={handleFetch}
              disabled={isFetching || isPolling}
            >
              {isFetching || isPolling ? <span className="btn-spinner" /> : (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M12 7A5 5 0 112 7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                  <path d="M12 3v4H8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
              {isFetching || isPolling ? "Fetching…" : "Fetch Now"}
            </button>
          )}
        </div>
      </div>

      {/* Fetch status messages */}
      {(fetchMsg || fetchError || isPolling) && (
        <div className={`alert ${fetchError ? "alert-error" : "alert-success"}`} style={{ marginBottom: 16 }}>
          {isPolling && <span className="spinner" style={{ width: 14, height: 14, borderWidth: 1.5 }} />}
          {isPolling
            ? `Running… (status: ${taskStatus?.status || "PENDING"})`
            : fetchError || fetchMsg}
        </div>
      )}

      {/* Stats row */}
      {stats && (
        <div className="stats-grid" style={{ marginBottom: 20 }}>
          <div className="stat-card">
            <div className="stat-label">Total domains</div>
            <div className="stat-value">{stats.total_domains.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Fetched today</div>
            <div className="stat-value" style={{ color: "var(--accent)" }}>{stats.fetched_today.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Pending SEO check</div>
            <div className="stat-value" style={{ color: "var(--warning)" }}>{stats.pending_check.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Checked</div>
            <div className="stat-value" style={{ color: "var(--success)" }}>{stats.checked.toLocaleString()}</div>
          </div>
          {stats.avg_seo_score !== null && (
            <div className="stat-card">
              <div className="stat-label">Avg SEO score</div>
              <div className="stat-value">{stats.avg_seo_score}</div>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="filter-bar">
        <input
          type="text"
          placeholder="Search domain…"
          value={filters.search || ""}
          onChange={(e) => setFilter("search", e.target.value || undefined)}
          style={{ width: 200 }}
        />
        <select
          value={filters.tld || ""}
          onChange={(e) => setFilter("tld", e.target.value || undefined)}
          className="filter-select"
        >
          <option value="">All TLDs</option>
          {TLDS.map((t) => <option key={t} value={t}>.{t}</option>)}
        </select>
        <select
          value={filters.status || ""}
          onChange={(e) => setFilter("status", e.target.value || undefined)}
          className="filter-select"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="done">Done</option>
          <option value="failed">Failed</option>
        </select>
        <select
          value={filters.sort_by || "fetched_date"}
          onChange={(e) => setFilter("sort_by", e.target.value)}
          className="filter-select"
        >
          <option value="fetched_date">Sort: Date</option>
          <option value="seo_score">Sort: Score</option>
          <option value="name">Sort: Name</option>
        </select>
        <button
          className="btn-secondary"
          onClick={() => setFilters({ page: 1, per_page: 50, sort_by: "fetched_date", sort_dir: "desc" })}
          style={{ padding: "0 10px", fontSize: 12 }}
        >
          Clear
        </button>
      </div>

      {/* Table */}
      <div className="table-container" style={{ marginTop: 12 }}>
        <div className="table-header">
          <span className="table-title">
            {data ? `${data.total.toLocaleString()} domains` : "Loading…"}
          </span>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--text-hint)" }}>
              Page {filters.page} of {data ? Math.ceil(data.total / (filters.per_page || 50)) : "—"}
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: "0 auto" }} />
          </div>
        ) : !data?.domains.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">🌐</div>
            <div className="empty-state-title">No domains found</div>
            <div className="empty-state-text">
              {isAdmin ? 'Click "Fetch Now" to pull today\'s newly registered domains.' : "No domains match your filters."}
            </div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th>TLD</th>
                <th>Registrar</th>
                <th>SEO Score</th>
                <th>Status</th>
                <th>Fetched</th>
              </tr>
            </thead>
            <tbody>
              {data.domains.map((d) => (
                <tr key={d.id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                    <a href={`https://${d.name}`} target="_blank" rel="noopener noreferrer"
                       style={{ color: "var(--accent)", display: "flex", alignItems: "center", gap: 5 }}>
                      {d.name}
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M2 8L8 2M8 2H4M8 2v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                      </svg>
                    </a>
                  </td>
                  <td>
                    <span className="badge badge-neutral">.{d.tld}</span>
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: 12 }}>
                    {d.registrar || "—"}
                  </td>
                  <td>
                    {d.seo_score !== null ? (
                      <div className={`score-cell ${scoreClass(d.seo_score)}`}>
                        <span style={{ fontWeight: 500, minWidth: 28 }}>{d.seo_score}</span>
                        <div className="score-bar">
                          <div className="score-fill" style={{ width: `${d.seo_score}%` }} />
                        </div>
                      </div>
                    ) : (
                      <span style={{ color: "var(--text-hint)", fontSize: 12 }}>—</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${STATUS_COLORS[d.check_status]}`}>
                      {d.check_status}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: 12 }}>
                    {new Date(d.fetched_date).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {data && data.total > (filters.per_page || 50) && (
          <div className="pagination">
            <button
              className="btn-secondary"
              disabled={(filters.page || 1) <= 1}
              onClick={() => setFilter("page", (filters.page || 1) - 1)}
            >← Prev</button>
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {filters.page} / {Math.ceil(data.total / (filters.per_page || 50))}
            </span>
            <button
              className="btn-secondary"
              disabled={(filters.page || 1) >= Math.ceil(data.total / (filters.per_page || 50))}
              onClick={() => setFilter("page", (filters.page || 1) + 1)}
            >Next →</button>
          </div>
        )}
      </div>
    </div>
  );
}
