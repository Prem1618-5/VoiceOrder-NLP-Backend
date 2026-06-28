import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getHealth,
  getMetrics,
  type HealthResponse,
  type MetricsResponse,
} from '@/lib/api';

interface UseMetricsReturn {
  health: HealthResponse | null;
  metrics: MetricsResponse | null;
  lastUpdated: Date | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Polls /health and /metrics every `intervalMs` (default 30s).
 * Stops polling when the component unmounts.
 */
export function useMetrics(intervalMs = 30_000): UseMetricsReturn {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [h, m] = await Promise.all([getHealth(), getMetrics()]);
      setHealth(h);
      setMetrics(m);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchData, intervalMs]);

  return { health, metrics, lastUpdated, isLoading, error, refresh: fetchData };
}
