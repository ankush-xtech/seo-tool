import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import NotificationBell from "../ui/NotificationBell";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", end: true,
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.2"/></svg> },
  { to: "/domains", label: "Domains",
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2"/><path d="M8 1.5S6 4 6 8s2 6.5 2 6.5M8 1.5S10 4 10 8s-2 6.5-2 6.5M1.5 8h13" stroke="currentColor" strokeWidth="1.2"/></svg> },
  { to: "/seo-checker", label: "SEO Checker",
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.2"/><path d="M10 10l4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M4.5 6.5h4M6.5 4.5v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> },
  { to: "/watchlist", label: "Watchlist",
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5l1.75 3.5 3.87.56-2.8 2.73.66 3.85L8 10.1l-3.48 1.84.66-3.85L2.38 5.56l3.87-.56L8 1.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg> },
  { to: "/alerts", label: "Alerts",
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2a4 4 0 00-4 4v3l-1.5 2h11L12 9V6a4 4 0 00-4-4z" stroke="currentColor" strokeWidth="1.2"/><path d="M6.5 13a1.5 1.5 0 003 0" stroke="currentColor" strokeWidth="1.2"/></svg> },
  { to: "/reports", label: "Reports",
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 2h10a1 1 0 011 1v10a1 1 0 01-1 1H3a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.2"/><path d="M5 6h6M5 9h4M5 12h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> },
  { to: "/admin", label: "Admin Panel", end: true, adminOnly: true,
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1.5" y="3" width="13" height="10" rx="2" stroke="currentColor" strokeWidth="1.2"/><path d="M5 7h6M5 10h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> },
  { to: "/admin/users", label: "Users", adminOnly: true,
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="6" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.2"/><path d="M1 13c0-2.76 2.24-5 5-5s5 2.24 5 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M11 7l1.5 1.5L15 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg> },
  { to: "/admin/audit-logs", label: "Audit Logs", adminOnly: true,
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 4h10M3 8h10M3 12h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> },
  { to: "/admin/maps", label: "Maps Search", adminOnly: true,
    icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1C5.2 1 3 3.2 3 6c0 3.5 5 9 5 9s5-5.5 5-9c0-2.8-2.2-5-5-5z" stroke="currentColor" strokeWidth="1.2"/><circle cx="8" cy="6" r="2" stroke="currentColor" strokeWidth="1.2"/></svg> },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => { await logout(); navigate("/login"); };
  const visibleItems = NAV_ITEMS.filter((item: any) => !item.adminOnly || isAdmin);

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo-icon small">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M5 8h6M8 5v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <span className="sidebar-brand">SEO Automation</span>
        </div>

        <nav className="sidebar-nav">
          {visibleItems.map((item: any) => (
            <NavLink key={item.to} to={item.to} end={item.end}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
              {item.icon}
              <span>{item.label}</span>
              {item.adminOnly && <span className="admin-badge">Admin</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="avatar">{user?.full_name?.[0]?.toUpperCase() || "U"}</div>
            <div className="user-info">
              <span className="user-name">{user?.full_name}</span>
              <span className="user-role">{user?.role}</span>
            </div>
          </div>
          <NotificationBell />
          <button className="logout-btn" onClick={handleLogout} title="Sign out">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3M10 11l3-3-3-3M13 8H6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
