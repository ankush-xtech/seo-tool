import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../services/api";

interface WatchlistItem {
  id: number;
  domain_id: number;
  notes: string | null;
  alert_on_score_change: boolean;
  score_threshold: number | null;
  created_at: string;
  domain: {
    id: number;
    name: string;
    tld: string;
    seo_score: number | null;
    check_status: string;
    fetched_date: string;
  };
}

const WatchlistService = {
  async list(): Promise<WatchlistItem[]> {
    const { data } = await api.get("/watchlist/");
    return data;
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/watchlist/${id}`);
  },
};

export default function WatchlistPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [removing, setRemoving] = useState<number | null>(null);

  const { data: items, isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: WatchlistService.list,
  });

  const handleRemove = async (item: WatchlistItem) => {
    if (!confirm(`Remove ${item.domain.name} from watchlist?`)) return;
    setRemoving(item.id);
    try {
      await WatchlistService.remove(item.id);
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    } finally {
      setRemoving(null);
    }
  };

  const scoreColor = (score: number | null) =>
    score === null ? "var(--text-hint)"
    : score >= 70 ? "var(--success)"
    : score >= 40 ? "var(--warning)"
    : "var(--danger)";

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Watchlist</h1>
        <p className="page-subtitle">Domains you're tracking — add them from the Domains page</p>
      </div>

      <div className="table-container">
        <div className="table-header">
          <span className="table-title">
            {isLoading ? "Loading…" : `${items?.length || 0} saved domains`}
          </span>
        </div>

        {isLoading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
        ) : !items?.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">⭐</div>
            <div className="empty-state-title">Watchlist is empty</div>
            <div className="empty-state-text">Go to the Domains page and click the star icon to save domains here.</div>
            <button className="btn-secondary" style={{ marginTop: 16 }} onClick={() => navigate("/domains")}>
              Browse Domains
            </button>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th>TLD</th>
                <th>SEO score</th>
                <th>Status</th>
                <th>Notes</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                    <a href={`https://${item.domain.name}`} target="_blank" rel="noopener noreferrer"
                       style={{ color: "var(--accent)", display: "flex", alignItems: "center", gap: 5 }}>
                      {item.domain.name}
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M2 8L8 2M8 2H4M8 2v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                      </svg>
                    </a>
                  </td>
                  <td><span className="badge badge-neutral">.{item.domain.tld}</span></td>
                  <td>
                    <span style={{ fontWeight: 600, color: scoreColor(item.domain.seo_score) }}>
                      {item.domain.seo_score ?? "—"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${
                      item.domain.check_status === "done" ? "badge-success"
                      : item.domain.check_status === "failed" ? "badge-danger"
                      : item.domain.check_status === "running" ? "badge-info"
                      : "badge-warning"
                    }`}>
                      {item.domain.check_status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    {item.notes || "—"}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        className="btn-secondary"
                        style={{ padding: "0 10px", height: 28, fontSize: 12 }}
                        onClick={() => navigate(`/seo-checker?domain=${item.domain.name}`)}
                      >
                        Re-check
                      </button>
                      <button
                        className="btn-danger"
                        style={{ padding: "0 10px", height: 28, fontSize: 12 }}
                        onClick={() => handleRemove(item)}
                        disabled={removing === item.id}
                      >
                        {removing === item.id ? "…" : "Remove"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
