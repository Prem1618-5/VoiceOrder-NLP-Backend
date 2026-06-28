/* ── OrderAccumulator — Live order panel (right side) ───────────────────── */

import type { OrderItem } from '@/lib/api';

interface OrderAccumulatorProps {
  items: OrderItem[];
  totalPrice: number;
}

function EmptyOrder() {
  return (
    <div className="flex items-center justify-center py-12">
      <p className="text-sm text-[#6B7280]">No items yet</p>
    </div>
  );
}

export default function OrderAccumulator({
  items,
  totalPrice,
}: OrderAccumulatorProps) {
  const subtotal = items.reduce(
    (sum, item) => sum + (item.unit_price ?? 0) * item.quantity,
    0,
  );
  const tax = subtotal * 0.05;
  const total = totalPrice > 0 ? totalPrice : subtotal + tax;

  return (
    <div
      className="bg-white border border-[#E2E8F0] rounded-xl p-5"
      role="region"
      aria-label="Your order"
    >
      {/* Header */}
      <h2 className="uppercase tracking-wider text-xs font-semibold text-[#6B7280]">
        Your Order
      </h2>

      <div className="border-b border-[#E2E8F0] my-3" role="separator" />

      {/* Items list */}
      {items.length === 0 ? (
        <EmptyOrder />
      ) : (
        <ul className="space-y-3" aria-label="Order items">
          {items.map((item, idx) => (
            <li
              key={`${item.name}-${idx}`}
              className="order-item-enter flex items-start justify-between gap-3"
            >
              {/* Left: item details */}
              <div className="min-w-0 flex-1">
                <p className="font-medium text-[#111827]">
                  {item.name}
                  <span className="ml-1 text-[#6B7280]">×{item.quantity}</span>
                </p>

                {item.size && (
                  <p className="text-sm text-[#6B7280]">{item.size}</p>
                )}

                {item.modifiers.length > 0 && (
                  <p className="text-sm text-[#6B7280]">
                    {item.modifiers.join(' · ')}
                  </p>
                )}
              </div>

              {/* Right: unit price */}
              {item.unit_price != null && (
                <span className="text-sm text-[#6B7280] shrink-0 tabular-nums">
                  ₹{item.unit_price.toFixed(2)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Totals section */}
      {items.length > 0 && (
        <>
          <div className="border-b border-[#E2E8F0] my-3" role="separator" />

          <div className="space-y-1.5">
            {/* Subtotal */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#6B7280]">Subtotal</span>
              <span className="tabular-nums">₹{subtotal.toFixed(2)}</span>
            </div>

            {/* Tax */}
            <div className="flex items-center justify-between text-sm text-[#6B7280]">
              <span>Tax (5%)</span>
              <span className="tabular-nums">₹{tax.toFixed(2)}</span>
            </div>

            {/* Total */}
            <div className="flex items-center justify-between text-base font-bold text-[#111827] pt-1">
              <span>Total</span>
              <span className="tabular-nums">₹{total.toFixed(2)}</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
