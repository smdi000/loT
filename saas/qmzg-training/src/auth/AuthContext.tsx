import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getMe, login as requestLogin } from '../api/services';
import { User } from '../api/types';
import { clearAccessToken, getAccessToken, setAccessToken } from './session';

interface AuthValue {
  user: User | null;
  loading: boolean;
  login(email: string, password: string): Promise<void>;
  logout(): void;
}

const AuthContext = createContext<AuthValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(getAccessToken()));

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    const onExpired = () => logout();
    window.addEventListener('qmzg:auth-expired', onExpired);
    return () => window.removeEventListener('qmzg:auth-expired', onExpired);
  }, [logout]);

  useEffect(() => {
    if (!getAccessToken()) return;
    getMe().then(setUser).catch(logout).finally(() => setLoading(false));
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await requestLogin(email, password);
    setAccessToken(result.access_token);
    try {
      setUser(await getMe());
    } catch (error) {
      clearAccessToken();
      throw error;
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used within AuthProvider');
  return value;
}
