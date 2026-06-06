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

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('blubridge_token'));
  // Centralized avatar cache: { employee_id: avatar_url }. Single source of
  // truth for all admin modules (Attendance, Leave, Verification, etc.) so
  // they can render the correct photo without each endpoint having to
  // enrich its own response with avatar URLs.
  const [avatarMap, setAvatarMap] = useState({});

  const refreshAvatars = useCallback(async (tk) => {
    const useToken = tk || token || localStorage.getItem('blubridge_token');
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
      const savedToken = localStorage.getItem('blubridge_token');
      if (savedToken) {
        try {
          const response = await axios.get(`${API}/auth/me`, {
            headers: { Authorization: `Bearer ${savedToken}` }
          });
          setUser(response.data);
          setToken(savedToken);
          // Hydrate avatar cache on app boot.
          refreshAvatars(savedToken);
        } catch (error) {
          console.error('Auth init error:', error);
          localStorage.removeItem('blubridge_token');
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
      const { token: newToken, user: userData } = response.data;
      localStorage.setItem('blubridge_token', newToken);
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

  const logout = () => {
    localStorage.removeItem('blubridge_token');
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

  const getAuthHeaders = useCallback(() => ({
    Authorization: `Bearer ${token}`
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
