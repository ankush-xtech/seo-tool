import api from "./api";

export type DomainStatus = "pending" | "running" | "done" | "failed" | "skipped";

export interface Domain {
  id: number;
  name: string;
  tld: string;
  registrar: string | null;
  registered_at: string | null;
  fetched_date: string;
  check_status: DomainStatus;
  seo_score: number | null;
  created_at: string;
}

export interface DomainList {
  domains: Domain[];
  total: number;
  page: number;
  per_page: number;
}

export interface DomainStats {
  total_domains: number;
  fetched_today: number;
  pending_check: number;
  checked: number;
  avg_seo_score: number | null;
}

export interface DomainFilters {
  page?: number;
  per_page?: number;
  tld?: string;
  status?: DomainStatus;
  min_score?: number;
  max_score?: number;
  search?: string;
  date_from?: string;
  date_to?: string;
  sort_by?: "fetched_date" | "seo_score" | "name";
  sort_dir?: "asc" | "desc";
}

export interface FetchTriggerResponse {
  status: string;
  date: string;
  total_fetched: number;
  new_domains: number;
  duplicates_skipped: number;
  duration_seconds: number;
  task_id: string | null;
}

export interface TaskStatus {
  task_id: string;
  status: "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY";
  result: Record<string, unknown> | null;
  error: string | null;
}

const DomainService = {
  async list(filters: DomainFilters = {}): Promise<DomainList> {
    const { data } = await api.get("/domains/", { params: filters });
    return data;
  },

  async getById(id: number): Promise<Domain> {
    const { data } = await api.get(`/domains/${id}`);
    return data;
  },

  async getStats(): Promise<DomainStats> {
    const { data } = await api.get("/domains/stats");
    return data;
  },

  async triggerFetch(fetchDate?: string): Promise<FetchTriggerResponse> {
    const { data } = await api.post("/domains/fetch", { fetch_date: fetchDate ?? null });
    return data;
  },

  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const { data } = await api.get(`/domains/fetch/status/${taskId}`);
    return data;
  },

  getExportUrl(filters: Omit<DomainFilters, "page" | "per_page" | "sort_by" | "sort_dir"> = {}): string {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
    });
    const base = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
    return `${base}/domains/export/csv?${params}`;
  },
};

export default DomainService;
