import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ProtectedRoute, AdminRoute, GuestRoute } from "./components/auth/ProtectedRoute";
import AppLayout from "./components/layout/AppLayout";

import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import DashboardPage from "./pages/user/DashboardPage";
import DomainsPage from "./pages/user/DomainsPage";
import SEOCheckerPage from "./pages/user/SEOCheckerPage";
import WatchlistPage from "./pages/user/WatchlistPage";
import AlertsPage from "./pages/user/AlertsPage";
import ReportsPage from "./pages/user/ReportsPage";
import AdminDashboardPage from "./pages/admin/AdminDashboardPage";
import AdminUsersPage from "./pages/admin/AdminUsersPage";
import AuditLogsPage from "./pages/admin/AuditLogsPage";
import MapsSearchPage from "./pages/admin/MapsSearchPage";
import CompetitorPage from "./pages/user/CompetitorPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function RootRedirect() {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Navigate to={isAdmin ? "/admin" : "/dashboard"} replace />;
}

const P = (children: React.ReactNode) => (
  <ProtectedRoute><AppLayout>{children}</AppLayout></ProtectedRoute>
);
const A = (children: React.ReactNode) => (
  <AdminRoute><AppLayout>{children}</AppLayout></AdminRoute>
);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login"    element={<GuestRoute><LoginPage /></GuestRoute>} />
            <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />

            <Route path="/dashboard"   element={P(<DashboardPage />)} />
            <Route path="/domains"     element={P(<DomainsPage />)} />
            <Route path="/seo-checker" element={P(<SEOCheckerPage />)} />
            <Route path="/watchlist"   element={P(<WatchlistPage />)} />
            <Route path="/alerts"      element={P(<AlertsPage />)} />
            <Route path="/reports"      element={P(<ReportsPage />)} />
            <Route path="/competitors" element={P(<CompetitorPage />)} />

            <Route path="/admin"            element={A(<AdminDashboardPage />)} />
            <Route path="/admin/users"      element={A(<AdminUsersPage />)} />
            <Route path="/admin/audit-logs" element={A(<AuditLogsPage />)} />
            <Route path="/admin/maps"       element={A(<MapsSearchPage />)} />

            <Route path="/" element={<RootRedirect />} />
            <Route path="*" element={<RootRedirect />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
