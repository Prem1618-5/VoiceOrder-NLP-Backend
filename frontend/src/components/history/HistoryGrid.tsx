/* ── HistoryGrid — Date-grouped two-column order card grid ─────────────────── */

import { useMemo } from 'react';
import type { OrderSummary } from '@/lib/api';
import Badge from '@/components/ui/Badge';

/* ── Props ────────────────────────────────────────────────────────────────── */

interface HistoryGridProps {
  orders: OrderSummary[];
  onOrderClick: (order: OrderSummary) => void;
}

/* ── Helpers ──────────────────────────────────────────────────────────────── */

/** Format an ISO date string as DD.MM.YYYY */
function formatDateGroup(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

/** Group orders by their created_at date (DD.MM.YYYY), preserving insertion order */
function groupByDate(
  orders: OrderSummary[],
): Map<string, OrderSummary[]> {
  const map = new Map<string, OrderSummary[]>();
  for (const order of orders) {
    const key = formatDateGroup(order.created_at);
    const list = map.get(key);
    if (list) {
      list.push(order);
    } else {
      map.set(key, [order]);
    }
  }
  return map;
}

/** Build a human-readable summary of order items, truncated to `maxLen` characters */
function itemsSummary(order: OrderSummary, maxLen = 60): string {
  const parts = order.items.map(
    (item) => `${item.name} ×${item.quantity}`,
  );
  const full = parts.join(', ');
  if (full.length <= maxLen) return full;
  return `${full.slice(0, maxLen - 1)}…`;
}

/** Return a Tailwind text + bg color class pair for a given confidence value */
function confidenceColor(c: number): { bar: string; text: string } {
  if (c >= 0.8) return { bar: 'bg-[#16A34A]', text: 'text-[#16A34A]' };
  if (c >= 0.6) return { bar: 'bg-[#D97706]', text: 'text-[#D97706]' };
  return { bar: 'bg-[#DC2626]', text: 'text-[#DC2626]' };
}

/* ── Component ────────────────────────────────────────────────────────────── */

export default function HistoryGrid({ orders, onOrderClick }: HistoryGridProps) {
  const grouped = useMemo(() => groupByDate(orders), [orders]);

  if (orders.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center py-20 text-[#6B7280]"
        role="status"
      >
        <p className="text-lg font-medium">No orders yet</p>
        <p className="mt-1 text-sm">
          Parsed orders will appear here once created.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6" role="list" aria-label="Order history">
      {Array.from(grouped.entries()).map(([date, dateOrders]) => (
        <section key={date} aria-label={`Orders from ${date}`}>
          {/* ── Date header ────────────────────────────────────────────── */}
          <h3 className="text-sm font-semibold text-[#6B7280] mb-2">
            {date}
          </h3>

          {/* ── Two-column grid ────────────────────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {dateOrders.map((order) => (
              <OrderCard
                key={order.id}
                order={order}
                onClick={() => onOrderClick(order)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/* ── OrderCard ────────────────────────────────────────────────────────────── */

interface OrderCardProps {
  order: OrderSummary;
  onClick: () => void;
}

function OrderCard({ order, onClick }: OrderCardProps) {
  const confidence = order.confidence ?? 0;
  const colors = confidenceColor(confidence);
  const shortId = order.id.slice(0, 8);

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        w-full text-left bg-white border border-[#E2E8F0] rounded-xl p-4
        cursor-pointer hover:shadow-md transition-shadow duration-150
        focus-visible:ring-2 focus-visible:ring-[#6366F1]
        ${order.for_review ? 'border-l-[3px] border-l-[#D97706]' : ''}
      `}
      aria-label={`Order ${shortId}${order.for_review ? ', flagged for review' : ''}`}
      role="listitem"
    >
      {/* ── Row 1: Items summary + review badge ───────────────────── */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-sm font-medium text-[#111827] leading-snug line-clamp-2">
          {itemsSummary(order)}
        </p>
        {order.for_review && (
          <span
            className="shrink-0 inline-flex items-center gap-1 rounded-full bg-[#FEF3C7] px-2 py-0.5 text-xs font-medium text-[#92400E]"
            aria-label="Flagged for review"
          >
            ⚠ Review
          </span>
        )}
      </div>

      {/* ── Row 2: File chip ──────────────────────────────────────── */}
      <p className="text-xs text-[#2563EB] mb-2 font-mono">
        🗎 order_{shortId}&nbsp;&nbsp;Format: JSON&nbsp;&nbsp;Items:{' '}
        {order.items.length}
      </p>

      {/* ── Row 3: Confidence mini bar + Total + Status ───────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Confidence mini bar */}
        <div className="flex items-center gap-1.5" aria-label={`Confidence ${Math.round(confidence * 100)}%`}>
          <div className="w-[60px] h-1.5 rounded-full bg-[#E2E8F0] overflow-hidden">
            <div
              className={`h-full rounded-full confidence-bar-fill ${colors.bar}`}
              style={{ width: `${Math.round(confidence * 100)}%` }}
            />
          </div>
          <span className={`text-xs font-medium ${colors.text}`}>
            {Math.round(confidence * 100)}%
          </span>
        </div>

        {/* Total */}
        {order.total_price != null && (
          <span className="text-sm font-semibold text-[#111827] ml-auto">
            ₹{order.total_price.toFixed(2)}
          </span>
        )}

        {/* Status badge */}
        <Badge
          variant={
            order.status === 'confirmed'
              ? 'success'
              : order.status === 'cancelled'
                ? 'error'
                : 'warning'
          }
        >
          {order.status}
        </Badge>
      </div>
    </button>
  );
}
