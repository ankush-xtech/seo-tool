import { useState, FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import AuthService from "../../services/auth.service";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirm) {
      setError("Passwords do not match");
      return;
    }
    setIsLoading(true);
    try {
      await AuthService.register({
        full_name: form.full_name,
        email: form.email,
        password: form.password,
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Registration failed.");
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
          <h2 style={{ marginBottom: 8 }}>Account created!</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: 24 }}>
            Your account is pending verification. An admin will activate it shortly.
          </p>
          <Link to="/login" className="btn-primary" style={{ display: "inline-block" }}>
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="logo-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M6 10h8M10 6v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <span>SEO Automation</span>
        </div>

        <h1 className="auth-title">Request access</h1>
        <p className="auth-subtitle">Create your team account</p>

        {error && (
          <div className="alert alert-error">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/>
              <path d="M7 4v4M7 9.5v.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="field">
            <label>Full name</label>
            <input
              type="text"
              value={form.full_name}
              onChange={set("full_name")}
              placeholder="Ankush Sharma"
              required
              autoFocus
            />
          </div>
          <div className="field">
            <label>Email address</label>
            <input
              type="email"
              value={form.email}
              onChange={set("email")}
              placeholder="you@company.com"
              required
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={form.password}
              onChange={set("password")}
              placeholder="Min 8 chars, 1 uppercase, 1 number"
              required
            />
          </div>
          <div className="field">
            <label>Confirm password</label>
            <input
              type="password"
              value={form.confirm}
              onChange={set("confirm")}
              placeholder="••••••••"
              required
            />
          </div>
          <button type="submit" className="btn-primary" disabled={isLoading}>
            {isLoading ? <span className="btn-spinner" /> : null}
            {isLoading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{" "}
          <Link to="/login" className="link-accent">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
