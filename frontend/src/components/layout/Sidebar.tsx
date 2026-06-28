import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

/* ── Navigation items ──────────────────────────────────────────────────────── */

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    to: '/',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    label: 'Parse Order',
    to: '/parse',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M13 8L3 8M3 8L7 4M3 8L7 12"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    label: 'Session Chat',
    to: '/session',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M2 3.5C2 2.67 2.67 2 3.5 2H12.5C13.33 2 14 2.67 14 3.5V10.5C14 11.33 13.33 12 12.5 12H5L2 14.5V3.5Z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    label: 'History',
    to: '/history',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M4 4H12M4 8H12M4 12H9"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
];

/* ── Style helpers ─────────────────────────────────────────────────────────── */

const activeClass =
  'bg-white/[0.12] border-l-[3px] border-[#6366F1] rounded-lg px-3 py-2.5 text-white text-sm font-medium flex items-center gap-2.5';

const inactiveClass =
  'text-white/55 text-sm px-3 py-2.5 rounded-lg hover:bg-white/[0.06] transition-colors duration-100 flex items-center gap-2.5 border-l-[3px] border-transparent';

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function Sidebar() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <aside
      className="w-[220px] bg-[#1C1C1E] flex flex-col py-5 px-3 shrink-0"
      aria-label="Main navigation"
    >
      {/* ── Logo ────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-2 mb-1">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
          className="text-[#6366F1] shrink-0"
        >
          <rect x="4" y="8" width="2.5" height="8" rx="1.25" fill="currentColor" />
          <rect x="8.5" y="4" width="2.5" height="16" rx="1.25" fill="currentColor" />
          <rect x="13" y="6" width="2.5" height="12" rx="1.25" fill="currentColor" />
          <rect x="17.5" y="9" width="2.5" height="6" rx="1.25" fill="currentColor" />
        </svg>
        <span className="font-sans text-[18px] font-bold tracking-tight text-white select-none">
          VOICEORDER
        </span>
      </div>

      {/* ── Divider ─────────────────────────────────────────────────────── */}
      <div className="border-b border-white/15 my-3" role="separator" />

      {/* ── Nav items ───────────────────────────────────────────────────── */}
      <nav className="flex flex-col gap-0.5" aria-label="Primary">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => (isActive ? activeClass : inactiveClass)}
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* ── Spacer ──────────────────────────────────────────────────────── */}
      <div className="flex-1" />

      {/* ── Logout ──────────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={handleLogout}
        className="flex items-center gap-2.5 text-white/45 text-sm px-3 py-2.5 rounded-lg hover:bg-white/[0.06] hover:text-white/70 transition-colors duration-100 w-full"
        aria-label="Sign out"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M6 14H3.5C2.67 14 2 13.33 2 12.5V3.5C2 2.67 2.67 2 3.5 2H6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M11 11L14 8L11 5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M14 8H6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Logout
      </button>
    </aside>
  );
}
