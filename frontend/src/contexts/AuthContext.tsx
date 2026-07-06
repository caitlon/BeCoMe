import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { User } from '@/types/api';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';

interface AuthContextType {
  readonly user: User | null;
  readonly isLoading: boolean;
  readonly isAuthenticated: boolean;
  readonly login: (email: string, password: string) => Promise<void>;
  readonly register: (email: string, password: string, firstName: string, lastName?: string) => Promise<void>;
  readonly logout: () => Promise<void>;
  readonly refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { readonly children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      // Probe the session via the HttpOnly cookie; silent so an anonymous visitor is
      // not redirected away from a public page.
      const userData = await api.getCurrentUser(true);
      setUser(userData);
    } catch (err) {
      logger.debug('No active session', {
        error: err instanceof Error ? err.message : String(err),
      });
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial auth load on mount
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    await refreshUser();
  }, [refreshUser]);

  const register = useCallback(async (email: string, password: string, firstName: string, lastName?: string) => {
    await api.register({
      email,
      password,
      first_name: firstName,
      last_name: lastName,
    });
    await api.login(email, password);
    await refreshUser();
  }, [refreshUser]);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
    // Drop cached queries so the next account on this tab cannot see them.
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo(() => ({
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    refreshUser,
  }), [user, isLoading, login, register, logout, refreshUser]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
