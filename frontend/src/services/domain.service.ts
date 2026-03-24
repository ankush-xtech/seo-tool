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

export interface ImportReportRow {
  domain: string;
  status: "imported" | "duplicate" | "invalid";
  reason?: string | null;
}

export interface ImportCsvResponse {
  filename: string;
  total_rows: number;
  valid_rows: number;
  imported_count: number;
  duplicate_count: number;
  invalid_count: number;
  report_rows: ImportReportRow[];
  report_truncated: boolean;
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
    params.set("limit", "2000");
    const base = (import.meta as any)?.env?.VITE_API_URL || "http://localhost:8000/api/v1";
    return `${base}/domains/export/csv?${params}`;
  },

  async exportCsv(filters: Omit<DomainFilters, "page" | "per_page" | "sort_by" | "sort_dir"> = {}) {
    const params: Record<string, string> = {};
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params[k] = String(v);
    });
    params.limit = "2000";

    const response = await api.get("/domains/export/csv", {
      params,
      responseType: "blob",
    });

    const disposition = response.headers["content-disposition"] as string | undefined;
    const filenameMatch = disposition?.match(/filename=([^;]+)/i);
    const filename = filenameMatch?.[1]?.replace(/"/g, "") || "domains_export.csv";

    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  async importCsv(file: File): Promise<ImportCsvResponse> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await api.post("/domains/import/csv", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
};

export default DomainService;
