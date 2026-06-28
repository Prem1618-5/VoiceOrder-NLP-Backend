import { useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useMetrics } from '@/hooks/useMetrics';
import StatusDot from '@/components/ui/StatusDot';

/* ── Route → Page title map ────────────────────────────────────────────────── */

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/parse': 'Parse Order',
  '/session': 'Session Chat',
  '/history': 'History',
};

/* ── Helpers ───────────────────────────────────────────────────────────────── */

/** Map the HealthResponse status to the StatusDot status type. */
function resolveStatus(
  health: { status: 'ok' | 'degraded' } | null,
  isLoading: boolean,
  error: string | null,
): 'operational' | 'degraded' | 'error' {
  if (isLoading) return 'operational';
  if (error || !health) return 'error';
  if (health.status === 'ok') return 'operational';
  return 'degraded';
}

/** Extract the first character of an email as an uppercase initial. */
function getInitial(email: string): string {
  return (email[0] ?? '?').toUpperCase();
}

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function ContentHeader() {
  const location = useLocation();
  const { user } = useAuth();
  const { health, isLoading, error } = useMetrics();

  const title = pageTitles[location.pathname] ?? 'VoiceOrder';
  const dotStatus = resolveStatus(health, isLoading, error);
  const email = user?.email ?? 'user@voiceorder.io';

  return (
    <header className="sticky top-0 z-10 bg-white border-b border-[#E2E8F0] px-6 py-3 flex items-center justify-between">
      {/* ── Page title ──────────────────────────────────────────────────── */}
      <h1 className="font-sans text-[18px] font-bold text-[#111827] leading-tight select-none">
        {title}
      </h1>

      {/* ── User chip ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        {/* Status dot */}
        <StatusDot status={dotStatus} />

        {/* User info */}
        <div className="text-right mr-2">
          <p className="font-sans text-sm font-medium text-[#111827] leading-tight">
            {email}
          </p>
          <p className="font-sans text-xs text-[#6B7280] leading-tight">
            Dev account · 20 req/min
          </p>
        </div>

        {/* Avatar */}
        <div
          className="flex items-center justify-center w-8 h-8 rounded-full bg-[#6366F1] shrink-0"
          aria-hidden="true"
        >
          <span className="font-sans text-xs font-bold text-white leading-none">
            {getInitial(email)}
          </span>
        </div>
      </div>
    </header>
  );
}
