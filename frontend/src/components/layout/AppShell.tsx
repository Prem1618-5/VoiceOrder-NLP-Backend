import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import TopNav from './TopNav';

export default function AppShell() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  /* ── Wait for auth state to hydrate from localStorage ─────────────────── */
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" role="status">
        <div className="flex flex-col items-center gap-3">
          <div className="h-9 w-9 animate-spin rounded-full border-[3px] border-[#6366F1] border-t-transparent" />
          <p className="text-sm text-[#6B7280] font-medium">Loading…</p>
        </div>
        <span className="sr-only">Loading application</span>
      </div>
    );
  }

  /* ── Redirect unauthenticated users to the login page ─────────────────── */
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  /* ── Page title derived from route for the document title ─────────────── */
  const pageTitles: Record<string, string> = {
    '/': 'Dashboard',
    '/parse': 'Parse Order',
    '/session': 'Session Chat',
    '/history': 'History',
  };
  const pageTitle = pageTitles[location.pathname] ?? 'VoiceOrder';
  document.title = `${pageTitle} — VoiceOrder NLP`;

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Sticky top glass nav ──────────────────────────────────────────── */}
      <TopNav />

      {/* ── Page content ─────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-6">
        <div className="page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
