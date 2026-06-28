import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getOrderHistory, type OrderSummary, type PaginatedOrders } from '@/lib/api';
import HistoryGrid from '@/components/history/HistoryGrid';
import OrderDetailSlideOver from '@/components/history/OrderDetailSlideOver';

export default function History() {
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedOrders | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedOrder, setSelectedOrder] = useState<OrderSummary | null>(null);
  const [slideOverOpen, setSlideOverOpen] = useState(false);

  const fetchOrders = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await getOrderHistory(page, pageSize);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  function handleOrderClick(order: OrderSummary) {
    setSelectedOrder(order);
    setSlideOverOpen(true);
  }

  const totalPages = data ? Math.ceil(data.total / data.size) : 0;

  // Filter orders by search query (client-side)
  const filteredOrders = data?.items.filter((order) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const itemNames = order.items.map((item) => item.name?.toLowerCase() ?? '').join(' ');
    return itemNames.includes(q) || order.id.toLowerCase().includes(q);
  }) ?? [];

  return (
    <div className="space-y-4">
      {/* Top controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 justify-between">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by item or order ID"
              className="form-input pr-10"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280]">
              🔍
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-sm text-[#6B7280]">
            {data ? `${data.total} orders` : '—'}
          </span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            className="form-input w-auto py-1.5"
          >
            <option value={10}>Show: 10</option>
            <option value={20}>Show: 20</option>
            <option value={50}>Show: 50</option>
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && filteredOrders.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="text-5xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-[#111827] mb-2">
            No orders yet
          </h3>
          <p className="text-sm text-[#6B7280] mb-6">
            Parse your first order to see history
          </p>
          <button
            onClick={() => navigate('/parse')}
            className="btn-primary px-6 py-2.5"
          >
            Go to Parser →
          </button>
        </div>
      )}

      {/* Grid */}
      {!isLoading && filteredOrders.length > 0 && (
        <HistoryGrid orders={filteredOrders} onOrderClick={handleOrderClick} />
      )}

      {/* Pagination */}
      {!isLoading && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="btn-ghost !py-1.5"
          >
            ← Prev
          </button>

          {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
            const pageNum = i + 1;
            return (
              <button
                key={pageNum}
                onClick={() => setPage(pageNum)}
                className={
                  page === pageNum
                    ? 'btn-primary !px-3 !py-1.5'
                    : 'btn-ghost !px-3 !py-1.5'
                }
              >
                {pageNum}
              </button>
            );
          })}

          {totalPages > 5 && (
            <span className="text-sm text-[#6B7280]">...</span>
          )}

          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="btn-ghost !py-1.5"
          >
            Next →
          </button>
        </div>
      )}

      {/* Slide-over detail panel */}
      <OrderDetailSlideOver
        order={selectedOrder}
        isOpen={slideOverOpen}
        onClose={() => {
          setSlideOverOpen(false);
          setSelectedOrder(null);
        }}
      />
    </div>
  );
}
