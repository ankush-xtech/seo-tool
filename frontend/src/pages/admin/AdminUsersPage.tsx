import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AuthService, { User } from "../../services/auth.service";

interface UserModalProps {
  user?: User | null;
  onClose: () => void;
  onSaved: () => void;
}

function UserModal({ user, onClose, onSaved }: UserModalProps) {
  const isEdit = !!user;
  const [form, setForm] = useState({
    full_name: user?.full_name || "",
    email: user?.email || "",
    password: "",
    role: user?.role || "user",
    is_active: user?.is_active ?? true,
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      if (isEdit) {
        await AuthService.updateUser(user!.id, {
          full_name: form.full_name,
          email: form.email,
          role: form.role as any,
          is_active: form.is_active,
        });
      } else {
        await AuthService.createUser({
          full_name: form.full_name,
          email: form.email,
          password: form.password,
          role: form.role as any,
        });
      }
      onSaved();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2 className="modal-title">{isEdit ? "Edit user" : "Create new user"}</h2>
        {error && <div className="alert alert-error" style={{ marginBottom: 12 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field">
              <label>Full name</label>
              <input type="text" value={form.full_name} onChange={set("full_name")} required />
            </div>
            <div className="field">
              <label>Email</label>
              <input type="email" value={form.email} onChange={set("email")} required />
            </div>
            {!isEdit && (
              <div className="field">
                <label>Password</label>
                <input type="password" value={form.password} onChange={set("password")}
                  placeholder="Min 8 chars, 1 uppercase, 1 number" required />
              </div>
            )}
            <div className="field">
              <label>Role</label>
              <select value={form.role} onChange={set("role")} className="filter-select" style={{ width: "100%", height: 40 }}>
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            {isEdit && (
              <div className="field" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <input
                  type="checkbox"
                  id="is_active"
                  checked={form.is_active}
                  onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
                  style={{ width: 16, height: 16 }}
                />
                <label htmlFor="is_active" style={{ cursor: "pointer" }}>Account active</label>
              </div>
            )}
          </div>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" style={{ width: "auto", padding: "0 20px" }} disabled={saving}>
              {saving ? <span className="btn-spinner" /> : null}
              {saving ? "Saving…" : isEdit ? "Save changes" : "Create user"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState<{ open: boolean; user: User | null }>({ open: false, user: null });
  const [deactivating, setDeactivating] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page, search, roleFilter],
    queryFn: () => AuthService.listUsers({
      page, per_page: 20,
      search: search || undefined,
      role: roleFilter || undefined,
    }),
  });

  const handleDeactivate = async (user: User) => {
    if (!confirm(`Deactivate ${user.email}?`)) return;
    setDeactivating(user.id);
    try {
      await AuthService.deactivateUser(user.id);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } finally {
      setDeactivating(null);
    }
  };

  const onSaved = () => {
    setModal({ open: false, user: null });
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
  };

  return (
    <div>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">User management</h1>
          <p className="page-subtitle">Create and manage your team members</p>
        </div>
        <button
          className="btn-primary"
          style={{ width: "auto", padding: "0 16px", height: 38 }}
          onClick={() => setModal({ open: true, user: null })}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          New user
        </button>
      </div>

      {/* Filters */}
      <div className="filter-bar" style={{ marginBottom: 14 }}>
        <input
          type="text" placeholder="Search by name or email…"
          value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
          style={{ width: 240 }}
        />
        <select value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(1); }} className="filter-select">
          <option value="">All roles</option>
          <option value="admin">Admin</option>
          <option value="user">User</option>
        </select>
        {(search || roleFilter) && (
          <button className="btn-secondary" style={{ padding: "0 10px", fontSize: 12 }}
            onClick={() => { setSearch(""); setRoleFilter(""); setPage(1); }}>
            Clear
          </button>
        )}
      </div>

      <div className="table-container">
        <div className="table-header">
          <span className="table-title">
            {data ? `${data.total} users` : "Loading…"}
          </span>
        </div>

        {isLoading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
        ) : !data?.users.length ? (
          <div className="empty-state">
            <div className="empty-state-icon">👥</div>
            <div className="empty-state-title">No users found</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last login</th>
                <th>Joined</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.users.map((u: User) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 500 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: "50%",
                        background: "var(--accent-bg)", color: "var(--accent)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 11, fontWeight: 700, flexShrink: 0,
                      }}>
                        {u.full_name?.[0]?.toUpperCase()}
                      </div>
                      {u.full_name}
                    </div>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                    {u.email}
                  </td>
                  <td>
                    <span className={`badge ${u.role === "admin" ? "badge-info" : "badge-neutral"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? "badge-success" : "badge-danger"}`}>
                      {u.is_active ? "active" : "inactive"}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-hint)" }}>
                    {u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-hint)" }}>
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        className="btn-secondary"
                        style={{ padding: "0 10px", height: 28, fontSize: 12 }}
                        onClick={() => setModal({ open: true, user: u })}
                      >
                        Edit
                      </button>
                      {u.is_active && (
                        <button
                          className="btn-danger"
                          style={{ padding: "0 10px", height: 28, fontSize: 12 }}
                          onClick={() => handleDeactivate(u)}
                          disabled={deactivating === u.id}
                        >
                          {deactivating === u.id ? "…" : "Deactivate"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {data && data.total > 20 && (
          <div className="pagination">
            <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {page} / {Math.ceil(data.total / 20)}
            </span>
            <button className="btn-secondary" disabled={page >= Math.ceil(data.total / 20)} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        )}
      </div>

      {modal.open && (
        <UserModal user={modal.user} onClose={() => setModal({ open: false, user: null })} onSaved={onSaved} />
      )}
    </div>
  );
}
