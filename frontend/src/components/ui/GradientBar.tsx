interface GradientBarProps {
  height?: 3 | 4;
  className?: string;
}

export default function GradientBar({ height = 4, className = '' }: GradientBarProps) {
  const barClass = height === 3 ? 'gradient-bar-3' : 'gradient-bar';

  return (
    <div
      role="separator"
      aria-hidden="true"
      className={`${barClass} ${className}`}
    />
  );
}
