import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AlertsService, { AlertRule, AlertCondition } from "../../services/alerts.service";

const CONDITION_LABELS: Record<AlertCondition, string> = {
  score_above: "Score rises above threshold",
  score_below: "Score falls below threshold",
  score_drop: "Score drops by N points",
  check_failed: "SEO check fails",
};

const CONDITION_HINT: Record<AlertCondition, string> = {
  score_above: "Alert when a domain scores ≥ this value (e.g. 70)",
  score_below: "Alert when a domain scores < this value (e.g. 40)",
  score_drop: "Alert when score drops by ≥ this many points (e.g. 20)",
  check_failed: "Alert whenever a domain check fails (no threshold needed)",
};

interface RuleModalProps {
  rule?: AlertRule | null;
  onClose: () => void;
  onSaved: () => void;
}

function RuleModal({ rule, onClose, onSaved }: RuleModalProps) {
  const isEdit = !!rule;
  const [form, setForm] = useState({
    name: rule?.name || "",
    condition: rule?.condition || "score_below" as AlertCondition,
    threshold: rule?.threshold?.toString() || "40",
    tld_filter: rule?.tld_filter || "",
    is_active: rule?.is_active ?? true,
    email_notify: rule?.email_notify ?? true,
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const needsThreshold = form.condition !== "check_failed";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        condition: form.condition,
        threshold: needsThreshold && form.threshold ? parseFloat(form.threshold) : null,
        tld_filter: form.tld_filter || null,
        is_active: form.is_active,
        email_notify: form.email_notify,
      };
      if (isEdit) {
        await AlertsService.updateRule(rule!.id, payload);
      } else {
        await AlertsService.createRule(payload);
      }
      onSaved();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2 className="modal-title">{isEdit ? "Edit alert rule" : "Create alert rule"}</h2>
        {error && <div className="alert alert-error" style={{ marginBottom: 12 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field">
              <label>Rule name</label>
              <input type="text" value={form.name} onChange={set("name")}
                placeholder="e.g. Alert on low score" required />
            </div>
            <div className="field">
              <label>Condition</label>
              <select value={form.condition} onChange={set("condition")}
                className="filter-select" style={{ width: "100%", height: 40 }}>
                {Object.entries(CONDITION_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              <span style={{ fontSize: 11, color: "var(--text-hint)", marginTop: 4 }}>
                {CONDITION_HINT[form.condition]}
              </span>
            </div>
            {needsThreshold && (
              <div className="field">
                <label>Threshold (0–100)</label>
                <input type="number" value={form.threshold} onChange={set("threshold")}
                  min="0" max="100" step="1" required />
              </div>
            )}
            <div className="field">
              <label>TLD filter (optional)</label>
              <input type="text" value={form.tld_filter} onChange={set("tld_filter")}
                placeholder="e.g. com  (leave empty for all TLDs)" />
            </div>
            <div style={{ display: "flex", gap: 20 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 7, cursor: "pointer", fontSize: 13 }}>
                <input type="checkbox" checked={form.is_active}
                  onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
                  style={{ width: 15, height: 15 }} />
                Rule active
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 7, cursor: "pointer", fontSize: 13 }}>
                <input type="checkbox" checked={form.email_notify}
                  onChange={e => setForm(f => ({ ...f, email_notify: e.target.checked }))}
                  style={{ width: 15, height: 15 }} />
                Email notification
              </label>
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary"
              style={{ width: "auto", padding: "0 20px" }} disabled={saving}>
              {saving ? <span className="btn-spinner" /> : null}
              {saving ? "Saving…" : isEdit ? "Save changes" : "Create rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [modal, setModal] = useState<{ open: boolean; rule: AlertRule | null }>({ open: false, rule: null });
  const [deleting, setDeleting] = useState<number | null>(null);

  const { data: rules, isLoading } = useQuery({
    queryKey: ["alert-rules"],
    queryFn: AlertsService.listRules,
  });

  const { data: notifData } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => AlertsService.listNotifications({ page: 1 }),
  });

  const handleDelete = async (rule: AlertRule) => {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    setDeleting(rule.id);
    try {
      await AlertsService.deleteRule(rule.id);
      queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
    } finally {
      setDeleting(null);
    }
  };

  const onSaved = () => {
    setModal({ open: false, rule: null });
    queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
  };

  return (
    <div>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">Alerts & Notifications</h1>
          <p className="page-subtitle">Configure alert rules — get notified when domains meet your criteria</p>
        </div>
        <button className="btn-primary" style={{ width: "auto", padding: "0 16px", height: 38 }}
          onClick={() => setModal({ open: true, rule: null })}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          New rule
        </button>
      </div>

      {/* Alert Rules */}
      <div className="table-container" style={{ marginBottom: 24 }}>
        <div className="table-header">
          <span className="table-title">Alert rules ({rules?.length || 0})</span>
        </div>
        {isLoading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
        ) : !rules?.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔔</div>
            <div className="empty-state-title">No alert rules yet</div>
            <div className="empty-state-text">Create a rule to get notified when domains meet your criteria.</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Rule name</th>
                <th>Condition</th>
                <th>Threshold</th>
                <th>TLD filter</th>
                <th>Email</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map(rule => (
                <tr key={rule.id}>
                  <td style={{ fontWeight: 500 }}>{rule.name}</td>
                  <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    {CONDITION_LABELS[rule.condition]}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                    {rule.threshold ?? "—"}
                  </td>
                  <td>
                    {rule.tld_filter
                      ? <span className="badge badge-neutral">.{rule.tld_filter}</span>
                      : <span style={{ color: "var(--text-hint)", fontSize: 12 }}>all</span>
                    }
                  </td>
                  <td>
                    <span className={`badge ${rule.email_notify ? "badge-success" : "badge-neutral"}`}>
                      {rule.email_notify ? "on" : "off"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${rule.is_active ? "badge-success" : "badge-neutral"}`}>
                      {rule.is_active ? "active" : "paused"}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn-secondary" style={{ padding: "0 10px", height: 28, fontSize: 12 }}
                        onClick={() => setModal({ open: true, rule })}>Edit</button>
                      <button className="btn-danger" style={{ padding: "0 10px", height: 28, fontSize: 12 }}
                        onClick={() => handleDelete(rule)} disabled={deleting === rule.id}>
                        {deleting === rule.id ? "…" : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent Notifications */}
      <div className="table-container">
        <div className="table-header">
          <span className="table-title">
            Recent notifications
            {notifData?.unread_count ? (
              <span className="badge badge-info" style={{ marginLeft: 8 }}>
                {notifData.unread_count} unread
              </span>
            ) : null}
          </span>
          {(notifData?.unread_count ?? 0) > 0 && (
            <button className="btn-secondary" style={{ fontSize: 12 }}
              onClick={async () => {
                await AlertsService.markAllRead();
                queryClient.invalidateQueries({ queryKey: ["notifications"] });
                queryClient.invalidateQueries({ queryKey: ["unread-count"] });
              }}>
              Mark all read
            </button>
          )}
        </div>

        {!notifData?.notifications.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <div className="empty-state-title">No notifications yet</div>
            <div className="empty-state-text">Notifications will appear here when alert rules are triggered.</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Message</th>
                <th>Status</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {notifData.notifications.map(n => (
                <tr key={n.id} style={{ opacity: n.status === "read" ? 0.6 : 1 }}>
                  <td style={{ fontWeight: n.status === "unread" ? 600 : 400 }}>{n.title}</td>
                  <td style={{ fontSize: 12, color: "var(--text-muted)" }}>{n.message}</td>
                  <td>
                    <span className={`badge ${n.status === "unread" ? "badge-info" : "badge-neutral"}`}>
                      {n.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-hint)", whiteSpace: "nowrap" }}>
                    {new Date(n.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modal.open && (
        <RuleModal rule={modal.rule} onClose={() => setModal({ open: false, rule: null })} onSaved={onSaved} />
      )}
    </div>
  );
}
