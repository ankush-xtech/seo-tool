import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import OutreachService, {
  type Lead, type OutreachStats, type SEOProgress, type LeadFilters,
} from "../../services/outreach.service";

const VERDICT_COLORS: Record<string, string> = {
  "Good": "#22c55e",
  "Needs Improvement": "#f59e0b",
  "Poor SEO": "#ef4444",
  "SEO Required": "#dc2626",
  "Unreachable": "#6b7280",
  "Pending": "#6b7280",
};

const EMAIL_STATUS_COLORS: Record<string, string> = {
  draft: "#6b7280",
  sent: "#3b82f6",
  opened: "#f59e0b",
  replied: "#22c55e",
  bounced: "#ef4444",
};

const normalizeEmailStatus = (status: string | null) => {
  if (status === "clicked") return "opened";
  return status;
};

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ background: "#13151a", borderRadius: 8, padding: "14px 18px", flex: 1, minWidth: 120, border: "1px solid #2a2d35" }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || "#fff" }}>{value}</div>
      <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{label}</div>
    </div>
  );
}

function ProgressBar({ progress }: { progress: SEOProgress }) {
  if (!progress.running && progress.total === 0) return null;
  return (
    <div style={{ background: "#1a1d23", borderRadius: 8, padding: "12px 16px", marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
        <span>
          {progress.running ? "🔍 Running SEO Checks..." : "✅ SEO Checks Complete"}{" "}
          <span style={{ color: "#aaa" }}>
            {progress.done}/{progress.total} checked
            {progress.failed > 0 && `, ${progress.failed} failed`}
          </span>
        </span>
        <span style={{ color: "#4f7cf8" }}>{progress.percent}%</span>
      </div>
      <div style={{ height: 6, background: "#2a2d35", borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${progress.percent}%`,
          background: progress.running ? "#3b82f6" : "#22c55e",
          borderRadius: 3, transition: "width 0.3s",
        }} />
      </div>
    </div>
  );
}

function StatusBadge({ status, color }: { status: string; color: string }) {
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 12, fontSize: 11, fontWeight: 600,
      background: `${color}22`, color, border: `1px solid ${color}44`,
    }}>
      {status}
    </span>
  );
}

export default function OutreachPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Read initial values from URL — so refresh / back-button preserve state
  const [filters, setFilters] = useState<LeadFilters>({
    page: parseInt(searchParams.get("page") || "1"),
    per_page: parseInt(searchParams.get("per_page") || "10"),
  });
  const [filterSearch, setFilterSearch] = useState(searchParams.get("search") || "");
  const [filterHasEmail, setFilterHasEmail] = useState(searchParams.get("has_email") === "1");
  const [filterMaxScore, setFilterMaxScore] = useState(searchParams.get("max_score") || "");
  const [filterEmailStatus, setFilterEmailStatus] = useState(searchParams.get("email_status") || "");

  // Keep URL in sync whenever filters change
  useEffect(() => {
    const params: Record<string, string> = {};
    if ((filters.page || 1) > 1) params.page = String(filters.page);
    if ((filters.per_page || 10) !== 10) params.per_page = String(filters.per_page);
    if (filterSearch) params.search = filterSearch;
    if (filterHasEmail) params.has_email = "1";
    if (filterMaxScore) params.max_score = filterMaxScore;
    if (filterEmailStatus) params.email_status = filterEmailStatus;
    setSearchParams(params, { replace: true });
  }, [filters.page, filters.per_page, filterSearch, filterHasEmail, filterMaxScore, filterEmailStatus]);
  const [seoProgress, setSeoProgress] = useState<SEOProgress | null>(null);
  const [polling, setPolling] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendingSelected, setSendingSelected] = useState(false);
  const [generatingPreviews, setGeneratingPreviews] = useState(false);
  const [withPreview, setWithPreview] = useState(false);

  // ── Prompt customization modal ──────────────────────────────────────────
  const [showPromptModal, setShowPromptModal] = useState(false);
  const [promptText, setPromptText] = useState("");
  const [loadingPrompt, setLoadingPrompt] = useState(false);
  const [heroImageUrl, setHeroImageUrl] = useState("");
  const [aboutImageUrl, setAboutImageUrl] = useState("");

  // ── Checkbox selection ───────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const { data: stats, refetch: refetchStats } = useQuery<OutreachStats>({
    queryKey: ["outreach-stats"],
    queryFn: () => OutreachService.getStats(),
    staleTime: 10_000,
  });

  const effectiveFilters: LeadFilters = {
    ...filters,
    search: filterSearch || undefined,
    has_email: filterHasEmail || undefined,
    max_score: filterMaxScore ? parseInt(filterMaxScore) : undefined,
    email_status: filterEmailStatus || undefined,
  };

  const { data: leads, refetch: refetchLeads } = useQuery({
    queryKey: ["outreach-leads", effectiveFilters],
    queryFn: () => OutreachService.listLeads(effectiveFilters),
    staleTime: 5_000,
    refetchInterval: 30_000,   // auto-refresh every 30s to pick up open/click tracking
  });

  // Clear selection when page or filters change
  useEffect(() => {
    setSelectedIds(new Set());
  }, [filters.page, filterSearch, filterHasEmail, filterMaxScore, filterEmailStatus]);

  // Poll SEO progress
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      const p = await OutreachService.getSEOProgress();
      setSeoProgress(p);
      if (!p.running) {
        setPolling(false);
        refetchLeads();
        refetchStats();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, refetchLeads, refetchStats]);

  const handleRunSEO = async () => {
    try {
      await OutreachService.runSEOCheck();
      setSeoProgress({ running: true, total: 0, done: 0, failed: 0, percent: 0, recently_checked: [] });
      setPolling(true);
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to start SEO check");
    }
  };

  const handleSendEmails = async () => {
    if (!confirm("Send outreach emails to all leads with SEO score < 70 and valid email?")) return;
    setSending(true);
    try {
      const result = await OutreachService.sendEmails({ max_score: 70, limit: 50 });
      const title = result.failed > 0
        ? (result.sent > 0 ? "Email send completed with errors" : "Email send failed")
        : "Emails sent successfully";
      alert(`${title}\n\nSent: ${result.sent}\nFailed: ${result.failed}`);
      refetchLeads();
      refetchStats();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to send emails");
    } finally {
      setSending(false);
    }
  };

  // ── Checkbox handlers ────────────────────────────────────────────────────
  const pageIds = leads?.items.map((l: Lead) => l.listing_id) ?? [];
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));
  const somePageSelected = pageIds.some((id) => selectedIds.has(id)) && !allPageSelected;

  const handleSelectAll = () => {
    if (allPageSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        pageIds.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        pageIds.forEach((id) => next.add(id));
        return next;
      });
    }
  };

  const handleSelectRow = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleClearSelection = () => setSelectedIds(new Set());

  const handleSendSelected = async (mode: "ai" | "template") => {
    const ids = Array.from(selectedIds);
    const label = mode === "ai" ? "AI" : "Template";
    const previewNote = withPreview ? " + preview site" : "";
    if (!confirm(`Send ${label} email${previewNote} to ${ids.length} selected business${ids.length !== 1 ? "es" : ""}?`)) return;

    setSendingSelected(true);
    try {
      const result = await OutreachService.sendSelectedEmails(ids, mode, withPreview, {
        hero_image_url: heroImageUrl || undefined,
        about_image_url: aboutImageUrl || undefined,
      });
      const header = result.failed > 0
        ? (result.sent > 0 ? `⚠️ ${label} emails completed with errors` : `❌ ${label} email sending failed`)
        : `✅ ${label} emails sent`;
      let msg = `${header}\n\nSent: ${result.sent}\nFailed: ${result.failed}`;
      if (result.previews_generated) msg += `\nPreview sites generated: ${result.previews_generated}`;
      if (result.skipped > 0) msg += `\nSkipped (no email / SEO not checked): ${result.skipped}`;
      if (result.errors?.length) msg += `\n\nErrors:\n${result.errors.slice(0, 3).join("\n")}`;
      alert(msg);
      setSelectedIds(new Set());
      refetchLeads();
      refetchStats();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const status = err.response?.status;
      const msg = detail
        ? `${detail}`
        : err.code === "ERR_NETWORK" || err.code === "ECONNABORTED"
        ? "Request timed out or server unreachable. The preview site generation may take longer — try with fewer leads or without preview."
        : `Failed to send ${label} emails`;
      alert(`${status ? `[${status}] ` : ""}${msg}`);
    } finally {
      setSendingSelected(false);
    }
  };

  const handleOpenPromptModal = async () => {
    setLoadingPrompt(true);
    try {
      const defaultPrompt = await OutreachService.getDefaultPrompt();
      setPromptText(defaultPrompt);
      setHeroImageUrl("");
      setAboutImageUrl("");
      setShowPromptModal(true);
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to load default prompt");
    } finally {
      setLoadingPrompt(false);
    }
  };

  const handleGeneratePreviews = async () => {
    const ids = Array.from(selectedIds);
    setShowPromptModal(false);
    setGeneratingPreviews(true);
    try {
      const result = await OutreachService.generatePreviews(ids, {
        custom_prompt: promptText || undefined,
        hero_image_url: heroImageUrl || undefined,
        about_image_url: aboutImageUrl || undefined,
      });
      let msg = `Preview generation complete\n\nGenerated: ${result.generated}\nFailed: ${result.failed}`;
      if (result.previews?.length) {
        msg += `\n\nPreview links are now visible in the "Preview" column.\nReview them, then send emails with the preview toggle ON.`;
      }
      if (result.errors?.length) msg += `\n\nErrors:\n${result.errors.slice(0, 3).join("\n")}`;
      alert(msg);
      setSelectedIds(new Set());
      refetchLeads();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to generate previews");
    } finally {
      setGeneratingPreviews(false);
    }
  };

  const totalPages = leads ? Math.ceil(leads.total / (filters.per_page || 50)) : 0;

  return (
    <div style={{ padding: "0 4px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ margin: 0, fontSize: "1.5rem" }}>📧 Outreach Dashboard</h1>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={handleRunSEO} disabled={polling}>
            {polling ? "Checking..." : "🔍 Run SEO Check"}
          </button>
       

          {/* ── Mail selected buttons — always visible, disabled until rows are ticked ── */}
          <button
            onClick={() => handleSendSelected("ai")}
            disabled={sendingSelected || selectedIds.size === 0}
            title={selectedIds.size === 0 ? "Select records using checkboxes first" : `Send AI email to ${selectedIds.size} selected`}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: selectedIds.size === 0 ? "#2a2d35" : "#4f7cf8",
              color: selectedIds.size === 0 ? "#666" : "#fff",
              border: "none", borderRadius: 6,
              padding: "7px 14px", cursor: selectedIds.size === 0 ? "not-allowed" : "pointer",
              fontWeight: 600, fontSize: 13, transition: "background 0.2s",
            }}
          >
            🤖 {sendingSelected ? "Sending..." : `Mail by AI${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </button>

          <button
            onClick={() => handleSendSelected("template")}
            disabled={sendingSelected || selectedIds.size === 0}
            title={selectedIds.size === 0 ? "Select records using checkboxes first" : `Send template email to ${selectedIds.size} selected`}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: selectedIds.size === 0 ? "#2a2d35" : "#16a34a",
              color: selectedIds.size === 0 ? "#666" : "#fff",
              border: "none", borderRadius: 6,
              padding: "7px 14px", cursor: selectedIds.size === 0 ? "not-allowed" : "pointer",
              fontWeight: 600, fontSize: 13, transition: "background 0.2s",
            }}
          >
            📋 {sendingSelected ? "Sending..." : `Mail by Template${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </button>

          {/* ── Generate Previews button ── */}
          <button
            onClick={handleOpenPromptModal}
            disabled={generatingPreviews || loadingPrompt || selectedIds.size === 0}
            title={selectedIds.size === 0 ? "Select records first" : `Generate preview websites for ${selectedIds.size} selected (review before sending)`}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: selectedIds.size === 0 ? "#2a2d35" : "#7c3aed",
              color: selectedIds.size === 0 ? "#666" : "#fff",
              border: "none", borderRadius: 6,
              padding: "7px 14px", cursor: selectedIds.size === 0 ? "not-allowed" : "pointer",
              fontWeight: 600, fontSize: 13, transition: "background 0.2s",
            }}
          >
            🌐 {generatingPreviews ? "Generating..." : loadingPrompt ? "Loading..." : `Generate Previews${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </button>

          {/* ── Preview toggle ── */}
          <label
            title="Include preview website link when sending emails"
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: withPreview ? "#0891b2" : "#1a1d23",
              border: withPreview ? "1px solid #0891b2" : "1px solid #2a2d35",
              borderRadius: 6, padding: "7px 14px", cursor: "pointer",
              fontSize: 13, fontWeight: 600, transition: "all 0.2s",
              color: withPreview ? "#fff" : "#888",
            }}
          >
            <input
              type="checkbox"
              checked={withPreview}
              onChange={(e) => setWithPreview(e.target.checked)}
              style={{ accentColor: "#0891b2" }}
            />
            🌐 Preview Sites
          </label>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
          <StatCard label="Total Leads" value={stats.total_leads} />
          <StatCard label="With Website" value={stats.with_website} />
          <StatCard label="With Email" value={stats.with_email} />
          <StatCard label="SEO Checked" value={stats.seo_checked} />
          <StatCard label="Score < 70" value={stats.score_below_70} color="#ef4444" />
          <StatCard label="Emails Sent" value={stats.emails_sent} color="#3b82f6" />
          <StatCard label="Opened" value={`${stats.emails_opened} (${stats.open_rate}%)`} color="#f59e0b" />
          <StatCard label="Replied" value={`${stats.emails_replied} (${stats.reply_rate}%)`} color="#22c55e" />
        </div>
      )}

      {/* Progress */}
      {seoProgress && <ProgressBar progress={seoProgress} />}

      {/* Filters */}
      <div style={{
        display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center",
        background: "#13151a", borderRadius: 8, padding: "10px 14px", border: "1px solid #2a2d35",
      }}>
        <input
          className="form-input" type="text" placeholder="Search business..."
          value={filterSearch}
          onChange={(e) => { setFilterSearch(e.target.value); setFilters(f => ({ ...f, page: 1 })); }}
          style={{ width: 200 }}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, color: "#ccc", cursor: "pointer" }}>
          <input type="checkbox" checked={filterHasEmail} onChange={(e) => { setFilterHasEmail(e.target.checked); setFilters(f => ({ ...f, page: 1 })); }} />
          Has Email
        </label>
        <select className="form-input" value={filterMaxScore}
          onChange={(e) => { setFilterMaxScore(e.target.value); setFilters(f => ({ ...f, page: 1 })); }}
          style={{ width: 140 }}>
          <option value="">Any Score</option>
          <option value="70">Below 70 (Targets)</option>
          <option value="50">Below 50 (Poor)</option>
          <option value="30">Below 30 (Critical)</option>
        </select>
        <select className="form-input" value={filterEmailStatus}
          onChange={(e) => { setFilterEmailStatus(e.target.value); setFilters(f => ({ ...f, page: 1 })); }}
          style={{ width: 140 }}>
          <option value="">Any Email Status</option>
          <option value="sent">Sent</option>
          <option value="opened">Opened</option>
          <option value="replied">Replied</option>
        </select>
        <select className="form-input"
          value={filters.per_page}
          onChange={(e) => setFilters(f => ({ ...f, page: 1, per_page: parseInt(e.target.value) }))}
          style={{ width: 110 }}>
          <option value={10}>10 / page</option>
          <option value={50}>50 / page</option>
          <option value={100}>100 / page</option>
          <option value={200}>200 / page</option>
        </select>
      </div>

      {/* Count + selection bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#aaa" }}>
        <span>{leads?.total.toLocaleString() ?? 0} leads</span>
        <span>Page {filters.page} of {totalPages}</span>
      </div>

      {/* Selection count + clear (only visible when rows are ticked) */}
      {selectedIds.size > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, fontSize: 13 }}>
          <span style={{ color: "#4f7cf8", fontWeight: 600 }}>
            ✓ {selectedIds.size} lead{selectedIds.size !== 1 ? "s" : ""} selected
          </span>
          <button
            onClick={handleClearSelection}
            style={{
              background: "transparent", border: "1px solid #4a5068",
              color: "#aaa", borderRadius: 5, padding: "2px 10px",
              cursor: "pointer", fontSize: 12,
            }}
          >
            ✕ Clear
          </button>
        </div>
      )}

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {/* Header checkbox — selects/deselects all on current page */}
              <th style={{ width: 40, textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  ref={(el) => { if (el) el.indeterminate = somePageSelected; }}
                  onChange={handleSelectAll}
                  style={{ cursor: "pointer", width: 15, height: 15 }}
                  title={allPageSelected ? "Deselect all on this page" : "Select all on this page"}
                />
              </th>
              <th>Business Name</th>
              <th>Website</th>
              <th>SEO Verdict</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Email Sent</th>
              <th>Opened</th>
              <th>Preview</th>
            </tr>
          </thead>
          <tbody>
            {leads?.items.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 40, color: "#666" }}>
                  No leads found. Run a Maps search first, then come back here.
                </td>
              </tr>
            )}
            {leads?.items.map((lead: Lead) => {
              const isSelected = selectedIds.has(lead.listing_id);
              const normalizedStatus = normalizeEmailStatus(lead.email_status);
              return (
                <tr
                  key={lead.listing_id}
                  style={{ background: isSelected ? "#1a2540" : undefined }}
                >
                  {/* Row checkbox */}
                  <td style={{ textAlign: "center", width: 40 }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleSelectRow(lead.listing_id)}
                      style={{ cursor: "pointer", width: 15, height: 15 }}
                    />
                  </td>
                  <td style={{ fontWeight: 500, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {lead.business_name}
                  </td>
                  <td>
                    {lead.website ? (
                      <a href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                        target="_blank" rel="noopener noreferrer" style={{ color: "#4f7cf8", fontSize: 13 }}>
                        {lead.website.replace(/^https?:\/\//, "").replace(/\/$/, "").substring(0, 25)}
                      </a>
                    ) : <span style={{ color: "#5a6278" }}>—</span>}
                  </td>
                  <td>
                    {lead.seo_score !== null ? (
                      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{
                          fontWeight: 700, fontSize: 13,
                          color: lead.seo_score >= 70 ? "#22c55e" : lead.seo_score >= 50 ? "#f59e0b" : "#ef4444",
                        }}>
                          {lead.seo_score}/100
                        </span>
                        <StatusBadge
                          status={lead.seo_verdict || ""}
                          color={VERDICT_COLORS[lead.seo_verdict || ""] || "#666"}
                        />
                      </span>
                    ) : (
                      <span style={{ color: "#5a6278", fontSize: 12 }}>
                        {lead.seo_status === "running" ? "⏳ Checking..." : "Not checked"}
                      </span>
                    )}
                  </td>
                  <td>
                    {lead.email ? (
                      <a href={`mailto:${lead.email}`} style={{ color: "#22c55e", fontSize: 13 }}>
                        {lead.email.length > 25 ? lead.email.substring(0, 25) + "..." : lead.email}
                      </a>
                    ) : <span style={{ color: "#5a6278" }}>—</span>}
                  </td>
                  <td>
                    {lead.phone ? (
                      <a href={`tel:${lead.phone}`} style={{ color: "#4f7cf8", fontSize: 13 }}>{lead.phone}</a>
                    ) : <span style={{ color: "#5a6278" }}>—</span>}
                  </td>
                  {/* Email tracking columns */}
                  <td style={{ textAlign: "center" }}>
                    {normalizedStatus && normalizedStatus !== "draft" ? (
                      <span
                        title={lead.email_sent_at ? `Sent: ${new Date(lead.email_sent_at).toLocaleString()}` : ""}
                      >
                        <StatusBadge
                          status={normalizedStatus.charAt(0).toUpperCase() + normalizedStatus.slice(1)}
                          color={EMAIL_STATUS_COLORS[normalizedStatus] || "#3b82f6"}
                        />
                      </span>
                    ) : <span style={{ color: "#5a6278" }}>—</span>}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {lead.email_opened_at ? (
                      <span
                        title={`Opened: ${new Date(lead.email_opened_at).toLocaleString()}`}
                        style={{ color: "#f59e0b", fontWeight: 600, cursor: "default", fontSize: 16 }}
                      >✅</span>
                    ) : <span style={{ color: "#5a6278" }}>—</span>}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {lead.preview_url ? (
                      <a
                        href={lead.preview_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`View preview: ${lead.preview_url}`}
                        style={{
                          color: "#0891b2", textDecoration: "none", fontWeight: 600,
                          fontSize: 14, display: "inline-flex", alignItems: "center", gap: 4,
                        }}
                      >
                        🌐 View
                      </a>
                    ) : <span style={{ color: "#5a6278" }}>—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16 }}>
          <button className="btn btn-secondary"
            disabled={(filters.page || 1) <= 1}
            onClick={() => setFilters(f => ({ ...f, page: (f.page || 1) - 1 }))}
            style={{ padding: "6px 14px" }}>
            ← Prev
          </button>
          <span style={{ display: "flex", alignItems: "center", color: "#aaa", fontSize: 13 }}>
            {filters.page} / {totalPages}
          </span>
          <button className="btn btn-secondary"
            disabled={(filters.page || 1) >= totalPages}
            onClick={() => setFilters(f => ({ ...f, page: (f.page || 1) + 1 }))}
            style={{ padding: "6px 14px" }}>
            Next →
          </button>
        </div>
      )}

      {/* ── Prompt Customization Modal ── */}
      {showPromptModal && (
        <div
          style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "rgba(0,0,0,0.7)", display: "flex",
            alignItems: "center", justifyContent: "center", zIndex: 9999,
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowPromptModal(false); }}
        >
          <div style={{
            background: "#13151a", borderRadius: 12, padding: 24,
            width: "90%", maxWidth: 800, maxHeight: "85vh",
            display: "flex", flexDirection: "column",
            border: "1px solid #2a2d35", boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
          }}>
            {/* Modal header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2 style={{ margin: 0, fontSize: 18, color: "#fff" }}>
                Customize Website Prompt
              </h2>
              <button
                onClick={() => setShowPromptModal(false)}
                style={{
                  background: "none", border: "none", color: "#888",
                  fontSize: 22, cursor: "pointer", padding: "0 4px",
                }}
              >
                x
              </button>
            </div>

            {/* Info */}
            <div style={{
              background: "#1a1d23", borderRadius: 8, padding: "10px 14px",
              marginBottom: 12, fontSize: 13, color: "#9ca3af",
              border: "1px solid #2a2d35",
            }}>
              Edit the prompt below to customize the generated website. Use these placeholders — they will be replaced per business:
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                {["{business_name}", "{category}", "{city}", "{phone}", "{email}", "{website}"].map((tag) => (
                  <code key={tag} style={{
                    background: "#7c3aed22", color: "#a78bfa", padding: "2px 8px",
                    borderRadius: 4, fontSize: 12, border: "1px solid #7c3aed44",
                  }}>{tag}</code>
                ))}
              </div>
            </div>

            {/* Image URL inputs */}
            <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4, display: "block" }}>
                  Hero Banner Image URL
                </label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="text"
                    value={heroImageUrl}
                    onChange={(e) => setHeroImageUrl(e.target.value)}
                    placeholder="Paste your own image URL (leave empty for default)"
                    style={{
                      flex: 1, background: "#0a0c10", color: "#e2e8f0",
                      border: "1px solid #2a2d35", borderRadius: 6,
                      padding: "8px 12px", fontSize: 13, outline: "none",
                    }}
                  />
                  {heroImageUrl && (
                    <img
                      src={heroImageUrl}
                      alt="Hero preview"
                      style={{
                        width: 40, height: 40, borderRadius: 6,
                        objectFit: "cover", border: "1px solid #2a2d35",
                      }}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  )}
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4, display: "block" }}>
                  About Section Image URL
                </label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="text"
                    value={aboutImageUrl}
                    onChange={(e) => setAboutImageUrl(e.target.value)}
                    placeholder="Paste your own image URL (leave empty for default)"
                    style={{
                      flex: 1, background: "#0a0c10", color: "#e2e8f0",
                      border: "1px solid #2a2d35", borderRadius: 6,
                      padding: "8px 12px", fontSize: 13, outline: "none",
                    }}
                  />
                  {aboutImageUrl && (
                    <img
                      src={aboutImageUrl}
                      alt="About preview"
                      style={{
                        width: 40, height: 40, borderRadius: 6,
                        objectFit: "cover", border: "1px solid #2a2d35",
                      }}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  )}
                </div>
              </div>
            </div>

            {/* Textarea */}
            <textarea
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              style={{
                flex: 1, minHeight: 300, background: "#0a0c10",
                color: "#e2e8f0", border: "1px solid #2a2d35",
                borderRadius: 8, padding: 14, fontSize: 13,
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                lineHeight: 1.6, resize: "vertical",
                outline: "none",
              }}
              spellCheck={false}
            />

            {/* Footer buttons */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16, gap: 12 }}>
              <button
                onClick={async () => {
                  try {
                    const defaultPrompt = await OutreachService.getDefaultPrompt();
                    setPromptText(defaultPrompt);
                    setHeroImageUrl("");
                    setAboutImageUrl("");
                  } catch { /* ignore */ }
                }}
                style={{
                  background: "none", border: "1px solid #2a2d35",
                  color: "#9ca3af", borderRadius: 6, padding: "8px 16px",
                  cursor: "pointer", fontSize: 13,
                }}
              >
                Reset to Default
              </button>
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  onClick={() => setShowPromptModal(false)}
                  style={{
                    background: "none", border: "1px solid #2a2d35",
                    color: "#ccc", borderRadius: 6, padding: "8px 20px",
                    cursor: "pointer", fontSize: 13,
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleGeneratePreviews}
                  disabled={!promptText.trim()}
                  style={{
                    background: "#7c3aed", color: "#fff",
                    border: "none", borderRadius: 6, padding: "8px 24px",
                    cursor: promptText.trim() ? "pointer" : "not-allowed",
                    fontWeight: 600, fontSize: 13, transition: "background 0.2s",
                  }}
                >
                  Confirm & Generate ({selectedIds.size})
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
