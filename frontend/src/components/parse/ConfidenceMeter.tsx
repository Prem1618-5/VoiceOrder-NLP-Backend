import { useMemo } from 'react';
import Badge from '@/components/ui/Badge';

/* ── Props ─────────────────────────────────────────────────────────────────── */

interface ConfidenceMeterProps {
  value: number; // 0.0 to 1.0
  forReview: boolean;
}

/* ── Helpers ───────────────────────────────────────────────────────────────── */

interface ConfidenceLevel {
  color: string;
  label: string;
  symbol: string;
}

function getLevel(value: number): ConfidenceLevel {
  if (value > 0.8) {
    return { color: '#16A34A', label: 'High confidence', symbol: '✓' };
  }
  if (value >= 0.6) {
    return { color: '#D97706', label: 'Moderate confidence', symbol: '◐' };
  }
  return { color: '#DC2626', label: 'Low confidence — flagged for review', symbol: '⚠' };
}

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function ConfidenceMeter({ value, forReview }: ConfidenceMeterProps) {
  const level = useMemo(() => getLevel(value), [value]);
  const pct = `${Math.round(value * 100)}%`;

  return (
    <div>
      <h3 className="text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-3">
        CONFIDENCE
      </h3>

      {/* ── Bar + value ────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <div
          className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden"
          role="meter"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={1}
          aria-label="Parse confidence"
        >
          <div
            className="confidence-bar-fill h-full rounded-full"
            style={{
              width: pct,
              backgroundColor: level.color,
            }}
          />
        </div>

        <span
          className="text-sm font-mono font-semibold tabular-nums min-w-[3rem] text-right"
          style={{ color: level.color }}
        >
          {value.toFixed(2)}
        </span>
      </div>

      {/* ── Descriptive label ──────────────────────────────────────────── */}
      <p
        className="text-xs mt-1.5 font-medium"
        style={{ color: level.color }}
        aria-live="polite"
      >
        {level.symbol} {level.label}
      </p>

      {/* ── Flagged badge ──────────────────────────────────────────────── */}
      {forReview && (
        <div className="mt-3">
          <Badge variant="warning">⚠ Flagged for Review</Badge>
        </div>
      )}
    </div>
  );
}
