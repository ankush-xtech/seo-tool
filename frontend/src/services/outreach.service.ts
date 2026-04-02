import api from "./api";

export interface Lead {
  listing_id: number;
  business_name: string;
  website: string | null;
  city: string | null;
  category: string | null;
  email: string | null;
  phone: string | null;
  seo_score: number | null;
  seo_verdict: string | null;
  seo_status: string | null;
  email_status: string | null;
  email_sent_at: string | null;
  email_opened_at: string | null;
  email_clicked_at: string | null;
  email_replied_at: string | null;
}

export interface LeadList {
  items: Lead[];
  total: number;
  page: number;
  per_page: number;
}

export interface OutreachStats {
  total_leads: number;
  with_website: number;
  with_email: number;
  seo_checked: number;
  score_below_70: number;
  emails_sent: number;
  emails_opened: number;
  emails_clicked: number;
  emails_replied: number;
  open_rate: number;
  reply_rate: number;
}

export interface SEOProgress {
  running: boolean;
  total: number;
  done: number;
  failed: number;
  percent: number;
  recently_checked: Record<string, any>[];
}

export interface EmailPreview {
  listing_id: number;
  business_name: string;
  to_email: string;
  subject: string;
  body_html: string;
  seo_score: number;
  problems: string[];
}

export interface LeadFilters {
  page?: number;
  per_page?: number;
  search_query_id?: number;
  category?: string;
  city?: string;
  has_email?: boolean;
  max_score?: number;
  min_score?: number;
  email_status?: string;
  search?: string;
}

const OutreachService = {
  async runSEOCheck(search_query_id?: number) {
    const params: Record<string, any> = {};
    if (search_query_id) params.search_query_id = search_query_id;
    const { data } = await api.post("/outreach/run-seo-check", null, { params });
    return data;
  },

  async getSEOProgress(): Promise<SEOProgress> {
    const { data } = await api.get("/outreach/seo-progress");
    return data;
  },

  async getStats(search_query_id?: number): Promise<OutreachStats> {
    const params: Record<string, any> = {};
    if (search_query_id) params.search_query_id = search_query_id;
    const { data } = await api.get("/outreach/stats", { params });
    return data;
  },

  async listLeads(filters: LeadFilters = {}): Promise<LeadList> {
    const params: Record<string, any> = {};
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params[k] = v;
    });
    const { data } = await api.get("/outreach/leads", { params });
    return data;
  },

  async previewEmails(params: {
    max_score?: number;
    search_query_id?: number;
    category?: string;
    city?: string;
    limit?: number;
  }): Promise<EmailPreview[]> {
    const { data } = await api.post("/outreach/preview-emails", params);
    return data;
  },

  async sendEmails(params: {
    max_score?: number;
    search_query_id?: number;
    category?: string;
    city?: string;
    limit?: number;
  }) {
    const { data } = await api.post("/outreach/send-emails", params);
    return data;
  },

  async sendSelectedEmails(listing_ids: number[], mode: "ai" | "template") {
    const { data } = await api.post("/outreach/send-selected-emails", { listing_ids, mode });
    return data as { sent: number; failed: number; skipped: number; total_requested: number; mode: string; errors?: string[] };
  },

  async updateEmailStatus(emailId: number, newStatus: string) {
    const { data } = await api.put(`/outreach/emails/${emailId}/status`, null, {
      params: { new_status: newStatus },
    });
    return data;
  },
};

export default OutreachService;
