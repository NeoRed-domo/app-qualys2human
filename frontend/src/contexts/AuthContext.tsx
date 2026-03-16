import {
  createContext, useContext, useState, useCallback, useEffect, useRef,
  type ReactNode,
} from 'react';
import api from '../api/client';

interface User {
  username: string;
  profile: string;
  mustChangePassword: boolean;
  firstName: string | null;
  lastName: string | null;
}

interface SessionConfig {
  timeout_minutes: number;
  warning_minutes: number;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (username: string, password: string, domain: string) => Promise<void>;
  logout: () => void;
  showTimeoutWarning: boolean;
  timeoutRemaining: number;
  dismissWarning: () => void;
  sessionConfig: SessionConfig;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

const DEFAULT_SESSION_CONFIG: SessionConfig = { timeout_minutes: 120, warning_minutes: 5 };
const ACTIVITY_DEBOUNCE_MS = 30_000;
const CHECK_INTERVAL_MS = 30_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  // User starts null — will be set only from server response, NEVER from localStorage
  const [user, setUser] = useState<User | null>(null);
  // loading = true while we verify identity against the server on mount
  const [loading, setLoading] = useState(() => !!localStorage.getItem('access_token'));

  // Block rendering until browser session is verified.
  const [sessionChecked, setSessionChecked] = useState(() => {
    if (!localStorage.getItem('access_token')) return true;
    if (sessionStorage.getItem('q2h_browser_session')) return true;
    return false;
  });

  const [sessionConfig, setSessionConfig] = useState<SessionConfig>(DEFAULT_SESSION_CONFIG);
  const [showTimeoutWarning, setShowTimeoutWarning] = useState(false);
  const [timeoutRemaining, setTimeoutRemaining] = useState(0);

  const lastActivityWrite = useRef(0);
  const isAuthenticated = !!user;

  // ── Verify identity from server ──────────────────────────────
  // Called on mount (if token exists) and after login.
  // This is the ONLY way user identity is set — never from localStorage.
  const verifyIdentity = useCallback(async (): Promise<User | null> => {
    try {
      const resp = await api.get('/auth/me');
      const u: User = {
        username: resp.data.username,
        profile: resp.data.profile,
        mustChangePassword: resp.data.must_change_password,
        firstName: resp.data.first_name ?? null,
        lastName: resp.data.last_name ?? null,
      };
      return u;
    } catch {
      // Token invalid/expired and refresh failed → not authenticated
      return null;
    }
  }, []);

  // ── Login ──────────────────────────────────────────────────
  const login = useCallback(async (username: string, password: string, domain: string) => {
    const resp = await api.post('/auth/login', { username, password, domain });
    const { access_token, refresh_token } = resp.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    localStorage.removeItem(`q2h_banner_dismissed_${username}`);
    sessionStorage.setItem('q2h_browser_session', '1');
    localStorage.setItem('q2h_last_activity', String(Date.now()));

    // Get identity from server (authoritative source)
    const u = await verifyIdentity();
    if (!u) throw new Error('Failed to verify identity after login');
    setUser(u);
  }, [verifyIdentity]);

  // ── Logout ─────────────────────────────────────────────────
  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('q2h_last_activity');
    sessionStorage.removeItem('q2h_browser_session');
    setUser(null);
    setShowTimeoutWarning(false);
  }, []);

  // ── On mount: verify identity from server ───────────────────
  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    (async () => {
      const u = await verifyIdentity();
      if (cancelled) return;
      if (u) {
        setUser(u);
      } else {
        // Token is invalid — clean up
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('q2h_last_activity');
      }
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Browser session detection (tab/window close) ───────────
  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;

    if (!sessionStorage.getItem('q2h_browser_session')) {
      const bc = new BroadcastChannel('q2h_session');
      let alive = false;
      const handler = (e: MessageEvent) => {
        if (e.data === 'ALIVE') alive = true;
      };
      bc.addEventListener('message', handler);
      bc.postMessage('CHECK');

      const timer = setTimeout(() => {
        bc.removeEventListener('message', handler);
        bc.close();
        if (!alive) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('q2h_last_activity');
          setUser(null);
          setLoading(false);
        } else {
          sessionStorage.setItem('q2h_browser_session', '1');
        }
        setSessionChecked(true);
      }, 300);

      return () => {
        clearTimeout(timer);
        bc.removeEventListener('message', handler);
        bc.close();
      };
    }
  }, []); // run once on mount

  // ── BroadcastChannel listener — respond to CHECK from other tabs ──
  useEffect(() => {
    if (!isAuthenticated) return;
    const bc = new BroadcastChannel('q2h_session');
    const handler = (e: MessageEvent) => {
      if (e.data === 'CHECK') bc.postMessage('ALIVE');
    };
    bc.addEventListener('message', handler);
    return () => {
      bc.removeEventListener('message', handler);
      bc.close();
    };
  }, [isAuthenticated]);

  // ── Cross-tab logout sync ──────────────────────────────────
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'access_token' && !e.newValue) {
        setUser(null);
        setShowTimeoutWarning(false);
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // ── Fetch session config after login ───────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    (async () => {
      try {
        const resp = await api.get('/settings/session');
        if (!cancelled) setSessionConfig(resp.data);
      } catch {
        // use defaults
      }
    })();
    return () => { cancelled = true; };
  }, [isAuthenticated]);

  // ── Activity tracking (debounced) ──────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;

    const updateActivity = () => {
      const now = Date.now();
      if (now - lastActivityWrite.current >= ACTIVITY_DEBOUNCE_MS) {
        lastActivityWrite.current = now;
        localStorage.setItem('q2h_last_activity', String(now));
      }
    };
    localStorage.setItem('q2h_last_activity', String(Date.now()));
    lastActivityWrite.current = Date.now();

    const events = ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'] as const;
    events.forEach((e) => window.addEventListener(e, updateActivity));
    return () => {
      events.forEach((e) => window.removeEventListener(e, updateActivity));
    };
  }, [isAuthenticated]);

  // ── Inactivity check interval ──────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;

    const interval = setInterval(() => {
      const last = Number(localStorage.getItem('q2h_last_activity') || 0);
      const elapsed = Date.now() - last;
      const timeoutMs = sessionConfig.timeout_minutes * 60 * 1000;
      const warningMs = sessionConfig.warning_minutes * 60 * 1000;

      if (elapsed >= timeoutMs) {
        logout();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      } else if (elapsed >= timeoutMs - warningMs) {
        setShowTimeoutWarning(true);
        setTimeoutRemaining(Math.ceil((timeoutMs - elapsed) / 1000));
      } else {
        setShowTimeoutWarning(false);
      }
    }, CHECK_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isAuthenticated, sessionConfig, logout]);

  // ── Countdown timer (1s) when warning is shown ─────────────
  useEffect(() => {
    if (!showTimeoutWarning) return;
    const interval = setInterval(() => {
      setTimeoutRemaining((prev) => {
        if (prev <= 1) {
          logout();
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [showTimeoutWarning, logout]);

  // ── Dismiss warning = "Stay connected" ─────────────────────
  const dismissWarning = useCallback(() => {
    localStorage.setItem('q2h_last_activity', String(Date.now()));
    lastActivityWrite.current = Date.now();
    setShowTimeoutWarning(false);
    api.post('/auth/refresh', {
      refresh_token: localStorage.getItem('refresh_token'),
    }).then((resp) => {
      const { access_token, refresh_token: newRefresh } = resp.data;
      localStorage.setItem('access_token', access_token);
      if (newRefresh) localStorage.setItem('refresh_token', newRefresh);
    }).catch(() => {
      // If refresh fails, user will be logged out on next 401
    });
  }, []);

  // Don't render anything until browser session check completes.
  if (!sessionChecked) return null;

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated,
      loading,
      login,
      logout,
      showTimeoutWarning,
      timeoutRemaining,
      dismissWarning,
      sessionConfig,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
