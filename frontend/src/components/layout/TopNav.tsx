import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useMetrics } from '@/hooks/useMetrics';
import StatusDot from '@/components/ui/StatusDot';

/* ── Nav items ─────────────────────────────────────────────────────────────── */

const navItems = [
  {
    label: 'Dashboard',
    to: '/',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
        <rect x="1" y="1" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
        <rect x="8.5" y="1" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
        <rect x="1" y="8.5" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
        <rect x="8.5" y="8.5" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.4"/>
      </svg>
    ),
  },
  {
    label: 'Parse Order',
    to: '/parse',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
        <path d="M2 7.5h11M9 3.5l4 4-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    label: 'Session',
    to: '/session',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
        <path d="M1.5 3C1.5 2.17 2.17 1.5 3 1.5h9c.83 0 1.5.67 1.5 1.5v7c0 .83-.67 1.5-1.5 1.5H4.5L1.5 13V3z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    label: 'History',
    to: '/history',
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
        <path d="M3 4h9M3 7.5h9M3 11h5.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
    ),
  },
];

/* ── Helpers ───────────────────────────────────────────────────────────────── */

function getInitial(email: string): string {
  return (email[0] ?? '?').toUpperCase();
}

function resolveStatus(
  health: { status: 'ok' | 'degraded' } | null,
  isLoading: boolean,
  error: string | null,
): 'operational' | 'degraded' | 'error' {
  if (isLoading) return 'operational';
  if (error || !health) return 'error';
  return health.status === 'ok' ? 'operational' : 'degraded';
}

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function TopNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { health, isLoading, error } = useMetrics();

  const email = user?.email ?? '';
  const dotStatus = resolveStatus(health, isLoading, error);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <header
      className="glass-nav sticky top-0 z-50 w-full h-14"
      role="banner"
    >
      <div className="max-w-7xl mx-auto h-full px-6 flex items-center gap-6">

        {/* ── Logo ──────────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-2 shrink-0">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true" className="text-[#6366F1]">
            <rect x="3" y="7" width="2.5" height="8" rx="1.25" fill="currentColor"/>
            <rect x="7.5" y="3" width="2.5" height="16" rx="1.25" fill="currentColor"/>
            <rect x="12" y="5" width="2.5" height="12" rx="1.25" fill="currentColor"/>
            <rect x="16.5" y="8" width="2.5" height="6" rx="1.25" fill="currentColor"/>
          </svg>
          <span className="text-[15px] font-bold text-[#111827] tracking-tight select-none">
            VoiceOrder
          </span>
        </div>

        {/* ── Nav links (center) ─────────────────────────────────────────────── */}
        <nav className="flex items-center gap-1 flex-1 justify-center" aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `nav-link flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                  isActive
                    ? 'active bg-[#EEF2FF] text-[#6366F1]'
                    : 'text-[#6B7280] hover:bg-gray-100/70 hover:text-[#111827]'
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* ── User chip (right) ──────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 shrink-0">
          {/* System status */}
          <div className="flex items-center gap-1.5" title={`System: ${dotStatus}`}>
            <StatusDot status={dotStatus} />
          </div>

          {/* User info */}
          <div className="hidden sm:block text-right">
            <p className="text-[13px] font-medium text-[#111827] leading-tight">
              {email}
            </p>
            <p className="text-[11px] text-[#9CA3AF] leading-tight">
              20 req/min
            </p>
          </div>

          {/* Avatar */}
          <div
            className="w-8 h-8 rounded-full bg-[#6366F1] flex items-center justify-center shrink-0 shadow-sm"
            aria-hidden="true"
          >
            <span className="text-xs font-bold text-white leading-none">
              {getInitial(email)}
            </span>
          </div>

          {/* Logout */}
          <button
            type="button"
            onClick={handleLogout}
            className="btn-ghost !px-2.5 !py-1.5 !text-[13px]"
            aria-label="Sign out"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M5 13H2.5C1.67 13 1 12.33 1 11.5v-9C1 1.67 1.67 1 2.5 1H5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              <path d="M9.5 10L13 7l-3.5-3M13 7H5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </div>
    </header>
  );
}
