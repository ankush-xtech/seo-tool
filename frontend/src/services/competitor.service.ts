import api from "./api";

export type AnalysisStatus = "pending" | "running" | "done" | "failed";

export interface CompetitorAnalysis {
  id: number;
  target_domain: string;
  target_category: string | null;
  target_city: string | null;
  target_state: string | null;
  status: AnalysisStatus;
  discovery_method: string | null;
  competitors_found: number;
  error_message: string | null;
  created_at: string;
}

export interface CompetitorEntry {
  id: number;
  domain: string;
  business_name: string | null;
  discovery_source: string | null;
  search_rank: number | null;
  is_target: boolean;
  seo_overall_score: number | null;
  seo_dns_score: number | null;
  seo_https_score: number | null;
  seo_meta_score: number | null;
  seo_robots_score: number | null;
  seo_sitemap_score: number | null;
  seo_speed_score: number | null;
  seo_mobile_score: number | null;
  seo_ssl_score: number | null;
  seo_social_meta_score: number | null;
  seo_heading_score: number | null;
  semrush_rank: number | null;
  organic_traffic: number | null;
  organic_keywords: number | null;
  domain_authority: number | null;
  backlinks_total: number | null;
  referring_domains: number | null;
  maps_rating: number | null;
  maps_reviews: number | null;
}

export interface Insight {
  id: number;
  insight_type: string;
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  meta: Record<string, any> | null;
}

export interface ComparisonResponse {
  target: CompetitorEntry | null;
  competitors: CompetitorEntry[];
  insights: Insight[];
}

export interface AnalysisList {
  items: CompetitorAnalysis[];
  total: number;
  page: number;
  per_page: number;
}

export interface AnalysisProgress {
  running: boolean;
  total: number;
  done: number;
  failed: number;
  percent: number;
  phase: string;
  analysis_id: number | null;
}

export interface ListingOption {
  id: number;
  business_name: string;
  website: string;
  category: string | null;
  city: string | null;
  state: string | null;
  rating: number | null;
  reviews_count: number | null;
}

const CompetitorService = {
  async startAnalysis(params: {
    target_domain: string;
    business_listing_id?: number;
    category?: string;
    city?: string;
    state?: string;
    max_competitors?: number;
    include_seo_checks?: boolean;
    include_semrush?: boolean;
  }) {
    const { data } = await api.post("/competitors/analyze", params);
    return data;
  },

  async getProgress(): Promise<AnalysisProgress> {
    const { data } = await api.get("/competitors/progress");
    return data;
  },

  async listAnalyses(params?: { page?: number; per_page?: number; status?: string }): Promise<AnalysisList> {
    const { data } = await api.get("/competitors/analyses", { params });
    return data;
  },

  async getComparison(analysisId: number): Promise<ComparisonResponse> {
    const { data } = await api.get(`/competitors/analyses/${analysisId}/comparison`);
    return data;
  },

  async getListingsWithWebsites(search?: string): Promise<ListingOption[]> {
    const { data } = await api.get("/competitors/listings-with-websites", {
      params: search ? { search } : {},
    });
    return data;
  },

  async exportCsv(analysisId: number) {
    const response = await api.get(`/competitors/analyses/${analysisId}/export/csv`, {
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `competitor_analysis_${analysisId}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};

export default CompetitorService;
