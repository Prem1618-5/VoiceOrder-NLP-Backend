type Status = 'operational' | 'degraded' | 'error';

interface StatusDotProps {
  status: Status;
}

const statusConfig: Record<Status, { color: string; animation: string; label: string }> = {
  operational: {
    color: 'bg-[#16A34A]',
    animation: '',
    label: 'System status: operational',
  },
  degraded: {
    color: 'bg-[#D97706]',
    animation: 'status-pulse-slow',
    label: 'System status: degraded',
  },
  error: {
    color: 'bg-[#DC2626]',
    animation: 'status-pulse-fast',
    label: 'System status: error',
  },
};

export default function StatusDot({ status }: StatusDotProps) {
  const { color, animation, label } = statusConfig[status];

  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-block w-2 h-2 rounded-full ${color} ${animation}`}
    />
  );
}
