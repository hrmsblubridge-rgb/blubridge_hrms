import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ============================================================================
// FEATURE FLAG — Onboarding gate
// ----------------------------------------------------------------------------
// When FALSE, the document-onboarding step is DISABLED app-wide: no employee is
// ever redirected to /employee/onboarding and everyone gets direct, full HRMS
// access immediately after login (regardless of their document-verification
// state). The Onboarding/Verification pages still exist and work — they are
// just no longer a mandatory gate.
//
// To RE-ENABLE the mandatory onboarding flow later, set this back to `true`.
// ============================================================================
const ONBOARDING_ENABLED = false;

// ============================================================================
// SECURITY — Access token (short-lived, ~10 min) + rotating refresh token.
// Access token is attached to every API request; on a 401 the interceptor
// silently calls /auth/refresh ONCE and retries. Logout revokes the session
// server-side, so old tokens stop working immediately.
// ============================================================================
export const TOKEN_KEY = 'blubridge_token';
export const REFRESH_TOKEN_KEY = 'blubridge_refresh_token';

// Bare client (NO interceptors) for refresh/logout calls — avoids loops.
const bareAxios = axios.create();

// Single-flight refresh: concurrent 401s share one refresh request.
let refreshPromise = null;
const refreshAuthTokens = () => {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const rt = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (!rt) throw new Error('No refresh token');
      const { data } = await bareAxios.post(`${API}/auth/refresh`, { refresh_token: rt });
      localStorage.setItem(TOKEN_KEY, data.token);
      localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token); // rotated
      return data.token;
    })().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
};

const clearStoredAuth = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

const isOurApi = (url) => !!url && (url.startsWith(API) || url.startsWith('/api'));
const AUTH_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/logout'];
const isAuthEndpoint = (url) => AUTH_ENDPOINTS.some((p) => (url || '').includes(p));

// Attach the CURRENT access token to every backend request (overrides any
// stale token a page captured before a silent refresh happened).
axios.interceptors.request.use((config) => {
  if (isOurApi(config.url) && !isAuthEndpoint(config.url)) {
    const t = localStorage.getItem(TOKEN_KEY);
    if (t) config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

// On 401 (expired access token or revoked session): refresh once, retry once.
// If refresh fails, clear auth state and send the user to login.
axios.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error;
    if (
      response?.status === 401 &&
      config &&
      isOurApi(config.url) &&
      !isAuthEndpoint(config.url) &&
      !config._authRetried
    ) {
      const hadSession = !!localStorage.getItem(TOKEN_KEY);
      try {
        const newToken = await refreshAuthTokens();
        config._authRetried = true;
        config.headers = { ...config.headers, Authorization: `Bearer ${newToken}` };
        return axios(config);
      } catch (_) {
        clearStoredAuth();
        if (hadSession && window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY));
  // Centralized avatar cache: { employee_id: avatar_url }. Single source of
  // truth for all admin modules (Attendance, Leave, Verification, etc.) so
  // they can render the correct photo without each endpoint having to
  // enrich its own response with avatar URLs.
  const [avatarMap, setAvatarMap] = useState({});

  const refreshAvatars = useCallback(async (tk) => {
    const useToken = tk || token || localStorage.getItem(TOKEN_KEY);
    if (!useToken) return;
    try {
      const resp = await axios.get(`${API}/employee-avatars`, {
        headers: { Authorization: `Bearer ${useToken}` },
      });
      setAvatarMap(resp.data || {});
    } catch (e) {
      // Non-fatal — admin pages will just show initials.
      console.warn('Avatar map fetch failed:', e?.response?.status);
    }
  }, [token]);

  // Public helper so any component can synchronously read the avatar by id.
  const getAvatarById = useCallback(
    (employeeId) => (employeeId ? avatarMap[employeeId] || null : null),
    [avatarMap]
  );

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem(TOKEN_KEY);
      if (savedToken) {
        try {
          // The response interceptor transparently refreshes an expired
          // access token here, so a returning user stays signed in.
          const response = await axios.get(`${API}/auth/me`);
          setUser(response.data);
          setToken(localStorage.getItem(TOKEN_KEY));
          // Hydrate avatar cache on app boot.
          refreshAvatars(localStorage.getItem(TOKEN_KEY));
        } catch (error) {
          console.error('Auth init error:', error);
          clearStoredAuth();
          setToken(null);
        }
      }
      setLoading(false);
    };
    initAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (username, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, { username, password });
      const { token: newToken, refresh_token: newRefresh, user: userData } = response.data;
      localStorage.setItem(TOKEN_KEY, newToken);
      if (newRefresh) localStorage.setItem(REFRESH_TOKEN_KEY, newRefresh);
      setToken(newToken);
      setUser(userData);
      // Hydrate avatar cache immediately after login.
      refreshAvatars(newToken);
      return { success: true, user: userData };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed'
      };
    }
  };

  const logout = async () => {
    // Revoke the session server-side FIRST so the old access/refresh tokens
    // are dead even if someone copied them. Local cleanup always runs.
    const t = localStorage.getItem(TOKEN_KEY);
    try {
      if (t) {
        await bareAxios.post(`${API}/auth/logout`, {}, {
          headers: { Authorization: `Bearer ${t}` },
        });
      }
    } catch (_) {
      // Best-effort — even if the network call fails we clear local state.
    }
    clearStoredAuth();
    setToken(null);
    setUser(null);
    setAvatarMap({});
  };

  const updateUser = useCallback((updates) => {
    setUser(prev => {
      if (!prev) return prev;
      // Skip the state update if nothing actually changed — prevents
      // re-render storms when callers (e.g. EmployeeProfile.fetchProfile)
      // call updateUser inside an effect.
      const next = { ...prev, ...updates };
      let changed = false;
      for (const k of Object.keys(updates || {})) {
        if (prev[k] !== updates[k]) { changed = true; break; }
      }
      return changed ? next : prev;
    });
  }, []);

  // Always read the CURRENT token — a silent refresh may have rotated it
  // after this component captured `token` state.
  const getAuthHeaders = useCallback(() => ({
    Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) || token}`
  }), [token]);

  // Check if user needs onboarding
  const needsOnboarding = () => {
    // Onboarding gate globally disabled — open HRMS access for all users.
    if (!ONBOARDING_ENABLED) return false;
    if (!user) return false;
    if (user.role !== 'employee') return false;
    return user.onboarding_status !== 'approved' && !user.onboarding_completed;
  };

  // Temporary 14-day document-verification bypass for newly created employees.
  // Returns true ONLY for users whose `documents_bypassed_until` (set at
  // creation by the backend) is still in the future. Existing employees and
  // admins are unaffected because the flag is missing on their records.
  const isWithinDocumentBypass = () => {
    if (!user) return false;
    const ts = user.documents_bypassed_until;
    if (!ts) return false;
    const exp = new Date(ts);
    if (Number.isNaN(exp.getTime())) return false;
    return exp.getTime() > Date.now();
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, getAuthHeaders, updateUser, needsOnboarding, isWithinDocumentBypass, avatarMap, getAvatarById, refreshAvatars }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
