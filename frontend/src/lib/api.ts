/* ── VoiceOrder NLP — Typed API Client ─────────────────────────────────────── */

const BASE =
  import.meta.env.VITE_API_URL ??
  'https://voiceorder-nlp-backend-production.up.railway.app';

/* ── Types ─────────────────────────────────────────────────────────────────── */

// Auth
export interface UserCreate {
  email: string;
  password: string;
}

export interface UserRead {
  id: string;
  email: string;
  created_at: string;
  is_active: boolean;
}

export interface TokenRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in_hours: number;
}

// NLP Entities
export interface RawEntity {
  text: string;
  label: 'FOOD' | 'SIZE' | 'MODIFIER' | 'CARDINAL';
  start: number;
  end: number;
}

// Order Items
export interface OrderItem {
  name: string;
  quantity: number;
  size: string | null;
  modifiers: string[];
  unit_price: number | null;
  matched_menu_item_id: string | null;
}

// Order Parse
export interface OrderParseRequest {
  text: string;
  menu_id?: string;
}

export interface OrderParseResponse {
  id: string;
  items: OrderItem[];
  confidence: number;
  for_review: boolean;
  raw_entities: RawEntity[];
  processing_time_ms: number;
}

// Order History
export interface OrderSummary {
  id: string;
  session_id: string | null;
  items: OrderItem[];
  total_price: number | null;
  status: 'pending' | 'confirmed' | 'cancelled';
  confidence: number | null;
  for_review: boolean;
  created_at: string;
}

export interface PaginatedOrders {
  items: OrderSummary[];
  page: number;
  size: number;
  total: number;
}

// Sessions
export interface SessionStartResponse {
  session_id: string;
  status: 'active';
  created_at: string;
  expires_at: string;
  message: string;
}

export interface MessageRequest {
  text: string;
}

export interface MessageResponse {
  updated_order: {
    items: OrderItem[];
    total_price: number;
  };
  turn: number;
  context_applied: boolean;
}

export interface SessionOrderResponse {
  session_id: string;
  turn: number;
  status: 'active' | 'closed';
  current_order: {
    items: OrderItem[];
    total_price: number;
  };
  last_food_entity: string | null;
}

// Monitoring
export interface HealthResponse {
  status: 'ok' | 'degraded';
  version: string;
  uptime_seconds: number;
  checks: {
    db: boolean;
    redis: boolean;
  };
  timestamp: string;
}

export interface MetricsResponse {
  orders_today: number;
  errors_today: number;
  for_review_today: number;
  avg_latency_ms: number;
  error_rate: number;
  uptime_seconds: number;
}

/* ── API Error ────────────────────────────────────────────────────────────── */

export class ApiError extends Error {
  status: number;
  detail: string;
  code?: string;

  constructor(status: number, detail: string, code?: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

/* ── Token helpers ────────────────────────────────────────────────────────── */

const TOKEN_KEY = 'voiceorder_jwt';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/* ── Fetch wrapper ────────────────────────────────────────────────────────── */

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true,
): Promise<{ data: T; processTime?: number }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (auth) {
    const token = getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  const processTime = res.headers.get('X-Process-Time')
    ? parseFloat(res.headers.get('X-Process-Time')!)
    : undefined;

  // 204 No Content — return empty
  if (res.status === 204) {
    return { data: undefined as unknown as T, processTime };
  }

  // 401 — clear token and redirect
  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    const body = await res.json().catch(() => ({ detail: 'Session expired' }));
    throw new ApiError(401, body.detail ?? 'Session expired', body.code);
  }

  // Other errors
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new ApiError(res.status, body.detail ?? 'Request failed', body.code);
  }

  const data = await res.json();
  return { data, processTime };
}

/* ── Auth ──────────────────────────────────────────────────────────────────── */

export async function register(email: string, password: string): Promise<UserRead> {
  const { data } = await request<UserRead>(
    '/auth/register',
    { method: 'POST', body: JSON.stringify({ email, password }) },
    false,
  );
  return data;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await request<TokenResponse>(
    '/auth/token',
    { method: 'POST', body: JSON.stringify({ email, password }) },
    false,
  );
  setToken(data.access_token);
  return data;
}

/* ── Orders ────────────────────────────────────────────────────────────────── */

export async function parseOrder(
  text: string,
  menuId?: string,
): Promise<{ result: OrderParseResponse; processTime?: number }> {
  const body: OrderParseRequest = { text };
  if (menuId) body.menu_id = menuId;
  const { data, processTime } = await request<OrderParseResponse>('/order/parse', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return { result: data, processTime };
}

export async function getOrderHistory(
  page = 1,
  size = 20,
): Promise<PaginatedOrders> {
  const { data } = await request<PaginatedOrders>(
    `/orders/history?page=${page}&size=${size}`,
  );
  return data;
}

/* ── Sessions ──────────────────────────────────────────────────────────────── */

export async function startSession(): Promise<SessionStartResponse> {
  const { data } = await request<SessionStartResponse>('/session/start', {
    method: 'POST',
  });
  return data;
}

export async function sendMessage(
  sessionId: string,
  text: string,
): Promise<MessageResponse> {
  const { data } = await request<MessageResponse>(
    `/session/${sessionId}/message`,
    { method: 'POST', body: JSON.stringify({ text }) },
  );
  return data;
}

export async function getSessionOrder(
  sessionId: string,
): Promise<SessionOrderResponse> {
  const { data } = await request<SessionOrderResponse>(
    `/session/${sessionId}/order`,
  );
  return data;
}

export async function closeSession(sessionId: string): Promise<void> {
  await request<void>(`/session/${sessionId}`, { method: 'DELETE' });
}

/* ── Monitoring ────────────────────────────────────────────────────────────── */

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await request<HealthResponse>('/health', {}, false);
  return data;
}

export async function getMetrics(): Promise<MetricsResponse> {
  const { data } = await request<MetricsResponse>('/metrics', {}, false);
  return data;
}
