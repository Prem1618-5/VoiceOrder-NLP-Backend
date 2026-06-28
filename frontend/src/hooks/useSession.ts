import { useCallback, useState } from 'react';
import {
  startSession as apiStart,
  sendMessage as apiSend,
  getSessionOrder as apiGetOrder,
  closeSession as apiClose,
  type SessionStartResponse,
  type MessageResponse,
  type SessionOrderResponse,
  type OrderItem,
} from '@/lib/api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'system';
  text: string;
  turn?: number;
  contextApplied?: boolean;
  items?: OrderItem[];
  timestamp: Date;
}

interface UseSessionReturn {
  sessionId: string | null;
  status: 'idle' | 'active' | 'closed';
  turn: number;
  expiresAt: Date | null;
  messages: ChatMessage[];
  currentOrder: { items: OrderItem[]; total_price: number } | null;
  isLoading: boolean;
  error: string | null;
  start: () => Promise<SessionStartResponse>;
  send: (text: string) => Promise<MessageResponse>;
  refreshOrder: () => Promise<SessionOrderResponse>;
  close: () => Promise<void>;
  reset: () => void;
}

let messageIdCounter = 0;
function nextMsgId() {
  return `msg-${++messageIdCounter}-${Date.now()}`;
}

export function useSession(): UseSessionReturn {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'active' | 'closed'>('idle');
  const [turn, setTurn] = useState(0);
  const [expiresAt, setExpiresAt] = useState<Date | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentOrder, setCurrentOrder] = useState<{
    items: OrderItem[];
    total_price: number;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiStart();
      setSessionId(res.session_id);
      setStatus('active');
      setTurn(0);
      setExpiresAt(new Date(res.expires_at));
      setMessages([]);
      setCurrentOrder(null);
      return res;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start session';
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!sessionId) throw new Error('No active session');
      setIsLoading(true);
      setError(null);

      // Add user message immediately
      const userMsg: ChatMessage = {
        id: nextMsgId(),
        role: 'user',
        text,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const res = await apiSend(sessionId, text);
        setTurn(res.turn);
        setCurrentOrder(res.updated_order);

        // Add system response
        const sysMsg: ChatMessage = {
          id: nextMsgId(),
          role: 'system',
          text: res.context_applied
            ? '↻ Updated order based on context'
            : '✓ Added to order',
          turn: res.turn,
          contextApplied: res.context_applied,
          items: res.updated_order.items,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, sysMsg]);
        return res;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to send message';
        setError(msg);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId],
  );

  const refreshOrder = useCallback(async () => {
    if (!sessionId) throw new Error('No active session');
    const res = await apiGetOrder(sessionId);
    setCurrentOrder(res.current_order);
    setTurn(res.turn);
    return res;
  }, [sessionId]);

  const close = useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      await apiClose(sessionId);
      setStatus('closed');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to close session';
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const reset = useCallback(() => {
    setSessionId(null);
    setStatus('idle');
    setTurn(0);
    setExpiresAt(null);
    setMessages([]);
    setCurrentOrder(null);
    setError(null);
  }, []);

  return {
    sessionId,
    status,
    turn,
    expiresAt,
    messages,
    currentOrder,
    isLoading,
    error,
    start,
    send,
    refreshOrder,
    close,
    reset,
  };
}
