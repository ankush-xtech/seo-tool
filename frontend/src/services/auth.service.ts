import api, { tokenStorage } from "./api";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "user";
  is_active: boolean;
  is_verified: boolean;
  last_login: string | null;
  created_at: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  full_name: string;
  password: string;
  role?: "admin" | "user";
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface UserUpdate {
  full_name?: string;
  email?: string;
  role?: "admin" | "user";
  is_active?: boolean;
}

const AuthService = {
  async login(payload: LoginPayload): Promise<{ user: User; access_token: string; refresh_token: string }> {
    const { data } = await api.post("/auth/login", payload);
    tokenStorage.setTokens(data.access_token, data.refresh_token);
    return data;
  },

  async register(payload: RegisterPayload): Promise<User> {
    const { data } = await api.post("/auth/register", payload);
    return data;
  },

  async logout(): Promise<void> {
    const refresh_token = tokenStorage.getRefresh();
    if (refresh_token) {
      try {
        await api.post("/auth/logout", { refresh_token });
      } catch {
        // Ignore errors on logout — clear local state regardless
      }
    }
    tokenStorage.clear();
  },

  async getMe(): Promise<User> {
    const { data } = await api.get("/auth/me");
    return data;
  },

  async changePassword(payload: ChangePasswordPayload): Promise<void> {
    await api.put("/auth/change-password", payload);
  },

  // ─── User Management (Admin) ───────────────────────────────────────────────
  async listUsers(params?: {
    page?: number;
    per_page?: number;
    role?: string;
    is_active?: boolean;
    search?: string;
  }) {
    const { data } = await api.get("/users/", { params });
    return data;
  },

  async createUser(payload: RegisterPayload): Promise<User> {
    const { data } = await api.post("/users/", payload);
    return data;
  },

  async updateUser(userId: number, payload: UserUpdate): Promise<User> {
    const { data } = await api.put(`/users/${userId}`, payload);
    return data;
  },

  async deactivateUser(userId: number): Promise<void> {
    await api.delete(`/users/${userId}`);
  },
};

export default AuthService;
