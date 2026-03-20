import api from "./api";

export interface UserDashboardStats {
  total_domains: number;
  fetched_today: number;
  pending_check: number;
  checked: number;
  failed: number;
  avg_seo_score: number | null;
  score_distribution: { good: number; average: number; poor: number };
  top_tlds: { tld: string; count: number }[];
  daily_fetched: { date: string; count: number }[];
}

export interface AdminDashboardStats extends UserDashboardStats {
  total_users: number;
  active_users: number;
  admin_count: number;
  checked_today: number;
  failed_today: number;
  recent_audit_logs: AuditLog[];
}

export interface AuditLog {
  id: number;
  user_id: number | null;
  user_email: string | null;
  action: string;
  description: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogList {
  logs: AuditLog[];
  total: number;
  page: number;
  per_page: number;
}

const DashboardService = {
  async getAdminStats(): Promise<AdminDashboardStats> {
    const { data } = await api.get("/dashboard/admin");
    return data;
  },

  async getUserStats(): Promise<UserDashboardStats> {
    const { data } = await api.get("/dashboard/user");
    return data;
  },

  async getAuditLogs(params?: {
    page?: number;
    per_page?: number;
    action?: string;
    user_id?: number;
  }): Promise<AuditLogList> {
    const { data } = await api.get("/dashboard/audit-logs", { params });
    return data;
  },
};

export default DashboardService;
