import type { OrderParseResponse } from '@/lib/api';
import EntityVisualization from '@/components/parse/EntityVisualization';
import ConfidenceMeter from '@/components/parse/ConfidenceMeter';
import JsonViewer from '@/components/ui/JsonViewer';
import CopyButton from '@/components/ui/CopyButton';
import Badge from '@/components/ui/Badge';

/* ── Props ─────────────────────────────────────────────────────────────────── */

interface ParseResultProps {
  result: OrderParseResponse | null;
  originalText: string;
  isLoading: boolean;
  processTime?: number;
}

/* ── Helpers ───────────────────────────────────────────────────────────────── */

/** Shared card wrapper — glass card style. */
function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`glass-card p-5 ${className}`}>
      {children}
    </div>
  );
}

/** Format price in ₹. */
function formatPrice(price: number): string {
  return `₹${price.toFixed(2)}`;
}

/** Truncate long IDs for display. */
function truncateId(id: string, len = 12): string {
  if (id.length <= len) return id;
  return `${id.slice(0, len)}…`;
}

/* ── Idle state ────────────────────────────────────────────────────────────── */

function IdlePlaceholder() {
  return (
    <Card className="flex flex-col items-center justify-center min-h-[280px] text-center gap-4">
      {/* Icon */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        className="w-10 h-10 text-[#6B7280]/40"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Zm3.75 11.625a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
        />
      </svg>

      <p className="text-sm text-[#6B7280]">Parse an order to see results</p>

      {/* Entity legend */}
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Badge variant="food">FOOD</Badge>
        <Badge variant="size">SIZE</Badge>
        <Badge variant="modifier">MODIFIER</Badge>
        <Badge variant="cardinal">CARDINAL</Badge>
      </div>
    </Card>
  );
}

/* ── Loading state ─────────────────────────────────────────────────────────── */

function LoadingSkeleton() {
  return (
    <Card className="flex flex-col gap-4">
      {/* Animated parsing indicator */}
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[#6366F1] status-pulse-fast" />
        <span className="text-sm text-[#6B7280] font-medium">Parsing…</span>
      </div>

      {/* Skeleton shimmers */}
      <div className="skeleton h-8 w-full" />
      <div className="skeleton h-5 w-3/4" />
      <div className="skeleton h-5 w-1/2" />
    </Card>
  );
}

/* ── Success state ─────────────────────────────────────────────────────────── */

function SuccessResult({
  result,
  originalText,
  processTime,
}: {
  result: OrderParseResponse;
  originalText: string;
  processTime?: number;
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* ── Entity Visualization ──────────────────────────────────────── */}
      <Card>
        <EntityVisualization
          originalText={originalText}
          rawEntities={result.raw_entities}
        />
      </Card>

      {/* ── Confidence Meter ──────────────────────────────────────────── */}
      <Card>
        <ConfidenceMeter
          value={result.confidence}
          forReview={result.for_review}
        />
      </Card>

      {/* ── Flagged for Review warning ────────────────────────────────── */}
      {result.for_review && (
        <Card className="border-l-4 border-l-[#D97706] bg-amber-50/50">
          <div className="flex items-start gap-2">
            <span className="text-lg leading-none" aria-hidden="true">
              ⚠
            </span>
            <div>
              <p className="text-sm font-semibold text-[#92400E]">
                Flagged for Review
              </p>
              <p className="text-xs text-[#92400E]/80 mt-0.5">
                This parse has low confidence and may require manual verification.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* ── Parsed Items ──────────────────────────────────────────────── */}
      <Card>
        <h3 className="text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-3">
          PARSED ITEMS
        </h3>

        {result.items.length === 0 ? (
          <p className="text-sm text-[#6B7280] italic">No items parsed.</p>
        ) : (
          <ul className="divide-y divide-[#E2E8F0]" role="list">
            {result.items.map((item, idx) => (
              <li
                key={`${item.name}-${idx}`}
                className="order-item-enter py-3 first:pt-0 last:pb-0"
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                <div className="flex items-start justify-between gap-3">
                  {/* Left: name × quantity */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[#111827]">
                      {item.name}
                      <span className="text-[#6366F1] ml-1">
                        ×{item.quantity}
                      </span>
                    </p>

                    {/* Size */}
                    {item.size && (
                      <p className="text-xs text-[#6B7280] mt-0.5">
                        Size:{' '}
                        <span className="font-medium text-[#92400E]">
                          {item.size}
                        </span>
                      </p>
                    )}

                    {/* Modifiers */}
                    {item.modifiers.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {item.modifiers.map((mod) => (
                          <Badge key={mod} variant="modifier">
                            {mod}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Right: unit price */}
                  {item.unit_price != null && (
                    <span className="text-sm font-mono font-semibold text-[#111827] whitespace-nowrap">
                      {formatPrice(item.unit_price)}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── Order ID ──────────────────────────────────────────────────── */}
      <Card>
        <h3 className="text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-2">
          ORDER ID
        </h3>
        <div className="flex items-center gap-2">
          <code className="text-sm font-mono text-[#111827] bg-gray-50 px-2 py-1 rounded">
            {truncateId(result.id)}
          </code>
          <CopyButton text={result.id} />
        </div>
      </Card>

      {/* ── Raw JSON ──────────────────────────────────────────────────── */}
      <Card>
        <h3 className="text-xs font-semibold text-[#6B7280] tracking-wider uppercase mb-3">
          RAW JSON
        </h3>
        <JsonViewer data={result} />
      </Card>

      {/* ── Process time ──────────────────────────────────────────────── */}
      {processTime != null && (
        <p className="text-xs text-[#6B7280] text-right font-mono tabular-nums">
          Processed in {Math.round(processTime)}ms
        </p>
      )}
    </div>
  );
}

/* ── Main component ────────────────────────────────────────────────────────── */

export default function ParseResult({
  result,
  originalText,
  isLoading,
  processTime,
}: ParseResultProps) {
  // Loading state
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // Idle state
  if (!result) {
    return <IdlePlaceholder />;
  }

  // Success state
  return (
    <SuccessResult
      result={result}
      originalText={originalText}
      processTime={processTime}
    />
  );
}
