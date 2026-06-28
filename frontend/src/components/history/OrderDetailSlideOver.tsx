/* ── OrderDetailSlideOver — Detailed order slide-over panel ────────────────── */

import { useEffect, useRef, useCallback } from 'react';
import type { OrderSummary } from '@/lib/api';
import Badge from '@/components/ui/Badge';
import CopyButton from '@/components/ui/CopyButton';
import JsonViewer from '@/components/ui/JsonViewer';
import ConfidenceMeter from '@/components/parse/ConfidenceMeter';

/* ── Props ────────────────────────────────────────────────────────────────── */

interface OrderDetailSlideOverProps {
  order: OrderSummary | null;
  isOpen: boolean;
  onClose: () => void;
}

/* ── Helpers ──────────────────────────────────────────────────────────────── */

/** Format ISO string as a human-readable date + time */
function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }) +
    ' at ' +
    d.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
}

/* ── Component ────────────────────────────────────────────────────────────── */

export default function OrderDetailSlideOver({
  order,
  isOpen,
  onClose,
}: OrderDetailSlideOverProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  /* ── Close on Escape key ────────────────────────────────────────────────── */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!isOpen) return;
    document.addEventListener('keydown', handleKeyDown);
    // Prevent body scroll when panel is open
    document.body.style.overflow = 'hidden';
    // Focus the panel for accessibility
    panelRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen || !order) return null;


  return (
    /* ── Overlay ──────────────────────────────────────────────────────────── */
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Order details">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* ── Panel ─────────────────────────────────────────────────────────── */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className="slide-over-enter fixed right-0 top-0 bottom-0 w-[480px] max-w-full bg-white shadow-2xl z-50 flex flex-col outline-none"
      >
        {/* ── Header ───────────────────────────────────────────────────── */}
        <header className="sticky top-0 bg-white border-b border-[#E2E8F0] px-6 py-4 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-lg font-bold text-[#111827] font-sans">
              Order Details
            </h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs font-mono text-[#6B7280]">
                {order.id}
              </span>
              <CopyButton text={order.id} />
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#6B7280] hover:bg-[#F1F5F9] hover:text-[#111827] transition-colors"
            aria-label="Close order details"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        {/* ── Body ─────────────────────────────────────────────────────── */}
        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-6">
          {/* Status + Created */}
          <div className="flex items-center justify-between">
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
            <time
              dateTime={order.created_at}
              className="text-xs text-[#6B7280]"
            >
              {formatDateTime(order.created_at)}
            </time>
          </div>

          {/* Confidence */}
          <section aria-label="Confidence score">
            <h3 className="text-xs font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
              Confidence
            </h3>
            <ConfidenceMeter value={order.confidence ?? 0} forReview={order.for_review} />
          </section>

          {/* For review flag */}
          {order.for_review && (
            <div className="flex items-center gap-2 rounded-lg bg-[#FEF3C7] border border-[#FDE68A] px-3 py-2">
              <span className="text-base" aria-hidden="true">⚠</span>
              <p className="text-sm font-medium text-[#92400E]">
                This order is flagged for manual review
              </p>
            </div>
          )}

          {/* ── Items list ──────────────────────────────────────────── */}
          <section aria-label="Order items">
            <h3 className="text-xs font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
              Items ({order.items.length})
            </h3>
            <div className="space-y-2">
              {order.items.map((item, idx) => (
                <div
                  key={`${item.name}-${idx}`}
                  className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#111827]">
                        {item.name}
                      </p>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-[#6B7280]">
                        <span>Qty: {item.quantity}</span>
                        {item.size && <span>Size: {item.size}</span>}
                        {item.modifiers.length > 0 && (
                          <span>
                            Mods: {item.modifiers.join(', ')}
                          </span>
                        )}
                      </div>
                    </div>
                    {item.unit_price != null && (
                      <span className="shrink-0 text-sm font-semibold text-[#111827]">
                        ₹{item.unit_price.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Total price ────────────────────────────────────────── */}
          {order.total_price != null && (
            <div className="flex items-center justify-between rounded-lg bg-white border border-[#E2E8F0] px-4 py-3">
              <span className="text-sm font-medium text-[#6B7280]">
                Total
              </span>
              <span className="text-lg font-bold text-[#111827]">
                ₹{order.total_price.toFixed(2)}
              </span>
            </div>
          )}

          {/* ── Session ID ─────────────────────────────────────────── */}
          {order.session_id && (
            <section aria-label="Session information">
              <h3 className="text-xs font-semibold text-[#6B7280] uppercase tracking-wide mb-1">
                Session
              </h3>
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono text-[#6B7280] bg-[#F1F5F9] px-2 py-1 rounded">
                  {order.session_id}
                </code>
                <CopyButton text={order.session_id} />
              </div>
            </section>
          )}

          {/* ── JSON viewer ────────────────────────────────────────── */}
          <section aria-label="Raw order JSON">
            <h3 className="text-xs font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
              Raw JSON
            </h3>
            <JsonViewer data={order} />
          </section>
        </div>
      </div>
    </div>
  );
}
