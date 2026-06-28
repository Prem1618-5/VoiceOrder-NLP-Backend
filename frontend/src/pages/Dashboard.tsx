import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMetrics } from '@/hooks/useMetrics';
import { parseOrder, type OrderParseResponse } from '@/lib/api';
import GradientBar from '@/components/ui/GradientBar';
import EntityVisualization from '@/components/parse/EntityVisualization';
import ConfidenceMeter from '@/components/parse/ConfidenceMeter';

export default function Dashboard() {
  const navigate = useNavigate();
  const { metrics, health, isLoading: metricsLoading } = useMetrics();

  const [inputText, setInputText] = useState('');
  const [parseResult, setParseResult] = useState<OrderParseResponse | null>(null);
  const [originalText, setOriginalText] = useState('');
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  async function handleParse(e: FormEvent) {
    e.preventDefault();
    if (!inputText.trim()) return;
    setIsParsing(true);
    setParseError(null);
    setOriginalText(inputText);
    try {
      const { result } = await parseOrder(inputText);
      setParseResult(result);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Parse failed');
    } finally {
      setIsParsing(false);
    }
  }

  const featureCards = [
    {
      icon: '⚡',
      title: 'Single-Turn Parser',
      desc1: 'Parse one order instantly.',
      desc2: 'See NLP entities live.',
      path: '/parse',
    },
    {
      icon: '💬',
      title: 'Multi-Turn Session',
      desc1: 'Build order across turns.',
      desc2: 'Context-aware updates.',
      path: '/session',
    },
    {
      icon: '📋',
      title: 'Order History',
      desc1: 'Browse past parsed orders.',
      desc2: 'Paginated, filterable.',
      path: '/history',
    },
    {
      icon: '📊',
      title: 'Live Metrics',
      desc1: 'Orders, latency, error rate.',
      desc2: 'DB + Redis health.',
      path: '/',
    },
  ];

  const metricCards = [
    { label: 'Orders Today', value: metrics?.orders_today ?? '—' },
    {
      label: 'Avg Latency',
      value: metrics ? `${metrics.avg_latency_ms.toFixed(0)} ms` : '—',
    },
    { label: 'For Review', value: metrics?.for_review_today ?? '—' },
    {
      label: 'Error Rate',
      value: metrics ? `${(metrics.error_rate * 100).toFixed(1)}%` : '—',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Hero + Metrics Row */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_42%] gap-6">
        {/* Hero Section */}
        <div className="space-y-4">
          <div>
            <h2 className="text-[32px] font-bold text-[#111827] leading-tight">
              Parse speech into structured orders.
            </h2>
            <p className="text-sm text-[#6B7280] mt-1">
              Powered by spaCy NLP · Multi-turn sessions
            </p>
          </div>

          <form onSubmit={handleParse}>
            <div className="bg-white rounded-xl shadow-sm border border-[#E2E8F0] overflow-hidden">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="I want 2 large pepperoni pizzas with extra cheese..."
                rows={3}
                maxLength={500}
                className="w-full px-4 py-3 text-sm text-[#111827] placeholder:text-[#6B7280]
                           resize-none focus:outline-none"
              />
            </div>
            <GradientBar height={4} className="mt-0" />
            <div className="flex justify-end mt-3">
              <button
                type="submit"
                disabled={isParsing || !inputText.trim()}
                className="bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-lg px-6 py-2.5
                           font-medium text-sm transition-colors disabled:opacity-50
                           disabled:cursor-not-allowed"
              >
                {isParsing ? 'Parsing...' : 'Parse →'}
              </button>
            </div>
          </form>

          {/* Inline parse result */}
          {parseError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {parseError}
            </div>
          )}
          {parseResult && (
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm space-y-4">
              <EntityVisualization
                originalText={originalText}
                rawEntities={parseResult.raw_entities}
              />
              <ConfidenceMeter
                value={parseResult.confidence}
                forReview={parseResult.for_review}
              />
              {parseResult.items.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-2">
                    Parsed Items
                  </h4>
                  {parseResult.items.map((item, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between py-1.5 text-sm"
                    >
                      <span className="text-[#111827] font-medium">
                        {item.name} ×{item.quantity}
                        {item.size && (
                          <span className="text-[#6B7280] font-normal ml-2">
                            {item.size}
                          </span>
                        )}
                      </span>
                      {item.unit_price != null && (
                        <span className="text-[#6B7280]">
                          ₹{(item.unit_price * item.quantity).toFixed(2)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Live Metrics Strip */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider">
            Live Metrics
          </h3>
          <div className="grid grid-cols-2 gap-3">
            {metricCards.map((card) => (
              <div
                key={card.label}
                className={`bg-white border border-[#E2E8F0] rounded-xl p-4 ${
                  !metricsLoading ? 'metric-refresh' : ''
                }`}
              >
                <p className="text-xs text-[#6B7280] mb-1">{card.label}</p>
                <p className="text-2xl font-bold text-[#111827]">
                  {metricsLoading ? (
                    <span className="skeleton inline-block w-16 h-7" />
                  ) : (
                    card.value
                  )}
                </p>
              </div>
            ))}
          </div>

          {/* Health status */}
          {health && (
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4">
              <p className="text-xs text-[#6B7280] mb-2">System Health</p>
              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1.5">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      health.checks.db ? 'bg-[#16A34A]' : 'bg-[#DC2626]'
                    }`}
                  />
                  Database
                </span>
                <span className="flex items-center gap-1.5">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      health.checks.redis ? 'bg-[#16A34A]' : 'bg-[#DC2626]'
                    }`}
                  />
                  Redis
                </span>
                <span className="text-[#6B7280] ml-auto text-xs">
                  v{health.version}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Feature Cards Grid (2×2) */}
      <div>
        <h3 className="text-sm font-semibold text-[#6B7280] uppercase tracking-wider mb-3">
          Features
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {featureCards.map((card) => (
            <button
              key={card.title}
              onClick={() => navigate(card.path)}
              className="bg-white border border-[#E2E8F0] rounded-xl p-5 text-left
                         hover:shadow-md hover:border-l-[3px] hover:border-l-[#6366F1]
                         transition-all duration-150 group"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">{card.icon}</span>
                <h4 className="font-semibold text-[#111827] group-hover:text-[#6366F1] transition-colors">
                  {card.title}
                </h4>
              </div>
              <p className="text-sm text-[#6B7280]">{card.desc1}</p>
              <p className="text-sm text-[#6B7280]">{card.desc2}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Bottom Search Bar */}
      <div className="sticky bottom-0 bg-[#F8FAFC] pt-2 pb-4">
        <GradientBar height={3} className="mb-2" />
        <div className="flex items-center bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-sm">
          <input
            type="text"
            placeholder="Enter your order text or search history..."
            className="flex-1 px-4 py-3 text-sm text-[#111827] placeholder:text-[#6B7280]
                       focus:outline-none"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const val = (e.target as HTMLInputElement).value.trim();
                if (val) {
                  setInputText(val);
                  (e.target as HTMLInputElement).value = '';
                }
              }
            }}
          />
          <button className="px-4 py-3 text-[#6366F1] hover:bg-[#F8FAFC] transition-colors">
            →
          </button>
        </div>
      </div>
    </div>
  );
}
