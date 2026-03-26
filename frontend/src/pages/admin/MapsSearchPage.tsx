import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import MapsService, {
  type BusinessListing,
  type MapsPresets,
  type MapsProgress,
  type MapSearch,
  type ListingFilters,
} from "../../services/maps.service";

// ─── Status badge colors ────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  pending: "#f59e0b",
  running: "#3b82f6",
  done: "#22c55e",
  failed: "#ef4444",
};

// ─── Stars component ────────────────────────────────────────────────────────
function Stars({ rating }: { rating: number | null }) {
  if (!rating) return <span style={{ color: "#5a6278" }}>—</span>;
  const full = Math.floor(rating);
  return (
    <span title={`${rating} / 5`}>
      {"★".repeat(full)}
      {"☆".repeat(5 - full)}
      <span style={{ marginLeft: 4, fontSize: "0.85em", color: "#aaa" }}>{rating}</span>
    </span>
  );
}

// ─── Progress bar ───────────────────────────────────────────────────────────
function ProgressBar({ progress }: { progress: MapsProgress }) {
  if (!progress.running && progress.total === 0) return null;
  return (
    <div style={{ background: "#1a1d23", borderRadius: 8, padding: "12px 16px", marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
        <span>
          {progress.running ? "🔍 Searching..." : "✅ Complete"}{" "}
          <span style={{ color: "#aaa" }}>
            {progress.done}/{progress.total} found
            {progress.failed > 0 && `, ${progress.failed} failed`}
          </span>
        </span>
        <span style={{ color: "#4f7cf8" }}>{progress.percent}%</span>
      </div>
      <div style={{ height: 6, background: "#2a2d35", borderRadius: 3, overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            width: `${progress.percent}%`,
            background: progress.running ? "#3b82f6" : "#22c55e",
            borderRadius: 3,
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────
export default function MapsSearchPage() {
  // Search form state
  const [searchMode, setSearchMode] = useState<"quick" | "category">("category");
  const [queryText, setQueryText] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedCity, setSelectedCity] = useState("");
  const [selectedState, setSelectedState] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  // Listing filters
  const [filters, setFilters] = useState<ListingFilters>({ page: 1, per_page: 50 });
  const [filterSearch, setFilterSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterCity, setFilterCity] = useState("");
  const [filterHasEmail, setFilterHasEmail] = useState(false);
  const [filterHasPhone, setFilterHasPhone] = useState(false);
  const [filterMinRating, setFilterMinRating] = useState("");

  // Progress polling
  const [progress, setProgress] = useState<MapsProgress | null>(null);
  const [polling, setPolling] = useState(false);

  // Presets
  const { data: presets } = useQuery<MapsPresets>({
    queryKey: ["maps-presets"],
    queryFn: () => MapsService.getPresets(),
    staleTime: 60_000 * 30,
  });

  // Past searches
  const { data: searches, refetch: refetchSearches } = useQuery({
    queryKey: ["maps-searches"],
    queryFn: () => MapsService.listSearches({ page: 1, per_page: 10 }),
    staleTime: 10_000,
  });

  // Build effective filters
  const effectiveFilters: ListingFilters = {
    ...filters,
    search: filterSearch || undefined,
    category: filterCategory || undefined,
    city: filterCity || undefined,
    has_email: filterHasEmail || undefined,
    has_phone: filterHasPhone || undefined,
    min_rating: filterMinRating ? parseFloat(filterMinRating) : undefined,
  };

  // Listings
  const { data: listings, refetch: refetchListings } = useQuery({
    queryKey: ["maps-listings", effectiveFilters],
    queryFn: () => MapsService.listListings(effectiveFilters),
    staleTime: 5_000,
  });

  // Progress polling
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      try {
        const p = await MapsService.getProgress();
        setProgress(p);
        if (!p.running) {
          setPolling(false);
          setIsSearching(false);
          refetchListings();
          refetchSearches();
        }
      } catch {
        setPolling(false);
        setIsSearching(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, refetchListings, refetchSearches]);

  // Auto-select state when city is picked
  const handleCityChange = useCallback(
    (city: string) => {
      setSelectedCity(city);
      const match = presets?.cities.find((c) => c.city === city);
      setSelectedState(match?.state || "");
    },
    [presets]
  );

  // Start search
  const handleSearch = async () => {
    setSearchError("");
    const params: any = {};

    if (searchMode === "quick") {
      if (!queryText.trim()) {
        setSearchError("Enter a search query");
        return;
      }
      params.query_text = queryText.trim();
    } else {
      if (!selectedCategory || !selectedCity) {
        setSearchError("Select both category and city");
        return;
      }
      params.category = selectedCategory;
      params.city = selectedCity;
      params.state = selectedState;
    }

    setIsSearching(true);
    try {
      const result = await MapsService.startSearch(params);
      setProgress({ running: true, total: 0, done: 0, failed: 0, percent: 0, query_id: result.query_id, recently_found: [] });
      setPolling(true);
      // Auto-filter listings to this search
      setFilters((f) => ({ ...f, page: 1, search_query_id: result.query_id }));
    } catch (err: any) {
      setSearchError(err.response?.data?.detail || "Search failed");
      setIsSearching(false);
    }
  };

  const handleExport = () => {
    MapsService.exportCsv({
      search_query_id: filters.search_query_id,
      category: filterCategory || undefined,
      city: filterCity || undefined,
      has_email: filterHasEmail || undefined,
      has_phone: filterHasPhone || undefined,
    });
  };

  const totalPages = listings ? Math.ceil(listings.total / (filters.per_page || 50)) : 0;

  return (
    <div style={{ padding: "0 4px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: "1.5rem" }}>
          📍 Google Maps Business Search
        </h1>
        {listings && listings.total > 0 && (
          <button className="btn btn-secondary" onClick={handleExport}>
            ⬇ Export CSV
          </button>
        )}
      </div>

      {/* Search Panel */}
      <div style={{ background: "#13151a", borderRadius: 8, padding: 20, marginBottom: 20, border: "1px solid #2a2d35" }}>
        {/* Tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <button
            onClick={() => setSearchMode("category")}
            style={{
              padding: "6px 16px", borderRadius: 6, border: "none", cursor: "pointer",
              background: searchMode === "category" ? "#4f7cf8" : "#2a2d35",
              color: "#fff", fontSize: 13,
            }}
          >
            Category + City
          </button>
          <button
            onClick={() => setSearchMode("quick")}
            style={{
              padding: "6px 16px", borderRadius: 6, border: "none", cursor: "pointer",
              background: searchMode === "quick" ? "#4f7cf8" : "#2a2d35",
              color: "#fff", fontSize: 13,
            }}
          >
            Free Text Search
          </button>
        </div>

        {searchMode === "category" ? (
          <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label style={{ display: "block", fontSize: 12, color: "#aaa", marginBottom: 4 }}>Category</label>
              <select
                className="form-input"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                style={{ width: "100%" }}
              >
                <option value="">Select category...</option>
                {presets?.categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label style={{ display: "block", fontSize: 12, color: "#aaa", marginBottom: 4 }}>City</label>
              <select
                className="form-input"
                value={selectedCity}
                onChange={(e) => handleCityChange(e.target.value)}
                style={{ width: "100%" }}
              >
                <option value="">Select city...</option>
                {presets?.cities.map((c) => (
                  <option key={c.city} value={c.city}>
                    {c.city}, {c.state}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="btn btn-primary"
              onClick={handleSearch}
              disabled={isSearching}
              style={{ height: 38 }}
            >
              {isSearching ? "Searching..." : "🔍 Search"}
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: "block", fontSize: 12, color: "#aaa", marginBottom: 4 }}>Search Query</label>
              <input
                className="form-input"
                type="text"
                placeholder='e.g., "dentist in Melbourne" or "plumber Sydney NSW"'
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                style={{ width: "100%" }}
              />
            </div>
            <button
              className="btn btn-primary"
              onClick={handleSearch}
              disabled={isSearching}
              style={{ height: 38 }}
            >
              {isSearching ? "Searching..." : "🔍 Search"}
            </button>
          </div>
        )}

        {searchError && (
          <div style={{ color: "#ef4444", fontSize: 13, marginTop: 8 }}>{searchError}</div>
        )}
      </div>

      {/* Progress */}
      {progress && <ProgressBar progress={progress} />}

      {/* Past Searches */}
      {searches && searches.items.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: "0.9rem", color: "#aaa", marginBottom: 8 }}>Recent Searches</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              onClick={() => setFilters((f) => ({ ...f, page: 1, search_query_id: undefined }))}
              style={{
                padding: "4px 12px", borderRadius: 20, border: "1px solid #2a2d35",
                background: !filters.search_query_id ? "#4f7cf8" : "#1a1d23",
                color: "#fff", cursor: "pointer", fontSize: 12,
              }}
            >
              All Results
            </button>
            {searches.items.map((s: MapSearch) => (
              <button
                key={s.id}
                onClick={() => setFilters((f) => ({ ...f, page: 1, search_query_id: s.id }))}
                style={{
                  padding: "4px 12px", borderRadius: 20, border: "1px solid #2a2d35",
                  background: filters.search_query_id === s.id ? "#4f7cf8" : "#1a1d23",
                  color: "#fff", cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6,
                }}
              >
                <span style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: STATUS_COLORS[s.status] || "#666",
                  display: "inline-block",
                }} />
                {s.query_text}
                <span style={{ color: "#888" }}>({s.results_count})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{
        display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center",
        background: "#13151a", borderRadius: 8, padding: "10px 14px", border: "1px solid #2a2d35",
      }}>
        <input
          className="form-input"
          type="text"
          placeholder="Search business name..."
          value={filterSearch}
          onChange={(e) => { setFilterSearch(e.target.value); setFilters((f) => ({ ...f, page: 1 })); }}
          style={{ width: 200 }}
        />
        <select
          className="form-input"
          value={filterCategory}
          onChange={(e) => { setFilterCategory(e.target.value); setFilters((f) => ({ ...f, page: 1 })); }}
          style={{ width: 150 }}
        >
          <option value="">All Categories</option>
          {presets?.categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          className="form-input"
          value={filterCity}
          onChange={(e) => { setFilterCity(e.target.value); setFilters((f) => ({ ...f, page: 1 })); }}
          style={{ width: 150 }}
        >
          <option value="">All Cities</option>
          {presets?.cities.map((c) => (
            <option key={c.city} value={c.city}>{c.city}</option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, color: "#ccc", cursor: "pointer" }}>
          <input type="checkbox" checked={filterHasEmail} onChange={(e) => { setFilterHasEmail(e.target.checked); setFilters((f) => ({ ...f, page: 1 })); }} />
          Has Email
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, color: "#ccc", cursor: "pointer" }}>
          <input type="checkbox" checked={filterHasPhone} onChange={(e) => { setFilterHasPhone(e.target.checked); setFilters((f) => ({ ...f, page: 1 })); }} />
          Has Phone
        </label>
        <select
          className="form-input"
          value={filterMinRating}
          onChange={(e) => { setFilterMinRating(e.target.value); setFilters((f) => ({ ...f, page: 1 })); }}
          style={{ width: 120 }}
        >
          <option value="">Any Rating</option>
          <option value="3">3+ Stars</option>
          <option value="4">4+ Stars</option>
          <option value="4.5">4.5+ Stars</option>
        </select>
      </div>

      {/* Results count */}
      {listings && (
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 13, color: "#aaa" }}>
          <span>{listings.total.toLocaleString()} businesses</span>
          <span>Page {filters.page} of {totalPages}</span>
        </div>
      )}

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th>Business Name</th>
              <th>Address</th>
              <th>Phone</th>
              <th>Email</th>
              <th>Website</th>
              <th>Rating</th>
              <th>Reviews</th>
              <th>Category</th>
            </tr>
          </thead>
          <tbody>
            {listings?.items.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 40, color: "#666" }}>
                  {filters.search_query_id
                    ? "No results for this search. Try a different query."
                    : "No business listings yet. Start a search above!"}
                </td>
              </tr>
            )}
            {listings?.items.map((b: BusinessListing) => (
              <tr key={b.id}>
                <td style={{ fontWeight: 500, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {b.business_name}
                </td>
                <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#aaa" }}>
                  {b.address || "—"}
                </td>
                <td>
                  {b.phone ? (
                    <a href={`tel:${b.phone}`} style={{ color: "#4f7cf8" }}>{b.phone}</a>
                  ) : (
                    <span style={{ color: "#5a6278" }}>—</span>
                  )}
                </td>
                <td>
                  {b.email ? (
                    <a href={`mailto:${b.email}`} style={{ color: "#22c55e" }}>{b.email}</a>
                  ) : (
                    <span style={{ color: "#5a6278" }}>—</span>
                  )}
                </td>
                <td>
                  {b.website ? (
                    <a href={b.website.startsWith("http") ? b.website : `https://${b.website}`}
                       target="_blank" rel="noopener noreferrer"
                       style={{ color: "#4f7cf8", maxWidth: 150, display: "inline-block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {b.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                    </a>
                  ) : (
                    <span style={{ color: "#5a6278" }}>—</span>
                  )}
                </td>
                <td><Stars rating={b.rating} /></td>
                <td style={{ color: b.reviews_count ? "#ccc" : "#5a6278" }}>
                  {b.reviews_count ?? "—"}
                </td>
                <td style={{ color: "#aaa", fontSize: "0.85em", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {b.category || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16 }}>
          <button
            className="btn btn-secondary"
            disabled={(filters.page || 1) <= 1}
            onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) - 1 }))}
            style={{ padding: "6px 14px" }}
          >
            ← Prev
          </button>
          <span style={{ display: "flex", alignItems: "center", color: "#aaa", fontSize: 13 }}>
            {filters.page} / {totalPages}
          </span>
          <button
            className="btn btn-secondary"
            disabled={(filters.page || 1) >= totalPages}
            onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) + 1 }))}
            style={{ padding: "6px 14px" }}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
