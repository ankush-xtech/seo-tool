import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import DashboardService from "../../services/dashboard.service";
import { DailyFetchChart, ScoreDistChart, TLDChart } from "../../components/ui/Charts";

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const { data: stats, isLoading } = useQuery({
    queryKey: ["user-dashboard"],
    queryFn: DashboardService.getUserStats,
    refetchInterval: 30_000,
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">
          Welcome back, {user?.full_name?.split(" ")[0]} 👋
        </h1>
        <p className="page-subtitle">Here's what's happening with your SEO pipeline today</p>
      </div>

      {isLoading ? (
        <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
      ) : stats ? (
        <>
          {/* Stats row */}
          <div className="stats-grid">
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
              <div className="stat-label">SEO checked</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>
                {stats.checked.toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Pending check</div>
              <div className="stat-value" style={{ color: "var(--warning)" }}>
                {stats.pending_check.toLocaleString()}
              </div>
            </div>
            {stats.avg_seo_score !== null && (
              <div className="stat-card">
                <div className="stat-label">Avg SEO score</div>
                <div className="stat-value" style={{
                  color: stats.avg_seo_score >= 70 ? "var(--success)" :
                         stats.avg_seo_score >= 40 ? "var(--warning)" : "var(--danger)"
                }}>
                  {stats.avg_seo_score}
                </div>
              </div>
            )}
          </div>

          {/* Charts row */}
          <div className="chart-grid">
            <div className="chart-card">
              <div className="chart-title">Daily domain fetches (last 7 days)</div>
              <DailyFetchChart data={stats.daily_fetched} />
            </div>
            <div className="chart-card">
              <div className="chart-title">Score distribution</div>
              <ScoreDistChart data={stats.score_distribution} />
            </div>
            <div className="chart-card">
              <div className="chart-title">Top TLDs</div>
              <TLDChart data={stats.top_tlds} />
            </div>
          </div>

          {/* Quick actions */}
          <div className="quick-actions">
            <div className="quick-title">Quick actions</div>
            <div className="qa-grid">
              <button className="qa-btn" onClick={() => navigate("/domains")}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <circle cx="9" cy="9" r="7.5" stroke="currentColor" strokeWidth="1.3"/>
                  <path d="M9 1.5S6.5 4.5 6.5 9s2.5 7.5 2.5 7.5M9 1.5S11.5 4.5 11.5 9 9 16.5 9 16.5M1.5 9h15" stroke="currentColor" strokeWidth="1.3"/>
                </svg>
                Browse Domains
              </button>
              <button className="qa-btn" onClick={() => navigate("/seo-checker")}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <circle cx="7.5" cy="7.5" r="5.5" stroke="currentColor" strokeWidth="1.3"/>
                  <path d="M12 12l4.5 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                  <path d="M5.5 7.5h4M7.5 5.5v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                </svg>
                Check a Domain
              </button>
              <button className="qa-btn" onClick={() => navigate("/watchlist")}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M9 2l2.25 4.5 5 .75-3.625 3.5.85 4.95L9 13.25l-4.475 2.45.85-4.95L1.75 7.25l5-.75L9 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
                </svg>
                My Watchlist
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
