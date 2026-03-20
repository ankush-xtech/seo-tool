import api from "./api";

export type AlertCondition = "score_above" | "score_below" | "score_drop" | "check_failed";

export interface AlertRule {
  id: number;
  user_id: number;
  name: string;
  condition: AlertCondition;
  threshold: number | null;
  tld_filter: string | null;
  is_active: boolean;
  email_notify: boolean;
  created_at: string;
}

export interface Notification {
  id: number;
  user_id: number;
  title: string;
  message: string;
  status: "unread" | "read";
  meta: Record<string, any> | null;
  created_at: string;
}

export interface NotificationList {
  notifications: Notification[];
  total: number;
  unread_count: number;
  page: number;
  per_page: number;
}

const AlertsService = {
  // ─── Alert Rules ───────────────────────────────────────────────────────────
  async listRules(): Promise<AlertRule[]> {
    const { data } = await api.get("/alerts/rules");
    return data;
  },

  async createRule(payload: Omit<AlertRule, "id" | "user_id" | "created_at">): Promise<AlertRule> {
    const { data } = await api.post("/alerts/rules", payload);
    return data;
  },

  async updateRule(id: number, payload: Partial<AlertRule>): Promise<AlertRule> {
    const { data } = await api.put(`/alerts/rules/${id}`, payload);
    return data;
  },

  async deleteRule(id: number): Promise<void> {
    await api.delete(`/alerts/rules/${id}`);
  },

  // ─── Notifications ─────────────────────────────────────────────────────────
  async listNotifications(params?: { page?: number; unread_only?: boolean }): Promise<NotificationList> {
    const { data } = await api.get("/alerts/notifications", { params });
    return data;
  },

  async getUnreadCount(): Promise<number> {
    const { data } = await api.get("/alerts/notifications/unread-count");
    return data.count;
  },

  async markRead(id: number): Promise<void> {
    await api.post(`/alerts/notifications/${id}/read`);
  },

  async markAllRead(): Promise<void> {
    await api.post("/alerts/notifications/read-all");
  },
};

export default AlertsService;
