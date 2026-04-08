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

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function RootRedirect() {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Navigate to={isAdmin ? "/admin" : "/dashboard"} replace />;
}

function ProtectedPage({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute><AppLayout>{children}</AppLayout></ProtectedRoute>;
}
function AdminPage({ children }: { children: React.ReactNode }) {
  return <AdminRoute><AppLayout>{children}</AppLayout></AdminRoute>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login"    element={<GuestRoute><LoginPage /></GuestRoute>} />
            <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />

            <Route path="/dashboard"   element={<ProtectedPage><DashboardPage /></ProtectedPage>} />
            <Route path="/domains"     element={<ProtectedPage><DomainsPage /></ProtectedPage>} />
            <Route path="/seo-checker" element={<ProtectedPage><SEOCheckerPage /></ProtectedPage>} />
            <Route path="/watchlist"   element={<ProtectedPage><WatchlistPage /></ProtectedPage>} />
            <Route path="/alerts"      element={<ProtectedPage><AlertsPage /></ProtectedPage>} />
            <Route path="/reports"     element={<ProtectedPage><ReportsPage /></ProtectedPage>} />

            <Route path="/admin"            element={<AdminPage><AdminDashboardPage /></AdminPage>} />
            <Route path="/admin/users"      element={<AdminPage><AdminUsersPage /></AdminPage>} />
            <Route path="/admin/audit-logs" element={<AdminPage><AuditLogsPage /></AdminPage>} />
            <Route path="/admin/maps"       element={<AdminPage><MapsSearchPage /></AdminPage>} />

            <Route path="/" element={<RootRedirect />} />
            <Route path="*" element={<RootRedirect />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
