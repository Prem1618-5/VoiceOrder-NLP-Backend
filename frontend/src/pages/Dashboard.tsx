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
      const { result: data } = await parseOrder(inputText);
      setParseResult(data);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Parse failed');
    } finally {
      setIsParsing(false);
    }
  }

  const featureCards = [
    { icon: '⚡', title: 'Parse Order', desc: 'NLP entity extraction with live visualization.', path: '/parse' },
    { icon: '💬', title: 'Session Chat', desc: 'Multi-turn ordering with context.', path: '/session' },
    { icon: '📋', title: 'History', desc: 'Browse all past parsed orders.', path: '/history' },
  ];

  const metricCards = [
    { label: 'Orders Today', value: metrics?.orders_today ?? '—' },
    { label: 'Avg Latency', value: metrics ? `${metrics.avg_latency_ms.toFixed(0)} ms` : '—' },
    { label: 'For Review', value: metrics?.for_review_today ?? '—' },
    { label: 'Error Rate', value: metrics ? `${(metrics.error_rate * 100).toFixed(1)}%` : '—' },
  ];

  return (
    <div className="space-y-6">

      {/* ── Hero parse strip ──────────────────────────────────────────────── */}
      <div className="glass-card p-6">
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-[#111827]">Parse speech into structured orders</h1>
          <p className="text-sm text-[#6B7280] mt-1">Powered by spaCy NLP · Multi-turn sessions · Live entity visualization</p>
        </div>

        <form onSubmit={handleParse} className="space-y-3">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder='Try: "I want 2 large pepperoni pizzas, three cans of Diet Coke, and one order of garlic bread with extra cheese"'
            rows={3}
            maxLength={500}
            className="form-input resize-none"
          />
          <GradientBar height={3} />
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#9CA3AF]">{inputText.length}/500</span>
            <button type="submit" disabled={isParsing || !inputText.trim()} className="btn-primary">
              {isParsing ? 'Parsing…' : 'Parse →'}
            </button>
          </div>
        </form>

        {parseError && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            {parseError}
          </div>
        )}

        {parseResult && (
          <div className="mt-5 space-y-4 border-t border-[rgba(99,102,241,0.08)] pt-5">
            <EntityVisualization originalText={originalText} rawEntities={parseResult.raw_entities} />
            <ConfidenceMeter value={parseResult.confidence} forReview={parseResult.for_review} />
            {parseResult.items.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">Parsed Items</p>
                {parseResult.items.map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 text-sm border-b border-[rgba(99,102,241,0.06)] last:border-0">
                    <span className="text-[#111827] font-medium">
                      {item.name} ×{item.quantity}
                      {item.size && <span className="text-[#6B7280] font-normal ml-1.5">({item.size})</span>}
                    </span>
                    {item.unit_price != null && (
                      <span className="text-[#6B7280] font-mono">₹{(item.unit_price * item.quantity).toFixed(2)}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Metrics + feature cards row ──────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">

        {/* Feature navigation cards */}
        <div className="space-y-3">
          <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">Features</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {featureCards.map((card) => (
              <button
                key={card.title}
                onClick={() => navigate(card.path)}
                className="glass-card p-5 text-left hover:shadow-[var(--shadow-card-hover)]
                           transition-all duration-200 group hover:-translate-y-0.5"
              >
                <div className="text-2xl mb-2">{card.icon}</div>
                <h3 className="text-sm font-semibold text-[#111827] group-hover:text-[#6366F1] transition-colors">
                  {card.title}
                </h3>
                <p className="text-xs text-[#6B7280] mt-0.5">{card.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Live metrics column */}
        <div className="space-y-3">
          <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">Live Metrics</p>
          <div className="grid grid-cols-2 gap-2">
            {metricCards.map((card) => (
              <div key={card.label} className="glass-card p-4">
                <p className="text-[11px] text-[#9CA3AF] mb-1">{card.label}</p>
                {metricsLoading ? (
                  <div className="skeleton h-7 w-16" />
                ) : (
                  <p className="text-xl font-bold text-[#111827]">{card.value}</p>
                )}
              </div>
            ))}
          </div>

          {health && (
            <div className="glass-card p-4">
              <p className="text-[11px] text-[#9CA3AF] mb-2 uppercase tracking-wider">System</p>
              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1.5 text-[#374151]">
                  <span className={`w-2 h-2 rounded-full ${health.checks.db ? 'bg-[#16A34A]' : 'bg-[#DC2626]'}`} />
                  Database
                </span>
                <span className="flex items-center gap-1.5 text-[#374151]">
                  <span className={`w-2 h-2 rounded-full ${health.checks.redis ? 'bg-[#16A34A]' : 'bg-[#DC2626]'}`} />
                  Redis
                </span>
                <span className="text-[#9CA3AF] text-xs ml-auto">v{health.version}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
