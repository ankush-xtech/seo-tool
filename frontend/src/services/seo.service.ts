import api from "./api";

export interface SEOCheckResult {
  domain: string;
  overall_score: number;
  result_id: number;
  checks: {
    dns: Record<string, any>;
    https: Record<string, any>;
    meta: Record<string, any>;
    robots: Record<string, any>;
    sitemap: Record<string, any>;
    ssl: Record<string, any>;
    speed: Record<string, any>;
    mobile: Record<string, any>;
    social_meta: Record<string, any>;
    headings: Record<string, any>;
  };
}

export interface SEOResult {
  id: number;
  domain_id: number;
  checked_at: string;
  overall_score: number | null;
  dns_score: number | null;
  https_score: number | null;
  meta_score: number | null;
  robots_score: number | null;
  sitemap_score: number | null;
  ssl_score: number | null;
  speed_score: number | null;
  mobile_score: number | null;
  social_meta_score: number | null;
  heading_score: number | null;
  dns_data: Record<string, any> | null;
  https_data: Record<string, any> | null;
  meta_data: Record<string, any> | null;
  robots_data: Record<string, any> | null;
  sitemap_data: Record<string, any> | null;
  speed_data: Record<string, any> | null;
  ssl_data: Record<string, any> | null;
  social_meta_data: Record<string, any> | null;
  heading_data: Record<string, any> | null;
}

const SEOService = {
  async checkDomain(domain: string): Promise<SEOCheckResult> {
    const { data } = await api.post("/seo/check", { domain });
    return data;
  },

  async getDomainResults(domainId: number): Promise<SEOResult[]> {
    const { data } = await api.get(`/seo/results/${domainId}`);
    return data;
  },

  async getResultDetail(resultId: number): Promise<SEOResult> {
    const { data } = await api.get(`/seo/detail/${resultId}`);
    return data;
  },
};

export default SEOService;
