import React, {
  createContext,
  startTransition,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { User } from '@/types/api';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { openAuthBroadcast, type AuthBroadcast } from '@/lib/auth-broadcast';
import { isUnauthorized, ForbiddenError } from '@/lib/errors';
import { useToast } from '@/hooks/use-toast';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'serviceUnavailable';

interface AuthContextType {
  readonly user: User | null;
  readonly status: AuthStatus;
  readonly isLoading: boolean;
  readonly isAuthenticated: boolean;
  readonly isServiceUnavailable: boolean;
  readonly login: (
    email: string,
    password: string,
    turnstileToken?: string | null
  ) => Promise<void>;
  readonly logout: () => Promise<void>;
  readonly refreshUser: () => Promise<void>;
  /**
   * Replaces the signed-in user with a fresh copy the caller already holds (the
   * response of a write), without refreshUser's status flip to 'loading', which
   * makes ProtectedRoute swap the whole page for a loader and remount it.
   */
  readonly setCurrentUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const signOutListeners = new Set<() => void>();

/**
 * Subscribes to every transition into the unauthenticated state: an explicit
 * sign-out, an expired session, and a session probe refused with 401/403. Lets
 * a feature that holds per-user state outside this context drop it without
 * this file knowing the feature exists. Returns the unsubscribe function.
 */
export function registerSignOutListener(listener: () => void): () => void {
  signOutListeners.add(listener);
  return () => {
    signOutListeners.delete(listener);
  };
}

// A throwing listener must not keep the rest from running, nor the caller from
// finishing its sign-out.
function notifySignOutListeners() {
  signOutListeners.forEach((listener) => {
    try {
      listener();
    } catch (err) {
      logger.error('Sign-out listener failed', {
        error: err instanceof Error ? err.message : String(err),
      });
    }
  });
}

export function AuthProvider({ children }: { readonly children: React.ReactNode }) {
  const queryClient = useQueryClient();
  // AuthProvider mounts outside BrowserRouter (see App.tsx), so it cannot use
  // routing hooks, but useToast and useTranslation work fine here.
  const { toast } = useToast();
  const { t: tCommon } = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  // The channel to the other tabs, open while this provider is mounted, and the user this tab
  // holds, which a probe refused with 401/403 reads to tell a real sign-out from an anonymous
  // visitor's first probe. The ref changes in the same call as the state, so a reader that
  // runs between a change and the next render sees the user the tab holds now.
  const channelRef = useRef<AuthBroadcast | null>(null);
  const userRef = useRef<User | null>(null);
  // Counts the events that decide who is signed in: every probe, a received sign-out, an
  // expired session, a logout and a login. A probe that finds the count moved on when its
  // request settles is stale and applies nothing, so an old answer never undoes a newer one.
  const epochRef = useRef(0);
  // Probes whose request has not settled yet, stale ones included: a login that invalidates
  // one must settle the tab itself, because the probe's own answer will be discarded.
  const probesInFlightRef = useRef(0);
  const updateUser = useCallback((next: User | null) => {
    userRef.current = next;
    setUser(next);
  }, []);

  // announceSignOut is false for a probe another tab asked for: that tab already knows, and a
  // tab never answers a message by posting one.
  const probeSession = useCallback(async (announceSignOut: boolean) => {
    const epoch = ++epochRef.current;
    // Read before the request: by the time it settles the user may be another event's.
    const hadUser = userRef.current !== null;
    probesInFlightRef.current += 1;
    try {
      setStatus('loading');
      // Probe the session via the HttpOnly cookie; isAuthProbe so an anonymous
      // visitor on a public page is not treated as a session failure.
      const userData = await api.getCurrentUser(true);
      if (epoch !== epochRef.current) {
        return;
      }
      // Query keys are not scoped to a user, so another account's cached data must go
      // before this tab shows the new one. The same user keeps the cache.
      const held = userRef.current;
      if (held !== null && held.id !== userData.id) {
        queryClient.clear();
      }
      // The probe settles at an arbitrary moment, possibly while a prerendered page
      // is still hydrating. A transition keeps React from answering a plain update
      // by discarding the server HTML of a boundary that has not hydrated yet.
      startTransition(() => {
        updateUser(userData);
        setStatus('authenticated');
      });
    } catch (err) {
      if (epoch !== epochRef.current) {
        return;
      }
      if (isUnauthorized(err) || err instanceof ForbiddenError) {
        startTransition(() => {
          updateUser(null);
          setStatus('unauthenticated');
        });
        // The next sign-in in this tab may be another account's: nothing of this one stays.
        if (hadUser) {
          queryClient.clear();
        }
        notifySignOutListeners();
        // An anonymous tab's probe changes nothing for the other tabs, and posting it could
        // sign out a tab that has just signed in.
        if (announceSignOut && hadUser) {
          channelRef.current?.post('signed-out');
        }
      } else {
        // Network/server trouble, not "not logged in": keep the distinction so the
        // UI can offer a retry instead of bouncing an authenticated user to /login.
        startTransition(() => setStatus('serviceUnavailable'));
        logger.debug('Session probe unavailable', {
          error: err instanceof Error ? err.message : String(err),
        });
      }
    } finally {
      probesInFlightRef.current -= 1;
    }
  }, [queryClient, updateUser]);

  const refreshUser = useCallback(() => probeSession(true), [probeSession]);

  // A sign-out in another tab ends this session too, with no request: the server session is
  // already gone, and a tab that still showed the account would keep its cached queries and
  // the assistant's conversation. A sign-in in another tab replaces the session cookie, so
  // this tab re-reads it; the assistant's user-switch reset then drops another user's history.
  useEffect(() => {
    const channel = openAuthBroadcast((type) => {
      if (type === 'signed-out') {
        epochRef.current += 1;
        // A transition, like the probe's: this can arrive while a lazy page hydrates.
        startTransition(() => {
          updateUser(null);
          setStatus('unauthenticated');
        });
        queryClient.clear();
        notifySignOutListeners();
      } else {
        void probeSession(false);
      }
    });
    channelRef.current = channel;
    return () => {
      channel.close();
      channelRef.current = null;
    };
  }, [queryClient, probeSession, updateUser]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial auth load on mount
    refreshUser();
  }, [refreshUser]);

  // Bridges the ApiClient's session-expiry signal (fired after a silent refresh
  // fails on a non-probe request) into auth state and a user-visible toast.
  useEffect(() => {
    api.setOnSessionExpired(() => {
      // An anonymous tab's expiry changes nothing for the other tabs.
      const hadUser = userRef.current !== null;
      epochRef.current += 1;
      updateUser(null);
      setStatus('unauthenticated');
      if (hadUser) {
        queryClient.clear();
      }
      notifySignOutListeners();
      if (hadUser) {
        channelRef.current?.post('signed-out');
      }
      toast({
        title: tCommon('errors.sessionExpiredTitle'),
        description: tCommon('errors.sessionExpired'),
        variant: 'destructive',
      });
    });
    return () => api.setOnSessionExpired(null);
  }, [toast, tCommon, updateUser, queryClient]);

  // The Turnstile token is the sign-in form's, not this context's: it is minted by the
  // widget on that page and passed straight through to the transport.
  const login = useCallback(async (
    email: string,
    password: string,
    turnstileToken?: string | null
  ) => {
    // A probe in flight now predates the session this login creates, and one that settles
    // while the request is out must not act on the tab as if nothing were happening.
    const probeInvalidated = probesInFlightRef.current > 0;
    epochRef.current += 1;
    try {
      await api.login(email, password, turnstileToken);
    } catch (err) {
      // The invalidated probe left the tab in 'loading' and will not say otherwise.
      if (probeInvalidated) {
        await probeSession(false);
      }
      throw err;
    }
    channelRef.current?.post('signed-in');
    await refreshUser();
  }, [refreshUser, probeSession]);

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
    epochRef.current += 1;
    updateUser(null);
    setStatus('unauthenticated');
    // Drop cached queries so the next account on this tab cannot see them.
    queryClient.clear();
    notifySignOutListeners();
    channelRef.current?.post('signed-out');
    if (logoutFailed) {
      throw logoutError;
    }
  }, [queryClient, updateUser]);

  // A profile update the caller already holds is newer than any probe still in flight, and a
  // successful write proves the session was valid, so a status a probe left at 'loading'
  // settles here. A tab that holds no user ignores it: the write's response arrived after a
  // sign-out, and it must not sign the tab back in.
  const setCurrentUser = useCallback((next: User) => {
    if (userRef.current === null) {
      return;
    }
    epochRef.current += 1;
    updateUser(next);
    setStatus((current) => (current === 'loading' ? 'authenticated' : current));
  }, [updateUser]);

  const value = useMemo(() => ({
    user,
    status,
    isLoading: status === 'loading',
    isAuthenticated: status === 'authenticated',
    isServiceUnavailable: status === 'serviceUnavailable',
    login,
    logout,
    refreshUser,
    setCurrentUser,
  }), [user, status, login, logout, refreshUser, setCurrentUser]);

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
