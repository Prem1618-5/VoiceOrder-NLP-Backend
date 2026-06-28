import { createContext, useCallback, useEffect, useState, type ReactNode } from 'react';
import {
  login as apiLogin,
  register as apiRegister,
  getToken,
  clearToken,
  type TokenResponse,
  type UserRead,
} from '@/lib/api';

/* ── Types ─────────────────────────────────────────────────────────────────── */

export interface AuthUser {
  email: string;
  token: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<TokenResponse>;
  register: (email: string, password: string) => Promise<UserRead>;
  logout: () => void;
}

/* ── Context ───────────────────────────────────────────────────────────────── */

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => { throw new Error('AuthContext not initialised'); },
  register: async () => { throw new Error('AuthContext not initialised'); },
  logout: () => {},
});

/* ── Helper: decode JWT to extract email from payload ──────────────────────── */

function decodeJwtPayload(token: string): { sub: string; email?: string } | null {
  try {
    const payload = token.split('.')[1];
    const decoded = JSON.parse(atob(payload));
    return decoded;
  } catch {
    return null;
  }
}

/* ── Provider ──────────────────────────────────────────────────────────────── */

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore from localStorage on mount
  useEffect(() => {
    const token = getToken();
    if (token) {
      const payload = decodeJwtPayload(token);
      if (payload) {
        setUser({
          email: payload.email ?? payload.sub,
          token,
        });
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password);
    setUser({ email, token: response.access_token });
    return response;
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const response = await apiRegister(email, password);
    return response;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
