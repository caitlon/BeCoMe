import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { User } from '@/types/api';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { isUnauthorized, ForbiddenError } from '@/lib/errors';
import { useToast } from '@/hooks/use-toast';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'serviceUnavailable';

interface AuthContextType {
  readonly user: User | null;
  readonly status: AuthStatus;
  readonly isLoading: boolean;
  readonly isAuthenticated: boolean;
  readonly isServiceUnavailable: boolean;
  readonly login: (email: string, password: string) => Promise<void>;
  readonly logout: () => Promise<void>;
  readonly refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { readonly children: React.ReactNode }) {
  const queryClient = useQueryClient();
  // AuthProvider mounts outside BrowserRouter (see App.tsx), so it cannot use
  // routing hooks, but useToast and useTranslation work fine here.
  const { toast } = useToast();
  const { t: tCommon } = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');

  const refreshUser = useCallback(async () => {
    try {
      setStatus('loading');
      // Probe the session via the HttpOnly cookie; isAuthProbe so an anonymous
      // visitor on a public page is not treated as a session failure.
      const userData = await api.getCurrentUser(true);
      setUser(userData);
      setStatus('authenticated');
    } catch (err) {
      if (isUnauthorized(err) || err instanceof ForbiddenError) {
        setUser(null);
        setStatus('unauthenticated');
      } else {
        // Network/server trouble, not "not logged in": keep the distinction so the
        // UI can offer a retry instead of bouncing an authenticated user to /login.
        setStatus('serviceUnavailable');
        logger.debug('Session probe unavailable', {
          error: err instanceof Error ? err.message : String(err),
        });
      }
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial auth load on mount
    refreshUser();
  }, [refreshUser]);

  // Bridges the ApiClient's session-expiry signal (fired after a silent refresh
  // fails on a non-probe request) into auth state and a user-visible toast.
  useEffect(() => {
    api.setOnSessionExpired(() => {
      setUser(null);
      setStatus('unauthenticated');
      toast({
        title: tCommon('errors.sessionExpiredTitle'),
        description: tCommon('errors.sessionExpired'),
        variant: 'destructive',
      });
    });
    return () => api.setOnSessionExpired(null);
  }, [toast, tCommon]);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    await refreshUser();
  }, [refreshUser]);

  const logout = useCallback(async () => {
    let logoutFailed = false;
    let logoutError: unknown;
    try {
      await api.logout();
    } catch (err) {
      // A server that refuses the sign-out is no reason to leave the user holding a
      // session they believe they closed. On a shared machine that is the worse
      // outcome of the two. Clear the local session below regardless, but keep the
      // failure and re-throw once it is clean: swallowing it entirely would make a
      // failed sign-out look identical to a real one, and the caller is what can
      // tell the user the server session may still be alive.
      logoutFailed = true;
      logoutError = err;
      logger.debug('Logout request failed; clearing the local session anyway', { error: err });
    }
    setUser(null);
    setStatus('unauthenticated');
    // Drop cached queries so the next account on this tab cannot see them.
    queryClient.clear();
    if (logoutFailed) {
      throw logoutError;
    }
  }, [queryClient]);

  const value = useMemo(() => ({
    user,
    status,
    isLoading: status === 'loading',
    isAuthenticated: status === 'authenticated',
    isServiceUnavailable: status === 'serviceUnavailable',
    login,
    logout,
    refreshUser,
  }), [user, status, login, logout, refreshUser]);

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
