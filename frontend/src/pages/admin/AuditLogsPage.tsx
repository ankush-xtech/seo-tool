import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import DashboardService from "../../services/dashboard.service";

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

const ACTIONS = [
  "login", "logout", "fetch_domains", "run_seo_check",
  "export", "user_created", "user_updated", "user_deleted",
];

export default function AuditLogsPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", page, action],
    queryFn: () => DashboardService.getAuditLogs({
      page, per_page: 25,
      action: action || undefined,
    }),
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Audit logs</h1>
        <p className="page-subtitle">Full history of all system and user actions</p>
      </div>

      <div className="filter-bar" style={{ marginBottom: 14 }}>
        <select value={action} onChange={e => { setAction(e.target.value); setPage(1); }} className="filter-select">
          <option value="">All actions</option>
          {ACTIONS.map(a => (
            <option key={a} value={a}>{a.replace(/_/g, " ")}</option>
          ))}
        </select>
        {action && (
          <button className="btn-secondary" style={{ padding: "0 10px", fontSize: 12 }}
            onClick={() => { setAction(""); setPage(1); }}>
            Clear
          </button>
        )}
      </div>

      <div className="table-container">
        <div className="table-header">
          <span className="table-title">{data ? `${data.total.toLocaleString()} entries` : "Loading…"}</span>
        </div>

        {isLoading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
        ) : !data?.logs.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-title">No logs found</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Action</th>
                <th>User</th>
                <th>Description</th>
                <th>IP address</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {data.logs.map(log => (
                <tr key={log.id}>
                  <td>
                    <span className={`badge ${ACTION_COLORS[log.action] || "badge-neutral"}`}>
                      {log.action.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--text-muted)" }}>
                    {log.user_email || <span style={{ color: "var(--text-hint)" }}>system</span>}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-muted)", maxWidth: 320 }}>
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

        {data && data.total > 25 && (
          <div className="pagination">
            <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {page} / {Math.ceil(data.total / 25)}
            </span>
            <button className="btn-secondary" disabled={page >= Math.ceil(data.total / 25)} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        )}
      </div>
    </div>
  );
}
