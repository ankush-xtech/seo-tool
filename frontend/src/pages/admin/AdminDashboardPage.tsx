import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import DashboardService from "../../services/dashboard.service";
import { DailyFetchChart, ScoreDistChart, TLDChart } from "../../components/ui/Charts";

const ACTION_COLORS: Record<string, string> = {
  login: "badge-info",
  logout: "badge-neutral",
  fetch_domains: "badge-success",
  run_seo_check: "badge-info",
  export: "badge-neutral",
  user_created: "badge-success",
  user_updated: "badge-warning",
  user_deleted: "badge-danger",
  settings_updated: "badge-warning",
};

export default function AdminDashboardPage() {
  const navigate = useNavigate();

  const { data: stats, isLoading } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: DashboardService.getAdminStats,
    refetchInterval: 30_000,
  });

  return (
    <div>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">Admin Dashboard</h1>
          <p className="page-subtitle">System overview — live stats</p>
        </div>
        <button
          className="btn-secondary"
          onClick={() => navigate("/admin/users")}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="5" cy="4" r="2.5" stroke="currentColor" strokeWidth="1.2"/>
            <path d="M1 12c0-2.2 1.8-4 4-4s4 1.8 4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            <path d="M10 6l1.5 1.5L14 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Manage Users
        </button>
      </div>

      {isLoading ? (
        <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
      ) : stats ? (
        <>
          {/* Top stats */}
          <div className="stats-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
            <div className="stat-card">
              <div className="stat-label">Total users</div>
              <div className="stat-value">{stats.total_users}</div>
              <div className="stat-sub">{stats.active_users} active</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total domains</div>
              <div className="stat-value">{stats.total_domains.toLocaleString()}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Fetched today</div>
              <div className="stat-value" style={{ color: "var(--accent)" }}>
                {stats.fetched_today.toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Checked today</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>
                {stats.checked_today.toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Failed today</div>
              <div className="stat-value" style={{ color: stats.failed_today > 0 ? "var(--danger)" : "var(--text)" }}>
                {stats.failed_today}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Avg SEO score</div>
              <div className="stat-value" style={{
                color: stats.avg_seo_score
                  ? stats.avg_seo_score >= 70 ? "var(--success)"
                  : stats.avg_seo_score >= 40 ? "var(--warning)" : "var(--danger)"
                  : "var(--text-hint)"
              }}>
                {stats.avg_seo_score ?? "—"}
              </div>
            </div>
          </div>

          {/* Charts */}
          <div className="chart-grid">
            <div className="chart-card" style={{ gridColumn: "span 2" }}>
              <div className="chart-title">Daily domain fetches (last 14 days)</div>
              <DailyFetchChart data={stats.daily_fetched} />
            </div>
            <div className="chart-card">
              <div className="chart-title">Score distribution</div>
              <ScoreDistChart data={stats.score_distribution} />
            </div>
          </div>

          <div className="chart-grid" style={{ marginTop: 0 }}>
            <div className="chart-card">
              <div className="chart-title">Top TLDs</div>
              <TLDChart data={stats.top_tlds} />
            </div>

            {/* User breakdown */}
            <div className="chart-card">
              <div className="chart-title">User breakdown</div>
              <div style={{ padding: "8px 0" }}>
                {[
                  { label: "Total users", value: stats.total_users, color: "var(--text)" },
                  { label: "Active users", value: stats.active_users, color: "var(--success)" },
                  { label: "Admins", value: stats.admin_count, color: "var(--accent)" },
                  { label: "Regular users", value: stats.total_users - stats.admin_count, color: "var(--text-muted)" },
                ].map(item => (
                  <div key={item.label} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", borderBottom: "0.5px solid var(--border)", fontSize: 13 }}>
                    <span style={{ color: "var(--text-muted)" }}>{item.label}</span>
                    <span style={{ fontWeight: 600, color: item.color }}>{item.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Score summary */}
            <div className="chart-card">
              <div className="chart-title">Score summary</div>
              <div style={{ padding: "8px 0" }}>
                {[
                  { label: "Good (70+)", value: stats.score_distribution.good, color: "var(--success)" },
                  { label: "Average (40–69)", value: stats.score_distribution.average, color: "var(--warning)" },
                  { label: "Poor (<40)", value: stats.score_distribution.poor, color: "var(--danger)" },
                  { label: "Pending check", value: stats.pending_check, color: "var(--text-hint)" },
                ].map(item => (
                  <div key={item.label} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", borderBottom: "0.5px solid var(--border)", fontSize: 13 }}>
                    <span style={{ color: "var(--text-muted)" }}>{item.label}</span>
                    <span style={{ fontWeight: 600, color: item.color }}>{item.value.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recent audit logs */}
          <div className="table-container" style={{ marginTop: 20 }}>
            <div className="table-header">
              <span className="table-title">Recent activity</span>
              <button className="btn-secondary" style={{ fontSize: 12 }} onClick={() => navigate("/admin/audit-logs")}>
                View all →
              </button>
            </div>
            {stats.recent_audit_logs.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <div className="empty-state-title">No activity yet</div>
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>User</th>
                    <th>Description</th>
                    <th>IP</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_audit_logs.map((log: any) => (
                    <tr key={log.id}>
                      <td>
                        <span className={`badge ${ACTION_COLORS[log.action] || "badge-neutral"}`}>
                          {log.action.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {log.user_email || "system"}
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-muted)", maxWidth: 280 }}>
                        <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {log.description || "—"}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-hint)", fontFamily: "var(--font-mono)" }}>
                        {log.ip_address || "—"}
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-hint)", whiteSpace: "nowrap" }}>
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
