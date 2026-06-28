import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import Sidebar from './Sidebar';
import ContentHeader from './ContentHeader';

export default function AppShell() {
  const { isAuthenticated, isLoading } = useAuth();

  /* ── Wait for auth state to hydrate from localStorage ─────────────────── */
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" role="status">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#6366F1] border-t-transparent" />
        <span className="sr-only">Loading…</span>
      </div>
    );
  }

  /* ── Redirect unauthenticated users to the login page ─────────────────── */
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen p-6">
      <main className="bg-white rounded-[20px] shadow-xl flex min-h-[calc(100vh-48px)] overflow-hidden">
        {/* ── Sidebar (220 px) ──────────────────────────────────────────── */}
        <Sidebar />

        {/* ── Content area ──────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col bg-[#F8FAFC]">
          <ContentHeader />
          <main className="flex-1 overflow-y-auto px-6 py-5">
            <Outlet />
          </main>
        </div>
      </main>
    </div>
  );
}
